# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Planlar ve aylık hibe (Faz 3 / 3; docs/faz3-kredi-defteri-filigran.md §3, K5/K6/K7).

Kuyruk ve defter GERÇEK Postgres (`depo_db`), sağlayıcı yamalı, anahtar kapısı
`platform` der (`c` fixture'ı). Conftest'in kullanıcısı ÜCRETSİZ — kapının
öntanımlı hâli ölçülür, `pro` bu dosyada açıkça yazılır (`depo_admin.plan_yaz`).
Beş soru:

  (i)   KATALOG — `PLANLAR` ↔ `kullanicilar.plan` CHECK kümesi eşit (bekçi); admin.js'in
        seçici listesi aynı üç ad; `KROMIS_FREE_AYLIK_HIBE` boş → 200, bozuk → gürültü.
  (ii)  KAPI — `model_available` dört durum; ücretsiz + video → 403 gövdesi
        `{"kod": "err.plan_kapsamiyor", "model", "plan"}`, iş satırı yok, nesne yok;
        BYOK'lu ücretsiz de 403 ve anahtar kapısı hiç sorulmaz (K7); yeniden gönderim
        de 403; görsel rotası açık; döküm `sebep`; yönetmen menüsü videoyu görmez.
  (iii) HİBE — tamamla: 0 → 200, 150 → 200 (+50), 250 → dokunma; aynı ay ikinci tur
        no-op; ay değişince yeni satır; silinmiş hesap ve hibesi 0 plan atlanır; `pro`
        kendi sayısına tamamlanır; SUM == bakiye.
  (iv)  RLS — kayıt hibesi ve bakım turu UYGULAMA ROLÜYLE (`SET ROLE`): kayıt yeni
        kullanıcının bağlamını bağlar (`sahip`), tur admin bağlamında (`yonetici_ekler`);
        bağlamsız aynı INSERT politikaya çarpar — bağlamın var olma sebebi ölçülür.
  (v)   ADMİN — plan yaz → sonraki iş video alır; kredi ± → `duzeltme` satırı `admin_id`
        dolu, 0 ve açıklamasız 422; admin olmayan 403; `olay=admin.plan`/`admin.kredi`.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import inspect
import io
import logging
import os
import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

import app as appmod
import catalog
import i18n
import providers
from routers import hesap as hesap_router
from services import (
    defter,
    depo_admin,
    isci,
    kapilar,
    kiraci,
    kota,
    modeller,
    planlar,
    platform_anahtari,
    tablolar,
)
from services.tablolar import KrediHareketi, Kullanici
from tests.test_rls import ROL, uygulama_motoru  # noqa: F401 — SET ROLE fixture'ı (getfixturevalue)

pytestmark = pytest.mark.usefixtures("depo_db")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
VIDEO = {"prompt": "kedi kosuyor", "size": "16:9", "quality": "720p", "duration": 4}
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
MP4 = b"\x00\x00\x00\x20ftypmp42"
SPEC = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
assert SPEC is not None
VIDEO_SPEC = catalog.video_model(catalog.DEFAULT_VIDEO_MODEL)
assert VIDEO_SPEC is not None
HIBE = planlar.PLANLAR["free"].aylik_hibe
EYLUL = dt.datetime(2026, 9, 20, 12, 0, tzinfo=dt.UTC)
EKIM = dt.datetime(2026, 10, 1, 0, 5, tzinfo=dt.UTC)
ANAHTAR_BICIMI = re.compile(r"^hibe:[0-9a-f-]{36}:\d{4}-\d{2}$")


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def temiz(depo_db):
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM kullanicilar WHERE eposta LIKE 'b-%@example.com'"))
    yield


@pytest.fixture
def c(tmp_path, monkeypatch, dizinler, kullanici):
    """Sahte sağlayıcı, işçi koşmaz; anahtar kapısı `platform` der (tests/test_uretim_kapilar.py deseni)."""
    dizinler(data_dir=str(tmp_path))
    monkeypatch.delenv(kota.GUNLUK_KREDI_ENV, raising=False)
    monkeypatch.setattr(kapilar, "check_anahtar", lambda *a, **k: "platform")
    monkeypatch.setattr(providers, "generate", lambda m, p, s, q, n, **k: [PNG] * n)
    monkeypatch.setattr(providers, "generate_video", lambda *a, **k: [MP4])
    monkeypatch.setattr(providers, "animate_video", lambda *a, **k: [MP4])
    return TestClient(appmod.app)


@pytest.fixture
def admin(depo_db, kullanici) -> Kullanici:
    """conftest'in kullanıcısı ADMİN olur — nesne (kapı) ve satır (tests/test_admin.py deseni)."""
    kullanici.is_admin = True
    with depo_db.begin() as c:
        c.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": kullanici.id})
    return kullanici


class _Yakalayici(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.satirlar: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        from services import gunluk
        alanlar = gunluk.alanlar(record)
        alanlar.pop("istek_id", None)
        self.satirlar.append(alanlar)


@pytest.fixture
def gunluk() -> Iterator[_Yakalayici]:
    """`kromis.admin` kayıtları (tests/test_admin.py'nin aynı gerekçesi: Alembic `fileConfig` günlükçüyü kapatıyor)."""
    logger = logging.getLogger("kromis.admin")
    yakalayici = _Yakalayici()
    eski = logger.level
    logger.disabled = False
    logger.addHandler(yakalayici)
    logger.setLevel(logging.INFO)
    try:
        yield yakalayici
    finally:
        logger.removeHandler(yakalayici)
        logger.setLevel(eski)


def _kullanici(depo_db, *, plan: str = "free", silindi: bool = False) -> uuid.UUID:
    with Session(depo_db) as s:
        k = Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                      dogrulandi_at=EYLUL, dil=None, plan=plan,
                      silindi_at=EYLUL if silindi else None)
        s.add(k)
        s.commit()
        return k.id


def _yukle(depo_db, kullanici_id: uuid.UUID, miktar: int, an: dt.datetime = EYLUL) -> None:
    """Bakiye yalnız defter üzerinden (tek yazar); anahtar ayın anahtarı DEĞİL — tohum, hibe sayılmasın."""
    with Session(depo_db) as db:
        assert defter.hibe(db, kullanici_id, miktar, f"{defter.ONEK_HIBE}{kullanici_id}:tohum-{uuid.uuid4().hex[:6]}", an=an)
        db.commit()


def _bakiye(depo_db, kullanici_id: uuid.UUID) -> int:
    """HİBE kovası (`kullanicilar.bakiye`): bu dosya hibeyi ölçer, paket kovası boş (Faz 4 / 2)."""
    with Session(depo_db) as db:
        return defter.bakiye(db, kullanici_id).hibe


def _plan_yaz(depo_db, kullanici_id: uuid.UUID, plan: str, nesne: Kullanici | None = None) -> None:
    """Planı DB'ye yazar; `nesne` verilmişse conftest'in override nesnesine de.

    Kapı planı YÜKLÜ satırdan okur (`kapilar.kullanici_plani`; üretimde kimlik
    kapısı satırı her istekte yeniden çeker). Testin override nesnesi ise bir
    kez yazılmış ve `eager_defaults` ile `plan="free"` yüklenmiş duruyor —
    DB'deki değişikliği görmez (`kota.check_gunluk`in `gunluk_kredi_tavani`
    için aynı dersi: tests/test_admin.py "override nesnesi tavan değişikliğini
    görmezdi"). Gerçek çerezli yol tests/test_playwright_admin.py'de.
    """
    with Session(depo_db) as db:
        assert depo_admin.plan_yaz(db, kullanici_id, plan)
        db.commit()
    if nesne is not None:
        nesne.plan = plan


def _hareketler(depo_db, kullanici_id: uuid.UUID) -> list[KrediHareketi]:
    with Session(depo_db) as db:
        return list(db.scalars(select(KrediHareketi).where(KrediHareketi.kullanici_id == kullanici_id)
                               .order_by(KrediHareketi.olusturuldu, KrediHareketi.id)))


def _hibe_turu(depo_db, an: dt.datetime) -> int:
    with Session(depo_db) as db:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
            n = defter.hibe_turu(db, an)
            db.commit()
    return n


def _toplam_esit_bakiye(depo_db, kullanici_id: uuid.UUID) -> None:
    with Session(depo_db) as db:
        toplam = int(db.scalar(select(func.coalesce(func.sum(KrediHareketi.miktar), 0))
                               .where(KrediHareketi.kullanici_id == kullanici_id)) or 0)
        assert toplam == defter.bakiye(db, kullanici_id).hibe, "SUM(defter) != bakiye"


def _isler(depo_db) -> list[tablolar.Is]:
    with Session(depo_db) as db:
        return list(db.scalars(select(tablolar.Is)))


# ── (i) katalog ────────────────────────────────────────────────────────

def test_the_plan_catalogue_matches_the_db_check_set_and_the_admin_selector():
    """K5: kodun planları DB'nin CHECK kümesiyle birebir; admin.js'in seçici listesi de aynı üç ad."""
    assert tuple(planlar.PLANLAR) == tablolar.PLANLAR_KUMESI == ("free", "temel", "pro")
    for ad, plan in planlar.PLANLAR.items():
        assert plan.ad == ad and plan.fiyat is None and plan.aylik_hibe >= 0
    assert planlar.PLANLAR["free"] == planlar.Plan("free", HIBE, filigran=True, video=False, rank=0)
    assert not planlar.PLANLAR["free"].video and planlar.PLANLAR["temel"].video and planlar.PLANLAR["pro"].video
    assert planlar.PLANLAR["free"].filigran and not planlar.PLANLAR["pro"].filigran
    with open(os.path.join(REPO, "static", "admin.js"), encoding="utf-8") as f:
        js = f.read()
    m = re.search(r'const PLANLAR = \[([^\]]+)\];', js)
    assert m, "admin.js plan listesi yok"
    assert tuple(re.findall(r'"([a-z]+)"', m.group(1))) == tablolar.PLANLAR_KUMESI


def test_the_free_grant_comes_from_the_environment_empty_is_200_and_garbage_is_loud():
    assert planlar.free_aylik_hibe({}) == 200
    assert planlar.free_aylik_hibe({planlar.FREE_AYLIK_HIBE_ENV: " "}) == 200
    assert planlar.free_aylik_hibe({planlar.FREE_AYLIK_HIBE_ENV: "350"}) == 350
    assert planlar.free_aylik_hibe({planlar.FREE_AYLIK_HIBE_ENV: "0"}) == 0, "0 geçerli: hibe kapalı"
    with pytest.raises(ValueError, match="tam sayi"):
        planlar.free_aylik_hibe({planlar.FREE_AYLIK_HIBE_ENV: "ikiyuz"})
    with pytest.raises(ValueError, match="negatif"):
        planlar.free_aylik_hibe({planlar.FREE_AYLIK_HIBE_ENV: "-5"})
    assert planlar.FREE_AYLIK_HIBE_ENV == "KROMIS_FREE_AYLIK_HIBE"
    with open(os.path.join(REPO, ".env.example"), encoding="utf-8") as f:
        assert "\nKROMIS_FREE_AYLIK_HIBE=\n" in f.read()


# ── (ii) kapı ──────────────────────────────────────────────────────────

PLATFORM = platform_anahtari.KAYNAK_PLATFORM
BENIM = platform_anahtari.KAYNAK_KULLANICI

# Üç eksen birden taranıyor (§1b "basamak bekçisi"): kullanıcının planı ×
# modelin istediği basamak × anahtarın kaynağı. Tek yol denemek yetmezdi —
# `kapsiyor`un imzası 1b'de değişti ve üç çağıranı var; risk notu ("biri
# unutulursa kapı sessizce gevşer") ancak kombinasyon taranırsa kapanır.
@pytest.mark.parametrize("spec, configured, plan, kaynak, beklenen, sebep", [
    (SPEC, True, "free", PLATFORM, True, None),                 # görsel + anahtar → açık
    (SPEC, False, "free", None, False, "anahtar"),              # görsel, anahtar yok
    (VIDEO_SPEC, True, "free", PLATFORM, False, "plan"),        # video, ücretsiz: anahtar olsa da kapalı (K7)
    (VIDEO_SPEC, True, "pro", PLATFORM, True, None),            # video, pro → açık
    (VIDEO_SPEC, False, "pro", None, False, "anahtar"),         # video, pro, anahtar yok
    (VIDEO_SPEC, False, "free", None, False, "plan"),           # iki sebep birden: plan önce
    # ── BASAMAK (1b-B): "yalnız pro" artık İFADE EDİLEBİLİR ──
    (dataclasses.replace(SPEC, plan="pro"), True, "free", PLATFORM, False, "plan"),
    (dataclasses.replace(SPEC, plan="pro"), True, "temel", PLATFORM, False, "plan"),
    (dataclasses.replace(SPEC, plan="pro"), True, "pro", PLATFORM, True, None),
    (dataclasses.replace(SPEC, plan="temel"), True, "free", PLATFORM, False, "plan"),
    (dataclasses.replace(SPEC, plan="temel"), True, "temel", PLATFORM, True, None),
    (dataclasses.replace(SPEC, plan="temel"), True, "pro", PLATFORM, True, None),  # üst basamak alt modeli görür
    # ── BYOK (1b-A): kendi anahtarı EŞİĞİ aşar, VİDEOYU aşmaz ──
    (dataclasses.replace(SPEC, plan="pro"), True, "free", BENIM, True, None),
    (dataclasses.replace(SPEC, plan="temel"), True, "free", BENIM, True, None),
    (VIDEO_SPEC, True, "free", BENIM, False, "plan"),
])
def test_model_available_reads_the_plan_and_sebep_names_the_reason(spec, configured, plan, kaynak, beklenen, sebep):
    assert modeller.model_available(spec, configured, plan, kaynak) is beklenen
    assert modeller.sebep(spec, configured, plan, kaynak) == sebep
    assert planlar.kapsiyor(plan, spec, platform_anahtariyla=kaynak == PLATFORM) is (sebep != "plan")


def test_the_plan_ranks_are_a_contiguous_ascending_ladder_in_the_check_sets_order():
    """1b-B basamak bekçisi: `rank` ↔ `PLANLAR_KUMESI` sırası ayrışmasın.

    `rank` BİLEREK türetilmiyor (gerekçe `Plan.rank`ın yorumunda: o demetin
    sözleşmesi CHECK kümesi, sıralama değil). Türetilmeyen her şeyin bekçisi
    bir testtir — ikisi ayrıştığı gün burası kırmızı olur, kapı sessizce
    yanlış sıraya geçmez.
    """
    sirali = [planlar.PLANLAR[ad].rank for ad in tablolar.PLANLAR_KUMESI]
    assert sirali == list(range(len(tablolar.PLANLAR_KUMESI))) == [0, 1, 2]
    assert planlar.PLANLAR["free"].rank < planlar.PLANLAR["temel"].rank < planlar.PLANLAR["pro"].rank


def test_the_key_source_gate_never_opens_video_and_never_changes_the_watermark():
    """1b-A'nın İKİ SINIRI: kendi anahtarı eşiği aşar, ama video kapısını ve filigranı AŞMAZ (K7).

    Bu testin var olma sebebi, 1b-A'nın kendi cümlesi: kural anahtarın kimin
    olduğuna değil FİLİGRAN YOKLUĞUNA dayanıyor (sunucuda ffmpeg yok) ve
    anahtarın sahibi o yokluğu değiştirmiyor. Eşik gevşerken bu ikisinin de
    gevşemesi, kapının en kolay yanlış genellemesi olurdu.
    """
    pahali = dataclasses.replace(SPEC, plan="pro")
    # Eşik: kendi anahtarıyla AŞILIR.
    assert planlar.kapsiyor("free", pahali, platform_anahtariyla=False)
    assert not planlar.kapsiyor("free", pahali, platform_anahtariyla=True)
    # Video: kendi anahtarıyla AŞILMAZ — iki kaynakta da kapalı.
    for platformla in (True, False):
        assert not planlar.kapsiyor("free", VIDEO_SPEC, platform_anahtariyla=platformla)
        assert planlar.kapsiyor("pro", VIDEO_SPEC, platform_anahtariyla=platformla)
    # Filigran: karar anahtarın sahibine BAKMIYOR. İmza denetimi YETMEZ —
    # `_filigranlanir` işin SATIRINI alıyor ve `Is.anahtar_kaynagi` o satırda
    # duruyor, yani alan erişimiyle sessizce okunabilirdi. Bu yüzden gövde
    # taranıyor: K7'nin taşıyıcı cümlesi ("kendi anahtarıyla pahalı model
    # kullanan ücretsiz kullanıcı yine FİLİGRANLI çıktı alır") ancak böyle
    # mandallanır.
    assert list(inspect.signature(isci._filigranlanir).parameters) == ["is_", "plan"]
    assert "anahtar_kaynagi" not in inspect.getsource(isci._filigranlanir)


def test_kapsiyor_has_no_default_for_the_key_source_so_a_forgotten_caller_is_loud():
    """Öntanımlı bir değer, unutulan çağıranda eşiği SESSİZCE atlatırdı (§1b risk notu).

    İmza anahtar sözcüklü ve öntanımsız: üç çağıranın biri güncellenmezse
    `TypeError` — kapı gevşemiyor, takım kırmızı oluyor.
    """
    p = inspect.signature(planlar.kapsiyor).parameters["platform_anahtariyla"]
    assert p.default is inspect.Parameter.empty, "öntanımlı değer kapıyı sessizce gevşetir"
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        planlar.kapsiyor("free", SPEC)


def test_a_free_user_posting_video_gets_403_with_the_body_and_no_row_or_object(c, depo_db, kullanici, tmp_path):
    _yukle(depo_db, kullanici.id, 1000)
    r = c.post("/api/video", json=VIDEO)
    assert r.status_code == 403, r.text
    assert r.json() == {"detail": {"kod": "err.plan_kapsamiyor", "model": catalog.DEFAULT_VIDEO_MODEL, "plan": "free"}}
    a = c.post("/api/video/animate", data=VIDEO, files={"file": ("a.png", _png(), "image/png")})
    assert a.status_code == 403 and a.json()["detail"]["kod"] == "err.plan_kapsamiyor", a.text
    assert _isler(depo_db) == [], "403 iş doğurmaz"
    assert _bakiye(depo_db, kullanici.id) == 1000, "403 bakiyeye dokunmaz"
    assert not list((tmp_path / "kullanicilar").rglob("isler/*")), "403 depoya nesne bırakmaz"
    # Cümle iki dilde ve iki alanı taşır (ön yüz `kod`dan kurar).
    for d in ("tr", "en"):
        cumle = i18n.t("err.plan_kapsamiyor", d, model="Veo", plan="free")
        assert "Veo" in cumle and "free" in cumle and "{" not in cumle


def test_a_byok_free_user_also_gets_403_and_the_key_gate_is_never_asked(c, depo_db, kullanici, monkeypatch):
    """K7: kural filigran yokluğu, anahtarın kimin olduğu değil — plan kapısı anahtar kapısından ÖNCE."""
    soruldu: list[str] = []

    def _anahtar(cred_id, kimlikler):
        soruldu.append(cred_id)
        return "kullanici"
    monkeypatch.setattr(kapilar, "check_anahtar", _anahtar)
    r = c.post("/api/video", json=VIDEO)
    assert r.status_code == 403 and r.json()["detail"]["plan"] == "free"
    assert soruldu == [], "plan kapısı anahtar kapısından önce; 403'te anahtar hiç sorulmaz"
    # Görsel rotası aynı kullanıcıya açık: anahtar kapısı sorulur.
    _yukle(depo_db, kullanici.id, 100)
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    assert soruldu == [SPEC.credential]


def test_image_routes_stay_open_to_the_free_plan_and_pro_opens_video(c, depo_db, kullanici):
    _yukle(depo_db, kullanici.id, 1000)
    assert c.post("/api/generate", json=GORSEL).status_code == 202
    e = c.post("/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "low", "n": "1"},
               files={"file": ("a.png", _png(), "image/png")})
    assert e.status_code == 202, e.text
    _plan_yaz(depo_db, kullanici.id, "pro", kullanici)
    v = c.post("/api/video", json=VIDEO)
    assert v.status_code == 202, v.text
    assert v.json()["is"]["tur"] == "video"


def test_resubmitting_a_closed_video_job_is_403_once_the_user_is_free_again(c, depo_db, kullanici):
    """Yeniden gönderim de bir iş doğurur: plan kapısını ATLAYAMAZ (ücretsize düşen kullanıcının eski video işi)."""
    _yukle(depo_db, kullanici.id, 1000)
    _plan_yaz(depo_db, kullanici.id, "pro", kullanici)
    is_id = c.post("/api/video", json=VIDEO).json()["is"]["id"]
    with depo_db.begin() as s:
        s.execute(text("UPDATE isler SET durum = 'hata', bitti = now() WHERE id = :id"), {"id": is_id})
    assert c.post(f"/api/isler/{is_id}/yeniden").status_code == 202
    _plan_yaz(depo_db, kullanici.id, "free", kullanici)
    r = c.post(f"/api/isler/{is_id}/yeniden")
    assert r.status_code == 403 and r.json()["detail"] == {
        "kod": "err.plan_kapsamiyor", "model": catalog.DEFAULT_VIDEO_MODEL, "plan": "free"}


def test_the_model_listing_carries_sebep_and_the_director_menu_hides_video_for_free(c, depo_db, kullanici):
    """`/api/settings`: video `sebep: "plan"` (ücretsiz, anahtar durumu ne olursa olsun), pro'da anahtara göre;
    yönetmen menüsü aynı süzgeçten geçer. Anahtar yok: görsel modelleri `anahtar` der."""
    govde = c.get("/api/settings").json()
    assert govde["video_models"] and all(m["available"] is False and m["sebep"] == "plan" for m in govde["video_models"])
    assert govde["image_models"] and all(m["available"] is False and m["sebep"] == "anahtar" for m in govde["image_models"])
    assert all(m["sebep"] in (None, "anahtar") for m in govde["chat_models"])
    kimlikler = {cr.key_env: "x" for cr in catalog.CREDENTIALS}
    with Session(depo_db) as db:
        menu = modeller.director_context(db, kullanici.id, kimlikler)["available_models"]
    assert menu and all(m["kind"] != "video" for m in menu), "ücretsiz kullanıcının yönetmeni video önermez"
    _plan_yaz(depo_db, kullanici.id, "pro", kullanici)
    govde = c.get("/api/settings").json()
    assert all(m["available"] is False and m["sebep"] == "anahtar" for m in govde["video_models"]), "pro: artık anahtar sorusu"
    with Session(depo_db) as db:
        menu = modeller.director_context(db, kullanici.id, kimlikler)["available_models"]   # plan DB'den okunur
    assert any(m["kind"] == "video" for m in menu)
    # `plan` açık verilirse DB okunmaz (rota yüklü satırdan verir).
    with Session(depo_db) as db:
        assert all(m["kind"] != "video" for m in modeller.director_context(db, kullanici.id, kimlikler,
                                                                            plan="free")["available_models"])


def test_the_front_end_shows_a_plan_locked_model_with_a_badge_and_blocks_go():
    """Rozet ve kapı: `secilebilirler` plan kapalıyı gizlemez, `secilecek` seçmez, `goBlockReason` sebebini söyler."""
    with open(os.path.join(REPO, "static", "core.js"), encoding="utf-8") as f:
        js = f.read()
    filtre = js.split("function secilebilirler(", 1)[1].split("\n}\n", 1)[0]
    assert 'm.sebep === "plan"' in filtre, "plan kapalı model listeden düşmüş"
    secilecek = js.split("function secilecek(", 1)[1].split("\n}\n", 1)[0]
    assert "sebep" not in secilecek and "m.available" in secilecek, "otomatik seçim yalnız kullanılabilir modeli alır"
    for fn in ("function modelSecenekMetni(", "function renderModelCards("):
        govde = js.split(fn, 1)[1].split("\n}\n", 1)[0]
        assert 't("model.plan_locked")' in govde or '"model.plan_locked"' in govde, fn
    kapi = js.split("function goBlockReason(", 1)[1].split("\n}\n", 1)[0]
    assert kapi.count('t("gate.model_plan_locked"') >= 3, "görsel, video ve arena dalları"
    assert 't("gate.plan_locked_video")' in kapi
    # Plan kapısı anahtar kapısından ÖNCE (video dalı): anahtar bu kapıyı açmaz.
    video = kapi.split('if (currentMode === "video")', 1)[1]
    assert video.index("gate.model_plan_locked") < video.index("gate.model_no_key")


# ── (iii) hibe ─────────────────────────────────────────────────────────

def test_the_monthly_tour_tops_up_to_the_grant_and_leaves_full_balances_alone(depo_db, kullanici):
    """K6 "hibeye tamamla": 0 → 200, 150 → 200 (+50), 250 → dokunma; anahtar `hibe:<u>:<YYYY-MM>`."""
    sifir = _kullanici(depo_db)
    yarim = _kullanici(depo_db)
    dolu = _kullanici(depo_db)
    _yukle(depo_db, yarim, 150)
    _yukle(depo_db, dolu, 250)
    yazilan = _hibe_turu(depo_db, EYLUL)
    # conftest kullanıcısı da ücretsiz ve 0'da — o da tamamlanır (+1).
    assert yazilan == 3
    assert _bakiye(depo_db, sifir) == HIBE and _bakiye(depo_db, yarim) == HIBE and _bakiye(depo_db, dolu) == 250
    assert _bakiye(depo_db, kullanici.id) == HIBE
    satirlar = [h for h in _hareketler(depo_db, yarim) if "tohum" not in h.idempotency_anahtari]
    assert len(satirlar) == 1 and satirlar[0].tur == defter.TUR_HIBE and satirlar[0].miktar == HIBE - 150
    assert satirlar[0].idempotency_anahtari == f"hibe:{yarim}:2026-09" and ANAHTAR_BICIMI.match(satirlar[0].idempotency_anahtari)
    assert satirlar[0].olusturuldu == EYLUL and satirlar[0].admin_id is None and satirlar[0].is_id is None
    assert [h.tur for h in _hareketler(depo_db, dolu)] == [defter.TUR_HIBE], "dolu bakiyeye satır yazılmaz"
    for u in (sifir, yarim, dolu, kullanici.id):
        _toplam_esit_bakiye(depo_db, u)


def test_a_second_tour_in_the_same_month_is_a_no_op_even_after_spending(depo_db, kullanici):
    """Devretmeme: ay içinde harcanan yeniden dolmaz — anahtar çakışır, satır yok, bakiye aynı."""
    u = _kullanici(depo_db)
    assert _hibe_turu(depo_db, EYLUL) >= 1 and _bakiye(depo_db, u) == HIBE
    # Harcama `duzelt` ile modellenir (tek yazar defter, elle UPDATE yok; `rezerve` iş satırı FK'sı ister).
    with Session(depo_db) as db:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
            defter.duzelt(db, u, -120, "harcama tohumu", admin_id=kullanici.id, an=EYLUL)
            db.commit()
    assert _bakiye(depo_db, u) == HIBE - 120
    assert _hibe_turu(depo_db, EYLUL + dt.timedelta(days=5)) == 0
    assert _bakiye(depo_db, u) == HIBE - 120
    assert sum(1 for h in _hareketler(depo_db, u) if h.tur == defter.TUR_HIBE) == 1
    _toplam_esit_bakiye(depo_db, u)


def test_a_new_month_tops_up_again_with_a_new_row(depo_db, kullanici):
    u = _kullanici(depo_db)
    _hibe_turu(depo_db, EYLUL)
    with Session(depo_db) as db:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
            defter.duzelt(db, u, -120, "harcama tohumu", admin_id=kullanici.id, an=EYLUL)
            db.commit()
    assert _hibe_turu(depo_db, EKIM) >= 1
    assert _bakiye(depo_db, u) == HIBE
    hibeler = [h for h in _hareketler(depo_db, u) if h.tur == defter.TUR_HIBE]
    assert [h.idempotency_anahtari for h in hibeler] == [f"hibe:{u}:2026-09", f"hibe:{u}:2026-10"]
    assert [h.miktar for h in hibeler] == [HIBE, 120]
    _toplam_esit_bakiye(depo_db, u)


def test_the_tour_skips_deleted_accounts_and_a_plan_whose_grant_is_zero(depo_db, kullanici, monkeypatch):
    silik = _kullanici(depo_db, silindi=True)
    canli = _kullanici(depo_db)
    monkeypatch.setitem(planlar.PLANLAR, "free", dataclasses.replace(planlar.PLANLAR["free"], aylik_hibe=0))
    assert _hibe_turu(depo_db, EYLUL) == 0, "hibesi 0 plan atlanır (KROMIS_FREE_AYLIK_HIBE=0)"
    monkeypatch.setitem(planlar.PLANLAR, "free", dataclasses.replace(planlar.PLANLAR["free"], aylik_hibe=200))
    _hibe_turu(depo_db, EYLUL)
    assert _bakiye(depo_db, silik) == 0 and _hareketler(depo_db, silik) == []
    assert _bakiye(depo_db, canli) == 200


def test_paid_plans_are_never_topped_up_by_the_tour_their_grant_comes_from_the_webhook(depo_db):
    """Faz 4 / 3 (K6): ücretli planın dönem hibesi `order.paid` webhook'unun (tests/test_odeme.py); bakım turu YALNIZ
    `free`yi tarar. Faz 4 / 2'nin geçici köprüsü (`KROMIS_UCRETLI_HIBE_BAKIMDA`) 3 ile kaldırıldı — ortamda
    kalmış bir `1` hiçbir şey açmaz."""
    u = _kullanici(depo_db, plan="pro")
    _yukle(depo_db, u, 500)
    os.environ["KROMIS_UCRETLI_HIBE_BAKIMDA"] = "1"
    try:
        _hibe_turu(depo_db, EYLUL)
    finally:
        del os.environ["KROMIS_UCRETLI_HIBE_BAKIMDA"]
    assert _bakiye(depo_db, u) == 500, "tur `pro`yu tamamlamaz — bayrak yok"
    assert not hasattr(planlar, "ucretli_hibe_bakimda")
    _toplam_esit_bakiye(depo_db, u)


def test_paid_plan_grants_come_from_the_environment_with_the_placeholders_as_defaults():
    """Faz 4 / 2 (K5): `KROMIS_TEMEL_AYLIK_HIBE` / `KROMIS_PRO_AYLIK_HIBE`; boş = 1.000 / 3.000, bozuk gürültü."""
    assert planlar.aylik_hibe(planlar.TEMEL_AYLIK_HIBE_ENV, planlar.TEMEL_AYLIK_HIBE_VARSAYILAN, {}) == 1_000
    assert planlar.aylik_hibe(planlar.PRO_AYLIK_HIBE_ENV, planlar.PRO_AYLIK_HIBE_VARSAYILAN, {}) == 3_000
    assert planlar.aylik_hibe(planlar.PRO_AYLIK_HIBE_ENV, 3_000, {planlar.PRO_AYLIK_HIBE_ENV: " 4500 "}) == 4_500
    assert planlar.aylik_hibe(planlar.TEMEL_AYLIK_HIBE_ENV, 1_000, {planlar.TEMEL_AYLIK_HIBE_ENV: "0"}) == 0
    for kotu in ("bin", "-1", "1.5"):
        with pytest.raises(ValueError):
            planlar.aylik_hibe(planlar.TEMEL_AYLIK_HIBE_ENV, 1_000, {planlar.TEMEL_AYLIK_HIBE_ENV: kotu})
    assert planlar.PLANLAR["temel"].aylik_hibe == 1_000 and planlar.PLANLAR["pro"].aylik_hibe == 3_000
    assert planlar.PLANLAR["pro"].fiyat is None, "fiyat Polar'da, aynası `urunler` (K5)"


# ── (iv) RLS: kayıt hibesi ve bakım turu uygulama rolüyle ───────────────

def test_registration_grants_the_month_immediately_under_the_application_role(request, depo_db, monkeypatch, c):
    """Kayıt → bakiye 200, `hibe` satırı; `SET ROLE` altında: rota yeni kullanıcının bağlamını bağlar (`sahip`)."""
    motor = request.getfixturevalue("uygulama_motoru")
    monkeypatch.setattr(hesap_router, "_gonder", lambda *a, **k: None)   # e-posta bu testin konusu değil
    # test_rls'in rolü tablolara yetkili, DİZİLERE değil (o dosyanın testleri satır eklemiyor); kayıt
    # `giris_denemeleri`ye yazar — üretimde `tools/uygulama_rolu.py` diziyi de verir, burada elle.
    with depo_db.begin() as yonetici:
        yonetici.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROL}"))

    def _uygulama_oturumu():
        with Session(motor) as s:
            try:
                yield s
            except BaseException:
                s.rollback()
                raise
            else:
                s.commit()
    from services import db as dbmod
    appmod.app.dependency_overrides[dbmod.oturum] = _uygulama_oturumu    # `kullanici` fixture'ı teardown'da düşürür
    eposta = f"b-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/hesap/kayit", json={"eposta": eposta, "parola": "cok-gizli-parola-1"})
    assert r.status_code == 200, r.text
    with Session(depo_db) as s:
        k = s.scalar(select(Kullanici).where(Kullanici.eposta == eposta))
        assert k is not None and k.plan == "free" and k.bakiye == HIBE
        hareketler = list(s.scalars(select(KrediHareketi).where(KrediHareketi.kullanici_id == k.id)))
    assert len(hareketler) == 1 and hareketler[0].tur == defter.TUR_HIBE and hareketler[0].miktar == HIBE
    assert ANAHTAR_BICIMI.match(hareketler[0].idempotency_anahtari) and hareketler[0].admin_id is None
    # Aynı ay bakım turu bu hesaba İKİNCİ hibe yazmaz (anahtar çakışır).
    with Session(motor) as s:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=s):
            yazilan = defter.hibe_turu(s, hareketler[0].olusturuldu)
            s.commit()
    with Session(depo_db) as s:
        assert s.scalar(select(func.count()).select_from(KrediHareketi).where(KrediHareketi.kullanici_id == k.id)) == 1
    assert isinstance(yazilan, int)
    # Yeniden kayıt (doğrulanmamış hesap): hesap yenilenir, hibe yeniden YAZILMAZ — `kullanici_olustur` dalı değil.
    assert c.post("/api/hesap/kayit", json={"eposta": eposta, "parola": "cok-gizli-parola-2"}).status_code == 200
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.bakiye).where(Kullanici.eposta == eposta)) == HIBE


