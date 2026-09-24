# Kromis Studio — Kurulum (macOS, Windows ve Android)

Bilgisayarına Python veya başka bir şey kurman gerekmiyor. 5 dakika sürer.

**Hangi bölümü okuyacaksın:** 1., 2. ve 5. adımların işletim sistemine göre iki
dalı var — kendi dalını oku, ötekini atla. 3. ve 4. adımlar (Azure kimliği,
Prompt Yönetmeni) iki sistemde aynıdır.

| Sistem | Dosya |
|---|---|
| macOS (Apple Silicon) | `kromis-macOS-arm64.zip` |
| Windows 10/11 (64-bit) | `kromis-windows-x64.zip` |
| Android 8.0+ (arm64) | `kromis-android-arm64.apk` |

**Sunucuya (web) kuruyorsan** bu adımların hiçbiri sana değil:
[Web sürümü](#web-sürümü-sunucu-kurulumu) bölümüne git.

**Telefona kuruyorsan** aşağıdaki 1. ve 2. adımları atla, doğrudan
[Android (sideload)](#android-sideload) bölümüne git — 3., 4. ve 5. adımlar
(Azure kimliği, Prompt Yönetmeni, kullanım) üç sistemde de aynıdır.

Not: Bu belge, sana ulaşan `.zip`'in kendi sistemin için ayrıca (GitHub
Actions'ın arm64 / windows runner'ında) üretildiğini varsayar — geliştirme
makinesinde yerel olarak alınan derlemeler yalnızca paketleme yolunu sınamak
için, sana gönderilen paket değildir.

## Önce: dosya gerçekten buradan mı geldi?

Kromis'in paketleri **imzasız** dağıtılıyor (macOS noter onayı ve Windows
Authenticode sertifikası yıllık ücretli; 2. adımdaki Gatekeeper/SmartScreen
uyarıları da bu yüzden çıkıyor). İmza olmayınca "bu dosya bozulmamış ve
gerçekten Kromis'in yayınından geldi" diyebilmenin yolu **SHA-256 özeti**.

Bunu yapmanı gerektiren tek durum var ama önemli: paketi
[resmî yayın sayfası](https://github.com/Zenginby/kromis/releases/latest)
dışında bir yerden indirdiysen — bir blog, bir dosya paylaşım sitesi, bir
arkadaşının gönderdiği kopya. Uygulama senin API anahtarlarını tutuyor;
değiştirilmiş bir kopya onları dışarı taşıyabilir.

**Her yayının notlarında üç paketin özeti yazılı** (ayrıca `SHA256SUMS.txt`
olarak da ekli). İndirdiğin dosyanınkini hesapla ve karşılaştır:

```sh
# macOS
shasum -a 256 ~/Downloads/kromis-macOS-arm64.zip

# Android (bilgisayarda, APK'yı telefona atmadan önce)
shasum -a 256 ~/Downloads/kromis-android-arm64.apk
```

```powershell
# Windows — PowerShell
Get-FileHash $HOME\Downloads\kromis-windows-x64.zip -Algorithm SHA256
```

Çıkan 64 karakterlik değer yayın sayfasındakiyle **birebir aynıysa** dosya
doğrudur; devam et. **Tutmuyorsa kurma** — dosyayı sil ve resmî yayın
sayfasından yeniden indir.

> [!NOTE]
> Özetler yayının kendi sayfasında duruyor, yani onları sahte paketi dağıtan
> kişi değiştiremez. Karşılaştırmayı her zaman yukarıdaki resmî bağlantıdan
> açtığın sayfayla yap; paketi aldığın yerde yazan bir özetle değil.
>
> "Kromis" adı ve logosu lisansın kapsamı dışında ([MARKA.md](MARKA.md)):
> Kromis adıyla dağıtılan resmî olmayan bir paket zaten kural dışıdır.

## 1. Uygulamayı yerine koy

### macOS
1. İndirdiğin `kromis-macOS-arm64.zip` dosyasına çift tıkla — yanında
   `Kromis` uygulaması çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.

### Windows
1. İndirdiğin zip dosyasına **sağ tıkla → Özellikler** (Properties). Pencerenin
   en altında *"Bu dosya başka bir bilgisayardan geldi…"* satırı ve yanında
   **Engellemeyi Kaldır** (Unblock) kutusu varsa **işaretle → Uygula → Tamam**.
   Kutu yoksa yapacak bir şey yok, 2. adıma geç.

   > **Bunu AYIKLAMADAN ÖNCE yap.** Windows internetten indirilen dosyaları
   > işaretliyor; zip'i önce ayıklarsan bu işaret içinden çıkan **her dosyaya**
   > kopyalanıyor ve uygulama açılmayabiliyor. Zip'i önce serbest bırakırsan
   > işaret hiç yayılmaz. Sonradan yüzlerce dosyayı tek tek temizlemek yerine
   > en kolayı zip'i bu adımdan başlayarak yeniden ayıklamaktır.
2. Zip dosyasına sağ tıkla → **Tümünü ayıkla** (Extract All).
3. Çıkan `Kromis` klasörünü kalıcı bir yere taşı — ör.
   `C:\Users\<kullanıcı adın>\Programlar\Kromis`.
   **Klasörü olduğu gibi taşı, içinden yalnız `.exe`'yi çekip almaya çalışma:**
   uygulama yanındaki `_internal` klasörüne ihtiyaç duyar, `.exe` tek başına
   çalışmaz.
4. Uygulamayı `Kromis.exe` ile açarsın. İstersen ona sağ tıklayıp
   **Başlat'a sabitle** / **Kısayol oluştur** diyebilirsin.

> **Zip'i doğrudan içinden çalıştırma.** Windows zip'in içeriğini geçici bir
> klasöre açar; uygulama oradan açılırsa ürettiğin görseller kaybolabilir.
> Önce ayıkla, sonra çalıştır.

## 2. İlk açılış — bir kerelik güvenlik izni

### macOS
Uygulama Apple'a ücretli geliştirici kaydıyla imzalanmadığı için (ad-hoc imza —
bkz. altta), macOS ilk açılışta soru soruyor. Bir kez izin verirsin, sonraki
açılışlarda sormaz. *Not:* Bu zip Apple Silicon Mac'in için derlendiğinden (arm64
native), Rosetta çevirisi yapılmaz.

1. Uygulamaya çift tıkla. Uygulama **açılmayacak** ve şu uyarı çıkacak:

   > **"Kromis" Not Opened**
   > Apple could not verify "Kromis" is free of malware that may harm
   > your Mac or compromise your privacy.
   >
   > *(Türkçe sistemde aynı uyarı "…Açılmadı / Apple … doğrulayamadı" biçiminde
   > çıkar.)*

   ### ⚠️ Burada dikkat — yanlış düğme uygulamayı siler

   Uyarıdaki iki düğmeden **"Move to Trash" (Çöp Sepetine Taşı) MAVİ olan**,
   yani macOS'un **varsayılan** düğmesi. Bu da şu demek: **Enter'a basmak
   uygulamayı siler.**

   - ❌ **"Move to Trash"e BASMA. Enter'a da BASMA.**
   - ✅ Alttaki **"Done" (Bitti)** düğmesine bas.

   Bu uyarı normaldir ve bir sorun olduğunu göstermez: uygulama Apple'a ücretli
   geliştirici kaydıyla imzalanmadığı için macOS onu tanımıyor. İmza geçerli,
   yalnızca Apple onayı (notarization) yok.
2. Ekranın sol üstündeki **Apple menüsü** → **Sistem Ayarları** (System Settings)
   → **Gizlilik ve Güvenlik** (Privacy & Security).
3. Sayfayı aşağı kaydır: *"Kromis engellendi"* / *"was blocked"* satırını
   bul → **Yine de Aç** (**Open Anyway**).
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir (ya da Touch ID).
5. Uygulama açılır. Bir daha sormaz.

