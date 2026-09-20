"""İş paneli E2E — Faz 2 / 5'in ÇIKIŞ KRİTERİ (docs/faz2-kuyruk-anahtarlar-depolama.md §5).

Dört tarayıcı gerçeği, hepsi yalnız burada ölçülebilir (kaynak taraması SSE'nin
düşüp düşmediğini, sekmenin kapanıp açılmasını göremez):

  1. SEKME KAPALIYKEN BİTEN İŞ YENİ SEKMEDE GÖRÜNÜYOR: sahte sağlayıcı 8 sn
     uyur, iş gönderilir, SAYFA KAPATILIR, işçi iş parçacığı işi bitirir, yeni
     sayfa açılır → panelde `bitti` + önizleme, galeride görsel. Gerçek 6 dk
     video yerine 8 sn: süre değil SÜREÇ sınanıyor.
  2. İKİ İŞ SIRADA, YENİLEMEDEN SONRA İKİSİ DE PANELDE: #go artık kilit değil
     (1 sn soğuma), ikinci iş birincisi sürerken sıraya girer; yenilenen sekme
     ikisini de `GET /api/isler`den geri alır ve bitince galeri SSE ile dolar.
  3. HATA → "YENİDEN GÖNDER" YENİ İŞ: sağlayıcı düşer, satır `hata` + düğme;
     düğme `POST /api/isler/{id}/yeniden` → panelde ikinci satır, düzelen
     sağlayıcıyla `bitti`.
  4. SSE DÜŞERSE YOKLAMA SÜRÜYOR: `/api/isler/akis` tarayıcıda kesilir
     (`page.route` abort), üç düşüşten sonra panel yedek yola geçer ve iş yine
     `bitti`ye ulaşır.
  5. SAYAÇ SUNUCUNUN DOĞUSUNDAKİ TARAYICIDA 0'DAN BAŞLIYOR (Faz 2 / 10, "180"
     kusuru): sunucu süreci UTC'de, tarayıcı `Europe/Istanbul` — `basladi`
     dilimli UTC (`Z`) geldiği için geçen süre saniyelerle ölçülür, "180:00"
     değil. Yalnız tarayıcı ölçebilir: `new Date()` tarayıcının dilimindedir.
  6. KREDİ GERİ GELİYOR (Faz 3 / 2 çıkış ölçütü): platform anahtarlı iş bakiyeyi
     tahmin kadar düşürür; sahte sağlayıcı düşer → panelde `hata`, bakiye ESKİ
     değerine döner (iade); "yeniden gönder" → `bitti`, satırda "~tahmin → gerçek",
     bakiye gerçek kadar eksik. Tarayıcı → 202 → işçi → SSE → panel zinciri
     defterle birlikte ancak burada uçtan uca ölçülür.

Sunucu ve işçi `tests/test_playwright_studio.py`nin `ServerThread`/`IsciThread`
ikilisi — aynı süreç, gerçek kuyruk (Postgres), sağlayıcı `monkeypatch`.
Zaman ölçümü: 1. test 8 sn uykuyu taşır, ötekiler saniyeler; toplam süre
belgeye yazıldı (§5 "Yapıldığında").
"""
from __future__ import annotations

import io
import os
import re
import threading
import time

import pytest

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright
from sqlalchemy import select

import azure_client as ac
import providers
from services import defter, kapilar, tablolar
from tests.conftest import posix_gerekir
from tests.test_playwright_studio import (
    ServerThread,
    _ilk_kurulum_perdesini_kapat,
    _tum_kimlikler_kayitli,
    get_free_port,
    sunucu_hazir,
)

pytestmark = pytest.mark.gercek_kimlik

PANEL_SATIR = "#isler-liste .is-satir"


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 80, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _uyuyan_saglayici(sn: float, sayac: list | None = None):
    """`providers.generate` yaması: `sn` uyur, n görsel döner; `sayac` her çağrıyı kaydeder."""
    png = _png()

    def uret(model, prompt, size, quality, n, **k):
        if sayac is not None:
            sayac.append(prompt)
        time.sleep(sn)
        return [png] * n
    return uret


