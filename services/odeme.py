# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ödeme olayları — Polar webhook'unu deftere ve plana çeviren TEK yer (Faz 4 / 3; docs/faz4-odeme-abonelik-kvkk.md §3, K4/K6).

PARA BURADAN GİRER: `order.paid` → paket kredisi (`defter.paket_yukle`, kova
paket, devreder) ya da plan + dönem hibesi (`plan_uygula` + `defter.hibe`,
"hibeye tamamla", K6); abonelik yaşam döngüsü Polar'ın durum makinesi, bizde
yansıması (K6): `canceled` → `plan_bitis` (plan KALIR, ödenen dönem kullanılır),
`uncanceled` → `plan_bitis` NULL, `revoked` → `free` + `defter.dusur` (hibe
kovası ücretsiz hibeye iner, paket kovası durur), `updated` → plan değişimi
(portaldan yükseltme/düşürme), `customer.*` → `polar_musteri_id`, `order.refunded`
→ yalnız WARNING (kredi geri alma admin `duzelt` kararı: harcanmış kredi eksiye
inmez — Faz 3 K1). Sipariş satırı (`siparisler`) her ödenen siparişte.

Olay → eylem tablosu (`_ISLEYICILER`; listede olmayan tür KAYDEDİLİR, işlenmez, 200 `atlandi`):

| olay | okunan alanlar | eylem |
| --- | --- | --- |
| `order.paid` | `id`, `billing_reason`, `product_id`, `subscription_id`, `customer.external_id`, `customer_id`, `total_amount`, `currency` | sipariş satırı; paket → `paket:<order_id>`; plan → `plan_uygula` + `hibe:<u>:polar:<order_id>` |
| `order.refunded` | `id`, `refunded_amount`, `customer.external_id` | WARNING `odeme.iade`, defter dokunulmaz |
| `subscription.active` | `id`, `product_id`, `customer.external_id` | `plan_uygula` (hibe YOK — `order.paid` yatırır) |
| `subscription.updated` | + `status`, `cancel_at_period_end`, `ends_at`/`current_period_end` | `status=active` ise plan (yükseltme/düşürme, düşürmede `dusur`) + `plan_bitis`; değilse dokunma |
| `subscription.canceled` | `ends_at`/`current_period_end` | `plan_bitis` |
| `subscription.uncanceled` | — | `plan_bitis` NULL |
| `subscription.revoked` | `id` | `free` + `sona_erme:<u>:<abonelik_id>:<gün>` |
| `customer.created`/`updated` | `id`, `external_id` | `polar_musteri_id` |

ÜÇ KATMAN İDEMPOTENCY (K4): (1) TESLİMAT — `olayi_kaydet` `INSERT … ON CONFLICT
(webhook_id) DO NOTHING`; `None` = çoktan alındı, rota 200 `yinelenen`, hiçbir
şey işlenmez (Polar yeniden gönderimde `webhook-id`yi korur). (2) İŞ — defter
anahtarı sipariş kimliği taşır (`paket:<order_id>`, `hibe:<u>:polar:<order_id>`):
aynı siparişi anlatan İKİ FARKLI olay (`order.paid` + panelden "yeniden gönder"
yeni `webhook-id` ile) tek kredi olur. (3) SİPARİŞ — `siparisler.polar_siparis_id`
UNIQUE, `ON CONFLICT DO NOTHING`. Üçü de Postgres'te: eş zamanlı iki teslimat
aynı satırı yazmaya kalkarsa ikincisi birincinin commit'ini bekler, sonra çakışır.

TEK TRANSAKSİYON: kayıt → işleme → `islendi_at`; hepsi rotanın oturumunda
(`db.oturum`: dönüşte commit, istisnada rollback). İşleme düşerse OLAY SATIRI DA
GERİ ALINIR (belge §3 "DİKKAT"): aksi hâlde Polar'ın yeniden denemesi (2)'ye
"çoktan alındı" diye çarpar ve para hiç yatmazdı. Rota 500 döner, Polar üstel
geri çekilmeyle yeniden dener, temiz gelir.

"HATA" AMA 200: kullanıcı çözülemedi (`kullanici_yok`), ürün aynada yok
(`urun_yok` — sahip `tools/polar_esitle.py` koşar, 4. görev), sebep ↔ ürün türü
uyumsuz (`urun_sebep_uyumsuz`), tanınmayan `billing_reason` (`sebep_bilinmiyor`),
bu müşteri kimliği başka kullanıcıda (`musteri_cakisiyor`), olay kullanıcının
GÜNCEL aboneliğine ait değil (`abonelik_eski` — iptal edilmiş eski aboneliğin
geciken `revoked`ı yeni aboneliği düşürmesin). Bunlar yeniden denemeyle
düzelmez; 5xx dönmek Polar'ı saatlerce boşuna uğraştırır. Satır `hata` sütunuyla
kalır, admin "Ödeme" sekmesinde görünür (`depo_admin.odeme_olaylari`), sahip
düzeltir (ürün aynası, admin `duzelt`).