<!-- Adım 1-5, 2026-07-29'da İKİ makinede uçtan uca gözle doğrulandı: (a) Intel,
zip'ten çıkarılmış temiz kopya + elle quarantine bayrağı (flags=0001);
(b) Apple Silicon (Mac mini), AirDrop ile gelen gerçek arm64 paketi. İkisinde de
sistem dili İngilizce'ydi, uyarı metni yukarıdaki gibiydi ve "Open Anyway"
sonrası uygulama açıldı, ikinci açılışta sormadı.
"Move to Trash"in MAVİ/varsayılan düğme olduğu (yani Enter'ın uygulamayı sildiği)
ekran görüntüsüyle teyit edildi — adım 1'deki uyarı bu yüzden var.
TODO(insan): Türkçe sistemdeki birebir metin (henüz Türkçe bir macOS'te
denenmedi) ve adımların ekran görüntüleri. -->

### Windows — SmartScreen uyarısı
Uygulama ücretli bir kod imzalama sertifikasıyla imzalanmadığı için Windows
**SmartScreen** ilk açılışta araya giriyor. Bir kez izin verirsin, sonraki
açılışlarda sormaz.

1. `Kromis.exe`'ye çift tıkla. Uygulama **açılmayacak** ve mavi bir
   pencere çıkacak:

   > **Windows bilgisayarınızı korudu**
   > Microsoft Defender SmartScreen tanınmayan bir uygulamanın başlatılmasını
   > engelledi. Bu uygulamayı çalıştırmak bilgisayarınızı riske atabilir.
   >
   > *(İngilizce sistemde: "Windows protected your PC".)*

2. **Daha fazla bilgi** (More info) yazısına tıkla — pencere genişler,
   "Yayımcı: Bilinmiyor" satırı ve yeni bir düğme çıkar.
3. **Yine de çalıştır** (Run anyway) düğmesine bas. Uygulama açılır ve bir daha
   sormaz.

   #### ✅ Burada YIKICI bir düğme YOK
   macOS'taki uyarının aksine (yukarıda: orada varsayılan düğme uygulamayı
   **siler**), SmartScreen penceresindeki düğmelerin hiçbiri dosyayı silmez,
   taşımaz veya karantinaya almaz:

   - **Çalıştırma** (Don't run) → yalnızca pencereyi kapatır. Uygulama yerinde
     kalır, tekrar çift tıklayıp baştan başlayabilirsin.
   - **Enter'a basmak** da güvenli — en kötüsü açılışı iptal eder.
   - Tek yapman gereken **Daha fazla bilgi** → **Yine de çalıştır**.

   Bu uyarı normaldir ve bir sorun olduğunu göstermez: uygulama henüz yeterince
   yaygın indirilmediği ve ücretli sertifikayla imzalanmadığı için SmartScreen
   onu "tanınmayan" sayıyor.

<!-- TODO(insan): Windows adımları 2026-08-13'te Faz 4'te paketlenmiş uygulamayla
doğrulandı, ANCAK SmartScreen penceresi bu makinede tetiklenmedi (dosya
internetten indirilmediği için Mark-of-the-Web bayrağı yok). Yukarıdaki metin
Microsoft'un standart uyarı metnine dayanıyor; gerçekten indirilen bir zip'le
birebir metin + ekran görüntüsü hâlâ alınmalı.

     O EKSİK DOĞRULAMANIN BEDELİ 2026-09-04'te ödendi: yerelde derlenen pakette
     olmayan Mark-of-the-Web, indirilen pakette VARDI ve .NET köprüsü (pythonnet)
     yüklenemeyince uygulama hiç açılmadı — 1. adımdaki "Engellemeyi Kaldır"
     maddesi o kusurdan doğdu. CI artık paketi hem işaretli hem işaretsiz
     ortamda açarak sınıyor (`_paket-windows.yml` → "Açılış denetimi"), yani bu
     sınıf bir daha elle doğrulamaya bağlı kalmıyor. -->

## 3. Azure kimliğini gir
İlk açılışta Ayarlar penceresi kendiliğinden açılır ve "Üret" düğmesi kilitlidir.
1. **Endpoint** ve **API key** alanlarını kendi Azure kaynağından aldığın
   bilgilerle doldur (Azure portalı → kaynağın → *Keys and Endpoint*).
2. **Kaydet**. Kilit açılır.

Key bilgisayarında yalnız senin okuyabileceğin izinle saklanır ve bir daha
ekranda gösterilmez. Dosyanın yeri iki sistemde de aynı mantıkta:

| Sistem | Dosya |
|---|---|
| macOS | `~/.config/kromis/credentials.env` (izin `0600`) |
| Windows | `C:\Users\<kullanıcı adın>\.config\kromis\credentials.env` |

Windows'ta POSIX izin bitleri işlemediği için dosyaya erişim listesi (DACL)
sıkılaştırılıyor: kalıtım kesilir ve listede **yalnız senin hesabın** kalır.
Kendin görmek istersen:

```powershell
icacls "$env:USERPROFILE\.config\kromis\credentials.env"
```

## 4. Prompt Yönetmeni'ni aç (istersen)
Yönetmen üç sağlayıcı ile konuşabiliyor; hangisini kullandığına göre yapılacak
şey değişiyor.

**Azure kullanacaksan:** Ayarlar penceresinde sağlayıcı **Azure OpenAI** seçili
dururken, **Prompt Yönetmeni (sohbet modeli)** başlığının altındaki
**Dağıtım adı** alanına Azure'da oluşturduğun dağıtımın adını yaz
(ör. `gpt-5.6-luna`) →
**Kaydet**. Bu, Azure AI Foundry'deki **deployment** adıdır; model ailesi adı
değil. Sohbet, görselinkiyle aynı endpoint ve API anahtarını kullanır — ikinci
bir anahtar girmen gerekmez.

**OpenAI ya da Gemini kullanacaksan:** girilecek bir dağıtım adı yok (o alan
zaten görünmüyor). Sağlayıcının API anahtarını kaydetmen yeterli; model adı
uygulamanın içinde yazılı.

Sohbet modelini composer'ın üstündeki şeritten seçiyorsun ve şerit
**anahtarı kayıtlı olan** modelleri gösteriyor. Hiçbir sohbet sağlayıcısı
yapılandırılmamışsa "Prompt Yönetmeni" sekmesi yine açılır ama **Gönder**
kilitli kalır ve nedenini panelde yazar.

## 5. Kullan
Prompt yaz → **Üret**. Ürettiğin görseller bilgisayarında saklanır; uygulamayı
kapatıp açsan da geçmişin durur.

| Sistem | Görsellerin yeri |
|---|---|
| macOS | `~/Library/Application Support/Kromis/output/` |
| Windows | `%LOCALAPPDATA%\Kromis\output\` — yani `C:\Users\<kullanıcı adın>\AppData\Local\Kromis\output\` |
| Android | Uygulamanın kendi özel klasörü (dosya yöneticisinden görünmez). Telefona indirdiklerin ise `Resimler/Kromis/` altında. |

Windows'ta klasörü hızlı açmak için Dosya Gezgini'nin adres çubuğuna
`%LOCALAPPDATA%\Kromis` yazıp Enter'a basabilirsin. (Bu klasör
bilerek `AppData\Local` altında — `Roaming` olsaydı ürettiğin bütün görseller
kurumsal profille birlikte ağ üzerinden taşınmaya çalışırdı.)

Hangi sürümü kullandığını **Ayarlar** penceresinin altındaki **Sürüm**
satırından görebilirsin.

---

## Android (sideload)

Android sürümü **Play Store'da değil**: APK'yı doğrudan kuruyorsun. Uygulama
telefonda tam olarak çalışıyor — üretim, düzenleme, palet ve logo bindirme
işlemlerinin hepsi telefonun kendi içinde koşuyor. Bilgisayarına ya da ayrı bir
sunucuya bağlanmıyor; internet yalnızca Azure çağrıları için gerekli.

**Gereken:** Android 8.0 veya üstü, 64-bit (arm64) telefon — 2017 sonrası
neredeyse her telefon. Yaklaşık **300 MB** boş alan (APK **28 MB**; kurulumdan
sonra Python çalışma zamanı açılıyor ve ürettiğin görseller de telefonda
duruyor — pay bunun için).

### A1. APK'yı indir
Telefonun tarayıcısından `kromis-android-arm64.apk` dosyasını indir.
Tarayıcı *"Bu dosya türü cihazına zarar verebilir"* diye sorabilir → **Yine de
indir**. (Bu uyarı her APK için çıkar, dosyayla ilgili bir şey söylemiyor.)

### A2. Bilinmeyen kaynaklara izin ver — bir kerelik
İndirilen dosyaya dokun. Android *"Bu kaynaktan uygulama yüklenemiyor"* diyecek.

1. Çıkan uyarıda **Ayarlar**'a dokun.
2. **Bu kaynaktan yükle** (ya da "Bilinmeyen uygulamalara izin ver") anahtarını aç.
3. Geri dön ve **Yükle**'ye dokun.

> İzin, dosyayı indirdiğin uygulamaya (Chrome, Dosyalar…) veriliyor — telefonun
> tamamına değil. Kurulum bitince istersen aynı yerden kapatabilirsin.

Google Play Protect *"Bilinmeyen bir uygulama gönderildi"* diye sorarsa
**Yine de yükle** de. Paket bizim kendi anahtarımızla imzalı; Play Protect
yalnızca Play Store dışından geldiğini söylüyor.

### A3. İlk açılış — biraz bekle
İlk açılışta ekranda **"Başlatılıyor…"** yazar ve **2–5 saniye** sürer:
uygulama Python çalışma zamanını telefonun içine açıyor. Bu yalnız ilk açılışta
(ve her güncellemeden sonra bir kez) olur; sonraki açılışlar hızlıdır.

Uygulama açılınca kalıcı bir bildirim görürsün: *"Kromis Studio çalışıyor"*.
Bu bildirim **gerekli, kapatma**: sayesinde uzun süren bir üretim sırasında
uygulamadan çıksan bile Android işlemi öldürmez ve ücretli istek boşa gitmez.

Android 13+ ise bildirim izni sorulur → **İzin ver**. Vermezsen uygulama yine
çalışır, yalnız bildirim görünmez.

### A4. Sonra
3. adımdan (Azure kimliğini gir) devam et — arayüz telefonda da aynı.

Telefona özgü iki fark:

- **Enter satır atlar, göndermez.** Prompt'u yazdıktan sonra **Üret** düğmesine
  dokun. (Masaüstünde Enter gönderir; telefonda öyle olsaydı çok satırlı bir
  prompt hiç yazılamazdı.)
- **Görselleri klasöre taşımak için "Seç" → "Taşı…"** kullan. Masaüstündeki
  sürükle-bırak dokunmatik ekranda çalışmıyor.

### A5. İndirdiklerin nereye gidiyor
- Görseller (PNG): **Resimler → Kromis**
- Klasör ZIP'leri: **İndirilenler → Kromis**

### Android'de sorun çıkarsa
- **"Uygulama yüklenmedi" / "Paket geçersiz":** dosya yarım inmiş olabilir —
  APK'yı sil ve yeniden indir.
- **"Uygulamanız bu cihazla uyumlu değil":** telefon 32-bit ya da Android 8'in
  altında. Bu pakete uygun değil, teknik desteğe yaz.
- **Ekranda sürekli "Başlatılıyor…" yazıyor:** uygulamayı tamamen kapat
  (son uygulamalardan kaydır) ve yeniden aç. Sürerse teknik desteğe yaz.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi? (3. adım)
- **İndirdiğim görseli galeride bulamıyorum:** Galeri uygulaması yeni klasörü
  görmek için biraz gecikebilir; Dosyalar uygulamasından
  `Resimler/Kromis` klasörüne bak.

---

## Web sürümü (sunucu kurulumu)

Masaüstü/Android paketiyle ilgisi yok: bu bölüm uygulamayı bir sunucuda,
çok kullanıcılı web olarak açan kişi için. Geliştirici ayrıntıları
[README → Geliştirici rehberi](README.md#-geliştirici-rehberi).

1. **PostgreSQL** ve üç ortam değişkeni (`.env.example` her birini açıklıyor):
   `DATABASE_URL` (`postgresql+psycopg://kullanici:parola@konak:5432/kromis`),
   `KROMIS_SECRET_KEY` (sağlayıcı anahtarlarını şifreleyen kök; `.env.example`
   1c bölümündeki komutla üret, **DB yedeğinden AYRI** sakla — kaybolursa
   kayıtlı anahtarlar okunamaz) ve `KROMIS_DATA_DIR` (medya dosyalarının
   kökü; konteynerde `/data`).

   **Uygulama rolü (RLS, Faz 2 / 7):** `DATABASE_URL`deki rol **süper
   kullanıcı ya da `BYPASSRLS` OLMAMALI** — ikisi de satır düzeyi güvenliği
   atlar ve kiracı yalıtımının ikinci katı sessizce kapanır (tablonun SAHİBİ
   olması sorun değil: göç `FORCE ROW LEVEL SECURITY` koyuyor). Yönetilen
   servislerin kutudan verdiği rol sağlayıcıya göre değişir ve bazıları süper
   kullanıcı ya da `BYPASSRLS` rol verir — Railway'inki ölçüldü (2026-09-18):
   `postgres` rolü İKİSİNİ DE taşıyor, orada ayrı rol zorunlu. Sağlayıcı ne
   verirse versin varsayma, bir kez sor:

   ```sh
   DATABASE_URL=… python tools/rls_kontrol.py --kullanici <bir hesabin uuid'si>
   ```

   Altı kapıyı birden koşar (rol nitelikleri, `SET ROLE` ile ulaşılabilen
   atlayıcı rol, sekiz tabloda `ENABLE`+`FORCE`, 24 politika, bağlamsız 0,
   bağlamlı n); çıkış 0 = rol temiz. `psql` varsa aynı iki soruyu elle de
   sorabilirsin:

   ```sh
   psql "${DATABASE_URL/+psycopg/}" -c "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
   psql "${DATABASE_URL/+psycopg/}" -c "SELECT count(*) FROM medya"   # bağlamsız: 0 olmalı
   ```

   İkisi de `f` ve sayım 0 ise rol doğru. Dikkat: `medya` BOŞKEN o 0 hiçbir
   şey kanıtlamaz (ölçüldü) — taze bir DB'de önce bir satır yaz (aşağıdaki
   `--tohum`), sonra say. Kırmızıysa ayrı bir rol aç ve uygulamaya onu ver
   (göç sahip rolüyle koşmaya devam eder):

   ```sh
   DATABASE_URL=… KROMIS_ROL_PAROLA=… python tools/uygulama_rolu.py --tohum
   ```

   Rolü açar, `GRANT`ları ve `ALTER DEFAULT PRIVILEGES`i (sonraki göçlerin
   tabloları da yeni role açık doğsun diye) verir, yeni rolün de RLS'i
   atlamadığını doğrular ve uygulamaya yazacağın `DATABASE_URL`i basar;
   `--kuru` hiçbir şey yazmadan koşacağı DDL'i gösterir, `--tohum` yalnız
   `medya` boşsa tek bir satır yazar. Sonra kontrolü YENİ dizeyle tekrar
   koştur. Neden ve ne ölçüldüğü: docs/faz2-kuyruk-anahtarlar-depolama.md §7.
