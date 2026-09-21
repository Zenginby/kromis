# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kredi defteri — `kredi_hareketleri` ve `kullanicilar.bakiye`/`paket_bakiye`nin TEK yazarı, saf `(db, …)` işlevler (Faz 3 / 1; Faz 4 / 2 iki kova).

APPEND-ONLY TEK TABLO + İKİ ÖNBELLEK (docs/faz3-kredi-defteri-filigran.md §1, K1;
docs/faz4-odeme-abonelik-kvkk.md §2, K3): her para hareketi bir satır
(`KrediHareketi`, imzalı `miktar`, `kova`), bakiye iki önbellekte —
`kullanicilar.bakiye` HİBE kovası (aylık/dönem hibesi, devretmez), `kullanicilar.
paket_bakiye` PAKET kovası (satın alınan kredi, devreder); kaynak gerçek
`SUM(miktar) WHERE kova = …`. Çift kayıt değil: tek hesap türü var, karşı ayak
her satırda "platform" olurdu (bilgi sıfır).

İKİ KOVA, TEK TABLO — FIFO satırları ya da Polar sayaçları DEĞİL (Faz 4 K3).
Faz 3'ün tek kovası ("hibeye tamamla") paketle kırılıyor: 5.000 kredilik paket
almış kullanıcı `bakiye < hibe` koşulunu hiç sağlamaz, aylık hibesini kaybeder;
ya da hibe paketin üstüne biner, "devretmeyen hibe" boşa çıkar. İki önbellek
sütunu: atomiklik Faz 3 K1'in aynı UPDATE'inde kalır (`LEAST` ile bölüşüm tek
ifadede), `tutarlilik` iki SUM'la ikisini de doğrular, satır sayısı artmaz (iş
başına en fazla iki `rezerv` satırı, çoğu işte bir).

DÜŞÜM ATOMİK, KİLİTSİZ, HİBE ÖNCE: `rezerve` tek ifadeyle iki kovadan düşer —
`UPDATE kullanicilar SET bakiye = bakiye - LEAST(bakiye, :m), paket_bakiye =
paket_bakiye - (:m - LEAST(bakiye, :m)) WHERE id = :u AND bakiye + paket_bakiye
>= :m`. Koşul UPDATE'in İÇİNDE: iki eş zamanlı rezerv aynı bakiyeye yarışırsa
Postgres satırı kilitler, ikincisi birincinin commit'ini bekler ve GÜNCEL
değeri görür. Hibe kovası ÖNCE tükenir: devretmeyen önce, devreden sona —
kullanıcı lehine (paket önce tükenseydi ay sonunda devreden kredi gitmiş,
devretmeyen kalmış olurdu). BÖLÜŞÜM ESKİ DEĞERLERDEN okunur ve bunun için
ifade bir CTE ile `SELECT … FOR UPDATE` taşır: `RETURNING` yalnız YENİ satırı
verir (PG 18'in `RETURNING OLD` ı test kümesinin PG 16'sında yok) ve yeni
değerlerden bölüşüm çıkmaz (`bakiye` 0'a indiyse hibeden ne düştüğü
bilinmez). CTE'deki `FOR UPDATE` READ COMMITTED altında satırın SON commit
edilmiş hâlini döndürür ve UPDATE aynı kilitli satırı görür: eski değer
bayat olamaz; hepsi TEK gidiş-dönüş, kilit zaten UPDATE'in kilidi. 0 satır →
toplam yetmedi, `YetersizBakiye(toplam, gereken, hibe=…, paket=…)` ve defter
satırı YAZILMAZ (rota 402 kurar, K11 — bu modül konuşmaz). Test: iki
`Session`, gerçek Postgres, 100 tekrar, çift düşüm 0 (tests/test_defter.py).

İŞ BAŞINA SATIRLAR: `rezerv:<is_id>` ANA satır (her işte bir tane — `onayla`/
`iade` ve idempotency onu bulur) ve gerekirse `rezerv:<is_id>:paket` İKİNCİ
satır (kova paket). Ana satırın kovası HİBE, ama iş tamamen paketten düştüyse
(hibe kovası boştu) ana satır PAKET kovasında yazılır ve ikinci satır olmaz:
sıfır miktarlı bir hibe satırı ("rezerv +0") kullanıcının hareket listesinde
anlamsız bir kayıt olurdu. Kural `_iki_satir`de tek yerde. Aynı deyim `onay`
ve `iade` için: `onay:<is_id>`(+`:paket`), `iade:<is_id>`(+`:paket`).

