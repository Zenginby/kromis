# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Model kataloğu — hangi görsel/sohbet modelleri var, ne yapabiliyorlar, kaça.

Bu modül BİLEREK YAPRAK: proje içinden hiçbir şey import etmiyor (yalnız
`__future__` ve `dataclasses`). `version.py`'nin duruşunun aynısı ve aynı
gerekçeyle — bir yaprak modül döngüye HİÇ katılamaz, dolayısıyla `models.py`,
`app.py`, `prefs.py`, `storage.py` ve her adaptör onu serbestçe import edebilir.
`models.py:5-6`'daki "app.py'ye BAKMAZ" kuralı böylece dişini koruyor: o kuralın
amacı `app`'i içe almamak, katalog ise `app`'in tam tersi.

REDDEDİLEN ALTERNATİF: kataloğun `azure_client`'ı import edip `IMAGE_KEY`,
`CHAT_KEY`, `ALLOWED_SIZES` sabitlerini yeniden kullanması. Bugün döngü
üretmiyor, ama saf veri katmanını dosya G/Ç yapan ve istisna yükselten bir
modüle kalıcı olarak kaynatırdı — ve kataloğu `paths` olmadan test edilemez
hale getirirdi. Bunun yerine env adları burada LİTERAL olarak yeniden beyan
ediliyor, kayma da bir tripwire testiyle ölçülüyor
(tests/test_catalog.py::test_azure_girdisi_azure_client_ile_ayrismiyor).
Bu tam olarak `models.LOGO_OFFSET_LIMIT` ile `composite.OFFSET_LIMIT` arasında
kurulmuş desen (bkz. models.py:44-47).

ŞEKİL NEDEN dataclass, `prefs._SCHEMA`'nın demet üslubu DEĞİL: `_SCHEMA` girdi
başına 2 alan taşıyor, bir model tanımı ~14. Konumlu bir demette her okuyan
tarafın alanı SAYIYLA indekslemesi gerekirdi. `dataclasses` stdlib olduğu için
`requirements.txt` değişmiyor → `kromis.spec`'in `hiddenimports=[]`
değeri (o dosyanın 50 satırlık yorumu bunu ÖLÇÜLMÜŞ bir değişmez sayıyor)
korunuyor → Chaquopy de etkilenmiyor. `frozen=True`, deponun bugün modül
düzeyindeki demetlerden aldığı değişmezlik garantisinin aynısını veriyor.

DOSYA KÖKTE ve DÜZ olmak ZORUNDA — bir `providers/` alt paketi olamaz.
`android/app/build.gradle` Chaquopy kaynak kümesini `include "*.py"` ile
kuruyor, yani APK'ya YALNIZ kök düzeyindeki .py dosyaları giriyor. Bir alt
paket masaüstünde çalışır, telefonda `ModuleNotFoundError` verir — ve o
gradle satırının yorumu "yeni bir dizin eklendiğinde kimsenin bir şeyi
hatırlaması gerekmiyor" derken tam olarak bunu kastediyor. Mandal:
tests/test_android_packaging.py.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Credential:
    """Bir sağlayıcıya ERİŞİM bilgisinin tanımı — değeri değil, ADRESİ.

    Değerler `credentials.env`'de yaşıyor (0600, atomik yazım); burada yalnız
    hangi env adında durdukları ve Ayarlar formundaki karşılıkları var.

    `secret_field` neden burada: `app._redact_validation_errors` gizli alan
    adlarını BU listeden türetiyor. BYOK üçlüsünün (openai_api_key, fal_key,
    replicate_api_token) redaksiyon dışında kalması, listenin elle tutulmasının
    bedeliydi — katalogdan türetildiği için bundan sonra bir sağlayıcı beyan
    etmek redaksiyonu da kendiliğinden kapsıyor.
    """

    id: str
    label: str                    # Ayarlar panelindeki başlık (Türkçe)
    key_env: str                  # "AZURE_IMAGE_API_KEY"
    url_env: str | None = None    # None = adres sabit, kullanıcı giremez
    default_base_url: str | None = None   # url_env boşsa kullanılan adres
    secret_field: str | None = None       # SettingsRequest'teki GİZLİ alan adı
    url_field: str | None = None          # SettingsRequest'teki (gizli OLMAYAN) adres alanı


@dataclass(frozen=True)
class ImageModel:
    """Bir görsel modelinin yetenekleri ve kredi tarifesi.

    `id` BİZİM kararlı kimliğimiz, sağlayıcının ham adı DEĞİL: bu değer
    `history.json` kayıtlarına ve `prefs.json`'a yazılıyor. Ayrımın bedeli bir
    alan (`wire_model`), kazancı şu — sağlayıcı yarın `gpt-image-2`'yi yeniden
    adlandırırsa geçmişteki her kaydın modeli anlamsızlaşmıyor.

    `sizes` "BOYUT" değil "bu modelin kabul ettiği GEOMETRİ JETONU": Gemini'nin
    `size`'ı yok, `imageConfig.aspectRatio`'su var ve jetonları `"16:9"`
    biçiminde. İkinci bir `aspect_ratio` alanı AÇILMADI çünkü o, altı katmana
    birden (istek modeli, form, _check_edit_form, storage.save, ResultParams,
    sonuç kartı) "iki alandan tam olarak biri dolu" kuralını öğretmek olurdu.
    Tek alanda taşımak güvenli, çünkü `ResultParams.size` bilerek allowlist'siz
    ve yalnız uzunlukla sınırlı (bkz. models.py:412-417) — yani `"16:9"` hiçbir
    şema değişikliği istemiyor ve eski oturumlar kaydedilebilir kalıyor.

    `qualities` HİÇ BOŞ OLMUYOR — kalite knob'u olmayan model tek bir sentetik
    jeton beyan edip `quality_hidden=True` diyor. Sebep zincirleme: 
    `GenerateRequest.quality` zorunlu, `ResultParams.quality` `min_length=1`,
    `storage.save` alanı koşulsuz yazıyor. Boş bırakmak `ResultParams`'ta 422
    demek, yani o modelle üretilmiş bir oturumun BİR DAHA KAYDEDİLEMEMESİ — tam
    olarak o sınıfın allowlist muafiyetinin önlemek için var olduğu kırılma.
    Bir kelimelik doküman bedeli, dört modelde şema değişikliğinin yerine geçiyor.

    `images_per_request` = 1 ise adet başına AYRI istek atılıyor. Bu yalnız bir
    döngü değil, ZAMAN AŞIMI politikasını da değiştiriyor:
    `azure_client.read_timeout_for`'un `180+120*(n-1)` formülü "n görsel tek
    POST'ta döner" varsayımına dayanıyor ve o varsayım burada yanlış olur
    (bkz. providers.read_timeout_for).
    """

    id: str
    label: str
    provider: str                 # adaptör anahtarı: "azure" | "openai" | "gemini"
    wire_model: str               # sağlayıcıya GİDEN ad
    credential: str               # Credential.id
    sizes: tuple[str, ...]
    qualities: tuple[str, ...]    # en az BİR jeton — bkz. docstring
    max_n: int
    # TABAN maliyet, yalnız metadata. BİRİMİ `kind`e BAĞLI ve bu ayrım
    # `cost_for`da yaşıyor: `kind="image"` → GÖRSEL başına, `kind="video"` →
    # SANİYE başına. Video tarafında üretim-başına yazmak, süre ekseni olan bir
    # modelde etiketi anlamsız kılardı (4 sn ile 8 sn aynı krediyi gösterirdi
    # ve fatura iki katı olurdu). Mandal: tests/test_catalog.py.
    credits: int
    images_per_request: int = 1
    supports_edit: bool = False
    max_refs: int = 1
    # SON KARE (`instances[0].lastFrame`) — yalnız Veo 3.1 ailesinde.
    #
    # `max_refs`e KATLANMADI ve gerekçesi şu: son kare bir REFERANS değil ayrı
    # bir EKSEN. `max_refs=2` demek "iki referans görsel" demekti ve sıra
    # bilgisini taşımazdı — ikinci görselin son kare mi yoksa ikinci bir
    # referans mı olduğu sayıdan okunamaz. Ayrı bayrak, ayrı form alanı
    # (`app.animate`in `last_file`/`last_source_id` çifti) ve ayrı arayüz
    # yuvası: üçü de aynı ayrımı söylüyor.
    #
    # `supports_edit`e de katlanmadı: ilk kareyi alan bir model son kareyi
    # almayabilir (Veo 3'ün tamamı böyle). İkisini tek bayrağa indirmek, o gün
    # telde 400 dönen bir istek üretirdi.
    supports_last_frame: bool = False
    quality_hidden: bool = False
    # Arayüzün ilk seçtiği değerler. BOŞ = listenin ilk öğesi. Azure'da
    # `default_quality="medium"` bilerek yazılı: index.html'de `medium`
    # `selected` durumunda ve model seçicisi eklendiğinde o davranışın
    # değişmemesi gerekiyor (bir üretimin varsayılan kalitesini sessizce
    # düşürmek ya da yükseltmek doğrudan faturaya dokunurdu).
    default_size: str = ""
    default_quality: str = ""
    # Kalite → maliyet; verilen kaliteler `credits` tabanını EZER.
    credits_by_quality: tuple[tuple[str, int], ...] = ()
    # Kuyruklu sağlayıcı (fal/Replicate) ya da yoklamalı bir uç (Veo'nun
    # `predictLongRunning`i) için sürenin tavanı. None = tek vuruş.
    poll_timeout: float | None = None
    # SÜRE EKSENİ — yalnız video modellerinde dolu; `()` = "bu modelin süresi
    # yok" ve görsel girdilerinin tamamı böyle. `sizes`/`qualities`in aksine
    # jetonlar SAYI: `durationSeconds` telde tam sayı ve arayüzdeki etiket
    # ("4 sn") sunucuda türetiliyor, yani ikinci bir eşleme tablosu gerekmiyor.
    #
    # NEDEN `qualities`e KATLANMADI: bir modelin çözünürlüğü ile süresi
    # BAĞIMSIZ iki eksen (720p×4sn de 1080p×4sn de geçerli) ve tek jetona
    # katlamak çarpım kadar sentetik jeton üretirdi ("720p-4", "720p-6", …).
    # `credits_by_quality` de o jetonlara bakıyor, yani tarife de çarpım kadar
    # satır olurdu.
    durations: tuple[int, ...] = ()
    # Arayüzün ilk seçtiği süre. 0 = demetin ilk öğesi (`default_size`in kuralı).
    default_duration: int = 0
    note: str | None = None       # seçicide gösterilen kısa Türkçe uyarı
    # MEDYA TÜRÜ. `"image"` ve `"video"` iki AYRI demette yaşıyor
    # (`IMAGE_MODELS` / `VIDEO_MODELS`), yani bu alan üyeliğin tekrarı gibi
    # görünüyor — ama tekrar DEĞİL, çünkü model örneği demetinden KOPUK
    # dolaşıyor: `storage.save` kaydın uzantısını (`.png` / `.mp4`) bu alandan
    # gelen değere göre türetiyor ve `providers`in sevk memuru da onu okuyor.
    # Üyeliği ikinci kez sormak (`m in VIDEO_MODELS`) katalogu her katmana
    # import ettirirdi.
    kind: str = "image"
    # ÜYELİK TOHUMU — bugün hiçbir şeyi değiştirmiyor, yarının tek kancası.
    # "free" = abonelik gerektirmiyor. Kredi/üyelik sistemi geldiğinde bir
    # modelin GÖRÜNMEME sebebi ikiye çıkacak ("anahtar yok" · "plan
    # kapsamıyor") ve o kararın TEK bir yerde verilmesi şart: arayüz bugün de
    # tek soru soruyor (`available`, bkz. app._model_available). Alanın burada
    # olmasının sebebi, kararın VERİSİNİN katalogda yaşaması — sağlayıcı
    # eklendiğinde plan bilgisi modelle birlikte geliyor, ikinci bir tabloda
    # unutulmuyor.
    plan: str = "free"


