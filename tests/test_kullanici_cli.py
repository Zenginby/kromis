"""`tools/kullanici.py` — ilk kullanıcı ve oturum düşürme CLI'ı (Faz 1 / 8).

`main(argv)` üzerinden, GERÇEK Postgres (`veritabani` fixture'ı `DATABASE_URL`i
bu dosyanın DB'sine çeviriyor; araç motorunu oradan kurar). Parola testlerde
`--parola-stdin` ile (TTY yok); `getpass` yolu yamayla sınanıyor. Özet
`services.hesap` ile doğrulanır: CLI ve web aynı kural kümesini kullansın.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services import db, hesap, tablolar
from tools import kullanici as cli

pytestmark = pytest.mark.usefixtures("veritabani")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOSTA = "ilk@example.com"
PAROLA = "  cok-gizli parola 1  "   # baştaki/sondaki boşluk parolanın parçası


def _stdin(monkeypatch, metin: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(metin))


def _olustur(monkeypatch, *ek: str, eposta: str = EPOSTA, parola: str = PAROLA) -> int:
    _stdin(monkeypatch, parola + "\n")
    return cli.main(["olustur", "--eposta", eposta, "--parola-stdin", *ek])


def _kullanici(motor, eposta: str = EPOSTA) -> tablolar.Kullanici | None:
    with Session(motor) as s:
        return s.scalar(select(tablolar.Kullanici).where(tablolar.Kullanici.eposta == eposta))


def _sayi(motor) -> int:
    with Session(motor) as s:
        return int(s.scalar(select(func.count()).select_from(tablolar.Kullanici)) or 0)


def test_olustur_writes_a_verified_user_whose_hash_verifies_through_hesap(veritabani_motor, monkeypatch, capsys):
    once = _sayi(veritabani_motor)
    assert _olustur(monkeypatch) == 0
    k = _kullanici(veritabani_motor)
    assert k is not None and k.dogrulandi_at is not None, "ilk kullanıcı posta servisi olmadan girebilmeli"
    assert k.is_admin is False and k.dil is None
    assert k.parola_ozeti and k.parola_ozeti.startswith("$argon2id$")
    assert hesap.parola_dogru(PAROLA, k.parola_ozeti)
    assert not hesap.parola_dogru(PAROLA.strip(), k.parola_ozeti), "boşluk kırpılmaz"
    assert _sayi(veritabani_motor) == once + 1
    out, err = capsys.readouterr()
    assert EPOSTA in out and str(k.id) in out and "dogrulanmis: evet" in out
    assert PAROLA.strip() not in out + err, "parola hiçbir çıktıya yazılmaz"


def test_admin_and_language_flags_land_on_the_row(veritabani_motor, monkeypatch):
    assert _olustur(monkeypatch, "--admin", "--dil", "tr", eposta="admin@example.com") == 0
    k = _kullanici(veritabani_motor, "admin@example.com")
    assert k is not None and k.is_admin is True and k.dil == "tr"


def test_an_existing_email_exits_1_and_writes_nothing(veritabani_motor, monkeypatch, capsys):
    assert _olustur(monkeypatch, eposta="tekrar@example.com") == 0
    k1 = _kullanici(veritabani_motor, "tekrar@example.com")
    once = _sayi(veritabani_motor)
    # citext: büyük/küçük harf aynı hesap.
    assert _olustur(monkeypatch, "--admin", eposta="Tekrar@Example.com", parola="baska-parola") == 1
    assert "zaten kayitli" in capsys.readouterr().err
    k2 = _kullanici(veritabani_motor, "tekrar@example.com")
    assert _sayi(veritabani_motor) == once
    assert k2 is not None and k1 is not None
    assert (k2.parola_ozeti, k2.is_admin) == (k1.parola_ozeti, False), "var olan hesaba dokunulmadı"


def test_invalid_email_or_short_password_exit_1_before_touching_the_db(veritabani_motor, monkeypatch, capsys):
    once = _sayi(veritabani_motor)
    assert _olustur(monkeypatch, eposta="eposta-degil") == 1
    assert _olustur(monkeypatch, eposta="kisa@example.com", parola="kisa") == 1
    _stdin(monkeypatch, "")
    assert cli.main(["olustur", "--eposta", "bos@example.com", "--parola-stdin"]) == 1
    assert "bos" in capsys.readouterr().err
    assert _sayi(veritabani_motor) == once


def test_the_tty_path_asks_twice_and_refuses_a_mismatch(veritabani_motor, monkeypatch):
    cevaplar = iter(["parola-12345", "parola-54321"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _istem: next(cevaplar))
    assert cli.main(["olustur", "--eposta", "tty@example.com"]) == 1
    assert _kullanici(veritabani_motor, "tty@example.com") is None
    cevaplar = iter(["parola-12345", "parola-12345"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _istem: next(cevaplar))
    assert cli.main(["olustur", "--eposta", "tty@example.com"]) == 0
    k = _kullanici(veritabani_motor, "tty@example.com")
    assert k is not None and hesap.parola_dogru("parola-12345", k.parola_ozeti)


def test_oturum_dusur_revokes_every_session_and_prints_the_count(veritabani_motor, monkeypatch, capsys):
    assert _olustur(monkeypatch, eposta="sizan@example.com") == 0
    with Session(veritabani_motor) as s:
        k = s.scalar(select(tablolar.Kullanici).where(tablolar.Kullanici.eposta == "sizan@example.com"))
        assert k is not None
        an = hesap.simdi()
        jetonlar = [hesap.oturum_ac(s, k, "203.0.113.5", "tarayici", an) for _ in range(3)]
        s.commit()
        kid = k.id
    capsys.readouterr()
    assert cli.main(["oturum-dusur", "--eposta", "sizan@example.com"]) == 0
    assert "3 oturum dusuruldu" in capsys.readouterr().out
    with Session(veritabani_motor) as s:
        assert s.scalar(select(func.count()).select_from(tablolar.Oturum)
                        .where(tablolar.Oturum.kullanici_id == kid)) == 0
        for jeton in jetonlar:
            assert hesap.oturum_dogrula(s, jeton, hesap.simdi()) is None, "düşen çerez tanınmaz"
    assert cli.main(["oturum-dusur", "--eposta", "yok@example.com"]) == 1
    assert "diye bir kullanici yok" in capsys.readouterr().err


def test_admin_flips_the_flag_on_an_existing_user_reports_whether_it_changed_and_kaldir_reverts(
        veritabani_motor, monkeypatch, capsys):
    """Faz 2 / 8: canlıdaki ilk admin sahibin var olan hesabı — `UPDATE` yazdırmak yerine komut."""
    eposta = "yonetici@example.com"    # dosyanın DB'si paylaşılıyor: `EPOSTA` öteki testlerin
    assert _olustur(monkeypatch, eposta=eposta) == cli.CIKIS_TAMAM
    capsys.readouterr()
    assert cli.main(["admin", "--eposta", eposta]) == cli.CIKIS_TAMAM
    assert f"{eposta}: admin = evet (degisti)" in capsys.readouterr().out
    with Session(veritabani_motor) as s:
        assert s.scalars(select(tablolar.Kullanici).where(tablolar.Kullanici.eposta == eposta)).one().is_admin is True
    assert cli.main(["admin", "--eposta", eposta]) == cli.CIKIS_TAMAM
    assert "zaten oyleydi" in capsys.readouterr().out
    assert cli.main(["admin", "--eposta", eposta, "--kaldir"]) == cli.CIKIS_TAMAM
    assert f"{eposta}: admin = hayir (degisti)" in capsys.readouterr().out
    with Session(veritabani_motor) as s:
        assert s.scalars(select(tablolar.Kullanici).where(tablolar.Kullanici.eposta == eposta)).one().is_admin is False
    assert cli.main(["admin", "--eposta", "yok@example.com"]) == cli.CIKIS_KULLANICI
    assert "diye bir kullanici yok" in capsys.readouterr().err


def test_parola_rewrites_the_hash_and_revokes_every_session(veritabani_motor, monkeypatch, capsys):
    """Parola sıfırlama: yeni özet DOĞRULANIR, eskisi artık geçmez ve bütün oturumlar düşer.

    Oturumların düşmesi yan etki değil ŞART: parola değiştirmek "bu hesabı artık
    ben yönetiyorum" demek; eski çerez ayakta kalırsa saldırgan dışarı atılmaz.
    """
    assert _olustur(monkeypatch, eposta="unutan@example.com") == 0
    with Session(veritabani_motor) as s:
        k = s.scalar(select(tablolar.Kullanici).where(tablolar.Kullanici.eposta == "unutan@example.com"))
        assert k is not None
        jeton = hesap.oturum_ac(s, k, "203.0.113.9", "tarayici", hesap.simdi())
        s.commit()
        kid = k.id
    capsys.readouterr()

    _stdin(monkeypatch, "YepyeniParola123!\n")
    assert cli.main(["parola", "--eposta", "unutan@example.com", "--parola-stdin"]) == 0
    assert "parola yazildi, 1 oturum dusuruldu" in capsys.readouterr().out

    with Session(veritabani_motor) as s:
        k = s.get(tablolar.Kullanici, kid)
        assert hesap.parola_dogru("YepyeniParola123!", k.parola_ozeti), "yeni parola geçmeli"
        assert not hesap.parola_dogru(PAROLA, k.parola_ozeti), "eski parola ARTIK geçmemeli"
        assert hesap.oturum_dogrula(s, jeton, hesap.simdi()) is None, "eski çerez tanınmaz"

    # Bilinmeyen e-posta: 1, hiçbir şey yazılmaz. Parola STDIN'den okunduğu için
    # DB'ye gitmeden ÖNCE tüketilir — akış bozulmasın diye yeniden veriliyor.
    _stdin(monkeypatch, "YepyeniParola123!\n")
    assert cli.main(["parola", "--eposta", "yok@example.com", "--parola-stdin"]) == 1
    assert "diye bir kullanici yok" in capsys.readouterr().err

    # Kısa parola: DB'ye hiç gidilmez (kural kümesi web ile AYNI, `models.check_parola`).
    _stdin(monkeypatch, "kisa\n")
    assert cli.main(["parola", "--eposta", "unutan@example.com", "--parola-stdin"]) == 1


def test_without_database_url_the_tool_exits_2(monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV)
    _stdin(monkeypatch, PAROLA + "\n")
    assert cli.main(["olustur", "--eposta", EPOSTA, "--parola-stdin"]) == cli.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err


def test_the_cli_shares_the_web_validation_rules():
    """`models.check_eposta`/`check_parola` ve `hesap.parola_ozeti` — kopya kural yok (AST değil, ad)."""
    with open(os.path.join(REPO, "tools", "kullanici.py"), encoding="utf-8") as f:
        kaynak = f.read()
    assert "models.check_eposta(" in kaynak and "models.check_parola(" in kaynak
    assert "hesap.kullanici_olustur(" in kaynak and "hesap.oturumlari_dusur(" in kaynak
    assert "--parola\"" not in kaynak and "'--parola'" not in kaynak, "parola argümanla alınmaz"


def test_the_script_runs_standalone():
    c = subprocess.run([sys.executable, os.path.join(REPO, "tools", "kullanici.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=REPO)
    assert c.returncode == 0, c.stderr
    assert "olustur" in c.stdout and "oturum-dusur" in c.stdout
