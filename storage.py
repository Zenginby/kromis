"""Üretilen görsellerin diske kaydı ve history.json yönetimi."""
from __future__ import annotations

import json
import os
import uuid

HISTORY_FILE = "history.json"


def _history_path(output_dir: str) -> str:
    return os.path.join(output_dir, HISTORY_FILE)


def _read_history(output_dir: str) -> list[dict]:
    path = _history_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save(image_bytes: bytes, meta: dict, output_dir: str, *, now: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    image_id = uuid.uuid4().hex[:12]
    filename = f"{image_id}.png"
    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(image_bytes)
    record = {
        "id": image_id,
        "filename": filename,
        "prompt": meta.get("prompt", ""),
        "size": meta.get("size", ""),
        "quality": meta.get("quality", ""),
        "created_at": now,
        "parent_id": meta.get("parent_id"),
    }
    # immutable append: yeni liste yaz
    history = _read_history(output_dir) + [record]
    with open(_history_path(output_dir), "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return record


def list_history(output_dir: str) -> list[dict]:
    return list(reversed(_read_history(output_dir)))