`onayla`/`iade` KOVAYA GERİ VERİR, ÖNCE PAKETE: iade edilen kredi hangi
kovadan düştüyse oraya döner — `iade` rezerv satırlarını kova kova geri
koyar; `onayla`nın farkı (tahmin − gerçek) ÖNCE paket kovasına (o en son
düşmüştü; iade edilen paket kredisi devretmeyi sürdürür), kalan hibeye.
`onayla` FARK İADE EDER, EK TAHSİLAT YAPMAZ: `fark = tahmin - gercek`; `fark >
0` `onay` satırı `+fark`; `fark == 0` yalnız `onay` 0 (iz: "onaylandı"); `fark
< 0` — gerçek tahmini AŞTI, tahmin üst sınırdır (Faz 2 / 6), olmamalı — yine
`onay` 0 ve `WARNING olay=defter.asim`; kullanıcıdan fazlası alınmaz.
Rezerv satırı yoksa (BYOK iş — K3; göç öncesi iş) no-op `None`.

İDEMPOTENCY SATIRIN KENDİSİNDE: `idempotency_anahtari` UNIQUE, yazım `INSERT
… ON CONFLICT DO NOTHING RETURNING`; satır yazılmadıysa bakiye de değişmez.
Anahtar biçimleri SÖZLEŞME (Faz 3 belge §1 "Risk", Faz 4 "Veri modeli"):
`rezerv:<is_id>`, `onay:<is_id>`, `iade:<is_id>` (+ `:paket` ikinci kova),
`hibe:<u>:<YYYY-MM>` (aylık, `free`), `hibe:<u>:polar:<order_id>` (ücretli
dönem hibesi — 3. görev kurar), `duzeltme:<uuid4>` (verilmezse),
`paket:<polar_order_id>` (K4 — SİPARİŞ kimliği, olay id'si değil: aynı
siparişi anlatan iki olay gelebilir, sipariş bir kez kredi olur),
`sona_erme:<u>:<abonelik_id>:<YYYY-MM-DD>` (3. görev kurar). `onayla` ve
`iade` birbirini dışlar: biri yazılmışsa öteki no-op.

PAKET YÜKLEME `paket_yukle`: `paket` satırı `+miktar` kova paket, `hibe`nin
deseni (`ON CONFLICT` → `False`); webhook `order.paid` çağırır (3. görev, admin
bağlamı — `yonetici_ekler`). PLAN DÜŞÜRME `dusur`: hibe kovasını yeni planın
hibesine indirir (`sona_erme` satırı `-(bakiye - hedef)`, kova hibe — Faz 3
`:501-503` "paketlerle gelirse anlam kazanır": geldi); paket kovasına
DOKUNMAZ (devreder). Sıcak yol değil (webhook, ayda bir): `SELECT … FOR
UPDATE` + UPDATE iki gidiş-dönüş burada kabul — kilit eş zamanlı rezervi
bekletir, eksiye inilmez.

KİRACI: `bakiye`/`hibe`/`paket_yukle`/`rezerve`/`dusur`/`hareketler` kullanıcı
imzalı `(db, kullanici_id, …)` ve `kullanicilar` sorgusunu `_sahibin(kullanici_id)`
ile süzer (bekçisi tests/test_galeri_db.py); `onayla`/`iade` işçinin (`is_id`
`al`dan geldi, RLS bağlamını işçi bağlar), `duzelt` adminin (`hedef_id`;
`yonetici_ekler` K4), `tutarlilik`/`hibe_turu` bakım turunun (bütün kiracılar,
admin bağlamı) — `KIRACISIZ` defterinde gerekçesiyle. `kullanicilar`
politikasız: iki önbellek yazımı rota (kullanıcı) ve işçi/webhook (admin)
bağlamında aynı ifadeyle geçer; yazan yer YALNIZ bu modül (AST bekçisi
tests/test_defter.py: `kullanicilar.bakiye`/`paket_bakiye`ye UPDATE kuran
başka modül yok, `KrediHareketi` kuran da).

