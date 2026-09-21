"""Kredi ön yüzü E2E — Faz 3 / 6'nın ÇIKIŞ ÖLÇÜTÜ (docs/faz3-kredi-defteri-filigran.md §6).

İki senaryo, ikisi de yalnız tarayıcıda ölçülebilir (composer satırı, SSE →
yenileme, toast, Ayarlar bölmesi — kaynak taraması bunların ZAMANLAMASINI göremez):

  1. ÜCRETSİZ KULLANICI, PLATFORM ANAHTARI: açılışta `#run-cost` "this run takes 8 ·
     200 left" → iş gönderilir → 202 rezerv → "192 left" → sahte sağlayıcı bitirir →
     panelde "reserved 8 · actual 8 · refunded 0", satır yine "192 left" → Ayarlar
     "Kredi": bakiye 192, hareketler onay/rezerv/hibe (en yeni üstte), "show job"
     paneldeki satırı vurgular.
  2. SAHTE HATA → İADE, SONRA 402: sağlayıcı düşer → panelde `hata`, "reserved 8 ·
     fully refunded", satır "200 left"e GERİ gelir. Bakiye 4'e düşürülür (admin
     düzeltmesi), gönderim 402 → toast (cümle + "See credits") → tıklanır → Ayarlar
     "Kredi" bölmesi açık, bakiye 4; `#run-cost` "4 left" ve uyarı rengi, #go AÇIK.

Sunucu + işçi `tests/test_playwright_studio.py`nin `ServerThread`i; anahtar kapısı
`platform` der (tests/test_playwright_isler.py 6. senaryonun deseni), sağlayıcı yamalı.
Sayfa dili İngilizce (öntanımlı, `services/dil.py`).
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import azure_client as ac
import providers
from services import defter, kapilar, zaman
from tests.test_playwright_isler import (
    PANEL_SATIR,
    _gonder,
    _paneli_ac,
    _studyo,
    _uyuyan_saglayici,
)
from tests.test_playwright_studio import (
    ServerThread,
    _tum_kimlikler_kayitli,
    get_free_port,
    sunucu_hazir,
)

pytestmark = pytest.mark.gercek_kimlik

RUN_COST = "#run-cost"


def _kalan_bekle(page, kalan: int) -> None:
    page.wait_for_function(
        f'!document.querySelector("{RUN_COST}").hidden && '
        f'document.querySelector("{RUN_COST}").textContent.includes("· {kalan} left")',
        timeout=15000)


def _hazirla(monkeypatch, e2e_oturum, hibe: int):
    _tum_kimlikler_kayitli(monkeypatch)
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "platform")
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    oturum = e2e_oturum()
    with oturum.db() as db:
        defter.aylik_hibe_yaz(db, oturum.kullanici_id, hibe, zaman.an())
        db.commit()
    sunucu_hazir(port)
    return server, oturum, f"http://127.0.0.1:{port}"


def _bakiye(oturum) -> int:
    with oturum.db() as db:
        return defter.bakiye(db, oturum.kullanici_id).toplam


def test_the_composer_line_follows_the_ledger_and_the_settings_pane_shows_the_movements(
        monkeypatch, veritabani, e2e_oturum):
    monkeypatch.setattr(providers, "generate", _uyuyan_saglayici(0.3))
    server, oturum, taban = _hazirla(monkeypatch, e2e_oturum, 200)
    t0 = time.perf_counter()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _kalan_bekle(page, 200)
            satir = page.inner_text(RUN_COST)
            assert satir == "this run takes 8 · 200 left", satir
            assert not page.eval_on_selector(RUN_COST, 'e => e.classList.contains("run-cost-uyari")')

            _gonder(page, "kedi")
            _kalan_bekle(page, 192)  # 202: rezerv düştü, panel `krediYenile` çağırdı
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="bitti"]', timeout=15000)
            biten = page.eval_on_selector(PANEL_SATIR + " .is-kredi", "e => e.textContent")
            assert biten == "reserved 8 · actual 8 · refunded 0", biten
            assert _bakiye(oturum) == 192
            _kalan_bekle(page, 192)  # onay = tahmin, fark iadesi 0: sayı yerinde

            # Ayarlar "Kredi": tek istek (`/api/kredi`), bakiye + hareketler + iş bağlantısı.
            page.keyboard.press("Escape")
            page.click("#settings-btn")
            page.wait_for_selector("#settings-modal.open")
            page.click('#settings-nav .picker-nav-item[data-pane="kredi"]')
            page.wait_for_function('document.querySelector("#settings-kredi-bakiye")?.textContent === "192"')
            assert not page.eval_on_selector('.settings-pane[data-pane="kredi"]', "e => e.hidden")
            turler = page.eval_on_selector_all("#settings-kredi-hareketler li", "els => els.map(e => e.dataset.tur)")
            assert turler == ["onay", "rezerv", "hibe"], turler
            miktarlar = page.eval_on_selector_all("#settings-kredi-hareketler .kredi-miktar", "els => els.map(e => e.textContent)")
            assert miktarlar == ["+0", "−8", "+200"], miktarlar
            assert page.inner_text('.settings-pane[data-pane="kredi"] .kredi-plan') == "Plan: Free"
            assert "Monthly grant: 200 credits · next on" in page.inner_text('.settings-pane[data-pane="kredi"] .kredi-hibe')
            assert "watermarked (free plan)" in page.inner_text('.settings-pane[data-pane="kredi"]')
            # "show job" yalnız işi olan satırlarda (hibe satırında yok) → panel açılır, satır vurgulanır.
            assert page.eval_on_selector_all("#settings-kredi-hareketler .kredi-is", "els => els.length") == 2
            page.click('#settings-kredi-hareketler li[data-tur="rezerv"] .kredi-is')
            page.wait_for_selector("#isler-sheet.open")
            page.wait_for_selector(PANEL_SATIR + ".is-vurgu")
            assert not page.eval_on_selector("#settings-modal", 'e => e.classList.contains("open")')
            browser.close()
    finally:
        server.stop()
    print(f"\nE2E kredi (1) composer + Ayarlar: {time.perf_counter() - t0:.1f} sn")


def test_a_failed_job_brings_the_balance_back_and_an_empty_wallet_gets_a_toast_to_the_credit_pane(
        monkeypatch, veritabani, e2e_oturum):
    def bozuk(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "generate", bozuk)
    server, oturum, taban = _hazirla(monkeypatch, e2e_oturum, 200)
    t0 = time.perf_counter()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 860})
            _studyo(page, taban, oturum)
            _kalan_bekle(page, 200)
            _gonder(page, "dusecek")
            _paneli_ac(page)
            page.wait_for_selector(PANEL_SATIR + '[data-durum="hata"]', timeout=15000)
            # İşçi iadeyi yazdı (`defter.iade`), panel kapanışta bakiyeyi yeniledi: sayı GERİ geldi.
            _kalan_bekle(page, 200)
            assert _bakiye(oturum) == 200
            satir = page.eval_on_selector(PANEL_SATIR + " .is-kredi", "e => e.textContent")
            assert satir == "reserved 8 · fully refunded", satir
            page.keyboard.press("Escape")

            # Bakiye 4'e: admin düzeltmesi (kapı yok, iz var). Sayfa hâlâ "200 left" der — 402
            # sunucunun kararı, istemci yalnız gösterir; toast onu bakiyesine götürür.
            with oturum.db() as db:
                defter.duzelt(db, oturum.kullanici_id, -196, "e2e: cüzdanı boşalt", oturum.kullanici_id)
                db.commit()
            assert _bakiye(oturum) == 4
            page.fill("#prompt", "yetmez")
            page.click("#go")
            toast = page.wait_for_selector("#kredi-toast:not([hidden])", timeout=15000)
            metin = toast.inner_text()
            assert "Your balance is 4 credits" in metin and "~8" in metin, metin
            assert "Your balance is 4 credits" in page.inner_text("#status"), "durum satırı da cümleyi yazar"
            # Toast'ın ardından bakiye yenilendi: satır "4 left" ve uyarı rengi, düğme AÇIK.
            _kalan_bekle(page, 4)
            assert page.eval_on_selector(RUN_COST, 'e => e.classList.contains("run-cost-uyari")')
            # #go KAPANMAZ (402 tek doğruluk kaynağı): tıklamanın 1 sn soğuması (`goSogut`) geçince
            # düğme serbest — bakiye kapısı olsaydı bu bekleme zaman aşımına düşerdi.
            page.wait_for_function('!document.querySelector("#go").disabled', timeout=5000)
            page.click("#kredi-toast .kredi-toast-baglanti")
            page.wait_for_selector("#settings-modal.open")
            assert not page.eval_on_selector('.settings-pane[data-pane="kredi"]', "e => e.hidden")
            page.wait_for_function('document.querySelector("#settings-kredi-bakiye")?.textContent === "4"')
            assert page.eval_on_selector("#kredi-toast", "e => e.hidden") is True
            turler = page.eval_on_selector_all("#settings-kredi-hareketler li", "els => els.map(e => e.dataset.tur)")
            assert turler == ["duzeltme", "iade", "rezerv", "hibe"], turler
            # İş doğmadı: panelde hâlâ tek satır (402 `check_bakiye` ön denetimi, iş yazılmadan).
            assert page.eval_on_selector_all(PANEL_SATIR, "els => els.length") == 1
            browser.close()
    finally:
        server.stop()
    print(f"\nE2E kredi (2) iade + 402 toast: {time.perf_counter() - t0:.1f} sn")
