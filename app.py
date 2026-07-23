"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import base64
import datetime as _dt
import io
import os
import subprocess
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field, field_validator

import assets_store
import azure_client as ac
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
COMPOSITE_SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 50 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

app = FastAPI(title="GPT-Image Studio")


@app.exception_handler(RequestValidationError)
async def _redact_validation_errors(request: Request, exc: RequestValidationError):
    """Doğrulama hatası gövdesinde API key'i yankılama (FastAPI varsayılanı 'input' döner)."""
    safe = []
    for err in exc.errors():
        err = dict(err)
        if any(str(p) == "api_key" for p in (err.get("loc") or ())):
            err.pop("input", None)
            err.pop("ctx", None)
        safe.append(err)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": safe}))


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    size: str
    quality: str
    n: int = Field(ge=1, le=4)

    @field_validator("size")
    @classmethod
    def _size_ok(cls, v):
        if v not in ac.ALLOWED_SIZES:
            raise ValueError("geçersiz size")
        return v

    @field_validator("quality")
    @classmethod
    def _quality_ok(cls, v):
        if v not in ac.ALLOWED_QUALITIES:
            raise ValueError("geçersiz quality")
        return v


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _to_png(raw: bytes) -> bytes:
    """Yüklenen görseli doğrula ve PNG'ye yeniden kodla. Geçersizse HTTPException(422)."""
    try:
        Image.open(io.BytesIO(raw)).verify()
        im = Image.open(io.BytesIO(raw))
        if im.width * im.height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=422, detail="Görsel çözünürlüğü çok yüksek.")
        im = im.convert("RGBA")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Geçersiz görsel dosyası.")
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


