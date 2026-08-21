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
    # Anthropic `max_tokens`'ı ZORUNLU tutuyor (yoksa 400). Bu bir ayar değil TEL
    # ZORUNLULUĞU, o yüzden `chat_client.build_payload`'ın "hiç sampling
    # parametresi göndermeme" duruşunun gevşetilmesi DEĞİL — sağlayıcı başına
    # ayrı bir olgu. Minimal-gövde tripwire'ı bu yüzden adaptör BAŞINA yazılıyor,
    # yoksa buradaki meşru `max_tokens` bir gün Azure gövdesine kopyalanır.
    needs_max_tokens: bool = False
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
)


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

DEFAULT_IMAGE_MODEL = "azure-gpt-image-2"

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
        # Tek POST n görsel döndürüyor (build_payload `n`'i gövdeye koyuyor).
        images_per_request=4,
        supports_edit=True,
        # 1 ana + 3 ek. `app.MAX_EDIT_IMAGES` ile aynı sayı.
        max_refs=4,
        credits=8,
        credits_by_quality=(("low", 4), ("medium", 8), ("high", 16)),
        note="Metin ve düzenlemede en güçlü. Uygulamanın varsayılanı.",
    ),
)


# ── Sohbet modelleri ────────────────────────────────────────────────────

DEFAULT_CHAT_PROVIDER = "azure"
DEFAULT_CHAT_MODEL = "azure-deployment"

CHAT_MODELS: tuple[ChatModel, ...] = (
    ChatModel(
        id=DEFAULT_CHAT_MODEL,
        label="Azure AI Foundry dağıtımı",
        provider="azure",
        credential="azure_chat",
        wire_model="",                          # ORTAMDAN okunuyor
        wire_from_env="AZURE_CHAT_DEPLOYMENT",
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
