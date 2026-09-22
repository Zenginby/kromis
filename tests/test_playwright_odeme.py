# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""E2E — ücretsiz kullanıcı `/planlar` → paket → "Polar" → teşekkür → bakiye 200 → 700 (Faz 4 / 4; belge §4 çıkış ölçütü).

SAHTE POLAR, GERÇEK İMZA (belge "Test stratejisi"): `polar.checkout_ac` yamalı ve bu
testin kendi HTTP sunucusuna ("ödeme sayfası", `_YerelPolar`) yönlendiriyor; o sayfadaki
"Öde" düğmesi sunucunun kendisine POST atıyor, sunucu tests/fixtures/polar/order_paid_purchase.json
yükünü kullanıcıya/ürüne göre doldurup `polar.imzala` ile GERÇEK HMAC üretiyor,
uygulamanın `POST /api/odeme/webhook`una teslim ediyor ve tarayıcıyı `success_url`a
(`/odeme/tesekkur?checkout_id=…`) yolluyor — Polar'ın gerçek sırası. `Webhook.verify`
YAMALANMAZ; uygulama sunucusu aynı süreçte (`ServerThread`), sır `monkeypatch.setenv`.

Üç adım tek tarayıcıda: (1) şartlar onaysız → 412 → kutu görünür → onayla → Polar'a;
(2) "Öde" → webhook → teşekkür sayfası "bakiyene işlendi", toplam 700, defterde `paket:`
satırı; (3) plan `temel`e çekilince pro'ya "Abone ol" → 409 → portal düğmesi → yamalı
`portal_baglantisi`nin URL'sine gider.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import select, text

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import i18n
from services import defter, polar, tablolar
from tests.test_odeme import FIXTURES, SIR, URUN_PAKET, URUN_PLAN
from tests.test_playwright_studio import ServerThread, get_free_port, sunucu_hazir

pytestmark = pytest.mark.gercek_kimlik

URUN_PRO = "00000000-0000-4000-8000-00000000e003"


