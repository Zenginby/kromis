# GPT-Image Studio — macOS uygulaması olarak paketleme (v1.8)

**Tarih:** 2026-07-28
**Durum:** tasarım onaylandı, plana geçiliyor

## Problem

Uygulama ofis çalışanlarıyla paylaşıldı ama **çalıştıramıyorlar**: tek giriş yolu
`./run.sh` ve o kişiler terminal kullanamıyor. Paylaşılan kopya çalıştırılabilse
bile üç yerde kırılırdı:

1. `app.py:37` logo bindirmeyi repo **dışındaki** `~/.config/claude-tools/composite-logo.py`
   dosyasını `python3` ile çağırarak yapıyor — o makinelerde ne dosya ne o yol var.
2. O script'in `DEFAULT_LOGO_BLUE/WHITE` varsayılanları geliştiricinin makinesine **mutlak
   yolla** bağlı (`.../Website/assets/kurumsal-logo-*.png`).
3. `assets/` gitignore'da → logo/motto/banner kütüphanesi boş başlar (v1.5'te not düşüldü).

## Hedef

Çift tıklanan, kendi penceresinde açılan, Python kurulumu gerektirmeyen bir **macOS
uygulaması** (`GPT-Image Studio.app`). Kullanıcı zip'i açar, Applications'a sürükler,
bir kez Gatekeeper uyarısını geçer, dişli ikonundan Azure kimliğini girer ve kullanır.

## Kapsam dışı (bilinçli)

Windows `.exe`, Apple notarization, otomatik güncelleme, universal2, DMG installer.

## ⚠️ Uygulama sırasında ortaya çıkan kısıt: derleme makinesi Intel

Bu spec "hedef makinelerin hepsi Apple Silicon" bilgisinden yola çıkıp derlemenin
geliştirme makinesinde yapılacağını varsaymıştı. **Task 6'da ortaya çıktı ki
geliştirme makinesi Intel'dir** (`uname -m` → `x86_64`; iMac20,2, Core i9-10910;
venv Python `macosx-26.0-x86_64`). PyInstaller çalışan CPython'un kendi C
uzantılarını pakete gömdüğü için **çapraz derleme yapamaz** → Intel'de arm64
paket üretilemez.

**Karar (insan): iki hatlı yaklaşım.**

1. **Yerel x86_64 derlemesi = doğrulama hattı.** Intel'de nativ çalışır, yani
   paketleme yolunun tamamı (pencere, kimlik girişi, üretim, geçmiş kalıcılığı,
   Gatekeeper akışı) geliştirme makinesinde uçtan uca sınanabilir. Bu, arm64
   hattının test edilemezliğini telafi eder.
2. **GitHub Actions arm64 = gönderim hattı.** `macos-14`+ runner'ları arm64'tür;
   ofis makinelerine gidecek paketi orada derleyip artifact olarak indiririz.
   Rosetta diyalogu çıkmaz.

Reddedilen alternatifler: **yalnız x86_64 + Rosetta** (bugün biterdi ama her
makinede bir kerelik yönetici şifreli Rosetta kurulumu ister ve Apple Rosetta'yı
macOS 27 sonrası kısıtlıyor); **yalnız Actions** (nativ ama paketi ne geliştirici
ne asistan test edebilir, ilk çalıştıran ofis çalışanı olur).

## Doğrulanmış ortam

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| Python | 3.14.6 | `.venv/bin/python -V` |
| pywebview | 6.2.1 | temiz venv'e kuruldu + `import webview` başarılı |
| PyInstaller | 6.21.0 | aynı venv'e kuruldu + `import PyInstaller` başarılı |
| pyobjc (Cocoa/WebKit) | 12.2.1 | pywebview bağımlılığı olarak sorunsuz kuruldu |
| Geliştirme makinesi | macOS 26.5.1 | `sw_vers` |
| Kod imzalama kimliği | **yok** (0 identity) | `security find-identity -v -p codesigning` |

## Kararlar

### K1 — Pencere: pywebview + gömülü uvicorn (`desktop.py`)

uvicorn daemon thread'de **port 0** ile başlar (boş portu çekirdek verir), hazır
olması beklenir, sonra native WKWebView penceresi açılır. Pencere kapanınca sunucu
kapatılır ve süreç ölür.

Sabit 8765 portu kalktığı için `run.sh`'teki `lsof` + `kill` + bayat-süreç mantığı
paket yolunda **gereksiz** hale gelir. `Info.plist`'e `LSMultipleInstancesProhibited`
konur → iki kez çift tıklamak ikinci sunucu doğurmaz.

`run.sh` geliştirme için **korunur**; `desktop.py` geliştirmede de çalıştırılabilir
olmalı (frozen olmayan modda mevcut yolları kullanır).

### K2 — `composite-logo.py` repoya port edilir, dışarıdaki kopya SİLİNMEZ

