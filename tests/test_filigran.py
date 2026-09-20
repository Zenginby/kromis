"""Filigran — `services/filigran.py` (Faz 3 / 4; docs/faz3-kredi-defteri-filigran.md §4, K7).

Bu dosya `@pytest.mark.gercek_filigran`: conftest'in autouse `_filigran_yamasi`
(`uygula` → kimlik) burada KURULMAZ, gerçek işaret gerçek görsele biner.

GOLDEN PİKSEL düzeyinde, bayt düzeyinde DEĞİL — tests/test_composite.py'nin
2026-07-29'da arm64'te ölçtüğü karar: PNG sıkıştırması platformlar arası bayt
bayt yeniden üretilebilir değil (Pillow tekerlekleri farklı deflate'lerle
derleniyor); pikseller farklı çıkarsa ise durdurucu hata. Belge §4 "bayt
eşitliği" der; test_composite'in ölçümü o cümleyi piksele indiriyor.
İşaret dosyası, `KONUM`/`OLCEK`/`OPAKLIK` ya da composite'in gölge sabitleri
değişince golden `tools/make_filigran.py` ile yeniden üretilir ve PR'a yazılır.

Sorular: (i) golden + alt-sağ + boyut korunur; (ii) JPEG girdi → PNG çıktı,
şeffaflık korunur; (iii) 50 MP sınırı ve bozuk girdi → `GorselIslenemedi`
(sessiz filigransız DEĞİL); (iv) işaret dosyası yok/bozuk → `FiligranDosyasiYok`,
`KROMIS_FILIGRAN_DOSYASI` yolu ve önceliği; (v) video girdi dokunulmaz;
(vi) opaklık gerçekten 0,6 (tam opak bindirmeden farklı).
"""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

import composite
from services import filigran, gorsel

pytestmark = pytest.mark.gercek_filigran

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "filigran")
BASE = os.path.join(FIXTURES, "base-256.png")
GOLDEN = os.path.join(FIXTURES, "golden-256.png")
ISARET = os.path.join(REPO, "bundled", "filigran.png")


def _oku(yol: str) -> bytes:
    with open(yol, "rb") as f:
        return f.read()


def _pikseller(veri: bytes) -> tuple[tuple[int, int], bytes]:
    im = Image.open(io.BytesIO(veri)).convert("RGBA")
    return im.size, im.tobytes()


