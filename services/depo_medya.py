# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Medya deposu — `medya` tablosu + kullanıcı dizinindeki dosyalar (Faz 1 / 5. görev).

`storage.py`nin DB ikizi: aynı işlev kümesi, aynı JSON dökümü, imzada
`output_dir` yerine `(db, kullanici_id)` — dosya YAZAN/SİLEN işlevler
`output_dir`i ayrıca alır (`ayarlar.output_dir`, kullanıcının kendi dizini).
`storage.py` SİLİNMEDİ ve bilerek: dondurulmuş masaüstü/Android kabuğu onu
okumaya devam ediyor ve `tools/ice_aktar.py` (8. görev) eski `history.json`ı
onunla okuyacak. Saf yardımcıları (`MEDIA_TYPES`, `ext_for`, `media_path_of`,
`media_type_for`, `valid_id`) buradan da kullanılıyor — kopyalanmadı; manifest
okuyan/yazan işlevleri ise web yolunda ÇAĞRILMAZ (bekçisi
tests/test_galeri_db.py, kaynak taraması).

HER SORGUDA `kullanici_id` SÜZGECİ — çok kiracılılık bu fazda UYGULAMA
düzeyinde (belge §2): `id` küresel benzersiz olsa da `WHERE id = :id` tek
başına başka kullanıcının satırını bulur. Bu yüzden her işlev `kullanici_id`yi
imzasında ZORUNLU alır ve her `select/update/delete` onu `WHERE`ine koyar;
bekçi test modülü tarar (tests/test_galeri_db.py). Başkasının kaydı "yok"
sayılır (rota 404), 403 DEĞİL: 403 "böyle bir kayıt var ama senin değil"
demek, yani id uzayını sızdırır.

`jsonstore.lock_for` YOK: "oku → değiştir → yaz" deseni tek `UPDATE … WHERE`
oldu, satır kilidini Postgres tutuyor. `delete_many`nin 500 id sınırı
(`models.MAX_BULK_IDS`) rotanın gövde doğrulamasında aynen duruyor.

