# İşletme: dağıtım öncesi göç, üç ayrı yedek, anahtar döndürme, geri yükleme tatbikatı

**Tarih:** 2026-09-17 (Faz 1 / 9) · **Kime:** web sürümünü işleten kişi ·
**Kurulum adımları:** [KURULUM.md → Web sürümü](../KURULUM.md#web-sürümü-sunucu-kurulumu) ·
**Karar kaydı:** [faz1-veritabani-hesaplar.md § 9](faz1-veritabani-hesaplar.md)

Bu belge kod değil, işletme düzeni. Üç şeyi söylüyor: şema göçü NEREDE koşar,
veri NEREDE durur ve nasıl yedeklenir, bir felakette ne sırayla geri gelir.
Bekçisi `tests/test_docker_kapisi.py` (belge var, üç yedek ayrı, tatbikat adımlı).

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
| **Veri tabanı** — hesaplar, oturumlar, medya/klasör/sohbet/palet/varlık SATIRLARI, tercihler, ŞİFRELİ sağlayıcı anahtarları | PostgreSQL (`DATABASE_URL`) | Yönetilen Postgres'te (Neon, Supabase, Fly Postgres, RDS) **platformun PITR'ı** — açık olduğunu ve saklama süresini PANELDEN doğrula, varsayılan bazı planlarda kapalı. Kendi Postgres'inde `pg_dump -Fc "$DATABASE_URL" > kromis-$(date +%F).dump` cron'u + dosyanın başka bir makineye/kovaya kopyası | Satırlar dosyayı GÖSTERİR (`medya.filename`), dosya DB'de değil: DB yedeği tek başına galeriyi geri getirmez |
| **Medya** — `kullanicilar/<uuid>/{output,assets}` (PNG/MP4 dosyaları): yerel diskte (`KROMIS_DATA_DIR`, compose) YA DA aynı anahtarla S3/R2 kovasında (`KROMIS_NESNE_DEPO_*`, Faz 2 / 2 — çok makineli dağıtımda zorunlu) | Kalıcı birim (`/data`) ya da kova | Diskte: **birim anlık görüntüsü** (Fly volume snapshot, bulut disk snapshot) ya da `rsync`/`rclone`; günlük. Kovada: **R2 nesne sürümlemesi** (bucket versioning, panelden aç) + isteğe bağlı ikinci kovaya `rclone sync` — düzeni Faz 2 / 10 yazar | Dosyalar DB'siz anlamsız (hangisi kimin, hangi klasörde — hepsi satırda); DB dosyasız yarım. İkisi AYNI ANDAN olmazsa artık dosya ya da kırık bağlantı doğar — `tools/artik_dosya.py` bunu iki yerde de bulur (§ 4) |
| **`KROMIS_SECRET_KEY`** — sağlayıcı anahtarlarını şifreleyen kök | Yalnız ortam değişkeni (platform sırları) | **ÜÇÜNCÜ bir yer**, öteki ikisinden ayrı: bir parola kasası (1Password/Bitwarden kasası, ya da basılı zarf). DB yedeğinin YANINA yazılmaz | DB yedeğiyle yan yana duran anahtar, yedeği ele geçirene bütün kullanıcıların sağlayıcı anahtarlarını düz metin verir. Kaybolursa `saglayici_kimlikleri` sütunu hiç okunamaz — kullanıcılar anahtarlarını yeniden girer, başka çare yok |

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
4. **Medya dizinini geri yükle** — birim anlık görüntüsünü yeni birime bağla
   ya da `rsync` ile `KROMIS_DATA_DIR/kullanicilar/` altına. Doğrula: dizin
   sahibi uid 10001 (`/health` `data_dir_writable:true`), dosya sayısı yedekle bir.
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
  yeri de yazıyor); kovanın sürümleme/çoğaltma düzeni ve platform sırları
  Faz 2 / 10'un kalemi.
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
