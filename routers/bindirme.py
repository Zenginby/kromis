# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Bindirme uçları: logo/afiş filigranı ve kullanıcının varlık kütüphanesi."""
from __future__ import annotations

import base64
import io
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

import assets_store
import composite
import i18n
import storage
from models import BannerRequest, LogoRequest
from services import ayar, dil, gorsel, kapilar, zaman

router = APIRouter()


def _composite_logo(src_path: str, req: LogoRequest, assets_dir: str) -> bytes:
    """Logo/motto filigranını süreç içinde bindirir (composite.py).

    Bindirilecek görsel HER ZAMAN kullanıcının kütüphanesinden gelir. Eskiden
    `asset_id` boş bırakılabilir ve pakete gömülü yerleşik logo çiftine düşülürdü;
    uygulama marka-nötr olduğundan o varsayılan yok — seçim yapılmadıysa istek
    422 ile reddedilir (modelde `asset_id` zorunlu), bulunamazsa 404.
    """
    if not req.asset_id:
        raise HTTPException(status_code=422, detail=i18n.t("err.pick_an_image", dil.aktif()))
    overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, assets_dir)
    if overlay_path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    try:
        return composite.composite_logo(
            src_path,
            logo_path=overlay_path,
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


def _logo_src_path(image_id: str, output_dir: str) -> str:
    return gorsel.output_png_path(image_id, output_dir)


@router.post("/api/logo/preview")
def preview_logo(req: LogoRequest, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    """Seçeneklerle geçici bir logo önizlemesi üretir — diske/geçmişe KAYDETMEZ."""
    src_path = _logo_src_path(req.id, ayarlar.output_dir)
    logo_bytes = _composite_logo(src_path, req, ayarlar.assets_dir)
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@router.post("/api/logo")
def add_logo(req: LogoRequest, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    output_dir = ayarlar.output_dir
    src_path = _logo_src_path(req.id, output_dir)
    src_id = os.path.basename(req.id)

    # kaynak metadata'sını history'den bul (prompt/size korunur)
    src_meta = next((h for h in storage.list_history(output_dir) if h["id"] == src_id), {})

    logo_bytes = _composite_logo(src_path, req, ayarlar.assets_dir)
    record = storage.save(
        logo_bytes,
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
        output_dir, now=zaman.simdi(),
    )
    return {"image": record}


def _composite_banner(src_path: str, banner_path: str, edge: str,
                      scale: float = 1.0, align: str = "center", margin: float = 0.0) -> bytes:
    """Banner'ı ölçekleyip üst/alt kenara bindirir (en-boy oranı korunur).

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


def _banner_asset_path(asset_id: str, assets_dir: str) -> str:
    path = assets_store.asset_path("banners", asset_id, assets_dir)
    if path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.banner_missing", dil.aktif()))
    return path


def _banner_bytes(src_path: str, req: BannerRequest, assets_dir: str) -> bytes:
    return _composite_banner(src_path, _banner_asset_path(req.asset_id, assets_dir), req.edge,
                             req.scale, req.align, req.margin)


@router.post("/api/banner/preview")
def preview_banner(req: BannerRequest, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    """Banner'lı geçici bir önizleme üretir — diske/geçmişe KAYDETMEZ."""
    banner_bytes = _banner_bytes(_logo_src_path(req.id, ayarlar.output_dir), req,
                                 ayarlar.assets_dir)
    b64 = base64.b64encode(banner_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@router.post("/api/banner")
def add_banner(req: BannerRequest, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    output_dir = ayarlar.output_dir
    src_path = _logo_src_path(req.id, output_dir)
    src_id = os.path.basename(req.id)

    src_meta = next((h for h in storage.list_history(output_dir) if h["id"] == src_id), {})

    banner_bytes = _banner_bytes(src_path, req, ayarlar.assets_dir)
    record = storage.save(
        banner_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id,
         "folder_id": src_meta.get("folder_id"),  # türev, kaynağın klasöründe kalır
         "palette": src_meta.get("palette"),
         "prompt_sent": src_meta.get("prompt_sent"),
         # Model de devralınıyor: bindirme TÜREV, kendi başına bir üretim
         # değil. Geçilmezse kayda varsayılan model yazılırdı — Nano Banana ile
         # üretilmiş bir görselin logolu hâli "azure-gpt-image-2" görünürdü.
         "model": src_meta.get("model")},
        output_dir, now=zaman.simdi(),
    )
    return {"image": record}


@router.post("/api/assets/{kind}")
async def upload_asset(
    kind: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
) -> dict:
    """Bir logo/banner PNG'si yükler; doğrulayıp yeniden kodlar ve kütüphaneye ekler."""
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
    record = assets_store.save_asset(kind, image_bytes, label, ayarlar.assets_dir,
                                     now=zaman.simdi())
    return {"asset": record}


@router.get("/api/assets/{kind}")
def list_assets_route(kind: str, ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    kapilar.check_asset_kind(kind, allow_all=True)
    assets_dir = ayarlar.assets_dir
    if kind == "all":
        all_items = []
        for k in assets_store.KINDS:
            all_items.extend(assets_store.list_assets(k, assets_dir))
        all_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"items": all_items}
    return {"items": assets_store.list_assets(kind, assets_dir)}


@router.delete("/api/assets/{kind}/{asset_id}")
def delete_asset_route(kind: str, asset_id: str,
                       ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> dict:
    kapilar.check_asset_kind(kind)
    removed = assets_store.delete_asset(kind, asset_id, ayarlar.assets_dir)
    if not removed:
        raise HTTPException(status_code=404, detail=i18n.t("err.asset_missing", dil.aktif()))
    return {"deleted": os.path.basename(asset_id)}


@router.get("/assets/{kind}/{filename}")
def asset_file(kind: str, filename: str,
               ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> FileResponse:
    kapilar.check_asset_kind(kind)
    safe = os.path.basename(filename)
    if not safe or safe in (".", "..") or safe == assets_store.MANIFEST_FILE:
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    path = os.path.join(ayarlar.assets_dir, kind, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    return FileResponse(path, media_type="image/png")
