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
çapraz derleme yapamadığı için tektir). Bu makinede (Intel) `./build.sh`
x86_64 üretir ve yerel doğrulama hattıdır — paketleme yolunu uçtan uca
sınamak için. Ofis çalışanlarına gidecek gerçek arm64 paket, GitHub
Actions'ın arm64 runner'ında aynı spec ve `build.sh` ile üretilir (gönderim
hattı — ayrı bir iş).

## Özellikler
- Prompt'tan görsel üretme (boyut/kalite/adet)
- Geçmiş galerisi (indir, sil)
- Görsel düzenleme: dosya yükle veya galeriden seç + prompt (Azure images/edits)
- KURUM logosu bindirme
- Tema rengi + renk paleti: bir tohum renkten OKLCH renk teorisiyle 6 uyumlu
  palet önerisi; seçilen palet prompt'a renk yönlendirmesi olarak eklenir
  (üretimde ve düzenlemede), 3 kademeli baskı (İpucu/Dengeli/Katı), kalıcı
  isimli palet kütüphanesi

## Sonraya (v2)
- Maske ile bölgesel düzenleme (inpainting)
- Çoklu referans görsel
