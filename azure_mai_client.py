# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Azure AI Foundry · MAI-Image ailesi — `/mai/v1/images/{generations,edits}`.

`azure_client.py`'nin İKİZİ DEĞİL, KARDEŞİ: tel formatı gerçekten farklı ve
fark tek bir alanda değil ÜÇ eksende birden —

  • host `<kaynak>.services.ai.azure.com`, `/openai/v1` DEĞİL;
  • geometri `size:"1024x1024"` değil `width`+`height` (int);
  • `quality` ve `n` parametreleri HİÇ YOK.

`/openai/v1`in bu modelleri servis ETMEDİĞİ kanıtlandı: şema doğrulamasını
geçen istek "Model not supported with Responses API" ile düşüyor ve Entra
sondası sebebi gösterdi — iki AYRI veri eylemi
(`…/accounts/OpenAI/images/generations/action` ve
`…/accounts/MaaS/images/generations/action`). Yani bu modelleri
`gpt-image-2`nin ikizi olarak beyan etmek, `catalog.py`nin uyardığı
"arayüzde seçilebilir bir 400"ün tam kendisi olurdu.

BU DOSYANIN EN PAHALI DERSİ, ve her satırını okuyan bunu bilmeli:
**MAI TANIMADIĞI ALANI SESSİZCE YUTUYOR.** Sondada `size:"1x1"` gönderildi;
MAI'nin `size` diye bir parametresi OLMADIĞI için alan yok sayıldı, istek
reddedilmedi ve İKİ GERÇEK GÖRSEL üretilip faturalandı (1024×1024). Sonuç:
sağlayıcı artık bir doğrulama katmanı DEĞİL. `models.check_capabilities` tek
kapı, `catalog.MAI_SIZES` de o kapının verisi — oradaki bir hata kullanıcıya
hata değil, istemediği boyutta bir fatura gösterir.

`azure_client.py` BU TURDA HİÇ DÜZENLENMİYOR: `build_payload`ın ürettiği tam
sözlük tests/test_azure_client.py'de donmuş durumda ve "kayıtlı Azure
kullanıcısı için sıfır davranış değişikliği" güvencesi buna dayanıyor.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA — bir `azure_foundry/` alt paketi olamaz.
`android/app/build.gradle` Chaquopy kaynak kümesini `include "*.py"` ile
kuruyor, yani APK'ya YALNIZ kök düzeyindeki .py dosyaları giriyor: alt paket
masaüstünde çalışır, telefonda `ModuleNotFoundError` verir. Mandal:
tests/test_android_packaging.py.

CANLI DOĞRULAMANIN SINIRI (2026-09-08): yol, host, geometri alanları, `n`/
`quality`nin YOKLUĞU ve hata gövdesinin şekli kullanıcının KENDİ kaynağına
atılan gerçek isteklerle ölçüldü. 200 yanıtının şekli de görüldü
(`data[].b64_json` + `usage.num_output_tokens = 1024`). ÖLÇÜLMEYEN taraf:
kimlik BAŞLIĞININ adı (bkz. AUTH_HEADER) ve düzenleme ucunun multipart alan
adları — ikisi de planın Açık Kalemler'inde yazılı.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import i18n
import providers

GENERATE_PATH = "/mai/v1/images/generations"
EDIT_PATH = "/mai/v1/images/edits"

# KİMLİK BAŞLIĞI TEK YERDE ve bu bilinçli: sonda anahtarın üç yüzeyde de
# geçtiğini ölçtü ama BAŞLIĞIN ADINI ölçmedi. `services.ai.azure.com`un kendi
# geleneği `api-key`; `Authorization: Bearer` (bu deponun Azure OpenAI yolunda
# kullandığı) da kabul edilebiliyor. Canlı ilk çağrı 401 dönerse değiştirilecek
# TEK yer bu sabit — iki fonksiyonda birden yazılı olsaydı biri değişip öteki
# kalabilirdi. Mandal: tests/test_azure_mai_client.py.
AUTH_HEADER = "api-key"


