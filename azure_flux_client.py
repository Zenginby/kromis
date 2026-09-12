# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Azure AI Foundry · FLUX.2 (Black Forest Labs) — BFL yolu.

`azure_mai_client`ın KARDEŞİ ama İKİZİ DEĞİL: aynı host, aynı `api-key`, ama
yol ve gövde farklı —

  • yol `/providers/blackforestlabs/v1/<model-path>?api-version=preview`
    ve `<model-path>` DAĞITIM ADI DEĞİL (`FLUX.2-pro` → `flux-2-pro`);
  • düzenleme AYRI BİR UÇ DEĞİL: referanslar aynı JSON gövdesine
    `input_image`, `input_image_2`, … olarak base64 giriyor;
  • flex'te `steps` + `guidance` GERÇEK bir kalite ekseni.

Tek bir `azure_foundry_client.py` REDDEDİLDİ: tek modül iki tel formatı
taşırdı, hata eşlemesi bulanıklaşırdı ve `PROVIDER_LOGOS` tek anahtara
düşerdi — oysa üretici gerçekten iki (Microsoft ve Black Forest Labs).

**FLUX'TA YERLEŞİK İÇERİK FİLTRESİ YOK** (Microsoft'un kendi uyarısı). Yani
`providers.is_content_policy` bu sağlayıcıda HİÇ tetiklenmeyecek ve bu bir
kusur değil, sağlayıcının özelliği. Açıkça yazılı ki ileride "içerik reddi
dalı neden çalışmıyor" diye aranmasın. `map_error`da o dal BİLEREK yok.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA (Chaquopy `include "*.py"`; bkz.
azure_mai_client.py'nin başlığı ve tests/test_android_packaging.py).

CANLI DOĞRULAMANIN SINIRI (2026-09-08) ve bu dosyanın en büyük riski:
**FLUX'un 200 YANITI BU DEPODAN GÖRÜLMEDİ.** Şekil Microsoft'un kendi örnek
deposundan alındı (`data[0]["b64_json"]`, senkron) ve MAI ile gpt-image-2'nin
ikisi de aynı şekli döndürüyor, ama ölçüm YOK. Azaltma `decode_images`ta:
beklenmeyen şekil ham `KeyError` değil Türkçe bir `ImageError` üretiyor —
sarmalanmayan bir `KeyError` app.py'nin süzgecinden geçer ve kullanıcı
beklemenin sonunda yalnızca "Hata (500)" görür. ÖLÇÜLMEYEN diğer üç şey:
kimlik başlığının adı (bkz. AUTH_HEADER), `num_images`ın üst sınırı ve
FLUX'un gerçek boyut kabulü.

`api-version=preview` SABİT DEĞİL: bu takma ad ileride başka bir şemaya
işaret edebilir ve o gün değişecek tek yer `API_VERSION`.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import providers

# Kimlik başlığı: `azure_mai_client.AUTH_HEADER`ın aynı gerekçesi ve aynı
# ölçülmemiş tarafı. İki modülde ayrı sabit olmasının sebebi paylaşılan bir
# yardımcının iki sağlayıcıyı birbirine kaynatması (karar 8) — biri 401
# dönerse öteki dokunulmadan kalabiliyor.
AUTH_HEADER = "api-key"
API_VERSION = "preview"

# `num_images` gövdede AÇIKÇA 1: alanı hiç göndermemek sağlayıcının kendi
# varsayılanına güvenmek olurdu ve o değer belgelenmemiş. 1 olması
# `ImageModel.images_per_request=1` beyanının teldeki karşılığı — adet başına
# AYRI istek atılıyor ve `providers.read_timeout_for` bu yüzden adetle
# büyümeyen süreyi veriyor. `max_n` bir gün yükselirse iki seçenek var:
# döngüyü korumak (bu satır aynı kalır) ya da `images_per_request`i de
# yükseltip buraya `n` koymak. Yarısını yapmak, ödenen ücretle dönen görsel
# sayısının ayrışması demek.
NUM_IMAGES = 1

# TEL ADI → YOL PARÇASI. Dağıtım adı gövdedeki `model` alanına gidiyor, YOLA
# GİTMİYOR — ikisi farklı ve karıştırmak 404 demek. Tablo elle tutuluyor
# çünkü türetilebilir değil: `FLUX.2-pro` → `flux-2-pro` dönüşümü noktayı
# tireye çeviriyor ama `FLUX.2-flex` gibi başka bir ad yarın başka bir kalıp
# taşıyabilir. Bilinmeyen ad SESSİZ 404 değil Türkçe hata üretiyor.
_MODEL_PATHS: dict[str, str] = {
    "FLUX.2-pro": "flux-2-pro",
    "FLUX.2-flex": "flux-2-flex",
}

