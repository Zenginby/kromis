# Kromis Studio — fal.ai video sağlayıcısı (Wan · PixVerse · Kling)

**Tarih:** 2026-09-14
**Durum:** tasarım onaylandı (Yaklaşım 1), plana geçiliyor

## Problem

Video tarafı TEK sağlayıcıya bağlı. `catalog.VIDEO_MODELS`'in üç girdisi de
Gemini · Veo 3.1 ve üçü de aynı `GEMINI_API_KEY`e dayanıyor. Yani:

* Gemini anahtarı olmayan kullanıcı için uygulamanın video kipi HİÇ yok.
* Veo'nun eksenleri tavan: en uzun klip **8 saniye**, oranlar yalnız 16:9 ve
  9:16, ve `catalog.VIDEO_MODELS`'in başlığındaki bilinen kusur ("başlangıç ve
  bitiş karesi BİRLİKTE verildiğinde HTTP 400") başka bir sağlayıcıyla
  karşılaştırılamıyor.
* Bir kesinti ya da fiyat değişikliği doğrudan özelliğin tamamını düşürüyor.

Görsel tarafında bu sorun yok: beş adaptör, dört ayrı kimlik. Asimetri
`VIDEO_MODELS`'in başlığında zaten "sırası kendi kuyruk adaptörleriyle
birlikte" diye işaretlenmiş durumda.

## Neden fal.ai, neden bu tur yalnız video

**Toplayıcı seçildi, doğrudan sağlayıcı değil.** `3df4742` (FLUX) birim ölçüyü
veriyor: 292 satır istemci + 92 satır katalog + 259 satır test + logo. Doğrudan
her marka bu bedeli baştan ödüyor. fal'da bedel BİR KEZ ödeniyor; sonraki her
model tek katalog satırı. Karşılığında sağlayıcının markaya özgü tel
özellikleri (Ideogram'ın tipografi kontrolü, Recraft'ın SVG çıktısı) kayboluyor
ve araya marj giriyor — video tarafında bu takas kabul edildi çünkü buradaki
ihtiyaç GENİŞLİK, derinlik değil.

**fal, Replicate'e tercih edildi:** video kataloğu belirgin biçimde geniş
(~450 video ucu) ve aradığımız üç eksen (ucuz / uzun / kaliteli) tek
sağlayıcıda karşılanıyor. Replicate'in `Prefer: wait` başlığı adaptörü
BASİTLEŞTİRİRDİ ama o kazanç görsel tarafında değerli; video zaten dakikalarca
sürüyor, yani kuyruk döngüsü her hâlükârda gerekli.

**Bu tur yalnız VİDEO.** `_ADAPTERS`'e "fal" GİRMİYOR. Gerekçe `providers.py`
`_azure_generate`'in yorumuyla aynı ailede: görsel yolunun telde ürettiği
baytlar DEĞİŞMEMELİ. Video tablosu ayrı olduğu için beş görsel adaptörü ve
onların testleri bu turun tamamen dışında kalıyor — geri alınması gereken bir
şey çıkarsa görsel tarafı hiç etkilenmiyor.

**Anahtar alanı ZATEN var.** `FAL_KEY` v0.2.0'dan beri `POST /api/settings`'te
kabul ediliyor (`models.SettingsRequest.fal_key`, `app.py:1222`). Bu tur onu
kataloğa taşıyor.

## Kapsam dışı (bilinçli)

* **fal'ın görsel modelleri.** Aynı protokol, farklı alanlar; sırası ayrı tur.
  Geldiğinde `generate`/`edit` AYNI `fal_client.py`'ye ekleniyor (bkz. "Dosya
  bölünmüyor").
