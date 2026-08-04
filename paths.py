"""Yol çözümü: PyInstaller paketi içinde ve geliştirmede farklı kökler.

Paket içinde `__file__` geçici çıkarma dizinine düşer; oraya yazılan geçmiş her
kapanışta kaybolur. Bu yüzden yazılabilir veri (output/, assets/) kullanıcının
Application Support dizinine, salt-okunur içerik (static/, bundled/) ise
PyInstaller'ın `sys._MEIPASS` dizinine bağlanır.

Geliştirmede (frozen değilken) her iki kök de repo dizinidir — mevcut testlerin
dayandığı yerleşim birebir korunur.
"""
from __future__ import annotations

import os
import sys

APP_NAME = "GPT-Image Studio"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGO_VARIANTS = ("blue", "white")


def is_frozen() -> bool:
    """PyInstaller paketi içinde mi çalışıyoruz?"""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """Salt-okunur paket içeriğinin kökü (static/, bundled/)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", REPO_DIR)
    return REPO_DIR


def data_dir() -> str:
    """Yazılabilir kullanıcı verisinin kökü (output/, assets/, manifest'ler)."""
    if is_frozen():
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    return REPO_DIR


def output_dir() -> str:
    return os.path.join(data_dir(), "output")


def assets_dir() -> str:
    return os.path.join(data_dir(), "assets")


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def bundled_logos_dir() -> str:
    return os.path.join(resource_dir(), "bundled", "logos")


def bundled_prompts_dir() -> str:
    """Gömülü sistem talimatlarının dizini (Prompt Yönetmeni personası)."""
    return os.path.join(resource_dir(), "bundled", "prompts")


def chat_instructions_override() -> str:
    """Kullanıcının düzenleyebildiği talimat dosyası (varsa gömülü olanı EZER).

    data_dir()'de, resource_dir()'de DEĞİL: paket içeriği salt-okunur ve frozen'da
    _MEIPASS her kapanışta siliniyor — oraya yazılan bir talimat kaybolur ve
    paketlenmiş .app'te hiç düzenlenemez.
    """
    return os.path.join(data_dir(), "chat-instructions.md")


def builtin_logo(variant: str) -> str:
    """Gömülü KURUM logosunun yolu. variant: "blue" | "white"."""
    if variant not in _LOGO_VARIANTS:
        raise ValueError(f"geçersiz logo varyantı: {variant!r}")
    return os.path.join(bundled_logos_dir(), f"kurum-logo-{variant}.png")


def ensure_data_dirs() -> None:
    """Yazılabilir dizinleri oluşturur; var olanlara dokunmaz."""
    for path in (output_dir(), assets_dir()):
        os.makedirs(path, exist_ok=True)
