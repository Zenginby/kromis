"""İlk açılış tohumlaması: pakete gömülü KURUM logolarını kullanıcı kütüphanesine ekler.

Neden gerekli: assets/ gitignore'da ve kullanıcı verisi dizini boş başlar; tohumlama
olmadan Logo modalındaki kütüphane bomboş görünür.

Neden marker dosyası: "kütüphane boşsa tohumla" kuralı, kullanıcı logoları bilinçli
sildiğinde onları her açılışta geri getirirdi. Marker bir kez tohumlar.
"""
from __future__ import annotations

import os

import assets_store

MARKER_FILE = ".logos-seeded"
# (dosya adı, kütüphanede görünecek ad)
BUILTIN_LOGOS = (
    ("kurum-logo-blue.png", "KURUM Logo Mavi"),
    ("kurum-logo-white.png", "KURUM Logo Beyaz"),
)


def seed_builtin_logos(assets_dir: str, bundled_dir: str, marker_dir: str,
                       *, now: str) -> list[dict]:
    """Gömülü logoları bir kez kütüphaneye ekler; eklenen kayıtları döndürür."""
    marker_path = os.path.join(marker_dir, MARKER_FILE)
    if os.path.exists(marker_path):
        return []
    if not os.path.isdir(bundled_dir):
        return []
    # Kullanıcının hâlihazırda logosu varsa (mevcut kurulum) karışma.
    if assets_store.list_assets("logos", assets_dir):
        _touch(marker_path)
        return []

    added: list[dict] = []
    for filename, label in BUILTIN_LOGOS:
        source = os.path.join(bundled_dir, filename)
        if not os.path.isfile(source):
            continue
        with open(source, "rb") as f:
            added.append(assets_store.save_asset("logos", f.read(), label,
                                                 assets_dir, now=now))
    _touch(marker_path)
    return added


def _touch(path: str) -> None:
    # dirname boş olabilir (marker_dir göreli ve tek parçalı) — makedirs("") patlar.
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8"):
        pass
