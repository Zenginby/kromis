# Faz 4 — Ödeme (Polar MoR), paketler ve abonelik, hesap silme / dışa aktarma, hukuki metinler: görev listesi

**Tarih:** 2026-09-21 · **Durum:** **2/8** (plan PR #69 `faz4/plan`, sahip 2026-09-21'de merge etti; görevler `faz4/<slug>` dallarında, her biri bir PR; **1b** görevi 2026-09-21'de sahibin yönlendirmesiyle eklendi, 7 → 8) · **Karar:** K1–K12 **kabul edildi 2026-09-21** (PR #69 sahip tarafından aynen merge edildi — Faz 3'ün deseni; madde madde değişiklik gelmedi) · **Önceki faz:** [faz3-kredi-defteri-filigran.md](faz3-kredi-defteri-filigran.md) (7/7 ✅, kapanış 2026-09-21, PR #56–#68)
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) §5 "Faz 5" kartının **"Ödeme Altyapısı: Merchant of Record (MoR)"** maddesi (`:184-214`) ve "Filigran & Kredi Kuralları" satırı (`:183`) — sapmalar bu belgenin sonunda tek tek yazılı. **Numaralama tuzağı** aynen (Faz 3 belgesi `:4`): master spec'in "Faz 5"i ürün yol haritasının SaaS kartı; bu belge SaaS dönüşümünün İÇ dizisindeki Faz 4'tür (Faz 0 web-first → 1 DB/hesap → 2 kuyruk → 3 kredi defteri → **4 ödeme/KVKK** → 5 işletme). Yol haritası kartı (Faz 4 "Ödeme, faturalama ve hukuk"): *"Bir kullanıcı kartla abone olup fatura alabiliyor ve hesabını tamamen silebiliyor."* — bu belgenin çıkış kriteri onu genişletir (sonda tam metin). Kartın "Stripe birincil" satırı 2026-09-18'de **MoR/Polar** ile güncellendi (Faz 1 ve Faz 2 belgelerinin "Not" satırı; master `:184-199`): Türkiye'den Stripe'a doğrudan hesap açılamıyor, uluslararası satış Merchant of Record üzerinden.

