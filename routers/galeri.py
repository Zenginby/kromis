# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Galeri uçları: klasörler, geçmiş, taşıma/silme, arena, içe aktarma, medya servisi."""
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response

import folders
import i18n
import storage
from models import (
    ArenaWinnerRequest,
    BulkImagesRequest,
    BulkMoveRequest,
    FolderRequest,
    MoveImageRequest,
)
from services import dil, gorsel, kapilar, yollar, zaman

router = APIRouter()

MAX_FOLDER_DEPTH = 5                         # iç içe klasör kademesi


@router.get("/api/folders")
def list_folders_route() -> dict:
    """Tüm klasörler (düz liste) + görsel ve alt klasör sayıları.

    Hiyerarşi `parent_id` ile taşınır; arayüz şeridi buna göre süzer, böylece
    sayaçlar ve sürükle-bırak hedefleri tek istekte tazelenir.
    """
    output_dir = yollar.output_dir()
    counts: dict[str, int] = {}
    for rec in storage.list_history(output_dir):
        fid = rec.get("folder_id")
        if fid:
            counts[fid] = counts.get(fid, 0) + 1
    items = folders.list_folders(output_dir)
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
def create_folder_route(req: FolderRequest) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=i18n.t("err.folder_name_required", dil.aktif()))
    parent_id = kapilar.check_folder(req.parent_id)
    # Sınırsız derinlik başlık şeridini taşırıyor ve köke dönüşü zorlaştırıyor;
    # yeniden ebeveynleme olmadığı için tek kapı burası.
    if parent_id and folders.depth(parent_id, yollar.output_dir()) >= MAX_FOLDER_DEPTH:
        raise HTTPException(
            status_code=422,
            detail=i18n.t("err.folder_depth", dil.aktif(), adet=MAX_FOLDER_DEPTH))
    return {"folder": folders.create(name, yollar.output_dir(), parent_id=parent_id,
                                     now=zaman.simdi())}


@router.delete("/api/folders/{folder_id}")
def delete_folder_route(folder_id: str) -> dict:
    """Klasörü ve alt klasörlerini siler; GÖRSELLER silinmez, klasörsüz (kök) hale döner."""
    output_dir = yollar.output_dir()
    fid = os.path.basename(folder_id)
    # Sıra önemli: önce ağacı çöz (yoksa 404), sonra görselleri çıkar, sonra kayıtları sil.
    doomed = folders.descendants(fid, output_dir)
    if not doomed:
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    unfiled = storage.unfile_folders(doomed, output_dir)
    deleted = folders.delete_tree(fid, output_dir)
    return {"deleted": deleted, "folders": len(deleted), "unfiled": unfiled}


@router.get("/api/folders/{folder_id}/download")
def download_folder_route(folder_id: str):
    """Klasörü ve alt klasörlerini görselleriyle birlikte ZIP olarak indirir."""
    output_dir = yollar.output_dir()
    fid = os.path.basename(folder_id)
    if not folders.exists(fid, output_dir):
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    try:
        zip_bytes, folder_name = folders.export_zip(fid, output_dir)
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


@router.patch("/api/folders/{folder_id}")
def rename_folder_route(folder_id: str, req: FolderRequest) -> dict:
    """Klasör adını değiştirir."""
    fid = os.path.basename(folder_id)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=i18n.t("err.folder_name_required", dil.aktif()))
    updated = folders.rename(fid, name, yollar.output_dir())
    if not updated:
        raise HTTPException(status_code=404, detail=i18n.t("err.folder_missing", dil.aktif()))
    return {"folder": updated}


@router.get("/api/history")
def history(folder_id: str | None = None) -> dict:
    """folder_id yoksa yalnızca klasörsüz görseller (kök), varsa o klasörünkiler."""
    items = storage.list_history(yollar.output_dir())
    if folder_id:
        kapilar.check_folder(folder_id)
        items = [r for r in items if r.get("folder_id") == folder_id]
    else:
        items = [r for r in items if not r.get("folder_id")]
    return {"images": items}


