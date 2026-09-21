"""`GET /api/kredi` — kredi ön yüzünün tek kaynağı (Faz 3 / 6; docs/faz3-kredi-defteri-filigran.md §6).

Gerçek Postgres (`depo_db`): bakiye ve hareketler defterden okunur, RLS
politikaları ve kullanıcı süzgeci birlikte ölçülür. Sekiz soru:
  (i)   ALANLAR — `{bakiye, paket_bakiye, toplam, plan, plan_bitis, hibe, sonraki_hibe, filigran, video,
        son_hareketler}`, fazlası yok; plan kuralları `PLANLAR`dan (arayüz kataloğu tekrar etmez).
        Faz 4 / 2: `bakiye` HİBE kovası olarak kalır, `paket_bakiye` ikinci kova, `toplam` ikisi;
        `plan_bitis` iptal edilmiş aboneliğin dönem sonu (3. görev yazar, bugün null).
  (ii)  SONRAKİ HİBE — gelecek ayın ilk günü, `aylik_hibe_yaz`ın `%Y-%m` anahtarıyla
        AYNI takvimde (`zaman.an()`ın dilimi), `damga_utc` biçiminde; yıl devri.
  (iii) SINIR — en yeni üstte, en çok 20 (`KREDI_HAREKET_SINIRI`).
  (iv)  DÖKÜM — hareket satırı `defter._json`: iç alanlar (`admin_id`,
        `idempotency_anahtari`) yok, damga `Z`.
  (v)   BAŞKASININ HAREKETİ GÖRÜNMEZ — depo süzgeci (RLS ikinci kapı, tests/test_rls.py).
  (vi)  PLAN — `pro` kullanıcı kendi kurallarını görür (filigran yok, video açık, hibe 3.000).
  (vii) REZERV — sırada bekleyen işin rezervi eksi satır, bakiye düşmüş.
  (viii) MODEL `kaynak` — `/api/settings` her görsel/video modelinde kimin anahtarıyla
        koşacağını söyler; composer "kendi anahtarın · düşmez" satırı bundan okur.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import app as appmod
import catalog
import credstore
from routers import isler as isler_rotasi
from services import defter, hesap, kuyruk, planlar, platform_anahtari, tablolar, zaman
from services.tablolar import Kullanici

pytestmark = pytest.mark.usefixtures("depo_db")

AN = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
ALANLAR = {"bakiye", "paket_bakiye", "toplam", "plan", "plan_bitis", "hibe", "sonraki_hibe", "filigran", "video",
           "son_hareketler"}
HAREKET_ALANLARI = {"id", "tur", "kova", "miktar", "aciklama", "is_id", "olusturuldu"}


@pytest.fixture(autouse=True)
def temiz(depo_db):
    """Dosya aynı DB'yi paylaşır; ikinci kullanıcılar ve işler her testte temizlenir
    (test kullanıcısını conftest yeniler — CASCADE defterini götürür)."""
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
    yield


@pytest.fixture
def c(dizinler):
    dizinler()
    return TestClient(appmod.app)


def _hibe(depo_db, kid: uuid.UUID, miktar: int, an: dt.datetime = AN, anahtar: str | None = None) -> None:
    with Session(depo_db) as s:
        defter.hibe(s, kid, miktar, anahtar or f"{defter.ONEK_HIBE}{kid}:{an:%Y-%m}", an=an)
        s.commit()


def _ikinci(depo_db) -> Kullanici:
    with Session(depo_db, expire_on_commit=False) as s:
        k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                      dogrulandi_at=hesap.simdi(), dil=None)
        s.add(k)
        s.commit()
        return k


# ───────────────────────────────────────────────────────────── (i) alanlar

def test_the_credit_endpoint_reports_balance_plan_grant_and_rules_for_a_free_user(c, depo_db, kullanici):
    _hibe(depo_db, kullanici.id, 200)
    r = c.get("/api/kredi")
    assert r.status_code == 200
    govde = r.json()
    assert set(govde) == ALANLAR
    ucretsiz = planlar.PLANLAR["free"]
    assert govde["bakiye"] == 200 and govde["plan"] == "free"
    assert (govde["paket_bakiye"], govde["toplam"], govde["plan_bitis"]) == (0, 200, None)
    assert govde["hibe"] == ucretsiz.aylik_hibe
    assert govde["filigran"] is ucretsiz.filigran is True
    assert govde["video"] is ucretsiz.video is False
    assert [h["tur"] for h in govde["son_hareketler"]] == ["hibe"]
    assert govde["son_hareketler"][0]["miktar"] == 200


def test_a_user_with_no_ledger_yet_gets_zero_and_an_empty_list(c):
    govde = c.get("/api/kredi").json()
    assert govde["bakiye"] == 0 and govde["son_hareketler"] == []
    assert (govde["paket_bakiye"], govde["toplam"]) == (0, 0)


# ─────────────────────────────────────────────────────── (ii) sonraki hibe

@pytest.mark.parametrize("an, beklenen", [
    (dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC), "2026-10-01T00:00:00Z"),
    (dt.datetime(2026, 12, 31, 23, 59, tzinfo=dt.UTC), "2027-01-01T00:00:00Z"),
    # Yerel dilim: hibe anahtarı `an`ın KENDİ takviminden (`%Y-%m`), UTC'den değil —
    # 30 Eylül 23:30 (+03) → Ekim'in ilk günü +03'te, UTC'de 30 Eylül 21:00.
    (dt.datetime(2026, 9, 30, 23, 30, tzinfo=dt.timezone(dt.timedelta(hours=3))), "2026-09-30T21:00:00Z"),
])
def test_the_next_grant_is_the_first_of_next_month_in_the_grant_keys_own_calendar(c, monkeypatch, an, beklenen):
    monkeypatch.setattr(zaman, "an", lambda: an)
    assert c.get("/api/kredi").json()["sonraki_hibe"] == beklenen
    assert isler_rotasi._sonraki_ay_basi(an).strftime("%Y-%m") != f"{an:%Y-%m}", "bir sonraki AY olmalı"


# ──────────────────────────────────────────────────────────── (iii) sınır

def test_the_movement_list_is_newest_first_and_capped_at_twenty(c, depo_db, kullanici):
    for i in range(25):
        _hibe(depo_db, kullanici.id, 1, an=AN + dt.timedelta(minutes=i), anahtar=f"{defter.ONEK_HIBE}{kullanici.id}:t{i}")
    govde = c.get("/api/kredi").json()
    assert govde["bakiye"] == 25
    assert len(govde["son_hareketler"]) == isler_rotasi.KREDI_HAREKET_SINIRI == 20
    damgalar = [h["olusturuldu"] for h in govde["son_hareketler"]]
    assert damgalar == sorted(damgalar, reverse=True), "en yeni üstte"
    assert damgalar[0] == zaman.damga_utc(AN + dt.timedelta(minutes=24))
    with Session(depo_db) as s:
        beklenen = [str(h.id) for h in defter.hareketler(s, kullanici.id, limit=20)]
    assert [h["id"] for h in govde["son_hareketler"]] == beklenen, "`defter.hareketler` ile aynı sıra"


# ──────────────────────────────────────────────────────────── (iv) döküm

def test_a_movement_row_exposes_only_the_public_fields(c, depo_db, kullanici):
    with Session(depo_db) as s:
        defter.duzelt(s, kullanici.id, 15, "test düzeltmesi", kullanici.id, an=AN)
        s.commit()
    satir = c.get("/api/kredi").json()["son_hareketler"][0]
    assert set(satir) == HAREKET_ALANLARI, "admin_id / idempotency_anahtari dökülmez"
    assert satir["tur"] == "duzeltme" and satir["miktar"] == 15 and satir["aciklama"] == "test düzeltmesi"
    assert satir["kova"] == "hibe"
    assert satir["is_id"] is None
    assert satir["olusturuldu"] == zaman.damga_utc(AN) and satir["olusturuldu"].endswith("Z")
    uuid.UUID(satir["id"])


# ─────────────────────────────────────────────── (v) başkasının hareketi

def test_another_users_movements_and_balance_are_invisible(c, depo_db, kullanici):
    baska = _ikinci(depo_db)
    _hibe(depo_db, baska.id, 500)
    _hibe(depo_db, kullanici.id, 7)
    govde = c.get("/api/kredi").json()
    assert govde["bakiye"] == 7
    assert [h["miktar"] for h in govde["son_hareketler"]] == [7]


# ──────────────────────────────────────────────────────────────── (vi) plan

def test_a_pro_user_sees_the_rules_of_the_pro_plan(c, plan_pro):
    govde = c.get("/api/kredi").json()
    pro = planlar.PLANLAR["pro"]
    assert govde["plan"] == "pro" and govde["hibe"] == pro.aylik_hibe == 3_000
    assert govde["filigran"] is False and govde["video"] is True


# ───────────────────────────────────────────────────────────── (vii) rezerv

def test_a_reserved_job_shows_as_a_negative_reserve_row_linked_to_the_job(c, depo_db, kullanici):
    _hibe(depo_db, kullanici.id, 100)
    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert spec is not None
    tahmin = catalog.cost_for(spec, "medium")
    with Session(depo_db) as s:
        is_ = kuyruk.ekle(s, kullanici.id, "generate", {"prompt": "x"}, spec.id, tahmin,
                          an=AN + dt.timedelta(minutes=1), anahtar_kaynagi="platform")
        defter.rezerve(s, kullanici.id, is_.id, tahmin, an=AN + dt.timedelta(minutes=1))
        s.commit()
        is_id = str(is_.id)
    govde = c.get("/api/kredi").json()
    assert govde["bakiye"] == 100 - tahmin
    rezerv = govde["son_hareketler"][0]
    assert rezerv["tur"] == "rezerv" and rezerv["miktar"] == -tahmin and rezerv["is_id"] == is_id


# ───────────────────────────────────────────────────────── (ix) iki kova (Faz 4 / 2)

def test_the_two_buckets_and_the_total_are_reported_and_each_movement_names_its_bucket(c, depo_db, kullanici):
    """K3: `bakiye` hibe kovası, `paket_bakiye` paket kovası, `toplam` ikisi; rezerv hibeyi tüketip pakete geçince
    iki `rezerv` satırı (`kova` alanı ayırır); `plan_bitis` sütun doluysa `damga_utc` biçiminde döner."""
    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert spec is not None
    tahmin = catalog.cost_for(spec, "medium")
    hibe = tahmin - 1                       # hibe yetmez, kalan 1 kredi paketten: iki kova da oynar
    assert hibe > 0, "tarife en az 2 kredi olmalı ki bölüşüm görülsün"
    _hibe(depo_db, kullanici.id, hibe)
    with Session(depo_db) as s:
        assert defter.paket_yukle(s, kullanici.id, 500, "paket:ord_test", an=AN) is True
        is_ = kuyruk.ekle(s, kullanici.id, "generate", {"prompt": "x"}, spec.id, tahmin,
                          an=AN + dt.timedelta(minutes=1), anahtar_kaynagi="platform")
        defter.rezerve(s, kullanici.id, is_.id, tahmin, an=AN + dt.timedelta(minutes=1))
        s.execute(text("UPDATE kullanicilar SET plan_bitis = :t WHERE id = :k"),
                  {"t": dt.datetime(2026, 11, 12, tzinfo=dt.UTC), "k": kullanici.id})
        s.commit()
    govde = c.get("/api/kredi").json()
    assert (govde["bakiye"], govde["paket_bakiye"], govde["toplam"]) == (0, 499, 499)
    assert govde["plan_bitis"] == "2026-11-12T00:00:00Z"
    kovali = [(h["tur"], h["kova"], h["miktar"]) for h in govde["son_hareketler"]]
    assert set(kovali[:2]) == {("rezerv", "hibe", -hibe), ("rezerv", "paket", -1)}, kovali
    assert ("paket", "paket", 500) in kovali and ("hibe", "hibe", hibe) in kovali


# ──────────────────────────────────────────────────────── (viii) model kaynağı

def test_every_model_payload_says_whose_key_it_runs_on(c, monkeypatch):
    """`kaynak`: `kullanici` | `platform` | None — `kaynaklar` sözlüğünün model başına izdüşümü
    (services/modeller.py). Sunucu söyler; istemci sağlayıcı → kimlik eşlemesini bilmiyor."""
    monkeypatch.setattr(credstore, "configured_map", lambda *a, **k: {c_.id: True for c_ in catalog.CREDENTIALS})
    monkeypatch.setattr(platform_anahtari, "kaynak", lambda cred_id, kimlikler: "platform")
    govde = c.get("/api/settings").json()
    modeller = govde["image_models"] + govde["video_models"]
    assert modeller and all(m["kaynak"] == "platform" for m in modeller)
    assert all(v == "platform" for v in govde["kaynaklar"].values())
    monkeypatch.setattr(credstore, "configured_map", lambda *a, **k: {})
    govde = c.get("/api/settings").json()
    assert all(m["kaynak"] is None for m in govde["image_models"] + govde["video_models"]), "kurulu değil → None"
    assert "kaynak" not in govde["chat_models"][0], "sohbet modeli rezerv etmez, alanı yok"


def test_the_ledger_types_the_pane_labels_cover_the_schema_set():
    """settings.js `KREDI_HAREKET_ANAHTARI` tablosu `HAREKET_TURLERI`nin her türünü çevirir —
    tanınmayan tür `düzeltme` etiketine düşer, sessiz kalmaz ama yanlış da olmaz."""
    import os
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "static", "settings.js"), encoding="utf-8") as f:
        js = f.read()
    for tur in tablolar.HAREKET_TURLERI:
        assert f'{tur}: "kredi.tur_{tur}"' in js, tur
