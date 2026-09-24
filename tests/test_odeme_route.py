# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Checkout, portal, ürün listesi ve satış yüzü (Faz 4 / 4; docs/faz4-odeme-abonelik-kvkk.md §4, K5/K7).

Sahte Polar: `polar.checkout_ac` / `polar.portal_baglantisi` yamalı (SDK'ya giden
ALANLAR kaydedilir — `external_customer_id` = kullanıcı id'si belge §4'ün ilk
iddiası); tablolar gerçek Postgres (`depo_db`), kullanıcı conftest'in test
kullanıcısı (DB satırı). Sorular:
  (i)   ÜRÜNLER — oturumsuz uç yalnız aktifleri, kararlı sırada, Polar kimliği olmadan; plan kuralları yanında.
  (ii)  CHECKOUT — Polar'a giden alanlar (products, external_customer_id, e-posta, metadata, success_url
        `{CHECKOUT_ID}` ile, köken `KROMIS_KOKEN` ya da isteğin); 404 bilinmeyen/arşivlenmiş; 412 şartlar
        onaysız + onayla sütunlar yazılır; 409 ücretli planda plan ürünü (`portal: true`), paket serbest;
        502 Polar düşerse + ERROR satırı; 422 bozuk gövde.
  (iii) PORTAL — `polar_musteri_id` yok → 404 `err.musteri_yok`; var → Polar kimliğiyle URL.
  (iv)  /api/kredi `siparisler` — son 10, en yeni üstte, ürün adıyla.
  (v)   SAYFALAR — `/planlar`, `/odeme/tesekkur` çevrili, yalnız sözlük + kendi betiği; id bağları.
  (vi)  ADMİN — özet `urunler_bayat` (boş / 7 günden eski / taze) + WARNING satırı; "paket kredisi ekle".
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import i18n
from services import defter, depo_admin, gunluk, hukuk, koken, odeme, planlar, polar
from services.tablolar import KrediHareketi, Kullanici, Siparis, Urun

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
POLAR_PAKET = "00000000-0000-4000-8000-00000000e001"
POLAR_TEMEL = "00000000-0000-4000-8000-00000000e002"
POLAR_PRO = "00000000-0000-4000-8000-00000000e003"
POLAR_ARSIV = "00000000-0000-4000-8000-00000000e004"
POLAR_BUYUK_PAKET = "00000000-0000-4000-8000-00000000e005"


@pytest.fixture(autouse=True)
def temiz(depo_db, monkeypatch):
    monkeypatch.delenv(koken.KOKEN_ENV, raising=False)
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM siparisler"))
        c.execute(text("DELETE FROM urunler"))
    yield


@pytest.fixture
def c(dizinler) -> TestClient:
    dizinler()
    return TestClient(appmod.app)


@pytest.fixture
def urunler(depo_db) -> dict[str, Urun]:
    """Ayna: 500 ve 1.600 kredilik paketler, `temel`/`pro` planları, bir de ARŞİVLENMİŞ paket (satışta değil)."""
    with Session(depo_db, expire_on_commit=False) as s:
        satirlar = {
            "paket": Urun(polar_urun_id=POLAR_PAKET, tur="paket", plan=None, kredi=500, fiyat_kurus=500,
                          para_birimi="usd", ad="500 kredi"),
            "buyuk": Urun(polar_urun_id=POLAR_BUYUK_PAKET, tur="paket", plan=None, kredi=1_600, fiyat_kurus=1_400,
                          para_birimi="usd", ad="1600 kredi"),
            "pro": Urun(polar_urun_id=POLAR_PRO, tur="plan", plan="pro", kredi=4_500, fiyat_kurus=2_900,
                        para_birimi="usd", ad="Pro"),
            "temel": Urun(polar_urun_id=POLAR_TEMEL, tur="plan", plan="temel", kredi=1_200, fiyat_kurus=900,
                          para_birimi="usd", ad="Temel"),
            "arsiv": Urun(polar_urun_id=POLAR_ARSIV, tur="paket", plan=None, kredi=100, fiyat_kurus=100,
                          para_birimi="usd", ad="Eski paket", aktif=False),
        }
        s.add_all(satirlar.values())
        s.commit()
        return satirlar


