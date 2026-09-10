"""Marka varlıklarını SVG kaynaklarından üretir: favicon, apple-touch-icon,
Windows .ico ve macOS .iconset (PNG'ler; .icns'e çevirme build.sh'te `iconutil`
ile olur, o araç yalnız macOS'ta var).

Kaynak SVG'ler tek doğruluk kaynağı (branding/kromis-mark.svg ve
kromis-icon-square.svg); bu betik geliştirici makinesinde elle çalıştırılır,
build/CI adımı DEĞİLDİR — çıktılar repoya commit edilir.
"""
from __future__ import annotations

import io
import os

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING = os.path.join(REPO, "branding")
BARE_SVG = os.path.join(BRANDING, "kromis-mark.svg")
SQUARE_SVG = os.path.join(BRANDING, "kromis-icon-square.svg")


def render_png(svg_path: str, size: int) -> Image.Image:
    # 1. Öncelik: resvg-py (C çalışma zamanı kütüphanesi istemez, her ortamda çalışır)
    try:
        import resvg_py

        with open(svg_path, encoding="utf-8") as f:
            svg_text = f.read()
        png_bytes = resvg_py.svg_to_bytes(svg_text, width=size, height=size)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except ImportError:
        pass

    # 2. Öncelik: cairosvg (macOS/Linux'ta brew/apt cairo kuruluysa)
    try:
        import cairosvg

        data = cairosvg.svg2png(url=svg_path, output_width=size, output_height=size)
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except (ImportError, OSError):
        pass

    # 3. Öncelik: C kütüphaneleri yoksa repoda var olan yüksek çözünürlüklü
    # 1024x1024 master PNG'den (lumeo.iconset) Lanczos ile ölçekle
    square_1024 = os.path.join(BRANDING, "lumeo.iconset", "icon_512x512@2x.png")
    if os.path.abspath(svg_path) == os.path.abspath(SQUARE_SVG) and os.path.isfile(square_1024):
        master = Image.open(square_1024).convert("RGBA")
        return master.resize((size, size), Image.Resampling.LANCZOS)

    raise RuntimeError(
        f"SVG render edilemedi ({svg_path}). Lütfen `pip install resvg-py` veya "
        "`pip install cairosvg` (cairo C kütüphanesiyle birlikte) kurun."
    )


def main() -> None:
    static_dir = os.path.join(REPO, "static")

    # ── favicon (şeffaf, çıplak diyafram) ──────────────────────────────
    # Pillow'un IcoImagePlugin._save mantığı: `im.size`'dan büyük boyutları
    # sessizce atar ve diğer kareleri `append_images`tan toplar. Bu yüzden
    # save() en BÜYÜK görsel üzerinden çağrılmalı ve geri kalan boyutlar
    # append_images ile verilmelidir.
    fav_sizes = [16, 32, 48]
    fav_imgs = [render_png(BARE_SVG, s) for s in fav_sizes]
    fav_imgs[-1].save(
        os.path.join(static_dir, "favicon.ico"),
        format="ICO",
        sizes=[(s, s) for s in fav_sizes],
        append_images=fav_imgs[:-1],
    )
    with open(BARE_SVG, encoding="utf-8") as f, \
            open(os.path.join(static_dir, "favicon.svg"), "w", encoding="utf-8") as out:
        out.write(f.read())

    # ── apple-touch-icon (opak kare simge) ─────────────────────────────
    render_png(SQUARE_SVG, 180).save(os.path.join(static_dir, "apple-touch-icon.png"))

    # ── Windows .ico (opak kare simge, çoklu boyut) ────────────────────
    # 24: %125 DPI görev çubuğu; 48: Windows masaüstü orta simgeler (varsayılan);
    # 64: %200 DPI görev çubuğu / büyük liste; 128/256: büyük ve çok büyük simgeler.
    # En büyük görsel (256) temel alınarak kaydedilir; aksi takdirde Pillow
    # 16'dan büyük tüm boyutları sessizce düşürür (v0.4.2'deki bulanıklık hatası).
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_imgs = [render_png(SQUARE_SVG, s) for s in ico_sizes]
    ico_imgs[-1].save(
        os.path.join(BRANDING, "kromis.ico"),
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_imgs[:-1],
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

    print("[OK] favicon.ico, favicon.svg, apple-touch-icon.png -> static/")
    print("[OK] kromis.ico -> branding/")
    print(f"[OK] {len(iconset_sizes)} PNG -> branding/kromis.iconset/")


if __name__ == "__main__":
    main()