def test_the_grant_insert_needs_a_tenant_context_under_rls_which_is_why_the_route_binds_one(request, depo_db):
    """Bağlamın var olma sebebi: aynı `hibe` bağlamsız INSERT politikaya çarpar; kullanıcı bağlamı ve admin bağlamı geçer."""
    motor = request.getfixturevalue("uygulama_motoru")
    u = _kullanici(depo_db)
    with Session(motor) as s:
        with pytest.raises(ProgrammingError, match="row-level security"):
            defter.aylik_hibe_yaz(s, u, HIBE, EYLUL)
            s.commit()
        s.rollback()
    with Session(motor) as s:
        with kiraci.baglam(kullanici_id=u, oturum=s):
            assert defter.aylik_hibe_yaz(s, u, HIBE, EYLUL) is True
            s.commit()
    assert _bakiye(depo_db, u) == HIBE
    v = _kullanici(depo_db)
    with Session(motor) as s:
        with pytest.raises(ProgrammingError, match="row-level security"):
            defter.hibe_turu(s, EYLUL)
            s.commit()
        s.rollback()
    with Session(motor) as s:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=s):
            assert defter.hibe_turu(s, EYLUL) >= 1   # `yonetici_ekler` (K4): bütün kiracılar adına
            s.commit()
    assert _bakiye(depo_db, v) == HIBE


