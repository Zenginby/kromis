# Çoklu dil desteği — plan

**Hedef:** Arayüzün kullanıcıya görünen her parçası Türkçe ya da İngilizce
olabilsin; seçim Ayarlar'dan yapılsın ve makinede kalıcı olsun. İkinci bir iş
olarak README'deki "Yönetmen'e Türkçe yaz" iddiası düzeltilsin — o iddia
personanın 1. kuralından geliyor, yani düzeltme README'de değil ÖNCE personada.

Bu belge tasarım kararlarını ve ölçülmüş kapsamı kayda geçiriyor; uygulama
sırasında değişen bir karar buraya da yazılmalı.

---

## 0. Ölçüm — iş ne kadar

Sayılar tahmin değil, kaynaktan sayıldı (yorumlar ve docstring'ler hariç):

| yüzey | dize | not |
| --- | --- | --- |
| `static/index.html` metin düğümleri | 221 (190 benzersiz) | ray, şerit, paneller, notlar |
| `static/index.html` öznitelikleri | 126 (96 benzersiz) | 70 `aria-label`, 44 `title`, 10 `placeholder`, 2 `alt` |
| `static/core.js` | ~111 | üretim akışı, durum satırları, onay metinleri |
| `static/chat.js` | ~123 | Yönetmen baloncukları, oturum yönetimi, arena |
| `static/folders.js` | ~121 | kütüphane, klasör, toplu seçim |
| `static/assets.js` · `palette.js` · `settings.js` · `viewer.js` | ~94 | varlıklar, palet, ayarlar, büyüteç |
| `app.py` `HTTPException(detail=…)` | ~45 | doğrudan kullanıcıya çıkıyor |
| `azure_client` · `openai_client` · `gemini_client` · `veo_client` · `azure_flux_client` · `azure_mai_client` · `chat_client` · `openai_chat` | ~100 | `map_error` çıktıları |
| `catalog.py` `note=` | 18 | model kartlarının bir satırlık açıklaması |
| `desktop.py` | ~19 | sunucu açılamadığında çıkan yerel uyarı pencereleri |

**Toplam ≈ 1060 dize.** `static/style.css` ve `static/mobile.css` içinde harf
taşıyan `content:` kuralı YOK — CSS bu işin dışında kalıyor.

Türkçe metne dayanan mevcut test iddiası: **131**. Varsayılan dil `tr`
kaldığı sürece bunların hiçbiri kırılmıyor (bkz. §1).

---

## 1. Varsayılan `tr` — bu bir karar, tembellik değil

> **SONRADAN ÇEVRİLDİ (v0.22).** Bu bölüm v0.21'in kararını ve gerekçesini
> olduğu gibi saklıyor; ürünün bugünkü varsayılanı `"en"` (`i18n.DEFAULT`).
> Aşağıdaki iki gerekçenin ikisi de o gün geçerliydi ve bugün ikisi de
> karşılandı: (1) tercihini kaydetmiş kullanıcı etkilenmiyor, kaydetmemiş
> kullanıcı Ayarlar'dan tek tıkla geri dönüyor; (2) Türkçe metne bakan test
> iddiaları körelmedi, İNGİLİZCE metne çevrildi — yani bekçiler hâlâ
> kullanıcının gerçekten gördüğü cümleyi ölçüyor. Belge silinmiyor çünkü
> kararın gerekçesi, kararın kendisinden uzun yaşıyor.

`prefs.json`'da `language` yoksa değer `"tr"`. İki sebep:

1. Mevcut kullanıcı bir güncellemeden sonra arayüzünü değişmiş bulmuyor.
   `Accept-Language`'e bakan bir otomatik algılama tam bunu yapardı.
2. Depodaki 131 test iddiası Türkçe metne bakıyor. Varsayılan `tr` kalınca
   o iddialar ÖLÇMEYE DEVAM EDİYOR; İngilizce yol ise kendi yeni iddialarıyla
   ölçülüyor. Varsayılanı çevirmek, çalışan 131 bekçiyi bir commit'te
   susturmak olurdu.

---

## 2. Katmanlar

### 2.1 Tercih — `language` anahtarı

`theme`'in birebir deseni; `prefs.py`'nin başındaki iki gerekçe (kimlik dosyası
yanlış yer · `localStorage` pywebview'ın private mode'unda siliniyor) burada da
kelimesi kelimesine geçerli.

* `models.py` — `ALLOWED_LANGUAGES = ("tr", "en")`, `ALLOWED_THEMES`'in yanında.
* `models.PrefsRequest.language: str | None` + `_language_ok` doğrulayıcı.
* `prefs._SCHEMA["language"] = ("tr", str)` ve `prefs._ENUMS["language"]`.
  `_ENUMS`'a girmesi ŞART: `theme: "neon"` için yazılan gerekçenin aynısı —
  elle yazılmış bir `language: "de"` katalogsuz bir arayüz üretirdi.
* Bekçi: `tests/test_prefs.py`, `tests/test_prefs_route.py`.

### 2.2 Sözlük — yeni `i18n.py` modülü + `bundled/i18n/*.json`

**Neden `.py` içinde sözlük DEĞİL:** `chat_prompt.py`'nin personayı ayrı
dosyada tutma gerekçesinin aynısı — bin dizelik bir sözlüğü kaynağa gömmek
modülü okunamaz yapar ve paketlenmiş `.app` içinde düzeltilemez hale getirir.

**Neden `static/` DEĞİL `bundled/`:** katalogları SUNUCU da okuyor (HTML'i
çevirmek ve hata mesajlarını üretmek için). `bundled/prompts/` zaten tam olarak
"sunucunun okuduğu, paketle gelen veri" için var. Paketleme bedavaya geliyor:
`kromis.spec` `datas=[('bundled','bundled')]` ve `android/app/build.gradle`
`into("resources/bundled")` dizinin TAMAMINI alıyor — yeni dosya için ikisinde
de değişiklik gerekmiyor (`tests/test_paket_icerik_listesi.py` bunun bekçisi).

`paths.bundled_i18n_dir()` — `bundled_prompts_dir()`'in ikizi.

`i18n.py` (yalnız `paths`'e bakar, `ValueError` yükseltir — `chat_prompt`'un
tek yönlü bağımlılık duruşunun aynısı):

```python
LANGUAGES = ("tr", "en")     # models.ALLOWED_LANGUAGES bunu AYNALIYOR
FALLBACK  = "tr"

def catalog(lang: str) -> dict[str, str]      # mtime anahtarlı önbellek
def t(key: str, lang: str, **vars) -> str     # eksik anahtar → tr → key
def render(template: str, lang: str) -> str   # {{t:key}} yer tutucularını çevirir
```

Önbellek **mtime anahtarlı**, süreç ömrü boyunca donmuş DEĞİL: `run.sh` ile
geliştirirken "dosyayı düzenle → yenile → gör" akışı index.html şablonunda
korunuyor (bkz. `app.index`'in docstring'i), sözlükte de korunmalı.

Eksik anahtarda düşüş sırası `tr` → anahtarın kendisi. Anahtarın EKRANA
çıkması bilerek gürültülü; kullanıcıya ulaşmasını ise §5'teki test kapatıyor.

### 2.3 HTML — sunucu tarafında çeviri

`app.index()` bugün zaten bir şablon motoru: `__APP_VERSION__` yer tutucusunu
değiştiriyor. Dil de AYNI mekanizmaya biniyor.

* `static/index.html`'de her görünen metin `{{t:anahtar}}` olur.
* `<html lang="tr">` → `<html lang="__APP_LANG__">`.
* `index()` üç geçiş yapar: sürüm · dil · `i18n.render`.
* Aynı yanıta `window.KROMIS_LANG` ve `window.KROMIS_I18N` (etkin dilin
  sözlüğü) satır içi gömülür.

**Neden istemci tarafında `data-i18n` taraması DEĞİL:** betikler DOM'dan sonra
koşar, yani ilk boyamada Türkçe görünüp sonra İngilizce'ye atlama riski var.
Sunucu tarafı çeviri o yanıp sönmeyi TANIMI GEREĞİ imkânsız kılıyor; üstelik
`lang` özniteliği de doğru değeri taşıdığı için ekran okuyucu metni doğru
seslendiriyor.

**Neden sözlük satır içi gömülü, ayrı bir dosyadan `fetch` DEĞİL:** ayrı dosya
ikinci bir ağ turu demek ve o tur dönene kadar çalışma anında üretilen dizeler
(`t(...)` çağrıları) dilsiz kalırdı. Belge zaten `no-store` (WKWebView
gerekçesi, `app.index`), yani gömülü sözlük hiç bayatlamıyor. Ölçü: ~25 KB,
loopback'te bedelsiz.

### 2.4 Betikler — yeni `static/i18n.js`

* Yükleme sırasında **EN BAŞA**, `pixel-canvas.js`'ten önce girer: geri kalan
  her betik `t()`'yi çağıracak.
* `window.KROMIS_I18N`'i okur; `t(key, vars)` tek üst düzey tanım.
* `core · chat · folders · settings · assets · palette · viewer` içindeki
  ~450 dize `t("…")` çağrısına dönüşür.
* `docs/graflar/onyuz.md` yükleme sırası değiştiği için yeniden üretilir.

### 2.5 Sunucu mesajları

* `app.py`: `_lang()` yardımcısı (`prefs.read(OUTPUT_DIR)["language"]`),
  `HTTPException(detail=i18n.t("err.…", _lang()))`.
* Sekiz istemci modülünün `map_error`'ı: **dili İSTEĞİN BAĞLAMINDAN okuyor**
  (`i18n.active()`, `contextvars.ContextVar`), parametre almıyor.

  > **PLANDAN SAPMA (uygulama sırasında).** Burada önce "isteğe bağlı `lang`
  > parametresi" yazıyordu. Uygulamada görüldü ki parametre `map_error`da
  > bitmiyor: onu çağıran istemci fonksiyonu da, onu çağıran adaptör de,
  > `providers` de, rota da almak zorunda — BEŞ kademelik bir imza
  > genişletmesi, ve o zincire eklenen her yeni fonksiyon parametreyi
  > unutmaya açık kalırdı. Üstelik metni üreten tek yer `map_error` değil:
  > `catalog`ın model notları ve `desktop.py`nin uyarıları da aynı sorunu
  > yaşıyor.
  >
  > `ContextVar` küresel bir değişken DEĞİL — değeri isteğin bağlamına bağlı
  > ve eşzamanlı iki istek birbirinin dilini göremiyor (`asyncio` görevleri
  > ile `run_in_threadpool`un iş parçacıkları bağlamı kopyalayarak taşıyor).
  > Tek yazar `app`in ara katmanı. Sızıntı olmadığı `test_i18n.py`de
  > ölçülüyor.
  >
  > Kararın korunan yanı aynı: `map_error` imzası ÇAĞIRANLAR için değişmedi,
  > yani mevcut ~100 test iddiası olduğu gibi ayakta kaldı.
* `catalog.py` `note=` alanı artık bir ÇEVİRİ ANAHTARI taşır
  (`model.<id>.note`); çözümleme `app._model_payload`'da, etkin dille yapılır.
  Katalog böylece dilsiz kalıyor — 13 modül onu ithal ediyor ve hiçbirinin
  dille işi yok.
* `desktop.py`: sunucu hiç açılmadan gösterilen uyarılar. `paths` elde olduğu
  için `prefs.read(paths.output_dir())` çalışıyor; okunamazsa `tr`.

### 2.6 Ayarlar'daki seçici

`#settings-nav`'a beşinci bölme: `data-pane="language"`.

Etiket **her iki dilde de "Dil / Language"** — bilerek çevrilmiyor. Yanlış
dilde kalmış bir kullanıcının geri dönüş yolu bu düğme; çevrilirse aradığı
kelimeyi göremez.

Seçici bir **native `<select>`** (`#language-select`). Plan önce tema
seçicinin `radio-row` kalıbını öngörüyordu; iki dilde ikisi de çalışıyor ama
radyo yığını üçüncü dilde Ayarlar bölmesini doldurmaya başlıyor ve asıl bedel
görünüşte değil: her satır şablona elle yazılırdı, yani yeni bir dil İKİ
dosyaya dokunmak olurdu. `<option>` listesi `i18n.language_options_html` ile
`LANGUAGES`tan üretilip `__APP_LANG_OPTIONS__` yer tutucusuna basılıyor —
üçüncü dilin bedeli **bir katalog dosyası + bir jeton**, şablon sabit kalıyor
(`test_adding_a_language_costs_no_template_edit`).

Dilin ADI çevrilmiyor: her katalog kendi adını `language.native_name` ile
söylüyor, yani liste hangi dilde çizilirse çizilsin aynı sözcükleri gösteriyor
— arayüzü yanlışlıkla tanımadığı bir dile çevirmiş kullanıcının geri dönüş
yolu bu.

Değişimde `POST /api/prefs {language}` → başarılıysa `location.reload()`.
Composer'da ya da sohbet kutusunda yazılmış metin varsa ÖNCE onay istenir
(`#confirm-modal` zaten var) — yenileme kullanıcının yazdığını silmemeli.

---

## 3. Yönetmen personası ve README

README'nin "Türkçe anlat" cümlesi bir belge hatası DEĞİL, personanın 1.
kuralının doğru bir özeti. Yani düzeltme önce personada:

* `bundled/prompts/prompt-yonetmeni.md` 1. kural → *"Kullanıcı hangi dilde
  yazıyorsa o dilde konuş; prompt'u HER ZAMAN İngilizce yaz."* Sohbet modeli
  hangi dili destekliyorsa o dil geçerli; İngilizce prompt kuralı ise
  değişmiyor, çünkü o bir dil tercihi değil görsel modellerinin ölçülmüş
  davranışı.
* Personadaki diğer dil kilidi satırları (soru metni, kısa özet, `variations`
  `istek` alanı, `aciklama` sınırı) "kullanıcının dilinde" olur. Türkçe
  karakter tavsiyesi (103. satır) KALIYOR ama "Türkçe" yerine "diyakritikli
  alfabeler" çerçevesine geçiyor — bilgi doğru, kapsamı dardı.
* `prompt-yonetmeni-video.md` aynı taramadan geçer.
* `chat_prompt.build_system` bağlam bloğuna etkin arayüz dilini ekler; rota
  onu `prefs`'ten okur (`_director_context` zaten `prefs` görüyor).
* `README.md`: 8., 45., 47. satırlar. `README.en.md`: 20–24 arası NOT bloğu
  (artık yanlış — dil anahtarı var) ve 57. satır.
* `tests/test_chat_prompt.py`'nin persona metnine bakan 18 iddiası güncellenir.

---

## 4. Commit sırası — UYGULANDI

Her commit kendi başına yeşil; graflar `tools/graf_uret.py` ile aynı commit'in
İÇİNDE yenilendi (CLAUDE.md §2).

1. ✅ `language` tercihi + `i18n.py` + kataloglar + bekçi testleri
2. ✅ `index.html` yer tutucuları + `index()` çevirisi + `static/i18n.js`
3. ✅ `static/*.js` dizeleri
4. ✅ Ayarlar'daki dil seçici
5. ✅ Sunucu mesajları (`app.py`, sekiz `map_error`, `catalog` notları, `desktop.py`)
6. ✅ Persona + README düzeltmesi

Katalog **743 anahtar** ile kapandı (plan ~1060 dize tahmin ediyordu; fark
tekrarların tek anahtarda toplanmasından — ör. `Hata (…)` 22 yerde yazılıydı,
`Kapat` on yerde).

Uygulama sırasında ortaya çıkan ve plana girmemiş üç kusur düzeltildi; üçü de
çeviri OLMASA sessiz kalmaya devam edecekti:

* `assets.js` düğme etiketinden ilk kelimeyi kesip tür adı olarak kullanıyordu
  (`"Logo yükle".split(" ")[0]`) — Türkçe'de kazara doğru, İngilizce'de
  "Upload".
* `folders.js` sıralaması `localeCompare(…, "tr")` ile Türkçe harf sırasını
  sabit dayatıyordu.
* `settings.js`te `startsWith("Başlamak için")` diye ölü bir nöbetçi vardı;
  çeviriyle birlikte "ölü ama masum"dan "dile bağlı ve sessizce yanlış"a
  dönüyordu.

Ayrıca iki BAYAT yer düzeltildi: Görünüm panelindeki "tema seçimi yeniden
başlatınca sıfırlanır" notu (Adım 9'dan beri yanlış) ve onu ARAYAN test.

**7. commit (CI kırmızısı).** Yukarıdaki altı commit'ten sonra CI iki kusur
gösterdi; ikisi de tarayıcı testleriydi ve bu kapsayıcıda Chromium
açılamadığı için yerelde ÖLÇÜLEMEMİŞTİ (13 Playwright testi burada launch
hatasıyla düşüyor — depoyla ilgisi yok):

* `syncPromptPlaceholder` anahtar tablosunun değerini `t()`den geçirmeden
  `placeholder`a yazıyordu; kullanıcı composer'da
  `composer.placeholder_director` okuyordu. Kaynak taramasının göremeyeceği
  bir kusur: satırda tablonun adı bile geçmiyor, yerel bir takma ad var.
  Bekçisi artık `tests/test_playwright_dil.py` — DOM'un tamamını tarayıp
  ekranda duran her metni katalog anahtarlarıyla karşılaştırıyor, iki dilde.
* `model.director_title` çeviri sırasında "Yönetmen modeli"nden "Prompt
  Yönetmeni modeli"ne kaymıştı. Çeviri metni DEĞİŞTİRMEZ; eski değer geri
  alındı ve testin haklı olduğu kabul edildi.

**8. commit (kaçan sunucu metni).** CI kusurlarını ararken İngilizce arayüz
Chromium'da baştan sona TARANDI (DOM'daki her metin düğümü ve öznitelik) ve
ilk turun "sunucu mesajları da çevrilsin" kararının YARIM kaldığı görüldü:
`app.py`nin `HTTPException`ları ve sekiz `map_error` çevrilmişti, ama aynı
kullanıcıya konuşan şu yerler çevrilmemişti —

