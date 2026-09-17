# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Varlık deposu — `varliklar` tablosu + kullanıcının `assets_dir`i (Faz 1 / 6. görev).

`assets_store.py`nin DB ikizi: `save_asset/list_assets/asset_path/delete_asset`
↔ `kaydet/listele/dosya_yolu/sil`; üç manifest (`assets/<tur>/index.json`) tek
tablo, `tur` sütunu `assets_store.KINDS`ten (`CHECK`). Dosya yerleşimi AYNI:
`<assets_dir>/<tur>/<id>.png` — bindirme (`composite`) ve `/assets/{kind}/
{filename}` yolu dosyayı buradan okuyor. `assets_store.migrate_legacy_uploads`
web yolunda ÇAĞRILMAZ: ölü `uploads` türünü içe aktarma aracı (8. görev)
taşır; burada o türün satırı olamaz (CHECK).

HER SORGUDA `kullanici_id` — gerekçe services/depo_medya.py. Başkasının varlığı
"yok" (rota 404). Geçersiz `tur` da "yok": kapı rotada (`kapilar.check_asset_kind`,
404), depo konuşmaz ve DB'ye geçersiz türle hiç gitmez.

DOSYA + SATIR ATOMİK DEĞİL, `depo_medya` ile aynı sıra ve aynı gerekçe: önce
dosya sonra satır (`kaydet`), silmede önce satır sonra dosya. `asset_path`in
"yalnız diske bak" kuralı DEĞİŞTİ: servis ve bindirme yolu artık satır VE
dosya ister (`dosya_yolu`), satırı silinmiş bir dosya sunulmaz — 5. görevin
`/output/{filename}` kararının aynısı. `assets_store.delete_asset`in "kaydı
olmayan dosya da silinmiş sayılır" sözleşmesi korunuyor.

DOSYANIN YERİ BİR `Depo` (Faz 2 / 2): `depo=` parametresi `depo_medya`nınkiyle
aynı sözleşme — rota söyler (yerel disk ya da kova), söylemeyen `dosya.YEREL`e
düşer; `assets_dir` yolun öneki, sıra nesne → satır → `flush`.
"""
from __future__ import annotations

import datetime as dt
import os
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from assets_store import _SAFE_ID, KINDS
from services import dosya, zaman
from services.tablolar import Varlik

__all__ = ["kaydet", "listele", "dosya_yolu", "dosya_yolu_adiyla", "sil", "KINDS"]


def _json(v: Varlik) -> dict:
    """Satır → `index.json` kaydı; anahtar sırası `assets_store.save_asset` ile birebir (`tur` → `kind`)."""
    return {"id": v.id, "filename": v.filename, "name": v.name, "kind": v.tur,
            "created_at": zaman.damga(v.olusturuldu)}


def _gecerli(kimlik: str | None) -> bool:
    if not kimlik:
        return False
    return _SAFE_ID.fullmatch(kimlik) is not None


def _sahibin(kullanici_id: uuid.UUID):
    return select(Varlik).where(Varlik.kullanici_id == kullanici_id)


def kaydet(db: Session, kullanici_id: uuid.UUID, tur: str, veri: bytes, name: str,
           assets_dir: str, *, now: dt.datetime | None = None,
           depo: dosya.Depo | None = None) -> dict:
    """PNG'yi `<assets_dir>/<tur>/<id>.png`e yazar, satırı ekler; `index.json` kaydını döndürür.

    `tur` çağıran tarafından doğrulanmış olmalı (rota 404 verir); yine de
    `ValueError` — CHECK'e çarpmadan, dosya yazılmadan önce dursun.
    """
    if tur not in KINDS:
        raise ValueError(tur)
    kimlik = uuid.uuid4().hex
    filename = f"{kimlik}.png"
    (depo or dosya.YEREL).yaz(os.path.join(assets_dir, tur, filename), veri, "image/png")
    v = Varlik(id=kimlik, kullanici_id=kullanici_id, filename=filename, name=name, tur=tur,
               olusturuldu=now if now is not None else zaman.an())
    db.add(v)
    db.flush()
    return _json(v)


def listele(db: Session, kullanici_id: uuid.UUID, tur: str | None = None) -> list[dict]:
    """Bir türün (ya da `None` ile hepsinin) varlıkları, en yeni başta (`GET /api/assets/{kind}`)."""
    sorgu = _sahibin(kullanici_id)
    if tur is not None:
        if tur not in KINDS:
            return []
        sorgu = sorgu.where(Varlik.tur == tur)
    return [_json(v) for v in db.scalars(sorgu.order_by(Varlik.olusturuldu.desc()))]


def _satir(db: Session, kullanici_id: uuid.UUID, tur: str, asset_id: str | None) -> Varlik | None:
    if tur not in KINDS or not _gecerli(asset_id):
        return None
    return db.scalar(_sahibin(kullanici_id).where(Varlik.tur == tur, Varlik.id == asset_id))


def _dosya(assets_dir: str, tur: str, filename: str, depo: dosya.Depo | None) -> str | None:
    yol = os.path.join(assets_dir, tur, filename)
    return yol if (depo or dosya.YEREL).var(yol) else None


def dosya_yolu(db: Session, kullanici_id: uuid.UUID, tur: str, asset_id: str | None,
               assets_dir: str, *, depo: dosya.Depo | None = None) -> str | None:
    """BİNDİRME yolu: kullanıcının satırı VE depodaki dosya; biri yoksa None."""
    v = _satir(db, kullanici_id, tur, asset_id)
    if v is None:
        return None
    return _dosya(assets_dir, tur, v.filename, depo)


def dosya_yolu_adiyla(db: Session, kullanici_id: uuid.UUID, tur: str, filename: str,
                      assets_dir: str, *, depo: dosya.Depo | None = None) -> str | None:
    """SERVİS yolu (`/assets/{kind}/{filename}`): dosya adı kullanıcının satırında mı, dosya duruyor mu."""
    if tur not in KINDS or not filename:
        return None
    var = db.scalar(select(Varlik.id).where(Varlik.kullanici_id == kullanici_id,
                                            Varlik.tur == tur, Varlik.filename == filename))
    if var is None:
        return None
    return _dosya(assets_dir, tur, filename, depo)


def sil(db: Session, kullanici_id: uuid.UUID, tur: str, asset_id: str | None,
        assets_dir: str, *, depo: dosya.Depo | None = None) -> bool:
    """Satır + dosya; ikisinden biri vardıysa True (`assets_store.delete_asset` sözleşmesi)."""
    if tur not in KINDS or not _gecerli(asset_id):
        return False
    sonuc = db.execute(delete(Varlik).where(Varlik.kullanici_id == kullanici_id,
                                            Varlik.tur == tur, Varlik.id == asset_id))
    satir_vardi = int(getattr(sonuc, "rowcount", 0) or 0) > 0
    dosya_vardi = (depo or dosya.YEREL).sil(os.path.join(assets_dir, tur, f"{asset_id}.png"))
    return satir_vardi or dosya_vardi
