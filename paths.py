# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Yol çözümü: PyInstaller paketi içinde, Android'de ve geliştirmede farklı kökler.

Paket içinde `__file__` geçici çıkarma dizinine düşer; oraya yazılan geçmiş her
kapanışta kaybolur. Bu yüzden yazılabilir veri (output/, assets/) kullanıcının
Application Support dizinine, salt-okunur içerik (static/, bundled/) ise
PyInstaller'ın `sys._MEIPASS` dizinine bağlanır.

Geliştirmede (frozen değilken) her iki kök de repo dizinidir — mevcut testlerin
dayandığı yerleşim birebir korunur.

DÖRT DAL var: Android → frozen-Windows → frozen-macOS → geliştirme; önlerinde
bir de AÇIK kapı, `KROMIS_DATA_DIR` (web/konteyner, bkz. `DATA_DIR_ENV`).
Android dalı otomatik dalların EN ÖNÜNDE, çünkü orada `sys.frozen` yok
(Chaquopy sıradan bir CPython koşturuyor) ve dal sırası tersine olsa Android
sessizce geliştirme dalına, yani APK'nın İÇİNDEKİ salt-okunur dizine yazmaya
çalışırdı.
"""
from __future__ import annotations

import os
import sys

import errlog

APP_NAME = "Kromis"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# Bir önceki uygulama adı — YALNIZ göç için duruyor (`_migrate_from_old_name`).
# v0.15.0 `Lumeo` adıyla YAYINLANDI ve kullanıldı: bu adla açılmış dizinlerde
# gerçek kullanıcı verisi (üretilmiş görseller, kütüphane, tercihler) ve Azure
# anahtarı duruyor. Bir önceki yeniden adlandırmada (`gpt-image-studio` →
# `lumeo`) göç GEREKMEMİŞTİ çünkü uygulama henüz kullanımda değildi; o gerekçe
# 2026-09-10'da geçerliliğini yitirdi ve göç kodu bu yüzden doğdu.
OLD_APP_NAME = "Lumeo"

# `~/.config/<ad>/credentials.env`in dizin adı. Uygulama adının küçük harfli
# hâli DEĞİL, ayrı bir sabit: XDG dizin adları küçük harf geleneğinde ve ikisi
# bir gün ayrışabilir (`Kromis Studio` gibi bir görsel ada geçilirse).
CONFIG_DIRNAME = "kromis"
OLD_CONFIG_DIRNAME = "lumeo"

# Android dalını AÇAN ortam değişkenleri. Kotlin tarafı (ServerService) Python'u
# başlatmadan ÖNCE ikisini de `os.environ`'a yazar.
#
# NEDEN ORTAM DEĞİŞKENİ, `sys.platform` DEĞİL: Chaquopy'de `sys.platform`
# "linux" döner ve masaüstü Linux geliştirmesinden ayırt edilemez — yani bir
# geliştiricinin Linux'ta koşturduğu uygulama Android sanılırdı. Ortam
# değişkeni açık, test edilebilir (monkeypatch) ve mevcut üç dalın hiçbirine
# dokunmuyor.
ANDROID_DATA_ENV = "KROMIS_ANDROID_DATA_DIR"
ANDROID_RESOURCE_ENV = "KROMIS_ANDROID_RESOURCE_DIR"

# Web dağıtımının veri kökü (Faz 0 / Adım 4): `KROMIS_DATA_DIR=/veri` verilirse
# output/, assets/ ve manifest'ler oraya iner. Konteynerde ne Application
# Support ne repo kökü anlamlı — bind-mount edilen tek bir dizin var ve onu
# işletmen söyler. Değişken `data_dir`de EN ÖNDE bakılıyor: açık bir işletmen
# kararı, dalların otomatik tahminini (frozen mı, Android mi) yenmeli.
# `resource_dir`i ETKİLEMEZ: static/ ve bundled/ paketle gelir, veriyle değil.
DATA_DIR_ENV = "KROMIS_DATA_DIR"


def is_android() -> bool:
    """Chaquopy içinde, Android uygulamasının kabuğunda mı çalışıyoruz?"""
    return bool(os.environ.get(ANDROID_DATA_ENV))


def is_frozen() -> bool:
    """PyInstaller paketi içinde mi çalışıyoruz?"""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """Salt-okunur paket içeriğinin kökü (static/, bundled/).

    Android'de bu dizin APK'nın `assets/`i DEĞİL, oradan `filesDir/resources/`
    altına KOPYALANMIŞ hâlidir. Gerekçe: `app.py` hem `StaticFiles(directory=…)`
    hem `FileResponse` ile gerçek bir dosya sistemi yolu istiyor; Android'in
    asset yöneticisi yalnız akış (stream) veriyor, yol vermiyor. Kopyalamayı
    Kotlin tarafı yapıp yolu bu değişkenle bildiriyor.
    """
    if is_android():
        # Kaynak dizini ayrıca verilmemişse veri kökünün altındaki `resources/`:
        # kopyalamayı yapan Kotlin kodu ile buradaki varsayılan aynı yerleşimi
        # anlatıyor, yani iki taraftan biri unutulursa yol yine çözülür.
        return os.environ.get(ANDROID_RESOURCE_ENV) or os.path.join(
            _android_data_dir(), "resources")
    if is_frozen():
        return getattr(sys, "_MEIPASS", REPO_DIR)
    return REPO_DIR


def _android_data_dir() -> str:
    """Android'de uygulamanın özel (app-private) yazılabilir kökü."""
    return os.environ[ANDROID_DATA_ENV]


