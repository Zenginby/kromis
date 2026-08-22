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
`requirements.txt` değişmiyor → `gpt-image-studio.spec`'in `hiddenimports=[]`
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
    credits: int                  # GÖRSEL BAŞINA taban maliyet (yalnız metadata)
    images_per_request: int = 1
    supports_edit: bool = False
    max_refs: int = 1
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
    # Kuyruklu sağlayıcı (fal/Replicate) için tek isteğin süresi. None = tek vuruş.
    poll_timeout: float | None = None
    note: str | None = None       # seçicide gösterilen kısa Türkçe uyarı
    kind: str = "image"


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
# Dosyalar `static/img/providers/` altında ve `gpt-image-studio.spec` `static`
# dizininin tamamını aldığı için paketleme bedeli SIFIR.

PROVIDER_LOGOS: dict[str, str] = {
    "azure": "azure.svg",
    "openai": "openai.svg",
    "gemini": "gemini.svg",
}


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
        note="Metin ve düzenlemede en güçlü. Uygulamanın varsayılanı.",
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
        note="Azure'daki modelin aynısı, kendi OpenAI anahtarınla.",
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
        note="23 Ekim 2026'da API'den kalkıyor — gpt-image-2'ye geç.",
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
        note="Oran seçiliyor (piksel değil). Hızlı ve ucuz; düzenleme yapıyor.",
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
        note="Metin ve marka tutarlılığında en güçlü Gemini; pahalı.",
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


def cost_for(m: ImageModel, quality: str, n: int = 1) -> int:
    """Bir turun kredi maliyeti. TEK hesaplama noktası.

    Bilinmeyen kalite `credits` tabanına düşüyor, hata YÜKSELTMİYOR: maliyet
    metadata'sı bir üretimi engellememeli. Kalitenin geçerliliği zaten
    `GenerateRequest`'in yetenek kapısında yüksek sesle doğrulanıyor; burada
    ikinci bir 500 üretmek yalnızca üretimi kaybettirirdi.
    """
    per = dict(m.credits_by_quality).get(quality, m.credits)
    return per * n


def secret_field_names() -> frozenset[str]:
    """`SettingsRequest`'teki GİZLİ alan adları — redaksiyon buradan besleniyor."""
    return frozenset(c.secret_field for c in CREDENTIALS if c.secret_field)


def secret_env_names() -> frozenset[str]:
    """Gizli değer taşıyan env adları — `errlog` testi buradan doğrulanıyor.

    Adres (`url_env`) DIŞARIDA: endpoint gizli değil, `get_settings_status`
    onu bugün de açıkça döndürüyor.
    """
    return frozenset(c.key_env for c in CREDENTIALS)
