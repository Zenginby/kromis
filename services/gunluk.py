# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Uygulama günlüğünün kurulumu — `kromis.*` günlükçülerine stdout işleyicisi (Faz 2 / 8; 9. görev genişletir).

NEDEN VAR (ölçüldü, 2026-09-18 dumanı): admin yazımları `logging.getLogger(
"kromis.admin").info("olay=admin.tavan …")` satırı düşürüyor, ama uvicorn
yalnız KENDİ günlükçülerini (`uvicorn.*`) yapılandırır; kökte işleyici yok ve
Python'un son çare işleyicisi WARNING altını atar — satır hiçbir yere yazılmadı
(web sürecinin çıktısında 0 `olay=admin.*`). Yani "admin eylemi günlüğe düşer"
sözü, birisi kök günlükçüyü kurmadan boş bir sözdü.

BU MODÜL o kurulumun en küçük hâli: `kromis` ad alanına (`kromis.admin`,
yarın `kromis.istek`, `kromis.is`) tek bir stdout işleyicisi, INFO seviyesi,
köke YAYILMAZ (`propagate = False` — uvicorn kökü yapılandırırsa aynı satır
iki kez basılmasın). Biçim düz metin `k=v`; 9. görevin JSON biçimleyicisi
(`{"ts","seviye","olay",…}`, istek/iş kimliği) buraya takılır — modülün adı
da o yüzden belgenin (§9) verdiği ad. Platform günlük toplayıcıları stdout'tan
okur (12-factor), dosya yok.

`kur` İKİ KEZ ÇAĞRILABİLİR (testler, `TestClient(app)` her `with`te lifespan
koşturur): işleyici zaten varsa ikincisi eklenmez. `akim` parametresi test
için (StringIO); üretimde `sys.stdout`. Kullanıcıya konuşmaz: satırlar
operatöre gider (tests/test_i18n.py sınıflandırması).
"""
from __future__ import annotations

import logging
import sys
from typing import IO

__all__ = ["KOK", "BICIM", "kur"]

# `kromis.<alan>` — bu deponun bütün günlükçüleri bu ad altında; alan admin/istek/is.
KOK = "kromis"
# Düz metin; alanlar `k=v` (routers/admin.py `olay=admin.*`). 9. görev JSON'a çevirir.
BICIM = "%(asctime)s %(levelname)s %(name)s %(message)s"


def kur(akim: IO[str] | None = None) -> logging.Logger:
    """`kromis` günlükçüsünü INFO'da, tek stdout işleyicisiyle kurar; kurulmuşsa dokunmaz. Günlükçüyü döner."""
    kok = logging.getLogger(KOK)
    if not kok.handlers:
        isleyici = logging.StreamHandler(akim or sys.stdout)
        isleyici.setFormatter(logging.Formatter(BICIM))
        kok.addHandler(isleyici)
    kok.setLevel(logging.INFO)
    kok.propagate = False
    # Aynı süreçte koşan Alembic `fileConfig` (testler) daha önce yaratılmış günlükçüleri
    # kapatabilir; kurulum onları yeniden açar — üretimde göç ayrı süreç, zararsız.
    kok.disabled = False
    for ad, gunlukcu in logging.Logger.manager.loggerDict.items():
        if ad.startswith(KOK + ".") and isinstance(gunlukcu, logging.Logger):
            gunlukcu.disabled = False
    return kok
