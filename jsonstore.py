"""Beş manifest deposunun PAYLAŞTIĞI iki mekanik: atomik yazım ve yazma kilidi.

`storage.py`, `folders.py`, `palette_store.py`, `assets_store.py` ve
`chat_store.py` aynı deseni beş kez kopyalamıştı (tmp dosyası + `os.replace`).
Desen doğruydu, iki eksiği vardı ve ikisi de beş yerde birden düzeltilmeli:

1. **Kilit yok.** Rotalar senkron `def`, yani Starlette onları KENDİ
   threadpool'unda koşturuyor: iki istek gerçekten paralel çalışabiliyor. Bütün
   depolar "oku → değiştir → yaz" yapıyor; araya girilirse kaybeden yazım
   sessizce düşer. v1.15'e kadar yazan tek şey kullanıcının tek tek eylemleriydi
   ve pencere pratikte kapalıydı; artık Prompt Yönetmeni HER TUR SONUNDA kendi
   kendine yazıyor, yani "tur kaydedilirken yeniden adlandır" gerçek bir dizilim.
   Kilit DOSYA BAŞINA: iki ayrı manifest birbirini beklemesin.

2. **Geçici dosya sızıntısı.** `json.dump` yazarken patlarsa (disk dolu,
   serileştirilemeyen değer) `os.replace`e hiç gelinmiyor ve `*.tmp` dosyası
   veri klasöründe kalıyordu. Kullanıcının gördüğü klasörde çöp bırakmıyoruz.

OKUMALAR kilitsiz kalıyor, bilerek: `os.replace` atomik, yani okuyan taraf ya
eski ya yeni dosyanın TAMAMINI görür — yarım dosya diye bir hâl yok.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import uuid

# Dosya yolu → kilit. `RLock` çünkü depo fonksiyonları birbirini çağırıyor
# (`storage.unfile_folder` → `unfile_folders`): düz `Lock` aynı iş parçacığında
# ikinci kez alınınca kilitlenirdi.
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def lock_for(path: str) -> threading.RLock:
    """Bu dosyanın "oku → değiştir → yaz" kilidi. Aynı yol → aynı kilit."""
    key = os.path.abspath(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.RLock()
        return lock


def _replace_via_tmp(path: str, render) -> None:
    """`render(f)` çıktısını tmp dosyaya yazıp `os.replace` ile yerine koyar.

    `render` patlarsa (disk dolu, serileştirilemeyen değer) tmp dosyası SİLİNİR:
    eskiden `os.replace`e hiç gelinmediği için veri klasöründe `*.tmp` çöpü
    kalıyordu — kullanıcının Finder'da gördüğü klasör.
    """
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            render(f)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def write_atomic(path: str, data: list[dict] | dict) -> None:
    """Manifesti tek parçada yazar: yarım dosya bırakmaz, `*.tmp` de bırakmaz.

    `encoding="utf-8"` AÇIKÇA veriliyor: iki depo bunu vermiyordu ve klasör/palet
    adlarındaki Türkçe karakterler platformun varsayılan kodlamasına kalıyordu.

    Beş manifest LİSTE yazıyor, `prefs.py` (v2.0) NESNE — tür bu yüzden geniş.
    Mekanik ikisi için de aynı; ayrı bir yazıcı açmak bu modülün var olma
    sebebine (deseni beş yerde kopyalamayı bitirmek) aykırı olurdu.
    """
    _replace_via_tmp(path, lambda f: json.dump(data, f, ensure_ascii=False, indent=2))


def write_text(path: str, text: str) -> None:
    """JSON olmayan tek satırlık dosyalar için aynı mekanik (bkz. backup damgası)."""
    _replace_via_tmp(path, lambda f: f.write(text))
