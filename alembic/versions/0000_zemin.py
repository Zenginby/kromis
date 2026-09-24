# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Zemin — BOŞ ilk göç: yalnız `alembic_version` tablosu doğar (Faz 1 / 1. görev).

Revision: 0000_zemin
Önceki:   yok

NEDEN BOŞ BİR GÖÇ: bu görev veri modelini getirmiyor (o 2. görev,
`faz1/veri-modeli`); getirdiği şey göç HATTININ kendisi — `alembic upgrade
head` boş bir Postgres'te geçiyor, `alembic current` bir sürüm söylüyor,
`alembic check` boş `MetaData` ile "fark yok" diyor. Yani CI'daki Postgres
servisi, yerel geçici küme ve test fixture'ının şablon DB'si bugünden aynı
komutla kuruluyor; 2. görev bu dosyanın ÜSTÜNE `0001_…` koyar, bu dosyaya
dokunmaz. Geri alma da boş: `downgrade base` tabloyu Alembic kendisi düşürür.
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "0000_zemin"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
