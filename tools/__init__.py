# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Derleme/yayın yardımcıları — uygulamanın çalışma zamanına GİRMEZ.

Bu dosyanın tek işi `tools`'u içe aktarılabilir bir paket yapmak: yayın hattının
karar mantığı (`surum_karari.py`) ve sürüm yazıcısı (`surum_yaz.py`) artık
`tests/` altından sınanıyor ve testin onları `import tools.surum_karari` ile
alması, her test dosyasında importlib kurulumu tekrarlamaktan hem kısa hem
sağlam.

Buradaki modüller PAKETE GİRMİYOR: `kromis.spec` yalnızca app.py'nin
import zincirini izliyor ve o zincir `tools`'a hiç dokunmuyor. `tools/` ayrıca
`tools/surum_karari.py` içindeki GUVENLI_YOLLAR listesinde "pakete girmeyen
yollar" arasında sayılı — yani buraya yapılan bir değişiklik tek başına yayın
tetiklemez.
"""