def data_dir() -> str:
    """Yazılabilir kullanıcı verisinin kökü (output/, assets/, manifest'ler).

    Windows'ta `%LOCALAPPDATA%`, `%APPDATA%` DEĞİL: burada üretilen görseller
    duruyor ve dizin yüzlerce MB'a çıkıyor — Roaming profil bunu etki alanı
    oturum açmalarında ağ üzerinden taşımaya çalışırdı. `%LOCALAPPDATA%`,
    macOS'taki `~/Library/Application Support`'un doğru karşılığı.

    Ortam değişkeni tanımsızsa (hizmet hesabı, soyulmuş ortam) yol elle
    `~\\AppData\\Local` olarak kuruluyor: kökün çözülememesi uygulamanın hiç
    açılmaması demek olurdu.

    Android'de kök, Kotlin'in bildirdiği app-private dizindir (`filesDir`).
    Orada `~` GÜVENİLİR DEĞİL: `HOME` kimi cihazlarda hiç tanımlı olmuyor,
    kimilerinde `/` gösteriyor — yani `expanduser` sessizce yazılamayan bir yol
    üretirdi. `APP_NAME` de EKLENMİYOR: `filesDir` zaten yalnız bu uygulamaya
    ait, uygulama adıyla ikinci bir kademe açmak boşuna derinlik olurdu.
    """
    acik = os.environ.get(DATA_DIR_ENV)
    if acik:
        return acik
    if is_android():
        return _android_data_dir()
    if not is_frozen():
        return REPO_DIR
    return _desktop_data_root(APP_NAME)


