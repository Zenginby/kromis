# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kredi defteri — `kredi_hareketleri` ve `kullanicilar.bakiye`nin TEK yazarı, saf `(db, …)` işlevler (Faz 3 / 1).

APPEND-ONLY TEK TABLO + ÖNBELLEK (docs/faz3-kredi-defteri-filigran.md §1, K1):
her para hareketi bir satır (`KrediHareketi`, imzalı `miktar`), bakiye
`kullanicilar.bakiye`de ÖNBELLEK — kaynak gerçek `SUM(miktar)`. Çift kayıt
değil: tek hesap türü var, karşı ayak her satırda "platform" olurdu (bilgi
sıfır); Faz 4 ödeme mutabakatıyla anlam kazanırsa göçle gelir, satırlar kalır.

DÜŞÜM ATOMİK, KİLİTSİZ: `rezerve` tek ifadeyle düşer —
`UPDATE kullanicilar SET bakiye = bakiye - :m WHERE id = :u AND bakiye >= :m`.
Koşul UPDATE'in İÇİNDE: iki eş zamanlı rezerv aynı bakiyeye yarışırsa Postgres
satırı kilitler, ikincisi birincinin commit'ini bekler ve GÜNCEL değeri görür;
`SELECT … FOR UPDATE` + karşılaştırma iki gidiş-dönüş ve tutulan kilit olurdu,
her seferinde `SUM` almak kullanıcı başına büyüyen tarama. 0 satır → bakiye
yetmedi, `YetersizBakiye(bakiye, gereken)` ve defter satırı YAZILMAZ (rota 402
kurar, K11 — bu modül konuşmaz). Test: iki `Session`, gerçek Postgres, 100
tekrar, çift düşüm 0 (tests/test_defter.py).

İDEMPOTENCY SATIRIN KENDİSİNDE: `idempotency_anahtari` UNIQUE, yazım `INSERT
… ON CONFLICT DO NOTHING RETURNING`; satır yazılmadıysa bakiye de değişmez.
Anahtar biçimleri Faz 4'ün okuyacağı SÖZLEŞME (belge §1 "Risk"): `rezerv:<is_id>`,
`onay:<is_id>`, `iade:<is_id>` (iş başına birer — `iade` iki kez çağrılabilir:
`dusur` ve bayat düşürme aynı işi ikinci kez düşürebilir), `hibe:<u>:<YYYY-MM>`
(çağıran kurar, 3. görev), `duzeltme:<uuid4>` (verilmezse). `onayla` ve `iade`
birbirini dışlar: biri yazılmışsa öteki no-op — bitmiş iş iade edilmez, iade
edilmiş iş onaylanmaz.

`onayla` FARK İADE EDER, EK TAHSİLAT YAPMAZ: `fark = -rezerv.miktar - gercek`;
`fark > 0` `onay` satırı `+fark` ve bakiye `+fark`; `fark == 0` yalnız `onay` 0
(iz: "onaylandı"); `fark < 0` — gerçek tahmini AŞTI, tahmin üst sınırdır (Faz
2 / 6), olmamalı — yine `onay` 0 ve `WARNING olay=defter.asim`; kullanıcıdan
fazlası alınmaz, mutabakat raporu (5. görev) yakalar. Rezerv satırı yoksa
(BYOK iş — K3, defteri hiç görmez; göç öncesi iş) no-op `None`.

