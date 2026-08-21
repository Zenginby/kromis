"""İstek gövdeleri (Pydantic) ve doğrulama sabitleri.

Rotalardan ayrı bir dosyada: app.py'nin yarısı model tanımıydı ve rotayı
okumak için önce altmış satırlık bir doğrulama bloğunu geçmek gerekiyordu.
Modeller yalnızca `azure_client` ve `palette`'e bakar — app.py'ye BAKMAZ, yoksa
döngüsel içe aktarma olur. Bu yüzden yalnızca modellerin kullandığı sınırlar da
(`MAX_PROMPT_CHARS`, `MAX_BULK_IDS`, konum/renk kümeleri) burada yaşar.

Ortak duruş: her modelde `extra="forbid"`. Pydantic varsayılanı bilinmeyen alanı
SESSİZCE yok sayar — eski bir sunucu süreci yeni arayüzün seçeneklerini
görmezden gelip 200 döndürür ve kullanıcı "ayar çalışmıyor" der. Tek istisna
`SettingsRequest`: kimlik bilgisi formu, alan kümesi arayüzle birebir sabit.
O istisnanın bedeli v1.13'te görüldü — forma `chat_deployment` eklenince eski
bir istemcinin alanı HİÇ göndermemesi ile BOŞ göndermesi ayırt edilemez hale
geldi; ayrım `None` varsayılanıyla kuruldu (bkz. alanın yorumu).
"""
from __future__ import annotations

from typing import Annotated

from pydantic import (BaseModel, ConfigDict, Field, field_validator,
                      model_validator)

import azure_client as ac
import catalog
import palette

MAX_PROMPT_CHARS = 4000    # kullanıcı prompt'u + palet eki
MAX_BULK_IDS = 500         # tek çoklu-seçim isteğindeki azami görsel
# Tek üretim turunda istenebilecek azami görsel. `GenerateRequest.n`'in üst
# sınırı ve dökümdeki bir sonuç kaydının azami `image_ids` uzunluğu AYNI sayı
# olmak zorunda: sonuç kaydı tam olarak bir turun çıktısını taşıyor.
MAX_IMAGES_PER_RUN = 4
# history.json / chats.json id'lerinin alan sınırı (uuid4().hex[:12] = 12).
# Biçimin KENDİSİ burada doğrulanmıyor — regex guard'ı depolarda (`_SAFE_ID`),
# bu dosya id'leri yalnızca uzunlukla sınırlıyor (folder_id geleneği).
MAX_ID_CHARS = 64

LOGO_POSITIONS = {
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
}
# Izgara noktasından kaydırmanın ± sınırı (görsel kenarının oranı).
# `composite.OFFSET_LIMIT` ile AYNI olmak zorunda: uçta geçen bir değer orada
# ValueError'a düşerse kullanıcı Türkçe 500 görür. composite import EDİLMİYOR —
# yukarıdaki konum kümesindeki gerekçenin aynısı; kayma
# tests/test_composite.py'deki tripwire ile ölçülüyor.
LOGO_OFFSET_LIMIT = 0.5
# Konumlanabilir (logo tarzı) bindirmenin varlığı hangi kütüphaneden gelebilir.
# Banner ayrı bir yerleşim olduğu için burada değil.
OVERLAY_ASSET_KINDS = {"logos", "mottos"}

BANNER_EDGES = {"top", "bottom"}
BANNER_ALIGNS = {"left", "center", "right"}


def check_drop_indices(values: list[int]) -> list[int]:
    """Paletten çıkarılan indeksleri tekilleştirip sıralar; geçersizse ValueError.

    İNDEKS, hex DEĞİL: renk sırası prompt'ta anlam taşıyor (palette._ORDER_CUE
    — baştaki renkler geniş alanlara, sondaki küçük vurgu olarak) ve aynı hex
    bir palette iki kez düşebilir; hex'le çıkarmak ikisini birden düşürürdü.

    Küme semantiği: aynı indeks iki kez gelirse istemci hatası yüzünden üretim
    bloke edilmez (silinmiş/bozuk palette benimsenen duruşun aynısı).

    Hepsi çıkarılamaz: boş palet `prompt_suffix`'i boş metne düşürür, kullanıcı
    da renksiz sonucu açıklayamaz — tam olarak `applied: False` bayrağının var
    olma nedeni olan sessiz sapma. DİKKAT: buradaki üst sınır 5'lik listeye
    göre; kayıtlı bir paletin DONMUŞ listesi daha kısa olabileceği için
    app._palette_prompt'ta çözümlemeden sonra ikinci bir kapı var.
    """
    unique = sorted(set(values))
    if any(not 0 <= index < palette.COLORS_PER_PALETTE for index in unique):
        raise ValueError("geçersiz palette_drop indeksi")
    if len(unique) >= palette.COLORS_PER_PALETTE:
        raise ValueError("paletten en az bir renk kalmalı")
    return unique