@dataclass(frozen=True)
class ChatModel:
    """Prompt Yönetmeni'nin konuşabildiği bir sohbet modeli.

    `wire_model` boşsa ad ORTAMDAN okunuyor (`wire_from_env`). Bu istisna
    yalnız Azure için var ve gerçek: Azure'da "model" yok, DAĞITIM var — adı
    kullanıcının verdiği herhangi bir dize olabiliyor, yani kataloğa
    yazılamıyor. `AZURE_CHAT_DEPLOYMENT` bu yüzden `credentials.env`'de
    KALIYOR (tercihlere taşınmıyor): o bir model adı değil, adresin parçası,
    ve tests/test_settings_route.py'de beş test onun gidiş-dönüşünü sabitliyor.

    Ayrım şu kuralla okunuyor: "hangi modeli İSTİYORUM" → prefs.json,
    "ona NASIL ULAŞIYORUM" → credentials.env.
    """

    id: str
    label: str
    provider: str                 # "azure" | "openai" | "anthropic" | "gemini"
    credential: str
    wire_model: str = ""
    wire_from_env: str | None = None
    # Kimliğin `base_url`üne EKLENEN yol. Varsayılan üç girdiden ikisinde
    # doğru (`https://api.openai.com/v1` + `/chat/completions`, Azure'ın
    # `…/openai/v1/`si + aynısı); Gemini'de değil — onun OpenAI-uyumlu ucu
    # `/v1beta/openai/` altında yaşıyor ve kimliğin `base_url`ü görsel
    # tarafıyla PAYLAŞILIYOR (`/v1beta/interactions`). İki `Credential`
    # açmak, kullanıcıdan aynı anahtarı iki kez istemek olurdu.
    endpoint_path: str = "/chat/completions"
    # Anthropic `max_tokens`'ı ZORUNLU tutuyor (yoksa 400). Bu bir ayar değil TEL
    # ZORUNLULUĞU, o yüzden `chat_client.build_payload`'ın "hiç sampling
    # parametresi göndermeme" duruşunun gevşetilmesi DEĞİL — sağlayıcı başına
    # ayrı bir olgu. Minimal-gövde tripwire'ı bu yüzden adaptör BAŞINA yazılıyor,
    # yoksa buradaki meşru `max_tokens` bir gün Azure gövdesine kopyalanır.
    needs_max_tokens: bool = False
    note: str | None = None       # seçicide gösterilen kısa Türkçe uyarı
    kind: str = "chat"
    # ImageModel.plan ile AYNI alan ve aynı gerekçe (uzunu orada).
    plan: str = "free"


# ── Kimlik bilgileri ────────────────────────────────────────────────────
#
# Env ADLARI burada literal (dosya başındaki "reddedilen alternatif" notu).
# `azure_client.IMAGE_KEY` / `IMAGE_URL` / `CHAT_*` ile ayrışma testte ölçülüyor.

CREDENTIALS: tuple[Credential, ...] = (
    Credential(
        id="azure_image",
        label="Azure OpenAI · görsel",
        key_env="AZURE_IMAGE_API_KEY",
        url_env="AZURE_IMAGE_BASE_URL",
        secret_field="api_key",
        url_field="base_url",
    ),
    Credential(
        id="azure_chat",
        label="Azure OpenAI · sohbet",
        key_env="AZURE_CHAT_API_KEY",
        url_env="AZURE_CHAT_BASE_URL",
        # Sohbetin kendi anahtarı yoksa GÖRSELİN kimliğine düşüyor — canlı
        # doğrulanmış davranış, bkz. azure_client.resolve_chat_credentials.
        # O düşme `credstore`'da yaşıyor, burada yalnız adlar var.
        secret_field=None,
        url_field=None,
    ),
    # OpenAI anahtarı v0.2.0'dan beri KAYDEDİLİYOR ama hiçbir kod onu okuyup
    # çağrı yapmıyordu; buradan itibaren `credstore` üzerinden okunabilir.
    Credential(
        id="openai",
        label="OpenAI",
        key_env="OPENAI_API_KEY",
        url_env="OPENAI_BASE_URL",
        # Adres SABİT bir varsayılana sahip: Azure'ın aksine OpenAI'de her
        # kullanıcının kendi endpoint'i yok. `url_env` yine de var, çünkü
        # uyumlu bir vekil (proxy/gateway) arkasına almak isteyen kullanıcı
        # dosyaya elle yazabilsin — forma alan eklemeden.
        default_base_url="https://api.openai.com/v1",
        secret_field="openai_api_key",
        url_field="openai_base_url",
    ),
    Credential(
        id="gemini",
        label="Google Gemini",
        key_env="GEMINI_API_KEY",
        url_env="GEMINI_BASE_URL",
        default_base_url="https://generativelanguage.googleapis.com",
        secret_field="gemini_api_key",
        url_field="gemini_base_url",
    ),
    # Yalnız SOHBET tarafında kullanılıyor: Anthropic'in görsel üretme ucu yok.
    Credential(
        id="anthropic",
        label="Anthropic",
        key_env="ANTHROPIC_API_KEY",
        url_env="ANTHROPIC_BASE_URL",
        default_base_url="https://api.anthropic.com",
        secret_field="anthropic_api_key",
        url_field="anthropic_base_url",
    ),
    # MAI ve FLUX aynı Azure kaynağında ama BAŞKA bir hostta yaşıyor
    # (`<kaynak>.services.ai.azure.com`) ve `/openai/v1` onları SERVİS
    # ETMİYOR: şema doğrulamasını geçen istek "Model not supported with
    # Responses API" ile düşüyor. Sebep Entra sondasıyla kanıtlandı — iki
    # AYRI veri eylemi (`…/accounts/OpenAI/images/generations/action` ve
    # `…/accounts/MaaS/images/generations/action`). Yani bu modelleri
    # `azure_image` kimliğinin altına koymak, bu dosyanın uyardığı
    # "arayüzde seçilebilir bir 400"ün tam kendisi olurdu.
    #
    # `secret_field=None` ve bu `azure_chat`in duruşunun aynısı: anahtar
    # `AZURE_IMAGE_API_KEY`e DÜŞÜYOR (sonda tek anahtarın üç yüzeyde de
    # geçtiğini ölçtü), yani forma ikinci bir gizli alan eklemek kullanıcıya
    # aynı değeri iki kez yazdırmak olurdu. Forma giren TEK yeni alan
    # `azure_foundry_base_url` ve o gizli DEĞİL — yani
    # `app._redact_validation_errors`'ın katalogdan türettiği redaksiyon
    # kümesi değişmiyor.
    #
    # `default_base_url` YOK çünkü sabit bir adres yok: adres ya elle yazılıyor
    # ya da görselin adresinin HOSTundan türetiliyor
    # (bkz. credstore.derive_foundry_base_url).
    Credential(
        id="azure_foundry",
        label="Azure AI Foundry · MAI ve FLUX",
        key_env="AZURE_FOUNDRY_API_KEY",
        url_env="AZURE_FOUNDRY_BASE_URL",
        secret_field=None,
        url_field="azure_foundry_base_url",
    ),
)


