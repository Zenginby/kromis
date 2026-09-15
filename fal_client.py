"""fal.ai kuyruk teli — Wan · PixVerse · Kling (VİDEO).

Deponun BEŞİNCİ tel formatı ve ilk TOPLAYICISI: tek anahtar, çok marka.
Sağlayıcı `providers._VIDEO_ADAPTERS`'e giriyor, `_ADAPTERS`'e GİRMİYOR —
görsel yolunun telde ürettiği baytlar bu turda dokunulmadan kalıyor.

DOSYA BÖLÜNMÜYOR (`azure_mai_client`/`azure_flux_client` gibi değil) ve
gerekçe o bölünmenin ÖLÇÜTÜNDEN geliyor: orada iki AYRI tel formatı vardı
(farklı yol, farklı gövde, farklı hata şekli). fal'da protokol TEK; modeller
arasında değişen yalnız ALAN ADLARI ve onlar `ALANLAR` tablosunda. fal'ın
görsel tarafı geldiği gün `generate`/`edit` BU dosyaya eklenecek.

DOSYA ADI PyPI'daki resmî `fal-client` paketini GÖLGELİYOR. O paket
kullanılmıyor ve kullanılmamalı: BYOK tasarımı yalnız `httpx` istiyor,
`kromis.spec`'in `hiddenimports=[]` değeri yeni bir bağımlılığı analiz
edemez ve Chaquopy kaynak kümesi `include "*.py"` ile kurulu. Biri
`fal-client`ı `requirements.txt`e eklerse kök modülü ONUN önüne geçer ve
hata yalnız o paketi kullanmaya çalışan kodda görünür.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA (Chaquopy; bkz. tests/test_android_packaging.py).

ALAN TABLOSU (`ALANLAR`) bu dosyanın taşıyıcı kararı ve gerekçesi ÖLÇÜLDÜ
(2026-09-14, canlı uç):

  **Beyan edilmemiş alan 422 ÜRETMİYOR — SESSİZCE YOK SAYILIYOR.** Kling'in
  görsel→video ucuna, şemasında hiç olmayan `aspect_ratio` gönderildi ve
  istek şema doğrulamasını GEÇTİ. İlk tasarımın "fal pydantic tabanlı, yani
  fazladan alan 422 demek" varsayımı YANLIŞ çıktı.

Bu, tabloyu gereksiz kılmıyor — TAM TERSİ, daha gerekli kılıyor. 422 gürültülü
bir hatadır ve kendini gösterir; sessiz yok sayım göstermez: kullanıcı 9:16
seçer, tel isteği kabul eder, video 16:9 döner ve hiçbir yerde bir hata
okunmaz. Bu deponun her yerde adlandırdığı SESSİZ SAPMA'nın tam kendisi.

Kling'in görsel→video ucu `aspect_ratio` ve `resolution` alanlarını şemasında
SAYMIYOR (oranı ilk kareden türetiyor), metin ucu ise sayıyor; katalog
`sizes`ı yine beyan ediyor çünkü metin yolunda GERÇEK. Adaptör düzenleme
yolunda onu sessizce değil, TABLOYA BAKARAK düşürüyor.
"""
from __future__ import annotations

import base64
import re
import time

import azure_client as ac
import catalog
import credstore
import providers

# Yüklenen referans karenin MIME'ı. `app._to_png` girdiyi koşulsuz PNG'ye
# çevirdiği için sağlayıcıya sorulacak bir şey yok (`veo_client.PNG_MIME`
# ile aynı olgu).
PNG_MIME = "image/png"

# model id → (metin→video alanları, görsel→video alanları).
#
# KATALOGDA DEĞİL BURADA: katalog "bu model ne yapabiliyor" diyor (yetenek
# beyanı, arayüz onu okuyor), bu tablo "bu uç hangi adı okuyor" (tel biçimi,
# yalnız bu dosya okuyor). İkisini karıştırmak, arayüzün tel ayrıntısına
# bağlanması demekti.
ALANLAR: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "fal-wan-3-0": (
        frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "resolution", "duration"}),
    ),
    "fal-pixverse-c1": (
        frozenset({"prompt", "resolution", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "resolution", "duration"}),
    ),
    # Kling: `resolution` İKİ uçta da YOK (şema o alanı saymıyor; katalogda
    # `quality_hidden=True` ile tek sentetik jeton duruyor) ve `aspect_ratio`
    # yalnız METİN ucunda var.
    "fal-kling-v3-turbo-pro": (
        frozenset({"prompt", "aspect_ratio", "duration"}),
        frozenset({"prompt", "image_url", "duration"}),
    ),
}


