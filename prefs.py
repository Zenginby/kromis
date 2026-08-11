"""Kullanıcı tercihleri (gizli DEĞİL) ve prefs.json yönetimi.

v2.0'da otomatik kayıt (karar D1) bir anahtar gerektirdi ve iki aday yer de
yanlıştı:

  1. **`credentials.env`** (`azure_client.save_env`) bir KİMLİK dosyası: 0600,
     `~/.config` altında. Bir arayüz tercihini oraya koymak, `POST /api/settings`
     `api_key` + `base_url` istediği için anahtarı her çevirişte kimliği yeniden
     yazmaya bağlardı — ve Azure hiç yapılandırılmamışken anahtar çevrilemez
     olurdu. Bir tema adının 0600 olmasının da bir anlamı yok.
  2. **İstemci (localStorage)**: `desktop.py` pencereyi pywebview'ın
     `private_mode=True` varsayılanıyla açıyor, orada localStorage her kapanışta
     siliniyor — `chat_store.py`'nin başındaki ölçülmüş sebep. Paketlenmiş
     `.app`'te tercih her açılışta sıfırlanırdı.

Bu yüzden tercihler kullanıcının VERİ dizinine, diğer beş manifestin yanına
düşüyor ve mekanikler jsonstore'dan geliyor (atomik yazım + yazma kilidi).
`backup.py`'nin manifest yedeği de böylece tercihleri kapsıyor.

Şekil farkı: bu dosya LİSTE değil NESNE. Depo başına bir kayıt kümesi yok, tek
bir tercih kümesi var.

Yazma yolu KATI (bilinmeyen anahtar ve yanlış tür yüksek sesle hata),
okuma yolu HOŞGÖRÜLÜ (bozuk dosya → varsayılanlar). Beş depodaki duruşun aynısı:
kullanıcının veri klasöründeki bir dosya uygulamayı açılamaz hale getirmemeli,
ama uygulamanın kendi yazdığı çöp de sessizce birikmemeli.
"""
from __future__ import annotations

import json
import os

import jsonstore

PREFS_FILE = "prefs.json"

# Tercih → (varsayılan, tür). Varsayılan "dosya yok" ile "alan yok" durumlarının
# İKİSİNİ de karşılıyor; tercihler bu yüzden hiç göç gerektirmiyor.
#
# `autosave_sessions` varsayılanı True: karar D1 oturumların kaydedilmesinden
# yana ve yeni bir kurulumda geçmişin boş kalması o kararın tersini uygulamak
# olurdu (bkz. tasarım §5/D1).
_SCHEMA: dict[str, tuple[object, type]] = {
    "autosave_sessions": (True, bool),
    "theme": ("mono", str),
}

DEFAULTS = {name: default for name, (default, _) in _SCHEMA.items()}


def _prefs_path(output_dir: str) -> str:
    return os.path.join(output_dir, PREFS_FILE)


def _read_raw(output_dir: str) -> dict:
    path = _prefs_path(output_dir)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk dosya: çökmek yerine varsayılanlar
            # (storage._read_history / chat_store._read ile aynı davranış).
            return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write(output_dir: str, values: dict) -> None:
    os.makedirs(output_dir, exist_ok=True)
    jsonstore.write_atomic(_prefs_path(output_dir), values)


def read(output_dir: str) -> dict:
    """Bilinen tercihlerin BİRLEŞİK görünümü; okuma yan etkisiz (dosya yaratmaz).

    Türü yanlış olan bir değer TAHMİN EDİLMEZ, varsayılana düşer: elle yazılmış
    `"false"` dizesini bool'a çevirmeye çalışmak (`bool("false") is True`)
    kullanıcının "kapat" niyetini tam tersine döndürebilirdi.
    """
    stored = _read_raw(output_dir)
    return {
        name: stored[name] if isinstance(stored.get(name), expected) else default
        for name, (default, expected) in _SCHEMA.items()
    }


def update(values: dict, output_dir: str) -> dict:
    """Verilen tercihleri yazar, DİĞERLERİNİ korur; birleşik görünümü döndürür.

    "Dosyanın geri kalanını koru" kuralı `azure_client.save_env`'den geliyor ve
    aynı sebeple: orada endpoint'i tek başına kaydetmek sohbet dağıtımını
    sessizce silmişti (v1.12). Burada tema (Adım 9) ile otomatik kayıt anahtarı
    aynı dosyayı paylaşacak.

    Bilinmeyen anahtar ya da yanlış tür `ValueError`: sessizce kabul edilse
    kullanıcı "ayar çalışmıyor" derdi ve dosyada hiç okunmayan bir alan birikirdi
    (modellerin `extra="forbid"` duruşunun aynısı).

    Değişecek bir şey yoksa dosyaya DOKUNULMAZ — `chat_store.update`'in boş
    güncellemede dosyaya dokunmama kuralının aynısı.
    """
    for name, value in values.items():
        if name not in _SCHEMA:
            raise ValueError(f"bilinmeyen tercih: {name}")
        if not isinstance(value, _SCHEMA[name][1]):
            raise ValueError(f"tercih için geçersiz değer: {name}")
        if name == "theme" and value not in ("mono", "ocean", "amber", "viola"):
            raise ValueError(f"tercih için geçersiz tema değeri: {value}")
    if not values:
        return read(output_dir)
    with jsonstore.lock_for(_prefs_path(output_dir)):
        _write(output_dir, {**_read_raw(output_dir), **values})   # immutable birleştirme
    return read(output_dir)
