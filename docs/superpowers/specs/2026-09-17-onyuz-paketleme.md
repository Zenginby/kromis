# Kromis Studio — ön yüz paketleme (bundler) kararı

**Tarih:** 2026-09-17
**Durum:** karar verildi — Faz 0'da yalnız lint/biçim; ES modül + paketleyici
sorusu Faz 1'in çerçeve kararıyla birlikte
**Bağlam:** docs/faz0-web-first.md → 7; docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md

## Ölçülen durum

* `static/` altında 10 betik, 10.867 satır (`wc -l static/*.js`, biçimlendirme
  öncesi): `core.js` 2961, `chat.js` 2665, `folders.js` 2063, `settings.js` 856,
  `palette.js` 769, `assets.js` 561, `viewer.js` 507, `pixel-canvas.js` 347
  (üçüncü parti, MIT), `i18n.js` 83, `mobile.js` 55.
* `static/index.html:1967-1988` **11 `<script>` etiketi**: bir satır içi
  (`window.KROMIS_LANG` / `window.KROMIS_I18N`, sunucu şablonundan) + 10 dosya,
  hepsi `?v=__APP_VERSION__` ile. Modül sistemi yok (`type="module"` yok,
  `import`/`export` yok); betikler yükleme SIRASIYLA tek küresel kapsama
  giriyor (docs/graflar/onyuz.md — 28 betik-arası bağ).
* Dosyalar arası bağ hacmi, eslint ile ölçüldü: yalnız tarayıcı
  küreselleriyle **1035 `no-undef` / 92 ayrı ad** — 59'u `core.js`in, 11'i
  `chat.js`in tanımı. 10 ad başka dosyadan ATANIYOR (`currentModel`,
  `imageModels`, `runBusy`, `sheetTetik`, `extras`, `seciliModelTercihi`…).
  Yani bu bir "birkaç yardımcı paylaşılıyor" durumu değil; durum da işlev de
  dosya sınırından geçiyor.
* Bir "iyimser kanca": `settings.js:127` `typeof syncSendButton === "function"`
  ile yoklayıp çağırıyor; hiçbir betik tanımlamıyor.

## Karşı ölçü: bugünkü testlerin kaynak METNİNE bağlılığı

Ön yüzün güvenlik ağı JS'i ÇALIŞTIRMIYOR, servis edilen metni OKUYOR:

* `tests/test_index.py` — 286'dan fazla test, çoğu `TestClient` ile
  `/static/*.js` metnini alıp regex/dizeyle iddia yazıyor
  (`function renderGallery()` gövdesi, `$("go").disabled` tek yerden,
  `document.addEventListener("keydown"` sayısı, `card.setAttribute("aria-label"`…).
  Prettier'ın satır kaydırması bile 7'sini kırdı (bu PR'da biçimden bağımsız
  hâle getirildi).
* `tests/test_id_contract.py` — 14 test; `_TOP_LEVEL_DECLARATION_RE` ile üst
  düzey adları tarıyor: hiçbir ad iki dosyada tanımlı değil, `$("id")` bağları
  HTML'de duruyor, kaldırılan id'nin JS bağı da gitmiş.
* Artık `tests/test_onyuz_lint_kapisi.py` — paylaşılan ad defteri ile
  `docs/graflar/graf.json`un betik-arası kenarları birbirini denetliyor.
* `tools/graf_uret.py` — betik-arası kenarları "üst düzey tanım + başka dosyada
  `ad(`" deseninden çıkarıyor; `docs/graflar/onyuz.md` bunun ürünü.

ES modüle geçiş bunların tamamını bir kerede etkiler: her `function foo()`
modül-yerel olur, dosyalar arası bağ `import { foo } from "./core.js"` satırına
taşınır, "üst düzey ad" kavramı değişir, `$()` bağları hâlâ üst düzeyde kalır
ama regex'in bulduğu yer değişir.

## Değerlendirilen seçenekler

