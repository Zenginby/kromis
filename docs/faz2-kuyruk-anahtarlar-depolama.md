# Faz 2 — iş kuyruğu, platform anahtarları ve nesne depolama: görev listesi

**Tarih:** 2026-09-17 · **Karar:** çok kullanıcılı web (Alperen Zengin, Slack, 2026-09-16: küresel kitle · modele göre kredi, abonelik paketiyle satılır, Stripe önce · yönetilen barındırma — örnek yığın Supabase/Neon + Upstash + Cloudflare R2 + Fly.io/Railway/Render "uygulama + worker" · web-first) · **Önceki faz:** [faz1-veritabani-hesaplar.md](faz1-veritabani-hesaplar.md) (9/9 ✅, PR #28-#36)
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) §1-§3, §5 — sapmalar bu belgenin sonunda tek tek yazılı. **Yol haritası kartı (Faz 2):** "Redis + worker; generate/edit/video uçları job oluşturup 202 döner · job durumu için SSE veya polling; ön yüzde iş listesi ve sekme yenilemeye dayanıklılık · platform sahipli sağlayıcı anahtarları için secret manager; isteğe bağlı kullanıcı BYOK · kullanıcı başına eşzamanlılık limiti ve rate limiting · yapısal loglama + Sentry + temel metrikler" — **çıkış kriteri:** "6 dakikalık video işi sekme kapansa da tamamlanıyor; sağlayıcı harcaması kullanıcı başına sınırlı."

