# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ödeme uçları — webhook (Faz 4 / 3), checkout / portal / ürün listesi (Faz 4 / 4; belge §3, §4).

DÖRT ROTA, ÜÇ KİMLİK DÜZENİ:

* `POST /api/odeme/webhook` — OTURUMSUZ, İMZALI, ADMİN BAĞLAMINDA. İsteği
  Polar'ın sunucusu atar: çerez yok, `Origin` yok (`services/koken.py`
  başlıksız POST'u geçirir — tarayıcı dışı istemci), dil yok. Kimlik =
  Standard Webhooks imzası (`services/polar.olay_dogrula`); o yüzden rota
  `KAPILI` dışında ve tests/test_kimlik.py `ACIK_ROTALAR`da gerekçesiyle.
  Gövde HAM bayt okunur (`request.stream()`, tavanlı): imza gövdenin baytları
  üstünde, JSON'a çevrilmiş hâli değil — Pydantic gövde modeli olsaydı FastAPI
  önce ayrıştırır, yeniden serileştirme baytları değiştirirdi. Yazım
  `kiraci.baglam(rol=ADMIN)` altında: `kredi_hareketleri` ve `siparisler`
  `yonetici_ekler` politikası (K4), hedef kullanıcı olaydan çözülür.
* `POST /api/odeme/checkout`, `GET /api/odeme/portal` — OTURUMLU (`KAPILI`,
  `DIZINSIZ_KAPILI`): kullanıcı kendi adına Polar'a gider. Polar'ın
  BARINDIRILAN sayfaları (K7): cevap `{"url"}`, ön yüz `location.assign`
  yapar — 303 DEĞİL, `fetch` sarmalı JSON bekler (core.js). Kart verisi
  alanımıza hiç girmez.
* `GET /api/odeme/urunler` — OTURUMSUZ (fiyat listesi herkese; `ACIK_ROTALAR`
  gerekçesiyle): aktif ürünler + `PLANLAR` kuralları, satış sayfasının verisi.
  `urunler` politikasız tablo (ALTYAPI), kullanıcı verisi taşımaz.

CHECKOUT KAPILARI (sırasıyla; hepsi `detail={"kod": …}` — cümle YOK, ön yüz
kodu kendi dilinde kurar, `services/kapilar.check_plan`ın deseni):
404 `err.urun_yok` (bilinmeyen ya da arşivlenmiş ürün) → 409
`err.abonelik_var` + `{"portal": true}` (ücretli plandaki kullanıcı PLAN ürünü
seçti: plan değişikliği PORTALDAN — Polar oranlamayı orada yapar, ikinci
abonelik açılmaz; paket ürünü serbest) → 412 `err.sartlar_gerekli`
(`sartlar_kabul_at` NULL ve gövdede `sartlar_kabul: true` yok; kutu işaretli
gelirse `odeme.sartlar_kabul_yaz` — `SARTLAR_SURUMU` yer tutucusu, 6. görev
`HUKUK_SURUMU` ile değiştirir) → Polar. Polar SDK'sı ya da ağ düşerse **502**
`err.odeme_saglayici` + `olay=odeme.saglayici_hata` ERROR (Sentry): bizim
hatamız değil, kullanıcı "az sonra yeniden dene" görür. `success_url`
`{koken}/odeme/tesekkur?checkout_id={CHECKOUT_ID}` (`koken.taban`: `KROMIS_KOKEN`
ya da isteğin kökeni) — teşekkür sayfası bakiyeyi yoklar (webhook gecikmesi).
`external_customer_id` = `kullanicilar.id` ve `metadata` (`kullanici_id`,
`urun_id`): webhook'un kullanıcıyı çözdüğü iki yol.

