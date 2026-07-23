"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import datetime as _dt
import io
import os
import subprocess
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field, field_validator

import azure_client as ac
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
COMPOSITE_SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="GPT-Image Studio")


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
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
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


class LogoRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)


@app.post("/api/logo")
def add_logo(req: LogoRequest) -> dict:
    src_id = os.path.basename(req.id)
    src_path = os.path.join(OUTPUT_DIR, f"{src_id}.png")
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail="kaynak görsel bulunamadı")

    # kaynak metadata'sını history'den bul (prompt/size korunur)
    src_meta = next((h for h in storage.list_history(OUTPUT_DIR) if h["id"] == src_id), {})

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_out = tmp.name
    try:
        result = subprocess.run(
            ["python3", COMPOSITE_SCRIPT, src_path, tmp_out],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500,
                                detail=f"Logo bindirme başarısız: {result.stderr[:200]}")
        with open(tmp_out, "rb") as f:
            logo_bytes = f.read()
    finally:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)

    record = storage.save(
        logo_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


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
