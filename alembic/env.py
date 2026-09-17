# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Alembic ortam betiği — URL'yi `services/db.py` ile AYNI yerden okur (Faz 1 / 1. görev).

Alembic bu dosyayı `alembic.ini`deki `script_location`dan yol ile yükler
(paket değil), bu yüzden depo kökü `sys.path`e elle giriyor; `prepend_sys_path
= .` yalnız komut satırı `alembic` için yeterdi, programatik çağrı
(`alembic.command.upgrade`, tests/conftest.py) için değil.

Bağlantı dizesi ÖNCELİK SIRASIYLA:
  1. `config.attributes["baglanti_dizesi"]` — programatik çağrının verdiği
     (test fixture'ı şablon DB'yi böyle göçürüyor; Alembic'in belgelediği
     "attributes ile bağlam geçirme" deseni),
  2. `DATABASE_URL` (`services.db.baglanti_dizesi`) — komut satırı ve
     dağıtım öncesi komut.
İkisi de yoksa açık bir hata: sessizce SQLite'a ya da localhost'a düşmek,
"göç koştu" sanılan bir hiçlik üretir.

`target_metadata` = `services.tablolar.Base.metadata` (2. görevden beri; 1.
görevde boş `MetaData()` idi ki `alembic check` ilk günden koşabilsin). Model
ithal ediliyor, yani `alembic` komutu `models`/`catalog`ı da yükler — göç
aracının uygulama kodunu görmesi kaçınılmaz, çünkü CHECK değer kümeleri o
sabitlerden okunuyor (services/tablolar.py, "ENUM'LAR CHECK İLE").
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import db, tablolar  # noqa: E402  — `sys.path` üstte kuruldu, gerekçesi docstring'de

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = tablolar.Base.metadata


def _url() -> str:
    url = config.attributes.get("baglanti_dizesi") or db.baglanti_dizesi()
    if not url:
        raise SystemExit(
            f"{db.DATABASE_URL_ENV} verilmedi: alembic hangi veri tabanina gidecegini bilmiyor. "
            f"Ornek: {db.DATABASE_URL_ENV}=postgresql+psycopg://kullanici:parola@konak/db "
            "alembic upgrade head")
    return url


def run_migrations_offline() -> None:
    """`--sql` kipi: bağlanmaz, SQL'i basar (bir DBA'nın önce okuması için)."""
    context.configure(url=_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # `NullPool`: göç aracı tek bağlantı açar ve çıkar; havuz tutmanın anlamı
    # yok, hatta şablon DB'den `CREATE DATABASE … TEMPLATE` yapacak fixture
    # için ZARARLI — şablona açık bağlantı kalırsa kopya reddedilir.
    ayarlar = dict(config.get_section(config.config_ini_section) or {})
    ayarlar["sqlalchemy.url"] = _url()
    motor = engine_from_config(ayarlar, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with motor.connect() as baglanti:
        context.configure(connection=baglanti, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
