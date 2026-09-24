# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ödeme şeması ve iki kova — `kova`, `paket` türü, `paket_bakiye`, Polar/rıza/silme sütunları, `urunler`/`siparisler`/`odeme_olaylari`, RLS (Faz 4 / 2. görev).

Revision: 0008_odeme
Önceki:   0007_kredi
Tarih:    2026-09-21

NEDEN: Faz 3'ün defteri parayı SAYIYOR ama bakiyeye para girişi yalnız aylık
hibe ve admin düzeltmesi (docs/faz4-odeme-abonelik-kvkk.md, giriş). Bu göç
PARAYI ALACAK şemayı açar; davranış DEĞİŞMEZ (webhook 3., checkout 4. görev),
gerekçeler `services/tablolar.py`de (`KOVALAR`, `Urun`, `Siparis`, `OdemeOlayi`),
bu dosya tarihçe.

FAZ 4'ÜN TEK GÖÇÜ (belge "NEDEN TEK GÖÇ"): dört görevin sütun ve tabloları
burada — `kredi_hareketleri.kova` + `tur` kümesine `paket` ve `kullanicilar.
paket_bakiye` (2), `urunler`/`siparisler`/`odeme_olaylari` (3-4),
`kullanicilar.polar_musteri_id`/`polar_abonelik_id`/`plan_bitis` (3),
`sartlar_kabul_at`/`sartlar_surumu` (6), `temizlendi_at` (5). Hepsi NULL ya da
öntanımlı (`kova` 'hibe', `paket_bakiye` 0): mevcut satırlar dokunulmadan
geçer — bugüne kadar her defter satırı hibe kovasıydı, öntanım o olguyu yazar.
Sahibin canlıda BİR `tools/goc.py` koşusu; 3-6. görevler şemayı hazır bulur.

`tur` CHECK'İ DÜŞÜP YENİDEN KURULUR (`ck_kredi_hareketleri_tur_kumesi`): Postgres
CHECK'i değiştiremez, yalnız düşürüp koyar; adı aynı kalır ki model
(`tablolar.HAREKET_TURLERI`) ile göç aynı kısıtı anlatsın. Literal 7 değer
burada TARİHÇE; kümenin bekçisi tests/test_tablolar.py (her üye yazılır,
`satin_alma` reddedilir) — `alembic check` CHECK karşılaştırmıyor.

