# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Admin sorguları — kullanıcı listesi, kuyruk görünümü, metrikler, tavan, plan, iptal (Faz 2 / 8; plan Faz 3 / 3).

BU DEPONUN KULLANICI SÜZGECİ YOK ve bu bilinçli: admin her kiracının satırını
görür. Öteki depoların `(db, kullanici_id, …)` sözleşmesini (bekçisi
tests/test_galeri_db.py) bu modül TAŞIMAZ ve o bekçinin `KIRACISIZ_MODULLER`
defterine GEREKÇESİYLE yazılıdır: hedef kullanıcı bir parametre olduğunda adı
`hedef_id`dir, `kullanici_id` değil — "bu sorgu kimin adına" sorusunun cevabı
burada satırın sahibi değil, isteği yapan ADMİN'dir ve onu rota kapısı
(`kimlik.admin_kullanici`) çözer.

İKİNCİ KAT BURADA DA İŞLER: RLS politikası (`0006_rls`) `app.rol = 'admin'`
bağlamı olmadan bu sorgulara başkasının satırını GÖSTERMEZ — hata değil, boş
sonuç (docs/faz2-kuyruk-anahtarlar-depolama.md §7, kırılma sınıfı (a)). Yani
bu modülün bir işlevini admin kapısından geçmeyen bir yerden çağırmak
sızıntı değil, sessiz bir boşluk üretir; tests/test_admin.py bunu uygulama
rolüyle iki yönden ölçer (bağlamsız boş, kapılı rota dolu). Admin politikası
SELECT ve UPDATE verir, INSERT/DELETE vermez — bu modül de yalnız okur ve
günceller (`tavan_yaz` `kullanicilar`da, o tablo politikasız; `is_iptal`
`isler`de UPDATE). Oturum düşürme `services/hesap.oturumlari_dusur`da kalır:
`oturumlar` hesap tablosu, politikasız, silme oradan.

