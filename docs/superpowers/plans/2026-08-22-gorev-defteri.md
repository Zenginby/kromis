# Görev defteri — sıradaki adımlar

**Tarih:** 23 Ağustos 2026 · **Son dal:** `claude/arena-mode-planning-design-orhatc`
**Bugünkü ölçüm:** `APP_VERSION` **0.9.2** (sonrakini CI yazıyor),
`pytest tests/ -q` → **1721 geçti / 10 atlandı**
**Defterin açılış ölçümü** (Tur A öncesi): `APP_VERSION` 0.7.0 → 1613 geçti / 10 atlandı
(atlananlar her iki ölçümde de yalnız Windows'a özgü DACL testleri + kurulu
olmayan Playwright)

Bu defter **canlı** bir belgedir: bitmiş turların kaydı ve sıradaki işin tanımı
burada durur. Yol haritaları (README fazları, `2026-08-10-saas-transformation-master-design.md`
§5) **ne** yapılacağını söylüyor; bu defter **sırayı** ve **kanıtı** taşıyor.

---

## Nasıl kullanılır (her oturum)

1. Bu dosyayı oku. **En üstteki açık tur** sıradaki iştir; başka bir şeye
   geçmek için gerekçe yazılır.
2. Turu bitir, sonra kutuyu **kanıtla** işaretle: test sayısı, tarayıcı ölçümü
   ve commit. Kanıtsız işaretlenmiş kutu, işaretlenmemiş kutudan kötüdür.
3. Bir madde ancak **işaretlenerek** ya da **gerekçesiyle ertelenerek** kapanır
   (flow-ui `§7` disiplininin aynısı: iddia silinmez, yeniden yazılır).
4. Kuyruktan bir madde alındığında **üste taşınır** ve kendi adım listesini
   orada kazanır. Kuyruk sırası bir söz değil, öneri: kullanıcı sırayı
   değiştirebilir.

---

## ✅ Tur D — Model Arena (kuyruk maddesi 8)

**Bitti (23 Ağustos).** Kuyruğun **8. maddesi** üste alındı. Kapsam oturumda
netleşti: 2–4 model seçilebilir · sütun başına AYRI kayıt, ortak `arena_id` ·
yalnız üretim (`/api/edit` kapsam dışı) · kazanan işaretleniyor, elenen
sonuç SİLİNMİYOR · yüzey composer'da bir anahtar · kalite ekseni SIRA ile
eşleniyor.

- [x] **Fan-out İSTEMCİDE, sunucuda değil.** Turun kendisi model başına ayrı
      bir `POST /api/generate`; sunucuya yeni bir üretim ucu, kuyruk ya da iş
      parçacığı havuzu GİRMEDİ. Üç ölçülmüş sebep: (a) zaman aşımı bütçesi
      model başına hesaplanıyor (`providers.total_budget`), tek istekte
      fan-out isteği en yavaş modele bağlardı — Nano Banana Pro'lu bir turda
      dakikalarca asılı bir bağlantı; (b) uçtaki hata modeli tek yollu
      (`except ac.ImageError → 502`, app.py:379) ve "3 modelden 1'i düştü"yü
      ifade edemiyor; (c) sunucu zaten çok iş parçacıklı (senkron `def` +
      anyio havuzu), yani N istek gerçekten paralel koşuyor.
      **Ölçüldü** (Chromium 1024×700): iki istek arasındaki fark **0.000s**,
      iki sütun **0.7s**'de doldu.
- [x] **Şema göçü YOK.** `arena_id` kayda KOŞULLU yazılıyor
      (`imported`/`session_id` deseninin aynısı, storage.py) — arena dışı
      üretimin kaydı bugünküyle bayt bayt aynı. **Ölçüldü:** arena kapalıyken
      tek istek gidiyor, son kayıtta `arena_id` anahtarı HİÇ yok.
      `ResultParams.arena_id` de boş dize varsayılanıyla geldi (v0.6'da
      `model`in girdiği yolun aynısı), yani v0.6 öncesi oturumlar geçerli
      kalıyor.
- [x] **Eksen çevirisi arenanın asıl işi ve TEK yerde.** Modellerin jeton
      kümeleri farklı: Azure `1024x1536`, Gemini `2:3`; Azure düşük/orta/yüksek,
      Gemini 1K/2K/4K. Kullanıcı TEK ayar seçiyor, `arenaSutunlari()` model
      başına çeviriyor — boyut ORAN üzerinden (`sizes[].ratio` sunucudan
      geliyor, istemci jeton ayrıştırmıyor), kalite SIRA üzerinden. Aynı
      fonksiyonu hem maliyet göstergesi hem üretim isteği okuyor: iki ayrı
      yerde çevrilseydi gösterilen fiyat ile faturalanan tur ayrışırdı.
      **Ölçüldü:** Azure "Orta" seçiliyken Gemini sütunu "2K" ile koştu, tur
      maliyeti `≈ 14 kredi · 2 model` (8 + 6) yazdı ve diskteki kayıtlar
      `credits` 8 ve 6 ile indi. Sıra varsayımının bekçisi ayrı bir test:
      katalogdaki her modelin kalite demeti ARTAN sırada olmak zorunda.
