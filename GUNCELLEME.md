# GPT-Image Studio — Güncelleme (macOS)

Kurum sana yeni bir `GPT-Image Studio.zip` gönderdiğinde bu sayfayı izle. 3 dakika sürer.

> ## 🛑 En önemli iki şey
>
> 1. **`Application Support` klasörünü SİLME.** Ürettiğin bütün görseller, geçmiş,
>    klasörler, paletler ve logo kütüphanen orada duruyor. Uygulamayı değiştirmek
>    onlara dokunmaz — ama "uygulamayla ilgili her şeyi silelim" diyip o klasörü
>    silersen **hepsi gider.** Uygulamayı değiştirmek için o klasöre hiç girmen
>    gerekmiyor.
> 2. **Güvenlik uyarısında "Çöp Sepetine Taşı"ya ve Enter'a BASMA** (aşağıda 3. adım).
>    O düğme mavi/varsayılan olduğu için Enter uygulamayı siler.

## 1. Uygulamayı kapat

Uygulama açıksa **kapat** (⌘Q ya da pencereyi kapat). Çalışırken değiştirmeye
çalışmak yarım kurulmuş bir uygulama bırakabilir.

## 2. Yenisini yerine koy

1. Yeni `GPT-Image Studio.zip` dosyasına çift tıkla — yanında uygulama çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.
3. macOS *"Aynı adda bir öge var"* diye soracak → **Değiştir** (Replace) de.

Eski sürümü önceden silmen gerekmiyor; değiştirmek yeterli.

## 3. Güvenlik izni — her güncellemede TEKRAR gerekiyor

Bu bir hata değil, beklenen davranış: uygulama Apple'a ücretli geliştirici
kaydıyla imzalanmadığı için (imza geçerli, yalnız Apple onayı yok), macOS her
**yeni** dosyayı ilk açılışta yeniden soruyor. Kurulumdaki adımların aynısı:

1. Uygulamaya çift tıkla. Uygulama **açılmayacak** ve şu uyarı çıkacak:

   > **"GPT-Image Studio" Not Opened**
   > Apple could not verify "GPT-Image Studio" is free of malware that may harm
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
3. Sayfayı aşağı kaydır: *"GPT-Image Studio engellendi"* / *"was blocked"*
   satırını bul → **Yine de Aç** (**Open Anyway**).
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir (ya da Touch ID).
5. Uygulama açılır. Bu sürüm için bir daha sormaz.

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

## Yedek nerede

Uygulama, sürüm değiştiğinde listelerinin bir kopyasını kendiliğinden alıyor:

```
~/Library/Application Support/GPT-Image Studio/backups/<sürüm>-<tarih>/
```

İçinde yalnızca küçük liste dosyaları var (geçmiş, klasörler, paletler, logo
kütüphanesi) — **görseller kopyalanmıyor**, onlar zaten yerlerinde duruyor.
Birkaç KB tutar, silmen gerekmez.

Geri yüklemek gerekirse (Kurum söylerse): o klasörün içindeki `output` ve `assets`
klasörlerini bir üstteki `GPT-Image Studio` klasöründeki aynı adlı klasörlerin
üstüne sürükle.

## Sorun çıkarsa

- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **Uygulama hiç açılmıyor:** `~/Library/Application Support/GPT-Image Studio/`
  içindeki `hata.log` dosyasını Kurum'ya gönder.
- **Eski arayüzü görüyorum gibi:** uygulamayı tamamen kapat (⌘Q) ve yeniden aç.
- **Geçmişim boş görünüyor:** hiçbir şey silme, Kurum'ya yaz — yukarıdaki yedek
  klasörü duruyor.
