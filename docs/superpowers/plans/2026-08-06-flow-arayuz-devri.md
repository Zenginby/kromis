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

## 0.1 Durum — nerede kaldık (7 Ağustos: PR 1 merge edildi)

**PR 1 bitti ve `main`'e indi.** [PR #16](https://github.com/Zenginby/gpt-image-studio/pull/16)
squash ile merge edildi; `main`'e inen tek commit **`a1478d4`**. Merge sonrası
ağaç hash'i dal ucuyla birebir aynı (`a717ef93`), yani squash'ta içerik kaybı yok.

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
| 5 · veri modeli (PR 2) | **bitti** (7 Ağustos, §0.4) | commit'lenmedi |
| 6 · otomatik kayıt (PR 2) | **bitti** (7 Ağustos, §0.5) | commit'lenmedi |
| 7a · JS dokunuş noktaları — **PR 2'nin ekran payı** | **bitti** (7 Ağustos, §0.6) | commit'lenmedi |
| **7b · JS dokunuş noktaları — PR 1'in giydirme borcu (A1–A6)** | **sırada** | — |
| 8 · §4.2'nin tamamlanması (devrin manşeti) | §0.2 denetiminden geldi | — |
| 9 · tema kalıcılığı + Kütüphane yüklemeleri | §0.2 denetiminden geldi | — |
| 10 · kozmetik süpürme | §0.2 denetiminden geldi | — |
| — · Yedekler paneli | **ertelendi** (§0.2) | — |

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
- **DM Sans bundle** (§4). İndirme izni alındı; **indirmeden önce dosya adı ve
  boyutu söylenip son onay alınacak.** `latin` + `latin-ext` şart (Türkçe),
  400 + 500.
- **Tema seçici arayüzü** — dört tema (`kurumsal` / `amber` / `viola` / monokrom)
  token katmanında hazır, seçici yok. Yeri sözleşmede belli: Araçlar → Görünüm.
  **Artık adıma bağlandı:** JS tarafı Adım 7 (`settings.js (tema…)`), kalıcılık
  tarafı Adım 9 — çünkü `SettingsRequest`'te tema alanı yok ve Adım 7 "mantık
  değişmez" diyor. Bkz. §0.2/D8.

**Devam etmek için (yeni oturum).** Adım 5, 6 ve **7a** bitti (§0.4, §0.5, §0.6),
**commit'lenmedi**: çalışma ağacı `main`'in ucunda, `pytest` **1080 yeşil**.
**PR 2 tamam** — arka uç ve ekran payı birlikte. Sıradaki tur **Adım 7b**:
`Adım 7` satırının PR 1'den devraldığı giydirme borcu (§0.2'nin A1–A6'sı).

```
docs/flow-ui/flow-redesign-plan.md ve docs/superpowers/plans/2026-08-06-flow-arayuz-devri.md
dosyalarını tamamen oku (§0.0 revizyonu, §0.1 durumu, §0.4/§0.5/§0.6 adım
kayıtları dahil). PR 1 merge edildi; PR 2 (Adım 5-6-7a) çalışma ağacında duruyor.

Bu turda sadece Adım 7b'yi yap: §0.2'nin A1–A6 maddeleri, yani PR 1'in
giydirme borcunun JS payı. §7'de kutulu:
  · Kütüphane kendi görünümü olsun (ray düğmesi modal açmasın),
  · Araçlar kendi görünümü olsun, iki araç kartıyla (Görünüm · Tema rengi/paletler),
  · Medya'da arama + "Arama sonuçları — tüm klasörler" etiketi,
  · Izgara boyutu S/M/L,
  · Azure/Ayarlar ve Tema panelleri slide-over olsun (modal değil),
  · tema seçici arayüzü dört temayı uygulasın (`data-theme` gerçekten yazılsın).

Tema KALICILIĞI bu turda DEĞİL — o Adım 9'un arka uç işi (§0.3). Bu tur
seçiciyi kurup `data-theme`'i yazıyor, oturum arası hatırlamayı Adım 9 ekliyor.

Kısıtlar §1'de: id ancak defterde gerekçesiyle ve JS bağı birlikte silinerek
kaldırılır (§1.1), negatif testler ihlal edilmez (§1.2), viewer.js yeniden
yazılmaz (§1.3). TDD: önce kırmızı test.

Bitirince §1.4'ün kanıtlarını göster — bu tur işaretlemeye dokunuyor, yani
tarayıcı konsolu VE 1024/1280/1440/1920 ekran görüntüleri zorunlu.
⚠️ Doğrulamada §0.6'nın "aynı sürüm altında bayat JS" tuzağına dikkat:
`?v=APP_VERSION` aynı kaldığı için tarayıcı ESKİ dosyayı önbellekten verir.
Hepsi temiz olmadan commit yok.
```

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

