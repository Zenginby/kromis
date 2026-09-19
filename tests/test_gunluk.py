"""Yapısal günlük — `services/gunluk.py`, `services/istek_kimligi.py`, işçi olayları (Faz 2 / 9).

Dört soru:

  (i)   JSON SATIR — alanlar (`ts`, `seviye`, `logger`, `mesaj`, bağlam, `extra`,
        `hata`), bağlamın birleşmesi ve çözülmesi, metin biçimi, `KROMIS_GUNLUK_BICIMI`.
  (ii)  REDAKSİYON — anahtar hiçbir satırda geçmez: mesajda, alanda, iç içe
        sözlükte, istisna izinde, gizli AD taşıyan alanda; katalogdaki her gizli
        env adıyla (tests/test_errlog.py'nin mekanik testinin günlük ikizi).
  (iii) İSTEK KİMLİĞİ — gelen `X-Request-ID` kullanılır ve cevaba döner, yoksa
        `uuid4`, geçersizse yenisi; erişim satırı yöntem/yol/durum/süre/kullanıcı;
        `/health` DEBUG; ara katman sırası (istek kimliği en dışta).
  (iv)  İŞÇİ — `tek_tur` `is.alindi/basladi/bitti` (`is_id`, `sure_ms`), düşen iş
        `is.hata`; kalp turu eşiği aşınca `uyari`, aşmayınca susar.

Yakalama pytest `caplog` ile DEĞİL, doğrudan `kromis` köküne takılan bir
işleyiciyle (tests/test_admin.py'nin deyimi): kök yapılandırmadan bağımsız ve
`propagate=False`tan etkilenmez; JSON biçimleyici GERÇEK olan, satır
`json.loads` ile açılıyor — testin gördüğü, toplayıcının göreceğinin aynısı.
"""
from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app as appmod
import catalog
import providers
from services import gunluk, isci, istek_kimligi, koken, kuyruk

SAHTE_ANAHTAR = "sk-DUMMY" + "A1b2C3d4" * 4   # `DUMMY` damgası: .gitleaks.toml muafiyeti
KOK_GUNLUKCU = logging.getLogger(gunluk.KOK)


class _Yakalayici(logging.Handler):
    """`kromis` kökünün her kaydını JSON biçimleyiciden geçirip sözlük olarak biriktirir."""

    def __init__(self, seviye: int = logging.INFO) -> None:
        super().__init__(level=seviye)
        self.setFormatter(gunluk.JsonBicimleyici())
        self.satirlar: list[dict] = []
        self.ham: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        metin = self.format(record)
        self.ham.append(metin)
        self.satirlar.append(json.loads(metin))

    def olaylar(self, ad: str) -> list[dict]:
        return [s for s in self.satirlar if s.get("olay") == ad]


@pytest.fixture
def yakala() -> Iterator[_Yakalayici]:
    """Kök `kromis` günlükçüsüne INFO işleyicisi; Alembic'in kapattığı alt günlükçüleri açar."""
    y = _Yakalayici(logging.DEBUG)   # `/health` satırı DEBUG; onu da görmek isteyen test var
    eski_seviye = KOK_GUNLUKCU.level
    gunluk.kur(io.StringIO())   # `disabled` bayraklarını açar, kendi işleyicisi StringIO'ya
    KOK_GUNLUKCU.addHandler(y)
    KOK_GUNLUKCU.setLevel(logging.DEBUG)
    try:
        yield y
    finally:
        KOK_GUNLUKCU.removeHandler(y)
        KOK_GUNLUKCU.setLevel(eski_seviye)
        gunluk.sifirla()


def _kayit(mesaj: str = "m", **extra) -> logging.LogRecord:
    kayit = logging.LogRecord("kromis.deneme", logging.INFO, __file__, 1, mesaj, (), None)
    kayit.__dict__.update(extra)
    return kayit


def _json(kayit: logging.LogRecord) -> dict:
    return json.loads(gunluk.JsonBicimleyici().format(kayit))


