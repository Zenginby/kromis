# Kromis Studio — Güncelleme (macOS, Windows ve Android)

Elindeki uygulamayı yenisiyle değiştirmek için bu sayfayı izle. 3 dakika sürer.
(İlk kez kuruyorsan: [KURULUM.md](KURULUM.md).)

**Yeni sürüm çıktığını uygulama sana söylüyor:** **Ayarlar**'ı açtığında,
kurulu sürümün hemen altında *"Yeni sürüm çıktı"* satırı belirir. Aynı yerdeki
anahtarla bu kontrolü kapatabilirsin. Paketleri her zaman
[son yayın sayfasından](https://github.com/Zenginby/kromis/releases/latest)
da indirebilirsin — adres sabit, sürüm yükseldiğinde değişmiyor.

| Sistem | Dosya |
|---|---|
| macOS (Apple Silicon) | `kromis-macOS-arm64.zip` |
| Windows 10/11 (64-bit) | `kromis-windows-x64.zip` |
| Android 8.0+ (arm64) | `kromis-android-arm64.apk` |

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
>    | macOS | `~/Library/Application Support/Kromis/` |
>    | Windows | `%LOCALAPPDATA%\Kromis\` |
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

1. Yeni `kromis-macOS-arm64.zip` dosyasına çift tıkla — yanında
   uygulama çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.
3. macOS *"Aynı adda bir öge var"* diye soracak → **Değiştir** (Replace) de.

Eski sürümü önceden silmen gerekmiyor; değiştirmek yeterli.

### Windows

1. Yeni `kromis-windows-x64.zip` dosyasına **sağ tıkla → Özellikler**
   (Properties). En altta **Engellemeyi Kaldır** (Unblock) kutusu varsa
   işaretle → Uygula. **Ayıklamadan ÖNCE**, çünkü Windows'un "internetten indi"
   işareti ayıklarken çıkan her dosyaya kopyalanıyor ve uygulama açılmayabiliyor.
   Her güncellemede yeni bir zip indiğinden bu adım da her seferinde gerekiyor
   (3. adımdaki güvenlik izniyle aynı mantık).
2. Zip dosyasına sağ tıkla → **Tümünü ayıkla** (Extract All).
3. Çıkan `Kromis` klasörünü, eski klasörünün **bulunduğu yere** taşı.
4. Windows *"Hedefte aynı adda dosyalar var"* diye soracak → **Hedefteki
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

2. **Apple menüsü** → **Sistem Ayarları** (System Settings) → **Gizlilik ve
   Güvenlik** (Privacy & Security).
3. Sayfayı aşağı kaydır: *"Kromis engellendi"* / *"was blocked"*
   satırını bul → **Yine de Aç** (**Open Anyway**).
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir (ya da Touch ID).
5. Uygulama açılır. Bu sürüm için bir daha sormaz.

### Windows

1. `Kromis.exe`'ye çift tıkla. Mavi **SmartScreen** penceresi
   çıkabilir ("Windows bilgisayarınızı korudu").
2. **Daha fazla bilgi** (More info) → **Yine de çalıştır** (Run anyway).

   #### ✅ Burada YIKICI bir düğme YOK
   macOS'un aksine SmartScreen'deki düğmelerin hiçbiri dosyayı silmez veya
   karantinaya almaz. **Çalıştırma** yalnızca pencereyi kapatır, Enter'a basmak
   da güvenli — en kötüsü açılışı iptal eder.

## Android'i güncelleme

**Uygulamayı KALDIRMA.** Yeni APK'yı doğrudan eskisinin üzerine kur:

1. Yeni `kromis-android-arm64.apk` dosyasını telefona indir.
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
yeniden indir. Sürerse teknik desteğe yaz — **kaldırıp yeniden kurma**, önce sor.

## 4. Güncellendiğini doğrula

Sağ üstteki **Ayarlar** düğmesine bas — pencerenin altında **Sürüm** yazıyor.
Yayın sayfasındaki en son numarayla aynıysa güncelleme geçmiş demektir. Destek
isterken de bu numarayı söyle.

## 5. Kontrol et: her şey yerinde mi

- **Geçmişin** (ürettiğin görseller), **klasörlerin**, **paletlerin** ve **logo
  kütüphanen** olduğu gibi duruyor olmalı.
- **Azure anahtarını yeniden girmen gerekmez** — o uygulamanın içinde değil,
  ayrı bir yerde duruyor.

Bir şey eksik görünüyorsa **uygulamayı kullanmaya devam etme** ve teknik desteğe yaz
(aşağıdaki yedek işine yarayabilir).

## Uygulamanın adı değiştiyse — bir kerelik geçiş

Uygulamanın adı **Kromis Studio** oldu. Eski adla kurduğun bir sürümden
geliyorsan bu bölüm bir kez okunur, sonra hiç gerekmez.

**macOS ve Windows'ta hiçbir şey yapmıyorsun.** Yeni sürüm ilk açılışta eski
veri klasörünü yeni ada KENDİSİ taşıyor: geçmişin, klasörlerin, paletlerin,
logo kütüphanen ve Azure anahtarın olduğu gibi geliyor. Taşıma yalnız yeni
klasör henüz yoksa (ya da boşsa) yapılıyor ve **hiçbir şey silinmiyor** — eski
klasör bir aksilik olursa yerinde durur. Taşıma yapılamazsa uygulama yine
açılır ve sebebi `hata.log`'a yazılır.

| Sistem | Taşınan |
|---|---|
| macOS | `~/Library/Application Support/<eski ad>/` → `.../Kromis/` |
| Windows | `%LOCALAPPDATA%\<eski ad>\` → `%LOCALAPPDATA%\Kromis\` |
| Her ikisi | `~/.config/<eski ad>/credentials.env` → `~/.config/kromis/credentials.env` |

İşi bittikten sonra bilgisayarındaki eski **uygulama** klasörünü (`.app` ya da
`.exe`'nin durduğu klasör) elle silebilirsin; veri klasörü artık `Kromis`
adında.

**Android'de yeni APK'yı elle kurman ve eskisini elle kaldırman gerekiyor.**
Yeni uygulama eskisinin ÜZERİNE yazmaz, **yan yana** kurulur (paket kimliği ve
imza anahtarı değişti — Android bunları farklı iki uygulama sayar). Bunun iki
sonucu var:

- Eski uygulamanın kendi içindeki veri (Azure anahtarı dahil) yeni uygulamaya
  **geçmez ve okunamaz**; eski uygulamayı kaldırmak o veriyi siler. Azure
  kimliğini yeni uygulamada bir kez daha girmen gerekiyor (masaüstünde
  gerekmiyor).
- **Telefona indirdiğin görseller yerinde kalıyor:** `Resimler/` altındaki eski
  adlı klasör olduğu gibi duruyor, silinmiyor. Yeni indirmeler
  `Resimler/Kromis` altına iniyor.

---

## Sürüm 0.17.3 — ne değişti

- bos bir sir "sir yok" diye bildiriliyordu
- Merge origin/main (v0.17.2) into chore/kromis-yeniden-adlandirma
- logo fixture DOSYA adlarinda kalan eski kurum izi

---

## Sürüm 0.17.2 — ne değişti

- Küçük düzeltmeler ve iyileştirmeler.

---

## Sürüm 0.17.1 — ne değişti

- windows simgesi ve favicon icin coklu cozunurluk destegi

---

## Sürüm 0.17.0 — ne değişti

- video prompt'u, uretim hafizasi ve model-farkindalikli yonlendirme

---

## Sürüm 0.16.0 — ne değişti

- tur suzgeci -- tumu, gorsel, video, yuklenen

---

## Sürüm 0.15.0 — ne değişti

- asgari Python 3.13 -- 45 sebepsiz kirmizinin gercek sebebi
- SyntaxWarning kapisi worktree kopyalarini kaynak sayiyordu
- ham olmayan docstring'in doğurduğu SyntaxWarning ve depo geneli kapısı
- yanlis "en ucuz" iddiasi, MAI tek-referans aciklamasi ve mandali
- FLUX.2 adaptoru, iki katalog girdisi ve detail_of liste dali
- MAI-Image adaptoru ve uc katalog girdisi
- azure_foundry kimligi, host turetme tablosu ve adres alani

---

## Sürüm 0.14.0 — ne değişti

- incelemenin bulduğu on gerileme — hap, oran, son kare akışı
- başlangıç + bitiş karesi ile geçiş üretimi
- ayar sayfasındaki üç denetim video modunda ölüydü
- mobilde video ne oynatılıyor ne de karosuna sığıyordu
- node'un soğuk açılışı Windows yayınını kırdı — sınır 10 sn'den 60'a

---

## Sürüm 0.13.1 — ne değişti

- CI açılış kapısını kendi kusuru düşürüyordu — guilib ad çakışması
- kod denetiminin dört bulgusu — üçü sessiz yalan, biri gürültü
- indirilen paket hiç açılmıyordu — .NET köprüsü + açılış kapısı

---

## Sürüm 0.13.0 — ne değişti

- Video üretimi geldi: composer'ın üçüncü modu (Görsel · Video · Yönetmen). Metinden video üretebiliyor ya da galerideki bir görseli tek tıkla canlandırabiliyorsun; model Gemini · Veo 3.1'in üç kademesi (Lite · Fast · tam) ve anahtar zaten girdiğin Gemini anahtarı — Ayarlar'a yeni bir alan gelmedi. Yeni ayar SÜRE (4, 6 ya da 8 saniye) ve kredi tahmini süreyle çarpılıyor, çünkü video tarifesi saniye başına. Üretilen video geçmişe kaydediliyor, Medya'da oynatılabiliyor, büyüteçte tam ekran açılıyor ve .mp4 olarak indirilebiliyor. NOT: video üretimi 1-6 dakika sürüyor ve o süre boyunca sekmeyi açık bırakmalısın; ayrıca Veo'nun ücretsiz kademesi YOK — Gemini anahtarının bağlı olduğu projede faturalandırma açık olmak zorunda.

---

## Sürüm 0.12.0 — ne değişti

- Prompt Yonetmeni elden gecti: oneriler artik kisa brief'lerde de tukenmiyor (yonetmen prompt'ta hic gecmeyen bir ekseni de onerebiliyor ve o kelime prompt'a ancak sen cipe tikladiginda giriyor), her secenegin altinda ne yaptigini anlatan bir aciklama ve renk/oran seceneklerinde kredi harcamadan cizilmis bir ornek var, Yonetmen modundaki yeni "Yonetmen ayarlari" cekmecesine yazdigin kalici yonlendirme her turda gecerli oluyor ve yonetmen artik secili gorsel modelini gordugu icin o modelde gecerli olmayan bir boyut ya da kalite onermiyor.

---

## Sürüm 0.11.8 — ne değişti

- klasör adı yalnız en yakın klasörde eşleşiyordu
- logo önizlemesi dikey tabanda kutusunu taşırıp kırpılıyordu

---

## Sürüm 0.11.7 — ne değişti

- İnceleme bulguları: küçülme çapası, boşa dönen bekçi, eksen metni, ikinci kısayol
- Stüdyo sadeleşti: az metin, yalnız kullanılabilir modeller, küçülen composer
- Tur J teslim edildi, kuyruğun başına kullanıcı bulgusu geçti

---

## Sürüm 0.11.6 — ne değişti

- kapının sentetik koşusu Windows'ta hiçbir şey ölçmüyordu
- üç küçük borç, üçü de ölçülerek kapandı

---

## Sürüm 0.11.5 — ne değişti

- İnceleme düzeltmeleri (seçici): üst zincir sıfırlanıyordu, kapanışta odak düşüyordu, rozet ekran okuyucuya ulaşmıyordu
- klavye kullanıcısı seçim yapınca yerini kaybediyordu; künye iç içe klasörün tam yolunu yazıyor

---

## Sürüm 0.11.4 — ne değişti

- büyeteçte "Logo ekle" yok, klasöre aktarma iki yerde kırık

---

## Sürüm 0.11.3 — ne değişti

- çoklu seçimin sonucu ClipData'dan okunuyor — "Bitti" artık yükleme başlatıyor

---

## Sürüm 0.11.2 — ne değişti

- telefonda yükleme iki yerde kapıda düşüyordu — seçici süzgeci ve MIME

---

## Sürüm 0.11.1 — ne değişti

- yüklenen logo kullanılamaz türe gidiyordu, ek görsel sessizce düşüyordu

---

## Sürüm 0.11.0 — ne değişti

- masaüstü sunucusuna istek kaynağı kapısı (netguard)
- klasör adı yanıt başlığına satır sonu sokabiliyordu

---

## Sürüm 0.10.0 — ne değişti

- İnceleme düzeltmeleri (arena): kapı, geri açma, kilit sızıntısı, çipin ARIA'sı
- aynı prompt 2-4 modelde yan yana, kazanan işaretlenebiliyor

---

## Sürüm 0.9.2 — ne değişti

- İnceleme düzeltmeleri: paketleme kapısı, sızıntı kapısı, harita kör noktası, çipin adı

---

## Sürüm 0.9.1 — ne değişti

- Stüdyo bekleme animasyonu: shimmer kutusu, uydurma yüzde kalktı

---

## Sürüm 0.9.0 — ne değişti

- model seçimi alttan açılan panele taşındı, Ayarlar da aynı yüzeye
- CLAUDE.md kök belge mandalına girdi, üreticinin kaçış dizisi düzeltildi
- depo grafları üretiliyor, commit'leniyor ve bir kapıyla taze tutuluyor

---

## Sürüm 0.8.2 — ne değişti

- medya seçicide görsel ekranı kaplamıyor, üstteki karolar seçilebiliyor

---

## Sürüm 0.8.1 — ne değişti

- §11 mandallarının delikleri kapandı, Ayarlar düğmesi tek adla anlatılıyor
- composer alt satırında ipucu tek satırda kalıyor
- tasarım ölçütünün iki ihlali kapandı — emoji ve vurgu renkli sol kenar

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

- depo adresi yeni hesaba çevrildi (eski hesap → Zenginby)

---

## Sürüm 0.5.2 — ne değişti

- indirme Android'de köprüden geçsin + geri tuşu bulguları

---

## Sürüm 0.5.1 — ne değişti

- telefonda S ile M ızgara boyutu aynı görünmesin

---

## Sürüm 0.5.0 — ne değişti

- Yeni sürüm çıktığında uygulama artık kendisi haber veriyor — Ayarlar'da, kurulu sürümün hemen altında.

---

## Sürüm 0.4.2 — ne değişti

**Manşet: uygulama yeniden adlandırıldı.** Simge de yenilendi. Adı değişti diye
hiçbir şeyini kaybetmiyorsun — görsellerin, geçmişin, klasörlerin ve paletlerin
olduğu gibi duruyor.

- **Telefonda üç arayüz kusuru düzeltildi.** Dar ekranda bozulan yerleşim ve
  dokunmayla ulaşılamayan iki düğme çalışır hâle geldi.
- **README'deki indirme bağlantıları çalışıyor.** Üç bağlantı da her zaman en
  son yayına işaret ediyor; sürüm yükseldiğinde adresi değiştirmek gerekmiyor.
- **Android paketinin adı düzeltildi.** Telefona kurulacak dosya artık
  uygulama adını taşıyan bir dosya adıyla geliyor.

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

- **Görsellerin `%LOCALAPPDATA%\Kromis\` altında** duruyor (yani
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
Hangi sürümde olduğunu Ayarlar'ın altındaki **Sürüm** satırından görürsün;
yayın sayfasındaki numarayla karşılaştır, büyüklük-küçüklük kıyaslama.

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
  - Kullanmak için **bir kerelik** ayar gerekiyor: **Ayarlar** → *Prompt Yönetmeni
    (sohbet modeli)* → **Dağıtım adı** (Azure'daki dağıtımının adı, ör.
    `gpt-5.6-luna`) → **Kaydet**.
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
| macOS | `~/Library/Application Support/Kromis/backups/<sürüm>-<tarih>/` |
| Windows | `%LOCALAPPDATA%\Kromis\backups\<sürüm>-<tarih>\` |

İçinde yalnızca küçük liste dosyaları var (geçmiş, klasörler, paletler, kayıtlı
sohbetler, logo kütüphanesi) — **görseller kopyalanmıyor**, onlar zaten
yerlerinde duruyor.
Birkaç KB tutar, silmen gerekmez.

Geri yüklemek gerekirse (teknik destek söylerse): o klasörün içindeki `output` ve `assets`
klasörlerini bir üstteki `Kromis` klasöründeki aynı adlı klasörlerin
üstüne sürükle.

## Sorun çıkarsa

- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **Uygulama hiç açılmıyor:** hata kaydını teknik desteğe gönder —
  macOS'ta `~/Library/Application Support/Kromis/hata.log`,
  Windows'ta `%LOCALAPPDATA%\Kromis\hata.log`.
- **(Windows) Pencere hiç gelmiyor:** iki olağan sebebi var. (a) `.exe`'yi
  `_internal` klasöründen ayırmış olabilirsin — ikisi aynı klasörde olmalı.
  (b) Zip'i **engellemesini kaldırmadan** ayıklamış olabilirsin (1. adım); o
  zaman zip'i baştan, 1. adımdan başlayarak yeniden ayıkla. Sebep hâlâ
  anlaşılmıyorsa `Kromis` klasöründe PowerShell açıp ön yükleme denetimini koştur
  ve çıkan raporu teknik desteğe gönder — komutlar ve çıkış kodlarının anlamı:
  [KURULUM.md → Sorun çıkarsa](KURULUM.md#sorun-çıkarsa). Özetle: paket
  pencere kipinde olduğu için kabuk exe'yi BEKLEMEZ, dosya bir iki saniye sonra
  oluşur; ve PowerShell'de yol `$env:LOCALAPPDATA\Kromis\...` diye yazılır.
- **Eski arayüzü görüyorum gibi:** uygulamayı tamamen kapat (macOS'ta ⌘Q) ve
  yeniden aç.
- **Geçmişim boş görünüyor:** hiçbir şey silme, teknik desteğe yaz — yukarıdaki yedek
  klasörü duruyor.
