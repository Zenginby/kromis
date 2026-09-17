# Kromis Studio

[![Release](https://img.shields.io/badge/version-v0.23.1-blue.svg)](https://github.com/Zenginby/kromis/releases/latest)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Build & Test](https://github.com/Zenginby/kromis/actions/workflows/release.yml/badge.svg)](https://github.com/Zenginby/kromis/actions)

**Kendi dilinde anlat, prompt'u uygulama yazsın.** Kromis Studio; görsel ve video
üretimini, görsel düzenlemeyi, renk paletini ve kurumsal logo/motto/banner
bindirmeyi tek pencerede toplar. Masaüstü uygulaması olarak da, bilgisayarındaki
yerel bir web sayfası olarak da aynı şeydir.

Anahtarlar senin (BYOK), üretilen her şey senin diskinde durur — arada bir
sunucu yok.

🇬🇧 [English](README.en.md) · 📦 [Kurulum](KURULUM.md) · 📖 [Tüm özellikler](docs/ozellikler.md)

![Kromis Studio — üretilen görsel stüdyo akışında](docs/gorseller/uretim-sonucu.png)

---

## 🚀 İndir

| Platform | Mimari | İndirme |
|---|---|---|
| 🍏 **macOS** | Apple Silicon (M1–M4) | [ZIP / ARM64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-macOS-arm64.zip) |
| 🪟 **Windows** | x64 (Windows 10 / 11) | [ZIP / x64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-windows-x64.zip) |
| 🤖 **Android** | arm64-v8a (Android 8.0+) | [APK / arm64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-android-arm64.apk) |

Bağlantılar her zaman **en son yayına** gider; sürüm yükselince adres değişmez.

> [!IMPORTANT]
> **Masaüstü ve Android paketleri v0.23.1'de donduruldu (2026-09-16).**
> Yukarıdaki paketler indirilebilir kalıyor ve çalışmaya devam ediyor: hepsi
> BYOK'tur (kendi anahtarın), hiçbir Kromis sunucusuna bağlanmaz, yani bir
> sunucunun kapanmasıyla bozulmaz. Ama bundan sonra otomatik yeni masaüstü ya
> da Android sürümü ÇIKMAYACAK; proje **web-first** ilerliyor — tarayıcıda
> çalışan, hesaplı ve kredili bir stüdyo. Yol haritası:
> [docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md](docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md),
> ilk adımların listesi: [docs/faz0-web-first.md](docs/faz0-web-first.md),
> veri tabanı ve hesaplar: [docs/faz1-veritabani-hesaplar.md](docs/faz1-veritabani-hesaplar.md).
> Masaüstü/Android bir gün geri gelirse web uygulamasını gösteren ince bir
> kabuk olarak gelir.

> [!TIP]
> Android sürümü Play Store'da değil, APK doğrudan kurulur — ve telefonda TAM
> çalışır: üretim, düzenleme, palet ve bindirme cihazdaki Python çalışma
> zamanında koşuyor. Güncellerken **uygulamayı silme, üzerine kur**; paketler
> aynı anahtarla imzalandığı için verin yerinde kalır.
>
> macOS Gatekeeper, Windows SmartScreen ve Android "bilinmeyen kaynak"
> adımlarının tamamı: [KURULUM.md](KURULUM.md).

---

## ✨ Güncel Özellikler (v0.23.1)

### Fikri kendi dilinde anlat, prompt'u Yönetmen yazsın

Ne istediğini gündelik dille yaz — **hangi dilde yazarsan o dilde cevap
alırsın**; sınır Yönetmen olarak seçtiğin sohbet modelinin desteklediği
dillerdir. Yönetmen bunu optimize edilmiş **İngilizce** bir prompt'a ve teknik
ayarlara (boyut, kalite, adet) çevirir; kararsız kaldığı yeri sana
**tıklanabilir seçeneklerle** sorar, varyasyon ve parametre ekseni önerir.
Beğendiğin prompt tek tuşla üretime gider.

Prompt'un İngilizce olması bir dil tercihi değil ölçülmüş bir davranış: aynı
sahne İngilizce tarif edildiğinde görsel modelleri belirgin biçimde daha sadık
çıktı veriyor. Türkçe (ya da başka bir dilde) prompt istersen Yönetmen onu da
verir, İngilizcesini yanına ekler.

### Arayüz dili: Türkçe ya da İngilizce

Ayarlar → **Dil / Language**. Seçim `prefs.json`'a yazılıyor, yani uygulamayı
kapatıp açınca yerinde duruyor. Arayüzün tamamı — menüler, durum satırları,
onay pencereleri ve hata mesajları — seçilen dilde geliyor. Belgeler ve
buradaki ekran görüntüleri Türkçe kalıyor.

**Ön tanımlı dil v0.22'den beri İngilizce.** Dilini daha önce seçmiş bir
kurulum etkilenmiyor (tercih diskte duruyor); hiç seçmemiş bir kurulum bu
sürümden sonra arayüzü İngilizce açar ve aynı menüden tek tıkla Türkçe'ye
döner.

![Prompt Yönetmeni: üretilen prompt, teknik ayarlar, varyasyonlar ve parametre eksenleri](docs/gorseller/studyo-yonetmen.png)

### Üret ve düzenle — birçok model, tek şerit

Azure OpenAI (`gpt-image-2`), Google Gemini (Nano Banana 2 / Pro), Azure AI
Foundry (MAI-Image, FLUX.2) ve OpenAI aynı şeritten seçilir. Her model kartı ne
işe yaradığını bir satırda söyler ve kredi aralığını gösterir; şerit yalnız
**anahtarı kayıtlı** sağlayıcıları listeler. Düzenleme (inpainting) modunda ana
referansın yanına 3 ek referans görsel konabilir.

![Telefonda alttan açılan model seçici: her model bir kart, sağlayıcı işareti ve kredi aralığıyla](docs/gorseller/mobil-model-secici.png)

### Metinden video, tek tıkla canlandırma

Composer'ın üçüncü modu video: Gemini · Veo 3.1'in üç kademesi (Lite / Fast /
tam) ve fal.ai'nin üç modeli — Alibaba Wan 3.0, PixVerse C1, Kling V3 Turbo
Pro. Veo 4–6–8 saniye sunarken PixVerse ve Kling **15 saniyeye kadar** klip
üretebiliyor; oran ekseni de genişledi, üçü de 16:9/9:16'nın yanına **1:1**'i
ekliyor. Veo'nun anahtarı görsel tarafıyla paylaşılır; fal kendi anahtarını
Ayarlar'dan alır — ikisi de aynı composer'da, yeni bir ekran açılmadı.
Galerideki bir görseli ilk kare yapıp canlandırabilirsin; kayıt türev bağını
korur.

![Video modu: Veo 3.1 Lite ile üretilmiş 4 saniyelik video, oynatıcı ve kredi tahmini](docs/gorseller/video-modu.png)

> [!WARNING]
> Video üretimi **1–6 dakika sürer ve senkrondur** — sekmeyi kapatmak işi
> kaybettirir. Veo'nun ücretsiz kademesi yoktur; **fal.ai de ön ödemelidir**,
> hesaba kredi yüklenmeden üretim başlamaz. **Bilinen kusur (Veo):** başlangıç
> ve bitiş karesi BİRLİKTE verildiğinde istek `HTTP 400 — "your use case is
> currently not supported"` ile düşüyor ([ölçümün kaydı](docs/ozellikler.md)).

### Klasörler, arama, toplu işlem

Üretilen her görsel ve video galeriye düşer. İç içe klasörler, sürükle-bırak
taşıma, tarihe veya ada göre sıralama, prompt/boyut/klasör üzerinde anlık arama,
çoklu seçimle toplu taşıma ve silme; bir klasörün tamamı ZIP olarak inebilir.

![Medya görünümü: klasör kartları ve klasörsüz görseller, video karosunda süre rozeti](docs/gorseller/medya-klasorler.png)

### Renk teorisiyle palet

Bir tema rengi seç; OKLCH uzayında uyumlu paletler (tek renk, komşu, karşıt,
komşu + karşıt) anında türetilir ve renkler adlarıyla listelenir. Seçtiğin palet
prompt'a renk yönlendirmesi olarak eklenir; istemediğin rengi çipine tıklayıp
çıkarabilirsin. Ekranın herhangi bir yerinden renk almak için damlalık var.

![Tema rengi ve paletler paneli: renk seçici ve dört armoni önerisi](docs/gorseller/palet.png)

### Logo, motto ve banner bindirme

Kütüphanene yüklediğin logoyu/mottoyu/banner'ı üretilmiş bir görselin üzerine
yerleştir: 9 noktalı ızgara çapası, ince kaydırma, boyut ve gölge — hepsi canlı
önizlemeli.

![Bindirme penceresi: canlı önizleme, 9'lu ızgara çapası, boyut ve kaydırma denetimleri](docs/gorseller/bindirme.png)

### Kendi anahtarın, kendi makinen

Anahtarlar yalnız bu makinede saklanır ve **ekranda hiç gösterilmez**:
`GET /api/settings` tek bir anahtar döndürmez, yalnızca "kayıtlı mı" bayrakları
döner; loglara ve hata izlerine düşen anahtarlar da sansürlenir. Yerel sunucu
yabancı `Host`/`Origin` taşıyan her isteği reddeder.

![Ayarlar: kayıtlı anahtar gösterilmiyor, yalnız "kayıtlı" bilgisi veriliyor](docs/gorseller/ayarlar-byok.png)

Dört karanlık tema (Monokrom · Okyanus · Amber · Menekşe), `prefers-reduced-motion`
desteği ve telefonda tam ekran açılan paneller de kutuda geliyor.

Maddelerin tamamı, hangi sağlayıcının nesi çalışıyor ve yol haritası:
**[docs/ozellikler.md](docs/ozellikler.md)**.

---

## 💻 Geliştirici rehberi

Kod okumaya başlamadan önce **[docs/graflar/README.md](docs/graflar/README.md)**:
modüller, HTTP uçları, `static/` betikleri ve testler arası bağlar kaynaktan
üretilir. Çalışma düzeninin tamamı [CLAUDE.md](CLAUDE.md)'de.

### 1. Gereksinimler

- **Python 3.13+** — Windows'ta ZORUNLU: `azure_client._atomic_write`, kimlik
  dosyasını yazmadan önce izinleri sıkılaştırmak için `os.fchmod` çağırıyor ve o
  çağrı CPython'un Windows yapısına 3.13'te eklendi. Daha eskisinde kimlik yazan
  her test düşer (belge bir zamanlar "3.10+" diyordu; 45 test bu yüzden
  kırmızıydı).
- macOS veya Windows. Android paketi için ayrıca JDK 17 + Android SDK (`android/`).

### 2. Çalıştır

```bash
./run.sh
```

Tarayıcıda `http://127.0.0.1:8765` açılır.

Konteynerde (web sürümü; `Dockerfile` ve gerekçeleri depoda):

```bash
docker build -t kromis .
docker run -p 8765:8765 -v kromis-data:/data kromis
curl localhost:8765/health     # {"ok": true, "version": "…", "data_dir_writable": true}
```

Yazılabilir veri kökü `KROMIS_DATA_DIR` (imajda `/data`, bkz. `paths.py`):
output/, assets/, manifest'ler ve — `HOME` da oraya bağlı olduğu için —
Ayarlar panelinin yazdığı `credentials.env`. Konak dizini bağlanacaksa dizin
uid 10001'e ait olmalı; yazılamıyorsa `/health` 503 döner. Ortam değişkenleri
ve sağlayıcı anahtar adlarının envanteri `.env.example`da; yerel deneme için
`docker compose up --build` (`compose.yaml`, yalnız geliştirme).

### 3. Test

```bash
python3 -m pytest tests/ -q
```

Ön yüz lint/biçim (CI'daki `lint-onyuz` işi aynısını koşar; Node 22):

```bash
npm ci                          # eslint + prettier, package-lock.json'daki sürümlerle
npx eslint static/              # dosyalar arası adlar: eslint.paylasilan-adlar.json
npx prettier --check static/    # düzeltmek için: npx prettier --write static/
```

### 4. Derle ve yayınla

```bash
./build.sh          # PyInstaller çıktısı dist/ altına
```

Paketleme 2026-09-16'dan beri **elle**: `main`'e merge artık sürüm artırmaz ve
paket derlemez. Gerekirse Actions → *Yayın* → *Run workflow* hattı eskisi gibi
çalıştırır (üç paket, tek yayın). Ayrıntı: [docs/yayin-hatti.md](docs/yayin-hatti.md).
Her PR'da koşan kapılar: pytest (E2E dâhil), sızıntı taraması, `ruff check`,
`mypy` (Adım 6'dan beri kesici), eslint + prettier, `docker build` + `/health`.

---

## 🕰️ Depo geçmişi

Bu depo **2026-09-11'de temiz bir geçmişle yeniden kuruldu**: public'e açılmadan
önce commit geçmişindeki eski kurum izleri silindi. Kodun, 47 dalın ve 38 sürüm
etiketinin tamamı taşındı; PR tartışmaları ve eski yayınlar özel arşivde kaldı.
Pratik sonucu, belgelerdeki `#NN` biçimli PR atıflarının bu depoda açılmaması —
ölçümler ilgili belgelerde yazılı, yalnız bağlantı ölü.

## 📜 Lisans

**GNU AGPL-3.0** — bkz. [LICENSE](LICENSE).

Özgürce kullan, incele, değiştir, dağıt. Karşılığında istenen tek şey var:
**değiştirip dağıtırsan kaynağını da aç.** Kapalı kaynak bir ürüne koymak ya da
kaynağı kapatıp kendi ürünün gibi satmak lisansa aykırıdır.

Uygulamayla **ÜRETTİĞİN görseller ve videolar tamamen senindir** — lisans kodu
kapsar, kodun çıktısını değil. Ticari kullanım da dâhil, hiçbir kısıt yok.

* Telif, önceki lisans (proje MIT olarak açılmıştı) ve ihlal bildirimi yolu:
  [TELIF.md](TELIF.md)
* **"Kromis" adı ve logosu lisansın DIŞINDADIR.** Çatal serbest, ad değil —
  değiştirilecekler listesiyle birlikte: [MARKA.md](MARKA.md)
* Üçüncü parti bileşenler ve bildirimleri: [NOTICE](NOTICE)

Paketler imzasız dağıtılıyor; indirdiğin dosyanın gerçekten bu depodan çıktığını
her yayının notlarındaki SHA-256 özetiyle doğrulayabilirsin — nasıl yapılacağı
[KURULUM.md](KURULUM.md)'de.