# ── (v) admin ──────────────────────────────────────────────────────────

def test_the_admin_writes_the_plan_and_the_users_next_job_gets_video(c, depo_db, admin, gunluk):
    b = _kullanici(depo_db)
    r = c.post(f"/api/admin/kullanicilar/{b}/plan", json={"plan": "pro"})
    assert r.status_code == 200 and r.json() == {"id": str(b), "plan": "pro"}
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.plan).where(Kullanici.id == b)) == "pro"
    assert {k["id"]: k["plan"] for k in c.get("/api/admin/kullanicilar").json()["kullanicilar"]}[str(b)] == "pro"
    for kotu in ({"plan": "platin"}, {"plan": ""}, {}, {"plan": 3}):
        assert c.post(f"/api/admin/kullanicilar/{b}/plan", json=kotu).status_code == 422, kotu
    assert i18n.t("err.plan_gecersiz", "en", plan="platin", planlar="free, temel, pro") in \
        c.post(f"/api/admin/kullanicilar/{b}/plan", json={"plan": "platin"}).json()["detail"]
    assert c.post(f"/api/admin/kullanicilar/{uuid.uuid4()}/plan", json={"plan": "pro"}).status_code == 404
    assert gunluk.satirlar[0] == {"olay": "admin.plan", "admin": str(admin.id), "hedef": str(b), "plan": "pro"}
    # Adminin KENDİ hesabı (belge §3 "Sahibin adımı"): free → 403, pro → 202.
    _yukle(depo_db, admin.id, 1000)
    assert c.post("/api/video", json=VIDEO).status_code == 403
    assert c.post(f"/api/admin/kullanicilar/{admin.id}/plan", json={"plan": "pro"}).status_code == 200
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.plan).where(Kullanici.id == admin.id)) == "pro"
    admin.plan = "pro"   # override nesnesi (bkz. `_plan_yaz`); gerçek çerezli yol E2E'de
    assert c.post("/api/video", json=VIDEO).status_code == 202


