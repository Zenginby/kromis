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

import azure_client as ac
import catalog


def _values(env_path: str | None = None) -> dict[str, str]:
    return ac.read_env_values(env_path)


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


def configured_map(env_path: str | None = None) -> dict[str, bool]:
    """{kimlik_id: yapılandırılmış mı} — `GET /api/settings` bunu yayınlıyor.

    YALNIZCA boolean döndürüyor. Anahtarın son dört hanesi, uzunluğu ya da
    maskelenmiş hâli DE dönmüyor: `get_settings_status`'un sözleşmesi
    "API key'i ASLA döndürmez" ve "sadece son dört hane" o sözleşmenin
    öldüğü yerdir.
    """
    return {c.id: is_configured(c.id, env_path) for c in catalog.CREDENTIALS}
