"""Sağlayıcı başına kimlik çözümü — "bu modele ulaşabiliyor muyum?" tek yerde.

Katalog neyin VAR OLDUĞUNU bilir (saf veri, dosya okumaz); bu modül neyin
ERİŞİLEBİLİR olduğunu bilir. Ayrım kasıtlı: kataloğun yaprak kalması onun
`models.py` dahil her yerden import edilebilmesinin tek sebebi.

Çözüm neden ADAPTÖRDE değil BURADA: `get_settings_status`'un arayüzde açtığı
kapı ile isteğin gerçekten kullandığı değerler ayrışırsa arayüz modeli
seçilebilir gösterir, ilk üretim 502 döner ve sebebi görünmez olur. Bu, tam
olarak `azure_client.resolve_chat_credentials`'ın kendi docstring'inde yazdığı
gerekçe — orada sohbet için bir kez çözülmüş bir sorun, burada N sağlayıcı için
genelleştirildi.

Azure YOLU DEĞİŞMİYOR: `azure_image` çözümü `ac.load_credentials()`'a
devrediliyor, yani iki dosyalı düşme sırası (uygulamanın kendi
`credentials.env`'i → paylaşılan `claude-tools` dosyası) ve o dosyanın legacy
anlamı bayt bayt korunuyor. Diğer sağlayıcılarda öyle bir geçmiş yok, o yüzden
onlar düz `read_env_values()` okuyor.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import azure_client as ac
import catalog


def _values(env_path: str | None = None) -> dict[str, str]:
    return ac.read_env_values(env_path)


# ── Azure AI Foundry adresinin TÜRETİLMESİ ─────────────────────────────
#
# MAI ve FLUX dağıtımları `<kaynak>.services.ai.azure.com` üzerinde duruyor;
# uygulamanın bildiği Azure adresi ise `<kaynak>.openai.azure.com`. Sonda
# ikisinin AYNI anahtarla çalıştığını ölçtü, yani kullanıcıdan ikinci bir
# anahtar istemek gereksiz — değişen tek şey HOST.
#
# TÜRETME BİR TABLO, DİZE AMELİYATI DEĞİL: `replace("openai", "services.ai")`
# gibi bir dokunuş kaynak adında "openai" geçen her kurulumu bozardı
# (`my-openai-lab.openai.azure.com`). Tablo yalnız TANINAN son ekleri
# çeviriyor; tanınmayan bir host (vekil, özel alan adı) HİÇ türetmiyor ve
# `resolve` Türkçe bir hatayla `AZURE_FOUNDRY_BASE_URL`ü ADIYLA istiyor.
# Sessiz düşme YOK: yanlış hosta atılan istek 404 döner ve sebebi kullanıcının
# hiçbir yerde okumadığı bir şey olur — bu modülün var olma sebebinin tam
# tersi. Mandal: tests/test_credstore.py.
_FOUNDRY_HOST = "services.ai.azure.com"
_FOUNDRY_SOURCES: tuple[str, ...] = (
    "openai.azure.com",
    "cognitiveservices.azure.com",
    _FOUNDRY_HOST,
)


def derive_foundry_base_url(image_base_url: str) -> str:
    """`AZURE_IMAGE_BASE_URL`ün HOSTundan Foundry KÖK adresi; tanınmazsa "".

    YOL ve SORGU BİLEREK DÜŞÜYOR: görsel adresi `/openai/v1/` ile bitiyor,
    Foundry yolları ise adaptörlerin kendi sabitleri (`/mai/v1/…`,
    `/providers/blackforestlabs/v1/…`). Kök adresi döndürmek o iki sabitin
    TEK yerde kalmasını sağlıyor — burada birleştirilse yol bilgisi iki
    dosyada birden yaşardı.
    """
    host = (urlsplit(image_base_url.strip()).hostname or "").lower()
    for son in _FOUNDRY_SOURCES:
        if host.endswith("." + son):
            kaynak = host[: -len(son) - 1]
            return f"https://{kaynak}.{_FOUNDRY_HOST}"
    return ""


def resolve(cred_id: str, env_path: str | None = None) -> tuple[str, str]:
    """(key, base_url). Eksikse Türkçe `ac.ImageError`.

    Hata mesajı sağlayıcının ADINI ve ORTAM DEĞİŞKENİNİN adını birden taşıyor:
    kullanıcı Ayarlar'da neyi arayacağını bilmeli. "Kimlik bilgileri eksik"
    demek, dört sağlayıcı varken hangisini kurcalayacağını söylemiyor.
    """
    cred = catalog.credential(cred_id)
    if cred is None:
        # Katalog ile kod ayrışmış: bu bir programlama hatası, kullanıcı hatası
        # değil — ama yine de Türkçe ve 502'ye çevrilebilir bir tür olmalı,
        # yoksa ham 500 olur ve arayüz gövdeyi ayrıştıramaz.
        raise ac.ImageError(f"Tanımsız kimlik: {cred_id}")

    if cred_id == "azure_image":
        # Azure'ın iki dosyalı düşmesi ve legacy paylaşılan dosyası korunuyor.
        return ac.load_credentials(env_path)

    if cred_id == "azure_chat":
        # Sohbetin kendi key/url'si yoksa GÖRSELİN kimliğine düşüyor. Bu düşme
        # canlı doğrulanmış bir davranış (iki dağıtım aynı Azure kaynağında,
        # aynı anahtarla) ve `resolve_chat_credentials` zaten tam olarak bunu
        # yapıyor — burada YENİDEN YAZILMIYOR, ona devrediliyor: ikinci bir
        # düşme mantığı yazmak, arayüzün açtığı kapı ile isteğin kullandığı
        # değerin ayrışması demek olurdu.
        key, url, _deployment = ac.resolve_chat_credentials(env_path)
        if not key or not url:
            raise ac.ImageError(
                "Azure sohbet kimliği eksik: Ayarlar'dan endpoint ve API "
                "anahtarını kaydet.")
        return key, url

    if cred_id == "azure_foundry":
        # `azure_chat` dalının İKİZİ ve aynı ölçülmüş olguya dayanıyor: tek
        # anahtar üç yüzeyde de geçiyor (Azure OpenAI, MAI, FLUX).
        #
        # ADRES İKİ KADEMELİ ve sıra bağlayıcı: elle yazılan
        # `AZURE_FOUNDRY_BASE_URL` KAZANIYOR (vekil ya da ayrı bir kaynak
        # kullanan kurulum), boşsa görselin adresinden türetiliyor. Tersi
        # olsaydı kullanıcının yazdığı adres sessizce yok sayılırdı.
        values = _values(env_path)
        key = values.get(cred.key_env) or values.get(ac.IMAGE_KEY, "")
        url = (values.get(cred.url_env, "").strip()
               or derive_foundry_base_url(values.get(ac.IMAGE_URL, "")))
        if not key:
            raise ac.ImageError(
                f"{cred.label} anahtarı yok: Ayarlar'dan Azure API anahtarını "
                f"kaydet (ortam değişkeni: {cred.key_env} ya da {ac.IMAGE_KEY}).")
        if not url:
            raise ac.ImageError(
                f"{cred.label} adresi çözülemedi: Azure adresin tanınan bir "
                f"Foundry hostu değil. Ayarlar'daki Foundry adresi alanına "
                f"https://<kaynak>.{_FOUNDRY_HOST} yaz "
                f"(ortam değişkeni: {cred.url_env}).")
        return key, url

    values = _values(env_path)
    key = values.get(cred.key_env, "")
    url = (values.get(cred.url_env, "") if cred.url_env else "") or (cred.default_base_url or "")
    if not key:
        raise ac.ImageError(
            f"{cred.label} anahtarı yok: Ayarlar'dan kaydet "
            f"(ortam değişkeni: {cred.key_env}).")
    if not url:
        raise ac.ImageError(
            f"{cred.label} adresi yok: Ayarlar'dan kaydet "
            f"(ortam değişkeni: {cred.url_env}).")
    return key, url


def is_configured(cred_id: str, env_path: str | None = None) -> bool:
    """`resolve` hata YÜKSELTMEDEN geçer mi. Arayüzün kapısı bu.

    `resolve`'u çağırıp istisnayı yutuyor — İKİNCİ bir "eksik mi?" mantığı
    yazmamak için. Ayrı yazılsa ikisi ayrışabilir ve arayüz yapılandırılmış
    gösterdiği bir modelde üretim anında 502 alırdı; bu modülün var olma
    sebebinin tam tersi.
    """
    try:
        resolve(cred_id, env_path)
    except ac.ImageError:
        return False
    return True


def chat_is_configured(m: catalog.ChatModel, env_path: str | None = None) -> bool:
    """Bu SOHBET modeliyle konuşulabilir mi — kimlik + (gerekiyorsa) dağıtım adı.

    `is_configured` tek başına yetmiyor ve sebebi Azure: kimliği tam olsa bile
    dağıtım adı boşken istek 404 döner (`chat_client.map_error`'ın en sık
    hatası). Arayüz o modeli "kurulu" gösterirse kullanıcı yönetmeni açar, ilk
    mesaj 502 döner ve sebebi görünmez olur — bu modülün var olma sebebinin tam
    tersi.

    Ad ORTAMDAN okunuyor ama `wire_model` katalogda yazılıysa ortama HİÇ
    bakılmıyor: OpenAI/Gemini'de girilecek bir ad yok, aranan bir env
    değişkeninin yokluğu onları sessizce kapatırdı.
    """
    if not is_configured(m.credential, env_path):
        return False
    if m.wire_from_env:
        return bool(_values(env_path).get(m.wire_from_env, "").strip())
    return True


def chat_configured_map(env_path: str | None = None) -> dict[str, bool]:
    """{sohbet_model_id: konuşulabilir mi} — `GET /api/settings` bunu yayınlıyor.

    KİMLİK BAŞINA değil MODEL BAŞINA: Azure'ın dağıtım adı model düzeyinde bir
    koşul ve `configured_map`'in kimlik tablosu onu ifade edemiyor.
    """
    return {m.id: chat_is_configured(m, env_path) for m in catalog.CHAT_MODELS}


def configured_map(env_path: str | None = None) -> dict[str, bool]:
    """{kimlik_id: yapılandırılmış mı} — `GET /api/settings` bunu yayınlıyor.

    YALNIZCA boolean döndürüyor. Anahtarın son dört hanesi, uzunluğu ya da
    maskelenmiş hâli DE dönmüyor: `get_settings_status`'un sözleşmesi
    "API key'i ASLA döndürmez" ve "sadece son dört hane" o sözleşmenin
    öldüğü yerdir.
    """
    return {c.id: is_configured(c.id, env_path) for c in catalog.CREDENTIALS}