def wire_path_for(m: catalog.ImageModel, *, images) -> str:
    """İstek hangi uca gidecek: metin→video mu, görsel→video mu.

    `wire_model_edit` BOŞSA `wire_model`e düşülüyor. Bu düşüş fal'da hiç
    yaşanmamalı (katalog mandalı boş bırakmayı yasaklıyor), ama sözleşme
    deponun geri kalanıyla tutarlı kalsın diye burada: uçları ayrışmamış bir
    sağlayıcı aynı yolu iki kez beyan etmek zorunda değil.
    """
    if images:
        return m.wire_model_edit or m.wire_model
    return m.wire_model


# Kuyruk adresinin taşıdığı segment sayısı — ÖLÇÜLMÜŞ bir sabit.
_UYGULAMA_SEGMENTI = 2


def queue_app_path(wire_path: str) -> str:
    """Kuyruk adreslerinin (`/requests/…`) kullandığı UYGULAMA yolu.

    GÖNDERİM yolu ile YOKLAMA yolu AYNI DEĞİL ve bu 2026-09-14'te canlı uçtan
    ölçüldü:

        gönderim : queue.fal.run/fal-ai/kling-video/v3/turbo/pro/text-to-video
        yoklama  : queue.fal.run/fal-ai/kling-video/requests/<id>/status

    Yani kuyruk adresi tam uç yolunu DEĞİL, yalnız ilk iki segmenti
    (sahip/uygulama) taşıyor; `v3/turbo/pro/text-to-video` düşüyor.

    NEDEN BU KADAR ÖNEMLİ: tam yolla kurulan adres 404 DÖNDÜRMÜYOR, BOŞ GÖVDE
    döndürüyor — yani döngü hatayla değil SESSİZCE ölüyor ve üretim duvar
    saatine kadar bekliyor. Ölçümde PixVerse ve Kling'in izlemesi tam bu
    yüzden 600 saniye boşa gitti; aynı `request_id`ler doğru adresle
    sorgulandığında ZATEN tamamlanmıştı. İptal `PUT`'u da aynı sebeple 405
    dönüyordu.

    Bu, adresin GÖVDEDEN alınmama kararını (bkz. `_durum_url`) değiştirmiyor
    — yalnız tabandan TÜRETME kuralını düzeltiyor.
    """
    parcalar = [p for p in wire_path.strip("/").split("/") if p]
    return "/".join(parcalar[:_UYGULAMA_SEGMENTI])


def _data_uri(png: bytes) -> str:
    """Referans kareyi base64 data URI'ye çevirir.

    YÜKLEME ADIMI YOK ve bu bilinçli: fal'ın dosya deposu ikinci bir kimlik
    yüzeyi, ikinci bir hata dalı ve ömrü sınırlı bir CDN adresi demekti.
    fal data URI'yi açıkça destekliyor; `gemini_client`in `inlineData`
    duruşunun aynısı.
    """
    return f"data:{PNG_MIME};base64," + base64.b64encode(png).decode("ascii")


def build_payload(m: catalog.ImageModel, prompt: str, size: str, quality: str,
                  duration: int, images) -> dict:
    """İstek gövdesi — YALNIZ `ALANLAR`ın izin verdiği anahtarlar.

    Süzgeç `ALANLAR`dan geçiyor, `if model_id == …` zincirinden DEĞİL: zincir
    her yeni modelde büyür ve bir dalı unutmak, beyan edilmemiş alan göndermek
    (422) ya da gerekli alanı düşürmek demekti.

    `images` sıralı [(dosya_adı, png_baytları), ...]; YALNIZ İLKİ kullanılıyor
    (`max_refs=1`). Fazlası `app.animate`in kapısında zaten eleniyor, ama
    burada da kesiliyor — `providers.edit`in ikinci kapı disiplini.
    """
    t2v, i2v = ALANLAR[m.id]
    izin = i2v if images else t2v
    tum = {
        "prompt": prompt,
        "aspect_ratio": size,
        "resolution": quality,
        "duration": duration,
    }
    if images:
        tum["image_url"] = _data_uri(images[0][1])
    return {ad: deger for ad, deger in tum.items() if ad in izin}


