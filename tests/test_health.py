"""`GET /health` — konteynerin sondası (Faz 0 / Adım 8 + Faz 1 / 1. görev, routers/saglik.py).

Sonda beş şey söylüyor: ayakta mı (200/503), hangi sürüm, veri dizinine
yazılabiliyor mu, veri tabanına ulaşılabiliyor mu, işçi canlı mı (Faz 2 / 9:
`worker_alive` + `worker_last_heartbeat`). `ok` dizin ve DB'nin VE'si ve
durum kodu `ok`u izliyor: `HEALTHCHECK` ve orkestratör gövdeyi okumadan
anlasın; gövde yine de tam döner ki insan NEYİN sağlıksız olduğunu okusun.
İşçi `ok`a GİRMEZ (belge §9): işçinin düşmesi web'i yeniden başlattırmamalı.

VERİ TABANI ÖLÇÜTÜ TESTLERİ NASIL DEĞİŞTİRDİ (Faz 1 / 1): motor lifespan'da
kuruluyor (services/db.py), yani 200 bekleyen her test artık `with
TestClient(app)` ile açılıyor ve `veritabani` fixture'ından GERÇEK bir
Postgres alıyor. Faz 0'daki `_client()` ("lifespan'a muhtaç olmamalı")
duruyor ama artık tek bir şeyi sınıyor: lifespan koşmamış bir süreçte sonda
yine CEVAP VERİYOR — 503 ve `db_reachable:false` ile, `AttributeError` ile
değil. Yazılamayan dizin senaryoları da DB'li koşuyor ki 503'ün sebebi
gövdeden okunsun (`data_dir_writable:false`, `db_reachable:true`): iki
ölçütün ikisi de kırmızıyken hangisinin sınandığı belli olmazdı.

TESTLER ROOT'TA DA ANLAMLI: bu takım hem CI koşucusunda hem Claude Code
konteynerinde çoğu zaman root olarak koşuyor ve root için `chmod` izin bitleri
bağlayıcı değil. Yazılamayan dizin bu yüzden İKİ yolla üretiliyor: dizin yerine
düz bir DOSYA (`mkstemp` → `NotADirectoryError`) ve hiç var olmayan yol —
ikisi de root'ta kırmızıya döner. Klasik `chmod 0o500` senaryosu ayrıca var
ama root'ta ve Windows'ta atlanıyor; sondanın `os.access` yerine gerçek yazım
denemesi kullanmasının gerekçesi de tam olarak bu (routers/saglik.py).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import stat
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import version
from routers import saglik
from services import depo_admin, kuyruk, zaman


def _client() -> TestClient:
    # `with` YOK, bilerek: lifespan koşmamış (ya da açılışı patlamış) bir
    # süreçte sonda yine cevap vermeli — ve o cevap "sağlıksız" olmalı, çünkü
    # motor lifespan'da kuruluyor. `app` burada ithal ediliyor (conftest gerekçesi).
    import app as appmod
    return TestClient(appmod.app)


@pytest.fixture
def istemci(veritabani) -> Iterator[TestClient]:
    """Lifespan'lı istemci: motor kurulu, `DATABASE_URL` bu dosyanın Postgres'ine bakıyor."""
    import app as appmod
    with TestClient(appmod.app) as c:
        yield c


GOVDE_ALANLARI = {"ok", "version", "data_dir_writable", "db_reachable", "worker_alive",
                  "worker_last_heartbeat"}
# İşçi satırı olmayan, ulaşılabilir DB: canlı değil, kalp yok.
ISCISIZ = {"worker_alive": False, "worker_last_heartbeat": None}
# Motor yok / DB yok: cevap BİLİNMİYOR, "hayır" değil.
BILINMIYOR = {"worker_alive": None, "worker_last_heartbeat": None}


def test_health_is_200_with_the_documented_body_when_the_data_dir_is_writable(tmp_path, dizinler, istemci):
    dizinler(data_dir=str(tmp_path))
    cevap = istemci.get("/health")
    assert cevap.status_code == 200
    assert cevap.json() == {"ok": True, "version": version.APP_VERSION,
                            "data_dir_writable": True, "db_reachable": True, **ISCISIZ}


def test_health_reports_the_apps_version_constant_not_a_second_literal(tmp_path, dizinler, istemci):
    """Sürüm `version.APP_VERSION`dan; rota kendi literalini taşımaz
    (deponun "sürüm literali tek yerde" kuralı, tests/test_version.py)."""
    dizinler(data_dir=str(tmp_path))
    surum = istemci.get("/health").json()["version"]
    assert surum == version.APP_VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", surum), surum


def test_health_leaves_no_trace_in_the_data_dir(tmp_path, dizinler, istemci):
    """Sonda her 30 sn'de bir koşacak; iz bıraksaydı `/data` geçici dosyayla dolardı."""
    dizinler(data_dir=str(tmp_path))
    for _ in range(3):
        assert istemci.get("/health").status_code == 200
    assert os.listdir(tmp_path) == []