2. **Şema — dağıtım ÖNCESİ komut, konteyner açılışı DEĞİL:**

   ```sh
   DATABASE_URL=… python tools/goc.py
   ```

   `alembic upgrade head`in sarmalayıcısı; sonda `mevcut 0003_… (head)` basar,
   head'teyse "zaten head'te" der (0 ile çıkar, her dağıtımda koşturulur).
   Uygulama konteyneri göç koşturmaz — iki replika aynı anda açılırsa iki göç
   yarışır. Bu yüzden komutu platformun **dağıtım öncesi komutuna** yaz, yeni
   sürüm ancak o 0 verirse açılır: Fly.io `fly.toml` → `[deploy]`
   `release_command = "python tools/goc.py"`; Railway → *Pre-deploy command*;
   Render → *Pre-Deploy Command*. Yerel `docker compose up` bunu kendi yapar:
   `goc` servisi göçü koşturup biter, `kromis` onu bekler
   (`service_completed_successfully`). Yedek, anahtar ve geri yükleme düzeni
   ayrı belgede: [docs/isletme.md](docs/isletme.md).
3. **İlk kullanıcı** — kayıt → e-posta doğrulama akışı posta servisi ister;
   ilk hesap onsuz açılır ve DOĞRULANMIŞ yazılır:

   ```sh
   DATABASE_URL=… python tools/kullanici.py olustur --eposta sen@ornek.com --admin
   ```

   Parola ekranda iki kez sorulur, argümanla verilmez (kabuk geçmişine
   düşerdi). `--dil tr` hesabın dilini yazar; `--admin` yalnız bir bayrak
   (bugün admin arayüzü yok). Çerezinin sızdığından şüphelenirsen
   `python tools/kullanici.py oturum-dusur --eposta sen@ornek.com` o hesabın
   bütün oturumlarını düşürür.
