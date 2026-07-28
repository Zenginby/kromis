"""Paylaşılan hata günlüğü: paketlenmiş uygulamada stderr'in kullanıcıya hiç
görünmediği tek çıkış yolu bu dosya.

`app.py` (tohumlama hatası, I2) ve `desktop.py` (başlatma/kapanış hatası, I1)
aynı `hata.log`'a yazar — konum `paths.data_dir()` ile aynı köke bağlıdır, yani
frozen'da Application Support altında, geliştirmede repo kökündedir.
"""
from __future__ import annotations

import datetime as _dt
import os

LOG_FILENAME = "hata.log"


def log_path(data_dir: str) -> str:
    """`data_dir` altındaki hata.log yolu (dosya henüz var olmayabilir)."""
    return os.path.join(data_dir, LOG_FILENAME)


def append(data_dir: str, text: str) -> str:
    """`text`'i zaman damgasıyla hata.log'a ekler; dosyanın yolunu döner.

    Bu fonksiyonun KENDİSİ patlayabilir (disk dolu, izinsiz dizin) — çağıranlar
    loglama hatasının kullanıcıya gösterilecek asıl uyarıyı engellememesi için
    `safe_append`'i tercih etmeli.
    """
    path = log_path(data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    timestamp = _dt.datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n--- {timestamp} ---\n{text}\n")
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