def check_capabilities(model_id: str, size: str, quality: str, n: int) -> str:
    """Seçili modelin `size`/`quality`/`n`'i kabul ettiğini doğrular.

    Dönen değer NORMALLEŞTİRİLMİŞ model id'si (boş girdi varsayılana düşüyor);
    geçersizse Türkçe `ValueError`.

    FONKSİYON olarak burada, `GenerateRequest`'in içinde DEĞİL: aynı kapı iki
    ayrı yerden geçilmek zorunda — JSON ucu pydantic ile, `/api/edit` ise
    multipart olduğu için ELLE (`app._check_edit_form`). İki kopya yazmak, iki
    ucun sessizce ayrışması demek olurdu: arayüz bir boyutu sunar, bir uçta
    geçer, diğerinde 422 döner.

    Mesajlar hangi değerlerin GEÇERLİ olduğunu söylüyor. "Geçersiz size" demek
    yetmiyor, çünkü artık geçerli küme modele göre değişiyor ve kullanıcı
    arayüzde göremediği bir kısıtla karşılaşabiliyor (bayat bir sekme, ya da
    Prompt Yönetmeni'nin önerdiği bir değer).
    """
    m = catalog.image_model(model_id or catalog.DEFAULT_IMAGE_MODEL)
    if m is None:
        raise ValueError(f"bilinmeyen model: {model_id}")
    if size not in m.sizes:
        raise ValueError(f"{m.label} bu boyutu desteklemiyor: {size} "
                         f"(geçerli: {', '.join(m.sizes)})")
    if quality not in m.qualities:
        raise ValueError(f"{m.label} bu kaliteyi desteklemiyor: {quality} "
                         f"(geçerli: {', '.join(m.qualities)})")
    if n > m.max_n:
        raise ValueError(f"{m.label} tek turda en fazla {m.max_n} görsel üretiyor")
    return m.id


