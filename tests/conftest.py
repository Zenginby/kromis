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

import importlib.util
import os
import sys

import pytest

import backup as backup_module
import paths as paths_module
from services import ayar

# Hangi dosyaların E2E olduğu TEK yerde ölçülüyor; gerekçesi orada. Salt
# kitaplık bir modül, yani takımın kendisi bir kuruluma bağlanmıyor.
from tools.test_ortami import e2e_dosyalari

_UNGUARDED_BACKUP_FILENAME = "test_backup.py"
_UNGUARDED_MIGRATION_FILENAME = "test_paths.py"

# Bu deponun ASGARİ Python sürümü — TEK tanım. README'nin "Gereksinimler"
# başlığı, requirements-dev.txt'in girişi ve CI'daki `python-version` pinleri
# buna göre sınanıyor (tests/test_python_surumu.py). Yani bu sayıyı değiştirmek
# tek bir yeri değil, o testin gösterdiği HER yeri değiştirmek demek.
ASGARI_PYTHON = (3, 13)

# Kapıyı bilerek atlamanın yolu; mesajın kendi içinde de yazılı.
ESKI_PYTHON_IZNI = "KROMIS_ALLOW_OLD_PYTHON"

# E2E'nin ATLANMASINI yasaklayan ortam değişkeni. CI bunu "1" veriyor
# (`_test.yml`), yani orada playwright kurulum adımı bir gün sessizce
# kaybolursa takım "yeşil ama eksik" olmaz, KIRMIZI olur.
E2E_ZORUNLU = "KROMIS_E2E_ZORUNLU"


def _playwright_var() -> bool:
    return importlib.util.find_spec("playwright") is not None


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """E2E atlandıysa takımın SONUNDA bunu bağıra bağıra söyler.

    NEDEN VAR (2026-09-13'te ölçüldü): `ci.yml` bu depoda dokuz kez kırmızıya
    döndü ve SEKİZİNDE düşen testler `tests/test_playwright_*.py`
    dosyalarındaydı. Playwright kurulu olmayan bir makinede o dosyalar
    `importorskip` ile ATLANIYOR ve pytest son satırda yine "passed" diyor.
    Kusur testlerde değil, SİNYALDE: "2531 passed, 11 skipped" cümlesi
    E2E'nin hiç koşmadığını söylemiyordu.

    NEDEN UYARI, KIRMIZI DEĞİL: playwright bilerek `requirements-dev.txt`te
    DEĞİL — paketleme işleri o dosyayı kurup pytest'i tarayıcısız koşturuyor
    ve orada atlama DOĞRU davranış (gerekçe: tests/test_playwright_kurulumu.py).
    Yani her atlama bir kusur değil; kusur olan, atlamanın GÖRÜNMEMESİ.
    Bilerek kırmızı isteyen için kapı ayrı: KROMIS_E2E_ZORUNLU=1.

    NEDEN SAYI DEĞİL DOSYA ADI: modül düzeyindeki `importorskip` tüm dosyayı
    tek bir "skipped" kaydına indiriyor, yani "kaç test atlandı" burada
    dürüstçe söylenemez. Atlanan DOSYALAR söyleniyor.
    """
    if _playwright_var():
        return
    atlanan = e2e_dosyalari()
    if not atlanan:
        return
    # Eyleme dönük kısımlar ASCII: bu satırlar cp1252 bir konsola boru ile
    # yazıldığında Türkçe harfler `ı` kaçışlarına düşüyor (Faz 5 dersi,
    # bkz. pytest_configure'ın gerekçesi) — komut okunur kalmalı.
    terminalreporter.write_sep("=", "E2E ATLANDI: bu yesil, TAM yesil degil",
                               yellow=True, bold=True)
    terminalreporter.write_line(
        "playwright kurulu olmadigi icin su dosyalar HIC kosmadi:")
    for ad in atlanan:
        terminalreporter.write_line(f"    tests/{ad}")
    terminalreporter.write_line(
        "Bu depodaki ilk-kosu CI kirmizilarinin cogu tam olarak bu dosyalardi: "
        "arayuz metni, on tanimli dil ve DOM capasi degisiklikleri yalnizca "
        "burada gorunuyor.")
    terminalreporter.write_line("Ortami kur : python3 tools/test_ortami.py")
    terminalreporter.write_line(f"Atlamayi hataya cevir: {E2E_ZORUNLU}=1")
    terminalreporter.write_sep("=", yellow=True, bold=True)


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
    # E2E KAPISI (gerekçesi pytest_terminal_summary'de): atlama açıkça
    # yasaklandıysa takımı HİÇ başlatma. `_test.yml` bu değişkeni veriyor, yani
    # CI'da playwright kurulum adımı bir gün sessizce kaybolursa kapı kapanır —
    # `tests/test_playwright_kurulumu.py` workflow'un METNİNİ sınıyor, bu satır
    # da onun GERÇEKTEN iş görüp görmediğini.
    if os.environ.get(E2E_ZORUNLU) == "1" and not _playwright_var():
        raise pytest.UsageError(
            f"{E2E_ZORUNLU}=1 verildi ama playwright kurulu DEGIL: E2E "
            "testleri atlanacakti."
            "\n\n"
            "COZUM: python3 tools/test_ortami.py"
            "\n\n"
            f"Atlamaya izin vermek icin {E2E_ZORUNLU} degiskenini kaldirin "
            "(paketleme isleri pytest'i bilerek tarayicisiz kosturuyor)."
        )

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


