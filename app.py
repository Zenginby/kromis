"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import base64
import datetime as _dt
import io
import os
import subprocess
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator
# Ham form değerleri Starlette'in UploadFile'ıdır; fastapi.UploadFile onun ALT
# sınıfı olduğundan isinstance kontrolü taban sınıfa yapılmalı.
from starlette.datastructures import UploadFile as FormUploadFile

import assets_store
import azure_client as ac
import color_names
import folders
import palette
import palette_store
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
COMPOSITE_SCRIPT = os.path.expanduser("~/.config/claude-tools/composite-logo.py")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024          # dosya başına
MAX_EDIT_IMAGES = 4                          # ana görsel + en fazla 3 ek referans
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES * MAX_EDIT_IMAGES  # tüm multipart gövdesi
MAX_IMAGE_PIXELS = 50 * 1024 * 1024
MAX_PROMPT_CHARS = 4000                      # kullanıcı prompt'u + palet eki
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

app = FastAPI(title="GPT-Image Studio")


@app.exception_handler(RequestValidationError)
async def _redact_validation_errors(request: Request, exc: RequestValidationError):
    """Doğrulama hatası gövdesinde API key'i yankılama (FastAPI varsayılanı 'input' döner)."""
    safe = []
    for err in exc.errors():
        err = dict(err)
        if any(str(p) == "api_key" for p in (err.get("loc") or ())):
            err.pop("input", None)
            err.pop("ctx", None)
        safe.append(err)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": safe}))


class GenerateRequest(BaseModel):
    # Bilinmeyen alanı reddet — LogoRequest ile aynı gerekçe (bkz. oradaki
    # yorum). Palet için bu özellikle kritik: eski bir sunucu süreci
    # `palette_hex`'i sessizce yok sayıp 200 ile renksiz görsel döndürürdü ve
    # kullanıcı "palet çalışmıyor" derdi. Artık yüksek sesle 422.
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    size: str
    quality: str
    n: int = Field(ge=1, le=4)
    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)
    # None = palet yok. Palet `(hex, mod)` çiftinin saf fonksiyonu olduğu için
    # tel üzerinde iki skaler yetiyor; sunucunun bir depoya bakması gerekmez.
    palette_hex: str | None = Field(default=None, max_length=7)
    palette_mode: str = "analogic"
    palette_strength: str = "balanced"
    # Kayıtlı palet kullanılıyorsa id'si: adlar kaydın dondurulmuş halinden
    # okunur, böylece gösterilen ad ile prompt'a giden ad hiç ayrışmaz.
    palette_id: str | None = Field(default=None, max_length=64)

    @field_validator("palette_hex")
    @classmethod
    def _palette_hex_ok(cls, v):
        if not v:
            return None
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz palette_hex")

    @field_validator("palette_mode")
    @classmethod
    def _palette_mode_ok(cls, v):
        if v not in palette.MODES:
            raise ValueError("geçersiz palette_mode")
        return v

    @field_validator("palette_strength")
    @classmethod
    def _palette_strength_ok(cls, v):
        if v not in palette.STRENGTHS:
            raise ValueError("geçersiz palette_strength")
        return v

    @field_validator("size")
    @classmethod
    def _size_ok(cls, v):
        if v not in ac.ALLOWED_SIZES:
            raise ValueError("geçersiz size")
        return v

    @field_validator("quality")
    @classmethod
    def _quality_ok(cls, v):
        if v not in ac.ALLOWED_QUALITIES:
            raise ValueError("geçersiz quality")
        return v


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _to_png(raw: bytes) -> bytes:
    """Yüklenen görseli doğrula ve PNG'ye yeniden kodla. Geçersizse HTTPException(422)."""
    try:
        Image.open(io.BytesIO(raw)).verify()
        im = Image.open(io.BytesIO(raw))
        if im.width * im.height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=422, detail="Görsel çözünürlüğü çok yüksek.")
        im = im.convert("RGBA")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Geçersiz görsel dosyası.")
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _output_png_path(image_id: str) -> str:
    """history id → output/<id>.png yolu. Geçersiz/bulunamayan id'de HTTPException(404).

    Tek path-traversal guard'ı: id yalnızca basename'e indirilir.
    """
    safe = os.path.basename(image_id or "")
    path = os.path.join(OUTPUT_DIR, f"{safe}.png")
    if not safe or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Kaynak görsel bulunamadı.")
    return path


