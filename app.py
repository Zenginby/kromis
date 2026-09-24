# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kromis Studio — yerel FastAPI arayüzü: BİLEŞİM KÖKÜ.

Faz 0 / Adım 2'ye (docs/faz0-web-first.md) kadar 45 rota ve yardımcıları bu
dosyadaydı (2.299 satır). Artık burada yalnız uygulamanın KURULUMU var:
veri dizinleri, açılış (`_lifespan`), ara katman, hata işleyici, router'ların
takılması ve `/static` mount'u. Rotalar `routers/` altında alan bazlı,
rota dışı mantık `services/` altında. Yön tek: app → routers → services →
kütüphane; hiçbir router ya da service bu dosyayı ithal etmez (döngü).
Bekçisi tests/test_app_bolme.py.
"""
from __future__ import annotations

import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

import catalog
import chat_client as cc
import chat_prompt
import composite
import credstore
import errlog
import paths
import providers
from models import MAX_PROMPT_CHARS, GenerateRequest
from routers import (
    admin,
    ayarlar,
    bindirme,
    galeri,
    hesap,
    isler,
    kok,
    odeme,
    paletler,
    saglik,
    sohbet,
    uretim,
)
from services import (
    ayar,
    db,
    dil,
    dosya,
    gorsel,
    gunluk,
    hata_izleme,
    istek_kimligi,
    kimlik,
    koken,
    modeller,
    palet,
    posta,
    redaksiyon,
    sifre,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Sunucu başlarken çalışır — import anında DEĞİL.

    Dizin açma gerçek dosya sistemine dokunduğu için modül kapsamında
    çalışmamalı: app'i yalnızca import eden bir test ya da betik kullanıcının
    gerçek veri dizinini (frozen'da ~/Library/Application Support/...)
    yaratmasın, assets/'ine yazmasın.

    Guard'ın gerekçesi: patlarsa (izinsiz Application Support, dolu disk) tek
    başına pencereyi engellememeli — guard olmadan uvicorn'un startup()'ı asla
    bitmez, desktop.py 15 sn sonra hata verir ve kullanıcı hiçbir pencere
    görmez. Dosya yazan depolar (`depo_medya`, `depo_varlik`) kendi
    `makedirs`'ini zaten yapıyor, yani hata gerçekten kalıcıysa kullanıcı istek
    başına anlaşılır bir hata görür; açılmayan bir uygulamadan iyidir. Hata
    hata.log'a yazılır, uygulama yine de açılır.

    İKİ ADIM BURADAN ÇIKTI (Faz 1 / 6): `backup.backup_manifests_if_version_changed`
    — yedeklenecek manifest kalmadı (galeri, klasör, sohbet, palet, varlık,
    tercih DB'de), DB yedeği platformun işi (9. görev); ve
    `assets_store.migrate_legacy_uploads` — ölü `uploads` türünü içe aktarma
    aracı taşıyacak (8. görev), web yolunda manifest okunmaz. İkisinin modülü
    dondurulmuş kabuk için duruyor. Daha önce bir üçüncüsü de vardı:
    `seed.seed_builtin_logos` (marka-nötr olunca kalktı).

    Dizinler `app.state.ayarlar`dan (Faz 0 / Adım 4), `paths`ten DEĞİL:
    testler o nesneyi geçici dizine yönlendiriyor ve açılışın açtığı yer de
    o olmalı — yoksa `with TestClient(app)` yine geliştiricinin gerçek veri
    dizinine dokunurdu (2. görevin ölçtüğü sızıntı sınıfı).

    VERİ TABANI MOTORU DA BURADA KURULUR (Faz 1 / 1. görev; gerekçesi
    services/db.py): `DATABASE_URL` verilmişse `app.state.motor`a tek bir
    `Engine`, kapanışta `dispose`. İthal anında DEĞİL — `TestClient(app)`i
    `with`siz kullanan 37 test dosyası Postgres'siz açılabilmeli. Kurulamazsa
    (bozuk URL) aynı guard: hata `hata.log`a, uygulama açılır, `/health`
    `db_reachable:false` ile 503 der — açılmayan uygulamadan iyidir ve sonda
    sebebi söyler. `create_engine` bağlanmaz; sunucunun yokluğu ilk istekte
    ya da sondada görünür, açılışı bekletmez.

    POSTACI DA BURADA (Faz 1 / 3, gerekçesi services/posta.py): `KROMIS_POSTA`
    / `RESEND_API_KEY` ortamdan bir kez okunur, `app.state.postaci`ya konur.
    Yanlış yapılandırma uygulamayı DURDURMAZ — `BozukPostaci` gelir ve ilk
    e-posta isteyen rota 503 der, sebep `hata.log`da.

    TEK İSTİSNA — `KROMIS_SECRET_KEY` (Faz 1 / 7, services/sifre.py): web'de
    (`DATABASE_URL` verilmiş süreç) anahtar yoksa ya da bozuksa uygulama
    AÇILMAZ; guard YOK, bilerek. Öteki iki adımın "açılmayan uygulamadan iyidir"
    gerekçesi burada tersine döner: anahtarsız açılan bir süreç sağlayıcı
    kimliği yazamaz/okuyamaz ve sessiz bir varsayılan anahtar, şifreli sütunu
    herkesin okuduğu bir sütuna çevirir. Hata `hata.log`a da yazılır, sonra
    yükselir — uvicorn "Application startup failed" der ve çıkar. DB'siz
    süreçte (dondurulmuş kabuk, `/health` sondası) kapı yok: orada okunacak
    kimlik satırı da yok.
    """
    ayarlar: ayar.Ayarlar = app.state.ayarlar
    # JSON günlük (Faz 2 / 8-9; services/gunluk.py). Guard YOK: tanınmayan `KROMIS_GUNLUK_BICIMI`
    # açılışı durdurur (yazım hatası sessizce JSON'a düşmesin). Sentry yalnız `SENTRY_DSN`
    # varsa (K10; services/hata_izleme.py): DSN yoksa paket ithal edilmez, bozuk DSN günlüğe.
    gunluk.kur()
    hata_izleme.kur(surec="web")
    url = db.baglanti_dizesi()
    if url:
        try:
            sifre.dogrula_ortam()
        except sifre.AnahtarHatasi:
            errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
            raise
    try:
        app.state.motor = db.motor_kur(url) if url else None
    except Exception:
        app.state.motor = None
        errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
    motor = app.state.motor
    postaci = app.state.postaci = posta.postaci_kur(ayarlar.data_dir)
    try:
        paths.ensure_data_dirs(ayarlar.output_dir, ayarlar.assets_dir)
    except Exception:
        errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
    try:
        yield
    finally:
        # Kapanışta havuz kapanır ve `motor` `None`a döner: bir sonraki
        # `with TestClient(app)` (ya da yeniden açılış) eskimiş, belki
        # düşürülmüş bir DB'ye bağlı motoru bulmamalı.
        #
        # YALNIZ KENDİ KURDUĞUNU düşürür (kimlik karşılaştırması). ÖLÇÜLDÜ
        # (Faz 1 / 3, tam takımda): E2E dosyaları uvicorn'u ayrı bir iş
        # parçacığında koşturuyor ve `stop()` beklemiyor; önceki dosyanın
        # sunucusu kapanışını bitirirken sonraki dosyanın sunucusu çoktan
        # açılmış ve motorunu koymuş oluyordu. Koşulsuz `= None` yeni motoru
        # da siliyor, ilk istek `database_unavailable` alıyordu.
        if motor is not None and app.state.motor is motor:
            app.state.motor = None
            motor.dispose()
        if app.state.postaci is postaci:
            app.state.postaci = None


