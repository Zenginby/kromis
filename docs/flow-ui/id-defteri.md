# id defteri — bilerek kaldırılan element id'leri

Flow taşımasında `static/index.html`'den **kaldırılan** her id burada gerekçesiyle
yazılı. `tests/test_id_contract.py` bu dosyayı okur; defterde yazmayan bir id
kaybolduğu anda test kırmızıya döner.

## Neden defter, neden "boş diff" değil

Taşıma başlarken kural "id diff boş olmalı" idi. Ama tasarım bazı öğeleri
gerçekten kaldırıyor (sekmeler, üst şeritteki arama, ayrı düzenle paneli) ve
6 Ağustos kararıyla **bu öğelerin testleri de onlarla birlikte güncelleniyor.**
O yüzden boş diff kuralı düştü; yerine bu defter ve üç otomatik iddia geçti.

Defter, diff'ten **güçlü** bir yerde duruyor: ikinci iddia bir id'nin JS bağının
da silinmiş olmasını şart koşuyor, yani **yeniden adlandırmayı** da yakalıyor —
eski diff yalnızca yokluğu görüyordu.

## Kaldırmanın gerçek maliyeti

`static/core.js:10`'da `const $ = (id) => document.getElementById(id)`.
JS'ten `$()` ile **145 id**'ye dokunuluyor ve **56'sı top-level bağ** — yani dosya
yüklenirken çalışan `$("x").addEventListener(...)` satırları. Böyle bir id
kaybolursa `$()` `null` döner, `addEventListener` `TypeError` atar ve **o dosyanın
o satırdan sonraki tüm dinleyicileri hiç kurulmaz.** Yükleme sırası bağlayıcı:

    core.js → folders.js → assets.js → palette.js → settings.js

Bu yüzden bir id'yi deftere yazmak yetmez: JS bağını da aynı commit'te
kaldırmak gerekir. Testin ikinci iddiası bunu zorunlu tutuyor.

## Kaldırılanlar