# ── (i) JSON satır ───────────────────────────────────────────────────────

def test_a_record_becomes_one_json_object_with_the_documented_leading_fields():
    satir = _json(_kayit("selam", olay="deneme", sure_ms=12))
    assert list(satir)[:4] == ["ts", "seviye", "logger", "mesaj"]
    assert satir["seviye"] == "INFO" and satir["logger"] == "kromis.deneme" and satir["mesaj"] == "selam"
    assert satir["olay"] == "deneme" and satir["sure_ms"] == 12
    assert satir["ts"].endswith("+00:00"), "UTC, ISO 8601"
    assert "\n" not in gunluk.JsonBicimleyici().format(_kayit("a\nb")), "satır başına bir nesne"


def test_context_fields_ride_on_every_record_merge_when_nested_and_vanish_when_released():
    assert gunluk.aktif() == {}
    with gunluk.baglam(istek_id="i-1"):
        assert _json(_kayit())["istek_id"] == "i-1"
        with gunluk.baglam(is_id="j-1"):
            satir = _json(_kayit())
            assert (satir["istek_id"], satir["is_id"]) == ("i-1", "j-1"), "iç içe bağlam BİRLEŞİR"
        assert "is_id" not in _json(_kayit())
    assert "istek_id" not in _json(_kayit()) and gunluk.aktif() == {}


def test_bagla_and_coz_are_the_token_form_of_the_same_context():
    jeton = gunluk.bagla(istek_id="x")
    try:
        assert dict(gunluk.aktif()) == {"istek_id": "x"}
    finally:
        gunluk.coz(jeton)
    assert gunluk.aktif() == {}


def test_an_exception_record_carries_the_traceback_in_the_hata_field():
    try:
        raise ValueError("bum")
    except ValueError:
        kayit = logging.LogRecord("kromis.deneme", logging.ERROR, __file__, 1, "dustu", (), sys.exc_info())
    satir = _json(kayit)
    assert satir["seviye"] == "ERROR" and "ValueError: bum" in satir["hata"] and "Traceback" in satir["hata"]


def test_the_olay_helper_writes_the_event_name_as_message_and_field_and_drops_a_trailing_underscore(yakala):
    gunluk.olay(logging.getLogger("kromis.deneme"), "admin.is_iptal", is_=1, sahip="a")
    (satir,) = yakala.satirlar
    assert (satir["mesaj"], satir["olay"], satir["is"], satir["sahip"]) == ("admin.is_iptal", "admin.is_iptal", 1, "a")
    assert "is_" not in satir, "`is` Python anahtar sözcüğü: `is_=` alanı `is` olarak düşer"


def test_the_text_format_is_one_readable_line_with_fields_appended_as_key_value():
    with gunluk.baglam(istek_id="i-1"):
        metin = gunluk.MetinBicimleyici().format(_kayit("selam", olay="deneme", n=3))
    assert metin.endswith("INFO kromis.deneme selam istek_id=i-1 olay=deneme n=3"), metin


def test_the_format_variable_defaults_to_json_accepts_metin_and_rejects_anything_else():
    assert gunluk.bicim({}) == gunluk.BICIM_JSON
    assert gunluk.bicim({gunluk.BICIM_ENV: ""}) == gunluk.BICIM_JSON
    assert gunluk.bicim({gunluk.BICIM_ENV: " Metin "}) == gunluk.BICIM_METIN
    with pytest.raises(ValueError, match=gunluk.BICIM_ENV):
        gunluk.bicim({gunluk.BICIM_ENV: "yaml"})
    assert isinstance(gunluk.bicimleyici(gunluk.BICIM_METIN), gunluk.MetinBicimleyici)
    assert isinstance(gunluk.bicimleyici(gunluk.BICIM_JSON), gunluk.JsonBicimleyici)


