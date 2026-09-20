#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Filigran işaretini ve golden fixture'ını üretir (Faz 3 / 4; docs/faz3-kredi-defteri-filigran.md §4).

İki çıktı, ikisi de commit edilir:

  * `bundled/filigran.png` — ücretsiz planın işareti: 512×512, şeffaf arka plan,
    MARKA-NÖTR soyut bir şekil ("kromis" metni DEĞİL — ad ve logo lisans dışı,
    MARKA.md; depodan kuran kişi kendi PNG'sini `KROMIS_FILIGRAN_DOSYASI` ile
    gösterir). Beyaz dolgu + koyu ince kenar: composite'in gölgesiyle birlikte
    açık ve koyu zeminde okunur.
  * `tests/fixtures/filigran/base-256.png` + `golden-256.png` — sabit 256×256
    gradyan girdi ve `services.filigran.uygula`nın ona verdiği cevap.
    tests/test_filigran.py golden'ı PİKSEL düzeyinde karşılaştırır
    (tests/test_composite.py'nin kararı: PNG sıkıştırması platformlar arası
    bayt bayt yeniden üretilebilir değil).

DETERMİNİSTİK: rastgelelik yok, Pillow çizimi 4× örneklemeyle çizilip LANCZOS
ile küçültülür. İşaret, `KONUM`/`OLCEK`/`OPAKLIK` ya da composite'in gölge
sabitleri değişince golden yeniden üretilir ve PR'da yazılır — aynı araç:

    .venv/bin/python tools/make_filigran.py

Geliştirici aracı, imaja GİRMEZ (`.dockerignore`; bekçisi tests/test_docker_kapisi.py).
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

ISARET = os.path.join(REPO, "bundled", "filigran.png")
FIXTURES = os.path.join(REPO, "tests", "fixtures", "filigran")
BOYUT = 512
ORNEKLEME = 4


def make_mark() -> Image.Image:
    """Soyut işaret: kalın bir halka, içinde dört köşeli bir kıvılcım; beyaz dolgu, koyu kenar."""
    n = BOYUT * ORNEKLEME
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    merkez = n / 2
    beyaz, koyu = (255, 255, 255, 255), (20, 24, 32, 255)
    # Halka: dış yarıçap %46, kalınlık %9; koyu kenar 1 px'in 4 katı (küçülünce ~1 px).
    r_dis, kalinlik, kenar = n * 0.46, n * 0.09, 6 * ORNEKLEME
    for r, renk in ((r_dis + kenar, koyu), (r_dis, beyaz)):
        d.ellipse([merkez - r, merkez - r, merkez + r, merkez + r], fill=renk)
    r_ic = r_dis - kalinlik
    for r, renk in ((r_ic, koyu), (r_ic - kenar, (0, 0, 0, 0))):
        d.ellipse([merkez - r, merkez - r, merkez + r, merkez + r], fill=renk)
    # Kıvılcım: dört köşeli yıldız (uçlar %30, bel %7).
    uc, bel = n * 0.30, n * 0.07
    yildiz = [(merkez, merkez - uc), (merkez + bel, merkez - bel), (merkez + uc, merkez),
              (merkez + bel, merkez + bel), (merkez, merkez + uc), (merkez - bel, merkez + bel),
              (merkez - uc, merkez), (merkez - bel, merkez - bel)]
    d.polygon(yildiz, fill=beyaz, outline=koyu, width=kenar)
    kucuk = img.resize((BOYUT, BOYUT), Image.Resampling.LANCZOS)
    # PALETLİ PNG (256 renk, oktree): gerçek renkli RGBA 72 KB, paletli ~14 KB
    # (ölçüldü); işaret üç renk + kenar yumuşatması, 256 giriş kayıpsıza yakın ve
    # 1024² görselde %6'ya (~60 px) küçülünce fark ölçülemez. Oktree deterministik.
    return kucuk.quantize(256, method=Image.Quantize.FASTOCTREE)


def make_base() -> Image.Image:
    """Sabit 256×256 girdi: köşegen gradyan, alt-sağ köşe koyu — işaret oraya iner, gölge görünür olsun."""
    img = Image.new("RGB", (256, 256))
    px = img.load()
    assert px is not None
    for y in range(256):
        for x in range(256):
            t = (x + y) / 510
            px[x, y] = (round(236 - 200 * t), round(228 - 170 * t), round(214 - 120 * t))
    return img


def main() -> int:
    os.makedirs(os.path.dirname(ISARET), exist_ok=True)
    os.makedirs(FIXTURES, exist_ok=True)
    make_mark().save(ISARET, "PNG", optimize=True)
    print(f"✓ {os.path.relpath(ISARET, REPO)} ({os.path.getsize(ISARET)} bayt)")
    base_yolu = os.path.join(FIXTURES, "base-256.png")
    make_base().save(base_yolu, "PNG", optimize=True)
    print(f"✓ {os.path.relpath(base_yolu, REPO)} ({os.path.getsize(base_yolu)} bayt)")

    from services import filigran  # işaret yazıldıktan SONRA: golden o dosyayla kurulur
    with open(base_yolu, "rb") as f:
        golden = filigran.uygula(f.read(), dosya=ISARET)
    golden_yolu = os.path.join(FIXTURES, "golden-256.png")
    with open(golden_yolu, "wb") as f:
        f.write(golden)
    print(f"✓ {os.path.relpath(golden_yolu, REPO)} ({len(golden)} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
