# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""OpenAI-uyumlu SOHBET ucu — `chat_client.py`'nin BİLİNÇLİ ikizi.

`openai_client.py`'nin `azure_client.py`'ye duruşunun aynısı ve aynı
gerekçeyle. İki dosya AYNI teli konuşuyor —

    POST {base}{endpoint_path}      → varsayılan `/chat/completions`
    {"model": …, "messages": [...]}
    → {"choices": [{"message": {"content": …}, "finish_reason": …}]}

— ama `chat_client`'ı parameterize edip yeniden kullanmak ÜÇ somut bedeli olurdu:

  1. `chat_client.build_payload`'ın MİNİMAL gövdesi
     tests/test_chat_client.py'de tripwire ile donmuş; oraya bir dal eklemek
     o mandalı gevşetirdi.
  2. Kimlik çözümü Azure'da BELGELENMİŞ bir düşme taşıyor (sohbetin kendi
     anahtarı yoksa görselin kimliğine düşüyor) ve OpenAI/Gemini'de o düşmenin
     karşılığı yok — `credstore.resolve` tek bir kimliği çözüyor.
  3. O dosyanın hata metinleri Azure'a özgü: 404 "Ayarlar'daki dağıtım adını
     Azure AI Foundry'deki adla karşılaştır" diyor. OpenAI'de girilecek bir
     dağıtım adı YOK — o metni göstermek kullanıcıyı olmayan bir forma
     yönlendirir. Buradaki 404 modelin ADINI söylüyor, çünkü orada 404'ün
     tek anlamı "bu model kalkmış" (DALL·E 3'ün katalogdan çıkarılma
     gerekçesinin aynısı).

PAYLAŞILAN kısım küçük ve tam olarak tel ŞEKLİ: `build_payload` ve
`extract_content` `chat_client`'tan AYNEN çağrılıyor. Kopyalanmadılar çünkü
ikisi de yalnız şekil biliyor ve `extract_content`'in üç kapısı (boş choices,
boş içerik + finish_reason, `MAX_CHAT_REPLY_CHARS` tavanı) sağlayıcıdan
bağımsız olgular. `openai_client.py`'nin sözü burada da geçerli:
"ŞEKİL paylaşılıyor, METİN paylaşılmıyor."

İKİ SAĞLAYICI, TEK DOSYA: `openai` ve `gemini` girdilerinin ikisi de buradan
geçiyor. Gemini'nin farkı YALNIZCA `endpoint_path` (`/v1beta/openai/…`) ve
hata metinlerindeki ad; ikisi de kataloğun kendisinden okunuyor, yani üçüncü
bir OpenAI-uyumlu sağlayıcı (LM Studio, Groq, birçok vekil) kataloğa tek girdi
olarak eklenebiliyor ve bu dosyaya HİÇ dokunulmuyor.