def test_kur_installs_exactly_one_handler_with_the_chosen_format_and_is_idempotent(monkeypatch):
    eski = list(KOK_GUNLUKCU.handlers)
    for h in eski:
        KOK_GUNLUKCU.removeHandler(h)
    akim = io.StringIO()
    try:
        monkeypatch.setenv(gunluk.BICIM_ENV, "metin")
        kok = gunluk.kur(akim)
        assert kok is KOK_GUNLUKCU and len(kok.handlers) == 1
        assert isinstance(kok.handlers[0].formatter, gunluk.MetinBicimleyici), "biçim ortamdan"
        assert gunluk.kur(io.StringIO()) is kok and len(kok.handlers) == 1, "ikinci çağrı eklemez"
        assert kok.propagate is False and kok.level == logging.INFO
        logging.getLogger("kromis.deneme").info("merhaba")
        assert akim.getvalue().rstrip().endswith("INFO kromis.deneme merhaba")
        monkeypatch.setenv(gunluk.BICIM_ENV, "xml")
        assert gunluk.kur(io.StringIO()) is kok, "kuruluyken bozuk değer okunmaz bile (işleyici var)"
    finally:
        for h in list(KOK_GUNLUKCU.handlers):
            KOK_GUNLUKCU.removeHandler(h)
        for h in eski:
            KOK_GUNLUKCU.addHandler(h)


# ── (i-b) kök günlükçü ve uvicorn (Faz 2 / 10) ──────────────────────────

@pytest.fixture
def kok_temiz() -> Iterator[None]:
    """Kökün ve uvicorn günlükçülerinin işleyici/yayılma durumunu test sonunda geri koyar."""
    kok = logging.getLogger()
    eski_kok = list(kok.handlers)
    eski_uvicorn = {ad: (list(logging.getLogger(ad).handlers), logging.getLogger(ad).propagate,
                         logging.getLogger(ad).level, logging.getLogger(ad).disabled)
                    for ad in (*gunluk.UVICORN_GUNLUKCULERI, "uvicorn.access")}
    for h in eski_kok:
        kok.removeHandler(h)
    try:
        yield
    finally:
        for h in list(kok.handlers):
            kok.removeHandler(h)
        for h in eski_kok:
            kok.addHandler(h)
        for ad, (isleyiciler, yayilma, seviye, kapali) in eski_uvicorn.items():
            g = logging.getLogger(ad)
            g.handlers[:] = isleyiciler
            g.propagate = yayilma
            g.setLevel(seviye)
            g.disabled = kapali


def test_third_party_warnings_reach_stdout_as_redacted_json_lines_and_their_info_stays_silent(kok_temiz):
    """9'da SQLAlchemy/httpx WARNING'i Python'un son çare işleyicisinden stderr'e düz ve REDAKSİYONSUZ
    düşüyordu; `kur` köke aynı biçimleyiciyi takar. Kökün seviyesi WARNING kalır: üçüncü partinin
    INFO'su (httpx her isteği INFO yazar) akıma girmez."""
    akim = io.StringIO()
    gunluk.kur(akim)
    logging.getLogger("sqlalchemy.pool").warning("havuz doldu OPENAI_API_KEY=DUMMY-plain-value-12345")
    logging.getLogger("httpx").info("HTTP Request: GET https://x.example")
    satirlar = [json.loads(s) for s in akim.getvalue().splitlines()]
    assert len(satirlar) == 1, akim.getvalue()
    assert satirlar[0]["logger"] == "sqlalchemy.pool" and satirlar[0]["seviye"] == "WARNING"
    assert "DUMMY-plain-value-12345" not in akim.getvalue() and "[REDACTED_API_KEY]" in satirlar[0]["mesaj"]


