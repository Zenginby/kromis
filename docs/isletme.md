# İşletme: iki süreç tek imaj, dağıtım öncesi göç, üç ayrı yedek, iş saklama, anahtar döndürme, geri yükleme tatbikatı

**Tarih:** 2026-09-17 (Faz 1 / 9) · **Güncelleme:** 2026-09-19 (Faz 2 / 10: § 7-9) ·
**Kime:** web sürümünü işleten kişi ·
**Kurulum adımları:** [KURULUM.md → Web sürümü](../KURULUM.md#web-sürümü-sunucu-kurulumu) ·
**Karar kaydı:** [faz1-veritabani-hesaplar.md § 9](faz1-veritabani-hesaplar.md),
[faz2-kuyruk-anahtarlar-depolama.md § 10](faz2-kuyruk-anahtarlar-depolama.md)

Bu belge kod değil, işletme düzeni. Söylediği şeyler: şema göçü NEREDE koşar
(§ 1), veri NEREDE durur ve nasıl yedeklenir (§ 2-4), bir felakette ne sırayla
geri gelir (§ 5), web ve işçi süreçleri platformda NASIL açılır ve kapanır
(§ 7), kova nasıl kurulur (§ 8), günlük işletme — dağıt, geri al, sağlık,
günlük, uyarı, saklama (§ 9). Bekçisi `tests/test_docker_kapisi.py` (belge
var, üç yedek ayrı, tatbikat adımlı, iki süreç tablosu, saklama).

## 1. Şema göçü — dağıtım ÖNCESİ komut, konteyner açılışı DEĞİL

Uygulama konteyneri (`Dockerfile` CMD) yalnız `uvicorn` koşturur; göç ayrı bir
komuttur ve imajın içinde durur:

```sh
DATABASE_URL=… python tools/goc.py
```

`alembic upgrade head`in ince sarmalayıcısı: bağlantı dizesini uygulamayla aynı
yerden okur (`DATABASE_URL`), göçü koşar, sonda `mevcut <sürüm> (head)` basar.
İdempotent — `head`teyse "zaten head'te" der ve 0 ile çıkar. Çıkış kodları:
0 tamam · 1 göç düştü · 2 ortam (`DATABASE_URL` yok / sunucuya ulaşılamıyor).

NEDEN açılışta değil: iki replika aynı anda açılırsa iki `upgrade` yarışır,
Alembic kilit tutmaz. "Açılışta göç" bayrağı BİLEREK yok — tek replikada rahat,
ikincisinde tuzak. Platformların hepsinde dağıtım öncesi tek seferlik komut var;
göç oraya konur ve platform yeni sürümü ancak komut 0 ile çıkarsa açar:

| platform | nereye yazılır | komut |
| --- | --- | --- |
| Fly.io | `fly.toml` → `[deploy]` → `release_command` | `python tools/goc.py` |
| Railway | servis → Settings → Deploy → *Pre-deploy command* | `python tools/goc.py` |
| Render | servis → Settings → *Pre-Deploy Command* | `python tools/goc.py` |
| kendi Docker'ın / compose | `goc` servisi (`compose.yaml`); `kromis` onu `service_completed_successfully` ile bekler | `docker compose run --rm goc` ya da `docker compose up` |
| kendi VM'in (systemd) | `ExecStartPre=` DEĞİL (her replikada koşar) — dağıtım betiğinin uvicorn'u yeniden başlatmadan önceki adımı | `python tools/goc.py && systemctl restart kromis` |

Göç düşerse (çıkış 1) uygulama eski sürümde kalır; Alembic göçü kendi
transaksiyonunda koşturduğu için şema yarım kalmaz. Geri almak gerekirse
`DATABASE_URL=… alembic downgrade -1` (elle; sarmalayıcı yalnız ileri gider).

## 2. Üç yedek, üç yer

Veri üç parçada duruyor ve **üçü birbirinden ayrı yedeklenir**; biri ötekinin
yanında dururken yedeğin işe yaramadığı ya da tek başına ele geçirildiğinde
fazlasını verdiği durumlar var, her satırda yazılı.

| parça | nerede | yedeği kimin, nasıl | neden ayrı |
| --- | --- | --- | --- |
| **Veri tabanı** — hesaplar, oturumlar, medya/klasör/sohbet/palet/varlık SATIRLARI, tercihler, ŞİFRELİ sağlayıcı anahtarları; Faz 2'den beri **`isler`** (iş kuyruğu ve 30 günlük geçmiş; `istek` prompt'u ve girdi anahtarlarını taşır) ve **`isciler`** (kalp atışı; işçi kalkınca yeniden yazılır, yedeğe girmese de kayıp yok) | PostgreSQL (`DATABASE_URL`) | Yönetilen Postgres'te (Neon, Supabase, Fly Postgres, RDS) **platformun PITR'ı** — açık olduğunu ve saklama süresini PANELDEN doğrula, varsayılan bazı planlarda kapalı. Kendi Postgres'inde `pg_dump -Fc "$DATABASE_URL" > kromis-$(date +%F).dump` cron'u + dosyanın başka bir makineye/kovaya kopyası | Satırlar dosyayı GÖSTERİR (`medya.filename`), dosya DB'de değil: DB yedeği tek başına galeriyi geri getirmez |
| **Medya** — `kullanicilar/<uuid>/{output,assets}` (PNG/MP4 dosyaları) ve `kullanicilar/<uuid>/isler/<is_id>/` (üretim işlerinin GİRDİ nesneleri: referans görseller, son kare; 30 gün sonra saklama siler, § 9): yerel diskte (`KROMIS_DATA_DIR`, compose) YA DA aynı anahtarla S3/R2 kovasında (`KROMIS_NESNE_DEPO_*`, Faz 2 / 2 — çok makineli dağıtımda zorunlu) | Kalıcı birim (`/data`) ya da kova | Diskte: **birim anlık görüntüsü** (Fly volume snapshot, bulut disk snapshot) ya da `rsync`/`rclone`; günlük. Kovada: **R2 nesne sürümlemesi** (§ 8: silinen/ezilen nesne 30 gün geri alınabilir) + isteğe bağlı ikinci kovaya `rclone sync` (§ 8, sahibin kararı) | Dosyalar DB'siz anlamsız (hangisi kimin, hangi klasörde — hepsi satırda); DB dosyasız yarım. İkisi AYNI ANDAN olmazsa artık dosya ya da kırık bağlantı doğar — `tools/artik_dosya.py` bunu iki yerde de bulur (§ 4) |
| **`KROMIS_SECRET_KEY`** — sağlayıcı anahtarlarını şifreleyen kök | Yalnız ortam değişkeni (platform sırları) | **ÜÇÜNCÜ bir yer**, öteki ikisinden ayrı: bir parola kasası (1Password/Bitwarden kasası, ya da basılı zarf). DB yedeğinin YANINA yazılmaz | DB yedeğiyle yan yana duran anahtar, yedeği ele geçirene bütün kullanıcıların sağlayıcı anahtarlarını düz metin verir. Kaybolursa `saglayici_kimlikleri` sütunu hiç okunamaz — kullanıcılar anahtarlarını yeniden girer, başka çare yok |
| **Platform sırları** (Faz 2 / 10) — `KROMIS_PLATFORM_<AD>` sağlayıcı anahtarları (Faz 2 / 6), R2 jetonu `KROMIS_NESNE_DEPO_ANAHTAR_ID`/`KROMIS_NESNE_DEPO_GIZLI`, `SENTRY_DSN`, `RESEND_API_KEY` | Platformun sır deposu (Fly secrets, Railway/Render env) | **Kasada kopyası** (`KROMIS_SECRET_KEY` ile aynı üçüncü yer): platform hesabı kapanır ya da proje silinirse sırlar onunla gider; hepsi sağlayıcı panelinden yeniden üretilebilir ama kesinti o kadar sürer. Kasadaki kayıt AD + değer + hangi panelden üretildiği | DB'de ve kovada bu değerlerin izi YOK (`.env.example` sözleşmesi; kod ortamdan okur); yedek tabloları onları taşımaz, kasa taşır |

