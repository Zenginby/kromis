"""Veri tabanı zemini — `services/db.py`, `alembic/`, lifespan (Faz 1 / 1. görev).

Sınanan şey tablo değil MEKANİZMA: motor ne zaman kuruluyor (lifespan'da,
ithalde değil), `oturum` bağımlılığı commit/rollback'i nerede yapıyor
(bağımlılıkta, rota gövdesinde değil), sonda 1 sn'de dönüyor mu, Alembic
hattı boş bir Postgres'te baştan sona geçiyor mu. Hepsi GERÇEK Postgres'e
karşı (`veritabani` fixture'ı, tests/conftest.py) — SQLite'ın gizleyeceği
davranışlar bu fazın kullandıkları (K4, docs/faz1-veritabani-hesaplar.md).

Postgres GEREKTİRMEYEN testler ayrıca var ve bilerek: "ithal bağlantı açmaz"
ve "URL kapalı bir porta bakıyorsa 503" iddiaları Postgres'siz bir makinede de
koşmalı — o makinede TAM OLARAK o iki iddia kırılır.
"""
from __future__ import annotations

import os
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from services import db

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Bağlanmayan bir adres: 127.0.0.1'in 1. portu kapalı, `connect` anında
# reddedilir (ECONNREFUSED) — "sunucu yok" senaryosu saniye beklemez.
KAPALI_PORT_URL = "postgresql+psycopg://kimse@127.0.0.1:1/yok"

# Göç hattının BAŞI — her yeni göçte burası güncellenir (tek yer). Aşağıdaki
# testler "head'e çıktı mı" sorusunu bu dizeyle soruyor; `ScriptDirectory`den
# okumak testi göç dosyalarına göre yumuşatır ve yanlış bir `down_revision`
# zinciri görünmez olurdu.
BAS = "0003_arena_win"
ZINCIR = ["0003_arena_win", "0002_deneme_turu", "0001_veri_modeli", "0000_zemin"]


# ──────────────────────────────────────────────────── Postgres GEREKMEYEN

def test_importing_the_app_opens_no_database_connection(monkeypatch):
    """`import app` diske bile dokunmuyor (services/ayar.py); DB'ye de dokunmamalı.

    286 `test_index` + 37 `TestClient` dosyası Postgres'siz açılabilmeli
    (1. görevin risk sınıfı (a)). Ölçüm: `create_engine` yamalanıyor; ithal ve
    `with`siz `TestClient` onu HİÇ çağırmamalı — URL verilmiş olsa bile.
    """
    monkeypatch.setenv(db.DATABASE_URL_ENV, KAPALI_PORT_URL)
    cagrilar: list[str] = []
    monkeypatch.setattr(db, "create_engine", lambda url, **k: cagrilar.append(url))
    import app as appmod
    assert appmod.app.state.motor is None
    TestClient(appmod.app).get("/")          # lifespan YOK
    assert cagrilar == [], "ithal ya da with'siz istemci motor kurdu"


def test_the_connection_string_comes_from_the_environment_and_empty_means_none(monkeypatch):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    assert db.baglanti_dizesi() is None
    monkeypatch.setenv(db.DATABASE_URL_ENV, "")
    assert db.baglanti_dizesi() is None, "boş dize 'verilmiş' sayılmamalı"
    monkeypatch.setenv(db.DATABASE_URL_ENV, KAPALI_PORT_URL)
    assert db.baglanti_dizesi() == KAPALI_PORT_URL


def test_the_engine_factory_does_not_connect():
    """`create_engine` tembel: sunucu yokken bile motor kurulur, ilk `connect` düşer."""
    motor = db.motor_kur(KAPALI_PORT_URL)
    try:
        assert isinstance(motor, Engine)
        assert motor.pool.size() == 2, "havuz küçük kalmalı (yönetilen Postgres sınırı)"
    finally:
        motor.dispose()