| yer | İngilizce arayüzde görünen |
| --- | --- |
| `catalog.QUALITY_LABELS` | "1:1 · ORTA · x1" |
| `catalog.duration_label` | "16:9 · 4 SN" |
| `core.js` kredi metinleri | "≈ 8 kredi", "16 kredi/sn" |
| `core.js` "kurulum gerekli" | model kartının rozeti |
| dört `catalog` etiketi | "Azure OpenAI · görsel", "Azure AI Foundry dağıtımı" |
| `models.py` doğrulayıcıları | "geçersiz theme", "{model} bu boyutu desteklemiyor: …" |
| `credstore.py` kurulum uyarıları | "… anahtarı yok: Ayarlar'dan kaydet" |
| `providers.py` / `chat_providers.py` | "… için sağlayıcı adaptörü yok" |
| `prefs.py` / `folders.py` / `palette.py` / `composite.py` | 422 gövdesindeki metinler |

Kusur SESSİZDİ çünkü Türkçe arayüzde hepsi doğru görünüyor. Bekçisi iki
testte birden: `test_no_user_facing_module_still_carries_turkish_text`
(kullanıcıya konuşan modüllerde Türkçe dize sabiti aramak, gerekçeli
muafiyet listesiyle) ve tarayıcıdaki DOM taraması.

