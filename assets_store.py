"""Kullanıcının logo/banner varlıklarının diske kaydı ve manifest yönetimi.

storage.py ile aynı desenleri izler: _SAFE_ID guard'ı, immutable-append; atomik
manifest yazımı ve yazma kilidi jsonstore.py'de paylaşılıyor. Varlıklar tür başına ayrı bir alt dizinde tutulur:

    <assets_dir>/<kind>/{id}.png
    <assets_dir>/<kind>/index.json   # [{id, filename, name, kind, created_at}]
"""
from __future__ import annotations

import json
import os
import re
import uuid

import jsonstore

MANIFEST_FILE = "index.json"
KINDS = ("logos", "banners", "mottos")

# ── ÖLÜ TÜR: `uploads` ──────────────────────────────────────────────
#
# D9'da dördüncü bir tür vardı ve kütüphanedeki "+ Yükle" düğmesi "Tümü"
# sekmesi seçiliyken oraya yazıyordu. ÇIKMAZ SOKAKTI: bindirme seçicisi yalnız
# logos/mottos/banners okuyor, sunucuda konumlanabilir bindirme de
# `models.OVERLAY_ASSET_KINDS` ile sınırlı — yani oraya düşen bir logo hiçbir
# görsele bindirilemiyordu. Kullanıcının gördüğü şuydu: dosya gidiyor,
# "Eklendi." yazıyor, logo hiçbir yerde kullanılamıyor.
#
# Hedef (sekmesi ve yükleme yolu) kaldırıldı ama TÜR duruyordu, çünkü eskiden
# oraya yazılmış varlıkları kaybetmemek gerekiyordu. Bedeli, yarım bir çözüm
# olmasıydı: o varlıklar "Tümü" listesinde GÖRÜNÜYOR ama hâlâ HİÇBİR yerde
# kullanılamıyordu — kullanıcı aynı çıkmaz sokağı bu kez sessizce yaşıyordu.
#
# Göç bunu kapatıyor: kayıtlar `logos`a taşınıyor (yükleme hedefinin bugünkü
# varsayılanı da orası — `assets.js` UPLOAD_TARGET.all === "logos"), yani
# varlık hem duruyor hem KULLANILABİLİR oluyor, ve tür artık taşınmıyor.
LEGACY_KIND = "uploads"
LEGACY_TARGET = "logos"

# storage._SAFE_ID ile aynı: uuid4().hex[:12] üretimiyle uyumlu bare hex token.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"geçersiz kind: {kind!r}")


def _kind_dir(assets_dir: str, kind: str) -> str:
    _check_kind(kind)
    return os.path.join(assets_dir, kind)


def _manifest_path(kind_dir: str) -> str:
    return os.path.join(kind_dir, MANIFEST_FILE)


def _read_manifest(kind_dir: str) -> list[dict]:
    path = _manifest_path(kind_dir)
    if not os.path.exists(path):
        return []
    # encoding="utf-8" AÇIKÇA — gerekçe storage._read_history'deki ile aynı:
    # manifest utf-8 yazılıyor, okuma platform varsayılanına düşerse Türkçe
    # varlık adları ("KURUM Logo Mavi") Türkçe Windows'ta cp1254 ile bozulur.
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan manifest: çökmek yerine boş kabul et
            # (storage._read_history ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write_manifest(kind_dir: str, items: list[dict]) -> None:
    jsonstore.write_atomic(_manifest_path(kind_dir), items)


def save_asset(kind: str, image_bytes: bytes, name: str, assets_dir: str, *, now: str) -> dict:
    kind_dir = _kind_dir(assets_dir, kind)
    os.makedirs(kind_dir, exist_ok=True)
    asset_id = uuid.uuid4().hex[:12]
    filename = f"{asset_id}.png"
    with open(os.path.join(kind_dir, filename), "wb") as f:
        f.write(image_bytes)
    record = {
        "id": asset_id,
        "filename": filename,
        "name": name,
        "kind": kind,
        "created_at": now,
    }
    # immutable append: yeni liste yaz. Kilit oku→yaz'ı sarıyor (bkz. jsonstore);
    # tür başına ayrı manifest, yani ayrı kilit.
    with jsonstore.lock_for(_manifest_path(kind_dir)):
        _write_manifest(kind_dir, _read_manifest(kind_dir) + [record])
    return record


def list_assets(kind: str, assets_dir: str) -> list[dict]:
    return list(reversed(_read_manifest(_kind_dir(assets_dir, kind))))