def _durumlar(oturum) -> list[str]:
    """Bu testin kullanıcısının işleri, eskiden yeniye. DB dosya başına bir kopya ve her test
    kendi kullanıcısını açıyor (`e2e_oturum`): süzgeçsiz sorgu önceki testlerin işlerini sayardı."""
    with oturum.db() as db:
        return [i.durum for i in db.scalars(
            select(tablolar.Is).where(tablolar.Is.kullanici_id == oturum.kullanici_id)
            .order_by(tablolar.Is.olusturuldu))]


def _bitmeyi_bekle(oturum, adet: int, sure_sn: float = 30.0) -> None:
    """İşçi iş parçacığı `adet` işi kapatıncaya kadar (bitti/hata) bekler — DB'den okur."""
    son = time.monotonic() + sure_sn
    while time.monotonic() < son:
        durumlar = _durumlar(oturum)
        if len(durumlar) >= adet and all(d in ("bitti", "hata", "iptal") for d in durumlar[:adet]):
            return
        time.sleep(0.2)
    raise AssertionError(f"{sure_sn} sn içinde {adet} iş kapanmadı: {_durumlar(oturum)}")


def _studyo(page, taban: str, oturum) -> None:
    oturum.cerez(page, taban)
    page.goto(taban)
    page.wait_for_selector("#view-studio")
    _ilk_kurulum_perdesini_kapat(page)


def _gonder(page, prompt: str) -> None:
    """Prompt yaz, #go'ya bas; soğuma bitince (#go serbest) döner ki ikinci gönderim kilide takılmasın."""
    page.wait_for_function('!document.querySelector("#go").disabled')
    page.fill("#prompt", prompt)
    page.click("#go")
    page.wait_for_function('document.querySelector("#composer").dataset.sent === "true"')
    page.wait_for_function('!document.querySelector("#go").disabled')


def _paneldekiler_bitsin(page, oturum, adet: int, sure_sn: float = 20.0) -> None:
    """Paneldeki `adet` satırın hepsi `bitti` olana kadar bekler; düşerse DB ile paneli yan yana yazar
    (bir `wait_for_function` zaman aşımı hangi tarafın geride kaldığını söylemez)."""
    son = time.monotonic() + sure_sn
    while time.monotonic() < son:
        durumlar = page.eval_on_selector_all(PANEL_SATIR, "els => els.map(e => e.dataset.durum)")
        if len(durumlar) == adet and all(d == "bitti" for d in durumlar):
            return
        time.sleep(0.25)
    raise AssertionError(
        f"panel {sure_sn} sn'de bitmedi — panel: {durumlar}, DB: {_durumlar(oturum)}, "
        f"durum satırı: {page.inner_text('#isler-durum')!r}")


def _paneli_ac(page) -> None:
    page.click("#isler-btn")
    page.wait_for_selector("#isler-sheet.open")


