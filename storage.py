"""Üretilen görsellerin diske kaydı ve history.json yönetimi."""
from __future__ import annotations

import json
import os
import re
import uuid

HISTORY_FILE = "history.json"

# Image ids are generated as uuid.uuid4().hex[:12] (see save()): bare lowercase
# hex tokens with no separators or dots. Reject anything else up front so a
# malicious/malformed id can never reach a filesystem path.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


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


def _write_history(output_dir: str, history: list[dict]) -> None:
    path = _history_path(output_dir)
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


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
        # None/eksik = klasörsüz (kök). Eski kayıtlarda bu alan hiç yoktur;
        # okurken .get("folder_id") ile kök kabul edilir → geçiş gerekmez.
        "folder_id": meta.get("folder_id"),
    }
    # immutable append: yeni liste yaz
    history = _read_history(output_dir) + [record]
    _write_history(output_dir, history)
    return record


def list_history(output_dir: str) -> list[dict]:
    return list(reversed(_read_history(output_dir)))


def set_folder(image_id: str, folder_id: str | None, output_dir: str) -> bool:
    """Bir görselin klasörünü değiştirir (None = klasörsüz/kök).

    Dosya taşınmaz — klasör yalnızca kayıttaki bir etikettir, bu yüzden
    `/output/{filename}` URL'leri ve türev zincirleri etkilenmez.
    Kayıt yoksa veya id formatı geçersizse False döner.
    """
    if not _SAFE_ID.fullmatch(image_id):
        return False
    history = _read_history(output_dir)
    if not any(r.get("id") == image_id for r in history):
        return False
    _write_history(output_dir,
                   [{**r, "folder_id": folder_id} if r.get("id") == image_id else r
                    for r in history])
    return True


def unfile_folder(folder_id: str, output_dir: str) -> int:
    """Bir klasördeki tüm kayıtları klasörsüz hale getirir; etkilenen sayıyı döndürür.

    Klasör silinirken kullanılır: görseller SİLİNMEZ, yalnızca köke döner.
    """
    history = _read_history(output_dir)
    affected = sum(1 for r in history if r.get("folder_id") == folder_id)
    if affected:
        _write_history(output_dir,
                       [{**r, "folder_id": None} if r.get("folder_id") == folder_id else r
                        for r in history])
    return affected


def delete(image_id: str, output_dir: str) -> bool:
    if not _SAFE_ID.fullmatch(image_id):
        return False

    history = _read_history(output_dir)
    remaining = [r for r in history if r.get("id") != image_id]
    record_existed = len(remaining) != len(history)

    file_path = os.path.join(output_dir, f"{image_id}.png")
    file_existed = os.path.exists(file_path)
    if file_existed:
        os.remove(file_path)

    if record_existed:
        _write_history(output_dir, remaining)

    return record_existed or file_existed
