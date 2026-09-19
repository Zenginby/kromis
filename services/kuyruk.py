# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İş kuyruğu ilkelleri — `isler` ve `isciler` üstünde saf `(db, …)` işlevler (Faz 2 / 1. görev).

KUYRUK POSTGRES'İN KENDİSİ (docs/faz2-kuyruk-anahtarlar-depolama.md §1, K1):
iş listesi, durum ucu, 30 günlük geçmiş ve admin görünümü zaten KALICI bir
`isler` satırı istiyor; Redis o satırın yanına ikinci bir doğruluk kaynağı
koyardı ("Redis'te var, DB'de yok" tutarsızlık sınıfı). Hacim dakikada
onlarca iş, saniyede binlerce değil; `FOR UPDATE SKIP LOCKED` bu hacmin
yüzlerce katını tek Postgres'te kaldırır. Arayüz arka uçtan bağımsız:
ölçüm bir gün Redis'i haklı çıkarırsa `kuyruk_redis.py` AYNI imzalarla gelir,
rotalar (4) ve işçi (3) değişmez.

İKİ TARAF, İKİ İMZA. Kullanıcı tarafı (`ekle`, `iptal`, `aktif_sayisi`,
`listele`) depo modüllerinin `(db, kullanici_id, …)` deyimini ve HER sorguda
`kullanici_id` süzgecini taşır (bekçisi tests/test_galeri_db.py). İşçi tarafı
(`al`, `kalp`, `bitir`, `dusur`, `bayatlari_dusur`, `isci_*`) kiracısız ve
bilerek: işçi platformun, kimsenin değil — `al` kuyruğun BAŞINI alır, kimin
işi olduğuna bakmaz (küresel FIFO); sonraki üçü işi kimliğiyle sürer.
Kullanıcı bir işe yalnız kendi id'siyle dokunur, işçi yalnız elindeki iş
id'siyle; iki taraf aynı satıra aynı anda dokunmaz, çünkü iptal yalnız
`bekliyor`u, işçi işlevleri yalnız `calisiyor`u değiştirir.

DURUM GEÇİŞLERİ `WHERE`DE, uygulamada değil: `bitir`/`dusur`/`kalp` yalnız
`calisiyor` satırı, `iptal` yalnız `bekliyor` satırı değiştirir; başka bir
durumdan gelen çağrı 0 satır etkiler ve `False` döner. Böylece yarış
Postgres'in satır kilidinde çözülür — bayat düşürülmüş (`hata`) bir işi geç
kalan işçi `bitti`ye çeviremez, iptal edilmiş işi işçi alamaz (zaten
`bekliyor` değil). `hata`dan kuyruğa GERİ DÖNÜŞ YOK (K8): sağlayıcı çağrısı
gidip gitmediği bilinemez, yeniden deneme çift fatura riski; kullanıcı
panelden yeniden gönderir.

ZAMAN PARAMETRE (`an`), Python'dan: `zaman.an()` mikrosaniyeli ve sıralanabilir
(Faz 1 / 5 kararı) — aynı saniyede sıraya giren dört iş FIFO'yu korur; testler
saatle oynamaz, `an` verir (`hesap.simdi()` deseni). `ekle` `an` almadan da
çağrılabilir (rota `zaman.an()` demek zorunda kalmasın).

KONUŞMAZ: kullanıcıya cümle yok. `hata` sütununa yazılan metin sağlayıcı
hatasının `errlog.redact_secrets`ten geçmiş hâli (redaksiyon YAZAN yerde,
çağıranda değil — unutulacak yer bir tane olsun) ve `BAYAT_HATASI` bir KOD
(ASCII), cümleyi ön yüz kurar (`services/db.py`nin `database_unavailable`
kararı). `_json` `istek`i DÖKMEZ: prompt ve klasör zaten `medya`da, referans
görsellerin anahtarları iç iş.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Connection, delete, func, select, update
from sqlalchemy.orm import Session

import errlog
from services import zaman
from services.tablolar import (
    DURUM_BEKLIYOR,
    DURUM_BITTI,
    DURUM_CALISIYOR,
    DURUM_HATA,
    DURUM_IPTAL,
    Is,
    Isci,
)

