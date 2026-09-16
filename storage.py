# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Üretilen MEDYANIN diske kaydı ve history.json yönetimi.

Atomik yazım ve "oku → değiştir → yaz" kilidi jsonstore.py'de paylaşılıyor:
manifest deposu olan beş dosya aynı iki mekaniği kullanıyor.

"GÖRSEL" DEĞİL "MEDYA": v0.13'ten beri depo iki tür taşıyor (PNG ve MP4) ve
türü söyleyen tek şey kaydın `kind` alanı. Uzantı ondan TÜRETİLİYOR
(bkz. `save`), yani ikinci bir gerçek kaynağı yok — kayıtta `"kind": "video"`
yazıyorsa dosya `.mp4`'tür, tersi de doğrudur. Alan adları (`image_id`,
`image_ids`) DEĞİŞMEDİ ve bu bilinçli: onlar `history.json`da, `chats.json`da
ve `/api/image/{id}` ucunda yaşayan KİMLİK adları — yeniden adlandırmak, tek
kazancı estetik olan bir veri göçü olurdu.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import uuid
from collections.abc import Iterable

import catalog
import jsonstore

HISTORY_FILE = "history.json"

# `kind` → dosya uzantısı. TEK eşleme noktası: `save` uzantıyı buradan
# alıyor, `media_type_for` de MIME'ı uzantıdan çözüyor, yani zincir tek yönlü
# ve tek kaynaklı (kind → uzantı → MIME).
MEDIA_EXTS = {"video": ".mp4"}
DEFAULT_EXT = ".png"

# Uzantı → HTTP içerik türü. `app.py` bu tabloyu okuyor; oradaki üç rota
# (`/output/{filename}`, indirme ucu ve varlık rotası) v0.13'e kadar
# `image/png`i ÇAKILI taşıyordu. Tablo BURADA, `app.py`de değil: uzantı
# kararının verildiği yer bu dosya ve iki bilgiyi ayrı dosyalarda tutmak,
# birine tür ekleyip ötekini unutmanın kapısı olurdu — bir MP4'ü
# `image/png` olarak sunmak tarayıcıda sessiz bir bozuk resim demek.
MEDIA_TYPES = {".png": "image/png", ".mp4": "video/mp4"}
FALLBACK_MEDIA_TYPE = "application/octet-stream"


def ext_for(kind: str | None) -> str:
    """Medya türünün dosya uzantısı. Bilinmeyen/boş tür → `.png`.

    Varsayılanın PNG olması geriye uyum: `kind` göndermeyen her çağıran
    (üretim öncesi yollar, içe aktarma, logo/afiş bindirmeleri) bugünkü
    davranışı bayt bayt koruyor.
    """
    return MEDIA_EXTS.get(kind or "", DEFAULT_EXT)


def media_path_of(image_id: str, output_dir: str) -> str | None:
    """`{id}` için diskte GERÇEKTEN duran dosyanın yolu; yoksa None.

    UZANTI DENENİYOR, kayıttan okunmuyor — ve bunun sebebi silme
    sözleşmesinin kendisi: "kaydı olmayan ama dosyası olan id de silinmiş
    sayılır", yani türü söyleyecek bir kayıt OLMADIĞI hâl sözleşmede yazılı.
    Deneme kümesi `MEDIA_TYPES`ten geliyor, yani uzantı kararının verildiği
    yer; yeni bir tür eklendiğinde silme yolunda hatırlanacak bir şey yok.

    İKİ TARAFTAN OKUNUYOR: `delete`/`delete_many` ve `app._output_media_path`.
    Üçü de v0.13'e kadar `f"{id}.png"` yazıyordu ve o doğruydu (depoda tek
    tür vardı); MP4 gelince o literal SESSİZ BİR SIZINTI oldu — kayıt
    siliniyor, dosya diskte kalıyor ve `/output/{id}.mp4` ile indirme ucu onu
    sunmaya devam ediyordu (megabaytlarca, hiçbir arayüzün ulaşamadığı yerde).
    """
    for uzanti in MEDIA_TYPES:
        path = os.path.join(output_dir, f"{image_id}{uzanti}")
        if os.path.isfile(path):
            return path
    return None


