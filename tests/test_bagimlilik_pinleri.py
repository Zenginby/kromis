"""Bağımlılıkların sürümü YAZILI mı — paketin yeniden üretilebilirliği.

NEDEN VAR (2026-09-04). Windows paketi v0.5.2'den v0.12.0'a kadar hiç açılmadı
ve sebebi paket koduyla ilgili değildi: `pywebview` Windows'ta `pythonnet` +
`clr-loader` çekiyor, `pyinstaller` da `pyinstaller-hooks-contrib` çekiyor ve
ÜÇÜ DE PİNSİZDİ. Yani aynı commit, derlendiği GÜNE göre farklı bir .NET köprüsü
paketliyordu; kullanıcının hata.log'undan sürümleri geri çıkarmak ancak satır
numaralarını PyPI'deki kaynakla karşılaştırarak mümkün oldu.

İDDİA "şu paketler pinli" DEĞİL, KURALIN KENDİSİ: her satır bir sürüm kısıtı
taşımak zorunda. Gerekçe `errlog.py`nin dersinin aynısı — adı birebir sayan bir
liste, listeye girmeyen bir sonraki bağımlılığı sessizce kapsam dışı bırakır.
Orada `OPENAI_API_KEY|FAL_KEY|...` alternasyonu `GEMINI_API_KEY`i kaçırmıştı.
"""
from __future__ import annotations

import os
import re

import pytest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(KOK, "requirements.txt")
DEV = os.path.join(KOK, "requirements-dev.txt")
WINDOWS_WORKFLOW = os.path.join(KOK, ".github", "workflows", "_paket-windows.yml")

# `ad==sürüm`, `ad>=sürüm`, `ad[extra]==sürüm; işaretçi` — hepsi geçerli.
_SATIR = re.compile(r"^\s*(?P<ad>[A-Za-z0-9._-]+)\s*(?P<extra>\[[^\]]*\])?"
                    r"\s*(?P<kisit>[<>=!~].*)$")


def _pinler(yol: str) -> dict[str, str]:
    """{paket adı → kısıt} — yorumlar ve boş satırlar atılmış."""
    bulunan: dict[str, str] = {}
    with open(yol, encoding="utf-8") as f:
        for ham in f:
            satir = ham.strip()
            if not satir or satir.startswith("#"):
                continue
            eslesme = _SATIR.match(satir)
            assert eslesme, f"{os.path.basename(yol)}: sürüm kısıtı olmayan satır: {satir!r}"
            bulunan[eslesme.group("ad").lower()] = eslesme.group("kisit").strip()
    return bulunan


@pytest.fixture(scope="module")
def runtime_pinleri() -> dict[str, str]:
    return _pinler(RUNTIME)


@pytest.fixture(scope="module")
def dev_pinleri() -> dict[str, str]:
    return _pinler(DEV)


def test_every_runtime_dependency_carries_a_version_constraint(runtime_pinleri):
    """Asıl kusur sınıfı ÇIPLAK AD: `_pinler` onu ayrıştırırken patlatıyor."""
    assert runtime_pinleri


def test_every_build_dependency_carries_a_version_constraint(dev_pinleri):
    assert dev_pinleri


def test_the_scanner_is_not_blind(runtime_pinleri, dev_pinleri):
    """Kör-tarama kapısı: ayrıştırma bir gün boş dönerse yukarıdaki iki test
    sessizce anlamsızlaşır ve "her satır pinli" hep doğru görünür."""
    assert len(runtime_pinleri) >= 7, runtime_pinleri
    assert len(dev_pinleri) >= 3, dev_pinleri


def test_the_windows_dotnet_bridge_is_pinned(runtime_pinleri):
    """pywebview'ın DOLAYLI bağımlılıkları açıkça yazılı olmak zorunda —
    paketin içeriğini onlar belirliyor, `pywebview==6.2.*` değil."""
    for ad in ("pythonnet", "clr-loader"):
        assert ad in runtime_pinleri, f"{ad} pinlenmemiş"


def test_the_dotnet_bridge_is_scoped_to_windows(runtime_pinleri):
    """İŞARETÇİ ŞART: bu dosya Linux (_test.yml) ve macOS'ta da kuruluyor.

    İşaretçi olmadan pip .NET köprüsünü oralara da kurar ve macOS paketine
    girer — sessiz bir boyut ve yüzey artışı.
    """
    for ad in ("pythonnet", "clr-loader"):
        assert 'sys_platform == "win32"' in runtime_pinleri[ad], (
            f"{ad} her platforma kuruluyor")


def test_the_pyinstaller_hooks_are_pinned_exactly(dev_pinleri):
    """`Python.Runtime.dll`i ve WebView2 DLL'lerini pakete KOYAN şey bu paket.

    TAM SÜRÜM isteniyor, `==2026.*` değil: takvim sürümlemesi (YYYY.N)
    kullandığı için `2026.*` bir yıllık pencere demek — pin değil, pin
    görüntüsü. Deponun `MAJOR.MINOR.*` geleneği burada anlamını kaybediyor.
    """
    kisit = dev_pinleri.get("pyinstaller-hooks-contrib")
    assert kisit, "pyinstaller-hooks-contrib pinlenmemiş"
    assert re.fullmatch(r"==\d{4}\.\d+", kisit), kisit


def test_the_dotnet_pin_matches_the_python_version_the_package_is_built_with():
    """YARIM GERİ ÇEKİLME MANDALI.

    pythonnet 3.0.5 `Requires-Python: <3.14`, 3.1.0 ise 3.14'ü destekliyor —
    yani iki literal BİRBİRİNE BAĞLI. Bir gün 3.1.x'ten dönülürse (B planı)
    Windows işinin Python'u da 3.13'e inmek zorunda; yalnız birini değiştirmek
    `pip install`i çözümleme aşamasında patlatır ve kırılma "paket derlenmiyor"
    biçiminde, sebebinden uzakta görünür.
    """
    with open(WINDOWS_WORKFLOW, encoding="utf-8") as f:
        metin = f.read()
    surum = re.search(r"python-version:\s*'([\d.]+)'", metin)
    assert surum, "Windows işinde python-version bulunamadı"

    pythonnet = _pinler(RUNTIME)["pythonnet"]
    if surum.group(1) == "3.13":
        assert "3.0." in pythonnet, (
            "Python 3.13'te pythonnet 3.0.* bekleniyordu (B planı yarım kalmış)")
    else:
        assert "3.1." in pythonnet, (
            f"Python {surum.group(1)} pythonnet 3.0.5'i çözemez "
            "(Requires-Python: <3.14)")
