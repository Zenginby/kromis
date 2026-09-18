# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Üretim uçları: görsel üret/düzenle, video üret/canlandır — hepsi 202, iş kuyruğa (Faz 2 / 4)."""
from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

import catalog
import etiket
import i18n
import palette
from models import (
    MAX_IMAGES_PER_RUN,
    MAX_PROMPT_CHARS,
    GenerateRequest,
    VideoRequest,
    check_capabilities,
    check_video_capabilities,
)
from services import ayar, dil, dosya, gorsel, kapilar, kimlik, kuyruk, palet
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# DÖRT ROTA SAĞLAYICIYI ÇAĞIRMAZ (Faz 2 / 4; docs/faz2-kuyruk-anahtarlar-depolama.md §4).
# Faz 1'e kadar üretim isteğin İÇİNDE koşuyordu: 1-6 dakika açık bağlantı,
# sekme yenilenirse iş kayıp (aşağıdaki `video` docstring'i o günün kaydı).
# Şimdi gövde üç adım: bugünkü doğrulamanın TAMAMI aynen (pydantic,
# `_check_edit_form`/`_check_video_form`, `check_folder`, palet kapıları,
# 413/422 metinleri — bayt bayt) → multipart girdiler depoya
# (`kullanicilar/<uuid>/isler/<is_id>/<ad>`) → `kuyruk.ekle` → **202**
# `{"is": kuyruk._json(is)}`. Sağlayıcı çağrısı, `medya` satırı ve kredi
# hesabı işçide (services/isci.py `kos`); rota yalnız `kredi_tahmini`
# (`catalog.cost_for × n`) ve `prompt_sent` (`palet.palette_prompt`) hesaplar,
# çünkü ikisi de kullanıcının O ANKİ paletine/kataloğa bağlı ve palet sonradan
# silinse iş değişmemeli (`istek` sözleşmesi services/isci.py'nin başında).
#
# SIRA BİLİNÇLİ: doğrulama → eş zamanlılık kapısı (`check_is_tavani`, 429) →
# girdi nesneleri → satır. 422 alacak istek 429 ile maskelenmez; 429 alacak
# istek depoya nesne bırakmaz; satır ancak nesneler yazıldıysa doğar (nesne
# yazımı düşerse istek 500, satır yok, işçi hiç görmez). `is_id` rotada
# üretilir (`uuid4`) ve `kuyruk.ekle`ye verilir: anahtar id'yi taşır.
#
# GİRDİ NESNELERİ İŞ BİTİNCE SİLİNMEZ (§3 kararı (g); belge §4'ün "iş bitince
# silinir" satırından bilinçli sapma): "yeniden gönder" (5. görev) aynı
# nesneleri kullanır, 30 günlük saklama (10. görev) ve `tools/artik_dosya.py`
# (`isler/` öneki) siler. İşçi yalnız okur.
#
# `kimlikler` İMZADAN ÇIKTI: sağlayıcı kimliğini işçi çözer (`kos`), rota
# artık anahtar okumaz — her istekte bir sorgu + N Fernet çözümü boşa
# giderdi (tests/test_kimlik.py `KIMLIK_OKUYAN` iki yönlü bekçi).
# `ayarlar` KALDI: `edit`/`animate` referansları `ayarlar.output_dir`den
# okur; `generate`/`video`da bağımlılık kullanıcı dizinlerini ilk istekte
# açar (`ayar._dizinleri_ac`, 0o700 kök) — işçi o dizine yazar ve rota
# kullanıcı verisine dokunan bir rota olarak sınıflanır (test_kimlik).
#
# Bayat SUNUCU tespiti (core.js "yanıt alanı geri yankılıyor mu") 202
# gövdesindeki `is.model` ve iş bitince `medya.model` üzerinden sürer.

# Girdi nesnelerinin depo anahtarı: `kullanicilar/<uuid>/isler/<is_id>/<ad>` —
# kök göreli (`Depo` sözleşmesi), web ve işçi süreçleri farklı `data_dir`
# bağlasa da aynı anahtar. `ad` adaptöre giden dosya adı (`abc123.png`,
# `upload.png`, `refN.png` — `_collect_edit_refs`in bugünkü adları).
ISLER_DIZINI = "isler"


