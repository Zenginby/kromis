"""Üretim rotalarında kredi kapısı — rezerv, 402 ve BYOK (Faz 3 / 2; docs/faz3-kredi-defteri-filigran.md §2).

Sağlayıcı YAMALI, kuyruk ve defter GERÇEK Postgres (`depo_db`), anahtar kapısı
yamalı ama bu dosyada `platform` der (conftest'in `kullanici` yamasının üstüne
`c` fixture'ı yeniden yamalar): işler platform anahtarıyla doğar ve defteri
GÖRÜR. Bakiye yalnız `defter.hibe` ile yazılır (tek yazar; tests/test_defter.py
AST bekçisi). Beş soru:

  (i)   REZERV — platform işi 202 ve bakiye tahmin kadar düşer, `rezerv:<is_id>`
        satırı; dört rota da; bakiye tahmine EŞİTKEN geçer (>=); resubmit yeni rezerv.
  (ii)  BYOK — `kullanici` kaynaklı iş bakiyeye dokunmaz, defter satırı yok (K3).
  (iii) 402 — gövde `{"kod": "err.kredi_yetersiz", "bakiye", "gereken", "plan", "hibe", "paket"}` (K11;
        Faz 4 / 2: `bakiye` iki kovanın toplamı, `hibe`/`paket` kovalar);
        iş satırı YOK, bakiye değişmez, multipart uçta girdi nesnesi de yok; i18n
        cümlesi üç alanı taşır; resubmit de 402.
  (iv)  SIRA — günlük tavan (429) bakiye kapısından ÖNCE: tavan aşımında bakiye
        hiç sorulmaz, dokunulmaz (K9).
  (v)   ASIL KAPI — ön denetim atlansa bile `rezerve_kredi`nin atomik düşümü 402
        der ve satır geri alınır (yarışın kaybedeni).

Kullanıcı `pro` (conftest `plan_pro`, Faz 3 / 3): dört rotanın parametrik testi
videoyu da sürer ve ücretsiz planda video 403 — bu dosya bakiye kapısını ölçer,
plan kapısı tests/test_planlar.py'de. 402 gövdesinin `plan` alanı o yüzden `pro`.
"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app as appmod
import azure_client as ac
import catalog
import i18n
import providers
from services import defter, isci, kapilar, kota, tablolar

# `plan_pro` (Faz 3 / 3): dört rotanın parametrik testi videoyu da sürer; plan kapısı tests/test_planlar.py'de.
pytestmark = pytest.mark.usefixtures("depo_db", "plan_pro")

GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
VIDEO = {"prompt": "kedi kosuyor", "size": "16:9", "quality": "720p", "duration": 4}
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
MP4 = b"\x00\x00\x00\x20ftypmp42"
SPEC = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
assert SPEC is not None
KREDI = catalog.cost_for(SPEC, "medium")          # tek görselin tahmini — KATALOGDAN
VIDEO_SPEC = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)
assert VIDEO_SPEC is not None
VIDEO_KREDI = catalog.cost_for(VIDEO_SPEC, "720p", duration=4)


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
    """Sahte sağlayıcı, işçi koşmaz; anahtar kapısı `platform` der (conftest'in `kullanici` yamasını EZER)."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV, raising=False)
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "platform")
    monkeypatch.setattr(providers, "generate", lambda m, p, s, q, n, **k: [PNG] * n)
    monkeypatch.setattr(providers, "edit", lambda m, p, r, s, q, n, **k: [PNG] * n)
    monkeypatch.setattr(providers, "generate_video", lambda *a, **k: [MP4])
    monkeypatch.setattr(providers, "animate_video", lambda *a, **k: [MP4])
    return TestClient(appmod.app)


def _yukle(depo_db, kullanici_id: uuid.UUID, miktar: int, ay: str = "2026-09") -> None:
    """Bakiye yalnız defter üzerinden (`hibe`); anahtar `hibe:<u>:<YYYY-MM>` sözleşmesinde."""
    with Session(depo_db) as db:
        assert defter.hibe(db, kullanici_id, miktar, f"{defter.ONEK_HIBE}{kullanici_id}:{ay}")
        db.commit()


