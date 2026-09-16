# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Veri dizinleri — rotaların İSTEK ANINDA okuduğu tek kapı.

NEDEN İŞLEV, SABİT DEĞİL: `OUTPUT_DIR`/`ASSETS_DIR`/`STATIC_DIR` bugün de
`app.py`nin modül düzeyi sabitleri ve testler onları oradan yamalıyor —
`monkeypatch.setattr(appmod, "OUTPUT_DIR", tmp_path)` 47 yerde, `ASSETS_DIR`
17, `STATIC_DIR` 2 (docs/faz0-web-first.md, 2. görevin ölçümü). Rotalar
`routers/` altına taşınınca `from app import OUTPUT_DIR` yazan bir router
İTHAL ANINDAKİ değeri kopyalar ve yama boşa gider: 47 test sessizce
geliştiricinin GERÇEK veri dizinine yazardı. `import app` de çözüm değil —
`app` router'ları ithal ediyor, döngü.

Bu yüzden değer burada TUTULMUYOR, OKUNUYOR: `app` modülü yüklüyse ORADAKİ
öznitelik döner (yamanın hedefi o), yüklü değilse (bir router'ı tek başına
ithal eden bir test) `paths` doğrudan cevaplar. Tek kaynak `app.py`, tek
okuma noktası burası.

GEÇİCİ ve bilerek: Faz 0'ın 4. görevi dizinleri bir ayar nesnesine
(`Depends`) taşıyacak ve o gün `sys.modules` bakışı da, `app.py`deki sabitler
de kalkacak. O güne kadar `app.py`ye `import` yerine ad üzerinden bakmak,
döngüyü açmadan yamayı çalışır tutmanın en küçük yolu.
"""
from __future__ import annotations

import sys

import paths

# Bileşim kökünün modül adı. `sys.modules` anahtarı, ithal DEĞİL (döngü).
_KOK_MODUL = "app"


def _kokten(ad: str, varsayilan) -> str:
    kok = sys.modules.get(_KOK_MODUL)
    deger = getattr(kok, ad, None) if kok is not None else None
    return deger if deger is not None else varsayilan()


def output_dir() -> str:
    """Çıktı dizini (`history.json`, görseller, tercihler, sohbetler)."""
    return _kokten("OUTPUT_DIR", paths.output_dir)


def assets_dir() -> str:
    """Kullanıcının logo/afiş kütüphanesi."""
    return _kokten("ASSETS_DIR", paths.assets_dir)


def static_dir() -> str:
    """`index.html` ve betiklerin dizini."""
    return _kokten("STATIC_DIR", paths.static_dir)