def test_uvicorns_loggers_are_stripped_and_propagate_so_the_asgi_traceback_is_json_and_redacted(kok_temiz):
    """uvicorn kendi günlükçülerine kendi işleyicisini takar (stderr, düz metin): "Exception in ASGI
    application" izi anahtar taşıyabilir ve redaksiyonsuz çıkıyordu. `kur` üç günlükçünün
    işleyicilerini boşaltır ve köke yayar; INFO seviyeleri uvicorn'un koyduğu gibi geçer."""
    for ad in (*gunluk.UVICORN_GUNLUKCULERI, "uvicorn.access"):
        g = logging.getLogger(ad)
        g.addHandler(logging.StreamHandler(io.StringIO()))
        g.propagate = False
        g.setLevel(logging.INFO)
        g.disabled = True      # Alembic `fileConfig`in bıraktığı hâl (takımda ölçüldü): `kur` açmalı
    akim = io.StringIO()
    gunluk.kur(akim)
    for ad in gunluk.UVICORN_GUNLUKCULERI:
        assert logging.getLogger(ad).handlers == [] and logging.getLogger(ad).propagate is True, ad
    # `uvicorn.access` DOKUNULMAZ: `--no-access-log` onu işleyicisiz + `propagate=False` bırakır;
    # köke yaysaydık kapatılan erişim satırı JSON olarak geri gelirdi (ölçüldü).
    erisim = logging.getLogger("uvicorn.access")
    erisim.handlers.clear()
    erisim.propagate = False
    gunluk.kur(akim)
    assert erisim.propagate is False and "uvicorn.access" not in gunluk.UVICORN_GUNLUKCULERI
    erisim.info('127.0.0.1 - "GET /health HTTP/1.1" 200')
    assert akim.getvalue() == "", "kapatılmış erişim günlüğü köke sızmaz"
    logging.getLogger("uvicorn.error").info("Started server process [1]")
    try:
        raise RuntimeError("iz FAL_KEY=DUMMY-plain-value-12345")
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")
    satirlar = [json.loads(s) for s in akim.getvalue().splitlines()]
    assert [(s["logger"], s["seviye"]) for s in satirlar] == [("uvicorn.error", "INFO"), ("uvicorn.error", "ERROR")]
    assert "RuntimeError" in satirlar[1]["hata"] and "DUMMY-plain-value-12345" not in akim.getvalue()


def test_the_root_handler_is_installed_once_and_comes_back_after_alembic_wipes_the_root(kok_temiz, monkeypatch):
    """İdempotent: iki `kur` tek işaretli işleyici. Alembic `fileConfig` (testlerde aynı süreç) kökün
    işleyicilerini siler — bir sonraki `kur` bizimkini görmez ve yeniden takar. Akım verilmemişse
    işleyici `sys.stdout`u EMİT ANINDA çözer: pytest'in değiştirdiği stdout'a yazar, kapanmış eskiye değil."""
    gunluk.kur(io.StringIO())
    gunluk.kur(io.StringIO())
    isaretli = [h for h in logging.getLogger().handlers if getattr(h, gunluk.KOK_ISARETI, False)]
    assert len(isaretli) == 1 and gunluk.kok_isleyicisi() is isaretli[0]
    logging.getLogger().handlers.clear()          # `fileConfig`in yaptığı
    assert gunluk.kok_isleyicisi() is None
    gunluk.kur(io.StringIO())
    assert gunluk.kok_isleyicisi() is not None
    # Dinamik stdout: kromis kökünün işleyicisi StringIO'ya sabit, kökünki `sys.stdout`a.
    logging.getLogger().handlers.clear()
    gunluk.kur()
    yeni_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", yeni_stdout)
    logging.getLogger("ucuncu.parti").warning("dinamik")
    assert json.loads(yeni_stdout.getvalue())["mesaj"] == "dinamik"


def test_the_platform_key_logger_lives_under_the_kromis_namespace():
    """9'un devri 6: `services.platform_anahtari` günlükçüsü `kromis.*` dışındaydı, uyarısı JSON'a girmiyordu."""
    from services import platform_anahtari
    assert platform_anahtari._log.name == "kromis.platform"


# ── (ii) redaksiyon ──────────────────────────────────────────────────────