def split_size(token: str) -> tuple[int, int]:
    """`"1024x768"` → `(1024, 768)`. Bozuk jetonda Türkçe `ImageError`.

    ÇEVİRİM ADAPTÖRDE, katalogda DEĞİL: `sizes` demeti jetonları STRING olarak
    taşımaya devam ediyor, yani `ResultParams.size`, `history.json` kayıtları,
    `storage.save` ve core.js'in oran-taşıma kademesi HİÇ değişmiyor. Bu,
    `ImageModel.sizes` docstring'inde Gemini için verilen kararın aynısı —
    "jeton, piksel değil".

    Ham `ValueError` BIRAKILMIYOR: bayat bir istemci ya da Prompt Yönetmeni'nin
    önerdiği bir jeton buraya ulaşabiliyor ve o durumun cevabı ham 500 değil,
    502'ye çevrilebilir Türkçe bir hata olmalı.
    """
    genislik, _, yukseklik = token.partition("x")
    try:
        return int(genislik), int(yukseklik)
    except ValueError:
        raise ac.ImageError(
            i18n.t("err.mai_bad_geometry", None, jeton=token)) from None


def build_payload(prompt: str, size: str, *, api_model: str) -> dict:
    """MAI üretim gövdesi. `quality` ve `n` BİLEREK YOK.

    İkisi de MAI'de mevcut DEĞİL ve göndermek zararsız da değil: tanınmayan
    alan sessizce yutuluyor (bkz. dosya başlığı), yani "gönderdim, demek ki
    uygulandı" varsayımı yanlış bir faturaya dönüşür. Beyan edilmeyen alan
    hiç gönderilmiyor.
    """
    w, h = split_size(size)
    return {"model": api_model, "prompt": prompt, "width": w, "height": h}


def build_image_file(images):
    """MAI düzenlemesi TEK görsel alıyor: `image` alanı, tekrarlanan `image[]` YOK.

    `ac.build_image_files` KULLANILMIYOR ve bu bilinçli: o fonksiyon çoklu
    görselde `image[]` tekrarına geçiyor (OpenAI/Azure'ın canlı doğrulanmış
    teli) ve MAI o alanı tanımıyor — tanınmayan alan da SESSİZCE yutuluyor,
    yani kullanıcı gönderdiği üç referansın yok sayıldığını hiçbir yerde
    okumazdı.

    KAPI BURADA olmak ZORUNDA: görsel düzenleme rotası (`app._collect_edit_refs`)
    yalnız küresel `MAX_EDIT_IMAGES`e bakıyor, model başına `max_refs`e
    BAKMIYOR — o kapı bugün yalnız video yolunda var. MAI, `max_refs=1` beyan
    eden ilk GÖRSEL modeli, yani ikinci kapı olmadan sessiz sapma gerçek
    olurdu.
    """
    if not images:
        raise ac.ImageError(i18n.t("err.need_an_image"))
    if len(images) > 1:
        raise ac.ImageError(
            i18n.t("err.mai_one_reference", None, adet=len(images)))
    filename, data = images[0]
    return {"image": (filename, data, "image/png")}


