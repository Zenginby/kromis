"""E2E — tarayıcıdan kayıt → e-posta bağlantısı → giriş → stüdyo → çıkış (Faz 1 / 3).

Belgenin çıkış ölçütü (§3): "tarayıcıdan kayıt → e-posta → giriş → çıkış".
Sunucu aynı süreçte (`test_playwright_studio.ServerThread` deseni), veri
tabanı `veritabani` fixture'ının kopyası, posta arka ucu konsol — doğrulama
bağlantısı `app.state.postaci.son`dan okunup tarayıcıya verilir. İki dilde
koşuyor: sayfa sunucuda çevriliyor (`{{t:…}}`) ve dil çerezi zincirin başında;
metin çapaları `i18n.t` ile okunuyor, kopyalanmıyor (conftest.tr gerekçesi).

Çerez `Secure` (web modu, services/cerez.py) ve sayfa `http://127.0.0.1`:
Chromium loopback'i güvenilir köken sayar ve Secure çerezi düz HTTP'de de
saklar — yani bu test bayrağı GEVŞETMEDEN gerçek dağıtım hâlini ölçüyor.
"""
from __future__ import annotations

import re
import socket
import threading
import time
from urllib.parse import quote

import pytest
import uvicorn
from sqlalchemy import create_engine, text

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import i18n
from app import app
from services import cerez, koken, posta
from tests.conftest import KAPANIS_TAVANI_SN

# Kapı GERÇEK: bu dosya kapının kendisini (form → çerez → stüdyo → çıkış → 401)
# ölçüyor; conftest'in autouse override'ı burada kurulmaz (Faz 1 / 4).
pytestmark = pytest.mark.gercek_kimlik

EPOSTA = "e2e@example.com"
PAROLA = "e2e-parolasi-123"


