# Flow Stüdyo — tek döküm turu (Adım 11 · 12 · 13) — uygulama planı

**Tarih:** 7 Ağustos 2026 (Adım 0 · commit ayrımı: 8 Ağustos)
**Dal:** `feat/flow-ui-pr3` — Adım 7b (`0223a19`) + Adım 8 (`2d97d94`) burada, **PR [#21](https://github.com/Zenginby/gpt-image-studio/pull/21)**
**Başlangıç:** `2d97d94` (`APP_VERSION` = **2.1.0**), `pytest` **1106 yeşil**, çalışma ağacı temiz
**Tasarım sözleşmesi:** `docs/flow-ui/flow-redesign-plan.md` (referans ekranlar `docs/flow-ui/*.html`)
**Önceki plan:** `docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md` (Adım 0–8 orada; §0.1 tablosu buraya işaret ediyor)

---

## Yeni oturum buradan devam ediyor — ilk üç iş

Bu plan başka bir oturumda uygulanmak üzere yazıldı. Sırayla:

1. **PR #21'in durumuna bak.** Adım 7b ve 8 artık commit'li ve `feat/flow-ui-pr3`
   dalında duruyor; PR açıldı. Merge edildiyse `main`'e dön ve oradan dallan,
   edilmediyse aynı dalın üstüne devam et — her iki hâlde de yeni tur **kendi
   commit'ini** alır. (Planın ilk hâli bu turu "commit'lenmemiş 14 dosya" diye
   tarif ediyordu; 8 Ağustos'ta ikiye ayrılıp commit'lendi.)
2. **Kanıtı tazele.** `.venv/bin/python -m pytest tests/ -q` → 1106 yeşil olmalı.
   Değilse önce onu çöz; yeni tur yeşil tabandan başlar.
3. **Adım 11'e geç** (aşağıda). 11 → 12 → 13 sırası bilinçli; gerekçesi en altta.

Faz 0 (Open Design mock) yalnız **12 ve 13** için zorunlu, 11 için değil — 11'in tek
tasarım sorusu (A9) o mock'ta cevaplanıyor, o yüzden 11'in mock'u 12'ninkiyle birlikte
üretilebilir ya da 11 mock'suz da bitirilebilir (A9 düşer, `.acts` iki pill kalır).

---

## Bağlam — bu tur neden var

7 Ağustos'ta Adım 5-6-7a-7b-8 bitti ve `docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md`
yol haritası Adım 9 (arka uç) ile 10 (kozmetik) kalmıştı. Kullanıcı denemede **üç somut açık**
buldu; üçü de o iki adımın kapsamında değil ve üçü de tasarım sözleşmesinin (`docs/flow-ui/`)
zaten söylediği ama teslim edilmemiş şeyler:

1. **Composer'daki (+) düğmesi mevcut medyayı açmıyor.** Sözleşme `flow-redesign-plan.md:222`
   dört maddelik bir menü söz veriyor ("Referans görsel · Ek görsel · Medya'dan seç · Dosyadan
   yükle") ve `:117` seçicinin ölçüsünü bile veriyor (776×570). Uygulamada iki madde var,
   "Medya'dan seç" `static/` genelinde **sıfır** eşleşme.
2. **Medya'da karta tıklamak büyüteci açmıyor.** `window.openViewer` (ölçüm anındaki
   HEAD `55b3356`) dışa verildi ve yalnız `chat.js:905`'e bağlandı; `folders.js` hiç güncellenmedi
   (`git log -S openViewer -- static/` tek commit gösteriyor — kayıp değil, hiç yazılmamış).
   Dahası: karttaki `Referans`/`+Ek` eylemleri **görünmez** çalışıyor — geri bildirimleri
   (`#ref-chip`, `#status`) Medya görünümündeyken `hidden` bir kabın içinde kalıyor.
3. **Mod değiştirince pencere değişiyor.** `#view-image` ve `#view-chat` iki ayrı panel; mod
   anahtarı onları takas ediyor, composer'da da iki ayrı metin kutusu var — yazdığın metin
   mod değişince kaybolmuş gibi görünüyor. Hedef `docs/flow-ui/studio-session.html`: **tek
   döküm, tek composer**. `static/index.html:148-152` ve `:396-401` bu işi kendi yorumlarında
   zaten "PR 2'de yapılacak" diye işaretliyor — yani bilinen, sahiplenilmemiş borç.

