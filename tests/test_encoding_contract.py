"""Metin dosyası açan her çağrı `encoding` VERMEK ZORUNDA — kalıcı kapı.

NEDEN VAR: bu proje aynı kusurdan iki kez yandı ve ikisi de "yazma tarafı
doğru, okuma tarafı platform varsayılanına düşüyor" desenindeydi:

  • Faz 0 — ÜRÜN kusuru: `storage._read_history` / `assets_store._read_manifest`
    `open()`'a encoding vermiyordu. Yazma yolu utf-8 yazıyor, okuma yolu Türkçe
    Windows'ta cp1254'e düşüyordu → `Zümrüt` → `ZÃ¼mrÃ¼t`, ardından
    `UnicodeDecodeError`. Türkçe promptla üretilmiş bir geçmiş, geçmiş
    listelemeyi ÇÖKERTİYORDU.
  • Faz 5 — TEST kusuru (CI Windows'un 1 kırmızısı): `test_paths.py`
    `write_text("kalmalı")` diyordu. Kullanıcının makinesi cp1254 (ı VAR),
    GitHub runner'ı cp1252 (ı YOK) → `UnicodeEncodeError: 'charmap' codec can't
    encode character '\\u0131'`. Yerelde 1171 yeşil, CI'da kırmızı.

Ders: varsayılan kodlama MAKİNENİN yerel ayarıdır; ölçüm yapılan makinede
"çalışıyor" olması hiçbir şey söylemez. Kapı bu yüzden ürünü DE testleri DE
tarıyor — Faz 0'ın dersi ("yazma ve okuma yolları BİRLİKTE taranır") ancak
böyle kalıcı olur.

NEDEN AST, regex DEĞİL: `open(p, "rb")` ikili kiptir, orada `encoding` vermek
TypeError; regex bunu ayırmak için kip dizesini anlamak zorunda kalırdı. AST
ayrıca `os.open` (dosya tanıtıcısı, metin katmanı yok) gibi ADI aynı ama işi
başka olan çağrıları da ayırıyor.

NEDEN `PYTHONWARNDEFAULTENCODING` (PEP 597) DEĞİL: o bayrak yorumlayıcı
başlangıcında okunuyor, yani `build.ps1` + `build.sh` + `release.yml` olmak
üzere ÜÇ yere yazılmalıydı — biri güncellenip öteki bırakılırsa kapı sessizce
kaybolur, ki bu tam olarak bu projenin tekrar eden kusur sınıfı. Sıradan bir
test olarak her platformda kendiliğinden koşuyor; üstelik statik tarama çalışma
anında HİÇ uğranmayan satırları da görüyor.
"""
import ast
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Taranmayan ağaçlar: bize ait olmayan ya da üretilmiş kod. `.claude` bu
# tanımın en keskin örneği — `.claude/worktrees/` altında BAŞKA commit'lerin
# tam çalışma kopyaları duruyor. Liste
# tests/test_syntax_warnings.py'dekiyle İKİZ kalmak ZORUNDA: orada bu satırın
# eksikliği ölçülmüş bir YANLIŞ KIRMIZI üretti (kapı kendi düzelttiği kusuru
# eski bir commit'in kopyasında yeniden okudu) ve bu sözleşme aynı kör
# noktayı taşıyordu — yalnız henüz ateşlenmemişti, çünkü o kopyalar
# `encoding` sözleşmesine zaten uyuyor. Bir gün sözleşmeden ÖNCEKİ bir
# commit worktree'ye çıktığında ateşlenirdi.
ATLANAN_DIZINLER = {
    ".venv", ".git", ".claude", "__pycache__", "dist", "build",
    "graphify-out", "output", "node_modules", ".pytest_cache",
}

# Adı benzediği için karışan, `encoding` alamayan çağrılar.
# `jsonstore.write_text` bu deponun KENDİ yardımcısı (utf-8'i içinde veriyor,
# bkz. jsonstore.py) — pathlib'in aynı adlı metoduyla karıştırılmamalı.
MUAF = {
    ("os", "open"),            # dosya tanıtıcısı döndürür, metin katmanı yok
    ("Image", "open"),         # PIL: ikili görsel açar, `encoding` parametresi yok
    # `webbrowser.open` bir DOSYA açmıyor, bir URL'i tarayıcıda açıyor —
    # dönüşü bool, metin katmanı hiç yok (desktop.py'nin tarayıcı yedeği).
    ("webbrowser", "open"),
    ("jsonstore", "write_text"),
    ("jsonstore", "read_text"),
}

