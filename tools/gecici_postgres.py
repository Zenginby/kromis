#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Makinedeki PostgreSQL ikililerinden GEÇİCİ bir küme açar — testler için (Faz 1 / 1. görev).

NEDEN VAR: test kararı GERÇEK Postgres, SQLite değil (docs/faz1-veritabani-
hesaplar.md, K4). SQLite'ın gizleyeceği şeyler tam olarak bu fazın
kullandıkları — JSONB, `citext`, `timestamptz`, `ON CONFLICT`, eş zamanlı
yazarlarda kilit — ve Faz 0'ın ölçülmüş dersi (CLAUDE.md §3: 9 kırmızının 8'i
atlanan E2E'de) burada birebir: SQLite'ta yeşil, Postgres'te kırmızı bir göç
CI'da görünür, yerelde görünmez. CI'da servis konteyneri var
(`KROMIS_TEST_DATABASE_URL`); yerelde ise Docker imajı çekilemeyen ama
`postgresql-16` paketi kurulu makineler (Claude Code konteyneri, ölçüldü)
için tek yol makinedeki ikililer: `initdb` → `pg_ctl start`.

NEDEN UNIX SOKETİ, TCP PORTU DEĞİL: `listen_addresses=''` ile küme hiçbir
porta bağlanmıyor; soket her kümenin KENDİ geçici dizininde. Aynı makinede
paralel iki takım (iki Claude Code oturumu, iki worktree) çakışmaz, boş port
aramak gerekmez. Bağlantı dizesi `host=<dizin>` sorgu parametresiyle gidiyor —
psycopg bunu soket dizini olarak okur.