def test_a_seeded_key_never_reaches_the_line_wherever_it_sits():
    """Mesaj, `extra` alanı, iç içe sözlük, liste, istisna izi — hepsi `errlog.redact_secrets`ten."""
    try:
        raise RuntimeError(f"cevap: {SAHTE_ANAHTAR}")
    except RuntimeError:
        kayit = logging.LogRecord("kromis.deneme", logging.ERROR, __file__, 1,
                                  f"anahtar {SAHTE_ANAHTAR} gitti", (), sys.exc_info())
    kayit.__dict__.update({"alan": SAHTE_ANAHTAR, "ic": {"derin": [SAHTE_ANAHTAR, 1]},
                           "ek": f"KROMIS_PLATFORM_OPENAI_API_KEY={'x' * 12}"})
    metin = gunluk.JsonBicimleyici().format(kayit)
    assert SAHTE_ANAHTAR not in metin and "xxxxxxxxxxxx" not in metin, metin
    satir = json.loads(metin)
    assert satir["alan"] == "[REDACTED_API_KEY]" and satir["ic"]["derin"] == ["[REDACTED_API_KEY]", 1]
    assert "[REDACTED_API_KEY]" in satir["hata"]
    assert SAHTE_ANAHTAR not in gunluk.MetinBicimleyici().format(kayit)


def test_a_field_whose_name_is_a_secret_env_name_is_masked_regardless_of_the_values_shape():
    """Kısa/atipik değer çıplak desenden kaçar; AD kuralı yakalar (errlog'un 4. deseninin ad yarısı)."""
    satir = _json(_kayit(OPENAI_API_KEY="kisa", ic={"FAL_KEY": "abc"}, sayi=3))
    assert satir["OPENAI_API_KEY"] == "[REDACTED_API_KEY]" and satir["ic"]["FAL_KEY"] == "[REDACTED_API_KEY]"
    assert satir["sayi"] == 3, "masum alan dokunulmaz"


@pytest.mark.parametrize("ad", sorted(catalog.secret_env_names()))
def test_every_catalog_secret_name_is_redacted_in_a_log_message_too(ad):
    """`errlog`un mekanik testinin günlük ikizi: `AD=değer` mesajda, sözlük biçimi (`{'AD': …}`) alanda,
    adın kendisi alan adı olarak — üçü de sansürlenir."""
    deger = "Gizli" + "9" * 20
    satir = _json(_kayit(f"{ad}={deger}", alan=repr({ad: deger}), ic={ad: deger}, **{ad: deger}))
    dokum = json.dumps(satir)
    assert deger not in dokum, dokum


def test_the_json_line_stays_valid_json_after_redaction():
    """Sözlük deseni anahtarıyla birlikte silerdi; değer değer redaksiyon satırı bozmaz (gerekçe gunluk.py)."""
    kayit = _kayit("x", ic={"OPENAI_API_KEY": "sk-" + "b" * 30, "sonraki": 1}, son="ok")
    metin = gunluk.JsonBicimleyici().format(kayit)
    assert json.loads(metin)["son"] == "ok" and json.loads(metin)["ic"]["sonraki"] == 1


# ── (iii) istek kimliği ──────────────────────────────────────────────────

def _istemci() -> TestClient:
    return TestClient(appmod.app)


def test_an_incoming_request_id_is_kept_and_echoed_and_a_missing_one_is_generated(yakala):
    c = _istemci()
    cevap = c.get("/yok", headers={istek_kimligi.BASLIK: "vekil-123"})
    assert cevap.status_code == 404 and cevap.headers[istek_kimligi.BASLIK] == "vekil-123"
    cevap = c.get("/yok")
    uretilen = cevap.headers[istek_kimligi.BASLIK]
    assert uuid.UUID(uretilen).version == 4
    assert [s["istek_id"] for s in yakala.olaylar("istek")] == ["vekil-123", uretilen]


@pytest.mark.parametrize("bozuk", ["", "a b", "x" * 129, "satır\nsonu"])
def test_an_unusable_incoming_request_id_is_replaced_not_rejected(bozuk):
    assert not istek_kimligi.gecerli(bozuk) and not istek_kimligi.gecerli("ünlü")
    cevap = _istemci().get("/yok", headers={istek_kimligi.BASLIK: bozuk.encode("latin-1", "replace").decode("latin-1")})
    assert cevap.status_code == 404
    assert uuid.UUID(cevap.headers[istek_kimligi.BASLIK]).version == 4
    assert istek_kimligi.gecerli("01J8Z0K9XQ") and istek_kimligi.gecerli("req-abc_1:2/3+4=")