* **Replicate.** `REPLICATE_API_TOKEN` `app.py`'nin "kataloğa girmemiş eski
  BYOK alanları" bloğunda KALIYOR — modeli ve adaptörü olmadan kataloğa yazmak
  o bloğun yorumunun tam olarak uyardığı şey ("bağlı gibi görünmelerine yol
  açardı").
* **Veo 3.1'i fal üzerinden eklemek.** Zaten doğrudan katalogda; fal'dan
  geçirmek aynı modele marj eklemek olurdu.
* **Son kare (`supports_last_frame`).** Bayrak üçünde de `False`; uygulama
  tarafı `providers.animate_video`'nun kapısıyla zaten korunuyor.
  **DÜZELTME (Görev 9, 2026-09-15):** bu satır önceden "üç modelin hiçbirinin
  i2v şemasında `tail_image_url` yok" diyordu — doğru ama BOŞ gerekçeydi,
  çünkü `tail_image_url` fal'da hiç kullanılmayan bir ad; hiçbir modelin
  şemasında böyle bir alan zaten yoktu. Görev 8'in tam OpenAPI şema ölçümü
  (`olcum-uc-semalari.md`) Wan'ın i2v ucunda GERÇEKTEN bir son-kare alanı
  olduğunu gösterdi: `end_image_url` (str|null, "son kare desteği VAR").
  Karar yine de doğru: `fal_client.ALANLAR` bu turda `end_image_url`ı
  BİLİNÇLİ OLARAK göndermiyor, yani bayrak dürüstçe `False`. PixVerse ve
  Kling'in şemalarında ise gerçekten hiçbir son-kare alanı yok.
* **`multi_prompt` / çok-çekimli storyboard** (Kling), `seed`, `cfg_scale`,
  `negative_prompt`, `enable_prompt_expansion`. Her biri YENİ bir eksen: istek
  modeli, form, `_check_video_form`, `ResultParams` ve sonuç kartı demek.
* **Kredi ledger'ı.** Krediler bugün olduğu gibi yalnız metadata.
* **`extend-video`.** `VIDEO_DURATIONS`'ın yorumunda zaten kapsam dışı.

## Karar 1 — İki uç sorunu: `wire_model_edit`

fal'da metin→video ve görsel→video **AYRI uçlar**:

```
fal-ai/kling-video/v3/turbo/pro/text-to-video
fal-ai/kling-video/v3/turbo/pro/image-to-video
```

`ImageModel.wire_model` tek alan. Üç yol değerlendirildi:

| reddedilen yaklaşım | gerekçe |
| --- | --- |
| Uç yolunu adaptörde türet (`wire_model` = taban, sonuna `/text-to-video` ekle) | Kural İLK istisnada kırılıyor: `fal-ai/veo3.1` metin tarafında ÇIPLAK, görsel tarafında `/image-to-video`. Kırılma telde 404 — bu deponun yasakladığı "arayüzde seçilebilir hata"nın video ikizi. |
| Model başına İKİ katalog girdisi | Şerit 3 değil 6 kart gösterirdi ve kullanıcı "Kling (metin)" / "Kling (görsel)" ayrımını elle yapardı — oysa `supports_edit` bayrağı tam olarak bu ayrımı SAKLAMAK için var. `app._check_video_form` ve önyüzün de iki id'yi eşlemeyi öğrenmesi gerekirdi. |

**Seçilen:** `ImageModel`'e tek alan, `wire_model`'in hemen altında:

```python
# İKİNCİ TEL YOLU — yalnız uçları AYRIŞMIŞ sağlayıcıda dolu.
# "" = düzenleme ve üretim AYNI uca gidiyor; bugünkü on üç girdinin hepsi
# böyle, yani bu alan onların hiçbirinin baytını değiştirmiyor.
wire_model_edit: str = ""
```

Mandal (`tests/test_catalog.py`): `provider == "fal"` ve `supports_edit` olan
bir girdide `wire_model_edit` BOŞ OLAMAZ. Boş bırakmak, düzenleme isteğini
metin ucuna göndermek — yani telde 422 — demek olurdu.

## Karar 2 — Kimlik: forma gerçek bir alan giriyor

```python
Credential(
    id="fal",
    label="fal.ai",
    key_env="FAL_KEY",
    url_env="FAL_BASE_URL",
    default_base_url="https://queue.fal.run",
    secret_field="fal_key",
    url_field=None,
)
```

`url_field=None` bilinçli ve `azure_chat`in duruşunun aynısı: fal'da
kullanıcıya özel endpoint yok, vekil arkasına almak isteyen `credentials.env`'e
elle yazıyor. Forma adres alanı GİRMİYOR.

İki sonucu var:

1. `app.py:1222`'deki elle yazılmış `fal_key` dalı **siliniyor** — katalog
   döngüsü (`for cred in catalog.CREDENTIALS`) aynı env'i aynı "boş = dokunma"
   kuralıyla yazıyor. `replicate_api_token`, `comfyui_url` ve `ollama_url` o
   blokta KALIYOR, yani bloğun varlık gerekçesi bozulmuyor.
2. **DÜZELTME (Görev 8, 2026-09-15):** bu maddenin önceki hâli "redaksiyon
   BEDAVA geliyor, `fal_key` bu turda o bedelden çıkıyor" diyordu — bu YANLIŞ.
   `app.py:125`'teki ÜÇÜNCÜ kapı (`_SECRET_SUFFIXES = ("_api_key", "_key",
   "_token", "_secret")`) adı `_key` ile biten HER alanı, kataloğa girip
   girmediğine BAKMAKSIZIN zaten redakte ediyordu; `fal_key` OKUMA
   (doğrulama hatası) yolunda bu turdan ÖNCE de korunuyordu — `app.py`'nin
   kendi yorumu bunu doğruluyor: "bugünkü `fal_key` / `replicate_api_token`
   tam olarak bu kapıdan geçiyor". Kataloğa girmenin redaksiyona kattığı tek
   şey, İKİNCİ kapının (`_SECRET_FIELDS`, `CREDENTIALS`tan türeyen ADLAR)
   artık onu da AÇIKÇA listelemesi — üçüncü kapıyla ÖRTÜŞEN, yedek bir
   koruma. Gerçek boşluk OKUMADA değil YAZMADAYDI: forma alan yoktu, sunucu
   tarafında elle yazılmış bir dal vardı ve bu yüzden anahtar bugüne kadar
   ancak `curl` ile yazılabiliyordu — kataloğa girmesinin asıl kazancı bu
   yazma yolunu (ve arayüz alanını) açması.

**Beklenmedik bulgu:** `fal_key`in bugün HİÇBİR arayüzü yok. API v0.2.0'dan
beri kabul ediyor ama `static/index.html`'de alanı yok — yani bugün o anahtar
ancak `curl` ile yazılabiliyor. Kataloğa girmesi arayüz işini ZORUNLU kılıyor
(bkz. Karar 6).

## Karar 3 — Katalog girdileri

`DEFAULT_VIDEO_MODEL` **DEĞİŞMİYOR** (`gemini-veo-3-1-lite`). Varsayılanı
kaydırmak her kullanıcının bir sonraki tıkına dokunurdu. fal girdileri üç Veo
girdisinin ALTINA, artan maliyete göre ekleniyor.

| id | t2v ucu / i2v ucu | `sizes` | `qualities` | `durations` | `credits`/sn | `poll_timeout` |
| --- | --- | --- | --- | --- | --- | --- |
| `fal-wan-3-0` | `alibaba/wan-3.0/text-to-video` · `…/image-to-video` | 16:9 · 9:16 · 1:1 | 480p · 720p · 1080p | 5 · 10 | 16 | 420 |
| `fal-pixverse-c1` | `fal-ai/pixverse/c1/text-to-video` · `…/image-to-video` | 16:9 · 9:16 · 1:1 | 720p · 1080p | 5 · 10 · 15 | 20 | 600 |
| `fal-kling-v3-turbo-pro` | `fal-ai/kling-video/v3/turbo/pro/text-to-video` · `…/image-to-video` | 16:9 · 9:16 · 1:1 | 1080p (gizli) | 5 · 10 · 15 | 30 | 600 |

**DÜZELTME (Görev 9, 2026-09-15):** yukarıdaki `credits`/sn sütunu (Wan 16 ·
PixVerse 20 · Kling 30) ve dolayısıyla üstteki "fal girdileri ... artan
maliyete göre ekleniyor" sırası (Wan · PixVerse · Kling) bu tasarımın İLK
yazıldığı gündü — ölçümden ÖNCEKİ tahmindi. Görev 7'nin canlı/şema ölçümü
(aşağıdaki "Ölçüm sonuçları" bölümü, `catalog.py`nin `VIDEO_MODELS` başlığı)
gerçek rakamların **PixVerse 13 · Wan 20 · Kling 28** olduğunu gösterdi —
sıra da buna göre **PixVerse · Wan · Kling**e döndü (`catalog.py`'deki
gerçek dizilim ve `tests/test_catalog.py`nin
`test_fal_video_models_are_ordered_PIXVERSE_WAN_KLING` mandalı). Eski
tahmin SİLİNMEDİ, çünkü tasarımın o an aldığı kararı (Karar 4'ün YUKARI
yuvarlama gerekçesi dahil) anlamak için hâlâ gerekli; ÜRETİM kodu şu an
ölçülmüş rakamları kullanıyor.

Üçü de: `provider="fal"`, `credential="fal"`, `kind="video"`, `max_n=1`,
`images_per_request=1`, `supports_edit=True`, `max_refs=1`,
`supports_last_frame=False`.

`credits_by_quality` (çözünürlük fiyatı GERÇEKTEN değiştirdiği yerde; taban
`credits`i ezer, `cost_for`un mevcut kuralı):

| model | tarife |
| --- | --- |
| `fal-wan-3-0` | 480p → 10 · 720p → 16 · 1080p → 24 |
| `fal-pixverse-c1` | 720p → 20 · 1080p → 32 |
| `fal-kling-v3-turbo-pro` | (yok — tek gizli jeton, taban `credits` geçerli) |

**DÜZELTME (Görev 9, 2026-09-15):** bu tarife de yukarıdaki `credits`/sn
sütunuyla AYNI ölçüm-öncesi tahmindi. Ölçüm sonrası gerçek tarife
`catalog.py`nin `credits_by_quality` alanlarında ve
`tests/test_catalog.py`nin
`test_fal_credits_are_derived_from_MEASURED_usd_per_second` mandalında
donuk: **Wan 480p→10 · 720p→20 · 1080p→40**, **PixVerse 720p→13 ·
1080p→24**. Eski tahmin (Wan 10·16·24, PixVerse 20·32) burada duruyor ama
ÜRETİM kodu bu satırı hiç okumadı — literaller doğrudan ölçümden yazıldı.

### Beyan kuralı

**Yalnız şemanın AÇIKÇA saydığı jeton beyan ediliyor.** Bu, Veo'nun 1080p'sinin
girme ve fast/lite'ın 1080p'sinin GİRMEME gerekçesinin aynısı
(`catalog.VIDEO_MODELS` başlığı: "doğrulanmamış bir jeton beyan etmek arayüzde
seçilebilir bir 400, eksik beyan etmek ise yalnızca bir yeteneği kullanmamak").

* **15 saniye** giriyor: Kling şeması `duration`ı 3–15, PixVerse 1–15 olarak
  AÇIKÇA sayıyor. Bu, Veo'nun 8 sn tavanını aşan tek yeni YETENEK ve
  PixVerse'ün kataloğa girme gerekçesi.
* **Wan'ın süresi yalnız 5 · 10**: şeması aralık VERMİYOR, yalnız varsayılanı
  (5) söylüyor.
  **DÜZELTME (Görev 9, 2026-09-15):** bu satır da ölçüm-öncesi tahmindi ve
  YANLIŞTI. Görev 8'in tam OpenAPI şema ölçümü
  (`.superpowers/sdd/2026-09-14-fal-video-saglayicisi/olcum-uc-semalari.md`)
  Wan'ın `duration` alanı için şemanın AÇIKÇA bir aralık (`minimum: 2,
  maximum: 30`, tamsayı\|null) verdiğini gösterdi — "aralık VERMİYOR" iddiası
  bayattı, kaynağı hiç canlı/şema ile sınanmamış bir varsayımdı. Katalog
  BİLİNÇLİ OLARAK yine de yalnız 5 ve 10'u beyan ediyor (`catalog.py`nin
  `VIDEO_MODELS` başlığı) — 15 sn'e (ya da şemanın izin verdiği 30 sn'e)
  çıkarmak ayrı bir ölçüm/karar ister (test edilmemiş süre, fatura ve
  `poll_timeout` etkisi bu turda değerlendirilmedi). Bu düzeltme `328defc`
  ile katalog tarafında zaten yapılmıştı; bu belge o güne kadar geride
  kalmıştı.
* **Kling'in `resolution`'ı tek gizli jeton**: i2v şemasında o alan HİÇ yok,
  t2v şeması da enum vermiyor. Etiket kullanıcıya bilgi veriyor, telde
  gönderilmiyor (`quality_hidden=True`).
* **1:1 giriyor**: üç şemada da var. `VIDEO_ASPECT_RATIOS` (16:9 · 9:16)
  Veo'nun demeti olarak KALIYOR; fal için ayrı bir `FAL_VIDEO_ASPECT_RATIOS`
  demeti açılıyor — iki sağlayıcının kabulünü tek demete katlamak, birine oran
  ekleyip ötekini unutmanın kapısı olurdu.

### Kredi tarifesi

Depo çapası korunuyor: Azure `medium` = 8 kredi ≈ 0,04 USD → **1 kredi ≈
0,005 USD**. Birim SANİYE (`ImageModel.credits` yorumu).

Yayınlanmış saniye fiyatları yalnız KOMŞU sürümler için bulunabildi (Kling 2.6
Pro 0,14 USD/sn sesli; Wan 2.5 0,05 USD/sn 480p; PixVerse C1 için hiç yok), bu
yüzden tablo **yukarı yuvarlandı**. Yön bilinçli: krediyi düşük göstermek
kullanıcıyı ucuz sanıp tıklamaya davet eder, yüksek göstermek yalnız fazla
ihtiyatlı olur. **Ölçüm adımında fal'ın fiyat sayfasından teyit edilecek** ve
tabloya gerçek rakamlar yazılacak.

## Karar 4 — `fal_client.py`

### Dosya bölünmüyor

Tek dosya, kökte DÜZ (Chaquopy `include "*.py"`;
`tests/test_android_packaging.py`). `azure_mai_client` / `azure_flux_client`
ikilisi gibi BÖLÜNMÜYOR, çünkü o bölünmenin ölçütü TEL FORMATIYDI (farklı yol,
farklı gövde, farklı hata şekli). fal'da protokol TEK; modeller arasında
değişen yalnız alan adları. fal'ın görsel tarafı geldiğinde `generate`/`edit`
AYNI dosyaya ekleniyor.

Dosya adı PyPI'daki resmî `fal-client` paketini GÖLGELİYOR. O paket
kullanılmıyor (BYOK, yalnız `httpx`, `hiddenimports=[]` ve Chaquopy gerekçesi)
ve bu, dosya başlığında yazılı olacak — ki ileride biri `fal-client`ı
`requirements.txt`e eklemeye kalkarsa gölgelenmeyi görsün.

### Dört adım

```
1. submit    POST {base}/{wire_path}          Authorization: Key <FAL_KEY>
             -> {request_id, status_url, response_url, cancel_url, queue_position}
