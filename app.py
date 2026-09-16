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
from routers import ayarlar, bindirme, galeri, kok, paletler, sohbet, uretim
from services import dil, gorsel, modeller, palet, redaksiyon, zaman

# Dizinler BURADA tanımlı ve router'lar onları `services.yollar` üzerinden
# İSTEK ANINDA okuyor — çünkü testler bu üç adı 66 yerde bu modülde yamalıyor
# (`monkeypatch.setattr(appmod, "OUTPUT_DIR", tmp_path)`). Gerekçenin tamamı
# services/yollar.py'nin başında; Faz 0'ın 4. görevi bunları bir ayar
# nesnesine taşıyacak.
BASE_DIR = paths.REPO_DIR                    # geriye uyum: mevcut kullanımlar bozulmasın
OUTPUT_DIR = paths.output_dir()
STATIC_DIR = paths.static_dir()
ASSETS_DIR = paths.assets_dir()


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
    """
    now = zaman.simdi()
    try:
        paths.ensure_data_dirs()
        backup.backup_manifests_if_version_changed(
            paths.data_dir(), OUTPUT_DIR, ASSETS_DIR,
            version=version.APP_VERSION, now=now)
        # Ölü `uploads` türünün göçü — YEDEKTEN SONRA, bilerek: göç kullanıcı
        # verisini yerinden oynatan tek açılış adımı, yani sürüm değişiminde
        # alınan yedek göç ÖNCESİ hâli taşımalı. Yeni kurulumda maliyeti tek
        # bir `isdir`; gerekçesi assets_store.migrate_legacy_uploads'ta.
        assets_store.migrate_legacy_uploads(ASSETS_DIR)
    except Exception:
        errlog.safe_append(paths.data_dir(), traceback.format_exc())
    yield


app = FastAPI(title="Kromis Studio", lifespan=_lifespan)

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
                paletler.router, bindirme.router, kok.router):
    app.include_router(_router)


# static/ dosyalarını /static altında servis et (index route'undan sonra mount).
# Geliştirmede STATIC_DIR git'te izlenen bir dizindir ama boş bir checkout'ta
# (taze klon) henüz yoksa StaticFiles mount'u import anında patlardı — bu
# yüzden yalnızca geliştirmede garanti altına alınır. Paket içindeyken
# (frozen) STATIC_DIR sys._MEIPASS altında PyInstaller'ın gömdüğü salt-okunur
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
if not paths.is_frozen():
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Geriye uyum: bu modülden OKUNAN adlar ─────────────────────────────────
# Testler (ve `netguard`/`android_main` yalnız `app` için) bu adlara `import app
# as appmod` üzerinden bakıyor; bölünme onların yerini değiştirdi, adını
# değil. Buradaki eşlemeler yalnız OKUMA için — `appmod._is_secret_loc(...)`,
# `appmod.providers` üstünden yapılan `setattr` (modülün kendisini yamalıyor,
# bu bağı değil), `appmod.MAX_EDIT_IMAGES`. YAMALANAN yardımcılar (`_to_png`,
# `_dil`) BİLEREK burada DEĞİL: `appmod._to_png = …` yeni yerini görmeyen ölü
# bir yama olurdu; testler onları asıl yerinde yamalıyor
# (`services.gorsel.to_png`, `services.dil.aktif`). Dizinler (yukarıda) bunun
# istisnası ve mekanizması services/yollar.py'de yazılı.
#
# Kalıcı değil: Faz 0'ın 4. görevi testleri ayar nesnesine geçirdiğinde bu
# blok da küçülür. O güne kadar her satırın karşılığı bir test dosyası.
__all__ = [
    "app", "BASE_DIR", "OUTPUT_DIR", "STATIC_DIR", "ASSETS_DIR",
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
