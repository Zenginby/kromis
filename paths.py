"""Yol çözümü: PyInstaller paketi içinde, Android'de ve geliştirmede farklı kökler.

Paket içinde `__file__` geçici çıkarma dizinine düşer; oraya yazılan geçmiş her
kapanışta kaybolur. Bu yüzden yazılabilir veri (output/, assets/) kullanıcının
Application Support dizinine, salt-okunur içerik (static/, bundled/) ise
PyInstaller'ın `sys._MEIPASS` dizinine bağlanır.

Geliştirmede (frozen değilken) her iki kök de repo dizinidir — mevcut testlerin
dayandığı yerleşim birebir korunur.

DÖRT DAL var: Android → frozen-Windows → frozen-macOS → geliştirme. Android
dalı EN ÖNDE, çünkü orada `sys.frozen` yok (Chaquopy sıradan bir CPython
koşturuyor) ve dal sırası tersine olsa Android sessizce geliştirme dalına,
yani APK'nın İÇİNDEKİ salt-okunur dizine yazmaya çalışırdı.
"""
from __future__ import annotations

import os
import sys

APP_NAME = "Lumeo"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# Android dalını AÇAN ortam değişkenleri. Kotlin tarafı (ServerService) Python'u
# başlatmadan ÖNCE ikisini de `os.environ`'a yazar.
#
# NEDEN ORTAM DEĞİŞKENİ, `sys.platform` DEĞİL: Chaquopy'de `sys.platform`
# "linux" döner ve masaüstü Linux geliştirmesinden ayırt edilemez — yani bir
# geliştiricinin Linux'ta koşturduğu uygulama Android sanılırdı. Ortam
# değişkeni açık, test edilebilir (monkeypatch) ve mevcut üç dalın hiçbirine
# dokunmuyor.
ANDROID_DATA_ENV = "GIS_ANDROID_DATA_DIR"
ANDROID_RESOURCE_ENV = "GIS_ANDROID_RESOURCE_DIR"


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
    if is_android():
        return _android_data_dir()
    if not is_frozen():
        return REPO_DIR
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local, APP_NAME)
    return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)


def output_dir() -> str:
    return os.path.join(data_dir(), "output")


def assets_dir() -> str:
    return os.path.join(data_dir(), "assets")


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def bundled_prompts_dir() -> str:
    """Gömülü sistem talimatlarının dizini (Prompt Yönetmeni personası)."""
    return os.path.join(resource_dir(), "bundled", "prompts")


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

    Masaüstünde `~/.config/lumeo/`; karar `azure_client`'tan buraya taşındı ki
    Android dalı tek bir yerde açılabilsin. (Dizin adı yeniden adlandırmada
    `gpt-image-studio` → `lumeo` oldu; uygulama henüz kullanımda olmadığı için
    veri taşıma adımı gerekmedi.)

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
    return os.path.expanduser("~/.config/lumeo/credentials.env")


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


def ensure_data_dirs() -> None:
    """Yazılabilir dizinleri oluşturur; var olanlara dokunmaz."""
    for path in (output_dir(), assets_dir()):
        os.makedirs(path, exist_ok=True)