- [x] **Boyut listesi seçili modellerin KESİŞİMİ.** Kesişim dışı bir oran bazı
      sütunları sessizce kendi varsayılanına düşürürdü ve karşılaştırma farklı
      çerçevelerde yapılırdı — aynı prompt'u aynı koşulda koşturmak arenanın
      tanımı.
- [x] **İKİNCİ bir model yüzeyi açılmadı.** Arena, `#model-sheet`in ÜÇÜNCÜ
      ekseni (`MODEL_EKSENLERI`e yeni anahtar): aynı liste, aynı `secilebilirler`
      filtresi, aynı perde/Escape/Android-geri mekaniği; tek fark kartların
      radyo yerine checkbox olması. `tests/test_index.py`'nin koruduğu tekillik
      korundu, iddiası "iki çip" yerine "üç çip" olarak GÜÇLENDİRİLDİ.
- [x] **Kısmi başarısızlık gerçekten sütunda kalıyor.** **Ölçüldü:** üç modelli
      turda biri kasten düşürüldü — 3 sütun çizildi, 2'si doldu, düşenin hatası
      kendi sütununda kaldı, `#status` "2/3 model üretti. gpt-image-1: …" yazdı,
      diske yalnız 2 kayıt indi ve kazanan düğmesi yalnız dolan iki sütunda
      göründü.
- [x] **Kazananın TEK kaynağı `history.json`.** Döküm kaydına ikinci bir kopya
      yazılmadı: oturum kaydedilmeyen bir turda ikisi ayrışırdı. Depo tarafı
      tek yazımda hallediyor (kazanana `arena_win`, kardeşlerden anahtarı
      SİLİYOR) — iki ayrı yazım arada okuyan bir istemciye iki kazanan
      gösterirdi. **Ölçüldü:** işaret diske indi, fikir değiştirilince tek
      kazanan kaldı, sayfa yenilenip oturum yeniden açıldığında satır 2
      sütunuyla ve işaretiyle geri geldi.
- [x] **Adet arenada 1'e kilitli** (satır gizli): 4 model × 4 görsel hem
      ızgarayı hem faturayı okunmaz yapardı ve bir sonuç kaydının `image_ids`
      tavanı zaten bir TURUN çıktısı kadar.
- [x] **Sessiz sapma yok.** Arena açıkken referans eklenirse `#go` kilitleniyor
      ve sebebi yazıyor ("Arena düzenlemeyle çalışmıyor — referansı kaldır");
      beşinci model seçilmeye çalışılınca kutucuk geri alınıyor ve tavan
      söyleniyor. **İkisi de ölçüldü.**
- [x] **Telefon.** 360px'de satır en çok 2 sütun; ölçülen karo **143px**.
      Dört sütun bırakılsaydı karo ~73px olurdu — o karşılaştırma değil, küçük
      resim şeridi. **Ölçüldü:** 360×780'de taşma x = 0, konsol temiz.
- [x] **Kanıt:** takım **1686 → 1721 geçti / 10 atlandı** (`tests/test_arena.py`
      14 iddia: etiket, biçim kapısı, iki modelin kendi kredisi, kazananın tek
      yazımı, idempotanlık, başka turun görselinde 404; `tests/test_arena_onyuz.py`
      21 iddia: fan-out, çeviri tekliği, kesişim, tek yazar, tavan, gruplama,
      mobil ızgara). Chromium 1024×700 ve 360×780 ölçümleri yukarıda.

---

## ✅ Tur C — Medya seçici telefonda kullanılamıyordu + geçersiz ARIA

**Bitti (22 Ağustos).** Bu tur **kullanıcı şikâyetiyle** açıldı, kuyruktan
değil: telefonda (+) → "Medya'dan seç" açılınca sağ bölme ekranın tamamını
kaplıyor, ızgara bir şeride iniyor ve **üstteki görseller seçilemiyordu**.
Kuyruğun **1. maddesi** (geçersiz ARIA) aynı tura katıldı — aynı bileşene
dokunuyor, ayrı turda yapmak aynı üç dosyayı iki kez açmak olurdu.

