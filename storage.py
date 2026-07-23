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
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Corrupt/unreadable history: tolerate it as empty history rather
            # than crashing the app. Other errors (e.g. permission errors)
            # still propagate.
            return []
    if not isinstance(data, list):
        return []
    return data


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
    history_path = _history_path(output_dir)
    tmp_path = f"{history_path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, history_path)  # atomic on POSIX: no partial-write corruption
    return record


def list_history(output_dir: str) -> list[dict]:
    return list(reversed(_read_history(output_dir)))
