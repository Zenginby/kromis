"""Kota — saatlik iş ve günlük kredi tavanı (Faz 2 / 6; docs/faz2-kuyruk-anahtarlar-depolama.md §6, K5).

  (i)   SAATLİK — 61. iş 429 + `Retry-After` (en eski işin pencereden çıkışı) + i18n gövde;
        `iptal` sayılmaz; pencere `zaman.an()` ile kayar; tavan ortamdan, bozuk değer gürültülü;
        BYOK'lu kullanıcıya da uygulanır.
  (ii)  GÜNLÜK — platform işlerinin tahmin toplamı + yeni tahmin > tavan → 429; gövde kalanı ve
        pencerenin açılışını söyler; BYOK sayılmaz; eski (kaynaksız) satır sayılmaz; `iptal`
        sayılmaz; kullanıcı başına ezme (`kullanicilar.gunluk_kredi_tavani`); pencere kayar.
  (iii) SIRA — anahtar (409) → eş zamanlılık → saatlik → günlük; 429 depoya nesne bırakmaz,
        satır yazmaz; yeniden gönderim aynı kapılardan geçer.

Kapı GERÇEK (`gercek_anahtar`) ve platform anahtarı ortamda: bu dosyanın işleri `platform`
kaynaklı doğar; BYOK için kullanıcı kendi anahtarını kaydeder.
"""
from __future__ import annotations

import datetime as dt
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import catalog
import i18n
import providers
from services import kapilar, kota, kuyruk, platform_anahtari, tablolar, zaman

pytestmark = [pytest.mark.usefixtures("depo_db"), pytest.mark.gercek_anahtar]

GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
MODEL_ID = catalog.DEFAULT_IMAGE_MODEL
SPEC = catalog.image_model(MODEL_ID)
assert SPEC is not None
KREDI = catalog.cost_for(SPEC, "medium")          # tek işin tahmini (8)
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def temiz(depo_db):
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
    yield