class _Kayit:
    """Yamalı `polar.checkout_ac` / `portal_baglantisi`: çağrı argümanlarını saklar, sabit URL döner ya da fırlatır."""

    def __init__(self, url: str = "https://sandbox.polar.sh/checkout/DUMMY", hata: Exception | None = None):
        self.url, self.hata = url, hata
        self.cagrilar: list[Any] = []

    def checkout(self, **kw):
        self.cagrilar.append(kw)
        if self.hata is not None:
            raise self.hata
        return self.url

    def portal(self, musteri_id: str):
        self.cagrilar.append(musteri_id)
        if self.hata is not None:
            raise self.hata
        return self.url


@pytest.fixture
def sahte_polar(monkeypatch) -> _Kayit:
    kayit = _Kayit()
    monkeypatch.setattr(polar, "checkout_ac", kayit.checkout)
    monkeypatch.setattr(polar, "portal_baglantisi", kayit.portal)
    return kayit


class _Yakala(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.kayitlar: list[tuple[int, dict]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.kayitlar.append((record.levelno, gunluk.alanlar(record)))


@pytest.fixture
def gunluk_kaydi() -> Iterator[_Yakala]:
    """`kromis.odeme` (checkout/portal) ve `kromis.admin` (admin sekmesinin `odeme.urunler_bayat` uyarısı) birlikte."""
    yakala = _Yakala()
    loggerlar = [logging.getLogger(ad) for ad in ("kromis.odeme", "kromis.admin")]
    eskiler = [lg.level for lg in loggerlar]
    for lg in loggerlar:
        lg.disabled = False
        lg.addHandler(yakala)
        lg.setLevel(logging.INFO)
    try:
        yield yakala
    finally:
        for lg, eski in zip(loggerlar, eskiler, strict=True):
            lg.removeHandler(yakala)
            lg.setLevel(eski)


def _yaz(depo_db, kullanici_id, **degerler) -> None:
    with Session(depo_db) as s:
        k = s.get(Kullanici, kullanici_id)
        assert k is not None
        for ad, deger in degerler.items():
            setattr(k, ad, deger)
        s.commit()


def _satir(depo_db, kullanici_id) -> Kullanici:
    with Session(depo_db) as s:
        k = s.get(Kullanici, kullanici_id)
        assert k is not None
        s.expunge(k)
        return k


def _sartlar_onayli(depo_db, kullanici) -> None:
    _yaz(depo_db, kullanici.id, sartlar_kabul_at=AN, sartlar_surumu="eski")


def _checkout(c: TestClient, urun_id, **ek):
    return c.post("/api/odeme/checkout", json={"urun_id": str(urun_id), **ek})


# ═══════════════════════════════════════════════════════════════ (i) ürünler

def test_the_products_endpoint_lists_only_active_products_in_a_stable_order_without_polar_ids_plus_plan_rules(
        c, urunler):
    r = c.get("/api/odeme/urunler")
    assert r.status_code == 200, r.text
    govde = r.json()
    # Planlar basamak sırasıyla, sonra paketler krediye göre artan; arşivlenmiş yok.
    assert [u["ad"] for u in govde["urunler"]] == ["Temel", "Pro", "500 kredi", "1600 kredi"]
    paket = govde["urunler"][2]
    assert set(paket) == {"id", "tur", "plan", "kredi", "fiyat_kurus", "para_birimi", "ad"}
    assert paket["id"] == str(urunler["paket"].id) and paket["plan"] is None
    assert "polar_urun_id" not in r.text and POLAR_PAKET not in r.text, "Polar kimliği istemciye gitmez"
    assert set(govde["planlar"]) == set(planlar.PLANLAR)
    assert govde["planlar"]["free"] == {"aylik_hibe": planlar.PLANLAR["free"].aylik_hibe, "filigran": True,
                                        "video": False, "rank": 0}
    assert govde["planlar"]["pro"]["aylik_hibe"] == planlar.PLANLAR["pro"].aylik_hibe == 4_500


def test_the_products_endpoint_works_with_an_empty_mirror(c):
    govde = c.get("/api/odeme/urunler").json()
    assert govde["urunler"] == [] and set(govde["planlar"]) == {"free", "temel", "pro"}


# ══════════════════════════════════════════════════════════════ (ii) checkout

def test_checkout_sends_the_product_the_users_id_as_external_customer_email_metadata_and_the_success_url_to_polar(
        c, depo_db, kullanici, urunler, sahte_polar, gunluk_kaydi):
    _sartlar_onayli(depo_db, kullanici)
    r = _checkout(c, urunler["paket"].id)
    assert r.status_code == 200, r.text
    assert r.json() == {"url": sahte_polar.url}
    (kw,) = sahte_polar.cagrilar
    assert kw == {
        "urun_id": POLAR_PAKET,                          # Polar ürün kimliği — bizim uuid'miz DEĞİL
        "external_customer_id": str(kullanici.id),       # webhook'un `customer.external_id` ile çözdüğü değer
        "customer_email": kullanici.eposta,
        "success_url": "http://testserver/odeme/tesekkur?checkout_id={CHECKOUT_ID}",   # Polar'ın yer tutucusu
        "metadata": {"kullanici_id": str(kullanici.id), "urun_id": str(urunler["paket"].id)},
    }
    assert [a.get("olay") for _, a in gunluk_kaydi.kayitlar] == ["odeme.checkout"]
    assert gunluk_kaydi.kayitlar[0][1]["urun"] == POLAR_PAKET


def test_the_success_url_uses_the_configured_origin_when_there_is_one(c, depo_db, kullanici, urunler, sahte_polar,
                                                                     monkeypatch):
    """Dağıtımda vekil arkasında isteğin kökeni iç adres olur; `KROMIS_KOKEN` (e-posta bağlantılarının tabanı) kazanır."""
    monkeypatch.setenv(koken.KOKEN_ENV, "https://studio.example.com/")
    _sartlar_onayli(depo_db, kullanici)
    assert _checkout(c, urunler["paket"].id).status_code == 200
    assert sahte_polar.cagrilar[0]["success_url"] == "https://studio.example.com/odeme/tesekkur?checkout_id={CHECKOUT_ID}"


def test_checkout_is_412_until_the_terms_are_accepted_and_the_acceptance_writes_both_columns_once(
        c, depo_db, kullanici, urunler, sahte_polar):
    assert _satir(depo_db, kullanici.id).sartlar_kabul_at is None
    r = _checkout(c, urunler["paket"].id)
    assert r.status_code == 412, r.text
    assert r.json()["detail"] == {"kod": "err.sartlar_gerekli", "surum": hukuk.HUKUK_SURUMU}
    assert sahte_polar.cagrilar == [], "onaysız istek Polar'a gitmez"
    # `sartlar_kabul: false` açıkça da 412 — yalnız `true` kapıyı açar.
    assert _checkout(c, urunler["paket"].id, sartlar_kabul=False).status_code == 412
    r = _checkout(c, urunler["paket"].id, sartlar_kabul=True)
    assert r.status_code == 200, r.text
    satir = _satir(depo_db, kullanici.id)
    assert satir.sartlar_kabul_at is not None and satir.sartlar_surumu == hukuk.HUKUK_SURUMU
    assert abs((satir.sartlar_kabul_at - dt.datetime.now(tz=dt.UTC)).total_seconds()) < 60
    # Onay bir kez: sonraki checkout bayraksız geçer ve damga DEĞİŞMEZ.
    assert _checkout(c, urunler["paket"].id).status_code == 200
    assert _satir(depo_db, kullanici.id).sartlar_kabul_at == satir.sartlar_kabul_at
    assert len(sahte_polar.cagrilar) == 2


def test_checkout_is_404_for_an_unknown_or_archived_product_and_422_for_a_malformed_body(
        c, depo_db, kullanici, urunler, sahte_polar):
    _sartlar_onayli(depo_db, kullanici)
    r = _checkout(c, uuid.uuid4())
    assert r.status_code == 404 and r.json()["detail"] == {"kod": "err.urun_yok"}
    r = _checkout(c, urunler["arsiv"].id)
    assert r.status_code == 404 and r.json()["detail"] == {"kod": "err.urun_yok"}, "arşivlenmiş ürün satılmaz"
    assert c.post("/api/odeme/checkout", json={"urun_id": "paket"}).status_code == 422
    assert c.post("/api/odeme/checkout", json={}).status_code == 422
    assert sahte_polar.cagrilar == []


def test_a_user_on_a_paid_plan_gets_409_with_the_portal_hint_for_a_plan_product_but_may_still_buy_a_pack(
        c, depo_db, kullanici, urunler, sahte_polar):
    _sartlar_onayli(depo_db, kullanici)
    _yaz(depo_db, kullanici.id, plan="temel")
    r = _checkout(c, urunler["pro"].id)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == {"kod": "err.abonelik_var", "portal": True, "plan": "temel", "plan_bitis": None}
    assert _checkout(c, urunler["temel"].id).status_code == 409, "aynı plan da portaldan"
    # İptal edilmiş abonelik: dönem sonu cevapta (sayfa "dönem sonunda ücretsiz plana geçer" der).
    _yaz(depo_db, kullanici.id, plan_bitis=dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.UTC))
    assert _checkout(c, urunler["pro"].id).json()["detail"]["plan_bitis"] == "2026-10-21T12:00:00Z"
    _yaz(depo_db, kullanici.id, plan_bitis=None)
    assert sahte_polar.cagrilar == []
    assert _checkout(c, urunler["paket"].id).status_code == 200, "paket aboneliğe bağlı değil"
    # Ücretsiz kullanıcı plana abone olabilir (free → ücretli checkout'tan).
    _yaz(depo_db, kullanici.id, plan="free")
    assert _checkout(c, urunler["pro"].id).status_code == 200
    assert sahte_polar.cagrilar[-1]["urun_id"] == POLAR_PRO


def test_a_polar_failure_is_502_with_the_provider_code_and_an_error_line_for_sentry(
        c, depo_db, kullanici, urunler, monkeypatch, gunluk_kaydi):
    _sartlar_onayli(depo_db, kullanici)
    kayit = _Kayit(hata=RuntimeError("DUMMY: sandbox-api.polar.sh 503"))
    monkeypatch.setattr(polar, "checkout_ac", kayit.checkout)
    monkeypatch.setattr(polar, "portal_baglantisi", kayit.portal)
    _yaz(depo_db, kullanici.id, polar_musteri_id="00000000-0000-4000-8000-00000000d001")
    r = _checkout(c, urunler["paket"].id)
    assert r.status_code == 502 and r.json()["detail"] == {"kod": "err.odeme_saglayici"}
    # Onay Polar'dan önce yazılır ama istek kapsamlı oturum 502'de ROLLBACK eder: damga kalmaz (rota yorumu).
    _yaz(depo_db, kullanici.id, sartlar_kabul_at=None, sartlar_surumu=None)
    assert _checkout(c, urunler["paket"].id, sartlar_kabul=True).status_code == 502
    assert _satir(depo_db, kullanici.id).sartlar_kabul_at is None, "502'de onay damgası geri alındı"
    _sartlar_onayli(depo_db, kullanici)
    r = c.get("/api/odeme/portal")
    assert r.status_code == 502 and r.json()["detail"] == {"kod": "err.odeme_saglayici"}
    hatalar = [(s, a) for s, a in gunluk_kaydi.kayitlar if a.get("olay") == "odeme.saglayici_hata"]
    assert [(s, a["islem"]) for s, a in hatalar] == [(logging.ERROR, "checkout"), (logging.ERROR, "checkout"),
                                                     (logging.ERROR, "portal")]
    assert all(a["kullanici_id"] == str(kullanici.id) for _, a in hatalar)
    assert "sandbox-api.polar.sh 503" not in r.text, "sağlayıcının metni kullanıcıya gitmez"


# ═══════════════════════════════════════════════════════════════ (iii) portal

def test_the_portal_is_404_without_a_polar_customer_and_returns_the_portal_url_for_that_customer(
        c, depo_db, kullanici, sahte_polar):
    r = c.get("/api/odeme/portal")
    assert r.status_code == 404 and r.json()["detail"] == {"kod": "err.musteri_yok"}
    assert sahte_polar.cagrilar == []
    _yaz(depo_db, kullanici.id, polar_musteri_id="00000000-0000-4000-8000-00000000d001")
    r = c.get("/api/odeme/portal")
    assert r.status_code == 200 and r.json() == {"url": sahte_polar.url}
    assert sahte_polar.cagrilar == ["00000000-0000-4000-8000-00000000d001"], "Polar kimliğiyle, bizim id'mizle değil"


# ═══════════════════════════════════════════════════════ (iv) /api/kredi siparişler

def test_the_credit_endpoint_lists_the_last_ten_orders_newest_first_with_the_product_name(c, depo_db, kullanici,
                                                                                            urunler):
    with Session(depo_db) as s:
        for i in range(12):
            s.add(Siparis(kullanici_id=kullanici.id, polar_siparis_id=f"00000000-0000-4000-8000-0000000000{i:02d}",
                          urun_id=(urunler["paket"] if i % 2 else urunler["temel"]).id,
                          sebep="purchase" if i % 2 else "subscription_create", tutar_kurus=500 if i % 2 else 900,
                          para_birimi="usd", olusturuldu=AN + dt.timedelta(minutes=i)))
        # Başkasının siparişi görünmez (kullanıcı süzgeci; RLS ikinci kapı tests/test_rls.py).
        b = Kullanici(eposta="b-siparis@example.com", parola_ozeti=None, dogrulandi_at=AN, dil=None)
        s.add(b)
        s.flush()
        s.add(Siparis(kullanici_id=b.id, polar_siparis_id="00000000-0000-4000-8000-0000000000bb", urun_id=urunler["paket"].id,
                      sebep="purchase", tutar_kurus=500, para_birimi="usd", olusturuldu=AN + dt.timedelta(hours=1)))
        s.commit()
    govde = c.get("/api/kredi").json()
    siparisler = govde["siparisler"]
    assert len(siparisler) == 10 and siparisler[0]["olusturuldu"] == "2026-09-22T12:11:00Z"
    assert set(siparisler[0]) == {"id", "olusturuldu", "urun", "tutar_kurus", "para_birimi", "sebep"}
    assert (siparisler[0]["urun"], siparisler[0]["tutar_kurus"], siparisler[0]["sebep"]) == ("500 kredi", 500, "purchase")
    assert (siparisler[1]["urun"], siparisler[1]["sebep"]) == ("Temel", "subscription_create")
    assert "2026-09-22T13:00:00Z" not in [s["olusturuldu"] for s in siparisler], "başkasının siparişi yok"
    with Session(depo_db) as s:
        assert defter.siparisler(s, kullanici.id, limit=2)[1]["urun"] == "Temel"
    with depo_db.begin() as cx:
        cx.execute(text("DELETE FROM siparisler")); cx.execute(text("DELETE FROM kullanicilar WHERE eposta = 'b-siparis@example.com'"))


# ═══════════════════════════════════════════════════════════════ (v) sayfalar

@pytest.mark.parametrize("yol, dosya, betik, baslik", [
    ("/planlar", "planlar.html", "planlar.js", "planlar.baslik"),
    ("/odeme/tesekkur", "tesekkur.html", "tesekkur.js", "tesekkur.baslik"),
])
@pytest.mark.parametrize("lang", i18n.LANGUAGES)
def test_the_sales_pages_are_served_translated_with_only_the_dictionary_and_their_own_script(
        c, lang, yol, dosya, betik, baslik):
    r = c.get(yol, headers={"X-Kromis-Lang": lang})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    html = r.text
    assert f'<html lang="{lang}">' in html and "{{t:" not in html and "__APP_" not in html
    assert f'window.KROMIS_LANG="{lang}"' in html and "window.KROMIS_I18N={" in html
    assert i18n.t(baslik, lang) in html
    assert re.findall(r'<script src="/static/([a-z0-9_.-]+)\?v=', html) == ["i18n.js", betik], "stüdyo betikleri yok"
    assert re.findall(r'<link rel="stylesheet" href="/static/([a-z0-9_.-]+)\?v=', html) == \
        ["fonts.css", "flow-tokens.css", "planlar.css"], "style.css yüklenmez (gerekçe planlar.html)"
    import version
    assert set(re.findall(r"\?v=([^\"'\s>]+)", html)) == {version.APP_VERSION}


@pytest.mark.parametrize("betik, sayfa, yollar", [
    ("planlar.js", "planlar.html", ("/api/odeme/urunler", "/api/kredi", "/api/odeme/checkout", "/api/odeme/portal")),
    ("tesekkur.js", "tesekkur.html", ("/api/kredi",)),
])
def test_every_id_the_sales_scripts_bind_exists_in_their_page_and_they_call_the_payment_routes(betik, sayfa, yollar):
    """planlar.js / tesekkur.js `KAPSAM_DISI`nda (tests/test_id_contract.py) — id bağlarının bekçisi burası."""
    with open(os.path.join(REPO, "static", betik), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(REPO, "static", sayfa), encoding="utf-8") as f:
        html = f.read()
    idler = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))
    bagli = set(re.findall(r'\bel\("([a-zA-Z0-9_-]+)"\)', js))
    assert bagli, "tarama boş — desen bayatladı mı?"
    assert bagli <= idler, f"{betik} şu id'lere bağlanıyor ama sayfada yok: {sorted(bagli - idler)}"
    for yol in yollar:
        assert f'"{yol}"' in js, yol
    assert js.lstrip().startswith("// Kromis Studio") and "(() => {" in js, "IIFE — küresel ad bırakmaz"
    assert '"/giris?sonra="' in js, "oturum düşerse giriş sayfasına, `sonra` ile"