def _girdi_anahtari(kullanici_id: uuid.UUID, is_id: uuid.UUID, ad: str) -> str:
    return f"{ayar.KULLANICILAR_DIZINI}/{kullanici_id}/{ISLER_DIZINI}/{is_id}/{ad}"


def _girdileri_yaz(depo: dosya.Depo, kullanici_id: uuid.UUID, is_id: uuid.UUID,
                   refs: list[tuple[str, bytes]]) -> list[dict[str, str]]:
    """`[(ad, bayt), …]` → depoya yazar, `istek.girdiler` sözleşmesini (`{"ad", "anahtar"}`) döndürür.

    Hepsi PNG: `_collect_edit_refs` her referansı `gorsel.to_png`ten geçiriyor.
    """
    girdiler = []
    for ad, veri in refs:
        anahtar = _girdi_anahtari(kullanici_id, is_id, ad)
        depo.yaz(anahtar, veri, "image/png")
        girdiler.append({"ad": ad, "anahtar": anahtar})
    return girdiler


def _siraya_koy(db: Session, kullanici_id: uuid.UUID, tur: str, istek: dict[str, Any],
                model: str, kredi_tahmini: int, is_id: uuid.UUID | None = None) -> dict:
    """`kuyruk.ekle` → 202 gövdesi. `istek` DÖKÜLMEZ (`_json`): prompt ve girdi anahtarları içeride."""
    is_ = kuyruk.ekle(db, kullanici_id, tur, istek, model, kredi_tahmini, is_id=is_id)
    return {"is": kuyruk._json(is_)}


def _ortak_istek(prompt: str, size: str, quality: str, n: int, folder_id: str | None,
                 session_id: str | None) -> dict[str, Any]:
    """Dört türün ortak alanları (services/isci.py `istek` sözleşmesi, "ortak" satırı)."""
    return {"prompt": prompt, "size": size, "quality": quality, "n": n,
            "folder_id": folder_id, "session_id": session_id}


