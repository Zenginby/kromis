# Flow arayüz devri — uygulama planı

**Tarih:** 6 Ağustos 2026
**Dal:** `feat/flow-ui`
**Başlangıç:** `25713f8` (v1.17.0), çalışma ağacı temiz
**Tasarım sözleşmesi:** `docs/flow-ui/flow-redesign-plan.md`

Arayüz Google Flow'un tasarım diline taşınıyor. Tasarım kararları **verilmiş
ve onaylanmış**; bu dosya onları koda çevirme sırasıdır. Yeniden tasarım yok:
`docs/flow-ui/` altındaki `flow.css` + 6 ekran referans uygulamadır.

---

## 0.0 Revizyon — 6 Ağustos, uygulama öncesi denetim

Plan koda dökülmeden önce depoda doğrulandı; altı madde değişti.

| # | Bulgu | Karar |
|---|---|---|
| A | §0'ın `cp` komutu `settings-panels.html`'i atlamış — tablo ve tasarım §7 onu sayıyor ama depoya girmemişti. Renk seçici **ve** dişliden açılan Ayarlar paneli o dosyada. | Kopyalandı (25 582 bayt). Referans ekran sayısı 5 değil **6**. |
| B | Referans ekranlar uygulamanın id sözleşmesini kullanmıyor: ekranlarda 159 id var, uygulamada 152, **kesişim 21** (9'u `viewer*`). | Beklenti netleşti: bu kopyala-yapıştır değil, **işaretlemeyi yeniden yazıp 152 id'yi yeni iskelete dağıtma** işi. |
| C | §1.1'in "boş id diff" kuralı, tasarımın gerçekten kaldırdığı öğelerle (sekmeler, üst şerit araması) çelişiyor. | id sözleşmesi **esnek** oldu: kaldırılan öğenin testi de güncellenir. Boş diff yerine **§1.1'deki id defteri + `tests/test_id_contract.py`** geçti. |
| D | §2 Adım 1'in "flow.css'i sonra yükle → geri alma tek satır" varsayımı yanlış: `flow.css`'in 70 sınıfının **15'i** `style.css`'teki sınıflarla aynı adı taşıyor, sonra yüklenen kazanır. | Adım 1'de yalnızca `:root` bloğu alınır (`static/flow-tokens.css`, 28 token). Bileşen CSS'i Adım 3'e kalır. §2 Adım 1'e yazıldı. |
| E | `static/fonts/` yok; DM Sans bundle'ı sıfırdan. | İndirmeye izin verildi. Türkçe için **`latin-ext` altkümesi şart**. §4'e yazıldı. |
| F | Vazgeçilen tasarım işi | PR #15 kapatıldı (yorumla), yerel `feat/google-flow-design` dalı silindi. `feat/redesign-v2` origin'de duruyor. |
| G | **Adım 1'in ölçümü:** metin kapıları geçiyor ama §8'in "kontrol komşu yüzeye karşı ≥3:1" kapısı ölçülen Flow paletiyle sağlanamıyor (`--border` 0.10 → 1.21:1, `--border-strong` 0.18 → 1.55:1). Ayrıca `textarea/select/input` dinlenme sınırı `transparent`tı: metin girişlerinin algılanabilir sınırı yoktu. | Yalnızca **etkileşimli** sınır yükseldi: `--control-border: rgba(255,255,255,0.36)` (ölçüm: 3.14–3.31:1, kapıyı geçen en sessiz değer). Dekoratif kenarlar, panel kenarları ve disabled hâller Flow'a **birebir** kaldı. Ölçülen paletten ayrıldığımız **tek yer**; gerekçe `style.css`'in köprü katmanında yazılı. |

**Ritim:** adım adım. Her adımdan sonra durulur, §1.4'teki kanıtlar gösterilir, onay beklenir.

**Baseline (uygulama öncesi ölçüm):** `pytest` → **994 test yeşil**. `static/index.html` → **152 id**.
JS'ten `$()` ile dokunulan id sayısı **145**; bunların **56'sı top-level bağ**.

---

## 0.1 Durum — nerede kaldık (7 Ağustos: PR 1 merge edildi)

**PR 1 bitti ve `main`'e indi.** [PR #16](https://github.com/Zenginby/gpt-image-studio/pull/16)
squash ile merge edildi → `main` = **`a1478d4`**. Merge sonrası ağaç hash'i dal
ucuyla birebir aynı (`a717ef93`), yani squash'ta içerik kaybı yok.

> **Adım commit'leri `main`'in geçmişinde YOK.** Squash tek commit bıraktı;
> aşağıdaki SHA'lar `feat/flow-ui` dalının geçmişine ait ve yalnızca PR #16
> üzerinden erişilebilir (`git log main` içinde bulunamazlar). Dal hem yerelde
> hem `origin`'de duruyor, silinmedi.

| Adım | Durum | Commit (dal geçmişi) |
|---|---|---|
| 0 · tasarımı depoya al | bitti | `3190e37` + `3b5a508` (6. ekran) |
| 1 · token katmanı + id mandalı | bitti | `1dce0aa`, `de1ea91`, `46443a6` |
| 2 · kabuk (ray/şerit/tuval/composer) | bitti | `f13fdd2` |
| 3 · bileşen CSS'i | bitti | `bc14b9a` |
| 4 · temizlik | bitti | `ee867fb` |
| **5–7 · PR 2 birleşik oturum** | **sırada** | — |

Adım 3'te ayrıca: 16 accent-hover kuralı §8'in yüzey yükseltmesine döndü,
`--radius` kalktı (üçlü bileşenlere bağlandı), tuval düzleşti (.stage/.gallery-wrap
kart değil), `.chat-own-input` sınırı `--control-border` oldu (kapı açığıydı).
Adım 4'te ayrıca: `test_the_new_chat_controls_have_a_visible_focus_ring`
listesinden ölü `.chat-new` çıkarıldı (gerekçe docstring'de) ve flow.css'in
global `:focus-visible` kuralı style.css'e alındı — §8'in "her odaklanabilir
öğede halka" şartını ağ olarak kapatıyor.

PR 1'in kanıtları (her adımda toplandı, sonuncusu Adım 4): pytest **1000 yeşil**
(taban 994, +6 id sözleşmesi) · `test_id_contract.py` 6 yeşil (**152 id'nin hepsi
duruyor, id defteri hâlâ boş**) · tarayıcı konsolu 0 hata · 1024×700 / 1280 /
1440 / 1920'de taşan öğe 0 · negatif testler (§1.2) korunuyor.

**PR 1'de bilinçli olarak yapılmayan arayüz işleri** (PR 2 / Adım 7'nin girdisi —
7 Ağustos'ta koda karşı doğrulandı, ikisi de hâlâ açık):

- **Kütüphane ve Araçlar görünüm değil**, ray düğmeleri mevcut modalları açıyor:
  `core.js:122-123` → `$("library-btn").click()` / `$("palette-btn").click()`.
  Görünüme dönüşmeleri `assets.js` / `palette.js` işi.
- **Medya'da arama yok** — `folders.js` tarafı gelmeden çalışmayan bir arama
  kutusu konmadı (işlevsiz işaretleme bilerek eklenmiyor). Referans işaretleme
  `docs/flow-ui/media-browser.html`'de: `.search` + `.sortbtn` + `.sizeseg` (S/M/L).

> Adım 2'nin girdi listesindeki diğer dört madde (accent hover, geometri
> tokenları, kart eylemlerinin sürekli görünürlüğü, yönetmen balonunun aynalı
> kuyruğu) **Adım 3'te kapandı** — bu listeden o yüzden düştüler.

**Adım 4'ün doğrulanmış ölü sınıf listesi** — **silindi (`ee867fb`)**; silme
öncesi yeniden ölçüldü, tuzağa uyuldu (yalnız nokta seçicileri gitti). Kayıt
için liste (7 Ağustos ölçümü: `style.css`'te kural var, `index.html` ve
`static/*.js`'te kullanım yok):

`.modal-version` · `.layout` (+780px sorgusu) · `.ref-row` · `.chat-workspace` ·
`.chat-shell` · `.chat-new` (3 kural) · `.chat-sidebar-toggle` · `.chat-composer`
(+`::before`) · `.chat-input-label` · `.chat-actions` · boş 900px medya sorgusu

(İlk taslaktaki satır numaraları düştü: Adım 3 dosyayı yeniden düzenledi, sonra
Adım 4 bu kuralları sildi — numaralar artık var olmayan bir dosya durumunu
gösteriyordu.)

> **Tuzak:** son ikisi değil ama `.chat-new` ve `.chat-sidebar-toggle` **sınıf**
> olarak ölü, **id** olarak canlı — `#chat-new` ve `#chat-sidebar-toggle` üst
> şeritte duruyor ve JS'ten bağlı. Silinecek olan yalnızca nokta ile başlayan
> seçici. İlk taslakta listede olan `sub` ve `topbar-text` **düştü**: `.sub`
> CSS'te hiç yok, `topbar-text` depoda hiçbir yerde geçmiyor.

**Açık kalan işler (adım dışı).** Üçü de Adım 5'i bloke etmez ama devrin sonunu
bloke eder — ilk ikisi kullanıcı kararı bekliyor:

- **Sürüm numarası:** v1.18.0 mı v2.0.0 mı. Arayüz baştan değişti ve otomatik
  kayıt bilinçli bir ürün kararını tersine çeviriyor (D1) — ikisi de major'ı
  savunur.
- **DM Sans bundle** (§4). İndirme izni alındı; **indirmeden önce dosya adı ve
  boyutu söylenip son onay alınacak.** `latin` + `latin-ext` şart (Türkçe),
  400 + 500.
- **Tema seçici arayüzü** — dört tema (`kurumsal` / `amber` / `viola` / monokrom)
  token katmanında hazır, seçici yok. Yeri sözleşmede belli: Araçlar → Görünüm.

**Devam etmek için (yeni oturum).** Başlangıç hâli: `main` = `a1478d4`, çalışma
ağacı temiz, `pytest` 1000 yeşil. Sıradaki tur **PR 2 / Adım 5** — §3'teki veri
modeli. Bu adım kozmetik değil, **kendi testleriyle gelir: TDD, test önce.**

```
docs/flow-ui/flow-redesign-plan.md ve docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md
dosyalarını tamamen oku (§0.0 revizyonu ve §0.1 durumu dahil). PR 1 merge edildi;
artık arka uçtayız.

Bu turda sadece PR 2 / Adım 5'i yap: §3'teki üç alan (koşullu `session_id`,
`result` rolü, `cover_image_id`) + `result`'ın Azure isteminden ve
MAX_CHAT_TOTAL_CHARS bütçesinden filtrelenmesi. TDD: önce kırmızı test.

Kısıtlar §1'de: göç YOK (koşullu yazım + .get() ile okuma), id sözleşmesi
korunur (§1.1), negatif testler ihlal edilmez (§1.2).

Bitirince §1.4'ün kanıtlarını göster. Hepsi temiz olmadan commit yok.
```

---

## 0. Tasarımı depoya al (ilk commit)

Tasarım dosyaları Open Design proje klasöründe duruyor; versiyonlu olması için
depoya kopyalanır:

```bash
git switch -c feat/flow-ui
mkdir -p docs/flow-ui
OD_PROJ="/Users/kullanici/Library/Application Support/Open Design/namespaces/release-stable-intel/data/projects/a1328958-5998-469c-96fd-ad169db18c0c"
cp -R "$OD_PROJ"/{flow.css,flow-redesign-plan.md,index.html,studio-session.html,media-browser.html,studio-preview.html,library-assets.html,settings-panels.html,assets} docs/flow-ui/
git add docs/flow-ui
git commit -m "docs: Flow arayüz sözleşmesi ve referans ekranlar"
```

`docs/flow-ui/` içeriği:

| Dosya | Ne |
|---|---|
| `flow-redesign-plan.md` | Karar kaydı: ölçülen tokenlar, bilgi mimarisi, veri modeli, riskler |
| `flow.css` | Tasarım sistemi: tokenlar, tema, kabuk, bileşenler |
| `index.html` | Genel bakış + token levhası |
| `studio-session.html` | **Ana ekran** — birleşik oturum, mod anahtarı, oturum drawer'ı |
| `media-browser.html` | Medya — arama, ızgara boyutu, klasör gezinme, çoklu seçim, büyüteç |
| `studio-preview.html` | Önizleme + bindirme paneli (offset kaydırıcıları) |
| `library-assets.html` | Kütüphane modal seçici |
| `settings-panels.html` | Araçlar (görünüm, palet) + dişliden açılan Ayarlar |

Ekranlardaki `assets/samples` görselleri `output/`'tan, `assets/brand` ise
`assets/`'ten kopyalandı — yani referans ekranlar gerçek çıktılarla dolu.

---

## 1. Değişmez kısıtlar

Bunlar tercih değil, sözleşme. Her commit'te geçerli.

### 1.1 id sözleşmesi (en kritik) — **revize edildi, bkz. §0.0/C**

`static/index.html`'de **152 id** var. `core.js:10`'da `const $ = (id) => document.getElementById(id)`;
JS'ten bu yolla **145 id**'ye dokunuluyor. Kritik alt küme: **56 id top-level
bağlanıyor** (dosya yüklenirken çalışan `$("x").addEventListener(...)` satırları):

| Dosya | Top-level bağlı id |
|---|---|
| `assets.js` | 16 |
| `folders.js` | 13 |
| `palette.js` | 11 |
| `core.js` | 7 |
| `settings.js` | 5 |
| `chat.js` | 5 |
| `viewer.js` | 0 |

Bu 56'dan biri kaybolursa `$()` `null` döner, `addEventListener` `TypeError`
atar ve **o dosyanın kalan tüm dinleyicileri hiç kurulmaz**. Yükleme sırası
bağlayıcı: `core.js → folders.js → assets.js → palette.js → settings.js`.

`tab-image` ve `tab-chat` **bu 56'nın içinde** → mod anahtarı bu id'leri
**devralmak zorunda** (tasarım §10.1'in birinci seçeneği; gizli sarmalayıcı
seçeneği artık geçerli değil).

#### Boş diff yerine: id defteri + otomatik kontrol

Kaldırılan öğenin testi de güncellenebildiği için "diff boş olmalı" kuralı
düştü. Yerine iki artefakt geliyor ve **ikisi de `pytest`'in içinde**:

| Artefakt | Ne |
|---|---|
| `docs/flow-ui/id-baseline.txt` | `25713f8`'deki 152 id — dondurulmuş taban |
| `docs/flow-ui/id-defteri.md` | Bilerek kaldırılan her id: **hangi tasarım kararıyla**, JS bağı nerede kaldırıldı, hangi test güncellendi |
| `tests/test_id_contract.py` | Aşağıdaki üç iddiayı doğrular |

1. **Kayıp id yok:** `index.html`'in id'leri ⊇ (taban − defter). Defterde yazmayan
   hiçbir id kaybolamaz.
2. **Sarkan JS bağı yok:** defterdeki hiçbir id `static/*.js`'te `$("…")` /
   `getElementById("…")` olarak **hâlâ geçmiyor.** R1'in gerçek çökme mekanizmasını
   yakalayan iddia bu — eski diff'ten güçlü, çünkü **yeniden adlandırmayı** da yakalar.
3. **Defter dürüst:** defterde yazan bir id `index.html`'de hâlâ duruyorsa hata.

Bu üçlü bir mandal (ratchet): silme ancak yazılı gerekçeyle ve JS bağı birlikte
temizlenerek mümkün. Defter Adım 1'in commit'inde kurulur, işaretleme kıpırdamadan önce.

### 1.2 Negatif testler

`test_index.py` bazı şeylerin **olmadığını** doğruluyor. Yeni işaretlemede
kazara geri gelmemeli:

- `type="color"` (yerini HSV alanı + ton kaydırıcısı aldı)
- `id="edit-panel"` (birleşik akış; ayrı düzenle paneli yok)
- `data-akind="palettes"` (paletler bir "varlık" türü değil)

### 1.3 `viewer.js` yeniden yazılmaz

Büyüteç bugün imleç-sabitli zoom, rubberband pan sınırı, ctrl+wheel pinch,
60px ok adımı ve küçük resimden büyüyerek açılma geçişini yapıyor. Bunlar
korunur; yalnızca `.viewer*` CSS'i Flow yüzeylerine geçer. Dokuz id aynı kalır:
`viewer`, `viewer-stage`, `viewer-img`, `viewer-zoom-out`, `viewer-zoom-pct`,
`viewer-zoom-in`, `viewer-fit`, `viewer-download`, `viewer-close`.
Alt şerit dizilimi de aynı: `− %100 + Sığdır İndir ×`.

### 1.4 Her adımın kabul kriteri — **revize edildi**

1. **`pytest` tamamı yeşil.** Taban: 994 test. Sayı düşerse (esnek karar
   gereği bir test silindiyse) neyin neden silindiği id defterinde yazılı olacak.
2. **`test_id_contract.py` yeşil** — §1.1'in üç iddiası.
3. **Tarayıcı konsolu 0 hata.** Sarkan bir bağın *tek* belirtisi bu: `pytest`
   servis edilen HTML'i okuyor, JS'i çalıştırmıyor. Uygulama açılır, konsol okunur.
   İşaretlemeye dokunan her adımda (Adım 2'den itibaren) zorunlu.
4. **Ekran görüntüsü** — işaretleme veya yerleşim değiştiyse 1024 / 1280 / 1440 / 1920.
   1024×700 en küçük pencere; taşma olmadığı orada görülür.

Hepsi geçmeden commit yok. Her adım sonunda durulur, kanıtlar gösterilir, onay beklenir.
Çıktılar commit mesajına değil, oturum kaydına yazılır.

---

## 2. PR 1 — yeniden giydirme (davranış değişmiyor)

Tamamı kozmetik; testler baştan sona yeşil kalır. Tek başına merge edilebilir.

### Adım 1 — token katmanı — **revize edildi, bkz. §0.0/D**

`flow.css` bütün olarak yüklenmez. Ölçüm: `flow.css`'te 70 sınıf, `style.css`'te
171 sınıf var ve **15'i aynı adı taşıyor** —

`.modal` · `.modal-head` · `.card` · `.row` · `.seg` · `.topbar` · `.icon-btn` ·
`.btn-ghost` · `.btn-danger` · `.progress` · `.viewer-bar` · `.viewer-btn` ·
`.viewer-img` · `.viewer-pct` · `.viewer-stage`

Sonra yüklenen kazandığı için "flow.css'i sonraya koy" hamlesi kozmetik bir
token turu değil, bu 15 bileşeni sessizce yeniden giydirmek olurdu. Bu yüzden:

- `docs/flow-ui/flow.css`'in **yalnızca `:root` bloğu** (28 token)
  `static/flow-tokens.css` olarak alınır. Sınıf kuralı taşınmaz.
- `static/index.html`'de **`style.css`'ten SONRA** yüklenir → geri alma gerçekten
  tek satır, çünkü dosyada sınıf seçici yok.
- `style.css`'teki `:root` (17 token) Flow paletine bağlanır; `--panel` /
  `--panel-2` gibi eski adlar **korunur**, yeni değerlere işaret eder. Böylece
  55 KB CSS yeniden yazılmadan tüm ekran Flow rengine döner.
- Sohbet balonu tokenları (`--chat-user`, `--chat-user-border`, `--chat-bot`,
  `--chat-bot-border`) sıcak turuncuya bağlıydı; nötr yüzeylere yeniden tanımlanır.
- Aynı commit'te **id mandalı** kurulur (§1.1): `id-baseline.txt`, `id-defteri.md`,
  `tests/test_id_contract.py`. İşaretleme kıpırdamadan önce ağ gerilmiş olur.

`flow.css`'in 70 sınıfı Adım 3'te, çakışmalar tek tek çözülerek taşınır.

Ölçülen token değerleri (`flow-redesign-plan.md` §2.1):
`--bg #000000` · `--surface #141415` · `--surface-2 #1e1e1f` ·
`--surface-3 #2a2a2b` · `--selected #353637` · `--selected-strong #4d4e50` ·
`--fg #e8eaed` · `--muted #9aa0a6` · `--primary #ffffff`.
`--accent` temaya bağlı, varsayılan monokrom (`#e8eaed`).

### Adım 2 — kabuk

`static/index.html` yapısı: sol ray (Stüdyo · Medya · Kütüphane · Araçlar +
Daralt) · üst şerit (hamburger + oturum adı + kebab · sağda yeni oturum, dişli,
sürüm) · tuval · yüzen composer.

- Sekmeler görünmez olur ama `tab-image` / `tab-chat` id'leri **yerinde kalır**;
  composer'daki Görsel/Yönetmen mod anahtarı bunlara bağlanır.
- Hamburger, mevcut `chat-sidebar-toggle` id'sine bağlanır; oturum listesi
  `chat-sidebar`.
- Üst şeritteki merkezi arama **kalkar** (arama Medya'ya taşındı).
- Yedekler sol raydan kalkar; dişliden açılan Ayarlar paneline girer.

### Adım 3 — bileşen CSS'i

`rail` · `topbar` · `composer` + `mode` · `thread` · `result` · `media-card` ·
`media-head` · `grid-size` (S/M/L) · `folder-tile` + `crumb` · `slide-over` ·
`segmented` · `chip` · `modal-picker` · `empty-state` · `viewer`.

Eski panel CSS'i hemen silinmez: önce yeni sınıflara devredilir.

### Adım 4 — temizlik

`style.css`'te ölü kalan kurallar silinir. Ölçüt: dosya küçülmeli ve
`pytest` + id diff hâlâ temiz olmalı.

---

## 3. PR 2 — birleşik oturum (arka uç işi)

Konuşma ve üretilen görseller aynı geçmişte tutulur. Bu adım kozmetik değil;
kendi testleriyle gelir. TDD: test önce.

### Adım 5 — veri modeli

Deponun kendi geleneği kullanılır (koşullu yazım + `.get()` ile okuma →
**göç gerekmez**):

1. **Görsel kaydına koşullu `session_id`** — yalnızca bir oturum içinde
   üretildiyse yazılır. `imported: True` ile birebir aynı desen; bugünkü
   kayıtlar bayt bayt aynı kalır (`test_legacy_formats.py` ve galeri testleri
   buna bağlı). Oturum id'si `chats.json`'daki mevcut `id`'dir; yeni bir kimlik
   uzayı açılmaz.
2. **Dökümde üçüncü rol** — `{"role": "result", "image_ids": [...], "params": {...}}`.
3. **Oturum özetine `cover_image_id`** — `chat_store._SUMMARY_FIELDS`'e eklenir
   (liste küçük resmi için; `messages` bilerek dışarıda kalmaya devam eder).

**Zorunlu testler:**

- `result` rolü Azure istemine **gitmiyor** (`chat_client.py` yalnızca
  `user`/`assistant` gönderir).
- `result` rolü `models.py`'deki `MAX_CHAT_TOTAL_CHARS` bütçesine **sayılmıyor**
  (modele gitmiyor).
- Silinmiş görselin sarkan `image_id`'si dökümü çökertmiyor; "görsel silindi"
  yer tutucusu gösteriyor (`storage.delete_many` sonrası).

### Adım 6 — otomatik kayıt (karar D1)

`chat_store.py`'nin başındaki not bilinçli bir kararı anlatıyor: `POST /api/chat`
diske hiçbir şey yazmıyor, yazan tek yol kullanıcının başlattığı `/api/chats`.

**Bu karar 6 Ağustos onayıyla değişti:** oturumlar otomatik kaydedilecek.
Gerekçe: "geçmişte hem konuşmalar hem üretilen görseller tutulsun" isteği
ancak otomatik yazımla karşılanır. Üç güvence:

- her şey yerelde kalır; `output_dir` ve izinler değişmez,
- oturum menüsünde tek tıkla **sil** ve **tümünü sil**,
- Ayarlar'da "oturumları otomatik kaydet" anahtarı; kapatınca bugünkü davranış.

`chat_store.py`'nin başındaki notu bu kararla **güncelle** — silme, "v1.15'te
şu gerekçeyle daraltıldı, 2026-08-06'da şu gerekçeyle açıldı" olarak yaz.

### Adım 7 — JS dokunuş noktaları

`core.js` (composer + döküm render), `chat.js` (mod anahtarı, `result` kartı),
`folders.js` (Medya görünümü: arama, ızgara boyutu, klasör gezinme),
`palette.js`, `assets.js`, `settings.js` (tema + otomatik kayıt anahtarı).
Mantık değişmez; modal→slide-over açma/kapama ve segmented kontrol okuma
yolları eklenir.

---

## 4. Ek işler (atlanırsa paketlemede patlar)

- **DM Sans bundle.** Uygulama paketlenmiş `.app`; ağa bağımlı font olmaz.
  `static/fonts/` bugün **yok**, sıfırdan kurulur. Referans ekranlardaki Google
  Fonts `<link>`'i depoya **girmez**.
  - Altküme: **`latin` + `latin-ext`.** `latin-ext` olmadan ğ/ş/ı/İ/ç/ö/ü
    fallback fonta düşer — arayüz Türkçe, yani bu şart, tercih değil.
  - Ağırlık: 400 + 500 (başlık için 700 gerekirse ayrıca). Her ağırlık ayrı istek,
    bütçe boşa gitmesin.
  - `font-display: swap`; **yalnızca** gerçekten kritik ağırlık `preload` edilir
    (ECC performans kuralı: en fazla iki aile, tek kritik ağırlık).
  - `gpt-image-studio.spec`'e `static/fonts` girdisi + paketten sonra `.app`
    içinde dosyanın gerçekten bulunduğu doğrulanır.
- **Pencere tabanı.** `desktop.py`: `WINDOW_SIZE (1440, 900)`,
  `MIN_WINDOW_SIZE (1024, 700)`. Doğrulama 1024 / 1280 / 1440 / 1920
  genişliklerinde ekran görüntüsüyle yapılır — sadece 1440'a bakmak yetmez.
  1200px altında ray otomatik daralır, 760px yükseklik altında üst şerit 60px.
- **Üretim seçenekleri allowlist'ten gelir:** `azure_client.ALLOWED_SIZES`
  = `1024x1024` · `1024x1536` · `1536x1024`; `ALLOWED_QUALITIES` =
  `low/medium/high`; `n` = 1–4. Segmented kontroller bunlarla eşleşmeli.

---

## 5. Riskler

| # | Risk | Önlem |
|---|---|---|
| R1 | id kaybı → yükleme anında `TypeError`, o dosyanın kalan dinleyicileri hiç kurulmaz (56 top-level bağ) | `test_id_contract.py`: defterde yazmayan id kaybolamaz + defterdeki id'nin JS bağı da silinmiş olmalı (§1.1) |
| R2 | Negatif testlerin ihlali (`type="color"` vb. geri gelir) | §1.2 listesi commit öncesi grep'lenir |
| R6 | Esnek id kararı istismar edilir: iş kolaylaşsın diye test silinir | Defter **gerekçe** ister; silme yalnızca tasarımın gerçekten kaldırdığı öğe için. Her adımda test sayısı ve azalma nedeni raporlanır |
| R7 | `flow.css`'in 15 sınıfı `style.css`'i sessizce ezer | Adım 1 yalnızca `:root` alır; çakışmalar Adım 3'te tek tek çözülür (§2 Adım 1) |
| R3 | 55 KB CSS'te ölü kural birikmesi | Adım 4 temizlik turu |
| R4 | `result` rolü Azure istemine sızar | Filtre için birim testi (adım 5) |
| R5 | Otomatik kayıt `MAX_CHAT_TOTAL_CHARS`'a daha hızlı çarpar | Sonuç kayıtları bütçeye sayılmaz; sınıra yaklaşınca kullanıcıya görünür uyarı |

---

## 6. Adım başına kalıp

Her tur tek adım, sonunda §1.4'ün kanıtları ve onay beklemesi.

> Aşağıdaki kalıp **PR 1'e aitti ve tüketildi** (Adım 1–4 bitti). PR 2'nin
> Adım 5 kalıbı §0.1'in sonunda — arka uç işi olduğu için çerçevesi farklı
> (TDD, "flow.css'i taşı" değil).

```
docs/flow-ui/flow-redesign-plan.md ve docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md
dosyalarını tamamen oku (§0.0 revizyonu dahil). Tasarım sözleşmesi bunlar;
yeniden tasarlamıyorsun, docs/flow-ui/ altındaki flow.css ve 6 HTML ekranı
static/'e taşıyorsun.

Bu turda sadece PR 1 / Adım <N>'i yap.

Kısıtlar §1'de: id ancak defterde gerekçesiyle yazılarak ve JS bağı birlikte
silinerek kaldırılır (§1.1), negatif testler ihlal edilmez (§1.2),
viewer.js yeniden yazılmaz (§1.3).

Bitirince §1.4'ün kanıtlarını göster: pytest, test_id_contract, konsol, ekran
görüntüsü. Hepsi temiz olmadan commit yok.
```

---

## 7. Bitti sayılma ölçütü

- [ ] Sekme yok: tek ray + tek composer; mod anahtarı (+) yanında, klavyeyle erişilebilir
- [ ] Döküm konuşmayı ve üretilen görselleri aynı akışta gösteriyor
- [ ] Arama yalnızca Medya'da; klasörler gezinme (kökte klasör kartları + klasörsüzler)
- [ ] Dört tema da kontrast kapılarını geçiyor; monokrom varsayılan
- [ ] Bugünkü tüm yetenekler yerinde: prompt, boyut/kalite/adet, referans + ek görsel,
      tema rengi/palet, logo/motto/banner + offset, klasörler, çoklu seçim, indirme,
      büyüteç, Azure ayarları, yönetmen sohbeti, yedekler, içe aktarma
- [ ] 1024×700'de taşma yok
- [ ] `pytest` tamamen yeşil (994'ten düşen her test id defterinde gerekçeli)
- [ ] `test_id_contract.py` yeşil: kayıp id yok, sarkan JS bağı yok, defter dürüst
- [ ] Tarayıcı konsolu 0 hata
- [ ] DM Sans `latin-ext` ile paketli; `.app` içinde font dosyası doğrulandı
