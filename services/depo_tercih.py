# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Tercih deposu — `tercihler` tablosu, kullanıcı başına TEK satır (Faz 1 / 6. görev).

`prefs.py`nin DB ikizi: `read/read_stored/update` ↔ `oku/kayitli/guncelle`,
imzada `output_dir` yerine `(db, kullanici_id)`. ŞEMA KOPYALANMADI: `_SCHEMA`
(ad → varsayılan, tür) ve `_ENUMS` (değer kümeleri, `models.ALLOWED_*` ve
katalog) `prefs`ten ithal — iki liste ayrışsaydı `GET /api/prefs`in anahtar
kümesi/sırası dondurulmuş kabuktan sessizce koparak ön yüzü bölerdi;
`tests/test_prefs_route.py` `PrefsRequest ⊇ _SCHEMA` bekçisini aynı kaynakla
tutuyor. `prefs.py` dondurulmuş kabuk ve içe aktarma için duruyor.

NULL = "HİÇ YAZILMAMIŞ" (services/tablolar.py'nin gerekçesi): `kayitli`
yalnız NULL olmayan VE geçerli değerleri döndürür, `oku` üstüne varsayılanı
doldurur — `read()`/`read_stored()` ayrımı sütun düzeyinde. Geçerlilik kapısı
`read_stored`unkiyle aynı: model/sağlayıcı sütunları CHECK'siz (katalog her
sürümde değişiyor), yani bayat bir `image_model` DB'de durabilir ve okunurken
varsayılana düşer; satır düzeltilmez, sonraki `guncelle` düzeltir.

`guncelle` KATI: bilinmeyen anahtar, yanlış tür, küme dışı değer ve
`chat_model`in sağlayıcıyla uyumsuzluğu (çapraz kural, birleşik görünüm
üzerinden — `prefs.update`in gerekçesi) `GecersizTercih` fırlatır. Depo
KONUŞMAZ: istisna i18n ANAHTARINI ve alanlarını taşır, cümleyi rota kurar
(`services/hesap.py` ve `depo_klasor` ile aynı karar). Verilen anahtarlar
yazılır, ÖTEKİLER KORUNUR (satır varsa `UPDATE`, yoksa `INSERT`); boş
istek satıra dokunmaz.

HER SORGUDA `kullanici_id` — burada aynı zamanda birincil anahtar.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import catalog
from prefs import _ENUMS, _SCHEMA
from services import zaman
from services.tablolar import Tercih

__all__ = ["oku", "kayitli", "guncelle", "GecersizTercih"]


class GecersizTercih(ValueError):
    """`guncelle`nin reddi: `kod` bir i18n anahtarı, `alanlar` onun yer tutucuları."""

    def __init__(self, kod: str, **alanlar: Any) -> None:
        super().__init__(kod)
        self.kod = kod
        self.alanlar = alanlar


def _satir(db: Session, kullanici_id: uuid.UUID) -> Tercih | None:
    return db.scalar(select(Tercih).where(Tercih.kullanici_id == kullanici_id))


def kayitli(db: Session, kullanici_id: uuid.UUID) -> dict:
    """Yalnız AÇIKÇA yazılmış (NULL olmayan) ve geçerli tercihler; varsayılan DOLDURULMAZ."""
    t = _satir(db, kullanici_id)
    if t is None:
        return {}
    sonuc: dict = {}
    for ad, (_, tur) in _SCHEMA.items():
        deger = getattr(t, ad)
        if deger is None or not isinstance(deger, tur):
            continue
        izinli = _ENUMS.get(ad)
        if izinli is not None and deger not in izinli:
            continue
        sonuc[ad] = deger
    return sonuc


def oku(db: Session, kullanici_id: uuid.UUID) -> dict:
    """Birleşik görünüm (`GET /api/prefs`): `_SCHEMA` sırasında, eksikler varsayılanla."""
    k = kayitli(db, kullanici_id)
    return {ad: k.get(ad, varsayilan) for ad, (varsayilan, _) in _SCHEMA.items()}


def guncelle(db: Session, kullanici_id: uuid.UUID, degerler: dict, *,
             now: dt.datetime | None = None) -> dict:
    """Verilen tercihleri yazar, ötekileri korur; birleşik görünümü döndürür. Reddi `GecersizTercih`."""
    for ad, deger in degerler.items():
        if ad not in _SCHEMA:
            raise GecersizTercih("err.unknown_pref", ad=ad)
        if not isinstance(deger, _SCHEMA[ad][1]):
            raise GecersizTercih("err.bad_pref_type", ad=ad)
        izinli = _ENUMS.get(ad)
        if izinli is not None and deger not in izinli:
            raise GecersizTercih("err.bad_pref_value", ad=ad, deger=deger)
    if degerler.get("chat_model"):
        saglayici = degerler.get("chat_provider") or oku(db, kullanici_id)["chat_provider"]
        if degerler["chat_model"] not in [m.id for m in catalog.chat_models_for(saglayici)]:
            raise GecersizTercih("err.bad_pref_chat_model",
                                 model=degerler["chat_model"], saglayici=saglayici)
    if not degerler:
        return oku(db, kullanici_id)
    an = now if now is not None else zaman.an()
    t = _satir(db, kullanici_id)
    if t is None:
        t = Tercih(kullanici_id=kullanici_id, olusturuldu=an, guncellendi=an, **degerler)
        db.add(t)
    else:
        for ad, deger in degerler.items():
            setattr(t, ad, deger)
        t.guncellendi = an
    db.flush()
    return oku(db, kullanici_id)