def test_health_is_503_when_the_data_dir_is_a_regular_file(tmp_path, dizinler, istemci):
    """Root'ta da çalışan "yazılamaz" senaryosu: dizin yerine dosya. DB sağlam — sebep gövdede."""
    dosya = tmp_path / "dizin-degil"
    dosya.write_text("", encoding="utf-8")
    dizinler(data_dir=str(dosya))
    cevap = istemci.get("/health")
    assert cevap.status_code == 503
    assert cevap.json() == {"ok": False, "version": version.APP_VERSION,
                            "data_dir_writable": False, "db_reachable": True, **ISCISIZ}


def test_health_is_503_when_the_data_dir_does_not_exist_and_does_not_create_it(tmp_path, dizinler, istemci):
    """Dizini `_lifespan` açar, sonda AÇMAZ: açamayan bir açılışı sonda gizlemesin."""
    yok = tmp_path / "yok"
    dizinler(data_dir=str(yok))
    cevap = istemci.get("/health")
    assert cevap.status_code == 503
    assert cevap.json()["data_dir_writable"] is False
    assert not yok.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX izin bitleri")
@pytest.mark.skipif(getattr(os, "geteuid", lambda: 0)() == 0,
                    reason="root için izin bitleri bağlayıcı değil")
def test_health_is_503_when_the_data_dir_is_read_only(tmp_path, dizinler, istemci):
    salt = tmp_path / "salt"
    salt.mkdir()
    salt.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        dizinler(data_dir=str(salt))
        cevap = istemci.get("/health")
        assert cevap.status_code == 503
        assert cevap.json()["data_dir_writable"] is False
    finally:
        salt.chmod(stat.S_IRWXU)


def test_health_is_not_cacheable(tmp_path, dizinler, istemci):
    """Bir ara vekil bu cevabı saklarsa sonda dakikalarca bayat "sağlıklı" okur."""
    dizinler(data_dir=str(tmp_path))
    assert istemci.get("/health").headers["cache-control"] == "no-store"


def test_health_still_answers_without_a_lifespan_and_says_the_database_is_unreachable(tmp_path, dizinler):
    """Lifespan koşmadı → motor yok → 503 + `db_reachable:false`; gövde yine tam.

    Faz 0'ın "sonda lifespan'a muhtaç olmamalı" ilkesinin Faz 1 hâli: cevap
    yine geliyor (AttributeError değil), ama "sağlıklı" DEĞİL — çünkü motor
    yok ve motorsuz uygulama kullanıcı hesabı açamaz. Dizin yazılabilir: 503'ün
    tek sebebi DB olduğu gövdeden okunuyor.
    """
    dizinler(data_dir=str(tmp_path))
    cevap = _client().get("/health")
    assert cevap.status_code == 503
    assert cevap.json() == {"ok": False, "version": version.APP_VERSION,
                            "data_dir_writable": True, "db_reachable": False, **BILINMIYOR}