# ── Sağlayıcı işaretleri (logo) ──────────────────────────────────────────
#
# Model şeritleri seçili modelin sağlayıcısını bir işaretle de gösteriyor.
# Eşleme BURADA, istemcide DEĞİL: `settings.js`in dağıtım kutusu kapısı için
# yazılmış gerekçenin aynısı geçerli — sağlayıcı adını istemcide literal saymak,
# yeni bir sağlayıcı eklendiği gün işaretin SESSİZCE kaybolması demekti. Burada
# duruyorsa tests/test_provider_logos.py adaptörü olan her sağlayıcı için dosya
# arıyor ve logosuz bir adaptör suite'i kırıyor.
#
# DEĞER dosya adı, tam adres DEĞİL: `?v=` cache-buster'ı `app.py`'nin
# `index()`indeki tek desenden geliyor ve katalog yaprak kalıyor (`version`
# import etmiyor).
#
# Dosyalar `static/img/providers/` altında ve `kromis.spec` `static`
# dizininin tamamını aldığı için paketleme bedeli SIFIR.

PROVIDER_LOGOS: dict[str, str] = {
    "azure": "azure.svg",
    "openai": "openai.svg",
    "gemini": "gemini.svg",
    "azure-mai": "microsoft.svg",
    "azure-flux": "blackforestlabs.svg",
}

# İşaret ARTIK MARKAYI SÖYLÜYOR, o yüzden etiketin de söylemesi gereksiz: şeritte
# "Gemini · Nano Banana 2" yazan satır Gemini işaretinin YANINDA duruyordu.
# Marka adları BURADA, `PROVIDER_LOGOS`la aynı gerekçeyle — istemcide sağlayıcı
# adını literal saymak yeni bir sağlayıcı eklendiği gün önekin sessizce ekranda
# kalması demekti (bkz. settings.js `syncChatDeployField`in gerekçesi).
#
# `label` DEĞİŞMİYOR ve bu bilinçli: hata metinleri ("… referans görselle
# çalışmıyor", "… anahtarı yok"), `#model-note` ve durum satırı hepsi ondan
# okuyor ve orada marka AYIRT EDİCİ — katalogda `gpt-image-2` adını taşıyan İKİ
# model var (Azure ve OpenAI). Kısa ad yalnız şeridin satırları için.
PROVIDER_BRANDS: dict[str, str] = {
    "azure": "Azure",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "anthropic": "Anthropic",
    "azure-mai": "Microsoft",
    "azure-flux": "Black Forest Labs",
}


# MAI'nin GEOMETRİ BÜTÇESİ — canlı ölçüldü: w,h ≥ 768 VE w·h ≤ 1.048.576.
#
# Jetonlar `gpt-image-2`den KOPYALANMIYOR ve sebep sert: `1024x1536` ile
# `1536x1024` 1.572.864 piksel eder, yani tavanı %50 aşar. Kopyalamak iki
# jetonu doğrudan hataya sokardı.
#
# BU LİSTE BİR KOLAYLIK DEĞİL, GÜVENLİK SINIRI. MAI hatalı bir `size`
# gönderildiğinde 400 DÖNMÜYOR, sessizce varsayılanla ÜRETİYOR — sondada
# ölçüldü: `size:"1x1"` yutuldu ve iki gerçek 1024×1024 görsel üretildi.
# Yani sağlayıcı artık bir doğrulama katmanı DEĞİL ve
# `models.check_capabilities` TEK kapı; buradaki bir hata kullanıcıya hata
# değil İSTEMEDİĞİ BOYUTTA BİR FATURA gösterir.
#
# Küme mevcut oranların HEPSİNİ karşılıyor (1:1, 4:3, 3:4, 3:2, 2:3, 16:9,
# 9:16), yani `gpt-image-2`den MAI'ye geçen kullanıcı "varsayılana düşüldü"
# uyarısı ALMIYOR (bkz. core.js `fillAxis`in ikinci kademesi).
#
# Mandal: tests/test_catalog.py::test_MAI_jetonlari_PIKSEL_butcesine_uyuyor.
MAI_MIN_EDGE = 768
MAI_PIXEL_CAP = 1_048_576
MAI_SIZES: tuple[str, ...] = (
    "1024x1024",   # 1.048.576 · 1:1
    "1024x768",    #   786.432 · 4:3
    "768x1024",    #   786.432 · 3:4
    "1248x832",    # 1.038.336 · 3:2
    "832x1248",    # 1.038.336 · 2:3
    "1365x768",    # 1.048.320 · 16:9
    "768x1365",    # 1.048.320 · 9:16
)

# FLUX.2 `gpt-image-2`nin ÜÇ JETONUNU AYNEN kullanabiliyor: üçü de belgelenmiş
# 4 MP tavanının çok altında ve 32'nin katı. Kazanç somut ve ölçülebilir —
# gpt-image-2'den FLUX'a geçen kullanıcı "varsayılana düşüldü" uyarısı ALMIYOR
# (bkz. core.js `fillAxis`).
#
# MAI'de aynı şeyi yapmak MÜMKÜN DEĞİLDİ (bkz. MAI_SIZES): `1024x1536` ve
# `1536x1024` MAI'nin piksel tavanını %50 aşıyor. İki sağlayıcının iki ayrı
# demet taşımasının sebebi bu, üslup değil.
#
# FLUX'un GERÇEK boyut kabulü (alt sınır, 32'nin katı olma şartı) bu depoda
# ÖLÇÜLMEDİ; üç jeton tavanın çok altında kaldığı için ilk tur güvenli.
# Mandal: tests/test_catalog.py::test_FLUX_jetonlari_gpt_image_2_ile_AYNI.
FLUX_SIZES: tuple[str, ...] = ("1024x1024", "1024x1536", "1536x1024")


# ── Görsel modelleri ────────────────────────────────────────────────────
#
# SIRA ANLAMLI: arayüzdeki seçicinin sırası bu ve ilk girdi varsayılan.
#
# Kredi değerleri BİZİM tarifemiz, sağlayıcının fiyatı değil — yani doğrulanacak
# bir olgu değil, ürün kararı. Bugün yalnız METADATA: hiçbir yerde bakiye
# düşülmüyor, hiçbir üretim engellenmiyor. Kayda ÜRETİM ANINDAKİ çözülmüş tam
# sayı yazılıyor (bkz. cost_for ve storage.save), katalog işaretçisi değil:
# tarife değişince geçmiş retroaktif olarak yeniden yazılmasın. İleride gelecek
# ledger'ın ihtiyacı olan tek şey o alan.
#
# ORANTI yine de keyfi değil, tek bir çapaya bağlı: Azure'ın `medium` kalitesi
# 8 kredi ve o üretim sağlayıcıda ~0,04 USD. Yeni girdilerin kredisi kendi
# yayınlanmış görsel-başı fiyatının bu çapaya bölünmesiyle yazıldı (Nano Banana
# Pro 1K/2K ≈ 0,134 USD → 27, 4K ≈ 0,24 USD → 48). Böylece seçicideki kredi
# etiketi kullanıcıya GERÇEK bir karşılaştırma veriyor: "27 kredi" gerçekten
# "8 kredi"nin üç katı kadar pahalı.
#
# `note` SEÇİCİDE model adının ALTINA yazılıyor (static/core.js) ve tek işi
# şu soruyu cevaplamak: "ne zaman bunu seçerim?". Bu yüzden notlar bir yetenek
# listesi DEĞİL, bir KARAR cümlesi — ve UYGULAMANIN YAPMADIĞI bir şeyi vaat
# etmiyorlar: FLUX 8/10 referans alabiliyor ama ilk tur `app.MAX_EDIT_IMAGES`
# (4) tavanında kalıyor, o yüzden hiçbir not o sayıları yazmıyor. Mandal:
# tests/test_catalog.py'nin `note` sözleşmesi bloğu.

DEFAULT_IMAGE_MODEL = "azure-gpt-image-2"

# Gemini'nin belgelenmiş ON oranı — `response_format.aspect_ratio` jetonları.
# İKİ Gemini girdisi de aynı demeti paylaşıyor: elle iki kez yazmak, birine
# oran ekleyip diğerini unutmanın kapısı olurdu.
#
# SIRA arayüzdeki seçicinin sırası: kare → dikey → yatay, her biri artan
# genişlikte. `default_size="1:1"` bilerek AÇIKÇA yazılı (demetin ilk öğesine
# güvenmek yerine): sıra bir gün estetik bir kararla değişirse varsayılan
# üretim oranı sessizce değişmesin.
#
# Bilinmeyen bir jeton buraya girerse sağlayıcı 400 döner ve hata Türkçeye
# çevrilerek görünür — sessiz bir düşme YOK. Bu yüzden liste yalnız
# BELGELENMİŞ oranları taşıyor, "muhtemelen çalışır" olanları değil.
ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "9:16", "2:3", "3:4", "4:5",
    "5:4", "4:3", "3:2", "16:9", "21:9",
)