AYLIK HİBE "HİBEYE TAMAMLA", DEVRETMEZ (K6): `hibe_turu(db, an)` `bakiye <
aylik_hibe` (HİBE kovası; paket kovası hesaba girmez — paketli kullanıcı
hibesini kaybetmesin, K3'ün sebebi) olan kullanıcıya FARKI yatırır (`hibe:<u>:
<YYYY-MM>`). Faz 4 / 2'den itibaren YALNIZ `free` planı tarar: ücretli planın
dönem hibesi Polar'ın `order.paid` olayıyla gelir (`services/odeme.py`, 3. görev;
Faz 4 / 2'nin geçici köprü bayrağı 3 ile kaldırıldı).
Anahtar aylık → ay içinde bir kez; kayıt (`routers/hesap.py`) aynı anahtarla
(`aylik_hibe_yaz`) hemen yatırır. `kullanicilar.plan`/`plan_bitis` da bu
modülden okunur (`plan_oku`, `plan_bitis_oku`): hesap tablosu, sahip `id`.

KONUŞMAZ: cümle yok; `YetersizBakiye` sayı taşır, 402 gövdesini rota kurar.
Zaman `zaman.an()` Python'dan — testler `an` verir. `_json` `admin_id` ve
`idempotency_anahtari`ni DÖKMEZ (iç iş), `kova`yı döker (Faz 4 / 2: "Kredi"
bölmesi satırın hangi kovayı oynattığını söyler).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import uuid
from typing import Any, NamedTuple

from sqlalchemy import ColumnElement, case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services import gunluk, planlar, zaman
from services.tablolar import (
    HAREKET_TURLERI,
    KOVA_HIBE,
    KOVA_PAKET,
    KOVALAR,
    KrediHareketi,
    Kullanici,
)

__all__ = ["TUR_HIBE", "TUR_REZERV", "TUR_ONAY", "TUR_IADE", "TUR_DUZELTME", "TUR_SONA_ERME", "TUR_PAKET",
           "KOVA_HIBE", "KOVA_PAKET",
           "ONEK_REZERV", "ONEK_ONAY", "ONEK_IADE", "ONEK_HIBE", "ONEK_DUZELTME", "ONEK_PAKET", "ONEK_SONA_ERME",
           "EK_PAKET",
           "Hareket", "Bakiye", "Sapma", "YetersizBakiye",
           "bakiye", "plan_oku", "plan_bitis_oku", "hibe", "aylik_hibe_yaz", "paket_yukle", "rezerve",
           "onayla", "iade", "duzelt", "dusur", "hareketler", "hibe_turu", "tutarlilik"]

_gunluk = logging.getLogger("kromis.defter")

# Tür sabitleri `HAREKET_TURLERI`nin sırasıyla (CHECK'in kaynağı `services/tablolar.py`).
TUR_HIBE, TUR_REZERV, TUR_ONAY, TUR_IADE, TUR_DUZELTME, TUR_SONA_ERME, TUR_PAKET = HAREKET_TURLERI

# İdempotency anahtarı önekleri — biçim `<onek><kimlik>`; ikinci kova satırı `<anahtar><EK_PAKET>`.
ONEK_REZERV = "rezerv:"
ONEK_ONAY = "onay:"
ONEK_IADE = "iade:"
ONEK_HIBE = "hibe:"
ONEK_DUZELTME = "duzeltme:"
ONEK_PAKET = "paket:"
ONEK_SONA_ERME = "sona_erme:"
EK_PAKET = ":paket"


class YetersizBakiye(Exception):
    """`rezerve` toplamı yetersiz buldu: `bakiye` iki kovanın TOPLAMI (402 gövdesinin `bakiye`si — Faz 3 adı
    korunur), `gereken` istenen düşüm; `hibe`/`paket` kovaların o anki değerleri. Satır yazılmadı."""

    def __init__(self, bakiye: int, gereken: int, *, hibe: int = 0, paket: int = 0) -> None:
        super().__init__(bakiye, gereken)
        self.bakiye = bakiye
        self.gereken = gereken
        self.hibe = hibe
        self.paket = paket


@dataclasses.dataclass(frozen=True)
class Hareket:
    """Bir defter satırının ORM'den bağımsız kopyası — çağıran transaksiyon bitince de okuyabilsin."""
    id: uuid.UUID
    kullanici_id: uuid.UUID
    tur: str
    kova: str
    miktar: int
    is_id: uuid.UUID | None
    aciklama: str | None
    admin_id: uuid.UUID | None
    idempotency_anahtari: str
    olusturuldu: dt.datetime


@dataclasses.dataclass(frozen=True)
class Bakiye:
    """İki kova ve toplamı (Faz 4 / 2): `hibe` = `kullanicilar.bakiye`, `paket` = `paket_bakiye`, `toplam` ikisi;
    okuyanların çoğu `toplam`a bakar (kapı, composer "kalan"), "Kredi" bölmesi ikisini ayrı gösterir.
    Üç alan da veri (özellik değil): tests/test_galeri_db.py imza bekçisi sınıf gövdesindeki her açık işlevi tarar."""
    hibe: int
    paket: int
    toplam: int


class Sapma(NamedTuple):
    """`tutarlilik`in bir satırı: iki kovanın önbelleği ve defter toplamı; en az biri ayrışmış."""
    kullanici_id: uuid.UUID
    bakiye: int
    hibe_toplam: int
    paket_bakiye: int
    paket_toplam: int


def _hareket(satir: KrediHareketi) -> Hareket:
    return Hareket(id=satir.id, kullanici_id=satir.kullanici_id, tur=satir.tur, kova=satir.kova,
                   miktar=satir.miktar, is_id=satir.is_id, aciklama=satir.aciklama, admin_id=satir.admin_id,
                   idempotency_anahtari=satir.idempotency_anahtari, olusturuldu=satir.olusturuldu)


def _json(h: Hareket) -> dict[str, Any]:
    """Dışarıya dökülen sözlük: `admin_id` ve `idempotency_anahtari` YOK (iç iş). Damga UTC `Z` (`kuyruk._json`)."""
    return {
        "id": str(h.id),
        "tur": h.tur,
        "kova": h.kova,
        "miktar": h.miktar,
        "aciklama": h.aciklama,
        "is_id": str(h.is_id) if h.is_id is not None else None,
        "olusturuldu": zaman.damga_utc(h.olusturuldu),
    }


def _sahibin(kullanici_id: uuid.UUID) -> ColumnElement[bool]:
    """`kullanicilar` satırının sahibi kendisidir: sahip süzgeci `id` sütunu (depo modüllerinin deyimi)."""
    return Kullanici.id == kullanici_id


def _kova_sutunu(kova: str) -> Any:
    """Kovanın önbellek sütunu; tanınmayan kova `ValueError` (CHECK'ten önce burada düşsün)."""
    if kova == KOVA_HIBE:
        return Kullanici.bakiye
    if kova == KOVA_PAKET:
        return Kullanici.paket_bakiye
    raise ValueError(f"kova {KOVALAR} icinden olmali: {kova!r}")


def _yaz(db: Session, *, kullanici_id: uuid.UUID, tur: str, miktar: int, anahtar: str,
         kova: str = KOVA_HIBE, is_id: uuid.UUID | None = None, aciklama: str | None = None,
         admin_id: uuid.UUID | None = None, an: dt.datetime | None = None) -> KrediHareketi | None:
    """Defter satırı — `INSERT … ON CONFLICT (idempotency_anahtari) DO NOTHING RETURNING`; çakıştıysa `None`.

    Bakiye BURADA değişmez: çağıran satırın yazıldığını görürse önbelleği
    oynatır (`_bakiye_ekle`), görmezse dokunmaz — idempotency iki yazımı
    birlikte kapsar.
    """
    ifade = (insert(KrediHareketi)
             .values(kullanici_id=kullanici_id, is_id=is_id, tur=tur, kova=kova, miktar=miktar,
                     aciklama=aciklama, admin_id=admin_id, idempotency_anahtari=anahtar,
                     olusturuldu=an if an is not None else zaman.an())
             .on_conflict_do_nothing(index_elements=[KrediHareketi.idempotency_anahtari])
             .returning(KrediHareketi))
    return db.scalars(ifade).one_or_none()


def _bakiye_ekle(db: Session, kullanici_id: uuid.UUID, miktar: int, kova: str = KOVA_HIBE) -> None:
    """Kovanın önbelleğine `miktar` ekler (negatif = düşer). Koşulsuz: koşullu düşüm yalnız `rezerve`de.

    İki dal, tek sözlük değil: `.values(bakiye=…)`/`.values(paket_bakiye=…)` anahtar
    sözcüğü tek yazar bekçisinin (tests/test_defter.py) gördüğü biçim.
    """
    _kova_sutunu(kova)
    ifade = update(Kullanici).where(_sahibin(kullanici_id))
    if kova == KOVA_PAKET:
        db.execute(ifade.values(paket_bakiye=Kullanici.paket_bakiye + miktar))
    else:
        db.execute(ifade.values(bakiye=Kullanici.bakiye + miktar))


def _isin_hareketleri(db: Session, is_id: uuid.UUID) -> list[KrediHareketi]:
    """Bir işin satırları (`ix_kredi_hareketleri_is`); tür başına en çok iki satır (ana + `:paket`), anahtar UNIQUE."""
    return list(db.scalars(select(KrediHareketi).where(KrediHareketi.is_id == is_id)
                           .order_by(KrediHareketi.olusturuldu, KrediHareketi.id)))


def _iki_satir(db: Session, *, kullanici_id: uuid.UUID, tur: str, anahtar: str, hibe: int, paket: int,
               is_id: uuid.UUID, an: dt.datetime | None) -> tuple[KrediHareketi | None, KrediHareketi | None]:
    """Bir işin kova başına satırları: ANA satır `anahtar` (kova hibe; iş tamamen paketten düştüyse kova paket),
    İKİNCİ satır `anahtar:paket` yalnız iki kova da oynadıysa. `(ana, ikinci)`; ana çakıştıysa `(None, None)`.

    `hibe`/`paket` imzalı miktarlar (rezerv negatif, onay/iade pozitif); ikisi de
    0 ise ana satır 0 miktarla hibe kovasında yazılır ("onaylandı" izi).
    """
    if hibe == 0 and paket != 0:
        ana = _yaz(db, kullanici_id=kullanici_id, tur=tur, miktar=paket, anahtar=anahtar, kova=KOVA_PAKET,
                   is_id=is_id, an=an)
        return ana, None
    ana = _yaz(db, kullanici_id=kullanici_id, tur=tur, miktar=hibe, anahtar=anahtar, kova=KOVA_HIBE,
               is_id=is_id, an=an)
    if ana is None:
        return None, None
    ikinci = None
    if paket != 0:
        ikinci = _yaz(db, kullanici_id=kullanici_id, tur=tur, miktar=paket, anahtar=anahtar + EK_PAKET,
                      kova=KOVA_PAKET, is_id=is_id, an=an)
    return ana, ikinci


def _kova_toplamlari(satirlar: list[KrediHareketi]) -> tuple[int, int]:
    """`(hibe, paket)` — verilen satırların kova başına toplamı (imzalı)."""
    hibe = sum(s.miktar for s in satirlar if s.kova == KOVA_HIBE)
    paket = sum(s.miktar for s in satirlar if s.kova == KOVA_PAKET)
    return hibe, paket


# ─────────────────────────────────────────────────── kullanıcı tarafı

def bakiye(db: Session, kullanici_id: uuid.UUID) -> Bakiye:
    """İki kova önbellekten (`kullanicilar.bakiye`, `paket_bakiye`); satır yoksa `Bakiye(0, 0, 0)`."""
    satir = db.execute(select(Kullanici.bakiye, Kullanici.paket_bakiye).where(_sahibin(kullanici_id))).one_or_none()
    if satir is None:
        return Bakiye(0, 0, 0)
    hibe_, paket_ = int(satir[0]), int(satir[1])
    return Bakiye(hibe_, paket_, hibe_ + paket_)


def plan_oku(db: Session, kullanici_id: uuid.UUID) -> str:
    """Kullanıcının planı (`kullanicilar.plan`, CHECK `PLANLAR_KUMESI`); satır yoksa `free` (3. görev).

    DB'den, `kullanici.plan`dan değil (`kapilar._yetersiz_bakiye`nin kararı):
    sütun `server_default`lı ve bağımlılığın verdiği nesne başka oturumdan/
    ayrılmış olabilir — `DetachedInstanceError` yerine tek indeksli SELECT.
    """
    return str(db.scalar(select(Kullanici.plan).where(_sahibin(kullanici_id))) or planlar.PLAN_VARSAYILAN)


def plan_bitis_oku(db: Session, kullanici_id: uuid.UUID) -> dt.datetime | None:
    """İptal edilmiş aboneliğin dönem sonu (`kullanicilar.plan_bitis`, Faz 4 / 2; 3. görev yazar); yoksa `None`.

    `plan_oku`nun gerekçesi aynen: bağımlılığın nesnesi ayrılmış olabilir, tek SELECT.
    """
    return db.scalar(select(Kullanici.plan_bitis).where(_sahibin(kullanici_id)))


def aylik_hibe_yaz(db: Session, kullanici_id: uuid.UUID, miktar: int, an: dt.datetime) -> bool:
    """`an`ın AYININ hibesi: `hibe` anahtarı `hibe:<u>:<YYYY-MM>` ile (K6); `False` = o ay zaten yatmış.

    Anahtarı TEK yer kurar: kayıt (`routers/hesap.py`, ilk hibe) ve bakım turu
    (`hibe_turu`) bu işlevi çağırır — biçim iki yerde yazılsaydı biri `%Y-%m`,
    öteki `%Y%m` derdi ve ay içinde iki hibe yatardı.
    """
    return hibe(db, kullanici_id, miktar, f"{ONEK_HIBE}{kullanici_id}:{an:%Y-%m}", an=an)


def hibe(db: Session, kullanici_id: uuid.UUID, miktar: int, anahtar: str, aciklama: str | None = None, *,
         an: dt.datetime | None = None) -> bool:
    """`hibe` satırı `+miktar` (kova hibe; anahtar çağıranın: `hibe:<u>:<YYYY-MM>` ya da `hibe:<u>:polar:<order_id>`)
    + bakiye `+miktar`; `False` = zaten vardı.

    Aylık hibe (3. görev, K6 "hibeye tamamla"), kayıt hibesi ve Faz 4 / 3'ün
    dönem hibesi çağırır; bakım turunda tekrar tekrar koşar — `ON CONFLICT`
    tekrarı no-op yapar.
    """
    if miktar <= 0:
        raise ValueError(f"hibe pozitif olmali: {miktar}")
    satir = _yaz(db, kullanici_id=kullanici_id, tur=TUR_HIBE, miktar=miktar, anahtar=anahtar,
                 aciklama=aciklama, an=an)
    if satir is None:
        return False
    _bakiye_ekle(db, kullanici_id, miktar)
    return True


def paket_yukle(db: Session, kullanici_id: uuid.UUID, miktar: int, anahtar: str, aciklama: str | None = None, *,
                an: dt.datetime | None = None) -> bool:
    """`paket` satırı `+miktar` KOVA PAKET (anahtar çağıranın: `paket:<polar_order_id>`, K4) + `paket_bakiye`
    `+miktar`; `False` = bu sipariş zaten yüklenmiş.

    Webhook `order.paid` (Faz 4 / 3, admin bağlamı) çağırır; aynı siparişi
    anlatan ikinci olay (`subscription.active`, panelden yeniden gönderim)
    anahtarda çakışır — sipariş bir kez kredi olur. `hibe`nin deseni; kovası
    farklı, tek işlev yapılmadı çünkü ikisinin türü ve önbelleği ayrı ve
    çağıranın kovayı seçebilmesi gerekmez (paket her zaman paket kovasına).
    """
    if miktar <= 0:
        raise ValueError(f"paket pozitif olmali: {miktar}")
    satir = _yaz(db, kullanici_id=kullanici_id, tur=TUR_PAKET, miktar=miktar, anahtar=anahtar, kova=KOVA_PAKET,
                 aciklama=aciklama, an=an)
    if satir is None:
        return False
    _bakiye_ekle(db, kullanici_id, miktar, KOVA_PAKET)
    return True


# TEK gidiş-dönüş, iki kova, ESKİ değerler (gerekçe modül başında): CTE satırı
# kilitler ve son commit edilmiş hâlini verir, UPDATE aynı satırı bölüşür.
# Bekçi tests/test_defter.py `_BAKIYE_SQL` bu dizeyi "bakiye yazan" sayar — doğru, tek yazar burası.
_REZERV_SQL = text("""
WITH eski AS (
    SELECT id, bakiye, paket_bakiye FROM kullanicilar WHERE id = :u FOR UPDATE
)
UPDATE kullanicilar k
   SET bakiye = k.bakiye - LEAST(k.bakiye, :m),
       paket_bakiye = k.paket_bakiye - (:m - LEAST(k.bakiye, :m))
  FROM eski
 WHERE k.id = eski.id AND k.bakiye + k.paket_bakiye >= :m
RETURNING eski.bakiye, eski.paket_bakiye
""")


def rezerve(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID, miktar: int, *,
            an: dt.datetime | None = None) -> Hareket:
    """Tahmini iki kovadan düşer — ATOMİK, HİBE ÖNCE (`WHERE bakiye + paket_bakiye >= :m`); yetmezse
    `YetersizBakiye`, satır YAZILMAZ. Döneni ANA `rezerv` satırı.

    Rota çağırır (kullanıcının bağlamı, `sahip`; `kuyruk.ekle` ile aynı
    transaksiyon — Faz 3 / 2). Aynı iş için ikinci çağrı (ana anahtar
    `rezerv:<is_id>` çakışır) düşümü iki kovada da geri alır ve var olan ana
    satırı döner: iş iki kez rezerve edilmez, bakiye iki kez düşmez.
    """
    if miktar < 0:
        raise ValueError(f"rezerv negatif olamaz: {miktar}")
    eski = db.execute(_REZERV_SQL, {"u": kullanici_id, "m": miktar}).one_or_none()
    if eski is None:
        b = bakiye(db, kullanici_id)
        raise YetersizBakiye(b.toplam, miktar, hibe=b.hibe, paket=b.paket)
    hibe_dusen = min(int(eski[0]), miktar)
    paket_dusen = miktar - hibe_dusen
    ana, _ikinci = _iki_satir(db, kullanici_id=kullanici_id, tur=TUR_REZERV, anahtar=f"{ONEK_REZERV}{is_id}",
                              hibe=-hibe_dusen, paket=-paket_dusen, is_id=is_id, an=an)
    if ana is None:
        if hibe_dusen:
            _bakiye_ekle(db, kullanici_id, hibe_dusen, KOVA_HIBE)
        if paket_dusen:
            _bakiye_ekle(db, kullanici_id, paket_dusen, KOVA_PAKET)
        mevcut = [s for s in _isin_hareketleri(db, is_id)
                  if s.tur == TUR_REZERV and s.idempotency_anahtari == f"{ONEK_REZERV}{is_id}"]
        return _hareket(mevcut[0])
    return _hareket(ana)


def hareketler(db: Session, kullanici_id: uuid.UUID, *, limit: int = 20) -> list[Hareket]:
    """Kullanıcının son hareketleri, EN YENİ ÜSTTE (`ix_kredi_hareketleri_kullanici_olusturuldu`); `_json` ile dökülür."""
    sorgu = (select(KrediHareketi).where(KrediHareketi.kullanici_id == kullanici_id)
             .order_by(KrediHareketi.olusturuldu.desc(), KrediHareketi.id).limit(limit))
    return [_hareket(h) for h in db.scalars(sorgu)]


# ─────────────────────────────────────────────────────── işçi tarafı

def _kapanis_hazirla(db: Session, is_id: uuid.UUID) -> tuple[list[KrediHareketi], uuid.UUID] | None:
    """`onayla`/`iade`nin ortak kapısı: işin rezerv satırları ve sahibi; rezerv yoksa ya da kapanmışsa `None`."""
    isin = _isin_hareketleri(db, is_id)
    rezervler = [s for s in isin if s.tur == TUR_REZERV]
    if not rezervler or any(s.tur in (TUR_ONAY, TUR_IADE) for s in isin):
        return None
    return rezervler, rezervler[0].kullanici_id


def _geri_ver(db: Session, kullanici_id: uuid.UUID, hibe_geri: int, paket_geri: int) -> None:
    for kova, m in ((KOVA_HIBE, hibe_geri), (KOVA_PAKET, paket_geri)):
        if m:
            _bakiye_ekle(db, kullanici_id, m, kova)


def onayla(db: Session, is_id: uuid.UUID, gercek: int, *, an: dt.datetime | None = None) -> Hareket | None:
    """İş bitti: rezervi gerçekle kapatır, farkı ÖNCE PAKET kovasına iade eder (`onay:<is_id>`[`:paket`]); rezerv
    yoksa ya da kapanmışsa `None`. Döneni ANA `onay` satırı.

    İşçi `kuyruk.bitir`le aynı commit'te çağırır (Faz 3 / 2). `gercek` ≥ 0
    (Σ `medya.credits`). Aşım (`gercek > tahmin`) ek tahsilat DEĞİL uyarı:
    tahmin üst sınır olmalıydı, sapma raporda görünsün (modül başı). Fark önce
    pakete: en son paketten düşülmüştü, iade edilen paket kredisi devretmeyi
    sürdürür (K3).
    """
    if gercek < 0:
        raise ValueError(f"gercek negatif olamaz: {gercek}")
    hazir = _kapanis_hazirla(db, is_id)
    if hazir is None:
        return None
    rezervler, kullanici_id = hazir
    hibe_rezerv, paket_rezerv = (-m for m in _kova_toplamlari(rezervler))
    tahmin = hibe_rezerv + paket_rezerv
    fark = tahmin - gercek
    if fark < 0:
        gunluk.olay(_gunluk, "defter.asim", "gercek maliyet tahmini asti", seviye=logging.WARNING,
                    is_id=str(is_id), kullanici_id=str(kullanici_id), tahmin=tahmin, gercek=gercek)
    paket_geri = min(max(fark, 0), paket_rezerv)
    hibe_geri = max(fark, 0) - paket_geri
    ana, _ikinci = _iki_satir(db, kullanici_id=kullanici_id, tur=TUR_ONAY, anahtar=f"{ONEK_ONAY}{is_id}",
                              hibe=hibe_geri, paket=paket_geri, is_id=is_id, an=an)
    if ana is None:
        return None
    _geri_ver(db, kullanici_id, hibe_geri, paket_geri)
    return _hareket(ana)


def iade(db: Session, is_id: uuid.UUID, *, an: dt.datetime | None = None) -> Hareket | None:
    """Rezervin TAMAMI geri, KOVA KOVA (`iade:<is_id>`[`:paket`]); onay ya da iade zaten varsa, rezerv yoksa `None`.

    Hata, iptal ve bayat düşürme çağırır (Faz 3 / 2) — ikisi aynı işi ikinci
    kez düşürebilir, ikinci çağrı satır yazmaz, bakiye oynamaz. Her kova
    kendi düşümünü geri alır: hibeden düşen hibeye, paketten düşen pakete.
    """
    hazir = _kapanis_hazirla(db, is_id)
    if hazir is None:
        return None
    rezervler, kullanici_id = hazir
    hibe_geri, paket_geri = (-m for m in _kova_toplamlari(rezervler))
    ana, _ikinci = _iki_satir(db, kullanici_id=kullanici_id, tur=TUR_IADE, anahtar=f"{ONEK_IADE}{is_id}",
                              hibe=hibe_geri, paket=paket_geri, is_id=is_id, an=an)
    if ana is None:
        return None
    _geri_ver(db, kullanici_id, hibe_geri, paket_geri)
    return _hareket(ana)


# ────────────────────────────────────────────────────── admin ve bakım

def duzelt(db: Session, hedef_id: uuid.UUID, miktar: int, aciklama: str | None, admin_id: uuid.UUID, *,
           anahtar: str | None = None, an: dt.datetime | None = None, kova: str = KOVA_HIBE) -> Hareket:
    """Admin düzeltmesi: `duzeltme` satırı (`admin_id` izi) + `kova`nın önbelleği `+miktar`; NEGATİF bakiyeye
    inebilir — bilerek. `kova` öntanımlı hibe; `paket` admin "paket kredisi ekle" (4. görev) ve iade kararı (K6).

    Admin bağlamında (`yonetici_ekler`, K4); kapı yok, iz var. `anahtar`
    verilmezse `duzeltme:<uuid4>` (her çağrı yeni satır); verilmiş ve zaten
    varsa var olan satır döner, bakiye oynamaz (rota yeniden denemesi).
    """
    _kova_sutunu(kova)
    anahtar = anahtar if anahtar is not None else f"{ONEK_DUZELTME}{uuid.uuid4()}"
    satir = _yaz(db, kullanici_id=hedef_id, tur=TUR_DUZELTME, miktar=miktar, anahtar=anahtar, kova=kova,
                 aciklama=aciklama, admin_id=admin_id, an=an)
    if satir is None:
        mevcut = db.scalars(select(KrediHareketi)
                            .where(KrediHareketi.idempotency_anahtari == anahtar)).one()
        return _hareket(mevcut)
    _bakiye_ekle(db, hedef_id, miktar, kova)
    return _hareket(satir)


def dusur(db: Session, kullanici_id: uuid.UUID, hedef: int, anahtar: str, *,
          an: dt.datetime | None = None) -> Hareket | None:
    """Plan düşürme (Faz 4 / 2, K3/K6): HİBE kovası `hedef`in (yeni planın hibesi) ÜSTÜNDEYSE `sona_erme` satırı
    `-(bakiye - hedef)` ve bakiye `hedef`e iner; paket kovasına DOKUNMAZ. Üstünde değilse ya da anahtar zaten
    yazılmışsa `None`.

    Webhook `subscription.revoked`/`updated` (3. görev, admin bağlamı) çağırır;
    anahtar çağıranın: `sona_erme:<u>:<abonelik_id>:<YYYY-MM-DD>`. Satır
    `FOR UPDATE` ile kilitlenir ki eş zamanlı bir rezerv araya girip bakiyeyi
    eksiye düşürmesin — iki gidiş-dönüş, sıcak yol değil (modül başı).
    """
    if hedef < 0:
        raise ValueError(f"hedef negatif olamaz: {hedef}")
    mevcut = db.scalar(select(Kullanici.bakiye).where(_sahibin(kullanici_id)).with_for_update())
    if mevcut is None or int(mevcut) <= hedef:
        return None
    fark = int(mevcut) - hedef
    satir = _yaz(db, kullanici_id=kullanici_id, tur=TUR_SONA_ERME, miktar=-fark, anahtar=anahtar, an=an)
    if satir is None:
        return None
    _bakiye_ekle(db, kullanici_id, -fark)
    return _hareket(satir)


def hibe_turu(db: Session, an: dt.datetime) -> int:
    """Aylık hibe turu (K6 "hibeye tamamla"): `free` planda `bakiye < aylik_hibe` (HİBE kovası) olan kullanıcıya
    farkı yatırır; yazılan satır sayısı. Ücretli planlar TARANMAZ (dönem hibesi webhook'un — `services/odeme.py`).

    Bakım turu (services/isci.py `bakim_turu`, 5 dk, ADMİN bağlamı —
    `yonetici_ekler`, K4) çağırır. Plan başına bir SELECT: süzgeç `WHERE plan =
    :p AND bakiye < :hibe` (Faz 3 belge §3 "Risk": 20-50 kullanıcıda ölçülemez;
    1.000+ kullanıcıda kısmi indeks adayı, Faz 5). Paket kovası hesaba
    GİRMEZ: paketli kullanıcı hibesini kaybetmez (K3). Silinmiş hesap almaz.
    `aylik_hibe` 0 olan plan atlanır. Aynı ay ikinci tur: anahtar çakışır,
    satır ve bakiye oynamaz — sayı 0.
    """
    yazilan = 0
    ad = planlar.PLAN_VARSAYILAN
    plan = planlar.PLANLAR[ad]
    if plan.aylik_hibe <= 0:
        return 0
    satirlar = db.execute(select(Kullanici.id, Kullanici.bakiye)
                          .where(Kullanici.plan == ad, Kullanici.bakiye < plan.aylik_hibe,
                                 Kullanici.silindi_at.is_(None))
                          .order_by(Kullanici.id)).all()
    for kullanici_id, mevcut in satirlar:
        if aylik_hibe_yaz(db, kullanici_id, plan.aylik_hibe - int(mevcut), an):
            yazilan += 1
    return yazilan


def tutarlilik(db: Session) -> list[Sapma]:
    """İki önbellek ↔ defter: `bakiye != SUM(kova=hibe)` YA DA `paket_bakiye != SUM(kova=paket)` olan kullanıcılar
    `Sapma(kullanici_id, bakiye, hibe_toplam, paket_bakiye, paket_toplam)` — ÖLÇER, düzeltmez.

    Bakım turu (Faz 3 / 7) çağırır, sapan her kova için `WARNING
    olay=defter.tutarsiz` (`kova` alanıyla); düzeltme admin `duzelt`. Hareketi
    olmayan kullanıcı iki toplamda 0 sayılır (LEFT JOIN): önbelleği 0 değilse
    o da sapmadır. Bütün kiracılar — admin bağlamı.
    """
    # Kova başına toplam CASE ile: tek tarama, alt sorgu yok.
    toplamlar = (select(KrediHareketi.kullanici_id,
                        func.sum(case((KrediHareketi.kova == KOVA_HIBE, KrediHareketi.miktar), else_=0))
                        .label("hibe"),
                        func.sum(case((KrediHareketi.kova == KOVA_PAKET, KrediHareketi.miktar), else_=0))
                        .label("paket"))
                 .group_by(KrediHareketi.kullanici_id).subquery())
    hibe_toplam = func.coalesce(toplamlar.c.hibe, 0)
    paket_toplam = func.coalesce(toplamlar.c.paket, 0)
    satirlar = db.execute(select(Kullanici.id, Kullanici.bakiye, hibe_toplam, Kullanici.paket_bakiye, paket_toplam)
                          .outerjoin(toplamlar, toplamlar.c.kullanici_id == Kullanici.id)
                          .where((Kullanici.bakiye != hibe_toplam) | (Kullanici.paket_bakiye != paket_toplam))
                          .order_by(Kullanici.id)).all()
    return [Sapma(kid, int(b), int(h), int(pb), int(p)) for kid, b, h, pb, p in satirlar]
