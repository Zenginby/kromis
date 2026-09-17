"""Telif başlığı, dağıtılan HER ilk-el kaynak dosyanın başında mı.

NEDEN VAR: LICENSE ve NOTICE tek dosya; bir kopyayı kendi ürünü gibi
yayımlayacak kişi ikisini de tek hamlede siler ve geriye kimin yazdığına dair
hiçbir iz kalmaz. Dosya başlığı bunu "tek hamle" olmaktan çıkarıyor — 50'den
fazla dosyayı tek tek temizlemek, kazara değil BİLEREK yapılan bir iştir ve
ihlal iddiasında kasıt tam olarak böyle gösterilir (TELIF.md).

Bunun bir yan kazancı da var: başlıktaki adres `guncelleme.DEPO` ile aynı
sahibi gösterdiği için (tests/test_depo_adresi.py) bir çatal, kendi deposuna
geçmeden takımı yeşile döndüremiyor — yani AGPL §5a'nın istediği "kaynağını
söyle" adımı çatalda kendiliğinden hatırlatılıyor.

KAPSAM = DAĞITILAN ilk-el kaynak:
  * kökteki, `routers/`, `services/` ve `tools/` altındaki `.py`  (tests/
    HARİÇ — pakete girmiyor); kapsam `git ls-files '*.py'`ten TÜRETİLİYOR,
    yani yeni bir paket kendiliğinden girer,
  * `static/` altındaki `.js`, `.css` ve `.html` (index.html, giris.html).

KAPSAM DIŞI ve bilinçli:
  * `static/pixel-canvas.js` — ÜÇÜNCÜ PARTİ (Ryan Mulligan, MIT). Başkasının
    eserine kendi telifini yazmak, bu testin engellemeye çalıştığı davranışın
    ta kendisi olurdu. Aşağıda ayrıca SINANIYOR.
  * `static/fonts/` — DM Sans, OFL 1.1; bildirimi OFL.txt'te yanında duruyor.
  * `tests/` — pakete girmiyor; yalnız gürültü eklerdi.
"""
from __future__ import annotations

import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Başlığın SÖZLEŞMESİ. Üç satırın üçü de anlamlı:
#   1) kim — telif sahibi,
#   2) hangi şartlarla + kaynağın nerede olduğu (AGPL §13),
#   3) kaldırılamayacağı (§5a) ve ad/logo ayrımı (MARKA.md).
# Yorum işareti dile göre değişiyor, METİN değişmiyor: iddia da metni arıyor.
BASLIK = (
    "Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)",
    "GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis",
    "Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).",
)

# Başlık dosyanın BAŞINDA olmak zorunda: ortasında bir yerde geçen bir telif
# satırı, dosyayı açan kişiye hiçbir şey söylemez. Pay shebang, doctype ve
# başlığın kendisi için.
ILK_SATIRLAR = 12

UCUNCU_PARTI = "static/pixel-canvas.js"


def _izlenen(*kaliplar: str) -> list[str]:
    cikti = subprocess.run(["git", "-C", REPO, "ls-files", *kaliplar],
                           check=True, capture_output=True, text=True).stdout
    return [y for y in cikti.splitlines() if y]


def _kapsam() -> list[str]:
    yollar = [y for y in _izlenen("*.py") if not y.startswith("tests/")]
    # `static/*.html`: index.html ve giris.html (Faz 1 / 3) — yeni bir sayfa
    # kendiliğinden girer, `.py` kalıbıyla aynı duruş.
    yollar += _izlenen("static/*.js", "static/*.css", "static/*.html")
    return sorted(set(yollar) - {UCUNCU_PARTI})


def _bas(yol: str) -> str:
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        return "".join(f.readlines()[:ILK_SATIRLAR])


@pytest.mark.parametrize("yol", _kapsam())
def test_every_shipped_source_file_carries_the_copyright_header(yol: str):
    bas = _bas(yol)
    eksik = [s for s in BASLIK if s not in bas]
    assert not eksik, (
        f"{yol}: telif başlığının satır(lar)ı ilk {ILK_SATIRLAR} satırda yok:\n  "
        + "\n  ".join(eksik)
        + "\nDosyanın başına (shebang/doctype varsa onun ALTINA) ekle."
    )


def test_the_scan_actually_covers_the_files_that_matter():
    """Bekçinin bekçisi: `git ls-files` kalıbı bir gün hiçbir şey döndürmez
    hâle gelirse yukarıdaki parametreli iddia SIFIR kez koşar ve takım
    "yeşil" görünür. tests/test_depo_adresi.py'deki aynı duruş."""
    kapsam = set(_kapsam())
    assert len(kapsam) > 40, f"kapsam şüpheli biçimde küçük: {len(kapsam)}"
    for beklenen in ("app.py", "version.py", "android_main.py", "desktop.py",
                     "tools/graf_uret.py", "static/core.js", "static/style.css",
                     "static/index.html"):
        assert beklenen in kapsam, f"{beklenen} taranmıyor — kalıp bayatladı mı?"


def test_the_third_party_file_is_left_with_its_own_attribution():
    """`static/pixel-canvas.js` başkasının eseri (MIT). Başlık betiği bir gün
    "bütün js dosyaları" diye genişletilirse, bu dosyaya bizim telifimizi
    yazmış oluruz — yani tam olarak bu testin önlemeye çalıştığı şeyi biz
    yaparız. NOTICE de aynı bildirimi taşıyor."""
    bas = _bas(UCUNCU_PARTI)
    assert BASLIK[0] not in bas, (
        f"{UCUNCU_PARTI} üçüncü parti bir eser; üzerine bu projenin telifi "
        "yazılamaz"
    )
    assert "Ryan Mulligan" in bas and "MIT" in bas, \
        f"{UCUNCU_PARTI} kendi atfını kaybetmiş"

    with open(os.path.join(REPO, "NOTICE"), encoding="utf-8") as f:
        assert UCUNCU_PARTI in f.read(), \
            "NOTICE üçüncü parti bileşeni saymıyor"