app = FastAPI(title="Kromis Studio", lifespan=_lifespan)

# AYAR NESNESİ — dizinlerin tek sahibi (Faz 0 / Adım 4; gerekçesi
# services/ayar.py'de). Rotalar `Depends(ayar.ayarlar)` ile, ara katman ve
# `_lifespan` `app.state` üzerinden okuyor; modül düzeyinde `OUTPUT_DIR` gibi
# bir sabit ARTIK YOK ve `services/yollar.py`nin `sys.modules["app"]` bakışı
# da onunla gitti. İthal anında kuruluyor (lifespan'da değil), çünkü bu saf
# bir yol hesabı — dizin açmaz — ve `TestClient(app)`i `with`siz kullanan
# testler lifespan'ı hiç koşturmuyor; nesne orada kurulsa her rota 500 verirdi.
# Testler değiştirmek için `tests/conftest.py::dizinler` fixture'ını kullanır.
# Faz 1 / 4'ten beri bu nesne sürecin PAYLAŞILAN yerleşimi (`ayar.genel`);
# kullanıcıya göre `output_dir`/`assets_dir` `ayar.ayarlar`ın içinde türetiliyor
# (`<data_dir>/kullanicilar/<uuid>/…`), rotalar aynı imzayla okumaya devam ediyor.
app.state.ayarlar = ayar.Ayarlar.varsayilan()

