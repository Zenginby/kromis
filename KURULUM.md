# Lumeo — Kurulum (macOS, Windows ve Android)

Bilgisayarına Python veya başka bir şey kurman gerekmiyor. 5 dakika sürer.

**Hangi bölümü okuyacaksın:** 1., 2. ve 5. adımların işletim sistemine göre iki
dalı var — kendi dalını oku, ötekini atla. 3. ve 4. adımlar (Azure kimliği,
Prompt Yönetmeni) iki sistemde aynıdır.

| Sistem | Dosya |
|---|---|
| macOS (Apple Silicon) | `lumeo-macOS-arm64.zip` |
| Windows 10/11 (64-bit) | `lumeo-windows-x64.zip` |
| Android 8.0+ (arm64) | `lumeo-android-arm64.apk` |

**Telefona kuruyorsan** aşağıdaki 1. ve 2. adımları atla, doğrudan
[Android (sideload)](#android-sideload) bölümüne git — 3., 4. ve 5. adımlar
(Azure kimliği, Prompt Yönetmeni, kullanım) üç sistemde de aynıdır.

Not: Bu belge, sana ulaşan `.zip`'in kendi sistemin için ayrıca (GitHub
Actions'ın arm64 / windows runner'ında) üretildiğini varsayar — geliştirme
makinesinde yerel olarak alınan derlemeler yalnızca paketleme yolunu sınamak
için, sana gönderilen paket değildir.

## 1. Uygulamayı yerine koy

### macOS
1. `Lumeo.zip` dosyasına çift tıkla — yanında `Lumeo` uygulaması çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.

### Windows
1. Zip dosyasına sağ tıkla → **Tümünü ayıkla** (Extract All).
2. Çıkan `Lumeo` klasörünü kalıcı bir yere taşı — ör.
   `C:\Users\<kullanıcı adın>\Programlar\Lumeo`.
   **Klasörü olduğu gibi taşı, içinden yalnız `.exe`'yi çekip almaya çalışma:**
   uygulama yanındaki `_internal` klasörüne ihtiyaç duyar, `.exe` tek başına
   çalışmaz.
3. Uygulamayı `Lumeo.exe` ile açarsın. İstersen ona sağ tıklayıp
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

   > **"Lumeo" Not Opened**
   > Apple could not verify "Lumeo" is free of malware that may harm
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
3. Sayfayı aşağı kaydır: *"Lumeo engellendi"* / *"was blocked"* satırını
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

1. `Lumeo.exe`'ye çift tıkla. Uygulama **açılmayacak** ve mavi bir
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
birebir metin + ekran görüntüsü hâlâ alınmalı. -->

## 3. Azure kimliğini gir
İlk açılışta Ayarlar penceresi kendiliğinden açılır ve "Üret" düğmesi kilitlidir.
1. **Endpoint** ve **API key** alanlarını Kurum'dan aldığın bilgilerle doldur.
2. **Kaydet**. Kilit açılır.

Key bilgisayarında yalnız senin okuyabileceğin izinle saklanır ve bir daha
ekranda gösterilmez. Dosyanın yeri iki sistemde de aynı mantıkta:

| Sistem | Dosya |
|---|---|
| macOS | `~/.config/lumeo/credentials.env` (izin `0600`) |
| Windows | `C:\Users\<kullanıcı adın>\.config\lumeo\credentials.env` |

Windows'ta POSIX izin bitleri işlemediği için dosyaya erişim listesi (DACL)
sıkılaştırılıyor: kalıtım kesilir ve listede **yalnız senin hesabın** kalır.
Kendin görmek istersen:

```powershell
icacls "$env:USERPROFILE\.config\lumeo\credentials.env"
```

## 4. Prompt Yönetmeni'ni aç (istersen)
Yönetmen üç sağlayıcı ile konuşabiliyor; hangisini kullandığına göre yapılacak
şey değişiyor.

