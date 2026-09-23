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

DÜZ-MODÜL KISITI KALKTI (2026-09-16, Faz 0 / Adım 1). Bu dosya bir zamanlar
"KÖKTE ve DÜZ olmak ZORUNDA" diyordu: `android/app/build.gradle` Chaquopy
kaynak kümesini `include "*.py"` ile kuruyor, yani APK'ya YALNIZ kök
düzeyindeki .py dosyaları giriyor ve bir `providers/` alt paketi masaüstünde
çalışıp telefonda `ModuleNotFoundError` verirdi; `tests/test_android_packaging.py`
bunu mandallıyordu. Masaüstü ve Android paketleri v0.23.1'de DONDURULDU
(paketleme yalnız elle, bkz. docs/faz0-web-first.md) ve o mandal silindi:
kod artık `routers/`, `services/` gibi paketlere taşınabilir. Katalog bugün
hâlâ kökte düz bir dosya — alışkanlıktan değil, henüz taşınmadığı için.
Android bir gün geri gelirse ince bir WebView kabuğu olarak gelir, Python
çalışma zamanını taşımaz; kısıt o hâliyle de geri gelmez.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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
    # İKİNCİ TEL YOLU (`wire_model`in ikizi) — yalnız uçları AYRIŞMIŞ
    # sağlayıcıda dolu.
    #
    # BURADA, `wire_model`in yanında DEĞİL: `dataclasses` varsayılanlı bir
    # alandan sonra varsayılansız alan kabul etmiyor ve `wire_model`i
    # `credential`, `sizes`, `qualities`, `max_n`, `credits` izliyor. Yerleşim
    # teknik zorunluluk, üslup tercihi değil.
    #
    # fal.ai'da metin→video ve görsel→video AYRI uçlar
    # (`…/text-to-video` ≠ `…/image-to-video`), oysa Azure, Gemini, MAI ve
    # FLUX'ta düzenleme aynı ucun bir ALANI. "" = ikisi aynı uca gidiyor,
    # yani bugünkü on üç girdinin hiçbirinin teli değişmiyor.
    #
    # UÇ YOLUNU ADAPTÖRDE TÜRETMEK reddedildi: kural ilk istisnada kırılıyor
    # (`fal-ai/veo3.1` metin tarafında ÇIPLAK, görsel tarafında
    # `/image-to-video`) ve kırılma telde 404 olarak görünürdü — bu dosyanın
    # her yerde uyardığı "arayüzde seçilebilir hata".
    #
    # MODEL BAŞINA İKİ GİRDİ de reddedildi: şerit iki kart gösterir ve
    # kullanıcı "(metin)" / "(görsel)" ayrımını elle yapardı — oysa
    # `supports_edit` bayrağı tam olarak bu ayrımı SAKLAMAK için var.
    wire_model_edit: str = ""
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
    # Seçicide gösterilen kısa açıklama. Değer METİN DEĞİL ÇEVİRİ ANAHTARI
    # (`model.<id>.note`) ve çözüm `app._model_payload`da: katalog dilsiz
    # kalmalı — onu on üç modül ithal ediyor ve hiçbirinin dille işi yok.
    note: str | None = None
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
    # EMEKLİLİK GÜNÜ (Faz 4 / 1b-D, 2026-09-23) — sağlayıcının duyurduğu kapanış
    # tarihi; None = duyuru yok. BUGÜN HİÇBİR GİRDİ DOLDURMUYOR ve alan yine de
    # burada, çünkü kalkacağı belli olan girdinin bedeli ÜÇ KEZ ölçüldü:
    # `openai-dall-e-3` (kullanıcı seçebiliyor, üretim 404), `openai-gpt-image-1`
    # (23 Ekim 2026 emekliliği, 2026-09-21'de silindi) ve `gpt-image-1.5`/
    # `-mini` (1 Aralık 2026, girdileri yok). Üçünde de tarih bir YORUMDA
    # yaşıyordu ve yorumu hiçbir araç saymıyor. Tarih VERİ olunca
    # `tools/tarife_kontrol.py` "30 gün içinde emekli olacak model" satırını
    # basar ve sahip girdiyi emeklilik gününü beklemeden siler (kurulu duruş:
    # ölü girdi katalogda kalmaz). Bekçisi tests/test_araclar.py (tarih yamalı).
    # Kapı DEĞİL, rapor: alan dolu diye üretim engellenmez — `cost_for` gibi
    # metadata, kullanıcıya hata değil sahibe uyarı üretir.
    emeklilik: date | None = None


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
    # Seçicide gösterilen kısa açıklama. Değer METİN DEĞİL ÇEVİRİ ANAHTARI
    # (`model.<id>.note`) ve çözüm `app._model_payload`da: katalog dilsiz
    # kalmalı — onu on üç modül ithal ediyor ve hiçbirinin dille işi yok.
    note: str | None = None
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
        label="credential.azure_image",
        key_env="AZURE_IMAGE_API_KEY",
        url_env="AZURE_IMAGE_BASE_URL",
        secret_field="api_key",
        url_field="base_url",
    ),
    Credential(
        id="azure_chat",
        label="credential.azure_chat",
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
        label="credential.azure_foundry",
        key_env="AZURE_FOUNDRY_API_KEY",
        url_env="AZURE_FOUNDRY_BASE_URL",
        secret_field=None,
        url_field="azure_foundry_base_url",
    ),
    # fal.ai — TOPLAYICI: tek anahtar, çok model. v0.23'te yalnız VİDEO
    # tablosuna girdi (`providers._VIDEO_ADAPTERS`); 2026-09-23'te (Faz 4 /
    # 1b-D) GÖRSEL tablosuna da (`providers._ADAPTERS`) — kimlik aynı, ikinci
    # bir anahtar istenmiyor.
    #
    # `FAL_KEY` YENİ DEĞİL: v0.2.0'dan beri `POST /api/settings`'te kabul
    # ediliyordu ama kataloğa girmediği için hem redaksiyonun hem de formun
    # DIŞINDAYDI — bugüne kadar yalnız `curl` ile yazılabiliyordu.
    #
    # `url_field=None` ve bu `azure_chat`in duruşunun aynısı: fal'da
    # kullanıcıya özel endpoint YOK, adres tek ve sabit. Vekil arkasına almak
    # isteyen `credentials.env`'e `FAL_BASE_URL` yazıyor — forma alan
    # eklemeden (OpenAI girdisindeki aynı gerekçe).
    Credential(
        id="fal",
        label="fal.ai",
        key_env="FAL_KEY",
        url_env="FAL_BASE_URL",
        default_base_url="https://queue.fal.run",
        secret_field="fal_key",
        url_field=None,
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
    "fal": "fal.svg",
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
    # fal'ın modelleri kendi ÜRETİCİ adlarını taşıyor ("Alibaba · Wan 3.0",
    # "PixVerse · C1", "Kling · V3 Turbo Pro"), "fal" ile BAŞLAMIYOR — yani
    # `_strip_brand_prefix` burada hiç eşleşmiyor ve etiketler bütün kalıyor.
    # Girdi yine de gerekli: `test_the_video_providers_all_have_a_LOGO`
    # `m.provider in PROVIDER_BRANDS` istiyor ve `Credential(id="fal").label`
    # ile aynı dizeyi kullanmak ikinci bir ad icat etmekten iyi.
    "fal": "fal.ai",
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

# fal'ın MEGAPİKSEL faturası YUKARI yuvarlıyor (Faz 4 / 1b-D): 1024×1024 =
# 1.048.576 piksel İKİ MP sayılır. İki fal görsel girdisinin kümesi bu yüzden
# fiyat basamağına göre seçildi; gpt-image-2'nin üçlüsü KOPYALANMADI.
#
# Qwen Image — modelin kendi önerdiği beş geometri (Qwen-Image model kartı):
# hepsi 1,5–1,8 MP, yani fal'da iki MP → 0,04 USD → 8 kredi. Kümeyi 1 MP'nin
# altına çekmek krediyi 4'e düşürürdü ama modelin eğitildiği çözünürlüğün
# yarısına inmek olurdu — burada kalite fiyattan önce geliyor, schnell'de tersi.
# Mandal: tests/test_catalog.py::test_qwen_jetonlari_IKI_megapikseli_ASMIYOR.
QWEN_SIZES: tuple[str, ...] = (
    "1328x1328",   # 1.763.584 · 1:1
    "1472x1104",   # 1.625.088 · 4:3
    "1104x1472",   # 1.625.088 · 3:4
    "1664x928",    # 1.544.192 · 16:9
    "928x1664",    # 1.544.192 · 9:16
)

# FLUX.1 [schnell] — ÜCRETSİZ PLANIN 1 KREDİLİK MODELİ (belge §1b "13. satır"):
# küme 1 MP'nin KESİNLİKLE altında, yoksa 0,003 USD/MP'lik fiyat iki MP'ye
# çıkar ve kredi 1 değil 2 olur. Beşi de 32'nin katı (FLUX'un adım kısıtı) ve
# ilk beş oranı karşılıyor; 1024×1024 BİLEREK YOK.
# Mandal: tests/test_catalog.py::test_schnell_jetonlari_BIR_megapikselin_ALTINDA.
SCHNELL_SIZES: tuple[str, ...] = (
    "960x960",     #   921.600 · 1:1
    "1024x768",    #   786.432 · 4:3
    "768x1024",    #   786.432 · 3:4
    "1024x576",    #   589.824 · 16:9
    "576x1024",    #   589.824 · 9:16
)


# KREDİ ÇAPASI, SAYI OLARAK (Faz 3 / 5): aşağıdaki yorum bloklarının tekrar
# tekrar yazdığı oran — 1 kredi = 0,005 USD.
#
# ÇAPA ARTIK SEÇİLMİŞ BİR ORAN, TÜRETİLMİŞ DEĞİL (Faz 4 / 1b, karar 1b-F).
# 0,005 bu dosyaya "Azure `medium` = 8 kredi ≈ 0,04 USD" denkleminden girmişti
# ve o denklem 2026-09-22'de ÖLDÜ: `gpt-image-2`nin kalite başına çıktı jetonu
# ilk kez ölçüldü (196 / 1.756 / 7.024) ve `medium` 0,04 değil **0,0527 USD**
# çıktı — aynı cümleyi yeni sayıyla yeniden türetsen çapa 0,0066 olurdu.
# Oran yine de DEĞİŞMEDİ, çünkü çapa sağlayıcının fiyatı değil bizim
# tarifemizin birimi: değiştirmek katalogdaki her satırı ve admin marj
# tablosunu birden kaydırırdı, geçmiş kayıtlar ise zaten donmuş.
# Yani buradan sonra hiçbir MODEL çapayı tanımlamıyor; modeller çapaya
# BÖLÜNÜYOR. Yuvarlama EN YAKIN tam sayıya (ayrımı gösteren tek örnek
# `azure-gpt-image-2` `medium`: 10,54 → 11; gerekçe o girdide).
#
# Admin "Marj" tablosu (services/depo_admin.py `marj`) ve
# `tools/tarife_kontrol.py` "bu kadar kredi ≈ kaç USD" derken buradan okur;
# yorumdaki sayı ile koddaki sayı tek yerde dursun. Bu bir ORAN, sağlayıcının
# fiyatı değil: gerçek fatura `isler.saglayici_maliyet_usd`e gelir, rapor ikisini
# yan yana koyar. `Decimal`: `numeric(10,6)` sütunuyla çarpılıyor, float değil.
KREDI_USD_CAPASI = Decimal("0.005")


# ── Görsel modelleri ────────────────────────────────────────────────────
#
# SIRA ANLAMLI: arayüzdeki seçicinin sırası bu — SAHİBİN SIRALI LİSTESİ (belge
# docs/faz4-odeme-abonelik-kvkk.md §1b "Sıralı görsel listesi (13)"),
# kaliteli/popüler → ucuz. VARSAYILAN SIRADAN AYRI: `DEFAULT_IMAGE_MODEL` bir
# SABİT ve hiçbir kod demetin indeks 0'ına bakmıyor (`image_model` id ile
# arıyor). Bu satır 2026-09-23'e kadar "ilk girdi varsayılan" diyordu — o
# yalnız o günkü yerleşimin tarifiydi ve liste sıralanınca yanlış okunurdu
# (belge §1b "SIRA İLE VARSAYILAN KODDA AYRI, YORUMDA DEĞİL"). Görselde
# varsayılan tesadüfen 1. sırada, videoda 10. sırada (bkz. VIDEO_MODELS).
# Mandal: tests/test_catalog.py::test_the_image_catalog_follows_the_owners_RANKED_list.
#
# Kredi değerleri BİZİM tarifemiz, sağlayıcının fiyatı değil — yani doğrulanacak
# bir olgu değil, ürün kararı. Bugün yalnız METADATA: hiçbir yerde bakiye
# düşülmüyor, hiçbir üretim engellenmiyor. Kayda ÜRETİM ANINDAKİ çözülmüş tam
# sayı yazılıyor (bkz. cost_for ve storage.save), katalog işaretçisi değil:
# tarife değişince geçmiş retroaktif olarak yeniden yazılmasın. İleride gelecek
# ledger'ın ihtiyacı olan tek şey o alan.
#
# ORANTI yine de keyfi değil, tek bir çapaya bağlı: 1 kredi = 0,005 USD
# (`KREDI_USD_CAPASI`, gerekçesi orada). Her girdinin kredisi kendi
# yayınlanmış görsel-başı fiyatının bu çapaya bölünmesiyle yazıldı (Nano Banana
# Pro 1K/2K ≈ 0,134 USD → 27, 4K ≈ 0,24 USD → 48). Böylece seçicideki kredi
# etiketi kullanıcıya GERÇEK bir karşılaştırma veriyor: "27 kredi" gerçekten
# "11 kredi"lik bir `gpt-image-2 medium`un iki buçuk katı kadar pahalı.
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
        # ÖLÇÜLDÜ 2026-09-22 (1b'nin devreden on birinci sayısı; ötekiler fiyat
        # sayfasından kapandı, bu kapanmadı): kalite başına ÇIKTI JETONU sayısı
        # hiçbir resmî yerde yayınlanmamış. Canlı anahtarla 1024x1024'te üç
        # üretim yapıldı, yanıttaki `usage.output_tokens` 196 / 1.756 / 7.024
        # (`output_tokens_details.image_tokens` aynı sayı). Birim 30 USD/1M
        # çıktı jetonu → 0,0059 / 0,0527 / 0,2107 USD; çapa 1 kredi = 0,005 USD
        # → 1,18 / 10,54 / 42,14, EN YAKIN tam sayıya yuvarlanınca
        # **1 / 11 / 42**. `gpt-image-1`in tablosu (272/1056/4160) TUTMUYOR:
        # bu yüzden eski modelden çıkarım değil ölçüm. `high` bugüne dek 16
        # kredide duruyordu, yani 2,6 kat eksik fiyatlanmıştı.
        #
        # `medium` 10 DEĞİL 11 ve tek ayrımı gösteren kademe bu: 10,54'ün
        # aşağı yuvarlanması dosyanın öteki girdileriyle çelişirdi (26,8 → 27,
        # 7,78 → 8, 9,62 → 10 hepsi EN YAKIN). `low` ve `high`ın küsuratı
        # 0,5'in altında, yani iki kuralda da aynı sayıyı veriyor — kural
        # ancak burada görünüyor ve burada yazılı olmak zorunda.
        credits=11,
        credits_by_quality=(("low", 1), ("medium", 11), ("high", 42)),
        note="model.azure-gpt-image-2.note",
    ),
    # ── OpenAI · GPT Image 2.5 (Faz 4 / 1b-E, 2026-09-23) ──────────────
    #
    # OpenAI 2026-09-08'de iki kardeş çıkardı: `gpt-image-2.5-flare` (hız) ve
    # `-sunburst` (düzenleme hassasiyeti). `gpt-image-2` EMEKLİ DEĞİL ve
    # `DEFAULT_IMAGE_MODEL` KAYMIYOR — 1b-E'nin iki katmanlı gerekçesi: (1)
    # varsayılanı kaydırmak E2E model seçici çapalarını, `test_catalog`ın
    # varsayılan iddialarını ve `prefs` doğrulamasını birlikte değiştirir;
    # (2) 2.5'in yetenek jetonları bu depoda DOĞRULANMADI.
    #
    # YETENEK JETONLARI `openai-gpt-image-2`DEN KOPYALANDI. Sahibin talimatı
    # (belge §1b "Sahibin adımı" 1): "jetonları `gpt-image-2`den KOPYALA".
    # OpenAI rehberi 2.5 için `low…xhigh, max, auto` kalite kümesi yazıyor ama
    # bu depoda hiçbir jeton canlı sınanmadı: doğrulanmamış jeton beyan etmek
    # arayüzde seçilebilir bir 400, eksik beyan yalnızca bir yeteneği
    # kullanmamak (`openai-gpt-image-2` girdisinin kurulmuş deseni). `xhigh`
    # (3.122 jeton → 19) ve `max` (7.024 → 42) bu yüzden YOK; eklenmesi
    # ayrı karar (belge §1b "Yapıldığında (D)").
    #
    # KREDİ KAYNAKTAN, KOPYA DEĞİL (sahibin araştırması, PR #80 yorumu,
    # 2026-09-23): OpenAI görsel üretim rehberi "Cost and latency" — çıktı
    # 30 USD/1M jeton (gpt-image-2 ile AYNI birim fiyat) ama kalite başına
    # JETON SAYISI farklı. Rehberdeki hesaplayıcının formülü
    #     jeton = ceil(g × o × (2e6 + W×H) / 4e6)
    # (g/o = kısa kenara oranla yuvarlanmış ızgara), kalite katsayıları
    # gpt-image-2 low 16 · medium 48 · high 96, gpt-image-2.5 low 16 ·
    # medium 24 · high 48 · xhigh 64 · max 96. SAĞLAMA: formül gpt-image-2'de
    # 1024×1024 için 196 / 1.756 / 7.024 veriyor — 2026-09-22'de canlı
    # `usage.output_tokens` ile ÖLÇÜLEN sayıların birebir aynısı; yani tablo
    # tahmin değil, ölçümle tutan kural. 2.5, 1024×1024: 196 / 439 / 1.756
    # jeton → 0,0059 / 0,0132 / 0,0527 USD → 1 / 3 / 11 kredi (çapa 0,005,
    # en yakına). Önceki 1/11/42 kopyası medium'da ×3,7, high'da ×3,8 fazla
    # alıyordu; `tarife_kontrol` notu düştü (2 → 0). Canlı ölçüm isteğe
    # bağlı sağlama, ön koşul değil.
    #
    # İKİ BİLİNEN SAPMA, bilerek açık (boyut başına kredi ekseni yok):
    # (1) dikey/yatay (1024×1536, 1536×1024) formülde KAREDEN UCUZ — 2.5
    # medium 343 → 2, high 1.372 → 8; katalog her boyuta kare fiyatını yazıyor,
    # yani dikey/yatayda ~%25 fazla alınıyor (gpt-image-2'de de öyle). (2)
    # GÖRSEL GİRDİ jetonu (8 USD/1M; düzenlemede referanslar yüksek ayrıntıda
    # işleniyor) krediye girmiyor — düzenleme istekleri hesabımızdan pahalı,
    # ölçülmedi. İkisi de ayrı karar; buraya yazılı ki sessiz kalmasın.
    #
    # `plan="free"` (sahibin araştırmasıyla değişti; ilk sürüm `temel` idi):
    # basamak gerekçesi FİYAT ve 2.5 medium'da 3 kredi — `free` olan
    # gpt-image-2'nin 11'inden UCUZ; ölçülmemiş tarifeyi ücretsize açmamak
    # gerekçesi tarife kaynaktan okununca düştü. OpenAI bu modeller için
    # **API Organization Verification** isteyebiliyor: kendi anahtarını giren
    # (BYOK) kullanıcının 403'ü buradan gelebilir — hata metni sağlayıcının,
    # katalogda bir kapı yok.
    ImageModel(
        id="openai-gpt-image-2-5-sunburst",
        label="OpenAI · GPT Image 2.5 Sunburst",
        provider="openai",
        wire_model="gpt-image-2.5-sunburst",
        credential="openai",
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("low", "medium", "high"),
        default_quality="medium",
        max_n=4,
        images_per_request=4,
        supports_edit=True,
        max_refs=4,
        # 196 / 439 / 1.756 jeton × 30 USD/1M → 1 / 3 / 11 kredi (OpenAI rehberi, 2026-09-23; blok yorumu).
        credits=3,
        credits_by_quality=(("low", 1), ("medium", 3), ("high", 11)),
        plan="free",
        note="model.openai-gpt-image-2-5-sunburst.note",
    ),
    ImageModel(
        id="openai-gpt-image-2-5-flare",
        label="OpenAI · GPT Image 2.5 Flare",
        provider="openai",
        wire_model="gpt-image-2.5-flare",
        credential="openai",
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("low", "medium", "high"),
        default_quality="medium",
        max_n=4,
        images_per_request=4,
        supports_edit=True,
        max_refs=4,
        # 196 / 439 / 1.756 jeton × 30 USD/1M → 1 / 3 / 11 kredi (OpenAI rehberi, 2026-09-23; blok yorumu).
        credits=3,
        credits_by_quality=(("low", 1), ("medium", 3), ("high", 11)),
        plan="free",
        note="model.openai-gpt-image-2-5-flare.note",
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
        note="model.gemini-nano-banana-pro.note",
    ),
    # OpenAI DOĞRUDAN (Azure üzerinden değil). Tel formatı Azure'ın aynısı, o
    # yüzden adaptör onun bilinçli ikizi (bkz. openai_client.py'nin başlığı).
    #
    # `gpt-image-2` OpenAI tarafının BAŞINDA duruyor çünkü OpenAI'nin görsel
    # ailesinde bugün tek KALICI ad o: `gpt-image-1` 23 Ekim 2026'da (girdisi
    # aşağıdaki notta — silindi),
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
        # Azure ikiziyle AYNI sayı — aynı model, aynı birim fiyat; ölçümün
        # kendisi ve gerekçesi `azure-gpt-image-2` girdisinde. İkisi ayrışırsa
        # kullanıcı sağlayıcı değiştirince kredisi sessizce değişir.
        credits=11,
        credits_by_quality=(("low", 1), ("medium", 11), ("high", 42)),
        note="model.openai-gpt-image-2.note",
    ),
    # `openai-gpt-image-1` BURADAYDI ve 2026-09-21'de SİLİNDİ (Faz 4 / 1):
    # 23 Ekim 2026'da OpenAI API'sinden kalkıyor ve `openai-dall-e-3`ün
    # ölçülmüş dersi ölü girdinin bedelini söylüyor — kullanıcı seçebiliyor,
    # üretim 404 alıyor. Emeklilik gününü beklemek yerine para almaya
    # başlamadan (Faz 4) kaldırıldı; eski `medya`/`isler` satırları `model`
    # dizesini taşımaya devam eder (yeniden gönderim "katalogdan düşmüş
    # model" dalına düşer — routers/isler.py `yeniden`), işçi onu
    # "bilinmeyen model" ile hata sayar (tests/test_isci.py). Sıradaki:
    # `gpt-image-1.5` / `gpt-image-1-mini` 1 Aralık 2026 (girdileri yok).
    ImageModel(
        id="gemini-nano-banana-2",
        label="Gemini · Nano Banana 2",
        provider="gemini",
        wire_model="gemini-3.1-flash-image",
        credential="gemini",
        sizes=ASPECT_RATIOS,
        default_size="1:1",
        qualities=("1K", "2K", "4K"),
        # VARSAYILAN 2K'NIN GEREKÇESİ ÖLDÜ, KARAR ERTELENDİ (2026-09-22).
        # Burada "2K, 1K ile AYNI fiyatta (ikisi de 1120 jeton) — varsayılanı
        # 1K yapmak bedava çözünürlüğü çöpe atmak olurdu" yazıyordu. Google'ın
        # yayınlanmış fiyatı o denklemi yanlışlıyor: 1K 0,067 · 2K 0,101 USD,
        # yani 2K %54 DAHA PAHALI ve varsayılan her üretimde 20 kredi
        # düşürüyor, 13 değil. Varsayılanı 1K'ya çekmek bir ÜRÜN kararı
        # (çıktı kalitesini düşürür) ve bu PR fiyat düzeltmesi — sessizce
        # değiştirmek, bu turun tam olarak yakaladığı kusuru tekrarlamak
        # olurdu. Soru sahibe açık yazıldı (belge §1b).
        default_quality="2K",
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        # Model daha fazlasını kabul ediyor; tavan `app.MAX_EDIT_IMAGES`.
        max_refs=4,
        # FİYAT DÜZELTİLDİ (2026-09-22, Google'ın yayınlanmış görsel fiyatı):
        # 1K 0,067 → 13 · 2K 0,101 → 20 · 4K 0,151 → 30 kredi. Katalog
        # 6/6/12 diyordu, yani 1K iki kattan fazla EKSİK fiyatlanmıştı.
        credits=13,
        credits_by_quality=(("1K", 13), ("2K", 20), ("4K", 30)),
        # "en ucuz" İDDİASI İKİ KEZ ÖLDÜ: önce MAI 2.6 Flash'a (4 kredi)
        # yenildi, şimdi düzeltilmiş fiyatla ailenin kendi içinde bile ucuz
        # değil. Hız iddiası duruyor — katalogda gecikme verisi yok, yani
        # ölçülemez; maliyet ölçülebilir ve artık mandallı.
        note="model.gemini-nano-banana-2.note",
    ),
    # ── Azure AI Foundry · MAI-Image (Microsoft) ────────────────────────
    #
    # ÜÇÜ DE ÖNİZLEME ve notlarında yazılı: ad ya da sözleşme haber vermeden
    # değişebilir. `openai-gpt-image-1`in duruşu benimseniyor — kalkacağı
    # belli olan girdi SİLİNİR (o girdi 2026-09-21'de, emekliliğinden önce
    # silindi; Faz 4 / 1), çünkü katalogda kalan ölü bir girdi arayüzde
    # seçilebilir bir 404 demek (`openai-dall-e-3`ün ölçülmüş dersi).
    #
    # KREDİ ÇAPASI görsel tarafındakiyle AYNI: 1 kredi = 0,005 USD
    # (`KREDI_USD_CAPASI`). MAI token bazlı faturalanıyor ve
    # sonda ölçüyü verdi: 1024×1024 görsel için `usage.num_output_tokens`
    # = 1024. 2.6 → 1024 tok × 38 USD/M = 0,0389 USD → 8 kredi;
    # 2.5-Pro → 1024 tok × 47 USD/M = 0,0481 USD → 10 kredi.
    # 2.6-Flash → 1024 tok × 19 USD/M = 0,0195 USD → 4 kredi. Bu satır
    # 2026-09-22'ye kadar "DOĞRULANAMADI, 4 kredi GEÇİCİ" diyordu: Azure'ın
    # fiyat tablosu JS ile çiziliyor ve `WebFetch` boş döndürüyordu. Tablo o
    # gün TARAYICIYLA açıldı — `tools/tarife_kontrol.py`nin var olma sebebi
    # tam olarak bu ertelemeydi. Tahmin ("2.6'nın yarısı") tutmuş.
    #
    # KABUL EDİLEN YAKLAŞIKLIK: `cost_for`un boyut ekseni yok, oysa MAI'de
    # token = piksel. Kredi VARSAYILAN boyuttaki maliyeti gösteriyor;
    # düzeltmek `cost_for`a üçüncü bir eksen eklemek demek ve bu turun
    # kapsamı dışında.
    #
    # `max_n=4`: MAI'de `n` parametresi HİÇ YOK, tavan
    # `models.MAX_IMAGES_PER_RUN`dan geliyor ve dört AYRI istek atılıyor.
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
        note="model.azure-mai-image-2-5-pro.note",
    ),
    # ── Azure AI Foundry · FLUX.2 (Black Forest Labs) ───────────────────
    #
    # MEGAPİKSEL FİYATI OKUNDU (2026-09-22, Azure fiyat sayfası TARAYICIYLA;
    # `WebFetch` boş döndürüyordu — `tools/tarife_kontrol.py`nin var olma
    # sebebi buydu). FLUX.2 pro KADEMELİ faturalanıyor: ilk megapiksel 0,03
    # USD, sonrakiler 0,015. Varsayılan 1024×1024 iki MP sayılıyor →
    # 0,03 + 0,015 = 0,045 USD → **9 kredi**. Çapa 1 kredi = 0,005 USD
    # (`KREDI_USD_CAPASI`).
    #
    # KATALOG 16 DİYORDU, yani pro 1,8 kat FAZLA fiyatlanmıştı. Krediler
    # "doğrulanacak bir olgu değil, ürün kararı" — ama ORAN yanlışsa
    # seçicideki karşılaştırma yalan söyler, ve burada söylüyordu: FLUX.2 pro
    # gerçekte Nano Banana Pro'nun (27) üçte biri, MAI 2.6'nın (8) hemen
    # üstünde duruyor.
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
        # 0,045 USD (kademeli MP fiyatı, kaynak blok yorumunda) → 9 kredi.
        credits=9,
        note="model.azure-flux-2-pro.note",
    ),
    # FLUX.2 FLEX SİLİNDİ (2026-09-22, Faz 4 / 1b karar 1b-D). Aynı fiyat
    # sayfası flex'i KADEMESİZ 0,05 USD/MP'den faturalıyor → 1024×1024'te
    # 0,10 USD = **20 kredi**, yani pro'nun (9) 2,2 KATI. Üstelik
    # `hizli`/`dengeli`/`detayli` ÜÇÜ DE AYNI paraya: Azure adım sayısına
    # değil megapiksele bakıyor, yani `azure_flux_client._FLEX_QUALITY`nin
    # `steps`/`guidance` çiftlerine çözdüğü eksenin FATURADA KARŞILIĞI YOK.
    # Aynı ailenin daha iyi modeli daha ucuzken flex'i seçicide tutmanın
    # gerekçesi kalmıyor; girdi `openai-gpt-image-1`in duruşuyla silindi
    # (kalkacağı belli olan girdi kalmaz, çünkü seçilebilir bir tuzak olur).
    # Adaptör tarafı da temizlendi: `_DEPLOYMENTS["FLUX.2-flex"]`,
    # `_FLEX_QUALITY` ve `quality_for`un flex dalı.
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
        note="model.azure-mai-image-2-6.note",
    ),
    # ── fal.ai (toplayıcı) · GÖRSEL — Faz 4 / 1b-D (2026-09-23) ─────────
    #
    # fal GÖRSEL tablosuna İLK KEZ giriyor (`providers._ADAPTERS["fal"]`).
    # Belge §1b "YENİ SAĞLAYICI YOK" diyordu ve haklıydı — kimlik, anahtar,
    # konak aynı (`FAL_KEY`, `queue.fal.run`) — ama fal bugüne kadar YALNIZ
    # video tablosuna kayıtlıydı: `fal_client.generate`/`edit` bu turda yazıldı
    # (belgede SAPMA olarak kayıtlı; yeni tel formatı değil, aynı kuyruk
    # protokolünün görsel çıktısı).
    #
    # FİYATLAR fal.ai model sayfalarından (erişim 2026-09-22, belge §1b tablosu);
    # çapa 1 kredi = 0,005 USD (`KREDI_USD_CAPASI`), yuvarlama en yakına.
    # fal MEGAPİKSELE YUKARI YUVARLIYOR: 1,048 MP (1024×1024) iki MP sayılır —
    # bu yüzden MP ile faturalanan iki girdinin boyut kümesi fiyat basamağına
    # göre seçildi, gpt-image-2'den kopyalanmadı.
    #
    # TEL ALANLARI `fal_client.GORSEL_ALANLAR`da; uç yolları (`wire_model` /
    # `wire_model_edit`) fal.ai'nin yayın adları. fal.ai bu depodan DOĞRUDAN
    # okunamadı (konteynerde egress kapalı, 2026-09-23); adlar ve alanlar
    # fal'ın OpenAPI şemasını kodlayan açık kaynak istemcilerden ÇAPRAZ okundu
    # (gerekçe ve kaynak listesi fal_client.py başlığında). Canlı üretim YOK —
    # sahibin sandbox turu (her modelde bir üretim) canlı doğrulamadır.
    #
    # Kalite ekseni ÜÇÜNDE DE YOK: tek sentetik jeton + gizli knob (MAI'nin
    # duruşu; boş `qualities` `ResultParams`ta 422 demekti).
    #
    # Alibaba · Qwen Image — 0,02 USD/MP. Qwen-Image'ın kendi önerdiği beş
    # geometri (`QWEN_SIZES`) 1,5–1,8 MP, fal'da İKİ MP sayılır → 0,04 USD →
    # 8 kredi metin ucunda. Düzenleme ucu (`fal-ai/qwen-image-edit`) TEK
    # `image_url` alıyor → `max_refs=1`; `image_size`ı da okuyor, seçilen boyut
    # düzenlemede de gider (ilk sürüm düşürüyordu — #80 incelemesi; bkz.
    # fal_client). DÜZENLEME 0,03 USD/MP (fal model sayfası, sahibin
    # araştırması 2026-09-23) → 2 MP → 0,06 USD → 12 kredi — ve katalogda TEK
    # `credits` alanı var, düzenleme için ayrı fiyat taşıyamıyor (`cost_for`,
    # `routers/uretim` iki rota, `isci._kredi`, `core.js` üç yer aynı alanı
    # okuyor). Seçim: `credits=12`, yani DÜZENLEME FİYATI — metin üretimi 4
    # kredi fazla öder, platform zarar etmez; 8 yazmak her düzenlemede 4
    # kredi zarardı. Ayrı bir `credits_edit` ekseni doğru ama yeni eksen,
    # gerekirse ayrı PR (belge §1b "Yapıldığında (D)").
    #
    # DÜZENLEME BOYUTU TAM TUTMUYOR (canlı, 2026-09-23): `image_size`
    # 1664×928 gönderildi, fal 1536×928 döndürdü — yükseklik kaldı, uzun kenar
    # 1536'ya indi, oran 1,79 → 1,66. Metin ucu ölçülmedi, 928×1664 de.
    # Sahibin kararı: küme DARALTILMADI (metin ucunda beş geometri modelin
    # kendi önerisi), sapma notta yazılı — "sessiz sapma yasak" kuralı notla
    # karşılanıyor, kullanıcı seçmeden önce görüyor. Fatura 2 MP'de kaldı
    # (1,43 MP yukarı yuvarlandı → 0,06 USD, ölçülen bakiye düşüşüyle birebir).
    ImageModel(
        id="fal-qwen-image",
        label="Alibaba · Qwen Image",
        provider="fal",
        wire_model="fal-ai/qwen-image",
        wire_model_edit="fal-ai/qwen-image-edit",
        credential="fal",
        sizes=QWEN_SIZES,
        default_size="1328x1328",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # Kuyruklu sağlayıcı: görselde de submit → yokla → indir. Tavan tek
        # görselin duvar saati; `total_budget` adetle çarpar.
        poll_timeout=180.0,
        # 0,03 USD/MP (DÜZENLEME ucu) × 2 MP (yukarı yuvarlama) = 0,06 USD → 12 kredi (fal.ai,
        # 2026-09-23); metin ucu 0,02/MP → 8 olurdu, tek alan düzenleme fiyatını taşıyor (blok yorumu).
        credits=12,
        note="model.fal-qwen-image.note",
    ),
    # ByteDance · Seedream V4 — 0,03 USD/GÖRSEL, boyuttan BAĞIMSIZ → 6 kredi.
    # Şema kenar başına 1024–4096 piksel istiyor; gpt-image-2'nin üç jetonu
    # (1024², 1024×1536, 1536×1024) bu aralıkta, yani model değiştiren
    # kullanıcı "varsayılana düşüldü" uyarısı almıyor (core.js `fillAxis`).
    # Düzenleme ucu (`…/v4/edit`) `image_urls` LİSTESİ alıyor (10'a kadar);
    # tavan `app.MAX_EDIT_IMAGES` (4) ve not bu yüzden 10 vaat etmiyor.
    ImageModel(
        id="fal-seedream-v4",
        label="ByteDance · Seedream V4",
        provider="fal",
        wire_model="fal-ai/bytedance/seedream/v4/text-to-image",
        wire_model_edit="fal-ai/bytedance/seedream/v4/edit",
        credential="fal",
        sizes=("1024x1024", "1024x1536", "1536x1024"),
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=True,
        max_refs=4,
        poll_timeout=180.0,
        # 0,03 USD/görsel, boyuttan bağımsız (fal.ai, 2026-09-22) → 6 kredi.
        credits=6,
        note="model.fal-seedream-v4.note",
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
        # 0,0195 USD (19 USD/1M × 1024 jeton), kaynak blok yorumunda.
        credits=4,
        note="model.azure-mai-image-2-6-flash.note",
    ),
    # Black Forest Labs · FLUX.1 [schnell] — 0,003 USD/MP → 1 kredi: ücretsiz
    # planın 1 kredilik modeli; ücretsiz planın E2E'si bununla koşuyor.
    #
    # BOYUT KÜMESİ 1 MP'NİN KESİNLİKLE ALTINDA (belge §1b "13. satır"): fal 1
    # MP'ye YUKARI yuvarlıyor, 1024×1024 = 1,048 MP İKİ MP sayılır ve kredi 1
    # değil 2 olurdu. `SCHNELL_SIZES`in beşi de 1 MP'nin altında ve 32'nin katı
    # (FLUX'un adım kısıtı); mandal
    # tests/test_catalog.py::test_schnell_jetonlari_BIR_megapikselin_ALTINDA.
    #
    # DÜZENLEME UCU YOK: `fal-ai/flux/schnell` yalnız metin→görsel (redux ayrı
    # bir model ve listede değil) → `supports_edit=False`; ikinci kapı
    # `fal_client.edit`te (`GORSEL_ALANLAR` düzenleme kümesi `None`).
    ImageModel(
        id="fal-flux-1-schnell",
        label="Black Forest Labs · FLUX.1 schnell",
        provider="fal",
        wire_model="fal-ai/flux/schnell",
        credential="fal",
        sizes=SCHNELL_SIZES,
        default_size="960x960",
        qualities=("standard",),
        quality_hidden=True,
        max_n=4,
        images_per_request=1,
        supports_edit=False,
        poll_timeout=180.0,
        # 0,003 USD/MP × 1 MP (kümenin tamamı 1 MP'nin altında) = 0,003 USD → 0,6 → 1 kredi (fal.ai, 2026-09-22).
        credits=1,
        note="model.fal-flux-1-schnell.note",
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
# fal.ai v0.23'te kuyruk adaptörüyle geldi (`fal_client.py`; video, sonra
# 2026-09-23'te görsel); Replicate hâlâ aday (anahtar alanı v0.2.0'dan beri
# formda, bkz. app.py'nin "kataloğa girmemiş eski BYOK alanları" bloğu),
# adaptörü yok.

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

# fal'ın kabul ettiği oranlar. `VIDEO_ASPECT_RATIOS` (Veo'nun ikilisi) ile
# BİRLEŞTİRİLMEDİ: iki sağlayıcının kabulünü tek demete katlamak, birine oran
# ekleyip ötekini unutmanın kapısı olurdu — `ASPECT_RATIOS`in on jetonunun
# Veo'da kullanılmama gerekçesinin aynısı, bir eksen ötede.
FAL_VIDEO_ASPECT_RATIOS: tuple[str, ...] = ("16:9", "9:16", "1:1")

# SIRA ANLAMLI ve SAHİBİN SIRALI LİSTESİ (belge §1b "Sıralı video listesi
# (10)"): kaliteli/popüler → ucuz, fal ile Gemini girdileri İÇ İÇE. Bu blok
# 2026-09-23'e kadar "ARTAN MALİYETE göre: ilk girdi varsayılan" diyordu ve
# fal'ın kendi içinde PixVerse < Wan < Kling sırasını mandallıyordu; liste
# sahipten gelince ikisi de düştü (`test_the_video_catalog_follows_the_owners_
# RANKED_list` yeni mandal).
#
# VARSAYILAN SIRADAN BAĞIMSIZ ve DEĞİŞMİYOR: `DEFAULT_VIDEO_MODEL` Veo Lite,
# listede 10. (son) sırada. Gerekçesi iki katmanlı ve ikisi de test mandallı:
# (1) Gemini ailesi içinde EN UCUZ kademe — yanlışlıkla atılan tek bir tık
# lite'ta 4 saniye için ~0,20 USD, kalite kademesinde ~1,60 USD; bir görselde
# o fark sentlerle ölçülüyordu (`test_the_default_video_model_is_the_CHEAPEST_
# tier`, Gemini bloğuna süzülmüş — fal'da daha ucuz satır var: MiniMax H3 12,
# yani "katalogdaki mutlak en ucuz" iddiası doğru DEĞİL ve test onu sormuyor);
# (2) "mevcut kullanıcının bir sonraki tıkına dokunmamak" — fal ucuz olsa bile
# ayrı bir anahtar istiyor, sessiz bir varsayılan kaymasıyla bunu dayatmak
# yanlış olurdu (`test_the_default_video_model_is_UNCHANGED`).
#
# KREDİ ÇAPASI görsel tarafındakiyle AYNI: 1 kredi = 0,005 USD
# (`KREDI_USD_CAPASI`). Veo'nun yayınlanmış saniye fiyatları bu çapaya
# bölündü (2026-09-22 düzeltmesiyle): lite 0,05 USD/sn → 10, fast 0,10 → 20,
# kalite 0,40 → 80. Birim
# SANİYE (bkz. `credits` alanının yorumu), yani 8 saniyelik bir kalite klibi
# 640 kredi — ve bu, kullanıcıya "11 kredi"lik bir `gpt-image-2 medium`
# görseliyle GERÇEK bir karşılaştırma veriyor.
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
    # ── fal.ai (toplayıcı) · DÖRT YENİ MODEL — Faz 4 / 1b-D (2026-09-23) ──
    #
    # SIRA sahibin sıralı listesi (belge §1b "Sıralı video listesi (10)"):
    # kaliteli/popüler → ucuz, fal ile Gemini girdileri İÇ İÇE. Varsayılan bu
    # sıradan BAĞIMSIZ: `DEFAULT_VIDEO_MODEL` (Veo Lite) 10. sırada duruyor,
    # gerekçesi demetin başındaki yorumda.
    #
    # KREDİLER fal.ai model sayfalarının saniye fiyatından (erişim 2026-09-22,
    # belge §1b tablosu); çapa 1 kredi = 0,005 USD, yuvarlama en yakına:
    #
    #     Seedance 2.5  720p sesli $0,473/sn · 480p sesli $0,2205/sn → 95 · 44
    #     FLUX 3        720p $0,17/sn · 1080p $0,29/sn                → 34 · 58
    #     Kling V3 Pro  sessiz $0,112/sn · sesli $0,168/sn            → 22 · 34
    #     MiniMax H3    768P $0,06/sn · 2K $0,13/sn                   → 12 · 26
    #
    # SESLİ/SESSİZ AYRIMI BU KEZ TELDE VAR: PixVerse'in ölçülemeyen ayrımının
    # (aşağıdaki 2026-09-14 bloğu) aksine Kling V3 Pro ve Seedance 2.5
    # şemalarında `generate_audio` okunuyor. Seedance'ta HEP açık gidiyor
    # (fiyat "sesli" rakam; ses aynı gizli uzayda üretiliyor, kapatmak fiyatı
    # değiştirmiyor). Kling'de KALİTE EKSENİ SES EKSENİDİR (`sessiz`/`sesli`
    # jetonları → `generate_audio`): `resolution` şemada yok (Turbo Pro'daki
    # gibi) ve iki fiyatı tek `credits`e sıkıştırmak, PixVerse'in "yukarı
    # yuvarla" tahminini ölçülebilirken bir kez daha yazmak olurdu.
    #
    # ŞEMALAR fal.ai'den DOĞRUDAN okunamadı (konteynerde egress kapalı,
    # 2026-09-23); uç yolları, alan adları, tipler ve enum'lar fal'ın OpenAPI
    # şemasını kodlayan açık kaynak istemcilerden ÇAPRAZ okundu (kaynak listesi
    # fal_client.py başlığında). Beyan yalnız ÜÇ kaynağın aynı söylediği
    # jetonlarla sınırlı: MiniMax H3'ün belgedeki 480p (10) ve 4K (32)
    # kademeleri temel H3 ucunun şemasında tek kaynakta görüldü (480P, H3 Max
    # Turbo'nun ekseni) ve YAZILMADI — eksik beyan yalnız bir yeteneği
    # kullanmamak, doğrulanmamış jeton seçilebilir bir 422. Canlı üretim YOK:
    # sahibin sandbox turu (her modelde bir klip) canlı doğrulamadır.
    #
    # `plan` BASAMAĞI (1b-B; ÖNERİ, sahip onaylamadı — belge §1b "Yapıldığında
    # (D)"): Seedance 2.5 ve FLUX 3 `pro` (5 sn = 475 / 170 kredi, `temel`in
    # 1.200'lük ayını iki-üç tıkta eritir), Kling V3 Pro `temel`, MiniMax H3
    # `free` — video kuralı (`Plan.video`, K7) ücretsizi zaten kapatıyor, yani
    # `free` burada "temel ve üstü" demek.
    ImageModel(
        id="fal-seedance-2-5",
        label="ByteDance · Seedance 2.5",
        provider="fal",
        wire_model="bytedance/seedance-2.5/text-to-video",
        wire_model_edit="bytedance/seedance-2.5/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("480p", "720p"),
        # Varsayılan 720p, en ucuz kademe DEĞİL: belgenin başlık rakamı (95) bu
        # kademeye ait ve girdi listede "en iyi" satır; 480p yalnız bütçeyi
        # düşürmek isteyene. Kredi etiketi iki kademede de seçicide görünür.
        default_quality="720p",
        # Şema 4–30 sn arası; Kling/PixVerse'in kurulu üçlüsü (5·10·15) beyan
        # ediliyor, 30 sn ÖLÇÜLMEDİ (95 kredi/sn'de tek tık 2.850 kredi olurdu).
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # i2v şemasında `end_image_url` VAR ama `fal_client.ALANLAR` göndermiyor
        # (Wan'ın aynı kararı) — bayrak dürüstçe False.
        supports_last_frame=False,
        poll_timeout=600.0,
        # 720p sesli $0,473/sn → 95 · 480p sesli $0,2205/sn → 44 kredi/sn (fal.ai, 2026-09-22).
        credits=95,
        credits_by_quality=(("480p", 44), ("720p", 95)),
        plan="pro",
        kind="video",
        note="model.fal-seedance-2-5.note",
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
        note="model.gemini-veo-3-1.note",
    ),
    # Black Forest Labs · FLUX 3 — sesi yerleşik, fiyata dahil (`generate_audio`
    # gönderilmiyor: fal sayfası iki çözünürlük için tek fiyat veriyor, ses
    # ayrımı yok). Şema `aspect_ratio`yu İKİ uçta da okuyor (Seedance/H3'ün
    # i2v'sinden farklı). Süre 5–20 tam sayı; kurulu üçlü beyan ediliyor.
    ImageModel(
        id="fal-flux-3",
        label="Black Forest Labs · FLUX 3",
        provider="fal",
        wire_model="blackforestlabs/flux-3/text-to-video",
        wire_model_edit="blackforestlabs/flux-3/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p", "1080p"),
        default_quality="720p",
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        # 720p $0,17/sn → 34 · 1080p $0,29/sn → 58 kredi/sn (fal.ai, 2026-09-22).
        credits=34,
        credits_by_quality=(("720p", 34), ("1080p", 58)),
        plan="pro",
        kind="video",
        note="model.fal-flux-3.note",
    ),
    # ── fal.ai (toplayıcı) · 2026-09-14 ölçüm turunun üç modeli ──────
    #
    # Bu blok Görev 7/8'in (2026-09-14/15) ÜÇ modelini anlatıyor: PixVerse ·
    # Wan · Kling V3 Turbo Pro. "SIRA Veo'dan SONRA … fal'ın kendi içindeki
    # sırası artan maliyete göre" paragrafı 2026-09-23'te DÜŞTÜ: sıra artık
    # sahibin sıralı listesi (demetin başındaki yorum) ve üç girdi o listede
    # Gemini girdileriyle iç içe duruyor (4 · 7 · 8). Ölçüm paragrafları
    # AYNEN duruyor — fiyatların kaynağı hâlâ o tur.
    #
    #
    # KREDİ ÇAPASI Veo'yla AYNI (yukarıdaki blok): 1 kredi = 0,005 USD
    # (`KREDI_USD_CAPASI`). Aşağıdaki `credits`/
    # `credits_by_quality` değerleri fal.ai'nin yayınlanmış saniye
    # fiyatlarından (design.md, 2026-09-14 canlı uçtan ölçüm tablosu, fal.ai
    # model sayfaları kaynak) bu çapaya bölünerek türetildi — brief'in kendi
    # tahmin ettiği rakamlar (Wan 16/16/24, PixVerse 20/32, Kling 30) DEĞİL:
    #
    #     Wan      480p $0,05/sn · 720p $0,10/sn · 1080p $0,20/sn → 10·20·40
    #     PixVerse 720p $0,065/sn (sesli) · 1080p $0,120/sn (sesli) → 13·24
    #     Kling    düz $0,14/sn, çözünürlükten BAĞIMSIZ             → 28
    #
    # PixVerse'İN SESLİ/SESSİZ AYRIMI ÖLÇÜLEMEDİ: fal.ai'nin fiyat sayfası bu
    # modelde sessiz ve sesli için iki ayrı $/sn veriyor, ama
    # `fal_client.ALANLAR`daki alan tablosunda bir ses anahtarı HİÇ YOK —
    # adaptör hangi moda düştüğünü hiç sormuyor. Hangisinin telde geçerli
    # olduğu bu turda test edilmedi, o yüzden YUKARI yuvarlandı (daha pahalı
    # olan sesli rakam alındı): krediyi düşük göstermek kullanıcıyı ucuz sanıp
    # tıklamaya davet ederdi. Bu tek çizgi bu bloktaki TEK tahmin — geri kalan
    # her rakam ya doğrudan ölçüldü ya da fal'ın fiyat sayfasından okundu.
    #
    # BEYAN KURALI: yalnız fal'ın ŞEMASININ AÇIKÇA saydığı jetonlar. 15 sn
    # Kling (3–15) ve PixVerse (1–15) şemalarında yazılı — Veo'nun 8 sn
    # tavanını aşan yeni yetenek (İKİ modelde birden — PixVerse'in kendi
    # notunun "tek model" demesi YANLIŞTI, düzeltildi). Wan'ın süresi 5·10'da
    # TUTULUYOR — DÜZELTME (Görev 8, 2026-09-15): bu satır önceden "şeması
    # aralık VERMİYOR" diyordu, bu YANLIŞTI. Ölçüm (`olcum-uc-semalari.md`)
    # şemanın `duration` için PixVerse'inkine benzer bir tamsayı aralığı
    # (`minimum: 2, maximum: 30`) verdiğini gösterdi; şema izin verirdi, ama
    # katalog BİLİNÇLİ OLARAK yalnız 5 ve 10'u beyan ediyor — 15 sn'e (ya da
    # daha uzununa) çıkarmak ayrı bir ölçüm/karar ister (test edilmemiş süre,
    # fatura ve `poll_timeout` etkisi bu turda değerlendirilmedi). Kling'in
    # `qualities`i tek sentetik
    # jeton (`quality_hidden=True`): şema `resolution` alanını hiç saymıyor,
    # yani gönderilecek bir değer yok ama `qualities` de boş bırakılamıyor
    # (bkz. o alanın yorumu).
    #
    # ÖLÇÜLDÜ / ŞEMADAN — hangi jetonun hangi yoldan geldiği (design.md'nin
    # ölçüm tablosu):
    #   • CANLI TAMAMLANDI: her üçünün de 5 sn · 16:9 (tamamlanan videonun
    #     çözünürlük oranıyla doğrulandı) · Wan'ın 480p'si.
    #   • ŞEMADAN KABUL EDİLDİ (parayla yeniden sondalanmadı, şema AÇIKÇA
    #     sayıyor): PixVerse/Kling'in 10-15 sn süreleri, üçünün de 1:1 oranı,
    #     Wan/PixVerse'in 720p/1080p kaliteleri (fiyatları fal.ai model
    #     sayfasından, canlı üretimle doğrulanmadı — yalnız Wan'ın 480p'si ve
    #     PixVerse/Kling'in varsayılan kademesi gerçek bir üretimle tamamlandı).
    #   • Wan'ın `duration=10`'u KUYRUKTA KABUL EDİLDİ ama jeton sondası iptal
    #     edildiği için TAMAMLANMADI — yine de şema aralığı (5,10) zaten
    #     kesin, ikinci bir kanıt yalnızca teyit.
    ImageModel(
        id="fal-kling-v3-turbo-pro",
        label="Kling · V3 Turbo Pro",
        provider="fal",
        wire_model="fal-ai/kling-video/v3/turbo/pro/text-to-video",
        wire_model_edit="fal-ai/kling-video/v3/turbo/pro/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("1080p",),
        quality_hidden=True,
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        credits=28,
        kind="video",
        # DÜZELTME (Görev 9, 2026-09-15): bu not önceden "En iyi fal
        # kademesi, 1080p ve lipsync" diyordu — İKİSİ DE ÖLÇÜLMEMİŞTİ.
        # lipsync adaptörün hiçbir alanında yok (`fal_client.ALANLAR`), ve
        # "1080p" `qualities`teki tek jeton ama `quality_hidden=True` ile
        # SENTETİK: şemada `resolution` alanı hiç yok, telde hiç gitmiyor,
        # çıktının gerçek çözünürlüğü ölçülmedi (bkz. `docs/ozellikler.md`nin
        # Kling satırı). Not artık yalnız ÖLÇÜLMÜŞ olanı söylüyor.
        note="model.fal-kling-v3-turbo-pro.note",
    ),
    # Kling · V3 Pro — Turbo Pro'nun (üstte) kardeşi, aynı uç ailesi
    # (`fal-ai/kling-video/v3/pro/…`), aynı dize `duration` ve aynı
    # `start_image_url`; fark KALİTE EKSENİNİN SES EKSENİ olması (blok yorumu).
    ImageModel(
        id="fal-kling-v3-pro",
        label="Kling · V3 Pro",
        provider="fal",
        wire_model="fal-ai/kling-video/v3/pro/text-to-video",
        wire_model_edit="fal-ai/kling-video/v3/pro/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        # Jetonlar ASCII (`hizli`/`dengeli` deseni), etiketleri `QUALITY_LABELS`ta,
        # tele `fal_client.build_payload` `generate_audio` olarak çeviriyor —
        # `resolution` olarak HİÇ gitmiyor (şemada o alan yok).
        qualities=("sessiz", "sesli"),
        # En ucuz kademe varsayılan: "yanlış tık pahalı olmasın" (Veo bloğunun kuralı).
        default_quality="sessiz",
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        # sessiz $0,112/sn → 22 · sesli $0,168/sn → 34 kredi/sn (fal.ai, 2026-09-22).
        credits=22,
        credits_by_quality=(("sessiz", 22), ("sesli", 34)),
        plan="temel",
        kind="video",
        note="model.fal-kling-v3-pro.note",
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
        # 0,10 USD/sn (720p, aynı kaynak) → 20 kredi/sn. Katalog 30 diyordu;
        # Lite'ın tam iki katı, sıralamadaki yeri değişmiyor.
        credits=20,
        kind="video",
        note="model.gemini-veo-3-1-fast.note",
    ),
    ImageModel(
        id="fal-pixverse-c1",
        label="PixVerse · C1",
        provider="fal",
        wire_model="fal-ai/pixverse/c1/text-to-video",
        wire_model_edit="fal-ai/pixverse/c1/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("720p", "1080p"),
        default_quality="720p",
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=600.0,
        credits=13,
        credits_by_quality=(("720p", 13), ("1080p", 24)),
        kind="video",
        note="model.fal-pixverse-c1.note",
    ),
    ImageModel(
        id="fal-wan-3-0",
        label="Alibaba · Wan 3.0",
        provider="fal",
        wire_model="alibaba/wan-3.0/text-to-video",
        wire_model_edit="alibaba/wan-3.0/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("480p", "720p", "1080p"),
        default_quality="720p",
        durations=(5, 10),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        supports_last_frame=False,
        poll_timeout=420.0,
        credits=20,
        credits_by_quality=(("480p", 10), ("720p", 20), ("1080p", 40)),
        kind="video",
        note="model.fal-wan-3-0.note",
    ),
    # MiniMax · H3 — sesi yerleşik (şemada ses anahtarı yok). Jetonlar fal'ın
    # ŞEMASININ YAZDIĞI gibi: `480P`/`768P` BÜYÜK P, `2K`/`4K` (Gemini'nin
    # görsel jetonlarıyla aynı dize, `QUALITY_LABELS` etiketini paylaşıyor).
    # Küçük harfe çevirmek telde başka bir enum demek — jeton tele OLDUĞU GİBİ
    # gidiyor. Dört kademe fal'ın birinci taraf OpenAPI'sinden (sahibin
    # araştırması 2026-09-23, PR #80 yorumu; ilk sürüm 480P/4K'yı üç kaynakla
    # göremediği için beyan etmiyordu). 2K ve 4K yerel değil, 768P'nin
    # yükseltilmiş hâli (şema açıklaması); VARSAYILAN 768P — yerel çözünürlük,
    # 480P ondan 2 kredi ucuz ama "en ucuz kademe varsayılan" kuralı burada
    # yerel kaliteye yenildi (Wan'ın 720p kararı gibi).
    ImageModel(
        id="fal-minimax-h3",
        label="MiniMax · H3",
        provider="fal",
        wire_model="minimax/h3/text-to-video",
        wire_model_edit="minimax/h3/image-to-video",
        credential="fal",
        sizes=FAL_VIDEO_ASPECT_RATIOS,
        default_size="16:9",
        qualities=("480P", "768P", "2K", "4K"),
        default_quality="768P",
        durations=(5, 10, 15),
        default_duration=5,
        max_n=1,
        images_per_request=1,
        supports_edit=True,
        max_refs=1,
        # i2v şemasında `end_image_url` var, `ALANLAR` göndermiyor (Wan/Seedance kararı).
        supports_last_frame=False,
        poll_timeout=600.0,
        # 480P $0,05 → 10 · 768P $0,06 → 12 · 2K $0,13 → 26 · 4K $0,16 → 32 kredi/sn
        # (fal.ai model sayfası, 2026-09-23). İlk 5 referans görsel ücretsiz (şema).
        credits=12,
        credits_by_quality=(("480P", 10), ("768P", 12), ("2K", 26), ("4K", 32)),
        kind="video",
        note="model.fal-minimax-h3.note",
    ),
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
        # 0,05 USD/sn (720p, Google'ın yayınlanmış video fiyatı, 2026-09-22)
        # → 10 kredi/sn. Katalog 16 diyordu. SANİYE BAŞINA, bkz. `credits`.
        credits=10,
        kind="video",
        note="model.gemini-veo-3-1-lite.note",
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
    # fal görsel jetonları (bkz. QWEN_SIZES / SCHNELL_SIZES): `ratio` sütunu
    # yine aynı oran dizelerini veriyor, model geçişinde oran taşınıyor.
    # 1024x768 / 768x1024 MAI ile PAYLAŞILIYOR (yukarıda), tekrar yazılmadı.
    "1328x1328": ("◼ 1:1", "1:1"),
    "1472x1104": ("▬ 4:3", "4:3"),
    "1104x1472": ("▮ 3:4", "3:4"),
    "1664x928": ("▬ 16:9", "16:9"),
    "928x1664": ("▮ 9:16", "9:16"),
    "960x960": ("◼ 1:1", "1:1"),
    "1024x576": ("▬ 16:9", "16:9"),
    "576x1024": ("▮ 9:16", "9:16"),
}

