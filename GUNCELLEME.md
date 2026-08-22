# Lumeo — Güncelleme (macOS, Windows ve Android)

Elindeki uygulamayı yenisiyle değiştirmek için bu sayfayı izle. 3 dakika sürer.
(İlk kez kuruyorsan: [KURULUM.md](KURULUM.md).)

**Yeni sürüm çıktığını uygulama sana söylüyor:** ⚙ **Ayarlar**'ı açtığında,
kurulu sürümün hemen altında *"Yeni sürüm çıktı"* satırı belirir. Aynı yerdeki
anahtarla bu kontrolü kapatabilirsin. Paketleri her zaman
[son yayın sayfasından](https://github.com/Zenginby/gpt-image-studio/releases/latest)
da indirebilirsin — adres sabit, sürüm yükseldiğinde değişmiyor.

| Sistem | Dosya |
|---|---|
| macOS (Apple Silicon) | `lumeo-macOS-arm64.zip` |
| Windows 10/11 (64-bit) | `lumeo-windows-x64.zip` |
| Android 8.0+ (arm64) | `lumeo-android-arm64.apk` |

**Telefondaysan** 1.–3. adımları atla, doğrudan
[Android'i güncelleme](#androidi-güncelleme) bölümüne git. 4. ve 5. adımlar
(doğrulama, kontrol) üç sistemde de aynıdır.

**Hangi bölümü okuyacaksın:** 2. ve 3. adımların işletim sistemine göre iki dalı
var — kendi dalını oku, ötekini atla. 1., 4. ve 5. adımlar iki sistemde aynıdır.

> ## 🛑 En önemli iki şey
>
> 1. **Veri klasörünü SİLME.** Ürettiğin bütün görseller, geçmiş, klasörler,
>    paletler ve logo kütüphanen orada duruyor. Uygulamayı değiştirmek onlara
>    dokunmaz — ama "uygulamayla ilgili her şeyi silelim" diyip o klasörü
>    silersen **hepsi gider.** Uygulamayı değiştirmek için o klasöre hiç girmen
>    gerekmiyor.
>
>    | Sistem | Silinmemesi gereken klasör |
>    |---|---|
>    | macOS | `~/Library/Application Support/Lumeo/` |
>    | Windows | `%LOCALAPPDATA%\Lumeo\` |
>    | Android | Uygulamanın kendi klasörü — **uygulamayı KALDIRMA**, üzerine kur |
>
> 2. **(Yalnız macOS) Güvenlik uyarısında "Çöp Sepetine Taşı"ya ve Enter'a
>    BASMA** (aşağıda 3. adım). O düğme mavi/varsayılan olduğu için Enter
>    uygulamayı siler. **Windows'ta böyle bir tehlike yok** — SmartScreen
>    penceresindeki hiçbir düğme dosyayı silmez.

## 1. Uygulamayı kapat

Uygulama açıksa **kapat** (macOS'ta ⌘Q, Windows'ta pencereyi kapat). Çalışırken
değiştirmeye çalışmak yarım kurulmuş bir uygulama bırakabilir.

## 2. Yenisini yerine koy

### macOS

1. Yeni `lumeo-macOS-arm64.zip` dosyasına çift tıkla — yanında
   uygulama çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.
3. macOS *"Aynı adda bir öge var"* diye soracak → **Değiştir** (Replace) de.

Eski sürümü önceden silmen gerekmiyor; değiştirmek yeterli.

### Windows

1. Yeni `lumeo-windows-x64.zip` dosyasına sağ tıkla → **Tümünü
   ayıkla** (Extract All).
2. Çıkan `Lumeo` klasörünü, eski klasörünün **bulunduğu yere** taşı.
3. Windows *"Hedefte aynı adda dosyalar var"* diye soracak → **Hedefteki
   dosyaları değiştir** de.

**Klasörü olduğu gibi taşı, içinden yalnız `.exe`'yi çekip almaya çalışma:**
uygulama yanındaki `_internal` klasörüne ihtiyaç duyar. Ayrıca zip'in **içinden**
çalıştırma — önce ayıkla, sonra çalıştır.

## 3. Güvenlik izni — her güncellemede TEKRAR gerekiyor

Bu bir hata değil, beklenen davranış: uygulama ücretli bir geliştirici
sertifikasıyla imzalanmadığı için işletim sistemi her **yeni** dosyayı ilk
açılışta yeniden soruyor. Kurulumdaki adımların aynısı.

### macOS

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

2. **Apple menüsü** → **Sistem Ayarları** (System Settings) → **Gizlilik ve
   Güvenlik** (Privacy & Security).
3. Sayfayı aşağı kaydır: *"Lumeo engellendi"* / *"was blocked"*
   satırını bul → **Yine de Aç** (**Open Anyway**).
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir (ya da Touch ID).
5. Uygulama açılır. Bu sürüm için bir daha sormaz.

### Windows

1. `Lumeo.exe`'ye çift tıkla. Mavi **SmartScreen** penceresi
   çıkabilir ("Windows bilgisayarınızı korudu").
2. **Daha fazla bilgi** (More info) → **Yine de çalıştır** (Run anyway).

   #### ✅ Burada YIKICI bir düğme YOK
   macOS'un aksine SmartScreen'deki düğmelerin hiçbiri dosyayı silmez veya
   karantinaya almaz. **Çalıştırma** yalnızca pencereyi kapatır, Enter'a basmak
   da güvenli — en kötüsü açılışı iptal eder.

## Android'i güncelleme

**Uygulamayı KALDIRMA.** Yeni APK'yı doğrudan eskisinin üzerine kur:

1. Yeni `lumeo-android-arm64.apk` dosyasını telefona indir.
2. Dosyaya dokun → **Yükle**. Android *"Bu uygulamanın yeni bir sürümünü
   yüklemek ister misiniz?"* diye sorar → **Yükle**.
3. İlk açılış yine **2–5 saniye** sürer: uygulama yeni sürümün arayüz
   dosyalarını telefonun içine yeniden açıyor. Bu normal ve yalnız
   güncellemeden sonraki ilk açılışta olur.

**Neden kaldırmamalısın:** Android bir uygulamayı kaldırdığında onun veri
klasörünü de siler — ürettiğin bütün görseller, klasörler, paletler ve Azure
anahtarın orada. Üzerine kurmak (aynı imzayla imzalandığı için sorunsuz
çalışır) verine hiç dokunmaz.

*"Uygulama yüklenmedi"* diyorsa çoğunlukla dosya yarım inmiştir: APK'yı sil,
yeniden indir. Sürerse Kurum'ya yaz — **kaldırıp yeniden kurma**, önce sor.

## 4. Güncellendiğini doğrula

Sağ üstteki **⚙ (dişli)** düğmesine bas — pencerenin altında **Sürüm** yazıyor.
Kurum'nın söylediği numarayla aynıysa güncelleme geçmiş demektir. Destek isterken
de bu numarayı söyle.

## 5. Kontrol et: her şey yerinde mi

- **Geçmişin** (ürettiğin görseller), **klasörlerin**, **paletlerin** ve **logo
  kütüphanen** olduğu gibi duruyor olmalı.
- **Azure anahtarını yeniden girmen gerekmez** — o uygulamanın içinde değil,
  ayrı bir yerde duruyor.

Bir şey eksik görünüyorsa **uygulamayı kullanmaya devam etme** ve Kurum'ya yaz
(aşağıdaki yedek işine yarayabilir).

---

## Sürüm 0.8.0 — ne değişti

- şerit satırlarında sağlayıcı markası tekrarlanmıyor
- model şeridinde sağlayıcı işareti + koşullu Yönetmen bölümü

---

## Sürüm 0.7.0 — ne değişti

- 400'ün iki anlamı sohbette de, 404 modelin adını söylüyor
- Google hata gövdesi tek öğelik DİZİ — detail_of onu açmıyordu
- Prompt Yönetmeni'ne model seçimi + şeritler anahtara göre süzülüyor
- Nano Banana adaptörü + kalkmış DALL·E 3 katalogdan çıkarıldı

---

## Sürüm 0.6.1 — ne değişti

- boş endpoint kayıtlı Azure kurulumunu siliyordu + beş inceleme bulgusu

---

## Sürüm 0.6.0 — ne değişti

- sağlayıcı grupları ve yalnız-OpenAI kurulumu
- doğrudan OpenAI adaptörü, gpt-image-1 ve DALL·E 3
- model seçici, yeteneğe göre kontroller ve tek kapı
- adapter katmanı, yetenek doğrulaması ve model/kredi kaydı
- kimlik çözümü, çoklu sağlayıcı ayarları ve model yayını
- gizli alanlar doğrulama hatasında ve logda sızıyordu
- model kataloğu ve Android paketleme mandalı

---

## Sürüm 0.5.4 — ne değişti

- birleştirme başlığı GUNCELLEME.md'ye girmesin + güncelleme bağlantısı doğrulanıyor

---

## Sürüm 0.5.3 — ne değişti

- depo adresi yeni hesaba çevrildi (Zenginby → Zenginby)

---

## Sürüm 0.5.2 — ne değişti

- indirme Android'de köprüden geçsin + geri tuşu bulguları

---

## Sürüm 0.5.1 — ne değişti

- telefonda S ile M ızgara boyutu aynı görünmesin

---

## Sürüm 0.5.0 — ne değişti

- Yeni sürüm çıktığında uygulama artık kendisi haber veriyor — ⚙ Ayarlar'da, kurulu sürümün hemen altında.

---

## Sürüm 0.4.2 — ne değişti

**Manşet: uygulamanın adı artık Lumeo.** Simge de yenilendi. Adı değişti diye
hiçbir şeyini kaybetmiyorsun — görsellerin, geçmişin, klasörlerin ve paletlerin
olduğu gibi duruyor.

- **Telefonda üç arayüz kusuru düzeltildi.** Dar ekranda bozulan yerleşim ve
  dokunmayla ulaşılamayan iki düğme çalışır hâle geldi.
- **README'deki indirme bağlantıları çalışıyor.** Üç bağlantı da her zaman en
  son yayına işaret ediyor; sürüm yükseldiğinde adresi değiştirmek gerekmiyor.
- **Android paketinin adı düzeltildi.** Telefona kurulacak dosya artık
  `lumeo-android-arm64.apk` adıyla geliyor.

> Bu bölümü artık yayın hattı otomatik yazıyor (`tools/surum_yaz.py`). Her
> yayında en üste yeni bir bölüm ekleniyor, eskiler aşağıda duruyor.

---

## Sürüm 0.4.0 — ne değişti

**Manşet: Android sürümü geldi.** Uygulama artık telefonda da çalışıyor —
Android 8.0+ ve 64-bit (arm64) cihazlar için. Play Store'da değil; APK'yı
doğrudan kuruyorsun (kurulum adımları: [KURULUM.md](KURULUM.md) →
*Android (sideload)*).

Telefondaki sürüm **eksiksiz**: üretim, düzenleme, Prompt Yönetmeni, palet
motoru, klasörler ve logo/banner bindirmesinin hepsi telefonun kendi içinde
koşuyor. Bilgisayara ya da ayrı bir sunucuya bağlanmıyor; internet yalnızca
Azure çağrıları için gerekli.

**Masaüstünde de göreceğin değişiklikler:**

- **Arayüz artık dar pencerelerde de kullanılabiliyor.** Pencereyi
  daralttığında sol ray alta iner, paneller tam ekrana geçer. Geniş pencerede
  hiçbir şey değişmedi.
- **Yeni "Taşı…" düğmesi.** Seçim modunda (Medya → *Seç*) görselleri klasöre
  taşımanın sürükle-bırak dışında bir yolu daha var. Sürükle-bırak duruyor;
  bu, klavyeyle ve dokunmatikle de çalışan ikinci yol.

**Telefonda masaüstünden farklı iki davranış** (ikisi de bilerek):

- **Enter satır atlar, göndermez** — göndermek için **Üret** düğmesi. Telefon
  klavyesinde Shift+Enter'a basmak pratikte mümkün değil; kural aynı kalsaydı
  çok satırlı bir prompt hiç yazılamazdı.
- **Sürükle-bırak yok** — dokunmatik ekranda hiç çalışmıyor. Yerine *Seç* →
  *Taşı…*, içe aktarma için *Yükle*.

**Damlalık (ekrandan renk seçme) telefonda yok:** Android'de karşılığı olan bir
sistem servisi bulunmuyor, düğme orada hiç görünmüyor. Masaüstünde aynen duruyor.

---

## Sürüm 0.3.0'da ne değişti

**Manşet: Windows sürümü geldi.** Uygulama artık Windows 10/11 (64-bit) için de
paketleniyor — aynı uygulama, aynı özellikler. Kurulum için
[KURULUM.md](KURULUM.md)'nin Windows dallarını izle.

**İki sistemde de göreceğin tek değişiklik: yazı tipi.** Arayüzün başlıkları
artık uygulamanın kendi içinde taşıdığı **DM Sans** ile çiziliyor. Öncesinde
arayüz o yazı tipini istiyordu ama paket onu taşımıyordu, yani senin makinende
kurulu değilse sessizce sistemin yazı tipine düşülüyordu — başlıklar tasarımda
göründüğü gibi değildi ve hangi Mac'te açtığına göre değişebiliyordu. Font
pakete girdiği için artık internet de gerekmiyor.

Bunun dışında **macOS kullanıyorsan** bu sürümde yeni bir özellik yok: 0.3.0'ın
geri kalanı tamamen Windows'u ayağa kaldırmakla ilgili.

**Windows tarafında neler var:**

- **Görsellerin `%LOCALAPPDATA%\Lumeo\` altında** duruyor (yani
  `C:\Users\<kullanıcı adın>\AppData\Local\...`). Bilerek `Local`, `Roaming`
  değil: `Roaming` olsaydı ürettiğin bütün görseller kurumsal profille birlikte
  ağ üzerinden taşınmaya çalışırdı.
- **Azure anahtarın yalnız senin hesabına açık.** Windows, macOS'taki `0600`
  izin bitlerini uygulamıyor; onun yerine dosyanın erişim listesi (DACL)
  sıkılaştırılıyor — kalıtım kesiliyor ve listede yalnız senin hesabın kalıyor.
  Kendin görmek istersen KURULUM.md'de `icacls` komutu yazılı.
- **Türkçe karakterler bozulmuyor.** "Zümrüt" gibi bir klasör ya da prompt adı,
  geçmiş listelenirken bozuk karakterlere dönüşüp listeyi çökertebilirdi
  (Türkçe Windows'un varsayılan kodlaması cp1254). Okuma yolu utf-8'e sabitlendi
  ve bu bir daha olmasın diye kodun tamamını tarayan bir test eklendi.
- **Damlalık çalışıyor.** Renk seçici, Windows'ta tarayıcının kendi damlalığını
  kullanıyor.
- **Açılışta bir şey ters giderse artık sessiz kalmıyor**, ne olduğunu söyleyen
  bir pencere gösteriyor. (Öncesinde paketlenmiş uygulamanın yazacak bir yeri
  olmadığı için hata hiç görünmeden kayboluyordu.)

> **Not:** Sana ulaşan `.zip`, kendi sistemin için ayrı ayrı üretiliyor ve
> ikisinden **biri bile** üretilemezse yayın hiç oluşmuyor — yani elinde
> "yarım" bir sürüm kalmıyor.

## Sürüm numarası neden 1.16'dan 0.3'e "düştü"?

Uygulaman geri gitmedi: **0.3.0, elindeki 1.16.0'dan yenidir.**

Numaralandırma bir kez sıfırlandı. 1.x sayaçları iç geliştirme sayaçlarıydı;
uygulama GitHub'da açık kaynak (MIT lisanslı) hâle gelirken sürüm numarası
ürünün gerçek olgunluğunu gösterecek şekilde **0.2.0**'dan yeniden başlatıldı.
Arada arayüz turları için 2.x'e kadar çıkmış numaralar da vardı; onlar da aynı
sıfırlamaya girdi.

Kısacası doğru sıra şu: `1.16.0` → **`0.2.0`** → `0.2.1` → **`0.3.0`** (bugün).
Hangi sürümde olduğunu ⚙ Ayarlar'ın altındaki **Sürüm** satırından görürsün;
Kurum'nın söylediği numarayla karşılaştır, büyüklük-küçüklük kıyaslama.

## Sürüm 0.2.1'de ne değişti

Hepsi **Medya** ve **sohbet** tarafında, gündelik kullanımı hızlandıran şeyler:

- **Klasörde arama.** Prompt, boyut ya da klasör adına göre anında süzüyorsun.
- **Izgara boyutu S / M / L.** Küçük karolarla çok görsel, büyük karolarla
  detay.
- **Klasörü ZIP olarak indir.** Klasör başlığındaki indirme düğmesi, alt
  klasörleriyle birlikte hepsini tek dosyada veriyor. Türkçe klasör adları da
  dosya adında doğru çıkıyor.
- **Sürükle-bırak.** Görselleri klasör kartlarının üstüne sürükleyerek
  taşıyorsun; bilgisayarından bir dosya bırakarak içe aktarıyorsun.
- **Ürettiğin görselden referans alma.** Bir sonuca "Referans" deyip onun
  üstünden yeni görsel üretiyorsun.
- **Sohbette mesaj düzenleme ve kopyalama.** Gönderdiğin bir mesajı yazı
  kutusuna geri alıp düzeltebiliyor, herhangi bir mesajı tek tıkla
  kopyalayabiliyorsun. Gönderdiğin an kutu kendiliğinden temizleniyor (ağ
  hatasında yazdığın geri geliyor).
- **Büyüteç dışına tıklayınca kapanıyor.**

## Sürüm 0.2.0'da ne değişti

Bu sürüm, 1.16.0'dan sonraki **arayüz devrini** getiriyor — uygulamayı açtığında
göreceğin en büyük fark burada.

- **Sekmeler kalktı, tek pencere kaldı.** Eskiden "Görsel" ve "Prompt Yönetmeni"
  diye iki sekme vardı ve prompt'u birinden ötekine taşıyordun. Artık **tek bir
  yazı kutusu** var; modu değiştiriyorsun, kutuda yazdığın metin yerinde
  kalıyor. Yönetmenin yazdığı prompt'u "Görsel modunda üret" ile doğrudan
  üretiyorsun, sekme yolculuğu yok.
- **Sohbet ve üretilen görseller aynı dökümde.** Konuşma ve sonuçlar tek bir
  akışta, sırayla akıyor.
- **Sol şerit:** Stüdyo · Medya · Kütüphane · Araçlar.
- **Medya görünümü:** iç içe klasörler, kırıntı gezintisi, klasör kartlarında
  kapak görseli, sıralama ve klasör yeniden adlandırma.
- **Kütüphane:** logolar, mottolar, bannerlar ve **yüklemeler**.
- **Tema seçici ve teması artık kalıcı:** Mono, Ocean, Amber, Viola. Seçtiğin
  tema uygulamayı kapatıp açtığında da duruyor.
- **Güvenlik:** API anahtarların hiçbir ekran yanıtında ve hiçbir hata kaydında
  görünmüyor — hata günlüğüne düşse bile otomatik sansürleniyor.
- **Uygulama açık kaynak oldu** (MIT lisansı, GitHub).

---

# Daha eski sürümler

## Sürüm 1.16.0'da ne değişti

Prompt Yönetmeni'nin tamamı bu sürümde elden geçti: artık daha sade prompt
yazıyor, varyasyonları tıklanabilir hâle geldi ve sohbet dışı sorulara cevap
vermiyor.

- **Varyasyonlar tek tıkla uygulanıyor.** Eskiden "A — Serin ve kurumsal: şunu
  şununla değiştir" diye yazıyordu ve prompt'u **elle** düzeltmen gerekiyordu.
  Artık varyasyonlar düğme: birine bastığında yönetmen prompt'u ona göre baştan
  yazıyor. Yarım dakikayı bulabilir, çünkü gerçekten yeniden yazıyor — yerinde
  kelime değiştirmiyor. Sebebi şu: varyasyonların çoğu tek kelime değişikliği
  değil ("fotoğraf üslubuna çevir" gibi), ve yerinde değiştirme tutmadığında
  sana hiç seçmediğin bir prompt verirdi.
- **Ayarlanabilir parametreler de tıklanabilir.** Işık, palet, kadraj gibi
  eksenler artık seçenek düğmeleri hâlinde geliyor; yanında **kendi fikrini
  yazabileceğin bir alan** var. Birkaç ekseni birlikte seçip tek "Uygula" ile
  gönderiyorsun. Her eksenin yanında şu an prompt'ta duran ifade yazılı, yani
  neyi takas ettiğini görüyorsun.
- **Seçimlerin artık senin yazdığın mesaj gibi görünmüyor.** Çiplerden seçip
  "Devam et"e bastığında akışta `Instagram karesi · Blog kapağı` diye bir
  baloncuk çıkıyordu — sanki sen yazmışsın gibi. Artık orada sessiz, küçük bir
  **SEÇİM** etiketi var. Kaydedilmiş sohbeti tekrar açtığında da öyle kalıyor.
- **Promptlar sadeleşti.** Yönetmene "en az 60 kelime yaz" diyen bir kural
  vardı; sen iki cümlelik bir fikir söylediğinde bile aradaki boşluğu **uydurma
  ayrıntıyla** doldurmak zorunda kalıyordu (senin hiç istemediğin ışık, doku,
  film graini). O kural kalktı: artık prompt'un uzunluğunu senin anlattığın
  belirliyor. Az anlatırsan kısa, çok anlatırsan uzun olur — ama uydurma
  ayrıntı girmez. Kısa prompt eksik prompt değil; yazılmayan her şeyi model
  kendi kararıyla iyi dolduruyor.
- **Yönetmen artık sohbet asistanı değil.** Şiir, kod, genel bilgi ya da alakasız
  bir soru sorarsan tek cümleyle "ben yalnızca görsel prompt'u hazırlıyorum"
  diyor. Prompt'la ilgili her şey hâlâ işinin içinde: "bu prompt'u Türkçe
  açıklar mısın", "görsel neden bulanık çıktı", "story için hangi oran" —
  hepsine cevap veriyor.
- **Yanlış bilgiler temizlendi.** Yönetmen sana olgu gibi söylediği ama
  doğrulanamayan birkaç şey biliyordu — en kötüsü "Türkçe desteklenen diller
  listesinde yok" iddiasıydı; öyle bir liste hiç yok. Türkçe karakterlerin
  bozulabildiği uyarısı ve üç pratik çaresi duruyor.

## Sürüm 1.15.1'de ne değişti

Yeni özellik yok; 1.15.0'ın kod incelemesinde çıkan pürüzler kapatıldı.

- **Prompt kutusu artık kaçmıyor.** Sağ alt köşesinden çekerek büyütürken kutu
  sağa doğru ekrandan taşabiliyor ve **bir daha geri çekilemiyordu.** Artık
  yalnızca aşağı-yukarı büyüyor, sütununun dışına çıkmıyor ve çok uzayıp
  altındaki düğmeleri görüş alanından çıkarmıyor. Sohbetteki mesaj kutusu için
  de aynı.
- **Uzun sohbetlerin son turu da kaydediliyor.** Sohbet sınıra yaklaştığında
  turun son yanıtı diske yazılamıyor, sohbet listede güncel görünüp bir tur
  geride kalıyordu.
- **Yönetmenin uzun bir yanıtı sohbeti kilitlemiyor.** Beklenenden uzun gelen
  bir yanıttan sonra sohbet ne devam ediyor ne kaydediliyordu; artık ya normal
  çalışıyor ya da ne olduğunu Türkçe söyleyen bir hata veriyor.
- **Sohbet listesi doğru sırada.** En son konuştuğun sohbet en üstte: eskiden
  satırda "bugün 14:32" yazarken sohbet listenin dibinde kalabiliyordu.
- **Klavyeyle gezinme.** Sol paneldeki düğmelerde ve seçenek çiplerinde odak
  çerçevesi görünüyor; ⋯ menüsü Esc ile kapanınca imleç geldiği düğmeye dönüyor.

## Sürüm 1.15.0'da ne değişti

Hepsi **Prompt Yönetmeni** sekmesinde:

- **Yönetmenin sorduğu seçenekler artık tıklanabilir.** Soru sorduğunda altında
  düğmeler çıkıyor: birden fazlasını seçebiliyorsun, en altta da **"Kendi
  fikrim"** kutusu var (listede olmayan bir cevabı oraya yazıyorsun). **Devam
  et**'e basınca seçtiklerin ve yazdığın tek mesaj olarak gidiyor — elle
  yazmaya gerek kalmıyor.
- **Prompt artık okunuyor.** Prompt metni satır sonuna gelince alt satıra
  geçiyor (eskiden tek satır halinde yana kayıyordu) ve **Kopyala** ile **Forma
  aktar** düğmeleri prompt'un **hemen üstünde** duruyor — mesajın en altında
  değil.
- **Sohbetler kaydediliyor.** Solda bir liste var: **+ Yeni sohbet** ile temiz
  bir sayfa açıyorsun, eski sohbetlere tıklayarak dönüyorsun. Uygulamayı
  kapatıp açsan da yerlerinde duruyorlar. Her satırın sağındaki **⋯**
  düğmesinden **Yeniden adlandır** ya da **Sil**. Sohbet adını uygulama ilk
  mesajından kendisi türetiyor.
  - "Sohbeti temizle" düğmesi **kalktı**: işini "Yeni sohbet" ve "Sil"
    devraldı.
  - Sohbetler de sürüm değişimindeki otomatik yedeğe dahil (aşağıya bak).
  - Dar pencerede liste soldan gizleniyor, üstteki **Sohbetler** düğmesiyle
    açılıyor.
- **Kimin konuştuğu bir bakışta belli.** Senin yazdıkların ve yönetmenin
  yanıtları farklı zeminde duruyor.
- **Sekmeler bitişik** ve aralarında geçiş yaparken sayfa yumuşakça kayıyor.

## Sürüm 1.13.0'da ne değişti

- **Prompt Yönetmeni geldi.** Uygulamanın üstünde artık iki sekme var: **Görsel**
  ve **Prompt Yönetmeni**. İkincisi bir sohbet: ne istediğini **Türkçe** anlatıyorsun,
  o da eksik kalan yerleri soruyor (en fazla 3 soru) ve sonunda görsel modelin en
  iyi anladığı **İngilizce prompt'u** + boyut/kalite/adet önerisini yazıyor.
  - **"Forma aktar"** düğmesi prompt'u Görsel sekmesindeki prompt alanına yazıyor
    ve ayarları uyguluyor — sen yalnızca **Üret**'e basıyorsun. Üretimi kendisi
    başlatmıyor (para harcayan adımı sen onaylıyorsun).
  - Önerdiği bir ayar formda yoksa **söylüyor** ("… uygulanamadı"), sessizce
    başka bir ayarla üretmiyor.
  - Sohbet **kaydedilmiyor**: uygulamayı kapatınca gider. Kalıcı olan, üretilen
    görselin prompt'u (o zaten geçmişte duruyor). "Sohbeti temizle" onay soruyor.
  - Kullanmak için **bir kerelik** ayar gerekiyor: ⚙ **Ayarlar** → *Prompt Yönetmeni
    (sohbet modeli)* → **Dağıtım adı** (Kurum verecek, ör. `gpt-5.6-luna`) → **Kaydet**.
    Girilmezse sekme açılır ama "Gönder" kilitli kalır ve nedeni panelde yazar.
  - Azure anahtarını **yeniden girmen gerekmiyor**; sohbet görselinkini kullanıyor.
- **Ayarlar kaydetmek artık başka ayarları silmiyor.** Endpoint'i tek başına
  güncellediğinde dağıtım adı yerinde kalıyor.

> Not: Bu dosya 1.11 ve 1.12 sürümlerini atlıyor — o sürümlerin notları yazılmadı
> (1.11: logo ince konum + damlalık + paletten renk çıkarma, 1.12: bilgisayardan
> sürükle-bırak ile içe aktarma). Eksiklik bilinçli olarak burada duruyor, sessizce
> yeniden yazılmadı.

## Sürüm 1.10.0'da ne değişti

- **"İndir" artık gerçekten indiriyor.** Önceki sürümde İndir'e basınca dosya
  kaydedilmiyor, görselin büyük hâli uygulamanın yerine açılıyor ve geri dönüş
  yolu kalmıyordu. Artık macOS'un **kaydetme penceresi** açılıyor; klasör olarak
  **İndirilenler (Downloads)** hazır geliyor, dosya adı da dolu geliyor. Başka
  bir klasör seçmek istersen o pencereden seçebilirsin.
- **Görsele tıklayınca büyüyor.** Ortadaki görsele tıkla → tam ekran açılır.
  Orada:
  - fare tekerleği ya da trackpad'de **iki parmakla kıstırma** → yakınlaştır /
    uzaklaştır (imlecin durduğu yere doğru),
  - **çift tıklama** → büyüt / sığdır arası geçiş,
  - büyütülmüşken **sürükle** → görselin içinde gezin,
  - alttaki şeritten **Sığdır** ile başa dön, **İndir** ile kaydet,
  - **Esc** ya da **×** ile kapat.

---

## Yedek nerede

Uygulama, sürüm değiştiğinde listelerinin bir kopyasını kendiliğinden alıyor:

| Sistem | Yedek klasörü |
|---|---|
| macOS | `~/Library/Application Support/Lumeo/backups/<sürüm>-<tarih>/` |
| Windows | `%LOCALAPPDATA%\Lumeo\backups\<sürüm>-<tarih>\` |

İçinde yalnızca küçük liste dosyaları var (geçmiş, klasörler, paletler, kayıtlı
sohbetler, logo kütüphanesi) — **görseller kopyalanmıyor**, onlar zaten
yerlerinde duruyor.
Birkaç KB tutar, silmen gerekmez.

Geri yüklemek gerekirse (Kurum söylerse): o klasörün içindeki `output` ve `assets`
klasörlerini bir üstteki `Lumeo` klasöründeki aynı adlı klasörlerin
üstüne sürükle.

## Sorun çıkarsa

- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **Uygulama hiç açılmıyor:** hata kaydını Kurum'ya gönder —
  macOS'ta `~/Library/Application Support/Lumeo/hata.log`,
  Windows'ta `%LOCALAPPDATA%\Lumeo\hata.log`.
- **(Windows) Pencere hiç gelmiyor:** `.exe`'yi `_internal` klasöründen ayırmış
  olabilirsin — ikisi aynı klasörde olmalı (2. adım).
- **Eski arayüzü görüyorum gibi:** uygulamayı tamamen kapat (macOS'ta ⌘Q) ve
  yeniden aç.
- **Geçmişim boş görünüyor:** hiçbir şey silme, Kurum'ya yaz — yukarıdaki yedek
  klasörü duruyor.