Bu plan üç adımı (11 · 12 · 13) tanımlıyor. Sıra: önce ucuz ve bağımsız hata (11), sonra
kullanıcının manşet isteği (12), en sonda yapısal olan (13).

---

## Değişmeyen kısıtlar (§1 — her adımda geçerli)

- **§1.1 id mandalı.** `docs/flow-ui/id-baseline.txt` **152 id'lik dondurulmuş** anlık görüntü;
  düzenlenmez (bir test sayıyı birebir kontrol ediyor). Servis edilmeyen her taban id'si
  `docs/flow-ui/id-defteri.md`'ye satır olarak yazılır (ilk hücre backtick içinde id) **ve** o
  id'ye bakan tüm `$("x")` / `getElementById("x")` / `querySelector("#x")` çağrıları silinir.
  Girintisiz (sütun 0) her `$("id")` servis edilen HTML'de bulunmak zorunda. **id EKLEMEK
  serbesttir** — mandal yalnız kaybı sorar.
- **§1.2 negatif testler ihlal edilmez.** Ratchet/negatif testler (docstring'inde "YOK",
  "asla", "kalmadı" geçenler) silinmez; şekil değişiyorsa iddia **yeniden yazılır**, kaldırılmaz.
- **§1.3 `viewer.js` yeniden yazılmaz.** Yalnız çağrılır. (Adım 13'te sarkan tek bağın
  silinmesi zorunlu ve bu bir yeniden yazım değil — defter testi onu istiyor.)
- **§1.4 kanıtlar.** Her adım sonunda: tam `pytest`, `test_id_contract.py`, **mutasyon turu**
  (her yeni iddiayı bozup kırmızıya döndüğünü göster), tarayıcı konsolu ve
  **1024/1280/1440/1920** ekran görüntüleri. Doğrulama **8799**'da yapılır
  (`.claude/launch.json` → `gpt-image-studio-verify`) — aynı `?v=APP_VERSION` altında tarayıcı
  bayat JS servis ediyor (§0.6 tuzağı).
- **TDD.** Önce kırmızı test. İddialar **kod desenini** arasın, kelimeyi değil — depo bu tuzağa
  iki kez düştü (§0.6, §0.7).
- **Sürüm.** `version.py:12`: gönderilen her build `APP_VERSION`'ı artırır. PR 3 ile
  taban **2.1.0** oldu, dolayısıyla 11 → `2.1.1` (hata düzeltmesi), 12 → `2.2.0`,
  13 → `2.3.0`.
- **Her adım kendi commit'i.** Adım sonunda durulur, kanıt gösterilir, onay beklenir.

---

## Adım 11 — Medya'da karta tıklamak büyüteci açar (hata + görünmez geri bildirim)

**Kök neden (ölçüldü):** `folders.js:611` küçük resmin tek `click` dinleyicisi ve
`setGallerySource(rec)`'e gidiyor; viewer'a giden hiçbir yol yok. İkinci ve bağımsız kusur:
`core.js:113` (`$("composer").hidden = !studio`) yüzünden Medya'dayken `setGallerySource`'un
yazdığı `#ref-chip`/`#status` **gizli kapların içinde** — eylem çalışıyor, geri bildirimi yok.
`canAddExtra`'nın Türkçe reddi de aynı sebeple görünmüyor. (Bu, §0.8'de kayıtlı "görünmez
durum satırı" dersinin aynısı.)

**Sözleşme:** `docs/flow-ui/media-browser.html` — kart tıklaması büyüteci açar
(`if (e.target.closest('.acts')) return;` muhafızıyla), `.acts` şeridinde **İndir · Referans**
durur.

