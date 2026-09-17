# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kayıtlı oturumlar (konuşma + üretilen görseller) ve chats.json yönetimi.

Kararın üç aşaması — hiçbiri silinmedi, her biri ötekini daralttı ya da açtı:

**v1.13, "karar 4": sohbet diske HİÇ yazılmıyordu.** Gerekçe: modelden dönen her
yanıtı sessizce diske almak ile kullanıcının "bu sohbeti sakla" demesi aynı şey
değil.

**v1.15: karar iptal edilmedi, KAPSAMI daraldı.** Sohbetler saklanabilir oldu ama
yazan tek yol kullanıcının kendi başlattığı `/api/chats`; tamamlama rotası
(`POST /api/chat`) hâlâ hiçbir şey yazmıyordu.

**2026-08-06, karar D1: otomatik kayıt AÇILDI.** Gerekçe, v1.13'ün gerekçesini
çürüten yeni bir gereksinim: birleşik oturum geçmişi ("konuşmalar ve üretilen
görseller aynı yerde") ancak otomatik yazımla dolar — kullanıcı her turda "sakla"
demek zorunda kalırsa geçmiş boş kalır. Üç güvence bunu v1.13'ün korktuğu şeyden
ayırıyor: (a) her şey yerelde, `output_dir` ve izinler değişmedi; (b) oturum
menüsünde tek tıkla sil ve tümünü sil (`delete`, `delete_all`); (c) `prefs.py`'de
"oturumları otomatik kaydet" anahtarı — kapatınca v1.15 davranışına dönülüyor.

**`POST /api/chat` yine hiçbir şey yazmıyor** ve bu tesadüf değil: oturumu
`/api/chats`'e yazan taraf istemci. Oturum yalnız konuşmadan oluşmuyor — Görsel
modunda üretilen sonuç kayıtları da dökümün parçası ve onlar tamamlama rotasına
hiç uğramıyor. Kalıcılık oraya konsaydı sohbetsiz bir oturum hiç
kaydedilemezdi (bkz. tests/test_chats_route.py'deki mekanik iddia).

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
kırpma, kullanıcının "kaydedildi" beklentisini bozardı. Otomatik kayıt bu sayıyı
hızlandırıyor ama kararı değiştirmiyor: sessiz kırpma yerine görünür bir
"tümünü sil" var (güvence b).
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
# `cover_image_id` (v2.0) o kuralın istisnası değil, uygulaması: liste küçük
# resmi için gövdenin tamamı değil ondan TÜRETİLEN 12 karakter gidiyor.
_SUMMARY_FIELDS = ("id", "title", "created_at", "updated_at", "cover_image_id")

# Dökümdeki sonuç kaydının rolü. `models.RESULT_ROLE` ile aynı dize olmak
# zorunda; import EDİLMİYOR çünkü models pydantic'e bağlı ve bu depo (diğer
# dördü gibi) bilerek bağımsız — kayma tests/test_chat_store.py'de ölçülüyor.
RESULT_ROLE = "result"


def _chats_path(output_dir: str) -> str:
    return os.path.join(output_dir, CHATS_FILE)


def valid_id(chat_id: str | None) -> bool:
    """`_SAFE_ID` guard'ı — yol parçası taşıyan bir id dosyaya hiç ulaşmasın.

    Ayrı bir fonksiyon çünkü `/api/generate` de bunu soruyor: bir görsel kaydına
    yazılacak `session_id` aynı kapıdan geçmek zorunda (bkz. app._check_session).
    """
    if not chat_id:  # iki adım: `bool(x) and …` mypy için daraltmıyor (storage.valid_id)
        return False
    return _SAFE_ID.fullmatch(chat_id) is not None


def cover_from(messages: list[dict]) -> str | None:
    """Dökümdeki İLK sonuç kaydının ilk görseli; sonuç yoksa None.

    Kapak PARAMETRE DEĞİL, türetiliyor. İstemciden alınsaydı oturumun dökümünde
    hiç bulunmayan bir görseli kapak yapabilirdi: panelde görünen küçük resim ile
    açılan oturumun içeriği ayrışırdı. Türetme tek kaynak bırakıyor — kapak,
    dökümün kendisi.

    SON değil İLK: son sonuçtan alınsaydı liste küçük resmi her üretimde
    değişirdi ve kullanıcı oturumu "o kırmızı afişli olan" diye tanıyorsa o iz
    kaybolurdu.

    Bayat/elle düzenlenmiş kayda dayanıklı: `image_ids`'i olmayan bir sonuç
    kaydı çökmeye değil, sıradakine bakmaya yol açar.
    """
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != RESULT_ROLE:
            continue
        image_ids = m.get("image_ids")
        if isinstance(image_ids, list) and image_ids:
            return image_ids[0]
    return None


def _with_cover(record: dict, messages: list[dict]) -> dict:
    """Kaydı kapak alanı dökümle TUTARLI hale getirilmiş kopyasıyla değiştirir.

    Kapak yoksa alan hiç yazılmaz (koşullu yazım geleneği) ve bayat bir alan
    varsa DÜŞER: kapak dökümün dışını gösteremez.
    """
    cover = cover_from(messages)
    rest = {k: v for k, v in record.items() if k != "cover_image_id"}
    return {**rest, **({"cover_image_id": cover} if cover else {})}


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
    """Yeni sohbet kaydı.

    `messages` iki biçim taşıyabilir (v2.0, birleşik döküm):
    `{"role": "user"|"assistant", "content": ...}` ve
    `{"role": "result", "image_ids": [...], "params": {...}}`. Doğrulama BURADA
    değil `models.ChatMessage`'ta; depo rolleri yalnızca kapak için okuyor.
    """
    os.makedirs(output_dir, exist_ok=True)
    record = _with_cover({
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "messages": messages,
        "created_at": now,
        "updated_at": now,
    }, messages)
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
    if not valid_id(chat_id):
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
    if not valid_id(chat_id):
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
        if messages is not None:
            # Kapak dökümden türetiliyor, yani gövde değiştiyse yeniden hesaplanır.
            # Yeniden adlandırmada gövdeye dokunulmadığı için kapak da korunur.
            record = _with_cover(record, messages)
        _write(output_dir, items[:index] + [record] + items[index + 1:])
    return record


def delete_all(output_dir: str) -> int:
    """Tüm oturumları siler; silinen sayıyı döndürür (karar D1'in güvence b'si).

    Dosya YOKSA yaratılmıyor: boş bir depoda "tümünü sil", var olmayan bir dosyayı
    var etmemeli. Tek tek silmenin tek çıkış yolu olması otomatik kayıtla birlikte
    güvenceyi lafta bırakırdı — otomatik yazım geçmişi kullanıcının istemediği
    kadar büyütebiliyor.
    """
    with jsonstore.lock_for(_chats_path(output_dir)):
        items = _read(output_dir)
        if items:
            _write(output_dir, [])
    return len(items)


def delete(chat_id: str, output_dir: str) -> bool:
    """Sohbeti siler. Bulunamadıysa/geçersiz id ise False."""
    if not valid_id(chat_id):
        return False
    with jsonstore.lock_for(_chats_path(output_dir)):
        items = _read(output_dir)
        kept = [c for c in items if c.get("id") != chat_id]
        if len(kept) == len(items):
            return False
        _write(output_dir, kept)
    return True
