---
ajan: agy
tarih: 2026-08-10
workspace: gpt-image-studio
durum: bekliyor
---

# Devir Paketi: Flow-UI Adım 9 — Tema Kalıcılığı & Kütüphane Yüklemeleri (v2.4.0)

**Tarih:** 10 Ağustos 2026  
**Sürüm:** `v2.4.0`  
**İlgili Modüller:** `models.py`, `prefs.py`, `assets_store.py`, `app.py`, `static/flow-tokens.css`, `static/index.html`, `static/settings.js`, `static/assets.js`, `static/chat.js`, `version.py`  
**Test Durumu:** `1150 / 1150` test geçiyor (`pytest tests/`).

---

## 📌 Yapılan Değişiklikler ve Kararlar

1. **Tema Kalıcılığı & "ocean" Teması (D8):**
   - Eski `kurumsal` teması **`ocean` (Okyanus Mavisi)** olarak yeniden adlandırıldı ve `flow-tokens.css` / `index.html` üzerinde güncellendi.
   - `models.py` içerisinde `ALLOWED_THEMES = ("mono", "ocean", "amber", "viola")` allowlist tupu tanımlandı ve `PrefsRequest` modeline `theme` alanı eklendi.
   - `prefs.py` içerisindeki `_SCHEMA` ve `DEFAULTS` güncellenerek tema tercihi `prefs.json` içerisine kalıcı kaydedilmeye başlandı.
   - `static/settings.js` üzerindeki tema seçimi `saveThemePref(theme)` aracılığıyla `/api/prefs` uç noktasına kaydedilir. `static/chat.js` içerisindeki `loadPrefs()` açılışta temayı okuyup DOM (`document.body.dataset.theme`) ve form radyo butonunu senkronize eder.

2. **Kütüphane Yüklemeleri & Tümü Filtresi (D9):**
   - `assets_store.py` içerisindeki `KINDS` tupu `("logos", "banners", "mottos", "uploads")` olarak genişletildi.
   - `app.py` `/api/assets/{kind}` uç noktası `kind == "all"` çağrısında 4 klasörün manifest verilerini `created_at` tarihine göre harmanlayıp döndürür.
   - `static/index.html` ve `static/assets.js` güncellenerek Kütüphane sekmesinde **"Tümü" (all)** varsayılan aktif kılındı ve **"Yüklemeler" (uploads)** sekmesi eklendi.
   - Arayüzden yapılan genel yüklemeler varsayılan olarak `uploads` kategorisine yazılır ve tüm sekmeler dinamik güncellenir.

3. **Sürüm:**
   - `version.py` `APP_VERSION = "2.4.0"` olarak güncellendi.

---

## 🧪 Doğrulama Sonuçları
- `tests/test_prefs.py`: Tema tercihi kaydı ve Pydantic allowlist doğrulaması test edildi.
- `tests/test_assets_route.py`: `uploads` türüne yükleme/listeleme ve `/api/assets/all` harmanlaması test edildi.
- `tests/test_index.py`: Tema seçici ve `flow-tokens.css` `ocean` seçicisi test edildi.
- `pytest tests/`: **1150 test %100 BAŞARIYLA GEÇTİ.**