IMAGE_MODELS: tuple[ImageModel, ...] = (
    ImageModel(
        id=DEFAULT_IMAGE_MODEL,
        label="Azure · gpt-image-2",
        provider="azure",
        wire_model="gpt-image-2",
        credential="azure_image",
        # Bu üçü `azure_client.ALLOWED_SIZES`/`ALLOWED_QUALITIES` ile BİREBİR
        # aynı olmak zorunda: o sabitler hâlâ duruyor ve testleri onlara bakıyor.
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("low", "medium", "high"),
        max_n=4,
        default_quality="medium",
        # Tek POST n görsel döndürüyor (build_payload `n`'i gövdeye koyuyor).
        images_per_request=4,
        supports_edit=True,
        # 1 ana + 3 ek. `app.MAX_EDIT_IMAGES` ile aynı sayı.
        max_refs=4,
        credits=8,
        credits_by_quality=(("low", 4), ("medium", 8), ("high", 16)),
        note="Metin, tabela ve çok referanslı düzenlemede en güçlü; "
             "uygulamanın varsayılanı.",
    ),
    # OpenAI DOĞRUDAN (Azure üzerinden değil). Tel formatı Azure'ın aynısı, o
    # yüzden adaptör onun bilinçli ikizi (bkz. openai_client.py'nin başlığı).
    #
    # `gpt-image-2` OpenAI tarafının BAŞINDA duruyor çünkü OpenAI'nin görsel
    # ailesinde bugün tek KALICI ad o: `gpt-image-1` 23 Ekim 2026'da,
    # `gpt-image-1.5` ve `gpt-image-1-mini` 1 Aralık 2026'da API'den kalkıyor.
    # Yetenek jetonları Azure ikizinden KOPYALANDI ve bu bilinçli bir alt
    # sınır: `gpt-image-2` 2K'ya kadar çıkabiliyor ve tek istekte 8 görsel
    # döndürebiliyor, ama o jetonların OpenAI ucundaki karşılıkları bu depoda
    # canlı DOĞRULANMADI. Doğrulanmamış bir boyut jetonu beyan etmek arayüzde
    # seçilebilir bir 400 üretir; eksik beyan etmek yalnızca bir yeteneği
    # kullanmamak. `max_n` ayrıca `models.MAX_IMAGES_PER_RUN` (4) ile de
    # sınırlı — 8'e çıkmak o sabiti ve sonuç kaydının `image_ids` tavanını
    # birden değiştirmek olurdu.
    #
    # TEL ADI belgeden doğrulandı (22 Ağustos 2026): `gpt-image-2` API'de bu
    # adla duruyor. CANLI çağrı YOK ve bu depoda yapılamıyor — sohbet
    # adlarının notunda yazılı gerekçenin aynısı.
    #
    # AYNI BELGE yukarıdaki "alt sınır" kararını da DOĞRULUYOR ve jetonların
    # uyuşmadığını söylüyor: modelin gerçek ekseni 1K/2K/4K fiyatlanıyor ve
    # boyut olarak 16'nın katı her `WxH` kabul ediliyor, buradaki
    # `low/medium/high` + üç sabit boyut ise Azure ikizinden kopyalandı. Yani
    # beyan edilen küme modelin YAPABİLDİĞİNDEN küçük — eksik beyan yalnızca
    # bir yeteneği kullanmamak, doğrulanmamış jeton beyan etmek ise arayüzde
    # seçilebilir bir 400. Genişletme, jetonlar canlı bir anahtarla
    # sınandığında yapılacak iş.
    #
    # Ad bir gün kalktığında maliyet artık bir cümle: 404 metni MODELİN ADINI
    # söylüyor (`openai_client.map_error`), yani kullanıcı anahtarını
    # kurcalamak yerine şeritten başka bir model seçiyor.
    ImageModel(
        id="openai-gpt-image-2",
        label="OpenAI · gpt-image-2",
        provider="openai",
        wire_model="gpt-image-2",
        credential="openai",
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("low", "medium", "high"),
        default_quality="medium",
        max_n=4,
        images_per_request=4,
        supports_edit=True,
        max_refs=4,
        credits=8,
        credits_by_quality=(("low", 4), ("medium", 8), ("high", 16)),
        note="Azure'daki modelin aynısı, kendi anahtarınla — kurumsal "
             "kaynağın yoksa bunu seç.",
    ),
    # KATALOGDA KALIYOR ama ÖMÜRLÜ: 23 Ekim 2026'da OpenAI API'sinden kalkıyor.
    # Bugün çalışıyor ve anahtarı yalnız bu modele erişen hesaplar var, o yüzden
    # silmek erken; notu uyarıyor. O tarihte girdi silinir — `openai-dall-e-3`
    # gibi ölmüş bir girdinin katalogda kalmasının bedeli ölçüldü: kullanıcı
    # seçebiliyor, üretim 404 alıyor ve hata "model bulunamadı" diyor.
    ImageModel(
        id="openai-gpt-image-1",
        label="OpenAI · gpt-image-1",
        provider="openai",
        wire_model="gpt-image-1",
        credential="openai",
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("low", "medium", "high"),
        default_quality="medium",
        max_n=4,
        images_per_request=4,
        supports_edit=True,
        max_refs=4,
        credits=8,
        credits_by_quality=(("low", 4), ("medium", 8), ("high", 16)),
        note="Seçmeyin: 23 Ekim 2026'da API'den kalkıyor. gpt-image-2'ye geç.",
    ),
    # ── Gemini · Nano Banana ────────────────────────────────────────────
    #
    # KATALOGDA İLK KEZ "BOYUT" YERİNE "ORAN" SEÇEN MODEL. `sizes` alanının
    # docstring'i bu günü tarif ediyordu: jetonlar `WxH` değil `16:9`, ikinci
    # bir `aspect_ratio` alanı AÇILMIYOR ve `ResultParams.size`ın allowlist'siz
    # olması sayesinde bu oturumlar kaydedilebilir kalıyor.
    #
    # `ratio` alanı sayesinde model değiştirmek ORANI TAŞIYOR: Azure'ın
    # `1024x1536`ı da Gemini'nin `2:3`ü de aynı `ratio`yu bildiriyor, yani
    # core.js'in ikinci kademesi sessizce doğru jetona geçiyor. Azure'ın üç
    # boyutunun ÜÇÜNÜN DE burada karşılığı var (1:1, 2:3, 3:2) — yani model
    # değiştiren kullanıcı hiçbir zaman "varsayılana düşüldü" uyarısı almıyor.
    #
    # KALİTE EKSENİ VAR ve `quality_hidden=False`: eski `gemini-2.5-flash-image`
    # döneminde bu modelin çözünürlük knob'u yoktu (core.js ve index.html'deki
    # yorumlar hâlâ o günü anlatıyordu, bu turda düzeltildi). Interactions ucu
    # `response_format.image_size` alıyor ve 1K/2K/4K GERÇEK bir eksen —
    # üstelik faturaya dokunuyor, yani `credits_by_quality` tam yerinde.
    #
    # `images_per_request=1`: Interactions ucunun görsel tarafında `n` YOK, tek
    # çağrı tek görsel döndürüyor. `providers.read_timeout_for`ın adet-başına-
    # ayrı-istek dalı bu modelle ilk gerçek kullanıcısını buluyor (öncesinde
    # yalnız sentetik testler ölçüyordu).
    #
    # TEL ADLARI belgeden doğrulandı (22 Ağustos 2026): `gemini-3.1-flash-image`
    # (Nano Banana 2) ve `gemini-3-pro-image` (Nano Banana Pro) — ikisi de
    # "preview" jetonu TAŞIMIYOR, yani sohbet tarafında Pro'yu dışarıda
    # bırakan kural burada tetiklenmiyor. Uç ve başlık CANLI doğrulandı
    # (anahtarsız çağrı 404 değil 400 dönüyor); 200 yanıtının şekli
    # doğrulanmadı (bkz. tests/test_gemini_client.py'nin başlığı).
    ImageModel(
        id="gemini-nano-banana-2",
        label="Gemini · Nano Banana 2",
        provider="gemini",
        wire_model="gemini-3.1-flash-image",
        credential="gemini",
        sizes=ASPECT_RATIOS,
        default_size="1:1",
        qualities=("1K", "2K", "4K"),
        # 2K, 1K ile AYNI fiyatta (ikisi de 1120 jeton) — yani varsayılanı 1K
        # yapmak bedava çözünürlüğü çöpe atmak olurdu.
        default_quality="2K",
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        # Model daha fazlasını kabul ediyor; tavan `app.MAX_EDIT_IMAGES`.
        max_refs=4,
        credits=6,
        credits_by_quality=(("1K", 6), ("2K", 6), ("4K", 12)),
        # "en ucuz" DEĞİL, ölçüldü: MAI-Image 2.6 Flash 4 kredi, bu 6. İddiayı
        # yazan tur ile onu yanlışlayan tur AYNI daldı. Hız iddiası duruyor —
        # katalogda gecikme verisi yok, yani ölçülemez; maliyet ölçülebilir ve
        # artık mandallı.
        note="En hızlı tur; oran seçiliyor (piksel değil). Taslak için.",
    ),
    ImageModel(
        id="gemini-nano-banana-pro",
        label="Gemini · Nano Banana Pro",
        provider="gemini",
        wire_model="gemini-3-pro-image",
        credential="gemini",
        sizes=ASPECT_RATIOS,
        default_size="1:1",
        qualities=("1K", "2K", "4K"),
        default_quality="2K",
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        credits=27,
        credits_by_quality=(("1K", 27), ("2K", 27), ("4K", 48)),
        note="Marka tutarlılığı ve uzun metin yerleşimi; pahalı ama en "
             "sadık.",
    ),
    # ── Azure AI Foundry · MAI-Image (Microsoft) ────────────────────────
    #
    # ÜÇÜ DE ÖNİZLEME ve notlarında yazılı: ad ya da sözleşme haber vermeden
    # değişebilir. `openai-gpt-image-1` girdisinin duruşu benimseniyor —
    # kalktığı gün girdi SİLİNİR, çünkü katalogda kalan ölü bir girdi
    # arayüzde seçilebilir bir 404 demek (`openai-dall-e-3`ün ölçülmüş dersi).
    #
    # KREDİ ÇAPASI görsel tarafındakiyle AYNI: Azure `medium` = 8 kredi
    # ≈ 0,04 USD, yani 1 kredi ≈ 0,005 USD. MAI token bazlı faturalanıyor ve
    # sonda ölçüyü verdi: 1024×1024 görsel için `usage.num_output_tokens`
    # = 1024. 2.6 → 1024 tok × 38 USD/M = 0,0389 USD → 8 kredi;
    # 2.5-Pro → 1024 tok × 47 USD/M = 0,0481 USD → 10 kredi.
    # 2.6-Flash'ın yayınlanmış birim fiyatı DOĞRULANAMADI (Azure fiyat
    # sayfaları JS ile çiziliyor, tablo boş döndü) — 4 kredi GEÇİCİ.
    #
    # KABUL EDİLEN YAKLAŞIKLIK: `cost_for`un boyut ekseni yok, oysa MAI'de
    # token = piksel. Kredi VARSAYILAN boyuttaki maliyeti gösteriyor;
    # düzeltmek `cost_for`a üçüncü bir eksen eklemek demek ve bu turun
    # kapsamı dışında.
    #
    # `max_n=4`: MAI'de `n` parametresi HİÇ YOK, tavan
    # `models.MAX_IMAGES_PER_RUN`dan geliyor ve dört AYRI istek atılıyor.
    ImageModel(
        id="azure-mai-image-2-6",
        label="Microsoft · MAI-Image 2.6",
        provider="azure-mai",
        wire_model="MAI-Image-2.6",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        # Kalite ekseni YOK (karar 4): tek sentetik jeton + gizli knob. Boş
        # bırakmak `ResultParams`ta 422 demekti, yani o modelle üretilmiş bir
        # oturumun BİR DAHA KAYDEDİLEMEMESİ.
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        # Düzenleme ucu TEK görsel alıyor (canlı ölçüldü). `max_refs=1` beyan
        # eden ilk GÖRSEL modeli bu, yani ikinci kapı adaptörde
        # (`azure_mai_client.build_image_file`) — görsel düzenleme rotası
        # model başına `max_refs`e bakmıyor.
        max_refs=1,
        credits=8,
        note="Fotogerçekçi ürün ve portre işi; metin işlemede MAI'nin en "
             "iyisi. Tek referansla düzenliyor. Önizleme.",
    ),
    ImageModel(
        id="azure-mai-image-2-6-flash",
        label="Microsoft · MAI-Image 2.6 Flash",
        provider="azure-mai",
        wire_model="MAI-Image-2.6-Flash",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # GEÇİCİ: birim fiyat doğrulanamadı, oran 2.6'nın yarısı varsayıldı.
        credits=4,
        note="2.6'nın hızlı ve ucuz kardeşi; taslak ve deneme turları için. "
             "Tek referansla düzenliyor. Önizleme.",
    ),
    ImageModel(
        id="azure-mai-image-2-5-pro",
        label="Microsoft · MAI-Image 2.5 Pro",
        provider="azure-mai",
        wire_model="MAI-Image-2.5-Pro",
        credential="azure_foundry",
        sizes=MAI_SIZES,
        default_size="1024x1024",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        credits=10,
        note="Kalabalık sahnelerde nesne ve karakter tutarlılığı; pahalı. "
             "Tek referansla düzenliyor. Önizleme.",
    ),
    # ── Azure AI Foundry · FLUX.2 (Black Forest Labs) ───────────────────
    #
    # KREDİLER GEÇİCİ: FLUX megapiksel başına faturalanıyor ve yayınlanmış
    # birim fiyat doğrulanamadı (Azure fiyat sayfaları JS ile çiziliyor,
    # tablo boş döndü). Çapa yine Azure `medium` = 8 kredi ≈ 0,04 USD.
    # Krediler zaten "doğrulanacak bir olgu değil, ürün kararı" — ama ORAN
    # yanlışsa seçicideki karşılaştırma yalan söyler, o yüzden takip ediliyor.
    #
    # `max_n=1` ve gerekçesi iki katmanlı: (1) `num_images`ın üst sınırı
    # ölçülmedi ve fazla beyan arayüzde seçilebilir bir hata; (2) FLUX
    # dağıtımlarının kapasitesi düşük (belgelenmiş RPM'de flex için 5/dk) —
    # dört paralel istek 429'a girerdi ve sonda sırasında `RateLimitReached`
    # gerçekten görüldü.
    #
    # ÇOK REFERANSLI DÜZENLEME 8/10 görsele kadar çıkıyor ama ilk tur
    # `app.MAX_EDIT_IMAGES` (4) tavanında kalıyor; not bu yüzden 8/10 SÖZÜ
    # VERMİYOR — uygulamanın yapmadığı bir şeyi seçicide vaat etmek bu
    # deponun yasakladığı sessiz sapmanın kendisi.
    #
    # İÇERİK FİLTRESİ YOK (Microsoft'un kendi uyarısı), yani
    # `providers.is_content_policy` bu sağlayıcıda hiç tetiklenmiyor. Not
    # adaptörün başlığında da yazılı ki ileride "neden çalışmıyor" diye
    # aranmasın.
    ImageModel(
        id="azure-flux-2-pro",
        label="Black Forest Labs · FLUX.2 pro",
        provider="azure-flux",
        wire_model="FLUX.2-pro",
        credential="azure_foundry",
        sizes=FLUX_SIZES,
        # `quality` parametresi YOK: tek sentetik jeton + gizli knob (karar 4).
        qualities=("standard",),
        quality_hidden=True,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        credits=16,
        note="En yüksek görsel kalite; yavaş ve pahalı. Tek turda 1 görsel.",
    ),
    ImageModel(
        id="azure-flux-2-flex",
        label="Black Forest Labs · FLUX.2 flex",
        provider="azure-flux",
        wire_model="FLUX.2-flex",
        credential="azure_foundry",
        sizes=FLUX_SIZES,
        # GERÇEK bir eksen (karar 4): jetonlar `steps`/`guidance` çiftlerine
        # çözülüyor (bkz. azure_flux_client._FLEX_QUALITY). Sentetik bir jeton
        # burada israf olurdu.
        qualities=("hizli", "dengeli", "detayli"),
        default_quality="dengeli",
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        credits=10,
        # Taban `dengeli` (25 adım); ötekiler adım oranından türetildi
        # (10/25 → 0,6× ve 50/25 → 1,6×, yuvarlanmış). ÜÇÜ DE GEÇİCİ —
        # megapiksel fiyatı doğrulanmadı.
        credits_by_quality=(("hizli", 6), ("dengeli", 10), ("detayli", 16)),
        note="Adım ve yönlendirme seçilebiliyor: metin ağırlıklı yerleşimler "
             "için. Tek turda 1 görsel.",
    ),
)


