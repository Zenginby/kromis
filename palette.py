# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Tema renginden uyumlu palet üretimi ve prompt metni.

Tamamen saf ve çevrimdışı: ağ yok, disk yok, global durum yok. Bir palet
`(tohum_hex, mod)` çiftinin saf fonksiyonudur — bu yüzden üretim yolunun
paleti yeniden hesaplaması için hiçbir şeyi saklamak/aramak gerekmez.

Renk uzayı OKLCH (Björn Ottosson'un OKLab'ı üzerine). HSL/`colorsys`
bilinçli olarak kullanılmıyor: HSL'de sabit lightness'ta tonu döndürmek
algısal olarak çok farklı parlaklıkta renkler üretir (HSL sarı %50 ile HSL
mavi %50 aynı görünmez). Bu özelliğin bütün değeri prompt'a giden renk
ADLARINDA olduğu için, algısal olarak bozuk bir üçlü bozuk adlar üretir —
yani doğrudan amacı baltalar. `static/style.css` de baştan sona `oklch()`
token'larıyla yazılmış; aynı uzayda kalmak tutarlı.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

COLORS_PER_PALETTE = 5

# Palet gücü: prompt'un renge ne kadar bastıracağı.
STRENGTHS = ("hint", "balanced", "strict")

# Lightness penceresi. Saf siyah/beyaz swatch hiçbir renk bilgisi taşımaz ve
# işe yaramaz bir isim üretir ("black"), o yüzden uçlar dışarıda tutulur.
_L_MIN = 0.16
_L_MAX = 0.94

# Tohumun kroması bunun altındaysa renk akromatiktir (gri/siyah/beyaz) ve
# TONU sayısal olarak anlamsızdır — atan2(≈0, ≈0) gürültüdür. Ton döndürmenin
# görünür olması için taban kroma bu değere yükseltilir, yoksa "üçlü" palet
# beş özdeş gri döndürür.
_ACHROMATIC_C = 0.02
_ACHROMATIC_BASE_C = 0.06

# Monokrom rampasının toplam açıklık aralığı (5 renk × 0.12 adım).
_MONO_STEP = 0.12
_MONO_SPAN = _MONO_STEP * (COLORS_PER_PALETTE - 1)

_HEX_RE = re.compile(r"#?([0-9a-fA-F]{6})")

# (ton_farkı°, lightness_farkı, kroma_çarpanı) — hepsi TOHUMA göre.
# Tek deklaratif tablo: yeni bir harmoni eklemek tek satır, hepsi aynı kodla
# üretilir. Her modda tam olarak bir (0, 0.0, 1.0) girdisi var → tohum rengi
# HER ZAMAN kendi paletinde yer alır (aşağıdaki verbatim kısayoluna bak).
_HARMONIES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "analogic": ((-60, 0.0, 1.0), (-30, 0.0, 1.0), (0, 0.0, 1.0),
                 (30, 0.0, 1.0), (60, 0.0, 1.0)),
    "complement": ((0, -0.14, 0.90), (0, 0.0, 1.0), (180, 0.0, 1.0),
                   (180, 0.12, 0.85), (0, 0.18, 0.70)),
    "analogic-complement": ((-30, 0.0, 1.0), (0, 0.0, 1.0), (30, 0.0, 1.0),
                            (180, 0.0, 1.0), (180, 0.14, 0.80)),
    "triad": ((0, 0.0, 1.0), (120, 0.0, 1.0), (240, 0.0, 1.0),
              (0, 0.16, 0.75), (120, -0.14, 0.90)),
    "quad": ((0, 0.0, 1.0), (90, 0.0, 1.0), (180, 0.0, 1.0),
             (270, 0.0, 1.0), (0, -0.18, 0.80)),
}

# monochrome tabloyla değil kendi rampasıyla üretilir (bkz. _monochrome).
MODES: tuple[str, ...] = ("monochrome", *_HARMONIES)


# ── sRGB ↔ OKLCH ────────────────────────────────────────────────────────────

