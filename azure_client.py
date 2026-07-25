"""Azure gpt-image-2 istemcisi. Kimlik `~/.config/claude-tools/azure-gpt-image2.env`'den okunur."""
from __future__ import annotations

import base64
import os
import tempfile

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


# Uygulamaya özel kimlik dosyası (admin buradan yazar). Yoksa paylaşılan
# claude-tools dosyasına düşer — böylece mevcut kurulumda kutudan çıktığı gibi çalışır.
APP_ENV_PATH = os.path.expanduser("~/.config/gpt-image-studio/credentials.env")
DEFAULT_ENV_PATH = os.path.expanduser("~/.config/claude-tools/azure-gpt-image2.env")
REQUEST_TIMEOUT = 120.0


class AzureImageError(Exception):
    """Kullanıcıya gösterilebilir Azure hatası (mesajı map_error çıktısıdır)."""


def _parse_env_file(path: str) -> tuple[str, str]:
    """Bir .env dosyasından key/url'yi çıkarır. Dosya yoksa OSError yükselir."""
    key = url = ""
    with open(path, encoding="utf-8") as f:  # yazımla aynı encoding
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
    return key, url


def _candidate_paths(env_path: str | None) -> list[str]:
    """Açık env_path verilirse sadece o; yoksa app dosyası → paylaşılan dosya sırası."""
    if env_path is not None:
        return [env_path]
    return [APP_ENV_PATH, DEFAULT_ENV_PATH]


def _first_complete_credentials(env_path: str | None) -> tuple[str, str] | None:
    """Aday dosyalar içinde hem key hem url'si dolu ilkini döndürür; yoksa None."""
    for path in _candidate_paths(env_path):
        try:
            key, url = _parse_env_file(path)
        except OSError:
            continue
        if key and url:
            return key, url
    return None


def load_credentials(env_path: str | None = None) -> tuple[str, str]:
    creds = _first_complete_credentials(env_path)
    if creds is None:
        raise AzureImageError("Kimlik bilgileri eksik: AZURE_IMAGE_API_KEY / AZURE_IMAGE_BASE_URL.")
    return creds


def save_credentials(api_key: str, base_url: str, env_path: str | None = None) -> str:
    """Kimlik bilgilerini yalnızca-yazılır 0o600 izinle atomik kaydeder. Yolu döndürür."""
    api_key = (api_key or "").strip()
    base_url = (base_url or "").strip()
    if not api_key or not base_url:
        raise AzureImageError("api_key ve base_url gerekli.")
    if any(c in s for s in (api_key, base_url) for c in "\r\n"):
        raise AzureImageError("Kimlik bilgileri satır sonu karakteri içeremez.")
    if not base_url.startswith(("http://", "https://")):
        raise AzureImageError("base_url http:// veya https:// ile başlamalı.")

    path = env_path if env_path is not None else APP_ENV_PATH
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, mode=0o700, exist_ok=True)
    try:
        os.chmod(parent, 0o700)  # dizin önceden varsa da daralt
    except OSError:
        pass

    content = f"AZURE_IMAGE_API_KEY={api_key}\nAZURE_IMAGE_BASE_URL={base_url}\n"
    # Aynı dizinde geçici dosyaya (mkstemp → 0o600) yazıp atomik os.replace ile taşı:
    # kısmi/boş dosya penceresi ve pre-existing gevşek izin (TOCTOU) kapanır.
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".cred-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)  # yazımdan ÖNCE izinleri sıkılaştır
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def get_settings_status(env_path: str | None = None) -> dict:
    """Yapılandırma durumu — API key'i ASLA döndürmez, sadece endpoint'i açar."""
    creds = _first_complete_credentials(env_path)
    if creds is None:
        return {"configured": False, "endpoint": None}
    return {"configured": True, "endpoint": creds[1]}


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


def build_image_files(images: list[tuple[str, bytes]]):
    """images/edits için multipart `files` yapısını kurar. Sıra korunur.

    Tek görselde alan adı `image` (bugüne dek canlı doğrulanmış tel formatı);
    çoklu görselde OpenAI/Azure'ın beklediği tekrarlanan `image[]` alanı
    (httpx tekrarlanan alan için (name, value) tuple listesi kabul eder).
    """
    if not images:
        raise AzureImageError("En az bir görsel gerekli.")
    if len(images) == 1:
        filename, data = images[0]
        return {"image": (filename, data, "image/png")}
    return [("image[]", (filename, data, "image/png")) for filename, data in images]


def edit(prompt, images, size, quality, n, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(filename, png_bytes), ...] — ilk görsel ana referanstır."""
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
    files = build_image_files(images)

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