def detail_of(body: dict | list | None) -> str:
    """`providers.detail_of`un fal sarmalı — ÜST DÜZEY `detail` de okunuyor.

    `providers.detail_of` iki şekil tanıyor: `{"error": {"message": …}}` ve
    onun `details[]` listesi. fal FastAPI/pydantic tabanlı olduğu için
    doğrulama hatasını ÜST DÜZEYDE taşıyor —

        {"detail": [{"loc": ["body", "duration"], "msg": "…"}]}

    — yani paylaşılan fonksiyon boş dize döndürür ve BÜTÜN 422'ler çıplak bir
    "HTTP 422"ya çöker. Tam olarak FLUX'un `error.details[]` dalının var olma
    sebebi, dördüncü bir şekilde.

    `providers.detail_of` DEĞİŞTİRİLMİYOR: Azure, OpenAI, Gemini ve FLUX'un
    yolları bayt bayt aynı kalmalı ve o fonksiyonun docstring'i hangi şekli
    neden tanıdığını tek tek sayıyor. Sarmal, o listeyi `error.details`
    konumuna TAŞIYIP aynı ayrıştırıcıya veriyor — ikinci bir `{loc, msg}`
    çözümleyicisi yazmamak için.
    """
    paylasilan = providers.detail_of(body)
    if paylasilan:
        return paylasilan
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        return ""
    ust = body.get("detail")
    if isinstance(ust, str):
        return ust
    if isinstance(ust, list):
        return providers.detail_of({"error": {"details": ust}})
    return ""


def map_error(status_code: int, body: dict | list | None) -> str:
    """HTTP durumunu Türkçe mesaja çevirir. ŞEKİL paylaşılıyor, METİN değil.

    `veo_client.map_error`in duruşunun aynısı: "Veo" diyen bir metin fal
    faturasını arayan kullanıcıyı yanlış konsola yönlendirir.

    402 DALI BU DOSYANIN EN ÖNEMLİ YERİ ve `veo_client`in 403/429 dalının
    ikizi: **fal ön ödemeli.** Bakiyesi biten kullanıcıya "anahtarını kontrol
    et" demek, anahtarı GERÇEKTEN doğru olan birini çalışan kurulumunu
    bozmaya davet etmek olurdu.

    429 DA AYRI bir cümle: fal'da yeni hesaplar İKİ eşzamanlı istekle
    başlıyor, yani 429 çoğu zaman bir kota değil bir SIRA sorunu ve cevabı
    "bekle ve tekrar dene".
    """
    detail = detail_of(body)
    ek = f" {detail}" if detail else ""
    if status_code in (401, 403):
        return ("fal.ai yetkilendirme hatası "
                f"({status_code}): anahtar geçersiz ya da bu modele erişimi "
                "yok. Ayarlar'dan yeniden kaydet." + ek)
    if status_code == 402:
        return ("fal.ai bakiyesi yetersiz (402): fal ön ödemeli çalışıyor, "
                "hesabına kredi yükleyip tekrar dene." + ek)
    if status_code == 404:
        return ("fal.ai modeli bulunamadı (404): bu uç yeniden adlandırılmış "
                "ya da kaldırılmış olabilir." + ek)
    if status_code == 429:
        return ("fal.ai eşzamanlı istek sınırı (429): bir önceki üretim hâlâ "
                "sürüyor olabilir. Yeni hesaplarda sınır ikidir; biraz "
                "bekleyip tekrar dene." + ek)
    if providers.is_content_policy(detail):
        return ("fal.ai isteği içerik kurallarıyla reddetti "
                f"(HTTP {status_code}): prompt'u ya da referans görseli "
                "değiştirip tekrar dene." + ek)
    if status_code == 400 and providers.is_invalid_key(detail):
        return ("fal.ai anahtarı geçersiz (400): Ayarlar'dan yeniden "
                "kaydet." + ek)
    if status_code == 422:
        return ("fal.ai isteği reddetti (422): "
                + (detail or "gövdedeki alanlardan biri geçersiz."))
    return f"fal.ai isteği başarısız (HTTP {status_code})." + ek


AUTH_HEADER = "Authorization"
# `Key ` ÖNEKİ ZORUNLU: fal'ın kabul ettiği tek biçim bu. `Bearer` ile
# gönderilen aynı anahtar 401 dönüyor (Replicate'in biçimi o).
AUTH_PREFIX = "Key "

# ÜÇ AYRI ZAMAN AŞIMI — `veo_client`in taşıyıcı kararının aynısı ve aynı
# sebeple: submit/yoklama metadata çağrısı (kısa), indirme megabaytlarca MP4
# (uzun), döngünün tamamı `providers.total_budget` (duvar saati).
#
# SABİTLER KOPYALANDI, `veo_client`ten İMPORT EDİLMEDİ:
# `azure_mai_client`/`azure_flux_client`in `AUTH_HEADER`ı iki kez beyan etme
# gerekçesinin aynısı — biri değişmek zorunda kaldığında öteki dokunulmadan
# kalabiliyor.
POLL_READ_TIMEOUT = 30.0
DOWNLOAD_READ_TIMEOUT = ac.read_timeout_for(1)
POLL_INTERVAL_START = 1.0
POLL_INTERVAL_MAX = 10.0
POLL_BACKOFF = 1.6

MAX_YONLENDIRME = 5
_YONLENDIRME_KODLARI = (301, 302, 303, 307, 308)

DURUM_TAMAM = "COMPLETED"

