"""Asgari Python sürümü DÖRT yerde yazılı — dördü aynı sayıyı söylemek zorunda.

NEDEN VAR (2026-09-08): README'nin "Gereksinimler" başlığı **"Python 3.10+"**
diyordu, CI ise her işte 3.13/3.14 pinliyordu. Aradaki fark teorik değildi:
`azure_client._atomic_write` kimlik dosyasını yazmadan ÖNCE izinleri
sıkılaştırmak için `os.fchmod(fd, 0o600)` çağırıyor ve `os.fchmod` CPython'un
Windows yapısına ancak 3.13'te eklendi. Windows'ta 3.12.10 ile ölçüldü: kimlik
YAZAN 45 test `AttributeError: module 'os' has no attribute 'fchmod'` ile
düşüyor (test_credstore 12, test_settings 9, test_settings_route 24).

Kusurun ASIL zararı belgede: geliştirici "3.10+" yazısına UYDUĞU için 3.12
kuruyor ve kırmızıyı kendi değişikliğinden sanıyor. Bu yüzden iddia "bir yerde
sürüm yazılı" DEĞİL, hepsinin AYNI sayıyı söylediği: sayı `conftest.ASGARI_PYTHON`
içinde bir kez tanımlı, README + requirements-dev.txt + CI pinleri ona göre
sınanıyor. Depo geleneği (CLAUDE.md §5): türetilen her şeyin bekçisi bir test.

NEDEN CI PİNLERİ DE SINANIYOR: kapı yalnızca `os.fchmod`'un YOKLUĞUNA bakıyor,
yani takım Linux'ta 3.10'da da açılır. Bir gün `_test.yml` 3.12'ye düşürülse
CI yeşil kalırdı — ve depo, Windows'ta koşmayan bir sürümü "sınanmış" sayardı.
Bu testin yakaladığı kırılma o.
"""
from __future__ import annotations

import os
import re

import pytest

from tests import conftest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(KOK, "README.md")
DEV = os.path.join(KOK, "requirements-dev.txt")
WORKFLOWS = os.path.join(KOK, ".github", "workflows")

# README'nin "Gereksinimler" bölümü: "### 1. ..."den bir sonraki "### "e kadar.
_GEREKSINIMLER = re.compile(r"^### 1\. Gereksinimler$(.*?)^### ",
                            re.MULTILINE | re.DOTALL)
_README_SURUM = re.compile(r"Python (\d+)\.(\d+)\+")
_DEV_SURUM = re.compile(r"ASGAR\w+ PYTHON:\s*(\d+)\.(\d+)")

# README'nin tepesindeki rozet: `badge/python-3.13%2B-blue`. AYRI SINANIYOR
# çünkü ayrı bayatlıyor — "3.10+" ikisinde de yazılıydı ve rozet, gereksinim
# listesinden ÖNCE görülen yer, yani yanlışsa daha çok kişiyi yanıltıyor.
_BADGE = re.compile(r"badge/python-(\d+)\.(\d+)%2B")


def _surumler(desen: re.Pattern[str], metin: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in desen.findall(metin)]

# `python-version: '3.14'` (setup-python) ve `-PkromisBuildPython=python3.13`
# (Android'in gradle çağrısı) — ikisi de bir yorumlayıcı SEÇİYOR.
_PIN = re.compile(r"""python-version:\s*['"]?(\d+)\.(\d+)"""
                  r"""|PkromisBuildPython=python(\d+)\.(\d+)""")


def _oku(yol: str) -> str:
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _gereksinim_maddeleri() -> str:
    """Gereksinimler bölümünün yalnızca MADDELERİ ("- " ile başlayan satırlar).

    NEDEN düz metnin tamamı DEĞİL: aynı bölümdeki gerekçe, eski ve YANLIŞ
    değeri ("Python 3.10+") tarihçe olarak BİLEREK anıyor — belgenin en
    öğretici cümlesi o. Bölümün tamamı taransa test, kendi gerekçesini kusur
    sayıp belgeyi kısaltmaya zorlardı. İddia "yürürlükteki gereksinim ne
    diyor", o da madde listesinde yazılı.
    """
    eslesme = _GEREKSINIMLER.search(_oku(README))
    assert eslesme, "README'de '### 1. Gereksinimler' bölümü bulunamadı"
    return "\n".join(satir for satir in eslesme.group(1).splitlines()
                     if satir.startswith("- "))


def _workflow_pinleri() -> dict[str, list[tuple[int, int]]]:
    """{workflow dosyası → seçtiği (major, minor) sürümleri}."""
    bulunan: dict[str, list[tuple[int, int]]] = {}
    for ad in sorted(os.listdir(WORKFLOWS)):
        if not ad.endswith((".yml", ".yaml")):
            continue
        surumler = []
        for eslesme in _PIN.finditer(_oku(os.path.join(WORKFLOWS, ad))):
            major, minor = (eslesme.group(1), eslesme.group(2))
            if major is None:
                major, minor = (eslesme.group(3), eslesme.group(4))
            surumler.append((int(major), int(minor)))
        if surumler:
            bulunan[ad] = surumler
    return bulunan