def test_the_sales_page_shows_terms_and_portal_only_when_the_server_says_so_and_the_thank_you_page_polls():
    with open(os.path.join(REPO, "static", "planlar.js"), encoding="utf-8") as f:
        planlar_js = f.read()
    with open(os.path.join(REPO, "static", "planlar.html"), encoding="utf-8") as f:
        html = f.read()
    assert re.search(r'<section id="planlar-sartlar"[^>]*\bhidden>', html) and \
        re.search(r'<section id="planlar-portal"[^>]*\bhidden>', html), "ikisi de gizli başlar"
    assert 'res.status === 412 && kod === "err.sartlar_gerekli"' in planlar_js
    assert 'res.status === 409 && kod === "err.abonelik_var"' in planlar_js
    assert "sartlar_kabul: Boolean(sartlarKabul)" in planlar_js and "window.location.assign(govde.url)" in planlar_js
    with open(os.path.join(REPO, "static", "tesekkur.js"), encoding="utf-8") as f:
        tesekkur_js = f.read()
    assert "const ARALIK_MS = 2000;" in tesekkur_js and "const TAVAN_MS = 30000;" in tesekkur_js
    for anahtar in ("tesekkur.islendi", "tesekkur.gecikti"):
        assert f'"{anahtar}"' in tesekkur_js


