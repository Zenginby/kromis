"""Kayıtlı Prompt Yönetmeni sohbetleri ve chats.json yönetimi.

v1.13'ün "karar 4"ü sohbeti diske hiç yazmıyordu; v1.15 o kararı İPTAL ETMİYOR,
KAPSAMINI DARALTIYOR: tamamlama rotası (`POST /api/chat`) hâlâ hiçbir şey
yazmıyor — yazan tek yol kullanıcının kendi başlattığı `/api/chats`. Ayrım
önemli: modelden dönen her yanıtı sessizce diske almak ile kullanıcının
"bu sohbeti sakla" demesi aynı şey değil.

Kalıcılık İSTEMCİDE (localStorage) tutulamıyor, ölçülen bir sebeple:
`desktop.py` pencereyi `webview.start()` ile argümansız açıyor ve pywebview
6.2.1'de `private_mode=True` varsayılan — dokümantasyonu net, private mode'da
"cookies and local storage are not preserved". Paketlenmiş `.app`'te geçmiş her
açılışta sessizce silinirdi.

storage.py / folders.py / palette_store.py ile aynı desenler: bozuk JSON'a
dayanıklı okuma, immutable append, `_SAFE_ID` guard'ı. Atomik yazım ve yazma
kilidi beş depoda PAYLAŞILIYOR (bkz. jsonstore.py) — desen beş kez kopyalanmış
olduğu için eksikleri de beş yerde birden düzeltilmek zorundaydı.

Sohbet SAYISINA üst sınır konmadı (bilinçli): tek kayıt models.py'deki
MAX_CHAT_TOTAL_CHARS ile zaten sınırlı ve sessizce eski sohbet düşüren bir
kırpma, kullanıcının "kaydedildi" beklentisini bozardı.
"""
from __future__ import annotations

import json
import os
import re
import uuid

import jsonstore

CHATS_FILE = "chats.json"

# storage._SAFE_ID / folders._SAFE_ID / palette_store._SAFE_ID ile aynı:
# uuid4().hex[:12] uyumlu bare hex token.
_SAFE_ID = re.compile(r"[0-9a-f]{8,32}")

# Kenar panelinin gördüğü alanlar. `messages` BİLEREK yok: otuz sohbetin
# gövdesini her açılışta göndermek boşuna trafik, gövde `get` ile geliyor.
_SUMMARY_FIELDS = ("id", "title", "created_at", "updated_at")


def _chats_path(output_dir: str) -> str:
    return os.path.join(output_dir, CHATS_FILE)


def _read(output_dir: str) -> list[dict]:
    path = _chats_path(output_dir)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Bozuk/okunamayan dosya: çökmek yerine boş kabul et
            # (storage._read_history, folders._read ile aynı davranış).
            return []
    if not isinstance(data, list):
        return []
    return data


def _write(output_dir: str, items: list[dict]) -> None:
    jsonstore.write_atomic(_chats_path(output_dir), items)


def create(title: str, messages: list[dict], output_dir: str, *, now: str) -> dict:
    """Yeni sohbet kaydı. `messages`: `[{"role": ..., "content": ...}, ...]`."""
    os.makedirs(output_dir, exist_ok=True)
    record = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    }
    # Kilit "oku → değiştir → yaz"ın TAMAMINI sarıyor (bkz. jsonstore): tur sonu
    # otomatik kaydı ile kullanıcının yeniden adlandırması gerçekten paralel
    # çalışabiliyor ve araya girilse kaybeden yazım sessizce düşerdi.
    with jsonstore.lock_for(_chats_path(output_dir)):
        _write(output_dir, _read(output_dir) + [record])  # immutable append
    return record


def list_chats(output_dir: str) -> list[dict]:
    """Özetler, EN SON GÜNCELLENEN başta.

    Dosya sırası oluşturma sırası: `update` kaydı yerinde değiştiriyor, hiç
    taşımıyor. Sıra dosyadan okunsaydı panel kendi kendisiyle çelişirdi — bugün
    devam edilen üç haftalık bir sohbet damgasında "14:32" yazıp, haftalardır
    dokunulmamış ama daha yeni oluşturulmuş sohbetlerin ALTINDA kalırdı.

    Damga ISO 8601 (`app._now`), yani sözlük sırası = zaman sırası; ayrı bir
    tarih ayrıştırma gerekmiyor. Eşitlikte dosya sırası ters çevriliyor (aynı
    saniyede oluşturulan iki kayıtta yeni olan başta kalsın, folders.list_folders
    geleneği), damgası eksik bayat bir kayıt ise çökmek yerine sona düşüyor.
    """
    ordered = sorted(enumerate(_read(output_dir)),
                     key=lambda pair: (str(pair[1].get("updated_at") or ""), pair[0]),
                     reverse=True)
    return [
        {**{k: c.get(k) for k in _SUMMARY_FIELDS},
         "message_count": len(c.get("messages") or [])}
        for _, c in ordered
    ]


def get(chat_id: str, output_dir: str) -> dict | None:
    """Tam kayıt (gövdesiyle). Yok ya da geçersiz id ise None."""
    if not chat_id or not _SAFE_ID.fullmatch(chat_id):
        return None
    for c in _read(output_dir):
        if c.get("id") == chat_id:
            return c
    return None


def update(chat_id: str, output_dir: str, *, messages: list[dict] | None = None,
           title: str | None = None, now: str) -> dict | None:
    """Gövdeyi ve/veya başlığı değiştirir; yeni kaydı döndürür (yoksa None).

    İkisi de verilmediyse dosyaya DOKUNULMAZ: boş bir güncelleme `updated_at`'i
    öne alırdı ve panel sıralaması onu izlediği için (bkz. `list_chats`) sohbet
    listenin başına atlardı — kullanıcının yapmadığı bir iş.
    """
    if not chat_id or not _SAFE_ID.fullmatch(chat_id):
        return None
    with jsonstore.lock_for(_chats_path(output_dir)):
        items = _read(output_dir)
        index = next((i for i, c in enumerate(items) if c.get("id") == chat_id), None)
        if index is None:
            return None
        if messages is None and title is None:
            return items[index]

        changes: dict = {"updated_at": now}
        if messages is not None:
            changes["messages"] = messages
        if title is not None:
            changes["title"] = title
        record = {**items[index], **changes}      # immutable: kopya üretilir
        _write(output_dir, items[:index] + [record] + items[index + 1:])
    return record


def delete(chat_id: str, output_dir: str) -> bool:
    """Sohbeti siler. Bulunamadıysa/geçersiz id ise False."""
    if not chat_id or not _SAFE_ID.fullmatch(chat_id):
        return False
    with jsonstore.lock_for(_chats_path(output_dir)):
        items = _read(output_dir)
        kept = [c for c in items if c.get("id") != chat_id]
        if len(kept) == len(items):
            return False
        _write(output_dir, kept)
    return True
