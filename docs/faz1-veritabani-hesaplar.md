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
**9** her an başlayıp 8 ile biter; **3b** (Google ile giriş) isteğe bağlı, 3'e
dayanır, ucuzsa Faz 1 içinde (sahibin 2026-09-17 kararı).

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

## 1. Veri tabanı zemini — SQLAlchemy 2 + Alembic + PostgreSQL, testte GERÇEK Postgres ✅ (PR: `faz1/veritabani-zemini`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Pinler `SQLAlchemy==2.0.*`
(2.0.54), `alembic==1.20.*` (1.20.0), `psycopg[binary]==3.3.*` (3.3.5 +
`psycopg-binary` 3.3.5); cp313 VE cp314 tekerlekleri PyPI'dan indirilerek
doğrulandı, `psycopg_binary.libs/libpq-*.so.5` tekerleğin içinde — `Dockerfile`
DEĞİŞMEDİ (libpq katmanı gerekmiyor; imaj boyutu bu makinede ölçülemedi, Docker
yok — CI'ın `docker` işi derliyor). `services/db.py`: `DATABASE_URL_ENV`,
`baglanti_dizesi()` (boş = yok), `motor_kur()` (`pool_size=2`, `max_overflow=3`,
`pool_pre_ping`, libpq `connect_timeout=2`), `motor_varsa(request)`,
`erisilebilir(motor, 1.0)`, `oturum(request)` ve **`OTURUM = Depends(oturum,
scope="function")`**. Kapsam sözcüğü PLANDA YOKTU ve zorunlu çıktı: FastAPI
0.118+ `yield` bağımlılığının çıkış kodunu ÖNTANIMLI olarak cevap
GÖNDERİLDİKTEN sonra koşturuyor — commit orada patlasa istemci 200 almış
olurdu; `function` kapsamı commit'i rota döner dönmez, cevap kurulmadan
koşturur (bekçisi `test_a_failing_commit_becomes_a_500_not_a_silent_200`).
Sondanın "1 sn zaman aşımı" cümlesi CEVAP BÜTÇESİ olarak uygulandı: libpq
`connect_timeout` asgarisi 2 sn (daha küçüğü 2'ye yuvarlanıyor), kara deliğe
giden TCP onu da aşabilir; `SELECT 1` ayrı iş parçacığında, `result(timeout=1)`
dolarsa `False`, vazgeçilen iş parçacığı libpq zaman aşımında kendi biter
(ölçüldü: asılı sahte motorla sonda 0,3 sn bütçede dönüyor). `Ayarlar`a alan
EKLENMEDİ (plan böyleydi); motor `app.state.motor`da, `_lifespan` kurar
(URL yoksa `None`, bozuk URL `hata.log`a + `None`, uygulama açılır),
kapanışta `dispose` + `None` — ardışık `with TestClient(app)`ler düşürülmüş
bir DB'nin motorunu görmesin.

`/health` gövdesi `{"ok","version","data_dir_writable","db_reachable"}`,
`ok` VE, 503 kuralı aynı. **Karar:** `DATABASE_URL` verilmemişse
`db_reachable:false` → 503, ayrı bir `null` değeri YOK — veri tabanı olmadan
bu uygulama hesap açamaz, "yapılandırılmamış ama sağlıklı" diye bir durum
yok. Bu kararın bedeli CI'ın `docker` işine düştü: DB'siz konteyner 503 verip
işi kırmızıya çevirirdi; sonda 503'e ALIŞTIRILMADI, iş 9. görevden öne alınan
Postgres servisiyle koşuyor (`--network host`, `-e DATABASE_URL`, `curl -f`
aynen). `alembic.ini` URL taşımıyor (`env.py` `config.attributes["baglanti_dizesi"]`
→ `DATABASE_URL`; ikisi de yoksa değişkenin adıyla `SystemExit`),
`target_metadata` boş `MetaData()` — böylece `alembic check` BUGÜNDEN
çalışıyor ("no new upgrade operations"; 2. görev buraya `tablolar.Base.metadata`
koyar), ilk göç `0000_zemin` boş (`upgrade`/`downgrade` `pass`), `script.py.mako`
telif başlıklı; `alembic/` `git ls-files` ile telif kapısına kendiliğinden
girdi, `docs/graflar` dışında (README'nin "görmediği şeyler" listesine
gerekçesiyle yazıldı).

**Test fixture'ı dört kademe** (`tests/conftest.py`): `pg_kume` (oturum;
`KROMIS_TEST_DATABASE_URL` varsa o, yoksa `tools/gecici_postgres.py`
`GeciciKume`) → `pg_sablon` (oturum; `DROP … WITH (FORCE)` + `CREATE DATABASE
kromis_sablon` + `alembic upgrade head` bir kez) → `veritabani_url` (modül;
`CREATE DATABASE kromis_t_<dosya>_<hex> TEMPLATE kromis_sablon`, dosya bitince
düşer) → `veritabani` (test; `DATABASE_URL`i `monkeypatch.setenv`). Autouse
altıncı guard `DATABASE_URL`i her testte ortamdan SİLİYOR — geliştiricinin
kabuğundaki gerçek adres `with TestClient(app)`e sızmasın. **Sapma:** küme
açma kodu `tools/test_ortami.py`ye DEĞİL yeni `tools/gecici_postgres.py`ye
kondu (salt kitaplık, 200 satır, hem conftest hem test_ortami ithal ediyor);
`test_ortami.py --kontrol` kümeyi GERÇEKTEN açıp kapatıyor ("ikili var" ≠
"küme açılıyor") ve "Postgres: hazir (gecici kume, ikililer:
/usr/lib/postgresql/16/bin)" diyor; `--ozet` (kanca) yalnız ikiliye bakıyor.
Root'ta yardımcı kullanıcı `su` ile DEĞİL `subprocess.run(user=, group=)` ile
(paketin `postgres` hesabı, yoksa `nobody`); soket dizini `/tmp/kromis-pg-*/soket`
(`sun_path` 107 bayt — uzun `TMPDIR`de düz `/tmp`), `listen_addresses=''`
(port yok), `--auth=trust`, `--no-sync` + `fsync=off`. **Ölçüldü:** küme açılışı
**0,7-0,8 sn** (initdb dâhil), kapanış 0,1 sn; şablon göçü + dosya başına
kopya ile takım **105,8 → 109,5 sn** (+4 sn); **3.000 → 3.032 geçti, 12
atlandı** (atlanan DB testi 0). Dosya sayıları: `tests/test_health.py` 8 → 11
(200 bekleyen testler artık `with TestClient` + `veritabani`; Faz 0'ın
lifespan'sız `_client()`i tek bir şeyi sınıyor — lifespan koşmamış süreçte
sonda 503 + `db_reachable:false` ile yine CEVAP VERİYOR), yeni `tests/test_db.py`
19 (ithal motor kurmaz; kapalı port 503; bozuk URL açılışı durdurmaz;
`oturum` commit/rollback/404-rollback/commit-hatası-500 GERÇEK Postgres'te;
`upgrade → downgrade base → upgrade`; `alembic check`; URL'siz alembic durur),
`test_docker_kapisi.py` +3, `test_test_ortami.py` +2; `tests/test_i18n.py`
`services/db.py`yi "konuşmayan" saydı (tek `detail` bir KOD:
`database_unavailable`). `.env.example`e `DATABASE_URL=` (BOŞ; compose
`environment:` kendi adresini verir ve `env_file`i ezer), `compose.yaml`a
`postgres:17-alpine` (yalnız `127.0.0.1:5432`, `pg_isready` sağlık denetimi,
`depends_on … service_healthy`, göç YOK — K6). `KROMIS_E2E_ZORUNLU=1` artık
Postgres yokluğunu da `UsageError` yapıyor (adı kaldı, anlamı genişledi);
yerelde eksikse conftest E2E uyarısının ikizini basıyor. Canlı doğrulama:
`uvicorn app:app` + geçici küme → `/health` 200
`{"ok":true,"version":"0.23.1","data_dir_writable":true,"db_reachable":true}`;
küme kapatıldı → 503 `{"ok":false,…,"db_reachable":false}`. Windows'ta geçici
küme yok (`KROMIS_TEST_DATABASE_URL` zorunlu — README'de yazılı); `tools/goc.py`
bu PR'da değil (9. görev).

---

## 2. Veri modeli ve ilk göç — kullanıcı, oturum, 7 iş tablosu ✅ (PR: `faz1/veri-modeli`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** `services/tablolar.py`
(454 satır, çoğu gerekçe): **11 tablo, 89 sütun, 13 indeks, 10 CHECK, 11 FK, 4
UNIQUE**, hepsi `MetaData(naming_convention)` ile adlı (`pk_/fk_/uq_/ck_/ix_`) —
adsız kısıt `alembic check`i her koşuda kırmızı yapar ve `downgrade`da
düşürülemez. Göç `0001_veri_modeli` `alembic revision --autogenerate` ile
üretildi ve ELLE dört yerde düzeltildi (dosyanın başlığında tek tek):
`CREATE EXTENSION IF NOT EXISTS citext` başa (autogenerate uzantı görmez;
uzantısız `upgrade` ilk tabloda düşüyordu), tablo sırası hesap → iş ve FK
bağımlılığına göre (autogenerate `medya`yı en sona, `giris_denemeleri`ni başa
koymuştu), dosya adı (`--rev-id` + `file_template` slug'ı iki kez yazdı), auto
işaretleri. `downgrade` 11 tabloyu ve uzantıyı düşürür; ileri-geri-ileri +
`check` temiz (ölçüldü: geçici kümede döngü ~1 sn). **Kararlar, belgenin açık
bıraktığı yerlerde:** (a) sütun adları — bugünkü JSON/API alanı olan her sütun
adını KORUR (`filename`, `folder_id`, `palette`, `theme` …; 5-6. görevin
satır→JSON dökümü eşlemesiz çıkar, alan-kaybı bekçisi sütun adlarını sayar),
yalnız DB'de yaşayanlar Türkçe (`kullanici_id`, `olusturuldu`/`guncellendi`,
belgenin adlandırdığı `mesajlar` ve `tur`); (b) enum'lar Postgres `ENUM`
tipiyle DEĞİL `text + CHECK` — `jetonlar.amac` dâhil (ALTER TYPE'ın transaksiyon
ve DROP TYPE dertleri yok; değer kümeleri `models.ALLOWED_THEMES/LANGUAGES`,
`assets_store.KINDS`ten okunuyor); `image_model`/`video_model`/`chat_provider`/
`chat_model` CHECK'siz (katalog değişince göç istemek yanlış yer); (c) bağlar —
`klasorler.parent_id` CASCADE (`delete_tree`), `medya.folder_id` SET NULL
(`unfile_folders`), `medya.parent_id`/`session_id`/`arena_id` FK DEĞİL (üçü de
bugün sarkabiliyor, FK anlamı değiştirirdi); (d) `tercihler` PK =
`kullanici_id` (ayrı id yok, "1 satır" DB'de), `saglayici_kimlikleri` PK =
`(kullanici_id, ad)`; ikisinde `(kullanici_id, olusturuldu)` indeksi YOK — PK
zaten `kullanici_id` ile başlıyor, belgenin "hepsinde" cümlesi beş liste
tablosunda birebir uygulandı; (e) `kullanicilar.dil` NULL'lanabilir (NULL =
hiç seçmedi, zincir tarayıcıya düşer) ve `CHECK dil IN ('tr','en')`;
`medya.filename` UNIQUE (`/output/{filename}` sorgusu); `medya.duration int`
(storage `int(...)` yazıyor). **Bekçiler** (`tests/test_tablolar.py`, 16 test):
`IS_TABLOLARI` ↔ belgenin "İş tabloları, envanterden birebir:" cümlesi ↔
`Base.metadata` üç küme eşit; yedi iş tablosunda `kullanici_id NOT NULL` +
CASCADE FK + önde `kullanici_id` olan indeks/PK; beş liste tablosunda
`(kullanici_id, olusturuldu)` + `id` CHECK'i; `ID_KALIBI` beş deponun
`_SAFE_ID`siyle birebir; her CHECK'in İZİNLİ HER değeri gerçekten yazılıyor —
`alembic check` CHECK kısıtlarını karşılaştırmadığı için `ALLOWED_THEMES`e
eklenen tema aksi hâlde sessizce göçsüz kalırdı; citext benzersizliği
(`Ali@…` = `ali@…`), kullanıcı silme yedi tabloyu boşaltıyor, klasör silme
görseli köke düşürüyor, JSONB gidiş-dönüş + `->` operatörü, `guncellendi`
ilerliyor, downgrade tablo VE uzantı bırakmıyor. `tests/test_db.py` head
literali tek yerde (`BAS`), `tests/test_i18n.py` `services/tablolar.py`yi
"konuşmayan" saydı. Rota sayısı 46 DEĞİŞMEDİ. `alembic/env.py` artık
`tablolar.Base.metadata` okuyor, yani `alembic` komutu `models`/`catalog`ı
yüklüyor (CHECK değer kümeleri oradan) — kabul edilen bedel. README'ye göç
üretme adımı yazıldı.

---

## 3. Hesap: kayıt, giriş, e-posta doğrulama, parola sıfırlama, oturum çerezi ✅ (PR: `faz1/hesap`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Sekiz rota birebir
(`routers/hesap.py`): `POST /api/hesap/{kayit,dogrula,giris,cikis,sifirla,
sifirla/dogrula}`, `GET /api/hesap/ben`, `GET /giris`; rota sayısı **46 → 54**
(`tests/test_app_bolme.py`). Hesap mantığı `services/hesap.py` (parola,
oturum, jeton, sayaç — kullanıcıya konuşmaz), kapı `services/kimlik.py`
(`aktif_kullanici`: bağımlılık, 401 JSON), çerez kararı `services/cerez.py`,
köken kapısı `services/koken.py`, posta `services/posta.py`, sayfa yerleştirme
`services/sablon.py` (yeni: `routers/kok.py`nin `index` gövdesi buraya taşındı —
router'lar birbirini ithal edemez, `/giris` aynı işi istedi). **Sayılar:**
parola argon2id (`pwdlib[argon2]==0.3.*`, 8-128, `models.PAROLA_EN_AZ/EN_COK`);
oturum `kromis_oturum` `HttpOnly; SameSite=Lax; Path=/; Max-Age=30 gün`, kayan
ömür `son_gorulme` 5 dk çözünürlükle (ilerlediğinde çerez de yeniden yazılır —
bağımlılık `response: Response` alıyor); doğrulama jetonu **24 sa**, sıfırlama
**1 sa** (belgede sayı yoktu), ikisi de tek kullanım (`kullanildi_at`) ve aynı
amaçlı yeni jeton eskileri siler; hız sınırı e-posta 10 / IP 30 (15 dk, yalnız
başarısız giriş), kayıt ve sıfırlama isteği IP 5 (1 sa) — bunun için
`giris_denemeleri`ne `tur text NOT NULL DEFAULT 'giris'` + CHECK sütunu geldi
(göç **`0002_deneme_turu`**, head değişti): tek sayaçta beş yanlış parola
"parolamı unuttum"u da kilitlerdi. `Retry-After` pencere içindeki en eski
denemenin çıkışına kalan saniye. Başarılı giriş o e-postanın sayacını siler.

**Kararlar, belgenin açık bıraktığı ya da düzelttiği yerlerde:** (a) `Secure`
bayrağı — öntanımlı "web modu" (`DATABASE_URL` var) ise AÇIK, dondurulmuş
kabukta (loopback http, WKWebView/Safari Secure çerezi saklamaz) KAPALI; env
`KROMIS_GUVENLI_CEREZ` ezer, `compose.yaml` `0` verir (Safari `localhost`ta
bile saklamıyor). Dil çerezi de aynı karardan okuyor. E2E `http://127.0.0.1`de
bayrağı GEVŞETMEDEN geçiyor: Chromium loopback'i güvenilir sayıyor (ölçüldü;
Playwright'ın kendi `page.request` katmanı saymıyor, test bu yüzden sayfanın
içinden `fetch` ediyor). (b) Köken kapısı `Sec-Fetch-Site` → `Origin` →
`Referer` sırasıyla; ÜÇÜ DE YOKSA GEÇER — CSRF tarayıcı saldırısı, üç başlıksız
istemci kurbanın çerezini taşıyamaz; aksi 178 `TestClient` çağrısını ve `curl`ü
kırardı. `same-site` geçmez. 403 gövdesi KOD (`cross_origin_rejected`): ara
katman dilden ÖNCE koşuyor (köken → dil → rota, `app.py`). `KROMIS_KOKEN` hem
izin listesi hem e-posta bağlantı tabanı; yoksa isteğin kendi kökeni. (c)
Başarısız girişin 401'i ve doğrulanmamış hesabın 403'ü `JSONResponse`,
`HTTPException` DEĞİL: `db.oturum` istisnada rollback yapıyor, deneme kaydı
(ve 403'te yeni jeton) geri alınırdı — 11. deneme hiç 429 vermezdi; bekçisi
`test_the_login_route_persists_the_failure_it_reports`. (d) Numaralandırma:
kayıt üç dalda da `{"ok": true}` ve üçünde de bir argon2 + bir posta çağrısı
(doğrulanmış adrese "zaten hesabın var" iletisi — hem süre eşit hem sahibi
bilgilendirir); giriş yanlış parola/bilinmeyen adres aynı 401 aynı sürede
(`parola_dogru` sahte özete karşı da doğrular); sıfırlama bilinmeyen adrese
ileti göndermez — gövde aynı, süre farkı posta sağlayıcısının gecikmesi kadar
(bilinen, kabul edilen sınır). (e) Doğrulanmamış hesaba giriş (doğru parola)
403 + doğrulama iletisini YENİDEN gönderir — ayrı "yeniden gönder" rotası yok;
yeniden KAYIT da doğrulanmamış hesabın parolasını bu isteğinkiyle yeniler
(sahiplik henüz kimsede değil). Sıfırlama adresi kanıtladığı için hesabı da
doğrulanmış işaretler ve BÜTÜN oturumları düşürür. (f) `pydantic` `EmailStr`
YOK (`email-validator` bağımlılığı): `x@y.z` biçimi + 254; adresin varlığını
zaten ileti kanıtlar. `parola` ve `jeton` `services/redaksiyon.py`nin gizli
alan kümesine girdi — 422 gövdesine parola sızmasın. (g) Posta seçimi:
`KROMIS_POSTA` açık; yoksa `RESEND_API_KEY` doluysa `resend`, değilse `konsol`.
`resend` deyip anahtarı unutan `BozukPostaci` alır: her gönderim 503 +
`hata.log`, uygulama açılır ama "gönderdik" yalanı yok. Konsol iletiyi
`posta.log`a (data_dir, `.gitignore`da) ve `app.state.postaci.son`a yazar —
belgenin `app.state.son_posta`sı bu; postacı `app.state.postaci`da, lifespan
kurar/kapatır. İleti dili: kayıtta isteğin dili (ve `kullanicilar.dil`e
yazılır — zincirin 3. halkası 4. görevde okunur), sıfırlamada kullanıcının
kayıtlı dili. Şablonlar düz metin, `posta.*` anahtarları. (h) Ön yüz:
`static/giris.{html,js,css}` — üç sekme + bağlantıdan açılan "yeni parola"
formu; `giris.js` IIFE (eslint her betiğe ötekilerin adlarını küresel veriyor,
üst düzey `$` `no-redeclare`a düşerdi), `tests/test_id_contract.py`de
gerekçeli `KAPSAM_DISI`, id bağları `tests/test_hesap.py`de. `?dogrula=`/
`?sifirla=` parametresi POST'a çevrilip `history.replaceState` ile silinir.
`style.css` yüklenmez (stüdyo yerleşimi), yalnız `flow-tokens.css` + kendi
stili. `index.html`e DOKUNULMADI; `settings.js` "Hakkında" bölmesine DİNAMİK
satır ekliyor (`GET /api/hesap/ben` → e-posta + "Çıkış yap", 401'de `/giris`
bağlantısı, 503/ağ hatasında hiç). **`core.js`nin 401'de `/giris`e
yönlendirmesi BU PR'DA YOK ve bilerek:** öteki 44 rota henüz kapının arkasında
değil, stüdyo oturumsuz çalışıyor ve E2E takımı onu öyle sınıyor; yönlendirme
kapıyla birlikte 4. görevde. (i) `.env.example`e beş değişken (`KROMIS_KOKEN`,
`KROMIS_POSTA`, `KROMIS_POSTA_GONDEREN`, `RESEND_API_KEY`, `KROMIS_GUVENLI_CEREZ`),
bekçi adları KAYNAKTAN okuyor (`koken.KOKEN_ENV` …). `pwdlib` 0.3.1 /
argon2-cffi 25.1.0 / bindings 21.2.0 (`cp36-abi3`) / cffi 2.1.1 cp314 tekerleği
PyPI'dan `--python-version 3.14` ile indirildi.

**Testler:** `tests/test_hesap.py` (40: kayıt-doğrula-giriş-ben-çıkış; jeton
tek kullanım ve süreli; yanlış parola = bilinmeyen adres; doğrulanmamış 403 +
yeniden ileti; çerez bayrakları; kayan ömür 4 dk / 6 dk; süresi dolan oturum;
11. giriş 429 + `Retry-After`, IP 30, başarı sayacı siler; kayıt/sıfırlama IP
5; yeniden kayıt iki dalı; citext; sıfırlama akışı, çapraz jeton, bilinmeyen
adres, doğrulanmamış hesap, ileti dili; 422 metinleri ve parola sızıntısı;
posta hatası 503 + rollback; `Secure` kararı ve compose kapatması; rota
envanteri = belgenin 8'i; `/giris` çevrili, yalnız iki betik; id bağları),
`tests/test_koken.py` (24), `tests/test_posta.py` (22, Resend `MockTransport`,
ağ yok), `tests/test_playwright_hesap.py` (E2E ×2 dil: form → konsol posta →
bağlantı → giriş → stüdyo → Ayarlar'dan çıkış), `tests/test_tablolar.py` +
`tur` CHECK'i, `tests/test_db.py` head `0002_deneme_turu`; `test_i18n.py`
şablon taraması artık `static/*.html`, `test_telif_basligi.py` de. Graf
üretici `static/*.html`in her birinin yükleme sırasını okuyor
(`onyuz.sayfalar`, "Öteki sayfalar" bölümü) ve README'ye ara katmanların
haritada görünmediği yazıldı. Tam takım (E2E + Postgres zorunlu):
**3.160 geçti, 12 atlandı, 134 sn** (taban 3.051 / 12 / 110 sn; E2E koştu, DB atlaması 0). ruff, mypy, eslint, prettier temiz.
**4. göreve kalan:** 44 rotaya `Depends(kimlik.aktif_kullanici)`, `GET /`nin
302'si, `core.js` 401 → `/giris`, dil zincirinin 3. halkası `kullanicilar.dil`,
autouse `kullanici` fixture'ı; bu PR hiçbir mevcut rotayı kapının arkasına
almadı.

---

## 3b. Google ile giriş (opsiyonel) — OIDC, sahibin Google Cloud istemcisiyle (PR: `faz1/google-giris`)

**Kapsam.** Sahibin 2026-09-17 kararı: "Faz 1 içinde, UCUZSA". Ucuz olan
yol OIDC'nin standart akışı, SDK'sız: `GET /api/hesap/google` (durum +
PKCE üretir, çerezde tutar, `accounts.google.com/o/oauth2/v2/auth`a 302) ve
`GET /api/hesap/google/geri` (kod → `oauth2.googleapis.com/token` `httpx`
ile, `id_token` doğrulaması Google'ın JWKS'iyle — `authlib==1.6.*` bunu
hazır verir ve `httpx` istemcisiyle çalışır; elle JWT doğrulaması YAZILMAZ,
imza/`aud`/`iss`/`exp` denetimi bir kütüphanenin işidir). Doğrulanmış
`email` + `sub` ile hesap: e-posta `kullanicilar`da varsa o kullanıcı
(Google `email_verified:true` ise parola hesabına bağlanır — hesap ele
geçirme yolu YOK, çünkü Google adresin sahibini doğruladı), yoksa
`parola_ozeti NULL` ve `dogrulandi_at = now` ile yeni satır; sonra 3.
görevin AYNI oturum çerezi (`kromis_oturum`) — Google jetonu saklanmaz,
yenilenmez, yalnız kimlik için bir kez kullanılır. `kullanicilar`a
`google_sub text UNIQUE NULL` sütunu (küçük göç `0002_google_sub`).
`static/giris.html`e "Google ile devam et" düğmesi (yalnız
`KROMIS_GOOGLE_ISTEMCI_ID` verilmişse görünür — `GET /api/hesap/ben`in yanına
`GET /api/hesap/saglayicilar` `{"google": bool}`). Sahibin işi: Google Cloud
projesinde OAuth istemcisi (web uygulaması türü), yetkili yönlendirme adresi
`https://<alan>/api/hesap/google/geri` (yerelde `http://localhost:8765/…`),
istemci kimliği + gizli anahtar → `KROMIS_GOOGLE_ISTEMCI_ID`,
`KROMIS_GOOGLE_ISTEMCI_SIRRI` (`.env.example`e açıklamalı, bekçi aynı).

**Dokunulan.** `routers/hesap.py` (+2 rota, 54 → 56; `tests/test_app_bolme.py`),
`services/kimlik.py` (Google kimliğinden kullanıcı bulma/açma), yeni
`services/google_oidc.py`, `alembic/versions/0002_google_sub.py`,
`static/giris.{html,js}`, `bundled/i18n/{tr,en}.json` (+3 anahtar),
`requirements.txt` (`authlib==1.6.*`), `.env.example`, yeni
`tests/test_google_giris.py` (sahte Google: `httpx.MockTransport` ile token
ucu + kendi ürettiğimiz JWKS/`id_token`; durum uyuşmazlığı 400; doğrulanmamış
e-posta bağlanmaz; var olan hesaba bağlanma; yeni hesap açılışı; sırlar
`GET /api/settings`e sızmaz), `docs/graflar/*`.

**Risk.** Orta: dış bağımlılık (Google Cloud projesi, yönlendirme adresi
alan adına bağlı — alan adı Faz 5'te kesinleşiyor, yerelde `localhost`)
ve kimlik yüzeyi. Küçültme: standart OIDC + hazır doğrulayıcı, PKCE, tek
kullanımlık `state`, jeton saklanmıyor, e-posta ile hesap birleştirme
YALNIZ `email_verified`. Ucuz değilse (authlib 3.14 tekerleği sorun çıkarır,
Google istemcisi gecikir) Faz 5'e ertelenir — 3. görev bundan bağımsız.

**Çıkış ölçütü.** Yerelde gerçek bir Google hesabıyla `/giris` → Google →
geri → `/` açılıyor ve `GET /api/hesap/ben` aynı kullanıcıyı veriyor; aynı
e-postanın parola hesabıyla Google hesabı TEK satır; `KROMIS_GOOGLE_*` yokken
düğme yok ve rotalar 404; takım yeşil.

---

## 4. İstek bağlamı: `services/kimlik.py` kapısı, kullanıcı başına `Ayarlar`, dil zinciri ✅ (PR: `faz1/istek-baglami`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Kapı **47 rota**: 44
stüdyo + `GET /` (302) + `GET /api/hesap/ben` + `POST /api/hesap/cikis`; açık
**7**: `GET /health`, `GET /giris`, `POST /api/hesap/{kayit,dogrula,giris,
sifirla,sifirla/dogrula}` — liste `tests/test_kimlik.py::ACIK_ROTALAR`da
GEREKÇESİYLE, bekçisi her rotanın YA kapılı YA listede olduğunu sınıyor (54 =
47 + 7; CLAUDE.md §5 deyimi). Rota sayısı 54 DEĞİŞMEDİ, `index.html`e
dokunulmadı. Belgenin "44 imzaya `Depends(kimlik.aktif_kullanici)`" cümlesi
DAHA KISA bir yoldan karşılandı: `ayar.ayarlar(request, kullanici =
Depends(kimlik.aktif_kullanici))` — ayar nesnesi kullanıcıya göre kurulduğu
için kapı onun İÇİNDE, yani `Depends(ayar.ayarlar)` yazan 42 rota tek satır
eklenmeden kapılı ve "dizin isteyen rota kimin dizinini istediğini söyler";
dizin okumayan iki rota (`POST /api/settings`, `POST /api/palette/suggest`)
kapıyı doğrudan alıyor. Bunun bedeli ikinci bir ayar bağımlılığı: **`ayar.genel`**
(paylaşılan `app.state.ayarlar`, oturum istemez) — `/health`, `/giris`, hesap
rotaları (kayıt olmadan kullanıcı dizini yok) ve `GET /` (yalnız `static_dir`)
onu alıyor; bekçi test kapılı bir rotanın `genel`i, açık bir rotanın
`ayarlar`ı almadığını sınıyor. `Ayarlar`a alan EKLENMEDİ (4 dize):
`kullanici_icin(id)` → `<data_dir>/kullanicilar/<uuid>/{output,assets}`
(`str(uuid)`, tireli — `GET /api/hesap/ben`in `id`siyle aynı yazım),
`data_dir`/`static_dir` aynı; kullanıcı kökü **0o700**, ilk istekte açılır,
süreç başına bir kez (`_acilanlar`); `paths.ensure_data_dirs` DEĞİL — o eski ad
göçünü de koşturuyor. `GET /`nin 302'si `kimlik.sayfa_kullanicisi` + `GirisSayfasi`
istisnası + `app.py`de işleyici (`RedirectResponse`, `no-store`); `?sonra=` YOK
(belge "302 `/giris`" diyor, tek sayfa `/`). Ön yüz: `core.js` `window.fetch`i
TEK noktadan sarıyor (35 çağrı yerine tek kapı), 401'de `/giris?sonra=<yol>`;
`giris.js` `sonra`yı yalnız `/` ile başlayan, `//` ile başlamayan, ters bölü
taşımayan bir yolsa kullanıyor (açık yönlendirici değil; E2E beş girdiyle).

**Dil zinciri:** 3. halka `kullanicilar.dil`, `services/tercih.py` web yolundan
ÇIKTI (modül dondurulmuş kabuk için duruyor, birim testleri `test_dil.py`nin
sonunda; kararı 6. görevde). Halka ara katmanda DEĞİL kapıda uygulanıyor
(`kimlik.bagla` → `dil.kullanici_dili`): ara katman kullanıcıyı sorgulasa ikinci
bir `Session` ve ayrılmış bir `Kullanici` gerekirdi; kapı zaten tek sorguyla
getiriyor (ek sorgu SIFIR — `test_resolving_the_user_costs_exactly_one_query_per_request`
`before_cursor_execute` sayıyor: `/api/history` ve `/` 1 sorgu). Bunun için
`aktif_kullanici` **`async def`** oldu: `i18n._AKTIF` bir `ContextVar` ve
FastAPI senkron bağımlılığı havuzda KOPYA bağlamla koşturuyor — orada yapılan
`set_active` rotaya ulaşmıyor (ölçüldü); DB sorgusu `run_in_threadpool` ile.
Ara katman 1-2. halkanın konuştuğunu `request.state.dil_acik`a yazıyor, kapı
yalnız o susmuşsa hesabın dilini uygular. `POST /api/prefs` `language` →
çerez + `kullanici.dil` (kapının çözdüğü, isteğin `Session`ına bağlı satır;
commit `db.oturum`da) + `prefs.json` (hâlâ; 6. görev taşır). Kapıdan ÖNCE
üretilen cevaplar (köken 403 — kod; oturumsuz 401) hesabın dilini görmez, 422
görür (alt bağımlılıklar gövde doğrulamasından önce).

**Testler:** conftest autouse **`kullanici`**: üç `dependency_overrides`
(`aktif_kullanici`, `sayfa_kullanicisi` → geçici `Kullanici`, `kimlik.bagla`
üzerinden — 3. halka orada da işler; `ayar.ayarlar` → paylaşılan yerleşim,
üretimdeki gibi kapıya bağımlı) — 37 dosyanın 178 `TestClient` çağrısı ve
`test_index`in 4 `c.get("/")`ü DEĞİŞMEDİ. Opt-out `@pytest.mark.gercek_kimlik`
(pyproject'te kayıtlı): `test_hesap.py`, yeni `test_kimlik.py`, dört
`test_playwright_*.py`. Yeni `tests/test_kimlik.py` (59: açık liste bekçisi,
302-yalnız-`/`, `genel`/`ayarlar` yer bekçisi, 47 kapılı rotanın her biri
çerezsiz 401 + i18n `detail` ×2 dil, sahte çerez, `/` 302 → `/giris` 200 →
oturumla 200, iki kullanıcı iki dizin + medya/indirme/silme 404 + 0o700 +
paylaşılan `output/` hiç açılmadı, tek sorgu, dil DB'den ve `prefs.json`
okunmuyor, `POST /api/prefs` DB'ye yazıyor / 422 yazmıyor, `bagla` birimi,
DB'siz 503). `test_dil.py` zinciri hesabın diliyle yeniden (40; `coz` beş halka tablosu; "20 istekte ≤1
okuma" → "0 okuma": `read_stored`/`tercih.dil` yamayla patlatılıyor).
`test_app_bolme.py` `ayar.genel`i tanıyor; `test_i18n.py`nin rota-hatası-dil testi hesabın diliyle. E2E: `e2e_oturum` fixture'ı
(conftest) DB'ye doğrulanmış kullanıcı + oturum yazıp `context.add_cookies` ile
çerezi koyuyor, `data_dir`i `tmp_path`e çekiyor (dev'de `data_dir` repo kökü —
`kullanicilar/` `.gitignore`a girdi); 18 stüdyo/dil/güncelleme testi çerezle
koşuyor, dosya tohumlayan üçü kullanıcının `oturum.ayarlar().output_dir`ine
yazıyor; `test_playwright_dil` dili `prefs` yamasıyla değil `e2e_oturum(dil=…)`
ile kuruyor. Yeni E2E: `/giris?sonra=` × 5 (aynı köken aynen; `//`, `https://`,
ters bölü, göreli → `/`) + çerez silinince `fetch` 401 → `/giris?sonra=<yol>`.
**E2E süresi:** 20 test 68,9 sn (main) → 25 test **78,2 sn** (bu dal, aynı
makine, dört dosya tek koşu): +9,3 sn'nin 8,7'si yeni `sonra` testinin beş
parametresi (her biri kendi sunucusu + tarayıcısı, ~1,7 sn); çerezle koşan 20
eski teste düşen pay ≈ **+0,6 sn** — DB kopyası + kullanıcı/oturum satırı test
başına ~30 ms. Tam takım (E2E + Postgres
zorunlu): **3.229 geçti, 12 atlandı, 149 sn** (taban 3.160 / 12 / 134 sn; E2E koştu, DB atlaması 0). ruff, mypy, eslint, prettier
temiz; graflar güncel. Canlı doğrulama (geçici küme + uvicorn + curl): `GET /`
302 `/giris`; `GET /api/history` 401 `{"detail":"You need to sign in for this."}`;
`/giris` ve `/health` 200; iki hesap kayıt → `posta.log` → doğrula → giriş; A
`/api/history` 200, `/` 200; B'nin kaydettiği palet A'nın listesinde YOK;
`$DATA/kullanicilar/<A>` ve `<B>` 0o700, `palettes.json` yalnız B'nin
`output/`unda. **Bilinen sonuç:** web sürümü `DATABASE_URL`siz stüdyoyu açmaz
(`oturum` 503 `database_unavailable`) — dondurulmuş kabuk bu dalda hesapsız
çalışmıyor; belge §1'in "veri tabanı olmadan hesap açamaz" kararının doğrudan
sonucu, kabuğun ince WebView'a dönüşü Faz 1 dışı notunda.

---

## 5. Galeri ve klasörler → DB: `medya`, `klasorler` ✅ (PR: `faz1/galeri-db`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** İki depo modülü
**`services/depo_medya.py`** ve **`services/depo_klasor.py`** — belgenin
`services/depo/{medya,klasor}.py` alt paketi DEĞİL, düz ad, ve bilerek:
`tools/graf_uret.py` bugün yalnız tek kademe (`services/<ad>.py`) görüyor
(alt paket 9. görevin listesinde); alt paket açmak haritayı bu PR'da kör
bırakırdı. `storage.py`/`folders.py` DURUYOR (dondurulmuş kabuk +
`tools/ice_aktar.py`); saf yardımcıları (`MEDIA_TYPES`, `ext_for`,
`media_path_of`, `media_type_for`, `valid_id`, `_SAFE_ID`, `safe_component`)
depo modülleri oradan ithal ediyor, kopya yok; manifest okuyan/yazan 24
işlevin web yolunda (`app.py`, `routers/`, `services/`) ÇAĞRILMAMASI AST
bekçisiyle (`tests/test_galeri_db.py::test_no_web_module_calls_a_manifest_function_of_storage_or_folders`),
`gorsel.output_media_path` (yalnız diske bakan servis yolu) silindi — yerine
`depo_medya.dosya_yolu`/`dosya_yolu_adiyla`: satır VE dosya, biri yoksa 404.
**Rotalar (19 + 12 → hepsi):** `routers/galeri.py` 15 (`/api/folders` ×5,
`/api/history`, `/api/image/{id}` PATCH/DELETE, `/api/images` PATCH/DELETE,
`/api/arena/{id}` GET + `winner`, `/api/import`, `/output/{filename}`,
`/api/output/{id}/download`), `uretim.py` 4 (`generate`, `video`, `animate`,
`edit` — YAZANLAR DÂHİL: dört üretim rotası `depo_medya.kaydet`e yazıyor),
`bindirme.py` 2 (`/api/logo`, `/api/banner`: kaynağın meta'sı `depo_medya.bul`).
Her rota `db: Session = OTURUM` + `kullanici: Kullanici = Depends(kimlik.aktif_kullanici)`
alıyor; ikincisi `ayar.ayarlar`ın içindeki kapıyla AYNI nesne (FastAPI
bağımlılık önbelleği) — ölçüldü: `/api/history` **2 sorgu** (kimlik + `medya`),
`/` 1 (`test_resolving_the_user_costs_exactly_one_query_per_request` 1 → 2'ye
güncellendi). Dosyaya dokunmayan 9 rota (`/api/folders` ×4, `/api/history`,
`/api/image` PATCH, `/api/images` PATCH, `/api/arena` ×2) artık `ayar.ayarlar`
ALMIYOR — `tests/test_kimlik.py::DIZINSIZ_KAPILI` listesi belgenin dört
istisnasını bunlarla genişletti, bekçisi iki yönlü (listedeki alan almaz,
almayan listede). Üç `async def` rota (`edit`, `animate`, `import`) DB'ye
`run_in_threadpool` ile (1. görev kararı). `kapilar.check_folder(folder_id,
db, kullanici_id)`. Rota sayısı **54 DEĞİŞMEDİ**, `index.html`/`static/`
DOKUNULMADI.

**Şema: bir göç geldi — `0003_arena_win`.** Envanter `storage.save`in 12 + 5
alanını saydı; `arena_win`i `save` değil `set_arena_winner` SONRADAN yazıyor
ve liste onu görmedi. `medya.arena_win boolean NULL`, kısıtsız (kısmi UNIQUE
içe aktarılan eski verideki olası çift işareti reddederdi); tur başına tek
kazanan tek `UPDATE … SET arena_win = (id = :kazanan) WHERE arena_id = :tur`
(storage'ın tek-yazım gerekçesi aynen). `head` 0002 → 0003
(`tests/test_db.py::BAS`), ileri-geri-ileri + `alembic check` temiz.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) ZAMAN — `olusturuldu`
`timestamptz` MİKROSANİYELİ, Python'dan (`zaman.an()`), Postgres `now()`
DEĞİL: `/api/generate` n=4 dört satırı aynı transaksiyonda aynı saniyede
yazıyor, `now()` dördüne aynı anı verir ve galeri "en yeni üstte"/arena
"üretim sırası" kaybolurdu (`test_four_records_written_in_the_same_second_keep_their_production_order`).
JSON `created_at` `zaman.damga()` ile eski biçimde birebir (yerel saat,
saniye, dilimsiz — `folders.js` `localeCompare` ile sıralıyor; bekçisi
`test_created_at_keeps_the_manifest_format_to_the_second`). (b) KİMLİK — yeni
satırlar `uuid4().hex` (32 hane, belge §2), dosya adı `{id}{uzantı}`; 12
haneli eski id aynı kapıdan geçiyor (test). (c) ŞEKİL — `_json` dökümü
`storage.save` kaydıyla anahtar SIRASI dâhil eşit, koşullu 5 alan + `arena_win`
yalnız doluysa (NULL/false = anahtar yok); bekçi iki yazıcıyı yan yana koşturup
`list(dict)` eşitliği arıyor. (d) SİLME sözleşmesi korunuyor: satır önce,
dosya sonra; "kaydı olmayan dosya" ve "dosyası olmayan kayıt" ikisi de
silinmiş sayılır; `sil_coklu` satırları tek `DELETE … RETURNING`, dosyaları
tek tek. (e) Klasör silme: `altagac` → `klasorden_cikar` (açık `UPDATE`,
`unfiled` sayısı FK'nın SET NULL yan etkisinden okunamaz) → `agaci_sil` (tek
`DELETE … IN`, aynı transaksiyon). Ağaç yürüyüşü Python'da (`SELECT id,
parent_id` tek sorgu, `folders.depth/descendants`ın ziyaret-kümeli yürüyüşü
birebir — kendi kendinin ebeveyni olan bozuk zincirde 1 döner, CTE `N`
dönerdi). (f) Depo katmanı KONUŞMAZ: `folders.export_zip`in `ValueError(i18n.t)`i
yerine `zip_disa_aktar` `None` döner, 404'ü rota kurar; iki modül
`test_i18n.py`de "konuşmayan". (g) 403 YOK: başkasının kaydı "yok" (404) —
403 id uzayını sızdırır. `jsonstore.lock_for` yok, yarış `UPDATE … WHERE`de.

**Testler.** conftest'e üç fixture: `veritabani_motor` (modül; dosyanın DB'sine
motor), **`depo_db`** (OPT-IN, `pytestmark = pytest.mark.usefixtures("depo_db")`
— autouse `kullanici` fixture'ı bunu görünce test kullanıcısını GERÇEK satır
yazar [önceki silinir, CASCADE önceki testin verisini götürür, e-posta sabit]
ve dördüncü override `db.oturum`u o motora bağlar: 178 `TestClient(app)` çağrısı
`with`siz kalır; `veritabani`yi doğrudan isteyen `test_db/health/tablolar`a
sızmaz), `db_oturumu` (tohum yazan testlerin `Session`ı); `E2EOturum.db()`.
14 rota test dosyası `depo_db`ye alındı (`test_folders/arena/app/delete_route/
edit_route/video_route/logo/banner/import_route/model_secimi/palette_route/
guvenlik_baslik/legacy_formats/i18n`), iki tekil test işaretle (`test_dil`,
`test_app_bolme`). `test_folders.py`nin manifest dosyası yazan 3 testi DB
tohumuyla yeniden yazıldı, biri (`corrupt folders.json`) yerini "web yolu
manifest dosyası HİÇ açmaz" bekçisine bıraktı; `storage`/`folders`ün saf birim
testleri (aynı dosyada 5, `test_storage*.py`, `test_arena.py`nin depo testleri)
dondurulmuş kabuk için AYNEN duruyor. `test_legacy_formats.py`: (ii) tüketici
testleri v1.8 fixture'ını içe aktarma aracının deseniyle DB'ye tohumluyor
(`_db_tohumla`: `.get()`, eksik anahtar NULL, 12 haneli id, liste sırası),
(i) ailesine iki DB ikizi (satır dökümü v1.8 anahtarlarını taşır, sıra eşit).
Yeni **`tests/test_galeri_db.py`** (16): AST bekçileri (manifest çağrısı yok;
sorgu kuran her depo işlevi `kullanici_id` alır VE süzgece koyar; imza
`(db, kullanici_id, …)`), iki kullanıcı depo düzeyinde 20 işlevde izole, şekil
eşitliği ×2, `created_at` biçimi, ağaç silme SET NULL/CASCADE, satır+dosya
silme sözleşmesi, toplu silme sayımı, servis yolu satır+dosya ister,
mikrosaniye sırası, arena kazananı, 12/32 haneli id. `test_kimlik.py`nin iki
kullanıcı testi klasör rotalarıyla genişledi (B'ye 10 uçta 404, A'nın verisi
yerinde, manifest dosyası yok). E2E `test_playwright_studio.py` tohumu
`oturum.db()` + depo ile; 4 E2E dosyası DB'li galeriyle geçiyor.
Tam takım (E2E + Postgres zorunlu): **3.255 geçti, 12 atlandı, 164 sn** (taban
3.229 / 12 / 149 sn; E2E koştu, DB atlaması 0). ruff, mypy (193 dosya), eslint,
prettier temiz; graflar güncel (76 modül, 54 uç, 107 test dosyası). Canlı
doğrulama (geçici küme + `alembic upgrade head` → `0003_arena_win` + uvicorn +
curl, iki hesap): A klasör açar + `/api/import` → `count:1`; B `/api/folders`
`[]`, `/api/history` `[]`, A'nın klasörüne `?folder_id=`/PATCH/download/DELETE
ve A'nın görseline `/output/…`/DELETE **404**; B kendi klasörünü açar, A onu
görmez; A klasörünü siler → `{"deleted":[…],"folders":1,"unfiled":1}`, görsel
kökte; DB'de `a: 1 medya/0 klasör`, `b: 0/1`; diskte yalnız
`kullanicilar/<A>/output/<id>.png` — `history.json`/`folders.json` yok.

**6. göreve kalan:** `palette_store`/`assets_store`/`chat_store`/`prefs`
diskte (üretim rotaları `palet.palette_prompt(output_dir=…)`i hâlâ dizinle
çağırıyor); dizin okumayan rotalar listesi (`DIZINSIZ_KAPILI`) o görevde
büyür. **8. göreve not:** `arena_win` de göçecek alan (envanter dışıydı);
`_db_tohumla`nın deseni (eksik anahtar NULL, liste sırası → `olusturuldu`
sırası, 12 haneli id korunur) aracın iskeleti. **9. göreve borç:** dosya +
satır atomik değil — `kaydet` satır düşerse dosya artık kalır, `tools/artik_dosya.py`.

---

## 6. Sohbet, palet, varlık, tercih → DB; `backup.py` web yolundan çıkar ✅ (PR: `faz1/sohbet-palet-varlik-db`)

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

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Dört depo modülü DÜZ ADLA
(5. görevin kararı, `tools/graf_uret.py` tek kademe görüyor): **`services/depo_sohbet.py`**
(`olustur/listele/bul/guncelle/sil/hepsini_sil`), **`depo_palet.py`**
(`olustur/listele/bul/sil`), **`depo_varlik.py`** (`kaydet/listele/dosya_yolu/
dosya_yolu_adiyla/sil`), **`depo_tercih.py`** (`oku/kayitli/guncelle`) — hepsi
`(db, kullanici_id, …)`, her sorguda sahip süzgeci, başkasının kaydı 404 (bekçi
`tests/test_galeri_db.py`, altı depoya genişledi; diskteki `depo_*.py` listesi
ile birebir). Dondurulmuş dört depo (`chat_store`/`palette_store`/`assets_store`/
`prefs`) DURUYOR; saf yardımcıları ithal ediliyor, kopya yok: `chat_store.valid_id`/
`cover_from`, `palette_store._SAFE_ID`, `assets_store.KINDS`/`_SAFE_ID`,
**`prefs._SCHEMA`/`_ENUMS`** (tercih şeması TEK kaynak — `GET /api/prefs`in
anahtar kümesi/sırası `prefs.DEFAULTS` ile birebir, `test_prefs_route`in
`PrefsRequest ⊇ _SCHEMA` bekçisi aynı kaynağa bakıyor). Manifest okuyan/yazan
işlevleri (`create/list_*/get/update/delete/…`, `save_asset/asset_path/
migrate_legacy_uploads/…`, `read/read_stored/update`) web yolunda ÇAĞRILMAZ —
AST bekçisi `MANIFEST_ISLEVLERI` dört modülle genişledi. **Rotalar (10 + 5 +
9 + 9 → hepsi, 54 DEĞİŞMEDİ):** `routers/sohbet.py` 7 (`/api/chat` + 6 sohbet
rotası), `paletler.py` 3, `ayarlar.py` 5 (`/api/settings` GET, `/api/guncelleme`
GET/POST, `/api/prefs` GET/POST), `bindirme.py` 9 (4 varlık rotası + 2 önizleme
+ 2 bindirme + `/assets/{kind}/{filename}`); `uretim.py` 2 (`palette_prompt`in
`db=, kullanici_id=` anahtar sözcükleri). `services/palet.saved_palette(db,
kullanici_id, palette_id)`, `services/modeller.director_context(db, kullanici_id)`.
Dizin okumayan 17 rota daha `ayar.ayarlar` almıyor (`DIZINSIZ_KAPILI` 13 → 30:
`/api/chat`, sohbet ×6, palet ×3, `/api/prefs` ×2, `GET /api/assets/{kind}`);
üç güncelleme rotası ve dosyaya dokunan varlık/bindirme rotaları ayar nesnesini
sürdürüyor. `services/tercih.py` SİLİNDİ; `backup` ve `assets_store` `app.py`den
çıktı (`migrate_legacy_uploads` da: manifest okuyan tek yol içe aktarma aracı,
bekçisi `test_assets_route.py::test_startup_leaves_a_legacy_uploads_directory_alone`);
conftest'in `_guard_against_real_backups` fixture'ı gerekçesiyle kaldırıldı
(yamalanacak çağrı kalmadı; `test_backup.py`nin 4 lifespan testi → 2: "app.py
`backup`ı ithal etmez" AST bekçisi ve "açılış adımı patlasa da uygulama
açılır" — birim testleri 13, dosya 15).

**Şema: göç GELMEDİ.** Dört yazıcının (`chat_store.create`, `palette_store.create`,
`assets_store.save_asset`, `prefs.update`) her alanı 2. görevin tablolarında
karşılığını buldu (`cover_image_id` türetilir, sütun değil); `head` `0003_arena_win`.

**Kararlar, belgenin açık bıraktığı yerlerde:** (a) ZAMAN 5. görevle aynı —
`olusturuldu`/`guncellendi` Python'dan (`zaman.an()`, mikrosaniyeli), JSON
`created_at`/`updated_at` `zaman.damga()` ile eski biçimde; `depo_sohbet.guncelle`
`guncellendi`yi AÇIKÇA yazıyor (ORM `onupdate=now()` Postgres saatini yazardı,
iki saat ayrışırdı); boş güncelleme (`messages`/`title` yok) satıra dokunmaz
(`chat_store.update`in gerekçesi). Sıra `guncellendi DESC, olusturuldu DESC`.
(b) ŞEKİL — dört dökümün üst düzey anahtar SIRASI eski yazıcılarla birebir
(bekçiler `list(dict)` eşitliği); `messages`/`colors` içindeki SÖZLÜKLERİN
anahtar sırası JSONB'nin (Postgres nesne anahtarlarını kendi sırasında saklar)
— ön yüz alanları adıyla okuyor, dizinin sırası korunuyor; 5. görevin `palette`
JSONB'siyle aynı durum. (c) VARLIK servis yolu `/output/{filename}` kararına
hizalandı: `/assets/{kind}/{filename}` ve bindirme (`_composite_logo`,
`_banner_asset_path`) artık SATIR VE dosya ister — `assets_store.asset_path`in
"yalnız diske bak" kuralı web'de yok; satırı olmayan `index.json`/artık dosya
404. Önizleme rotaları bu yüzden `Session` alıyor (diske yazmıyorlar, varlığı
DB'den buluyorlar). (d) TERCİH deposu KONUŞMAZ: `prefs.update`in `ValueError(i18n.t)`
yerine `GecersizTercih(kod, **alanlar)` — cümleyi rota `i18n.t(e.kod, dil.aktif(),
**e.alanlar)` ile kurar; reddettiği küme `prefs.update`inkiyle bir (parite
testi, dört i18n anahtarı). Bayat `image_model` DB'de durur (CHECK yok), `oku`
varsayılana düşer, satır düzeltilmez — `prefs.read`in yan etkisizlik sözü.
(e) `guncelleme.json` YERİNDE (kullanıcının `output_dir`i, 4. görevden beri):
belge "diskte kalır" dedi, taşıma/kapatma 9. görevin; yalnız `izin` DB'den.
(f) `/api/logo/preview`, `/api/banner/preview`, `/api/settings` ve güncelleme
rotaları ilk kez `kimlik.aktif_kullanici`yi DOĞRUDAN alıyor (ayar nesnesinin
yanında) — kapı sayısı 47 değişmedi, FastAPI önbelleği aynı nesneyi veriyor.

**Testler.** Yeni **`tests/test_sohbet_db.py`** (9), **`test_palet_db.py`** (6),
**`test_varlik_db.py`** (9), **`test_tercih_db.py`** (11): şekil eşitliği eski
yazıcıyla (sıra dâhil), özet alanları `_SUMMARY_FIELDS` ile bir, damga biçimi,
sıra, boş güncelleme, dondurulmuş `colors` (ad çözücü yamalanınca bile aynı),
dosya yerleşimi + manifest yok, geçersiz tür ne diske ne DB'ye (CHECK `uploads`u
reddediyor), satır+dosya silme sözleşmesi, NULL = hiç yazılmamış / varsayılana
eşit yazılmış ayrımı, red paritesi, bayat model, iki kullanıcı depo düzeyinde
izole, hesap silinince CASCADE, 12/32 haneli id. Rota dosyaları `depo_db`ye
alındı ve depodan doğruluyor: `test_chats_route` (`depo_sohbet.bul`, `chats.json`
yok), `test_palette_route` (bozuk palet SATIRI tohumu; "bozuk `palettes.json`"
testi "dosya HİÇ okunmaz"a döndü), `test_assets_route` (`index.json`
sunulmaz/yazılmaz; lifespan göçü çağırmaz), `test_prefs_route`, `test_chat_route`
(bozuk `prefs.json` testi "dosya okunmaz"a döndü; tripwire `director_context(db,
kullanici.id)`), `test_settings_route`, `test_guncelleme_route`, `test_logo`/
`test_banner`/`test_playwright_studio` (varlık tohumu `depo_varlik.kaydet`),
`test_arena_onyuz`/`test_provider_logos` (`/api/settings` tek test), `test_dil`
(modül `depo_db`; `tercih` testleri gitti; "≤1 okuma" → `prefs.read_stored` VE
`depo_tercih.kayitli` patlatılıyor: dil zinciri tercihe hiç bakmaz),
`test_chat_prompt`. `test_legacy_formats.py`: `_db_tohumla` palet + varlık
tohumluyor, (i) ailesine iki DB ikizi daha. `test_kimlik.py`: `DIZINSIZ_KAPILI`
+17, iki kullanıcı testi sohbet/palet/varlık/tercihle (B'ye 9 uçta 404, A'nın
dizininde dört manifest yok), sorgu sayımı `GET /api/prefs` 2 (kimlik + tercih)
ve `/` 1 (tercih için 0 ek sorgu). `test_i18n`: dört depo `KULLANICIYA_KONUSMAYAN`da,
`services/tercih.py` listeden çıktı. Eski depo testleri (`test_chat_store` 30,
`test_palette_store` 14, `test_assets` 17, `test_prefs` 27) AYNEN duruyor.

**7. göreve kalan:** `/api/settings`in kimlik dosyası (`credentials.env`) —
`post_settings` hâlâ `ac.save_env`; `credstore.configured_map()` süreç geneli.
**8. göreve not:** `_db_tohumla` artık dört depoyu da tohumluyor (palet
`colors` olduğu gibi, varlık `kind` → `tur`, ölü `uploads` türü `logos`a —
CHECK başka türü reddediyor); eski `prefs.json` → `tercihler`: yalnız
`read_stored`un geçtiği alanlar, gerisi NULL. **9. göreve borç:** `guncelleme.json`
kullanıcı dizininde; DB yedeği; varlık dosya + satır atomik değil (5. görevle
aynı sınıf).

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
* **CI.** ~~`_test.yml`: `services: postgres:17-alpine` + `KROMIS_TEST_DATABASE_URL`;
  `ci.yml` `docker` işi: konteyner artık `DATABASE_URL` ister~~ — İKİSİ DE
  1. GÖREVLE GELDİ (zorunlu oldu: `/health` DB'siz 503 verince `docker` işi
  kırmızıya dönerdi; sonda gevşetilmedi, konteynere Postgres verildi —
  `ci.yml`deki yorum). Burada kalan: `goc` servisi/release command ile
  uyum ve `tests/test_docker_kapisi.py`nin o adımı görmesi.
* **`guncelleme.py` web'de KAPALI** (sahibin 2026-09-17 kararı). GitHub
  Releases denetimi dondurulmuş masaüstü/Android için anlamlı; web'de "yeni
  sürüm var" yanlış pozitif ve dış ağa gereksiz çıkış. `GET /api/guncelleme`
  web yapısında `{"web": true}` döner (`KROMIS_WEB=1` ya da `DATABASE_URL`
  varlığı — tek bayrak, `services/db.py`nin okuduğuyla aynı kaynak), ön yüz
  düğmeyi ve `prefs.guncelleme_kontrolu` anahtarını gizler; `guncelleme.json`
  önbelleği web'de hiç yazılmaz. Modül ve 3 rotası dondurulmuş kabuk için
  DURUR; bekçi test web bayrağıyla ağa çıkılmadığını (sahte `httpx`
  taşıyıcısı çağrılmıyor) sınar.
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
| K2 | Kimlik doğrulama yöntemi | **E-posta + parola (argon2id) + e-posta doğrulama + sıfırlama**; Google ile giriş isteğe bağlı **3b. görev** (Faz 1 içinde, ucuzsa — sahibin 2026-09-17 eki) | Küresel kitle, e-posta evrensel; parola yolu doğrulama e-postasını zaten gerektiriyor, sıfırlama aynı altyapı; OAuth ek bir dış bağımlılık (Google Cloud projesi, redirect URI, gizli anahtar) | Sihirli bağlantı (parolasız): daha az kod ama her giriş e-posta bekler, posta sağlayıcısı kesintisi = giriş kesintisi. OAuth-first: parolasız ama Google'a bağımlı, kurumsal e-postası Google olmayan kullanıcı dışarıda |
| K3 | Oturum vs JWT | **Sunucu oturumu (DB) + HttpOnly SameSite=Lax çerez** | İptal tek `DELETE`; tek köken, jeton taşınacak üçüncü taraf yok; spec'in JWT'si 2026-08'de "ayrı API + mobil" varsayımıyla yazıldı, web-first o varsayımı kaldırdı | JWT: istek başına DB sorgusu yok (biz zaten kullanıcıyı çekiyoruz — dil için), ama kara liste tablosu gerekir; ikisinin toplamı oturum tablosundan fazla |
| K4 | Testte SQLite mi Postgres mi | **Postgres** — CI servis konteyneri, yerelde ikililerden geçici küme, yoksa gürültülü atlama, `KROMIS_E2E_ZORUNLU=1` hata | JSONB/citext/timestamptz/eş zamanlılık SQLite'ta yok; Faz 0'ın "atlanan test = yeşil değil" dersi ölçülü (8/9). Bu makinede Postgres 16.13 ikilileri var ve küme açıldı; Docker imajı çekilemiyor | SQLite: kurulumsuz, ama göç dosyaları iki lehçede yazılır ve Postgres'e özgü kusur yalnız CI'da görünür — Faz 0'ın kırmızılarının aynısı |
| K5 | Medya dosyalarının yeri | **Faz 1'de yerel disk**, `KROMIS_DATA_DIR/kullanicilar/<uuid>/`; S3/R2 **Faz 2** (kuyrukla birlikte) | Worker yok — medyayı yazan hâlâ istek; `FileResponse` çalışıyor; yönetilen platformlarda kalıcı birim var; tek replika kabul. Nesne depolama gelince yazan taraf worker olacak, o zaman tek seferde | R2 şimdi: yol haritası Faz 1'de sayıyor (sapma, aşağıda); bedeli imzalı URL + yükleme akışı + 5 rota daha ve iki kez dokunma (Faz 2'de worker yine değiştirir) |
| K6 | Göçlerin çalıştığı yer | **Platformun dağıtım öncesi komutu** (`tools/goc.py`); konteyner açılışında DEĞİL | İki replika yarışı; yönetilen platformların hepsinde release command var | Açılışta `alembic upgrade`: tek replikada kolay, ölçek çıkınca tuzak; Alembic kilit tutmaz |
| K7 | E-posta sağlayıcısı | **Resend** (API + httpx, EU bölgesi, ücretsiz kademe 3.000/ay, alan adı doğrulaması SPF/DKIM) — DIŞ ve ileride ÜCRETLİ bağımlılık, hesap + DNS kaydı sahibin | Depo zaten httpx; SDK yok; `konsol` arka ucu testleri ağdan bağımsız kılar | Postmark (işlemsel e-postada güvenilirlik, ücretsiz 100/ay), SES (en ucuz, kurulumu en ağır, IAM). SMTP genel arayüz (`smtplib`) ile her sağlayıcı — ama API hata cevapları daha okunur |

**Sahibin kararları (2026-09-17, Slack).** Yedi önerinin yedisi de (K1-K7)
olduğu gibi kabul edildi. İki ek: (a) `guncelleme.py` web yapısında
KAPATILIR — 9. göreve girdi (yukarıda, "`guncelleme.py` web'de KAPALI");
(b) Google ile giriş Faz 1 içinde denenir, UCUZSA — 3b. görev olarak
eklendi, 3'e dayanır, pahalıya çıkarsa Faz 5'e kayar.

Bunlara ek, daha küçük iki soru VARDI ve ikisi de yukarıdaki kararla kapandı:
`guncelleme.py`/`GET /api/guncelleme` web'de kapatılsın mı (öneri "Faz 2'de"
idi, karar: Faz 1 / 9. görev); Google OAuth Faz 1'e girsin mi (öneri "hayır"
idi, karar: isteğe bağlı 3b, ucuzsa).

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
* **Google OAuth** → Faz 1 içinde isteğe bağlı **3b. görev** (sahibin
  2026-09-17 kararı: ucuzsa); pahalıya çıkarsa Faz 5.
* **`chat-instructions.md` / `chat-instructions-video.md` ezmeleri**
  (`paths.py:177`, `chat_prompt.py:63`): web'de kullanıcı sunucu dosyası
  düzenleyemez; `director_guidance` tercihi (DB'de) kullanıcı özelleştirmesini
  karşılıyor. Ezme dosyaları dondurulmuş kabuk için kalır; web'de
  `GET /api/settings`in `chat_instructions_path` alanı (`routers/ayarlar.py:53`)
  anlamsız — Faz 2'de "persona düzenleme" özelliği olur ya da alan düşer.
* **`guncelleme.py` web'de** → KAPALI, 9. görevde (sahibin 2026-09-17
  kararı); modül dondurulmuş kabuk için durur.
* **Ön yüz çerçevesi / ES modül** (Faz 0 / 7 kararı): bu fazda iki statik
  sayfa vanilla; karar Faz 2'nin iş listesi arayüzüyle.
* **Dondurulmuş kabuk testleri** (~190 + bu fazda kalan eski depo testleri
  ~200): silinmez, kabuk ince WebView'a dönüştüğü gün toptan gider.
* **Ölçülmeyen:** sahibin gerçek veri hacmi (bu makinede `output/` boş),
  imaj boyutu (Faz 0 / 8'den devam), yönetilen Postgres'in pooler
  davranışı (RLS notu), Python 3.14 tekerlekleri (CI'da görünür).