def _bos_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Sunucu(threading.Thread):
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.server = uvicorn.Server(
            uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning",
                           timeout_graceful_shutdown=KAPANIS_TAVANI_SN))

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def _bekle(port: int) -> None:
    """Sabit uyku değil yoklama: yavaş makinede 1 sn yetmez, hızlısında fazla."""
    for _ in range(100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("sunucu açılmadı")


def _baglanti(parametre: str) -> str:
    son = app.state.postaci.son
    assert son is not None, "konsol postacıya ileti düşmedi"
    m = re.search(rf"https?://[^\s]+/giris\?{parametre}=[A-Za-z0-9_-]+", son.metin)
    assert m, son.metin
    return m.group(0)


@pytest.mark.parametrize("dil", i18n.LANGUAGES)
def test_register_verify_login_and_logout_through_the_browser(
        dil, veritabani, monkeypatch, tmp_path, dizinler):
    for ad in (posta.POSTA_ENV, posta.RESEND_ANAHTAR_ENV, koken.KOKEN_ENV, cerez.GUVENLI_ENV):
        monkeypatch.delenv(ad, raising=False)
    dizinler(data_dir=str(tmp_path))
    # Aynı dosyanın iki parametresi aynı DB'yi paylaşıyor (`veritabani_url` modül
    # kapsamlı); ikinci dil ilk dilin hesabını bulmasın.
    motor = create_engine(veritabani)
    with motor.begin() as c:
        c.execute(text("TRUNCATE kullanicilar CASCADE"))
        c.execute(text("TRUNCATE giris_denemeleri"))
    motor.dispose()
    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    _bekle(port)
    taban = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            baglam = tarayici.new_context()
            # Dil zincirinin başı: çerez. Sunucu sayfayı bu dille çizer.
            baglam.add_cookies([{"name": "kromis_lang", "value": dil, "url": taban}])
            page = baglam.new_page()

            # 1. Sayfa doğru dilde ve stüdyo betikleri olmadan açılıyor.
            page.goto(f"{taban}/giris")
            page.wait_for_selector("#form-giris:not([hidden])")
            assert page.get_attribute("html", "lang") == dil
            assert page.inner_text('#giris-sekmeler [data-sekme="kayit"]') == i18n.t("giris.sekme_kayit", dil)
            assert page.query_selector("#view-studio") is None

            # 2. Kayıt formu → "bağlantı gönderildi" mesajı, giriş sekmesine dönüş.
            page.click('#giris-sekmeler [data-sekme="kayit"]')
            page.fill("#kayit-eposta", EPOSTA)
            page.fill("#kayit-parola", PAROLA)
            page.click("#form-kayit button[type=submit]")
            page.wait_for_function(
                '() => { const m = document.querySelector("#giris-mesaj");'
                ' return !m.hidden && m.dataset.tur !== "bilgi"; }')
            assert page.inner_text("#giris-mesaj") == i18n.t("giris.kayit_gonderildi", dil)
            assert not page.is_hidden("#form-giris")
            ileti = app.state.postaci.son
            assert ileti is not None and ileti.kime == EPOSTA
            assert ileti.konu == i18n.t("posta.dogrulama_konu", dil), "ileti sayfanın dilinde"

            # 3. E-postadaki bağlantı → otomatik doğrulama, jeton adres çubuğundan silinir.
            page.goto(_baglanti("dogrula"))
            page.wait_for_function(
                '() => { const m = document.querySelector("#giris-mesaj");'
                ' return !m.hidden && m.dataset.tur === "basari"; }')
            assert page.inner_text("#giris-mesaj") == i18n.t("giris.dogrulandi", dil)
            assert "dogrula=" not in page.url, "jeton geçmişte/Referer'da kalmamalı"

            # 4. Giriş → stüdyo açılır; SAYFANIN İÇİNDEN `fetch` çerezi taşır.
            # (`page.request` DEĞİL: Playwright'ın kendi istek katmanı `Secure`
            # çerezi düz HTTP'ye göndermez — tarayıcı ise loopback'i güvenilir
            # sayar. Ölçülen şey tarayıcının davranışı, o yüzden `evaluate`.)
            page.fill("#giris-eposta", EPOSTA)
            page.fill("#giris-parola", PAROLA)
            page.click("#form-giris button[type=submit]")
            page.wait_for_url(f"{taban}/")
            page.wait_for_selector("#view-studio")
            ben = page.evaluate("() => fetch('/api/hesap/ben').then((r) => r.json())")
            assert ben.get("eposta") == EPOSTA, ben
            cerezler = {c["name"]: c for c in baglam.cookies()}
            oturum = cerezler[cerez.OTURUM_CEREZI]
            assert oturum["httpOnly"] and oturum["secure"] and oturum["sameSite"] == "Lax"

            # 5. Oturum açıkken /giris stüdyoya döner.
            page.goto(f"{taban}/giris")
            page.wait_for_url(f"{taban}/")

            # 6. Ayarlar → Hakkında → "Çıkış yap" (settings.js'in dinamik satırı) → /giris, ben 401.
            page.wait_for_function(
                '() => { const m = document.querySelector("#model");'
                ' return (m && m.value !== "") || !!document.querySelector(".sheet.open"); }')
            if not page.query_selector(".sheet.open"):
                page.click("#settings-btn")
            page.wait_for_selector("#settings-modal.open")
            page.click('#settings-nav [data-pane="about"]')
            page.wait_for_selector("#settings-cikis")
            assert page.inner_text("#settings-hesap").startswith(
                i18n.t("hesap.oturum_acik", dil, eposta=EPOSTA))
            page.click("#settings-cikis")
            page.wait_for_url(f"{taban}/giris")
            page.wait_for_selector("#form-giris:not([hidden])")
            assert page.evaluate("() => fetch('/api/hesap/ben').then((r) => r.status)") == 401
            assert cerez.OTURUM_CEREZI not in {c["name"] for c in baglam.cookies()}
            tarayici.close()
    finally:
        sunucu.stop()
        sunucu.join(timeout=5)


def _dogrulanmis_hesap(veritabani_url: str) -> None:
    """DB'ye doğrudan doğrulanmış hesap: bu test formun kayıt akışını değil `?sonra=` kapısını ölçüyor."""
    from sqlalchemy.orm import Session

    from services import hesap
    from services.tablolar import Kullanici

    motor = create_engine(veritabani_url)
    with Session(motor) as db:
        db.execute(text("TRUNCATE kullanicilar CASCADE"))
        db.execute(text("TRUNCATE giris_denemeleri"))
        db.add(Kullanici(eposta=EPOSTA, parola_ozeti=hesap.parola_ozeti(PAROLA),
                         dogrulandi_at=hesap.simdi()))
        db.commit()
    motor.dispose()


@pytest.mark.parametrize("dil", i18n.LANGUAGES)
def test_deleting_the_account_from_settings_lands_on_the_login_page_and_the_old_email_no_longer_signs_in(
        dil, veritabani, monkeypatch, tmp_path, dizinler):
    """Faz 4 / 5 (belge §5 E2E): Ayarlar → Hesap → parola + onay metni → `/giris`; aynı e-posta ile giriş
    bilinmeyen adresle AYNI 401 cümlesini alır (numaralandırmaya karşı — routers/hesap.py). Onay metni
    dile göre (`hesap.sil_onay_metni`: SİL / DELETE), çerez düşer, ileti konsol postacıya ASIL adrese gider."""
    for ad in (posta.POSTA_ENV, posta.RESEND_ANAHTAR_ENV, koken.KOKEN_ENV, cerez.GUVENLI_ENV):
        monkeypatch.delenv(ad, raising=False)
    dizinler(data_dir=str(tmp_path))
    _dogrulanmis_hesap(veritabani)
    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    _bekle(port)
    taban = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            baglam = tarayici.new_context()
            baglam.add_cookies([{"name": "kromis_lang", "value": dil, "url": taban}])
            page = baglam.new_page()
            page.goto(f"{taban}/giris")
            page.wait_for_selector("#form-giris:not([hidden])")
            page.fill("#giris-eposta", EPOSTA)
            page.fill("#giris-parola", PAROLA)
            page.click("#form-giris button[type=submit]")
            page.wait_for_url(f"{taban}/")
            page.wait_for_selector("#view-studio")
            page.wait_for_function(
                '() => { const m = document.querySelector("#model");'
                ' return (m && m.value !== "") || !!document.querySelector(".sheet.open"); }')
            if not page.query_selector(".sheet.open"):
                page.click("#settings-btn")
            page.wait_for_selector("#settings-modal.open")
            page.click('#settings-nav [data-pane="hesap"]')
            page.wait_for_selector("#hesap-sil-dugme")
            assert page.inner_text("#hesap-sil-dugme") == i18n.t("hesap.sil_dugme", dil)
            # Yanlış onay metni sunucuya GİTMEZ: cümle yerel, hesap durur.
            page.fill("#hesap-sil-parola", PAROLA)
            page.fill("#hesap-sil-onay", "hayir")
            page.click("#hesap-sil-dugme")
            page.wait_for_function(
                '() => document.querySelector("#hesap-sil-durum").textContent !== ""')
            assert page.inner_text("#hesap-sil-durum") == i18n.t("hesap.sil_onay_uyusmuyor", dil)
            assert page.url == f"{taban}/"
            page.fill("#hesap-sil-onay", i18n.t("hesap.sil_onay_metni", dil))
            page.click("#hesap-sil-dugme")
            page.wait_for_url(f"{taban}/giris")
            page.wait_for_selector("#form-giris:not([hidden])")
            assert cerez.OTURUM_CEREZI not in {c["name"] for c in baglam.cookies()}
            ileti = app.state.postaci.son
            assert ileti is not None and ileti.kime == EPOSTA and ileti.konu == i18n.t("posta.silme_konu", dil)
            # Aynı adresle giriş: "hesap yok" — bilinmeyen adresin 401'iyle aynı cümle.
            page.fill("#giris-eposta", EPOSTA)
            page.fill("#giris-parola", PAROLA)
            page.click("#form-giris button[type=submit]")
            page.wait_for_function(
                '() => { const m = document.querySelector("#giris-mesaj");'
                ' return !m.hidden && m.dataset.tur === "hata"; }')
            assert page.inner_text("#giris-mesaj") == i18n.t("err.hesap_giris_hatali", dil)
            assert page.url.startswith(f"{taban}/giris")
            tarayici.close()
    finally:
        sunucu.stop()
        sunucu.join(timeout=5)
    motor = create_engine(veritabani)
    with motor.connect() as c:
        eposta, silindi, oturum = c.execute(text(
            "SELECT k.eposta, k.silindi_at, (SELECT count(*) FROM oturumlar o WHERE o.kullanici_id = k.id) "
            "FROM kullanicilar k")).one()
    motor.dispose()
    assert eposta.startswith("silindi-") and eposta.endswith("@anonim.invalid") and silindi is not None
    assert oturum == 0, "oturum satırı gitti — çerez ölü"


@pytest.mark.parametrize("sonra, beklenen", [
    ("/?sekme=galeri", "/?sekme=galeri"),          # aynı kökene ait yol: aynen
    ("//evil.example/", "/"),                       # şemasız dış adres: /
    ("https://evil.example/", "/"),                 # şemalı dış adres: /
    ("/\\evil.example/", "/"),                    # ters bölü — tarayıcı `//` okur: /
    ("/\t/evil.example/", "/"),                    # sekme — WHATWG soyar, `//evil.example` olur: / (inceleme 2026-09-22)
    ("/\n/evil.example/?x=1", "/"),                # satır sonu — aynı soyma: /
    ("/?sekme=paket#kart", "/?sekme=paket"),       # yol + sorgu aynen, parça düşer (`URL` ayrıştırıcısı)
    ("galeri", "/"),                                # göreli: /
])
def test_after_login_the_page_returns_only_to_a_same_origin_path(
        sonra, beklenen, veritabani, monkeypatch, tmp_path, dizinler):
    """`/giris?sonra=` (core.js 401 sarmalı yazar) — açık yönlendirici DEĞİL (static/giris.js `hedef`).

    Kapının kendisi JavaScript'te; sunucuya bakan hiçbir test onu göremez,
    yalnız tarayıcıda ölçülür. Dış adresler için iddia "sayfa BİZDE kaldı":
    `page.url` `taban + "/"`; `evil.example` çözülmez, gerçekten oraya gitseydi
    `wait_for_url` düşerdi.
    """
    for ad in (posta.POSTA_ENV, posta.RESEND_ANAHTAR_ENV, koken.KOKEN_ENV, cerez.GUVENLI_ENV):
        monkeypatch.delenv(ad, raising=False)
    dizinler(data_dir=str(tmp_path))
    _dogrulanmis_hesap(veritabani)
    port = _bos_port()
    sunucu = _Sunucu(port)
    sunucu.start()
    _bekle(port)
    taban = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            page = tarayici.new_page()
            page.goto(f"{taban}/giris?sonra=" + quote(sonra, safe=""))
            page.wait_for_selector("#form-giris:not([hidden])")
            page.fill("#giris-eposta", EPOSTA)
            page.fill("#giris-parola", PAROLA)
            page.click("#form-giris button[type=submit]")
            page.wait_for_url(f"{taban}{beklenen}")
            page.wait_for_selector("#view-studio")
            assert page.url == f"{taban}{beklenen}"

            # Oturum düşerse stüdyo `/giris?sonra=<bulunduğu yol>`e gider (core.js sarmalı):
            # çerezi tarayıcıdan silip bir API çağrısı yaptırıyoruz.
            page.context.clear_cookies(name=cerez.OTURUM_CEREZI)
            page.evaluate("() => fetch('/api/history')")
            page.wait_for_url(f"{taban}/giris?sonra=*")
            assert page.url == f"{taban}/giris?sonra=" + quote(beklenen, safe="")
            tarayici.close()
    finally:
        sunucu.stop()
        sunucu.join(timeout=5)