__all__ = ["ekle", "al", "kalp", "bitir", "dusur", "iptal", "bayatlari_dusur", "bekleyen_ozeti",
           "aktif_sayisi", "listele", "bul", "satir", "isci_kaydet", "isci_kalp", "isci_sil",
           "isci_son_kalp", "BAYAT_HATASI", "AKTIF_DURUMLAR", "KAPANMIS_DURUMLAR"]

# `bayatlari_dusur`un `hata` sütununa yazdığı KOD — cümle değil (gerekçe üstte).
BAYAT_HATASI = "isci yanit vermiyor"

# "Aktif" = kuyrukta ya da işçide; eş zamanlılık sayacı ve kısmi indeks
# `ix_isler_kullanici_aktif` aynı iki değeri sayar.
AKTIF_DURUMLAR: tuple[str, ...] = (DURUM_BEKLIYOR, DURUM_CALISIYOR)
# Sonuçsuz kapanmış işler — "yeniden gönder" (Faz 2 / 5) yalnız bunlardan
# doğar: `bitti` işin sonucu galeride duruyor, ikinci kez koşturmak çift
# fatura (K8); aktif iş zaten sırada.
KAPANMIS_DURUMLAR: tuple[str, ...] = (DURUM_HATA, DURUM_IPTAL)


def _etkilenen(sonuc: object) -> int:
    """`UPDATE`/`DELETE` sonucunun satır sayısı; ORM `Result` tipi `rowcount`u ilan etmiyor."""
    return int(getattr(sonuc, "rowcount", 0) or 0)


def _damga(t: dt.datetime | None) -> str | None:
    return zaman.damga(t) if t is not None else None


def _json(is_: Is) -> dict[str, Any]:
    """Satır → dışarıya dökülen sözlük. `istek` YOK, `isci_id`/`kalp_atisi` YOK (iç iş).

    Anahtarlar sütun adları (Türkçe, ASCII): bu tablo bugünkü hiçbir JSON
    kaydının ikizi değil, koruyacak eski ad yok. Zaman damgaları `medya`nın
    `created_at`iyle aynı biçimde (`zaman.damga`), ön yüz tek sıralama kuralı
    bilsin.

    `arena_id` ve `folder_id` `istek`in İÇİNDEN dökülen İKİ alan (Faz 2 / 5):
    iş paneli aynı turun 2-4 sütununu sekme yenilendikten sonra da gruplayabilsin
    ve biten işin önizlemesini doğru klasörün `GET /api/history`sinden çekebilsin
    (kök yalnız klasörsüzleri veriyor) — ikisi de `medya` kaydında zaten galeriye
    çıkıyor, gizli bir şey değil. Prompt ve girdi anahtarları içeride kalır.
    """
    istek = is_.istek if isinstance(is_.istek, dict) else {}
    return {
        "id": str(is_.id),
        "tur": is_.tur,
        "durum": is_.durum,
        "model": is_.model,
        "kredi_tahmini": is_.kredi_tahmini,
        # Faz 2 / 6: panel "platform anahtarıyla" işaretini, sahibi doğrulamasını buradan okur.
        "anahtar_kaynagi": is_.anahtar_kaynagi,
        "olusturuldu": _damga(is_.olusturuldu),
        "basladi": _damga(is_.basladi),
        "bitti": _damga(is_.bitti),
        "sonuc": is_.sonuc,
        "hata": is_.hata,
        "arena_id": istek.get("arena_id"),
        "folder_id": istek.get("folder_id"),
    }


# ─────────────────────────────────────────────────── kullanıcı tarafı