4. **Eski verini taşı** (masaüstü/Android'de ürettiğin geçmiş, klasörler,
   oturumlar, paletler, logo/afiş kütüphanesi, tercihler ve sağlayıcı
   anahtarların). Kaynak, eski uygulamanın veri klasörü (5. adımdaki tablo:
   `~/Library/Application Support/Kromis` ya da `%LOCALAPPDATA%\Kromis`);
   kimlik dosyası ayrı verilir (3. adımdaki yol). **Önce `--kuru`:** hiçbir
   şey yazmaz, depo başına sayıları basar.

   ```sh
   DATABASE_URL=… KROMIS_SECRET_KEY=… KROMIS_DATA_DIR=/data \
     python tools/ice_aktar.py --kaynak "~/Library/Application Support/Kromis" \
       --eposta sen@ornek.com --kimlik-dosyasi ~/.config/kromis/credentials.env --kuru
   ```

   Sayılar beklediğin gibiyse `--kuru`yu kaldırıp aynı komutu koştur.
   Dosyalar `KROMIS_DATA_DIR/kullanicilar/<hesap>/` altına **kopyalanır**,
   kaynak klasöre dokunulmaz — taşıma bittikten sonra eskisini kendin
   arşivlersin. Aynı komutu ikinci kez koşturmak güvenli: var olan kayıtlar
   atlanır (0 yeni satır); `--yeniden` var olanı kaynaktakiyle ezer. Bozuk bir
   kayıt varsa araç onu bildirir, gerisini yükler ve 3 ile çıkar; 0 "her şey
   geldi" demek. Kaynak klasör web'in `KROMIS_DATA_DIR`i ile aynıysa
   (`output/` kökte) araç yine çalışır — kullanıcı dizini ayrı bir alt klasör.
5. Uygulamayı aç (`uvicorn app:app` ya da `docker compose up`), `/giris`ten
   3. adımdaki hesapla gir; Medya, klasörler, oturumlar, paletler, kütüphane ve
   Ayarlar'daki anahtarlar eski uygulamadakiyle aynı görünmeli. Ayarlar'ın
   dibindeki "yeni sürüm" satırı ve "şimdi kontrol et" düğmesi web'de YOK:
   GitHub sürüm denetimi web sürümünde kapalı (sunucuyu sen güncelliyorsun),
   sürüm satırı duruyor.
6. **Bakım:** `DATABASE_URL=… KROMIS_DATA_DIR=… python tools/artik_dosya.py`
   DB'de satırı olmayan medya dosyalarını listeler (`--sil --evet` siler);
   `KROMIS_SECRET_KEY` döndürme `tools/anahtar_dondur.py` ile — ikisi de
   [docs/isletme.md](docs/isletme.md)'de.