Faz 4'ün amacı, Faz 3'ün kurduğu defterin (rezerv → onay → iade, aylık hibe,
planlar, filigran, 402/403) üstüne **parayı almayı** koymak: bugün bakiyeye
para girişi yalnız aylık hibe ve admin `duzeltme` (Faz 3 `:18`), `temel`/`pro`
planlarına admin dışında kimse geçemez (`services/planlar.py:26-30`), `fiyat`
`None`, `Plan.aylik_hibe` yer tutucu 1.000 / 3.000. Faz 4'te kullanıcı bir
**kredi paketi** satın alır ya da **`temel`/`pro`ya abone olur**; ödeme, vergi
(KDV/VAT/GST), fatura ve kart verisi **Polar'da** (MoR), bizde yalnız Polar'ın
webhook'unun deftere yazdığı satır; paket kredisi **devreder**, abonelik hibesi
devretmez (iki kova, K3); abonelik yaşam döngüsü (yenileme, iptal, başarısız
ödeme) Polar'ın olayı → bizim plan sütunumuz (K6); kullanıcı **hesabını
siler** (içerik gider, defter anonim kalır — K9) ve **verisini dışa aktarır**;
kullanım şartları, aydınlatma metni, "ticari haklar" ve Polar kabul edilebilir
kullanım kuralları kayıtta onaylanır (K11). Katalog hijyeni — `gpt-image-1`
2026-10-23'te emekli, dört Azure fiyatı ve yedi kredi ≠ maliyet notu — bu
fazın İLK ve bağımsız görevi (1 ✅ 2026-09-21: girdi silindi; fiyat ve kredi
düzeltmeleri sahibin doğrulamasını bekliyor, 1b'ye devredildi). Hemen ardından
**katalog genişletme** (1b, 2026-09-21'de eklendi): ~10 görsel + ~10 video
model, sağlayıcıdan BAĞIMSIZ — sahibin 2026-09-21 yönlendirmesi: Azure bundan
sonra tek ana sağlayıcı DEĞİL, tarife sağlayıcı başına doğrulanır.

**BU FAZDA YOK** — gerekçeleri "Faz 4 dışı" bölümünde:

* **TR içi TRY satışı (iyzico/PayTR), e-Arşiv, taksit** → Faz 5+ (master
  `:189-192`: MoR'un YERİNE değil, istenirse ikinci ayak). Polar bize hizmet
  ihracı faturasının tek muhatabı; son kullanıcıya faturayı Polar keser.
* **Polar'ın kendi sayaç/kredi sistemi (events → meters → Meter Credits)** →
  KULLANILMAZ (K2): tarife bizim kataloğumuzda, defter tek gerçek (master
  `:205-208`). Polar yalnız "ödeme alındı" der.
* **BYOK'ta platform payı** → yine yok (K8; Faz 3 K3 aynen), Faz 5'te ölçümle.
* **Ön yüz çerçeve değişimi** (Faz 2 K3'ün "yeniden bakış Faz 4" noktası) →
  vanilla sürer (K12); satış sayfası sunucu şablonu, ödeme ve portal Polar'ın.
* **Kötüye kullanım / IP limitleri, içerik moderasyonu otomasyonu** → Faz 5;
  bu faz yalnız KURALI yazar (kullanım şartları, K11), uygulamasını değil.
* **E2/E3 hızlı araçlar** (Faz 3 K10) → mini faz, bu fazdan sonra.

Her madde bir PR (`faz4/<slug>` dalı), her PR tek başına yeşil ve geri
alınabilir; her PR'da testler + `docs/graflar` aynı commit'te, tam takım E2E
dahil yerelde koşulur (`KROMIS_E2E_ZORUNLU=1`). Sıra bağımlılığa göre: **1**
(bağımsız, önce — takvim kısıtı 2026-10-23), **1b** (1'den sonra; 2-4'ten
bağımsız, omurgayla paralel gidebilir — sahibin sıralı model listesini bekler),
**2 → 3 → 4** (omurga: şema →
webhook → checkout/satış yüzü), **5** (2'den sonra; 3 varsa Polar aboneliğini
de iptal eder, yoksa o adım sonraki PR'a), **6** (2'den sonra, 3-5'ten
bağımsız), **7** en son. Çıkış kriterinin ödeme yarısı 3-4'te, KVKK yarısı 5-6'da
karşılanır.

**NEDEN TEK GÖÇ (`0008_odeme`) — dört görevin sütun ve tabloları 2. görevin
göçünde.** Faz 3'ün "NEDEN TEK GÖÇ" gerekçesi (`:45-52`) aynen: `kova` ve
`paket` türü (2), `urunler`/`siparisler`/`odeme_olaylari` (3-4),
`kullanicilar.polar_*`/`plan_bitis` (3), `sartlar_kabul_at`/`sartlar_surumu`
(6), `temizlendi_at` (5) — hepsi NULL/öntanımlı, geriye uyumlu, sahibin
canlıda BİR `tools/goc.py` koşusu. 3-6. görevler şemayı hazır bulur.

Ölçüler Faz 3 kapanışından (`bb30f9a`, PR #68 ve sahibin #64/#67'si main'de;
Faz 3 belgesi "kapanış"): takım **3.982 geçti, 12 atlandı, ~271 sn** (E2E +
Postgres zorunlu); **70 rota** (`KAPILI` 63, `ADMIN_ROTALAR` 9), **111 modül**,
şema başı **`0007_kredi`**, **14 tablo**, `IS_TABLOLARI` **9**, RLS politikası
**28** (3 × 9 + `kredi_hareketleri.yonetici_ekler`), `DEPOLAR` 11, tarayıcı
betiği 13. Bugünkü parçalar ve Faz 4'ün dokunacağı yerler:

* **Defter** `services/defter.py`: `bakiye`, `hibe`, `rezerve` (atomik `UPDATE
  … WHERE bakiye >= :m`), `onayla`, `iade`, `duzelt`, `hibe_turu`,
  `tutarlilik`; anahtar biçimleri `rezerv:|onay:|iade:<is_id>`,
  `hibe:<u>:<YYYY-MM>`, `duzeltme:<uuid>` (`ONEK_*`, regex bekçisi
  `tests/test_defter.py:52,173`); `HAREKET_TURLERI` **6** (`hibe, rezerv, onay,
  iade, duzeltme, sona_erme`; `services/tablolar.py:173`) ↔ CHECK
  `tur_kumesi` (`:674`) — `paket` yok; `sona_erme` hiç YAZILMIYOR (Faz 3 `:501-503`).
  Tek yazar AST bekçisi: `kullanicilar.bakiye`ye UPDATE kuran yalnız `defter.py`.
* **Planlar** `services/planlar.py`: `Plan(ad, aylik_hibe, filigran, video,
  fiyat=None)`, `PLANLAR` üç plan, `free_aylik_hibe()` `KROMIS_FREE_AYLIK_HIBE`
  (boş = 200, 0 = kapalı, bozuk = `ValueError`); `PLANLAR.keys() ==
  tablolar.PLANLAR_KUMESI` bekçili; `temel`/`pro` hibe **1.000 / 3.000 yer
  tutucu**. Plan yazan tek yol `POST /api/admin/kullanicilar/{id}/plan`
  (`depo_admin.plan_yaz`).
* **Kapılar** `services/kapilar.py`: `check_plan` (403 `err.plan_kapsamiyor`,
  zincirin başı), `check_bakiye` (402 ön denetim), `rezerve_kredi` (atomik,
  `kuyruk.ekle` ile aynı transaksiyon); `kullanici_plani`. `GET /api/kredi`
  (`routers/isler.py:168`) `{bakiye, plan, hibe, sonraki_hibe, filigran, video,
  son_hareketler}`; ön yüz `core.js krediDurumu/krediYenile`, `settings.js`
  "Kredi" bölmesi (`KREDI_HAREKET_ANAHTARI` altı türün hepsi — bekçi testi,
  `paket` gelince yedinci satır), 403 toast'ında satış bağlantısı BİLEREK BOŞ
  (Faz 3 / 6 `:943`).
* **Hesap** `kullanicilar.silindi_at` yer tutucu (Faz 1; bugün `services/hesap.py`
  ve `depo_admin.py` yalnız `IS NULL` süzer, YAZAN yok); hesap silme rotası
  yok; dışa aktarma yalnız galeri ZIP'i (`depo_klasor.zip_disa_aktar`,
  `routers/galeri.py:113`). Oturumsuz yazan rota deseni: `routers/hesap.py`
  `kayit` → `_ilk_hibe` `kiraci.baglam(kullanici_id=…)` (Faz 3 / 3 sapma g).
* **Tablolar/RLS bekçileri** `tests/test_tablolar.py`: `HESAP_TABLOLARI` 4,
  `ALTYAPI_TABLOLARI = {"isciler"}` (`:55`), `IS_TABLOLARI` 9, **14 tablo**;
  üç belge çapası regex ile (`:126-160`; bu belge dördüncü çapayı verir).
  `tests/test_rls.py` 28 politika; `tools/rls_kontrol.py` `beklenen_politika()`.
* **Katalog** `catalog.py`: `openai-gpt-image-1` girdisi (`:588-602`) — yorum
  `gpt-image-1` 23 Ekim 2026, `gpt-image-1.5`/`-mini` 1 Aralık 2026 (`:538-539`);
  `KREDI_USD_CAPASI = 0.005` (`:464`); `tools/tarife_kontrol.py` TAM DÖRT
  "fiyat doğrulanamadı" modeli basar (bekçi `tests/test_araclar.py`).
* **Dış ağ:** web süreci sağlayıcılara `httpx` ile çıkar; Polar API'si yeni
  bir dış konak (`api.polar.sh` / `sandbox-api.polar.sh` — doğrulanmadı,
  aşağıda). Webhook alan uç yeni bir GİRİŞ yolu: oturumsuz, imzalı.
* **Belgeler:** KURULUM.md web bölümü **10 adım** (`:259` "Planlar ve kredi");
  `docs/isletme.md:200-201` "kredi defterinin hesap silmede kaderi — Faz 4",
  `:329` "ödeyen kullanıcı gelince (Faz 4) ikinci kova açılır"; `.env.example`
  1. bölüm ↔ `ALTYAPI` (`tests/test_docker_kapisi.py`) birebir.

---

## Polar — ne bildiğimiz, ne doğrulayamadığımız (2026-09-21)

`polar.sh` bu oturumun ağ proxy'sinden **erişilemedi** (egress engeli); aşağıdaki
olgular master design'ın 2026-09-18 notu (`:193-204`, sahibin araştırması) ve
üçüncü taraf özetlerinden (2026 tarihli) derlendi. **Her satır 3. görevin ilk
adımında Polar'ın kendi belgesiyle doğrulanır**; farklıysa bu belgeye "sapma"
yazılır, kod belgeye değil Polar'a uyar.

| konu | bildiğimiz | kaynak / durum |
| --- | --- | --- |
| Rol | Merchant of Record: satıcı Polar, dünya çapında KDV/VAT/GST hesaplar-beyan eder, faturayı son kullanıcıya keser, bize net ödeme; biz Polar'a tek hizmet ihracı faturası | master `:184-189`; [polar.sh/docs/merchant-of-record/fees](https://polar.sh/docs/merchant-of-record/fees) (erişilemedi) |
| Ücret — Starter (ücretsiz plan) | **%5 + 0,50 USD** / işlem; uluslararası kart **+%1,5**; dispute **15 USD**; payout ayda 2 USD + %0,25 + 0,25 USD; USD dışı payout'ta %0,25–1 kur farkı | master `:193` (%5 + 50¢, +%1,5, $15); ikincil: paritydeals.com, dodopayments.com "Polar.sh Review 2026", makerkit.dev fiyat hesaplayıcısı (2026) — **payout ve kur satırları doğrulanmadı** |
| Ücret — Pro | **20 USD/ay, %3,8 + 0,40 USD**; Growth 100 USD/ay %3,6 + 0,35; Scale 400 USD/ay %3,4 + 0,30; 2026-05-27 öncesi kuruluşlar "Early Member" %4 + 0,40 (+%0,5 abonelik) | master `:197` ("~1.000 USD/ay ciro üstünde Pro ucuzlar"); ikincil kaynaklar 2026 — **doğrulanmadı** |
| Türkiye'ye ödeme | Stripe Connect Express ile TR'ye payout | master `:194` |
| Ürünler | tek seferlik ürün (paket) ve abonelik (aylık/yıllık); ürün `metadata` taşır; fiyat Polar'da | master `:195-196`; ikincil |
| Checkout | `POST /v1/checkouts/` → barındırılan ödeme sayfası URL'si; alanlar `products`, **`external_customer_id`** (eski `customer_external_id` KULLANIMDAN KALDIRILDI — API changelog), `customer_email`, `metadata`, `success_url` | polar.sh/docs/changelog/api (arama özeti) — **alan adları 3. görevde doğrulanır** |
| Müşteri | `external_id` = bizim `kullanicilar.id`; Customer Session API → **müşteri portalı** bağlantısı (abonelik iptali, kart güncelleme, fatura indirme Polar'da) | ikincil (hookdeck, better-auth eklentisi) |
| Webhook | **Standard Webhooks**: başlıklar `webhook-id`, `webhook-timestamp`, `webhook-signature` (HMAC-SHA256 base64, `{id}.{timestamp}.{body}`); Python SDK `polar_sdk.webhooks.validate_event(payload, headers, secret)` → `WebhookVerificationError`; bilinmeyen tür `WebhookUnknownTypeError` (imza doğrulandıktan sonra); başarısız teslimat **üstel geri çekilmeyle saatlerce yeniden denenir**, aynı olay birden çok kez GELEBİLİR | hookdeck.com "Polar webhooks" (2026), github.com/polarsource/polar-python; Standard Webhooks spec: `webhook-id` yeniden gönderimde AYNI kalır |
| Olay türleri | `checkout.created/updated`, **`order.paid`**, `order.created/updated/refunded`, **`subscription.created/active/updated/canceled/uncanceled/revoked`**, `customer.created/updated/deleted`, **`customer.state_changed`** (bütün durumun tek özeti), `benefit_grant.created/revoked/cycled` | polar.sh/docs/integrate/webhooks/events (erişilemedi); ikincil özetler |
| `order.paid` alanları | `billing_reason` = `purchase` \| `subscription_create` \| `subscription_cycle` \| `subscription_update` (K6 bunu okur); `product_id`, `customer.external_id`, `subscription_id`, `amount`, `currency`, `metadata` | SDK modelinden bilinen adlar — **doğrulanmadı** |
| Sandbox | `sandbox.polar.sh` ayrı ortam, ayrı jeton ve webhook sırrı; SDK `server="sandbox"`; test kartıyla gerçek para yok | ikincil (encore.dev, opensaas.sh) |
| Kabul edilebilir kullanım | AI üretim araçları "ek incelemeye tabi"; NSFW, deepfake/face swap, ses klonlama, telif/marka ihlali YASAK — kullanım şartlarına ve moderasyona yazılmadan yayına çıkılmaz | master `:201-204` |
| Python SDK | `polar-sdk` (PyPI; `polarsource/polar-python`), Pydantic modelleri, senkron + async istemci | github (arama) — sürüm pini 3. görevde |

**Ücretin fiyata etkisi (K5'in hesabı):** Starter'da 9 USD'lik bir aboneliğin
ücreti 0,45 + 0,50 (+ 0,135 uluslararası kart) ≈ **1,09 USD (%12)**; 4 USD'lik
bir paketin ücreti 0,20 + 0,50 + 0,06 ≈ **0,76 USD (%19)**. Sabit 0,50 USD
küçük paketleri pahalı kılıyor → en küçük paket **≥ 5 USD** (öneri). Tarife
çapası 1 kredi ≈ 0,005 USD SAĞLAYICI maliyeti (`catalog.py:464`); bir planın
"tam kullanımda maliyeti" = hibe × 0,005.

---

## Envanter: bugünkü parçalar → Faz 4 parçaları

Adlar ÖNERİ (Türkçe, ASCII: `services/polar.py`, `services/odeme.py`,
`routers/odeme.py`, `urunler`, `siparisler`, `odeme_olaylari`); her satır hangi
görevde değiştiğini söylüyor.

| bugün | nerede | Faz 4'te | görev |
| --- | --- | --- | --- |
| `openai-gpt-image-1` katalogda; 4 fiyat "doğrulanamadı"; 7 kredi ≠ maliyet | `catalog.py:588-602`; `tools/tarife_kontrol.py` | Girdi kaldırılır (2026-10-23 öncesi) — ✅ 1; dört fiyat sahibin doğrulamasıyla kapanır, yedi kredi düzeltilir, `tarife_kontrol` bekçisi 4 → 0 — sahip henüz doğrulamadı, **1b'ye devredildi** | 1, 1b |
| Katalog **9 görsel** (`azure`, `openai`, `gemini`, `azure-mai`, `azure-flux`) + **6 video** (`gemini`, `fal`); ücretsiz plana 1 kredilik model yok; `emeklilik` alanı yok | `catalog.py` `IMAGE_MODELS`/`VIDEO_MODELS`; `*_client.py` adaptörleri | ~10 görsel + ~10 video, popüler/kaliteli → ucuz sırasıyla, sağlayıcıdan bağımsız (fal, Runware, Azure, OpenAI, Google …); kredi = maliyet × marj (araştırma yöntemi); eksik adaptör eklenir; `emeklilik: date` + `tarife_kontrol` "30 gün" satırı | 1b |
| `HAREKET_TURLERI` 6, `sona_erme` yazılmıyor; tek kova `bakiye` | `tablolar.py:173`; `defter.py` | `paket` türü (7); `kova` sütunu (`hibe`/`paket`); `kullanicilar.paket_bakiye`; `rezerve` iki kovadan tek UPDATE; `sona_erme` düşürmede yazılır | 2 |
| Defter anahtarları `rezerv: onay: iade: hibe: duzeltme:` | `defter.ONEK_*` | + `paket:` (`paket:<polar_order_id>`), `hibe:` Polar dönemi için `hibe:<u>:polar:<order_id>` | 2, 3 |
| `Plan.fiyat None`; `temel`/`pro` hibe yer tutucu | `services/planlar.py` | Hibe ortamdan (`KROMIS_TEMEL_AYLIK_HIBE`, `KROMIS_PRO_AYLIK_HIBE`); fiyat ve Polar ürün id'si `urunler` tablosunda (Polar'ın aynası, `tools/polar_esitle.py`) — `planlar` tablosu YOK (K5) | 2, 4 |
| Plan yazan tek yol admin rotası | `routers/admin.py:130` | + webhook (`subscription.*`) `odeme.plan_uygula`; admin rotası kalır (destek, deneme hesabı) | 3 |
| Bakiyeye para girişi: hibe + `duzeltme` | `defter.hibe/duzelt` | + `defter.paket_yukle` (webhook `order.paid`, admin bağlamı `yonetici_ekler`) | 2, 3 |
| Webhook yok; dış ağ yalnız sağlayıcılara | — | `POST /api/odeme/webhook` (oturumsuz, Standard Webhooks imzası); `odeme_olaylari` (webhook-id UNIQUE) | 3 |
| Satış yüzü yok; 403 toast bağlantısı boş; "Kredi" bölmesi tek bakiye | `static/core.js`, `settings.js` | `/planlar` sayfası; `POST /api/odeme/checkout`; `GET /api/odeme/portal`; "Kredi" bölmesinde iki kova + "satın al" + "aboneliği yönet" + siparişler; toast → `/planlar` | 4 |
| `silindi_at` yer tutucu; silme rotası yok | `tablolar.py:289` | `POST /api/hesap/sil` → anonimleştir + kilitle; bakım turu 7 gün sonra içeriği ve R2 nesnelerini siler; defter KALIR (K9) | 5 |
| Dışa aktarma yalnız galeri ZIP'i | `routers/galeri.py:113` | `GET /api/hesap/disa-aktar` → ZIP (profil, hareketler, siparişler, işler JSON/CSV); medya için mevcut galeri ZIP'i | 5 |
| Hukuki metin yok; kayıtta onay yok | `routers/hesap.py kayit` | `bundled/hukuk/*.html` → `GET /hukuk/{slug}`; kayıtta onay kutusu → `sartlar_kabul_at`/`sartlar_surumu`; footer bağlantıları | 6 |
| `isletme.md` "defterin kaderi Faz 4", "ikinci kova Faz 4"; KURULUM 10 adım | `docs/isletme.md:200,329`; `KURULUM.md:259` | § kapanır; KURULUM **11. adım "Ödeme (Polar)"** + canlı kontrol listesi (sandbox → production); ikinci kova açılır | 7 |

---

## 1. Katalog hijyeni — `gpt-image-1` emekliliği, dört Azure fiyatı, yedi kredi ≠ maliyet ✅ (PR: `faz4/katalog-hijyeni`)

**Kapsam.** Faz 3'ün "açık kalemler"inden ikisi (`:1160-1163`), ödemeden
BAĞIMSIZ ve takvimli: para almaya başlamadan tarifenin doğru olması gerekir,
yanlış krediyle satılan paket sonradan düzeltilemez (geçmiş kayıt retroaktif
yazılmaz, `catalog.py:460-465`).

* **`openai-gpt-image-1` katalogdan ÇIKAR** (`catalog.py:588-602`; kaynak:
  OpenAI duyurusu, `catalog.py:538-539` yorumu — 23 Ekim 2026). "Ölü girdi
  seçilebilir bir 404'tür" (araştırma artifact'ı). Dokunulan: `catalog.py`,
  `bundled/i18n/{tr,en}.json` (`model.openai-gpt-image-1.*` anahtarları — i18n
  bekçisi kullanılmayan anahtarı reddeder), `tests/test_catalog.py`,
  `tests/test_openai_client.py`, `tests/test_index.py`, `tests/test_chat_prompt.py`
  (girdiye adıyla değen iddialar). Eski `medya`/`isler` satırları `model` dizesini
  taşımaya devam eder (silinmez; yeniden gönderim "katalogdan düşmüş model"
  dalına düşer — Faz 3 / 3 sapma i). **`gpt-image-1.5` ve `gpt-image-1-mini`
  1 Aralık 2026** — bu PR onları KALDIRMAZ (henüz iki ay var), kataloğa
  `emeklilik: date` alanı ekler ve `tools/tarife_kontrol.py` "30 gün içinde
  emekli olacak model" satırı basar (bekçi: bugün 0 satır; 2026-11-01'den
  itibaren 2 — test tarihi yamalar, sabit tarih zaman bombası olmaz — Faz 2 / 9
  dersi).
* **Dört Azure fiyatı** (`tarife_kontrol` çıktısı: `azure-mai-image-2-6` 8 kr,
  `azure-mai-image-2-6-flash` 4 kr, `azure-flux-2-pro` 16 kr, `azure-flux-2-flex`
  10 kr / 6-10-16): **sahip Azure Foundry fiyat sayfasından doğrular** (bu
  oturumların ağından Azure sayfası JS ile çiziliyor, okunamıyor — araştırma
  artifact'ı). Doğrulanan fiyat yorumdan "doğrulanamadı" sözcüğünü düşürür,
  farklıysa `credits` değişir. **Bekçi:** `tests/test_araclar.py` "tam dört
  model" → **"tam sıfır"** (liste elle değil katalogdan; CLAUDE.md § 5).
* **Yedi kredi ≠ maliyet** (araştırma artifact'ı, 2026-09-20; Jul–Sep 2026
  fiyat izleyicileri): `azure-gpt-image-2 high` 16 → **25-42** (maliyet
  0,125-0,211 USD, düşük fiyatlı ×1,6-2,6), `gemini-nano-banana-2` 1K/2K/4K
  6/6/12 → **13/20/30** (düşük ×2-3), `azure-flux-2-pro` 16 → **6-8** (yüksek
  ×2,7), `gemini-veo-3-1-lite` 16 → **10**/sn, `gemini-veo-3-1-fast` 30 →
  **20**/sn, `azure-gpt-image-2 low` 1-2 (bant içinde, dokunma), `medium` 8
  (bant içinde 6-11, dokunma). **Sahip sağlayıcı sayfasıyla satır satır
  doğrular, PR sayıyı yazar**; doğrulanamayan satır yorumla kalır ve bekçi
  sayısına girer. Düşük fiyatlı ikisi (`gpt-image-2 high`, `nano-banana-2`)
  ÖNCELİKLİ: her iş platform zararı.
* **Retroaktif yok:** `medya.credits`, `isler.kredi_tahmini/kredi_gercek` eski
  değerle kalır; Marj raporu iki tarifeyi aynı tabloda gösterir (satırın
  tarihi belli). Bu PR'ın "Sahibin adımı" kod değil, fiyat sayfaları.

**Dokunulan.** `catalog.py`, `bundled/i18n/*`, `tools/tarife_kontrol.py`
(+emeklilik satırı), `tests/test_catalog.py`, `tests/test_araclar.py`
(dört → sıfır; emeklilik 0/2 tarih yamalı), `tests/test_openai_client.py`,
`tests/test_index.py`, `tests/test_chat_prompt.py`, `docs/graflar/*`.

**Risk.** Düşük-orta. Kredi artışı (`gpt-image-2 high` 16 → 25+) ücretsiz
kullanıcının 200 hibesini 8 → 5 görsele düşürür — ürün kararı, sahibin;
alternatif `high` kalitesini `free`ye kapatmak (`ImageModel.plan` alanı
NİHAYET veri olur: `plan="temel"` → `model_available` zaten okuyor). Kaldırılan
model bir kullanıcının kayıtlı tercihinde olabilir → ön yüz "katalogda yok"
dalı (Faz 1'den beri var, `secilecek`).

**Çıkış ölçütü.** `tarife_kontrol.py` boş liste; katalogda `gpt-image-1` yok;
`kredi × 0,005` her modelde araştırmanın "gerçek maliyet" bandının içinde ya da
yorumla gerekçeli; takım yeşil.

**Sahibin adımı — fiyat sayfaları (PR'dan önce).** Azure Foundry (MAI 2.6 /
Flash / FLUX.2 pro / flex), OpenAI (gpt-image-2 low/medium/high), Google
(Nano Banana 2 1K/2K/4K; Veo 3.1 lite/fast saniye), fal (FLUX.2 pro) fiyat
sayfalarından on bir sayı; PR onlarla yazılır.

**Yapıldığında (2026-09-21) ölçümler ve sapmalar.** Rota YOK (70), göç YOK,
modül 111. `openai-gpt-image-1` girdisi ve üstündeki "KATALOGDA KALIYOR ama
ÖMÜRLÜ" bloğu `catalog.py`den SİLİNDİ (`IMAGE_MODELS` 10 → **9**; yerine
neden silindiğini ve eski satırların kaderini söyleyen bir not — Gemini
girdisinin yorum bölgesine düşüyor, `fiyat` + `doğrulanamadı` çifti yok,
`tarife_kontrol` sayısı değişmedi); `gpt-image-2` bloğundaki tarih cümlesi ve
MAI bloğundaki "duruşu benimseniyor" yorumu silinen girdiye geçmiş zamanla
işaret eder. i18n **−1** tr/en (`model.openai-gpt-image-1.note`; bekçi
kullanılmayan anahtarı reddederdi). Testler: `test_openai_client.py` `MODEL`
artık `openai-gpt-image-2`, `IKINCI` katalogdan DEĞİL — gerçek girdinin
`dataclasses.replace` kopyası (`wire_model="gpt-image-sentetik"`): bu rol
`dall-e-3` ve `gpt-image-1` ile iki kez emekli oldu, üçüncüsü dosyaya
dokunmasın; "model katalogdan geliyor" iddiası uydurma adın tele aynen
çıkmasıyla ölçülüyor. `test_catalog.py` kısa etiket iddiası tekil örneğini
`gemini-nano-banana-2`ye taşıdı, iki docstring silinen girdiye geçmiş zamanla
değinir. **+1 test** `test_isler_route.py`: modeli katalogdan düşmüş `hata`
işi listede ve tekil uçta `model` dizesiyle durur, `yeniden` plan/anahtar
kapısını sormaz ve 202 döner (`spec is None` dalı; işçi tarafı `test_isci`
"bilinmeyen model"). Kod tarafında DEĞİŞİKLİK GEREKMEDİ: liste, tekil uç,
yeniden gönderim (`routers/isler.py`), işçi ve ön yüz (`secilecek`) katalogda
olmayan `model` dizesini zaten taşıyordu. `docs/ozellikler.md` sağlayıcı
satırı güncel; `static/index.html` / `test_index.py` / `test_chat_prompt.py` /
`GUNCELLEME.md` içindeki `gpt-image-1` geçişleri TARİHÇE (ekran okuyucu
örneği, sürüm notu, olgusal `input_fidelity` notu) — kalır. Takım **3.982 geçti, 12 atlandı, ~274 sn** (E2E + Postgres zorunlu; toplanan 3.999 → 3.994: `gpt-image-1` üzerinden parametrelenen 6 katalog testi düştü, 1 yeni test geldi — öncesi 3.987 / 12).

**Sapmalar — bilerek yapılmayanlar, gerekçesiyle.** (a) **Dört Azure fiyatı
ve yedi kredi ≠ maliyet DOKUNULMADI**: sahip fiyat sayfalarını henüz
doğrulamadı ("Sahibin adımı" yukarıda; bu oturumların ağından Azure/OpenAI/
Google/fal sayfaları okunamıyor) ve doğrulanmamış sayıyla `credits`
değiştirmek, düzeltmek istediğimiz kusurun kendisi (retroaktif yazılmaz,
`catalog.py:460-465`). `tools/tarife_kontrol.py` çıktısı ve bekçisi
(`tests/test_araclar.py`, TAM DÖRT model) AYNEN. Sahibin 2026-09-21
yönlendirmesi: Azure bundan sonra TEK ana sağlayıcı değil, tarife sağlayıcı
başına doğrulanır — bu yüzden fiyat/kredi düzeltmeleri yeni **1b** görevine
(katalog genişletme) devredildi; sahip doğruladığında orada, ya da 1b'den
önce ayrı küçük bir PR'da yazılır; bekçi 4 → 0 o PR'da. (b) **`emeklilik:
date` alanı ve `tarife_kontrol` "30 gün içinde emekli olacak model" satırı
YAPILMADI**: `gpt-image-1.5`/`-mini`nin girdisi zaten yok (yalnız yorumda
anılıyor), yani bugün işaretlenecek girdi de yok; alan katalog genişlerken
(1b) her yeni girdiyle birlikte gelir. (c) Bu PR'da **"Sahibin adımı" yok**:
fiyat sayfaları 1b'nin ön koşulu olarak duruyor. Çıkış ölçütünün
"`tarife_kontrol.py` boş liste" ve "`kredi × 0,005` bant içinde" maddeleri
1b'ye taşındı; "katalogda `gpt-image-1` yok; takım yeşil" karşılandı.

---

## 1b. Katalog genişletme — ~10 görsel + ~10 video model, sağlayıcıdan bağımsız (PR: `faz4/katalog-genisletme`)

**Kapsam.** Sahibin 2026-09-21 yönlendirmesiyle eklendi (1. görevin PR'ında;
sahip "olur onaylıyorum"): bugünkü katalog **9 görsel + 6 video** model ve
sağlayıcı ağırlığı Azure'da (5 girdi: `azure`, `azure-mai` × 3, `azure-flux`
× 2). Azure bundan sonra TEK ana sağlayıcı DEĞİL; katalog **sağlayıcıdan
bağımsız** büyür: en popüler / en kaliteli olandan daha ucuza doğru sıralı
**~10 görsel + ~10 video** model — fal, Runware, Azure AI Foundry, OpenAI,
Google ve sahibin adını vereceği başka sağlayıcılar. Ürün kararı sahibin,
sayı işi bu PR'ın:

* **Sahip listeyi verir** (sıralı: popülerlik/kalite → fiyat); her satır için
  bu PR **sağlayıcı**, **birim maliyet** (USD; kaynak + erişim tarihi
  yorumda — fiyat sayfası bu oturumların ağından okunamıyorsa sahibin verdiği
  sayı ve tarih), **kredi = maliyet × marj** (araştırma artifact'ının yöntemi:
  `KREDI_USD_CAPASI` 0,005 USD/kredi çapası, düşük fiyatlı model platform
  zararı — `claude.ai/artifact/GxN2FA5932GpJYGEgSiruL`), **plan kapsamı**
  (`free`/`temel`/`pro` — `planlar.kapsiyor`; `ImageModel.plan` alanı veri
  olur: ücretsiz plana 1 kredilik hızlı model — FLUX schnell / FLUX.2 klein
  fal ya da Runware'de — masada, Faz 3 araştırması), **yetenek jetonları**
  (boyut/oran, kalite, `max_n`, düzenleme, referans sayısı — doğrulanmamış
  jeton beyan edilmez: "seçilebilir bir 400" ilkesi, `catalog.py` gpt-image-2
  bloğu), **`emeklilik: date`** (1. görevden devir; boşsa yok) yazar.
  Filigran kuralı DEĞİŞMEZ (Faz 3 / 4: plan belirler, model değil).
* **Adaptörler yalnız eksikse genişler:** fal (`fal_client.py`), Azure
  (`azure_client.py`, `azure_mai_client.py`, `azure_flux_client.py`), OpenAI
  (`openai_client.py`), Gemini (`gemini_client.py`) var; **Runware** ya da
  başka yeni bir sağlayıcı gelirse yeni `*_client.py` + `CREDENTIALS` girdisi
  + `providers._resolve` dalı + `saglayici_meta.kaydet` (Faz 3 / 5 deseni) —
  Azure'a özel varsayım eklenmez, sağlayıcı verisi yan kanalda kalır.
  Kimlik/anahtar tarafı `credstore`/`platform_anahtari` mevcut deseniyle
  (platform anahtarı küme katalogdan türer).
* **1. görevden devredilenler:** dört Azure fiyatı (`azure-mai-image-2-6`,
  `-flash`, `azure-flux-2-pro`, `-flex`) ve yedi kredi ≠ maliyet satırı
  (`azure-gpt-image-2 high`, `gemini-nano-banana-2` 1K/2K/4K, `azure-flux-2-pro`,
  `gemini-veo-3-1-lite`, `-fast`) sahip doğruladığında bu PR'da kapanır:
  yorumdan "doğrulanamadı" düşer ya da `credits` değişir; **`tarife_kontrol`
  bekçisi 4 → 0** (`tests/test_araclar.py`, liste katalogdan). Sahip yalnız
  bir kısmını doğrularsa kalanlar yorumla ve bekçi sayısıyla kalır — sayı
  PR'da yazılır. `tarife_kontrol` "30 gün içinde emekli olacak model" satırı
  (bekçi tarih yamalı: bugün 0; `gpt-image-1.5`/`-mini` girdisi eklenirse
  2026-11-01'den itibaren 2).
* **Sıra ve varsayılan:** `IMAGE_MODELS`/`VIDEO_MODELS` sırası arayüz sırası
  ve ilk girdi varsayılan (`catalog.py` başlığı) — sahibin listesi bu sırayı
  belirler; `DEFAULT_IMAGE_MODEL` değişirse E2E çapaları ve `test_catalog`
  varsayılan iddiaları onunla.
* **Retroaktif yok** (1. görev aynen): eski `medya.credits`, `isler.kredi_*`
  eski tarifeyle kalır.

**Dokunulan.** `catalog.py` (+~15 girdi, `emeklilik` alanı, fiyat yorumları),
`bundled/i18n/{tr,en}.json` (`model.<id>.note` her girdi için, 20-110
karakter, adı tekrar etmez — `test_catalog` bekçileri), varsa yeni
`*_client.py` + `providers.py` + `tools/tarife_kontrol.py` (+emeklilik satırı),
`tests/test_catalog.py`, `tests/test_araclar.py` (4 → 0, emeklilik 0/2 tarih
yamalı), yeni adaptörün `tests/test_<saglayici>_client.py`,
`tests/test_playwright_*` model seçici çapaları (yalnız varsayılan değişirse),
`docs/ozellikler.md`, `README*.md` sağlayıcı satırı, `docs/graflar/*`.

**Testler / bekçiler.** Katalog bekçileri aynen (`test_catalog`: her girdinin
notu iki dilde var, adı tekrar etmiyor, jetonlar tutarlı, kısa etiket
çakışması); i18n eşliği (`test_i18n`: tr ↔ en aynı anahtar kümesi,
kullanılmayan anahtar yok); `tarife_kontrol` ↔ bağımsız tarama (0 ya da
kalan sayı); `emeklilik` bekçisi tarih yamalı; yeni adaptör için tel formatı +
hata çevirisi + `saglayici_meta` testi (Faz 3 / 5 deseni); E2E model seçici
(seçicide her `available` model bir satır; ücretsiz planın 1 kredilik modeli
varsa `free` E2E'si onunla); `kredi × 0,005` her girdide araştırmanın "gerçek
maliyet" bandında ya da yorumla gerekçeli.

**Risk.** Orta. Yeni sağlayıcı = yeni gizli anahtar + dış konak (`.env.example`
↔ `ALTYAPI` bekçisi, `tests/test_docker_kapisi.py`; Sentry/egress notu
`docs/isletme.md`); ~20 yeni satır seçicide kaydırma ve mobil düzen
(ölçülmedi — gerekirse sağlayıcıya göre gruplama, ayrı küçük PR);
düşük fiyatlı satır platform zararı — kredi hesabı yorumda kaynaklı olmak
zorunda.

**Çıkış ölçütü.** Katalog ~10 görsel + ~10 video, her girdide sağlayıcı,
kaynaklı maliyet ve kredi; `tarife_kontrol.py` boş (ya da sahibin
doğrulamadığı sayı PR'da yazılı); Azure'a özel varsayım yok (sağlayıcı verisi
yan kanalda, katalog satırı sağlayıcıyı `provider`/`credential` ile söylüyor);
i18n eşliği; takım yeşil (E2E dahil).

**Sahibin adımı — PR'dan önce.** (1) Sıralı model listesi (~10 görsel + ~10
video; her satırda sağlayıcı ve varsa tercih ettiği fiyat kaynağı); (2) 1.
görevden devreden on bir sayı (Azure Foundry MAI 2.6 / Flash / FLUX.2 pro /
flex; OpenAI gpt-image-2 low/medium/high; Google Nano Banana 2 1K/2K/4K, Veo
3.1 lite/fast saniye; fal FLUX.2 pro) — doğrulayabildiği kadarı; (3) yeni
sağlayıcı (Runware vb.) gelirse hesap + anahtar.

**Bağımlılıklar.** 1'den sonra (girdi silinmiş, yorumlar yerinde); 2-4'ten
BAĞIMSIZ — omurgayla paralel gidebilir; 7 (operasyon) bu görevin sağlayıcı
listesini KURULUM'a ve `isletme.md`ye yazar. Sahibin listesi gelmeden
başlamaz — yalnız 1. görevden devreden fiyat/kredi düzeltmeleri, sahip
doğruladığı anda ayrı küçük bir PR olarak öne alınabilir.

---

## 2. Ödeme şeması ve iki kova — `0008_odeme`, `kova`, `paket`, `urunler`/`siparisler`/`odeme_olaylari`, `defter` iki kova ✅ (PR: `faz4/odeme-semasi`)

**Kapsam.** Davranış DEĞİŞMEZ (webhook yok, rota yok); yalnız şema + defter
katmanı + bekçileri — Faz 3 / 1'in deseni. Göç **`0008_odeme`** — Faz 4'ün
TEK göçü (giriş).

* **`kredi_hareketleri`:** `kova text NOT NULL DEFAULT 'hibe' CHECK IN
  ('hibe','paket')` (`KOVALAR` sabiti); `tur` CHECK kümesi **+`paket`**
  (`HAREKET_TURLERI` 6 → **7**; bekçi `tur_kumesi` ↔ liste). Mevcut satırlar
  `hibe` kovasında kalır (bugüne kadar her satır hibe kovasıydı). İndeks
  değişmez.
* **`kullanicilar`:** `paket_bakiye int NOT NULL DEFAULT 0` (ikinci ÖNBELLEK;
  kaynak `SUM(miktar) WHERE kova='paket'`), `polar_musteri_id text NULL UNIQUE`,
  `polar_abonelik_id text NULL`, `plan_bitis timestamptz NULL` (iptal edilmiş
  aboneliğin dönem sonu — "dönem sonunda free"), `sartlar_kabul_at timestamptz
  NULL`, `sartlar_surumu text NULL` (6), `temizlendi_at timestamptz NULL` (5:
  içerik silindi damgası; `silindi_at` talep anı olur).
* **`urunler`** (ALTYAPI tablosu, kullanıcı satırı yok — `isciler` gibi):
  `id uuid`, `polar_urun_id text NOT NULL UNIQUE`, `tur text CHECK IN
  ('plan','paket')`, `plan text NULL CHECK IN PLANLAR_KUMESI` (tur=plan ise
  dolu), `kredi int NOT NULL` (paket: yüklenen kredi; plan: dönem hibesi —
  bilgi, kural `PLANLAR`da), `fiyat_kurus int NOT NULL`, `para_birimi text NOT
  NULL` (`usd`), `ad text NOT NULL`, `aktif bool NOT NULL DEFAULT true`,
  `guncellendi timestamptz`. Polar'ın **aynası**: yazarı `tools/polar_esitle.py`
  (4), okuyanı webhook (`product_id` → satır) ve satış sayfası. RLS YOK
  (herkese açık fiyat listesi; yazımı yalnız araç ve admin bağlamı).
* **`siparisler`** (İŞ tablosu, `kullanici_id` FK CASCADE → **`IS_TABLOLARI` 9
  → 10**): `id uuid`, `kullanici_id`, `polar_siparis_id text NOT NULL UNIQUE`,
  `polar_abonelik_id text NULL`, `urun_id uuid FK urunler`, `sebep text CHECK IN
  ('purchase','subscription_create','subscription_cycle','subscription_update')`
  (Polar `billing_reason` aynen — çeviri yok, sağlayıcı sözlüğü), `tutar_kurus
  int`, `para_birimi text`, `olusturuldu timestamptz`. RLS: `sahip` ALL +
  `yonetici_okur` + `yonetici_gunceller` + **`yonetici_ekler`** (webhook admin
  bağlamında yazar; `YONETICI_EKLER_TABLOLARI` 1 → 2) → politika 28 → **32**
  (3 × 10 + 2). Kullanıcı "Kredi" bölmesinde kendi siparişlerini görür, Polar
  faturasına oradan gider.
* **`odeme_olaylari`** (ALTYAPI tablosu): `id uuid`, `webhook_id text NOT NULL
  UNIQUE` (Standard Webhooks `webhook-id` — teslimat idempotency'si), `tur text`
  (`order.paid` …), `polar_nesne_id text NULL`, `kullanici_id uuid NULL FK SET
  NULL`, `govde jsonb NOT NULL` (redakte: `kuyruk._redakte` deseni — kart
  verisi zaten gelmez, e-posta/adres gelebilir), `alindi timestamptz`,
  `islendi_at timestamptz NULL`, `hata text NULL`. Saklama 1 yıl (K10; bakım
  turu siler). ALTYAPI_TABLOLARI `{isciler}` → `{isciler, urunler,
  odeme_olaylari}`; **tablo 14 → 17**.
* **`services/defter.py` iki kova (K3):**
  * `rezerve(db, u, is_id, m)` — TEK atomik UPDATE: `SET bakiye = bakiye -
    LEAST(bakiye, :m), paket_bakiye = paket_bakiye - (:m - LEAST(bakiye, :m))
    WHERE id = :u AND bakiye + paket_bakiye >= :m RETURNING …` (eski
    `bakiye`/`paket_bakiye` da döner → bölüşüm bilinir); 0 satır →
    `YetersizBakiye(toplam, gereken)`. Hibe kovası ÖNCE tükenir (devretmeyen
    önce — kullanıcı lehine). Satırlar: `rezerv:<is_id>` (kova hibe, hibeden
    düşen kadar) ve gerekirse `rezerv:<is_id>:paket` (kova paket). Eski
    anahtar biçimi korunur (bekçi regex'i `:paket` son ekini kabul eder).
  * `onayla`/`iade` — kovaya GERİ verir: fark önce paket kovasına (o en son
    düşmüştü), kalan hibe kovasına — "hibeden önce paketi geri koy" kuralı,
    böylece iade edilen paket kredisi devretmeyi sürdürür. Satır anahtarları
    `onay:<is_id>`/`onay:<is_id>:paket`, `iade:…` aynı deyim.
  * `paket_yukle(db, u, miktar, anahtar, aciklama, *, an=None) -> bool` —
    `tur='paket'`, `kova='paket'`, `ON CONFLICT DO NOTHING` (hibe'nin deseni);
    anahtar biçimi **`paket:<polar_order_id>`** (K4).
  * `dusur(db, u, hedef, anahtar, an)` — plan düşürmede hibe kovasını `hedef`e
    (yeni planın hibesi) indirir: `bakiye > hedef` ise `sona_erme` satırı
    `-(bakiye - hedef)`, kova hibe (Faz 3 `:501-503` "paketlerle gelirse
    anlam kazanır" — geldi). Paket kovasına DOKUNMAZ.
  * `hibe`/`hibe_turu`/`aylik_hibe_yaz` kova `hibe` aynen; `hibe_turu` yalnız
    **`free`** planı tarar (ücretli planların dönem hibesi webhook'la, K6) —
    `hibe:<u>:<YYYY-MM>` anahtarı ücretsizde aynen.
  * `duzelt` `kova` parametresi alır (öntanım `hibe`; admin "paket kredisi
    ekle" desteği için).
  * `tutarlilik` iki kovayı ayrı ölçer: `(u, bakiye, Σhibe, paket_bakiye,
    Σpaket)`; `defter.tutarsiz` uyarısı `kova` alanı taşır.
  * `bakiye(db, u)` → `Bakiye(hibe, paket, toplam)` (üç alan; okuyanlar
    `toplam` — 402 gövdesi `bakiye` = toplam kalır, `hibe`/`paket` eklenir).

**İki kova, tek tablo — FIFO satırları ya da Polar sayaçları DEĞİL (K3).**
Faz 3 K6 "tek kova + hibeye tamamla"yı seçmiş, kova ayrımını "paket gelince o
gün" demişti (`:1142-1145`). Paket geldi ve tek kova kırılıyor: 5.000 kredilik
paket almış kullanıcı `bakiye < hibe` koşulunu hiç sağlamaz, aylık hibesini
kaybeder; ya da hibe paketin üstüne biner, "devretmeyen hibe" boşa çıkar.
Ölçülen gerekçe iki önbellek sütunu lehine: (a) atomiklik Faz 3 K1'in aynı
UPDATE'inde kalır (`LEAST` ile bölüşüm tek ifadede, yarış Postgres'te); (b)
`tutarlilik` iki SUM'la ikisini de doğrular; (c) satır sayısı artmaz — iş
başına en fazla iki `rezerv` satırı, çoğu işte bir. Alternatif FIFO (her hibe
satırının son kullanma tarihi, tüketim en eskisinden): satır başına kalan
bakiye sütunu, ay sonu `sona_erme` turu, `tutarlilik`in tamamen yeniden
yazımı — bugün iki kova için fazla. Alternatif Polar Meter Credits (bakiye
Polar'da): defter tek gerçek ilkesini bozar (master `:205-208`), her rezerv bir
dış çağrı olurdu, BYOK/hibe/iade Polar'ın sözlüğünde yok.

**Dokunulan.** `services/tablolar.py` (+3 sınıf `Urun`, `Siparis`, `OdemeOlayi`;
`KrediHareketi.kova`; `Kullanici` +7 sütun; `HAREKET_TURLERI` 7, `KOVALAR`,
`SIPARIS_SEBEPLERI`, `URUN_TURLERI`), `services/kiraci.py` (`IS_TABLOLARI` 10,
`YONETICI_EKLER_TABLOLARI` 2), `alembic/versions/0008_odeme.py` (RLS literali
`TABLOLAR` 10 + `siparisler` dört politika), `services/defter.py` (iki kova;
`paket_yukle`, `dusur`, `Bakiye`, `ONEK_PAKET`), `services/kapilar.py` (402
gövdesi `hibe`/`paket` alanları), `routers/isler.py` (`/api/kredi` +`paket_bakiye`,
`toplam`, `plan_bitis`), `static/settings.js` (`KREDI_HAREKET_ANAHTARI` +`paket`
— bekçi testi yedi türü ister; iki kova satırı), `static/core.js` (`kalan M` =
toplam), `bundled/i18n/*` (+~4), `tools/rls_kontrol.py` (`beklenen_politika()`
3 × 10 + 2 = 32), `tests/test_tablolar.py` (`ALTYAPI_TABLOLARI` 3, `len ==
17`, bu belgeden DÖRDÜNCÜ çapa: "`IS_TABLOLARI` bekçi listesi 9 → 10:
`siparisler`", CHECK kümeleri), `tests/test_rls.py` (10 tablo; `siparisler`de
dört politika), `tests/test_rls_kontrol.py` (32), `tests/test_db.py`/`test_goc.py`/
`test_kuyruk.py` (`BAS` → `0008_odeme`), `tests/test_defter.py` (+~25: iki
kovadan rezerv bölüşümü 3 durum — yalnız hibe / hibe + paket / yalnız paket;
yetersiz toplam; onay farkı önce pakete; iade iki satırı da geri koyar;
`paket_yukle` idempotent; `dusur` `sona_erme` yalnız hibe kovasında; iki kova
`tutarlilik`; eş zamanlı rezerv iki kovada 100 tekrar çift düşüm 0; anahtar
regex'i `:paket` son eki), `tests/test_kredi_route.py` (+alanlar),
`tests/test_galeri_db.py` (`DEPOLAR["services/defter.py"]` sayısı; `KIRACISIZ`
+`paket_yukle`/`dusur` gerekçesiyle — webhook admin bağlamı), `docs/graflar/*`.
Rota YOK, davranış değişikliği YOK (kimse `paket` yazmıyor; `dusur` çağrılmıyor).

**Risk.** Düşük-orta. Geri dönüşsüz adlar: `kova`, `paket:<order_id>`,
`siparisler.sebep` = Polar `billing_reason` literalleri. İki önbellek iki
tutarlılık borcu — `tutarlilik` ikisini de ölçer. `hibe_turu`nun ücretli planı
atlaması: 3 gelmeden `pro` yapılan sahibin hesabı bir daha hibe ALMAZ (bugün
3.000'e tamamlanıyordu) — sahibin adımı: 2 ile 3 tek dağıtım penceresinde, ya da
2'de geçici olarak eski davranış korunur (ortam bayrağı `KROMIS_UCRETLI_HIBE_BAKIMDA=1`,
3'te kaldırılır). **Öneri: bayrak** — 2 tek başına canlıya çıkabilir.

**Çıkış ölçütü.** `alembic upgrade head && downgrade base && upgrade head` temiz,
`alembic check` boş; **17 tablo**, `IS_TABLOLARI` 10, politika 32; iki kova
rezerv testi 100 tekrar çift düşüm 0; `SUM(kova=hibe) == bakiye` ve
`SUM(kova=paket) == paket_bakiye` bakım turunda; takım yeşil.

**Sahibin adımı — yok** (göç dağıtım öncesi komutta). *Yapıldığında eklendi:*
2 canlıya 3'ten ÖNCE çıkarsa işçinin ortamına `KROMIS_UCRETLI_HIBE_BAKIMDA=1`
(aşağıda), 3 ile birlikte silinir.

**Yapıldığında (2026-09-21) ölçümler ve sapmalar.** Rota YOK (70), göç
**`0008_odeme`** (şema başı `0007_kredi` → `0008_odeme`; ileri-geri-ileri +
`alembic check` temiz), modül 111, **17 tablo**, `IS_TABLOLARI` **10**,
`ALTYAPI_TABLOLARI` **3** (`isciler`, `urunler`, `odeme_olaylari`),
`YONETICI_EKLER_TABLOLARI` **2**, RLS politikası **32**, `HAREKET_TURLERI` **7**,
`KOVALAR`/`URUN_TURLERI`/`SIPARIS_SEBEPLERI` CHECK'li ve bekçili (her üye
yazılır, dışı reddedilir; `urunler` ayrıca `tur_plan_uyumu`: plan ürünü
plansız, paket ürünü planlı olamaz). `DEPOLAR["services/defter.py"]` 8 → **10**
(+`plan_bitis_oku`, +`dusur`; `rezerve` artık `select/update` çağrısı değil ham
CTE — sayılmaz). i18n **+2** tr/en (`kredi.tur_paket`, `kredi.kova_satiri`),
`.env.example` **+3** (`KROMIS_TEMEL_AYLIK_HIBE`, `KROMIS_PRO_AYLIK_HIBE`,
`KROMIS_UCRETLI_HIBE_BAKIMDA` — `ALTYAPI` bekçisi 3 ad). Gemiye binen API:
`defter.bakiye(db, u) -> Bakiye(hibe, paket, toplam)`; `defter.rezerve` tek
ifade (aşağıda), ana satır + gerekirse `:paket` satırı; `defter.onayla`/`iade`
kova kova, fark ÖNCE pakete; `defter.paket_yukle(db, u, miktar, anahtar,
aciklama=None, *, an=None) -> bool` (`paket:<order_id>`); `defter.dusur(db, u,
hedef, anahtar, *, an=None) -> Hareket | None` (`sona_erme`, yalnız hibe kovası,
`FOR UPDATE`); `defter.duzelt(..., kova="hibe")`; `defter.tutarlilik(db) ->
list[Sapma(kullanici_id, bakiye, hibe_toplam, paket_bakiye, paket_toplam)]`
(NamedTuple; bakım turu sapan her kova için `defter.tutarsiz` uyarısına `kova`
alanı ekler); `defter.plan_bitis_oku`; `YetersizBakiye(toplam, gereken, *,
hibe, paket)` — `bakiye` alanı toplam; 402 gövdesi `bakiye` (toplam) + `hibe`
+ `paket`; `GET /api/kredi` `bakiye` HİBE kovası olarak kalır (Faz 3'ün alanı,
sütunla aynı anlam) + `paket_bakiye`, `toplam`, `plan_bitis` (bugün `null`),
hareket dökümünde `kova`; composer "kalan" ve bölmenin büyük sayısı `toplam`,
bölmede "Aylık hibe: N · paket kredisi: M" satırı; admin "kredi ekle" cevabı
hibe kovası (listenin `bakiye` sütunuyla aynı). `planlar.py`: `aylik_hibe(ad,
varsayilan, ortam)`, `TEMEL/PRO_AYLIK_HIBE_ENV` (boş = 1.000 / 3.000 — K5'in
1.200 / 4.500'ü sahibin 4. görevde ürünleri yazarken vereceği sayı),
`ucretli_hibe_bakimda()` (`1`/boş/`0`, başka değer `ValueError`; işçi
açılışta doğrular, `isci.py hazirla`). `hibe_turu` bayrak kapalıyken YALNIZ
`free`; paket kovası hesaba girmez (paketli kullanıcı hibesini kaybetmez).
`0008` downgrade `kova`/`tur = 'paket'` satırı varsa `RuntimeError` ile DURUR
(test çivili). Testler **+~30**: iki kovadan rezerv bölüşümü 5 durum
(parametreli), toplam yetersiz, aynı işi iki kez rezerv iki kovayı geri koyar,
onay farkı 6 durum (önce paket), iade iki satır, `paket_yukle` idempotent,
`dusur`, `duzelt(kova)`, iki kova `tutarlilik`, eş zamanlı iki kova 100 tekrar
çift düşüm 0, anahtar regex'leri (`:paket`, `paket:`, `sona_erme:`, `hibe:…:polar:`),
`hibe_turu` paket kovasını görmez, downgrade kapısı; RLS `siparisler` dört
politika + admin ekler/silemez, kullanıcı başkasınınkini ne okur ne ekler,
`urunler` bağlamsız okunur; `/api/kredi` iki kova; bayrak; env değişkenleri.
Takım sayısı PR gövdesinde.

**Sapmalar — belgeden farklı yapılanlar, gerekçesiyle.** (a) **`paket_yukle`/
`dusur` `KIRACISIZ` defterinde DEĞİL**: belge "webhook admin bağlamı"
gerekçesiyle oraya yazmıştı, ama imza bekçisi (tests/test_galeri_db.py)
kiracısız işlevin `kullanici_id` ALMAMASINI ister ve ikisi de hedef kullanıcıyı
alır — `hibe` gibi kullanıcı imzalı `(db, kullanici_id, …)`, sahip süzgeci
`_sahibin`; çağıran (webhook, 3) admin bağlamında koşar ve kullanıcıyı olaydan
çözüp verir. (b) **`rezerve` `RETURNING eski.bakiye` yerine CTE + `SELECT …
FOR UPDATE`**: `RETURNING` yalnız YENİ satırı verir (PG 18'in `RETURNING OLD`ı
test kümesinin PG 16'sında yok) ve yeni değerlerden bölüşüm çıkmaz (hibe 0'a
inmişse hibeden ne düştüğü bilinmez); CTE aynı satırı kilitler, son commit
edilmiş değeri döner, UPDATE aynı kilitli satırı bölüşür — yine TEK gidiş-dönüş,
yarış testi (100 tekrar) yeşil. (c) **Ana satırın kovası**: belge "`rezerv:<is_id>`
kova hibe, hibeden düşen kadar" demişti; iş TAMAMEN paketten düştüyse
(hibe kovası boş) ana satır PAKET kovasında yazılır, sıfır miktarlı hibe satırı
("rezerv +0") yazılmaz — hareket listesinde anlamsız kayıt olurdu; `onay`/`iade`
aynı kural (`_iki_satir`). (d) **`Bakiye.toplam` alan, özellik değil**: imza
bekçisi sınıf gövdesindeki açık `def`i tarar. (e) **`tutarlilik` `Sapma`
NamedTuple** (belgenin 5'li demeti, adlı); bakım turu kova başına uyarı.
(f) **`GET /api/kredi` `bakiye` = hibe kovası** (belge "`bakiye` = toplam
kalır" 402 gövdesi için demişti, `/api/kredi` için `toplam` alanını ayrı
saymıştı — ikisi de öyle): alanın anlamı `kullanicilar.bakiye` sütunuyla aynı
kaldı, toplam kendi adıyla geldi. (g) **`siparisler.urun_id` NOT NULL, FK NO
ACTION**: ürünü aynada olmayan sipariş işlenmez (`hata='urun_yok'`, 3), ürün
satırı silinmez (`aktif=false`) — belge yalnız "FK urunler" demişti. (h)
**`odeme_olaylari`ya `alindi` indeksi**: 1 yıllık saklama turu (7) tarih
tarar. (i) **test_rls iş tablosu türetimi NOT NULL `kullanici_id`**:
`odeme_olaylari.kullanici_id` NULL'lanabilir (sahibi olmayan olay) — eski
türetim onu iş tablosu sayardı. (j) **`KROMIS_TEMEL/PRO_AYLIK_HIBE` bu
görevde** (belge "2, 4" demişti; `.env.example` bekçisi kod okuyor → şablon
aynı PR'da). (k) **`hibe_turu` bayrağı öntanımlı KAPALI** ve işçi açılışta
doğrular: yanlışlıkla çift hibe yerine yanlışlıkla eksik hibe — ilki para,
ikincisi bir ortam değişkeni (`.env.example` açıklaması). (l) i18n +2, ~4
değil: iki kova satırı tek anahtar. Belgenin kalan cümleleri aynen uygulandı.

---

## 3. Polar webhook ve olay işleme — `services/polar.py`, `services/odeme.py`, `POST /api/odeme/webhook` (PR: `faz4/polar-webhook`)

**Kapsam.** Para bu görevden sonra DEFTERE GİRER: Polar "ödendi" der, biz
paket yükler ya da planı yazarız. Satış yüzü yok (4); sandbox'ta elle checkout
ile ölçülür.

* **`services/polar.py`** — SDK sarmalı, konuşmaz: `istemci()` (`polar-sdk`;
  `KROMIS_POLAR_ORTAM` `sandbox`|`production`, **boş = sandbox** — yanlışlıkla
  canlıya bağlanmak yerine yanlışlıkla sandbox'a bağlanılır, ilk canlı
  denemede fark edilir), `KROMIS_POLAR_ERISIM_JETONU` (organizasyon erişim
  jetonu), `KROMIS_POLAR_WEBHOOK_SIRRI`. İşlevler: `olay_dogrula(govde: bytes,
  basliklar) -> Olay` (`validate_event`; imza hatası → `ImzaHatasi`; bilinmeyen
  tür → `Olay(tur, veri=None)` — 200 dön, kaydet, işleme), `checkout_ac(...)`
  (4), `portal_baglantisi(...)` (4), `urunler()` (4), `abonelik_iptal(id)` (5).
  Testlerde SDK YAMALI; imza testi gerçek HMAC (sır sabit `DUMMY`li — gitleaks
  dersi, Faz 2 / 9).
* **`services/odeme.py`** — olayı deftere/plana çeviren TEK yer (depo
  sözleşmesi `(db, …)`; kiracısız — `KIRACISIZ` defterine gerekçesiyle: "webhook
  oturumsuz, admin bağlamında yazar, hedef kullanıcı olaydan çözülür"):
  * `olayi_kaydet(db, olay) -> bool` — `odeme_olaylari` `INSERT … ON CONFLICT
    (webhook_id) DO NOTHING`; `False` = çoktan alındı → rota **200, işleme
    yok** (teslimat idempotency'si; Polar yeniden gönderir, `webhook-id` aynı).
  * `kullaniciyi_coz(db, olay) -> Kullanici | None` — `customer.external_id`
    (= `kullanicilar.id`), yoksa `metadata.kullanici_id`, yoksa
    `polar_musteri_id`; bulunamazsa olay `hata='kullanici_yok'` ile kaydedilir,
    200 (Polar'a 5xx dönmek yeniden denemeyi tetikler, kullanıcı hiç yoksa
    faydasız — admin listesinde görünür, 7).
  * `order_paid(db, k, siparis)` — `urunler`den ürünü bul (`product_id`;
    bilinmiyorsa `hata='urun_yok'`, 200 — sahibin `polar_esitle` koşması
    gerekir). `sebep == 'purchase'` ve `urun.tur == 'paket'` →
    `defter.paket_yukle(k.id, urun.kredi, anahtar=f"paket:{order_id}")` (K4);
    `sebep in (subscription_create, subscription_cycle, subscription_update)`
    ve `urun.tur == 'plan'` → `plan_uygula` + **dönem hibesi** "hibeye tamamla":
    `bakiye < PLANLAR[plan].aylik_hibe` ise `defter.hibe(k.id, fark,
    anahtar=f"hibe:{k.id}:polar:{order_id}")` (K6). Her durumda `siparisler`
    satırı (`polar_siparis_id` UNIQUE — ikinci koruma). Hepsi TEK transaksiyon
    (`olayi_kaydet` → işle → `islendi_at`; düşerse olay satırı `hata` ile
    kalır, rota 500 → Polar yeniden dener → `ON CONFLICT` bu kez `False`…
    **DİKKAT:** o yüzden `olayi_kaydet` ile işleme AYNI transaksiyonda; hata
    ikisini de geri alır, yeniden deneme temiz gelir).
  * `plan_uygula(db, k, plan, *, abonelik_id, plan_bitis=None)` — `kullanicilar.plan`
    (hesap tablosu, RLS dışı; `depo_admin.plan_yaz`in deseni), `polar_abonelik_id`,
    `plan_bitis`. Yükseltme (`free → temel/pro`, `temel → pro`): hibe kovası
    yeni hibeye tamamlanır (order.paid zaten yapar). Düşürme (`pro → temel`
    `subscription.updated`; `→ free` `subscription.revoked`): `defter.dusur(k.id,
    hedef=PLANLAR[yeni].aylik_hibe, anahtar=f"sona_erme:{k.id}:{abonelik_id}:{an:%Y-%m-%d}")`
    — paket kovası dokunulmaz.
  * `subscription_canceled` → yalnız `plan_bitis = current_period_end` (plan
    KALIR — kullanıcı ödediği dönemi kullanır; Polar `cancel_at_period_end`);
    `subscription_uncanceled` → `plan_bitis NULL`; **`subscription_revoked`**
    (dönem bitti ya da ödeme başarısız dunning sonu) → `plan_uygula(free)` +
    `dusur`. `subscription.active` yeni abonelikte `order.paid`in ikizi —
    ikisi de gelir; plan yazımı idempotent (aynı değer), hibe `order_id`
    anahtarlı (bir kez).
  * `customer.created/updated` → `polar_musteri_id`. `order.refunded` →
    **manuel**: olay kaydedilir, `olay=odeme.iade` WARNING; kredi geri alma
    admin `duzelt`le (iade politikası K11 metninde: kullanılmış kredi iade
    edilmez; kullanılmamış paket 14 gün — sahibin kararı). Otomatik negatif
    `paket` satırı YOK: kullanıcı krediyi çoktan harcamış olabilir, eksi
    bakiye yalnız admin kararıyla (Faz 3 K1 "eksiye yalnız admin `duzelt` ile").
* **`routers/odeme.py` `POST /api/odeme/webhook`** — oturumsuz (`KAPILI`
  dışı; `test_kimlik` "oturumsuz 401" listesinde MUAF gerekçesiyle — `hesap`
  rotalarının deseni), CSRF/Origin kapısı web'de yok (netguard masaüstü);
  gövde HAM bayt okunur (`await request.body()`; JSON'a çevirmeden imza),
  `kiraci.baglam(rol=ADMIN)` (`yonetici_ekler` — `kredi_hareketleri` ve
  `siparisler`), `odeme.isle(db, olay)`; **imza hatası 400**, işlenen 200,
  yinelenen 200, iç hata 500 (Polar yeniden dener). Yanıt gövdesi `{"durum":
  "islendi"|"yinelenen"|"atlandi"}`. Günlük: `olay=odeme.<tur>` INFO
  (`kullanici_id`, `siparis`, `kredi`), `odeme.hata` ERROR (Sentry olayı).
  Rota sayısı 70 → **71**.
* **Admin:** `GET /api/admin/odeme-olaylari?hata=1` (son 100; `depo_admin`)
  ve `admin.js` "Ödeme" sekmesi (olay, tür, kullanıcı, hata) — sahibin
  "ürün yok / kullanıcı yok" satırlarını göreceği yer. `ADMIN_ROTALAR` 9 → 10;
  rota 71 → **72**.
* **Sandbox uçtan uca (sahibin adımı ile):** Polar sandbox'ta ürün oluştur,
  metadata `kromis_tur=paket kromis_kredi=500` / `kromis_plan=temel`, webhook
  URL'si → geliştirici tüneli (ör. `cloudflared`/`ngrok`), test kartı; olay
  gelir, defter satırı yazılır. Bu ölçüm PR gövdesine yazılır.

**`paket:<order_id>`, `polar:<event_id>` DEĞİL (K4).** Faz 3 devir listesi
`polar:<event_id>` demişti (`:1140-1141`). İki katman ayrılıyor: **teslimat**
idempotency'si `odeme_olaylari.webhook_id` (Standard Webhooks `webhook-id`,
yeniden denemede aynı) — yinelenen teslimatı rota kapıda döndürür; **iş**
idempotency'si defter anahtarında sipariş kimliği — çünkü aynı siparişi anlatan
İKİ FARKLI olay gelebilir (`order.paid` + `subscription.active`; sahibin
panelden "yeniden gönder"i yeni `webhook-id` üretebilir). Sipariş kimliği
Polar'ın parasal nesnesi: bir sipariş bir kez kredi olur, hangi yoldan
gelirse gelsin. `siparisler.polar_siparis_id UNIQUE` üçüncü kilit.

**Dokunulan.** yeni `services/polar.py`, yeni `services/odeme.py`, yeni
`routers/odeme.py`, `app.py` (router), `services/depo_admin.py`
(`odeme_olaylari`), `routers/admin.py`, `static/admin.{js,html,css}` (sekme),
`bundled/i18n/*` (+~10), `requirements.txt` (`polar-sdk==X.*` pin + gerekçe;
`Dockerfile` imaja girer), `.env.example` (`KROMIS_POLAR_ORTAM`,
`KROMIS_POLAR_ERISIM_JETONU`, `KROMIS_POLAR_WEBHOOK_SIRRI`) + `ALTYAPI` +3,
`tests/test_odeme.py` (~30: imza geçerli/geçersiz/eksik başlık; yinelenen
`webhook-id` 200 + tek satır; `order.paid purchase` → `paket` satırı +
`paket_bakiye` + `siparisler`; aynı `order_id` iki olayla → tek satır;
`subscription_create` → plan + hibe tamamla; `subscription_cycle` ay ortası
→ tamamla, dolu bakiye dokunulmaz; `canceled` → `plan_bitis`, plan kalır;
`revoked` → free + `sona_erme` yalnız hibe kovası, paket durur; `updated` pro →
temel düşürme; kullanıcı yok / ürün yok → 200 + `hata`; bilinmeyen tür → 200
`atlandi`; iç hata → 500 + olay satırı YOK (aynı transaksiyon); RLS: uygulama
rolüyle `yonetici_ekler` `siparisler`de; `refunded` → WARNING, defter dokunulmaz),
`tests/test_kimlik.py` (muaf liste), `tests/test_app_bolme.py` (72),
`tests/test_admin.py` (`ADMIN_ROTALAR` 10), `tests/test_i18n.py` (konuşmayan
modüller), `tests/test_galeri_db.py` (`EK_DEPOLAR` +`odeme.py`; `KIRACISIZ`),
`tests/test_docker_kapisi.py`, `docs/graflar/*`. Sahte Polar yükleri
`tests/fixtures/polar/*.json` (sandbox'tan KAYDEDİLMİŞ, e-posta/adres
`DUMMY`lenmiş).

**Risk.** Orta-yüksek: para. Küçültme: `ON CONFLICT` üç katman, her yol
idempotent test; `order.refunded` otomatik değil; sandbox önce. Polar alan
adları doğrulanmadı — bu görev ilk adımında Polar belgesini okur, tablo
güncellenir. Webhook ucu internete açık, sırsız çağrı 400 — imza yoksa gövde
hiç ayrıştırılmaz (DoS yüzeyi küçük: HMAC hesabı).

**Çıkış ölçütü.** Sandbox'ta 500 kredilik paket → `order.paid` → 10 sn içinde
`GET /api/kredi` `paket_bakiye` 500, `siparisler` 1 satır; Polar'dan aynı olayı
yeniden gönder → satır sayısı aynı; `temel` aboneliği → plan `temel`, hibe
tamamlandı; iptal → `plan_bitis` dolu, plan aynı; takım yeşil.

**Sahibin adımı — Polar hesabı (bir kez, bu görevden ÖNCE).** Polar'da
organizasyon + **sandbox** organizasyonu; sandbox'ta erişim jetonu ve webhook
uç noktası (URL `https://<sandbox alan adı>/api/odeme/webhook`, olaylar:
`order.paid`, `order.refunded`, `subscription.active/updated/canceled/uncanceled/revoked`,
`customer.created/updated`); sandbox ürünleri: `temel` (aylık), `pro` (aylık),
paketler — metadata yukarıdaki anahtarlarla. Üç sırrı sandbox dağıtımının
ortamına. **Hesap riski** (master `:201-204`): Polar'ın AI ürün incelemesi için
kullanım şartları (6) yayında olmalı — production onayı 6'dan sonra istenir.

---

## 4. Checkout, müşteri portalı, satış yüzü — `POST /api/odeme/checkout`, `GET /api/odeme/portal`, `/planlar`, "Kredi" bölmesi, `tools/polar_esitle.py` (PR: `faz4/checkout-portal`)

**Kapsam.** Kullanıcı satın alır; çıkış kriterinin ödeme yarısı.

* **`tools/polar_esitle.py`** — Polar `products.list` → `urunler` (upsert
  `polar_urun_id`; metadata `kromis_tur` `plan|paket`, `kromis_plan`,
  `kromis_kredi`; Polar'da arşivlenen ürün `aktif=false`). `DATABASE_URL` +
  Polar sırlarıyla, imajda (`OPERATOR_ARACLARI`, `tools/marj_raporu.py` deseni);
  admin bağlamı gereksiz (RLS'siz tablo). `--kontrol` bayrağı yalnız farkı
  basar (CI değil, sahibin). Fiyat Polar'dan gelir, bizde yazılmaz (K5).
* **`POST /api/odeme/checkout` `{"urun_id": …}`** (oturumlu, `KAPILI`) →
  `polar.checkout_ac(products=[polar_urun_id], external_customer_id=str(k.id),
  customer_email=k.eposta, metadata={"kullanici_id": …, "urun_id": …},
  success_url=f"{koken}/odeme/tesekkur?checkout_id={{CHECKOUT_ID}}")` → `{"url":
  …}` (ön yüz `location.assign`; 303 değil — `fetch` sarmalı JSON bekler,
  `core.js:42` deseni). Ücretli plandayken plan ürünü seçilirse Polar aynı
  aboneliği YÜKSELTİR mi, yeni abonelik mi açar — **3. görevde doğrulanır**;
  öneri: aktif aboneliği olan kullanıcıya plan değişikliği için PORTAL bağlantısı
  gösterilir (Polar oranlar/proration'ı kendisi yapar), checkout yalnız
  `free → ücretli` ve paketler için. `sartlar_kabul_at` NULL ise **412**
  `err.sartlar_gerekli` (6'nın onay kutusu; eski kullanıcı ilk satın almada
  onaylar).
* **`GET /api/odeme/portal`** → Customer Session → `{"url": …}`;
  `polar_musteri_id` yoksa (hiç satın almamış) 404 `err.musteri_yok`. Portalda
  Polar: aboneliği iptal et/geri al, kart güncelle, **faturaları indir** —
  fatura sayfası BİZDE YOK (MoR keser). "Kredi" bölmesinde `siparisler` listesi
  yalnız özet (tarih, ürün, tutar) + "faturalar Polar portalında" bağlantısı.
* **`GET /api/odeme/urunler`** (oturumsuz — fiyat listesi herkese) → aktif
  ürünler + `PLANLAR` kuralları (filigran, video, hibe) → satış sayfasının verisi.
* **`/planlar` sayfası** — sunucu şablonu (`sablon.sayfa`, `/giris`in deseni;
  vanilla, K12): üç plan kartı (free/temel/pro: fiyat, hibe, filigran, video,
  "ticari haklar"), paket kartları, "Satın al" → checkout; oturumsuzsa
  `/giris?sonra=/planlar`. **`err.plan_kapsamiyor` 403 toast'ının bağlantısı
  BURAYA** (Faz 3 / 6'nın bilerek boş bıraktığı yer, `core.js`). Composer
  `#run-cost` "kalan M" = toplam; `M < N` uyarısında "kredi al" bağlantısı.
  `/odeme/tesekkur` sayfası `krediYenile()`i 2 sn'de bir 30 sn yoklar
  (webhook gecikmesi), "bakiyene işlendi" / "birkaç dakika sürebilir".
* **Ayarlar "Kredi" bölmesi** (`settings.js`): iki kova satırı ("aylık hibe
  120 · paket 480"), plan + `plan_bitis` ("dönem sonunda ücretsiz plana geçer:
  12 Kasım"), "Plan değiştir / kredi al" → `/planlar`, "Aboneliğimi ve
  faturalarımı yönet" → portal, son siparişler. Hareket listesinde `paket` türü.
* **Admin:** kullanıcı satırında `paket_bakiye`, `polar_musteri_id` (Polar
  panelinde arama için), "paket kredisi ekle" (`duzelt(kova='paket')`).

**Polar'ın barındırılan sayfaları, gömülü checkout DEĞİL (K7).** Kart verisi
hiçbir zaman bizim alanımızda değil (PCI kapsamı sıfır); vanilla ön yüz Polar
JS'ini almaz; başarı sayfası yoklama ile bakiyeyi gösterir. Gömülü/iframe
checkout (Polar "embedded"): daha akıcı ama üçüncü taraf betiği + CSP + 286
test çapası; bugün kazancı yok.

**Dokunulan.** yeni `tools/polar_esitle.py`, `routers/odeme.py` (+3 rota →
**75**; `KAPILI` +1 checkout/portal, `DIZINSIZ_KAPILI`; `urunler` oturumsuz
muaf), `routers/kok.py` (`/planlar`, `/odeme/tesekkur` şablon rotaları → **77**),
`static/planlar.html`, `static/tesekkur.html` (ya da tek şablon), `static/{core,settings,admin}.js`,
`static/*.css`, `bundled/i18n/*` (+~30), `eslint.paylasilan-adlar.json`,
`services/polar.py` (checkout/portal/urunler), `services/depo_admin.py`,
`.dockerignore` (araç imajda KALIR), `tests/test_odeme_route.py` (~15: checkout
gövdesi Polar'a giden alanlar — `external_customer_id` = kullanıcı id'si;
şartlar onaysız 412; portal 404/200; urunler oturumsuz; plan sayfası HTML
çapaları), `tests/test_araclar.py` (`polar_esitle` upsert/arşiv), `tests/test_index.py`
(toast bağlantısı, `#run-cost` "kredi al"), `tests/test_playwright_odeme.py`
(E2E: sahte Polar — `sitecustomize` sağlayıcısının deseniyle `polar.checkout_ac`
yerel bir "ödeme sayfası"na yönlendirir, o sayfa webhook'u İMZALI çağırır →
bakiye 200 → 700; portal düğmesi URL alır), `tests/test_kimlik.py`/`test_app_bolme.py`
(rota sayıları), `tests/test_id_contract.py` (yeni betik yoksa dokunulmaz),
`docs/graflar/onyuz.md` (yeni şablon), `docs/graflar/*`.

**Risk.** Orta. Fiyat gösterimi `urunler` aynasından: sahip Polar'da fiyatı
değiştirip `polar_esitle` koşmazsa sayfa bayat fiyat gösterir (ödeme yine
Polar'ın doğru fiyatıyla) — `urunler.guncellendi` 7 günden eskiyse admin
sekmesinde uyarı + `olay=odeme.urunler_bayat`. Webhook gecikmesi teşekkür
sayfasında dürüstçe söylenir.

**Çıkış ölçütü.** Ücretsiz kullanıcı `/planlar` → paket → Polar sandbox →
teşekkür → composer "kalan 700"; `temel` aboneliği → filigran kalkar, video
açılır; portal bağlantısı Polar'a gider; E2E sahte Polar yeşil; takım yeşil.

**Sahibin adımı — fiyatlar ve ürünler (bir kez sandbox, bir kez production).**
Polar'da ürünleri ve fiyatları yaz (öneri tablosu K5), metadata'yı doldur,
`python tools/polar_esitle.py` koş, `/planlar`a bak.

---

## 5. Hesap silme ve veri dışa aktarma — `POST /api/hesap/sil`, bakım turunda `silme_turu`, `GET /api/hesap/disa-aktar` (PR: `faz4/hesap-silme-disa-aktarma`)

**Kapsam.** Çıkış kriterinin "hesabını tamamen silebiliyor" yarısı + KVKK
md. 11 / GDPR md. 17 ve 20 (silme, taşınabilirlik).

* **`POST /api/hesap/sil` `{"parola": …}`** (Google hesabı için parolasız →
  e-posta jetonu `sil-dogrula`, `sifirla` akışının ikizi) → **anında:**
  `silindi_at = an`, `eposta → f"silindi-{id}@anonim.invalid"` (citext UNIQUE
  bozulmaz; asıl e-posta GİDER — anonimleştirme), `parola_ozeti NULL`, `dil
  NULL`, `polar_musteri_id` KALIR (Polar mutabakatı; Polar tarafında müşteri
  silme sahibin — K9 notu), bütün `oturumlar` silinir (giriş imkânsız —
  `hesap.py` zaten `silindi_at IS NULL` süzer), `saglayici_kimlikleri` HEMEN
  silinir (BYOK anahtarları — bekletilmez), aktif Polar aboneliği
  `polar.abonelik_iptal(cancel_at_period_end=False)` (3 varsa; yoksa `olay=
  hesap.silme_abonelik` WARNING sahibe). Yanıt 200 + çıkış. E-posta: "hesabın
  kapatıldı; içerik 7 gün sonra silinir" (`services/posta.py`, `posta.log`).
  Geri alma YOK (öneri — basitlik; alternatif 7 gün içinde giriş = iptal, K9).
* **`silme_turu` (bakım turu, 5 dk, admin bağlamı):** `silindi_at < an - 7 gün
  AND temizlendi_at IS NULL` olan hesaplar için, HER KİRACI KENDİ BAĞLAMINDA
  (`eskileri_sil`in deseni — admin DELETE yapamaz): `isler` (girdi dizinleri
  + R2 nesneleri, `dosya.Depo.sil`), `medya` + nesneleri, `klasorler`,
  `sohbetler`, `paletler`, `varliklar`, `tercihler`; sonra admin bağlamında
  `jetonlar`/`giris_denemeleri`; **`kredi_hareketleri` ve `siparisler` KALIR**
  (sahibi anonim `kullanicilar` satırı — K9); `temizlendi_at = an`;
  `BakimOzeti` +`temizlenen_hesap`; `olay=hesap.temizlendi` INFO. Kuyruktaki
  işleri `kuyruk.iptal` + `defter.iade` (silme anında — 7 gün beklemez).
  `KROMIS_HESAP_SILME_BEKLEME_GUN` (boş = 7, 0 = hemen).
* **`GET /api/hesap/disa-aktar`** → ZIP (akışla, `zip_disa_aktar`ın deyimi):
  `hesap.json` (id, e-posta, dil, plan, olusturuldu, sartlar_*), `kredi_hareketleri.csv`
  (tamamı — `defter.hareketler(limit=None)`), `siparisler.csv`, `isler.json`
  (`kuyruk._json` — `saglayici_meta` DÖKÜLMEZ, platformun verisi), `sohbetler.json`,
  `paletler.json`, `klasorler.json`, `medya.json` (kayıtlar + nesne yolları);
  **medya baytları DEĞİL** — 500 MB'lık galeri senkron ZIP olmaz; onun için
  galerinin mevcut ZIP dışa aktarması (klasör başına) bağlantısı yanıtta.
  Kullanıcının bağlamında, `sahip` politikası zaten süzer. Saatte 1 (kota
  `check_saatlik` deseni; 429).
* **Ayarlar "Hesap" bölmesi:** "Verimi indir" ve "Hesabımı sil" (parola +
  ikinci onay metni "SİL"); silme sonrası `/giris`. Admin listesi silinmişleri
  ayrı süzgeçle gösterir (`silindi_at`, `temizlendi_at`), geri alma yok.

**Anonimleştir + 7 gün sonra içeriği sil; defter kalır — CASCADE ya da sonsuz
soft delete DEĞİL (K9).** Faz 3 / 1 FK'yi CASCADE koymuş, kararı buraya
bırakmıştı (`:134-135`, `:1152-1154`). CASCADE kişisel veriyi de mali kaydı da
siler: `siparisler`/`kredi_hareketleri` Polar'ın ödemeleriyle mutabakatın bizim
tarafımız, TTK md. 82 / VUK md. 253 saklama süreleri (10 / 5 yıl — **mali
müşavir teyidi**, sahibin adımı) satırın kalmasını ister; anonim `kullanicilar`
satırı FK'yi ayakta tutar, kişisel veri (e-posta, parola, dil, içerik, BYOK
anahtarı) gider. Sonsuz soft delete (bugünkü `silindi_at` yer tutucunun ima
ettiği) KVKK md. 7 "silme/yok etme/anonimleştirme"yi karşılamaz. 7 gün: yanlış
tıklamaya/hesap ele geçirmeye pay (bekleme içinde içerik durur, oturum yok);
KVKK md. 13 30 gün cevap süresinin içinde.

**Dokunulan.** `routers/hesap.py` (+2-3 rota → **79-80**), `services/hesap.py`
(`anonimlestir`, `sil_dogrula`), yeni `services/disa_aktar.py` (ZIP), `services/isci.py`
(`silme_turu`, `BakimOzeti`), `services/kuyruk.py` (`sahibin_islerini_iptal`),
`services/dosya.py`/`nesne_depo.py` (kiracının bütün nesneleri — önek `kullanicilar/<id>/`
ve `isler/<id>/` listeleme), `services/defter.py` (`hareketler(limit=None)`),
`static/settings.js`, `static/index.html` (Hesap bölmesi düğmeleri — metin
çapaları dokunulmaz, kök eklenir), `bundled/i18n/*` (+~20), `.env.example`
(`KROMIS_HESAP_SILME_BEKLEME_GUN`) + `ALTYAPI`, `tests/test_hesap_silme.py` (~20:
silme → oturum yok, giriş 401, e-posta anonim, BYOK satırı yok, kuyruktaki iş
iptal + iade; 7 gün önce tur dokunmaz; 7 gün sonra tur içerik + nesne siler,
defter ve sipariş satırı KALIR, `temizlendi_at` dolu; ikinci tur no-op; RLS:
kiracı bağlamında silme uygulama rolüyle; Google hesabı jeton yolu; yanlış
parola 401; dışa aktarma ZIP içeriği + başkasının satırı yok + saatlik 429),
`tests/test_isci.py` (özet +1 anahtar), `tests/test_rls.py`, `tests/test_galeri_db.py`
(`DEPOLAR`/`KIRACISIZ`), E2E `tests/test_playwright_hesap.py` (sil → giriş
sayfası → aynı e-posta ile giriş "hesap yok"), `docs/graflar/*`.

**Risk.** Orta. Geri dönüşsüz kullanıcı eylemi: parola + onay metni + 7 gün.
R2 nesne listeleme kiracı öneki ile (`artik_dosya.py` deseni). Anonim e-posta
biçimi `@anonim.invalid` (RFC 2606 rezerve TLD) — posta gönderilmez
(`posta.py` `.invalid`i reddeder, test).

**Çıkış ölçütü.** Hesap sil → giriş yok, e-posta anonim, BYOK yok; bakım turu
(saat yamalı) 7 gün sonra medya/iş/sohbet/palet sıfır, R2'de kiracı öneki
boş, `kredi_hareketleri` satır sayısı aynı; dışa aktarma ZIP beş dosya; takım yeşil.

**Sahibin adımı — Polar tarafı ve saklama süresi teyidi.** Polar müşteri
kaydını (e-posta, adres) kullanıcı adına Polar'dan silmek: Polar veri işleyen
mi sorumlu mu (MoR olarak kendi veri sorumlusu — aydınlatma metni 6'da böyle
yazar) — Polar belgesinden doğrula; mali müşavire "anonim hesabın kredi
hareketleri ve sipariş kayıtları kaç yıl" sorusu; cevap K10 tablosuna.

---

## 6. Hukuki metinler ve rıza — `bundled/hukuk/`, `GET /hukuk/{slug}`, kayıtta onay, "ticari haklar", Polar AUP (PR: `faz4/hukuk-metinleri`)

**Kapsam.** Yol haritası kartı: "GDPR + KVKK birlikte: gizlilik/aydınlatma
metni + açık rıza, kullanım şartları, çerez bildirimi". Metinler TASLAK —
avukat/mali müşavir onayı sahibin adımı; kod kısmı onaydan bağımsız.

* **Dört metin, iki dil** — `bundled/hukuk/{kullanim-sartlari,gizlilik,cerez,ticari-haklar}.{tr,en}.html`
  (HTML parçası; markdown kütüphanesi eklenmez — yeni bağımlılık, i18n
  JSON'una 20 KB metin de girmez). `GET /hukuk/{slug}` (`kok.py`, `sablon.sayfa`
  ile kabuk + parça; dil `services/dil.py` zinciri; slug beyaz liste, 404).
  `HUKUK_SURUMU = "2026-10"` kod sabiti (metin değişince sürüm değişir → yeni
  onay istenir). Footer bağlantıları `/giris`, `/planlar`, ayarlar "Hakkında".
* **Kayıtta onay kutusu** (`giris.js`/`giris.html`; zorunlu; `KayitIstegi.sartlar:
  bool` → 422 yoksa) → `sartlar_kabul_at`, `sartlar_surumu`. Var olan kullanıcı:
  ilk checkout'ta (4'ün 412'si) ya da sürüm değişince ayarlarda banner
  "şartlar güncellendi" → `POST /api/hesap/sartlar-kabul`. Tıkla-onay
  (clickwrap), yalnız bağlantı (browsewrap) DEĞİL (K11).
* **Çerez:** yalnız oturum çerezi (`services/cerez.py`, zorunlu, `Secure`
  `HttpOnly`) ve `localStorage` tercihleri; üçüncü taraf/izleme yok → **çerez
  BANNER'I GEREKMEZ**, çerez bildirimi metni yeter (ePrivacy md. 5(3) "kesinlikle
  gerekli" istisnası; KVKK Kurulu 2022 çerez rehberi aynı ayrım). Sentry
  istek gövdesi/PII kapalı (Faz 2 / 9) — metinde yazılır.
* **Aydınlatma metni (KVKK md. 10) + GDPR md. 13 birlikte:** veri sorumlusu
  (sahip; unvan `marka-ve-unvan.md`), işlenen veriler (e-posta, parola özeti,
  dil, IP/istek günlüğü, prompt ve üretilen medya, kredi hareketleri, sipariş
  özeti — kart verisi YOK), amaçlar, hukuki sebepler (sözleşme, meşru menfaat,
  açık rıza yalnız pazarlama e-postası varsa — yok), **alıcılar:** Polar (MoR,
  kendi veri sorumlusu — ödeme/fatura), model sağlayıcıları (Azure/OpenAI,
  Google, fal — prompt ve girdi görseli oraya gider; platform anahtarıyla
  üretimde işleyen biziz, BYOK'ta kullanıcının kendi sözleşmesi), barındırma
  (Fly.io, Neon/Postgres, Cloudflare R2), hata izleme (Sentry — PII kapalı),
  posta servisi; **yurt dışına aktarım** (KVKK md. 9 — sağlayıcılar ABD/AB;
  2024 değişikliği sonrası standart sözleşme / açık rıza yolu — **avukat**);
  saklama süreleri (K10 tablosu); haklar ve başvuru yolu (e-posta; 30 gün / 1 ay);
  hesap silme ve dışa aktarma (5) bağlantısı.
* **Kullanım şartları:** hizmet tanımı (BYOK + platform kredisi), planlar,
  kredi kuralları (hibe devretmez, paket devreder, iade politikası: kullanılmış
  kredi iade edilmez, kullanılmamış paket 14 gün — sahibin kararı; abonelik
  iptali dönem sonu), **Polar AUP yansıması** (master `:201-204`): NSFW,
  deepfake/face swap, ses klonlama, telif/marka ihlali, gerçek kişi görselinin
  izinsiz kullanımı YASAK; ihlalde hesap kapatma, kredi iadesi yok; sağlayıcı
  içerik politikaları da geçerli. Yaş 18+. Hizmet "olduğu gibi", sağlayıcı
  kesintileri.
* **"Ticari haklar" metni** (master `:183`): ücretli planda üretilen medya —
  kullanıcının, ticari kullanım dahil, sağlayıcı lisansının izin verdiği ölçüde
  (OpenAI/Google/BFL çıktı politikaları BAĞLAYICI — metin onlara bağlanır);
  ücretsiz planda kişisel kullanım + filigran, filigran kaldırılamaz; Kromis
  çıktı üzerinde hak iddia etmez. `/planlar` kartındaki cümlenin kaynağı.
* **DPA gözden geçirmesi** (kart: "sağlayıcılarla veri işleme sözleşmeleri"):
  `docs/hukuk-kontrol-listesi.md` — her alıcı için DPA/DPF durumu, veri
  konumu, kabul edildiği tarih; sahibin doldurduğu tablo, test yalnız dosyanın
  ve satır başlıklarının varlığını ölçer.

**Kendi metnimiz, üretici hizmeti DEĞİL (K11).** Termly/iubenda tarzı üretici
aylık ücret + gömülü betik (çerez banner'ı zaten gereksiz) + Türkçe KVKK
metinleri zayıf; metin bizim `bundled/`de, sürümlü, testli (çapa cümleleri:
"filigran", "ticari", "Polar", "30 gün", "silme"). Avukat onayı metnin
İÇERİĞİNE — mekanizma (sürüm, onay damgası, sayfa) bundan bağımsız gemiye
biner.

**Dokunulan.** yeni `bundled/hukuk/*.html` (8 dosya), `routers/kok.py` (+1
rota), `routers/hesap.py` (`sartlar` alanı, `sartlar-kabul` → +1), `services/hesap.py`,
`static/giris.{html,js}`, `static/index.html` (footer/hakkında bağlantıları),
`static/planlar.html` (4 varsa; yoksa 4 ekler), `bundled/i18n/*` (+~8 kısa
anahtar; metinler değil), yeni `docs/hukuk-kontrol-listesi.md`, `tests/test_hukuk.py`
(~12: dört slug × iki dil 200 + `Content-Language`; bilinmeyen slug 404;
metin çapaları; onaysız kayıt 422; onaylı kayıt damga + sürüm; sürüm değişince
`GET /api/hesap/ben` `sartlar_guncel: false`; `.dockerignore` `bundled/hukuk`
imajda), `tests/test_telif.py` (yeni dosyaların başlığı), `tests/test_docker_kapisi.py`,
`tests/test_kimlik.py`/`test_app_bolme.py` (rota sayıları), `docs/graflar/*`.

**Risk.** Düşük (kod), yüksek (içerik — avukatsız yayın). Küçültme: metinler
"taslak — avukat onayı bekliyor" damgasıyla gemiye biner, damga
`HUKUK_ONAYLI = False` sabiti; production Polar onayı (3) yayında metin ister
→ sahibin sırası: avukat → damga → Polar başvurusu.

**Çıkış ölçütü.** `/hukuk/kullanim-sartlari` iki dilde; kayıt onay kutusuz
422; `sartlar_kabul_at` dolu; `/planlar` "ticari haklar" cümlesi metne
bağlanır; takım yeşil.

**Sahibin adımı — avukat ve mali müşavir.** Dört metnin gözden geçirilmesi
(KVKK md. 9 yurt dışı aktarım yolu; iade politikası; yaş), `docs/hukuk-kontrol-listesi.md`
tablosunun doldurulması, `HUKUK_ONAYLI = True` PR'ı.

---

## 7. Operasyon ve belgeler — `isletme.md`, KURULUM 11. adım "Ödeme (Polar)", `.env.example`, mutabakat aracı, ikinci kova, Faz 4 kapanışı (PR: `faz4/operasyon`)

**Kapsam.** Faz 4'ün işletme ayağı ve kapanış belgesi (Faz 3 / 7'nin deseni).

* **`tools/polar_mutabakat.py`** — Polar `orders.list` (dönem) ↔ `siparisler`
  (aynı dönem): Polar'da olup bizde olmayan sipariş (webhook kaçtı → `olay`
  yeniden gönder) ve bizde olup Polar'da olmayan (olmamalı) — CSV; aylık,
  payout'la yan yana (`marj_raporu.py`nin ikizi; imajda). Marj tablosuna
  (5. görev Faz 3) **gelir sütunu**: dönemde `siparisler` toplamı (USD) ve
  Polar ücreti tahmini (%5 + 0,50 + %1,5 varsayımı — gerçek payout Polar'da).
* **`docs/isletme.md`:** § 2 yedek tablosuna `urunler`/`siparisler`/`odeme_olaylari`
  (pg_dump içinde; `odeme_olaylari` 1 yıl saklama); § 6 uyarılara `odeme.hata`
  (ERROR — Sentry OLAYI), `odeme.urunler_bayat`, `hesap.silme_abonelik`; §
  "Faz 4" satırları kapanır (`:200-201` defterin kaderi → K9; `:329` **ikinci
  kova AÇILIR**: ödeyen kullanıcı var — `rclone sync` cron sahibin adımı); §
  7 sırlar +5 (`KROMIS_POLAR_*` ×3, `KROMIS_TEMEL/PRO_AYLIK_HIBE`,
  `KROMIS_HESAP_SILME_BEKLEME_GUN`); § 9 bakım turu (6) silme turu, (7) olay
  saklama; aylık mutabakat maddesi; KVKK başvuru işleyişi (e-posta → 30 gün;
  silme/dışa aktarma kullanıcının kendi düğmesi, başvuru gelirse admin aynı
  yolu koşar).
* **KURULUM.md 11. adım "Ödeme (Polar)"**: sandbox → production sırası
  (jetonlar, webhook URL'si ve olay listesi, ürün metadata'sı, `polar_esitle`),
  fiyat/hibe değişkenleri, iki kova kuralı, iade politikası (admin `duzelt`),
  hesap silme/dışa aktarma, hukuki metin sürümü; **canlı kontrol listesi**
  (10 madde: sandbox paket → bakiye; sandbox abonelik → plan; yeniden gönder →
  tek satır; iptal → `plan_bitis`; production jetonları; ilk gerçek 5 USD'lik
  paket kendi hesabından; portal faturası; hesap silme test hesabıyla + 7 gün
  turu (`KROMIS_HESAP_SILME_BEKLEME_GUN=0` ile prova); `/hukuk/*` yayında;
  `polar_mutabakat.py` ilk ay sonu). README (tr/en) "Planlar ve kredi" bölümüne
  "ödeme Polar üzerinden" cümlesi + KURULUM 11 bağlantısı.
* **`.env.example`** 1. bölüm: bütün Faz 4 değişkenleri kendi görevlerinde
  girmiş olur (2: `KROMIS_TEMEL/PRO_AYLIK_HIBE`, `KROMIS_UCRETLI_HIBE_BAKIMDA`;
  3: `KROMIS_POLAR_*`; 5: `KROMIS_HESAP_SILME_BEKLEME_GUN`) — burada
  `test_docker_kapisi` bekçisi şablon ↔ KURULUM/isletme adlarını ölçer.
* **Faz 4 kapanış** bu belgeye: PR tablosu, ölçümler (test, rota, tablo,
  politika), sahibin bekleyen adımları, **Faz 5'e devir** (kötüye kullanım / IP
  limitleri, moderasyon otomasyonu, TR ikinci ayak iyzico + e-Arşiv, BYOK payı
  ölçümü, `tutarlilik` ve `hibe_turu` ölçeği, dağıtımda iş kaybı, yedek
  tatbikatı, E2/E3 mini faz, vanilla yeniden bakış).

**Dokunulan.** yeni `tools/polar_mutabakat.py`, `services/depo_admin.py` (marj
gelir sütunu), `static/admin.js`, `docs/isletme.md`, `KURULUM.md`, `README.md`,
`README.en.md`, `tests/test_araclar.py`, `tests/test_admin.py`, `tests/test_docker_kapisi.py`
(+1 bekçi: KURULUM 11, README cümlesi, isletme satırları, `.env.example` beş ad),
`tests/test_rls.py` (`BAGLAM_TASIYAN_ARACLAR` — araç admin bağlamı taşır),
bu belge (kapanış), `docs/graflar/*`.

**Risk.** Düşük.

**Çıkış ölçütü.** `test_docker_kapisi` yeşil; `polar_mutabakat.py` sandbox'ta
sıfır fark; belge kapanışı dolu; takım yeşil.

**Sahibin adımı — production'a geçiş (canlıda bir kez).** KURULUM 11'in
listesi; ikinci kova cron'u; Polar production onayı (AI ürün incelemesi —
hukuki metinler yayında olmalı).

---

## Faz 4 çıkış kriteri

Ücretsiz kullanıcı `/planlar`dan **kartla paket alır** → Polar sandbox/production
→ webhook → `paket:<order_id>` satırı → composer "kalan" artar → aynı olayı
Polar yeniden gönderir → satır sayısı AYNI → **`temel`ye abone olur** → plan
`temel`, filigran kalkar, video açılır, dönem hibesi tamamlanır → bir sonraki
dönem `order.paid subscription_cycle` → yine tamamla, dolu bakiyeye binmez →
portaldan iptal → `plan_bitis` dolu, plan dönem sonuna kadar → `revoked` →
`free`, hibe kovası 200'e `sona_erme` ile iner, **paket kovası durur** →
**faturasını Polar portalından indirir** → **hesabını siler** → giriş yok,
e-posta anonim, BYOK yok → 7 gün sonra bakım turu içerik + R2 nesnelerini
siler, `kredi_hareketleri`/`siparisler` anonim sahiple KALIR → dışa aktarma
ZIP'i beş dosya → kayıt onay kutusuz 422, `/hukuk/*` iki dilde → katalogda
`gpt-image-1` yok (1 ✅), katalog ~10 görsel + ~10 video sağlayıcıdan bağımsız
ve `tarife_kontrol` boş (1b) → RLS bekçileri **10 tablo / 32
politika**, **17 tablo** → her kullanıcıda iki kova SUM == önbellek → tam takım
yeşil (E2E dahil, sahte Polar ile).

Yol haritası kartının cümlesi ("kartla abone olup fatura alabiliyor ve hesabını
tamamen silebiliyor") bunun içinde: fatura Polar'ın, silme 5'in.

---

## Veri modeli değişiklikleri — `0008_odeme` özeti

**Uygulandı 2026-09-21 (2. görev, PR `faz4/odeme-semasi`)** — tablo aynen;
sapmalar §2 "Yapıldığında": `siparisler.urun_id` NOT NULL, `urunler`
`tur_plan_uyumu` CHECK'i, `odeme_olaylari` `alindi` indeksi, downgrade paket
satırıyla durur.

| tablo | değişiklik | görev |
| --- | --- | --- |
| `kredi_hareketleri` | `kova text NOT NULL DEFAULT 'hibe' CHECK ('hibe','paket')`; `tur` CHECK + `paket` | 2 |
| `kullanicilar` | `paket_bakiye int NOT NULL DEFAULT 0`; `polar_musteri_id text UNIQUE NULL`; `polar_abonelik_id text NULL`; `plan_bitis timestamptz NULL`; `sartlar_kabul_at timestamptz NULL`; `sartlar_surumu text NULL`; `temizlendi_at timestamptz NULL` | 2 (okuyan 3-6) |
| `urunler` (yeni, altyapı) | Polar ürün aynası: `polar_urun_id UNIQUE`, `tur`, `plan`, `kredi`, `fiyat_kurus`, `para_birimi`, `ad`, `aktif`, `guncellendi` | 2 (yazan 4) |
| `siparisler` (yeni, iş tablosu, RLS 4 politika) | `kullanici_id` CASCADE, `polar_siparis_id UNIQUE`, `polar_abonelik_id`, `urun_id`, `sebep`, `tutar_kurus`, `para_birimi`, `olusturuldu` | 2 (yazan 3) |
| `odeme_olaylari` (yeni, altyapı) | `webhook_id UNIQUE`, `tur`, `polar_nesne_id`, `kullanici_id SET NULL`, `govde jsonb` (redakte), `alindi`, `islendi_at`, `hata` | 2 (yazan 3) |

Sayılar: tablo 14 → **17**; `IS_TABLOLARI` 9 → **10**; `ALTYAPI_TABLOLARI`
1 → **3**; RLS politikası 28 → **32**; `HAREKET_TURLERI` 6 → **7**;
`YONETICI_EKLER_TABLOLARI` 1 → **2**. `downgrade` üç tabloyu, dokuz sütunu ve
iki CHECK'i düşürür (`kova` sütunu düşerken `paket` satırları varsa göç
DURUR — geri alınamaz veri; test bunu çiviler).

**Defter anahtar biçimleri (Faz 3 `:1194-1197` listesine ek, regex bekçili):**
`paket:<polar_order_id>`, `hibe:<u>:polar:<polar_order_id>` (ücretli dönem
hibesi), `sona_erme:<u>:<abonelik_id>:<YYYY-MM-DD>`, `rezerv|onay|iade:<is_id>:paket`
(ikinci kova satırı). Mevcut beş biçim aynen.

---

## Güvenlik, RLS, KVKK notları

* **Webhook ucu** internete açık ve oturumsuz: imza doğrulanmadan gövde
  ayrıştırılmaz; sır `KROMIS_POLAR_WEBHOOK_SIRRI` yalnız web sürecinde; zaman
  damgası toleransı SDK'nın (Standard Webhooks 5 dk); yeniden oynatma
  `webhook_id UNIQUE` ile. `X-Request-ID` ve `olay=odeme.*` günlüğü; gövde
  `odeme_olaylari.govde`ye REDAKTE (e-posta maskelenir mi — K10: hayır, olay
  1 yıl saklanır, kullanıcı silinince `kullanici_id SET NULL` ve gövdedeki
  e-posta/adres `[SILINDI]` — `silme_turu` günceller).
* **Yazan bağlamlar:** webhook ADMIN (`yonetici_ekler` iki tabloda); checkout/portal
  kullanıcı; `silme_turu` kiracı başına kullanıcı bağlamı (DELETE — admin
  yapamaz, `eskileri_sil` deseni); `polar_esitle` politikasız tablo.
* **Kart verisi yok**, PCI kapsamı yok; Polar'ın barındırılan sayfası (K7).
* **Sırlar:** `KROMIS_POLAR_ERISIM_JETONU` yalnız web + araçlar (işçi Polar
  konuşmaz — `silme_turu` abonelik iptalini SİLME ANINDA web yapar); `pg_dump`
  sır testi (Faz 1) `odeme_olaylari.govde`yi tarar.
* **KVKK/GDPR eşlemesi:** md. 11 / md. 15 erişim → dışa aktarma; md. 7 / md. 17
  silme → anonimleştirme + 7 gün; GDPR md. 20 taşınabilirlik → JSON/CSV;
  md. 10 / md. 13 aydınlatma → `/hukuk/gizlilik`; md. 9 yurt dışı aktarım →
  avukat; cevap süresi 30 gün (KVKK md. 13) / 1 ay (GDPR md. 12) — kullanıcının
  kendi düğmesi anında. Çerez banner'ı gerekmez (yalnız zorunlu çerez).
* **Saklama süreleri (K10)** aşağıdaki tabloda; `isler` 30 gün aynen (Faz 2 / 10).

| veri | süre | mekanizma |
| --- | --- | --- |
| `isler` (prompt, `saglayici_meta`) | 30 gün (`KROMIS_IS_SAKLAMA_GUN`) | `eskileri_sil` (var) |
| `medya`, klasör, sohbet, palet, varlık | hesap yaşadıkça; silmede +7 gün | `silme_turu` (5) |
| `oturumlar`, `jetonlar`, `giris_denemeleri` | ömür/kullanım; silmede anında | var + 5 |
| `saglayici_kimlikleri` (BYOK) | silmede ANINDA | 5 |
| `kullanicilar` anonim satır, `kredi_hareketleri`, `siparisler` | 10 yıl (TTK 82 — **mali müşavir teyidi**) | silinmez; K9 |
| `odeme_olaylari` | 1 yıl | bakım turu (7) |
| Günlük (JSON satır), Sentry | platformun/Sentry'nin süresi (90 gün öntanım) | isletme § 6 |
| Polar'daki müşteri/fatura kaydı | Polar'ın (veri sorumlusu) | aydınlatma metni |

---

## Test stratejisi — kesişen kararlar

* **Sahte Polar, gerçek imza.** SDK istemcisi yamalı (`polar.istemci`), webhook
  yükleri sandbox'tan kaydedilmiş fixture'lar, imza testte GERÇEK HMAC ile
  üretilir (sır `DUMMY…`) — `validate_event` yamalanmaz (yamalansa imza
  kapısı sessizce anlamsızlaşır, Faz 0 netguard dersi). E2E'de yerel "ödeme
  sayfası" (`sitecustomize` sağlayıcısı deseni) webhook'u imzalı çağırır.
* **İdempotency üç katman, her biri ayrı test:** `webhook_id` (yinelenen
  teslimat), `paket:<order_id>` (aynı siparişi anlatan iki olay),
  `polar_siparis_id UNIQUE` (defter yazıldı, sipariş satırı yarışta).
* **İki kova yarışı** Faz 3'ün 100 tekrarlık deseniyle; bölüşüm üç durum.
* **Hesap silme saat yamalı** (`zaman.an`): tur 6. günde dokunmaz, 8. günde siler.
* **Elle tutulan listelerin bekçisi** (CLAUDE.md § 5): `IS_TABLOLARI` (10),
  `ALTYAPI_TABLOLARI` (3), `0008_odeme.TABLOLAR`, `HAREKET_TURLERI` ↔ CHECK,
  `KOVALAR` ↔ CHECK, `SIPARIS_SEBEPLERI` ↔ CHECK, `YONETICI_EKLER_TABLOLARI`
  (2), `ADMIN_ROTALAR` (10), `KAPILI`/muaf listeleri (webhook, urunler, hukuk),
  `KREDI_HAREKET_ANAHTARI` (7), `ALTYAPI` (+6), `tarife_kontrol` (0 — 1b'de;
  1 ✅ dörtte bıraktı), `test_tablolar` dördüncü belge çapası (bu belge),
  `OPERATOR_ARACLARI` (+2), katalog ↔ i18n eşliği ve `emeklilik` tarih yamalı
  bekçisi (1b).
* **Rota sayısı:** 70 → ~80 (webhook, admin olaylar, checkout, portal, urunler,
  `/planlar`, `/odeme/tesekkur`, sil, sil-dogrula, disa-aktar, sartlar-kabul,
  `/hukuk/{slug}`) — her görev kendi literalini günceller.
* **Takım büyüklüğü tahmini:** 3.982 → ~4.150 (+~170), süre +30-40 sn (E2E
  ödeme + silme senaryoları); ölçülür ve kapanışa yazılır.

---

## Sahibin karar noktaları — öneri ve gerekçe

**Durum: kabul edildi 2026-09-21.** Sahip plan PR'ını (#69) aynen merge etti —
Faz 3'ün deseni ("kabul ediyorum" ile aynen); madde madde değişiklik gelmedi.
K5'in sayıları yine sahibin: 4. görevde `urunler` aynasına yazılırken son kez
sorulur. Aynı gün gelen tek ek yönlendirme kararları değiştirmiyor, kapsamı
genişletiyor: katalog sağlayıcıdan bağımsız büyür (1b), Azure tek ana
sağlayıcı değil.

| # | konu | öneri | neden | alternatif ve bedeli |
| --- | --- | --- | --- | --- |
| K1 | Ödeme sağlayıcısı | **Polar.sh, Merchant of Record, Starter plan**; önce sandbox; ciro ~1.000 USD/ay üstünde Pro (%3,8 + 0,40) | Türkiye'den Stripe açılamıyor (master `:184-187`); MoR KDV/VAT/GST'yi ve son kullanıcı faturasını üstlenir, biz Polar'a tek hizmet ihracı faturası keseriz (KDV istisnası, %100 kazanç indirimi — master `:209-214`); TR'ye Stripe Connect Express payout; resmî Python SDK; sandbox | Stripe Atlas (ABD LLC): kuruluş + yıllık maliyet + iki ülke muhasebesi. Paddle: TRY yok, aylık payout, 15 USD SWIFT; yedek olarak durur. iyzico/PayTR: MoR değil, 3D Secure yabancı kartı reddeder — TR içi ikinci ayak Faz 5+. Lemon Squeezy: Stripe'a geçti, yeni proje başlamaz |
| K2 | Ürün modeli | **İki ürün türü:** aylık abonelik `temel`/`pro` (dönem hibesi, devretmez) + tek seferlik **kredi paketleri** (devreder); Polar yalnız "ödendi" der, **tarife ve bakiye bizde** | Master `:205-208` "tek gerçek kaynak defter, sağlayıcı adaptör, tarife kendi katalogumuzda"; ücretsiz plan zaten deneme (trial yok); paket, aboneliğe gönülsüz kullanıcıyı da müşteri yapar | Polar events → meters → Meter Credits (bakiye Polar'da): her rezerv dış çağrı, BYOK/iade/hibe Polar sözlüğünde yok, defter ikiye bölünür. Yalnız abonelik: küçük kullanıcı kaçar. Yalnız paket: filigran/video kuralı plansız kalır |
| K3 | Kova ayrımı | **İki kova, tek tablo:** `kredi_hareketleri.kova` + `kullanicilar.paket_bakiye`; rezerv **hibe önce** tek atomik UPDATE (`LEAST`), iade/onay **önce pakete**; ücretli hibe "tamamla" webhook'la, `free` bakım turuyla; düşürmede `sona_erme` yalnız hibe kovasında | Tek kova + "hibeye tamamla" paketle kırılır (paketli kullanıcı hibesini kaybeder ya da hibe biner); atomiklik Faz 3 K1'in UPDATE'inde kalır; `tutarlilik` iki SUM; satır artışı iş başına ≤ 1 | FIFO son kullanma satırları: satır başına kalan sütunu, ay sonu tur, `tutarlilik` yeniden yazımı. Paket önce tüketilsin: kullanıcı aleyhine (devreden kredi gider, devretmeyen kalır) |
| K4 | Webhook idempotency | **İki katman:** `odeme_olaylari.webhook_id UNIQUE` (teslimat, Standard Webhooks `webhook-id`) + defter anahtarı **`paket:<order_id>`** / `hibe:<u>:polar:<order_id>` (iş) + `siparisler.polar_siparis_id UNIQUE`; kayıt ve işleme AYNI transaksiyon; yinelenen 200, iç hata 500 | Aynı siparişi iki farklı olay anlatabilir (`order.paid` + `subscription.active`), panelden yeniden gönderim yeni `webhook-id` üretebilir — sipariş kimliği parasal nesnenin kendisi; Faz 3 devir listesindeki `polar:<event_id>` yalnız teslimat katmanını kapatırdı | Yalnız `polar:<event_id>` (Faz 3 devri): yeniden gönderim çift kredi. Yalnız sipariş anahtarı: olay günlüğü olmaz, "webhook geldi mi" sorusu cevapsız |
| K5 | Planlar, fiyat, ürün eşlemesi | **`planlar` tablosu YOK** (Faz 3 K5'in "o gün gelir" cümlesinden SAPMA): kurallar `services/planlar.py`de kalır, ücretli hibe ortamdan (`KROMIS_TEMEL_AYLIK_HIBE`/`KROMIS_PRO_AYLIK_HIBE`), fiyat ve Polar ürün id'si **`urunler` aynasında** (`tools/polar_esitle.py`). **Fiyat önerisi (sahibin):** `temel` 9 USD/ay 1.200 kredi; `pro` 29 USD/ay 4.500 kredi; paketler 5 USD/500, 14 USD/1.600, 30 USD/3.800; yıllık plan yok (ilk sürüm) | Fiyatın gerçek sahibi Polar (MoR onu tahsil eder) — bizde kopyası tablo değil ayna; hibe "sayı ortamdan" deseni (Faz 3 K6); üç planın kuralı hâlâ sabit. Hesap: 1 kredi ≈ 0,005 USD maliyet → `temel` tam kullanımda 6 USD maliyet, Polar ücreti ≈ 1,09 USD → 9 USD'de ~1,9 USD marj tam kullanımda (tipik kullanım < %50); paket 5 USD → ücret 0,76, maliyet 2,5 | `planlar` tablosu + admin CRUD: göç + depo + rota + bekçi, Polar'daki fiyatla iki gerçek. Fiyat kodda: her değişiklik PR. Yıllık plan: proration/düşürme karmaşası ilk sürümde gereksiz |
| K6 | Abonelik yaşam döngüsü | **Polar'ın durum makinesi, bizde yansıması:** `order.paid` (`subscription_create/cycle/update`) → plan + hibe tamamla; `canceled` → `plan_bitis` (plan kalır); `revoked` → `free` + `dusur`; dunning/başarısız ödeme Polar'ın (revoked gelene kadar bir şey yapılmaz); yükseltme/düşürme portaldan; `order.refunded` → WARNING, kredi iadesi admin `duzelt` | Abonelik durumu Polar'da doğru, bizde türetilmiş; iptal eden kullanıcı ödediği dönemi kullanır (adil, itiraz azaltır); otomatik negatif satır kullanıcıyı eksiye düşürebilir — eksi yalnız admin kararıyla (Faz 3 K1) | Kendi durum makinesi (`past_due`, yeniden deneme e-postaları): Polar'ın işini iki kez yapmak. İptalde anında `free`: ödenmiş dönem kaybı, geri ödeme talepleri. Otomatik iade satırı: harcanmış kredi eksiye iner |
| K7 | Checkout ve portal | **Polar barındırılan checkout** (`POST /v1/checkouts/`, `external_customer_id` = `kullanicilar.id`, `metadata`), **Polar müşteri portalı** (iptal, kart, fatura); bizde fatura sayfası yok; teşekkür sayfası bakiyeyi yoklar | Kart verisi alanımıza girmez (PCI yok); MoR faturayı zaten kesiyor; vanilla ön yüz üçüncü taraf betiği almaz (K12) | Gömülü checkout: akıcı ama Polar JS + CSP + test çapaları. Kendi fatura listesi: Polar API'sinden çekip göstermek — portal aynı şeyi veriyor |
| K8 | BYOK'ta platform payı | **Yine DÜŞMEZ** (Faz 3 K3 aynen); BYOK'lu ücretsiz kullanıcı plan kurallarına (filigran, video kapalı) tabi kalır; Faz 5'te ölçümle (BYOK iş oranı, işçi maliyeti) | Kullanıcı sağlayıcıya kendi ödüyor; bugün ölçülmüş bir işçi maliyeti yok — fiyatlamak tahmin; ücretsiz BYOK "planında yok" rozeti ve filigranla zaten ücretli plana çağırıyor | 1 kredi/iş: gelir küçük, "kendi anahtarımla neden ödüyorum" itirazı, kapının açıklaması karmaşık. BYOK'u ücretli plana kapatmak: bugünkü kullanıcıların tamamını kilitler |
| K9 | Hesap silme ve defterin kaderi | **Anonimleştir + kilitle ANINDA** (e-posta `silindi-<id>@anonim.invalid`, parola/dil NULL, oturumlar ve BYOK anahtarları silinir, Polar aboneliği iptal), **içerik 7 gün sonra** bakım turunda kalıcı (`KROMIS_HESAP_SILME_BEKLEME_GUN`), **`kredi_hareketleri`/`siparisler` KALIR** anonim sahiple; geri alma yok | KVKK md. 7 anonimleştirmeyi silmeye denk sayar; mali kayıt saklama (TTK 82 / VUK 253 — mali müşavir teyidi) ödeme izini ister; FK CASCADE değişmeden kalır (satır silinmiyor); 7 gün yanlış tıklama/hesap ele geçirme payı, 30 günlük yasal sürenin içinde | CASCADE (bugünkü FK'nin ima ettiği): mali kayıt gider, Polar mutabakatı kör. Sonsuz soft delete: KVKK'yı karşılamaz. Geri alma (7 gün içinde giriş): oturum silinmemiş olmalı → hesap ele geçirilmişse saldırgan da geri alır |
| K10 | Saklama süreleri | Tablo yukarıda: `isler` 30 gün (aynen), içerik hesap ömrü + 7 gün, BYOK anında, `odeme_olaylari` 1 yıl, anonim mali kayıt 10 yıl (teyitli), günlük/Sentry platform süresi | Her satırın silen mekanizması var (bakım turu); `istek.prompt` `isler` satırıyla gider (Faz 2 `:2048` notu kapanır) | Prompt'u ayrı ve daha kısa saklamak: `isler.istek` bütün, yeniden gönderim ona bağlı (Faz 2 / 5) |
| K11 | Hukuki metinler ve rıza | **Kendi metinlerimiz** `bundled/hukuk/` (4 × tr/en, HTML parçası, sürümlü `HUKUK_SURUMU`), kayıtta **tıkla-onay** zorunlu → `sartlar_kabul_at`/`sartlar_surumu`; var olan kullanıcı ilk checkout'ta (412) ya da sürüm değişince; çerez banner'ı YOK (yalnız zorunlu çerez); Polar AUP kuralları şartlarda; "ticari haklar" ücretli plana, ücretsiz kişisel + filigran; iade politikası: harcanmış kredi iade edilmez, harcanmamış paket 14 gün; metinler "taslak — avukat onayı bekliyor" damgasıyla (`HUKUK_ONAYLI`) | Polar'ın AI ürün incelemesi şartları ve moderasyon kuralını yayında ister (master `:201-204`); clickwrap KVKK açık rıza / sözleşme kanıtı; üçüncü taraf çerez yok → banner yasal olarak gereksiz; markdown kütüphanesi eklenmez | Termly/iubenda: ücret + betik + zayıf Türkçe KVKK; browsewrap (yalnız bağlantı): kanıt zayıf; banner: gereksiz gürültü; metni i18n JSON'una koymak: 20 KB çeviri anahtarı |
| K12 | Ön yüz çerçevesi (Faz 2 K3 yeniden bakış) | **Vanilla sürer:** `/planlar` ve teşekkür sunucu şablonu (`/giris` deseni), "Kredi" bölmesi genişler, ödeme/portal/fatura ekranları Polar'ın; yeniden bakış Faz 5 sonu (ölçüm: JS satırı, hata oranı) | Fatura/satış sayfası çerçeve gerekçesiydi (Faz 2 `:852`) — MoR ikisini de kendisi barındırıyor, bizde iki statik sayfa kaldı; 286 + 14 test çapası ve Node derleme aşaması bugün karşılıksız | React/Svelte + paketleyici: Docker'a Node, CI'a derleme, çapaların yeniden yazımı; kazanç iki sayfa |

---

## Üst belgeden (master §5 "Faz 5" kartı, yol haritası Faz 4 kartı) ve önceki faz belgelerinden sapmalar — gerekçeli

* **"Stripe birincil" (yol haritası kartı) → Polar MoR** (K1) — kartın 2026-09-18
  notuyla zaten güncellenmişti (Faz 1/2 belgeleri "Not"); bu belge kararı
  görev yapar. iyzico/PayTR/e-Arşiv "TR pazarı açılırsa opsiyonel" — Faz 5+.
* **"Webhook'ta idempotency = sağlayıcının event id'si" (master `:207`, Faz 3
  devir `polar:<event_id>`) → iki katman** (K4): event id teslimat katmanında
  (`odeme_olaylari`), defterde sipariş kimliği. Master'ın "çift kredi yüklemesi
  en sık hata" uyarısı iki kilitle karşılanır.
* **Faz 3 K5 "ödeme gelince `planlar` tablosu ve FK göçle gelir" → gelmez**
  (K5): kurallar kodda kalır, fiyat Polar'da, eşleme `urunler` aynasında.
  `PLANLAR[ad]` arayüzü Faz 3'ün vaat ettiği gibi değişmez.
* **Faz 3 K6 "tek kova, `sona_erme` yazılmaz" → iki kova, `sona_erme`
  düşürmede** (K3) — Faz 3 belgesi bunu "paket gelince o gün" diye açık
  bırakmıştı (`:1142-1145`); geldi.
* **Faz 3 / 1 "`kredi_hareketleri` CASCADE — KVKK Faz 4'te yeniden değerlendirir"
  → FK aynen, satır silinmez** (K9): kullanıcı satırı anonimleşir, CASCADE
  hiç tetiklenmez.
* **Faz 2 K3 "yeniden bakış Faz 4" → Faz 5 sonu** (K12); gerekçe MoR'un
  ekranları üstlenmesi.
* **Master "Meter Credits Benefit native" (`:195-196`) → kullanılmaz** (K2);
  master'ın kendi "tarife kendi katalogumuzda" kuralı (`:208`) üstün.
* **Yol haritası "deneme (trial)" → yok** (K2): ücretsiz plan denemedir.
* **Yol haritası "vergi/KDV işleme" → Polar'ın** (K1): bizde vergi hesabı yok;
  TR tarafı hizmet ihracı faturası (sahip, mali müşavir).
* **Yol haritası "başarısız ödeme / dunning" → Polar'ın** (K6).
* **JWT → oturum** (Faz 1 K3), **kuruluş yok** sapmaları aynen.

---

## Faz 4 dışı, ama burada not edilen

* **TR içi TRY satışı (iyzico/PayTR), taksit, e-Arşiv (Paraşüt vb.)** → Faz 5+,
  sahip TR pazarı açarsa; MoR'un yerine değil yanına (master `:189-192`).
* **Polar Meter Credits / usage events** → kullanılmaz (K2); bir gün Polar'ın
  portalında "kalan kredi" göstermek istenirse `customer meter` API'sine
  yalnız OKUMA amaçlı yazılabilir — defter yine bizde.
* **BYOK platform payı** → Faz 5 ölçümü (K8).
* **Kötüye kullanım, IP limitleri, içerik moderasyonu otomasyonu (NSFW
  sınıflandırıcı vb.)** → Faz 5; K11 yalnız kuralı yazar. Sağlayıcı reddi
  (`content_policy_violation`) bugün `hata` + iade — Faz 5'te sayılır.
* **Yıllık plan, kupon/indirim kodu, hediye kredisi** → Polar destekliyor;
  ürün kararı yok. `urunler.tur` CHECK'i genişlemeye açık (`text + CHECK`).
* **Ekip/kuruluş hesapları, fatura adresi alanları** → kuruluş yok (Faz 1 sapması).
* **Polar `order.refunded` → otomatik kredi düşümü** → admin kararı (K6).
* **E-posta bildirimleri** (ödeme alındı, abonelik yenilendi/bitti): Polar
  kendi e-postalarını gönderir (doğrulanmadı); bizim "iş bitti" e-postası hâlâ
  ürün kararı (Faz 2 `:2481`).
* **Vanilla yeniden bakış** → Faz 5 sonu (K12).
* **`tutarlilik`/`hibe_turu` ölçeği, dağıtımda iş kaybı, yedek tatbikatı,
  E2/E3 mini faz, video filigranı, sağlayıcı idempotency anahtarı** → Faz 3
  "açık kalemler" aynen Faz 5'e.
* **`saglayici_maliyet_usd` otomatik** → hiçbir adaptör vermiyor; Polar
  geliriyle birlikte Marj tablosunda gelir sütunu (7) — gider sütunu yine
  sahibin fatura CSV'si.
* **Doğrulanmayanlar (3. görevin ilk adımı Polar belgesiyle kapatır):** Polar
  ücret tablosunun payout/kur satırları; `external_customer_id` alan adı ve
  eski adın kaldırılma durumu; `order.paid` `billing_reason` literalleri;
  webhook yeniden deneme sayısı/süresi; sandbox API alan adı; aktif abonelikte
  yeni plan checkout'unun davranışı (yükseltme mi ikinci abonelik mi); Polar'ın
  müşteriye gönderdiği e-postalar; Polar müşteri kaydının silinme yolu
  (K9 sahibin adımı). Azure/OpenAI/Google/fal fiyatları (1b. görev, sahibin —
  1. görev onlara dokunmadı).
* **Prompt yönetmeni modu → Faz 5 planının İLK maddesi** (sahibin
  yönlendirmesi 2026-09-21, "olur onaylıyorum"): yönetmene **effort / kalite /
  düşünme** ayarı gelir ve seçime göre istek, onu karşılayabilen sohbet
  modelleri arasında **ucuz-hızlıdan pahalı-kaliteli-çok düşünene** (Claude
  gibi) yönlendirilir; ikinci adımda yönetmen **ajanlaşır** — kullanıcının
  isteğini daha iyi karşılamak için görsel ve video modellerini KENDİSİ çağırır
  (1b'nin genişlettiği katalog onun araç kümesi). Bu fazda YOK çünkü ödeme ve
  KVKK omurgası önce; kredi/defter tarafı hazır (Faz 3), model yönlendirmesi
  `ChatModel` kataloğuna kademe alanı ister — Faz 5 belgesinin işi.
* **Ölçülmeyen:** webhook gecikmesi (Polar → bizim 200; teşekkür sayfasının
  yoklama süresi buna göre ayarlanır), `silme_turu`nün R2 listeleme maliyeti
  büyük galeride, takım süresi artışı, `polar_esitle` ürün sayısı (< 20).

---

## Kaynaklar (erişim tarihi 2026-09-21)

* Master design "Ödeme Altyapısı: MoR" (2026-09-18 notu, sahibin araştırması):
  [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) `:184-214`.
* Yol haritası (Faz 0–5, Türkçe): claude.ai artifact `Lz65U9WpRQfbMeGCHDvLi5` —
  Faz 4 kartı "Ödeme, faturalama ve hukuk", çıkış kriteri cümlesi.
* Model barındırma / maliyet araştırması (2026-09-20): claude.ai artifact
  `GxN2FA5932GpJYGEgSiruL` — dört doğrulanmamış Azure fiyatı, yedi kredi ≠
  maliyet, `gpt-image-1` 2026-10-23 (OpenAI duyurusu üzerinden).
* Polar ücretleri: [polar.sh/docs/merchant-of-record/fees](https://polar.sh/docs/merchant-of-record/fees)
  (**erişilemedi**, egress engeli); ikincil: paritydeals.com "Polar Fee
  Calculator" (2026), dodopayments.com "Polar.sh Review 2026: New 5% + 50¢
  Pricing", makerkit.dev "Polar Pricing Calculator (2026)" — Starter %5 + 0,50,
  Pro 20 USD/ay %3,8 + 0,40, uluslararası +%1,5, dispute 15 USD, payout 2
  USD/ay + %0,25 + 0,25 (**payout/kur doğrulanmadı**).
* Polar webhook'ları: [polar.sh/docs/integrate/webhooks/events](https://polar.sh/docs/integrate/webhooks/events)
  ve [/delivery](https://polar.sh/docs/integrate/webhooks/delivery)
  (**erişilemedi**); ikincil: hookdeck.com "Guide to Polar Webhooks Features
  and Best Practices" (2026) — Standard Webhooks başlıkları, HMAC-SHA256,
  üstel yeniden deneme, çift teslimat uyarısı; github.com/polarsource/polar-python —
  `validate_event`, `WebhookVerificationError`, `WebhookUnknownTypeError`.
* Polar API changelog: `customer_external_id` → `external_customer_id`
  (arama özeti, **doğrulanmadı**); Customer State endpoint/webhook duyurusu
  (x.com/polar_sh, 2025-03).
* Polar sandbox: encore.dev "Using Polar with Encore.ts", docs.opensaas.sh
  "Polar" — `sandbox.polar.sh`, SDK `server="sandbox"`.
* KVKK: 6698 sayılı Kanun md. 7 (silme/yok etme/anonimleştirme), md. 9 (yurt
  dışı aktarım), md. 10 (aydınlatma), md. 11 (haklar), md. 13 (30 gün cevap);
  KVKK Kurulu 2019/9 sayılı karar (süre hesabı); Kişisel Verilerin Silinmesi,
  Yok Edilmesi veya Anonim Hale Getirilmesi Hakkında Yönetmelik (kvkk.gov.tr).
* GDPR md. 12 (1 ay), 13, 15, 17 (silme), 20 (taşınabilirlik); ePrivacy
  2002/58/EC md. 5(3) zorunlu çerez istisnası (ico.org.uk özetleri).
* TTK md. 82 (ticari defter ve belgelerin 10 yıl saklanması), VUK md. 253
  (5 yıl) — **mali müşavir teyidi gerekir**; Cumhurbaşkanı Kararı 11257
  (29/04/2026) hizmet ihracı kazanç indirimi %100 — master `:209-214`.
* Standard Webhooks spesifikasyonu: `webhook-id` yeniden gönderimde aynı
  (standardwebhooks.com — bu oturumda doğrulanmadı, K4'ün teslimat katmanı
  buna dayanır; farklıysa `odeme_olaylari` yalnız günlük olur, sipariş anahtarı
  yine korur).
