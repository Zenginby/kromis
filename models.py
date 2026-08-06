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

from pydantic import (BaseModel, ConfigDict, Field, field_validator,
                      model_validator)

import azure_client as ac
import palette

MAX_PROMPT_CHARS = 4000    # kullanıcı prompt'u + palet eki
MAX_BULK_IDS = 500         # tek çoklu-seçim isteğindeki azami görsel

LOGO_POSITIONS = {
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
}
LOGO_COLORS = {"auto", "blue", "white"}
# Izgara noktasından kaydırmanın ± sınırı (görsel kenarının oranı).
# `composite.OFFSET_LIMIT` ile AYNI olmak zorunda: uçta geçen bir değer orada
# ValueError'a düşerse kullanıcı Türkçe 500 görür. composite import EDİLMİYOR —
# yukarıdaki konum/renk kümelerindeki gerekçenin aynısı; kayma
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


class GenerateRequest(BaseModel):
    # Bilinmeyen alanı reddet — palet için bu özellikle kritik: eski bir sunucu
    # süreci `palette_hex`'i sessizce yok sayıp 200 ile renksiz görsel
    # döndürürdü ve kullanıcı "palet çalışmıyor" derdi. Artık yüksek sesle 422.
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    size: str
    quality: str
    n: int = Field(ge=1, le=4)
    folder_id: str | None = Field(default=None, max_length=64)  # None = klasörsüz (kök)
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

    @field_validator("size")
    @classmethod
    def _size_ok(cls, v):
        if v not in ac.ALLOWED_SIZES:
            raise ValueError("geçersiz size")
        return v

    @field_validator("quality")
    @classmethod
    def _quality_ok(cls, v):
        if v not in ac.ALLOWED_QUALITIES:
            raise ValueError("geçersiz quality")
        return v


class SettingsRequest(BaseModel):
    # api_key boş bırakılabilir: mevcut key korunur (endpoint'i tek başına güncelleme).
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(min_length=1, max_length=500)
    # Prompt Yönetmeni'nin Azure DAĞITIM adı (model ailesi adı değil).
    #
    # `None` ile `""` BİLEREK ayrı anlam taşıyor — api_key'in aksine burada üç
    # durum var, iki değil:
    #   None : alan hiç gönderilmedi → DOKUNMA. Bayat bir settings.js (cache-
    #          buster'ı atlatmış bir kopya) endpoint kaydettiğinde Prompt
    #          Yönetmeni'ni sessizce kapatmasın diye.
    #   ""   : kullanıcı alanı boşalttı → TEMİZLE (sohbeti kapat).
    #   dolu : kaydet.
    # Gizli bilgi olmadığı için `GET /api/settings` bu alanı geri döndürüyor ve
    # form önceden dolu geliyor; o yüzden write-only değil.
    chat_deployment: str | None = Field(default=None, max_length=200)


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
    # asset_id boş/None => yerleşik KURUM logosu (mavi/beyaz auto). Doluysa
    # asset_kind kütüphanesinden seçilen özel görsel (tek görsel) kullanılır.
    asset_id: str | None = Field(default=None, max_length=64)
    asset_kind: str = "logos"                                # "logos" | "mottos"
    position: str = "bottom-right"
    color: str = "auto"
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

    @field_validator("color")
    @classmethod
    def _color_ok(cls, v):
        if v not in LOGO_COLORS:
            raise ValueError("geçersiz color")
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
CHAT_ROLES = {"user", "assistant"}


def _check_chat_total(messages: list["ChatMessage"], limit: int) -> list["ChatMessage"]:
    """Toplam karakter kapısı. Sınır ROTAYA GÖRE değişiyor (bkz. sabitler).

    Rol kuralı da paylaşılmıyor: tamamlamada son mesaj kullanıcıdan olmak ZORUNDA,
    kaydetmede ise normalde asistandan (turun yanıtı).

    `display` de SAYILIYOR: sayılmasa `chats.json`'da ölçülmeyen bir ağırlık
    olurdu — tek başına küçük, ama sınırın amacı "dosya istemcinin gönderdiği
    kadar büyüyebilmesin" ve ölçülmeyen her alan o amacı deler.
    """
    if sum(len(m.content) + len(m.display or "") for m in messages) > limit:
        raise ValueError("sohbet çok uzun: yeni bir sohbet başlat")
    return messages


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "system" BİLEREK KABUL EDİLMİYOR: sistem mesajını sunucu koyuyor. İzin
    # verilse istemci persona'yı tümden değiştirebilirdi ve `extra="forbid"` bunu
    # YAKALAMAZ — `role` geçerli bir alan, kabul edilmeyen şey DEĞERİ.
    role: str
    # Alan sınırı GENİŞ olanı (asistan); dar olan kullanıcı sınırı aşağıda,
    # rolü bilen doğrulayıcıda. Alan düzeyinde ayrılamaz: `max_length` başka bir
    # alanın değerine bakamaz.
    content: str = Field(min_length=1, max_length=MAX_CHAT_REPLY_CHARS)
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

    @field_validator("role")
    @classmethod
    def _role_ok(cls, v):
        if v not in CHAT_ROLES:
            raise ValueError("geçersiz role")
        return v

    @model_validator(mode="after")
    def _content_fits_the_role(self):
        """Kullanıcı mesajı için dar kapı. Metin TÜRKÇE ve istemcinin aynasıyla
        aynı sayıyı söylüyor — pydantic'in `max_length` metni İngilizce olurdu."""
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

    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_CHAT_MESSAGES)

    @field_validator("messages")
    @classmethod
    def _messages_ok(cls, v):
        # `min_length` bu validator'dan ÖNCE koşuyor (ölçüldü: boş liste
        # `too_short` veriyor), yani buraya boş liste gelmez. Guard yine de
        # duruyor: sınır bir gün kaldırılırsa `v[-1]` IndexError → 500 olurdu.
        if not v:
            raise ValueError("en az bir mesaj gerekli")
        if v[-1].role != "user":
            # Son mesaj asistandaysa model kendi cevabını yeniden üretmeye çalışır.
            raise ValueError("son mesaj kullanıcıdan olmalı")
        return _check_chat_total(v, MAX_CHAT_TOTAL_CHARS)


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
                                               max_length=MAX_CHAT_MESSAGES)

    @field_validator("messages")
    @classmethod
    def _messages_ok(cls, v):
        # Rol kuralı YOK: kaydedilen sohbetin son mesajı normalde asistandan.
        # Toplam kapısı bir yanıt kadar GENİŞ (bkz. MAX_CHAT_SAVE_TOTAL_CHARS).
        return v if v is None else _check_chat_total(v, MAX_CHAT_SAVE_TOTAL_CHARS)


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