# VERİ TABANI MOTORU — ithal anında YOK (`None`), `_lifespan` kurar (Faz 1 /
# 1. görev, gerekçesi services/db.py). Buradaki atama yalnız adın var olması
# için: `/health` lifespan koşmamış bir süreçte de cevap vermeli ve o cevap
# `db_reachable:false` olmalı, `AttributeError` değil.
app.state.motor = None

# POSTACI — motor gibi ithal anında YOK, `_lifespan` kurar (Faz 1 / 3). Ad
# burada var olsun ki lifespan'sız süreçte hesap rotaları `AttributeError`
# değil 503 (`mail_unavailable`) versin.
app.state.postaci = None

# DOSYA DEPOSU — ayar nesnesi gibi İTHAL ANINDA (Faz 2 / 2; gerekçesi
# services/dosya.py): `KROMIS_NESNE_DEPO_*` dördü doluysa R2/S3 kovası, boşsa
# yerel disk (`data_dir` kökü). Yarım yapılandırma `YapilandirmaHatasi` ile
# ithali DURDURUR — sessizce diske düşen bir dağıtım işçi gelince "üretildi
# ama görünmüyor" olurdu. Nesne kurulurken ağa çıkılmaz (`httpx.Client` tembel).
# Rotalar `Depends(dosya.depo)` ile okur; testler `app.state.dosya`yı yamalar.
app.state.dosya = dosya.depo_kur(app.state.ayarlar.data_dir)

# Dil ara katmanı — `i18n._AKTIF`ın tek yazarı (gerekçesi services/dil.py'de).
# Dekoratörün (`@app.middleware("http")`) çağrı biçimi; işlev başka dosyada
# durduğu için dekoratör olarak yazılamıyor.
app.middleware("http")(dil.dil_baglami)

# Köken kapısı (CSRF'nin ikinci katı, Faz 1 / 3; gerekçesi services/koken.py).
# DİL'DEN SONRA EKLENİYOR ve bu sırayı belirliyor: Starlette son eklenen ara
# katmanı EN DIŞA koyar, yani istek önce buradan geçer, sonra dile, sonra
# rotaya (belge §3: "köken → dil → rota"). Reddedilen istek dil bağlamını
# hiç kurmaz — 403 gövdesinin bir KOD olmasının sebebi de bu.
app.middleware("http")(koken.koken_kapisi)

# İstek kimliği (Faz 2 / 9; gerekçesi services/istek_kimligi.py) EN SON = EN DIŞ katman,
# köken 403'ünü de kapsar: istek kimliği → köken → dil → rota (bekçisi tests/test_koken.py).
app.middleware("http")(istek_kimligi.istek_kimligi)

# Doğrulama hatasından gizli değerin silinmesi (gerekçesi services/redaksiyon.py'de).
# Ara katmanla aynı biçim: dekoratörün çağrı hâli.
app.exception_handler(RequestValidationError)(redaksiyon.redact_validation_errors)

# Oturumsuz TARAYICI GEZİNMESİ → 302 `/giris` (Faz 1 / 4; gerekçesi
# services/kimlik.py). API rotalarının 401'i FastAPI'nin kendi HTTPException
# işleyicisinden geliyor, burada yalnız sayfa yönlendirmesinin istisnası var.
app.exception_handler(kimlik.GirisSayfasi)(kimlik.giris_sayfasina)
# Admin OLMAYAN kullanıcının `/admin` gezinmesi → 403 HTML (Faz 2 / 8; gerekçesi
# services/kimlik.py `YetkiYok`). API rotalarının 403'ü JSON ve kapının kendisinden.
app.exception_handler(kimlik.YetkiYok)(kimlik.yetki_yok_sayfasi)

# Router'lar ÖNEKSİZ takılıyor: yollar her rotanın üstünde birebir yazılı (routers/__init__.py).
# Sıra rota eşleşmesini etkilemiyor (iki kalıp aynı yol+fiili paylaşmıyor); eski app.py sırası.
for _router in (uretim.router, isler.router, ayarlar.router, sohbet.router, galeri.router,
                paletler.router, bindirme.router, hesap.router, admin.router, kok.router,
                saglik.router, odeme.router):
    app.include_router(_router)


