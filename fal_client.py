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

import azure_client as ac
import catalog
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