def _bakiye(depo_db, kullanici_id: uuid.UUID) -> int:
    """İki kovanın toplamı — bu dosyada paket kovası boş, toplam = hibe (Faz 4 / 2)."""
    with Session(depo_db) as db:
        return defter.bakiye(db, kullanici_id).toplam


def _hareketler(depo_db, kullanici_id: uuid.UUID) -> list[tuple[str, int, str | None]]:
    """`(tur, miktar, is_id)` — hibe hariç, eskiden yeniye."""
    with Session(depo_db) as db:
        return [(h.tur, h.miktar, str(h.is_id) if h.is_id else None)
                for h in defter.hareketler(db, kullanici_id)[::-1] if h.tur != defter.TUR_HIBE]


def _isler(depo_db) -> list[tablolar.Is]:
    with Session(depo_db) as db:
        return list(db.scalars(select(tablolar.Is)))


def _tek_tur(depo_db) -> bool:
    with Session(depo_db) as db:
        return isci.tek_tur(db, appmod.app.state.dosya, ayarlar=appmod.app.state.ayarlar)


def _cumle(anahtar: str, **alanlar) -> set[str]:
    return {i18n.t(anahtar, d, **alanlar) for d in ("tr", "en")}


# ── (i) rezerv ──────────────────────────────────────────────────────────

def test_a_platform_job_reserves_its_estimate_and_the_balance_drops(c, depo_db, kullanici):
    _yukle(depo_db, kullanici.id, 100)
    r = c.post("/api/generate", json={**GORSEL, "n": 2})
    assert r.status_code == 202, r.text
    is_ = r.json()["is"]
    assert is_["anahtar_kaynagi"] == "platform" and is_["kredi_tahmini"] == 2 * KREDI
    assert _bakiye(depo_db, kullanici.id) == 100 - 2 * KREDI
    assert _hareketler(depo_db, kullanici.id) == [(defter.TUR_REZERV, -2 * KREDI, is_["id"])]


@pytest.mark.parametrize("yol, istek, tahmin", [
    ("/api/generate", {"json": GORSEL}, KREDI),
    ("/api/video", {"json": VIDEO}, VIDEO_KREDI),
    ("/api/edit", {"data": {"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
                   "files": {"file": ("a.png", _png(), "image/png")}}, catalog.cost_for(SPEC, "low")),
    ("/api/video/animate", {"data": VIDEO, "files": {"file": ("a.png", _png(), "image/png")}}, VIDEO_KREDI),
])
def test_all_four_production_routes_reserve_in_the_same_transaction_as_the_row(c, depo_db, kullanici,
                                                                              yol, istek, tahmin):
    _yukle(depo_db, kullanici.id, 1000)
    r = c.post(yol, **istek)
    assert r.status_code == 202, r.text
    is_ = r.json()["is"]
    assert is_["kredi_tahmini"] == tahmin
    assert _bakiye(depo_db, kullanici.id) == 1000 - tahmin
    (satir,) = _isler(depo_db)
    assert str(satir.id) == is_["id"]
    assert _hareketler(depo_db, kullanici.id) == [(defter.TUR_REZERV, -tahmin, is_["id"])], "rezerv satırı işin id'sini taşır"


def test_a_balance_exactly_equal_to_the_estimate_passes_and_lands_on_zero(c, depo_db, kullanici):
    _yukle(depo_db, kullanici.id, KREDI)
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert _bakiye(depo_db, kullanici.id) == 0
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 402 and r.json()["detail"]["bakiye"] == 0


def test_resubmitting_a_failed_job_reserves_anew_because_the_old_ledger_is_closed(c, depo_db, kullanici, monkeypatch):
    _yukle(depo_db, kullanici.id, 100)

    def bozuk(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "generate", bozuk)
    eski = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db)
    assert c.get(f"/api/isler/{eski}").json()["is"]["durum"] == "hata"
    assert _bakiye(depo_db, kullanici.id) == 100, "hata → tam iade"

    r = c.post(f"/api/isler/{eski}/yeniden")
    assert r.status_code == 202, r.text
    yeni = r.json()["is"]["id"]
    assert _bakiye(depo_db, kullanici.id) == 100 - KREDI, "yeni iş = yeni rezerv"
    assert _hareketler(depo_db, kullanici.id) == [(defter.TUR_REZERV, -KREDI, eski), (defter.TUR_IADE, KREDI, eski),
                                                  (defter.TUR_REZERV, -KREDI, yeni)]