METIN_METOTLARI = {"read_text", "write_text"}


def _python_dosyalari():
    for kok, dizinler, dosyalar in os.walk(REPO):
        dizinler[:] = [d for d in dizinler if d not in ATLANAN_DIZINLER]
        for ad in dosyalar:
            if ad.endswith(".py"):
                yield os.path.join(kok, ad)


def _ikili_kip(cagri) -> bool:
    """`open(...)`'ın kipi ikili mi? İkiliyse `encoding` vermek TypeError."""
    kip = None
    if len(cagri.args) >= 2:
        kip = cagri.args[1]
    for kw in cagri.keywords:
        if kw.arg == "mode":
            kip = kw.value
    return (isinstance(kip, ast.Constant) and isinstance(kip.value, str)
            and "b" in kip.value)


def ihlaller(kaynak: str, yol: str = "<kaynak>"):
    """Kaynaktaki `encoding`siz metin çağrılarını (satır, ad) olarak verir."""
    for dugum in ast.walk(ast.parse(kaynak, filename=yol)):
        if not isinstance(dugum, ast.Call):
            continue
        f = dugum.func

        if isinstance(f, ast.Name) and f.id == "open":
            ad, metinsel = "open", False
        elif isinstance(f, ast.Attribute) and (
                f.attr == "open" or f.attr in METIN_METOTLARI):
            sahip = f.value.id if isinstance(f.value, ast.Name) else None
            if (sahip, f.attr) in MUAF:
                continue
            ad = f"{sahip or '…'}.{f.attr}"
            metinsel = f.attr in METIN_METOTLARI
        else:
            continue

        # İkili kip yalnız `open`/`.open` için sorulabilir; `*_text` metinseldir.
        if not metinsel and _ikili_kip(dugum):
            continue
        # `**kwargs` yayılıyorsa (arg=None) zorlamıyoruz: çağrı yerinde
        # görülemeyen bir sözlük gelmiş olabilir.
        if any(kw.arg == "encoding" or kw.arg is None for kw in dugum.keywords):
            continue
        yield dugum.lineno, ad


def test_every_text_file_call_declares_its_encoding():
    """Ürün VE testlerde `encoding` verilmeyen metin çağrısı kalmamalı.

    Kapı yazıldığında 21 ihlal buldu (hepsi testlerde; ürün kodu Faz 0'da
    temizlenmişti) — yani yazıldığı anda KIRMIZIYDI.
    """
    bulgular = []
    for yol in _python_dosyalari():
        with open(yol, encoding="utf-8") as fh:
            kaynak = fh.read()
        for satir, ad in ihlaller(kaynak, yol):
            bulgular.append(f"{os.path.relpath(yol, REPO)}:{satir} → {ad}()")

    assert not bulgular, (
        f"{len(bulgular)} çağrı `encoding` vermiyor; varsayılan kodlama "
        "makinenin yerel ayarıdır ve başka bir makinede bozar:\n  "
        + "\n  ".join(sorted(bulgular)))


def test_the_scanner_sees_violations_and_respects_the_exemptions():
    """Kapının kendisi ölçülüyor: sessizce boş dönen bir tarayıcı kapı değildir.

    Yukarıdaki testin yeşil olması iki şey demek olabilir — ihlal yok, YA DA
    tarayıcı kör. Bu test ikincisini eliyor: bilinen ihlaller BULUNMALI, muaf
    biçimler ise bulunmamalı.
    """
    ornek = (
        "import os, jsonstore\n"                     # 1
        "from pathlib import Path\n"                 # 2
        "p = Path('x')\n"                            # 3
        "open('a.txt')\n"                            # 4  ← ihlal
        "p.read_text()\n"                            # 5  ← ihlal
        "p.write_text('m')\n"                        # 6  ← ihlal
        "open('a.bin', 'rb')\n"                      # 7  ikili, muaf
        "open('a.txt', encoding='utf-8')\n"          # 8  bildirilmiş
        "p.read_text(encoding='utf-8')\n"            # 9  bildirilmiş
        "os.open('a', os.O_RDONLY)\n"                # 10 fd, muaf
        "jsonstore.write_text('a', 'm')\n"           # 11 depo yardımcısı, muaf
        "open('a.txt', **kw)\n"                      # 12 yayılım, zorlanmıyor
        "p.write_text('m', encoding='utf-8')\n"      # 13 bildirilmiş
    )
    assert {s for s, _ in ihlaller(ornek)} == {4, 5, 6}, sorted(ihlaller(ornek))
