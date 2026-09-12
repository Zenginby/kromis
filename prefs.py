# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kullanıcı tercihleri (gizli DEĞİL) ve prefs.json yönetimi.

v2.0'da otomatik kayıt (karar D1) bir anahtar gerektirdi ve iki aday yer de
yanlıştı:

  1. **`credentials.env`** (`azure_client.save_env`) bir KİMLİK dosyası: 0600,
     `~/.config` altında. Bir arayüz tercihini oraya koymak, `POST /api/settings`
     `api_key` + `base_url` istediği için anahtarı her çevirişte kimliği yeniden
     yazmaya bağlardı — ve Azure hiç yapılandırılmamışken anahtar çevrilemez
     olurdu. Bir tema adının 0600 olmasının da bir anlamı yok.
  2. **İstemci (localStorage)**: `desktop.py` pencereyi pywebview'ın
     `private_mode=True` varsayılanıyla açıyor, orada localStorage her kapanışta
     siliniyor — `chat_store.py`'nin başındaki ölçülmüş sebep. Paketlenmiş
     `.app`'te tercih her açılışta sıfırlanırdı.

Bu yüzden tercihler kullanıcının VERİ dizinine, diğer beş manifestin yanına
düşüyor ve mekanikler jsonstore'dan geliyor (atomik yazım + yazma kilidi).
`backup.py`'nin manifest yedeği de böylece tercihleri kapsıyor.

Şekil farkı: bu dosya LİSTE değil NESNE. Depo başına bir kayıt kümesi yok, tek
bir tercih kümesi var.

