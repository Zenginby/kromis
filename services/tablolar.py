# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri modeli — 11 tablo, SQLAlchemy 2 `DeclarativeBase` (Faz 1 / 2. görev).

Bu modül ŞEMANIN tek tanımı: Alembic `alembic/env.py`de `Base.metadata`yı
okur, `alembic check` göç dosyalarının bu tanımdan ayrışmadığını sınar
(tests/test_tablolar.py). Burada sorgu YOK, depo işlevi YOK — onlar 5-7.
görevlerin `services/depo/` modülleri; burası yalnız tablo, sütun, kısıt.

Dört tablo hesabın (`kullanicilar`, `oturumlar`, `jetonlar`, `giris_denemeleri`),
yedisi bugünkü JSON depolarının karşılığı (docs/faz1-veritabani-hesaplar.md,
"Envanter"): `medya` ← history.json, `klasorler` ← folders.json, `sohbetler`
← chats.json, `paletler` ← palettes.json, `varliklar` ← assets/*/index.json,
`tercihler` ← prefs.json, `saglayici_kimlikleri` ← credentials.env.

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

# Yedi iş tablosu — belgenin envanteriyle birebir; bekçi test bu kümenin her
# üyesinde `kullanici_id` + FK + indeks arar ve kümenin belgeyle eşit olduğunu
# sınar. Hesap tabloları burada DEĞİL: onlarda sahiplik sütunu ya yok
# (`kullanicilar`, `giris_denemeleri`) ya da anlamı başka (`oturumlar`).
IS_TABLOLARI: tuple[str, ...] = (
    "medya", "klasorler", "sohbetler", "paletler", "varliklar",
    "tercihler", "saglayici_kimlikleri",
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
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    eposta: Mapped[str] = mapped_column(pg.CITEXT, nullable=False, unique=True)
    parola_ozeti: Mapped[str | None] = mapped_column(Text)
    dogrulandi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    dil: Mapped[str | None] = mapped_column(Text)
    olusturuldu: Mapped[dt.datetime] = _olusturuldu()
    guncellendi: Mapped[dt.datetime] = _guncellendi()
    silindi_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


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
