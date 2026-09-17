"""Paketlenmiş DM Sans sözleşmesi.

Bu dosyanın varlık sebebi: font kusurları SESSİZ. Yanlış yol, eksik altküme ya
da preload'la eşleşmeyen bir URL hiçbir hata üretmez — uygulama açılır, yalnız
harfler başka bir yazı tipiyle çizilir ve kimse fark etmeyebilir. Buradaki her
iddia, o sessiz kusurlardan birini sese çeviriyor.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

import app as appmod

STATIC = Path(appmod.app.state.ayarlar.static_dir)
FONTS = STATIC / "fonts"

# Arayüz Türkçe: bu beş harf latin-ext'te, bu yedisi latin'de (fontTools ile
# cmap taranarak ölçüldü, bkz. fonts.css başlığı).
TR_LATIN_EXT = "ğĞşŞİ"
TR_LATIN = "ıçÇöÖüÜ"


def _fonts_css() -> str:
    return TestClient(appmod.app).get("/static/fonts.css").text


def _faces(css: str) -> list[str]:
    return re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)


def test_font_files_are_real_woff2():
    """Dosyalar depoda ve gerçekten woff2 (LFS işaretçisi ya da HTML hata sayfası değil)."""
    files = sorted(p.name for p in FONTS.glob("*.woff2"))
    assert files == ["dm-sans-v17-latin-ext.woff2", "dm-sans-v17-latin.woff2"], files
    for p in FONTS.glob("*.woff2"):
        assert p.read_bytes()[:4] == b"wOF2", f"{p.name} woff2 imzası taşımıyor"
        assert p.stat().st_size > 5000, f"{p.name} şüpheli derecede küçük"


def test_ofl_license_ships_with_the_font():
    """OFL 1.1 fontun yanında dağıtılmayı ŞART koşuyor; dosya pakete giren yerde."""
    ofl = (FONTS / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in ofl.upper()
    assert "DM Sans" in ofl


def test_font_face_src_paths_resolve():
    """CSS'in gösterdiği her dosya GERÇEKTEN sunuluyor.

    Yol yanlış olsaydı tarayıcı sessizce yedek yazı tipine düşerdi — 404 hiçbir
    yerde görünmez, yalnız harfler değişir.
    """
    css = _fonts_css()
    srcs = re.findall(r'url\("([^"]+)"\)', css)
    assert len(srcs) == 2, srcs
    c = TestClient(appmod.app)
    for url in srcs:
        r = c.get(url)
        assert r.status_code == 200, url
        assert r.content[:4] == b"wOF2", url


def test_preload_url_matches_a_font_face_src_exactly():
    """index.html'in preload'u ile CSS'in src'i BİREBİR aynı olmalı.

    Ayrışırlarsa preload eşleşmez ve dosya İKİ KEZ iner — üstelik hiçbir hata
    vermeden. `?v=__APP_VERSION__` eklemek tam olarak bunu yapıyordu: fonts.css
    statik servis edildiği için oradaki yer tutucu çevrilmiyor.
    """
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    preloads = re.findall(r'<link rel="preload"[^>]*href="([^"]+)"', html)
    assert len(preloads) == 1, f"tek kritik dosya preload edilmeli, bulunan: {preloads}"
    assert "__APP_VERSION__" not in preloads[0]
    assert preloads[0] in re.findall(r'url\("([^"]+)"\)', _fonts_css())


def test_preload_is_crossorigin_and_typed():
    """`crossorigin` yoksa preload eşleşmez (font isteği hep CORS kipinde)."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    tag = re.search(r'<link rel="preload".*?/>', html, re.S).group(0)
    assert "crossorigin" in tag
    assert 'as="font"' in tag and 'type="font/woff2"' in tag


def test_both_subsets_declared_with_swap_and_variable_range():
    """İki altküme, `swap` ve değişken ağırlık aralığı — üçü de sözleşmede."""
    faces = _faces(_fonts_css())
    assert len(faces) == 2, f"latin + latin-ext bekleniyor, bulunan {len(faces)}"
    for face in faces:
        assert "font-display: swap" in face
        # Dosya değişken font (fvar: wght 100–1000). Tek ağırlık yazmak
        # 600'ü sentetik kalınlaştırmaya bırakırdı.
        assert "font-weight: 100 1000" in face
        assert 'font-family: "DM Sans"' in face


def test_turkish_letters_are_inside_a_declared_unicode_range():
    """Türkçe harflerin HEPSİ bir unicode-range'in içinde.

    Altkümeyi daraltmak dosyada VAR OLAN glifi erişilemez yapar: harf yedek
    fonta düşer ve kelime satır ortasında yazı tipi değiştirir.
    """
    covered: list[tuple[int, int]] = []
    for value in re.findall(r"unicode-range:([^;]+);", _fonts_css(), re.S):
        for token in value.split(","):
            token = token.strip()
            if not token.startswith("U+"):
                continue
            lo, _, hi = token[2:].partition("-")
            covered.append((int(lo, 16), int(hi or lo, 16)))

    for ch in TR_LATIN_EXT + TR_LATIN:
        cp = ord(ch)
        assert any(lo <= cp <= hi for lo, hi in covered), f"{ch} (U+{cp:04X}) kapsam dışı"


def test_turkish_letters_are_split_across_the_two_files_as_measured():
    """ğ Ğ ş Ş İ latin-ext'te, ı ç ö ü latin'de — yani latin-ext ŞART.

    Emsal kusur: yalnız `latin` paketlenirse uygulama açılır, hiçbir hata
    çıkmaz, ama "Değiştir" ve "Bağış" yedek yazı tipiyle çizilir.
    """
    css = _fonts_css()
    ext_face = next(f for f in _faces(css) if "latin-ext" in f)
    latin_face = next(f for f in _faces(css) if "latin-ext" not in f)

    def ranges(face: str) -> list[tuple[int, int]]:
        out = []
        aralik = re.search(r"unicode-range:([^;]+);", face, re.S)
        assert aralik is not None, f"unicode-range yok: {face[:80]!r}"
        for token in aralik.group(1).split(","):
            token = token.strip()
            lo, _, hi = token[2:].partition("-")
            out.append((int(lo, 16), int(hi or lo, 16)))
        return out

    def covers(face: str, ch: str) -> bool:
        return any(lo <= ord(ch) <= hi for lo, hi in ranges(face))

    for ch in TR_LATIN_EXT:
        assert covers(ext_face, ch), f"{ch} latin-ext'te olmalı"
        assert not covers(latin_face, ch), f"{ch} latin'de görünüyor — ölçümle çelişiyor"
    for ch in TR_LATIN:
        assert covers(latin_face, ch), f"{ch} latin'de olmalı"


def test_no_google_fonts_link_anywhere_in_static():
    """Ağa bağımlı font YOK — paketlenmiş uygulamada internet garanti değil.

    Referans ekranlardaki Google Fonts <link>'i depoya bilerek girmedi
    (plan §0.2); bu test o kararın nöbetçisi.
    """
    for path in STATIC.rglob("*"):
        if path.suffix.lower() not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in text, path
        assert "fonts.gstatic.com" not in text, path


def test_display_token_and_stylesheet_are_wired():
    """`--font-display` DM Sans diyor ve fonts.css index.html'e bağlı."""
    tokens = TestClient(appmod.app).get("/static/flow-tokens.css").text
    assert '--font-display: "DM Sans"' in tokens
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "/static/fonts.css" in html