def decode_images(response_json: dict) -> list[bytes]:
    """`data[].b64_json` → PNG baytları. Beklenmeyen şekil ham `KeyError` DEĞİL.

    `ac.decode_images`ın koşulsuz `data[].b64_json` varsayımı Azure'ın özel
    meselesi ve orada kalıyor (bkz. providers.py'nin başlığı). Buradaki kopya
    aynı şekli okuyor ama SARMALIYOR: sarmalanmayan bir `KeyError`
    `app.py`nin `except ac.AzureImageError` süzgecinden GEÇER, ham 500 olur ve
    kullanıcı beklemenin sonunda yalnızca "Hata (500)" görür.
    """
    data = response_json.get("data")
    if not isinstance(data, list) or not data:
        raise ac.ImageError(i18n.t("err.mai_empty"))
    out: list[bytes] = []
    for item in data:
        b64 = item.get("b64_json") if isinstance(item, dict) else None
        if not b64:
            raise ac.ImageError(i18n.t("err.mai_unexpected"))
        out.append(base64.b64decode(b64))
    return out


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN paylaşılmıyor.

    `providers.detail_of` gövde şeklini çözüyor — MAI'nin gövdesi
    (`error.code` + `message` + `details`) OpenAI şekline yeterince yakın.
    `azure_client.map_error`ın mantığı buraya KOPYALANMIYOR ve ORTAK bir
    yardımcıya da ÇIKARILMIYOR: iki satırlık bir zincir, paylaşılan bir
    soyutlamanın iki sağlayıcıyı birbirine kaynatmasından ucuz (bkz. karar 8).

    429 AYRI bir dal ve gerekçesi ölçülmüş: Foundry dağıtımlarının kapasitesi
    düşük ve sonda sırasında `RateLimitReached` birkaç kez görüldü. Ham bir
    502 kullanıcıya "bozuk" der; doğru cevap "kota doldu, biraz bekle".
    """
    detail = providers.detail_of(body)
    if status_code == 401:
        return i18n.t("err.foundry_401")
    if status_code == 404:
        return i18n.t("err.mai_404") + (f" {detail}" if detail else "")
    if status_code == 429:
        return i18n.t("err.mai_429")
    if providers.is_content_policy(detail):
        return i18n.t("err.mai_content_policy")
    return (i18n.t("err.mai_failed", None, durum=status_code)
            + (f" {detail}" if detail else ""))


def _post(endpoint: str, key: str, *, client, read: float,
          json=None, data=None, files=None) -> dict:
    """Ortak POST + hata çevirisi; `generate` ve `edit` PAYLAŞIYOR.

    `client` sözleşmede KORUNUYOR (adaptör sözleşmesinin `client=` anahtarı):
    testler `FakeClient` geçiriyor ve döngülü üretimde tek istemciyi yeniden
    kullanmak bağlantı başına TLS el sıkışmasını da ortadan kaldırıyor.

    `Content-Type` YALNIZ JSON gövdede: multipart'ta sınırı istemci koyuyor ve
    elle yazmak gövdeyi bozar.
    """
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    headers = {AUTH_HEADER: key}
    if json is not None:
        headers["Content-Type"] = "application/json"
    try:
        resp = client.post(endpoint, headers=headers, json=json, data=data,
                           files=files, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor: "Azure'a
        # bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter, oysa çözülemeyen adres Foundry'nin. ÜCRET UYARISI
        # korunuyor.
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


def _uret(m: catalog.ImageModel, prompt: str, size: str, n: int, images,
          *, client, credentials) -> list[bytes]:
    """`generate` ve `edit`in PAYLAŞILAN gövdesi — tek fark `images`.

    KİMLİK BURADA, TEMBEL çözülüyor (`credstore.resolve`): erken çözüm
    `providers._azure_generate`in yorumunda anlatılan 104 testlik dersin
    tekrarı olurdu — rota testleri adaptörü monkeypatch'liyor ve kimliği HİÇ
    yapılandırmıyor.

    DÖNGÜ ve ZAMAN AŞIMI: MAI'de `n` YOK, yani n görsel n istek.
    `providers.read_timeout_for` `images_per_request=1` gördüğü için adetle
    BÜYÜMEYEN tek isteğin süresini döndürüyor; döngünün toplamı da
    `providers.total_budget`e eşit oluyor. Karışsa n=4'te her isteğe 540
    saniye verilirdi: 36 dakikalık en kötü hâl.

    HATA KISMİ SONUÇ BIRAKMIYOR: ikinci istek düşerse birincinin görseli de
    kaybediliyor ve 502 dönüyor. Alternatif (eldekini döndürüp sessizce eksik
    teslim etmek) bu deponun "sessiz sapma yasak" duruşuna aykırı.

    `out[:n]` bir süsleme değil: `decode_images` tek yanıttan birden çok görsel
    döndürebiliyor ve fazlalık `models.MAX_IMAGES_PER_RUN` (4) ile
    `ChatMessage.image_ids`in `max_length=4`ünde patlar — hem de görseller
    ÜRETİLDİKTEN ve ücret ödendikten sonra.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    read = providers.read_timeout_for(m, n)
    kok = base_url.rstrip("/")
    w, h = split_size(size)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            if images is None:
                govde = _post(kok + GENERATE_PATH, key, client=client, read=read,
                              json=build_payload(prompt, size,
                                                 api_model=m.wire_model))
            else:
                # Multipart alanları STRING: `azure_client.edit`in `"n": str(n)`
                # duruşunun aynısı — httpx sayıyı `data=` içinde kabul etmiyor.
                govde = _post(kok + EDIT_PATH, key, client=client, read=read,
                              data={"model": m.wire_model, "prompt": prompt,
                                    "width": str(w), "height": str(h)},
                              files=build_image_file(images))
            out.extend(decode_images(govde))
        return out[:n]
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    """`quality` BİLEREK YOK SAYILIYOR: MAI'nin kalite parametresi yok.

    İmzada duruyor çünkü adaptör SÖZLEŞMESİNİN parçası (bkz. providers.py'nin
    başlığı) ve katalog tek sentetik jeton + `quality_hidden=True` beyan
    ediyor — boş `qualities` `ResultParams`ta 422 demekti, yani o modelle
    üretilmiş bir oturumun bir daha kaydedilememesi.
    """
    return _uret(m, prompt, size, n, None,
                 client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — MAI yalnız İLKİNİ alır
    ve fazlası SESSİZCE düşmez, `build_image_file` yüksek sesle reddeder."""
    return _uret(m, prompt, size, n, images,
                 client=client, credentials=credentials)
