# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Görsel klasörleri (koleksiyonlar) ve folders.json yönetimi.

Klasörler diskte gerçek dizin DEĞİL: görseller `output/` altında düz durur ve
klasör yalnızca kayıttaki bir etikettir (`folder_id`). Böylece `/output/{filename}`
URL'leri ile `parent_id` türev zincirleri klasör taşımalarından etkilenmez.

storage.py ile aynı desenler: bozuk JSON'a dayanıklı okuma, immutable-append,
`_SAFE_ID` guard'ı. Atomik yazım ve yazma kilidi jsonstore.py'de paylaşılıyor.
"""
from __future__ import annotations

import io
import json
import os
import re
import uuid
import zipfile

import i18n
import jsonstore
import storage

FOLDERS_FILE = "folders.json"


# storage._SAFE_ID ile aynı: uuid4().hex[:12] üretimiyle uyumlu bare hex token.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


# Kullanıcı metnini dosya/dizin/başlık adına indiren TEK süzgeç.
#
# ESKİ DESEN `[^\w\s-]` İDİ ve `\s` yüzünden CR/LF'yi KORUYORDU. Zararsız
# görünüyordu — ta ki aynı desenin ikinci kopyası `app.py`'nin ZIP indirme
# ucunda, klasör adını `Content-Disposition` DEĞERİNE koyana kadar. Ölçüldü:
# adı `kotu\r\nX-Injected: yes` olan bir klasörde başlık
# `attachment; filename="kotu\r\nX-Injected_yes...` olarak kuruluyor, yani
# kullanıcı metni yanıt başlıklarının arasına satır atabiliyor. Bugün bunu
# uvicorn reddediyor (`RuntimeError: Invalid HTTP header value`) — sonuç
# indirmenin çalışması değil, yakalanmamış bir ASGI hatası ve kopan bağlantı;
# BAŞKA bir ASGI sunucusunun altında ise yanıt bölme (response splitting).
# Savunma sunucunun sürümüne bırakılamaz, o yüzden süzgecin KENDİSİ kapatıyor.
#
# İKİ ADIM, sırası önemli: önce boşluk sayılan HER karakter (CR, LF, TAB, NBSP)
# tek düz boşluğa iniyor, sonra `\w`, boşluk ve tire dışındaki her şey düşüyor.
# Tersi sırada CR/LF önce silinip iki kelime birbirine yapışırdı.
_BOSLUK = re.compile(r"\s+")
_AD_DISI = re.compile(r"[^\w -]")


def safe_component(name: str, *, fallback: str = "klasor") -> str:
    r"""Kullanıcı adını TEK SATIRLIK, yol/başlık parçası olarak güvenli ada indirir.

    `.` ve `/` de düşüyor (`\w` dışındalar), yani ZIP girdisi `..` ya da mutlak
    yol taşıyamıyor — zip-slip kapısı bu fonksiyonun yan ürünü.

    Boşalan ad `fallback`e düşüyor: adı tümüyle noktalama olan bir klasör
    ("!!!") aksi halde adsız bir ZIP girdisi üretirdi.
    """
    duz = _BOSLUK.sub(" ", name or "")
    return _AD_DISI.sub("", duz).strip().replace(" ", "_") or fallback


def _folders_path(output_dir: str) -> str:
    return os.path.join(output_dir, FOLDERS_FILE)


def _read(output_dir: str) -> list[dict]:
    path = _folders_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan dosya: çökmek yerine boş kabul et
            # (storage._read_history ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write(output_dir: str, items: list[dict]) -> None:
    jsonstore.write_atomic(_folders_path(output_dir), items)


def create(name: str, output_dir: str, *, parent_id: str | None = None, now: str) -> dict:
    """`parent_id` None ise kök klasör, doluysa o klasörün altına açılır.

    Çağıran tarafın `parent_id`'yi `exists()` ile doğrulaması beklenir (app._check_folder).
    """
    os.makedirs(output_dir, exist_ok=True)
    folder_id = uuid.uuid4().hex[:12]
    record = {"id": folder_id, "name": name, "parent_id": parent_id, "created_at": now}
    with jsonstore.lock_for(_folders_path(output_dir)):   # oku→değiştir→yaz bölünmez
        _write(output_dir, _read(output_dir) + [record])  # immutable append
    return record


def list_folders(output_dir: str) -> list[dict]:
    """En yeni klasör başta (assets_store.list_assets ile aynı sıra)."""
    return list(reversed(_read(output_dir)))


def exists(folder_id: str, output_dir: str) -> bool:
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        return False
    return any(f.get("id") == folder_id for f in _read(output_dir))


def depth(folder_id: str, output_dir: str) -> int:
    """Kök klasör 1, onun altındaki 2… Klasör yoksa 0.

    `descendants` ile aynı duruş: yeniden ebeveynleme olmadığı için zincir
    döngü içermez, ama elle bozulmuş bir dosyada asılı kalmamak için ziyaret
    edilenler işaretlenir.
    """
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        return 0
    by_id = {f.get("id"): f for f in _read(output_dir) if f.get("id")}
    if folder_id not in by_id:
        return 0
    seen: set[str] = set()
    level = 0
    current: str | None = folder_id  # `parent_id` kökte None
    while current and current in by_id and current not in seen:
        seen.add(current)
        level += 1
        current = by_id[current].get("parent_id")
    return level


def descendants(folder_id: str, output_dir: str) -> list[str]:
    """Klasörün kendisi + tüm alt klasörlerinin id'leri (üstten alta).

    Klasör yoksa boş liste. Yeniden ebeveynleme olmadığı için `parent_id` zinciri
    döngü içermez; yine de ziyaret edilenler işaretlenerek bozuk bir dosyada
    sonsuz döngüye düşülmez.
    """
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        return []
    items = _read(output_dir)
    if not any(f.get("id") == folder_id for f in items):
        return []
    found = [folder_id]
    seen = {folder_id}
    queue = [folder_id]
    while queue:
        parent = queue.pop(0)
        for f in items:
            fid = f.get("id")
            if f.get("parent_id") == parent and fid and fid not in seen:
                seen.add(fid)
                found.append(fid)
                queue.append(fid)
    return found


def delete_tree(folder_id: str, output_dir: str) -> list[str]:
    """Klasörü ve tüm alt klasörlerini siler; silinen id'leri döndürür (yoksa boş liste).

    İçindeki GÖRSELLER silinmez — çağıran taraf `storage.unfile_folders` ile onları
    klasörsüz hale getirir.
    """
    with jsonstore.lock_for(_folders_path(output_dir)):
        doomed = descendants(folder_id, output_dir)   # o da okuyor: kilit içinde
        if not doomed:
            return []
        targets = set(doomed)
        _write(output_dir, [f for f in _read(output_dir) if f.get("id") not in targets])
    return doomed


def rename(folder_id: str, new_name: str, output_dir: str) -> dict | None:
    """Klasör adını günceller. Klasör yoksa veya adı boşsa None döner."""
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        return None
    name = new_name.strip()
    if not name:
        return None
    with jsonstore.lock_for(_folders_path(output_dir)):
        items = _read(output_dir)
        target = None
        for f in items:
            if f.get("id") == folder_id:
                f["name"] = name
                target = f
                break
        if target:
            _write(output_dir, items)
            return target
    return None


def export_zip(folder_id: str, output_dir: str) -> tuple[bytes, str]:
    """Klasörü ve tüm alt ağacını görselleriyle birlikte ZIP arşivi olarak üretir."""
    if not folder_id or not _SAFE_ID.fullmatch(folder_id):
        raise ValueError(i18n.t("err.bad_folder_id"))

    all_folders = _read(output_dir)
    folder_map = {f["id"]: f for f in all_folders if f.get("id")}
    root_folder = folder_map.get(folder_id)
    if not root_folder:
        raise ValueError(i18n.t("err.folder_missing"))

    root_name = root_folder.get("name", "klasor").strip()


    def get_rel_path(fid: str) -> str:
        chain = []
        curr: str | None = fid  # `parent_id` kökte None
        seen = set()
        while curr and curr in folder_map and curr not in seen:
            seen.add(curr)
            node = folder_map[curr]
            chain.append(node.get("name", "klasor").strip())
            if curr == folder_id:
                break
            curr = node.get("parent_id")
        chain.reverse()
        return "/".join(safe_component(p) for p in chain)


    tree_ids = set(descendants(folder_id, output_dir))
    tree_ids.add(folder_id)

    history = storage.list_history(output_dir)
    matching_records = [rec for rec in history if rec.get("folder_id") in tree_ids]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in tree_ids:
            rel = get_rel_path(fid)
            if rel:
                zf.writestr(f"{rel}/", b"")

        for rec in matching_records:
            fn = rec.get("filename")
            if not fn:
                continue
            src_path = os.path.join(output_dir, fn)
            if os.path.exists(src_path):
                f_id = rec.get("folder_id")
                rel_dir = get_rel_path(f_id) if f_id in tree_ids else get_rel_path(folder_id)
                zip_path = f"{rel_dir}/{fn}"
                zf.write(src_path, arcname=zip_path)

    return buf.getvalue(), root_name