class GenerateRequest(BaseModel):
    # Bilinmeyen alanı reddet — palet için bu özellikle kritik: eski bir sunucu
    # süreci `palette_hex`'i sessizce yok sayıp 200 ile renksiz görsel
    # döndürürdü ve kullanıcı "palet çalışmıyor" derdi. Artık yüksek sesle 422.
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    # None = VARSAYILAN model. Alanı hiç göndermeyen (bugünkü) bir istemcinin
    # gövdesi bayt bayt aynı kalıyor ve aynı modele gidiyor — "kayıtlı Azure
    # kullanıcısı için sıfır davranış değişikliği" bu varsayılanla sağlanıyor.
    #
    # `extra="forbid"` bu alanın İKİNCİ faydalanıcısı: yeni bir arayüz bayat bir
    # sunucuya `model` gönderdiğinde istek sessizce varsayılana düşmüyor,
    # YÜKSEK SESLE 422 dönüyor. (Multipart uçta bu koruma YOK — Starlette
    # bilinmeyen form alanını atıyor; bkz. app._check_edit_form ve core.js'in
    # yanıt yankısı kontrolü.)
    model: str | None = Field(default=None, max_length=100)
    size: str
    quality: str
    n: int = Field(ge=1, le=MAX_IMAGES_PER_RUN)
    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)
    # Üretimin doğduğu oturum (`chats.json`'daki mevcut `id`). None/boş = oturum
    # dışı üretim; etiket o zaman kayda HİÇ yazılmaz (bkz. storage.save).
    # Varlık kapısı BİLEREK yok, yalnızca biçim: bkz. app._check_session.
    session_id: str | None = Field(default=None, max_length=MAX_ID_CHARS)
    # None = palet yok. Palet `(hex, mod)` çiftinin saf fonksiyonu olduğu için
    # tel üzerinde iki skaler yetiyor; sunucunun bir depoya bakması gerekmez.
    palette_hex: str | None = Field(default=None, max_length=7)
    palette_mode: str = "analogic"
    palette_strength: str = "balanced"
    # Kayıtlı palet kullanılıyorsa id'si: adlar kaydın dondurulmuş halinden
    # okunur, böylece gösterilen ad ile prompt'a giden ad hiç ayrışmaz.
    palette_id: str | None = Field(default=None, max_length=64)
    # Seçili paletten çıkarılan renklerin indeksleri (bkz. check_drop_indices).
    # Boş = çıkarma yok ⇒ tel ve prompt v1.10'daki gibi.
    palette_drop: list[int] = Field(default_factory=list,
                                    max_length=palette.COLORS_PER_PALETTE)

    @field_validator("palette_hex")
    @classmethod
    def _palette_hex_ok(cls, v):
        if not v:
            return None
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz palette_hex")

    @field_validator("palette_mode")
    @classmethod
    def _palette_mode_ok(cls, v):
        if v not in palette.MODES:
            raise ValueError("geçersiz palette_mode")
        return v

    @field_validator("palette_strength")
    @classmethod
    def _palette_strength_ok(cls, v):
        if v not in palette.STRENGTHS:
            raise ValueError("geçersiz palette_strength")
        return v

    @field_validator("palette_drop")
    @classmethod
    def _palette_drop_ok(cls, v):
        return check_drop_indices(v)

    @model_validator(mode="after")
    def _capabilities_fit_the_model(self):
        """`size`/`quality`/`n` artık SEÇİLİ MODELE göre doğrulanıyor.

        `field_validator` DEĞİL `model_validator`: geçerli boyut kümesi artık
        kardeş bir alana (`model`) bağlı ve alan doğrulayıcısı kardeşini
        göremiyor. İki genel küme (`ac.ALLOWED_SIZES`/`ALLOWED_QUALITIES`)
        aslında hep Azure'ın yetenekleriydi; katalog her modelin kendi kümesini
        taşıyor.

        Doğrulama ROTAYA taşınmadı, burada kaldı: `extra="forbid"` ile aynı
        sözleşme — ayrışma 200 değil gürültülü 422 olmalı, ve mesajlar Türkçe
        (pydantic'in İngilizce metni kullanıcıya doğrudan görünüyor).

        `model` alanı NORMALLEŞTİRİLİYOR: None geldiyse varsayılanın gerçek
        id'si yazılıyor. Rota bundan sonra `req.model`'i doğrudan kullanabiliyor
        ve `storage.save`'e giden değer ile doğrulanan değer ayrışamıyor.
        """
        try:
            self.model = check_capabilities(self.model, self.size, self.quality, self.n)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class SettingsRequest(BaseModel):
    # api_key ve base_url boş/None bırakılabilir: mevcut değerler korunur.
    api_key: str = Field(default="", max_length=500)
    base_url: str | None = Field(default=None, max_length=500)

    # Prompt Yönetmeni'nin Azure DAĞITIM adı (model ailesi adı değil).
    chat_deployment: str | None = Field(default=None, max_length=200)
    # BYOK Sağlayıcı Ayarları (v0.2.0)
    openai_api_key: str | None = Field(default=None, max_length=500)
    fal_key: str | None = Field(default=None, max_length=500)
    replicate_api_token: str | None = Field(default=None, max_length=500)
    comfyui_url: str | None = Field(default=None, max_length=500)
    ollama_url: str | None = Field(default=None, max_length=500)

    # Çoklu model sağlayıcıları (v0.6). Adlar `catalog.CREDENTIALS`'taki
    # `secret_field` / `url_field` ile BİREBİR eşleşmek zorunda: redaksiyon ve
    # yazma yolu o eşlemeden besleniyor (mandal: tests/test_catalog.py).
    #
    # `*_base_url` alanları GİZLİ DEĞİL ve varsayılanı olan bir adresi ezmek
    # için var (uyumlu bir vekil arkasına almak isteyen kullanıcı). Boş
    # gönderilmesi "varsayılana dön" demek — bu yüzden gizli anahtarların
    # "boş = mevcut korunur" kuralına DAHİL DEĞİL (bkz. app.post_settings).
    gemini_api_key: str | None = Field(default=None, max_length=500)
    anthropic_api_key: str | None = Field(default=None, max_length=500)
    openai_base_url: str | None = Field(default=None, max_length=500)
    gemini_base_url: str | None = Field(default=None, max_length=500)
    anthropic_base_url: str | None = Field(default=None, max_length=500)



ALLOWED_THEMES = ("mono", "ocean", "amber", "viola")