# `request_id`in KABUL EDİLEN karakterleri. Kuyruk adresleri gövdeden
# alınmıyor, TABANDAN kuruluyor (bkz. `_durum_url`) — ve o kurulumda id tek
# değişken parça. Süzgeç olmasaydı `../../..` taşıyan bir id yolu başka bir
# uca çevirebilirdi.
_REQUEST_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")


def _simdi() -> float:
    """Tek yönlü saat — TEST DİKİŞİ (`veo_client._simdi`nin aynı gerekçesi)."""
    return time.monotonic()


def _bekle(saniye: float) -> None:
    """Yoklama arası uyku — `_simdi` ile aynı gerekçe."""
    time.sleep(saniye)


def _durum_url(taban: str, yol: str, rid: str) -> str:
    """Yoklama adresi — GÜVENİLEN TABANDAN kuruluyor, yanıttan DEĞİL.

    fal'ın belgesi "dönen `status_url`'ü kullan, elle kurma" diyor ve biz
    BİLEREK tersini yapıyoruz. Gerekçe `veo_client._indir`in ölçülmüş
    kararı: gövdeden gelen bir adreste "hedef konağı gövdeyi yazan taraf
    seçiyor". Gövdeden alınan tek şey `request_id` ve o da `_REQUEST_ID`
    süzgecinden geçiyor.

    TAKAS AÇIK: fal kuyruğu bir gün bölgeselleştirirse (BFL'in
    `api.eu`/`api.us` uçlarında olduğu gibi) değişecek tek yer bu iki
    fonksiyon. Belirti net olur: 404.
    """
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}/status"


def _sonuc_url(taban: str, yol: str, rid: str) -> str:
    """`_durum_url`in ikizi; aynı gerekçe."""
    return f"{taban}/{queue_app_path(yol)}/requests/{rid}"


def _istek(client, method: str, url: str, key: str | None, *, read: float,
           json=None):
    """Ortak HTTP + taşıma hatası çevirisi. Yanıtı ÇÖZÜMLEMİYOR.

    `key=None` KİMLİKSİZ istek demek ve tek kullanıcısı `_indir` —
    gerekçesi orada. `veo_client._istek`ten farkı tam olarak bu: orada
    indirme Google konağında anahtarı GÖNDERİYORDU, burada hiç göndermiyor.

    YÖNLENDİRME İZLENMİYOR (`follow_redirects` yok): `_indir` onu ELLE
    izliyor, çünkü httpx yönlendirmede özel başlıkları soymuyor.

    ÜÇ İSTİSNA SARMALANIYOR, YALNIZ `TransportError` DEĞİL: `url` iki
    yerde GÖVDEDEN geliyor (indirme adresi, `Location` başlığı) ve ikisi de
    `httpx.InvalidURL` fırlatabilir — bu sınıf `TransportError`
    HİYERARŞİSİNDE DEĞİL, düz bir `Exception` alt sınıfı, çünkü URL ayrıştırma
    isteğin kendisinden ÖNCE patlıyor. `httpx.DecodingError` de aynı şekilde
    dışarıda kalıyor (bozuk gzip/deflate gövdesi, yine gövdeyi yazan tarafın
    elinde). Sarmalanmazlarsa üçü de `ac.ImageError`in docstring'indeki aynı
    kadere düşer: `app.py`'nin süzgecinden GEÇİP ham 500 olurlar.
    """
    import httpx
    basliklar = {}
    if key:
        basliklar[AUTH_HEADER] = AUTH_PREFIX + key
    if json is not None:
        basliklar["Content-Type"] = "application/json"
    try:
        return client.request(method, url, headers=basliklar, json=json,
                              timeout=ac.request_timeout(read))
    except (httpx.TransportError, httpx.InvalidURL, httpx.DecodingError) as exc:
        # Mesaj `azure_client`tan geliyor, sağlayıcı adı düzeltiliyor:
        # "Azure'a bağlanılamadı" diyen bir metin kullanıcıyı Endpoint alanını
        # kurcalamaya iter (`veo_client._istek`in aynı satırı). `InvalidURL`/
        # `DecodingError` `TimeoutException`/`TransportError` DEĞİL, yani
        # `transport_error_message` bunları genel dala düşürüyor — o da
        # Türkçe ve `ac.ImageError`, ham 500'den her hâlükârda iyi.
        raise ac.ImageError(
            ac.transport_error_message(exc, read).replace("Azure", "fal.ai")) from exc


