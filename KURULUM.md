# GPT-Image Studio — Kurulum (macOS)

Bilgisayarına Python veya başka bir şey kurman gerekmiyor. 5 dakika sürer.

Not: Bu belge, sana ulaşan `.zip`'in Apple Silicon Mac'in için ayrıca (GitHub
Actions'ın arm64 runner'ında) üretildiğini varsayar — geliştirme makinesinde
yerel olarak alınan x86_64 derlemesi yalnızca paketleme yolunu sınamak için,
sana gönderilen paket değildir.

## 1. Uygulamayı yerine koy
1. `GPT-Image Studio.zip` dosyasına çift tıkla — yanında `GPT-Image Studio` uygulaması çıkar.
2. Çıkan uygulamayı **Programlar (Applications)** klasörüne sürükle.

## 2. İlk açılış — bir kerelik güvenlik izni
Uygulama Apple'a ücretli geliştirici kaydıyla imzalanmadığı için (ad-hoc imza —
bkz. altta), macOS ilk açılışta soru soruyor. Bir kez izin verirsin, sonraki
açılışlarda sormaz. *Not:* Bu zip Apple Silicon Mac'in için derlendiğinden (arm64
native), Rosetta çevirisi yapılmaz.

1. Uygulamaya çift tıkla. Uygulama **açılmayacak** ve şu uyarı çıkacak:

   > **"GPT-Image Studio" Açılmadı**
   > Apple, "GPT-Image Studio" uygulamasının Mac'ine zarar verebilecek ya da
   > gizliliğini tehlikeye atabilecek kötücül yazılım içermediğini doğrulayamadı.
   >
   > *(İngilizce sistemde: "GPT-Image Studio" Not Opened — Apple could not verify
   > "GPT-Image Studio" is free of malware…)*

   ⚠️ **"Çöp Sepetine Taşı" (Move to Trash) düğmesine BASMA** — uygulamayı siler.
   **Bitti** (Done) düğmesine bas. Bu uyarı normaldir: uygulama Apple'a ücretli
   geliştirici kaydıyla imzalanmadığı için macOS onu tanımıyor, bir sorun
   olduğu anlamına gelmiyor.
2. Ekranın sol üstündeki **Apple menüsü** → **Sistem Ayarları** → **Gizlilik ve Güvenlik**.
3. Sayfayı aşağı kaydır: *"GPT-Image Studio engellendi"* satırını bul → **Yine de Aç**.
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir (ya da Touch ID).
5. Uygulama açılır. Bir daha sormaz.

<!-- Adım 1'in uyarı metni 2026-07-29'da gerçek bir quarantine bayrağıyla
(zip'ten çıkarılmış temiz kopya, flags=0001) gözle doğrulandı; İngilizce sistemde
görülen metin yukarıda. TODO(insan): Türkçe sistemdeki birebir metin ve adım
2-4'ün ekran görüntüleri hâlâ eksik. -->


## 3. Azure kimliğini gir
İlk açılışta Ayarlar penceresi kendiliğinden açılır ve "Üret" düğmesi kilitlidir.
1. **Endpoint** ve **API key** alanlarını Kurum'dan aldığın bilgilerle doldur.
2. **Kaydet**. Kilit açılır.

Key bilgisayarında `~/.config/gpt-image-studio/credentials.env` dosyasında, yalnız
senin okuyabileceğin izinle saklanır ve bir daha ekranda gösterilmez.

## 4. Kullan
Prompt yaz → **Üret**. Ürettiğin görseller bilgisayarında
`~/Library/Application Support/GPT-Image Studio/output/` altında saklanır;
uygulamayı kapatıp açsan da geçmişin durur.

## Sorun çıkarsa
- **Pencere boş açılıyor:** uygulamayı kapat, tekrar aç.
- **"Üret" kilitli:** Ayarlar (dişli) → endpoint + key girilmiş mi?
- **Görsel üretilmiyor, hata mesajı çıkıyor:** key süresi/rotasyonu için Kurum'ya yaz.
