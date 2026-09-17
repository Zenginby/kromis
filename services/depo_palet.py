# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Palet deposu — `paletler` tablosu (Faz 1 / 6. görev).

`palette_store.py`nin DB ikizi (`create/list_palettes/delete` + `saved_palette`in
aradığı `bul`), imzada `output_dir` yerine `(db, kullanici_id)`. Eski modül
dondurulmuş kabuk ve içe aktarma aracı için duruyor; `_SAFE_ID` oradan.

`colors` JSONB ve DONDURULMUŞ: kayıt anında çözülen adlar bir daha
hesaplanmaz — thecolorapi bir rengi yeniden adlandırsa da yeniden seçilen
palet kaydedildiği günkü prompt'u üretir (`palette_store.py`nin disiplini;
bekçisi tests/test_palette_route.py "frozen names"). Tarif (`palette.harmony`)
değişse geçmiş yeniden yazılmaz. Liste öğelerinin sırası korunur; sözlük
anahtarlarının sırası JSONB'nin (bkz. services/depo_sohbet.py).

HER SORGUDA `kullanici_id` — gerekçe services/depo_medya.py. Sıra `olusturuldu
DESC` (en yeni başta, `palette_store.list_palettes`in `reversed`i).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from palette_store import _SAFE_ID
from services import zaman
from services.tablolar import Palet

__all__ = ["olustur", "listele", "bul", "sil"]


def _json(p: Palet) -> dict:
    """Satır → `palettes.json` kaydı; anahtar sırası `palette_store.create` ile birebir."""
    return {"id": p.id, "name": p.name, "seed": p.seed, "mode": p.mode,
            "strength": p.strength, "colors": p.colors,
            "created_at": zaman.damga(p.olusturuldu)}


def _gecerli(kimlik: str | None) -> bool:
    if not kimlik:
        return False
    return _SAFE_ID.fullmatch(kimlik) is not None


def _sahibin(kullanici_id: uuid.UUID):
    return select(Palet).where(Palet.kullanici_id == kullanici_id)


def olustur(db: Session, kullanici_id: uuid.UUID, name: str, seed: str, mode: str,
            strength: str, colors: list[dict], *, now: dt.datetime | None = None) -> dict:
    """Yeni palet. `colors`: `[{"hex", "name"}, …]`, olduğu gibi dondurulur; `strength` da saklanır."""
    p = Palet(id=uuid.uuid4().hex, kullanici_id=kullanici_id, name=name, seed=seed,
              mode=mode, strength=strength, colors=colors,
              olusturuldu=now if now is not None else zaman.an())
    db.add(p)
    db.flush()
    return _json(p)


def listele(db: Session, kullanici_id: uuid.UUID) -> list[dict]:
    """En yeni palet başta."""
    return [_json(p) for p in db.scalars(_sahibin(kullanici_id).order_by(Palet.olusturuldu.desc()))]


def bul(db: Session, kullanici_id: uuid.UUID, palette_id: str | None) -> dict | None:
    """Tek kayıt (üretim yolunun `saved_palette`i); yok/başkasının/geçersiz id ise None."""
    if not _gecerli(palette_id):
        return None
    p = db.scalar(_sahibin(kullanici_id).where(Palet.id == palette_id))
    return _json(p) if p is not None else None


def sil(db: Session, kullanici_id: uuid.UUID, palette_id: str | None) -> bool:
    """Paleti siler; yok/başkasının/geçersiz id ise False."""
    if not _gecerli(palette_id):
        return False
    sonuc = db.execute(delete(Palet).where(Palet.kullanici_id == kullanici_id,
                                           Palet.id == palette_id))
    return int(getattr(sonuc, "rowcount", 0) or 0) > 0