# static/ dosyalarını /static altında servis et (index route'undan sonra mount).
# Geliştirmede static dizini git'te izlenen bir dizindir ama boş bir checkout'ta
# (taze klon) henüz yoksa StaticFiles mount'u import anında patlardı — bu
# yüzden yalnızca geliştirmede garanti altına alınır. Paket içindeyken
# (frozen) static dizini sys._MEIPASS altında PyInstaller'ın gömdüğü salt-okunur
# bir dizindir: hem zaten var, hem de oraya os.makedirs YAZMA denemesi bile
# yanlış — bu dal frozen'da hiç çalışmamalı.
#
# Yazılabilir dizinler (output/, assets/) burada AÇILMAZ: mount'un onlara
# ihtiyacı yok ve import'un yan etkisi olmamalı — açılış `_lifespan`'da.
#
# `/` no-store gönderirken /static'in ÖNBELLEKLENEBİLİR kalması KASITLI bir
# asimetridir, tutarsızlık değil: `?v=<sürüm>` her sürüme ayrı URL veriyor,
# yani bayat bir kayıt hiç ADRESLENMİYOR; üstelik StaticFiles ETag/
# Last-Modified gönderdiği için aynı URL'ye gelen istek loopback'te ucuz bir
# 304'e düşüyor. Buraya no-store eklemek cache-buster mekanizmasının bütün
# anlamını siler.
#
# Mount'un dizini İTHAL ANINDA bağlanıyor ve bu ayar nesnesinin istisnası:
# StaticFiles bir alt uygulama, isteğe bağlı çözülemez. Zararsız — static/
# kullanıcı verisi değil, paketle gelen içerik; Faz 1'de kiracıya göre
# değişecek olan şey o değil. `index()` rotası ise şablonun dizinini istek
# anında ayar nesnesinden okuyor (testler orayı yönlendiriyor).
if not paths.is_frozen():
    os.makedirs(app.state.ayarlar.static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=app.state.ayarlar.static_dir), name="static")


# ── Geriye uyum: bu modülden OKUNAN adlar ─────────────────────────────────
# Testler (ve `netguard`/`android_main` yalnız `app` için) bu adlara `import app
# as appmod` üzerinden bakıyor; bölünme onların yerini değiştirdi, adını
# değil. Buradaki eşlemeler yalnız OKUMA için — `appmod._is_secret_loc(...)`,
# `appmod.providers` üstünden yapılan `setattr` (modülün kendisini yamalıyor,
# bu bağı değil), `appmod.MAX_EDIT_IMAGES`. YAMALANAN yardımcılar (`_to_png`,
# `_dil`) BİLEREK burada DEĞİL: `appmod._to_png = …` yeni yerini görmeyen ölü
# bir yama olurdu; testler onları asıl yerinde yamalıyor
# (`services.gorsel.to_png`, `services.dil.aktif`). Dizinler de artık burada
# DEĞİL (Faz 0 / Adım 4): `appmod.OUTPUT_DIR` yaması ayar nesnesini görmezdi;
# testler `app.state.ayarlar`ı `tests/conftest.py::dizinler` ile değiştiriyor.
#
# Her satırın karşılığı bir test dosyası; okunmayan ad buradan düşer.
__all__ = [
    "app",
    # depo modülleri — testler `appmod.<modül>` üstünden yamalıyor
    "catalog", "cc", "chat_prompt", "composite",
    "credstore", "errlog", "paths", "providers",
    # sabitler
    "MAX_UPLOAD_BYTES", "MAX_EDIT_IMAGES", "MAX_REQUEST_BYTES",
    "MAX_IMAGE_PIXELS", "MAX_FOLDER_DEPTH", "MAX_PROMPT_CHARS",
    "GenerateRequest",
    # salt okunan yardımcılar
    "_is_secret_loc", "_resolve_palette", "_saved_colors", "_settings_payload",
    "_director_context", "_provider_logo_url", "_auto_title",
]
MAX_UPLOAD_BYTES = gorsel.MAX_UPLOAD_BYTES
MAX_EDIT_IMAGES = gorsel.MAX_EDIT_IMAGES
MAX_REQUEST_BYTES = gorsel.MAX_REQUEST_BYTES
MAX_IMAGE_PIXELS = gorsel.MAX_IMAGE_PIXELS
MAX_FOLDER_DEPTH = galeri.MAX_FOLDER_DEPTH
_is_secret_loc = redaksiyon.is_secret_loc
_resolve_palette = palet.resolve_palette
_saved_colors = palet.saved_colors
_settings_payload = modeller.settings_payload
_director_context = modeller.director_context
_provider_logo_url = modeller.provider_logo_url
_auto_title = sohbet._auto_title
