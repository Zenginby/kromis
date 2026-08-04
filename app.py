"""GPT-Image Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import base64
import datetime as _dt
import io
import os
import traceback
from collections.abc import Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
# Ham form değerleri Starlette'in UploadFile'ıdır; fastapi.UploadFile onun ALT
# sınıfı olduğundan isinstance kontrolü taban sınıfa yapılmalı.
from starlette.datastructures import UploadFile as FormUploadFile

import assets_store
import azure_client as ac
import backup
import chat_client as cc
import chat_store
import color_names
import composite
import errlog
import folders
import palette
import palette_store
import paths
import seed
import storage
import version
from models import (MAX_PROMPT_CHARS, BannerRequest, BulkImagesRequest,
                    BulkMoveRequest, ChatRequest, ChatSaveRequest, FolderRequest,
                    GenerateRequest, LogoRequest, MoveImageRequest,
                    SavePaletteRequest, SettingsRequest, SuggestRequest,
                    check_drop_indices)

BASE_DIR = paths.REPO_DIR                    # geriye uyum: mevcut kullanımlar bozulmasın
OUTPUT_DIR = paths.output_dir()
STATIC_DIR = paths.static_dir()
ASSETS_DIR = paths.assets_dir()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024          # dosya başına
MAX_EDIT_IMAGES = 4                          # ana görsel + en fazla 3 ek referans
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES * MAX_EDIT_IMAGES  # tüm multipart gövdesi
MAX_IMAGE_PIXELS = 50 * 1024 * 1024
MAX_FOLDER_DEPTH = 5                         # iç içe klasör kademesi
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Sunucu başlarken çalışır — import anında DEĞİL.

    Hem dizin açma hem tohumlama gerçek dosya sistemine dokunduğu için modül
    kapsamında çalışmamalı: app'i yalnızca import eden bir test ya da betik
    kullanıcının gerçek veri dizinini (frozen'da ~/Library/Application
    Support/...) yaratmasın, assets/'ine yazmasın.

    Tohumlama kozmetik bir kolaylıktır (logo seçiciyi önceden doldurur) —
    başarısız olması (dolu disk, kısıtlı Application Support, okunamayan
    gömülü PNG) uygulamanın TAMAMINI düşürmemeli: guard olmadan uvicorn'un
    startup()'ı asla bitmez, desktop.py 15 sn sonra hata verir ve kullanıcı
    hiçbir pencere görmez. Hata hata.log'a yazılır, uygulama yine de açılır.

    Dizin açma da aynı guard'ın içinde: patlarsa (izinsiz Application Support)
    tek başına pencereyi engellememeli — yazma yollarının hepsi (storage,
    assets_store, folders, palette_store) kendi `makedirs`'ini zaten yapıyor,
    yani hata gerçekten kalıcıysa kullanıcı istek başına anlaşılır bir hata
    görür; açılmayan bir uygulamadan iyidir.

    SIRA YÜK TAŞIYOR: yedek, tohumlamadan ÖNCE koşar. `seed` yazan bir işlem
    (assets/logos/index.json); tohumlama önce koşsa taze bir makinede yedek
    "kullanıcının verisi var" diye taze tohum verisinin işe yaramaz yedeğini
    alırdı. Yükseltmede sıra fark etmez (seed marker yüzünden no-op) — yani bu
    hata YALNIZCA taze kurulumda görünür, yani ofiste, asla geliştirmede. Bu
    yüzden yoruma değil teste bağlandı (tests/test_backup.py).

    İKİ AYRI guard: yedek hatası kullanıcının tohumlanmış logolarına mal
    olmasın. Yedek bir EMNİYET özelliği olduğu için "başarısızsa durdur"
    cazibesi var; YAPILMIYOR — yedek yüzünden uygulamaya giremeyen kullanıcının
    verisine arayüzden hiçbir yolu kalmaz, bu loglanmış-ama-alınmamış bir
    yedekten kesinlikle kötüdür.
    """
    now = _now()
    try:
        paths.ensure_data_dirs()
        backup.backup_manifests_if_version_changed(
            paths.data_dir(), OUTPUT_DIR, ASSETS_DIR,
            version=version.APP_VERSION, now=now)
    except Exception:
        errlog.safe_append(paths.data_dir(), traceback.format_exc())
    try:
        seed.seed_builtin_logos(ASSETS_DIR, paths.bundled_logos_dir(),
                                paths.data_dir(), now=now)
    except Exception:
        errlog.safe_append(paths.data_dir(), traceback.format_exc())
    yield


