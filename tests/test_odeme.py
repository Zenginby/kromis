"""Polar webhook ve olay işleme (Faz 4 / 3; docs/faz4-odeme-abonelik-kvkk.md §3, K4/K6).

Sahte Polar, GERÇEK imza: yükler tests/fixtures/polar/*.json (SDK 0.32.0 modelinden
geçer — `test_every_fixture_is_a_valid_sdk_payload`), imza `polar.imzala` ile
gerçek HMAC (sır `DUMMY…`), `standardwebhooks.Webhook.verify` HİÇ yamalanmaz.
Defter ve tablolar gerçek Postgres (`depo_db`); webhook oturumsuz, `kullanici`
fixture'ının kimlik override'ı bu rotaya dokunmaz.

Sorular:
  (i)   İMZA — geçerli/yanlış sır/eksik başlık/eski damga/bozuk imza/oynanmış gövde
        → `ImzaHatasi`; JSON dışı ya da `type`siz gövde → `YukHatasi`; sır yoksa
        `YapilandirmaHatasi`; SDK'nın `validate_event`i bizim imzamızı KABUL eder
        (aynı sır dönüşümü); ortam boş = sandbox, bozuk = gürültü.
  (ii)  ROTA — 503 sırsız, 413 büyük gövde, 400 imza, 200 `islendi`/`yinelenen`/`atlandi`,
        500 iç hata (olay satırı YOK — aynı transaksiyon).
  (iii) İDEMPOTENCY ÜÇ KATMAN — aynı `webhook-id` → satır sayısı aynı; aynı sipariş iki
        farklı olayla → tek `paket` satırı, tek sipariş; RLS uygulama rolüyle admin bağlamı
        `siparisler`e ve `kredi_hareketleri`ne yazar.
  (iv)  OLAY → EYLEM — paket yükler; `subscription_create` plan + hibeye tamamla; `cycle`
        dolu bakiyeye dokunmaz; `canceled` `plan_bitis`, plan kalır; `uncanceled` NULL;
        `revoked` free + `sona_erme` yalnız hibe kovası; `updated` pro → temel düşürme,
        `active` dışı durum dokunmaz, eski abonelik atlanır; `customer.*` müşteri kimliği,
        çakışma; `refunded` WARNING, defter dokunulmaz; kullanıcı/ürün yok → 200 + `hata`.
  (v)   ADMİN — `GET /api/admin/odeme-olaylari` liste + `?hata=1` + özet; gövde dökülmez.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

import app as appmod
from services import db as dbmod
from services import defter, depo_admin, gunluk, kiraci, odeme, planlar, polar
from services.tablolar import KrediHareketi, Kullanici, OdemeOlayi, Siparis, Urun
from tests.test_rls import ROL, uygulama_motoru  # noqa: F401 — SET ROLE fixture'ı (getfixturevalue)

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "polar")
# gitleaks dersi (Faz 2 / 9): sır sabit ve `DUMMY`li — gerçek bir sırra benzemez.
SIR = "DUMMY_polar_webhook_sirri_0123456789abcdef"
YOL = "/api/odeme/webhook"
AN = dt.datetime(2026, 9, 21, 12, 0, tzinfo=dt.UTC)
URUN_PAKET = "00000000-0000-4000-8000-00000000e001"
URUN_PLAN = "00000000-0000-4000-8000-00000000e002"
ABONELIK = "00000000-0000-4000-8000-00000000a0b0"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


# ──────────────────────────────────────────────────────────── fixture'lar

@pytest.fixture(autouse=True)
def temiz(depo_db, monkeypatch):
    monkeypatch.setenv(polar.WEBHOOK_SIRRI_ENV, SIR)
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM odeme_olaylari"))
        c.execute(text("DELETE FROM siparisler"))
        c.execute(text("DELETE FROM kredi_hareketleri WHERE kullanici_id IN "
                       "(SELECT id FROM kullanicilar WHERE eposta LIKE 'b-%@example.com')"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
        c.execute(text("DELETE FROM urunler"))
    yield


@pytest.fixture
def c() -> TestClient:
    return TestClient(appmod.app)


@pytest.fixture
def urunler(depo_db) -> dict[str, Urun]:
    """Ayna: 500 kredilik paket + `temel` planı (Polar id'leri fixture'lardaki DUMMY uuid'ler)."""
    with Session(depo_db, expire_on_commit=False) as s:
        paket = Urun(polar_urun_id=URUN_PAKET, tur="paket", plan=None, kredi=500, fiyat_kurus=500,
                     para_birimi="usd", ad="500 kredi")
        plan = Urun(polar_urun_id=URUN_PLAN, tur="plan", plan="temel", kredi=1_000, fiyat_kurus=900,
                    para_birimi="usd", ad="Temel")
        s.add_all([paket, plan])
        s.commit()
        return {"paket": paket, "plan": plan}


class _Yakala(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.kayitlar: list[tuple[int, dict]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.kayitlar.append((record.levelno, gunluk.alanlar(record)))

    def olaylar(self) -> list[str]:
        return [a.get("olay", "") for _, a in self.kayitlar]


@pytest.fixture
def gunluk_kaydi() -> Iterator[_Yakala]:
    logger = logging.getLogger("kromis.odeme")
    yakala = _Yakala()
    eski = logger.level
    logger.disabled = False
    logger.addHandler(yakala)
    logger.setLevel(logging.INFO)
    try:
        yield yakala
    finally:
        logger.removeHandler(yakala)
        logger.setLevel(eski)


# ──────────────────────────────────────────────────────────── yardımcılar

def _kullanici(depo_db, *, plan: str = "free", abonelik: str | None = None, musteri: str | None = None) -> Kullanici:
    with Session(depo_db, expire_on_commit=False) as s:
        k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None, dogrulandi_at=AN,
                      dil=None, plan=plan, polar_abonelik_id=abonelik, polar_musteri_id=musteri)
        s.add(k)
        s.commit()
        return k


def _yuk(ad: str, kullanici: Kullanici | None = None, **degisiklik) -> dict:
    """Fixture yükü; `customer.external_id` (ya da `customer.*`de `external_id`) kullanıcının id'si; `data` alanları ezilebilir."""
    with open(os.path.join(FIXTURES, f"{ad}.json"), encoding="utf-8") as f:
        yuk = json.load(f)
    if kullanici is not None:
        if yuk["type"].startswith("customer."):
            yuk["data"]["external_id"] = str(kullanici.id)
        else:
            yuk["data"]["customer"]["external_id"] = str(kullanici.id)
    yuk["data"].update(degisiklik)
    return yuk


def _gonder(c: TestClient, yuk: dict, *, webhook_id: str | None = None, sir: str = SIR,
            zaman: dt.datetime | None = None, govde: bytes | None = None, basliklar: dict | None = None):
    govde = govde if govde is not None else json.dumps(yuk).encode()
    b = polar.imzala(govde, sir, webhook_id=webhook_id or f"wh_{uuid.uuid4().hex}", zaman=zaman)
    b.update(basliklar or {})
    return c.post(YOL, content=govde, headers={"content-type": "application/json", **b})


def _kovalar(depo_db, kullanici_id) -> tuple[int, int]:
    with Session(depo_db) as s:
        b = defter.bakiye(s, kullanici_id)
        return b.hibe, b.paket


def _hareketler(depo_db, kullanici_id) -> list[tuple[str, str, int, str]]:
    with Session(depo_db) as s:
        return [(h.tur, h.kova, h.miktar, h.idempotency_anahtari) for h in s.scalars(
            select(KrediHareketi).where(KrediHareketi.kullanici_id == kullanici_id)
            .order_by(KrediHareketi.olusturuldu, KrediHareketi.idempotency_anahtari))]


def _satir(depo_db, kullanici_id) -> Kullanici:
    with Session(depo_db) as s:
        k = s.get(Kullanici, kullanici_id)
        assert k is not None
        s.expunge(k)
        return k


def _olaylar(depo_db) -> list[OdemeOlayi]:
    with Session(depo_db, expire_on_commit=False) as s:
        return list(s.scalars(select(OdemeOlayi).order_by(OdemeOlayi.alindi, OdemeOlayi.webhook_id)))


def _siparisler(depo_db) -> list[Siparis]:
    with Session(depo_db, expire_on_commit=False) as s:
        return list(s.scalars(select(Siparis).order_by(Siparis.olusturuldu)))


def _hibe(depo_db, kullanici_id, miktar: int) -> None:
    with Session(depo_db) as s:
        assert defter.hibe(s, kullanici_id, miktar, f"hibe:{kullanici_id}:tohum-{uuid.uuid4().hex[:6]}", an=AN)
        s.commit()


def _paket(depo_db, kullanici_id, miktar: int) -> None:
    with Session(depo_db) as s:
        assert defter.paket_yukle(s, kullanici_id, miktar, f"paket:tohum_{uuid.uuid4().hex[:8]}", an=AN)
        s.commit()


# ══════════════════════════════════════════════════════════ (i) imza ve ortam

def test_the_environment_defaults_to_sandbox_and_a_typo_is_loud():
    """Belge §3: boş = sandbox (yanlışlıkla canlıya değil yanlışlıkla sandbox'a bağlanılır)."""
    assert polar.ortam({}) == "sandbox"
    assert polar.ortam({polar.ORTAM_ENV: " production "}) == "production"
    assert polar.ortam({polar.ORTAM_ENV: "sandbox"}) == "sandbox"
    with pytest.raises(ValueError):
        polar.ortam({polar.ORTAM_ENV: "prod"})
    assert polar.erisim_jetonu({}) is None and polar.webhook_sirri({polar.WEBHOOK_SIRRI_ENV: " "}) is None
    assert polar.erisim_jetonu({polar.JETON_ENV: "polar_oat_DUMMY"}) == "polar_oat_DUMMY"
    with pytest.raises(polar.YapilandirmaHatasi) as e:
        polar.istemci({})
    assert str(e.value) == polar.JETON_ENV


def test_a_signed_body_round_trips_and_every_tamper_is_rejected_before_the_body_is_parsed():
    govde = json.dumps({"type": "order.paid", "data": {"id": "ord_1"}}).encode()
    b = polar.imzala(govde, SIR, webhook_id="wh_1", zaman=dt.datetime.now(tz=dt.UTC))
    assert set(b) == {polar.BASLIK_ID, polar.BASLIK_ZAMAN, polar.BASLIK_IMZA} and b[polar.BASLIK_IMZA].startswith("v1,")
    olay = polar.olay_dogrula(govde, b, sir=SIR)
    assert (olay.webhook_id, olay.tur, olay.nesne_id) == ("wh_1", "order.paid", "ord_1")
    assert olay.zaman.tzinfo is not None and abs((olay.zaman - dt.datetime.now(tz=dt.UTC)).total_seconds()) < 5
    # Başlık adları büyük/küçük harften bağımsız (HTTP), Starlette `Headers` gibi bir Mapping de geçer.
    assert polar.olay_dogrula(govde, {k.upper(): v for k, v in b.items()}, sir=SIR).tur == "order.paid"
    # Yanlış sır, oynanmış gövde, eksik başlık, bozuk imza, `v0` sürümü → hepsi ImzaHatasi.
    with pytest.raises(polar.ImzaHatasi):
        polar.olay_dogrula(govde, b, sir=SIR + "x")
    with pytest.raises(polar.ImzaHatasi):
        polar.olay_dogrula(govde + b" ", b, sir=SIR)
    for eksik in (polar.BASLIK_ID, polar.BASLIK_ZAMAN, polar.BASLIK_IMZA):
        with pytest.raises(polar.ImzaHatasi):
            polar.olay_dogrula(govde, {k: v for k, v in b.items() if k != eksik}, sir=SIR)
    for bozuk in ("v1", "v1,%%%", "v0," + b[polar.BASLIK_IMZA][3:], ""):
        with pytest.raises(polar.ImzaHatasi):
            polar.olay_dogrula(govde, {**b, polar.BASLIK_IMZA: bozuk}, sir=SIR)
    with pytest.raises(polar.ImzaHatasi):
        polar.olay_dogrula(govde, {**b, polar.BASLIK_ZAMAN: "dun"}, sir=SIR)
    with pytest.raises(polar.YapilandirmaHatasi):
        polar.olay_dogrula(govde, b, sir="")


def test_a_replay_outside_the_five_minute_window_is_rejected_even_with_a_valid_signature():
    """Standard Webhooks toleransı ±5 dk (kütüphanenin); eski ya da gelecekten damga → ImzaHatasi."""
    govde = b'{"type":"order.paid","data":{}}'
    simdi = dt.datetime.now(tz=dt.UTC)
    for kayma in (dt.timedelta(minutes=6), -dt.timedelta(minutes=6)):
        b = polar.imzala(govde, SIR, webhook_id="wh_eski", zaman=simdi - kayma)
        with pytest.raises(polar.ImzaHatasi):
            polar.olay_dogrula(govde, b, sir=SIR)
    b = polar.imzala(govde, SIR, webhook_id="wh_taze", zaman=simdi - dt.timedelta(minutes=4))
    assert polar.olay_dogrula(govde, b, sir=SIR).tur == "order.paid"


def test_a_validly_signed_body_that_is_not_an_event_envelope_is_a_payload_error_not_a_signature_error():
    for govde in (b"[]", b'"x"', b'{"data": {}}', b'{"type": 5}', b"degil json"):
        b = polar.imzala(govde, SIR, webhook_id="wh_zarf")
        with pytest.raises(polar.YukHatasi if govde != b"degil json" else polar.ImzaHatasi):
            polar.olay_dogrula(govde, b, sir=SIR)
    # UTF-8 olmayan gövde: kütüphane `decode` ederken düşer — imza hatası (bu Polar'dan gelmedi).
    with pytest.raises(polar.ImzaHatasi):
        polar.olay_dogrula(b"\xff\xfe", polar.imzala(b"{}", SIR, webhook_id="wh_bayt"), sir=SIR)


def test_the_sdk_accepts_our_signature_so_the_secret_convention_is_the_sdks(depo_db):
    """`_anahtar` = SDK `validate_event`in dönüşümü: SDK bizim imzaladığımız gövdeyi aynı ham sırla doğrular."""
    from polar_sdk.webhooks import WebhookVerificationError, validate_event
    yuk = _yuk("order_paid_purchase")
    govde = json.dumps(yuk).encode()
    b = polar.imzala(govde, SIR, webhook_id="wh_sdk")
    model = validate_event(govde, b, SIR)
    assert type(model).__name__ == "WebhookOrderPaidPayload"
    assert model.data.customer.external_id == yuk["data"]["customer"]["external_id"]
    with pytest.raises(WebhookVerificationError):
        validate_event(govde, b, SIR + "x")


@pytest.mark.parametrize("ad", sorted(a[:-5] for a in os.listdir(FIXTURES) if a.endswith(".json")))
def test_every_fixture_is_a_valid_sdk_payload_and_carries_the_fields_we_read(ad):
    """Sahte yükler SDK 0.32.0 (openapi 2026-04) modelinden geçer — okuduğumuz alanlar sağlayıcı şemasında VAR.

    Polar'a bu oturumdan erişilemedi; şemanın kaynağı SDK. Pin ilerlerse (requirements.txt)
    bu test yeni şemanın alan adlarını yeniden ölçer."""
    from polar_sdk._webhooks import WebhookPayloadAdapter
    yuk = _yuk(ad)
    WebhookPayloadAdapter.validate_python(yuk)
    veri = yuk["data"]
    assert yuk["type"] in odeme.ISLENEN_TURLER and isinstance(veri["id"], str)
    if yuk["type"].startswith("order."):
        assert veri["billing_reason"] in ("purchase", "subscription_create", "subscription_cycle", "subscription_update")
        assert {"product_id", "subscription_id", "customer_id", "total_amount", "currency", "refunded_amount",
                "metadata"} <= set(veri)
        assert "external_id" in veri["customer"]
    elif yuk["type"].startswith("subscription."):
        assert {"status", "product_id", "current_period_end", "cancel_at_period_end", "ends_at", "customer_id"} <= set(veri)
        assert "external_id" in veri["customer"]
    else:
        assert "external_id" in veri
    # DUMMY disiplini: e-posta/ad gerçek değil.
    assert "dummy@example.com" in json.dumps(yuk)


def test_the_handled_event_set_is_exactly_what_the_owner_subscribes_the_endpoint_to():
    """Belge §3 "Sahibin adımı": Polar panelinde seçilecek olaylar bu küme; listede olmayan tür 200 `atlandi`."""
    assert odeme.ISLENEN_TURLER == {"order.paid", "order.refunded", "subscription.active", "subscription.updated",
                                   "subscription.canceled", "subscription.uncanceled", "subscription.revoked",
                                   "customer.created", "customer.updated"}
    fixture_turleri = {json.load(open(os.path.join(FIXTURES, a), encoding="utf-8"))["type"]
                       for a in os.listdir(FIXTURES) if a.endswith(".json")}
    assert fixture_turleri == odeme.ISLENEN_TURLER, "her işlenen tür için bir fixture, fazlası yok"


# ══════════════════════════════════════════════════════════ (ii) rota

def test_the_route_is_sessionless_and_answers_503_without_a_secret_413_to_a_huge_body_and_400_to_a_bad_signature(
        c, monkeypatch, depo_db, gunluk_kaydi):
    yuk = _yuk("order_paid_purchase")
    monkeypatch.delenv(polar.WEBHOOK_SIRRI_ENV)
    r = _gonder(c, yuk)
    assert (r.status_code, r.json()) == (503, {"detail": "odeme_yapilandirilmadi"})
    monkeypatch.setenv(polar.WEBHOOK_SIRRI_ENV, SIR)
    # Sırsız/yanlış sırlı çağrı: 400 + kod; gövde HİÇ işlenmez, satır yok.
    r = _gonder(c, yuk, sir="baska-sir")
    assert (r.status_code, r.json()) == (400, {"detail": "imza_gecersiz"})
    r = c.post(YOL, content=json.dumps(yuk).encode(), headers={"content-type": "application/json"})
    assert r.status_code == 400
    # İmzalı ama zarf değil.
    r = _gonder(c, {}, govde=b"[]")
    assert (r.status_code, r.json()) == (400, {"detail": "govde_gecersiz"})
    # Tavan üstü gövde: HMAC'ten önce 413 (beyan edilen uzunluk ve gerçek uzunluk).
    buyuk = b'{"type":"order.paid","data":{"x":"' + b"a" * (256 * 1024) + b'"}}'
    r = _gonder(c, {}, govde=buyuk)
    assert (r.status_code, r.json()) == (413, {"detail": "govde_buyuk"})
    r = c.post(YOL, content=b"{}", headers={"content-length": str(300 * 1024), polar.BASLIK_ID: "x",
                                            polar.BASLIK_ZAMAN: "1", polar.BASLIK_IMZA: "v1,x"})
    assert r.status_code == 413
    assert _olaylar(depo_db) == []
    assert "odeme.imza_gecersiz" in gunluk_kaydi.olaylar()
    # Oturum çerezi, CSRF/Origin yok — Polar'ın sunucusu böyle gelir; köken kapısı başlıksız POST'u geçirir.
    assert "cookie" not in {k.lower() for k in _gonder(c, yuk, sir="x").request.headers}


def test_an_internal_error_rolls_back_the_event_row_too_and_answers_500_so_polar_retries(
        depo_db, urunler, monkeypatch, gunluk_kaydi):
    """Belge §3 DİKKAT: kayıt ve işleme AYNI transaksiyon — düşerse olay satırı da gider, yeniden deneme temiz gelir."""
    k = _kullanici(depo_db)

    def _patla(*a, **kw):
        raise RuntimeError("DUMMY patlama")
    monkeypatch.setattr(defter, "paket_yukle", _patla)
    c = TestClient(appmod.app, raise_server_exceptions=False)
    r = _gonder(c, _yuk("order_paid_purchase", k), webhook_id="wh_500")
    assert r.status_code == 500
    assert _olaylar(depo_db) == [] and _siparisler(depo_db) == [] and _kovalar(depo_db, k.id) == (0, 0)
    assert [a for s, a in gunluk_kaydi.kayitlar if s == logging.ERROR][0]["olay"] == "odeme.hata"
    # Aynı `webhook-id` ile yeniden deneme: bu kez işlenir (satır yoktu, "çoktan alındı" demez).
    monkeypatch.undo()
    monkeypatch.setenv(polar.WEBHOOK_SIRRI_ENV, SIR)
    r = _gonder(TestClient(appmod.app), _yuk("order_paid_purchase", k), webhook_id="wh_500")
    assert r.json() == {"durum": "islendi"} and _kovalar(depo_db, k.id) == (0, 500)


def test_an_unknown_event_type_is_recorded_and_skipped_with_200(c, depo_db):
    """Bilinmeyen tür (ör. `checkout.created`, `benefit_grant.cycled`): kaydet, işleme, 200 — Polar yeniden denemez."""
    r = _gonder(c, {"type": "checkout.created", "data": {"id": "chk_1", "customer_email": "dummy@example.com"}},
                webhook_id="wh_bilinmeyen")
    assert (r.status_code, r.json()) == (200, {"durum": "atlandi"})
    (o,) = _olaylar(depo_db)
    assert (o.webhook_id, o.tur, o.polar_nesne_id, o.kullanici_id, o.hata) == ("wh_bilinmeyen", "checkout.created", "chk_1", None, None)
    assert o.islendi_at is not None and o.govde["data"]["customer_email"] == "dummy@example.com"


# ══════════════════════════════════════════════════════════ (iii) idempotency üç katman

def test_a_paid_pack_order_loads_the_pack_bucket_writes_the_order_row_and_a_redelivery_is_a_no_op(
        c, depo_db, urunler, gunluk_kaydi):
    k = _kullanici(depo_db)
    yuk = _yuk("order_paid_purchase", k, metadata={"api_key": "sk-DUMMYDUMMYDUMMYDUMMYDUMMY", "not": "x"})
    r = _gonder(c, yuk, webhook_id="wh_paket")
    assert (r.status_code, r.json()) == (200, {"durum": "islendi"}), r.text
    assert _kovalar(depo_db, k.id) == (0, 500)
    assert _hareketler(depo_db, k.id) == [("paket", "paket", 500, f"paket:{yuk['data']['id']}")]
    (s,) = _siparisler(depo_db)
    assert (s.kullanici_id, s.polar_siparis_id, s.urun_id, s.sebep, s.tutar_kurus, s.para_birimi, s.polar_abonelik_id) == (
        k.id, yuk["data"]["id"], urunler["paket"].id, "purchase", 500, "usd", None)
    (o,) = _olaylar(depo_db)
    assert (o.tur, o.kullanici_id, o.hata, o.polar_nesne_id) == ("order.paid", k.id, None, yuk["data"]["id"])
    assert o.islendi_at is not None
    # Gövde REDAKTE: anahtar kokan alan `[REDACTED]`, öteki alanlar aynen; e-posta kalır (K10).
    assert o.govde["data"]["metadata"] == {"api_key": "[REDACTED]", "not": "x"}
    assert o.govde["data"]["customer"]["email"] == "dummy@example.com"
    # Müşteri kimliği bağlandı (sonraki olaylar `polar_musteri_id` ile de çözülür).
    assert _satir(depo_db, k.id).polar_musteri_id == yuk["data"]["customer_id"]
    # Aynı `webhook-id` yeniden: 200 `yinelenen`, hiçbir satır artmaz.
    r = _gonder(c, yuk, webhook_id="wh_paket")
    assert r.json() == {"durum": "yinelenen"}
    assert len(_olaylar(depo_db)) == 1 and len(_siparisler(depo_db)) == 1 and _kovalar(depo_db, k.id) == (0, 500)
    islenen = [a for _, a in gunluk_kaydi.kayitlar if a.get("olay") == "odeme.order.paid"]
    assert len(islenen) == 1 and islenen[0]["kredi"] == 500 and islenen[0]["kullanici_id"] == str(k.id)
    assert "odeme.yinelenen" in gunluk_kaydi.olaylar()


def test_the_same_order_told_by_two_deliveries_with_different_webhook_ids_is_credited_once(c, depo_db, urunler):
    """K4 iş katmanı: panelden "yeniden gönder" yeni `webhook-id` üretir — defter anahtarı sipariş kimliği, sipariş UNIQUE."""
    k = _kullanici(depo_db)
    yuk = _yuk("order_paid_purchase", k)
    assert _gonder(c, yuk, webhook_id="wh_a").json() == {"durum": "islendi"}
    assert _gonder(c, yuk, webhook_id="wh_b").json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (0, 500) and len(_siparisler(depo_db)) == 1
    assert [o.webhook_id for o in _olaylar(depo_db)] == ["wh_a", "wh_b"]


def test_the_webhook_writes_orders_and_ledger_rows_under_the_application_role_through_the_admin_context(
        request, depo_db, urunler, monkeypatch, c):
    """RLS: `siparisler` ve `kredi_hareketleri` INSERT'i `yonetici_ekler` politikasıyla (K4) — rota admin bağlamı kurar."""
    motor = request.getfixturevalue("uygulama_motoru")

    def _uygulama_oturumu():
        with Session(motor) as s:
            try:
                yield s
            except BaseException:
                s.rollback()
                raise
            else:
                s.commit()
    appmod.app.dependency_overrides[dbmod.oturum] = _uygulama_oturumu    # `kullanici` fixture'ı teardown'da düşürür
    k = _kullanici(depo_db)
    gorulen: list[kiraci.Baglam | None] = []
    asil = odeme.isle

    def _izle(db, olay, **kw):
        gorulen.append(kiraci.aktif())
        return asil(db, olay, **kw)
    monkeypatch.setattr(odeme, "isle", _izle)
    r = _gonder(c, _yuk("order_paid_purchase", k))
    assert (r.status_code, r.json()) == (200, {"durum": "islendi"}), r.text
    assert gorulen == [kiraci.Baglam(kullanici_id=None, rol=kiraci.ADMIN)]
    assert _kovalar(depo_db, k.id) == (0, 500) and len(_siparisler(depo_db)) == 1
    # Bağlamsız aynı INSERT politikaya çarpar — bağlamın var olma sebebi.
    with Session(motor) as s:
        with pytest.raises(ProgrammingError):
            s.add(Siparis(kullanici_id=k.id, polar_siparis_id="ord_baglamsiz", urun_id=urunler["paket"].id,
                          sebep="purchase", tutar_kurus=1, para_birimi="usd"))
            s.flush()
        s.rollback()


# ══════════════════════════════════════════════════════════ (iv) olay → eylem

def test_a_subscription_create_order_sets_the_plan_and_tops_the_grant_bucket_up_to_the_plan_grant(
        c, depo_db, urunler):
    """K6 "hibeye tamamla": 300 → 1.000 (+700), anahtar `hibe:<u>:polar:<order_id>`; plan `temel`, abonelik bağlandı."""
    k = _kullanici(depo_db)
    _hibe(depo_db, k.id, 300)
    _paket(depo_db, k.id, 40)   # paket kovası hesaba GİRMEZ
    yuk = _yuk("order_paid_subscription_create", k)
    r = _gonder(c, yuk)
    assert r.json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (planlar.PLANLAR["temel"].aylik_hibe, 40) == (1_000, 40)
    hareketler = _hareketler(depo_db, k.id)
    assert hareketler[-1] == ("hibe", "hibe", 700, f"hibe:{k.id}:polar:{yuk['data']['id']}")
    assert re.fullmatch(rf"^hibe:{UUID}:polar:[A-Za-z0-9_-]+$", hareketler[-1][3])
    satir = _satir(depo_db, k.id)
    assert (satir.plan, satir.polar_abonelik_id, satir.plan_bitis) == ("temel", ABONELIK, None)
    (s,) = _siparisler(depo_db)
    assert (s.sebep, s.polar_abonelik_id, s.tutar_kurus) == ("subscription_create", ABONELIK, 900)
    # `subscription.active` ikizi: plan aynı, hibe TEKRAR yatmaz (sipariş anahtarlı, bu olayda sipariş yok).
    assert _gonder(c, _yuk("subscription_active", k)).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (1_000, 40) and len(_hareketler(depo_db, k.id)) == len(hareketler)


def test_a_cycle_order_tops_up_only_when_below_the_grant_and_leaves_a_full_bucket_alone(c, depo_db, urunler):
    k = _kullanici(depo_db, plan="temel", abonelik=ABONELIK)
    _hibe(depo_db, k.id, 1_400)   # admin kredisiyle hibe üstünde: dokunulmaz, kesilmez
    yuk = _yuk("order_paid_subscription_cycle", k, id="00000000-0000-4000-8000-00000000f002")
    assert _gonder(c, yuk).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (1_400, 0) and len(_hareketler(depo_db, k.id)) == 1
    # Ay ortası düşük bakiye: yeni dönemde tamamlanır — sipariş başına bir kez.
    with Session(depo_db) as s:
        defter.duzelt(s, k.id, -1_100, "DUMMY harcama", admin_id=k.id, an=AN)   # harcamayı temsil eder
        s.commit()
    yuk2 = _yuk("order_paid_subscription_cycle", k, id="00000000-0000-4000-8000-00000000f003")
    assert _gonder(c, yuk2).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (1_000, 0)
    assert _gonder(c, yuk2, webhook_id="wh_tekrar").json() == {"durum": "islendi"}   # ikinci teslimat: anahtar çakışır
    assert _kovalar(depo_db, k.id) == (1_000, 0)
    assert len(_siparisler(depo_db)) == 2


def test_canceled_keeps_the_plan_and_records_the_period_end_and_uncanceled_clears_it(c, depo_db, urunler):
    k = _kullanici(depo_db, plan="temel", abonelik=ABONELIK)
    assert _gonder(c, _yuk("subscription_canceled", k)).json() == {"durum": "islendi"}
    satir = _satir(depo_db, k.id)
    assert satir.plan == "temel" and satir.plan_bitis == dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.UTC)
    with Session(depo_db) as s:
        assert defter.plan_bitis_oku(s, k.id) == satir.plan_bitis
    assert _gonder(c, _yuk("subscription_uncanceled", k)).json() == {"durum": "islendi"}
    assert _satir(depo_db, k.id).plan_bitis is None and _satir(depo_db, k.id).plan == "temel"


def test_revoked_drops_to_free_and_expires_only_the_grant_bucket_while_the_pack_bucket_survives(
        c, depo_db, urunler, gunluk_kaydi):
    """K3/K6: `sona_erme` yalnız hibe kovasında (1.000 → 200), paket 500 aynen; anahtar `sona_erme:<u>:<abonelik>:<gün>`."""
    k = _kullanici(depo_db, plan="temel", abonelik=ABONELIK)
    _hibe(depo_db, k.id, 1_000)
    _paket(depo_db, k.id, 500)
    assert _gonder(c, _yuk("subscription_revoked", k)).json() == {"durum": "islendi"}
    satir = _satir(depo_db, k.id)
    assert (satir.plan, satir.polar_abonelik_id, satir.plan_bitis) == ("free", None, None)
    assert _kovalar(depo_db, k.id) == (planlar.PLANLAR["free"].aylik_hibe, 500) == (200, 500)
    son = _hareketler(depo_db, k.id)[-1]
    assert son[:3] == ("sona_erme", "hibe", -800)
    assert re.fullmatch(rf"^sona_erme:{UUID}:[A-Za-z0-9_-]+:\d{{4}}-\d{{2}}-\d{{2}}$", son[3]), son[3]
    assert son[3].startswith(f"sona_erme:{k.id}:{ABONELIK}:")
    with Session(depo_db) as s:
        assert defter.tutarlilik(s) == []
    # Aynı gün ikinci `revoked` (yeniden gönderim, yeni webhook-id): anahtar çakışır, ikinci düşüm YOK.
    assert _gonder(c, _yuk("subscription_revoked", k)).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (200, 500)
    kayit = [a for _, a in gunluk_kaydi.kayitlar if a.get("olay") == "odeme.subscription.revoked"]
    assert kayit[0]["dusen"] == 800 and kayit[1]["dusen"] == 0


def test_updated_applies_a_downgrade_with_an_expiry_row_and_ignores_non_active_states_and_stale_subscriptions(
        c, depo_db, urunler):
    """Portaldan pro → temel: plan `temel`, hibe 3.000 → 1.000 (`sona_erme` −2.000); `past_due` dokunmaz; eski abonelik atlanır."""
    k = _kullanici(depo_db, plan="pro", abonelik=ABONELIK)
    _hibe(depo_db, k.id, 3_000)
    _paket(depo_db, k.id, 10)
    r = _gonder(c, _yuk("subscription_updated", k))
    assert r.json() == {"durum": "islendi"}
    assert _satir(depo_db, k.id).plan == "temel" and _kovalar(depo_db, k.id) == (1_000, 10)
    assert _hareketler(depo_db, k.id)[-1][:3] == ("sona_erme", "hibe", -2_000)
    # İptal edilmiş ama hâlâ aktif dönem: `plan_bitis` dönem sonu (Polar `cancel_at_period_end`).
    r = _gonder(c, _yuk("subscription_updated", k, cancel_at_period_end=True, ends_at="2026-10-21T12:00:00Z"))
    assert r.json() == {"durum": "islendi"}
    assert _satir(depo_db, k.id).plan_bitis == dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.UTC)
    # `past_due`: Polar'ın dunning'i — dokunulmaz (K6).
    _hibe(depo_db, k.id, 250)
    r = _gonder(c, _yuk("subscription_updated", k, status="past_due"))
    assert r.json() == {"durum": "islendi"}
    assert _satir(depo_db, k.id).plan == "temel" and _kovalar(depo_db, k.id) == (1_250, 10)
    # Kullanıcının GÜNCEL aboneliği başka: eski aboneliğin geciken olayı planı değiştiremez.
    yuk = _yuk("subscription_updated", k, id="00000000-0000-4000-8000-00000000a0b1")
    r = _gonder(c, yuk)
    assert r.json() == {"durum": "atlandi", "hata": "abonelik_eski"}
    r = _gonder(c, _yuk("subscription_revoked", k, id="00000000-0000-4000-8000-00000000a0b1"))
    assert r.json() == {"durum": "atlandi", "hata": "abonelik_eski"}
    assert _satir(depo_db, k.id).plan == "temel" and _kovalar(depo_db, k.id) == (1_250, 10)


