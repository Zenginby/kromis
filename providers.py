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
Sebep: `gpt-image-studio.spec`'in `hiddenimports=[]` değeri PyInstaller'ın
statik analizine dayanıyor ve o dosyanın 50 satırlık yorumu bunu ölçülmüş bir
değişmez sayıyor. Dinamik import o analizden kaçar ve paketlenmiş uygulamada
adaptör bulunamaz.

Bu dosya KÖKTE ve DÜZ — bir `providers/` PAKETİ olamaz. Android'in Chaquopy
kaynak kümesi `include "*.py"` ile kurulu, yani alt paket APK'ya hiç girmez ve
hata yalnız telefonda görünür (bkz. tests/test_android_packaging.py).
"""
from __future__ import annotations

import azure_client as ac
import catalog
import credstore


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
    çağrının bile gerçek bir `credentials.env` istemesine yol açıyordu.
    Testlerin ölçtüğü şey doğruydu: çözümü öne almak davranış DEĞİŞİKLİĞİ.
    Azure'ın iki dosyalı düşmesi de böylece tek bir yerde kalıyor.

    Yeni adaptörler kendi kimliğini `credstore.resolve(m.credential)` ile
    çözüyor — aynı tembellikle, yani kendi istek fonksiyonlarının içinde.
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


_ADAPTERS: dict[str, tuple] = {
    "azure": (_azure_generate, _azure_edit),
    # Değer bir ÇAĞRILABİLİR döndürücü olabiliyor (döngüyü kıran geç bağlama);
    # `_pair` ikisini de karşılıyor.
    "openai": _openai_adapter,
    "gemini": _gemini_adapter,
}

# provider → (generate_video, animate_video). Boş kalmayan tek anahtar bugün
# `gemini`: OpenAI'nin Videos API'si 24 Eylül 2026'da kapanıyor (yerine gelen
# ad YOK), Azure AI Foundry'de video barındırılmıyor, Anthropic'in video ucu
# hiç yok. Gerekçenin uzunu `catalog.VIDEO_MODELS`in başlığında.
_VIDEO_ADAPTERS: dict[str, tuple] = {
    "gemini": _veo_adapter,
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
            f"{m.label} için sağlayıcı adaptörü yok ({m.provider}).")
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
            f"{m.label} için video adaptörü yok ({m.provider}).")
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
    """
    # `list` kapısı `dict` kapısından ÖNCE: aksi hâlde dizi zaten elenmiş olur.
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message", ""))
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


def is_configured(model_id: str) -> bool:
    """Modelin kimliği girilmiş mi. Katalogda olmayan model için False."""
    m = catalog.image_model(model_id)
    return bool(m) and credstore.is_configured(m.credential)


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
        raise ac.ImageError(f"{m.label} referans görselle çalışmıyor.")
    return _pair(m.provider)[1](m, prompt, images, size, quality, n,
                                client=client, credentials=credentials)


def video_is_configured(model_id: str) -> bool:
    """`is_configured`ın video ikizi. Katalogda olmayan model için False."""
    m = catalog.video_model(model_id)
    return bool(m) and credstore.is_configured(m.credential)


def generate_video(model_id: str, prompt: str, size: str, quality: str,
                   duration: int, n: int, *, client=None,
                   credentials=None) -> list[bytes]:
    m = _resolve_video(model_id)
    return _video_pair(m.provider)[0](m, prompt, size, quality, duration, n,
                                      client=client, credentials=credentials)


def animate_video(model_id: str, prompt: str, images, size: str, quality: str,
                  duration: int, n: int, *, client=None,
                  credentials=None) -> list[bytes]:
    m = _resolve_video(model_id)
    if not m.supports_edit:
        # `edit`teki ikinci kapının aynısı ve aynı gerekçesi: rota kapısı
        # (`app._check_video_form`) tek çağıran olmayabilir.
        raise ac.ImageError(f"{m.label} referans görselle çalışmıyor.")
    return _video_pair(m.provider)[1](m, prompt, images, size, quality,
                                      duration, n, client=client,
                                      credentials=credentials)