KİRACISIZ MODÜL (tests/test_galeri_db.py `KIRACISIZ_MODULLER`): webhook
OTURUMSUZ gelir, isteğin kiracısı yoktur; rota `kiraci.baglam(rol=ADMIN)` kurar
(`yonetici_ekler` — `kredi_hareketleri` ve `siparisler`, K4) ve hedef kullanıcı
OLAYDAN çözülür (`kullaniciyi_coz`: `customer.external_id` = `kullanicilar.id`,
yoksa `metadata.kullanici_id`, yoksa `polar_musteri_id`). Bu yüzden işlevler
`kullanici_id` parametresi almaz — hedef `hedef_id`/`kullanici` nesnesi;
`defter.*` çağrıları hedefi açık verir (defterin sahip süzgeci durur).

KONUŞMAZ: hata kodları ASCII (`kullanici_yok` …), günlük satırları ASCII;
kullanıcıya cümle yok (tests/test_i18n.py sınıflandırması). Polar şemasına
tolerant okuma (`dict.get`, `isinstance`): eksik alan "atlandı", 500 değil —
gerekçe services/polar.py başında.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from services import defter, gunluk, hukuk, kuyruk, planlar, polar, zaman
from services.tablolar import SIPARIS_SEBEPLERI, URUN_TURLERI, Kullanici, OdemeOlayi, Siparis, Urun

__all__ = ["DURUM_ISLENDI", "DURUM_YINELENEN", "DURUM_ATLANDI", "HATALAR", "ISLENEN_TURLER", "Sonuc",
           "URUNLER_BAYAT_GUN",
           "isle", "olayi_kaydet", "kullaniciyi_coz", "urun_bul", "plan_uygula",
           "aktif_urunler", "urun_bul_id", "urun_json", "sartlar_kabul_at_oku", "sartlar_kabul_yaz",
           "polar_musteri_id_oku", "urunler_bayat_mi"]

# `olay=odeme.*` satırlarının kaynağı; biçim `kromis` kökünde (services/gunluk.py).
_gunluk = logging.getLogger("kromis.odeme")

# Rota gövdesinin `durum` alanı (belge §3): işlendi / çoktan alınmıştı / kaydedildi ama işlenmedi.
DURUM_ISLENDI = "islendi"
DURUM_YINELENEN = "yinelenen"
DURUM_ATLANDI = "atlandi"

# `odeme_olaylari.hata` değerleri — ASCII kod, cümle değil (admin sekmesi aynen gösterir).
HATA_KULLANICI_YOK = "kullanici_yok"
HATA_URUN_YOK = "urun_yok"
HATA_SEBEP_BILINMIYOR = "sebep_bilinmiyor"
HATA_URUN_SEBEP_UYUMSUZ = "urun_sebep_uyumsuz"
HATA_MUSTERI_CAKISIYOR = "musteri_cakisiyor"
HATA_ABONELIK_ESKI = "abonelik_eski"
HATA_NESNE_YOK = "nesne_yok"
HATALAR: tuple[str, ...] = (HATA_KULLANICI_YOK, HATA_URUN_YOK, HATA_SEBEP_BILINMIYOR, HATA_URUN_SEBEP_UYUMSUZ,
                            HATA_MUSTERI_CAKISIYOR, HATA_ABONELIK_ESKI, HATA_NESNE_YOK)

URUN_PLAN, URUN_PAKET = URUN_TURLERI
SEBEP_PURCHASE = "purchase"

# ŞARTLAR SÜRÜMÜ artık `services/hukuk.HUKUK_SURUMU` (Faz 4 / 6). 4. görev burada
# `SARTLAR_SURUMU = "0000-yer-tutucu"` taşıyordu: metin yoktu ama sütun boş
# bırakılmadı (onayın sürümü sonradan kurulamaz). 6. görev metni getirdi, sabit
# oraya bağlandı ve buradan SİLİNDİ — iki modülde iki sürüm literali, biri bir
# gün ötekinden ayrı ilerlerdi. `0000-yer-tutucu` ile damgalı satırlar
# `hukuk.guncel_mi` için "güncel değil"dir ve ayarlar banner'ı yeniden onay ister.

# Ayna tazeliği (belge §4 "Risk"): `urunler.guncellendi`nin en yenisi bundan
# eskiyse — ya da hiç ürün yoksa — admin "Ödeme" sekmesi uyarır ve
# `olay=odeme.urunler_bayat` düşer. 7 gün: sahip Polar'da fiyat değiştirip
# `polar_esitle` koşmayı unutursa sayfa bayat fiyat gösterir (ödeme Polar'ın
# doğru fiyatıyla); bir hafta o unutkanlığın görünür olması için yeter.
URUNLER_BAYAT_GUN = 7
ABONELIK_AKTIF = "active"
assert SEBEP_PURCHASE in SIPARIS_SEBEPLERI


