# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Galeri uçları: klasörler, geçmiş, taşıma/silme, arena, içe aktarma, medya servisi."""
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

import i18n
import storage
from models import (
    ArenaWinnerRequest,
    BulkImagesRequest,
    BulkMoveRequest,
    FolderRequest,
    MoveImageRequest,
)
from services import ayar, depo_klasor, depo_medya, dil, dosya, gorsel, kapilar, kimlik, zaman
from services.db import OTURUM
from services.tablolar import Kullanici

router = APIRouter()

# Galeri ve klasörler DB'de (Faz 1 / 5): her rota isteğin `Session`ını (`OTURUM`,
# commit `db.oturum`da) ve kapının çözdüğü kullanıcıyı alır. `kullanici`
# `Depends(kimlik.aktif_kullanici)` ile ikinci kez İSTENMİYOR gibi görünse de
# FastAPI aynı bağımlılığı istek başına bir kez çözer (`use_cache`) —
# `ayar.ayarlar`ın içindeki kapıyla aynı nesne, ek sorgu yok. `storage`/`folders`
# manifestleri bu dosyadan artık OKUNMAZ; `storage`dan yalnız MIME tablosu
# (`media_type_for`) geliyor.
#
# Dosyanın YERİ bir `Depo` (Faz 2 / 2, services/dosya.py): dosyaya dokunan her
# rota `Depends(dosya.depo)` ile sürecin deposunu alır ve depo işlevlerine
# `depo=` diye geçirir; `ayarlar.output_dir` yolun öneki olarak duruyor.
# Servis rotaları (`/output/*`, indirme) kovada 302 → 15 dk ön imzalı URL (K7),
# yerelde `FileResponse`; ZIP uygulamadan akar (`StreamingResponse`).

MAX_FOLDER_DEPTH = 5                         # iç içe klasör kademesi


