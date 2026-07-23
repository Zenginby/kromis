"""Kullanıcının logo/banner varlıklarının diske kaydı ve manifest yönetimi.

storage.py ile aynı desenleri izler: _SAFE_ID guard'ı, atomik manifest yazımı,
immutable-append. Varlıklar tür başına ayrı bir alt dizinde tutulur:

    <assets_dir>/<kind>/{id}.png
    <assets_dir>/<kind>/index.json   # [{id, filename, name, kind, created_at}]
"""
from __future__ import annotations

import json
import os
import re
import uuid

MANIFEST_FILE = "index.json"
KINDS = ("logos", "banners", "mottos")

# storage._SAFE_ID ile aynı: uuid4().hex[:12] üretimiyle uyumlu bare hex token.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"geçersiz kind: {kind!r}")


def _kind_dir(assets_dir: str, kind: str) -> str:
    _check_kind(kind)
    return os.path.join(assets_dir, kind)


def _manifest_path(kind_dir: str) -> str:
    return os.path.join(kind_dir, MANIFEST_FILE)


def _read_manifest(kind_dir: str) -> list[dict]:
    path = _manifest_path(kind_dir)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan manifest: çökmek yerine boş kabul et
            # (storage._read_history ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write_manifest(kind_dir: str, items: list[dict]) -> None:
    path = _manifest_path(kind_dir)
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_asset(kind: str, image_bytes: bytes, name: str, assets_dir: str, *, now: str) -> dict:
    kind_dir = _kind_dir(assets_dir, kind)
    os.makedirs(kind_dir, exist_ok=True)
    asset_id = uuid.uuid4().hex[:12]
    filename = f"{asset_id}.png"
    with open(os.path.join(kind_dir, filename), "wb") as f:
        f.write(image_bytes)
    record = {
        "id": asset_id,
        "filename": filename,
        "name": name,
        "kind": kind,
        "created_at": now,
    }
    # immutable append: yeni liste yaz
    items = _read_manifest(kind_dir) + [record]
    _write_manifest(kind_dir, items)
    return record


def list_assets(kind: str, assets_dir: str) -> list[dict]:
    return list(reversed(_read_manifest(_kind_dir(assets_dir, kind))))


def asset_path(kind: str, asset_id: str, assets_dir: str) -> str | None:
    """Var olan bir varlığın dosya yolunu döndürür; id geçersiz/bulunamazsa None."""
    kind_dir = _kind_dir(assets_dir, kind)
    if not _SAFE_ID.fullmatch(asset_id):
        return None
    path = os.path.join(kind_dir, f"{asset_id}.png")
    return path if os.path.isfile(path) else None


def delete_asset(kind: str, asset_id: str, assets_dir: str) -> bool:
    kind_dir = _kind_dir(assets_dir, kind)
    if not _SAFE_ID.fullmatch(asset_id):
        return False

    items = _read_manifest(kind_dir)
    remaining = [r for r in items if r.get("id") != asset_id]
    record_existed = len(remaining) != len(items)

    file_path = os.path.join(kind_dir, f"{asset_id}.png")
    file_existed = os.path.exists(file_path)
    if file_existed:
        os.remove(file_path)

    if record_existed:
        _write_manifest(kind_dir, remaining)

    return record_existed or file_existed
