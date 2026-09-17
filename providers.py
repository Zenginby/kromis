# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Görsel sağlayıcı sevk memuru: model tanımı → o modeli konuşan adaptör.

Bu dosya İKİ şey yapıyor ve üçüncüsünü BİLEREK yapmıyor:
  • `catalog.ImageModel` → adaptör eşlemesi ve çağrının kendisi,
  • zaman aşımı politikası (adet başına ayrı istek atan sağlayıcı için),
  • ve tel formatına HİÇ karışmıyor — o her adaptörün özel işi.

Üçüncüsü tasarımın taşıyıcı kararı: adaptörler ÇÖZÜLMÜŞ PNG BAYTLARI
döndürüyor. Böylece `azure_client.decode_images`'ın koşulsuz `data[].b64_json`
varsayımı Azure'ın özel meselesi olarak kalıyor; Gemini'nin
`candidates[].content.parts[].inlineData` şekli Gemini'nin; ve ileride URL
döndüren bir sağlayıcı (fal, Replicate) kendi `GET`'ini yapıp bayt döndürüyor.
Çağıran taraf aradaki farkı HİÇ öğrenmiyor.

ADAPTÖR SÖZLEŞMESİ — her adaptör modülü şu iki adı dışa veriyor:

    generate(m, prompt, size, quality, n, *, client=None, credentials=None) -> list[bytes]
    edit(m, prompt, images, size, quality, n, *, client=None, credentials=None) -> list[bytes]

`images`: sıralı [(dosya_adı, png_baytları), ...] — ilk görsel ana referans.
Biçimden bağımsız BİLEREK: Azure bunu multipart alanlarına, Gemini base64
`inlineData` bloklarına çeviriyor. `azure_client.build_image_files` bu yüzden
sözleşmeye HİÇ girmiyor.

