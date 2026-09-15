# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Paylaşılan hata günlüğü: paketlenmiş uygulamada stderr'in kullanıcıya hiç
görünmediği tek çıkış yolu bu dosya.

`app.py` (tohumlama hatası, I2) ve `desktop.py` (başlatma/kapanış hatası, I1)
aynı `hata.log`'a yazar — konum `paths.data_dir()` ile aynı köke bağlıdır, yani
frozen'da Application Support altında, geliştirmede repo kökündedir.
"""
from __future__ import annotations

import datetime as _dt
import os

import re

LOG_FILENAME = "hata.log"
MAX_LOG_BYTES = 1024 * 1024   # 1 MB — üstünde .1'e döndürülür
ROTATED_SUFFIX = ".1"

# Desenlerin İKİ ailesi var ve ikisi de gerekli:
#   (a) DEĞERİN kendi biçimi (`sk-…`, `fal-…`, `AIza…`) — anahtar adsız,
#       çıplak bir traceback parçasında geçtiğinde yakalar,
#   (b) `AD=değer` ve başlık biçimleri — değerin biçimi tanınmadığında yakalar.
# Bir sağlayıcı yalnız (a) ile korunuyorsa kısa/atipik bir anahtar sızar; yalnız
# (b) ile korunuyorsa httpx'in URL/repr çıktısındaki çıplak değer sızar.
#
# 4. desen v0.6'da GENELLEŞTİ ve sebebi ölçüldü: adı birebir sayan alternasyon
# (`OPENAI_API_KEY|FAL_KEY|REPLICATE_API_TOKEN|AZURE_[A-Z_]*KEY`) yeni bir
# sağlayıcı eklendiğinde SESSİZCE kapsam dışı bırakıyordu —
# `GEMINI_API_KEY=AIza…` satırı sansürsüz loglanıyordu, üstelik Google'ın
# biçimi (a) ailesinde de yoktu, yani anahtar iki kapıdan birden kaçıyordu.
# Artık kural adın BİÇİMİ: KEY/TOKEN/SECRET ile biten her BÜYÜK_HARF adı.
# Böylece kataloğa bir sağlayıcı eklemek log sansürlemesini de kendiliğinden
# kapsıyor (mandal: tests/test_errlog.py, catalog.secret_env_names() üzerinde
# dönen mekanik test).
_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"fal-[a-zA-Z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"r8_[a-zA-Z0-9_-]{16,}", re.IGNORECASE),
    # Google (Gemini) anahtar biçimi. BÜYÜK/küçük harf duyarlı BİLEREK: `AIza`
    # önekinin harf düzeni sabit ve `re.IGNORECASE` "aiza" ile başlayan sıradan
    # Türkçe metni de sansürleyebilirdi.
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    # AD=değer. `[A-Z][A-Z0-9_]*` + KEY/TOKEN/SECRET: ad biçimine bağlı, listeye
    # değil. IGNORECASE YOK — küçük harf bir `key=` sıradan bir sorgu dizesi
    # olabilir ve ad kuralının anlamı BÜYÜK HARF env adı olmasıydı.
    re.compile(r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET)\s*=\s*['\"]?[a-zA-Z0-9_.-]{8,}['\"]?"),
    # Başlıklar. `x-goog-api-key` ve `x-api-key` AÇIKÇA yazılı: ikisi de bugün
    # `api-key` alt dizesi sayesinde tesadüfen eşleşiyor, ama tesadüf sözleşme
    # değil — `anthropic-version` gibi bir komşu bir gün deseni daraltırsa
    # sessizce açık kalırlardı.
    re.compile(r"(x-goog-api-key|x-api-key|api-key|authorization):\s*(Bearer\s*)?[a-zA-Z0-9_.-]{16,}", re.IGNORECASE),
]



def redact_secrets(text: str) -> str:
    """Metindeki hassas API anahtarlarını sansürler."""
    if not text:
        return ""
    result = text
    for pat in _KEY_PATTERNS:
        result = pat.sub("[REDACTED_API_KEY]", result)
    return result


def log_path(data_dir: str) -> str:
    """`data_dir` altındaki hata.log yolu (dosya henüz var olmayabilir)."""
    return os.path.join(data_dir, LOG_FILENAME)


def _rotate_if_large(path: str) -> None:
    """Dosya sınırı aşmışsa `.1`'e taşır; tek bir eski kopya tutulur.

    Kullanıcı bu dosyayı hiç silmiyor (varlığını yalnız bir hata anında
    öğreniyor), o yüzden sınırsız büyümemeli. `.2`, `.3` biriktirmenin teşhis
    değeri yok: ilgilenilen şey her zaman EN SON açılış denemesi.
    """
    try:
        if os.path.getsize(path) <= MAX_LOG_BYTES:
            return
    except OSError:
        return  # dosya yok ya da okunamıyor — döndürecek bir şey de yok
    os.replace(path, path + ROTATED_SUFFIX)


def append(data_dir: str, text: str) -> str:
    """`text`'i zaman damgasıyla hata.log'a ekler; dosyanın yolunu döner.

    Bu fonksiyonun KENDİSİ patlayabilir (disk dolu, izinsiz dizin) — çağıranlar
    loglama hatasının kullanıcıya gösterilecek asıl uyarıyı engellememesi için
    `safe_append`'i tercih etmeli.
    """
    path = log_path(data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _rotate_if_large(path)
    safe_text = redact_secrets(text)
    timestamp = _dt.datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n--- {timestamp} ---\n{safe_text}\n")
    return path



def safe_append(data_dir: str, text: str) -> str:
    """`append`'i sarar: loglama başarısız olsa bile ASLA patlamaz.

    Başarısız olursa yine de beklenen log yolunu döner (çağıran kullanıcıya
    "buraya bak" diyebilsin diye) — dosyanın gerçekten yazılmış olması garanti
    değildir.
    """
    try:
        return append(data_dir, text)
    except Exception:
        return log_path(data_dir)
