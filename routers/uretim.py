# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Üretim uçları: görsel üret/düzenle, video üret/canlandır."""
from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

import azure_client as ac
import catalog
import etiket
import i18n
import palette
import providers
from models import (
    MAX_IMAGES_PER_RUN,
    MAX_PROMPT_CHARS,
    GenerateRequest,
    VideoRequest,
    check_capabilities,
    check_video_capabilities,
)
from services import ayar, depo_medya, dil, gorsel, kapilar, kimlik, palet, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# Üretilen medyanın kaydı DB'de (Faz 1 / 5): dört rota `depo_medya.kaydet`e
# yazıyor — dosya kullanıcının `output_dir`ine, satır isteğin `Session`ına
# (commit `db.oturum`da, rota döner dönmez). Kullanıcı `ayar.ayarlar`ın içindeki
# kapıyla aynı nesne (FastAPI bağımlılık önbelleği), ek sorgu yok. İki `async
# def` rota (`edit`, `animate`) DB'ye `run_in_threadpool` ile gidiyor.
#
# Dört rota SAĞLAYICI KİMLİĞİ okuyor (Faz 1 / 7): `kimlik.KIMLIKLER` kullanıcının
# şifreli satırlarını bir kez çözer ve isteğin bağlamına bağlar; adaptörler
# kimliği oradan, TEMBEL çözer (`credentials=None` düşmesi — gerekçesi
# providers._azure_generate ve kimlik_baglami). `kimlikler` imzada dursun ki
# hangi rotanın anahtar okuduğu imzasında okunsun (bekçi tests/test_kimlik.py).