**`etiket.py` (yeni modül).** Etiket çözümü `catalog.py`ye konamadı:
`tests/test_catalog.py` kataloğun PROJE İÇİNDEN hiçbir şey import etmemesini
şart koşuyor (yaprak kalmalı; `i18n` de `paths`i çeker). Ayrım şu oldu —
`catalog` neyin VAR OLDUĞUNU söylüyor (jetonlar, yetenekler, etiket
anahtarları), `etiket` onu kullanıcının OKUYACAĞI metne çeviriyor
(`label_of`, `quality_label`, `duration_label`, `short_labels`).

---

## 5. Bekçiler — yeni `tests/test_i18n.py`

Depodaki "türetilen her şeyin bekçisi bir testtir" kuralının bu iş için
karşılığı:

1. **İki katalog aynı anahtar kümesine sahip.** Ayrışma = bir dilde eksik
   metin, ve eksik metin sessizce Türkçe'ye düşerdi.
2. **`index.html`'deki her `{{t:…}}` her iki katalogda var.**
3. **`static/*.js`'teki her `t("…")` çağrısının anahtarı her iki katalogda
   var.** (Sabit dizeli çağrılar taranıyor; değişkenli çağrı varsa test onu
   ADIYLA muaf listesine alır — sessizce atlamaz.)
