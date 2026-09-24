# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Bindirme uçları: logo/afiş filigranı ve kullanıcının varlık kütüphanesi."""
from __future__ import annotations

import base64
import io
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse, Response
from PIL import Image
from sqlalchemy.orm import Session

import composite
import i18n
from models import BannerRequest, LogoRequest
from services import ayar, depo_medya, depo_varlik, dil, dosya, gorsel, kapilar, kimlik, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# Varlık kütüphanesi DB'de (Faz 1 / 6): kayıt `varliklar` satırı, dosya
# kullanıcının `assets_dir`inde aynı yerleşimle. Bindirilecek varlık satır VE
# dosya ister (`depo_varlik.dosya_yolu`); `assets_store` buradan okunmaz
# (bekçisi tests/test_galeri_db.py). Önizleme rotaları da bu yüzden `Session`
# alıyor: bindirdikleri varlığı DB'den buluyorlar, diske yazmıyorlar.
#
# Dosyanın YERİ bir `Depo` (Faz 2 / 2, services/dosya.py): kaynak görsel ve
# bindirilecek varlık depodan BAYT olarak okunur (`gorsel.read_png_file`,
# `depo.oku`) ve `composite`e `io.BytesIO` ile verilir — kovada dosya yolu
# yok, 10 MB tavanı (`gorsel.MAX_UPLOAD_BYTES`) belleği karşılıyor. Sonuç
# `depo_medya.kaydet(depo=…)` ile aynı depoya. `/assets/{kind}/{filename}`
# kovada 302 → ön imzalı URL, yerelde `FileResponse` (galeri.py'nin kararı).


def _composite_logo(src_path: str, req: LogoRequest, db: Session, kullanici_id: uuid.UUID,
                    assets_dir: str, depo: dosya.Depo) -> bytes:
    """Logo/motto filigranını süreç içinde bindirir (composite.py).

    Bindirilecek görsel HER ZAMAN kullanıcının kütüphanesinden gelir. Eskiden
    `asset_id` boş bırakılabilir ve pakete gömülü yerleşik logo çiftine düşülürdü;
    uygulama marka-nötr olduğundan o varsayılan yok — seçim yapılmadıysa istek
    422 ile reddedilir (modelde `asset_id` zorunlu), bulunamazsa 404.
    """
    if not req.asset_id:
        raise HTTPException(status_code=422, detail=i18n.t("err.pick_an_image", dil.aktif()))
    overlay_path = depo_varlik.dosya_yolu(db, kullanici_id, req.asset_kind,
                                          os.path.basename(req.asset_id), assets_dir, depo=depo)
    if overlay_path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    try:
        return composite.composite_logo(
            io.BytesIO(gorsel.read_png_file(src_path, depo=depo)),
            logo_path=io.BytesIO(depo.oku(overlay_path)),
            position=req.position, scale=req.size,
            shadow_alpha=req.shadow_alpha, shadow_blur=req.shadow_blur,
            offset_x=req.offset_x, offset_y=req.offset_y,
        )
    except Exception as exc:
        # Geniş yakalama bilinçli: PIL'in DecompressionBombError'ı doğrudan
        # Exception'dan türüyor, OSError/ValueError ile sınırlı bir except onu
        # kaçırıp kullanıcıya çıplak bir sunucu hatası gösteriyordu. Buradaki
        # sözleşme "bindirme neyle patlarsa patlasın Türkçe 500 dön".
        raise HTTPException(
            status_code=500,
            # str(exc) boş olabilir (argümansız istisna) — o zaman sınıf adı
            # hiç yoktan iyidir. `exc or ...` işe yaramaz: istisna nesneleri
            # her zaman truthy.
            detail=i18n.t("err.overlay_failed", dil.aktif(), hata=str(exc) or type(exc).__name__)) from exc


def _logo_src_path(image_id: str, output_dir: str, depo: dosya.Depo) -> str:
    return gorsel.output_png_path(image_id, output_dir, depo=depo)


