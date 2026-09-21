# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri modeli — 17 tablo, SQLAlchemy 2 `DeclarativeBase` (Faz 1 / 2. görev; Faz 2 / 1: `isler`, `isciler`; Faz 3 / 1: `kredi_hareketleri`; Faz 4 / 2: `urunler`, `siparisler`, `odeme_olaylari`).

Bu modül ŞEMANIN tek tanımı: Alembic `alembic/env.py`de `Base.metadata`yı
okur, `alembic check` göç dosyalarının bu tanımdan ayrışmadığını sınar
(tests/test_tablolar.py). Burada sorgu YOK, depo işlevi YOK — onlar 5-7.
görevlerin `services/depo/` modülleri; burası yalnız tablo, sütun, kısıt.

Dört tablo hesabın (`kullanicilar`, `oturumlar`, `jetonlar`, `giris_denemeleri`),
yedisi bugünkü JSON depolarının karşılığı (docs/faz1-veritabani-hesaplar.md,
"Envanter"): `medya` ← history.json, `klasorler` ← folders.json, `sohbetler`
← chats.json, `paletler` ← palettes.json, `varliklar` ← assets/*/index.json,
`tercihler` ← prefs.json, `saglayici_kimlikleri` ← credentials.env.
İki tablo Faz 2 / 1'in (docs/faz2-kuyruk-anahtarlar-depolama.md §1): `isler`
(üretim kuyruğu ve iş geçmişi — bugün istek içinde koşan sağlayıcı çağrısının
kaydı) ve `isciler` (işçi süreçlerinin kalp atışı). Kuyruk arka ucu Postgres'in
kendisi (`FOR UPDATE SKIP LOCKED`, K1), Redis değil; sorgular `services/kuyruk.py`de.
Bir tablo Faz 3 / 1'in (docs/faz3-kredi-defteri-filigran.md §1): `kredi_hareketleri`
(append-only kredi defteri; `kullanicilar.bakiye` onun ÖNBELLEĞİ) — tek yazarı
`services/defter.py`. Aynı göç (`0007_kredi`) ileriki görevlerin sütunlarını da
getirir: `kullanicilar.plan`, `isler.kredi_gercek`/`saglayici_meta`/
`saglayici_maliyet_usd`, `medya.filigranli` — hepsi NULL/öntanımlı, geriye uyumlu.
Üç tablo Faz 4 / 2'nin (docs/faz4-odeme-abonelik-kvkk.md §2, göç `0008_odeme` —
Faz 4'ün TEK göçü): `urunler` (Polar ürün AYNASI — fiyat ve Polar ürün id'si;
`planlar` tablosu YOK, K5), `siparisler` (Polar `order.paid` → bizdeki satır;
iş tablosu, `kullanici_id` taşır) ve `odeme_olaylari` (webhook teslimatlarının
günlüğü, `webhook_id` UNIQUE = teslimat idempotency'si, K4). Aynı göç iki
kovayı açar (K3): `kredi_hareketleri.kova` (`hibe`/`paket`) + `kullanicilar.
paket_bakiye` (ikinci ÖNBELLEK), `tur` kümesine `paket`; ve 3-6. görevlerin
sütunlarını getirir: `kullanicilar.polar_musteri_id`/`polar_abonelik_id`/
`plan_bitis` (3), `sartlar_kabul_at`/`sartlar_surumu` (6), `temizlendi_at` (5).

SÜTUN ADLARI — iki dil, tek kural. Bugünkü JSON kaydında da API gövdesinde
de var olan alanlar ADINI KORUR (`filename`, `prompt`, `folder_id`, `palette`,
`credits`, `theme`, `image_model` …): 5-6. görevde bir satırın JSON'a dökümü
sütun→anahtar eşlemesi olmadan çıkacak ve `tests/test_legacy_formats.py`nin
alan-kaybı bekçisi doğrudan sütun adlarını sayacak; her yeniden adlandırma
o eşlemede bir satır ve bir hata yeri demek. Yalnız DB'de yaşayan şeyler
Türkçe: tablo adları, `kullanici_id`, `olusturuldu`/`guncellendi`
(`created_at`/`updated_at`), ve belgenin açıkça adlandırdığı iki alan —
`sohbetler.mesajlar` (`messages`), `varliklar.tur` (`kind`). ASCII zorunlu:
`ı/ş/ğ` SQL'de tırnak ister ve her araçta sorun çıkarır (belgenin risk notu).

KİMLİK — iki uzay. Hesap tabloları `uuid` (`gen_random_uuid()`, PG 13+):
kullanıcıyı dışarıya taşıyan tek şey çerezdeki jeton, id'nin biçimi kimseye
görünmüyor. Beş liste tablosu (`medya`, `klasorler`, `sohbetler`, `paletler`,
`varliklar`) ise `id text` + `CHECK (id ~ '^[0-9a-f]{8,32}$')`: bu
`storage._SAFE_ID`nin SQL'i (bekçisi testte). Bugünkü kayıtlar
`uuid4().hex[:12]` taşıyor, `/output/{filename}` ve `/api/image/{id}` yolları
id'yi URL'de taşıyor ve ön yüz onu dize olarak biliyor — içe aktarılan eski
kayıt 12 hanesini korur, yeni satır 32 haneli tam `uuid4().hex` alır, ikisi
de aynı kapıdan geçer. `(kullanici_id, id)` bileşik anahtar DEĞİL, id küresel
benzersiz: sorgu zaten `WHERE id = :id AND kullanici_id = :ben` diyor ve
bileşik anahtar her FK'yi ikiye katlardı (gerekçenin tamamı belgede, "Kimlik
kararı").

SAHİPLİK — tek DB, satır düzeyi `kullanici_id`. Yedi iş tablosunun her
satırında `kullanici_id uuid NOT NULL REFERENCES kullanicilar ON DELETE
CASCADE`: hesap silinince verisi de gider, artık satır kalmaz. Liste
tablolarında `(kullanici_id, olusturuldu)` indeksi — `list_history`in ters
kronolojik listesi (storage.py) tam bu iki sütunla sıralanıyor. RLS BU FAZDA
YOK (belgenin sapma notu); şema ona hazır, politika Faz 2/3.

BAĞLAR — hangisi FK, hangisi değil, ölçüte göre:
* `klasorler.parent_id → klasorler.id ON DELETE CASCADE`: `folders.delete_tree`
  bugün alt ağacı elle siliyor; DB aynı şeyi kendisi yapar.
* `medya.folder_id → klasorler.id ON DELETE SET NULL`: `storage.unfile_folders`
  klasör silinince görselleri köke düşürüyor — SET NULL onun birebir SQL'i.
* `medya.parent_id`, `medya.session_id`, `medya.arena_id` FK DEĞİL, düz metin.
  Üçü de bugün SARKABİLİYOR: ebeveyn görsel silinince türev `parent_id`sini
  tutuyor (galeri "kaynağı silinmiş" diye gösteriyor), sohbet silinince
  üretilen görseller `session_id`siyle kalıyor, arena turunun bir sütunu
  silinince kardeşleri `arena_id`sini koruyor. FK bu üç davranışı ya
  yasaklar ya NULL'lar — ikisi de bugünkü anlamı değiştirir ve 8. görevin
  içe aktaracağı eski verinin bir kısmını reddederdi.

NULL'UN ANLAMI — `medya`nın 5 koşullu alanı (`imported`, `session_id`,
`arena_id`, `kind`, `duration`) NULL'lanabilir: history.json'da bu anahtarlar
ancak bir anlam taşıdıklarında yazılıyor (storage.py'nin "yokluğun tanımlı bir
anlamı var" disiplini); SQL'de o yokluk NULL'un kendisi. `model` ve `credits`
koşulsuz NOT NULL — storage.py'nin gerekçesi aynen: her üretilen kayıtta var
olan olgular, ledger'ın tek müşterisi. `tercihler`in 9 sütunu da NULL'lanabilir:
NULL = "hiç yazılmamış" (`prefs.read_stored`ın ayrımı), okuyan taraf
varsayılanı doldurur — `read()`/`read_stored()` çiftinin sütun düzeyi karşılığı.

ENUM'LAR CHECK İLE, Postgres `ENUM` tipiyle DEĞİL. `tercihler.theme`/`language`,
`kullanicilar.dil`, `varliklar.tur`, `jetonlar.amac` — hepsi `text` + `CHECK
(… IN (…))`. Değer kümeleri kodun sahip olduğu sabitlerden okunuyor
(`models.ALLOWED_THEMES`, `models.ALLOWED_LANGUAGES`, `assets_store.KINDS`) ki
Python'daki liste ile SQL'deki liste ayrışamasın; yeni bir değer geldiğinde
`CHECK` yeniden yazılır (tek `ALTER TABLE`, transaksiyon içinde) — `ALTER TYPE
… ADD VALUE` eski Postgres'lerde transaksiyon dışı istiyor ve tip düşürmesi
göç dosyasına elle `DROP TYPE` yazdırıyordu. `image_model`/`video_model`/
`chat_provider`/`chat_model` CHECK'SİZ ve bilerek: değer kümeleri katalog
(`catalog.image_model_ids()`), her model eklemesinde göç istemek yanlış yer.

ZAMAN — hepsi `timestamptz` (`DateTime(timezone=True)`), sunucu saatiyle
(`now()`): bugünkü `created_at` dizeleri `services/zaman.py`nin biçimindeydi
ve istemcinin saatinden bağımsızdı; sunucu varsayılanı aynı şeyi DB'de
söylüyor. `guncellendi` ORM `onupdate` ile — tetikleyici yok, yani ham SQL
`UPDATE` yazan bir yol bu sütunu kendi güncellemeli (depo modülleri ORM
kullanacak).

ADLANDIRMA KURALI (`MetaData(naming_convention=…)`): her kısıt öngörülebilir
bir ad alır (`pk_…`, `fk_<tablo>_<sütun>_<hedef>`, `uq_…`, `ck_<tablo>_<ad>`,
`ix_…`). Adsız kısıt Postgres'in ürettiği adı alır ve `alembic check` o adı
model tarafında bulamayınca her koşuda "fark var" der; `downgrade` da adsız
kısıtı düşüremez.
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import assets_store
import models

# `storage._SAFE_ID`nin (`[0-9a-f]{8,32}`, `fullmatch`) SQL karşılığı — ikisi
# ayrışmasın diye bekçisi var (tests/test_tablolar.py). `fullmatch` çapaları
# burada `^…$` ile açık.
ID_KALIBI = r"^[0-9a-f]{8,32}$"

# `jetonlar.amac`ın değer kümesi — e-posta doğrulama ve parola sıfırlama (3. görev).
JETON_AMACLARI: tuple[str, ...] = ("eposta_dogrulama", "parola_sifirlama")

# `giris_denemeleri.tur`un değer kümesi (3. görev, göç `0002_deneme_turu`).
# Üç sayaç aynı tabloda ama AYRI sayılır: başarısız giriş (e-posta 10 / IP 30,
# 15 dk), kayıt isteği ve sıfırlama isteği (IP 5, 1 sa). Tek sayaçta
# olsalardı parolasını beş kez yanlış yazan kullanıcı "parolamı unuttum"u da
# kilitli bulurdu — tam olarak ihtiyacı olan kapıyı.
DENEME_TURLERI: tuple[str, ...] = ("giris", "kayit", "sifirlama")

# `isler.tur` — dört üretim rotasının adı (`routers/uretim.py`: generate, edit,
# video, animate). İşçi (Faz 2 / 3) hangi sağlayıcı işlevini çağıracağını
# buradan seçer; sohbet BİLEREK yok — `/api/chat` saniyeler sürer, senkron kalır.
IS_TURLERI: tuple[str, ...] = ("generate", "edit", "video", "animate")

# `isler.durum` — ön yüzün ve admin'in okuduğu SÖZLEŞME, CHECK'te kilitli:
# sessizce eklenen bir durum ön yüzde "bilinmeyen" demek, o yüzden eklemek göç
# ister (belge §1, "Risk"). Geçişler: bekliyor → calisiyor → bitti | hata;
# bekliyor → iptal. `calisiyor` iptal EDİLMEZ (sağlayıcı çoktan faturalandı) ve
# `hata`dan geri kuyruğa dönüş YOK (K8: çift fatura riski).
IS_DURUMLARI: tuple[str, ...] = ("bekliyor", "calisiyor", "bitti", "hata", "iptal")
DURUM_BEKLIYOR, DURUM_CALISIYOR, DURUM_BITTI, DURUM_HATA, DURUM_IPTAL = IS_DURUMLARI

# `isler.anahtar_kaynagi` — iş HANGİ anahtarla koştu (Faz 2 / 6, göç `0005_kota`):
# kullanıcının kendi satırı ya da platformun ortam sırrı (`services/platform_anahtari.py`).
# Rota sıraya alırken yazar; günlük kredi tavanı YALNIZ `platform` satırlarını
# toplar (BYOK kendi parası). NULL = 6. görevden önceki satır (kaynağı bilinmiyor,
# sayılmaz). CHECK'te kilitli: üçüncü bir kaynak (ör. kurumsal havuz) göç ister.
ANAHTAR_KAYNAKLARI: tuple[str, ...] = ("kullanici", "platform")

# `kredi_hareketleri.tur` — defter satırının türü (Faz 3 / 1, göç `0007_kredi`;
# belge §1). `miktar` İMZALI: `rezerv` negatif (sıraya girerken tahmin düşer),
# `onay` pozitif ya da 0 (gerçek < tahmin farkı geri gelir; "onaylandı" izi
# fark 0 olsa da yazılır), `iade` pozitif (rezervin tamamı), `hibe` pozitif,
# `duzeltme` her iki yön (admin), `sona_erme` negatif (Faz 3'te CHECK'te vardı,
# yazan yoktu; Faz 4 / 2 `defter.dusur` plan düşürmede hibe kovasını yeni
# planın hibesine indirirken yazar), `paket` pozitif (Faz 4 / 2, göç `0008_odeme`:
# satın alınan kredi paketi, `defter.paket_yukle`, anahtar `paket:<polar_order_id>`
# — K4). Küme CHECK'te kilitli (Faz 1 / 2'nin `text + CHECK` kararı), sessiz yeni
# tür yok: `tur_kumesi` CHECK'i bu demetten kurulur, bekçisi tests/test_tablolar.py
# (her üye yazılır, dışı reddedilir) ve settings.js `KREDI_HAREKET_ANAHTARI`
# (her türün etiketi var — tests/test_kredi_route.py).
HAREKET_TURLERI: tuple[str, ...] = ("hibe", "rezerv", "onay", "iade", "duzeltme", "sona_erme", "paket")

# `kredi_hareketleri.kova` — satır hangi KOVAYI oynatır (Faz 4 / 2, K3): `hibe`
# aylık/dönem hibesi (devretmez, `kullanicilar.bakiye` önbelleği) ya da `paket`
# satın alınan kredi (devreder, `kullanicilar.paket_bakiye`). Öntanımlı `hibe`:
# göçten önceki her satır hibe kovasıydı (paket yoktu). İki kova TEK tabloda —
# FIFO satırları ya da Polar sayaçları değil (belge §2 gerekçesi); rezerv hibe
# kovasından ÖNCE düşer (devretmeyen önce — kullanıcı lehine), iade/onay farkı
# ÖNCE paket kovasına döner (`services/defter.py`).
KOVALAR: tuple[str, ...] = ("hibe", "paket")
KOVA_HIBE, KOVA_PAKET = KOVALAR

# `urunler.tur` — Polar ürünü ne satıyor (Faz 4 / 2, K2): aylık abonelik
# (`plan`; `urunler.plan` dolu, dönem hibesi devretmez) ya da tek seferlik kredi
# paketi (`paket`; `urunler.kredi` yüklenen sayı, devreder). `text + CHECK`:
# yıllık plan/hediye kredisi gelirse (belge "Faz 4 dışı") küme göçle genişler.
URUN_TURLERI: tuple[str, ...] = ("plan", "paket")

# `siparisler.sebep` — Polar `order.paid` olayının `billing_reason`ı AYNEN (Faz 4 / 2,
# K6 bunu okur): `purchase` tek seferlik paket, `subscription_create` ilk abonelik
# dönemi, `subscription_cycle` yenileme, `subscription_update` plan değişikliği.
# ÇEVİRİ YOK — sağlayıcı sözlüğü: Polar bir gün yeni sebep gönderirse webhook
# (3. görev) bilinmeyen sebebi `hata` ile kaydeder, küme göçle genişler.
# Literaller 2026-09-21'de Polar belgesinden DOĞRULANMADI (egress); 3. görev
# doğrular, farklıysa göçle düzelir (belge "Doğrulanmayanlar").
SIPARIS_SEBEPLERI: tuple[str, ...] = ("purchase", "subscription_create", "subscription_cycle", "subscription_update")

# `kullanicilar.plan` — üç plan, kodda katalog (Faz 3 / 3 `services/planlar.py`
# bu kümeye bağlanır; K5: DB tablosu Faz 4'te ödeme gelince). Öntanımlı `free`:
# göç mevcut kullanıcıları dokunmadan ücretsiz plana koyar.
PLANLAR_KUMESI: tuple[str, ...] = ("free", "temel", "pro")

# Dokuz iş tablosu — belgenin envanteriyle birebir; bekçi test bu kümenin her
# üyesinde `kullanici_id` + FK + indeks arar ve kümenin belgeyle eşit olduğunu
# sınar. Hesap tabloları burada DEĞİL: onlarda sahiplik sütunu ya yok
# (`kullanicilar`, `giris_denemeleri`) ya da anlamı başka (`oturumlar`).
# `isciler` de DEĞİL (Faz 2 / 1): işçi süreci bir kullanıcının değil
# platformun — satırında `kullanici_id` yok, kiracı süzgeci anlamsız.
# `kredi_hareketleri` (Faz 3 / 1) İÇİNDE: `kullanici_id` taşıyor, iş tablosu —
# ama `kullanicilar.bakiye` önbelleği hesap tablosunda, politikasız (belge §1 "Risk").
# `siparisler` (Faz 4 / 2) İÇİNDE: kullanıcının kendi siparişleri ("Kredi"
# bölmesi). `urunler` ve `odeme_olaylari` DEĞİL: ikisi de platformun —
# `urunler`de kullanıcı sütunu yok (herkese açık fiyat listesi), `odeme_olaylari`
# NULL'lanabilir `kullanici_id` taşır (olay gelir, kullanıcı çözülemeyebilir —
# sahibi olmayan satır) ve yalnız admin okur; kiracı süzgeci ikisinde de anlamsız.
IS_TABLOLARI: tuple[str, ...] = (
    "medya", "klasorler", "sohbetler", "paletler", "varliklar",
    "tercihler", "saglayici_kimlikleri", "isler", "kredi_hareketleri", "siparisler",
)

ADLANDIRMA = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _sql_kumesi(degerler: tuple[str, ...]) -> str:
    """`('a', 'b')` — CHECK için değer listesi. Değerler kodun sabitleri, kullanıcı girdisi değil."""
    return "(" + ", ".join("'" + d.replace("'", "''") + "'" for d in degerler) + ")"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=ADLANDIRMA)


# Sık kullanılan sütun kalıpları — her tabloda aynı cümleyi yazmamak için.
# İşlev, sabit DEĞİL: `mapped_column` nesnesi tabloya bağlanıyor, paylaşılamaz.

def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(pg.UUID(as_uuid=True), primary_key=True,
                         server_default=text("gen_random_uuid()"))


def _kullanici_fk(*, primary_key: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(pg.UUID(as_uuid=True),
                         ForeignKey("kullanicilar.id", ondelete="CASCADE"),
                         primary_key=primary_key, nullable=False)


def _liste_id() -> Mapped[str]:
    """Liste tablolarının `id text` anahtarı — CHECK tabloda (`__table_args__`), adı tabloya göre."""
    return mapped_column(Text, primary_key=True)


def _olusturuldu() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


def _guncellendi() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False,
                         server_default=text("now()"), onupdate=text("now()"))


def _id_kisiti() -> CheckConstraint:
    """`_SAFE_ID`nin CHECK'i; adı kurala göre `ck_<tablo>_id_bicimi` olur."""
    return CheckConstraint(f"id ~ '{ID_KALIBI}'", name="id_bicimi")


def _sahip_indeksi(tablo: str) -> Index:
    """`(kullanici_id, olusturuldu)` — ters kronolojik liste sorgusunun indeksi."""
    return Index(f"ix_{tablo}_kullanici_olusturuldu", "kullanici_id", "olusturuldu")


# ───────────────────────────────────────────────────────────── hesap

class Kullanici(Base):
    """Hesap. `eposta` citext: `Ali@x.com` ile `ali@x.com` aynı hesap, UNIQUE bunu DB'de tutar.

    `parola_ozeti` NULL olabilir — Google ile açılan hesabın parolası yok (3b).
    `dil` NULL = kullanıcı hiç seçmedi, zincir tarayıcı başlığına düşer
    (services/dil.py); dolu değer `i18n.LANGUAGES`ten. `silindi_at` yer
    tutucu (Faz 4 hesap silme akışı) — bugün hiçbir sorgu okumuyor.
    """
    __tablename__ = "kullanicilar"
    __table_args__ = (
        CheckConstraint("dil IN " + _sql_kumesi(models.ALLOWED_LANGUAGES), name="dil_kumesi"),
        CheckConstraint("plan IN " + _sql_kumesi(PLANLAR_KUMESI), name="plan_kumesi"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    eposta: Mapped[str] = mapped_column(pg.CITEXT, nullable=False, unique=True)
    parola_ozeti: Mapped[str | None] = mapped_column(Text)
    dogrulandi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    dil: Mapped[str | None] = mapped_column(Text)
    # Günlük kredi tavanı EZMESİ (Faz 2 / 6, göç `0005_kota`): NULL = ortamın
    # öntanımlısı (`KROMIS_GUNLUK_KREDI_TAVANI`, services/kota.py); dolu değer bu
    # kullanıcıya özel tavan — admin 8. görevde yazar, bugün yalnız okunur.
    gunluk_kredi_tavani: Mapped[int | None] = mapped_column(Integer)
    # KREDİ BAKİYESİ — ÖNBELLEK (Faz 3 / 1, göç `0007_kredi`, K1): kaynak gerçek
    # `SUM(kredi_hareketleri.miktar)`. Tek yazarı `services/defter.py` (AST bekçisi
    # tests/test_defter.py: başka modül `kullanicilar.bakiye`ye UPDATE kuramaz);
    # düşüm atomik `UPDATE … SET bakiye = bakiye - :m WHERE bakiye >= :m`, yarış
    # Postgres'in satır kilidinde. Hesap tablosunda ve politikasız: işçi admin
    # bağlamında (bayat iade, aylık hibe) ve rota kullanıcı bağlamında yazar,
    # ikisine de RLS engel olmasın. `defter.tutarlilik` SUM ile karşılaştırır,
    # sapma günlüğe düşer (sessiz yanılma yok). Eksiye yalnız admin `duzelt` ile iner.
    bakiye: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # PAKET KOVASI — İKİNCİ ÖNBELLEK (Faz 4 / 2, göç `0008_odeme`, K3): kaynak
    # gerçek `SUM(miktar) WHERE kova = 'paket'`. Satın alınan kredi devreder;
    # `bakiye` (hibe kovası) devretmez. Rezerv ikisinden TEK atomik UPDATE'le
    # düşer (hibe önce, `LEAST`), yazarı yine yalnız `services/defter.py` (AST
    # bekçisi `paket_bakiye`yi de tarar). `defter.tutarlilik` iki SUM'la ikisini
    # de ölçer. Eksiye yalnız admin `duzelt(kova='paket')` ile iner.
    paket_bakiye: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Plan (`PLANLAR_KUMESI`, CHECK'te): 3. görev okur (`model_available(plan)`,
    # aylık hibe miktarı, filigran kararı); Faz 3'te yalnız `free` yazılıyordu
    # (öntanımlı), Faz 4 / 3 webhook (`subscription.*`) ücretli planı yazar.
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'free'"))
    # POLAR (Faz 4 / 2 göçü; 3-4. görev yazar): `polar_musteri_id` Polar'daki
    # müşteri kaydı (UNIQUE, `customer.created/updated`; portal bağlantısı ve
    # mutabakat bununla), `polar_abonelik_id` aktif abonelik, `plan_bitis` İPTAL
    # EDİLMİŞ aboneliğin dönem sonu — plan o güne kadar kalır, "dönem sonunda
    # free" (K6); NULL = iptal yok. Üçü de NULL = hiç satın almamış kullanıcı.
    polar_musteri_id: Mapped[str | None] = mapped_column(Text, unique=True)
    polar_abonelik_id: Mapped[str | None] = mapped_column(Text)
    plan_bitis: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # RIZA (Faz 4 / 2 göçü; 6. görev yazar, K11): kullanım şartlarını ne zaman ve
    # HANGİ SÜRÜMÜNÜ onayladı (`HUKUK_SURUMU` kod sabiti; metin değişince sürüm
    # değişir, yeni onay istenir — tıkla-onay kanıtı). NULL = henüz onaylamadı
    # (eski kullanıcı ilk satın almada onaylar, 4. görevin 412'si).
    sartlar_kabul_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    sartlar_surumu: Mapped[str | None] = mapped_column(Text)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    guncellendi: Mapped[dt.datetime] = _guncellendi()
    # HESAP SİLME (Faz 4 / 5 yazar, K9): `silindi_at` TALEP anı (anonimleştir +
    # kilitle hemen), `temizlendi_at` içeriğin bakım turunda silindiği an (talep
    # + 7 gün; `KROMIS_HESAP_SILME_BEKLEME_GUN`). Satır KALIR: `kredi_hareketleri`
    # ve `siparisler` anonim sahiple durur (mali kayıt). Faz 1'den beri yer tutucu
    # olan `silindi_at`ı bugün `hesap.py`/`depo_admin.py` yalnız `IS NULL` süzer.
    silindi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    temizlendi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Oturum(Base):
    """Sunucu tarafı oturum (K3): ham jeton yalnız çerezde, burada SHA-256 özeti.

    `jeton_ozeti` UNIQUE: giriş bu sütundan tek satır bulur. `son_gorulme`
    5 dk çözünürlükle güncellenir (3. görev), `bitis` kayan ömrün sonu.
    """
    __tablename__ = "oturumlar"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    jeton_ozeti: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    son_gorulme: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    server_default=text("now()"))
    bitis: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip: Mapped[str | None] = mapped_column(pg.INET)
    istemci: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Kullanıcının oturumlarını düşürmek (çıkış, parola değişikliği, admin)
        # tek `DELETE … WHERE kullanici_id` — indeks onun için.
        Index("ix_oturumlar_kullanici", "kullanici_id"),
    )


class Jeton(Base):
    """E-posta doğrulama / parola sıfırlama jetonu — DB'de durur ki iptal edilebilsin.

    `ozet` UNIQUE (ham jeton e-postada), `kullanildi_at` tek kullanımın
    kaydı, `bitis` süre sınırı. `itsdangerous` imzalı jeton bu yüzden
    GEREKMİYOR (belge, 2. görev).
    """
    __tablename__ = "jetonlar"
    __table_args__ = (
        CheckConstraint("amac IN " + _sql_kumesi(JETON_AMACLARI), name="amac_kumesi"),
        Index("ix_jetonlar_kullanici", "kullanici_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    amac: Mapped[str] = mapped_column(Text, nullable=False)
    ozet: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    bitis: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kullanildi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class GirisDenemesi(Base):
    """Başarısız giriş denemesi — 3. görevin hız sınırı Redis'siz buradan sayar.

    `kullanici_id` YOK ve bilerek: var olmayan bir e-postaya yapılan
    denemeler de sayılmalı (numaralandırmaya karşı cevaplar ayırt etmiyor,
    sayaç da ayırt etmez). `eposta` citext: `kullanicilar.eposta` ile aynı
    eşitlik kuralı. İki indeks iki sayaç: e-posta başına ve IP başına, ikisi
    de "son 15 dk" penceresinde — `zaman` ikinci sütun.

    `tur` (3. görev): `giris` / `kayit` / `sifirlama` — üç ayrı sayaç, tek
    tablo (gerekçesi `DENEME_TURLERI`nin üstünde). Öntanımlı `giris`: sütun
    0001'deki satırların üstüne göçle geldi ve o satırların hepsi başarısız
    girişti (başka yazan yoktu).
    """
    __tablename__ = "giris_denemeleri"
    __table_args__ = (
        CheckConstraint("tur IN " + _sql_kumesi(DENEME_TURLERI), name="tur_kumesi"),
        Index("ix_giris_denemeleri_eposta_zaman", "eposta", "zaman"),
        Index("ix_giris_denemeleri_ip_zaman", "ip", "zaman"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tur: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'giris'"))
    eposta: Mapped[str] = mapped_column(pg.CITEXT, nullable=False)
    ip: Mapped[str | None] = mapped_column(pg.INET)
    zaman: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                              server_default=text("now()"))


# ─────────────────────────────────────────────────────────────── iş

class Klasor(Base):
    """← folders.json (`folders.create`): `id`, `name`, `parent_id`, `created_at`.

    Derinlik sınırı (5, `folders.depth`) DB'de DEĞİL uygulamada kalır —
    özyinelemeli bir CHECK yok ve sınır bir ürün kararı, bütünlük kuralı değil.
    """
    __tablename__ = "klasorler"
    __table_args__ = (
        _id_kisiti(),
        _sahip_indeksi("klasorler"),
        Index("ix_klasorler_parent", "parent_id"),
    )

    id: Mapped[str] = _liste_id()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("klasorler.id", ondelete="CASCADE"))
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


class Medya(Base):
    """← history.json (`storage.save`): 12 koşulsuz + 5 koşullu alan (gerekçe modül başında).

    `filename` UNIQUE: `/output/{filename}` yolu yalnız dosya adı taşıyor ve
    ad `id + uzantı`dan türetiliyor — benzersizlik zaten olgu, indeks o yolun
    sorgusu için. `duration` saniye, tam sayı (`int(meta["duration"])`).
    """
    __tablename__ = "medya"
    __table_args__ = (
        _id_kisiti(),
        _sahip_indeksi("medya"),
        Index("ix_medya_kullanici_folder", "kullanici_id", "folder_id"),
    )

    id: Mapped[str] = _liste_id()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    filename: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("klasorler.id", ondelete="SET NULL"))
    palette: Mapped[dict[str, object] | None] = mapped_column(pg.JSONB)
    prompt_sent: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    imported: Mapped[bool | None] = mapped_column(Boolean)
    session_id: Mapped[str | None] = mapped_column(Text)
    arena_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[int | None] = mapped_column(Integer)
    # ARENA KAZANANI (Faz 1 / 5, göç `0003_arena_win`): envanterin 17 alanı
    # `storage.save`in yazdıklarıydı; bu alanı `storage.set_arena_winner` SONRADAN
    # yazıyor (`{**r, "arena_win": True}`) ve envanter onu görmedi. Koşullu
    # alanların disiplini aynen: NULL/false = "işaret yok", JSON'a dökülmez;
    # `True` = turun kazananı. Tur başına tek kazanan uygulamada
    # (`depo_medya.arena_kazanani` tek UPDATE'te kardeşleri NULL'lar), kısıtta
    # değil — kısmi UNIQUE `(arena_id) WHERE arena_win` içe aktarılan eski
    # verideki olası çift işareti reddedip 8. görevin aracını durdururdu.
    arena_win: Mapped[bool | None] = mapped_column(Boolean)
    # FİLİGRAN (Faz 3 / 1 göçü, 4. görev yazar): ücretsiz planın görseli işçide
    # `_uret` → `_yaz` arasında filigranlanır ve satır bunu bilir (K7: tek nesne,
    # ham kopya yok). NOT NULL DEFAULT false: göçten önceki her kayıt filigransız,
    # bu bir olgu — koşullu alanların NULL disiplini burada geçerli değil.
    # `_json`a yalnız `true` iken dökülür (4. görev: `arena_win`in koşullu deseni;
    # galeri kartı rozeti kayıttan okur, ayrı bir uç yok).
    filigranli: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


class Sohbet(Base):
    """← chats.json (`chat_store.create`): `title`, `messages` → `mesajlar` JSONB.

    `mesajlar` iki biçimde öğe taşıyor (`{role, content}` ve `{role:"result",
    image_ids, params}`); doğrulama `models.ChatMessage`ta, DB için opak bir
    dizi. `cover` türetilir, sütun DEĞİL (chat_store `_with_cover`).
    `list_chats` `updated_at DESC` sıralıyor — indeks `guncellendi`de.
    """
    __tablename__ = "sohbetler"
    __table_args__ = (
        _id_kisiti(),
        _sahip_indeksi("sohbetler"),
        Index("ix_sohbetler_kullanici_guncellendi", "kullanici_id", "guncellendi"),
    )

    id: Mapped[str] = _liste_id()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    mesajlar: Mapped[list[dict[str, object]]] = mapped_column(pg.JSONB, nullable=False)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    guncellendi: Mapped[dt.datetime] = _guncellendi()


class Palet(Base):
    """← palettes.json (`palette_store.create`): `colors` dondurulmuş liste, JSONB.

    Tarif değişse geçmiş yeniden yazılmaz (palette_store'un disiplini) —
    renkler hesaplanmaz, saklanır.
    """
    __tablename__ = "paletler"
    __table_args__ = (_id_kisiti(), _sahip_indeksi("paletler"))

    id: Mapped[str] = _liste_id()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    seed: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[str] = mapped_column(Text, nullable=False)
    colors: Mapped[list[dict[str, object]]] = mapped_column(pg.JSONB, nullable=False)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


class Varlik(Base):
    """← assets/{logos,banners,mottos}/index.json (`assets_store.save_asset`); üç manifest tek tablo.

    `tur` (`kind`) `assets_store.KINDS`ten CHECK'li; dosya yerleşimi
    `assets_dir/<tur>/<filename>` aynı kalıyor (6. görev).
    """
    __tablename__ = "varliklar"
    __table_args__ = (
        _id_kisiti(),
        _sahip_indeksi("varliklar"),
        CheckConstraint("tur IN " + _sql_kumesi(assets_store.KINDS), name="tur_kumesi"),
        Index("ix_varliklar_kullanici_tur", "kullanici_id", "tur"),
    )

    id: Mapped[str] = _liste_id()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tur: Mapped[str] = mapped_column(Text, nullable=False)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


class Tercih(Base):
    """← prefs.json (NESNE): kullanıcı başına TEK satır, `kullanici_id` birincil anahtar.

    Ayrı bir `id` yok: "kullanıcının tercihi" sorgusu zaten `kullanici_id`
    ile geliyor ve iki satır olamaz — PK bunu DB'de söylüyor. 9 tipli sütun
    `prefs._SCHEMA` ile aynı adlar; hepsi NULL'lanabilir (NULL = hiç
    yazılmamış). `theme`/`language` CHECK'li (`prefs._ENUMS`in SQL'i),
    model/sağlayıcı sütunları CHECK'siz (gerekçe modül başında).
    """
    __tablename__ = "tercihler"
    __table_args__ = (
        CheckConstraint("theme IN " + _sql_kumesi(models.ALLOWED_THEMES), name="theme_kumesi"),
        CheckConstraint("language IN " + _sql_kumesi(models.ALLOWED_LANGUAGES),
                        name="language_kumesi"),
    )

    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk(primary_key=True)
    autosave_sessions: Mapped[bool | None] = mapped_column(Boolean)
    theme: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    guncelleme_kontrolu: Mapped[bool | None] = mapped_column(Boolean)
    image_model: Mapped[str | None] = mapped_column(Text)
    video_model: Mapped[str | None] = mapped_column(Text)
    chat_provider: Mapped[str | None] = mapped_column(Text)
    chat_model: Mapped[str | None] = mapped_column(Text)
    director_guidance: Mapped[str | None] = mapped_column(Text)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    guncellendi: Mapped[dt.datetime] = _guncellendi()


class SaglayiciKimligi(Base):
    """← credentials.env: kullanıcı başına, sağlayıcı anahtarı ŞİFRELİ (7. görev, Fernet).

    Birincil anahtar `(kullanici_id, ad)`: `ad` bugünkü env adı
    (`AZURE_IMAGE_API_KEY` …, `catalog.CREDENTIALS`), bir kullanıcının aynı
    addan iki değeri olamaz. `sifreli_deger bytea` — Fernet jetonu bayt;
    `anahtar_surumu` `MultiFernet` döndürmesinin hangi anahtarla şifrelendiğini
    söyler. Düz metin sütunu YOK ve olmayacak (7. görevin `pg_dump` bekçisi).
    """
    __tablename__ = "saglayici_kimlikleri"

    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk(primary_key=True)
    ad: Mapped[str] = mapped_column(Text, primary_key=True)
    sifreli_deger: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    anahtar_surumu: Mapped[int] = mapped_column(Integer, nullable=False)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    guncellendi: Mapped[dt.datetime] = _guncellendi()


# ─────────────────────────────────────────────────────────── kuyruk

class Is(Base):
    """Üretim işi — kuyruk satırı VE iş geçmişi tek tabloda (Faz 2 / 1, K1).

    Bugün `routers/uretim.py` sağlayıcı çağrısını isteğin içinde koşturuyor;
    4. görevde rota bu satırı yazıp 202 dönecek, işçi (3) `services/kuyruk.al`
    ile alacak. Kuyruk okuması `durum='bekliyor'` satırlarını `olusturuldu`
    sırasıyla tarar — kısmi indeks `ix_isler_kuyruk` tam bunun için, bitmiş
    binlerce satırı hiç görmez. `ix_isler_kullanici_aktif` (kısmi, bekliyor +
    calisiyor) 4. görevin "kullanıcı başına eş zamanlı iş" sayacı.

    `istek` doğrulanmış istek gövdesi (`GenerateRequest.model_dump()` ya da
    multipart alanları + girdi nesnelerinin anahtarları) — DIŞARIYA DÖKÜLMEZ
    (`kuyruk._json`): prompt ve klasör zaten `medya`da. `sonuc` `{"medya":
    [id, …]}` — kayıtların kendisi değil, satırlar `medya`da. `hata`
    `errlog.redact_secrets`ten geçmiş metin. `model` ve `kredi_tahmini`
    (`catalog.cost_for` × n, sıraya girerken) 6. görevin günlük tavanının ve
    Faz 3 defterinin okuduğu iki alan — TAHMİN, gerçek maliyet Faz 3'ün işi.
    `anahtar_kaynagi` (Faz 2 / 6) o tavanın süzgeci: yalnız `platform` toplanır.

    `isci_id` FK DEĞİL ve bilerek: işçi kapanışta kendi `isciler` satırını
    siler; biten işin "kim koştu" kaydı işçi gidince de durmalı (SET NULL onu
    silerdi, CASCADE işi). Zaman damgaları Python'dan (`zaman.an()`, Faz 1 / 5
    kararı: mikrosaniye, sıralama); `server_default` yalnız ham SQL yazan bir
    yol için emniyet.
    """
    __tablename__ = "isler"
    __table_args__ = (
        CheckConstraint("tur IN " + _sql_kumesi(IS_TURLERI), name="tur_kumesi"),
        CheckConstraint("durum IN " + _sql_kumesi(IS_DURUMLARI), name="durum_kumesi"),
        CheckConstraint("anahtar_kaynagi IN " + _sql_kumesi(ANAHTAR_KAYNAKLARI),
                        name="anahtar_kaynagi_kumesi"),
        _sahip_indeksi("isler"),
        Index("ix_isler_kuyruk", "durum", "olusturuldu",
              postgresql_where=text("durum = 'bekliyor'")),
        Index("ix_isler_kullanici_aktif", "kullanici_id", "olusturuldu",
              postgresql_where=text("durum IN ('bekliyor', 'calisiyor')")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    tur: Mapped[str] = mapped_column(Text, nullable=False)
    durum: Mapped[str] = mapped_column(Text, nullable=False,
                                       server_default=text("'bekliyor'"))
    istek: Mapped[dict[str, object]] = mapped_column(pg.JSONB, nullable=False)
    sonuc: Mapped[dict[str, object] | None] = mapped_column(pg.JSONB)
    hata: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    kredi_tahmini: Mapped[int] = mapped_column(Integer, nullable=False)
    # Hangi anahtarla koşacak/koştu (`ANAHTAR_KAYNAKLARI`); NULL yalnız eski satırlarda.
    anahtar_kaynagi: Mapped[str | None] = mapped_column(Text)
    # FAZ 3 (göç `0007_kredi`, üçü de NULL = henüz yazılmadı / göç öncesi satır):
    # `kredi_gercek` işin GERÇEK kredisi (Σ `medya.credits`; 2. görev `bitir`le
    # aynı commit'te yazar, `defter.onayla` farkı iade eder) — `kredi_tahmini` üst
    # sınır, bu gerçek; ikisinin farkı 5. görevin marj raporu. `saglayici_meta`
    # sağlayıcının yanıtından ContextVar yan kanalıyla (K8) toplanan ham alanlar
    # (`usage`, `request_id` …), `saglayici_maliyet_usd` ondan türetilen USD
    # (`numeric(10,6)`: 0,000001 USD çözünürlük — görsel başına milyonda bir
    # dolar mertebesindeki fiyatlar tam sayı kalsın, float yuvarlaması olmasın).
    kredi_gercek: Mapped[int | None] = mapped_column(Integer)
    saglayici_meta: Mapped[dict[str, object] | None] = mapped_column(pg.JSONB)
    saglayici_maliyet_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    isci_id: Mapped[uuid.UUID | None] = mapped_column(pg.UUID(as_uuid=True))
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    basladi: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    bitti: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    kalp_atisi: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Isci(Base):
    """İşçi süreci — açılışta satır yazar, 30 sn'de bir `son_kalp` günceller, kapanışta siler.

    Kullanıcı sütunu YOK: işçi platformun, kiracının değil (`IS_TABLOLARI`
    dışında). `/health`in `worker_alive`ı (Faz 2 / 9) ve admin sayfası (8)
    buradan okur; `es_zamanli` işçinin aynı anda kaç iş aldığı (4'ün
    varsayımı, sağlayıcı gecikmesiyle ölçülür). `surum` `version.APP_VERSION`:
    dağıtım sırasında eski ve yeni sürüm yan yana koşar, admin hangisinin
    kaldığını görür.
    """
    __tablename__ = "isciler"

    id: Mapped[uuid.UUID] = _uuid_pk()
    konak: Mapped[str] = mapped_column(Text, nullable=False)
    surum: Mapped[str] = mapped_column(Text, nullable=False)
    basladi: Mapped[dt.datetime] = _olusturuldu()
    son_kalp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  server_default=text("now()"))
    es_zamanli: Mapped[int] = mapped_column(Integer, nullable=False)


# ─────────────────────────────────────────────────────────── defter (Faz 3 / 1)

class KrediHareketi(Base):
    """Kredi defterinin bir satırı — APPEND-ONLY, `kullanicilar.bakiye` bunun toplamının önbelleği (K1).

    Tek tablo, çift kayıt DEĞİL: tek hesap türü var (kullanıcının kredisi),
    karşı ayak "platform" her satırda aynı bilgiyi taşırdı; Faz 4'ün ödeme
    mutabakatı gelince karşı hesap sütunu eklenir, satırlar kalır (belge §1
    "Defter biçimi"). Yazarı yalnız `services/defter.py` (rota ve işçi `db.add`
    YAPMAZ — AST bekçisi tests/test_defter.py).

    `is_id` FK `isler` **SET NULL**: saklama süresi dolan iş silinir
    (`kuyruk.eskileri_sil`, Faz 2 / 10), para izi işten uzun yaşar. `kullanici_id`
    CASCADE: hesap silinirse defteri de gider (KVKK Faz 4'te yeniden bakar).
    `admin_id` yalnız `duzeltme` satırında (kim düzeltti), SET NULL — admin
    hesabı silinse iz kalır. `idempotency_anahtari` UNIQUE: aynı işin rezervi/
    onayı/iadesi ikinci kez YAZILAMAZ (`INSERT … ON CONFLICT DO NOTHING`);
    biçimler `rezerv:<is_id>`, `onay:<is_id>`, `iade:<is_id>`, `hibe:<u>:<YYYY-MM>`,
    `duzeltme:<uuid4>`; Faz 4 / 2 ekledi: `paket:<polar_order_id>` (K4 — sipariş
    kimliği, olay id'si değil), `rezerv|onay|iade:<is_id>:paket` (aynı işin paket
    kovasındaki ikinci satırı), `sona_erme:<u>:<abonelik_id>:<YYYY-MM-DD>`,
    `hibe:<u>:polar:<order_id>` (ücretli dönem hibesi, 3. görev).

    `kova` (Faz 4 / 2, `KOVALAR`): satır hangi önbelleği oynatır — `hibe` →
    `kullanicilar.bakiye`, `paket` → `kullanicilar.paket_bakiye`. NOT NULL
    DEFAULT 'hibe': göçten önceki her satır hibe kovasıydı. Bir iş en çok İKİ
    `rezerv` satırı yazar (hibe yetmezse kalan paketten), çoğu işte bir.

    İki indeks iki soru: `(kullanici_id, olusturuldu)` hareket listesi (`medya`nın
    deseni), `(is_id)` "bu işin rezervi var mı" (`defter.onayla`/`iade`).
    RLS: `IS_TABLOLARI`da, üç politika + yalnız bu tabloda `yonetici_ekler`
    INSERT (K4: admin düzeltmesi ve işçinin admin bağlamlı bakım turu yazar);
    DELETE kimseye yok.
    """
    __tablename__ = "kredi_hareketleri"
    __table_args__ = (
        CheckConstraint("tur IN " + _sql_kumesi(HAREKET_TURLERI), name="tur_kumesi"),
        CheckConstraint("kova IN " + _sql_kumesi(KOVALAR), name="kova_kumesi"),
        _sahip_indeksi("kredi_hareketleri"),
        Index("ix_kredi_hareketleri_is", "is_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    is_id: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True), ForeignKey("isler.id", ondelete="SET NULL"))
    tur: Mapped[str] = mapped_column(Text, nullable=False)
    kova: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'hibe'"))
    miktar: Mapped[int] = mapped_column(Integer, nullable=False)
    aciklama: Mapped[str | None] = mapped_column(Text)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True), ForeignKey("kullanicilar.id", ondelete="SET NULL"))
    idempotency_anahtari: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


# ─────────────────────────────────────────────────────── ödeme (Faz 4 / 2)

class Urun(Base):
    """Polar ürününün AYNASI — fiyat listesinin ve webhook'un `product_id` → kredi/plan eşlemesinin tek satırı (K5).

    Fiyatın gerçek sahibi Polar (MoR onu tahsil eder); bizde KOPYA değil ayna:
    yazarı `tools/polar_esitle.py` (4. görev — Polar `products.list` → upsert
    `polar_urun_id`), okuyanı webhook (`order.paid` `product_id` → bu satır →
    `kredi`/`plan`) ve satış sayfası. `planlar` tablosu YOK (Faz 3 K5'ten sapma,
    belge K5): plan KURALLARI `services/planlar.py`de kalır, burada yalnız plan
    ürününün Polar id'si, fiyatı ve dönem hibesi (bilgi; kural `PLANLAR`da).

    `tur` `plan`/`paket` (`URUN_TURLERI`); `plan` yalnız `tur = 'plan'` iken dolu
    ve `PLANLAR_KUMESI`nden (CHECK `tur_plan_uyumu`: paket ürünü plan taşımaz,
    plan ürünü plansız olmaz). `kredi` paket için yüklenen sayı, plan için dönem
    hibesi. `fiyat_kurus` + `para_birimi` (`usd`): kuruş/cent tam sayı, float yok.
    `aktif` false = Polar'da arşivlenmiş (satışta değil, eski siparişler FK'yle
    ona bakar — satır silinmez). `guncellendi` aynanın tazeliği (4. görev: 7
    günden eskiyse admin uyarısı).

    ALTYAPI tablosu: kullanıcı sütunu yok, RLS yok — herkese açık fiyat listesi;
    yazımı yalnız araç ve admin bağlamı (`IS_TABLOLARI` dışında, bekçisi
    tests/test_tablolar.py `ALTYAPI_TABLOLARI`).
    """
    __tablename__ = "urunler"
    __table_args__ = (
        CheckConstraint("tur IN " + _sql_kumesi(URUN_TURLERI), name="tur_kumesi"),
        CheckConstraint("plan IN " + _sql_kumesi(PLANLAR_KUMESI), name="plan_kumesi"),
        CheckConstraint("(tur = 'plan') = (plan IS NOT NULL)", name="tur_plan_uyumu"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    polar_urun_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tur: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text)
    kredi: Mapped[int] = mapped_column(Integer, nullable=False)
    fiyat_kurus: Mapped[int] = mapped_column(Integer, nullable=False)
    para_birimi: Mapped[str] = mapped_column(Text, nullable=False)
    ad: Mapped[str] = mapped_column(Text, nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    guncellendi: Mapped[dt.datetime] = _guncellendi()


class Siparis(Base):
    """Polar'ın ödenmiş siparişi — bizdeki satır; kullanıcı "Kredi" bölmesinde görür, faturaya Polar'dan gider (K7).

    Yazarı webhook (`order.paid`, 3. görev) ADMİN bağlamında (`yonetici_ekler`
    — `YONETICI_EKLER_TABLOLARI`nın ikinci üyesi: webhook oturumsuz, hedef
    kullanıcı olaydan çözülür). `polar_siparis_id` UNIQUE — K4'ün ÜÇÜNCÜ
    kilidi (teslimat: `odeme_olaylari.webhook_id`; iş: defter anahtarı
    `paket:<order_id>`; sipariş satırı: burası): aynı siparişi anlatan iki olay
    ikinci satır yazamaz. `sebep` Polar `billing_reason` aynen (`SIPARIS_SEBEPLERI`).
    `urun_id` → `urunler` (NOT NULL: ürünü aynada olmayan sipariş İŞLENMEZ,
    `hata='urun_yok'` ile olay günlüğünde kalır — sahip `polar_esitle` koşar);
    ürün satırı silinmez (`aktif=false`), FK NO ACTION bunu DB'de de söyler.
    `tutar_kurus`/`para_birimi` Polar'ın tahsil ettiği (bilgi; vergi ve fatura
    Polar'da). `kullanici_id` CASCADE ama hesap silinince satır SİLİNMEZ (K9):
    kullanıcı satırı anonimleşir, CASCADE hiç tetiklenmez — mali kayıt kalır.

    İŞ tablosu (`IS_TABLOLARI` 10.): `sahip` ALL + `yonetici_okur` +
    `yonetici_gunceller` + `yonetici_ekler` (göç `0008_odeme`); DELETE kimseye yok.
    """
    __tablename__ = "siparisler"
    __table_args__ = (
        CheckConstraint("sebep IN " + _sql_kumesi(SIPARIS_SEBEPLERI), name="sebep_kumesi"),
        _sahip_indeksi("siparisler"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    kullanici_id: Mapped[uuid.UUID] = _kullanici_fk()
    polar_siparis_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    polar_abonelik_id: Mapped[str | None] = mapped_column(Text)
    urun_id: Mapped[uuid.UUID] = mapped_column(pg.UUID(as_uuid=True), ForeignKey("urunler.id"), nullable=False)
    sebep: Mapped[str] = mapped_column(Text, nullable=False)
    tutar_kurus: Mapped[int] = mapped_column(Integer, nullable=False)
    para_birimi: Mapped[str] = mapped_column(Text, nullable=False)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()


class OdemeOlayi(Base):
    """Bir webhook TESLİMATININ günlüğü — `webhook_id` UNIQUE, yinelenen teslimat kapıda döner (K4, teslimat katmanı).

    Standard Webhooks `webhook-id` başlığı yeniden gönderimde AYNI kalır: rota
    (3. görev) `INSERT … ON CONFLICT (webhook_id) DO NOTHING` ile satırı yazar,
    yazılamadıysa "çoktan alındı" → 200, işleme yok. Kayıt ve işleme AYNI
    transaksiyonda: işleme düşerse satır da geri alınır, Polar yeniden dener,
    temiz gelir (belge §3 "DİKKAT"). `tur` olay adı (`order.paid` …), `polar_nesne_id`
    olayın nesnesi (sipariş/abonelik id'si), `kullanici_id` çözülen kullanıcı —
    NULL'lanabilir (çözülemedi → `hata='kullanici_yok'`) ve SET NULL (hesap
    silinince olay kalır, sahibi düşer — K10: 1 yıl saklanır, bakım turu siler).
    `govde` REDAKTE edilmiş yük (kart verisi zaten gelmez; e-posta/adres
    gelebilir — `kuyruk._redakte` deseni; silme turu `[SILINDI]` yazar).
    `islendi_at` dolu = işlendi; `hata` dolu = neden işlenmedi (admin listesi).

    ALTYAPI tablosu: sahibi olmayan satır olabilir, yalnız admin okur; RLS yok
    (`IS_TABLOLARI` dışında — `kullanici_id` NULL'lanabilir olduğu için bekçi
    türetimi de onu iş tablosu saymaz, tests/test_rls.py).
    """
    __tablename__ = "odeme_olaylari"
    __table_args__ = (
        Index("ix_odeme_olaylari_alindi", "alindi"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    webhook_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tur: Mapped[str] = mapped_column(Text, nullable=False)
    polar_nesne_id: Mapped[str | None] = mapped_column(Text)
    kullanici_id: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True), ForeignKey("kullanicilar.id", ondelete="SET NULL"))
    govde: Mapped[dict[str, object]] = mapped_column(pg.JSONB, nullable=False)
    alindi: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("now()"))
    islendi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    hata: Mapped[str | None] = mapped_column(Text)
