# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yüklenen ve depodaki görsellerin doğrulama/okuma yolu.

Boyut sınırları da burada: `MAX_UPLOAD_BYTES` hem yüklemenin hem multipart
gövdesinin (`MAX_REQUEST_BYTES`) ölçüsü ve iki ayrı router (üretim, bindirme)
aynı sayıya bakıyor — sayı tek yerde durmalı.
"""
from __future__ import annotations

import io
import os

from fastapi import HTTPException, Request
from PIL import Image

# Ham form değerleri Starlette'in UploadFile'ıdır; fastapi.UploadFile onun ALT
# sınıfı olduğundan isinstance kontrolü taban sınıfa yapılmalı.
from starlette.datastructures import UploadFile as FormUploadFile

import i18n
import storage
from services import dil, yollar

MAX_UPLOAD_BYTES = 10 * 1024 * 1024          # dosya başına
MAX_EDIT_IMAGES = 4                          # ana görsel + en fazla 3 ek referans
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES * MAX_EDIT_IMAGES  # tüm multipart gövdesi
MAX_IMAGE_PIXELS = 50 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def to_png(raw: bytes) -> bytes:
    """Yüklenen görseli doğrula ve PNG'ye yeniden kodla. Geçersizse HTTPException(422).

    Çağıranlar bu işleve MODÜL NİTELİĞİ üzerinden (`gorsel.to_png`) ulaşıyor,
    `from services.gorsel import to_png` ile DEĞİL: testler PIL turunu
    atlamak için burayı yamalıyor (16 yer) ve ada bağlanmış bir kopya yamayı
    görmezdi.
    """
    try:
        Image.open(io.BytesIO(raw)).verify()
        im: Image.Image = Image.open(io.BytesIO(raw))
        if im.width * im.height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=422, detail=i18n.t("err.image_too_large", dil.aktif()))
        im = im.convert("RGBA")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_image", dil.aktif()))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def output_png_path(image_id: str) -> str:
    """history id → output/<id>.png yolu. Geçersiz/bulunamayan id'de HTTPException(404).

    Tek path-traversal guard'ı: id yalnızca basename'e indirilir.
    """
    safe = os.path.basename(image_id or "")
    path = os.path.join(yollar.output_dir(), f"{safe}.png")
    if not safe or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=i18n.t("err.source_image_missing", dil.aktif()))
    return path


def output_media_path(media_id: str) -> str:
    """history id → output/<id>.<uzantı> yolu; bulunamayanda HTTPException(404).

    `output_png_path`in İKİZİ DEĞİL, KARDEŞİ — ve ikisinin ayrı durması
    bilinçli:

      • `output_png_path` REFERANS okuma yolu (`/api/edit`in `source_id`si,
        logo/afiş bindirmeleri, video için ilk kare). Orada PNG olmak bir
        VARSAYIM değil ŞART: bir MP4'ü referans görsel olarak sağlayıcıya
        göndermek anlamsız. O yüzden o işlev PNG'de çakılı KALIYOR ve bir
        videonun id'siyle çağrıldığında 404 vermeye devam ediyor — doğru
        cevap bu.
      • Bu işlev SERVİS yolu (`/output/{filename}` ve indirme ucu), yani
        kullanıcının görmek/indirmek istediği her şey.

    Uzantı DENENİYOR, `history.json` OKUNMUYOR: manifesti okumak her küçük
    resim isteğinde bir dosya kilidi ve tam bir JSON ayrıştırması demekti
    (galeri tek ekranda onlarca istek atıyor). Aramanın KENDİSİ `storage`da
    (`media_path_of`) çünkü silme yolu da aynı soruyu soruyor — iki yerde iki
    döngü, birine tür eklenip ötekinin unutulmasının kapısı olurdu.

    Path-traversal guard'ı `output_png_path`in aynısı: id yalnızca
    basename'e indiriliyor.
    """
    safe = os.path.basename(media_id or "")
    path = storage.media_path_of(safe, yollar.output_dir()) if safe else None
    if path:
        return path
    raise HTTPException(status_code=404, detail=i18n.t("err.source_media_missing", dil.aktif()))


def read_png_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


async def read_upload_png(upload: FormUploadFile) -> bytes:
    """Yüklenen dosyayı boyut sınırıyla okur ve doğrulanmış PNG'ye çevirir.

    Taban sınıf (Starlette) kabul ediyor: `extra_refs` ham formdan Starlette
    nesnesi veriyor, rota parametreleri FastAPI'nin alt sınıfını — ikisi de
    buraya geliyor.
    """
    raw = await upload.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.file_too_big", dil.aktif()))
    return to_png(raw)


def png_dimensions(data: bytes) -> str:
    """PNG baytlarından `"GENİŞLİKxYÜKSEKLİK"`. Üretimde bu alan Azure'ın boyut
    dizesi; içe aktarmada uydurulacak bir değer yok, gerçek çözünürlük yazılır."""
    with Image.open(io.BytesIO(data)) as im:
        return f"{im.width}x{im.height}"


async def extra_refs(request: Request) -> tuple[list[FormUploadFile], list[str]]:
    """Ek referansları form verisinden okur: (yüklemeler, galeri id'leri).

    Declared parametre yerine ham form kullanılır: Starlette dosya adı olmayan
    bir parçayı UploadFile değil düz str olarak çözdüğü için `list[UploadFile]`
    annotation'ı iyi niyetli bir boş parçayı 422'ye düşürürdü. FastAPI formu bu
    noktada zaten ayrıştırıp request üzerinde önbelleklemiş olur — ikinci bir
    gövde okuması yapılmaz.
    """
    form = await request.form()
    uploads = [v for v in form.getlist("extra_files")
               if isinstance(v, FormUploadFile) and (v.filename or "").strip()]
    ids = [v for v in form.getlist("extra_source_ids")
           if isinstance(v, str) and v.strip()]
    return uploads, ids