# Değerler ETİKET DEĞİL ÇEVİRİ ANAHTARI (`ImageModel.note`un aynı kararı ve
# `etiket.quality_label` çözüyor): etiketi kullanıcı okuyor, yani dile bağlı —
# JETON ise `history.json`a, `prefs.json`a ve tele gidiyor, yani dile bağlı
# OLAMAZ. İkisini ayırmanın yolu tabloda anahtarı tutmak.
#
# Dile bağlı OLMAYAN satırlar da (1K · 1 MP, 720p · HD) anahtar taşıyor ve bu
# bilinçli: "bunun çevirisi yok" kararı iki katalogda AYNI değeri yazarak
# GÖRÜNÜR kalıyor, tabloda literal bırakılarak gizlenmiyor — yeni bir dil
# eklendiğinde çevirmen satırı görüyor ve gerekiyorsa değiştiriyor.
QUALITY_LABELS: dict[str, str] = {
    "low": "gen.quality_low",
    "medium": "gen.quality_medium",
    "high": "gen.quality_high",
    # Kalite ekseni OLMAYAN modellerin sentetik jetonu (bkz. karar Q1).
    # Bugün onu taşıyan GERÇEK bir model yok (DALL·E 3 gitti, Gemini'nin
    # çözünürlük ekseni var); jeton yine de duruyor çünkü `quality_hidden`
    # sözleşmesinin belgelenmiş karşılığı bu ve testler onu kullanıyor.
    "standard": "gen.quality_standard",
    # Gemini'nin `image_size` jetonları. Piksel yerine MEGAPİKSEL yazılı:
    # oran seçen bir modelde "2048x2048" demek yanlış olurdu (2K, seçilen
    # orana göre farklı piksel boyutlarına çözülüyor).
    "1K": "gen.quality_1k",
    "2K": "gen.quality_2k",
    "4K": "gen.quality_4k",
    # Veo'nun `resolution` jetonları. Video tarafında MEGAPİKSEL yazmak yanlış
    # olurdu: video dünyasında ölçü satır sayısıdır ve kullanıcı "720p"yi
    # zaten öyle tanıyor.
    "720p": "gen.quality_720p",
    "1080p": "gen.quality_1080p",
    # Wan 3.0'ın en ucuz kademesi (Veo'da karşılığı yok, fal'ın kendi ekseni).
    "480p": "gen.quality_480p",
    # MiniMax H3'ün jetonu fal'ın ŞEMASINDAKİ yazımla (BÜYÜK P): jeton tele
    # olduğu gibi gidiyor, küçük harfe çevirmek başka bir enum olurdu. `2K`
    # Gemini'nin satırını paylaşıyor (aynı dize).
    "768P": "gen.quality_768p",
    # H3'ün 480P'si Wan'ın 480p etiketini paylaşıyor: aynı çözünürlük, fal'ın
    # iki ucu farklı yazıyor; kullanıcıya iki farklı "480p" göstermek yanlış.
    "480P": "gen.quality_480p",
    # Kling V3 Pro'nun KALİTE EKSENİ SES EKSENİ (Faz 4 / 1b-D): `resolution`
    # şemada yok, `generate_audio` fiyatı ikiye bölüyor (22/34 kredi/sn).
    # Jetonlar ASCII ve tele `fal_client.build_payload` çeviriyor.
    "sessiz": "gen.quality_silent",
    "sesli": "gen.quality_audio",
    # FLUX.2-flex'in `steps`/`guidance` kademeleri. Sentetik bir jeton İSRAF
    # olurdu: belgelenmiş `steps` (≤50) ve `guidance` (1.5–10) kaliteyi
    # DOĞRUDAN belirliyor, yani burada gerçek bir eksen var (karar 4).
    #
    # JETONLAR ASCII ve bu deponun kurulu deseni: `low`, `1K`, `720p`, tema
    # adları — hepsi ASCII. Jeton `history.json`a, `prefs.json`a ve
    # `ResultParams.quality`ye yazılıyor; Türkçe metin ETİKETTE yaşıyor.
    # Jetonlar sağlayıcıya GİTMİYOR: `azure_flux_client.quality_axis` onları
    # sayılara çeviriyor.
    "hizli": "gen.quality_flux_fast",
    "dengeli": "gen.quality_flux_balanced",
    "detayli": "gen.quality_flux_detailed",
}


def geometry_of(token: str) -> tuple[str, str]:
    """(etiket, oran). Bilinmeyen jetonda ikisi de jetonun kendisi."""
    return GEOMETRY_LABELS.get(token, (token, token))


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
        label="model.azure_deployment.label",
        provider="azure",
        credential="azure_chat",
        wire_model="",                          # ORTAMDAN okunuyor
        wire_from_env="AZURE_CHAT_DEPLOYMENT",
        note="model.azure-deployment.note",
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
        note="model.openai-gpt-5.6-terra.note",
    ),
    ChatModel(
        id="openai-gpt-5.6-luna",
        label="OpenAI · GPT-5.6 Luna",
        provider="openai",
        credential="openai",
        wire_model="gpt-5.6-luna",
        note="model.openai-gpt-5.6-luna.note",
    ),
    ChatModel(
        id="openai-gpt-5.6-sol",
        label="OpenAI · GPT-5.6 Sol",
        provider="openai",
        credential="openai",
        wire_model="gpt-5.6-sol",
        note="model.openai-gpt-5.6-sol.note",
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
        note="model.gemini-3.7-flash.note",
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