@router.post("/api/generate")
def generate(req: GenerateRequest, db: Session = OTURUM,
             ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
             kimlikler: Mapping[str, str] = kimlik.KIMLIKLER) -> dict:
    folder_id = kapilar.check_folder(req.folder_id, db, kullanici.id)
    session_id = kapilar.check_session(req.session_id)
    arena_id = kapilar.check_arena(req.arena_id)
    prompt_sent, pal = palet.palette_prompt(req.prompt, req.palette_hex, req.palette_mode,
                                            req.palette_strength, req.palette_id,
                                            drop=req.palette_drop,
                                            task="generate", db=db, kullanici_id=kullanici.id)
    # `req.model` doğrulayıcıda NORMALLEŞTİRİLDİ (None → varsayılanın gerçek
    # id'si), yani doğrulanan değer ile kaydedilen değer ayrışamıyor. İki
    # `assert` o sözleşmenin TİP düzeyindeki karşılığı: alan telde None
    # alabildiği için `str | None` kalıyor ve katalog kaydı doğrulayıcının
    # geçirdiği id için hiç None olamaz — mypy bunu göremez, burada daraltılıyor.
    assert req.model is not None
    spec = catalog.image_model(req.model)
    assert spec is not None
    try:
        images = providers.generate(req.model, prompt_sent, req.size,
                                    req.quality, req.n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    # Maliyet GÖRSEL BAŞINA yazılıyor: kayıt tek bir görselin kaydı ve n=4'lük
    # bir turun tamamını her satıra yazmak toplamı dörde katlardı.
    kredi = catalog.cost_for(spec, req.quality)
    records = [
        depo_medya.kaydet(db, kullanici.id, img,
                          {"prompt": req.prompt, "size": req.size,
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
                          ayarlar.output_dir, now=zaman.an())
        for img in images
    ]
    return {"images": records}


@router.post("/api/video")
def video(req: VideoRequest, db: Session = OTURUM,
          ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
          kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
          kimlikler: Mapping[str, str] = kimlik.KIMLIKLER) -> dict:
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
    folder_id = kapilar.check_folder(req.folder_id, db, kullanici.id)
    session_id = kapilar.check_session(req.session_id)
    # `req.model` doğrulayıcıda NORMALLEŞTİRİLDİ (None → varsayılanın gerçek
    # id'si), yani doğrulanan değer ile kaydedilen değer ayrışamıyor; iki
    # `assert` `generate`teki daraltmanın ikizi.
    assert req.model is not None
    spec = catalog.video_model(req.model)
    assert spec is not None
    try:
        videos = providers.generate_video(req.model, req.prompt, req.size,
                                          req.quality, req.duration, req.n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))
    kredi = catalog.cost_for(spec, req.quality, duration=req.duration)
    records = [
        depo_medya.kaydet(db, kullanici.id, vid,
                          {"prompt": req.prompt, "size": req.size,
                           "quality": req.quality, "parent_id": None,
                           "folder_id": folder_id, "palette": None,
                           "session_id": session_id,
                           "kind": "video", "duration": req.duration,
                           "model": req.model, "credits": kredi,
                           "prompt_sent": None},
                          ayarlar.output_dir, now=zaman.an())
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
    assert spec is not None  # `check_video_capabilities` aynı id'yi az önce katalogda buldu
    if not spec.supports_edit:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.model_no_reference", dil.aktif(), model=etiket.label_of(spec)))
    # `_check_edit_form`un aynı kapısı ve burada ALT sınır daha da gerekli:
    # `check_video_capabilities` yalnız TAVANI ölçüyor (`n > max_n`) ve form
    # ucunda `n` için pydantic `ge=1` YOK (JSON ikizinde var). `n=0` geçse
    # `providers.total_budget` SIFIR dönerdi — yani Veo işi gönderilir
    # (faturalanır) ve döngü ilk yoklamadan önce "süre doldu" der.
    if not (1 <= n <= min(spec.max_n, MAX_IMAGES_PER_RUN)):
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.n_range", dil.aktif(), ust=min(spec.max_n, MAX_IMAGES_PER_RUN)))
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.prompt_range", dil.aktif(), ust=MAX_PROMPT_CHARS))
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.exactly_one_source", dil.aktif()))
    # SON KARE. Ana karenin "tam olarak biri" kapısının ikizi, tek farkı
    # İSTEĞE BAĞLI olması: bitiş görseli hiç verilmeyebilir (o zaman istek
    # bugünküyle aynı), ama iki yoldan birden verilemez.
    if last_file is not None and last_source_id is not None:
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.at_most_one_last", dil.aktif()))
    if (last_file is not None or last_source_id is not None) \
            and not spec.supports_last_frame:
        # Yetenek kapısı `supports_edit`ten AYRI: ilk kareyi alan bir model
        # son kareyi almayabilir. Mesaj hangi modelin reddettiğini söylüyor,
        # çünkü çözüm composer'daki şeritten başka bir model seçmek.
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.model_no_last_frame", dil.aktif(), model=etiket.label_of(spec)))
    return model_id


@router.post("/api/video/animate")
async def animate(
    request: Request,
    prompt: str = Form(...),
    size: str = Form(...),
    quality: str = Form(...),
    duration: int = Form(...),
    n: int = Form(1),
    file: UploadFile | None = File(None),
    source_id: str | None = Form(None),
    # SON KARE ana karenin form çiftinin BİREBİR ikizi. `gorsel.extra_refs`in
    # "ek referans" kanalından geçirilmedi ve gerekçesi katalogtaki
    # `supports_last_frame` yorumunda: son kare bir referans değil ayrı bir
    # eksen, o kanal da video tarafında üç ayrı kapıyla zaten kapalı.
    last_file: UploadFile | None = File(None),
    last_source_id: str | None = Form(None),
    folder_id: str | None = Form(None),
    session_id: str | None = Form(None),
    model: str = Form(""),
    db: Session = OTURUM,
    ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
    kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
    kimlikler: Mapping[str, str] = kimlik.KIMLIKLER,
) -> dict:
    """Görsel → video: bir kareyi hareketlendirir.

    `/api/edit`in kalıbı AYNEN kullanılıyor — `_collect_edit_refs` de aynen,
    yeniden yazılmadan. O işlev "ana görsel → ek yüklemeler → ek galeri
    görselleri" sırasını ve `parent_id` türev zincirini zaten kuruyor; video
    tarafında yalnız TAVAN farklı ve o tavan katalogdan geliyor
    (`max_refs=1`, yani ilk kare). Kapı `refs` toplandıktan SONRA: erken
    davranmak, `_collect_edit_refs`in kendi 413/422 mesajlarını
    ikizlemek olurdu.

    Referans PNG'ye çevriliyor (`gorsel.to_png`, `_collect_edit_refs`in içinde)
    ve `source_id` yolu `gorsel.output_png_path`ten okuyor — o işlev PNG'de
    çakılı KALIYOR ve bu doğru: bir videoyu ilk kare olarak göndermek anlamsız,
    404 doğru cevap (servis yolu `depo_medya.dosya_yolu`, uzantıyı ARAR).
    """
    # BOŞ FORM ALANI "VERİLMEDİ" DEMEK. Bütün alanlarını koşulsuz serileştiren
    # bir istemci `last_source_id=""` yolluyor ve `is not None` onu "bitiş
    # görseli var" sayardı: yeteneği olmayan bir modelde hiç bitiş karesi
    # TAŞIMAYAN bir istek 422 yer, yetenekli modelde `output_png_path("")`
    # 404 döner — ikisi de kullanıcının yapmadığı bir şeyi anlatan mesajlar.
    # `gorsel.extra_refs` galeri id'lerini tam bu yüzden `v.strip()` ile süzüyor.
    # Normalleştirme kapıdan ÖNCE: kapı ile rota AYNI değeri görmek zorunda.
    #
    # `last_file`in İKİZİ YOK ve gerekmiyor: dosya adı olmayan bir parçayı
    # çerçeve rotadan ÖNCE çözüyor. Starlette onu hâlâ boş `str` olarak
    # ayrıştırıyor, FastAPI 0.141 ise boş dizeyi `UploadFile | None` için
    # `None` sayıyor (0.115'te 422 oluyordu; Faz 0 / Adım 5'te pinler
    # yükselirken ölçüm yenilendi). Dolu METİN gelen bir dosya alanı ise iki
    # sürümde de 422 (`gorsel.extra_refs`in ham formu okumasının gerekçesi tam
    # bu). Ana karenin `file` alanı da aynı yoldan geçiyor — burada ayrı bir
    # süzgeç açmak iki kardeş alanı sessizce ayrıştırırdı.
    last_source_id = (last_source_id or "").strip() or None
    model_id = _check_video_form(prompt, size, quality, duration, n,
                                 file, source_id, model,
                                 last_file, last_source_id)
    spec = catalog.video_model(model_id)
    assert spec is not None  # `_check_video_form` id'yi katalogdan geçirdi
    target_folder = await run_in_threadpool(kapilar.check_folder, folder_id, db, kullanici.id)
    session = kapilar.check_session(session_id)
    refs, parent_id = await _collect_edit_refs(request, file, source_id, ayarlar.output_dir)
    if len(refs) > spec.max_refs:
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.model_max_refs", dil.aktif(), model=etiket.label_of(spec), adet=spec.max_refs))
    # Son kare `refs`e KATILMIYOR: `max_refs` sayacı "kaç referans" sorusunun
    # cevabı ve son kare o sorunun konusu değil. Katsaydı yukarıdaki kapı
    # bitiş görseli seçen HER isteği 422 yapardı.
    #
    # PNG'ye çevirme `_collect_edit_refs`in kullandığı AYNI iki yardımcıyla —
    # ikinci bir okuma yolu yazmak, birinde `to_png` çağrısını unutmakla
    # biten türden bir ayrışma olurdu. `output_png_path` uzantıyı PNG'de
    # çakılı tutuyor, yani bir VİDEO id'si burada da 404: bir mp4'ü son kare
    # olarak göndermenin karşılığı yok (ana karenin aynı kararı).
    son_kare = None
    if last_source_id is not None:
        son_kare = gorsel.read_png_file(gorsel.output_png_path(last_source_id, ayarlar.output_dir))
    elif last_file is not None:
        son_kare = await gorsel.read_upload_png(last_file)

    try:
        videos = providers.animate_video(model_id, prompt, refs, size, quality,
                                         duration, n, last_frame=son_kare)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    kredi = catalog.cost_for(spec, quality, duration=duration)
    records = [
        await run_in_threadpool(
            depo_medya.kaydet, db, kullanici.id, vid,
            {"prompt": prompt, "size": size, "quality": quality,
             "parent_id": parent_id, "folder_id": target_folder,
             "palette": None, "session_id": session,
             "kind": "video", "duration": duration,
             "model": model_id, "credits": kredi,
             "prompt_sent": None},
            ayarlar.output_dir, now=zaman.an())
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
    assert spec is not None  # `check_capabilities` aynı id'yi az önce katalogda buldu
    if not spec.supports_edit:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.model_no_reference", dil.aktif(), model=etiket.label_of(spec)))
    # Küresel tavan, model tavanının ÜSTÜNDE: `MAX_IMAGES_PER_RUN` aynı zamanda
    # bir sonuç kaydının azami `image_ids` uzunluğu (bkz. models.py), yani onu
    # aşan bir değer dökümü bozar. Buradaki sayı v0.6'ya kadar ELLE yazılmış
    # `4` idi — `MAX_IMAGES_PER_RUN` için ikinci bir literal, yani sessiz bir
    # kayma kaynağı; model tavanı devreye girerken sabite bağlandı.
    if not (1 <= n <= min(spec.max_n, MAX_IMAGES_PER_RUN)):
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.n_range", dil.aktif(), ust=min(spec.max_n, MAX_IMAGES_PER_RUN)))
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.prompt_range", dil.aktif(), ust=MAX_PROMPT_CHARS))
    if palette_mode not in palette.MODES:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_palette_mode", dil.aktif()))
    if palette_strength not in palette.STRENGTHS:
        raise HTTPException(status_code=422, detail=i18n.t("err.bad_palette_strength", dil.aktif()))
    if (file is None) == (source_id is None):
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.exactly_one_source", dil.aktif()))
    return model_id


async def _collect_edit_refs(
    request: Request, file: UploadFile | None, source_id: str | None, output_dir: str,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Azure'a gidecek referans görselleri toplar: `(refs, parent_id)`.

    Sıra sözleşme: ana görsel → ek yüklemeler → ek galeri görselleri. `parent_id`
    yalnızca ana görsel galeriden seçildiğinde dolu (türev zinciri buna bağlı).
    Galeri id'leri `output_dir`de aranıyor — rotanın ayar nesnesinden geliyor.
    """
    extra_uploads, extra_ids = await gorsel.extra_refs(request)
    if 1 + len(extra_uploads) + len(extra_ids) > gorsel.MAX_EDIT_IMAGES:
        raise HTTPException(status_code=422,
                            detail=i18n.t("err.max_images", dil.aktif(), adet=gorsel.MAX_EDIT_IMAGES,
                                                                      ek=gorsel.MAX_EDIT_IMAGES - 1))

    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > gorsel.MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.request_too_big", dil.aktif()))

    refs: list[tuple[str, bytes]] = []
    if source_id is not None:
        sid = os.path.basename(source_id)
        refs.append((f"{sid}.png", gorsel.read_png_file(gorsel.output_png_path(sid, output_dir))))
        parent_id = sid
    else:
        # Form kapısı "tam olarak biri" dedi (`_check_edit_form` /
        # `_check_video_form`): `source_id` yoksa `file` var. mypy iki
        # parametre arasındaki o bağı göremez, daraltma burada.
        assert file is not None
        refs.append(("upload.png", await gorsel.read_upload_png(file)))
        parent_id = None

    for upload in extra_uploads:
        refs.append((f"ref{len(refs) + 1}.png", await gorsel.read_upload_png(upload)))
    for extra_id in extra_ids:
        refs.append((f"ref{len(refs) + 1}.png",
                     gorsel.read_png_file(gorsel.output_png_path(extra_id, output_dir))))
    return refs, parent_id


@router.post("/api/edit")
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
    # (bkz. palet.check_palette_drop). Boş = çıkarma yok.
    palette_drop: str = Form(""),
    # Düzenlemenin doğduğu oturum; boş = oturum dışı (bkz. kapilar.check_session).
    session_id: str | None = Form(None),
    # Boş = varsayılan model. `Form("")` ve zorunlu DEĞİL: bugünkü arayüz alanı
    # hiç göndermiyor ve göndermeyen bir istemci bugünkü davranışı aynen
    # almalı. Bayat SUNUCU tarafı bu uçta pydantic ile korunamıyor (Starlette
    # bilinmeyen form alanını sessizce atıyor), o yüzden koruma yanıtın alanı
    # geri yankılamasıyla kuruluyor — bkz. _check_edit_form'un docstring'i.
    model: str = Form(""),
    db: Session = OTURUM,
    ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
    kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
    kimlikler: Mapping[str, str] = kimlik.KIMLIKLER,
) -> dict:
    """Ek referans görselleri (`extra_files` yüklemeleri, `extra_source_ids`
    galeri id'leri) form verisinden okunur — bkz. gorsel.extra_refs."""
    model_id = _check_edit_form(prompt, size, quality, n, file, source_id,
                                palette_mode, palette_strength, model)
    spec = catalog.image_model(model_id)
    assert spec is not None  # `_check_edit_form` id'yi katalogdan geçirdi
    palette_hex = palet.check_palette_hex(palette_hex)
    drop = palet.check_palette_drop(palette_drop)

    target_folder = await run_in_threadpool(kapilar.check_folder, folder_id, db, kullanici.id)
    session = kapilar.check_session(session_id)
    refs, parent_id = await _collect_edit_refs(request, file, source_id, ayarlar.output_dir)

    # task="edit": üretim ifadesi modele yeniden boyama söyler ve referans
    # görselin kompozisyonunu yok eder; düzenlemede istenen renk derecelendirmesi.
    prompt_sent, pal = palet.palette_prompt(prompt, palette_hex, palette_mode,
                                            palette_strength, palette_id, task="edit",
                                            db=db, kullanici_id=kullanici.id, drop=drop)
    try:
        images = providers.edit(model_id, prompt_sent, refs, size, quality, n)
    except ac.ImageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    kredi = catalog.cost_for(spec, quality)
    records = [
        await run_in_threadpool(
            depo_medya.kaydet, db, kullanici.id, img,
            {"prompt": prompt, "size": size, "quality": quality,
             "parent_id": parent_id, "folder_id": target_folder,
             "palette": pal, "session_id": session,
             "model": model_id, "credits": kredi,
             "prompt_sent": prompt_sent if pal and pal["applied"] else None},
            ayarlar.output_dir, now=zaman.an())
        for img in images
    ]
    return {"images": records}
