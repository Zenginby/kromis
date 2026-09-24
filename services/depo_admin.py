# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
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

KREDİ SAYIMI GERÇEKLE (Faz 3 / 5): `platform_kredi` ve `kredi_24sa`
`SUM(COALESCE(kredi_gercek, kredi_tahmini))` — biten işte GERÇEK (Σ
`medya.credits`, 2. görev), henüz bitmemiş ya da düşmüş işte REZERV (gerçek
yok; düşen iş K8 gereği faturalanmış olabilir, tahmin en iyi bilgi). Salt
`SUM(kredi_gercek)` yoğun bir saatte "0" gösterirdi. Tahminin toplamı
`platform_kredi_rezerv` olarak yanında durur ("rezerv edilen").

MARJ (`marj`, Faz 3 / 5): model başına, `gun` günlük pencerede kapanan işler
— iş sayısı, Σ `kredi_gercek`, ≈ USD (× `catalog.KREDI_USD_CAPASI`), Σ
`saglayici_maliyet_usd` YALNIZ dolu satırlardan ve kaç satırın dolu olduğu
("bilinen n/N": bugün hiçbir adaptör fiyat vermiyor, sahip fatura CSV'siyle
doldurur), `AVG(bitti − basladi)` (`percentile_cont` değil: iki satır yeter,
rapor için ortalama okunur), `hata` iş sayısı ve onların TAHMİNİ kredisi (K8
zararı: sağlayıcı faturaladı, kullanıcıya iade edildi). Admin metriklerinde
7 ve 30 gün yan yana; `tools/marj_raporu.py` aynı işlevi CSV'ye döker.

GELİR (`gelir`, Faz 4 / 7): aynı iki pencerede `siparisler` — adet, Σ
`tutar_kurus` (USD), Polar ücreti TAHMİNİ (%6,5 + 0,50; varsayım sabitin
yorumunda) ve net. Dönem başına TEK satır, model başına değil: sipariş modele
bağlanamaz. Marj tablosunun altında ayrı tablo; gerçek payout Polar'da,
aylık fark `tools/polar_mutabakat.py`.

