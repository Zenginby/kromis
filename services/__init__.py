# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Rota DIŞI uygulama mantığı — `routers/` altındaki uçların ortak paydası.

Faz 0 / Adım 2'de `app.py`den çıkarıldı (docs/faz0-web-first.md). Buradaki
modüller depo kütüphanesi (`storage`, `folders`, `catalog`…) ile rotalar
arasında duruyor: yükleme doğrulaması, id kapıları, palet yönlendirmesi, model
yükü, dil bağlamı. KURAL: bu paket ne `app`i ne `routers`ı ithal eder — yön
tek: app → routers → services → kütüphane (bekçisi tests/test_app_bolme.py).
"""