class PrefsRequest(BaseModel):
    """`POST /api/prefs` gövdesi — gizli olmayan kullanıcı tercihleri (v2.0).

    `SettingsRequest`'ten AYRI bir model, çünkü ayrı bir uç: o uç kimlik formu
    (`api_key` + `base_url` zorunlu) ve bir tercihi çevirmek kimliği yeniden
    yazmak zorunda kalırdı. Buradaki `extra="forbid"` de o modelin istisnasını
    tekrarlamıyor: tercih kümesi arayüzle birebir sabit DEĞİL, zamanla büyüyecek
    (tema, Adım 9) ve bayat bir istemcinin bilinmeyen alanı yüksek sesle 422 olmalı.

    `None` = "alan hiç gönderilmedi → DOKUNMA" (`chat_deployment` geleneği):
    tema kaydeden bir istek otomatik kayıt anahtarını sessizce açmasın.
    """
    model_config = ConfigDict(extra="forbid")

    autosave_sessions: bool | None = None
    theme: str | None = None
    # EKSİKTİ ve `extra="forbid"` yüzünden sessiz değil GÜRÜLTÜLÜ bir kırılma
    # üretiyordu: `static/chat.js`'in "yeni sürüm çıkınca haber ver" anahtarı
    # `{guncelleme_kontrolu: …}` POST ediyor, uç 422 dönüyor, arayüz onay
    # kutusunu geri alıp "Tercih kaydedilemedi" yazıyordu — yani anahtar
    # HİÇ KAPATILAMIYORDU. `prefs._SCHEMA` alanı v0.4'ten beri tanıyor; eksik
    # olan yalnızca bu satırdı. Rotanın "buraya düşmek pydantic ile prefs
    # şemasının ayrışması demek olur" notu tam olarak bu durumu tarif ediyor.
    guncelleme_kontrolu: bool | None = None
    # Seçili görsel modeli ve Prompt Yönetmeni sağlayıcı/modeli (v0.6).
    image_model: str | None = Field(default=None, max_length=100)
    chat_provider: str | None = Field(default=None, max_length=50)
    chat_model: str | None = Field(default=None, max_length=100)

    @field_validator("theme")
    @classmethod
    def _theme_ok(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_THEMES:
            raise ValueError("geçersiz theme")
        return v

    @field_validator("image_model")
    @classmethod
    def _image_model_ok(cls, v: str | None) -> str | None:
        """Katalog üyeliği. `prefs.update` de aynı kapıyı tutuyor ve bu ÇİFT
        kapı bilinçli: rotanın notu ("buraya düşmek pydantic ile prefs
        şemasının ayrışması demek olur") ikisinin birden var olmasını istiyor."""
        if v is not None and catalog.image_model(v) is None:
            raise ValueError(f"geçersiz image_model: {v}")
        return v

    @field_validator("chat_provider")
    @classmethod
    def _chat_provider_ok(cls, v: str | None) -> str | None:
        if v is not None and v not in catalog.chat_provider_ids():
            raise ValueError(f"geçersiz chat_provider: {v}")
        return v

    @field_validator("chat_model")
    @classmethod
    def _chat_model_ok(cls, v: str | None) -> str | None:
        """Yalnız VARLIK kontrolü; sağlayıcıyla UYUM `prefs.update`'te.

        Uyum çapraz bir kural (`chat_provider`'a bağlı) ve isteğin yalnız modeli
        göndermesi geçerli bir durum — o zaman sağlayıcı DİSKTEN okunmak
        zorunda, yani karar depoya erişimi olan katmanda verilmeli.
        """
        if v not in (None, "") and catalog.chat_model(v) is None:
            raise ValueError(f"geçersiz chat_model: {v}")
        return v


class FolderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = Field(default=None, max_length=64)  # None = kök klasör


class MoveImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)


# Çoklu seçim uçları: tek istek = tek history.json yazımı. İstemci tarafında
# id başına ayrı istek atılsaydı yazımlar birbirini ezip güncelleme kaybettirirdi.

class BulkImagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(min_length=1, max_length=MAX_BULK_IDS)


class BulkMoveRequest(BulkImagesRequest):
    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)


class SuggestRequest(BaseModel):
    # POST + extra="forbid": query parametreleri bilinmeyen alanı reddedemez,
    # bayat sunucu tespiti bu özellikte en büyük risk olduğu için GET değil.
    model_config = ConfigDict(extra="forbid")

    hex: str = Field(min_length=6, max_length=7)

    @field_validator("hex")
    @classmethod
    def _hex_ok(cls, v):
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz hex")


class SavePaletteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    seed: str = Field(min_length=6, max_length=7)
    mode: str
    strength: str = "balanced"
    # Kaydedilirken çıkarılacak renkler. Kayıt donmuş `colors` tuttuğu için
    # (palette_store başlığı) bu, KALICI olarak daha az renkli bir paletin tek
    # yolu: çıkar → kaydet. Kayıtlı paleti sonradan düzenleme özelliği bu
    # yüzden yazılmadı; aynı sonucu veriyor.
    drop: list[int] = Field(default_factory=list,
                            max_length=palette.COLORS_PER_PALETTE)

    @field_validator("drop")
    @classmethod
    def _drop_ok(cls, v):
        return check_drop_indices(v)

    @field_validator("seed")
    @classmethod
    def _seed_ok(cls, v):
        try:
            return palette.parse_hex(v)
        except ValueError:
            raise ValueError("geçersiz seed")

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v):
        if v not in palette.MODES:
            raise ValueError("geçersiz mode")
        return v

    @field_validator("strength")
    @classmethod
    def _strength_ok(cls, v):
        if v not in palette.STRENGTHS:
            raise ValueError("geçersiz strength")
        return v


class LogoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    # asset_id ZORUNLU (min_length=1): bindirilecek görsel her zaman kullanıcının
    # kütüphanesinden gelir. Eskiden None geçilebilirdi ve sunucu pakete gömülü
    # KURUM logo çiftine düşerdi; uygulama marka-nötr olduğundan o varsayılan yok.
    # Tip `str | None` KALIYOR: alan hiç gönderilmediğinde Pydantic'in ürettiği
    # hata "asset_id zorunlu" olarak okunsun, `extra="forbid"` ile karışmasın.
    asset_id: str | None = Field(default=None, min_length=1, max_length=64)
    asset_kind: str = "logos"                                # "logos" | "mottos"
    position: str = "bottom-right"
    size: float = Field(default=0.14, ge=0.04, le=0.5)       # logo genişliği / görsel genişliği
    shadow_alpha: int = Field(default=120, ge=0, le=255)     # 0 = gölge yok
    shadow_blur: int = Field(default=6, ge=0, le=50)
    # `position` ızgara noktası ÇAPA; bunlar ondan sapma. Oran, piksel DEĞİL
    # (size/scale/margin ile aynı gelenek): 1024² ile 1536×1024'te aynı slider
    # aynı görünsün. + sağ/aşağı, − sol/yukarı.
    offset_x: float = Field(default=0.0, ge=-LOGO_OFFSET_LIMIT, le=LOGO_OFFSET_LIMIT)
    offset_y: float = Field(default=0.0, ge=-LOGO_OFFSET_LIMIT, le=LOGO_OFFSET_LIMIT)

    @field_validator("position")
    @classmethod
    def _position_ok(cls, v):
        if v not in LOGO_POSITIONS:
            raise ValueError("geçersiz position")
        return v

    @field_validator("asset_kind")
    @classmethod
    def _asset_kind_ok(cls, v):
        if v not in OVERLAY_ASSET_KINDS:
            raise ValueError("geçersiz asset_kind")
        return v


# ── Prompt Yönetmeni sohbeti ───────────────────────────────────────────
#
# Açık sohbet istemcide yaşıyor, yani her turda tel üzerinden TAMAMI geliyor.
# Sınırlar bu yüzden burada: ~9 bin karakterlik sistem talimatının üstüne
# sınırsız bir geçmiş binerse token maliyeti sessizce patlar.
#
# v1.15: aynı sınırlar KAYDETME yolunda da geçerli (`ChatSaveRequest`) — yoksa
# chats.json istemcinin gönderdiği kadar büyüyebilirdi.
MAX_CHAT_MESSAGES = 24          # ~12 tur
MAX_CHAT_MSG_CHARS = 6000       # tek KULLANICI mesajı (textarea'nın maxlength'i)
# Asistan yanıtı için AYRI ve daha geniş sınır. Sebep ölçülü: `chat_client` bilerek
# `max_tokens` göndermiyor (akıl yürüten dağıtımlar 400 veriyor), yani yanıtın
# uzunluğunu sunucu SEÇMİYOR — ve o yanıt bir sonraki turda tel üzerinden GERİ
# geliyor, kaydetmede de gövdenin parçası oluyor. İki rol tek sınırı paylaşsaydı
# 6.000'i aşan tek bir yanıt sohbeti tümden kilitlerdi: sonraki her tamamlama ve
# her kaydetme pydantic'in İNGİLİZCE 422'siyle geri dönerdi. Sınırsız da değil —
# aşan yanıt `chat_client.extract_content`'te Türkçe bir hatayla patlıyor.
MAX_CHAT_REPLY_CHARS = 12000    # tek ASİSTAN yanıtı
MAX_CHAT_TOTAL_CHARS = 60000    # tüm geçmiş — mesaj sayısı × tek mesajdan DAHA DAR
# Kaydetme kapısı tamamlama kapısından TAM BİR YANIT KADAR geniş. İstemci
# "geçmiş + kullanıcı mesajı ≤ MAX_CHAT_TOTAL_CHARS" diye ölçüp gönderiyor, yani
# tamamlama isteği sınırın dibinde geçebilir; asistan yanıtı üstüne bindiğinde
# kaydedilecek gövde o sınırı ZORUNLU olarak aşar. İki sayı eşit olsaydı uzun bir
# sohbetin son turu — prompt'u üreten tur — hiç diske yazılamazdı ve kullanıcı
# panelde güncel görünen, ama bir tur geride bir sohbet bulurdu.
MAX_CHAT_SAVE_TOTAL_CHARS = MAX_CHAT_TOTAL_CHARS + MAX_CHAT_REPLY_CHARS
MAX_CHAT_TITLE_CHARS = 120      # kenar panelinde gösterilen başlık
# Çipten gelen turun EKRANDA görünen etiketi (v1.16). Modele giden `content` ile
# aynı şey DEĞİL: kullanıcı "Instagram karesi" çipine bastığında modele bir
# cümle, akışa ise kısa bir "seçim" pili gidiyor. 400 bir çip listesine bol
# geliyor (8 çip × 40 karakter + ayraçlar ≈ 341).
MAX_CHAT_DISPLAY_CHARS = 400
# Azure'a ÇIKAN alanlar. ALLOWLIST, kara liste değil: `display` gibi yalnızca
# arayüze ait bir alan tel üzerine sızsa Azure bilinmeyen alan için 400 döner ve
# hata "sohbet bozuldu" gibi görünürdü. Allowlist olduğu için bundan sonra
# eklenen her arayüz alanı da varsayılan olarak DIŞARIDA kalır.
WIRE_MESSAGE_FIELDS = {"role", "content"}
# v2.0 (birleşik oturum): dökümde ÜÇ rol var, Azure'da hâlâ iki.
#
# `result` yalnızca DİSKTE ve EKRANDA yaşıyor: `{"role": "result",
# "image_ids": [...], "params": {...}}`. Alan allowlist'i tek başına yetmez —
# süzülmüş bir sonuç kaydı geride `{"role": "result"}` bırakır ve Azure o rolü
# bilmediği için 400 döner. Bu yüzden ROL allowlist'i de var; süzgeç
# `chat_client.build_payload`'ta, yani gövdeyi gerçekten kuran yerde.
RESULT_ROLE = "result"
WIRE_CHAT_ROLES = {"user", "assistant"}
CHAT_ROLES = WIRE_CHAT_ROLES | {RESULT_ROLE}
# Sonuç kaydının nasıl doğduğu. Kart başlığı buradan çiziliyor
# ("Üretildi · …" / "Düzenlendi · …"). Bu küme BİZE ait, Azure'a değil:
# `size`/`quality` allowlist'e karşı doğrulanmıyor (aşağıdaki not).
RESULT_KINDS = {"generate", "edit"}
# Sonuç kayıtları KONUŞMA kotasından ayrı bir baş payı alıyor. Aynı 24'ü
# paylaşsalardı üretim yapan bir oturum ~8 turda dolar ve kullanıcı pydantic'in
# İNGİLİZCE `too_long` hatasını görürdü — modele hiç gitmeyen bir kaydın
# konuşmayı kısaltması için bir sebep yok.
MAX_CHAT_RESULTS = 24
MAX_CHAT_ITEMS = MAX_CHAT_MESSAGES + MAX_CHAT_RESULTS