2. yokla     GET  {base}/{app_path}/requests/{id}/status
             -> {status: IN_QUEUE | IN_PROGRESS | COMPLETED, queue_position?, error?}
3. sonuç     GET  {base}/{app_path}/requests/{id}
             -> {video: {url, content_type, file_name, file_size}}
4. indir     GET  video.url                    -> mp4 baytları
```

`app_path` = `wire_path`in İLK İKİ SEGMENTİ (`fal-ai/kling-video/v3/turbo/pro/
text-to-video` → `fal-ai/kling-video`). Gönderim tam yola, yoklama ve sonuç
uygulama yoluna gidiyor; 2026-09-14'te canlı uçtan ölçüldü ve tam yolla kurulan
adres 404 değil BOŞ GÖVDE döndürüyor — yani sessiz bir kusur.

### GÜVENLİK: 2. ve 3. adımın adresi YANITTAN alınmıyor

fal'ın belgesi "dönen `status_url`'ü kullan, elle kurma" diyor. **Bilerek
yapmıyoruz.** Adres güvenilen tabandan kuruluyor; gövdeden alınan TEK şey
`request_id` ve o da katı bir karakter kümesine karşı doğrulanıyor, yani yola
segment enjekte edilemiyor.

Gerekçe `veo_client`'ın ölçülmüş kararı: orada `op_url` da
`taban + OPERATION_PREFIX + ad` ile kuruluyor ve `_indir`in yorumu sorunu
yazıyor — "buradaki `uri` YANIT GÖVDESİNDEN geliyor, yani hedef konağı gövdeyi
yazan taraf seçiyor". Aynı disiplin burada da geçerli.

Takas açık: fal bir gün kuyruğu bölgeselleştirirse (BFL'in `api.eu` / `api.us`
uçlarında olduğu gibi) değişecek tek satır burasıdır. Buna karşılık bugün
gövdeyi yazan taraf bizim `GET`'imizin hedefini seçemiyor.

**4. adım ANAHTARSIZ.** fal'ın çıktı URL'i genel erişime açık bir CDN adresi;
`veo_client._indir` Google konağında anahtarı gönderiyordu, burada HİÇ
gönderilmiyor — gövdeden gelen bir adrese anahtar sızma yolu tamamen kapalı.
Yönlendirme yine ELLE izleniyor (`follow_redirects` YOK), tavanla.

### Zaman aşımları

`veo_client`'ın kanıtladığı üçlü; sabitler de ONUN değerleri, çünkü sorun aynı
(uzun süren kuyruk + büyük indirme) ve iki video adaptörünün sessizce
ayrışması için bir sebep yok:

```python
POLL_READ_TIMEOUT = 30.0
DOWNLOAD_READ_TIMEOUT = ac.read_timeout_for(1)   # 180 sn — video onlarca MB
POLL_INTERVAL_START = 1.0
POLL_INTERVAL_MAX = 10.0
POLL_BACKOFF = 1.6
MAX_YONLENDIRME = 5
```

Üçüncü sınır duvar saati: `providers.total_budget(m, n)`, yani `poll_timeout`.
Sabitler KOPYALANIYOR, `veo_client`ten import EDİLMİYOR — `azure_mai_client` /
`azure_flux_client` ikilisinin `AUTH_HEADER`ı iki kez beyan etme gerekçesinin
aynısı: biri değişmek zorunda kaldığında öteki dokunulmadan kalabiliyor.

### Uç → alan tablosu

Yaklaşım 1'in taşıyıcı parçası. Katalogda DEĞİL burada, çünkü katalog "bu model
ne yapabiliyor" diyor, tablo "bu uç hangi adı okuyor".

| model | t2v gönderilen | i2v gönderilen |
| --- | --- | --- |
| Wan 3.0 | `prompt` `resolution` `aspect_ratio` `duration` | `prompt` `image_url` `resolution` `duration` |
| PixVerse C1 | `prompt` `resolution` `aspect_ratio` `duration` | `prompt` `image_url` `resolution` `duration` |
| Kling V3 Turbo Pro | `prompt` `aspect_ratio` `duration` | `prompt` `image_url` `duration` |

Kling'in i2v satırında `aspect_ratio` ve `resolution` YOK — şemasında o alanlar
yok, oran ilk kareden türetiliyor. Katalog `sizes`'ı yine beyan ediyor (metin
yolunda gerçek); adaptör düzenleme yolunda onu SESSİZCE değil, TABLOYA BAKARAK
düşürüyor.

**Tabloda olmayan hiçbir alan gönderilmiyor** — ve gerekçe 2026-09-14
ölçümünden SONRA değişti (bkz. "Ölçüm sonuçları"). İlk tasarım "fal pydantic
tabanlı, bilinmeyen alan 422 demek" diyordu; ölçüm bunu ÇÜRÜTTÜ — beyan
edilmemiş alan SESSİZCE YOK SAYILIYOR. Bu tabloyu gereksiz değil DAHA gerekli
kılıyor: 422 kendini gösteren bir hata, sessiz yok sayım göstermeyen bir
sapma. Kullanıcı 9:16 seçer, tel isteği kabul eder, video 16:9 döner ve
hiçbir yerde hata okunmaz.

### Referans görsel

`image_url` alanına base64 data URI: `data:image/png;base64,…`. fal bunu
açıkça destekliyor. Yükleme adımı, ikinci kimlik yüzeyi ve CDN ömrü sorunu YOK
— `gemini_client`'ın `inlineData` duruşunun aynısı. `max_refs=1`, yani
`images[0]`; fazlası `app.animate`in kapısında zaten eleniyor.

### Hata eşlemesi

Paylaşılan YÜKLEMLER yeniden kullanılıyor, Türkçe METİNLER fal'a özgü
(`providers.detail_of` docstring'indeki "ŞEKİL paylaşılıyor, MESAJ
paylaşılmıyor" kuralı):

* `providers.detail_of` şekli çözüyor. fal FastAPI tabanlı olduğu için ÜST
  DÜZEY `detail: [{loc, msg}]` listesi de gelebiliyor; bu `fal_client` içinde
  YEREL bir sarmalla okunuyor — `providers.detail_of`un baytları
  Azure/OpenAI/Gemini/FLUX yolunda DOKUNULMADAN kalıyor. Ayrıştırma mantığı
  zaten `providers._madde_metni`nin çözdüğü şekil.
* 401/403 → `providers.is_invalid_key` + "fal.ai anahtarı geçersiz"
* 402 / bakiye → AYRI ve açık metin. fal ön ödemeli; "anahtarını kontrol et"
  demek çalışan bir kurulumu bozmaya davet olurdu (`veo_client`in 403/429
  dalının birebir gerekçesi).
* 429 → eşzamanlılık/kuyruk sınırı. Yeni hesaplar 2 eşzamanlı istekle
  başlıyor; bu AYRI bir cümle, "anahtar" cümlesi değil.
* `providers.is_content_policy` → Wan'ın `enable_safety_checker`'ı ve Kling'in
  filtresi.
* `COMPLETED` ama `video` yok → ham `KeyError` DEĞİL, Türkçe `ImageError`
  (`azure_flux_client.decode_images`in kararı: sarmalanmayan bir `KeyError`
  `app.py`'nin süzgecinden geçer ve kullanıcı beklemenin sonunda yalnızca
  "Hata (500)" görür).
* Beklenmeyen şekil → aynı şekilde sarmalanıyor.

### Sözleşme

Video sözleşmesi aynen:

```python
generate(m, prompt, size, quality, duration, n, *, client=None,
         credentials=None) -> list[bytes]
