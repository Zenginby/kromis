#!/usr/bin/env python3
"""Golden fixture üretici — composite.py port'unun referansını dış script'ten alır.

BİR KEZ çalıştırılır (port yazılmadan önce). Ürettiği PNG'ler commit edilir ve
tests/test_composite.py bunlara karşı **piksel** karşılaştırması yapar — bayt
değil: PNG sıkıştırması platformlar arası yeniden üretilebilir olmadığı için
golden'ların hangi mimaride üretildiği önemsiz kalır (bkz. test docstring'i).

    .venv/bin/python tools/make_logo_goldens.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "logo")
SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
# Logo çifti FIXTURES altında: bunlar bir zamanlar pakete gömülü kurumsal logolarıydı,
# uygulama marka-nötr olunca paketten çıkıp yalnızca bu golden'ların
# girdisi olarak testlerde kaldılar.
LOGO_BLUE = os.path.join(FIXTURES, "kurumsal-logo-blue.png")
LOGO_WHITE = os.path.join(FIXTURES, "kurumsal-logo-white.png")

# (ad, base, position, color, scale, shadow_alpha, shadow_blur, overlay_or_None, logo)
#
# `color` DIŞ SCRIPT'e geçen argüman; dış script auto'da zemin parlaklığına göre
# mavi/beyaz seçiyor. `logo` ise o seçimin SONUCU — dış script'in her vakada
# fiilen hangi dosyayı bindirdiği. İkisi ayrı tutuluyor çünkü composite.py artık
# tek bir `logo_path` alıyor (varyant seçimi uygulamadan kaldırıldı) ve test
# golden'ı üretmek için sonucu bilmek zorunda. Değerler dış script'in kendi
# davranışından ölçüldü; golden PNG'ler gibi bunlar da donmuş veridir.
CASES = [
    ("defaults",        "base-light", "bottom-right", "auto",  0.14, 120, 6,  None, "blue"),
    ("topleft-blue-lg", "base-light", "top-left",     "blue",  0.30, 0,   0,  None, "blue"),
    ("center-white",    "base-dark",  "center",       "white", 0.14, 200, 12, None, "white"),
    ("auto-on-light",   "base-light", "bottom-center", "auto", 0.14, 120, 6,  None, "blue"),
    ("auto-on-dark",    "base-dark",  "top-right",    "auto",  0.14, 120, 6,  None, "white"),
    ("custom-overlay",  "base-dark",  "center",       "auto",  0.20, 60,  4,  "overlay", "overlay"),
]


def make_bases() -> None:
    """Deterministik iki temel görsel: biri açık, biri koyu (auto dalının iki yönü)."""
    os.makedirs(FIXTURES, exist_ok=True)
    for name, start, end in (("base-light", (245, 240, 230), (255, 255, 255)),
                             ("base-dark", (18, 20, 28), (40, 30, 60))):
        img = Image.new("RGB", (320, 240))
        draw = ImageDraw.Draw(img)
        for y in range(240):
            t = y / 239
            draw.line([(0, y), (320, y)],
                      fill=tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3)))
        img.save(os.path.join(FIXTURES, f"{name}.png"), "PNG")

    # Özel overlay dalı için küçük, yarı saydam bir işaret.
    overlay = Image.new("RGBA", (120, 40), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).ellipse([0, 0, 119, 39], fill=(220, 60, 90, 235))
    overlay.save(os.path.join(FIXTURES, "overlay.png"), "PNG")


def write_cases_manifest() -> None:
    """Vakaları JSON'a yazar; test buradan parametrize olur.

    Liste iki yerde (üretici + test) elle durursa sessizce ayrışır ve golden'lar
    yanlış vakayla karşılaştırılır. Tek kaynak burada.
    """
    keys = ("name", "base", "position", "color", "scale",
            "shadow_alpha", "shadow_blur", "overlay", "logo")
    # encoding AÇIKÇA veriliyor: `ensure_ascii=False` ile birlikte varsayılan
    # kodlamaya bırakmak, Türkçe Windows'ta (cp1254) manifest'i bozar — aynı
    # kusur storage/assets_store'un OKUMA yolunda gerçekten patladı (v0.3.0).
    with open(os.path.join(FIXTURES, "cases.json"), "w", encoding="utf-8") as f:
        json.dump([dict(zip(keys, case)) for case in CASES], f,
                  ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    if not os.path.isfile(SCRIPT):
        print(f"HATA: dış script bulunamadı: {SCRIPT}", file=sys.stderr)
        return 1
    make_bases()
    write_cases_manifest()
    for (name, base, position, color, scale, sa, sb, overlay, _logo) in CASES:
        out = os.path.join(FIXTURES, f"golden-{name}.png")
        blue, white = LOGO_BLUE, LOGO_WHITE
        if overlay:
            blue = white = os.path.join(FIXTURES, "overlay.png")
        cmd = [sys.executable, SCRIPT, os.path.join(FIXTURES, f"{base}.png"), out,
               "--position", position, "--color", color, "--scale", str(scale),
               "--shadow-alpha", str(sa), "--shadow-blur", str(sb),
               "--logo-blue", blue, "--logo-white", white]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"HATA ({name}): {result.stderr}", file=sys.stderr)
            return 1
        print(f"✓ {os.path.basename(out)} ({os.path.getsize(out)} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