# Katalog jetonu → (steps, guidance). YALNIZ flex'te anlamlı; pro'nun
# `quality` parametresi yok ve tablo onun jetonunu ("standard") HİÇ
# tanımıyor, yani `quality_axis` None döndürüyor ve gövdeye iki alan da
# girmiyor. Değerler belgelenmiş aralıklardan: `steps` ≤ 50 (varsayılan 50),
# `guidance` 1.5–10 (varsayılan 4.5).
_FLEX_QUALITY: dict[str, tuple[int, float]] = {
    "hizli": (10, 3.0),
    "dengeli": (25, 4.5),
    "detayli": (50, 6.0),
}


def model_path(wire_model: str) -> str:
    """Tel adının YOL parçası. Bilinmeyen adda Türkçe `ImageError`.

    Ham `KeyError` BIRAKILMIYOR: katalog ile bu tablo ayrışırsa bu bir
    programlama hatası, ama yine de 502'ye çevrilebilir bir tür olmalı —
    ham 500'de arayüz gövdeyi ayrıştıramıyor (bkz. credstore'un
    "Tanımsız kimlik" dalı).
    """
    yol = _MODEL_PATHS.get(wire_model)
    if yol is None:
        raise ac.ImageError(
            f"FLUX yol eşlemesi yok: {wire_model}. Katalog ile "
            "azure_flux_client._MODEL_PATHS ayrışmış.")
    return yol


def endpoint_for(base_url: str, wire_model: str) -> str:
    """Tam uç adresi. `api-version` sorgu dizesinde ve SABİT DEĞİL (bkz. başlık)."""
    return (f"{base_url.rstrip('/')}/providers/blackforestlabs/v1/"
            f"{model_path(wire_model)}?api-version={API_VERSION}")


def split_size(token: str) -> tuple[int, int]:
    """`"1024x1536"` → `(1024, 1536)`. Bozuk jetonda Türkçe `ImageError`.

    `azure_mai_client.split_size`ın İKİZİ ve BİLEREK kopyalanmış: ortak bir
    yardımcıya çıkarmak iki sağlayıcıyı birbirine kaynatmak olurdu (karar 8)
    ve bu deponun yazılı kuralı `openai_client.py`nin başlığında —
    "İki kopya yeterli kanıt değil, ÜÇ kopya kanıttır". Üçüncü kopya
    ortaya çıktığında çıkarılacak yer o gün belli olur.
    """
    genislik, _, yukseklik = token.partition("x")
    try:
        return int(genislik), int(yukseklik)
    except ValueError:
        raise ac.ImageError(
            f"FLUX geometri jetonunu anlamadı: {token} "
            "(beklenen biçim: GENİŞLİKxYÜKSEKLİK).") from None


def quality_axis(quality: str) -> tuple[int, float] | None:
    """Kalite jetonu → `(steps, guidance)`; ekseni olmayan modelde None.

    None SESSİZ bir yol ve bilinçli: pro'nun jetonu ("standard") tabloda YOK
    ve gövdeye `steps`/`guidance` GİRMEMESİ gerekiyor. Bilinmeyen bir jetonu
    hata saymak, kalite ekseni olmayan modelde her üretimi düşürürdü.
    """
    return _FLEX_QUALITY.get(quality)


def build_payload(prompt: str, size: str, quality: str, *, api_model: str,
                  images=None) -> dict:
    """FLUX gövdesi. ÜRETİM ve DÜZENLEME AYNI gövdeyi kullanıyor.

    Düzenleme ayrı bir uç DEĞİL: referanslar `input_image`, `input_image_2`,
    `input_image_3`… alanlarına base64 olarak giriyor ve SIRA anlamlı (ilk
    görsel ana referans, adaptör sözleşmesinin kuralı). Numaralandırma 1'den
    DEĞİL 2'den başlıyor — ilk alanın adı sonek TAŞIMIYOR ve bu telin kendi
    kuralı, uydurulmuş bir simetri değil.
    """
    w, h = split_size(size)
    govde = {"model": api_model, "prompt": prompt,
             "width": w, "height": h, "num_images": NUM_IMAGES}
    eksen = quality_axis(quality)
    if eksen is not None:
        govde["steps"], govde["guidance"] = eksen
    for sira, (_ad, veri) in enumerate(images or ()):
        alan = "input_image" if sira == 0 else f"input_image_{sira + 1}"
        govde[alan] = base64.b64encode(veri).decode("ascii")
    return govde