def _govde(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _video_url(sonuc: dict) -> str:
    """Sonuç gövdesinden MP4 adresi.

    BEKLENMEYEN ŞEKİL ham `KeyError` DEĞİL Türkçe `ImageError` üretiyor:
    `azure_flux_client.decode_images`in kararı — sarmalanmayan bir `KeyError`
    `app.py`'nin süzgecinden geçer ve kullanıcı dakikalarca bekledikten sonra
    yalnızca "Hata (500)" görür. Anahtarlar mesaja giriyor ki şekil
    değiştiğinde teşhis kullanıcının ekranında olsun.
    """
    video = sonuc.get("video") if isinstance(sonuc, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise ac.ImageError(
            "fal.ai video döndürmedi: yanıtta `video.url` yok "
            f"(anahtarlar: {sorted(sonuc) if isinstance(sonuc, dict) else '—'}). "
            "Üretim fal tarafında tamamlanmış ve ücretlendirilmiş olabilir.")
    return str(url)


# İndirme hedefinin uyması gereken şema. fal'ın CDN'i HER ZAMAN https
# veriyor; düz `http` kabul etmek görünürde zararsız ama sessizce bir
# ortadaki-adam saldırısına açık kapı bırakırdı — reddetmenin bedeli yok.
_IZIN_VERILEN_SEMA = "https"


def _guvenli_hedef_mi(url: str) -> bool:
    """İndirme adresi bir SSRF açığına yol açıyor mu — açıyorsa REDDET.

    ANAHTARSIZLIK (bkz. `_indir`'in docstring'i) ile bu kapı AYRI tehditleri
    kapatıyor: biri "bu adrese giden istek kimlik TAŞIMASIN" diyor, bu ise
    "bu adrese HİÇ istek gitmesin". İkisi de gerekli çünkü `url` YANIT
    GÖVDESİNDEN (ya da `Location` başlığından) geliyor — kimliksiz bir GET
    bile hedefi seçen tarafın işine yarar: bu MASAÜSTÜ bir uygulama, yani
    loopback yüzeyi (`http://127.0.0.1:…`) gerçek, bulut meta-veri servisi
    (`169.254.169.254`) de öyle. Gövde bu adreslerden birini yazarsa ve kapı
    yoksa dönen baytlar kullanıcıya "video" diye teslim edilir.

    `veo_client._google_konagi` bir ALLOWLIST taşıyordu çünkü Google'ın
    indirme konağı SABİTTİ (`*.googleapis.com` vb.). Burada DENY-LIST:
    fal'ın CDN konağı sabit değil (`v3.fal.media` gibi adlar sürüm/bölgeyle
    değişebiliyor), bir allowlist yanlış konakları da reddedip döngüyü
    sessizce kırardı. Yalnız özel/yerel aralıklar eleniyor, geri kalan her
    şeye izin veriliyor.

    AD ÇÖZÜMLEMESİ YAPILMIYOR (DNS'e HİÇ çıkılmıyor): bir sorgu hem yan
    etkili hem de TOCTOU açığı taşır (çözümleme ile asıl istek arasında ad
    başka bir IP'ye işaret edebilir). Yalnız adresin METNİ denetleniyor: host
    bir literal IP ise `ipaddress` onu private/loopback/link-local diye
    işaretliyor; `ipaddress` REDDEDERSE de otomatik "sıradan alan adı, izin
    ver" DENMİYOR — `ipaddress.ip_address()` yalnız NOKTALI-ONDALIK biçimi
    tanıyor, alternatif IPv4 yazımlarını (bkz. `_alan_adi_mi`) da `ValueError`
    ile reddediyor, yani o dal IP OLMAYANLA IP'nin TANINMAYAN YAZIMINI
    ayıramıyor. İkinci bir denetim (`_alan_adi_mi`) bu ikisini ayırıyor.
    """
    import ipaddress
    from urllib.parse import urlparse

    parcalar = urlparse(url)
    if parcalar.scheme != _IZIN_VERILEN_SEMA:
        return False
    konak = (parcalar.hostname or "").lower()
    if not konak or konak == "localhost" or konak.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(konak)
    except ValueError:
        return _alan_adi_mi(konak)
    return not (ip.is_loopback or ip.is_link_local or ip.is_private
                or ip.is_unspecified or ip.is_reserved or ip.is_multicast)


def _alan_adi_mi(konak: str) -> bool:
    """`ipaddress.ip_address()`in reddettiği bir host GERÇEKTEN bir alan adı
    mı — yoksa `ipaddress`in TANIMADIĞI alternatif bir IPv4 YAZIMI mı.

    ÖLÇÜLMÜŞ AÇIK (2026-09-15, ikinci inceleme turu): `ipaddress.ip_address()`
    yalnız noktalı-ondalık (`a.b.c.d`) biçimi tanıyor;

        https://2130706433/x       (decimal: 127.0.0.1'in tek sayısı)
        https://0x7f.1/x           (hex/ondalık karışık)
        https://127.1/x            (kısaltılmış — eksik oktet)
        https://017700000001/x     (oktal)

    dördü de birer IP LİTERALİ ama `ipaddress` hepsini `ValueError` ile
    reddediyor. İlk yazım bu reddi "sıradan bir alan adı" sanıp KAPIDAN
    GEÇİRİYORDU. Bu bir teorik açık değil: bu depo macOS ve Android'e de
    paketleniyor (`build.sh`, `kromis.spec`, Chaquopy) ve glibc'in
    `getaddrinfo`si bu dört biçimi de `127.0.0.1`'e ÇÖZÜYOR — Windows'ta
    `socket.getaddrinfo`nun aynısını çözememesi savunma DEĞİL, platforma
    bağlı bir baypas hâlâ baypas.

    KURAL: son etiket (TLD) bir HARFLE başlamalı. Sayısal biçimlerin
    DÖRDÜ de bunu ihlal ediyor — `2130706433` ve `017700000001` TEK etiket ve
    tamamı rakam; `0x7f.1` ve `127.1`'in son etiketi `1`. `v3.fal.media`,
    `fal.media`, `xn--...` (IDNA) gibi gerçek alan adları TLD'si harfle
    başladığı için geçiyor.

    KÖK NOKTA (`v3.fal.media.`) doğrulamadan ÖNCE soyuluyor: DNS'te geçerli
    bir biçim, onu reddetmek meşru bir adresi kırardı.
    """
    konak = konak.rstrip(".")
    if not konak:
        return False
    son_etiket = konak.rsplit(".", 1)[-1]
    return son_etiket[:1].isalpha()


def _indir(client, url: str) -> bytes:
    """MP4'ü indirir — ANAHTARSIZ, HEDEFİ DENETLENMİŞ ve yönlendirmeyi ELLE
    izleyerek.

    ANAHTARSIZ olması bu dosyanın ikinci güvenlik kararı: `url` YANIT
    GÖVDESİNDEN geliyor, yani hedef konağı gövdeyi yazan taraf seçiyor.
    fal'ın çıktı adresi genel erişime açık bir CDN, yani kimlik zaten
    gereksiz — göndermemek, sızma yolunu tamamen kapatıyor.
    (`veo_client._indir` Google konağında anahtarı gönderiyordu ve bu yüzden
    bir konak allowlist'i taşımak zorundaydı; burada ona gerek yok.)

    HEDEF de AYRICA denetleniyor (`_guvenli_hedef_mi`) ve bu BAŞKA bir karar:
    anahtarsızlık SIZINTIYI kapatıyor, hedef denetimi SSRF'i — `url` gövdeden
    gelmeseydi ikisi de gereksizdi, ama geldiği için ikisi de gerekli; biri
    ötekinin yerine geçmiyor. Denetim hem İLK adreste hem her `urljoin`
    SONRASINDA çalışıyor: yönlendirme zinciri de ilk adres kadar güvenilmez,
    aksi hâlde kapı yalnızca girişte durur, ikinci atlayışta atlanırdı.
    """
    from urllib.parse import urljoin

    def _kapiya_sor(adres: str) -> str:
        if not _guvenli_hedef_mi(adres):
            raise ac.ImageError(
                f"fal.ai videosu indirilemedi: hedef adres ({adres}) yerel "
                "ya da özel bir ağa işaret ediyor; SSRF riski nedeniyle "
                "reddedildi.")
        return adres

    url = _kapiya_sor(url)
    # +1: İLK istek bir yönlendirme DEĞİL, döngü `MAX_YONLENDIRME` kadar
    # yönlendirmeyi İZLESİN diye bir fazla dönüyor (`veo_client._indir`in
    # aynı deseni) — aksi hâlde tavan mesajı "5" derken gerçekte yalnızca 4
    # yönlendirme izlenmiş olurdu.
    for _ in range(MAX_YONLENDIRME + 1):
        resp = _istek(client, "GET", url, None, read=DOWNLOAD_READ_TIMEOUT)
        if resp.status_code == 200:
            return resp.content
        if resp.status_code not in _YONLENDIRME_KODLARI:
            raise ac.ImageError(
                f"fal.ai videosu indirilemedi (HTTP {resp.status_code}).")
        hedef = resp.headers.get("location")
        if not hedef:
            raise ac.ImageError(
                f"fal.ai videosu indirilemedi: {resp.status_code} "
                "yönlendirmesi adres taşımıyor.")
        # GÖRECELİ adres de geçerli (RFC 7231); `urljoin` mutlaklaştırıyor.
        url = _kapiya_sor(urljoin(url, hedef))
    raise ac.ImageError(
        f"fal.ai videosu indirilemedi: {MAX_YONLENDIRME} yönlendirmeden "
        "sonra hâlâ bitmedi.")


def _timeout_message(gecen: float, butce: float) -> str:
    """`veo_client._timeout_message`in ikizi ve aynı ÜCRET UYARISIYLA: iş fal
    tarafında tamamlanmış olabilir ve kullanıcı 'hata aldım, demek ki
    ücretlenmedim' diye düşünmemeli."""
    return (f"fal.ai üretimi {gecen:.0f} saniyede bitmedi (tavan "
            f"{butce:.0f} sn). Süreyi ya da çözünürlüğü düşürüp tekrar dene. "
            "Not: üretim fal tarafında tamamlanmış ve ücretlendirilmiş "
            "olabilir, yalnızca sonuç bu tarafa ulaşmadı.")


def _uret(m: catalog.ImageModel, prompt: str, size: str, quality: str,
          duration: int, n: int, images, *, client, credentials) -> list[bytes]:
    """`generate` ve `animate`in PAYLAŞILAN gövdesi — tek fark `images`.

    DÖRT ADIM: submit → `COMPLETED` olana kadar yokla → sonucu al → indir.
    `veo_client._uret`in üç adımından farkı, fal'ın sonucu DURUM yanıtında
    değil AYRI bir adreste vermesi.

    KİMLİK TEMBEL çözülüyor (`providers._azure_generate`in belgelenmiş
    kuralı). SON TARİH duvar saatiyle ölçülüyor, yoklama SAYISIYLA değil.

    SON TARİH BİR KEZ, BURADA hesaplanıyor (`son_tarih`) ve HER tura AYNI
    mutlak an olarak geçiyor — tur başına SIFIRLANMIYOR. `providers.
    total_budget` zaten `n` ile ölçekliyor ve docstring'i "DÖNGÜNÜN duvar
    saati tavanı" diyor, yani turların TOPLAMI: saat her turda sıfırlansaydı
    gerçek tavan `n · butce` olurdu (bugün `max_n=1` olduğu için görünmez,
    ama `total_budget`ın n-ile-çarpma kararını anlamsızlaştırırdı).

    DÖNGÜ adet başına ayrı istek atıyor (`images_per_request=1`). Bugün
    `max_n=1` olduğu için tek tur, ama yapısı tavan yükseldiği gün hazır.
    """
    key, base_url = (credentials if credentials is not None
                     else credstore.resolve(m.credential))
    taban = base_url.rstrip("/")
    yol = wire_path_for(m, images=images).strip("/")
    butce = providers.total_budget(m, n)
    son_tarih = _simdi() + butce
    payload = build_payload(m, prompt, size, quality, duration, images)

    import httpx
    owns = client is None
    if owns:
        client = httpx.Client()
    try:
        out: list[bytes] = []
        while len(out) < n:
            out.append(_tek_uretim(client, key, taban, yol, payload, butce,
                                   son_tarih))
        return out[:n]
    finally:
        if owns:
            client.close()


def _tek_uretim(client, key: str, taban: str, yol: str, payload: dict,
                butce: float, son_tarih: float) -> bytes:
    """Tek bir kuyruk turu: submit → yokla → sonuç → indir.

    `son_tarih` ÇAĞIRANDAN (`_uret`) geliyor ve TÜM turlarda SABİT — bu
    fonksiyon kendi saatini sıfırlamıyor (bkz. `_uret`'in gerekçesi). `butce`
    yalnız zaman aşımı MESAJINDA "kaç saniyede bitmedi" diye göstermek için
    taşınıyor, son tarih hesabına bir daha girmiyor.
    """
    # ── 1. Submit ────────────────────────────────────────────────────────
    resp = _istek(client, "POST", f"{taban}/{yol}", key,
                  read=POLL_READ_TIMEOUT, json=payload)
    if resp.status_code != 200:
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    kuyruk = _govde(resp) or {}
    rid = str(kuyruk.get("request_id") or "")
    if not _REQUEST_ID.match(rid):
        raise ac.ImageError(
            "fal.ai işi başlatılamadı: yanıttaki `request_id` yok ya da "
            f"tanınmayan biçimde (anahtarlar: {sorted(kuyruk)}).")

    # ── 2. Yoklama ───────────────────────────────────────────────────────
    # Döngü UYKUYLA DEĞİL KONTROLLE başlıyor: kısa bir iş ilk yanıtta
    # `COMPLETED` olabilir ve uykuyla başlamak hazır sonucu bekletmek olurdu
    # (`veo_client`in aynı notu).
    durum_url = _durum_url(taban, yol, rid)
    aralik = POLL_INTERVAL_START
    durum = ""
    while durum != DURUM_TAMAM:
        kalan = son_tarih - _simdi()
        if kalan <= 0:
            raise ac.ImageError(_timeout_message(butce - kalan, butce))
        resp = _istek(client, "GET", durum_url, key, read=POLL_READ_TIMEOUT)
        if resp.status_code != 200:
            raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
        govde = _govde(resp) or {}
        durum = str(govde.get("status") or "")
        # TANINMAYAN ya da eksik `status` HATA sayılmıyor, "devam ediyor"
        # sayılıyor: fal ileride `IN_QUEUE`/`IN_PROGRESS`/`COMPLETED` dışında
        # bir ara durum eklerse döngü onu es geçip yoklamaya devam ediyor —
        # tek ÇIKIŞ koşulu `COMPLETED`, tek HATA koşulu HTTP durumu ya da son
        # tarih. Tek risk: iş gerçekten düşüp fal onu `COMPLETED` DIŞINDA bir
        # durum adıyla (`FAILED` gibi) işaretlerse — belgede böyle bir durum
        # görülmedi, o hâlde bu dal son tarih dolana kadar boşa yoklar.
        if durum == DURUM_TAMAM:
            break
        _bekle(min(aralik, max(0.0, kalan)))
        aralik = min(aralik * POLL_BACKOFF, POLL_INTERVAL_MAX)

    # SON TARİH yalnız SUBMIT + YOKLAMA'yı kapsıyor: `COMPLETED` görüldükten
    # sonraki SONUÇ ve İNDİRME adımları bütçeye bir daha sokulmuyor, kendi
    # OKUMA zaman aşımlarıyla sınırlı kalıyor (`POLL_READ_TIMEOUT`,
    # `DOWNLOAD_READ_TIMEOUT` × yönlendirme tavanı). Bilinçli sadeleştirme:
    # iş zaten `COMPLETED`, yani "vazgeçme" kararı anlamsızlaşıyor — kalan
    # yolun tek riski yavaş bir indirme ve o da kendi tavanıyla sınırlı (en
    # kötü hâl ~1110 sn: 30 sn sonuç + `MAX_YONLENDIRME + 1` = 6 indirme
    # denemesinin her biri en çok `DOWNLOAD_READ_TIMEOUT` = 180 sn).
    #
    # ── 3. Sonuç ─────────────────────────────────────────────────────────
    resp = _istek(client, "GET", _sonuc_url(taban, yol, rid), key,
                  read=POLL_READ_TIMEOUT)
    if resp.status_code != 200:
        raise ac.ImageError(map_error(resp.status_code, _govde(resp)))
    sonuc = _govde(resp) or {}
    # `COMPLETED` BAŞARI DEMEK DEĞİL: fal işin BİTTİĞİNİ söylüyor, iyi
    # bittiğini değil — düşen iş de `COMPLETED` olup gövdesinde `error`
    # taşıyabiliyor. Denetim KOŞULSUZ: `veo_client._operation_hatasi`nin
    # "iş düştüyse sonuç geçersiz, gövdede bir video görünse bile teslim
    # edilmemeli" kararının aynısı — bayat/kısmi bir video, parayı zaten
    # harcamış DÜŞMÜŞ bir işin üstünü örtmemeli.
    #
    # `map_error` BURADA ÇAĞRILMIYOR: onun sözleşmesi bir HTTP DURUM KODUNU
    # çevirmek ve buradaki yanıt 200 — `map_error(200, …)` genel "istek
    # başarısız (HTTP 200)" dalına düşer, yani kullanıcıya anlamsız bir
    # cümle gösterirdi. Gerekçe doğrudan yazılıyor.
    hata = detail_of(sonuc)
    if hata:
        raise ac.ImageError(f"fal.ai video üretmedi: {hata}")

    # ── 4. İndirme ───────────────────────────────────────────────────────
    return _indir(client, _video_url(sonuc))


def generate(m: catalog.ImageModel, prompt: str, size: str, quality: str,
             duration: int, n: int, *, client=None,
             credentials=None) -> list[bytes]:
    return _uret(m, prompt, size, quality, duration, n, None,
                 client=client, credentials=credentials)


def animate(m: catalog.ImageModel, prompt: str, images, size: str, quality: str,
            duration: int, n: int, *, last_frame=None, client=None,
            credentials=None) -> list[bytes]:
    """`images`: sıralı [(dosya_adı, png_baytları), ...] — yalnız ilki kullanılıyor.

    `last_frame` SÖZLEŞMEDE VAR ama bu sağlayıcıda DESTEKLENMİYOR: üç modelin
    hiçbirinin i2v şemasında `tail_image_url` yok. Kapı `providers.animate_video`'da
    (`supports_last_frame=False`) ve buradaki iddia onun İKİNCİ kapısı —
    `providers.edit`in ikinci kapı disiplininin aynısı.
    """
    if last_frame is not None:
        raise ac.ImageError(f"{m.label} bitiş görseli almıyor.")
    return _uret(m, prompt, size, quality, duration, n, images,
                 client=client, credentials=credentials)