app = FastAPI(title="GPT-Image Studio", lifespan=_lifespan)


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


def _png_dimensions(data: bytes) -> str:
    """PNG baytlarından `"GENİŞLİKxYÜKSEKLİK"`. Üretimde bu alan Azure'ın boyut
    dizesi; içe aktarmada uydurulacak bir değer yok, gerçek çözünürlük yazılır."""
    with Image.open(io.BytesIO(data)) as im:
        return f"{im.width}x{im.height}"


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


# palettes.json elle düzenlenebilir bir dosya. Okuma katmanı bozuk JSON'a
# dayanıklı (palette_store._read), ama kaydın İÇERİĞİ de doğrulanmalı: `mode`
# ve `seed` doğrudan palette.harmony'ye gidiyor ve orada ValueError üretip
# üretimi 500'e düşürüyordu. Bozuk alan sessizce yok sayılır ve istekle gelen
# değere düşülür — silinmiş palet nasıl bloke etmiyorsa bozuk palet de etmemeli.

def _safe_seed(value) -> str | None:
    """Kayıttan gelen tohum hex'i; geçersizse None."""
    try:
        return palette.parse_hex(value)
    except (ValueError, TypeError):
        return None


def _saved_colors(saved: dict) -> list[dict]:
    """Kayıttaki kullanılabilir renkler: hem `hex` hem `name` taşıyan girdiler."""
    raw = saved.get("colors")
    if not isinstance(raw, list):
        return []
    return [c for c in raw
            if isinstance(c, dict) and c.get("hex") and c.get("name")]