7. **Nesne depolama (isteğe bağlı, işçi süreci gelince ZORUNLU).** Medya
   dosyaları öntanımlı olarak `KROMIS_DATA_DIR` altındaki diskte durur; bu,
   tek makinede (`docker compose`) yeter. Uygulama ve işçi ayrı makinelerde
   koşacaksa ortak disk yok — medya S3 uyumlu bir kovaya taşınır
   (Cloudflare R2 önerilen: çıkış ücreti sıfır). Kod `boto3` taşımaz, imzayı
   kendisi atar; kovaya CORS gerekmez, `/output/*` ve `/assets/*` 302 ile 15
   dakikalık imzalı adrese yönlenir (tarayıcı takip eder, `<video>` ileri
   sarmayı doğrudan kovadan yapar).

   *Kova ve jeton (Cloudflare panosu):* **R2 → Create bucket** (ad: ör.
   `kromis`, konum otomatik) → **Manage R2 API Tokens → Create API token** →
   izin **Object Read & Write**, kapsam **yalnız bu kova** → *Access Key ID*
   ve *Secret Access Key* bir kez gösterilir, parola kasasına yaz. Uç nokta
   panonun sağında: `https://<hesap-id>.r2.cloudflarestorage.com` (kova adı
   URL'de YOK). Dört değişken (`.env.example` her birini açıklıyor):

   ```sh
   KROMIS_NESNE_DEPO_URL=https://<hesap-id>.r2.cloudflarestorage.com
   KROMIS_NESNE_DEPO_KOVA=kromis
   KROMIS_NESNE_DEPO_ANAHTAR_ID=…
   KROMIS_NESNE_DEPO_GIZLI=…
   ```

   Dördü de boşsa disk, dördü de doluysa kova; **yarısı doluysa uygulama
   açılmaz** (sessizce diske düşen bir dağıtım işçi gelince "üretildi ama
   görünmüyor" olurdu). `KROMIS_NESNE_DEPO_BOLGE` yalnız R2 dışı S3 için.

   *Sıra: araç → değişkenler → dağıt.* Yereldeki dosyaları aynı anahtarla
   (`kullanicilar/<uuid>/…`) kovaya önce **`--kuru`** ile say, sonra yükle;
   araç idempotent (ikinci koşu 0 yükler), yereli **silmez**:

   ```sh
   KROMIS_NESNE_DEPO_URL=… KROMIS_NESNE_DEPO_KOVA=… KROMIS_NESNE_DEPO_ANAHTAR_ID=… KROMIS_NESNE_DEPO_GIZLI=… \
     python tools/medya_tasi.py --kaynak /data --kuru     # kaç dosya, kaç bayt; çıkış 3 = yüklenecek var
   …  python tools/medya_tasi.py --kaynak /data            # yükle, HEAD ile doğrula; çıkış 0 = hepsi kovada
   ```

   Sonra dört değişkeni platforma yaz, dağıt ve canlı doğrula: giriş yapmış
   bir tarayıcıdan bir galeri görselini aç (ağ sekmesinde `/output/<ad>` →
   **302**, ardından `r2.cloudflarestorage.com` adresinden 200); ya da
   çerezle `curl -sI -b "kromis_oturum=…" https://<alan>/output/<ad>` — `HTTP/2
   302` ve `location: https://<hesap-id>.r2.cloudflarestorage.com/kromis/
   kullanicilar/…?X-Amz-Algorithm=…` görülmeli; `curl -s -o /dev/null -w
   '%{http_code}' '<location>'` 200 verir, `-H 'Range: bytes=0-7'` ile 206.
   Bir video oynatıp ileri sar, bir klasörü ZIP indir, bir görsel içe aktar
   ve logo bindir — hepsi kovaya yazar. Bakım aracı kovayı da tarar: aynı
   dört değişkenle `python tools/artik_dosya.py` "kova: kromis … 0 artik"
   demeli. Doğrulama bitince yerel `kullanicilar/` dizinini arşivle; artık
   okunmuyor.

   *Kova ayarları (Faz 2 / 10; bir kez, Cloudflare panosu → kova → Settings):*
   **özel** kalsın (public access ve r2.dev kapalı — okuma 15 dk'lık imzalı
   URL'yle), **Object versioning (nesne sürümleme): açık** (silinen/ezilen nesne geri alınabilir;
   medya yedeğin bu), **yaşam döngüsü kuralı:** önek `kullanicilar/` için
   "delete noncurrent versions after 30 days" (sürüm geçmişi sonsuza dek
   şişmesin). Girdi nesnelerinin (`isler/<id>/`) temizliği kovada değil
   işçide (8. adımdaki saklama). İsteğe bağlı ikinci kovaya `rclone sync`
   ve gerekçeleri [docs/isletme.md § 8](docs/isletme.md).
8. **İşçi süreci** (Faz 2 / 3). Üretim işleri (görsel üret/düzenle, video
   üret/canlandır) web sürecinde değil ayrı bir işçide koşar: rota işi
   `isler` tablosuna yazar, işçi kuyruktan alır, sağlayıcıyı çağırır, sonucu
   depoya ve `medya`ya yazar. İşçi AYNI imajdan, başka komutla açılır —
   `Dockerfile` CMD değişmez, ikinci süreç `python isci.py`:

   ```sh
   DATABASE_URL=… KROMIS_SECRET_KEY=… KROMIS_DATA_DIR=/data python isci.py
   ```

   Yerel `docker compose up` bunu kendi yapar (`isci` servisi; göçü bekler,
   web ile aynı `/data` birimini paylaşır, `stop_grace_period: 60s`).
   Platformda ikinci bir süreç/servis olarak tanımlanır: Fly.io `fly.toml` →
   `[processes]` `isci = "python isci.py"` (web `app`in yanına), işçiye ayrı
   `[[vm]]`, `kill_timeout = "300s"` (Fly'ın tavanı) ve `[http_service]`
   yalnız `app`e — tam örnek ve Railway/Render karşılıkları
   [docs/isletme.md § 7](docs/isletme.md); Railway/Render → aynı repo ve
   imajla ikinci servis, *Start Command* `python isci.py` (Render'da tür
   *Background Worker*). İşçi web'in **üç değişkenini aynen**
   ister (`DATABASE_URL`, `KROMIS_SECRET_KEY` — anahtarsız işçi de açılmaz,
   çözeceği satır var —, `KROMIS_DATA_DIR`) ve ayrı makinedeyse 7. adımdaki
   dört nesne depolama değişkenini (ortak disk yok: işçinin yazdığı MP4'ü web
   ancak kovadan görür; yarım yapılandırma işçiyi de açmaz). İsteğe bağlı üç
   ayar (`.env.example`): `KROMIS_ISCI_ES_ZAMANLI` aynı anda kaç iş (öntanımlı
   4; her iş bir sağlayıcı çağrısı, bağlantı havuzu `4 + 1`),
   `KROMIS_IS_KALP_ESIGI_SN` kalbi bu kadar saniye susan işin `hata` sayılması
   (öntanımlı 300), `KROMIS_IS_SAKLAMA_GUN` kapanmış iş satırlarının kaç gün
   saklanacağı (öntanımlı 30). Açılışta `isciler` tablosuna satır yazar, 30
   sn'de bir kalp atar, kapanışta siler; günlüğü stdout'a satır başına JSON
   (9. adım). **Kapanış SIGTERM:** yeni iş almayı bırakır, eldeki işi BİTİRİR
   (sağlayıcı çağrısı faturalandı), sonra çıkar — platformun kapanış süresini
   (Fly `kill_timeout`, compose `stop_grace_period`) en uzun sağlayıcı
   çağrısına göre ver (video 10 dk'ya kadar; Fly'ın tavanı 300 sn, yani uzun
   video işi dağıtımda kaybedilebilir — bilinen sınır); süre yetmezse iş
   `calisiyor`da kalır ve başka bir işçinin kalp turu onu `hata` yapar,
   kullanıcı panelden yeniden gönderir (otomatik yeniden deneme YOK: çift
   fatura riski). **Bakım işçinin içinde, ayrı cron yok (Faz 2 / 10):**
   açılışta ve 5 dk'da bir kapanmış ve `KROMIS_IS_SAKLAMA_GUN` günden eski
   iş satırlarını siler (galeri ürünlerine dokunmaz; silinen işin referans
   görselleri yalnız başka iş onlara bakmıyorsa gider), kalbi susmuş ölü
   işçi satırlarını düşürür (`/health` `worker_alive` doğruyu söylesin);
   günlükte `olay=bakim`. Sağlık denetimi: `python isci.py --tek-tur` bir iş
   alıp çıkar, kuyruk boşsa 0 ile döner — CI'ın `docker` işi bunu koşturur;
   işçinin ayakta olduğunu web'in `/health` gövdesindeki `worker_alive`
   alanından okursun (9. adım).
9. **Günlük, istek kimliği, `/health`, Sentry** (Faz 2 / 9). İki süreç de
   stdout'a **satır başına bir JSON nesnesi** yazar (`ts`, `seviye`, `logger`,
   `mesaj`, sonra alanlar); platformun günlük ekranı/toplayıcısı alanlara
   açar. Her HTTP isteği bir satır (`olay=istek`: `yontem`, `rota`, `durum`,
   `sure_ms`, `kullanici_id`, `istek_id`); her iş dört satır (`is.alindi` →
   `is.basladi` → `is.bitti`/`is.hata`, hepsinde `is_id` + `kullanici_id` +
   `model` + `sure_ms`) — "bu iş ne oldu" sorusu `grep <is_id>`. Anahtarlar
   hiçbir satıra girmez (aynı redaksiyon `hata.log`unkiyle). Yerelde okunur
   biçim için `KROMIS_GUNLUK_BICIMI=metin`; başka bir değer uygulamayı
   AÇMAZ. uvicorn'un kendi erişim günlüğü imajda kapalı (`--no-access-log`);
   kendi komutunla açıyorsan aynı bayrağı ver, yoksa her istek iki kez yazılır.
   Üçüncü parti uyarıları (SQLAlchemy, httpx) ve uvicorn'un yaşam döngüsü /
   istisna satırları da aynı JSON akımında ve redakte (Faz 2 / 10) — yalnız
   açılışın ilk iki uvicorn satırı stderr'de düz metin.

   *Günlük işletme — dağıt, geri al, sağlık, uyarı, saklama:* tek yerde,
   [docs/isletme.md § 7-9](docs/isletme.md) (iki süreç tablosu, `fly.toml`
   örneği, kova düzeni, ilk üretim koşusu kontrol listesi).

   *İstek kimliği:* her cevapta `X-Request-ID` başlığı döner; vekil (Fly,
   Cloudflare, Railway) gelen isteğe bir kimlik koyduysa o kullanılır, yoksa
   üretilir. Kullanıcı "şu istek hata verdi" dediğinde tarayıcının ağ
   sekmesindeki başlık ile günlükteki `istek_id` aynı dizedir.

   *`/health`:* gövdeye `worker_alive` (son 90 sn içinde kalp atan bir işçi
   satırı var mı) ve `worker_last_heartbeat` (ISO 8601) eklendi; DB'ye
   ulaşılamıyorsa ikisi `null`. **`ok`a ve durum koduna GİRMEZ:** işçi ölüyken
   web 200 verir — işçinin düşmesi web'i yeniden başlattırmamalı. Platformun
   sağlık denetimi durum koduna baksın (200/503); işçi için uyarı kuralı
   gövdeye (`worker_alive:false` beş dakikadır sürüyorsa bildir) ya da işçinin
   kendi günlüğüne (`isci.basladi` sonrası satır yoksa) bağlanır. Kuyruk
   birikirse (derinlik > 20 ya da en eski bekleyen > 10 dk) işçi 30 sn'de bir
   `olay=uyari` (WARNING) düşürür — [docs/isletme.md](docs/isletme.md) § 6.

   *Sentry (isteğe bağlı):* `SENTRY_DSN` verilmişse web ve işçi istisnaları
   ve ERROR satırlarını Sentry'ye gönderir (PII kapalı, istek gövdesi hiç,
   olaydaki her dize redaksiyondan geçer; `surec` etiketi `web`/`isci`, işçide
   `is_id` etiketi, web'de `istek_id`). DSN yoksa paket ithal bile edilmez.
   Kurulum: Sentry'de proje aç (Platform: Python → FastAPI) → *Client Keys
   (DSN)* → değeri platformda **web ve işçi** servislerinin ikisine de
   `SENTRY_DSN` olarak yaz, istersen `SENTRY_ENVIRONMENT=production`; dağıt.
   Doğrula: işçiye bozuk bir iş ver ya da geçici olarak bir hata fırlat, Sentry
   *Issues*'ta `kromis@<sürüm>` etiketiyle görünmeli. Kapatmak: değişkeni sil,
   yeniden dağıt. Uyarı kuralları (`uyari` olayı, hata oranı) Sentry
   panelinde *Alerts* altında tanımlanır, kodda değil.
10. **Planlar ve kredi** (Faz 3). Platform anahtarıyla (1d) üreten kullanıcı
    artık **kredi harcar**; kendi anahtarıyla üreten harcamaz. Kurallar kodda,
    sayılar ortamda:

    *Üç plan* (`services/planlar.py`; `kullanicilar.plan`): **`free`** —
    herkes böyle başlar, aylık hibe alır, görselleri **filigranlı**, video
    modelleri **kapalı** (403 "planında yok"); **`temel`** ve **`pro`** —
    filigransız, video açık, hibeleri öntanımlı 1.200 / 4.500 (K5; fiyat
    Polar'da). Satın alma yolu `/planlar` (Faz 4 / 4: checkout ve müşteri
    portalı Polar'ın barındırılan sayfaları; ürün aynası `tools/polar_esitle.py`
    — kurulum **11. adımda**). Admin yolu duruyor: `/admin` → kullanıcı
    satırı → plan seçici (`olay=admin.plan`), "kredi ekle" (hibe ya da paket kovası).

    *Aylık hibe* — `KROMIS_FREE_AYLIK_HIBE` (`.env.example` 1. bölüm): boş =
    **200** kredi (≈ 1 USD sağlayıcı maliyeti, ~25 Azure `medium` görsel),
    `0` = hibe kapalı. Kural "**hibeye tamamla**": bakiye bu sayının
    ALTINDAYSA fark yatar, üstündeyse dokunulmaz; kullanılmayan hibe
    devretmez. İki yazar: web kayıt anında ilk hibeyi yatırır, işçinin 5
    dakikalık bakım turu her ay başında tamamlar — değişken **web VE işçi**
    sürecine aynı değerle verilir (yalnız birine verilirse kayıt hibesi ile
    aylık hibe farklı sayı olur).

    *İki kova (Faz 4 / 2)* — bakiye artık iki kova: **aylık hibe**
    (`kullanicilar.bakiye`, devretmez) ve **paket kredisi**
    (`kullanicilar.paket_bakiye`, satın alınan, devreder — Polar webhook'u
    yazar, Faz 4 / 3). Rezerv hibeden başlar, yetmezse paketten sürer; iade
    önce pakete döner. Ücretli planların dönem hibesi `KROMIS_TEMEL_AYLIK_HIBE`
    / `KROMIS_PRO_AYLIK_HIBE` (boş = 1.200 / 4.500 — K5; `.env.example` 1. bölüm,
    web VE işçi). Bakım turu YALNIZ `free` planı tamamlar; ücretli planın dönem
    hibesini Polar'ın `order.paid` olayı yatırır (Faz 4 / 3, `POST
    /api/odeme/webhook`; üç `KROMIS_POLAR_*` değişkeni `.env.example` 1.
    bölümde — kurulum **11. adımda**). Faz 4 / 2'nin geçici köprüsü
    `KROMIS_UCRETLI_HIBE_BAKIMDA` KALDIRILDI: ortamda kalmışsa silin, işçi onu
    artık okumaz. Admin eliyle `pro` yapılmış (Polar aboneliği olmayan) hesap
    dönem hibesi almaz — admin "kredi ekle" ile.

    *Rezerv → onay → iade* — iş sıraya girerken tahmini kredi bakiyeden
    **rezerve** edilir (yetmezse **402** `err.kredi_yetersiz`, iş açılmaz);
    bitince gerçek maliyetle **onaylanır**, fark iade; hata / iptal / bayat
    düşürme **tam iade**. Günlük kredi tavanı (`KROMIS_GUNLUK_KREDI_TAVANI`,
    8. adımın öncesi) KALIR ve önce sorulur: tavan kötüye kullanımı, bakiye
    parayı sınırlar. Kullanıcı bakiyesini composer satırında ("bu tur 8
    düşer · kalan 192"), iş panelinde ("rezerv 8 · gerçek 8 · iade 0") ve
    Ayarlar → **Kredi** bölmesinde (son 20 hareket) görür; API'si
    `GET /api/kredi`.

    *Filigran* — `KROMIS_FILIGRAN_DOSYASI` (isteğe bağlı, yalnız işçi okur):
    şeffaf arka planlı PNG yolu, ≥ 512 px; boşsa paketle gelen marka-nötr
    `bundled/filigran.png`. Ücretsiz planın görseli işçide alt sağa işaretle
    yazılır (tek nesne, ham kopya yok); dosya YOKSA iş `hata`ya düşer ve
    rezerv iade edilir — sessizce filigransız çıkmaz.

    *Admin kredi ekleme* — `/admin` → kullanıcı → "kredi ekle" (± miktar +
    zorunlu açıklama) `duzeltme` satırı yazar, `admin_id` izli
    (`olay=admin.kredi`); tek para girişi yolu bu ve aylık hibe.

    *Marj* — `/admin` → **Marj** sekmesi (7 / 30 gün, model başına Σ kredi,
    ≈USD, sağlayıcı verisi, ortalama süre, hata) ve aynı sayılar CSV olarak
    `DATABASE_URL=… python tools/marj_raporu.py --gun 30` (konteyner içinden;
    aylık sağlayıcı faturasıyla yan yana). `python tools/tarife_kontrol.py`
    (depodan) katalogda "fiyat doğrulanamadı" notlu modelleri basar — bir kez
    sağlayıcı fiyatıyla karşılaştır, gerekirse `credits`i PR ile düzelt.

    *Defter tutarlılığı* — işçinin bakım turu her 5 dk her kullanıcıda iki
    kovayı ayrı ölçer (`SUM(kova=hibe) == bakiye`, `SUM(kova=paket) ==
    paket_bakiye`); sapma varsa `olay=defter.tutarsiz` (WARNING, kullanıcı ve
    `kova` başına) ve `olay=bakim` satırında `tutarsiz_kullanici=N`
    — tur düzeltmez, "kredi ekle" ile düzeltirsin. Yedeği ayrı değil: tablo DB
    yedeğinin içinde ([docs/isletme.md § 2, § 6, § 9](docs/isletme.md)).

    **Canlı kontrol listesi (bir kez, dağıtım sonrası):**
    1. `KROMIS_FREE_AYLIK_HIBE` iki sürecin de sırrında (ya da ikisinde de boş).
    2. İlk `olay=bakim` satırı (≤ 5 dk): `hibe_satiri=N` (N = mevcut kullanıcı
       sayısı — hepsi `free`, hepsi 0 bakiyeyle başlıyor) ve `tutarsiz_kullanici=0`.
    3. `/admin` → kendi hesabın → plan `pro` (günlükte `olay=admin.plan`);
       yoksa kendi hesabın da video göremez. Bakım turu ücretli planı
       TAMAMLAMAZ (Faz 4 / 3): kendi hesabına krediyi aynı satırdan "kredi
       ekle" ile ver (kendi platform anahtarına kendi harcaman).
    4. Kendi hesabınla `GET /api/kredi` → `bakiye`, `plan: "pro"`, `hibe`,
       `sonraki_hibe`, `filigran: false`, `video: true`.
    5. Ücretsiz bir TEST hesabıyla platform anahtarlı bir görsel (Azure
       `medium` = 8 kredi): composer "kalan 200" → gönderince "kalan 192" →
       iş bitince panelde "rezerv 8 · gerçek 8 · iade 0", indirilen görselde
       işaret alt sağda, Ayarlar → Kredi'de hibe, rezerv ve onay satırları.
    6. Aynı hesapla bir video modeli seç → kartta "planında yok" rozeti,
       gönder düğmesi kapalı (sunucu tarafı aynı kapı: 403 `err.plan_kapsamiyor`).
    7. `/admin` → Marj sekmesi o işle dolu; `python tools/tarife_kontrol.py`
       dört modeli bir kez fiyat sayfasıyla doğrula.

11. **Ödeme (Polar)** (Faz 4). Para **Polar'da** tahsil edilir — Polar
    **Merchant of Record**: satıcı hukuken Polar, vergi (KDV/VAT/GST), fatura
    ve kart verisi onda; bize yalnız imzalı webhook'un deftere yazdığı satır gelir.
    Bizde kart verisi YOK, fatura sayfası YOK (müşteri portalı Polar'ın).
    Karar kaydı ve ölçümler: [docs/faz4-odeme-abonelik-kvkk.md](docs/faz4-odeme-abonelik-kvkk.md);
    işletme yüzü (yedek, uyarı, aylık mutabakat, KVKK başvurusu)
    [docs/isletme.md § 2, § 6, § 9](docs/isletme.md).

    *Sıra: önce sandbox, sonra production.* Polar'ın sandbox'ı
    (`sandbox.polar.sh`) AYRI bir organizasyon: kendi jetonu, kendi webhook
    sırrı, kendi ürünleri. `KROMIS_POLAR_ORTAM` boşken uygulama SANDBOX'a
    bağlanır (yanlışlıkla canlıya değil yanlışlıkla sandbox'a — ilk canlı
    denemede "ürün yok" diye fark edilir); canlıya geçerken `production`
    yazılır. Her iki ortam için aynı dört adım:

    1. **Jeton** — Polar → *Settings → Developers → Access tokens* → yeni
       organizasyon jetonu — kapsamlar en az: ürünleri ve siparişleri OKUMA
       (ayna, mutabakat), checkout ve müşteri oturumu AÇMA (satış, portal),
       abonelik YAZMA (hesap silmede `revoke`); kapsam adlarını panelden
       doğrula (bu oturumlardan Polar belgesi okunamadı) → `KROMIS_POLAR_ERISIM_JETONU`. Yalnız WEB süreci ve araçlar okur; işçi
       Polar konuşmaz. Kasaya kopya (isletme § 2).
    2. **Webhook** — *Settings → Webhooks → Add endpoint*: URL
       `https://<alan adı>/api/odeme/webhook`, biçim *Raw* (Standard
       Webhooks), olaylar: `order.paid`, `order.refunded`,
       `subscription.active`, `subscription.updated`, `subscription.canceled`,
       `subscription.uncanceled`, `subscription.revoked`, `customer.created`,
       `customer.updated` (dokuz; `services/odeme.py ISLENEN_TURLER` —
       seçilmeyen tür kaydedilir, işlenmez). Panelin ürettiği sır →
       `KROMIS_POLAR_WEBHOOK_SIRRI` (yalnız web). Sır boşsa uç 503 verir,
       yanlışsa her teslimat 400 `imza_gecersiz` ve `olay=odeme.imza_gecersiz`
       (WARNING) — Polar saatlerce yeniden dener, sonra ucu kapatır: ilk
       teslimatı günlükte gör.
    3. **Ürünler ve metadata** — Polar'da her ürünün *Metadata* alanına
       sözleşme yazılır (`tools/polar_esitle.py` başlığı): `kromis_tur`
       `plan` | `paket` (zorunlu); `kromis_plan` `temel` | `pro` (yalnız
       plan); `kromis_kredi` tam sayı (paket: yüklenen kredi; plan: dönem
       hibesi, bilgi). Plan ürünü AYLIK abonelik, paket TEK SEFERLİK sabit
       fiyat; K5'in tablosu: `temel` 9 USD/ay 1.200 kredi, `pro` 29 USD/ay
       4.500 kredi, paketler 5 USD/500, 14 USD/1.600, 30 USD/3.800 (sahibin
       sayıları; Polar'da başka yazılırsa aşağıdaki hibe değişkenleri ezer).
       Metadata'sı eksik ürün (bağış, deneme) aynaya SIZMAZ, `UYARI URUN
       ATLANDI` ile görünür.
    4. **Ayna** — konteynerin içinden:

       ```sh
       DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_esitle.py --kontrol   # ne değişecek? (fark → 2)
       DATABASE_URL=… KROMIS_POLAR_ERISIM_JETONU=… python tools/polar_esitle.py             # yazar
       ```

       `/planlar` fiyatı bu aynadan gösterir; webhook `product_id`yi burada
       arar — satır yoksa para YATMAZ, olay `hata=urun_yok` ile bekler (admin
       "Ödeme" sekmesi), aracı koş ve Polar panelinden olayı yeniden gönder.
       Ayna 7 günden eskiyse admin sekmesi uyarır (`olay=odeme.urunler_bayat`):
       Polar'da fiyat değiştirdiğin her gün aracı koş.

    *Fiyat ve hibe değişkenleri* (`.env.example` 1. bölüm): fiyat Polar'da,
    bizde yok. Dönem hibesi `KROMIS_TEMEL_AYLIK_HIBE` / `KROMIS_PRO_AYLIK_HIBE`
    (boş = 1.200 / 4.500; web VE işçi, aynı değer) — `order.paid` ile "hibeye
    tamamla" (dolu bakiyeye binmez), `subscription.revoked` ile ücretsiz
    hibeye iner (`sona_erme`, yalnız hibe kovası). `KROMIS_FREE_AYLIK_HIBE` 10.
    adımda.

    *İki kova kuralı* (K3): **aylık/dönem hibesi** devretmez ("hibeye
    tamamla"), **paket kredisi** devreder ve plan düşse de durur. Rezerv
    hibeden başlar, yetmezse paketten; iade önce pakete. Ayarlar → Kredi
    ikisini ayrı gösterir; bakım turu ikisini ayrı ölçer (`tutarsiz_kullanici`).

    *İade politikası* (K6, K11; `/hukuk/kullanim-sartlari`): harcanmış kredi
    iade edilmez; harcanmamış paket 14 gün içinde iade edilebilir; abonelik
    dönem sonunda biter (iptal eden ödediği dönemi kullanır). Parayı Polar
    panelinden iade edersin (`order.refunded` bize yalnız WARNING
    `olay=odeme.iade` düşürür, defter DOKUNULMAZ — harcanmış kredi eksiye
    inmesin); krediyi `/admin` → kullanıcı → **"kredi ekle"** ile eksi
    miktar ve açıklamayla düşersin (`duzeltme` satırı, kova seçilir).
    Otomatik düşüm BİLEREK yok.

    *Hesap silme ve dışa aktarma* (K9, Faz 4 / 5): kullanıcının kendi düğmesi
    Ayarlar → **Hesap** — "Verimi indir" (dokuz dosyalık ZIP) ve "Hesabımı sil"
    (parola + onay metni). Silme ANINDA hesabı kilitler (e-posta anonim,
    oturumlar/BYOK anahtarları gider, bekleyen işler iptal + iade, Polar
    aboneliği `revoke`), içerik `KROMIS_HESAP_SILME_BEKLEME_GUN` (boş = 7) gün
    sonra işçinin bakım turunda kalıcı gider; `kredi_hareketleri`/`siparisler`
    anonim sahiple KALIR (mali kayıt). Polar aboneliği kapatılamazsa
    `olay=hesap.silme_abonelik` (WARNING) — Polar panelinden elle kapat.
    E-postayla gelen KVKK başvurusu: isletme § 9 (30 gün).

    *Webhook teslimat günlüğü* (`odeme_olaylari`): admin "Ödeme" sekmesi son
    100 teslimatı ve hatalıları gösterir; satırlar
    `KROMIS_ODEME_OLAY_SAKLAMA_GUN` (boş = 365, yalnız işçi) gün sonra bakım
    turunda silinir (`olay=odeme.olaylar_temizlendi`) — sipariş ve defter
    satırı bu süreye bağlı değil.

    *Hukuki metin sürümü* (K11, Faz 4 / 6): dört metin `bundled/hukuk/`
    (kullanım şartları, gizlilik, çerez, ticari haklar; tr/en) `/hukuk/<slug>`
    altında; sürüm `services/hukuk.py HUKUK_SURUMU` (YYYY-AA), kayıtta ve ilk
    checkout'ta tıkla-onay bu sürümle damgalanır, sürüm ilerleyince herkes
    Ayarlar'daki banner'dan yeniden onaylar. `HUKUK_ONAYLI = False` iken her
    sayfada "TASLAK — avukat onayı bekliyor" damgası; avukat ve mali müşavir
    incelemesi bitince tek satırlık PR `HUKUK_ONAYLI = True` yapar
    (adımlar [docs/hukuk-kontrol-listesi.md](docs/hukuk-kontrol-listesi.md)).
    Polar'ın AI ürün incelemesi bu metinleri yayında ister — production
    başvurusu ondan sonra.

    *Aylık mutabakat* — payout geldiğinde konteynerin içinden
    `python tools/polar_mutabakat.py --cikti fark.csv` (geçen ay; `--ay
    YYYY-MM` ile başka ay): Polar'ın ödenmiş siparişleri ↔ `siparisler`, fark
    CSV'de, çıkış **0** sıfır fark / **2** fark var / **3** Polar-DB hatası —
    cron'a bağla. Yanına `tools/marj_raporu.py --gun 30` (gider). Ayrıntı
    isletme § 9.

    **Canlı kontrol listesi (bir kez; ilk beşi sandbox'ta, sonrası production):**
    1. Sandbox'ta test hesabıyla bir **kredi paketi** al (Polar test kartı) →
       teşekkür sayfası "bakiyene işlendi", Ayarlar → Kredi'de paket kovası
       500 ve sipariş satırı; günlükte `olay=odeme.order.paid kredi=500`.
    2. Sandbox'ta **`temel`ye abone ol** → plan `temel`, filigran kalkar, video
       açılır, hibe kovası 1.200'e tamamlanır (`hibe:<u>:polar:<order_id>`).
    3. Polar panelinden aynı `order.paid` olayını **yeniden gönder** → cevap
       `yinelenen` ya da `islendi`, ama `siparisler` ve defterde satır sayısı
       AYNI (K4 üç katman).
    4. Portaldan aboneliği **iptal et** → `plan_bitis` dolu, plan dönem sonuna
       kadar `temel`; (sandbox'ta dönem sonu beklenmez) `subscription.revoked`
       gelince `free` + `sona_erme` satırı, paket kovası DURUR.
    5. **Production jetonları**: Polar production organizasyonunda jeton +
       webhook + ürünler + metadata (yukarıdaki dört adım), `KROMIS_POLAR_ORTAM=production`,
       `polar_esitle.py --kontrol` → 0; dağıt; `/planlar` gerçek fiyatları
       gösteriyor.
    6. **İlk gerçek 5 USD'lik paket kendi hesabından** (gerçek kart) → bakiye,
       sipariş, Polar panelinde ödeme; `olay=odeme.hata` YOK.
    7. **Portaldan faturayı indir** (Ayarlar → Kredi → "Aboneliğimi ve
       faturalarımı yönet") — fatura Polar'ın, bizde kopyası yok.
    8. **Hesap silme test hesabıyla**: Ayarlar → Hesap → "Verimi indir" (ZIP
       dokuz dosya) → "Hesabımı sil" → giriş yok, e-posta anonim; işçiye geçici
       `KROMIS_HESAP_SILME_BEKLEME_GUN=0` ver (dağıt), ilk `olay=bakim`
       satırında `temizlenen_hesap=1` ve `olay=hesap.temizlendi`, R2'de
       `kullanicilar/<id>/` boş, `siparisler`/`kredi_hareketleri` satırları
       duruyor → değişkeni geri boşalt (7 gün).
    9. **`/hukuk/*` yayında**: dört sayfa iki dilde açılıyor, footer bağlantıları
       çalışıyor; avukat onayı geldiyse `HUKUK_ONAYLI = True` ve damga yok —
       Polar production başvurusu bundan sonra.
    10. **İlk ay sonunda `polar_mutabakat.py`** → çıkış 0 (sıfır fark) ve
        Polar payout brütü = özet satırındaki toplam; yanında `marj_raporu.py`.
        Aynı gün **ikinci kova** (`kromis-yedek`, başka hesap/sağlayıcı) ve
        günlük `rclone sync` cron'u kurulur — ödeyen kullanıcı var (isletme § 8).

---

## Sonra: yeni sürüm gelirse
Yeni bir `.zip` aldığında [GUNCELLEME.md](GUNCELLEME.md) sayfasını izle.

- **macOS:** uygulamayı kapat → yenisini Programlar'a sürükleyip **Değiştir** →
  güvenlik iznini bir kez daha ver. `Application Support` klasörünü SİLME.
- **Windows:** uygulamayı kapat → yeni zip'i ayıkla → eski `Kromis`
  klasörünün **yerine** koy (Windows "Hedefteki dosyaları değiştir" diye sorar,
  onayla) → SmartScreen izni bir kez daha gerekebilir.
  `AppData\Local\Kromis` klasörünü SİLME.
- **Android:** yeni APK'yı indir ve üzerine kur — **uygulamayı SİLME.**
  Android eskisinin üzerine yazar ve verin (görseller, klasörler, Azure anahtarı)
  yerinde kalır. Uygulamayı kaldırıp yeniden kurarsan hepsi silinir.

> **Uygulamanın adı değiştiyse bu bölüm geçerli değil.** Uygulama **Kromis
> Studio** adını aldı; eski adla kurulu bir sürümden geçiyorsan masaüstünde
> veri kendiliğinden taşınıyor, Android'de ise yeni APK eskisinin ÜZERİNE
> yazmıyor — yan yana kuruluyor ve eskisini elle kaldırman gerekiyor. Tek
> seferlik adımlar: [GUNCELLEME.md → Uygulamanın adı değiştiyse](GUNCELLEME.md#uygulamanın-adı-değiştiyse--bir-kerelik-geçiş).

İki sistemde de **verin kaybolmaz** ve Azure anahtarını yeniden girmen gerekmez:
görseller ve ayarlar uygulama klasörünün DIŞINDA duruyor (yerleri için 3. ve 5.
adım), yani uygulamayı silip yenisini koymak geçmişine dokunmaz.

## Sorun çıkarsa
- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi?
- **(Windows) Uygulama hiç açılmıyor, pencere gelmiyor:** iki olağan sebebi var.
  (a) `.exe`'yi `_internal` klasöründen ayırmış olabilirsin — ikisi aynı klasörde
  olmalı. (b) Zip'i **engellemesini kaldırmadan** ayıklamış olabilirsin (1. adım);
  bu durumda en temizi zip'i baştan, 1. adımdan başlayarak yeniden ayıklamak.
  Her iki durumda da `%LOCALAPPDATA%\Kromis\hata.log` dosyasına bak; varsa
  içeriğini teknik desteğe gönder.
- **(Windows) Sebebi anlaşılmıyorsa — kendi kendine teşhis:** `Kromis` klasöründe
  boş bir yere **Shift + sağ tık → PowerShell penceresini burada aç** de ve şu iki
  satırı sırayla yaz. Pencere açılmaz; çıkan dosyayı teknik desteğe gönder, hangi
  halkanın koptuğunu yazıyor.

  ```powershell
  $p = Start-Process -FilePath .\Kromis.exe -ArgumentList '--onyukleme-denetimi' -NoNewWindow -PassThru; [void]$p.WaitForExit(120000); "cikis kodu: $($p.ExitCode)"
  Get-Content $env:LOCALAPPDATA\Kromis\onyukleme-denetimi.txt -Encoding utf8
  ```

  > Neden bu kadar uzun: `.\Kromis.exe --onyukleme-denetimi` de çalışır ama paket
  > pencere kipinde derlendiği için PowerShell onu BEKLEMEZ — komut hemen geri
  > döner, dosya bir iki saniye sonra oluşur. Hemen bakılırsa "dosya oluşmadı"
  > sanılıyor (2026-09-10'da tam olarak bu yaşandı). `Start-Process` bekliyor ve
  > çıkış kodunu da veriyor: **0** = zincir sağlam, **1** = bir kademe düştü,
  > **2** = rapor bile yazılamadı (o zaman `hata.log`'a bak).
  >
  > `$env:LOCALAPPDATA` yazımı da önemli: bu sayfadaki öteki `%LOCALAPPDATA%`
  > yazımları Dosya Gezgini'nin adres çubuğu için doğru, ama PowerShell onları
  > genişletmez — boş döner.
- **(Windows) Uygulama tarayıcıda açıldı ve "bu pencereyi kapatmayın" diyor:**
  bu bir arıza değil, yedek yol — Kromis'nun kendi penceresi açılamadığında
  uygulama tarayıcında açılıyor ve her şey normal çalışıyor. O küçük pencereyi
  kapatınca Kromis da kapanır. Yine de `hata.log`'u teknik desteğe gönder: yedeğe
  düşülmesinin bir sebebi var ve o sebep düzeltilebilir.
- **(Windows) Antivirüs uygulamayı karantinaya aldı:** paket imzalanmadığı için
  bazı kurumsal antivirüsler yanlış-pozitif verebiliyor. Klasörü silme, teknik desteğe
  yaz.
- **Görsel üretilmiyor, hata mesajı çıkıyor:** key süresi/rotasyonu için teknik desteğe yaz.
- **Prompt Yönetmeni'nde "Gönder" kilitli:** hiçbir sohbet sağlayıcısı
  yapılandırılmamış. Azure'da **Dağıtım adı** boştur; OpenAI/Gemini'de anahtar
  kaydedilmemiştir. Düğmenin üzerine gelince hangi modelin eksik olduğunu yazar.
- **"Sohbet dağıtımı bulunamadı (404)":** yazdığın dağıtım adı Azure'daki adla
  birebir aynı değil. Doğru adı Azure portalındaki dağıtım listesinden kopyala.
- **"… bu modeli tanımıyor (404)":** OpenAI/Gemini tarafında seçtiğin model
  kalkmış olabilir — şeritten başka bir sohbet modeli seç.