animate(m, prompt, images, size, quality, duration, n, *, last_frame=None,
        client=None, credentials=None) -> list[bytes]
```

Kimlik `credstore.resolve("fal")` ile ve FONKSİYONUN İÇİNDE, tembel —
`providers._azure_generate`in yorumundaki belgelenmiş kural ("Yeni adaptörler
kendi kimliğini `credstore.resolve(m.credential)` ile çözüyor — aynı
tembellikle").

## Karar 5 — `providers.py` sevk memuru

```python
def _fal_adapter():
    """`_veo_adapter`ın aynı gerekçesi: `fal_client` bu modülü import ediyor
    (`total_budget`, `detail_of` ve iki paylaşılan yüklem için), yani modül
    düzeyinde import etmek DÖNGÜ olurdu. Düz `import` ifadesi, yalnız fonksiyon
    içinde — PyInstaller'ın statik analizi onu da görüyor."""
    import fal_client
    return (fal_client.generate, fal_client.animate)


_VIDEO_ADAPTERS = {
    "gemini": _veo_adapter,
    "fal": _fal_adapter,
}
```

`_ADAPTERS` DEĞİŞMİYOR. `PROVIDER_LOGOS["fal"] = "fal.svg"` ve
`static/img/providers/fal.svg` — `tests/test_provider_logos.py` eksik dosyada
kırmızı yanıyor ve o dosyanın başlığı sebebi yazıyor: "logo kusurları SESSİZ".

## Karar 6 — Ayarlar arayüzü

`fal_key` kataloğa girince forma gerçekten girmesi gerekiyor:

* `static/index.html`: `#set-provider`'a `<option value="fal">fal.ai</option>`.
  Seçici `sr-only`; gerçek arayüzü `settings.js` `#provider-list`ten kuruyor ve
  kaynağı `secici.options`, yani option eklemek yetiyor.
