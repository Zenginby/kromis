"""Sözlük anahtarının EKRANA sızmadığı — tarayıcıda ölçülüyor.

NEDEN BU DOSYA VAR: çeviriye geçerken etiket tabloları anahtar tablosuna
döndü (`HARMONY_KEYS`, `PROMPT_YER_TUTUCU`, `MODEL_EKSENLERI` …) ve o
tabloların değerlerini okuyan HER yerin `t()`den geçmesi gerekti. Bir tanesi
geçmedi: `syncPromptPlaceholder` `metin.tam`ı doğrudan `placeholder`a yazıyordu
ve kullanıcı composer'da "composer.placeholder_director" okuyordu.

Kaynak taraması o kusuru göremiyor: satırda tablonun ADI bile geçmiyor, yerel
bir takma ad (`metin`) var. Python testleri de göremiyor: `t()` çağrısı
tarayıcıda koşuyor. Ölçülebildiği tek yer DOM — ve ölçülen şey tam olarak
kullanıcının gördüğü şey: ekranda bir anahtar duruyor mu?

Kapsam DOM'un TAMAMI, yalnız görünen bölme değil: gizli paneller de aynı
sayfada duruyor, yani tek yükleme arayüzün büyük kısmını tarıyor. Dinamik
çizilen parçalar (model kartları, ayar bölmeleri) için gezinti yapılıyor.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import catalog
import credstore
import i18n
import prefs
from app import app

# Ekranda anahtar arayan tarama. `value` de okunuyor: kusurun ilk görüldüğü
# yer bir `placeholder`dı ve `<option>`/`<input>` değerleri de metin taşıyor.
TARAMA = """() => {
  const cikti = new Set();
  const oznitelikler = ["placeholder", "title", "aria-label", "alt", "value"];
  for (const el of document.querySelectorAll("*")) {
    for (const ad of oznitelikler) {
      const deger = el.getAttribute(ad);
      if (deger) cikti.add(deger.trim());
    }
    for (const dugum of el.childNodes) {
      if (dugum.nodeType === 3 && dugum.textContent.trim()) {
        cikti.add(dugum.textContent.trim());
      }
    }
  }
  return [...cikti];
}"""


def _bos_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Sunucu(threading.Thread):
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.server = uvicorn.Server(
            uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning"))

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def _kurgu(monkeypatch, dil: str) -> None:
    """Öncül KURGUYLA kuruluyor, makineden umulmuyor.

    `test_playwright_studio._tum_kimlikler_kayitli`nin gerekçesinin aynısı:
    anahtarsız bir sunucuda model şeridi boş açılıyor ve taranacak metnin
    yarısı hiç çizilmiyor. Dil de aynı sebeple kurgulanıyor — geliştiricinin
    kendi `prefs.json`una dokunmadan.
    """
    monkeypatch.setattr(credstore, "configured_map",
                        lambda *a, **k: {c.id: True for c in catalog.CREDENTIALS})
    monkeypatch.setattr(credstore, "chat_configured_map",
                        lambda *a, **k: {m.id: True for m in catalog.CHAT_MODELS})
    gercek = prefs.read
    monkeypatch.setattr(prefs, "read",
                        lambda *a, **k: {**gercek(*a, **k), "language": dil})


def _tikla(page, secici: str) -> None:
    """Perde ARKASINDAN tıklar.

    İlk kurulumda Ayarlar kendiliğinden açılıyor ve `#shell-scrim` isabet
    testini yutuyor (`test_playwright_studio`daki perde notunun aynısı).
    Burada perdeyi kapatmak yerine JS tıklaması kullanılıyor: bu testin
    ölçtüğü şey tıklamanın ULAŞMASI değil, çizilen metin.
    """
    if page.query_selector(secici):
        page.eval_on_selector(secici, "el => el.click()")
        page.wait_for_timeout(120)


@pytest.mark.parametrize("dil", i18n.LANGUAGES)
def test_no_dictionary_key_reaches_the_screen(monkeypatch, dil):
    """ASIL İDDİA: kullanıcı hiçbir yerde "composer.placeholder" okumuyor.

    İki dilde birden koşuyor çünkü eksik anahtar dile göre değişebilir: bir
    katalogda olup ötekinde olmayan anahtar, yalnız o dilde sızardı.
    """
    _kurgu(monkeypatch, dil)
    anahtarlar = set(i18n.catalog(dil))
    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    time.sleep(1.0)

    sizanlar: set[str] = set()
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            sayfa = tarayici.new_page()
            sayfa.goto(f"http://127.0.0.1:{port}")
            sayfa.wait_for_selector("#view-studio")
            sayfa.wait_for_function(
                '() => { const m = document.querySelector("#model");'
                ' return (m && m.value !== "") || !!document.querySelector(".sheet.open"); }')

            def tara():
                sizanlar.update(m for m in sayfa.evaluate(TARAMA) if m in anahtarlar)

            tara()
            # Üç mod: yer tutucu, "Üret" düğmesi ve eksene bağlı her şey
            # moda göre yeniden yazılıyor — kusurun çıktığı yol tam buydu.
            for sekme in ("#tab-video", "#tab-chat", "#tab-image"):
                _tikla(sayfa, sekme)
                tara()
            # Gönderim sonrası KISA yer tutucu: ayrı bir tablo satırı, ayrı
            # bir sızma ihtimali.
            sayfa.evaluate('() => { document.querySelector("#composer").dataset.sent = "1";'
                           ' syncPromptPlaceholder(); }')
            tara()

            # Ayarlar'ın her bölmesi: içerik gizli de olsa DOM'da, ama şerit
            # düğmeleri bölmeyi ayrıca çiziyor (sağlayıcı rozetleri).
            _tikla(sayfa, "#settings-btn")
            for dugme in sayfa.query_selector_all(".settings-nav .picker-nav-item"):
                dugme.evaluate("el => el.click()")
                sayfa.wait_for_timeout(80)
                tara()
            sayfa.keyboard.press("Escape")

            # Model panelleri: kartlar JS'te çiziliyor, şablonda yoklar.
            for tetik in ("#model-btn", "#chat-model-btn", "#video-model-btn"):
                _tikla(sayfa, tetik)
                tara()
                sayfa.keyboard.press("Escape")
                sayfa.wait_for_timeout(120)

            # Medya ve palet görünümleri: boş hâl metinleri burada.
            for tetik in ("#tab-media", "#palette-btn", "#tools-btn"):
                _tikla(sayfa, tetik)
                tara()

            tarayici.close()
    finally:
        sunucu.stop()

    assert not sizanlar, (
        f"{dil}: ekranda çevrilmemiş sözlük anahtarı duruyor: {sorted(sizanlar)}")