KİRACI: `bakiye`/`hibe`/`rezerve`/`hareketler` kullanıcı imzalı `(db,
kullanici_id, …)` ve `kullanicilar` sorgusunu `_sahibin(kullanici_id)` ile
süzer (hesap tablosunun sahibi `id` sütunu — depo modüllerinin `_sahibin`
deyimi, bekçisi tests/test_galeri_db.py); `onayla`/`iade` işçinin (`is_id`
`al`dan geldi, RLS bağlamını işçi bağlar: `kos` işin kullanıcısı, bayat iade
admin), `duzelt` adminin (`hedef_id`, `depo_admin`in adlandırması;
`yonetici_ekler` politikası K4), `tutarlilik` bakım turunun (bütün kiracılar,
admin bağlamı) — dördü `KIRACISIZ` defterinde gerekçesiyle. `kullanicilar`
politikasız: `bakiye` yazımı rota (kullanıcı) ve işçi (admin) bağlamında aynı
ifadeyle geçer; yazan yer YALNIZ bu modül (AST bekçisi tests/test_defter.py:
`kullanicilar.bakiye`ye UPDATE kuran başka modül yok, `KrediHareketi` kuran da).

KONUŞMAZ: cümle yok; `YetersizBakiye` iki sayı taşır, 402 gövdesini rota kurar
(`services/db.py`nin `database_unavailable` kararı). Zaman `zaman.an()`
Python'dan (mikrosaniye, Faz 1 / 5) — testler `an` verir, saatle oynamaz
(`kuyruk.ekle` deseni). `_json` `admin_id` ve `idempotency_anahtari`ni
DÖKMEZ: iç iş (kimin düzelttiği admin panelinin, anahtar Faz 4'ün).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services import gunluk, zaman
from services.tablolar import HAREKET_TURLERI, KrediHareketi, Kullanici

__all__ = ["TUR_HIBE", "TUR_REZERV", "TUR_ONAY", "TUR_IADE", "TUR_DUZELTME", "TUR_SONA_ERME",
           "ONEK_REZERV", "ONEK_ONAY", "ONEK_IADE", "ONEK_HIBE", "ONEK_DUZELTME",
           "Hareket", "YetersizBakiye",
           "bakiye", "hibe", "rezerve", "onayla", "iade", "duzelt", "hareketler", "tutarlilik"]

_gunluk = logging.getLogger("kromis.defter")

# Tür sabitleri `HAREKET_TURLERI`nin sırasıyla (CHECK'in kaynağı `services/tablolar.py`).
TUR_HIBE, TUR_REZERV, TUR_ONAY, TUR_IADE, TUR_DUZELTME, TUR_SONA_ERME = HAREKET_TURLERI

# İdempotency anahtarı önekleri — biçim `<onek><kimlik>`; Faz 4 `polar:` ekler.
ONEK_REZERV = "rezerv:"
ONEK_ONAY = "onay:"
ONEK_IADE = "iade:"
ONEK_HIBE = "hibe:"
ONEK_DUZELTME = "duzeltme:"


class YetersizBakiye(Exception):
    """`rezerve` bakiyeyi yetersiz buldu: `bakiye` o anki değer, `gereken` istenen düşüm. Satır yazılmadı."""

    def __init__(self, bakiye: int, gereken: int) -> None:
        super().__init__(bakiye, gereken)
        self.bakiye = bakiye
        self.gereken = gereken


@dataclasses.dataclass(frozen=True)
class Hareket:
    """Bir defter satırının ORM'den bağımsız kopyası — çağıran transaksiyon bitince de okuyabilsin."""
    id: uuid.UUID
    kullanici_id: uuid.UUID
    tur: str
    miktar: int
    is_id: uuid.UUID | None
    aciklama: str | None
    admin_id: uuid.UUID | None
    idempotency_anahtari: str
    olusturuldu: dt.datetime


def _hareket(satir: KrediHareketi) -> Hareket:
    return Hareket(id=satir.id, kullanici_id=satir.kullanici_id, tur=satir.tur, miktar=satir.miktar,
                   is_id=satir.is_id, aciklama=satir.aciklama, admin_id=satir.admin_id,
                   idempotency_anahtari=satir.idempotency_anahtari, olusturuldu=satir.olusturuldu)


def _json(h: Hareket) -> dict[str, Any]:
    """Dışarıya dökülen sözlük: `admin_id` ve `idempotency_anahtari` YOK (iç iş). Damga UTC `Z` (`kuyruk._json`)."""
    return {
        "id": str(h.id),
        "tur": h.tur,
        "miktar": h.miktar,
        "aciklama": h.aciklama,
        "is_id": str(h.is_id) if h.is_id is not None else None,
        "olusturuldu": zaman.damga_utc(h.olusturuldu),
    }


def _sahibin(kullanici_id: uuid.UUID) -> ColumnElement[bool]:
    """`kullanicilar` satırının sahibi kendisidir: sahip süzgeci `id` sütunu (depo modüllerinin deyimi)."""
    return Kullanici.id == kullanici_id


def _etkilenen(sonuc: object) -> int:
    """`UPDATE` sonucunun satır sayısı; ORM `Result` tipi `rowcount`u ilan etmiyor (`kuyruk._etkilenen`)."""
    return int(getattr(sonuc, "rowcount", 0) or 0)


def _yaz(db: Session, *, kullanici_id: uuid.UUID, tur: str, miktar: int, anahtar: str,
         is_id: uuid.UUID | None = None, aciklama: str | None = None,
         admin_id: uuid.UUID | None = None, an: dt.datetime | None = None) -> KrediHareketi | None:
    """Defter satırı — `INSERT … ON CONFLICT (idempotency_anahtari) DO NOTHING RETURNING`; çakıştıysa `None`.

    Bakiye BURADA değişmez: çağıran satırın yazıldığını görürse önbelleği
    oynatır (`_bakiye_ekle`), görmezse dokunmaz — idempotency iki yazımı
    birlikte kapsar.
    """
    ifade = (insert(KrediHareketi)
             .values(kullanici_id=kullanici_id, is_id=is_id, tur=tur, miktar=miktar,
                     aciklama=aciklama, admin_id=admin_id, idempotency_anahtari=anahtar,
                     olusturuldu=an if an is not None else zaman.an())
             .on_conflict_do_nothing(index_elements=[KrediHareketi.idempotency_anahtari])
             .returning(KrediHareketi))
    return db.scalars(ifade).one_or_none()


def _bakiye_ekle(db: Session, kullanici_id: uuid.UUID, miktar: int) -> None:
    """Önbelleğe `miktar` ekler (negatif = düşer). Koşulsuz: koşullu düşüm yalnız `rezerve`de."""
    db.execute(update(Kullanici).where(_sahibin(kullanici_id))
               .values(bakiye=Kullanici.bakiye + miktar))


def _isin_hareketleri(db: Session, is_id: uuid.UUID) -> dict[str, KrediHareketi]:
    """Bir işin satırları tür → satır (`ix_kredi_hareketleri_is`); iş başına her türden en çok bir satır (anahtar UNIQUE)."""
    return {h.tur: h for h in db.scalars(select(KrediHareketi).where(KrediHareketi.is_id == is_id))}


# ─────────────────────────────────────────────────── kullanıcı tarafı

def bakiye(db: Session, kullanici_id: uuid.UUID) -> int:
    """Önbellekten (`kullanicilar.bakiye`); satır yoksa 0."""
    return int(db.scalar(select(Kullanici.bakiye).where(_sahibin(kullanici_id))) or 0)


def hibe(db: Session, kullanici_id: uuid.UUID, miktar: int, anahtar: str, aciklama: str | None = None, *,
         an: dt.datetime | None = None) -> bool:
    """`hibe` satırı `+miktar` (anahtar çağıranın: `hibe:<u>:<YYYY-MM>`) + bakiye `+miktar`; `False` = zaten vardı.

    Aylık hibe (3. görev, K6 "hibeye tamamla") ve kayıt hibesi çağırır;
    ikisi de bakım turunda tekrar tekrar koşar — `ON CONFLICT` tekrarı no-op yapar.
    """
    if miktar <= 0:
        raise ValueError(f"hibe pozitif olmali: {miktar}")
    satir = _yaz(db, kullanici_id=kullanici_id, tur=TUR_HIBE, miktar=miktar, anahtar=anahtar,
                 aciklama=aciklama, an=an)
    if satir is None:
        return False
    _bakiye_ekle(db, kullanici_id, miktar)
    return True


def rezerve(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID, miktar: int, *,
            an: dt.datetime | None = None) -> Hareket:
    """Tahmini düşer — ATOMİK (`WHERE bakiye >= :m`); yetmezse `YetersizBakiye`, satır YAZILMAZ.

    Rota çağırır (kullanıcının bağlamı, `sahip`; `kuyruk.ekle` ile aynı
    transaksiyon — 2. görev). Aynı iş için ikinci çağrı (anahtar `rezerv:<is_id>`
    çakışır) düşümü geri alır ve var olan satırı döner: iş iki kez rezerve
    edilmez, bakiye iki kez düşmez.
    """
    if miktar < 0:
        raise ValueError(f"rezerv negatif olamaz: {miktar}")
    sonuc = db.execute(update(Kullanici)
                       .where(_sahibin(kullanici_id), Kullanici.bakiye >= miktar)
                       .values(bakiye=Kullanici.bakiye - miktar))
    if _etkilenen(sonuc) == 0:
        raise YetersizBakiye(bakiye(db, kullanici_id), miktar)
    satir = _yaz(db, kullanici_id=kullanici_id, tur=TUR_REZERV, miktar=-miktar,
                 anahtar=f"{ONEK_REZERV}{is_id}", is_id=is_id, an=an)
    if satir is None:
        _bakiye_ekle(db, kullanici_id, miktar)
        return _hareket(_isin_hareketleri(db, is_id)[TUR_REZERV])
    return _hareket(satir)


def hareketler(db: Session, kullanici_id: uuid.UUID, *, limit: int = 20) -> list[Hareket]:
    """Kullanıcının son hareketleri, EN YENİ ÜSTTE (`ix_kredi_hareketleri_kullanici_olusturuldu`); `_json` ile dökülür."""
    sorgu = (select(KrediHareketi).where(KrediHareketi.kullanici_id == kullanici_id)
             .order_by(KrediHareketi.olusturuldu.desc(), KrediHareketi.id).limit(limit))
    return [_hareket(h) for h in db.scalars(sorgu)]


# ─────────────────────────────────────────────────────── işçi tarafı

def onayla(db: Session, is_id: uuid.UUID, gercek: int, *, an: dt.datetime | None = None) -> Hareket | None:
    """İş bitti: rezervi gerçekle kapatır, farkı iade eder (`onay:<is_id>`); rezerv yoksa ya da kapanmışsa `None`.

    İşçi `kuyruk.bitir`le aynı commit'te çağırır (2. görev). `gercek` ≥ 0
    (Σ `medya.credits`). Aşım (`gercek > tahmin`) ek tahsilat DEĞİL uyarı:
    tahmin üst sınır olmalıydı, sapma raporda görünsün (modül başı).
    """
    if gercek < 0:
        raise ValueError(f"gercek negatif olamaz: {gercek}")
    isin = _isin_hareketleri(db, is_id)
    rezerv = isin.get(TUR_REZERV)
    if rezerv is None or TUR_ONAY in isin or TUR_IADE in isin:
        return None
    tahmin = -rezerv.miktar
    fark = tahmin - gercek
    if fark < 0:
        gunluk.olay(_gunluk, "defter.asim", "gercek maliyet tahmini asti", seviye=logging.WARNING,
                    is_id=str(is_id), kullanici_id=str(rezerv.kullanici_id), tahmin=tahmin, gercek=gercek)
    satir = _yaz(db, kullanici_id=rezerv.kullanici_id, tur=TUR_ONAY, miktar=max(fark, 0),
                 anahtar=f"{ONEK_ONAY}{is_id}", is_id=is_id, an=an)
    if satir is None:
        return None
    if fark > 0:
        _bakiye_ekle(db, rezerv.kullanici_id, fark)
    return _hareket(satir)


def iade(db: Session, is_id: uuid.UUID, *, an: dt.datetime | None = None) -> Hareket | None:
    """Rezervin TAMAMI geri (`iade:<is_id>`); onay ya da iade zaten varsa, rezerv yoksa `None` (idempotent).

    Hata, iptal ve bayat düşürme çağırır (2. görev) — ikisi aynı işi ikinci
    kez düşürebilir, ikinci çağrı satır yazmaz, bakiye oynamaz.
    """
    isin = _isin_hareketleri(db, is_id)
    rezerv = isin.get(TUR_REZERV)
    if rezerv is None or TUR_ONAY in isin or TUR_IADE in isin:
        return None
    satir = _yaz(db, kullanici_id=rezerv.kullanici_id, tur=TUR_IADE, miktar=-rezerv.miktar,
                 anahtar=f"{ONEK_IADE}{is_id}", is_id=is_id, an=an)
    if satir is None:
        return None
    _bakiye_ekle(db, rezerv.kullanici_id, -rezerv.miktar)
    return _hareket(satir)


# ────────────────────────────────────────────────────── admin ve bakım

def duzelt(db: Session, hedef_id: uuid.UUID, miktar: int, aciklama: str | None, admin_id: uuid.UUID, *,
           anahtar: str | None = None, an: dt.datetime | None = None) -> Hareket:
    """Admin düzeltmesi: `duzeltme` satırı (`admin_id` izi) + bakiye `+miktar`; NEGATİF bakiyeye inebilir — bilerek.

    Admin bağlamında (`yonetici_ekler`, K4); kapı yok, iz var. `anahtar`
    verilmezse `duzeltme:<uuid4>` (her çağrı yeni satır); verilmiş ve zaten
    varsa var olan satır döner, bakiye oynamaz (rota yeniden denemesi).
    """
    anahtar = anahtar if anahtar is not None else f"{ONEK_DUZELTME}{uuid.uuid4()}"
    satir = _yaz(db, kullanici_id=hedef_id, tur=TUR_DUZELTME, miktar=miktar, anahtar=anahtar,
                 aciklama=aciklama, admin_id=admin_id, an=an)
    if satir is None:
        mevcut = db.scalars(select(KrediHareketi)
                            .where(KrediHareketi.idempotency_anahtari == anahtar)).one()
        return _hareket(mevcut)
    _bakiye_ekle(db, hedef_id, miktar)
    return _hareket(satir)


def tutarlilik(db: Session) -> list[tuple[uuid.UUID, int, int]]:
    """Önbellek ↔ defter: `bakiye != SUM(miktar)` olan kullanıcılar `(kullanici_id, bakiye, toplam)` — ÖLÇER, düzeltmez.

    Bakım turu (7. görev) çağırır, fark varsa `WARNING olay=defter.tutarsiz`;
    düzeltme admin `duzelt`. Hareketi olmayan kullanıcı toplam 0 sayılır (LEFT
    JOIN): bakiyesi 0 değilse o da sapmadır. Bütün kiracılar — admin bağlamı.
    """
    toplamlar = (select(KrediHareketi.kullanici_id, func.sum(KrediHareketi.miktar).label("toplam"))
                 .group_by(KrediHareketi.kullanici_id).subquery())
    toplam = func.coalesce(toplamlar.c.toplam, 0)
    satirlar = db.execute(select(Kullanici.id, Kullanici.bakiye, toplam)
                          .outerjoin(toplamlar, toplamlar.c.kullanici_id == Kullanici.id)
                          .where(Kullanici.bakiye != toplam)
                          .order_by(Kullanici.id)).all()
    return [(kid, int(b), int(t)) for kid, b, t in satirlar]