`client=` / `credentials=` anahtarları KORUNUYOR: bunlar mevcut test koşumu
(tests/test_azure_client_http.py'deki FakeClient) ve her yeni adaptör aynı
dikişi bedavaya alıyor, testleri de bugünkülere benziyor.

VİDEO SÖZLEŞMESİ AYRI ve iki eksen bilerek AYRIŞTIRILDI:

    generate_video(model_id, prompt, size, quality, duration, n, …) -> list[bytes]
    animate_video(model_id, prompt, images, size, quality, duration, n, …) -> list[bytes]

Tek bir `generate`e katlanmadı çünkü katlamanın bedeli GÖRSEL yolunda
ödenecekti: `duration` görsel adaptörlerin üçünün imzasına da girer, üçü de
onu yok saymak zorunda kalır ve `azure_client`ın "baytları değişmemiş
fonksiyon" güvencesi (bkz. `_azure_generate`in yorumu) kırılırdı. Ayrı iki
masa, görsel yolunu BAYT BAYT dokunulmadan bırakıyor.

`_VIDEO_ADAPTERS` de `_ADAPTERS`ten ayrı bir tablo ve aynı gerekçenin
devamı: bir sağlayıcı iki tabloda birden bulunabiliyor (Gemini bugün tam
olarak öyle — görselde `gemini_client`, videoda `veo_client`) ve tek tabloda
bu "sağlayıcı → dörtlü demet" olurdu, yani görsel adaptörü olmayan bir video
sağlayıcısı iki boş yuva taşırdı.

Sınıf DEĞİL, fonksiyon modülü: bu depoda hiçbir yerde servis sınıfı yok.

Adaptörler modül düzeyinde STATİK import ediliyor, `importlib` ile DEĞİL.
Sebep: `kromis.spec`'in `hiddenimports=[]` değeri PyInstaller'ın
statik analizine dayanıyor ve o dosyanın 50 satırlık yorumu bunu ölçülmüş bir
değişmez sayıyor. Dinamik import o analizden kaçar ve paketlenmiş uygulamada
adaptör bulunamaz.

Bu dosya kökte düz duruyor ama artık ZORUNDA DEĞİL (2026-09-16). Eski kısıt
Android'in Chaquopy kaynak kümesinden geliyordu (`include "*.py"` → alt paket
APK'ya hiç girmez, hata yalnız telefonda görünür). Masaüstü ve Android
paketleri v0.23.1'de dondurulduğu için o kısıt ve mandalı
(`tests/test_android_packaging.py`) kaldırıldı; bir `providers/` paketi
bundan sonra serbest — gerekçe ve sıra: docs/faz0-web-first.md.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

import azure_client as ac
import catalog
import credstore
import etiket
import i18n


def _azure_generate(m, prompt, size, quality, n, *, client=None, credentials=None):
    """Azure yolu: `azure_client`'a AYNEN devrediliyor.

    Model tanımı burada DÜŞÜRÜLÜYOR ve bu bilinçli. `azure_client.py` bu adımda
    hiç düzenlenmiyor — `build_payload`'ın ürettiği tam sözlük
    tests/test_azure_client.py'de donmuş durumda ve dosyanın her yorumu Azure'a
    özgü. Yani varsayılan yolun tel üzerindeki baytları DEĞİŞMEMİŞ bir fonksiyon
    üretmeye devam ediyor: "kayıtlı Azure kullanıcısı için sıfır davranış
    değişikliği" güvencesinin somut karşılığı bu.

    KİMLİK BURADA ÇÖZÜLMÜYOR, `credentials=None` aynen geçiliyor. İlk yazımda
    burada `credstore.resolve(...)` vardı ve 104 test birden düştü: rota
    testlerinin tamamı `ac.generate`'i monkeypatch'liyor ve kimliği HİÇ
    yapılandırmıyor — çünkü bugünkü `ac.generate` kimliği kendi İÇİNDE, tembel
    biçimde çözüyor. Erken çözüm o tembelliği bozuyor ve stub'lanmış bir
    çağrının bile gerçek bir kimlik istemesine yol açıyordu.
    Testlerin ölçtüğü şey doğruydu: çözümü öne almak davranış DEĞİŞİKLİĞİ.
    Web'de (Faz 1 / 7) `ac.generate` `credentials=None` görünce isteğin
    sözlüğüne bakıyor (`kimlik_baglami`, rota `kimlik.KIMLIKLER` ile bağlar);
    tembellik korunuyor, dosya yolu yalnız bağlamsız dondurulmuş kabukta.

    Yeni adaptörler kendi kimliğini `credstore.resolve(m.credential)` ile
    çözüyor — aynı tembellikle, yani kendi istek fonksiyonlarının içinde;
    `credstore` da açık sözlük verilmediğinde isteğin bağlamına bakıyor.
    """
    return ac.generate(prompt, size, quality, n, client=client, credentials=credentials)


def _azure_edit(m, prompt, images, size, quality, n, *, client=None, credentials=None):
    return ac.edit(prompt, images, size, quality, n, client=client, credentials=credentials)


# provider → (generate, edit). Yeni bir adaptör buraya girmediği sürece
# kataloğa eklenen model çalışma anında "bilinmeyen sağlayıcı" hatası verir —
# sessizce Azure'a düşmez. Mandal: tests/test_providers.py.
def _openai_adapter():
    """Geç bağlama: `openai_client` bu modülü import ediyor (paylaşılan zaman
    aşımı ve hata gövdesi çözümlemesi için), yani modül düzeyinde import etmek
    DÖNGÜ olurdu.

    `importlib` KULLANILMIYOR — düz `import` ifadesi, yalnız fonksiyonun
    içinde. PyInstaller'ın statik analizi fonksiyon içindeki import'u da
    görüyor (`azure_client`'ın httpx'i tam olarak böyle alıyor), yani
    `hiddenimports=[]` korunuyor.
    """
    import openai_client
    return (openai_client.generate, openai_client.edit)


def _gemini_adapter():
    """`_openai_adapter`ın aynı gerekçesi: `gemini_client` bu modülü import
    ediyor (`read_timeout_for` ve `detail_of` için), yani modül düzeyinde
    import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız fonksiyon içinde —
    PyInstaller'ın statik analizi onu da görüyor."""
    import gemini_client
    return (gemini_client.generate, gemini_client.edit)


def _veo_adapter():
    """`_gemini_adapter`ın aynı gerekçesi: `veo_client` bu modülü import ediyor
    (`total_budget`, `detail_of` ve iki paylaşılan yüklem için), yani modül
    düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız
    fonksiyon içinde — PyInstaller'ın statik analizi onu da görüyor, yani
    `hiddenimports=[]` korunuyor."""
    import veo_client
    return (veo_client.generate, veo_client.animate)


def _fal_adapter():
    """`_veo_adapter`ın aynı gerekçesi: `fal_client` bu modülü import ediyor
    (`total_budget`, `detail_of` ve iki paylaşılan yüklem için), yani modül
    düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız
    fonksiyon içinde — PyInstaller'ın statik analizi onu da görüyor, yani
    `hiddenimports=[]` korunuyor."""
    import fal_client
    return (fal_client.generate, fal_client.animate)


def _mai_adapter():
    """`_gemini_adapter`ın aynı gerekçesi: `azure_mai_client` bu modülü import
    ediyor (`read_timeout_for`, `detail_of`, `is_content_policy` için), yani
    modül düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız
    fonksiyon içinde — PyInstaller'ın statik analizi onu da görüyor, yani
    `hiddenimports=[]` korunuyor."""
    import azure_mai_client
    return (azure_mai_client.generate, azure_mai_client.edit)


def _flux_adapter():
    """`_mai_adapter`ın aynı gerekçesi: `azure_flux_client` bu modülü import
    ediyor (`read_timeout_for` ve `detail_of` için), yani modül düzeyinde
    import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız fonksiyon içinde —
    PyInstaller'ın statik analizi onu da görüyor."""
    import azure_flux_client
    return (azure_flux_client.generate, azure_flux_client.edit)


_ADAPTERS: dict[str, tuple | Callable[[], tuple]] = {
    "azure": (_azure_generate, _azure_edit),
    # Değer bir ÇAĞRILABİLİR döndürücü olabiliyor (döngüyü kıran geç bağlama);
    # `_pair` ikisini de karşılıyor.
    "openai": _openai_adapter,
    "gemini": _gemini_adapter,
    # Azure AI Foundry'nin İKİ AYRI teli, TEK anahtar altında: MAI ile FLUX
    # aynı hostta ve aynı `api-key` ile çalışıyor ama gövdeleri, yolları ve
    # hata şekilleri farklı. Tek bir `azure-foundry` anahtarı olsaydı iki tel
    # formatı bir modülde yaşardı, hata eşlemesi bulanıklaşırdı ve
    # `PROVIDER_LOGOS` tek anahtara düşerdi — oysa üretici GERÇEKTEN iki
    # (Microsoft ve Black Forest Labs).
    "azure-mai": _mai_adapter,
    "azure-flux": _flux_adapter,
}

# provider → (generate_video, animate_video). İKİ anahtar: doğrudan
# `gemini` (Veo) ve TOPLAYICI `fal` (Wan · PixVerse · Kling). Ölü uçların
# gerekçesi `catalog.VIDEO_MODELS`in başlığında duruyor — OpenAI'nin Videos
# API'si kapanıyor, Azure AI Foundry'de video barındırılmıyor, Anthropic'in
# video ucu hiç yok.
#
# `fal` BU TABLODA VAR, `_ADAPTERS`te YOK: bu turun kapsamı video ve görsel
# yolunun telde ürettiği baytlar dokunulmadan kalıyor. Bu asimetri tam
# olarak iki tablonun ayrı olma gerekçesi (bkz. dosya başlığı).
_VIDEO_ADAPTERS: dict[str, tuple | Callable[[], tuple]] = {
    "gemini": _veo_adapter,
    "fal": _fal_adapter,
}


def _pair(provider: str) -> tuple:
    """Adaptör çiftini çözer: ya doğrudan demet, ya geç bağlayan fonksiyon."""
    girdi = _ADAPTERS[provider]
    return girdi() if callable(girdi) else girdi


def _video_pair(provider: str) -> tuple:
    """`_pair`in video tablosundaki ikizi."""
    girdi = _VIDEO_ADAPTERS[provider]
    return girdi() if callable(girdi) else girdi


def adapter_ids() -> frozenset[str]:
    return frozenset(_ADAPTERS)


def video_adapter_ids() -> frozenset[str]:
    return frozenset(_VIDEO_ADAPTERS)


def _resolve(model_id: str) -> catalog.ImageModel:
    m = catalog.image_model(model_id)
    if m is None:
        # Kullanıcıya gösterilebilir Türkçe hata: bayat bir istemci artık var
        # olmayan bir modeli isteyebilir ve bunun cevabı ham 500 olmamalı.
        raise ac.ImageError(f"Bilinmeyen model: {model_id}")
    if m.provider not in _ADAPTERS:
        raise ac.ImageError(
            i18n.t("err.no_image_adapter", None, model=etiket.label_of(m),
                   saglayici=m.provider))
    return m


def _resolve_video(model_id: str) -> catalog.ImageModel:
    """`_resolve`ın video tablosundaki ikizi; mesajlar da onun kalıbında.

    `catalog.video_model`a bakıyor, `image_model`a DEĞİL — ve bu ayrım
    sessiz sapmayı kapatan yer: bir görsel modelinin id'siyle `/api/video`ya
    gelen istek burada "bilinmeyen video modeli" alıyor, senkron bir görsel
    adaptörüne 7 dakikalık bir video isteği olarak DÜŞMÜYOR.
    """
    m = catalog.video_model(model_id)
    if m is None:
        raise ac.ImageError(f"Bilinmeyen video modeli: {model_id}")
    if m.provider not in _VIDEO_ADAPTERS:
        raise ac.ImageError(
            i18n.t("err.no_video_adapter", None, model=etiket.label_of(m),
                   saglayici=m.provider))
    return m


def read_timeout_for(m: catalog.ImageModel, n: int) -> float:
    """TEK isteğin okuma süresi.

    `azure_client.read_timeout_for`'un formülü (180 + 120·(n-1)) açık bir
    varsayıma dayanıyor ve kendi yorumunda yazılı: `build_payload` `n`'i gövdeye
    koyuyor, yani 4 görsel TEK POST'ta üretiliyor. Adet başına ayrı istek atan
    bir sağlayıcıda o varsayım YANLIŞ — her istek bir görsel döndürüyor, süre
    adetle büyümüyor. Büyüyen şey döngünün TOPLAMI (bkz. total_budget).

    Karışsa n=4'te her isteğe 540 saniye verilirdi: 36 dakikalık en kötü hâl.
    """
    if m.poll_timeout:
        return m.poll_timeout
    tek_istekteki = n if m.images_per_request > 1 else 1
    return ac.read_timeout_for(tek_istekteki)


def total_budget(m: catalog.ImageModel, n: int) -> float:
    """Döngünün duvar saati tavanı — kaç istek atılacağı ile ölçeklenen taraf."""
    tur = 1 if m.images_per_request > 1 else n
    return read_timeout_for(m, n) * tur


# FLUX'un 422'si mesajı DEĞİL bir LİSTE taşıyor: `error.details[]` içinde
# `{"loc": [...], "msg": "..."}` maddeleri. Mevcut hiçbir çözümleyici bunu
# tanımıyordu ve `error.message` boş olduğu için BÜTÜN 422'ler çıplak bir
# "HTTP 422"ya çöküyordu — yani kullanıcı hangi alanın yanlış olduğunu hiçbir
# yerde okumuyordu. Tam olarak `detail_of`un Gemini'nin tek öğelik dizisi için
# var olma sebebi, üçüncü bir şekilde.
#
# YALNIZ LİSTE OKUNUYOR: MAI'nin gövdesinde de `details` var ama o bir DİZE ve
# mesaj zaten `error.message`da — o yolun baytları değişmiyor.
#
# ÜÇ MADDE TAVANI: doğrulayıcı onlarca madde döndürebiliyor ve hepsini tek
# satıra dizmek kullanıcıya okunamayan bir duvar gösterirdi. Kesme SESSİZ
# SAPMA değil çünkü ilk madde neredeyse her zaman asıl kusuru söylüyor;
# tamamı zaten `errlog`da duruyor.
_DETAIL_LIMIT = 3


def _madde_metni(madde: dict) -> str:
    """Tek bir `details[]` maddesini `"body.width: must be …"` biçimine indirir.

    `msg` yoksa `message` deneniyor: iki ad da canlıda görülüyor ve hangisinin
    geldiğine göre boş dönmek, sebebi hiç göstermemek olurdu.
    """
    loc = madde.get("loc")
    yer = ".".join(str(p) for p in loc) if isinstance(loc, list) else ""
    msg = str(madde.get("msg") or madde.get("message") or "")
    if yer and msg:
        return f"{yer}: {msg}"
    return msg or yer


def _details_metni(err: dict) -> str:
    ayrintilar = err.get("details")
    if not isinstance(ayrintilar, list):
        return ""
    parcalar = []
    for madde in ayrintilar[:_DETAIL_LIMIT]:
        if not isinstance(madde, dict):
            continue
        metin = _madde_metni(madde)
        if metin:
            parcalar.append(metin)
    return "; ".join(parcalar)


def detail_of(body: dict | list | None) -> str:
    """Sağlayıcı hata gövdesinden kullanıcıya gösterilebilir açıklama.

    ŞEKİL paylaşılıyor, MESAJ paylaşılmıyor: `{"error": {"message": …}}`
    biçimini Azure, OpenAI, Gemini ve Anthropic'in dördü de kullanıyor, ama
    Türkçe metinler sağlayıcıya özgü kalmak zorunda (`chat_client.map_error`'ın
    404 metni Azure AI Foundry'nin dağıtım alanından söz ediyor — o metni
    Gemini'ye göstermek kullanıcıyı olmayan bir forma yönlendirir).

    TEK ÖĞELİK DİZİ DE AÇILIYOR ve bu bir hoşgörü değil ÖLÇÜLMÜŞ bir olgu:
    `generativelanguage.googleapis.com` hata gövdesini nesne olarak DEĞİL,
    tek öğelik bir JSON DİZİSİ olarak döndürüyor —

        [{"error": {"code": 400, "message": "API key not valid. …",
                    "status": "INVALID_ARGUMENT"}}]

    Gerçek uca yapılan çağrıyla doğrulandı (görsel tarafı
    `/v1beta/interactions`, sohbet tarafı `/v1beta/openai/chat/completions`;
    ikisi de aynı sarmalı kullanıyor). Dizi açılmazsa `isinstance(body, dict)`
    kapısı boş dize döndürüyor ve BÜTÜN Gemini hataları çıplak bir
    "HTTP 400"a çöküyor: `gemini_client.map_error`'ın 400'ü ikiye ayıran dalı
    (geçersiz anahtar ↔ desteklenmeyen jeton) hiç tetiklenmiyor, yani anahtarı
    doğru olan kullanıcı sebebi hiçbir yerde okumuyor.

    ÇOK ÖĞELİ dizi BİLEREK açılmıyor: ilkini seçmek, geri kalanını sessizce
    yutmak olurdu. Azure ve OpenAI düz nesne döndürüyor, o yüzden onların yolu
    bayt bayt aynı kalıyor.

    ÜÇÜNCÜ ŞEKİL — `error.details[]`: FLUX'un 422'si mesaj yerine bir LİSTE
    döndürüyor ve o liste okunmazsa bütün 422'ler çıplak bir "HTTP 422"ya
    çöküyor. Ayrıntı `_details_metni`de; Azure, OpenAI ve MAI'nin düz nesne
    yolu bayt bayt aynı kalıyor (onların `details`i ya yok ya bir dize).
    """
    # `list` kapısı `dict` kapısından ÖNCE: aksi hâlde dizi zaten elenmiş olur.
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        mesaj = str(err.get("message", ""))
        # Liste MESAJI EZMİYOR, TAMAMLIYOR: ikisi de dolu gelebiliyor ve
        # mesajı düşürmek asıl cümleyi çöpe atmak olurdu.
        ayrintilar = _details_metni(err)
        if mesaj and ayrintilar:
            return f"{mesaj} ({ayrintilar})"
        return mesaj or ayrintilar
    if isinstance(err, str):
        return err
    return ""


# ── Hata GÖVDESİNİN ANLAMI: iki paylaşılan yüklem ──────────────────────
#
# `detail_of` gövdenin ŞEKLİNİ çözüyor; aşağıdaki ikisi o metnin ANLAMINI
# okuyor. Aynı iki soru üç `map_error`da birden geçiyor — "anahtar mı
# geçersiz?", "içerik mi reddedildi?" — ve her biri kendi alt dizesini elle
# arıyordu. Şekil paylaşımının gerekçesinin aynısı burada da geçerli: SORU
# sağlayıcıdan bağımsız, cevabın TÜRKÇE METNİ değil.
#
# İKİ AZURE İKİZİ BİLEREK DIŞARIDA: `azure_client.map_error` bu modülü import
# EDEMEZ (`providers` onu import ediyor, döngü olurdu) ve o dosyaya dokunmama
# kararı `openai_client._post`un yorumunda yazılı; `chat_client` ise yalnız
# Azure'ı konuşuyor, yani aşağıda anlatılan yanlış pozitifi üreten gövde
# (Google'ın şema hatası) oraya hiç ulaşmıyor. İkisi de gövdeyi kendi içinde
# ayrıştırmaya devam ediyor.


def is_invalid_key(detail: str) -> bool:
    """Hata metni "anahtar geçersiz" mi diyor.

    400 İKİ ANLAMLI ve bu yüklem o ayrımın taşıyıcısı: Google geçersiz
    anahtarı da (`API key not valid` / `API_KEY_INVALID`) desteklenmeyen bir
    jetonu da 400 ile döndürüyor — canlı uçtan ölçüldü. Ayrımı yapmamak,
    anahtarı doğru olan kullanıcıya "anahtarını kontrol et" demek olurdu.

    Yüklem `gemini_client`ten ÇIKARILDI çünkü aynı gövde `openai_chat`
    üzerinden de geliyor: Gemini'nin sohbet ucu (`/v1beta/openai/…`) geçersiz
    anahtara 401 DEĞİL 400 döndürüyor ve o dosyanın anahtar metni yalnız 401
    dalındaydı — yani Gemini sohbeti çıplak bir "HTTP 400" ile bitiyordu.
    """
    alt = detail.lower()
    return "api key" in alt or "api_key" in alt


# İçerik reddinin GERÇEK işaretleri. Liste uzun ama her öğesi bir sağlayıcının
# ölçülmüş metninden: OpenAI "content policy" ve "safety system", Azure
# "content management policy" ve "content filter", Google "safety" /
# "blocked" / "prohibited".
_ICERIK_REDDI = ("content policy", "content_policy", "content filter",
                 "content_filter", "content filtering",
                 "content management policy", "safety", "moderation",
                 "prohibited", "block", "responsible ai", "flagged")


def is_content_policy(detail: str) -> bool:
    """Hata metni içerik reddi mi anlatıyor.

    ÇIPLAK `"content" in detail` YETMİYOR ve bu ölçülmüş bir yanlış pozitif:
    Google şema hatalarını da 400 ile döndürüyor ve metni

        Unknown name "content": Cannot find field.

    — yani gövdedeki bir ALAN ADINDAN söz ediyor, kullanıcının mesajından
    değil. O dizeyi içerik reddi saymak kullanıcıya "mesajın engellendi"
    diyordu; gerçek sebep (istemcinin göndermediği/yanlış gönderdiği alan)
    hiçbir yerde okunmuyordu — ve bu, hata metinlerini eyleme dönüştürme
    çabasının tam tersi. Aynı tuzak OpenAI'de de var:
    `Invalid value for 'content'` de 400 ve o da bir şema hatası.
    """
    alt = detail.lower()
    return any(isaret in alt for isaret in _ICERIK_REDDI)


def is_configured(model_id: str, kimlikler: Mapping[str, str] | None = None) -> bool:
    """Modelin kimliği girilmiş mi. Katalogda olmayan model için False."""
    m = catalog.image_model(model_id)
    # `is not None`, `bool(m)` DEĞİL: ikisi aynı şeyi söylüyor (dataclass
    # örneği her zaman doğru) ama mypy yalnız ilkini daraltıyor.
    return m is not None and credstore.is_configured(m.credential, kimlikler)


def generate(model_id: str, prompt: str, size: str, quality: str, n: int,
             *, client=None, credentials=None) -> list[bytes]:
    m = _resolve(model_id)
    return _pair(m.provider)[0](m, prompt, size, quality, n,
                                client=client, credentials=credentials)


def edit(model_id: str, prompt: str, images, size: str, quality: str, n: int,
         *, client=None, credentials=None) -> list[bytes]:
    m = _resolve(model_id)
    if not m.supports_edit:
        # Katalog kapısı rotada da var (app._check_edit_form); buradaki ikinci
        # kapı `providers.edit`'in başka bir çağıranı olduğu gün de korur.
        raise ac.ImageError(i18n.t("err.model_no_reference", None,
                                   model=etiket.label_of(m)))
    return _pair(m.provider)[1](m, prompt, images, size, quality, n,
                                client=client, credentials=credentials)


def video_is_configured(model_id: str, kimlikler: Mapping[str, str] | None = None) -> bool:
    """`is_configured`ın video ikizi. Katalogda olmayan model için False.

    ÜRETİMDE ÇAĞIRANI YOK ve bu not okurun onu aramasını önlemek için: iki
    kardeşi de (`is_configured` yukarıda, `chat_providers.is_configured`)
    aynı durumda. Arayüzün gerçekten okuduğu kapı `app._model_available` ve
    o `credstore`u doğrudan sorguluyor.

    Üçlü yine de duruyor çünkü sevk memurunun sözleşmesinin parçası: bir
    adaptör katmanına "bu modeli konuşabiliyor muyum" sorusunun cevabı o
    katmanda olmalı. Silinseydi bu modül, kardeşlerinin cevapladığı bir
    soruyu cevaplamayan tek sevk masası olurdu — ve dördüncü bir sağlayıcı
    eklerken o asimetri "video tarafında bu soru nasıl soruluyor?" diye
    aranan bir şey olurdu.
    """
    m = catalog.video_model(model_id)
    return m is not None and credstore.is_configured(m.credential, kimlikler)


def generate_video(model_id: str, prompt: str, size: str, quality: str,
                   duration: int, n: int, *, client=None,
                   credentials=None) -> list[bytes]:
    m = _resolve_video(model_id)
    return _video_pair(m.provider)[0](m, prompt, size, quality, duration, n,
                                      client=client, credentials=credentials)


def animate_video(model_id: str, prompt: str, images, size: str, quality: str,
                  duration: int, n: int, *, last_frame=None, client=None,
                  credentials=None) -> list[bytes]:
    m = _resolve_video(model_id)
    if not m.supports_edit:
        # `edit`teki ikinci kapının aynısı ve aynı gerekçesi: rota kapısı
        # (`app._check_video_form`) tek çağıran olmayabilir.
        raise ac.ImageError(i18n.t("err.model_no_reference", None,
                                   model=etiket.label_of(m)))
    if last_frame is not None and not m.supports_last_frame:
        # AYNI ikinci-kapı disiplini, ayrı bayrak üstünde: `supports_edit`
        # "ilk kareyi alır" diyor, son kareyi almayı SÖYLEMİYOR (Veo 3 ailesi
        # tam olarak böyle). Kapısız bırakmak, telde 400 dönen ve gerekçesi
        # sağlayıcının diliyle yazılmış bir istek demekti.
        raise ac.ImageError(i18n.t("err.model_no_last_frame", None,
                                   model=etiket.label_of(m)))
    return _video_pair(m.provider)[1](m, prompt, images, size, quality,
                                      duration, n, last_frame=last_frame,
                                      client=client, credentials=credentials)