### Kararlar
- **A1** Kart tıklaması büyüteci açar; bağ `<img>`'den **karta** taşınır (tüm karo hedef olur).
- **A2** Dışlama tek muhafızda toplanır: `.acts`, `.card-del`, `.card-check` (mevcut
  `stopPropagation`'lar kalır — kemer + askı).
- **A3** **Seçim modu kazanır:** `if (selectMode) { toggleSelected(rec.id); return; }` `openViewer`
  çağrısından **önce**. Test sırayı indeksle mandallıyor.
- **A4** "Referans yap" artık `.acts` içinde açık bir düğme; `folders.js:611` **silinir**.
- **A5** `.acts`'ın durum değiştiren iki eylemi önce **Stüdyo'ya döner**:
  `showSection("studio"); setGallerySource(rec);` (aynı sırayla). Sebep yukarıdaki görünmezlik.
  `İndir` navigasyon yapmaz. `showSection` core.js'te üst düzey tanım, olay anında çağrılıyor —
  yükleme sırası kuralının izin verdiği yol.
- **A6** `.card .acts`'a `pointer-events: none`, çocuklarına `pointer-events: auto`
  (`style.css:1119-1132`). `opacity:0` bir öğe tıklamayı yutuyor; şeridin boş sol yarısı kartın
  tıklamasını yiyordu. `.card-badge` (1106) zaten aynı şeyi yapıyor.
- **A7** Kart klavyeyle erişilir: `tabIndex = 0`, `role="button"`, `aria-label` moda göre
  ("büyüt" / "seç"), `keydown`'da **`if (e.target !== card) return;`** — `chat.js:908-910`'daki
  gizli çift-tetikleme kopyalanmaz.
- **A8** `.card img { cursor: zoom-in }` ve `img.title` → "Büyütmek için tıkla · taşımak için
  klasöre sürükle". Seçim modu override'ı (`style.css:1190`) özgüllükle kazanmaya devam ediyor.
- **A9** `.acts` = **İndir · Referans · +Ek** (3 pill) ve `.card .acts { flex-wrap: wrap }`.
  Ölçüm: S/M/L karo genişlikleri 110/150/210 → kullanılabilir 94/134/194px; üç pill ≈181px,
  yani S ve M'de sarıyor. Sarma Faz 0 mock'unda gözle onaylanır; onaylanmazsa `+Ek` düşer ve
  gerekçesi yazılır.

### Dokunulan dosyalar
`static/folders.js` (`renderGallery` 596-696) · `static/style.css` (1091, 1119-1132) ·
`version.py`

### Testler (önce kırmızı) — `tests/test_index.py`
Yardımcı: `_render_gallery_body()` (regex `function renderGallery\(\)\s*\{(.*?)\n\}`).

| # | Test | İddia (kod deseni) |
|---|---|---|
| A-T1 | `test_a_gallery_card_opens_the_full_viewer` | `` window\.openViewer\(\s*`/output/\$\{rec\.filename\}` `` · `getBoundingClientRect()` · `img.draggable = false` |
| A-T2 | `test_the_thumbnail_click_is_no_longer_the_edit_shortcut` | `img.addEventListener("click"` **yok**; konumsal: `"Referans"` < `setGallerySource(rec)` < `acts.className` |
| A-T3 | `test_select_mode_still_wins_over_the_viewer` | handler diliminde `selectMode` indeksi `openViewer`'dan küçük |
| A-T4 | `test_card_actions_are_excluded_from_the_card_click` | `.acts`, `.card-del`, `.card-check` üçü de `closest(...)` listesinde |
| A-T5 | `test_the_invisible_action_row_does_not_swallow_card_clicks` | `.card .acts` bloğunda `opacity: 0` **ve** `pointer-events: none`; çocuk kuralında `pointer-events: auto` |
| A-T6 | `test_a_gallery_card_is_reachable_by_keyboard` | `card.tabIndex = 0`, `role="button"`, `aria-label`, keydown'da `"Enter"`/`" "`/`e.target !== card`/`preventDefault()` |
| A-T7 | `test_making_a_gallery_image_the_reference_lands_where_it_is_visible` | `showSection("studio")` indeksi `setGallerySource(rec)`'ten küçük (aynısı `addGalleryExtra`), + CSS'te `#composer[data-mode="director"] … #status` kuralının varlığı (navigasyonun neden zorunlu olduğunun kanıtı) |
| A-T8 | `test_the_gallery_viewer_keeps_the_download_seam` | `viewer.js`'te `path.startsWith("/output/")` · `folders.js`'te `openViewer` — kartın verdiği URL biçiminin indirme dikişini açtığını mandallar |

**Mutasyon:** `openViewer` çağrısını sil → A-T1 · img click'i geri koy → A-T2 · `selectMode`
dalını aşağı al → A-T3 · `.acts`'ı listeden çıkar → A-T4 · `pointer-events` sil → A-T5 ·
`tabIndex`/`e.target !== card` sil → A-T6 · `showSection`/`setGallerySource` sırasını takas et → A-T7.

---

## Adım 12 — Composer'ın (+) menüsünden açılan **Medya seçici**

**Kullanıcı kararları (kilitli):** kapsam **yalnız Medya** (üretilen/içe aktarılan + klasörler);
Kütüphane bindirme varlıkları bugünkü `#overlay-picker`'da kalır. Commit **tek seçim + iki
düğme**: "Referans yap" (birincil) ve "Ek olarak ekle" (ana referans yokken kapalı + sebebi yazılı).

### Kararlar
- **B1 · Sahibi `static/folders.js`**, sekizinci bir dosya değil. Gerekçe: `folderCache`,
  `folderById`, `folderPath`, `loadAllImages`, `matchesSearch` zaten orada. Asıl risk sekizinci
  dosyanın `tests/test_id_contract.py:36 JS_FILES`'a eklenmemesi — o zaman içindeki tüm `$()`
  bağları mandalın **dışında** kalır. (Not: `test_index.py:541` sekizinci dosyayı yakalamıyor;
  yalnız yedi dosyanın göreli sırasını mandallıyor. Bu deliği kapatmak ayrı bir iş olarak yazılır.)
  Bölüm banner'la sınırlanır (`// ══ Medya seçici … ══`), testler o dilimi kesip iddia kurar.
- **B2 · "Tümü" `loadAllImages()` ile toplanır, satır içine kopyalanmaz.** `GET /api/history`
  klasör-dışlayıcı (klasörsüz VEYA tek klasör; "hepsi" ucu yok). `test_index.py:1659` bu
  fonksiyonun adını ve `folderCache` referansını zaten mandallıyor.
- **B3 · Seçici kendi kopyasını tutar.** `pickerImages` / `pickerScope` / `pickerQuery` /
  `pickerSelectedId` / `pickerToken`. `historyCache`, `searchQuery`, `selected` ve
  `renderGallery()` **hiç yazılmaz** — Medya'nın arkadaki durumu bozulmasın.
- **B4 · Sol gezinme:** Tümü · Klasörsüz · her klasör (`folderPath` ile tam yol etiketi) ·
  İçe aktarılanlar. Sayılar `<em>` içinde. `imported` bir **bölme değil kesişen süzgeç** —
  yorum satırında yazılı olmalı yoksa biri "toplam tutmuyor" diye düzeltmeye kalkar.
- **B5 · Arama yeniden kullanılır:** `matchesSearch(rec, q = searchQuery)` imzasına çevrilir;
  tek yüklem, iki çağıran. Mevcut test (`function matchesSearch\([^)]*\)` + haystack alanları)
  bunu bozmadan geçiyor.
- **B6 · Ret gerekçesi tek kaynakta.** `core.js`'e `extraBlockReason(rec)` eklenir; `canAddExtra`
  ve `addGalleryExtra` onu kullanır, seçici de **gösterim için** çağırır
  (`$("picker-use-extra").disabled = !!why`). Türkçe cümleler kodda bir kez geçer (test sayıyor).
- **B7 · Commit davranışı bilerek asimetrik:** "Referans yap" → `closePicker(); setGallerySource(rec);`
  (bu sırayla — `setGallerySource` odak veriyor, açık `aria-modal` arkasına odak verilmez);
  "Ek olarak ekle" → seçici **açık kalır** (3 ek slotu var, her biri için menüden dönmek saçma),
  `#picker-note` "Eklendi · N/3" der, slot bitince düğme kendi gerekçesiyle kapanır.
- **B8 · Seçici `statusEl` yazmaz.** Yönetmen modunda `#status` `display:none`, Görsel modunda
  modalın arkasında. Tek geri bildirim yüzeyi `#picker-note` (`role="status"`).
- **B9 · Sıralama bu adımda YOK, yazılı olarak erteleniyor.** `#sort-btn` hiçbir yerde ship
  etmedi ve **D10** olarak Adım 10'un (Medya sıralaması) işi. Yalnız modalda sıralama koymak,
  arkasındaki görünümde olmayan bir kontrol demek — "çalışmayan arama kutusu konmadı" kuralının
  tersi. Seçici `created_at`'e göre azalan sabit sırayla gelir; erteleme `flow-redesign-plan.md:117`
  yanına ve Adım 10 tablosuna yazılır.
- **B10 · Katman ve Escape.** `openPicker()` önce `closeSheets()` çağırır (`.sheet` ve `.modal`
  aynı z-index 50; açık kalan sheet "Escape neyi kapatır" belirsizliği yaratır). Seçicinin kendi
  Escape'i `confirm-modal` muhafızlı + `stopImmediatePropagation`. `folders.js:510`'daki seçim
  modu Escape'ine `&& $("media-picker").hidden` eklenir (yoksa tek Escape hem seçiciyi kapatır
  hem seçim modundan çıkarır). Menü kapanışı için `core.js:195`'teki diziye `"media-pick-btn"`
  eklenir — yoksa menü modalın arkasında açık kalır.
- **B11 · İki kapı değil.** "Bu görseli referans yap" iki yerden erişilebilir olacak (Medya
  kartı + seçici) ama: gizli düğmeye programatik `.click()` yok; iki yüzeyde yalnız biri
  `.primary`; **tek uygulama** var (`setGallerySource`); niyetler farklı (Medya yönetim,
  seçici besteleme). Yasak olan kapı şu: seçici Kütüphane varlıklarına ikinci kapı **olmaz** —
  test `assetCache`/`overlay-picker`/`logo-modal`/`/assets/logos` referanslarının yokluğunu sorar.

### Markup (`static/index.html`)
- `#plus-menu`'ye `<hr>` + `#media-pick-btn` ("Medya'dan seç"). "Dosyadan yükle" **eklenmez** —
  `#upload-btn`/`#extra-add-btn` zaten dosya yolu; dördüncü madde aynı `#file-input`'a ikinci kapı olurdu.
- `#logo-modal`'dan sonra, `#viewer`'dan önce `#media-picker.modal[hidden]` bloğu (13 yeni id:
  `media-pick-btn`, `media-picker`, `picker-search`, `picker-close`, `picker-kinds`, `picker-grid`,
  `picker-empty`, `picker-preview-img`, `picker-meta`, `picker-use-ref`, `picker-use-extra`,
  `picker-note`). **Hiçbir id kaldırılmıyor → defter satırı yok.**
- Kart `class="picker-card"`, **`modal-card` DEĞİL**: `style.css:464-465`'teki
  `.modal-card label/input` kuralları arama pill'ini blok yapar ve girdiyi yeniden giydirir
  (`#palette-hue` için zaten yazılmış tuzağın aynısı).

### CSS (`static/style.css`) — mock'tan port, **her seçici yeniden adlandırılarak**
`.modal.three→.picker-card` · `.modal-head→.picker-head` · `.modal-nav/.nav-item→.picker-nav/.picker-nav-item`
· `.modal-body→.picker-body` · `.asset-grid/.asset→.picker-grid/.picker-tile` (çakışma: uygulamada
`.asset-grid` zaten Kütüphane'nin) · `.modal-side→.picker-side` · `.side-preview→.picker-preview`
· `.kv→.picker-kv` · `.empty→.picker-empty`. `.popover hr` olduğu gibi portlanır.
`.primary` ve `.btn-ghost` yeniden kullanılır (`.btn-ghost:disabled` doğru semantik;
`.primary:disabled`'ın `cursor: progress`'i bu kod tabanında "üretiliyor" demek — kullanılmaz).
Token eşlemesi: `--surface→--panel`, `--surface-2→--panel-2`, `--surface-3→--raised`,
`--fg→--text`, hairline'da `--hairline` / kontrol kenarında **`--control-border`**,
seçili karo `--accent` (durum rengi — "seçili görsel çerçevesi" sözleşmede sanksiyonlu).
Geometri: `width: min(776px, 94vw); height: min(570px, 88vh)`; ızgara `208px | 1fr | 236px`.
`.picker-grid` `repeat(auto-fill, minmax(96px, 1fr))` — orta sütun 292px, 132px'te 2 sütun
çıkıyor; aritmetik yorumda yazılı.

### Testler (önce kırmızı) — seçilmiş çekirdek
`_picker_js()` (banner'lar arası dilim) ve `_section(html, "media-picker")` yardımcılarıyla:
menü maddesi + modal markup'ı servis ediliyor · seçici `fetch("/api/history`/`?folder_id=`
**içermiyor** (yalnız `loadAllImages`) · `historyCache`/`renderGallery`/`selected` yazılmıyor ·
`.click()` yok · `statusEl` yok · seçim `pickerSelectedId`'den okunuyor,
`querySelector('[aria-selected')` ile DEĞİL · "Önce ana görseli seç" cümlesi core.js'te **bir kez** ·
"Referans yap" `closePicker()`'dan **sonra** `setGallerySource` çağırıyor · "Ek olarak ekle"
`closePicker()` çağırMIYOR · Escape muhafızı `confirm-modal` + `media-picker` · `core.js:195`
dizisinde `media-pick-btn` · composer'da hâlâ tam iki `.primary` · seçicide `overlay-picker`/
`assetCache`/`logo-modal`/`/assets/logos` **yok** · `#sort-btn` **yok** (bilinçli erteleme).

---

## Adım 13 — Tek döküm, tek composer (`studio-session.html`)

Mod değiştirince görünen pencere ve yazılan metin değişmez. Tuval = döküm; üretim sonuçları
döküme akar (Adım 7a'nın `.chat-result` kartı zaten var).

### Kararlar
- **C1 · Hayatta kalan id'ler / defter satırları.**
  - Panel: `#view-image` ve `#view-chat` **kalkar**, yerine tek **`#view-studio`**. Böylece
    `SECTION_VIEWS` dört bölüm → dört görünüm biçiminde tekdüze olur ve `VIEWS`/`VIEW_ORDER`/
    `showView` tümden silinir. → **2 defter satırı.**
  - Metin kutusu: **`#prompt` kalır**, `#chat-input` gider (1 satır). Kutu artık `maxlength`
    taşımaz (iki farklı sınır var), sınır JS'te moda göre uygulanır (C3).
  - Gönder: **`#go` kalır**, `#chat-send` gider (1 satır).
  - Durum: **`#status` kalır**, `#chat-status` gider (1 satır); `chatStatus()` `statusEl`'e yazar
    (26 çağrı yeri değişmeden çalışır).
  - Önizleme: `#preview`, `#preview-empty`, `#preview-img`, `#preview-clear` gider (4 satır).
  - **`#progress`, `#progress-fill`, `#progress-pct` KALIR** — düğüm silinmez, **taşınır**:
    `startProgress()` onu bekleyen üretim kartının içine `appendChild` eder. Defter churn'ü
    3 satır azalır ve `startProgress`/`stopProgress` şeklini korur.
  - Toplam **9 defter satırı**; her biri gerekçe + JS bağının nerede silindiği + hangi testin
    güncellendiği ile yazılır.
- **C2 · Mod anahtarı.** `showView` yerine `setMode(name)`: `currentMode`, `$("composer").dataset.mode`
  (tek sahip), `.active` + **`aria-pressed`** (`role="tablist"/"tab"`/`aria-selected` → `role="group"`;
  `index.html:396-401` bunu zaten öngörüyor), placeholder değişimi, `syncSendButton()`, `syncTabThumb()`.
  `#tab-image`/`#tab-chat`/`#view-tabs-thumb` **kalır** (mod anahtarının kendisi). ⌘J korunur.
  **`.view-in-*` animasyonu ölmez, işi değişir:** panel takası bitti ama **bölüm** geçişleri
  (Stüdyo↔Medya↔Kütüphane↔Araçlar) duruyor — animasyon oraya bağlanır, testi docstring'i
  güncellenerek yaşar (§1.2: iddia yeniden yazılır, silinmez).
- **C3 · Tek gönder düğmesi.** `core.js`'te `submitComposer()` → moda göre `run()` veya
  **`sendChat()`** (argümansız — `sendChat(event)` tıklama olayını `display` alanı sanardı;
  o ders korunur ve testi yeniden yazılır). `settings.js:136` bağı `submitComposer`'a döner.
  Etiket moda göre: Görsel'de `renderSource()`'un hesabı (Üret / Görseli düzenle / Görselleri
  birleştir), Yönetmen'de "Gönder". Kilit: `(image && !configured) || (director && !chatConfigured) || busy`.
  Karakter sınırı `maxlength` yerine gönderimde: Görsel'de `MAX_PROMPT_CHARS` (4000), Yönetmen'de
  `MAX_CHAT_MSG_CHARS` (6000) — aşınca **kırpma yok, Türkçe ret** (`applyToForm` geleneği).
- **C4 · Üretim kartı.** `beginResultTurn` kullanıcı balonunu basarken bir de
  `.chat-result.is-pending` iskelet kartı ekler (`n` kadar boş kare); `startProgress()`
  `#progress`'i o kartın içine taşır; `appendResultTurn` iskeleti gerçek sonuç kartıyla
  değiştirir; `dropPendingTurn` onu kaldırır. Döküm doluysa (kart yok) `#progress` dökümün
  sonundaki varsayılan yuvasında kalır. `chat.js` **`startProgress` çağırmaz** — mevcut test korunur.
- **C5 · Sürükle-bırak.** `.stage` gidince referans-bırakma hedefi `#view-studio` olur.
  "Galeri ile İÇ İÇE OLMAMA" değişmezi korunur (`#view-studio` ve `#view-media` kardeş
  bölümler). Boş durum metni (`#preview-empty` → `#chat-empty`) "bir görseli buraya
  sürükle-bırak" cümlesini devralır.
- **C6 · `#ref-chip`'e küçük resim.** Büyük önizleme gidince yüklenen referansın görüntüsü
  kaybolmasın diye çip mock'taki gibi (`studio-session.html:165-171`) bir `<img>` taşır.
  Sözleşmenin "bugünkü tüm yetenekler temsil edilmiş" ölçütü bunu gerektiriyor.
- **C7 · K21 yürürlükten kalkar.** Tek kutu olunca "Yönetmen'e sor"un metin taşıma/birleştirme/
  ret mantığı gereksiz: düğme `setMode("director"); $("prompt").focus()` olur (mock'un kendi
  satırı). Adım 8'in dört testi **silinmez, yeniden yazılır**: yeni değişmez "metin TAŞINMAZ
  çünkü kutu ortak; mod değişir, metin yerinde kalır". Karar kaydında K21'in neden ve neyle
  değiştiği yazılır.
- **C8 · `showPreview` zinciri.** `showPreviewSrc`/`clearPreview` silinir; `setCurrentImage`
  kalır (`#logo-add-btn` kapısı ona bağlı). `run()` `setCurrentImage(images[0])` çağırır.
  `viewer.js`'teki `#preview-img` bağı silinir (defter testi zorunlu kılıyor; §1.3 ihlali değil).
  `assets.js:424`'ün `showPreview(image)` çağrısı `setCurrentImage(image)` + `loadHistory()` olur.

### Yeniden yazılacak testler (silinmez)
`test_chat_workspace_markup_is_served` · `test_chat_view_is_hidden_on_first_paint` ·
`test_view_switching_updates_aria_selected` (→ `aria-pressed`) ·
`test_apply_to_form_switches_to_the_image_view` (→ `setMode("image")`) ·
`test_chat_does_not_reuse_the_image_progress_bar` (iddia korunur: `startProgress` chat.js'te yok) ·
`test_the_send_button_does_not_leak_the_click_event_into_the_display_field` (→ `submitComposer`) ·
`test_ask_director_*` (dördü, C7) · `test_the_hand_off_still_goes_through_the_mode_switch` ·
`test_the_view_transition_only_animates_compositor_properties` + `test_reduced_motion_…` (bölüm
geçişine bağlanır) · `test_chat_prompt_char_limit_mirrors_the_server`.

### Yeni testler (önce kırmızı)
Tek panel (`#view-studio` var, `view-image`/`view-chat` yok) · mod değişimi dökümü **gizlemiyor**
(`setMode` gövdesinde `.hidden` yazımı yok) · tek metin kutusu (`chat-input` hiçbir JS'te yok) ·
`#prompt`'ta `maxlength` **yok** ama iki sınır da gönderimde kontrol ediliyor · `submitComposer`
moda göre dallanıyor ve `sendChat()`'i argümansız çağırıyor · bekleyen kart `is-pending` ve
`#progress` onun içine taşınıyor · başarısızlıkta iskelet kaldırılıyor · sürükle-bırak hedefi
`#view-studio` ve galeriyle iç içe değil · `#ref-chip` küçük resim taşıyor · "Yönetmen'e sor"
metni taşımıyor (mod değiştiriyor).

### Regresyon listesi
`openChat` üç dallı replay · `#chat-sidebar`'ın `openSheet` dışı sınıf-toggle'ı ·
`viewer.js` bağının silinmesi · `assets.js` bindirme sonrası akış · `#logo-add-btn` kapısı ·
`renderSource()`'un `$("go").textContent` yazımı · seçim modu Escape'i · `#chat-gate` ·
Adım 12'nin seçicisi (yalnız `setGallerySource`'un iç yapısı değişir, adı durur).

---

## Faz 0 — Open Design mock (12 ve 13'ten önce, onay kapısı)

Daemon boş (`list_projects` → `[]`). Tek proje: **`gpt-image-studio-flow`**.
`docs/flow-ui/flow.css` **birebir kopyalanır** (yeniden yazılmaz — mock'un `library-assets.html`
ve `media-browser.html` ile karşılaştırılabilir kalmasının tek yolu), örnek görseller
`docs/flow-ui/assets/`'ten alınır.

| Ekran | Kaynak | Neyi cevaplıyor |
|---|---|---|
| `media-card-actions.html` | `media-browser.html` + `.acts` = İndir · Referans · +Ek | Üç pill 110/150/210px karolara sığıyor mu, sarma kabul edilebilir mi (**A9 kararı burada verilir**) · kart odak halkası |
| `media-picker-modal.html` | `library-assets.html` | 208/332/236 bölünmesi 776px'te · orta sütunda kaç karo · iki düğmeli commit alanının ağırlığı · kapalı "Ek olarak ekle"nin okunabilirliği |
| `studio-single-thread.html` | `studio-session.html` + bekleyen üretim kartı + küçük resimli ref çipi | İskelet kartın döküm içindeki ağırlığı · `#progress`'in kart içindeki yeri · tek gönder düğmesinin iki moddaki etiketi |

**Onay kapısı — hiçbir port bunlar doğru olmadan başlamaz:** (1) `flow.css` dışında CSS
yazılmadı (port edilecek tek blok `library-assets.html`'in satır içi 12-53'ü), (2) A9 kararı
verildi, (3) üç bölmeli düzen onaylandı, (4) mock yalnız `static/flow-tokens.css`'te **var olan**
token'ları kullanıyor — port bir **ad** eşlemesi olmalı, **değer** icadı değil.

---

## Doğrulama (her adımın sonunda)

```bash
.venv/bin/python -m pytest tests/ -q
```

```bash
.venv/bin/python -m pytest tests/test_id_contract.py -q
```

Sonra: mutasyon turu (her yeni iddia bozulup kırmızıya döndüğü gösterilir) → `preview_start`
ile **8799** doğrulama sunucusu (`gpt-image-studio-verify`) → yeni sekmede konsol **0 mesaj** →
1024×700 / 1280 / 1440 / 1920'de yatay taşma 0 + ekran görüntüsü → geliştiricinin verisine
**yazmadan** canlı tur. Hepsi temiz olmadan commit yok.

---

## Sıra ve bağımsızlık

**11 → 12 → 13.** 11 ucuz ve bağımsız (temiz geri alınabilir hata düzeltmesi). 12, 11'in
`.acts` kararını varsayar ama teknik bağımlılığı yok. 13 en riskli olan; en sona bırakılıyor ki
iki temiz adım bankada olsun. 12 ile 13 gerçekten bağımsız: 13, 12'nin eklediği hiçbir şeyi
değiştirmiyor (`setGallerySource`'un **adı** duruyor, yalnız iç yapısı sadeleşiyor). İstenirse
13 öne alınabilir — bedeli seçicinin composer'ın son hâline karşı bir kez daha gözden geçirilmesi.

Bu turdan sonra eski yol haritası devam eder: **Adım 9** (tema kalıcılığı → `prefs.json`,
Kütüphane "Yüklemeler" + "Tümü") ve **Adım 10** (kozmetik süpürme; **D10 sıralaması burada hem
Medya'ya hem seçiciye gelir**, bkz. B9). Karar bekleyenler: K14 (sonuç kartında "Düzenle"/"+ Ek"),
D17 (klasör yeniden adlandırma), DM Sans bundle.
