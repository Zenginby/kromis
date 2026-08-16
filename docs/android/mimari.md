# Android paketi — mimari ve derleme

Masaüstü sürümü ne yapıyorsa telefonda da aynısı yapılıyor: **cihazda tam
Python**. Uygulama bir uzak sunucuya ya da bilgisayara bağlanmıyor; FastAPI +
uvicorn telefonun içinde koşuyor, arayüz onu `http://127.0.0.1:<port>`
üzerinden kullanıyor. Dış bağımlılık yalnız Azure çağrıları.

## Yığın

```
┌─────────────────────── Android süreci ────────────────────────┐
│  MainActivity  ──WebView──►  http://127.0.0.1:<port>          │
│      │                              ▲                         │
│      │ (port, token)                │ HTTP + oturum çerezi    │
│      ▼                              │                         │
│  PythonServer ──► android_main.start()                        │
│                       │                                       │
│                       ├─ paths.py Android dalını açar         │
│                       ├─ SessionCookieGuard'ı takar           │
│                       └─ desktop.start_server() ──► uvicorn   │
│                                                    └─ app.py  │
│  ServerService (foreground) — süreci ayakta tutar             │
└───────────────────────────────────────────────────────────────┘
```

Python kaynakları **kopyalanmıyor**: `android/app/build.gradle` repo kökünü
doğrudan kaynak dizini gösteriyor (`srcDirs = ["../.."]`, `include "*.py"`).
Tek kaynak korunuyor — masaüstünde düzeltilen bir hata telefonda da düzeliyor.

## Dosya haritası

| Dosya | İşi |
|---|---|
| `android_main.py` | Android girişi: yolları açar, token'ı üretir, uvicorn'u başlatır |
| `paths.py` | Dördüncü dal (Android) — `GIS_ANDROID_DATA_DIR` / `GIS_ANDROID_RESOURCE_DIR` |
| `android/pins.properties` | pydantic / pydantic-core / Python sürümleri — tek kaynak |
| `android/app/build.gradle` | Chaquopy yapılandırması, sürümü `version.py`'den okur |
| `…/StudioApplication.kt` | `Python.start()` — süreç başına bir kez |
| `…/PythonServer.kt` | assets kopyalama + `android_main` köprüsü |
| `…/ServerService.kt` | Foreground service (kalıcı bildirim) |
| `…/MainActivity.kt` | WebView, çerez, dosya seçici, indirme, geri tuşu |
| `…/Downloader.kt` | MediaStore'a indirme (PNG → Resimler, ZIP → İndirilenler) |
| `static/mobile.css` | Mobil yerleşim + dokunmatik kuralları |
| `static/mobile.js` | Composer yüksekliğini ölçer (`--composer-h`) |

## Dört karar ve gerekçeleri

### 1. pydantic-core wheel'ini kendimiz derliyoruz
Chaquopy 17 sdist kurmuyor ve `pydantic-core`'un Android wheel'i hiçbir yerde
yok. Ayrıntı ve reddedilen alternatif: [`pydantic-karari.md`](pydantic-karari.md).

### 2. Yollar ortam değişkeniyle açılıyor, `sys.platform` ile değil
Chaquopy'de `sys.platform` `"linux"` döner — masaüstü Linux geliştirmesinden
ayırt edilemez. `paths.ANDROID_DATA_ENV` açık, test edilebilir ve mevcut üç
dala hiç dokunmuyor. Kotlin dizinleri argüman olarak veriyor; `android_main`
onları `import app`'ten **önce** `os.environ`'a yazıyor — sıra kritik, çünkü
`app.py` yol sabitlerini modül düzeyinde hesaplıyor.

### 3. Sunucu oturum çerezi istiyor
Android'de `127.0.0.1` cihazdaki **her** uygulamaya açık ve `app.py`'de ne CORS
ne kimlik denetimi var — bu sunucu kullanıcının Azure anahtarını tutuyor.
Rastgele bir token WebView'e `HttpOnly` çerez olarak yazılıyor, `android_main`
içindeki ince ASGI katmanı her isteği doğruluyor.

Frontend'e **hiç dokunulmadı**: 27 `fetch` çağrısının hepsi göreli, çerez
kendiliğinden gidiyor. Katman `app.py`'ye değil `android_main`'e takıldığı için
masaüstü ve 1213 testin hiçbiri onu görmüyor.

Doğrulama: cihazdaki başka bir tarayıcıdan `http://127.0.0.1:<port>/api/history`
**403** dönmeli.

