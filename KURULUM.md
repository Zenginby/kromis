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