Yedeklenmeyenler, bilerek: `hata.log`/`posta.log` (tanı, veri değil), oturum
satırları (yedekle gelirse gelir, kullanıcı yeniden girer), `guncelleme.json`
(web'de artık yazılmıyor).

Sır sızıntısı denetimi (7. görevin kuralı, yedekte de geçerli): bir `pg_dump`
çıktısında `sk-` ya da `AZURE` araması boş dönmeli — sütun Fernet jetonu
(`gAAAA…`) taşır. Boş dönmüyorsa yedeği ŞİFRELEMEDEN hiçbir yere koyma ve
sebebini bul.

## 3. `KROMIS_SECRET_KEY` döndürme

Anahtar listesi virgülle, **yeni en başta**: yazan taraf hep ilk anahtarla
yazar, okuyan taraf hepsini dener (`services/sifre.py`). Bu yüzden döndürme
kesintisiz ve dört adım:

1. Yeni anahtar üret (`.env.example`daki komut) ve kasaya (üçüncü yer) yaz.
2. Ortamı `KROMIS_SECRET_KEY="yeni,eski"` yap, dağıt. Uygulama açık kalır;
   yeni yazımlar yeni anahtarla, eski satırlar eski anahtarla okunur.
3. Bütün satırları yeni anahtara taşı:

   ```sh
   DATABASE_URL=… KROMIS_SECRET_KEY="yeni,eski" python tools/anahtar_dondur.py --kuru   # kaç satır?
   DATABASE_URL=… KROMIS_SECRET_KEY="yeni,eski" python tools/anahtar_dondur.py
   ```

   Araç kullanıcı başına döndürülen satırı ve sonda parmak izi başına kalan
   satırı basar; `ESKI anahtar` satırı 0 olmadan 4. adıma geçme. Düz metin bu
   süreçte açılmaz (`MultiFernet.rotate`). Uygulama açıkken koşabilir.
4. Ortamı `KROMIS_SECRET_KEY="yeni"` yap, dağıt; eskiyi kasadan sil.

Eski anahtar erken düşürülürse kullanıcı Ayarlar'da `SifreHatasi` görür; çare
eskiyi listenin SONUNA geri koyup 3. adımı yeniden koşturmak (araç çıkış 1 ile
bunu söyler, hiçbir şey yazmaz). `SELECT anahtar_surumu, count(*) FROM
saglayici_kimlikleri GROUP BY 1` hangi parmak izinin kullanımda olduğunu
gösterir; elindeki anahtarın parmak izi `services.sifre.parmak_izi()`.

## 4. Artık dosya taraması

Dosya + satır atomik değil: `depo_medya.kaydet`/`depo_varlik.kaydet` önce
dosyayı yazar, sonra satırı; commit düşerse dosya kalır. Silinen hesabın
satırları CASCADE ile gider, dosyaları gitmez. İkisini de bu araç bulur:

```sh
DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py            # listele (çıkış 3 = artık var)
DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py --sil      # sor, onaylanırsa sil
DATABASE_URL=… KROMIS_DATA_DIR=/data python tools/artik_dosya.py --sil --evet   # cron
```

Satırı olan dosyaya hiç dokunmaz; medya uzantısı taşımayan dosyaları
(`guncelleme.json` gibi) "medya değil" diye sayar, silmez. Haftalık cron makul;
geri yükleme tatbikatının da son adımı (aşağıda).

Medya kovadaysa (`KROMIS_NESNE_DEPO_*` dördü dolu, Faz 2 / 2) aynı komut aynı
değişkenlerle **kovayı** tarar (`kullanicilar/` öneki bir kez listelenir,
anahtarlar satırlarla karşılaştırılır, `--sil` nesneyi kovadan siler); veri
kökü dizini o kipte aranmaz. Yerelden kovaya taşıma `tools/medya_tasi.py`
(KURULUM.md → Web sürümü → 7).

## 5. Geri yükleme tatbikatı — iskelet (Faz 5'in kalemi)

Yedek, geri yüklenebildiği ölçüde yedektir. Aşağıdaki adımlar ÜRETİME DEĞİL
boş bir ortama (yeni bir Postgres + boş birim) uygulanır; her adımın sonunda
"doğrula" satırı var. İlk tatbikat bu PR'la yapılmadı (bu makinede Docker ve
yönetilen Postgres yok); Faz 5'in "yedekleme ve geri yükleme tatbikatı" kalemi
bu iskeleti doldurur ve ölçtüğü süreleri buraya yazar.

