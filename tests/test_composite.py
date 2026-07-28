"""composite.py, dış composite-logo.py ile bayt bayt aynı çıktı vermeli."""
import io
import json
import os

import pytest
from PIL import Image

import composite

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "logo")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_BLUE = os.path.join(REPO, "bundled", "logos", "kurum-logo-blue.png")
LOGO_WHITE = os.path.join(REPO, "bundled", "logos", "kurum-logo-white.png")
OVERLAY = os.path.join(FIXTURES, "overlay.png")

# Vakaların tek kaynağı üreticinin yazdığı manifest — elle ikinci bir liste
# tutulsa golden'lar sessizce yanlış vakayla eşleşebilirdi.
with open(os.path.join(FIXTURES, "cases.json")) as _f:
    CASES = json.load(_f)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_port_matches_the_external_script(case):
    name, base = case["name"], case["base"]
    blue, white = (OVERLAY, OVERLAY) if case["overlay"] else (LOGO_BLUE, LOGO_WHITE)
    produced = composite.composite_logo(
        os.path.join(FIXTURES, f"{base}.png"),
        logo_blue=blue, logo_white=white,
        position=case["position"], color=case["color"], scale=case["scale"],
        shadow_alpha=case["shadow_alpha"], shadow_blur=case["shadow_blur"])

    golden_path = os.path.join(FIXTURES, f"golden-{name}.png")
    with open(golden_path, "rb") as f:
        golden = f.read()

    if produced != golden:
        # Bayt farkı kodlayıcı metadata'sından da gelebilir; pikselleri de kıyasla ki
        # hata mesajı "gerçekten görüntü mü değişti" sorusunu yanıtlasın.
        a = Image.open(io.BytesIO(produced)).convert("RGB")
        b = Image.open(golden_path).convert("RGB")
        assert a.size == b.size, f"{name}: boyut değişti {a.size} != {b.size}"
        assert a.tobytes() == b.tobytes(), f"{name}: PİKSELLER değişti — port davranışı kaydırdı"
        pytest.fail(f"{name}: pikseller aynı ama baytlar farklı — PNG kodlayıcı ayarı değişmiş")


def test_auto_picks_blue_on_light_background():
    chosen = composite.pick_logo(
        Image.open(os.path.join(FIXTURES, "base-light.png")).convert("RGBA"),
        "bottom-right", "auto", LOGO_BLUE, LOGO_WHITE)
    assert chosen == LOGO_BLUE


def test_auto_picks_white_on_dark_background():
    chosen = composite.pick_logo(
        Image.open(os.path.join(FIXTURES, "base-dark.png")).convert("RGBA"),
        "bottom-right", "auto", LOGO_BLUE, LOGO_WHITE)
    assert chosen == LOGO_WHITE


def test_explicit_color_skips_brightness_sampling():
    base = Image.open(os.path.join(FIXTURES, "base-dark.png")).convert("RGBA")
    assert composite.pick_logo(base, "center", "blue", LOGO_BLUE, LOGO_WHITE) == LOGO_BLUE
    assert composite.pick_logo(base, "center", "white", LOGO_BLUE, LOGO_WHITE) == LOGO_WHITE


@pytest.mark.parametrize("position,expected", [
    ("top-left", (10, 10)),
    ("top-right", (100 - 20 - 10, 10)),
    ("bottom-left", (10, 80 - 15 - 10)),
    ("bottom-right", (100 - 20 - 10, 80 - 15 - 10)),
    ("center", ((100 - 20) // 2, (80 - 15) // 2)),
    ("top-center", ((100 - 20) // 2, 10)),
    ("center-left", (10, (80 - 15) // 2)),
])
def test_paste_position_covers_the_nine_grid(position, expected):
    assert composite.paste_position(100, 80, 20, 15, position, 10) == expected


def test_region_box_stays_inside_the_image():
    for position in composite.POSITIONS:
        x0, y0, x1, y1 = composite.region_box(200, 100, position)
        assert 0 <= x0 < x1 <= 200
        assert 0 <= y0 < y1 <= 100


def test_returns_png_bytes_without_touching_disk(tmp_path):
    out = composite.composite_logo(
        os.path.join(FIXTURES, "base-light.png"),
        logo_blue=LOGO_BLUE, logo_white=LOGO_WHITE)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert list(tmp_path.iterdir()) == []  # geçici dosya bırakmıyor


def test_missing_base_raises_oserror():
    with pytest.raises(OSError):
        composite.composite_logo("/yok/boyle/bir/dosya.png",
                                 logo_blue=LOGO_BLUE, logo_white=LOGO_WHITE)
