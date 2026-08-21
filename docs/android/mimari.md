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
| `…/MainActivity.kt` | WebView, çerez, dosya seçici, indirme köprüsü, geri tuşu |
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

### 4. İndirme JS köprüsünden geçiyor, `<a download>`'dan değil
Android WebView'in **indirme sistemi yok**: bir indirmeyi tanır tanımaz iptal
edip olayı uygulamaya devrediyor (`AwDownloadManagerDelegate` →
`DownloadListener`). Üstelik `<a download>` tıklaması orada bir gezinme değil,
"renderer kaynaklı indirme". Zincirin herhangi bir halkası koptuğunda hiçbir
hata çıkmıyor — tıklama **sessizce hiçbir şey yapmıyor**. Telefonda "indirme
çalışmıyor"un tarifi tam olarak bu ve tek bir `Content-Disposition` başlığı onu
kapatmıyor.

Bu yüzden `MainActivity` sayfaya `LumeoIndirme` adında bir arayüz enjekte
ediyor (`addJavascriptInterface`, `loadUrl`'den **önce**) ve `core.js`
`downloadViaAnchor` köprü varsa doğrudan onu çağırıyor. Zincirden çıkanlar:
WebView'in indirme devralması, `<a download>`, ve `URLUtil.guessFileName` —
dosya adını artık **adı zaten bilen** taraf, frontend veriyor. Klasör
ZIP'lerinin telefona `download.zip` diye inmesinin sebebi o tahmin regex'iydi.

Köprü yoksa (tarayıcı, masaüstü paketi) hiçbir şey değişmiyor: eski
`<a download>` yolu duruyor. `DownloadListener` de duruyor, ama artık yalnız
**bizim başlatmadığımız** indirmeler için (uzun basıp "bağlantıyı kaydet").

Yüzeyin bedeli ödendi: `addJavascriptInterface` nesneyi WebView'deki her sayfaya
açıyor, o yüzden köprü tek çağrı ve adresi **kendi sunucumuza** çiviliyor (host
+ port). Dosya adı da `Downloader.guvenliAd`den geçiyor — klasör ZIP'inde o ad
kullanıcı metni. Mandalları: `tests/test_mobile.py`.

### 5. Foreground service zorunlu
`azure_client.READ_TIMEOUT_FIRST = 180 s`; n=4 üretimde toplam
`180 + 3×120 = 540 s`. Kullanıcı üretim sürerken uygulamadan çıkarsa Android
arka plandaki süreci öldürebilir ve **ücretlendirilmiş** bir istek yanıtsız
kalır. Kalıcı bildirim bunun bedeli.

## Derleme

Bu depoda APK **CI'da** derleniyor: `.github/workflows/_paket-android.yml`
(çağıranlar: PR'da `ci.yml`, yayında `release.yml`).
Yerelde derlemek için Android SDK + JDK 17 gerekiyor.

```bash
cd android
./gradlew -PgisBuildPython=python3.13 :app:assembleRelease
```

**Yerelde** `android/wheels/` altında pydantic-core wheel'i olmalı; yoksa Gradle
anlaşılır bir Türkçe hatayla durur (bkz. `android/wheels/README.md`). **CI'da**
gerekmiyor: `_paket-android.yml`'in `wheel` işi
(`build-pydantic-core-android.yml`) onu repo → önbellek → derleme sırasıyla
kendisi buluyor.

### APK'yı telefona ulaştırmak

Kullanıcının gördüğü tarafı `KURULUM.md` → *Android (sideload)* anlatıyor.
Bakımcı tarafı iki yol:

**Deneme paketi (yayın oluşmaz).** Actions → *Yayın* → **Run workflow**; dalı
seç, `surum` alanına bir sonraki sürümü yaz, `kuru_prova`yı işaretle. Dal
kapısı sürüm commit'ini ve yayını engelliyor (`release.yml` → DAL KAPISI), ama
Android işi tam olarak koşuyor. Koşu bitince `lumeo-android-arm64` varlığını
indir, ZIP'ten çıkan APK'yı telefona at. `android/` altına dokunan bir PR'da
aynı iş kendiliğinden koşuyor (`docs/yayin-hatti.md` → "PR'da ne koşuyor") —
orada ayrıca tetiklemek gerekmiyor. Wheel önbellekte olduğu sürece koşu
~2 dakika; önbellek boşsa wheel derlemesi 30–40 dakika sürebilir.

> **Bu paket ancak imzalıysa kurulabilir.** İmzalama sırları tanımlı değilse
> koşu yine yeşil olur ve varlığı üretir, ama APK **imzasızdır** ve Android onu
> kurmaz — telefonda *"paket geçersiz görünüyor"* der. Koşu sayfasının başındaki
> özet bunu yazıyor; `İmzayı doğrula` adımının atlanmış olması da aynı işaret.
> Aşağıdaki *İmzalama* bölümü tek seferlik kurulumu anlatıyor.

**Yayın.** Tag atmak gerekmiyor: `main`'e her merge `release.yml`'i çalıştırıyor,
sürüm kararını `tools/surum_karari.py` veriyor ve APK üç paketle birlikte tek
yayına giriyor (`docs/yayin-hatti.md`). Kullanıcı doğrudan Releases sayfasından
indiriyor.

> **Dalda tetiklemek çalışıyor.** GitHub `workflow_dispatch`'i yalnız
> varsayılan dalda **bulunan** workflow dosyaları için gösteriyor; `release.yml`
> `main`'de olduğu için herhangi bir dal seçilerek koşturulabiliyor ve koşu o
> dalın içeriğini derliyor. Ölçüldü: koşu 32478330228, dal
> `claude/gis-keystore-mobile-app-mgakyw`. (`main`'de HİÇ bulunmayan bir
> workflow dalda tetiklenemez — API 404 döner.)

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

Sırları tanımladıktan sonra yukarıdaki *deneme paketi* koşusunu tetikle. Bu kez
`İmzayı doğrula` atlanmaz; `apksigner verify --print-certs` sertifikayı basar ve
o adım yeşilse paket telefona kurulur.

#### Yayındaki anahtarın kimliği

`apksigner verify --print-certs` ile ölçüldü (koşu 32478330228, 2026-08-21):

| Alan | Değer |
|---|---|
| Sertifika DN | `CN=GPT-Image Studio, OU=Unknown, O=Unknown, L=İstanbul, ST=Unknown, C=Unknown` |
| Sertifika SHA-256 | `b24743de4456ad092563678aea48cdb13d05ff848746bef534be1eeb7cf7768b` |
| Sertifika SHA-1 | `c2a4349e1b096b8d9ec422e0df0a7dfc6fdf57b0` |
| Anahtar | RSA 4096 |
| İmza şeması | yalnız v2 (APK Signature Scheme v2) |

Bu parmak izleri **sır değil**: imzalı her APK'nın içinden okunabiliyorlar.
Burada durmalarının sebebi, bir sonraki imzalı derlemenin AYNI anahtarla
imzalandığını kanıtlayacak referans olmaları. Parmak izi değiştiyse anahtar da
değişmiştir ve o paket telefondaki kurulumun üzerine yazamaz — kullanıcı
uygulamayı kaldırmak zorunda kalır.

#### Depo başka bir hesaba taşındığında

Sırlar depo **ayarlarında** yaşıyor, git ağacında değil: `git clone` onları
getirmiyor, depoya bakarak varlıkları anlaşılmıyor. Hesap değişikliğinden sonra
ilk soru her zaman "dört sır hâlâ orada mı" oluyor.

Ölçüldü: depo `Zenginby`'dan `Zenginby`'ye taşındıktan sonra (2026-08-21,
koşu 32478330228) dördü de yerindeydi — GitHub taşımada depo sırlarını
düşürmedi ve APK yukarıdaki parmak iziyle imzalandı. Yine de her taşımadan
sonra ölçülmeli; tek güvenilir işaret `İmzayı doğrula` adımının ATLANMAMIŞ
olması.

Sürüm harcamadan ölçmek: Actions → *Yayın* → *Run workflow*; dal olarak bir
çalışma dalı, `surum` alanına bir sonraki sürüm, `kuru_prova` işaretli
(ayrıntı: `docs/yayin-hatti.md` → "Yeni bir kapıyı sürüm harcamadan denemek").

`surum` alanını **boş bırakmak bu ölçümü yapmıyor**: `karar` işi "pakete
girmiyor" deyip bütün paket işlerini atlıyor, koşu yeşil biter ve imza hakkında
hiçbir şey söylemez. Ölçüldü — koşu 32478178747 tam olarak böyle bitti.

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
| `import pydantic` | CI kapısı yeşil (`_paket-android.yml` → *pydantic APK'ya girdi mi*) |
| Uçtan uca üretim | Azure kimliğini gir → görsel üret → galeride gör → logo bindir → indir |
| Dosya yükleme | Referans görsel ekle (`onShowFileChooser`) |
| İndirme | PNG → `Resimler/Lumeo`, klasör ZIP → `İndirilenler/Lumeo`; ZIP adı klasörün ADI olmalı (`download.zip` değil) |
| Güvenlik | Başka bir tarayıcıdan `127.0.0.1:<port>/api/history` → **403** |
| Uzun üretim arka planda | n=4 başlat → uygulamadan çık → 5 dk sonra dön → sonuç kayıpsız |
| Responsive | Gerçek telefonda ve Chrome DevTools 390×844'te yatay kaydırma **olmamalı** |
| APK | `apksigner verify` + gerçek cihaza kurulum |