@dataclasses.dataclass(frozen=True)
class Sonuc:
    """`isle`nin cevabı: `durum` (yukarıdaki üç değer), `hata` (atlandıysa neden), çözülen kullanıcı, yatan kredi."""
    durum: str
    hata: str | None = None
    kullanici_id: uuid.UUID | None = None
    kredi: int = 0

    def json(self) -> dict[str, Any]:
        govde: dict[str, Any] = {"durum": self.durum}
        if self.hata is not None:
            govde["hata"] = self.hata
        return govde


def _atla(hata: str, kullanici: Kullanici | None = None) -> Sonuc:
    return Sonuc(DURUM_ATLANDI, hata=hata, kullanici_id=kullanici.id if kullanici is not None else None)


# ─────────────────────────────────────────────────────── yük okuma

def _dize(veri: Mapping[str, Any], ad: str) -> str | None:
    deger = veri.get(ad)
    return deger if isinstance(deger, str) and deger else None


def _tam_sayi(veri: Mapping[str, Any], ad: str) -> int:
    deger = veri.get(ad)
    return deger if isinstance(deger, int) and not isinstance(deger, bool) else 0


def _zaman(veri: Mapping[str, Any], ad: str) -> dt.datetime | None:
    """ISO 8601 (`…Z` ya da `+00:00`) → dilimli `datetime`; yoksa/bozuksa `None`."""
    ham = _dize(veri, ad)
    if ham is None:
        return None
    try:
        deger = dt.datetime.fromisoformat(ham.replace("Z", "+00:00"))
    except ValueError:
        return None
    return deger if deger.tzinfo is not None else deger.replace(tzinfo=dt.UTC)


def _uuid(ham: str | None) -> uuid.UUID | None:
    if not ham:
        return None
    try:
        return uuid.UUID(ham)
    except ValueError:
        return None


def _musteri(olay: polar.Olay) -> tuple[str | None, str | None]:
    """(`external_id`, Polar müşteri kimliği) — sipariş/abonelikte `data.customer`, `customer.*`de `data`nın kendisi."""
    veri = olay.veri
    if olay.tur.startswith("customer."):
        return _dize(veri, "external_id"), _dize(veri, "id")
    musteri = veri.get("customer")
    if isinstance(musteri, Mapping):
        return _dize(musteri, "external_id"), _dize(musteri, "id") or _dize(veri, "customer_id")
    return None, _dize(veri, "customer_id")


# ─────────────────────────────────────────────────────── depo

def olayi_kaydet(db: Session, olay: polar.Olay, an: dt.datetime) -> uuid.UUID | None:
    """`odeme_olaylari`ya teslimat satırı — `ON CONFLICT (webhook_id) DO NOTHING`; `None` = çoktan alındı (K4 teslimat katmanı).

    Gövde REDAKTE yazılır (`kuyruk._redakte`: `sk-…`/`Bearer …` desenleri ve adı
    gizli kokan alanlar; kart verisi zaten gelmez, e-posta/adres K10 gereği kalır).
    `kullanici_id`/`islendi_at`/`hata` işleme bitince `_kapat` yazar — aynı transaksiyon.
    """
    satir = db.execute(
        pg_insert(OdemeOlayi)
        .values(webhook_id=olay.webhook_id, tur=olay.tur, polar_nesne_id=olay.nesne_id,
                govde=kuyruk._redakte(dict(olay.govde)), alindi=an)
        .on_conflict_do_nothing(index_elements=["webhook_id"])
        .returning(OdemeOlayi.id)).scalar_one_or_none()
    return satir


def _kapat(db: Session, olay_id: uuid.UUID, an: dt.datetime, sonuc: Sonuc) -> None:
    db.execute(update(OdemeOlayi).where(OdemeOlayi.id == olay_id)
               .values(islendi_at=an, kullanici_id=sonuc.kullanici_id, hata=sonuc.hata))