def test_the_admin_adjusts_credits_and_the_ledger_row_carries_the_admin_id(c, depo_db, admin, gunluk):
    b = _kullanici(depo_db)
    _yukle(depo_db, b, 100)
    r = c.post(f"/api/admin/kullanicilar/{b}/kredi", json={"miktar": 50, "aciklama": "destek jesti"})
    assert r.status_code == 200, r.text
    govde = r.json()
    assert govde["id"] == str(b) and govde["bakiye"] == 150
    assert govde["hareket"]["tur"] == defter.TUR_DUZELTME and govde["hareket"]["miktar"] == 50
    assert govde["hareket"]["aciklama"] == "destek jesti" and "admin_id" not in govde["hareket"]
    eksi = c.post(f"/api/admin/kullanicilar/{b}/kredi", json={"miktar": -30, "aciklama": "geri alma"})
    assert eksi.status_code == 200 and eksi.json()["bakiye"] == 120
    duzeltmeler = [h for h in _hareketler(depo_db, b) if h.tur == defter.TUR_DUZELTME]
    assert [h.miktar for h in duzeltmeler] == [50, -30]
    assert all(h.admin_id == admin.id and h.idempotency_anahtari.startswith("duzeltme:") for h in duzeltmeler)
    _toplam_esit_bakiye(depo_db, b)
    for kotu in ({"miktar": 0, "aciklama": "x"}, {"miktar": 5}, {"miktar": 5, "aciklama": ""},
                 {"miktar": "bes", "aciklama": "x"}, {"miktar": 10**10, "aciklama": "x"}):
        assert c.post(f"/api/admin/kullanicilar/{b}/kredi", json=kotu).status_code == 422, kotu
    assert c.post(f"/api/admin/kullanicilar/{uuid.uuid4()}/kredi", json={"miktar": 5, "aciklama": "x"}).status_code == 404
    assert _bakiye(depo_db, b) == 120
    assert [s["olay"] for s in gunluk.satirlar] == ["admin.kredi", "admin.kredi"]
    assert gunluk.satirlar[0]["admin"] == str(admin.id) and gunluk.satirlar[0]["hedef"] == str(b)
    assert gunluk.satirlar[0]["miktar"] == 50 and gunluk.satirlar[1]["miktar"] == -30
    assert uuid.UUID(gunluk.satirlar[0]["hareket"]) == duzeltmeler[0].id
    assert {k["id"]: k["bakiye"] for k in c.get("/api/admin/kullanicilar").json()["kullanicilar"]}[str(b)] == 120