- [x] **Sağ bölme telefonda alt şeride indi.** Kök neden ölçüldü: mobil katman
      kartı tek sütuna indiriyor (`mobile.css`, `"phead" "pnav" "pbody"
      "pside"`) ama bölmenin DÜŞTÜKTEN SONRA ne kadar yer kaplayacağı hiç
      sınırlanmamıştı — masaüstü kuralları 180px'lik bir sütun için yazılmış,
      telefonda 360px'in tamamında koşuyordu. `pbody` ise `minmax(0, 1fr)`,
      yani **tabanı sıfır**: bölmeye ne kalırsa ızgaraya o kalıyordu.
      **Ölçülen hâl 360×780'de: ızgara 21px, tam görünen karo 0, ilk karonun
      merkezine `elementFromPoint` başka bir öğe döndürüyor** — yani şikâyet
      mecazi değil, karo gerçekten tıklanamıyordu.
      Bölme artık iki sütunlu kompakt bir şerit: 72px önizleme + yanında künye,
      altında yan yana iki düğme. `.picker-side`'ın kendi `overflow-y: auto`'su
      bunu HİÇ çözmüyordu ve ayrım kuralın gövdesine yazıldı: taşan bölme
      değil, **ezilen ızgara**.
- [x] **İki emniyet kilidi.** `max-height: 40vh` + satır tanımı
      `minmax(0, 1fr) auto`: künye beklenmedik biçimde uzasa (iç içe klasör
      zinciri — kuyruktaki "iç içe klasör etiketi" maddesinin konusu) bölme
      ekranın %40'ını aşamıyor ve küçülen tek şey künye satırı oluyor — `auto` satırlar küçülmediği için
      sınıra dayanınca kırpılan ilk şey **düğmeler** olurdu.
- [x] **Alt güvenli alan payı geldi.** `.picker-card` yalnız `padding-top`
      alıyordu (`.modal-card`'ın iki kenarlı kuralı seçiciyi bilerek
      kapsamıyor, kartın kendi sınıfı var). Android'de jest çubuğu "Ek olarak
      ekle"nin üstüne biniyordu: düğme görünüyor ama basılamıyor — bu dosyanın
      açtığı kırılma sınıfının aynısı.
- [x] **İki düğme yan yana ve sarma KURALA bağlı.** `flex-basis` rem tabanlı
      (Tur B'nin `.chat-hint` dersi: Android WebView sistem yazı ölçeğini
      uyguluyor, piksel eşiği cihazdan cihaza farklı karar verir).
      **Yan yana dizince iki eski kusur görünür oldu ve ikisi de ölçüldü:**
      `.primary`nin `margin-top: 1rem`i (dikey yığın mirası) satırı 16px
      uzatıp düğmenin kendisini 16px kısaltıyordu — "Referans yap" 44px,
      "Ek olarak ekle" 60px ve ikisi alt kenarlarından hizalıydı; `.primary`
      hiç font bildirmediği için UA'nın 13.33px'ini alıyor, `.btn-ghost` ise
      `font: inherit` ile 15px'te duruyordu. İkisi de yalnız mobil blokta
      düzeltildi. `font` KISA BİÇİMİ kullanılmadı: `.primary`nin
      `font-weight: 500`ünü sıfırlar ve birincil eylem inceleşirdi.
- [x] **Kuyruk maddesi 1 — `aria-selected` → `aria-pressed`.** `.picker-tile`
      düz bir `<button>`, kapsayıcısı düz bir `<div>`; `aria-selected` yalnız
      `option`/`tab`/`row`/`treeitem`/`gridcell` rollerinde geçerli.
      **Ölçüldü:** düzeltme öncesi erişilebilirlik ağacında seçili karo için
      `pressed` özelliği YOK (ağaçtaki tek `pressed` mod anahtarınınki),
      sonrasında iki tane — yani seçim ekran okuyucuya gerçekten ulaşmıyordu.
      `role="listbox"/"option"` çifti reddedildi: gezinen tabindex + ok tuşu
      modeli ister, depoda öyle bir desen hiç yok; `aria-pressed` altı yerde
      zaten kurulu.
- [x] **İkiz kural tekilleşti.** `.picker-tile[aria-selected="true"]` **iki
      kez** tanımlıydı (biri gezinme bölümüne düşmüş); ikisi `background` ve
      `outline` için çakışıyordu, ikizden hayatta kalan tek bildirim
      `box-shadow`du. Tek kurala indirildi, boyanan sonuç birebir aynı.
- [x] **İkizin ÖTEKİ YARISI da tekilleşti** (aynı turun kapanışı, istek
      üzerine). Gezinme bölümüne düşen yapıştırma iki kuraldan oluşuyordu;
      `aria-selected` yarısı yukarıda kapandı, `.picker-tile:hover` yarısı
      kaldı. Aynı mekanizma: eşit özgüllük, kaskad sırası karo bölümündeki
      `background`ı kazandırıyor — ikizin `--accent-surface` tercihi hiç
      boyanmıyordu — ama `box-shadow`u kimse ezmediği için o BOYANIYORDU.
      **Buradaki asıl risk temizliğin kendisiydi:** ikizi yalnızca silmek,
      üzerine gelince beliren accent kenarını da sessizce götürürdü. Chromium
      ölçümü önce/sonra birebir aynı: üzerine gelinen karo
      `rgb(39,39,40)` + `inset 0 0 0 1px rgba(255,255,255,.2)`, seçili+üzerine
      gelinen karo `rgb(53,54,55)` + `outline 2px` (yani seçim hover'a
      yenilmiyor — sıra bilinçli ve mandallı).

