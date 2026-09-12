# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""OpenAI görsel üretimi — `azure_client.py`'nin BİLİNÇLİ ikizi.

`chat_client.py`'nin duruşunun aynısı ve aynı gerekçeyle: iki dosya aynı teli
konuşuyor (`/images/generations`, `/images/edits`, `data[].b64_json`) ama
`azure_client`'ı parametreleyip yeniden kullanmak ÜÇ somut bedeli olurdu —

  1. `ac.build_payload`'ın ürettiği tam sözlük `tests/test_azure_client.py`'de
     DONMUŞ durumda; oraya bir dal eklemek o mandalı gevşetirdi.
  2. Azure'ın kimlik çözümü belgelenmiş bir İKİ DOSYALI düşme ve paylaşılan bir
     `claude-tools` legacy dosyası içeriyor — OpenAI'de ikisinin de karşılığı yok.
  3. O dosyanın her yorumu Azure'a özgü (dağıtım adı, AI Foundry, endpoint
     formu). Ortak bir dosyada yorumlar ya yanlış ya da her cümlede "Azure'da
     şöyle, OpenAI'de böyle" demek zorunda kalırdı.

ÇIKARMA NOKTASI ŞİMDİDEN YAZILI: bu ikizin ÜÇÜNCÜSÜ ortaya çıktığında (fal'ın
uyumlu ucu, LM Studio, Groq) `openai_wire.py` çıkarılacak. İki kopya yeterli
kanıt değil, üç kopya kanıttır. O gün paylaşılacak şey `build_payload` +
`decode` + `edit` gövdesi; kimlik çözümü ve hata metinleri paylaşılmayacak.

Kayma mandalı: tests/test_openai_client.py, `ac.build_payload` ile bu dosyanın
`build_payload`'ını PAYLAŞILAN anahtarlar üzerinde karşılaştırıyor.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import i18n
import providers

# `azure_client.CONNECT_TIMEOUT` ve `read_timeout_for` PAYLAŞILIYOR: ağ
# davranışı sağlayıcıya göre değişmiyor ve iki ayrı sayı tutmak, birini
# ayarlayıp diğerini unutmanın kapısı olurdu.