def test_reachability_is_false_without_an_engine_or_with_a_closed_port():
    assert db.erisilebilir(None) is False
    motor = db.motor_kur(KAPALI_PORT_URL)
    try:
        basla = time.monotonic()
        assert db.erisilebilir(motor) is False
        assert time.monotonic() - basla < 2.0, "kapalı port anında reddedilmeli"
    finally:
        motor.dispose()


def test_reachability_gives_up_within_the_probe_budget_when_the_server_hangs():
    """Kara deliğe giden bağlantı: sonda 1 sn'de `False` der, 3 sn beklemez.

    libpq `connect_timeout` asgarisi 2 sn; `HEALTHCHECK --timeout=5s` ve
    orkestratör sondaları bunu beklemez. İş parçacığı + `result(timeout)`
    tam bu yüzden (services/db.py). Sahte motor: `connect` uyuyor.
    """
    serbest = threading.Event()

    class _AsiliBaglanti:
        def __enter__(self):
            serbest.wait(3.0)
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            raise AssertionError("buraya gelinmemeli")

    class _AsiliMotor:
        def connect(self):
            return _AsiliBaglanti()

    basla = time.monotonic()
    try:
        assert db.erisilebilir(_AsiliMotor(), zaman_asimi=0.3) is False
        gecen = time.monotonic() - basla
    finally:
        serbest.set()               # vazgeçilen iş parçacığını bırak
    assert gecen < 1.5, f"sonda zaman aşımını beklemedi: {gecen:.2f} sn"


def test_health_is_503_with_db_reachable_false_when_the_url_points_at_a_closed_port(
        tmp_path, dizinler, monkeypatch):
    """Çıkış ölçütü: "DB kapalıyken 503". Lifespan motoru kurar, sonda bağlanamaz."""
    import app as appmod
    dizinler(data_dir=str(tmp_path))
    monkeypatch.setenv(db.DATABASE_URL_ENV, KAPALI_PORT_URL)
    with TestClient(appmod.app) as c:
        assert appmod.app.state.motor is not None
        cevap = c.get("/health")
    assert cevap.status_code == 503
    govde = cevap.json()
    assert govde["db_reachable"] is False
    assert govde["data_dir_writable"] is True, "sebep DB olmalı, dizin değil"
    assert govde["ok"] is False
    assert appmod.app.state.motor is None, "kapanış motoru bırakmadı"


def test_a_malformed_url_does_not_stop_the_app_from_starting(tmp_path, dizinler, monkeypatch):
    """Bozuk URL → motor yok, hata `hata.log`da, uygulama AÇIK ve sonda sebebi söylüyor."""
    import app as appmod
    dizinler(data_dir=str(tmp_path))
    monkeypatch.setenv(db.DATABASE_URL_ENV, "bu bir url değil")
    with TestClient(appmod.app) as c:
        assert appmod.app.state.motor is None
        cevap = c.get("/health")
        assert cevap.status_code == 503
        assert cevap.json()["db_reachable"] is False
        assert c.get("/").status_code == 200
    gunluk = tmp_path / "hata.log"
    assert gunluk.exists() and "ArgumentError" in gunluk.read_text(encoding="utf-8")


def test_the_session_dependency_answers_503_when_no_engine_is_configured():
    """`DATABASE_URL` verilmemiş dağıtımda DB isteyen rota "hizmet yok" der, 500 değil."""
    uygulama = FastAPI()
    uygulama.state.motor = None

    @uygulama.get("/x")
    def x(oturum: Session = db.OTURUM) -> dict:
        return {}

    cevap = TestClient(uygulama).get("/x")
    assert cevap.status_code == 503
    assert cevap.json() == {"detail": "database_unavailable"}


def test_the_session_dependency_runs_its_exit_code_before_the_response_is_sent():
    """`OTURUM` `scope="function"` taşımalı (FastAPI ≥ 0.118).

    Öntanımlı `request` kapsamı commit'i cevap GÖNDERİLDİKTEN sonra koşturur:
    commit patlasa istemci 200 almış olurdu. Bu, mekanizmanın davranışsal
    ikizi aşağıda (`test_a_failing_commit_becomes_a_500`).
    """
    assert db.OTURUM.scope == "function"
    assert db.OTURUM.dependency is db.oturum