**Kanıt.** Takım **1632 → 1637 geçti / 10 atlandı**. *(Yukarıdaki "defterin
açılış ölçümü" satırı 1631 diyordu; Tur C'nin ölçtüğü taban 1632 — defterin
sayısı bir gerideymiş, kayıt düzeltiliyor.)* Dört yeni mandal ve
**hepsi mutasyonla doğrulandı — on beş mutasyon, on beşi de kırmızı**:
kare önizlemenin sabit boyu, `max-height`, satır tanımı, kuralın medya
sorgusunun dışına kaçması, alt güvenli alan, rem tabanı, `width: auto`,
`min-height: var(--tap)`, `margin-top: 0`, JS'in özniteliği, CSS'in seçicisi,
hover kenarının düşmesi, ikizin geri konması ve iki kuralın sırasının
ters çevrilmesi.

**Tarayıcı ölçümü** (Chromium 1194, dokunmatik bağlam, seçicide 36 karo):

| Ölçü | 360×780 önce | 360×780 sonra | 360×640 sonra | 800×700 | 1024×700 |
|---|---|---|---|---|---|
| ızgara (`.picker-body`) | **21px** | **506px** | 366px | 502px | 502px |
| bölme (`.picker-side`) | 656px | **171px** | 171px | 502px×180 | 502px×180 |
| önizleme | 327px kare | 72px | 72px | 147px | 147px |
| tam görünen karo | **0** | **6** | 6 | 9 | 6 |
| ilk karo tıklanabilir | **hayır** | evet | evet | evet | evet |
| ikinci karo dokununca seçildi | **hayır** | evet | evet | — | — |
| iki düğme aynı satırda | — | evet | evet | hayır (yığın) | hayır (yığın) |
| yatay taşma | 0 | 0 | 0 | 0 | 0 |
| konsol | temiz | temiz | temiz | temiz | temiz |

Masaüstü **hiç değişmedi**: kart 776×570, yan bölme 180px, üç sütun — bütün
kurallar `@media (max-width: 768px)`in içinde ve bir mutasyon tam olarak bunu
mandallıyor (kuralı sorgunun dışına taşımak testi kırmızıya düşürüyor).

> **Ölçülen tuzak (mandalın kendisinde).** İlk yazımda mobil iddialar CSS
> gövdesini **yorumlarıyla birlikte** okuyordu ve bu dosyanın kuralları
> gerekçesini kendi gövdesinde yazıyor: `max-height` bildirimini silen mutasyon,
> "`max-height` devreye girdiği anda…" diyen YORUM sayesinde **hayatta kaldı**.
> İkinci tuzak aynı turda: `minmax(0, 1fr)` gövdede aranınca
> `grid-template-columns`taki aynı değere takılıyordu, yani satır tanımını
> `auto auto`ya çeviren mutasyon da geçiyordu. Yardımcı artık yorumları
> ayıklıyor (brace sayımından ÖNCE) ve iddia `grid-template-rows`un DEĞERİNE
> bakıyor. §0.6/§0.7/§0.9'un "iddia kodu arar, kelimeyi değil" dersinin
> beşinci ve altıncı kurbanı.

> **Plandan sapma (gerekçeli).** Plan beşinci madde olarak bir Playwright
> ölçüm testi öngörüyordu. Yazılmadı: `playwright` paketi CI'da kurulu değil
> (`test_playwright_studio.py` zaten `importorskip` ile atlanıyor) ve bu
> kaptaki tarayıcı sürümü paketinkiyle uyuşmuyor — eklenen test hiçbir yerde
> koşmaz, yalnız ikinci bir atlanan dosya olurdu. Tarayıcı ölçümü Tur A ve
> B'nin yaptığı yerde duruyor: yukarıdaki tabloda.

---

## ✅ Tur B — Tasarım ölçütünün ihlalleri + composer alt satırı

**Bitti (22 Ağustos).** Kuyruğun **1. maddesi** sıradaki işti. **6. madde**
kuyruktan alınıp aynı tura katıldı ve gerekçesi teknik: 1'in üçüncü bulgusu
(`⚙` → "Ayarlar düğmesi") `#status`'a yazılan metni ~15 karakter **uzatıyor**,
bugünkü `.chat-hint { flex: 1 }` kuralında ise uzayan `#status` ipucunu daha da
eziyordu. Yani 6 olmadan 1 sıkışmayı **kötüleştiriyordu**; ikisi ayrı turda
yapılamazdı. Üstelik `.folder-target` zaten `.composer-foot`'un içinde yaşıyor,
yani iki madde aynı satırı paylaşıyor.