def _linear(c: float) -> float:
    """sRGB kanalı → lineer ışık."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c: float) -> float:
    """Lineer ışık → sRGB kanalı."""
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _cbrt(x: float) -> float:
    """Küp kök. math.cbrt Python 3.11+ olduğu için negatifi elle taşıyoruz."""
    return math.copysign(abs(x) ** (1 / 3), x)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def parse_hex(value: str) -> str:
    """`"C86A3C"` / `"#c86a3c"` → `"#c86a3c"`. Geçersizse ValueError.

    3 haneli kısaltma bilinçli olarak reddedilir: `<input type="color">` her
    zaman 7 karakterlik `#rrggbb` gönderir, esneklik gereksiz yüzey açar.
    """
    if not isinstance(value, str):
        raise ValueError("hex bir metin olmalı")
    m = _HEX_RE.fullmatch(value.strip())
    if not m:
        raise ValueError(f"geçersiz hex: {value!r}")
    return "#" + m.group(1).lower()


def oklab(hex_color: str) -> tuple[float, float, float]:
    """hex → OKLab (L, a, b). color_names'in mesafe ölçüsü de bunu kullanır."""
    h = parse_hex(hex_color)[1:]
    r, g, b = (_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (_cbrt(v) for v in lms)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def hex_to_oklch(hex_color: str) -> tuple[float, float, float]:
    """hex → (L, C, h°). h derece cinsinden, [0, 360)."""
    lightness, a, b = oklab(hex_color)
    return lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _to_linear_rgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def _in_gamut(lightness: float, chroma: float, hue: float) -> bool:
    return all(-1e-4 <= c <= 1 + 1e-4 for c in _to_linear_rgb(lightness, chroma, hue))


def _hex_from(lightness: float, chroma: float, hue: float) -> str:
    channels = (
        round(255 * _clamp(_gamma(_clamp(c, 0.0, 1.0)), 0.0, 1.0))
        for c in _to_linear_rgb(lightness, chroma, hue)
    )
    return "#" + "".join(f"{c:02x}" for c in channels)


def oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    """OKLCH → hex. Gamut dışıysa TON ve LIGHTNESS korunarak kroma düşürülür.

    Bileşenleri kırpmak yerine bu yapılıyor: kırpma rengi kaydırır ve iki
    farklı swatch'ı aynı hex'e düşürebiliyor. Aynı hex = aynı isim = prompt'a
    tekrarlı renk adı = palet bozulur. sRGB'nin taşıyabildiği en yüksek kroma
    tona göre ~0.29–0.37 arasında değiştiği için sabit bir üst sınır yanlış
    olurdu; ton başına ikili arama doğru cevabı verir.
    """
    lightness = _clamp(lightness, 0.0, 1.0)
    chroma = max(chroma, 0.0)
    if _in_gamut(lightness, chroma, hue):
        return _hex_from(lightness, chroma, hue)
    lo, hi = 0.0, chroma
    for _ in range(12):  # hata < C/4096 — göz için kesin
        mid = (lo + hi) / 2
        if _in_gamut(lightness, mid, hue):
            lo = mid
        else:
            hi = mid
    return _hex_from(lightness, lo, hue)


# ── Harmoni ─────────────────────────────────────────────────────────────────

def _monochrome(seed: str, lightness: float, chroma: float, hue: float) -> tuple[str, ...]:
    """Aynı ton, eşit aralıklı 5 açıklık.

    Pencere KIRPILMAZ, KAYDIRILIR: tohum L=0.93 gibi bir uçtaysa kırpma beş
    rengi tepede birbirine yapıştırırdı. Kaydırma her tohumda 5 belirgin
    açıklık garantiler. Rampanın tohuma en yakın basamağı tohumun tam hex'iyle
    değiştirilir → kullanıcının seçtiği renk her zaman paletinde yer alır.
    """
    base = _clamp(lightness - _MONO_SPAN / 2, _L_MIN, _L_MAX - _MONO_SPAN)
    steps = [base + i * _MONO_STEP for i in range(COLORS_PER_PALETTE)]
    nearest = min(range(COLORS_PER_PALETTE), key=lambda i: abs(steps[i] - lightness))
    return tuple(
        seed if i == nearest else oklch_to_hex(step, chroma, hue)
        for i, step in enumerate(steps)
    )


def harmony(seed_hex: str, mode: str) -> tuple[str, ...]:
    """`(tohum, mod)` → 5 hex. Mod geçersizse ValueError.

    Deterministik ve çevrimdışı: aynı girdi her zaman aynı çıktıyı verir.
    """
    if mode not in MODES:
        raise ValueError(f"geçersiz mod: {mode!r}")
    seed = parse_hex(seed_hex)
    lightness, chroma, hue = hex_to_oklch(seed)

    if mode == "monochrome":
        return _monochrome(seed, lightness, chroma, hue)

    if chroma < _ACHROMATIC_C:
        chroma = _ACHROMATIC_BASE_C

    table = _HARMONIES[mode]
    # Açıklık penceresi KIRPILMAZ, KAYDIRILIR — _monochrome ile aynı mantık.
    # Her rengin lightness'ını tek tek kırpmak, uçtaki bir tohumda (beyaz,
    # siyah) birden fazla girdiyi aynı açıklığa yapıştırıp aynı hex'i
    # ürettiriyordu. Tabanı kaydırmak bağıl farkları koruyor.
    offsets = [d_light for _, d_light, _ in table]
    base = _clamp(lightness, _L_MIN - min(offsets), _L_MAX - max(offsets))

    colors = []
    for d_hue, d_light, chroma_factor in table:
        if d_hue == 0 and d_light == 0 and chroma_factor == 1.0:
            # Tohumun kendisi: gidiş-dönüşü atla. Hem kullanıcının seçtiği
            # rengin bire bir korunmasını hem de ±1/255 kayan nokta
            # oynamasının testleri titretmemesini sağlar.
            colors.append(seed)
            continue
        colors.append(oklch_to_hex(
            base + d_light,
            chroma * chroma_factor,
            (hue + d_hue) % 360,
        ))
    return tuple(colors)


# ── Prompt metni ────────────────────────────────────────────────────────────

# Görsel modelleri bir renk listesi verildiğinde gerçekten palet şeridi/renk
# kartı çizmeye meyilli. Bu cümle altı şablonun hepsinde yer alıyor.
#
# Aynı sebeple metinlerde "palette" ismi TEK BAŞINA kullanılmıyor ("Color
# palette: ..." bazen modele ressam paleti/renk şeridi çizdiriyor); başlık
# her yerde "Color direction".
_NO_RENDER = ("Do not render the color scheme itself — no swatches, color "
              "chips, labels or hex codes.")

# Kullanıcının kendi renk kelimeleriyle çatışmayı azaltan öncelik cümlesi.
# `strict`'te bilinçli olarak YOK — "katı" tam olarak bu demek.
_USER_WINS = ("If the description above already names a color for a specific "
              "object, keep that color for that object.")

# Renklere gidecek yer vermek uyumu belirgin artırıyor: sınırsız bir renk
# listesi verilince model ya gökkuşağı gradyan yapıyor ya birini seçip
# gerisini atıyor. Rol etiketi (zemin/baskın/vurgu) yerine SWATCH SIRASI
# kullanılıyor — ek arayüz gerektirmeden aynı işi görüyor.
_ORDER_CUE = ("earlier colors across the larger areas, the last as small "
              "accents")

# Metin İngilizce: prompt modele gidiyor ve gpt-image-2 renk talimatlarına
# İngilizce belirgin biçimde daha iyi tepki veriyor. Kullanıcının Türkçe
# prompt'una dokunulmuyor, bu blok arkasına ekleniyor.
#
# `edit` şablonları AYRI olmak zorunda: üretim ifadesi ("use these colors for
# the dominant colors") modele yeniden boyama söyler ve referans görselin
# kompozisyonunu yok eder. Düzenlemede istenen şey renk derecelendirmesi.
_TEMPLATES: dict[tuple[str, str], str] = {
    ("generate", "hint"): (
        "Color direction: lean toward {names} without forcing them — as a "
        "gentle undertone of the lighting and materials rather than the "
        "subject of the image. " + _USER_WINS + " " + _NO_RENDER),
    ("generate", "balanced"): (
        "Color direction — use these colors: {detailed}. Let them carry the "
        "dominant colors, lighting and overall mood of the image, with "
        + _ORDER_CUE + ", blended naturally into the scene. Any other color "
        "should read as a neutral grey, white or black, or as a lighter or "
        "darker shade of these. " + _USER_WINS + " " + _NO_RENDER),
    ("generate", "strict"): (
        "Color direction — strict color scheme, use only these colors: "
        "{detailed}, with " + _ORDER_CUE + ". Do not introduce any other "
        "saturated hue; every remaining color must be a neutral grey, white "
        "or black, or a lighter or darker shade of these. " + _NO_RENDER),
    ("edit", "hint"): (
        "Color direction: nudge the overall color grade toward {names}, "
        "keeping the composition, subject and framing exactly as they are. "
        + _USER_WINS + " " + _NO_RENDER),
    ("edit", "balanced"): (
        "Color direction — shift the image's colors toward this scheme while "
        "keeping the composition, subject, framing and lighting unchanged: "
        "{detailed}. Re-grade the existing colors toward the nearest of "
        "these; do not repaint or move anything. " + _NO_RENDER),
    ("edit", "strict"): (
        "Color direction — shift the image's colors to this scheme exactly, "
        "keeping the composition, subject and framing unchanged: {detailed}. "
        "Replace every color outside the scheme with the nearest of these and "
        "keep neutral greys neutral. Do not repaint or move anything. "
        + _NO_RENDER),
}

# Prompt bağlamı: yeni görsel üretimi mi, mevcut görselin düzenlenmesi mi.
TASKS = ("generate", "edit")


def _join_names(names: Sequence[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def prompt_suffix(colors: Sequence[Mapping[str, str]], strength: str,
                  *, task: str = "generate") -> str:
    """Prompt'un sonuna eklenecek renk yönlendirmesi. Palet yoksa boş metin.

    `colors`: `[{"hex": "#c86a3c", "name": "terracotta orange"}, ...]`
    `task`: `"generate"` (yeni görsel) veya `"edit"` (referanslı düzenleme).

    Hex kodları yalnızca `balanced` ve `strict`'te yer alır; `hint` zaten gevşek
    bir yönlendirme olduğu için orada hex sayısal gürültüden başka bir şey
    yapmıyor. Ad = anlamsal sinyal, hex = kesinlik çıpası.
    """
    if not colors:
        return ""
    if strength not in STRENGTHS:
        raise ValueError(f"geçersiz güç: {strength!r}")
    if task not in TASKS:
        raise ValueError(f"geçersiz görev: {task!r}")
    body = _TEMPLATES[(task, strength)].format(
        names=_join_names([str(c["name"]) for c in colors]),
        detailed=", ".join(f"{c['name']} ({c['hex']})" for c in colors),
    )
    # Boş satır ayrımı: modelin bunu kullanıcının cümlesinin devamı değil,
    # ayrı bir talimat olarak okuması için.
    return "\n\n" + body