def map_error(status_code: int, body: dict | list | None, *,
              wire_model: str | None = None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN paylaşılmıyor.

    `providers.detail_of` gövde şeklini çözüyor (dört sağlayıcı da
    `{"error": {"message": …}}` kullanıyor), ama metinler sağlayıcıya özgü
    kalmak zorunda: "Azure yetkilendirme hatası" diyen bir mesaj OpenAI
    anahtarını kurcalayan kullanıcıyı yanlış forma yönlendirir.

    404 ARTIK MODELİ SÖYLÜYOR ve bu dal bu dosyanın en çok işe yarayan yeri
    olabilir: `dall-e-3`'ün API'den kalkması tam olarak burada görünüyordu ve
    o gün kullanıcı "OpenAI isteği başarısız (HTTP 404)" okuyordu — hangi
    modelin kalktığını söylemeyen, dolayısıyla kullanıcıyı anahtarını
    kurcalamaya iten bir metin. Katalogdaki her tel adı bir gün kalkacak
    (`openai_chat.map_error`ın ve `gemini_client.map_error`ın 404 dallarının
    aynı gerekçesi); o günün maliyeti, adı yazmakla bir cümleye düşüyor.
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return i18n.t("err.openai_401")
    if status_code == 403:
        return i18n.t("err.openai_403") + (f" {detail}" if detail else "")
    if status_code == 429:
        return i18n.t("err.openai_429")
    if status_code == 404:
        return (i18n.t("err.openai_404")
                        + (f": {wire_model}." if wire_model else ".")
                        + " " + i18n.t("err.model_gone_pick_another")
                        + (f" {detail}" if detail else ""))
    # ÇIPLAK `"content" in detail` DEĞİL: `Invalid value for 'content'` de 400
    # ve o bir şema hatası — bkz. providers.is_content_policy.
    if status_code == 400 and providers.is_content_policy(detail):
        return i18n.t("err.openai_content_policy")
    return i18n.t("err.openai_failed", None, durum=status_code) + (
        f" {detail}" if detail else "")


def build_payload(prompt: str, size: str, quality: str, n: int, *,
                  api_model: str) -> dict:
    """`/images/generations` gövdesi.

    `ac.build_payload`'ın aynısı, tek farkla: `model` sabit değil PARAMETRE.
    `response_format` BİLEREK gönderilmiyor — `gpt-image-*` ailesi onu kabul
    etmiyor ve zaten b64 döndürüyor. (Bu satır bir zamanlar `dall-e-3`'ün URL
    dönen varsayılanından söz ediyordu; o model 12 Mayıs 2026'da API'den
    kalktı ve katalogdan çıkarıldı.)
    """
    return {"model": api_model, "prompt": prompt, "size": size,
            "quality": quality, "n": n}


def decode_images(response_json: dict, *, client=None) -> list[bytes]:
    """`data[]` içindeki her öğeyi PNG baytına çevirir.

    `ac.decode_images`'tan AYRILDIĞI tek nokta: orada `b64_json` KOŞULSUZ
    varsayılıyor (Azure her zaman öyle döndürüyor). Burada `url` de karşılanıyor.
    URL dalı ikinci bir HTTP isteği demek — o yüzden `client` buraya kadar
    taşınıyor.

    URL DALI NEDEN DURUYOR: onu getiren model (`dall-e-3`, tek görselini URL
    olarak döndürüyordu) 12 Mayıs 2026'da API'den kalktı, yani bugün katalogdaki
    hiçbir OpenAI modeli o şekli üretmiyor. Dal yine de silinmedi ve gerekçe
    kataloğun kendisinde yazılı: `openai` kimliğinin `url_env`i var, yani
    kullanıcı uyumlu bir vekilin (proxy/gateway) arkasına geçebiliyor ve o
    vekillerin bir kısmı b64 yerine URL döndürüyor. Silmek, çalışan bir
    kurulumu "ne b64_json ne url var" hatasına çevirirdi — kazancı ise
    ölçülmemiş bir sadelik.

    Adaptör sözleşmesi "çözülmüş PNG baytları döndür" diyor; bu fonksiyon o
    sözleşmenin OpenAI tarafındaki bedeli. Çağıran taraf hangi şeklin geldiğini
    HİÇ öğrenmiyor.
    """
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise ac.ImageError(i18n.t("err.openai_empty"))

    import httpx
    owns = client is None
    out: list[bytes] = []
    try:
        for item in data:
            if not isinstance(item, dict):
                raise ac.ImageError(i18n.t("err.openai_unexpected"))
            if item.get("b64_json"):
                out.append(base64.b64decode(item["b64_json"]))
                continue
            url = item.get("url")
            if not url:
                raise ac.ImageError(
                    i18n.t("err.openai_no_payload"))
            if client is None:
                client = httpx.Client()
            try:
                resp = client.get(url, timeout=ac.request_timeout(ac.READ_TIMEOUT_FIRST))
            except httpx.TransportError as exc:
                raise ac.ImageError(
                    ac.transport_error_message(exc, ac.READ_TIMEOUT_FIRST)
                    .replace("Azure", "OpenAI")) from exc
            if resp.status_code != 200:
                raise ac.ImageError(
                    i18n.t("err.openai_download_failed", None, durum=resp.status_code))
            out.append(resp.content)
    finally:
        if owns and client is not None:
            client.close()
    return out


def _post(endpoint, headers, *, client, read, json=None, data=None, files=None):
    """Ortak POST + hata çevirisi. `ac.generate`/`ac.edit`'in gövdesinin aynısı.

    İki fonksiyon arasında PAYLAŞILIYOR çünkü ikisi de aynı şeyi yapıyor;
    `azure_client`'ta bu paylaşım yok ve orada gövde iki kez yazılı — o dosyaya
    dokunmama kararının bedeli, burada tekrarlamak zorunda olmamak kazancı.
    """
    import httpx
    owns_client = client is None
    if owns_client:
        client = httpx.Client()
    try:
        resp = client.post(endpoint, headers=headers, json=json, data=data,
                           files=files, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`'tan geliyor ama sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin OpenAI hatasında kullanıcıyı
        # yanlış endpoint'i kurcalamaya iter. ÜCRET UYARISI korunuyor.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "OpenAI")) from exc
    finally:
        if owns_client:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        # Tel adı GÖVDEDEN: `generate` JSON, `edit` multipart `data`
        # gönderiyor ve ikisinde de `model` alanı var. İmzaya eklemek aynı
        # değeri iki yoldan taşımak olurdu (`gemini_client._post`un aynı
        # gerekçesi).
        raise ac.ImageError(map_error(
            resp.status_code, body,
            wire_model=(json or data or {}).get("model")))
    return resp.json()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    key, base_url = credentials if credentials is not None else credstore.resolve(m.credential)
    read = providers.read_timeout_for(m, n)
    body = _post(base_url.rstrip("/") + "/images/generations",
                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                 client=client, read=read,
                 json=build_payload(prompt, size, quality, n, api_model=m.wire_model))
    return decode_images(body, client=client)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana referans.

    Multipart alanlarını `ac.build_image_files` kuruyor: tel formatı BİREBİR
    aynı (tek görselde `image`, çoklu görselde tekrarlanan `image[]`) ve o
    fonksiyon canlı doğrulanmış. Kopyalamak, iki yerde birden yanlış olabilecek
    bir tel detayı üretirdi.
    """
    key, base_url = credentials if credentials is not None else credstore.resolve(m.credential)
    read = providers.read_timeout_for(m, n)
    body = _post(base_url.rstrip("/") + "/images/edits",
                 # Content-Type YOK: multipart sınırını istemci koyuyor.
                 {"Authorization": f"Bearer {key}"},
                 client=client, read=read,
                 data={"model": m.wire_model, "prompt": prompt, "size": size,
                       "quality": quality, "n": str(n)},
                 files=ac.build_image_files(images))
    return decode_images(body, client=client)