def _check_chat_total(messages: list["ChatMessage"], limit: int) -> list["ChatMessage"]:
    """Toplam karakter kapısı. Sınır ROTAYA GÖRE değişiyor (bkz. sabitler).

    Rol kuralı da paylaşılmıyor: tamamlamada son mesaj kullanıcıdan olmak ZORUNDA,
    kaydetmede ise normalde asistandan (turun yanıtı).

    `display` de SAYILIYOR: sayılmasa `chats.json`'da ölçülmeyen bir ağırlık
    olurdu — tek başına küçük, ama sınırın amacı "dosya istemcinin gönderdiği
    kadar büyüyebilmesin" ve ölçülmeyen her alan o amacı deler.

    `result` kayıtları SAYILMIYOR (v2.0): bu sınır token bütçesi, sonuç kayıtları
    ise modele hiç gitmiyor. Ölçülmemiş ağırlık da bırakmıyorlar — şemaları
    kapalı: en çok `MAX_IMAGES_PER_RUN` id + üç kısa parametre, adetleri de
    `MAX_CHAT_RESULTS` ile bağlı. Serbest metin taşıyabildikleri tek alan
    (`content`) onlara YASAK; `display` de öyle.
    """
    if sum(len(m.content or "") + len(m.display or "")
           for m in messages if m.role in WIRE_CHAT_ROLES) > limit:
        raise ValueError("sohbet çok uzun: yeni bir sohbet başlat")
    return messages


def _check_chat_counts(messages: list["ChatMessage"]) -> list["ChatMessage"]:
    """Konuşma turu sayısı kapısı — Türkçe, çünkü kullanıcıya görünüyor.

    Alan düzeyindeki `max_length` artık TOPLAM öğe sayısını (`MAX_CHAT_ITEMS`)
    tutuyor; konuşma turlarının kendi sınırı burada sayılıyor.
    """
    if sum(1 for m in messages if m.role in WIRE_CHAT_ROLES) > MAX_CHAT_MESSAGES:
        raise ValueError("sohbet çok uzun: yeni bir sohbet başlat")
    return messages