WEBHOOK DURUM KODLARI (belge §3): sır yapılandırılmamış **503**
(`odeme_yapilandirilmadi` — sırsız uç hiçbir gövdeye "geçerli" demez), gövde
tavanı üstü **413** (`govde_buyuk` — HMAC'ten önce, Polar yükleri birkaç KB),
imza/zaman/başlık hatası **400** (`imza_gecersiz`), zarf hatası **400**
(`govde_gecersiz`), işlenen/yinelenen/atlanan **200** `{"durum": …}` (+`hata`
kodu atlandıysa), iç hata **500** (istisna yukarıya: `db.oturum` rollback eder —
olay satırı da gider, Polar yeniden dener, temiz gelir; `olay=odeme.hata` ERROR
satırı Sentry'ye). `detail` değerleri KOD, cümle değil: okuyucu Polar'ın
panelindeki teslimat günlüğü, kullanıcı değil (tests/test_i18n.py
sınıflandırması — konuşmayan; checkout kodları da öyle, cümleyi ön yüz kurar).

DİZİN OKUMAZ, ayar nesnesi almaz; `ADMIN_ROTALAR`da değil (admin kapısı taşımaz).
Rota 70 → 71 (Faz 4 / 3) → 74 (Faz 4 / 4; tests/test_app_bolme.py).
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from services import defter, gunluk, kimlik, kiraci, koken, odeme, planlar, polar, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

_gunluk = logging.getLogger("kromis.odeme")

# Polar yükleri birkaç KB (en büyüğü abonelik: ürün + fiyatlar + faydalar ≈ 10 KB).
# 256 KiB rahat tavan; üstü HMAC hesaplanmadan 413 — internete açık uçta bedava koruma.
AZAMI_GOVDE = 256 * 1024

KOD_YAPILANDIRILMADI = "odeme_yapilandirilmadi"
KOD_GOVDE_BUYUK = "govde_buyuk"
KOD_IMZA_GECERSIZ = "imza_gecersiz"
KOD_GOVDE_GECERSIZ = "govde_gecersiz"

# Checkout/portal `detail.kod` değerleri — i18n anahtarı, ön yüz çevirir (planlar.js, settings.js).
KOD_URUN_YOK = "err.urun_yok"
KOD_ABONELIK_VAR = "err.abonelik_var"
KOD_SARTLAR_GEREKLI = "err.sartlar_gerekli"
KOD_MUSTERI_YOK = "err.musteri_yok"
KOD_SAGLAYICI = "err.odeme_saglayici"

# Teşekkür sayfasının yolu; `{CHECKOUT_ID}` Polar'ın yer tutucusu (SDK `CheckoutCreate.success_url`).
TESEKKUR_YOLU = "/odeme/tesekkur"


class CheckoutIstegi(BaseModel):
    """`{"urun_id": <uuid>, "sartlar_kabul": bool}` — `urun_id` BİZİM `urunler.id`miz (Polar kimliği istemciye gitmez)."""
    urun_id: uuid.UUID
    sartlar_kabul: bool = False


async def _govde(request: Request) -> bytes:
    """Gövdeyi parça parça okur, tavanı aşan yerde keser — `Content-Length` yazmayan (chunked) istemci
    belleğe sınırsız bayt dolduramasın; `request.body()` önce hepsini okurdu."""
    parcalar: list[bytes] = []
    toplam = 0
    async for parca in request.stream():
        toplam += len(parca)
        if toplam > AZAMI_GOVDE:
            raise HTTPException(status_code=413, detail=KOD_GOVDE_BUYUK)
        parcalar.append(parca)
    return b"".join(parcalar)


def _isle(db: Session, olay: polar.Olay) -> odeme.Sonuc:
    """Havuz iş parçacığında: admin bağlamı + işleme; istisna günlüğe (ERROR) ve yukarıya."""
    try:
        with kiraci.baglam(rol=kiraci.ADMIN, oturum=db):
            return odeme.isle(db, olay)
    except Exception:
        _gunluk.error("polar olayi islenemedi", exc_info=True,
                      extra={"olay": "odeme.hata", "tur": olay.tur, "webhook_id": olay.webhook_id})
        raise


@router.post("/api/odeme/webhook")
async def webhook(request: Request, db: Session = OTURUM) -> dict:
    """Polar webhook'u: imza → kayıt → defter/plan; cevap `{"durum": "islendi"|"yinelenen"|"atlandi"[, "hata"]}`."""
    sir = polar.webhook_sirri()
    if not sir:
        raise HTTPException(status_code=503, detail=KOD_YAPILANDIRILMADI)
    beyan = request.headers.get("content-length")
    if beyan is not None and beyan.isdigit() and int(beyan) > AZAMI_GOVDE:
        raise HTTPException(status_code=413, detail=KOD_GOVDE_BUYUK)
    govde = await _govde(request)
    try:
        olay = polar.olay_dogrula(govde, request.headers, sir=sir)
    except polar.ImzaHatasi:
        gunluk.olay(_gunluk, "odeme.imza_gecersiz", seviye=logging.WARNING,
                    webhook_id=request.headers.get(polar.BASLIK_ID))
        raise HTTPException(status_code=400, detail=KOD_IMZA_GECERSIZ)
    except polar.YukHatasi:
        raise HTTPException(status_code=400, detail=KOD_GOVDE_GECERSIZ)
    sonuc = await run_in_threadpool(_isle, db, olay)
    gunluk.olay(_gunluk, "odeme.webhook", tur=olay.tur, webhook_id=olay.webhook_id, durum=sonuc.durum,
                hata=sonuc.hata, kullanici_id=str(sonuc.kullanici_id) if sonuc.kullanici_id else None,
                kredi=sonuc.kredi)
    return sonuc.json()


# ─────────────────────────────────────────────────────── Faz 4 / 4: satış yüzü

def _saglayici_hatasi(islem: str, kullanici: Kullanici, hata: Exception) -> HTTPException:
    """Polar SDK/ağ istisnası → 502 `err.odeme_saglayici`; ERROR satırı `exc_info` ile (Sentry)."""
    _gunluk.error("polar %s basarisiz", islem, exc_info=hata,
                  extra={"olay": "odeme.saglayici_hata", "islem": islem, "kullanici_id": str(kullanici.id)})
    return HTTPException(status_code=502, detail={"kod": KOD_SAGLAYICI})


@router.post("/api/odeme/checkout")
def checkout(req: CheckoutIstegi, request: Request, db: Session = OTURUM,
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Ürün → Polar checkout URL'si (kapılar ve gerekçeleri modül başında): `{"url": …}`."""
    urun = odeme.urun_bul_id(db, req.urun_id)
    if urun is None:
        raise HTTPException(status_code=404, detail={"kod": KOD_URUN_YOK})
    # Plan değişikliği PORTALDAN: ücretli plandaki kullanıcının ikinci bir abonelik
    # açmasını engeller (Polar oranlar/proration'ı portalda kendisi yapar). Paket
    # ürünü serbest — abonelikten bağımsız tek seferlik satın alma.
    plan = defter.plan_oku(db, kullanici.id)
    if urun.tur == odeme.URUN_PLAN and plan != planlar.PLAN_VARSAYILAN:
        # `plan_bitis` (iptal edilmiş aboneliğin dönem sonu, yoksa null): sayfa "dönem sonunda
        # ücretsiz plana geçer" diyebilsin — kullanıcı zaten iptal ettiyse portal yerine beklemesi yeter.
        bitis = defter.plan_bitis_oku(db, kullanici.id)
        raise HTTPException(status_code=409, detail={"kod": KOD_ABONELIK_VAR, "portal": True, "plan": plan,
                                                     "plan_bitis": zaman.damga_utc(bitis) if bitis else None})
    an = zaman.an()
    if odeme.sartlar_kabul_at_oku(db, kullanici.id) is None:
        if not req.sartlar_kabul:
            raise HTTPException(status_code=412, detail={"kod": KOD_SARTLAR_GEREKLI, "surum": odeme.SARTLAR_SURUMU})
        # Polar çağrısından ÖNCE yazmak güvenli: oturum istek kapsamlı (`db.oturum`), 502'nin
        # `HTTPException`ı onu ROLLBACK eder — Polar düşerse onay damgası da gitmez, kullanıcı yeniden onaylar.
        odeme.sartlar_kabul_yaz(db, kullanici.id, an)
    success_url = f"{koken.taban(request)}{TESEKKUR_YOLU}?checkout_id={{CHECKOUT_ID}}"
    try:
        url = polar.checkout_ac(urun_id=urun.polar_urun_id, external_customer_id=str(kullanici.id),
                                customer_email=kullanici.eposta, success_url=success_url,
                                metadata={"kullanici_id": str(kullanici.id), "urun_id": str(urun.id)})
    except Exception as hata:   # noqa: BLE001 — SDK'nın istisna ailesi ve ağ hataları tek kapıdan 502
        raise _saglayici_hatasi("checkout", kullanici, hata) from hata
    gunluk.olay(_gunluk, "odeme.checkout", kullanici_id=str(kullanici.id), urun=urun.polar_urun_id, tur=urun.tur)
    return {"url": url}


@router.get("/api/odeme/portal")
def portal(db: Session = OTURUM, kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Polar müşteri portalı URL'si: `{"url": …}`; hiç satın almamış (`polar_musteri_id` NULL) → 404 `err.musteri_yok`."""
    musteri_id = odeme.polar_musteri_id_oku(db, kullanici.id)
    if not musteri_id:
        raise HTTPException(status_code=404, detail={"kod": KOD_MUSTERI_YOK})
    try:
        url = polar.portal_baglantisi(musteri_id)
    except Exception as hata:   # noqa: BLE001 — aynı gerekçe
        raise _saglayici_hatasi("portal", kullanici, hata) from hata
    gunluk.olay(_gunluk, "odeme.portal", kullanici_id=str(kullanici.id))
    return {"url": url}


@router.get("/api/odeme/urunler")
def urunler(db: Session = OTURUM) -> dict:
    """Satış sayfasının verisi (oturumsuz): aktif ürünler + plan kuralları (`PLANLAR`: hibe, filigran, video, rank)."""
    return {
        "urunler": [odeme.urun_json(u) for u in odeme.aktif_urunler(db)],
        "planlar": {ad: {"aylik_hibe": p.aylik_hibe, "filigran": p.filigran, "video": p.video, "rank": p.rank}
                    for ad, p in planlar.PLANLAR.items()},
    }