def test_the_access_line_has_method_path_status_duration_and_no_query_string(yakala):
    cevap = _istemci().get("/yok?gizli=deger")
    (satir,) = yakala.olaylar("istek")
    assert (satir["logger"], satir["yontem"], satir["rota"], satir["durum"]) == ("kromis.istek", "GET", "/yok", 404)
    assert isinstance(satir["sure_ms"], float) and satir["sure_ms"] >= 0
    assert satir["kullanici_id"] is None and satir["istek_id"] == cevap.headers[istek_kimligi.BASLIK]
    assert "gizli" not in yakala.ham[-1]


@pytest.mark.usefixtures("depo_db")
def test_the_access_line_names_the_resolved_user(yakala, kullanici):
    cevap = _istemci().get("/api/isler")
    assert cevap.status_code == 200
    (satir,) = yakala.olaylar("istek")
    assert satir["kullanici_id"] == str(kullanici.id) and satir["durum"] == 200


def test_the_health_probe_and_static_files_log_at_debug_so_a_30s_probe_does_not_flood(yakala):
    c = _istemci()
    assert c.get("/health").headers.get(istek_kimligi.BASLIK)
    c.get("/static/core.js")
    c.get("/yok")
    seviyeler = {s["rota"]: s["seviye"] for s in yakala.olaylar("istek")}
    assert seviyeler == {"/health": "DEBUG", "/static/core.js": "DEBUG", "/yok": "INFO"}


def test_the_request_id_is_in_context_inside_the_route_and_gone_after(yakala, monkeypatch):
    from routers import saglik
    gorulen: list[str | None] = []
    monkeypatch.setattr(saglik, "veri_dizini_yazilabilir", lambda d: gorulen.append(istek_kimligi.aktif()) or True)
    cevap = _istemci().get("/health", headers={istek_kimligi.BASLIK: "rota-ici"})
    assert gorulen == ["rota-ici"], "rota iş parçacığı havuzunda koşar, bağlamın kopyası oraya gider"
    assert cevap.headers[istek_kimligi.BASLIK] == "rota-ici"
    assert istek_kimligi.aktif() is None


def test_a_route_that_raises_still_gets_an_access_line_with_status_500(yakala, monkeypatch):
    from routers import saglik

    def _patla(d):
        raise RuntimeError("bum")
    monkeypatch.setattr(saglik, "veri_dizini_yazilabilir", _patla)
    cevap = TestClient(appmod.app, raise_server_exceptions=False).get("/health")
    assert cevap.status_code == 500
    (satir,) = [s for s in yakala.olaylar("istek") if s["rota"] == "/health"]
    assert satir["durum"] == 500


def test_a_cross_origin_rejection_still_carries_a_request_id_because_the_middleware_is_outermost(yakala):
    cevap = _istemci().post("/api/palettes/x", headers={"Sec-Fetch-Site": "cross-site",
                                                        istek_kimligi.BASLIK: "koken-403"})
    assert cevap.status_code == 403 and cevap.headers[istek_kimligi.BASLIK] == "koken-403"
    (satir,) = yakala.olaylar("istek")
    assert satir["durum"] == 403 and satir["istek_id"] == "koken-403"


def test_the_middleware_order_is_request_id_then_origin_then_language():
    """Belge §9: istek kimliği → köken → dil → rota. Starlette listede İLK olanı en dışa koyar."""
    from services import dil
    zincir = [m.kwargs.get("dispatch") for m in appmod.app.user_middleware]
    assert zincir[:3] == [istek_kimligi.istek_kimligi, koken.koken_kapisi, dil.dil_baglami], zincir


