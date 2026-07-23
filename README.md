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

## Özellikler
- Prompt'tan görsel üretme (boyut/kalite/adet)
- Geçmiş galerisi (indir, sil)
- Görsel düzenleme: dosya yükle veya galeriden seç + prompt (Azure images/edits)
- KURUM logosu bindirme

## Sonraya (v2)
- Maske ile bölgesel düzenleme (inpainting)
- Çoklu referans görsel