def test_the_readme_states_exactly_the_minimum_the_repo_enforces():
    """Asıl kusur burasıydı: "3.10+" yazan bir belge, 45 kırmızının sebebi."""
    bulunan = _surumler(_README_SURUM, _gereksinim_maddeleri())
    assert bulunan, ("README'nin Gereksinimler maddeleri bir Python tabanı "
                     "söylemiyor ('Python X.Y+' biçimi bekleniyor)")
    assert conftest.ASGARI_PYTHON in bulunan, (
        f"README {bulunan} diyor, kapı {conftest.ASGARI_PYTHON} istiyor")
    for surum in bulunan:
        assert surum >= conftest.ASGARI_PYTHON, (
            f"README {surum} tabanını duyuruyor ama takım Windows'ta "
            f"{conftest.ASGARI_PYTHON} altında koşmuyor")


def test_the_readme_badge_shows_the_same_minimum():
    """Rozet gereksinim listesinden ÖNCE okunuyor; ayrı bayatlarsa ayrı yanıltır."""
    bulunan = _surumler(_BADGE, _oku(README))
    assert bulunan == [conftest.ASGARI_PYTHON], (
        f"README rozeti {bulunan} gösteriyor, "
        f"kapı {conftest.ASGARI_PYTHON} istiyor")


def test_the_dev_requirements_record_the_same_minimum():
    """pip bunu ZORLAYAMAZ (bkz. dosyanın girişi), ama yazılı olmak zorunda."""
    bulunan = [(int(a), int(b)) for a, b in _DEV_SURUM.findall(_oku(DEV))]
    assert bulunan == [conftest.ASGARI_PYTHON], (
        f"requirements-dev.txt {bulunan} kaydediyor, "
        f"kapı {conftest.ASGARI_PYTHON} istiyor")


def test_no_workflow_pins_an_interpreter_below_the_minimum():
    """CI 3.12'ye düşerse yeşil kalır ama Windows'ta koşmaz — kapı bu."""
    pinler = _workflow_pinleri()
    assert pinler, "workflow'larda hiç Python pini bulunamadı (regex bayatladı mı?)"
    for ad, surumler in pinler.items():
        for surum in surumler:
            assert surum >= conftest.ASGARI_PYTHON, (
                f"{ad} Python {surum[0]}.{surum[1]} pinliyor; asgari "
                f"{conftest.ASGARI_PYTHON[0]}.{conftest.ASGARI_PYTHON[1]}")


def test_the_gate_stops_the_suite_when_fchmod_is_missing(monkeypatch):
    """`os.fchmod`u SİLEREK sınanıyor: iddia platforma değil YETENEĞE bağlı.

    Böylece kapının kendisi Linux CI'da da gerçekten koşuyor — yoksa yalnızca
    eski bir Windows'ta anlam taşır ve orada kimse koşmaz.
    """
    monkeypatch.delattr(os, "fchmod", raising=False)
    monkeypatch.delenv(conftest.ESKI_PYTHON_IZNI, raising=False)

    with pytest.raises(pytest.UsageError) as hata:
        conftest.pytest_configure(None)

    mesaj = str(hata.value)
    assert "3.13+" in mesaj, "mesaj istenen sürümü söylemiyor"
    assert "fchmod" in mesaj, "mesaj sebebi söylemiyor"
    assert "py -3.13 -m venv" in mesaj, "mesaj ÇÖZÜMÜ söylemiyor"
    assert conftest.ESKI_PYTHON_IZNI in mesaj, "mesaj kaçış yolunu söylemiyor"


def test_the_gate_message_survives_a_cp1252_console(monkeypatch):
    """Mesajın GÖVDESİ saf ASCII olmak zorunda — ölçülmüş bir karar.

    cp1252 konsola boru ile yazıldığında pytest `backslashreplace` uyguluyor:
    Türkçe harfler `\\u0131` kaçışlarına düşüyor. Çökme YOK (Faz 5'teki
    UnicodeEncodeError bu yolda çıkmıyor) ama metin okunmuyor — ve bu mesajın
    TEK işi ne yapılacağını söylemek. Gövdesi bu yüzden bilinçle ASCII;
    gerekçenin Türkçesi `pytest_configure`'ın docstring'inde duruyor.
    """
    monkeypatch.delattr(os, "fchmod", raising=False)
    monkeypatch.delenv(conftest.ESKI_PYTHON_IZNI, raising=False)

    with pytest.raises(pytest.UsageError) as hata:
        conftest.pytest_configure(None)

    str(hata.value).encode("ascii")  # UnicodeEncodeError → cp1252'de bozulur


def test_the_gate_can_be_bypassed_on_purpose(monkeypatch):
    """Kapı bir DUVAR değil: 3.12'de kalan geliştirici öteki 2142 testi koşabilir.

    Bu olmadan değişiklik bir yeteneği geri alırdı — ölçüldü: aynı yorumlayıcıda
    bayrakla 12 kırmızı / 10 yeşil, yani kapı öncesi davranışın birebir aynısı.
    """
    monkeypatch.delattr(os, "fchmod", raising=False)
    monkeypatch.setenv(conftest.ESKI_PYTHON_IZNI, "1")
    assert conftest.pytest_configure(None) is None


def test_the_gate_is_silent_where_fchmod_exists(monkeypatch):
    """POSIX'te 3.13 altı da `fchmod` taşıyor: orada durmanın sebebi yok."""
    monkeypatch.setattr(os, "fchmod", lambda fd, mode: None, raising=False)
    monkeypatch.delenv(conftest.ESKI_PYTHON_IZNI, raising=False)
    assert conftest.pytest_configure(None) is None
