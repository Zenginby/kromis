"""Uygulama sürümü — TEK kaynak.

Buradaki değer üç yere birden akar:
  1. macOS paketinin Info.plist'i (gpt-image-studio.spec → CFBundle*Version),
  2. index.html'deki statik dosya cache-buster'ı (`?v=`, app.py:index()),
  3. Ayarlar panelinde kullanıcıya gösterilen sürüm satırı (GET /api/settings).

Elle bakımı gereken İKİNCİ bir sürüm literali BIRAKILMAMALI: v1.8'e kadar
`?v=18` elle artırılıyordu ve unutulduğunda paketi değiştiren kullanıcı bayat
JS ile kalıyordu — sessiz ve teşhisi zor bir kırılma.

KURAL: gönderilen HER build APP_VERSION'ı artırır — yalnızca bir CSS/JS
düzeltmesi de olsa. Cache-buster artık buna bağlı; sürüm sabit kalırsa
statik dosyaların URL'si de sabit kalır ve istemci eski kopyayı sunabilir.

Bu modül BİLEREK bağımlılıksız (yalnız __future__): gpt-image-studio.spec onu
PyInstaller DERLEME zamanında, uygulamanın hiçbir bağımlılığı import edilmeden
dosyadan yükler (bkz. spec'in başındaki açıklama). Buraya bir proje import'u
eklemek o yüklemeyi kırar — tests/test_version.py bunu zorluyor.

Biçim MAJOR.MINOR.PATCH olmak ZORUNDA: Info.plist'in CFBundleVersion'ı
noktalı-sayısal bir dizi bekler.
"""
from __future__ import annotations

APP_VERSION = "0.3.0"

