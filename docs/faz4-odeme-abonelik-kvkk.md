# Faz 4 — Ödeme (Polar MoR), paketler ve abonelik, hesap silme / dışa aktarma, hukuki metinler: görev listesi

**Tarih:** 2026-09-22 · **Durum:** **3/8** (plan PR #69 `faz4/plan`, sahip 2026-09-21'de merge etti; görevler `faz4/<slug>` dallarında, her biri bir PR; **1b** görevi 2026-09-21'de sahibin yönlendirmesiyle eklendi, 7 → 8; **1b'nin model listesi ve `1b-A`…`1b-G` kararları 2026-09-22'de sahipten geldi; on birinci sayı aynı gün ÖLÇÜLDÜ ve `catalog.py`ye yazıldı — o görev artık uygulanabilir**) · **Karar:** K1–K12 **kabul edildi 2026-09-21** (PR #69 sahip tarafından aynen merge edildi — Faz 3'ün deseni; madde madde değişiklik gelmedi) · **Önceki faz:** [faz3-kredi-defteri-filigran.md](faz3-kredi-defteri-filigran.md) (7/7 ✅, kapanış 2026-09-21, PR #56–#68)
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
bağımsız, omurgayla paralel gidebilir — sahibin sıralı model listesi
2026-09-22'de geldi, artık bekleyen girdisi yok),
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
| Checkout | `POST /v1/checkouts/` → barındırılan ödeme sayfası URL'si; alanlar `products`, **`external_customer_id`** (eski `customer_external_id` KULLANIMDAN KALDIRILDI — API changelog), `customer_email`, `metadata`, `success_url` | **SDK 0.32.0 kaynağıyla doğrulandı (3. görev, 2026-09-21):** `models/checkoutcreate.py` `external_customer_id` var, `customer_external_id` yok; `customer_email`, `metadata`, `success_url`, `products` alanları modelde |
| Müşteri | `external_id` = bizim `kullanicilar.id`; Customer Session API → **müşteri portalı** bağlantısı (abonelik iptali, kart güncelleme, fatura indirme Polar'da) | `external_id` **SDK'da doğrulandı** (`Customer`/`OrderCustomer`/`SubscriptionCustomer.external_id`, NULL'lanabilir); portal akışı (`customer_sessions`) SDK'da var, davranışı 4. görevde ölçülür |
| Webhook | **Standard Webhooks**: başlıklar `webhook-id`, `webhook-timestamp`, `webhook-signature` (`v1,<base64>`; HMAC-SHA256 `{id}.{timestamp}.{body}`); zaman toleransı **±5 dk**; Python SDK `polar_sdk.webhooks.validate_event(payload, headers, secret)` = `standardwebhooks.Webhook(base64(secret)).verify` (ham sır base64'lenir → kütüphane çözer; `whsec_` öneki varsa kütüphane soyar) → `WebhookVerificationError`; bilinmeyen tür `WebhookUnknownTypeError` (imza doğrulandıktan sonra); başarısız teslimat **üstel geri çekilmeyle saatlerce yeniden denenir**, aynı olay birden çok kez GELEBİLİR | **SDK 0.32.0 + standardwebhooks 1.1.0 kaynağıyla doğrulandı** (`polar_sdk/_webhooks/__init__.py`, `standardwebhooks/webhooks.py`); yeniden deneme süresi/sayısı ve panelden "yeniden gönder"in `webhook-id`yi koruyup korumadığı **doğrulanmadı** (K4 bu yüzden sipariş anahtarına da dayanır) |
| Olay türleri | **35 tür (SDK `WebhoookPayload`):** `checkout.created/updated/expired`, `customer.created/updated/deleted/state_changed`, `customer_seat.assigned/claimed/revoked`, `member.created/updated/deleted`, `order.created/updated/paid/refunded`, `subscription.created/updated/active/canceled/uncanceled/revoked/past_due`, `refund.created/updated`, `product.created/updated`, `benefit.created/updated`, `benefit_grant.created/cycled/updated/revoked`, `organization.updated` | **SDK 0.32.0 kaynağıyla doğrulandı** (`models/webhookeventtype.py`); biz dokuzunu işleriz (`odeme.ISLENEN_TURLER`), ötekiler 200 `atlandi` |
| `order.paid` alanları | `billing_reason` = `purchase` \| `subscription_create` \| `subscription_cycle` \| `subscription_update` (K6 bunu okur); `product_id` (NULL'lanabilir), `subscription_id` (NULL'lanabilir), `customer_id`, `customer.external_id`, **`total_amount`** (`amount` DEĞİL; ayrıca `net_amount`, `tax_amount`, `refunded_amount`), `currency`, `metadata`, `status` (`paid`/`refunded`…) | **SDK 0.32.0 kaynağıyla doğrulandı** (`models/order.py`, `orderbillingreason.py`); Subscription: `status` ∈ `incomplete\|incomplete_expired\|trialing\|active\|past_due\|canceled\|unpaid\|paused`, `current_period_end`, `cancel_at_period_end`, `ends_at`, `ended_at`, `canceled_at`, `product_id` |
| Sandbox | `sandbox.polar.sh` ayrı ortam, ayrı jeton ve webhook sırrı; SDK `server="sandbox"` → `https://sandbox-api.polar.sh`, production `https://api.polar.sh`; test kartıyla gerçek para yok | sunucu adları **SDK'da doğrulandı** (`sdkconfiguration.SERVERS`); test kartı ve panel akışı **doğrulanmadı** (sahibin sandbox adımı) |
| Kabul edilebilir kullanım | AI üretim araçları "ek incelemeye tabi"; NSFW, deepfake/face swap, ses klonlama, telif/marka ihlali YASAK — kullanım şartlarına ve moderasyona yazılmadan yayına çıkılmaz | master `:201-204` |
| Python SDK | `polar-sdk` (PyPI; `polarsource/polar-python`), Pydantic ≥ 2.11 modelleri, senkron + async istemci; bağımlılıkları `httpx ≥ 0.28.1`, `standardwebhooks ≥ 1,<2`, `jsonpath-python`; saf Python tekerleği ~0,9 MB | **PyPI'dan indirildi ve okundu 2026-09-21:** 0.32.0, openapi `2026-04`; pin `polar-sdk==0.32.*` (requirements.txt, gerekçesiyle) |

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
| `openai-gpt-image-1` katalogda; 4 fiyat "doğrulanamadı"; 7 kredi ≠ maliyet | `catalog.py:588-602`; `tools/tarife_kontrol.py` | Girdi kaldırılır (2026-10-23 öncesi) — ✅ 1; **2026-09-22'de on biri de kapandı** (onu fiyat kaynağından okundu, on birincisi — `azure-gpt-image-2` kalite jetonu — yayınlanmadığı için canlı anahtarla ÖLÇÜLDÜ: 1/11/42, `catalog.py`ye yazıldı) → `tarife_kontrol` bekçisi 1b'nin kod PR'ında 4 → **0** | 1, 1b |
| Katalog **9 görsel** (`azure`, `openai`, `gemini`, `azure-mai`, `azure-flux`) + **6 video** (`gemini`, `fal`); ücretsiz plana 1 kredilik model yok; `emeklilik` alanı yok | `catalog.py` `IMAGE_MODELS`/`VIDEO_MODELS`; `*_client.py` adaptörleri | **13 görsel + 10 video**, kaliteli/popüler → ucuz sırasıyla; sağlayıcı kümesi DEĞİŞMİYOR (mevcut beş kimlik — yeni adaptör yok, Runware/Replicate masadan kalktı); `azure-flux-2-flex` silinir; ücretsiz planın 1 kredilik modeli `fal` FLUX.1 schnell; `emeklilik: date` + `tarife_kontrol` "30 gün" satırı | 1b |
| Plan kapısı İKİLİ (`free` ↔ ücretli) ve anahtar kaynağından bağımsız; `ImageModel.plan` her girdide `free` | `services/planlar.py` `kapsiyor`; `services/modeller.py` | **Basamaklı** (`Plan.rank`: free<temel<pro) ve **kendi anahtarı eşiği aşar** (`kapsiyor` anahtar kaynağını alır); `Plan.video` ve filigran kuralı anahtar kaynağından BAĞIMSIZ kalır (K7) | 1b |
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

## 1b. Katalog genişletme — 13 görsel + 10 video model, sağlayıcıdan bağımsız (PR'lar: `faz4/katalog-genisletme` ✅, `faz4/1b-plan-kapisi`, `faz4/1b-fiyat-duzeltme`, `faz4/1b-yeni-girdiler`)

**Kapsam.** Sahibin 2026-09-21 yönlendirmesiyle eklendi; **sıralı liste ve altı
ürün kararı 2026-09-22'de geldi** — bu bölüm o oturumun çıktısı ve artık bir
niyet beyanı değil, uygulanabilir bir tarif. Bugünkü katalog **9 görsel + 6
video** ve sağlayıcı ağırlığı Azure'da (5 girdi). Azure bundan sonra TEK ana
sağlayıcı DEĞİL: katalog **13 görsel + 10 video** modele çıkıyor, en
kaliteli/popüler olandan ucuza doğru sıralı.

**YENİ SAĞLAYICI YOK** (sahip, 2026-09-22). Mevcut beş kimlik yetiyor:
`azure_image`, `azure_foundry`, `openai`, `gemini`, `fal`. Runware ve Replicate
MASADAN KALKTI ve gerekçesi ölçülebilir — fal bir TOPLAYICI, listedeki her fal
satırı onun tek anahtarıyla geliyor. Yani bu görev yeni `*_client.py`, yeni
gizli anahtar, yeni dış konak ve `.env.example` ↔ `ALTYAPI` bekçisi
(`tests/test_docker_kapisi.py`) açmıyor. §1b'nin ilk yazımındaki "Runware
gelirse yeni istemci" dalı bu yüzden düştü; risk bölümünün yarısı onunla
birlikte düştü.

### Kararlar (sahip, 2026-09-22)

Faz düzeyindeki K1–K12'den AYRI numaralanıyor (`1b-A`…`1b-G`): o küme
2026-09-21'de PR #69 ile kabul edildi ve yeniden açılmıyor, bunlar yalnız bu
görevin içine bakan kararlar.

* **1b-A · Kendi anahtarı plan kapısını AŞAR.** `planlar.kapsiyor` bugün
  anahtarın kimin olduğunu BİLEREK sormuyor (K7) ve bu bugüne kadar zararsızdı,
  çünkü `ImageModel.plan` her girdide `"free"`. Bu görev o alanı VERİ yapıyor —
  ve o an, kendi `gemini` anahtarını girmiş ücretsiz kullanıcı bize hiçbir
  maliyeti olmayan bir modeli göremez hâle gelirdi. Kapı bu yüzden anahtar
  kaynağına bakar: `kapsiyor(plan, spec, anahtar_kaynagi)`, model eşiği
  YALNIZ `platform` anahtarıyla koşan işlere uygulanır.

  İKİ ŞEY DEĞİŞMİYOR ve ikisi de K7'nin taşıyıcı gerekçesi: (1) `Plan.video`
  kapısı anahtar kaynağından BAĞIMSIZ kalır — sunucuda video işleme aracı yok
  (ffmpeg imaja girmiyor), ücretsiz video filigransız çıkardı ve anahtarın
  kimin olduğu filigranın yokluğunu değiştirmez; (2) **filigran kuralı aynen**
  — `services/isci._filigranlanir` yalnız `PLANLAR[plan].filigran` ve
  `spec.kind`e bakıyor, anahtar kaynağına değil. Kendi anahtarıyla pahalı model
  kullanan ücretsiz kullanıcı yine FİLİGRANLI çıktı alır.

  Çağıran üç yer var ve üçü de kimlik sözlüğünü zaten görüyor, yani parametre
  taşınabilir: `services/modeller.model_available`, `services/modeller.sebep`,
  `services/kapilar.check_plan`.

* **1b-B · Plan kapısı BASAMAKLI (`free` < `temel` < `pro`).** Bugünkü
  `kapsiyor` ikili: `spec.plan != "free"` ise `temel` de `pro` da geçiyor, yani
  **"yalnız pro" bir model ifade EDİLEMİYOR**. 13 + 10 girdide fiyat farkı 95
  kata çıkıyor (`fal-flux-1-schnell` 1 kredi ↔ `fal-seedance-2-5` 95 kredi/sn);
  ikili kapı, `temel` planın aylık hibesini tek üretimde eritebilecek bir
  modeli o plana açık bırakırdı. `Plan` bir `rank: int` alanı kazanır
  (free=0, temel=1, pro=2), `kapsiyor` eşik karşılaştırması yapar.
  `Plan.video` AYRI eksende kalır — basamağa katlamak, video kuralının
  gerekçesini (filigran yokluğu) bir fiyat sıralamasının içinde görünmez
  kılardı.

* **1b-C · Model başına TEK yol; popülerlerde birinci taraf.** Katalog satırı
  tek `provider` + tek `credential` taşıyor. Aynı modeli platformda fal'dan,
  kullanıcıda doğrudan sağlayıcıdan sunmak, seçicide **iki kart** demekti —
  `catalog.py`nin "MODEL BAŞINA İKİ GİRDİ de reddedildi" dediği durumun
  kendisi. Bu yüzden BYOK'lanabilir modeller (OpenAI, Gemini) katalogda kendi
  sağlayıcılarından duruyor: sahip platform anahtarını aynı kimliğe koyar,
  kullanıcı da aynı kimliğe kendi anahtarını girer ve
  `services/platform_anahtari.birlestir`in çözüm sırası (kullanıcı → platform →
  yok) hiçbir kod değişmeden çalışır. fal YALNIZ BYOK'lanmayacak modelleri
  taşır (Kling, Wan, PixVerse, MiniMax, Seedance, FLUX).

  BEDELİ ÖLÇÜLDÜ ve kabul edildi: fal, Veo 3.1'i sessiz modda 0,20 USD/sn'ye
  veriyor, Google doğrudan 0,40. Fark bilinçli bırakılıyor — Veo satırının
  BYOK'lanabilir kalması, iki kart göstermekten ve aynı modelin iki yüzünün
  farklı davranmasından (boyut jetonları, `max_n`, ses) daha değerli.

* **1b-D · FLUX.2 flex SİLİNİR.** Azure'ın fiyat tablosu (aşağıda, canlı
  okundu) flex'i düz 0,05 USD/MP'den faturalıyor → 1024×1024'te **20 kredi**,
  yani FLUX.2 pro'nun (9) **2,2 katı**. Üstelik `hizli`/`dengeli`/`detayli`
  ÜÇÜ DE AYNI paraya: Azure adım sayısına bakmıyor, megapiksele bakıyor —
  `azure_flux_client._FLEX_QUALITY`nin `steps`/`guidance` çiftlerine çözdüğü
  eksen faturada KARŞILIĞI OLMAYAN bir eksen. Aynı ailenin daha iyi modeli
  daha ucuzken flex'i seçicide tutmanın gerekçesi kalmıyor; girdi
  `openai-gpt-image-1`in duruşuyla SİLİNİR.

  Silme `azure_flux_client.py`ye kadar iner: `_DEPLOYMENTS["FLUX.2-flex"]`,
  `_FLEX_QUALITY` ve `quality_for` dalı ölü kod olur, `tests/test_azure_flux_client.py:28,65`
  ve `tests/test_catalog.py:684` ile `bundled/i18n/{tr,en}.json:648` birlikte
  düşer. Adaptörün kendisi KALIR — FLUX.2 pro onu kullanıyor.

* **1b-E · GPT Image 2.5 eklenir, varsayılan DEĞİŞMEZ.** OpenAI 2026-09-08'de
  `gpt-image-2.5-flare` (hızlı) ve `-sunburst` (düzenleme hassasiyeti)
  modellerini çıkardı; `gpt-image-2` emekli DEĞİL (varsayılan anlık görüntü
  `gpt-image-2-2026-04-21`). İkisi de listeye giriyor, `DEFAULT_IMAGE_MODEL`
  `azure-gpt-image-2` KALIYOR. Gerekçe iki katmanlı: (1) varsayılanı kaydırmak
  E2E model seçici çapalarını, `test_catalog` varsayılan iddialarını ve
  `prefs` doğrulamasını birlikte değiştirir; (2) 2.5'in yetenek jetonları bu
  depoda DOĞRULANMADI ve doğrulanmamış jeton beyan etmek arayüzde seçilebilir
  bir 400 demek — `gpt-image-2` girdisinin "alt sınır" kararının aynısı.

* **1b-F · Kredi çapası SABİT: `KREDI_USD_CAPASI = 0,005`.** Çapa bir ORAN,
  sağlayıcının fiyatı değil; değiştirmek katalogdaki HER satırı ve admin marj
  tablosunu birden kaydırırdı. **GÜNCELLEME 2026-09-22:** gpt-image-2'nin
  kalite maliyeti o gün ÖLÇÜLDÜ (aşağıda) ve krediler 4/8/16 → **1/11/42**
  oldu; çapa değişmedi ama gerekçesi öldü — artık seçilmiş bir oran, türetilmiş
  değil. Yuvarlama EN YAKIN tam sayıya.

* **1b-G · Kalite başına plan kapısı YOK (2026-09-22).** Ölçüm `high`ı 42
  krediye çıkarınca "high yalnız `pro`da olsun" seçeneği masaya geldi ve
  REDDEDİLDİ. Üç gerekçe: (1) `ImageModel.plan` model başına TEK alan ve
  `kapsiyor` modeli alıyor, kaliteyi değil — kademe kapatmak yeni bir eksen
  demek ve o eksen `model_available` · `sebep` · `check_plan` üçlüsünden ön
  yüze kadar iner; (2) ön yüz bugün model KARTINI soluklaştırıyor, `<option>`
  soluklaştırmıyor, yani görünen ama yasak bir kalite "seçilebilir 403" olurdu
  — bu dosyanın her yerde kaçındığı şeyin kalite eksenindeki hâli; (3) kredi
  zaten caydırıcı ve GÖRÜNÜR: seçicide "42 kredi" yazıyor, varsayılan da
  `medium` (11). Soru kapanmadı, ERTELENDİ: ödeme açıldıktan sonra `isler`
  tablosu "ücretsiz kullanıcıların kaçı `high` seçiyor" sorusunu veriyle
  cevaplar; o güne kadar kapı eklenmez.

### Sıralı görsel listesi (13) — kaliteli/popüler → ucuz

Sıra ARAYÜZ sırası. Fiyatlar 2026-09-22'de kaynağından okundu; kredi =
birim maliyet ÷ `KREDI_USD_CAPASI`, yuvarlanmış.

| # | model | sağlayıcı | kimlik | birim maliyet (USD) | kredi | BYOK |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Azure · gpt-image-2 ⭐ | `azure` | `azure_image` | 30/1M jeton · **jeton sayısı ölçülmedi** | 4/8/16 (aynen) | — |
| 2 | OpenAI · GPT Image 2.5 Sunburst | `openai` | `openai` | 30/1M jeton · ölçülmedi | ölçümle | ✅ |
| 3 | OpenAI · GPT Image 2.5 Flare | `openai` | `openai` | 30/1M jeton · ölçülmedi | ölçümle | ✅ |
| 4 | Gemini · Nano Banana Pro | `gemini` | `gemini` | 0,134 (1K/2K) · 0,24 (4K) | 27 / 48 ✓ | ✅ |
| 5 | OpenAI · gpt-image-2 | `openai` | `openai` | Azure ile aynı | 4/8/16 (aynen) | ✅ |
| 6 | Gemini · Nano Banana 2 | `gemini` | `gemini` | 0,067 / 0,101 / 0,151 | **13 / 20 / 30** | ✅ |
| 7 | Microsoft · MAI-Image 2.5 Pro | `azure-mai` | `azure_foundry` | 0,0481 | 10 ✓ | — |
| 8 | Black Forest Labs · FLUX.2 pro | `azure-flux` | `azure_foundry` | 0,045 (2 MP) | **9** | — |
| 9 | Microsoft · MAI-Image 2.6 | `azure-mai` | `azure_foundry` | 0,0389 | 8 ✓ | — |
| 10 | Alibaba · Qwen Image | `fal` | `fal` | 0,02/MP → 0,04 | **8** | — |
| 11 | ByteDance · Seedream V4 | `fal` | `fal` | 0,03/görsel | **6** | — |
| 12 | Microsoft · MAI-Image 2.6 Flash | `azure-mai` | `azure_foundry` | 0,0195 | 4 ✓ | — |
| 13 | Black Forest Labs · FLUX.1 schnell | `fal` | `fal` | 0,003/MP | **1** | — |

⭐ `DEFAULT_IMAGE_MODEL` · ✓ bugünkü değer doğru çıktı, değişmiyor.

**13. satır ücretsiz planın 1 kredilik modeli** — §1b'nin ilk yazımının
"masada" dediği girdi. fal 1 MP'ye yuvarlıyor, yani jeton kümesi 1 MP'nin
ALTINDA tutulmak zorunda; 1024×1024 (1,048 MP) iki megapiksel sayılır ve
kredi 1 değil 2 olur. Ücretsiz planın E2E'si bu modelle koşar.

**SAYININ HESABI:** bugünkü 9 görsel girdisinden `azure-flux-2-flex` silinir
(1b-D), kalan 8'i aynen listede; üstüne 5 yeni girdi (GPT Image 2.5 × 2, Qwen
Image, Seedream V4, FLUX.1 schnell) → **13**. Video tarafında silinen yok:
bugünkü 6 girdi + 4 yeni (Seedance 2.5, FLUX 3, Kling V3 Pro, MiniMax H3) →
**10**.

### Sıralı video listesi (10) — kaliteli/popüler → ucuz

Kredi SANİYE başına (`cost_for`un `kind="video"` dalı).

| # | model | sağlayıcı | kimlik | birim maliyet (USD/sn) | kredi/sn | BYOK |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ByteDance · Seedance 2.5 | `fal` | `fal` | ~0,473 (720p sesli) | **95** | — |
| 2 | Gemini · Veo 3.1 | `gemini` | `gemini` | 0,40 (720p/1080p) · 0,60 (4K) | 80 ✓ / 120 | ✅ |
| 3 | Black Forest Labs · FLUX 3 | `fal` | `fal` | 0,17 (720p) · 0,29 (1080p) | **34 / 58** | — |
| 4 | Kling · V3 Turbo Pro | `fal` | `fal` | 0,14 | 28 ✓ | — |
| 5 | Kling · V3 Pro | `fal` | `fal` | 0,112 sessiz · 0,168 sesli | **22 / 34** | — |
| 6 | Gemini · Veo 3.1 Fast | `gemini` | `gemini` | 0,10 (720p) · 0,12 (1080p) | **20 / 24** | ✅ |
| 7 | PixVerse · C1 | `fal` | `fal` | 0,065 (720p sesli) · 0,120 (1080p sesli) | 13 / 24 ✓ | — |
| 8 | Alibaba · Wan 3.0 | `fal` | `fal` | 0,05 / 0,10 / 0,20 | 10 / 20 / 40 ✓ | — |
| 9 | MiniMax · H3 | `fal` | `fal` | 0,05 (480p) · 0,06 (768p) · 0,13 (2K) · 0,16 (4K) | **10 / 12 / 26 / 32** | — |
| 10 | Gemini · Veo 3.1 Lite ⭐ | `gemini` | `gemini` | 0,05 (720p) · 0,08 (1080p) | **10 / 16** | ✅ |

⭐ `DEFAULT_VIDEO_MODEL` · ✓ bugünkü değer doğru çıktı, değişmiyor.

**SIRA İLE VARSAYILAN KODDA AYRI, YORUMDA DEĞİL.** `catalog.py`nin başlığı
"SIRA ANLAMLI: … ilk girdi varsayılan" diyor, ama bu yalnız bugünkü
yerleşimin tarifi: `DEFAULT_IMAGE_MODEL`/`DEFAULT_VIDEO_MODEL` ayrı SABİTLER
ve hiçbir kod demetin indeks 0'ına bakmıyor (`catalog.image_model` id ile
arıyor). Liste kaliteli→ucuz sıralanınca varsayılanlar 1. ve 10. sıraya
düşüyor, ikisi de yerinde kalıyor — yalnız o yorum düzeltilir. Bu, bu PR'daki
TEK belge-kod ayrışması ve düzeltilmezse bir sonraki okuyan "varsayılan
Seedance" sanır.

### 1. görevden devreden on bir sayı — ON BİRİ DE KAPANDI

Dört "doğrulanamadı" notu ve yedi kredi ≠ maliyet satırı. Kaynaklar
2026-09-22'de okundu; Azure'ın JS ile çizilen tablosu tarayıcıyla açıldı (ilk
turda `$-` dönüyordu, `tools/tarife_kontrol.py`nin varlık sebebi buydu).

| satır | bulunan | kredi olmalı | katalogda | sonuç |
| --- | --- | --- | --- | --- |
| `azure-mai-image-2-6` fiyatı | 38 USD/1M × 1024 jeton = 0,0389 | 8 | 8 | ✅ not düşer |
| `azure-mai-image-2-6-flash` fiyatı | 19 USD/1M × 1024 jeton = 0,0195 | 4 | 4 | ✅ "GEÇİCİ" düşer, tahmin tutmuş |
| `azure-flux-2-pro` fiyatı | ilk MP 0,03 + sonraki 0,015 → 2 MP = 0,045 | 9 | 16 | ⚠️ düzeltilir |
| `azure-flux-2-flex` fiyatı | 0,05/MP × 2 MP = 0,10 | 20 | 6/10/16 | ⚠️ girdi SİLİNİR (1b-D) |
| `gemini-nano-banana-2` 1K | 0,067 | 13 | 6 | ⚠️ düzeltilir |
| `gemini-nano-banana-2` 2K | 0,101 | 20 | 6 | ⚠️ düzeltilir |
| `gemini-nano-banana-2` 4K | 0,151 | 30 | 12 | ⚠️ düzeltilir |
| `azure-flux-2-pro` kredisi | (üstteki satır) | 9 | 16 | ⚠️ düzeltilir |
| `gemini-veo-3-1-lite` sn | 0,05 (720p) | 10 | 16 | ⚠️ düzeltilir |
| `gemini-veo-3-1-fast` sn | 0,10 (720p) | 20 | 30 | ⚠️ düzeltilir |
| `azure-gpt-image-2` low | 196 jeton × 30 USD/1M = 0,0059 | 1 | 4 | ⚠️ düzeltildi |
| `azure-gpt-image-2` medium | 1.756 jeton = 0,0527 | 11 | 8 | ⚠️ düzeltildi |
| `azure-gpt-image-2` high | 7.024 jeton = 0,2107 | 42 | 16 | ⚠️ düzeltildi |

**ON BİRİNCİ SAYI ÖLÇÜLDÜ (2026-09-22).** `gpt-image-2`nin kalite başına ÇIKTI
JETONU SAYISI hiçbir resmî yerde yayınlanmamış: Azure ve OpenAI aynı birim
fiyatı veriyor (30 USD/1M çıktı jetonu) ama `low`/`medium`/`high` karşılığı
yok, üçüncü taraf kaynaklar da açıkça "eski modellerin statik tablosundan
çıkarım yapmayın" diyor. O yüzden web'den değil ÖLÇÜMLE kapandı — bu deponun
MAI'de yaptığının aynısı: canlı anahtarla 1024×1024'te üç üretim, yanıttaki
`usage.output_tokens` **196 / 1.756 / 7.024** (`output_tokens_details.image_tokens`
aynı sayı). Çapayla **1 / 11 / 42**; katalog 4/8/16 diyordu, yani `high` 2,6 kat
EKSİK fiyatlanmıştı ve `azure-gpt-image-2` varsayılan model. Uyarının haklılığı
ölçüldü: `gpt-image-1`in tablosu (272/1056/4160) tutmuyor. Düzeltme `catalog.py`de
İKİ girdiye birden yazıldı (Azure ve OpenAI ikizi aynı modeli satıyor).

**ÖLÇÜM ÇAPANIN GEREKÇESİNİ ÖLDÜRDÜ.** `KREDI_USD_CAPASI = 0,005` bu dosyaya
"Azure `medium` = 8 kredi ≈ 0,04 USD" denkleminden girmişti — ve ölçüm
`medium`ı 0,04 değil **0,0527 USD** buldu. Aynı cümleyi yeni sayıyla yeniden
türetsen çapa 0,0066 olurdu. Çapa yine de 0,005'te KALIYOR (1b-F): o bir oran,
sağlayıcının fiyatı değil. Ama artık **seçilmiş** bir oran, türetilmiş değil —
hiçbir model onu tanımlamıyor, modeller ona bölünüyor. Bu cümlenin `catalog.py`de
BEŞ blokta tekrarlanan eski hâli (`:458, :479, :483, :685, :763, :899, :903,
:1008`) aynı turda temizlendi; çürümüştü ve bekçisi yoktu, çünkü CLAUDE.md
§5'in "türetilen her şeyin bekçisi bir testtir" kuralı sayıyı koruyor,
sayının GEREKÇE CÜMLESİNİ değil.

**YUVARLAMA EN YAKINA.** 10,54 → **11**, 10 değil. Ayrımı gösteren tek kademe
bu: `low` (1,18) ve `high` (42,14) iki kuralda da aynı sayıyı veriyor, oysa
`medium` aşağı yuvarlansa dosyanın öteki girdileriyle çelişirdi (26,8 → 27,
7,78 → 8, 9,62 → 10 hepsi en yakın). Kural artık `KREDI_USD_CAPASI` yorumunda
yazılı ki bir sonraki düzeltme hangisini uygulayacağını bilsin.

`tools/tarife_kontrol.py` bekçisi bu satırdan ETKİLENMİYOR (gpt-image-2'nin
kredisinde "doğrulanamadı" notu hiç yoktu, bekçi dört Azure MAI/FLUX girdisini
sayıyor); dördün sıfıra inmesi 1b'nin kod PR'ına bağlı — FLUX.2 pro 16 → 9,
iki MAI notunun düşmesi ve `azure-flux-2-flex`in silinmesi (1b-D) orada.

**YAN ÜRÜN — doğru çıkan beş satır** (bu PR'da DEĞİŞMEZ, ama artık kaynaklı):
Nano Banana Pro 27/48, Veo 3.1 80, Kling V3 Turbo Pro 28, Wan 3.0 10/20/40,
PixVerse C1 13/24. Sonuncusu SESLİ fiyattan türemiş ve tutuyor — adaptör sesi
açık gönderiyor, yani etiket faturayı doğru anlatıyor.

### Düzeltilmiş krediler planları zorluyor — 4. görevin girdisi

Ücretsiz plan aylık 200 kredi (`KROMIS_FREE_AYLIK_HIBE`), `temel` 1.000,
`pro` 3.000 (yer tutucular, `services/planlar.py`). Düzeltilmiş tarifeyle:

* Veo 3.1 ile **8 saniyelik tek klip = 640 kredi** → `temel`in ayının %64'ü.
* Seedance 2.5 ile 5 saniye = 475 kredi.
* Nano Banana 2 düzeltilince ücretsiz kullanıcı ayda 33 değil **15** görsel
  alıyor (1K).

Basamaklı kapı (1b-B) bunun bir yarısını çözüyor: pahalı video `pro` eşiğine
konur. Öteki yarısı HİBE SAYILARI ve o bu görevin kararı DEĞİL — sahip 4.
görevde Polar ürünlerini yazarken verir (K5/K6). Burada yalnız ölçü kayda
geçiyor ki o gün tahminle değil sayıyla karar verilsin.

**Dokunulan.** `catalog.py` (+13 girdi, −1 girdi, `emeklilik: date` alanı,
kaynaklı fiyat yorumları, sıra yorumu), `services/planlar.py` (`Plan.rank`,
`kapsiyor` üçüncü parametre), `services/modeller.py` + `services/kapilar.py`
(anahtar kaynağını `kapsiyor`a taşır), `azure_flux_client.py` (flex kalkar),
`bundled/i18n/{tr,en}.json` (`model.<id>.note` her yeni girdi için, 20-110
karakter, adı tekrar etmez), `tools/tarife_kontrol.py` (+emeklilik satırı),
`tests/test_catalog.py`, `tests/test_planlar.py`, `tests/test_modeller.py`,
`tests/test_araclar.py` (4 → 0), `tests/test_azure_flux_client.py`,
`docs/ozellikler.md`, `README*.md` sağlayıcı satırı, `docs/graflar/*`.

**Testler / bekçiler.** Katalog bekçileri aynen (`test_catalog`: her girdinin
notu iki dilde var, adı tekrar etmiyor, jetonlar tutarlı, kısa etiket
çakışması); i18n eşliği (`test_i18n`); `tarife_kontrol` ↔ bağımsız tarama
(**0** — on birinci sayı 2026-09-22'de ölçüldü, dört Azure notunun dördü de bu
görevde düşüyor); `emeklilik` bekçisi tarih yamalı;
**yeni: basamak bekçisi** (`Plan.rank` ↔ `PLANLAR_KUMESI` sırası, `kapsiyor`
her (plan, model.plan, anahtar_kaynagi) üçlüsünde beklenen cevabı verir) ve
**BYOK bekçisi** (kendi anahtarıyla plan eşiği aşılır, ama `Plan.video` ve
filigran AŞILMAZ — K7 bu testle mandallanır); E2E model seçici (seçicide her
`available` model bir satır; ücretsiz planın E2E'si `fal-flux-1-schnell` ile).
Yeni adaptör YOK, yani yeni tel formatı/hata çevirisi testi de yok.

**Risk.** Düşük-orta — ilk yazımdakinden düşük, çünkü yeni sağlayıcı dalı
kalktı (yeni gizli anahtar, dış konak, `ALTYAPI` bekçisi, Sentry/egress notu
yok). Kalan iki risk: (1) **23 satır seçicide kaydırma ve mobil düzen**
(ölçülmedi — gerekirse sağlayıcıya göre gruplama, ayrı küçük PR); (2)
**`kapsiyor` imzasının değişmesi** üç çağıranı birden etkiliyor ve biri
unutulursa kapı sessizce gevşer — bekçi bu yüzden üçlü kombinasyonu tarıyor,
tek yol değil. Düşük fiyatlı satır (1 kredi) platform zararı olabilir; kredi
hesabı yorumda kaynaklı.

**Çıkış ölçütü.** Katalog 13 görsel + 10 video, her girdide sağlayıcı,
kaynaklı maliyet (kaynak + erişim tarihi yorumda) ve kredi; `azure-flux-2-flex`
yok; `tarife_kontrol.py` **0 satır** basıyor (on birinci sayı 2026-09-22'de
ölçüldü, kalan dört Azure notu fiyat PR'ında düşüyor); Azure'a özel varsayım yok; kendi anahtarıyla
plan eşiği aşılıyor ama filigran ve video kuralı aşılmıyor (bekçili); i18n
eşliği; takım yeşil (E2E dahil).

### Görev DÖRT PR'a bölündü (sahip, 2026-09-22)

İlk yazımda tek PR öngörülüyordu. Bölme sahibin kararı ve gerekçesi ölçüldü:
tasarım PR'ında tarife TEK bir modelde değişti ve **yedi test birden düştü**,
hepsi ayrı dosyalarda. Fiyat düzeltmeleri adaptöre (`azure_flux_client`) ve iki
test dosyasına daha iniyor, `kapsiyor` imzası üç çağıranı birden etkiliyor.
Tek PR'da bunlar toplansa hangi kırmızının hangi değişiklikten geldiği
okunamazdı.

| PR | dal | kapsam | bağımlılık |
| --- | --- | --- | --- |
| **#74 ✅** | `faz4/katalog-genisletme` | tasarım, kararlar, ölçülen kredi | — |
| **B** | `faz4/1b-plan-kapisi` | `Plan.rank`, `kapsiyor` üçüncü parametre, üç çağıran, iki yeni bekçi | `catalog.py`'ye DOKUNMAZ |
| **C** | `faz4/1b-fiyat-duzeltme` | on sayı, flex silme, `tarife_kontrol` 4 → 0 | — |
| **D** | `faz4/1b-yeni-girdiler` | 5 görsel + 4 video, `emeklilik`, i18n, E2E çapaları | **C'den sonra** |

B ile C paralel gidebilir (dosya kümeleri kesişmiyor); D ile C aynı katalog
satırlarını yazdığı için sıralı.

**KAPI ÖNCE, VERİ SONRA.** B'nin C/D'den önce gelmesi sıra tercihi değil,
1b-A'nın gereği: `ImageModel.plan` veri olduğu an kapı yerinde olmalı, yoksa
kendi anahtarını girmiş ücretsiz kullanıcı bir tur boyunca o modeli göremez.
Bu yüzden B **hiçbir davranışı değiştirmiyor** — her girdi hâlâ `plan="free"`,
basamak ve BYOK ekseni boşta çalışıyor. PR'ın tamamı makine + bekçi.

**Yapıldığında (B, 2026-09-22) — sapmalar.** İki yerde tariften SAPILDI,
ikisi de ölçülmüş gerekçeyle:

(a) **`kapsiyor`un üçüncü parametresi dizge DEĞİL bool** (`platform_anahtariyla`).
1b-A `kapsiyor(plan, spec, anahtar_kaynagi)` diyordu; o imza
`platform_anahtari.KAYNAK_PLATFORM`ı ithal etmeyi gerektiriyor ve o modül
`depo_kimlik_bilgisi` üzerinden SQLAlchemy'yi içeri çekiyor — oysa
`services/planlar.py`nin dosya başlığı "**Saf: DB yok, cümle yok**" diyor.
Karşılaştırma çağıranlara taşındı; ikisi de o modülü zaten ithal ediyor.

(b) **Parametrenin öntanımlı değeri YOK ve anahtar sözcüklü.** Tarif öntanımdan
söz etmiyordu; öntanımlı `None`/`False` verilseydi, unutulan bir çağıran
"platform değil" diye okunup **model eşiğini sessizce atlardı** — bölümün kendi
risk notunun ("biri unutulursa kapı sessizce gevşer") tarif ettiği kusur.
Öntanımsız imzada unutulan çağıran `TypeError` veriyor; bekçisi
`test_kapsiyor_has_no_default_for_the_key_source_so_a_forgotten_caller_is_loud`.

Bir de **tarifte olmayan bir iş** çıktı: `director_context` kimlik sözlüğünü
`configured_map`e verip ikinci kez çözüyordu. `platform_anahtari.kaynak`
`kaynaklar` alanını taşımayan düz bir sözlük görseydi her anahtarı `kullanici`
sayar ve **plan eşiği yönetmen menüsünde sessizce düşerdi**. Sözlük artık bir
kez çözülüyor (`credstore.degerler`), ikisi de aynı nesneye bakıyor.

`_filigranlanir`ın bekçisi imza denetimiyle YETİNMİYOR: işlev işin SATIRINI
alıyor ve `Is.anahtar_kaynagi` o satırda duruyor, yani alan erişimiyle sessizce
okunabilirdi — gövde taranıyor.

Dokunulan: `services/planlar.py`, `services/modeller.py`, `services/kapilar.py`,
`routers/uretim.py`, `routers/isler.py`, `tests/test_planlar.py`, `CLAUDE.md`,
`docs/graflar/*`. Katalog ve i18n'e DOKUNULMADI.

**Sahibin adımı — PR'dan önce.** Sıralı liste ✅ geldi (2026-09-22). Kalan iki
girdi:

1. **GPT Image 2.5'in yetenek jetonları** — `flare` ve `sunburst` için boyut
   kümesi, kalite kümesi (`low…xhigh, max, auto` belgede yazılı ama bu depoda
   doğrulanmadı), `max_n`, referans sayısı. Ya birer canlı üretim, ya da
   "jetonları `gpt-image-2`den KOPYALA, alt sınır kalsın" talimatı — ikincisi
   `openai-gpt-image-2` girdisinin zaten kurulmuş deseni ve bu PR'ı
   bloklamıyor.
2. **`gpt-image-2` kalite ölçümü** — `low`/`medium`/`high`, 1024×1024,
   yanıttaki `usage`. Gelmezse 4/8/16 aynen kalır ve bekçi 1'de durur; PR
   bunun için BEKLEMEZ.

**Bağımlılıklar.** 1'den sonra (girdi silinmiş, yorumlar yerinde); 2-4'ten
BAĞIMSIZ — omurgayla paralel gidebilir; 7 (operasyon) bu görevin sağlayıcı
listesini KURULUM'a ve `isletme.md`ye yazar. Düzeltilmiş krediler 4. görevin
hibe/fiyat kararına GİRDİ olur (yukarıdaki "planları zorluyor" bölümü), ama
onu bloklamaz.

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

## 3. Polar webhook ve olay işleme — `services/polar.py`, `services/odeme.py`, `POST /api/odeme/webhook` ✅ (PR: `faz4/polar-webhook`)

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

**Yapıldığında (2026-09-21) ölçümler ve sapmalar.** Rota 70 → **72**
(`POST /api/odeme/webhook` açık — `ACIK_ROTALAR` 7 → 8 gerekçesiyle; `GET
/api/admin/odeme-olaylari` `ADMIN_ROTALAR` 9 → **10**; `KAPILI` 63 → 64), modül
111 → **114** (`services/polar.py`, `services/odeme.py`, `routers/odeme.py`),
göç YOK (şema 2'den hazır). Polar'a bu oturumdan yine erişilemedi; **SDK
0.32.0 PyPI'dan indirildi, kaynağı okundu** — yukarıdaki tablo satır satır
güncellendi (imza şeması, olay türleri, alan adları, sunucu adları
DOĞRULANDI; ücretler, yeniden deneme süresi, panelden yeniden gönderimin
`webhook-id`si, test kartı DOĞRULANMADI). Gemiye binen API:
`polar.ortam()` (boş = sandbox, başka değer `ValueError`), `polar.erisim_jetonu()`,
`polar.webhook_sirri()`, `polar.olay_dogrula(govde: bytes, basliklar, *, sir=None)
-> Olay(webhook_id, tur, zaman, govde)` (`.veri`, `.nesne_id`; `ImzaHatasi` /
`YukHatasi` / `YapilandirmaHatasi`), `polar.imzala(govde, sir, *, webhook_id,
zaman=None) -> {üç başlık}` (doğrulamanın tersi — testler ve 4. görevin yerel
Polar'ı), `polar.istemci()` (tembel `polar_sdk.Polar(access_token, server)`);
`odeme.isle(db, olay, *, an=None) -> Sonuc(durum, hata, kullanici_id, kredi)`
(`.json()` = rota gövdesi), `odeme.olayi_kaydet(db, olay, an) -> uuid | None`,
`odeme.kullaniciyi_coz(db, olay)`, `odeme.urun_bul(db, polar_urun_id)`,
`odeme.plan_uygula(db, hedef_id, plan, *, abonelik_id, plan_bitis=None) -> bool`,
`odeme.ISLENEN_TURLER` (9 tür — sahibin panelde seçeceği liste), `odeme.HATALAR`
(`kullanici_yok`, `urun_yok`, `sebep_bilinmiyor`, `urun_sebep_uyumsuz`,
`musteri_cakisiyor`, `abonelik_eski`, `nesne_yok`); rota cevabı `{"durum":
"islendi"|"yinelenen"|"atlandi"[, "hata": <kod>]}`, 400 `imza_gecersiz` /
`govde_gecersiz`, 413 `govde_buyuk` (256 KiB tavan, HMAC'ten önce), 503
`odeme_yapilandirilmadi` (sır yok), 500 iç hata (olay satırı rollback ile
gider). Günlük: `olay=odeme.<tur>` INFO (`kullanici_id`, `siparis`, `sebep`,
`urun`, `plan`, `kredi`, `dusen`), `odeme.webhook` INFO (her cevap),
`odeme.iade` WARNING, `odeme.imza_gecersiz` WARNING, `odeme.yinelenen` INFO,
`odeme.hata` ERROR (`exc_info`, Sentry). Admin: `depo_admin.odeme_olaylari(db,
*, yalniz_hata, limit=100)` + `odeme_ozeti(db)` → `{"olaylar": [...], "ozet":
{olay, hatali, siparis}}`; `admin.js` dördüncü sekme "Ödeme" (alındı, tür, Polar
nesnesi, e-posta, işlendi, hata kodu; "yalnız hatalı" kutusu), i18n **+6** tr/en.
Köprü bayrağı `KROMIS_UCRETLI_HIBE_BAKIMDA` KALDIRILDI (`planlar.py`,
`defter.hibe_turu` yalnız `free`, `isci.py hazirla`, `.env.example`, KURULUM,
`ALTYAPI`); `.env.example` **+3** (`KROMIS_POLAR_ORTAM`, `KROMIS_POLAR_ERISIM_JETONU`,
`KROMIS_POLAR_WEBHOOK_SIRRI`), `ALTYAPI` net +2. `requirements.txt`
`polar-sdk==0.32.*` (imaja girer; `standardwebhooks` onun bağımlılığı).
Sahte yükler `tests/fixtures/polar/*.json` **11 dosya**, sandbox'tan
KAYDEDİLMİŞ DEĞİL (erişim yok) — SDK modellerinden kurulup **SDK'nın
`WebhookPayloadAdapter`ından geçirildi** (her fixture bir testte yeniden geçer:
pin ilerlediğinde şema kayması orada görünür); e-posta/ad `DUMMY`. Testler
**+39** (`tests/test_odeme.py`: imza 6 durum + 5 dk penceresi + zarf hataları +
SDK `validate_event` bizim imzayı kabul eder; rota 503/413/400/500; yinelenen
`webhook-id`; aynı sipariş iki teslimat; RLS uygulama rolüyle admin bağlamı
`siparisler` + `kredi_hareketleri`; paket → `paket_bakiye` + sipariş + redakte
gövde; `subscription_create` plan + tamamla 300 → 1.000; `cycle` dolu bakiyeye
dokunmaz, düşükte tamamlar, ikinci teslimat çakışır; `canceled`/`uncanceled`
`plan_bitis`; `revoked` free + `sona_erme` −800 yalnız hibe, paket 500 durur,
`tutarlilik` boş; `updated` pro → temel −2.000, `cancel_at_period_end`,
`past_due` dokunmaz, `abonelik_eski`; aynı plandaki `updated` ve zaten `free`
hesaba başka gün gelen `revoked` admin kredisini kırpmaz; `customer.*` bağla/çakışma/üçüncü çözüm
yolu; iade WARNING; 5 hata kodu parametreli + ürün aynası yazılınca yeniden
gönderim işlenir; `metadata.kullanici_id` yedeği, silinmiş hesap; bakım turu
`pro`yu tamamlamaz; admin ucu liste/süzgeç/özet/gövde yok) + E2E admin dört
sekme (`tests/test_playwright_admin.py` "Ödeme" sekmesi: iki tohum, süzgeç,
çevrili özet). Takım sayısı PR gövdesinde. **Sandbox uçtan uca ölçüm
YAPILMADI** (Polar erişimi yok; sahibin adımı — PR gövdesindeki kontrol
listesi).

**Sapmalar — belgeden farklı yapılanlar, gerekçesiyle.** (a) **İmza SDK'nın
`validate_event`iyle DEĞİL, onun altındaki `standardwebhooks.Webhook.verify`
ile** (aynı kütüphane, aynı sır dönüşümü — `polar._anahtar` SDK'nın satırının
kopyası; test SDK'nın bizim imzamızı kabul ettiğini ölçer): `validate_event`
imzadan sonra yükü SDK'nın pydantic modelinden geçiriyor ve model o günkü
şemanın HER zorunlu alanını istiyor — Polar bir enum değeri ya da alan
eklediğinde işimize yaramayan bir doğrulama hatası 500 olur, Polar saatlerce
yeniden dener ve sonunda ucu kapatır (para yolu). Alan okumaları
`services/odeme.py`de tolerant (`dict.get`); şemaya bağlılık fixture'ların SDK
modelinden geçmesiyle ölçülür. (b) **`services/odeme.py` `KIRACISIZ_MODULLER`de**
(işlev düzeyi `KIRACISIZ` defteri değil): modülün HİÇBİR işlevi `kullanici_id`
almaz — hedef `hedef_id`/`kullanici` nesnesi (`plan_uygula(db, hedef_id, …)`),
`depo_admin`in deseni; gerekçe belgeninkiyle aynı. (c) **"hata ama 200"
gövdesi `{"durum": "atlandi", "hata": <kod>}`** — `durum` üç değerli kaldı,
`hata` alanı eklendi; belgenin iki koduna (`kullanici_yok`, `urun_yok`) beş kod
daha: `sebep_bilinmiyor` (tanınmayan `billing_reason` — CHECK'e çarpıp 500
olmasın), `urun_sebep_uyumsuz` (paket ürünü abonelik sebebiyle ya da tersi —
ayna yanlış, para YATMAZ), `musteri_cakisiyor` (`polar_musteri_id` UNIQUE'e
çarpmasın), `abonelik_eski` (olay kullanıcının güncel `polar_abonelik_id`sine
ait değil — iptal edilmiş eski aboneliğin geciken `revoked`ı yeni aboneliği
düşürmesin), `nesne_yok`. (d) **`subscription.updated` yalnız `status=active`
iken yazar** (plan + `plan_bitis`; `cancel_at_period_end` ise dönem sonu) ve
düşürmede `dusur`; `past_due`/`canceled`/`unpaid` durumlarında dokunmaz —
belgenin "pro → temel `subscription.updated`" satırı bu dalda. **`sona_erme`
yalnız plan GERÇEKTEN daha düşük hibeli plana inince** (`_dusur(eski_plan, plan)`):
belge "düşürmede `dusur`" demişti, uygulamada aynı plandaki bir `updated`
(iptal bayrağı, metadata) ya da zaten `free` hesaba başka gün yeniden gönderilen
`revoked` (yeni günlük anahtar) admin `duzelt`le verilmiş fazla hibeyi kırpardı —
adversarial okumada bulundu, test çivili. `order.paid`
ayrıca `polar_musteri_id`yi bağlar (ilk siparişte müşteri kimliği öğrenilir;
`customer.*` olayı seçilmemiş olsa da üçüncü çözüm yolu çalışır). (e) **413 ve
503** belgede yoktu: 256 KiB gövde tavanı HMAC'ten önce (bedava koruma), sır
yapılandırılmamışsa 503 `odeme_yapilandirilmadi` (sırsız uç "geçerli" demez).
(f) **`polar.imzala`** eklendi (doğrulamanın tersi; testler ve 4. görevin E2E
"yerel Polar"ı gerçek HMAC üretir — `Webhook.verify` yamalanmaz). (g)
**`checkout_ac`/`portal_baglantisi`/`urunler`/`abonelik_iptal` bu PR'da YOK** —
belge onları `(4)`/`(5)` diye işaretliyordu, o görevlerde gelir; `istemci()` hazır.
(h) **`standardwebhooks` ayrıca pinlenmedi**: `polar-sdk`nın bağımlılığı
(`>=1,<2`), iki pin bir gün çelişirdi. (i) **Admin cevabı `{"olaylar", "ozet"}`**
(belge yalnız liste demişti) — sahip "kaç sipariş, kaç hatalı" sayısını listeyi
saymadan görsün; i18n +6, ~10 değil. (j) **Fixture'lar sandbox kaydı değil, SDK
modelinden kurulmuş** (Polar erişimi yok); DUMMY disiplini aynen. (k) **Admin
eliyle `pro` yapılmış hesap artık dönem hibesi almaz** (köprü kalktı, webhook
yalnız Polar siparişinde yatırır) — sahibin yolu admin "kredi ekle";
KURULUM 10. adıma cümle eklendi, 11. adım 7. görevin. Belgenin kalan cümleleri
aynen uygulandı.

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

## Kaynaklar (erişim tarihi 2026-09-21; 1b tarife kaynakları 2026-09-22)

* Master design "Ödeme Altyapısı: MoR" (2026-09-18 notu, sahibin araştırması):
  [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) `:184-214`.
* Yol haritası (Faz 0–5, Türkçe): claude.ai artifact `Lz65U9WpRQfbMeGCHDvLi5` —
  Faz 4 kartı "Ödeme, faturalama ve hukuk", çıkış kriteri cümlesi.
* Model barındırma / maliyet araştırması (2026-09-20): claude.ai artifact
  `GxN2FA5932GpJYGEgSiruL` — dört doğrulanmamış Azure fiyatı, yedi kredi ≠
  maliyet, `gpt-image-1` 2026-10-23 (OpenAI duyurusu üzerinden).
* **1b tarife kaynakları (erişim 2026-09-22).** Azure Foundry Models pricing,
  Black Forest Labs sekmesi:
  [azure.microsoft.com/…/ai-foundry-models/black-forest-labs](https://azure.microsoft.com/en-us/pricing/details/ai-foundry-models/black-forest-labs/)
  — `Flux 2 Pro Initial MP` 0,03, `Flux 2 Pro MP` 0,015, `Flux 2 Ref MP` 0,015,
  `Flex Global` 0,05, `Flex Ref Global` 0,05 USD/MP. **Sayfa JS ile çiziliyor
  ve düz `fetch` `$-` döndürüyor** (`tools/tarife_kontrol.py`nin varlık
  sebebi); tablo TARAYICIYLA açılarak okundu — bir dahaki doğrulamada da aynı
  yol gerekir. Megapiksel yuvarlama kuralı ("rounded up to the next megapixel,
  separately for each reference image and for the generated image") Microsoft
  Community Hub FLUX.2 duyurularından.
* Azure OpenAI Service pricing, GPT-Image Series tablosu:
  [azure.microsoft.com/…/cognitive-services/openai-service](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
  — `GPT-Image-2 Global` çıktı görseli 30 USD/1M jeton (OpenAI doğrudanla
  AYNI). Kalite başına jeton sayısı bu tabloda **YOK**.
* MAI-Image jeton fiyatları: techcommunity.microsoft.com "MAI-Image-2.6 and
  MAI-Image-2.6-Flash" (2026) — 2.6 çıktı 38, **2.6-Flash çıktı 19** USD/1M
  jeton; 1024×1024 = 1024 jeton ölçümü bu depodan (Faz 3 sondası).
* [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)
  — Nano Banana 2 (gemini-3.1-flash-image) 1K 0,067 / 2K 0,101 / 4K 0,151;
  Nano Banana Pro 1K-2K 0,134 / 4K 0,24; Veo 3.1 0,40 · Fast 0,10 (720p) /
  0,12 (1080p) · Lite 0,05 (720p) / 0,08 (1080p) USD/sn. **1K ile 2K'nın aynı
  fiyatta olduğu eski gözlem ARTIK GEÇERSİZ** (1120 ↔ 1680 jeton) — katalogdaki
  `default_quality="2K"` yorumu o öncüle dayanıyordu.
* [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing)
  ve [/models/gpt-image-2.5-sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)
  — GPT Image 2.5 (`flare`, `sunburst`) 2026-09-08'de çıktı, 30 USD/1M çıktı
  jetonu, kalite kümesi `low…xhigh, max, auto`; `gpt-image-2` emekli DEĞİL
  (anlık görüntü `gpt-image-2-2026-04-21`).
* fal.ai model sayfaları (fiyat her sayfanın kendi "your request will cost"
  cümlesinden): [flux/schnell](https://fal.ai/models/fal-ai/flux/schnell) 0,003/MP ·
  [qwen-image](https://fal.ai/models/fal-ai/qwen-image) 0,02/MP ·
  [seedream v4](https://fal.ai/models/fal-ai/bytedance/seedream/v4/text-to-image) 0,03/görsel ·
  [wan-3.0](https://fal.ai/models/alibaba/wan-3.0/text-to-video) 0,05/0,10/0,20 ·
  [pixverse c1](https://fal.ai/models/fal-ai/pixverse/c1/text-to-video) 0,065/0,120 (sesli) ·
  [minimax h3](https://fal.ai/models/minimax/h3/text-to-video) 0,05/0,06/0,13/0,16 ·
  [kling v3 turbo pro](https://fal.ai/models/fal-ai/kling-video/v3/turbo/pro/text-to-video) 0,14 ·
  [kling v3 pro](https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video) 0,112/0,168 ·
  [flux 3](https://fal.ai/models/blackforestlabs/flux-3/image-to-video) 0,17/0,29 ·
  [seedance 2.5](https://fal.ai/models/bytedance/seedance-2.5/image-to-video) ~0,473 (720p sesli).
  fal'ın `/pricing` sayfası ÖZET ve BAYAT (Wan 2.5, Kling 2.5, Veo 3 yazıyor) —
  gerçek fiyat model sayfasında; bir dahaki turda oradan okunmalı.
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
