# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""`isler.anahtar_kaynagi` ve `kullanicilar.gunluk_kredi_tavani` — kota (Faz 2 / 6. görev).

Revision: 0005_kota
Önceki:   0004_isler
Tarih:    2026-09-18

NEDEN: platform sahipli sağlayıcı anahtarı geliyor (`KROMIS_PLATFORM_<AD>`,
services/platform_anahtari.py) ve bu görevden sonra platformun parası
harcanıyor (docs/faz2-kuyruk-anahtarlar-depolama.md §6). Günlük kredi tavanı
(services/kota.py) yalnız PLATFORM anahtarıyla koşan işleri toplamalı — BYOK
kendi parası — o yüzden iş satırı hangi anahtarla koştuğunu yazar:
`anahtar_kaynagi text CHECK IN ('kullanici', 'platform')`, NULL = bu göçten
önceki satır (kaynağı bilinmiyor, sayılmaz). Tavanın kullanıcı başına ezmesi
`kullanicilar.gunluk_kredi_tavani int NULL` (NULL = ortamın öntanımlısı; admin
8. görevde yazar). Gerekçeler `services/tablolar.py`de; bu dosya tarihçe.

İNDEKS YOK: iki kota sorgusu da (`kullanici_id`, `olusturuldu > now - pencere`)
mevcut `ix_isler_kullanici_olusturuldu`yu kullanır; `anahtar_kaynagi` süzgeci
o aralıkta tarama. GERİ ALINABİLİR: `downgrade` iki sütunu düşürür (CHECK
sütunla gider); ileri-geri-ileri döngüsü tests/test_db.py.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_kota"
down_revision: str | Sequence[str] | None = "0004_isler"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("isler", sa.Column("anahtar_kaynagi", sa.Text(), nullable=True))
    op.create_check_constraint(op.f("ck_isler_anahtar_kaynagi_kumesi"), "isler",
                               "anahtar_kaynagi IN ('kullanici', 'platform')")
    op.add_column("kullanicilar", sa.Column("gunluk_kredi_tavani", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("kullanicilar", "gunluk_kredi_tavani")
    op.drop_constraint(op.f("ck_isler_anahtar_kaynagi_kumesi"), "isler", type_="check")
    op.drop_column("isler", "anahtar_kaynagi")
