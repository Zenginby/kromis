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
# Gölgenin logoya göre kaydırması (px) — dış script'ten birebir taşındı;
# golden fixture'lar bu iki sayıya bağlı, değiştirilirse yeniden üretilmeli.
SHADOW_OFFSET = (4, 6)

POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

LOGO_COLORS = {"auto", "blue", "white"}

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
        raise ValueError(f"geçersiz konum: {position!r}")


def _check_color(color: str) -> None:
    """color auto/blue/white dışındaysa ValueError fırlatır.

    Dış scriptte argparse `choices` ile sınırlıydı; port'ta beklenmeyen bir
    değer sessizce "auto" gibi davranıyordu.
    """
    if color not in LOGO_COLORS:
        raise ValueError(f"geçersiz renk: {color!r}")


def _check_offset(value: float) -> None:
    """Kaydırma oranı ±OFFSET_LIMIT dışındaysa ValueError fırlatır.

    _check_position/_check_color ile aynı gerekçe: uçtaki Pydantic sınırı tek
    kapı olsaydı, bu modülü doğrudan çağıran bir yol (blog routine'i bir gün
    dış script yerine bunu import ederse) sessizce clamp'lenmiş bir sonuç
    alırdı. NaN de reddedilir — karşılaştırmalar False dönüyor.
    """
    if not -OFFSET_LIMIT <= value <= OFFSET_LIMIT:
        raise ValueError(f"geçersiz kaydırma: {value!r}")


def _vh(position: str) -> tuple[str, str]:
    """Konum adını (dikey, yatay) belirteçlerine ayırır."""
    if position == "center":
        return ("center", "center")
    v, _, h = position.partition("-")
    return (v, h or "center")


def region_box(img_w: int, img_h: int, position: str,
               frac: float = 0.22,
               offset_x_px: int = 0, offset_y_px: int = 0) -> tuple[int, int, int, int]:
    """Logonun düşeceği alanın kutusu — parlaklık örneklemesi için.

    Kenar en az 1 px: `frac * kenar` 1'in altına düşen çok küçük görsellerde
    kutu boşalır ve boş bir crop'ta ImageStat ortalama alırken sıfıra bölerdi.

    `offset_*_px` kutuyu logoyla BİRLİKTE kaydırır. Kaydırmasa `color="auto"`
    kaydırılmış logonun altındaki zemini değil çapadaki zemini örnekler; açık
    zemine taşınmış bir logo koyu zeminin parlaklığına göre beyaz seçilir ve
    okunmaz çıkardı.
    """
    rw, rh = max(1, int(img_w * frac)), max(1, int(img_h * frac))
    v, h = _vh(position)
    x0 = 0 if h == "left" else (img_w - rw if h == "right" else (img_w - rw) // 2)
    y0 = 0 if v == "top" else (img_h - rh if v == "bottom" else (img_h - rh) // 2)
    x0 = _clamp_px(x0 + offset_x_px, img_w - rw)
    y0 = _clamp_px(y0 + offset_y_px, img_h - rh)
    return (x0, y0, x0 + rw, y0 + rh)


def pick_logo(base: Image.Image, position: str, color: str,
              logo_blue: str, logo_white: str,
              offset_x_px: int = 0, offset_y_px: int = 0) -> str:
    """color=auto ise zemin parlaklığına göre mavi/beyaz varyantı seçer."""
    _check_position(position)
    _check_color(color)
    if color == "blue":
        return logo_blue
    if color == "white":
        return logo_white
    box = region_box(*base.size, position,
                     offset_x_px=offset_x_px, offset_y_px=offset_y_px)
    region = base.convert("RGB").crop(box)
    brightness = ImageStat.Stat(region).mean  # [R, G, B]
    luminance = 0.299 * brightness[0] + 0.587 * brightness[1] + 0.114 * brightness[2]
    return logo_blue if luminance > BRIGHTNESS_THRESHOLD else logo_white


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


def composite_logo(base_path: str, *, logo_blue: str, logo_white: str,
                   position: str = "bottom-right", color: str = "auto",
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
    _check_color(color)
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

    logo_path = pick_logo(base, position, color, logo_blue, logo_white,
                          off_x_px, off_y_px)
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