# ── Video modelleri ─────────────────────────────────────────────────────
#
# AYRI BİR DEMET, `IMAGE_MODELS`a EKLENMİŞ girdiler DEĞİL — ve bu kararın
# taşıyıcı gerekçesi şu: `image_model()` bugün beş yerden okunuyor (prefs
# doğrulaması, `models.check_capabilities`, `app._model_available`,
# `storage.save`in varsayılanı, arena turu). Video girdileri o demete girse
# BEŞİNİN DE süzgeç öğrenmesi gerekirdi ve birini unutmak videoyu
# `/api/generate`de seçilebilir kılardı: senkron bir görsel ucuna 7 dakikalık
# bir video isteği, yani sessiz sapmanın en pahalı türü. Ayrı demet
# `image_model()`i dokunulmadan bırakıyor; `kind` alanı da o yüzden hâlâ
# gerekli (bkz. onun yorumu — örnek demetinden kopuk dolaşıyor).
#
# DATACLASS PAYLAŞILIYOR (`ImageModel`), ikinci bir `VideoModel` AÇILMADI:
# eksenlerin dördü (`sizes`→aspectRatio, `qualities`→resolution, `credential`,
# `wire_model`) birebir örtüşüyor, `supports_edit`/`max_refs` de video
# tarafında "görselden animasyon" olarak aynı soruyu soruyor. Ayrı bir sınıf,
# `short_labels`, `cost_for`, `geometry_of`, `provider_logo` ve
# `app._model_payload`ın hepsini iki tür alacak şekilde ikizlemek olurdu —
# tam olarak `short_labels`in "iki tür alıyor, ortak alanları okuyor"
# duruşunun önlemek için var olduğu şey. Sınıfın ADI artık türünden geniş,
# ama ad değiştirmek 5 modül + onlarca testin baktığı bir simgeyi kırardı.
#
# ÖLÜ UÇLAR BİLEREK YOK — üçü de araştırıldı ve üçü de kataloğa GİRMEDİ:
#   • OpenAI Sora 2 / Videos API 24 Eylül 2026'da kapanıyor (`sora-2`,
#     `sora-2-pro` ve anlık görüntüleri; sonrasında 410) ve OpenAI yerine
#     gelecek bir ad VERMİYOR. Girmesi `openai-dall-e-3` deneyiminin birebir
#     tekrarı olurdu: üç hafta sonra seçilebilir bir 410.
#   • Azure AI Foundry'de video YOK: `sora` 28 Şubat 2026'da, `sora-2`
#     14 Eylül 2026'da kalkıyor ve Foundry'de geçilecek başka video modeli
#     barındırılmıyor.
#   • Anthropic'in video ucu yok (görsel için `CREDENTIALS`ta yazılı olanın
#     aynısı).
# fal.ai ve Replicate GERÇEK adaylar (anahtar alanları v0.2.0'dan beri formda,
# bkz. app.py'nin "kataloğa girmemiş eski BYOK alanları" bloğu) ama adaptörleri
# yok; sırası kendi kuyruk adaptörleriyle birlikte.