HATA TÜRÜ PAYLAŞILIYOR (`cc.ChatError`): `app.py` sohbet çağrısını
`except cc.ChatError` ile süzüyor. İkinci bir tür açmak o süzgeci ikiye
bölerdi ve sarmalanmayan bir hata ham 500 olurdu — arayüz gövdeyi JSON olarak
ayrıştıramaz ve kullanıcı beklemenin sonunda yalnızca "Hata (500)" görür.
Bu, `azure_client.ImageError`'ın tek-tür/iki-ad kararının aynı gerekçesi.
"""
from __future__ import annotations

import azure_client as ac
import catalog
import chat_client as cc
import chat_prompt
import credstore
import providers

# Zaman aşımı ve ağ-hatası metni `chat_client` ile PAYLAŞILIYOR
# (`cc.REQUEST_TIMEOUT`, `ac.transport_error_message`): ağ davranışı
# sağlayıcıya göre değişmiyor ve iki ayrı sayı tutmak, birini ayarlayıp
# diğerini unutmanın kapısı olurdu — `openai_client.py`'nin başındaki notun
# aynısı.


def _label(m: catalog.ChatModel) -> str:
    """Hata metinlerinde geçen sağlayıcı adı — KATALOGDAN, literal DEĞİL.

    `Credential.label` zaten Ayarlar panelindeki başlık, yani kullanıcı hatada
    okuduğu adı formda birebir buluyor. İkinci bir literal tablo yazmak, bir
    sağlayıcının adını değiştirince hatanın eski adı söylemesi demekti.
    """
    cred = catalog.credential(m.credential)
    return cred.label if cred else m.provider


def map_error(status_code: int, body: dict | list | None, *, label: str,
              wire_model: str) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. `chat_client.map_error`'ın ikizi.

    Gövde şeklini `providers.detail_of` çözüyor (dört sağlayıcı da
    `{"error": {"message": …}}` kullanıyor); ayrışan taraf metinler.

    404 BURADA MODELİN ADINI söylüyor: bu uçta 404'ün tek anlamı "istenen model
    yok" ve o durumun tek çözümü Ayarlar'dan başka bir model seçmek. Azure'ın
    404'ü ise dağıtım adı ayrışmasını anlatıyor — iki metnin birleşmesi
    kullanıcıyı yanlış yere yönlendirirdi.

    GEÇERSİZ ANAHTAR BU UÇTA 401 DEĞİL 400 OLABİLİR ve bu ölçülmüş bir olgu:
    Gemini'nin OpenAI-uyumlu ucu (`/v1beta/openai/chat/completions`) geçersiz
    anahtara `[{"error": {"code": 400, "status": "INVALID_ARGUMENT",
    "message": "API key not valid…"}}]` döndürüyor — canlı çağrıyla
    doğrulandı. Anahtar metni yalnız 401 dalındayken Gemini sohbeti çıplak bir
    "HTTP 400" ile bitiyordu: `gemini_client`in GÖRSEL tarafında bilerek
    yazılan ayrım, SOHBET tarafında yoktu. Yüklem paylaşılıyor
    (`providers.is_invalid_key`) çünkü ayrışan tek şey buradaki `label`.
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return (f"{label} yetkilendirme hatası (401): API anahtarı geçersiz "
                "veya süresi dolmuş. Ayarlar'dan yeniden kaydet.")
    if status_code == 403:
        return (f"{label} erişimi reddetti (403): hesabın bu modele erişimi "
                "olmayabilir." + (f" {detail}" if detail else ""))
    if status_code == 404:
        return (f"{label} bu modeli tanımıyor (404): {wire_model}. "
                "Model kalkmış olabilir — composer'daki şeritten başka bir "
                "sohbet modeli seç.")
    if status_code == 429:
        return (f"{label} istek limiti aşıldı (429): biraz bekleyip tekrar "
                "dene. Faturalandırma limitin de dolmuş olabilir.")
    if status_code == 400 and providers.is_invalid_key(detail):
        # SIRA ÖNEMLİ: içerik dalından ÖNCE. Google'ın anahtar hatası
        # `INVALID_ARGUMENT` durumuyla geliyor ve aynı gövdede "content"
        # geçen bir alan adı da bulunabiliyor — ters sırada anahtar hatası
        # "içerik reddi" diye okunurdu, yani kullanıcı çalışan promptunu
        # değiştirmeye çalışırdı.
        return (f"{label} API anahtarı geçersiz (400): Ayarlar'dan yeniden "
                "kaydet." + (f" {detail}" if detail else ""))
    # ÇIPLAK `"content" in detail` DEĞİL ve bu ölçülmüş bir yanlış pozitif:
    # Google şema hatasını `Unknown name "content": Cannot find field.` diye
    # anlatıyor ve o dize "İçerik politikası reddi" olarak gösteriliyordu —
    # kullanıcı engellenmeyen bir mesajı yeniden yazmaya çalışırdı
    # (bkz. providers.is_content_policy).
    if status_code == 400 and providers.is_content_policy(detail):
        return f"İçerik politikası reddi: mesaj {label} tarafından engellendi."
    return (f"{label} sohbet isteği başarısız (HTTP {status_code})."
            + (f" {detail}" if detail else ""))


def complete(m: catalog.ChatModel, messages: list[dict], *, client=None,
             credentials=None, instructions: str | None = None) -> dict:
    """Tek turda tamamlama. `{"content": str, "finish_reason": str}` döndürür.

    `chat_providers.complete`'in sözleşmesini uyguluyor; imzası
    `chat_client.complete`'in aynısı, tek farkla — model tanımı İLK parametre.

    `credentials` verilmezse `credstore.resolve(m.credential)` ile tembel
    çözülüyor: `providers._azure_generate`'in docstring'inde yazılı gerekçe
    (kimliği erken çözmek, stub'lanmış bir çağrının bile gerçek bir
    `credentials.env` istemesine yol açar) burada da geçerli.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    if instructions is None:
        try:
            instructions = chat_prompt.load_instructions()
        except ValueError as e:
            raise cc.ChatError(f"Prompt Yönetmeni talimatı yüklenemedi: {e}")

    label = _label(m)
    endpoint = base_url.rstrip("/") + m.endpoint_path
    payload = cc.build_payload(messages, m.wire_model, instructions)
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json"}

    import httpx   # bkz. chat_client.complete(): hata türleri için de gerekli
    owns_client = client is None
    if owns_client:
        client = httpx.Client()
    try:
        resp = client.post(endpoint, headers=headers, json=payload,
                           timeout=ac.request_timeout(cc.REQUEST_TIMEOUT))
    except httpx.TransportError as exc:
        # Metin `azure_client`'ta PAYLAŞILIYOR ama sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir cümle OpenAI hatasında kullanıcıyı
        # yanlış endpoint'i kurcalamaya iter (`openai_client._post`'un aynı
        # satırı).
        raise cc.ChatError(
            ac.transport_error_message(exc, cc.REQUEST_TIMEOUT)
            .replace("Azure", label)) from exc
    finally:
        if owns_client:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise cc.ChatError(map_error(resp.status_code, body, label=label,
                                    wire_model=m.wire_model))

    content, finish_reason = cc.extract_content(resp.json())
    return {"content": content, "finish_reason": finish_reason}