def _desktop_data_root(app_name: str) -> str:
    """Frozen masaüstü yerleşiminde `app_name` uygulamasının veri kökü.

    Ad PARAMETRE, sabit değil: göç kodu aynı dal düzenini ESKİ adla sormak
    zorunda (`_migrate_from_old_name`) ve iki yere ayrı ayrı yazılmış bir dal
    düzeni bir gün ayrışırdı — göç o gün sessizce yanlış dizine bakıp
    "taşınacak bir şey yok" derdi. Gerekçeler `data_dir`'in docstring'inde.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local, app_name)
    return os.path.join(os.path.expanduser("~/Library/Application Support"), app_name)


def output_dir() -> str:
    return os.path.join(data_dir(), "output")


def assets_dir() -> str:
    return os.path.join(data_dir(), "assets")


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def bundled_prompts_dir() -> str:
    """Gömülü sistem talimatlarının dizini (Prompt Yönetmeni personası)."""
    return os.path.join(resource_dir(), "bundled", "prompts")


def bundled_i18n_dir() -> str:
    """Arayüz sözlüklerinin dizini (`tr.json`, `en.json`).

    `static/` ALTINDA DEĞİL ve bu bilinçli: sözlüğü tarayıcı kadar SUNUCU da
    okuyor — `app.index` HTML'i servis ederken çeviriyor ve rotalar hata
    mesajlarını buradan üretiyor. `static/` "tarayıcıya servis edilen dosya"
    demek; `bundled/` ise tam olarak "uygulamanın okuduğu, paketle gelen veri"
    için var (bugünkü tek sakini Yönetmen personası).

    Ayrımın ölçülebilir bir bedeli de yok: `kromis.spec` ve
    `android/app/build.gradle` iki dizini de BÜTÜN olarak paketliyor, yani yeni
    bir dil dosyası ikisinde de değişiklik gerektirmiyor
    (`tests/test_paket_icerik_listesi.py` bunun bekçisi).
    """
    return os.path.join(resource_dir(), "bundled", "i18n")


def chat_instructions_override() -> str:
    """Kullanıcının düzenleyebildiği talimat dosyası (varsa gömülü olanı EZER).

    data_dir()'de, resource_dir()'de DEĞİL: paket içeriği salt-okunur ve frozen'da
    _MEIPASS her kapanışta siliniyor — oraya yazılan bir talimat kaybolur ve
    paketlenmiş .app'te hiç düzenlenemez.
    """
    return os.path.join(data_dir(), "chat-instructions.md")


def chat_video_instructions_override() -> str:
    """Video yönetmenliği bölümünün kullanıcı ezmesi (varsa gömülü olanı EZER).

    Yukarıdakinin birebir ikizi ve aynı gerekçeyle `data_dir()`'de. Video
    talimatı ayrı bir dosya çünkü sistem mesajına yalnız kullanıcının video
    modeli yapılandırılmışsa giriyor (bkz. chat_prompt.build_system); ezmesinin
    de ayrı olması bunun doğal sonucu — tek dosya olsaydı video bölümünü
    özelleştirmek isteyen kullanıcı görsel personayı da üstlenmek zorunda
    kalırdı.
    """
    return os.path.join(data_dir(), "chat-instructions-video.md")


def credentials_path() -> str:
    """Uygulamanın KENDİ kimlik dosyası — Ayarlar penceresi buraya yazar.

    Masaüstünde `~/.config/kromis/`; karar `azure_client`'tan buraya taşındı ki
    Android dalı tek bir yerde açılabilsin. Dizin adı İKİ kez değişti:
    `gpt-image-studio` → `lumeo` geçişinde veri taşıma adımı GEREKMEDİ (uygulama
    henüz kullanımda değildi), `lumeo` → `kromis` geçişinde GEREKTİ — dosyanın
    içinde kullanıcının Azure anahtarı var ve taşınmazsa uygulama açılışta
    "kimlik yok" der. Göç `_migrate_from_old_name` içinde.

    Android'de `~` KULLANILAMAZ (bkz. `data_dir`), bu yüzden dosya app-private
    kökün altına iniyor. Dizin zaten yalnız bu uygulamaya açık; üstelik
    `azure_client._atomic_write` orada da 0o700 + 0o600 uyguluyor. Keystore /
    EncryptedSharedPreferences bu aşamada bilerek kullanılmıyor: app-private
    dizin root olmayan bir cihazda başka uygulamalara kapalı ve şifreleme
    anahtarı yine aynı cihazda dururdu — kazanç, getirdiği karmaşıklığı
    karşılamıyor.
    """
    if is_android():
        return os.path.join(data_dir(), "credentials.env")
    return _desktop_credentials_path(CONFIG_DIRNAME)


def _desktop_credentials_path(config_dirname: str) -> str:
    """`~/.config/<config_dirname>/credentials.env`.

    Dizin adı PARAMETRE — gerekçe `_desktop_data_root` ile aynı: göç eski adı
    aynı yol düzeniyle sormak zorunda.
    """
    return os.path.expanduser(f"~/.config/{config_dirname}/credentials.env")


def shared_credentials_path() -> str | None:
    """`claude-tools` ile PAYLAŞILAN kimlik dosyası; Android'de yok (None).

    Masaüstünde bu dosya, uygulamanın kendi dosyası yokken kutudan çıktığı gibi
    çalışmayı sağlıyor — mevcut kurulumlar buna dayanıyor, o yüzden yol ve sıra
    değiştirilmedi.

    Android'de karşılığı YOK: telefonda ne `claude-tools` kurulu ne de
    uygulamalar arası okunabilen böyle bir dizin var. `None` döndürmek,
    `azure_client`'ın aday listesini tek dosyaya indiriyor.
    """
    if is_android():
        return None
    return os.path.expanduser("~/.config/claude-tools/azure-gpt-image2.env")


def _move_if_new_is_absent(old: str, new: str) -> None:
    """`old`'u `new`'e taşır — ama YALNIZ `new` yokken ya da boş bir dizinken.

    Dört kural ve NEDEN'leri:

    1. `new` doluysa HİÇBİR ŞEY yapılmaz. Kullanıcı yeni adla zaten çalışmışsa
       taze verisi, eski kurulumun bayat verisiyle ezilemez. Boş bir dizin
       göçü ENGELLEMEZ: `makedirs`'in bir önceki açılışta açıp bıraktığı boş
       kabuk "kullanıcı yeni adla çalıştı" demek değil.
    2. Taşıma `os.rename`: aynı birimde atomik ve bedava. Kopyala-sonra-sil
       olsaydı yarı yolda kesilen bir göç (kapatma, disk dolması) veriyi iki
       dizine bölerdi ve hangisinin doğru olduğu bilinemezdi.
    3. Hiçbir şey SİLİNMEZ. Tek istisna hedefteki BOŞ dizin — `os.rename`
       Windows'ta var olan bir hedefin üstüne yazmıyor, `rmdir` o kabuğu
       kaldırıyor ve boş bir dizinde kaybedilecek veri yok.
    4. `OSError` YUTULUR (kilitli dosya, salt-okunur birim, farklı sürücü —
       `rename` birimler arasında çalışmaz) ve `hata.log`'a yazılır. Bir göç
       hatası uygulamayı hiç açılamaz hâle getirmemeli: en kötü hâlde kullanıcı
       verisini kaybetmiş SANIR, oysa eski dizin olduğu gibi yerinde durur ve
       log nereye bakacağını söyler.
    """
    if not os.path.exists(old):
        return
    if os.path.exists(new) and (not os.path.isdir(new) or os.listdir(new)):
        return
    try:
        if os.path.isdir(new):
            os.rmdir(new)
        os.makedirs(os.path.dirname(new), exist_ok=True)
        os.rename(old, new)
    except OSError as e:
        errlog.safe_append(data_dir(), f"Veri göçü başarısız: {old} -> {new}: {e}")


def _migrate_from_old_name() -> None:
    """Eski adla (`Lumeo`) açılmış kullanıcı verisini yeni ada taşır.

    `ensure_data_dirs()`in İÇİNDE, `makedirs`'ten ÖNCE çağrılıyor — sıra
    sözleşmenin parçası: dizinler bir kez açıldıktan sonra "yeni dizin boş mu"
    sorusunun cevabı değişir ve göç bir daha hiç koşmaz. Üç giriş noktası da
    (`app.py`, `desktop.py`, `android_main.py`) açılışta orayı çağırıyor,
    import'ta değil (`tests/test_paths.py` bunun bekçisi).

    Android'de HİÇ koşmaz. Orada kök `filesDir` ve uygulama adı yolun hiçbir
    yerinde geçmiyor; üstelik `applicationId` de değiştiği için eski
    uygulamanın app-private dizini yeni uygulamaya KAPALI — okunamayan bir
    dizini taşımaya çalışmak yalnız hata üretirdi. Telefondaki eski veri
    bilinçli olarak KAYIP; KURULUM.md bunu kullanıcıya yazıyor.
    """
    if is_android():
        return
    # Veri kökü adı YALNIZ frozen'da taşıyor. Geliştirmede kök repo dizinidir
    # ve `REPO_DIR`i taşımaya çalışmak deponun kendisini oynatırdı.
    if is_frozen():
        _move_if_new_is_absent(_desktop_data_root(OLD_APP_NAME), data_dir())
    # Kimlik dosyası frozen'dan BAĞIMSIZ: kaynaktan çalıştıran da aynı
    # `~/.config/<ad>/credentials.env`i kullanıyor ve içinde Azure anahtarı var.
    _move_if_new_is_absent(_desktop_credentials_path(OLD_CONFIG_DIRNAME),
                           credentials_path())


def ensure_data_dirs(*dizinler: str) -> None:
    """Yazılabilir dizinleri oluşturur; var olanlara dokunmaz.

    Göç `makedirs`'ten ÖNCE: gerekçe `_migrate_from_old_name`'de. Çağrı MODÜL
    GLOBAL'i üzerinden gidiyor, `from ... import` ile değil — testlerin
    (ve `tests/conftest.py`'nin gerçek `~/.config` ağacını koruyan guard'ının)
    onu değiştirebilmesi buna bağlı.

    `dizinler` verilirse ONLAR açılır (web bileşim kökü `app.py` ayar
    nesnesinin `output_dir`/`assets_dir`ini geçiyor — Faz 0 / Adım 4; ayar
    nesnesi testte başka yere yönlendirilmişse açılan dizin de o olmalı).
    Verilmezse bu modülün kendi çözdüğü çift: dondurulmuş kabuklar
    (`desktop.py`, `android_main.py`) argümansız çağırıyor ve onlara
    dokunulmuyor.
    """
    _migrate_from_old_name()
    for path in dizinler or (output_dir(), assets_dir()):
        os.makedirs(path, exist_ok=True)