**Azure kullanacaksan:** Ayarlar penceresinde sağlayıcı **Azure OpenAI** seçili
dururken, **Prompt Yönetmeni (sohbet modeli)** başlığının altındaki
**Dağıtım adı** alanına Kurum'dan aldığın adı yaz (ör. `gpt-5.6-luna`) →
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
| macOS | `~/Library/Application Support/Lumeo/output/` |
| Windows | `%LOCALAPPDATA%\Lumeo\output\` — yani `C:\Users\<kullanıcı adın>\AppData\Local\Lumeo\output\` |
| Android | Uygulamanın kendi özel klasörü (dosya yöneticisinden görünmez). Telefona indirdiklerin ise `Resimler/Lumeo/` altında. |

Windows'ta klasörü hızlı açmak için Dosya Gezgini'nin adres çubuğuna
`%LOCALAPPDATA%\Lumeo` yazıp Enter'a basabilirsin. (Bu klasör
bilerek `AppData\Local` altında — `Roaming` olsaydı ürettiğin bütün görseller
kurumsal profille birlikte ağ üzerinden taşınmaya çalışırdı.)

Hangi sürümü kullandığını **⚙ Ayarlar** penceresinin altındaki **Sürüm**
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
Telefonun tarayıcısından `lumeo-android-arm64.apk` dosyasını indir.
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

Uygulama açılınca kalıcı bir bildirim görürsün: *"Lumeo çalışıyor"*.
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
- Görseller (PNG): **Resimler → Lumeo**
- Klasör ZIP'leri: **İndirilenler → Lumeo**

### Android'de sorun çıkarsa
- **"Uygulama yüklenmedi" / "Paket geçersiz":** dosya yarım inmiş olabilir —
  APK'yı sil ve yeniden indir.
- **"Uygulamanız bu cihazla uyumlu değil":** telefon 32-bit ya da Android 8'in
  altında. Bu pakete uygun değil, Kurum'ya yaz.
- **Ekranda sürekli "Başlatılıyor…" yazıyor:** uygulamayı tamamen kapat
  (son uygulamalardan kaydır) ve yeniden aç. Sürerse Kurum'ya yaz.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi? (3. adım)
- **İndirdiğim görseli galeride bulamıyorum:** Galeri uygulaması yeni klasörü
  görmek için biraz gecikebilir; Dosyalar uygulamasından
  `Resimler/Lumeo` klasörüne bak.

---

## Sonra: yeni sürüm gelirse
Kurum yeni bir `.zip` gönderdiğinde [GUNCELLEME.md](GUNCELLEME.md) sayfasını izle.

- **macOS:** uygulamayı kapat → yenisini Programlar'a sürükleyip **Değiştir** →
  güvenlik iznini bir kez daha ver. `Application Support` klasörünü SİLME.
- **Windows:** uygulamayı kapat → yeni zip'i ayıkla → eski `Lumeo`
  klasörünün **yerine** koy (Windows "Hedefteki dosyaları değiştir" diye sorar,
  onayla) → SmartScreen izni bir kez daha gerekebilir.
  `AppData\Local\Lumeo` klasörünü SİLME.
- **Android:** yeni APK'yı indir ve üzerine kur — **uygulamayı SİLME.**
  Android eskisinin üzerine yazar ve verin (görseller, klasörler, Azure anahtarı)
  yerinde kalır. Uygulamayı kaldırıp yeniden kurarsan hepsi silinir.

İki sistemde de **verin kaybolmaz** ve Azure anahtarını yeniden girmen gerekmez:
görseller ve ayarlar uygulama klasörünün DIŞINDA duruyor (yerleri için 3. ve 5.
adım), yani uygulamayı silip yenisini koymak geçmişine dokunmaz.

## Sorun çıkarsa
- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi?
- **(Windows) Uygulama hiç açılmıyor, pencere gelmiyor:** `.exe`'yi `_internal`
  klasöründen ayırmış olabilirsin — ikisi aynı klasörde olmalı (1. adım). Ayrıca
  `%LOCALAPPDATA%\Lumeo\hata.log` dosyasına bak; varsa içeriğini
  Kurum'ya gönder.
- **(Windows) Antivirüs uygulamayı karantinaya aldı:** paket imzalanmadığı için
  bazı kurumsal antivirüsler yanlış-pozitif verebiliyor. Klasörü silme, Kurum'ya
  yaz.
- **Görsel üretilmiyor, hata mesajı çıkıyor:** key süresi/rotasyonu için Kurum'ya yaz.
- **Prompt Yönetmeni'nde "Gönder" kilitli:** hiçbir sohbet sağlayıcısı
  yapılandırılmamış. Azure'da **Dağıtım adı** boştur; OpenAI/Gemini'de anahtar
  kaydedilmemiştir. Düğmenin üzerine gelince hangi modelin eksik olduğunu yazar.
- **"Sohbet dağıtımı bulunamadı (404)":** yazdığın dağıtım adı Azure'daki adla
  birebir aynı değil. Kurum'ya doğru adı sor.
- **"… bu modeli tanımıyor (404)":** OpenAI/Gemini tarafında seçtiğin model
  kalkmış olabilir — şeritten başka bir sohbet modeli seç.
