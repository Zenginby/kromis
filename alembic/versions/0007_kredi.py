# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kredi defteri — `kredi_hareketleri`, `kullanicilar.bakiye`/`plan`, Faz 3'ün ileri sütunları, RLS (Faz 3 / 1. görev).

Revision: 0007_kredi
Önceki:   0006_rls
Tarih:    2026-09-19

NEDEN: Faz 2 her iş satırına bir tahmin, her medya satırına bir gerçek yazıyor
ama ikisi de yalnız metadata — bakiye yok, düşüm yok
(docs/faz3-kredi-defteri-filigran.md, giriş). Bu göç PARAYI SAYACAK şemayı
açar; davranış DEĞİŞMEZ (rota ve işçi 2. görevde çağırır), gerekçeler
`services/tablolar.py::KrediHareketi`de, bu dosya tarihçe.

FAZ 3'ÜN TEK GÖÇÜ (belge, "NEDEN TEK GÖÇ"): dört görevin sütunları burada —
`kredi_hareketleri` (1), `kullanicilar.bakiye` (1) ve `plan` (3),
`isler.kredi_gercek` (2), `isler.saglayici_meta`/`saglayici_maliyet_usd` (5),
`medya.filigranli` (4). Hepsi NULL ya da öntanımlı (`bakiye` 0, `plan` 'free',
`filigranli` false): mevcut satırlar dokunulmadan geçer, dört ayrı göç dört
ayrı `alembic check` turu ve sahibin canlıda dört `tools/goc.py` koşusu
olurdu. `kullanicilar.plan` CHECK'i `services/tablolar.py::PLANLAR_KUMESI`nden
(`text + CHECK`, Faz 1 / 2 kararı; bekçi tests/test_tablolar.py).

RLS (belge §1, K4): `kredi_hareketleri` `kullanici_id` taşır →
`kiraci.IS_TABLOLARI`ya girer (8 → 9), `0006_rls`nin üç politikası AYNEN
(`sahip` ALL, `yonetici_okur` SELECT, `yonetici_gunceller` UPDATE) + `FORCE`.
ARTI, yalnız bu tabloda, dördüncü politika **`yonetici_ekler` FOR INSERT WITH
CHECK (app.rol = 'admin')**: iki yazar admin bağlamında yazar — admin
düzeltmesi (`defter.duzelt`, `admin_id` izi) ve işçinin bakım turu (aylık
hibe, bayat işin iadesi; `isci.py` `rol=ADMIN`). DELETE yine kimseye yok:
defter append-only. Öteki sekiz tabloda admin INSERT yapamaz (0006 kararı
durur). `TABLOLAR` bu göçün 9'lu literali (tarihçe; bekçi tests/test_rls.py
`kiraci.IS_TABLOLARI` ile karşılaştırır), `RLS_TABLOLAR` bu göçün politika
KOYDUĞU tablo (öteki sekizi 0006 koydu).

İNDEKSLER: `(kullanici_id, olusturuldu)` hareket listesi (`medya`nın deseni),
`(is_id)` onay/iade "bu işin rezervi var mı". `idempotency_anahtari` UNIQUE'i
sütunla gelir (`uq_…`). GERİ ALINABİLİR: `downgrade` tabloyu (politikalar ve
indeksler onunla), beş sütunu ve `plan` CHECK'ini düşürür; ileri-geri-ileri
tests/test_defter.py ve tests/test_db.py. `alembic check` politikaları da
CHECK'leri de karşılaştırmıyor — bekçileri tests/test_rls.py (`pg_policies`)
ve tests/test_tablolar.py (her izinli değer yazılır, dışı reddedilir).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_kredi"
down_revision: str | Sequence[str] | None = "0006_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Göç dosyasının kendi literali (tarihçe): services/kiraci.py::IS_TABLOLARI'nın 2026-09-19 hâli (8 → 9).
TABLOLAR: tuple[str, ...] = ("klasorler", "medya", "sohbetler", "paletler", "varliklar",
                             "tercihler", "saglayici_kimlikleri", "isler", "kredi_hareketleri")
