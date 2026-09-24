# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""`medya.arena_win` — arena turunun kazanan işareti (Faz 1 / 5. görev).

Revision: 0003_arena_win
Önceki:   0002_deneme_turu
Tarih:    2026-09-17

NEDEN: belgenin envanteri (`history.json` → `medya`) `storage.save`in yazdığı
12 + 5 alanı saydı; `arena_win` o listede yok, çünkü onu `save` değil
`storage.set_arena_winner` yazıyor — kayıt ÜRETİLDİKTEN sonra, turun kazananı
seçilince. Galeri DB'ye taşınırken `POST /api/arena/{id}/winner` ve arena
dökümünün `arena_win` okuması bir sütun istedi. NULL'lanabilir `boolean`,
öteki koşullu alanlarla aynı disiplin (NULL = alan JSON'da yok). Kısıt yok
(gerekçe `services/tablolar.py::Medya`). GERİ ALINABİLİR: `downgrade` sütunu
düşürür (ileri-geri-ileri döngüsü tests/test_db.py'de).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_arena_win"
down_revision: str | Sequence[str] | None = "0002_deneme_turu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("medya", sa.Column("arena_win", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("medya", "arena_win")
