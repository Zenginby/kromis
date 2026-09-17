# Faz 1 — veri tabanı ve hesaplar: görev listesi

**Tarih:** 2026-09-17 · **Karar:** çok kullanıcılı web (Alperen Zengin, Slack, 2026-09-16: küresel kitle · modele göre kredi, abonelik paketiyle satılır, Stripe önce · yönetilen barındırma · web-first) · **Önceki faz:** [faz0-web-first.md](faz0-web-first.md) (8/8 ✅)
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md) — sapmalar bu belgenin sonunda tek tek yazılı.

Faz 1'in amacı, Faz 0'ın kurduğu zeminin (router'lar, ayar nesnesi, istek
başına dil, konteyner) üstüne **hesabı ve veri tabanını** koymak: iki farklı
kullanıcı aynı sunucuda birbirinin verisini göremiyor, E2E takımı bunu
sınıyor. Kredi, kuyruk, ödeme ve nesne depolama BU FAZDA YOK (gerekçeler
"Faz 1 dışı" bölümünde). Her madde bir PR (`faz1/<slug>` dalı), her PR tek
başına yeşil ve geri alınabilir; her PR'da testler + `docs/graflar` aynı
commit'te. Sıra bağımlılığa göre: **1 → 2 → 3 → 4**, sonra **5 ve 6** (4'e
dayanır, birbirinden bağımsız), **7** (4'e dayanır), **8** (5-7 bittiğinde),
**9** her an başlayıp 8 ile biter.

Ölçüler bu belge yazılırken alındı (`f178ce9`, Faz 0 tamamı main'de):

* **46 rota / 8 router** (`docs/graflar/uc-noktalar.md`). Depolara göre
  sınıflandırıldı (`graf.json` → `uc_noktalar[].moduller`): **42 rota**
  kullanıcı verisine dokunuyor (`storage`, `folders`, `chat_store`,
  `palette_store`, `assets_store`, `prefs`), **1** yalnız kimlik dosyasına
  (`POST /api/settings`), **3** hiçbirine (`GET /`, `GET /health`,
  `POST /api/palette/suggest`). Rotaların **41'i senkron `def`**, 5'i
  `async def` (`routers/uretim.py` 3, `galeri` 1, `bindirme` 1) — yani
  Starlette threadpool'unda koşuyorlar; bu sayı 1. görevin sürücü kararını
  belirliyor.
* **8 JSON dosya türü** tek `output_dir`/`assets_dir` altında (aşağıdaki
  envanter), 5'i `jsonstore.write_atomic` (`jsonstore.py:68`) ile yazılan
  LİSTE, 1'i NESNE (`prefs.json`), 1'i önbellek (`guncelleme.json`), artı
  `~/.config/kromis/credentials.env` (`paths.py:200`, 15 ad) ve iki isteğe
  bağlı talimat ezmesi (`paths.py:177`).
* `Depends(ayar.ayarlar)` **44** yerde (`routers/*.py`); ayar nesnesi
  `services/ayar.py:83`teki tek işlevden okunuyor — Faz 0 bu kapıyı Faz 1
  için bıraktı.
* Takım **3.000 geçti, 12 atlandı, 106 sn** (E2E dâhil, `KROMIS_E2E_ZORUNLU=1`);
  99 test dosyası, 2.098 `def test_`. **37** test dosyası `TestClient`
  kuruyor (178 çağrı), **47** dosya bir depo modülünü ithal ediyor, **24**
  dosya `credentials.env`/`env_path`e dokunuyor; Playwright **4 dosya / 19
  test**, sunucu aynı süreçte (`tests/test_playwright_studio.py:133`
  `ServerThread`). Rota sayısı `tests/test_app_bolme.py:124`te **46** diye
  mandallı.
* Bu makinede ölçülen ortam kısıtları: Docker imajı ÇEKİLEMİYOR (vekil
  `production.cloudfront.docker.com`u 403'lüyor — `docker pull postgres:17-alpine`
  "Forbidden"), ama **PostgreSQL 16.13 sunucu ikilileri kurulu**
  (`/usr/lib/postgresql/16/bin/{initdb,pg_ctl,postgres}`); süreç root ve
  `initdb` root'u reddediyor, yardımcı bir kullanıcıyla (`useradd` + `su`)
  geçici küme **açıldı ve cevap verdi** (`select version()` → 16.13). 4.
  görevin test kararı bu ölçüme dayanıyor.
* Kütüphane sürümleri PyPI'dan bugün (`pip download`, cp313 tekerleği var):
  SQLAlchemy 2.0.54, Alembic 1.20.0, psycopg 3.3.5 (+`psycopg-binary`),
  asyncpg 0.31.0, pwdlib 0.3.1 / argon2-cffi 25.1.0, cryptography 50.0.1,
  aiosqlite 0.22.1, testcontainers 4.15.0, pytest-postgresql 9.1.0,
  slowapi 0.1.10, itsdangerous 2.2.0. CI Python **3.14**
  (`_test.yml:41`, `ci.yml:120`), imaj 3.13-slim — cp314 tekerleği her
  ikili bağımlılık için CI'da doğrulanmalı (5. görevin Faz 0'daki
  yükseltme deneyimi: kırılma test tarafında görünür).

---

## Envanter: bugünkü JSON depoları → tablolar

Tablo adları ÖNERİ (deponun yeni kod geleneği Türkçe: `services/{ayar,dil,kimlik}`);
alan listeleri KAYNAKTAN (`create`/`save` gövdeleri). `kullanici_id` her iş
satırında sahiplik sütunu; `(kullanici_id, id)` yerine `id` TEK BAŞINA birincil
anahtar — gerekçe 2. görevde.

| dosya | yazan | kayıt alanları | okuyan rotalar | tablo (öneri) |
| --- | --- | --- | --- | --- |
| `output/history.json` (liste) | `storage.save` `storage.py:148` | 12 koşulsuz: `id` (`uuid4().hex[:12]`, `:150`), `filename`, `prompt`, `size`, `quality`, `created_at`, `parent_id`, `folder_id`, `palette` (nesne), `prompt_sent`, `model`, `credits`; 5 koşullu: `imported`, `session_id`, `arena_id`, `kind`, `duration` | 19 (`galeri` 14, `uretim` 4, `bindirme` 2 — `/output/{filename}` dâhil) | `medya` |
| `output/folders.json` | `folders.create` `folders.py:96` | `id`, `name`, `parent_id`, `created_at` (5 derinlik, `depth`) | 12 | `klasorler` |
| `output/chats.json` | `chat_store.create` `chat_store.py:144` | `id`, `title`, `messages` (rol/`content` ya da `result`+`image_ids`), `created_at`, `updated_at`; `cover` türetilir | 10 (`sohbet` 6, `uretim` 4 oturum etiketi) | `sohbetler` (`mesajlar` JSONB) |
| `output/palettes.json` | `palette_store.create` `palette_store.py:58` | `id`, `name`, `seed`, `mode`, `strength`, `colors` (dondurulmuş liste), `created_at` | 5 | `paletler` |
| `assets/{logos,banners,mottos}/index.json` ×3 (`assets_store.py:23`) | `assets_store.save_asset` `:86` | `id`, `filename`, `name`, `kind`, `created_at` | 9 | `varliklar` (`tur` sütunu) |
| `output/prefs.json` (NESNE) | `prefs.update` `prefs.py:226`; şema `prefs.py:66` | 9 anahtar: `autosave_sessions`, `theme`, `language`, `guncelleme_kontrolu`, `image_model`, `video_model`, `chat_provider`, `chat_model`, `director_guidance` | 9 (`ayarlar` 4, `sohbet` 4, `settings` 1) | `tercihler` (kullanıcı başına 1 satır, tipli sütunlar) |
| `~/.config/kromis/credentials.env` | `azure_client.save_env` `azure_client.py:276`; okuyan `read_env_values` `:220`, `credstore.resolve` `credstore.py:77` | 15 ad (`catalog.CREDENTIALS` 7 sağlayıcı × key/url + `AZURE_CHAT_DEPLOYMENT`; `.env.example` 2. bölüm) | `POST/GET /api/settings`, `POST /api/chat`, 4 üretim rotası (`credstore` üzerinden) | `saglayici_kimlikleri` (şifreli, 7. görev) |
| `output/guncelleme.json` | `guncelleme.py:76` (GitHub Releases önbelleği) | süreç geneli, kullanıcı verisi DEĞİL | 3 | tablo YOK — diskte kalır (bkz. "Faz 1 dışı") |
| `data_dir/.last-version` + `yedek/` | `backup.py:133` (manifest bayt kopyası) | — | `_lifespan` `app.py:79` | 6. görevde web yolundan çıkar |

Hepsinde kimlik `uuid4().hex[:12]` ve kapı `_SAFE_ID = [0-9a-f]{8,32}`
(`storage.py:94`, beş depoda kopya) — yani **32 haneli tam `uuid4().hex` de
geçerli bir kimlik**: yeni satırlar tam uuid alabilir, içe aktarılan eski
kayıtlar 12 haneli kimliklerini KORUR, ön yüz ve `/output/{filename}` yolu
değişmez. Bu gözlem 2. ve 8. görevin göç tasarımını belirliyor.

---

## 1. Veri tabanı zemini — SQLAlchemy 2 + Alembic + PostgreSQL, testte GERÇEK Postgres (PR: `faz1/veritabani-zemini`)

**Kapsam.** `requirements.txt`e `SQLAlchemy==2.0.*`, `alembic==1.20.*`,
`psycopg[binary]==3.3.*`. Yeni `services/db.py`: `DATABASE_URL`den
(`postgresql+psycopg://…`) TEK bir `Engine` (`pool_size` küçük — yönetilen
Postgres'lerin havuzu sınırlı, Neon/Supabase kendi pooler'ını koyuyor),
`Depends(db.oturum)` ile istek başına `Session` (commit rota gövdesinde
DEĞİL bağımlılıkta: başarıyla dönen istek commit, istisna rollback — tek
kural, 46 rotaya tek tek yazılmaz). Motor LİFESPAN'da kurulur, ithal anında
DEĞİL: `import app` bugün diske bile dokunmuyor (`services/ayar.py`, "ithal
anında bağlanmaz") ve `test_index` gibi 286 testin `TestClient(app)`i DB'siz
açılabilmeli. `Ayarlar`a (`services/ayar.py:56`) alan EKLENMEZ — o nesne
dizinlerin nesnesi; bağlantı dizesi `os.environ` → `db.py` sabiti (`paths.DATA_DIR_ENV`
deyimi). Kök dizinde `alembic.ini` + `alembic/` (`env.py` URL'yi aynı
kaynaktan okur; `alembic/versions/*.py` telif başlığı kapsamına GİRER —
`tests/test_telif_basligi.py`nin listesi bugün kök, `routers/`, `services/`,
`tools/`; yeni dizin ya listeye ya gerekçeli muafiyete, CLAUDE.md §5).
`compose.yaml`a `postgres:17` servisi (yalnız geliştirme; `.env.example`e
`DATABASE_URL`). `GET /health` (`routers/saglik.py:85`) ikinci ölçüt alır:
`db_reachable` (`SELECT 1`, 1 sn zaman aşımı), `ok` ikisinin VE'si, 503 kuralı
aynı — Faz 0 / 8'in "alan adları değişmez" notu.

**Sürücü kararı — senkron `Session` + psycopg 3, `asyncpg` DEĞİL.** Ölçüldü:
46 rotanın 41'i senkron `def`; hepsi zaten Starlette threadpool'unda. Async
motor (`create_async_engine` + asyncpg) o 41 rotanın `async def`e
çevrilmesini ya da her DB çağrısının `run_in_threadpool` ile sarılmasını
isterdi — kazancı yok, çünkü ağır iş (Pillow yeniden kodlama, 1-6 dk
sağlayıcı çağrısı) zaten senkron ve Faz 2'de kuyruğa çıkacak. psycopg 3 tek
sürücüyle iki yolu da açık tutuyor (`postgresql+psycopg` hem `Engine` hem
`AsyncEngine`); asyncpg yalnız async. 5 `async def` rota (dosya yükleyenler)
DB'ye `run_in_threadpool` ile gider — bu PR'da değil, 5. görevde.

**Test kararı — GERÇEK Postgres, SQLite DEĞİL; Docker'sız.** SQLite'ın
gizleyeceği şeyler tam olarak bu fazın kullandıkları: JSONB (`mesajlar`,
`palette`), `citext`/benzersiz e-posta, `timestamptz`, `ON CONFLICT`,
eş zamanlı yazarlarda kilit davranışı (jsonstore'un `RLock`unun yerine
gelen şey). Faz 0'ın ölçülmüş dersi (CLAUDE.md §3: 9 kırmızının 8'i
atlanan E2E'de) burada birebir: SQLite'ta yeşil, Postgres'te kırmızı bir
göç dosyası CI'da görünür, yerelde görünmez. Yol: `tests/conftest.py`
`veritabani` fixture'ı (oturum kapsamı) — `KROMIS_TEST_DATABASE_URL`
verilmişse onu kullanır (CI: `_test.yml`e `services: postgres:17` +
`KROMIS_E2E_ZORUNLU`nun yanına), verilmemişse `tools/test_ortami.py`
makinedeki ikililerle (`pg_config --bindir`, yoksa `apt`/`brew` yönergesi)
geçici bir küme açar: `initdb` → `pg_ctl start` unix soketiyle (port yok,
paralel takımlar çakışmaz) → test başına `CREATE DATABASE` şablondan (her
test dosyasına temiz DB; `TRUNCATE` DEĞİL — Alembic göçü şablona bir kez
uygulanır). Root'ta koşan takım (Claude Code konteyneri, ölçüldü) için
`test_ortami.py` yardımcı kullanıcı açar ve `su` ile koşturur — ölçüldü,
çalışıyor. Postgres HİÇ yoksa DB'ye dokunan testler `pytest.skip` ile
düşer ve `pytest_terminal_summary` E2E ile aynı gürültüyü basar; `KROMIS_E2E_ZORUNLU=1`
atlamayı HATAYA çevirir (değişkenin adı kalır, anlamı "tam takım zorunlu"ya
genişler — `tests/conftest.py:60`). `testcontainers` ELENDİ: bu makinede
imaj çekilemiyor ve CI'da servis konteyneri zaten var. `pytest-postgresql`
(9.1.0) ELENDİ: `pg_ctl`i mevcut kullanıcıyla çağırıyor, root'ta düşer;
kendi fixture'ımız 60 satır. `aiosqlite` GİRMEZ.

**Dokunulan.** `requirements.txt`, `requirements-dev.txt` (hayır — sürücü
çalışma zamanı), yeni `services/db.py`, `alembic.ini`, `alembic/env.py`,
`alembic/versions/` (boş ilk göç: yalnız `alembic_version`), `routers/saglik.py`,
`compose.yaml`, `.env.example`, `Dockerfile` (yalnız `libpq` gerekmiyor —
`psycopg-binary` kendi libpq'sunu taşıyor; ölçülecek), `tools/test_ortami.py`,
`tests/conftest.py`, yeni `tests/test_db.py` (motor lifespan'da kuruluyor,
ithal anında bağlantı yok, `SELECT 1`, `/health` 503'ü DB yokken),
`tests/test_health.py` (8 → +3), `tests/test_docker_kapisi.py` (`.env.example`
yeni değişken açıklamalı), `tests/test_bagimlilik_pinleri.py` (biçim),
`tests/test_test_ortami.py` (yeni kurulum adımı `_test.yml` ile aynı),
`tests/test_i18n.py::test_every_shipped_module_is_classified` (yeni modüller),
`docs/graflar/*`.

**Risk.** Orta. Kırılma sınıfı: (a) `import app` bir yerden DB'ye dokunur ve
286 `test_index` + 37 `TestClient` dosyası Postgres'siz düşer — bekçi
`tests/test_db.py` ("ithal bağlantı açmaz"); (b) `test_ortami.py`nin küme
açma yolu platforma göre kırılgan (macOS'ta `brew` yolu, Windows'ta yok —
Windows'ta `KROMIS_TEST_DATABASE_URL` zorunlu, belgeye yazılır); (c) CI'da
Python 3.14 için `psycopg-binary` tekerleği.

**Çıkış ölçütü.** `DATABASE_URL` verilmiş uygulama açılıyor, `/health`
`{"ok":true,…,"db_reachable":true}`; DB kapalıyken 503; `alembic upgrade head`
boş DB'de geçiyor; CI'da Postgres servisi ayakta ve takım onu kullanıyor
(atlanan DB testi 0); yerelde `tools/test_ortami.py --kontrol` "Postgres:
hazır" diyor; takım yeşil.

---

## 2. Veri modeli ve ilk göç — kullanıcı, oturum, 7 iş tablosu (PR: `faz1/veri-modeli`)

**Kapsam.** `services/tablolar.py` (SQLAlchemy 2 `DeclarativeBase`, `Mapped[]`
tip notları — mypy kapısı açık, `tests/test_mypy_kapisi.py`) ve ilk gerçek
Alembic göçü. Tablolar:

* `kullanicilar` — `id uuid`, `eposta citext UNIQUE`, `parola_ozeti text`
  (argon2id, 3. görev), `dogrulandi_at timestamptz NULL`, `is_admin bool`
  (8. görev), `dil text` (dil zincirinin 3. halkası, 4. görev), `olusturuldu`,
  `guncellendi`, `silindi_at NULL` (yumuşak silme — Faz 4'ün hesap silme
  akışı için yer; bugün okunmaz).
* `oturumlar` — `id uuid`, `kullanici_id`, `jeton_ozeti bytea UNIQUE`
  (SHA-256; ham jeton yalnız çerezde), `olusturuldu`, `son_gorulme`,
  `bitis`, `ip inet`, `istemci text`.
* `jetonlar` — e-posta doğrulama ve parola sıfırlama; `amac` enum, `ozet`,
  `bitis`, `kullanildi_at` (tek kullanım). DB'de duruyor ki iptal edilebilsin;
  `itsdangerous` imzalı jeton bu yüzden GEREKMİYOR.
* `giris_denemeleri` — `(eposta, ip, zaman)`; 3. görevin hız sınırı Redis'siz
  buradan sayar (Faz 2'de Redis gelirse taşınır).
* İş tabloları, envanterden birebir: `medya`, `klasorler`, `sohbetler`,
  `paletler`, `varliklar`, `tercihler`, `saglayici_kimlikleri` — hepsinde
  `kullanici_id uuid NOT NULL REFERENCES kullanicilar ON DELETE CASCADE` +
  `(kullanici_id, olusturuldu)` indeksi (`list_history`in ters kronolojik
  listesi, `storage.py:254`). `medya.palette`, `sohbetler.mesajlar` JSONB;
  `medya`nın 5 koşullu alanı NULL'lanabilir sütun (JSON'daki "yokluğun
  anlamı var" disiplini SQL'de NULL'un kendisi); `credits int NOT NULL` ve
  `model text NOT NULL` koşulsuz kalır (storage.py'nin gerekçesi aynen
  geçerli: ledger'ın tek müşterisi). `tercihler` tipli 9 sütun + `CHECK`
  (`theme`/`language` enum'ları `models.ALLOWED_*`tan — prefs `_ENUMS`in
  SQL karşılığı), JSONB DEĞİL: yazma yolu katı, okuma hoşgörülü ilkesi
  (`prefs.py` başlığı) sütun düzeyinde daha ucuz.

**Kimlik kararı.** `medya`/`klasorler`/`sohbetler`/`paletler`/`varliklar`
birincil anahtarı `id text` (`CHECK (id ~ '^[0-9a-f]{8,32}$')` — `_SAFE_ID`in
SQL'i), yeni satırlar `uuid4().hex` (32), içe aktarılanlar bugünkü 12 hane.
Küresel benzersiz, `(kullanici_id, id)` DEĞİL: `/output/{filename}` ve
`/api/image/{id}` yolları yalnız id taşıyor ve sorgu `WHERE id = :id AND
kullanici_id = :ben` zaten sahibi kontrol ediyor; iki kullanıcının aynı 12
haneli id'ye sahip eski kaydı içe aktarılırsa çakışma 8. görevde yeniden
adlandırılır (ihtimal 2⁻⁴⁸/çift, ama sıfır değil ve göç aracı yazıyorsa
bilmeli).

**Çok kiracılılık modeli — tek DB, satır düzeyi `kullanici_id`.** Şema başına
kiracı ELENDİ: N kullanıcı × 11 tablo göç fan-out'u, yönetilen Postgres'in
bağlantı/şema sınırları, ve Faz 3'ün defter/marj raporlarının kullanıcılar
ARASI toplam istemesi. Spec'in RLS'i (§3) bu şemayla UYUMLU ama bu fazda
UYGULAMA düzeyinde: her depo işlevi `kullanici_id`yi imzasında zorunlu alır
(`medya.listele(oturum, kullanici_id)` — `output_dir` parametresinin
yerine geçen şey), bekçi test her iş tablosunun sorgusunda süzgeç arar.
Postgres RLS (`SET LOCAL app.kullanici_id` + politika) Faz 2/3'te ikinci
kat olarak eklenir; şema değişmez.

**Dokunulan.** yeni `services/tablolar.py`, `alembic/versions/0001_*.py`,
yeni `tests/test_tablolar.py` (göç ileri-geri-ileri; `alembic check` —
autogenerate farkı BOŞ, yani model ile göç ayrışmamış; her iş tablosunda
`kullanici_id` + FK + indeks; `CHECK` kısıtları gerçekten reddediyor),
`docs/graflar/*`. Rota YOK, davranış değişikliği YOK.

**Risk.** Düşük-orta. Tek geri dönüşsüz şey adlar: tablo/sütun adı sonradan
değişmez (`GUNCELLEME.md`de göç kaydı gerektirir). Türkçe ad + ASCII
(`kullanicilar`, `saglayici_kimlikleri`) — SQL'de ı/ş/ğ tırnak ister ve her
araçta sorun çıkarır.

**Çıkış ölçütü.** `alembic upgrade head && alembic downgrade base && alembic
upgrade head` temiz; `alembic check` "no new upgrade operations"; 11 tablo;
takım yeşil.

---

## 3. Hesap: kayıt, giriş, e-posta doğrulama, parola sıfırlama, oturum çerezi (PR: `faz1/hesap`)

**Kapsam.** Yeni `routers/hesap.py` — öneri 8 rota: `POST /api/hesap/kayit`,
`POST /api/hesap/dogrula` (jeton), `POST /api/hesap/giris`,
`POST /api/hesap/cikis`, `POST /api/hesap/sifirla` (istek),
`POST /api/hesap/sifirla/dogrula` (yeni parola), `GET /api/hesap/ben`
(`{id, eposta, dil, is_admin}` — ön yüz açılışta bunu sorar),
`GET /giris` (statik sayfa). Rota sayısı 46 → 54, `tests/test_app_bolme.py:124`
güncellenir.

**Parola.** `pwdlib[argon2]` (`pwdlib==0.3.*`; altında argon2-cffi 25.1) —
argon2id, kütüphane parametreleri, `needs_rehash` ile ileride sessiz göç.
Doğrudan `argon2-cffi` de olurdu; pwdlib'in kazancı algoritma göçünün hazır
olması. Kayıtta asgari 8 karakter, azami 128; başka kural YOK (NIST 800-63B).

**Oturum — sunucu tarafı, DB'de; JWT DEĞİL.** Giriş `secrets.token_urlsafe(32)`
üretir, SHA-256 özeti `oturumlar`a yazılır, ham jeton `kromis_oturum`
çerezinde: `HttpOnly`, `SameSite=Lax`, `Path=/`, 30 gün kayan ömür
(`son_gorulme` her istekte 5 dk çözünürlükle güncellenir — istek başına
UPDATE değil), `Secure` HTTPS arkasında (`services/dil.py:132`nin dil
çerezi için bıraktığı aynı not — iki çerez aynı bayrak kararını tek yerden
alır: `services/cerez.py`). NEDEN JWT DEĞİL: (a) iptal — çıkış, parola
değişikliği ve admin'in oturum düşürmesi tek `DELETE`; JWT'de kara liste
gerekir ki o da bir DB tablosu; (b) tek köken — ön yüz aynı sunucudan
geliyor, üçüncü bir tarafa jeton taşınmıyor; (c) sızan çerezin ömrü DB'den
kesilebilir. Spec'in "JWT Auth" satırından sapma, sonda yazılı.

**CSRF ve köken — `netguard`ın web karşılığı.** `SameSite=Lax` başka siteden
gelen POST'ta çerezi göndermez; ikinci kat `services/koken.py` ara katmanı:
GET/HEAD dışındaki her istekte `Sec-Fetch-Site` `same-origin`/`none` olmalı
ya da `Origin` başlığı `KROMIS_KOKEN` (env, `https://…`) ile eşleşmeli;
aksi 403. Ön yüzün 15 JSON `fetch`i zaten `Content-Type: application/json`
gönderiyor (Faz 0 / 5 ölçümü), multipart yükleyen 5 rota (`/api/edit`,
`/api/video/animate`, `/api/import`, `POST /api/assets/{kind}`, `/api/logo`
ve `/api/banner`) için de `Origin` tarayıcı tarafından kendiliğinden
geliyor. Özel başlık (`X-Kromis-Istek`) GEREKMİYOR; `netguard.py`nin
`Host`/`Origin` mantığı dondurulmuş kabukta kalır, buraya kopyalanmaz.

**Hız sınırı.** `giris_denemeleri` tablosundan: aynı e-posta 15 dk'da 10,
aynı IP 15 dk'da 30 başarısız → 429 + `Retry-After`. Kayıt ve sıfırlama
isteği IP başına saatte 5. Redis yok (Faz 2), `slowapi` yok (süreç içi
sayaç, çok replikada anlamsız). Kullanıcı numaralandırmasına karşı: kayıt
ve sıfırlama cevapları e-posta var/yok ayırt ETMEZ.

**E-posta.** `services/posta.py` — `gonder(kime, konu, metin_tr, metin_en)`;
iki arka uç: `konsol` (geliştirme/test: `hata.log` yanına `posta.log` ve
`app.state.son_posta` — E2E doğrulama bağlantısını buradan okur) ve
`resend` (`https://api.resend.com/emails`, `httpx` ile — SDK yok, depo
zaten httpx). Seçim `KROMIS_POSTA=konsol|resend`, anahtar `RESEND_API_KEY`,
gönderen `KROMIS_POSTA_GONDEREN`. Metinler `bundled/i18n`e girer (831
anahtar/dil → +~20). Şablon HTML değil düz metin (ilk sürüm; tıklanabilir
bağlantı yeter).

**Ön yüz.** `static/giris.html` + `static/giris.js` + `static/giris.css`:
giriş / kayıt / sıfırlama üç sekme, `X-Kromis-Lang`-çerez dil zinciri aynen
(sayfa `routers/kok.py`nin `index` deyimiyle çevrilerek servis edilir).
`index.html`e DOKUNULMAZ (286 metin çapası); `core.js` açılışta
`GET /api/hesap/ben` sorar, 401'de `/giris`e yönlendirir; Ayarlar paneline
"Çıkış" düğmesi (`settings.js`). Faz 0 / 7'nin çerçeve kararı BU PR'da
verilmez: iki statik sayfa vanilla kalır; eslint defterine
(`eslint.paylasilan-adlar.json`) yeni dosya, `tests/test_id_contract.py::
test_the_scan_covers_every_shipped_script` yeni betiği görür.

**Dokunulan.** yeni `routers/hesap.py`, `services/{kimlik,posta,koken,cerez}.py`,
`models.py` (`KayitIstegi`, `GirisIstegi`, … `extra="forbid"`), `static/giris.*`,
`static/core.js`, `static/settings.js`, `bundled/i18n/{tr,en}.json`,
`app.py` (ara katman sırası: köken → dil → rota), `.env.example`
(`KROMIS_KOKEN`, `KROMIS_POSTA*`, `RESEND_API_KEY`), `eslint.paylasilan-adlar.json`,
`tests/test_hesap.py` (yeni, ~40: kayıt-doğrula-giriş-çıkış; yanlış parola;
doğrulanmamış hesap giremez; sıfırlama tek kullanım ve süreli; çerez
bayrakları; 429; köken 403; numaralandırma yok), `tests/test_playwright_hesap.py`
(yeni E2E: form üzerinden kayıt → `konsol` postadan bağlantı → giriş → `/`
açılıyor), `tests/test_app_bolme.py`, `tests/test_i18n.py`, `docs/graflar/*`.

**Risk.** Orta-yüksek: güvenlik yüzeyi. Küçültme: hazır parola kütüphanesi,
sunucu oturumu, tek köken; jetonlar özetli, tek kullanımlık, süreli.
`Secure` bayrağı yerelde `http://localhost`ta çerezi düşürür — env ile
kapatılabilir (`KROMIS_GUVENLI_CEREZ=0` yalnız compose'ta), bekçi test
varsayılanın AÇIK olduğunu sınar. Google OAuth BU PR'da YOK (aşağıda,
"Faz 1 dışı" / isteğe bağlı 10. görev).

**Çıkış ölçütü.** E2E: tarayıcıdan kayıt → e-posta → giriş → çıkış;
çerezsiz `GET /api/history` 401; başka siteden gelen POST 403; 11.
başarısız giriş 429; takım yeşil.

---

## 4. İstek bağlamı: `services/kimlik.py` kapısı, kullanıcı başına `Ayarlar`, dil zinciri (PR: `faz1/istek-baglami`)

**Kapsam.** Faz 0'ın bıraktığı iki kapı dolduruluyor:

* `services/ayar.py:83` `ayarlar(request)` — çerezden oturum → kullanıcı
  çözülür (tek sorgu, `oturumlar ⋈ kullanicilar`, `request.state.kullanici`ye
  konur, aynı istekte ikinci kez sorulmaz) ve o kullanıcının `Ayarlar`ı
  döner: `data_dir` aynı, `output_dir = <data_dir>/kullanicilar/<uuid>/output`,
  `assets_dir = …/assets`, `static_dir` aynı. Donmuş `dataclass` istek başına
  yeni örnek — 4 dize, ölçülecek bir bedeli yok. Router'lar DEĞİŞMEZ
  (`ayarlar.output_dir` okumaya devam eder — Faz 0 / 4'ün vaadi). Kullanıcı
  dizini ilk girişte `paths.ensure_data_dirs(...)` ile açılır (`paths.py:309`,
  zaten değişken argüman alıyor).
* `services/kimlik.py` — `aktif_kullanici(request)` bağımlılığı: oturum
  yoksa/bitmişse **401** (JSON `{"detail": …}` i18n'li; ön yüz 401'de
  `/giris`e gider — 302 DEĞİL, çünkü `fetch` yönlendirmeyi takip eder ve
  JSON bekleyen 15 çağrı HTML alırdı). Tarayıcı gezinmesi olan tek rota
  `GET /`: oturumsuzsa **302 `/giris`**. Ara katman DEĞİL bağımlılık:
  hangi rotanın açık olduğu imzada okunur (Faz 0 / 4'ün "imza bağımlılığı
  söyler" ilkesi). Kapı arkasına giren: 46 − 2 (`/`, `/health`) − hesap
  rotaları = **44 rota** (42 depo + `POST /api/settings` + `POST /api/palette/suggest`
  — sonuncusu veri okumaz ama `thecolorapi.com`a çıkıyor, anonim istek
  kotayı yer). `/static` mount açık kalır (giriş sayfasının CSS/JS'i).
* Dil zinciri (`services/dil.py:82` `coz`): 3. halka `tercih.dil(output_dir)`
  (`dil.py:89`) yerine `kullanicilar.dil` — oturum sorgusu zaten kullanıcıyı
  getirdi, ek sorgu SIFIR; `services/tercih.py`nin dosya imzalı önbelleği
  web'de gereksizleşir (dondurulmuş kabuk için durur, 6. görevde `prefs`
  ile birlikte kararı). `POST /api/prefs` `language` yazınca hem çerez
  (`cerez_yaz`) hem `kullanicilar.dil` güncellenir — oturumsuz istemci yolu
  (Faz 0 / 3 sapma b) web'de yok.
* Playwright `ServerThread` (`tests/test_playwright_studio.py:133`) aynı
  süreçte koşuyor; E2E fixture'ı DB'ye kullanıcı yazıp tarayıcıya
  `context.add_cookies` ile oturum çerezi koyar (her testte formu doldurmak
  değil — form akışı `test_playwright_hesap.py`nin işi). Birim/rota testleri
  için `tests/conftest.py`de **autouse** `kullanici` fixture'ı:
  `app.dependency_overrides[kimlik.aktif_kullanici]` → test kullanıcısı;
  37 dosyanın 178 `TestClient`i değişmeden geçer (Faz 0 / 4'te 66 yamanın
  tek fixture'a inmesinin aynısı). Hesap testleri override'ı kaldırır.

**Dokunulan.** `services/ayar.py`, `services/kimlik.py`, `services/dil.py`,
`routers/kok.py`, `routers/*.py` (44 imzaya `kullanici: Kullanici = Depends(kimlik.aktif_kullanici)`
— mekanik, ama her rotaya tek satır), `routers/ayarlar.py` (`language`
yazımı), `tests/conftest.py`, `tests/test_dil.py` (3. halka), `tests/test_app_bolme.py`
(yeni bekçi: hesap rotaları ve `/`,`/health` dışında HER rota kapı
bağımlılığını taşıyor — `test_every_route_that_touches_a_directory_declares_the_dependency`
deyimi), yeni `tests/test_kimlik.py` (401/302; iki kullanıcı iki dizin;
`ayarlar()` aynı istekte tek sorgu), `tests/test_playwright_*.py` (çerez
fixture'ı), `docs/graflar/*` (README'ye "kiracıya göre dizin bu kapının
içinde" notu zaten var — `uc-noktalar.md` başlığı).

**Risk.** Orta. En geniş mekanik diff (44 imza). Kırılma sınıfı: bir rota
kapıyı unutur → bekçi test yakalar; `GET /`nin 302'si `test_index`in 4
`c.get("/")`ünü (satır 15, 58, 70, 103, 325) kırar → autouse fixture
oturumu da sağlar (çerez değil override — `index` rotası `aktif_kullanici`yi
`Depends` ile alır, override onu da kapsar).

**Çıkış ölçütü.** İki kullanıcı, aynı süreç, aynı anda: A `history`sinde
B'nin görselini görmüyor, `/output/<B'nin dosyası>` A'ya 404; oturumsuz
44 rota 401, `/` 302; dil DB'den geliyor (`prefs.json` okunmuyor); takım yeşil.

---

## 5. Galeri ve klasörler → DB: `medya`, `klasorler` (PR: `faz1/galeri-db`)

**Kapsam.** `storage.py` ve `folders.py`nin JSON tarafı DB'ye taşınır;
MEDYA DOSYALARI DİSKTE KALIR (kullanıcı dizininde, 4. görev). Yeni
`services/depo/medya.py` ve `services/depo/klasor.py` (öneri; `storage`/`folders`
adları dondurulmuş kabukta kalıyor, ikisi bir arada yaşar): aynı işlev
kümesi (`save/list_history/set_folder/delete/delete_many/unfile_folders/
arena_round/set_arena_winner` ↔ `create/list/exists/depth/descendants/
delete_tree/rename/export_zip`), imzada `output_dir` → `(oturum, kullanici_id)`;
dosya yazımı için `output_dir` ayrıca gelir (`ayarlar.output_dir`). 19 + 12
rota (`routers/galeri.py` 14 + `uretim.py` 4 + `bindirme.py` 2 — `/output/{filename}`
artık `medya`da `filename` sorgular, id'yi `_SAFE_ID`den geçirmeye devam
eder) yeni depoya döner. `jsonstore.lock_for`un yerine transaksiyon:
"oku → değiştir → yaz" deseni SQL `UPDATE … WHERE`e iner, `RLock` gerekmez;
`delete_many`nin 500 id sınırı (`models.MAX_BULK_IDS`) aynen. 5 `async def`
rotanın DB çağrısı `run_in_threadpool` ile (1. görev kararı). Dosya + satır
ATOMİK DEĞİL ve bilinçli: önce dosya yazılır sonra satır (`storage.save`
`:148` zaten bu sıradadır); satır yazımı düşerse dosya artık kalır — 9.
görevin "artık dosya taraması" CLI'ına not. Silmede önce satır sonra dosya
(satır gidince dosya ulaşılmaz; `media_path_of`in "kaydı olmayan dosya da
silinmiş sayılır" sözleşmesi korunur).

**Dokunulan.** yeni `services/depo/{medya,klasor}.py`, `routers/galeri.py`,
`routers/uretim.py`, `routers/bindirme.py`, `services/gorsel.py`
(`output_png_path` — dosya yolu hesabı aynı), `services/kapilar.py`
(`check_folder(folder_id, output_dir)` → `(oturum, kullanici_id)`),
`tests/test_storage.py` (19) / `test_folders.py` (52) / `test_galeri_*`,
`test_arena*` (9 dosya `storage` ithal ediyor, 4 `folders`) — testler DB
fixture'ıyla yeniden yazılır ya da yeni dosyalara kopyalanır (eski
`storage`/`folders` testleri dondurulmuş kabuk için KALIR, CLAUDE.md §4'ün
dondurulmuş test notu), `tests/test_legacy_formats.py` (yalnız alan
KAYBINI kovalıyor — DB satırının JSON'a dökümü aynı alanları vermeli:
bekçi), `docs/graflar/*`.

**Risk.** Orta-yüksek: en çok rota (31/46) ve en büyük test dokunuşu.
Küçültme: önce `klasorler` (12 rota, `folders` 4 test dosyası), sonra
`medya`; ikisi ayrı commit, gerekirse ayrı PR (`faz1/galeri-db-1/2`).
Eş zamanlılık: Prompt Yönetmeni tur sonunda yazıyor + kullanıcı taşıyor —
`jsonstore`un çözdüğü yarış artık `SELECT … FOR UPDATE`/`UPDATE … WHERE`
ile; `tests/test_jsonstore.py`nin (6) paralel-yazım senaryosu DB'ye
taşınır.

**Çıkış ölçütü.** `history.json`/`folders.json` web yolunda hiç açılmıyor
(bekçi: test kullanıcı dizininde bu dosyaların OLMADIĞINI sınar); 31 rota
aynı gövdeleri döndürüyor (`tests/test_legacy_formats.py` alan kümesi);
iki kullanıcı izolasyonu 4'teki testte yeniden doğrulanıyor; takım yeşil.

---

## 6. Sohbet, palet, varlık, tercih → DB; `backup.py` web yolundan çıkar (PR: `faz1/sohbet-palet-varlik-db`)

**Kapsam.** `chat_store` → `services/depo/sohbet.py` (`sohbetler`, `mesajlar`
JSONB; `cover_from`/`message_count` türetimi aynı; `list_chats` `updated_at
DESC`), `palette_store` → `depo/palet.py` (`paletler`; `colors` JSONB
dondurulmuş — `palette_store.py`nin "tarife değişse geçmiş yeniden yazılmaz"
disiplini), `assets_store` → `depo/varlik.py` (`varliklar`, `tur ∈ {logos,
banners,mottos}` `CHECK`; dosya `assets_dir/<tur>/<id>.png` aynı yerleşim;
`migrate_legacy_uploads` (`assets_store.py:120`) web'de ÇAĞRILMAZ — 8.
görevin içe aktarma aracı yapar), `prefs` → `depo/tercih.py` (`tercihler`,
kullanıcı başına 1 satır; `read()`/`read_stored()` ayrımı `NULL` ile:
"hiç yazılmamış" = NULL, `update()` `_ENUMS` doğrulaması `models.ALLOWED_*`
ile aynı). 10 + 5 + 9 + 9 rota. `services/modeller.director_context(output_dir)`
ve `services/palet.saved_palette` imzaları `(oturum, kullanici_id)`.
`routers/sohbet.py:78`in `json.load`/`UnicodeDecodeError` yorumu (bozuk
dosya senaryosu) anlamını yitirir — silinir. `backup.backup_manifests_if_version_changed`
`app.py:79`dan çıkar: yedeklenecek manifest kalmadı, DB yedeği platformun
(9. görev); modül ve 17 testi dondurulmuş kabuk için durur. `services/tercih.py`
(dosya imzalı önbellek, Faz 0 / 3) web yolunda okuyucusuz kalır: 4. görevde
dil DB'den geldi, `director_context` tercihi DB'den okur — modül silinir,
`tests/test_dil.py`nin "20 istekte ≤1 okuma" ölçüsü "istek başına 1 sorgu
(oturum), tercih için 0 ek sorgu" ölçüsüne döner.

**Dokunulan.** yeni `services/depo/{sohbet,palet,varlik,tercih}.py`,
`routers/{sohbet,paletler,bindirme,ayarlar}.py`, `services/{modeller,palet}.py`,
`app.py` (`backup` çağrısı), `tests/test_chat_store.py` (30) / `test_palette_store.py`
(14) / `test_assets.py` (17) / `test_assets_route.py` (10) / `test_prefs.py`
(27) / `test_chat_route.py` (50) / `test_palette_route.py` (54) / `test_dil.py`
— aynı "eski dosya kabuk için kalır, DB ikizi yeni dosya" düzeni,
`tests/test_backup.py` (17: `_isolate_lifespan` koruması `conftest`te —
lifespan artık `backup` çağırmıyorsa koruma anlamsızlaşır, gerekçesiyle
kaldırılır), `docs/graflar/*`.

**Risk.** Orta. `prefs`in `guncelleme_kontrolu`/`/api/guncelleme` çifti:
GitHub Releases denetimi dondurulmuş masaüstü için anlamlı, web'de
"yeni sürüm var" yanlış pozitif (Faz 0 dışı notu). BU PR'da `guncelleme.json`
diskte süreç geneli kalır (kullanıcı verisi değil), rota kullanıcı tercihini
DB'den okur; web'de kapatma kararı sahibin (aşağıda).

**Çıkış ölçütü.** Kullanıcı dizininde `chats.json`/`palettes.json`/`index.json`/
`prefs.json` YOK; `_lifespan` `backup`/`tercih` çağırmıyor; 33 rota aynı
gövdeler; takım yeşil.

---

## 7. BYOK anahtarları kullanıcı başına, şifreli: `credentials.env` → `saglayici_kimlikleri` (PR: `faz1/kimlik-bilgileri`)

**Kapsam.** Bugün: `POST /api/settings` (`routers/ayarlar.py:117`, imza
`models.SettingsRequest` `models.py:316`, 15 alan) `ac.save_env`
(`routers/ayarlar.py:256`) ile TEK dosyaya yazıyor; okuyan `credstore.resolve/
configured_map/chat_configured_map` (`credstore.py:77,184,193`) ve
`azure_client.load_credentials/read_env_values` (`:213,220`); 14 modül
`azure_client`ı, 11'i `credstore`u ithal ediyor ama SAĞLAYICI ADAPTÖRLERİ
`(key, base_url)` çiftini `credstore.resolve`dan alıyor — yani kaynağı
değiştirmenin yeri `credstore`, adaptörler değil. Yeni: `services/sifre.py`
(`cryptography` Fernet — `MultiFernet` ile anahtar döndürme;
`KROMIS_SECRET_KEY` 32 bayt base64, HKDF ile "kimlik" amaçlı alt anahtar;
sütun `anahtar_surumu`), `saglayici_kimlikleri (kullanici_id, ad, sifreli_deger,
anahtar_surumu, guncellendi)` — `ad` bugünkü env adı (`AZURE_IMAGE_API_KEY`
…, `catalog.CREDENTIALS` `key_env`/`url_env` + `AZURE_CHAT_DEPLOYMENT`;
ad envanteri `.env.example`in bekçisiyle aynı kaynaktan). `credstore`
işlevleri `env_path` yerine `kimlikler: Mapping[str, str]` alır (istek
başına bir kez çözülüp `request.state`e konan düz sözlük — adaptörlere
`resolve(cred_id, kimlikler)`); `azure_client.read_env_values` dondurulmuş
kabukta kalır, web yolu çağırmaz. `GET /api/settings` yalnız boolean
döndürmeye devam eder (`configured_map` sözleşmesi — anahtar HİÇ geri
dönmez, maskeli bile). `POST /api/settings` doğrulaması aynı
(`check_base_url`, satır sonu kapısı — `AzureImageError` → 400 aynen).
Platform sahipli anahtar (herkes için tek Azure anahtarı) BU FAZDA YOK —
Faz 2 (spec §5 "platform sahipli sağlayıcı anahtarları için secret
manager"); Faz 0 / 8'in `.env.example` takibi ("ortamdan okuma 12-factor")
böylece kapanıyor: web'de anahtar ne dosyadan ne ortamdan, DB'den.

**Dokunulan.** yeni `services/sifre.py`, `services/depo/kimlik_bilgisi.py`,
`credstore.py` (imza), `routers/ayarlar.py`, `routers/{sohbet,uretim}.py`
(kimlik sözlüğünü `Depends` ile alır), `chat_providers.py`/`providers.py`
(çözüm çağrısının parametresi), `.env.example` (`KROMIS_SECRET_KEY`
zorunlu — yoksa uygulama AÇILMAZ, sessiz varsayılan anahtar YOK; bekçi),
`Dockerfile` (`HOME=/data` gerekçesi zayıflar — kimlik dosyası web'de yok;
satır KALIR, gerekçe yorumu güncellenir), `tests/test_credstore.py` (17) /
`test_settings_route.py` (44) / `test_azure_client*.py` (16; 30 test
dosyası `azure_client` ithal ediyor — çoğu adaptör testi, `env_path`
geçen 24 dosya gözden geçirilir), yeni `tests/test_sifre.py` (şifrele/çöz,
yanlış anahtar → hata, döndürme, DB'de düz metin YOK — satırı okuyup
`sk-` aranır), `docs/graflar/*`.

**Risk.** Orta. Sır yönetimi: `KROMIS_SECRET_KEY` kaybolursa bütün
kullanıcıların anahtarları okunamaz — 9. görevin yedek notunda "anahtar
DB yedeğiyle AYRI yerde" kuralı. Hata mesajı redaksiyonu (`errlog.redact_secrets`)
DB istisnalarını da kapsamalı: bir `IntegrityError` mesajı sütun DEĞERİNİ
taşıyabilir — `tests/test_errlog.py`ye SQLAlchemy istisnası senaryosu.

**Çıkış ölçütü.** İki kullanıcı farklı Azure anahtarıyla üretiyor, her
istek kendi anahtarıyla çıkıyor (sahte istemci hangi anahtarı gördüğünü
kaydeder); DB dökümünde (`pg_dump`) hiçbir anahtar düz metin değil; web
yolunda `credentials.env` hiç açılmıyor (bekçi: `credentials_path` çağrısı
`routers/`/`services/`te yok); takım yeşil.

---

## 8. İçe aktarma ve ilk kullanıcı: `tools/ice_aktar.py`, `tools/kullanici.py`, `is_admin` (PR: `faz1/ice-aktarma`)

**Kapsam.** İki CLI, ikisi de `services/db.py` üzerinden, uygulama
ayakta olmadan çalışır:

* `tools/kullanici.py olustur --eposta … [--admin] [--dil tr]` — parolayı
  TTY'den ister (argümanda değil: kabuk geçmişi), e-postayı doğrulanmış
  yazar (`dogrulandi_at = now`; ilk kullanıcı posta servisi kurulmadan
  girebilmeli). `--admin` `is_admin=true`; bugün `is_admin`i okuyan tek şey
  `GET /api/hesap/ben` (ön yüz için) — admin arayüzü YOK, admin rotası YOK.
  Ayrıca `oturum-dusur --eposta` (sızan çerez için acil kapı).
* `tools/ice_aktar.py --kaynak <KROMIS_DATA_DIR> --eposta …` — tek kullanıcılı
  yerleşimi (sahibin kendi verisi: `output/history.json`, `folders.json`,
  `chats.json`, `palettes.json`, `assets/*/index.json`, `prefs.json`, ve
  `~/.config/kromis/credentials.env` — `--kimlik-dosyasi` ile ayrı verilir,
  `data_dir` DIŞINDA) bir hesaba yükler; medya dosyaları kullanıcı dizinine
  KOPYALANIR (taşınmaz; kaynak dokunulmaz — `paths._move_if_new_is_absent`in
  "hiçbir şey silinmez" kuralı). 12 haneli id'ler KORUNUR (`_SAFE_ID`
  32'ye kadar kabul ediyor); DB'de çakışan id yeniden üretilir ve
  başvurular (`parent_id`, `folder_id`, `chats.messages[].image_ids`,
  `arena_id` kardeşleri) yeniden yazılır — `assets_store.migrate_legacy_uploads`in
  (`:163`) çakışma deseni. Yoklukları NULL: `imported`/`session_id`/
  `arena_id`/`kind`/`duration`. `--kuru` (dry run) sayıları basar;
  `--yeniden` yoksa ikinci koşu var olanı atlar (idempotent: `(kullanici_id,
  id)` üzerinden). Okuma `json.load` — `backup.py`nin "bayt kopyala" kuralı
  burada GEÇERLİ DEĞİL, çünkü amaç tam tersi: okuyup dönüştürmek; bozuk
  dosya kayıt kayıt raporlanır, araç durmaz.

**Dokunulan.** yeni `tools/ice_aktar.py`, `tools/kullanici.py`, yeni
`tests/test_ice_aktar.py` (`tests/fixtures/v18` eski biçim fixture'ı +
üretilmiş güncel yerleşim → DB satırları alan alan; çakışma; idempotenlik;
kuru koşu yazmıyor), `tests/test_kullanici_cli.py`, `KURULUM.md` (web
kurulumu: ilk kullanıcı, içe aktarma), `README.md` geliştirici bölümü,
`docs/graflar/*` (`tools/` modülleri haritada — `tools/graf_uret.py`
kendini nasıl görüyorsa öyle).

**Risk.** Düşük-orta: yalnız araç, ürün yolu değişmiyor. Sahibin verisi
ölçülemedi (bu makinede `output/` boş: `prefs.json` + `guncelleme.json`) —
`--kuru` ilk koşuda gerçek sayıları verir, belgeye yazılır.

**Çıkış ölçütü.** Sahibin `KROMIS_DATA_DIR`ı tek komutla bir hesaba iniyor,
galeri/klasör/sohbet/palet/varlık/tercih/anahtar hepsi arayüzde aynı
görünüyor; ikinci koşu 0 yeni satır; takım yeşil.

---

## 9. Operasyon: göçlerin çalışma yeri, giriş betiği, yedek, `.env.example`, CI (PR: `faz1/operasyon`)

**Kapsam.**

* **Göçler NEREDE koşar — "release command", konteyner açılışı DEĞİL.**
  `Dockerfile` CMD (`Dockerfile:93`) `alembic upgrade head && uvicorn`
  YAPMAZ: iki replika aynı anda açılırsa iki `upgrade` yarışır (Alembic
  kilit tutmaz). Yönetilen platformların hepsinde dağıtım öncesi tek
  seferlik komut var (Fly `release_command`, Railway pre-deploy, Render
  pre-deploy command); imaja `tools/goc.py` (`alembic upgrade head`in ince
  sarmalayıcısı: URL'yi aynı kaynaktan, çıkışta `alembic current` basar)
  girer ve platform onu çağırır. Yerel `compose.yaml` için ayrı `goc`
  servisi (`depends_on: postgres`, `condition: service_completed_successfully`
  ile `kromis` onu bekler). `KROMIS_GOC_ACILISTA=1` gibi bir "açılışta
  göç" bayrağı BİLEREK YOK: tek replikada rahat, iki replikada tuzak.
* **Yedek.** DB yedeği platformun (Neon/Supabase PITR; kendi Postgres'inde
  `pg_dump` cron); MEDYA dizini ayrı yedek (birim anlık görüntüsü);
  `KROMIS_SECRET_KEY` ikisinden AYRI yerde (7. görev). `docs/isletme.md`
  (yeni): geri yükleme tatbikatı adımları — Faz 5'in "yedekleme ve geri
  yükleme tatbikatı" kalemi için iskelet. Kod yok, belge + bekçi
  (`tests/test_docker_kapisi.py` `.env.example`i tarıyor: her yeni değişken
  açıklamalı).
* **`.env.example`** son hâli: `KROMIS_DATA_DIR`, `PORT`, `DATABASE_URL`,
  `KROMIS_SECRET_KEY`, `KROMIS_KOKEN`, `KROMIS_POSTA`, `KROMIS_POSTA_GONDEREN`,
  `RESEND_API_KEY`; 2. bölüm (15 sağlayıcı adı) BAŞLIĞI değişir:
  "credentials.env biçimi — dondurulmuş masaüstü/Android sürümü ve
  `tools/ice_aktar.py --kimlik-dosyasi` için; web sürümü bunları DB'de
  tutar". Bekçi testin katalog eşitliği aynen.
* **CI.** `_test.yml`: `services: postgres:17-alpine` + `KROMIS_TEST_DATABASE_URL`;
  `ci.yml` `docker` işi: konteyner artık `DATABASE_URL` ister — iş bir
  Postgres servisiyle koşar, `/health` `db_reachable:true` bekler
  (`curl -f` 503'te düşer, aynı mekanizma). `tests/test_test_ortami.py`
  yeni adımı `_test.yml`le eşitler.
* **Artık dosya taraması.** `tools/artik_dosya.py`: kullanıcı dizinlerinde
  DB'de satırı olmayan medya dosyalarını listeler (`--sil` ile siler) —
  5. görevin "dosya + satır atomik değil" borcu.
* **`tools/graf_uret.py`.** `services/depo/` alt paketi ve `alembic/`
  haritada; `alembic/versions/*.py` modül sayısını şişirir — `docs/graflar`
  için `alembic/` dışlanır, gerekçe README'nin son bölümüne (statik
  taramanın görmediği şeyler listesine "göç betikleri bilerek dışarıda").

**Dokunulan.** `Dockerfile` (gerekçe yorumları), `compose.yaml`, `.env.example`,
`.github/workflows/{_test,ci}.yml`, yeni `tools/{goc,artik_dosya}.py`,
`docs/isletme.md`, `KURULUM.md`, `tools/graf_uret.py`, `tests/test_docker_kapisi.py`
(28), `tests/test_test_ortami.py`, `tests/test_paketleme_dondurma.py`
(`docker` işi hâlâ kesici ve itmiyor), `tests/test_graflar.py`.

**Risk.** Düşük. Kod tarafı iki küçük araç; asıl iş belge ve YAML. CI
`docker` işinde Postgres servisi + `docker run --network` ayarı kırılgan
olabilir — `host.docker.internal` yerine `--network host` ve `localhost`.

**Çıkış ölçütü.** Boş bir Postgres + boş birim ile `docker compose up`:
göç koşuyor, uygulama açılıyor, `/health` 200, `/giris` açılıyor, CLI ile
ilk kullanıcı yaratılıp giriliyor; CI'ın 5 işi yeşil; takım yeşil.

---

## Test stratejisi — kesişen kararlar (her görevin "Dokunulan"ında tek tek var)

* **Postgres gerçek, atlama gürültülü, CI'da zorunlu** (1. görev). Yerel
  `tools/test_ortami.py` kümeyi ikililerden açar; root'ta yardımcı kullanıcı.
  SQLite hiçbir yerde.
* **Kimlik testlerde tek noktadan** (4. görev): autouse `kullanici` fixture'ı
  `dependency_overrides` ile; 178 `TestClient` çağrısı değişmez. E2E'de çerez
  `context.add_cookies` ile; form akışı tek E2E dosyasında.
* **Eski depo testleri SİLİNMEZ** (5-6): `tests/test_storage.py` ve kardeşleri
  dondurulmuş kabuğu koruyor (Faz 0 dışı notu, ~190 kabuk testi ile aynı
  aile); DB ikizleri yeni dosyalar. Takım büyür (~3.000 → ~3.400 tahmin),
  süre Postgres fixture'ıyla +10-15 sn (şablon DB kopyası ~50 ms/test dosyası).
* **Alan kaybı bekçisi** `tests/test_legacy_formats.py` DB dökümüne
  uygulanır: bir satırın JSON'a dökümü bugünkü kayıt alanlarının tamamını
  taşır (`legacy - set(produced)` boş).
* **`tests/test_app_bolme.py:124` rota sayısı** 46 → 54 (hesap 8) tek yerde;
  yeni bekçi: hesap dışı her rota `kimlik.aktif_kullanici` taşıyor.
* **Sır sızıntısı**: `pg_dump` çıktısında ve `hata.log`da `sk-`/`AZURE`
  değer araması (7. görev); `.gitleaks.toml` test fixture'larındaki sahte
  Fernet anahtarları için muafiyet satırı (gerekçesiyle).
* **`tests/test_index.py` (286) DOKUNULMAZ**: `index.html` değişmiyor; giriş
  sayfası ayrı dosya. Faz 0 / 7'nin çerçeve kararı bu fazda AÇIK kalıyor —
  vanilla sürüyor; karar Faz 2'nin iş listesi/SSE arayüzüyle birlikte.

---

## Sahibin karar noktaları — öneri ve gerekçe

| # | konu | öneri | neden | alternatif ve bedeli |
| --- | --- | --- | --- | --- |
| K1 | ORM / göç aracı | **SQLAlchemy 2.0 + Alembic**, senkron `Session`, sürücü **psycopg 3** | 41/46 rota senkron `def`, threadpool'da; psycopg 3 sync+async tek sürücü; Alembic `check` ile "model = göç" bekçisi | asyncpg: async-only, 41 rota yeniden yazılır. SQLModel: Pydantic v2 ile tablo/istek modelini birleştirir ama `models.py`nin `extra="forbid"` istek modelleri zaten var, iki dünya karışır. Ham SQL: göç ve tip notu elle |
| K2 | Kimlik doğrulama yöntemi | **E-posta + parola (argon2id) + e-posta doğrulama + sıfırlama**; Google OAuth isteğe bağlı 10. görev | Küresel kitle, e-posta evrensel; parola yolu doğrulama e-postasını zaten gerektiriyor, sıfırlama aynı altyapı; OAuth ek bir dış bağımlılık (Google Cloud projesi, redirect URI, gizli anahtar) | Sihirli bağlantı (parolasız): daha az kod ama her giriş e-posta bekler, posta sağlayıcısı kesintisi = giriş kesintisi. OAuth-first: parolasız ama Google'a bağımlı, kurumsal e-postası Google olmayan kullanıcı dışarıda |
| K3 | Oturum vs JWT | **Sunucu oturumu (DB) + HttpOnly SameSite=Lax çerez** | İptal tek `DELETE`; tek köken, jeton taşınacak üçüncü taraf yok; spec'in JWT'si 2026-08'de "ayrı API + mobil" varsayımıyla yazıldı, web-first o varsayımı kaldırdı | JWT: istek başına DB sorgusu yok (biz zaten kullanıcıyı çekiyoruz — dil için), ama kara liste tablosu gerekir; ikisinin toplamı oturum tablosundan fazla |
| K4 | Testte SQLite mi Postgres mi | **Postgres** — CI servis konteyneri, yerelde ikililerden geçici küme, yoksa gürültülü atlama, `KROMIS_E2E_ZORUNLU=1` hata | JSONB/citext/timestamptz/eş zamanlılık SQLite'ta yok; Faz 0'ın "atlanan test = yeşil değil" dersi ölçülü (8/9). Bu makinede Postgres 16.13 ikilileri var ve küme açıldı; Docker imajı çekilemiyor | SQLite: kurulumsuz, ama göç dosyaları iki lehçede yazılır ve Postgres'e özgü kusur yalnız CI'da görünür — Faz 0'ın kırmızılarının aynısı |
| K5 | Medya dosyalarının yeri | **Faz 1'de yerel disk**, `KROMIS_DATA_DIR/kullanicilar/<uuid>/`; S3/R2 **Faz 2** (kuyrukla birlikte) | Worker yok — medyayı yazan hâlâ istek; `FileResponse` çalışıyor; yönetilen platformlarda kalıcı birim var; tek replika kabul. Nesne depolama gelince yazan taraf worker olacak, o zaman tek seferde | R2 şimdi: yol haritası Faz 1'de sayıyor (sapma, aşağıda); bedeli imzalı URL + yükleme akışı + 5 rota daha ve iki kez dokunma (Faz 2'de worker yine değiştirir) |
| K6 | Göçlerin çalıştığı yer | **Platformun dağıtım öncesi komutu** (`tools/goc.py`); konteyner açılışında DEĞİL | İki replika yarışı; yönetilen platformların hepsinde release command var | Açılışta `alembic upgrade`: tek replikada kolay, ölçek çıkınca tuzak; Alembic kilit tutmaz |
| K7 | E-posta sağlayıcısı | **Resend** (API + httpx, EU bölgesi, ücretsiz kademe 3.000/ay, alan adı doğrulaması SPF/DKIM) — DIŞ ve ileride ÜCRETLİ bağımlılık, hesap + DNS kaydı sahibin | Depo zaten httpx; SDK yok; `konsol` arka ucu testleri ağdan bağımsız kılar | Postmark (işlemsel e-postada güvenilirlik, ücretsiz 100/ay), SES (en ucuz, kurulumu en ağır, IAM). SMTP genel arayüz (`smtplib`) ile her sağlayıcı — ama API hata cevapları daha okunur |

Bunlara ek, daha küçük iki soru: `guncelleme.py`/`GET /api/guncelleme`
web'de kapatılsın mı (öneri: Faz 1'de dokunma, Faz 2'de "web sürümü" için
rota `{"web": true}` döner ve ön yüz düğmeyi gizler); Google OAuth Faz 1'in
10. görevi olsun mu (öneri: hayır, Faz 5 kapalı beta geri bildirimine göre).

---

## Üst belgeden (spec §2-3, §5) sapmalar — gerekçeli

* **JWT → sunucu oturumu** (K3). Spec'in şeması ayrı bir API sunucusu +
  mobil istemci varsayıyordu; web-first tek kökene indi.
* **PostgreSQL RLS → uygulama düzeyi süzgeç, RLS ikinci kat sonra** (2.
  görev). Şema RLS'e hazır (`kullanici_id` her satırda); politika ve
  `SET LOCAL` Faz 2/3'te, yönetilen Postgres'in rol modeli netleşince
  (Neon/Supabase'de superuser yok; pooler `SET LOCAL`i transaksiyon
  modunda geçiriyor, oturum modunda geçirmiyor — ölçülecek).
* **Cloudflare R2 Faz 1 → Faz 2** (K5). Yol haritası kartı R2'yi Faz 1'de
  sayıyor; medyayı yazan taraf Faz 2'de worker'a geçtiği için iki kez
  dokunmamak adına ertelendi. Faz 1'in çıkış ölçütü ("iki kullanıcı
  birbirinin verisini göremiyor") disk yerleşimiyle karşılanıyor.
* **`user / organization / membership` → yalnız `kullanicilar`.** Yol
  haritası Faz 1 kartı üç tablo sayıyor; ekip/kurum hesabı için ürün
  kararı yok (fiyatlama bireysel abonelik paketi). `kullanici_id` sütunu
  ileride `hesap_id`ye genelleştirilebilir; bugün ikinci bir kavram
  taşımak her sorguya bir `JOIN` eklemek demek.
* **Hetzner + Coolify → yönetilen servis** (sahibin 2026-09-16 kararı; K6
  buna göre). Spec §1 tablosu tarihsel kayıt olarak durur.
* **Dockerfile + compose + /health** yol haritasında Faz 1'deydi, Faz 0 / 8
  erken yaptı; burada yalnız DB eklentisi (1. ve 9. görev).

---

## Faz 1 dışı, ama burada not edilen

* **Kredi defteri, planlar, `model_available(plan)`** (`services/modeller.py:22`,
  `catalog.py:202`) → Faz 3. `medya.credits` sütunu koşulsuz yazılmaya devam
  eder; defter geldiğinde okuyacağı alan hazır. Faz 1'de kullanıcıya kredi
  gösterilmez, üretim engellenmez (BYOK: herkes kendi anahtarıyla).
* **İş kuyruğu, SSE, iş listesi, platform sahipli anahtarlar, Redis, hız
  sınırının Redis'e taşınması, R2/S3, RLS ikinci katı, yapısal loglama,
  Sentry** → Faz 2.
* **Stripe, abonelik yaşam döngüsü, KVKK/GDPR metinleri, hesap silme akışı,
  veri dışa aktarma** → Faz 4. `kullanicilar.silindi_at` sütunu yer tutucu.
* **Google OAuth** → isteğe bağlı, sahibin kararı (K2).
* **`chat-instructions.md` / `chat-instructions-video.md` ezmeleri**
  (`paths.py:177`, `chat_prompt.py:63`): web'de kullanıcı sunucu dosyası
  düzenleyemez; `director_guidance` tercihi (DB'de) kullanıcı özelleştirmesini
  karşılıyor. Ezme dosyaları dondurulmuş kabuk için kalır; web'de
  `GET /api/settings`in `chat_instructions_path` alanı (`routers/ayarlar.py:53`)
  anlamsız — Faz 2'de "persona düzenleme" özelliği olur ya da alan düşer.
* **`guncelleme.py` web'de** (yukarıdaki küçük soru).
* **Ön yüz çerçevesi / ES modül** (Faz 0 / 7 kararı): bu fazda iki statik
  sayfa vanilla; karar Faz 2'nin iş listesi arayüzüyle.
* **Dondurulmuş kabuk testleri** (~190 + bu fazda kalan eski depo testleri
  ~200): silinmez, kabuk ince WebView'a dönüştüğü gün toptan gider.
* **Ölçülmeyen:** sahibin gerçek veri hacmi (bu makinede `output/` boş),
  imaj boyutu (Faz 0 / 8'den devam), yönetilen Postgres'in pooler
  davranışı (RLS notu), Python 3.14 tekerlekleri (CI'da görünür).
