"""Yeni sürüm bildirimi — TARAYICIDA ölçülen kısmı.

NEDEN BURADA SINANIYOR: kusur yalnız tarayıcıda görünüyordu. Sunucu tarafı
kusursuz çalışıyordu — `guncelleme.bilgi()` bayat önbellekte tazelemeyi arka
plana atıp `None` dönüyor (2. sözleşme), arka plan iş parçacığı GitHub'a sorup
cevabı diske yazıyor. Her birim testi yeşildi. Eksik olan tek şey ön yüzün o
cevabı BİR DAHA HİÇ SORMAMASIYDI: `settings.js` `/api/settings`'i yalnız
açılışta bir kez çağırıyor, yani tazelenen cevap bir sonraki uygulama açılışına
kadar diskte kalıyordu. Kullanıcı tarafından bakıldığında bu, bildirimin hiç
gelmemesiyle aynı şey — ve kaynak taraması bunu yakalayamaz, çünkü iki tarafta
da kod "doğru" görünüyor.

Bu dosya `test_playwright_studio.py`den AYRI: oradaki koşum kimlik/katalog
kurgusu kuruyor, buradaki testin öncülü ise anahtarsız bir kurulum (bildirim
kimlikten bağımsız).
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time

import pytest
import uvicorn

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import guncelleme
import version
from app import app

# Kapı GERÇEK (Faz 1 / 4): oturum `e2e_oturum`dan; `guncelleme.json` önbelleği
# kullanıcının kendi `output/`unda (`ayar.ayarlar` kullanıcıya göre) — kurgu
# dosyası oraya yazılıyor, `tmp_path`in köküne değil.
pytestmark = pytest.mark.gercek_kimlik


@pytest.fixture(autouse=True)
def _dondurulmus_kabuk_kipi(monkeypatch):
    """İlk üç test DONDURULMUŞ KABUĞUN arayüzünü ölçüyor (Faz 1 / 9).

    `veritabani` `DATABASE_URL` veriyor ve o, web bayrağı (`guncelleme.web_yapisi`);
    sunucu aynı süreçte koştuğu için modül özniteliğini yamamak yeter. Web
    kipinin E2E bekçisi aşağıda, kendi `web_kipi` fixture'ıyla (autouse'tan
    sonra kurulur, kazanır). Gerekçenin tamamı tests/test_guncelleme_route.py.
    """
    monkeypatch.setattr(guncelleme, "web_yapisi", lambda: False)


@pytest.fixture
def web_kipi(monkeypatch):
    monkeypatch.setattr(guncelleme, "web_yapisi", lambda: True)

YENI_SURUM = "99.0.0"
YENI_URL = f"{guncelleme.GECERLI_URL_ONEKI}releases/tag/v{YENI_SURUM}"


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


def test_the_update_notice_appears_without_reloading_the_page(monkeypatch, veritabani, e2e_oturum):
    """ASIL İDDİA: arka plan kontrolü cevabı bulduğunda AÇIK sayfa onu gösteriyor.

    Kurgu tam olarak gerçek ilk açılış: önbellek bayat (`zaman: 0`), yani
    `/api/settings` "bilmiyorum" diyor ve tazeleme arka planda başlıyor. Bu
    testin ölçtüğü şey o andan SONRA ne olduğu.

    Yalnız GitHub çağrısı (`_sor`) taklit ediliyor — testin ağa çıkması, ölçtüğü
    şeyi GitHub'ın o anki yayınına bağlardı. Aradaki her şey (önbellek yazımı,
    iş parçacığı, uç nokta, yoklama, DOM) GERÇEK.
    """
    oturum = e2e_oturum()
    out = oturum.ayarlar().output_dir
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": YENI_SURUM, "url": YENI_URL})
    guncelleme._KOSUYOR = False
    with open(os.path.join(out, guncelleme.ONBELLEK_DOSYASI), "w", encoding="utf-8") as f:
        f.write('{"zaman": 0}')

    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    time.sleep(1.0)
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            sayfa = tarayici.new_page()
            oturum.cerez(sayfa, f"http://127.0.0.1:{port}")
            sayfa.goto(f"http://127.0.0.1:{port}")
            sayfa.wait_for_selector("#view-studio")

            # Açılışta hiçbir şey görünmüyor: cevap henüz yok. Bu iddia
            # testin kendisini de koruyor — rozet baştan açık olsaydı
            # aşağıdaki bekleyiş hiçbir şey KANITLAMAZDI.
            assert not sayfa.eval_on_selector("#settings-btn",
                                              "el => el.classList.contains('has-update')")

            # Yoklama 3. saniyede: sayfa yeniden YÜKLENMEDEN rozet geliyor.
            sayfa.wait_for_selector("#settings-btn.has-update", timeout=15000)

            assert sayfa.eval_on_selector("#settings-update", "el => el.hidden") is False
            assert sayfa.inner_text("#settings-update-version") == YENI_SURUM
            assert sayfa.get_attribute("#settings-update-link", "href") == YENI_URL
            # Eylem bir DÜĞME gibi duruyor — kartın öteki bağlantılarından
            # ayırt edilebilmesinin tek işareti bu.
            assert "btn-ghost" in sayfa.get_attribute("#settings-update-link", "class")
            # Rozet salt görsel olamaz: anlamı düğmenin adına da girmeli.
            assert YENI_SURUM in sayfa.get_attribute("#settings-btn", "aria-label")

            tarayici.close()
    finally:
        sunucu.stop()
        guncelleme._KOSUYOR = False


def test_the_check_now_button_finds_a_release_the_cache_never_asked_for(monkeypatch, veritabani, e2e_oturum):
    """ASIL İDDİA: önbellek TAZE ama cevabı bayatken düğme yine de buluyor.

    Kurgu, 2026-09-12'de gerçekten yaşanan durum: telefonda kurulu sürüm
    güncel sanılıyor, çünkü son başarılı kontrol birkaç saat önce koştu ve o
    an en yenisi buydu. Arada yeni bir yayın çıktı; `TTL_SANIYE` dolmadığı için
    otomatik yol GitHub'a HİÇ sormuyor ve kullanıcının elinde tetikleyecek
    bir şey yok.

    Sunucu tarafı `tests/test_guncelleme_route.py`de zaten ölçülü. Buradaki
    soru ön yüzün kendisi: düğme gerçekten POST atıyor mu, cevap satıra ve
    ROZETE işliyor mu, durum cümlesi yazılıyor mu. Kardeş testin gerekçesi
    aynen geçerli — iki tarafta da "doğru" görünen kod, tarayıcıda hiçbir şey
    yapmayan bir düğme üretebiliyor.
    """
    oturum = e2e_oturum()
    out = oturum.ayarlar().output_dir
    guncelleme._KOSUYOR = False

    # TAZE önbellek: kurulu sürüm en yenisi sanılıyor, tazeleme tetiklenmiyor.
    with open(os.path.join(out, guncelleme.ONBELLEK_DOSYASI), "w", encoding="utf-8") as f:
        f.write(json.dumps({"zaman": time.time(), "son_deneme": time.time(),
                            "surum": version.APP_VERSION}))

    soruldu = []

    def _sor():
        soruldu.append(1)
        return {"surum": YENI_SURUM, "url": YENI_URL}

    monkeypatch.setattr(guncelleme, "_sor", _sor)

    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    time.sleep(1.0)
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            sayfa = tarayici.new_page()
            oturum.cerez(sayfa, f"http://127.0.0.1:{port}")
            sayfa.goto(f"http://127.0.0.1:{port}")
            sayfa.wait_for_selector("#view-studio")
            # Modal KENDİLİĞİNDEN açılıyor (anahtarsız kurulumda
            # `loadSettings(true)` onu açıyor), o yüzden dişliye tıklamak
            # gerekmiyor — üstelik scrim tıklamayı keserdi.
            sayfa.wait_for_selector("#settings-modal.open")
            sayfa.click('#settings-nav [data-pane="about"]')

            # Öncül: otomatik yol sormadı ve satır gizli. Bu iddia olmadan
            # aşağıdaki tıklama hiçbir şey kanıtlamazdı.
            assert soruldu == []
            assert sayfa.eval_on_selector("#settings-update", "el => el.hidden") is True

            sayfa.click("#settings-update-check")

            sayfa.wait_for_selector("#settings-update:not([hidden])", timeout=15000)
            assert soruldu == [1]                       # GitHub'a GERÇEKTEN soruldu
            assert sayfa.inner_text("#settings-update-version") == YENI_SURUM
            assert sayfa.get_attribute("#settings-update-link", "href") == YENI_URL
            # Rozet de işleniyor: telefonda yeni sürümü haber veren TEK yüzey o.
            assert sayfa.eval_on_selector(
                "#settings-btn", "el => el.classList.contains('has-update')")
            # Düğmeye basan kişi bir CEVAP görmeli — sessiz bir düğme,
            # çalışmayan bir düğmeden ayırt edilemez.
            assert YENI_SURUM in sayfa.inner_text("#settings-update-check-status")

            tarayici.close()
    finally:
        sunucu.stop()
        guncelleme._KOSUYOR = False


def test_the_check_now_button_answers_when_there_is_nothing_new(monkeypatch, veritabani, e2e_oturum):
    """"Güncelsin" bir CEVAP, sessizlik değil. `bilgi()` bu durumu "soramadım"la
    aynı `None`a indiriyor; elle basılan bir düğmede farkı `durum` taşıyor ve
    ekranda görünmesi gereken şey de o."""
    oturum = e2e_oturum()
    guncelleme._KOSUYOR = False
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": version.APP_VERSION, "url": YENI_URL})

    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    time.sleep(1.0)
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            sayfa = tarayici.new_page()
            oturum.cerez(sayfa, f"http://127.0.0.1:{port}")
            sayfa.goto(f"http://127.0.0.1:{port}")
            sayfa.wait_for_selector("#view-studio")
            # Modal KENDİLİĞİNDEN açılıyor (anahtarsız kurulumda
            # `loadSettings(true)` onu açıyor), o yüzden dişliye tıklamak
            # gerekmiyor — üstelik scrim tıklamayı keserdi.
            sayfa.wait_for_selector("#settings-modal.open")
            sayfa.click('#settings-nav [data-pane="about"]')
            sayfa.click("#settings-update-check")

            # Boş kalmıyor: yazı geliyor ve satır GİZLİ kalıyor.
            sayfa.wait_for_function(
                "() => document.getElementById("
                "'settings-update-check-status').textContent.trim().length > 0",
                timeout=15000)
            yazi = sayfa.inner_text("#settings-update-check-status")
            assert yazi and "{" not in yazi          # ham anahtar/değişken değil
            assert sayfa.eval_on_selector("#settings-update", "el => el.hidden") is True

            tarayici.close()
    finally:
        sunucu.stop()
        guncelleme._KOSUYOR = False



def test_on_the_web_build_the_update_ui_is_hidden_and_the_page_never_asks(
        monkeypatch, veritabani, e2e_oturum, web_kipi):
    """Web yapısı (Faz 1 / 9): "şimdi kontrol et" satırı, tercih anahtarı ve ipucu
    GİZLİ; rozet yok; sayfa `/api/guncelleme`yi HİÇ sormuyor (yoklama da kapalı);
    bayat önbellek yerinde ve yeniden yazılmamış.

    Kurgu kabuk testinin aynısı (bayat `zaman: 0` + GitHub'a cevap verecek `_sor`):
    kabukta 3. saniyede rozet gelirdi — burada 4 saniye sonra hâlâ hiçbir istek yok.
    `index.html` DEĞİŞMEDİ: çapalar `settings.js`in `webKipineGec`inin bulduğu
    ebeveynler; test de aynı yoldan bakıyor.
    """
    oturum = e2e_oturum()
    out = oturum.ayarlar().output_dir
    monkeypatch.setattr(guncelleme, "_sor",
                        lambda: {"surum": YENI_SURUM, "url": YENI_URL})
    guncelleme._KOSUYOR = False
    onbellek = os.path.join(out, guncelleme.ONBELLEK_DOSYASI)
    with open(onbellek, "w", encoding="utf-8") as f:
        f.write('{"zaman": 0}')

    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    time.sleep(1.0)
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            sayfa = tarayici.new_page()
            istekler: list[str] = []
            sayfa.on("request", lambda r: istekler.append(r.url) if "/api/guncelleme" in r.url else None)
            oturum.cerez(sayfa, f"http://127.0.0.1:{port}")
            sayfa.goto(f"http://127.0.0.1:{port}")
            sayfa.wait_for_selector("#view-studio")
            sayfa.wait_for_selector("#settings-modal.open")     # anahtarsız kurulum: kendiliğinden
            sayfa.click('#settings-nav [data-pane="about"]')

            assert sayfa.eval_on_selector("#settings-update-check", "el => el.closest('p').hidden") is True
            assert sayfa.eval_on_selector("#pref-guncelleme", "el => el.closest('label').hidden") is True
            assert sayfa.eval_on_selector(
                "#pref-guncelleme", "el => el.closest('label').nextElementSibling.hidden") is True
            assert sayfa.eval_on_selector("#settings-update", "el => el.hidden") is True
            # Sürüm satırı DURUYOR: kapanan denetim, kimlik değil.
            assert sayfa.inner_text("#settings-modal [data-app-version]").strip() == version.APP_VERSION

            time.sleep(4.0)                                    # kabukta ilk yoklama 3. saniyede
            assert istekler == [], "web'de sayfa /api/guncelleme'yi sordu"
            assert not sayfa.eval_on_selector("#settings-btn", "el => el.classList.contains('has-update')")
            with open(onbellek, encoding="utf-8") as f:
                assert f.read() == '{"zaman": 0}', "önbellek web'de yeniden yazıldı"

            tarayici.close()
    finally:
        sunucu.stop()
        guncelleme._KOSUYOR = False