@app.post("/api/generate")
def generate(req: GenerateRequest) -> dict:
    try:
        images = ac.generate(req.prompt, req.size, req.quality, req.n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    records = [
        storage.save(img, {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


@app.post("/api/edit")
async def edit(
    request: Request,
    prompt: str = Form(...),
    size: str = Form(...),
    quality: str = Form(...),
    n: int = Form(...),
    file: UploadFile | None = File(None),
    source_id: str | None = Form(None),
) -> dict:
    if size not in ac.ALLOWED_SIZES or quality not in ac.ALLOWED_QUALITIES:
        raise HTTPException(status_code=422, detail="Geçersiz size veya quality.")
    if not (1 <= n <= 4):
        raise HTTPException(status_code=422, detail="n 1-4 arasında olmalı.")
    if not prompt or len(prompt) > 4000:
        raise HTTPException(status_code=422, detail="prompt 1-4000 karakter olmalı.")
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422, detail="Tam olarak biri gerekli: file veya source_id.")

    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")

    if source_id is not None:
        sid = os.path.basename(source_id)
        src_path = os.path.join(OUTPUT_DIR, f"{sid}.png")
        if not os.path.isfile(src_path):
            raise HTTPException(status_code=404, detail="Kaynak görsel bulunamadı.")
        with open(src_path, "rb") as f:
            image_bytes = f.read()
        filename = f"{sid}.png"
        parent_id = sid
    else:
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
        image_bytes = _to_png(raw)
        filename = "upload.png"
        parent_id = None

    try:
        images = ac.edit(prompt, image_bytes, filename, size, quality, n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    records = [
        storage.save(img, {"prompt": prompt, "size": size, "quality": quality,
                           "parent_id": parent_id}, OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


class SettingsRequest(BaseModel):
    # api_key boş bırakılabilir: mevcut key korunur (endpoint'i tek başına güncelleme).
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(min_length=1, max_length=500)


@app.get("/api/settings")
def get_settings() -> dict:
    """Yapılandırma durumu — API key asla dönmez, yalnızca configured + endpoint."""
    return ac.get_settings_status()


@app.post("/api/settings")
def post_settings(req: SettingsRequest) -> dict:
    """Admin kimlik bilgilerini yalnızca-yazılır kaydeder; durumu döndürür (key'siz).

    api_key boşsa mevcut key korunur — ilk kurulumda ise key zorunludur.
    """
    api_key = req.api_key.strip()
    if not api_key:
        try:
            api_key, _ = ac.load_credentials()
        except ac.AzureImageError:
            raise HTTPException(status_code=422, detail="İlk kurulumda API key gerekli.")
    try:
        ac.save_credentials(api_key, req.base_url)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ac.get_settings_status()


@app.get("/api/history")
def history() -> dict:
    return {"images": storage.list_history(OUTPUT_DIR)}


@app.delete("/api/image/{image_id}")
def delete_image(image_id: str) -> dict:
    iid = os.path.basename(image_id)
    removed = storage.delete(iid, OUTPUT_DIR)
    if not removed:
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return {"deleted": iid}


LOGO_POSITIONS = {
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
}
LOGO_COLORS = {"auto", "blue", "white"}
# Konumlanabilir (logo tarzı) bindirmenin varlığı hangi kütüphaneden gelebilir.
# Banner ayrı bir yerleşim olduğu için burada değil.
OVERLAY_ASSET_KINDS = {"logos", "mottos"}


class LogoRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    # asset_id boş/None => yerleşik KURUM logosu (mavi/beyaz auto). Doluysa
    # asset_kind kütüphanesinden seçilen özel görsel (tek görsel) kullanılır.
    asset_id: str | None = Field(default=None, max_length=64)
    asset_kind: str = "logos"                                # "logos" | "mottos"
    position: str = "bottom-right"
    color: str = "auto"
    size: float = Field(default=0.14, ge=0.04, le=0.5)       # logo genişliği / görsel genişliği
    shadow_alpha: int = Field(default=120, ge=0, le=255)     # 0 = gölge yok
    shadow_blur: int = Field(default=6, ge=0, le=50)

    @field_validator("position")
    @classmethod
    def _position_ok(cls, v):
        if v not in LOGO_POSITIONS:
            raise ValueError("geçersiz position")
        return v

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v):
        if v not in LOGO_COLORS:
            raise ValueError("geçersiz color")
        return v

    @field_validator("asset_kind")
    @classmethod
    def _asset_kind_ok(cls, v):
        if v not in OVERLAY_ASSET_KINDS:
            raise ValueError("geçersiz asset_kind")
        return v


def _composite_logo(src_path: str, req: LogoRequest) -> bytes:
    """composite-logo.py'yi verilen seçeneklerle çalıştırır, sonuç PNG baytlarını döndürür.

    base_image ve output_path ilk iki konumsal argümandır (cmd[2], cmd[3]);
    bayraklar sonradan gelir.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_out = tmp.name
    try:
        cmd = [
            "python3", COMPOSITE_SCRIPT, src_path, tmp_out,
            "--position", req.position,
            "--color", req.color,
            "--scale", str(req.size),
            "--shadow-alpha", str(req.shadow_alpha),
            "--shadow-blur", str(req.shadow_blur),
        ]
        # Özel logo/motto seçildiyse aynı dosyayı her iki varyant olarak geç:
        # renk seçimi (auto/blue/white) hangisine düşerse düşsün tek görsel kullanılır.
        if req.asset_id:
            overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, ASSETS_DIR)
            if overlay_path is None:
                raise HTTPException(status_code=404, detail="görsel bulunamadı")
            cmd += ["--logo-blue", overlay_path, "--logo-white", overlay_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500,
                                detail=f"Logo bindirme başarısız: {result.stderr[:200]}")
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)


def _logo_src_path(image_id: str) -> str:
    src_id = os.path.basename(image_id)
    src_path = os.path.join(OUTPUT_DIR, f"{src_id}.png")
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail="kaynak görsel bulunamadı")
    return src_path


@app.post("/api/logo/preview")
def preview_logo(req: LogoRequest) -> dict:
    """Seçeneklerle geçici bir logo önizlemesi üretir — diske/geçmişe KAYDETMEZ."""
    src_path = _logo_src_path(req.id)
    logo_bytes = _composite_logo(src_path, req)
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@app.post("/api/logo")
def add_logo(req: LogoRequest) -> dict:
    src_path = _logo_src_path(req.id)
    src_id = os.path.basename(req.id)

    # kaynak metadata'sını history'den bul (prompt/size korunur)
    src_meta = next((h for h in storage.list_history(OUTPUT_DIR) if h["id"] == src_id), {})

    logo_bytes = _composite_logo(src_path, req)
    record = storage.save(
        logo_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


BANNER_EDGES = {"top", "bottom"}


class BannerRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)          # bindirilecek görsel (history id)
    asset_id: str = Field(min_length=1, max_length=64)    # kütüphaneden seçilen banner
    edge: str = "bottom"

    @field_validator("edge")
    @classmethod
    def _edge_ok(cls, v):
        if v not in BANNER_EDGES:
            raise ValueError("geçersiz edge")
        return v


def _composite_banner(src_path: str, banner_path: str, edge: str) -> bytes:
    """Banner'ı görselin tüm genişliğine ölçekleyip üst/alt kenara bindirir.

    Logo filigranından farklı: köşe değil, tam-genişlik şerit. Alfa maskesiyle
    paste kullanılır; banner taşarsa kenardan kırpılır (paste otomatik kırpar).
    """
    base = Image.open(src_path).convert("RGBA")
    banner = Image.open(banner_path).convert("RGBA")
    new_h = max(1, round(banner.height * (base.width / banner.width)))
    banner = banner.resize((base.width, new_h), Image.LANCZOS)
    y = 0 if edge == "top" else max(0, base.height - banner.height)
    composed = base.copy()
    composed.paste(banner, (0, y), banner)  # banner alfası maske; taşma kırpılır
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def _banner_asset_path(asset_id: str) -> str:
    path = assets_store.asset_path("banners", asset_id, ASSETS_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail="banner bulunamadı")
    return path


@app.post("/api/banner/preview")
def preview_banner(req: BannerRequest) -> dict:
    """Banner'lı geçici bir önizleme üretir — diske/geçmişe KAYDETMEZ."""
    src_path = _logo_src_path(req.id)
    banner_bytes = _composite_banner(src_path, _banner_asset_path(req.asset_id), req.edge)
    b64 = base64.b64encode(banner_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@app.post("/api/banner")
def add_banner(req: BannerRequest) -> dict:
    src_path = _logo_src_path(req.id)
    src_id = os.path.basename(req.id)
    banner_path = _banner_asset_path(req.asset_id)

    src_meta = next((h for h in storage.list_history(OUTPUT_DIR) if h["id"] == src_id), {})

    banner_bytes = _composite_banner(src_path, banner_path, req.edge)
    record = storage.save(
        banner_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


def _check_asset_kind(kind: str) -> None:
    if kind not in assets_store.KINDS:
        raise HTTPException(status_code=404, detail="bilinmeyen tür")


@app.post("/api/assets/{kind}")
async def upload_asset(
    kind: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
) -> dict:
    """Bir logo/banner PNG'si yükler; doğrulayıp yeniden kodlar ve kütüphaneye ekler."""
    _check_asset_kind(kind)
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    image_bytes = _to_png(raw)  # şeffaflığı koruyan RGBA PNG'ye yeniden kodla
    stem = os.path.splitext(os.path.basename(file.filename or ""))[0]
    label = (name.strip() or stem or "varlık")[:120]
    record = assets_store.save_asset(kind, image_bytes, label, ASSETS_DIR, now=_now())
    return {"asset": record}


@app.get("/api/assets/{kind}")
def list_assets_route(kind: str) -> dict:
    _check_asset_kind(kind)
    return {"items": assets_store.list_assets(kind, ASSETS_DIR)}


@app.delete("/api/assets/{kind}/{asset_id}")
def delete_asset_route(kind: str, asset_id: str) -> dict:
    _check_asset_kind(kind)
    removed = assets_store.delete_asset(kind, asset_id, ASSETS_DIR)
    if not removed:
        raise HTTPException(status_code=404, detail="varlık bulunamadı")
    return {"deleted": os.path.basename(asset_id)}


@app.get("/assets/{kind}/{filename}")
def asset_file(kind: str, filename: str) -> FileResponse:
    _check_asset_kind(kind)
    safe = os.path.basename(filename)
    if not safe or safe in (".", "..") or safe == assets_store.MANIFEST_FILE:
        raise HTTPException(status_code=404, detail="bulunamadı")
    path = os.path.join(ASSETS_DIR, kind, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type="image/png")


@app.get("/output/{filename}")
def output_file(filename: str) -> FileResponse:
    safe = os.path.basename(filename)
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=404, detail="bulunamadı")
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# static/ dosyalarını /static altında servis et (index route'undan sonra mount)
# STATIC_DIR Task 6'da oluşturulacak; mount import anında hata vermesin diye
# önce garanti altına alınır.
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