ZAMAN PARAMETRE (`an`): `kota.py`nin aynı kararı — testler saatle oynamaz,
`an` verir; pencere sınırı `>` (dâhil değil). Konuşmaz: cümle yok, sözlük
döner; 404/409 metnini rota kurar (`services/db.py`nin `database_unavailable`
kararı). İş satırının dökümü `kuyruk._json` — kullanıcının gördüğüyle AYNI
biçim (`istek` yine dökülmez: admin de prompt'u görmez, galeriden görür) +
`kullanici_id`/`eposta` (admin kimin işi olduğunu bilmek zorunda).

ÖDEME OLAYLARI (`odeme_olaylari`, `odeme_ozeti`, Faz 4 / 3): admin "Ödeme"
sekmesi — son 100 webhook teslimatı (`?hata=1` yalnız `hata` dolu olanlar:
`kullanici_yok`, `urun_yok` … — sahibin `tools/polar_esitle.py` koşacağı ya da
admin `duzelt`le düzelteceği satırlar) ve üç sayı (olay, hatalı, sipariş).
Gövde (`govde`) DÖKÜLMEZ: e-posta/adres taşır, admin bunları Polar panelinden
görür; liste teslimatın kaderini söyler, içeriğini değil. `alindi` indeksi
sıralamayı taşır (`0008_odeme`).
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, select, update
from sqlalchemy.orm import Session

import catalog
from services import kota, kuyruk, odeme, platform_anahtari, zaman
from services.tablolar import (
    DURUM_BEKLIYOR,
    DURUM_BITTI,
    DURUM_CALISIYOR,
    DURUM_HATA,
    DURUM_IPTAL,
    Is,
    Isci,
    Kullanici,
    OdemeOlayi,
    Oturum,
    Siparis,
)

__all__ = ["CANLI_ESIK", "SAYFA_ADEDI", "SAYFA_ADEDI_AZAMI", "IS_LISTESI_SINIRI",
           "kullanicilar", "kullanici_bul", "oturum_sayisi", "tavan_yaz", "plan_yaz",
           "is_listesi", "is_satiri", "is_iptal", "is_dokumu", "metrikler", "marj", "gelir",
           "MARJ_PENCERELERI", "POLAR_UCRET_ORAN", "POLAR_UCRET_SABIT_KURUS", "GELIR_PARA_BIRIMI"]

# İşçi kalbi 30 sn (services/isci.py); üç kaçırılan kalp = bayat. Bayat işçi
# satırı listede KALIR (admin "kim kaldı" sorusunu buradan okur), yalnız `canli` düşer.
CANLI_ESIK = dt.timedelta(seconds=90)
# Kullanıcı listesi sayfası: öntanımlı 50, en çok 200 (belge: "sayfalı, `?q=`").
SAYFA_ADEDI = 50
SAYFA_ADEDI_AZAMI = 200
# Kuyruk görünümü: son 200 iş (belge §8).
IS_LISTESI_SINIRI = 200
# Faz 4 / 3: admin "Ödeme" sekmesinin satır tavanı — 1 yıllık saklama (K10) tabloyu büyütür, liste son 100.
ODEME_OLAY_SINIRI = 100

_BIR_SAAT = dt.timedelta(hours=1)
_BIR_GUN = dt.timedelta(hours=24)
# Admin "Marj" tablosunun iki penceresi (gün): haftalık bakış ve fatura dönemi.
MARJ_PENCERELERI: tuple[int, ...] = (7, 30)
# Polar ücreti TAHMİNİ (Faz 4 / 7; belge §7 "gelir sütunu"): Starter planın ilan
# edilen tarifesi %5 + 0,50 USD sipariş başına, uluslararası karta +%1,5 (master
# spec Faz 5 kartı; Polar'dan bu oturumlarda doğrulanamadı). VARSAYIM: her
# sipariş uluslararası kart sayılır (satıcı Türkiye'de, alıcı hep başka ülkede —
# kötümser taraf), yani %6,5 + 0,50. Gerçek kesinti Polar'ın payout raporunda;
# bu sayı yalnız marj tablosunun "gelirin ne kadarı kalır" sorusuna kaba cevap.
# Etiket (admin.metrik_gelir) varsayımı açık yazar. Ciro ~1.000 USD/ay üstünde
# Pro plan (%3,8 + 0,40) — sahip geçince iki sabit birlikte değişir.
POLAR_UCRET_ORAN = Decimal("0.065")
POLAR_UCRET_SABIT_KURUS = 50
# Ürünler USD fiyatlı (`urunler.para_birimi`, `tools/polar_esitle.py`); başka
# para biriminde gelen sipariş TOPLANMAZ, sayısı `diger_para_birimi`nde görünür
# (kur uydurmak yalan olurdu — okuyan Polar panelinden bakar).
GELIR_PARA_BIRIMI = "usd"

# Biten işte gerçek, bitmemiş/düşmüş işte rezerv (gerekçe modül başında).
_KREDI = func.coalesce(Is.kredi_gercek, Is.kredi_tahmini)


def _damga(t: dt.datetime | None) -> str | None:
    """Dilimli UTC (`Z`), `kuyruk._json`la aynı (Faz 2 / 10): admin.js süreyi `new Date(basladi)`
    ile hesaplar ve dilimsiz dize tarayıcının dilimi kadar yanlış süre veriyordu."""
    return zaman.damga_utc(t) if t is not None else None


def _saniye(baslangic: dt.datetime | None, an: dt.datetime) -> int | None:
    return max(0, int((an - baslangic).total_seconds())) if baslangic is not None else None


# ─────────────────────────────────────────────────────────── kullanıcılar

def _kullanici_sorgusu(q: str | None, silinmis: bool = False) -> Select:
    # Faz 4 / 5: öntanımlı liste yaşayan hesaplar; `silinmis=True` YALNIZ silinmişler
    # (anonim e-posta, `silindi_at`/`temizlendi_at` damgaları) — ikisi bir listede
    # karışsa "kullanıcı sayısı" anlamını yitirirdi. Geri alma yok (K9).
    sorgu = select(Kullanici).where(Kullanici.silindi_at.is_not(None) if silinmis
                                    else Kullanici.silindi_at.is_(None))
    if q:
        # citext sütunda ILIKE gereksiz ama zararsız; `%`/`_` kaçırılıyor ki
        # arama metni joker değil düz metin olsun.
        kalip = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sorgu = sorgu.where(Kullanici.eposta.ilike(kalip, escape="\\"))
    return sorgu


def kullanicilar(db: Session, *, q: str | None = None, sayfa: int = 1, adet: int = SAYFA_ADEDI,
                 an: dt.datetime | None = None, silinmis: bool = False) -> tuple[list[dict[str, Any]], int]:
    """Kullanıcı sayfası (en yeni üstte) ve toplam sayı; `q` e-postada geçen metin; `silinmis` yalnız silinmişler.

    Her satırda üç türetilmiş alan, üçü de korelasyonlu alt sorgu (tek gidiş-dönüş,
    sayfa 50 satır): `son_gorulme` (oturumların en yenisi), `kredi_24sa` (son 24
    saatte PLATFORM anahtarıyla sıraya alınan kredi — bitende gerçek, ötekinde
    rezerv (`_KREDI`, Faz 3 / 5) —, `iptal` hariç, `kota.gunluk_durum`un aynı
    süzgeci) ve `aktif_is` (bekliyor + calisiyor).
    `plan` ve `bakiye` (Faz 3 / 3) satırın kendi sütunları: admin plan seçiciyi ve
    "kredi ekle" alanını bunlardan kurar; `bakiye` defterin önbelleği (`defter.bakiye`
    ile aynı sütun, ikinci bir SUM yok).
    """
    an = an if an is not None else zaman.an()
    sayfa = max(1, sayfa)
    adet = max(1, min(adet, SAYFA_ADEDI_AZAMI))
    son_gorulme = (select(func.max(Oturum.son_gorulme))
                   .where(Oturum.kullanici_id == Kullanici.id).scalar_subquery())
    kredi = (select(func.coalesce(func.sum(_KREDI), 0))
             .where(Is.kullanici_id == Kullanici.id, Is.durum != DURUM_IPTAL,
                    Is.anahtar_kaynagi == platform_anahtari.KAYNAK_PLATFORM,
                    Is.olusturuldu > an - kota.GUNLUK_PENCERE).scalar_subquery())
    aktif = (select(func.count()).select_from(Is)
             .where(Is.kullanici_id == Kullanici.id, Is.durum.in_(kuyruk.AKTIF_DURUMLAR))
             .scalar_subquery())
    taban = _kullanici_sorgusu(q, silinmis)
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
        # Faz 4 / 4: paket kovası ve Polar müşteri kimliği (Polar panelinde arama için;
        # NULL = hiç satın almamış). "Paket kredisi ekle" `kova='paket'` ile aynı rotaya.
        "paket_bakiye": int(k.paket_bakiye),
        "polar_musteri_id": k.polar_musteri_id,
        # Faz 4 / 5 (K9): silme isteğinin ve içerik temizliğinin anı; yaşayan hesapta ikisi de null.
        "silindi_at": _damga(k.silindi_at),
        "temizlendi_at": _damga(k.temizlendi_at),
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
    """`GET /api/admin/metrikler` gövdesi — beş sorgu + iki marj penceresi (`isler`/`isciler`; belge §8; marj Faz 3 / 5) + iki gelir penceresi (`siparisler`; Faz 4 / 7)."""
    an = an if an is not None else zaman.an()
    bekleyen, calisan, en_eski = db.execute(
        select(func.count(case((Is.durum == DURUM_BEKLIYOR, 1))),
               func.count(case((Is.durum == DURUM_CALISIYOR, 1))),
               func.min(case((Is.durum == DURUM_BEKLIYOR, Is.olusturuldu))))
        .where(Is.durum.in_(kuyruk.AKTIF_DURUMLAR))).one()
    platform_kredi, platform_rezerv = db.execute(
        select(func.coalesce(func.sum(_KREDI), 0), func.coalesce(func.sum(Is.kredi_tahmini), 0))
        .where(Is.durum != DURUM_IPTAL, Is.anahtar_kaynagi == platform_anahtari.KAYNAK_PLATFORM,
               Is.olusturuldu > an - _BIR_GUN)).one()
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
        "son_24sa": {**son_24sa, "platform_kredi": int(platform_kredi or 0),
                     "platform_kredi_rezerv": int(platform_rezerv or 0)},
        "modeller": [{"model": m, "adet": int(n), "p50_sn": round(float(p50), 2),
                      "p95_sn": round(float(p95), 2)} for m, n, p50, p95 in modeller],
        "isciler": [{"id": str(i.id), "konak": i.konak, "surum": i.surum,
                     "es_zamanli": i.es_zamanli, "basladi": _damga(i.basladi),
                     "son_kalp": _damga(i.son_kalp), "canli": i.son_kalp > an - CANLI_ESIK}
                    for i in isciler],
        # Faz 3 / 5: 7 ve 30 günlük pencereler tek düz liste, satırda `gun` (admin.js tek tablo çizer).
        "marj": [satir for gun in MARJ_PENCERELERI for satir in marj(db, gun, an)],
        "gelir": [gelir(db, gun, an) for gun in MARJ_PENCERELERI],
    }


