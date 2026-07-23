"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import datetime as _dt
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import azure_client as ac
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")

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
def generate(req: GenerateRequest):
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
def history():
    return {"images": storage.list_history(OUTPUT_DIR)}


@app.get("/output/{filename}")
def output_file(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# static/ dosyalarını /static altında servis et (index route'undan sonra mount)
# STATIC_DIR Task 6'da oluşturulacak; mount import anında hata vermesin diye
# önce garanti altına alınır.
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
