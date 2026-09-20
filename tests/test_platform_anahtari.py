"""Platform sahipli sağlayıcı anahtarları (Faz 2 / 6; docs/faz2-kuyruk-anahtarlar-depolama.md §6).

  (i)   ÇÖZÜM SIRASI — ad ad kullanıcı → platform → yok; boş kullanıcı değeri
        platformu gölgelemez; `kaynak` anahtar adını eşler, Azure yüzeyleri
        görselin anahtarına düşer.
  (ii)  BEKÇİ — `ADLAR` katalogdan türeyen kümeyle BİREBİR (eski BYOK dışarıda);
        bilinmeyen `KROMIS_PLATFORM_X` bir kez bildirilir, değeri günlüğe girmez.
  (iii) `GET /api/settings` — `kaynaklar` her sağlayıcı için kullanici / platform /
        null; anahtar hiçbir biçimde dönmez; kendi anahtarı platformu ezer;
        `anahtar_sil` platforma düşürür; boş gizli kutu yine "dokunmadım".
  (iv)  UÇTAN UCA — anahtarsız kullanıcı platform anahtarıyla üretir, kendi
        anahtarını girince onunla, silince yine platformla (sahte istemci
        `Authorization` kaydeder: `[platform, kullanici, platform]`); satırda
        `anahtar_kaynagi`; ne kullanıcı ne platform → 409 ve iş doğmaz; ekilen
        platform anahtarı DB dökümünde, günlükte ve cevaplarda YOK.

Kapı GERÇEK (`gercek_anahtar`): conftest'in `check_anahtar` yaması burada kurulmaz.
"""
from __future__ import annotations

import base64
import logging
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import app as appmod
import catalog
import errlog
from services import defter, depo_kimlik_bilgisi, kapilar, platform_anahtari, tablolar

pytestmark = [pytest.mark.usefixtures("depo_db"), pytest.mark.gercek_anahtar]

PLATFORM_GEMINI = "PLATFORM-GIZLI-GEMINI-9f8e7d6c5b4a"
PLATFORM_AZURE = "PLATFORM-GIZLI-AZURE-1a2b3c4d5e6f"
PLATFORM_AZURE_URL = "https://platform-kaynak.openai.azure.com/openai/v1/"
KULLANICI_AZURE = "KULLANICI-KENDI-ANAHTARI-0011"
GORSEL = {"prompt": "kedi", "size": "1024x1024", "quality": "low", "n": 1}


@pytest.fixture
def client():
    return TestClient(appmod.app)


@pytest.fixture(autouse=True)
def _temiz_ortam(monkeypatch):
    """Geliştiricinin kabuğunda duran bir `KROMIS_PLATFORM_*` testi ele geçirmesin; bildirim kaydı sıfır."""
    for ad in list(os.environ):
        if ad.startswith(platform_anahtari.ONEK):
            monkeypatch.delenv(ad)
    platform_anahtari.bilinmeyenleri_sifirla()
    yield
    platform_anahtari.bilinmeyenleri_sifirla()


def _platform_azure(monkeypatch) -> None:
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_API_KEY", PLATFORM_AZURE)
    monkeypatch.setenv(platform_anahtari.ONEK + "AZURE_IMAGE_BASE_URL", PLATFORM_AZURE_URL)


# ── (i) çözüm sırası ────────────────────────────────────────────────────

def test_the_user_row_wins_over_the_platform_value_name_by_name():
    ortam = {"KROMIS_PLATFORM_GEMINI_API_KEY": "p-gemini", "KROMIS_PLATFORM_OPENAI_API_KEY": "p-openai",
             "KROMIS_PLATFORM_FAL_KEY": "p-fal", "BASKA": "x"}
    sozluk, kaynaklar = platform_anahtari.birlestir({"OPENAI_API_KEY": "k-openai"}, ortam)
    assert sozluk == {"GEMINI_API_KEY": "p-gemini", "OPENAI_API_KEY": "k-openai", "FAL_KEY": "p-fal"}
    assert kaynaklar == {"GEMINI_API_KEY": "platform", "OPENAI_API_KEY": "kullanici", "FAL_KEY": "platform"}
    # Ne kullanıcı ne platform: ad sözlükte HİÇ yok (credstore `.get(ad, "")` ile okur).
    assert "ANTHROPIC_API_KEY" not in sozluk and platform_anahtari.kaynak("anthropic", sozluk) is None


