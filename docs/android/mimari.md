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

**Yerelde** `android/wheels/` altında pydantic-core wheel'i olmalı; yoksa Gradle
anlaşılır bir Türkçe hatayla durur (bkz. `android/wheels/README.md`). **CI'da**
gerekmiyor: `build-android.yml`'deki `wheel` işi onu repo → önbellek → derleme
sırasıyla kendisi buluyor.

### APK'yı telefona ulaştırmak

Kullanıcının gördüğü tarafı `KURULUM.md` → *Android (sideload)* anlatıyor.
Bakımcı tarafı iki yol:

**Deneme paketi (yayın oluşmaz).** Actions → *Android APK* → **Run workflow** →
dalı seç. Koşu bitince sayfanın altındaki `gpt-image-studio-android-arm64`
varlığını indir, ZIP'ten çıkan APK'yı telefona at. İlk koşuda wheel de
derlendiği için 30–40 dakika sürebilir; sonraki koşular önbellekten okur.

> **Bu paket ancak imzalıysa kurulabilir.** İmzalama sırları tanımlı değilse
> koşu yine yeşil olur ve varlığı üretir, ama APK **imzasızdır** ve Android onu
> kurmaz — telefonda *"paket geçersiz görünüyor"* der. Koşu sayfasının başındaki
> özet bunu yazıyor; `İmzayı doğrula` adımının atlanmış olması da aynı işaret.
> Aşağıdaki *İmzalama* bölümü tek seferlik kurulumu anlatıyor.

**Yayın.** `v*` biçiminde bir tag at. `release.yml` masaüstü paketlerini,
`build-android.yml` APK'yı üretir ve `publish-android` işi APK'yı aynı yayına
ekler. Kullanıcı doğrudan Releases sayfasından indirir.

> **Elle tetikleme yalnız `main`'de çalışır.** GitHub `workflow_dispatch`'i
> sadece varsayılan dalda bulunan workflow dosyaları için gösteriyor — bu iki
> workflow `main`'e girmeden bir dal üzerinde tetiklenemez (API 404 döner).
> Yani ilk APK, bu çalışma `main`'e merge edildikten sonra alınabilir.

### İmzalama

Anahtar repoya **girmiyor**. CI dört GitHub Secret okuyor:

| Sır | İçerik |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | Keystore dosyasının base64'ü |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore parolası |
| `ANDROID_KEY_ALIAS` | Anahtar takma adı |
| `ANDROID_KEY_PASSWORD` | Anahtar parolası |

Yerelde aynı değerler ortam değişkeni olarak veriliyor
(`ANDROID_KEYSTORE_PATH` + üçü). Tanımlı değilse `build.gradle` `release`
buildType'ına hiçbir `signingConfig` bağlamıyor ve `assembleRelease`
**imzasız** bir paket üretir.

> **İmzasız APK KURULMAZ.** Android imzasız paketi reddeder: telefonda
> *"Uygulama yüklenmedi — paket geçersiz görünüyor"*. Bu bir Xiaomi/MIUI ayarı
> ya da "bilinmeyen kaynaklar" izni sorunu **değil**; izni versen de kurulmaz.
> Dosya adı da yardımcı olmuyor: AGP normalde `app-release-unsigned.apk` derdi,
> ama workflow çıktı adını `…-release.apk` olarak sabitliyor. Tek güvenilir
> işaret koşudaki `İmzayı doğrula` adımı — atlandıysa paket imzasızdır.
> İmzasız derleme yine de bir işe yarıyor: derlemenin ayakta olduğunu gösteriyor
> ve imzalama sırlarına erişimi olmayan bir çatal da koşabiliyor. Tag'de ise CI
> imzasız APK'yı yayına sokmuyor.

Anahtar bir kez üretilir ve **kaybedilmemelidir**: aynı anahtarla imzalanmayan
bir APK, kullanıcının telefonundaki kurulumun üzerine yazamaz — kullanıcı
uygulamayı kaldırmak zorunda kalır ve kaldırma tüm verisini siler. Anahtar repo
dışında, parola yöneticisinde ya da şifreli bir yedekte durmalı.

```bash
keytool -genkeypair -v -keystore gis.keystore -alias gis \
        -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12
```

PKCS12'de **anahtar parolası = depo parolası**; `keytool` ayrı bir anahtar
parolası sormuyor. `ANDROID_KEYSTORE_PASSWORD` ve `ANDROID_KEY_PASSWORD`
sırlarına aynı değer yazılır — farklı yazılırsa Gradle parola hatasıyla düşer.

Sırları tanımladıktan sonra Actions → *Android APK* → **Run workflow**. Bu kez
`İmzayı doğrula` atlanmaz; `apksigner verify --print-certs` sertifikayı basar ve
o adım yeşilse paket telefona kurulur.

## Beklenen boyut ve ilk açılış

- APK: **28 MB** (ölçüldü, run 31969129034 · 482 girdi). İlk tahmin 45–70 MB'ydı;
  fark, Chaquopy'nin stdlib'i ve bağımlılıkları sıkıştırılmış `.imy` arşivleri
  olarak paketlemesinden — cihazdaki açılmış boyut tahmine daha yakın.
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