def test_the_alembic_config_loads_and_names_the_revision_chain():
    """`alembic.ini` + `alembic/` okunuyor; hat tek kollu: `0000_zemin` → `0001_veri_modeli` → `0002_deneme_turu`."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    betikler = ScriptDirectory.from_config(cfg)
    assert betikler.get_heads() == [BAS]
    assert [r.revision for r in betikler.walk_revisions()] == ZINCIR
    assert cfg.get_main_option("sqlalchemy.url") is None, (
        "URL alembic.ini'ye yazılmış — tek kaynak DATABASE_URL (services/db.py)")


def test_alembic_refuses_to_run_without_a_connection_string(monkeypatch):
    """Sessizce bir varsayılana düşmek yok: URL yoksa açık hata, hangi değişkenin adıyla."""
    from alembic.config import Config

    from alembic import command
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    with pytest.raises(SystemExit) as hata:
        command.current(cfg)
    assert db.DATABASE_URL_ENV in str(hata.value)


# ─────────────────────────────────────────────────────── GERÇEK Postgres

def test_the_fixture_gives_a_real_postgres_with_the_migration_applied(veritabani):
    """Fixture'ın sözü: `SELECT version()` PostgreSQL diyor, `alembic_version` `head`te."""
    motor = create_engine(veritabani)
    try:
        with motor.connect() as c:
            assert c.execute(text("SELECT version()")).scalar_one().startswith("PostgreSQL")
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BAS
    finally:
        motor.dispose()


def test_alembic_upgrade_downgrade_upgrade_is_clean_on_an_empty_database(veritabani):
    """Çıkış ölçütü: `alembic upgrade head` boş DB'de geçiyor; geri alma da temiz.

    Şablon DB zaten `head`te; burada `base`e inip yeniden çıkıyoruz — geri
    alma yolu hiç sınanmasa ilk gerçek göçte (2. görev) ilk kez koşardı.
    """
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    command.downgrade(cfg, "base")
    motor = create_engine(veritabani)
    try:
        with motor.connect() as c:
            assert c.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
        command.upgrade(cfg, "head")
        with motor.connect() as c:
            assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BAS
    finally:
        motor.dispose()


def test_alembic_check_reports_no_drift_between_model_and_migration(veritabani):
    """`alembic check`: model (`services/tablolar.py`) ile göç ayrışmamış.

    1. görevde boş `MetaData` ile yazıldı ki kapı ilk günden koşsun; 2. görev
    gerçek şemayı getirdi. Şemanın kendisini sınayan testler `tests/test_tablolar.py`de.
    """
    from alembic.config import Config

    from alembic import command
    cfg = Config(os.path.join(REPO, "alembic.ini"))
    cfg.attributes["baglanti_dizesi"] = veritabani
    command.check(cfg)          # fark varsa AutogenerateDiffsDetected fırlatır


def test_health_reports_db_reachable_true_and_200_with_a_live_database(tmp_path, dizinler, veritabani):
    """Çıkış ölçütü: `DATABASE_URL` verilmiş uygulama → `{"ok":true,…,"db_reachable":true}`."""
    import app as appmod
    import version
    dizinler(data_dir=str(tmp_path))
    with TestClient(appmod.app) as c:
        cevap = c.get("/health")
    assert cevap.status_code == 200
    assert cevap.json() == {"ok": True, "version": version.APP_VERSION,
                            "data_dir_writable": True, "db_reachable": True}


