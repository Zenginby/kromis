# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
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
from services import dil, dosya

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


def output_png_path(image_id: str, output_dir: str, *, depo: dosya.Depo | None = None) -> str:
    """history id → output/<id>.png yolu. Geçersiz/bulunamayan id'de HTTPException(404).

    Tek path-traversal guard'ı: id yalnızca basename'e indirilir. Dizin
    çağıranın ayar nesnesinden geliyor (Faz 0 / Adım 4) — bu modül hangi
    depoya baktığını kendisi bilmez, söyleneni okur; VAR MI sorusunu da
    söylenen depoya sorar (Faz 2 / 2: kovada HEAD, yerelde `isfile`).

    PNG'de ÇAKILI ve bu bilinçli: REFERANS okuma yolu (`/api/edit`in
    `source_id`si, logo/afiş bindirmeleri, video için ilk kare) — bir MP4'ü
    referans görsel olarak sağlayıcıya göndermek anlamsız, bir videonun
    id'siyle çağrıldığında 404 doğru cevap. SERVİS yolu (`/output/{filename}`,
    indirme ucu) buranın kardeşi değil artık: Faz 1 / 5'te `depo_medya.dosya_yolu*`
    oldu — kullanıcının `medya` satırını arıyor, uzantıyı `storage.media_path_of`
    ile deniyor (Faz 0'ın `output_media_path`i yalnız diske bakıyordu; dizin
    tek kullanıcınındı).
    """
    safe = os.path.basename(image_id or "")
    path = os.path.join(output_dir, f"{safe}.png")
    if not safe or not (depo or dosya.YEREL).var(path):
        raise HTTPException(status_code=404, detail=i18n.t("err.source_image_missing", dil.aktif()))
    return path


def read_png_file(path: str, *, depo: dosya.Depo | None = None) -> bytes:
    """Referans görselin baytları, söylenen depodan (kovada GET). 10 MB tavanı
    (`MAX_UPLOAD_BYTES`) yüklemede uygulanıyor, depodaki dosya zaten o kapıdan geçmiş
    ya da sağlayıcının ürettiği bir PNG — bellek için yeter (belge §2)."""
    try:
        return (depo or dosya.YEREL).oku(path)
    except dosya.DosyaYok:
        raise HTTPException(status_code=404, detail=i18n.t("err.source_image_missing", dil.aktif()))


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
