# Flow Stüdyo — tek döküm turu (Adım 11 · 12 · 13) — uygulama planı

**Tarih:** 7 Ağustos 2026 (Adım 0 · commit ayrımı: 8 Ağustos)
**Dal:** `feat/flow-ui-pr4` — Adım 7b (`f9227de`) + Adım 8 (`f35b5c6`) **PR [#21](https://github.com/Zenginby/kromis/pull/21)** ile `main`'e indi (rebase merge, 8 Ağustos)
**Başlangıç:** `4375062` (`main` ucu · `APP_VERSION` = **2.1.0**), `pytest` **1106 yeşil**, çalışma ağacı temiz
**Tasarım sözleşmesi:** `docs/flow-ui/flow-redesign-plan.md` (referans ekranlar `docs/flow-ui/*.html`)
**Önceki plan:** `docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md` (Adım 0–8 orada; §0.1 tablosu buraya işaret ediyor)

---

## Yeni oturum buradan devam ediyor — ilk üç iş

Bu plan başka bir oturumda uygulanmak üzere yazıldı. Sırayla:

1. ~~**PR #21'in durumuna bak.**~~ **Yapıldı (8 Ağustos).** PR #21 **rebase** ile
   merge edildi; Adım 7b (`f9227de`) ve 8 (`f35b5c6`) `main`'de, ağaç hash'i dal
   ucuyla birebir (`3e8756a`). Bu tur `main`'den dallanan **`feat/flow-ui-pr4`**
   üstünde ilerliyor. Not: GitHub'ın rebase merge'ü fast-forward **değil**,
   commit'leri yeniden yazar — dal üstündeki eski SHA'lara (`0223a19`,
   `2d97d94`) atıf veren dokümanlar bu turun ilk commit'inde düzeltildi.
2. **Kanıtı tazele.** `.venv/bin/python -m pytest tests/ -q` → 1106 yeşil olmalı.
   Değilse önce onu çöz; yeni tur yeşil tabandan başlar.
3. ~~**Adım 11'e geç.**~~ **Bitti (8 Ağustos, `c65fbb7`, `APP_VERSION` 2.1.1).**
   Karar kaydı ve kanıtlar **§0.9**'da; A9 ölçümle reddedildi (şerit iki pill).
   PR **[#22](https://github.com/Zenginby/kromis/pull/22)** rebase ile
   `main`'e indi (8 Ağustos). 1. maddedeki not **yine geçerli çıktı**: rebase merge
   fast-forward mümkünken bile commit'leri yeniden yazdı (`b79dc17` → `c65fbb7`,
   `6cf86f4` → `2bfd87e`), atıflar bu turun commit'inde düzeltildi.
4. ~~**Adım 12.**~~ **Bitti (8 Ağustos, `APP_VERSION` 2.2.0).** Faz 0 kapısı **§0.10**,
   port ve doğrulama kapısının bulduğu üç kusur **§0.11**, PR'dan sonra çalıştırılan
   **inceleme turunun** bulduğu iki HIGH ve düzeltmeleri **§0.12** (K28 · K29).
   PR **[#23](https://github.com/Zenginby/kromis/pull/23)** açık.
   Sıradaki iş **Adım 13**; bekleyen kararlar **K27** (iç içe klasör yolu) ve
   **M1** (`aria-selected` düz `<button>`da geçersiz) — ikisi de D10 turunda.

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

## Adım 11 — Medya'da karta tıklamak büyüteci açar (hata + görünmez geri bildirim) — **BİTTİ** (`c65fbb7`)

> Aşağıdaki bölüm **planın kendisi** (uygulama öncesi hâli, olduğu gibi bırakıldı).
> Ne olduğu, A9'un nasıl karara bağlandığı ve plandan bilerek ayrılan iki nokta
> için **§0.9**'a bak.

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

## §0.9 Adım 11 — karar kaydı ve kanıtlar (bitti, 8 Ağustos, `c65fbb7`)

Adım 11 planlandığı gibi indi; **iki nokta** plandan bilerek ayrıldı, ikisi de
ölçüme dayanıyor.

**K23 · A9 reddedildi: şerit iki pill kalıyor (İndir · Referans).** Plan üçüncü
pill'i (`+Ek`) Faz 0 mock'unda gözle onaylatmayı öneriyordu; mock yerine 8799'da
**gerçek karolarda ölçüldü**, çünkü ölçülecek şey zaten canlı yerleşimdi:

| Yoğunluk | Karo | Şeride kalan | 3 pill (184.8px) | 2 pill (131.8px) |
|---|---|---|---|---|
| S | 113px | 97px | 3 satır · karonun **%89**'u | 2 satır · %58 |
| M | 154px | 138px | 2 satır · %43 | 1 satır · %21 |
| L | 237px | 221px | 1 satır · %13 | 1 satır · %14 |

S'de şerit görselin kendisini yutuyordu (ekran görüntüsüyle onaylandı). Planın
yazılı yedeği uygulandı: `+Ek` düştü. **Bedel açıkça kabul edildi:**
`addGalleryExtra`'nın tek çağıranı oydu, yani galeri görselini ek referans yapma
yolu Adım 12'nin seçicisi gelene kadar YOK. Hafifletici ve kararı taşıyan gerekçe:
o düğme Medya'da zaten **görünmez** çalışıyordu (geri bildirimi `hidden` composer'ın
içindeydi), yani çalışan bir özellik değil tamamlanmamış bir yol geri çekildi.
`addGalleryExtra` **silinmedi**: Adım 12'nin B6/B7'si onu ve `canAddExtra`'yı
adıyla yeniden kullanmayı şart koşuyor; core.js'te çağrısız beklediği
gerekçesiyle yorumlandı.

**K24 · A-T3'ün dilimi `activateCard`'a taşındı.** Plan iddiayı tıklama
dinleyicisinin gövdesinde tarif ediyordu; kart A7 ile klavyeden de etkinleşince
iki dinleyici aynı gövdeyi çağırır oldu. Dalı iki yere kopyalamak, birinde seçim
modunu unutmakla biten ayrışma olurdu — değişmez ("seçim modu büyütecin önünde")
aynı yerde, yalnız tek kopya hâlinde. Testin docstring'i sebebi yazıyor (§1.2:
iddia yeniden yazılır, kaldırılmaz).

