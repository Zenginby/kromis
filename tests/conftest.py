"""Paylaşılan test fixture'ları.

I3 bulgusu: "import'un yan etkisi yok" sözleşmesi yalnızca KURAL olarak
duruyordu — hiçbir mekanizma zorlamıyordu. `with TestClient(app)` FastAPI'nin
belgelediği standart kalıptır; bunu kullanan HERHANGİ bir test dosyası
lifespan'ı tetikler ve lifespan'daki yan etkiler GERÇEK dosya sistemine
(geliştiricinin repo kökündeki assets/ ve output/ dizinlerine) yazar.

Lifespan'da bugün İKİ yan etki var: backup.py'nin sürüm-değişimi yedeği ve
(2026-09-10'dan beri) `paths._migrate_from_old_name` — eski `Lumeo` adıyla
açılmış kullanıcı dizinlerini yeni ada taşıyan göç. İkisinin de guard'ı
aşağıda, ikisi de kendi bekçi dosyasında muaf.
Geliştiricinin repo kökünde gerçek `output/history.json` ve `assets/*/index.json`
dosyaları VAR, yani `with TestClient(app)` kullanan tek bir test
`<repo>/backups/bilinmeyen-<bugün>/` ve `<repo>/.last-version` bırakırdı. O
kaçak damga, geliştiricinin KENDİ uygulamasının bir sonraki sürüm yedeğini bir
daha hiç almamasına yol açar. Aşağıdaki autouse fixture varsayılanı güvenli
yapıyor; yedeğin KENDİSİNİ test eden dosya (tests/test_backup.py) muaf tutuluyor
çünkü gerçek fonksiyonu koşturmak zorunda.

TARİHÇE: burada İKİNCİ bir guard vardı — `seed.seed_builtin_logos` pakete gömülü
yerleşik logoları kullanıcı kütüphanesine kopyalıyor ve `.logos-seeded`'i repo
kökünde bırakıyordu. Uygulama marka-nötr olunca seed.py tümüyle kaldırıldı, o
guard da onunla birlikte gitti.

Aşağıdaki `pytest_configure` bir fixture DEĞİL: takım koşmadan önce
yorumlayıcının ön koşulunu (`os.fchmod`) bir kez sınıyor. Gerekçesi orada.
"""
from __future__ import annotations

import os
import sys

import pytest

import backup as backup_module
import paths as paths_module

_UNGUARDED_BACKUP_FILENAME = "test_backup.py"
_UNGUARDED_MIGRATION_FILENAME = "test_paths.py"

# Bu deponun ASGARİ Python sürümü — TEK tanım. README'nin "Gereksinimler"
# başlığı, requirements-dev.txt'in girişi ve CI'daki `python-version` pinleri
# buna göre sınanıyor (tests/test_python_surumu.py). Yani bu sayıyı değiştirmek
# tek bir yeri değil, o testin gösterdiği HER yeri değiştirmek demek.
ASGARI_PYTHON = (3, 13)

# Kapıyı bilerek atlamanın yolu; mesajın kendi içinde de yazılı.
ESKI_PYTHON_IZNI = "KROMIS_ALLOW_OLD_PYTHON"