def _png(boyut: tuple[int, int] = (64, 48), renk: tuple[int, ...] = (200, 40, 40), mod: str = "RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mod, boyut, renk).save(out, format="PNG")
    return out.getvalue()


# ── (i) golden ───────────────────────────────────────────────────────────

def test_the_golden_matches_pixel_for_pixel_and_the_size_is_preserved():
    uretilen = filigran.uygula(_oku(BASE))
    assert uretilen[:8] == b"\x89PNG\r\n\x1a\n"
    a_boyut, a = _pikseller(uretilen)
    b_boyut, b = _pikseller(_oku(GOLDEN))
    assert a_boyut == b_boyut == (256, 256), "boyut değişti"
    assert a == b, "PİKSELLER değişti — işaret, sabitler ya da composite kaydı; golden'ı yeniden üret ve PR'a yaz"


def test_the_mark_lands_in_the_bottom_right_corner_and_nowhere_else():
    """Belge §4: alt-sağ, %6 genişlik. Değişen pikseller yalnız alt-sağ çeyrekte; sol üst el değmemiş."""
    taban = Image.open(BASE).convert("RGBA")
    sonuc = Image.open(io.BytesIO(filigran.uygula(_oku(BASE)))).convert("RGBA")
    degisen = [(x, y) for y in range(256) for x in range(256)
               if taban.getpixel((x, y)) != sonuc.getpixel((x, y))]
    assert degisen, "hiçbir piksel değişmedi — filigran binmedi"
    assert min(x for x, _ in degisen) >= 192 and min(y for _, y in degisen) >= 192, "işaret alt-sağ çeyrekte değil"
    # İşaret genişliği %6 → 15 px + kenar boşluğu %3 → 7 px: sağ kenardan ~22 px içeride başlar; gölge + bulanıklık ekler.
    assert max(x for x, _ in degisen) == 255 or max(x for x, _ in degisen) >= 240


def test_the_asset_is_brand_neutral_transparent_and_at_least_512_wide():
    """Belge §4 "Sahibin adımı": şeffaf arka plan, ≥ 512 px; işaret metin değil (test dosya adını ve alfayı ölçer)."""
    im = Image.open(ISARET).convert("RGBA")
    assert im.width >= 512
    alfa = im.getchannel("A").getextrema()
    assert alfa[0] == 0 and alfa[1] == 255, "şeffaf arka plan + opak işaret bekleniyor"
    assert os.path.getsize(ISARET) < 64 * 1024, "işaret küçük kalmalı (paletli PNG ~13 KB)"


# ── (ii) girdi biçimi ────────────────────────────────────────────────────

def test_a_jpeg_input_comes_back_as_a_png_of_the_same_size():
    out = io.BytesIO()
    Image.open(BASE).save(out, format="JPEG", quality=90)
    sonuc = filigran.uygula(out.getvalue())
    assert sonuc[:8] == b"\x89PNG\r\n\x1a\n"
    assert Image.open(io.BytesIO(sonuc)).size == (256, 256)


def test_a_transparent_input_keeps_its_transparency():
    """`keep_alpha`: sağlayıcının şeffaf PNG'si filigranla siyah zemin kazanmasın (composite'in RGB öntanımı burada geçersiz)."""
    sonuc = Image.open(io.BytesIO(filigran.uygula(_png((120, 120), (0, 0, 0, 0), "RGBA")))).convert("RGBA")
    assert sonuc.getpixel((5, 5)) == (0, 0, 0, 0), "sol üst şeffaf kalmalı"
    assert sonuc.getchannel("A").getextrema()[1] > 0, "işaret görünür olmalı"


def test_a_larger_image_gets_a_proportionally_larger_mark():
    """%6 ORAN, sabit piksel değil: 1024 genişlikte işaret ~61 px, 256'da ~15 px."""
    sonuc = Image.open(io.BytesIO(filigran.uygula(_png((1024, 512), (30, 30, 30))))).convert("RGB")
    degisen_x = sorted({x for y in range(400, 512) for x in range(800, 1024) if sonuc.getpixel((x, y)) != (30, 30, 30)})
    assert 55 <= degisen_x[-1] - degisen_x[0] <= 90, degisen_x[-1] - degisen_x[0]


# ── (iii) girdi reddi ────────────────────────────────────────────────────

def test_an_image_over_the_pixel_limit_is_refused_not_passed_through(monkeypatch):
    # test_edit_route'un deyimi: küçük tavan. 24 px'ten dar bir görselde işaret 0 px'e
    # iner (%6) ve composite patlar — sağlayıcı öyle bir görsel vermez, tavan 1.000 seçildi.
    monkeypatch.setattr(gorsel, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(filigran.GorselIslenemedi):
        filigran.uygula(_png((40, 40)))
    assert filigran.uygula(_png((24, 24))), "tavanın altı geçer"


def test_bytes_that_are_not_an_image_raise_not_return_untouched():
    with pytest.raises(filigran.GorselIslenemedi):
        filigran.uygula(b"\x89PNG\r\n\x1a\n" + bytes(range(16)))


# ── (iv) işaret dosyası ─────────────────────────────────────────────────

def test_a_missing_asset_is_an_explicit_error_never_a_silent_skip(tmp_path, monkeypatch):
    yok = str(tmp_path / "yok.png")
    monkeypatch.setenv(filigran.DOSYA_ENV, yok)
    with pytest.raises(filigran.FiligranDosyasiYok) as hata:
        filigran.uygula(_png())
    assert yok in str(hata.value)


def test_a_corrupt_asset_is_the_same_explicit_error(tmp_path):
    bozuk = tmp_path / "bozuk.png"
    bozuk.write_bytes(b"bu bir png degil")
    with pytest.raises(filigran.FiligranDosyasiYok):
        filigran.uygula(_png(), dosya=str(bozuk))


def test_the_env_var_overrides_the_bundled_asset_and_the_argument_overrides_both(tmp_path, monkeypatch):
    kirmizi = tmp_path / "kirmizi.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(kirmizi, "PNG")
    monkeypatch.setenv(filigran.DOSYA_ENV, str(kirmizi))
    assert filigran.dosya_yolu() == str(kirmizi)
    assert filigran.dosya_yolu("/x.png") == "/x.png"
    monkeypatch.delenv(filigran.DOSYA_ENV)
    assert filigran.dosya_yolu() == filigran.varsayilan_dosya()
    assert os.path.isfile(filigran.varsayilan_dosya())
    # Ortamın işareti gerçekten binen: kırmızı kare alt-sağda, paketin beyaz halkası değil.
    monkeypatch.setenv(filigran.DOSYA_ENV, str(kirmizi))
    sonuc = Image.open(io.BytesIO(filigran.uygula(_png((200, 200), (0, 0, 0))))).convert("RGB")
    r, g, b = sonuc.getpixel((200 - 6 - 6, 200 - 6 - 6))
    assert r > 100 and g < 40 and b < 40, (r, g, b)


# ── (v) video ────────────────────────────────────────────────────────────

def test_a_video_input_is_returned_untouched_without_opening_the_asset(monkeypatch):
    mp4 = b"\x00\x00\x00\x20ftypmp42" + bytes(8)
    monkeypatch.setenv(filigran.DOSYA_ENV, "/yok/yok.png")  # dosyaya bakılmadığı da ölçülür
    assert filigran.uygula(mp4, kind="video") is mp4


# ── (vi) opaklık ─────────────────────────────────────────────────────────

def test_the_mark_is_applied_at_sixty_percent_not_fully_opaque():
    """Aynı işaret opaklık 1,0 ile bindirilse (composite doğrudan) pikseller farklı; 0,6 daha soluk."""
    taban = _png((256, 256), (0, 0, 0))
    bizim = Image.open(io.BytesIO(filigran.uygula(taban))).convert("RGB")
    tam = Image.open(io.BytesIO(composite.composite_logo(
        io.BytesIO(taban), logo_path=ISARET, position=filigran.KONUM, scale=filigran.OLCEK))).convert("RGB")
    en_parlak_bizim = max(sum(bizim.getpixel((x, y))) for x in range(220, 256) for y in range(220, 256))
    en_parlak_tam = max(sum(tam.getpixel((x, y))) for x in range(220, 256) for y in range(220, 256))
    assert en_parlak_tam == 765, "tam opak beyaz işaret tam beyaz piksel bırakır"
    assert 300 < en_parlak_bizim < 560, en_parlak_bizim  # 0,6 × 255 ≈ 153 kanal başına → ~459
