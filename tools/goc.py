#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Şema göçü — dağıtım ÖNCESİ tek seferlik komut (Faz 1 / 9, K6).

    DATABASE_URL=… python tools/goc.py

`alembic upgrade head`in ince sarmalayıcısı: bağlantı dizesini `services.db`
ile AYNI yerden okur (`DATABASE_URL`; `alembic/env.py` de oradan), göçü koşar,
sonda hangi sürümde olduğunu basar. İdempotent: `head`teyse hiçbir şey yapmaz,
yine 0 ile çıkar — platform her dağıtımda koşturur.

NEDEN KONTEYNER AÇILIŞINDA DEĞİL: `Dockerfile` CMD yalnız `uvicorn`. İki
replika aynı anda açılırsa iki `upgrade` yarışır — Alembic kilit tutmaz,
`CREATE TABLE` biri kazanır öteki `DuplicateTable` ile düşer. Yönetilen
platformların hepsinde dağıtım öncesi tek seferlik komut var (Fly
`release_command`, Railway pre-deploy, Render pre-deploy command) ve bu betik
imajda durur: `python tools/goc.py`. Yerel `compose.yaml`da aynı işi `goc`
servisi yapar, `kromis` onu `service_completed_successfully` ile bekler.
"Açılışta göç" bayrağı (`KROMIS_GOC_ACILISTA=1` gibi) BİLEREK YOK: tek
replikada rahat, ikincisi eklendiği gün tuzak — sonradan silinmesi gereken bir
kolaylık baştan konmuyor (docs/faz1-veritabani-hesaplar.md § 9).

ÇIKIŞ KODLARI öteki araçlarla bir (`tools/kullanici.py`): 0 tamam ·
1 göç düştü (bir betik hata verdi; DB o göçün transaksiyonu geri alınmış
hâlde) · 2 ortam (`DATABASE_URL` yok ya da sunucuya ulaşılamıyor).
"""
from __future__ import annotations

import argparse
import os
import sys

# Betik olarak koşarken (`python tools/goc.py`) `sys.path[0]` bu dizin ve kök
# modüller görünmez; testler `tools.goc` diye ithal ediyor.
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from alembic import command  # noqa: E402
from services import db  # noqa: E402

CIKIS_TAMAM = 0
CIKIS_GOC = 1
CIKIS_ORTAM = 2

ALEMBIC_INI = os.path.join(_KOK, "alembic.ini")


def yapilandirma(url: str) -> Config:
    """`alembic.ini` + programatik URL — `env.py`nin 1. önceliği (`config.attributes`)."""
    cfg = Config(ALEMBIC_INI)
    cfg.attributes["baglanti_dizesi"] = url
    return cfg


def bas(cfg: Config) -> str:
    """Göç hattının `head` sürümü (dosyalardan, DB'ye bakmadan)."""
    return str(ScriptDirectory.from_config(cfg).get_current_head())


def mevcut(url: str) -> str | None:
    """DB'nin `alembic_version` satırı; tablo yoksa (boş DB) `None`.

    `alembic current` ÇIKTISI değil, doğrudan değer: `command.current` yalnız
    stdout'a yazar, dönmez — sonunda "head'te miyiz" sorusuna cevap vermek için
    metin ayrıştırmak gerekirdi.
    """
    motor = create_engine(url, connect_args={"connect_timeout": db.BAGLANTI_ZAMAN_ASIMI_SN})
    try:
        with motor.connect() as baglanti:
            return MigrationContext.configure(baglanti).get_current_revision()
    finally:
        motor.dispose()


def _ayristirici() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="goc.py",
        description="Semayi head'e tasir (alembic upgrade head) — dagitim oncesi komut, "
                    "acilista degil. DATABASE_URL ile.")


def main(argv: list[str]) -> int:
    _ayristirici().parse_args(argv)
    url = db.baglanti_dizesi()
    if not url:
        print(f"{db.DATABASE_URL_ENV} verilmedi: goc hangi veri tabanina gidecegini bilmiyor.",
              file=sys.stderr)
        return CIKIS_ORTAM
    cfg = yapilandirma(url)
    hedef = bas(cfg)
    try:
        once = mevcut(url)
    except OperationalError as hata:
        # SQLAlchemy mesajı URL'deki parolayı maskeliyor; yine de yalnız ilk satır.
        print(f"veri tabanina ulasilamiyor: {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_ORTAM
    print(f"goc: mevcut {once or 'bos (alembic_version yok)'} -> hedef {hedef}")
    if once == hedef:
        print("goc: zaten head'te, yapilacak bir sey yok")
        return CIKIS_TAMAM
    try:
        command.upgrade(cfg, "head")
    except Exception as hata:  # bilinçle geniş: göç betiğinden ne gelirse kod 1, sebep stderr
        print(f"goc DUSTU ({type(hata).__name__}): {str(hata).splitlines()[0]}", file=sys.stderr)
        return CIKIS_GOC
    sonra = mevcut(url)
    print(f"goc: tamam, mevcut {sonra} ({'head' if sonra == hedef else 'head DEGIL'})")
    return CIKIS_TAMAM if sonra == hedef else CIKIS_GOC


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
