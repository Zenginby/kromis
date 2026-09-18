# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Platform sahipli sağlayıcı anahtarları — ortamdan `KROMIS_PLATFORM_<AD>` (Faz 2 / 6, K4).

Faz 1 / 7'ye kadar web'de anahtar YALNIZ kullanıcının satırıydı
(`saglayici_kimlikleri`, şifreli; services/depo_kimlik_bilgisi.py): anahtarı
olmayan kullanıcı üretemiyordu. Bu modül ikinci bir kaynak açıyor —
platformun (sahibin) anahtarı, sürecin ORTAMINDAN. Çözüm sırası ad ad
**kullanıcının satırı → platform değeri → yok**: kullanıcı yalnız bir
sağlayıcıya kendi anahtarını girmiş olabilir, ötekilerde platforma düşer.
Birleştirmenin yeri iki kapı — `services/kimlik.kimlik_bilgileri` (istek) ve
`services/isci.kos` (iş); adaptörler ve `credstore` TEK sözlük görür ve
DEĞİŞMEZ.

`<AD>` KATALOGDAN TÜREYEN küme (`depo_kimlik_bilgisi.ADLAR`ın katalog yarısı:
`key_env`, `url_env`, `wire_from_env`), elle liste YOK — CLAUDE.md § 5'in
"kapsam listesinin bekçisi test" kuralı; `.env.example` 1d bölümü aynı
kümeyi `KROMIS_PLATFORM_` önekiyle sayar, bekçisi tests/test_docker_kapisi.py.
Eski BYOK adları (`REPLICATE_API_TOKEN`, `COMFYUI_URL`, `OLLAMA_URL`)
DIŞARIDA: adaptörü yok, platformun onlara anahtar vermesi anlamsız.

NEDEN ORTAM, Vault/Doppler/KMS DEĞİL (K4): yönetilen platform (Fly `secrets`,
Railway/Render env) değeri şifreli saklar ve sürece ortam olarak verir —
12-factor, ek ajan/hesap/kesinti noktası yok; `KROMIS_SECRET_KEY` de aynı
yerde yaşıyor (Faz 1 / 9). Her çağrıda ortam yeniden okunur (süreç başına bir
kez okumak testte yamalanamazdı; `services/kapilar.py`nin aynı kararı).

BİLİNMEYEN `KROMIS_PLATFORM_X` yüksek sesle ama BİR KEZ: yazım hatalı bir ad
(`KROMIS_PLATFORM_GEMINI_KEY`) sessizce yok sayılsa sahibi "anahtarı verdim,
neden çalışmıyor" der; her istekte uyarmak ise günlüğü doldururdu. Değerin
KENDİSİ hiçbir yerde loglanmaz, istisna mesajına girmez (Faz 1 / 7
sözleşmesi; bekçi tests/test_platform_anahtari.py "sızmaz" testleri).

`Kimlikler`: birleşik sözlüğün ad başına KAYNAĞINI da taşıyan `dict` alt
sınıfı. Rota "bu iş hangi anahtarla koşacak" sorusunu (`isler.anahtar_kaynagi`,
günlük kredi tavanı yalnız platform işlerini sayar) buradan cevaplar; öteki
okuyucular onu düz `Mapping[str, str]` olarak görür. Düz bir sözlük gelirse
(`kaynaklar` yok) her ad "kullanici" sayılır — bilinmeyen bir kaynak platform
parasını harcamış sayılmasın, ama tavanı da gevşetmesin: bu yol yalnız eski
çağıranlar için, rota her zaman `kimlikler()`den geçen nesneyi görür.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping

import catalog
from services import depo_kimlik_bilgisi

__all__ = ["ONEK", "ADLAR", "KAYNAK_KULLANICI", "KAYNAK_PLATFORM", "Kimlikler",
           "platform_sozlugu", "birlestir", "kimlikler", "kaynak", "bilinmeyenleri_sifirla"]

_log = logging.getLogger(__name__)

# Ortam değişkeni öneki: `KROMIS_PLATFORM_` + katalog adı (`KROMIS_PLATFORM_FAL_KEY`).
ONEK = "KROMIS_PLATFORM_"

# `isler.anahtar_kaynagi` değerleri — CHECK kümesi `services/tablolar.py`de.
KAYNAK_KULLANICI = "kullanici"
KAYNAK_PLATFORM = "platform"