def test_an_update_that_keeps_the_plan_and_a_repeated_revoke_on_a_later_day_do_not_clip_admin_credits(
        c, depo_db, urunler):
    """Düşürme yalnız plan GERÇEKTEN düşünce: aynı plandaki `updated` (iptal bayrağı) ve zaten `free` olan hesaba
    başka gün gelen `revoked` (yeni `sona_erme` anahtarı) admin `duzelt`le verilmiş fazla hibeyi kırpmaz."""
    k = _kullanici(depo_db, plan="temel", abonelik=ABONELIK)
    _hibe(depo_db, k.id, 1_500)   # plan hibesi 1.000 + admin 500
    assert _gonder(c, _yuk("subscription_updated", k, cancel_at_period_end=True,
                            ends_at="2026-10-21T12:00:00Z")).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (1_500, 0) and _satir(depo_db, k.id).plan == "temel"
    # Yükseltme (temel → pro) da kırpmaz; tamamlamayı `order.paid` yapar.
    with Session(depo_db) as s:
        s.add(Urun(polar_urun_id="00000000-0000-4000-8000-00000000e003", tur="plan", plan="pro", kredi=3_000,
                   fiyat_kurus=2_900, para_birimi="usd", ad="Pro"))
        s.commit()
    assert _gonder(c, _yuk("subscription_updated", k, product_id="00000000-0000-4000-8000-00000000e003")).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (1_500, 0) and _satir(depo_db, k.id).plan == "pro"
    # Zaten free: revoke geldi, hibe 1.500 → 200; SONRA admin 300 verdi; başka gün aynı revoke → dokunmaz.
    assert _gonder(c, _yuk("subscription_revoked", k)).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (200, 0) and _satir(depo_db, k.id).plan == "free"
    with Session(depo_db) as s:
        defter.duzelt(s, k.id, 300, "DUMMY destek", admin_id=k.id, an=AN)
        s.commit()
    assert _gonder(c, _yuk("subscription_revoked", k)).json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (500, 0)
    assert [h for h in _hareketler(depo_db, k.id) if h[0] == "sona_erme"].__len__() == 1