def test_the_image_turns_uvicorns_access_log_off_because_the_app_writes_its_own():
    import os
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Dockerfile"),
              encoding="utf-8") as f:
        dockerfile = f.read()
    cmd = [s for s in dockerfile.splitlines() if s.startswith("CMD")]
    assert len(cmd) == 1 and "--no-access-log" in cmd[0], cmd


# ── (iv) işçi ────────────────────────────────────────────────────────────

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))


@pytest.fixture
def isci_ortami(depo_db, tmp_path):
    """`tests/test_isci.py`nin en küçük düzeni: boş kuyruk, yerel depo, `data_dir = tmp_path`."""
    import dataclasses
    import os

    from sqlalchemy import text

    from services import ayar, dosya
    with depo_db.begin() as c:
        c.execute(text("DELETE FROM isler"))
        c.execute(text("DELETE FROM isciler"))
    yerlesim = dataclasses.replace(ayar.Ayarlar.varsayilan(), data_dir=str(tmp_path),
                                   output_dir=os.path.join(str(tmp_path), "output"),
                                   assets_dir=os.path.join(str(tmp_path), "assets"))
    return dosya.YerelDepo(str(tmp_path)), yerlesim


def _is_ekle(db, kullanici_id: uuid.UUID) -> uuid.UUID:
    from services import zaman
    is_ = kuyruk.ekle(db, kullanici_id, "generate",
                      {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1,
                       "folder_id": None, "session_id": None}, catalog.DEFAULT_IMAGE_MODEL, 1, an=zaman.an())
    db.commit()
    return is_.id


def test_a_job_run_emits_taken_started_and_done_events_all_carrying_the_job_id(
        yakala, db_oturumu, kullanici, isci_ortami, monkeypatch):
    depo, yerlesim = isci_ortami
    monkeypatch.setattr(providers, "generate", lambda *a, **k: [PNG])
    is_id = _is_ekle(db_oturumu, kullanici.id)
    isci_id = uuid.uuid4()

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim, isci_id=isci_id) is True

    olaylar = [s["olay"] for s in yakala.satirlar if s["logger"] == "kromis.is"]
    assert olaylar == ["is.alindi", "is.basladi", "is.bitti"]
    alindi, basladi, bitti = (s for s in yakala.satirlar if s["logger"] == "kromis.is")
    assert alindi["is_id"] == str(is_id) and alindi["isci_id"] == str(isci_id) and alindi["bekleme_ms"] >= 0
    assert (alindi["tur"], alindi["model"], alindi["kullanici_id"]) == ("generate", catalog.DEFAULT_IMAGE_MODEL,
                                                                         str(kullanici.id))
    assert basladi["is_id"] == str(is_id) and basladi["kullanici_id"] == str(kullanici.id), "bağlamdan"
    assert bitti["is_id"] == str(is_id) and isinstance(bitti["sure_ms"], int) and bitti["sure_ms"] >= 0
    assert gunluk.aktif() == {}, "iş bitince bağlam çözülür"


def test_a_failing_job_emits_is_hata_and_a_seeded_provider_secret_never_reaches_the_output(
        yakala, db_oturumu, kullanici, isci_ortami, monkeypatch):
    import azure_client as ac
    depo, yerlesim = isci_ortami

    def _patla(*a, **k):
        raise ac.ImageError(f"saglayici reddetti: {SAHTE_ANAHTAR}")
    monkeypatch.setattr(providers, "generate", _patla)
    is_id = _is_ekle(db_oturumu, kullanici.id)

    assert isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim) is True
    olaylar = [s["olay"] for s in yakala.satirlar if s["logger"] == "kromis.is"]
    assert olaylar == ["is.alindi", "is.basladi", "is.hata"]
    assert all(s["is_id"] == str(is_id) for s in yakala.satirlar if s["logger"] == "kromis.is")
    assert SAHTE_ANAHTAR not in "\n".join(yakala.ham)