# ═══════════════════════════════════════════════════════════════ (vi) admin

def test_the_admin_summary_flags_an_empty_or_stale_product_mirror_and_the_route_logs_a_warning(
        c, depo_db, kullanici, gunluk_kaydi, monkeypatch):
    monkeypatch.setattr(odeme.zaman, "an", lambda: AN)
    with Session(depo_db) as s:
        assert odeme.urunler_bayat_mi(s) is True, "ayna boş → bayat"
        assert depo_admin.odeme_ozeti(s)["urunler_bayat"] is True
        s.add(Urun(polar_urun_id=POLAR_PAKET, tur="paket", plan=None, kredi=500, fiyat_kurus=500, para_birimi="usd",
                   ad="500 kredi", guncellendi=AN - dt.timedelta(days=6, hours=23)))
        s.commit()
        assert odeme.urunler_bayat_mi(s) is False
        s.execute(text("UPDATE urunler SET guncellendi = :t"), {"t": AN - dt.timedelta(days=7, minutes=1)})
        s.commit()
        assert odeme.urunler_bayat_mi(s) is True
    kullanici.is_admin = True
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    r = c.get("/api/admin/odeme-olaylari")
    assert r.status_code == 200 and r.json()["ozet"]["urunler_bayat"] is True
    uyari = [(s, a) for s, a in gunluk_kaydi.kayitlar if a.get("olay") == "odeme.urunler_bayat"]
    assert [(s, a["gun"]) for s, a in uyari] == [(logging.WARNING, 7)]
    with open(os.path.join(REPO, "static", "admin.js"), encoding="utf-8") as f:
        assert 'el("admin-odeme-uyari").hidden = !m.ozet.urunler_bayat;' in f.read()
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET is_admin = false WHERE id = :id"), {"id": kullanici.id})