def test_customer_events_bind_the_polar_customer_id_and_a_clash_with_another_user_is_reported_not_500(
        c, depo_db):
    k = _kullanici(depo_db)
    b = _kullanici(depo_db, musteri="00000000-0000-4000-8000-00000000d001")
    r = _gonder(c, _yuk("customer_created", k, id="00000000-0000-4000-8000-00000000d002"))
    assert r.json() == {"durum": "islendi"}
    assert _satir(depo_db, k.id).polar_musteri_id == "00000000-0000-4000-8000-00000000d002"
    # Aynı kimlik ikinci kez: dokunmaz, islendi.
    assert _gonder(c, _yuk("customer_updated", k, id="00000000-0000-4000-8000-00000000d002")).json() == {"durum": "islendi"}
    # B'nin kimliği K'ya gelirse: UNIQUE'e çarpıp 500 yerine `musteri_cakisiyor`.
    r = _gonder(c, _yuk("customer_updated", k, id="00000000-0000-4000-8000-00000000d001"))
    assert r.json() == {"durum": "atlandi", "hata": "musteri_cakisiyor"}
    assert _satir(depo_db, k.id).polar_musteri_id == "00000000-0000-4000-8000-00000000d002"
    assert _satir(depo_db, b.id).polar_musteri_id == "00000000-0000-4000-8000-00000000d001"
    # Çözüm üçüncü yol: `external_id` yok, `customer_id` = B'nin müşteri kimliği → B.
    yuk = _yuk("customer_updated", id="00000000-0000-4000-8000-00000000d001")
    yuk["data"]["external_id"] = None
    assert _gonder(c, yuk).json() == {"durum": "islendi"}
    assert [o.kullanici_id for o in _olaylar(depo_db)][-1] == b.id