def test_an_empty_or_blank_user_or_platform_value_counts_as_absent():
    ortam = {"KROMIS_PLATFORM_GEMINI_API_KEY": "  p-gemini  ", "KROMIS_PLATFORM_FAL_KEY": "   "}
    sozluk, kaynaklar = platform_anahtari.birlestir({"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}, ortam)
    assert sozluk == {"GEMINI_API_KEY": "p-gemini"} and kaynaklar == {"GEMINI_API_KEY": "platform"}


def test_kaynak_reads_the_key_env_and_the_azure_surfaces_fall_back_to_the_image_key():
    k = platform_anahtari.kimlikler(
        {"AZURE_IMAGE_API_KEY": "kendi", "AZURE_IMAGE_BASE_URL": "https://a.openai.azure.com/openai/v1/"},
        {"KROMIS_PLATFORM_GEMINI_API_KEY": "p", "KROMIS_PLATFORM_AZURE_FOUNDRY_BASE_URL": "https://f/"})
    assert isinstance(k, dict) and k.kaynaklar["AZURE_IMAGE_API_KEY"] == "kullanici"
    assert platform_anahtari.kaynak("azure_image", k) == "kullanici"
    assert platform_anahtari.kaynak("gemini", k) == "platform"
    # Foundry ve sohbet kendi anahtarını taşımıyor → görselin anahtarı, onun kaynağı; adres sayılmaz.
    assert platform_anahtari.kaynak("azure_foundry", k) == "kullanici"
    assert platform_anahtari.kaynak("azure_chat", k) == "kullanici"
    assert platform_anahtari.kaynak("openai", k) is None
    assert platform_anahtari.kaynak("yok-boyle-kimlik", k) is None
    # Düz sözlük (kaynaksız): her ad kullanıcının sayılır — platform toplamına girmesin.
    assert platform_anahtari.kaynak("openai", {"OPENAI_API_KEY": "x"}) == "kullanici"


# ── (ii) bekçiler ───────────────────────────────────────────────────────

def test_the_platform_name_set_is_exactly_the_catalogs_and_excludes_the_legacy_byok_names():
    """CLAUDE.md § 5: elle liste yok. Aynı küme kataloğun üç alanından yeniden kurulur;
    `.env.example` 1d'nin bekçisi (test_docker_kapisi) öneki aynı kümeye takar."""
    katalog = {c.key_env for c in catalog.CREDENTIALS}
    katalog |= {c.url_env for c in catalog.CREDENTIALS if c.url_env}
    katalog |= {m.wire_from_env for m in catalog.CHAT_MODELS if m.wire_from_env}
    assert platform_anahtari.ADLAR == frozenset(katalog)
    assert not platform_anahtari.ADLAR & set(depo_kimlik_bilgisi.ESKI_BYOK)
    assert platform_anahtari.ADLAR < depo_kimlik_bilgisi.ADLAR
    assert platform_anahtari.ONEK == "KROMIS_PLATFORM_"


def test_an_unknown_platform_variable_is_reported_once_and_ignored_without_its_value():
    # `depo_db` fixture'ı Alembic'i AYNI süreçte koşturuyor ve `alembic/env.py`nin `fileConfig`i
    # o ana kadar yaratılmış her günlükçüyü KAPATIYOR (`disable_existing_loggers`) — modül
    # günlükçüsü de dâhil (ölçüldü: kayıt sıfır). Üretimde göç ayrı süreçte (tools/goc.py),
    # sorun yalnız testin; burada yeniden açılıyor. Günlükçü `kromis.platform` (Faz 2 / 10) ve
    # `kromis` kökü köke YAYILMAZ (gunluk.kur) — caplog kökte dinler; kendi işleyicimizi takıyoruz.
    gunlukcu = logging.getLogger("kromis.platform")
    gunlukcu.disabled = False
    kayitlar: list[logging.LogRecord] = []

    class _Topla(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            kayitlar.append(record)

    isleyici = _Topla(logging.WARNING)
    gunlukcu.addHandler(isleyici)
    eski_seviye = gunlukcu.level
    gunlukcu.setLevel(logging.WARNING)
    ortam = {"KROMIS_PLATFORM_GEMINI_KEY": "YANLIS-AD-DEGERI-xyz", "KROMIS_PLATFORM_FAL_KEY": "p-fal"}
    try:
        assert platform_anahtari.platform_sozlugu(ortam) == {"FAL_KEY": "p-fal"}
        assert platform_anahtari.platform_sozlugu(ortam) == {"FAL_KEY": "p-fal"}
        assert platform_anahtari.platform_sozlugu(ortam) == {"FAL_KEY": "p-fal"}
    finally:
        gunlukcu.removeHandler(isleyici)
        gunlukcu.setLevel(eski_seviye)
    uyarilar = [r for r in kayitlar if "KROMIS_PLATFORM_GEMINI_KEY" in r.getMessage()]
    assert len(uyarilar) == 1, "bilinmeyen ad her okumada değil BİR kez bildirilir"
    assert "FAL_KEY" in uyarilar[0].getMessage(), "uyarı tanınan adları sayar (yazım yardımı)"
    metin = "\n".join(r.getMessage() for r in kayitlar)
    assert "YANLIS-AD-DEGERI" not in metin and "p-fal" not in metin, "değer günlüğe girmez"


# ── (iii) GET/POST /api/settings ────────────────────────────────────────

def test_get_settings_reports_the_source_per_provider_and_never_the_platform_key(client, monkeypatch):
    monkeypatch.setenv(platform_anahtari.ONEK + "GEMINI_API_KEY", PLATFORM_GEMINI)
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["providers"]["gemini"] is True and body["kaynaklar"]["gemini"] == "platform"
    assert body["providers"]["openai"] is False and body["kaynaklar"]["openai"] is None
    assert set(body["kaynaklar"]) == {c.id for c in catalog.CREDENTIALS}
    assert set(body["kaynaklar"].values()) <= {"kullanici", "platform", None}
    assert PLATFORM_GEMINI not in r.text and PLATFORM_GEMINI[-6:] not in r.text
    # Video şeridi Gemini'yi paylaşıyor: Veo modeli platform anahtarıyla "kullanılabilir".
    assert any(m["configured"] for m in body["video_models"] if m["provider"] == "gemini")


def test_a_users_own_key_overrides_the_platform_and_deleting_it_falls_back_to_the_platform(
        client, monkeypatch, db_oturumu, kullanici):
    monkeypatch.setenv(platform_anahtari.ONEK + "GEMINI_API_KEY", PLATFORM_GEMINI)
    r = client.post("/api/settings", json={"gemini_api_key": "AIza-KULLANICININ-KENDI-anahtari"})
    assert r.status_code == 200 and r.json()["kaynaklar"]["gemini"] == "kullanici"
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {"GEMINI_API_KEY": "AIza-KULLANICININ-KENDI-anahtari"}

    # Boş gizli kutu hâlâ "dokunmadım" (yalnızca-yazılır formun kuralı korunuyor).
    r = client.post("/api/settings", json={"gemini_api_key": ""})
    assert r.status_code == 200 and r.json()["kaynaklar"]["gemini"] == "kullanici"

    # Açık silme → satır gider → platforma DÜŞER; `providers` hâlâ True (üretim sürer).
    r = client.post("/api/settings", json={"anahtar_sil": ["gemini"]})
    assert r.status_code == 200, r.text
    assert r.json()["kaynaklar"]["gemini"] == "platform" and r.json()["providers"]["gemini"] is True
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {}
    g = client.get("/api/settings").json()
    assert g["kaynaklar"]["gemini"] == "platform"
    assert "KULLANICININ" not in r.text and PLATFORM_GEMINI not in r.text

    # Platform yokken silmek → kaynak null, `providers` False.
    monkeypatch.delenv(platform_anahtari.ONEK + "GEMINI_API_KEY")
    client.post("/api/settings", json={"gemini_api_key": "AIza-yeniden"})
    r = client.post("/api/settings", json={"anahtar_sil": ["gemini"]})
    assert r.json()["kaynaklar"]["gemini"] is None and r.json()["providers"]["gemini"] is False


def test_deleting_azure_drops_the_key_and_the_address_together(client, db_oturumu, kullanici):
    """Azure'da anahtar + adres tek kimlik: yalnız anahtar silinse kullanıcının adresi platformun
    anahtarıyla eşleşir ve istek yanlış hosta giderdi (credstore'un "sessiz düşme yok" kararı)."""
    client.post("/api/settings", json={"api_key": KULLANICI_AZURE, "base_url": "https://k.openai.azure.com/openai/v1/"})
    assert set(depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id)) == {"AZURE_IMAGE_API_KEY", "AZURE_IMAGE_BASE_URL"}
    r = client.post("/api/settings", json={"anahtar_sil": ["azure_image"]})
    assert r.status_code == 200 and r.json()["configured"] is False and r.json()["endpoint"] is None
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {}


def test_an_unknown_id_in_anahtar_sil_is_422_and_writes_nothing(client, db_oturumu, kullanici):
    client.post("/api/settings", json={"openai_api_key": "sk-proj-KALICI"})
    r = client.post("/api/settings", json={"openai_api_key": "sk-proj-YENI", "anahtar_sil": ["replicate"]})
    assert r.status_code == 422 and "replicate" in r.text
    assert depo_kimlik_bilgisi.oku(db_oturumu, kullanici.id) == {"OPENAI_API_KEY": "sk-proj-KALICI"}, (
        "422 dönen istek HİÇBİR alanı yazmaz")


def test_the_settings_query_count_does_not_grow_with_the_platform_merge(client, monkeypatch, depo_db):
    """Platform anahtarı ORTAMDAN okunur, DB'den değil: `GET /api/settings` hâlâ tek kimlik sorgusu
    (test_kimlik'in "2 sorgu" ölçüsü bozulmaz)."""
    from sqlalchemy import event
    monkeypatch.setenv(platform_anahtari.ONEK + "GEMINI_API_KEY", PLATFORM_GEMINI)
    sayac: list[str] = []

    def _say(conn, cursor, statement, parameters, context, executemany):
        sayac.append(statement)
    event.listen(depo_db, "before_cursor_execute", _say)
    try:
        assert client.get("/api/settings").status_code == 200
    finally:
        event.remove(depo_db, "before_cursor_execute", _say)
    assert sum("saglayici_kimlikleri" in q for q in sayac) == 1, sayac
    # Kiracı bağlaması (Faz 2 / 7) kimlik sorgusu DEĞİL: transaksiyon başına bir `set_config`.
    assert sum("set_config" in q for q in sayac) == 1, sayac


# ── (iv) uçtan uca: işçi platform anahtarıyla çıkıyor ───────────────────

class _SahteAzure:
    """`httpx.Client` yerine: `Authorization` başlığını kaydeder, tek görsel döndürür (test_kimlik'in ikizi)."""
    gorulen: list[str] = []
    adresler: list[str] = []

    def __init__(self, *a, **k):
        pass

    def post(self, url, headers=None, json=None, timeout=None, **k):
        _SahteAzure.gorulen.append((headers or {}).get("Authorization", ""))
        _SahteAzure.adresler.append(url)

        class _Cevap:
            status_code = 200

            @staticmethod
            def json():
                return {"data": [{"b64_json": base64.b64encode(b"\x89PNG-sahte").decode()}]}
        return _Cevap()

    def close(self):
        pass


def _dokum(depo_db) -> str:
    """`pg_dump` görünümü: bütün iş tablolarının satırları düz metin olarak."""
    parcalar = []
    with depo_db.connect() as c:
        for tablo in tablolar.Base.metadata.tables:
            for satir in c.execute(text(f"SELECT row_to_json(t)::text FROM {tablo} t")).scalars():
                parcalar.append(satir)
    return "\n".join(parcalar)


def test_the_worker_uses_the_platform_key_then_the_users_own_then_the_platform_again(
        client, monkeypatch, depo_db, tmp_path, kullanici, uret_ve_bitir, caplog):
    """Belge §6 çıkış ölçütü: anahtar girmemiş kullanıcı platform anahtarıyla üretir; kendi
    anahtarını giren onunla; silen yine platformla — `[platform, kullanici, platform]`.
    Satır `anahtar_kaynagi`ni taşır; ekilen platform anahtarı DB dökümünde, `hata.log`da,
    günlükte ve cevaplarda YOK."""
    import httpx
    monkeypatch.setattr(httpx, "Client", _SahteAzure)
    _SahteAzure.gorulen.clear()
    _SahteAzure.adresler.clear()
    _platform_azure(monkeypatch)
    # Platform işi bakiye ister (Faz 3 / 2, 402): kredi yalnız defter üzerinden (`hibe`).
    with Session(depo_db) as db:
        defter.hibe(db, kullanici.id, 1000, f"{defter.ONEK_HIBE}{kullanici.id}:2026-09")
        db.commit()
    cevaplar: list[str] = []

    with caplog.at_level(logging.DEBUG):
        r = uret_ve_bitir(client, "/api/generate", json=GORSEL)
        assert r.status_code == 200, getattr(r, "text", r)
        assert r.is_["durum"] == "bitti" and r.is_["anahtar_kaynagi"] == "platform"
        cevaplar.append(repr(r.is_))

        s = client.post("/api/settings", json={"api_key": KULLANICI_AZURE,
                                               "base_url": "https://kullanici.openai.azure.com/openai/v1/"})
        assert s.status_code == 200 and s.json()["kaynaklar"]["azure_image"] == "kullanici"
        cevaplar.append(s.text)
        r = uret_ve_bitir(client, "/api/generate", json=GORSEL)
        assert r.status_code == 200 and r.is_["anahtar_kaynagi"] == "kullanici"

        s = client.post("/api/settings", json={"anahtar_sil": ["azure_image"]})
        assert s.json()["kaynaklar"]["azure_image"] == "platform"
        cevaplar.append(s.text)
        r = uret_ve_bitir(client, "/api/generate", json=GORSEL)
        assert r.status_code == 200 and r.is_["anahtar_kaynagi"] == "platform"
        cevaplar.append(client.get("/api/isler").text)
        cevaplar.append(client.get("/api/settings").text)

    assert _SahteAzure.gorulen == [f"Bearer {PLATFORM_AZURE}", f"Bearer {KULLANICI_AZURE}",
                                   f"Bearer {PLATFORM_AZURE}"]
    assert _SahteAzure.adresler[0].startswith(PLATFORM_AZURE_URL) and "kullanici." in _SahteAzure.adresler[1]
    assert [i["anahtar_kaynagi"] for i in client.get("/api/isler").json()["isler"]] == [
        "platform", "kullanici", "platform"]

    # Sızıntı taraması: DB dökümü (kullanıcının anahtarı yalnız Fernet jetonu olarak vardı,
    # platformunki hiç yazılmadı), hata.log, pytest'in yakaladığı günlük, HTTP cevapları.
    dokum = _dokum(depo_db)
    for parca in (PLATFORM_AZURE, KULLANICI_AZURE, "platform-kaynak"):
        assert parca not in dokum, parca
    log = errlog.log_path(str(tmp_path))
    if os.path.exists(log):
        with open(log, encoding="utf-8") as f:
            assert PLATFORM_AZURE not in f.read()
    assert PLATFORM_AZURE not in caplog.text and KULLANICI_AZURE not in caplog.text
    assert not any(PLATFORM_AZURE in c or KULLANICI_AZURE in c for c in cevaplar)


def test_without_a_user_or_platform_key_the_route_answers_409_and_creates_no_job(
        client, depo_db, tmp_path, dizinler, kullanici):
    """§5'in 6'ya devrettiği ilk madde: anahtarsız kullanıcı 202 + `hata`lı iş DEĞİL, 409 ve hiç iş
    görmez; kota sayaçlarına da dokunmaz (iş doğmadı). Cümle sağlayıcıyı ve ortam adını söyler."""
    dizinler(data_dir=str(tmp_path))
    r = client.post("/api/generate", json=GORSEL)
    assert r.status_code == 409, r.text
    assert "AZURE_IMAGE_API_KEY" in r.json()["detail"]   # cümle isteğin dilinde; env adı dilden bağımsız
    v = client.post("/api/video", json={"prompt": "kedi", "size": "16:9", "quality": "720p", "duration": 4})
    assert v.status_code == 409 and "GEMINI_API_KEY" in v.json()["detail"]
    assert client.get("/api/isler").json()["isler"] == []
    with depo_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM isler")).scalar_one() == 0
    assert not (tmp_path / "kullanicilar").exists() or not any((tmp_path / "kullanicilar").rglob("isler/*"))


def test_the_gate_reads_the_merged_mapping_and_returns_the_source():
    """`check_anahtar`: kurulu değilse 409 (HTTPException), kuruluysa kaynak."""
    from fastapi import HTTPException
    k = platform_anahtari.kimlikler({}, {"KROMIS_PLATFORM_GEMINI_API_KEY": "p"})
    assert kapilar.check_anahtar("gemini", k) == "platform"
    k = platform_anahtari.kimlikler({"GEMINI_API_KEY": "u"}, {"KROMIS_PLATFORM_GEMINI_API_KEY": "p"})
    assert kapilar.check_anahtar("gemini", k) == "kullanici"
    with pytest.raises(HTTPException) as e:
        kapilar.check_anahtar("openai", k)
    assert e.value.status_code == 409 and "OPENAI_API_KEY" in str(e.value.detail)
