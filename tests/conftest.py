"""Paylaşılan test fixture'ları.

I3 bulgusu: "import'un yan etkisi yok" sözleşmesi yalnızca KURAL olarak
duruyordu — hiçbir mekanizma zorlamıyordu. `with TestClient(app)` FastAPI'nin
belgelediği ve tests/test_seed.py'nin de kullandığı standart bir kalıptır;
bunu kullanan HERHANGİ bir yeni test dosyası lifespan'ı tetikler ve
`seed.seed_builtin_logos` GERÇEK dosya sistemine (geliştiricinin assets/
dizinine) yazar, `.logos-seeded`'i repo kökünde bırakır.

Bu autouse fixture varsayılanı güvenli yapar: `seed.seed_builtin_logos`
her testte no-op'a çevrilir. Tohumlamanın KENDİSİNİ test eden tek dosya
(tests/test_seed.py) — hem davranış testleri hem de lifespan-kanıt testleri —
kasıtlı olarak muaf tutulur: onlar ya gerçek fonksiyonu doğrudan çağırıyor
ya da kendi casus'larını (spy) kuruyor; ikisi de bu guard'ın no-op'uyla
ezilirse test vacuous (anlamsız) hale gelir.

v1.9'da lifespan'a İKİNCİ bir yan etki eklendi (backup.py, sürüm değişiminde
manifest yedeği) ve aynı tehdide açık — hatta sonucu daha kötü: geliştiricinin
repo kökünde gerçek `output/history.json` ve `assets/*/index.json` dosyaları
VAR (`.logos-seeded`'ın repo kökünde durması bunun kanıtı), yani `with
TestClient(app)` kullanan tek bir test `<repo>/backups/bilinmeyen-<bugün>/` ve
`<repo>/.last-version` bırakırdı. O kaçak damga, geliştiricinin KENDİ
uygulamasının v1.8→v1.9 yedeğini bir daha hiç almamasına yol açar.

İkinci guard AYRI tutuldu (mevcut olanı bir muafiyet tablosuna çevirmek yerine)
çünkü muafiyetler kesişmiyor: tests/test_seed.py seed guard'ından muaf ama
yedek guard'ına TABİ kalmalı (lifespan testleri repoya yedek yazmasın);
simetrik olarak tests/test_backup.py gerçek yedeği koşarken tohumlama no-op
kalmalı (yedek testleri tohum verisiyle kirlenmesin).
"""
from __future__ import annotations

import os

import pytest

import backup as backup_module
import paths as paths_module
import seed as seed_module

_UNGUARDED_FILENAME = "test_seed.py"
_UNGUARDED_BACKUP_FILENAME = "test_backup.py"


@pytest.fixture(autouse=True)
def _guard_against_leaking_android_env():
    """Android dalını açan ortam değişkenleri testler arasında SIZMASIN.

    Üçüncü guard, aynı sınıf bir tehdide karşı: `paths.py`'nin Android dalı
    `GIS_ANDROID_DATA_DIR` ortam değişkenine bakıyor ve o değişken KÜRESEL —
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
def _guard_against_real_seeding(request: pytest.FixtureRequest,
                                monkeypatch: pytest.MonkeyPatch):
    """Varsayılan olarak seed.seed_builtin_logos'u no-op yapar (bkz. modül docstring'i)."""
    if os.path.basename(str(request.node.fspath)) == _UNGUARDED_FILENAME:
        yield
        return
    monkeypatch.setattr(seed_module, "seed_builtin_logos", lambda *a, **k: [])
    yield


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