* Kendi bloğu ve `#set-fal-key` girişi. PAYLAŞILAN tek input YOK —
  `index.html:1262`'nin yasağı ("paylaşılan bir alan sağlayıcı değişince ya
  yazılanı TAŞIR ya da TEMİZLER").
* `static/settings.js`: placeholder üçlüsüne `["set-fal-key", "fal", "…"]`,
  `syncProviderFields`'in elle yazılmış `["azure", "openai", "gemini"]`
  listesine `"fal"`.
* `tests/test_id_contract.py` defterine yeni id kaydı.

## Uygulama sırası — ÖLÇÜM ÖNCE

Kullanıcı fal anahtarını 2026-09-14'te aldı, yani katalog literalleri tahminden
değil ÖLÇÜMDEN doğabilir. **Planın İLK maddesi ölçümdür; katalog literalleri
ancak ondan sonra donar.**

Anahtar sohbete YAZILMIYOR. İki yoldan biri:

* `credentials.env`'e (uygulamanın `paths.py` ile bulduğu dosya) elle
  `FAL_KEY=…` satırı — form alanı henüz olmadığı için bu tur elle; ya da
* kullanıcının kendi kabuğunda ortam değişkeni.

Scratchpad'de TEK KULLANIMLIK bir sonda betiği (depoya GİRMİYOR), deponun kendi
`credstore`'undan okuyup üç uca EN UCUZ isteği atıyor (en kısa süre, en düşük
çözünürlük) ve şunları ölçüyor:

1. `duration` gerçekte hangi değerleri kabul ediyor (5 · 10 · 15)
2. `aspect_ratio` ve `resolution` enum'larının gerçek kabulü
3. Kling i2v `aspect_ratio`'yu GERÇEKTEN reddediyor mu
4. 200 yanıtının gerçek şekli (`video.url` yuvalanması)
5. hata gövdesi `detail` mi `error` mi taşıyor
6. fal'ın fiyat sayfasından saniye başına gerçek ücret

Tahmini maliyet 1 USD altı. Ölçüm sonuçları katalog yorumlarına ve
`fal_client.py` başlığına YAZILIYOR — `azure_flux_client`'ın "FLUX'un 200
YANITI BU DEPODAN GÖRÜLMEDİ" itirafının tekrarlanmaması bu turun açık hedefi.

## Test stratejisi

`tests/test_fal_client.py` — `tests/test_azure_flux_client.py` (259 satır)
kalıbında, sözleşmenin `client=` anahtarının açtığı `FakeClient` dikişiyle:

* mutlu yol: submit → IN_QUEUE → IN_PROGRESS → COMPLETED → sonuç → indirme
* **adres kurma mandalı**: gövdeye düşmanca bir `status_url` konur; iddia,
  isteğin oraya GİTMEDİĞİdir
* indirmenin ANAHTARSIZ olduğu
* yönlendirmenin elle izlendiği ve tavanın çalıştığı
* alan tablosu: Kling i2v isteğinde `aspect_ratio`/`resolution` YOK,
  Wan t2v'de VAR
* `image_url`'ün `data:image/png;base64,` ile başladığı
* hata dalları: 401 · 402 · 429 · içerik reddi · COMPLETED-ama-video-yok ·
  beklenmeyen şekil
* sahte saatle duvar saati aşımı

Mevcut dosyalara eklenenler:

* `tests/test_catalog.py` — `fal` + `supports_edit` → `wire_model_edit` boş
  olamaz; kredi sırası artan; `FAL_VIDEO_ASPECT_RATIOS` beyanı
* `tests/test_providers.py` — `fal` yalnız `_VIDEO_ADAPTERS`'te, `_ADAPTERS`'te
  DEĞİL
* `tests/test_settings_route.py` — `fal_key` gidiş-dönüşü ve redaksiyon
* `tests/test_provider_logos.py` — dosya geldiği için kendiliğinden yeşil
* `tests/test_video_onyuz.py`, `tests/test_id_contract.py`
* `tests/test_graflar.py` — graf kapısı

## Belgeler

* `python tools/graf_uret.py` — değişen graf dosyaları AYNI commit'in İÇİNDE
  (CLAUDE.md §2).
* `README.md` ve `README.en.md` — "Güncel Özellikler" video bölümü artık tek
  sağlayıcı anlatmıyor.
* `docs/ozellikler.md` — üç yeni model, 15 saniyelik klip ekseni ve fal'ın ön
  ödemeli olduğu notu.

## Ölçüm sonuçları (2026-09-14, canlı uçtan)