def ekle(db: Session, kullanici_id: uuid.UUID, tur: str, istek: dict[str, Any], model: str,
         kredi_tahmini: int, *, an: dt.datetime | None = None,
         is_id: uuid.UUID | None = None, anahtar_kaynagi: str | None = None) -> Is:
    """İşi kuyruğa koyar (`bekliyor`); satırı döndürür (`_json` ile dökülür).

    `flush`: CHECK (`tur`), FK ve NOT NULL burada patlasın — rota 202
    döndükten sonra commit'te değil. `kredi_tahmini` çağıranın hesabı
    (`catalog.cost_for` × n): bu modül kataloğu bilmez, sayıyı saklar.

    `is_id` (Faz 2 / 4): rota girdi nesnelerini `kullanicilar/<uuid>/isler/<is_id>/…`
    anahtarına işi YAZMADAN ÖNCE koyar (`istek.girdiler` o anahtarları taşır),
    yani id'yi satırdan önce bilmek zorunda. Verilmezse DB'nin varsayılanı
    (`gen_random_uuid`), bugünkü davranış.

    `anahtar_kaynagi` (Faz 2 / 6): rotanın çözdüğü kaynak (`kullanici` |
    `platform`); günlük kredi tavanı yalnız `platform` satırlarını toplar
    (services/kota.py). Bu modül çözmez, saklar — CHECK bilinmeyen değeri reddeder.
    """
    satir = Is(kullanici_id=kullanici_id, tur=tur, durum=DURUM_BEKLIYOR, istek=istek,
               model=model, kredi_tahmini=kredi_tahmini, anahtar_kaynagi=anahtar_kaynagi,
               olusturuldu=an if an is not None else zaman.an())
    if is_id is not None:
        satir.id = is_id
    db.add(satir)
    db.flush()
    return satir


def iptal(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID, *,
          an: dt.datetime | None = None) -> bool:
    """Yalnız `bekliyor` işi iptal eder; `calisiyor` EDİLMEZ (sağlayıcı çoktan faturalandı).

    Tek `UPDATE … WHERE durum = 'bekliyor'`: işçi aynı anda `al` ile satırı
    kilitlemişse bu ifade onun commit'ini bekler, sonra 0 satır görür →
    `False`. Başkasının işi de 0 satır (`kullanici_id` süzgeci) — rota 404
    kurar, 403 değil (id uzayı sızmasın; depo modüllerinin kararı).
    `bitti` iptal anı: iş listesi "ne zaman kapandı"yı tek sütundan okur.
    """
    sonuc = db.execute(update(Is)
                       .where(Is.kullanici_id == kullanici_id, Is.id == is_id,
                              Is.durum == DURUM_BEKLIYOR)
                       .values(durum=DURUM_IPTAL, bitti=an if an is not None else zaman.an()))
    return _etkilenen(sonuc) > 0


def aktif_sayisi(db: Session, kullanici_id: uuid.UUID) -> int:
    """Kullanıcının `bekliyor` + `calisiyor` işi — 4. görevin eş zamanlılık tavanı buradan sayar."""
    n = db.scalar(select(func.count()).select_from(Is)
                  .where(Is.kullanici_id == kullanici_id, Is.durum.in_(AKTIF_DURUMLAR)))
    return int(n or 0)


