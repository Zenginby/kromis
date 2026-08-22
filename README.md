# 🎨 Lumeo

[![Release](https://img.shields.io/badge/version-v0.8.1-blue.svg)](https://github.com/Zenginby/gpt-image-studio/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Build & Test](https://github.com/Zenginby/gpt-image-studio/actions/workflows/release.yml/badge.svg)](https://github.com/Zenginby/gpt-image-studio/actions)

**Lumeo**, yapay zeka destekli görsel üretimi, görsel içi nesne/metin düzenleme, akıllı prompt yönetmenliği, renk paleti teorisi ve kurumsal görsel bindirme (logo/banner/motto) işlemlerini tek bir arayüzde birleştiren gelişmiş masaüstü ve yerel web uygulamasıdır.

---

## 🚀 Uygulamayı İndir

Son kullanıcılar için hazırlanmış hazır derleme paketlerini doğrudan indirebilirsiniz:

| Platform | Mimari | İndirme Bağlantısı |
|---|---|---|
| 🍏 **macOS** | Apple Silicon (M1 / M2 / M3 / M4) | [İndir (ZIP / ARM64)](https://github.com/Zenginby/gpt-image-studio/releases/latest/download/lumeo-macOS-arm64.zip) |
| 🪟 **Windows** | x64 (Windows 10 / 11) | [İndir (ZIP / x64)](https://github.com/Zenginby/gpt-image-studio/releases/latest/download/lumeo-windows-x64.zip) |
| 🤖 **Android** | arm64-v8a (Android 8.0+) | [İndir (APK / arm64)](https://github.com/Zenginby/gpt-image-studio/releases/latest/download/lumeo-android-arm64.apk) |

> [!TIP]
> Paketleme hakkında detaylı bilgi ve kurulum talimatları için [KURULUM.md](KURULUM.md) rehberini inceleyebilirsiniz — belge üç sistemi de kapsıyor (macOS Gatekeeper, Windows SmartScreen ve Android "bilinmeyen kaynak" adımları dahil).
>
> **Android sürümü Play Store'da değil.** APK doğrudan kurulur (sideload) ve uygulama telefonda TAM olarak çalışır: üretim, düzenleme, palet ve bindirme işlemlerinin hepsi cihazdaki Python çalışma zamanında koşuyor — bilgisayara ya da ayrı bir sunucuya bağlı değil. İnternet yalnızca Azure çağrıları için gerekiyor.

### Android'de güncel sürüme geçmek

Yukarıdaki üç bağlantı **her zaman en son yayına** işaret ediyor (`releases/latest/download/…`), yani adres sabit — sürüm yükseldiğinde bağlantıyı değiştirmek gerekmiyor. Rozetteki sürüm o yayının sürümü.

1. **Kurulu sürümünü öğren:** uygulamada **Ayarlar**'ı aç, panelin en altındaki *"Kurulu sürüm"* satırına bak. (Üst şeritteki sürüm rozeti telefonda gizli — dar ekranda oturum başlığını eziyor.)
2. Rozetteki sürümden düşükse APK'yı telefonun tarayıcısından indir.
3. **Üzerine kur, uygulamayı SİLME.** Paketler aynı anahtarla imzalandığı için Android eskisinin üzerine yazar ve verin (görseller, klasörler, Azure anahtarı) yerinde kalır. Silip yeniden kurmak veriyi de siler.
4. Güncellemeden sonraki ilk açılış yine **2–5 saniye** sürer (Python çalışma zamanı yeniden açılıyor); sonrakiler hızlı.

Adım adım anlatım ve "bilinmeyen kaynak" izinleri için: [KURULUM.md → Android (sideload)](KURULUM.md#android-sideload).

---

## ✨ Güncel Özellikler (v0.8.1 & Flow-UI)

### 🎬 1. Stüdyo Tek Döküm & Prompt Yönetmeni
* **Türkçe Diyalogdan İngilizce Prompt:** Türkçe fikir anlatımını otomatik olarak optimizasyonu yapılmış İngilizce `gpt-image-2` prompt'una ve teknik ayarlara (`size`, `quality`, `n`) çevirir.
* **Çoklu Sohbet Sağlayıcısı:** Yönetmen artık Azure AI Foundry dağıtımının yanında OpenAI (GPT-5.6 Terra / Luna / Sol) ve Google Gemini (3.7 Flash) ile de konuşuyor. Model, composer'ın üstündeki şeritten seçiliyor ve seçim `prefs.json`'a yazılıyor. **Şeritler anahtarına göre süzülüyor:** yalnızca kimliği kayıtlı sağlayıcıların modelleri listeleniyor (hiçbiri kayıtlı değilse ilk kurulum için hepsi görünür). Ayarlar'daki **"Prompt Yönetmeni (sohbet modeli)" bölümü de yalnızca onu isteyen sağlayıcıda** (Azure) görünüyor: dağıtım adı istemeyen bir sağlayıcıda başlık dahil hiçbir şey çıkmıyor, yönetmenin talimat dosyası yolu ise her sağlayıcıda duruyor.
* **Tıklanabilir Çip Menüleri:**
  - `options`: Yönetmenin sorduğu sorular için tıklanabilir yanıt önerileri.
  - `variations`: Fikirden türetilen tek tıkla uygulanabilir varyasyonlar.
  - `parameters`: Stil, ışık, açı ve kompozisyon parametre eksenleri.
* **Oturum Yönetimi & Kebap Menüsü:** Sohbet geçmişleri diske saklanır (`output/chats.json`), kenar panelinde listelenir. Üst şeritteki kebap menüsü (`#chats-kebab`) ile oturumlar yeniden adlandırılabilir, temizlenebilir veya toplu olarak silinebilir.

### 🖼️ 2. Görsel Üretimi & Çoklu Referans Düzenleme
* **Çoklu Sağlayıcı Entegrasyonu:** Azure OpenAI (`gpt-image-2`), OpenAI (`gpt-image-2`, `gpt-image-1`) ve Google Gemini (Nano Banana 2 / Nano Banana Pro) üretimi (1-4 görsel). Gemini'de piksel boyutu yerine oran (1:1 … 21:9) ve 1K/2K/4K çözünürlük seçiliyor. *DALL-E 3 12 Mayıs 2026'da OpenAI API'sinden kalktığı için katalogdan çıkarıldı.*
* **Sağlayıcı İşareti:** Her iki model şeridi (görsel ve Prompt Yönetmeni) seçili modelin sağlayıcısını bir işaretle de gösteriyor — Gemini modelinde Gemini, OpenAI'de OpenAI, Azure'da Azure. Model değişince işaret de değişiyor.
* **Çoklu Referans Görsel Bindirme:** Düzenleme (Inpainting / Edits) modunda ana referans görselin yanına en fazla 3 ek referans görsel eklenebilir.

### 📁 3. Klasörler & Medya Yönetimi
* **Sınırsız Hiyerarşik Klasör Ağacı:** İç içe alt klasörler (`parent_id` hiyerarşisi), kırıntı (breadcrumb) gezintisi.
* **Akıllı Kapak Görselleri (`.folder-thumb`):** Klasör kartları, klasör içindeki ilk üretilen görselin küçük resmini otomatik kapak olarak gösterir.
* **Klasör Yeniden Adlandırma:** `#folder-rename` düğmesi ile klasör adları anında güncellenir.
* **Sürükle-Bırak Taşıma:** Görseller klasör kartlarına sürüklenerek kolayca taşınabilir. Bilgisayardan dosya bırakılarak doğrudan içe aktarılabilir.
* **Medya Sıralama & Arama:** Görseller ve klasörler **Tarih** veya **İsim (A-Z)** sırasına göre dizilebilir. Prompt, boyut veya klasör adına göre anlık arama yapılabilir.
* **Boş Durum Glifleri:** Boş galeri veya arama sonuçlarında açıklayıcı Türkçe boş durum ekranları beliri.

### 🔘 4. Çoklu Seçim & Toplu İşlemler
* **Toplu Seçim Modu:** Görseller tek tıkla seçilebilir, seçili gruptaki görseller tek seferde başka bir klasöre sürüklenebilir veya toplu olarak silinebilir.

### 🎨 5. OKLCH Renk Teorisi & Palet Motoru
* **OKLCH Armoni Önerileri:** Bir tohum renkten 6 uyumlu renk paleti türetilir.
* **3 Kademeli Renk Baskısı:** İpucu (%25), Dengeli (%50), Katı (%85) renk hassasiyet seviyeleri.
* **Paletten Renk Çıkarma:** İstenmeyen renkler çipe tıklanarak paletten çıkarılabilir.
* **Damlalık (EyeDropper):** Tarayıcıda EyeDropper API, macOS masaüstü uygulamasında yerel `NSColorSampler` ile ekranın her yerinden renk seçimi.

### 🏷️ 6. Varlık Kütüphanesi & Bindirme (Logo / Motto / Banner)
* **Kurumsal Bindirme:** Görsel üzerine Logo, Motto veya Banner yerleştirme.
* **9'lu Izgara Çapası & Offset Kaydırma:** 9 farklı yön noktasına çapalama ve hassas oran kaydırma, boyut ve gölge ayarları. Canlı önizleme desteği.

### 🌙 7. Tüm Uygulamayı Kapsayan Tema Motoru
* **4 Curated Dark Theme:** **Mono** (Siyah/Gri), **Ocean** (Okyanus Mavisi), **Amber** (Kehribar/Sıcak), **Viola** (Mor/Asil) karanlık cam Temaları.
* **Erişilebilirlik:** `prefers-reduced-motion` desteği.

### 🔒 8. BYOK (Bring Your Own Key) & Güvenlik Redaksiyonu
* **Çoklu Sağlayıcı Desteği:** OpenAI, Fal.ai, Replicate, ComfyUI, Ollama altyapısı.
* **Write-Only Güvenlik Maskelemesi:** `GET /api/settings` yanıtlarında hiçbir API anahtarı istemciye açık olarak dönmez, yalnızca boolean durum bayrakları döndürülür.
* **Otomatik Log Sansürleme:** `errlog.py` içerisindeki `redact_secrets()` mekanizması, loglarda veya hata traceback'lerinde geçen tüm API anahtarlarını sansürler.

---

## 🔮 Gelecek Yol Haritası (SaaS Transformation Master Plan)

> **Durum denetimi (2026-08-22).** 21–22 Ağustos'taki çoklu sağlayıcı turundan
> (model kataloğu → sağlayıcı adaptörleri → Gemini) sonra her madde **koda
> bakılarak** işaretlendi, belgeye bakılarak değil. Faz faz tam döküm ve kanıtlar:
> [master yol haritası](docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md).
> **Sıradaki iş ve öncelik sıralı kuyruk:**
> [görev defteri](docs/superpowers/plans/2026-08-22-gorev-defteri.md) — hangi
> maddenin neden beklediği, kabul ölçütüyle birlikte orada yazılı.

* **Faz 2: BYOK Çoklu Sağlayıcı Arayüzü** — 🟡 kısmen teslim
  - [x] **Model ve sağlayıcı seçimi:** üst şeritte görsel modeli seçici, composer'da
        sohbet modeli şeridi; ikisi de kayıtlı anahtara göre süzülüyor ve seçim
        `prefs.json`'a yazılıyor.
  - [x] **Ayarlar panelinde sağlayıcı grupları:** Azure OpenAI, OpenAI ve Google Gemini
        (yalnız-OpenAI ya da yalnız-Gemini kurulumu da geçerli).
  - [x] **Sağlayıcı adaptör katmanı:** görselde `providers.py`, sohbette
        `chat_providers.py`; kataloğa girmemiş bir sağlayıcı sessizce Azure'a düşmüyor.
  - [ ] Fal.ai, Replicate, ComfyUI ve Ollama sekmeleri — bugün yalnızca
        `credentials.env` alanları ve durum bayrakları var; adaptör ve arayüz yok.
  - [ ] Canlı bağlantı testi düğmeleri — bugünkü karşılık yalnız "anahtar kayıtlı mı"
        listesi, gerçek bir çağrı denemesi değil.
* **Faz 3: E-Ticaret Ürün Araçları** — ⬜ açık
  - [ ] Elde Ürün Görselleştirme (Product-in-Hand).
  - [ ] Otomatik Arka Plan Kaldırma & Konu Gölgeleme.
  - [ ] Görsel İçi Metin & Banner Sihirbazı (E-ticaret duyuruları için).
* **Faz 4: Image-to-Video Animasyon Motoru** — ⬜ açık
  - [ ] Üretilen görselleri tek tıkla animasyona çevirme (Kling, Luma Dream Machine,
        Runway Gen-3 entegrasyonları).
* **Faz 5: SaaS & Bulut Altyapısı** — 🟡 yalnız kredi metadata'sı hazır
  - [x] **Model bazlı kredi tarifesi:** katalogda her modelin kredisi yazılı ve üretim
        anındaki değer kayda geçiyor. **Bugün YALNIZ metadata:** hiçbir bakiye
        düşülmüyor, hiçbir üretim engellenmiyor — gelecek ledger'ın ihtiyacı olan alan
        şimdiden dolu.
  - [ ] Kullanıcı hesapları ve çoklu çalışma alanları (Workspaces).
  - [ ] Nesne depolama + CDN (Cloudflare R2 / MinIO) ve medya yönetimi.
  - [ ] Üyelik paketleri (Free, Basic, Pro, Max) ve atomik kredi ledger'ı.
  - [ ] Ücretsiz pakette filigran (watermark) kuralı.

---

## 💻 Geliştirici Rehberi (Developer Setup)

### 1. Gereksinimler
- Python 3.10+
- macOS veya Windows OS (Android paketi için ayrıca JDK 17 + Android SDK — bkz. `android/`)

### 2. Yerel Sunucuyu Çalıştırma
```bash
# Bağımlılıkları yükle ve sunucuyu başlat
./run.sh
```
Tarayıcıda `http://127.0.0.1:8765` (veya `http://localhost:8000`) adresi açılır.

### 3. Test Paketini Çalıştırma
```bash
.venv/bin/python -m pytest tests/ -v
```

### 4. Masaüstü Uygulaması Derleme (PyInstaller)
```bash
./build.sh
```
Derleme çıktısı `dist/` klasörüne yerleşir.

### 5. Yayın Almak

**Elle yapılacak hiçbir şey yok.** `main`'e bir PR birleştir; sürüm otomatik
artar, macOS + Windows + Android paketlerinin üçü birden derlenir ve **hepsi
yeşilse** yayın tek seferde oluşur. Bir platform düşerse ne tag ne yayın oluşur —
eksik yayın diye bir ara durum yok.

- Sürüm seviyesini commit başlığı belirler (`feat:` → minör, ötekiler → yama).
- Yalnız belge/test/CI değiştiyse yayın çıkmaz.
- `[yayin: yok]`, `[surum: minor]` ve `[not] …` ile hatta elle müdahale edilir.

Ayrıntı, kuru prova ve sorun giderme: **[docs/yayin-hatti.md](docs/yayin-hatti.md)**.

---

## 📜 Lisans

Bu proje **MIT Lisansı** altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakabilirsiniz.