@pytest.fixture
def c(tmp_path, monkeypatch, dizinler, kullanici):
    """Platform anahtarı ortamda (Azure görsel = varsayılan model), sahte sağlayıcı, işçi koşmaz."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY", "PLATFORM-TEST-ANAHTARI")
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_BASE_URL", "https://p.openai.azure.com/openai/v1/")
    monkeypatch.delenv(kota.SAATLIK_IS_ENV, raising=False)
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV, raising=False)
    monkeypatch.setattr(providers, "generate", lambda m, p, s, q, n, **k: [PNG] * n)
    return TestClient(appmod.app)


def _an(dakika: int = 0) -> dt.datetime:
    return dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC) + dt.timedelta(minutes=dakika)


def _simdi(monkeypatch, t: dt.datetime) -> None:
    """Rotanın ve kotanın "şimdi"si — `zaman.an()` yamalı (kuyruk.ekle de bunu okur)."""
    monkeypatch.setattr(zaman, "an", lambda: t)


def _ek(depo_db, kullanici, *, kac: int = 1, an: dt.datetime, kaynak: str | None = "platform",
        kredi: int = KREDI, durum: str = "bitti") -> list[uuid.UUID]:
    """Doğrudan `isler`e satır — 60 POST yerine (aynı sayaç, aynı sütunlar)."""
    ids = []
    with Session(depo_db) as db:
        for _ in range(kac):
            is_ = kuyruk.ekle(db, kullanici.id, "generate", {"prompt": "x"}, MODEL_ID, kredi, an=an,
                              anahtar_kaynagi=kaynak)
            is_.durum = durum
            ids.append(is_.id)
        db.commit()
    return ids


def _isler(depo_db) -> list[tablolar.Is]:
    with Session(depo_db) as db:
        return list(db.scalars(select(tablolar.Is)))


def _cumle(anahtar: str, **alanlar) -> set[str]:
    return {i18n.t(anahtar, d, **alanlar) for d in ("tr", "en")}


# ── (i) saatlik ─────────────────────────────────────────────────────────

def test_the_61st_job_in_an_hour_is_429_with_retry_after_and_an_i18n_body(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    _ek(depo_db, kullanici, kac=59, an=_an(-30))
    _ek(depo_db, kullanici, kac=1, an=_an(-50))           # en eski: 50 dk önce
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429, r.text
    # En eski iş 10 dk sonra pencereden çıkar: 600 (+1 yuvarlama).
    assert r.headers["Retry-After"] == "601"
    assert r.json()["detail"] in _cumle("err.saatlik_is_tavani", tavan=60, dakika=11)
    assert "60" in r.json()["detail"] and r.json()["detail"] != "err.saatlik_is_tavani"
    assert len(_isler(depo_db)) == 60, "429 satır yazmaz"


def test_the_60th_job_passes_and_cancelled_jobs_do_not_count(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    _ek(depo_db, kullanici, kac=59, an=_an(-30))
    assert c.post("/api/generate", json=GORSEL).status_code == 202       # 60.
    assert c.post("/api/generate", json=GORSEL).status_code == 429       # 61.
    _ek(depo_db, kullanici, kac=3, an=_an(-20), durum="iptal")
    assert c.post("/api/generate", json=GORSEL).status_code == 429, "iptal sayılmıyor, sayı hâlâ 60"
    with Session(depo_db) as db:
        is_ = db.scalars(select(tablolar.Is).where(tablolar.Is.durum == "bitti")).first()
        assert is_ is not None
        is_.durum = "iptal"
        db.commit()
    assert c.post("/api/generate", json=GORSEL).status_code == 202, "biri iptal → 59 → geçer"


def test_the_hourly_window_slides_with_zaman_an(c, depo_db, kullanici, monkeypatch):
    _ek(depo_db, kullanici, kac=60, an=_an(-59))
    _simdi(monkeypatch, _an(0))
    assert c.post("/api/generate", json=GORSEL).status_code == 429
    _simdi(monkeypatch, _an(2))                                          # 61 dk geçti
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert kota.saatlik_bekleme(Session(depo_db), kullanici.id, _an(-58)) == 3541  # 59 dk - 1 dk = 58 dk + 1


def test_the_hourly_cap_comes_from_the_environment_and_a_bad_value_is_loud(c, monkeypatch):
    monkeypatch.setenv(kota.SAATLIK_IS_ENV, "2")
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and "2" in r.json()["detail"]
    assert kota.saatlik_is_tavani({}) == 60 and kota.saatlik_is_tavani({kota.SAATLIK_IS_ENV: " 7 "}) == 7
    assert kota.gunluk_kredi_tavani({}) == 2000 and kota.gunluk_kredi_tavani({kota.GUNLUK_KREDI_ENV: "10"}) == 10
    for ad, fn in ((kota.SAATLIK_IS_ENV, kota.saatlik_is_tavani), (kota.GUNLUK_KREDI_ENV, kota.gunluk_kredi_tavani)):
        with pytest.raises(ValueError, match=ad):
            fn({ad: "cok"})
        with pytest.raises(ValueError, match=ad):
            fn({ad: "0"})


def test_the_hourly_cap_applies_to_byok_users_too_and_counts_only_this_user(c, depo_db, kullanici, monkeypatch):
    """K5: BYOK'lu kullanıcı da işçiyi meşgul ediyor — kendi anahtarıyla koşan işler sayılır;
    başkasının dolu saati beni etkilemez."""
    _simdi(monkeypatch, _an(0))
    c.post("/api/settings", json={"api_key": "KENDI", "base_url": "https://k.openai.azure.com/openai/v1/"})
    _ek(depo_db, kullanici, kac=60, an=_an(-10), kaynak="kullanici")
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and r.json()["detail"] in _cumle("err.saatlik_is_tavani", tavan=60, dakika=51)
    # Başka kullanıcının 60 işi: bu kullanıcıya dokunmaz.
    with Session(depo_db) as db:
        db.execute(text("DELETE FROM isler"))
        baska = tablolar.Kullanici(eposta="baska@example.com", parola_ozeti=None)
        db.add(baska)
        db.flush()
        for _ in range(60):
            kuyruk.ekle(db, baska.id, "generate", {}, MODEL_ID, KREDI, an=_an(-10), anahtar_kaynagi="platform")
        db.commit()
    assert c.post("/api/generate", json=GORSEL).status_code == 202


# ── (ii) günlük ─────────────────────────────────────────────────────────

def test_the_2001st_credit_is_429_and_the_body_tells_the_remaining_credits_and_the_window_end(
        c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    # 1.992 kredi platformla harcanmış: en eskisi 20 saat önce (249 × 8).
    _ek(depo_db, kullanici, kac=1, an=_an(-20 * 60), kredi=KREDI)
    _ek(depo_db, kullanici, kac=1, an=_an(-60), kredi=1992 - KREDI)
    assert c.post("/api/generate", json=GORSEL).status_code == 202, "1992 + 8 = 2000: tavana EŞİT geçer"
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429, r.text
    acilis = zaman.damga(_an(-20 * 60) + kota.GUNLUK_PENCERE)            # en eski iş 4 saat sonra düşer
    assert r.json()["detail"] in _cumle("err.gunluk_kredi_tavani", tavan=2000, kalan=0, tahmin=KREDI,
                                        saat=acilis[11:16], tarih=acilis[:10])
    assert r.headers["Retry-After"] == str(4 * 3600 + 1)
    assert "2000" in r.json()["detail"] and str(KREDI) in r.json()["detail"]
    assert len(_isler(depo_db)) == 3, "429 satır yazmaz"


def test_the_remaining_credits_are_reported_when_the_new_job_does_not_fit(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=1995)
    r = c.post("/api/generate", json=GORSEL)                             # 1995 + 8 > 2000
    assert r.status_code == 429
    assert r.json()["detail"] in _cumle("err.gunluk_kredi_tavani", tavan=2000, kalan=5, tahmin=KREDI,
                                        saat=zaman.damga(_an(-30) + kota.GUNLUK_PENCERE)[11:16],
                                        tarih=zaman.damga(_an(-30) + kota.GUNLUK_PENCERE)[:10])
    # Daha küçük bir iş (low = 4 kredi) hâlâ sığar — kota "kalan"ı gerçekten söylüyor.
    assert c.post("/api/generate", json={**GORSEL, "quality": "low"}).status_code == 202


def test_byok_jobs_and_legacy_rows_and_cancelled_jobs_do_not_count_toward_the_daily_credits(
        c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=5000, kaynak="kullanici")   # kendi parası
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=5000, kaynak=None)          # 0005 öncesi satır
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=5000, durum="iptal")       # hiç koşmadı
    assert kota.gunluk_durum(Session(depo_db), kullanici.id, _an(0)) == (0, None)
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    # `hata`yla kapanan platform işi SAYILIR (sağlayıcı faturalamış olabilir).
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=1990, durum="hata")
    assert c.post("/api/generate", json=GORSEL).status_code == 429


def test_a_byok_user_is_never_stopped_by_the_daily_cap(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    _ek(depo_db, kullanici, kac=1, an=_an(-30), kredi=2000)                       # platform tavanı dolu
    assert c.post("/api/generate", json=GORSEL).status_code == 429
    c.post("/api/settings", json={"api_key": "KENDI", "base_url": "https://k.openai.azure.com/openai/v1/"})
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 202 and r.json()["is"]["anahtar_kaynagi"] == "kullanici"


def test_the_per_user_override_replaces_the_default_cap(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    with Session(depo_db) as db:
        db.execute(text("UPDATE kullanicilar SET gunluk_kredi_tavani = :t WHERE id = :id"),
                   {"t": 2 * KREDI, "id": kullanici.id})
        db.commit()
    kullanici.gunluk_kredi_tavani = 2 * KREDI      # override'ın taşıdığı nesne; rota bunu okur
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and str(2 * KREDI) in r.json()["detail"] and "2000" not in r.json()["detail"]
    kullanici.gunluk_kredi_tavani = None
    assert c.post("/api/generate", json=GORSEL).status_code == 202, "NULL = ortamın öntanımlısı (2000)"


def test_the_daily_window_slides_with_zaman_an(c, depo_db, kullanici, monkeypatch):
    _ek(depo_db, kullanici, kac=1, an=_an(-23 * 60), kredi=2000)
    _simdi(monkeypatch, _an(0))
    assert c.post("/api/generate", json=GORSEL).status_code == 429
    _simdi(monkeypatch, _an(61))                                         # 24 sa 1 dk geçti
    assert c.post("/api/generate", json=GORSEL).status_code == 202


# ── (iii) sıra ve yan etkiler ───────────────────────────────────────────

def test_the_gate_order_is_key_then_concurrency_then_hourly_then_daily(c, depo_db, kullanici, monkeypatch, tmp_path):
    _simdi(monkeypatch, _an(0))
    # Saatlik VE günlük dolu, eş zamanlılık da dolu (4 aktif): cümle eş zamanlılığın.
    _ek(depo_db, kullanici, kac=4, an=_an(-10), kredi=500, durum="bekliyor")
    _ek(depo_db, kullanici, kac=56, an=_an(-10), kredi=1)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and r.json()["detail"] in _cumle("err.is_kuyrugu_dolu", tavan=4)
    assert r.headers["Retry-After"] == str(kapilar.RETRY_AFTER_SN)
    # Aktifler bitti: saatlik dolu (60) ve günlük dolu (2000+) → cümle saatliğin.
    with Session(depo_db) as db:
        db.execute(text("UPDATE isler SET durum = 'bitti'"))
        db.commit()
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and r.json()["detail"] in _cumle("err.saatlik_is_tavani", tavan=60, dakika=51)
    # Saatlik açıldı (pencere kaydı), günlük hâlâ dolu → cümle günlüğün.
    _simdi(monkeypatch, _an(55))
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429 and "2000" in r.json()["detail"]
    # Anahtar yokken her şey dolu olsa da cevap 409 — kotaya hiç varılmaz, iş doğmaz.
    monkeypatch.delenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY")
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 409 and "Retry-After" not in r.headers
    assert len(_isler(depo_db)) == 60


def test_a_quota_429_writes_no_object_and_no_row_on_the_multipart_route(c, depo_db, kullanici, monkeypatch, tmp_path):
    _simdi(monkeypatch, _an(0))
    monkeypatch.setenv(kota.SAATLIK_IS_ENV, "1")
    _ek(depo_db, kullanici, kac=1, an=_an(-5))
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("a.png", _png(), "image/png")})
    assert r.status_code == 429, r.text
    assert not any((tmp_path / "kullanicilar").rglob("isler/*/*")), "429 depoya nesne bırakmaz"
    assert len(_isler(depo_db)) == 1


def test_the_resubmit_route_passes_through_the_same_gates(c, depo_db, kullanici, monkeypatch):
    _simdi(monkeypatch, _an(0))
    (eski,) = _ek(depo_db, kullanici, kac=1, an=_an(-30), durum="hata")
    monkeypatch.setenv(kota.SAATLIK_IS_ENV, "1")
    r = c.post(f"/api/isler/{eski}/yeniden")
    assert r.status_code == 429 and r.json()["detail"] in _cumle("err.saatlik_is_tavani", tavan=1, dakika=31)
    monkeypatch.delenv(kota.SAATLIK_IS_ENV)
    _ek(depo_db, kullanici, kac=1, an=_an(-10), kredi=1999)
    r = c.post(f"/api/isler/{eski}/yeniden")
    assert r.status_code == 429 and "1999" not in r.json()["detail"] and "2000" in r.json()["detail"]
    monkeypatch.delenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY")
    assert c.post(f"/api/isler/{eski}/yeniden").status_code == 409
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY", "PLATFORM-TEST-ANAHTARI")
    with Session(depo_db) as db:
        db.execute(text("DELETE FROM isler WHERE kredi_tahmini = 1999"))
        db.commit()
    r = c.post(f"/api/isler/{eski}/yeniden")
    assert r.status_code == 202 and r.json()["is"]["anahtar_kaynagi"] == "platform"
