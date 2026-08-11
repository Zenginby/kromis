# Flow-UI Adım 13 Devir Paketi (Tek Döküm, Tek Composer)

- **Tarih:** 2026-08-10
- **Sürüm:** `v2.3.0`
- **Tamamlanan Görev:** Flow-UI Adım 13 (Tek döküm sohbet ve görsel üretimi + Tek composer mimarisi)
- **Referans Tasarım:** `docs/flow-ui/studio-session.html`

---

## Yapılan Değişiklikler ve Kararlar

1. **HTML & Bileşen Yapısı (`static/index.html`):**
   - `#view-image` ve `#view-chat` ayrımı kaldırıldı; yerine tek `<section id="view-studio">` (Tek döküm alanı) eklendi.
   - `#chat-input`, `#chat-send`, `#chat-status`, `#preview`, `#preview-empty`, `#preview-img`, `#preview-clear` emekliye ayrıldı.
   - Yüzen composer tek `textarea id="prompt"` ve tek `button id="go"` etrafında birleştirildi.
   - `#ref-chip` içerisine küçük önizleme görseli `<img id="ref-chip-img">` eklendi.

2. **Mantık ve Akış Senkronizasyonu (`static/core.js`, `static/chat.js`):**
   - `VIEWS`, `VIEW_ORDER` ve `showView()` kaldırıldı; `setMode(modeName)` ve `submitComposer()` getirildi.
   - Mod değiştiğinde (`Görsel` / `Yönetmen`): `#composer[data-mode=...]` güncellenir, `#prompt` placeholder'ı ve `#go` buton etiketi dinamik değişir.
   - Enter (Shift+Enter hariç) ve ⌘/Ctrl+Enter kısayolları doğrudan `submitComposer()`'a bağlandı.
   - Görsel üretimi sırasında `.chat-result.is-pending` skeleton kartı `#chat-log` içerisine eklenir ve `#progress` barı bu kartın içine taşınır.

3. **ID Sözleşmesi & Defteri (`docs/flow-ui/id-defteri.md`, `tests/test_id_contract.py`):**
   - Emekliye ayrılan 9 baseline ID (`view-image`, `view-chat`, `chat-input`, `chat-send`, `chat-status`, `preview`, `preview-empty`, `preview-img`, `preview-clear`) deftere gerekçeleriyle kaydedildi.
   - JS dosyalarındaki döküntü referanslar temizlendi ve ID sözleşme testleri `%100` yeşile çekildi.

4. **Sürüm & Test Doğrulamaları:**
   - `APP_VERSION` -> `2.3.0`
   - Unit & Entegrasyon Testleri: **1144 testin tamamı BAŞARIYLA geçti** (`pytest tests/`).
   - Playwright End-to-End Testi: `tests/test_playwright_studio.py` başarıyla çalıştırıldı ve geçti.

---

## Gelecek Görevler (Kalan Flow-UI Adımları)

- **Adım 9:** Tema kalıcılığı + Kütüphane Yüklemeleri (`docs/flow-ui/library-view.html`)
- **Adım 10:** Kozmetik cila + D10 Medya sıralaması + M1 listbox accessibility + DM Sans font bundle (`docs/flow-ui/app-shell.html`)
