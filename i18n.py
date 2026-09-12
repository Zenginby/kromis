# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Arayüz sözlükleri: anahtar → kullanıcıya görünen metin.

Sözlük neden `.py` içinde bir sözlük DEĞİL: `chat_prompt.py`'nin personayı ayrı
dosyada tutma gerekçesinin aynısı — bin dizelik bir tabloyu kaynağa gömmek
modülü okunamaz yapar ve paketlenmiş `.app` içinde düzeltilemez hale getirir.
JSON ayrıca kaynağın ötesinde bir okur kitlesi kazandırıyor: çeviriyi
düzeltecek kişinin Python bilmesi gerekmiyor.

Bu modül BİLEREK yalnızca `paths`'e bakıyor. `prefs`'i ithal etmiyor ve
etmemeli: "hangi dil seçili" sorusu ROTANIN sorusu, sözlüğünki değil — o kenar
açılsaydı `prefs` → `catalog` → … zinciri bu modülü uygulamanın ortasına
çekerdi ve "yalnızca diski okur" sözü bozulurdu (`chat_prompt`'un tek yönlü
bağımlılık duruşu).

DÜŞÜŞ SIRASI üç kademeli ve hiçbiri istisna sızdırmıyor:
`istenen dil` → `FALLBACK` (tr) → `anahtarın kendisi`.

Bozuk ya da eksik bir katalog uygulamayı AÇILAMAZ yapmıyor, ekrana ham anahtar
yazdırıyor. Bu, `prefs._read_raw`'un "okuma yolu HOŞGÖRÜLÜ" duruşunun aynısı:
kullanıcının makinesindeki bir dosya uygulamayı kilitlememeli. Kataloğun
DEPODA eksiksiz olması ise ayrı bir soru ve cevabı çalışma anında değil
`tests/test_i18n.py`'de — `chat_prompt.load_video_instructions`'ın "kapı burada
değil testte" ayrımının birebir eşi.

Değişken yerleştirme İKİ TARAFTA AYNI SÖZDİZİM: `{ad}`. `static/i18n.js` aynı
deseni uyguluyor, yani bir metin sunucudan da tarayıcıdan da çözülebiliyor ve
çevirmen tek bir kural öğreniyor. Bilinmeyen bir değişken adı SİLİNMİYOR,
olduğu gibi bırakılıyor: eksik bir argüman yüzünden cümlenin ortasının
buharlaşması, ekranda duran `{adet}`ten çok daha sessiz bir kusur olurdu.
"""
from __future__ import annotations

import contextvars
import html
import json
import os
import re
import threading

import paths

# Desteklenen diller. `models.ALLOWED_LANGUAGES` bunu AYNALIYOR — kopya değil
# ithal: iki liste ayrışırsa `prefs` kabul ettiği bir dili sözlük tanımaz.
LANGUAGES: tuple[str, ...] = ("tr", "en")

# Eksik anahtarın düştüğü dil. Türkçe, çünkü kaynak metin Türkçe yazılıyor:
# yeni bir dize önce burada var oluyor, çeviri sonra geliyor.
FALLBACK = "tr"

# `index.html`'deki yer tutucu. `__APP_VERSION__` ile AYNI FİKİR ama ayrı
# sözdizim: sürüm TEK bir değer, bu ise adlı bir tablo — `{{t:…}}` biçimi
# anahtarı yer tutucunun İÇİNDE taşıyor ve bir HTML özniteliğinin içinde de
# tırnak kaçışı gerektirmiyor.
_PLACEHOLDER = re.compile(r"\{\{t:([a-zA-Z0-9_.-]+)\}\}")

# `{ad}` — yalnız harf/rakam/alt çizgi. Dar tutulması bilinçli: CSS ya da JSON
# örneği taşıyan bir çeviri metnindeki süslü parantezler değişken sanılmasın.
_VAR = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# (dil → (mtime, sözlük)). Süreç ömrü boyunca DONMUYOR, mtime ile
# tazeleniyor: `run.sh` ile geliştirirken "dosyayı düzenle → yenile → gör"
# akışı `app.index`'in şablonu için korunuyor (o rota HTML'i her istekte
# diskten okuyor) ve sözlükte de korunmalı — yoksa bir çeviri düzeltmesini
# görmek için sunucuyu yeniden başlatmak gerekirdi.
_cache: dict[str, tuple[float, dict[str, str]]] = {}

# Kilit, ÖNBELLEK için: iki istek aynı anda aynı dili ilk kez okuyabilir ve
# `dict` ataması atomik olsa da dosyayı iki kez ayrıştırmanın anlamı yok.
# `jsonstore.lock_for`ın deseni DEĞİL ve olmamalı: orada yazma var, burada
# yalnızca okuma — süreçler arası bir kilide gerek yok.
_lock = threading.Lock()


# BU İSTEĞİN dili. `ContextVar`, küresel bir değişken DEĞİL: değeri isteğin
# bağlamına bağlı ve eşzamanlı iki istek birbirinin dilini göremiyor —
# `asyncio` görevleri ile `run_in_threadpool`'un iş parçacıkları bağlamı
# kopyalayarak taşıyor, yani FastAPI'nin hem async hem senkron rotaları
# doğru değeri okuyor.
#
# NEDEN VAR: hata metinlerini üreten yer sağlayıcı istemcileri
# (`azure_client.map_error` ve yedi ikizi) ve onlar dili SORAMIYOR —
# `prefs`'i ithal etmeleri döngü açardı (`prefs` → `models` → `azure_client`).
# Dili beş kademe boyunca parametre olarak taşımak (rota → providers →
# adaptör → istemci → map_error) her imzayı genişletmek ve her testi
# güncellemek demekti; üstelik o zincirdeki her yeni fonksiyon aynı
# parametreyi unutmaya açık olurdu.
#
# TEK YAZAR `app`'in ara katmanı (`_dil_baglami`). İkinci bir yazar doğarsa
# hangisinin son sözü söylediği çağrı sırasına kalırdı; `#go.disabled`ın "tek
# yazar" kuralının aynısı.
_AKTIF = contextvars.ContextVar("kromis_dil", default=FALLBACK)


def set_active(lang: str | None) -> None:
    """Bu isteğin dilini kurar. Tek çağıranı `app`'in ara katmanı."""
    _AKTIF.set(normalize(lang))


