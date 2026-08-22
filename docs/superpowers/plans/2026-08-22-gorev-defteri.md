# Görev defteri — sıradaki adımlar

**Tarih:** 22 Ağustos 2026 · **Dal:** `claude/review-tasks-mark-done-tcff52`
**Taban ölçüm:** `APP_VERSION` **0.7.0**, `pytest tests/ -q` → **1613 geçti / 10 atlandı**
(atlananlar yalnız Windows'a özgü DACL testleri + kurulu olmayan Playwright)

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

---

## Bekleyen kuyruk

Sıra öneri; her madde **neden · dokunulacak yer · kabul ölçütü · büyüklük**
taşıyor. Büyüklükler: **S** tek oturum, **M** bir tur, **L** kendi planını
isteyen iş, **XL** kendi tasarım belgesi olan faz.

### 1. Denetim bulguları — tasarım ölçütü ihlalleri · **S**
21 Ağustos denetiminde ölçüldü, `docs/flow-ui/flow-redesign-plan.md` §11'de
açık duran tek kutunun iki ihlali:
- [ ] `#settings-update` satırındaki `🎉` — "emoji ikon yok" ölçütünün tek
      ihlali. Yerine `.field-note` tonunda bir metin ya da hatlı bir glif.
- [ ] `.folder-target`'ın vurgu renkli sol kenarı (`style.css`) — "sol kenarı
      renkli yuvarlak kart yok" ölçütü. Kardeşi `.chat-gate` aynı biçimde ama
      nötr kenarlı, yani hedef hâl elde var.
- **Kabul:** flow-redesign §11'in son kutusu kanıtla işaretlenebiliyor.

### 2. `aria-selected` düz `<button>`da geçersiz (M1) · **S**
`folders.js`'te `picker-tile` düz bir `<button>`, kapsayıcı `#picker-grid` düz
bir `<div>`: `aria-selected` bu bağlamda geçersiz ARIA.
- [ ] Ya `role="listbox"` + `role="option"` çifti kurulacak, ya da seçim
      `aria-pressed` ile anlatılacak (uygulamada `aria-pressed` deseni zaten var).
- **Kabul:** ekran okuyucu ağacında seçim durumu doğru; `tests/test_index.py`'de
      bir iddia.

### 3. Seçicide iç içe klasör etiketi (K27) · **S/M**
`picker-tile` künyesi yalnız en yakın klasörün adını yazıyor; iç içe klasörlerde
"hangi A altındaki B" sorusu cevapsız. `folders.js`'te kök→klasör zinciri
(`parentOf` zinciri zaten var, kırıntı başlığı onu kullanıyor) künyeye taşınacak.
- [ ] **Kabul:** iki seviyeli klasörde künye "A / B" yazıyor; genişlik 360px'de
      taşmıyor.

### 4. Sonuç kartında "Düzenle" / "+ Ek" (K14) · **M**
Karar "tam bir geçmiş kaydı ister" diye ertelenmişti; döküm bugün yalnız
`image_id` taşıyor. Kart eylemleri için kaydın kendisi lazım.
- [ ] **Kabul:** sonuç kartından doğrudan düzenlemeye/ek referansa geçilebiliyor
      ve silinmiş görselde yer tutucu davranışı bozulmuyor.

### 5. `gitleaks` işi CI'da · **S**
Adım 1 planının tek açık maddesi: geçmiş taramasının kaydı yok.
- [ ] `.github/workflows/ci.yml`'e bir iş; `credentials.env` deseni ve test
      sabitleri için allowlist gerekiyor (`tests/test_errlog.py` sahte anahtar
      taşıyor).
- **Kabul:** iş yeşil koşuyor ve gerçek bir sızıntı denemesinde kırmızıya dönüyor.

### 6. Composer alt satırının sıkışması · **S**
Ölçüldü (Chromium 1024×700, **origin/main'de de var** — bu turun getirdiği bir
şey değil): `.composer-foot` içinde `.chat-hint` 65px'lik dar bir kolona
sıkışıyor, `#status` 428px alıyor. Dört satıra sarıyor.
- [ ] **Kabul:** ipucu tek satırda; 360px'de bugünkü davranış (`display: none`)
      korunuyor.

### 7. Ayarlar'da canlı bağlantı testi düğmeleri · **M**
README Faz 2'nin son açık maddesi. Bugünkü karşılık yalnız "anahtar kayıtlı mı"
listesi; gerçek bir çağrı denemesi yok.
- [ ] Sağlayıcı başına küçük bir uç (`POST /api/settings/test`?) + düğme;
      hata metinleri `providers._ICERIK_REDDI` çevirisinden geçmeli.
- **Kabul:** yanlış anahtarda anlaşılır Türkçe hata, doğru anahtarda "bağlantı
      kuruldu"; anahtar yanıtta HİÇ yankılanmıyor (write-only sözleşmesi).

### 8. Yerel sağlayıcı adaptörleri: ComfyUI · Ollama · **L**
Anahtar/adres alanları v0.2.0'dan beri kayıtlı, **adaptör ve arayüz yok**
(`azure_client.get_settings_status` yalnız durum bayrağı döndürüyor).
- [ ] `providers._ADAPTERS`'a iki adaptör, katalogda modeller, Ayarlar'da
      gruplar, `catalog.PROVIDER_LOGOS`'a iki işaret (mandal onu zorluyor).
- **Kabul:** yerel bir kurulumla üretim yapılabiliyor; sağlayıcı düşükken hata
      Türkçe ve anlaşılır.

### 9. fal.ai · Replicate adaptörleri · **L**
Aynı boşluğun bulut yarısı; ikisi de **kuyruklu** akış (`providers`'ın zaman
aşımı politikası bunu zaten öngörüyor: "adet başına ayrı istek atan sağlayıcı").
- [ ] **Kabul:** kuyruk beklerken arayüz ilerleme gösteriyor, zaman aşımı
      sağlayıcıya göre çözülüyor (`tests/test_providers.py`'nin deseni).

### 10. Model Arena · **M**
Aynı prompt'u iki modelde yan yana koşturup karşılaştırma (master spec Faz 3).
- [ ] **Kabul:** iki üretim tek turda, künyelerinde model + kredi; kayıtlar
      bugünkü şemayı bozmuyor.

### 11. Maske tuvali / bölgesel düzenleme · **L**
Master spec Faz 1'in açık yarısı: bugünkü `/api/edit` tüm görsel üzerinden
çalışıyor, `mask` alanı yok.
- [ ] Fırça/silgi HTML5 Canvas + `mask` alanının adaptör sözleşmesine girmesi
      (Azure ve OpenAI destekliyor; Gemini'de karşılığı farklı).
- **Kabul:** maskelenen bölge dışında piksel değişmiyor (golden fixture).

### 12. Stil çipleri · stil şablonları · tipografi katmanı · **M**
Faz 2'nin açık yarısı. Hazır stil çipleri (*Anime*, *Cyberpunk*, *Cinematic*,
*Pixel Art*, *3D Render*) prompt'a eklenen jetonlar; tipografi katmanı
bindirmenin metin tarafı.
- [ ] **Kabul:** çip seçimi prompt'a görünür biçimde giriyor ve geri alınabiliyor.

### 13. Özel araçlar: Upscaler · Product-in-Hand · **L**
README Faz 3. Upscaler bir sağlayıcı yeteneği; Product-in-Hand bir prompt
şablonu + referans akışı.
- [ ] **Kabul:** her ikisi kendi kredi etiketiyle katalogda.

### 14. Image-to-Video motoru · **L**
README Faz 4 (master spec Faz 3'ün video payı). Yeni bir medya TÜRÜ: depo,
küçük resim, büyüteç ve indirme yolları video tanımıyor.
- [ ] **Kabul:** üretilen video kayıtta, galeride oynatılabiliyor, indirilebiliyor.

### 15. i18n (TR/EN) · **M**
Arayüz metinleri bugün HTML/JS içinde birebir Türkçe; sözlük katmanı yok.
- [ ] **Kabul:** dil anahtarı `prefs.json`'a yazılıyor, iki dilde de 360px'de
      taşma yok (İngilizce metinler daha uzun).

### 16. SaaS dönüşümü · **XL**
Kendi tasarım belgesi var: `docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md`
(Faz 5). Kredi tarifesi katalogda **metadata olarak** hazır; ledger, hesaplar,
depolama, ödeme ve filigran açık.
- [ ] **Kabul:** o belgenin kendi kabul ölçütleri; buraya alınmadan önce ayrı
      bir uygulama planı yazılır.

### 17. PWA · iOS · **L**
Android teslim (Chaquopy APK); PWA'nın service worker/manifest'i ve iOS yok.
- [ ] **Kabul:** çevrimdışı açılış ve "ana ekrana ekle" akışı çalışıyor.

---

## Bilinçli olarak YAPILMAYANLAR

macOS paketleme planından devralınan liste, hâlâ geçerli: Apple
**notarization**, **universal2/Intel** paketi, **DMG** kurulumcusu. Ücretli
sertifika ve ölçülmemiş bir dağıtım yüzeyi istiyorlar; "Yine de Aç" akışı
`KURULUM.md` ve `GUNCELLEME.md`'de yazılı ve çalışıyor.