# ── (ii) BYOK ───────────────────────────────────────────────────────────

def test_a_byok_job_never_touches_the_ledger(c, depo_db, kullanici, monkeypatch):
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "kullanici")
    _yukle(depo_db, kullanici.id, 100)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 202 and r.json()["is"]["anahtar_kaynagi"] == "kullanici"
    assert _bakiye(depo_db, kullanici.id) == 100 and _hareketler(depo_db, kullanici.id) == []
    # Bakiye SIFIRKEN de: BYOK kullanıcı 402 görmez (K3 — kendi parası).
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "kullanici")
    with Session(depo_db) as db:
        db.execute(text("DELETE FROM isler"))
        db.commit()
    r = c.post("/api/generate", json={**GORSEL, "n": 4})
    assert r.status_code == 202, r.text


# ── (iii) 402 ───────────────────────────────────────────────────────────

def test_an_insufficient_balance_is_402_with_the_three_fields_and_writes_no_row(c, depo_db, kullanici):
    _yukle(depo_db, kullanici.id, KREDI - 1)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 402, r.text
    assert r.json() == {"detail": {"kod": "err.kredi_yetersiz", "bakiye": KREDI - 1, "gereken": KREDI,
                                   "plan": "pro", "hibe": KREDI - 1, "paket": 0}}
    assert "Retry-After" not in r.headers, "402 kota değil: beklemek para getirmez (K11)"
    assert _isler(depo_db) == [], "402'de iş satırı YOK: rezerv satırla aynı transaksiyonda geri alındı"
    assert _bakiye(depo_db, kullanici.id) == KREDI - 1 and _hareketler(depo_db, kullanici.id) == []


def test_a_402_on_the_multipart_route_leaves_no_row_and_no_input_object(c, depo_db, kullanici, tmp_path):
    # Bakiye işin maliyetinin BİR ALTINDA — sıfır DEĞİL: boş cüzdanın ayrı bir
    # dalı kapıyı gizleyebilir, yetersizlik dolu cüzdanla ölçülmeli. Sabit 1
    # yazılıydı ve low 4 iken yetersizdi; 2026-09-22 ölçümüyle low 1 olunca hem
    # YETER hâle geldi hem de "bir altı" 0'a indi (hibe pozitif olmak zorunda).
    # Kademe bu yüzden medium: sayı katalogdan gelir, tarife yine değişse de tutar.
    _yukle(depo_db, kullanici.id, catalog.cost_for(SPEC, "medium") - 1)
    r = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "medium", "n": "1"},
               files={"file": ("a.png", _png(), "image/png")})
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["gereken"] == catalog.cost_for(SPEC, "medium")
    assert not any((tmp_path / "kullanicilar").rglob("isler/*/*")), "ön denetim girdi nesnesinden ÖNCE: 402 depoya nesne bırakmaz"
    assert _isler(depo_db) == []


def test_the_402_sentence_carries_the_balance_and_the_need_in_both_languages():
    for d in ("tr", "en"):
        cumle = i18n.t("err.kredi_yetersiz", d, bakiye=3, gereken=8, plan="free")
        assert "3" in cumle and "8" in cumle and "{" not in cumle, cumle
    assert len(_cumle("err.kredi_yetersiz", bakiye=3, gereken=8, plan="free")) == 2