def pytest_configure(config: pytest.Config) -> None:
    """`os.fchmod` yoksa takımı HİÇ başlatmaz; tek ve okunur bir hata verir.

    NEDEN VAR (2026-09-08): Windows + Python 3.12.10'da ölçüldü — takım
    "45 failed, 2142 passed" veriyor ve 45'inin de TEK sebebi
    azure_client.py:262'deki `os.fchmod`. Kimlik dosyası YAZAN her yol aynı
    satırdan geçtiği için kırmızı üç dosyaya birden yayılıyor (test_credstore
    12, test_settings 9, test_settings_route 24) ve hiçbiri sebebi söylemiyor:
    `AttributeError: module 'os' has no attribute 'fchmod'`. Üstelik sinyal
    YANLIŞTI — README "Python 3.10+" yazıyordu; geliştirici belgeye UYDUĞU için
    bu duvara çarpıyordu.

    NEDEN 3.13: `os.fchmod` CPython'un Windows yapısına o sürümde eklendi
    (belge: "Changed in version 3.13: Added support on Windows"). 3.12'de
    yedek bir yol da YOK — `os.chmod` orada dosya tanıtıcısı kabul etmiyor
    (aynı makinede ölçüldü: `os.chmod in os.supports_fd` → False).

    NEDEN DURDURMAK, uyarmak DEĞİL: 45 sebepsiz kırmızının içinde GERÇEK bir
    gerileme görünmez olur. winsec.py'deki ilkenin öteki yüzü — orada
    "testlerin yeşil olduğu bir yalan"dan kaçınılıyor; sebepsiz kırmızı da
    kapıyı aynı biçimde işlevsizleştirir. Bir kez söyle ve dur.

    NEDEN `hasattr(os, "fchmod")`, sürüm KARŞILAŞTIRMASI DEĞİL: sınanan şey
    yorumlayıcının NUMARASI değil, eksik olan YETENEK. POSIX'te `fchmod` 3.13
    öncesinde de var ve orada takımı durdurmanın hiçbir sebebi yok — kapı bu
    yüzden yalnızca gerçekten kırılan yerde kapanıyor. `winsec.is_supported()`
    ile aynı disiplin.

    NEDEN Türkçe metin: depo geleneği — ama ÖLÇÜLDÜ: cp1252 konsola boru ile
    yazıldığında pytest `backslashreplace` uyguluyor, yani harfler `\\u0131`
    kaçışlarına düşer ama UnicodeEncodeError ÇIKMIYOR
    (test_encoding_contract'ın Faz 5 dersi). Eyleme dönük kısımlar — sürümler,
    komutlar, ortam değişkeni — bu yüzden ASCII bırakıldı: kodlama ne olursa
    olsun onlar okunur kalıyor.
    """
    if hasattr(os, "fchmod"):
        return
    if os.environ.get(ESKI_PYTHON_IZNI) == "1":
        return  # bilinçli atlama: yukarıda sayılan 45 test yine düşecek

    asgari = ".".join(str(parca) for parca in ASGARI_PYTHON)
    bulunan = ".".join(str(parca) for parca in sys.version_info[:3])
    raise pytest.UsageError(
        f"Bu depo Python {asgari}+ ISTIYOR - bulunan: {bulunan} ({sys.platform})."
        "\n\n"
        "NEDEN: azure_client._atomic_write, kimlik dosyasini yazmadan ONCE "
        "izinleri sikilastirmak icin `os.fchmod(fd, 0o600)` cagiriyor ve bu "
        "cagri CPython'un Windows yapisina ancak 3.13'te eklendi. Bu "
        "yorumlayicida kimlik YAZAN her test \"AttributeError: module 'os' has "
        "no attribute 'fchmod'\" ile duser (olculdu: 45 test) - kusur SENIN "
        "degisikliginde degil, yorumlayicida."
        "\n\n"
        "COZUM: 3.13 ya da ustunu kur (CI ve paketler 3.14 kullaniyor) ve "
        ".venv'i onunla yeniden yarat:\n"
        "    py -3.13 -m venv .venv\n"
        "    .venv\\Scripts\\python -m pip install -r requirements.txt "
        "-r requirements-dev.txt"
        "\n\n"
        "Kimlige dokunmayan testleri bu yorumlayicida yine de kosmak icin: "
        f"{ESKI_PYTHON_IZNI}=1 (o 45 test yine duser)."
    )


@pytest.fixture(autouse=True)
def _guard_against_leaking_android_env():
    """Android dalını açan ortam değişkenleri testler arasında SIZMASIN.

    Üçüncü guard, aynı sınıf bir tehdide karşı: `paths.py`'nin Android dalı
    `KROMIS_ANDROID_DATA_DIR` ortam değişkenine bakıyor ve o değişken KÜRESEL —
    `monkeypatch` yalnız KENDİ yazdığı değerleri geri alıyor. Ortam değişkenine
    doğrudan yazan bir üretim fonksiyonu (`android_main._prepare_environment`,
    Kotlin'in yaptığı işi taklit ederken) değeri geride bırakırsa, o noktadan
    SONRAKİ her test `paths.data_dir()`'i repo kökü yerine sahte bir Android
    dizini sanır.

    Bu teorik değil, ölçüldü: guard yazılmadan önce tek bir sızıntı
    test_chat_prompt / test_logo / test_paths'te 27 testi birden düşürdü —
    üstelik hata mesajları kaynağa hiç işaret etmiyordu. Guard, teşhisi zor bu
    kırılma sınıfını tümden kapatıyor.
    """
    yield
    for ad in (paths_module.ANDROID_DATA_ENV, paths_module.ANDROID_RESOURCE_ENV):
        os.environ.pop(ad, None)