1. **Anahtarı kasadan al.** Doğrula: `python -c "from services import sifre;
   print(sifre.parmak_izi(sifre.kok_anahtarlar(KEY)[0]))"` çıktısı üretimde
   `SELECT DISTINCT anahtar_surumu` ile görülen değerlerden biri.
2. **DB'yi geri yükle** — PITR'da zaman noktası seç; `pg_dump` ile
   `pg_restore -d "$YENI_DATABASE_URL" kromis-….dump`. Doğrula:
   `SELECT count(*) FROM kullanicilar`, `… FROM medya` üretimdeki sayılara yakın;
   `SELECT version_num FROM alembic_version` yedeğin alındığı sürüm.
3. **Şemayı head'e taşı:** `DATABASE_URL=$YENI python tools/goc.py`. Doğrula:
   çıktı `(head)`; yedek eski bir sürümdense ara göçler burada koşar.
4. **Medyayı geri yükle.** Kovadaysa (Faz 2 / 2, üretimin hâli) kova ZATEN
   DURUYOR — bu adım yalnız kovanın kendisi kaybolduysa ya da nesneler
   silindiyse çalışır: sürümleme açıksa (§ 8) silinen nesnelerin önceki
   sürümü panelden/`rclone`la geri alınır; ikinci kova varsa
   `rclone sync r2-yedek:kromis-yedek r2:kromis`. Diskteyse (compose) birim
   anlık görüntüsünü yeni birime bağla ya da `rsync` ile
   `KROMIS_DATA_DIR/kullanicilar/` altına. Doğrula: kovada `rclone size`
   yedekle bir; diskte dizin sahibi uid 10001 (`/health`
   `data_dir_writable:true`), dosya sayısı yedekle bir.
