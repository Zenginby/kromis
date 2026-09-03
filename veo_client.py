"""Video üretimi — Google'ın Veo modelleri, `predictLongRunning` ucu.

BU DOSYA `gemini_client.py`'NİN İKİZİ DEĞİL. Kimlik başlığını
(`x-goog-api-key`), konağı ve hata gövdesinin şeklini onunla paylaşıyor; geri
kalan her şey farklı ve en önemli fark YAŞAM DÖNGÜSÜ:

  • yol: `POST {base}/v1beta/models/{model}:predictLongRunning` (model YOLDA,
    gövdede DEĞİL — Interactions ucunun tam tersi),
  • istek: `instances[]` + `parameters{}` — Interactions'ın `input[]` /
    `response_format{}` çifti değil,
  • yanıt TEK VURUŞTA GELMİYOR: dönen şey bir `operation` adı. Sonuç, o ad
    `done` olana kadar yoklanarak alınıyor ve videonun kendisi ÜÇÜNCÜ bir
    istekle (imzalı `uri`ye `GET`) indiriliyor,
  • geometri: `parameters.aspectRatio` ve YALNIZ iki jeton (16:9, 9:16),
  • çözünürlük: `parameters.resolution` (720p/1080p), `image_size` değil,
  • yeni eksen: `parameters.durationSeconds`.

Yani `gemini_client.py`'nin başlığındaki "bu üçüncü bir kopya değil, üçüncü
bir tel" cümlesi burada bir kez daha geçerli: bu DÖRDÜNCÜ tel ve tek POST
varsayımını da kıran ilki. Paylaşılan tek şey ağ davranışı
(`ac.CONNECT_TIMEOUT`, `ac.request_timeout`) ve hata gövdesinin çözümlemesi
(`providers.detail_of`, `is_invalid_key`, `is_content_policy`).

SÖZLEŞME `providers.py`'deki görsel sözleşmesinin video ikizi — adaptör
ÇÖZÜLMÜŞ MP4 BAYTLARI döndürüyor:

    generate(m, prompt, size, quality, duration, n, *, client=None, credentials=None) -> list[bytes]
    animate(m, prompt, images, size, quality, duration, n, *, client=None, credentials=None) -> list[bytes]

`images`: görsel sözleşmesinin AYNI biçimi, sıralı [(dosya_adı, png_baytları)].
Yalnız İLKİ kullanılıyor (`catalog` `max_refs=1` diyor): Veo'nun bu turdaki
girdisi ilk KARE. Uçun ilk/son kare ve çoklu referans yetenekleri BİLEREK
kapsam dışı — her biri kendi yetenek bayrağını ve kendi arayüz kontrolünü
ister.

CANLI DOĞRULAMANIN DURUMU (3 Eylül 2026): HİÇ canlı çağrı yapılmadı, bu
depoda yapılamıyor da — Veo'nun ÜCRETSİZ KADEMESİ YOK, yani anahtarsız bir
çağrı `gemini_client`in aldığı gibi "yol tanınıyor" sinyali bile vermiyor,
faturalı bir anahtar gerekiyor. Aşağıdaki her şey belgeye dayanıyor
(ai.google.dev/gemini-api → Veo) ve ilk gerçek anahtarla bir kez sınanmalı.
Riskin en yüksek olduğu üç yer: `_video_uri`nin okuduğu yuvalanma
(`generateVideoResponse.generatedSamples[]`), `parameters` alan adları, ve
indirme `GET`inin kimliği başlıkla mı sorgu dizesiyle mi istediği.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA: Android'in Chaquopy kaynak kümesi
`include "*.py"` ile kurulu, alt paket APK'ya hiç girmez (bkz.
tests/test_android_packaging.py). Adaptör `providers.py`'de düz bir `import`
ifadesiyle bağlanıyor — `importlib` PyInstaller'ın statik analizinden kaçar ve
`hiddenimports=[]` değerini geçersiz kılar.
"""
from __future__ import annotations

import base64
import time

import azure_client as ac
import catalog
import credstore
import providers

# Sürüm ÖNEKİ kodda, `credentials.env`'de DEĞİL — `gemini_client.ENDPOINT_PATH`
# ile birebir aynı gerekçe: `GEMINI_BASE_URL` çıplak konak taşıyor, yani
# `v1beta`dan `v1`e geçiş bir kod değişikliği, kullanıcının kayıtlı adresini
# geçersiz kılan bir migrasyon DEĞİL.
SUBMIT_PATH_TMPL = "/v1beta/models/{model}:predictLongRunning"

