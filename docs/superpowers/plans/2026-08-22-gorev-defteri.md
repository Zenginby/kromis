# Görev defteri — sıradaki adımlar

**Tarih:** 22 Ağustos 2026 · **Son dal:** `claude/next-task-implementation-dc06i9`
**Bugünkü ölçüm:** `APP_VERSION` **0.8.0** (sonrakini CI yazıyor),
`pytest tests/ -q` → **1631 geçti / 10 atlandı**
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

### 1. `aria-selected` düz `<button>`da geçersiz (M1) · **S**
`folders.js`'te `picker-tile` düz bir `<button>`, kapsayıcı `#picker-grid` düz
bir `<div>`: `aria-selected` bu bağlamda geçersiz ARIA.
- [ ] Ya `role="listbox"` + `role="option"` çifti kurulacak, ya da seçim
      `aria-pressed` ile anlatılacak (uygulamada `aria-pressed` deseni zaten var).
- **Kabul:** ekran okuyucu ağacında seçim durumu doğru; `tests/test_index.py`'de
      bir iddia.

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

### 8. Model Arena · **M**
Aynı prompt'u iki modelde yan yana koşturup karşılaştırma (master spec Faz 3).
- [ ] **Kabul:** iki üretim tek turda, künyelerinde model + kredi; kayıtlar
      bugünkü şemayı bozmuyor.

### 9. Maske tuvali / bölgesel düzenleme · **L**
Master spec Faz 1'in açık yarısı: bugünkü `/api/edit` tüm görsel üzerinden
çalışıyor, `mask` alanı yok.
- [ ] Fırça/silgi HTML5 Canvas + `mask` alanının adaptör sözleşmesine girmesi
      (Azure ve OpenAI destekliyor; Gemini'de karşılığı farklı).
- **Kabul:** maskelenen bölge dışında piksel değişmiyor (golden fixture).

### 10. Stil çipleri · stil şablonları · tipografi katmanı · **M**
Faz 2'nin açık yarısı. Hazır stil çipleri (*Anime*, *Cyberpunk*, *Cinematic*,
*Pixel Art*, *3D Render*) prompt'a eklenen jetonlar; tipografi katmanı
bindirmenin metin tarafı.
- [ ] **Kabul:** çip seçimi prompt'a görünür biçimde giriyor ve geri alınabiliyor.

### 11. Özel araçlar: Upscaler · Product-in-Hand · **L**
README Faz 3. Upscaler bir sağlayıcı yeteneği; Product-in-Hand bir prompt
şablonu + referans akışı.
- [ ] **Kabul:** her ikisi kendi kredi etiketiyle katalogda.

### 12. Image-to-Video motoru · **L**
README Faz 4 (master spec Faz 3'ün video payı). Yeni bir medya TÜRÜ: depo,
küçük resim, büyüteç ve indirme yolları video tanımıyor.
- [ ] **Kabul:** üretilen video kayıtta, galeride oynatılabiliyor, indirilebiliyor.

### 13. i18n (TR/EN) · **M**
Arayüz metinleri bugün HTML/JS içinde birebir Türkçe; sözlük katmanı yok.
- [ ] **Kabul:** dil anahtarı `prefs.json`'a yazılıyor, iki dilde de 360px'de
      taşma yok (İngilizce metinler daha uzun).

### 14. SaaS dönüşümü · **XL**
Kendi tasarım belgesi var: `docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md`
(Faz 5). Kredi tarifesi katalogda **metadata olarak** hazır; ledger, hesaplar,
depolama, ödeme ve filigran açık.
- [ ] **Kabul:** o belgenin kendi kabul ölçütleri; buraya alınmadan önce ayrı
      bir uygulama planı yazılır.

### 15. PWA · iOS · **L**
Android teslim (Chaquopy APK); PWA'nın service worker/manifest'i ve iOS yok.
- [ ] **Kabul:** çevrimdışı açılış ve "ana ekrana ekle" akışı çalışıyor.

---

## Bilinçli olarak YAPILMAYANLAR

macOS paketleme planından devralınan liste, hâlâ geçerli: Apple
**notarization**, **universal2/Intel** paketi, **DMG** kurulumcusu. Ücretli
sertifika ve ölçülmemiş bir dağıtım yüzeyi istiyorlar; "Yine de Aç" akışı
`KURULUM.md` ve `GUNCELLEME.md`'de yazılı ve çalışıyor.
