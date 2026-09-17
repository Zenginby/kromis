# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kök sayfa: `index.html`in sürüm ve çeviri yerleştirilmiş hâli.

`/static` mount'u BURADA DEĞİL, `app.py`de: mount bir rota değil bir alt
uygulama ve `include_router` onu taşıyamaz. İki şeyin ayrı yerde durmasının
gerekçesi `app.py`deki mount yorumunda (no-store / önbellek asimetrisi).

Yerleştirmenin KENDİSİ de burada değil, `services/sablon.py`de (Faz 1 / 3):
ikinci sayfa (`GET /giris`, routers/hesap.py) aynı işi istedi ve router'lar
birbirini ithal edemez. `FileResponse` yerine neden şablon, neden `no-store`,
neden okuma hatası 500 HTML — üç gerekçe oraya taşındı.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from services import ayar, sablon

router = APIRouter()


@router.get("/")
def index(ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)) -> HTMLResponse:
    """index.html'i sürüm, dil ve sözlük yerine konarak servis eder (services/sablon.py)."""
    return sablon.sayfa(ayarlar, "index.html")