def listele(db: Session, kullanici_id: uuid.UUID, *, since: dt.datetime | None = None,
            limit: int = 50, durumlar: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Kullanıcının işleri, EN YENİ ÜSTTE; `since` verilmişse yalnız o andan sonra DEĞİŞENLER.

    "Değişme" = `olusturuldu`/`basladi`/`bitti`nin en büyüğü (`GREATEST` NULL'u
    atlar): SSE'nin `Last-Event-ID`si (5. görev) "şu andan beri ne oldu" diye
    sorar ve bir iş üç anda değişir — sıraya girince, alınınca, kapanınca.
    `kalp_atisi` sayılmaz: istemciye görünen bir şey değiştirmez. `limit`
    çağıranın; öntanımlı 50 iş paneli için, geçmiş sayfalaması 4. görevin.
    `durumlar` (Faz 2 / 4): yalnız bu durumdaki işler — `GET /api/isler`in
    öntanımlı görünümü "aktifler + son 50" ve 51. sıraya düşmüş bir `bekliyor`
    iş listeden kaybolmasın diye aktifler AYRI çekilir (`AKTIF_DURUMLAR`).
    """
    sorgu = select(Is).where(Is.kullanici_id == kullanici_id)
    if since is not None:
        sorgu = sorgu.where(func.greatest(Is.olusturuldu, Is.basladi, Is.bitti) > since)
    if durumlar is not None:
        sorgu = sorgu.where(Is.durum.in_(durumlar))
    sorgu = sorgu.order_by(Is.olusturuldu.desc()).limit(limit)
    return [_json(i) for i in db.scalars(sorgu)]


def satir(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID) -> Is | None:
    """Kullanıcının bir iş SATIRI (ORM), sahip süzgeçli; yoksa/başkasınınsa `None`.

    `bul`dan farkı `istek`i taşıması: "yeniden gönder" (Faz 2 / 5) eski işin
    `istek`ini yeni satıra kopyalar ve o sözlük `_json`la DÖKÜLMEZ — istemci
    hiç görmez, kopya sunucuda kalır. Rota dışına çıkmayan tek çağrı yeri o.
    """
    return db.scalar(select(Is).where(Is.kullanici_id == kullanici_id, Is.id == is_id))


def bul(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID) -> dict[str, Any] | None:
    """Tek iş, `_json` ile; başkasının işi ve olmayan iş aynı `None` (rota 404 kurar, 403 değil)."""
    s = satir(db, kullanici_id, is_id)
    return _json(s) if s is not None else None


# ────────────────────────────────────────────────────── işçi tarafı

def al(db: Session, isci_id: uuid.UUID, an: dt.datetime) -> Is | None:
    """Kuyruğun başındaki işi bu işçiye verir — TEK ifade, iki işçi aynı işi ALAMAZ.

        UPDATE isler SET durum='calisiyor', isci_id=:isci, basladi=:an, kalp_atisi=:an
         WHERE id = (SELECT id FROM isler WHERE durum='bekliyor'
                     ORDER BY olusturuldu FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING *

    `FOR UPDATE SKIP LOCKED`: ikinci işçi, birincisinin henüz commit'lemediği
    satırı BEKLEMEZ, atlar ve sıradakini alır — bekleseydi commit'ten sonra
    aynı satırı görür, `durum` artık `bekliyor` olmadığı için 0 satır alırdı
    (doğru ama boşa bir tur); `SKIP LOCKED` bunu da, kilit kuyruğunu da
    kaldırır. Alt sorgu yalnız `bekliyor` tarar (kısmi indeks `ix_isler_kuyruk`),
    sıra `olusturuldu` (FIFO, mikrosaniye). Kuyruk boşsa `None`. Çağıran
    commit'ler; commit'e kadar satır kilitli kalır, bu istenen şey (işçi
    düşerse satır `bekliyor` kalır, kayıp yok).
    """
    siradaki = (select(Is.id).where(Is.durum == DURUM_BEKLIYOR)
                .order_by(Is.olusturuldu).limit(1)
                .with_for_update(skip_locked=True).scalar_subquery())
    ifade = (update(Is).where(Is.id == siradaki)
             .values(durum=DURUM_CALISIYOR, isci_id=isci_id, basladi=an, kalp_atisi=an)
             .returning(Is))
    # `populate_existing`: aynı `Session` bu satırı önceden `bekliyor` olarak
    # yüklemişse kimlik haritasındaki bayat kopya değil RETURNING'in dediği dönsün.
    return db.scalars(ifade.execution_options(populate_existing=True)).one_or_none()


def kalp(db: Session, is_id: uuid.UUID, an: dt.datetime) -> bool:
    """İşçi 30 sn'de bir: `kalp_atisi = an`. `False` = iş artık `calisiyor` değil (bayat düşürüldü)."""
    sonuc = db.execute(update(Is).where(Is.id == is_id, Is.durum == DURUM_CALISIYOR)
                       .values(kalp_atisi=an))
    return _etkilenen(sonuc) > 0


def bitir(db: Session, is_id: uuid.UUID, sonuc: dict[str, Any], an: dt.datetime) -> bool:
    """`calisiyor` → `bitti`, `sonuc` (`{"medya": [id, …]}`) ve `bitti = an`. Başka durumdan 0 satır → `False`.

    `False` işçi için bir sinyal: iş bu arada bayat sayılıp `hata`ya düşmüş
    (kalp 5 dk susmuş) — sonuç satıra yazılamaz, işçi ürettiği nesneyi siler
    (telafi, 3. görev). Yeniden kuyruğa almaz (K8).
    """
    etkilenen = db.execute(update(Is).where(Is.id == is_id, Is.durum == DURUM_CALISIYOR)
                           .values(durum=DURUM_BITTI, sonuc=sonuc, bitti=an))
    return _etkilenen(etkilenen) > 0


def dusur(db: Session, is_id: uuid.UUID, hata: str, an: dt.datetime) -> bool:
    """`calisiyor` → `hata`; metin `errlog.redact_secrets`ten geçer (sağlayıcı hatası anahtar taşıyabilir)."""
    sonuc = db.execute(update(Is).where(Is.id == is_id, Is.durum == DURUM_CALISIYOR)
                       .values(durum=DURUM_HATA, hata=errlog.redact_secrets(hata), bitti=an))
    return _etkilenen(sonuc) > 0


def bayatlari_dusur(db: Session, an: dt.datetime, esik: dt.timedelta) -> int:
    """Kalbi `esik`ten uzun susan `calisiyor` işler → `hata` (`BAYAT_HATASI`); düşürülen sayı.

    Yeniden KUYRUĞA ALMAZ (K8): işçi sağlayıcıyı çağırmış olabilir ve çağrı
    faturalanmıştır; ikinci deneme çift fatura. `bitti = an`: iş kapandı,
    kullanıcı panelden yeniden gönderir. 10. görevin periyodik bakımı ve
    işçinin kendi döngüsü (3) çağırır; `esik` çağıranın (öneri 5 dk, K8).
    """
    sonuc = db.execute(update(Is)
                       .where(Is.durum == DURUM_CALISIYOR, Is.kalp_atisi < an - esik)
                       .values(durum=DURUM_HATA, hata=BAYAT_HATASI, bitti=an))
    return _etkilenen(sonuc)


def bekleyen_ozeti(db: Session, an: dt.datetime) -> tuple[int, int | None]:
    """Kuyruk derinliği (`bekliyor` sayısı) ve en eski bekleyenin yaşı (sn; kuyruk boşsa `None`) — TEK sorgu.

    İşçinin kalp turu (services/isci.py `kuyruk_uyarisi`, Faz 2 / 9) 30 sn'de
    bir sorar ve `isletme.md` § 6 eşiklerini aşınca `uyari` olayı düşürür;
    admin metrikleri aynı iki sayıyı `depo_admin.metrikler`de `calisan`la
    birlikte hesaplar. Bütün kiracıların işi: çağıran `app.rol='admin'`
    bağlamında koşar (kalp turuyla aynı transaksiyon), yoksa RLS 0 döner.
    """
    derinlik, en_eski = db.execute(
        select(func.count(), func.min(Is.olusturuldu)).where(Is.durum == DURUM_BEKLIYOR)).one()
    yas = int((an - en_eski).total_seconds()) if en_eski is not None else None
    return int(derinlik or 0), yas


def isci_kaydet(db: Session, konak: str, surum: str, es_zamanli: int, an: dt.datetime) -> Isci:
    """İşçi açılışta: kendi satırı (`basladi = son_kalp = an`); `id` DB'den, işçi onu `al`a taşır."""
    satir = Isci(konak=konak, surum=surum, es_zamanli=es_zamanli, basladi=an, son_kalp=an)
    db.add(satir)
    db.flush()
    return satir


def isci_son_kalp(db: Session | Connection) -> dt.datetime | None:
    """Bütün işçilerin EN SON kalbi; satır yoksa `None` — `/health` `worker_alive` bunu `CANLI_ESIK`le okur.

    `Connection` de alır: sonda (`routers/saglik.py`) `Session` açmaz, `SELECT 1`
    ile aynı bağlantıda sorar. `isciler` politikasız, bağlam gerekmez.
    """
    return db.execute(select(func.max(Isci.son_kalp))).scalar_one()


def isci_kalp(db: Session, isci_id: uuid.UUID, an: dt.datetime) -> bool:
    """30 sn'de bir `son_kalp = an`; `False` = satır yok (admin düşürmüş ya da kayıt hiç olmamış)."""
    sonuc = db.execute(update(Isci).where(Isci.id == isci_id).values(son_kalp=an))
    return _etkilenen(sonuc) > 0


def isci_sil(db: Session, isci_id: uuid.UUID) -> bool:
    """Kapanışta satır silinir; `isler.isci_id` kalır (FK yok — "kim koştu" kaydı durur)."""
    sonuc = db.execute(delete(Isci).where(Isci.id == isci_id))
    return _etkilenen(sonuc) > 0