5. **Uygulamayı aç** (`KROMIS_SECRET_KEY`, `DATABASE_URL`, `KROMIS_DATA_DIR`).
   Doğrula: `/health` 200 ve `db_reachable:true`; `/giris` açılıyor; bir
   test hesabıyla (ya da `tools/kullanici.py olustur` ile açılan yeni hesapla)
   giriş; Ayarlar'da `configured:true` — yani anahtar doğru, satırlar çözüldü
   (yanlış anahtarda burada 500 ve `hata.log`da `SifreHatasi`).
6. **Tutarlılık:** `python tools/artik_dosya.py` — DB ve medya yedeği farklı
   anlardan alındıysa fark burada görünür: satırı olan ama dosyası olmayan
   kayıtlar galeride kırık görsel (bunlar araçta değil; `SELECT filename FROM
   medya` ile dizin karşılaştırılır), dosyası olan ama satırı olmayanlar
   aracın listesinde. Doğrula: her iki sayı kabul edilebilir ve nedeni biliniyor.
7. **Kayıt:** tatbikatın tarihi, yedeğin yaşı, 2.-6. adımların süresi ve
   bulunan farklar bu belgenin altına eklenir. Bir sonraki tatbikat bu
   sayıların gerilemediğini ölçer.

## 6. Bu belgeye girmeyenler (ve nereye ait oldukları)

* Nesne depolama (R2/S3) — Faz 2 / 2 ile GELDİ (2. bölümün medya satırı iki
  yeri de yazıyor); kovanın sürümleme/çoğaltma düzeni § 8'de, platform
  sırları § 2 tablosunda (Faz 2 / 10 ile KAPANDI).
* Yapısal loglama, Sentry, uyarı eşikleri — Faz 2 / 9 ile GELDİ: iki süreç
  stdout'a satır başına JSON yazar (`istek_id`/`is_id` bağlamda; biçim
  `KROMIS_GUNLUK_BICIMI`), Sentry yalnız `SENTRY_DSN` verilmişse (redakte,
  PII kapalı), `/health` `worker_alive` (90 sn eşiği, `ok`a girmez). **Uyarı
  eşikleri:** kuyruk derinliği > 20 ya da en eski bekleyen > 10 dk → işçinin
  kalp turu (30 sn) `olay=uyari` (WARNING) düşürür, koşul sürdükçe her turda.
  Uyarının BİLDİRİMİ kodda değil: Sentry *Alerts* → "issue/log içeren olay
  sayısı ≥ 1 / 5 dk, `uyari` süzgeciyle" ya da platform günlüğünün metin
  uyarısı; `worker_alive:false` için `/health` gövdesini okuyan bir uptime
  sondası. KURULUM.md → Web sürümü, 9. adım.
* Kredi defteri yedeği — Faz 3 (tablo yok).
* Kimlik/oturum kaydının KVKK/GDPR saklama süresi — Faz 4.

## 7. Platformda iki süreç, tek imaj — açılış ve kapanış (Faz 2 / 10)

Web (`uvicorn app:app`, `Dockerfile` CMD) ve işçi (`python isci.py`) AYNI
imajdan iki süreçtir; ortak zeminleri Postgres (`isler` tablosu = kuyruk) ve
kova (medya). Platformda ikisi ayrı makinede koşar; hiçbir şey kodda platforma
özgü değil — fark yalnız yapılandırma dosyasında. Sahip Faz 2–4 için Fly.io'yu
seçti (K11); tablo üçünü de yazıyor, Railway'de prova yapıldı.