def _read_png_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


async def _read_upload_png(upload: UploadFile) -> bytes:
    """Yüklenen dosyayı boyut sınırıyla okur ve doğrulanmış PNG'ye çevirir."""
    raw = await upload.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    return _to_png(raw)


async def _extra_refs(request: Request) -> tuple[list[UploadFile], list[str]]:
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


def _check_folder(folder_id: str | None) -> str | None:
    """Boş/None ise kök (None). Doluysa klasörün var olduğunu doğrular, yoksa 404."""
    if not folder_id:
        return None
    if not folders.exists(folder_id, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Klasör bulunamadı.")
    return folder_id


def _resolve_palette(seed: str, mode: str, *, offline: bool = False) -> list[dict]:
    """`(seed, mod)` → `[{"hex", "name"}]`. offline=True ise ağa ÇIKMAZ.

    Adlar palet içinde tekilleştirilir: aynı ad iki farklı hex'le prompt'a
    girerse model hangisini kullanacağını bilemez (bkz. dedupe_names).
    """
    hexes = palette.harmony(seed, mode)
    names = color_names.names_for(hexes, offline=offline)
    return color_names.dedupe_names(
        [{"hex": h, "name": n} for h, n in zip(hexes, names)])


def _saved_palette(palette_id: str | None) -> dict | None:
    """Kayıtlı paleti id ile bulur; yoksa None (hata DEĞİL — bkz. _palette_prompt)."""
    if not palette_id:
        return None
    pid = os.path.basename(palette_id)
    return next((p for p in palette_store.list_palettes(OUTPUT_DIR)
                 if p.get("id") == pid), None)


def _palette_prompt(prompt: str, seed: str | None, mode: str, strength: str,
                    palette_id: str | None = None, *, task: str) -> tuple[str, dict | None]:
    """Prompt'a renk yönlendirmesi ekler. Palet yoksa prompt aynen döner.

    KAYITLI palet kullanılıyorsa renkler/adlar kaydın DONDURULMUŞ halinden
    okunur. Bu, kullanıcının kütüphanede gördüğü adlarla prompt'a giden adların
    her zaman birebir aynı olmasını garanti eder — yeniden hesaplasaydık
    sunucu yeniden başladıktan sonra (önbellek boş) yerel adlara düşer ve
    "bu palet bana o görseli vermişti" sözü tutulamazdı.

    Kayıt bulunamazsa (silinmiş palet) hata verilmez, `(seed, mode)`'dan
    yeniden hesaplanır: silinmiş bir palet üretimi bloke etmemeli.

    Ad çözümlemesi `offline=True`: üretim yolu thecolorapi'yi ASLA beklemez.
    Arayüz aynı tohum için /api/palette/suggest'i çağırdığından adlar
    önbellekte sıcaktır; değilse gömülü tablo mikrosaniyede yanıt verir.

    Prompt uzunluk sınırı kullanıcının metnini doğruluyor, ek sonradan geldiği
    için birleşik metin 4000'i aşabilir. Bu durumda EK DÜŞÜRÜLÜR, kullanıcının
    metni asla kırpılmaz ve istek reddedilmez: paletin görsel üretimini bloke
    etmesi, renk yönlendirmesinin kaybolmasından kötü.
    """
    if not seed:
        return prompt, None
    saved = _saved_palette(palette_id)
    if saved:
        mode = saved.get("mode", mode)
        seed = saved.get("seed", seed)
        colors = saved.get("colors") or _resolve_palette(seed, mode, offline=True)
    else:
        colors = _resolve_palette(seed, mode, offline=True)
    suffix = palette.prompt_suffix(colors, strength, task=task)
    record = {"seed": seed, "mode": mode, "strength": strength, "colors": colors}
    if saved:
        record["id"] = saved["id"]
        record["name"] = saved.get("name", "")
    if len(prompt) + len(suffix) > MAX_PROMPT_CHARS:
        return prompt, record
    return prompt + suffix, record


@app.post("/api/generate")
def generate(req: GenerateRequest) -> dict:
    folder_id = _check_folder(req.folder_id)
    prompt_sent, pal = _palette_prompt(req.prompt, req.palette_hex, req.palette_mode,
                                       req.palette_strength, req.palette_id,
                                       task="generate")
    try:
        images = ac.generate(prompt_sent, req.size, req.quality, req.n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    records = [
        storage.save(img, {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None,
                           "folder_id": folder_id, "palette": pal,
                           "prompt_sent": prompt_sent if pal else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


@app.post("/api/edit")
async def edit(
    request: Request,
    prompt: str = Form(...),
    size: str = Form(...),
    quality: str = Form(...),
    n: int = Form(...),
    file: UploadFile | None = File(None),
    source_id: str | None = Form(None),
    folder_id: str | None = Form(None),
    palette_hex: str | None = Form(None),
    palette_mode: str = Form("analogic"),
    palette_strength: str = Form("balanced"),
    palette_id: str | None = Form(None),
) -> dict:
    """Ek referans görselleri (`extra_files` yüklemeleri, `extra_source_ids`
    galeri id'leri) form verisinden okunur — bkz. _extra_refs."""
    if size not in ac.ALLOWED_SIZES or quality not in ac.ALLOWED_QUALITIES:
        raise HTTPException(status_code=422, detail="Geçersiz size veya quality.")
    if not (1 <= n <= 4):
        raise HTTPException(status_code=422, detail="n 1-4 arasında olmalı.")
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=422,
                            detail=f"prompt 1-{MAX_PROMPT_CHARS} karakter olmalı.")
    # Bu uçta doğrulama elle yapılıyor (GenerateRequest gibi bir Pydantic modeli
    # yok, bkz. yukarıdaki mevcut kontroller). Not: multipart'ta extra="forbid"
    # karşılığı YOK — Starlette bilinmeyen form alanını sessizce atar. Bayat
    # sunucu tespiti bu yüzden arayüz tarafında yanıtın paleti geri yansıtıp
    # yansıtmadığına bakılarak yapılıyor.
    if palette_mode not in palette.MODES:
        raise HTTPException(status_code=422, detail="Geçersiz palette_mode.")
    if palette_strength not in palette.STRENGTHS:
        raise HTTPException(status_code=422, detail="Geçersiz palette_strength.")
    if palette_hex:
        try:
            palette_hex = palette.parse_hex(palette_hex)
        except ValueError:
            raise HTTPException(status_code=422, detail="Geçersiz palette_hex.")
    else:
        palette_hex = None
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422, detail="Tam olarak biri gerekli: file veya source_id.")

    target_folder = _check_folder(folder_id)

    extra_uploads, extra_ids = await _extra_refs(request)
    if 1 + len(extra_uploads) + len(extra_ids) > MAX_EDIT_IMAGES:
        raise HTTPException(status_code=422,
                            detail=f"En fazla {MAX_EDIT_IMAGES} görsel gönderilebilir "
                                   f"(1 ana + {MAX_EDIT_IMAGES - 1} ek).")

    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="İstek çok büyük.")

    # Azure'a giden sıra: ana görsel → ek yüklemeler → ek galeri görselleri.
    refs: list[tuple[str, bytes]] = []
    if source_id is not None:
        sid = os.path.basename(source_id)
        refs.append((f"{sid}.png", _read_png_file(_output_png_path(sid))))
        parent_id = sid
    else:
        refs.append(("upload.png", await _read_upload_png(file)))
        parent_id = None

    for upload in extra_uploads:
        refs.append((f"ref{len(refs) + 1}.png", await _read_upload_png(upload)))
    for extra_id in extra_ids:
        refs.append((f"ref{len(refs) + 1}.png", _read_png_file(_output_png_path(extra_id))))

    # task="edit": üretim ifadesi modele yeniden boyama söyler ve referans
    # görselin kompozisyonunu yok eder; düzenlemede istenen renk derecelendirmesi.
    prompt_sent, pal = _palette_prompt(prompt, palette_hex, palette_mode,
                                       palette_strength, palette_id, task="edit")
    try:
        images = ac.edit(prompt_sent, refs, size, quality, n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    records = [
        storage.save(img, {"prompt": prompt, "size": size, "quality": quality,
                           "parent_id": parent_id, "folder_id": target_folder,
                           "palette": pal,
                           "prompt_sent": prompt_sent if pal else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


class SettingsRequest(BaseModel):
    # api_key boş bırakılabilir: mevcut key korunur (endpoint'i tek başına güncelleme).
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(min_length=1, max_length=500)


@app.get("/api/settings")
def get_settings() -> dict:
    """Yapılandırma durumu — API key asla dönmez, yalnızca configured + endpoint."""
    return ac.get_settings_status()


@app.post("/api/settings")
def post_settings(req: SettingsRequest) -> dict:
    """Admin kimlik bilgilerini yalnızca-yazılır kaydeder; durumu döndürür (key'siz).

    api_key boşsa mevcut key korunur — ilk kurulumda ise key zorunludur.
    """
    api_key = req.api_key.strip()
    if not api_key:
        try:
            api_key, _ = ac.load_credentials()
        except ac.AzureImageError:
            raise HTTPException(status_code=422, detail="İlk kurulumda API key gerekli.")
    try:
        ac.save_credentials(api_key, req.base_url)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ac.get_settings_status()


class FolderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = Field(default=None, max_length=64)  # None = kök klasör


@app.get("/api/folders")
def list_folders_route() -> dict:
    """Tüm klasörler (düz liste) + görsel ve alt klasör sayıları.

    Hiyerarşi `parent_id` ile taşınır; arayüz şeridi buna göre süzer, böylece
    sayaçlar ve sürükle-bırak hedefleri tek istekte tazelenir.
    """
    counts: dict[str, int] = {}
    for rec in storage.list_history(OUTPUT_DIR):
        fid = rec.get("folder_id")
        if fid:
            counts[fid] = counts.get(fid, 0) + 1
    items = folders.list_folders(OUTPUT_DIR)
    child_counts: dict[str, int] = {}
    for f in items:
        pid = f.get("parent_id")
        if pid:
            child_counts[pid] = child_counts.get(pid, 0) + 1
    return {"items": [{"parent_id": None, **f,
                       "count": counts.get(f["id"], 0),
                       "child_count": child_counts.get(f["id"], 0)}
                      for f in items]}


@app.post("/api/folders")
def create_folder_route(req: FolderRequest) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Klasör adı gerekli.")
    parent_id = _check_folder(req.parent_id)
    return {"folder": folders.create(name, OUTPUT_DIR, parent_id=parent_id, now=_now())}


@app.delete("/api/folders/{folder_id}")
def delete_folder_route(folder_id: str) -> dict:
    """Klasörü ve alt klasörlerini siler; GÖRSELLER silinmez, klasörsüz (kök) hale döner."""
    fid = os.path.basename(folder_id)
    # Sıra önemli: önce ağacı çöz (yoksa 404), sonra görselleri çıkar, sonra kayıtları sil.
    doomed = folders.descendants(fid, OUTPUT_DIR)
    if not doomed:
        raise HTTPException(status_code=404, detail="Klasör bulunamadı.")
    unfiled = storage.unfile_folders(doomed, OUTPUT_DIR)
    deleted = folders.delete_tree(fid, OUTPUT_DIR)
    return {"deleted": deleted, "folders": len(deleted), "unfiled": unfiled}


@app.get("/api/history")
def history(folder_id: str | None = None) -> dict:
    """folder_id yoksa yalnızca klasörsüz görseller (kök), varsa o klasörünkiler."""
    items = storage.list_history(OUTPUT_DIR)
    if folder_id:
        _check_folder(folder_id)
        items = [r for r in items if r.get("folder_id") == folder_id]
    else:
        items = [r for r in items if not r.get("folder_id")]
    return {"images": items}


class MoveImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)


@app.patch("/api/image/{image_id}")
def move_image(image_id: str, req: MoveImageRequest) -> dict:
    """Görseli bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = _check_folder(req.folder_id)
    iid = os.path.basename(image_id)
    if not storage.set_folder(iid, target, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return {"id": iid, "folder_id": target}


@app.delete("/api/image/{image_id}")
def delete_image(image_id: str) -> dict:
    iid = os.path.basename(image_id)
    removed = storage.delete(iid, OUTPUT_DIR)
    if not removed:
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return {"deleted": iid}


# Çoklu seçim uçları: tek istek = tek history.json yazımı. İstemci tarafında
# id başına ayrı istek atılsaydı yazımlar birbirini ezip güncelleme kaybettirirdi.
MAX_BULK_IDS = 500


class BulkImagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(min_length=1, max_length=MAX_BULK_IDS)


class BulkMoveRequest(BulkImagesRequest):
    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)


@app.patch("/api/images")
def move_images(req: BulkMoveRequest) -> dict:
    """Seçili görselleri bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = _check_folder(req.folder_id)
    ids = [os.path.basename(i) for i in req.ids]
    moved = storage.set_folder_many(ids, target, OUTPUT_DIR)
    if not moved:
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return {"moved": moved, "folder_id": target}


@app.delete("/api/images")
def delete_images(req: BulkImagesRequest) -> dict:
    """Seçili görselleri siler (dosya + kayıt)."""
    ids = [os.path.basename(i) for i in req.ids]
    deleted = storage.delete_many(ids, OUTPUT_DIR)
    if not deleted:
        raise HTTPException(status_code=404, detail="Görsel bulunamadı.")
    return {"deleted": deleted}


class SuggestRequest(BaseModel):
    # POST + extra="forbid": query parametreleri bilinmeyen alanı reddedemez,
    # bayat sunucu tespiti bu özellikte en büyük risk olduğu için GET değil.
    model_config = ConfigDict(extra="forbid")

    hex: str = Field(min_length=6, max_length=7)

    @field_validator("hex")
    @classmethod
    def _hex_ok(cls, v):
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz hex")


class SavePaletteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    seed: str = Field(min_length=6, max_length=7)
    mode: str
    strength: str = "balanced"

    @field_validator("seed")
    @classmethod
    def _seed_ok(cls, v):
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz seed")

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v):
        if v not in palette.MODES:
            raise ValueError("geçersiz mode")
        return v

    @field_validator("strength")
    @classmethod
    def _strength_ok(cls, v):
        if v not in palette.STRENGTHS:
            raise ValueError("geçersiz strength")
        return v


@app.post("/api/palette/suggest")
def suggest_palettes(req: SuggestRequest) -> dict:
    """Tohum renkten altı harmoni önerisi. Diske hiçbir şey yazmaz.

    İsimlendirme burada bilinçli olarak ÇEVRİMDIŞI: keşif sırasında 30 rengi
    thecolorapi'ye sormak ölçülen 2.5 sn'lik bir bekleme getiriyor ve kazanç
    marjinal (gömülü tablo "copper orange", "cobalt blue" gibi zaten iyi adlar
    veriyor). Buna karşılık çevrimdışı olması üç şey kazandırıyor: öneriler
    anında gelir, deterministiktir, ve kartta GÖRÜLEN ad ile prompt'a GİDEN ad
    birebir aynı olur (üretim yolu da çevrimdışı).

    thecolorapi kullanıcı paleti KAYDEDERKEN devreye girer: 5 renk, tek bütçe,
    kullanıcı kararını vermiş, ve sonuç kayda dondurulup palette_id ile
    gerçekten prompt'a girer (bkz. create_palette_route, _palette_prompt).
    """
    per_mode = {mode: palette.harmony(req.hex, mode) for mode in palette.MODES}
    resolved = color_names.names_map(
        [h for hexes in per_mode.values() for h in hexes], offline=True)
    return {
        "seed": req.hex,
        "items": [
            {"mode": mode,
             # Tekilleştirme palet BAŞINA yapılır: aynı ad farklı paletlerde
             # geçebilir (sorun değil), ama tek palet içinde geçemez.
             "colors": color_names.dedupe_names(
                 [{"hex": h, "name": resolved[h]} for h in hexes])}
            for mode, hexes in per_mode.items()
        ],
    }


@app.get("/api/palettes")
def list_palettes_route() -> dict:
    return {"items": palette_store.list_palettes(OUTPUT_DIR)}


@app.post("/api/palettes")
def create_palette_route(req: SavePaletteRequest) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Palet adı gerekli.")
    # Renkleri SUNUCU yeniden hesaplar: istemci renk listesi göndermediği için
    # doğrulanacak istemci verisi yok ve tek doğruluk kaynağı korunur.
    #
    # thecolorapi'nin devreye girdiği TEK yer burası: yalnızca 5 renk, tek
    # bütçe, kullanıcı "bunu saklıyorum" demiş. Dönen adlar kayda dondurulur
    # ve palette_id ile prompt'a girer; API sonradan çökse bile bu palet
    # kaydedildiği günkü prompt'u üretmeye devam eder.
    colors = _resolve_palette(req.seed, req.mode, offline=False)
    return {"palette": palette_store.create(name, req.seed, req.mode, req.strength,
                                            colors, OUTPUT_DIR, now=_now())}


@app.delete("/api/palettes/{palette_id}")
def delete_palette_route(palette_id: str) -> dict:
    pid = os.path.basename(palette_id)
    if not palette_store.delete(pid, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Palet bulunamadı.")
    return {"deleted": pid}


LOGO_POSITIONS = {
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
}
LOGO_COLORS = {"auto", "blue", "white"}
# Konumlanabilir (logo tarzı) bindirmenin varlığı hangi kütüphaneden gelebilir.
# Banner ayrı bir yerleşim olduğu için burada değil.
OVERLAY_ASSET_KINDS = {"logos", "mottos"}


class LogoRequest(BaseModel):
    # Bilinmeyen alanı reddet: Pydantic varsayılanı onu SESSİZCE yok sayar, bu yüzden
    # eski bir sunucu süreci yeni arayüzün seçeneklerini görmezden gelip değişmemiş
    # görseli 200 ile döndürür ("ayar çalışmıyor" gibi görünür). Artık 422 + mesaj.
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    # asset_id boş/None => yerleşik KURUM logosu (mavi/beyaz auto). Doluysa
    # asset_kind kütüphanesinden seçilen özel görsel (tek görsel) kullanılır.
    asset_id: str | None = Field(default=None, max_length=64)
    asset_kind: str = "logos"                                # "logos" | "mottos"
    position: str = "bottom-right"
    color: str = "auto"
    size: float = Field(default=0.14, ge=0.04, le=0.5)       # logo genişliği / görsel genişliği
    shadow_alpha: int = Field(default=120, ge=0, le=255)     # 0 = gölge yok
    shadow_blur: int = Field(default=6, ge=0, le=50)

    @field_validator("position")
    @classmethod
    def _position_ok(cls, v):
        if v not in LOGO_POSITIONS:
            raise ValueError("geçersiz position")
        return v

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v):
        if v not in LOGO_COLORS:
            raise ValueError("geçersiz color")
        return v

    @field_validator("asset_kind")
    @classmethod
    def _asset_kind_ok(cls, v):
        if v not in OVERLAY_ASSET_KINDS:
            raise ValueError("geçersiz asset_kind")
        return v


def _composite_logo(src_path: str, req: LogoRequest) -> bytes:
    """composite-logo.py'yi verilen seçeneklerle çalıştırır, sonuç PNG baytlarını döndürür.

    base_image ve output_path ilk iki konumsal argümandır (cmd[2], cmd[3]);
    bayraklar sonradan gelir.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_out = tmp.name
    try:
        cmd = [
            "python3", COMPOSITE_SCRIPT, src_path, tmp_out,
            "--position", req.position,
            "--color", req.color,
            "--scale", str(req.size),
            "--shadow-alpha", str(req.shadow_alpha),
            "--shadow-blur", str(req.shadow_blur),
        ]
        # Özel logo/motto seçildiyse aynı dosyayı her iki varyant olarak geç:
        # renk seçimi (auto/blue/white) hangisine düşerse düşsün tek görsel kullanılır.
        if req.asset_id:
            overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, ASSETS_DIR)
            if overlay_path is None:
                raise HTTPException(status_code=404, detail="görsel bulunamadı")
            cmd += ["--logo-blue", overlay_path, "--logo-white", overlay_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500,
                                detail=f"Logo bindirme başarısız: {result.stderr[:200]}")
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)


def _logo_src_path(image_id: str) -> str:
    return _output_png_path(image_id)


@app.post("/api/logo/preview")
def preview_logo(req: LogoRequest) -> dict:
    """Seçeneklerle geçici bir logo önizlemesi üretir — diske/geçmişe KAYDETMEZ."""
    src_path = _logo_src_path(req.id)
    logo_bytes = _composite_logo(src_path, req)
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@app.post("/api/logo")
def add_logo(req: LogoRequest) -> dict:
    src_path = _logo_src_path(req.id)
    src_id = os.path.basename(req.id)

    # kaynak metadata'sını history'den bul (prompt/size korunur)
    src_meta = next((h for h in storage.list_history(OUTPUT_DIR) if h["id"] == src_id), {})

    logo_bytes = _composite_logo(src_path, req)
    record = storage.save(
        logo_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id,
         # türev, kaynağın klasöründe kalır
         "folder_id": src_meta.get("folder_id"),
         # palet de devralınır: logo bindirince renk şeridi kaybolmasın
         "palette": src_meta.get("palette"),
         "prompt_sent": src_meta.get("prompt_sent")},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


BANNER_EDGES = {"top", "bottom"}
BANNER_ALIGNS = {"left", "center", "right"}


class BannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")             # bkz. LogoRequest'teki gerekçe

    id: str = Field(min_length=1, max_length=64)          # bindirilecek görsel (history id)
    asset_id: str = Field(min_length=1, max_length=64)    # kütüphaneden seçilen banner
    edge: str = "bottom"
    # Varsayılanlar v1.4 davranışını birebir korur: tam genişlik, ortalı, boşluksuz.
    scale: float = Field(default=1.0, ge=0.2, le=1.0)     # banner genişliği / görsel genişliği
    align: str = "center"                                # scale < 1 iken yatay yerleşim
    margin: float = Field(default=0.0, ge=0.0, le=0.2)   # kenardan uzaklık / görsel yüksekliği

    @field_validator("edge")
    @classmethod
    def _edge_ok(cls, v):
        if v not in BANNER_EDGES:
            raise ValueError("geçersiz edge")
        return v

    @field_validator("align")
    @classmethod
    def _align_ok(cls, v):
        if v not in BANNER_ALIGNS:
            raise ValueError("geçersiz align")
        return v


def _composite_banner(src_path: str, banner_path: str, edge: str,
                      scale: float = 1.0, align: str = "center", margin: float = 0.0) -> bytes:
    """Banner'ı ölçekleyip üst/alt kenara bindirir (en-boy oranı korunur).

    Logo filigranından farklı: köşe değil, yatay şerit. `scale` görsel genişliğinin
    oranı (1.0 = tam genişlik), `align` artan boşluğun paylaşımı, `margin` seçilen
    kenardan içeri kayma (görsel yüksekliğinin oranı). Alfa maskesiyle paste;
    banner taşarsa kenardan kırpılır (paste otomatik kırpar).
    """
    base = Image.open(src_path).convert("RGBA")
    banner = Image.open(banner_path).convert("RGBA")
    target_w = max(1, round(base.width * scale))
    target_h = max(1, round(banner.height * (target_w / banner.width)))
    banner = banner.resize((target_w, target_h), Image.LANCZOS)

    free_x = base.width - target_w
    x = 0 if align == "left" else (free_x if align == "right" else free_x // 2)
    pad = round(base.height * margin)
    y = pad if edge == "top" else base.height - target_h - pad
    y = max(0, min(y, max(0, base.height - target_h)))  # kenar dışına taşmayı engelle

    composed = base.copy()
    composed.paste(banner, (x, y), banner)  # banner alfası maske
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def _banner_asset_path(asset_id: str) -> str:
    path = assets_store.asset_path("banners", asset_id, ASSETS_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail="banner bulunamadı")
    return path


def _banner_bytes(src_path: str, req: BannerRequest) -> bytes:
    return _composite_banner(src_path, _banner_asset_path(req.asset_id), req.edge,
                             req.scale, req.align, req.margin)


@app.post("/api/banner/preview")
def preview_banner(req: BannerRequest) -> dict:
    """Banner'lı geçici bir önizleme üretir — diske/geçmişe KAYDETMEZ."""
    banner_bytes = _banner_bytes(_logo_src_path(req.id), req)
    b64 = base64.b64encode(banner_bytes).decode("ascii")
    return {"b64": f"data:image/png;base64,{b64}"}


@app.post("/api/banner")
def add_banner(req: BannerRequest) -> dict:
    src_path = _logo_src_path(req.id)
    src_id = os.path.basename(req.id)

    src_meta = next((h for h in storage.list_history(OUTPUT_DIR) if h["id"] == src_id), {})

    banner_bytes = _banner_bytes(src_path, req)
    record = storage.save(
        banner_bytes,
        {"prompt": src_meta.get("prompt", ""), "size": src_meta.get("size", ""),
         "quality": src_meta.get("quality", ""), "parent_id": src_id,
         "folder_id": src_meta.get("folder_id"),  # türev, kaynağın klasöründe kalır
         "palette": src_meta.get("palette"),
         "prompt_sent": src_meta.get("prompt_sent")},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


def _check_asset_kind(kind: str) -> None:
    if kind not in assets_store.KINDS:
        raise HTTPException(status_code=404, detail="bilinmeyen tür")


@app.post("/api/assets/{kind}")
async def upload_asset(
    kind: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
) -> dict:
    """Bir logo/banner PNG'si yükler; doğrulayıp yeniden kodlar ve kütüphaneye ekler."""
    _check_asset_kind(kind)
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    image_bytes = _to_png(raw)  # şeffaflığı koruyan RGBA PNG'ye yeniden kodla
    stem = os.path.splitext(os.path.basename(file.filename or ""))[0]
    label = (name.strip() or stem or "varlık")[:120]
    record = assets_store.save_asset(kind, image_bytes, label, ASSETS_DIR, now=_now())
    return {"asset": record}


@app.get("/api/assets/{kind}")
def list_assets_route(kind: str) -> dict:
    _check_asset_kind(kind)
    return {"items": assets_store.list_assets(kind, ASSETS_DIR)}


@app.delete("/api/assets/{kind}/{asset_id}")
def delete_asset_route(kind: str, asset_id: str) -> dict:
    _check_asset_kind(kind)
    removed = assets_store.delete_asset(kind, asset_id, ASSETS_DIR)
    if not removed:
        raise HTTPException(status_code=404, detail="varlık bulunamadı")
    return {"deleted": os.path.basename(asset_id)}


@app.get("/assets/{kind}/{filename}")
def asset_file(kind: str, filename: str) -> FileResponse:
    _check_asset_kind(kind)
    safe = os.path.basename(filename)
    if not safe or safe in (".", "..") or safe == assets_store.MANIFEST_FILE:
        raise HTTPException(status_code=404, detail="bulunamadı")
    path = os.path.join(ASSETS_DIR, kind, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type="image/png")


@app.get("/output/{filename}")
def output_file(filename: str) -> FileResponse:
    safe = os.path.basename(filename)
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=404, detail="bulunamadı")
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# static/ dosyalarını /static altında servis et (index route'undan sonra mount)
# STATIC_DIR Task 6'da oluşturulacak; mount import anında hata vermesin diye
# önce garanti altına alınır.
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