def kullaniciyi_coz(db: Session, olay: polar.Olay) -> Kullanici | None:
    """Olayın kullanıcısı: `customer.external_id` (= `kullanicilar.id`) → `metadata.kullanici_id` → `polar_musteri_id`; silinmiş hesap çözülmez.

    `external_id` checkout'ta bizim yazdığımız değer (4. görev `external_customer_id`);
    `metadata` yedek (Polar panelinden elle açılan sipariş); müşteri kimliği son
    çare (`customer.*` olayı önce gelmişse bağ kurulmuştur).
    """
    external_id, musteri_id = _musteri(olay)
    metadata = olay.veri.get("metadata")
    meta_id = _dize(metadata, "kullanici_id") if isinstance(metadata, Mapping) else None
    for aday in (_uuid(external_id), _uuid(meta_id)):
        if aday is not None:
            kullanici = db.scalars(select(Kullanici).where(Kullanici.id == aday,
                                                           Kullanici.silindi_at.is_(None))).one_or_none()
            if kullanici is not None:
                return kullanici
    if musteri_id is not None:
        return db.scalars(select(Kullanici).where(Kullanici.polar_musteri_id == musteri_id,
                                                  Kullanici.silindi_at.is_(None))).one_or_none()
    return None


def urun_bul(db: Session, polar_urun_id: str | None) -> Urun | None:
    """`urunler` aynasında Polar ürün kimliği; arşivlenmiş (`aktif=false`) ürün de bulunur — eski siparişler ona bakar."""
    if not polar_urun_id:
        return None
    return db.scalars(select(Urun).where(Urun.polar_urun_id == polar_urun_id)).one_or_none()


def urun_bul_id(db: Session, urun_id: uuid.UUID) -> Urun | None:
    """Bizim `urunler.id`miz ile AKTİF ürün; arşivlenmiş ya da bilinmeyen → `None` (checkout 404 `err.urun_yok`).

    `urun_bul`un tersi: o Polar kimliğiyle ve arşivlenmişi de bulur (eski
    siparişler), bu satış yüzünün seçimini doğrular — arşivlenmiş ürün sayfada
    görünmez, elle kurulan bir istekle de satılmaz.
    """
    return db.scalars(select(Urun).where(Urun.id == urun_id, Urun.aktif.is_(True))).one_or_none()


def aktif_urunler(db: Session) -> list[Urun]:
    """Satıştaki ürünler, kararlı sırada: planlar `PLANLAR`ın basamağıyla, paketler krediye göre artan.

    Sıra SUNUCUDA: satış sayfası kartları geldiği sırayla çizer ve iki dilde
    aynı sırayı göstermeli. `urunler` politikasız tablo (ALTYAPI): oturumsuz
    `GET /api/odeme/urunler` de okuyabilir.
    """
    satirlar = list(db.scalars(select(Urun).where(Urun.aktif.is_(True))))
    return sorted(satirlar, key=lambda u: (0, planlar.PLANLAR[u.plan].rank, 0) if u.tur == URUN_PLAN and u.plan
                  else (1, 0, u.kredi))


def urun_json(u: Urun) -> dict[str, Any]:
    """Satış yüzüne giden satır — `polar_urun_id` YOK (istemci Polar kimliğini bilmez; checkout bizim id'mizle)."""
    return {"id": str(u.id), "tur": u.tur, "plan": u.plan, "kredi": u.kredi, "fiyat_kurus": u.fiyat_kurus,
            "para_birimi": u.para_birimi, "ad": u.ad}


def sartlar_kabul_at_oku(db: Session, hedef_id: uuid.UUID) -> dt.datetime | None:
    """`kullanicilar.sartlar_kabul_at` — checkout'un 412 kapısı; DB'den (bağımlılığın nesnesi ayrılmış olabilir,
    `defter.plan_oku`nun gerekçesi)."""
    return db.scalar(select(Kullanici.sartlar_kabul_at).where(Kullanici.id == hedef_id))


def polar_musteri_id_oku(db: Session, hedef_id: uuid.UUID) -> str | None:
    """`kullanicilar.polar_musteri_id` — portal için; NULL = hiç satın almamış (rota 404 `err.musteri_yok`)."""
    return db.scalar(select(Kullanici.polar_musteri_id).where(Kullanici.id == hedef_id))


def sartlar_kabul_yaz(db: Session, hedef_id: uuid.UUID, an: dt.datetime, *,
                      surum: str = hukuk.HUKUK_SURUMU) -> bool:
    """`sartlar_kabul_at` + `sartlar_surumu` (checkout'un 412 kapısı ve `POST /api/hesap/sartlar-kabul`); satır yoksa `False`.

    Hesap tablosu, RLS dışı (`plan_uygula`nın deseni); hedef `hedef_id` — kiracısız
    modül sözleşmesi (tests/test_galeri_db.py `KIRACISIZ_MODULLER`). Eski bir onayın
    üstüne yazar: kullanıcı yeni sürümü onayladığında damga ve sürüm ilerler.
    """
    sonuc = db.execute(update(Kullanici)
                       .where(Kullanici.id == hedef_id, Kullanici.silindi_at.is_(None))
                       .values(sartlar_kabul_at=an, sartlar_surumu=surum))
    return kuyruk._etkilenen(sonuc) > 0


