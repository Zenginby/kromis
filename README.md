# GPT-Image Studio

Azure `gpt-image-2` deployment'ı için yerel web arayüzü. Prompt'tan görsel üretir,
geçmişi diskte saklar, KURUM logosunu köşeye bindirir.

## Çalıştırma
    ./run.sh
Tarayıcıda http://127.0.0.1:8765 açılır.

## Kimlik
`~/.config/gpt-image-studio/credentials.env` (arayüzden yazılır), yoksa
`~/.config/claude-tools/azure-gpt-image2.env` okunur — anahtarlar:
- `AZURE_IMAGE_API_KEY`, `AZURE_IMAGE_BASE_URL` — görsel üretimi (zorunlu)
- `AZURE_CHAT_DEPLOYMENT` — Prompt Yönetmeni'nin sohbet dağıtımı (ör. `gpt-5.6-luna`).
  Arayüzde Ayarlar'dan girilir; boşsa özellik kapalı kalır.
- `AZURE_CHAT_API_KEY`, `AZURE_CHAT_BASE_URL` — **opsiyonel**, yalnız sohbet ayrı bir
  Azure kaynağındaysa ve ELLE yazılır. Verilmezse görselin key/endpoint'i kullanılır.

Yazma birleştirmelidir (`azure_client.save_env`): endpoint'i tek başına kaydetmek
dosyadaki diğer anahtarları silmez.

Key rotasyonu: `az cognitiveservices account keys list -g ai-services -n ai-ornek-swedencentral`.
Dağıtımları listeleme (CLI'ın `cognitiveservices deployment list` komutu 2.87'de
desteklenmeyen bir api-version gönderiyor, ARM'a doğrudan sormak gerekiyor):

    ID=$(az resource list --name ai-ornek-swedencentral \
      --resource-type Microsoft.CognitiveServices/accounts --query '[0].id' -o tsv)
    az rest --method get --url "https://management.azure.com${ID}/deployments?api-version=2026-07-01" \
      --query "value[].{dagitim:name, model:properties.model.name}" -o table

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
- **Prompt Yönetmeni** (üst bardaki "Prompt Yönetmeni" sekmesi): Türkçe anlatılan
  fikri İngilizce bir `gpt-image-2` prompt'una + teknik ayarlara çeviren sohbet.
  "Forma aktar" prompt'u `#prompt`'a yazar, `size/quality/n` önerilerini yalnızca
  formda GERÇEKTEN var olan değerlerse uygular, uygulanamayanı açıkça söyler.
  Yanıt tek seferde gelir (streaming yok), sohbet geçmişi diske yazılmaz.
  Persona `bundled/prompts/prompt-yonetmeni.md`'de; kullanıcı
  `<data_dir>/chat-instructions.md` dosyasını oluşturarak ezebilir (yol Ayarlar'da
  yazılı). Gömülü dosya kopyalanmaz, her açılışta okunur — yeni sürümdeki
  iyileştirme kendi dosyasını yazmamış herkese ulaşır.
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
- İndirme konumu seçilebilir (galeri kartında ve büyüteçte): paketlenmiş
  uygulamada WKWebView'ın kayıt paneli, tarayıcıda File System Access API
  (Chrome/Edge). İkisi de yoksa (Safari, Firefox) dosya indirme klasörüne düşer
- Bilgisayardan içe aktarma: görseli klasör kartına ya da galeri alanına
  sürükleyip bırakınca o klasöre kaydedilir (çoklu dosya, PNG'ye kodlanır,
  kartta "içe aktarıldı" işareti). Merkez alana bırakmak değişmedi: orası
  hâlâ "referans görsel olarak yükle"

## Sonraya (v2)
- Maske ile bölgesel düzenleme (inpainting)
- Çoklu referans görsel
