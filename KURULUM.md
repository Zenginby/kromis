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
açılışlarda sormaz.

1. Uygulamaya çift tıkla. "açılamadı" uyarısı çıkacak — **Tamam**'a bas.
2. Ekranın sol üstündeki **Apple menüsü** → **Sistem Ayarları** → **Gizlilik ve Güvenlik**.
3. Sayfayı aşağı kaydır: *"GPT-Image Studio engellendi"* satırını bul → **Yine de Aç**.
4. Çıkan onayda tekrar **Yine de Aç** → Mac şifreni gir.

<!-- TODO(insan): Adım 2'nin gerçek ekran görüntülerini buraya ekle (Gatekeeper
akışını gözle doğrulayıp aldıktan sonra — bkz. task-6-report.md, Step 8 bu
oturumda atlandı çünkü quarantine bayrağı ve GUI etkileşimi ekran gerektiriyor). -->

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