@pytest.fixture(autouse=True)
def _dil_baglami_testler_arasinda_sizmasin():
    """Her testi `i18n.FALLBACK` bağlamıyla başlatır.

    BEŞİNCİ guard ve sebebi ÖLÇÜLDÜ (v0.22, ön tanımlı dil "en" olurken):
    `app._dil_baglami` her istekte `i18n.set_active` çağırıyor ve `TestClient`
    isteği kendi portalında koşturduğu için o değer ana bağlamda ASILI
    KALIYOR. Yani bir `client.post(...)`tan sonra koşan HER test, bağlamı hiç
    kurmadan `i18n.t(anahtar, None)` çağırdığında bir önceki testin dilini
    görüyor — sıraya bağlı, dosya dışına taşan bir sızıntı.

    Sızıntı ÖNCEDEN DE VARDI, yalnızca GÖRÜNMÜYORDU: ön tanımlı dil ile
    kaynak dil aynı olduğu sürece sızan değer zaten beklenen değerdi. İkisi
    ayrılınca `map_error`ı doğrudan çağıran testler (test_gemini_client ve
    yedi ikizi) tek başına YEŞİL, takımın içinde KIRMIZI oldu — testin kendi
    kusuru değil, bağlamın kusuru.

    `FALLBACK`, `DEFAULT` DEĞİL: bu fixture'ın kurduğu şey "kullanıcı yok"
    hâli ve `i18n._AKTIF`ın kendi varsayılanı da o (gerekçesi orada). Ürünün
    ön tanımlı dilinin bekçisi ayrı: `test_prefs.py` varsayılanı,
    `test_i18n.py` de hiç tercih yazılmamış bir kurulumun hangi dilde
    servis edildiğini sınıyor.

    `tercih.sifirla()` da burada (Faz 0 / Adım 3) ve aynı sınıf sızıntı:
    kayıtlı tercih artık dosya imzalı bir önbellekten okunuyor. İki test aynı
    dizini paylaşıp (`dizinler` fixture'ını kullanmayan E2E testleri
    geliştiricinin gerçek `output/`unu kullanıyor) `prefs.read_stored`ı FARKLI dillerle
    yamalarsa dosya ikisinde de değişmez ve ikinci test önbellekten
    birincinin dilini okurdu — `test_playwright_dil`in iki parametresi tam
    olarak bu çift.
    """
    import i18n
    from services import tercih
    i18n.set_active(i18n.FALLBACK)
    tercih.sifirla()
    yield


