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
`desktop.py -> app.py -> (paths/seed/composite/storage/folders/assets_store/
azure_client/models/palette/palette_store/color_names)` zinciri de düz
`import` ifadeleri olduğundan statik analiz zaten buluyor. Bu yüzden
`hiddenimports` burada boş — bu makinede üretilen bitmiş `.app` bundle'ı
üzerinde doğrulandı (bkz. task-6 raporu); arm64 runner'da farklı çıkarsa
orada yeniden doğrulanmalı.
"""

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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='GPT-Image Studio',
)
app = BUNDLE(
    coll,
    name='GPT-Image Studio.app',
    icon=None,
    bundle_identifier='org.zenginby.gptimagestudio',
    info_plist={
        'LSMultipleInstancesProhibited': True,   # iki kez çift tıklama ikinci sunucu doğurmaz
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.8.0',
        'CFBundleVersion': '1.8.0',
        'LSMinimumSystemVersion': '13.0',
    },
)