| seçenek | ne değişir | bedel | ne zaman |
| --- | --- | --- | --- |
| **(1) Vanilla kalır, paketleyici yok — yalnız lint/biçim** | `package.json` (devDependencies), `eslint.config.js`, `.prettierrc`, `ci.yml`'de `lint-onyuz` | Düşük: `static/*.js` yalnız otomatik biçim + 2 elle düzeltme; 7 regex biçimden bağımsız | **Faz 0 — bu PR** |
| (2) ES modül + esbuild/Vite, çerçevesiz | Her betik `export`, `index.html` tek `<script type="module">`, `routers/kok.py` derlenmiş çıktıyı servis eder, `?v=` yerine içerik hash'i | Yüksek: 286 + 14 test metin çapası, `graf_uret` betik tarayıcısı, `test_telif_basligi` kapsamı, `id-baseline.txt`; Faz 1'de çerçeve gelirse iş İKİ kez yapılır | Faz 1'de, çerçeve kararıyla BİRLİKTE |
| (3) Çerçeve (React/Svelte/Solid) + Vite | (2)'nin tamamı + bileşen modeli, durum yönetimi, i18n'in `t()`'sinin çerçeve yolu | En yüksek; SaaS ön yüzünün (hesap, ödeme, çoklu kiracı) gereksinimi zaten bunu soracak | Faz 1 |

(2)'yi tek başına yapmanın gerekçesi zayıf: modül sınırı ancak ÜZERİNE bir
şey (ağaç sallama, çerçeve, tip denetimi) konacaksa bedelini ödüyor. Faz 1'de
çerçeve seçilirse (2) o geçişin içinde kendiliğinden gelir; seçilmezse (2)
yine o noktada, testlerin nasıl taşınacağı bilinerek yapılır.

## Karar

1. **Faz 0: (1).** eslint (`no-undef`, `no-unused-vars` `vars: "local"`,
   `eqeqeq`, + `recommended`) ve prettier `--check` CI'da kesici. Dosyalar
   arası adlar `eslint.paylasilan-adlar.json`da; bekçisi
   `tests/test_onyuz_lint_kapisi.py`. `no-redeclare`, defter sayesinde iki
   dosyanın aynı adı tanımlamasını lint düzeyinde yakalıyor.
2. **ES modül / paketleyici sorusu Faz 1'in çerçeve kararıyla birlikte**
   karara bağlanır; ayrı bir tasarım belgesi o zaman yazılır.
3. Bu belge o güne kadar "neyi neden yapmadık"ın kaydı.

## Faz 1'de değişmek zorunda olanlar (envanter)

Geçiş yapıldığında aynı PR'da ele alınmalı — hepsi kaynak metnine bağlı:

* `tests/test_index.py`: `/static/*.js` metnine yazılan iddiaların çoğu ya
  derlenmiş çıktıya (anlamsız — minify) ya KAYNAK dosyaya (yolu değişir)
  bakmalı; "tek yerden yazılıyor" sınıfı iddialar (`$("go").disabled`)
  modül sınırı gelince zaten yapısal olarak sağlanır ve silinebilir.
* `tests/test_id_contract.py`: `_TOP_LEVEL_DECLARATION_RE` → `export`lu
  tanımlar; "iki dosyada aynı ad" iddiası modülde ANLAMSIZLAŞIR (yerel),
  yerine "iki modül aynı adı export ediyor" ya hiç gerekmez.
* `tests/test_onyuz_lint_kapisi.py` + `eslint.paylasilan-adlar.json`: defter
  tümüyle KALKAR — `import` satırı sözleşmenin kendisidir, eslint
  `sourceType: "module"` ile `no-undef`ü kendi başına doğru koşar.
* `tools/graf_uret.py` `onyuz()`: betik-arası kenarlar `import … from`
  satırlarından okunur (bugünkü "ad(" deseninden daha kesin — yorumda geçen
  adın kenar ürettiği bilinen fazla sayım da biter).
* `tests/test_telif_basligi.py`: kapsam kaynak dosyalarda kalır; derlenmiş
  çıktı için lisans başlığı `banner` ile eklenir ve ayrı sınanır.
* `routers/kok.py` + `static/index.html`: `?v=__APP_VERSION__` yerine
  içerik hash'li dosya adı; `tests/test_static_cache.py` benzeri iddialar.
* `docs/flow-ui/id-baseline.txt` DEĞİŞMEZ (HTML id'leri), `id-defteri.md`
  değişmez; yalnız JS bağı tarayan iddialar yeni yolu öğrenir.
* `.prettierignore`'daki `static/*.css` ve `static/*.html` muafiyeti o gün
  yeniden sorulur (bugün `test_index.py`nin CSS/HTML metin iddiaları yüzünden).