@pytest.fixture
def dizinler(monkeypatch: pytest.MonkeyPatch):
    """Uygulamanın veri dizinlerini bu test süresince YÖNLENDİRİR (Faz 0 / Adım 4).

    Kullanımı: `dizinler(output_dir=str(tmp_path))`,
    `dizinler(output_dir=…, assets_dir=…)`, `dizinler(static_dir=…)`,
    `dizinler(data_dir=…)`. Verilmeyen alan olduğu gibi kalır; dönen `Ayarlar`
    nesnesinden yollar okunabilir.

    NEDEN TEK FİXTURE: Adım 4'e kadar 66 test `monkeypatch.setattr(appmod,
    "OUTPUT_DIR", …)` yazıyordu ve router'lar o adı `sys.modules["app"]`
    üzerinden okuyordu (services/yollar.py, artık yok). Dizinler artık
    `app.state.ayarlar`daki donmuş `Ayarlar` nesnesinde; rotalar onu
    `Depends(ayar.ayarlar)` ile alıyor, ara katman ve lifespan `app.state`ten
    okuyor. Yani yamanın TEK hedefi var ve o hedef burada — bir testin başka
    bir yolla dizin değiştirmesi (`paths`i yamalamak gibi) rotaya ULAŞMAZ.

    NEDEN FABRİKA (çağrılabilir döndürüyor), sabit yerleşim DEĞİL: mevcut
    testlerin yarısı `output_dir=tmp_path`, öteki yarısı `tmp_path/"output"`
    yerleşimini kullanıyor ve dosya yollarına iddia yazıyor
    (`tmp_path / "hata.log"`, `tmp_path / f"{id}.png"`). Tek bir yerleşim
    dayatmak o iddiaların hepsini elle yeniden yazdırırdı; fabrika eski
    yamayı bire bir karşılıyor.

    NEDEN `dataclasses.replace` + `monkeypatch.setattr(app.state, …)`:
    nesne donmuş (paylaşılan durum yanlışlıkla değişmesin), kopya alınıyor;
    `monkeypatch` testin sonunda eski nesneyi geri koyuyor. Art arda iki
    çağrı birikir (ikincisi birincinin kopyasından türer) ve LIFO geri alma
    sırayı doğru kapatır.

    `app` BURADA ithal ediliyor (modül başında değil): conftest'in kendisi
    `import app` yaparsa her test dosyası — `paths`i tek başına sınayanlar
    dâhil — bileşim kökünü ve 60 modülü yüklemiş olurdu.
    """
    import dataclasses

    import app as appmod

    def _yonlendir(**alanlar: str) -> ayar.Ayarlar:
        yeni = dataclasses.replace(appmod.app.state.ayarlar, **alanlar)
        monkeypatch.setattr(appmod.app.state, "ayarlar", yeni)
        return yeni

    return _yonlendir


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


def duz_rotalar(uygulama) -> list[tuple[str, str]]:
    """Çalışan uygulamanın (YÖNTEM, yol) çiftleri — ağaç değil DÜZ liste.

    NEDEN VAR (Faz 0 / Adım 5): FastAPI 0.137 `include_router`ı rotaları
    kopyalamayı bıraktı; `app.routes` artık takılan her router için tek bir
    `_IncludedRouter` düğümü taşıyor ve asıl rotalar onun
    `original_router.routes` altında (iç içe include'larda daha da derinde).
    0.115'te `app.routes` düz bir listeydi; onu doğrudan sayan iki test
    (`test_app_bolme`, `test_arena_onyuz`) 0.141'de yalnız `/docs` ailesini
    görüp kırmızıya döndü. Yürüyüş TEK yerde dursun ki bir sonraki iç yapı
    değişikliği iki testi ayrı ayrı değil burayı kırsın.

    Ön ek `include_context.prefix`ten toplanıyor: bugün `app.py` öneksiz
    takıyor, ama öneksiz varsayan bir yürüyüş ilk `prefix=` ile sessizce
    yanlış yol üretirdi. Belge rotaları (`/docs`, `/redoc`, `/openapi.json`)
    ve `Mount`lar (yöntemsiz) çağıranın süzgecine bırakılıyor.
    """
    bulunan: list[tuple[str, str]] = []

    def _yuru(rotalar, on_ek: str) -> None:
        for r in rotalar:
            ic = getattr(r, "original_router", None)
            if ic is not None:                      # FastAPI ≥ 0.137 düğümü
                baglam = getattr(r, "include_context", None)
                _yuru(ic.routes, on_ek + (getattr(baglam, "prefix", "") or ""))
                continue
            for yontem in getattr(r, "methods", None) or ():
                bulunan.append((yontem, on_ek + r.path))

    _yuru(uygulama.routes, "")
    return bulunan