@router.post("/api/generate", status_code=202)
def generate(req: GenerateRequest, db: Session = OTURUM,
             ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
             kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
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
    kapilar.check_is_tavani(db, kullanici.id)
    # TAHMİN görsel başına maliyet × adet; işçi gerçek maliyeti satır başına
    # yazar (`isci._kredi`), bu sayı 6. görevin günlük tavanı için.
    kredi_tahmini = catalog.cost_for(spec, req.quality) * req.n
    istek = {**_ortak_istek(req.prompt, req.size, req.quality, req.n, folder_id, session_id),
             # Turun sütunları AYRI isteklerle geliyor (istemci fan-out'u; bkz.
             # models.GenerateRequest.arena_id) — onları birbirine bağlayan tek şey bu etiket.
             "arena_id": arena_id, "palette": pal, "prompt_sent": prompt_sent}
    return _siraya_koy(db, kullanici.id, "generate", istek, req.model, kredi_tahmini)


@router.post("/api/video", status_code=202)
def video(req: VideoRequest, db: Session = OTURUM,
          ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
          kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Metin → video. `generate`in video ikizi.

    Faz 1'de SENKRONDU ve bu bilinçli bir seçimdi, kaza değil: üretim 1-6
    dakika sürüyor ve istek o süre boyunca açık kalıyordu. Emsali depoda
    zaten vardı — Azure'ın n=4 üretimi `180+120·3` = 540 saniyelik bir okuma
    bütçesiyle çalışıyor (`azure_client.read_timeout_for`). Yoklamanın
    adaptörün İÇİNDE olması, `providers` sözleşmesini (`list[bytes]`) bozmadan
    bu yolu açıyor; `catalog.poll_timeout` alanının ilk yorumu da tam olarak
    bu günü tarif ediyordu.
    Bilinen bedeli: sekme yenilenirse iş kaybediliyor ve ilerleme yüzde
    olarak gösterilemiyordu. İkincisi zaten deponun kayıtlı kararı
    (`index.html`in "yüzde uydurmaydı" notu); ilkinin cevabı bir iş kuyruğu
    ve o ayrı bir maddeydi — BU madde (Faz 2 / 4): rota 202 döner, dakikalar
    işçide geçer (services/isci.py), adaptörün iç yoklaması aynen orada.

    `def`, `async def` DEĞİL — `generate` ve `chat` ile aynı gerekçe: Starlette
    senkron rotayı iş parçacığı havuzunda koşturuyor; gövde artık kısa ama
    DB'ye gidiyor (klasör kapısı, sayaç, satır) ve senkron sürücü olay
    döngüsünü kilitlemesin.

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
    kapilar.check_is_tavani(db, kullanici.id)
    kredi_tahmini = catalog.cost_for(spec, req.quality, duration=req.duration) * req.n
    istek = {**_ortak_istek(req.prompt, req.size, req.quality, req.n, folder_id, session_id),
             "duration": req.duration}
    return _siraya_koy(db, kullanici.id, "video", istek, req.model, kredi_tahmini)


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


@router.post("/api/video/animate", status_code=202)
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
    depo: dosya.Depo = Depends(dosya.depo),
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

    Referans ve son kare depoya `isler/<is_id>/` altına yazılır, işçi oradan
    okur (`istek.girdiler`, `istek.son_kare`) — rota baytı adaptöre değil depoya taşır.
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
    refs, parent_id = await _collect_edit_refs(request, file, source_id, ayarlar.output_dir, depo)
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
        son_kare = gorsel.read_png_file(
            gorsel.output_png_path(last_source_id, ayarlar.output_dir, depo=depo), depo=depo)
    elif last_file is not None:
        son_kare = await gorsel.read_upload_png(last_file)

    await run_in_threadpool(kapilar.check_is_tavani, db, kullanici.id)
    is_id = uuid.uuid4()
    # Son kare `girdiler`in DIŞINDA, kendi anahtarıyla (`istek.son_kare`): işçi
    # `girdiler`i referans listesi, `son_kare`yi `last_frame` olarak verir —
    # yukarıdaki "refs'e katılmıyor" kararının depo karşılığı.
    yazilacak = refs + ([("son_kare.png", son_kare)] if son_kare is not None else [])
    girdiler = await run_in_threadpool(_girdileri_yaz, depo, kullanici.id, is_id, yazilacak)
    kredi_tahmini = catalog.cost_for(spec, quality, duration=duration) * n
    istek = {**_ortak_istek(prompt, size, quality, n, target_folder, session),
             "girdiler": girdiler[:len(refs)], "parent_id": parent_id, "duration": duration,
             "son_kare": girdiler[len(refs)] if son_kare is not None else None}
    return await run_in_threadpool(_siraya_koy, db, kullanici.id, "animate", istek, model_id,
                                   kredi_tahmini, is_id)


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
    depo: dosya.Depo,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Azure'a gidecek referans görselleri toplar: `(refs, parent_id)`.

    Sıra sözleşme: ana görsel → ek yüklemeler → ek galeri görselleri. `parent_id`
    yalnızca ana görsel galeriden seçildiğinde dolu (türev zinciri buna bağlı).
    Galeri id'leri `output_dir`de, `depo`da aranıyor — ikisi de rotadan geliyor.
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
        refs.append((f"{sid}.png",
                     gorsel.read_png_file(gorsel.output_png_path(sid, output_dir, depo=depo), depo=depo)))
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
                     gorsel.read_png_file(gorsel.output_png_path(extra_id, output_dir, depo=depo),
                                          depo=depo)))
    return refs, parent_id


@router.post("/api/edit", status_code=202)
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
    depo: dosya.Depo = Depends(dosya.depo),
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
    refs, parent_id = await _collect_edit_refs(request, file, source_id, ayarlar.output_dir, depo)

    # task="edit": üretim ifadesi modele yeniden boyama söyler ve referans
    # görselin kompozisyonunu yok eder; düzenlemede istenen renk derecelendirmesi.
    prompt_sent, pal = await run_in_threadpool(
        palet.palette_prompt, prompt, palette_hex, palette_mode, palette_strength, palette_id,
        task="edit", db=db, kullanici_id=kullanici.id, drop=drop)

    await run_in_threadpool(kapilar.check_is_tavani, db, kullanici.id)
    is_id = uuid.uuid4()
    girdiler = await run_in_threadpool(_girdileri_yaz, depo, kullanici.id, is_id, refs)
    kredi_tahmini = catalog.cost_for(spec, quality) * n
    istek = {**_ortak_istek(prompt, size, quality, n, target_folder, session),
             "girdiler": girdiler, "parent_id": parent_id,
             "palette": pal, "prompt_sent": prompt_sent}
    return await run_in_threadpool(_siraya_koy, db, kullanici.id, "edit", istek, model_id,
                                   kredi_tahmini, is_id)