- [x] **`#settings-update`'teki `🎉` düştü.** Yerine sade metin: satır artık
      `Yeni sürüm çıktı:` diyor. İşaret gerekmiyor çünkü satır varsayılan olarak
      `hidden` ve yalnız gerçekten yeni sürüm varken açılıyor — **varlığı**
      işaretin kendisi. Metin `GUNCELLEME.md` ve README'nin bu satırı anlattığı
      sözlerle birebir aynı; emoji o belgelerde hiç yoktu. Hatlı SVG glif yolu
      **reddedildi** (Tur A'nın ölçtüğü sessiz kusur — geçersiz XML →
      `naturalWidth = 0`, konsolda tek hata yok — bu yola da bulaşırdı).
      JS bağlantısı yok: JS yalnız sürüm ve adresi yazıyor, satırın metnine hiç
      dokunmuyor.
- [x] **`.folder-target`'ın vurgu renkli sol kenarı nötrleşti.** Token zinciri
      kardeş `.chat-gate`'ten **birebir** alındı
      (`var(--border-strong, var(--control-border))`) — hedef hâl elde vardı.
      Gerekçe kuralın gövdesinde yazılı: `--accent` bu kod tabanında yalnız
      DURUM anlatıyor (`flow-tokens.css`), `.folder-target` ise durum değil,
      "bulunduğun klasöre eklenecek" diye statik bir ipucu (tetikleyici
      sürükleme DEĞİL, klasörün İÇİNDE olmak).
- [x] **ÜÇÜNCÜ BULGU — 21 Ağustos denetimi bunu saymamıştı.** `settings.js`
      durum metnini üç yerde `(sağ üstteki ⚙)` diye yazıyordu; üst şeritteki
      gerçek düğme ise hatlı bir SVG dişli (`aria-label="Ayarlar"`), yani glif
      düğmenin görünüşünü **yanlış** söylüyordu. Metin artık düğmenin adını
      veriyor. **Ölçülen ikinci kusur:** dize üç kez elle yazılıydı ve biri
      **nöbetçi** (`includes(…)` — durum satırını temizleyen kapı). Biri
      değişip öteki kalsa hata VERMEZ, satır ekranda asılı kalırdı. Tek sabit:
      `AYARLAR_EKI`.
- [x] **Composer alt satırında ipucu tek satırda** (kuyruk maddesi 6).
      **Ölçülen mekanizma:** `.chat-hint { flex: 1 }` kısa biçimi
      `flex: 1 1 0%`e çözülüyor, yani taban genişliği **SIFIR**. Satırdaki tek
      esnek öğe buydu — `#status` bir `<p>` (`flex: 0 1 auto`, tabanı içerik
      genişliği), `.run-cost` ise `flex: none`. Taban artık içerikten geliyor ve
      `nowrap` sarmayı kapatıyor; satır zaten `flex-wrap: wrap`, yani sığmayan
      kardeş alta düşüyor. **`#status`'a kural EKLENMEDİ ve bu bilinçli:**
      `flex-basis: 100%` gibi bir kural durumu her zaman kendi satırına atardı
      ve ipucu telefonda zaten gizli, yani 360px'de bedava bir satır yüksekliği
      demekti. Kısa durum metni ipucuyla aynı satırda kalmaya devam ediyor.