class _YerelPolar(ThreadingHTTPServer):
    """Testin "Polar"ı: `/checkout?...` ödeme sayfası, `/ode` imzalı webhook + 303, `/portal` sabit sayfa."""

    def __init__(self, uygulama_taban: str):
        super().__init__(("127.0.0.1", 0), _Isleyici)
        self.uygulama_taban = uygulama_taban
        self.webhook_cevaplari: list[dict] = []

    @property
    def taban(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _Isleyici(BaseHTTPRequestHandler):
    server: _YerelPolar

    def log_message(self, *_):   # pytest çıktısını kirletmesin
        pass

    def _html(self, govde: str, durum: int = 200, basliklar: dict | None = None) -> None:
        veri = govde.encode()
        self.send_response(durum)
        for k, v in (basliklar or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def do_GET(self) -> None:
        yol = urllib.parse.urlparse(self.path)
        if yol.path == "/checkout":
            self._html('<!doctype html><title>DUMMY Polar</title><h1 id="polar">DUMMY Polar Checkout</h1>'
                       f'<form method="post" action="/ode?{yol.query}"><button id="ode" type="submit">Öde</button></form>')
        elif yol.path == "/portal":
            self._html('<!doctype html><title>DUMMY Portal</title><h1 id="portal">DUMMY Polar Portal</h1>')
        else:
            self._html("yok", 404)

    def do_POST(self) -> None:
        yol = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(yol.query)
        kullanici_id, urun_id, success_url = q["u"][0], q["p"][0], q["s"][0]
        with open(os.path.join(FIXTURES, "order_paid_purchase.json"), encoding="utf-8") as f:
            yuk = json.load(f)
        yuk["data"]["id"] = "00000000-0000-4000-8000-00000000f0e2"
        yuk["data"]["product_id"] = urun_id
        yuk["data"]["customer"]["external_id"] = kullanici_id
        yuk["data"]["checkout_id"] = "00000000-0000-4000-8000-00000000cce2"
        govde = json.dumps(yuk).encode()
        basliklar = polar.imzala(govde, SIR, webhook_id="wh_e2e_odeme")
        istek = urllib.request.Request(self.server.uygulama_taban + "/api/odeme/webhook", data=govde, method="POST",
                                       headers={"Content-Type": "application/json", **basliklar})
        with urllib.request.urlopen(istek, timeout=10) as cevap:
            self.server.webhook_cevaplari.append(json.loads(cevap.read()))
        # Polar `{CHECKOUT_ID}` yer tutucusunu doldurur ve tarayıcıyı `success_url`a gönderir.
        self._html("", 303, {"Location": success_url.replace("{CHECKOUT_ID}", yuk["data"]["checkout_id"])})


def test_a_free_user_accepts_the_terms_buys_a_pack_on_the_fake_polar_and_sees_the_balance_land_then_reaches_the_portal(
        monkeypatch, veritabani, e2e_oturum):
    port = get_free_port()
    server = ServerThread(port)
    taban = f"http://127.0.0.1:{port}"
    yerel = _YerelPolar(taban)
    yerel_is = threading.Thread(target=yerel.serve_forever, daemon=True)
    yerel_is.start()
    monkeypatch.setenv(polar.WEBHOOK_SIRRI_ENV, SIR)

    def _checkout_ac(*, urun_id, external_customer_id, customer_email, success_url, metadata=None):
        assert metadata and metadata["kullanici_id"] == external_customer_id and customer_email
        return f"{yerel.taban}/checkout?" + urllib.parse.urlencode({"u": external_customer_id, "p": urun_id, "s": success_url})

    portal_cagrilari: list[str] = []

    def _portal(musteri_id: str) -> str:
        portal_cagrilari.append(musteri_id)
        return f"{yerel.taban}/portal"

    monkeypatch.setattr(polar, "checkout_ac", _checkout_ac)
    monkeypatch.setattr(polar, "portal_baglantisi", _portal)

    server.start()
    oturum = e2e_oturum(dil="tr")
    with oturum.db() as db:
        db.add_all([
            tablolar.Urun(polar_urun_id=URUN_PAKET, tur="paket", plan=None, kredi=500, fiyat_kurus=500, para_birimi="usd",
                          ad="500 kredi"),
            tablolar.Urun(polar_urun_id=URUN_PLAN, tur="plan", plan="temel", kredi=1_200, fiyat_kurus=900, para_birimi="usd",
                          ad="Temel"),
            tablolar.Urun(polar_urun_id=URUN_PRO, tur="plan", plan="pro", kredi=4_500, fiyat_kurus=2_900, para_birimi="usd",
                          ad="Pro"),
        ])
        # Hibeyi TEST yatırır (200): işçinin bakım turu da yatırabilir ama aynı ay anahtarına çarpar (idempotent).
        assert defter.hibe(db, oturum.kullanici_id, 200, f"{defter.ONEK_HIBE}{oturum.kullanici_id}:e2e-odeme")
        db.commit()

    def bakiye():
        with oturum.db() as db:
            return defter.bakiye(db, oturum.kullanici_id)

    def satir():
        with oturum.db() as db:
            k = db.get(tablolar.Kullanici, oturum.kullanici_id)
            db.expunge(k)
            return k

    sunucu_hazir(port)
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            page = tarayici.new_page()
            oturum.cerez(page, taban)

            # 1. Satış sayfası: üç plan kartı (ücretsiz "mevcut"), paket kartı fiyatıyla.
            page.goto(f"{taban}/planlar")
            page.wait_for_selector("#planlar-paketler .plan-kart")
            assert page.locator("#planlar-planlar .plan-kart").count() == 3
            assert page.locator('#planlar-planlar .plan-kart[data-plan="free"][data-mevcut="true"]').count() == 1
            assert i18n.t("planlar.mevcut_plan", "tr") in page.inner_text('#planlar-planlar .plan-kart[data-plan="free"]')
            assert "500 kredi" in page.inner_text("#planlar-paketler")
            assert page.is_hidden("#planlar-sartlar") and page.is_hidden("#planlar-portal")

            # 1b. Şartlar onaysız → 412 → kutu görünür; işaretle, onayla → Polar'a (yerel) gidilir.
            page.click('#planlar-paketler .plan-kart button')
            page.wait_for_selector("#planlar-sartlar:not([hidden])")
            assert page.inner_text("#planlar-mesaj") == i18n.t("err.sartlar_gerekli", "tr")
            assert page.is_disabled("#planlar-sartlar-onayla")
            page.check("#planlar-sartlar-kutu")
            page.click("#planlar-sartlar-onayla")
            page.wait_for_selector("#polar")
            assert page.url.startswith(f"{yerel.taban}/checkout?")
            k = satir()
            assert k.sartlar_kabul_at is not None and k.sartlar_surumu, "onay checkout'tan önce yazıldı"
            assert bakiye().toplam == 200

            # 2. "Öde" → yerel Polar imzalı `order.paid` teslim eder → teşekkür sayfası yoklar → 700.
            page.click("#ode")
            page.wait_for_url(f"{taban}/odeme/tesekkur?checkout_id=*")
            page.wait_for_selector('#tesekkur-mesaj[data-durum="islendi"]', timeout=15_000)
            assert page.inner_text("#tesekkur-toplam") == "700"
            assert page.inner_text("#tesekkur-mesaj") == i18n.t("tesekkur.islendi", "tr", toplam=700)
            assert yerel.webhook_cevaplari == [{"durum": "islendi"}]
            b = bakiye()
            assert (b.hibe, b.paket, b.toplam) == (200, 500, 700)
            with oturum.db() as db:
                turler = list(db.scalars(select(tablolar.KrediHareketi.tur)
                                         .where(tablolar.KrediHareketi.kullanici_id == oturum.kullanici_id)
                                         .order_by(tablolar.KrediHareketi.olusturuldu)))
                assert turler == ["hibe", "paket"]
                assert db.scalar(select(tablolar.Siparis.tutar_kurus)
                                 .where(tablolar.Siparis.kullanici_id == oturum.kullanici_id)) == 500
            assert satir().polar_musteri_id, "`order.paid` müşteri kimliğini bağladı — portal artık açık"

            # 3. Ücretli planda plan ürünü → 409 → portal düğmesi → yamalı portal URL'sine gider.
            with oturum.db() as db:
                db.execute(text("UPDATE kullanicilar SET plan = 'temel' WHERE id = :id"), {"id": oturum.kullanici_id})
                db.commit()
            page.goto(f"{taban}/planlar")
            page.wait_for_selector('#planlar-planlar .plan-kart[data-plan="temel"][data-mevcut="true"]')
            page.click('#planlar-planlar .plan-kart[data-plan="pro"] button')
            page.wait_for_selector("#planlar-portal:not([hidden])")
            assert page.inner_text("#planlar-mesaj") == i18n.t("err.abonelik_var", "tr", plan="temel")
            page.click("#planlar-portal-dugme")
            page.wait_for_selector("#portal")
            assert page.url == f"{yerel.taban}/portal"
            assert portal_cagrilari == [satir().polar_musteri_id]
            tarayici.close()
    finally:
        yerel.shutdown()
        yerel.server_close()
        server.stop()
