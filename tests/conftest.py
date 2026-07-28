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
"""
from __future__ import annotations

import os

import pytest

import seed as seed_module

_UNGUARDED_FILENAME = "test_seed.py"


@pytest.fixture(autouse=True)
def _guard_against_real_seeding(request: pytest.FixtureRequest,
                                monkeypatch: pytest.MonkeyPatch):
    """Varsayılan olarak seed.seed_builtin_logos'u no-op yapar (bkz. modül docstring'i)."""
    if os.path.basename(str(request.node.fspath)) == _UNGUARDED_FILENAME:
        yield
        return
    monkeypatch.setattr(seed_module, "seed_builtin_logos", lambda *a, **k: [])
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
