"""Paylaşılan test fixture'ları.

I3 bulgusu: "import'un yan etkisi yok" sözleşmesi yalnızca KURAL olarak
duruyordu — hiçbir mekanizma zorlamıyordu. `with TestClient(app)` FastAPI'nin
belgelediği standart kalıptır; bunu kullanan HERHANGİ bir test dosyası
lifespan'ı tetikler ve lifespan'daki yan etkiler GERÇEK dosya sistemine
(geliştiricinin repo kökündeki assets/ ve output/ dizinlerine) yazar.

Bugün lifespan'da tek yan etki var: backup.py'nin sürüm-değişimi yedeği.
Geliştiricinin repo kökünde gerçek `output/history.json` ve `assets/*/index.json`
dosyaları VAR, yani `with TestClient(app)` kullanan tek bir test
`<repo>/backups/bilinmeyen-<bugün>/` ve `<repo>/.last-version` bırakırdı. O
kaçak damga, geliştiricinin KENDİ uygulamasının bir sonraki sürüm yedeğini bir
daha hiç almamasına yol açar. Aşağıdaki autouse fixture varsayılanı güvenli
yapıyor; yedeğin KENDİSİNİ test eden dosya (tests/test_backup.py) muaf tutuluyor
çünkü gerçek fonksiyonu koşturmak zorunda.

TARİHÇE: burada İKİNCİ bir guard vardı — `seed.seed_builtin_logos` pakete gömülü
KURUM logolarını kullanıcı kütüphanesine kopyalıyor ve `.logos-seeded`'i repo
kökünde bırakıyordu. Uygulama marka-nötr olunca seed.py tümüyle kaldırıldı, o
guard da onunla birlikte gitti.
"""
from __future__ import annotations

import os

import pytest

import backup as backup_module
import paths as paths_module

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
