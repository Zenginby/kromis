"""Marka varlıklarını SVG kaynaklarından üretir: favicon, apple-touch-icon,
Windows .ico ve macOS .iconset (PNG'ler; .icns'e çevirme build.sh'te `iconutil`
ile olur, o araç yalnız macOS'ta var).

Kaynak SVG'ler tek doğruluk kaynağı (branding/kromis-mark.svg ve
kromis-icon-square.svg); bu betik geliştirici makinesinde elle çalıştırılır,
build/CI adımı DEĞİLDİR — çıktılar repoya commit edilir.
"""
from __future__ import annotations

import os

import cairosvg
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING = os.path.join(REPO, "branding")
BARE_SVG = os.path.join(BRANDING, "kromis-mark.svg")
SQUARE_SVG = os.path.join(BRANDING, "kromis-icon-square.svg")


def render_png(svg_path: str, size: int) -> Image.Image:
    data = cairosvg.svg2png(url=svg_path, output_width=size, output_height=size)
    return Image.open(__import__("io").BytesIO(data)).convert("RGBA")


def main() -> None:
    static_dir = os.path.join(REPO, "static")

    # ── favicon (şeffaf, çıplak diyafram) ──────────────────────────────
    fav_sizes = [16, 32, 48]
    fav_imgs = [render_png(BARE_SVG, s) for s in fav_sizes]
    fav_imgs[0].save(
        os.path.join(static_dir, "favicon.ico"),
        sizes=[(s, s) for s in fav_sizes],
    )
    with open(BARE_SVG, encoding="utf-8") as f, \
            open(os.path.join(static_dir, "favicon.svg"), "w", encoding="utf-8") as out:
        out.write(f.read())

    # ── apple-touch-icon (opak kare simge) ─────────────────────────────
    render_png(SQUARE_SVG, 180).save(os.path.join(static_dir, "apple-touch-icon.png"))

    # ── Windows .ico (opak kare simge, çoklu boyut) ────────────────────
    ico_sizes = [16, 32, 48, 64, 128, 256]
    ico_imgs = [render_png(SQUARE_SVG, s) for s in ico_sizes]
    ico_imgs[0].save(
        os.path.join(BRANDING, "kromis.ico"),
        sizes=[(s, s) for s in ico_sizes],
    )

    # ── macOS .iconset kaynağı (iconutil ileride bunu .icns'e çevirir) ──
    iconset_dir = os.path.join(BRANDING, "kromis.iconset")
    os.makedirs(iconset_dir, exist_ok=True)
    iconset_sizes = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for name, size in iconset_sizes.items():
        render_png(SQUARE_SVG, size).save(os.path.join(iconset_dir, name))

    print("✓ favicon.ico, favicon.svg, apple-touch-icon.png -> static/")
    print("✓ kromis.ico -> branding/")
    print(f"✓ {len(iconset_sizes)} PNG -> branding/kromis.iconset/")


if __name__ == "__main__":
    main()
