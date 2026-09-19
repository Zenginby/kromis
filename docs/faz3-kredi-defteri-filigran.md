# Faz 3 — Kredi defteri, tarife–maliyet mutabakatı, planlar ve filigran: görev listesi

**Tarih:** 2026-09-19 · **Karar:** bekliyor — K1–K11 aşağıda sahibin onayına sunuldu (öneri; kabul edilince bu satır tarih ve kaynakla güncellenir) · **Önceki faz:** [faz2-kuyruk-anahtarlar-depolama.md](faz2-kuyruk-anahtarlar-depolama.md) (10/10 ✅, kapanış 2026-09-19, PR #37–#52)
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) §5 **"Faz 5"** bölümü (`:170-221`) — sapmalar bu belgenin sonunda tek tek yazılı. **Numaralama tuzağı:** master spec'in "Faz 5"i ürün yol haritasının SaaS kartı; bu belge SaaS dönüşümünün İÇ dizisindeki Faz 3'tür (Faz 0 web-first → Faz 1 DB/hesap → Faz 2 kuyruk → **Faz 3 kredi defteri** → Faz 4 ödeme/KVKK → Faz 5 işletme; [studyo-guncelleme-plani.md](studyo-guncelleme-plani.md):4). Kartın ilgili satırları: "Filigran & Kredi Kuralları: ücretsiz deneme katmanı (filigranlı), ücretli katmanlar (filigransız + ticari haklar), devredilmeyen aylık kredi (no-rollover)" (`:183`); "Tek gerçek kaynak atomik kredi ledger'ı… Webhook'ta idempotency zorunlu… Kredi tarifesi… kendi katalogumuzda durur" (`:205-208`); "Bugün YALNIZ metadata: bakiye düşülmüyor, üretim engellenmiyor" (`:215-219`). **Çıkış kriteri (bu belgenin sonunda tam metin):** ücretsiz kullanıcı platform anahtarıyla iş verir → bakiyesi düşer → iş biter → gerçek maliyetle onaylanır, fark iade; hata/iptal tam iade; ücretsiz görselde filigran; SUM(defter) == bakiye; admin marj tablosu dolu.

Faz 3'ün amacı, Faz 2'nin kurduğu kuyruk + platform anahtarı + günlük tavan
zemininin üstüne **parayı saymayı** koymak: bugün her iş satırına bir tahmin
(`isler.kredi_tahmini`, `routers/uretim.py:154`) ve her medya satırına bir
gerçek (`medya.credits`, `services/tablolar.py:379`) yazılıyor ama ikisi de
yalnız metadata — bakiye yok, düşüm yok, plan yok, filigran yok (master spec
`:215-219`; Faz 2 belgesi `:1030-1031`). Faz 3'te kullanıcının bir **bakiyesi**
olur; platform anahtarıyla giden iş sıraya girerken tahmini **rezerve eder**,
biterken gerçek maliyetle **onaylanır** ve fark iade edilir; hata/iptal/bayat
düşme tam iade; ücretsiz planın aylık hibesi işçinin bakım turunda yatar;
ücretsiz görsel işçide **filigranlanır**; ücretli planların modelleri
`model_available(plan)` kancasıyla (`services/modeller.py:26-40`) ayrılır; admin
sağlayıcının gerçek faturasıyla tarifemizi yan yana görür (**marj raporu**).
Ödeme YOK: bakiyeye para girişi yalnız aylık hibe ve admin düzeltmesi.

**BU FAZDA YOK** — gerekçeleri "Faz 3 dışı" bölümünde:

* **Ödeme, MoR/Polar, webhook, abonelik yaşam döngüsü, vergi, e-Arşiv, KVKK**
  → **Faz 4** (Faz 2 belgesi `:2469-2473`). Defter Faz 4'ün webhook'una
  hazır bırakılır: `idempotency_anahtari` sütunu sağlayıcının event id'sini
  taşıyacak (master `:205-208`), `tur` kümesine `paket`/`satin_alma` o gün eklenir.
* **Kötüye kullanım / IP limitleri, yedek tatbikatı, dağıtımda iş kaybı** →
  **Faz 5** (Faz 2 belgesi `:2474-2478`).
* **Video filigranı (ffmpeg)** → dışarıda. Sunucuda video işleme aracı yok,
  `Dockerfile`da `apt-get` katmanı yok, imaj 284 MB (`tests/test_video_onyuz.py:649-653`;
  `studyo-guncelleme-plani.md:303-304`); ücretsiz planda video modelleri
  KAPALI olduğu için (3. görev) filigransız video ücretsiz kullanıcıya hiç
  çıkmaz — ihtiyaç doğmuyor.
* **E2/E3 hızlı araçlar** (arka plan kaldırma, vesikalık, görselden prompt;
  `studyo-guncelleme-plani.md:273-294`) → defterden SONRA isteğe bağlı mini
  faz (K10).

