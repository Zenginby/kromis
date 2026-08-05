"""Azure sohbet istemcisi (Prompt Yönetmeni). `azure_client.py`'nin ikizi.

Aynı duruşu paylaşıyor: ham `httpx`, fonksiyon içinde lazy import, kendi hata
sınıfı, kullanıcıya gösterilebilir Türkçe mesajlar. Bir SDK eklenmiyor —
`requirements.txt` değişmiyor, dolayısıyla `gpt-image-studio.spec`'in
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
import models

# Okuma zaman aşımı. ~13,6 bin karakter sistem talimatı + akıl yürüten dağıtım
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
        return "Azure yetkilendirme hatası (401): API key geçersiz veya süresi dolmuş."
    if status_code == 404:
        # Bu uçta EN SIK hata: Ayarlar'a yazılan ad ile Foundry'deki dağıtım adı
        # ayrışması. Genel "istek başarısız" metni kullanıcıyı hiçbir yere
        # götürmezdi; 404 burada tek bir eyleme işaret ediyor.
        return ("Sohbet dağıtımı bulunamadı (404): Ayarlar'daki dağıtım adını "
                "Azure AI Foundry'deki adla karşılaştır.")
    if status_code == 429:
        return "İstek limiti aşıldı (429): biraz bekleyip tekrar deneyin."
    if status_code == 400 and "content" in detail.lower():
        return "İçerik politikası reddi: mesaj Azure tarafından engellendi."
    return f"Sohbet isteği başarısız (HTTP {status_code})." + (f" {detail}" if detail else "")


def load_credentials(env_path: str | None = None) -> tuple[str, str, str]:
    """(key, base_url, deployment). Sohbet key/url'si yoksa GÖRSEL olanlara düşer."""
    key, base_url, deployment = ac.resolve_chat_credentials(env_path)
    if not key or not base_url:
        raise ChatError("Azure kimlik bilgileri eksik: önce Ayarlar'dan endpoint ve "
                        "API key'i kaydet.")
    if not deployment:
        raise ChatError("Sohbet dağıtımı tanımlı değil: Ayarlar'dan Prompt Yönetmeni "
                        "dağıtım adını gir (ör. gpt-5.6-luna).")
    return key, base_url, deployment


def build_payload(messages: list[dict], deployment: str, instructions: str) -> dict:
    """MİNİMAL ve savunmacı: yalnızca `model` + `messages`.

    `temperature` / `top_p` / `max_tokens` BİLEREK YOK. GPT-5 sınıfı akıl yürüten
    dağıtımlar bunları 400 ile reddedebiliyor (`max_tokens` yerine
    `max_completion_tokens` istiyorlar) ve hiçbiri gerekli değil: persona'nın
    tamamı sistem talimatında yaşıyor. Yeni bir alan eklenirse CANLI doğrulanmalı
    (tests/test_chat_client.py'deki tripwire bunu zorluyor).

    Sistem mesajını SUNUCU koyuyor; istemciden gelen listede `role: "system"`
    kabul edilmiyor (bkz. models.ChatMessage).
    """
    return {
        "model": deployment,  # DAĞITIM adı, model ailesi adı DEĞİL
        "messages": [{"role": "system", "content": instructions}, *messages],
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
        raise ChatError("Sohbet yanıtı boş döndü (choices yok). Tekrar deneyin.")
    choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = str(choice.get("finish_reason") or "")
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ChatError("Sohbet yanıtı boş içerik döndürdü"
                        + (f" (finish_reason: {finish_reason})" if finish_reason else "")
                        + ". Mesajı kısaltıp tekrar deneyin.")
    # AŞIRI UZUN yanıt da burada, ayrıştırıldığı yerde patlar. Geçirilse ekrana
    # çizilirdi ama `models.ChatMessage`'a sığmazdı: bir sonraki tur ve kaydetme
    # pydantic'in İNGİLİZCE 422'siyle geri döner, sohbet sessizce kilitlenirdi.
    # Uzunluğu biz seçemiyoruz — `build_payload` bilerek `max_tokens` göndermiyor.
    if len(content) > models.MAX_CHAT_REPLY_CHARS:
        raise ChatError(
            f"Yönetmenin yanıtı beklenmedik biçimde uzun geldi ({len(content)} karakter, "
            f"sınır {models.MAX_CHAT_REPLY_CHARS}). Brief'i kısaltıp tekrar deneyin.")
    return content, finish_reason


def complete(messages: list[dict], *, client=None, credentials=None,
             instructions: str | None = None) -> dict:
    """Tek turda tamamlama. `{"content": str, "finish_reason": str}` döndürür."""
    key, base_url, deployment = credentials if credentials is not None else load_credentials()
    if instructions is None:
        try:
            instructions = chat_prompt.load_instructions()
        except ValueError as e:
            raise ChatError(f"Prompt Yönetmeni talimatı yüklenemedi: {e}")

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