# `odeme_olaylari.govde`de kişisel veri taşıyan alanlar — Polar'ın `customer`
# nesnesi ve siparişin fatura alanları (tests/fixtures/polar/*.json: `email`,
# `billing_name`, `billing_address`, `tax_id`; `avatar_url` kişiye gider).
# Anahtar adıyla, yolla değil: aynı alanlar `data.customer` altında da `data`
# kökünde de (`billing_address`) geçiyor ve Polar şemasında yeri değişebilir.
# `name` listede DEĞİL: ürünün de `name`i var ("DUMMY urun") ve o mali kaydın
# parçası — kişinin adı yalnız `email` taşıyan nesnede (müşteri) silinir.
KISISEL_ALANLAR: frozenset[str] = frozenset({"email", "billing_name", "billing_address", "tax_id", "avatar_url"})
SILINDI = "[SILINDI]"


def _kisiseli_sil(deger: Any) -> Any:
    """Gövdeyi alan alan gezer; `KISISEL_ALANLAR`daki her anahtarın değeri `[SILINDI]` (yapı korunur)."""
    if isinstance(deger, Mapping):
        musteri = "email" in deger
        return {str(ad): (SILINDI if str(ad) in KISISEL_ALANLAR or (musteri and str(ad) == "name")
                          else _kisiseli_sil(v))
                for ad, v in deger.items()}
    if isinstance(deger, list):
        return [_kisiseli_sil(v) for v in deger]
    return deger


def olaylari_anonimlestir(db: Session, hedef_id: uuid.UUID) -> int:
    """Silinen hesabın olaylarını sahipsizleştirir: `kullanici_id` NULL, gövdedeki e-posta/ad/adres `[SILINDI]`; satır sayısı.

    K10: olay 1 yıl saklanır (webhook teslimatının kanıtı — "geldi mi, işlendi
    mi" sorusu Polar mutabakatında hâlâ anlamlı), ama kişisel veri hesapla
    birlikte gider (KVKK md. 7). `SET NULL` FK'sı yalnız SATIR silinince
    tetiklenir; hesap satırı anonim KALIYOR (K9), o yüzden bağı burası
    keser. Hesap silme turu (services/isci.py `silme_turu`) admin bağlamında
    çağırır — tablo politikasız, bağlam yalnız kural.
    """
    satirlar = db.execute(select(OdemeOlayi.id, OdemeOlayi.govde)
                          .where(OdemeOlayi.kullanici_id == hedef_id)).all()
    for olay_id, govde in satirlar:
        db.execute(update(OdemeOlayi).where(OdemeOlayi.id == olay_id)
                   .values(kullanici_id=None, govde=_kisiseli_sil(govde)))
    return len(satirlar)


def urunler_bayat_mi(db: Session, an: dt.datetime | None = None) -> bool:
    """Ayna `URUNLER_BAYAT_GUN`den eski ya da BOŞ mu (admin uyarısı + `odeme.urunler_bayat`; gerekçe sabitte)."""
    an = an if an is not None else zaman.an()
    en_yeni = db.scalar(select(func.max(Urun.guncellendi)))
    return en_yeni is None or en_yeni < an - dt.timedelta(days=URUNLER_BAYAT_GUN)


def plan_uygula(db: Session, hedef_id: uuid.UUID, plan: str, *, abonelik_id: str | None,
                plan_bitis: dt.datetime | None = None) -> bool:
    """`kullanicilar.plan` + `polar_abonelik_id` + `plan_bitis` (hesap tablosu, RLS dışı — `depo_admin.plan_yaz`in deseni); satır yoksa `False`.

    `plan` `PLANLAR`dan olmalı (`urunler.plan` CHECK'i bunu zaten garanti eder;
    KeyError sessiz 500 yerine burada gürültü). Bakiyeye DOKUNMAZ: hibe
    `_donem_hibesi`, düşürme `_dusur` — çağıran sıralar.
    """
    if plan not in planlar.PLANLAR:
        raise KeyError(plan)
    sonuc = db.execute(update(Kullanici)
                       .where(Kullanici.id == hedef_id, Kullanici.silindi_at.is_(None))
                       .values(plan=plan, polar_abonelik_id=abonelik_id, plan_bitis=plan_bitis))
    return kuyruk._etkilenen(sonuc) > 0


def _plan_bitis_yaz(db: Session, hedef_id: uuid.UUID, plan_bitis: dt.datetime | None) -> None:
    db.execute(update(Kullanici).where(Kullanici.id == hedef_id).values(plan_bitis=plan_bitis))


