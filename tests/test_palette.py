"""palette.py — saf renk matematiği ve prompt metni testleri.

Ağ yok, disk yok, TestClient yok: tests/test_azure_client.py stilinde düz
birim testleri.
"""
import re

import pytest

import palette

_HEX = re.compile(r"#[0-9a-f]{6}")

# Farklı ton/açıklık/kroma bölgelerinden temsili tohumlar.
SEEDS = ("#c86a3c", "#2e5fa3", "#000000", "#ffffff", "#808080",
         "#ff0000", "#00ff00", "#0000ff", "#f0e6d2", "#12030a")


# ── Dönüşümler ──────────────────────────────────────────────────────────────

def test_oklab_matches_published_anchors():
    """Ottosson referans değerleri — matris sabitlerinin bekçisi."""
    lightness, a, b = palette.oklab("#ffffff")
    assert lightness == pytest.approx(1.0, abs=1e-3)
    assert a == pytest.approx(0.0, abs=1e-3)
    assert b == pytest.approx(0.0, abs=1e-3)

    lightness, a, b = palette.oklab("#ff0000")
    assert lightness == pytest.approx(0.6280, abs=1e-3)
    assert a == pytest.approx(0.2249, abs=1e-3)
    assert b == pytest.approx(0.1258, abs=1e-3)


@pytest.mark.parametrize("hex_color", SEEDS)
def test_hex_oklch_round_trip(hex_color):
    lightness, chroma, hue = palette.hex_to_oklch(hex_color)
    assert palette.oklch_to_hex(lightness, chroma, hue) == hex_color


def test_achromatic_colors_have_near_zero_chroma():
    for grey in ("#000000", "#808080", "#ffffff"):
        _, chroma, _ = palette.hex_to_oklch(grey)
        assert chroma < palette._ACHROMATIC_C


def test_parse_hex_normalizes():
    assert palette.parse_hex("C86A3C") == "#c86a3c"
    assert palette.parse_hex("#C86A3C") == "#c86a3c"
    assert palette.parse_hex("  #c86a3c  ") == "#c86a3c"


@pytest.mark.parametrize("bad", ["", "#12", "zzzzzz", "#1234567", "#abc", None, 42])
def test_parse_hex_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        palette.parse_hex(bad)


# ── Harmoni ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", palette.MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_mode_returns_five_valid_distinct_colors(mode, seed):
    colors = palette.harmony(seed, mode)
    assert len(colors) == palette.COLORS_PER_PALETTE
    assert all(_HEX.fullmatch(c) for c in colors)
    # Tekrarlı hex = tekrarlı isim = bozuk prompt. Gamut eşlemesinin kroma
    # ikili aramasıyla (kırpma yerine) yapılmasının bütün sebebi bu.
    assert len(set(colors)) == palette.COLORS_PER_PALETTE, colors