def _oturumlu_uygulama(veritabani: str) -> FastAPI:
    """`oturum` bağımlılığını gerçek motorla sınayan mini uygulama.

    Tablo bu testin kendisine ait (`deneme`): ürün şeması 2. görevde geliyor,
    burada sınanan şey bağımlılığın commit/rollback KURALI, şema değil.
    """
    uygulama = FastAPI()
    uygulama.state.motor = db.motor_kur(veritabani)
    with uygulama.state.motor.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS deneme (deger text NOT NULL)"))
        c.execute(text("TRUNCATE deneme"))

    @uygulama.post("/yaz/{deger}")
    def yaz(deger: str, oturum: Session = db.OTURUM) -> dict:
        oturum.execute(text("INSERT INTO deneme (deger) VALUES (:d)"), {"d": deger})
        return {"yazildi": deger}      # commit ROTADA DEĞİL — bağımlılıkta

    @uygulama.post("/yaz-ve-patla/{deger}")
    def yaz_ve_patla(deger: str, oturum: Session = db.OTURUM) -> dict:
        oturum.execute(text("INSERT INTO deneme (deger) VALUES (:d)"), {"d": deger})
        raise RuntimeError("rota patladı")

    @uygulama.post("/yaz-ve-404/{deger}")
    def yaz_ve_404(deger: str, oturum: Session = db.OTURUM) -> dict:
        from fastapi import HTTPException
        oturum.execute(text("INSERT INTO deneme (deger) VALUES (:d)"), {"d": deger})
        raise HTTPException(status_code=404)

    @uygulama.get("/say")
    def say(oturum: Session = db.OTURUM) -> dict:
        return {"n": oturum.execute(text("SELECT count(*) FROM deneme")).scalar_one()}

    return uygulama


def test_the_session_dependency_commits_when_the_route_returns(veritabani):
    uygulama = _oturumlu_uygulama(veritabani)
    try:
        c = TestClient(uygulama)
        assert c.post("/yaz/a").json() == {"yazildi": "a"}
        assert c.post("/yaz/b").status_code == 200
        assert c.get("/say").json() == {"n": 2}
    finally:
        uygulama.state.motor.dispose()


def test_the_session_dependency_rolls_back_when_the_route_raises(veritabani):
    """İstisna → rollback: yarım yazım kalmaz. `HTTPException` de istisna (404 dönen rota)."""
    uygulama = _oturumlu_uygulama(veritabani)
    try:
        c = TestClient(uygulama, raise_server_exceptions=False)
        assert c.post("/yaz-ve-patla/x").status_code == 500
        assert c.post("/yaz-ve-404/y").status_code == 404
        assert c.get("/say").json() == {"n": 0}
    finally:
        uygulama.state.motor.dispose()


def test_a_failing_commit_becomes_a_500_not_a_silent_200(veritabani, monkeypatch):
    """`scope="function"`ın davranışsal kanıtı: commit patlarsa istemci 500 görür.

    Öntanımlı kapsamda cevap çoktan gitmiş olurdu (200) ve hata yalnız
    sunucu günlüğüne düşerdi — "kaydedildi" denen şey kaydedilmemiş olurdu.
    """
    uygulama = _oturumlu_uygulama(veritabani)

    def _patlayan_commit(self):
        raise RuntimeError("commit reddedildi")

    monkeypatch.setattr(Session, "commit", _patlayan_commit)
    try:
        c = TestClient(uygulama, raise_server_exceptions=False)
        assert c.post("/yaz/z").status_code == 500
    finally:
        monkeypatch.undo()
        uygulama.state.motor.dispose()
    uygulama2 = _oturumlu_uygulama(veritabani)     # TRUNCATE eder; sayım sıfırdan
    try:
        assert TestClient(uygulama2).get("/say").json() == {"n": 0}
    finally:
        uygulama2.state.motor.dispose()


def test_each_test_file_gets_its_own_database_copied_from_the_template(veritabani, veritabani_url):
    """Fixture sözleşmesi: dosyaya ait DB adı `kromis_t_<dosya>_…`, şablon DEĞİL."""
    from sqlalchemy.engine import make_url
    ad = make_url(veritabani).database
    assert ad and ad.startswith("kromis_t_test_db_"), ad
    assert veritabani == veritabani_url
    assert os.environ[db.DATABASE_URL_ENV] == veritabani
