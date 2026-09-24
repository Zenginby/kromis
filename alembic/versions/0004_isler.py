# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""`isler` ve `isciler` — üretim kuyruğu ve işçi kalp atışı (Faz 2 / 1. görev).

Revision: 0004_isler
Önceki:   0003_arena_win
Tarih:    2026-09-17

NEDEN: sağlayıcı çağrısı (1-6 dk) bugün HTTP isteğinin içinde koşuyor ve
sekme yenilenince iş kayboluyor (docs/faz2-kuyruk-anahtarlar-depolama.md,
giriş). Faz 2 onu ayrı bir işçi sürecine taşıyor; bu göç o işin kaydını ve
kuyruğunu AYNI tabloda açıyor — Postgres `FOR UPDATE SKIP LOCKED` kuyruğun
kendisi, Redis yok (K1). Gerekçeler `services/tablolar.py::Is`/`Isci`de; bu
dosya tarihçe. Bu göçte davranış DEĞİŞMEZ: rotalar hâlâ senkron, tabloya
yazan yalnız `services/kuyruk.py` ve onun testleri (4. göreve kadar).

İki kısmi indeks (`postgresql_where`) — ve bir sınır: `alembic check` kısmi
indeksin `WHERE`ini KARŞILAŞTIRMIYOR (ölçüldü, 2026-09-17: modelin `WHERE`i
değiştirilip `check` koşuldu, "fark yok" dedi — CHECK kısıtlarındaki aynı
körlük, tests/test_tablolar.py'nin gerekçesi). Bu yüzden bekçisi ayrı:
`tests/test_kuyruk.py::test_the_queue_indexes_are_partial_in_the_database`
`pg_indexes.indexdef`i okur. Buradaki `WHERE` metni ile modeldeki
(`services/tablolar.py::Is`) ELLE aynı tutulur. `isler.isci_id` FK DEĞİL
(işçi kendi satırını siler, işin "kim koştu" kaydı durur). GERİ ALINABİLİR: `downgrade` iki tabloyu düşürür (indeksler tabloyla
gider); ileri-geri-ileri döngüsü tests/test_kuyruk.py ve tests/test_db.py'de.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_isler"
down_revision: str | Sequence[str] | None = "0003_arena_win"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("isler",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("tur", sa.Text(), nullable=False),
        sa.Column("durum", sa.Text(), server_default=sa.text("'bekliyor'"), nullable=False),
        sa.Column("istek", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sonuc", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("hata", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("kredi_tahmini", sa.Integer(), nullable=False),
        sa.Column("isci_id", sa.UUID(), nullable=True),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("basladi", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bitti", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kalp_atisi", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("durum IN ('bekliyor', 'calisiyor', 'bitti', 'hata', 'iptal')", name=op.f("ck_isler_durum_kumesi")),
        sa.CheckConstraint("tur IN ('generate', 'edit', 'video', 'animate')", name=op.f("ck_isler_tur_kumesi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_isler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_isler"))
    )
    op.create_index("ix_isler_kullanici_olusturuldu", "isler", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_index("ix_isler_kuyruk", "isler", ["durum", "olusturuldu"], unique=False,
                    postgresql_where=sa.text("durum = 'bekliyor'"))
    op.create_index("ix_isler_kullanici_aktif", "isler", ["kullanici_id", "olusturuldu"], unique=False,
                    postgresql_where=sa.text("durum IN ('bekliyor', 'calisiyor')"))
    op.create_table("isciler",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("konak", sa.Text(), nullable=False),
        sa.Column("surum", sa.Text(), nullable=False),
        sa.Column("basladi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("son_kalp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("es_zamanli", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_isciler"))
    )


def downgrade() -> None:
    op.drop_table("isciler")
    op.drop_index("ix_isler_kullanici_aktif", table_name="isler")
    op.drop_index("ix_isler_kuyruk", table_name="isler")
    op.drop_index("ix_isler_kullanici_olusturuldu", table_name="isler")
    op.drop_table("isler")