def _musteriyi_bagla(db: Session, kullanici: Kullanici, musteri_id: str | None) -> str | None:
    """`polar_musteri_id` yaz; zaten aynıysa/kimlik yoksa dokunmaz. Başka kullanıcıdaysa `musteri_cakisiyor` (UNIQUE'e çarpıp 500 olmasın)."""
    if not musteri_id or kullanici.polar_musteri_id == musteri_id:
        return None
    sahip = db.scalar(select(Kullanici.id).where(Kullanici.polar_musteri_id == musteri_id))
    if sahip is not None and sahip != kullanici.id:
        return HATA_MUSTERI_CAKISIYOR
    db.execute(update(Kullanici).where(Kullanici.id == kullanici.id).values(polar_musteri_id=musteri_id))
    return None


def _siparis_yaz(db: Session, kullanici: Kullanici, urun: Urun, veri: Mapping[str, Any], siparis_id: str,
                 sebep: str, an: dt.datetime) -> bool:
    """`siparisler` satırı — `polar_siparis_id` UNIQUE, `ON CONFLICT DO NOTHING` (K4 üçüncü kilit); `True` = yeni."""
    satir = db.execute(
        pg_insert(Siparis)
        .values(kullanici_id=kullanici.id, polar_siparis_id=siparis_id,
                polar_abonelik_id=_dize(veri, "subscription_id"), urun_id=urun.id, sebep=sebep,
                tutar_kurus=_tam_sayi(veri, "total_amount"), para_birimi=(_dize(veri, "currency") or "usd").lower(),
                olusturuldu=an)
        .on_conflict_do_nothing(index_elements=["polar_siparis_id"])
        .returning(Siparis.id)).scalar_one_or_none()
    return satir is not None


def _donem_hibesi(db: Session, hedef_id: uuid.UUID, plan: str, siparis_id: str, an: dt.datetime) -> int:
    """K6 "hibeye tamamla": hibe kovası planın dönem hibesinin ALTINDAYSA farkı `hibe:<u>:polar:<order_id>` ile yatır; yatan miktar."""
    hedef = planlar.PLANLAR[plan].aylik_hibe
    mevcut = defter.bakiye(db, hedef_id).hibe
    if hedef <= 0 or mevcut >= hedef:
        return 0
    fark = hedef - mevcut
    yatti = defter.hibe(db, hedef_id, fark, f"{defter.ONEK_HIBE}{hedef_id}:polar:{siparis_id}", an=an)
    return fark if yatti else 0


def _dusur(db: Session, hedef_id: uuid.UUID, eski_plan: str, plan: str, abonelik_id: str, an: dt.datetime) -> int:
    """Düşürme (K3/K6): plan GERÇEKTEN daha düşük hibeli bir plana indiyse hibe kovası yeni hibenin üstündeki kadar
    `sona_erme:<u>:<abonelik>:<gün>` ile iner; düşen miktar (0 = yok).

    Plan değişmemişse ya da yükselmişse DOKUNMAZ — aksi hâlde alakasız bir
    `subscription.updated` (iptal bayrağı, metadata) ya da başka gün yeniden
    gönderilen bir `revoked` (yeni anahtar) admin `duzelt`le verilmiş fazla
    hibeyi kırpardı; ölçüldü (tests/test_odeme.py "does not clip").
    """
    if planlar.PLANLAR[plan].aylik_hibe >= planlar.PLANLAR[eski_plan].aylik_hibe:
        return 0
    hareket = defter.dusur(db, hedef_id, planlar.PLANLAR[plan].aylik_hibe,
                           f"{defter.ONEK_SONA_ERME}{hedef_id}:{abonelik_id}:{an:%Y-%m-%d}", an=an)
    return -hareket.miktar if hareket is not None else 0


def _abonelik_eslesiyor(kullanici: Kullanici, abonelik_id: str) -> bool:
    """Olay kullanıcının güncel aboneliğine mi ait? Bağ hiç kurulmamışsa (NULL) kabul."""
    return kullanici.polar_abonelik_id is None or kullanici.polar_abonelik_id == abonelik_id


# ─────────────────────────────────────────────────────── işleyiciler

