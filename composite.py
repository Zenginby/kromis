"""KURUM logo/motto filigranı bindirme — composite-logo.py'nin süreç içi port'u.

Neden port: paket içinde ne `python3` ne de o script bulunur; subprocess çağrısı
Logo ve Banner uçlarını 500'e düşürürdü. Yan fayda: her canlı önizlemede bir
Python süreci başlatma maliyeti kalkar.

Dış script (~/.config/claude-tools/composite-logo.py) blog routine'i tarafından
bağımsız kullanıldığı için YERİNDE KALIR. Bu modül uygulamanın kaynağıdır; ikisi
arasındaki kayma riski tests/test_composite.py'deki golden fixture'larla ölçülür.
"""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageStat

BRIGHTNESS_THRESHOLD = 140  # 0-255; üstü "açık zemin" sayılır

POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

LOGO_COLORS = {"auto", "blue", "white"}


def _check_position(position: str) -> None:
    """position 9'lu ızgarada değilse ValueError fırlatır.

    Dış scriptte bu argparse `choices` ile garanti edilirdi; port'ta o kapı
    yoktu — geçersiz bir değer sessizce ortalanmış bir logoya (_vh eşleşmez)
    dönüşüyordu. Burada erken ve gürültülü başarısız oluyoruz.
    """
    if position not in POSITIONS:
        raise ValueError(f"geçersiz konum: {position!r}")


def _check_color(color: str) -> None:
    """color auto/blue/white dışındaysa ValueError fırlatır.

    Dış scriptte argparse `choices` ile sınırlıydı; port'ta beklenmeyen bir
    değer sessizce "auto" gibi davranıyordu.
    """
    if color not in LOGO_COLORS:
        raise ValueError(f"geçersiz renk: {color!r}")


def _vh(position: str) -> tuple[str, str]:
    """Konum adını (dikey, yatay) belirteçlerine ayırır."""
    if position == "center":
        return ("center", "center")
    v, _, h = position.partition("-")
    return (v, h or "center")


def region_box(img_w: int, img_h: int, position: str,
               frac: float = 0.22) -> tuple[int, int, int, int]:
    """Logonun düşeceği alanın kutusu — parlaklık örneklemesi için."""
    rw, rh = int(img_w * frac), int(img_h * frac)
    v, h = _vh(position)
    x0 = 0 if h == "left" else (img_w - rw if h == "right" else (img_w - rw) // 2)
    y0 = 0 if v == "top" else (img_h - rh if v == "bottom" else (img_h - rh) // 2)
    return (x0, y0, x0 + rw, y0 + rh)


def pick_logo(base: Image.Image, position: str, color: str,
              logo_blue: str, logo_white: str) -> str:
    """color=auto ise zemin parlaklığına göre mavi/beyaz varyantı seçer."""
    _check_position(position)
    _check_color(color)
    if color == "blue":
        return logo_blue
    if color == "white":
        return logo_white
    box = region_box(*base.size, position)
    region = base.convert("RGB").crop(box)
    brightness = ImageStat.Stat(region).mean  # [R, G, B]
    luminance = 0.299 * brightness[0] + 0.587 * brightness[1] + 0.114 * brightness[2]
    return logo_blue if luminance > BRIGHTNESS_THRESHOLD else logo_white


def paste_position(img_w: int, img_h: int, logo_w: int, logo_h: int,
                   position: str, margin_px: int) -> tuple[int, int]:
    """Logonun sol-üst köşe koordinatı (x, y) — 9'lu ızgara + kenar boşluğuna göre."""
    v, h = _vh(position)
    x = margin_px if h == "left" else (
        img_w - logo_w - margin_px if h == "right" else (img_w - logo_w) // 2)
    y = margin_px if v == "top" else (
        img_h - logo_h - margin_px if v == "bottom" else (img_h - logo_h) // 2)
    return (x, y)


def composite_logo(base_path: str, *, logo_blue: str, logo_white: str,
                   position: str = "bottom-right", color: str = "auto",
                   scale: float = 0.14, margin: float = 0.03,
                   shadow_alpha: int = 120, shadow_blur: int = 6) -> bytes:
    """Filigranı bindirip sonuç PNG'yi bayt olarak döndürür (diske yazmaz)."""
    _check_position(position)
    _check_color(color)
    base = Image.open(base_path).convert("RGBA")
    logo_path = pick_logo(base, position, color, logo_blue, logo_white)
    logo = Image.open(logo_path).convert("RGBA")

    logo_w = int(base.width * scale)
    logo_h = int(logo.height * (logo_w / logo.width))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    margin_px = int(base.width * margin)
    x, y = paste_position(base.width, base.height, logo_w, logo_h, position, margin_px)

    composed = base
    if shadow_alpha > 0:
        # Karmaşık zeminlerde okunurluk için yumuşak gölge.
        shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        shadow_mask = logo.split()[-1]
        shadow_layer = Image.new("RGBA", logo.size,
                                 (0, 0, 0, max(0, min(255, shadow_alpha))))
        shadow_layer.putalpha(shadow_mask)
        shadow.paste(shadow_layer, (x + 4, y + 6), shadow_layer)
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(0, shadow_blur)))
        composed = Image.alpha_composite(base, shadow)

    composed = composed.copy()
    composed.alpha_composite(logo, (x, y))
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()
