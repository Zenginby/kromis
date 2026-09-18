"""`tools/goc.py` — dağıtım öncesi göç komutu (Faz 1 / 9, K6).

GERÇEK Postgres: `veritabani` fixture'ı `DATABASE_URL`i bu dosyanın DB'sine
çeviriyor, araç motorunu oradan kurar. DB şablon kopyasıyla `head`te geliyor;
"boş DB" kurgusu `alembic downgrade base` ile kuruluyor ve her test sonda DB'yi
`head`e geri koyuyor — dosyanın öteki testleri aynı DB'yi paylaşıyor.

NEDEN AYRI BİR ARAÇ SINANIYOR: `alembic upgrade head` zaten `tests/test_db.py`de
ölçülü. Buradaki iddialar sarmalayıcının SÖZÜ: URL'yi uygulamayla aynı yerden
okur, boş DB'yi head'e taşır, ikinci koşu hiçbir şey yapmaz ve 0 ile çıkar
(platform her dağıtımda koşturur), URL yoksa/sunucu yoksa 2, göç düşerse 1 —
ve `python tools/goc.py` diye, imajdaki gibi koşuyor.
"""
from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from alembic import command
from services import db
from tools import goc

pytestmark = pytest.mark.usefixtures("veritabani")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAS = "0005_kota"


def _surum(url: str) -> str | None:
    motor = create_engine(url)
    try:
        with motor.connect() as c:
            if not c.execute(text("SELECT to_regclass('alembic_version')")).scalar():
                return None
            return c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        motor.dispose()


@pytest.fixture
def bos_db(veritabani):
    """DB'yi `base`e indirir, test bitince `head`e geri koyar."""
    cfg = goc.yapilandirma(veritabani)
    command.downgrade(cfg, "base")
    assert _surum(veritabani) is None
    yield veritabani
    command.upgrade(cfg, "head")


def test_the_head_named_by_the_tool_is_the_migration_chain_head(veritabani):
    assert goc.bas(goc.yapilandirma(veritabani)) == BAS


def test_an_empty_database_is_migrated_to_head_and_the_second_run_is_a_no_op(bos_db, capsys):
    """ASIL İDDİA: platformun ilk dağıtımı (boş DB) ve her sonraki dağıtımı (head'te)."""
    assert goc.main([]) == goc.CIKIS_TAMAM
    out = capsys.readouterr().out
    assert "bos (alembic_version yok)" in out and f"hedef {BAS}" in out
    assert f"mevcut {BAS} (head)" in out
    assert _surum(bos_db) == BAS

    assert goc.main([]) == goc.CIKIS_TAMAM
    out = capsys.readouterr().out
    assert "zaten head'te" in out
    assert _surum(bos_db) == BAS


def test_without_a_database_url_the_tool_exits_2_and_names_the_variable(monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    assert goc.main([]) == goc.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err


def test_an_unreachable_server_exits_2_without_a_traceback(monkeypatch, capsys):
    monkeypatch.setenv(db.DATABASE_URL_ENV, "postgresql+psycopg://x:x@127.0.0.1:1/x")
    assert goc.main([]) == goc.CIKIS_ORTAM
    err = capsys.readouterr().err
    assert "ulasilamiyor" in err and "Traceback" not in err


def test_a_failing_migration_exits_1_and_leaves_the_version_where_it_was(bos_db, monkeypatch, capsys):
    """Göç betiği patlarsa: kod 1, sebep stderr'de, `alembic_version` dokunulmamış —
    platform yeni sürümü AÇMAZ."""
    def _patlar(cfg, hedef):
        raise RuntimeError("sahte gocte hata: sutun zaten var")

    # `goc.command` YAMALANIYOR, `alembic.command` değil: ikincisi bu dosyanın
    # `bos_db` fixture'ının head'e geri koymak için kullandığı modülün kendisi.
    monkeypatch.setattr(goc, "command", SimpleNamespace(upgrade=_patlar))
    assert goc.main([]) == goc.CIKIS_GOC
    err = capsys.readouterr().err
    assert "goc DUSTU" in err and "RuntimeError" in err
    assert _surum(bos_db) is None


def test_the_tool_reads_the_url_from_the_same_place_as_the_app():
    """İkinci bir `os.environ` okuması yok: ad `services.db.DATABASE_URL_ENV`, okuyan
    `db.baglanti_dizesi` (alembic/env.py de aynı). Bir gün ad değişirse tek yer."""
    with open(os.path.join(REPO, "tools", "goc.py"), encoding="utf-8") as f:
        kaynak = f.read()
    assert "db.baglanti_dizesi()" in kaynak
    assert 'environ' not in kaynak.replace("os.environ", "")  # başka ortam okuması yok
    assert "os.environ" not in kaynak, "URL'yi doğrudan ortamdan okuyor — tek kaynak services.db"


def test_the_script_runs_from_the_command_line_the_way_the_image_calls_it(veritabani):
    """`python tools/goc.py` — imajın/platformun çağırdığı biçim; `sys.path` düzeltmesi çalışıyor."""
    ortam = {**os.environ, db.DATABASE_URL_ENV: veritabani}
    sonuc = subprocess.run([sys.executable, os.path.join("tools", "goc.py")], cwd=REPO, env=ortam,
                           capture_output=True, text=True, timeout=120)
    assert sonuc.returncode == goc.CIKIS_TAMAM, sonuc.stderr
    assert "zaten head'te" in sonuc.stdout
