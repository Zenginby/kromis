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

# python3, python DEĞİL: macOS'te `python` diye bir komut yok. Erken ve
# anlaşılır başarısız ol — yoksa hata "command not found" olarak çıkıp
# kullanıcıya ne kuracağını söylemiyor.
if ! command -v python3 >/dev/null 2>&1; then
  echo "HATA: python3 bulunamadı." >&2
  echo "Xcode Command Line Tools kur:  xcode-select --install" >&2
  exit 1
fi

# .venv'i BURADA oluştur. Önceki sürüm var olmasını bekliyordu; taze bir
# kopyada (ör. GitHub'dan indirilen zip) "activate: No such file or directory"
# ile düşüyordu ve CI bu kusuru ayrı bir "venv kur" adımıyla etrafından
# dolaşıyordu. run.sh zaten bu deseni kullanıyor.
if [[ ! -d .venv ]]; then
  echo "→ .venv yok, oluşturuluyor"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt -r requirements-dev.txt

echo "→ testler"
python3 -m pytest tests/ -q

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