METRİKLER `isler`DEN TÜRETİLİR, Prometheus yok (belge §8): kuyruk derinliği,
en eski bekleyenin yaşı, son 1 sa / 24 sa iş ve hata sayısı, model başına
p50/p95 süre (`percentile_cont` … `WITHIN GROUP`, `bitti - basladi` saniye),
son 24 sa platform kredisi, `isciler` (son kalp `CANLI_ESIK` içindeyse canlı —
işçi 30 sn'de bir atıyor, üç kaçırılan kalp bayat sayılır). Sayılar zaten
DB'de; ikinci bir metrik deposu Faz 5'in ölçeğinde değil.

ZAMAN PARAMETRE (`an`): `kota.py`nin aynı kararı — testler saatle oynamaz,
`an` verir; pencere sınırı `>` (dâhil değil). Konuşmaz: cümle yok, sözlük
döner; 404/409 metnini rota kurar (`services/db.py`nin `database_unavailable`
kararı). İş satırının dökümü `kuyruk._json` — kullanıcının gördüğüyle AYNI
biçim (`istek` yine dökülmez: admin de prompt'u görmez, galeriden görür) +
`kullanici_id`/`eposta` (admin kimin işi olduğunu bilmek zorunda).
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Select, case, func, select, update
from sqlalchemy.orm import Session

from services import kota, kuyruk, platform_anahtari, zaman
from services.tablolar import (
    DURUM_BEKLIYOR,
    DURUM_BITTI,
    DURUM_CALISIYOR,
    DURUM_HATA,
    DURUM_IPTAL,
    Is,
    Isci,
    Kullanici,
    Oturum,
)

__all__ = ["CANLI_ESIK", "SAYFA_ADEDI", "SAYFA_ADEDI_AZAMI", "IS_LISTESI_SINIRI",
           "kullanicilar", "kullanici_bul", "oturum_sayisi", "tavan_yaz", "plan_yaz",
           "is_listesi", "is_satiri", "is_iptal", "is_dokumu", "metrikler"]

# İşçi kalbi 30 sn (services/isci.py); üç kaçırılan kalp = bayat. Bayat işçi
# satırı listede KALIR (admin "kim kaldı" sorusunu buradan okur), yalnız `canli` düşer.
CANLI_ESIK = dt.timedelta(seconds=90)
# Kullanıcı listesi sayfası: öntanımlı 50, en çok 200 (belge: "sayfalı, `?q=`").
SAYFA_ADEDI = 50
SAYFA_ADEDI_AZAMI = 200
# Kuyruk görünümü: son 200 iş (belge §8).
IS_LISTESI_SINIRI = 200

_BIR_SAAT = dt.timedelta(hours=1)
_BIR_GUN = dt.timedelta(hours=24)


def _damga(t: dt.datetime | None) -> str | None:
    """Dilimli UTC (`Z`), `kuyruk._json`la aynı (Faz 2 / 10): admin.js süreyi `new Date(basladi)`
    ile hesaplar ve dilimsiz dize tarayıcının dilimi kadar yanlış süre veriyordu."""
    return zaman.damga_utc(t) if t is not None else None


def _saniye(baslangic: dt.datetime | None, an: dt.datetime) -> int | None:
    return max(0, int((an - baslangic).total_seconds())) if baslangic is not None else None


# ─────────────────────────────────────────────────────────── kullanıcılar

def _kullanici_sorgusu(q: str | None) -> Select:
    sorgu = select(Kullanici).where(Kullanici.silindi_at.is_(None))
    if q:
        # citext sütunda ILIKE gereksiz ama zararsız; `%`/`_` kaçırılıyor ki
        # arama metni joker değil düz metin olsun.
        kalip = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sorgu = sorgu.where(Kullanici.eposta.ilike(kalip, escape="\\"))
    return sorgu


def kullanicilar(db: Session, *, q: str | None = None, sayfa: int = 1, adet: int = SAYFA_ADEDI,
                 an: dt.datetime | None = None) -> tuple[list[dict[str, Any]], int]:
    """Kullanıcı sayfası (en yeni üstte) ve toplam sayı; `q` e-postada geçen metin.

    Her satırda üç türetilmiş alan, üçü de korelasyonlu alt sorgu (tek gidiş-dönüş,
    sayfa 50 satır): `son_gorulme` (oturumların en yenisi), `kredi_24sa` (son 24
    saatte PLATFORM anahtarıyla sıraya alınan tahmin, `iptal` hariç —
    `kota.gunluk_durum`un aynı süzgeci) ve `aktif_is` (bekliyor + calisiyor).
    `plan` ve `bakiye` (Faz 3 / 3) satırın kendi sütunları: admin plan seçiciyi ve
    "kredi ekle" alanını bunlardan kurar; `bakiye` defterin önbelleği (`defter.bakiye`
    ile aynı sütun, ikinci bir SUM yok).
    """
    an = an if an is not None else zaman.an()
    sayfa = max(1, sayfa)
    adet = max(1, min(adet, SAYFA_ADEDI_AZAMI))
    son_gorulme = (select(func.max(Oturum.son_gorulme))
                   .where(Oturum.kullanici_id == Kullanici.id).scalar_subquery())
    kredi = (select(func.coalesce(func.sum(Is.kredi_tahmini), 0))
             .where(Is.kullanici_id == Kullanici.id, Is.durum != DURUM_IPTAL,
                    Is.anahtar_kaynagi == platform_anahtari.KAYNAK_PLATFORM,
                    Is.olusturuldu > an - kota.GUNLUK_PENCERE).scalar_subquery())
    aktif = (select(func.count()).select_from(Is)
             .where(Is.kullanici_id == Kullanici.id, Is.durum.in_(kuyruk.AKTIF_DURUMLAR))
             .scalar_subquery())
    taban = _kullanici_sorgusu(q)
    toplam = int(db.scalar(select(func.count()).select_from(taban.subquery())) or 0)
    satirlar = db.execute(
        taban.add_columns(son_gorulme.label("son_gorulme"), kredi.label("kredi_24sa"),
                          aktif.label("aktif_is"))
        .order_by(Kullanici.olusturuldu.desc(), Kullanici.id)
        .offset((sayfa - 1) * adet).limit(adet)).all()
    return [{
        "id": str(k.id),
        "eposta": k.eposta,
        "is_admin": k.is_admin,
        "dogrulandi": k.dogrulandi_at is not None,
        "olusturuldu": _damga(k.olusturuldu),
        "son_gorulme": _damga(son),
        "gunluk_kredi_tavani": k.gunluk_kredi_tavani,
        "kredi_24sa": int(kredi_24sa or 0),
        "aktif_is": int(aktif_is or 0),
        "plan": k.plan,
        "bakiye": int(k.bakiye),
    } for k, son, kredi_24sa, aktif_is in satirlar], toplam


def kullanici_bul(db: Session, hedef_id: uuid.UUID) -> Kullanici | None:
    """Silinmemiş kullanıcı satırı; yoksa `None` (rota 404 kurar)."""
    return db.scalar(select(Kullanici).where(Kullanici.id == hedef_id,
                                             Kullanici.silindi_at.is_(None)))


def oturum_sayisi(db: Session, hedef_id: uuid.UUID) -> int:
    """Kullanıcının açık oturum satırı sayısı — düşürmeden önce, cevap "kaç oturum düştü" desin."""
    return int(db.scalar(select(func.count()).select_from(Oturum)
                         .where(Oturum.kullanici_id == hedef_id)) or 0)


def tavan_yaz(db: Session, hedef_id: uuid.UUID, tavan: int | None) -> bool:
    """`kullanicilar.gunluk_kredi_tavani` yaz (sayı) ya da sil (`None` = ortamın öntanımlısı); satır yoksa `False`.

    `kullanicilar` politikasız (hesap tablosu): DB katı bunu kısıtlamaz, kapı
    rotadaki `admin_kullanici`dır (belge §7 devri, madde 2). 6. görevin kotası
    (`kota.check_gunluk`) bir sonraki istekte bu değeri okur.
    """
    sonuc = db.execute(update(Kullanici)
                       .where(Kullanici.id == hedef_id, Kullanici.silindi_at.is_(None))
                       .values(gunluk_kredi_tavani=tavan))
    return kuyruk._etkilenen(sonuc) > 0


def plan_yaz(db: Session, hedef_id: uuid.UUID, plan: str) -> bool:
    """`kullanicilar.plan` yaz (Faz 3 / 3; `PLANLAR_KUMESI`nden biri — rota doğrular, CHECK son kapı); satır yoksa `False`.

    `tavan_yaz`ın ikizi: hesap tablosu politikasız, kapı rotadaki
    `admin_kullanici`. Kullanıcının bir sonraki isteği yeni planı okur
    (`kapilar.check_plan`, `modeller.settings_payload`); bakiyeye DOKUNMAZ —
    planın hibesi bakım turunda tamamlanır (K6), anında para yok.
    """
    sonuc = db.execute(update(Kullanici)
                       .where(Kullanici.id == hedef_id, Kullanici.silindi_at.is_(None))
                       .values(plan=plan))
    return kuyruk._etkilenen(sonuc) > 0


# ─────────────────────────────────────────────────────────────── kuyruk

def is_dokumu(is_: Is, eposta: str | None = None) -> dict[str, Any]:
    """Kullanıcının gördüğü `kuyruk._json` + sahibi (`kullanici_id`, `eposta`); `istek` yine dökülmez."""
    return {**kuyruk._json(is_), "kullanici_id": str(is_.kullanici_id), "eposta": eposta}


def is_listesi(db: Session, *, durum: str | None = None, limit: int = IS_LISTESI_SINIRI,
               an: dt.datetime | None = None) -> dict[str, Any]:
    """Son `limit` iş (en yeni üstte, `durum` süzgeçli) + özet: bekleyen/çalışan/son 24 sa hata, en eski bekleyenin yaşı."""
    an = an if an is not None else zaman.an()
    sorgu = (select(Is, Kullanici.eposta)
             .join(Kullanici, Kullanici.id == Is.kullanici_id, isouter=True))
    if durum:
        sorgu = sorgu.where(Is.durum == durum)
    satirlar = db.execute(sorgu.order_by(Is.olusturuldu.desc()).limit(max(1, limit))).all()
    bekleyen, calisan, hata_24sa, en_eski = db.execute(
        select(func.count(case((Is.durum == DURUM_BEKLIYOR, 1))),
               func.count(case((Is.durum == DURUM_CALISIYOR, 1))),
               func.count(case(((Is.durum == DURUM_HATA) & (Is.bitti > an - _BIR_GUN), 1))),
               func.min(case((Is.durum == DURUM_BEKLIYOR, Is.olusturuldu))))).one()
    return {
        "isler": [is_dokumu(i, e) for i, e in satirlar],
        "ozet": {"bekleyen": int(bekleyen or 0), "calisan": int(calisan or 0),
                 "hata_24sa": int(hata_24sa or 0),
                 "en_eski_bekleyen_sn": _saniye(en_eski, an)},
    }


def is_satiri(db: Session, is_id: uuid.UUID) -> Is | None:
    """Herhangi bir kullanıcının iş satırı; yoksa `None` (rota 404 kurar)."""
    return db.scalar(select(Is).where(Is.id == is_id))


def is_iptal(db: Session, is_id: uuid.UUID, *, an: dt.datetime | None = None) -> bool:
    """Sahip süzgeçsiz iptal: yalnız `bekliyor` iş — `kuyruk.iptal`ın admin ikizi, aynı `WHERE durum` kararı.

    Çalışan iş burada da İPTAL EDİLMEZ (K8): sağlayıcı çağrısı gitti, faturalandı;
    işçi sonucu yazar. RLS'te `yonetici_gunceller` bu UPDATE'i geçirir.
    """
    sonuc = db.execute(update(Is).where(Is.id == is_id, Is.durum == DURUM_BEKLIYOR)
                       .values(durum=DURUM_IPTAL, bitti=an if an is not None else zaman.an()))
    return kuyruk._etkilenen(sonuc) > 0


# ───────────────────────────────────────────────────────────── metrikler

def _pencereler(db: Session, an: dt.datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Son 1 sa ve son 24 sa: sıraya alınan iş (iptal hariç) ve hatayla kapanan sayısı, oran hata/iş — TEK sorgu."""
    saat = Is.olusturuldu > an - _BIR_SAAT
    satir = db.execute(
        select(func.count(case((saat, 1))), func.count(case((saat & (Is.durum == DURUM_HATA), 1))),
               func.count(), func.count(case((Is.durum == DURUM_HATA, 1))))
        .where(Is.durum != DURUM_IPTAL, Is.olusturuldu > an - _BIR_GUN)).one()

    def _ozet(is_sayisi: int, hata: int) -> dict[str, Any]:
        return {"is": is_sayisi, "hata": hata,
                "hata_orani": round(hata / is_sayisi, 4) if is_sayisi else 0.0}
    return _ozet(int(satir[0] or 0), int(satir[1] or 0)), _ozet(int(satir[2] or 0), int(satir[3] or 0))


def metrikler(db: Session, an: dt.datetime | None = None) -> dict[str, Any]:
    """`GET /api/admin/metrikler` gövdesi — beş sorgu, hepsi `isler`/`isciler` (belge §8)."""
    an = an if an is not None else zaman.an()
    bekleyen, calisan, en_eski = db.execute(
        select(func.count(case((Is.durum == DURUM_BEKLIYOR, 1))),
               func.count(case((Is.durum == DURUM_CALISIYOR, 1))),
               func.min(case((Is.durum == DURUM_BEKLIYOR, Is.olusturuldu))))
        .where(Is.durum.in_(kuyruk.AKTIF_DURUMLAR))).one()
    platform_kredi = db.scalar(
        select(func.coalesce(func.sum(Is.kredi_tahmini), 0))
        .where(Is.durum != DURUM_IPTAL, Is.anahtar_kaynagi == platform_anahtari.KAYNAK_PLATFORM,
               Is.olusturuldu > an - _BIR_GUN))
    # `percentile_cont(p) WITHIN GROUP (ORDER BY extract(epoch FROM bitti - basladi))`:
    # son 24 saatte BİTEN işler, model başına. `basladi` NULL olan satır (ham
    # SQL'le kapanmış) süreye girmez.
    sure = func.extract("epoch", Is.bitti - Is.basladi)
    modeller = db.execute(
        select(Is.model, func.count(),
               func.percentile_cont(0.5).within_group(sure),
               func.percentile_cont(0.95).within_group(sure))
        .where(Is.durum == DURUM_BITTI, Is.basladi.is_not(None), Is.bitti > an - _BIR_GUN)
        .group_by(Is.model).order_by(func.count().desc(), Is.model)).all()
    isciler = db.scalars(select(Isci).order_by(Isci.basladi)).all()
    son_1sa, son_24sa = _pencereler(db, an)
    return {
        "an": zaman.damga_utc(an),
        "kuyruk": {"derinlik": int(bekleyen or 0), "calisan": int(calisan or 0),
                   "en_eski_bekleyen_sn": _saniye(en_eski, an)},
        "son_1sa": son_1sa,
        "son_24sa": {**son_24sa, "platform_kredi": int(platform_kredi or 0)},
        "modeller": [{"model": m, "adet": int(n), "p50_sn": round(float(p50), 2),
                      "p95_sn": round(float(p95), 2)} for m, n, p50, p95 in modeller],
        "isciler": [{"id": str(i.id), "konak": i.konak, "surum": i.surum,
                     "es_zamanli": i.es_zamanli, "basladi": _damga(i.basladi),
                     "son_kalp": _damga(i.son_kalp), "canli": i.son_kalp > an - CANLI_ESIK}
                    for i in isciler],
    }