Sıra §0.2'nin şiddet sırasına göre: önce sözleşmenin manşeti, sonra arka uç
gerektirenler, en sonda kozmetik.

### Adım 8 — §4.2'yi gerçekten teslim et (D13 + D14)

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

### Adım 7 — JS dokunuş noktaları — **7a bitti (7 Ağustos), kaydı §0.6'da**

> Satır İKİYE ayrıldı; gerekçe §0.6'nın başında. **7a (bitti):** PR 2'nin ekran
> payı — `result` kartı, "görsel silindi" yer tutucusu, sayı kapısı, otomatik
> kayıt + anahtar + tümünü sil, üretimin oturuma katılması. Turda verilen beş
> karar (K10–K14) ve kanıtlar **§0.6'da**. **7b (sırada):** aşağıdaki
> `folders.js` / `palette.js` / `assets.js` / `settings.js` payı, yani §0.2'nin
> A1–A6'sı.

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

Adım **7b**'ye bağlı (A1–A6) — 7a bu altı maddeye dokunmadı:

- [ ] Kütüphane kendi görünümü (ray düğmesi modal açmıyor)
- [ ] Araçlar kendi görünümü, iki araç kartıyla (Görünüm · Tema rengi/paletler)
- [ ] Medya'da arama + "Arama sonuçları — tüm klasörler" etiketi
- [ ] Izgara boyutu S/M/L
- [ ] Azure ve Tema paneli slide-over (modal değil)
- [ ] Tema seçici arayüzü dört temayı uyguluyor (`data-theme` gerçekten yazılıyor)

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
      Adım 7a. Oturumu Görsel modundan BAŞLATMAK Adım 8'in işi (§0.6/K10)
- [x] **`#session-title` / `#session-stamp` bağlandı** — Adım 7a. §0.2 bu ölü
      işaretlemeyi kaçırmıştı; üretim açık oturumun dökümüne düştüğü için
      "hangi oturumdayım" cevabının üst şeritte olması zorunlu

Adım 8 — §4.2'nin manşeti:

- [ ] `chat.js`'te "Forma aktar" **kalmadı**; yerine "Görsel modunda üret"
- [ ] Görsel modunda dolu kutuda "Yönetmen'e sor" çıkıyor, boş kutuda çıkmıyor

Adım 9 — arka uç:

- [ ] Tema `settings`'e yazılıyor (allowlist: `kurumsal`/`amber`/`viola`/monokrom), `0600`
- [ ] Kütüphane'de "Yüklemeler" türü + "Tümü" filtresi (`KINDS` testle genişletildi)

Adım 10 — kozmetik:

- [ ] Üst şeritte kebab (oturum menüsü) — Adım 6'dan sonra
- [ ] Medya'da sıralama düğmesi
- [ ] Klasör kartında kapak görseli (glif değil)
- [ ] Medya'da `rail-count` sayacı
- [ ] Boş durumda glif + tek satır metin
- [ ] Klasör "Yeniden adlandır" **veya** sözleşmeden düşürüldüğü yazılı (D17 kararı)
