# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Logo/motto filigranı bindirme — composite-logo.py'nin süreç içi port'u.

Neden port: paket içinde ne `python3` ne de o script bulunur; subprocess çağrısı
Logo ve Banner uçlarını 500'e düşürürdü. Yan fayda: her canlı önizlemede bir
Python süreci başlatma maliyeti kalkar.

Dış script (~/.config/claude-tools/composite-logo.py) blog routine'i tarafından
bağımsız kullanıldığı için YERİNDE KALIR. Bu modül uygulamanın kaynağıdır; ikisi
arasındaki kayma riski tests/test_composite.py'deki golden fixture'larla ölçülür.

BİNDİRİLEN GÖRSEL TEK: çağıran `logo_path` verir. Eskiden mavi/beyaz bir ÇİFT
geçilir ve `color="auto"` zemin parlaklığına göre birini seçerdi; o mekanizma
(pick_logo + region_box + parlaklık örneklemesi) yalnızca pakete gömülü eski
yerleşik logo çifti için vardı. Uygulama marka-nötr — kullanıcının kütüphanesinden
gelen logolar tek dosya — ve varyant seçimi karşılıksız kalmıştı. Golden
fixture'lar korunuyor: aynı dosya doğrudan geçildiğinde pikseller birebir aynı
(bkz. tests/fixtures/logo/cases.json'daki `logo` alanı).
"""
from __future__ import annotations

import io

from PIL import Image, ImageFilter

import i18n

# Gölgenin logoya göre kaydırması (px) — dış script'ten birebir taşındı;
# golden fixture'lar bu iki sayıya bağlı, değiştirilirse yeniden üretilmeli.
SHADOW_OFFSET = (4, 6)

POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

# Kaydırmanın ± sınırı, görsel kenarının oranı olarak. models.LogoRequest'teki
# alan sınırıyla AYNI olmak zorunda — ikisi ayrışırsa uç bir değer uçta geçip
# burada patlar ve kullanıcı Türkçe 500 görür.
OFFSET_LIMIT = 0.5


def _clamp_px(value: int, free: int) -> int:
    """`value`'yu [0, free] aralığına sıkıştırır; `free` negatifse 0 döner.

    `free` negatif OLABİLİR: yerleştirilecek şey tabandan büyükse serbest alan
    yoktur. Tek katmanlı bir `min(value, free)` o durumda negatif koordinat
    üretip bindirmeyi kadrajın dışına atardı; içteki `max(0, free)` bunu keser.
    """
    return max(0, min(value, max(0, free)))


def _check_position(position: str) -> None:
    """position 9'lu ızgarada değilse ValueError fırlatır.

    Dış scriptte bu argparse `choices` ile garanti edilirdi; port'ta o kapı
    yoktu — geçersiz bir değer sessizce ortalanmış bir logoya (_vh eşleşmez)
    dönüşüyordu. Burada erken ve gürültülü başarısız oluyoruz.
    """
    if position not in POSITIONS:
        raise ValueError(i18n.t("err.invalid_field_value", None, alan="position",
                            deger=repr(position)))


def _check_offset(value: float) -> None:
    """Kaydırma oranı ±OFFSET_LIMIT dışındaysa ValueError fırlatır.

    _check_position ile aynı gerekçe: uçtaki Pydantic sınırı tek kapı olsaydı,
    bu modülü doğrudan çağıran bir yol (blog routine'i bir gün dış script
    yerine bunu import ederse) sessizce clamp'lenmiş bir sonuç alırdı. NaN de
    reddedilir — karşılaştırmalar False dönüyor.
    """
    if not -OFFSET_LIMIT <= value <= OFFSET_LIMIT:
        raise ValueError(i18n.t("err.invalid_field_value", None, alan="offset",
                            deger=repr(value)))


def _vh(position: str) -> tuple[str, str]:
    """Konum adını (dikey, yatay) belirteçlerine ayırır."""
    if position == "center":
        return ("center", "center")
    v, _, h = position.partition("-")
    return (v, h or "center")


def paste_position(img_w: int, img_h: int, logo_w: int, logo_h: int,
                   position: str, margin_px: int,
                   offset_x_px: int = 0, offset_y_px: int = 0) -> tuple[int, int]:
    """Logonun sol-üst köşe koordinatı (x, y) — ızgara + kenar boşluğu + kaydırma.

    Izgara noktası ÇAPA, `offset_*_px` ondan sapma. Sonuç kadrajın içine
    sıkıştırılır: kullanıcı slider'ı uca dayadığında logo kenarda durur,
    kırpılmaz (kullanıcı kararı; `_composite_banner`'ın margin clamp'iyle aynı
    mantık).

    `offset=0` iken clamp hiçbir ULAŞILABİLİR girdide devreye girmez —
    composite_logo'da scale ≤ 0.5 ve margin = 0.03 olduğu için serbest alan en
    az 0.47·kenar. Yani golden fixture'ların beklediği matematik birebir
    korunuyor; test_offset_zero_is_a_no_op_for_paste_position bunu çiviliyor.
    """
    v, h = _vh(position)
    x = margin_px if h == "left" else (
        img_w - logo_w - margin_px if h == "right" else (img_w - logo_w) // 2)
    y = margin_px if v == "top" else (
        img_h - logo_h - margin_px if v == "bottom" else (img_h - logo_h) // 2)
    return (_clamp_px(x + offset_x_px, img_w - logo_w),
            _clamp_px(y + offset_y_px, img_h - logo_h))


def composite_logo(base_path: str, *, logo_path: str,
                   position: str = "bottom-right",
                   scale: float = 0.14, margin: float = 0.03,
                   shadow_alpha: int = 120, shadow_blur: int = 6,
                   offset_x: float = 0.0, offset_y: float = 0.0) -> bytes:
    """Filigranı bindirip sonuç PNG'yi bayt olarak döndürür (diske yazmaz).

    `offset_x`/`offset_y`: ızgara noktasından sapma, görsel kenarının ORANI
    olarak (+ sağ/aşağı, − sol/yukarı). Oran, piksel değil: 1024² ile
    1536×1024'te aynı slider aynı görünsün — `scale` ve `margin` ile aynı
    gelenek. Varsayılan 0 ⇒ bu fonksiyonun çıktısı birebir eskisi gibi.
    """
    _check_position(position)
    _check_offset(offset_x)
    _check_offset(offset_y)
    base = Image.open(base_path).convert("RGBA")

    # Oran → piksel dönüşümü YALNIZCA burada; aşağıdaki fonksiyonlar piksel
    # konuşur. Yatay oran genişliğe, dikey oran YÜKSEKLİĞE göre: kullanıcı için
    # "%10 aşağı" yüksekliğin %10'u demek. (`margin_px` bilinçli olarak iki
    # eksende de genişliği kullanıyor — dış script'ten öyle geldi ve golden'lar
    # ona bağlı; burada onu taklit etmek daha kötü olurdu.)
    off_x_px = round(base.width * offset_x)
    off_y_px = round(base.height * offset_y)

    logo = Image.open(logo_path).convert("RGBA")

    logo_w = int(base.width * scale)
    logo_h = int(logo.height * (logo_w / logo.width))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    margin_px = int(base.width * margin)
    x, y = paste_position(base.width, base.height, logo_w, logo_h, position,
                          margin_px, off_x_px, off_y_px)

    composed = base
    if shadow_alpha > 0:
        # Karmaşık zeminlerde okunurluk için yumuşak gölge.
        shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        shadow_mask = logo.split()[-1]
        shadow_layer = Image.new("RGBA", logo.size,
                                 (0, 0, 0, max(0, min(255, shadow_alpha))))
        shadow_layer.putalpha(shadow_mask)
        shadow.paste(shadow_layer,
                     (x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]), shadow_layer)
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(0, shadow_blur)))
        composed = Image.alpha_composite(base, shadow)

    composed = composed.copy()
    composed.alpha_composite(logo, (x, y))
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()