class ResultParams(BaseModel):
    """Sonuç kartının başlığını çizen üretim parametreleri.

    `size`/`quality` `azure_client` allowlist'lerine karşı DOĞRULANMIYOR, yalnızca
    uzunlukla sınırlı. Sebep ölçülü bir tuzak: allowlist bir gün daralırsa (Azure
    bir boyutu kaldırır) o boyutla üretilmiş eski oturumlar bir daha
    KAYDEDİLEMEZ olurdu — `PUT /api/chats/{id}` 422 döner ve kullanıcı sessizce
    donmuş bir oturumla kalır. `MAX_CHAT_REPLY_CHARS`'ın var olma sebebi de bu
    sınıf hataydı. `kind` ise bizim kümemiz; altımızdan değişmez.
    """
    model_config = ConfigDict(extra="forbid")

    kind: str
    size: str = Field(min_length=1, max_length=32)
    quality: str = Field(min_length=1, max_length=32)
    # ÜRETEN MODEL (v0.6). Varsayılanı BOŞ dize: bu sınıf `extra="forbid"`
    # taşıyor, yani alanı hiç göndermeyen bir istemcinin kaydı geçerli kalmalı —
    # v0.6'dan ÖNCE kaydedilmiş bütün oturumlar tam olarak öyle.
    #
    # Katalog üyeliğine karşı DOĞRULANMIYOR, yalnız uzunlukla sınırlı: yukarıdaki
    # docstring'in `size`/`quality` için anlattığı tuzağın aynısı. Bir model
    # katalogdan çıkarsa (sağlayıcı kapatır, biz kaldırırız) o modelle üretilmiş
    # eski oturumlar bir daha KAYDEDİLEMEZ olurdu — PUT /api/chats/{id} 422
    # döner ve kullanıcı sessizce donmuş bir oturumla kalır.
    model: str = Field(default="", max_length=100)

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v):
        if v not in RESULT_KINDS:
            raise ValueError("geçersiz kind")
        return v


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "system" BİLEREK KABUL EDİLMİYOR: sistem mesajını sunucu koyuyor. İzin
    # verilse istemci persona'yı tümden değiştirebilirdi ve `extra="forbid"` bunu
    # YAKALAMAZ — `role` geçerli bir alan, kabul edilmeyen şey DEĞERİ.
    role: str
    # Alan sınırı GENİŞ olanı (asistan); dar olan kullanıcı sınırı aşağıda,
    # rolü bilen doğrulayıcıda. Alan düzeyinde ayrılamaz: `max_length` başka bir
    # alanın değerine bakamaz.
    #
    # v2.0'da OPSİYONEL oldu — `result` kaydının metni yok, kart görsellerden ve
    # parametrelerden çiziliyor. Zorunluluk role bağlandı (aşağıdaki
    # doğrulayıcı): boş dize hâlâ reddedilir, çünkü `min_length` açıkça
    # gönderilen `""`'yi de görür.
    content: str | None = Field(default=None, min_length=1,
                                max_length=MAX_CHAT_REPLY_CHARS)
    # Yalnızca ARAYÜZ alanı: varsa akışa baloncuk değil kısa bir "seçim" pili
    # çiziliyor ve `content` hiç gösterilmiyor (v1.16). Çip seçimleri modele bir
    # cümle olarak gidiyor; o cümlenin kullanıcının kendi yazdığı bir replik gibi
    # görünmesi v1.15'in şikâyet edilen yanıydı.
    #
    # Alan MESAJLA birlikte yolculuk ediyor, ayrı bir istemci durumunda DEĞİL:
    # `openChat` sohbeti `chatThread`'den yeniden çiziyor, yani işaret mesajda
    # olmazsa kaydedilmiş bir sohbet açıldığında piller baloncuğa dönerdi. Metni
    # önceki bot mesajının çiplerinden geri türetmek de seçenek değildi: tahmin
    # olurdu ve kullanıcının GERÇEKTEN yazdığı bir cümle pil gibi çizilebilirdi.
    #
    # Azure'a ÇIKMIYOR (bkz. WIRE_MESSAGE_FIELDS).
    display: str | None = Field(default=None, min_length=1,
                                max_length=MAX_CHAT_DISPLAY_CHARS)
    # ── yalnızca `result` rolünde (v2.0) ────────────────────────────────
    # Üretilen görsellerin `history.json` id'leri. Görsel BURAYA kopyalanmıyor,
    # yalnızca işaret ediliyor: tek kaynak history deposu ve kullanıcı bir
    # görseli Medya'dan sildiğinde döküm onu "silinmiş" gösterebilsin. Sarkan id
    # bir hata değil, BEKLENEN durum (tasarım §5) — sunucu kaydı budamıyor,
    # yoksa oturum "burada iki görsel üretmiştim" bilgisini kaybederdi.
    image_ids: list[Annotated[str, Field(min_length=1, max_length=MAX_ID_CHARS)]] | None \
        = Field(default=None, min_length=1, max_length=MAX_IMAGES_PER_RUN)
    params: ResultParams | None = None

    @field_validator("role")
    @classmethod
    def _role_ok(cls, v):
        if v not in CHAT_ROLES:
            raise ValueError("geçersiz role")
        return v

    @model_validator(mode="after")
    def _fields_fit_the_role(self):
        """Alanlar ROLE bağlı. Metinler TÜRKÇE ve istemcinin aynasıyla aynı
        sayıyı söylüyor — pydantic'in `max_length` metni İngilizce olurdu."""
        if self.role == RESULT_ROLE:
            # Sonuç kaydında SERBEST METİN yok: `content` kabul edilse dökümde
            # `MAX_CHAT_TOTAL_CHARS`'a sayılmayan (bkz. _check_chat_total)
            # ölçülmemiş bir ağırlık açılırdı — bütçenin delindiği yer tam burası.
            if self.content is not None:
                raise ValueError("sonuç kaydında content olamaz")
            if not self.image_ids:
                raise ValueError("sonuç kaydında image_ids zorunlu")
            if self.params is None:
                raise ValueError("sonuç kaydında params zorunlu")
        else:
            if self.content is None:
                raise ValueError("content zorunlu")
            # Konuşma mesajına sonuç alanı takılsa döküm İKİ ayrı yerden sonuç
            # kartı çizmeye başlardı; hangisinin doğru olduğu belirsiz kalırdı.
            if self.image_ids is not None or self.params is not None:
                raise ValueError("image_ids/params yalnızca sonuç kaydında kullanılabilir")
        if self.role == "user" and len(self.content) > MAX_CHAT_MSG_CHARS:
            raise ValueError(f"mesaj çok uzun: en fazla {MAX_CHAT_MSG_CHARS} karakter")
        # `display` yalnızca KULLANICI turunda anlamlı: pil, kullanıcının verdiği
        # seçimi gösteriyor. Asistan mesajında kabul edilse yönetmenin yanıtı
        # ekranda tek satırlık bir pile inerdi — prompt'u da, "Forma aktar"
        # düğmesini de görünmez yapan sessiz bir kırılma.
        if self.role != "user" and self.display is not None:
            raise ValueError("display yalnızca kullanıcı mesajında kullanılabilir")
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_CHAT_ITEMS)

    @field_validator("messages")
    @classmethod
    def _messages_ok(cls, v):
        # `min_length` bu validator'dan ÖNCE koşuyor (ölçüldü: boş liste
        # `too_short` veriyor), yani buraya boş liste gelmez. Guard yine de
        # duruyor: sınır bir gün kaldırılırsa `v[-1]` IndexError → 500 olurdu.
        if not v:
            raise ValueError("en az bir mesaj gerekli")
        if v[-1].role != "user":
            # Son mesaj asistandaysa model kendi cevabını yeniden üretmeye
            # çalışır; sonuç kaydıysa Azure'a yalnız sistem talimatı giderdi.
            raise ValueError("son mesaj kullanıcıdan olmalı")
        return _check_chat_total(_check_chat_counts(v), MAX_CHAT_TOTAL_CHARS)