Sonda `credentials.env`'deki gerçek `FAL_KEY` ile `queue.fal.run`'a üç model
için en ucuz isteği attı (Wan/PixVerse tamamlandı, Kling t2v tamamlandı) ve
yalnız GERÇEKTEN belirsiz iki jetonu (Wan `duration=10`, Kling i2v
`aspect_ratio`) test etti — geri kalanı (PixVerse/Kling'in 15 saniyeye kadar
`duration`'ı, üç modelin de 1:1 oranı) şema zaten AÇIKÇA saydığı için kesin
kabul edildi, parayla yeniden doğrulanmadı (bkz. betiğin baş yorumu).

| model | kabul edilen `duration` | `aspect_ratio` | `resolution` | USD/sn |
| --- | --- | --- | --- | --- |
| Wan 3.0 | 5 (tamamlandı), 10 (kabul edildi — jeton sondası kuyrukta iptal edildi, tamamlanmadı) | 16:9 (tamamlanan videonun 854×480 çözünürlüğü oranı doğruluyor) | 480p (tamamlandı) | 480p **$0,05**; 720p **$0,10**; 1080p **$0,20** ([fal.ai model sayfası](https://fal.ai/models/alibaba/wan-3.0/text-to-video)) |
| PixVerse C1 | 5 (tamamlandı); 10/15 ayrıca sondalanmadı — şema `duration`ı 1–15 AÇIKÇA sayıyor, kesin | 16:9 (tamamlandı) | 360p (tamamlandı) | 360p **$0,030** sessiz / $0,040 sesli; 540p $0,040/$0,050; 720p $0,050/$0,065; 1080p **$0,095**/$0,120 ([fal.ai model sayfası](https://fal.ai/models/fal-ai/pixverse/c1/text-to-video)) |
| Kling V3 Turbo Pro | 5 (tamamlandı, t2v); 10/15 ayrıca sondalanmadı — şema `duration`ı 3–15 AÇIKÇA sayıyor, kesin | 16:9 (tamamlandı, t2v) | (yok — gizli tek jeton, tel'e hiç gönderilmiyor) | **$0,14** düz (çözünürlükten bağımsız) ([fal.ai model sayfası](https://fal.ai/models/fal-ai/kling-video/v3/turbo/pro/text-to-video)) |

200 yanıtının şekli: **modele göre FARKLI**, ama üçü de `video.url` yuvalanmasını
paylaşıyor —

* Wan: `{"video": {"url","content_type","file_name","file_size","width","height","fps","duration","num_frames"}, "seed", "duration", "actual_prompt"}`
* PixVerse / Kling: `{"video": {"url","content_type","file_name","file_size"}}` (Wan'daki ek alanlar yok)

Hata gövdesinin anahtarı: `detail` — FastAPI'nin standart listesi
(`[{"loc": [...], "msg": ..., "type": ..., "url": ..., "input": ...}]`).
Gözlem bir `duration`/`aspect_ratio` reddinden değil, Kling i2v sondasının
bozuk referans görüntüsünden geldi (`image_load_error`); yine de `detail`
anahtarının biçimi bu depoya güvenle yazılabilir kadar nettir.

Kling i2v `aspect_ratio`'yu GERÇEKTEN reddediyor mu: **HAYIR — şema
doğrulaması düzeyinde reddetmiyor.** İstek `aspect_ratio` alanıyla (i2v
şemasında o alan yokken) şema doğrulamasını GEÇTİ; 422 aldık ama hatanın türü
`image_load_error` — yani sondanın test görüntüsü (1×1 saydam PNG) fal'ın
görüntü çözümleyicisi tarafından reddedildi, alanın kendisi DEĞİL. Bilinmeyen
alan bir "extra input değil" hatasıyla değil, tamamen farklı bir hatayla
karşılandı; bu, `fal_client.py`'nin "tabloda olmayan hiçbir alan
gönderilmiyor, fal pydantic tabanlı, bilinmeyen alan 422 demek" varsayımının
en azından bu uçta YANLIŞ olduğunu gösteriyor — fal muhtemelen bilinmeyen
alanları sessizce YOK SAYIYOR. Sonuç: adaptör alan tablosuna UYMAK hâlâ doğru
disiplin (yanlışlıkla eklenen bir alan artık "422 ile yakalanır" diye
GÜVENİLEMEZ), ama testlerin bunu 422 bekleyerek DEĞİL, gönderilen JSON gövdesini
doğrudan inceleyerek doğrulaması gerekiyor.

Bu yalnız ŞEMA DOĞRULAMASI düzeyinde bir yanıt — DAHA DERİN soru AYRI ve
ÖLÇÜLEMEDİ: alanın Kling i2v'nin çıktısını GERÇEKTEN etkileyip etkilemediği
(örn. gönderilen `aspect_ratio` çıktı oranına yansıyor mu, yoksa şema
doğrulamasını geçtikten sonra sunucu tarafında da mı sessizce yok sayılıyor)
ölçülemedi, çünkü üretim görüntü hatasından ötürü hiç başlamadı. "Şemayı
geçiyor" ile "işlevsel olarak etkili" İKİ AYRI iddia; burada yalnız birincisi
kanıtlanmıştır.

**Beklenmeyen bulgu — status/cancel adresi TABAN+TAM YOL'dan kurulamıyor.**
Karar 4'ün "adres YANITTAN alınmıyor, TABANDAN kuruluyor" güvenlik kararı
DOĞRU kalıyor, ama kurma KURALI yanlış ölçülmüştü: gerçek `status_url` /
`cancel_url` / `response_url`, gönderilen tam tel yolunun (`.../text-to-video`
dahil) yalnız İLK İKİ segmentini (`sahip/uygulama`) taşıyor, uç adı DÜŞÜYOR.
Örnek: `fal-ai/pixverse/c1/text-to-video`'ya gönderilen istek
`.../fal-ai/pixverse/requests/{id}/status` adresinden yoklanıyor —
`c1/text-to-video` yok. Bu YANLIŞ varsayımla kurulan adresler PixVerse ve
Kling'in izleme döngüsünde 600 sn boyunca boş gövde döndürdü (betik bunları
zaman aşımına uğrattı) ve iki jeton sondasının iptal `PUT`'u 405 ile geri
döndü; üçü de betik dışında elle kurulmuş 2-segmentli adreslerle düzeltildi.
**Görev 4'e taşınacak bulgu:** `fal_client.py` `status`/`cancel`/`sonuç`
adresini `wire_model`'in İLK İKİ segmentinden türetmeli, tam yoldan değil.

**Maliyet:** Üç DENEME tamamlandı (Wan 5,038 sn×480p ≈ 0,25 USD + PixVerse
5 sn×360p ≈ 0,15 USD + Kling 5 sn ≈ 0,70 USD ≈ **1,10 USD**); Wan `duration=10`
jeton sondası kuyrukta iptal edildi (muhtemelen faturasız); Kling i2v sondası
üretime hiç başlamadan görüntü hatasıyla düştü (muhtemelen faturasız, teyit
edilemedi — fal'ın fatura dökümüne bu betikten erişilmedi). Toplam tahmini
**~1,10 USD**, brief'in "1 USD altı" tahmininin hafifçe üzerinde — Kling'in düz
$0,14/sn'sinin diğer ikisinden pahalı çıkması bunun sebebi.

Katalog literalleri (Görev 7) YALNIZ bu tablodan yazıldı.

**EK ÖLÇÜM — kuyruk girişinin HTTP durumu SABİT DEĞİL (Görev 8, canlı duman
testi).** Yukarıdaki sonda 2026-09-14'te `POST …/text-to-video`e `200`
almıştı. Görev 8'in canlı duman testi bir gün sonra (2026-09-15) AYNI uca
`202 Accepted` aldı. fal ya yüke/kuyruk durumuna göre ikisi arasında geçiyor
ya da davranış değişti — hangisi olursa olsun kod herhangi bir `2xx`'i kabul
etmek ZORUNDA (`fal_client._basarili`, yalnız `== 200` DEĞİL). İlk sürümde
kod yalnız `200`ü başarı sayıyordu; bu, Görev 8'in bulduğu ve `a512029`'un
kapattığı gerçek bir kusurdu (kaynak: bu spec'in yazıldığı gün atılan sonda
201/202'yi hiç görmemişti, yani ilk tasarım bu davranışı ÖLÇMEDEN varsaydı).

## Riskler

| risk | azaltma |
| --- | --- |
| fal kuyruğu bölgeselleşirse yeniden kurulan adres yanlış hosta gider | Tek satır; `fal_client` başlığında işaretli. Belirti net: 404. |
| Ölçüm bir jetonu yanlış çıkarırsa katalog yanlış beyan eder | Ölçüm planın İLK maddesi; literaller ondan sonra donuyor. |
| Kredi tahmini gerçek fiyattan sapar | Yukarı yuvarlandı; ölçüm adımında fiyat sayfasından teyit. |
| `fal_client._guvenli_hedef_mi` DNS ÇÖZMÜYOR (TOCTOU'dan kaçınmak için bilinçli) — yalnız adresin METNİ denetleniyor | Kabul edilmiş tasarım sınırı: `nip.io` gibi görünüşte sıradan ama loopback'e çözülen bir konak adı kapıdan METİN düzeyinde geçer (host literal bir IP ise private/loopback/link-local elenir, alan adıysa yalnız TLD'nin harfle başlaması denetlenir — bkz. `_alan_adi_mi`). Ad çözümlemesi yan etkili ve TOCTOU açığı taşıdığı için bilinçli olarak yapılmıyor. |
| fal modelleri hızla ad değiştirir (`preview` kuyrukları) | `wire_model` ile `id` zaten AYRI (`ImageModel.id` docstring'i); geçmiş kayıtlar anlamsızlaşmıyor. |
| Yeni hesabın 2 eşzamanlı istek sınırı kullanıcıyı şaşırtır | 429 için AYRI Türkçe metin. |

## Ölçüm sonuçları (2026-09-15, Görev 8 — canlı duman testi, görsel→video)

Görev 7'nin teslimi sonrası görsel→video hiç canlı sınanmamıştı. Görev 8 DÖRT
turda tamamlandı (üçü düştü, dördüncüsü BAŞARILI oldu) — tam gidişat
`.superpowers/sdd/2026-09-14-fal-video-saglayicisi/task-8-report-v3.md`de:
1) `422 Field required: start_image_url` (Wan'ın alan adı `image_url` DEĞİLDİ
— bu tasarımın "Uç → alan tablosu"ndaki Wan i2v satırı YANLIŞTI, kaynağı hiç
canlı sınanmamış bir varsayımdı); alan adı `643f545`'te düzeltildi. 2) oturum
sınırı (kod kusuru değil). 3) `422 Image dimensions are too small. Minimum
dimensions are 240x240 pixels.` — düzeltilmiş alan adı DOĞRU gitti ama test
görseli (8×8 piksel) fal'ın kendi alt sınırının altındaydı. 4) **BAŞARILI**:
512×512 piksellik gerçek bir referans kareyle `POST /api/video/animate`
(model `fal-wan-3-0`, 5 sn, 480p, 16:9) uçtan uca tamamlandı —

| adım | HTTP durumu |
| --- | --- |
| submit | 200 |
| yoklama (14 tur) | 13× 202, son turda 200 |
| sonuç | 200 |
| indirme (`v3b.fal.media`) | 200 |
| `/api/video/animate` uç yanıtı | 200 |

`request_id = 01a0a586-7de0-7d61-8bae-89cc60ab86c0`. Geçen süre 103,05 sn;
MP4 1.543.287 bayt; `credits=50` (480p×5sn×10 kredi/sn), tahmini **0,25
USD**. Bu, `643f545`'in `start_image_url` düzeltmesinin canlı üretimle UÇTAN
UCA doğrulandığı anlamına geliyor.

**(f) DÜRÜSTLÜK NOTU.** Üç modelden yalnız **Wan 3.0** canlı doğrulandı — iki
yönde de (metin→video 2026-09-14, görsel→video 2026-09-15, yukarıdaki
tablo). **PixVerse C1 ve Kling V3 Turbo Pro'nun tel alan adları yalnız fal'ın
OpenAPI şemasından ölçüldü**
(`.superpowers/sdd/2026-09-14-fal-video-saglayicisi/olcum-uc-semalari.md`,
2026-09-15), canlı üretimle sınanmadı — ikisinin de görsel→video denemesi
bütçe dışında kaldı (Kling 5 sn ~0,70 USD, PixVerse ~0,33 USD). Kling'in
`duration`ının dize (`"5"` gibi) gitmesi de aynı şemaya dayanıyor, canlı bir
422'ye değil.

**(g) ÖLÇÜLEN SAĞLAYICI SINIRI.** PixVerse ve Kling'in görsel→video
uçlarında `aspect_ratio` alanı ŞEMADA HİÇ YOK — oranı ilk kareden türetiyorlar
(`olcum-uc-semalari.md`). Ama composer'ın oran seçici arayüzü canlandırma
yönünde de bu iki model için oran sunuyor: kullanıcının seçtiği oran bu iki
modelde TEL ÜZERİNDE ETKİSİZ (istek kabul edilir, video ilk karenin oranında
döner). Wan'da böyle değil — Wan'ın i2v ucu `aspect_ratio`'yu gerçekten
kabul ediyor (`fal_client.ALANLAR["fal-wan-3-0"].gorsel`). Arayüzü yöne göre
kısmak (PixVerse/Kling animasyon modunda oran seçiciyi gizlemek) AYRI bir
iş; bilinen sınır olarak burada duruyor, bu turda dokunulmadı.

**(h) ÖLÇÜLEN SINIR — referans karenin ALT piksel boyutu.** fal,
`start_image_url` (Wan) için görselin **en az 240×240 piksel** olmasını
istiyor — 2026-09-15'te canlı ölçüldü (üçüncü deneme, madde 3 yukarıda).
`app.py`nin `_to_png`/`_check_video_form`'u yüklenen görsel için yalnız
DOSYA BOYUTU ve MIME'ı sınıyor, bir ALT piksel-boyutu denetimi YOK — yani
küçük bir görsel yükleyen kullanıcı bugün fal'ın İngilizce 422 mesajını
görür. Bu Görev 8'in yarattığı bir kusur DEĞİL ve Veo yolu da aynı açığı
taşıyor; `app.py`yi tüm sağlayıcılar için değiştirmek bu görevin kapsamını
aşardı. Bilinen sınır / ileride yapılacak iş olarak kayıtta duruyor, kod
BU TURDA değiştirilmedi.
