#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yeni sürümü tek kaynağa ve ona bağlı belgelere yazar.

`release.yml`'deki `surum-yaz` işi bunu çağırıyor. Elle yapılırken atlanan tam
olarak bu adımlardı: v0.4.1'de version.py 0.4.1'e çıktı ama README rozeti
v0.3.0'da kaldı (bkz. tests/test_version.py'deki gerekçe) ve GUNCELLEME.md hâlâ
"Sürüm 0.4.0" anlatıyordu.

`version.py`'ye yazmak yeterli DEĞİL: Info.plist, VERSIONINFO ve Gradle
versionName oradan otomatik akıyor, ama README ile GUNCELLEME.md akmıyor —
onları bekçi testleri (`tests/test_version.py`) kolluyor. Yani bu betik
çalışmazsa pytest kırmızıya döner ve yayın hiç oluşmaz. Otomasyonun doğru
olduğunu iddia etmiyoruz; yanlışsa hattın durduğunu biliyoruz.

Fonksiyonlar bilinçle SAF (metin al, metin döndür): `tests/test_surum_yaz.py`
onları dosya sistemine hiç dokunmadan sınıyor.
"""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GUNCELLEME.md'deki sürüm başlığı. Türkçe ek ("0.4.0'da" ama "0.4.2'de",
# "0.4.5'te") sayının OKUNUŞUNA bağlı ve otomatik üretilirse er geç yanlış
# çıkar; başlık bu yüzden eksiz bir biçime çekildi.
BASLIK_ONEKI = "## Sürüm "
BASLIK_SONEKI = " — ne değişti"
_BASLIK = re.compile(
    r"^" + re.escape(BASLIK_ONEKI) + r"(\d+\.\d+\.\d+)" + re.escape(BASLIK_SONEKI) + r"\s*$",
    re.M,
)
# Eski biçim ("## Sürüm 0.4.0'da ne değişti") bir kez karşılanıp yeni biçime
# taşınsın diye ayrıca tanınıyor.
_ESKI_BASLIK = re.compile(r"^## Sürüm (\d+\.\d+\.\d+)['’][dt][ae] ne değişti\s*$", re.M)

_SURUM_LITERALI = re.compile(r"\bv\d+\.\d+\.\d+\b")


def version_py_yaz(metin: str, surum: str) -> str:
    """`APP_VERSION = "0.4.2"` satırını yeni sürümle değiştirir."""
    yeni, sayi = re.subn(
        r'^APP_VERSION\s*=\s*"[^"]*"',
        f'APP_VERSION = "{surum}"',
        metin,
        count=1,
        flags=re.M,
    )
    if sayi != 1:
        raise ValueError("version.py'de APP_VERSION satırı bulunamadı")
    return yeni


def readme_yaz(metin: str, surum: str) -> str:
    """README'deki BÜTÜN `vX.Y.Z` literallerini yeni sürüme çeker.

    Rozet ve başlık ayrı ayrı değil TOPLUCA değiştiriliyor, çünkü
    `test_readme_version_literals_match_the_single_source` README'de farklı bir
    sürüm literali kalmasını da yasaklıyor ("kaçak" iddiası). İki hedefi tek tek
    saymak, üçüncü bir literal eklendiğinde bu betiği sessizce eksik bırakırdı.
    """
    return _SURUM_LITERALI.sub(f"v{surum}", metin)


def guncelleme_yaz(metin: str, surum: str, notlar: list[str]) -> str:
    """GUNCELLEME.md'ye yeni sürüm bölümünü EKLER (eskileri silmez).

    Yeni bölüm, var olan en üstteki sürüm bölümünün HEMEN ÜSTÜNE giriyor; böylece
    dosya ters kronolojik bir kuyruk biriktiriyor ve elle yazılmış eski metinler
    korunuyor. Elle yazılmış metni silmek, otomasyonun yapabileceği en pahalı
    şey olurdu: kullanıcıya dönük tek anlatım orada.
    """
    baslik = f"{BASLIK_ONEKI}{surum}{BASLIK_SONEKI}"
    mevcut = _BASLIK.search(metin)
    if mevcut and mevcut.group(1) == surum:
        # Aynı sürüm iki kez yazılmasın: iş yeniden koşarsa (ya da kendi
        # kendini onarma kuralı aynı sürümü yeniden yayınlarsa) bölüm
        # tekrarlanmamalı.
        return metin

    govde = "\n".join(f"- {n}" for n in notlar) if notlar else \
        "- Küçük düzeltmeler ve iyileştirmeler."
    # Sonundaki `---`: art arda eklenen otomatik bölümler birbirine yapışmasın.
    # Dosyada elle yazılmış bölümler zaten bu ayraçla ayrılıyor; biçim ayrışırsa
    # okuyan kişi iki sürümün notlarını tek bölüm sanabilir.
    bolum = f"{baslik}\n\n{govde}\n\n---\n"

    m = _BASLIK.search(metin) or _ESKI_BASLIK.search(metin)
    if m:
        return metin[:m.start()] + bolum + "\n" + metin[m.start():]
    # Hiç sürüm bölümü yoksa dosyanın sonuna eklenir.
    return metin.rstrip("\n") + "\n\n" + bolum


def en_ustteki_surum(metin: str) -> str | None:
    """GUNCELLEME.md'deki EN ÜSTTEKİ sürüm bölümünün sürümü (bekçi testi için)."""
    m = _BASLIK.search(metin) or _ESKI_BASLIK.search(metin)
    return m.group(1) if m else None


def _oku(yol: str) -> str:
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _yaz(yol: str, metin: str) -> None:
    with open(yol, "w", encoding="utf-8") as f:
        f.write(metin)


# Sürüm literali TAŞIYAN dosyalar → onu tazeleyen işlev. Liste burada, main'in
# içinde değil: bekçisi (tests/test_surum_yaz.py) çalıştırmadan okuyabilsin.
#
# `README.en.md` NEDEN listede: İngilizce sayfa da rozetinde ve "What it does
# (vX.Y.Z)" başlığında aynı literali taşıyor. Listeye girmeseydi Türkçe rozet
# tazelenir, İngilizcesi olduğu yerde kalırdı — ve bunu hiçbir şey kırmızıya
# düşürmezdi: test_version.py'nin "kaçak literal" iddiası YALNIZ README.md'yi
# okuyor. Bu tam olarak v0.4.1'de yaşanan kusurun ikinci dildeki kopyası.
SURUM_DOSYALARI: tuple[tuple[str, Callable[[str, str], str]], ...] = (
    ("version.py", version_py_yaz),
    ("README.md", readme_yaz),
    ("README.en.md", readme_yaz),
)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("kullanım: surum_yaz.py <surum> [not...]", file=sys.stderr)
        return 2
    surum = argv[1]
    if not re.fullmatch(r"\d+\.\d+\.\d+", surum):
        print(f"HATA: MAJOR.MINOR.PATCH bekleniyordu: {surum!r}", file=sys.stderr)
        return 2
    notlar = [n for n in argv[2:] if n.strip()]

    for ad, yazici in SURUM_DOSYALARI:
        yol = os.path.join(KOK, ad)
        _yaz(yol, yazici(_oku(yol), surum))
        print(f"yazıldı: {ad}")

    yol = os.path.join(KOK, "GUNCELLEME.md")
    _yaz(yol, guncelleme_yaz(_oku(yol), surum, notlar))
    print(f"yazıldı: GUNCELLEME.md ({len(notlar)} not)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