def test_an_unexpected_exception_in_a_job_is_logged_with_the_traceback_under_the_job_id(
        yakala, db_oturumu, kullanici, isci_ortami, monkeypatch):
    depo, yerlesim = isci_ortami

    def _patla(*a, **k):
        raise KeyError("beklenmedik")
    monkeypatch.setattr(providers, "generate", _patla)
    is_id = _is_ekle(db_oturumu, kullanici.id)
    isci.tek_tur(db_oturumu, depo, ayarlar=yerlesim)
    (iz,) = yakala.olaylar("is.istisna")
    assert iz["seviye"] == "ERROR" and iz["is_id"] == str(is_id) and "KeyError" in iz["hata"]
    assert [s["olay"] for s in yakala.satirlar if s["logger"] == "kromis.is"][-1] == "is.hata"


def test_the_queue_alert_fires_past_either_threshold_and_stays_silent_below(db_oturumu, kullanici, isci_ortami):
    import datetime as dt

    from sqlalchemy import text

    from services import zaman
    an = zaman.an()
    assert isci.kuyruk_uyarisi(db_oturumu, an) is None, "boş kuyruk susar"
    is_id = _is_ekle(db_oturumu, kullanici.id)
    assert isci.kuyruk_uyarisi(db_oturumi := db_oturumu, an) is None, "bir taze iş susar"
    # En eski bekleyen 11 dk: derinlik 1 ama yaş eşiği aşıldı.
    db_oturumi.execute(text("UPDATE isler SET olusturuldu = :t WHERE id = :id"),
                       {"t": an - dt.timedelta(minutes=11), "id": is_id})
    db_oturumi.commit()
    uyari = isci.kuyruk_uyarisi(db_oturumi, an)
    assert uyari is not None and uyari["derinlik"] == 1 and uyari["en_eski_bekleyen_sn"] >= 660
    assert (uyari["esik_derinlik"], uyari["esik_en_eski_sn"]) == (isci.UYARI_KUYRUK_DERINLIGI,
                                                                    isci.UYARI_EN_ESKI_BEKLEYEN_SN)
    # Derinlik eşiği: 21 taze iş, hepsi genç.
    db_oturumi.execute(text("UPDATE isler SET olusturuldu = :t"), {"t": an})
    for _ in range(isci.UYARI_KUYRUK_DERINLIGI):
        _is_ekle(db_oturumi, kullanici.id)
    uyari = isci.kuyruk_uyarisi(db_oturumi, an)
    assert uyari is not None and uyari["derinlik"] == isci.UYARI_KUYRUK_DERINLIGI + 1
    assert (isci.UYARI_KUYRUK_DERINLIGI, isci.UYARI_EN_ESKI_BEKLEYEN_SN) == (20, 600), "isletme.md § 6"


def test_the_worker_process_writes_json_lines_to_stdout_with_the_chosen_format(tmp_path, monkeypatch):
    """Süreç düzeyi: `isci.py` `gunluk.kur`u ilk iş olarak çağırır — kapı hatası bile JSON satır;
    bozuk `KROMIS_GUNLUK_BICIMI` işleyicisiz tek satır + çıkış 2."""
    import os
    ortam = {k: v for k, v in os.environ.items() if not k.startswith("KROMIS_NESNE_DEPO_")}
    ortam.update({"KROMIS_DATA_DIR": str(tmp_path)})
    ortam.pop("DATABASE_URL", None)
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sonuc = subprocess.run([sys.executable, "isci.py", "--tek-tur"], cwd=kok, env=ortam,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert sonuc.returncode == 2
    (satir,) = [json.loads(s) for s in sonuc.stdout.splitlines()]
    assert satir["olay"] == "isci.hata" and satir["seviye"] == "ERROR" and "DATABASE_URL" in satir["mesaj"]

    ortam[gunluk.BICIM_ENV] = "xml"
    sonuc = subprocess.run([sys.executable, "isci.py", "--tek-tur"], cwd=kok, env=ortam,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert sonuc.returncode == 2 and gunluk.BICIM_ENV in sonuc.stderr and sonuc.stdout == ""