def test_a_non_admin_gets_403_on_plan_and_credit_and_nothing_changes(c, depo_db, kullanici):
    assert kullanici.is_admin is False
    b = _kullanici(depo_db)
    assert c.post(f"/api/admin/kullanicilar/{b}/plan", json={"plan": "pro"}).status_code == 403
    assert c.post(f"/api/admin/kullanicilar/{b}/kredi", json={"miktar": 5, "aciklama": "x"}).status_code == 403
    with Session(depo_db) as s:
        assert s.scalar(select(Kullanici.plan).where(Kullanici.id == b)) == "free"
    assert _bakiye(depo_db, b) == 0 and _hareketler(depo_db, b) == []


def test_the_plan_gate_helper_reads_the_loaded_row_without_a_second_query(depo_db, kullanici):
    """`kapilar.kullanici_plani`: yüklü nesneden (istek başına ek sorgu yok — test_kimlik sayacı), yüklü değilse DB'den."""
    from sqlalchemy import event
    sayac: list[str] = []

    def _say(conn, cursor, statement, parameters, context, executemany):
        sayac.append(statement)

    with Session(depo_db) as s:
        yuklu = s.get(Kullanici, kullanici.id)
        assert yuklu is not None
        # Yüklenmemiş bir vekil: yalnız `id` bilinen, satırı çekilmemiş nesne (kimlik kapısı böyle vermez;
        # `_yetersiz_bakiye`nin `DetachedInstanceError` dersi — `inspect().dict` lazy yükleme tetiklemez).
        vekil = Kullanici(id=kullanici.id, eposta="vekil@example.com", parola_ozeti=None)
        event.listen(depo_db, "before_cursor_execute", _say)
        try:
            assert kapilar.kullanici_plani(s, yuklu) == "free"
            assert sayac == [], "yüklü satır varken SELECT atılmaz"
            assert kapilar.kullanici_plani(s, vekil) == "free"
            assert len(sayac) == 1 and "kullanicilar.plan" in sayac[0], sayac
        finally:
            event.remove(depo_db, "before_cursor_execute", _say)