def test_a_refund_only_warns_and_never_touches_the_ledger(c, depo_db, urunler, gunluk_kaydi):
    """K6: otomatik negatif satır YOK — kullanıcı krediyi harcamış olabilir; iade admin `duzelt` kararı."""
    k = _kullanici(depo_db)
    _paket(depo_db, k.id, 500)
    r = _gonder(c, _yuk("order_refunded", k))
    assert r.json() == {"durum": "islendi"}
    assert _kovalar(depo_db, k.id) == (0, 500) and len(_hareketler(depo_db, k.id)) == 1
    uyari = [a for s, a in gunluk_kaydi.kayitlar if s == logging.WARNING and a.get("olay") == "odeme.iade"]
    assert len(uyari) == 1 and uyari[0]["kullanici_id"] == str(k.id) and uyari[0]["iade_kurus"] == 500
    (o,) = _olaylar(depo_db)
    assert (o.kullanici_id, o.hata) == (k.id, None) and o.islendi_at is not None


@pytest.mark.parametrize("durum, degisiklik, hata", [
    ("kullanici_yok", {}, "kullanici_yok"),
    ("urun_yok", {"product_id": "00000000-0000-4000-8000-00000000e999"}, "urun_yok"),
    ("uyumsuz", {"billing_reason": "subscription_create"}, "urun_sebep_uyumsuz"),
    ("sebep", {"billing_reason": "DUMMY_reason"}, "sebep_bilinmiyor"),
    ("nesne", {"id": ""}, "nesne_yok"),
])
def test_unresolvable_orders_are_recorded_with_an_error_code_and_answered_200(c, depo_db, urunler, durum, degisiklik, hata):
    """Yeniden denemeyle düzelmeyen hâller: 5xx Polar'ı boşuna uğraştırır; satır `hata` ile kalır, admin görür."""
    k = None if durum == "kullanici_yok" else _kullanici(depo_db)
    yuk = _yuk("order_paid_purchase", k, **degisiklik)
    if k is None:
        yuk["data"]["customer"]["external_id"] = str(uuid.uuid4())   # bizde olmayan kullanıcı
    r = _gonder(c, yuk)
    assert (r.status_code, r.json()) == (200, {"durum": "atlandi", "hata": hata}), r.text
    (o,) = _olaylar(depo_db)
    assert o.hata == hata and o.islendi_at is not None and o.kullanici_id == (k.id if k else None)
    assert _siparisler(depo_db) == []
    if k is not None:
        assert _kovalar(depo_db, k.id) == (0, 0)
    # Ürün aynası yazılınca AYNI olayın yeniden gönderimi (yeni webhook-id) işlenir — sahibin `polar_esitle` yolu.
    if durum == "urun_yok":
        with Session(depo_db) as s:
            s.add(Urun(polar_urun_id=degisiklik["product_id"], tur="paket", plan=None, kredi=50, fiyat_kurus=100,
                       para_birimi="usd", ad="50"))
            s.commit()
        assert _gonder(c, yuk).json() == {"durum": "islendi"} and _kovalar(depo_db, k.id) == (0, 50)


