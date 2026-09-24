# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""HTTP uçları — alan bazlı `APIRouter` modülleri.

Her modül tek bir `router = APIRouter()` tanımlar ve `app.py` (bileşim kökü)
onları `include_router` ile takar. Yollar ÖNEKSİZ, rotanın üstünde birebir
yazılı (`@router.post("/api/generate")`): `grep "/api/generate"` hâlâ tek
satıra düşmeli ve `tools/graf_uret.py`nin uç nokta taraması bir önek
tablosu okumak zorunda kalmamalı.

KURAL: bir router `app`i ithal etmez (döngü) ve başka bir router'ı da ithal
etmez — paylaşılan her şey `services/` altında (bekçisi tests/test_app_bolme.py).
"""
