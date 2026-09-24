# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kayıtlı renk paletleri ve palettes.json yönetimi.

Bir palet `(seed, mode)` çiftinin saf fonksiyonu olduğu için (bkz. palette.py)
üretim yolu bu store'a HİÇ bakmaz — burada tutulan şey yalnızca kullanıcının
"bu paleti sonra tekrar kullanacağım" dediği isimli seçkiler.

`colors` kayıt anında dondurulur ve bir daha çözümlenmez: thecolorapi bir
rengi yeniden adlandırsa ya da tamamen kaybolsa bile, yeniden seçilen bir
palet kaydedildiği günkü prompt'u üretmeye devam eder. "Bu palet bana o
görseli vermişti" sözünün tutulabilmesi buna bağlı.

storage.py / folders.py ile aynı desenler: bozuk JSON'a dayanıklı okuma,
immutable-append, `_SAFE_ID` guard'ı. Atomik yazım ve yazma kilidi
jsonstore.py'de paylaşılıyor.
"""
from __future__ import annotations

import json
import os
import re
import uuid

import jsonstore

PALETTES_FILE = "palettes.json"

# storage._SAFE_ID / folders._SAFE_ID ile aynı: uuid4().hex[:12] uyumlu.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def _palettes_path(output_dir: str) -> str:
    return os.path.join(output_dir, PALETTES_FILE)


def _read(output_dir: str) -> list[dict]:
    path = _palettes_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan dosya: çökmek yerine boş kabul et
            # (storage._read_history ve folders._read ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write(output_dir: str, items: list[dict]) -> None:
    jsonstore.write_atomic(_palettes_path(output_dir), items)


def create(name: str, seed: str, mode: str, strength: str,
           colors: list[dict], output_dir: str, *, now: str) -> dict:
    """Yeni palet kaydı. `colors`: `[{"hex": ..., "name": ...}, ...]`.

    `strength` de saklanır: kullanıcı paleti yeniden seçtiğinde kaydettiği
    baskı kademesi de geri gelir.
    """
    os.makedirs(output_dir, exist_ok=True)
    palette_id = uuid.uuid4().hex[:12]
    record = {
        "id": palette_id,
        "name": name,
        "seed": seed,
        "mode": mode,
        "strength": strength,
        "colors": colors,
        "created_at": now,
    }
    with jsonstore.lock_for(_palettes_path(output_dir)):  # oku→değiştir→yaz bölünmez
        _write(output_dir, _read(output_dir) + [record])   # immutable append
    return record


def list_palettes(output_dir: str) -> list[dict]:
    """En yeni palet başta (folders.list_folders ile aynı sıra)."""
    return list(reversed(_read(output_dir)))


def delete(palette_id: str, output_dir: str) -> bool:
    """Paleti siler. Bulunamadıysa/geçersiz id ise False."""
    if not palette_id or not _SAFE_ID.fullmatch(palette_id):
        return False
    with jsonstore.lock_for(_palettes_path(output_dir)):
        items = _read(output_dir)
        kept = [p for p in items if p.get("id") != palette_id]
        if len(kept) == len(items):
            return False
        _write(output_dir, kept)
    return True