def media_type_for(filename: str) -> str:
    """Dosya adından HTTP içerik türü.

    Bilinmeyen uzantıda `application/octet-stream` — `image/png` DEĞİL. Ayrım
    önemli: yanlış bir `image/png`, tarayıcıya "bunu resim olarak çiz" demek
    ve sonuç sessizce bozuk bir resim oluyor; octet-stream ise "ne olduğunu
    bilmiyorum" diyor ve tarayıcı indirmeyi öneriyor. İkisi de hata hâli, ama
    yalnız ikincisi kendini gösteriyor.
    """
    _kok, _nokta, uzanti = filename.rpartition(".")
    return MEDIA_TYPES.get("." + uzanti.lower(), FALLBACK_MEDIA_TYPE)

# Image ids are generated as uuid.uuid4().hex[:12] (see save()): bare lowercase
# hex tokens with no separators or dots. Reject anything else up front so a
# malicious/malformed id can never reach a filesystem path.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def valid_id(value: str | None) -> bool:
    """`_SAFE_ID` guard'ı, dışarıya açık hâli (bkz. chat_store.valid_id).

    Ayrı bir fonksiyon çünkü `/api/generate` de bunu soruyor: bir kayda
    yazılacak `arena_id` uçta reddedilmezse depoya kadar iner ve orada
    SESSİZCE düşürülürdü — turun sütunları birbirini bulamaz, sebebi de
    hiçbir yerde görünmezdi (app._check_session'ın kuralı).
    """
    return bool(value) and _SAFE_ID.fullmatch(value) is not None


def _history_path(output_dir: str) -> str:
    return os.path.join(output_dir, HISTORY_FILE)


def _read_history(output_dir: str) -> list[dict]:
    path = _history_path(output_dir)
    if not os.path.exists(path):
        return []
    # encoding="utf-8" AÇIKÇA: yazma yolu (jsonstore.write_atomic) utf-8 yazıyor,
    # okuma yolu ise bunu vermediği sürece platformun varsayılanına düşer. Türkçe
    # Windows'ta o varsayılan cp1254'tür → Türkçe promptlu bir geçmiş ya mojibake
    # olur ("Zümrüt" → "ZÃ¼mrÃ¼t") ya da UnicodeDecodeError ile listelemeyi
    # çökertir. macOS/Linux'ta varsayılan zaten utf-8 olduğu için kusur uzun süre
    # görünmedi; Windows paketlemesinin ilk test turunda ortaya çıktı.
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Corrupt/unreadable history: tolerate it as empty history rather
            # than crashing the app. Other errors (e.g. permission errors)
            # still propagate.
            return []
    if not isinstance(data, list):
        return []
    return data


def _write_history(output_dir: str, history: list[dict]) -> None:
    jsonstore.write_atomic(_history_path(output_dir), history)


def _lock(output_dir: str):
    """Bu history.json'ın yazma kilidi — okuma ile yazım arasına girilmesin."""
    return jsonstore.lock_for(_history_path(output_dir))