DEFAULT_VIDEO_MODEL = "gemini-veo-3-1-lite"

# Veo'nun BELGELENMİŞ iki oranı. `ASPECT_RATIOS`in on jetonu burada
# KULLANILMIYOR ve bu eksik beyan bilinçli: Veo yalnız 16:9 ve 9:16 kabul
# ediyor, ötekiler telde 400 demek — yani arayüzde seçilebilir bir hata.
# Demetin paylaşılma gerekçesi `ASPECT_RATIOS`in aynısı: üç girdiye elle üç
# kez yazmak, birine oran ekleyip ötekini unutmanın kapısı olurdu.
VIDEO_ASPECT_RATIOS: tuple[str, ...] = ("16:9", "9:16")

# Veo 3.1'in klip süreleri. Sekiz saniye modelin tek üretimdeki tavanı;
# daha uzunu `extend-video` ile yapılıyor ve o BU TURDA KAPSAM DIŞI (kendi
# yetenek bayrağını ve kendi arayüz kontrolünü ister).
VIDEO_DURATIONS: tuple[int, ...] = (4, 6, 8)

# SIRA ANLAMLI (görsel modellerindeki kural) ve burada ARTAN MALİYETE göre:
# ilk girdi varsayılan, yani `DEFAULT_VIDEO_MODEL` en UCUZ kademe. Görsel
# tarafında varsayılan "en güçlü" (Azure'ın gpt-image-2'si), burada değil —
# ayrımın sebebi fiyat farkının BÜYÜKLÜĞÜ: yanlışlıkla atılan tek bir tık
# lite'ta 4 saniye için ~0,32 USD, kalite kademesinde ~1,60 USD. Bir
# görselde o fark sentlerle ölçülüyordu.
#
# KREDİ ÇAPASI görsel tarafındakiyle AYNI: Azure `medium` = 8 kredi ≈ 0,04 USD,
# yani 1 kredi ≈ 0,005 USD. Veo'nun yayınlanmış saniye fiyatları bu çapaya
# bölündü: lite ~0,08 USD/sn → 16, fast ~0,15 → 30, kalite ~0,40 → 80. Birim
# SANİYE (bkz. `credits` alanının yorumu), yani 8 saniyelik bir kalite klibi
# 640 kredi — ve bu, kullanıcıya "8 kredi"lik bir görselle GERÇEK bir
# karşılaştırma veriyor.
#
# `qualities` ÜÇ GİRDİDE AYNI DEĞİL ve bu da eksik beyan disiplini: Gemini'nin
# belgesi `resolution`ı "Veo 3 modellerinde desteklenir, varsayılan 720p"
# diyor ve 1080p'yi yalnız tam kademe için AÇIKÇA sayıyor. Fast/lite'ın
# 1080p'si bu depoda doğrulanmadı, o yüzden tek jeton beyan ediyorlar ve
# `quality_hidden=True` ile knob'u hiç göstermiyorlar — doğrulanmamış bir
# jeton beyan etmek arayüzde seçilebilir bir 400, eksik beyan etmek ise
# yalnızca bir yeteneği kullanmamak. 4K de aynı sebeple YOK.
#
# `poll_timeout` bir BEKLENTİ değil TAVAN: üretim tipik olarak 1-3 dakika
# sürüyor, buradaki sayı döngünün duvar saati sınırı (bkz.
# providers.total_budget ve veo_client'in son tarih hesabı).

VIDEO_MODELS: tuple[ImageModel, ...] = (
    ImageModel(
        id=DEFAULT_VIDEO_MODEL,
        label="Gemini · Veo 3.1 Lite",
        provider="gemini",
        wire_model="veo-3.1-lite-generate-preview",
        # Kimlik GÖRSEL tarafıyla PAYLAŞILIYOR: aynı `GEMINI_API_KEY`, aynı
        # konak. İkinci bir `Credential` açmak kullanıcıdan aynı anahtarı iki
        # kez istemek olurdu (`ChatModel.endpoint_path`in yorumundaki gerekçe).
        credential="gemini",
        sizes=VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p",),
        quality_hidden=True,
        durations=VIDEO_DURATIONS,
        # En kısa süre varsayılan: aynı "yanlış tık pahalı olmasın" kararı.
        default_duration=4,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # Veo 3.1'in ailesi; ilk/son kare geçişi ÜÇÜNDE de var.
        supports_last_frame=True,
        poll_timeout=420.0,
        credits=16,
        kind="video",
        note="En ucuz Veo. Gemini anahtarının ödemesi AÇIK olmalı.",
    ),
    ImageModel(
        id="gemini-veo-3-1-fast",
        label="Gemini · Veo 3.1 Fast",
        provider="gemini",
        wire_model="veo-3.1-fast-generate-preview",
        credential="gemini",
        sizes=VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p",),
        quality_hidden=True,
        durations=VIDEO_DURATIONS,
        default_duration=4,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # Veo 3.1'in ailesi; ilk/son kare geçişi ÜÇÜNDE de var.
        supports_last_frame=True,
        poll_timeout=420.0,
        credits=30,
        kind="video",
        note="Hız ile kalite arasında denge; sesi de kendi üretiyor.",
    ),
    ImageModel(
        id="gemini-veo-3-1",
        label="Gemini · Veo 3.1",
        provider="gemini",
        wire_model="veo-3.1-generate-preview",
        credential="gemini",
        sizes=VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p", "1080p"),
        default_quality="720p",
        durations=VIDEO_DURATIONS,
        default_duration=4,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # Veo 3.1'in ailesi; ilk/son kare geçişi ÜÇÜNDE de var.
        supports_last_frame=True,
        # 1080p'lik sekiz saniye en uzun süren üretim; tavan ona göre.
        poll_timeout=600.0,
        credits=80,
        kind="video",
        note="En iyi Veo, 1080p açık. Saniyesi pahalı — süreye dikkat.",
    ),
)


# ── Arayüz etiketleri ───────────────────────────────────────────────────
#
# Jeton → (etiket, oran). MODEL BAŞINA değil ORTAK: jetonlar sağlayıcılar
# arasında büyük ölçüde tekrar ediyor (`1024x1024` üçünde de var) ve her modele
# kendi etiket listesini yazdırmak aynı Türkçe dizeyi N kez bakıma sokardı.
#
# Etiketler burada, `static/core.js`'te DEĞİL. Öncesinde core.js'te `SIZE_RATIO`
# adında `ALLOWED_SIZES`'ın elle tutulan bir AYNASI vardı; çoklu modelde o ayna
# kaçınılmaz olarak bayatlardı — arayüz bir oranı gösterirken sunucu başka bir
# jeton beklerdi. Şimdi tek kaynak burası ve `/api/settings` etiketi de
# yetenekle BİRLİKTE gönderiyor.
#
# Bilinmeyen jeton HATA DEĞİL: etiketi kendisi olur (bkz. geometry_of). Yeni bir
# sağlayıcı eklerken etiketi unutmak, o modelin arayüzde HİÇ görünmemesine yol
# açmamalı — ham jeton çirkin ama çalışır.
GEOMETRY_LABELS: dict[str, tuple[str, str]] = {
    "1024x1024": ("◼ 1:1", "1:1"),
    "1024x1536": ("▮ 2:3", "2:3"),
    "1536x1024": ("▬ 3:2", "3:2"),
    # Gemini'nin oran jetonları (bkz. ASPECT_RATIOS). `ratio` sütunu jetonun
    # KENDİSİ — `geometry_of`un varsayılanı da bunu verirdi, ama o zaman
    # `label` da çıplak jeton olurdu ve seçicide Azure'ın glif'li satırlarıyla
    # aynı hizada durmazdı. Glif YÖNÜ söylüyor: ◼ kare, ▮ dikey, ▬ yatay.
    #
    # 1:1 / 2:3 / 3:2 burada AYRICA yazılmıyor: Azure'ın `1024x1024`ü zaten
    # `ratio="1:1"` bildiriyor, ama JETON farklı ("1024x1024" ≠ "1:1"), yani
    # ikisi de kendi satırına ihtiyaç duyuyor.
    "2:3": ("▮ 2:3", "2:3"),
    "3:2": ("▬ 3:2", "3:2"),
    "1:1": ("◼ 1:1", "1:1"),
    "3:4": ("▮ 3:4", "3:4"),
    "4:3": ("▬ 4:3", "4:3"),
    "4:5": ("▮ 4:5", "4:5"),
    "5:4": ("▬ 5:4", "5:4"),
    "9:16": ("▮ 9:16", "9:16"),
    "16:9": ("▬ 16:9", "16:9"),
    "21:9": ("▬ 21:9", "21:9"),
    # MAI'nin bütçeye uyan jetonları (bkz. MAI_SIZES). `ratio` sütunu Azure ve
    # Gemini'nin oranlarıyla AYNI dizeleri veriyor — `fillAxis`in ikinci
    # kademesi model değiştirirken oranı böyle taşıyor. Glif YÖNÜ söylüyor:
    # ◼ kare, ▮ dikey, ▬ yatay.
    "1024x768": ("▬ 4:3", "4:3"),
    "768x1024": ("▮ 3:4", "3:4"),
    "1248x832": ("▬ 3:2", "3:2"),
    "832x1248": ("▮ 2:3", "2:3"),
    "1365x768": ("▬ 16:9", "16:9"),
    "768x1365": ("▮ 9:16", "9:16"),
}