@router.post("/api/logo/preview")
def preview_logo(req: LogoRequest, db: Session = OTURUM,
                 ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                 kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                 depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    """Seçeneklerle geçici bir logo önizlemesi üretir — diske/geçmişe KAYDETMEZ."""
    src_path = _logo_src_path(req.id, ayarlar.output_dir, depo)
    logo_bytes = _composite_logo(src_path, req, db, kullanici.id, ayarlar.assets_dir, depo)
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@router.post("/api/logo")
def add_logo(req: LogoRequest, db: Session = OTURUM,
             ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
             depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    output_dir = ayarlar.output_dir
    src_path = _logo_src_path(req.id, output_dir, depo)
    src_id = os.path.basename(req.id)

    # Kaynağın meta'sı `medya` satırından (prompt/size korunur); kaydı olmayan
    # dosya `{}` — bindirme yine yapılır, alanlar boş kalır (eski davranış).
    src_meta = depo_medya.bul(db, kullanici.id, src_id) or {}

    logo_bytes = _composite_logo(src_path, req, db, kullanici.id, ayarlar.assets_dir, depo)
    record = depo_medya.kaydet(
        db, kullanici.id, logo_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id,
         # türev, kaynağın klasöründe kalır
         "folder_id": src_meta.get("folder_id"),
         # palet de devralınır: logo bindirince renk şeridi kaybolmasın
         "palette": src_meta.get("palette"),
         "prompt_sent": src_meta.get("prompt_sent"),
         # Model de devralınıyor: bindirme TÜREV, kendi başına bir üretim
         # değil. Geçilmezse kayda varsayılan model yazılırdı — Nano Banana ile
         # üretilmiş bir görselin logolu hâli "azure-gpt-image-2" görünürdü.
         "model": src_meta.get("model")},
        output_dir, now=zaman.an(), depo=depo,
    )
    return {"image": record}


def _composite_banner(src_path: str | io.BytesIO, banner_path: str | io.BytesIO, edge: str,
                      scale: float = 1.0, align: str = "center", margin: float = 0.0) -> bytes:
    """Banner'ı ölçekleyip üst/alt kenara bindirir (en-boy oranı korunur).

    Girdiler yol ya da açık ikili akış (`composite.composite_logo`nun aynı kararı).

    Logo filigranından farklı: köşe değil, yatay şerit. `scale` görsel genişliğinin
    oranı (1.0 = tam genişlik), `align` artan boşluğun paylaşımı, `margin` seçilen
    kenardan içeri kayma (görsel yüksekliğinin oranı). Alfa maskesiyle paste;
    banner taşarsa kenardan kırpılır (paste otomatik kırpar).
    """
    base = Image.open(src_path).convert("RGBA")
    banner = Image.open(banner_path).convert("RGBA")
    target_w = max(1, round(base.width * scale))
    target_h = max(1, round(banner.height * (target_w / banner.width)))
    banner = banner.resize((target_w, target_h), Image.Resampling.LANCZOS)

    free_x = base.width - target_w
    x = 0 if align == "left" else (free_x if align == "right" else free_x // 2)
    pad = round(base.height * margin)
    y = pad if edge == "top" else base.height - target_h - pad
    y = max(0, min(y, max(0, base.height - target_h)))  # kenar dışına taşmayı engelle

    composed = base.copy()
    composed.paste(banner, (x, y), banner)  # banner alfası maske
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def _banner_asset_path(asset_id: str, db: Session, kullanici_id: uuid.UUID,
                       assets_dir: str, depo: dosya.Depo) -> str:
    path = depo_varlik.dosya_yolu(db, kullanici_id, "banners", os.path.basename(asset_id),
                                  assets_dir, depo=depo)
    if path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.banner_missing", dil.aktif()))
    return path


def _banner_bytes(src_path: str, req: BannerRequest, db: Session, kullanici_id: uuid.UUID,
                  assets_dir: str, depo: dosya.Depo) -> bytes:
    banner_path = _banner_asset_path(req.asset_id, db, kullanici_id, assets_dir, depo)
    return _composite_banner(io.BytesIO(gorsel.read_png_file(src_path, depo=depo)),
                             io.BytesIO(depo.oku(banner_path)),
                             req.edge, req.scale, req.align, req.margin)


@router.post("/api/banner/preview")
def preview_banner(req: BannerRequest, db: Session = OTURUM,
                   ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                   kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                   depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    """Banner'lı geçici bir önizleme üretir — diske/geçmişe KAYDETMEZ."""
    banner_bytes = _banner_bytes(_logo_src_path(req.id, ayarlar.output_dir, depo), req,
                                 db, kullanici.id, ayarlar.assets_dir, depo)
    b64 = base64.b64encode(banner_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@router.post("/api/banner")
def add_banner(req: BannerRequest, db: Session = OTURUM,
               ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
               kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
               depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    output_dir = ayarlar.output_dir
    src_path = _logo_src_path(req.id, output_dir, depo)
    src_id = os.path.basename(req.id)

    src_meta = depo_medya.bul(db, kullanici.id, src_id) or {}

    banner_bytes = _banner_bytes(src_path, req, db, kullanici.id, ayarlar.assets_dir, depo)
    record = depo_medya.kaydet(
        db, kullanici.id, banner_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id,
         "folder_id": src_meta.get("folder_id"),  # türev, kaynağın klasöründe kalır
         "palette": src_meta.get("palette"),
         "prompt_sent": src_meta.get("prompt_sent"),
         # Model de devralınıyor: bindirme TÜREV, kendi başına bir üretim
         # değil. Geçilmezse kayda varsayılan model yazılırdı — Nano Banana ile
         # üretilmiş bir görselin logolu hâli "azure-gpt-image-2" görünürdü.
         "model": src_meta.get("model")},
        output_dir, now=zaman.an(), depo=depo,
    )
    return {"image": record}


@router.post("/api/assets/{kind}")
async def upload_asset(
    kind: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    db: Session = OTURUM,
    ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
    kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
    depo: dosya.Depo = Depends(dosya.depo),
) -> dict:
    """Bir logo/banner PNG'si yükler; doğrulayıp yeniden kodlar ve kütüphaneye ekler.

    `async def` rota: DB çağrısı `run_in_threadpool` ile (belge §1'in sürücü kararı).
    """
    kapilar.check_asset_kind(kind)
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > gorsel.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.file_too_big", dil.aktif()))
    raw = await file.read()
    if len(raw) > gorsel.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.file_too_big", dil.aktif()))
    image_bytes = gorsel.to_png(raw)  # şeffaflığı koruyan RGBA PNG'ye yeniden kodla
    stem = os.path.splitext(os.path.basename(file.filename or ""))[0]
    label = (name.strip() or stem or i18n.t("library.asset"))[:120]
    record = await run_in_threadpool(depo_varlik.kaydet, db, kullanici.id, kind, image_bytes,
                                     label, ayarlar.assets_dir, now=zaman.an(), depo=depo)
    return {"asset": record}


@router.get("/api/assets/{kind}")
def list_assets_route(kind: str, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Bir türün ya da (`all`) hepsinin varlıkları, en yeni başta; dizin okumaz (yalnız satır)."""
    kapilar.check_asset_kind(kind, allow_all=True)
    return {"items": depo_varlik.listele(db, kullanici.id, None if kind == "all" else kind)}


@router.delete("/api/assets/{kind}/{asset_id}")
def delete_asset_route(kind: str, asset_id: str, db: Session = OTURUM,
                       ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                       kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                       depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    kapilar.check_asset_kind(kind)
    aid = os.path.basename(asset_id)
    if not depo_varlik.sil(db, kullanici.id, kind, aid, ayarlar.assets_dir, depo=depo):
        raise HTTPException(status_code=404, detail=i18n.t("err.asset_missing", dil.aktif()))
    return {"deleted": aid}


@router.get("/assets/{kind}/{filename}")
def asset_file(kind: str, filename: str, db: Session = OTURUM,
               ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
               kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
               depo: dosya.Depo = Depends(dosya.depo)) -> Response:
    """Kütüphane karosunun görseli. Dosya adı kullanıcının `varliklar` satırında ARANIYOR
    (Faz 1 / 6): satırı yoksa dosya diskte dursa bile 404 — `/output/{filename}`in kararı.
    Eski `index.json` adı da bu yüzden ayrıca yasaklanmıyor: hiçbir satır o adı taşımaz.
    Kovada 302 → ön imzalı URL (15 dk, `Cache-Control: private`), yerelde `FileResponse`
    — `/output/{filename}`in Faz 2 / 2 kararı (routers/galeri.py::_medya_cevabi)."""
    kapilar.check_asset_kind(kind)
    safe = os.path.basename(filename)
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    path = depo_varlik.dosya_yolu_adiyla(db, kullanici.id, kind, safe, ayarlar.assets_dir, depo=depo)
    if path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    url = depo.url(path, dosya.URL_SURESI)
    if url is not None:
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": dosya.CACHE_CONTROL})
    return FileResponse(path, media_type="image/png")