def active() -> str:
    """Bu isteğin dili; hiç kurulmamışsa `FALLBACK`.

    Kurulmamış hâl GERÇEK ve doğru davranışı da o: `desktop.py` sunucu hiç
    açılmadan uyarı gösteriyor, testler `map_error`ı doğrudan çağırıyor.
    İkisinde de Türkçe'ye düşmek, patlamaktan da boş dizeden de iyidir.
    """
    return _AKTIF.get()


def normalize(lang: str | None) -> str:
    """Bilinen bir dil jetonu; tanınmayan/boş her şey `FALLBACK`.

    `prefs.read` zaten değer kapısı tutuyor, yani normal yolda buraya hep
    geçerli bir jeton geliyor. Yine de var: bu modülü `prefs`'ten BAĞIMSIZ
    çağıran yerler mevcut (`desktop.py` sunucu hiç açılmadan uyarı gösteriyor)
    ve orada elde ham bir değer oluyor.
    """
    return lang if lang in LANGUAGES else FALLBACK


def catalog_path(lang: str) -> str:
    return os.path.join(paths.bundled_i18n_dir(), f"{normalize(lang)}.json")


def catalog(lang: str) -> dict[str, str]:
    """`lang` sözlüğü; okunamıyor ya da bozuksa BOŞ sözlük.

    İstisna YÜKSELTMİYOR ve gerekçe modül başlığında: bu fonksiyonun dönüşü
    her HTML isteğinin yolunda ve boş bir sözlük ekrana ham anahtar yazdırır —
    çalışmayan bir uygulamadan iyidir.

    Dosya adı `normalize` üzerinden geçtiği için dışarıdan gelen bir dil
    jetonu dizin dışına çıkamaz; yol birleştirme bu yüzden güvenli.
    """
    lang = normalize(lang)
    path = catalog_path(lang)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    with _lock:
        onbellek = _cache.get(lang)
        if onbellek is not None and onbellek[0] == mtime:
            return onbellek[1]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # `UnicodeDecodeError` ayrı bir olay ve `prefs._read_raw`'daki
        # gerekçenin aynısı: elle düzenlenip cp1254 kaydedilmiş bir dosya
        # JSON'a hiç varamadan çözme sırasında düşüyor.
        return {}
    if not isinstance(data, dict):
        return {}
    # Yalnız dize→dize çiftleri: bir çeviriye kazayla liste ya da sayı yazılmışsa
    # o anahtar YOK sayılıyor ve `t()` düşüş sırasını işletiyor. `prefs.read`'in
    # "yanlış TÜR, bilinmeyen DEĞER ile aynı sınıf çöp" kuralı.
    temiz = {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    with _lock:
        _cache[lang] = (mtime, temiz)
    return temiz


def t(key: str, lang: str | None = None, /, **degiskenler: object) -> str:
    """`key`in `lang` dilindeki karşılığı; yoksa `tr`, o da yoksa anahtarın kendisi.

    `lang` VERİLMEZSE isteğin dili (`active()`) kullanılıyor. Açıkça vermek
    hâlâ mümkün ve gerekli: testler belirli bir dili ölçüyor, `app.index` de
    şablonu çözerken dili zaten elinde tutuyor.

    Anahtarın EKRANA çıkması bilerek gürültülü — sessizce boş bir etiket
    bırakmak, eksik çeviriyi görünmez kılardı. Kullanıcıya ulaşmasını ise
    `tests/test_i18n.py` kapatıyor.

    `lang` konumsal-yalnız (`/`): çağrılar `t("x", dil, adet=3)` biçiminde ve
    `lang` adında bir DEĞİŞKENİ olan bir metin (`"{lang} seçildi"`) aksi hâlde
    parametreyle çakışırdı.
    """
    lang = active() if lang is None else normalize(lang)
    metin = catalog(lang).get(key)
    if metin is None and lang != FALLBACK:
        metin = catalog(FALLBACK).get(key)
    if metin is None:
        return key
    if not degiskenler:
        # `format` HİÇ ÇAĞRILMIYOR: değişkensiz bir metindeki süslü parantez
        # (bir JSON örneği, bir CSS kuralı) `format`a girerse KeyError olurdu.
        return metin
    return _VAR.sub(
        lambda m: str(degiskenler[m.group(1)]) if m.group(1) in degiskenler
        else m.group(0),
        metin)


def render(template: str, lang: str) -> str:
    """`{{t:anahtar}}` yer tutucularını `lang` diline çevirir.

    Değer HTML'e KAÇIŞLI giriyor ve bu bir enjeksiyon savunması değil —
    kataloglar depodan geliyor, kullanıcıdan değil — DOĞRULUK meselesi: `&`
    taşıyan bir çeviri kaçışsız yazıldığında tarayıcı onu varlık başlangıcı
    sanar, `"` taşıyan bir çeviri de bir `title="…"` özniteliğini ORTASINDAN
    böler. Tek bir kaçış hem metin düğümünde hem çift tırnaklı öznitelikte
    doğru olduğu için yer tutucunun nerede durduğunu bilmeye gerek kalmıyor.

    KESME İŞARETİ KAÇIRILMIYOR ve bu bilinçli bir sapma: `html.escape`in
    `quote=True` hâli `'`yi de `&#x27;` yapıyor ve Türkçe metin kesme
    işaretiyle dolu ("Medya'dan seç", "Ayarlar'ı aç", "prompt'u"). Tarayıcıda
    ikisi de doğru görünüyor, ama servis edilen HTML okunamaz hale geliyor ve
    metne bakan her test `&#x27;` beklemek zorunda kalıyor — yani kaçış,
    koruduğu hiçbir şeyi korumadan bir maliyet biriktiriyor. Güvenli olmasının
    sebebi şablonun kendisi: her öznitelik ÇİFT tırnaklı. Bu varsayım
    `tests/test_i18n.py`de ölçülüyor, umut edilmiyor.

    Bunun bedeli: çeviri metnine HTML ETİKETİ yazılamaz. Bu bir kısıt değil
    tercih — `<b>Monokrom</b><span>…</span>` gibi bir satır İKİ anahtara
    bölünüyor, yani çevirmen biçimlendirmeyi bozamıyor ve etiketler şablonda
    kalıyor.
    """
    def _koy(m):
        return html.escape(t(m.group(1), lang), quote=False).replace('"', "&quot;")
    return _PLACEHOLDER.sub(_koy, template)


def js_payload(lang: str) -> str:
    """Sözlüğün `<script>` içine gömülmeye hazır JSON hâli.

    AYRI BİR DOSYADAN `fetch` DEĞİL, satır içi — üç sebep:

      1. Ek bir ağ turu, ve o tur dönene kadar çalışma anında üretilen her
         dize (`t(...)` çağrıları) dilsiz kalırdı.
      2. Belge zaten `no-store` (WKWebView belgeyi de önbellekliyor —
         `app.index`'in 2. gerekçesi), yani gömülü sözlük hiç bayatlamıyor.
         Ayrı bir `/static/…json` ise `?v=` ile sürümlenmek zorunda kalırdı.
      3. Dil DEĞİŞKEN, dosya adı SABİT: `static/` altındaki her şey sürüm
         sorgusuyla adresleniyor ve iki dil aynı adresi paylaşamazdı.

    `</` dizisi kaçırılıyor: JSON'un içindeki bir `</script>` HTML
    ayrıştırıcısını erken kapatırdı. `<\\/` JavaScript'te `/` ile aynı şey,
    yani sözlüğün değeri değişmiyor.
    """
    return json.dumps(catalog(lang), ensure_ascii=False,
                      separators=(",", ":")).replace("</", "<\\/")