def test_health_is_503_when_only_the_database_is_missing(tmp_path, dizinler, monkeypatch):
    """`ok` iki ölçütün VE'si: dizin iyi, `DATABASE_URL` verilmemiş → 503, sebep gövdede.

    "Yapılandırılmamış" ayrı bir değer DEĞİL (`null` yok): veri tabanı olmadan
    bu uygulama hesap açamaz, sondanın "sağlıklı" demesi için sebep yok
    (routers/saglik.py). Lifespan koşuyor ama URL yok → motor `None`.
    """
    import app as appmod
    dizinler(data_dir=str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(appmod.app) as c:
        assert appmod.app.state.motor is None
        cevap = c.get("/health")
    assert cevap.status_code == 503
    assert cevap.json() == {"ok": False, "version": version.APP_VERSION,
                            "data_dir_writable": True, "db_reachable": False, **BILINMIYOR}


def test_the_health_body_has_exactly_the_documented_fields(tmp_path, dizinler, istemci):
    """Alan adları sözleşme: `HEALTHCHECK`, uptime sondaları ve README bunları okuyor.
    Yeni ölçüt gelirse buraya eklenir (Faz 0 / 8'in "alan adları değişmez" notu)."""
    dizinler(data_dir=str(tmp_path))
    assert set(istemci.get("/health").json()) == GOVDE_ALANLARI


def test_the_probe_helper_answers_from_the_filesystem_alone(tmp_path):
    """Yardımcı uygulamadan bağımsız; `Dockerfile` dışında da (bir betikten) kullanılabilir."""
    assert saglik.veri_dizini_yazilabilir(str(tmp_path)) is True
    dosya = tmp_path / "dosya"
    dosya.write_text("", encoding="utf-8")
    assert saglik.veri_dizini_yazilabilir(str(dosya)) is False
    assert saglik.veri_dizini_yazilabilir(str(tmp_path / "yok")) is False
    assert sorted(os.listdir(tmp_path)) == ["dosya"]


# ── worker_alive (Faz 2 / 9) ───────────────────────────────────────────────

@pytest.fixture
def isciler(veritabani_motor) -> Iterator[Session]:
    """Bu dosyanın DB'sine `isciler` satırı yazmak için oturum; test sonunda tablo boşalır."""
    with Session(veritabani_motor) as s:
        yield s
        s.rollback()
        s.execute(text("DELETE FROM isciler"))
        s.commit()


def test_worker_alive_is_true_with_a_fresh_heartbeat_and_the_body_names_it(tmp_path, dizinler, istemci, isciler):
    dizinler(data_dir=str(tmp_path))
    an = zaman.an()
    kuyruk.isci_kaydet(isciler, "konak-a", version.APP_VERSION, 2, an - dt.timedelta(minutes=10))
    isciler.execute(text("UPDATE isciler SET son_kalp = :an"), {"an": an - dt.timedelta(seconds=30)})
    isciler.commit()
    govde = istemci.get("/health").json()
    assert govde["ok"] is True and govde["worker_alive"] is True
    assert govde["worker_last_heartbeat"] == zaman.damga(an - dt.timedelta(seconds=30))


def test_worker_alive_is_false_past_the_shared_threshold_and_ok_is_unaffected(tmp_path, dizinler, istemci, isciler):
    """Eşik `depo_admin.CANLI_ESIK`in KENDİSİ (90 sn): admin sayfası "canlı" derken sonda "ölü" demesin.
    İşçi ölü → yine 200: işçinin sağlığı web'in sağlığı değil (belge §9)."""
    dizinler(data_dir=str(tmp_path))
    an = zaman.an()
    kuyruk.isci_kaydet(isciler, "konak-b", version.APP_VERSION, 1, an - dt.timedelta(hours=1))
    isciler.execute(text("UPDATE isciler SET son_kalp = :an"),
                    {"an": an - depo_admin.CANLI_ESIK - dt.timedelta(seconds=5)})
    isciler.commit()
    cevap = istemci.get("/health")
    assert cevap.status_code == 200
    govde = cevap.json()
    assert govde["ok"] is True and govde["worker_alive"] is False
    assert govde["worker_last_heartbeat"] == zaman.damga(an - depo_admin.CANLI_ESIK - dt.timedelta(seconds=5))
    # Eşiğin hemen içi canlı: sınır `>`, `depo_admin.metrikler`in `canli`siyle aynı karşılaştırma.
    isciler.execute(text("UPDATE isciler SET son_kalp = :an"),
                    {"an": an - depo_admin.CANLI_ESIK + dt.timedelta(seconds=20)})
    isciler.commit()
    assert istemci.get("/health").json()["worker_alive"] is True


def test_worker_alive_is_null_when_there_is_no_engine_or_the_table_is_missing(tmp_path, dizinler, monkeypatch):
    """Motor yok → `null` (bilinmiyor). Tablo yok (göç koşmamış) → `db_reachable` yine true, işçi `null`."""
    dizinler(data_dir=str(tmp_path))
    assert _client().get("/health").json()["worker_alive"] is None
    assert saglik.isci_durumu(None) == (False, None, None)

    class _Baglanti:
        def execute(self, ifade):
            class _S:
                def scalar_one(self_inner):
                    return 1
            if "SELECT 1" in str(ifade):
                return _S()
            raise RuntimeError("relation isciler does not exist")

        def rollback(self) -> None:
            pass
    from services import db
    monkeypatch.setattr(db, "sor", lambda motor, sorgu, *a, **k: sorgu(_Baglanti()))
    assert saglik.isci_durumu(object()) == (True, None, None)
