"""Azure gpt-image-2 istemcisi.

Kimlik iki dosyadan SIRAYLA okunur, ilk tam olan kazanır (bkz. `_candidate_paths`):
`~/.config/gpt-image-studio/credentials.env` (uygulamanın kendi dosyası, Ayarlar
penceresi buraya yazar) → `~/.config/claude-tools/azure-gpt-image2.env` (paylaşılan).
"""
from __future__ import annotations

import base64
import os
import tempfile

import paths
import winsec

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
#
# Yollar artık `paths` üzerinden çözülüyor: Android'de `~` güvenilir değil ve
# paylaşılan dosyanın karşılığı hiç yok (bkz. paths.credentials_path). Masaüstü
# değerleri BİREBİR aynı kaldı. İkisi de modül düzeyinde SABİT kalmaya devam
# ediyor — testler bunları `monkeypatch.setattr(ac, "APP_ENV_PATH", …)` ile
# değiştiriyor ve fonksiyona çevirmek o desenin tamamını kırardı.
APP_ENV_PATH = paths.credentials_path()
DEFAULT_ENV_PATH = paths.shared_credentials_path()
# ── Zaman aşımları ──────────────────────────────────────────────────
# Tek sabit 120 s ilk commit'ten (e9748da) beri hiç ayarlanmamıştı ve
# 2026-08-04'te canlıda yüksek kalite bir üretimde ReadTimeout'a düştü.
#
# Okuma süresi ADETLE büyümek zorunda: `build_payload` n'i tek isteğe koyuyor,
# yani 4 görsel tek POST'ta üretiliyor ve süre buna göre uzuyor. Sabit bir değer
# ya n=4 için kısa kalır ya da n=1 takıldığında boşuna dakikalar bekletir.
#
# Bağlanma süresi AYRI ve kısa: ölü ağda/yanlış endpoint'te hızlı düşülmeli —
# yoksa yazım hatası olan bir adres, uzun okuma süresi kadar bekletirdi.
# NOT: aşağıdaki değerler ÖLÇÜM DEĞİL, başlık payı (gerçek gecikme ancak ücretli
# bir üretimle ölçülebilir). Zaman aşımı mesajı kaç saniye beklendiğini yazıyor,
# böylece ayar gerekiyorsa kanıt kullanıcının elinde oluyor.
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT_FIRST = 180.0   # ilk görsel
READ_TIMEOUT_EXTRA = 120.0   # her ek görsel


def read_timeout_for(n: int) -> float:
    """`n` görsellik bir istek için okuma zaman aşımı (saniye)."""
    return READ_TIMEOUT_FIRST + READ_TIMEOUT_EXTRA * max(0, n - 1)


def request_timeout(read: float):
    """httpx.Timeout: okuma çağrının kendisine göre, bağlanma her zaman kısa."""
    import httpx
    return httpx.Timeout(read, connect=CONNECT_TIMEOUT)

# Prompt Yönetmeni (v1.13) aynı dosyada yaşıyor. Sohbetin key/url'si BOŞ
# bırakılabilir: o zaman görselin kimliğine düşer — canlı doğrulandı, iki dağıtım
# aynı Azure kaynağında ve aynı anahtarla çalışıyor. Ayrı bir kaynak gerekiyorsa
# bu iki değişken dosyaya ELLE yazılır; forma ikinci bir gizli alan eklenmiyor
# (app.py'deki doğrulama redaksiyonu `loc`'ta yalnızca `api_key` arıyor, başka
# adlı bir gizli alan o redaksiyonu sessizce atlatırdı).
CHAT_KEY = "AZURE_CHAT_API_KEY"
CHAT_URL = "AZURE_CHAT_BASE_URL"
CHAT_DEPLOYMENT = "AZURE_CHAT_DEPLOYMENT"
IMAGE_KEY = "AZURE_IMAGE_API_KEY"
IMAGE_URL = "AZURE_IMAGE_BASE_URL"


class AzureImageError(Exception):
    """Kullanıcıya gösterilebilir Azure hatası (mesajı map_error çıktısıdır)."""


