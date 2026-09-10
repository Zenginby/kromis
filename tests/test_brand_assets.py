"""Marka varlıkları (simge ve favicon) sözleşmesi.

Bu testler, v0.4.2'den beri süren ve Windows masaüstünde uygulamanın simgesini
bulanık gösteren kusuru (Pillow'un IcoImagePlugin'inin ana görsel boyutundan
büyük kareleri sessizce atması sonucu kromis.ico'nun yalnız 16x16 kalması)
kalıcı olarak engeller.
"""
import os

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING = os.path.join(REPO, "branding")
STATIC = os.path.join(REPO, "static")


def test_windows_ico_has_all_required_resolutions():
    """Windows .ico simgesi masaüstü, görev çubuğu ve yüksek DPI için tüm standart kareleri taşır.

    16x16: Başlık çubuğu, küçük simgeler
    24x24: %125 DPI görev çubuğu
    32x32: Standart görev çubuğu / Alt-Tab
    48x48: Windows masaüstü orta simge (VARSAYILAN görünüm)
    64x64: %200 DPI görev çubuğu
    128x128: Büyük simgeler
    256x256: Çok büyük simgeler / 4K ölçekleme
    """
    ico_path = os.path.join(BRANDING, "kromis.ico")
    assert os.path.isfile(ico_path), f"kromis.ico bulunamadı: {ico_path}"

    with Image.open(ico_path) as im:
        assert hasattr(im, "ico") and im.ico.entry, "kromis.ico geçerli bir ICO dosyası değil"
        sizes = {(e.width, e.height) for e in im.ico.entry}
        beklenen = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
        assert beklenen.issubset(sizes), f"Eksik çözünürlükler: {beklenen - sizes} (mevcut: {sizes})"

        # Tüm karelerin 32-bit RGBA olması gerekir (opak degrade ve saydam kenarlar için)
        for e in im.ico.entry:
            assert e.bpp == 32, f"{e.width}x{e.height} karesi 32-bit değil: {e.bpp} bpp"


def test_favicon_ico_has_multiple_resolutions():
    """Web faviconu 16x16, 32x32 ve 48x48 karelerini taşır."""
    fav_path = os.path.join(STATIC, "favicon.ico")
    assert os.path.isfile(fav_path), f"favicon.ico bulunamadı: {fav_path}"

    with Image.open(fav_path) as im:
        assert hasattr(im, "ico") and im.ico.entry, "favicon.ico geçerli bir ICO dosyası değil"
        sizes = {(e.width, e.height) for e in im.ico.entry}
        beklenen = {(16, 16), (32, 32), (48, 48)}
        assert beklenen.issubset(sizes), f"Eksik favicon kareleri: {beklenen - sizes}"


def test_apple_touch_icon_resolution():
    """Apple touch icon 180x180 pikseldir."""
    touch_path = os.path.join(STATIC, "apple-touch-icon.png")
    assert os.path.isfile(touch_path), f"apple-touch-icon.png bulunamadı: {touch_path}"

    with Image.open(touch_path) as im:
        assert im.size == (180, 180), f"Beklenen 180x180, bulunan {im.size}"


def test_macos_iconset_has_required_png_files():
    """macOS iconset klasörü iconutil'in .icns üretmesi için gereken tüm PNG'leri içerir."""
    iconset_dir = os.path.join(BRANDING, "kromis.iconset")
    beklenen_dosyalar = {
        "icon_16x16.png": (16, 16),
        "icon_16x16@2x.png": (32, 32),
        "icon_32x32.png": (32, 32),
        "icon_32x32@2x.png": (64, 64),
        "icon_128x128.png": (128, 128),
        "icon_128x128@2x.png": (256, 256),
        "icon_256x256.png": (256, 256),
        "icon_256x256@2x.png": (512, 512),
        "icon_512x512.png": (512, 512),
        "icon_512x512@2x.png": (1024, 1024),
    }
    for ad, boyut in beklenen_dosyalar.items():
        yol = os.path.join(iconset_dir, ad)
        assert os.path.isfile(yol), f"Eksik iconset PNG: {ad}"
        with Image.open(yol) as im:
            assert im.size == boyut, f"{ad} boyutu {boyut} değil, {im.size}"