Her madde bir PR (`faz3/<slug>` dalı), her PR tek başına yeşil ve geri
alınabilir; her PR'da testler + `docs/graflar` aynı commit'te, tam takım E2E
dahil yerelde koşulur (`KROMIS_E2E_ZORUNLU=1`). Sıra bağımlılığa göre:
**1 → 2 → 3 → 4** (omurga: tablo → rezerve/onayla → planlar → filigran), **5**
(2'den sonra: `kredi_gercek` raporun sütunu), **6** (3'ten sonra: plan ve hibe
alanları API'de), **7** en son. Çıkış kriterinin defter yarısı 2'de, plan/filigran
yarısı 4'te, marj yarısı 5'te karşılanır.

**NEDEN TEK GÖÇ (`0007_kredi`) — dört görevin sütunları 1. görevin göçünde.**
Faz 3'ün şema dokunuşları küçük ve birbirine bağlı: yeni tablo
`kredi_hareketleri`, `kullanicilar.bakiye`/`plan`, `isler.kredi_gercek`/
`saglayici_meta`/`saglayici_maliyet_usd`, `medya.filigranli`. Dört ayrı göç
(0007–0010) dört ayrı `alembic check` turu, dört `BAS` literali güncellemesi
(`tests/test_db.py`) ve sahibin canlıda dört kez `tools/goc.py` koşması demek;
hepsi NULL/öntanımlı sütun, geriye uyumlu, birlikte gitmesinin bedeli yok.
2, 4 ve 5. görevler şemayı hazır bulur; her birinin "Dokunulan"ı bunu söyler.

Ölçüler bu belge yazılırken alındı (`7a94ac0`, Faz 2'nin tamamı main'de):

* **Faz 2 tabanı:** takım **3.819 geçti, 12 atlandı** (main; E2E + Postgres
  zorunlu); **67 rota**, **104 modül** (`docs/graflar/README.md`); şema başı
  `0006_rls`, **13 tablo** (`tests/test_tablolar.py:143`), `IS_TABLOLARI` **8**
  (`services/kiraci.py:87-88`; bekçi `tests/test_rls.py:179` `len == 8` SABİT).
* **Tarife tek noktada:** `catalog.cost_for(m, quality, n=1, *, duration=0)`
  (`catalog.py:1426-1447`) — `credits_by_quality` kaliteye göre ezer, birim
  `kind`e bağlı (görsel başına / saniye başına, `:112-117`); çapa Azure `medium`
  = 8 kredi ≈ 0,04 USD → **1 kredi ≈ 0,005 USD** (`:467-472`). Dört birim fiyat
  "doğrulanamadı" notlu (`:678`, `:726`, `:750-751`, `:806`). `ImageModel.plan:
  str = "free"` alanı var, okunmuyor (`:195-202`).
* **Tahmin ve gerçek, ikisi de yalnız metadata:** `isler.kredi_tahmini int NOT
  NULL` rotada `cost_for × n` (`routers/uretim.py:154`, video `:199`, animate
  `:351`, edit `:513`); işçi `_kredi(is_)` medya BAŞINA `cost_for` yazar
  (`services/isci.py:392-399`) → `medya.credits` (`depo_medya.py:160`). İşçi
  tahmine bakmaz (`isci.py:31-32`). Yeniden gönderim tahmini eski satırdan
  kopyalar (`routers/isler.py:289`, `:306-310`).
* **Günlük tavan = rezervin bugünkü vekili:** `kota.check_gunluk` yalnız
  `anahtar_kaynagi == "platform"` için `SUM(kredi_tahmini)` (24 sa, `iptal`
  hariç) + tahmin > tavan → 429 (`services/kota.py:124-137`, `:152-183`);
  `_kapilar` zincirinin sonunda (`routers/uretim.py:109-122`). Admin metrikleri
  aynı toplamı okur (`services/depo_admin.py:114`, `:235-236`). `GET /api/kota`
  paneli besler (`routers/isler.py:131-147`; `static/isler.js:265-273`).
* **Sağlayıcı adaptörleri `list[bytes]` döner, usage/maliyet dönmez**
  (`providers.py:20`, `:34-35`; `azure_client.py:438,484`; `fal_client.py:730-739`;
  `veo_client.py:30-31`). Azure MAI 200 gövdesinde `usage.num_output_tokens`
  GÖRÜLDÜ ama okunmuyor (`azure_mai_client.py:39-42`); fal yalnız `request_id`
  doğrular (`fal_client.py:650-666`). `isler`de maliyet için sütun yok.
* **Filigran çekirdeği var, video işleme yok:** Pillow 12 (`requirements.txt`,
  `Dockerfile:19`); `composite.py` logo bindirme — 9 konum `POSITIONS`
  (`:35-39`), gölge, ölçek, golden testler `tests/test_composite.py`;
  `services/gorsel.to_png` (`:32`), `MAX_IMAGE_PIXELS` 50 MP (`:28-29`).
  ffmpeg/imageio/moviepy/cv2 hiçbir yerde yok.
* **Medya baytı işçide doğrudan yazılıyor:** `_uret` → `list[bytes]` → `_yaz` →
  `depo_medya.kaydet` "önce nesne, sonra satır" (`isci.py:349-369`, `:417-448`;
  `depo_medya.py:136-142`). Servis 302 → ön imzalı URL, uygulama bayt taşımaz
  (Faz 2 K7; `routers/galeri.py:302-318`) → araya girecek TEK yer işçi.
* **RLS:** 8 tabloda `sahip` ALL + `yonetici_okur` SELECT + `yonetici_gunceller`
  UPDATE (`alembic/versions/0006_rls.py:64-77`); **admin INSERT/DELETE YAPAMAZ**
  (`:15-17`; `services/kiraci.py:41`). İşçi işi kullanıcının bağlamında koşar
  (`isci.py:481`), `bakim_turu` ve `siradakini_al` `rol=ADMIN` (`:265`, `:577`, `:643`).
* **Ön yüz:** `#run-cost` satırı `static/core.js syncRunCost` (`:547`) model ×
  boyut/kalite × adet; "bakiye yok, düşüm yok" (`studyo-guncelleme-plani.md:122-136`,
  B1 → Faz 3). i18n `gen.cost_one/many` "≈ {n} kredi" (`bundled/i18n/tr.json:423-424`).
* **Belgeler:** `docs/isletme.md:173` "Kredi defteri yedeği — Faz 3 (tablo yok)";
  `tests/test_tablolar.py` yalnız faz1/faz2 belgelerini okur (`:48-49`,
  `:126-137`) — bu belge tek başına hiçbir testi kırmaz, 1. görev ona çapa ekler.

---

## Envanter: bugünkü kredi/plan parçaları → Faz 3 parçaları

Adlar ÖNERİ (Türkçe, ASCII: `kredi_hareketleri`, `services/defter.py`,
`services/planlar.py`); her satır hangi görevde değiştiğini söylüyor.

| bugün | nerede | Faz 3'te | görev |
| --- | --- | --- | --- |
| Tarife: `cost_for` tek hesaplama noktası, birim `kind`e bağlı | `catalog.py:1426-1447` | DEĞİŞMEZ; rezerv ve onay aynı işlevi çağırır; `tools/tarife_kontrol.py` doğrulanamayan dört fiyatı listeler | 5 |
| Tahmin `isler.kredi_tahmini`, rota yazar, tavan toplar | `routers/uretim.py:154`; `0004_isler.py:53` | **Rezerv miktarı**: sıraya girerken bakiyeden düşer (`defter.rezerve`), ledger satırı `rezerv` | 1, 2 |
| Gerçek `medya.credits`, işçi medya başına yazar | `services/isci.py:392-399`; `tablolar.py:379` | Toplamı `isler.kredi_gercek` (0007); `defter.onayla` farkı iade eder | 1, 2 |
| `anahtar_kaynagi` kullanici/platform | `0005_kota.py:39-43`; `tablolar.py:155` | BYOK iş rezerv ETMEZ (K3), yalnız saatlik tavan | 2 |
| Günlük kredi tavanı `check_gunluk` (429) | `services/kota.py:152-183` | KALIR — kötüye kullanım tavanı (K9); bakiye kapısı ondan ÖNCE, 402 | 2 |
| `model_available(configured, plan)` — `plan` okunmuyor | `services/modeller.py:26-40` | `plan` OKUNUR: `catalog.ImageModel.plan` + `kind=='video'` kapısı → 403 `err.plan_kapsamiyor` | 3 |
| Katalog `plan: str = "free"` alanı, metadata | `catalog.py:195-202` | Kararın VERİSİ; `services/planlar.py` kod kataloğu onunla eşleşir | 3 |
| `#run-cost` "≈ N kredi", bakiye yok | `static/core.js:547`; `tr.json:423-424` | "bu tur X düşer · kalan Y"; 402'de plan bağlantısı (stüdyo B1) | 6 |
| Admin metrikleri `SUM(kredi_tahmini)` | `services/depo_admin.py:114`, `:235-236` | + "Marj" tablosu: model başına Σ `kredi_gercek`, ≈USD, Σ sağlayıcı USD, ort. süre | 5 |
| `composite.py` filigran çekirdeği (logo/motto, 9 konum) | `composite.py:4`, `:35-39` | `services/filigran.py` işçide `_uret` → `_yaz` arasına; `medya.filigranli` | 4 |
| `GET /api/kota` günlük kalan, saatlik sayı | `routers/isler.py:131-147` | `GET /api/kredi` {bakiye, plan, hibe, sonraki_hibe, filigran, son_hareketler}; `/api/kota` kalır | 6 |
| Bakiye/hibe/plan sütunu YOK; admin kredi ekleyemez | Faz 2 belgesi `:1548-1549` | `kullanicilar.bakiye`/`plan`, `kredi_hareketleri`; admin `duzeltme` satırı + `yonetici_ekler` politikası (K4) | 1, 3 |
| `isletme.md` "kredi defteri yedeği — Faz 3 (tablo yok)" | `docs/isletme.md:173` | Tablo günlük `pg_dump`un içinde → satır "Faz 3'te kapandı" | 7 |

---

## 1. Kredi defteri — `kredi_hareketleri`, `kullanicilar.bakiye`/`plan`, `services/defter.py` (PR: `faz3/kredi-defteri`)

**Kapsam.** Davranış DEĞİŞMEZ; yalnız şema + defter katmanı + bekçileri
(Faz 2 / 1'in deseni). Göç **`0007_kredi`** — Faz 3'ün TEK göçü (giriş):

* **`kredi_hareketleri`** — `id uuid` (`gen_random_uuid`), `kullanici_id` FK
  `kullanicilar` CASCADE (hesap silinirse defteri de gider — KVKK Faz 4'te
  bunu yeniden değerlendirir), `is_id uuid NULL` FK `isler` **SET NULL**
  (saklama süresi dolan iş silinir — `kuyruk.eskileri_sil`, Faz 2 / 10 —
  defter satırı KALIR; para izi işten uzun yaşar), `tur text CHECK IN
  ('hibe','rezerv','onay','iade','duzeltme','sona_erme')` — `paket`/`satin_alma`
  Faz 4'te göçle eklenir (Faz 1 / 2'nin `text + CHECK` kararı aynen),
  `miktar int NOT NULL` (İMZALI: `rezerv` negatif, `onay`/`iade`/`hibe`
  pozitif, `duzeltme` her iki yön, `sona_erme` negatif), `aciklama text
  NULL`, `admin_id uuid NULL` (FK `kullanicilar` SET NULL; yalnız `duzeltme`),
  `idempotency_anahtari text NOT NULL UNIQUE`, `olusturuldu timestamptz NOT
  NULL`. İndeks `(kullanici_id, olusturuldu)` (hareket listesi, `medya`nın
  deseni) ve `(is_id)` (onay/iade "bu işin rezervi var mı" sorusu).
* **`kullanicilar.bakiye int NOT NULL DEFAULT 0`** — ÖNBELLEK; kaynak gerçek
  `SUM(kredi_hareketleri.miktar)`. **`kullanicilar.plan text NOT NULL
  DEFAULT 'free' CHECK IN ('free','temel','pro')`** — küme `services/planlar.py`
  kataloğundan (3. görev bu göçü hazır bulur; CHECK literali ile kod listesi
  bekçili, `0006_rls.TABLOLAR` deseni).
* Aynı göçte, ileriki görevler için: `isler.kredi_gercek int NULL` (2),
  `isler.saglayici_meta jsonb NULL` ve `isler.saglayici_maliyet_usd
  numeric(10,6) NULL` (5), `medya.filigranli bool NOT NULL DEFAULT false` (4).
  Hepsi NULL/öntanımlı, geriye uyumlu; `downgrade` hepsini düşürür.
* **RLS:** `kredi_hareketleri` `kullanici_id` taşır → `IS_TABLOLARI`ya girer,
  `0006_rls`nin üç politikası (`sahip` ALL, `yonetici_okur`, `yonetici_gunceller`)
  aynen, `FORCE`. ARTI, yalnız bu tabloda: **`yonetici_ekler` INSERT** `WITH
  CHECK (current_setting('app.rol', true) = 'admin')` (K4). Sebebi iki yazar:
  admin düzeltmesi (3. görev rotası) ve İŞÇİNİN BAKIM TURU (`rol=ADMIN`,
  `isci.py:643`) — aylık hibe (3) ve bayat işin iadesi (2) o bağlamda yazar.
  DELETE yine kimseye yok: defter append-only.

Yeni **`services/defter.py`** — konuşmaz, `(db, ...)` imzalı; para hareketinin
TEK yazarı (rotalar ve işçi `kredi_hareketleri`ye doğrudan `db.add` YAPMAZ;
AST bekçisi `test_galeri_db`nin deseniyle):

* `bakiye(db, kullanici_id) -> int` — önbellekten (`kullanicilar.bakiye`).
* `hibe(db, kullanici_id, miktar, anahtar, aciklama=None) -> bool` — `INSERT …
  ON CONFLICT (idempotency_anahtari) DO NOTHING` + etkilenen satır 1 ise
  `UPDATE kullanicilar SET bakiye = bakiye + :m`; `False` = zaten vardı.
* `rezerve(db, kullanici_id, is_id, miktar)` — **atomik**: `UPDATE kullanicilar
  SET bakiye = bakiye - :m WHERE id = :u AND bakiye >= :m`; etkilenen satır 0
  → `YetersizBakiye(bakiye, gereken)` yükseltir, satır YAZILMAZ; 1 → aynı
  transaksiyonda `rezerv` satırı, `miktar = -m`, anahtar `rezerv:<is_id>`.
  Rota çağırır (kullanıcının bağlamı, `sahip`). Kilit yok, `SELECT … FOR
  UPDATE` yok: koşul UPDATE'in içinde, iki eş zamanlı rezerv aynı bakiyeye
  yarışırsa Postgres satır kilidiyle sıralar, ikincisi güncel değeri görür (K1).
* `onayla(db, is_id, gercek)` — işin `rezerv` satırını bulur (`is_id` + `tur`),
  `fark = -rezerv.miktar - gercek`; `fark > 0` ise `onay` satırı `+fark`,
  anahtar `onay:<is_id>`, bakiye `+fark`; `fark == 0` ise yalnız `onay` satırı
  `0` (iz: "onaylandı"); `fark < 0` (gerçek tahmini AŞTI — tahmin üst sınır,
  olmamalı) ise EK TAHSİLAT YOK, `onay` 0 + `WARNING olay=defter.asim`
  (mutabakat raporu 5'te yakalar). Rezerv satırı yoksa (BYOK iş, göç öncesi
  iş) no-op. İşçi çağırır (`kuyruk.bitir`le aynı commit, 2).
* `iade(db, is_id)` — rezervin TAMAMI, anahtar `iade:<is_id>`; onay ya da
  iade zaten varsa no-op (idempotent — `dusur` ve bayat düşürme aynı işi
  ikinci kez düşürebilir, K8'in "yeniden kuyruğa almaz" dünyasında bile).
* `duzelt(db, hedef_id, miktar, aciklama, admin_id, anahtar=None) -> Hareket` —
  admin bağlamında (`yonetici_ekler`), `hedef_id` `depo_admin`in adlandırması
  (`kullanici_id` alan işlev süzmek zorunda, `test_galeri_db` bekçisi);
  `anahtar` verilmezse `duzeltme:<uuid4>`. Negatif miktar bakiyeyi eksiye
  düşürebilir — bilerek: admin düzeltmesi, kapı yok, iz var.
* `hareketler(db, kullanici_id, *, limit=20) -> list[Hareket]` ve `_json`
  dökümü (`id, tur, miktar, aciklama, is_id, olusturuldu` — `admin_id` ve
  `idempotency_anahtari` DÖKÜLMEZ: iç iş).
* `tutarlilik(db) -> list[(kullanici_id, bakiye, toplam)]` — `SUM(miktar)
  GROUP BY kullanici_id` ile `kullanicilar.bakiye`yi karşılaştırır; farklı
  olanları döner. Bakım turu (7. görev) çağırır, fark varsa `WARNING
  olay=defter.tutarsiz` (düzeltmez — ölçer; düzeltme admin `duzelt`).

**Defter biçimi — append-only tek tablo + önbellek, çift kayıt DEĞİL (K1).**
Faz 2 belgesi "kredi defteri (çift kayıt)" yazmıştı (`:2462`); master spec
"atomik kredi ledger'ı" (`:57`, `:205`). Ölçülen gerekçe tek tablo lehine:
(a) tek hesap türü var (kullanıcının kredisi) — çift kaydın ikinci ayağı
(platformun gelir/gider hesabı) Faz 4'ün ödeme kaydında anlam kazanır, bugün
her satırın karşı hesabı "platform" olur, bilgi sıfır; (b) atomiklik zaten
tek UPDATE'te: `WHERE bakiye >= :m` koşulu yarışı Postgres'e bırakır, her
seferinde `SUM` almak (kilit + kullanıcı başına büyüyen tarama) ya da
`SELECT FOR UPDATE` + karşılaştırma iki gidiş-dönüş ve kilit tutma; (c)
önbellek DOĞRULANABİLİR: `tutarlilik` her bakım turunda SUM ile bakiyeyi
karşılaştırır, sapma günlüğe düşer — önbellek yanılırsa görünür, sessiz
kalmaz; (d) idempotency satırın kendisinde (`UNIQUE`), Faz 4'ün webhook event
id'si aynı sütuna yazılır (master `:205-208`). Hesap tablosu + çift kayıt
Faz 4'te paketler ve MoR mutabakatı gelince yeniden değerlendirilir; o gün
`kredi_hareketleri` olduğu gibi kalır, karşı hesap sütunu eklenir.

**Faz 2'den devralınan.** "`isler.kredi_tahmini` + `anahtar_kaynagi`
defterin ilk müşterisi" (`:2464-2466`); `medya.credits`in "ledger'ın tek
müşterisi" notu (Faz 1 `:1686-1689`) → `isler.kredi_gercek` onun iş
düzeyindeki toplamı; "admin kredi ekleyemez (defter yok)" (`:1548-1549`);
"kredi defteri yedeği Faz 3" (`isletme.md:173`, 7'de kapanır).

**Dokunulan.** `services/tablolar.py` (+1 sınıf `KrediHareketi`, +5 sütun üç
tabloda; `HAREKET_TURLERI`, `PLANLAR_KUMESI` sabitleri; **`IS_TABLOLARI`
bekçi listesi 8 → 9: `kredi_hareketleri`** — `kullanici_id` taşıyor, iş
tablosu), `services/kiraci.py` (`IS_TABLOLARI` 9), `alembic/versions/0007_kredi.py`
(RLS literali `TABLOLAR` 9 + `yonetici_ekler`), yeni `services/defter.py`,
yeni `tests/test_defter.py` (~30: ileri-geri-ileri + `alembic check`; rezerv
yeterli/yetersiz; **iki eş zamanlı rezerv aynı bakiyeye — iki `Session`,
gerçek Postgres, biri `YetersizBakiye`**; onay fark iade / sıfır / aşım
WARNING; iade idempotent (ikinci çağrı no-op, satır sayısı sabit); hibe
`ON CONFLICT` no-op; `duzelt` negatif; `tutarlilik` sapmayı bulur; iki
kullanıcı depo düzeyinde izole; CASCADE; `is_id` SET NULL — iş silinince
satır kalır), `tests/test_rls.py` (`len == 8` → **9**; `0006_rls` literali
yanına `0007_kredi` literali; `kredi_hareketleri`de DÖRT politika: üçü aynen
+ `yonetici_ekler`; kullanıcı başkasının hareketini OKUYAMAZ, admin okur +
ekler ama SİLEMEZ), `tests/test_tablolar.py` (bu belgeden ÜÇÜNCÜ çapa
cümlesi: "`IS_TABLOLARI` bekçi listesi 8 → 9: `kredi_hareketleri`" deseni
`faz3` belgesinden regex ile; `len(metadata) == 13` → **14**; CHECK
kümeleri), `tests/test_galeri_db.py` (`DEPOLAR["services/defter.py"]` sorgu
sayısıyla; **`EK_DEPOLAR`a** — `depo_` kalıbı dışında, `kuyruk.py` gibi;
`KIRACISIZ["services/defter.py"]`: `onayla`/`iade` "işçi elindeki işin
rezervi; `is_id` `al`dan geldi, RLS bağlamı işçi bağlıyor", `tutarlilik`
"periyodik bakım: bütün kiracıların toplamı"), `tests/test_db.py` (`BAS` →
`0007_kredi`), `tests/test_i18n.py` (konuşmayan modül), `docs/graflar/*`.
Rota YOK, davranış değişikliği YOK.

**Risk.** Düşük-orta. Geri dönüşsüz olan adlar: `tur` kümesi ve
`idempotency_anahtari` biçimleri (`rezerv:<is_id>` …) — Faz 4 bunları
okuyacak, belgeye yazılı. `kullanicilar.bakiye`nin önbellek olması bir
tutarlılık borcu: `tutarlilik` ölçer, `duzelt` kapatır, sessiz sapma yok.
`bakiye` sütunu hesap tablosunda (RLS dışı) — yazımı yalnız `defter.py`den,
AST bekçisi `kullanicilar.bakiye`ye `UPDATE` kuran başka modül yok der.

**Çıkış ölçütü.** `alembic upgrade head && downgrade base && upgrade head`
temiz, `alembic check` boş; **14 tablo**; eş zamanlı rezerv testi 100
tekrarda çift düşüm 0 (bakiye asla eksiye inmez); RLS dört politika; takım yeşil.

**Sahibin adımı — yok.** Göç dağıtım öncesi komutta (`tools/goc.py`, Faz 1 K6);
`bakiye` öntanımlı 0, `plan` 'free' — mevcut kullanıcılar dokunulmadan geçer,
ilk hibe 3. görevin bakım turuyla yatar.

---

## 2. Rezerve → onayla / iade — `routers/uretim.py`, `services/isci.py`, `services/kuyruk.py` (PR: `faz3/rezerve-onayla`)

**Kapsam.** Çıkış kriterinin defter yarısı: para bu görevden sonra SAYILIR.

* **Rezerv (rota).** `_kapilar` (`routers/uretim.py:109-122`) zincirinin
  sonuna, `check_gunluk`ten SONRA: `kaynak == "platform"` ise
  `defter.rezerve(db, kullanici.id, is_.id, kredi_tahmini)` — sıra önemli:
  bakiye düşümü, işin satırı yazıldıktan sonra AYNI transaksiyonda (rezerv
  satırı `is_id` ister; `kuyruk.ekle` + `rezerve` + commit). `YetersizBakiye`
  → **402** JSON `{"detail": {"kod": "err.kredi_yetersiz", "bakiye": …,
  "gereken": …, "plan": "free"}}` (K11; i18n `err.kredi_yetersiz` "Bakiyen
  {bakiye} kredi, bu iş {gereken} ister…"). Günlük tavan (429) KALIR ve
  önce sorulur: tavan kötüye kullanımın, bakiye paranın kapısı (K9).
* **BYOK iş rezerv ETMEZ (K3).** `anahtar_kaynagi == "kullanici"` → defter
  dokunulmaz; saatlik iş tavanı (`check_saatlik`) herkese aynen. Kullanıcı
  sağlayıcıya kendi ödüyor; platform payı fiyatlandırma kararı, Faz 4.
* **Onay (işçi).** `_yaz` (`isci.py:417-448`): medya satırları yazıldıktan
  sonra `kredi_gercek = Σ meta["credits"]` (medya başına `_kredi`, `:392-399`;
  spec yoksa 0), `kuyruk.bitir(db, is_id, sonuc, an, kredi_gercek=)` artık
  `isler.kredi_gercek`i de yazar (`kuyruk.py:281-289`); `defter.onayla(db,
  is_id, kredi_gercek)` AYNI commit'te — iş `bitti` olup fark iade edilmemiş
  bir ara durum yok. Nesne yazıldı, satır düştü → nesneler silinir ve `_dusur`
  (bugünkü telafi aynen) → iade.
* **İade (dört yol, hepsi `defter.iade(db, is_id)`):** (a) işçi `_dusur` /
  `kuyruk.dusur` (`:293-296`) — sağlayıcı hatası, yazım hatası; (b) kullanıcı
  iptali `kuyruk.iptal` (yalnız `bekliyor`, `:182`) — rota kullanıcının
  bağlamında; (c) bayat düşürme `kuyruk.bayatlari_dusur` (`:300`, bakım
  turu, admin bağlamı → `yonetici_ekler`, K4) — düşürülen her `is_id` için;
  (d) saklama silmesi `eskileri_sil` (`:426`) iade ETMEZ: silinen iş çoktan
  `bitti/hata/iptal`, defteri kapanmış; `is_id` SET NULL, satır kalır.
  `iade` idempotent: (a) ve (c) aynı işe iki kez değebilir.
* **Yeniden gönderim** (`routers/isler.py:289-310`) yeni iş = yeni rezerv;
  eski işin defteri kapalı (hata → iade edilmişti). "hata → yeniden gönder"
  döngüsü bakiyeyi değil yalnız saatlik tavanı yer — bilerek.
* **Panel ve SSE:** `kuyruk._json` dökümüne `kredi_gercek` eklenir; `isler.js`
  bitti satırında "tahmin → gerçek" gösterir (6. görev süsler, burada ham).

**Sıralama — neden rezerv `check_gunluk`ten SONRA ve `kuyruk.ekle`yle aynı
transaksiyonda.** Rezerv bakiyeyi DEĞİŞTİRİR; tavan yalnız OKUR. Kapı
zinciri "ucuz ve salt okunur önce, yazan en sonda" (Faz 2 / 6'nın
`_kapilar` gerekçesi `uretim.py:113-116`); tavan 429 dediyse bakiye hiç
düşmez. `is_id` olmadan rezerv satırı yazılamaz (FK), o yüzden `ekle`den
sonra; ikisi tek commit — rota 402 derse iş satırı da geri alınır, kuyrukta
öksüz iş yok.

**Faz 2'den devralınan.** "defter geldiğinde 'rezerve' tavan denetiminin
yerine, 'onayla' `bitir`in içine oturur" (`:2464-2466`) — yarısı aynen
(onayla `bitir`de), yarısı sapma: tavan YERİNE değil YANINA (K9);
"`kredi_tahmini` TAHMİN — gerçek maliyet Faz 3'ün mutabakat kalemi"
(`:194`, `:1046-1047`, `:1078-1079`); K8 "yeniden deneme yok" — iade onun
tamamlayıcısı: kaybolan iş parayı da kaybettirmez.

**Dokunulan.** `routers/uretim.py` (`_kapilar` + rezerv, dört rotada
transaksiyon sınırı), `services/kuyruk.py` (`bitir(kredi_gercek=)`, `_json`),
`services/isci.py` (`_yaz` toplam + `onayla`; `_dusur` → `iade`; bakım turu
bayat düşürmede `iade`), `routers/isler.py` (iptal → `iade`), `services/kapilar.py`
(402 yardımcısı), `bundled/i18n/*` (+2), `static/isler.js` (ham `kredi_gercek`),
`tests/test_uretim_kapilar.py` (~10: platform iş rezerv düşer, BYOK düşmez,
402 gövdesi, 429 önce 402 sonra — tavan aşımında bakiye dokunulmaz, 402'de
iş satırı YOK), `tests/test_isci.py` (~10: bitti → onay fark iade, gerçek ==
tahmin → 0, sağlayıcı hatası → tam iade, yazım hatası → nesne silinir + iade,
bayat → iade admin bağlamında, iptal → iade, yeniden gönderim yeni rezerv),
E2E (`tests/test_e2e_isler.py`: sahte sağlayıcı hata → panelde bakiye eski
değerine döner), `docs/graflar/*`.

**Risk.** Orta-yüksek: bu görevden sonra yetersiz bakiye üretimi ENGELLER.
Küçültme: hibe henüz yok (3. görev) → 1 ve 2 main'e girip 3 girmeden canlıya
ÇIKILMAZ (mevcut kullanıcı bakiye 0, her şey 402); belge bunu 3'ün "Sahibin
adımı"na yazar, sıra 1 → 2 → 3 tek dağıtım penceresi. Sağlayıcı faturaladı,
`bitir` düştü, iade edildi (K8'in dünyası): platform zararı, kullanıcı değil —
bilinen; 5'in marj raporunda `hata` işlerinin sağlayıcı maliyeti görünür.

**Çıkış ölçütü.** Ücretsiz kullanıcı (bakiye elle `duzelt` ile) platform
anahtarıyla iş verir → bakiye tahmin kadar düşer → `tek_tur` → `bitti`,
`kredi_gercek` dolu, fark iade; sahte sağlayıcı hata → bakiye eski değer;
BYOK iş bakiyeye dokunmaz; 402 gövdesi üç alanı taşır; takım yeşil.

**Sahibin adımı — yok** (3 ile birlikte dağıtılır, oradaki adım).

---

## 3. Planlar ve aylık hibe — `services/planlar.py`, `model_available(plan)`, admin plan/kredi rotaları (PR: `faz3/planlar-hibe`)

**Kapsam.** Kullanıcının planı ve planın parası.

* **Kod kataloğu `services/planlar.py` (K5):** `Plan(ad, aylik_hibe, filigran,
  video, fiyat=None)`; `PLANLAR = {"free": Plan(aylik_hibe=FREE_AYLIK_HIBE,
  filigran=True, video=False), "temel": Plan(…, filigran=False, video=True),
  "pro": Plan(…, filigran=False, video=True)}`. `temel`/`pro` bugün yalnız
  METADATA (hibe sayıları yer tutucu, fiyat `None` — Faz 4 Polar ürünüyle
  doldurur); kimse o plana geçemez, admin dışında. `FREE_AYLIK_HIBE`
  `KROMIS_FREE_AYLIK_HIBE` ortamından, **öneri 200 kredi/ay ≈ 1 USD**
  sağlayıcı maliyeti (1 kredi ≈ 0,005 USD çapası; ~25 Azure `medium` görsel);
  sayı SAHİBİN, K6. `kullanicilar.plan` CHECK kümesi `PLANLAR.keys()` ile
  eşit — bekçi.
* **`model_available(configured, plan)` nihayet `plan`ı OKUR**
  (`services/modeller.py:26-40`'ın "değişecek yer burası" sözü): `configured
  and (spec.plan == "free" or plan != "free") and (spec.kind != "video" or
  PLANLAR[plan].video)`. Katalogdaki `ImageModel.plan` (`catalog.py:195-202`)
  kararın verisi — bugün hepsi `"free"`, bu görev video modellerini KATALOGDA
  DEĞİL plan kataloğunda kapatır (`video=False`): video kuralı planın
  özelliği, modelin değil. Model dökümü (`/api/models`, `modeller.py:107-112`)
  `available: false` yanına `sebep: "anahtar" | "plan"` — arayüz kapalı
  modeli GİZLEMEZ, "planında yok" rozetiyle gösterir (yükseltme çağrısı
  Faz 4'ün satış yüzü; bugün rozet). Rotalar (`uretim.py` dört rota + yeniden
  gönderim) aynı işlevi sorar → **403** JSON `err.plan_kapsamiyor` {model,
  plan}. Kapı anahtar kaynağından BAĞIMSIZ: BYOK'lu ücretsiz kullanıcı da
  video alamaz — kuralın sebebi filigran yokluğu, anahtarın kimin olduğu
  onu değiştirmez (K7 notu).
* **Aylık hibe — "hibeye tamamla", no-rollover (K6).** İşçinin bakım turu
  (`bakim_turu`, `isci.py:631`, 5 dk, admin bağlamı) `defter.hibe_turu(db,
  an)`: her kullanıcı için `hibe = PLANLAR[plan].aylik_hibe`; `bakiye < hibe`
  ise `defter.hibe(db, u, hibe - bakiye, anahtar=f"hibe:{u}:{an:%Y-%m}")`,
  değilse DOKUNMA. Anahtar aylık → ay içinde bir kez, `ON CONFLICT` no-op;
  bakım turu her 5 dk'da aynı sorguyu koşar, ikinci koşu satır yazmaz.
  "Devredilmeyen" böyle sağlanır: dolu bakiye üstüne hibe BİNMEZ, kullanılan
  kadar dolar. Yeni kayıt (`routers/hesap.py:109` `kayit`) `defter.hibe`yi
  doğrudan çağırır — ilk hibe için 5 dk beklenmez. `sona_erme` türü bu
  fazda YAZILMAZ (tamamlama kuralında düşecek şey yok); Faz 4 paketlerle
  gelirse anlam kazanır.
* **Admin:** `POST /api/admin/kullanicilar/{id}/plan` `{"plan": "pro"}` →
  `kullanicilar.plan` (hesap tablosu, RLS dışı; `tavan` rotasının deseni
  `routers/admin.py:102`), `POST /api/admin/kullanicilar/{id}/kredi`
  `{"miktar": ±n, "aciklama": "…"}` → `defter.duzelt(…, admin_id=admin.id)`
  (`yonetici_ekler`, K4). `ADMIN_ROTALAR` 7 → 9 (bekçi). `admin.js`
  kullanıcı satırında plan seçici + "kredi ekle" alanı; `olay=admin.plan`,
  `olay=admin.kredi` günlük satırları (`kromis.admin`).

**Planlar kodda, tablo DEĞİL (K5).** Üç plan, alanları sabit, fiyat yok:
tablo bugün üç satırlık bir sözlük olur, göç + depo + admin CRUD + bekçi
ister ve hiç değişmez. Ödeme gelince plan ↔ Polar ürün id'si, fiyat, para
birimi, dönem bilgisi gerekir — o gün `planlar` tablosu ve `kullanicilar.plan`
FK'si göçle gelir, `services/planlar.py` arayüzü (`PLANLAR[ad]`) aynı kalır,
okuyanlar değişmez.

**Faz 2'den devralınan.** "`model_available(plan)` → Faz 3" (`:2462-2466`;
Faz 1 `:1686-1689`); "admin kredi ekleyemez" (`:1548-1549`); 2. görevin
"3 girmeden canlıya çıkılmaz" kısıtı.

**Dokunulan.** yeni `services/planlar.py`, `services/modeller.py`
(`model_available` + döküm `sebep`), `services/defter.py` (`hibe_turu`),
`services/isci.py` (bakım turunda `hibe_turu`; `BakimOzeti` +`hibe_satiri`),
`routers/{uretim,isler,admin,hesap}.py`, `services/depo_admin.py` (`plan_yaz`),
`static/{admin,core}.js` (rozet), `bundled/i18n/*` (+~6), `.env.example`
(`KROMIS_FREE_AYLIK_HIBE`, 1. bölüm) + `tests/test_docker_kapisi.py` `ALTYAPI`,
`tests/test_planlar.py` (~15: CHECK ↔ `PLANLAR` eşit; `model_available`
dört durum; free + video → 403 gövdesi; BYOK'lu free + video → 403; döküm
`sebep`; hibe tamamla: 0 → 200, 150 → 200 (+50), 250 → dokunma; aynı ay
ikinci tur no-op; ay değişince yeni satır; kayıtta anında hibe; admin plan
yaz → sonraki iş video alır; admin kredi ± → `duzeltme` satırı `admin_id`
dolu; admin olmayan 403), `tests/test_admin.py` (`ADMIN_ROTALAR` 9),
`docs/graflar/*`.

**Risk.** Orta. Hibe miktarı ürün kararı: 200 kredi = ~25 görsel/ay, sahibin
`.env`i değiştirir, kod sabiti değil. `hibe_turu` bütün kullanıcıları her 5
dk tarar: `WHERE bakiye < :hibe` süzgeciyle, 20-50 kullanıcıda ölçülemez;
1.000+ kullanıcıda kısmi indeks adayı (Faz 5 ölçümü). Video modellerinin
ücretsiz plana kapanması BUGÜNKÜ kullanıcılar için davranış değişikliği:
hepsi `free`, hepsi video görüyordu — dağıtım notunda yazılır, sahip kendi
hesabını `pro` yapar (aşağıda).

**Çıkış ölçütü.** Yeni kullanıcı kayıt olur → bakiye 200, `hibe` satırı;
ay içinde 120 harcar → bakım turu dokunmaz; ay değişir → +120, 200;
ücretsiz planda video modeli 403 + rozet; admin `pro` yapar → video açılır;
takım yeşil.

**Sahibin adımı — planı ve hibeyi belirlemek, kendi hesabını `pro` yapmak
(canlıda bir kez, 1–3 birlikte dağıtılır).** Platformun sırrına
`KROMIS_FREE_AYLIK_HIBE=200` (ya da sahibin sayısı; boş = 200). Dağıtım
sonrası ilk bakım turu (≤ 5 dk) bütün mevcut kullanıcılara hibe yatırır —
`olay=bakim` satırında `hibe_satiri=N`. Sonra `/admin` → kendi satırı → plan
`pro` (`olay=admin.plan`). Kontrol: bir görsel işi platform anahtarıyla →
`GET /api/kredi` (6'ya kadar `/api/admin/kullanicilar` bakiye sütunu) düşer,
biter, iade satırı görünür.

---

## 4. Filigran — `services/filigran.py`, işçide `_uret` → `_yaz` arası, `medya.filigranli` (PR: `faz3/filigran`)

**Kapsam.** Ücretsiz planın görseli filigranlı çıkar; yalnız GÖRSEL, yalnız
İŞÇİDE, TEK nesne (K7).

* **Yer:** `services/isci.py` `_uret` (`:349-369`) baytları döndürdükten
  sonra, `_yaz` (`:417`) nesneyi yazmadan önce: `if PLANLAR[plan].filigran
  and spec.kind == "image": sonuclar = [filigran.uygula(b) for b in sonuclar]`.
  Plan işin sahibinden (`kullanicilar.plan`, `kos` işi alırken okur);
  `kind` katalogdan (`_kredi`nin `spec`i). `_uret` ve adaptörler DEĞİŞMEZ.
* **Çekirdek `composite.py`den:** `services/filigran.py` `uygula(png: bytes,
  *, dosya=None) -> bytes` — `gorsel.to_png` ile PNG'ye çevir (sağlayıcı
  JPEG/WebP verebilir), `composite.composite_logo`nun konum/ölçek/opaklık
  mantığıyla bindir: öntanım **alt-sağ** (`bottom-right`, `POSITIONS`
  `:35-39`), logo genişliği görselin **%6**'sı, **opaklık 0,6**, gölge
  `SHADOW_OFFSET` aynen; PNG döner. Marka-nötr varlık **`bundled/filigran.png`**
  (metin "kromis" değil, soyut işaret — marka kararı `marka-ve-unvan.md`'ye
  bağlı, dosya değişince golden yeniden üretilir; `tools/make_logo_goldens.py`
  deseni). `KROMIS_FILIGRAN_DOSYASI` ortamı ezer (sahip kendi PNG'sini koyar).
* **`medya.filigranli bool`** (0007'de hazır) `depo_medya.kaydet` meta'sından
  yazılır; `/api/history` dökümüne girer → galeri kartında rozet (6).
* **Video:** ücretsiz planda video modeli yok (3) → filigransız video
  ücretsiz kullanıcıya çıkmaz → ffmpeg yok. Ücretli planlar filigransız
  (`filigran=False`). Bu kural bozulursa (ücretsiz video açılırsa) video
  filigranı ikili bağımlılık kararıyla gelir — "Faz 3 dışı"nda yazılı.

**Tek nesne, işçide — iki nesne ya da servis anında DEĞİL (K7).** Servis
anında bindirme K7'yi (Faz 2 `:2409`, "uygulama bayt taşımaz", 302 → R2)
bozar: her `GET /output` uygulama sürecinden geçer, R2'nin sıfır çıkış
ücretinin sebebi yok olur. İki nesne (ham + filigranlı) saklamak yükseltince
hamı açar ama depolamayı ikiye katlar ve "hangi nesne servis edilir" kararını
servise taşır; ücretsiz kullanıcının geçmiş görsellerinin yükseltmede
filigransız açılması ürün vaadi değil (master `:183` "ticari haklar" ücretli
katmana ait, geçmişe değil). Tek nesne: yazıldığı gibi servis edilir,
`filigranli` bayrağı yalnız arayüz bilgisi.

**Faz 2'den devralınan.** "Filigran (ücretsiz katman) → Faz 3" (`:2467`);
K7 servis kararı (`:2409`); işçi telafi deseni (`isci.py:417-448`).

**Dokunulan.** yeni `services/filigran.py`, `bundled/filigran.png`,
`services/isci.py` (`_uret` → `_yaz` arası tek satır + plan okuma),
`services/depo_medya.py` (`filigranli` meta → sütun), `routers/galeri.py`
(döküm), `.env.example` (`KROMIS_FILIGRAN_DOSYASI`) + `ALTYAPI`,
`tests/test_filigran.py` (~10: **golden** — sabit 256×256 girdi + bundled
işaret → bayt eşitliği, `tests/test_composite.py` deseni; JPEG girdi PNG
çıkar; boyut korunur; 50 MP sınırı; `KROMIS_FILIGRAN_DOSYASI` yok → açık
hata, sessiz filigransız DEĞİL; free + image → `filigranli=true`; pro +
image → false ve bayt aynen; free + video imkânsız (3'ün 403'ü) — yine de
işlev `kind=="video"`da dokunmaz), `tests/test_isci.py` (+3),
`tests/test_telif.py`/`test_docker_kapisi.py` (yeni `bundled/` dosyası imaja
GİRER — `.dockerignore` bekçisi), `docs/graflar/*`.

**Risk.** Düşük-orta. Görsel yeniden kodlanır (PNG): sağlayıcının JPEG'i
büyür — ücretsiz kullanıcıda kabul (kalite değil boyut). İşçiye CPU işi
eklenir: 1024² PNG bindirme ~100 ms, sağlayıcı süresinin yanında görünmez;
`sure_ms` (`isci.py:487-488`) ölçer. Filigran dosyası imajda olmalı —
`.dockerignore` `bundled/`yi dışlamıyor, bekçi doğrular.

**Çıkış ölçütü.** Ücretsiz kullanıcının görseli indirilince işaret alt
sağda; `pro` kullanıcının görseli sağlayıcının verdiği bayt; golden eşit;
`filigranli` bayrağı `/api/history`de; takım yeşil.

**Sahibin adımı — filigran işaretini seçmek (isteğe bağlı).** Öntanımlı
`bundled/filigran.png` marka-nötr; sahip kendi PNG'sini (şeffaf arka plan,
≥ 512 px genişlik) platformun diskine/imajına koyup `KROMIS_FILIGRAN_DOSYASI`
ile gösterir. Kontrol: ücretsiz test hesabıyla bir görsel, indir, bak.

---

## 5. Tarife–maliyet mutabakatı ve marj raporu — `services/saglayici_meta.py`, `isler.saglayici_*`, admin "Marj", `tools/marj_raporu.py`, `tools/tarife_kontrol.py` (PR: `faz3/mutabakat-marj`)

**Kapsam.** Tarifemiz (kredi) ile sağlayıcının faturası (USD) yan yana;
`isler.bitti − basladi` ve `model` sütunu raporun ham verisi (Faz 2 `:2467-2468`).

* **Yan kanal `services/saglayici_meta.py` (K8):** `ContextVar` — `kimlik_baglami`
  (`services/kimlik.py:146-171`) deseninin ikizi. `with toplayici() as meta:`
  işçide `_uret`i sarar; adaptörler İSTEĞE BAĞLI `saglayici_meta.kaydet(usage=…,
  maliyet_usd=…, request_id=…)` çağırır (bağlam yoksa no-op — istek yolu ve
  testler değişmez). İmza `list[bytes]` KALIR (`providers.py:20`, `:34-35`).
  İlk iki adaptör: **azure_mai** `usage.num_output_tokens`
  (`azure_mai_client.py:39-42`, gövde çoktan elde) ve **fal** `request_id`
  (`fal_client.py:663-666`, çoktan doğrulanıyor). `maliyet_usd` bugün HİÇBİR
  adaptörden gelmiyor (sağlayıcılar yanıtla fiyat vermiyor) — alan hazır,
  sahip fatura CSV'siyle ya da bir gün API'yle doldurur; rapor "bilinen"
  satırları ayırır.
* **Kalıcı:** işçi `_yaz`da `isler.saglayici_meta jsonb` (ham sözlük, redakte:
  `errlog.redact_secrets`) ve `isler.saglayici_maliyet_usd numeric(10,6)`
  (varsa) — 0007'de hazır. `kuyruk.bitir(…, saglayici_meta=, saglayici_maliyet_usd=)`.
* **Admin "Marj" tablosu** (`/api/admin/metrikler` → `marj` alanı; `admin.js`
  Metrikler sekmesi `:295`): model başına, 7 ve 30 gün: iş sayısı, Σ
  `kredi_gercek`, ≈ USD (× 0,005, çapa `catalog.py:467-472`), Σ
  `saglayici_maliyet_usd` (yalnız dolu satırlar; kaç satır dolu yazılır),
  ort. süre `bitti − basladi` (`percentile_cont` yerine `AVG`, iki satır
  yeter), `hata` işlerinin sayısı ve tahmini (K8 zararı görünür). Sorgu
  `depo_admin.marj(db, gun)` (kiracısız modül, `yonetici_okur`).
* **`tools/marj_raporu.py`** — aynı sorgu CSV'ye (`--gun 30 --cikti marj.csv`),
  `DATABASE_URL`le, admin bağlamı `kiraci.baglam(rol=ADMIN)`; sahibin
  hesap tablosuna yapıştıracağı şey (`tools/kullanici.py` deseni).
* **`tools/tarife_kontrol.py`** — katalogdaki `credits` yorumlarında
  "doğrulanamadı" notlu modelleri basar (`catalog.py:678`, `:726`, `:750-751`,
  `:806`; büyük/küçük harf duyarsız) ve çapayla bekleneni (kredi × 0,005 USD)
  yanına yazar; sahip dördünü sağlayıcının fiyat sayfasıyla doğrular, yorumu
  siler ya da sayıyı düzeltir. Bekçi testi: aracın bugün TAM DÖRT model
  bulması (liste elle değil, katalogdan; not silinince test sayıyı düşürür —
  CLAUDE.md § 5).

**Yan kanal, imza değişimi DEĞİL (K8).** `-> list[bytes]` beş istemci + 
`providers.py` + işçi + ~40 test dosyasının yamaladığı sözleşme (Faz 1 / 7'nin
104 testlik dersi). `list[Sonuc]`e çevirmek hepsine dokunur ve bugün taşınacak
veri iki alan. `ContextVar` yan kanalı kimlik bağlamının zaten kullandığı
mekanizma, adaptör "isteğe bağlı kaydet" der, yoksa sessiz; sağlayıcılar
fiyat/usage vermeye başladıkça adaptör adaptör açılır. Bedeli: örtük bağlam
(iş parçacığında kaybolabilir — işçi `to_thread` kullanmıyor, `kos` tek
parçacık; test bunu sınar).

**Faz 2'den devralınan.** "tarife-maliyet mutabakatı ve marj raporu → Faz 3;
`bitti - basladi` ve model sütunu ham veri" (`:2467-2468`); admin metrikleri
`SUM(kredi_tahmini)` (`depo_admin.py:114`, `:235-236`) → `kredi_gercek`e geçer
(tahmin sütunu kalır, "rezerv edilen" olarak).

**Dokunulan.** yeni `services/saglayici_meta.py`, `azure_mai_client.py`
(+1 satır), `fal_client.py` (+1 satır), `services/isci.py` (`toplayici`),
`services/kuyruk.py` (`bitir` alanları), `services/depo_admin.py` (`marj`;
`DEPOLAR` sayısı +1), `routers/admin.py`, `static/admin.js` (+tablo),
`bundled/i18n/*` (+~8), yeni `tools/marj_raporu.py`, yeni `tools/tarife_kontrol.py`,
`tests/test_saglayici_meta.py` (~8: bağlam yokken no-op; içinde toplanır;
iç içe bağlam sızmaz; azure_mai sahte 200 → `usage` yakalanır; fal →
`request_id`; redaksiyon), `tests/test_admin.py` (+marj: iki model, 7/30
gün, dolu/boş USD ayrımı, hata sayısı), `tests/test_araclar.py` (CSV başlığı
ve satır; `tarife_kontrol` dört model), `docs/graflar/*`.

**Risk.** Düşük. Rapor GERÇEK sağlayıcı maliyetini bugün gösteremez
(veri yok) — dürüstçe "bilinen n/N" yazar; değerini sahibin fatura
CSV'siyle el mutabakatı verir. `saglayici_meta` sağlayıcı gövdesinden
parça taşır: redaksiyon zorunlu, `pg_dump` sır testi (Faz 1) bu sütunu da tarar.

**Çıkış ölçütü.** İki sahte modelle koşan on iş → Marj tablosu iki satır,
Σ kredi ve ≈USD doğru, süre ortalaması `bitti − basladi`; `marj_raporu.py`
aynı sayıları CSV'ye; `tarife_kontrol.py` dört model; takım yeşil.

**Sahibin adımı — dört tarifeyi doğrulamak (bir kez, kod değişmez).**
`python tools/tarife_kontrol.py` dört satır basar (model, bugünkü kredi, ≈USD).
Sağlayıcının fiyat sayfasıyla karşılaştır; doğruysa yorumu sil, değilse
`credits`i düzelt — ikisi de bir PR, geçmiş kayıtlar değişmez (`catalog.py:460-465`
"retroaktif yazılmasın"). Sonra ayda bir `tools/marj_raporu.py --gun 30` →
sağlayıcı faturasıyla yan yana.

---

## 6. Kredi ön yüzü — `GET /api/kredi`, `#run-cost` B1, ayarlar "Kredi", filigran rozeti (PR: `faz3/kredi-onyuz`)

**Kapsam.** Kullanıcı bakiyesini görür, ne düşeceğini bilir, 402'yi anlar.

* **`GET /api/kredi`** (`routers/isler.py`, `/api/kota`nın yanına; `/api/kota`
  KALIR — panel günlük tavanı hâlâ ondan okur): `{bakiye, plan, hibe,
  sonraki_hibe, filigran, video, son_hareketler: [defter._json × ≤20]}`.
  `sonraki_hibe` = gelecek ayın ilk günü (`zaman.damga_utc`); `filigran`/
  `video` `PLANLAR[plan]`dan — arayüz plan kataloğunu tekrar etmez.
* **B1 `#run-cost`** (`static/core.js:547` `syncRunCost`; stüdyo planı
  `:122-136`): "≈ N kredi" → **"bu tur N düşer · kalan M"**; `M` `/api/kredi`
  bakiyesi, sayfa açılışında ve her iş olayında (SSE `bitti/hata/iptal` →
  yeniden çek; iade sonrası sayı geri gelir). `N > M` ise satır uyarı rengi,
  gönder düğmesi KAPANMAZ (sunucu karar verir — 402 tek doğruluk kaynağı,
  istemci yalnız gösterir). BYOK modelde "kendi anahtarın · düşmez".
* **402 / 403 ele alma:** `window.fetch` sarmalı (`core.js:42`, 401 deseni) →
  `err.kredi_yetersiz` gövdesi toast + ayarlar "Kredi" bölümüne bağlantı;
  `err.plan_kapsamiyor` → "planında yok" (Faz 4 satış sayfası gelince
  bağlantı orada).
* **Ayarlar "Kredi" bölümü** (`settings.js`): bakiye, plan, aylık hibe ve
  tarihi, filigran/video kuralı, son 20 hareket (tür simgesi, miktar imzalı,
  iş bağlantısı → panelde satır). Kaynak `/api/kredi`, ikinci istek yok.
* **Medya kartında filigran rozeti** (`galeri` kartı, `filigranli` alanı);
  iş panelinde `kredi_tahmini → kredi_gercek` ("rezerv 8 · gerçek 8 · iade 0").
* **i18n** +~15 anahtar (`kredi.*`, `err.kredi_yetersiz`, `err.plan_kapsamiyor`),
  `test_i18n` kümesi.
* **E2E** (Playwright): ücretsiz kullanıcı → composer satırı "kalan 200" →
  iş → "kalan 192" → sahte sağlayıcı bitirir → gerçek 8, kalan 192; ikinci
  senaryo sahte hata → "kalan 200" geri.

**Faz 2'den devralınan.** "kredi göstergesi Faz 3'e önerildi" (`:2491-2496`);
stüdyo B1 "kaç kredin kaldı / bu tur ne düşer" (`studyo-guncelleme-plani.md:122-136`);
Faz 2 K3 vanilla (`isler.js` deyimi); `window.fetch` tek kapı (`core.js:42`).

**Dokunulan.** `routers/isler.py` (+1 rota → 70 rota: 2'de 0, 3'te +2, burada +1),
`static/{core,settings,isler}.js`, galeri kartı betiği, `bundled/i18n/*`,
`tests/test_kredi_route.py` (~8: alanlar, 20 sınırı, başkasının hareketi
görünmez — RLS + depo, `sonraki_hibe` biçimi), `tests/test_index.py` (yalnız
`#run-cost` metni ve "Kredi" bölümü kökü — metin çapaları dokunulmaz),
`tests/test_e2e_kredi.py` (2 senaryo), `docs/graflar/onyuz.md` (yükleme
sırası değişmez: yeni betik yok), `docs/graflar/*`.

**Risk.** Düşük. Vanilla'da +~250 satır JS; Faz 2 K3'ün "yeniden bakış Faz 4"
noktası yaklaşıyor — bu görev çerçeve tartışmasını AÇMAZ, Faz 4 bakar.

**Çıkış ölçütü.** E2E iki senaryo yeşil; `GET /api/kredi` başkasının
hareketini sızdırmaz; 402 toast + bağlantı; galeri rozeti; takım yeşil.

**Sahibin adımı — yok.**

---

## 7. Operasyon ve belgeler — `isletme.md`, `KURULUM.md`/`README`, `.env.example`, bakım turu tutarlılık, Faz 4'e devir (PR: `faz3/operasyon`)

**Kapsam.** Faz 3'ün işletme ayağı ve kapanış belgesi.

* **`docs/isletme.md:173`** "Kredi defteri yedeği — Faz 3 (tablo yok)" →
  "Faz 3'te kapandı: `kredi_hareketleri` günlük `pg_dump`un içinde (§ 5),
  ayrı yedek yok; geri yükleme sonrası `defter.tutarlilik` (bakım turu ilk
  koşuda) SUM == bakiye der". § 6 uyarılara `olay=defter.tutarsiz` ve
  `olay=defter.asim` satırları (Sentry'ye WARNING düşer, Faz 2 / 9).
* **Bakım turunda tutarlılık:** `bakim_turu` → `defter.tutarlilik(db)`; sapma
  varsa kullanıcı başına WARNING; `BakimOzeti` +`tutarsiz_kullanici`.
  Düzeltmez (K1 gerekçesi: ölçer, admin `duzelt`).
* **`.env.example`** 1. bölüm: `KROMIS_FREE_AYLIK_HIBE` (3), `KROMIS_FILIGRAN_DOSYASI`
  (4) — her biri kendi görevinde eklenir, burada `test_docker_kapisi`
  `ALTYAPI` sırası ve README/KURULUM `.env` tablosu (`test_docker_kapisi.py:69-71`
  okur) tamamlanır.
* **KURULUM.md / README** "Planlar ve kredi" bölümü: üç plan, hibe kuralı,
  BYOK düşmez, filigran, admin kredi/plan; canlı kontrol listesi (3'ün
  sahibin adımı) buraya taşınır.
* **Faz 3 kapanış** bu belgeye (Faz 2 `:2287-2343` deseni): PR tablosu,
  ölçümler (test sayısı, rota, tablo), sahibin bekleyen adımları.
* **Faz 4'e devir listesi** (bu belgenin "Faz 3 dışı"sından kapanışa):
  paket satın alma = yeni `tur` (`paket`) + göç; hibe/paket **kova ayrımı**
  (K6 alternatifi — paket bakiyesi devreder, hibe devretmez → iki kova ya
  da FIFO tüketim, o gün); webhook idempotency = `idempotency_anahtari`
  (`polar:<event_id>`); `planlar` tablosu + fiyat; `temel`/`pro` hibe
  sayıları; "ticari haklar" metni; KVKK: defter CASCADE mi anonimleştirme mi.

**Faz 2'den devralınan.** `isletme.md` § 5-6 iskeleti (`:2066`); bakım turu
`BakimOzeti` (Faz 2 / 10); `.env.example` bekçisi (`test_docker_kapisi.py:279`,
`:339-347`).

**Dokunulan.** `docs/isletme.md`, `KURULUM.md`, `README.md`, `.env.example`,
`services/isci.py` (bakım turu + özet), `tests/test_isci.py` (+2: sapma
WARNING, sapma yok sessiz), `tests/test_docker_kapisi.py`, bu belge
(kapanış), `docs/graflar/*`.

**Risk.** Düşük.

**Çıkış ölçütü.** `tests/test_docker_kapisi.py` yeşil (iki yeni değişken
üç yerde); bakım turu sapmayı yakalar (test); belge kapanışı dolu; takım yeşil.

**Sahibin adımı — ilk üretim koşusu kontrolü (canlıda bir kez).** Dağıtım
sonrası: `olay=bakim` satırında `hibe_satiri` ve `tutarsiz_kullanici=0`;
`/admin` Marj sekmesi boş değil; kendi hesabında `GET /api/kredi`; ücretsiz
test hesabıyla bir görsel — filigranlı, bakiye 200 → 192.

---

## Faz 3 çıkış kriteri

Ücretsiz kullanıcı platform anahtarıyla iş verir → rezerv düşer (402 yoksa)
→ panelde bakiye canlı ("bu tur X düşer · kalan Y") → iş biter → gerçek
maliyetle onaylanır, fark iade → hata/iptal/bayat düşme → TAM iade →
ücretsiz görselde filigran, ücretsiz planda video kapalı (403) → admin Marj
tablosu dolu → RLS bekçileri **9 tablo**, `kredi_hareketleri`de dört politika
→ her kullanıcıda `SUM(kredi_hareketleri.miktar) == kullanicilar.bakiye`
(bakım turu ölçer) → BYOK iş bakiyeye dokunmaz → tam takım yeşil (E2E dahil).

---

## Test stratejisi — kesişen kararlar (her görevin "Dokunulan"ında tek tek var)

* **Postgres gerçek, yarış gerçek.** `UPDATE … WHERE bakiye >= :m` yarışı iki
  `Session` + iki bağlantıyla: aynı bakiyeye iki eş zamanlı rezerv, biri
  `YetersizBakiye`; 100 tekrarda çift düşüm 0. `ON CONFLICT` idempotency ve
  RLS politikaları SQLite'ta yok — Faz 1'in fixture zinciri (`pg_kume →
  pg_sablon → veritabani_url → veritabani`) aynen.
* **RLS üç iddia, `kredi_hareketleri` için dördüncü:** kullanıcı başkasının
  hareketini okuyamaz; admin okur; admin EKLER (`yonetici_ekler`, K4 — yalnız
  bu tabloda); admin SİLEMEZ (hiçbir tabloda). `test_rls`nin "her tabloda üç
  politika" döngüsü bu tablo için dört bekler, ötekilerde dört BULMAZ.
* **İdempotency tekrar çağrısı no-op:** `iade` ×2, `hibe` aynı ay ×2,
  `onayla` sonra `iade` — satır sayısı ve bakiye sabit. Her anahtar biçimi
  (`rezerv:` `onay:` `iade:` `hibe:` `duzeltme:`) belgede; test biçimleri
  regex'le sınar (Faz 4 `polar:` ekler).
* **İşçi süreç değil işlev** (Faz 2): `tek_tur` + `uret_ve_bitir` aynen;
  hata → iade, bitti → onay, bayat → iade admin bağlamında — `zaman.an()`
  yamasıyla. E2E'de sahte sağlayıcı hata senaryosu bakiye geri gelir.
* **Sağlayıcı sahte, çağrı yeri aynen;** yan kanal testi sahte 200 gövdesiyle
  (`usage`, `request_id`), bağlam yokken no-op.
* **Golden filigran:** sabit girdi + bundled işaret → bayt eşitliği
  (`test_composite.py` deseni); işaret dosyası değişince golden yeniden
  üretilir, PR'a yazılır.
* **Elle tutulan listelerin bekçisi** (CLAUDE.md § 5): `IS_TABLOLARI` (9),
  `0007_kredi.TABLOLAR` literali, `HAREKET_TURLERI` ↔ CHECK, `PLANLAR` ↔
  CHECK, `ADMIN_ROTALAR` (9), `KIRACISIZ["services/defter.py"]`, `EK_DEPOLAR`
  (+`defter.py`), `ALTYAPI` (+2), `tarife_kontrol` dört model (katalogdan),
  `test_tablolar` üçüncü belge çapası (bu belge).
* **`kullanicilar.bakiye` tek yazar:** AST bekçisi — `UPDATE kullanicilar …
  bakiye` kuran modül yalnız `services/defter.py` (`test_galeri_db`nin
  deseni; rotalar ve işçi defteri çağırır, elle yazmaz).
* **`tests/test_index.py`**: yalnız `#run-cost` metni ve "Kredi" bölümü
  kökü; dondurulmuş kabuk testleri aynen durur.
* **Takım büyüklüğü tahmini:** 3.819 → ~3.950 (+~130), süre +15-25 sn (E2E
  iki senaryo, yarış testi 100 tekrar); ölçülür ve kapanışa yazılır.

---

## Sahibin karar noktaları — öneri ve gerekçe

**Sahibin kararı: BEKLİYOR** — K1–K11 aşağıda öneri; kabul/değişiklik
tarih ve kaynakla (Slack) bu satıra yazılır, görevler ondan sonra açılır.

| # | konu | öneri | neden | alternatif ve bedeli |
| --- | --- | --- | --- | --- |
| K1 | Defter biçimi | **Append-only tek tablo `kredi_hareketleri` + `kullanicilar.bakiye` önbelleği**; düşüm atomik `UPDATE … SET bakiye = bakiye − :m WHERE bakiye >= :m`; bakım turu SUM == bakiye ölçer | Tek hesap türü var, çift kaydın karşı ayağı bugün bilgi taşımaz; yarış Postgres'in satır kilidine bırakılır, gidiş-dönüş bir; önbellek doğrulanabilir (sapma günlüğe); idempotency satırın `UNIQUE`inde, Faz 4 webhook'u aynı sütunu kullanır | Her seferinde `SUM`: kilit + kullanıcı başına büyüyen tarama. Gerçek çift kayıt (hesap tablosu + iki satır): ödeme/MoR mutabakatında anlam kazanır, Faz 4'te göçle eklenir; bugün üç görev fazla |
| K2 | Rezerve → onayla | **Kuyruğa girişte tahmin rezerve** (`kuyruk.ekle` ile aynı transaksiyon), **bitişte gerçek ile onay + fark iade** (`bitir` ile aynı commit); hata/iptal/bayat TAM iade | Tahmin üst sınır (Faz 2 / 6): kullanıcı asla fazla ödemez, bakiye asla eksiye inmez; iade `is_id` anahtarıyla idempotent, K8'in ikinci düşürmesine dayanır | Yalnız bitişte düş: kuyruktaki 40 iş bakiyeyi aşabilir → negatif bakiye ya da bitişte "para yok" (sağlayıcı çoktan faturaladı). Yalnız girişte düş, iade yok: gerçek < tahmin farkı kullanıcıdan gider |
| K3 | BYOK işler | **Kredi DÜŞMEZ** (`anahtar_kaynagi == 'kullanici'` defteri hiç görmez); saatlik iş tavanı herkese kalır | Kullanıcı sağlayıcıya kendi ödüyor (Faz 2 / 6'nın "kendi parası" ilkesi aynen); işçi kapasitesini saatlik tavan korur | Küçük platform payı (ör. 1 kredi/iş): gelir ve "ücretsiz planda BYOK sınırsız mı" sorusu — fiyatlandırma kararı, Faz 4 |
| K4 | Admin kredi ekleme ve bakım turunun yazımı | **Yalnız `kredi_hareketleri`de `yonetici_ekler` INSERT politikası** (0007), `admin_id` ile iz; DELETE kimseye yok | İki yazar admin bağlamında: admin düzeltmesi ve işçinin bakım turu (hibe, bayat iadesi); `0006_rls`nin "admin INSERT yapamaz" kuralı öteki 8 tabloda aynen — istisna tek tablo, tek fiil, gerekçesi satırda | Admin rotasını hedef kullanıcının bağlamına bağlamak (`kiraci.bagla(hedef)`): politika değişmez ama admin BAŞKASI GİBİ yazar — `admin_id` izi kaybolur, `sahip` politikası "kullanıcı yazdı" der; tuzak |
| K5 | Planların yeri | **Kodda katalog `services/planlar.py`** (`free`/`temel`/`pro`), `kullanicilar.plan text CHECK`; DB tablosu Faz 4 (ödeme gelince fiyat/ürün id'siyle) | Üç sabit satır; tablo = göç + depo + CRUD + bekçi, hiç değişmeyecek veri için; `PLANLAR[ad]` arayüzü tabloya geçişte aynı kalır | Şimdi tablo: admin panelden plan tanımlar; bedeli bu fazda +1 görev ve Faz 4'te yine değişecek şema (fiyat, dönem, Polar id) |
| K6 | Aylık hibe ve no-rollover; miktar | **"Hibeye tamamla":** `bakiye < hibe` ise fark eklenir, değilse dokunulmaz; anahtar `hibe:<u>:<YYYY-MM>`; **free 200 kredi/ay** (≈ 1 USD, ~25 Azure `medium` görsel), `KROMIS_FREE_AYLIK_HIBE` ile sahip değiştirir | Devretmeme tek kuralla: kullanılmayan hibe üstüne binmez; tek kova, `sona_erme` satırı gerekmez; bakım turunda idempotent; sayı kod sabiti değil ortam | İki kova (hibe/paket): paket devreder, hibe ay sonu `sona_erme` ile düşer — paket yokken ikinci kova boş; Faz 4 paketlerle birlikte gelir, o gün yeniden değerlendirilir. Miktar: 100 (daha muhafazakâr) / 500 (daha cömert) — sahibin `.env`i |
| K7 | Filigranın yeri ve kapsamı | **İşçide, `_uret` → `_yaz` arası, TEK nesne, yalnız görsel**; ücretsiz planda video modelleri KAPALI (anahtar kaynağından bağımsız) | Servis anında bindirme Faz 2 K7'yi bozar (uygulama bayt taşımaz); tek nesne depolamayı ikilemez; video filigranı ffmpeg = yeni ikili + imaj, ücretsiz video kapalıyken gereksiz | İki nesne (ham + filigranlı): yükseltince ham açılır, depolama ×2, servis kararı karmaşık. Servis anında: URL sabit ama R2'nin sıfır çıkışı kaybolur. Ücretsiz videoya izin + ffmpeg: imaj +~100 MB, işçide dakikalık CPU |
| K8 | Sağlayıcı maliyet verisi | **`ContextVar` yan kanalı `services/saglayici_meta.py`**; adaptörler isteğe bağlı `kaydet(...)`, imza `list[bytes]` KALIR; ilk iki adaptör azure_mai (`usage`) ve fal (`request_id`) | `kimlik_baglami` deseni hazır; beş istemci + ~40 test yamasına dokunulmaz; sağlayıcı fiyat verdiğinde adaptör adaptör açılır | İmza değişimi `list[Sonuc]`: açık ve tip güvenli; bedeli 5 istemci + `providers.py` + işçi + testler, bugün taşınacak iki alan için |
| K9 | Günlük kredi tavanı | **KALIR** (`check_gunluk`, 429, admin ezmesi); bakiye kapısı (402) ondan SONRA | İki kapı iki tehdit: tavan kötüye kullanım/çalınan hesap (bakiyesi dolu bir hesabın bir günde boşaltılması), bakiye para; Faz 5'in IP limitleri tavanı devralır | Kaldır: defter zaten sınırlar; bedeli çalınan/kötüye kullanılan hesabın bütün bakiyesini bir günde harcayabilmesi ve admin ezmesinin kaybı |
| K10 | E2/E3 hızlı araçlar | **Faz 3 çekirdeğinin DIŞINDA**; defterden sonra isteğe bağlı mini faz (`isler.tur` göçü + katalog "araç" türü + sağlayıcı çağrısı + kredi) | Defter, plan, filigran birbirine bağlı yedi görev; araçlar defterin MÜŞTERİSİ, önce defter; `IS_TURLERI` CHECK göçü ve katalog türü kendi PR'ları | Faz 3'e almak: kapsam 7 → 9 görev, `uretim.py`ye iki rota, katalog şeması değişir; stüdyo planı "Faz 3 ürün araçları kartına ek" diyor, kart master spec dizisinin Faz 3'ü (numaralama tuzağı) |
| K11 | Yetersiz bakiye yanıtı | **402 JSON `err.kredi_yetersiz` {bakiye, gereken, plan}** | 402 "ödeme gerekir" — anlamı bu; 429'dan (kota, `Retry-After`lı) ve 403'ten (plan/yetki) ayrışır; ön yüz üç kodu üç farklı mesajla gösterir | 429: kota ile karışır, `Retry-After` anlamsız (para beklemekle gelmez). 403: plan kapısıyla (`err.plan_kapsamiyor`) karışır |

---

## Üst belgeden (spec §5 "Faz 5") ve önceki faz belgelerinden sapmalar — gerekçeli

* **"Kredi defteri (çift kayıt)" (Faz 2 `:2462`) → append-only tek tablo +
  önbellek** (K1). Master spec "atomik kredi ledger'ı" der (`:57`, `:205`),
  biçim söylemez; atomiklik tek UPDATE'te. Çift kayıt Faz 4'te ödeme
  mutabakatıyla anlam kazanırsa göçle gelir, satırlar kalır.
* **"'rezerve' tavan denetiminin YERİNE" (Faz 2 `:2464-2466`) → YANINA** (K9).
  Tavan kalır; iki kapı iki tehdit.
* **Tarife katalogda kalır** (master `:208` "kendi katalogumuzda") — UYUM;
  `cost_for` tek nokta, rezerv ve onay aynı işlevi çağırır. Kartın kredi
  aralıkları (`:172-175`) tarihsel, çapa notu (`:176-182`) geçerli.
* **Webhook idempotency** (master `:205-208`) — UYUM, erken: `idempotency_anahtari
  UNIQUE` bu fazda gelir, Faz 4 `polar:<event_id>` yazar; `tur` kümesine
  `paket` göçle eklenir.
* **"Devredilmeyen aylık kredi (no-rollover)" (master `:183`) → "hibeye
  tamamla"** (K6). Kural aynen sağlanır (kullanılmayan hibe birikmez), ay
  sonu `sona_erme` satırı yerine ay başı tamamlama — daha az satır, tek kova.
* **"Ücretli katmanlar (filigransız + ticari haklar)" (master `:183`)** —
  filigransız evet (4); "ticari haklar" hukuki metin, Faz 4'ün kullanım
  şartlarıyla (Polar AUP notu `:201-204`).
* **Plan tablosu YOK, kod kataloğu** (K5) — master spec "üyelik paketleri"
  der (`:220`), yeri söylemez; paketler Faz 4.
* **Ücretsiz planda video KAPALI** — master spec ücretsiz katmanı "filigranlı"
  diye tanımlar, videoyu ayırmaz; video filigranı ffmpeg istediği için kapalı
  (K7). Sahip ücretsiz video isterse iki yol: ffmpeg kararı ya da filigransız
  ücretsiz video (kartın kuralını bozar).
* **JWT → oturum** (Faz 1 K3) ve **user/organization → yalnız `kullanicilar`**
  sapmaları aynen sürüyor; defter kullanıcıya bağlı, kuruluş yok.

---

## Faz 3 dışı, ama burada not edilen

* **Ödeme (MoR/Polar), webhook, abonelik yaşam döngüsü, paketler, vergi,
  e-Arşiv** → **Faz 4** (Faz 2 `:2469-2470`; master `:184-214`). Bu fazın
  hazırladığı: `idempotency_anahtari`, `tur` CHECK (göçle `paket`),
  `kullanicilar.plan`, `PLANLAR` arayüzü, `temel`/`pro` iskeleti.
* **KVKK/GDPR: hesap silme ve defter** — `kredi_hareketleri` CASCADE (1);
  Faz 4 "anonimleştir, satırı tut" derse FK değişir. Saklama süreleri orada.
* **Video filigranı** — ffmpeg/imageio yeni ikili bağımlılık, imaj +~100 MB;
  ücretsiz video kapalıyken gereksiz. Kural değişirse ayrı karar.
* **E2/E3 hızlı araçlar** (arka plan kaldırma, vesikalık, görselden prompt,
  yan şerit; `studyo-guncelleme-plani.md:273-294`) → K10, defterden sonra
  mini faz: `IS_TURLERI` göçü, katalog "araç" türü, `cost_for` araç birimi.
* **Kova ayrımı (hibe/paket)** ve **`sona_erme` satırları** → Faz 4
  paketlerle (K6 alternatifi).
* **Platform payı BYOK'ta** → Faz 4 fiyatlandırma (K3 alternatifi).
* **Kötüye kullanım / IP limitleri** → Faz 5; günlük tavan (K9) ve saatlik
  tavan tohum. **Yedek tatbikatı** → Faz 5 (`isletme.md` § 5 satırı 7'de
  güncellenir, koşulmaz). **Dağıtımda çalışan işin kaybı** → Faz 5; iade
  (2) parayı korur, işi değil.
* **E-posta ile iş bitti bildirimi** (`services/posta.py` hazır) ve
  **persona / `chat_instructions_path` düzenleme** — ürün kararı yok, Faz 3+
  aynen (Faz 2 `:2481-2484`).
* **Gerçek sağlayıcı maliyeti (USD) otomatik** — hiçbir adaptör fiyat
  dönmüyor (`azure_mai_client.py:42` yalnız token); `saglayici_maliyet_usd`
  sütunu hazır, dolduran sahibin fatura CSV'si ya da bir gün API.
* **`hibe_turu` tarama indeksi** — 1.000+ kullanıcıda `WHERE bakiye < :hibe`
  kısmi indeks; Faz 5 ölçümü.
* **Sağlayıcı idempotency anahtarı** yok (Faz 2 K8 aynen) — iade parayı
  kullanıcıya döndürür, platformun sağlayıcı faturası kalır; marj raporu
  `hata` sütunuyla gösterir.
* **Bugünkü PR incelemesinin (2026-09-19) üç Faz-dışı notu — ayrı küçük
  düzeltme PR'ı #55 (taslak, 2026-09-19), Faz 3 değil:** (1) `.dockerignore` `.env` ve `.env.example`
  var (`:76-77`), PR #54'ün `.gitignore`a eklediği `.env.*` türevleri yok →
  `.env*`; (2) `test_env_yok_sayma` testinde alt sürecin `returncode`
  denetimi (çıkış kodu sınanmadan çıktı okunuyor); (3) Faz 2 belgesi
  `:1696-1697` "`olay=admin.*` görünmüyorsa lifespan'dan geçmiyor" cümlesi
  — aynı bölümün "İKİ ŞEY ÖLÇÜLDÜ" paragrafı bunu çoktan düzeltiyor, üstteki
  cümle ona işaret etmeli.
* **Ölçülmeyen:** filigran bindirmenin işçi süresine etkisi (4'te `sure_ms`
  ile), yarış testinin 100 tekrar süresi, `hibe_turu`nun 5 dk'lık tarama
  maliyeti (bakım turu `sure_ms`), gerçek Azure/fal `usage` alanlarının
  kararlılığı (canlı doğrulamada bir kez), takım süresi artışı.
