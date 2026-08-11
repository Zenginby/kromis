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

<!-- Tablo biçimi bağlayıcı: ilk hücre backtick içinde id olmak zorunda,
     test satırları böyle ayıklıyor. Örnek:
| `topbar-search` | Arama Medya görünümüne taşındı (plan §4.1) | `folders.js` — `searchInput` dinleyicisi kaldırıldı | `test_index.py::test_index_served` arama iddiası silindi |
-->