def test_the_admin_credit_route_writes_the_pack_bucket_when_asked_and_the_grant_bucket_by_default(c, depo_db, kullanici):
    kullanici.is_admin = True
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    yol = f"/api/admin/kullanicilar/{kullanici.id}/kredi"
    r = c.post(yol, json={"miktar": 40, "aciklama": "DUMMY hibe"})
    assert r.status_code == 200 and (r.json()["bakiye"], r.json()["paket_bakiye"]) == (40, 0)
    r = c.post(yol, json={"miktar": 500, "aciklama": "DUMMY paket", "kova": "paket"})
    assert r.status_code == 200, r.text
    assert (r.json()["bakiye"], r.json()["paket_bakiye"]) == (40, 500) and r.json()["hareket"]["kova"] == "paket"
    assert c.post(yol, json={"miktar": 1, "aciklama": "x", "kova": "bonus"}).status_code == 422, "CHECK'e varmadan"
    with Session(depo_db) as s:
        b_ = defter.bakiye(s, kullanici.id)
        assert (b_.hibe, b_.paket, b_.toplam) == (40, 500, 540)
        kovalar = list(s.scalars(select(KrediHareketi.kova).where(KrediHareketi.kullanici_id == kullanici.id)))
        assert sorted(kovalar) == ["hibe", "paket"]
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET is_admin = false WHERE id = :id"), {"id": kullanici.id})


def test_the_terms_version_comes_from_the_legal_module_not_a_placeholder():
    """Faz 4 / 6: `SARTLAR_SURUMU = "0000-yer-tutucu"` gitti, sabit `services/hukuk.HUKUK_SURUMU` (tests/test_hukuk.py)."""
    assert not hasattr(odeme, "SARTLAR_SURUMU")
    assert odeme.URUNLER_BAYAT_GUN == 7