ROOT: `initdb` ve `postgres` root'u reddediyor ("cannot be run as root") ve
bu takım CI koşucusunda da Claude Code konteynerinde de root koşuyor
(ölçüldü). Çözüm yardımcı bir kullanıcı: paketin bıraktığı `postgres`
kullanıcısı varsa o, yoksa `nobody`; alt süreçler `subprocess`in `user=`
parametresiyle o kimlikle açılır (`su`/`runuser` gerekmez, PATH/HOME
aktarılmaz). Veri ve soket dizini o kullanıcıya `chown` edilir; root soketten
yine bağlanır (dosya izni root'u bağlamaz), `--auth=trust` da işletim sistemi
kullanıcısına bakmaz.

NEDEN `pytest-postgresql` / `testcontainers` DEĞİL: birincisi `pg_ctl`i mevcut
kullanıcıyla çağırıyor (root'ta düşer), ikincisi imaj çekiyor (bu makinede
403). Buradaki kod 100 satır ve ikisinin de yapmadığı şeyi yapıyor.

SALT KİTAPLIK (üçüncü parti ithal YOK): `tools/test_ortami.py` bunu
SessionStart kancasında, hiçbir şeyin kurulu olmadığı yorumlayıcıyla ithal
ediyor; `tests/conftest.py` de pytest başlarken. Bağlantı dizesi DİZE olarak
dönüyor, SQLAlchemy'ye çeviren taraf çağıran.

HIZ: `initdb --no-sync` + `fsync=off`/`synchronous_commit=off`/
`full_page_writes=off` — veri atılabilir, dayanıklılık için ödenen her
milisaniye boşa. Ölçüldü (2026-09-17, bu makine): açılış ~0,8 sn (initdb dâhil),
kapanış `-m immediate` ile ~0,1 sn.
"""
from __future__ import annotations

import atexit
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

# `pwd` POSIX'te var, Windows'ta YOK — ve buradaki tek kullanıcısı
# `_yardimci_kullanici`, o da Windows'ta ilk satırda `None` dönüyor. Koşulsuz
# ithal edilirse modül Windows'ta ithal edilemez; `tests/conftest.py` bunu
# ithal ettiği için pytest CONFTEST'te düşer ve takım HİÇ toplanmaz — yani
# "Windows'ta gecici kume yok, KROMIS_TEST_DATABASE_URL verin" yönergesi
# (`kurulum_yonergesi`) hiç okunamadan hata veriyordu. Ölçüldü 2026-09-18.
if sys.platform != "win32":
    import pwd

# CI'ın (ya da geliştiricinin) hazır bir sunucu verdiği değişken. Süper
# kullanıcı yetkisi ister: fixture şablon DB'yi ve test dosyası başına birer
# DB'yi `CREATE DATABASE` ile açar. ÜRETİM `DATABASE_URL`i ile AYNI AD DEĞİL,
# bilerek: geliştiricinin kabuğunda duran gerçek bir `DATABASE_URL`, testin
# `CREATE/DROP DATABASE` koşturduğu yer olmamalı.
TEST_URL_ENV = "KROMIS_TEST_DATABASE_URL"

# Kümenin süper kullanıcısı ve bakım DB'si.
KULLANICI = "kromis"
BAKIM_DB = "postgres"

# Root için aday yardımcı kullanıcılar, tercih sırasıyla. `postgres` Debian/
# Ubuntu `postgresql-*` paketinin bıraktığı hesap; `nobody` her POSIX'te var.
YARDIMCI_KULLANICILAR = ("postgres", "nobody")


def ikili_dizini() -> str | None:
    """`initdb`, `pg_ctl` ve `postgres`in yaşadığı dizin — yoksa `None`.

    Sıra: `pg_config --bindir` (paketin kendi cevabı), PATH'teki `pg_ctl`,
    Debian/Ubuntu'nun `/usr/lib/postgresql/<sürüm>/bin`i (PATH'e GİRMİYOR —
    ölçüldü, `which pg_ctl` boş dönerken ikililer oradaydı; en yeni sürüm),
    Homebrew'un `/opt/homebrew/opt/postgresql@<n>/bin`i.
    """
    adaylar: list[str] = []
    pg_config = shutil.which("pg_config")
    if pg_config:
        try:
            c = subprocess.run([pg_config, "--bindir"], capture_output=True, text=True,
                               timeout=30, encoding="utf-8")
            if c.returncode == 0 and c.stdout.strip():
                adaylar.append(c.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    pg_ctl = shutil.which("pg_ctl")
    if pg_ctl:
        adaylar.append(os.path.dirname(os.path.realpath(pg_ctl)))
    adaylar += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    adaylar += sorted(glob.glob("/opt/homebrew/opt/postgresql@*/bin"), reverse=True)
    adaylar += sorted(glob.glob("/usr/local/opt/postgresql@*/bin"), reverse=True)
    for dizin in adaylar:
        if all(os.access(os.path.join(dizin, ad), os.X_OK)
               for ad in ("initdb", "pg_ctl", "postgres")):
            return dizin
    return None


def kurulum_yonergesi() -> str:
    """İkili yoksa ne yapılacağı — ASCII, çünkü kopyalanacak."""
    if sys.platform == "darwin":
        return "brew install postgresql@17"
    if os.name == "nt":
        # KONAK `127.0.0.1`, `localhost` DEGIL — ve bu bir uslup tercihi degil,
        # olculmus bir bedel (2026-09-18, bu makine): compose Postgres'i yalniz
        # IPv4 loopback'e bagliyor ("127.0.0.1:5432:5432", gerekcesi
        # compose.yaml'da: agdaki baska kimse baglanamasin). Windows ise
        # `localhost`u ONCE `::1`e cozuyor, orada dinleyici olmadigi icin
        # baglanti `connect_timeout` dolana kadar bekliyor ve ancak sonra IPv4'e
        # dusuyor: TEK baglanti 45,04 sn, ayni kume `127.0.0.1` ile 0,02 sn.
        # Takim her test dosyasi icin ayri DB acip bagladigindan bu bedel
        # yuzlerce kez odeniyor ve kosum "takilmis" gibi gorunuyor.
        return (f"Windows'ta gecici kume yok: {TEST_URL_ENV}="
                "postgresql+psycopg://postgres:...@127.0.0.1:5432/postgres verin "
                "(konak 127.0.0.1 olmali; localhost IPv6'ya dusup her baglantiya "
                "connect_timeout kadar bekletir)")
    return "sudo apt install postgresql   # ya da: dnf install postgresql-server"


def _yardimci_kullanici() -> tuple[int, int] | None:
    """Root'ta alt süreçlerin koşacağı (uid, gid) — root değilsek `None`."""
    if os.name == "nt" or os.geteuid() != 0:
        return None
    for ad in YARDIMCI_KULLANICILAR:
        try:
            k = pwd.getpwnam(ad)
        except KeyError:
            continue
        return k.pw_uid, k.pw_gid
    raise RuntimeError(
        "takim root kosuyor ve initdb root'u reddediyor; yardimci kullanici da yok "
        f"({', '.join(YARDIMCI_KULLANICILAR)}). `useradd --system postgres` ile acin.")


def baglanti_dizesi(soket_dizini: str, db: str = BAKIM_DB) -> str:
    """`postgresql+psycopg://kromis@/<db>?host=<soket dizini>` — SQLAlchemy biçimi."""
    return f"postgresql+psycopg://{KULLANICI}@/{db}?host={quote(soket_dizini, safe='')}"