Yazma yolu KATI (bilinmeyen anahtar ve yanlış tür yüksek sesle hata),
okuma yolu HOŞGÖRÜLÜ (bozuk dosya → varsayılanlar). Beş depodaki duruşun aynısı:
kullanıcının veri klasöründeki bir dosya uygulamayı açılamaz hale getirmemeli,
ama uygulamanın kendi yazdığı çöp de sessizce birikmemeli.
"""
from __future__ import annotations

import json
import os

import catalog
import i18n
import jsonstore
from models import ALLOWED_LANGUAGES, ALLOWED_THEMES

PREFS_FILE = "prefs.json"

# Tercih → (varsayılan, tür). Varsayılan "dosya yok" ile "alan yok" durumlarının
# İKİSİNİ de karşılıyor; tercihler bu yüzden hiç göç gerektirmiyor.
#
# `autosave_sessions` varsayılanı True: karar D1 oturumların kaydedilmesinden
# yana ve yeni bir kurulumda geçmişin boş kalması o kararın tersini uygulamak
# olurdu (bkz. tasarım §5/D1).
#
# `guncelleme_kontrolu` varsayılanı True: paketler artık main'e giren her
# değişiklikte otomatik üretiliyor, yani yayınlar sık çıkıyor ve kullanıcının
# bunu öğrenmesinin başka bir yolu yok (GUNCELLEME.md'yi kendiliğinden açıp
# bakması gerekirdi). Ama KAPATILABİLİR olması şart: uygulamanın kullanıcının
# haberi olmadan dışarıya bağlanması, kapatma düğmesi olmadan savunulamaz —
# üstelik bu uygulama üretim dışında tümüyle çevrimdışı çalışıyor.
#
# `image_model` (v0.6): seçili görsel modeli. Burada, `credentials.env`'de DEĞİL —
# dosyanın başındaki iki gerekçenin ikisi de birebir geçerli: bir model adı gizli
# değil (0600 olmasının anlamı yok) ve `POST /api/settings` api_key + base_url
# istediği için modeli çevirmek Azure kimliğini yeniden yazmaya bağlanırdı, yani
# Azure hiç yapılandırılmamışken model DEĞİŞTİRİLEMEZ olurdu.
#
# Kural şöyle okunuyor: "hangi modeli İSTİYORUM" → prefs.json,
# "ona NASIL ULAŞIYORUM" → credentials.env. `AZURE_CHAT_DEPLOYMENT` bu yüzden
# taşınmıyor: o bir model adı değil, adresin parçası.
_SCHEMA: dict[str, tuple[object, type]] = {
    "autosave_sessions": (True, bool),
    "theme": ("mono", str),
    # Arayüz dili (v0.21). Varsayılan "tr" ve bu bir TEMBELLİK DEĞİL KARAR:
    #
    #   1. Mevcut kullanıcı bir güncellemeden sonra arayüzünü değişmiş
    #      bulmamalı. Sistem/tarayıcı dilinden otomatik algılama tam bunu
    #      yapardı — hem de tercih henüz diske yazılmadığı için SESSİZCE.
    #   2. Kaynak metin Türkçe yazılıyor: yeni bir dize önce `tr.json`'da var
    #      oluyor, çeviri sonra geliyor (`i18n.FALLBACK`'in gerekçesi). Ön
    #      tanımlı dilin düşüş diliyle AYNI olması, çevrilmemiş bir dizenin
    #      varsayılan kurulumda hiç görünmemesi demek.
    #
    # Anahtar burada, `credentials.env`'de DEĞİL: dosyanın başındaki iki
    # gerekçe (bir arayüz tercihinin 0600 olmasının anlamı yok · anahtarı
    # çevirmek Azure kimliğini yeniden yazmaya bağlanırdı) birebir geçerli.
    "language": ("tr", str),
    "guncelleme_kontrolu": (True, bool),
    "image_model": (catalog.DEFAULT_IMAGE_MODEL, str),
    # Video şeridinin seçimi. `image_model`in AYRI bir anahtarı ve bu
    # bilinçli: iki şerit iki farklı listeden besleniyor
    # (`catalog.VIDEO_MODELS` ↔ `IMAGE_MODELS`) ve tek anahtarda tutmak, mod
    # değiştiren kullanıcının seçimini karşı listede GEÇERSİZ kılardı — yani
    # her mod geçişinde sessizce varsayılana düşerdi.
    "video_model": (catalog.DEFAULT_VIDEO_MODEL, str),
    "chat_provider": (catalog.DEFAULT_CHAT_PROVIDER, str),
    # "" = sağlayıcının ilk modeli. Boş bir varsayılan, "kullanıcı henüz
    # seçmedi" ile "şu modeli seçti" ayrımını korumak için — sağlayıcı
    # değiştiğinde eski sağlayıcının modeli yapışıp kalmasın.
    "chat_model": ("", str),
    # Yönetmen ayarları çekmecesindeki kalıcı yönlendirme (serbest metin).
    # `_ENUMS`'a GİRMİYOR ve giremez: değer kümesi açık.
    #
    # Buraya, `chat_instructions_override()` dosyasına DEĞİL — ikisi aynı işi
    # yapmıyor. O dosya personayı EZİYOR (on sekiz bin karakteri yeniden yazmak
    # demek); bu alan personaya EKLENİYOR. Kullanıcının "her zaman düz vektör"
    # demek için personanın tamamını devralmak zorunda kalması, özelliğin
    # pratikte var olmaması demekti.
    "director_guidance": ("", str),
}

DEFAULTS = {name: default for name, (default, _) in _SCHEMA.items()}

# Değer kümesi SINIRLI olan tercihler. Tablo v0.6'da açıldı; öncesinde tema
# kontrolü `update()` içinde tek bir `if` idi ve listeyi `models.ALLOWED_THEMES`
# varken LİTERAL olarak tekrarlıyordu. Tek örnek kazaydı, ikincisi desen olurdu.
#
# `chat_model` bu tabloda YOK ve olamaz: geçerliliği `chat_provider`'a bağlı,
# yani anahtar BAŞINA bir kural onu ifade edemiyor (bkz. update()).
_ENUMS: dict[str, tuple[str, ...]] = {
    "theme": ALLOWED_THEMES,
    # `theme`in gerekçesi kelimesi kelimesine geçerli: elle yazılmış bir
    # `language: "de"` buradan geçse arayüz karşılığı olmayan bir sözlüğe
    # düşer ve ekran baştan sona ham ANAHTAR gösterirdi — sessiz ve teşhisi
    # zor. `i18n.normalize` çalışma anında ayrıca koruyor ama o bir savunma;
    # tercihin kendisinin geçerli kalması bu tablonun işi.
    "language": ALLOWED_LANGUAGES,
    "image_model": catalog.image_model_ids(),
    "video_model": catalog.video_model_ids(),
    "chat_provider": catalog.chat_provider_ids(),
}


def _prefs_path(output_dir: str) -> str:
    return os.path.join(output_dir, PREFS_FILE)


def _read_raw(output_dir: str) -> dict:
    path = _prefs_path(output_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Bozuk dosya: çökmek yerine varsayılanlar
        # (storage._read_history / chat_store._read ile aynı davranış).
        #
        # `UnicodeDecodeError` de burada ve o AYRI bir olay: elle düzenlenmiş
        # bir prefs.json (modülün beklediği bir durum — bkz. read()'in
        # `theme: "neon"` notu) cp1254 kaydedilmişse `json.load` UTF-8
        # çözerken düşüyor, JSON'a hiç varamıyor. Yalnız `JSONDecodeError`
        # yakalandığında bu dosya "okuma yolu HOŞGÖRÜLÜ" sözünü deliyordu:
        # `GET /api/prefs` çıplak 500 veriyor, `POST /api/chat` ise aynı
        # arızayı yönetmenin TALİMAT dosyasının suçu gibi gösteriyordu.
        # `open` da `try`nin içinde: kod çözme okuma sırasında oluyor.
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write(output_dir: str, values: dict) -> None:
    os.makedirs(output_dir, exist_ok=True)
    jsonstore.write_atomic(_prefs_path(output_dir), values)


def read(output_dir: str) -> dict:
    """Bilinen tercihlerin BİRLEŞİK görünümü; okuma yan etkisiz (dosya yaratmaz).

    Türü yanlış olan bir değer TAHMİN EDİLMEZ, varsayılana düşer: elle yazılmış
    `"false"` dizesini bool'a çevirmeye çalışmak (`bool("false") is True`)
    kullanıcının "kapat" niyetini tam tersine döndürebilirdi.

    v0.6'da kapı DEĞERE de indi. Öncesinde yalnız TÜR kontrol ediliyordu, yani
    elle yazılmış `theme: "neon"` buradan geçip arayüze ulaşıyor ve karşılığı
    olmayan bir CSS sınıfına dönüşüyordu — sessiz ve teşhisi zor. Bayat bir
    `image_model` bundan kesinlikle daha kötü: arayüz var olmayan bir modeli
    seçili gösterir, üretim "bilinmeyen model" der.

    Bilinmeyen DEĞER, yanlış TÜR ile aynı sınıf çöp sayılıyor ve aynı yere
    düşüyor: varsayılana. Dosya YAZILMIYOR — bu fonksiyonun yan etkisiz olma
    sözü korunuyor; düzeltme bir sonraki `update()`'te kendiliğinden diske iner.

    DİKKAT — "yapılandırılmamış" bir model geçerli SAYILIYOR: katalogda var olan
    ama anahtarı henüz girilmemiş bir model seçili KALIR. Aksi hâlde kullanıcı
    Gemini'yi seçip anahtarı sonra kaydettiğinde seçimi sessizce Azure'a dönmüş
    olurdu. "Var mı?" katalogdan, "ulaşılabilir mi?" credstore'dan — ikisi ayrı
    soru ve yalnız ilki bir tercihi geçersiz kılıyor.
    """
    stored = _read_raw(output_dir)

    def _cozumle(name, default, expected):
        value = stored.get(name)
        if not isinstance(value, expected):
            return default
        allowed = _ENUMS.get(name)
        if allowed is not None and value not in allowed:
            return default
        return value

    return {name: _cozumle(name, default, expected)
            for name, (default, expected) in _SCHEMA.items()}


def update(values: dict, output_dir: str) -> dict:
    """Verilen tercihleri yazar, DİĞERLERİNİ korur; birleşik görünümü döndürür.

    "Dosyanın geri kalanını koru" kuralı `azure_client.save_env`'den geliyor ve
    aynı sebeple: orada endpoint'i tek başına kaydetmek sohbet dağıtımını
    sessizce silmişti (v1.12). Burada tema (Adım 9) ile otomatik kayıt anahtarı
    aynı dosyayı paylaşacak.

    Bilinmeyen anahtar ya da yanlış tür `ValueError`: sessizce kabul edilse
    kullanıcı "ayar çalışmıyor" derdi ve dosyada hiç okunmayan bir alan birikirdi
    (modellerin `extra="forbid"` duruşunun aynısı).

    Değişecek bir şey yoksa dosyaya DOKUNULMAZ — `chat_store.update`'in boş
    güncellemede dosyaya dokunmama kuralının aynısı.
    """
    for name, value in values.items():
        if name not in _SCHEMA:
            raise ValueError(i18n.t("err.unknown_pref", None, ad=name))
        if not isinstance(value, _SCHEMA[name][1]):
            raise ValueError(i18n.t("err.bad_pref_type", None, ad=name))
        allowed = _ENUMS.get(name)
        if allowed is not None and value not in allowed:
            raise ValueError(i18n.t("err.bad_pref_value", None, ad=name, deger=value))

    # `chat_model` ÇAPRAZ bir kural: geçerliliği `chat_provider`'a bağlı, yani
    # `_ENUMS` gibi anahtar-başına bir tablo onu ifade edemiyor. Kontrol
    # döngüden SONRA ve BİRLEŞİK görünüm üzerinde: istek yalnız modeli
    # gönderiyorsa sağlayıcı diskteki değerden okunmak zorunda, yoksa geçerli
    # bir çift reddedilirdi. Şeklen `GenerateRequest`'in alan doğrulayıcısından
    # model doğrulayıcısına geçişiyle aynı sebep.
    if values.get("chat_model"):
        provider = values.get("chat_provider") or read(output_dir)["chat_provider"]
        gecerli = [m.id for m in catalog.chat_models_for(provider)]
        if values["chat_model"] not in gecerli:
            raise ValueError(
                i18n.t("err.bad_pref_chat_model", None,
                       model=values["chat_model"], saglayici=provider))

    if not values:
        return read(output_dir)
    with jsonstore.lock_for(_prefs_path(output_dir)):
        _write(output_dir, {**_read_raw(output_dir), **values})   # immutable birleştirme
    return read(output_dir)
