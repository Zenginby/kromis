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
SPEC = os.path.join(REPO, "kromis.spec")


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

    `%LOCALAPPDATA%\\Kromis` yazmak `\\K`'yi geçersiz bir kaçış dizisi
    yapar ve Python SyntaxWarning basar (v0.3.0'da gerçekten oldu). Bu uyarı
    ancak DERLEME sırasında, pyinstaller'ın onlarca INFO satırı arasında
    görünür — kaybolmaya birebir uygun; ayrıca Python 3.15'te bu sınıf uyarı
    SyntaxError'a dönüyor, yani sessiz bir zaman bombası. Windows paketleme
    işi spec'e daha çok yol yazacağı için burada hataya çevriliyor.

    `compile` sadece derler, ÇALIŞTIRMAZ: spec'in Analysis/EXE çağrıları ve
    SPECPATH globali burada sorun etmez.

    KAPSAM: bu kapı yalnız spec'e bakıyor ve o yüzden aynı kusurun bir test
    docstring'inde İKİNCİ kez geçmesini göremedi. Sınıfın depo geneli kapısı
    artık tests/test_syntax_warnings.py; bu test onun altında kalıyor çünkü
    v0.3.0 olayının kaydı ve spec'i adıyla gösteren bir hata mesajı veriyor.
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


def test_the_windows_gate_expects_exactly_what_the_spec_writes():
    """EŞLEŞEN ÇİFT: spec'in VERSIONINFO alanları ↔ workflow'un kapısı.

    `_paket-windows.yml` derlenen exe'nin `CompanyName` ve `FileDescription`
    alanlarını okuyup BEKLENEN değerle karşılaştırıyor. İki dosya da kendi
    içinde tutarlı olabilir ama birleştikleri yerde ayrışırsa sonuç en pahalı
    kırmızı: Windows paketi ONLARCA DAKİKA derlenip, tam yayına gireceği anda
    "beklenen [X], gelen [Y]" diyerek düşer. Yerelde koşan bu ucuz iddia aynı
    kaymayı saniyede yakalıyor — `tests/test_android_apk_name.py` ile birebir
    aynı gerekçe.

    NEDEN `FileDescription` TÜRKÇE KARAKTER TAŞIMALI: o alan VERSIONINFO'nun
    Türkçe karakter turunu ölçen TEK yer. Güvence 2026-09-10'da bir an
    kaybolmuştu (eski `CompanyName` Türkçe karakter taşıyordu, ASCII bir
    sahiplikle değişince VERSIONINFO tümden ASCII kaldı). ASCII'ye inen bir
    açıklama kapıyı yeşil bırakır ama KONUSUZ yapar; bu yüzden ölçülüyor.

    Workflow tarafındaki beklenti kod noktalarından kuruluyor
    (`[char]0xF6`) — gerekçesi orada yazılı: doğrulamanın kendisi, ölçtüğü
    kodlama kusuruna açık olmamalı. Bu test o küçük ifadeyi çözüp değeri
    yeniden kuruyor.
    """
    spec = _spec_text()
    with open(os.path.join(REPO, ".github", "workflows", "_paket-windows.yml"),
              encoding="utf-8") as f:
        workflow = f.read()

    def _spec_alani(ad: str) -> str:
        m = re.search(rf'StringStruct\(\s*"{ad}"\s*,\s*"([^"]*)"\s*\)', spec)
        assert m, f"kromis.spec'te VERSIONINFO alanı {ad} bulunamadı"
        return m.group(1)

    def _ps_dizesi(degisken: str) -> str:
        """`$x = 'a' + [char]0xF6 + 'b'` ifadesini çözer."""
        m = re.search(rf"\${degisken}\s*=\s*(.+)", workflow)
        assert m, f"_paket-windows.yml'de ${degisken} atanmıyor"
        parcalar = re.findall(r"'([^']*)'|\[char\]0x([0-9A-Fa-f]+)", m.group(1))
        assert parcalar, f"${degisken} ifadesi çözülemedi: {m.group(1)!r}"
        return "".join(duz or chr(int(kod, 16)) for duz, kod in parcalar)

    assert _ps_dizesi("sirket") == _spec_alani("CompanyName")
    aciklama = _spec_alani("FileDescription")
    assert _ps_dizesi("aciklama") == aciklama
    assert any(ord(c) > 127 for c in aciklama), (
        "FileDescription ASCII'ye indi — VERSIONINFO'nun Türkçe karakter turunu "
        "ölçen alan buydu; kapı yeşil kalır ama artık hiçbir şey ölçmez"
    )


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


def _readme_text() -> str:
    with open(os.path.join(REPO, "README.md"), encoding="utf-8") as f:
        return f.read()


def test_readme_version_literals_match_the_single_source():
    """README'nin sürüm literalleri version.py ile aynı olmak ZORUNDA.

    Bu test var, çünkü hata gerçekten oldu: rozet `v0.3.0`da kalmışken version.py
    0.4.1'e gelmişti. Zararı kozmetik değil — rozetin yanındaki indirme
    bağlantıları `releases/latest` gösteriyor, yani kullanıcı "v0.3.0" yazan bir
    rozete bakıp gerçekte 0.4.1'i indiriyor ve telefonundaki sürümün güncel
    olup olmadığına karar veremiyor.

    Rozet BİLEREK elle yazılıyor, shields.io'nun dinamik `github/v/release`
    rozetiyle değil: depo private, shields.io okuyamaz ve rozet "inaccessible"
    çıkardı. Elle yazılan bir literalin bekçisi de ancak böyle bir test olur.
    """
    text = _readme_text()
    v = version.APP_VERSION

    rozet = re.search(r"img\.shields\.io/badge/version-v([\d.]+)-", text)
    assert rozet, "sürüm rozeti bulunamadı"
    assert rozet.group(1) == v, \
        f"rozet v{rozet.group(1)}, version.py {v} — tek kaynak bozuldu"

    # Başlıktaki sürüm de aynı kaynağa bağlı: "Güncel Özellikler (v0.4.1 ...)"
    baslik = re.search(r"##\s*.*Güncel Özellikler\s*\(v([\d.]+)", text)
    assert baslik, "özellik başlığındaki sürüm bulunamadı"
    assert baslik.group(1) == v, \
        f"başlık v{baslik.group(1)}, version.py {v} — tek kaynak bozuldu"

    # Kaçak: başka hiçbir yerde farklı bir vX.Y.Z geçmesin. Tarihçe/geçmiş
    # sürüm anlatan bir bölüm eklenirse bu iddia bilinçli olarak gevşetilmeli.
    kacak = {m for m in re.findall(r"\bv(\d+\.\d+\.\d+)\b", text) if m != v}
    assert not kacak, f"README'de bayat sürüm literali: {sorted(kacak)}"


# NOT — buradaki "README indirme bağlantıları yayına eklenen adlarla aynı mı"
# testi tests/test_release_manifest.py'ye TAŞINDI.
#
# Gerekçe: o iddia dosya adlarını üç yerde birden (README, iki workflow'un
# `files:` listesi) sabit yazıyordu, yani dördüncü bir platform eklendiğinde
# testin KENDİSİ de elle güncellenmesi gereken bir yer oluyordu — koruduğu
# ayrışmanın aynısına açık. Artık tek kaynak `release_manifest.py` ve zincirin
# her halkası oradan türetiliyor:
#   README      ↔ manifest  →  test_readme_indirme_baglantilari_manifestle_birebir
#   manifest    ↔ workflow  →  test_workflow_varligi_manifestteki_adla_yukluyor
#   manifest    ↔ yayın işi →  test_yayin_isi_her_paketi_bekliyor
# Yayına yazan tek bir iş kaldığı için `files:` listesini ayrıca aramaya da
# gerek kalmadı (bkz. test_yayini_yalnizca_tek_is_olusturuyor).


def test_version_module_imports_nothing_from_the_project():
    """spec bunu DERLEME zamanında yüklüyor: import zinciri yan etki üretmemeli.

    O noktada uygulamanın bağımlılıkları kurulu olmak zorunda değil ve
    version.py'nin çektiği herhangi bir proje modülü derlemeyi kırabilir.
    """
    with open(os.path.join(REPO, "version.py"), encoding="utf-8") as f:
        src = f.read()
    imports = re.findall(r"^\s*(?:import|from)\s+(\S+)", src, re.M)
    assert imports == ["__future__"], f"beklenmeyen import: {imports}"
