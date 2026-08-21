"""Gemini görsel üretimi — Google'ın Interactions ucu.

BU DOSYA `openai_client.py`'NİN İKİZİ DEĞİL ve olmaması bir tercih değil,
tel formatının sonucu. `azure_client` ↔ `openai_client` çifti aynı teli
konuşuyor (`/images/generations`, `data[].b64_json`); Gemini'nin teli her
katmanda farklı:

  • yol: `POST {base}/v1beta/interactions` (model gövdede, yolda DEĞİL),
  • kimlik: `x-goog-api-key` başlığı (`Authorization: Bearer` değil),
  • istek: düz `prompt` alanı yok — sıralı bir `input[]` listesi, metin ve
    görsel blokları AYNI dizide,
  • geometri: `size` yok, `response_format.aspect_ratio` var ve jetonları
    `16:9` biçiminde,
  • çözünürlük: `quality` yok, `response_format.image_size` var (1K/2K/4K),
  • adet: `n` YOK — tek çağrı tek görsel,
  • yanıt: `data[]` yok, `steps[].content[]` var ve metin blokları görsel
    bloklarıyla aynı listede duruyor.

Yani `openai_client.py`'nin başlığındaki "üçüncü kopya çıkarma noktasıdır"
kuralı burada TETİKLENMİYOR: bu üçüncü bir kopya değil, üçüncü bir tel.
Paylaşılan tek şey ağ davranışı (`ac.CONNECT_TIMEOUT`, `ac.request_timeout`,
`ac.transport_error_message`) ve hata gövdesinin şekli
(`providers.detail_of` — Google da `{"error": {"message": …}}` döndürüyor).

DOSYA KÖKTE ve DÜZ olmak ZORUNDA: Android'in Chaquopy kaynak kümesi
`include "*.py"` ile kurulu, alt paket APK'ya hiç girmez (bkz.
tests/test_android_packaging.py). Adaptör `providers.py`'de STATİK import
ediliyor — `importlib` PyInstaller'ın statik analizinden kaçar.
"""
from __future__ import annotations

import base64

import azure_client as ac
import catalog
import credstore
import providers

# Sürüm ÖNEKİ burada, `credentials.env`'de DEĞİL. `GEMINI_BASE_URL` ve
# katalogdaki `default_base_url` çıplak konak adı taşıyor
# (`https://generativelanguage.googleapis.com`), yani `v1beta`dan `v1`e geçiş
# bir kod değişikliği — kullanıcının kayıtlı adresini geçersiz kılan bir
# migrasyon DEĞİL. Vekil (gateway) arkasına almak isteyen kullanıcı yine
# yalnız konağı değiştiriyor.
ENDPOINT_PATH = "/v1beta/interactions"

# Tek görsel bloğunun MIME'ı. Depoda diske yazılan her şey PNG
# (`app._to_png` girdiyi koşulsuz PNG'ye çeviriyor), o yüzden burada
# sağlayıcıya sorulacak bir şey yok.
PNG_MIME = "image/png"