@pytest.fixture(autouse=True)
def _guard_against_real_backups(request: pytest.FixtureRequest,
                                monkeypatch: pytest.MonkeyPatch):
    """Varsayılan olarak sürüm-değişimi yedeğini no-op yapar (bkz. modül docstring'i).

    app.py bu fonksiyonu MODÜL ATTRIBUTE'u üzerinden çağırmak zorunda —
    `from backup import ...` bu guard'ı sessizce devre dışı bırakır.
    """
    if os.path.basename(str(request.node.fspath)) == _UNGUARDED_BACKUP_FILENAME:
        yield
        return
    monkeypatch.setattr(backup_module, "backup_manifests_if_version_changed",
                        lambda *a, **k: None)
    yield


@pytest.fixture(autouse=True)
def _guard_against_real_migration(request: pytest.FixtureRequest,
                                  monkeypatch: pytest.MonkeyPatch):
    """Ad göçünü varsayılan olarak no-op yapar (2026-09-10).

    DÖRDÜNCÜ guard, yedek guard'ıyla aynı sınıf bir tehdide karşı:
    `paths.ensure_data_dirs()` artık `_migrate_from_old_name()` çağırıyor ve o
    fonksiyon geliştiricinin GERÇEK `~/.config/lumeo/credentials.env` dosyasını
    `~/.config/kromis/` altına taşıyor. `with TestClient(app)` kullanan tek bir
    test, geliştiricinin ev dizinini oynatırdı — üstelik sessizce, çünkü göç
    başarılı olduğunda hiçbir şey söylemiyor.

    Muafiyet `test_paths.py`: göç davranışının bekçisi orada ve gerçek
    fonksiyonu koşturmak zorunda. O dosyadaki her göç testi yolları tmp_path'e
    çekiyor, yani muafiyet ev dizinini açıkta bırakmıyor.
    """
    if os.path.basename(str(request.node.fspath)) == _UNGUARDED_MIGRATION_FILENAME:
        yield
        return
    monkeypatch.setattr(paths_module, "_migrate_from_old_name", lambda: None)
    yield


@pytest.fixture
def fake_composite():
    """composite.composite_logo yerine geçer: girdiyi olduğu gibi döndürür.

    tests/test_folders.py ve tests/test_palette_route.py'de birebir aynı
    (`_fake_composite`) olarak duruyordu — buraya taşındı.
    """
    def _fake_composite(base_path: str, **kwargs) -> bytes:
        with open(base_path, "rb") as f:
            return f.read()
    return _fake_composite


def tr(anahtar: str) -> str:
    """Bir çeviri anahtarının TÜRKÇE metni — arayüz metnine bakan testler için.

    Çoklu dil desteği (v0.21) arayüz metinlerini `static/*.js` ve
    `static/index.html` içinden `bundled/i18n/*.json`a taşıdı. Bunu ölçen
    testlerin İKİ farklı sorusu var ve ikisi ayrı yere bakmalı:

      · "Bu dal DOĞRU cümleyi mi seçiyor?" → betikte ANAHTARI ara
        (`t("gate.arena_no_edit")`). Metin değişse bile dal aynı kalır, yani
        test cümlenin yazımına değil KARARA bakmış olur.
      · "Cümle kullanıcıya şunu SÖYLÜYOR mu?" → metni buradan al. Anahtarın
        kendisini kopyalamak yetmezdi: sözlükten silinmiş bir anahtar
        `i18n.t` tarafından sessizce kendisine düşer ve test yine geçerdi.

    İkincisi için doğrudan `i18n.t` çağrılabilirdi; bu sarmalayıcı ADIYLA
    hangi soruyu sorduğunu söylüyor ve testlerin dile bağımlılığını tek bir
    yerde topluyor.
    """
    import i18n
    metin = i18n.t(anahtar, "tr")
    assert metin != anahtar, f"sözlükte yok: {anahtar}"
    return metin