Yeni `composite.py`: dış script'in (148 satır, saf Pillow + argparse) saf fonksiyon
karşılığı — `argparse` yok, `subprocess` yok, geçici dosya yok. `app.py:_composite_logo`
doğrudan bu modülü çağırır.

- **Neden port:** paket içinde `python3` + o dosya yok; Logo ve Banner özellikleri
  aksi halde 500 verir.
- **Neden dışarıdaki kopya kalıyor:** günlük blog routine'i (bkz. Wiki
  `Claude Blog Routines`) onu bağımsız çağırıyor. Silmek onu kırar.
- **Kabul edilen borç:** iki kopya, kayabilir. Repo kopyası uygulamanın kaynağıdır.
  Wiki'ye açıkça not düşülür.
- **Yan fayda:** her önizlemede Python süreci başlatma maliyeti gider; 220 ms
  debounce'lu canlı önizleme hızlanır.

**Kaydırma koruması — golden test:** port yazılmadan ÖNCE mevcut subprocess yolundan
bir opsiyon kombinasyonu kümesi için çıktı PNG'leri üretilir ve fixture olarak
commit edilir. Yeni modülün çıktısı bunlarla **bayt bayt** karşılaştırılır. Kombinasyonlar
en az: 9 konumdan 3'ü × `auto`/`blue`/`white` × iki `scale` × gölge açık/kapalı, artı
`asset_id` ile özel overlay yolu (aynı dosya iki varyant olarak geçen dal).

### K3 — Yazılabilir veri dizini (`paths.py`)

Tek karar noktası `sys.frozen`:

| | Paket içinde (frozen) | Geliştirmede |
|---|---|---|
| `output/`, `history.json`, `folders.json`, `palettes.json` | `~/Library/Application Support/GPT-Image Studio/output/` | `<repo>/output/` (değişmez) |
| `assets/` (kullanıcı kütüphanesi) | `~/Library/Application Support/GPT-Image Studio/assets/` | `<repo>/assets/` (değişmez) |
| `static/` | `sys._MEIPASS/static` (salt-okunur) | `<repo>/static/` |
| `bundled/logos/` | `sys._MEIPASS/bundled/logos` (salt-okunur) | `<repo>/bundled/logos/` |
| kimlik (`credentials.env`) | değişmez — `~/.config/gpt-image-studio/` | aynı |

`dirname(__file__)` frozen modda geçici çıkarma dizinine düşer → geçmiş her kapanışta
silinirdi. Bu yüzden zorunlu.

**Kritik kısıt:** mevcut 581 testin tamamı rotaların `app.OUTPUT_DIR`'ı **çağrı anında**
okumasına dayanıyor. `paths.py` bu davranışı bozmamalı; geliştirme modunda çözülen
yollar bugünküyle birebir aynı olmalı ki testlerin hiçbiri elden geçmesin.

### K4 — kurumsal logolar pakete gömülür ve ilk açılışta tohumlanır

`bundled/logos/kurumsal-logo-{blue,white}.png` repoya **commit edilir** (kaynak:
`.../Website/assets/kurumsal-logo-*.png`, ~300 KB × 2). `assets/` gitignore'da kalır.

İlk açılışta kullanıcı `assets/logos/` boşsa iki logo kopyalanır ve `index.json`'a
yazılır (mevcut `assets_store` deseniyle, atomik). İkinci açılışta **çoğaltmaz**.

Bu aynı zamanda dış script'in mutlak varsayılan yollarına olan bağımlılığı da bitirir:
`composite.py` logo yollarını `paths.py`'den alır.

### K5 — Gatekeeper: ad-hoc imza + tek seferlik "Yine de Aç"

Developer ID sertifikası yok ve alınmayacak ($99/yıl gerekçelendirilmedi). Paket
`codesign --force --deep -s -` ile ad-hoc imzalanır. Kullanıcı ilk açılışta bir kez
Sistem Ayarları → Gizlilik ve Güvenlik → **"Yine de Aç"** yapar. Terminal gerekmez.

macOS 26'da imzasız uygulamalarda sağ tık → Aç yolu güvenilir değil; talimat bu
yüzden Sistem Ayarları üzerinden yazılır.

### K6 — Dağıtım paketi

`build.sh`: PyInstaller `--windowed` (arm64) → ad-hoc imza → zip. Tahmini boyut
60–90 MB (Python, Pillow, pyobjc, uvicorn gömülü).

Yanında ekran görüntülü Türkçe `KURULUM.md`: zip'i aç → Applications'a sürükle →
Gatekeeper adımı → dişli → Azure endpoint + key.

`pywebview` çalışma-zamanı bağımlılığı olduğu için `requirements.txt`'e; `pyinstaller`
yalnız build'de gerektiği için `requirements-dev.txt`'e girer.