def marj(db: Session, gun: int, an: dt.datetime | None = None) -> list[dict[str, Any]]:
    """Model başına tarife–maliyet satırları: son `gun` günde KAPANAN (`bitti > an - gun`) işler — TEK sorgu.

    Satır: `model`, `gun`, `adet` (biten iş), `kredi` (Σ `kredi_gercek`), `usd`
    (kredi × `catalog.KREDI_USD_CAPASI`, tarifemizin USD karşılığı), `maliyet_usd`
    (Σ `saglayici_maliyet_usd`, yalnız dolu satırlar; hiç dolu yoksa `None`),
    `maliyet_bilinen` (kaç biten satır dolu — "bilinen n/N"), `ort_sure_sn`
    (`AVG(bitti − basladi)`, biten; `basladi` NULL olan satır süreye girmez),
    `hata` (düşen iş sayısı) ve `hata_kredi` (onların TAHMİNİ kredisi — K8:
    sağlayıcı faturalamış olabilir, kullanıcıya iade edildi, fark platformun).
    `iptal`/aktif işler girmez: ne faturalandı ne bitti. Sıra: en çok iş üstte,
    sonra model adı (`metrikler.modeller` ile aynı).

    Pencere `bitti`ye göre, `olusturuldu`ya değil: fatura kapanışa düşer ve
    30 gün önce sıraya girip bugün biten iş bu ayın faturasında. Marj
    hesabı BURADA DEĞİL: `usd − maliyet_usd` farkını okuyan çıkarır; bugün
    `maliyet_usd` çoğunlukla `None` ve `None`dan fark uydurmak yalan olurdu.
    """
    an = an if an is not None else zaman.an()
    biten = Is.durum == DURUM_BITTI
    dusen = Is.durum == DURUM_HATA
    sure = func.extract("epoch", Is.bitti - Is.basladi)
    satirlar = db.execute(
        select(Is.model,
               func.count(case((biten, 1))),
               func.coalesce(func.sum(case((biten, Is.kredi_gercek))), 0),
               func.sum(case((biten, Is.saglayici_maliyet_usd))),
               func.count(case((biten & Is.saglayici_maliyet_usd.is_not(None), 1))),
               func.avg(case((biten & Is.basladi.is_not(None), sure))),
               func.count(case((dusen, 1))),
               func.coalesce(func.sum(case((dusen, Is.kredi_tahmini))), 0))
        .where(Is.durum.in_((DURUM_BITTI, DURUM_HATA)), Is.bitti.is_not(None),
               Is.bitti > an - dt.timedelta(days=gun))
        .group_by(Is.model).order_by(func.count().desc(), Is.model)).all()
    return [{
        "model": model,
        "gun": gun,
        "adet": int(adet),
        "kredi": int(kredi),
        # `float(Decimal)`: JSON'a sayı olarak gitsin; 4 hane 0,0001 USD (kredi çapasının onda biri).
        "usd": round(float(Decimal(int(kredi)) * catalog.KREDI_USD_CAPASI), 4),
        "maliyet_usd": round(float(maliyet), 6) if maliyet is not None else None,
        "maliyet_bilinen": int(bilinen),
        "ort_sure_sn": round(float(sure_ort), 2) if sure_ort is not None else None,
        "hata": int(hata),
        "hata_kredi": int(hata_kredi),
    } for model, adet, kredi, maliyet, bilinen, sure_ort, hata, hata_kredi in satirlar]