def asset_path(kind: str, asset_id: str, assets_dir: str) -> str | None:
    """Var olan bir varlığın dosya yolunu döndürür; id geçersiz/bulunamazsa None."""
    kind_dir = _kind_dir(assets_dir, kind)
    if not _SAFE_ID.fullmatch(asset_id):
        return None
    path = os.path.join(kind_dir, f"{asset_id}.png")
    return path if os.path.isfile(path) else None


def migrate_legacy_uploads(assets_dir: str) -> int:
    """Ölü `uploads` türündeki varlıkları `logos`a taşır; taşınan sayısını döndürür.

    Açılışta koşuyor (`app._lifespan`), dizin yoksa hiçbir şey yapmıyor — yani
    yeni kurulumlarda maliyeti bir `isdir` çağrısı.

    SIRA BİLİNÇLİ: önce dosya taşınıyor (`os.replace`, aynı dosya sistemi
    içinde atomik), sonra manifest yazılıyor. Ters sıra, araya düşen bir
    çökmede manifest'i OLMAYAN bir dosyaya işaret eder bırakırdı — kullanıcı
    kütüphanede kırık bir karo görürdü. Bu sırada ise yarım kalmış bir koşu
    yalnız listelenmeyen bir dosya bırakıyor ve İKİNCİ koşu onu topluyor:
    kaynak dosya yok ama hedef dosya varsa kayıt yine yazılıyor.

    ÇAKIŞMA gerçek bir kayıp riski taşıdığı için ayrıca ele alınıyor: id hedef
    türde zaten varken kaynak dosya da HÂLÂ duruyorsa bu "göçmüş" değil
    çakışmış demektir (göçen kaydın kaynağı silinmiş olurdu). Aynı id ikinci
    kez yazılsaydı eski logo listede görünmez olurdu; onun yerine yeni bir id
    veriliyor.

    Kaynak dizin yalnız BOŞSA siliniyor: manifest'te kaydı olmayan (uygulamanın
    hiç görmediği) bir dosya kalmışsa `rmdir` düşer ve dizin yerinde kalır.
    Kullanıcının dosyasını sessizce silmektense okunmayan bir dizin bırakmak
    yeğdir.
    """
    kaynak = os.path.join(assets_dir, LEGACY_KIND)
    if not os.path.isdir(kaynak):
        return 0

    hedef = _kind_dir(assets_dir, LEGACY_TARGET)
    os.makedirs(hedef, exist_ok=True)
    tasinan = 0

    with jsonstore.lock_for(_manifest_path(hedef)):
        kayitlar = _read_manifest(hedef)
        idler = {r.get("id") for r in kayitlar}
        for kayit in _read_manifest(kaynak):
            asset_id = kayit.get("id")
            if not isinstance(asset_id, str) or not _SAFE_ID.fullmatch(asset_id):
                continue  # bozuk kayıt: dosyası zaten adreslenemez
            src = os.path.join(kaynak, f"{asset_id}.png")
            if asset_id in idler:
                if not os.path.exists(src):
                    continue  # göçmüş: yarım kalmış bir koşunun ikinci turu
                asset_id = uuid.uuid4().hex[:12]  # çakışma (yukarıdaki gerekçe)
            dst = os.path.join(hedef, f"{asset_id}.png")
            if os.path.exists(src):
                os.replace(src, dst)
            elif not os.path.exists(dst):
                continue  # ne kaynakta ne hedefte: kayıt zaten öksüz
            kayitlar.append({**kayit, "id": asset_id,
                             "filename": f"{asset_id}.png",
                             "kind": LEGACY_TARGET})
            idler.add(asset_id)
            tasinan += 1
        if tasinan:
            _write_manifest(hedef, kayitlar)

    manifest = _manifest_path(kaynak)
    if os.path.exists(manifest):
        os.remove(manifest)
    try:
        os.rmdir(kaynak)
    except OSError:
        pass  # manifest'siz dosya kalmış: kullanıcının verisi silinmez
    return tasinan


def delete_asset(kind: str, asset_id: str, assets_dir: str) -> bool:
    kind_dir = _kind_dir(assets_dir, kind)
    if not _SAFE_ID.fullmatch(asset_id):
        return False

    with jsonstore.lock_for(_manifest_path(kind_dir)):
        items = _read_manifest(kind_dir)
        remaining = [r for r in items if r.get("id") != asset_id]
        record_existed = len(remaining) != len(items)

        file_path = os.path.join(kind_dir, f"{asset_id}.png")
        file_existed = os.path.exists(file_path)
        if file_existed:
            os.remove(file_path)

        if record_existed:
            _write_manifest(kind_dir, remaining)

    return record_existed or file_existed