### K7 — Kimlik: mevcut v1.2 mekanizması, ek iş yok

Her kullanıcı kendi Azure kimliğini Ayarlar modalından girer; ilk açılışta
"yapılandırılmamış" kilidi modalı zaten otomatik açıyor. Key `mkstemp` + `fchmod 0600`
+ `os.replace` ile yazılır ve ekrana asla dönmez.

**Operasyonel not (kod değil):** herkes aynı Azure kaynağının key'ini kullanacağı için
kullanım tek faturada toplanır ve key rotasyonu herkesi etkiler.

## Mimari — dosya bazında

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `desktop.py` | **yeni** | uvicorn'u thread'de + port 0 ile başlat, hazır olmasını bekle, pywebview penceresi aç, kapanışta kapat |
| `composite.py` | **yeni** | logo/filigran bindirme saf fonksiyonları (dış script'in portu) |
| `paths.py` | **yeni** | frozen/dev yol çözümü + veri dizini oluşturma + ilk açılış logo tohumlaması |
| `app.py` | değişir | `COMPOSITE_SCRIPT`/`subprocess` yerine `composite.py`; `BASE_DIR` türevleri yerine `paths.py` |
| `gpt-image-studio.spec` | **yeni** | PyInstaller yapılandırması (datas: `static/`, `bundled/`; hidden imports) |
| `build.sh` | **yeni** | temizle → pyinstaller → ad-hoc imza → zip |
| `KURULUM.md` | **yeni** | son kullanıcı talimatı (Türkçe, ekran görüntülü) |
| `run.sh` | değişmez | geliştirme yolu korunur |

Her yeni modül tek amaçlı ve I/O'suz test edilebilir sınırda: `composite.py` saf
görüntü matematiği, `paths.py` saf yol çözümü + açıkça ayrılmış bir tohumlama
fonksiyonu, `desktop.py` yalnızca süreç yaşam döngüsü.

## Test

- **Test tabanı 599** (`pytest --collect-only`). Geliştirme modunda yollar birebir aynı
  kaldığı için yol değişikliği hiçbir testi elden geçirmez. **Tek istisna:** 10 test
  logo bindirmeyi `appmod.subprocess.run` mock'layıp komut dizisine assert ediyor
  (`tests/test_logo.py` 7, `tests/test_folders.py` 2, `tests/test_palette_route.py` 1)
  → port sonrası bunlar `composite.composite_logo` kwargs sözleşmesine taşınır.
- `composite.py`: golden fixture karşılaştırmaları (K2), artı konum/ölçek/renk-seçimi
  birim testleri.
- `paths.py`: frozen/dev ayrımı (`sys.frozen` monkeypatch'iyle), dizin oluşturma
  idempotansı.
- Tohumlama: boş kütüphanede iki logo eklenir; ikinci çağrıda çoğaltmaz; kullanıcı
  logoyu sildiyse geri getirmez.
- `desktop.py`: headless test edilmez, **manuel doğrulanır** — pencere açılıyor mu,
  arayüz yükleniyor mu, pencere kapanınca süreç ölüyor mu, iki kez çift tıklamada tek
  örnek mi kalıyor.
- **Paket üzerinde canlı kabul testi:** derlenmiş `.app` temiz bir kullanıcı hesabında
  (veya veri dizini silinmiş halde) açılır; kimlik girilir, görsel üretilir, logo ve
  banner bindirilir, uygulama kapatılıp açıldığında geçmiş **yerinde durur**.

## Riskler

| Risk | Etki | Karşılık |
|---|---|---|
| `uvicorn[standard]` (uvloop/httptools) PyInstaller'da gizli import gerektirir | paket açılışta çöker | `.spec`'e `hiddenimports`; çözülmezse düz asyncio loop'a düş |
| Pillow plugin importları frozen modda bulunmaz | PNG kaydı/okuması patlar | `.spec`'te Pillow hook'u doğrula; kabul testi bunu yakalar |
| Port'un çıktısı dış script'ten kayar | logo çıktısı sessizce değişir | golden fixture'lar (K2) |
| `paths.py` mevcut test varsayımını bozar | 581 testte kırılma | dev modunda yolları birebir koru; refactor'dan sonra tüm suite çalıştırılır |
| İki `composite` kopyası zamanla ayrışır | blog routine'i ile app farklı çıktı verir | Wiki'ye borç notu; ileride dış script'in repo modülünü çağırması |

## Sonraya bırakılan

- Dış script'in repo modülünü import eden ince bir sarmalayıcıya indirilmesi (tek
  kaynak).
- `app.py` **765 satır** (Wiki'deki "921 satır" notu `04dab75` refactor'ından sonra
  stale). Stil sınırı 800 → bu iş dosyayı büyütmemeli; `_composite_logo` süreç içine
  taşınınca subprocess/tempfile bloğu düştüğü için hafif azalmalı.
