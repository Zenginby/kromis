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

import pytest
import uvicorn
from sqlalchemy import create_engine, text

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import i18n
from app import app
from services import cerez, koken, posta

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
            uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning"))

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
