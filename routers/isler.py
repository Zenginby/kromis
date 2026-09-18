# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İş uçları: kullanıcının üretim işleri — liste, tekil, iptal (Faz 2 / 4).

Üretim rotaları (routers/uretim.py) 202 ile bir `is` döndürüyor; tarayıcı
sonucu buradan izler (core.js `isiBekle`: 2 sn'de bir `GET /api/isler/{id}`).
5. görev SSE akışını (`GET /api/isler/akis`) ve iş panelini bunun üstüne kurar;
bu üç rota o zaman da durur — yoklama SSE'nin düştüğü yerdeki yedek yol.

ÜÇÜ DE KAPILI (`kimlik.aktif_kullanici`) ve SAHİP SÜZGEÇLİ: her sorgu
`kuyruk`un kullanıcı tarafı imzasından geçer (`(db, kullanici_id, …)`),
başkasının işi "yok" sayılır — 404, 403 değil (id uzayı sızmasın; depo
modüllerinin kararı). Dizin okumazlar: ayar nesnesi almazlar
(tests/test_kimlik.py `DIZINSIZ_KAPILI`).

`istek` DÖKÜLMEZ (`kuyruk._json`): prompt ve girdi anahtarları içeride kalır;
sonuç `sonuc.medya` id listesi, kayıtların kendisi `GET /api/history`den.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import i18n
from services import dil, kimlik, kuyruk
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# Öntanımlı görünümün genişliği: "aktifler + son 50" (belge §4). Aktifler
# ayrı çekilir ki 51. sıraya düşmüş bir `bekliyor` iş listeden kaybolmasın —
# sayıları zaten tavanla sınırlı (kapilar.ES_ZAMANLI_IS_VARSAYILAN).
SON_IS_SAYISI = 50


def _since(ham: str | None) -> dt.datetime | None:
    """`?since=` — `zaman.damga` biçimi (`2026-09-18T12:00:00`, dilimsiz = yerel saat) ya da
    dilimli ISO 8601. Bozuksa 422: sessizce "hepsi"ni döndürmek istemciye
    yanlış bir "değişen yok / hepsi değişti" resmi çizerdi."""
    if not ham:
        return None
    try:
        an = dt.datetime.fromisoformat(ham)
    except ValueError:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_since", dil.aktif()))
    # Dilimsiz değer `damga`nın yazdığı YEREL saat (services/zaman.py); sorgu
    # `timestamptz` sütunlarla karşılaştırıyor, dilim burada bağlanır.
    return an.astimezone() if an.tzinfo is None else an


@router.get("/api/isler")
def isleri_listele(since: str | None = None, db: Session = OTURUM,
                   kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """`since` yoksa aktifler + son 50 (en yeni üstte); varsa o andan sonra değişenler."""
    an = _since(since)
    isler = kuyruk.listele(db, kullanici.id, since=an, limit=SON_IS_SAYISI)
    if an is None:
        gorunen = {i["id"] for i in isler}
        aktifler = kuyruk.listele(db, kullanici.id, limit=SON_IS_SAYISI,
                                  durumlar=kuyruk.AKTIF_DURUMLAR)
        isler += [i for i in aktifler if i["id"] not in gorunen]
        # `listele` her iki parçayı en yeni üstte veriyor; birleşik liste de öyle kalsın
        # (`olusturuldu` `zaman.damga` biçimi — sözlük sırası, dize sırasıyla aynı).
        isler.sort(key=lambda i: i["olusturuldu"] or "", reverse=True)
    return {"isler": isler}


def _bul(db: Session, kullanici_id: uuid.UUID, is_id: uuid.UUID) -> dict:
    is_ = kuyruk.bul(db, kullanici_id, is_id)
    if is_ is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.is_bulunamadi", dil.aktif()))
    return is_


@router.get("/api/isler/{is_id}")
def is_getir(is_id: uuid.UUID, db: Session = OTURUM,
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Tek iş; `is_id` UUID biçiminde değilse çerçeve 422 verir (yol eşleşmez)."""
    return {"is": _bul(db, kullanici.id, is_id)}


@router.post("/api/isler/{is_id}/iptal")
def is_iptal(is_id: uuid.UUID, db: Session = OTURUM,
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Yalnız `bekliyor` işi iptal eder; başka durumdaki iş 409, olmayan/başkasının işi 404.

    `kuyruk.iptal` tek `UPDATE … WHERE durum='bekliyor'`: işçi aynı anda `al`
    ile satırı kilitlemişse bu ifade onun commit'ini bekler, sonra 0 satır
    görür — yani "çalışıyor" cevabı bir yarışın kaybedilmiş hâli değil,
    Postgres'in satır kilidinin verdiği kesin cevap. Çalışan iş İPTAL EDİLMEZ:
    sağlayıcı çağrısı çoktan gitti ve faturalandı (K8), işçi sonucu yazar.
    """
    if kuyruk.iptal(db, kullanici.id, is_id):
        return {"is": _bul(db, kullanici.id, is_id)}
    is_ = _bul(db, kullanici.id, is_id)      # yoksa 404
    raise HTTPException(status_code=409,
                        detail=i18n.t("err.is_iptal_edilemez", dil.aktif(), durum=is_["durum"]))