def test_a_deleted_account_and_a_metadata_fallback_are_resolved_as_the_document_says(c, depo_db, urunler):
    """`kullaniciyi_coz` sırası: `external_id` → `metadata.kullanici_id` → `polar_musteri_id`; silinmiş hesap çözülmez."""
    k = _kullanici(depo_db)
    yuk = _yuk("order_paid_purchase", metadata={"kullanici_id": str(k.id)})
    yuk["data"]["customer"]["external_id"] = None
    assert _gonder(c, yuk).json() == {"durum": "islendi"} and _kovalar(depo_db, k.id) == (0, 500)
    with Session(depo_db) as s:
        s.execute(text("UPDATE kullanicilar SET silindi_at = now() WHERE id = :k"), {"k": k.id})
        s.commit()
    yuk = _yuk("order_paid_purchase", k, id="00000000-0000-4000-8000-00000000f009")
    assert _gonder(c, yuk).json() == {"durum": "atlandi", "hata": "kullanici_yok"}


def test_the_grant_tour_never_tops_up_paid_plans_anymore_the_webhook_does(depo_db):
    """Faz 4 / 2'nin köprü bayrağı kaldırıldı: bakım turu yalnız `free`; `pro` hesap turdan hibe ALMAZ."""
    assert not hasattr(planlar, "ucretli_hibe_bakimda") and not hasattr(planlar, "UCRETLI_HIBE_BAKIMDA_ENV")
    pro = _kullanici(depo_db, plan="pro")
    free = _kullanici(depo_db)
    with Session(depo_db) as s:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=s):
            defter.hibe_turu(s, AN)
            s.commit()
    assert _kovalar(depo_db, pro.id) == (0, 0)
    assert _kovalar(depo_db, free.id) == (planlar.PLANLAR["free"].aylik_hibe, 0)