def gelir(db: Session, gun: int, an: dt.datetime | None = None) -> dict[str, Any]:
    """Dönemin GELİR satırı (Faz 4 / 7): son `gun` günde işlenen `siparisler` — adet, Σ tutar (USD), Polar ücreti tahmini, net.

    Marj tablosunun karşı sütunu: `marj` gideri (sağlayıcı USD) model başına
    verir, sipariş modele bağlanamaz (paket kredisi her modele harcanır) — o
    yüzden gelir MODEL BAŞINA DEĞİL, DÖNEM BAŞINA tek satır. Pencere
    `olusturuldu`ya göre (webhook'un işlediği an; Polar'ın `created_at`i
    saniyeler önce — ay sınırındaki farkı `tools/polar_mutabakat.py` bilir).
    `gelir_usd` yalnız `GELIR_PARA_BIRIMI` satırları; ötekiler `diger_para_birimi`
    sayısında. `polar_ucreti_usd` = Σ tutar × `POLAR_UCRET_ORAN` + adet ×
    `POLAR_UCRET_SABIT_KURUS` (VARSAYIM, sabitin yorumunda) — gerçek payout
    Polar'da; `net_usd` = gelir − tahmini ücret. Sipariş yoksa üç sayı 0.0
    (bilinen sıfır: dönemde satış olmadı — `marj`ın "bilinmeyen maliyet `None`"
    kararından farklı, çünkü burada kaynak eksiksiz: her ödenen sipariş bizde).
    """
    an = an if an is not None else zaman.an()
    pencere = Siparis.olusturuldu > an - dt.timedelta(days=gun)
    usd = Siparis.para_birimi == GELIR_PARA_BIRIMI
    adet, toplam_kurus, diger = db.execute(
        select(func.count(case((usd, 1))),
               func.coalesce(func.sum(case((usd, Siparis.tutar_kurus))), 0),
               func.count(case((~usd, 1))))
        .where(pencere)).one()
    adet, toplam_kurus, diger = int(adet), int(toplam_kurus), int(diger)
    gelir_ = Decimal(toplam_kurus) / 100
    ucret = gelir_ * POLAR_UCRET_ORAN + Decimal(adet * POLAR_UCRET_SABIT_KURUS) / 100
    return {
        "gun": gun,
        "siparis": adet,
        # `float(Decimal)` — JSON'a sayı; 2 hane: cent hassasiyeti, ücret tahmini de cent'e yuvarlanır.
        "gelir_usd": round(float(gelir_), 2),
        "polar_ucreti_usd": round(float(ucret), 2),
        "net_usd": round(float(gelir_ - ucret), 2),
        "diger_para_birimi": diger,
    }