**Kanıt.** Takım **1625 → 1631 geçti / 10 atlandı** (atlananlar yine yalnız
Windows'a özgü DACL testleri + kurulu olmayan Playwright);
`test_id_contract.py` 12 geçti. Altı yeni mandal ve **hepsi mutasyonla
doğrulandı** (sekiz mutasyon, sekizi de kırmızı): `test_index.py`'de
emoji taraması, güncelleme cümlesi, tek sabit, sol kenar ve `.chat-hint`;
`test_mobile.py`'de ipucunun telefonda hâlâ gizli olduğu.

*Emoji mandalı ölçütü mandallıyor, tek düzeltmeyi değil:* iki kademeli
(kademe 1 astral düzlem + VS16 → HTML·JS·CSS; kademe 2 Misc Symbols + Dingbats
→ HTML·JS) ve taradığı dosyaları **HTML'den keşfediyor**, yani sayfaya eklenen
yeni bir `.js`/`.css` mandalın dışında kalamıyor. **CSS kademe 2'den muaf** ve
gerekçesi testte yazılı: `content: "✓ "` tek renkli, metin sunumlu bir dingbat —
yani bu defterin `🎉` yerine **önerdiği** "hatlı glif" biçiminin kendisi.
Sol kenar mandalı da aynı biçimde genel: tek kurala değil `style.css` ve
`mobile.css`'teki **her `border-left` bildirimine** bakıyor.

**Tarayıcı ölçümü** (Chromium; `1024×700` = en küçük pencere, `800×700` =
768px kırılımı ile onun arası, `360×780` = telefon). `#status`'a
`goBlockReason`'ın en uzun çıktısı + yeni `AYARLAR_EKI` yazılıyken:

| Ölçü | 1024×700 | 800×700 | 360×780 |
|---|---|---|---|
| `.chat-hint` | **18px · 1 satır** (`flex-basis: auto`, `nowrap`) | 18px · 1 satır | `display: none` |
| ÖNCE (aynı düzenek, `flex: 1`) | **53px · 3 satır** (`flex-basis: 0%`) | — | — |
| yatay taşma | 0 | 0 | 0 |
| konsol | temiz | temiz | temiz |

`#folder-target`'ın sol kenarı **dört temada da** `rgba(255,255,255,0.18)`:
`.chat-gate` ile eşit, `--accent`'in hesaplanmış değerine eşit değil.
Güncelleme satırında astral kod noktası yok.

> **Ölçülen tuzak (ölçümün kendisinde).** İlk tema turunda `--accent`
> `documentElement`'ten okundu ve dört temada da `#e8eaed` çıktı — "tema
> değişmiyor" gibi görünen bu sonuç bir **ölçüm hatasıydı**: temalar `body`'ye
> yazılıyor (`[data-theme=…]` seçicisi), yani override `html`'de görünmüyor.
> `body`'den okununca dört tema gerçekten ayrıştı. Kayıt burada duruyor çünkü
> yanlış ölçüm "kanıt" diye yazılsa kutu kanıtsız işaretlenmiş olurdu.
>
> **İkinci tuzak (araç).** Mutasyon turunda `git checkout -- <dosya>` ile geri
> alma, henüz **commit edilmemiş** düzeltmeyi de siliyor: bir mandal o yüzden
> "hayatta kaldı" gibi göründü, oysa mutasyonun hedef dizesi dosyada artık yoktu
> ve `replace` sessizce hiçbir şey yapmadı. Geri alma scratchpad kopyalarına
> çevrildi ve mutasyon betiği artık hedefi bulamazsa **patlıyor**
> (`assert s.count(a) == 1`).

---

## ✅ Tur A — Model şeritlerinde sağlayıcı işareti + koşullu Yönetmen bölümü

**Bitti (22 Ağustos).** İki iş de kullanıcı isteğiydi; kararlar sorulup
onaylandı.

- [x] **Model şeritlerinde sağlayıcı logosu.** Seçili modelin sağlayıcısı çipin
      içinde, solda bir işaretle gösteriliyor; model değişince işaret değişiyor.
      Native `<select>` **korundu** (Android'de sistem seçicisi + ARIA gerekçesi
      `index.html`'de yazılı): native `<option>` görsel taşıyamadığı için açılan
      listede işaret yok, gösterilebilen tek şey seçili model.
      **Eşleme katalogda** (`catalog.PROVIDER_LOGOS` + `provider_logo`), adres
      sunucuda kuruluyor (`app._provider_logo_url`, `?v=` damgası `index()`in
      deseni) ve istemci yalnız `logo` alanını okuyor — sağlayıcı adı istemcide
      hiç sayılmıyor.
      **Kanıt:** `tests/test_provider_logos.py` (8 iddia; biri "adaptörü olan
      her sağlayıcının işareti var", yani logosuz yeni adaptör suite'i kırar),
      `test_index.py`'de beş işaretleme/JS mandalı, `test_mobile.py`'de iki
      sarmalayıcı mandalı. Chromium (1024×700 **ve** 360×780): işaret 14×14 ve
      çipin İÇİNDE, model değişince `src` değişiyor, mod anahtarı gizli şeridin
      **kabuğunu** da gizliyor, taşma x/y = 0, konsol temiz.
      **Ölçülen tuzak:** ilk yazımda dosyaların yorumunda çift tire (`--fg`)
      vardı; XML'de yasak olduğu için tarayıcı 200 alıp **hiçbir şey çizmedi**
      (`naturalWidth = 0`, boyanan piksellerin hepsi panel arka planı). Konsolda
      tek hata yoktu. Mandalı `test_isaretler_GECERLI_XML_ve_ICSEL_boyutlu`.
- [x] **Ayarlar'da koşullu "Prompt Yönetmeni (sohbet modeli)" bölümü.**
      Sağlayıcı dağıtım adı istemiyorsa (OpenAI · Gemini) **başlık da** gidiyor;
      "bu sağlayıcıda dağıtım adı yok" paragrafı tümden kaldırıldı (gizli bir
      başlığın altında hiç görünemezdi). Kapı yine **katalogdan** türetiliyor
      (`chat_models[].needs_deployment`) ve **fail-open** kalıyor.
      Talimat dosyası yolu **koşulsuz** duruyor, kendi başlığıyla
      ("Prompt Yönetmeni · talimat") — keşfedilebilirlik gerekçesi
      `index.html`'de yazılı.
      **Kanıt:** `test_index.py`'de üç iddia yeniden yazıldı + biri yeni
      (talimat yolunun koşullu grubun DIŞINDA olduğu). Chromium: Azure'da
      başlık + kutu var, OpenAI ve Gemini'de ikisi de `display: none`, talimat
      satırı üç sağlayıcıda da görünür.
- [x] **Şerit satırlarında marka öneki kalktı** (kullanıcı geri bildirimi, aynı
      tur). İşaret markayı söylediği için `Gemini · Nano Banana 2` satırı aynı
      bilgiyi iki kez yazıyordu; satır artık `Nano Banana 2` diyor. Kısaltma
      **sunucuda** (`catalog.short_labels` → `/api/settings`'in yeni
      `short_label` alanı): istemci ne marka adı sayıyor ne dize kırpıyor.
      `label` **değişmedi** — hata metinleri, `#model-note` ve durum satırı tam
      adı okumaya devam ediyor.
      **Çakışma kuralı** (ölçülmüş): katalogda `gpt-image-2` adını taşıyan İKİ
      model var (Azure · OpenAI). Önek ikisinden de düşerse açılan listede aynı
      iki satır oluşur ve native `<option>` işaret taşımadığı için logo onları
      ayırmaz — o yüzden kısa adı çakışan model tam etiketini koruyor.
      **Kanıt:** takım 1613 → **1622 geçti / 10 atlandı** (`test_catalog.py`'de
      altı iddia — kural, çakışma, `Azure AI Foundry dağıtımı`nın kırpılmaması,
      liste içinde tekillik; `test_settings_route.py`'de donmuş alan kümesi +
      yeni gövde iddiası; `test_index.py`'de "istemci kırpmıyor" mandalı).
      Chromium 1024×700 ve 360×780: satırlar `Nano Banana 2` / `GPT-5.6 Terra` /
      `3.7 Flash`, iki `gpt-image-2` önekli, işaret 14×14 ve `naturalWidth > 0`,
      taşma x/y = 0, konsol temiz.

---

## Bekleyen kuyruk

Sıra öneri; her madde **neden · dokunulacak yer · kabul ölçütü · büyüklük**
taşıyor. Büyüklükler: **S** tek oturum, **M** bir tur, **L** kendi planını
isteyen iş, **XL** kendi tasarım belgesi olan faz.

### 1. Seçicide karo seçilince ODAK KAYBOLUYOR · **S**
Tur C'nin `aria-pressed` işini yarıda bırakan kusur, kod gözden geçirmesinde
çıktı: `#picker-grid` tıklamasında `renderPickerGrid()` çağrılıyor ve o
`grid.innerHTML = ""` ile bütün karoları **yeniden kuruyor**
(`folders.js:1070-1072`). Klavyeyle bir karoya Enter'a basan kullanıcının
odaklı düğümü yok oluyor, odak `<body>`'ye düşüyor — yani ekran okuyucu
kullanıcısı seçtiği karonun artık "pressed" olduğunu **duymuyor** ve gezinmeye
diyaloğun başından devam etmek zorunda kalıyor. Kusur `aria-selected`
döneminden beri var, ama `aria-pressed` düzeltmesinin faydasını tam olarak
o kullanıcıda siliyor. Karo yeniden kurulmak yerine yalnız özniteliği
güncellenebilir (eski seçili `false`, yeni seçili `true`) ya da yeniden
kurulumdan sonra `data-id`'den odak geri verilebilir.
- [ ] **Kabul:** klavyeyle karo seçildikten sonra `document.activeElement`
      hâlâ o karo; iddia mutasyonla doğrulanıyor.

### 2. Seçicide iç içe klasör etiketi (K27) · **S/M**
`picker-tile` künyesi yalnız en yakın klasörün adını yazıyor; iç içe klasörlerde
"hangi A altındaki B" sorusu cevapsız. `folders.js`'te kök→klasör zinciri
(`parentOf` zinciri zaten var, kırıntı başlığı onu kullanıyor) künyeye taşınacak.
- [ ] **Kabul:** iki seviyeli klasörde künye "A / B" yazıyor; genişlik 360px'de
      taşmıyor.

### 3. Sonuç kartında "Düzenle" / "+ Ek" (K14) · **M**
Karar "tam bir geçmiş kaydı ister" diye ertelenmişti; döküm bugün yalnız
`image_id` taşıyor. Kart eylemleri için kaydın kendisi lazım.
- [ ] **Kabul:** sonuç kartından doğrudan düzenlemeye/ek referansa geçilebiliyor
      ve silinmiş görselde yer tutucu davranışı bozulmuyor.

### 4. `gitleaks` işi CI'da · **S**
Adım 1 planının tek açık maddesi: geçmiş taramasının kaydı yok.
- [ ] `.github/workflows/ci.yml`'e bir iş; `credentials.env` deseni ve test
      sabitleri için allowlist gerekiyor (`tests/test_errlog.py` sahte anahtar
      taşıyor).
- **Kabul:** iş yeşil koşuyor ve gerçek bir sızıntı denemesinde kırmızıya dönüyor.

### 5. Ayarlar'da canlı bağlantı testi düğmeleri · **M**
README Faz 2'nin son açık maddesi. Bugünkü karşılık yalnız "anahtar kayıtlı mı"
listesi; gerçek bir çağrı denemesi yok.
- [ ] Sağlayıcı başına küçük bir uç (`POST /api/settings/test`?) + düğme;
      hata metinleri `providers._ICERIK_REDDI` çevirisinden geçmeli.
- **Kabul:** yanlış anahtarda anlaşılır Türkçe hata, doğru anahtarda "bağlantı
      kuruldu"; anahtar yanıtta HİÇ yankılanmıyor (write-only sözleşmesi).

### 6. Yerel sağlayıcı adaptörleri: ComfyUI · Ollama · **L**
Anahtar/adres alanları v0.2.0'dan beri kayıtlı, **adaptör ve arayüz yok**
(`azure_client.get_settings_status` yalnız durum bayrağı döndürüyor).
- [ ] `providers._ADAPTERS`'a iki adaptör, katalogda modeller, Ayarlar'da
      gruplar, `catalog.PROVIDER_LOGOS`'a iki işaret (mandal onu zorluyor).
- **Kabul:** yerel bir kurulumla üretim yapılabiliyor; sağlayıcı düşükken hata
      Türkçe ve anlaşılır.

### 7. fal.ai · Replicate adaptörleri · **L**
Aynı boşluğun bulut yarısı; ikisi de **kuyruklu** akış (`providers`'ın zaman
aşımı politikası bunu zaten öngörüyor: "adet başına ayrı istek atan sağlayıcı").
- [ ] **Kabul:** kuyruk beklerken arayüz ilerleme gösteriyor, zaman aşımı
      sağlayıcıya göre çözülüyor (`tests/test_providers.py`'nin deseni).

### 8. Maske tuvali / bölgesel düzenleme · **L**
Master spec Faz 1'in açık yarısı: bugünkü `/api/edit` tüm görsel üzerinden
çalışıyor, `mask` alanı yok.
- [ ] Fırça/silgi HTML5 Canvas + `mask` alanının adaptör sözleşmesine girmesi
      (Azure ve OpenAI destekliyor; Gemini'de karşılığı farklı).
- **Kabul:** maskelenen bölge dışında piksel değişmiyor (golden fixture).

### 9. Stil çipleri · stil şablonları · tipografi katmanı · **M**
Faz 2'nin açık yarısı. Hazır stil çipleri (*Anime*, *Cyberpunk*, *Cinematic*,
*Pixel Art*, *3D Render*) prompt'a eklenen jetonlar; tipografi katmanı
bindirmenin metin tarafı.
- [ ] **Kabul:** çip seçimi prompt'a görünür biçimde giriyor ve geri alınabiliyor.

### 10. Özel araçlar: Upscaler · Product-in-Hand · **L**
README Faz 3. Upscaler bir sağlayıcı yeteneği; Product-in-Hand bir prompt
şablonu + referans akışı.
- [ ] **Kabul:** her ikisi kendi kredi etiketiyle katalogda.

### 11. Image-to-Video motoru · **L**
README Faz 4 (master spec Faz 3'ün video payı). Yeni bir medya TÜRÜ: depo,
küçük resim, büyüteç ve indirme yolları video tanımıyor.
- [ ] **Kabul:** üretilen video kayıtta, galeride oynatılabiliyor, indirilebiliyor.

### 12. i18n (TR/EN) · **M**
Arayüz metinleri bugün HTML/JS içinde birebir Türkçe; sözlük katmanı yok.
- [ ] **Kabul:** dil anahtarı `prefs.json`'a yazılıyor, iki dilde de 360px'de
      taşma yok (İngilizce metinler daha uzun).

### 13. SaaS dönüşümü · **XL**
Kendi tasarım belgesi var: `docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md`
(Faz 5). Kredi tarifesi katalogda **metadata olarak** hazır; ledger, hesaplar,
depolama, ödeme ve filigran açık.
- [ ] **Kabul:** o belgenin kendi kabul ölçütleri; buraya alınmadan önce ayrı
      bir uygulama planı yazılır.

### 14. PWA · iOS · **L**
Android teslim (Chaquopy APK); PWA'nın service worker/manifest'i ve iOS yok.
- [ ] **Kabul:** çevrimdışı açılış ve "ana ekrana ekle" akışı çalışıyor.

---

## Bilinçli olarak YAPILMAYANLAR

macOS paketleme planından devralınan liste, hâlâ geçerli: Apple
**notarization**, **universal2/Intel** paketi, **DMG** kurulumcusu. Ücretli
sertifika ve ölçülmemiş bir dağıtım yüzeyi istiyorlar; "Yine de Aç" akışı
`KURULUM.md` ve `GUNCELLEME.md`'de yazılı ve çalışıyor.
