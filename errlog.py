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
MAX_LOG_BYTES = 1024 * 1024   # 1 MB — üstünde .1'e döndürülür
ROTATED_SUFFIX = ".1"


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
