# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: GPT-Image Studio -> macOS .app.

`target_arch` kasıtlı olarak verilmiyor: PyInstaller o zaman derlemeyi
çalıştıran yorumlayıcının mimarisini hedefler. Bu, iki hattın da AYNI spec ve
build.sh ile, değişiklik gerektirmeden çalışmasını sağlar — bu makinede
(Intel) yerel doğrulama derlemesi x86_64 üretir; Apple Silicon'a gönderilecek
gerçek paket GitHub Actions'ın arm64 runner'ında bu aynı dosyalarla üretilir.
Mimariyi elle 'arm64' ya da 'x86_64' olarak sabitlemek, çalıştığı makineden
farklı bir hedef seçilirse geçen görevde yaşanan IncompatibleBinaryArchError'ı
geri getirir (bkz. task-6 raporu).

Not: `uvicorn`, `_pyinstaller_hooks_contrib`'in kendi `hook-uvicorn.py`'si
üzerinden `collect_submodules('uvicorn')` ile zaten TÜMÜYLE toplanıyor;
`desktop.py -> (errlog/paths/screencolor) + app.py -> (paths/seed/backup/
composite/storage/folders/assets_store/azure_client/models/palette/
palette_store/color_names/version)` zinciri de düz `import` ifadeleri
olduğundan statik analiz zaten buluyor. Bu yüzden `hiddenimports` burada boş —
bu makinede üretilen bitmiş `.app` bundle'ı üzerinde doğrulandı (bkz. task-6
raporu); arm64 runner'da farklı çıkarsa orada yeniden doğrulanmalı.

`screencolor` (v1.11, damlalık köprüsü) `AppKit`'i FONKSİYON İÇİNDE import
ediyor. PyInstaller bunu bytecode'dan bulur, ayrıca `AppKit` pywebview'ın
cocoa arka ucu üzerinden zaten toplanıyor — yani ek bir hiddenimport
beklenmiyor. Ama bu, paket üzerinde damlalık gerçekten açılarak doğrulanmalı:
açılmıyorsa `hiddenimports=['AppKit']` gerekir.

DİKKAT: `version.py` pakete YALNIZCA `app.py`'nin `import version`'ı sayesinde
giriyor. Aşağıdaki derleme-zamanı yüklemesi hiçbir şey PAKETLEMEZ; yalnızca
plist için değeri okur. O import "kullanılmıyor" diye silinirse paket
`ModuleNotFoundError` ile ölür ve tek iz `hata.log` olur.
"""

# Sürüm TEK kaynaktan (version.py) okunur; buraya elle YAZILMAZ.
#
# Düz `import version` DEĞİL: PyInstaller bu dosyayı `exec(code, {...})` ile
# çalıştırıyor — namespace'te `__file__` YOK ve spec'in dizini sys.path'e
# EKLENMİYOR (`pathex` yalnızca Analysis içinde ekleniyor, o da bu satırdan
# sonra). `pyinstaller` kurulu bir konsol betiği olduğu için sys.path[0]
# .venv/bin'dir; build.sh repo köküne `cd` etse bile düz import ImportError
# verir. PyInstaller'ın verdiği `SPECPATH` globali spec dosyasının dizinidir —
# tek doğru çapa o. importlib ile yükleme sys.path'i de kirletmez.
import importlib.util
import os

_version_spec = importlib.util.spec_from_file_location(
    "_gis_version", os.path.join(SPECPATH, "version.py"))
_version_module = importlib.util.module_from_spec(_version_spec)
_version_spec.loader.exec_module(_version_module)
APP_VERSION = _version_module.APP_VERSION

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('bundled', 'bundled'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Bu üçü uvicorn'un "auto" seçiminde yalnızca performans katmanı;
    # yoklukları asyncio/h11/wsproto'ya sessizce düşer (uvicorn'un kendi
    # try/except ImportError deseni — desktop.py'ye dokunmadan çalışır).
    # yaml/watchfiles/watchgod ise yalnız `uvicorn --reload` / yaml log
    # config yolunda kullanılır; masaüstü paketi ikisini de kullanmıyor.
    excludes=['uvloop', 'httptools', 'websockets', 'watchfiles', 'watchgod', 'yaml'],
    noarchive=False,
    optimize=0,
)
# upx=False (her iki yerde de): PyInstaller'ın şablon varsayılanı upx=True idi —
# bilinçli bir seçim değildi. UPX yerelde ve macos-14 runner imajında YOK,
# yani bugün sessiz bir no-op; ama PATH'e bir gün eklenirse UPX'in
# Mach-O ikilisini paketlemesi ad-hoc imzayı bozar ve açılmayan bir .app
# üretebilir. Sıfır kazanç için gizli bir kırılma noktası tutmaya değmez.
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GPT-Image Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GPT-Image Studio',
)

import sys

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name='GPT-Image Studio.app',
        icon=None,
        bundle_identifier='org.zenginby.gptimagestudio',
        info_plist={
            'LSMultipleInstancesProhibited': True,   # iki kez çift tıklama ikinci sunucu doğurmaz
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'LSMinimumSystemVersion': '13.0',
        },
    )
