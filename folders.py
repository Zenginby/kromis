"""Görsel klasörleri (koleksiyonlar) ve folders.json yönetimi.

Klasörler diskte gerçek dizin DEĞİL: görseller `output/` altında düz durur ve
klasör yalnızca kayıttaki bir etikettir (`folder_id`). Böylece `/output/{filename}`
URL'leri ile `parent_id` türev zincirleri klasör taşımalarından etkilenmez.

storage.py ile aynı desenler: bozuk JSON'a dayanıklı okuma, atomik yazım
(`os.replace`), immutable-append, `_SAFE_ID` guard'ı.
"""
from __future__ import annotations

import json
import os
import re
import uuid

FOLDERS_FILE = "folders.json"

# storage._SAFE_ID ile aynı: uuid4().hex[:12] üretimiyle uyumlu bare hex token.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def _folders_path(output_dir: str) -> str:
    return os.path.join(output_dir, FOLDERS_FILE)


def _read(output_dir: str) -> list[dict]:
    path = _folders_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan dosya: çökmek yerine boş kabul et
            # (storage._read_history ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write(output_dir: str, items: list[dict]) -> None:
    path = _folders_path(output_dir)
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def create(name: str, output_dir: str, *, now: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    folder_id = uuid.uuid4().hex[:12]
    record = {"id": folder_id, "name": name, "created_at": now}
    _write(output_dir, _read(output_dir) + [record])  # immutable append
    return record


def list_folders(output_dir: str) -> list[dict]:
    """En yeni klasör başta (assets_store.list_assets ile aynı sıra)."""
    return list(reversed(_read(output_dir)))


def exists(folder_id: str, output_dir: str) -> bool:
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        return False
    return any(f.get("id") == folder_id for f in _read(output_dir))


def delete(folder_id: str, output_dir: str) -> bool:
    """Klasör kaydını siler. İçindeki GÖRSELLER silinmez — çağıran taraf
    `storage.unfile_folder` ile onları klasörsüz hale getirir."""
    if not _SAFE_ID.fullmatch(folder_id):
        return False
    items = _read(output_dir)
    remaining = [f for f in items if f.get("id") != folder_id]
    if len(remaining) == len(items):
        return False
    _write(output_dir, remaining)
    return True
