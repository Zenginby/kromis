# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Azure sohbet istemcisi (Prompt Yönetmeni). `azure_client.py`'nin ikizi.

Aynı duruşu paylaşıyor: ham `httpx`, fonksiyon içinde lazy import, kendi hata
sınıfı, kullanıcıya gösterilebilir Türkçe mesajlar. Bir SDK eklenmiyor —
`requirements.txt` değişmiyor, dolayısıyla `kromis.spec`'in
`hiddenimports`'u da değişmiyor.

STREAMING YOK. Yönetmenin çıktısı zaten ancak tamamlanınca (PROMPT + JSON
blokları) işe yarıyor; ayrıca depoda hiç SSE kodu yok. Yükseltme gerekirse yol
açık: Starlette'in `StreamingResponse`'u SENKRON generator kabul ediyor
(`iterate_in_threadpool` ile sarıyor), yani `httpx.Client.stream` düz bir `def`
içinde asyncio'suz çalışır ve arayüzün ayrıştırma katmanına dokunulmaz.

Kimlik çözümü BİLEREK burada değil `azure_client.resolve_chat_credentials`'ta:
`GET /api/settings`'in arayüzde açtığı kapı ile isteğin gerçekten kullandığı
değerler ayrışırsa arayüz sohbeti açar, ilk mesaj 502 döner ve sebebi görünmez.
"""
from __future__ import annotations

import azure_client as ac
import chat_prompt
# Yanıt sınırı `models`'ta yaşıyor çünkü ORASI onu zorunlu kılan yer
# (`ChatMessage.content`); ikinci bir sabit iki sayının ayrışmasına davetiye
# olurdu. Döngü yok: `models` yalnız `azure_client` ve `palette`'e bakıyor.
import i18n
import models

# Okuma zaman aşımı. ~16,5 bin karakter sistem talimatı + akıl yürüten dağıtım
# için bol başlık payı: ÖLÇÜLEN turlar 4,9 s ve 9,3 s (2026-08-04).
#
# ⚠️ Bu değer bir zamanlar "görsel üretiminden UZUN olmalı" diye çivilenmişti;
# ölçüm bunu çürüttü — yavaş olan taraf görsel üretimi ve süresi adetle büyüyor
# (bkz. azure_client.read_timeout_for). Sohbet tek yanıt döndürüyor, ölçekleyecek
# bir adet yok; o yüzden burada tek sabit yeterli.
REQUEST_TIMEOUT = 180.0


class ChatError(Exception):
    """Kullanıcıya gösterilebilir sohbet hatası (Türkçe)."""


def map_error(status_code: int, body: dict | None) -> str:
    detail = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            detail = str(err.get("message", ""))
        elif isinstance(err, str):
            detail = err
    if status_code == 401:
        return i18n.t("err.azure_401")
    if status_code == 404:
        # Bu uçta EN SIK hata: Ayarlar'a yazılan ad ile Foundry'deki dağıtım adı
        # ayrışması. Genel "istek başarısız" metni kullanıcıyı hiçbir yere
        # götürmezdi; 404 burada tek bir eyleme işaret ediyor.
        return i18n.t("err.chat_deployment_404")
    if status_code == 429:
        return i18n.t("err.rate_limited")
    if status_code == 400 and "content" in detail.lower():
        return i18n.t("err.chat_content_policy")
    return i18n.t("err.chat_failed", None, durum=status_code) + (
        f" {detail}" if detail else "")


def load_credentials(env_path: str | None = None) -> tuple[str, str, str]:
    """(key, base_url, deployment). Sohbet key/url'si yoksa GÖRSEL olanlara düşer."""
    key, base_url, deployment = ac.resolve_chat_credentials(env_path)
    if not key or not base_url:
        raise ChatError(i18n.t("err.azure_credentials_missing"))
    if not deployment:
        raise ChatError(i18n.t("err.chat_deployment_missing"))
    return key, base_url, deployment


