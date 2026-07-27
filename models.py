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
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
# Konumlanabilir (logo tarzı) bindirmenin varlığı hangi kütüphaneden gelebilir.
# Banner ayrı bir yerleşim olduğu için burada değil.
OVERLAY_ASSET_KINDS = {"logos", "mottos"}

BANNER_EDGES = {"top", "bottom"}
BANNER_ALIGNS = {"left", "center", "right"}


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
