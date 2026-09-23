# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sağlayıcı kimlik deposu — `saglayici_kimlikleri`, kullanıcı başına, ŞİFRELİ (Faz 1 / 7).

`azure_client.save_env`/`read_env_values`in DB ikizi: `credentials.env`in
`AD=değer` satırları burada `(kullanici_id, ad)` birincil anahtarlı satırlar.
`ad` bugünkü env adı (`AZURE_IMAGE_API_KEY` …) — envanter `ADLAR`: katalogtan
(`key_env`/`url_env` + `wire_from_env`, `.env.example`in bekçisiyle aynı
küme) artı kataloğa girmemiş üç eski BYOK adı (`ESKI_BYOK`; `POST /api/settings`
onları v0.2.0'dan beri yazıyor, `GET /api/settings` `has_replicate_token`/
`comfyui_url`/`ollama_url` olarak yansıtıyor — düşürmek gövdeyi değiştirirdi).
Bilinmeyen `ad` programlama hatası (`ValueError`), kullanıcı hatası değil:
rota adı katalogdan türetiyor, elden vermiyor.

DEĞER DB'YE GİRMEDEN ŞİFRELENİR (`services/sifre.py`), okunurken çözülür;
bu modül değeri hiçbir yerde LOGLAMAZ ve istisna mesajına koymaz. `pg_dump`
çıktısında yalnız Fernet jetonu var (bekçisi tests/test_sifre.py).

BOŞ = SİL. `save_env`de boş değer dosyada `AD=` olarak kalır ve okuma tarafı
boş dizeyi yapılandırılmamış sayar; burada satır silinir — `oku`nun sözlüğünde
anahtar hiç olmaz, `credstore` zaten `.get(ad, "")` ile okuyor, anlam aynı.

`dondur`: anahtar listesinin ilk anahtarıyla yazılmamış satırları yeniden
şifreler (`MultiFernet.rotate`). Yazım zaten hep güncel anahtarla; bu işlev
operatörün eski anahtarı listeden düşürmeden önce koşturduğu adım.

HER SORGUDA `kullanici_id` — birincil anahtarın ilk yarısı (bekçi
tests/test_galeri_db.py). Bu modül KONUŞMAZ.
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Mapping

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

import catalog
from services import sifre, zaman
from services.tablolar import SaglayiciKimligi

__all__ = ["ADLAR", "ESKI_BYOK", "oku", "yaz", "sil", "dondur"]

# Kataloğa girmemiş eski BYOK alanları (routers/ayarlar.py'deki "katalog
# döngüsünün DIŞINDA" bloğu): adaptörü yok, ama v0.2.0'dan beri kaydediliyor.
ESKI_BYOK: tuple[str, ...] = ("REPLICATE_API_TOKEN", "COMFYUI_URL", "OLLAMA_URL")


def _adlar() -> frozenset[str]:
    adlar = {c.key_env for c in catalog.CREDENTIALS}
    adlar |= {c.url_env for c in catalog.CREDENTIALS if c.url_env}
    adlar |= {m.wire_from_env for m in catalog.CHAT_MODELS if m.wire_from_env}
    return frozenset(adlar | set(ESKI_BYOK))


# Yazılabilir `ad` envanteri — katalog + eski BYOK. Bekçisi tests/test_kimlik_bilgisi_db.py.
ADLAR: frozenset[str] = _adlar()


def _satirlar(db: Session, kullanici_id: uuid.UUID) -> list[SaglayiciKimligi]:
    return list(db.scalars(select(SaglayiciKimligi)
                           .where(SaglayiciKimligi.kullanici_id == kullanici_id)
                           .order_by(SaglayiciKimligi.ad)))


def _satir(db: Session, kullanici_id: uuid.UUID, ad: str) -> SaglayiciKimligi | None:
    return db.scalar(select(SaglayiciKimligi)
                     .where(SaglayiciKimligi.kullanici_id == kullanici_id,
                            SaglayiciKimligi.ad == ad))


def oku(db: Session, kullanici_id: uuid.UUID) -> dict[str, str]:
    """Kullanıcının bütün kimlikleri ÇÖZÜLMÜŞ `{ad: değer}` — `credstore`un beklediği düz sözlük."""
    s = sifre.sifreci()
    return {satir.ad: s.coz(satir.sifreli_deger) for satir in _satirlar(db, kullanici_id)}


