# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri modeli — 4 hesap + 7 iş tablosu, ilk GERÇEK göç (Faz 1 / 2. görev).

Revision: 0001_veri_modeli
Önceki:   0000_zemin
Tarih:    2026-09-17

NEDEN: çok kullanıcılı web (docs/faz1-veritabani-hesaplar.md) bugünkü JSON
depolarını PostgreSQL'e taşıyor; bu dosya o şemanın doğduğu yer. Şemanın
GEREKÇESİ burada değil `services/tablolar.py`nin başında (sütun adları,
kimlik uzayları, hangi bağ FK hangi bağ değil, CHECK'ler, NULL'un anlamı) —
göç dosyası tarihçedir, karar belgesi değil. Bu dosya `alembic revision
--autogenerate` ile üretildi ve ELLE dört yerde düzeltildi:

1. `CREATE EXTENSION IF NOT EXISTS citext` başa eklendi: `kullanicilar.eposta`
   ve `giris_denemeleri.eposta` citext ve autogenerate eklentileri GÖRMEZ —
   uzantısız `upgrade` ilk tabloda "type citext does not exist" ile düşerdi.
   Yönetilen Postgres'lerde (Neon, Supabase, RDS) uzantı DB sahibine açık.
   `downgrade` uzantıyı da düşürür: tablo kalmayınca ona bağlı bir şey yok.
2. Tablo SIRASI belirlendi: autogenerate sözlük sırasıyla yazıyor (`medya`
   en sonda, `giris_denemeleri` başta); burada hesap tabloları önce
   (`kullanicilar` → ona bağlı üçü), sonra iş tabloları FK bağımlılığına göre
   (`klasorler`, `medya` ona bağlı, …). Okuyan kişi şemayı belgedeki sırayla
   görür; `downgrade` tam tersi.
3. Dosya adı: `file_template = %(rev)s_%(slug)s` ile `--rev-id 0001_veri_modeli`
   `0001_veri_modeli_veri_modeli.py` üretti (slug iki kez); `0001_veri_modeli.py`
   olarak adlandırıldı. `revision` alanı zaten aynı dizeyi taşıyor.
4. "auto generated … please adjust" işaretleri kaldırıldı, başlık yazıldı.