def test_a_job_that_finishes_while_the_tab_is_closed_shows_up_in_a_fresh_tab(
        monkeypatch, veritabani, e2e_oturum):
    """Çıkış kriteri: sekme kapalıyken biten iş yeni sekmede panelde `bitti`, galeride görsel."""
    _tum_kimlikler_kayitli(monkeypatch)
    monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(8.0))
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    taban = f"http://127.0.0.1:{port}"
    t0 = time.perf_counter()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _gonder(page, "sekme kapanacak")
            # İş sırada/işçide: rozet 1, panelde aktif bir satır.
            page.wait_for_function('document.querySelector("#isler-sayac").textContent === "1"')
            _paneli_ac(page)
            satir = page.wait_for_selector(PANEL_SATIR)
            assert satir.get_attribute("data-durum") in ("bekliyor", "calisiyor")
            assert page.eval_on_selector(PANEL_SATIR + " .is-tur", "e => e.textContent") == "Image"
            # SAYFA KAPANIYOR — iş sürüyor (sağlayıcı 8 sn uyuyor).
            page.close()
            assert _durumlar(oturum)[0] in ("bekliyor", "calisiyor"), "iş sayfayla birlikte ölmedi"

            _bitmeyi_bekle(oturum, 1)
            assert _durumlar(oturum) == ["bitti"]

            # YENİ SEKME: panel `GET /api/isler`den işi geri alır, önizleme çeker; galeri dolu.
            yeni = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(yeni, taban, oturum)
            _paneli_ac(yeni)
            yeni.wait_for_selector(PANEL_SATIR + '[data-durum="bitti"]')
            yeni.wait_for_selector(PANEL_SATIR + " .is-onizleme img")
            assert yeni.eval_on_selector(PANEL_SATIR + " .is-durum", "e => e.textContent") == "done"
            assert yeni.eval_on_selector("#isler-sayac", "e => e.hidden") is True, "aktif iş yok, rozet gizli"
            yeni.keyboard.press("Escape")
            yeni.evaluate('showSection("media")')
            yeni.wait_for_selector("#gallery .card")
            assert yeni.eval_on_selector_all("#gallery .card", "els => els.length") == 1
            browser.close()
    finally:
        server.stop()
    print(f"\nE2E (1) sekme kapalıyken biten iş: {time.perf_counter() - t0:.1f} sn (8 sn uyku dâhil)")


def test_two_queued_jobs_survive_a_reload_and_both_land_in_the_gallery(
        monkeypatch, veritabani, e2e_oturum):
    """#go kilit değil: ikinci iş birincisi sürerken sıraya girer; yenilenen sekme ikisini de gösterir."""
    _tum_kimlikler_kayitli(monkeypatch)
    monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(2.5))
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    taban = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _gonder(page, "birinci")
            assert page.is_disabled("#go") is False, "soğuma bitti, düğme serbest"
            _gonder(page, "ikinci")
            page.wait_for_function('document.querySelector("#isler-sayac").textContent === "2"')
            assert len(_durumlar(oturum)) == 2, "iki iş kuyrukta: kilit yok, tavan sunucuda"

            page.reload()
            page.wait_for_selector("#view-studio")
            _ilk_kurulum_perdesini_kapat(page)
            _paneli_ac(page)
            page.wait_for_function(
                f'document.querySelectorAll("{PANEL_SATIR}").length === 2')
            durumlar = page.eval_on_selector_all(PANEL_SATIR, "els => els.map(e => e.dataset.durum)")
            assert all(d in ("bekliyor", "calisiyor", "bitti") for d in durumlar), durumlar
            assert any(d in ("bekliyor", "calisiyor") for d in durumlar), (
                "yenilemeden sonra aktif iş panelde değil")
            # Panel en yeni üstte: ikinci gönderim ilk satır.
            assert page.eval_on_selector_all(PANEL_SATIR + " .is-durum",
                                             "els => els.length") == 2

            # İkisi de bitince (SSE) galeri yenilenmiş sekmede de dolar — geri çağrı yok, ürün var.
            # ÖLÇÜLEN KUSUR: ilk sürümde akışın ilk turu yalnız AKTİF işleri yazıyordu
            # ve yenilemenin liste → bağlanma aralığında biten iş panelde
            # `calisiyor` diye donuyordu (DB `bitti`). Akışın ilk turu artık son
            # 30 sn'de değişenleri de yazıyor (routers/isler.py `AKIS_ILK_PENCERE_SN`).
            _paneldekiler_bitsin(page, oturum, 2)
            page.keyboard.press("Escape")
            page.evaluate('showSection("media")')
            page.wait_for_function('document.querySelectorAll("#gallery .card").length === 2',
                                   timeout=10000)
            assert _durumlar(oturum) == ["bitti", "bitti"]
            browser.close()
    finally:
        server.stop()