DOSYA + SATIR ATOMİK DEĞİL, bilinçli (belge §5): `kaydet` önce dosyayı yazar
sonra satırı ekler — satır (istek sonunda `db.oturum` commit'i) düşerse
dosya artık kalır; 9. görevin artık dosya taraması bunun için. `sil` önce
satırı sonra dosyayı siler: satır gidince dosyaya ulaşan yol kalmıyor.
`storage`ın "kaydı olmayan ama dosyası olan id de silinmiş sayılır" sözleşmesi
korunuyor — dosya kullanıcının KENDİ dizininde aranıyor, yani kimlik kapısı
dizinin kendisi.

ZAMAN: satır `olusturuldu timestamptz` (mikrosaniyeli, `zaman.an()`); JSON
`created_at` `zaman.damga()` ile eski biçimde (gerekçe services/zaman.py).
Sıralama `olusturuldu`dan: liste EN YENİ ÜSTTE (`list_history`in ters
kronolojisi), arena turu ÜRETİM SIRASINDA (sütunlar soldan sağa).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import uuid
from collections.abc import Iterable

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

import catalog
from services import zaman
from services.tablolar import Medya
from storage import _SAFE_ID, ext_for, media_path_of

# `storage.py`den yeniden dışa açılıyor: rotalar MIME'ı ve uzantı kararını hâlâ
# `storage.MEDIA_TYPES`/`media_type_for`dan okuyor (o tablonun yorumu orada).
__all__ = ["kaydet", "listele", "klasorlerde", "klasor_sayilari", "bul", "dosya_yolu",
           "dosya_yolu_adiyla", "klasor_ata", "klasor_ata_coklu", "klasorden_cikar",
           "sil", "sil_coklu", "arena_turu", "arena_kazanani"]


def _json(m: Medya) -> dict:
    """Satır → `history.json` kaydı; anahtar SIRASI ve koşullu alanlar `storage.save` ile birebir.

    Koşullu beş alan (+ `arena_win`) yalnız doluysa yazılır: yokluğun anlamı
    var ("görsel", "oturum dışı", "arena değil", "işaret yok") ve ön yüz ile
    eski-biçim bekçisi (`tests/test_legacy_formats.py`) alan KÜMESİNE bakıyor.
    `model`/`credits` koşulsuz — `storage.save`in gerekçesi aynen.
    """
    kayit: dict = {
        "id": m.id,
        "filename": m.filename,
        "prompt": m.prompt,
        "size": m.size,
        "quality": m.quality,
        "created_at": zaman.damga(m.olusturuldu),
        "parent_id": m.parent_id,
        "folder_id": m.folder_id,
        "palette": m.palette,
        "prompt_sent": m.prompt_sent,
    }
    if m.imported:
        kayit["imported"] = True
    if m.session_id:
        kayit["session_id"] = m.session_id
    if m.arena_id:
        kayit["arena_id"] = m.arena_id
    if m.kind:
        kayit["kind"] = m.kind
    if m.duration:
        kayit["duration"] = m.duration
    kayit["model"] = m.model
    kayit["credits"] = m.credits
    if m.arena_win:
        kayit["arena_win"] = True
    return kayit


def _gecerli(kimlik: str | None) -> bool:
    """`_SAFE_ID` kapısı — geçersiz id DB'ye hiç gitmez (dosya yoluna da)."""
    if not kimlik:
        return False
    return _SAFE_ID.fullmatch(kimlik) is not None


def _etkilenen(sonuc: object) -> int:
    """`UPDATE`/`DELETE` sonucunun satır sayısı; ORM `Result` tipi `rowcount`u ilan etmiyor."""
    return int(getattr(sonuc, "rowcount", 0) or 0)


def kaydet(db: Session, kullanici_id: uuid.UUID, veri: bytes, meta: dict, output_dir: str,
           *, now: dt.datetime | None = None) -> dict:
    """Medyayı kullanıcının dizinine yazar, satırı ekler; `history.json` kaydının aynısını döndürür.

    `meta` → sütun eşlemesi `storage.save`in kurallarıyla birebir (gerekçeleri
    orada, burada yinelenmiyor): uzantı `kind`dan türetilir; `model` alanı
    GÖNDERİLDİYSE değeri onun sözü (boş dize dâhil), gönderilmediyse günün
    varsayılanı; `credits` yoksa 0; koşullu alanlar boşsa NULL.

    Kimlik `uuid4().hex` (32 hane) — belge §2: `_SAFE_ID` 8-32 kabul ediyor,
    içe aktarılan eski kayıtlar 12 haneli kimliklerini korur, yeni satırlar
    tam uuid alır. Dosya adı `{id}{uzantı}`, `filename` UNIQUE.
    """
    an = now if now is not None else zaman.an()
    os.makedirs(output_dir, exist_ok=True)
    kimlik = uuid.uuid4().hex
    filename = f"{kimlik}{ext_for(meta.get('kind'))}"
    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(veri)
    satir = Medya(
        id=kimlik,
        kullanici_id=kullanici_id,
        filename=filename,
        prompt=meta.get("prompt", ""),
        size=meta.get("size", ""),
        quality=meta.get("quality", ""),
        parent_id=meta.get("parent_id"),
        folder_id=meta.get("folder_id"),
        palette=meta.get("palette"),
        prompt_sent=meta.get("prompt_sent"),
        imported=True if meta.get("imported") else None,
        session_id=meta.get("session_id") or None,
        arena_id=meta.get("arena_id") or None,
        kind=meta.get("kind") or None,
        duration=int(meta["duration"]) if meta.get("duration") else None,
        model=(str(meta["model"] or "") if "model" in meta else catalog.DEFAULT_IMAGE_MODEL),
        credits=int(meta.get("credits") or 0),
        olusturuldu=an,
    )
    db.add(satir)
    # `flush`: `filename` UNIQUE ve FK kısıtları burada patlasın — rotaya
    # döndükten sonra commit'te değil (o zaman istemci kaydı almış olurdu).
    db.flush()
    return _json(satir)


def _sahibin(kullanici_id: uuid.UUID):
    return select(Medya).where(Medya.kullanici_id == kullanici_id)


def listele(db: Session, kullanici_id: uuid.UUID, *, folder_id: str | None = None) -> list[dict]:
    """`/api/history`: `folder_id` yoksa yalnız klasörsüzler (kök), varsa o klasörünkiler; en yeni üstte."""
    sorgu = _sahibin(kullanici_id)
    sorgu = sorgu.where(Medya.folder_id == folder_id) if folder_id else sorgu.where(Medya.folder_id.is_(None))
    return [_json(m) for m in db.scalars(sorgu.order_by(Medya.olusturuldu.desc()))]


def klasorlerde(db: Session, kullanici_id: uuid.UUID, folder_ids: Iterable[str]) -> list[dict]:
    """Verilen klasörlerdeki kayıtlar (ZIP dışa aktarma); en yeni üstte."""
    hedefler = [fid for fid in folder_ids if fid]
    if not hedefler:
        return []
    sorgu = _sahibin(kullanici_id).where(Medya.folder_id.in_(hedefler))
    return [_json(m) for m in db.scalars(sorgu.order_by(Medya.olusturuldu.desc()))]


def klasor_sayilari(db: Session, kullanici_id: uuid.UUID) -> dict[str, int]:
    """{klasör id: görsel sayısı} — `GET /api/folders`un `count` sütunu, tek `GROUP BY`."""
    sorgu = (select(Medya.folder_id, func.count())
             .where(Medya.kullanici_id == kullanici_id, Medya.folder_id.is_not(None))
             .group_by(Medya.folder_id))
    return {fid: int(n) for fid, n in db.execute(sorgu)}


def _satir(db: Session, kullanici_id: uuid.UUID, image_id: str) -> Medya | None:
    if not _gecerli(image_id):
        return None
    return db.scalar(_sahibin(kullanici_id).where(Medya.id == image_id))


def bul(db: Session, kullanici_id: uuid.UUID, image_id: str) -> dict | None:
    """Tek kayıt (bindirmelerin devraldığı kaynak meta'sı); yoksa/başkasınınsa None."""
    m = _satir(db, kullanici_id, image_id)
    return _json(m) if m is not None else None


def dosya_yolu(db: Session, kullanici_id: uuid.UUID, image_id: str, output_dir: str) -> str | None:
    """İNDİRME yolu: kullanıcının satırı VE diskte duran dosya; biri yoksa None.

    Uzantı `media_path_of` ile aranıyor (tür kayıttan da okunabilirdi, ama
    silme yolu aynı aramayı yapıyor ve iki döngü birine tür eklenip ötekinin
    unutulmasının kapısı olurdu). Satır ŞART: Faz 0'ın `gorsel.output_media_path`i
    yalnız diske bakıyordu, çünkü dizin tek kullanıcınındı; bugün dizin de
    kullanıcıya özel ama servis yolunun gerçeği DB satırı — satırı silinmiş
    (artık) bir dosya indirilemez.
    """
    m = _satir(db, kullanici_id, image_id)
    if m is None:
        return None
    return media_path_of(m.id, output_dir)


def dosya_yolu_adiyla(db: Session, kullanici_id: uuid.UUID, filename: str,
                      output_dir: str) -> str | None:
    """ÇİZİM yolu (`/output/{filename}`): `filename` sütunu kullanıcının mı, dosya duruyor mu.

    Dosya adı yalnız `basename` olarak gelir (rota indirger); burada ayrıca
    satırın varlığı aranıyor — belge §5: "`/output/{filename}` artık `medya`da
    `filename` sorgular". Her küçük resim bir sorgu; `filename` UNIQUE indeksli.
    """
    if not filename:
        return None
    var = db.scalar(select(Medya.id).where(Medya.kullanici_id == kullanici_id,
                                           Medya.filename == filename))
    if var is None:
        return None
    yol = os.path.join(output_dir, filename)
    return yol if os.path.isfile(yol) else None


def klasor_ata(db: Session, kullanici_id: uuid.UUID, image_id: str, folder_id: str | None) -> bool:
    """Görselin klasörünü değiştirir (None = kök). Dosya taşınmaz; kayıt yoksa/geçersizse False."""
    if not _gecerli(image_id):
        return False
    sonuc = db.execute(update(Medya)
                       .where(Medya.kullanici_id == kullanici_id, Medya.id == image_id)
                       .values(folder_id=folder_id))
    return _etkilenen(sonuc) > 0


def klasor_ata_coklu(db: Session, kullanici_id: uuid.UUID, image_ids: Iterable[str],
                     folder_id: str | None) -> int:
    """Birden çok görseli aynı klasöre taşır; taşınan sayı. Geçersiz/bilinmeyen id sessizce atlanır."""
    hedefler = {iid for iid in image_ids if _gecerli(iid)}
    if not hedefler:
        return 0
    sonuc = db.execute(update(Medya)
                       .where(Medya.kullanici_id == kullanici_id, Medya.id.in_(hedefler))
                       .values(folder_id=folder_id))
    return _etkilenen(sonuc)


def klasorden_cikar(db: Session, kullanici_id: uuid.UUID, folder_ids: Iterable[str]) -> int:
    """Klasörlerdeki kayıtları köke düşürür; etkilenen sayı. Görseller SİLİNMEZ.

    `medya.folder_id` FK'sı `ON DELETE SET NULL` bunu klasör silinince kendisi de
    yapardı; açık `UPDATE` iki şey için: rota `unfiled` sayısını döndürüyor ve
    sayı FK'nın yan etkisinden okunamaz; ayrıca sıra belgede yazılı (önce
    görseller çıkar, sonra klasörler silinir).
    """
    hedefler = {fid for fid in folder_ids if fid}
    if not hedefler:
        return 0
    sonuc = db.execute(update(Medya)
                       .where(Medya.kullanici_id == kullanici_id, Medya.folder_id.in_(hedefler))
                       .values(folder_id=None))
    return _etkilenen(sonuc)


def _dosyayi_sil(image_id: str, output_dir: str) -> bool:
    """Kullanıcının dizinindeki `{id}.{uzantı}` dosyasını siler; vardıysa True."""
    yol = media_path_of(image_id, output_dir)
    if yol is None:
        return False
    # Bulma ile `remove` arasında dosya kaybolabilir (aynı görseli iki sekmeden
    # silmek yeter). Sonuç zaten istenen: dosya yok.
    with contextlib.suppress(FileNotFoundError):
        os.remove(yol)
    return True


def sil(db: Session, kullanici_id: uuid.UUID, image_id: str, output_dir: str) -> bool:
    """Satır + dosya; ikisinden biri vardıysa True (`storage.delete` sözleşmesi)."""
    if not _gecerli(image_id):
        return False
    satir_vardi = _etkilenen(db.execute(delete(Medya)
                                        .where(Medya.kullanici_id == kullanici_id,
                                               Medya.id == image_id))) > 0
    dosya_vardi = _dosyayi_sil(image_id, output_dir)
    return satir_vardi or dosya_vardi


def sil_coklu(db: Session, kullanici_id: uuid.UUID, image_ids: Iterable[str],
              output_dir: str) -> int:
    """Birden çok görseli siler (satırlar tek `DELETE`, dosyalar tek tek); silinen sayı."""
    hedefler = {iid for iid in image_ids if _gecerli(iid)}
    if not hedefler:
        return 0
    silinen = set(db.scalars(delete(Medya)
                             .where(Medya.kullanici_id == kullanici_id, Medya.id.in_(hedefler))
                             .returning(Medya.id)))
    for iid in hedefler:
        if _dosyayi_sil(iid, output_dir):
            silinen.add(iid)
    return len(silinen)


def arena_turu(db: Session, kullanici_id: uuid.UUID, arena_id: str) -> list[dict]:
    """Bir arena turunun kayıtları ÜRETİM SIRASINDA (sütun sırası); bilinmeyen turda boş."""
    if not _gecerli(arena_id):
        return []
    sorgu = _sahibin(kullanici_id).where(Medya.arena_id == arena_id).order_by(Medya.olusturuldu.asc())
    return [_json(m) for m in db.scalars(sorgu)]


def arena_kazanani(db: Session, kullanici_id: uuid.UUID, arena_id: str, image_id: str) -> bool:
    """Turun kazananını işaretler; tur başına TEK kazanan, tek `UPDATE`.

    Kazanana `arena_win = true`, kardeşlerine NULL — aynı ifadede (`CASE`), yani
    arada okuyan bir istemci iki kazanan görmez (`storage.set_arena_winner`in
    tek-yazım gerekçesi). Görsel o turun içinde değilse ya da başkasınınsa
    hiçbir satır değişmez → False. İdempotent.
    """
    if not _gecerli(image_id) or not _gecerli(arena_id):
        return False
    turda = db.scalar(select(func.count()).select_from(Medya)
                      .where(Medya.kullanici_id == kullanici_id, Medya.arena_id == arena_id,
                             Medya.id == image_id))
    if not turda:
        return False
    db.execute(update(Medya)
               .where(Medya.kullanici_id == kullanici_id, Medya.arena_id == arena_id)
               .values(arena_win=(Medya.id == image_id)))
    return True