Faz 2'nin amacı, Faz 1'in kurduğu hesabın ve veri tabanının üstüne **üretimi
istekten ayırmak**: bugün 1-6 dakika süren sağlayıcı çağrısı HTTP isteğinin
içinde koşuyor (`routers/uretim.py:102-112` bunu "bilinçli bir seçim, kaza
değil" diye kaydediyor ve bedelini yazıyor: sekme yenilenirse iş kaybolur);
Faz 2'de aynı çağrı ayrı bir işçi sürecinde, kullanıcının sekmesinden bağımsız
koşar, sonucu nesne depolamaya yazar, kullanıcı iş listesinden izler. Aynı
fazda anahtar KULLANICIDAN PLATFORMA taşınır (kullanıcı kendi anahtarını
girmek zorunda kalmadan üretir; girerse onunki kazanır) ve platformun parasını
harcayan her iş kullanıcı başına bir tavana bağlanır. Kredi DEFTERİ, planlar,
filigran (Faz 3) ve ödeme (Faz 4) BU FAZDA YOK — yol haritası kartları öyle
diyor ve gerekçeleri "Faz 2 dışı" bölümünde. Her madde bir PR (`faz2/<slug>`
dalı), her PR tek başına yeşil ve geri alınabilir; her PR'da testler +
`docs/graflar` aynı commit'te. Sıra bağımlılığa göre: **1 → 2 → 3 → 4 → 5**
(omurga: tablo → nesne depolama → işçi → 202 → iş listesi), sonra **6** (4'e
dayanır), **7** (1'e dayanır, 4'ten sonra önerilir), **8** (4 ve 6'ya dayanır),
**9** her an başlayıp 8 ile biter, **10** en son. Çıkış kriterinin ilk yarısı
5'te, ikinci yarısı 6'da karşılanır.

**NEDEN 2 (nesne depolama) 3'ten (işçi) ÖNCE — Faz 1'in K5'i sırayı ters
yazmıştı ("R2 Faz 2'de, kuyrukla birlikte; yazan taraf worker olacak").**
Sahibin yığınında uygulama ve worker AYRI süreçler, yönetilen platformların
hepsinde ayrı makineler ve ORTAK DİSKLERİ YOK (Fly birimi makineye bağlı,
Railway/Render'da kalıcı disk tek servise). İşçinin ürettiği MP4 işçinin
diskine düşerse `GET /output/{filename}` (`routers/galeri.py:288`,
`FileResponse`) onu hiç göremez; `/api/edit`in referans görselleri
(`services/gorsel.py:25-27`, 40 MB'a kadar) de web sürecinin diskinden işçiye
geçemez. Yani işçi ile web'in ortak bir dosya zemini olmadan işçi kurulamaz;
o zemin nesne depolama (ya da tek makine + compose, ki o yerel geliştirme).
Bu yüzden 2. görev "medyanın yerini değiştirir, davranışı değiştirmez" ve 3.
görev onun üstüne oturur.

Ölçüler bu belge yazılırken alındı (`4b5c74f`, Faz 1'in tamamı main'de):

* **Faz 1 tabanı:** 11 tablo (`services/tablolar.py`, göç başı `0003_arena_win`),
  **54 rota / 9 dosya** (`docs/graflar/uc-noktalar.md`), 47'si kimlik kapısının
  arkasında; kullanıcı başına ŞİFRELİ BYOK anahtarı (`saglayici_kimlikleri`,
  Fernet, `services/sifre.py`); göç dağıtım öncesi komutta (`tools/goc.py`, K6);
  imaj **284 MB** (PR #36'nın `docker` işi). Takım **3.413 geçti, 12 atlandı,
  180 sn** (E2E + Postgres zorunlu); 118 test dosyası, 87 Python modülü, 11
  tarayıcı betiği (`docs/graflar/README.md`).
* **Senkron üretim yolu:** `routers/uretim.py` dört rota — `POST /api/generate`
  (`:47`, `def`), `/api/video` (`:95`, `def`), `/api/video/animate` (`:210`,
  `async def`, multipart), `/api/edit` (`:408`, `async def`, multipart). Dördü
  de `providers.generate/generate_video/animate_video/edit`i istek içinde
  çağırıyor, dönen baytları `depo_medya.kaydet` (`services/depo_medya.py:113-158`:
  önce dosya, sonra satır, `flush`) ile yazıyor, `{"images"|"videos": [...]}`
  döndürüyor. Süre tavanları: görselde `180 + 120·(n-1)` sn (Azure n=4 → 540 sn,
  `uretim.py:103-105`), videoda `catalog.poll_timeout` **420-600 sn**
  (`catalog.py:929-1110`; `providers.total_budget`, `providers.py:271`).
  Starlette'in iş parçacığı havuzu **40** (anyio öntanımı): 40 eş zamanlı
  video isteği bütün sunucuyu — `/api/history` dâhil — bekletir.
* **Ön yüz beklemesi:** `static/core.js` üretimi `await fetch(...)` ile
  bekliyor (`:2873-2914` istekler, `:2948` `await request`); durum satırı
  videoda süreyi söylüyor çünkü "ekranda yalnız shimmer var" (`:2934-2946`);
  arena turu model başına ayrı `POST /api/generate` (`:2712`, istemci
  fan-out'u, 2-4 sütun). `window.fetch` TEK noktadan sarılı (`:42`, 401 →
  `/giris`) — 35 çağrı yeri, tek kapı. Bu üç gerçek 4. ve 5. görevin ön yüz
  planını belirliyor.
* **Anahtar çözümü:** `services/kimlik.py:146-171` `kimlik_bilgileri` /
  `KIMLIKLER` — kullanıcının şifreli satırları istek başına bir kez çözülür,
  `kimlik_baglami` (ContextVar, kökte yaprak) ile adaptörlere TEMBEL iner
  (`credentials=None` düşmesi; Faz 1 / 7'nin 104 testlik dersi). İşçi bir
  istek değil; aynı bağlamı işçi kendisi bağlar (3. görev) — adaptörlere
  dokunulmaz.
* **Hız sınırı bugün yalnız hesapta:** `giris_denemeleri` tablosundan
  (`services/hesap.py:41-44, 253-289`; e-posta 10 / IP 30 / 15 dk; kayıt ve
  sıfırlama IP 5 / sa). Üretimde SIFIR kota: anahtarı olan herkes sınırsız
  gönderir — BYOK'ta kendi parası, platform anahtarı gelince BİZİM paramız.
* **Bağlantı havuzu küçük ve bilerek:** `services/db.py:99-100` `pool_size=2`,
  `max_overflow=3` (yönetilen Postgres'in havuzu sınırlı, pooler kendi
  koyuyor). İşçi süreci kendi motorunu kurar; SSE bağlantısı (5. görev) sorgu
  ARASINDA bağlantı tutmaz — bu iki kural buradan geliyor.
* **Kütüphane ölçüleri PyPI'dan bugün** (`pip download`, cp313): `boto3`
  zinciri 7 tekerlek, **21 MB açılmış** (`botocore` tek başına 19 MB — yaklaşık
  400 servisin modeli, bize biri gerek), imaja +%7; `minio` istemcisi 0,1 MB
  ama `pycryptodome` + `urllib3` getiriyor (depo `httpx` kullanıyor, ikinci bir
  HTTP yığını); `sentry-sdk` 2,0 MB açılmış, saf Python. `hmac`/`hashlib`
  ile SigV4 imzası standart kütüphane. 2. ve 9. görevin bağımlılık kararları
  bu sayılara dayanıyor. Bu makinede Docker YOK (Faz 1 ölçümü aynen), geçici
  Postgres kümesi açılıyor (`tools/test_ortami.py --kontrol` "hazir").

---

## Envanter: bugünkü senkron/yerel parçalar → Faz 2 parçaları

Adlar ÖNERİ (deponun yeni kod geleneği Türkçe, ASCII: `isler`, `isciler`,
`services/kuyruk.py`); her satır hangi görevde değiştiğini söylüyor.

| bugün | nerede | Faz 2'de | görev |
| --- | --- | --- | --- |
| Üretim 4 rotada, istek içinde, 1-10 dk açık bağlantı; sonuç `{"images"\|"videos"}` 200 | `routers/uretim.py:47-473` | Rota isteği DOĞRULAR, `isler`e satır yazar, **202 `{"is": {...}}`** döner; sağlayıcı çağrısı işçide | 1, 3, 4 |
| İş kaydı YOK — biten iş yalnız `medya` satırı, düşen iş yalnız `hata.log` | — | `isler` tablosu: durum, istek, sonuç, hata (redakte), süre, tahminî kredi; 30 gün saklama | 1, 10 |
| Bekleme: `await fetch`, shimmer, süre metni; sekme yenilenince iş kayıp | `static/core.js:2873-2948` | `GET /api/isler` + SSE `GET /api/isler/akis`; `static/isler.js` iş paneli; yenilemede aktif işler geri gelir | 4, 5 |
| Medya dosyası yerel disk `kullanicilar/<uuid>/output`, `FileResponse` | `services/depo_medya.py:113`, `routers/galeri.py:288` | Nesne depolama (R2/S3), aynı anahtar yolu; `/output/{filename}` **302 imzalı URL**; yerel disk compose/test için kalır | 2 ✅ |
| Dosya + satır atomik değil, `tools/artik_dosya.py` arkadan topluyor | Faz 1 / 5, 9 | İşçi akışın tamamına sahip: nesne → satır → commit, satır düşerse nesne SİLİNİR (telafi); `artik_dosya.py` kovayı tarar | 2 ✅ (kova taraması), 3 |
| Sağlayıcı anahtarı yalnız kullanıcının (DB, şifreli) | `services/kimlik.py:146`, `depo_kimlik_bilgisi` | Kullanıcı → **platform (ortam sırrı)** → yok; `GET /api/settings` kaynağı söyler | 6 |
| Harcama sınırı YOK | — | Kullanıcı başına eş zamanlı iş (4), saatlik iş, günlük kredi tavanı (platform anahtarlı işler); admin ezer | 4, 6, 8 |
| Kiracı ayrımı yalnız uygulama süzgeci (`WHERE kullanici_id`) | `tests/test_galeri_db.py` AST bekçisi | + Postgres RLS ikinci kat: `SET LOCAL app.kullanici_id`, 8 iş tablosunda politika, FORCE | 7 |
| `is_admin` bayrağı var, okuyan yalnız `GET /api/hesap/ben` | `tablolar.py:217`, `tools/kullanici.py --admin` | `/admin` sayfası + `/api/admin/*`: kullanıcılar, kuyruk, metrikler, tavan, iptal, oturum düşürme | 8 |
| Günlük: `hata.log` (redakte) + uvicorn erişim satırları | `errlog.py:71,101` | JSON satır günlüğü stdout'a (istek/iş kimliği, kullanıcı, süre), Sentry isteğe bağlı, redaksiyon aynı işlevle | 9 |
| `/health`: veri dizini + DB | `routers/saglik.py:95` | + `worker_alive` (son kalp atışı ≤ 90 sn) BİLGİ alanı, `ok`a girmez | 9 |
| compose 3 servis (`goc`, `kromis`, `postgres`) | `compose.yaml:35-97` | 4 servis (+`isci`, aynı imaj); platformda ikinci süreç/servis; R2 kovası; işçi için SIGTERM düzeni | 3, 10 |
| Ön yüz çerçevesi kararı AÇIK (Faz 0 / 7 → Faz 1 → buraya) | `docs/superpowers/specs/2026-09-17-onyuz-paketleme.md` | **Vanilla sürer**, `isler.js` + `admin.js` aynı deyimle; karar belgeye yazılır, yeniden bakış Faz 4 | 5 |

---

## 1. İş tablosu ve kuyruk ilkelleri — `isler`, `isciler`, `services/kuyruk.py` ✅ (PR: `faz2/is-tablosu-kuyruk`)

**Kapsam.** Davranış DEĞİŞMEZ; yalnız şema + kuyruk katmanı + bekçileri. İki
tablo (`services/tablolar.py`, göç `0004_isler`):

* `isler` — `id uuid` (`gen_random_uuid`), `kullanici_id` FK CASCADE, `tur text
  CHECK IN ('generate','edit','video','animate')`, `durum text CHECK IN
  ('bekliyor','calisiyor','bitti','hata','iptal')`, `istek JSONB NOT NULL`
  (doğrulanmış istek gövdesi: `GenerateRequest`/`VideoRequest`in `model_dump`ı ya
  da multipart alanları + girdi nesnelerinin anahtarları), `sonuc JSONB NULL`
  (`{"medya": [id, ...]}` — kayıtların kendisi değil; `medya` satırı zaten var),
  `hata text NULL` (`errlog.redact_secrets`ten geçmiş), `model text NOT NULL`,
  `kredi_tahmini int NOT NULL` (`catalog.cost_for` × n, sıraya girerken; 6.
  görevin tavanı bunu toplar, Faz 3'ün defteri bunu okur), `isci_id uuid NULL`,
  `olusturuldu`, `basladi NULL`, `bitti NULL`, `kalp_atisi NULL`. İndeksler:
  `(kullanici_id, olusturuldu)` (liste, `medya`nın deseni), `(durum,
  olusturuldu) WHERE durum = 'bekliyor'` (kısmi — kuyruk okuması yalnız
  bekleyenleri tarar), `(kullanici_id, olusturuldu) WHERE durum IN
  ('bekliyor','calisiyor')` (eş zamanlılık sayacı).
* `isciler` — `id uuid`, `konak text`, `surum text` (`version.APP_VERSION`),
  `basladi`, `son_kalp timestamptz`, `es_zamanli int`. İşçi açılışta satır yazar,
  30 sn'de bir `son_kalp` günceller, kapanışta siler. `/health`in
  `worker_alive`ı (9) ve admin sayfası (8) buradan okur.

Yeni **`services/kuyruk.py`** — konuşmaz (kullanıcıya değil), `(db, ...)` imzalı
saf işlevler: `ekle(db, kullanici_id, tur, istek, model, kredi_tahmini) -> Is`;
`al(db, isci_id, an) -> Is | None` — TEK sorgu: `UPDATE isler SET
durum='calisiyor', isci_id=:isci, basladi=:an, kalp_atisi=:an WHERE id = (SELECT
id FROM isler WHERE durum='bekliyor' ORDER BY olusturuldu FOR UPDATE SKIP LOCKED
LIMIT 1) RETURNING *`; `kalp(db, is_id, an)`; `bitir(db, is_id, sonuc, an)`;
`dusur(db, is_id, hata, an)`; `iptal(db, kullanici_id, is_id) -> bool` (yalnız
`bekliyor`; `calisiyor` iptal EDİLMEZ — sağlayıcı çağrısı çoktan faturalandı,
`UPDATE … WHERE durum='bekliyor'` etkilenen satır 0 ise `False`);
`bayatlari_dusur(db, an, esik)` — `calisiyor` ve `kalp_atisi < an - esik` →
`hata` "isci yanit vermiyor" (yeniden KUYRUĞA ALMAZ, K8); `aktif_sayisi(db,
kullanici_id)`, `listele(db, kullanici_id, *, since=None, limit=50)`,
`_json(is)` dökümü (`id, tur, durum, model, kredi_tahmini, olusturuldu,
basladi, bitti, sonuc, hata` — `istek` DÖKÜLMEZ: prompt ve klasör zaten
`medya`da, referans anahtarları iç iş). Zaman `zaman.an()` ile Python'dan
(Faz 1 / 5-6 kararı: mikrosaniye, sıralama).

**Kuyruk arka ucu — Postgres (`FOR UPDATE SKIP LOCKED`), Redis DEĞİL (K1).**
Yol haritası kartı ve spec §2 "Redis + worker (ARQ/Celery/Dramatiq)" diyor;
sahibin örnek yığınında Upstash var. Ölçülen gerekçe Postgres lehine: (a) iş
LİSTESİ, durum ucu, 30 günlük geçmiş, admin kuyruk görünümü ve Faz 3'ün
defteri zaten KALICI bir `isler` satırı istiyor — Redis kuyruğu o satırın
yanına ikinci bir doğruluk kaynağı koyar ("Redis'te var, DB'de yok" tutarsızlık
sınıfı, iki fazlı yazım); (b) hacim: işler DAKİKALARLA sürüyor, kapalı beta
20-50 kullanıcı (Faz 5 kartı), yani saniyede binlerce değil dakikada onlarca
iş — `SKIP LOCKED` tek Postgres'te saniyede binlerce alım yapar, darboğaz
kuyruk değil sağlayıcı; (c) test zemini HAZIR: gerçek Postgres CI'da ve yerelde
(Faz 1 / K4), ikinci bir servis (`redis:7` + `fakeredis`?) Faz 0'ın "sahte
yeşil" dersini yeniden açar; (d) Upstash "sunucusuz" Redis: komut başına
ücret ve bağlantı sınırı, `BRPOP`la bekleyen işçi bu modele ters; (e) işletme:
sahibin yığınında bir servis daha, bir sır daha, bir yedek daha. Redis'in
kazanacağı yer alım gecikmesi (yoklama aralığı, aşağıda 1 sn) ve DB yükü — ikisi
de ölçülmeden bilinmez; `kuyruk.py` arayüzü (`ekle/al/kalp/bitir/dusur`)
arka uçtan bağımsız yazılır, ölçüm Redis'i haklı çıkarırsa `services/kuyruk_redis.py`
aynı imzayla gelir, rotalar ve işçi değişmez. Hız sınırı da AYNI karardan:
`giris_denemeleri` Postgres'te kalır (Faz 1 / 3'ün "Redis gelirse taşınır"
notu KAPANIR: gelmiyor), üretim kotaları `isler`den sayılır (4, 6).

**Faz 1'den devralınan.** "Kuyruk → Faz 2", "hız sınırının Redis'e taşınması"
(karar: taşınmaz, K1), `medya.credits`in "ledger'ın tek müşterisi" notu →
`isler.kredi_tahmini` onun iş düzeyindeki ikizi.

**Dokunulan.** `services/tablolar.py` (+2 sınıf; `IS_TABLOLARI` bekçi listesi 7
→ 8: `isler` iş tablosu, `isciler` DEĞİL — kullanıcı satırı yok),
`alembic/versions/0004_isler.py`, yeni `services/kuyruk.py`, yeni
`tests/test_kuyruk.py` (~25: ileri-geri-ileri + `alembic check`; iki eş zamanlı
alıcı TEK işi ALMAZ — iki `Session`, gerçek Postgres, `SKIP LOCKED`; FIFO;
kalp/bitir/düşür geçişleri ve CHECK'lerin reddettiği geçişler; iptal yalnız
bekleyeni; bayat düşürme eşiği; `_json` `istek` sızdırmaz; iki kullanıcı depo
düzeyinde izole — `test_galeri_db`nin AST bekçisi sekizinci depoya çıkar;
CASCADE), `tests/test_tablolar.py` (`IS_TABLOLARI`, CHECK değer kümeleri),
`tests/test_db.py` (`BAS` → `0004_isler`), `tests/test_i18n.py` (konuşmayan
modül), `docs/graflar/*`. Rota YOK, davranış değişikliği YOK.

**Risk.** Düşük. Geri dönüşsüz olan adlar (tablo/sütun/durum değerleri) —
`durum` değer kümesi ön yüzün ve admin'in okuduğu SÖZLEŞME olur, CHECK'te
kilitli, eklemek göç ister (bilerek: sessiz yeni durum ön yüzde "bilinmeyen"
demek). `kredi_tahmini` TAHMİN — gerçek maliyet Faz 3'ün mutabakat kalemi.

**Çıkış ölçütü.** `alembic upgrade head && downgrade base && upgrade head`
temiz, `alembic check` boş; 13 tablo; iki eş zamanlı alıcı testi 100 tekrarda
çift alım 0; takım yeşil.

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** `services/tablolar.py`
+2 sınıf (`Is`, `Isci`; 571 satır), **13 tablo**; `isler` 14 sütun, 2 CHECK
(`ck_isler_tur_kumesi`, `ck_isler_durum_kumesi` — değer kümeleri
`IS_TURLERI`/`IS_DURUMLARI` sabitlerinden, Faz 1 / 2'nin `text + CHECK`
kararı aynen), 1 FK (CASCADE), 3 indeks — ikisi KISMİ (`ix_isler_kuyruk`
`WHERE durum = 'bekliyor'`, `ix_isler_kullanici_aktif` `WHERE durum IN
('bekliyor','calisiyor')`); `isciler` 6 sütun, kısıtsız. Göç `0004_isler`
elle yazıldı (0001'in biçimi), ileri-geri-ileri + `alembic check` temiz
(geçici kümede ölçüldü, `tools/goc.py` → `0004_isler (head)`). **Kararlar,
belgenin açık bıraktığı yerlerde:** (a) `isler.isci_id` FK DEĞİL — işçi
kapanışta kendi satırını siliyor, işin "kim koştu" kaydı işçi gidince de
durmalı (SET NULL onu silerdi, CASCADE işi); (b) `durum` geçiş kuralı
UYGULAMADA DEĞİL `WHERE`de: `kalp`/`bitir`/`dusur` yalnız `calisiyor`,
`iptal` yalnız `bekliyor` satırı değiştirir, aksi 0 satır → `False` — yarış
Postgres'in satır kilidinde çözülür, bayat düşürülmüş işi geç kalan işçi
`bitti`ye çeviremez (test: `test_a_late_worker_cannot_resurrect_…`; işçi o
`False`ta ürettiği nesneyi siler — 3. görevin telafisi); (c) `iptal` ve
`ekle` `an=` anahtar parametresi aldı (belgedeki imzaya ek, öntanımlı
`zaman.an()`): `iptal` `bitti`yi yazıyor ("ne zaman kapandı" tek sütun),
testler saatle oynamıyor; (d) `listele(since)` "o andan beri DEĞİŞENLER" —
`GREATEST(olusturuldu, basladi, bitti) > since` (SSE `Last-Event-ID`nin
sorusu; `kalp_atisi` sayılmaz, istemciye görünmez); (e) `dusur` metni
`errlog.redact_secrets`ten geçiriyor — redaksiyon YAZAN yerde, çağıranda
değil (unutulacak yer bir tane); (f) `_json` anahtarları sütun adları
(`id, tur, durum, model, kredi_tahmini, olusturuldu, basladi, bitti, sonuc,
hata`; `istek`/`isci_id`/`kalp_atisi` yok), damgalar `zaman.damga` ile
`medya.created_at` biçiminde; (g) `bayatlari_dusur`un metni `BAYAT_HATASI =
"isci yanit vermiyor"` bir KOD, modül `test_i18n`de "konuşmayan"; (h) işçi
yardımcıları `isci_kaydet/isci_kalp/isci_sil` asgari (3. görevin ihtiyacı),
`al` `RETURNING`i `populate_existing` ile okuyor (aynı `Session`in bayat
`bekliyor` kopyası dönmesin). **Kiracı bekçisi** (`tests/test_galeri_db.py`):
`DEPOLAR` sekizinci depoya çıktı (`services/kuyruk.py`, `depo_*` kalıbının
dışında → `EK_DEPOLAR`), işçi tarafı için **`KIRACISIZ` defteri** açıldı
(8 işlev, her biri gerekçeli; bekçinin bekçisi muaf işlevin `kullanici_id`
ALMADIĞINI sınar — 7. görevin `depo_admin` muafiyeti aynı deftere yazılır).
**Testler:** yeni `tests/test_kuyruk.py` **24 test** (deterministik iki
`Session` testi: A alır commit'lemez, B alır, 100 tur, **çift alım 0**;
iş parçacıklı ikizi 60 iş; kilitli satırda bekleme < 1 sn; iptal ↔ alım
yarışı: iptal kilidi bekler ve 0 satır görür; FIFO mikrosaniye; geçişler;
bayat eşiği kesin küçük; `_json` sızıntısı kaynak + çalışma zamanı; iki
kullanıcı izole ama kuyruk küresel FIFO; CASCADE; kısmi indeksler
`pg_indexes`te gerçekten `WHERE`li; ileri-geri-ileri + `check`).
`test_tablolar` 13 tablo + `ALTYAPI_TABLOLARI = {isciler}` + iki yeni CHECK
kümesi; `test_db.py::BAS` → `0004_isler`. **Canlı duman** (geçici küme):
`goc.py` → head `0004_isler`, 13 tablo; `downgrade base && upgrade head`
temiz; 20 iş, iki iş parçacığı → 8 + 12 = 20 farklı, çift 0. **Alembic
notu:** `alembic check` kısmi indeksin `WHERE`ini KARŞILAŞTIRMIYOR (CHECK'ler
gibi) — bekçisi `test_the_queue_indexes_are_partial_in_the_database`
(`pg_indexes.indexdef`). Rota sayısı **54 DEĞİŞMEDİ**, `static/` DOKUNULMADI,
davranış değişikliği YOK.

---

## 2. Medya nesne depolamaya — `services/nesne_depo.py` (S3/R2, SigV4, httpx), `/output` → 302 imzalı URL, `tools/medya_tasi.py` ✅ (PR: `faz2/nesne-depolama`)

**Kapsam.** Medyanın YERİ değişir, rotaların şekli değişmez; üretim hâlâ
senkron (3-4. görev). Soyutlama **`services/dosya.py`** — `yaz(anahtar, bayt,
mime)`, `oku(anahtar) -> bytes`, `sil(anahtar)`, `var(anahtar)`, `url(anahtar,
sure, *, indirme_adi=None) -> str | None`, `listele(onek)`; iki uygulama:
`YerelDepo(kok)` (bugünkü disk — dondurulmuş kabuk, compose, testler; `url`
`None` döner, rota `FileResponse`a düşer) ve `NesneDepo(istemci, kova)`.
Anahtar = bugünkü yol: `kullanicilar/<uuid>/output/<filename>`,
`kullanicilar/<uuid>/assets/<tur>/<id>.png` — `ayar.Ayarlar.output_dir` /
`assets_dir` dizelerinin ANLAMI "önek" olur, alan adları ve 42 rotanın
`ayarlar.output_dir` okuması değişmez (Faz 0 / 4'ün vaadi bir kez daha tutar).
Seçim ortamdan: `KROMIS_NESNE_DEPO_URL` (uç nokta, R2: `https://<hesap>.r2.cloudflarestorage.com`),
`_KOVA`, `_ANAHTAR_ID`, `_GIZLI`, `_BOLGE` (R2 `auto`); dördü de boşsa
`YerelDepo`. `app.state.dosya` lifespan'da kurulur; `Depends(dosya.depo)`.

**S3 istemcisi — SigV4 elle, `httpx` ile; `boto3`/`minio` DEĞİL (K6).**
`services/nesne_depo.py` ~200 satır: `PUT/GET/HEAD/DELETE /<kova>/<anahtar>`,
`ListObjectsV2` (sayfalı), ön imzalı GET URL (`X-Amz-*` sorgu imzası,
`response-content-disposition` ile indirme adı), `hmac`/`hashlib` standart
kütüphane, HTTP `httpx` (depoda zaten: Resend, OIDC, adaptörler — SDK'sız
deyim Faz 1 / 3 ve 3b). Ölçü: `boto3` zinciri 21 MB açılmış (imaja +%7),
`botocore` yaklaşık 400 servis modeli taşıyor; `minio` `pycryptodome` +
`urllib3` getiriyor (ikinci HTTP yığını, ikinci pin ailesi); ikisi de testte
ya `moto`/gerçek uç ister ya da kendi taşıyıcısını yamalatır. Elle imza
`httpx.MockTransport`/`ASGITransport` ile deponun MEVCUT test deyimine
oturur. Bedeli: SigV4'ü doğru yazmak — bekçisi AWS'nin yayımladığı imza
örneği (bilinen anahtar/tarih/istek → bilinen `Authorization` dizesi) ve
gerçek bir R2 kovasına karşı CANLI doğrulama (sahibin hesabı, aşağıda).
Çok parçalı yükleme YOK: en büyük nesne bir video, sağlayıcılar onu tek gövde
veriyor, `PUT` 5 GB'a kadar tek parça.

**Servis yolu — 302 ön imzalı URL, vekil akış DEĞİL (K7).** `GET /output/{filename}`
ve `GET /assets/{kind}/{filename}` satırı DB'de bulur (sahiplik süzgeci aynen),
`NesneDepo`da **302** `Location: <imzalı URL, 15 dk>` + `Cache-Control:
private, max-age=600`, `YerelDepo`da bugünkü `FileResponse`. `<img>`/`<video>`
yönlendirmeyi takip eder, `<video>`nun aralık (Range) istekleri doğrudan R2'ye
gider — uygulama süreci bayt taşımaz, R2'nin sıfır çıkış ücreti (spec §1.3)
ancak böyle gerçekleşir. `GET /api/output/{id}/download` aynı yol +
`response-content-disposition`; `GET /api/folders/{id}/download` (ZIP)
akışı UYGULAMADAN geçer (ZIP'i biz kuruyoruz) — `httpx` stream → `zipfile`
→ `StreamingResponse`. Bindirme (`/api/logo`, `/api/banner`) ve düzenleme
referansları (`gorsel.output_png_path` → `dosya.oku`) baytı belleğe alır;
10 MB dosya tavanı (`gorsel.py:25`) bunu karşılıyor.

**Yazan taraflar.** Bu görevde yazanlar hâlâ web süreci: `depo_medya.kaydet`
ve `depo_varlik.kaydet` `dosya.yaz` çağırır (imza `output_dir` → `dosya`
nesnesi + önek); `POST /api/import`, `POST /api/assets/{kind}`, bindirme
sonucu. Sıra AYNI: nesne → satır → `flush`; commit `db.oturum`da, düşerse nesne
artık kalır — `tools/artik_dosya.py` kovayı tarar (`listele(onek)` ↔ `medya`/
`varliklar` satırları; çıkış kodları aynı). Kök çözüm 3. görevde: işçi akışın
tamamına sahip, telafi eder.

**Göç aracı — `tools/medya_tasi.py`.** `KROMIS_DATA_DIR/kullanicilar/<uuid>/
{output,assets}` altındaki dosyaları aynı anahtarla kovaya yükler (`PUT`),
`HEAD` ile boyut doğrular, `--kuru` sayar, `--sil` yerel kopyayı ancak
doğrulanmış nesne için siler (öntanımlı SİLMEZ — `ice_aktar`ın "kaynak
dokunulmaz" kuralı). İkili okuma KODU YOK, bilerek: kesme anı sahibin verisi
(beta yok), sıra "araç → ortam değişkenleri → dağıt"; iki yolu aynı anda
tutmak her okuma rotasına bir dal ve bir test eklerdi, kesmeyi bir kez
yapmak daha ucuz. `isletme.md` § 2 "medya dizini" satırı "kova" olur:
yedek = R2 nesne sürümlemesi (bucket versioning) + isteğe bağlı ikinci
kovaya `rclone` — 10. görev yazar.

**Faz 1'den devralınan.** K5 ("S3/R2 Faz 2, kuyrukla birlikte" — sıra ters
döndü, gerekçesi girişte), `artik_dosya.py`nin uyarlanması, `isletme.md`
§ 6'nın "R2 → Faz 2" satırı, `.env.example`in "kod başka değişken okumaz,
okursa buraya girer" sözleşmesi (+5 değişken, bekçi).

**Dokunulan.** yeni `services/{dosya,nesne_depo}.py`, `services/{depo_medya,
depo_varlik,gorsel,ayar}.py`, `routers/{galeri,bindirme,uretim}.py` (okuma/
yazma çağrıları — rota GÖVDELERİ aynı), `app.py` (lifespan), yeni
`tools/medya_tasi.py`, `tools/artik_dosya.py`, `.env.example` (+5, açıklamalı),
`compose.yaml` (yalnız yorum: yerel disk), `docs/isletme.md` § 2, `KURULUM.md`
(R2 kovası: oluşturma, API jetonu "Object Read & Write", CORS gerekmez —
302 aynı kökenden çıkıyor), yeni `tests/test_nesne_depo.py` (SigV4 bilinen
örnek; sahte S3 ASGI uygulaması — `PUT/GET/HEAD/DELETE/List` bellek sözlüğü,
`httpx.ASGITransport` ile takılır, imza DOĞRULAMAZ ama `Authorization`
başlığının varlığını ve biçimini sınar; ön imzalı URL süresi ve `X-Amz-*`
kümesi; 404/403/5xx eşlemesi `DosyaHatasi`), yeni `tests/test_dosya.py`
(iki uygulama aynı sözleşme — parametrik), `tests/test_medya_tasi.py`
(kuru/gerçek/`--sil`, HEAD uyuşmazlığında silmez), `test_galeri_db.py`/
`test_varlik_db.py`/`test_kimlik.py` (302 dalı: başkasının dosyası yine
**404**, kendi dosyası 302 + `Location` kova alan adında; yerel dalda 200
aynen), `test_artik_dosya.py` (kova dalı), `test_docker_kapisi.py`
(`ALTYAPI` +5), `docs/graflar/*`.

**Risk.** Orta-yüksek: medyanın tamamı bir dış servise geçiyor ve imza
elle. Küçültme: `YerelDepo` her yerde çalışır durumda kalır (compose,
test, dondurulmuş kabuk — geri dönüş ortam değişkenlerini silmek);
`medya_tasi` doğrulamadan silmez; canlı doğrulama gerçek kovada (SAHİBİN
İŞİ: Cloudflare hesabında kova + API jetonu, değerler bu PR'ın koşusunda
gizli olarak — belgeye yazılmaz). Faz 1'in K7'si gibi bu da DIŞ ve ÜCRETLİ
bağımlılık (R2: depolama GB/ay, çıkış ücretsiz). Bilinen bedel: ön imzalı
URL 15 dk sonra ölür — galeri açık kalan sekmede `<img>` yeniden yüklenirse
yeni 302 alır, sorun değil; kopyalanan URL paylaşılamaz (istenen davranış,
medya özel).

**Çıkış ölçütü.** Sahte S3'le tam takım yeşil; gerçek R2 kovasında canlı:
`medya_tasi --kuru` sayı, gerçek koşu, `/output/<ad>` 302 → görsel açılıyor,
`<video>` oynuyor ve ileri sarıyor, ZIP indiriliyor, `POST /api/import` +
`/api/logo` kovaya yazıyor, `artik_dosya.py` kovada 0 artık; başkasının
dosyası 404; yerel dizinde `output/` boş.

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Yeni `services/dosya.py`
(328 satır: `Depo` protokolü — `yaz/oku/oku_akis/sil/var/url/listele` —,
`YerelDepo`, `NesneDepo`, `depo_kur`, `Depends(dosya.depo)`, akışlı ZIP
tamponu) ve `services/nesne_depo.py` (317 satır: SigV4 saf işlevler +
`S3Istemci`: `koy/al/al_akis/bas/sil/listele/imzali_url`); **0 yeni
bağımlılık** (`hmac`/`hashlib`/`xml.etree` + depodaki `httpx`). **SigV4 dört
AWS vektörüyle bayt bayt doğrulandı** (GET + Range, PUT + gövde özeti + `$`
kodlaması, ön imzalı GET, ListObjects sorgusu — ilk denemede dördü de
tuttu). Ölçüler: **rota 54 DEĞİŞMEDİ**, `static/` DOKUNULMADI (`<img>`/
`<video>` 302'yi kendisi izliyor, `onyuz.md`de URL varsayımı yok), modül 88 →
91, test dosyası 119 → 123, takım **3.413 → 3.506 geçti, 12 atlandı, 189 sn**
(E2E + Postgres zorunlu). Yeni testler: `test_nesne_depo` 14, `test_dosya` 19
(iki depo PARAMETRİK, aynı senaryo), `test_dosya_rotalari` 13 (gerçek Postgres
+ imza DOĞRULAYAN sahte S3), `test_medya_tasi` 7, `test_artik_dosya` +2 (kova
kipi). **Canlı duman** (geçici küme + uvicorn, bu makinede): yerel kipte
`/output` 200 `FileResponse` aynen; sahte S3 sunucusuna (`tests/sahte_s3.py`
HTTP kipi, imza doğrulaması AÇIK) karşı `medya_tasi --kuru` çıkış 3 → gerçek
koşu 1 yüklendi → `--kuru` çıkış 0; `/output` **302** `Cache-Control: private,
max-age=600`, `Location` GET 200, **`Range: bytes=0-7` → 206** doğrudan
kovadan; indirme 302 + `response-content-disposition`; import + logo bindirme
+ varlık yükleme kovaya yazdı (4 nesne), diske hiçbir şey düşmedi;
`artik_dosya` kova kipi 0 artık, bırakılan artık `--sil --evet` ile silindi;
23 istek, 0 imza reddi.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) YOL ↔ ANAHTAR çevirisi
DEPODA: rotalar bugün ne yazıyorsa onu verir (`os.path.join(ayarlar.output_dir,
ad)`), `NesneDepo` `data_dir`i düşürüp `kullanicilar/<uuid>/output/<ad>`
anahtarını üretir — 42 rotanın `ayarlar.output_dir` okuması ve depo
modüllerinin `output_dir` parametresi DEĞİŞMEDİ, anlamı "önek" oldu (belgenin
vaadi); `kok` dışı mutlak yol kovada `DosyaHatasi` (programlama hatası),
yerelde geçer (testlerin `tmp_path`i). (b) `depo=` PARAMETRESİ İSTEĞE BAĞLI,
öntanımlısı yerel disk (`dosya.YEREL`): 60'tan fazla test `depo_medya.kaydet(…,
out)` diye doğrudan çağırıyor ve bugünkü davranışı ölçüyor; bedeli "unutulan
depo diske yazar" — bekçisi kaynak taraması
(`test_every_file_touching_call_in_the_routers_names_the_depo`: üç router
dosyasında 12 işlevin her çağrısı, `run_in_threadpool(...)` biçimi dâhil,
`depo=` söylemek zorunda). (c) `app.state.dosya` İTHAL ANINDA (`ayarlar`
gibi), lifespan'da DEĞİL — `with`siz `TestClient(app)` lifespan koşturmuyor;
YARIM yapılandırma ithali durdurur (`YapilandirmaHatasi`, eksik adları
söyler): sessizce diske düşen dağıtım işçi gelince "üretildi ama görünmüyor"
olurdu (`KROMIS_SECRET_KEY`nin duruşu). conftest `pytest_configure`
`KROMIS_NESNE_DEPO_*`ı süpürür — geliştiricinin kabuğundaki gerçek R2 değeri
178 rota testini gerçek kovaya yazdırmasın. (d) SATIR VE NESNE, iki depoda da:
servis/indirme/referans yolları `depo.var()` sorar (kovada HEAD) — Faz 1 /
5'in sözleşmesi korunur, "satırı var nesnesi yok" JSON 404 kalır (302 sonrası
R2'nin XML 404'ü değil); bedeli küçük resim başına bir HEAD, 302'nin 10 dk
önbelleği yineleri tutar; ağır ölçülürse tek satır düşer. (e) Dosya adı
SATIRDAN (`medya.filename`): Faz 1 / 5 uzantıyı `media_path_of` ile diskte
deniyordu, kovada her deneme bir HEAD olurdu; satırsız silme (eski "kaydı
olmayan dosya da silinmiş sayılır" sözleşmesi) iki uzantıyı depo üstünden
dener. (f) ZIP GERÇEKTEN AKIYOR: `Depo.oku_akis` (belgede yoktu) + `zipfile`
aranamayan akışta (`YazmaTamponu`, `write`/`flush`; `test_galeri_db`nin imza
bekçisi depo modülünde sınıf istemediği için `dosya.py`de) →
`StreamingResponse`; DB'ye dokunan her şey üreticiden ÖNCE (isteğin `Session`ı
akış sırasında kapanmış olabilir). (g) Bindirme/düzenleme BAYT okur:
`composite.composite_logo` ve `_composite_banner` yol YA DA `io.BytesIO`
alır (`Image.open` ikisini de açar; dondurulmuş kabuk yol vermeye devam
eder); iki test sahtesi (`fake_composite`, `_fake_composite_factory`) buna
uyarlandı, üç logo testi yol yerine İÇERİK ölçer. (h) `medya_tasi` `--sil`
TAŞIMAZ (belge sayıyordu): görev tanımı "yereli hiç silmez" dedi ve
`ice_aktar`ın "kaynak dokunulmaz" kuralı aynı yöne — yerel kopyayı sahibi
canlı doğrulamadan sonra kendisi arşivler; çıkış 3 = "iş kaldı" (kuru koşuda
yüklenecek var / gerçek koşuda doğrulanamayan var), idempotenlik HEAD +
boyut. (i) `tools/ice_aktar.py` DOKUNULMADI, bilerek: eski uygulamanın
verisini `KROMIS_DATA_DIR`a kopyalar (yerel), sonra `medya_tasi` kovaya taşır
— tek yön, iki araç; içe aktarmaya bir depo dalı eklemek "araç → değişkenler →
dağıt" sırasını bulandırırdı. (j) Path-style adres (`https://<uç>/<kova>/
<anahtar>`), bölge `auto`; `S3Istemci` `PUT`ta `content-type` + `content-length`
imzalar, hata mesajına S3 gövdesini YAZMAZ (istek kimliği ve anahtar id
yansır), `Kimlik.gizli` `repr` dışı. (k) Sahte S3 (`tests/sahte_s3.py`) imzayı
YENİDEN HESAPLAYIP doğrular (`Authorization` ve `X-Amz-Signature`; süre
kontrolü dâhil) — döngüsel değil: istemcinin imzaladığı küme ile gönderdiği
küme aynı mı; tek çekirdek, iki adaptör (`MockTransport` testte, `http.server`
dumanda). (l) `.env.example` +5 (`KROMIS_NESNE_DEPO_{URL,KOVA,ANAHTAR_ID,GIZLI,
BOLGE}`, `ALTYAPI` bekçisi 9 → 14), `medya_tasi` `OPERATOR_ARACLARI`nda
(imajda), `compose.yaml` DOKUNULMADI (yerel disk, yorum gerekmedi — yorum
`.env.example`da). Bilinen bedel: `KROMIS_NESNE_DEPO_BOLGE` yalnız R2 dışı
S3 için anlamlı.

**Sahibin adımı — gerçek R2 kovasında canlı doğrulama (CI'dan ve bu
konteynerden erişilemiyor).** Kod sahte S3'e karşı yeşil ve SigV4 AWS
vektörleriyle doğrulandı; R2'nin ÖZEL davranışı (jeton kapsamı, `auto` bölge,
`response-content-disposition`ı ön imzalı sorgudan okuması) ancak gerçek
kovada görünür. Sıra:

1. **Kova + jeton:** Cloudflare panosu → R2 → *Create bucket* (`kromis`) →
   *Manage R2 API Tokens* → *Create API token*: izin **Object Read & Write**,
   kapsam **yalnız bu kova**; *Access Key ID* ve *Secret Access Key* bir kez
   gösterilir, parola kasasına. Uç nokta `https://<hesap-id>.r2.cloudflarestorage.com`
   (hesap id panonun sağında; kova adı URL'de YOK). CORS gerekmez.
2. **Değişkenler** (platform sırlarına, `.env.example`deki açıklamalarla):
   `KROMIS_NESNE_DEPO_URL`, `_KOVA=kromis`, `_ANAHTAR_ID`, `_GIZLI`; `_BOLGE`
   boş (= `auto`).
3. **Taşıma, dağıtımdan ÖNCE**, aynı dört değişkenle konteyner içinden ya da
   `/data`ya erişen bir kabuktan:
   `python tools/medya_tasi.py --kaynak /data --kuru` (sayı; çıkış 3 =
   yüklenecek var) → `python tools/medya_tasi.py --kaynak /data` (çıkış 0 =
   hepsi kovada, her nesne HEAD ile doğrulandı) → `--kuru` yeniden: `0
   yuklenecek`.
4. **Dağıt** (dört değişken sürece girmiş olmalı; yarısı girmişse uygulama
   açılmaz ve `uvicorn` eksik adları söyler — kasıtlı).
5. **Canlı denetim**, giriş yapmış bir tarayıcıdan ya da çerezle `curl`:
   `curl -sI -b "kromis_oturum=<çerez>" https://<alan>/output/<dosya>` →
   `HTTP/2 302`, `cache-control: private, max-age=600`, `location: https://
   <hesap-id>.r2.cloudflarestorage.com/kromis/kullanicilar/<uuid>/output/<dosya>
   ?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=…&X-Amz-Date=…&X-Amz-Expires=900&
   X-Amz-Signature=…&X-Amz-SignedHeaders=host`; sonra
   `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' '<location>'` →
   `200 image/png` (ya da `video/mp4`); `curl -s -o /dev/null -w '%{http_code}\n'
   -H 'Range: bytes=0-7' '<location>'` → `206`. Galeride bir görsel açılıyor,
   bir video oynuyor ve ileri sarıyor (ağ sekmesinde aralık istekleri
   `r2.cloudflarestorage.com`a), `GET /api/output/<id>/download` 302 →
   tarayıcı `attachment` ile indiriyor, bir klasör ZIP iniyor (bu tek istek
   uygulamadan akar), `POST /api/import` + `/api/logo` + `/api/assets/logos`
   kovaya yazıyor (R2 panosunda `kullanicilar/<uuid>/…` görünür), başkasının
   `filename`i 404. Sonra `python tools/artik_dosya.py` aynı değişkenlerle
   `kova: kromis … 0 artik dosya` (çıkış 0).
6. **Sonuç bu belgeye** ("Yapıldığında"nın altına bir satır: tarih, kaç dosya
   taşındı, 302/206 görüldü); yerel `/data/kullanicilar/` arşivlenir — artık
   okunmuyor. Bir şey tutmazsa geri dönüş dört değişkeni silmek: yerel disk
   yerinde duruyor (`medya_tasi` silmedi).

**3. göreve devredilen.** İşçi `dosya.depo_kur(data_dir)` ile aynı depoyu
kurar ve `depo_medya.kaydet(…, depo=…)` çağırır; `Depo` arayüzü anahtarla
(`kullanicilar/<uuid>/…`) da konuşur, işçi `Ayarlar.varsayilan().kullanici_icin(uid)`
yollarını verebilir. Referans nesneleri (`istek` JSONB'deki anahtarlar) `depo.oku`
ile okunur; düşen satırın nesnesi `depo.sil` ile telafi edilir (bugün
`artik_dosya` topluyor). `compose.yaml`ın `isci` servisi yerel kipte AYNI
birimi paylaşmak zorunda (`/data`), platformda kova.

---

## 3. İşçi süreci — `isci.py`, `services/isci.py`: al → üret → yaz → bitir; compose `isci` servisi ✅ (PR: `faz2/isci`)

**Kapsam.** İkinci süreç. Giriş noktası kökte **`isci.py`** (`app.py` web'in
girişi nasılsa bu da işçinin: `python isci.py`; `Dockerfile` CMD DEĞİŞMEZ,
platform ikinci süreci aynı imajdan bu komutla açar — 10. görev), mantık
**`services/isci.py`**: açılışta `db.motor_kur(DATABASE_URL)` (kendi havuzu,
`pool_size = es_zamanli + 1`), `sifre.dogrula_ortam()` (web'deki kapı aynen:
anahtarsız işçi açılmaz, çözecek satırı var), `dosya.depo_kur()`, `isciler`
satırı; ana döngü `KROMIS_ISCI_ES_ZAMANLI` (öntanımlı **4**) iş parçacığı,
her biri `kuyruk.al` → yoksa **1 sn** uyu (`LISTEN/NOTIFY` YOK: senkron sürücüde
ayrı bağlantı ister ve 1 sn gecikme dakikalık işte görünmez; ölçülürse gelir)
→ varsa `kos(is)`. Kalp atışı AYRI bir iş parçacığında 30 sn'de bir
(`kuyruk.kalp` + `isciler.son_kalp`), çünkü sağlayıcı çağrısı adaptörün içinde
dakikalarca bloklar. Kapanış: SIGTERM → almayı bırak, eldeki işi bitir, sonra
çık (`kill_timeout`ın yetmediği yerde iş `calisiyor`da kalır, bayat düşürme
onu `hata` yapar — K8; 10. görev platform sürelerini yazar).

**`kos(is)` — rotanın gövdesi, istek olmadan.** `kimlik_baglami.bagla(
depo_kimlik_bilgisi.oku(db, kullanici_id))` (6. görevde platform anahtarıyla
birleşir), `dil.set_active(kullanici.dil)` (hata metinleri kullanıcının
dilinde — `hata` sütunu ONA gösterilecek), tür → mevcut sağlayıcı sözleşmesi:
`providers.generate/edit/generate_video/animate_video` (imzaları DEĞİŞMEZ;
`_azure_generate`in "kimliği önceden çözmüyor" mandalı aynen), girdi nesneleri
`dosya.oku(istek["girdiler"][...])`; sonuç baytları için **sıra: nesne yaz →
`depo_medya.kaydet` satırı → `kuyruk.bitir` → tek `commit`**; satır ya da commit
düşerse yazılan nesneler `dosya.sil` ile TELAFİ edilir ve iş `hata` — Faz 1 /
5'in "dosya + satır atomik değil" borcu işçide KAPANIR, çünkü işçi akışın iki
ucunu da tutuyor (web rotası tutamıyordu: commit bağımlılıkta, rota
döndükten sonra). `ac.ImageError` → `hata` metni (`redact_secrets`), başka
istisna → `hata` + `hata.log` + Sentry (9). Palet: `palet.palette_prompt`in
`prompt_sent`/`pal` hesabı ROTADA kalır ve `istek`e yazılır (istek anında
kullanıcının paleti; işçi yeniden hesaplamaz — palet sonradan silinse iş
değişmez). `kredi_tahmini` rotada; işçi gerçek `catalog.cost_for`u satıra
yazar (`medya.credits`, bugünkü gibi).

**Yeniden deneme YOK (K8).** Sağlayıcı çağrısı faturalanır; düşen işçinin
çağrıyı gönderip göndermediği bilinemez. Otomatik yeniden deneme çift fatura
riski; kullanıcı iş panelinden "yeniden gönder" der (5. görev, aynı `istek`
gövdesiyle yeni iş). Kuyruk yalnız `bekliyor`daki işi başka işçiye verir.

**Testlerde işçi süreç DEĞİL işlev.** `services/isci.tek_tur(db, dosya, an)`:
bir kez `al`, varsa `kos`, döner — rota/E2E testleri sağlayıcıyı yamalayıp
(`providers.generate` → sahte PNG; 104 testin bugünkü deyimi) `tek_tur`ü
çağırır, işi bitmiş görür. Ayrı süreç yok, port yok, uyku yok; `isci.py`nin
kendisi için tek test: `--tek-tur` bayrağıyla boş kuyrukta 0 ile çıkar (CI
`docker` işi bunu koşar, 10).

**Faz 1'den devralınan.** "Dosya + satır atomikliği — kök çözüm nesne depolama
+ worker ile Faz 2'de" (kapanır), `kimlik_baglami`nın "istek değil bağlam"
tasarımı (işçi bağlar), `KROMIS_SECRET_KEY` kapısı (`app._lifespan`in
"tek istisna"sı işçide de).

**Dokunulan.** yeni `isci.py` (kök, telif başlığı kapsamında), yeni
`services/isci.py`, `services/kuyruk.py` (küçük: `kos`un ihtiyacı), `compose.yaml`
(`isci` servisi: `image: kromis`, `command: ["python", "isci.py"]`, `depends_on
goc: service_completed_successfully`, aynı `environment`), `.env.example`
(`KROMIS_ISCI_ES_ZAMANLI`, `KROMIS_IS_KALP_ESIGI_SN` öntanımlı 300),
`.dockerignore` (kök `isci.py` imajda — bekçi), `KURULUM.md` (işçi süreci),
`tests/test_isci.py` (~30: `tek_tur` dört türde sahte sağlayıcıyla → `medya`
satırı + nesne + `bitti`; satır düşerse nesne silinir ve `hata`; sağlayıcı
hatası → `hata` redakte, anahtar yok; kalp ilerler; iki işçi iki iş; bayat
düşürme; kullanıcının dili hata metninde; kimlik bağlamı işten sonra çözülür;
anahtarsız açılmaz; `--tek-tur` boş kuyruk 0), `tests/test_docker_kapisi.py`,
`tests/test_i18n.py`, `tests/test_telif_basligi.py` (kökte yeni modül —
`git ls-files` kapsamı), `docs/graflar/*` (kök modül olarak haritada; `app`
gibi bir bileşim kökü, README'ye not).

**Risk.** Orta. Kırılma sınıfı: (a) işçi süreci kendi ContextVar'larını
bağlamayı unutur → adaptör "hiçbir şey yapılandırılmamış" der, 502 yerine
`hata` — bekçi test iki kullanıcının işini art arda koşturup anahtarları
kaydeder (`[A, B]`, Faz 1 / 7'nin testinin ikizi); (b) uzun süren sağlayıcı
çağrısında `Session` boş boş bağlantı tutar → `kos` sağlayıcı çağrısı SIRASINDA
`Session` AÇMAZ (al → commit; çağrı; yeni `Session` → yaz → commit), kalp
kendi bağlantısında; (c) SIGTERM'de yarım iş — K8.

**Çıkış ölçütü.** compose'ta `docker compose up`: `isci` açılıyor, `isciler`de
satır, kalp ilerliyor; testte `kuyruk.ekle` + `tek_tur` → `medya` satırı + nesne;
telafi testi geçiyor; takım yeşil.

**Yapıldığında (2026-09-18) ölçümler ve sapmalar.** Yeni `services/isci.py`
(425 satır: `kos`, `tek_tur`, `siradakini_al`, `kalp_turu`, `es_zamanli`/
`kalp_esigi`, `_YazimIzi` telafi sarmalayıcısı) ve kökte `isci.py` (258
satır: kapılar → motor → `isciler` satırı → N iş parçacığı + kalp iş
parçacığı → SIGTERM/SIGINT ile temiz kapanış; `--tek-tur`; testler/duman için
gizli `--kalp-araligi`). `Dockerfile` CMD DEĞİŞMEDİ; `compose.yaml` 3 → 4
servis (`isci`: `image: kromis`, `command: ["python", "isci.py"]`, göçü
bekler, web ile aynı `/data` birimi, port yok); `.env.example` +2
(`KROMIS_ISCI_ES_ZAMANLI`, `KROMIS_IS_KALP_ESIGI_SN`; `ALTYAPI` bekçisi 14 →
16); `services/db.py::motor_kur` `pool_size=` aldı (öntanımlı 2, işçi
`es_zamanli + 1`); `services/kuyruk.py` DOKUNULMADI (ilkeller yetti);
`tools/graf_uret.py` `GIRIS_NOKTALARI`na `isci` (ikinci bileşim kökü, README
notu). Ölçüler: modül 91 → 93, test dosyası 123 → 124, rota **54 DEĞİŞMEDİ**,
`static/` DOKUNULMADI, takım **3.506 → 3.545 geçti, 12 atlandı, 199 sn** (E2E +
Postgres zorunlu); ruff/mypy temiz. Yeni `tests/test_isci.py` **35 test** (dört tür; kredi
katalogtan, tahmin değil; `prompt_sent` rotanın; n satır sıralı; telafi üç
yoldan — FK düşüşü, `bitir` düşüşü, bayat düşürülmüş iş; nesne → satır →
`bitir` → tek commit sırası olay dinleyicisiyle; redakte sağlayıcı hatası;
beklenmeyen istisna KOD + `hata.log`; bilinmeyen model; eksik girdi ve
sağlayıcı hatası kullanıcının dilinde (tr/en parametrik); dil seçmemiş
kullanıcı `i18n.DEFAULT`; `[A, B]` kimlik bekçisi + istisnada da çözülme;
çağrı sırasında `pool.checkedout() == 0`; iki işçi iki iş; kalp ilerler ve
bayatı düşürür; ortam değişkeni ayrıştırma; kaynak taraması "web'in
kapıları işçide"; alt süreç: anahtarsız/URL'siz 2, yarım kova 2, bozuk
eş zamanlılık 2, `--tek-tur` boş kuyrukta 0 ve `isciler`e yazmaz, `--tek-tur`
gerçek süreçte kimliksiz işi `hata`ya indirir, tam süreç kaydolur → kalp
ilerler → SIGTERM → 0 ve satır silinir). **Canlı duman** (geçici küme, bu
makine): `goc.py` → `0004_isler`; sahte sağlayıcıyla `isci.main(["--tek-tur"])`
→ iş `bitti`, `sonuc.medya` 2 id, 2 `medya` satırı = diskte 2 nesne;
gerçek `python isci.py` → `isciler` satırı (`es_zamanli=2`), 1 sn'de kalp
ilerledi, SIGTERM → "yeni is alinmiyor, eldeki 0 is bitirilecek" → çıkış 0,
satır silindi, `hata.log` yok.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) `istek` SÖZLEŞMESİ
`services/isci.py`nin başında yazılı ve 4. görevin girdisi: ortak `prompt,
size, quality, n, folder_id, session_id`; generate `arena_id, palette,
prompt_sent`; edit `girdiler [{"ad", "anahtar"}], parent_id, palette,
prompt_sent`; video `duration`; animate `girdiler, parent_id, duration,
son_kare`. `anahtar` depo YOLU (kök göreli, `kullanicilar/<uuid>/isler/…`),
`ad` adaptöre giden dosya adı (`abc123.png`, `upload.png`, `refN.png` —
rotanın bugünkü adları). Model `isler.model`den. (b) TELAFİ SARMALAYICIYLA:
`depo_medya.kaydet` dosya adını içinde üretiyor ve flush düşerse adı
söyleyemez; `_YazimIzi` depoyu sarar, yazılan yolları tutar, düşüşte hepsini
siler — `kaydet`in imzası değişmedi. (c) `kos` ÜÇ KISA OTURUM açar (kullanıcı +
kimlik okuması; yazım; düşüş) ve sağlayıcı çağrısı boyunca hiçbirini —
`siradakini_al` satırı commit'ten ÖNCE `expunge` eder (yoksa
`expire_on_commit` ilk öznitelik okumasında bağlantı açardı). (d) Dil:
`kullanicilar.dil`, NULL ise `i18n.DEFAULT` (belge `FALLBACK`ı ima ediyordu;
`i18n`in kendi ayrımı "kullanıcı seçmemiş" ≠ "kullanıcı yok" ve burada
kullanıcı var). Dil ve kimlik bağlamı `finally`de sıfırlanır. (e) Beklenmeyen
istisnanın `hata` metni `beklenmeyen hata: <TürAdı>` — mesaj değil (yol ve
parametre sızdırabilir), iz `hata.log`da; sağlayıcı hatası (`ImageError`)
günlüğe YAZILMAZ (beklenen hata, `hata` sütunu yeter). (f) Eksik girdi
nesnesi rotanın 404 metniyle (`err.source_image_missing`) `hata` — modül bu
tek yerde kullanıcıya konuşur, `test_i18n`de KONUŞAN listesinde. (g)
Girdi nesneleri işçi tarafından SİLİNMEZ (belge 4. göreve "iş bitince
silinir" yazmış): silme kararı rotanın — "yeniden gönder" (5) aynı
nesneleri kullanabilir, `artik_dosya.py` `isler/` önekini tarar. (h) Kalp iş
parçacığı `bayatlari_dusur`u da çağırır (eşik `KROMIS_IS_KALP_ESIGI_SN`):
ölen işçinin işini yaşayan işçi `hata`ya çeker, 10. görevin bakımı aynı
işlevi çağırır. (i) İş parçacığı döngüsü istisnada ÖLMEZ (iz + 1 sn +
devam): sessizce düşen kapasite en geç görünen kusur. (j) `hata`ya düşen
işin nesnesi de SİLİNİR (telafi her yolda), yani düşen iş disk/kovada iz
bırakmaz. (k) Günlük stdout'a tek satır ASCII (`isci: …`), 9. görev JSON'a
çevirir; `isciler.konak` `socket.gethostname()`, `surum` `version.APP_VERSION`.

**4. göreve devredilen.** Rotalar sağlayıcıyı çağırmaz: doğrulama aynen →
multipart girdiler `depo.yaz("kullanicilar/<uuid>/isler/<is_id>/<ad>")` →
`palet.palette_prompt` (`prompt_sent`, `pal`) ve `catalog.cost_for × n`
(`kredi_tahmini`) ROTADA → `kuyruk.ekle(db, kullanici.id, tur, istek, model,
kredi_tahmini)` → **202** `{"is": kuyruk._json(is)}`. `istek` yukarıdaki (a)
sözleşmesiyle; `girdiler[0]` ana referans, `parent_id` galeriden seçildiyse.
Test deseni: sağlayıcıyı yamala (`providers.generate` …) → `POST` 202 →
`isci.tek_tur(db, depo, ayarlar=…)` → `GET /api/history`de kayıt; conftest'e
`uret_ve_bitir(client, …)` yardımcısı. `tek_tur`ün `ayarlar`ı testte
`app.state.ayarlar`, depo `app.state.dosya`. Girdi nesnelerinin ömrü rotanın
kararı (g). E2E fixture'ına `tek_tur` döngüsü iş parçacığı (belge §4).

---

## 4. Üretim rotaları 202 döner; `GET /api/isler`, iptal; kullanıcı başına eş zamanlı iş; `core.js` asgari uyum ✅ (PR: `faz2/uretim-202`)

**Kapsam.** Dört rota (`routers/uretim.py`) sağlayıcıyı ÇAĞIRMAZ: bugünkü
doğrulamanın tamamı (pydantic, `_check_edit_form`/`_check_video_form`,
`check_folder`, palet kapıları, 413/422 mesajları — bayt bayt) → multipart
girdiler `dosya.yaz("kullanicilar/<uuid>/isler/<is_id>/ref1.png")` → `kuyruk.ekle`
→ **202** `{"is": kuyruk._json(is)}`. `generate`/`video` `def` kalır,
`edit`/`animate` `async def` + `run_in_threadpool` (Faz 1 / 1 kararı). Bayat
sunucu tespiti (`core.js`nin "yanıt alanı geri yankılıyor mu" deseni) `is.model`
üzerinden sürer. Yeni `routers/isler.py`: `GET /api/isler` (`?since=` ile
artımlı; öntanımlı aktifler + son 50), `GET /api/isler/{id}`, `POST
/api/isler/{id}/iptal` (yalnız bekleyen; 409 aksi) — üçü kapılı, sahip
süzgeçli. Rota sayısı **54 → 57** (`tests/test_app_bolme.py`), `ACIK_ROTALAR`
değişmez, `DIZINSIZ_KAPILI` +3.

**Kullanıcı başına eş zamanlı iş — `KROMIS_KULLANICI_ES_ZAMANLI_IS` öntanımlı 4.**
`kuyruk.aktif_sayisi ≥ tavan` → **429** + `Retry-After: 30` + i18n gövde
(`err.is_kuyrugu_dolu`). 4, çünkü arena turu istemci fan-out'uyla 2-4 ayrı
istek (`core.js:2712`) ve dördüncü sütunun 429 yemesi turu "3/4" diye
bitirirdi. Sayım kullanıcının `bekliyor + calisiyor` işleri; küresel işçi
kapasitesi ayrı (`KROMIS_ISCI_ES_ZAMANLI × işçi sayısı`). Saatlik iş tavanı
ve kredi tavanı 6. görevde (platform parası orada devreye giriyor).

**Ön yüz — asgari uyum, iş paneli DEĞİL (o 5).** Bu PR tek başına yeşil
kalmalı ve E2E stüdyoyu sınıyor: `core.js` 202 alınca `GET /api/isler/{id}`i
**2 sn**de bir yoklar (`bitti` → `sonuc.medya` id'lerini `GET /api/history`
üzerinden çeker ve bugünkü `showPreview`/`loadHistory` akışına aynı şekle
sokar; `hata` → bugünkü hata satırı), `runBusy`/durum metni AYNEN ("Üretiliyor…"
+ video süresi). Sekme yenilenirse iş sürer ama ekran onu göstermez — 5'te
kapanır; belgeye "bilinen ara durum" diye yazılır. `index.html`e dokunulmaz
(286 metin çapası). Arena: `sonuclar[i]` doldurma yoklama sonuna kayar,
`fillArenaSlot` aynen.

**Faz 1'den devralınan.** `routers/uretim.py`nin "sekme yenilenirse iş
kaybediliyor … cevabı bir iş kuyruğu ve o ayrı bir madde" notu (bu madde);
"5 `async def` rota `run_in_threadpool`" kararı.

**Dokunulan.** `routers/uretim.py` (dört gövde kısalır; yardımcılar kalır),
yeni `routers/isler.py`, `app.py` (`include_router`), `models.py`
(`IsDokumu`? — hayır: döküm `kuyruk._json`, pydantic çıktı modeli yok, bugünkü
deyim), `services/kapilar.py` (eş zamanlılık kapısı), `static/core.js`
(yoklama), `bundled/i18n/{tr,en}.json` (+~6: kuyrukta, 429, iptal),
`.env.example` (+1), `tests/test_video_route.py` / `test_edit_route.py` /
`test_app.py` / `test_arena.py` / `test_model_secimi.py` (~15 dosya `providers.*`
ya da `ac.generate`i yamalıyor ve `{"images"}` bekliyor → **202 + `tek_tur`
+ `GET /api/history`** kalıbına; conftest'e yardımcı `uret_ve_bitir(client,
...)`: POST → `tek_tur` → sonuç kayıtları — eski iddialar tek satır değişerek
durur), yeni `tests/test_isler_route.py` (~20: 202 gövdesi, doğrulama
hataları AYNI kodlarla (422/413/404) ve sıraya iş yazmaz, girdi nesneleri
yazılır ve iş bitince silinir, liste/tekil/iptal, başkasının işi 404, 5. iş
429 + `Retry-After`, arena 4 sütun geçer, `since`), `tests/test_playwright_studio.py`
(E2E fixture'ına işçi: `ServerThread` yanında `tek_tur` döngüsü iş parçacığı
— sahte sağlayıcı, gerçek kuyruk), `tests/test_kimlik.py` (rota envanteri),
`docs/graflar/*`.

**Risk.** Orta-yüksek: en geniş test dokunuşu (~15 dosya) ve ürün davranışı
görünür değişiyor (yanıt 200 → 202). Küçültme: doğrulama kodu TAŞINMAZ,
yalnız sağlayıcı çağrısı + kayıt satırları çıkar; `uret_ve_bitir` yardımcısı
eski iddiaları korur; E2E aynı kullanıcı akışını sınar (üret → galeri).
Girdi nesneleri: iş bitince/düşünce silinir, `artik_dosya.py` `isler/`
önekini de tarar.

**Çıkış ölçütü.** Tarayıcıdan üretim bugünkü gibi bitiyor (E2E), sunucu
günlüğünde sağlayıcı çağrısı yalnız işçide; `POST /api/generate` 50 ms
altında 202 (sağlayıcı yamalı ölçüm); 5. eş zamanlı iş 429; takım yeşil.

**Yapıldığında (2026-09-18) ölçümler ve sapmalar.** `routers/uretim.py`
dört gövde kısaldı (`providers`, `azure_client`, `depo_medya`, `zaman`
ithalleri gitti; üç yardımcı — `_check_edit_form`, `_check_video_form`,
`_collect_edit_refs` — bayt bayt yerinde; yeni `_girdileri_yaz`,
`_siraya_koy`, `_ortak_istek`, `ISLER_DIZINI`); yeni `routers/isler.py` (3
rota, 100 satır); `services/kapilar.py` +`check_is_tavani`/
`es_zamanli_is_tavani` (429 + `Retry-After: 30`, `err.is_kuyrugu_dolu`);
`services/kuyruk.py` KÜÇÜK dokunuş (belge "dokunulmaz" demiyordu, 3. görev
dokunmamıştı): `ekle(is_id=…)`, `listele(durumlar=…)`, yeni `bul` — üçü de
rotanın ihtiyacı, işçi tarafı aynen. `static/core.js` +`isiBekle`/
`yanittakiIs`/`isSonuclari` (2 sn yoklama; `run` ve `runArena` yanıtı işe,
işi kayıtlara çevirir; `runBusy`/durum metni, `showPreview`, `fillArenaSlot`,
gövde ifadeleri AYNEN; `index.html` DOKUNULMADI). `bundled/i18n/{tr,en}.json`
+7 (`err.is_kuyrugu_dolu`, `err.is_bulunamadi`, `err.is_iptal_edilemez`,
`err.bad_since`, `gen.job_failed`, `gen.job_cancelled`,
`gen.no_job_in_response`); `.env.example` +1 (`KROMIS_KULLANICI_ES_ZAMANLI_IS`,
`ALTYAPI` 16 → 17). `tools/artik_dosya.py` `isler/<is_id>/` önekini iki kipte
de tarar (ölçüt DOSYA ADI değil İŞ SATIRI: satırı olan işin girdileri durur).
Ölçüler: rota **54 → 57**, modül 93 → 94, test dosyası 124 → 125, takım
**3.545 → 3.583 geçti, 12 atlandı, 206 sn** (E2E + Postgres zorunlu);
ruff/mypy/eslint/prettier temiz. **Gecikme:** yamalı sağlayıcıyla `POST
/api/generate` 20 istekte **ortanca 8,1 ms** (en iyi 7,4, en kötü 9,5; bu
makine, Postgres aynı konteynerde) — 50 ms ölçütünün altında; iddia 250 ms
(CI gürültüsüne pay). **Test dokunuşu:** 15 dosya `c.post("/api/generate"…)`
→ `uret_ve_bitir(c, "/api/generate"…)` (conftest yardımcısı POST → 202 →
`isci.tek_tur` → `IsSonucu`: eski yanıtın ŞEKLİNDE — `bitti` 200 +
`{"images"|"videos": kayıtlar}`, `hata` 502 + `detail`, 202 dışı yanıt
olduğu gibi — eski iddialar TEK SATIR değişerek durdu; işçi paylaşılan
yerleşime yazar, `_PaylasilanYerlesim`, `kullanici` override'ının ikizi);
`test_kimlik` kendi işçi turunu GERÇEK yerleşimle koşar. Yeni
`tests/test_isler_route.py` **32 test** (202 gövdesi + `istek` dökülmez;
doğrulama 10 parametrik hâl AYNI kodlarla ve iş/nesne yazmaz; 413; kaynak
bekçisi "rota `providers`ı ithal etmez"; girdiler `isler/<is_id>/` altında
adaptör sırasıyla, son kare ayrı; girdiler iş bitince DURUR; galeri
referansı `parent_id` + kopya; liste en yeni üstte / aktifler + son 50 /
`since` + 422; tekil ve iptal, başkasının işi 404, biçimsiz id 422, çalışan
ve bitmiş iş 409; 5. iş 429 + `Retry-After` + i18n, 429 nesne bırakmaz;
arena 4 sütun; tavan ortamdan ve bozuk değer yüksek sesle; sayaç kullanıcı
başına; gecikme; gerçek yerleşimde işçi kullanıcı dizinine yazar).
`tests/test_playwright_studio.py` `ServerThread` yanına `IsciThread`
(`tek_tur` döngüsü, aynı süreç, gerçek kuyruk, boşta 0,2 sn) — 13 E2E
aynen geçti, tarayıcı akışı üret → galeri işçi üzerinden bitiyor.
**Canlı duman** (geçici küme, bu makine): `goc.py` → `uvicorn` + AYRI süreçte
`python isci.py` (sağlayıcı `sitecustomize` ile yamalı, repo'ya dokunmadan) →
`POST /api/generate` **202, 27,9 ms** (soğuk ilk istek, gerçek uvicorn) →
işçi günlüğü "is aldi … is bitti" → `GET /api/isler/{id}` `bitti`,
`sonuc.medya` 1 id → `GET /api/history` 1 kayıt = diskte
`kullanicilar/<uuid>/output/` altında 1 nesne → `GET /api/isler` 1 iş →
SIGTERM → işçi 0 ile kapandı. Web sürecinin günlüğünde sağlayıcıya dair tek
satır yok: çağrı yalnız işçide.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) GİRDİ NESNELERİNİN ÖMRÜ —
§3 kararı (g) uygulandı, bu bölümün "iş bitince silinir" satırından BİLİNÇLİ
SAPMA: işçi silmez, rota silmez; "yeniden gönder" (5) aynı nesneleri kullanır,
saklama (10) satırla birlikte düşürür, `artik_dosya.py` satırsız `isler/<id>/`
dizinini artık sayar. Test "yazılır ve iş bitince silinir" değil "yazılır ve
DURUR" diye ölçüyor. (b) `kimlikler` dört üretim rotasının İMZASINDAN ÇIKTI:
kimliği işçi çözer (`kos`); rotada tutmak her isteğe bir sorgu + N Fernet
çözümü eklerdi (`KIMLIK_OKUYAN` bekçisinin kendi gerekçesi). Bedeli: anahtarı
olmayan kullanıcı 502 yerine `hata`lı bir iş görür (aynı metin); erken "anahtar
yok" kapısı 6. görevin platform anahtarıyla birlikte düşünülmeli. (c) `ayarlar`
`generate`/`video`da KALDI (dizin okumasalar da): bağımlılık kullanıcı
dizinlerini ilk istekte açar ve rota `test_kimlik`te "kullanıcı verisine
dokunan" sınıfında kalır; `DIZINSIZ_KAPILI` yalnız 3 iş rotasıyla büyüdü
(belgenin "+3"ü). (d) SIRA: doğrulama → 429 kapısı → girdi nesneleri → satır
(`is_id` rotada `uuid4`, `kuyruk.ekle(is_id=…)`): 422 alacak istek 429 ile
maskelenmez, 429 alacak istek nesne bırakmaz, satır ancak nesneler yazıldıysa
doğar. (e) `GET /api/isler` öntanımlısı "aktifler + son 50" İKİ sorgu
(`listele(durumlar=AKTIF_DURUMLAR)` ayrı): 51. sıraya düşmüş `bekliyor` iş
kaybolmasın; `since` `zaman.damga` biçimi ya da dilimli ISO, bozuksa 422
(`err.bad_since`). (f) 202 gövdesinde `{"videos": …}` anahtarı yok, tür
`is.tur`; ön yüzde `videoMu ? govde.videos : govde.images` gitti, dört tür
aynı iş kaydından okunur (`test_video_onyuz` çapası buna göre). (g) `dizinler`
fixture'ı `data_dir` yönlendirilince `app.state.dosya`yı da oraya çeker
(yalnız `YerelDepo`): rota kök göreli anahtarla yazıyor, depo repo kökünde
kalsa testler depoya `kullanicilar/` bırakırdı. (h) `_PaylasilanYerlesim`
işçiye verilen ayar nesnesi — `kullanici_icin` kendini döndürür; gerçek
türetim `test_kimlik`/`test_isci`/E2E'de ölçülüyor. **Bilinen ara durum:**
sekme yenilenirse iş sürer, ekran onu göstermez (galeri yenilenince sonuç
orada); yoklama düşerse (ağ) prompt kutuya döner, iş yine sürer — ikisi 5'te
kapanır. Sağlayıcı yamalanmamış bir kurulumda anahtarsız üretim artık 502
değil `hata`lı iş (test_kimlik bunu ölçüyor).

**5. göreve devredilen.** SSE `GET /api/isler/akis` (yoklama yedek yol olarak
kalır; `since` ve `listele(durumlar=…)` hazır); `static/isler.js` paneli
(liste/tekil/iptal uçları hazır, `iptal` yalnız `bekliyor`); "yeniden gönder"
— girdi nesneleri `isler/<is_id>/` altında duruyor, `istek` satırda, yeni iş
aynı anahtarları `girdiler`e kopyalayabilir (nesne kopyası mı referans mı,
saklama (10) ile birlikte kararlaştırılır); sekme yenilemeye dayanıklılık
(`bekliyor`/`calisiyor` işleri açılışta panele çekmek, biten işi galeriye
düşürmek); `core.js`teki `isiBekle`/`isSonuclari` panel gelince SSE'nin
arkasına geçer ya da kalkar; 429'un `Retry-After`ını okuyan istemci davranışı
(bugün yalnız metin gösteriyor).

---

## 5. İş listesi: SSE `GET /api/isler/akis`, `static/isler.js` paneli, sekme yenilemeye dayanıklılık; ön yüz çerçevesi kararı ✅ (PR: `faz2/is-listesi-sse`)

**Kapsam.** Çıkış kriterinin ilk yarısı. **Sunucu:** `GET /api/isler/akis` —
`text/event-stream`, `async def`, `Last-Event-ID`/`?since=` ile kaldığı
yerden; döngü **1,5 sn**de bir `run_in_threadpool(kuyruk.listele, since=…)`
(bağlantı yalnız sorgu anında alınır ve bırakılır — `pool_size=2`nin
gerekçesi), değişen işleri `event: is` + JSON olarak yazar, 15 sn'de bir `:
kalp` yorumu (vekiller boş bağlantıyı 30-60 sn'de kesiyor), 10 dk'da bağlantıyı
kendisi kapatır (istemci yeniden bağlanır; uzun ömürlü bağlantı sızıntısı
sınıfı). `Cache-Control: no-store`, `X-Accel-Buffering: no`. Kapılı; kimlik
bağımlılığı aynen. Rota **57 → 58**.

**SSE, WebSocket DEĞİL, salt yoklama DEĞİL (K2).** Akış TEK YÖNLÜ (sunucu →
istemci; istemci POST'la konuşuyor), `EventSource` yeniden bağlanmayı ve
`Last-Event-ID`yi tarayıcıda ücretsiz veriyor, oturum ÇEREZİ aynı kökende
kendiliğinden gidiyor (WebSocket'te köken kapısı ve çerez ayrı iş,
`services/koken.py`nin `Sec-Fetch-Site` mantığı `Upgrade` isteğinde farklı
davranır). Salt yoklama (`GET /api/isler` 3 sn) YEDEK olarak kalır:
`EventSource` üç kez düşerse istemci yoklamaya geçer — SSE'nin
desteklenmediği ya da vekilin kestiği ortamda liste yine çalışır.

**Ön yüz:** yeni `static/isler.js` (yükleme sırasında `settings.js`ten önce;
`index.html`e TEK `<script>` satırı + bir panel çapası — `test_index`in
286 iddiasına dokunmayan ek), `style.css`e panel: her iş bir satır (tür
simgesi, model etiketi `etiket`, durum, geçen süre; `bitti`de küçük
önizleme `GET /api/history`den, `hata`da metin + "yeniden gönder", `bekliyor`da
"iptal"). Açılışta `GET /api/isler` (aktifler + son 50) → panel dolar →
`EventSource` bağlanır; **sekme yenilenince aktif işler geri gelir** ve
bitince galeri `loadHistory` ile yenilenir. `core.js`nin 4'teki yoklaması
kalkar: 202 → `isler.js`e teslim (`kaydetIs(is)`), `runBusy` artık KİLİT
DEĞİL (birden fazla iş sıraya girebilir; #go serbest, eş zamanlılık sınırı
sunucuda 429 ve panelde okunur). Arena: 2-4 iş aynı `arena_id`, panelde
grup; `fillArenaSlot` bitince. i18n +~15 anahtar. eslint defteri
(`eslint.paylasilan-adlar.json`) yeni betik; `tests/test_id_contract.py`
yeni betiği görür.

**Çerçeve kararı — vanilla SÜRER, karar belgeye yazılır (K3).** Faz 0 / 7 ve
Faz 1 bu kararı "iş listesi/SSE arayüzüyle" bıraktı; ölçü: iş paneli ~350
satır, admin sayfası (8) ~300 satır — ikisi de `giris.js`nin deyimiyle (IIFE,
`fetch`, DOM) yazılır. React/Svelte + paketleyici: Docker'a Node derleme
aşaması (imaj ve derleme süresi), CI'da ikinci bir derleme, `test_index`in
286 metin iddiası ve `test_id_contract`ın ad çakışması bekçisi yeniden
tasarlanır — 650 satır için değil. Yeniden bakış noktası **Faz 4**: fatura/
plan/hesap sayfaları geldiğinde sayfa sayısı ve form yoğunluğu ölçülür;
`docs/superpowers/specs/2026-09-17-onyuz-paketleme.md`ye bu PR'da bir
"2026-09 kararı" bölümü eklenir (envanteri orada).

**Faz 1'den devralınan.** "Ön yüz çerçevesi / ES modül → karar Faz 2'nin iş
listesi arayüzüyle" (kapanır), `core.js`nin `window.fetch` tek kapısı (401
davranışı `EventSource`a da: `onerror`da `GET /api/hesap/ben` 401 ise `/giris`).

**Dokunulan.** `routers/isler.py` (+1 rota), yeni `static/isler.js`,
`static/index.html` (1 `<script>` + 1 panel kökü), `static/style.css`,
`static/core.js` (yoklama çıkar, teslim girer; `runBusy` anlamı), `static/chat.js`
(arena bitişi `isler.js`ten), `bundled/i18n/*`, `eslint.paylasilan-adlar.json`,
`docs/superpowers/specs/2026-09-17-onyuz-paketleme.md`, `tests/test_isler_route.py`
(SSE: `TestClient.stream` ile ilk olay, `since`, kalp yorumu, kapı 401, yalnız
kendi işleri — `kuyruk.listele` yoklama aralığı env ile 0,05 sn'ye çekilir),
yeni `tests/test_playwright_isler.py` (E2E, ÇIKIŞ KRİTERİ: sahte sağlayıcı
**8 sn** uyur, iş gönderilir, SAYFA KAPATILIR, işçi iş parçacığı bitirir, yeni
sayfa açılır → panelde `bitti`, galeride görsel; ikinci test: iki iş sırada,
yenileme sonrası ikisi de panelde; üçüncü: hata → "yeniden gönder" yeni iş),
`tests/test_index.py` (yalnız yeni çapa için +1-2 iddia), `tests/test_onyuz_lint_kapisi.py`,
`docs/graflar/*` (`onyuz.md` yükleme sırası 11 → 12 betik).

**Risk.** Orta. Kırılma sınıfı: (a) vekil SSE'yi tamponlar → kalp yorumu +
`X-Accel-Buffering` + yoklama yedeği; (b) `EventSource` bağlantı başına bir
tarayıcı bağlantı yuvası (HTTP/1.1'de 6 sınırı) — tek akış, tek sekme başına;
(c) `runBusy` kilidi kalkınca çift tıklama iki iş → #go 1 sn devre dışı +
sunucu 429. E2E süresi: sahte sağlayıcının 8 sn uykusu tek testte, ölçülür.

**Çıkış ölçütü.** E2E: sekme kapalıyken biten iş yeni sekmede görünüyor
(gerçek 6 dk video yerine 8 sn sahte — süre değil süreç sınanıyor; canlı
doğrulama sahibin anahtarıyla gerçek bir videoda bir kez); yenilemede aktif
işler panelde; SSE düşerse yoklama sürüyor; takım yeşil.

**Yapıldığında (2026-09-18).** `routers/isler.py` +2 rota (belge "+1"
diyordu, sapma aşağıda): `GET /api/isler/akis` — `async def`,
`StreamingResponse(text/event-stream)`, `Cache-Control: no-store`,
`X-Accel-Buffering: no`; döngü `AKIS_YOKLAMA_SN` (1,5) sn'de bir
`run_in_threadpool(_akis_sorgusu)` ve `Session` YALNIZ sorgu süresince açık
(isteğin `OTURUM`u imzada, ama yalnız motoru vermek için: `scope="function"`
onu rota dönerken kapatıyor; test akış açıkken `pool.checkedout() == 0`
ölçüyor); değişen iş `id: <sorgu anı, ISO µs>` + `event: is` + JSON, aynı hâl
ikinci kez yazılmaz; `: kalp` 15 sn, akış 10 dk'da kendini kapatır;
`Last-Event-ID` başlığı `?since=`in önünde, ikisi `_since`ten (bozuk 422).
Üç zaman + örtüşme MODÜL SABİTİ (env değil; `.env.example`/`ALTYAPI`
büyümedi), testler `monkeypatch` ile 0,05 sn'ye çeker. Ve `POST
/api/isler/{id}/yeniden` (202): `hata`/`iptal` işi aynı `istek`le yeni satır;
aktif/bitmiş 409 (`err.is_yeniden_gonderilemez`), başkasının 404, tavan 429.
`kuyruk.satir` (ORM satırı, sahip süzgeçli; `istek`i taşıyan tek okuma),
`KAPANMIS_DURUMLAR`; `_json` `istek`ten İKİ alan döker — `arena_id` (panel
gruplaması) ve `folder_id` (önizlemenin klasörü), ikisi de `medya`da zaten
görünür; prompt ve anahtarlar içeride (test_kuyruk'un kaynak bekçisi artık
"`.get` ile yalnız bu iki anahtar" diye ölçüyor). Yeni `static/isler.js`
(505 satır, IIFE, tek üst düzey ad `kromisIsler`): açılışta `GET /api/isler`
→ `EventSource` → satır başına tür/model etiketi/durum/geçen süre, `bitti`de
önizleme (`GET /api/history?folder_id=`), `hata`da metin + "yeniden gönder",
`bekliyor`da "iptal"; aktif iş rozeti üst şeritte (`#isler-btn`), panel sağ
sheet (`#isler-sheet`); `open` görmeden üç düşüş ya da CLOSED → 3 sn yoklama;
`onerror`da `GET /api/hesap/ben` (401 → `/giris`, core.js sarmalı). `core.js`:
`isiBekle`/`isSonuclari`/`IS_YOKLAMA_MS` KALKTI, 202 → `kromisIsler.kaydetIs(is,
{bitince, hatada})`; `run()`ın sonuç akışı (önizleme, yankı denetimi, döküm,
galeri) `bitince` geri çağrısına taşındı, `runArena` sütun başına aynı sözü
bekliyor (`fillArenaSlot` aynen); `runBusy` artık yalnız SOHBET turunun
bayrağı (chat.js yazıyor), üretim kilidi yok; #go gönderim kabul edilince
1 sn soğur (`goSogut`, `gate.sent`); 429 cümlesi durum satırında, `Retry-After`
ipucu panelde (`kromisIsler.uyar`). `index.html`: 1 `<script>` (palette →
**isler** → settings), 1 panel kökü + 1 tetik düğmesi (belgenin "bir çapa"sı
iki eleman oldu: sheet deseninde tetik panelden ayrı yaşıyor). i18n **+21**
(`isler.*` 19, `gate.sent`, `err.is_yeniden_gonderilemez`); eslint defteri
`static/isler.js: [kromisIsler]`; `test_id_contract.JS_FILES` +1 (sıra
sayfayla). Ölçüler: rota **57 → 59**, betik 11 → 12, betik-arası bağ 29 → 33,
test dosyası 125 → 126, takım **3.583 → 3.605 geçti, 12
atlandı, 250 sn** (E2E + Postgres zorunlu); ruff/mypy/eslint/prettier
temiz. **E2E** (`tests/test_playwright_isler.py`, 4 test, 37,8 sn): (1) 8 sn
uyuyan sağlayıcı, iş gönder, SAYFA KAPAT, işçi bitirir, yeni sayfa → panelde
`bitti` + önizleme, galeride 1 kart — **9,7 sn** (8 sn uyku dâhil); (2) iki
iş sırada (#go kilit değil), yenileme sonrası ikisi de panelde, ikisi de SSE
ile `bitti`, galeride 2 kart; (3) sağlayıcı düşer → satır `hata` + düğme →
`yeniden` → ikinci satır, düzelen sağlayıcıyla `bitti`, prompt kutuya
dönmüş; (4) `/api/isler/akis` tarayıcıda kesilir → üç düşüş → yoklama
mesajı → iş yine `bitti`. `tests/test_isler_route.py` 32 → 43 (+akış 6,
+yeniden 5, +bitiş damgası 1). **Canlı duman** (geçici küme, `goc.py`,
uvicorn + AYRI süreçte `python isci.py`, sağlayıcı `sitecustomize` ile
yamalı): `curl -N` çerezli akış → `retry: 3000` → `POST /api/generate` 202
(18 ms) → akışta `bekliyor` → `calisiyor` → `bitti` (`sonuc.medya` 1 id) →
`: kalp` → `GET /api/history` 1 kayıt; çerezsiz akış 401; SIGTERM → işçi 0.

**Ölçülen kusur (3. görevden):** işçi `bitti` sütununa işin BAŞINDA aldığı
anı yazıyordu (`kos` → `bitis = zaman.an()` en üstte) — `bitti ≈ basladi`,
sağlayıcı dakikalarca sürse de. E2E (2) yakaladı: akışın `since` sorgusu
`GREATEST(olusturuldu, basladi, bitti) > since` ve başlangıcına damgalanmış
bir bitiş hiçbir `since`in ötesine geçmiyor; işçi bitiriyor, panel
`calisiyor`da donuyordu. Düzeltme `services/isci.py`: bitiş anı BİTİŞTE
ölçülür (`an` verilmişse aynen — testler); bekçisi
`test_the_finish_stamp_is_taken_when_the_job_finishes_not_when_it_starts`.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) "YENİDEN GÖNDER"
SUNUCUDA ve bu ikinci rotanın gerekçesi: `istek` §4 sözleşmesiyle dökülmüyor
ve üretim rotaları anahtar değil bayt/galeri id'si alıyor — istemcinin "aynı
isteği yeniden POST etmesi" ya `istek`i dökmek ya girdi baytlarını tarayıcıda
saklamak demekti (yenilemede kaybolur). Rota 57 → 58 yerine **59**. (b) GİRDİ
NESNELERİ: KOPYA DEĞİL REFERANS — yeni işin `istek.girdiler`i eski
`isler/<eski_id>/…` anahtarlarına bakar, yeni işin kendi dizini yok (test
ölçüyor). Kopya her yeniden gönderimde referans görselleri ikinci kez yazmak
demekti; bedeli saklamaya (10) düşer: bir işin dizini ancak ona bakan hiçbir
satır kalmadığında silinir (`artik_dosya.py`nin ölçütü zaten satır). (c)
`arena_id` yeniden gönderimde DÜŞER: tur kapandı, beşinci sütun
`fillArenaSlot`ın beklediği bir şey değil. (d) Akışın İLK TURU aktifler +
son 30 sn'de değişenler (`AKIS_ILK_PENCERE_SN`): yalnız aktifler yetmiyordu,
E2E ölçtü — liste → bağlanma arasında biten iş ilk turda gelmiyor, sonraki
turlar da "bağlandıktan sonra"yı soruyordu. (e) `since` ÖRTÜŞMELİ
(`AKIS_ORTUSME_SN` 2 sn): damga Python'da yazılıp commit sonra geliyor;
yinelenen olay zararsız (istemci id'ye göre çizer, sunucu aynı hâli ikinci
kez yazmaz). (f) `retry: 3000` ilk satır: başlıklar hemen gider, tarayıcı
`open` görür, yeniden bağlanma aralığı sunucunun sözü. (g) YOKLAMAYA GEÇİŞ
kalıcı (bu sekmede akış bir daha denenmez): "üç düşüş" zaten ortamın
söylediği şey, tekrar denemek aynı düşüşü tekrar yaşatır; yenileme sıfırlar.
(h) `TestClient` akışı SONUNA KADAR tamponluyor (starlette `BytesIO`): akış
açıkken araya girmek için testler isteği ayrı iş parçacığına veriyor
(`_AkisOkuyucu`), akış `AKIS_AZAMI_SN`de kendi kapanıyor. (i) SIRA BAĞLAYICI:
`/api/isler/akis` `/api/isler/{is_id}`ten ÖNCE tanımlı — Starlette `{is_id}`i
"akis"e de eşler ve UUID doğrulaması eşleşmeden SONRA 422 verir (ölçüldü).
**Bilinen ara durum:** arena turu yenilenen sekmede panelde GRUP olarak
görünür ama döküm satırı (chat.js `pending`) gider — ürün galeride,
karşılaştırma sütunları `GET /api/arena/{id}` ile yeniden çizilebilir (bugün
çizilmiyor). Panelin model etiketi katalog (`imageModels`) geldikten sonra
doğru okunur; ilk çizimde id görünebilir, panel açılışında yeniden çizilir.

**6. göreve devredilen.** (1) "ANAHTAR YOK" ERKEN KAPISI: anahtarsız
kullanıcı bugün 202 alıp panelde `hata`lı bir iş görüyor (duman testinin
ilk turu tam bunu gösterdi: "Kimlik bilgileri eksik …") — platform anahtarı
gelince çözüm sırası (kullanıcı → platform → yok) rotada bir kez sorulur ve
"yok" 4xx döner, iş hiç doğmaz; panelin `hata` satırı o gün yalnız gerçek
sağlayıcı hatasını taşır. (2) SAATLİK İŞ TAVANI 429'unun panelde okunması:
`kromisIsler.uyar(mesaj, retryAfter)` bugün eş zamanlılık 429'unu gösteriyor;
saatlik kotanın `Retry-After`ı dakikalarla ölçülecek, aynı kapıdan geçer ama
metin "kota" demeli (yeni i18n anahtarı, `err.*` sunucudan). (3) GÜNLÜK KREDİ
TAVANI panelde: `kredi_tahmini` satırda var, panel henüz yazmıyor — kota
gelince satıra "~N kredi" ve panelin başına günlük kalan. (4) `hata` KODLARI
(`BAYAT_HATASI`, `BEKLENMEYEN_HATASI`, `KULLANICI_YOK_HATASI`) panelde ham
görünüyor; cümleyi ön yüz kurmalı (i18n eşlemesi) — 6 ya da 10. (5) SAKLAMA
(10): yeniden gönderim referans verdiği için `isler/<id>/` dizini "ona bakan
satır kaldı mı" ölçütüyle silinir; `artik_dosya.py` bunu bilmeli. (6)
Yoklamadan akışa GERİ DÖNÜŞ yok (karar (g)); vekil arkasında uzun oturumlar
ölçülürse yeniden düşünülür.

---

## 6. Platform sahipli sağlayıcı anahtarları (ortam sırrı) + kullanıcı BYOK; kota: saatlik iş, günlük kredi tavanı ✅ (PR: `faz2/platform-anahtarlari-kota`)

**Kapsam.** Çıkış kriterinin ikinci yarısı. **Anahtarlar:** işçi ve web
süreci ortamdan `KROMIS_PLATFORM_<AD>` okur — `<AD>` `depo_kimlik_bilgisi.ADLAR`ın
katalogdan türeyen kümesi (`AZURE_IMAGE_API_KEY`, `GEMINI_API_KEY`, `FAL_KEY` …
`.env.example` 2. bölüm envanteri; bekçi aynı kümeyi katalogdan kurar, elle
liste yok — CLAUDE.md § 5). Çözüm sırası **kullanıcının satırı → platform
değeri → yok**, ad ad (kullanıcı yalnız bir sağlayıcıya kendi anahtarını
girmiş olabilir). Yeri `services/kimlik.kimlik_bilgileri` (istek) ve
`services/isci.kos` (iş): `depo_kimlik_bilgisi.oku(...)`nun sözlüğü `platform_anahtari.
birlestir(kullanici_sozlugu)` ile tamamlanır — adaptörler ve `credstore`
DEĞİŞMEZ (bağlam tek sözlük görür). `GET /api/settings` her sağlayıcı için
`configured` yanına **`kaynak: "kullanici" | "platform" | null`**; anahtarın
kendisi hiçbir biçimde dönmez (Faz 1 / 7 sözleşmesi). Ayarlar paneli
(`settings.js`) "platform sağlıyor — kendi anahtarını girersen o kullanılır"
satırı; boş gönderim kullanıcının satırını siler, platforma DÜŞER (bugünkü
"boş = sil" anlamı korunur).

**Secret manager — platformun sır deposu, Vault/Doppler/KMS DEĞİL (K4).**
Yol haritası "Vault / Doppler / cloud KMS" diyor. Sahibin yığını yönetilen
platform; Fly `secrets`, Railway/Render ortam değişkenleri şifreli saklanır,
sürece ortam olarak verilir — 12-factor, ek ajan yok, ek hesap yok, ek kesinti
noktası yok. Vault/Doppler ikinci bir servis + istemci + jeton döndürme; KMS
zarf şifreleme uygulamada çözme kodu ister. Kazancı: denetim günlüğü ve
merkezi döndürme — Faz 5'in ölçeğinde değil. `KROMIS_SECRET_KEY` de aynı yerde
yaşıyor (Faz 1 / 9), tutarlı. Değişken adları `.env.example` 1. bölüme
GİRMEZ (bekçi "kodun `os.environ`dan okuduğu küme" — türetilen ad kümesi
için ayrı bir `1d` bölümü: "`KROMIS_PLATFORM_` + 2. bölümün adları", bekçi
öneki katalogla kurar).

**Kota — "sağlayıcı harcaması kullanıcı başına sınırlı" (K5).** Defter yok
(Faz 3); birim katalogun kredisi (1 kredi ≈ 0,005 USD çıpası, `catalog.py`).
İki tavan, `isler`den sayılır (`services/kota.py`, `giris_denemeleri`
deseninin ikizi — pencere, sayı, `Retry-After`):

* **Saatlik iş** — kullanıcının son 60 dk'da sıraya aldığı iş (`iptal` hariç)
  `KROMIS_SAATLIK_IS_TAVANI` (öntanımlı **60**) → 429. Herkese: BYOK'lu kullanıcı
  da işçiyi meşgul ediyor. Faz 5'in "kötüye kullanım / IP limitleri" kartının
  tohumu.
* **Günlük kredi** — kullanıcının son 24 sa'da PLATFORM anahtarıyla koşan
  işlerinin `kredi_tahmini` toplamı + yeni işin tahmini >
  `KROMIS_GUNLUK_KREDI_TAVANI` (öntanımlı **2.000** ≈ 10 USD/gün) → 429 + gövde
  kalan krediyi ve pencerenin kapanışını söyler (`err.gunluk_kredi_tavani`).
  BYOK'lu iş SAYILMAZ (kendi parası). Hangi anahtarın kullanıldığı iş satırına
  yazılır: `isler.anahtar_kaynagi text CHECK IN ('kullanici','platform')` (göç
  `0005_kota`), `kullanicilar.gunluk_kredi_tavani int NULL` (NULL = öntanımlı;
  admin 8'de ezer). Tahmin ÜST sınır (`cost_for` × n, videoda × süre); gerçek
  maliyet Faz 3'ün mutabakatı.

`chat_instructions_path` (`GET /api/settings`, `routers/ayarlar.py:53`): web'de
alan **`null`** (kabukta aynen) — persona düzenleme bir ürün özelliği, Faz 3+'a
not; alan düşürülmez, `settings.js` `null`da satırı gizler (Faz 1 / 9'un
`guncelleme: null` deseni).

**Faz 1'den devralınan.** "Platform sahipli sağlayıcı anahtarları → Faz 2
(kredi tarifesiyle birlikte anlam kazanıyor)" — tarife katalogda, tavan burada,
defter Faz 3; `.env.example`in "platform sahipli anahtar Faz 2'nin konusu"
notu; `chat_instructions_path` kararı.

**Dokunulan.** yeni `services/{platform_anahtari,kota}.py`, `services/kimlik.py`,
`services/isci.py`, `routers/{uretim,ayarlar}.py`, `services/kapilar.py`,
`services/tablolar.py` + `alembic/versions/0005_kota.py`, `credstore.py`
(`settings_status` kaynak alanı), `static/settings.js`, `bundled/i18n/*`
(+~8), `.env.example` (`1d` + 2 tavan), `compose.yaml` (yorum: platform
anahtarı yerelde `.env`den), `tests/test_platform_anahtari.py` (~12: sıra
kullanıcı → platform, ad ad karışım, bilinmeyen `KROMIS_PLATFORM_X` bildirilir
ve yok sayılır, bekçi katalog eşitliği, `GET /api/settings` kaynak + anahtar
sızmaz, boş gönderim platforma düşer, işçi platform anahtarıyla çıkıyor —
sahte istemci `Authorization` kaydeder `[platform, kullanici, platform]`),
`tests/test_kota.py` (~12: 61. iş 429, pencere kayar, günlük toplam,
BYOK sayılmaz, `Retry-After`, kullanıcı ezmesi, iptal edilen sayılmaz,
`zaman.an()` yamasıyla pencere), `tests/test_docker_kapisi.py`, `tests/test_settings_route.py`
(+kaynak), `tests/test_kimlik.py`, `docs/graflar/*`.

**Risk.** Orta-yüksek: bu görevden sonra platformun parası harcanıyor.
Küçültme: tavan öntanımlı MUHAFAZAKÂR (2.000/gün; sahibin kararı), 429
gövdesi ne zaman açılacağını söyler; `hata.log`/Sentry'de tavan aşımı
kullanıcı başına sayılır (9); platform anahtarı olmayan sağlayıcı bugünkü
gibi "yapılandırılmamış". Bilinen sınır: tahmin üst sınır, gerçek fatura
düşük kalır — Faz 3 düzeltir.

**Çıkış ölçütü.** Anahtar girmemiş kullanıcı platform anahtarıyla üretiyor
(sahibin gerçek anahtarıyla canlı, bir görsel); kendi anahtarını giren onunla
çıkıyor (sahte istemci kaydı); 2.001. kredi 429; `pg_dump`/günlük/cevapta
anahtar yok; takım yeşil.

**Yapıldığında (2026-09-18).** Yeni `services/platform_anahtari.py`:
`ADLAR = depo_kimlik_bilgisi.ADLAR − ESKI_BYOK` (katalogdan türeyen 15 ad;
bekçi kümeyi kataloğun üç alanından yeniden kurar), `platform_sozlugu(ortam)`
her çağrıda ortamı okur (süreç başına bir kez okumak testte yamalanamazdı —
`kapilar.es_zamanli_is_tavani`nın kararı), bilinmeyen `KROMIS_PLATFORM_X` bir
kez `logging.warning` (değer yok, tanınan adlar var), `birlestir(kullanici) →
(sözlük, kaynaklar)` ad ad kullanıcı → platform → yok, `Kimlikler(dict)` +
`.kaynaklar` (rota "hangi anahtarla" sorusunu buradan cevaplar; düz sözlük
gelirse her ad `kullanici` sayılır), `kaynak(cred_id, kimlikler)` anahtar
adının kaynağı — `azure_chat`/`azure_foundry` görselin anahtarına düşer
(`credstore.resolve`ın aynı düşmesi), ADRES sayılmaz. Yeri belgenin dediği
iki kapı: `kimlik.kimlik_bilgileri` (`request.state.kimlikler` artık
birleşik nesne; DB sorgusu değişmedi — test_kimlik'in "GET /api/settings 2
sorgu" ölçüsü duruyor) ve `isci.kos` (`birlestir(depo_kimlik_bilgisi.oku(…))`).
Adaptörler ve `credstore` dokunulmadı.

"ANAHTAR YOK" KAPISI `kapilar.check_anahtar(cred_id, kimlikler) → kaynak`:
`credstore.is_configured` (arayüzün "kurulu" dediğiyle rotanın kabul ettiği
ayrışmasın) → değilse **409** `err.anahtar_yok` (sağlayıcı adı + ortam
değişkeni; 502 değil — sağlayıcıya gidilmedi, 422 değil — istek biçimce
doğru). Dört üretim rotası `kimlik.KIMLIKLER`i GERİ ALDI (4. görevde çıkmıştı;
gerekçe `routers/uretim.py` başında, `KIMLIK_OKUYAN` +5) ve `POST
/api/isler/{id}/yeniden` de aynı zincirden geçer — yeniden gönderim iş
doğurur, kotanın arka kapısı olamaz; `anahtar_kaynagi` eski satırdan
KOPYALANMAZ, yeniden çözülür. Zincir `routers/uretim.py::_kapilar`: doğrulama
→ anahtar (409) → eş zamanlılık (429) → saatlik (429) → günlük (429) → girdi
nesneleri → satır. Anahtarsız istek kotaya hiç sayılmaz (iş doğmaz).

KOTA `services/kota.py` (`hesap._bekleme`nin ikizi): `saatlik_bekleme` —
`count, min(olusturuldu)` son 60 dk, `durum != 'iptal'`; `Retry-After` en eski
işin pencereden çıkışı +1 sn; gövde `err.saatlik_is_tavani` (tavan, dakika).
`gunluk_durum` — `sum(kredi_tahmini)` son 24 sa, `anahtar_kaynagi =
'platform'`, `iptal` hariç; `hata` SAYILIR (faturalanmış olabilir, K8'in
kuşkusu); toplam + tahmin > tavan → 429, gövde tavan/kalan/tahmin/pencerenin
açılış tarihi-saati (`zaman.damga`), `Retry-After` en eski sayılan işin
düşüşü; tavan `kullanicilar.gunluk_kredi_tavani` (NULL → ortam). Eşitlik
GEÇER (1.992 + 8 = 2.000 → 202; 2.001. kredi 429 — ölçüldü). Eski (kaynaksız)
satır sayılmaz. Yeni indeks yok: iki sorgu da `ix_isler_kullanici_olusturuldu`.
Göç `0005_kota`: `isler.anahtar_kaynagi text` + `ck_isler_anahtar_kaynagi_kumesi`,
`kullanicilar.gunluk_kredi_tavani int`; `alembic check` temiz, ileri-geri-ileri
yeşil; `kuyruk.ekle(…, anahtar_kaynagi=)`, `_json` +1 alan (13).

`GET/POST /api/settings`: `kaynaklar: {kimlik: "kullanici" | "platform" | null}`
`providers`ın yanında (`services/modeller.py`; anahtar yine yok — bekçi ekilen
platform anahtarını `r.text`te arar); `chat_instructions_path` VE
`chat_video_instructions_path` web'de `null` (aynı sınıf: sunucunun diski),
kabukta aynen. SAPMA — "boş gönderim siler" YAPILMADI: rotanın bugünkü kuralı
gizli alanda boş = "dokunmadım" (yalnızca-yazılır form; istemci her kutuyu
koşulsuz gönderiyor — boşu silme saymak Gemini anahtarı kaydedenin OpenAI
anahtarını silmek olurdu, `test_saglayici_anahtari_bos_gelirse_mevcut_KORUNUYOR`).
Belgenin "boş = sil" dediği şey DEPO katmanının anlamı ve o korunuyor: yeni
`SettingsRequest.anahtar_sil: list[kimlik_id]` kimliğin anahtar + adres
satırlarını boş değerle yazar (Azure'da ikisi birlikte — yalnız anahtar
silinse kullanıcının adresi platformun anahtarıyla eşleşir ve istek yanlış
hosta giderdi), kullanıcı platforma düşer; bilinmeyen id 422, aynı istekte
değer de gelmişse silme kazanır. `settings.js`: `#prov-<p>` gruplarına
dinamik "platform sağlıyor — kendi anahtarını girersen o kullanılır" notu
(kaynak `platform`) ve "kendi anahtarımı sil" düğmesi (kaynak `kullanici`;
`POST {anahtar_sil: [kimlik]}`), sağlayıcı kartı rozeti üç hâl; index.html
DEĞİŞMEDİ. `isler.js`: satırda "~N kredi" (+ "platform anahtarı" işareti),
`hata` kodları i18n cümlesine (`HATA_KODLARI` — bekçi `test_isler_route`
Python sabitleriyle harfiyen eşler); kota 429'ları core.js'in mevcut
`kromisIsler.uyar(mesaj, retryAfter)` yolundan geçer, cümle sunucudan.
"Panelin başına günlük kalan" YAPILMADI: yeni bir uç ister, 8. görevin admin
metrikleriyle birlikte düşünülür. i18n +12 (tr/en).

`.env.example`: 1. bölüm +2 (`KROMIS_SAATLIK_IS_TAVANI`, `KROMIS_GUNLUK_KREDI_TAVANI`,
öntanımlılarıyla), yeni **1d** bölümü `KROMIS_PLATFORM_` + katalog adları
(15 atama, hepsi boş; bekçi öneki katalogla kurar, ALTYAPI'nın ardından ve 2.
bölümün önünde olduğunu sınar); başlık "12-factor … KAPANDI" cümlesi KULLANICI
anahtarına daraltıldı. `compose.yaml` yorumu: platform anahtarı yerelde
`.env`den, `env_file` iki servise (`kromis`, `isci`) taşır.

TESTLER: takım 3.617 → 3.652. Yeni `tests/test_platform_anahtari.py` (13: sıra,
boş değer, `kaynak` düşmeleri, katalog eşitliği, bilinmeyen ad bir kez ve
değersiz, `GET /api/settings` kaynak + sızmaz, kendi anahtarı ezer / sil →
platforma düşer / boş kutu dokunmaz, Azure'da anahtar + adres birlikte,
bilinmeyen id 422 hiçbir şey yazmaz, sorgu sayısı büyümez, işçi
`[platform, kullanici, platform]` + DB dökümü/`hata.log`/günlük/cevap taraması,
anahtarsız 409 ve iş yok, kapı birimi), `tests/test_kota.py` (14: 61. iş 429 +
`Retry-After: 601`, 60. geçer / iptal sayılmaz, pencere `zaman.an()` ile
kayar, ortam + bozuk değer, BYOK'a da uygulanır + yalnız bu kullanıcı,
2.001. kredi 429 gövdede kalan + açılış, kalan gerçek (küçük iş sığar), BYOK /
eski satır / iptal sayılmaz ama `hata` sayılır, BYOK'lu kullanıcı hiç durmaz,
kullanıcı ezmesi, günlük pencere kayar, kapı SIRASI, multipart 429 nesne
bırakmaz, yeniden gönderim aynı kapılar). Güncellenen: `test_kimlik`
(`KIMLIK_OKUYAN` +5; anahtarsız kullanıcı 409, iş yok; `gercek_anahtar`),
`test_settings_route` (talimat yolu web'de null / kabukta dosya),
`test_isler_route` (+`anahtar_kaynagi`; panel kod eşlemesi bekçisi),
`test_kuyruk` (13 anahtar; göç literali), `test_tablolar` (CHECK), `test_db` /
`test_goc` (`BAS = "0005_kota"`, zincir), `test_docker_kapisi` (ALTYAPI +2,
1d bekçisi), `test_i18n` (kota konuşan, platform_anahtari konuşmayan).
CONFTEST: autouse `_anahtar_kapisi` `kapilar.check_anahtar`ı `"kullanici"`
döndüren bir yamayla örter — 26 test dosyasının üretim çağrıları anahtar
bilmiyor (sağlayıcı yamalı, kimlik satırı yok) ve hepsi 409 alırdı; `kullanici`
fixture'ının kimlik kapısı için yaptığının ikizi, opt-out
`@pytest.mark.gercek_anahtar` (üç dosya). Ortama sahte platform anahtarı
eklemek seçilmedi: `providers` her yerde `true` olur, "kurulu değil" ölçen
iddialar kırılırdı. ÖLÇÜLEN TUZAK: `depo_db` Alembic'i aynı süreçte koşturur
ve `alembic/env.py`nin `fileConfig`i o ana kadar yaratılmış günlükçüleri
KAPATIR (`disable_existing_loggers`) — "bir kez uyarır" testi günlükçüyü
yeniden açar; üretimde göç ayrı süreçte, sorun yok.

DUMAN (2026-09-18; geçici Postgres + `tools/goc.py` → `0005_kota` + uvicorn +
`isci.py` ayrı süreçler, sahte `KROMIS_PLATFORM_AZURE_IMAGE_API_KEY` ortamda,
sağlayıcı yamalı): anahtarsız kullanıcı `GET /api/settings` →
`providers.azure_image = true`, `kaynaklar.azure_image = "platform"`,
`chat_instructions_path = null`; `POST /api/generate` → 202 (22 ms), 202
gövdesinde `anahtar_kaynagi = "platform"`; işçi `bitti`, DB satırı `('bitti',
'platform', 4)`. Ortam silinip iki süreç yeniden açılınca aynı kullanıcı
`kaynaklar.azure_image = null`, `POST /api/generate` **409** ("Azure OpenAI ·
görsel için kayıtlı anahtar yok …"), `isler` sayısı değişmedi (1).
`KROMIS_SAATLIK_IS_TAVANI=2` ile (1 eski + 2 yeni) `[202, 429, 429]`,
`Retry-After: 3597`, gövde "Saatlik iş kotası doldu (2 iş/saat); yaklaşık 60
dk sonra yeniden dene." Ekilen anahtar iki sürecin stdout'unda (3,2 KB) ve 12
cevabın hiçbirinde yok.

**Sahibin adımı — platform anahtarını gerçek sırla canlıya almak (CI'dan
yapılamaz).** Kod sahte anahtara karşı yeşil; parayı harcayan adım sahibin:

1. **Hangi sağlayıcı fonlanacak?** Katalogun adları (bekçi aynı kümeyi
   kurar; `.env.example` 1d): `KROMIS_PLATFORM_AZURE_IMAGE_API_KEY` +
   `KROMIS_PLATFORM_AZURE_IMAGE_BASE_URL` (Azure'da ikisi birlikte; MAI/FLUX
   aynı anahtarla, `KROMIS_PLATFORM_AZURE_FOUNDRY_BASE_URL` yalnız ayrı
   kaynak/vekilse), `KROMIS_PLATFORM_AZURE_CHAT_API_KEY` /
   `_AZURE_CHAT_BASE_URL` / `_AZURE_CHAT_DEPLOYMENT` (yönetmen; boşsa
   görselin anahtarına düşer), `KROMIS_PLATFORM_OPENAI_API_KEY`
   (`_OPENAI_BASE_URL` yalnız vekil), `KROMIS_PLATFORM_GEMINI_API_KEY`
   (görsel + Veo; `_GEMINI_BASE_URL` yalnız vekil),
   `KROMIS_PLATFORM_ANTHROPIC_API_KEY` (`_ANTHROPIC_BASE_URL`),
   `KROMIS_PLATFORM_FAL_KEY` (`_FAL_BASE_URL`). Yalnız istediğin satırlar;
   boş kalan sağlayıcı yalnız BYOK ("yapılandırılmamış", bugünkü gibi).
2. **Tavanlar** (isteğe bağlı, öntanımlı 60 iş/saat ve 2.000 kredi/gün ≈ 10
   USD/gün/kullanıcı): `KROMIS_SAATLIK_IS_TAVANI`, `KROMIS_GUNLUK_KREDI_TAVANI`.
   Muhafazakâr başla; admin (8) kullanıcı başına ezecek.
3. **Sırları platforma gir** (Fly `secrets set`, Railway/Render env — şifreli
   saklanır, sürece ortam olarak gelir), HEM web HEM işçi sürecine (ikisi de
   okur; compose'ta `env_file` ikisine taşıyor). Göç dağıtım öncesi komutla
   (`python tools/goc.py` → `0005_kota`), sonra dağıt.
4. **Canlı denetim:** anahtar girmemiş bir kullanıcıyla gir → Ayarlar'da o
   sağlayıcının kartı "platform sağlıyor", alanın altında aynı not;
   `GET /api/settings` `kaynaklar.<kimlik> = "platform"` (anahtar hiçbir
   alanda yok); bir görsel üret → 202, iş paneli satırında "~N kredi ·
   platform anahtarı", iş `bitti`, `GET /api/isler/{id}` `anahtar_kaynagi =
   "platform"`; kendi anahtarını gir → sonraki iş `kullanici`; "kendi
   anahtarımı sil" → yine `platform`. Sağlayıcı panosunda faturanın platform
   anahtarına düştüğünü bir kez gör.
5. **Sonuç bu belgeye** ("Yapıldığında"nın altına bir satır: tarih, sağlayıcı,
   ilk günün kredi toplamı). Geri dönüş: sırrı silmek — anahtarsız kullanıcı
   yine 409 alır, BYOK sürer.

**7. göreve devredilen.** RLS ikinci kat (`0006_rls`): `SET LOCAL
app.kullanici_id` ile politika 8 iş tablosunda; bu görevin İKİ yeni sütunu
politika istemez ama ROL ister — `isler.anahtar_kaynagi` sahibin satırında
(kiracı süzgeci `kullanici_id`den geliyor), `kullanicilar.gunluk_kredi_tavani`
ise `kullanicilar`da: kullanıcı KENDİ tavanını okuyabilir (rota
`kullanici.gunluk_kredi_tavani` okuyor, kimlik sorgusuyla geliyor) ama
YAZAMAMALI — yazan yalnız admin rolü (8), politika `kullanicilar`ı zaten
kapsam dışında tutuyorsa sütun düzeyinde `GRANT UPDATE (gunluk_kredi_tavani)`
admin'e. İşçi rolü: `kos` kullanıcının kimliklerini `SET LOCAL`sız okuyor
(`depo_kimlik_bilgisi.oku(db, is_.kullanici_id)`) — işçi ya BYPASSRLS ya da
işin `kullanici_id`sini `SET LOCAL` ile bağlar (ikincisi doğru olan: işçi
platformun, ama her iş bir kiracının). Kota sorguları (`kota.saatlik_bekleme`,
`gunluk_durum`) `kullanici_id` süzgeçli, politika altında aynen çalışır.
Platform anahtarı DB'de değil, RLS'in konusu değil. Ayrıca 8'e: "panelin
başına günlük kalan" için `GET /api/kota` (kalan kredi, saatlik sayı,
pencerelerin açılışı) — admin metrikleriyle aynı sorgular.

**7'de yolu üstündeyken toparlanacak: `"platform"` değeri ÜÇ yerde elle
yazılı.** 6. görevden kalan bir tutarsızlık; 7 zaten `kota` sorgularına
dokunacağı için ayrı bir PR'a değmez:

| yer | bugünkü hâli |
| --- | --- |
| `services/platform_anahtari.py:62` | `KAYNAK_PLATFORM = "platform"` — sabitin kendisi |
| `services/tablolar.py:155` | `ANAHTAR_KAYNAKLARI = ("kullanici", "platform")` — CHECK'i kuran küme, sabiti İTHAL ETMİYOR |
| `services/kota.py:122` ve `:151` | `Is.anahtar_kaynagi == "platform"` / `!= "platform"` — düz dize |

Zararı bugün yok (üçü de aynı dizeyi söylüyor) ama bu deponun § 5 kuralına
aykırı: türetilebilen bir değerin tek kaynağı olur ve bekçisi bir testtir.
Somut risk, kümeye üçüncü bir kaynak eklendiğinde (belge bunu öngörüyor:
"üçüncü bir kaynak — ör. kurumsal havuz — göç ister"): CHECK ve göç
güncellenir, `kota`nın iki süzgeci sessizce eski dizede kalır ve yeni kaynakla
koşan işler günlük tavana HİÇ sayılmaz — yani kapı, tam da platform parasını
koruduğu yerde açılır. Kusur o gün sayacın eksik saymasıyla, faturadan geri
okunarak bulunur.

İstenen: `kota` iki noktada `platform_anahtari.KAYNAK_PLATFORM`u kullansın,
`tablolar.ANAHTAR_KAYNAKLARI` de kümeyi o sabitlerden kursun
(`(KAYNAK_KULLANICI, KAYNAK_PLATFORM)`) — ithal yönü zaten bu tarafa akıyor,
çevrim doğmuyor. Bekçisi, `ANAHTAR_KAYNAKLARI` ile `platform_anahtari`nin iki
sabitini karşılaştıran bir test (`tests/test_kota.py`, "kapı sırası"
testlerinin yanına); deyimin örnekleri § 5'te sayılı.

---

## 7. RLS ikinci kat — `SET LOCAL app.kullanici_id`, 8 iş tablosunda politika, FORCE; işçi ve admin rolü (PR: `faz2/rls`)

**Kapsam.** Faz 1 / 2'nin "şema RLS'e hazır, politika Faz 2/3'te" notu. Göç
`0006_rls`: 7 Faz 1 iş tablosu + `isler` için `ALTER TABLE … ENABLE ROW LEVEL
SECURITY; … FORCE ROW LEVEL SECURITY; CREATE POLICY sahip ON <tablo> USING
(kullanici_id = current_setting('app.kullanici_id', true)::uuid) WITH CHECK
(aynı)`; admin okuması için ikinci politika `USING (current_setting('app.rol',
true) = 'admin')` yalnız `SELECT` ve `UPDATE` (8. görevin tavan/iptal
yazımları). `FORCE`: yönetilen Postgres'te uygulama rolü çoğu zaman tablonun
SAHİBİ (tek rol veriyorlar) ve sahip RLS'i öntanımlı ATLAR — `FORCE`
olmadan politika hiç işlemezdi (Faz 1'in "rol modeli netleşince" sorusunun
cevabı: netleşmesini beklemeden `FORCE`). Uygulama: `services/db.oturum`
`Session` `after_begin` olayında `SET LOCAL app.kullanici_id = :id` (istek
bağlamındaki kullanıcı; kimlik çözülmeden koşan sorgular — `oturumlar ⋈
kullanicilar` — hesap tablolarında ve onlar politikasız); `SET LOCAL`
transaksiyonla biter, pooler'ın **transaksiyon modu** bunu geçirir (Supabase
Supavisor / pgbouncer transaction mode; oturum modunda da sorun yok, `LOCAL`
zaten transaksiyonda) — Faz 1'in "ölçülecek" notu burada CI'da ölçülür:
`_test.yml`e pgbouncer YOK, ama test `SET LOCAL`in transaksiyon dışına
sızmadığını doğrudan sınar. İşçi `kos`ta işin kullanıcısını, admin rotaları
`app.rol='admin'`i (`kimlik.admin_kullanici` bağımlılığı, 8) bağlar; `tools/*`
(içe aktarma, artık dosya, medya taşıma) `app.rol='admin'` ile koşar —
araçların sorguları kullanıcı süzgeci taşıyor, RLS onları da kapsar.

**Neden ikinci kat:** uygulama süzgeci bir AST bekçisiyle korunuyor
(`test_galeri_db`), ama bekçi yalnız `services/depo_*` imzalarını görür; ham
`select(Medya)` yazan bir admin rotası ya da bir araç bekçiden kaçar. RLS
sorguyu değil BAĞLANTIYI kısıtlar: süzgeç unutulursa sonuç boş, sızıntı değil.

**Faz 1'den devralınan.** "RLS ikinci katı → Faz 2", "yönetilen Postgres
pooler davranışı (RLS notu)" ölçümü, `superuser yok` gözlemi (→ FORCE).

**Dokunulan.** `alembic/versions/0006_rls.py`, `services/db.py` (`after_begin`
kancası; bağlamdaki kullanıcı `request.state.kullanici` → ContextVar
`kimlik_baglami`nın deseniyle `services/kiraci.py`: `bagla(kullanici_id |
rol)`), `services/kimlik.py`, `services/isci.py`, `tools/{ice_aktar,artik_dosya,
medya_tasi,anahtar_dondur,kullanici}.py` (rol bağlama), `tests/conftest.py`
(test kullanıcısı bağlamı; `depo_db` fixture'ı), yeni `tests/test_rls.py`
(~15: politikasız süzgeçsiz `SELECT` başkasının satırını DÖNDÜRMEZ (ikinci
bir Postgres rolüyle — CI süper kullanıcı rol yaratabilir, geçici kümede de);
`INSERT` başka `kullanici_id` ile reddedilir (`WITH CHECK`); ayar yokken 0
satır (hata değil — `current_setting(..., true)` NULL); admin rolü hepsini
okur, silmez; `SET LOCAL` transaksiyon sonunda düşer; 8 tablo + FORCE
bekçisi `pg_class.relforcerowsecurity`; downgrade politikaları kaldırır),
`docs/graflar/*`, `KURULUM.md` (uygulama rolü notu).

**Risk.** Orta. Kırılma sınıfı: (a) bağlam bağlanmadan koşan bir sorgu boş
döner → 404 yağmuru, sızıntı değil; bekçi test her kapılı rotada bağlamın
bağlı olduğunu `before_cursor_execute` ile sayar (Faz 1 / 4'ün "tek sorgu"
testinin deseni); (b) `FORCE` + göç: Alembic göçü de aynı rolle koşuyor,
`CREATE POLICY`/`ALTER TABLE` sahiplik ister — `tools/goc.py` `app.rol=
'admin'` bağlamaz, göç DDL politikaya tabi değil; (c) performans: politika
her sorguya `kullanici_id = …` ekler, indeksler zaten o sütunla başlıyor
(Faz 1 / 2), ölçüm `EXPLAIN` ile bir kez.

**Çıkış ölçütü.** Süzgeçsiz sorgu testi geçiyor; 47 kapılı rota + işçi +
5 araç bağlamla koşuyor (bekçi); `alembic` döngüsü temiz; canlı: iki hesap,
`psql`de uygulama rolüyle `SELECT count(*) FROM medya` → yalnız `SET
app.kullanici_id` sonrası satır; takım yeşil.

---

## 8. Admin: `kimlik.admin_kullanici`, `/admin` sayfası, `/api/admin/*` — kullanıcılar, kuyruk, metrikler, tavan, iptal, oturum düşürme (PR: `faz2/admin`)

**Kapsam.** `is_admin` bayrağının ilk okuyucusu. `services/kimlik.admin_kullanici`
(`aktif_kullanici` + `is_admin` değilse **403** — 404 değil: admin varlığı
gizli bilgi değil, `/admin` yolu zaten görünür) ve `admin_sayfasi` (302
`/giris`, admin değilse 403 HTML). Rotalar (`routers/admin.py`): `GET /admin`
(statik sayfa, `services/sablon.py` ile çevrili — `/giris`in yolu),
`GET /api/admin/kullanicilar` (e-posta, kayıt, son görülme, `is_admin`,
tavan, son 24 sa kredi, aktif iş; sayfalı, `?q=`), `GET /api/admin/isler`
(`?durum=`, son 200; bekleyen/çalışan/hata sayıları, en eski bekleyenin yaşı),
`GET /api/admin/metrikler` (aşağıda), `POST /api/admin/kullanicilar/{id}/tavan`
(`gunluk_kredi_tavani` yaz/sil), `POST /api/admin/kullanicilar/{id}/oturum-dusur`
(`hesap.oturumlari_dusur` — `tools/kullanici.py`nin CLI'ının rotası),
`POST /api/admin/isler/{id}/iptal` (sahip süzgeçsiz, `app.rol='admin'`).
Rota **58 → 65**. Admin yazımları `isler`e DEĞİL yeni `denetim` tablosuna da
mı? HAYIR — Faz 4'ün KVKK/GDPR kalemi denetim günlüğünü isterse gelir; bugün
admin eylemi 9. görevin yapısal günlüğüne `olay=admin.*` satırı olarak düşer.

**Metrikler — "temel metrikler" `isler`den türetilir, Prometheus YOK.**
`GET /api/admin/metrikler`: kuyruk derinliği, en eski bekleyen (sn), son 1
sa/24 sa iş sayısı ve hata oranı, model başına p50/p95 süre (`bitti - basladi`,
`percentile_cont`), son 24 sa `kredi_tahmini` toplamı (platform), `isciler`
(canlı işçi, son kalp). Yönetilen platformda kazıyıcı (scraper) yok, ikinci
bir metrik deposu kurmak Faz 5'in ölçeğinde değil; sayılar zaten DB'de.
Sayfa 30 sn'de bir yeniler.

**Ön yüz:** `static/admin.{html,js,css}` — `giris.*`nin deyimi (IIFE, kendi
stili, `flow-tokens.css`), üç sekme (kullanıcılar / kuyruk / metrikler),
i18n +~25. `settings.js` "Hakkında"da admin ise `/admin` bağlantısı.

**Faz 1'den devralınan.** "admin arayüzü / admin rotası (`is_admin` hazır) →
Faz 2+", `tools/kullanici.py oturum-dusur`un rotası.

**Dokunulan.** yeni `routers/admin.py`, `services/kimlik.py`, yeni
`services/depo_admin.py` (sorgular; `(db, ...)`, kullanıcı süzgeci YOK ve
bekçi bunu GEREKÇELİ muafiyete alır — `test_galeri_db`nin AST bekçisinde
`KIRACISIZ = {"depo_admin"}`), `services/kuyruk.py` (admin iptali),
`static/admin.*`, `static/settings.js`, `bundled/i18n/*`, `eslint.paylasilan-adlar.json`,
`app.py`, `tests/test_admin.py` (~25: admin değilse 403 her rotada, oturumsuz
401/302, liste/arama/sayfa, tavan yaz-sil ve 6'nın kotası onu okur, oturum
düşürme çerezi öldürür, admin iptali başkasının bekleyen işini iptal eder
çalışanı 409, metrik alanları ve p95 hesabı tohumla, `admin.html` çevrili,
`GET /api/hesap/ben` `is_admin` aynen), `tests/test_playwright_admin.py`
(E2E: admin girişi → üç sekme → tavan yaz), `tests/test_kimlik.py`
(`ACIK_ROTALAR` değişmez; yeni `ADMIN_ROTALAR` bekçisi: `/api/admin/*` HER
rota `admin_kullanici` taşır — listede olmayan admin rotası kırmızı, CLAUDE.md
§ 5), `tests/test_app_bolme.py`, `tests/test_id_contract.py`, `docs/graflar/*`.

**Risk.** Orta: yetki yüzeyi. Küçültme: tek bağımlılık, bekçi her `/api/admin`
rotasında; admin RLS'te yalnız okuma + iki `UPDATE`; yazımlar günlüğe.
Bilinen sınır: admin kullanıcı silemez, kredi ekleyemez (defter yok), e-posta
gönderemez — Faz 3-4.

**Çıkış ölçütü.** Admin hesabı `/admin`de kullanıcıları ve kuyruğu görüyor,
bir kullanıcının tavanını değiştiriyor ve o kullanıcının 429'u yeni tavana
göre geliyor; admin olmayan 403; takım yeşil.

---

## 9. Yapısal günlük (JSON satır, istek/iş kimliği), Sentry (isteğe bağlı), `/health` `worker_alive` (PR: `faz2/gunluk-sentry`)

**Kapsam.** `services/gunluk.py` — standart `logging` üzerine JSON biçimleyici:
`{"ts","seviye","olay","mesaj","istek_id","is_id","kullanici_id","sure_ms",
"rota","durum"}`; stdout'a (platform günlük toplayıcıları oradan okur), yerelde
`KROMIS_GUNLUK_BICIMI=metin` okunur biçim. Her satır `errlog.redact_secrets`ten
GEÇER (aynı işlev; iki redaksiyon kopyası olmaz). Ara katman `services/istek_kimligi.py`:
gelen `X-Request-ID` (platform vekilleri veriyor) ya da `uuid4`, cevaba
`X-Request-ID`, bağlama ContextVar (`dil`/`kimlik_baglami` deseni); erişim
satırı istek sonunda (yöntem, yol, durum, süre, kullanıcı) — uvicorn'un
erişim günlüğü KAPATILIR (iki satır aynı şeyi söylerdi). İşçi: `is.alindi/
basladi/bitti/hata` olayları `is_id` + `kullanici_id` + `model` + `sure_ms` ile
— "hangi iş ne kadar sürdü" sorusu `grep is_id` ile. `hata.log` KALIR
(`errlog`, dondurulmuş kabuk ve `KROMIS_DATA_DIR`de iz) — ama web'de asıl
kanal stdout.

**Sentry — `sentry-sdk`, yalnız `SENTRY_DSN` verilmişse (K10).** 2,0 MB saf
Python; `sentry_sdk.init(dsn, integrations=[FastApiIntegration(),
SqlalchemyIntegration()], send_default_pii=False, before_send=redakte)` —
`before_send` `errlog.redact_secrets`i olayın mesaj/istisna/breadcrumb
alanlarına uygular, istek gövdesi hiç gönderilmez (`request_bodies="never"`);
işçide aynı `init` + iş bağlamı `set_tag(is_id)`. DSN yoksa `init` hiç
çağrılmaz, modül ithal edilmez (tembel) — dondurulmuş kabuk ve testler
ağa çıkmaz. Sahibin işi: Sentry hesabı (ücretsiz kademe), DSN platform
sırrına. Alternatif GlitchTip (kendine barındırma — yönetilen karara ters).

**`/health` `worker_alive`.** Gövdeye `worker_alive: bool` (`isciler.son_kalp`
≤ 90 sn olan satır var mı; `motor` yoksa `null`) — **`ok`a GİRMEZ**: işçinin
düşmesi web sürecini "sağlıksız" yapıp platformun web'i yeniden başlatmasına
yol açmamalı; işçinin sağlığı işçinin kalbi, platform onu kendi yeniden
başlatır. Alan adları değişmez, 503 kuralı aynı (Faz 0 / 8 sözleşmesi:
alan eklenir, anlam değişmez).

**Faz 1'den devralınan.** "Yapısal loglama, Sentry → Faz 2"; `isletme.md`
§ 6 "uyarı eşikleri — Faz 2" (eşikler: kuyruk derinliği > 20 ya da en eski
bekleyen > 10 dk → günlüğe `uyari` olayı; Sentry'de alert kuralı sahibin
panelinde — belge yazar).

**Dokunulan.** yeni `services/{gunluk,istek_kimligi}.py`, `app.py` (ara katman
sırası: istek kimliği → köken → dil → rota; uvicorn `access_log=False`
`Dockerfile` CMD'de `--no-access-log`), `isci.py`/`services/isci.py`,
`routers/saglik.py`, `errlog.py` (yalnız yeniden kullanım), `requirements.txt`
(`sentry-sdk==2.*`; cp314 tekerleği saf Python, sorun yok), `.env.example`
(`SENTRY_DSN`, `KROMIS_GUNLUK_BICIMI`), `Dockerfile`, `tests/test_gunluk.py`
(~15: JSON satırı alanları, redaksiyon (anahtar geçmez), istek kimliği
gelen/üretilen/cevapta, erişim satırı süre ve durum, işçi olayları `is_id`,
metin biçimi), `tests/test_sentry.py` (~8: DSN yoksa modül ithal edilmez ve
ağ yok; DSN varsa `transport=` bellek taşıyıcısı — olay redakte, gövde yok,
PII kapalı; işçi etiketi), `tests/test_health.py` (+3: `worker_alive`
true/false/null, `ok` etkilenmez), `tests/test_docker_kapisi.py`, `docs/graflar/*`.

**Risk.** Düşük-orta. Kırılma sınıfı: redaksiyon kaçağı (yeni bir günlük
yolu `redact_secrets`i atlar) → bekçi test JSON satırında `sk-`/`DUMMY`
arar (Faz 1 / 7'nin `pg_dump` kuralının günlük ikizi); Sentry SDK'nın
otomatik breadcrumb'ları SQL parametresi taşıyabilir → `before_breadcrumb`
de redakte. Bağımlılık DIŞ ve isteğe bağlı.

**Çıkış ölçütü.** `uvicorn` stdout'u satır başına geçerli JSON, `X-Request-ID`
cevapta, işçi satırları `is_id` taşıyor; sahte DSN'le bellek taşıyıcısında
olay ve olayda anahtar yok; `/health` gövdesinde `worker_alive`; takım yeşil.

---

## 10. Operasyon: platformda işçi süreci, SIGTERM/`kill_timeout`, R2 kovası düzeni, iş saklama (30 gün), bayat düşürme, CI `docker` işine işçi, belgeler (PR: `faz2/operasyon`)

**Kapsam.** Kod tarafı küçük, asıl iş YAML ve belge (Faz 1 / 9'un deseni):

* **Platformda iki süreç, tek imaj.** `docs/isletme.md`ye tablo: Fly
  `fly.toml` `[processes] web = "uvicorn …", isci = "python isci.py"` +
  `[[vm]]` işçiye ayrı boyut + `kill_timeout` (Fly'da 300 sn'ye kadar
  çıkarılabilir — 6 dk'lık iş bunu da aşar, bilinen sınır); Railway/Render
  aynı imajdan ikinci servis ("background worker"), kapanış süresi platforma
  bağlı (~30 sn öntanımlı) ve ölçülüp yazılır. **Dağıtım sırasında çalışan iş
  KAYBEDİLİR** (`hata`, "isci yanit vermiyor"; K8) — kapalı betada kabul,
  Faz 5'te "dağıtım penceresi" ya da "boşalt (drain) sonra dağıt" kalemi.
  `compose.yaml` `isci` servisi `stop_grace_period: 60s`.
* **R2 kovası düzeni.** Kova özel, sürümleme AÇIK (silme/ezme kurtarılır —
  `isletme.md` § 2'nin "medya yedeği" satırı bu), yaşam döngüsü kuralı: `isler/`
  öneki 7 gün (girdi nesneleri; işçi zaten siliyor, bu emniyet), sürüm
  geçmişi 30 gün; isteğe bağlı ikinci kovaya `rclone sync` cron (sahibin
  kararı). `KURULUM.md` adım adım.
* **İş saklama ve bayat düşürme.** İşçinin ana döngüsünde 5 dk'da bir
  `kuyruk.bayatlari_dusur` (eşik `KROMIS_IS_KALP_ESIGI_SN`, 300) ve
  `kuyruk.eskileri_sil` (`bitti`/`hata`/`iptal` ve `bitti < now - 30 gün`;
  `KROMIS_IS_SAKLAMA_GUN`) — ayrı cron YOK (işçi zaten sürekli koşan tek
  süreç). `medya` satırları etkilenmez (`isler.sonuc` yalnız id listesi).
  Faz 4'ün KVKK saklama süresi kararı `istek.prompt`u da kapsar, burada not.
* **Yedek.** `isletme.md` § 2 tablosu: DB satırına `isler`, `isciler` (PITR
  aynen); medya satırı → kova (sürümleme + isteğe bağlı ikinci kova);
  `KROMIS_SECRET_KEY` aynen; **YENİ:** `KROMIS_PLATFORM_*` anahtarları ve R2
  jetonu — platform sırrında, kasada kopyası (3. yer). Geri yükleme
  tatbikatı iskeleti (§ 5) 4. adımı "kova zaten duruyor / ikinci kovadan
  `rclone`" olur.
* **CI.** `ci.yml` `docker` işi: derle → `goc.py` ×2 → **`python isci.py
  --tek-tur`** (boş kuyruk, 0) → konteyner → `/health` (`worker_alive` alanı
  var) + `/giris` + `/`; imaj boyutu yeniden okunur (`sentry-sdk` +2 MB
  beklenir, sayı buraya). `_test.yml` DEĞİŞMEZ (Redis yok, S3 sahte).
  `tests/test_docker_kapisi.py`: `isci.py` imajda, `stop_grace_period`,
  `.env.example` yeni değişkenler açıklamalı, `isletme.md` iddiaları.
* **`tools/graf_uret.py`.** `isci.py` kök bileşim kökü (`app` gibi) —
  README'nin "bileşim kökü" notu ikiye çıkar; `static/isler.js`/`admin.*`
  zaten haritada (5, 8).

**Faz 1'den devralınan.** `isletme.md` § 6'nın üç "Faz 2" satırı (R2, günlük/
Sentry/eşikler — 9'la kapanır; kredi defteri yedeği Faz 3 kalır), "imaj
boyutunun izlenmesi", "Python 3.14 tekerlekleri (CI'da görünür)" — Faz 2'nin
tek yeni ikili bağımlılığı yok (`sentry-sdk` saf), takip kapanır.

**Dokunulan.** `compose.yaml`, `.github/workflows/ci.yml`, `services/kuyruk.py`
(`eskileri_sil`), `services/isci.py` (bakım turu), `isci.py` (`--tek-tur`
zaten 3'te), `docs/isletme.md`, `KURULUM.md`, `.env.example`, `tools/graf_uret.py`
+ `docs/graflar/README.md`, `tests/test_docker_kapisi.py`, `tests/test_kuyruk.py`
(+3: saklama, bakım turu), `tests/test_paketleme_dondurma.py` (docker işi
hâlâ kesici), `tests/test_graflar.py`.

**Risk.** Düşük. CI `docker` işinde işçinin tek turu Postgres servisini
kullanır (zaten var).

**Çıkış ölçütü.** Boş Postgres + boş kova (sahte) ile `docker compose up`:
göç, web, işçi açılıyor, `/health` `worker_alive:true`; CI 5 iş yeşil;
belgelerde platform başına iki süreç tablosu; takım yeşil.

---

## Test stratejisi — kesişen kararlar (her görevin "Dokunulan"ında tek tek var)

* **Postgres gerçek, kuyruk gerçek.** `FOR UPDATE SKIP LOCKED`, kısmi indeks,
  `SET LOCAL`, RLS politikası, `percentile_cont` — hiçbiri SQLite'ta yok;
  Faz 1'in fixture zinciri (`pg_kume → pg_sablon → veritabani_url → veritabani`,
  `tests/conftest.py:439-529`) aynen, `depo_db` opt-in aynen. Eş zamanlılık
  testleri iki `Session` + iki bağlantıyla (aynı süreçte yeter: kilit
  sunucuda). Redis YOK, dolayısıyla `fakeredis` de yok (K1).
* **Sağlayıcı sahte, çağrı yeri aynı.** Testler `providers.generate`/
  `ac.generate`/`cc.complete`i yamalıyor (Faz 1 / 7'nin 104 testlik dersi);
  Faz 2 bu deyimi korur — işçi AYNI işlevleri çağırır, yama işçide de
  geçerli. Kimlik hangi anahtarla çıkmış: sahte `httpx.Client`
  `Authorization` kaydeder (`[A, B, platform]`).
* **İşçi süreç değil işlev.** `services/isci.tek_tur(db, dosya, an)`;
  conftest'e `uret_ve_bitir(client, yol, gövde) -> kayıtlar` (POST → 202 →
  `tek_tur` → `GET /api/history`) — 202'ye geçen ~15 rota test dosyasının
  eski iddiaları tek satır değişerek durur. E2E'de `ServerThread` yanında
  `tek_tur` döngüsü iş parçacığı (1 sn yoklama, test bitince durur).
* **SSE `TestClient.stream`le.** Yoklama aralığı env ile 0,05 sn'ye
  (`KROMIS_AKIS_YOKLAMA_SN`, yalnız test); ilk olay, `since`, kalp yorumu,
  10 dk kapanış (env ile 0,2 sn). E2E'de gerçek `EventSource` (Playwright
  Chromium), kapanan sekme senaryosu ÇIKIŞ KRİTERİ testi — sahte sağlayıcı
  8 sn uyur, sayfa kapanır, yeni sayfa `bitti`yi görür.
* **S3 sahte, ASGI uygulaması olarak.** `tests/sahte_s3.py`: bellek sözlüğü,
  `PUT/GET/HEAD/DELETE` + `ListObjectsV2` XML, `httpx.ASGITransport` ile
  `nesne_depo`nun istemcisine takılır; imzayı doğrulamaz, `Authorization`
  biçimini sınar. SigV4'ün doğruluğu AWS'nin yayımlı örneğiyle (sabit
  anahtar/tarih → bilinen imza) — `moto` ELENDİ (`boto3` gerektirir, K6),
  MinIO ikilisi ELENDİ (CI'a ikinci servis; Faz 1 / K4'ün "Docker'sız"
  kısıtı bu makinede aynen). Gerçek R2'ye karşı canlı doğrulama sahibin
  hesabıyla, her fazda bir kez, sonucu belgeye.
* **Zaman yamayla.** Kota pencereleri, kalp eşiği, saklama: `zaman.an()`
  parametre (`an=`) — `hesap.simdi()` deseni; uyku yok.
* **Kimlik testlerde tek noktadan** (Faz 1 / 4) aynen; RLS bağlamı aynı
  autouse fixture'tan (`kiraci.bagla(test_kullanicisi.id)`), admin testleri
  `is_admin=True` kullanıcı ister (`kullanici` fixture'ına parametre).
* **Sır sızıntısı** üç kanalda: `pg_dump` (Faz 1), JSON günlük satırı ve
  Sentry olayı (`sk-`/`DUMMY`/platform anahtarı aranır); `.gitleaks.toml`
  BÜYÜMEZ (sahte değerler `DUMMY` kuralında).
* **Elle tutulan listelerin bekçisi** (CLAUDE.md § 5): `IS_TABLOLARI` (8),
  `ADMIN_ROTALAR` (7), `KIRACISIZ` depo muafiyeti (`depo_admin`), `ALTYAPI`
  env kümesi (+~12), platform anahtar adları katalogdan, `onyuz.md` yükleme
  sırası (12 betik), `ACIK_ROTALAR` DEĞİŞMEZ.
* **`tests/test_index.py` (286)**: yalnız iki ek (panel kökü, `<script>`);
  metin çapaları dokunulmaz. Dondurulmuş kabuk testleri (~390) aynen durur.
* **Takım büyüklüğü tahmini:** 3.413 → ~3.650 (+~240), süre +25-40 sn (E2E'de
  8 sn uyku ×1, işçi iş parçacığı, SSE); ölçülür ve "Yapıldığında"ya yazılır.

---

## Sahibin karar noktaları — öneri ve gerekçe

**Sahibin kararı (2026-09-17, Slack): K1–K11 öneriler AYNEN kabul edildi.**

| # | konu | öneri | neden | alternatif ve bedeli |
| --- | --- | --- | --- | --- |
| K1 | Kuyruk arka ucu | **Postgres `FOR UPDATE SKIP LOCKED`** (`isler` tablosu), Redis/ARQ/Celery YOK; `kuyruk.py` arayüzü arka uçtan bağımsız | İş listesi/geçmiş/admin zaten kalıcı satır istiyor — Redis ikinci doğruluk kaynağı olur; hacim dakikada onlarca iş; test zemini (gerçek Postgres) hazır; Upstash komut başına ücret + bağlantı sınırı, bekleyen işçiye ters; bir servis, bir sır, bir yedek daha az | Upstash + ARQ: alım gecikmesi ~0 (bizde 1 sn), DB'de sorgu yükü yok; bedeli iki depo tutarlılığı, `redis:7` + sahte CI'da, `_test.yml`e servis, `giris_denemeleri`nin taşınması. Ölçüm gerekçe verirse `kuyruk_redis.py` aynı imzayla |
| K2 | İş durumu iletimi | **SSE** (`EventSource`, `Last-Event-ID`) + yoklama yedeği | Tek yönlü akış yeter; çerez ve köken kapısı aynen; tarayıcı yeniden bağlanmayı veriyor; vekil tamponu kalp yorumuyla | WebSocket: çift yönlü (gereksiz), köken/çerez ayrı iş, `TestClient` desteği var ama vekil ayarı ister. Salt yoklama: en basit, 3 sn gecikme + N kullanıcı × 20 istek/dk boş yük |
| K3 | Ön yüz çerçevesi (Faz 0 / 7'den açık) | **Vanilla sürer**; `isler.js` + `admin.*` `giris.js` deyimiyle; karar `onyuz-paketleme.md`ye; yeniden bakış Faz 4 | ~650 satır yeni arayüz; React/Svelte + paketleyici Docker'a Node aşaması, CI'a derleme, 286 + 14 test iddiasının yeniden tasarımı ister | Şimdi çerçeve: iş paneli/admin bileşenli yazılır, ileride fatura sayfaları hazır zemin bulur; bedeli bu fazda +1 PR (araç zinciri) ve E2E çapalarının yeniden yazımı |
| K4 | Platform anahtarlarının yeri ("secret manager") | **Platformun sır deposu** (Fly secrets / Railway-Render env), `KROMIS_PLATFORM_<AD>`; Vault/Doppler/KMS YOK | Şifreli saklanır, sürece ortam olarak gelir, ek ajan/hesap/kesinti noktası yok; `KROMIS_SECRET_KEY` zaten orada | Doppler/Vault: merkezi döndürme + denetim günlüğü; bedeli ikinci servis + istemci + jeton yönetimi. KMS zarf şifreleme: uygulamada çözme kodu. İkisi de Faz 5 ölçeğinde değil |
| K5 | Harcama sınırının birimi ve öntanımı | **Katalog kredisi**: günlük **2.000 kredi** (≈10 USD, 1 kredi ≈ 0,005 USD çıpası) platform anahtarlı işler için, saatlik **60 iş** herkese; admin kullanıcı başına ezer | Defter Faz 3'te; tarife katalogda hazır ve üst sınır verir; iki tavan iki tehdidi ayırır (para / işçi kapasitesi) | USD birimi: tarifeyi çift tutmak. Tek tavan: BYOK'lu kullanıcıyı ya boşuna sınırlar ya işçiyi korumaz. Sayıların kendisi SAHİBİN — belge öneri yazıyor, `.env` değiştirir |
| K6 | Nesne depolama istemcisi | **SigV4 elle, `httpx` ile** (~200 satır), 0 yeni bağımlılık | `boto3` zinciri 21 MB (+%7 imaj), 400 servis modeli; `minio` `pycryptodome`+`urllib3` (ikinci HTTP yığını); ikisi de testte ya `moto`/gerçek uç ya kendi yaması. Elle imza deponun `MockTransport` deyimine oturur, AWS'nin yayımlı örneğiyle sınanır | `boto3`: en yaygın, çok parçalı yükleme hazır; bedeli boyut + `moto`. `minio`: küçük; bedeli ikinci HTTP/kripto yığını. R2 tek sağlayıcı olduğu sürece 200 satır yeter; çok parçalı yükleme gerekmedi (tek gövde ≤ 5 GB) |
| K7 | Medyanın servis yolu | **302 → 15 dk ön imzalı URL** (`/output`, `/assets`, indirme); ZIP uygulamadan akar | Uygulama bayt taşımaz, R2'nin sıfır çıkış ücreti ancak böyle gerçek olur; `<video>` aralık istekleri doğrudan R2'ye; sahiplik DB'de denetlenir | Vekil akış: URL sabit, önbellek kolay; bedeli her medya baytı uygulama sürecinden (ve platformun çıkış ücretinden) geçer — spec §1.3'ün seçtiği R2'nin sebebini yok eder |
| K8 | Düşen işçi / yarım iş | **Otomatik yeniden deneme YOK**: kalp 5 dk susarsa iş `hata` ("isci yanit vermiyor"), kullanıcı panelden yeniden gönderir; dağıtım sırasında çalışan iş kaybedilir (bilinen) | Sağlayıcı çağrısı faturalanır; çağrının gidip gitmediği bilinemez → yeniden deneme çift fatura riski | Bir kez yeniden dene: kayıp iş azalır, çift fatura ihtimali doğar; sağlayıcı idempotency anahtarı vermiyor. Faz 5'te "boşalt sonra dağıt" |
| K9 | RLS rol modeli | **`FORCE ROW LEVEL SECURITY`** + `SET LOCAL app.kullanici_id`/`app.rol` her transaksiyonda; uygulama rolü tablo sahibi olsa da politika işler | Yönetilen Postgres tek rol veriyor, sahip RLS'i atlar; `SET LOCAL` pooler'ın transaksiyon modunu geçer | Ayrı uygulama rolü (sahip değil): `FORCE` gerekmez ama iki rol + `GRANT` yönetimi + platformda ikinci kullanıcı açma (her yerde mümkün değil) |
| K10 | Hata izleme | **Sentry SaaS**, `sentry-sdk` (2 MB), yalnız `SENTRY_DSN` verilmişse; `before_send` redaksiyon, PII/gövde kapalı; DSN + hesap SAHİBİN | Yönetilen karara uygun, ücretsiz kademe kapalı betaya yeter, FastAPI/SQLAlchemy entegrasyonu hazır | GlitchTip (kendine barındırma) yönetilen karara ters; yalnız günlük: iz var ama gruplama/uyarı yok |
| K11 | Uygulama platformu (Faz 1 / K6 açık bırakmıştı; işçi seçimi zorluyor) | **Fly.io**: tek imajdan `[processes]` web + isci, `release_command` (`tools/goc.py`), `kill_timeout` 300 sn'ye kadar, bölge seçimi (küresel kitle) | İki süreç tek yapılandırma dosyasında; uzun işe en çok kapanış süresi; Faz 1'in göç deseni birebir oturuyor | Railway/Render: panelden ikinci servis, aynı imaj; kapanış ~30 sn (6 dk'lık iş dağıtımda kesin kaybolur); pre-deploy komutu var. Sahibin hesabı/tercihi belirler; belge üçünü de yazar |

**Barındırma kararı (2026-09-17).** Sahip, Faz 2–4 boyunca YÖNETİLEN
platformda kalmayı kabul etti: Fly.io (K11'in önerisi — tek imajdan web +
işçi süreçleri, `release_command`, uzun işe yeten `kill_timeout`), yanında
Neon Postgres, Cloudflare R2 ve Sentry'nin ücretsiz kademeleri. NEDEN: bu
fazların işi ürünün kendisi (kuyruk, işçi, anahtarlar, ödeme); bir VPS'in
işletme yükü — yama, yedek, TLS, ikinci süreç için süpervizör, disk dolması
— aynı kişinin aynı saatlerinden gider ve bugün ölçülebilir bir kazancı yok:
ödeyen kullanıcı yokken sabit maliyet zaten sıfıra yakın, ölçek yok. Ücretsiz
kademelerin sınırları (Neon'un uyuyan hesaplama, R2'nin 10 GB'ı, Sentry'nin
olay kotası) kapalı betaya yeter ve aşıldığında sayı görünür. **"Hetzner VPS +
Coolify" Faz 5'in maliyet kararı olarak kayda geçti:** ödeyen kullanıcı olunca
aylık platform faturası ile bir VPS'in fiyatı + işletme saati yan yana
konulur; o gün taşınmayı kolaylaştıran şey bu fazın kararları — imaj tek,
göç dağıtım öncesi komutta, medya nesne depolamada, sırlar ortamda — yani
platforma özgü hiçbir şey kodda yok.

---

## Üst belgeden (spec §1-§3, §5) ve yol haritası kartından sapmalar — gerekçeli

* **Redis + Celery/ARQ → Postgres kuyruğu, kendi işçi döngüsü** (K1). Spec §2
  şeması "Redis In-Memory Data Store → Background Worker Cluster (Celery /
  ARQ)"; kart "Redis + worker (ARQ / Celery / Dramatiq)". Ölçülen hacimde ve
  sahibin yönetilen yığınında Redis ikinci doğruluk kaynağı ve ikinci servis;
  `isler` tablosu zaten şart. Karar geri alınabilir: arayüz sabit.
* **Secret manager (Vault/Doppler/KMS) → platform sırrı** (K4). Kartın
  "secret manager"ı sahibin yığınında platformun kendisi.
* **"Redis-tabanlı rate limiting" → Postgres sayaçları** (K1, 6). Hedef
  (kullanıcı başına eş zamanlılık ve hız sınırı) aynen; araç `isler`.
* **Traefik/Nginx + Gunicorn/Uvicorn cluster (spec §2) → platformun TLS'i
  ve tek uvicorn/replika.** Faz 0 / 8 ve Faz 1 / 9'un yönetilen barındırma
  kararının devamı; spec §1 tablosu tarihsel kayıt.
* **"Temel metrikler" → `isler`den türetilen admin ucu**, Prometheus/OTel
  YOK (8). Kazıyıcı yok, sayılar DB'de.
* **R2 Faz 1 → Faz 2, ve Faz 2 İÇİNDE işçiden ÖNCE** (giriş, K5'in tersine
  dönüşü): işçi ve web ayrı makinelerde, ortak zemin nesne depolama.
* **"6 dakikalık video işi" testte 8 saniyelik sahte iş.** Kriter SÜREÇ
  (sekme kapalıyken tamamlanma), süre değil; gerçek süre canlı doğrulamada
  bir kez, CI'da her koşuda değil.
* **JWT → oturum** (Faz 1 / K3) ve **user/organization/membership → yalnız
  `kullanicilar`** sapmaları aynen sürüyor; işçi kullanıcıyı `isler.kullanici_id`
  ile bilir, jetona ihtiyacı yok.

---

## Faz 2 dışı, ama burada not edilen

* **Kredi defteri (çift kayıt), rezerve → onayla / iade, aylık hibe, paketler,
  `model_available(plan)`** (`services/modeller.py:22`, `catalog.py:202`) →
  **Faz 3**. Faz 2'nin `isler.kredi_tahmini` + `anahtar_kaynagi` sütunları ve
  günlük tavan defterin ilk müşterisi: defter geldiğinde "rezerve" tavan
  denetiminin yerine, "onayla" `bitir`in içine oturur.
* **Filigran (ücretsiz katman), tarife-maliyet mutabakatı ve marj raporu** →
  Faz 3. `isler.bitti - basladi` ve model sütunu raporun ham verisi.
* **Stripe, webhook, abonelik yaşam döngüsü, vergi, e-Arşiv** → **Faz 4**;
  kart açıkça orada, sahibin "Stripe önce" kararı sırayı değiştirmiyor.
* **KVKK/GDPR: gizlilik metni, rıza, hesap silme, veri dışa aktarma, saklama
  süreleri** → Faz 4. `isler.istek.prompt` ve `kullanicilar.silindi_at` yer
  tutucular; iş saklama 30 gün (10) o kararın öncülü, kesin süre orada.
* **Kötüye kullanım / IP limitleri, içerik politikası** → Faz 5; saatlik iş
  tavanı (6) tohumu. **Yedekleme ve geri yükleme tatbikatı** → Faz 5
  (`isletme.md` § 5 iskeleti Faz 2'de kova adımıyla güncellenir, koşulmaz).
* **Dağıtım sırasında çalışan işin kaybı** (K8) → Faz 5 "boşalt sonra dağıt"
  ya da dağıtım penceresi. **Sağlayıcı idempotency anahtarı** yok.
* **`LISTEN/NOTIFY` ile anlık alım** ve **Redis'e geçiş** → yalnız ölçüm
  isterse; 1 sn yoklama dakikalık işte görünmez.
* **İş bitiminde e-posta bildirimi** ("sekme kapansa da" tamamlanan işi
  haber vermek): `services/posta.py` hazır, ürün kararı yok → Faz 3+ adayı.
* **Persona / `chat-instructions.md` düzenleme** (Faz 1 notu): web'de alan
  `null` (6), özellik Faz 3+; `director_guidance` tercihi bugünkü karşılığı.
* **`/api/chat` kuyruğa GİRMEZ**: sohbet çağrısı saniyeler, senkron kalır;
  kullanıcı BYOK → platform anahtarı çözümü (6) ona da uygulanır.
* **Google ile giriş (3b)** hâlâ isteğe bağlı, Faz 1'in notu aynen.
* **Çok parçalı (multipart) S3 yüklemesi, CDN özel alan adı, görsel dönüşüm** —
  gerekmedi/ürün kararı yok.
* **Dondurulmuş kabuk testleri** (~390) silinmez; `YerelDepo` kabuğun yolu.
* **Ölçülmeyen:** gerçek R2'de 302 + `<video>` aralık davranışı (canlı
  doğrulamada), Fly/Railway/Render kapanış süreleri (10'da yazılır), takım
  süresi artışı, işçi başına makul eş zamanlılık (4 varsayım; sağlayıcı
  gecikmesiyle ölçülür), `botocore`suz SigV4'ün R2'nin `auto` bölgesiyle
  imza uyumu (bilinen: R2 `us-east-1`/`auto` kabul ediyor — canlı doğrulamada
  kesinleşir).