# Bu göçün politika koyduğu tablo(lar); öteki sekizinin politikası 0006_rls'te.
RLS_TABLOLAR: tuple[str, ...] = ("kredi_hareketleri",)
# Dördüncü politikayı (`yonetici_ekler` INSERT) alan tablo(lar) — kiraci.YONETICI_EKLER_TABLOLARI'nın literali.
YONETICI_EKLER: tuple[str, ...] = ("kredi_hareketleri",)

_SAHIP = "kullanici_id = NULLIF(current_setting('app.kullanici_id', true), '')::uuid"
_ADMIN = "current_setting('app.rol', true) = 'admin'"


def upgrade() -> None:
    op.create_table("kredi_hareketleri",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("is_id", sa.UUID(), nullable=True),
        sa.Column("tur", sa.Text(), nullable=False),
        sa.Column("miktar", sa.Integer(), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("admin_id", sa.UUID(), nullable=True),
        sa.Column("idempotency_anahtari", sa.Text(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tur IN ('hibe', 'rezerv', 'onay', 'iade', 'duzeltme', 'sona_erme')",
                           name=op.f("ck_kredi_hareketleri_tur_kumesi")),
        sa.ForeignKeyConstraint(["admin_id"], ["kullanicilar.id"],
                                name=op.f("fk_kredi_hareketleri_admin_id_kullanicilar"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["is_id"], ["isler.id"],
                                name=op.f("fk_kredi_hareketleri_is_id_isler"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"],
                                name=op.f("fk_kredi_hareketleri_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kredi_hareketleri")),
        sa.UniqueConstraint("idempotency_anahtari", name=op.f("uq_kredi_hareketleri_idempotency_anahtari"))
    )
    op.create_index("ix_kredi_hareketleri_is", "kredi_hareketleri", ["is_id"], unique=False)
    op.create_index("ix_kredi_hareketleri_kullanici_olusturuldu", "kredi_hareketleri",
                    ["kullanici_id", "olusturuldu"], unique=False)

    op.add_column("kullanicilar", sa.Column("bakiye", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("kullanicilar", sa.Column("plan", sa.Text(), server_default=sa.text("'free'"), nullable=False))
    op.create_check_constraint(op.f("ck_kullanicilar_plan_kumesi"), "kullanicilar",
                               "plan IN ('free', 'temel', 'pro')")
    op.add_column("isler", sa.Column("kredi_gercek", sa.Integer(), nullable=True))
    op.add_column("isler", sa.Column("saglayici_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("isler", sa.Column("saglayici_maliyet_usd", sa.Numeric(precision=10, scale=6), nullable=True))
    op.add_column("medya", sa.Column("filigranli", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    for tablo in RLS_TABLOLAR:
        op.execute(f"ALTER TABLE {tablo} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tablo} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY sahip ON {tablo} USING ({_SAHIP}) WITH CHECK ({_SAHIP})")
        op.execute(f"CREATE POLICY yonetici_okur ON {tablo} FOR SELECT USING ({_ADMIN})")
        op.execute(f"CREATE POLICY yonetici_gunceller ON {tablo} FOR UPDATE USING ({_ADMIN})")
    for tablo in YONETICI_EKLER:
        op.execute(f"CREATE POLICY yonetici_ekler ON {tablo} FOR INSERT WITH CHECK ({_ADMIN})")


def downgrade() -> None:
    # Politikalar ve indeksler tabloyla gider; sütunlar ve CHECK ayrı ayrı.
    op.drop_column("medya", "filigranli")
    op.drop_column("isler", "saglayici_maliyet_usd")
    op.drop_column("isler", "saglayici_meta")
    op.drop_column("isler", "kredi_gercek")
    op.drop_constraint(op.f("ck_kullanicilar_plan_kumesi"), "kullanicilar", type_="check")
    op.drop_column("kullanicilar", "plan")
    op.drop_column("kullanicilar", "bakiye")
    op.drop_index("ix_kredi_hareketleri_kullanici_olusturuldu", table_name="kredi_hareketleri")
    op.drop_index("ix_kredi_hareketleri_is", table_name="kredi_hareketleri")
    op.drop_table("kredi_hareketleri")