4. **Serviste çevrilmemiş yer tutucu kalmıyor** — `test_index_has_no_unsubstituted_placeholder`'ın ikizi, `{{t:` için.
5. **`ALLOWED_LANGUAGES` ile `bundled/i18n/` altındaki dosyalar örtüşüyor.**
6. **Kataloğu okuyan çağrı `encoding` veriyor.** `.gitattributes`'ın genel
   `* text=auto eol=lf` kuralı `.json`'u zaten kapsıyor (ayrı satır gerekmiyor);
   `tests/test_encoding_contract.py` AST taraması `i18n.py`'yi kendiliğinden
   görüyor.

Ayrıca: `test_index.py` · `test_mobile.py` · `test_arena_onyuz.py` ·
`test_video_onyuz.py` · `test_playwright_studio.py` içindeki metne dayalı
iddialar, metin artık şablonda olmadığı için anahtara ya da çevrilmiş çıktıya
bakacak şekilde güncellenir.

---

## 6. Kapsam DIŞI

* Belgelerin çevirisi (`KURULUM.md`, `docs/ozellikler.md`, `GUNCELLEME.md`).
  `README.en.md` yalnız YANLIŞ olan cümleleri için düzeltiliyor, yeniden
  yazılmıyor.
* Ekran görüntüleri — `docs/gorseller/` altındakiler Türkçe arayüzü gösteriyor
  ve öyle kalıyor; `README.en.md`'nin bunu söyleyen notu güncellenir.
* Üçüncü bir dil. Mekanik buna hazır (yeni bir `bundled/i18n/xx.json` +
  `ALLOWED_LANGUAGES`'a bir jeton) ama bu turda eklenmiyor.
* `color_names.py`'nin ürettiği renk adları: onlar prompt'a giriyor, arayüze
  değil — İngilizce olmaları bir çeviri eksiği değil, modülün var olma sebebi.
