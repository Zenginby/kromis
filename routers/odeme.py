# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Ödeme uçları — `POST /api/odeme/webhook` (Faz 4 / 3; docs/faz4-odeme-abonelik-kvkk.md §3).

OTURUMSUZ, İMZALI, ADMİN BAĞLAMINDA. İsteği Polar'ın sunucusu atar: çerez yok,
`Origin` yok (`services/koken.py` başlıksız POST'u geçirir — tarayıcı dışı
istemci), dil yok. Kimlik = Standard Webhooks imzası (`services/polar.olay_dogrula`);
o yüzden rota `KAPILI` dışında ve tests/test_kimlik.py `ACIK_ROTALAR`da
gerekçesiyle. Gövde HAM bayt okunur (`request.stream()`, tavanlı): imza gövdenin
baytları üstünde, JSON'a çevrilmiş hâli değil — Pydantic gövde modeli olsaydı
FastAPI önce ayrıştırır, yeniden serileştirme baytları değiştirirdi.

Yazım `kiraci.baglam(rol=ADMIN)` altında: `kredi_hareketleri` ve `siparisler`
`yonetici_ekler` politikası (K4, `YONETICI_EKLER_TABLOLARI`), hedef kullanıcı
olaydan çözülür (`services/odeme.kullaniciyi_coz`). İş iş parçacığı havuzunda
(`run_in_threadpool`): `Session` senkron, rota gövdeyi `await` ile okuduğu için
async — `kimlik.aktif_kullanici`nin deyimi. Bağlam `ContextVar`, havuza KOPYASI
gider (`kiraci` modül başı).

DURUM KODLARI (belge §3): sır yapılandırılmamış **503** (`odeme_yapilandirilmadi`
— sırsız uç hiçbir gövdeye "geçerli" demez), gövde tavanı üstü **413**
(`govde_buyuk` — HMAC'ten önce, Polar yükleri birkaç KB), imza/zaman/başlık
hatası **400** (`imza_gecersiz`), zarf hatası **400** (`govde_gecersiz`),
işlenen/yinelenen/atlanan **200** `{"durum": …}` (+`hata` kodu atlandıysa),
iç hata **500** (istisna yukarıya: `db.oturum` rollback eder — olay satırı da
gider, Polar yeniden dener, temiz gelir; `olay=odeme.hata` ERROR satırı Sentry'ye).
`detail` değerleri KOD, cümle değil: okuyucu Polar'ın panelindeki teslimat
günlüğü, kullanıcı değil (tests/test_i18n.py sınıflandırması — konuşmayan).

DİZİN OKUMAZ, ayar nesnesi almaz; `ADMIN_ROTALAR`da değil (admin kapısı taşımaz).
Rota 70 → 71 (`tests/test_app_bolme.py`).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from services import gunluk, kiraci, odeme, polar
from services.db import OTURUM

router = APIRouter()

_gunluk = logging.getLogger("kromis.odeme")

# Polar yükleri birkaç KB (en büyüğü abonelik: ürün + fiyatlar + faydalar ≈ 10 KB).
# 256 KiB rahat tavan; üstü HMAC hesaplanmadan 413 — internete açık uçta bedava koruma.
AZAMI_GOVDE = 256 * 1024

KOD_YAPILANDIRILMADI = "odeme_yapilandirilmadi"
KOD_GOVDE_BUYUK = "govde_buyuk"
KOD_IMZA_GECERSIZ = "imza_gecersiz"
KOD_GOVDE_GECERSIZ = "govde_gecersiz"


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