def _palette_prompt(prompt: str, seed: str | None, mode: str, strength: str,
                    palette_id: str | None = None, *, task: str,
                    drop: Sequence[int] = ()) -> tuple[str, dict | None]:
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

    Düşen ek `applied: False` ile İŞARETLENİR. Kayıt yine tutulur ("istedim")
    ama arayüz bunu uygulanmış bir paletten ayırabilmek zorunda; ayıramazsa
    kullanıcı renksiz sonucu açıklayamaz. Bayrağı çıkarmak yerine koymak, aynı
    sessiz-sapma hatasının bindirme seçeneklerinde yaşanmış halinin tekrarı
    olmasını engelliyor (bkz. 15c6646).
    """
    if not seed:
        return prompt, None
    saved = _saved_palette(palette_id)
    if saved:
        mode = saved["mode"] if saved.get("mode") in palette.MODES else mode
        seed = _safe_seed(saved.get("seed")) or seed
        colors = _saved_colors(saved) or _resolve_palette(seed, mode, offline=True)
    else:
        colors = _resolve_palette(seed, mode, offline=True)

    # Çıkarma TEK NOKTADA, renkler çözüldükten SONRA uygulanıyor: indeksler
    # böylece kayıtlı paletin DONMUŞ listesinde de tutarlı oluyor (kullanıcı
    # çıkarıp kaydettiyse o liste 5'ten kısa olabilir).
    kept = _drop_colors(colors, drop)
    if not kept:
        # models.check_drop_indices'in üst sınırı 5'lik listeye göre; 3 renkli
        # donmuş bir kayıtta [0,1,2] o kapıdan GEÇER ama sonuç boş palet olur.
        # Sessizce çıkarmayı yok saymak yerine gürültülü 422: renksiz sonucu
        # açıklayamayan kullanıcı, bu özelliğin engellemek için var olduğu şey.
        raise HTTPException(status_code=422,
                            detail="Paletten en az bir renk kalmalı.")

    suffix = palette.prompt_suffix(kept, strength, task=task)
    applied = len(prompt) + len(suffix) <= MAX_PROMPT_CHARS
    record = {"seed": seed, "mode": mode, "strength": strength,
              # `colors` = KALANLAR: çip ve galeri bunu gösteriyor, yani
              # gösterilen şerit prompt'a gidenle birebir. `dropped` ise
              # geçmişten aynı durumu kurabilmek için.
              "colors": kept, "applied": applied,
              "dropped": sorted(set(drop))}
    if saved:
        record["id"] = saved["id"]
        record["name"] = saved.get("name", "")
    return (prompt + suffix if applied else prompt), record


@app.post("/api/generate")
def generate(req: GenerateRequest) -> dict:
    folder_id = _check_folder(req.folder_id)
    prompt_sent, pal = _palette_prompt(req.prompt, req.palette_hex, req.palette_mode,
                                       req.palette_strength, req.palette_id,
                                       drop=req.palette_drop,
                                       task="generate")
    try:
        images = ac.generate(prompt_sent, req.size, req.quality, req.n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    records = [
        storage.save(img, {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None,
                           "folder_id": folder_id, "palette": pal,
                           # Ek düştüyse metin prompt'un birebir aynısı; storage
                           # sözleşmesi "yalnızca farklıysa" diyor (bkz. save).
                           "prompt_sent": prompt_sent if pal and pal["applied"] else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


def _check_edit_form(prompt: str, size: str, quality: str, n: int,
                     file: UploadFile | None, source_id: str | None,
                     palette_mode: str, palette_strength: str) -> None:
    """`/api/edit` form alanlarını doğrular; geçersizse HTTPException(422).

    Doğrulama neden elle: uç multipart olduğu için GenerateRequest gibi tek bir
    Pydantic modeli yok. Not: multipart'ta `extra="forbid"` karşılığı YOK —
    Starlette bilinmeyen form alanını sessizce atar. Bayat sunucu tespiti bu
    yüzden arayüz tarafında, yanıtın paleti geri yansıtıp yansıtmadığına
    bakılarak yapılıyor.
    """
    if size not in ac.ALLOWED_SIZES or quality not in ac.ALLOWED_QUALITIES:
        raise HTTPException(status_code=422, detail="Geçersiz size veya quality.")
    if not (1 <= n <= 4):
        raise HTTPException(status_code=422, detail="n 1-4 arasında olmalı.")
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=422,
                            detail=f"prompt 1-{MAX_PROMPT_CHARS} karakter olmalı.")
    if palette_mode not in palette.MODES:
        raise HTTPException(status_code=422, detail="Geçersiz palette_mode.")
    if palette_strength not in palette.STRENGTHS:
        raise HTTPException(status_code=422, detail="Geçersiz palette_strength.")
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422,
                            detail="Tam olarak biri gerekli: file veya source_id.")


def _check_palette_hex(palette_hex: str | None) -> str | None:
    """Form'dan gelen tohum hex'i normalleştirir; boşsa None, geçersizse 422."""
    if not palette_hex:
        return None
    try:
        return palette.parse_hex(palette_hex)
    except ValueError:
        raise HTTPException(status_code=422, detail="Geçersiz palette_hex.")


def _check_palette_drop(value: str | None) -> list[int]:
    """Form'dan gelen `"0,3"` biçimini indeks listesine çevirir; geçersizse 422.

    Arayüz hiçbir şey çıkarılmadığında alanı GÖNDERMİYOR; boş dize de "çıkarma
    yok" demek, hata değil.

    Biçim neden virgüllü metin: core.js palet seçeneklerini genel bir döngüyle
    (`Object.entries(pal)`) FormData'ya basıyor ve orada JS dizisi kendiliğinden
    `"0,3"`'e dönüyor. Döngüyü elle sayıma çevirmek bir kez `palette_id`'yi
    sessizce düşürmüştü (core.js'teki not), o yüzden ayrıştırma burada.
    """
    if not value:
        return []
    try:
        indices = [int(part) for part in value.split(",")]
    except ValueError:
        raise HTTPException(status_code=422, detail="Geçersiz palette_drop.")
    try:
        return check_drop_indices(indices)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _drop_colors(colors: list[dict], drop: Sequence[int]) -> list[dict]:
    """Verilen indeksleri çıkarır; KALANLARIN SIRASI korunur.

    Sıra prompt'ta anlam taşıyor (palette._ORDER_CUE: baştaki renkler geniş
    alanlara, sondaki küçük vurgu olarak). Yeniden dizilse kullanıcının çipte
    gördüğü şerit ile modele giden ağırlık sırası ayrışırdı.
    """
    if not drop:
        return colors
    excluded = set(drop)
    return [c for i, c in enumerate(colors) if i not in excluded]


async def _collect_edit_refs(
    request: Request, file: UploadFile | None, source_id: str | None,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Azure'a gidecek referans görselleri toplar: `(refs, parent_id)`.

    Sıra sözleşme: ana görsel → ek yüklemeler → ek galeri görselleri. `parent_id`
    yalnızca ana görsel galeriden seçildiğinde dolu (türev zinciri buna bağlı).
    """
    extra_uploads, extra_ids = await _extra_refs(request)
    if 1 + len(extra_uploads) + len(extra_ids) > MAX_EDIT_IMAGES:
        raise HTTPException(status_code=422,
                            detail=f"En fazla {MAX_EDIT_IMAGES} görsel gönderilebilir "
                                   f"(1 ana + {MAX_EDIT_IMAGES - 1} ek).")

    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="İstek çok büyük.")

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
    return refs, parent_id


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
    # Virgüllü metin, dizi DEĞİL: core.js FormData'ya böyle yazıyor
    # (bkz. _check_palette_drop). Boş = çıkarma yok.
    palette_drop: str = Form(""),
) -> dict:
    """Ek referans görselleri (`extra_files` yüklemeleri, `extra_source_ids`
    galeri id'leri) form verisinden okunur — bkz. _extra_refs."""
    _check_edit_form(prompt, size, quality, n, file, source_id,
                     palette_mode, palette_strength)
    palette_hex = _check_palette_hex(palette_hex)
    drop = _check_palette_drop(palette_drop)

    target_folder = _check_folder(folder_id)
    refs, parent_id = await _collect_edit_refs(request, file, source_id)

    # task="edit": üretim ifadesi modele yeniden boyama söyler ve referans
    # görselin kompozisyonunu yok eder; düzenlemede istenen renk derecelendirmesi.
    prompt_sent, pal = _palette_prompt(prompt, palette_hex, palette_mode,
                                       palette_strength, palette_id, task="edit",
                                       drop=drop)
    try:
        images = ac.edit(prompt_sent, refs, size, quality, n)
    except ac.AzureImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    records = [
        storage.save(img, {"prompt": prompt, "size": size, "quality": quality,
                           "parent_id": parent_id, "folder_id": target_folder,
                           "palette": pal,
                           "prompt_sent": prompt_sent if pal and pal["applied"] else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


@app.get("/api/settings")
def get_settings() -> dict:
    """Yapılandırma durumu + uygulama sürümü. API key asla dönmez.

    `version` BURADA birleştiriliyor, azure_client'ta DEĞİL: onun işi kimlik
    bilgisi, uygulama sürümünü bilmesi gereksiz bir bağ olurdu ve
    tests/test_settings.py'deki get_settings_status sözleşmesini genişletirdi.

    Destek sorusu "hangi sürümdesiniz?" v1.8'de cevaplanamıyordu — sürüm
    yalnızca Info.plist'te vardı ve arayüz onu hiç göstermiyordu.

    `chat_instructions_path` da burada birleşiyor: talimatı ezme özelliği
    keşfedilebilir olmasa var olmakla olmamak arasında bir fark kalmaz.
    """
    return {**ac.get_settings_status(),
            "version": version.APP_VERSION,
            "chat_instructions_path": paths.chat_instructions_override()}


@app.post("/api/settings")
def post_settings(req: SettingsRequest) -> dict:
    """Admin kimlik bilgilerini yalnızca-yazılır kaydeder; durumu döndürür (key'siz).

    api_key boşsa mevcut key korunur — ilk kurulumda ise key zorunludur.

    Sohbet dağıtımı AYRI bir çağrıyla ve görsel kimliği doğrulamadan GEÇTİKTEN
    SONRA yazılıyor: geçersiz bir endpoint'le gelen istek hiçbir şey yazmadan
    422 dönmeli.
    """
    api_key = req.api_key.strip()
    if not api_key:
        try:
            api_key, _ = ac.load_credentials()
        except ac.AzureImageError:
            raise HTTPException(status_code=422, detail="İlk kurulumda API key gerekli.")
    try:
        ac.save_credentials(api_key, req.base_url)
        # None = alan hiç gönderilmedi → dokunma (bkz. models.SettingsRequest).
        if req.chat_deployment is not None:
            ac.save_env({ac.CHAT_DEPLOYMENT: req.chat_deployment.strip()})
    except ac.AzureImageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ac.get_settings_status()


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    """Prompt Yönetmeni: Türkçe sohbet → İngilizce gpt-image-2 prompt'u.

    SENKRON `def` (bilinçli): httpx çağrısı bloklayıcı, Starlette bunu kendi
    threadpool'unda koşturur ve olay döngüsü — yani pencere — donmaz;
    `/api/generate`'in aynısı.

    BU ROTA diske hiçbir şey yazmaz ve v1.15'ten sonra da yazmıyor. v1.13'ün
    "karar 4"ü iptal edilmedi, KAPSAMI daraldı: sohbetler artık saklanabiliyor
    ama yazan tek yol kullanıcının kendi başlattığı `/api/chats` (bkz.
    chat_store.py). Modelden dönen her yanıtı sessizce diske almak ile
    kullanıcının "bunu sakla" demesi aynı şey değil; ayrımı
    tests/test_chat_route.py mekanik olarak koruyor.
    """
    try:
        return cc.complete([m.model_dump() for m in req.messages])
    except cc.ChatError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Kayıtlı sohbetler ───────────────────────────────────────────────────
# Kalıcılık SUNUCUDA, istemcide değil: `desktop.py` pencereyi private mode'da
# açıyor (pywebview varsayılanı) ve orada localStorage her kapanışta silinir —
# paketlenmiş .app'te geçmiş sessizce buharlaşırdı.

@app.get("/api/chats")
def list_chats_route() -> dict:
    """Kenar panelinin listesi: başlıklar, gövdeler DEĞİL (bkz. chat_store)."""
    return {"chats": chat_store.list_chats(OUTPUT_DIR)}


@app.get("/api/chats/{chat_id}")
def get_chat_route(chat_id: str) -> dict:
    rec = chat_store.get(os.path.basename(chat_id), OUTPUT_DIR)
    if rec is None:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    return {"chat": rec}


@app.post("/api/chats")
def create_chat_route(req: ChatSaveRequest) -> dict:
    """Yeni kayıt. Başlık ve gövde ZORUNLU: boş bir sohbet kaydetmek anlamsız."""
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Sohbet başlığı gerekli.")
    if not req.messages:
        raise HTTPException(status_code=422, detail="Kaydedilecek mesaj yok.")
    messages = [m.model_dump() for m in req.messages]
    return {"chat": chat_store.create(title, messages, OUTPUT_DIR, now=_now())}


@app.put("/api/chats/{chat_id}")
def update_chat_route(chat_id: str, req: ChatSaveRequest) -> dict:
    """Gövdeyi ve/veya başlığı değiştirir (tur sonu kaydı + yeniden adlandırma).

    Başlık BOŞ dizeyle gelirse reddedilir: adsız bir sohbet kenar panelinde
    tıklanacak hiçbir şey bırakmaz.
    """
    title = None if req.title is None else req.title.strip()
    if title is not None and not title:
        raise HTTPException(status_code=422, detail="Sohbet başlığı boş olamaz.")
    messages = None if req.messages is None else [m.model_dump() for m in req.messages]
    rec = chat_store.update(os.path.basename(chat_id), OUTPUT_DIR,
                            messages=messages, title=title, now=_now())
    if rec is None:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    return {"chat": rec}


@app.delete("/api/chats/{chat_id}")
def delete_chat_route(chat_id: str) -> dict:
    cid = os.path.basename(chat_id)
    if not chat_store.delete(cid, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    return {"deleted": cid}


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
    # Sınırsız derinlik başlık şeridini taşırıyor ve köke dönüşü zorlaştırıyor;
    # yeniden ebeveynleme olmadığı için tek kapı burası.
    if parent_id and folders.depth(parent_id, OUTPUT_DIR) >= MAX_FOLDER_DEPTH:
        raise HTTPException(
            status_code=422,
            detail=f"En fazla {MAX_FOLDER_DEPTH} kademe klasör açılabilir.")
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


@app.post("/api/import")
async def import_image(request: Request,
                      file: UploadFile = File(...),
                      folder_id: str | None = Form(None)) -> dict:
    """Bilgisayardan sürüklenen bir görseli galeriye (isteğe bağlı klasöre) aktarır.

    ÜRETİMDEN DOĞMAYAN ilk kayıt türü: prompt yok, palet yok, Azure'a hiç
    çıkılmaz. Dosya `_read_upload_png` ile doğrulanıp PNG'ye YENİDEN KODLANIR —
    `/output/{filename}`, `storage.delete` ve `_output_png_path` dosyanın
    `{id}.png` olduğunu varsayıyor; JPEG olduğu gibi kaydedilirse kayıt görünür
    ama görsel açılmaz.

    Sıra bilinçli: content-length → klasör → gövde. Geçersiz bir klasör için
    10 MB'ı okumak boşuna iş.

    Dosya başına TEK istek: arayüz çoklu bırakmayı sıraya koyuyor. Toplu bir uç
    yok, çünkü `storage.save` her kayıtta history.json'ın tamamını yeniden
    yazıyor ve eşzamanlılık kayıp güncelleme üretir.
    """
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    target_folder = _check_folder(folder_id)
    png = await _read_upload_png(file)

    # Dosya adı yalnızca ETİKET (galeri başlığı/alt metni); kayıt adı uuid'den
    # geliyor. basename yol parçalarını düşürür, kırpma başlığı taşırmaz.
    label = os.path.basename(file.filename or "").strip()[:120] or "içe aktarılan görsel"
    record = storage.save(
        png,
        {"prompt": label, "size": _png_dimensions(png), "quality": "",
         "parent_id": None, "folder_id": target_folder,
         "palette": None, "prompt_sent": None, "imported": True},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


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
    # Çıkarma DONMA'dan önce uygulanır: kayıt kaç renk taşıyorsa o kadarı
    # prompt'a gider ve sonraki kullanımlarda çıkarma göndermek gerekmez.
    # Kalıcı olarak daha az renkli bir paletin tek yolu bu (bkz. models.drop).
    colors = _drop_colors(colors, req.drop)
    return {"palette": palette_store.create(name, req.seed, req.mode, req.strength,
                                            colors, OUTPUT_DIR, now=_now())}


@app.delete("/api/palettes/{palette_id}")
def delete_palette_route(palette_id: str) -> dict:
    pid = os.path.basename(palette_id)
    if not palette_store.delete(pid, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Palet bulunamadı.")
    return {"deleted": pid}


def _composite_logo(src_path: str, req: LogoRequest) -> bytes:
    """Logo/motto filigranını süreç içinde bindirir (composite.py).

    asset_id verilirse seçilen tek görsel her iki varyant olarak geçilir: renk
    seçimi (auto/blue/white) hangisine düşerse düşsün aynı görsel kullanılır.
    """
    logo_blue = paths.builtin_logo("blue")
    logo_white = paths.builtin_logo("white")
    if req.asset_id:
        overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, ASSETS_DIR)
        if overlay_path is None:
            raise HTTPException(status_code=404, detail="görsel bulunamadı")
        logo_blue = logo_white = overlay_path
    try:
        return composite.composite_logo(
            src_path,
            logo_blue=logo_blue, logo_white=logo_white,
            position=req.position, color=req.color, scale=req.size,
            shadow_alpha=req.shadow_alpha, shadow_blur=req.shadow_blur,
            offset_x=req.offset_x, offset_y=req.offset_y,
        )
    except Exception as exc:
        # Geniş yakalama bilinçli: PIL'in DecompressionBombError'ı doğrudan
        # Exception'dan türüyor, OSError/ValueError ile sınırlı bir except onu
        # kaçırıp kullanıcıya çıplak bir sunucu hatası gösteriyordu. Buradaki
        # sözleşme "bindirme neyle patlarsa patlasın Türkçe 500 dön".
        raise HTTPException(
            status_code=500,
            # str(exc) boş olabilir (argümansız istisna) — o zaman sınıf adı
            # hiç yoktan iyidir. `exc or ...` işe yaramaz: istisna nesneleri
            # her zaman truthy.
            detail=f"Logo bindirme başarısız: {str(exc) or type(exc).__name__}") from exc


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
def index() -> HTMLResponse:
    """index.html'i sürüm yerine konarak servis eder.

    Neden FileResponse DEĞİL, üç sebep:

    1. `?v=` cache-buster'ı artık version.py'den TÜRETİLİYOR. Şablonda
       `__APP_VERSION__` yer tutucusu duruyor, burada gerçek sürümle
       değiştiriliyor — elle artırılan ikinci bir sürüm literali kalmıyor.

    2. `no-store` şart, süs değil: WKWebView (pywebview) HTML BELGESİNİN
       KENDİSİNİ de önbelleğe alır. Belge bayatlarsa içindeki `?v=` de
       bayatlar ve cache-buster hiçbir işe yaramaz — kullanıcı .app'i
       değiştirse bile eski arayüzü görür. Bu delik paket tarafında bugün
       desktop.py'nin `port=0`'ı sayesinde KAZARA kapalı (her açılış farklı
       origin); `run.sh` tarafında ise CANLI (sabit 8765 + Cache-Control yok
       + frozen'da Last-Modified = build tarihi → sezgisel tazelik penceresi
       günlere çıkabilir). Portu bir gün sabitleme kararı deliği sessizce
       geri getirirdi. `/static`'e bu başlık BİLEREK konmuyor — orada `?v=`
       her sürüme ayrı URL veriyor (bkz. mount açıklaması).

    3. Okuma hatası artık sessiz değil: FileResponse'ın davranışı gönderim
       anında yakalanmayan bir RuntimeError'dı ve --windowed pakette stderr
       olmadığı için kullanıcı boş pencere görür, hata.log'a hiçbir şey
       düşmezdi. HTTPException değil HTMLResponse dönüyor — çalışan çıplak
       JSON görmesin.

    Şablon her istekte diskten okunuyor, BELLEKTE TUTULMUYOR: run.sh ile
    geliştirirken "HTML'i düzenle → yenile → gör" akışı böyle korunuyor.
    """
    try:
        with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
            template = f.read()
    except OSError:
        log_path = errlog.safe_append(paths.data_dir(), traceback.format_exc())
        return HTMLResponse(
            "<h1>Arayüz yüklenemedi</h1>"
            "<p>Uygulama dosyaları okunamadı. Lütfen uygulamayı kapatıp yeniden açın; "
            f"sürerse hata kaydını (<code>{log_path or 'hata.log'}</code>) Kurum'ya iletin.</p>",
            status_code=500, headers={"Cache-Control": "no-store"})
    return HTMLResponse(template.replace("__APP_VERSION__", version.APP_VERSION),
                        headers={"Cache-Control": "no-store"})


# static/ dosyalarını /static altında servis et (index route'undan sonra mount).
# Geliştirmede STATIC_DIR git'te izlenen bir dizindir ama boş bir checkout'ta
# (taze klon) henüz yoksa StaticFiles mount'u import anında patlardı — bu
# yüzden yalnızca geliştirmede garanti altına alınır. Paket içindeyken
# (frozen) STATIC_DIR sys._MEIPASS altında PyInstaller'ın gömdüğü salt-okunur
# bir dizindir: hem zaten var, hem de oraya os.makedirs YAZMA denemesi bile
# yanlış — bu dal frozen'da hiç çalışmamalı.
#
# Yazılabilir dizinler (output/, assets/) burada AÇILMAZ: mount'un onlara
# ihtiyacı yok ve import'un yan etkisi olmamalı — açılış `_lifespan`'da.
#
# `/` no-store gönderirken /static'in ÖNBELLEKLENEBİLİR kalması KASITLI bir
# asimetridir, tutarsızlık değil: `?v=<sürüm>` her sürüme ayrı URL veriyor,
# yani bayat bir kayıt hiç ADRESLENMİYOR; üstelik StaticFiles ETag/
# Last-Modified gönderdiği için aynı URL'ye gelen istek loopback'te ucuz bir
# 304'e düşüyor. Buraya no-store eklemek cache-buster mekanizmasının bütün
# anlamını siler.
if not paths.is_frozen():
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