def _order_paid(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    veri = olay.veri
    siparis_id = olay.nesne_id
    if siparis_id is None:
        return _atla(HATA_NESNE_YOK, kullanici)
    sebep = _dize(veri, "billing_reason")
    if sebep not in SIPARIS_SEBEPLERI:
        return _atla(HATA_SEBEP_BILINMIYOR, kullanici)
    urun = urun_bul(db, _dize(veri, "product_id"))
    if urun is None:
        return _atla(HATA_URUN_YOK, kullanici)
    # Aynadaki tür ile Polar'ın sebebi çelişiyorsa para YATMAZ: paket ürünü abonelik
    # sebebiyle ya da plan ürünü tek seferlik gelmişse ayna yanlış yazılmıştır.
    if (urun.tur == URUN_PAKET) != (sebep == SEBEP_PURCHASE):
        return _atla(HATA_URUN_SEBEP_UYUMSUZ, kullanici)
    _, musteri_id = _musteri(olay)
    cakisma = _musteriyi_bagla(db, kullanici, musteri_id)
    if cakisma is not None:
        return _atla(cakisma, kullanici)
    yeni_siparis = _siparis_yaz(db, kullanici, urun, veri, siparis_id, sebep, an)
    if urun.tur == URUN_PAKET:
        yatti = defter.paket_yukle(db, kullanici.id, urun.kredi, f"{defter.ONEK_PAKET}{siparis_id}",
                                   aciklama=urun.ad, an=an)
        kredi = urun.kredi if yatti else 0
        plan = None
    else:
        plan = urun.plan
        assert plan is not None   # CHECK `tur_plan_uyumu`
        plan_uygula(db, kullanici.id, plan, abonelik_id=_dize(veri, "subscription_id"))
        kredi = _donem_hibesi(db, kullanici.id, plan, siparis_id, an)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), siparis=siparis_id, sebep=sebep,
                urun=urun.polar_urun_id, plan=plan, kredi=kredi, yeni_siparis=yeni_siparis)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id, kredi=kredi)


def _order_refunded(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    """K6: OTOMATİK geri alma yok — kullanıcı krediyi harcamış olabilir, eksi yalnız admin `duzelt` kararıyla."""
    kullanici = kullaniciyi_coz(db, olay)
    gunluk.olay(_gunluk, "odeme.iade", "polar siparisi iade edildi; kredi geri alimi admin karari",
                seviye=logging.WARNING, kullanici_id=str(kullanici.id) if kullanici is not None else None,
                siparis=olay.nesne_id, iade_kurus=_tam_sayi(olay.veri, "refunded_amount"),
                para_birimi=_dize(olay.veri, "currency"))
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id if kullanici is not None else None)


def _abonelik_plani(db: Session, olay: polar.Olay, kullanici: Kullanici) -> tuple[str, str] | Sonuc:
    """Abonelik olayının (abonelik_id, plan) çifti ya da atlanma sonucu."""
    abonelik_id = olay.nesne_id
    if abonelik_id is None:
        return _atla(HATA_NESNE_YOK, kullanici)
    urun = urun_bul(db, _dize(olay.veri, "product_id"))
    if urun is None:
        return _atla(HATA_URUN_YOK, kullanici)
    if urun.tur != URUN_PLAN or urun.plan is None:
        return _atla(HATA_URUN_SEBEP_UYUMSUZ, kullanici)
    return abonelik_id, urun.plan


def _donem_sonu(veri: Mapping[str, Any]) -> dt.datetime | None:
    """İptalde erişimin bittiği an: Polar `ends_at` (dönem sonu iptalinde dolu), yoksa `current_period_end`."""
    return _zaman(veri, "ends_at") or _zaman(veri, "current_period_end")


def _subscription_active(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    """`order.paid`in ikizi (ikisi de gelir): plan yazımı idempotent, HİBE burada değil — sipariş anahtarlı, bir kez."""
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    cozum = _abonelik_plani(db, olay, kullanici)
    if isinstance(cozum, Sonuc):
        return cozum
    abonelik_id, plan = cozum
    plan_uygula(db, kullanici.id, plan, abonelik_id=abonelik_id)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), abonelik=abonelik_id, plan=plan)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


def _subscription_updated(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    """Portaldan yükseltme/düşürme (`status=active`, ürün değişmiş olabilir): plan + `plan_bitis`; düşürmede `dusur`.
    Öteki durumlar (`past_due`, `canceled`, `unpaid` …) Polar'ın işi — `revoked` gelene kadar dokunulmaz (K6)."""
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    cozum = _abonelik_plani(db, olay, kullanici)
    if isinstance(cozum, Sonuc):
        return cozum
    abonelik_id, plan = cozum
    if not _abonelik_eslesiyor(kullanici, abonelik_id):
        return _atla(HATA_ABONELIK_ESKI, kullanici)
    veri = olay.veri
    dusen = 0
    if _dize(veri, "status") == ABONELIK_AKTIF:
        # Eski plan `plan_uygula`dan ÖNCE okunur: ORM `update()` oturumdaki nesneyi de eşitler (`synchronize_session`),
        # sonra okunan `kullanici.plan` yeni plan olur ve düşürme hiç görünmezdi (ölçüldü).
        eski_plan = kullanici.plan
        plan_bitis = _donem_sonu(veri) if veri.get("cancel_at_period_end") is True else None
        plan_uygula(db, kullanici.id, plan, abonelik_id=abonelik_id, plan_bitis=plan_bitis)
        dusen = _dusur(db, kullanici.id, eski_plan, plan, abonelik_id, an)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), abonelik=abonelik_id, plan=plan,
                durum=_dize(veri, "status"), dusen=dusen)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