QUALITY_LABELS: dict[str, str] = {
    "low": "Düşük",
    "medium": "Orta",
    "high": "Yüksek",
    # Kalite ekseni OLMAYAN modellerin sentetik jetonu (bkz. karar Q1).
    # Bugün onu taşıyan GERÇEK bir model yok (DALL·E 3 gitti, Gemini'nin
    # çözünürlük ekseni var); jeton yine de duruyor çünkü `quality_hidden`
    # sözleşmesinin belgelenmiş karşılığı bu ve testler onu kullanıyor.
    "standard": "Standart",
    # Gemini'nin `image_size` jetonları. Piksel yerine MEGAPİKSEL yazılı:
    # oran seçen bir modelde "2048x2048" demek yanlış olurdu (2K, seçilen
    # orana göre farklı piksel boyutlarına çözülüyor).
    "1K": "1K · 1 MP",
    "2K": "2K · 4 MP",
    "4K": "4K · 16 MP",
    # Veo'nun `resolution` jetonları. Video tarafında MEGAPİKSEL yazmak yanlış
    # olurdu: video dünyasında ölçü satır sayısıdır ve kullanıcı "720p"yi
    # zaten öyle tanıyor.
    "720p": "720p · HD",
    "1080p": "1080p · Full HD",
    # FLUX.2-flex'in `steps`/`guidance` kademeleri. Sentetik bir jeton İSRAF
    # olurdu: belgelenmiş `steps` (≤50) ve `guidance` (1.5–10) kaliteyi
    # DOĞRUDAN belirliyor, yani burada gerçek bir eksen var (karar 4).
    #
    # JETONLAR ASCII ve bu deponun kurulu deseni: `low`, `1K`, `720p`, tema
    # adları — hepsi ASCII. Jeton `history.json`a, `prefs.json`a ve
    # `ResultParams.quality`ye yazılıyor; Türkçe metin ETİKETTE yaşıyor.
    # Jetonlar sağlayıcıya GİTMİYOR: `azure_flux_client.quality_axis` onları
    # sayılara çeviriyor.
    "hizli": "Hızlı · 10 adım",
    "dengeli": "Dengeli · 25 adım",
    "detayli": "Detaylı · 50 adım",
}


def geometry_of(token: str) -> tuple[str, str]:
    """(etiket, oran). Bilinmeyen jetonda ikisi de jetonun kendisi."""
    return GEOMETRY_LABELS.get(token, (token, token))


def quality_label(token: str) -> str:
    return QUALITY_LABELS.get(token, token)


def default_size_of(m: ImageModel) -> str:
    return m.default_size or m.sizes[0]


def default_quality_of(m: ImageModel) -> str:
    return m.default_quality or m.qualities[0]


def default_duration_of(m: ImageModel) -> int:
    """Arayüzün ilk seçeceği süre; süre ekseni olmayan modelde 0.

    `default_size_of`/`default_quality_of` ile aynı desen, tek farkı BOŞ
    DEMET hâli: onların `sizes`/`qualities`i hiç boş olamıyor (kalite ekseni
    olmayan model sentetik bir jeton beyan ediyor), süre ekseni ise gerçekten
    yok olabiliyor ve `m.durations[0]` o modelde IndexError olurdu.
    """
    if not m.durations:
        return 0
    return m.default_duration or m.durations[0]


def duration_label(seconds: int) -> str:
    """Süre jetonunun arayüzdeki etiketi.

    `GEOMETRY_LABELS`/`QUALITY_LABELS` gibi bir tablo YOK ve gerekmiyor:
    jeton sayı olduğu için etiket ondan türetilebiliyor. Tablo açmak, her
    yeni süre değerinde ikinci bir yere satır eklemeyi unutmanın kapısı
    olurdu — ve etiketi unutulan jeton arayüzde çıplak sayı olarak görünürdü.
    Etiketin SUNUCUDA türetilmesi ise `GEOMETRY_LABELS`in gerekçesiyle aynı:
    istemcide kurulan bir dize, aynı bilginin bayatlayabilen ikinci kopyası.
    """
    return f"{seconds} sn"


# ── Sohbet modelleri ────────────────────────────────────────────────────

DEFAULT_CHAT_PROVIDER = "azure"
DEFAULT_CHAT_MODEL = "azure-deployment"

# SIRA ANLAMLI, görsel modellerindeki gibi: seçicinin sırası bu ve ilk girdi
# varsayılan. Azure BAŞTA KALIYOR — `DEFAULT_CHAT_MODEL` ve
# `prefs.DEFAULTS["chat_provider"]` onu gösteriyor; varsayılanı değiştirmek
# kayıtlı bir kullanıcının yönetmenini sessizce başka bir sağlayıcıya, yani
# başka bir faturaya taşımak olurdu.
#
# ÜÇ SAĞLAYICININ TELİ AYNI: `POST …/chat/completions`, `{"model","messages"}`
# gövdesi, `choices[0].message.content` yanıtı, `Authorization: Bearer`
# başlığı. Azure'ın kendi istemcisi (`chat_client`) DURUYOR ve baytları
# değişmiyor; OpenAI ile Gemini `openai_chat` üzerinden gidiyor (bkz. o
# dosyanın başlığı: `openai_client`'ın `azure_client`'a duruşunun aynısı).
# Gemini'nin tek farkı YOL: OpenAI-uyumlu ucu `/v1beta/openai/` altında
# yaşıyor, `endpoint_path` alanı tam olarak bu yüzden var.
#
# ANTHROPIC BİLEREK YOK. Kimliği (`anthropic`) katalogda duruyor ama Ayarlar
# formunda anahtarını girecek bir kutu yok, yani "anahtarı olan modelleri
# göster" kuralı onu HER koşulda gizlerdi: girdiyi eklemek, hiç seçilemeyecek
# bir satır eklemek olurdu. Teli de bu üçünün aynısı değil — `/v1/messages`,
# `system` ayrı alan, `max_tokens` ZORUNLU (`needs_max_tokens` alanı tam olarak
# o günü bekliyor) — yani `openai_chat`a da düşmüyor. Sırası: forma anahtar
# kutusu + kendi adaptörü, birlikte.
#
# MODEL ADLARI (`wire_model`) 21 Ağustos 2026'da belgeden doğrulandı:
# `gpt-5.6-sol` / `-terra` / `-luna` üçlüsü 9 Temmuz 2026'da GA oldu (çıplak
# `gpt-5.6` alias'ı sol'a gidiyor), `gemini-3.7-flash` 13 Ağustos 2026'da.
# Gemini'nin Pro'su BİLEREK yok: bugün yalnız `gemini-3.1-pro-preview` var ve
# bu depoda "preview" jetonu beyan etmiyoruz — kalkmış bir ad, arayüzde
# seçilebilir bir 404 demek (bkz. DALL·E 3'ün katalogdan çıkarılma gerekçesi).
CHAT_MODELS: tuple[ChatModel, ...] = (
    ChatModel(
        id=DEFAULT_CHAT_MODEL,
        label="Azure AI Foundry dağıtımı",
        provider="azure",
        credential="azure_chat",
        wire_model="",                          # ORTAMDAN okunuyor
        wire_from_env="AZURE_CHAT_DEPLOYMENT",
        note="Adı Ayarlar'dan giriliyor: Azure'da model değil DAĞITIM var.",
    ),
    # GPT-5.6 ailesinin üç kademesi. Üçü de AYNI tel, yalnız `wire_model`
    # farklı — o yüzden üçü de tek adaptörden geçiyor ve yeni bir kademe
    # eklemek tek satır. Sıra ucuzdan pahalıya DEĞİL, "önce dengeli olan":
    # varsayılan seçim faturayı yönetmenin en pahalı kademesine bağlamamalı.
    ChatModel(
        id="openai-gpt-5.6-terra",
        label="OpenAI · GPT-5.6 Terra",
        provider="openai",
        credential="openai",
        wire_model="gpt-5.6-terra",
        note="Dengeli kademe — günlük brief'ler için varsayılan.",
    ),
    ChatModel(
        id="openai-gpt-5.6-luna",
        label="OpenAI · GPT-5.6 Luna",
        provider="openai",
        credential="openai",
        wire_model="gpt-5.6-luna",
        note="En ucuz ve en hızlı kademe; kısa turlar için.",
    ),
    ChatModel(
        id="openai-gpt-5.6-sol",
        label="OpenAI · GPT-5.6 Sol",
        provider="openai",
        credential="openai",
        wire_model="gpt-5.6-sol",
        note="Ailenin en güçlüsü ve en pahalısı; uzun, çok kısıtlı brief'ler için.",
    ),
    ChatModel(
        id="gemini-3.7-flash",
        label="Gemini · 3.7 Flash",
        provider="gemini",
        credential="gemini",
        wire_model="gemini-3.7-flash",
        # Görsel tarafı `/v1beta/interactions` konuşuyor; sohbet tarafı
        # OpenAI-uyumlu uçtan gidiyor. Aynı kimlik, iki ayrı yol.
        endpoint_path="/v1beta/openai/chat/completions",
        note="Gemini'nin OpenAI-uyumlu ucundan konuşuyor; hızlı ve ucuz.",
    ),
)