| platform | iki süreç nasıl tanımlanır | göç (§ 1) | kapanış süresi (SIGTERM → SIGKILL) | ölçülen / bilinen sınır |
| --- | --- | --- | --- | --- |
| **Fly.io** (seçilen) | `fly.toml` → `[processes]` `app = "uvicorn …"`, `isci = "python isci.py"`; `[[vm]]` bloklarıyla işçiye ayrı boyut; `[http_service]` yalnız `app` sürecine (`processes = ["app"]`) — işçi port açmaz | `[deploy] release_command = "python tools/goc.py"` | `kill_timeout` süreç bloğunda, **en çok 300 sn** (`kill_signal = "SIGTERM"`) | 300 sn bir görsel işini (≤ 180 sn) ve kısa videoyu sığdırır; 600 sn'lik video çağrısı SIĞMAZ — dağıtım sırasında koşan uzun iş kaybedilir (aşağıda) |
| **Railway** | aynı repo/imajdan İKİNCİ servis, *Settings → Deploy → Start Command* `python isci.py`; sağlık denetimi yok (port yok) | *Pre-deploy command* `python tools/goc.py` (yalnız web servisinde — iki servis aynı göçü yarıştırmasın) | ~10 sn öntanımlı, panelden uzatılabilir (sürüm/plan bağımlı, panelden doğrula) | Prova 2026-09-18: göç ve rol düzeni çalıştı (§ 7 karar kaydı); kapanış süresi ölçülmedi — dağıtımdan önce panelden oku ve buraya yaz |
| **Render** | *Background Worker* türünde ikinci servis, aynı imaj, *Start Command* `python isci.py` | *Pre-Deploy Command* (yalnız web) | ~30 sn öntanımlı (SIGTERM, sonra SIGKILL) | Yalnız görsel işleri sığar; video işi dağıtımda kaybolur |
| **compose** (yerel) | `compose.yaml` `kromis` + `isci` servisleri (`goc` servisini bekler) | `goc` servisi | `isci` → `stop_grace_period: 60s` (öntanımlı 10 sn bir görsel işini bile bitirmez) | `docker compose stop` 60 sn bekler, sonra SIGKILL |

**Fly örneği** (`fly.toml`, depoya konmaz — sahibin dosyası; değerler
öneri):

```toml
app = "kromis"
primary_region = "fra"
kill_signal = "SIGTERM"
kill_timeout = "300s"          # işçi için; web saniyeler içinde kapanır

[build]
  dockerfile = "Dockerfile"

[deploy]
  release_command = "python tools/goc.py"    # § 1: göç dağıtım ÖNCESİ, yeni sürüm ancak 0 verirse açılır
  strategy = "rolling"

[env]
  KROMIS_DATA_DIR = "/data"      # web: geçici; medya kovada (KROMIS_NESNE_DEPO_*), disk yalnız hata.log/posta.log
  KROMIS_GUNLUK_BICIMI = "json"

[processes]
  app  = "uvicorn app:app --host 0.0.0.0 --port 8080 --no-access-log"
  isci = "python isci.py"

[http_service]
  internal_port = 8080
  force_https = true
  processes = ["app"]
  [http_service.checks]
    [http_service.checks.health]
      path = "/health"           # 200/503 — `worker_alive` duruma GİRMEZ (Faz 2 / 9)
      interval = "30s"
      timeout = "5s"

[[vm]]
  processes = ["app"]
  size = "shared-cpu-1x"
  memory = "512mb"

[[vm]]
  processes = ["isci"]
  size = "shared-cpu-2x"         # sağlayıcı çağrısı beklemesi çoğunlukla ağ; 4 iş parçacığı (KROMIS_ISCI_ES_ZAMANLI)
  memory = "1gb"
```

Sırlar (`fly secrets set …`, iki sürece de gider; kasaya kopya, § 2):
`DATABASE_URL`, `KROMIS_SECRET_KEY`, `KROMIS_KOKEN`, `KROMIS_NESNE_DEPO_URL`,
`KROMIS_NESNE_DEPO_KOVA`, `KROMIS_NESNE_DEPO_ANAHTAR_ID`,
`KROMIS_NESNE_DEPO_GIZLI`, `KROMIS_POSTA`/`KROMIS_POSTA_GONDEREN`/`RESEND_API_KEY`,
fonlanan sağlayıcıların `KROMIS_PLATFORM_*` anahtarları, isteğe bağlı
`SENTRY_DSN`/`SENTRY_ENVIRONMENT`. İşçiye özel isteğe bağlı üç sayı
`.env.example`da: `KROMIS_ISCI_ES_ZAMANLI` (4), `KROMIS_IS_KALP_ESIGI_SN`
(300), `KROMIS_IS_SAKLAMA_GUN` (30). Tam envanter ve her birinin açıklaması
`.env.example` (bekçisi `tests/test_docker_kapisi.py`, ad kümesi kaynaktan).

