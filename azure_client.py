"""Azure gpt-image-2 istemcisi. Kimlik `~/.config/claude-tools/azure-gpt-image2.env`'den okunur."""
from __future__ import annotations

import base64
import os

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


DEFAULT_ENV_PATH = os.path.expanduser("~/.config/claude-tools/azure-gpt-image2.env")
REQUEST_TIMEOUT = 120.0


class AzureImageError(Exception):
    """Kullanıcıya gösterilebilir Azure hatası (mesajı map_error çıktısıdır)."""


def load_credentials(env_path: str | None = None) -> tuple[str, str]:
    path = env_path or DEFAULT_ENV_PATH
    key = url = ""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip().strip('"').strip("'")
            if name == "AZURE_IMAGE_API_KEY":
                key = value
            elif name == "AZURE_IMAGE_BASE_URL":
                url = value
    if not key or not url:
        raise AzureImageError("Kimlik bilgileri eksik: AZURE_IMAGE_API_KEY / AZURE_IMAGE_BASE_URL.")
    return key, url


def generate(prompt, size, quality, n, *, client=None, credentials=None) -> list[bytes]:
    key, base_url = credentials if credentials else load_credentials()
    endpoint = base_url.rstrip("/") + "/images/generations"
    payload = build_payload(prompt, size, quality, n)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    owns_client = client is None
    if owns_client:
        import httpx
        client = httpx.Client()
    try:
        resp = client.post(endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    finally:
        if owns_client:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise AzureImageError(map_error(resp.status_code, body))
    return decode_images(resp.json())


def edit(prompt, image_bytes, filename, size, quality, n, *, client=None, credentials=None) -> list[bytes]:
    key, base_url = credentials if credentials is not None else load_credentials()
    endpoint = base_url.rstrip("/") + "/images/edits"
    headers = {"Authorization": f"Bearer {key}"}  # Content-Type YOK: multipart client set eder
    data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": str(n),
    }
    files = {"image": (filename, image_bytes, "image/png")}

    owns_client = client is None
    if owns_client:
        import httpx
        client = httpx.Client()
    try:
        resp = client.post(endpoint, headers=headers, data=data, files=files, timeout=REQUEST_TIMEOUT)
    finally:
        if owns_client:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise AzureImageError(map_error(resp.status_code, body))
    return decode_images(resp.json())
