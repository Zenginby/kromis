# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kayıt zaman damgası — depoya yazılan her `created_at`ın tek kaynağı.

Ayrı ve küçük: her store işlevi `now=` parametresi alıyor (test edilebilirlik),
değeri üreten yer ise tek olmalı — biçim (`isoformat(timespec="seconds")`)
iki router'da iki kez yazılsaydı bir gün biri mikrosaniye taşırdı ve
`history.json`daki damgalar sıralanamaz olurdu.

İKİ BİÇİM, TEK KAYNAK (Faz 1 / 5): JSON depolar `simdi()`nin saniye
çözünürlüklü, saat dilimsiz yerel dizesini yazıyor; DB depoları
(`services/depo_medya.py`, `depo_klasor.py`) `timestamptz` sütununa `an()`ın
saat dilimli, MİKROSANİYELİ anını yazıyor ve dışarıya `damga()` ile yine
`simdi()` biçiminde döküyor. Mikrosaniye DB'de ŞART: `/api/generate` n=4'te
dört satırı aynı saniyede yazıyor ve galeri "en yeni üstte", arena "üretim
sırasında" istiyor — saniyeye kırpılmış bir damga bu sırayı kaybederdi.
Postgres'in `now()`u da olmazdı: transaksiyonun başlangıç anı, dört satırda
aynı. `damga()` yerel saate çevirip diliminden soyar, yani `created_at`
istemcinin bugüne kadar gördüğü dizeyle birebir aynı biçimde kalır
(`static/folders.js` bu dizeyi `localeCompare` ile sıralıyor).
"""
from __future__ import annotations

import datetime as _dt


def simdi() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def an() -> _dt.datetime:
    """Şu an, saat dilimli (yerel) ve mikrosaniyeli — DB depolarının `olusturuldu`su."""
    return _dt.datetime.now().astimezone()


def damga(t: _dt.datetime) -> str:
    """Saat dilimli bir anı `simdi()` biçimine döker (yerel saat, saniye, dilimsiz).

    Dilimsiz (naive) gelen bir değer yerel saat sayılır — `simdi()`nin yazdığı
    şey zaten o. Böylece `damga(an())` ile `simdi()` aynı saniyede aynı dize.
    """
    if t.tzinfo is not None:
        t = t.astimezone()
    return t.replace(tzinfo=None).isoformat(timespec="seconds")
