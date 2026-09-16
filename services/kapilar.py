# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İstekle gelen kimliklerin (klasör, oturum, arena, varlık türü) kapıları.

Hepsi aynı sözleşmeyi paylaşıyor: boş/None → "yok" (None), dolu → doğrula,
geçersizse HTTPException. Hangi kapının VARLIK, hangisinin yalnız BİÇİM
denetlediği her işlevin başında yazılı — ayrım bilinçli ve gerekçeli.
"""
from __future__ import annotations

from fastapi import HTTPException

import assets_store
import chat_store
import folders
import i18n
import storage
from services import dil


def check_folder(folder_id: str | None, output_dir: str) -> str | None:
    """Boş/None ise kök (None). Doluysa klasörün var olduğunu doğrular, yoksa 404.

    `output_dir` ÇAĞIRANDAN geliyor (rotanın `Depends(ayar.ayarlar)`ı): bu
    kapı VARLIK soruyor, yani diske bakıyor ve hangi diske bakacağını rotanın
    ayarları söyler — süreç geneli bir okuma kapısı değil (Faz 0 / Adım 4).
    """
    if not folder_id:
        return None
    if not folders.exists(folder_id, output_dir):
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