def test_a_failed_job_offers_resubmit_and_the_resubmitted_job_finishes(
        monkeypatch, veritabani, e2e_oturum):
    """Sağlayıcı düşer → satır `hata` + "yeniden gönder" → yeni iş; düzelen sağlayıcıyla biter."""
    _tum_kimlikler_kayitli(monkeypatch)

    def bozuk(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "generate", bozuk)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    taban = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _gonder(page, "dusecek")
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="hata"]', timeout=15000)
            assert "500" in page.eval_on_selector(PANEL_SATIR + " .is-hata", "e => e.textContent")
            # Döküm turu geri alındı, prompt kutuya döndü (`geriAl`), durum satırı sebebi söylüyor.
            assert page.input_value("#prompt") == "dusecek"
            assert "500" in page.inner_text("#status")

            monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(0.1))
            page.click(PANEL_SATIR + " .is-yeniden")
            page.wait_for_function(f'document.querySelectorAll("{PANEL_SATIR}").length === 2')
            assert page.inner_text("#isler-durum").strip() == "The job is back in the queue."
            page.wait_for_selector(PANEL_SATIR + '[data-durum="bitti"]', timeout=15000)
            durumlar = _durumlar(oturum)
            assert sorted(durumlar) == ["bitti", "hata"], durumlar
            with oturum.db() as db:
                satirlar = list(db.scalars(
                    select(tablolar.Is).where(tablolar.Is.kullanici_id == oturum.kullanici_id)))
            assert satirlar[0].istek["prompt"] == satirlar[1].istek["prompt"] == "dusecek"
            browser.close()
    finally:
        server.stop()


def test_when_the_stream_is_cut_the_panel_falls_back_to_polling_and_still_finishes(
        monkeypatch, veritabani, e2e_oturum):
    """`/api/isler/akis` tarayıcıda kesilir: `EventSource` üç kez düşer → 3 sn yoklama → iş yine `bitti`."""
    _tum_kimlikler_kayitli(monkeypatch)
    cagrilar: list[str] = []
    monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(0.1, cagrilar))
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    taban = f"http://127.0.0.1:{port}"
    kesilen = threading.Event()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})

            def kes(route):
                kesilen.set()
                route.abort()
            page.route("**/api/isler/akis*", kes)
            _studyo(page, taban, oturum)
            assert kesilen.wait(5.0), "panel akışa hiç bağlanmayı denemedi"
            # Üç düşüş (tarayıcının yeniden bağlanma aralığıyla) → yedek yol mesajı.
            page.wait_for_function(
                'document.querySelector("#isler-durum").textContent.includes("refreshes every 3 seconds")',
                timeout=30000)

            _gonder(page, "yoklamayla")
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="bitti"]', timeout=15000)
            assert cagrilar == ["yoklamayla"]
            assert page.eval_on_selector("#isler-sayac", "e => e.hidden") is True
            browser.close()
    finally:
        server.stop()


@posix_gerekir(
    "`time.tzset` Windows'ta YOK: sunucunun dilimi `TZ=UTC` ile "
    "sabitlenemiyor, testin kurduğu 3 saatlik fark hiç oluşmuyor")