**Kapanış (SIGTERM) ne yapar.** İşçi yeni iş almayı bırakır, ELDEKİ işleri
BİTİRİR (sağlayıcı çağrısı çoktan faturalandı — yarıda kesmek sonucu çöpe
atmak) ve **bu sürede kalp atmayı SÜRDÜRÜR** (`isciler.son_kalp` + eldeki
işlerin `kalp_atisi`; kalp ancak işler boşalınca durur — yoksa 270. saniyeden
sonra biten bir iş yeni işçinin bayat düşürmesine yakalanır ve sonucu çöpe
giderdi), sonra `isciler` satırını siler, 0 ile çıkar; boşta işçi ~0,1 sn'de
kapanır (ölçüldü). `kill_timeout` yetmezse platform SIGKILL gönderir: iş `calisiyor`da
kalır, yaşayan işçinin (ya da yenisinin) kalp turu `KROMIS_IS_KALP_ESIGI_SN`
(300 sn) sonra onu `hata` ("isci yanit vermiyor") yapar, kullanıcı panelden
yeniden gönderir — otomatik yeniden deneme YOK (K8: çift fatura riski). Ölen
işçinin `isciler` satırını yeni işçinin açılış bakım turu siler (§ 9).
**Dağıtım sırasında çalışan uzun iş KAYBEDİLİR** — kapalı betada kabul edilen
sınır; "boşalt (drain) sonra dağıt" ya da dağıtım penceresi Faz 5'in kalemi.
Web tarafında kapanış saniyeler: açık SSE akışları düşer, tarayıcı
`EventSource` ile yeniden bağlanır.

## 8. R2 kovası düzeni (Faz 2 / 10)

Kova adı `kromis` (KURULUM.md → Web sürümü, 7. adım kurar). Anahtar düzeni
tek kök altında, kullanıcı başına:

```
kullanicilar/<kullanici uuid>/output/<dosya>        üretilen görsel/video (medya.filename)
kullanicilar/<kullanici uuid>/assets/<tur>/<dosya>  logo/afiş kütüphanesi (varliklar.filename)
kullanicilar/<kullanici uuid>/isler/<is uuid>/<ad>  üretim işinin GİRDİLERİ (upload.png, refN.png, son_kare.png)
```

Satır dosyayı gösterir, dosya satırı bilmez (§ 2); `isler/` altındaki nesneler
işin `istek`indeki anahtarlardır ve "yeniden gönder" yeni işi ESKİ dizine
referansla koşturur (kopya yok) — bu yüzden bir `isler/<id>/` dizini ancak ona
bakan hiçbir satır kalmadığında silinir (saklama, § 9; `tools/artik_dosya.py`
de aynı ölçütü kullanır). Dört panel ayarı, kova açılırken bir kez:

1. **Kova ÖZEL** (public access kapalı, r2.dev alt alanı kapalı): her okuma
   uygulamanın 15 dakikalık ön imzalı URL'siyle (`/output/*` → 302). CORS
   gerekmez (302 aynı kökenden çıkar).
2. **Nesne sürümleme AÇIK** (*Settings → Object versioning*): silinen ya da
   ezilen nesnenin önceki sürümü durur — § 2'nin "medya yedeği" satırı budur;
   yanlış `--sil` ya da yanlış taşıma geri alınabilir.