def save(image_bytes: bytes, meta: dict, output_dir: str, *, now: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    image_id = uuid.uuid4().hex[:12]
    # Uzantı `kind`dan TÜRETİLİYOR, çağıran ayrıca dosya adı vermiyor: iki
    # bilgi (tür ve uzantı) ayrı ayrı geçirilse ayrışabilirlerdi ve
    # ayrıştıkları anda `/output/{filename}` yanlış MIME sunardı.
    filename = f"{image_id}{ext_for(meta.get('kind'))}"
    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(image_bytes)
    record = {
        "id": image_id,
        "filename": filename,
        "prompt": meta.get("prompt", ""),
        "size": meta.get("size", ""),
        "quality": meta.get("quality", ""),
        "created_at": now,
        "parent_id": meta.get("parent_id"),
        # None/eksik = klasörsüz (kök). Eski kayıtlarda bu alan hiç yoktur;
        # okurken .get("folder_id") ile kök kabul edilir → geçiş gerekmez.
        "folder_id": meta.get("folder_id"),
        # None/eksik = palet kullanılmadı. folder_id ile aynı mantık: eski
        # kayıtlarda alan yok, okurken .get("palette") None verir → geçiş yok.
        "palette": meta.get("palette"),
        # Azure'a GİDEN tam metin, yalnızca prompt'tan farklıysa. "Palet
        # gerçekten uygulandı mı?" sorusunun adli cevabı; `prompt` alanı
        # kullanıcının yazdığı ham metin olarak kalmak zorunda (galeri
        # başlıkları, türev prompt kopyalama ve mevcut testler ona bağlı).
        "prompt_sent": meta.get("prompt_sent"),
        # İÇE AKTARMA İŞARETİ (v1.12): kayıt bilgisayardan sürüklenen bir
        # dosyadan doğduysa True. KOŞULLU yazılıyor — üretilen kayıtlar
        # bugünküyle bayt bayt aynı kalsın (galeri ve eski-biçim testleri buna
        # bağlı). folder_id/palette ile aynı geçiş stratejisi: eski kayıtlarda
        # alan yok, okuyan taraf .get()/falsy kontrolü yapıyor → göç gerekmez.
        **({"imported": True} if meta.get("imported") else {}),
        # OTURUM ETİKETİ (v2.0): kayıt bir oturumun içinde üretildiyse o oturumun
        # `chats.json` id'si. Yeni bir kimlik uzayı açılmadı. `imported` ile
        # birebir aynı koşullu desen ve aynı gerekçe: oturum dışı üretim (Medya'dan
        # doğrudan ya da otomatik kayıt kapalıyken) kalıcı bir hâl, o kayıtlara
        # `"session_id": null` yazmak history.json'ın tamamını değiştirirdi.
        **({"session_id": meta["session_id"]} if meta.get("session_id") else {}),
        # ARENA ETİKETİ: kayıt, aynı prompt'u birden çok modelde koşturan bir
        # turun sütunlarından biriyse o turun id'si. `session_id` ile birebir
        # aynı koşullu desen ve aynı gerekçe — arena DIŞI üretim kalıcı bir hâl
        # ve o kayıtlara `"arena_id": null` yazmak history.json'ın tamamını
        # değiştirirdi.
        #
        # Turun sütunları AYRI kayıtlar (kayıt başına tek `model`, tek
        # `credits`); onları birbirine bağlayan tek şey bu alan. `parent_id`
        # kullanılmadı: o TÜREV zinciri (bir görselden düzenleme), arena
        # sütunları ise kardeş — hiçbiri ötekinin ebeveyni değil.
        **({"arena_id": meta["arena_id"]} if meta.get("arena_id") else {}),
        # MEDYA TÜRÜ (v0.13) ve klip SÜRESİ. `imported`/`session_id`/`arena_id`
        # ile birebir aynı KOŞULLU desen ve aynı gerekçe: yokluğun tanımlı bir
        # anlamı var ("görsel", "süresi yok"), yani göç GEREKMİYOR ve bugüne
        # kadar üretilmiş her görsel kaydı bayt bayt aynı kalıyor.
        #
        # `model`/`credits`in KOŞULSUZ deseni burada BİLEREK kullanılmıyor:
        # onlar her üretilen kayıtta var olan olgular, tür ise gerçek bir
        # yokluk hâli taşıyor — `history.json`ın tamamına `"kind": "image"`
        # yazmak, hiçbir soruyu cevaplamayan bir göç olurdu.
        **({"kind": meta["kind"]} if meta.get("kind") else {}),
        **({"duration": int(meta["duration"])} if meta.get("duration") else {}),
        # ÜRETEN MODEL (v0.6) ve o üretimin KREDİ maliyeti.
        #
        # İkisi de KOŞULSUZ — `imported`/`session_id`'nin koşullu deseni burada
        # BİLEREK kullanılmıyor. Ayrım şu: o iki alan gerçek bir YOKLUK hâlini
        # anlatıyor (kayıt içe aktarılmadıysa `imported` hiç olmaz, oturum dışı
        # üretimin `session_id`'si hiç olmaz). Model ise HER üretilen kayıtta
        # vardır; alanın yokluğu ancak "o günün varsayılanı" demek olurdu ve
        # varsayılan DEĞİŞECEK — yani tam olarak bu deponun sevmediği sessiz
        # belirsizlik. Üstelik /api/edit'in bayat-sunucu yankı kontrolü
        # (core.js) alan yokken varsayılan modelde kör kalırdı.
        #
        # Eski kayıtlar DOKUNULMADAN kalıyor: okuyan taraf
        # `.get("model") or catalog.DEFAULT_IMAGE_MODEL` diyor —
        # folder_id/palette ile aynı "yokluğun tanımlı anlamı var" disiplini,
        # göç YOK. Ölçüldü: tests/test_legacy_formats.py yalnız alan KAYBINI
        # kovalıyor (`legacy - set(produced)`), alan eklemek testi kırmıyor.
        #
        # AYRIM `in` ile, `or` ile DEĞİL: çağıran alanı GÖNDERDİYSE değer
        # onun sözü — boş dize dahil. `or` her boş değeri varsayılana
        # çeviriyordu ve ÜRETİM OLMAYAN üç yol (`/api/import` içe aktarımı,
        # logo ve afiş bindirmeleri) modeli hiç geçmediği için kayda
        # "azure-gpt-image-2 üretti" yazılıyordu. Bindirmeler artık KAYNAĞIN
        # modelini devralıyor (türev kendi başına bir üretim değil), içe
        # aktarım ise boş dize geçiyor: "üreteni yok", `credits: 0`ın
        # ("bedeli yok") tam karşılığı. İkisi de uydurma değil ölçülmüş olgu
        # — bu alanın tek müşterisi ileride gelecek kredi ledger'ı.
        #
        # Alanı HİÇ göndermeyen çağıran eski üretim yolu; orada varsayılan
        # doğru cevap olmaya devam ediyor.
        "model": (str(meta["model"] or "") if "model" in meta
                  else catalog.DEFAULT_IMAGE_MODEL),
        # ÜRETİM ANINDAKİ çözülmüş tam sayı, katalog işaretçisi DEĞİL: bir
        # modelin tarifesi değişince geçmiş retroaktif olarak yeniden yazılmış
        # olurdu (palette_store'un dondurulmuş `colors` disiplini). İleride
        # gelecek kredi ledger'ının ihtiyacı olan tek şey bu alan; bugün
        # hiçbir yerde bakiye düşülmüyor, hiçbir üretim engellenmiyor.
        "credits": int(meta.get("credits") or 0),
    }
    # immutable append: yeni liste yaz
    with _lock(output_dir):
        _write_history(output_dir, _read_history(output_dir) + [record])
    return record


def list_history(output_dir: str) -> list[dict]:
    return list(reversed(_read_history(output_dir)))


def set_folder(image_id: str, folder_id: str | None, output_dir: str) -> bool:
    """Bir görselin klasörünü değiştirir (None = klasörsüz/kök).

    Dosya taşınmaz — klasör yalnızca kayıttaki bir etikettir, bu yüzden
    `/output/{filename}` URL'leri ve türev zincirleri etkilenmez.
    Kayıt yoksa veya id formatı geçersizse False döner.
    """
    if not _SAFE_ID.fullmatch(image_id):
        return False
    with _lock(output_dir):
        history = _read_history(output_dir)
        if not any(r.get("id") == image_id for r in history):
            return False
        _write_history(output_dir,
                       [{**r, "folder_id": folder_id} if r.get("id") == image_id else r
                        for r in history])
    return True


def arena_round(arena_id: str, output_dir: str) -> list[dict]:
    """Bir arena turunun kayıtları, ÜRETİM SIRASINDA (sütun sırası).

    `list_history` TERSTEN veriyor (galeri en yeniyi üstte istiyor); arena
    satırı ise sütunları soldan sağa, üretildikleri sırayla çiziyor — bu yüzden
    ham sıra kullanılıyor.

    Turun kazananı `history.json`da yaşıyor ve TEK kaynak orası: döküm kaydına
    ikinci bir kopya yazılsaydı oturum kaydedilmeyen bir turda ikisi ayrışırdı.
    """
    if not valid_id(arena_id):
        return []
    return [r for r in _read_history(output_dir) if r.get("arena_id") == arena_id]


def set_arena_winner(arena_id: str, image_id: str, output_dir: str) -> bool:
    """Bir arena turunun kazananını işaretler. Tur başına TEK kazanan.

    Kazanana `arena_win: True` yazılır, aynı turun ÖTEKİ kayıtlarından alan
    SİLİNİR — `False` yazmak yerine silmek koşullu alan geleneğinin (bkz. save)
    devamı: "işaret yok" hâli alanın YOKLUĞU ile anlatılıyor ve hiç kazanan
    seçilmemiş turlar history.json'da bugünküyle bayt bayt aynı kalıyor.

    TEK yazımda yapılıyor: kazanana yazıp kardeşlerden silmek iki ayrı yazım
    olsaydı arada okuyan bir istemci İKİ kazanan görürdü (`set_folder_many`'nin
    gerekçesinin aynısı — her yazım dosyanın tamamını değiştiriyor).

    Kayıt yoksa, id formatı geçersizse ya da görsel o turun içinde DEĞİLSE
    False döner. İdempotent: aynı kazanana ikinci çağrı aynı sonucu verir.
    """
    if not _SAFE_ID.fullmatch(image_id) or not _SAFE_ID.fullmatch(arena_id):
        return False
    with _lock(output_dir):
        history = _read_history(output_dir)
        if not any(r.get("id") == image_id and r.get("arena_id") == arena_id
                   for r in history):
            return False
        yeni = []
        for r in history:
            if r.get("arena_id") != arena_id:
                yeni.append(r)
            elif r.get("id") == image_id:
                yeni.append({**r, "arena_win": True})
            else:
                yeni.append({k: v for k, v in r.items() if k != "arena_win"})
        _write_history(output_dir, yeni)
    return True


def unfile_folders(folder_ids: Iterable[str], output_dir: str) -> int:
    """Verilen klasörlerdeki tüm kayıtları klasörsüz hale getirir; etkilenen sayıyı döndürür.

    Klasör (ve alt klasör) ağacı silinirken kullanılır: görseller SİLİNMEZ, yalnızca
    köke döner. Ağacın tamamı TEK yazımda işlenir — id başına ayrı yazım yapılmaz.
    """
    targets = {fid for fid in folder_ids if fid}
    if not targets:
        return 0
    with _lock(output_dir):
        history = _read_history(output_dir)
        affected = sum(1 for r in history if r.get("folder_id") in targets)
        if affected:
            _write_history(output_dir,
                           [{**r, "folder_id": None} if r.get("folder_id") in targets else r
                            for r in history])
    return affected


def unfile_folder(folder_id: str, output_dir: str) -> int:
    """Tek klasör için `unfile_folders` kısayolu."""
    return unfile_folders([folder_id], output_dir)


def set_folder_many(image_ids: Iterable[str], folder_id: str | None, output_dir: str) -> int:
    """Birden çok görseli tek yazımda aynı klasöre taşır; taşınan sayıyı döndürür.

    Çoklu seçimle taşıma için: id başına ayrı yazım yapmak history.json'da
    kayıp güncellemeye yol açardı (her yazım dosyanın tamamını değiştiriyor).
    Bilinmeyen veya geçersiz id'ler sessizce atlanır — sayı gerçekten taşınanı verir.
    """
    targets = {iid for iid in image_ids if iid and _SAFE_ID.fullmatch(iid)}
    if not targets:
        return 0
    with _lock(output_dir):
        history = _read_history(output_dir)
        moved = sum(1 for r in history if r.get("id") in targets)
        if moved:
            _write_history(output_dir,
                           [{**r, "folder_id": folder_id} if r.get("id") in targets else r
                            for r in history])
    return moved


def delete_many(image_ids: Iterable[str], output_dir: str) -> int:
    """Birden çok görseli tek yazımda siler (dosya + kayıt); silinen sayıyı döndürür.

    `delete()` ile aynı sözleşme: dosya adı `{id}.{uzantı}` (uzantı kaydın
    `kind`inden doğuyor, bkz. `save`), kaydı olmayan ama dosyası olan (veya
    tersi) id de silinmiş sayılır.
    """
    targets = {iid for iid in image_ids if iid and _SAFE_ID.fullmatch(iid)}
    if not targets:
        return 0
    with _lock(output_dir):
        history = _read_history(output_dir)
        remaining = [r for r in history if r.get("id") not in targets]
        existing_records = {r.get("id") for r in history if r.get("id") in targets}

        deleted = set(existing_records)
        for image_id in targets:
            # UZANTI ARANIYOR, yazılmıyor (bkz. `media_path_of`): `.png` çakılı
            # kalsaydı bir video kaydı silinirken dosyası diskte kalırdı.
            file_path = media_path_of(image_id, output_dir)
            if file_path:
                # Bulma ile `remove` arasında dosya kaybolabilir (aynı görseli
                # iki sekmeden silmek yeter). Sonuç zaten istenen: dosya yok.
                with contextlib.suppress(FileNotFoundError):
                    os.remove(file_path)
                deleted.add(image_id)

        if existing_records:
            _write_history(output_dir, remaining)
    return len(deleted)


def delete(image_id: str, output_dir: str) -> bool:
    if not _SAFE_ID.fullmatch(image_id):
        return False

    with _lock(output_dir):
        history = _read_history(output_dir)
        remaining = [r for r in history if r.get("id") != image_id]
        record_existed = len(remaining) != len(history)

        # `delete_many` ile aynı arama (bkz. `media_path_of`).
        file_path = media_path_of(image_id, output_dir)
        file_existed = file_path is not None
        if file_existed:
            # delete_many ile aynı yarış: araya başka bir silme girebilir.
            with contextlib.suppress(FileNotFoundError):
                os.remove(file_path)

        if record_existed:
            _write_history(output_dir, remaining)

    return record_existed or file_existed