### 4. Foreground service zorunlu
`azure_client.READ_TIMEOUT_FIRST = 180 s`; n=4 üretimde toplam
`180 + 3×120 = 540 s`. Kullanıcı üretim sürerken uygulamadan çıkarsa Android
arka plandaki süreci öldürebilir ve **ücretlendirilmiş** bir istek yanıtsız
kalır. Kalıcı bildirim bunun bedeli.

## Derleme

Bu depoda APK **CI'da** derleniyor: `.github/workflows/build-android.yml`.
Yerelde derlemek için Android SDK + JDK 17 gerekiyor.

```bash
cd android
./gradlew -PgisBuildPython=python3.13 :app:assembleRelease
```

Önce `android/wheels/` altında pydantic-core wheel'i olmalı; yoksa Gradle
anlaşılır bir Türkçe hatayla durur (bkz. `android/wheels/README.md`).

### İmzalama

Anahtar repoya **girmiyor**. CI dört GitHub Secret okuyor:

| Sır | İçerik |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | Keystore dosyasının base64'ü |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore parolası |
| `ANDROID_KEY_ALIAS` | Anahtar takma adı |
| `ANDROID_KEY_PASSWORD` | Anahtar parolası |

Yerelde aynı değerler ortam değişkeni olarak veriliyor
(`ANDROID_KEYSTORE_PATH` + üçü). Tanımlı değilse `assembleRelease` **imzasız**
üretir — dal üzerinde derlemenin ayakta olduğunu görmek için yeterli, ama
tag'de CI imzasız APK'yı yayına sokmuyor.

Anahtar bir kez üretilir ve **kaybedilmemelidir**: aynı anahtarla imzalanmayan
bir APK, kullanıcının telefonundaki kurulumun üzerine yazamaz — kullanıcı
uygulamayı kaldırmak zorunda kalır ve kaldırma tüm verisini siler.

```bash
keytool -genkeypair -v -keystore gis.keystore -alias gis \
        -keyalg RSA -keysize 4096 -validity 10000
```

## Beklenen boyut ve ilk açılış

- APK: **~45–70 MB** (Python 3.13 çalışma zamanı + stdlib ~25 MB, Pillow +
  libjpeg/freetype ~8 MB, saf Python bağımlılıklar ~10 MB, `static/` +
  `bundled/` ~1.1 MB, Chaquopy çalışma zamanı).
- Tek ABI (`arm64-v8a`) **şart**: ikinci bir ABI boyutu neredeyse ikiye katlar.
- İlk açılış **2–5 sn**: Chaquopy stdlib'i açıyor, `PythonServer` assets'i
  `filesDir/resources/`'a kopyalıyor. Sonraki açılışlar hızlı; kopyalama
  `APP_VERSION` damgasıyla yalnız güncellemeden sonra tekrarlanıyor.

## Bu ortamda derlenemiyor

Bu depoda çalışan oturum `dl.google.com`'a çıkamıyor (egress politikası, 403),
yani Android SDK indirilemiyor ve APK yerel olarak derlenemiyor. Kod, Gradle
yapılandırması ve workflow burada yazıldı; gerçek derleme GitHub Actions'ta
koşuyor. Faz 5'in (CI) erken kurulmasının sebebi de bu: geri bildirim döngüsü
CI üzerinden işliyor.

## Elle doğrulama listesi

Otomatik testler Python ve arayüz sözleşmelerini tutuyor; aşağıdakiler yalnız
gerçek cihazda ölçülebilir.

| Ne | Nasıl |
|---|---|
| Sunucu ayağa kalkıyor mu | Logcat'te `uvicorn hazır: port=…`, WebView'de arayüz |
| `import pydantic` | CI kapısı yeşil (`build-android.yml`) |
| Uçtan uca üretim | Azure kimliğini gir → görsel üret → galeride gör → logo bindir → indir |
| Dosya yükleme | Referans görsel ekle (`onShowFileChooser`) |
| İndirme | PNG → Resimler/GPT-Image Studio, klasör ZIP → İndirilenler/GPT-Image Studio |
| Güvenlik | Başka bir tarayıcıdan `127.0.0.1:<port>/api/history` → **403** |
| Uzun üretim arka planda | n=4 başlat → uygulamadan çık → 5 dk sonra dön → sonuç kayıpsız |
| Responsive | Gerçek telefonda ve Chrome DevTools 390×844'te yatay kaydırma **olmamalı** |
| APK | `apksigner verify` + gerçek cihaza kurulum |
