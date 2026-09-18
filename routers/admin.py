# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Admin uçları — `/admin` sayfası ve `/api/admin/*` (Faz 2 / 8).

Yedi rota: `GET /admin` (statik sayfa, `services/sablon.py` ile çevrili —
`/giris`in yolu), `GET /api/admin/kullanicilar` (sayfalı, `?q=`),
`GET /api/admin/isler` (`?durum=`, son 200 + özet), `GET /api/admin/metrikler`,
`POST /api/admin/kullanicilar/{id}/tavan` (yaz/sil),
`POST /api/admin/kullanicilar/{id}/oturum-dusur`, `POST /api/admin/isler/{id}/iptal`.

HER API ROTASI `kimlik.admin_kullanici` TAŞIR — tek bağımlılık, tek çözüm:
oturumsuz 401, admin değilse **403** (404 değil; gerekçe services/kimlik.py),
adminse RLS bağlamı `app.rol = 'admin'` aynı transaksiyona. Bekçisi
tests/test_kimlik.py `ADMIN_ROTALAR`: `/api/admin/` altında bu kapıyı
taşımayan rota kırmızı. Sorgular `services/depo_admin.py`de ve KULLANICI
SÜZGEÇSİZ (gerekçesi orada); bu dosya HTTP'yi kurar — durum kodu, gövde,
i18n'li `detail`.

ADMİN YAZIMI GÜNLÜĞE, `denetim` TABLOSUNA DEĞİL (belge §8): üç yazım (tavan,
oturum düşürme, iptal) `logging` ile `olay=admin.*` satırı düşürür — kim
(admin id), kime/neye (hedef), ne. 9. görevin yapısal günlüğü bu satırları
JSON'a çevirecek; Faz 4'ün KVKK/GDPR kalemi denetim tablosu isterse gelir.

DİZİN OKUMAZLAR: ayar nesnesi almazlar (`DIZINSIZ_KAPILI`); sayfa rotası
`ayar.genel` (paylaşılan `static_dir`, `routers/kok.py`nin kararı).
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import i18n
from services import ayar, depo_admin, dil, hesap, kimlik, sablon, zaman
from services.db import OTURUM
from services.tablolar import IS_DURUMLARI, Kullanici

router = APIRouter()

# `olay=admin.*` satırlarının kaynağı; 9. görev biçimleyiciyi bu ada da takar.
_gunluk = logging.getLogger("kromis.admin")


class TavanIstegi(BaseModel):
    """`{"tavan": 500}` yazar, `{"tavan": null}` siler (NULL = ortamın öntanımlısı, services/kota.py)."""
    # Üst sınır keyfî değil: `Integer` sütun 2^31'e kadar ve "sınırsız" demenin
    # yolu NULL — dev bir sayı yazmak yerine tavanı kaldırmak istenen şey.
    tavan: int | None = Field(default=None, ge=1, le=1_000_000_000)


@router.get("/admin")
def admin_sayfasi(kullanici: Kullanici = Depends(kimlik.admin_sayfasi),
                  ayarlar: ayar.Ayarlar = Depends(ayar.genel)) -> HTMLResponse:
    """`static/admin.html` — `index`/`giris` ile aynı yerleştirme; oturumsuz 302, admin değilse 403 HTML."""
    return sablon.sayfa(ayarlar, "admin.html")


@router.get("/api/admin/kullanicilar")
def kullanicilar(q: str | None = Query(default=None, max_length=200),
                 sayfa: int = Query(default=1, ge=1),
                 adet: int = Query(default=depo_admin.SAYFA_ADEDI, ge=1,
                                   le=depo_admin.SAYFA_ADEDI_AZAMI),
                 db: Session = OTURUM,
                 admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Kullanıcı sayfası: e-posta, kayıt, son görülme, `is_admin`, tavan, son 24 sa kredi, aktif iş."""
    satirlar, toplam = depo_admin.kullanicilar(db, q=q or None, sayfa=sayfa, adet=adet)
    return {"kullanicilar": satirlar, "toplam": toplam, "sayfa": sayfa, "adet": adet}


@router.get("/api/admin/isler")
def isler(durum: str | None = Query(default=None), db: Session = OTURUM,
          admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Son 200 iş (herkesin) + özet; `?durum=` `IS_DURUMLARI`ndan biri, başkası 422."""
    if durum is not None and durum not in IS_DURUMLARI:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.is_durumu_gecersiz", dil.aktif(), durum=durum))
    return depo_admin.is_listesi(db, durum=durum)


@router.get("/api/admin/metrikler")
def metrikler(db: Session = OTURUM,
              admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Kuyruk, son 1 sa / 24 sa, model başına p50/p95, platform kredisi, işçiler (services/depo_admin.py)."""
    return depo_admin.metrikler(db)


def _hedef(db: Session, kullanici_id: uuid.UUID) -> Kullanici:
    hedef = depo_admin.kullanici_bul(db, kullanici_id)
    if hedef is None:
        raise HTTPException(status_code=404,
                            detail=i18n.t("err.kullanici_bulunamadi", dil.aktif()))
    return hedef


@router.post("/api/admin/kullanicilar/{kullanici_id}/tavan")
def tavan(kullanici_id: uuid.UUID, req: TavanIstegi, db: Session = OTURUM,
          admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Günlük kredi tavanını yazar/siler; kullanıcının bir sonraki işi yeni tavana göre 429 alır (services/kota.py)."""
    hedef = _hedef(db, kullanici_id)
    depo_admin.tavan_yaz(db, hedef.id, req.tavan)
    _gunluk.info("olay=admin.tavan admin=%s hedef=%s tavan=%s", admin.id, hedef.id, req.tavan)
    return {"id": str(hedef.id), "gunluk_kredi_tavani": req.tavan}


@router.post("/api/admin/kullanicilar/{kullanici_id}/oturum-dusur")
def oturum_dusur(kullanici_id: uuid.UUID, db: Session = OTURUM,
                 admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Kullanıcının BÜTÜN oturumlarını düşürür (`tools/kullanici.py oturum-dusur`un rotası); çerez ölür."""
    hedef = _hedef(db, kullanici_id)
    sayi = depo_admin.oturum_sayisi(db, hedef.id)
    hesap.oturumlari_dusur(db, hedef.id)
    _gunluk.info("olay=admin.oturum_dusur admin=%s hedef=%s adet=%d", admin.id, hedef.id, sayi)
    return {"id": str(hedef.id), "dusurulen": sayi}


@router.post("/api/admin/isler/{is_id}/iptal")
def is_iptal(is_id: uuid.UUID, db: Session = OTURUM,
             admin: Kullanici = Depends(kimlik.admin_kullanici)) -> dict:
    """Herhangi bir kullanıcının BEKLEYEN işini iptal eder; çalışan 409, olmayan 404 (routers/isler.py `is_iptal`in kararları)."""
    an = zaman.an()
    iptal_edildi = depo_admin.is_iptal(db, is_id, an=an)
    satir = depo_admin.is_satiri(db, is_id)
    if satir is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.is_bulunamadi", dil.aktif()))
    if not iptal_edildi:
        raise HTTPException(status_code=409,
                            detail=i18n.t("err.is_iptal_edilemez", dil.aktif(), durum=satir.durum))
    _gunluk.info("olay=admin.is_iptal admin=%s is=%s sahip=%s", admin.id, satir.id, satir.kullanici_id)
    return {"is": depo_admin.is_dokumu(satir)}
