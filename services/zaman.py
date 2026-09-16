# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kayıt zaman damgası — depoya yazılan her `created_at`ın tek kaynağı.

Ayrı ve küçük: her store işlevi `now=` parametresi alıyor (test edilebilirlik),
değeri üreten yer ise tek olmalı — biçim (`isoformat(timespec="seconds")`)
iki router'da iki kez yazılsaydı bir gün biri mikrosaniye taşırdı ve
`history.json`daki damgalar sıralanamaz olurdu.
"""
from __future__ import annotations

import datetime as _dt


def simdi() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")