RLS (belge §2, K4 devamı): `siparisler` `kullanici_id` taşır → `kiraci.IS_TABLOLARI`
(9 → 10), `0006_rls`nin üç politikası AYNEN + `FORCE`, ARTI `yonetici_ekler`
INSERT (0007'nin deseni): webhook oturumsuz, admin bağlamında yazar
(`YONETICI_EKLER_TABLOLARI` 1 → 2). Politika 28 → 32. `urunler` ve
`odeme_olaylari` POLİTİKASIZ: platformun tabloları (`isciler` gibi) — biri
herkese açık fiyat listesi, ötekinin sahibi olmayan satırı olabilir
(`kullanici_id` NULL) ve yalnız admin okur.

GERİ ALINABİLİR, TEK KOŞULLA: `downgrade` üç tabloyu, dokuz sütunu ve iki
CHECK'i düşürür — ama `kova = 'paket'` ya da `tur = 'paket'` satırı VARSA
DURUR (`RuntimeError`): o satırlar parayla alınmış kredidir, `kova` sütunuyla
birlikte sessizce silinmesi geri alınamaz veri kaybı olurdu; sahip önce
satırları elle karar verip taşır (belge "Veri modeli"; test bunu çiviler,
tests/test_defter.py). Paket satırı yoksa ileri-geri-ileri temiz.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_odeme"
down_revision: str | Sequence[str] | None = "0007_kredi"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Göç dosyasının kendi literali (tarihçe): services/kiraci.py::IS_TABLOLARI'nın 2026-09-21 hâli (9 → 10).
TABLOLAR: tuple[str, ...] = ("klasorler", "medya", "sohbetler", "paletler", "varliklar",
                             "tercihler", "saglayici_kimlikleri", "isler", "kredi_hareketleri", "siparisler")
# Bu göçün politika koyduğu tablo(lar); öteki dokuzunun politikası 0006_rls (8) ve 0007_kredi (1)'de.
RLS_TABLOLAR: tuple[str, ...] = ("siparisler",)
# Dördüncü politikayı (`yonetici_ekler` INSERT) bu göçte alan tablo(lar) — 0007'nin literaliyle birlikte
# kiraci.YONETICI_EKLER_TABLOLARI'nı verir.
YONETICI_EKLER: tuple[str, ...] = ("siparisler",)
# Bu göçün yarattığı tablolar, düşürme sırasıyla (FK: `siparisler` → `urunler`).
YENI_TABLOLAR: tuple[str, ...] = ("siparisler", "odeme_olaylari", "urunler")

_SAHIP = "kullanici_id = NULLIF(current_setting('app.kullanici_id', true), '')::uuid"
_ADMIN = "current_setting('app.rol', true) = 'admin'"
_TUR_ESKI = "tur IN ('hibe', 'rezerv', 'onay', 'iade', 'duzeltme', 'sona_erme')"
_TUR_YENI = "tur IN ('hibe', 'rezerv', 'onay', 'iade', 'duzeltme', 'sona_erme', 'paket')"


def upgrade() -> None:
    # ── kredi_hareketleri: kova + paket türü ─────────────────────────────
    op.add_column("kredi_hareketleri",
                  sa.Column("kova", sa.Text(), server_default=sa.text("'hibe'"), nullable=False))
    op.create_check_constraint(op.f("ck_kredi_hareketleri_kova_kumesi"), "kredi_hareketleri",
                               "kova IN ('hibe', 'paket')")
    op.drop_constraint(op.f("ck_kredi_hareketleri_tur_kumesi"), "kredi_hareketleri", type_="check")
    op.create_check_constraint(op.f("ck_kredi_hareketleri_tur_kumesi"), "kredi_hareketleri", _TUR_YENI)

    # ── kullanicilar: ikinci kova + Polar + rıza + silme ─────────────────
    op.add_column("kullanicilar",
                  sa.Column("paket_bakiye", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("kullanicilar", sa.Column("polar_musteri_id", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_kullanicilar_polar_musteri_id"), "kullanicilar", ["polar_musteri_id"])
    op.add_column("kullanicilar", sa.Column("polar_abonelik_id", sa.Text(), nullable=True))
    op.add_column("kullanicilar", sa.Column("plan_bitis", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kullanicilar", sa.Column("sartlar_kabul_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("kullanicilar", sa.Column("sartlar_surumu", sa.Text(), nullable=True))
    op.add_column("kullanicilar", sa.Column("temizlendi_at", sa.DateTime(timezone=True), nullable=True))

    # ── urunler (altyapı, politikasız) ───────────────────────────────────
    op.create_table("urunler",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("polar_urun_id", sa.Text(), nullable=False),
        sa.Column("tur", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("kredi", sa.Integer(), nullable=False),
        sa.Column("fiyat_kurus", sa.Integer(), nullable=False),
        sa.Column("para_birimi", sa.Text(), nullable=False),
        sa.Column("ad", sa.Text(), nullable=False),
        sa.Column("aktif", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("guncellendi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tur IN ('plan', 'paket')", name=op.f("ck_urunler_tur_kumesi")),
        sa.CheckConstraint("plan IN ('free', 'temel', 'pro')", name=op.f("ck_urunler_plan_kumesi")),
        sa.CheckConstraint("(tur = 'plan') = (plan IS NOT NULL)", name=op.f("ck_urunler_tur_plan_uyumu")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_urunler")),
        sa.UniqueConstraint("polar_urun_id", name=op.f("uq_urunler_polar_urun_id"))
    )

    # ── siparisler (iş tablosu, RLS dört politika) ───────────────────────
    op.create_table("siparisler",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kullanici_id", sa.UUID(), nullable=False),
        sa.Column("polar_siparis_id", sa.Text(), nullable=False),
        sa.Column("polar_abonelik_id", sa.Text(), nullable=True),
        sa.Column("urun_id", sa.UUID(), nullable=False),
        sa.Column("sebep", sa.Text(), nullable=False),
        sa.Column("tutar_kurus", sa.Integer(), nullable=False),
        sa.Column("para_birimi", sa.Text(), nullable=False),
        sa.Column("olusturuldu", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sebep IN ('purchase', 'subscription_create', 'subscription_cycle', 'subscription_update')",
                           name=op.f("ck_siparisler_sebep_kumesi")),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"],
                                name=op.f("fk_siparisler_kullanici_id_kullanicilar"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["urun_id"], ["urunler.id"], name=op.f("fk_siparisler_urun_id_urunler")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_siparisler")),
        sa.UniqueConstraint("polar_siparis_id", name=op.f("uq_siparisler_polar_siparis_id"))
    )
    op.create_index("ix_siparisler_kullanici_olusturuldu", "siparisler", ["kullanici_id", "olusturuldu"],
                    unique=False)

    # ── odeme_olaylari (altyapı, politikasız) ────────────────────────────
    op.create_table("odeme_olaylari",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("webhook_id", sa.Text(), nullable=False),
        sa.Column("tur", sa.Text(), nullable=False),
        sa.Column("polar_nesne_id", sa.Text(), nullable=True),
        sa.Column("kullanici_id", sa.UUID(), nullable=True),
        sa.Column("govde", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alindi", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("islendi_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hata", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["kullanici_id"], ["kullanicilar.id"],
                                name=op.f("fk_odeme_olaylari_kullanici_id_kullanicilar"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_odeme_olaylari")),
        sa.UniqueConstraint("webhook_id", name=op.f("uq_odeme_olaylari_webhook_id"))
    )
    op.create_index("ix_odeme_olaylari_alindi", "odeme_olaylari", ["alindi"], unique=False)

    # ── RLS: siparisler ──────────────────────────────────────────────────
    for tablo in RLS_TABLOLAR:
        op.execute(f"ALTER TABLE {tablo} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tablo} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY sahip ON {tablo} USING ({_SAHIP}) WITH CHECK ({_SAHIP})")
        op.execute(f"CREATE POLICY yonetici_okur ON {tablo} FOR SELECT USING ({_ADMIN})")
        op.execute(f"CREATE POLICY yonetici_gunceller ON {tablo} FOR UPDATE USING ({_ADMIN})")
    for tablo in YONETICI_EKLER:
        op.execute(f"CREATE POLICY yonetici_ekler ON {tablo} FOR INSERT WITH CHECK ({_ADMIN})")


def downgrade() -> None:
    # PARAYLA ALINMIŞ KREDİ SİLİNMEZ: `kova`/`tur = 'paket'` satırı varsa göç durur (dosya başı).
    baglanti = op.get_bind()
    paket = baglanti.execute(sa.text(
        "SELECT count(*) FROM kredi_hareketleri WHERE kova = 'paket' OR tur = 'paket'")).scalar_one()
    if paket:
        raise RuntimeError(f"0008_odeme geri alinamaz: {paket} paket satiri var (kova/tur = 'paket'); "
                           "satirlar parayla alinmis kredidir, once elle karar verilip tasinmali")
    # Politikalar ve indeksler tabloyla gider; sütunlar ve CHECK ayrı ayrı.
    op.drop_index("ix_odeme_olaylari_alindi", table_name="odeme_olaylari")
    op.drop_index("ix_siparisler_kullanici_olusturuldu", table_name="siparisler")
    for tablo in YENI_TABLOLAR:
        op.drop_table(tablo)
    for sutun in ("temizlendi_at", "sartlar_surumu", "sartlar_kabul_at", "plan_bitis", "polar_abonelik_id"):
        op.drop_column("kullanicilar", sutun)
    op.drop_constraint(op.f("uq_kullanicilar_polar_musteri_id"), "kullanicilar", type_="unique")
    op.drop_column("kullanicilar", "polar_musteri_id")
    op.drop_column("kullanicilar", "paket_bakiye")
    op.drop_constraint(op.f("ck_kredi_hareketleri_tur_kumesi"), "kredi_hareketleri", type_="check")
    op.create_check_constraint(op.f("ck_kredi_hareketleri_tur_kumesi"), "kredi_hareketleri", _TUR_ESKI)
    op.drop_constraint(op.f("ck_kredi_hareketleri_kova_kumesi"), "kredi_hareketleri", type_="check")
    op.drop_column("kredi_hareketleri", "kova")