# ── Erişim ──────────────────────────────────────────────────────────────
#
# Hepsi saf: dosya okumuyor, istisna yükseltmiyor (arama başarısızsa None).
# "Yapılandırılmış mı?" sorusu BURADA CEVAPLANMIYOR — o G/Ç ve `credstore`'un
# işi. Katalog neyin VAR OLDUĞUNU bilir, neyin ERİŞİLEBİLİR olduğunu bilmez.


def image_model(model_id: str) -> ImageModel | None:
    for m in IMAGE_MODELS:
        if m.id == model_id:
            return m
    return None


def image_model_ids() -> tuple[str, ...]:
    return tuple(m.id for m in IMAGE_MODELS)


def video_model(model_id: str) -> ImageModel | None:
    """`image_model`in ikizi, `VIDEO_MODELS` üzerinde.

    AYRI bir fonksiyon ve iki demeti birden tarayan tek bir arama YOK: bugün
    hiçbir çağıran "görsel mi video mu, fark etmez" demiyor — `/api/generate`
    yalnız görseli, `/api/video` yalnız videoyu kabul ediyor ve o ayrım
    ucun sözleşmesi. Birleşik bir arama, yanlış türü doğru sanan bir
    çağıranı sessizce geçirirdi.
    """
    for m in VIDEO_MODELS:
        if m.id == model_id:
            return m
    return None


def video_model_ids() -> tuple[str, ...]:
    return tuple(m.id for m in VIDEO_MODELS)


def chat_model(model_id: str) -> ChatModel | None:
    for m in CHAT_MODELS:
        if m.id == model_id:
            return m
    return None


def chat_models_for(provider: str) -> tuple[ChatModel, ...]:
    return tuple(m for m in CHAT_MODELS if m.provider == provider)


def chat_model_ids() -> tuple[str, ...]:
    return tuple(m.id for m in CHAT_MODELS)


def chat_needs_deployment(m: ChatModel) -> bool:
    """Adı kullanıcının GİRMESİ gereken model mi (Ayarlar'daki dağıtım kutusu).

    Tek ölçüt `wire_from_env`: adı katalogda yazamıyorsak kullanıcıdan almak
    zorundayız. Ayarlar formu bu bayrağı `/api/settings` → `chat_models[]`
    üzerinden okuyor ve dağıtım alanını YALNIZCA onu isteyen sağlayıcı
    seçiliyken gösteriyor — OpenAI/Gemini kullanıcısına doldurulamayan bir
    kutu göstermek, 360px'lik bir panelde ödenmiş boş yer demekti.
    """
    return bool(m.wire_from_env)


def provider_logo(provider: str) -> str | None:
    """Sağlayıcının işaret dosyasının ADI; tanımsızsa None.

    None SESSİZ bir yol ve bilinçli: işareti olmayan bir sağlayıcı eklendiğinde
    şerit işaretsiz çiziliyor, hata vermiyor — bir logo eksikliği üretimi
    engellememeli. Eksikliği yüksek sesle söyleyen yer TEST
    (tests/test_provider_logos.py), çalışma zamanı değil.
    """
    return PROVIDER_LOGOS.get(provider)


# Marka ile adın arasındaki ayraç. Etiketlerin yazım kuralı bu ve `_drop_brand`
# aynı dizeyi hem ARIYOR hem UZUNLUĞUNU kullanıyor: iki yerde ayrı yazılmış
# olsaydı ("· " ile " · ") kırpma bir karakter kayar ve ad boşlukla başlardı.
_BRAND_SEP = " · "


def _drop_brand(label: str, provider: str) -> str:
    marka = PROVIDER_BRANDS.get(provider)
    if not marka:
        return label
    onek = f"{marka}{_BRAND_SEP}"
    return label[len(onek):] if label.startswith(onek) else label


def short_labels(
    models: Sequence[ImageModel] | Sequence[ChatModel],
) -> dict[str, str]:
    """Model id → ŞERİTTE gösterilecek ad: marka öneki düşürülmüş `label`.

    ÇAKIŞMA KURALI tek istisna ve ölçülmüş bir kırılmayı kapatıyor: önek
    düşünce `Azure · gpt-image-2` ile `OpenAI · gpt-image-2` AYNI satıra
    dönüşüyor — ikisinin de anahtarı olan kullanıcı açılan listede hangisini
    seçtiğini bilemez ve native bir `<option>` işaret taşıyamıyor, yani logo o
    satırları ayırmıyor. O yüzden kısa adı bir başkasıyla çakışan model TAM
    etiketini koruyor. Kullanıcının gördüğü fark şu: markası tekil olan her
    model (Gemini'nin ikisi, OpenAI'nin sohbet kademeleri) önekini bırakıyor,
    yalnız gerçekten iki yerde birden bulunan ad markasını taşımaya devam
    ediyor.

    Önek `f"{marka} · "` deseniyle aranıyor, "içinde marka geçiyor mu" diye
    DEĞİL: Azure'ın sohbet girdisi `Azure AI Foundry dağıtımı` ve orada marka
    adın PARÇASI (Azure'da model yok, dağıtım var) — kırpılırsa etiket
    anlamsızlaşır.

    `models` iki tür alıyor (`ImageModel` ve `ChatModel`); ortak alan olarak
    yalnız `id`, `label` ve `provider` okunuyor.
    """
    kisa = {m.id: _drop_brand(m.label, m.provider) for m in models}
    adlar = list(kisa.values())
    cakisan = {ad for ad in adlar if adlar.count(ad) > 1}
    return {m.id: (m.label if kisa[m.id] in cakisan else kisa[m.id])
            for m in models}


def chat_provider_ids() -> tuple[str, ...]:
    """Sağlayıcı kimlikleri, katalogdaki İLK GÖRÜLME sırasıyla (tekilleştirilmiş).

    `set` DEĞİL: sıra arayüzdeki seçicinin sırası ve varsayılan başta durmalı.
    """
    seen: list[str] = []
    for m in CHAT_MODELS:
        if m.provider not in seen:
            seen.append(m.provider)
    return tuple(seen)


def credential(cred_id: str) -> Credential | None:
    for c in CREDENTIALS:
        if c.id == cred_id:
            return c
    return None


def cost_for(m: ImageModel, quality: str, n: int = 1, *,
             duration: int = 0) -> int:
    """Bir turun kredi maliyeti. TEK hesaplama noktası.

    Bilinmeyen kalite `credits` tabanına düşüyor, hata YÜKSELTMİYOR: maliyet
    metadata'sı bir üretimi engellememeli. Kalitenin geçerliliği zaten
    `GenerateRequest`'in yetenek kapısında yüksek sesle doğrulanıyor; burada
    ikinci bir 500 üretmek yalnızca üretimi kaybettirirdi.

    `duration` VERİLDİYSE taban saniye başına yorumlanıyor — `credits`
    alanının `kind`e bağlı birimi (bkz. o alanın yorumu) burada, tek bir
    çarpma olarak yaşıyor. Anahtar argüman olması bilinçli: görsel
    çağıranların hiçbiri değişmiyor ve bir gün üçüncü bir eksen gelirse
    konumlu bir parametre sırası kırılmıyor.

    0 ve None AYNI anlamda ("süre ekseni yok"): `default_duration_of` süre
    ekseni olmayan modelde 0 döndürüyor ve o değer buraya doğrudan
    akabiliyor. Çarpan olarak 0 kullanmak, ücretsiz görünen bir video
    demekti.
    """
    per = dict(m.credits_by_quality).get(quality, m.credits)
    return per * n * (duration or 1)


def secret_field_names() -> frozenset[str]:
    """`SettingsRequest`'teki GİZLİ alan adları — redaksiyon buradan besleniyor."""
    return frozenset(c.secret_field for c in CREDENTIALS if c.secret_field)


def secret_env_names() -> frozenset[str]:
    """Gizli değer taşıyan env adları — `errlog` testi buradan doğrulanıyor.

    Adres (`url_env`) DIŞARIDA: endpoint gizli değil, `get_settings_status`
    onu bugün de açıkça döndürüyor.
    """
    return frozenset(c.key_env for c in CREDENTIALS)
