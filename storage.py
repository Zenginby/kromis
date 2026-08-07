"""Üretilen görsellerin diske kaydı ve history.json yönetimi.

Atomik yazım ve "oku → değiştir → yaz" kilidi jsonstore.py'de paylaşılıyor:
manifest deposu olan beş dosya aynı iki mekaniği kullanıyor.
"""
from __future__ import annotations

import json
import contextlib
import os
import re
import uuid
from collections.abc import Iterable

import jsonstore

HISTORY_FILE = "history.json"

# Image ids are generated as uuid.uuid4().hex[:12] (see save()): bare lowercase
# hex tokens with no separators or dots. Reject anything else up front so a
# malicious/malformed id can never reach a filesystem path.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")


def _history_path(output_dir: str) -> str:
    return os.path.join(output_dir, HISTORY_FILE)


def _read_history(output_dir: str) -> list[dict]:
    path = _history_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path) as f:
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
    filename = f"{image_id}.png"
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

    `delete()` ile aynı sözleşme: dosya adı `{id}.png`, kaydı olmayan ama dosyası
    olan (veya tersi) id de silinmiş sayılır.
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
            file_path = os.path.join(output_dir, f"{image_id}.png")
            if os.path.exists(file_path):
                # `exists` ile `remove` arasında dosya kaybolabilir (aynı görseli
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

        file_path = os.path.join(output_dir, f"{image_id}.png")
        file_existed = os.path.exists(file_path)
        if file_existed:
            # delete_many ile aynı yarış: araya başka bir silme girebilir.
            with contextlib.suppress(FileNotFoundError):
                os.remove(file_path)

        if record_existed:
            _write_history(output_dir, remaining)

    return record_existed or file_existed