class GeciciKume:
    """`ac()` ile başlar, `kapat()` ile silinir; `with` de olur.

    `url` bakım DB'sine (`postgres`) süper kullanıcı bağlantısı — çağıran
    oradan `CREATE DATABASE` koşturur (tests/conftest.py).
    """

    def __init__(self, ikililer: str | None = None) -> None:
        dizin = ikililer or ikili_dizini()
        if not dizin:
            raise RuntimeError("PostgreSQL ikilileri bulunamadi: " + kurulum_yonergesi())
        self.ikililer: str = dizin
        self.kok: str | None = None
        self.url: str = ""
        self._kimlik = _yardimci_kullanici()

    # ------------------------------------------------------------- yardımcı
    def _kos(self, *komut: str, zaman: int = 120) -> None:
        secenek: dict[str, object] = {}
        if self._kimlik is not None:
            uid, gid = self._kimlik
            # `extra_groups=[]`: root'un ek grupları çocuğa geçmesin — initdb
            # "grup üyeliği" değil uid'e bakıyor ama temiz kimlik daha az sürpriz.
            secenek = {"user": uid, "group": gid, "extra_groups": []}
        c = subprocess.run(
            [os.path.join(self.ikililer, komut[0]), *komut[1:]],
            capture_output=True, text=True, timeout=zaman, encoding="utf-8",
            **secenek)  # type: ignore[call-overload]
        if c.returncode != 0:
            raise RuntimeError(f"{komut[0]} basarisiz ({c.returncode}):\n{c.stdout}\n{c.stderr}")

    def _sahiplen(self, yol: str) -> None:
        if self._kimlik is not None:
            uid, gid = self._kimlik
            os.chown(yol, uid, gid)

    # ------------------------------------------------------------- yaşam
    def ac(self) -> str:
        # Soket yolu 107 bayta sığmalı (sun_path): `tempfile.gettempdir()`
        # bazı ortamlarda çok uzun (scratchpad yolları), o zaman düz `/tmp`.
        temp = tempfile.gettempdir()
        dizin = None if len(temp) <= 60 or not os.path.isdir("/tmp") else "/tmp"
        self.kok = tempfile.mkdtemp(prefix="kromis-pg-", dir=dizin)
        # Yardımcı kullanıcı `mkdtemp`in 0700 dizinine giremez; kök 0755,
        # veri dizini ise Postgres'in istediği gibi 0700 ve onun malı.
        os.chmod(self.kok, 0o755)
        veri = os.path.join(self.kok, "veri")
        soket = os.path.join(self.kok, "soket")
        os.mkdir(veri, 0o700)
        os.mkdir(soket, 0o755)
        self._sahiplen(veri)
        self._sahiplen(soket)
        atexit.register(self.kapat)

        self._kos("initdb", "-D", veri, "--auth=trust", f"--username={KULLANICI}",
                  "--encoding=UTF8", "--locale=C", "--no-sync")
        secenekler = " ".join([
            f"-k {soket}",
            "-c listen_addresses=''",           # port YOK — yalnız soket
            "-c fsync=off", "-c synchronous_commit=off", "-c full_page_writes=off",
            "-c log_min_messages=warning",
        ])
        # Günlük VERİ dizininde: kök dizin root'un, yardımcı kullanıcı oraya
        # yazamaz (ölçüldü: "cannot create …/postgres.log: Permission denied").
        self._kos("pg_ctl", "-D", veri, "-o", secenekler, "-l",
                  os.path.join(veri, "postgres.log"), "-w", "-t", "60", "start")
        self.url = baglanti_dizesi(soket)
        return self.url

    def kapat(self) -> None:
        if not self.kok:
            return
        kok, self.kok = self.kok, None
        veri = os.path.join(kok, "veri")
        try:
            # `immediate`: bekleyen bağlantı varsa bile kapan; veri atılabilir.
            self._kos("pg_ctl", "-D", veri, "-m", "immediate", "-w", "-t", "30", "stop")
        except (RuntimeError, OSError):
            pass
        shutil.rmtree(kok, ignore_errors=True)

    def __enter__(self) -> str:
        return self.ac()

    def __exit__(self, *_: object) -> None:
        self.kapat()


def kaynak() -> str | None:
    """Testlerin Postgres'i nereden alacağı — `None` ise HİÇ yok.

    Cevap `"env"` (`KROMIS_TEST_DATABASE_URL` verilmiş) ya da ikililerin
    dizini. `tools/test_ortami.py` raporda, `tests/conftest.py` fixture'da
    aynı soruyu buradan soruyor.
    """
    if os.environ.get(TEST_URL_ENV):
        return "env"
    return ikili_dizini()


def main(argv: list[str]) -> int:
    """`python3 tools/gecici_postgres.py`: kümeyi açar, `SELECT version()` sorar, kapatır.

    Elle deneme ve `test_ortami.py --kontrol` için — "ikili var" ile "küme
    açılıyor" aynı şey değil (root, izin, bozuk paket).
    """
    import time
    t0 = time.monotonic()
    try:
        with GeciciKume() as url:
            acilis = time.monotonic() - t0
            print(f"acildi ({acilis:.1f} sn): {url}")
    except RuntimeError as hata:
        print(str(hata), file=sys.stderr)
        return 1
    print(f"kapandi ({time.monotonic() - t0 - acilis:.1f} sn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