# Operation adı yanıtta `models/…/operations/…` biçiminde, yani ÖNEKSİZ ve
# taban adrese eklenmeye hazır. Sürüm öneki yine bizden.
OPERATION_PREFIX = "/v1beta/"

# Yüklenen referans karenin MIME'ı. `app._to_png` girdiyi koşulsuz PNG'ye
# çevirdiği için burada sağlayıcıya sorulacak bir şey yok
# (`gemini_client.PNG_MIME` ile aynı olgu).
PNG_MIME = "image/png"

# ÜÇ AYRI ZAMAN AŞIMI ve üçünün ayrı olması bu dosyanın taşıyıcı kararı:
#
#   • SUBMIT/YOKLAMA istekleri kısa. İkisi de metadata çağrısı — biri bir
#     operation adı, öteki bir `done` bayrağı döndürüyor. Onlara
#     `providers.read_timeout_for`ın verdiği değeri (video modellerinde
#     `poll_timeout`, yani 7-10 dakika) vermek, ölü bir ağda tek bir yoklamada
#     o kadar beklemek olurdu.
#   • İNDİRME uzun: gelen şey megabaytlarca MP4.
#   • DÖNGÜNÜN TAMAMI `providers.total_budget`la sınırlı. `read_timeout_for`ın
#     sözleşmesi "TEK isteğin okuma süresi" ve onu toplam son tarih olarak
#     kullanmak o sözleşmeyi bozardı; `total_budget` ise adıyla ve
#     docstring'iyle zaten "döngünün duvar saati tavanı".
POLL_READ_TIMEOUT = 30.0
DOWNLOAD_READ_TIMEOUT = ac.read_timeout_for(1)

# Geri çekilme: 1 saniyeden başlayıp 10'da sınırlanıyor (belgenin önerdiği
# desen). TAVAN olmadan üstel artış bir noktada son tarihi tek bir uykuda
# aşardı ve kullanıcı sonucu hazır olduktan dakikalar sonra görürdü.
POLL_INTERVAL_START = 1.0
POLL_INTERVAL_MAX = 10.0
POLL_BACKOFF = 1.6


def _simdi() -> float:
    """Tek yönlü saat. Ayrı bir işlev olmasının sebebi TEST DİKİŞİ.

    `time.monotonic`i doğrudan çağırmak, son tarih dalını (deadline aşımı)
    yalnızca gerçekten dakikalarca bekleyen bir testle ölçülebilir kılardı.
    `time`ı küresel olarak maymun-yamalamak ise bütün takımı etkilerdi;
    modül düzeyindeki bu iki işlev yalnız bu dosyayı etkiliyor —
    `tests/conftest.py`'nin `backup` işlevini modül niteliği olarak
    yamalamasının aynı deseni.
    """
    return time.monotonic()


def _bekle(saniye: float) -> None:
    """Yoklama arası uyku. `_simdi` ile aynı gerekçe (test dikişi)."""
    time.sleep(saniye)


