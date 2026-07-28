#!/usr/bin/env bash
# GPT-Image Studio'yu macOS uygulaması olarak derler, ad-hoc imzalar, zip'ler.
# İki hat var: bu makinede (host mimarisi neyse) yerel doğrulama derlemesi —
# paketleme yolunu uçtan uca sınamak için; Apple Silicon'a gönderilecek gerçek
# paket GitHub Actions'ın arm64 runner'ında ayrı bir işle üretilir (bkz.
# docs/superpowers). Notarization YOK — kullanıcı ilk açılışta Sistem
# Ayarları → Gizlilik ve Güvenlik → "Yine de Aç" yapar (bkz. KURULUM.md).
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/GPT-Image Studio.app"
ZIP="dist/GPT-Image Studio.zip"

source .venv/bin/activate
pip install -q -r requirements.txt -r requirements-dev.txt

echo "→ testler"
python -m pytest tests/ -q

echo "→ temizlik"
rm -rf build dist

echo "→ derleme"
pyinstaller gpt-image-studio.spec --noconfirm

echo "→ ad-hoc imza"
codesign --force --sign - "$APP"
codesign --verify --verbose "$APP"

echo "→ zip (ditto: .app'in sembolik bağları korunur, 'zip' bozar)"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "→ ara derleme dizinini temizle"
rm -rf build

echo "✓ hazır: $ZIP ($(du -h "$ZIP" | cut -f1))"