def build_payload(messages: list[dict], deployment: str, instructions: str) -> dict:
    """MİNİMAL ve savunmacı: yalnızca `model` + `messages`.

    `temperature` / `top_p` / `max_tokens` BİLEREK YOK. GPT-5 sınıfı akıl yürüten
    dağıtımlar bunları 400 ile reddedebiliyor (`max_tokens` yerine
    `max_completion_tokens` istiyorlar) ve hiçbiri gerekli değil: persona'nın
    tamamı sistem talimatında yaşıyor. Yeni bir alan eklenirse CANLI doğrulanmalı
    (tests/test_chat_client.py'deki tripwire bunu zorluyor).

    Minimallik v1.16'da MESAJ İÇİNE de indi: her mesaj sözlüğü
    `models.WIRE_MESSAGE_FIELDS`'e süzülüyor. Sebebi somut — `ChatMessage.display`
    yalnızca arayüzün çizdiği etiket ve Azure onu bilmiyor; süzgeç olmasa tel
    üzerine çıkar ve istek 400 dönerdi. Süzgeç BURADA çünkü Azure gövdesini
    gerçekten kuran yer burası: `complete()`'in bugünkü tek çağıranı rota, ama
    yarınki çağıran da korunmuş oluyor. ALLOWLIST olduğu için bundan sonra
    eklenen her arayüz alanı da varsayılan olarak dışarıda kalır.

    Sistem mesajını SUNUCU koyuyor; istemciden gelen listede `role: "system"`
    kabul edilmiyor (bkz. models.ChatMessage).

    v2.0'da süzgeç ROL düzeyine de çıktı (`models.WIRE_CHAT_ROLES`): birleşik
    döküm `result` kayıtlarını konuşmanın İÇİNDE tutuyor ve her tur tel üzerinden
    geri geliyor. Alan allowlist'i tek başına yetmez — süzülmüş bir sonuç kaydı
    geride `{"role": "result"}` bırakır, Azure o rolü bilmez ve 400 döner: bir
    kez üretim yapmış oturum bir daha hiç konuşamaz.

    ROTA ARTIK BU SÜZGECE GÜVENMİYOR: `models.wire_messages` sonuç kayıtlarını
    daha üstte kısa bir NOTA çeviriyor, yani buraya `result` rolü normalde hiç
    ulaşmıyor. Süzgeç yine de kaldırılmadı ve sebebi bu fonksiyonun ne olduğu:
    telin gerçek sınırı burası. Ham dict geçiren başka bir çağıran, ya da
    dökümde açılıp çevirmene eklenmesi unutulan SONRAKİ bir rol, buradan
    sessizce geçip 400'e dönüşmemeli.
    """
    return {
        "model": deployment,  # DAĞITIM adı, model ailesi adı DEĞİL
        "messages": [
            {"role": "system", "content": instructions},
            *({k: m[k] for k in models.WIRE_MESSAGE_FIELDS if k in m}
              for m in messages if m.get("role") in models.WIRE_CHAT_ROLES),
        ],
    }


def extract_content(response_json: dict) -> tuple[str, str]:
    """(content, finish_reason). Boş içerik GÜRÜLTÜLÜ hata olur, boş baloncuk DEĞİL.

    `IndexError`/`KeyError`'a düşmek 500 üretir ve kullanıcı Türkçe hata görmez;
    sessizce boş baloncuk basmak daha da kötü — "cevap vermedi" denir, iz kalmaz.

    `finish_reason` mesaja giriyor: `length` + boş içerik, dağıtımın
    `max_completion_tokens` istediğinin tek işareti ve tek turda teşhis
    edilebilmeli.
    """
    choices = response_json.get("choices") if isinstance(response_json, dict) else None
    if not isinstance(choices, list) or not choices:
        raise ChatError(i18n.t("err.chat_empty"))
    choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = str(choice.get("finish_reason") or "")
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ChatError(i18n.t("err.chat_empty_content")
                                + (f" (finish_reason: {finish_reason})" if finish_reason else "")
                                + " " + i18n.t("err.shorten_and_retry"))
    # AŞIRI UZUN yanıt da burada, ayrıştırıldığı yerde patlar. Geçirilse ekrana
    # çizilirdi ama `models.ChatMessage`'a sığmazdı: bir sonraki tur ve kaydetme
    # pydantic'in İNGİLİZCE 422'siyle geri döner, sohbet sessizce kilitlenirdi.
    # Uzunluğu biz seçemiyoruz — `build_payload` bilerek `max_tokens` göndermiyor.
    if len(content) > models.MAX_CHAT_REPLY_CHARS:
        raise ChatError(
            i18n.t("err.chat_reply_too_long", None, uzunluk=len(content),
                           sinir=models.MAX_CHAT_REPLY_CHARS))
    return content, finish_reason


def complete(messages: list[dict], *, client=None, credentials=None,
             instructions: str | None = None) -> dict:
    """Tek turda tamamlama. `{"content": str, "finish_reason": str}` döndürür."""
    key, base_url, deployment = credentials if credentials is not None else load_credentials()
    if instructions is None:
        try:
            instructions = chat_prompt.load_instructions()
        except ValueError as e:
            raise ChatError(i18n.t("err.persona_load_failed", None, hata=e))

    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = build_payload(messages, deployment, instructions)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    owns_client = client is None
    import httpx   # bkz. azure_client.generate(): hata türleri için de gerekli
    if owns_client:
        client = httpx.Client()
    try:
        resp = client.post(endpoint, headers=headers, json=payload,
                           timeout=ac.request_timeout(REQUEST_TIMEOUT))
    except httpx.TransportError as exc:
        # Mesaj metni azure_client'ta PAYLAŞILIYOR: iki istemcinin ağ hatası
        # aynı hata, iki ayrı Türkçe metne ayrışmaları anlamsız.
        raise ChatError(ac.transport_error_message(exc, REQUEST_TIMEOUT)) from exc
    finally:
        if owns_client:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise ChatError(map_error(resp.status_code, body))

    content, finish_reason = extract_content(resp.json())
    return {"content": content, "finish_reason": finish_reason}
