"""Kromis Studio — yerel FastAPI arayüzü."""
from __future__ import annotations

import base64
import datetime as _dt
import io
import os
import re
import traceback
from collections.abc import Sequence
from contextlib import asynccontextmanager
from urllib.parse import quote


from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from fastapi.staticfiles import StaticFiles
from PIL import Image
# Ham form değerleri Starlette'in UploadFile'ıdır; fastapi.UploadFile onun ALT
# sınıfı olduğundan isinstance kontrolü taban sınıfa yapılmalı.
from starlette.datastructures import UploadFile as FormUploadFile

import assets_store
import azure_client as ac
import catalog
import credstore
import providers
import backup
import chat_client as cc
import chat_prompt
import chat_providers
import chat_store
import color_names
import composite
import errlog
import folders
import guncelleme
import palette
import palette_store
import paths
import prefs
import storage
import version
from models import (MAX_CHAT_TITLE_CHARS, MAX_IMAGES_PER_RUN, MAX_PROMPT_CHARS,
                    ArenaWinnerRequest,
                    BannerRequest, BulkImagesRequest, BulkMoveRequest,
                    ChatRequest, ChatSaveRequest, FolderRequest, GenerateRequest,
                    LogoRequest, MoveImageRequest, PrefsRequest,
                    SavePaletteRequest, SettingsRequest, SuggestRequest,
                    VideoRequest, check_capabilities,
                    check_drop_indices, check_video_capabilities,
                    wire_messages)

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

    Dizin açma ve yedek gerçek dosya sistemine dokunduğu için modül kapsamında
    çalışmamalı: app'i yalnızca import eden bir test ya da betik kullanıcının
    gerçek veri dizinini (frozen'da ~/Library/Application Support/...)
    yaratmasın, assets/'ine yazmasın.

    Guard'ın gerekçesi: patlarsa (izinsiz Application Support, dolu disk) tek
    başına pencereyi engellememeli — guard olmadan uvicorn'un startup()'ı asla
    bitmez, desktop.py 15 sn sonra hata verir ve kullanıcı hiçbir pencere
    görmez. Yazma yollarının hepsi (storage, assets_store, folders,
    palette_store) kendi `makedirs`'ini zaten yapıyor, yani hata gerçekten
    kalıcıysa kullanıcı istek başına anlaşılır bir hata görür; açılmayan bir
    uygulamadan iyidir. Hata hata.log'a yazılır, uygulama yine de açılır.

    Yedek bir EMNİYET özelliği olduğu için "başarısızsa durdur" cazibesi var;
    YAPILMIYOR — yedek yüzünden uygulamaya giremeyen kullanıcının verisine
    arayüzden hiçbir yolu kalmaz, bu loglanmış-ama-alınmamış bir yedekten
    kesinlikle kötüdür.

    NOT: Burada bir İKİNCİ adım vardı — `seed.seed_builtin_logos`
    pakete gömülü yerleşik logo çiftini kullanıcının kütüphanesine kopyalardı.
    Uygulama marka-nötr olduğundan o modül tamamen kaldırıldı; kütüphane artık
    boş başlar ve kullanıcı kendi logosunu yükler.
    """
    now = _now()
    try:
        paths.ensure_data_dirs()
        backup.backup_manifests_if_version_changed(
            paths.data_dir(), OUTPUT_DIR, ASSETS_DIR,
            version=version.APP_VERSION, now=now)
        # Ölü `uploads` türünün göçü — YEDEKTEN SONRA, bilerek: göç kullanıcı
        # verisini yerinden oynatan tek açılış adımı, yani sürüm değişiminde
        # alınan yedek göç ÖNCESİ hâli taşımalı. Yeni kurulumda maliyeti tek
        # bir `isdir`; gerekçesi assets_store.migrate_legacy_uploads'ta.
        assets_store.migrate_legacy_uploads(ASSETS_DIR)
    except Exception:
        errlog.safe_append(paths.data_dir(), traceback.format_exc())
    yield


app = FastAPI(title="Kromis Studio", lifespan=_lifespan)


# Kimlik FORMU olan rotalar: yanıtta hiçbir alanın değeri yankılanmak zorunda
# değil, o yüzden kapı alan adına değil ROTAYA bakıyor. Üç kapının en GÜÇLÜSÜ bu —
# yarın forma eklenen bir alan hiçbir şey hatırlanmadan kapsanıyor.
_CREDENTIAL_ROUTES = frozenset({"/api/settings"})

# İkinci kapı: BAŞKA bir rotada geçebilecek gizli alan adları. Katalogdan
# TÜRETİLİYOR, elle sayılmıyor.
_SECRET_FIELDS = frozenset({"api_key"}) | catalog.secret_field_names()
# Üçüncü kapı: kataloğa hiç girmemiş alan da adının BİÇİMİNDEN yakalanıyor
# (bugünkü `fal_key` / `replicate_api_token` tam olarak bu kapıdan geçiyor).
_SECRET_SUFFIXES = ("_api_key", "_key", "_token", "_secret")


def _is_secret_loc(loc) -> bool:
    return any(str(p) in _SECRET_FIELDS or str(p).endswith(_SECRET_SUFFIXES)
               for p in loc)


@app.exception_handler(RequestValidationError)
async def _redact_validation_errors(request: Request, exc: RequestValidationError):
    """Doğrulama hatası gövdesinde gizli değeri yankılama (FastAPI 'input' döner).

    v0.6'da GENELLEŞTİ ve sebebi ÖLÇÜLDÜ: kapı `loc` içinde birebir `"api_key"`
    arıyordu, yani BYOK alanları (`openai_api_key`, `fal_key`,
    `replicate_api_token` — üçü de v0.2.0'dan beri kabul ediliyor) kapsam
    DIŞINDAYDI. 500 karakteri aşan bir değer 422 alıyor ve anahtar `input`
    alanında istemciye AYNEN dönüyordu. `azure_client.py`'nin başındaki
    "bu yüzden ikinci bir gizli form alanı eklenmedi" notu tam olarak bu boşluğu
    tarif ediyor; boşluk kapandığı için o notun dayattığı kısıt da kalktı —
    çoklu sağlayıcı formu ancak bundan sonra eklenebilir.

    Üç kapı birlikte çünkü her biri diğerinin kaçırdığını yakalıyor:
      1. ROTA: /api/settings bir kimlik formu, hiçbir alanı yankılanmamalı.
      2. AD: katalogda gizli olarak beyan edilmiş alanlar (başka rotalarda da).
      3. SONEK: kataloğa girmemiş ama adı `_key`/`_token`/`_secret` ile bitenler.

    `ctx` de siliniyor, `input` gibi: pydantic uzunluk hatalarında bağlamda
    değerin kendisi ya da uzunluğu geçebiliyor.
    """
    kimlik_rotasi = request.url.path in _CREDENTIAL_ROUTES
    safe = []
    for err in exc.errors():
        err = dict(err)
        if kimlik_rotasi or _is_secret_loc(err.get("loc") or ()):
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


def _output_media_path(media_id: str) -> str:
    """history id → output/<id>.<uzantı> yolu; bulunamayanda HTTPException(404).

    `_output_png_path`in İKİZİ DEĞİL, KARDEŞİ — ve ikisinin ayrı durması
    bilinçli:

      • `_output_png_path` REFERANS okuma yolu (`/api/edit`in `source_id`si,
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

    Path-traversal guard'ı `_output_png_path`in aynısı: id yalnızca
    basename'e indiriliyor.
    """
    safe = os.path.basename(media_id or "")
    path = storage.media_path_of(safe, OUTPUT_DIR) if safe else None
    if path:
        return path
    raise HTTPException(status_code=404, detail="Kaynak medya bulunamadı.")


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


def _check_session(session_id: str | None) -> str | None:
    """Boş/None ise oturum dışı üretim (None). Doluysa BİÇİMİ doğrular, 422.

    `_check_folder`'ın aksine VARLIK kapısı yok — bilerek. Konsaydı, oturum kaydı
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
        raise HTTPException(status_code=422, detail="Geçersiz session_id.")
    return session_id


def _check_arena(arena_id: str | None) -> str | None:
    """Boş/None ise arena değil (None). Doluysa BİÇİMİ doğrular, 422.

    `_check_session` ile aynı duruş: VARLIK kapısı yok (turun ilk isteği
    yazıldığında ortada henüz başka kayıt yoktur), yalnız biçim. Biçim kapısı
    ise zorunlu — geçersiz bir id depoda sessizce düşerdi ve turun sütunları
    birbirini hiç bulamazdı.
    """
    if not arena_id:
        return None
    if not storage.valid_id(arena_id):
        raise HTTPException(status_code=422, detail="Geçersiz arena_id.")
    return arena_id


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
    session_id = _check_session(req.session_id)
    arena_id = _check_arena(req.arena_id)
    prompt_sent, pal = _palette_prompt(req.prompt, req.palette_hex, req.palette_mode,
                                       req.palette_strength, req.palette_id,
                                       drop=req.palette_drop,
                                       task="generate")
    # `req.model` doğrulayıcıda NORMALLEŞTİRİLDİ (None → varsayılanın gerçek
    # id'si), yani doğrulanan değer ile kaydedilen değer ayrışamıyor.
    spec = catalog.image_model(req.model)
    try:
        images = providers.generate(req.model, prompt_sent, req.size,
                                    req.quality, req.n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    # Maliyet GÖRSEL BAŞINA yazılıyor: kayıt tek bir görselin kaydı ve n=4'lük
    # bir turun tamamını her satıra yazmak toplamı dörde katlardı.
    kredi = catalog.cost_for(spec, req.quality)
    records = [
        storage.save(img, {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None,
                           "folder_id": folder_id, "palette": pal,
                           "session_id": session_id,
                           # Turun sütunları AYRI isteklerle geliyor (istemci
                           # fan-out'u; bkz. models.GenerateRequest.arena_id) —
                           # onları birbirine bağlayan tek şey bu etiket.
                           "arena_id": arena_id,
                           "model": req.model, "credits": kredi,
                           # Ek düştüyse metin prompt'un birebir aynısı; storage
                           # sözleşmesi "yalnızca farklıysa" diyor (bkz. save).
                           "prompt_sent": prompt_sent if pal and pal["applied"] else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


@app.post("/api/video")
def video(req: VideoRequest) -> dict:
    """Metin → video. `generate`in video ikizi.

    SENKRON ve bu bilinçli bir seçim, kaza değil: üretim 1-6 dakika sürüyor ve
    istek o süre boyunca açık kalıyor. Emsali depoda zaten var — Azure'ın n=4
    üretimi `180+120·3` = 540 saniyelik bir okuma bütçesiyle çalışıyor
    (`azure_client.read_timeout_for`). Yoklamanın adaptörün İÇİNDE olması,
    `providers` sözleşmesini (`list[bytes]`) bozmadan bu yolu açıyor;
    `catalog.poll_timeout` alanının ilk yorumu da tam olarak bu günü tarif
    ediyordu.
    Bilinen bedeli: sekme yenilenirse iş kaybediliyor ve ilerleme yüzde
    olarak gösterilemiyor. İkincisi zaten deponun kayıtlı kararı
    (`index.html`in "yüzde uydurmaydı" notu); ilkinin cevabı bir iş kuyruğu ve
    o ayrı bir madde.

    `def`, `async def` DEĞİL — `generate` ve `chat` ile aynı gerekçe: Starlette
    senkron rotayı iş parçacığı havuzunda koşturuyor, yani bloklayan httpx
    çağrısı olay döngüsünü dondurmuyor. `async def` içinde aynı çağrı bütün
    sunucuyu kilitlerdi ve burada süre dakikalarla ölçülüyor.

    PALET ve ARENA yok; gerekçeleri `VideoRequest`in docstring'inde.
    """
    folder_id = _check_folder(req.folder_id)
    session_id = _check_session(req.session_id)
    # `req.model` doğrulayıcıda NORMALLEŞTİRİLDİ (None → varsayılanın gerçek
    # id'si), yani doğrulanan değer ile kaydedilen değer ayrışamıyor.
    spec = catalog.video_model(req.model)
    try:
        videos = providers.generate_video(req.model, req.prompt, req.size,
                                          req.quality, req.duration, req.n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    kredi = catalog.cost_for(spec, req.quality, duration=req.duration)
    records = [
        storage.save(vid, {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None,
                           "folder_id": folder_id, "palette": None,
                           "session_id": session_id,
                           "kind": "video", "duration": req.duration,
                           "model": req.model, "credits": kredi,
                           "prompt_sent": None},
                     OUTPUT_DIR, now=_now())
        for vid in videos
    ]
    # ANAHTAR `videos`, `images` DEĞİL: istemci yanıtın türünü gövdeden
    # okuyor ve `{"images": …}` döndürmek, bayat bir istemcinin videoyu
    # `<img>` olarak çizmesine yol açardı — sessiz bir bozuk resim. Ayrı
    # anahtar, eski istemcide YÜKSEK SESLE "images undefined" demek.
    return {"videos": records}


def _check_video_form(prompt: str, size: str, quality: str, duration: int,
                      n: int, file: UploadFile | None,
                      source_id: str | None, model: str = "",
                      last_file: UploadFile | None = None,
                      last_source_id: str | None = None) -> str:
    """`/api/video/animate` form alanlarını doğrular; geçersizse 422.

    `_check_edit_form`un video ikizi ve aynı iki gerekçeyle var: multipart uçta
    tek bir Pydantic modeli YOK (elle doğrulama şart) ve yetenek kapısı JSON
    ucuyla PAYLAŞILMAK zorunda — iki kopya, iki ucun sessizce ayrışması
    demekti (arayüz bir süreyi sunar, bir uçta geçer, diğerinde 422 döner).

    Palet kapıları YOK: bu ucun palet alanı da yok (bkz. `VideoRequest`).
    """
    try:
        model_id = check_video_capabilities(model, size, quality, duration, n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    spec = catalog.video_model(model_id)
    if not spec.supports_edit:
        raise HTTPException(status_code=422,
                            detail=f"{spec.label} referans görselle çalışmıyor.")
    # `_check_edit_form`un aynı kapısı ve burada ALT sınır daha da gerekli:
    # `check_video_capabilities` yalnız TAVANI ölçüyor (`n > max_n`) ve form
    # ucunda `n` için pydantic `ge=1` YOK (JSON ikizinde var). `n=0` geçse
    # `providers.total_budget` SIFIR dönerdi — yani Veo işi gönderilir
    # (faturalanır) ve döngü ilk yoklamadan önce "süre doldu" der.
    if not (1 <= n <= min(spec.max_n, MAX_IMAGES_PER_RUN)):
        raise HTTPException(
            status_code=422,
            detail=f"n 1-{min(spec.max_n, MAX_IMAGES_PER_RUN)} arasında olmalı.")
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=422,
                            detail=f"prompt 1-{MAX_PROMPT_CHARS} karakter olmalı.")
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422,
                            detail="Tam olarak biri gerekli: file veya source_id.")
    # SON KARE. Ana karenin "tam olarak biri" kapısının ikizi, tek farkı
    # İSTEĞE BAĞLI olması: bitiş görseli hiç verilmeyebilir (o zaman istek
    # bugünküyle aynı), ama iki yoldan birden verilemez.
    if last_file is not None and last_source_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Bitiş görseli için en fazla biri: last_file veya "
                   "last_source_id.")
    if (last_file is not None or last_source_id is not None) \
            and not spec.supports_last_frame:
        # Yetenek kapısı `supports_edit`ten AYRI: ilk kareyi alan bir model
        # son kareyi almayabilir. Mesaj hangi modelin reddettiğini söylüyor,
        # çünkü çözüm composer'daki şeritten başka bir model seçmek.
        raise HTTPException(
            status_code=422,
            detail=f"{spec.label} bitiş görseli almıyor.")
    return model_id


@app.post("/api/video/animate")
async def animate(
    request: Request,
    prompt: str = Form(...),
    size: str = Form(...),
    quality: str = Form(...),
    duration: int = Form(...),
    n: int = Form(1),
    file: UploadFile | None = File(None),
    source_id: str | None = Form(None),
    # SON KARE ana karenin form çiftinin BİREBİR ikizi. `_extra_refs`in
    # "ek referans" kanalından geçirilmedi ve gerekçesi katalogtaki
    # `supports_last_frame` yorumunda: son kare bir referans değil ayrı bir
    # eksen, o kanal da video tarafında üç ayrı kapıyla zaten kapalı.
    last_file: UploadFile | None = File(None),
    last_source_id: str | None = Form(None),
    folder_id: str | None = Form(None),
    session_id: str | None = Form(None),
    model: str = Form(""),
) -> dict:
    """Görsel → video: bir kareyi hareketlendirir.

    `/api/edit`in kalıbı AYNEN kullanılıyor — `_collect_edit_refs` de aynen,
    yeniden yazılmadan. O işlev "ana görsel → ek yüklemeler → ek galeri
    görselleri" sırasını ve `parent_id` türev zincirini zaten kuruyor; video
    tarafında yalnız TAVAN farklı ve o tavan katalogdan geliyor
    (`max_refs=1`, yani ilk kare). Kapı `refs` toplandıktan SONRA: erken
    davranmak, `_collect_edit_refs`in kendi 413/422 mesajlarını
    ikizlemek olurdu.

    Referans PNG'ye çevriliyor (`_to_png`, `_collect_edit_refs`in içinde) ve
    `source_id` yolu `_output_png_path`ten okuyor — o işlev PNG'de çakılı
    KALIYOR ve bu doğru: bir videoyu ilk kare olarak göndermek anlamsız,
    404 doğru cevap (bkz. `_output_media_path`in docstring'i).
    """
    # BOŞ FORM ALANI "VERİLMEDİ" DEMEK. Bütün alanlarını koşulsuz serileştiren
    # bir istemci `last_source_id=""` yolluyor ve `is not None` onu "bitiş
    # görseli var" sayardı: yeteneği olmayan bir modelde hiç bitiş karesi
    # TAŞIMAYAN bir istek 422 yer, yetenekli modelde `_output_png_path("")`
    # 404 döner — ikisi de kullanıcının yapmadığı bir şeyi anlatan mesajlar.
    # `_extra_refs` galeri id'lerini tam bu yüzden `v.strip()` ile süzüyor.
    # Normalleştirme kapıdan ÖNCE: kapı ile rota AYNI değeri görmek zorunda.
    #
    # `last_file`in İKİZİ YOK ve gerekmiyor: dosya adı olmayan bir parçayı
    # Starlette `str` olarak çözüyor, declared `UploadFile | None` da onu daha
    # buraya varmadan 422 yapıyor (`_extra_refs`in ham formu okumasının
    # gerekçesi tam bu). Ana karenin `file` alanı da aynı davranıyor — burada
    # ayrı bir süzgeç açmak iki kardeş alanı sessizce ayrıştırırdı.
    last_source_id = (last_source_id or "").strip() or None
    model_id = _check_video_form(prompt, size, quality, duration, n,
                                 file, source_id, model,
                                 last_file, last_source_id)
    spec = catalog.video_model(model_id)
    target_folder = _check_folder(folder_id)
    session = _check_session(session_id)
    refs, parent_id = await _collect_edit_refs(request, file, source_id)
    if len(refs) > spec.max_refs:
        raise HTTPException(
            status_code=422,
            detail=f"{spec.label} en fazla {spec.max_refs} referans görsel "
                   "alıyor (ilk kare).")
    # Son kare `refs`e KATILMIYOR: `max_refs` sayacı "kaç referans" sorusunun
    # cevabı ve son kare o sorunun konusu değil. Katsaydı yukarıdaki kapı
    # bitiş görseli seçen HER isteği 422 yapardı.
    #
    # PNG'ye çevirme `_collect_edit_refs`in kullandığı AYNI iki yardımcıyla —
    # ikinci bir okuma yolu yazmak, birinde `_to_png` çağrısını unutmakla
    # biten türden bir ayrışma olurdu. `_output_png_path` uzantıyı PNG'de
    # çakılı tutuyor, yani bir VİDEO id'si burada da 404: bir mp4'ü son kare
    # olarak göndermenin karşılığı yok (ana karenin aynı kararı).
    son_kare = None
    if last_source_id is not None:
        son_kare = _read_png_file(_output_png_path(last_source_id))
    elif last_file is not None:
        son_kare = await _read_upload_png(last_file)

    try:
        videos = providers.animate_video(model_id, prompt, refs, size, quality,
                                         duration, n, last_frame=son_kare)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    kredi = catalog.cost_for(spec, quality, duration=duration)
    records = [
        storage.save(vid, {"prompt": prompt, "size": size, "quality": quality,
                           "parent_id": parent_id, "folder_id": target_folder,
                           "palette": None, "session_id": session,
                           "kind": "video", "duration": duration,
                           "model": model_id, "credits": kredi,
                           "prompt_sent": None},
                     OUTPUT_DIR, now=_now())
        for vid in videos
    ]
    return {"videos": records}


def _check_edit_form(prompt: str, size: str, quality: str, n: int,
                     file: UploadFile | None, source_id: str | None,
                     palette_mode: str, palette_strength: str,
                     model: str = "") -> str:
    """`/api/edit` form alanlarını doğrular; geçersizse HTTPException(422).

    NORMALLEŞTİRİLMİŞ model id'sini döndürüyor (boş girdi → varsayılan), tıpkı
    `models.check_capabilities` gibi: kaydedilen değer ile doğrulanan değer
    ayrışmasın.

    Doğrulama neden elle: uç multipart olduğu için GenerateRequest gibi tek bir
    Pydantic modeli yok. Not: multipart'ta `extra="forbid"` karşılığı YOK —
    Starlette bilinmeyen form alanını sessizce atar. Bayat sunucu tespiti bu
    yüzden arayüz tarafında, yanıtın alanı geri yansıtıp yansıtmadığına
    bakılarak yapılıyor (palet için v1.10'dan beri; `model` için de aynı desen,
    ama orada karşılaştırma DEĞERİN kendisi üzerinden — yanlış model sessizce
    geçerse kullanıcı hem beklediği estetiği hem doğru faturayı kaybeder).

    Yetenek kapısı `models.check_capabilities` ile PAYLAŞILIYOR: JSON ucu onu
    pydantic içinden çağırıyor, bu uç buradan. İki kopya, iki ucun sessizce
    ayrışması demek olurdu.
    """
    try:
        model_id = check_capabilities(model, size, quality, n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    spec = catalog.image_model(model_id)
    if not spec.supports_edit:
        raise HTTPException(status_code=422,
                            detail=f"{spec.label} referans görselle çalışmıyor.")
    # Küresel tavan, model tavanının ÜSTÜNDE: `MAX_IMAGES_PER_RUN` aynı zamanda
    # bir sonuç kaydının azami `image_ids` uzunluğu (bkz. models.py), yani onu
    # aşan bir değer dökümü bozar. Buradaki sayı v0.6'ya kadar ELLE yazılmış
    # `4` idi — `MAX_IMAGES_PER_RUN` için ikinci bir literal, yani sessiz bir
    # kayma kaynağı; model tavanı devreye girerken sabite bağlandı.
    if not (1 <= n <= min(spec.max_n, MAX_IMAGES_PER_RUN)):
        raise HTTPException(
            status_code=422,
            detail=f"n 1-{min(spec.max_n, MAX_IMAGES_PER_RUN)} arasında olmalı.")
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
    return model_id


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
    # Düzenlemenin doğduğu oturum; boş = oturum dışı (bkz. _check_session).
    session_id: str | None = Form(None),
    # Boş = varsayılan model. `Form("")` ve zorunlu DEĞİL: bugünkü arayüz alanı
    # hiç göndermiyor ve göndermeyen bir istemci bugünkü davranışı aynen
    # almalı. Bayat SUNUCU tarafı bu uçta pydantic ile korunamıyor (Starlette
    # bilinmeyen form alanını sessizce atıyor), o yüzden koruma yanıtın alanı
    # geri yankılamasıyla kuruluyor — bkz. _check_edit_form'un docstring'i.
    model: str = Form(""),
) -> dict:
    """Ek referans görselleri (`extra_files` yüklemeleri, `extra_source_ids`
    galeri id'leri) form verisinden okunur — bkz. _extra_refs."""
    model_id = _check_edit_form(prompt, size, quality, n, file, source_id,
                                palette_mode, palette_strength, model)
    spec = catalog.image_model(model_id)
    palette_hex = _check_palette_hex(palette_hex)
    drop = _check_palette_drop(palette_drop)

    target_folder = _check_folder(folder_id)
    session = _check_session(session_id)
    refs, parent_id = await _collect_edit_refs(request, file, source_id)

    # task="edit": üretim ifadesi modele yeniden boyama söyler ve referans
    # görselin kompozisyonunu yok eder; düzenlemede istenen renk derecelendirmesi.
    prompt_sent, pal = _palette_prompt(prompt, palette_hex, palette_mode,
                                       palette_strength, palette_id, task="edit",
                                       drop=drop)
    try:
        images = providers.edit(model_id, prompt_sent, refs, size, quality, n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    kredi = catalog.cost_for(spec, quality)
    records = [
        storage.save(img, {"prompt": prompt, "size": size, "quality": quality,
                           "parent_id": parent_id, "folder_id": target_folder,
                           "palette": pal, "session_id": session,
                           "model": model_id, "credits": kredi,
                           "prompt_sent": prompt_sent if pal and pal["applied"] else None},
                     OUTPUT_DIR, now=_now())
        for img in images
    ]
    return {"images": records}


def _model_available(configured: bool, plan: str) -> bool:
    """Bu model kullanıcıya GÖRÜNÜYOR mu — arayüzün sorduğu TEK soru.

    Görünmeme sebebi bugün tek: anahtar kayıtlı değil. Kredi/üyelik sistemi
    geldiğinde ikincisi ekleniyor — "kullanıcının planı bu modeli kapsamıyor" —
    ve o gün DEĞİŞECEK YER BURASI, istemci değil. Filtrenin istemcide olduğu
    bir dünyada iki sebebi ayrı ayrı sormak gerekirdi ve "hangi modeller
    görünür" sorusunun iki cevabı doğardı; `static/core.js secilebilirler`in
    var olma sebebi tam olarak o ikiliği önlemek.

    `plan` BUGÜN OKUNMUYOR ve bu bilinçli: parametre imzada duruyor çünkü
    kancanın YERİ burası, ama plan tablosu (kim hangi abonelikte) henüz yok —
    kullanıcı modeli, kimlik doğrulama ve bakiye SaaS dönüşümüne bağlı
    (docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md).
    Uydurma bir eşleştirme yazmak, olmayan bir gerçeği kodlamak olurdu.
    """
    return configured


def _provider_logo_url(provider: str) -> str | None:
    """Sağlayıcı işaretinin ADRESİ — katalogdaki dosya adı + sürüm damgası.

    `?v=` cache-buster'ı `index()`in desenini tekrarlıyor ve gerekçesi de aynı:
    işaretin çizimi bir gün değişirse kullanıcının tarayıcısı eski dosyayı
    sunmasın. Adresi SUNUCU kuruyor, istemci değil — `settings.js`in sürüm
    alanını okuyup ikinci bir yerde dize birleştirmesi, aynı bilginin iki
    kopyası olurdu (core.js ile settings.js arasında da üst düzey ad çakışması
    üretirdi, bkz. tests/test_id_contract.py).

    Tanımsız sağlayıcıda None: katalogdaki `provider_logo`'nun sessiz yolu
    burada da korunuyor, istemci `logo` boşsa işareti hiç çizmiyor.
    """
    ad = catalog.provider_logo(provider)
    return f"/static/img/providers/{ad}?v={version.APP_VERSION}" if ad else None


def _model_payload(m: catalog.ImageModel, cfg: dict, kisa: dict) -> dict:
    """Bir görsel/video modelinin arayüze giden hâli.

    ÇIKARILDI, kopyalanmadı: `image_models` ve `video_models` listelerinin
    ikisi de bu sözlüğü kuruyor ve elle iki kez yazmak, birine alan ekleyip
    ötekini unutmanın kapısı olurdu — `catalog.ASPECT_RATIOS`in paylaşılma
    gerekçesinin aynısı. Bugün ölçülebilir sonucu şu: `requires_plan` ya da
    `logo` bir gün değişirse iki şerit birlikte değişiyor.

    Jetonlar ETİKETLERİYLE gönderiliyor, çıplak dize değil: arayüz `<option>`
    listelerini bunlardan kuruyor ve etiketi istemcide tutmak `SIZE_RATIO`'nun
    bayatlayan aynası olurdu. `ratio` de sunucudan geliyor çünkü Gemini'nin
    jetonları `WxH` biçiminde DEĞİL — istemci ayrıştırma yapmamalı.
    """
    return {
        "id": m.id,
        "label": m.label,
        # ŞERİDİN adı ayrı bir alan: `label` hata metinlerinin ve
        # `#model-note`un okuduğu TAM ad ve orada marka ayırt edici
        # kalıyor (katalogda iki `gpt-image-2` var).
        "short_label": kisa[m.id],
        "provider": m.provider,
        "sizes": [{"value": s, "label": catalog.geometry_of(s)[0],
                   "ratio": catalog.geometry_of(s)[1]} for s in m.sizes],
        "qualities": [{"value": q, "label": catalog.quality_label(q)}
                      for q in m.qualities],
        "quality_hidden": m.quality_hidden,
        # SÜRE EKSENİ. Görsel modellerinde boş liste + 0, yani arayüz için
        # "bu knob yok" — `quality_hidden`ın kurulmuş kalıbının aynısı, tek
        # farkı bayrak yerine LİSTENİN BOŞLUĞUNUN işaret olması (boş bir
        # eksen için ayrı bir `duration_hidden` bayrağı ikinci bir gerçek
        # kaynağı olurdu).
        "durations": [{"value": d, "label": catalog.duration_label(d)}
                      for d in m.durations],
        "default_duration": catalog.default_duration_of(m),
        "default_size": catalog.default_size_of(m),
        "default_quality": catalog.default_quality_of(m),
        "max_n": m.max_n,
        "supports_edit": m.supports_edit,
        "max_refs": m.max_refs,
        # SON KARE yeteneği AYRI bir anahtar, `max_refs`in bir değeri değil:
        # arayüz "bitiş görseli yuvasını çizeyim mi" sorusunu buradan soruyor
        # ve sayıdan türetmek, ikinci referans ile son kareyi aynı sayının
        # arkasına saklamak olurdu (gerekçenin uzunu katalogda).
        "supports_last_frame": m.supports_last_frame,
        # Video modellerinde SANİYE BAŞINA (bkz. catalog.ImageModel.credits).
        # Arayüz farkı `durations`ın boş olup olmamasından biliyor ve süreyle
        # çarpıyor — ikinci bir birim alanı göndermek, aynı bilgiyi iki
        # yoldan taşımak olurdu.
        "credits": m.credits,
        "credits_by_quality": dict(m.credits_by_quality),
        "note": m.note,
        # Sağlayıcı işaretinin adresi (yoksa None). Şerit yalnız SEÇİLİ
        # modelin işaretini çiziyor: native <option> görsel taşımıyor
        # (bkz. core.js renderModelOptions).
        "logo": _provider_logo_url(m.provider),
        # TEK türetilmiş alan: modelin anahtarı GİRİLMİŞ mi. Arayüzün
        # "#go kilitli mi" kararı ve "anahtar gerekli" etiketi bundan geliyor.
        "configured": cfg.get(m.credential, False),
        # GÖRÜNÜRLÜK kararı — arayüzün filtresi YALNIZ bunu okuyor.
        # Bugün `configured` ile birebir aynı; ayrımın gerekçesi
        # _model_available'da yazılı. `configured` KALIYOR çünkü MESAJ ondan
        # geliyor: "anahtar yok" ile "planın kapsamıyor" aynı cümle değil.
        "available": _model_available(cfg.get(m.credential, False), m.plan),
        # Bugün her modelde "free". Arayüz bir gün "Pro" rozetini bundan
        # çizecek; alan şimdiden akıyor ki o gün şema değişikliği gerekmesin.
        "requires_plan": m.plan,
    }


def _settings_payload() -> dict:
    """Kimlik DURUMU + hangi modeller var + hangileri kullanılabilir.

    `ac.get_settings_status()` GENİŞLETİLMEDİ, üzerine BURADA ekleniyor —
    `version`'ın aynı gerekçesi (o fonksiyonun docstring'i): `azure_client`'ın
    işi kimlik bilgisi, hangi modellerin var olduğunu bilmesi gereksiz bir bağ
    olurdu ve tests/test_settings.py'deki sözleşmesini genişletirdi. Mevcut
    anahtarların HEPSİ adıyla ve anlamıyla korunuyor, yani `settings.js` ve
    tests/test_settings_route.py etkilenmiyor.

    Bu fonksiyon GET ve POST'un PAYLAŞTIĞI gövde. `version`/`guncelleme`/
    `chat_instructions_path` bilerek DIŞINDA: onlar yalnız GET'te var (sürüm
    çalışma anında değişmiyor, mutasyon ucundan yansıtmak gürültü olurdu) ve
    settings.js'in `!== undefined` guard'ları tam olarak o daha dar POST
    gövdesine dayanıyor.

    ANAHTAR TAŞIMIYOR. `providers` yalnız boolean, `image_models[].configured`
    de öyle. Anahtarın son dört hanesi, uzunluğu ya da maskelenmiş hâli DE
    dönmüyor: `get_settings_status`'un sözleşmesi "API key'i ASLA döndürmez" ve
    "sadece son dört hane" o sözleşmenin öldüğü yerdir.
    """
    cfg = credstore.configured_map()
    chat_cfg = credstore.chat_configured_map()
    # Şeritte gösterilecek KISA adlar: sağlayıcı markası işaretle geldiği için
    # etiketten düşüyor. Liste bütününden hesaplanıyor (çakışma kuralı için),
    # o yüzden model başına değil bir kez (bkz. catalog.short_labels).
    kisa_gorsel = catalog.short_labels(catalog.IMAGE_MODELS)
    kisa_sohbet = catalog.short_labels(catalog.CHAT_MODELS)
    # Video şeridinin kısa adları AYRI hesaplanıyor, görselle BİRLİKTE değil:
    # `short_labels`ın çakışma kuralı verilen listenin BÜTÜNÜNE bakıyor ve
    # iki şeridi birleştirmek, ayrı seçicilerde duran iki modelin birbirine
    # marka öneki taktırması olurdu (kullanıcı hiçbir zaman aynı listede
    # `Veo 3.1` ile bir görsel modelini yan yana görmüyor).
    kisa_video = catalog.short_labels(catalog.VIDEO_MODELS)
    return {
        **ac.get_settings_status(),
        # {kimlik_id: bool}. Arayüz Ayarlar'daki sağlayıcı gruplarının
        # "Kayıtlı" durumunu buradan okuyor.
        "providers": cfg,
        "default_image_model": catalog.DEFAULT_IMAGE_MODEL,
        # Video şeridi. ANAHTARIN AYRI OLMASI şart: `image_models`a katmak,
        # bugün o listeyi okuyan her yerin (model kartları, arena sütun
        # seçicisi, `secilebilirler` süzgeci) videoyu görsel sanması demekti —
        # `catalog.VIDEO_MODELS`in ayrı bir demet olma gerekçesinin ön yüz
        # tarafındaki karşılığı.
        "default_video_model": catalog.DEFAULT_VIDEO_MODEL,
        "video_models": [_model_payload(m, cfg, kisa_video)
                         for m in catalog.VIDEO_MODELS],
        "image_models": [_model_payload(m, cfg, kisa_gorsel)
                         for m in catalog.IMAGE_MODELS],
        "default_chat_model": catalog.DEFAULT_CHAT_MODEL,
        "chat_models": [
            {"id": m.id, "label": m.label,
             # Görsel şeridiyle AYNI ayrım (bkz. yukarısı).
             "short_label": kisa_sohbet[m.id], "provider": m.provider,
             # `cfg` (KİMLİK tablosu) DEĞİL `chat_cfg` (MODEL tablosu):
             # Azure'ın dağıtım adı model düzeyinde bir koşul ve kimlik
             # tablosu onu ifade edemiyor — kimliği tam, dağıtımı boş bir
             # kurulumda arayüz modeli "kurulu" gösterir ve ilk mesaj 404
             # dönerdi (bkz. credstore.chat_is_configured).
             "configured": chat_cfg.get(m.id, False),
             # Görsel şeridiyle AYNI alan, aynı gerekçe (_model_available).
             "available": _model_available(chat_cfg.get(m.id, False), m.plan),
             "requires_plan": m.plan,
             # Ayarlar formunun dağıtım adı kutusunun kapısı: KATALOGDAN
             # türetiliyor, istemcide sağlayıcı adı literal olarak
             # sayılmıyor. Sayılsaydı, adı ortamdan okunan ikinci bir
             # sağlayıcı eklendiği gün kutu sessizce görünmez kalırdı.
             "needs_deployment": catalog.chat_needs_deployment(m),
             # Görsel şeridiyle AYNI alan adı ve aynı gerekçe.
             "logo": _provider_logo_url(m.provider),
             "note": m.note}
            for m in catalog.CHAT_MODELS
        ],
        # `ac.get_settings_status()`in AYNI ADLI alanını BİLEREK eziyor (bu
        # anahtar `**`ın sonrasında). O alan yalnız Azure'ı ölçüyor ve tek
        # sağlayıcı varken doğruydu; bugün yalnızca Gemini anahtarı olan bir
        # kullanıcıda Prompt Yönetmeni'ni kapalı gösterirdi. Ölçüt artık
        # "konuşulabilir EN AZ BİR sohbet modeli var mı".
        #
        # `azure_client` tarafındaki alan KALDIRILMADI: onun sözleşmesi
        # tests/test_settings.py'de donmuş ve orada "Azure sohbeti hazır mı"
        # sorusunun doğru cevabı hâlâ o.
        "chat_configured": any(chat_cfg.values()),
    }


@app.get("/api/settings")
def get_settings() -> dict:
    """Yapılandırma durumu + uygulama sürümü. API key asla dönmez.

    `version` BURADA birleştiriliyor, azure_client'ta DEĞİL: onun işi kimlik
    bilgisi, uygulama sürümünü bilmesi gereksiz bir bağ olurdu ve
    tests/test_settings.py'deki get_settings_status sözleşmesini genişletirdi.

    Destek sorusu "hangi sürümdesiniz?" v1.8'de cevaplanamıyordu — sürüm
    yalnızca Info.plist'te vardı ve arayüz onu hiç göstermiyordu.

    `chat_instructions_path` da burada birleşiyor: talimatı ezme özelliği
    keşfedilebilir olmasa var olmakla olmamak arasında bir fark kalmaz. Video
    bölümünün ezmesi AYRI bir yol ve o da burada, aynı gerekçeyle: iki dosya
    ayrı çünkü video talimatı sistem mesajına yalnız video modeli
    yapılandırılmışsa giriyor (bkz. chat_prompt.build_system).

    `guncelleme` de burada: kullanılan sürümün YANINDA durması gerekiyor, çünkü
    kullanıcının sorduğu şey "hangi sürümdeyim" değil "güncel miyim". Ayrı bir
    uç nokta arayüze ikinci bir istek ekler ve ikisi ayrı zamanlarda gelirse
    panel bir an "0.4.2 — güncel" deyip sonra fikir değiştirirdi.

    Bu alan istek yolunu BEKLETMEZ: `guncelleme.bilgi()` yalnız önbelleğe
    bakıyor, ağ çağrısı arka planda koşuyor (bkz. guncelleme.py'deki 2.
    sözleşme). İlk açılışta değeri `null` olur, sonrakinde dolar.
    """
    return {**_settings_payload(),
            "version": version.APP_VERSION,
            "guncelleme": guncelleme.bilgi(
                OUTPUT_DIR, izin=prefs.read(OUTPUT_DIR)["guncelleme_kontrolu"]),
            "chat_instructions_path": paths.chat_instructions_override(),
            "chat_video_instructions_path":
                paths.chat_video_instructions_override()}


@app.get("/api/guncelleme")
def get_guncelleme() -> dict:
    """Yalnız güncelleme cevabı — `/api/settings`'in ARDIL okuması.

    NEDEN AYRI BİR UÇ: `guncelleme.bilgi()` bayat önbellekte tazelemeyi arka
    plana atıp `None` döner (guncelleme.py'nin 2. sözleşmesi). Modül bunu
    "birkaç saniye sonrakinde gerçek cevap gelir" diye yazmıştı, ama ön yüz
    `/api/settings`'i YALNIZ açılışta bir kez soruyor (settings.js'nin tek
    `loadSettings(true)` çağrısı) — yani "sonraki" istek hiç gelmiyordu ve
    tazelenen cevap BİR SONRAKİ uygulama açılışına kadar diskte kalıyordu.
    Kullanıcı tarafından bakıldığında bu, "bildirim hiç gelmiyor"dan ayırt
    edilemez.

    Alan `/api/settings`'ten KALDIRILMADI ve kaldırılmamalı: oradaki gerekçe
    (sürüm satırıyla aynı yanıtta gelmezse panel bir an "güncelsin" deyip fikir
    değiştirir) ilk çizim için hâlâ geçerli. Bu uç onun YERİNE değil ARDINDAN
    geliyor — çağrıldığı anda sürüm zaten çizilmiş oluyor, dolayısıyla
    "fikir değiştirme" durumu doğmuyor.

    Ön yüz bunun için `/api/settings`'i yeniden çağıramaz: o yanıt
    `applyConfigured()` üzerinden formun tamamını yeniden yazıyor ve
    kullanıcının o sırada doldurduğu alanları ezerdi.

    İstek yolunu BEKLETMEZ — `/api/settings` ile aynı çağrı, aynı önbellek.
    """
    return {"guncelleme": guncelleme.bilgi(
        OUTPUT_DIR, izin=prefs.read(OUTPUT_DIR)["guncelleme_kontrolu"])}


@app.post("/api/settings")
def post_settings(req: SettingsRequest) -> dict:
    """Sağlayıcı kimliklerini yalnızca-yazılır kaydeder; durumu döndürür (key'siz).

    Gizli alanda boş değer "mevcut korunur" demek — istemci kayıtlı anahtarı hiç
    görmediği için boş bir kutu "sildim" değil "dokunmadım"dır. Adres
    alanlarında boş "varsayılana dön" demek; ayrım her ikisinin de yazıldığı
    döngülerde yorumlu.

    Azure kimliği artık YALNIZ istek onu hedeflediğinde zorunlu (bkz. gövdedeki
    `azure_hedefli`): eskiden ilk kurulumda koşulsuz zorunluydu ve yalnızca
    başka bir sağlayıcının anahtarını girmek isteyen kullanıcı hiçbir şey
    kaydedemiyordu.

    Sohbet dağıtımı ve öteki sağlayıcılar, görsel kimliği doğrulamadan GEÇTİKTEN
    SONRA yazılıyor: geçersiz bir endpoint'le gelen istek hiçbir şey yazmadan
    422 dönmeli.
    """
    api_key = req.api_key.strip()
    base_url = (req.base_url or "").strip()
    # İSTEK AZURE'U HEDEFLİYOR MU: iki alandan biri doluysa evet. Bu ayrım
    # v0.6'da açıldı ve sebebi somut bir kilitti — kural "ilk kurulumda Azure
    # api_key + base_url ZORUNLU" biçimindeydi, yani yalnızca Gemini anahtarı
    # olan bir kullanıcı HİÇBİR ŞEY kaydedemiyordu ve aldığı 422 bambaşka bir
    # sağlayıcıdan söz ediyordu ("İlk kurulumda API key gerekli"). Çoklu
    # sağlayıcının önündeki en somut engel buydu.
    azure_hedefli = bool(api_key or base_url)

    # Mevcut Azure kimliği. Hata YÜKSELTİLMİYOR: Azure'ın hiç yapılandırılmamış
    # olması artık bir hata durumu değil, sıradan bir başlangıç hâli.
    try:
        mevcut_key, mevcut_url = ac.load_credentials()
    except ac.ImageError:
        mevcut_key, mevcut_url = "", ""
    # "Boş = mevcut korunur" kuralı KORUNUYOR (v1.x davranışı).
    api_key = api_key or mevcut_key
    base_url = base_url or mevcut_url

    if azure_hedefli:
        # Azure hedefleniyorsa İKİSİ de gerekli. Mesajlar bilerek ayrı: hangi
        # alanın eksik olduğunu söylemeyen bir hata kullanıcıyı formda arattırır.
        if not api_key:
            raise HTTPException(status_code=422, detail="İlk kurulumda API key gerekli.")
        if not base_url:
            raise HTTPException(status_code=422, detail="İlk kurulumda base_url gerekli.")

    try:
        # Kimlik doğrulaması DİĞER alanların yazımından ÖNCE: geçersiz bir
        # endpoint'le gelen istek hiçbir şey yazmadan 422 dönmeli
        # (tests/test_settings_route.py bu sırayı sabitliyor).
        if azure_hedefli and api_key and base_url:
            ac.save_credentials(api_key, base_url)
        updates = {}

        if req.chat_deployment is not None:
            updates[ac.CHAT_DEPLOYMENT] = req.chat_deployment.strip()

        # GİZLİ alanlar: boş gönderim "mevcut korunur" demek, silme DEĞİL.
        # (Yalnızca-yazılır formun kuralı: istemci kayıtlı anahtarı hiç
        # görmüyor, o yüzden boş bir kutu "sildim" değil "dokunmadım"dır.)
        # Alan adı → env adı eşlemesi KATALOGDAN geliyor, elle sayılmıyor:
        # elle sayılan liste tam olarak redaksiyonun kaçırdığı hataydı.
        for cred in catalog.CREDENTIALS:
            if not cred.secret_field or cred.secret_field == "api_key":
                continue    # api_key yukarıda, kendi doğrulama yolundan geçiyor
            deger = getattr(req, cred.secret_field, None)
            if deger is not None and deger.strip():
                updates[cred.key_env] = deger.strip()

        # ADRES alanları: gizli DEĞİL ve boş gönderim "varsayılana dön" demek,
        # o yüzden `is not None` yeterli (gizli alanların aksine).
        #
        # TEK İSTİSNA ve gerekçesi kataloğun KENDİSİNDEN okunuyor:
        # `default_base_url`ü OLMAYAN kimlikte (bugün yalnız azure_image)
        # düşülecek bir varsayılan yok — orada boş adres "varsayılana dön"
        # değil "bağlantıyı kopar" demek olurdu. O yüzden boş kutu, gizli
        # alanlarla AYNI kuralı izliyor: "dokunmadım".
        #
        # Gerekçe simetri değil, ÖLÇÜLEN veri kaybı: yukarıdaki
        # `save_credentials` boş `base_url`de bilerek atlanıp mevcut
        # endpoint'i KORUYOR, ama bu döngü hemen ardından onu "" ile
        # eziyordu — tek istekte biri koruyup öteki siliyordu. İstemci
        # `base_url`i KOŞULSUZ gönderiyor (static/settings.js → saveSettings)
        # ve boş-adres kapısı yalnız sağlayıcı "azure" seçiliyken kuruluyor,
        # yani yalnızca OpenAI anahtarı kaydeden bir kullanıcı çalışan Azure
        # kurulumunu 200 alarak siliyordu.
        #
        # Yetenek KAYBI yok: boş endpoint hiçbir zaman "bağlantıyı kes"
        # gestürü değildi — istemci onu "Endpoint gerekli." ile reddediyor.
        for cred in catalog.CREDENTIALS:
            if not cred.url_field:
                continue
            deger = getattr(req, cred.url_field, None)
            if deger is None:
                continue
            if not deger.strip() and not cred.default_base_url:
                continue
            # ŞEMA KAPISI: Azure'ın adresinde ilk günden beri var olan denetim
            # (bkz. ac.check_base_url) öteki sağlayıcılarda YOKTU — şemasız bir
            # yapıştırma 200 alıyor, hata ancak ilk üretimde ve "bağlanılamadı"
            # kılığında görünüyordu. Boş değer bu kapıdan MUAF: yukarıdaki iki
            # satır onu zaten "varsayılana dön" olarak geçirdi.
            if deger.strip():
                ac.check_base_url(deger.strip(), cred.url_field)
            updates[cred.url_env] = deger.strip()

        # Kataloğa girmemiş eski BYOK alanları. Katalog döngüsünün DIŞINDA
        # bilerek: bunların henüz bir modeli ve adaptörü yok, kataloğa yazmak
        # "bağlı" gibi görünmelerine yol açardı. Yazma yolu korunuyor çünkü
        # v0.2.0'dan beri kaydediliyorlar ve veri kaybı olmamalı.
        #
        # `fal_key` BURADAN ÇIKTI: adaptörü geldi, kataloğa girdi ve yukarıdaki
        # `for cred in catalog.CREDENTIALS` döngüsü onu aynı env'e aynı
        # "boş = dokunma" kuralıyla yazıyor — üstelik redaksiyonu da
        # kendiliğinden kapsıyor.
        if req.replicate_api_token is not None and req.replicate_api_token.strip():
            updates["REPLICATE_API_TOKEN"] = req.replicate_api_token.strip()
        # Aynı şema kapısı burada da: bu ikisi katalog döngüsünün DIŞINDA
        # (henüz modelleri yok) ve boş değer yine "temizle" demek.
        if req.comfyui_url is not None:
            if req.comfyui_url.strip():
                ac.check_base_url(req.comfyui_url.strip(), "comfyui_url")
            updates["COMFYUI_URL"] = req.comfyui_url.strip()
        if req.ollama_url is not None:
            if req.ollama_url.strip():
                ac.check_base_url(req.ollama_url.strip(), "ollama_url")
            updates["OLLAMA_URL"] = req.ollama_url.strip()

        if updates:
            ac.save_env(updates)
    except ac.ImageError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _settings_payload()



def _model_facts(m: catalog.ImageModel) -> dict:
    """Yönetmene giden model olguları — İKİ okuyanın ortak sözlüğü.

    Satır içi bir sözlükken yalnız bağlam bloğu okuyordu; model menüsü açılınca
    ikinci okuyan geldi ve elle yazılmış iki kopya kaçınılmaz olarak ayrışırdı
    (bağlam bloğuna bir eksen eklenip menüye eklenmemesi, yönetmenin seçili
    modelde bildiği bir şeyi öteki modellerde bilmemesi demek olurdu).
    Çıkarma, `_model_payload`ın "ÇIKARILDI, kopyalanmadı" gerekçesinin aynısı.

    `_model_payload` BURADA KULLANILAMAZ ve bu bir tembellik değil: o sözlük
    arayüzün sözleşmesi (etiket/değer çiftleri, logo adresi, `credits_by_quality`,
    `short_label`) ve sistem mesajına girdiğinde HER TURDA ödenen ölü karakter
    olurdu — bu yüzeyde prompt caching yok.

    `id` alanı ZORUNLU ve yeni: yönetmen artık model ÖNERİYOR, ön yüz de
    önerilen id'yi uyguluyor. Onsuz menü okunabilir ama işe yaramaz olurdu.
    """
    return {"id": m.id, "label": m.label, "kind": m.kind,
            "sizes": m.sizes, "qualities": m.qualities,
            "quality_hidden": m.quality_hidden, "max_n": m.max_n,
            "supports_edit": m.supports_edit, "max_refs": m.max_refs,
            "durations": m.durations, "supports_last_frame": m.supports_last_frame,
            "credits": m.credits}


def _director_context() -> dict:
    """Yönetmenin sistem mesajına giren TUR bağlamı: seçili model + menü + yönlendirme.

    Bağlamı burada toplamanın sebebi katman kuralı: `chat_prompt` yalnızca
    diski okuyor (katman 1, tek bağımlılığı `paths`) ve `catalog`/`prefs`'e
    bakması onu yukarı çekerdi. Rotada ikisi de hâlihazırda var.

    MODEL BURADA TERCİHTEN okunuyor ve bu, aynı dosyadaki `/api/chat`
    kararının ("model istekten, tercihlerden DEĞİL") istisnası değil TAMAMLAYANI:
    o karar yönetmenin konuşacağı SOHBET modeliyle ilgili ve tel üzerinde
    geliyor; buradaki ise kullanıcının üretimde kullanacağı GÖRSEL modeli, yani
    yönetmenin hangi jetonları önerebileceği. İstemci onu bu uçta göndermiyor
    (`ChatRequest` `extra="forbid"`) ve göndermesi de gerekmiyor: `prefs.json`
    o seçimin zaten TEK kaynağı (bkz. prefs.py'nin "hangi modeli İSTİYORUM"
    kuralı).

    Bilinmeyen/bayat bir tercih sessizce bağlamsız kalıyor — `prefs.read`
    katalog üyeliğini zaten kapıyor, ama `image_model` yine None dönebilir ve
    o durumda doğru davranış bugünkü davranıştır: bağlamsız persona.

    MENÜ (`available_models`) seçili modelin YANINDA duruyor, onun yerine
    değil: bağlam bloğu "bu turda hangi jetonlar geçerli" sorusunu, menü
    "hangi modele GEÇİLEBİLİR" sorusunu cevaplıyor ve ikisi farklı sorular.

    Süzgeç `_model_available`, ikinci bir "eksik mi" mantığı DEĞİL: arayüzün
    gösterdiği küme ile yönetmenin gördüğü küme ayrışsaydı yönetmen
    kullanıcının ekranında olmayan bir modeli önerirdi — o fonksiyonun var
    olma gerekçesi tam olarak bu ikiliği önlemek. `credstore.configured_map()`
    de altı kimliği BİR kez çözüyor; model başına `providers.is_configured`
    çağırmak aynı dosyayı on üç kez okumak olurdu.

    `selected` `_model_facts`in İÇİNDE değil çünkü o bir MODEL olgusu değil bu
    TURUN olgusu — aynı sözlüğün iki bağlamda kullanılabilmesinin şartı bu
    ayrım. İki tercih birden işaretleniyor: video modu Yönetmen'e kapalı
    olmadığı için kullanıcının video seçimi de "seçili" sayılmalı.
    """
    p = prefs.read(OUTPUT_DIR)
    m = catalog.image_model(p["image_model"])
    cfg = credstore.configured_map()
    secili = {p["image_model"], p["video_model"]}
    # GÖRSEL + VİDEO tek listede: `catalog.video_model`in "birleşik arama YOK"
    # kuralı id ile ARAMA hakkında (yanlış türü doğru sanan bir çağıranı
    # sessizce geçirirdi); burada arama değil sıralı gösterim var ve tür her
    # satırda `kind` alanıyla açıkça taşınıyor.
    menu = [{**_model_facts(x), "selected": x.id in secili}
            for x in catalog.IMAGE_MODELS + catalog.VIDEO_MODELS
            if _model_available(cfg.get(x.credential, False), x.plan)]
    return {"model_facts": _model_facts(m) if m is not None else None,
            "guidance": p["director_guidance"], "available_models": menu}


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

    Tel mesajlarını `models.wire_messages` kuruyor ve o bir SÜZGEÇ DEĞİL
    ÇEVİRMEN: `display` gibi arayüz alanlarını allowlist'le dışarıda tutmaya
    devam ediyor (çıplak `model_dump()` onları tele koyar ve istek 400 döner),
    ama `result` kayıtlarını artık DÜŞÜRMÜYOR — kısa bir nota çeviriyor, çünkü
    yönetmenin ne ürettiğini bilmesi gerekiyor.

    `chat_client.build_payload`'ın kendi rol/alan süzgeci YERİNDE DURUYOR ve
    gövdesine dokunulmadı: o telin gerçek sınırı, yani son savunma. Çevirmen
    bir gün yeni bir rolü çevirmeyi unutursa istek yine 400 almasın diye.

    ÇAĞRI ARTIK SEVK MEMURUNDAN geçiyor (`chat_providers`), doğrudan
    `chat_client`'tan değil: yönetmen üç sağlayıcı konuşabiliyor ve hangisinin
    konuşulacağı `req.model`'da. Azure yolunun tel üzerindeki baytları
    DEĞİŞMEDİ — sevk memuru model tanımını düşürüp `cc.complete`'e aynen
    devrediyor (bkz. chat_providers._azure_complete).
    """
    try:
        # MODEL İSTEKTEN, tercihlerden DEĞİL. `/api/generate`'in aynı duruşu:
        # seçim ekranda yaşıyor ve tel üzerinde geliyor. `prefs.json`'ı ikinci
        # bir kaynak yapmak, kullanıcının bu turda seçtiği modelle sunucunun
        # kullandığı modelin ayrışmasına kapı açardı (tercih yazımı ağ üstünden
        # ve başarısız olabiliyor — bkz. core.js savePref).
        #
        # `or DEFAULT_CHAT_MODEL`: alanı hiç göndermeyen bayat bir istemci
        # bugünkü modele gidiyor. Geçerlilik `ChatRequest`'te ölçüldü, burada
        # ikinci bir kapı yok — `chat_providers._resolve` yine de bilinmeyen
        # id'yi Türkçe bir 502'ye çeviriyor (bayat istemci + katalogdan kalkmış
        # model).
        # `instructions` ARTIK ROTADAN geçiyor. Adaptörler onu zaten
        # destekliyordu (`complete(..., instructions=None)`), yani imza
        # değişmedi — değişen tek şey, `None` bırakıldığında adaptörün diskten
        # okuduğu personanın yerine burada KURULMUŞ olanın gelmesi.
        #
        # `ValueError` → `cc.ChatError`: talimat dosyası bulunamadığında
        # kullanıcının okuduğu metin, `chat_client`'ın kendi dalında ürettiğiyle
        # AYNI kalmalı. İki yerde iki Türkçe cümle olsaydı aynı kusur, çağrının
        # hangi yoldan gittiğine göre iki farklı hata okuturdu.
        # Bağlam TOPLAMA `try`nin DIŞINDA: `prefs.read` da `ValueError`
        # yükseltebiliyor (elle cp1254 kaydedilmiş bir prefs.json'da
        # `json.load` `UnicodeDecodeError` atar ve o bir `ValueError`
        # alt sınıfı; `_read_raw` yalnız `JSONDecodeError`u yakalıyor).
        # Çağrı `try`nin içindeyken kullanıcı bozuk prefs.json yüzünden
        # "Prompt Yönetmeni talimatı yüklenemedi" okuyor, yani YANLIŞ dosyaya
        # yönlendiriliyordu — üstelik aynı arıza `GET /api/prefs`te çıplak
        # 500 veriyor, iki uç aynı kusur için iki farklı şey söylüyordu.
        baglam = _director_context()
        try:
            instructions = chat_prompt.build_system(**baglam)
        except ValueError as e:
            raise cc.ChatError(f"Prompt Yönetmeni talimatı yüklenemedi: {e}")
        return chat_providers.complete(
            req.model or catalog.DEFAULT_CHAT_MODEL,
            wire_messages(req.messages),
            instructions=instructions)
    except cc.ChatError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Kullanıcı tercihleri ────────────────────────────────────────────────

@app.get("/api/prefs")
def get_prefs_route() -> dict:
    """Tercihlerin birleşik görünümü (bkz. prefs.py). Gizli alan taşımıyor."""
    return prefs.read(OUTPUT_DIR)


@app.post("/api/prefs")
def post_prefs_route(req: PrefsRequest) -> dict:
    """Gönderilen tercihleri yazar, diğerlerine dokunmaz; yeni görünümü döndürür.

    Anahtar BİLEREK `/api/settings`'te DEĞİL: o uç kimlik formu ve `api_key` +
    `base_url` istiyor — bir tercihi çevirmek Azure kimliğini yeniden yazmak
    zorunda kalırdı ve Azure hiç yapılandırılmamışken anahtar çevrilemez olurdu.
    Değer de tek yerden okunuyor (`/api/settings` onu YANSITMIYOR): iki uç aynı
    değeri döndürseydi ayrışabilirlerdi.
    """
    values = req.model_dump(exclude_none=True)
    try:
        return prefs.update(values, OUTPUT_DIR)
    except ValueError as e:
        # prefs katmanı da bilinmeyen anahtarı/yanlış türü reddediyor; buraya
        # düşmek pydantic ile prefs şemasının ayrışması demek olur.
        raise HTTPException(status_code=422, detail=str(e))


# ── Kayıtlı oturumlar ───────────────────────────────────────────────────
# Kalıcılık SUNUCUDA, istemcide değil: `desktop.py` pencereyi private mode'da
# açıyor (pywebview varsayılanı) ve orada localStorage her kapanışta silinir —
# paketlenmiş .app'te geçmiş sessizce buharlaşırdı.


def _guard_autosave(title: str | None) -> None:
    """Otomatik yazımı anahtar kapalıyken reddeder (409). Karar D1, güvence (c).

    Ayrımı taşıyan işaret zaten elde: **otomatik kaydın verecek bir ADI yok.**
    Kullanıcı bir oturumu kendisi kaydediyor ya da yeniden adlandırıyorsa istekte
    başlık VAR; tur sonunda kendi kendine büyüyen yazımda YOK. Yani "başlıksız
    yazım = otomatik yazım" ve kapalı anahtarda durduruluyor — adlandırılmış yazım
    her koşulda çalışıyor, yani "kapatınca bugünkü davranış" (v1.15) gerçekten
    sağlanıyor.

    İsteğe "bu otomatik" diye bir bayrak KONMADI: bayat/hatalı bir istemci onu
    yanlış gönderdiğinde anahtar sessizce delinirdi. Başlığın yokluğu ise
    uydurulamaz bir işaret.

    409, 422 değil: gövde geçerli, reddin sebebi kullanıcının AYARI. 403 de değil —
    yerel tek kullanıcılı bir uygulamada yetkilendirme çağrışımı yanlış olurdu.
    """
    if title is None and not prefs.read(OUTPUT_DIR)["autosave_sessions"]:
        raise HTTPException(status_code=409,
                            detail="Oturumların otomatik kaydı kapalı: "
                                   "Ayarlar'dan açabilir ya da oturuma ad vererek "
                                   "kendiniz kaydedebilirsiniz.")


def _auto_title(messages: list[dict]) -> str:
    """Otomatik kaydedilen oturumun adı: ilk KULLANICI turunun ilk satırı.

    `display` varsa o kazanıyor: çip turunda modele giden cümle ile ekranda
    görünen etiket farklı (v1.16) ve panelde kullanıcının GÖRDÜĞÜ metin durmalı.

    Tek satır + sıkıştırılmış boşluk: kenar paneli tek satır çiziyor, gövdedeki
    satır sonu oraya boşluk olarak sızardı. Sınır `MAX_CHAT_TITLE_CHARS` (kayıt
    kapısıyla aynı sayı) ve kesme işareti görünür — kırpıldığı belli olsun.

    Sonuç kaydıyla başlayan döküm (Görsel modunda üretimle açılan oturum) için
    yedek ad var: kullanıcı mesajı olmayabilir, ama adsız oturum olamaz.
    """
    for m in messages:
        if m.get("role") != "user":
            continue
        text = " ".join((m.get("display") or m.get("content") or "").split("\n")[0].split())
        if text:
            return (text if len(text) <= MAX_CHAT_TITLE_CHARS
                    else text[:MAX_CHAT_TITLE_CHARS - 1] + "…")
    return "Adsız oturum"

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
    """Yeni kayıt. Gövde ZORUNLU, başlık DEĞİL (v2.0: otomatik kayıt).

    Başlık gelmediyse ilk mesajdan türetiliyor (`_auto_title`) — kural aynı
    kalıyor ("adsız sohbet olmaz"), onu sağlayan taraf değişti: otomatik kaydın
    ad verecek bir kullanıcı eylemi yok. BOŞ gelen başlık ise hâlâ 422; "alan hiç
    gelmedi" ile "boş geldi" ayrımı `chat_deployment`'taki geleneğin aynısı.

    Kaydetmede allowlist DEĞİL `exclude_none` var — ayrım bilinçli: tamamlama
    yolunun sınırı Azure'ın şeması, kaydetmenin sınırı ise diskteki biçim.
    `display` diske YAZILMAK ZORUNDA (pil yeniden açılışta sağ kalsın), ama
    `display: null` satırları eski sohbetlerin gövdesini sebepsiz büyütür.
    """
    if req.title is not None and not req.title.strip():
        raise HTTPException(status_code=422, detail="Sohbet başlığı boş olamaz.")
    if not req.messages:
        raise HTTPException(status_code=422, detail="Kaydedilecek mesaj yok.")
    messages = [m.model_dump(exclude_none=True) for m in req.messages]
    _guard_autosave(req.title)
    title = req.title.strip() if req.title else _auto_title(messages)
    return {"chat": chat_store.create(title, messages, OUTPUT_DIR, now=_now())}


@app.delete("/api/chats")
def delete_all_chats_route() -> dict:
    """Tüm oturumları siler (karar D1'in güvence b'si: "tümünü sil").

    Boş depoda 404 DEĞİL: tek kayıt silmede 404'ün anlamı "hangi kayıt?" sorusunun
    cevapsız kalması; burada soru yok, istenen durum zaten sağlanmış.
    """
    return {"deleted": chat_store.delete_all(OUTPUT_DIR)}


@app.put("/api/chats/{chat_id}")
def update_chat_route(chat_id: str, req: ChatSaveRequest) -> dict:
    """Gövdeyi ve/veya başlığı değiştirir (tur sonu kaydı + yeniden adlandırma).

    Başlık BOŞ dizeyle gelirse reddedilir: adsız bir sohbet kenar panelinde
    tıklanacak hiçbir şey bırakmaz.
    """
    title = None if req.title is None else req.title.strip()
    if title is not None and not title:
        raise HTTPException(status_code=422, detail="Sohbet başlığı boş olamaz.")
    # Gövde-yalnız `PUT` = tur sonu otomatik yazımı (bkz. _guard_autosave).
    if req.messages is not None:
        _guard_autosave(req.title)
    messages = (None if req.messages is None
                else [m.model_dump(exclude_none=True) for m in req.messages])
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


@app.get("/api/folders/{folder_id}/download")
def download_folder_route(folder_id: str):
    """Klasörü ve alt klasörlerini görselleriyle birlikte ZIP olarak indirir."""
    fid = os.path.basename(folder_id)
    if not folders.exists(fid, OUTPUT_DIR):
        raise HTTPException(status_code=404, detail="Klasör bulunamadı.")
    try:
        zip_bytes, folder_name = folders.export_zip(fid, OUTPUT_DIR)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Süzgeç ARTIK TEK YERDE (`folders.safe_component`). Buradaki kopya
    # `[^\w\s-]` deseniyle CR/LF'yi KORUYORDU ve klasör adı doğrudan bu
    # başlığın DEĞERİNE giriyordu — gerekçenin tamamı o fonksiyonun başında.
    # `filename*` tarafında böyle bir açık hiç yoktu: `quote` satır sonunu
    # zaten `%0D%0A` olarak kaçırıyor.
    safe_ascii = folders.safe_component(folder_name)
    safe_ascii = safe_ascii.encode("ascii", "ignore").decode("ascii") or "klasor"
    encoded_utf8 = quote(folder_name)
    # SIRA RFC 6266'nın ÖNERDİĞİ gibi: tırnaklı `filename` önce, `filename*`
    # sonra. Öncelik parametreyle belirleniyor (ikisini de anlayan istemci
    # `filename*`i seçer), ama eski istemciler ilk parametreyi okuyup durabildiği
    # için spec bu sırayı öneriyor.
    #
    # BU SIRA BİR KEZ TERSİNE ÇEVRİLMİŞTİ ve gerekçesi yanlıştı: Android
    # WebView'in `URLUtil.guessFileName`'i sırayla düzelmiyor. Android 14
    # ÖNCESİNDEKİ regex `attachment;\s*filename\s*=…$` ile ÇAPALI — yani
    # tırnaklı `filename`den sonra `filename*` gelince de, `filename*` başa
    # alınınca da eşleşme olmuyor; iki sırada da ad URL yolundan türetiliyor.
    # Android 14+ ise RFC 6266 ayrıştırıcısını kullanıyor ve `filename*`i sıradan
    # bağımsız zaten tercih ediyor. Yani o çevirme hiçbir şey düzeltmiyordu.
    #
    # Adın telefonda doğru inmesi artık bu başlığa hiç bağlı değil: APK'da adı
    # frontend veriyor (`core.js` → `MainActivity.IndirmeKoprusu`), tahmin eden
    # bir regex zincirde yok. Başlık masaüstü ve tarayıcı için duruyor.
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_ascii}.zip"; filename*=UTF-8\'\'{encoded_utf8}.zip'
    }

    return Response(content=zip_bytes, media_type="application/zip", headers=headers)




@app.patch("/api/folders/{folder_id}")
def rename_folder_route(folder_id: str, req: FolderRequest) -> dict:
    """Klasör adını değiştirir."""
    fid = os.path.basename(folder_id)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Klasör adı gerekli.")
    updated = folders.rename(fid, name, OUTPUT_DIR)
    if not updated:
        raise HTTPException(status_code=404, detail="Klasör bulunamadı.")
    return {"folder": updated}



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


@app.get("/api/arena/{arena_id}")
def arena_round_route(arena_id: str) -> dict:
    """Turun kayıtları, sütun sırasında. Bilinmeyen turda boş liste.

    Döküm arena satırını KENDİ kayıtlarından çiziyor; bu uç yalnızca "kazanan
    hangisi" sorusunu cevaplıyor. Ayrı bir uç, çünkü `/api/history` KLASÖRE
    göre süzülüyor: başka klasöre taşınmış bir sütunu hiç döndürmezdi
    (chat.js'in `/output/{id}.png` kararının aynı gerekçesi).

    404 YOK: silinmiş bir tur, boş bir tur gibi okunuyor — döküm satırı yine
    çizilebilir olmalı (sarkan id'nin yer tutucu davranışıyla aynı duruş).
    """
    return {"images": storage.arena_round(os.path.basename(arena_id), OUTPUT_DIR)}


@app.post("/api/arena/{arena_id}/winner")
def set_arena_winner_route(arena_id: str, req: ArenaWinnerRequest) -> dict:
    """Arena turunun kazananını işaretler; tur başına TEK kazanan.

    Elenen sonuç SİLİNMİYOR — işaret bir tercih kaydı, bir çöp kutusu değil:
    kullanıcı iki gün sonra ötekini indirebilmeli. Depoda tek yazımla
    yapılıyor (bkz. storage.set_arena_winner).
    """
    aid = os.path.basename(arena_id)
    iid = os.path.basename(req.image_id)
    if not storage.set_arena_winner(aid, iid, OUTPUT_DIR):
        raise HTTPException(status_code=404,
                            detail="Arena turu ya da görsel bulunamadı.")
    return {"arena_id": aid, "winner": iid}


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
         "palette": None, "prompt_sent": None, "imported": True,
         # BOŞ bilerek: bu görsel başka bir araçta üretildi, bir modeli yok.
         # (bkz. storage.save → "model")
         "model": ""},
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

    Bindirilecek görsel HER ZAMAN kullanıcının kütüphanesinden gelir. Eskiden
    `asset_id` boş bırakılabilir ve pakete gömülü yerleşik logo çiftine düşülürdü;
    uygulama marka-nötr olduğundan o varsayılan yok — seçim yapılmadıysa istek
    422 ile reddedilir (modelde `asset_id` zorunlu), bulunamazsa 404.
    """
    if not req.asset_id:
        raise HTTPException(status_code=422, detail="Bindirilecek bir görsel seç.")
    overlay_path = assets_store.asset_path(req.asset_kind, req.asset_id, ASSETS_DIR)
    if overlay_path is None:
        raise HTTPException(status_code=404, detail="görsel bulunamadı")
    try:
        return composite.composite_logo(
            src_path,
            logo_path=overlay_path,
            position=req.position, scale=req.size,
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
         "prompt_sent": src_meta.get("prompt_sent"),
         # Model de devralınıyor: bindirme TÜREV, kendi başına bir üretim
         # değil. Geçilmezse kayda varsayılan model yazılırdı — Nano Banana ile
         # üretilmiş bir görselin logolu hâli "azure-gpt-image-2" görünürdü.
         "model": src_meta.get("model")},
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
         "prompt_sent": src_meta.get("prompt_sent"),
         # Model de devralınıyor: bindirme TÜREV, kendi başına bir üretim
         # değil. Geçilmezse kayda varsayılan model yazılırdı — Nano Banana ile
         # üretilmiş bir görselin logolu hâli "azure-gpt-image-2" görünürdü.
         "model": src_meta.get("model")},
        OUTPUT_DIR, now=_now(),
    )
    return {"image": record}


def _check_asset_kind(kind: str, *, allow_all: bool = False) -> None:
    if allow_all and kind == "all":
        return
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
    _check_asset_kind(kind, allow_all=True)
    if kind == "all":
        all_items = []
        for k in assets_store.KINDS:
            all_items.extend(assets_store.list_assets(k, ASSETS_DIR))
        all_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"items": all_items}
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
    """Depodaki medyayı ÇİZİM için sunar (inline, indirme başlığı YOK).

    Tür ARTIK TÜRETİLİYOR: v0.13'e kadar `image/png` çakılıydı ve o doğruydu
    çünkü depoda tek tür vardı. MP4 gelince çakılı tür sessiz bir kırılma
    olurdu — tarayıcı `image/png` diyen bir gövdeyi resim olarak çizmeye
    çalışır, `<video>` etiketi hiçbir şey oynatmaz ve konsolda bir hata bile
    çıkmaz. Eşleme `storage.MEDIA_TYPES`te, yani uzantı kararının verildiği
    yerde (bkz. o tablonun yorumu).

    `Content-Disposition` HÂLÂ YOK ve bu adres hâlâ her galeri küçük resminin
    `src`i — indirme yolu ayrı bir uç (`output_download`) ve gerekçesi orada
    yazılı.
    """
    safe = os.path.basename(filename)
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=404, detail="bulunamadı")
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="bulunamadı")
    return FileResponse(path, media_type=storage.media_type_for(safe))


@app.get("/api/output/{image_id}/download")
def output_download(image_id: str) -> FileResponse:
    """Aynı PNG, ama `Content-Disposition: attachment` ile — İNDİRME yolu.

    NEDEN AYRI BİR UÇ, `/output/{filename}`e başlık eklemek yerine: o adres aynı
    zamanda her galeri küçük resminin ve büyüteç görselinin `<img src>`'i. Onu
    "attachment" demeye zorlamak, görsellerin ÇİZİLMESİNİ bir indirme başlığına
    bağlardı — kazanacağımız şeyin bedeli, kaybetmeye hiç razı olmayacağımız şey.
    Kalıp `/api/folders/{folder_id}/download`'un aynısı (yukarısı).

    NEDEN VAR: `Content-Disposition` taşımayan bir `image/png`, ona giden her
    istemci için "çizilecek bir şey" — indirilecek bir şey değil. Sağ tık /
    uzun basıp "bağlantıyı kaydet", tarayıcıda indirme ve `.app` paketindeki
    WKWebView kayıt paneli bu başlığa bakıyor; başlıksız adres hepsinde
    "görseli aç"a dönüyordu.

    ANDROID'İN TEK ÇARESİ BU DEĞİL, bilerek: WebView'in indirme sistemi hiç yok
    ve `<a download>` tıklaması orada bir gezinme değil "renderer kaynaklı
    indirme" — yani başlık doğru olsa da devralma zinciri sessizce kopabiliyor.
    APK'da indirme bu yüzden `MainActivity.IndirmeKoprusu` üzerinden gidiyor ve
    dosya adını da frontend veriyor. Bu uç orada yalnız köprünün indirdiği adres
    olarak kalıyor.

    Path-traversal guard'ı yeniden yazılmıyor: `_output_media_path` servis
    yolunun tek kapısı ve 404'ü de o veriyor.

    TÜR VE DOSYA ADI, DİSKTEKİ DOSYADAN geliyor — `image_id`ye uzantı
    EKLENMİYOR. Fark v0.13'te gerçek oldu: `f"{id}.png"` yazan bir indirme,
    bir videoyu `.png` adıyla teslim ederdi ve dosya kullanıcının
    diskinde açılmayan bir şey olurdu. Adı diskteki gerçeğe bağlamak, aynı
    zamanda `download` özniteliğiyle (`folders.js` onu `rec.filename`den
    veriyor) tek bir gerçeği paylaşmak demek.
    """
    path = _output_media_path(image_id)
    ad = os.path.basename(path)
    return FileResponse(path, media_type=storage.media_type_for(ad),
                        filename=ad)


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
            f"sürerse hata kaydını (<code>{log_path or 'hata.log'}</code>) teknik desteğe iletin.</p>",
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
