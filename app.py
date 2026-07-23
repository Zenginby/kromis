"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import azure_client as ac
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
COMPOSITE_SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")

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


@app.get("/api/history")
def history() -> dict:
    return {"images": storage.list_history(OUTPUT_DIR)}


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