def map_error(status_code: int, body: dict | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN paylaşılmıyor.

    `openai_client.map_error`'ın duruşunun aynısı ve aynı gerekçeyle: "OpenAI
    yetkilendirme hatası" diyen bir metin, Gemini anahtarını kurcalayan
    kullanıcıyı yanlış forma yönlendirir.

    400 İKİ ANLAMLI ve ayrım GÖVDEDEN okunuyor: Google geçersiz anahtarı da
    (`API_KEY_INVALID`) desteklenmeyen bir jetonu da 400 ile döndürüyor.
    Ayrımı yapmamak, anahtarı doğru olan kullanıcıya "anahtarını kontrol et"
    demek olurdu — yani onu çalışan kurulumunu bozmaya davet etmek.
    """
    detail = providers.detail_of(body)
    alt = detail.lower()
    if status_code == 400 and ("api key" in alt or "api_key" in alt):
        return ("Gemini API anahtarı geçersiz (400): Ayarlar'dan yeniden "
                "kaydet." + (f" {detail}" if detail else ""))
    if status_code in (401, 403):
        return (f"Gemini erişimi reddetti ({status_code}): anahtar geçersiz "
                "olabilir ya da hesabın bu modele erişimi yok."
                + (f" {detail}" if detail else ""))
    if status_code == 429:
        return ("Gemini istek limiti aşıldı (429): biraz bekleyip tekrar dene. "
                "Ücretsiz kademede görsel üretimi kapalı olabilir.")
    if status_code == 404:
        # Ölmüş bir model adının kullanıcıya görünen hâli. Metin MODELİ
        # söylüyor: `openai-dall-e-3` deneyimi tam olarak bunu öğretti —
        # "model bulunamadı" diyen ama hangi model olduğunu söylemeyen bir
        # hata, kullanıcıyı anahtarını kurcalamaya iter.
        return ("Gemini bu modeli tanımıyor (404): katalogdaki ad artık "
                "geçerli olmayabilir." + (f" {detail}" if detail else ""))
    if status_code == 400 and ("safety" in alt or "block" in alt
                               or "prohibited" in alt):
        return "İçerik politikası reddi: prompt Gemini tarafından engellendi."
    return f"Gemini isteği başarısız (HTTP {status_code})." + (f" {detail}" if detail else "")


def build_input(prompt: str, images=None) -> list[dict]:
    """`input[]` — metin ÖNCE, referans görseller sırayla arkasından.

    `images`: adaptör sözleşmesinin biçimi, sıralı [(dosya_adı, png_baytları)].
    Dosya ADI KULLANILMIYOR ve bu Azure'dan gerçek bir ayrım: orada multipart
    alan adı gerekiyordu (`ac.build_image_files`), burada tel yalnız baytı
    taşıyor. Sıra ise KORUNUYOR — sözleşme "ilk görsel ana referans" diyor ve
    Gemini de listedeki sırayı anlamlı sayıyor.
    """
    girdi: list[dict] = [{"type": "text", "text": prompt}]
    for _ad, raw in images or ():
        girdi.append({"type": "image", "mime_type": PNG_MIME,
                      "data": base64.b64encode(raw).decode("ascii")})
    return girdi


def build_payload(prompt: str, size: str, quality: str, *, api_model: str,
                  images=None) -> dict:
    """Interactions gövdesi.

    `n` YOK ve bu kataloğun `images_per_request=1` beyanının tel tarafındaki
    karşılığı: uç görsel adedi almıyor, adet döngüyle çözülüyor (bkz.
    `_uret`). İkisi ayrışırsa zaman aşımı politikası da yanlış olur
    (`providers.read_timeout_for`ın 36 dakikalık en kötü hâli).
    """
    return {
        "model": api_model,
        "input": build_input(prompt, images),
        # `type: image` AÇIKÇA yazılı: bu modeller metin de döndürebiliyor ve
        # istediğimiz şeyi söylemeyen bir istek, cevap olarak açıklama metni
        # alabilir — `decode_images` onu hataya çevirir, yani sessiz değil ama
        # gereksiz bir başarısızlık olurdu.
        "response_format": {"type": "image", "aspect_ratio": size,
                            "image_size": quality},
    }


def decode_images(response_json: dict) -> list[bytes]:
    """`steps[].content[]` içindeki görsel bloklarını PNG baytına çevirir.

    URL dalı YOK: Interactions ucu görseli her zaman gövdede base64 olarak
    döndürüyor (`openai_client.decode_images`ın ikinci HTTP isteği burada
    karşılığı olmayan bir bedel olurdu).

    GÖRSEL YOKSA metin bloğu HATA MESAJINA GİRİYOR. Bu satır bu dosyanın en
    çok işe yarayan yeri: model bir prompt'u reddettiğinde 200 ile geri
    dönüyor ve gerekçeyi METİN olarak yazıyor. Onu yutmak, kullanıcıya
    "görsel üretilemedi" diyen ama sebebini söylemeyen bir 502 vermek olurdu.
    """
    adimlar = response_json.get("steps")
    if not isinstance(adimlar, list):
        raise ac.ImageError("Gemini yanıtı beklenmedik biçimde geldi (steps yok).")

    out: list[bytes] = []
    metinler: list[str] = []
    for adim in adimlar:
        if not isinstance(adim, dict):
            continue
        for blok in adim.get("content") or ():
            if not isinstance(blok, dict):
                continue
            if blok.get("type") == "image" and blok.get("data"):
                out.append(base64.b64decode(blok["data"]))
            elif blok.get("type") == "text" and blok.get("text"):
                metinler.append(str(blok["text"]).strip())

    if not out:
        aciklama = " ".join(m for m in metinler if m)[:300]
        durum = response_json.get("status")
        raise ac.ImageError(
            "Gemini görsel döndürmedi"
            + (f" (durum: {durum})" if durum and durum != "completed" else "")
            + (f": {aciklama}" if aciklama else ". Prompt'u değiştirip tekrar deneyin."))
    return out


def _post(endpoint: str, key: str, payload: dict, *, client, read: float) -> dict:
    """Ortak POST + hata çevirisi.

    `client` sözleşmede KORUNUYOR (adaptör sözleşmesinin `client=` anahtarı):
    testler FakeClient geçiriyor ve döngülü üretimde tek istemciyi yeniden
    kullanmak bağlantı başına TLS el sıkışmasını da ortadan kaldırıyor.
    """
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        resp = client.post(endpoint,
                           headers={"x-goog-api-key": key,
                                    "Content-Type": "application/json"},
                           json=payload, timeout=ac.request_timeout(read))
    except httpx.TransportError as exc:
        # Mesaj `azure_client`'tan geliyor, sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin kullanıcıyı yanlış
        # endpoint'i kurcalamaya iter. ÜCRET UYARISI korunuyor.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "Gemini")) from exc
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

    Gemini'de düzenleme ayrı bir uç DEĞİL: referans görseller aynı `input[]`
    dizisine giriyor. İki fonksiyonu ayrı yazmak, aynı döngüyü ve aynı zaman
    aşımı hesabını iki yerde birden bakıma sokardı.

    DÖNGÜ ve ZAMAN AŞIMI: uç görsel adedi almıyor, o yüzden n görsel n istek.
    Her isteğe `providers.read_timeout_for` veriliyor ve o fonksiyon
    `images_per_request=1` gördüğü için adetle BÜYÜMEYEN tek isteğin süresini
    döndürüyor; döngünün toplamı da `providers.total_budget`e eşit oluyor.
    Karışsa n=4'te her isteğe 540 saniye verilirdi: 36 dakikalık en kötü hâl.

    HATA KISMİ SONUÇ BIRAKMIYOR: ikinci istek düşerse birincinin görseli de
    kaybediliyor ve 502 dönüyor. Alternatif (eldekini döndürüp sessizce eksik
    teslim etmek) bu deponun "sessiz sapma yasak" duruşuna aykırı — kullanıcı
    4 istedi, 3 aldı ve bunu hiçbir yerde okumadı olurdu. Adedi kısan tek
    yerin `fillAxis`in yüksek sesle söylediği kademe olması gerekiyor.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    read = providers.read_timeout_for(m, n)
    endpoint = base_url.rstrip("/") + ENDPOINT_PATH
    payload = build_payload(prompt, size, quality, api_model=m.wire_model,
                           images=images)

    # Tek istemci bütün döngü için: `_post`un `owns` dalı her turda yeni bir
    # bağlantı açardı. `client` verilmişse (testler, çağıran taraf) ona
    # dokunulmuyor.
    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        for _ in range(n):
            out.extend(decode_images(
                _post(endpoint, key, payload, client=client, read=read)))
        return out
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, n, None,
                 client=client, credentials=credentials)


def edit(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
         n: int, *, client=None, credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana referans."""
    return _uret(m, prompt, size, quality, n, images,
                 client=client, credentials=credentials)