@pytest.mark.parametrize("mode", palette.MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_seed_is_always_in_its_own_palette(mode, seed):
    assert palette.parse_hex(seed) in palette.harmony(seed, mode)


@pytest.mark.parametrize("mode", palette.MODES)
def test_harmony_is_deterministic(mode):
    assert palette.harmony("#c86a3c", mode) == palette.harmony("#c86a3c", mode)


@pytest.mark.parametrize("mode", palette.MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_generated_colors_are_in_gamut(mode, seed):
    """Her çıktı kendine gidiş-dönüş yapmalı.

    Bileşen kırpması yapılsaydı üretilen hex farklı bir OKLCH'ye çözülür ve
    geri dönüşte başka bir hex verirdi; bu test tam olarak onu yakalar.
    """
    for hex_color in palette.harmony(seed, mode):
        lightness, chroma, hue = palette.hex_to_oklch(hex_color)
        assert palette.oklch_to_hex(lightness, chroma, hue) == hex_color


def test_monochrome_keeps_hue_and_varies_lightness():
    colors = palette.harmony("#c86a3c", "monochrome")
    lightnesses = [palette.hex_to_oklch(c)[0] for c in colors]
    assert lightnesses == sorted(lightnesses)
    hues = [palette.hex_to_oklch(c)[2] for c in colors]
    assert max(hues) - min(hues) < 3.0


@pytest.mark.parametrize("seed", ["#ffffff", "#000000", "#f0e6d2", "#12030a"])
def test_monochrome_window_is_shifted_not_clipped(seed):
    """Uç açıklıktaki tohumlarda bile 5 BELİRGİN açıklık kalmalı."""
    lightnesses = sorted(palette.hex_to_oklch(c)[0]
                         for c in palette.harmony(seed, "monochrome"))
    gaps = [b - a for a, b in zip(lightnesses, lightnesses[1:])]
    assert min(gaps) > 0.05, lightnesses


def test_complement_contains_opposite_hue():
    _, _, seed_hue = palette.hex_to_oklch("#2e5fa3")
    hues = [palette.hex_to_oklch(c)[2] for c in palette.harmony("#2e5fa3", "complement")]
    opposite = (seed_hue + 180) % 360
    assert any(min(abs(h - opposite), 360 - abs(h - opposite)) < 8 for h in hues)


def test_triad_hues_are_120_apart():
    hues = sorted(palette.hex_to_oklch(c)[2]
                  for c in palette.harmony("#2e5fa3", "triad"))
    # 5 rengin 3'ü ana üçlü; ardışık farklar arasında ~120 bulunmalı.
    spread = {round(b - a) for a, b in zip(hues, hues[1:])}
    assert any(110 <= d <= 130 for d in spread), hues


@pytest.mark.parametrize("mode", [m for m in palette.MODES if m != "monochrome"])
@pytest.mark.parametrize("grey", ["#000000", "#808080", "#ffffff"])
def test_achromatic_seeds_still_produce_varied_hues(mode, grey):
    """Gri tohumda ton sayısal olarak anlamsız; koruma olmasa 5 özdeş gri gelirdi."""
    colors = palette.harmony(grey, mode)
    assert len(set(colors)) == palette.COLORS_PER_PALETTE, colors


def test_harmony_rejects_unknown_mode():
    with pytest.raises(ValueError):
        palette.harmony("#c86a3c", "kaleidoscope")


def test_modes_contains_the_six_documented_harmonies():
    assert set(palette.MODES) == {
        "monochrome", "analogic", "complement",
        "analogic-complement", "triad", "quad",
    }


# ── Prompt metni ────────────────────────────────────────────────────────────

COLORS = [
    {"hex": "#101b2e", "name": "midnight navy blue"},
    {"hex": "#2e5fa3", "name": "cobalt blue"},
    {"hex": "#3e7c7b", "name": "slate teal"},
]


def test_prompt_suffix_is_empty_without_colors():
    assert palette.prompt_suffix([], "balanced") == ""


@pytest.mark.parametrize("task", palette.TASKS)
@pytest.mark.parametrize("strength", palette.STRENGTHS)
def test_prompt_suffix_starts_with_blank_line_and_names_every_color(task, strength):
    out = palette.prompt_suffix(COLORS, strength, task=task)
    assert out.startswith("\n\n")
    for color in COLORS:
        assert color["name"] in out


@pytest.mark.parametrize("task", palette.TASKS)
def test_hex_codes_appear_only_in_balanced_and_strict(task):
    assert "#2e5fa3" not in palette.prompt_suffix(COLORS, "hint", task=task)
    for strength in ("balanced", "strict"):
        out = palette.prompt_suffix(COLORS, strength, task=task)
        assert all(c["hex"] in out for c in COLORS)


@pytest.mark.parametrize("task", palette.TASKS)
def test_every_strength_forbids_rendering_the_scheme(task):
    """Modeller renk listesi görünce gerçekten swatch şeridi çiziyor."""
    for strength in palette.STRENGTHS:
        out = palette.prompt_suffix(COLORS, strength, task=task)
        assert "no swatches" in out


@pytest.mark.parametrize("task", palette.TASKS)
def test_bare_palette_noun_is_never_used(task):
    """"Color palette:" ifadesi modele ressam paleti çizdirebiliyor."""
    for strength in palette.STRENGTHS:
        out = palette.prompt_suffix(COLORS, strength, task=task)
        assert "Color palette" not in out
        assert out.lstrip().startswith("Color direction")


@pytest.mark.parametrize("task", palette.TASKS)
def test_strengths_are_mutually_distinct(task):
    outs = {palette.prompt_suffix(COLORS, s, task=task) for s in palette.STRENGTHS}
    assert len(outs) == len(palette.STRENGTHS)


@pytest.mark.parametrize("task", palette.TASKS)
def test_only_strict_omits_the_user_priority_clause(task):
    """Katı mod tam olarak "kullanıcının renk kelimelerini ez" demek."""
    assert "take priority" not in palette.prompt_suffix(COLORS, "strict", task=task)
    assert "keep that color" not in palette.prompt_suffix(COLORS, "strict", task=task)


def test_edit_templates_preserve_composition_and_generate_ones_do_not():
    """En kritik ayrım: üretim ifadesi düzenlemede referans görseli yok eder."""
    for strength in palette.STRENGTHS:
        edit = palette.prompt_suffix(COLORS, strength, task="edit")
        assert "composition" in edit
        assert "framing" in edit

        generate = palette.prompt_suffix(COLORS, strength, task="generate")
        assert "composition" not in generate


def test_edit_balanced_and_strict_forbid_repainting():
    for strength in ("balanced", "strict"):
        out = palette.prompt_suffix(COLORS, strength, task="edit")
        assert "do not repaint or move anything" in out.lower()


def test_strict_generate_forbids_other_hues():
    out = palette.prompt_suffix(COLORS, "strict", task="generate")
    assert "use only these colors" in out
    assert "saturated hue" in out


def test_names_are_joined_with_and_in_hint_mode():
    out = palette.prompt_suffix(COLORS, "hint")
    assert "midnight navy blue, cobalt blue and slate teal" in out


def test_name_joining_handles_one_two_and_many():
    assert palette._join_names(["a"]) == "a"
    assert palette._join_names(["a", "b"]) == "a and b"
    assert palette._join_names(["a", "b", "c"]) == "a, b and c"


def test_single_color_palette_names_it_without_a_dangling_conjunction():
    out = palette.prompt_suffix([COLORS[0]], "hint")
    assert "toward midnight navy blue without" in out


@pytest.mark.parametrize("bad", ["", "STRICT", "loud", None])
def test_prompt_suffix_rejects_unknown_strength(bad):
    with pytest.raises(ValueError):
        palette.prompt_suffix(COLORS, bad)


@pytest.mark.parametrize("bad", ["", "GENERATE", "remix", None])
def test_prompt_suffix_rejects_unknown_task(bad):
    with pytest.raises(ValueError):
        palette.prompt_suffix(COLORS, "balanced", task=bad)


def test_suffix_stays_within_a_sane_length_budget():
    """Prompt'un 4000 karakter sınırıyla birlikte yönetilebilir kalması için."""
    for task in palette.TASKS:
        for strength in palette.STRENGTHS:
            colors = [{"hex": "#c86a3c", "name": "a" * 32}] * palette.COLORS_PER_PALETTE
            assert len(palette.prompt_suffix(colors, strength, task=task)) < 800