# ══════════════════════════════════════════════════════════ (v) admin

def test_the_admin_payment_events_endpoint_lists_deliveries_filters_errors_and_never_dumps_the_body(
        c, depo_db, urunler, kullanici):
    k = _kullanici(depo_db)
    assert _gonder(c, _yuk("order_paid_purchase", k), webhook_id="wh_iyi").json() == {"durum": "islendi"}
    yuk = _yuk("order_paid_purchase", k, product_id="00000000-0000-4000-8000-00000000e999",
               id="00000000-0000-4000-8000-00000000f004")
    assert _gonder(c, yuk, webhook_id="wh_kotu").json()["hata"] == "urun_yok"
    kullanici.is_admin = True
    with depo_db.begin() as b:
        b.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    r = c.get("/api/admin/odeme-olaylari")
    assert r.status_code == 200, r.text
    govde = r.json()
    assert govde["ozet"] == {"olay": 2, "hatali": 1, "siparis": 1}
    assert [o["webhook_id"] for o in govde["olaylar"]] == ["wh_kotu", "wh_iyi"], "en yeni üstte"
    kotu = govde["olaylar"][0]
    assert set(kotu) == {"id", "webhook_id", "tur", "nesne", "kullanici_id", "eposta", "alindi", "islendi_at", "hata"}
    assert (kotu["tur"], kotu["hata"], kotu["eposta"], kotu["kullanici_id"]) == ("order.paid", "urun_yok", k.eposta, str(k.id))
    assert kotu["alindi"] and kotu["islendi_at"] and "govde" not in kotu and "dummy@example.com" not in r.text
    assert [o["hata"] for o in c.get("/api/admin/odeme-olaylari?hata=1").json()["olaylar"]] == ["urun_yok"]
    with Session(depo_db) as s:
        assert depo_admin.odeme_olaylari(s, limit=1)[0]["webhook_id"] == "wh_kotu"
        assert s.scalar(select(func.count()).select_from(OdemeOlayi)) == 2