@router.get("/api/folders")
def list_folders_route(db: Session = OTURUM,
                       kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Tüm klasörler (düz liste) + görsel ve alt klasör sayıları.

    Hiyerarşi `parent_id` ile taşınır; arayüz şeridi buna göre süzer, böylece
    sayaçlar ve sürükle-bırak hedefleri tek istekte tazelenir. İki sorgu:
    klasörler ve `GROUP BY folder_id` sayaçları; alt klasör sayısı listeden.
    """
    counts = depo_medya.klasor_sayilari(db, kullanici.id)
    items = depo_klasor.listele(db, kullanici.id)
    child_counts: dict[str, int] = {}
    for f in items:
        pid = f.get("parent_id")
        if pid:
            child_counts[pid] = child_counts.get(pid, 0) + 1
    return {"items": [{"parent_id": None, **f,
                       "count": counts.get(f["id"], 0),
                       "child_count": child_counts.get(f["id"], 0)}
                      for f in items]}


@router.post("/api/folders")
def create_folder_route(req: FolderRequest, db: Session = OTURUM,
                        kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=i18n.t("err.folder_name_required", dil.aktif()))
    parent_id = kapilar.check_folder(req.parent_id, db, kullanici.id)
    # Sınırsız derinlik başlık şeridini taşırıyor ve köke dönüşü zorlaştırıyor;
    # yeniden ebeveynleme olmadığı için tek kapı burası.
    if parent_id and depo_klasor.derinlik(db, kullanici.id, parent_id) >= MAX_FOLDER_DEPTH:
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.folder_depth", dil.aktif(), adet=MAX_FOLDER_DEPTH))
    return {"folder": depo_klasor.olustur(db, kullanici.id, name, parent_id=parent_id,
                                          now=zaman.an())}


@router.delete("/api/folders/{folder_id}")
def delete_folder_route(folder_id: str, db: Session = OTURUM,
                        kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Klasörü ve alt klasörlerini siler; GÖRSELLER silinmez, klasörsüz (kök) hale döner."""
    fid = os.path.basename(folder_id)
    # Sıra önemli: önce ağacı çöz (yoksa 404), sonra görselleri çıkar, sonra kayıtları sil.
    # Üçü aynı transaksiyonda (`db.oturum`), yani arada okuyan yarım ağaç görmez.
    doomed = depo_klasor.altagac(db, kullanici.id, fid)
    if not doomed:
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    unfiled = depo_medya.klasorden_cikar(db, kullanici.id, doomed)
    deleted = depo_klasor.agaci_sil(db, kullanici.id, fid)
    return {"deleted": deleted, "folders": len(deleted), "unfiled": unfiled}


@router.get("/api/folders/{folder_id}/download")
def download_folder_route(folder_id: str, db: Session = OTURUM,
                          ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                          kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                          depo: dosya.Depo = Depends(dosya.depo)):
    """Klasörü ve alt klasörlerini görselleriyle birlikte ZIP olarak indirir.

    ZIP UYGULAMADAN AKAR ve K7'nin (302) tek istisnası: arşivi biz kuruyoruz,
    kovada hazır duran bir nesne yok. `StreamingResponse`: bir klasördeki
    videolar yüzlerce MB olabilir, bütünü bellekte tutulmaz (services/depo_klasor.py).
    """
    fid = os.path.basename(folder_id)
    paket = depo_klasor.zip_disa_aktar(db, kullanici.id, fid, ayarlar.output_dir, depo=depo)
    if paket is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    zip_akisi, folder_name = paket

    # Süzgeç ARTIK TEK YERDE (`folders.safe_component`; `depo_klasor` yeniden
    # dışa açıyor). Buradaki kopya
    # `[^\w\s-]` deseniyle CR/LF'yi KORUYORDU ve klasör adı doğrudan bu
    # başlığın DEĞERİNE giriyordu — gerekçenin tamamı o fonksiyonun başında.
    # `filename*` tarafında böyle bir açık hiç yoktu: `quote` satır sonunu
    # zaten `%0D%0A` olarak kaçırıyor.
    safe_ascii = depo_klasor.safe_component(folder_name)
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

    return StreamingResponse(zip_akisi, media_type="application/zip", headers=headers)


@router.patch("/api/folders/{folder_id}")
def rename_folder_route(folder_id: str, req: FolderRequest, db: Session = OTURUM,
                        kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Klasör adını değiştirir."""
    fid = os.path.basename(folder_id)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=i18n.t("err.folder_name_required", dil.aktif()))
    updated = depo_klasor.yeniden_adlandir(db, kullanici.id, fid, name)
    if not updated:
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    return {"folder": updated}


@router.get("/api/history")
def history(folder_id: str | None = None, db: Session = OTURUM,
            kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """folder_id yoksa yalnızca klasörsüz görseller (kök), varsa o klasörünkiler."""
    if folder_id:
        kapilar.check_folder(folder_id, db, kullanici.id)
    return {"images": depo_medya.listele(db, kullanici.id, folder_id=folder_id or None)}


@router.patch("/api/image/{image_id}")
def move_image(image_id: str, req: MoveImageRequest, db: Session = OTURUM,
               kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Görseli bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = kapilar.check_folder(req.folder_id, db, kullanici.id)
    iid = os.path.basename(image_id)
    if not depo_medya.klasor_ata(db, kullanici.id, iid, target):
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"id": iid, "folder_id": target}


@router.get("/api/arena/{arena_id}")
def arena_round_route(arena_id: str, db: Session = OTURUM,
                      kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Turun kayıtları, sütun sırasında. Bilinmeyen turda boş liste.

    Döküm arena satırını KENDİ kayıtlarından çiziyor; bu uç yalnızca "kazanan
    hangisi" sorusunu cevaplıyor. Ayrı bir uç, çünkü `/api/history` KLASÖRE
    göre süzülüyor: başka klasöre taşınmış bir sütunu hiç döndürmezdi
    (chat.js'in `/output/{id}.png` kararının aynı gerekçesi).

    404 YOK: silinmiş bir tur, boş bir tur gibi okunuyor — döküm satırı yine
    çizilebilir olmalı (sarkan id'nin yer tutucu davranışıyla aynı duruş).
    """
    return {"images": depo_medya.arena_turu(db, kullanici.id, os.path.basename(arena_id))}


@router.post("/api/arena/{arena_id}/winner")
def set_arena_winner_route(arena_id: str, req: ArenaWinnerRequest, db: Session = OTURUM,
                           kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Arena turunun kazananını işaretler; tur başına TEK kazanan.

    Elenen sonuç SİLİNMİYOR — işaret bir tercih kaydı, bir çöp kutusu değil:
    kullanıcı iki gün sonra ötekini indirebilmeli. Depoda tek yazımla
    yapılıyor (bkz. depo_medya.arena_kazanani).
    """
    aid = os.path.basename(arena_id)
    iid = os.path.basename(req.image_id)
    if not depo_medya.arena_kazanani(db, kullanici.id, aid, iid):
        raise HTTPException(status_code=404,
                            detail=i18n.t("err.arena_or_image_missing", dil.aktif()))
    return {"arena_id": aid, "winner": iid}


@router.delete("/api/image/{image_id}")
def delete_image(image_id: str, db: Session = OTURUM,
                 ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                 kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                 depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    iid = os.path.basename(image_id)
    removed = depo_medya.sil(db, kullanici.id, iid, ayarlar.output_dir, depo=depo)
    if not removed:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"deleted": iid}


@router.patch("/api/images")
def move_images(req: BulkMoveRequest, db: Session = OTURUM,
                kullanici: Kullanici = Depends(kimlik.aktif_kullanici)) -> dict:
    """Seçili görselleri bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = kapilar.check_folder(req.folder_id, db, kullanici.id)
    ids = [os.path.basename(i) for i in req.ids]
    moved = depo_medya.klasor_ata_coklu(db, kullanici.id, ids, target)
    if not moved:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"moved": moved, "folder_id": target}


@router.delete("/api/images")
def delete_images(req: BulkImagesRequest, db: Session = OTURUM,
                  ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                  kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                  depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    """Seçili görselleri siler (kayıt + dosya)."""
    ids = [os.path.basename(i) for i in req.ids]
    deleted = depo_medya.sil_coklu(db, kullanici.id, ids, ayarlar.output_dir, depo=depo)
    if not deleted:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"deleted": deleted}


@router.post("/api/import")
async def import_image(request: Request,
                       file: UploadFile = File(...),
                       folder_id: str | None = Form(None),
                       db: Session = OTURUM,
                       ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                       kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                       depo: dosya.Depo = Depends(dosya.depo)) -> dict:
    """Bilgisayardan sürüklenen bir görseli galeriye (isteğe bağlı klasöre) aktarır.

    ÜRETİMDEN DOĞMAYAN ilk kayıt türü: prompt yok, palet yok, Azure'a hiç
    çıkılmaz. Dosya `gorsel.read_upload_png` ile doğrulanıp PNG'ye YENİDEN
    KODLANIR — `/output/{filename}`, `depo_medya.sil` ve `gorsel.output_png_path`
    dosyanın `{id}.png` olduğunu varsayıyor; JPEG olduğu gibi kaydedilirse
    kayıt görünür ama görsel açılmaz.

    Sıra bilinçli: content-length → klasör → gövde. Geçersiz bir klasör için
    10 MB'ı okumak boşuna iş.

    Dosya başına TEK istek: arayüz çoklu bırakmayı sıraya koyuyor. Toplu bir uç
    yok — o kısıt `history.json`ın tam-dosya yazımından geliyordu (Faz 1 / 5'te
    kalktı), ama arayüzün sırası ve tek dosyalık gövde sözleşmesi duruyor.

    `async def` rota: DB çağrıları `run_in_threadpool` ile (senkron sürücü olay
    döngüsünü kilitlemesin — belge §1'in sürücü kararı, §5'in 5 async rota notu).
    """
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > gorsel.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.file_too_big", dil.aktif()))
    target_folder = await run_in_threadpool(kapilar.check_folder, folder_id, db, kullanici.id)
    png = await gorsel.read_upload_png(file)

    # Dosya adı yalnızca ETİKET (galeri başlığı/alt metni); kayıt adı uuid'den
    # geliyor. basename yol parçalarını düşürür, kırpma başlığı taşırmaz.
    label = os.path.basename(file.filename or "").strip()[:120] or i18n.t("media.imported_image", dil.aktif())
    record = await run_in_threadpool(
        depo_medya.kaydet, db, kullanici.id, png,
        {"prompt": label, "size": gorsel.png_dimensions(png), "quality": "",
         "parent_id": None, "folder_id": target_folder,
         "palette": None, "prompt_sent": None, "imported": True,
         # BOŞ bilerek: bu görsel başka bir araçta üretildi, bir modeli yok.
         # (bkz. storage.save → "model")
         "model": ""},
        ayarlar.output_dir, now=zaman.an(), depo=depo,
    )
    return {"image": record}


def _medya_cevabi(yol: str, depo: dosya.Depo, *, indirme_adi: str | None = None) -> Response:
    """Dosyayı SUN: kovada 302 → ön imzalı URL, yerelde `FileResponse` (K7).

    302'nin gerekçesi: `<img>`/`<video>` yönlendirmeyi takip eder, `<video>`nun
    aralık (Range) istekleri doğrudan R2'ye gider — uygulama süreci bayt
    taşımaz, R2'nin sıfır çıkış ücreti ancak böyle gerçekleşir. `Cache-Control:
    private, max-age=600`: aynı sekmede aynı görsel 10 dk boyunca yeniden
    sorulmaz (URL 15 dk yaşıyor; önbellek ömürden kısa ki bayat adres
    hiç kullanılmasın); `private`, çünkü adres sahibine özel. `indirme_adi`
    kovada `response-content-disposition` ile R2'ye, yerelde `FileResponse`un
    `filename`ine gider — iki yolda da tarayıcı aynı `attachment` başlığını görür.
    """
    url = depo.url(yol, dosya.URL_SURESI, indirme_adi=indirme_adi)
    ad = os.path.basename(yol)
    if url is not None:
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": dosya.CACHE_CONTROL})
    return FileResponse(yol, media_type=storage.media_type_for(ad), filename=indirme_adi)


@router.get("/output/{filename}")
def output_file(filename: str, db: Session = OTURUM,
                ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                depo: dosya.Depo = Depends(dosya.depo)) -> Response:
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

    Dosya adı `medya.filename`de ARANIYOR (Faz 1 / 5): kullanıcının satırı
    yoksa dosya diskte dursa bile 404 — servis yolunun gerçeği DB satırı,
    dizin değil (bkz. depo_medya.dosya_yolu_adiyla).

    Kovada 302 → ön imzalı URL, yerelde `FileResponse` (Faz 2 / 2, `_medya_cevabi`);
    sahiplik süzgeci iki yolda da AYNI satır sorgusu — başkasının dosyası 404.
    """
    safe = os.path.basename(filename)
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    path = depo_medya.dosya_yolu_adiyla(db, kullanici.id, safe, ayarlar.output_dir, depo=depo)
    if path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    return _medya_cevabi(path, depo)


@router.get("/api/output/{image_id}/download")
def output_download(image_id: str, db: Session = OTURUM,
                    ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar),
                    kullanici: Kullanici = Depends(kimlik.aktif_kullanici),
                    depo: dosya.Depo = Depends(dosya.depo)) -> Response:
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

    Path-traversal guard'ı yeniden yazılmıyor: id `basename`e iner ve
    `depo_medya.dosya_yolu` `_SAFE_ID`den geçirip kullanıcının satırını arar;
    satır ya da dosya yoksa 404 burada.

    TÜR VE DOSYA ADI SATIRDAKİ DOSYA ADINDAN geliyor — `image_id`ye uzantı
    EKLENMİYOR. Fark v0.13'te gerçek oldu: `f"{id}.png"` yazan bir indirme,
    bir videoyu `.png` adıyla teslim ederdi ve dosya kullanıcının
    diskinde açılmayan bir şey olurdu. Adı kayıttaki gerçeğe bağlamak, aynı
    zamanda `download` özniteliğiyle (`folders.js` onu `rec.filename`den
    veriyor) tek bir gerçeği paylaşmak demek. Kovada aynı ad
    `response-content-disposition` ile ön imzalı URL'ye gömülür (302).
    """
    path = depo_medya.dosya_yolu(db, kullanici.id, os.path.basename(image_id), ayarlar.output_dir,
                                 depo=depo)
    if path is None:
        raise HTTPException(status_code=404, detail=i18n.t("err.source_media_missing", dil.aktif()))
    return _medya_cevabi(path, depo, indirme_adi=os.path.basename(path))