**Tuzağa üçüncü kez düşüldü ve yakalandı.** A9'un yeni testi ilk hâlinde `"+Ek"`
**kelimesini** arıyordu ve kendi gerekçe yorumuna takılıp kırmızı kaldı; iddia
kod desenine (`.textContent = "+Ek"`) çevrildi. §0.6 ve §0.7'nin dersi aynen
geçerli: **iddia kodu arar, kelimeyi değil.**

**Kanıtlar.** `pytest` 1106 → **1115** (9 yeni test, silinen yok) ·
`test_id_contract.py` 6 yeşil (kaldırılan id yok → defter satırı gerekmedi) ·
**12 mutasyonun hepsi kırmızıya döndü** (A-T1…A-T9 + pointer-events'in iki yarısı
+ flex-wrap) · 8799'da canlı tur: kart tıklaması büyüteci açtı ve indirme dikişi
`download="a5fefdf98088.png"` ile `/output/` önekinden türedi (A-T8 kodda değil
**gerçekte** doğrulandı), "Referans" büyüteci açmadan Stüdyo'ya döndü ve çip
görünür oldu (`#go` → "Görseli düzenle"), seçim modu kazandı, kart içi düğmeden
gelen Enter kartı tetiklemedi · tarayıcı konsolu **0 mesaj**, sunucu hatası yok ·
**1024/1280/1440/1920**'de yatay taşma **0** (taşan tek şey kapalı yan çekmecenin
`translateX(-320px)` park hâli — mevcut davranış, kaydırma üretmiyor) ·
geliştiricinin verisine **yazılmadı** (`history.json`/`chats.json` mtime'ları
7 Ağustos'ta kaldı).

---

## Adım 12 — Composer'ın (+) menüsünden açılan **Medya seçici** — **BİTTİ**

> **Faz 0 kapısı kapandı (8 Ağustos) — bkz. §0.10.** Mock `docs/flow-ui/media-picker-modal.html`.
> Bölünme **`208 / 388 / 180`** (K25), ret cümlesi **"Önce ana görseli seç."** (K26).
> Mock'un ölçtüğü beş düzeltme aşağıdaki CSS bölümüne işlendi. **Port başlayabilir.**
>
> **Port bitti; doğrulama kapısının bulduğu iki kusur kapatıldı — bkz. §0.11.**
> `APP_VERSION` 2.1.1 → **2.2.0**.

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
Geometri: `width: min(776px, 94vw); height: min(570px, 88vh)`; ızgara **`208px | 1fr | 180px`**
(K25 · §0.10). `.picker-grid` `repeat(auto-fill, minmax(96px, 1fr))` → **ölçüldü: 333px ızgara,
3 sütun × 103px**; 132px'lik eski min bu genişlikte bile 2 sütunda kalırdı, yani 96px kararı
3. sütunu açan şey. Aritmetik yorumda yazılı.

**Mock'un ölçtüğü beş düzeltme de bu bölümün parçası** (gerekçeler §0.10'da):
`.picker-tile`'ın `<button>` `padding`'i **sıfırlanır** · karo görseli `.thumb` değil
uygulamadaki **medya kartı** desenini kullanır ve kabı `display: block` olur ·
`.picker-preview img`'e **`height: auto`** · `.btn-ghost`'un **kapalı hâli tanımlanır**
(`--muted` metin, `--border` kenar, `not-allowed`) · `.picker-kv` etiketi değerin **üstüne**
alır (180px yan bölmede uzun klasör adı sarıyor).

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