def transport_error_message(exc: Exception, timeout: float) -> str:
    """httpx TAŞIMA hatasını kullanıcıya gösterilebilir Türkçe mesaja çevirir.

    `map_error`'ın ikizi: o Azure'ın DÖNDÜĞÜ HTTP durumunu çevirir, bu ise yanıtın
    hiç gelmediği durumu. İkisi de aynı yere varmak zorunda — app.py Azure
    çağrılarını yalnızca `AzureImageError`/`ChatError` süzgeciyle yakalayıp 502'ye
    çeviriyor, sarmalanmayan bir httpx hatası o süzgeçten GEÇİP ham 500 oluyor.
    O noktada arayüz gövdeyi JSON olarak ayrıştıramıyor ve kullanıcı beklemenin
    sonunda yalnızca "Hata (500)" görüyor: ne sebep, ne çıkış yolu.

    Zaman aşımı ile bağlanamama AYRI mesajlar: ilkinde adet/kalite düşürülür,
    ikincisinde endpoint ve ağ kontrol edilir. Tek mesaja indirilirse kullanıcı
    yanlış tarafı kurcalar.
    """
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        # ÜCRET UYARISI şart: zaman aşımı İSTEMCİNİN vazgeçmesidir, Azure'ın
        # değil. İstek karşı tarafta tamamlanmış ve faturalanmış olabilir;
        # kullanıcı "hata aldım, demek ki ücretlenmedim" diye düşünmemeli.
        return (f"Azure {timeout:.0f} saniyede yanıt vermedi (zaman aşımı). "
                "Yüksek kalite ve yüksek adet üretimi uzatır — adedi ya da "
                "kaliteyi düşürüp tekrar dene. Not: istek Azure tarafında "
                "tamamlanmış ve ücretlendirilmiş olabilir, yalnızca sonuç bu "
                "tarafa ulaşmadı.")
    if isinstance(exc, httpx.TransportError):
        return ("Azure'a bağlanılamadı: internet bağlantını ve Ayarlar'daki "
                f"endpoint adresini kontrol et. ({type(exc).__name__})")
    return f"Azure isteği beklenmedik biçimde başarısız oldu: {type(exc).__name__}."


def _parse_env_all(path: str) -> dict[str, str]:
    """Bir .env dosyasının TÜM anahtarları. Dosya yoksa OSError yükselir.

    İki isme sabitlenmiyor: birleştirmeli yazım (save_env) dokunmadığı anahtarları
    koruyabilmek için dosyanın tamamını görmek zorunda.
    """
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:  # yazımla aynı encoding
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _parse_env_file(path: str) -> tuple[str, str]:
    """Bir .env dosyasından key/url'yi çıkarır. Dosya yoksa OSError yükselir.

    GERİYE UYUM: OSError sözleşmesi ve (key, url) imzası korunuyor —
    `_first_complete_credentials` ve tests/test_settings.py buna dayanıyor.
    """
    values = _parse_env_all(path)
    return values.get(IMAGE_KEY, ""), values.get(IMAGE_URL, "")


def _candidate_paths(env_path: str | None) -> list[str]:
    """Açık env_path verilirse sadece o; yoksa app dosyası → paylaşılan dosya sırası.

    `None` olan aday ELENİYOR: Android'de paylaşılan dosyanın karşılığı yok ve
    `DEFAULT_ENV_PATH` orada `None` oluyor (bkz. paths.shared_credentials_path).
    Masaüstünde iki değer de dolu, yani liste ve sıra bugünküyle birebir aynı.
    """
    if env_path is not None:
        return [env_path]
    return [p for p in (APP_ENV_PATH, DEFAULT_ENV_PATH) if p]


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


def read_env_values(env_path: str | None = None) -> dict[str, str]:
    """Aday dosyaların BİRLEŞİK görünümü; anahtar başına ilk BOŞ OLMAYAN değer kazanır.

    Neden birleşik: sohbet dağıtımı uygulamanın kendi dosyasında, görsel kimliği
    ise eski paylaşılan `claude-tools` dosyasında olabilir — ikisini birlikte
    görmek gerekiyor. "İlk boş olmayan kazanır" kuralı
    `_first_complete_credentials`'ın fallback semantiğinin aynısı: yarım
    doldurulmuş app dosyası çalışan bir kurulumu gölgelemesin.
    """
    merged: dict[str, str] = {}
    for path in _candidate_paths(env_path):
        try:
            values = _parse_env_all(path)
        except OSError:
            continue
        for name, value in values.items():
            if not merged.get(name):
                merged[name] = value
    return merged


