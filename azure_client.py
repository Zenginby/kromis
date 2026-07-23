"""Azure gpt-image-2 istemcisi. Kimlik `~/.config/claude-tools/azure-gpt-image2.env`'den okunur."""
from __future__ import annotations

import base64

MODEL_NAME = "gpt-image-2"
ALLOWED_SIZES = {"1024x1024", "1024x1536", "1536x1024"}
ALLOWED_QUALITIES = {"low", "medium", "high"}


def build_payload(prompt: str, size: str, quality: str, n: int) -> dict:
    return {
        "model": MODEL_NAME,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": n,
    }


def decode_images(response_json: dict) -> list[bytes]:
    return [base64.b64decode(item["b64_json"]) for item in response_json["data"]]


def map_error(status_code: int, body: dict | None) -> str:
    detail = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            detail = str(err.get("message", ""))
        elif isinstance(err, str):
            detail = err
    if status_code == 401:
        return "Azure yetkilendirme hatası (401): API key geçersiz veya süresi dolmuş."
    if status_code == 429:
        return "İstek limiti aşıldı (429): biraz bekleyip tekrar deneyin."
    if status_code == 400 and "content" in detail.lower():
        return "İçerik politikası reddi: prompt Azure tarafından engellendi."
    return f"Azure isteği başarısız (HTTP {status_code})." + (f" {detail}" if detail else "")
