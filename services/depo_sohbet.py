# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sohbet deposu — `sohbetler` tablosu (Faz 1 / 6. görev).

`chat_store.py`nin DB ikizi: aynı işlev kümesi (`create/list_chats/get/update/
delete/delete_all`), aynı JSON dökümü, imzada `output_dir` yerine
`(db, kullanici_id)`. `chat_store.py` dondurulmuş kabuk ve `tools/ice_aktar.py`
(8. görev) için duruyor; saf yardımcıları (`valid_id`, `cover_from`) buradan
da kullanılıyor, kopya yok. Manifest okuyan/yazan işlevleri web yolunda
ÇAĞRILMAZ (bekçisi tests/test_galeri_db.py).

HER SORGUDA `kullanici_id` — gerekçe services/depo_medya.py başında. Başkasının
sohbeti "yok" (rota 404), 403 değil.

`mesajlar` JSONB: iki biçimde öğe (`{role, content}` ve `{role:"result",
image_ids, params}`), doğrulama `models.ChatMessage`ta; burada opak bir dizi.
JSONB nesne anahtarlarını KENDİ sırasında saklar — `messages` içindeki
sözlüklerin anahtar sırası yazanın sırası değil; ön yüz ve testler alanları
adıyla okuyor, dizinin SIRASI (döküm sırası) ise korunuyor.

KAPAK türetilir, sütun değil (`chat_store._with_cover`in gerekçesi): dökümün
İLK sonuç kaydının ilk görseli; yoksa anahtar hiç yazılmaz. `list_chats`in
özetinde ise `cover_image_id` her zaman var (`None` olabilir) —
`chat_store._SUMMARY_FIELDS` ile birebir, bekçisi testte.

SIRA: `guncellendi DESC` (en son güncellenen başta — `chat_store.list_chats`in
gerekçesi), eşitlikte `olusturuldu DESC`. Boş güncelleme (`messages` ve
`title` ikisi de None) `guncellendi`ye DOKUNMAZ: panel sıralaması onu
izliyor ve sohbet kullanıcının yapmadığı bir işle başa atlardı.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from chat_store import cover_from, valid_id
from services import zaman
from services.tablolar import Sohbet

__all__ = ["olustur", "listele", "bul", "guncelle", "sil", "hepsini_sil", "OZET_ALANLARI"]

# Kenar panelinin özeti — `chat_store._SUMMARY_FIELDS`in aynısı (bekçi:
# tests/test_sohbet_db.py). Gövde (`messages`) listede TAŞINMAZ.
OZET_ALANLARI: tuple[str, ...] = ("id", "title", "created_at", "updated_at", "cover_image_id")


def _json(s: Sohbet) -> dict:
    """Satır → `chats.json` kaydı; anahtar SIRASI `chat_store.create` ile birebir, kapak koşullu."""
    kayit: dict = {
        "id": s.id,
        "title": s.title,
        "messages": s.mesajlar,
        "created_at": zaman.damga(s.olusturuldu),
        "updated_at": zaman.damga(s.guncellendi),
    }
    kapak = cover_from(s.mesajlar)
    if kapak:
        kayit["cover_image_id"] = kapak
    return kayit


def _ozet(s: Sohbet) -> dict:
    kayit = _json(s)
    return {**{k: kayit.get(k) for k in OZET_ALANLARI},
            "message_count": len(s.mesajlar or [])}


def _sahibin(kullanici_id: uuid.UUID):
    return select(Sohbet).where(Sohbet.kullanici_id == kullanici_id)


def _satir(db: Session, kullanici_id: uuid.UUID, chat_id: str | None) -> Sohbet | None:
    if not valid_id(chat_id):
        return None
    return db.scalar(_sahibin(kullanici_id).where(Sohbet.id == chat_id))


def olustur(db: Session, kullanici_id: uuid.UUID, title: str, messages: list[dict],
            *, now: dt.datetime | None = None) -> dict:
    """Yeni sohbet; `created_at` = `updated_at` = `now`. Kimlik tam `uuid4().hex` (belge §2)."""
    an = now if now is not None else zaman.an()
    s = Sohbet(id=uuid.uuid4().hex, kullanici_id=kullanici_id, title=title,
               mesajlar=messages, olusturuldu=an, guncellendi=an)
    db.add(s)
    db.flush()
    return _json(s)


def listele(db: Session, kullanici_id: uuid.UUID) -> list[dict]:
    """Özetler, EN SON GÜNCELLENEN başta; gövde yok."""
    sorgu = _sahibin(kullanici_id).order_by(Sohbet.guncellendi.desc(), Sohbet.olusturuldu.desc())
    return [_ozet(s) for s in db.scalars(sorgu)]


def hepsi(db: Session, kullanici_id: uuid.UUID) -> list[dict]:
    """BÜTÜN sohbetler GÖVDELERİYLE, en eski üstte — dışa aktarma (Faz 4 / 5, `sohbetler.json`).

    `listele` özet verir (kenar paneli mesajları yüklemesin); KVKK md. 11
    dökümü mesajların kendisini ister — `bul`u N kez çağırmak N sorgu olurdu.
    """
    sorgu = _sahibin(kullanici_id).order_by(Sohbet.olusturuldu, Sohbet.id)
    return [_json(s) for s in db.scalars(sorgu)]


def bul(db: Session, kullanici_id: uuid.UUID, chat_id: str | None) -> dict | None:
    """Tam kayıt (gövdesiyle). Yok, başkasının ya da geçersiz id ise None."""
    s = _satir(db, kullanici_id, chat_id)
    return _json(s) if s is not None else None


def guncelle(db: Session, kullanici_id: uuid.UUID, chat_id: str | None, *,
             messages: list[dict] | None = None, title: str | None = None,
             now: dt.datetime | None = None) -> dict | None:
    """Gövdeyi ve/veya başlığı değiştirir; yeni kaydı döndürür (yoksa None).

    İkisi de verilmediyse satıra DOKUNULMAZ (gerekçe modül başında). Kapak
    dökümden türetildiği için gövde değişince kendiliğinden yeniden hesaplanır;
    yeniden adlandırmada gövde aynı, kapak da aynı.
    """
    s = _satir(db, kullanici_id, chat_id)
    if s is None:
        return None
    if messages is None and title is None:
        return _json(s)
    if messages is not None:
        s.mesajlar = messages
    if title is not None:
        s.title = title
    # Açık atama: ORM `onupdate=now()` Postgres'in transaksiyon anını yazardı,
    # `created_at`/`updated_at` çifti ise Python saatinden (`zaman.an`) geliyor —
    # iki saat ayrışırsa yeni açılmış bir sohbet "güncellenmiş" görünürdü.
    s.guncellendi = now if now is not None else zaman.an()
    db.flush()
    return _json(s)


def sil(db: Session, kullanici_id: uuid.UUID, chat_id: str | None) -> bool:
    """Sohbeti siler; yok/başkasının/geçersiz id ise False."""
    if not valid_id(chat_id):
        return False
    sonuc = db.execute(delete(Sohbet).where(Sohbet.kullanici_id == kullanici_id,
                                            Sohbet.id == chat_id))
    return int(getattr(sonuc, "rowcount", 0) or 0) > 0


def hepsini_sil(db: Session, kullanici_id: uuid.UUID) -> int:
    """Kullanıcının bütün sohbetleri; silinen sayı (karar D1'in güvence b'si)."""
    sonuc = db.execute(delete(Sohbet).where(Sohbet.kullanici_id == kullanici_id))
    return int(getattr(sonuc, "rowcount", 0) or 0)