# ─────────────────────────────────────────────────────────────── ödeme (Faz 4 / 3)

def odeme_olaylari(db: Session, *, yalniz_hata: bool = False, limit: int = ODEME_OLAY_SINIRI) -> list[dict[str, Any]]:
    """Son `limit` webhook teslimatı, en yeni üstte; `yalniz_hata` ile `hata` dolu olanlar (gerekçe modül başında)."""
    sorgu = (select(OdemeOlayi, Kullanici.eposta)
             .outerjoin(Kullanici, Kullanici.id == OdemeOlayi.kullanici_id)
             .order_by(OdemeOlayi.alindi.desc(), OdemeOlayi.id).limit(limit))
    if yalniz_hata:
        sorgu = sorgu.where(OdemeOlayi.hata.is_not(None))
    return [{
        "id": str(o.id),
        "webhook_id": o.webhook_id,
        "tur": o.tur,
        "nesne": o.polar_nesne_id,
        "kullanici_id": str(o.kullanici_id) if o.kullanici_id is not None else None,
        "eposta": eposta,
        "alindi": _damga(o.alindi),
        "islendi_at": _damga(o.islendi_at),
        "hata": o.hata,
    } for o, eposta in db.execute(sorgu).all()]


def odeme_ozeti(db: Session) -> dict[str, Any]:
    """Üç sayı + ayna tazeliği: toplam teslimat, `hata` dolu teslimat, `siparisler` satırı, `urunler_bayat`
    (admin bağlamı hepsini okur, `yonetici_okur`).

    `urunler_bayat` (Faz 4 / 4, belge §4 "Risk"): `odeme.urunler_bayat_mi` — ayna
    7 günden eski ya da boşsa `True`; admin.js uyarı satırını gösterir. Günlük
    satırı (`olay=odeme.urunler_bayat`) rotada, her sekme açılışında bir kez.
    """
    olay, hatali = db.execute(select(func.count(), func.count(OdemeOlayi.hata))).one()
    siparis = db.scalar(select(func.count()).select_from(Siparis))
    return {"olay": int(olay or 0), "hatali": int(hatali or 0), "siparis": int(siparis or 0),
            "urunler_bayat": odeme.urunler_bayat_mi(db)}