3. **Yaşam döngüsü kuralları** (*Settings → Object lifecycle rules*), iki
   kural: (a) önek `kullanicilar/` — **sürüm geçmişi 30 gün** ("delete
   noncurrent versions after 30 days"; geçmiş sonsuza dek şişmesin), (b) önek
   yalnız `isler/` içeren anahtarlar için doğrudan bir önek kuralı R2'de
   yazılamaz (önek anahtarın BAŞINDAN eşleşir ve kullanıcı uuid'si önde); bu
   yüzden girdi nesnelerinin 7 günlük EMNİYET silmesi kovada değil UYGULAMADA:
   saklama turu satırı düşerken referanssız dizini siler (§ 9), `artik_dosya`
   kalanı bulur. Kova tarafında girdiler için ek kural YOK — belgenin § 10
   metnindeki "isler/ öneki 7 gün" kalemi bu gerekçeyle uygulamaya taşındı.
4. **İkinci kova (isteğe bağlı, sahibin kararı):** başka hesapta ya da başka
   sağlayıcıda `kromis-yedek`, günlük `rclone sync r2:kromis r2-yedek:kromis-yedek
   --fast-list` (cron, sahibin makinesi ya da platformun zamanlanmış işi).
   Sürümleme AYNI hesabın hatalarına karşı korur, ikinci kova hesabın kendisinin
   kaybına karşı. Kapalı betada sürümleme yeter; ödeyen kullanıcı gelince
   (Faz 4) ikinci kova açılır.

Jeton (`KROMIS_NESNE_DEPO_ANAHTAR_ID`/`_GIZLI`): **Object Read & Write, yalnız
bu kova**; kasaya kopya (§ 2). Döndürme: yeni jeton üret → iki sürecin sırrını
değiştir → dağıt → eskiyi panelden sil (kod tek jeton okur, çakışma yok;
dağıtım penceresinde eski süreç eski jetonla kapanır).

## 9. Günlük işletme: dağıt, geri al, sağlık, günlük, uyarı, saklama (Faz 2 / 10)

**Dağıtım sırası.** (1) `main` yeşil (5 CI işi: testler, sızıntı, lint,
ön yüz lint, docker — `docker` işi imajı derler, göçü koşturur, işçiyi bir tur
çalıştırır, `/health`i sorar). (2) Yeni göç varsa önce ÜRETİM DB'sinin yedeği
alınmış olsun (PITR açık mı, panelden). (3) `fly deploy` (ya da platformun
"deploy"u): `release_command` göçü koşturur — düşerse (çıkış 1/2) yeni sürüm
AÇILMAZ, eski süreçler koşmaya devam eder; günlükte `goc:` satırı sebebi
söyler. (4) İşçi ve web yeni imajla yeniden başlar; işçi eldeki işi bitirip
kapanır (`kill_timeout`, § 7); dağıtım penceresinde koşan uzun video işi
kaybedilebilir (bilinen). (5) Doğrula: `curl https://<alan>/health` →
`{"ok": true, "version": "<yeni>", "db_reachable": true, "worker_alive": true,
…}` (işçi kalkıp ilk kalbini atınca `true`; 90 sn içinde). `/giris` açılıyor,
bir hesapla giriş, küçük bir üretim işi panelde `bitti`.

**Geri alma.** Kod: platformun önceki sürümünü seç (`fly releases` →
`fly deploy --image <önceki>`; Railway/Render "Rollback"). Şema: yeni göç geri
alınabilir yazılmıştır (`downgrade` her göçte var, `tests/test_db.py`
ileri-geri-ileri); `DATABASE_URL=… alembic downgrade -1` ELLE ve yalnız eski
kod yeni sütunla çalışamıyorsa — çoğu göç ek sütun/tablo ekler ve eski kod
onları görmez, geri almak gerekmez. Sıra: önce kodu geri al, sonra gerekirse
şemayı. Medya: sürümleme (§ 8). Sır: eski değer kasada (§ 2).

**Sağlık.** `/health` 200/503 = web sağlığı (yazılabilir disk + DB);
`worker_alive` ve `worker_last_heartbeat` gövdede, duruma GİRMEZ (işçinin
düşmesi web'i yeniden başlattırmamalı). Platformun sağlık denetimi durum
koduna; işçi için uptime sondasının gövde kuralı `worker_alive == false` 5
dakikadır → bildir. Admin sayfası (`/admin` → işçiler) aynı eşikle (90 sn)
"canlı/bayat" der.

**Günlük.** İki süreç de stdout'a satır başına JSON (`ts`, `seviye`,
`logger`, `mesaj`, alanlar; `KROMIS_GUNLUK_BICIMI`). `kromis.*` dışındaki
WARNING+ (SQLAlchemy, httpx) ve uvicorn'un yaşam döngüsü/ASGI istisna izi de
aynı akımda ve redaksiyondan geçer (Faz 2 / 10) — lifespan'dan ÖNCEKİ iki
uvicorn satırı (`Started server process`, `Waiting for application startup`)
stderr'de düz metin kalır. "Bu istek ne oldu": cevaptaki `X-Request-ID` =
günlükteki `istek_id`. "Bu iş ne oldu": `grep <is_id>` → `is.alindi` →
`is.basladi` → `is.bitti`/`is.hata`. İşçi süreç olayları `isci.basladi/
sinyal/kapandi`, `bayat` (düşürülen iş sayısı), `bakim` (aşağıda), `uyari`.

**Uyarı** (Sentry *Alerts* ya da günlük toplayıcısının kuralı): `uyari` olayı
5 dk'da ≥ 1 (kuyruk derinliği > 20 ya da en eski bekleyen > 10 dk — § 6),
`seviye=ERROR` 1 saatte ≥ 10, `worker_alive:false` 5 dk. Bildirimin kendisi
kodda değil, panelde.

**İş saklama ve bayat düşürme — ayrı cron YOK.** İşçi zaten sürekli koşan tek
süreç; iki ayrı iş parçacığı iki şeyi yapar (ayrı, çünkü bakım turu nesne
başına ağa çıkar ve birikmiş kuyrukta dakikalar sürebilir — kalp o sürede
susarsa eldeki işler bayat düşer, `/health` işçiyi ölü gösterir):

* **Her 30 sn (kalp turu, kalp iş parçacığı):** `isciler.son_kalp`, eldeki
  işlerin `kalp_atisi`, ve kalbi `KROMIS_IS_KALP_ESIGI_SN` (300) saniyeden
  uzun susan HER `calisiyor` iş → `hata` ("isci yanit vermiyor"; K8, yeniden
  kuyruğa alınmaz). Günlükte `olay=bayat adet=N`. İşçinin kendi `isciler`
  satırı YOKSA (başka işçinin ölü süpürmesi, 5 dk'lık DB kesintisi, dağıtımda
  yeni işçinin açılış turu boşalan eskinin satırını sildi) aynı `id`yle
  yeniden yazılır — `olay=isci.yeniden_kaydoldu` (WARNING); yaşayan işçi
  `worker_alive:false` üretmez, kapanışta silecek satırı bulur.
* **Açılışta bir kez ve sonra her 5 dk (bakım turu, bakım iş parçacığı,
  `olay=bakim`):**
  (1) `bitti`/`hata`/`iptal` durumundaki ve kapanışı `KROMIS_IS_SAKLAMA_GUN`
  (30) günden eski `isler` satırları silinir — `medya` satırlarına ve
  üretilen görsellere DOKUNULMAZ (`isler.sonuc` yalnız id listesi, ürün
  galeride durur; aktif iş yaşı ne olursa olsun silinmez). (2) Silinen işin
  `isler/<id>/` girdi dizini yalnız ona bakan hiçbir satır kalmadıysa
  kovadan/diskten silinir (yeniden gönderilen iş eski dizine referans verir);
  silinen işin `istek`i BAŞKA kiracının dizinine bakıyorsa o dizine dokunulmaz,
  `olay=bakim.yabanci_dizin` (WARNING) düşer — bugün olmaması gereken bir şey.
  (3) `son_kalp` kalp eşiğinden eski `isciler` satırları silinir — SIGKILL ya
  da `kill_timeout` aşımıyla ölen işçi kendi satırını silemez ve
  `worker_alive:false` sonsuza dek kalırdı; açılıştaki tur yeni işçi kalkar
  kalkmaz bunu kapatır (tek işçili dağıtımda silecek başka işçi yok).
  Günlük satırı sayıları verir: `silinen_is`, `silinen_nesne`,
  `korunan_dizin`, `silinen_isci`; boş turda satır yok. KVKK saklama süresi
  kararı Faz 4'te (`istek.prompt`u da kapsar); 30 onun öncülü. Elle tarama
  `tools/artik_dosya.py` (§ 4) aynı referans ölçütünü bilir.

**İlk üretim koşusu — kontrol listesi.** `tools/rls_kontrol.py` yeşil
(KURULUM.md 1), göç head (§ 1), kova özel + sürümleme + yaşam döngüsü (§ 8),
sırlar iki serviste de ve kasada (§ 2), `fly.toml`da `kill_timeout` ve iki
süreç (§ 7), admin hesabı (`tools/kullanici.py admin`), `/health`
`worker_alive:true`, bir görsel işi panelde saniyelerle sayılıp `bitti`
oluyor (sayaç 0'dan başlar — Faz 2 / 10 saat dilimi düzeltmesi), Sentry'de
deneme olayı (isteğe bağlı), platform günlüğünde JSON satırlar.
