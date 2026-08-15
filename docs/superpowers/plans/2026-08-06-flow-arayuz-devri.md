# Flow arayüz devri — uygulama planı

**Tarih:** 6 Ağustos 2026
**Dal:** `feat/flow-ui`
**Başlangıç:** `25713f8` (`APP_VERSION` = **1.16.0**), çalışma ağacı temiz
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

## 0.1 Durum — nerede kaldık (8 Ağustos: PR 1 · PR 2 · PR 3 merge edildi)

**PR 1 bitti ve `main`'e indi.** [PR #16](https://github.com/Zenginby/gpt-image-studio/pull/16)
squash ile merge edildi; `main`'e inen tek commit **`a1478d4`**. Merge sonrası
ağaç hash'i dal ucuyla birebir aynı (`a717ef93`), yani squash'ta içerik kaybı yok.
**PR 2 de indi:** [PR #19](https://github.com/Zenginby/gpt-image-studio/pull/19)
→ **`55b3356`**, Adım 5 + 6 + 7a'nın üçü birden (`APP_VERSION` 2.0.0).
**PR 3 de indi:** [PR #21](https://github.com/Zenginby/gpt-image-studio/pull/21)
**rebase** ile merge edildi (squash değil — dal `main`'in tepesinden 4 commit
ileri, 0 geri olduğu için adım commit'leri ayrı ayrı korunabildi). Adım 7b →
**`f9227de`**, Adım 8 → **`f35b5c6`** (`APP_VERSION` 2.1.0), dokümanlar
`0d02072` + `4375062`.

> **Adım commit'leri `main`'in geçmişinde YOK** (PR 1 ve PR 2 için). Squash her
> ikisinde de tek commit bıraktı; aşağıdaki 0–4 SHA'ları `feat/flow-ui` dalının
> geçmişine ait ve yalnızca PR #16 üzerinden erişilebilir (`git log main` içinde
> bulunamazlar). Dal hem yerelde hem `origin`'de duruyor, silinmedi. 5 · 6 · 7a
> tek satırda `55b3356`'ya işaret ediyor çünkü PR #19 üçünü birleştirdi.
>
> **PR 3 istisna:** rebase merge adım commit'lerini `main`'e ayrı ayrı taşıdı,
> yani 7b ve 8 `git log main` içinde bulunur. Ama rebase SHA'ları **yeniden
> yazdı**: dal üstündeki `0223a19`/`2d97d94` artık yalnız `feat/flow-ui-pr3`
> dalında; `main`'deki karşılıkları `f9227de`/`f35b5c6`. İkisi de aynı ağacı
> taşıyor, atıf verirken `main` SHA'ları kullanılır.

| Adım | Durum | Commit (dal geçmişi) |
|---|---|---|
| 0 · tasarımı depoya al | bitti | `3190e37` + `3b5a508` (6. ekran) |
| 1 · token katmanı + id mandalı | bitti | `1dce0aa`, `de1ea91`, `46443a6` |
| 2 · kabuk (ray/şerit/tuval/composer) | bitti | `f13fdd2` |
| 3 · bileşen CSS'i | bitti | `bc14b9a` |
| 4 · temizlik | bitti | `ee867fb` |
| 5 · veri modeli (PR 2) | **bitti** (7 Ağustos, §0.4) | `55b3356` (PR #19, squash) |
| 6 · otomatik kayıt (PR 2) | **bitti** (7 Ağustos, §0.5) | `55b3356` (PR #19, squash) |
| 7a · JS dokunuş noktaları — **PR 2'nin ekran payı** | **bitti** (7 Ağustos, §0.6) | `55b3356` (PR #19, squash) |
| 7b · JS dokunuş noktaları — PR 1'in giydirme borcu (A1–A6) | **bitti** (7 Ağustos, §0.7) | `f9227de` (PR #21, rebase) |
| 8 · §4.2'nin tamamlanması (devrin manşeti) | **bitti** (7 Ağustos, §0.8) | `f35b5c6` (PR #21, `APP_VERSION` → 2.1.0) |
| 11 · Medya'da büyüteç + kart eylemleri | **bitti** (8 Ağustos, tek-döküm planı §0.9) | `c65fbb7` (PR 4, `APP_VERSION` → 2.1.1) |
| 12 · composer'dan Medya seçici (§4.2'nin (+) menüsü) | kullanıcı denemesinden geldi | — |
| 13 · tek döküm + tek composer (`studio-session.html`) | kullanıcı denemesinden geldi | — |
| 9 · tema kalıcılığı + Kütüphane yüklemeleri | §0.2 denetiminden geldi | — |
| 10 · kozmetik süpürme | §0.2 denetiminden geldi | — |
| — · Yedekler paneli | **ertelendi** (§0.2) | — |

> **Sıra 8'den sonra değişti.** 7 Ağustos denemesinde kullanıcı üç açık buldu ve üçü de
> Adım 9/10'un kapsamında değildi: (+) menüsünde "Medya'dan seç" yok, Medya'da karta
> tıklamak büyüteci açmıyor, mod değişince görünen pencere ve yazılan metin değişiyor.
> Üçü **Adım 11 · 12 · 13** olarak kendi planına yazıldı ve 9/10'un önüne alındı:
> **`docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md`**. Bu dosya (§0.1–§0.8)
> geçmişin kaydı olarak kalıyor; sıradaki turun tanımı orada.

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

**PR 1'de yapılmayan arayüz işleri: bkz. §0.2.** Burada elle tutulan iki maddelik
liste **kaldırıldı** — 7 Ağustos denetimi onun eksik olduğunu gösterdi (wordmark,
kebab, boş durum glifi ve §4.2'nin iki düğmesi listede yoktu). Elle yazılan liste
hafızadan besleniyordu; yerine referans ekranlara karşı ölçülmüş §0.2 tablosu geçti.

> Adım 2'nin girdi listesindeki dört madde (accent hover, geometri tokenları,
> kart eylemlerinin sürekli görünürlüğü, yönetmen balonunun aynalı kuyruğu)
> **Adım 3'te kapandı.**

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

- ~~**Sürüm numarası:** v1.18.0 mı v2.0.0 mı.~~ **Karar (7 Ağustos): `2.0.0`.**
  Arayüz baştan değişti ve otomatik kayıt bilinçli bir ürün kararını tersine
  çeviriyor (D1) — ikisi de major'ı savunuyordu. `version.py` güncellendi.
  > **PR 1'in atladığı şey buydu:** `version.py`'nin kendi kuralı "gönderilen
  > HER build APP_VERSION'ı artırır — yalnızca bir CSS/JS düzeltmesi de olsa",
  > çünkü `?v=` cache-buster'ı buna bağlı. PR 1 `style.css`'in 834 satırını ve
  > `index.html`'in 535 satırını değiştirdi ama `APP_VERSION`'a dokunmadı:
  > `/static/style.css?v=1.16.0` aynı URL altında bambaşka içerik servis etti,
  > yani 1.16.0'ı bir kez yüklemiş kullanıcı ESKİ stil dosyasını önbellekten
  > alıyordu. 2.0.0 bunu da kapatıyor.
- **DM Sans bundle** (§4) — **bitti (2026-08-15).** Onay ölçümle alındı: üç
  seçenek (tam değişken 92 KB · wght-yalnız 54 KB · tek statik ağırlık 21 KB)
  boyutlarıyla sunuldu, ortadaki seçildi. `latin` + `latin-ext` şartı ölçümle
  doğrulandı (fontTools cmap: `ğ Ğ ş Ş İ` yalnız latin-ext'te). **Ağırlık
  varsayımı düzeldi:** 400 kullanılmıyor, kullanılanlar 500 ve 600; dosya
  değişken olduğu için tek `@font-face` `font-weight: 100 1000` ikisini de
  karşılıyor.
- **Tema seçici arayüzü** — dört tema (`kurumsal` / `amber` / `viola` / monokrom)
  token katmanında hazır, seçici yok. Yeri sözleşmede belli: Araçlar → Görünüm.
  **Artık adıma bağlandı:** JS tarafı Adım 7 (`settings.js (tema…)`), kalıcılık
  tarafı Adım 9 — çünkü `SettingsRequest`'te tema alanı yok ve Adım 7 "mantık
  değişmez" diyor. Bkz. §0.2/D8.

**Devam etmek için (yeni oturum).** Adım 5, 6, **7a**, **7b** ve **8** bitti
(§0.4–§0.8) ve **commit'lendi**: 5-6-7a `55b3356` ile, 7b ve 8 `f9227de` +
`f35b5c6` ile `main`'de (`pytest` **1106 yeşil**,
`APP_VERSION` 2.1.0). PR 2 tamam, PR 1'in giydirme borcu (A1–A6) kapandı,
§4.2'nin manşeti teslim edildi.

**Sıradaki tur bu dosyada DEĞİL.** 7 Ağustos kullanıcı denemesi üç açık buldu
ve üçü Adım **11 · 12 · 13** olarak kendi planına yazıldı; Adım 9 ile 10 onların
arkasına düştü (§0.1'in tablosu ve §0.3'ün başındaki not). Devam istemi ve
adım tanımları orada:

**`docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md`**

Adım 9'un tanımı §0.3'te geçerliliğini koruyor — yalnız sırası değişti; oraya
gelindiğinde tema kalıcılığının yeri `prefs.json` (K6), Kütüphane "Yüklemeler"
için `assets_store.KINDS` bir sözleşme (`_check_asset_kind` ona bakıyor).

---

## 0.2 Referans ekran ↔ uygulama denetimi (7 Ağustos)

Beş referans ekran (`studio-session` · `media-browser` · `studio-preview` ·
`library-assets` · `settings-panels`) uygulamanın işaretlemesine ve JS'ine karşı
tek tek okundu. **Göz kararı değil:** her satır ya işaretlemede ya kodda
doğrulandı, dosya/satır referansı verildi.

**Neden gerekti:** §0.1'in elle yazılmış "yapılmayan işler" listesi iki madde
sayıyordu; denetim **18** açık madde buldu. Elle tutulan liste hafızadan
besleniyor ve sessizce eksik kalıyor — bu yüzden kaldırıldı (yukarı bkz.).

### Zaten bir adıma bağlı olanlar (9)

| # | Eksik | Nerede kapanıyor |
|---|---|---|
| A1 | Kütüphane görünüm değil (`core.js:122` → `$("library-btn").click()`) | Adım 7 |
| A2 | Araçlar görünüm değil (`core.js:123` → `$("palette-btn").click()`) | Adım 7 |
| A3 | Medya'da arama yok | Adım 7 (`folders.js`: "arama") |
| A4 | Izgara boyutu S/M/L yok (`#size-seg`) | Adım 7 (`folders.js`: "ızgara boyutu") |
| A5 | Azure + Tema modalları hâlâ `.modal`; §2.4/3 slide-over istiyor | Adım 7 ("modal→slide-over … yolları") |
| A6 | Tema seçici JS'i | Adım 7 (`settings.js`: "tema") |
| A7 | Otomatik kayıt anahtarı | Adım 6 (D1) |
| A8 | Oturumu sil / tümünü sil | Adım 6 (D1 güvencesi b) |
| A9 | Birleşik döküm (konuşma + sonuç aynı akışta) | Adım 5 + 7 |

### Hiçbir adımın sahiplenmediği açıklar (10) — yeni Adım 8/9/10

> **Sayım:** denetim 18 açık madde buldu. Bunların 8'i zaten bir adıma bağlıydı
> (A1–A6, A9 ve D8'in JS yarısı), 9'u sahipsizdi, 1'i (D7) ertelendi. Aşağıdaki
> tablo 10 satır: dokuz sahipsiz madde + **D8'in arka uç yarısı** — tema seçici
> ikiye bölündüğü için hem A6 hem D8 olarak geçiyor. A tablosundaki A9 (birleşik
> döküm) denetimden değil, §3/§5'ten geliyor; tamlık için oraya yazıldı.

| # | Eksik | Sözleşme | Kanıt |
|---|---|---|---|
| **D14** | **"Görsel modunda üret" yok; `chat.js:109` hâlâ "Forma aktar" diyor** | §4.2: bu gidiş-geliş "ortadan kalkıyor" | `static/chat.js:109` |
| **D13** | **"Yönetmen'e sor" düğmesi yok** | §4.2: Görsel modunda metin yazınca sağda çıkar | `static/` genelinde 0 eşleşme |
| D8 | Tema **kalıcılığı** yok: dört tema `[data-theme=…]` olarak var ama hiçbir JS `data-theme` yazmıyor **ve** `SettingsRequest`'te tema alanı yok | §2.1 "settings.py'nin yazdığı yerel ayara yazılır" | `flow-tokens.css:65`, `models.py:140` |
| D9 | Kütüphane'de **"Yüklemeler"** türü ve **"Tümü"** filtresi yok (uygulamada 3 tür, referansta 5 gezinme öğesi) | §4.1 "logolar, mottolar, bannerlar, **yüklemeler**" | `assets_store.py:19` → `KINDS = ("logos","banners","mottos")` |
| D10 | Medya'da **sıralama** yok (`#sort-btn` · "En son üretilen") | §4.1 "arama burada + **sıralama**" | Adım 7 yalnızca arama/ızgara/gezinme sayıyor |
| D12 | Klasör kartlarında **kapak görseli** yok, genel klasör glifi var | §4.1 "klasör kartları (**kapak görseli** + ad + sayı)" | `folders.js:272` (SVG glif) |
| D15 | Üst şeritte **kebab** (oturum menüsü) yok | §2.2 · §6 · **bu planın 297. satırı** (Adım 2'nin kendi kapsamı) | Adım 2 bitti, gelmedi |
| D16 | Boş durumda **glif** yok, yalnız metin var | §2.4/5 "küçük tek glif + tek satır" | Adım 3 bitti (`empty-state` listesindeydi), gelmedi |
| D17 | Klasörde **"Yeniden adlandır"** yok | yalnız referans işaretlemesinde (`media-browser.html` crumb), düzyazıda yok | `static/` genelinde 0 eşleşme |
| D18 | Medya'da **`rail-count`** sayacı yok | yalnız referans işaretlemesinde, düzyazıda yok | — |

> **D14 devrin manşeti.** Sekmeler §4.2 uğruna kaldırıldı ve o bölümün
> gerekçesi "Forma aktar → diğer sekme gidiş gelişi ortadan kalkıyor" cümlesi.
> O gidiş-geliş **hâlâ duruyor**: sekme kabuğu gitti, hand-off kalmadı sanıldı,
> ama düğme `chat.js`'te aynı adla yaşıyor. Yani yeniden tasarımın satış
> argümanı henüz teslim edilmedi ve hiçbir adım onu sahiplenmiyor.

### Ertelenen (7 Ağustos kararı)

| # | Eksik | Karar |
|---|---|---|
| D7 | **Yedekler paneli** (otomatik yedek · eski biçim göçü · şimdi yedek al · klasörü aç) | **Şimdilik atlanıyor.** Kullanıcı kararı: "yedek alma özelliği şu anda yok, şimdilik es geçelim." Devrin bitiş ölçütünden de düşürüldü (§7), sessizce kaybolmasın diye burada duruyor. |

> Kayıt için: §4.1'in **"Yedekler artık sol rayda değil"** cümlesi yanlıştı.
> `25713f8`'in `static/index.html`'i ve `settings.js`'i denetlendi — yedek
> arayüzü **hiç var olmamıştı**, dolayısıyla raydan kaldırılmadı. Bu bir
> gerileme değil, hiç yazılmamış kapsam. `backup.py` yalnızca açılışta
> otomatik çalışıyor (`app.py:92`), kullanıcıya dönük ne arayüz ne rota var.

### Denetimde SAĞLAM çıkanlar

Liste güvenilir olsun diye: bindirme paneli tam (`logo-size`, `logo-offset-x/y`
+ `-val` + `logo-offset-reset`, `logo-shadow`, `logo-blur`, `banner-scale` —
referans bilerek uygulamanın **kendi id'lerini** kullanıyor) · büyütecin dokuz
id'si ve alt şerit dizilimi duruyor · oturum drawer'ı ve üretim ayarları gerçek
slide-over · dört ray öğesi + Daralt (228↔72 ölçüldü) · mod anahtarı ve `⌘J`
çalışıyor · çoklu seçim şeridi ve sürükle-bırak içe aktarma yerinde
(`folders.js`'te 8 `dragover`) · §1.2'nin negatif testleri korunuyor.

---

## 0.3 Adım 8 · 9 · 10 — denetimden doğan turlar

> **Devamı yeni planda.** Adım 8 bitti (§0.8). 9 ve 10 duruyor ama sıraları **geriye**
> düştü: kullanıcı denemesinden doğan Adım 11 · 12 · 13 önlerine geçti —
> `docs/superpowers/plans/2026-08-07-flow-studio-tek-dokum.md`. Aşağıdaki 9 ve 10
> tanımları geçerli; yalnız zamanlaması değişti. Bir madde iki planda birden yaşıyor:
> **D10 (sıralama)** — Adım 12'nin seçicisi sıralamayı bilerek ship etmiyor, çünkü D10
> Medya görünümüyle AYNI turda gelmeli (bkz. yeni planın B9 kararı).

Sıra §0.2'nin şiddet sırasına göre: önce sözleşmenin manşeti, sonra arka uç
gerektirenler, en sonda kozmetik.

### Adım 8 — §4.2'yi gerçekten teslim et (D13 + D14) — **bitti (7 Ağustos, §0.8)**

Kozmetik **değil**, davranış: kendi testleriyle gelir.

- `chat.js`'in prompt bloğundaki **"Forma aktar" → "Görsel modunda üret"**:
  modu Görsel'e alır, prompt'u composer'a basar, sekme yolculuğu yok.
- Görsel modunda prompt kutusuna yazınca sağda **"Yönetmen'e sor"** metin
  düğmesi (kutu boşken görünmez — §4.2 "ikinci dolu düğme oluşmasın").
- Zorunlu testler: düğme etiketi artık "Forma aktar" **değil**; boş kutuda
  "Yönetmen'e sor" **yok**, doluyken **var**; mod geçişi `tab-image`/`tab-chat`
  mandalını bozmuyor (§1.1).

### Adım 9 — arka uç gerektiren iki açık (D8 kalıcılığı + D9)

- **Tema kalıcılığı:** `SettingsRequest`'e tema alanı + `GET /api/settings`'in
  onu döndürmesi. §2.1: API anahtarıyla aynı dosya, aynı `0600` izni.
  Doğrulama listesi `kurumsal` / `amber` / `viola` / monokrom ile sınırlı
  (allowlist — serbest metin değil).
- **Kütüphane "Yüklemeler":** `assets_store.KINDS`'a dördüncü tür + "Tümü"
  filtresi. `KINDS` bir sözleşme: `_check_asset_kind` ona bakıyor, yani
  genişletme testle gelir.

### Adım 10 — kozmetik süpürme (D10 · D12 · D15 · D16 · D17 · D18)

Tek tur, tek commit. Hiçbiri arka uca dokunmuyor.

| # | İş | Not |
|---|---|---|
| D15 | Üst şeride kebab | Menü içeriği Adım 6'da geldiği için ondan SONRA — işlevsiz işaretleme konmuyor |
| D10 | Medya sıralama düğmesi | `folders.js`; Adım 7 dosyayı zaten açıyor, orada yapmak daha ucuz |
| D12 | Klasör kartına kapak görseli | `folders.js:272`'deki glif yerine ilk görselin küçük resmi |
| D18 | Medya'da `rail-count` sayacı | sayı `folders.js`'te zaten hesaplanıyor |
| D17 | Klasör "Yeniden adlandır" | düzyazıda yok; **onay gerekiyor** — sözleşmeye eklenecek mi, düşecek mi |
| D16 | Boş durum glifi | saf CSS/işaretleme, bağımlılığı yok |

> **Tuzak:** D15 ve D10/D12/D18 aynı turda ama farklı bağımlılıkta. Kebab
> Adım 6'yı bekliyor, Medya maddeleri Adım 7'yi. Adım 10'u ikisinden önce
> açmak işlevsiz işaretleme üretir — §0.1'in "çalışmayan bir arama kutusu
> konmadı" kuralı burada da geçerli.

---

## 0.4 Adım 5 kaydı — veri modeli (7 Ağustos)

TDD ile: 32 test önce yazıldı, hepsi kırmızı görüldü, sonra kod. `pytest`
**1000 → 1032**. Arayüz ve işaretleme kıpırdamadı; id sözleşmesi de öyle.

### Teslim edilen üç alan (tasarım §5)

| # | Nerede | Ne |
|---|---|---|
| 1 | `storage.save` + `GenerateRequest.session_id` + `/api/edit` form alanı | Görsel kaydına **koşullu `session_id`** — `imported` deseninin birebir aynısı |
| 2 | `models.ChatMessage` + `ResultParams` | Dökümde üçüncü rol: `{"role": "result", "image_ids": [...], "params": {kind, size, quality}}` |
| 3 | `chat_store._SUMMARY_FIELDS` + `cover_from` | Oturum özetine **`cover_image_id`** |

Filtreler (plan R4/R5): `chat_client.build_payload` **rol** allowlist'i
(`WIRE_CHAT_ROLES`) ile süzüyor, `app.chat` aynı süzgeci isteğin girişinde
tekrarlıyor, `_check_chat_total` sonuç kayıtlarını **saymıyor**.

### Bu turda verilen ve yazıya geçen beş karar

| # | Karar | Gerekçe |
|---|---|---|
| K1 | Rol süzgeci **alan** allowlist'ine ek olarak geldi, onun yerine değil | `WIRE_MESSAGE_FIELDS` bir sonuç kaydından geride `{"role": "result"}` bırakır: Azure o rolü bilmez, 400 döner ve **bir kez üretim yapmış oturum bir daha hiç konuşamaz.** Mutasyon testiyle doğrulandı |
| K2 | `session_id`'de **biçim kapısı var, varlık kapısı yok** | `_check_folder` gibi varlık sorulsaydı, oturum kaydı yazılmadan önce (otomatik kayıt kapalıyken hiç yazılmıyor) ya da oturum başka sekmede silindikten sonra yapılan üretim 422 ile düşerdi — pahalı bir Azure turu bir ETİKET yüzünden kaybedilirdi. Ters yön zaten hoşgörülü (sarkan `image_id` dökümü çökertmiyor); simetrik duruş tutarlı olan. Bozuk biçim ise **sessizce düşürülmüyor**, 422 dönüyor |
| K3 | `cover_image_id` **parametre değil, dökümden türetiliyor** (ilk sonucun ilk görseli) | İstemciden alınsaydı dökümde hiç bulunmayan bir görsel kapak olabilirdi: panelde görünen küçük resim ile açılan oturum ayrışırdı. SON değil İLK: liste küçük resmi her üretimde değişmesin. Döküm küçülürse alan **düşüyor** — kapak dökümün dışını gösteremez |
| K4 | Sonuç kayıtlarına **kendi sayı payı**: `MAX_CHAT_ITEMS = MAX_CHAT_MESSAGES + MAX_CHAT_RESULTS` (24+24) | Aynı 24'ü paylaşsalardı üretim yapan oturum ~8 turda dolar ve kullanıcı pydantic'in **İngilizce** `too_long` hatasını görürdü. Konuşma turu sayısı artık Türkçe mesajlı bir doğrulayıcıda |
| K5 | `ResultParams.size/quality` **allowlist'e karşı doğrulanmıyor** (yalnız uzunluk) | Allowlist bir gün daralırsa (Azure bir boyutu kaldırır) o boyutla üretilmiş eski oturumlar bir daha **kaydedilemez** olurdu: `PUT /api/chats/{id}` 422 döner, oturum sessizce donar. `MAX_CHAT_REPLY_CHARS`'ın var olma sebebi bu sınıf hataydı. `kind` bizim kümemiz, altımızdan değişmez |

Ek olarak `content` opsiyonel oldu (sonuç kaydının metni yok) ve alan-rol
kuralları tek doğrulayıcıda toplandı; `chat_store.valid_id` üç guard'ın
tekrarını kaldırdı ve `/api/generate`'in de kullandığı kapı oldu.

### Ölçülen kanıtlar

- `pytest` **1032 yeşil** (taban 1000, +32). Silinen test yok, id defteri boş kaldı.
- **Mutasyon testi** — beş çekirdek iddianın her biri, kodu bozunca kırmızıya
  döndü: rol süzgeci (istemci ve rota ayrı ayrı), kapak türetimi, bütçe süzgeci,
  koşullu `session_id`. Boş geçen tek iddia yok.
- **Canlı tur** (8799, süreç yeniden başlatıldı): sonuç kaydı olan bir oturum
  kaydedildi → `POST` 200, `image_ids`/`params` diske birebir indi, özet
  `cover_image_id`'yi taşıdı, `DELETE` 200 ile temizlendi.
- **Göç gerçekten yok:** geliştiricinin gerçek `output/chats.json`'ındaki 5
  oturumun hiçbirine `cover_image_id` yazılmadı (sonuçları yok), `history.json`
  kayıtlarına `session_id` girmedi.
- Tarayıcı konsolu **0 hata/0 mesaj**. İşaretleme değişmediği için ekran
  görüntüsü turu (§1.4/4) gerekmedi.

### Adım 5'in bıraktığı iki arayüz borcu (Adım 7'ye) — Adım 6 ikiye daha ekledi

Sunucu payı bitti; ekran payı Adım 7'nin. İkisi de §7'de kutulu — yazılı
olmayan bir şey "yapıldı" sayılamıyor (§0.2'nin dersi):

1. **"Görsel silindi" yer tutucusu.** Sarkan `image_id` sunucuda kasten
   budanmıyor (`test_a_deleted_image_leaves_the_transcript_readable`); dökümün
   onu yer tutucuyla çizmesi gerekiyor (tasarım §5, kabul ölçütü).
2. **`chat.js`'in mesaj sayısı kapısı.** `chatThread.length >= MAX_CHAT_MESSAGES`
   (chat.js:817) artık yanlış sayar: sonuç kayıtlarının kendi payı var (K4).
   Sunucu 48 öğeye izin verirken istemci 24'te durdurursa üretim yapan oturum
   sebepsiz kilitlenir. Aynı yerde `MAX_CHAT_ITEMS` de aynalanmalı.

---

## 0.5 Adım 6 kaydı — otomatik kayıt (7 Ağustos)

TDD ile: 30 test önce, hepsi kırmızı, sonra kod. `pytest` **1032 → 1062**.
Arayüz ve işaretleme yine kıpırdamadı — bu tur da tamamen arka uç.

Karar D1'in üç güvencesi, üçü de mekanik:

| Güvence | Nasıl karşılandı |
|---|---|
| (a) her şey yerelde; `output_dir` ve izinler değişmez | Yeni dosya `output/prefs.json`, diğer beş manifestin yanında; yazım `jsonstore` (atomik + kilit). Kimlik dosyasına dokunulmadı |
| (b) tek tıkla **sil** ve **tümünü sil** | `chat_store.delete_all` + `DELETE /api/chats` (boş depoda 404 değil, `{"deleted": 0}`) |
| (c) "oturumları otomatik kaydet" anahtarı; kapatınca bugünkü davranış | `prefs.py` + `GET/POST /api/prefs`; kapalıyken otomatik yazım **409** ile durduruluyor, adlandırılmış yazım çalışmaya devam ediyor |

### Bu turda verilen ve yazıya geçen dört karar

| # | Karar | Gerekçe |
|---|---|---|
| K6 | Anahtar `credentials.env`'e DEĞİL yeni bir `prefs.py` deposuna yazılıyor | `credentials.env` bir KİMLİK dosyası (0600, `~/.config`) ve `POST /api/settings` `api_key` + `base_url` istiyor: anahtarı çevirmek Azure kimliğini yeniden yazmak zorunda kalırdı, Azure hiç yapılandırılmamışken de anahtar çevrilemez olurdu. Bir tema adının 0600 olması da anlamsız. localStorage ise pywebview'ın private mode'unda her kapanışta siliniyor (`chat_store`'un ölçülmüş sebebi). Tema (Adım 9) aynı dosyaya girecek |
| K7 | Uç ayrı: `GET/POST /api/prefs`. `/api/settings` bu değeri **yansıtmıyor** | Aynı değer iki uçtan okunsa ayrışabilirdi; ayrıca tercih formu ile kimlik formu farklı iki form |
| K8 | **"Başlıksız yazım = otomatik yazım"** ve kapalı anahtarda 409 | Anahtarın teeth'i olması için otomatik yazımın ayırt edilmesi gerekiyordu. İsteğe "bu otomatik" bayrağı KONMADI: bayat/hatalı bir istemci onu yanlış gönderdiğinde anahtar sessizce delinirdi. Otomatik kaydın verecek bir ADI yok — uydurulamaz işaret bu. Sonuç: adlandırılmış POST/PUT (elle kaydet, yeniden adlandır) her koşulda çalışıyor, yani "kapatınca v1.15 davranışı" gerçekten sağlanıyor. Silme de anahtardan bağımsız: anahtar YAZIMI kısıtlıyor, kullanıcının kendi verisini silmesini değil |
| K9 | Başlıksız POST artık 422 değil: başlık **ilk kullanıcı turundan türetiliyor** | Otomatik kaydın ad verecek kullanıcı eylemi yok. Kural ("adsız sohbet olmaz") aynı kaldı, sağlayan taraf değişti. `display` varsa o kazanıyor (çip turunda ekranda görünen metin odur); tek satır, boşluk sıkıştırılmış, `MAX_CHAT_TITLE_CHARS`'ta "…" ile kesiliyor; kullanıcı mesajı hiç yoksa "Adsız oturum". **BOŞ** gelen başlık hâlâ 422 — "alan gelmedi" ile "boş geldi" ayrımı `chat_deployment` geleneği |

`POST /api/chat` hâlâ hiçbir şey yazmıyor ve bu bilinçli: oturumu yazan taraf
istemci. Sebep birleşik dökümün kendisi — Görsel modunda üretilen sonuç kayıtları
tamamlama rotasına hiç uğramıyor, dolayısıyla kalıcılık oraya konsa sohbetsiz bir
oturum hiç kaydedilemezdi. `chat_store.py`'nin başındaki not bu üç aşamayı
(v1.13 → v1.15 → D1) silmeden anlatacak şekilde yeniden yazıldı.

### Ölçülen kanıtlar

- `pytest` **1062 yeşil** (Adım 5 sonu 1032, +30). **Silinen test yok.** Tek
  yeniden adlandırma: `test_post_without_a_title_is_422` →
  `test_post_without_a_title_is_an_automatic_save` — iddia D1 yüzünden tersine
  döndü, gerekçesi testin kendi docstring'inde yazılı.
- **Mutasyon testi** — yedi çekirdek iddia, kodu bozunca hepsi kırmızıya döndü:
  POST guard'ı, PUT guard'ı, guard'ın adlandırılmış yazımı serbest bırakması,
  varsayılanın açık olması, başlıkta `display` önceliği, boş depoda dosya
  yaratmama, tercih birleştirme (diğer tercihi düşürmeme).
- **Canlı tur** (8799, süreç yeniden başlatıldı): başlıksız POST → 200 ve başlık
  "mevlid kandili için kare tebrik" (ikinci satır düştü) · gövde-yalnız PUT → 200,
  kapak türedi · anahtar kapatıldı → otomatik POST **409**, tur sonu PUT **409**,
  yeniden adlandırma **200**, adlandırılmış kayıt **200** · iki oturum silindi,
  anahtar geri açıldı, geliştiricinin 5 oturumu olduğu gibi kaldı.
- **Doğrulama artığı temizlendi:** canlı tur `output/prefs.json` yaratmıştı
  (içeriği varsayılanla aynı), silindi.
- Tarayıcı konsolu: uygulama açılışında **0 mesaj**. (Kontrol turunda görülen iki
  409, benim `fetch` çağrılarımın kendi çıktısıydı — uygulamanın JS'i değil.)

---

## 0.6 Adım 7a kaydı — PR 2'nin ekran payı (7 Ağustos)

TDD ile: 15 test önce, hepsi kırmızı, sonra kod. Sonradan üç test daha eklendi
(biri ikiye ayrıldı, ikisi aşağıdaki kod incelemesinden doğdu) → **18**.
`pytest` **1062 → 1080**. **Bu turda PR 2 kapandı**: arka ucun teslim ettiği üç
alan artık ekranda.

> **Adım 7 ikiye ayrıldı ve bu bilinçli.** `Adım 7` satırı iki ayrı işi
> taşıyordu: (a) PR 2'nin ekran payı — Adım 5–6'nın bıraktığı dört borç,
> (b) §0.2 denetiminden gelen A1–A6, yani **PR 1'in** giydirme borcu (Kütüphane/
> Araçlar görünümleri, Medya araması, ızgara boyutu, modal→slide-over, tema
> seçici). İkisi aynı satırda olsa da aynı iş değil: (a) birleşik oturumun
> parçası ve arka ucu hazır bekliyor, (b) kabuğun tamamlanması. §0.1'in devam
> istemi de bu turu "sadece PR 2 / Adım 7" diye yazmıştı. Ayrım **satır olarak**
> yazıldı (7a/7b) ki (b) yine §0.2'nin yakaladığı biçimde sessizce düşmesin.

### Teslim edilen dört borç

| # | Borç | Nasıl karşılandı |
|---|---|---|
| 1 | Döküm `result` rolünü çiziyor | `appendResult` + `resultThumb`; künye `Üretildi · 1024² · Orta · x2` (referans ekranın `.result .who` satırı). `openChat` artık ÜÇ dallı — iki dallı hâlinde sonuç kaydı `appendBot(undefined)`'a düşüp dökümü çökertirdi |
| 2 | "Görsel silindi" yer tutucusu | `resultThumb`'ın `error` dinleyicisi; `.chat-media.gone` çizgili zeminle (flow.css'in `.media .ph` grameri) |
| 3 | Mesaj sayısı kapısı yalnız konuşmayı sayıyor | `conversationIsFull()` + `transcriptIsFull(slots)`; `chatThread.length >= MAX_CHAT_MESSAGES` kalktı |
| 4 | Oturumlar gerçekten otomatik kaydediliyor | `persistThread` **başlıksız** `POST`/gövde-yalnız `PUT`; 409 Türkçe; anahtar `/api/prefs`'ten; "tüm oturumları sil" panelin dibinde |

Ek olarak, borç listesinde OLMAYAN üç şey bu turda kapandı çünkü üçü de bu
turun kendi işinden doğdu:

- **Üretim açık oturuma katılıyor** (`core.js`'in `run()`'ı): `session_id` iki
  dalda da gidiyor, prompt bir kullanıcı turu olarak döküme basılıyor, sonuç
  kaydı ekleniyor. Bu olmadan Adım 5'in üç alanı da **ulaşılamaz** kalırdı.
- **`#session-title` / `#session-stamp` bağlandı.** PR 1'de kondu, hiç
  bağlanmamıştı — §0.2 bunu da kaçırmıştı. Süs değil gereklilik: kabuk iki
  modda da aynı, üretim açık oturumun dökümüne düşüyor, yani "hangi
  oturumdayım" sorusunun cevabı üst şeritte olmak zorunda.
- **Ayarlar panelinin başlığı** "Azure Ayarları" → **"Ayarlar"**, Azure kendi alt
  başlığına indi. Panelin içine kimlik dışı bir tercih girdiği anda eski başlık
  yalan oldu; tasarım §4.1 de dişliyi tek bir "Ayarlar" paneli sayıyor.

### Bu turda verilen ve yazıya geçen beş karar

| # | Karar | Gerekçe |
|---|---|---|
| K10 | Üretim açık bir oturuma **katılıyor**, kendi başına oturum **açmıyor** | `session_id`'de varlık kapısı yok (§0.4/K2), yani henüz yazılmamış bir oturumun id'si gönderilemez — sarkan bir etiket diske yazılırdı. Boş oturum da açılamıyor (`POST /api/chats` gövde istiyor, 422). Üretimden önce bir kullanıcı turu yazıp oturum açmak ise BAŞARISIZ her üretimden sonra dökümde cevapsız bir tur bırakırdı; yeniden deneme onu ikinci kez eklerdi. Oturumu Görsel modundan BAŞLATMAK tek composer'ın kararı (tasarım §4.2 → Adım 8): orada prompt yapısı gereği bir döküm turu |
| K11 | Sonuç görselinin URL'i **id'den kuruluyor** (`/output/{id}.png`), ikinci bir istek yok | Dosya adı sözleşmesi `storage.py`'de yazılı (`save`'in `filename` satırı, `delete_many`'nin docstring'i). `/api/history` KULLANILAMAZDI: o uç klasöre göre süzülüyor, yani başka bir klasöre taşınmış bir sonuç görselini hiç döndürmezdi ve kart sebepsiz "silindi" derdi |
| K12 | Yer tutucunun ölçüsü **`error` olayı**, tutulan bir liste değil | Dosya gerçekten yoksa `/output/{id}.png` 404 döner — gerçek koşul ölçülüyor. Bayat bir dizinden bakmak, silinmiş ama dizinde duran bir görseli "var" gösterirdi. `loading="lazy"` ile birlikte yer tutucu kart görüş alanına GİRDİĞİNDE çiziliyor; kullanıcının baktığı an da tam olarak o |
| K13 | **`MAX_CHAT_RESULTS` istemcide aynalanMIYOR** | Sunucu sonuç ADEDİNİ ayrıca kapamıyor: kuralları "konuşma ≤ 24" ve "toplam ≤ 48". İstemci ayrıca 24 sonuçta durursa **sunucudan katı** olur ve sohbetsiz bir oturum 24. üretimde sebepsiz kilitlenir — kapatılan borcun ekseni değişmiş aynısı. Aynalanan tek yeni sabit `MAX_CHAT_ITEMS`; testi bunu hem doğruluyor hem `MAX_CHAT_RESULTS`'ın tanımlanMAdığını mandallıyor |
| K14 | Sonuç kartında "Düzenle" ve "+ Ek" **yok**, "İndir" var | İkisi de tam bir geçmiş KAYDI istiyor (prompt, boyut, klasör); döküm yalnız id taşıyor. Çalışmayan bir düğme çizmek yerine composer turuna (Adım 8) bırakıldı. "İndir" yalnız URL istiyor, o yüzden bugün gerçek. Karenin kendisi büyüteci açıyor (tasarım §6) |

`viewer.js` **yeniden yazılmadı** (§1.3): tek bir açılış dikişi dışa verildi
(`window.openViewer`), imleç-sabitli zoom / rubberband / pinch / ok adımı aynen
duruyor ve `openerRect` sayesinde büyüteç tıklanan karenin bulunduğu yerden
büyüyor. Testi korunan davranışların adlarını da ayrıca sayıyor.

`test_the_chat_title_is_derived_locally_not_asked_from_the_model` **silinmedi,
taşındı**: iddiası ("başlık için ikinci bir model çağrısı yok") aynı kaldı ama
ölçüldüğü yer `chat.js`'in `deriveTitle`'ından `app._auto_title`'a geçti.

### Ölçülen kanıtlar

- `pytest` **1080 yeşil** (Adım 6 sonu 1062, +18). **Silinen test yok.**
- **Kendi kodumun incelemesi iki gerçek açık buldu ve ikisi de kapandı:**
  (a) `run()`'ın `try` bloğu sonuç kaydını da kapsıyor, yani sonuç yazıldıktan
  SONRA bir hata (ör. `loadHistory`'nin ağ hatası) `catch`'e düşse kullanıcı
  turu silinir ama sonuç kaydı kalırdı — dökümde **sahipsiz bir kart**. `pending
  .done` işareti kapanmış turu geri alınamaz yaptı. (b) Azure hiç görsel
  döndürmezse `image_ids: []` yazılırdı ve sunucu `min_length=1` ile **422**
  verirdi — kullanıcının açıklayamayacağı bir hata. Artık boş sonuç yazılmıyor,
  kullanıcı turu da cevapsız bırakılmıyor. İkisinin de testi ve mutasyonu var.
- **Mutasyon testi — 18 çekirdek iddia, hepsi kırmızıya döndü.** İlk turda
  DÖRDÜ boş geçti ve dördü de aynı sebepten: iddia kodu değil KELİMEYİ arıyordu
  (gövdedeki not "409"/"session_id"/"session-title" yazdığı için, ya da kardeş
  bir çağrı yeri aynı dizeyi taşıdığı için). Düzeltilen iddialar artık
  `e.status === 409`, `fd.append("session_id", …)` + JSON dalını ayrı ayrı,
  `$("session-title").textContent` gibi **kodun kendisini** arıyor.
- **Canlı tur** (8799, süreç yeniden başlatıldı, geliştiricinin gerçek verisi):
  başlıksız `POST` → 200 ve türetilen başlık "Mevlid kandili için ornamental kare
  tebrik görseli" · iki sonuç kartı çizildi (`Üretildi · 1024² · Orta · x2` ve
  `Düzenlendi · 1536×1024 · Yüksek · x1`) · sarkan `ffffffffdead` id'si **"Görsel
  silindi"** yer tutucusuna döndü · anahtar kapatıldı → otomatik `POST` **409**
  ve Türkçe satır, `currentChatId` null kaldı, adlandırılmış `POST` **200** ·
  anahtar geri açıldı · `run()` stub'lı `/api/generate` ile çalıştırıldı:
  gövdede `session_id`, dökümde `user, assistant, user, result`, diske aynısı
  indi ve `cover_image_id` türedi · üretim 500 ile başarısız edildi: döküm
  BÜYÜMEDİ, prompt kutuda kaldı, diskteki gövde değişmedi · "tüm oturumları sil"
  onay penceresini açtı ("8 oturum kalıcı olarak silinecek… görseller SİLİNMEZ"),
  **Vazgeç** 8'i 8 bıraktı, **onay** 0'a indirdi, 25 görsel yerinde kaldı, ikinci
  `DELETE` boş depoda 404 değil `{"deleted": 0}` döndü.
- **Geliştiricinin verisi bozulmadı:** `chats.json` tur öncesinde yedeklendi,
  sonunda **bayt bayt aynı** geri kondu (sha `dd7af60ecd75d684`); 5 oturum,
  25 görsel. Kayıt alanları değişmedi (`cover_image_id` yazılmadı, `history.json`'a
  `session_id` girmedi) — göç gerçekten yok. Doğrulamanın yarattığı
  `output/prefs.json` silindi.
- **Tarayıcı konsolu:** temiz sekmede, geliştiricinin gerçek oturumu açıkken
  **0 mesaj**. (Doğrulama sekmesinde görülen 404'ler benim kasten uydurduğum
  silinmiş görsel id'leriydi — yer tutucu yolunun kanıtı; 409 da anahtarı
  kapatma denemem.)
- **Ekran görüntüleri 1024×700 / 1280 / 1440 / 1920:** dördünde de yatay taşma
  **yok** (`scrollWidth == clientWidth`). Sağ/sol slide-over'lar ölçümde
  "taşıyor" görünüyor ama kapalı hâlde `translateX(100%)` ile ekran dışında
  duruyorlar — tasarım gereği.

> **⚠️ Doğrulama tuzağı — aynı sürüm altında bayat JS.** `index.html` statikleri
> `?v={APP_VERSION}` ile çağırıyor. Sürüm 2.0.0'da SABİT kalırken içerik
> değiştiği için tarayıcı **eski** `chat.js`/`viewer.js`'i önbellekten verdi ve
> yeni fonksiyonların hiçbiri tanımlı görünmedi (`window.location.reload()` de
> kurtarmıyor). Çözüm: doğrulamayı **başka bir origin'de** yapmak
> (`127.0.0.1` ↔ `localhost` ayrı önbellek anahtarı). 2.0.0 henüz
> gönderilmediği için bu kullanıcıyı etkilemiyor — `version.py`'nin "gönderilen
> HER build sürümü artırır" kuralı zaten kapıyı kapatıyor. Ama tur içinde
> tekrar edeceği için buraya yazıldı; `run.sh`'in bayat-arka-uç tuzağının
> ön yüz kardeşi.

---

## 0.7 Adım 7b kaydı — PR 1'in giydirme borcu (7 Ağustos)

TDD ile: **15 test önce**, hepsi kırmızı görüldü, sonra kod. `pytest`
**1080 → 1095**. Silinen test yok. §0.2'nin A1–A6'sı kapandı; id sözleşmesinden
**iki id defterli olarak düştü** (aşağıda).

### Teslim edilen altı madde

| # | Borç | Nasıl karşılandı |
|---|---|---|
| A1 | Kütüphane kendi görünümü | `#view-library` bölümü; içerik id'leri (`asset-tabs`, `asset-grid`…) modaldan taşındı, **modal kabuğu** (`assets-modal`, `assets-close`) id defterine yazılarak kaldırıldı. `assets.js`'te `openLibraryView` görünüme girişte paneli tazeliyor |
| A2 | Araçlar kendi görünümü | `#view-tools` + iki kart (`#tool-palette`, `#tool-look`). Azure kimliği bilerek DIŞARIDA — Araçlar = tasarım kararları, dişli = makine ayarı (§4.1); testi ayrı (`test_the_gear_and_the_tools_view_are_different_doors`) |
| A3 | Medya'da arama | `#media-search`; sorgu üç alanda (prompt/klasör adı/boyut, içe aktarılanlarda dosya adı). Sorgu yazıldığı an klasör sınırı kalkıyor: `loadAllImages` kök + her klasörü çekip birleştiriyor, `#search-label` kapsamı söylüyor, kartlara `card-where` klasör künyesi basılıyor |
| A4 | Izgara boyutu S/M/L | `#size-seg` yalnızca `data-size` yazıyor; kutucuk ölçüsü CSS'te `.gallery[data-size=…]`nin `--tile`'ından. JS'ten `grid-template-columns` yazmak `auto-fill` duyarlılığını ezerdi |
| A5 | Azure + Tema panelleri slide-over | `#settings-modal` ve `#palette-modal` `<aside class="sheet sheet-right">` oldu — **id'ler bilerek aynı** (152 sözleşmesi + JS bağı; ad telin üstündeki isim, yüzey iddiası değil). Palet paneline 420px (renk seçmek onun ana işi). Form sınırı kuralı `.sheet-body input`'a taşındı (§0.0/G kapısı açılmadı) |
| A6 | Tema seçici | `#look-sheet` + `#theme-picker`; `change` → `document.body.dataset.theme`. **Monokrom = öznitelik YOK** (aşağıda K15). Kalıcılık BİLEREK yok ve panel bunu yazıyla söylüyor — Adım 9'un işi |

### Bu turda verilen ve yazıya geçen dört karar

| # | Karar | Gerekçe |
|---|---|---|
| K15 | Monokrom seçimi `data-theme` YAZMIYOR, özniteliği siliyor | `flow-tokens.css`'te `[data-theme="mono"]` diye bir satır yok — varsayılan `--accent` zaten monokrom. Sahte bir "mono" değeri token katmanında karşılığı olmayan bir durum üretir ve dördüncü tema satırı yazdırırdı |
| K16 | Slide-over açmanın TEK kapısı `openSheet` (önce `closeSheets`) | Beş panel aynı perdeyi ve aynı şeridi paylaşıyor; ikisi birlikte açılırsa üst üste biner ve `Esc`in hangisini kapattığı belirsizleşir. Escape dinleyicisine `confirm-modal` guard'ı da eklendi: onay penceresi panelin ÜSTÜNDE açılıyor (palet kaydetme) ve guard'sız tek Escape iki katmanı birden kapatırdı |
| K17 | Arama filtresi İSTEMCİDE, sunucuya arama parametresi eklenmedi | 25 kayıtlık yerel arşivde sunucu tarafı arama ucu YAGNI; `loadAllImages` GET'leri paralel (importFiles'ın "sırayla" kuralı YAZAN uçlar için). Eşik tasarım §10/3'te zaten var: 500 görselde yeniden ölçülecek |
| K18 | `loadHistory` arama açıkken `refreshSearch`'e sapıyor | Silme/taşıma/içe aktarma sonrası tazeleme klasör görünümüne sessizce dönmemeli — kullanıcı arama sonuçlarına bakarken listenin altından görünüm değişirdi |

### Ölçülen kanıtlar

- `pytest` **1095 yeşil** (7a sonu 1080, +15) · `test_id_contract.py` 6 yeşil
  (defterde 2 kayıt: `assets-modal`, `assets-close` — gerekçe ve JS temizliği yazılı).
- **Mutasyon turu:** 5 çekirdek iddia mutasyonla sınandı; İKİSİ ilk turda boş
  geçti ve ikisi de §0.6'daki sebepten (iddia kodu değil KELİMEYİ arıyordu):
  (a) arama testi `folder` kelimesini `const folder =` satırında buldu —
  artık şablon dizesinin kendisinde `${folderName}` arıyor; (b) tema testi
  `dataset.theme`'i `delete` satırında buldu — artık ATAMA ve SİLME ayrı ayrı
  aranıyor. Düzeltme sonrası beşi de kırmızıya döndü.
- **Canlı tur** (8799 — §0.6 tuzağına karşı ayrı origin, geliştiricinin gerçek
  verisi, tümü SALT OKUNUR): dört ray görünümü gezildi; Kütüphane gerçek
  logoları, Araçlar iki kartı gösterdi · Görünüm panelinden KURUM mavisi seçildi
  → `data-theme="kurumsal"` + `--accent oklch(72% 0.11 245)`, Monokrom'a dönüş
  özniteliği sildi · Tema rengi kartı 420px slide-over'ı açtı, HSV/ton/hex/
  öneriler canlı · dişli Ayarlar'ı sağdan açtı (endpoint dolu, anahtar
  "Kayıtlı" yer tutucusu) · Medya'da "kurban" araması 6 sonucu **iki klasörden**
  getirdi, künyeler ("Kurban 2026" / "Klasörsüz") ve "Arama sonuçları — tüm
  klasörler" etiketi göründü; sorgu silinince klasör görünümü döndü · S/M/L
  `--tile` 110/150/210 ölçüldü, `aria-pressed` tekil · specs panelindeki
  "Kütüphane" kısayolu paneli kapatıp görünüme gitti · oturum drawer'ı açıldı
  ve Escape kapattı (regresyon yok). Geliştiricinin verisine tek bayt yazılmadı.
- **Tarayıcı konsolu:** tur boyunca **0 mesaj**.
- **Ekran görüntüleri 1024×700 / 1280 / 1440 / 1920:** dördünde de
  `scrollWidth == clientWidth` (yatay taşma 0); 1200px altında ray daraldı.
- Ölçülen tek pürüz kapatıldı: `#chat-instructions-path` (boşluksuz uzun yol)
  320px şeritte gövde dolgusuna 9px taşıyordu → `overflow-wrap: anywhere`.

---

## 0.8 Adım 8 kaydı — §4.2'nin manşeti (7 Ağustos)

TDD ile: 11 test önce yazıldı, onu kırmızı görüldü (biri sınır testi — mevcut
davranışı mandallıyor, bkz. K20). `pytest` **1095 → 1106**. Silinen test yok.

Sekmeler §4.2 uğruna kaldırılmıştı ve o bölümün gerekçesi tek bir cümleydi:
"Forma aktar → diğer sekme gidiş gelişi ortadan kalkıyor". §0.2 denetimi
gidiş-gelişin **hâlâ durduğunu** buldu (D14) ve ters yönün hiç yazılmadığını
(D13). Bu tur ikisini de kapattı; üçüncü iş K10'un ikinci yarısıydı.

### Teslim edilen üç iş

| # | İş | Nasıl |
|---|---|---|
| **D14** | prompt bloğunun eylem düğmesi **"Görsel modunda üret"** | `promptFigure`'ın etiketi + `applyToForm`'un durum satırı. Davranış aynı kaldı (mod + prompt + ayarlar); değişen, olmayan bir "form"a işaret etmemesi. "Forma aktar" dizesi **yorumlarda da** kalmadı — kabul ölçütü "chat.js'te kalmadı" diyor |
| **D13** | Görsel modunda **"Yönetmen'e sor"** | `#ask-director`; `askDirector()` ham metni yönetmenin kutusuna TAŞIYOR (K21), `syncAskDirector()` görünürlüğü kutunun doluluğundan okuyor |
| **K10/2** | Görsel modu **kendi oturumunu başlatıyor** | `run()` döküm turunu koşulsuz açıyor; oturumu `persistThread` üretimden SONRA POST'la yazıyor (K19) |

### Bu turda verilen ve yazıya geçen dört karar

| # | Karar | Gerekçe |
|---|---|---|
| K19 | Oturum üretimden **SONRA** doğuyor (`persistThread`'in POST'u), önce değil | K10'un itirazı "üretimden önce kullanıcı turu yazmak" biçimindeydi: BAŞARISIZ üretim diskte cevapsız bir tur bırakır, yeniden deneme onu ikinci kez eklerdi. Yazma başarıya bağlanınca itiraz kendiliğinden düşüyor — `dropPendingTurn` yalnız BELLEKTEN siliyor, diskte hiçbir şey yok. Ön-uçuş POST'u ayrıca yeni bir tehlike doğuruyordu: üretim sürerken kullanıcı sohbete devam edebiliyor (`#go` kilitli, "Gönder" değil), yani hata anında silinecek oturum artık kullanıcının kendi mesajlarını taşıyor olabilirdi. Kapı da yeni değil: sohbetsiz oturum POST'u yönetmen akışının her gün kullandığı yol, sunucu tarafı `test_an_image_only_session_still_gets_a_title` ile Adım 5'ten beri yeşil |
| K20 | Üretim isteğine **uydurma `session_id` konmuyor** — ilk partide ters bağ eksik kalıyor | `session_id`'de varlık kapısı yok (§0.4/K2): henüz yazılmamış bir oturumun id'si diske sarkan bir etiket olarak düşerdi. Bedel ölçülü ve tek yönlü — **ileri bağ tam** (`result.image_ids`, dökümün çizdiği bağ), eksik olan ters bağ (görsel kaydındaki `session_id`) bugün hiçbir yerde OKUNMUYOR (`grep`: yalnız `storage.save` yazıyor). Tamamlanması bir arka uç işi (mevcut kayda oturum etiketi yazan rota) → Adım 9'un alanı. Sınır testle mandallandı: uydurma id yok, üretimden önce `/api/chats` çağrısı yok |
| K21 | "Yönetmen'e sor" metni **taşıyor**, kopyalamıyor; yönetmenin kutusundaki metnin **üstüne yazmıyor** | Kopyalasa metin iki kutuda kalırdı: Görsel'e dönüp Üret'e basmak yönetmene sorulmuş ham metni ayrıca üretir, düğme de görünür kalıp ikinci bir devir davet ederdi. Üstüne yazsa yazılmış ama gönderilmemiş bir yönetmen mesajı sessizce silinirdi — o yüzden birleşim `existing\n\ntext`. Sığmazsa **kırpma yok**, ret var (`applyToForm`'un `MAX_PROMPT_CHARS` duruşunun ters yönü) |
| K22 | Düğme **çerçevesiz** metin | §4.2 "metin düğmesi" diyor ve "ekranda ikinci bir dolu düğme oluşmaz" gerekçesini de yazıyor. Çerçeveli olsa composer barında üst üste üç hatlı pill olurdu (mod anahtarı · bu · üretim çipi) ve kaçış kapısı ayarların ağırlığında görünürdü. Hiyerarşi: dolu = Üret, hatlı = kontroller, düz metin = ikincil yol. Kontrast `--muted` ile **6.97:1** ölçüldü (mevcut `--muted` kullanımlarıyla birebir aynı) |

### Ölçülen kanıtlar (§1.4)

- `pytest` **1106 yeşil** · `test_id_contract.py` 6 yeşil (`ask-director` bir
  EKLEME, defterde iş yok — defter yalnız kaybı sorar).
- **Mutasyon turu: 9 iddia sınandı, dokuzu da kırmızıya döndü** (etiket, görünürlük
  yönü `hidden = !…`, birleşim `existing ? … : text`, sınır kapısı, `showView`
  yerine elle `dataset.mode`, koşulsuz `beginResultTurn`, uydurma POST, CSS mod
  ekseni, durum satırı). Bu turda boş geçen iddia **yok** — §0.6/§0.7'nin dersi
  önden uygulandı: iddialar kod deseni arıyor, kelime değil.
- **Tarayıcı (8799, ayrı origin — bayat JS tuzağı):** yeni sekmede konsol
  **0 mesaj**. Ölçülen davranışlar: boş kutu → düğme yok; yazınca → var;
  Yönetmen moduna geçince `display:none`, Görsel'e dönünce geri · devir sonrası
  `chat-input` dolu, `#prompt` boş, odak `chat-input`, düğme kendini gizledi ·
  yönetmen kutusunda metin varken devir **eklendi** (`…kılavuzu var\n\nkar
  altında bir kule`), üzerine yazmadı · 5990 karakterlik kutuya devir
  **reddedildi**, hiçbir şey kırpılmadı · yönetmen yanıtı çizildiğinde bar
  düğmeleri `["Kopyala", "Görsel modunda üret"]`, düğme prompt'u composer'a
  bastı ve `1024x1536`/`high` ayarlarını uyguladı · açık oturum YOKKEN
  `beginResultTurn` turu açtı (balon çizildi, boş durum kalktı),
  `dropPendingTurn` geri aldı. Geliştiricinin verisine tek bayt yazılmadı.
- **1024×700 / 1280 / 1440 / 1920:** dördünde de yatay taşma 0, composer barında
  da 0 (`scrollWidth == clientWidth`).

### Bu turun iki dersi

1. **Canlı ölçüm testin göremediğini gösterdi.** Sınır aşımı reddi ilk yazımda
   `chatStatus`'a gidiyordu — ama devir olmadığı için mod Görsel'de kalıyor ve
   `#chat-status` orada `display:none`. Yani düğme tıklanıyor, hiçbir şey olmuyor
   ve sebebi de **görünmüyordu**: kod doğru, kullanıcı için sessiz. Ret
   `statusEl`'e taşındı ve iddiaya "hangi satıra yazıldığı" eklendi.
2. **Kaskad, özgüllük kadar sıra demek.** `.composer-ask` ilk yazımda composer
   mod bloğunun yanına konmuştu, yani `.btn-ghost`'tan ÖNCE — aynı özgüllükte
   sonraki kazandığı için çerçeve geri geliyordu (ölçüldü: `borderColor` hâlâ
   `--control-border`). Blok düğme varyantlarının yanına taşındı.

### Bu turda BİLEREK yapılmayanlar

- **K14 (sonuç kartında "Düzenle" / "+ Ek")** §0.6'da "composer turuna bırakıldı"
  diye anılıyor ama §0.3'ün Adım 8 tanımına hiç girmedi (o liste D13 + D14 ve üç
  zorunlu test). Bu turda ölçülen yeni bilgi: **"+ Ek" bugün yapılabilir** (yalnız
  id istiyor), **"Düzenle" ise bir tercih gerektiriyor** — prompt'u dökümden
  (sonuç kaydından önceki kullanıcı turu) yeniden kurmak mı, yoksa tek bir geçmiş
  kaydını döndüren rotayı beklemek mi. İkincisi arka uç işi, yani Adım 9'un alanı.
  **Karar kullanıcıya bırakıldı**; sessizce kaybolmasın diye burada duruyor.
- `applyToForm` **adı değişmedi**. Ad kullanıcıya dönük bir iddia değil (7b'nin
  `settings-modal` gerekçesinin aynısı) ve üç test regex'i ile 2026-08-04 planı
  ona referans veriyor. Kullanıcıya görünen her dize değişti.
- §4.2'nin Yönetmen modu için saydığı **"Yönetmen talimatları ikonu"** bu tura
  girmedi: §0.2 denetiminin 18 maddesinde yok, talimat yolu bugün Ayarlar
  panelinde (`#chat-instructions-path`). Kapsam genişletilmedi, kayda geçti.

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
- ~~Yedekler sol raydan kalkar; dişliden açılan Ayarlar paneline girer.~~
  **Bu madde yanlıştı ve düştü (7 Ağustos, §0.2/D7):** `25713f8` denetlendi,
  raydaki bir yedek arayüzü **hiç yoktu** — kaldırılacak bir şey de yoktu.
  Yedekler paneli şimdilik ertelendi; bkz. §0.2 ertelenen tablosu.

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

### Adım 5 — veri modeli — **bitti (7 Ağustos), kaydı §0.4'te**

> Aşağıdaki üç madde ve zorunlu testler **teslim edildi.** Turda verilen beş
> karar (rol süzgecinin iki katmanı, `session_id`'de varlık kapısı olmaması,
> kapağın türetilmesi, sonuç kayıtlarının kendi sayı payı, `size/quality`'nin
> allowlist'e karşı doğrulanmaması) ve ölçülen kanıtlar **§0.4'te.**

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

- [x] `result` rolü Azure istemine **gitmiyor** (`chat_client.py` yalnızca
  `user`/`assistant` gönderir) — `test_build_payload_drops_result_records` +
  `test_a_result_record_is_accepted_but_never_forwarded`. Süzgeç **rol**
  düzeyinde; alan allowlist'i tek başına yetmiyordu (§0.4/K1).
- [x] `result` rolü `models.py`'deki `MAX_CHAT_TOTAL_CHARS` bütçesine
  **sayılmıyor** — `test_result_records_do_not_count_towards_the_total_cap`.
  Ölçülmemiş ağırlık da bırakmıyor: `content` ve `display` sonuç kaydında yasak,
  şema kapalı, adet `MAX_CHAT_RESULTS` ile bağlı.
- [x] Silinmiş görselin sarkan `image_id`'si dökümü çökertmiyor — sunucu payı:
  `test_a_deleted_image_leaves_the_transcript_readable` (kayıt budanmıyor,
  `GET /api/chats/{id}` 200 kalıyor). **"Görsel silindi" yer tutucusunun kendisi
  Adım 7'nin işi** (§0.4'ün borç listesi, §7'de kutusu var).

### Adım 6 — otomatik kayıt (karar D1) — **bitti (7 Ağustos), kaydı §0.5'te**

> Üç güvence de mekanik olarak karşılandı. Anahtarın nereye yazıldığı (yeni
> `prefs.py`, kimlik dosyası değil), ucun neden ayrı olduğu ve "başlıksız yazım =
> otomatik yazım" kuralının nasıl teeth kazandığı **§0.5'te** (K6–K9).

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

### Adım 7 — JS dokunuş noktaları — **7a ve 7b bitti (7 Ağustos), kayıtları §0.6 ve §0.7'de**

> Satır İKİYE ayrıldı; gerekçe §0.6'nın başında. **7a (bitti):** PR 2'nin ekran
> payı — `result` kartı, "görsel silindi" yer tutucusu, sayı kapısı, otomatik
> kayıt + anahtar + tümünü sil, üretimin oturuma katılması. Turda verilen beş
> karar (K10–K14) ve kanıtlar **§0.6'da**. **7b (bitti):** `folders.js` /
> `palette.js` / `assets.js` / `settings.js` payı, yani §0.2'nin A1–A6'sı —
> kararlar (K15–K18) ve kanıtlar **§0.7'de**.

**Adım 5'ten devraldığı iki borç** (§0.4) — **ikisi de 7a'da kapandı:** silinmiş
görselin "görsel silindi" yer tutucusu ve `chat.js:817`'deki mesaj sayısı
kapısının yalnız konuşma mesajlarını sayması (sunucu 48 öğeye izin veriyor,
istemci 24'te durduruyordu).

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
- [x] Döküm konuşmayı ve üretilen görselleri aynı akışta gösteriyor — Adım 7a
      (§0.6): `result` kartı + silinmiş görsel yer tutucusu + üretimin açık
      oturuma katılması
- [ ] Arama yalnızca Medya'da; klasörler gezinme (kökte klasör kartları + klasörsüzler)
- [ ] Dört tema da kontrast kapılarını geçiyor; monokrom varsayılan
- [ ] Bugünkü tüm yetenekler yerinde: prompt, boyut/kalite/adet, referans + ek görsel,
      tema rengi/palet, logo/motto/banner + offset, klasörler, çoklu seçim, indirme,
      büyüteç, Azure ayarları, yönetmen sohbeti, içe aktarma
      (**yedekler bilerek düştü** — bkz. §0.2 ertelenen D7)
- [ ] 1024×700'de taşma yok
- [ ] `pytest` tamamen yeşil (994'ten düşen her test id defterinde gerekçeli)
- [ ] `test_id_contract.py` yeşil: kayıp id yok, sarkan JS bağı yok, defter dürüst
- [ ] Tarayıcı konsolu 0 hata
- [ ] DM Sans `latin-ext` ile paketli; `.app` içinde font dosyası doğrulandı

### §0.2 denetiminin maddeleri — mandal

Aşağıdaki kutular §0.2'den geliyor. **Amaç tam olarak şu:** bir madde ancak
işaretlenerek ya da gerekçesiyle ertelenerek kapanabilir; listede yazmayan bir
şey "yapıldı" sayılamaz. §0.1'in elle yazılmış listesi bu ağ olmadığı için
wordmark'ı, kebab'ı ve §4.2'nin iki düğmesini kaçırdı.

Adım **7b**'ye bağlı (A1–A6) — **altısı da 7 Ağustos'ta kapandı (§0.7)**:

- [x] Kütüphane kendi görünümü (ray düğmesi modal açmıyor) — `#view-library`;
      modal kabuğu id defteriyle kaldırıldı (`assets-modal`, `assets-close`)
- [x] Araçlar kendi görünümü, iki araç kartıyla (Görünüm · Tema rengi/paletler) —
      `#view-tools`; Azure kimliği bilerek dışarıda (dişli), testi ayrı
- [x] Medya'da arama + "Arama sonuçları — tüm klasörler" etiketi — `#media-search`,
      `loadAllImages` klasör sınırını aşıyor, kartlarda `card-where` künyesi
- [x] Izgara boyutu S/M/L — `#size-seg` yalnız `data-size` yazıyor, ölçü
      CSS'teki `--tile`'dan (110/150/210)
- [x] Azure ve Tema paneli slide-over (modal değil) — id'ler bilerek aynı kaldı
      (`settings-modal` / `palette-modal`: 152 sözleşmesi), yüzey `.sheet` oldu
- [x] Tema seçici arayüzü dört temayı uyguluyor (`data-theme` gerçekten
      yazılıyor) — monokrom özniteliği siler (§0.7/K15). **Kalıcılık hâlâ
      Adım 9'da** (panel geçiciliği yazıyla söylüyor)

Adım 5–6'ya bağlı (A7–A9):

- [x] Otomatik kayıt anahtarı; kapatınca bugünkü davranış — arka uç Adım 6,
      **arayüzü + 409'un Türkçe gösterimi Adım 7a** (`#pref-autosave`,
      Ayarlar → Oturumlar; kapalıyken satır "Otomatik kayıt kapalı — bu oturum
      diske yazılmadı")
- [x] Oturumu sil + tümünü sil — arka uç Adım 6, **bağlaması Adım 7a**
      (`#chats-delete-all`, oturum panelinin dibinde, onay pencereli).
      **Kebabın kendisi hâlâ Adım 10'da**
- [x] Oturumlar gerçekten otomatik kaydediliyor: istemci **başlıksız** `POST` ile
      açıyor, tur sonunda gövde-yalnız `PUT` ile büyütüyor — Adım 7a
      (`persistThread`; başlık uydurmak anahtarı delerdi, §0.6)
- [x] `result` rolü Azure istemine gitmiyor **ve** `MAX_CHAT_TOTAL_CHARS`'a
      sayılmıyor — Adım 5, iki katmanlı süzgeç (§0.4/K1)
- [x] Sunucu payı: sarkan `image_id` dökümü çökertmiyor, kayıt budanmıyor — Adım 5
- [x] **Ekran payı: "görsel silindi" yer tutucusu çiziliyor** — Adım 7a
      (`resultThumb`'ın `error` dinleyicisi, §0.6/K12)
- [x] **`chat.js` mesaj sayısı kapısı yalnız KONUŞMA mesajlarını sayıyor**
      (`MAX_CHAT_ITEMS` aynalandı; `MAX_CHAT_RESULTS` bilerek aynalanMADI,
      §0.6/K13) — Adım 7a
- [x] **Üretim açık oturuma katılıyor:** `session_id` iki dalda da gidiyor,
      prompt kullanıcı turu olarak döküme giriyor, sonuç kaydı ekleniyor —
      Adım 7a. Oturumu Görsel modundan BAŞLATMAK Adım 8'te yapıldı (§0.8/K19)
- [x] **`#session-title` / `#session-stamp` bağlandı** — Adım 7a. §0.2 bu ölü
      işaretlemeyi kaçırmıştı; üretim açık oturumun dökümüne düştüğü için
      "hangi oturumdayım" cevabının üst şeritte olması zorunlu

Adım 8 — §4.2'nin manşeti:

- [x] `chat.js`'te "Forma aktar" **kalmadı** (yorumlar dahil); yerine "Görsel
      modunda üret" — durum satırı da artık "form" demiyor. Adım 8, §0.8
- [x] Görsel modunda dolu kutuda "Yönetmen'e sor" çıkıyor, boş kutuda çıkmıyor
      — iki eksen iki sahip (doluluk `hidden`/chat.js, mod `display`/CSS) ve
      düğme çerçevesiz metin (§4.2'nin "ikinci dolu düğme yok" cümlesi). Adım 8
- [x] **Görsel modu kendi oturumunu başlatıyor** (K10'un ikinci yarısı, §0.8/K19):
      döküm turu koşulsuz açılıyor, oturumu `persistThread` üretimden SONRA
      yazıyor. Uydurma `session_id` yok — bedeli K20'de yazılı

Adım 9 — arka uç (**bitti**, v0.2.0 · `b7b323c`):

- [x] Tema kalıcı — ama **yeri ve adları sözleşmeden saptı**, ikisi de bilerek:
      `settings`/`credentials.env` yerine `prefs.json` (§0.5/K6'nın gerekçesi:
      bir tema adının `0600` olması anlamsız, üstelik Azure hiç yapılandırılmamışken
      tema çevrilemez olurdu) ve allowlist `kurumsal` değil `ocean`
      (`models.py:170 ALLOWED_THEMES`, `prefs.py:45`). Uçtan uca: seçim
      `POST /api/prefs` (`settings.js:132`) → açılışta geri okuma (`chat.js:1492`)
- [x] Kütüphane'de "Yüklemeler" türü + "Tümü" filtresi
      (`assets_store.py:19 KINDS` → `uploads`; `index.html:325,329`)

Adım 10 — kozmetik (**bitti**, v0.2.0–v0.2.1):

- [x] Üst şeritte kebab (oturum menüsü) — `#chats-kebab` (`index.html`, `chat.js`)
- [x] Medya'da sıralama düğmesi — `#sort-btn` (`index.html`, `folders.js`)
- [x] Klasör kartında kapak görseli (glif değil) — `.folder-thumb` (`folders.js`, `style.css`)
- [x] Medya'da `rail-count` sayacı — `index.html`, `folders.js`
- [x] Boş durumda glif + tek satır metin — `#media-empty-state` (`index.html:298`, D16 glifi)
- [x] Klasör "Yeniden adlandır" — sözleşmeye **girdi** (D17 kararı): `#folder-rename`
      (`index.html`, `folders.js`) + `PATCH /api/folders/{id}`

> **Kayıt düzeltmesi (2026-08-15).** Bu iki blok 11 Ağustos'ta yapıldığı hâlde
> işaretsiz kalmıştı; `flow_ui_step13_handoff.md` de "Gelecek Görevler" diye
> ikisini sayıyordu. Yukarıdaki her satır bugün depoda tek tek arandı ve
> karşılığı yazıldı — belgeye değil koda bakılarak. Flow-UI'dan geriye **yalnız
> DM Sans bundle** kalıyor (§4; `--font-display` "DM Sans" diyor ama
> `static/fonts/` yok, yani paket font'u taşımıyor).