Kısıt adları `op.f(...)` ile: ad zaten `MetaData(naming_convention)` ile
üretilmiş, Alembic ikinci kez kural uygulamasın (services/tablolar.py,
"ADLANDIRMA KURALI"). GERİ ALINABİLİR: `downgrade` 11 tabloyu ve uzantıyı
düşürür; ileri-geri-ileri döngüsü `tests/test_tablolar.py`de sınanıyor.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_veri_modeli"
down_revision: str | Sequence[str] | None = "0000_zemin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (1) citext — gerekçesi docstring'de. `IF NOT EXISTS`: paylaşılan bir
    # sunucuda başka bir DB'nin uzantısı değil, bu DB'nin; ama önceden elle
    # kurulmuş olabilir.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # ── hesap ──────────────────────────────────────────────────────────
    op.create_table("kullanicilar",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("eposta", postgresql.CITEXT(), nullable=False),
        sa.Column("parola_ozeti", sa.Text(), nullable=True),
        sa.Column("dogrulandi_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dil", sa.Text(), nullable=True),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellendi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("silindi_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("dil IN ('tr', 'en')", name=op.f("ck_kullanicilar_dil_kumesi")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kullanicilar")),
        sa.UniqueConstraint("eposta", name=op.f("uq_kullanicilar_eposta"))
    )
    op.create_table("oturumlar",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("jeton_ozeti", sa.LargeBinary(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("son_gorulme", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("istemci", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_oturumlar_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oturumlar")),
        sa.UniqueConstraint("jeton_ozeti", name=op.f("uq_oturumlar_jeton_ozeti"))
    )
    op.create_index("ix_oturumlar_kullanici", "oturumlar", ["kullanici_id"], unique=False)
    op.create_table("jetonlar",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("amac", sa.Text(), nullable=False),
        sa.Column("ozet", sa.LargeBinary(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kullanildi_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amac IN ('eposta_dogrulama', 'parola_sifirlama')", name=op.f("ck_jetonlar_amac_kumesi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_jetonlar_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jetonlar")),
        sa.UniqueConstraint("ozet", name=op.f("uq_jetonlar_ozet"))
    )
    op.create_index("ix_jetonlar_kullanici", "jetonlar", ["kullanici_id"], unique=False)
    op.create_table("giris_denemeleri",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("eposta", postgresql.CITEXT(), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("zaman", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_giris_denemeleri"))
    )
    op.create_index("ix_giris_denemeleri_eposta_zaman", "giris_denemeleri", ["eposta", "zaman"], unique=False)
    op.create_index("ix_giris_denemeleri_ip_zaman", "giris_denemeleri", ["ip", "zaman"], unique=False)

    # ── iş (JSON depolarının karşılığı; sıra FK bağımlılığına göre) ──
    op.create_table("klasorler",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), nullable=True),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{8,32}$'", name=op.f("ck_klasorler_id_bicimi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_klasorler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["klasorler.id"], name=op.f("fk_klasorler_parent_id_klasorler"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_klasorler"))
    )
    op.create_index("ix_klasorler_kullanici_olusturuldu", "klasorler", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_index("ix_klasorler_parent", "klasorler", ["parent_id"], unique=False)
    op.create_table("medya",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("size", sa.Text(), nullable=False),
        sa.Column("quality", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), nullable=True),
        sa.Column("folder_id", sa.Text(), nullable=True),
        sa.Column("palette", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_sent", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Boolean(), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("arena_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{8,32}$'", name=op.f("ck_medya_id_bicimi")),
        sa.ForeignKeyConstraint(["folder_id"], ["klasorler.id"], name=op.f("fk_medya_folder_id_klasorler"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_medya_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medya")),
        sa.UniqueConstraint("filename", name=op.f("uq_medya_filename"))
    )
    op.create_index("ix_medya_kullanici_folder", "medya", ["kullanici_id", "folder_id"], unique=False)
    op.create_index("ix_medya_kullanici_olusturuldu", "medya", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_table("sohbetler",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("mesajlar", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellendi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{8,32}$'", name=op.f("ck_sohbetler_id_bicimi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_sohbetler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sohbetler"))
    )
    op.create_index("ix_sohbetler_kullanici_guncellendi", "sohbetler", ["kullanici_id", "guncellendi"], unique=False)
    op.create_index("ix_sohbetler_kullanici_olusturuldu", "sohbetler", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_table("paletler",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("seed", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("strength", sa.Text(), nullable=False),
        sa.Column("colors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{8,32}$'", name=op.f("ck_paletler_id_bicimi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_paletler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paletler"))
    )
    op.create_index("ix_paletler_kullanici_olusturuldu", "paletler", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_table("varliklar",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tur", sa.Text(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{8,32}$'", name=op.f("ck_varliklar_id_bicimi")),
        sa.CheckConstraint("tur IN ('logos', 'banners', 'mottos')", name=op.f("ck_varliklar_tur_kumesi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_varliklar_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_varliklar"))
    )
    op.create_index("ix_varliklar_kullanici_olusturuldu", "varliklar", ["kullanici_id", "olusturuldu"], unique=False)
    op.create_index("ix_varliklar_kullanici_tur", "varliklar", ["kullanici_id", "tur"], unique=False)
    op.create_table("tercihler",
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("autosave_sessions", sa.Boolean(), nullable=True),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("guncelleme_kontrolu", sa.Boolean(), nullable=True),
        sa.Column("image_model", sa.Text(), nullable=True),
        sa.Column("video_model", sa.Text(), nullable=True),
        sa.Column("chat_provider", sa.Text(), nullable=True),
        sa.Column("chat_model", sa.Text(), nullable=True),
        sa.Column("director_guidance", sa.Text(), nullable=True),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellendi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("language IN ('tr', 'en')", name=op.f("ck_tercihler_language_kumesi")),
        sa.CheckConstraint("theme IN ('mono', 'ocean', 'amber', 'viola')", name=op.f("ck_tercihler_theme_kumesi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_tercihler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kullanici_id", name=op.f("pk_tercihler"))
    )
    op.create_table("saglayici_kimlikleri",
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("ad", sa.Text(), nullable=False),
        sa.Column("sifreli_deger", sa.LargeBinary(), nullable=False),
        sa.Column("anahtar_surumu", sa.Integer(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellendi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"], name=op.f("fk_saglayici_kimlikleri_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kullanici_id", "ad", name=op.f("pk_saglayici_kimlikleri"))
    )


def downgrade() -> None:
    # Ters sıra: bağlı olan önce düşer. `drop_table` tablonun indekslerini de
    # götürür, ayrı `drop_index` gerekmez.
    op.drop_table("saglayici_kimlikleri")
    op.drop_table("tercihler")
    op.drop_table("varliklar")
    op.drop_table("paletler")
    op.drop_table("sohbetler")
    op.drop_table("medya")
    op.drop_table("klasorler")
    op.drop_table("giris_denemeleri")
    op.drop_table("jetonlar")
    op.drop_table("oturumlar")
    op.drop_table("kullanicilar")
    # Uzantı en son: artık ona bağlı sütun yok.
    op.execute("DROP EXTENSION IF EXISTS citext")