| id | Hangi tasarım kararıyla | JS bağı nerede kaldırıldı | Güncellenen test |
|---|---|---|---|
| `assets-modal` | Kütüphane modal değil GÖRÜNÜM (tasarım §4.1, plan §0.2/A1 — Adım 7b). İçerik id'leri (`asset-tabs`, `asset-grid`…) `#view-library` bölümüne taşındı; giden yalnızca modal kabuğu. | `assets.js` — `openAssetsModal`/`closeAssetsModal` ve backdrop/Escape dinleyicileri silindi; `loadAssets` artık modal açıklığına bakmıyor | `test_index.py::test_library_is_a_rail_view_not_a_click_on_a_hidden_button` (yokluğunu doğruluyor) |
| `assets-close` | Aynı karar: kapatılacak modal kalmadı, görünümden ray ile çıkılıyor. | `assets.js` — kapatma dinleyicisi `openAssetsModal` ile birlikte gitti | aynı test |
| `view-image` | Tek döküm, tek composer (tasarım §2, Adım 13). `#view-image` ve `#view-chat` tek `#view-studio` bölümünde birleşti. | `core.js` — `VIEWS`, `VIEW_ORDER` ve `showView` silindi; `setMode` kullanılıyor | `test_index.py::test_single_studio_view_is_rendered` |
| `view-chat` | Aynı karar (Adım 13): sohbet ve üretim akışı tek `#view-studio` bölümünde. | `core.js` — `showView` silindi; sohbet dökümü `#view-studio` içinde | aynı test |
| `chat-input` | Tek composer (Adım 13). `#chat-input` metin kutusu `#prompt` ile birleşti. | `chat.js` — tüm `$("chat-input")` atıfları `$("prompt")` yapıldı | `test_index.py::test_submit_composer_routes_by_mode` |
| `chat-send` | Tek composer (Adım 13). `#chat-send` düğmesi `#go` ile birleşti. | `chat.js`, `settings.js` — tüm `$("chat-send")` atıfları `$("go")` veya `submitComposer` yapıldı | aynı test |
| `chat-status` | Tek composer (Adım 13). `#chat-status` durum metni `#status` (`statusEl`) ile birleşti. | `chat.js` — `chatStatus` artık `statusEl`'e yazıyor | `test_index.py::test_single_studio_view_is_rendered` |
| `preview` | Tek döküm (Adım 13). Büyük önizleme sahnesi kalktı; görseller döküm kartlarında ve büyüteçte gösteriliyor. | `core.js` — `showPreviewSrc` ve `clearPreview` silindi | aynı test |
| `preview-empty` | Aynı karar (Adım 13): önizleme sahnesi kalktı. | `core.js` — `clearPreview` silindi | aynı test |
| `preview-img` | Aynı karar (Adım 13): önizleme sahnesi kalktı. | `viewer.js` — `previewImg` dinleyicisi silindi | `test_index.py::test_single_studio_view_is_rendered` |
| `preview-clear` | Aynı karar (Adım 13): önizleme sahnesi kalktı. | `core.js` — `clearPreview` silindi | aynı test |
| `logo-color-row` | Marka-nötr ürün kararı: pakete gömülü kurumsal logo çifti (mavi + beyaz) kaldırıldı. Oto/Mavi/Beyaz satırı YALNIZCA o çift için görünüyordu (`syncColorRow` onu `selectedAsset.logo === "builtin"` koşuluna bağlıyordu) — kullanıcının yüklediği tek dosyalık logolarda hiçbir işlevi yoktu. | `assets.js` — `syncColorRow` ve tüm çağrıları silindi; `style.css`'ten `#logo-color-row[hidden]` kuralı kalktı | `test_composite.py` (oto-renk/`pick_logo`/`region_box` testleri kaldırıldı), `test_logo.py::test_logo_without_asset_id_is_rejected` (yerleşik logo testinin yerini aldı) |
| `logo-color` | Aynı karar: seçilecek varyant kalmadı. Sunucu tarafında `LogoRequest.color` alanı ve `composite.pick_logo` da bu commit'te gitti; `composite_logo` artık tek `logo_path` alıyor. | `assets.js` — `#logo-color` click dinleyicisi ve `readLogoOpts`'taki `color` okuması silindi | aynı testler |
| `progress` | Bekleme göstergesi olarak shimmer kutusu geçti (pixel-canvas, `.pending-shimmer`). Yüzde de birlikte kalktı çünkü ÖLÇÜM DEĞİLDİ: sağlayıcı tek yanıt döndürüyor, gerçek bir akış yok — bar 160ms'lik bir `setInterval` ile ~%90'a doğru asimptotik dolup orada bekliyor, iş bitince %100'e sıçrıyordu. Taşınabilir düğüm olması da buradan geliyordu (`.studio-flow` ↔ bekleme kartı); shimmer kartın İÇİNDE doğduğu için taşıma mantığı da gitti. | `core.js` — `startProgress`/`stopProgress`, `progressTimer`/`progressHideTimer`/`progressGen` ve tek okuyucusu `stopProgress` olan `ok` bayrağı silindi; `chat.js` — `beginResultTurn`/`dropPendingTurn`/`appendResultTurn`'deki taşıma blokları silindi | `test_shimmer.py::test_simulated_percentage_is_gone` (yokluğunu doğruluyor), `test_shimmer.py::test_shimmer_is_the_only_thing_in_the_pending_card` |
| `progress-fill` | Aynı karar: dolduracak bir yüzde kalmadı. `style.css`'ten `.progress`, `.bar`, `.bar-fill`, `.pct` kuralları da bu commit'te kalktı — tek kullanıcıları bu bloktu (büyüteç kendi `.viewer-bar`/`.viewer-pct` sınıflarını kullanıyor). | `core.js` — `startProgress`/`stopProgress` ile birlikte gitti | aynı testler |
| `progress-pct` | Aynı karar: yazılacak bir yüzde kalmadı. | `core.js` — `startProgress`/`stopProgress` ile birlikte gitti | aynı testler |
| `chat-instructions-path` | "Prompt Yönetmeni · talimat" bölümü kaldırıldı (11 Eylül 2026 kullanıcı kararı, Ayarlar penceresinin sadeleştirilmesi). Bölüm SALT OKUNUR iki dosya yolundan ibaretti (`chat-instructions.md` ve video karşılığı) — kullanıcının panelde yapabileceği hiçbir şey yoktu, yani ayarlar penceresinin en pahalı yerinde duran bir künyeydi. Yollar sunucuda duruyor ve `GET /api/settings` hâlâ döndürüyor (`chat_instructions_path`); giden yalnız ekrandaki kopyası. Kardeşi `chat-video-instructions-path` aynı commit'te gitti ama tabanda hiç yoktu, o yüzden deftere yazılmıyor (`test_defter_tabandan_sec` reddederdi). | `settings.js` — `applyConfigured`'in iki `textContent` yazımı silindi | `test_index.py::test_YONETMEN_TALIMAT_bolumu_KALDIRILDI` (yokluğunu doğruluyor), `test_index.py::test_chat_workspace_markup_is_served` (id listesinden çıktı) |

<!-- Tablo biçimi bağlayıcı: ilk hücre backtick içinde id olmak zorunda,
     test satırları böyle ayıklıyor. Örnek:
| `topbar-search` | Arama Medya görünümüne taşındı (plan §4.1) | `folders.js` — `searchInput` dinleyicisi kaldırıldı | `test_index.py::test_index_served` arama iddiası silindi |
-->