def map_error(status_code: int, body: dict | list | None, *,
              wire_model: str | None = None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN paylaşılmıyor.

    `gemini_client.map_error`'ın duruşunun aynısı ve aynı gerekçeyle: "Gemini
    görsel" diyen bir metin, video faturasını arayan kullanıcıyı yanlış yere
    yönlendirir.

    401/403/429 DALI BU DOSYANIN EN ÖNEMLİ YERİ ve ölçülmüş bir olgu
    üzerinde duruyor: **Veo'nun ücretsiz kademesi yok.** Görsel tarafında
    çalışan bir `GEMINI_API_KEY`, faturalandırması açık değilse burada
    reddediliyor. Genel "anahtar geçersiz olabilir" metnini göstermek,
    anahtarı GERÇEKTEN doğru olan kullanıcıyı çalışan kurulumunu bozmaya davet
    etmek olurdu — `gemini_client`in 400'ü ikiye ayırma kararının arkasındaki
    aynı ilke, burada başka bir eksende.
    """
    detail = providers.detail_of(body)
    ek = f" {detail}" if detail else ""
    if status_code == 400 and providers.is_invalid_key(detail):
        return ("Gemini API anahtarı geçersiz (400): Ayarlar'dan yeniden "
                "kaydet." + ek)
    if status_code in (401, 403):
        return ("Veo erişimi reddedildi "
                f"({status_code}): Veo'nun ÜCRETSİZ KADEMESİ YOK — Gemini "
                "anahtarının bağlı olduğu projede faturalandırma açık olmak "
                "zorunda. Anahtar görsel üretiminde çalışıyorsa sorun anahtarda "
                "değil, projenin ödeme ayarındadır." + ek)
    if status_code == 429:
        return ("Veo istek limiti aşıldı (429): biraz bekleyip tekrar dene. "
                "Faturalandırması yeni açılmış projelerde video kotası düşük "
                "başlıyor." + ek)
    if status_code == 404:
        # `gemini_client.map_error`ın 404 dalıyla aynı ders: metin MODELİ
        # söylüyor. Burada ad YOLDAN geliyor, yani telin gerçekten çağırdığı
        # değer — katalogdan ikinci bir okuma değil.
        return ("Gemini bu video modelini tanımıyor (404)"
                + (f": {wire_model}." if wire_model else ": katalogdaki ad "
                   "artık geçerli olmayabilir.")
                + " Composer'daki şeritten başka bir model seç." + ek)
    if status_code == 400 and providers.is_content_policy(detail):
        return "İçerik politikası reddi: prompt Veo tarafından engellendi."
    return f"Veo isteği başarısız (HTTP {status_code})." + ek


def build_payload(prompt: str, size: str, quality: str, duration: int, n: int,
                  *, images=None) -> dict:
    """`predictLongRunning` gövdesi.

    ŞEKİL Interactions'tan tümden farklı: prompt `instances[0]`ın içinde,
    knob'lar `parameters`ın içinde. `instances` ÇOĞUL ama tek öğeli — uç
    toplu istek alıyor, biz almıyoruz: `catalog` `max_n=1` diyor ve adet
    `parameters.sampleCount` üzerinden geçiyor, yani toplu istek ikinci bir
    adet ekseni olurdu.

    REFERANS KARE `instances[0].image`a giriyor, ayrı bir uca DEĞİL — Veo'da
    "animasyon" ayrı bir endpoint değil, aynı isteğin bir alanı
    (`gemini_client`in düzenlemeyi `input[]`e katmasının aynı olgusu). Yalnız
    İLK görsel kullanılıyor; sözleşme "ilk görsel ana referans" diyor ve
    `max_refs=1` de aynı şeyi söylüyor.
    """
    instance: dict = {"prompt": prompt}
    for _ad, raw in (images or ())[:1]:
        instance["image"] = {
            "bytesBase64Encoded": base64.b64encode(raw).decode("ascii"),
            "mimeType": PNG_MIME,
        }
    return {
        "instances": [instance],
        "parameters": {
            "aspectRatio": size,
            "resolution": quality,
            "durationSeconds": duration,
            "sampleCount": n,
        },
    }


def _coz_base64(deger) -> bytes:
    """Gömülü videoyu açar; BOZUK gövdeyi `ac.ImageError`a çevirir.

    Sarmalama ŞART ve gerekçesi `ac.ImageError`in docstring'inde yazılı:
    `binascii.Error` bir `ValueError` ve `app.py`nin
    `except ac.ImageError` süzgeçinden GEÇİP ham 500 olur — gövdesi JSON
    olmayan, kullanıcının sebebini hiçbir yerde okumadığı bir 500. Bu dalın
    şekli canlı DOĞRULANMADI (bkz. dosya başlığı), yani bozuk gelmesi
    teorik bir olasılık değil, en olası hatalardan biri.
    """
    try:
        return base64.b64decode(deger)
    except Exception as exc:
        raise ac.ImageError(
            "Veo yanıtındaki gömülü video çözülemedi (bozuk base64). "
            "Prompt'u değiştirip tekrar deneyin.") from exc


def _video_uri(op: dict) -> tuple[list[str], list[bytes]]:
    """Tamamlanmış operation'dan `(uri listesi, gömülü bayt listesi)`.

    İKİ DAL var çünkü belge İKİSİNİ de söylüyor: yanıt videoyu ya imzalı bir
    `uri` olarak ya da `bytesBase64Encoded` olarak taşıyor. Birini atlamak,
    çalışan bir kurulumda "video döndürmedi" hatası vermek olurdu.

    ŞEKİL TANINMAZSA HATA, sessiz boş liste DEĞİL — ve mesaj gövdede BULUNAN
    anahtarları yazıyor. Gerekçe `gemini_client.decode_images`in "model 200 ile
    ret metni döndürüyor, onu yutmak sebebi olmayan bir 502 verir" dersinin
    aynısı, bir adım ileri taşınmış hâli: burada risk en yüksek (yuvalanma
    canlı doğrulanmadı, bkz. dosya başlığı) ve uç bir gün adı değiştirirse
    kullanıcının göreceği metin, teşhisi TEK turda yapılabilir kılmalı.
    """
    yanit = op.get("response")
    if not isinstance(yanit, dict):
        raise ac.ImageError(
            "Veo yanıtı beklenmedik biçimde geldi (`response` yok). "
            f"Gövdedeki anahtarlar: {sorted(op)}.")

    kap = yanit.get("generateVideoResponse")
    ornekler = kap.get("generatedSamples") if isinstance(kap, dict) else None
    if not isinstance(ornekler, list):
        raise ac.ImageError(
            "Veo yanıtı beklenmedik biçimde geldi "
            "(`generateVideoResponse.generatedSamples` yok). "
            f"`response` içindeki anahtarlar: {sorted(yanit)}.")

    uriler: list[str] = []
    gomulu: list[bytes] = []
    for ornek in ornekler:
        if not isinstance(ornek, dict):
            continue
        video = ornek.get("video")
        if not isinstance(video, dict):
            continue
        if video.get("uri"):
            uriler.append(str(video["uri"]))
        elif video.get("bytesBase64Encoded"):
            gomulu.append(_coz_base64(video["bytesBase64Encoded"]))
    return uriler, gomulu


# `gemini_client.decode_images`'ın "200 ile gelen ret metnini yutma" kuralının
# video karşılığı. Sinyal İKİ AYRI KILIKTA geliyor ve İKİ AYRI İŞLEV okuyor —
# çünkü ANLAMLARI farklı ve ilk yazımda tek işlevde toplanmaları ölçülebilir
# bir kusur üretiyordu:
#
#   • `error` alanı → operation BAŞARISIZ bitti (kota, geçersiz parametre).
#     Sonuç geçersiz, yani video gelmiş olsa bile teslim edilmemeli.
#   • RAI FİLTRESİ → operation BAŞARIYLA bitti, içeriğin bir kısmı
#     engellendi. `sampleCount > 1` olduğunda n örnekten biri engellenip
#     geri kalanı TESLİM EDİLİYOR; ikisi tek işlevde toplandığında o teslim
#     edilen video atılıyordu — Google'ın ürettiği ve faturaladığı bir video.
#
# İkisi de HİÇBİR HTTP durumuyla haber verilmiyor: reddedilen bir prompt da
# 200 + `done: true` dönüyor. Yutulursa kullanıcı "video üretilemedi" diyen
# ama sebebini söylemeyen bir 502 alır — hem de gerekçe elimizdeyken.


def _operation_hatasi(op: dict) -> str | None:
    """Operation'ın KENDİSİ düştü mü — düştüyse mesajı.

    Bu dal KOŞULSUZ yükseltiliyor (bkz. `_uret`): başarısız bir operation'ın
    gövdesinde bir video görünse bile o sonuç geçerli değil.
    """
    hata = op.get("error")
    if isinstance(hata, dict) and hata.get("message"):
        return str(hata["message"])
    return None


def _filtre_gerekcesi(op: dict) -> str | None:
    """İçerik güvenlik filtresi devreye girdi mi — girdiyse gerekçesi.

    KOŞULLU yükseltiliyor (bkz. `_uret`): filtre KISMİ olabiliyor ve
    engellenmeyen örnekler teslim edilmek zorunda.

    None = "gerekçe bulunamadı", yani çağıran genel bir metin yazıyor.
    """
    yanit = op.get("response")
    kap = (yanit.get("generateVideoResponse")
           if isinstance(yanit, dict) else None)
    for kaynak in (kap, yanit):
        if not isinstance(kaynak, dict):
            continue
        sebepler = kaynak.get("raiMediaFilteredReasons")
        if isinstance(sebepler, list) and sebepler:
            return "; ".join(str(x) for x in sebepler)
        if kaynak.get("raiMediaFilteredCount"):
            return ("içerik güvenlik filtresi videoyu engelledi "
                    "(gerekçe belirtilmedi)")
    return None


def _timeout_message(gecen: float, butce: float) -> str:
    """Son tarih doldu. ÜCRET UYARISI `ac.transport_error_message`tan devralınıyor.

    Metin yeniden yazıldı, o işlev ÇAĞRILMADI: onun mesajı "adedi ya da
    kaliteyi düşür" diyor ve video tarafında yanlış tavsiye — buradaki knob
    SÜRE. Devralınan şey uyarının kendisi: zaman aşımı İSTEMCİNİN
    vazgeçmesidir, sağlayıcının değil. Video karşı tarafta tamamlanmış ve
    saniyesi faturalanmış olabilir ve kullanıcı "hata aldım, demek ki
    ücretlenmedim" diye düşünmemeli.
    """
    return (f"Veo {gecen:.0f} saniyede bitmedi (tavan {butce:.0f} sn). "
            "Süreyi ya da çözünürlüğü düşürüp tekrar dene. Not: üretim Google "
            "tarafında tamamlanmış ve ücretlendirilmiş olabilir, yalnızca "
            "sonuç bu tarafa ulaşmadı.")


def _istek(client, method: str, url: str, key: str | None, *, read: float,
           json=None):
    """Ortak HTTP + taşıma hatası çevirisi. Yanıtı ÇÖZÜMLEMİYOR.

    Üç adımın (submit / yokla / indir) üçü de bu kapıdan geçiyor, çünkü
    üçünde de aynı şey doğru olmak zorunda: sarmalanmayan bir httpx hatası
    `app.py`nin `except ac.AzureImageError` süzgeçinden GEÇİP ham 500 olur
    (bkz. `ac.ImageError`in docstring'i).

    `key=None` KİMLİKSİZ istek demek ve tek kullanıcısı `_indir`in Google
    dışı yönlendirme dalı — gerekçesi orada yazılı. Submit ve yoklama her
    zaman anahtar veriyor.

    YÖNLENDİRME İZLENMİYOR (`follow_redirects` yok): `_indir` onu ELLE
    izliyor, çünkü httpx yönlendirmede özel başlıkları soymuyor ve
    `x-goog-api-key` yabancı bir konağa gidiyordu.

    Durum kodu BURADA denetlenmiyor: `map_error` çağrısı için adım bağlamı
    (hangi model, hangi aşama) gerekiyor ve o bilgi çağıranda.
    """
    import httpx
    basliklar = {}
    if key:
        basliklar["x-goog-api-key"] = key
    if json is not None:
        basliklar["Content-Type"] = "application/json"
    try:
        return client.request(
            method, url,
            headers=basliklar,
            json=json,
            timeout=ac.request_timeout(read),
        )
    except httpx.TransportError as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin kullanıcıyı yanlış
        # endpoint'i kurcalamaya iter (`gemini_client._post`un aynı satırı).
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "Veo")) from exc


# İndirme yönlendirmesinde kimliğin GİDEBİLECEĞİ konaklar. Küme KAPALI ve
# hepsi Google'a ait.
GOOGLE_KONAK_SONLARI = (".googleapis.com", ".google.com",
                        ".googleusercontent.com")
# Yönlendirme tavanı: sonsuz döngü de bir hata hâli ve zaman aşımıyla değil
# kendi mesajıyla bitmeli.
MAX_YONLENDIRME = 5
_YONLENDIRME_KODLARI = (301, 302, 303, 307, 308)


def _google_konagi(url: str) -> bool:
    from urllib.parse import urlparse
    konak = (urlparse(url).hostname or "").lower()
    return konak.endswith(GOOGLE_KONAK_SONLARI) or konak in (
        "googleapis.com", "google.com")


def _indir(client, url: str, key: str, *, wire_model: str) -> bytes:
    """MP4'ü indirir. Yönlendirmeyi ELLE izler — ve bu bir güvenlik kararı.

    `follow_redirects=True` iki şeyi birden yapıyordu: yönlendirmeyi izliyor
    VE `x-goog-api-key` başlığını yeni konağa da taşıyordu. httpx
    yönlendirmede yalnız `Authorization`ı soyuyor, ÖZEL başlıkları değil — ve
    buradaki `uri` YANIT GÖVDESİNDEN geliyor, yani hedef konağı gövdeyi yazan
    taraf belirliyor. Faturalı bir Gemini anahtarını Google dışı bir konağa
    vermek, o anahtarı karşı tarafın eline bırakmak olurdu; üstelik bu dalın
    kimlik mekanizması bu depoda DOĞRULANMADI (bkz. dosya başlığı), yani
    "nereye gittiğini biliyoruz" varsayımı da yok.

    İzleme yine ŞART: izlenmezse gövde boş bir 302 olur ve hata "video
    döndürmedi" kılığında görünür — sebebi yanlış yerde aratan bir mesaj.
    Yani karar "izle ama kimliği taşıma".

    İmzalı depolama adresleri kimlik İSTEMİYOR: imza zaten yetkilendirmenin
    kendisi. O yüzden anahtarı düşürmek erişimi kaybetmek değil.
    """
    from urllib.parse import urljoin

    for _ in range(MAX_YONLENDIRME + 1):
        resp = _istek(client, "GET", url,
                      key if _google_konagi(url) else None,
                      read=DOWNLOAD_READ_TIMEOUT)
        if resp.status_code not in _YONLENDIRME_KODLARI:
            if resp.status_code != 200:
                raise ac.ImageError(map_error(resp.status_code, _govde(resp),
                                              wire_model=wire_model))
            return resp.content
        hedef = (getattr(resp, "headers", None) or {}).get("location")
        if not hedef:
            raise ac.ImageError(
                f"Veo videosu indirilemedi: {resp.status_code} yönlendirmesi "
                "adres taşımıyor.")
        # GÖRECELİ adres de geçerli (RFC 7231): `urljoin` mutlaklaştırıyor,
        # yoksa `_google_konagi` boş bir konak görüp anahtarı düşürürdü.
        url = urljoin(url, hedef)
    raise ac.ImageError(
        f"Veo videosu indirilemedi: {MAX_YONLENDIRME} yönlendirmeden sonra "
        "hâlâ dosyaya ulaşılamadı.")


def _govde(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str,
          duration: int, n: int, images, *, client, credentials) -> list[bytes]:
    """`generate` ve `animate`in PAYLAŞILAN gövdesi — tek fark `images`.

    `gemini_client._uret`in duruşunun aynısı ve aynı gerekçeyle: Veo'da
    animasyon ayrı bir uç değil, aynı isteğin bir alanı; iki işlev ayrı
    yazılsa aynı üç adımlı döngü ve aynı son tarih hesabı iki yerde birden
    bakıma girerdi.

    ÜÇ ADIM: submit → `done` olana kadar yokla → videoyu indir. Tek bir
    istemci üçünü de taşıyor (`gemini_client._uret`in tek-istemci kararı:
    bağlantı başına TLS el sıkışmasını ortadan kaldırıyor) ve `client`
    verilmişse ona hiç dokunulmuyor — testlerin enjekte ettiği sahte istemci
    tam olarak buradan giriyor.

    SON TARİH duvar saatiyle ölçülüyor (`providers.total_budget`), yoklama
    SAYISIYLA değil. Sayıya bağlamak, geri çekilme çarpanı değiştiğinde
    tavanın sessizce kayması demekti.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    taban = base_url.rstrip("/")
    butce = providers.total_budget(m, n)
    payload = build_payload(prompt, size, quality, duration, n, images=images)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        # ── 1. Submit ────────────────────────────────────────────────────
        submit_url = taban + SUBMIT_PATH_TMPL.format(model=m.wire_model)
        resp = _istek(client, "POST", submit_url, key,
                      read=POLL_READ_TIMEOUT, json=payload)
        if resp.status_code != 200:
            raise ac.ImageError(map_error(resp.status_code, _govde(resp),
                                          wire_model=m.wire_model))
        op = _govde(resp) or {}
        ad = op.get("name")
        if not ad:
            raise ac.ImageError(
                "Veo işi başlatılamadı: yanıtta operation adı yok "
                f"(anahtarlar: {sorted(op)}).")

        # ── 2. Yoklama ───────────────────────────────────────────────────
        # `done` İLK yanıtta da gelebiliyor (belgede kısa işler için mümkün);
        # o yüzden döngü uykuyla değil KONTROLLE başlıyor. Uykuyla başlamak,
        # hazır olan bir sonucu bir saniye bekletmek olurdu.
        op_url = taban + OPERATION_PREFIX + str(ad).lstrip("/")
        baslangic = _simdi()
        aralik = POLL_INTERVAL_START
        while not op.get("done"):
            gecen = _simdi() - baslangic
            if gecen >= butce:
                raise ac.ImageError(_timeout_message(gecen, butce))
            # `POLL_INTERVAL_MAX` burada İKİNCİ KEZ sorulmuyor: `aralik` bir
            # satır aşağıda zaten onunla sınırlanıyor. Kalan tek tavan SON
            # TARİH — hazır olabilecek bir sonucu bütçenin ötesinde bekletmemek.
            _bekle(min(aralik, max(0.0, butce - gecen)))
            aralik = min(aralik * POLL_BACKOFF, POLL_INTERVAL_MAX)
            resp = _istek(client, "GET", op_url, key, read=POLL_READ_TIMEOUT)
            if resp.status_code != 200:
                raise ac.ImageError(map_error(resp.status_code, _govde(resp),
                                              wire_model=m.wire_model))
            op = _govde(resp) or {}

        # ── 3. Sonuç ─────────────────────────────────────────────────────
        #
        # OPERATION HATASI KOŞULSUZ: iş düştüyse sonuç geçersiz ve gövdede
        # bir video görünse bile teslim edilmemeli.
        hata = _operation_hatasi(op)
        if hata:
            raise ac.ImageError(f"Veo video üretmedi: {hata}")

        # FİLTRE GEREKÇESİ KOŞULLU ve bu sıra ölçülü: filtre KISMİ olabiliyor
        # (n örnekten biri engellenir, geri kalanı teslim edilir) ve ilk
        # yazımda gerekçe koşulsuz yükseltiliyordu — yani Google'ın ÜRETTİĞİ
        # ve FATURALADIĞI bir video atılıyordu. `max_n=1` olduğu sürece
        # ulaşılamaz bir dal, ama katalog tavanı yükseldiği gün canlı; o gün
        # burada hatırlanacak bir şey olmasın diye şimdi doğru.
        filtre = _filtre_gerekcesi(op)
        try:
            uriler, gomulu = _video_uri(op)
        except ac.ImageError:
            # Şekil TANINMADI. Filtre gerekçesi varsa kullanıcının okumak
            # istediği şey o ("içerik filtresi engelledi"), "generatedSamples
            # yok" değil; gerekçe de yoksa şekil hatası kendi teşhis edici
            # mesajıyla çıkıyor (bkz. `_video_uri`in docstring'i).
            if not filtre:
                raise
            uriler, gomulu = [], []

        out: list[bytes] = list(gomulu)
        for uri in uriler:
            out.append(_indir(client, uri, key, wire_model=m.wire_model))

        if not out:
            # GEREKÇE BURAYA DA GİRİYOR: filtre TÜM örnekleri engellediğinde
            # tek çıkış bu satır ve gerekçesiz bir "video döndürmedi",
            # kullanıcıya prompt'unu neden değiştirmesi gerektiğini
            # söylemeyen bir mesaj olurdu.
            raise ac.ImageError(
                "Veo video döndürmedi"
                + (f": {filtre}" if filtre
                   else ". Prompt'u değiştirip tekrar deneyin."))
        # `gemini_client._uret`in tavanıyla aynı gerekçe: uç istenenden FAZLA
        # örnek döndürebiliyor ve fazlalık sessizce ilerlemiyor, ilerideki bir
        # doğrulamada patlıyor (`ChatMessage.image_ids` `max_length=4`). Eksik
        # teslim değil FAZLASININ atılması — kullanıcı ne istediyse onu alıyor.
        return out[:n]
    finally:
        if owns:
            client.close()


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str,
             duration: int, n: int, *, client=None,
             credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, duration, n, None,
                 client=client, credentials=credentials)


def animate(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
            duration: int, n: int, *, client=None,
            credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — yalnız ilki kullanılıyor."""
    return _uret(m, prompt, size, quality, duration, n, images,
                 client=client, credentials=credentials)
