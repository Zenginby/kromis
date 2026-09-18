# Stüdyo güncelleme planı — sahibin ileriye dönük notları

**Tarih:** 2026-09-18 · **Kaynak:** Alperen Zengin'in "Kromis Plans.md" notu (Slack, aynı gün) · **Durum:** plan, görev DEĞİL · **Yerleştirme:** öneri, karar sahibin
**Bağlam:** SaaS dönüşümü [Faz 0](faz0-web-first.md) (8/8 ✅) → [Faz 1](faz1-veritabani-hesaplar.md) (9/9 ✅) → [Faz 2](faz2-kuyruk-anahtarlar-depolama.md) (7/10, sürüyor) → Faz 3 kredi defteri → Faz 4 ödeme/KVKK → Faz 5 işletme; stüdyo arayüzünün bugünkü tasarım kaynağı [flow-ui/flow-redesign-plan.md](flow-ui/flow-redesign-plan.md) (§4.1 ray, §4.2 composer)

Sahip, Faz 2 sürerken stüdyo arayüzünde ileride istediği değişiklikleri tek
bir not olarak verdi. Bu belge o notu **kaybolmayacağı bir yere** koyuyor ve
her maddenin yanına üç şey yazıyor: bugün kodda ne var (koda bakılarak, belgeye
değil), neye bağlı, hangi faza oturması önerilir. Hiçbir madde bu belgeyle
göreve dönüşmüyor; faz belgelerinin "Faz N dışı" bölümleri gibi bir bekleme
odası. Sahibin ifadesi en sonda ["Sahibin notları (aynen)"](#sahibin-notları-aynen)
bölümünde birebir duruyor — gruplama ve başlıklar bu belgenin yorumu, metin
onun.

Neden şimdi yazıldı: Faz 2'nin kalan üç görevi (8 admin, 9 günlük, 10
operasyon) `static/isler.js`e ve iş paneline dokunuyor; buradaki iki küçük
madde (süre göstergesi, "180" gözlemi) o dokunuşa binebilir, geri kalanı
binmemeli — ayrımı kaydetmek için.

---

## Bugünkü zemin — plan hangi parçaların üstüne konuşuyor

Sahibin notu "stüdyo penceresi" diyor; koddaki karşılığı **composer**
(`static/index.html` `#composer`, `data-mode` ekseni `image | video | director`)
ve onun açtığı yüzeyler. Notun dokunduğu her parça ve bugünkü hâli:

