# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Lumeo -> macOS .app + Windows klasörü.

TEK spec, İKİ platform: build.sh (macOS) ve build.ps1 (Windows) aynı dosyayı
çağırır. Platforma göre dallanan yalnızca İKİ şey var: sürüm kaynağı
(macOS'ta Info.plist, Windows'ta VERSIONINFO kaynağı) ve BUNDLE adımı (yalnız
macOS). Geri kalan her şey ORTAK — `hiddenimports` dahil, bu ölçüldü (aşağıda).

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

WINDOWS'TA DA BOŞ — VARSAYIM DEĞİL, ÖLÇÜM (v0.3.0, bu makinede):
pywebview'ın Windows arka ucu endişe kaynağıydı çünkü backend seçimi çalışma
anında yapılıyor. Ama zincirin her halkası STATİK `import` ifadesi:
`webview/guilib.py` fonksiyon içinde `import webview.platforms.winforms`,
`winforms.py` ise modül düzeyinde `from . import edgechromium` / `mshtml`
yapıyor — PyInstaller bunları bytecode'dan buluyor. Üretilen paketin PYZ
arşivi açılıp doğrulandı: `webview.platforms.{winforms,edgechromium,mshtml,
win32}` ve `clr` içeride. WebView2 DLL'lerini (`webview/lib/`) ve pythonnet
çalışma zamanını (`Python.Runtime.dll`) hooks-contrib'in kendi
`hook-webview.py`/`hook-clr*.py`'si topluyor.
`warn-*.txt`'teki `System`, `System.Drawing`, `Microsoft.Web` gibi "missing
module" satırları YANILTICI: bunlar Python modülü değil .NET assembly'leri,
`clr.AddReference` ile çalışma anında yükleniyorlar. Aynı biçimde `objc`,
`WebKit`, `AppKit` da Windows'ta eksik görünür — macOS arka ucuna ait, bu
platformda hiç çalışmıyor (`screencolor` v0.3.0'dan beri macOS dışında
`AppKit`'e hiç dokunmuyor).
Kanıt derlemenin ötesinde: paket ÇALIŞTIRILDI — pencere açıldı, `hata.log`
yazılmadı, veri dizini `%LOCALAPPDATA%\\Lumeo` altında doğdu,
pencere kapanınca süreç temiz çıktı. Bir gün paket "açılmıyor" hâline gelirse
ilk bakılacak yer budur: `hiddenimports` eklemek gerekiyorsa hangi modülün
eksik olduğunu `hata.log`'daki traceback söyler.

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
import sys

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
#
# Windows'ta bu satır DAHA çok önemli, iki sebeple: (1) UPX Windows
# makinelerinde PATH'e girmeye çok daha yatkın (chocolatey/scoop paketi),
# yani no-op kalacağının garantisi yok; (2) UPX ile paketlenmiş bir exe
# antivirüs ve SmartScreen için klasik bir şüphe işaretidir — imzasız zaten
# uyarı alan bir uygulamada bunu üstüne eklemek kurulumu iyice zorlaştırır.
pyz = PYZ(a.pure)

# Windows'ta Info.plist'in KARŞILIĞI: VERSIONINFO kaynağı. Olmadan exe'nin
# Özellikler → Ayrıntılar sekmesi boş kalır ve Görev Yöneticisi'nde süreç
# adsız görünür — kullanıcıya "hangi sürümü kullanıyorsun?" diye sorulduğunda
# cevabı bulacağı yer yok. Sürüm yine version.py'den akıyor; buraya literal
# YAZILMAZ (macOS dalındaki CFBundleVersion ile aynı kural).
#
# macOS'ta bilerek üretilmiyor: PyInstaller Windows dışında bu argümanı
# "Ignoring version information" uyarısıyla atıyor, yani üretmek derlemeye
# gürültüden başka bir şey katmazdı.
_version_resource = None
if sys.platform == "win32":
    from PyInstaller.utils.win32 import versioninfo as _vi

    # VERSIONINFO DÖRT parçalı bir sayı ister; APP_VERSION üç parçalı
    # (MAJOR.MINOR.PATCH, bkz. version.py). Dördüncü hane build numarası —
    # sürüm şemasında karşılığı olmadığı için 0.
    _v = tuple(int(p) for p in APP_VERSION.split(".")) + (0,)
    # 0x041F/1200 = Türkçe + Unicode. Uygulama tek dilli olduğu için tek
    # çeviri bloğu var; Explorer eldeki bloğu gösterir.
    _version_resource = _vi.VSVersionInfo(
        ffi=_vi.FixedFileInfo(filevers=_v, prodvers=_v),
        kids=[
            _vi.StringFileInfo([
                _vi.StringTable("041F04B0", [
                    _vi.StringStruct("CompanyName", "Lumeo"),
                    _vi.StringStruct("FileDescription", "Lumeo"),
                    _vi.StringStruct("FileVersion", APP_VERSION),
                    _vi.StringStruct("InternalName", "Lumeo"),
                    _vi.StringStruct("OriginalFilename", "Lumeo.exe"),
                    _vi.StringStruct("ProductName", "Lumeo"),
                    _vi.StringStruct("ProductVersion", APP_VERSION),
                ]),
            ]),
            _vi.VarFileInfo([_vi.VarStruct("Translation", [0x041F, 1200])]),
        ],
    )

# Windows exe'nin simgesi. macOS'ta EXE seviyesindeki icon PyInstaller
# tarafından yok sayılır (asıl .icns BUNDLE'a veriliyor, aşağıda) — burada da
# yalnızca win32'de doldurulur ki gereksiz bir "icon ignored" uyarısı eklenmesin.
_exe_icon = os.path.join(SPECPATH, 'branding', 'lumeo.ico') if sys.platform == "win32" else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Lumeo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # console=False iki platformda da ŞART: desktop.py'nin bütün hata yolu
    # (errlog + sistem uyarısı) "stderr yok, konsol yok" varsayımı üzerine
    # kurulu. True yapmak Windows'ta her açılışta boş bir siyah pencere açar.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    icon=_exe_icon,
    version=_version_resource,  # Windows'ta VERSIONINFO, macOS'ta None
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Lumeo',
)

if sys.platform == "darwin":
    # build.sh, pyinstaller'dan ÖNCE `iconutil` ile branding/lumeo.iconset'ten
    # bu .icns'i üretir (iconutil yalnız macOS'ta var, o yüzden burada
    # commit edilmiş bir dosya değil — bkz. build.sh). Henüz üretilmemişse
    # (ör. spec'i build.sh'siz doğrudan çalıştırmak) sessizce simgesiz derler.
    _icns_path = os.path.join(SPECPATH, 'branding', 'lumeo.icns')
    app = BUNDLE(
        coll,
        name='Lumeo.app',
        icon=_icns_path if os.path.isfile(_icns_path) else None,
        bundle_identifier='org.zenginby.gptimagestudio',
        info_plist={
            'LSMultipleInstancesProhibited': True,   # iki kez çift tıklama ikinci sunucu doğurmaz
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'LSMinimumSystemVersion': '13.0',
        },
    )