## §0.10 Faz 0 — Adım 12'nin mock'u teslim edildi (8 Ağustos) — **onay bekliyor**

**Teslim.** `docs/flow-ui/media-picker-modal.html` (493 satır, kardeş ekranların yanında,
göreli `flow.css` + `assets/` ile). Open Design projesi **`gpt-image-studio-flow-574a`**
(daemon gerçekten boştu, `list_projects` → `[]`); `flow.css` oraya **birebir** kopyalandı
(`shasum` iki tarafta da `62610ea1…`), örnek görseller `docs/flow-ui/assets/`'ten geldi.
Kanonik kopya depoda; Open Design'daki eşi gözle inceleme içindir. Yerel servis:
`.claude/launch.json` → **`flow-ui-mock`** (8801, `docs/flow-ui` kökü). Not: `.claude/`
`.gitignore:26` ile hariç, yani bu giriş **yerel** — başka bir makinede elle eklenir.

**Kapı maddelerinin durumu.** (1) ✅ tek satır içi blok, `library-assets.html:12-53`'ün portu;
her sapma yorumla gerekçeli. (2) ✅ A9 zaten §0.9'da ölçümle kapandı — bu mock'un konusu değil.
(3) ⏳ **karar sizde**, ölçümler aşağıda. (4) ✅ `flow-tokens.css` `flow.css`'in `:root`'unun
birebir kopyası olduğundan mock'un kullandığı her token uygulamada var; yeni değer yok.

**Ölçüm — kapının 2. sorusu (776×570'te orta sütun).**

| Bölünme | Izgara | Sütun | Karo | Bir bakışta | Bedeli |
|---|---|---|---|---|---|
| **Sözleşme** 208 / 332 / 236 | 277px | **2** | 133px | ≈5 karo | tarama dar |
| **Geniş ızgara** 208 / 388 / 180 | 333px | **3** | 103px | ≈9 karo | önizleme 203→147px; künyede "Kandil kapakları" iki satıra sarıyor |
| **Dar gezinme** 168 / 400 / 208 | 345px | **3** | 107px | ≈9 karo | klasör adları **kırpık** ("Kandil ka…") |

Mock üçünü canlı geziyor (`Bölünmeyi değiştir`), ölçüm modalın altında yazılı.
Sol gezinme etiketleri yalnız **dar** seçeneğinde kırpılıyor (üçü de ölçüldü).
**B-CSS'in `minmax(132px→96px)` değişikliği sözleşme bölünmesinde sütun sayısını
DEĞİŞTİRMİYOR** (her ikisi de 2 veriyor); 96px yalnız dar bölünmede 3. sütunu açıyor.
Dar bölünmenin bedeli: sol gezinmede klasör adları kırpılıyor ("Kandil ka…").

**Mock'un çözdüğü, plana yazılmamış beş şey** (hepsi ölçüldü, port'a taşınacak):
1. `.asset` `<button>`'ının UA `padding`'i (`1px 6px`) sıfırlanmalı — yoksa 133px'lik karo
   121px'lik görsel taşıyor. Kütüphane'de `.thumb`'ın kendi boşluğu bunu gizliyor.
2. Karo görselinde `.thumb` yerine flow.css'in kendi **`.media`** bileşeni kullanılıyor
   (opak üretim görseli; dama deseni + `contain` şeffaf marka varlıkları içindi).
   `display:block` gerekiyor: `.media` satır içi kutuda `aspect-ratio` çalışmıyor.
3. `.side-preview img`'e `height: auto` — `max-height:100%` esnek kolonda çözülmüyor,
   `height` özniteliği kazanıp önizlemeyi 1000px yapıyordu.
4. **`#media-picker` sınıfla değil `hidden` ile kapanmalı.** Kapalı `.modal-wrap` yalnız
   `opacity:0 + pointer-events:none`; ölçüldü: içindeki **25 kontrol sekme sırasında kalıyor**.
   Planın markup'ı zaten `[hidden]` diyor — JS'in de sınıfın yanında özniteliği çevirmesi şart.
5. `.btn-ghost`'un **kapalı hâli flow.css'te yok**; kapalı "Ek olarak ekle" açık görünüyordu.
   Mock'ta token dışına çıkmadan tanımlandı (`--muted` metin, `--border` kenar, `not-allowed`).

**Ayrıca:** `#picker-note` **`--danger` değil `--muted`** — bu bir hata değil karşılanmamış
önkoşul; kırmızı okuyunca kullanıcı yanlış bir şey yaptığını sanıyor. Not iki düğmenin
**altında** duruyor (gerekçe de sayaç da yalnız ikinci düğmeyi anlatıyor). 3/3'te sayaç
gerekçeyi yeniyor: "Eklendi · 3/3", "En fazla 4 görsel gönderilebilir." değil.