def yaz(db: Session, kullanici_id: uuid.UUID, degerler: Mapping[str, str], *,
        now: dt.datetime | None = None) -> None:
    """Verilen adları yazar (varsa ezer), ötekilere dokunmaz; boş değer satırı SİLER.

    `save_env`in "oku → birleştir → yaz" sözleşmesinin satır düzeyindeki hâli:
    dokunulmayan ad dokunulmamış kalır. Değer kırpılmadan saklanır — kırpma
    rotanın işi (`save_env` de kırpmıyordu).
    """
    bilinmeyen = sorted(set(degerler) - ADLAR)
    if bilinmeyen:
        raise ValueError(f"bilinmeyen kimlik adi: {bilinmeyen}")
    if not degerler:
        return
    s = sifre.sifreci()
    an = now if now is not None else zaman.an()
    for ad, deger in degerler.items():
        mevcut = _satir(db, kullanici_id, ad)
        if not deger:
            if mevcut is not None:
                db.delete(mevcut)
            continue
        jeton = s.sifrele(str(deger))
        if mevcut is None:
            db.add(SaglayiciKimligi(kullanici_id=kullanici_id, ad=ad, sifreli_deger=jeton,
                                    anahtar_surumu=s.surum, olusturuldu=an, guncellendi=an))
        else:
            mevcut.sifreli_deger = jeton
            mevcut.anahtar_surumu = s.surum
            mevcut.guncellendi = an
    db.flush()


def sil(db: Session, kullanici_id: uuid.UUID, ad: str) -> bool:
    """Tek adı siler; satır var idiyse True."""
    sonuc = db.execute(delete(SaglayiciKimligi)
                       .where(SaglayiciKimligi.kullanici_id == kullanici_id,
                              SaglayiciKimligi.ad == ad))
    # ORM `Result` tipi `rowcount`u ilan etmiyor (depo_medya'nın aynı notu).
    return int(getattr(sonuc, "rowcount", 0) or 0) > 0


def hepsini_sil(db: Session, kullanici_id: uuid.UUID) -> int:
    """Kullanıcının BÜTÜN sağlayıcı anahtarlarını siler; silinen sayı.

    Hesap silme ANINDA (`routers/hesap.py sil`, Faz 4 / 5, K9) — 7 gün
    BEKLETİLMEZ: BYOK anahtarı kullanıcının başka bir hizmetteki sırrı, bizim
    içeriğimiz değil; hesap kapanır kapanmaz elimizde durması için hiçbir
    gerekçe yok (belge §5 "saglayici_kimlikleri HEMEN silinir"). Kullanıcının
    kendi bağlamında koşar (`sahip` politikası DELETE verir).
    """
    sonuc = db.execute(delete(SaglayiciKimligi).where(SaglayiciKimligi.kullanici_id == kullanici_id))
    return int(getattr(sonuc, "rowcount", 0) or 0)


def dondur(db: Session, kullanici_id: uuid.UUID) -> int:
    """Güncel anahtarla yazılmamış satırları yeniden şifreler; kaç satır döndüğünü söyler.

    `MultiFernet.rotate` düz metni bu sürece açmadan yeni jeton üretir; parmak
    izi (`anahtar_surumu`) ilk anahtarınkine çekilir. `guncellendi` DEĞİŞMEZ:
    kullanıcının değeri değişmedi, yalnız zarfı — sütunun `onupdate=now()`u
    Core `UPDATE`te de ateşlenir, o yüzden mevcut değer SET'e açıkça yazılıyor
    (ORM'de aynı değeri atamak "değişmedi" sayılır ve `onupdate` kazanırdı).
    """
    s = sifre.sifreci()
    sayi = 0
    for satir in _satirlar(db, kullanici_id):
        if s.guncel_mi(satir.anahtar_surumu):
            continue
        db.execute(update(SaglayiciKimligi)
                   .where(SaglayiciKimligi.kullanici_id == kullanici_id,
                          SaglayiciKimligi.ad == satir.ad)
                   .values(sifreli_deger=s.dondur(satir.sifreli_deger),
                           anahtar_surumu=s.surum, guncellendi=satir.guncellendi))
        sayi += 1
    if sayi:
        db.expire_all()
    return sayi