def _kimlikler(spec, kaynak):
    """Tek kimliği `kaynak`a ayarlanmış bir `Kimlikler` — `check_plan`ın okuduğu tek şey bu."""
    cred = catalog.credential(spec.credential)
    assert cred is not None
    return platform_anahtari.Kimlikler({cred.key_env: "x"}, {cred.key_env: kaynak})


def test_check_plan_is_the_route_side_of_the_same_rule(depo_db, kullanici):
    platform = _kimlikler(SPEC, PLATFORM)
    video_platform = _kimlikler(VIDEO_SPEC, PLATFORM)
    with Session(depo_db) as s:
        assert kapilar.check_plan(s, kullanici, SPEC, platform) == "free"
        with pytest.raises(HTTPException) as e:
            kapilar.check_plan(s, kullanici, VIDEO_SPEC, video_platform)
        assert e.value.status_code == 403
        assert e.value.detail == {"kod": "err.plan_kapsamiyor", "model": VIDEO_SPEC.id, "plan": "free"}
        assert depo_admin.plan_yaz(s, kullanici.id, "temel") and s.commit() is None
        yuklu = s.get(Kullanici, kullanici.id)
        assert yuklu is not None
        s.expire(yuklu)   # bağlı nesne yeniden okur — kimlik kapısının her istekte verdiği taze satır
        assert kapilar.check_plan(s, yuklu, VIDEO_SPEC, video_platform) == "temel"


def test_check_plan_lets_a_free_user_through_on_a_pro_model_when_the_key_is_theirs(depo_db, kullanici):
    """1b-A rota tarafında: eşik yalnız PLATFORM anahtarına uygulanır.

    Aynı kullanıcı, aynı model, tek fark anahtarın sahibi — biri 403, öteki
    geçiyor. `model_available`ın verdiği cevapla birebir aynı olmak zorunda:
    dökümde görünen model rotada 403 alırsa arayüz "seçilebilir 403" üretirdi.
    """
    pahali = dataclasses.replace(SPEC, plan="pro")
    with Session(depo_db) as s:
        with pytest.raises(HTTPException) as e:
            kapilar.check_plan(s, kullanici, pahali, _kimlikler(pahali, PLATFORM))
        assert e.value.status_code == 403 and e.value.detail["plan"] == "free"
        assert kapilar.check_plan(s, kullanici, pahali, _kimlikler(pahali, BENIM)) == "free"
        # Video AŞILMIYOR: kendi anahtarı bu kapıyı açmıyor (K7).
        with pytest.raises(HTTPException):
            kapilar.check_plan(s, kullanici, VIDEO_SPEC, _kimlikler(VIDEO_SPEC, BENIM))