**Kanıtlar.** 1024×700 / 1280 / 1440 / 1920'de yatay taşma **0**, modal her yerde 776×570,
1024'te ray 72px'e iniyor · tarayıcı konsolu **0 mesaj** · `impeccable detect` **1 uyarı**
(`flat-type-hierarchy`, 11.5/12/13/14px) — **kardeş `library-assets.html` birebir aynı tek
uyarıyı veriyor**, yani port edilen blokla geldi, mock eklemedi; sözleşmenin tip ölçeği
kilitli olduğu için bilerek bırakıldı · klavye: karo `:focus-visible` halkasını alıyor
(2px `--accent`, offset −2px) · B7'nin asimetrisi çalışıyor ("Referans yap" kapatıyor,
"Ek olarak ekle" açık bırakıp 1/3 → 2/3 → 3/3 sayıyor, 4. denemede düğme kapanıyor).

**İki soru karara bağlandı (8 Ağustos, kullanıcı) — kapı KAPANDI:**

- **K25 · S1 → "geniş ızgara" `208 / 388 / 180`.** Seçicinin işi düzinelerce görsel
  arasından birini bulmak; 2×133px (≈5 karo) tarama için dar. Dar gezinme (168px) 3.
  sütunu daha ucuza alıyordu ama kapsamı daraltmanın **birincil aracını** — klasör
  adlarını — kırpıyor, o yüzden reddedildi. Bedeli kabul edildi: yan önizleme 203→**147px**
  (karo zaten 103px, yargıyı hâlâ o taşıyor) ve künyede uzun klasör adı sarıyor —
  **port'ta `.picker-kv`'de etiket değerin üstüne alınarak çözülür**, `justify-content:
  space-between` yerine iki satır. **`flow-redesign-plan.md:117`'deki "776×570 + kendi iç
  navigasyonu" satırına bölünme yazılır** (ölçü değişmiyor, yalnız iç dağılım).
  → Plan §"CSS"teki `ızgara 208px | 1fr | 236px` **`208px | 1fr | 180px`** olur;
  `minmax(96px, 1fr)` aynen kalır (3 sütunu açan tam da o — 132px'te 2 sütunda kalırdı).

- **K26 · S2 → ret cümlesi `"Önce ana görseli seç."`** Parantez (`Görsel ekle veya
  galeriden Düzenle`) düşüyor: Adım 11'de galeri kartının "+Ek"i ölçümle kaldırıldığından
  o kurtuluş yolu **artık yok**, yani cümle bugün bile yanlış yol tarif ediyor. Kısa hâli
  her yüzeyde doğru; kurtuluş yolunu yüzeyin kendi bağlamı söylüyor. B6'nın "Türkçe
  cümleler kodda bir kez geçer" kuralı korunuyor (`extraBlockReason` tek kaynak,
  `canAddExtra` onu çağırır). `core.js:474`'ün metnini mandallayan test tek satırda
  güncellenir — silinmez (§1.2).

---

## §0.11 Adım 12 — port bitti; doğrulama kapısının bulduğu iki kusur (8 Ağustos)

**Süit tek başına yetmedi.** Port yazıldığında 22 yeni iddia ve tüm süit (1137) yeşildi.
Kapının geri kalanı — mutasyon turu + canlı tur — **üç şey** buldu; üçü de yeşil süitin
altından geçmişti. Kayıt, "hangi iddia türü neyi kaçırır" dersinin devamıdır (§0.6/§0.7/§0.9).

