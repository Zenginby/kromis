# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
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

import assets_store
import backup
import catalog
import chat_client as cc
import chat_prompt
import composite
import credstore
import errlog
import paths
import providers
import version
from models import MAX_PROMPT_CHARS, GenerateRequest
from routers import ayarlar, bindirme, galeri, kok, paletler, saglik, sohbet, uretim
from services import ayar, db, dil, gorsel, modeller, palet, redaksiyon, zaman


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Sunucu başlarken çalışır — import anında DEĞİL.

    Dizin açma ve yedek gerçek dosya sistemine dokunduğu için modül kapsamında
    çalışmamalı: app'i yalnızca import eden bir test ya da betik kullanıcının
    gerçek veri dizinini (frozen'da ~/Library/Application Support/...)
    yaratmasın, assets/'ine yazmasın.

    Guard'ın gerekçesi: patlarsa (izinsiz Application Support, dolu disk) tek
    başına pencereyi engellememeli — guard olmadan uvicorn'un startup()'ı asla
    bitmez, desktop.py 15 sn sonra hata verir ve kullanıcı hiçbir pencere
    görmez. Yazma yollarının hepsi (storage, assets_store, folders,
    palette_store) kendi `makedirs`'ini zaten yapıyor, yani hata gerçekten
    kalıcıysa kullanıcı istek başına anlaşılır bir hata görür; açılmayan bir
    uygulamadan iyidir. Hata hata.log'a yazılır, uygulama yine de açılır.

    Yedek bir EMNİYET özelliği olduğu için "başarısızsa durdur" cazibesi var;
    YAPILMIYOR — yedek yüzünden uygulamaya giremeyen kullanıcının verisine
    arayüzden hiçbir yolu kalmaz, bu loglanmış-ama-alınmamış bir yedekten
    kesinlikle kötüdür.

    NOT: Burada bir İKİNCİ adım vardı — `seed.seed_builtin_logos`
    pakete gömülü yerleşik logo çiftini kullanıcının kütüphanesine kopyalardı.
    Uygulama marka-nötr olduğundan o modül tamamen kaldırıldı; kütüphane artık
    boş başlar ve kullanıcı kendi logosunu yükler.

    `backup` MODÜL NİTELİĞİ üzerinden çağrılıyor (`from backup import …` değil):
    tests/conftest.py'nin gerçek-yedek koruması o niteliği yamalıyor.

    Dizinler `app.state.ayarlar`dan (Faz 0 / Adım 4), `paths`ten DEĞİL:
    testler o nesneyi geçici dizine yönlendiriyor ve açılışın açtığı/yedeklediği
    yer de o olmalı — yoksa `with TestClient(app)` yine geliştiricinin gerçek
    veri dizinine dokunurdu (2. görevin ölçtüğü sızıntı sınıfı).

    VERİ TABANI MOTORU DA BURADA KURULUR (Faz 1 / 1. görev; gerekçesi
    services/db.py): `DATABASE_URL` verilmişse `app.state.motor`a tek bir
    `Engine`, kapanışta `dispose`. İthal anında DEĞİL — `TestClient(app)`i
    `with`siz kullanan 37 test dosyası Postgres'siz açılabilmeli. Kurulamazsa
    (bozuk URL) aynı guard: hata `hata.log`a, uygulama açılır, `/health`
    `db_reachable:false` ile 503 der — açılmayan uygulamadan iyidir ve sonda
    sebebi söyler. `create_engine` bağlanmaz; sunucunun yokluğu ilk istekte
    ya da sondada görünür, açılışı bekletmez.
    """
    ayarlar: ayar.Ayarlar = app.state.ayarlar
    now = zaman.simdi()
    try:
        url = db.baglanti_dizesi()
        app.state.motor = db.motor_kur(url) if url else None
    except Exception:
        app.state.motor = None
        errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
    try:
        paths.ensure_data_dirs(ayarlar.output_dir, ayarlar.assets_dir)
        backup.backup_manifests_if_version_changed(
            ayarlar.data_dir, ayarlar.output_dir, ayarlar.assets_dir,
            version=version.APP_VERSION, now=now)
        # Ölü `uploads` türünün göçü — YEDEKTEN SONRA, bilerek: göç kullanıcı
        # verisini yerinden oynatan tek açılış adımı, yani sürüm değişiminde
        # alınan yedek göç ÖNCESİ hâli taşımalı. Yeni kurulumda maliyeti tek
        # bir `isdir`; gerekçesi assets_store.migrate_legacy_uploads'ta.
        assets_store.migrate_legacy_uploads(ayarlar.assets_dir)
    except Exception:
        errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
    try:
        yield
    finally:
        # Kapanışta havuz kapanır ve `motor` `None`a döner: bir sonraki
        # `with TestClient(app)` (ya da yeniden açılış) eskimiş, belki
        # düşürülmüş bir DB'ye bağlı motoru bulmamalı.
        motor = app.state.motor
        app.state.motor = None
        if motor is not None:
            motor.dispose()


app = FastAPI(title="Kromis Studio", lifespan=_lifespan)

# AYAR NESNESİ — dizinlerin tek sahibi (Faz 0 / Adım 4; gerekçesi
# services/ayar.py'de). Rotalar `Depends(ayar.ayarlar)` ile, ara katman ve
# `_lifespan` `app.state` üzerinden okuyor; modül düzeyinde `OUTPUT_DIR` gibi
# bir sabit ARTIK YOK ve `services/yollar.py`nin `sys.modules["app"]` bakışı
# da onunla gitti. İthal anında kuruluyor (lifespan'da değil), çünkü bu saf
# bir yol hesabı — dizin açmaz — ve `TestClient(app)`i `with`siz kullanan
# testler lifespan'ı hiç koşturmuyor; nesne orada kurulsa her rota 500 verirdi.
# Testler değiştirmek için `tests/conftest.py::dizinler` fixture'ını kullanır.
app.state.ayarlar = ayar.Ayarlar.varsayilan()

# VERİ TABANI MOTORU — ithal anında YOK (`None`), `_lifespan` kurar (Faz 1 /
# 1. görev, gerekçesi services/db.py). Buradaki atama yalnız adın var olması
# için: `/health` lifespan koşmamış bir süreçte de cevap vermeli ve o cevap
# `db_reachable:false` olmalı, `AttributeError` değil.
app.state.motor = None

# Dil ara katmanı — `i18n._AKTIF`ın tek yazarı (gerekçesi services/dil.py'de).
# Dekoratörün (`@app.middleware("http")`) çağrı biçimi; işlev başka dosyada
# durduğu için dekoratör olarak yazılamıyor.
app.middleware("http")(dil.dil_baglami)

# Doğrulama hatasından gizli değerin silinmesi (gerekçesi services/redaksiyon.py'de).
# Ara katmanla aynı biçim: dekoratörün çağrı hâli.
app.exception_handler(RequestValidationError)(redaksiyon.redact_validation_errors)

# Router'lar ÖNEKSİZ takılıyor: yollar her rotanın üstünde birebir yazılı
# (bkz. routers/__init__.py). Sıra rota eşleşmesini etkilemiyor — hiçbir iki
# kalıp aynı yol+fiili paylaşmıyor — ama okunurluk için eski app.py sırası.
for _router in (uretim.router, ayarlar.router, sohbet.router, galeri.router,
                paletler.router, bindirme.router, kok.router, saglik.router):
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
    "assets_store", "backup", "catalog", "cc", "chat_prompt", "composite",
    "credstore", "errlog", "paths", "providers", "version",
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