@router.patch("/api/image/{image_id}")
def move_image(image_id: str, req: MoveImageRequest) -> dict:
    """Görseli bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = kapilar.check_folder(req.folder_id)
    iid = os.path.basename(image_id)
    if not storage.set_folder(iid, target, yollar.output_dir()):
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"id": iid, "folder_id": target}


@router.get("/api/arena/{arena_id}")
def arena_round_route(arena_id: str) -> dict:
    """Turun kayıtları, sütun sırasında. Bilinmeyen turda boş liste.

    Döküm arena satırını KENDİ kayıtlarından çiziyor; bu uç yalnızca "kazanan
    hangisi" sorusunu cevaplıyor. Ayrı bir uç, çünkü `/api/history` KLASÖRE
    göre süzülüyor: başka klasöre taşınmış bir sütunu hiç döndürmezdi
    (chat.js'in `/output/{id}.png` kararının aynı gerekçesi).

    404 YOK: silinmiş bir tur, boş bir tur gibi okunuyor — döküm satırı yine
    çizilebilir olmalı (sarkan id'nin yer tutucu davranışıyla aynı duruş).
    """
    return {"images": storage.arena_round(os.path.basename(arena_id), yollar.output_dir())}


@router.post("/api/arena/{arena_id}/winner")
def set_arena_winner_route(arena_id: str, req: ArenaWinnerRequest) -> dict:
    """Arena turunun kazananını işaretler; tur başına TEK kazanan.

    Elenen sonuç SİLİNMİYOR — işaret bir tercih kaydı, bir çöp kutusu değil:
    kullanıcı iki gün sonra ötekini indirebilmeli. Depoda tek yazımla
    yapılıyor (bkz. storage.set_arena_winner).
    """
    aid = os.path.basename(arena_id)
    iid = os.path.basename(req.image_id)
    if not storage.set_arena_winner(aid, iid, yollar.output_dir()):
        raise HTTPException(status_code=404,
                            detail=i18n.t("err.arena_or_image_missing", dil.aktif()))
    return {"arena_id": aid, "winner": iid}


@router.delete("/api/image/{image_id}")
def delete_image(image_id: str) -> dict:
    iid = os.path.basename(image_id)
    removed = storage.delete(iid, yollar.output_dir())
    if not removed:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"deleted": iid}


@router.patch("/api/images")
def move_images(req: BulkMoveRequest) -> dict:
    """Seçili görselleri bir klasöre taşır (folder_id=None ise köke). Dosya taşınmaz."""
    target = kapilar.check_folder(req.folder_id)
    ids = [os.path.basename(i) for i in req.ids]
    moved = storage.set_folder_many(ids, target, yollar.output_dir())
    if not moved:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"moved": moved, "folder_id": target}


@router.delete("/api/images")
def delete_images(req: BulkImagesRequest) -> dict:
    """Seçili görselleri siler (dosya + kayıt)."""
    ids = [os.path.basename(i) for i in req.ids]
    deleted = storage.delete_many(ids, yollar.output_dir())
    if not deleted:
        raise HTTPException(status_code=404, detail=i18n.t("err.image_missing", dil.aktif()))
    return {"deleted": deleted}


@router.post("/api/import")
async def import_image(request: Request,
                       file: UploadFile = File(...),
                       folder_id: str | None = Form(None)) -> dict:
    """Bilgisayardan sürüklenen bir görseli galeriye (isteğe bağlı klasöre) aktarır.

    ÜRETİMDEN DOĞMAYAN ilk kayıt türü: prompt yok, palet yok, Azure'a hiç
    çıkılmaz. Dosya `gorsel.read_upload_png` ile doğrulanıp PNG'ye YENİDEN
    KODLANIR — `/output/{filename}`, `storage.delete` ve `gorsel.output_png_path`
    dosyanın `{id}.png` olduğunu varsayıyor; JPEG olduğu gibi kaydedilirse
    kayıt görünür ama görsel açılmaz.

    Sıra bilinçli: content-length → klasör → gövde. Geçersiz bir klasör için
    10 MB'ı okumak boşuna iş.

    Dosya başına TEK istek: arayüz çoklu bırakmayı sıraya koyuyor. Toplu bir uç
    yok, çünkü `storage.save` her kayıtta history.json'ın tamamını yeniden
    yazıyor ve eşzamanlılık kayıp güncelleme üretir.
    """
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > gorsel.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=i18n.t("err.file_too_big", dil.aktif()))
    target_folder = kapilar.check_folder(folder_id)
    png = await gorsel.read_upload_png(file)

    # Dosya adı yalnızca ETİKET (galeri başlığı/alt metni); kayıt adı uuid'den
    # geliyor. basename yol parçalarını düşürür, kırpma başlığı taşırmaz.
    label = os.path.basename(file.filename or "").strip()[:120] or i18n.t("media.imported_image", dil.aktif())
    record = storage.save(
        png,
        {"prompt": label, "size": gorsel.png_dimensions(png), "quality": "",
         "parent_id": None, "folder_id": target_folder,
         "palette": None, "prompt_sent": None, "imported": True,
         # BOŞ bilerek: bu görsel başka bir araçta üretildi, bir modeli yok.
         # (bkz. storage.save → "model")
         "model": ""},
        yollar.output_dir(), now=zaman.simdi(),
    )
    return {"image": record}


@router.get("/output/{filename}")
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
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    path = os.path.join(yollar.output_dir(), safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=i18n.t("err.not_found", dil.aktif()))
    return FileResponse(path, media_type=storage.media_type_for(safe))


@router.get("/api/output/{image_id}/download")
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

    Path-traversal guard'ı yeniden yazılmıyor: `gorsel.output_media_path` servis
    yolunun tek kapısı ve 404'ü de o veriyor.

    TÜR VE DOSYA ADI, DİSKTEKİ DOSYADAN geliyor — `image_id`ye uzantı
    EKLENMİYOR. Fark v0.13'te gerçek oldu: `f"{id}.png"` yazan bir indirme,
    bir videoyu `.png` adıyla teslim ederdi ve dosya kullanıcının
    diskinde açılmayan bir şey olurdu. Adı diskteki gerçeğe bağlamak, aynı
    zamanda `download` özniteliğiyle (`folders.js` onu `rec.filename`den
    veriyor) tek bir gerçeği paylaşmak demek.
    """
    path = gorsel.output_media_path(image_id)
    ad = os.path.basename(path)
    return FileResponse(path, media_type=storage.media_type_for(ad),
                        filename=ad)