**1 · `renderPicker` adı `palette.js` ile çarpışıyordu — seçici BOMBOŞ açılıyordu.**
`static/palette.js:96` aynı adı çoktan kullanıyor (renk seçicinin render'ı) ve `index.html`'de
folders.js'ten **sonra** yükleniyor. Klasik script'ler tek global kapsamı paylaştığı için
sonraki tanım öncekini **sessizce** eziyordu: `openPicker()` medya seçicisini değil renk
paletini çiziyordu. Konsolda tek satır hata yok, süit yeşil, ekran boş — çünkü hiçbir iddia
"bu ad başka dosyada da tanımlı mı" diye sormuyordu. Ad `renderMediaPicker` oldu.
**Mandal `test_id_contract.py`'ye yazıldı** (`test_hicbir_ust_duzey_ad_iki_dosyada_tanimli_degil`):
yedi dosyanın üst düzey `function`/`const`/`let` adları taranır, çarpışma varsa kırmızı.
Bu, yalnız seçiciyi değil **gelecekteki her adımı** koruyan bir mandal — Adım 13 aynı global
kapsamda `setMode`/`showView` etrafında iş yapacak.

**2 · `folderPath` bir etiket değil, klasör NESNELERİNDEN oluşan zincir döndürüyor.**
Plan B4 "`folderPath` ile tam yol etiketi" diyordu; fonksiyon `path.unshift(node)` ile dizi
döndürüyor. `textContent`e verilince sol gezinmedeki üç klasör de, künyedeki "Klasör" satırı
da **"[object Object]"** yazıyordu. Süit yeşildi çünkü hiçbir iddia **değerin türünü**
sormuyordu — kelime aramasının tuzağının tür hâli. Tek üretim yeri `pickerFolderLabel`
oldu; ayraç kod tabanından alındı (`" / "`, `folders.js:106`'daki kırıntı başlığıyla aynı).

**3 · Mutasyon turunda bir iddia hayatta kaldı** (`…reads_its_selection_from_state…`).
`"aria-selected\"]" not in picker` yalnız TEK bir yazımı yakalıyordu; gerçek regresyon
`querySelector('[aria-selected="true"]')` diye yazılır ve o dizede `aria-selected`'ın
ardından `=` gelir, `"]` değil. İddia tırnak biçimine bakmayan hâle çevrildi: sorgunun
**argümanı** taranıyor. Bu, kelime aramasının **dördüncüsü** (§0.6, §0.7, §0.9 CSS'te).

**Mutasyon turu.** 22 iddianın her biri için üretim kodunda hedefli bir bozma yapıldı ve
o testin kırmızıya döndüğü gösterildi: **23/23 kırmızı** (bir iddia iki farklı yazımla
sınandı). Sonradan eklenen iki mandal da kendi regresyonlarıyla kırmızıya döndü.

**Kanıtlar (8799, geliştiricinin verisine yazmadan).** Süit **1139 yeşil** ·
konsol kendi kodumuzdan **0 mesaj** (tek giriş `favicon.ico` 404'ü — uygulamanın süregelen
hâli, `index.html`'de de `app.py`'de de favicon yok, HEAD'de de yoktu) · **1024×700 / 1280 /
1440 / 1920**'de yatay taşma **0**, modal her yerde **776×570** ve ekran içinde ·
ızgara dördünde de **3 sütun × 103px** — §0.10'un ölçtüğü sayının **canlıda birebir doğrulanması**
(kaydırma çubuğunun 15px'i dahil, ızgara 333px) · kapsam sayıları bölmeyi tutuyor
(Tümü 25 = Klasörsüz 19 + 0 + 1 + 5; İçe aktarılanlar 1 **kesişiyor**) · B7 canlı doğrulandı:
"Referans yap" kapatıp **sonra** odağı `#prompt`'a veriyor, "Ek olarak ekle" seçiciyi açık
bırakıp 1/3 → 2/3 → 3/3 sayıyor ve dördüncü denemede kendi gerekçesiyle kapanıyor ·
B10 canlı doğrulandı: seçim modu **açıkken** tek Escape yalnız seçiciyi kapatıyor, mod ayakta
kalıyor · kapalı modalda **0** odaklanabilir kontrol (Faz 0 mock'unda 25'ti) ·
manifest `mtime`'ları tur öncesi/sonrası **birebir aynı**.

**Kapatılmayan, bilerek:** (a) `.picker-body`'nin kaydırma çubuğu platformun varsayılanı —
depoda `scrollbar` için **tek kural yok** (0 eşleşme), yani seçici her yüzeyle aynı davranıyor;
buraya özel kural yazmak "port bir **ad** eşlemesidir, **değer** icadı değil" kuralını çiğnerdi.
(b) 208px'lik gezinmede **iç içe** klasörün tam yolu kırpılıyor ("Kandil kapakları / test" →
"Kandil kapaklar…") ve ebeveyniyle neredeyse aynı görünüyor; `title` tam yolu veriyor.
§0.10'un ölçümü **kök** adlarını ölçmüştü, iç içe yolu değil. Karar gerektirir (K27 adayı:
yaprak adı + girinti mi, tam yol mu) — D10 turuna bırakıldı.

---

## §0.12 Adım 12 — inceleme turu: yeşil süitin altından geçen iki geri bildirim kusuru (8 Ağustos)

PR **#23** açıldıktan **sonra** kod incelemesi çalıştırıldı. O anda süit 1139 yeşildi,
mutasyon turu 23/23 kırmızıydı, canlı tur temizdi. **Yine de iki HIGH çıktı** — ikisi de
§0.9'un kök nedeninin (eylem çalışıyor, **geri bildirimi görünmüyor**) yeni kılığı, ikisi de
canlı ölçüldü. Ders şu: mutasyon turu **iddiaların** gücünü ölçer, **iddia edilmeyen** şeyi
değil. İkisi de "kullanıcıya ne yazıyoruz" sorusuydu ve hiçbir iddia notun **içeriğine**
bakmıyordu.

**H1 · Sayaç ret gerekçesini yutuyordu — kapalı düğme sebepsiz kalıyordu (K28).**
Not `extras.length ? sayaç : gerekçe` idi. Yorumun savunması ("3/3'te sayaç gerekçeyi yener,
yoksa az önce olanı söylemeden reddi tekrarlamış oluruz") **doğruydu** — ama yalnız
**kapasite** gerekçesi için. Koşul gerekçeye değil `extras.length`e bağlandığı için **ilk ek
eklendiği anda** diğer iki gerekçe de susuyordu. Canlı ölçüm (ana referans A, ek olarak B):

| Seçili karo | `extraBlockReason` | düğme | not (eski) | not (yeni) |
|---|---|---|---|---|
| B — ek listesinde | `Bu görsel zaten ek referans listesinde.` | kapalı | `Eklendi · 1/3` | gerekçe |
| A — ana referans | `Bu görsel zaten ana referans.` | kapalı | `Eklendi · 1/3` | gerekçe |
| C — eklenebilir | — | açık | `Eklendi · 1/3` | `Eklendi · 1/3` |

Kullanıcı `1/3` okuyup (yer var) ölü düğmeye basıyordu. Artık **gerekçe varsayılan olarak
kazanıyor**. Düzeltmedeki gerçek gerilim şuydu: ekleme başarılı olduğunda seçili karo **artık**
ek listesindedir, yani `why` o an da doludur — gerekçeyi koşulsuz öne almak "Eklendi" onayını
öldürürdü. Çözüm onayı **çağrı yerine** taşımak: `renderPickerSide` gerekçeyi tercih eder,
"Ek olarak ekle" dinleyicisi ekleme **anında** sayacı yazar. Kapasite ucu da canlı ölçüldü:
3. ek eklenince `Eklendi · 3/3`, sonra başka karoya geçilince
`En fazla 4 görsel gönderilebilir.` — yani gerekçe kapalı düğmeyi **payda ima etmeden**
açıklıyor, eski hâlden de iyi.

**H2 · `#picker-empty` üç durumu tek cümleyle anlatıyordu (K29).**
`openPicker()` `loadAllImages()`i `await` ediyor ama **reddi yakalamıyordu**; içerideki
`if (!res.ok) continue` yalnız HTTP hatasını süzüyor, `Promise.all(fetch…)` ağ reddinde komple
düşüyor. `window.fetch` reddedecek şekilde saplandığında ölçülen:

```
yakalanmamisRet:         ["TypeError: Failed to fetch"]     → düzeltmeden sonra []
kullaniciyaGorunenMetin: "Bu kapsamda görsel yok"           → "Görseller alınamadı."
```

Yükleme çökmüşken kullanıcıya **yanlış bir cümle** söyleniyordu. Aynı kök neden ikinci
belirtiyi de veriyordu: `renderMediaPicker()` `await`'ten **önce** çağrıldığı için boş durum
**her açılışta** bir an görünüyordu (ölçüldü: açılışın ilk karesinde
`picker-empty.hidden === false`, `await` sonrası 25 karo) — yerelde göz kırpma, uzak/yavaş
sunucuda kalıcı, çünkü `loadAllImages` klasör başına bir istek atıyor (N+1). Artık
`pickerState` üç durumu ayırıyor: **yükleniyor · alınamadı · gerçekten boş**.

### İkinci geçiş — düzeltmenin kendisi eksikti (aynı gün)

İlk düzeltme commit'lenmeden **çekişmeli bir doğrulama turundan** geçirildi: üç ayrı mercek
(doğruluk · gerileme · yorum-kod uyumu) diff'i bağımsız okudu, her aday bulgu ayrı bir
ajan tarafından **çürütülmeye** çalışıldı. Üç bulgu ayakta kaldı ve **üçü de gerçekti.**
Ders §0.11'inkinin devamı: **mutasyon turu iddiaların gücünü ölçer, iddia EDİLMEYEN şeyi
değil.**

**(a) H2'nin ilk düzeltmesi asıl hata yolunu kaçırıyordu.** `fetch` HTTP hatasında
**reddetmez** — `res.ok === false` ile çözülür — ve `loadAllImages` onu `continue` ile
yutuyordu. Yani `try/catch` **yalnız ağ katmanı** kesintisini yakalıyordu; sunucu 500
döndürdüğünde liste boş geliyor, `pickerState` "ready" oluyor ve kullanıcı gene
"Bu kapsamda görsel yok" okuyordu. Erişilebilir somut yol kodun kendi belgesinde:
`storage._read_history` yalnız `JSONDecodeError`ı yutuyor, docstring'i "Other errors
(e.g. permission errors) still propagate" diyor → izin/IO hatası `/api/history`yi 500'e
çeviriyor. **Düzeltmenin düzeltmesi:** `loadAllImages` artık `{ images, failed }`
döndürüyor (sayı dönüşte taşınıyor, modül değişkeninde değil — iki çağıran çakışabilir) ve
`openPicker` "boş liste + düşen uç" bileşimini hataya çeviriyor. Kısmi arıza bilerek
akışı bozmuyor: bir klasör düşse de gerisi geliyor, ızgara doluyor.

**Yazdığım yorum yanlıştı ve yanlış hâliyle bu belgeye de geçmişti.** "`Promise.all`
bilerek… sinyal fail-loud yukarı geliyor" diyordu; oysa yutma bir kat **aşağıda**,
`loadAllImages`'ın döngüsündeydi. Bu depoda yorum bir tasarım kaydı ve testler onu
alıntılıyor — yanlış bir değişmez sonraki okuyucuyu yanıltır. Hem yorum hem K29'un
docstring'i gerçeğe çekildi. (`catch`in `console.error` yazmaması **doğru** kaldı: deponun
kapısı "konsol 0 mesaj" ve sinyal kullanıcının gördüğü cümleye çevriliyor — yutulan değil,
**çevrilen** bir hata.)

**(b) K29'un `"loading"` kolu kendi bekçiliğini yapamıyordu.** İddia `_picker_js()`
diliminin tamamında `pickerState = "loading"` arıyordu; **bildirim satırının kendisi**
(`let pickerState = "loading";`) o dilimde olduğu için iddia hep karşılanıyordu. Mutasyonla
ölçüldü: `openPicker`'daki **sıfırlama** silindiğinde süit **1141 yeşil** kalıyordu (kontrol:
`"error"` silinince 1 kırmızı — yani iddia bütün olarak zayıf değil, yalnız o kol). Davranış
sonucu gerçek: hatadan sonra tekrar açılışta taze istek uçarken ekranda "Görseller alınamadı."
asılı kalırdı. İddia artık `_balanced_body(picker, "async function openPicker()")` gövdesine
bakıyor.

**(c) "Eklendi · N/3" hiç eklenmemiş karoya yapışıyordu.** H1 düzeltmesi aynı dizeye
**ikinci bir anlam** yüklemişti (duran sayaç *ve* eylem onayı). B eklendikten sonra hiç
eklenmemiş C'ye geçince not "Eklendi · 1/3" diyordu, düğme açıktı — kullanıcı C'yi de
eklemiş sanabilirdi. `#picker-note` `role="status"`, yani ekran okuyucuda **yapılmamış
eylemin duyulur onayı**. Fiil ayrıldı: duran okuma **"Ek referans · N/3"**, onay yalnız
ekleme anında **"Eklendi · N/3"**. Yazdığım "«Eklendi» onayı BURADA verilmiyor" yorumu da
hemen altındaki satırı yanlış tarif ediyordu; düzeltildi.

**Bonus:** `#picker-empty` canlı bölge değildi. Kap artık yalnız "boş" demiyor,
"yükleniyor" ve "alınamadı" da diyor — `role="status"` verildi. Yanındaki `#picker-note`
zaten canlıydı; asimetriyi bu diff imal etmişti.

**Yeni iddialar.** `test_the_picker_note_shows_the_reason_not_just_the_counter` (K28) ·
`test_the_picker_separates_loading_and_failure_from_emptiness` (K29). Mutasyon turu
**8/8 kırmızı**: sayacın gerekçeyi ezmesi · onayın çağrı yerinden düşmesi · duran okumanın
da "Eklendi" demesi · `try/catch`in kalkması · boş durum metninin yeniden yalnız sorguya
bakması · **açılıştaki `"loading"` sıfırlamasının silinmesi** (önceki turda hayatta kalan
mutant) · düşen uç sayısının yok sayılması · `role="status"`un kalkması. Her JS mutantı
ayrıca `node --check`ten geçirildi — geçersiz JS olan bir mutant "gerçekçi gerileme"
sayılmaz, testi yanlış nedenle kırmızı yapar.

**Kanıtlar (8799, geliştiricinin verisine yazmadan).** Süit **1141 yeşil** (1139 + 2) ·
konsol kendi kodumuzdan **0 mesaj** (yalnız süregelen `favicon.ico` 404'ü ve tarayıcının
parola alanı notu; bilerek çökertilen `fetch`ler bile yeni giriş üretmedi) ·
**yakalanmamış promise reddi 0**. Dört arıza biçimi ayrı ayrı ölçüldü:

| Senaryo | Ekranda | Karo |
|---|---|---|
| HTTP 500 (tüm uçlar) | `Görseller alınamadı.` | 0 |
| kısmi (kök 200, klasör 500) | ızgara dolu, boş durum gizli | 19 |
| ağ reddi | `Görseller alınamadı.` | 0 |
| hatadan sonra tekrar açılış | `Görseller yükleniyor…` → ızgara | 25 |

Not akışı da adım adım ölçüldü: eklenebilir karo → boş · az önce eklendi →
`Eklendi · 1/3` · **hiç eklenmemiş karo → `Ek referans · 1/3`** · tekrar seçilen ek →
`Bu görsel zaten ek referans listesinde.` · ana referans → `Bu görsel zaten ana referans.`
En dar bağlayıcı genişlikte (**1024×700**, en uzun yeni cümleyle): yatay taşma **0**, modal
**776×570** ve tümüyle ekran içinde, boş durum kutusu kartın içinde, `role="status"` yerinde ·
`output/*.json` `mtime`'ları tur öncesi/sonrası **birebir aynı**. Geometri değişmediği için
§0.11'in dört genişlikli süpürmesi geçerliliğini koruyor — bu tur metin değişikliği,
yerleşim değişikliği değil.

**İncelemenin geri kalanı, kapatılmadan bırakıldı.** 1 MEDIUM + 5 LOW, tam kayıt
`.claude/reviews/pr-23-review.md`'de. En önemlisi **M1**: `aria-selected` düz `<button>`
üzerinde **desteklenmiyor** (yalnız `gridcell · option · row · tab · treeitem` rollerinde) ve
canlı erişilebilirlik ağacında 25 karonun hiçbirinde "selected" **geçmiyor** — gören kullanıcı
2px accent çerçeveyi görüyor, ekran okuyucu kullanıcısı hangi görselin seçili olduğunu
bilmiyor, oysa "Referans yap" tam o seçime göre çalışıyor. Deponun doğru kullanımı
`role="tab"` üzerinde (`core.js:71`); seçici ondan ayrılmış. Asgari geçerli düzeltme
`#picker-grid`e `role="listbox"` + karoya `role="option"` (CSS aynı kalır); tam listbox klavye
kalıbı (ok tuşları + roving tabindex) ayrı bir iş. **K27 ile birlikte D10 turuna** bırakıldı.

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

**Durum (8 Ağustos):** 11 bitti (`c65fbb7`, PR #22), **12 bitti** (§0.11) — sıra **13**'te.

Bu turdan sonra eski yol haritası devam eder: **Adım 9** (tema kalıcılığı → `prefs.json`,
Kütüphane "Yüklemeler" + "Tümü") ve **Adım 10** (kozmetik süpürme; **D10 sıralaması burada hem
Medya'ya hem seçiciye gelir**, bkz. B9). Karar bekleyenler: K14 (sonuç kartında "Düzenle"/"+ Ek"),
D17 (klasör yeniden adlandırma), **K27 (seçicinin gezinmesinde iç içe klasör etiketi, §0.11)**,
DM Sans bundle.

> ## Durum denetimi (2026-08-22) — bu turun tamamı bitti
>
> Yukarıdaki "sıra 13'te" satırı eskidi. Bugün depoda:
>
> - **Adım 13 bitti** — tek döküm/tek composer yerinde: tek `#prompt`, tek `#go`,
>   mod anahtarı `#plus-btn`'in yanında; `tests/test_playwright_studio.py` bu akışın
>   E2E mandalı (Playwright kurulu olmayan koşumda temiz SKIP veriyor).
> - **Adım 9 ve 10 bitti** (11 Ağustos, PR #25) — tema `prefs.json`'a yazılıyor,
>   Kütüphane'de "Yüklemeler" + "Tümü", kozmetik süpürmenin altı maddesi
>   (`#chats-kebab`, `#media-sort-btn`, `.folder-thumb`, `#media-rail-count`,
>   `#media-empty-state`, `#folder-rename`).
> - **D17 bitti** — `#folder-rename` + `PATCH /api/folders/{id}`.
> - **DM Sans bundle bitti** (15 Ağustos) — `static/fonts/` iki woff2 + `OFL.txt`,
>   mandalı `tests/test_fonts.py`.
>
> **Hâlâ açık üç madde** (bugün koda bakılarak doğrulandı, hiçbiri kapanmadı):
>
> | Madde | Bugünkü hâli |
> |---|---|
> | **K14** — sonuç kartında "Düzenle" / "+ Ek" | Kartta yalnız "İndir" var (`chat.js`), ikisi de gelmedi — kararın kendisi "tam geçmiş kaydı ister" diyordu, o kayıt hâlâ yok |
> | **K27** — seçicide iç içe klasör etiketi | `picker-tile` künyesi yalnız en yakın klasörün adını yazıyor (`folders.js`), kök→klasör zinciri yok |
> | **M1** — `aria-selected` düz `<button>`da geçersiz | Hâlâ öyle: `picker-tile` düz `<button>`, kapsayıcı `#picker-grid` düz `<div>`; ne `role="listbox"` ne `role="option"` var (`folders.js`) |