def test_the_elapsed_counter_starts_near_zero_in_a_browser_three_hours_east_of_the_server(
        monkeypatch, veritabani, e2e_oturum):
    """"180" kusuru (docs/studyo-guncelleme-plani.md B3; Faz 2 / 10): sunucu UTC, tarayıcı UTC+3.

    Eski yük dilimsiz `zaman.damga` dizesiydi; tarayıcı onu kendi yerel saati okuyor, `basladi`
    3 saat geriye kayıyor ve panel `sureMetni`yle "180:00" açılıyordu. Sunucunun dilimi burada
    `TZ=UTC` + `tzset` ile üretimdeki gibi sabitlenir (`zaman.an()` `astimezone()` yerel dilimi
    C kütüphanesinden okur), tarayıcı bağlamı `timezone_id="Europe/Istanbul"`. İddia: `calisiyor`
    satırın `.is-sure` metni "N s(n)" ve N < 60 — `dk:ss` biçimi (saat farkı) hiç görünmez.
    """
    eski_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    _tum_kimlikler_kayitli(monkeypatch)
    monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(6.0))
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    sunucu_hazir(port)
    taban = f"http://127.0.0.1:{port}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            baglam = browser.new_context(viewport={"width": 1280, "height": 860},
                                         timezone_id="Europe/Istanbul")
            page = baglam.new_page()
            assert page.evaluate("new Date().getTimezoneOffset()") == -180, "tarayıcı UTC+3 değil"
            _studyo(page, taban, oturum)
            _gonder(page, "saat dilimi")
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="calisiyor"]', timeout=15000)
            # Sayaç saniyede bir tazelenir; iki okuma da saniye biçiminde ve küçük olmalı.
            okumalar = []
            for _ in range(2):
                okumalar.append(page.eval_on_selector(PANEL_SATIR + " .is-sure", "e => e.textContent"))
                time.sleep(1.1)
            for metin in okumalar:
                e = re.fullmatch(r"(\d+) sn?", metin)
                assert e, f"sayaç saniye biçiminde değil (saat dilimi farkı?): {metin!r}"
                assert int(e.group(1)) < 60, f"sayaç dakikalarla açıldı: {metin!r}"
            # Yük gerçekten dilimli UTC: panelin okuduğu `basladi` `Z` ile bitiyor.
            basladi = page.evaluate(
                "async () => (await (await fetch('/api/isler')).json()).isler[0].basladi")
            assert basladi and basladi.endswith("Z"), basladi
            _paneldekiler_bitsin(page, oturum, 1)
            son = page.eval_on_selector(PANEL_SATIR + " .is-sure", "e => e.textContent")
            e = re.fullmatch(r"(\d+) sn?", son)
            assert e and 4 <= int(e.group(1)) <= 20, f"biten işin süresi sağlayıcının 6 sn'sine yakın olmalı: {son!r}"
            browser.close()
    finally:
        server.stop()
        if eski_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = eski_tz
        time.tzset()


def test_a_failed_platform_job_gives_the_credits_back_and_a_finished_one_shows_the_real_cost(
        monkeypatch, veritabani, e2e_oturum):
    """Faz 3 / 2 çıkış ölçütü: sağlayıcı hatası → bakiye eski değer; yeniden gönderim biter →
    panelde "~tahmin → gerçek", bakiye gerçek kadar düşük. Platform anahtarı: kapı yaması `platform` der."""
    _tum_kimlikler_kayitli(monkeypatch)
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "platform")

    def bozuk(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "generate", bozuk)
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    with oturum.db() as db:
        defter.hibe(db, oturum.kullanici_id, 100, f"{defter.ONEK_HIBE}{oturum.kullanici_id}:2026-09")
        db.commit()
    time.sleep(1.0)
    taban = f"http://127.0.0.1:{port}"

    def bakiye() -> int:
        with oturum.db() as db:
            return defter.bakiye(db, oturum.kullanici_id)

    def defter_turleri() -> list[str]:
        with oturum.db() as db:
            return [h.tur for h in defter.hareketler(db, oturum.kullanici_id)[::-1]]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _gonder(page, "dusecek")
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="hata"]', timeout=15000)
            assert page.eval_on_selector(PANEL_SATIR, "e => e.dataset.durum") == "hata"
            # Rota tahmini düştü, işçi hatada iade etti: bakiye eski değerinde, defter rezerv + iade.
            assert bakiye() == 100, defter_turleri()
            assert defter_turleri() == ["hibe", "rezerv", "iade"]
            tahmin = page.eval_on_selector(PANEL_SATIR + " .is-kredi", "e => e.textContent")
            assert "→" not in tahmin and "8" in tahmin, tahmin

            monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(0.1))
            page.click(PANEL_SATIR + " .is-yeniden")
            page.wait_for_selector(PANEL_SATIR + '[data-durum="bitti"]', timeout=15000)
            biten = page.eval_on_selector(PANEL_SATIR + '[data-durum="bitti"] .is-kredi', "e => e.textContent")
            assert biten == "~8 → 8 credits", biten
            assert bakiye() == 100 - 8
            assert defter_turleri() == ["hibe", "rezerv", "iade", "rezerv", "onay"]
            browser.close()
    finally:
        server.stop()