class ChatSaveRequest(BaseModel):
    """`POST /api/chats` ve `PUT /api/chats/{id}` gövdesi.

    `messages` OPSİYONEL çünkü yeniden adlandırma gövdeyi göndermek zorunda
    değil; `POST`ta zorunluluğu rota kontrol ediyor (yeni ve boş bir kayıt
    yaratmak anlamsız). "Alan hiç gelmedi" ile "boş geldi" ayrımı burada da
    None ile taşınıyor — settings yolundaki desenin aynısı.
    """
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1,
                              max_length=MAX_CHAT_TITLE_CHARS)
    messages: list[ChatMessage] | None = Field(default=None, min_length=1,
                                               max_length=MAX_CHAT_ITEMS)

    @field_validator("messages")
    @classmethod
    def _messages_ok(cls, v):
        # Rol kuralı YOK: kaydedilen sohbetin son mesajı normalde asistandan —
        # otomatik kayıtta (Adım 6) bir sonuç kaydı da olabilir.
        # Toplam kapısı bir yanıt kadar GENİŞ (bkz. MAX_CHAT_SAVE_TOTAL_CHARS).
        if v is None:
            return v
        return _check_chat_total(_check_chat_counts(v), MAX_CHAT_SAVE_TOTAL_CHARS)


class BannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)          # bindirilecek görsel (history id)
    asset_id: str = Field(min_length=1, max_length=64)    # kütüphaneden seçilen banner
    edge: str = "bottom"
    # Varsayılanlar v1.4 davranışını birebir korur: tam genişlik, ortalı, boşluksuz.
    scale: float = Field(default=1.0, ge=0.2, le=1.0)     # banner genişliği / görsel genişliği
    align: str = "center"                                # scale < 1 iken yatay yerleşim
    margin: float = Field(default=0.0, ge=0.0, le=0.2)   # kenardan uzaklık / görsel yüksekliği

    @field_validator("edge")
    @classmethod
    def _edge_ok(cls, v):
        if v not in BANNER_EDGES:
            raise ValueError("geçersiz edge")
        return v

    @field_validator("align")
    @classmethod
    def _align_ok(cls, v):
        if v not in BANNER_ALIGNS:
            raise ValueError("geçersiz align")
        return v