def decode_images(response_json: dict) -> list[bytes]:
    """`data[].b64_json` → PNG baytları. ŞEKİL ÖLÇÜLMEDİ, o yüzden SARMALI.

    Spec'in 1. riski bu: FLUX'un 200'ü bu depodan görülmedi. Şekil değişirse
    doğru davranış ham `KeyError` değil Türkçe bir hata — sarmalanmayan bir
    `KeyError` app.py'nin `except ac.AzureImageError` süzgecinden GEÇER ve
    kullanıcı beklemenin sonunda yalnızca "Hata (500)" görür.
    """
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise ac.ImageError("FLUX yanıtı boş döndü (data yok). Tekrar deneyin.")
    out: list[bytes] = []
    for item in data:
        b64 = item.get("b64_json") if isinstance(item, dict) else None
        if not b64:
            raise ac.ImageError(
                "FLUX yanıtı beklenmedik biçimde geldi (b64_json yok).")
        out.append(base64.b64decode(b64))
    return out


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir.

    422 KENDİ DALINDA ve bu dosyanın en çok işe yarayan yeri: FLUX'un
    doğrulayıcısı mesaj yerine `error.details[]` listesi döndürüyor ve o liste
    okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya çöküyor — yani kullanıcı
    hangi alanın yanlış olduğunu hiçbir yerde okumuyor. Listeyi tek cümleye
    indiren yer `providers.detail_of` (`_details_metni`), Türkçeye çeviren
    yer burası.

    İÇERİK REDDİ DALI BİLEREK YOK: FLUX'ta yerleşik içerik filtresi
    bulunmuyor (Microsoft'un kendi uyarısı), yani `providers.is_content_policy`
    burada hiç tetiklenmeyecek. Boş bir dal bırakmak, ileride "neden hiç
    çalışmıyor" diye aranan bir şey olurdu.
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return ("Azure AI Foundry yetkilendirme hatası (401): api-key geçersiz "
                "veya bu kaynağa ait değil. Ayarlar'dan yeniden kaydet.")
    if status_code == 404:
        return ("FLUX dağıtımı bulunamadı (404): bu model Foundry'de "
                "dağıtılmamış olabilir, ya da Ayarlar'daki Foundry adresi "
                "başka bir kaynağı gösteriyor." + (f" {detail}" if detail else ""))
    if status_code == 422:
        return ("FLUX isteği reddetti (422): "
                + (detail or "gövdedeki alanlardan biri geçersiz."))
    if status_code == 429:
        return ("FLUX kotası doldu (429): biraz bekleyip tekrar deneyin. "
                "FLUX dağıtımlarının kapasitesi düşük.")
    return (f"FLUX isteği başarısız (HTTP {status_code})."
            + (f" {detail}" if detail else ""))


def _post(endpoint: str, key: str, payload: dict, *, client, read: float) -> dict:
    """Ortak POST + hata çevirisi. Multipart YOK — düzenleme de JSON.

    `client` sözleşmede KORUNUYOR (adaptör sözleşmesinin `client=` anahtarı):
    testler `FakeClient` geçiriyor ve döngülü üretimde tek istemciyi yeniden
    kullanmak bağlantı başına TLS el sıkışmasını da ortadan kaldırıyor.
    """
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        resp = client.post(endpoint,
                           headers={AUTH_HEADER: key,
                                    "Content-Type": "application/json"},
                           json=payload, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor: "Azure'a
        # bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter. ÜCRET UYARISI korunuyor.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "Foundry")) from exc
    finally:
        if owns:
            client.close()

    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = None
        raise ac.ImageError(map_error(resp.status_code, body))
    return resp.json()


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
          images, *, client, credentials) -> list[bytes]:
    """`generate` ve `edit`in PAYLAŞILAN gövdesi — tek fark `images`.

    FLUX'ta düzenleme ayrı bir uç DEĞİL, o yüzden iki fonksiyonu ayrı yazmak
    aynı döngüyü ve aynı zaman aşımı hesabını iki yerde bakıma sokardı
    (`gemini_client._uret`in aynı gerekçesi).

    KİMLİK TEMBEL çözülüyor; DÖNGÜ adet başına ayrı istek atıyor
    (`images_per_request=1`). Bugün `max_n=1` olduğu için döngü tek tur
    dönüyor, ama yapısı `max_n` yükseldiği gün hazır: `providers.total_budget`
    zaten tur sayısıyla ölçekleniyor.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    read = providers.read_timeout_for(m, n)
    endpoint = endpoint_for(base_url, m.wire_model)
    payload = build_payload(prompt, size, quality, api_model=m.wire_model,
                            images=images)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            out.extend(decode_images(
                _post(endpoint, key, payload, client=client, read=read)))
        return out[:n]
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, n, None,
                 client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana
    referans ve gövdedeki `input_image` alanına giriyor."""
    return _uret(m, prompt, size, quality, n, images,
                 client=client, credentials=credentials)