def test_resubmit_is_402_too_when_the_balance_ran_out(c, depo_db, kullanici, monkeypatch):
    _yukle(depo_db, kullanici.id, KREDI)

    def bozuk(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 500).")
    monkeypatch.setattr(providers, "generate", bozuk)
    eski = c.post("/api/generate", json=GORSEL).json()["is"]["id"]
    assert _tek_tur(depo_db) and _bakiye(depo_db, kullanici.id) == KREDI
    # Arada bakiye başka bir işe gitti: yeniden gönderim yeni rezerv ister, yetmez.
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    r = c.post(f"/api/isler/{eski}/yeniden")
    assert r.status_code == 402, r.text
    assert r.json()["detail"] == {"kod": "err.kredi_yetersiz", "bakiye": 0, "gereken": KREDI, "plan": "pro",
                                  "hibe": 0, "paket": 0}
    assert len(_isler(depo_db)) == 2, "402'de yeni satır doğmadı"


# ── (iv) sıra: 429 önce, 402 sonra (K9) ────────────────────────────────

def test_the_daily_cap_is_asked_before_the_balance_so_a_429_never_touches_the_ledger(c, depo_db, kullanici,
                                                                                  monkeypatch):
    _yukle(depo_db, kullanici.id, 1)                            # bakiye de yetmiyor…
    monkeypatch.setenv(kota.GUNLUK_KREDI_ENV, str(KREDI - 1))   # …ama tavan daha önce konuşur (K9)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers and isinstance(r.json()["detail"], str)
    assert str(KREDI - 1) in r.json()["detail"], "cümle günlük tavanın (`err.gunluk_kredi_tavani`), bakiyenin değil"
    assert _bakiye(depo_db, kullanici.id) == 1 and _hareketler(depo_db, kullanici.id) == []
    assert _isler(depo_db) == []
    # Tavan açıldı, bakiye hâlâ yetmiyor → şimdi 402.
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 402 and r.json()["detail"]["bakiye"] == 1


# ── (v) asıl kapı: atomik rezerv ────────────────────────────────────────

def test_the_atomic_reserve_is_the_authority_even_when_the_read_only_precheck_is_bypassed(c, depo_db, kullanici,
                                                                                        monkeypatch):
    """İki istek aynı bakiyeye yarışırsa ön denetim ikisini de geçirir; kararı `rezerve`nin
    `WHERE bakiye >= :m`i verir. Ön denetimi susturup o yolu tek başına ölçüyoruz."""
    monkeypatch.setattr(kapilar, "check_bakiye", lambda *a, **k: None)
    _yukle(depo_db, kullanici.id, KREDI - 1)
    r = c.post("/api/generate", json=GORSEL)
    assert r.status_code == 402, r.text
    assert r.json()["detail"] == {"kod": "err.kredi_yetersiz", "bakiye": KREDI - 1, "gereken": KREDI, "plan": "pro",
                                  "hibe": KREDI - 1, "paket": 0}
    assert _isler(depo_db) == [], "`kuyruk.ekle` flush etmişti; 402 transaksiyonu geri aldı"
    assert _bakiye(depo_db, kullanici.id) == KREDI - 1 and _hareketler(depo_db, kullanici.id) == []
    # Aynı yol yeterli bakiyede geçer ve satırı yazar.
    _yukle(depo_db, kullanici.id, 1, ay="2026-10")
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert _bakiye(depo_db, kullanici.id) == 0 and len(_isler(depo_db)) == 1


def test_the_reserve_helper_raises_402_for_a_platform_job_and_is_a_no_op_for_byok(depo_db, kullanici):
    from fastapi import HTTPException
    _yukle(depo_db, kullanici.id, 3)
    with Session(depo_db) as db:
        assert kapilar.rezerve_kredi(db, kullanici, uuid.uuid4(), 8, "kullanici") is None
        kapilar.check_bakiye(db, kullanici, 8, "kullanici")
        with pytest.raises(HTTPException) as e:
            kapilar.check_bakiye(db, kullanici, 8, "platform")
        assert e.value.status_code == 402 and e.value.detail == {"kod": "err.kredi_yetersiz", "bakiye": 3,
                                                                 "gereken": 8, "plan": "pro", "hibe": 3, "paket": 0}
        with pytest.raises(HTTPException) as e:
            kapilar.rezerve_kredi(db, kullanici, uuid.uuid4(), 8, "platform")
        assert e.value.status_code == 402 and e.value.detail["bakiye"] == 3
        db.rollback()
    assert _bakiye(depo_db, kullanici.id) == 3
