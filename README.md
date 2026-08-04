# GPT-Image Studio

Azure `gpt-image-2` deployment'ı için yerel web arayüzü. Prompt'tan görsel üretir,
geçmişi diskte saklar, KURUM logosunu köşeye bindirir.

## Çalıştırma
    ./run.sh
Tarayıcıda http://127.0.0.1:8765 açılır.

## Kimlik
`~/.config/claude-tools/azure-gpt-image2.env` okunur (AZURE_IMAGE_API_KEY, AZURE_IMAGE_BASE_URL).
Key rotasyonu: `az cognitiveservices account keys list -g ai-services -n ai-ornek-swedencentral`.

## Test
    python -m pytest tests/ -v

## Masaüstü uygulaması olarak paketleme
    ./build.sh          # → dist/GPT-Image Studio.zip (host mimarisi, ad-hoc imzalı)
Pencereyi kaynaktan denemek için: `.venv/bin/python desktop.py`
Son kullanıcı talimatı: `KURULUM.md`. Tasarım/plan: `docs/superpowers/`.

İki hat var: `gpt-image-studio.spec` kasıtlı olarak `target_arch` vermez —
PyInstaller derlemeyi çalıştıran yorumlayıcının mimarisini hedefler (bu
çapraz derleme yapamadığı için tektir).

**Doğrulama hattı (yerel):** Bu makinede (Intel) `./build.sh` x86_64 üretir —
paketleme yolunu uçtan uca sınamak için.

**Gönderim hattı (CI):** Ofis çalışanlarına gidecek arm64 paket, GitHub Actions'ın
arm64 runner'ında (macos-14) aynı spec ve `build.sh` ile üretilir. Actions → **Kodu
Çalıştır** (Run Workflow) → **macOS arm64 paketi** → **Yapıtlar** (Artifacts) den
`gpt-image-studio-macos-arm64.zip` indir (`.github/workflows/build-macos-arm64.yml`).

## Özellikler
- Prompt'tan görsel üretme (boyut/kalite/adet)
- Geçmiş galerisi (indir, sil)
- Görsel düzenleme: dosya yükle veya galeriden seç + prompt (Azure images/edits)
- Logo / motto / banner bindirme: 9'lu konum ızgarası + ince kaydırma
  (yatay/dikey, görselin dışına taşmaz), boyut ve gölge; canlı önizleme
- Tema rengi + renk paleti: bir tohum renkten OKLCH renk teorisiyle 6 uyumlu
  palet önerisi; seçilen palet prompt'a renk yönlendirmesi olarak eklenir
  (üretimde ve düzenlemede), 3 kademeli baskı (İpucu/Dengeli/Katı), kalıcı
  isimli palet kütüphanesi. Paletten istenmeyen renk çipe tıklanarak çıkarılır
  (kalanların sırası korunur; çıkarıp kaydedince palet o renksiz donar)
- Damlalık: ekranın her yerinden renk seçme — tarayıcıda EyeDropper API,
  paketlenmiş uygulamada macOS NSColorSampler (WKWebView'da EyeDropper yok)
- Bilgisayardan içe aktarma: görseli klasör kartına ya da galeri alanına
  sürükleyip bırakınca o klasöre kaydedilir (çoklu dosya, PNG'ye kodlanır,
  kartta "içe aktarıldı" işareti). Merkez alana bırakmak değişmedi: orası
  hâlâ "referans görsel olarak yükle"

## Sonraya (v2)
- Maske ile bölgesel düzenleme (inpainting)
- Çoklu referans görsel