| notun dediği | koddaki karşılık | bugünkü biçim |
| --- | --- | --- |
| görsel / video / yönetmen seçimi | `.seg.view-tabs.mode` — `#tab-image`, `#tab-video`, `#tab-chat` (`index.html` "Mod anahtarı"); `core.js setMode`, ⌘/Ctrl+J | üç düğmeli **bölmeli anahtar** (kayan dolgu `#view-tabs-thumb`), açılır menü değil |
| üretim ayarları | `#specs-btn` çipi → `#specs-sheet` | **sağdan kayan panel** (`.sheet-right`): boyut/oran, kalite, adet, süre, palet şiddeti, bindirme |
| yönetmen ayarları | `#director-btn` → `#director-sheet` | sağdan kayan panel, yalnız yönetmen modunda |
| model seçimi | `#model-btn` / `#video-model-btn` / `#chat-model-btn` / `#arena-btn` → `#model-sheet` | **alttan açılan** tek panel (`.sheet-bottom`, `data-axis`) — notun istediği "üste doğru açılan" deseni bugün yalnız burada var |
| tema (arayüz) | Araçlar sayfası `#tool-look` kartı → `#look-sheet` (`#theme-picker`, 4 tema) | sağdan panel; seçim `POST /api/prefs` ile kalıcı (`settings.js saveThemePref`) |
| tema rengi / paletler | Araçlar `#tool-palette` kartı ve composer'daki "+ Tema rengi" → `#palette-modal` | sağdan panel; `palette.js` notu üretim/düzenleme ayrımını yazıyor (`#palette-mode-note`) |
| logo ekleme | `#specs-sheet` içindeki `.assets-panel` → `#logo-add-btn` → `#logo-modal` | ayar panelinin dibinde; Medya karosunda ve büyütecte (`viewer.js`) bindirme girişi YOK |
| kredi | `#run-cost` (composer dip satırı) ← `core.js syncRunCost` | model × boyut/kalite × adet, videoda × süre; arena açıkken **toplam + "N model"**; yönetmen modunda gizli (`style.css`) |
| işlem süresi | `#isler-sheet` paneli, `isler.js sureMetni` | iş satırında "12 sn" / "1:05", her saniye tazelenir; dökümdeki bekleme kartında (`chat.js` `.is-pending`) ve yönetmenin `#chat-wait`inde sayaç YOK |
| geçmiş oturumlar | `header.topbar` içinde `#chat-sidebar-toggle` (hamburger), `#chat-new`, `#chats-kebab` (yeniden adlandır / temizle / tümünü sil) | üst şerit bölümlerin DIŞINDA, yani dört sayfada da görünür; `core.js showSection` şeride dokunmuyor |
| arena kazananı | `.arena-win[aria-pressed="true"]` (`style.css`), `storage.set_arena_winner` → kayda `arena_win: true` | kazanan düğmesi vurgulu; **Medya/kütüphane karosu `arena_win`i okumuyor** (`folders.js`, `assets.js`, `viewer.js`'te geçmiyor) |
| araçlar sayfası | `#view-tools`: iki kart (palet, görünüm); ray `#rail-tools` | `.rail-item:hover` yalnız renk değiştiriyor; ray daraltma (`#rail-collapse`, 72 px) var |
| pencere küçültme | — | composer'ı ya da dökümü katlayan bir denetim yok; yalnız ray daraltılıyor |

---

## A. Stüdyo penceresi düzeni

Beş madde, hepsi composer'ın kendisi. Ortak nokta: bugün **sağdan kayan
paneller** olan şeylerin composer'dan **yukarı doğru açılan küçük menüler**
olması. Model seçicinin `#model-sheet`i bu desenin var olan tek örneği;
A2-A3 onun deyimini üretim ayarlarına ve temaya taşımak demek. Bu, tasarım
belgesinin §4.2 "tek composer, iki mod" kararının üstüne yazılır — orası
güncellenmeden başlanmamalı.

### A1. Mod seçimi açılır menü + yanında Yönetmen düğmesi

* **İstek:** Görsel/Video bir açılır menüden seçilsin; Yönetmen ayrı bir
  düğme olarak hemen yanında dursun.
* **Bugün:** üç düğmeli bölmeli anahtar; sıra bilinçli ("Yönetmen bir turdur,
  en sağda kalıyor" — `index.html` yorumu). ⌘/Ctrl+J üçünü dolaşıyor.
* **Etkisi:** `core.js setMode`, `syncTabThumb` (kayan dolgu kalkar),
  `#composer[data-mode]` ekseni aynen kalır; `tests/test_index.py` ve E2E
  çapaları (`tab-image/-video/-chat` id'leri) yeniden yazılır — id sözleşmesi
  `docs/flow-ui/id-defteri.md`ye işlenir.
* **Bağımlılık:** yok. **Öneri:** Stüdyo arayüz yenilemesi bloğu (aşağıda).

### A2. Üretim ayarları composer'dan yukarı açılan küçük pencere

* **İstek:** `#specs-btn`e basınca ayarlar sağdan değil, düğmenin üstünde
  küçük bir pencerede açılsın.
* **Bugün:** `#specs-sheet` sağdan kayan panel; içinde boyut/oran, kalite,
  adet, video süresi, palet şiddeti, **bindirme** (A5 bunu taşıyor) ve
  kütüphane düğmesi var — yani "küçük pencere"ye sığmayan bir içerik.
* **Not:** A5 ile birlikte düşünülmeli: bindirme paneli çıkınca kalan içerik
  küçülür. Mobilde alttan panel (`#model-sheet` deseni) doğal karşılık.
* **Bağımlılık:** A5. **Öneri:** aynı blok.

### A3. Tema düğmesi composer'da; masaüstünde yukarı açılır, mobilde popup

* **İstek:** tema seçimi stüdyo penceresine bir düğme olarak gelsin.
* **Bugün:** iki ayrı "tema" var ve not ikisini de aynı sözcükle anıyor:
  **arayüz teması** (Mono/Okyanus/Amber/Menekşe — Araçlar → Görünüm →
  `#look-sheet`) ve **tema rengi/paletler** (üretime giden renk paleti —
  Araçlar → `#palette-modal`, composer'da "+ Tema rengi"). Notun E1
  maddesi "temayı sadece görsel üretmede kullanıyoruz" diyor; bu yalnız
  **palet** için doğru (arayüz teması her sayfada geçerli). Bu belge A3 ve
  E1'deki "tema"yı **tema rengi/palet** okuyor — **sahip doğrulamalı.**
* **Etkisi:** "+ Tema rengi" çipi zaten composer'da; iş, açtığı panelin
  biçimini değiştirmek (sağdan → yukarı/popup) ve palet önerilerinin dar bir
  alana sığdırılması.
* **Bağımlılık:** yok. **Öneri:** aynı blok.

### A4. Stüdyo penceresi küçültülebilir — sağ üstte aşağı ok

* **İstek:** stüdyo penceresinin sağ üstünde aşağı bakan bir ok; tıklanınca
  pencere küçülsün.
* **Bugün:** composer'da böyle bir denetim yok; tek "katlama" ray daraltma
  (`#rail-collapse`, `.app.rail-collapsed`).
* **Açık soru:** "pencere" composer mı (prompt kutusu + ayar şeridi tek
  satıra insin), döküm mü, ikisi birden mi? Mobilde composer zaten alt
  kenarda — orada küçülme ne demek? Tasarım belgesi güncellenirken sahibe
  sorulacak; katlanmış durum `prefs`e yazılır (tema gibi kalıcı).
* **Bağımlılık:** yok. **Öneri:** aynı blok.

### A5. Logo ekleme yeri: Medya'ya ya da odaklanmış görsele; ayar panelinden çıkar

* **İstek:** bindirme (logo/motto/banner) Medya'daki görsel üzerinde ya da
  ekranda odaklanmış görselde yapılsın; görsel ve video ayarlarından kalksın.
* **Bugün:** giriş noktası yalnız `#specs-sheet` → `.assets-panel` →
  `#logo-add-btn` (seçili sonuç yokken `disabled`); işi yapan `#logo-modal`
  (9'lu ızgara, boyut, kaydırma, canlı önizleme) ve sunucu bindirme ucu. Medya
  karosunun eylemleri "Referans", indir, taşı; büyütecin (`viewer.js`)
  denetimlerinde bindirme yok.
* **Etkisi:** `#logo-modal` olduğu gibi kalır (giriş noktası değişir, motor
  değişmez); karoya/büyütece bir "Bindirme" eylemi eklenir; `#specs-sheet`
  küçülür (A2'nin önkoşulu). Bindirme ürettiği yeni kaydı zaten galeriye
  yazıyor — akış Medya'dan başlayınca kullanıcı sonucu aynı yerde görür.
* **Bağımlılık:** yok; A2 buna bağlı. **Öneri:** aynı blok, A2'den önce.

## B. Göstergeler

### B1. Sol altta seçili modelin kredi maliyeti; arenada toplam

* **İstek:** seçili modele göre ne kadar kredi harcanacağı sol altta yazsın;
  arena açıksa modellerin toplamı.
* **Bugün:** **büyük ölçüde var.** `#run-cost` composer'ın dip satırında;
  `core.js syncRunCost` model × boyut/kalite × adet (videoda × süre), arena
  açıkken `toplam · N model` yazıyor; tarife SUNUCUDAN geliyor (istemci fiyat
  mantığı taşımıyor — çift kopya gerekçesi `core.js`te). Yönetmen modunda
  gizli. Eksik olan yalnız **konum** (sahibin "sol alt"ı) ve **anlam**: bugün
  yazan katalog **tahmini**, bakiye yok, düşüm yok (`isler.kredi_tahmini`
  Faz 2 / 6).
* **Bağımlılık:** konum için yok; gerçek maliyet/bakiye için **Faz 3 kredi
  defteri** ("rezerve → onayla", tarife-maliyet mutabakatı — Faz 2 belgesi
  "Faz 2 dışı"). **Öneri:** konum arayüz bloğunda, "kaç kredin kaldı / bu tur
  ne düşer" Faz 3'te — ikisini tek maddede çözmeye çalışmamak.

### B2. Yönetmen ve üretimde geçen süre (sn / dk)

* **İstek:** yönetmen düşünürken ve üretim sürerken işlemin ne kadar
  sürdüğü saniye/dakika olarak görünsün.
* **Bugün:** iş panelinde var (`isler.js sureMetni`: "12 sn" → "1:05", her
  saniye `sureleriTazele`), ama dökümdeki bekleme kartında (`chat.js`
  `.is-pending` + `.pending-shimmer`) ve yönetmenin `#chat-wait`inde
  (spinner + "düşünüyor") yok. Veri hazır: `isler.basladi/bitti`
  (`services/kuyruk.py _json`) 202 gövdesiyle ve SSE ile geliyor;
  `kromisIsler.kaydetIs(is, {bitince, hatada})` bekleme kartını işe
  bağlıyor. Yönetmen sohbeti kuyruğa girmiyor (senkron `/api/chat`), orada
  sayaç istemci saatiyle tutulur.
* **Bağımlılık:** yok. **Öneri:** küçük madde; Faz 2 / 10'un `isler.js`
  dokunuşuna binebilir (bkz. aşağıda "180") ya da arayüz bloğunun ilk kalemi.

### B3. Doğrulanacak gözlem — "üretim süresi açılan panelde 180'den başlıyor"

Sahip iş panelinde sayacın 180'den başladığını görüyor. Koda bakınca
mekanizması **büyük olasılıkla saat dilimi**, sayaç hatası değil:

* `services/zaman.py damga()` DB'deki `timestamptz` anı **sunucunun yerel
  saatine** çevirip **dilimini soyuyor** (`2026-09-18T18:44:25`); belgesi
  bunu bilerek yapıyor — `created_at` istemcinin masaüstü döneminden beri
  gördüğü dizeyle aynı kalsın diye ("sunucuyla aynı makine saati varsayımı",
  `isler.js an()` yorumu da aynısını söylüyor).
* Web'de bu varsayım düştü: konteyner (`python:3.13-slim`, `compose.yaml`de
  `TZ` yok) **UTC**, sahip **UTC+3**. `_json` `basladi`yi UTC duvar saati
  olarak dilimsiz yazıyor; tarayıcı dilimsiz ISO'yu **kendi yerel saati**
  sayıyor (`new Date("2026-09-18T18:44:25")`), yani başlangıcı 3 saat GERİYE
  alıyor; `sureMetni` `şimdi − basladi` = 3 saat + gerçek süre → **"180:00"**
  ile açılıyor (biçim `dk:ss`). Sunucunun doğusundaki her kullanıcı kendi
  farkını görür; batısındaki `Math.max(0, …)` yüzünden gerçek süre farkı
  aşana kadar **0'da takılır**. Testler tek makinede koştuğu için görünmez.
* Aynı dize galerinin `created_at`ine de gidiyor (`folders.js` sıralama
  bundan etkilenmez, aynı kayma; ama "az önce/bugün" gibi gösterimler
  etkilenir) ve `GET /api/isler?since=`e geri dönüyor (`routers/isler.py
  _since` dilimsizi sunucu yereli sayıyor — kendi dizesini geri aldığı için
  tutarlı, sorun yok).
* **Doğrulama:** UTC sunucu + tarayıcıda `TZ=Europe/Istanbul` ile bir iş
  kuyruğa at; panel "180:xx"le açılıyorsa doğrulanmış demek. **Aday çözüm
  (bu belgede yapılmıyor):** `isler` yükünde damgaları dilimli ISO
  (`isoformat()` `+00:00`/`Z` ile) vermek — `an()` `Date`'e dilimli dize
  verir, sıralama dizesi (`localeCompare`) de aynı ofsetle bozulmaz; ya da
  `_json`a `gecen_sn` eklemek. İkisi de `zaman.py`nin belgelenmiş "tek
  biçim" kararına dokunur, önce o gerekçe okunur. **Yeri:** Faz 2 / 10'un
  `static/isler.js` dokunuşu (belgede "Dokunulan"da) — ya da B2 ile birlikte
  ayrı küçük PR. Faz 3'ün `bitti − basladi` marj raporu sunucu tarafında
  hesaplanır, bundan etkilenmez.

## C. Gezinme ve durum korunumu

### C1. Sayfa değiştirince üretim animasyonu kayboluyor; dönüşte döküm en baştan açılıyor

* **İstek:** Medya'ya gidip stüdyoya dönünce bekleme animasyonu sürsün ve
  döküm **en alttan** (son mesaj) açılsın.
* **Bugün — kaydırma:** `core.js showSection` dört `.section`a `hidden`
  yazıyor; ama kaydıran kap ortak **`.canvas`** (`style.css` `overflow-y:
  auto`). Medya'ya geçince kapın içeriği kısalır, `scrollTop` kırpılır;
  dönüşte döküm kırpılmış konumda (çoğu zaman tepede) görünür. Kabul
  edilebilir çözüm: bölüm başına `scrollTop` hatırlamak ya da stüdyoya
  dönüşte son mesaja `scrollIntoView` (`chat.js scrollMessageIntoView`
  zaten var). **Doğrulanacak.**
* **Bugün — animasyon:** bekleme kartı `#chat-log`ta kalıyor
  (`showSection` `resetThread` çağırmıyor), iş bağlamı `baglamlar` haritasında
  ("yalnız bu sekmede", `isler.js`). Kaybolmanın mekanizması koddan
  okunamadı — `display:none` sonrası CSS animasyonunun yeniden başlaması
  beklenir, kaybolması değil. **Ölçülmesi gerekir**: hangi mod (görsel /
  video / arena), hangi tarayıcı; `prefers-reduced-motion` açık mı.
* **Bağımlılık:** yok. **Öneri:** arayüz bloğu; kaydırma kısmı B2 gibi küçük
  ve erken alınabilir.

### C2. Hamburger, yeni sohbet ve silme yalnız stüdyoda görünsün

* **İstek:** geçmiş oturumlar (hamburger), yeni sohbet ve silme düğmeleri
  üst sabit şeritten kalksın, yalnız stüdyo sayfasında görünsün.
* **Bugün:** `#chat-sidebar-toggle`, `#chat-new`, `#chats-kebab` (yeniden
  adlandır / temizle / tümünü sil) `header.topbar`da, bölümlerin dışında;
  `showSection` şeride dokunmuyor. Oturum başlığı `#session-title` de orada.
  Android geri tuşu (`window.geriTusu`) `#chats-kebab-menu`yu tanıyor — yer
  değişirse o seçici de.
* **Etkisi:** ya `showSection` `data-section` yazıp CSS gizler (en ucuz), ya
  düğmeler stüdyo bölümünün içine taşınır (tasarım §4.1 üst şerit kararı
  değişir). `tests/test_mobile.py` ve E2E çapaları.
* **Bağımlılık:** yok. **Öneri:** arayüz bloğu.

## D. Arena

### D1. Kazanan seçilince animasyon; kütüphanede farklı çerçeve rengi

* **İstek:** kazanan model seçildiğinde etrafında bir animasyon, seçilen
  belli olsun; kazanan görseller Medya'da farklı renkte çerçeveyle görünsün.
* **Bugün:** kazanan düğmesi vurgulu (`.arena-win[aria-pressed="true"]`),
  sütunda başka işaret yok; sunucu kazanana `arena_win: true` yazıyor ve aynı
  turun ötekilerinden siliyor (`storage.set_arena_winner`; rota
  `routers/galeri.py`); **Medya karosu bu alanı okumuyor.** Yani ikinci yarı
  yalnız ön yüz: karoya `data-arena-win` + bir çerçeve rengi (tema
  değişkeninden, `--accent` gibi).
* **Bağımlılık:** yok. `tests/test_arena_onyuz.py` `markArenaWinner`
  gövdesini ölçüyor — animasyon oraya eklenir. **Öneri:** arayüz bloğu, küçük.

## E. Görünüm ve araçlar sayfası

### E1. Görünüm Ayarlar'a taşınsın; tema (palet) yalnız görsel modunda seçilsin

* **İstek:** "Görünüm" kartı Araçlar'dan Ayarlar'a; tema (bkz. A3'teki
  okuma: **palet**) yalnız görsel seçiliyken seçilebilsin.
* **Bugün:** Ayarlar'ın bölmeleri (`#settings-modal` `.picker-nav-item`):
  erişim, yönetmen, oturumlar, dil, hakkında — görünüm bölmesi yok;
  `#look-sheet` Araçlar kartından açılıyor. Palet çipinin video modunda
  görünüp görünmediği mod ekseninde (`style.css` `#composer[data-mode]`
  blokları) **doğrulanmalı**; video üretimi palet parametresi almıyorsa
  gizlenmesi tutarlı.
* **Etkisi:** `#look-sheet` içeriği Ayarlar'a bölme olarak girer (radyo
  kalıbı `radio-row` zaten Ayarlar'ın dil bölmesiyle aynı); Araçlar'da bir
  kart kalır (palet) — E2 onu dolduruyor.
* **Bağımlılık:** yok. **Öneri:** arayüz bloğu.

### E2. Hızlı araçlar: arka plan temizleme, vesikalık, görselden prompt

* **İstek:** Araçlar sayfasına tek adımlık araçlar.
* **Bugün:** Araçlar'da iki kart. **Arka plan kaldırma** zaten yol
  haritasında: [ozellikler.md](ozellikler.md) "Faz 3: E-Ticaret Ürün
  Araçları — Otomatik Arka Plan Kaldırma & Konu Gölgeleme" (açık kutu).
  Vesikalık ve görselden prompt yeni; üçü de bir **sağlayıcı çağrısı** ister
  (kredi, kuyruk, anahtar çözümü — Faz 2'nin `isler` hattından geçer) ve
  katalogda bir "araç" türü (`isler.tur` bugün dört değer:
  `services/tablolar.py IS_TURLERI`).
* **Bağımlılık:** Faz 2 iş hattı ✅; kredi düşümü Faz 3. **Öneri:** ürün
  maddesi, arayüz bloğu değil — Faz 3 "ürün araçları" kartına ek; her araç
  kendi küçük tasarım notunu ister.

### E3. Fareyle Araçlar'a gelince yana açılan küçük araç şeridi

* **İstek:** rayda Araçlar'ın üstüne gelince araçlar yana doğru küçük bir
  şerit hâlinde belirsin.
* **Bugün:** `.rail-item:hover` yalnız renk; daraltılmış ray (72 px) var.
  Hover menüsü klavye ve dokunmatikte karşılık ister (odakla açılma, mobilde
  tıklama) — tasarım §4.1 ve erişilebilirlik notu.
* **Bağımlılık:** E2 (gösterilecek araçlar). **Öneri:** E2 ile birlikte.

## F. Uzak ufuk — medya düzenleme sayfası

* **İstek:** Medya'dan video/görseli sürükle-bırak, altına ses yükle,
  birleştir — stüdyoda bir düzenleme işlemi. Sahibin kendi notu: "çok
  ilerideki aşamalarda detaylı planlanması lazım".
* **Bugün:** sürükle-bırak var ama **taşıma** için (görsel → klasör,
  bilgisayardan içe aktarma; `folders.js`); `<video>` oynatılıyor, kesme /
  birleştirme / ses yok; sunucuda video işleme aracı (ffmpeg gibi) yok,
  imaj 284 MB ve her ek araç imaj boyutu ve işçi CPU'su demek.
* **Öneri:** **Faz 5+**, kendi tasarım belgesiyle
  (`docs/superpowers/specs/` deyimi): tarayıcıda mı sunucuda mı işlenir,
  hangi biçimler, kredi birimi ne (saniye? dosya?), depoda türev bağı
  (`parent_id` videoya da uzar mı). Bu belge yalnız yerini tutuyor.

---

## Yerleştirme — ÖNERİ (karar sahibin)

| grup | ne | neden orada | öneri |
| --- | --- | --- | --- |
| B1 (gerçek kredi / bakiye) | tur maliyeti + kalan kredi | defter, rezerve/onayla, gerçek tarife Faz 3'te; bugünkü `#run-cost` tahmindir ve zaten var | **Faz 3** (konum değişikliği arayüz bloğunda) |
| B2 + B3 | süre göstergesi; "180" gözlemi | yalnız `isler.basladi/bitti` ister (var); Faz 2 / 10 `isler.js`e zaten dokunuyor | **Faz 2 / 10'a küçük kalem** ya da hemen ardından ayrı küçük PR |
| A1-A5, C1-C2, D1, E1 | composer düzeni, gezinme, arena işareti, görünümün taşınması | saf ön yüz, sunucu değişmez; tasarım §4.1-4.2 kararlarını günceller; E2E çapaları toplu yeniden yazılır | **"Stüdyo arayüz yenilemesi" tek blok** — doğal yeri **Faz 4** (K3: ön yüz çerçevesine yeniden bakış orada; çerçeve değişecekse bu blok o çerçevede yazılır) **ya da** sahibin seçtiği Faz 2 → 3 arası mini faz (vanilla ile) |
| E2 + E3 | hızlı araçlar ve yan şerit | sağlayıcı çağrısı + kredi düşümü + katalog türü | **Faz 3** ürün araçları kartına ek |
| F | medya düzenleme | ayrı ürün, ayrı altyapı | **Faz 5+**, kendi spec'i |

**Blok için ölçü (başlarken alınır):** `static/` betikleri + `index.html`
16.783 satır (bu belge yazılırken; `chat.js` 2.773, `core.js` 3.226,
`index.html` 2.028), E2E çapaları `docs/flow-ui/id-defteri.md`de; blok başlamadan
`flow-redesign-plan.md` §4'e bir "2026 revizyonu" bölümü yazılır, kabul
ölçütleri oraya. Hangi çerçevede yazıldığına göre (K3) maliyet iki kat
farklı — bu yüzden Faz 4 önerisi: karar bir kez verilir, iki kez ödenmez.

**Sahibe açık sorular:** (1) A3/E1'deki "tema" palet mi arayüz teması mı?
(2) A4'teki "pencere" composer mı, döküm mü? (3) A1'de Yönetmen düğmesi
mod mu (bugünkü gibi), yoksa "Yönetmen'e sor" gibi bir eylem mi?

---

## Sahibin notları (aynen)

Kaynak: "Kromis Plans.md", 2026-09-18. Aşağısı düzenlenmemiş; yukarıdaki
gruplama bu satırların yorumu.

```
# Studyo Güncelleme Planı
- görsel ve video üretme dropdown ile açılıp seçilebilsin, hemen yanında da yönetmen butonu olsun
- uygulamamızdaki tema seçimini de stüdyo penceresine ekleyelim buton olarak, butona tıklayınca tema seçimi kısmı üste doğru dropdown olarak açılsın mobilde ise popup olarak açılabilir. Logo eklemeyi medya üzerinde yada ekranda odaklanmış görsel üzerinde yapalım video ve görsel ayarları kısmından kaldıralım
- görsel ve video üretme ayarları stüdyo penceresindeki butona basınca dropdown şeklinde üste doğru açılsın ve küçük bir pencere içerisinde ayarlamalarını yapabilelim
- sol altta seçilen modele göre ne kadar kredi harcayacağı da yazsın ve arena modu seçilirse modellerin toplam kredisine göre harcama değeri yazsın
- Yönetmen ve üretim kısımlarında işlemin ne kadar sürdüğünü saniye ve dakika cinsinden gösterelim
- Uygulama içerisinde başka bir sayfaya geçtiğimde görsel ve video üretme animasyonu kalkıyor ve başka sayfadan stüdyo kısmına geri geldiğimde hep sohbetin en başından başlıyor en alttan başlamasını istiyorum
- Stüdyo kısmının penceresi küçültülebilir olsun sağ üstte aşağı doğru bir ok koyalım tıklayınca küçülsün
- üretim süresi açılan panelde 180 den başlıyor
- stüdyo kısmında geçmiş oturumların görüntülenmesi üstteki hamburger butonundan açılıyor bunun sadece studyo kısmında gözükmesini istiyorum diğer sayfalarda gözükmesin hatta yeni sohbet başlatma ve silme butonlarını da üstteki sabit menüden kaldıralım sadece o sayfada gözüksün
- arena kazanan model seçilince bir etrafında bir animasyon ekleyelim seçilen belli olsun ve kazanan görseller kütüphanede çerçevesi farklı bir renkte gözüksün
- görünümü ayarlar kısmına taşıyalım ve temayı da sadece görsel üretmede kullandığımız için görsel seçili iken seçilsin, araçlar sayfasına ileride arka plan temizleme, vesikalık hazırlama, görselden prompt üretme gibi hızlı araçlar ekleyemeyi düşünüyorum, birde mouse ile araçlar sayfasına gelindiğinde yana doğru küçük bir şekilde araçlar gözüksün
- ileride uygulamaya video ve görsel düzenlemek için bir sayfa eklemeyi düşünüyorum medya içerisinden video veya görseli sürükle bırak yapıp altta ses yükleyip birleştirme gibi bir stüdyo işlemi olabilir. tabi çok ilerideki aşamalarda detaylı planlanması lazım
```