def _subscription_canceled(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    """Plan KALIR, `plan_bitis` = dönem sonu — kullanıcı ödediği dönemi kullanır (K6). Anında iptalde `revoked` hemen ardından gelir."""
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    abonelik_id = olay.nesne_id
    if abonelik_id is None:
        return _atla(HATA_NESNE_YOK, kullanici)
    if not _abonelik_eslesiyor(kullanici, abonelik_id):
        return _atla(HATA_ABONELIK_ESKI, kullanici)
    plan_bitis = _donem_sonu(olay.veri)
    _plan_bitis_yaz(db, kullanici.id, plan_bitis)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), abonelik=abonelik_id,
                plan_bitis=zaman.damga_utc(plan_bitis) if plan_bitis is not None else None)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


def _subscription_uncanceled(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    abonelik_id = olay.nesne_id
    if abonelik_id is None:
        return _atla(HATA_NESNE_YOK, kullanici)
    if not _abonelik_eslesiyor(kullanici, abonelik_id):
        return _atla(HATA_ABONELIK_ESKI, kullanici)
    _plan_bitis_yaz(db, kullanici.id, None)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), abonelik=abonelik_id)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


def _subscription_revoked(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    """Erişim bitti (dönem sonu ya da dunning sonu): `free` + hibe kovası ücretsiz hibeye iner (`sona_erme`), paket kovası DURUR."""
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    abonelik_id = olay.nesne_id
    if abonelik_id is None:
        return _atla(HATA_NESNE_YOK, kullanici)
    if not _abonelik_eslesiyor(kullanici, abonelik_id):
        return _atla(HATA_ABONELIK_ESKI, kullanici)
    eski_plan = kullanici.plan   # `plan_uygula`dan önce (gerekçe `_subscription_updated`)
    plan_uygula(db, kullanici.id, planlar.PLAN_VARSAYILAN, abonelik_id=None)
    dusen = _dusur(db, kullanici.id, eski_plan, planlar.PLAN_VARSAYILAN, abonelik_id, an)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), abonelik=abonelik_id,
                plan=planlar.PLAN_VARSAYILAN, dusen=dusen)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


def _customer(db: Session, olay: polar.Olay, an: dt.datetime) -> Sonuc:
    kullanici = kullaniciyi_coz(db, olay)
    if kullanici is None:
        return _atla(HATA_KULLANICI_YOK)
    _, musteri_id = _musteri(olay)
    cakisma = _musteriyi_bagla(db, kullanici, musteri_id)
    if cakisma is not None:
        return _atla(cakisma, kullanici)
    gunluk.olay(_gunluk, f"odeme.{olay.tur}", kullanici_id=str(kullanici.id), musteri=musteri_id)
    return Sonuc(DURUM_ISLENDI, kullanici_id=kullanici.id)


_Isleyici = Callable[[Session, polar.Olay, dt.datetime], Sonuc]

_ISLEYICILER: dict[str, _Isleyici] = {
    "order.paid": _order_paid,
    "order.refunded": _order_refunded,
    "subscription.active": _subscription_active,
    "subscription.updated": _subscription_updated,
    "subscription.canceled": _subscription_canceled,
    "subscription.uncanceled": _subscription_uncanceled,
    "subscription.revoked": _subscription_revoked,
    "customer.created": _customer,
    "customer.updated": _customer,
}
# Sahibin Polar panelinde uç noktaya seçeceği olaylar (belge §3 "Sahibin adımı"). Listede olmayan
# tür gelirse kaydedilir, 200 `atlandi` — Polar yeniden denemez, admin sekmesinde görünür.
ISLENEN_TURLER: frozenset[str] = frozenset(_ISLEYICILER)


def isle(db: Session, olay: polar.Olay, *, an: dt.datetime | None = None) -> Sonuc:
    """Doğrulanmış olayı kaydet + işle + kapat — TEK transaksiyon (çağıran commit eder; gerekçe modül başında).

    Yinelenen teslimat (`webhook_id` çakışır) → `yinelenen`, hiçbir şey yazılmaz.
    Tanınmayan tür → kaydedilir, `atlandi` (hata yok). İşleyicinin "hata ama 200"
    dönüşleri satıra `hata` olarak yazılır; istisna yukarıya çıkar (rota 500),
    satır rollback ile gider.
    """
    an = an if an is not None else zaman.an()
    olay_id = olayi_kaydet(db, olay, an)
    if olay_id is None:
        gunluk.olay(_gunluk, "odeme.yinelenen", tur=olay.tur, webhook_id=olay.webhook_id)
        return Sonuc(DURUM_YINELENEN)
    isleyici = _ISLEYICILER.get(olay.tur)
    sonuc = isleyici(db, olay, an) if isleyici is not None else Sonuc(DURUM_ATLANDI)
    _kapat(db, olay_id, an, sonuc)
    return sonuc
