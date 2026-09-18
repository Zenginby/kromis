# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İstekle gelen kimliklerin (klasör, oturum, arena, varlık türü) kapıları.

Hepsi aynı sözleşmeyi paylaşıyor: boş/None → "yok" (None), dolu → doğrula,
geçersizse HTTPException. Hangi kapının VARLIK, hangisinin yalnız BİÇİM
denetlediği her işlevin başında yazılı — ayrım bilinçli ve gerekçeli.

Beşinci kapı başka türden (Faz 2 / 4): `check_is_tavani` bir kimlik değil
bir SAYI denetler — kullanıcının aynı anda sırada/işçide tutabileceği iş
sayısı. Rotalar sağlayıcıyı çağırmayı bıraktı ve 202 ile döndü; sınırsız
sıraya yazma, tek kullanıcının kuyruğu (ve platform parasını, 6. görev)
tek başına doldurması demekti.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Mapping

from fastapi import HTTPException
from sqlalchemy.orm import Session

import assets_store
import chat_store
import i18n
import storage
from services import depo_klasor, dil, kuyruk

# Kullanıcı başına eş zamanlı (`bekliyor` + `calisiyor`) iş tavanı — `.env.example`
# aynı adı buradan okur (bekçisi tests/test_docker_kapisi.py `ALTYAPI`).
# 4, çünkü arena turu istemci fan-out'uyla 2-4 AYRI istek (core.js `runArena`) ve
# dördüncü sütunun 429 yemesi turu "3/4" diye bitirirdi. Küresel işçi kapasitesi
# ayrı bir kapı (`KROMIS_ISCI_ES_ZAMANLI` × işçi sayısı, services/isci.py).
ES_ZAMANLI_IS_ENV = "KROMIS_KULLANICI_ES_ZAMANLI_IS"
ES_ZAMANLI_IS_VARSAYILAN = 4
# 429'un `Retry-After`ı (sn), belge §4'ün sayısı: sağlayıcı çağrısı saniyelerle
# değil dakikalarla ölçülüyor, daha sık gelen bir yeniden deneme aynı cevabı
# alırdı; istemci (core.js) bunu bir ipucu olarak okur, uyumak zorunda değil.
RETRY_AFTER_SN = 30


def check_folder(folder_id: str | None, db: Session, kullanici_id: uuid.UUID) -> str | None:
    """Boş/None ise kök (None). Doluysa klasörün BU KULLANICININ olduğunu doğrular, yoksa 404.

    `(db, kullanici_id)` ÇAĞIRANDAN geliyor (rotanın `OTURUM`u ve kapının
    çözdüğü kullanıcı): bu kapı VARLIK soruyor, yani depoya bakıyor ve hangi
    kullanıcının klasörlerine bakacağını rota söyler — süreç geneli bir okuma
    kapısı değil (Faz 0 / 4; Faz 1 / 5'te `output_dir` → `klasorler` satırı).
    Başkasının klasörü "yok" sayılır: 403 id uzayını sızdırırdı.
    """
    if not folder_id:
        return None
    if not depo_klasor.var_mi(db, kullanici_id, folder_id):
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    return folder_id


def check_session(session_id: str | None) -> str | None:
    """Boş/None ise oturum dışı üretim (None). Doluysa BİÇİMİ doğrular, 422.

    `check_folder`'ın aksine VARLIK kapısı yok — bilerek. Konsaydı, oturum kaydı
    diske yazılmadan önce (otomatik kayıt kapalıyken hiç yazılmıyor) ya da oturum
    başka bir sekmede silindikten sonra yapılan üretim 422 ile düşerdi: pahalı bir
    Azure turu bir ETİKET yüzünden kaybedilirdi. Ters yön de zaten hoşgörülü —
    silinmiş görselin dökümde bıraktığı sarkan id kaydı çökertmiyor (tasarım §5),
    simetrik duruş tutarlı olan.

    Sessizce düşürmek seçenek değil: kullanıcı üretimini oturumda göremez ve
    sebebi hiçbir yerde görünmezdi.
    """
    if not session_id:
        return None
    if not chat_store.valid_id(session_id):
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_session_id", dil.aktif()))
    return session_id


def check_arena(arena_id: str | None) -> str | None:
    """Boş/None ise arena değil (None). Doluysa BİÇİMİ doğrular, 422.

    `check_session` ile aynı duruş: VARLIK kapısı yok (turun ilk isteği
    yazıldığında ortada henüz başka kayıt yoktur), yalnız biçim. Biçim kapısı
    ise zorunlu — geçersiz bir id depoda sessizce düşerdi ve turun sütunları
    birbirini hiç bulamazdı.
    """
    if not arena_id:
        return None
    if not storage.valid_id(arena_id):
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_arena_id", dil.aktif()))
    return arena_id


def check_asset_kind(kind: str, *, allow_all: bool = False) -> None:
    if allow_all and kind == "all":
        return
    if kind not in assets_store.KINDS:
        raise HTTPException(status_code=404, detail=i18n.t("err.unknown_kind", dil.aktif()))


def es_zamanli_is_tavani(ortam: Mapping[str, str] | None = None) -> int:
    """`KROMIS_KULLANICI_ES_ZAMANLI_IS`; boşsa 4. Bozuk değer YÜKSEK SESLE: sessizce 4'e
    düşen bir tavan, operatörün "10 yaptım" sanmasıyla biterdi."""
    ham = ((os.environ if ortam is None else ortam).get(ES_ZAMANLI_IS_ENV) or "").strip()
    if not ham:
        return ES_ZAMANLI_IS_VARSAYILAN
    try:
        deger = int(ham)
    except ValueError as e:
        raise ValueError(f"{ES_ZAMANLI_IS_ENV} tam sayi olmali, verilen: {ham!r}") from e
    if deger < 1:
        raise ValueError(f"{ES_ZAMANLI_IS_ENV} en az 1 olmali, verilen: {deger}")
    return deger


def check_is_tavani(db: Session, kullanici_id: uuid.UUID) -> None:
    """Kullanıcının aktif işi tavana ulaşmışsa 429 + `Retry-After`; değilse sessiz.

    Sayım `kuyruk.aktif_sayisi` (`bekliyor` + `calisiyor`): bitmiş/düşmüş/iptal
    işler sayılmaz — geçmiş bir ceza değil, o anki yük. Kapı doğrulamanın
    SONUNDA ve girdi nesnesi yazılmadan ÖNCE koşar: 422 alacak bir istek 429
    ile maskelenmesin, 429 alacak bir istek depoya nesne bırakmasın. Her
    istekte ortamı yeniden okur (süreç başına bir kez okumak testte
    yamalanamazdı; bir `os.environ.get` ölçülecek bedel değil).
    """
    tavan = es_zamanli_is_tavani()
    if kuyruk.aktif_sayisi(db, kullanici_id) >= tavan:
        raise HTTPException(status_code=429,
                            detail=i18n.t("err.is_kuyrugu_dolu", dil.aktif(), tavan=tavan),
                            headers={"Retry-After": str(RETRY_AFTER_SN)})
