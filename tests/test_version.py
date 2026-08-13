"""Sürüm TEK kaynaktan mı akıyor: version.py → spec / index.html / /api/settings.

index.html ve /api/settings tarafı tests/test_index.py ile
tests/test_settings_route.py'de. Burada spec ve modülün KENDİ sözleşmesi var:
spec'i hiçbir pytest çalıştıramaz (içinde Analysis/BUNDLE çağrıları var), o
yüzden METİN üzerinden doğrulanıyor. Plist'in gerçekten doğru üretildiği ancak
CI'daki `plutil` adımıyla kanıtlanır.
"""
import os
import re
import warnings

import version

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(REPO, "gpt-image-studio.spec")


def _spec_text() -> str:
    with open(SPEC, encoding="utf-8") as f:
        return f.read()


def test_version_is_a_three_part_number():
    """Info.plist'in CFBundleVersion'ı noktalı-sayısal bir dizi bekler."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.APP_VERSION), version.APP_VERSION


def test_spec_derives_the_version_and_hardcodes_nothing():
    """Plist'e elle sürüm yazılırsa tek kaynak bozulur ve sessizce ayrışır."""
    text = _spec_text()
    assert not re.search(r"CFBundle\w*Version\w*'\s*:\s*['\"]\d", text), \
        "Info.plist'e elle sürüm literali yazılmış — tek kaynak bozuldu"
    assert "version.py" in text, "spec sürümü version.py'den okumalı"


def test_spec_anchors_the_version_load_on_specpath():
    """Düz `import version` spec'te ImportError verir — SPECPATH çapası ŞART.

    PyInstaller spec'i `exec(code, {...})` ile çalıştırıyor: namespace'te
    `__file__` yok ve spec'in dizini sys.path'e eklenmiyor (`pathex` yalnızca
    Analysis içinde, o da bu satırdan sonra). `pyinstaller` kurulu bir konsol
    betiği olduğu için sys.path[0] .venv/bin'dir. Bu test, birinin importlib
    bloğunu "sadeleştirip" düz import'a çevirmesini engelliyor — o hata ancak
    derleme zamanında, testler geçtikten SONRA ortaya çıkar.
    """
    text = _spec_text()
    assert "SPECPATH" in text, "sürüm yüklemesi SPECPATH'e çapalanmalı"
    assert not re.search(r"^\s*import\s+version\s*$", text, re.M), \
        "spec'te düz `import version` çalışmaz (bkz. docstring)"


def test_spec_has_no_syntax_warnings():
    """Yorumlara/docstring'e giren Windows yolları geçersiz kaçış dizisi doğurur.

    `%LOCALAPPDATA%\\GPT-Image Studio` yazmak `\\G`'yi geçersiz bir kaçış dizisi
    yapar ve Python SyntaxWarning basar (v0.3.0'da gerçekten oldu). Bu uyarı
    ancak DERLEME sırasında, pyinstaller'ın onlarca INFO satırı arasında
    görünür — kaybolmaya birebir uygun; ayrıca Python 3.15'te bu sınıf uyarı
    SyntaxError'a dönüyor, yani sessiz bir zaman bombası. Windows paketleme
    işi spec'e daha çok yol yazacağı için burada hataya çevriliyor.

    `compile` sadece derler, ÇALIŞTIRMAZ: spec'in Analysis/EXE çağrıları ve
    SPECPATH globali burada sorun etmez.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        compile(_spec_text(), SPEC, "exec")


def test_spec_windows_version_resource_derives_the_version():
    """VERSIONINFO'ya elle sürüm yazılırsa Windows tarafı sessizce ayrışır.

    Yukarıdaki CFBundle testinin birebir eşi: Info.plist'in Windows karşılığı
    bu kaynak ve aynı tek-kaynak kuralına tabi. Ayrışması özellikle sinsi,
    çünkü hatalı sürüm yalnızca exe'nin Özellikler sekmesinde görünür —
    hiçbir test, hiçbir çalışma zamanı davranışı bunu ele vermez.
    """
    text = _spec_text()
    for alan in ("FileVersion", "ProductVersion"):
        assert not re.search(rf'StringStruct\(\s*"{alan}"\s*,\s*["\']\d', text), \
            f"VERSIONINFO'da {alan} elle yazılmış — tek kaynak bozuldu"
        assert re.search(rf'StringStruct\(\s*"{alan}"\s*,\s*APP_VERSION\s*\)', text), \
            f"VERSIONINFO'daki {alan} APP_VERSION'dan gelmeli"


def test_spec_builds_the_version_resource_only_on_windows():
    """macOS derlemesinde üretmek yalnızca "Ignoring version information" gürültüsü.

    Kapı kaldırılırsa macOS hattı her derlemede uyarı basar; uyarı gürültüsü de
    zamanla gerçek uyarıların görülmemesine yol açar.
    """
    text = _spec_text()
    assert 'sys.platform == "win32"' in text, \
        "VERSIONINFO üretimi win32 kapısının arkasında olmalı"
    assert "version=_version_resource" in text, \
        "kaynak EXE'ye version=_version_resource ile geçmeli"


def test_version_module_imports_nothing_from_the_project():
    """spec bunu DERLEME zamanında yüklüyor: import zinciri yan etki üretmemeli.

    O noktada uygulamanın bağımlılıkları kurulu olmak zorunda değil ve
    version.py'nin çektiği herhangi bir proje modülü derlemeyi kırabilir.
    """
    with open(os.path.join(REPO, "version.py"), encoding="utf-8") as f:
        src = f.read()
    imports = re.findall(r"^\s*(?:import|from)\s+(\S+)", src, re.M)
    assert imports == ["__future__"], f"beklenmeyen import: {imports}"