def _atomic_write(path: str, content: str) -> str:
    """0o700 dizin + 0o600 dosya, atomik replace ile. Yolu döndürür.

    Aynı dizinde geçici dosyaya (mkstemp → 0o600) yazıp atomik os.replace ile
    taşı: kısmi/boş dosya penceresi ve pre-existing gevşek izin (TOCTOU) kapanır.

    Windows'ta `chmod`/`fchmod` POSIX bitlerini UYGULAMIYOR (Faz 0'da ölçüldü:
    0o600 istendiği halde dosya 0o666 kalıyor). Aynı güvence orada DACL ile
    kuruluyor — bkz. winsec. İki çağrı POSIX'te no-op, yani bu fonksiyonun
    macOS davranışı birebir aynı kalıyor.
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, mode=0o700, exist_ok=True)
    try:
        os.chmod(parent, 0o700)  # dizin önceden varsa da daralt
        winsec.restrict_to_current_user(parent)
    except OSError:
        pass

    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".cred-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)  # yazımdan ÖNCE izinleri sıkılaştır
        winsec.restrict_to_current_user(tmp)  # aynı disiplin, Windows karşılığı
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


def save_env(updates: dict[str, str], env_path: str | None = None) -> str:
    """Verilen anahtarları günceller, dosyanın GERİ KALANINI korur. Yolu döndürür.

    OKU → BİRLEŞTİR → atomik yaz. v1.12'ye kadar `save_credentials` dosyayı
    sıfırdan iki satır yazıyordu; sohbet dağıtımı aynı dosyada durduğu için
    "endpoint'i tek başına güncelle" eylemi onu SESSİZCE siliyordu.

    Bilinen anahtar süzgeci YOK: dosyada bulunan her satır korunuyor, çünkü
    kullanıcı buraya elle bir değişken (ör. ayrı bir AZURE_CHAT_BASE_URL)
    yazabiliyor ve onu düşürmek sessiz bir veri kaybı olurdu.

    Boş değer "temizle" demek: alan dosyada `AD=` olarak kalır, okuma tarafı
    boş dizeyi yapılandırılmamış sayar.

    Dosya VAR ama okunamıyorsa (izin sorunu) birleştirme yapılamaz ve dosya
    yalnızca yeni değerlerle yazılır. Bilinçli: alternatif "kaydetmeyi tümden
    reddetmek" olurdu ve kullanıcı arayüzden hiçbir şeyi düzeltemez hale
    gelirdi — böyle bir durumda dağıtım adını yeniden girmek yeterli.
    """
    for value in updates.values():
        # Satır sonu taşıyan bir değer dosyaya İKİNCİ bir anahtar enjekte eder.
        # `chat_deployment` bir form alanı olduğu için bu guard bu yolda da şart.
        if any(c in str(value) for c in "\r\n"):
            raise AzureImageError("Ayar değeri satır sonu karakteri içeremez.")

    path = env_path if env_path is not None else APP_ENV_PATH
    try:
        values = _parse_env_all(path)
    except OSError:
        values = {}
    values.update({name: str(value) for name, value in updates.items()})
    return _atomic_write(path, "".join(f"{n}={v}\n" for n, v in values.items()))


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
    return save_env({IMAGE_KEY: api_key, IMAGE_URL: base_url}, env_path=env_path)


def resolve_chat_credentials(env_path: str | None = None) -> tuple[str, str, str]:
    """(key, base_url, deployment) — eksik alanlar BOŞ dize, hata YÜKSELTİLMEZ.

    Sohbetin kendi anahtarları varsa onlar, yoksa görselin kimliği kullanılır
    (canlı doğrulandı: iki dağıtım aynı kaynakta, aynı anahtarla çalışıyor).

    Çözüm BURADA, `chat_client`'ta değil: `get_settings_status`'un arayüzde
    açtığı kapı ile isteğin gerçekten kullandığı değerler ayrışırsa arayüz
    sohbeti açar, ilk mesaj 502 döner ve sebebi görünmez olur.
    """
    values = read_env_values(env_path)
    key = values.get(CHAT_KEY) or values.get(IMAGE_KEY, "")
    url = values.get(CHAT_URL) or values.get(IMAGE_URL, "")
    return key, url, values.get(CHAT_DEPLOYMENT, "")


def get_settings_status(env_path: str | None = None) -> dict:
    """Yapılandırma durumu — API key'i ASLA döndürmez, sadece status/endpoint'i açar."""
    creds = _first_complete_credentials(env_path)
    chat_key, chat_url, chat_deployment = resolve_chat_credentials(env_path)
    env_vals = read_env_values(env_path)
    return {
        "configured": creds is not None,
        "endpoint": creds[1] if creds is not None else None,
        "chat_deployment": chat_deployment,
        "chat_configured": bool(chat_deployment and chat_key and chat_url),
        "has_openai_key": bool(env_vals.get("OPENAI_API_KEY")),
        "has_fal_key": bool(env_vals.get("FAL_KEY")),
        "has_replicate_token": bool(env_vals.get("REPLICATE_API_TOKEN")),
        "comfyui_url": env_vals.get("COMFYUI_URL", ""),
        "ollama_url": env_vals.get("OLLAMA_URL", ""),
    }



def generate(prompt, size, quality, n, *, client=None, credentials=None) -> list[bytes]:
    key, base_url = credentials if credentials else load_credentials()
    endpoint = base_url.rstrip("/") + "/images/generations"
    payload = build_payload(prompt, size, quality, n)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    owns_client = client is None
    # httpx modül düzeyinde değil BURADA (dosyanın lazy-import duruşu): hata
    # türlerini yakalamak için enjekte edilmiş istemcide de gerekiyor.
    import httpx
    if owns_client:
        client = httpx.Client()
    read = read_timeout_for(n)
    try:
        resp = client.post(endpoint, headers=headers, json=payload,
                           timeout=request_timeout(read))
    except httpx.TransportError as exc:
        raise AzureImageError(transport_error_message(exc, read)) from exc
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
    import httpx   # bkz. generate(): hata türleri için enjekte istemcide de gerekli
    if owns_client:
        client = httpx.Client()
    read = read_timeout_for(n)
    try:
        resp = client.post(endpoint, headers=headers, data=data, files=files,
                           timeout=request_timeout(read))
    except httpx.TransportError as exc:
        raise AzureImageError(transport_error_message(exc, read)) from exc
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