# Platformun verebileceği adlar — katalogdan türeyen küme (gerekçe üstte).
ADLAR: frozenset[str] = depo_kimlik_bilgisi.ADLAR - frozenset(depo_kimlik_bilgisi.ESKI_BYOK)

# Bir kez bildirilen bilinmeyen adlar (süreç ömrü boyunca).
_bildirilen: set[str] = set()


class Kimlikler(dict[str, str]):
    """Birleşik `{ad: değer}` + `kaynaklar` (`{ad: "kullanici" | "platform"}`)."""

    kaynaklar: dict[str, str]

    def __init__(self, degerler: Mapping[str, str], kaynaklar: Mapping[str, str]) -> None:
        super().__init__(degerler)
        self.kaynaklar = dict(kaynaklar)


def bilinmeyenleri_sifirla() -> None:
    """"Bir kez bildirildi" kaydını boşaltır — testler arası (tests/test_platform_anahtari.py)."""
    _bildirilen.clear()


def platform_sozlugu(ortam: Mapping[str, str] | None = None) -> dict[str, str]:
    """Ortamdaki `KROMIS_PLATFORM_<AD>` değerleri, `{AD: değer}` — boş değer yok sayılır.

    Yalnız `ADLAR`daki adlar alınır; öneki taşıyan ama tanınmayan bir ad bir
    kez uyarıyla bildirilir, sonra sessizce geçilir. Değer loglanmaz.
    """
    kaynak = os.environ if ortam is None else ortam
    sonuc: dict[str, str] = {}
    for anahtar, deger in kaynak.items():
        if not anahtar.startswith(ONEK):
            continue
        ad = anahtar[len(ONEK):]
        if ad not in ADLAR:
            if ad not in _bildirilen:
                _bildirilen.add(ad)
                _log.warning("%s%s tanınmıyor, yok sayıldı (katalogdaki adlar: %s)",
                             ONEK, ad, ", ".join(sorted(ADLAR)))
            continue
        deger = (deger or "").strip()
        if deger:
            sonuc[ad] = deger
    return sonuc


def birlestir(kullanici_sozlugu: Mapping[str, str],
              ortam: Mapping[str, str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """Ad ad `kullanıcı → platform → yok`; `(sözlük, kaynaklar)`.

    Kullanıcının BOŞ değeri yok: `depo_kimlik_bilgisi.yaz` boş değeri satır
    silmek sayar, `oku` boş dize döndürmez. Yine de savunma olarak boş dize
    "yok" sayılır — aksi hâlde boş bir kullanıcı değeri platformu gölgelerdi.
    """
    sozluk: dict[str, str] = {}
    kaynaklar: dict[str, str] = {}
    for ad, deger in platform_sozlugu(ortam).items():
        sozluk[ad] = deger
        kaynaklar[ad] = KAYNAK_PLATFORM
    for ad, deger in kullanici_sozlugu.items():
        if deger:
            sozluk[ad] = deger
            kaynaklar[ad] = KAYNAK_KULLANICI
    return sozluk, kaynaklar


def kimlikler(kullanici_sozlugu: Mapping[str, str],
              ortam: Mapping[str, str] | None = None) -> Kimlikler:
    """`birlestir`in tek nesnede hâli — rotaya ve bağlama giden şey."""
    sozluk, kaynaklar = birlestir(kullanici_sozlugu, ortam)
    return Kimlikler(sozluk, kaynaklar)


def kaynak(cred_id: str, kimlikler: Mapping[str, str]) -> str | None:
    """Bu kimlikle çıkan iş hangi anahtarla koşar: `"kullanici"` | `"platform"` | `None`.

    Kimliğin `key_env`inin kaynağı; kendi anahtarı olmayan Azure yüzeyleri
    (`azure_chat`, `azure_foundry`) `credstore.resolve`ın yaptığı gibi görselin
    anahtarına düşer. Yalnız ANAHTAR sayılır, adres değil: adres kimin
    verdiğine bakılmaksızın fatura anahtarın sahibine kesilir.
    """
    cred = catalog.credential(cred_id)
    if cred is None:
        return None
    kaynaklar = getattr(kimlikler, "kaynaklar", None)
    if kaynaklar is None:
        kaynaklar = {ad: KAYNAK_KULLANICI for ad in kimlikler}
    if cred.key_env in kaynaklar:
        return kaynaklar[cred.key_env]
    gorsel = catalog.credential("azure_image")
    if cred_id in ("azure_chat", "azure_foundry") and gorsel is not None:
        return kaynaklar.get(gorsel.key_env)
    return None
