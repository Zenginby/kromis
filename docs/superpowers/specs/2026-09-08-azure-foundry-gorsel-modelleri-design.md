# GPT-Image Studio — Azure Foundry görsel modelleri (MAI + FLUX.2)

**Tarih:** 2026-09-08
**Durum:** tasarım onaylandı (yaklaşım A), plana geçiliyor

## Problem

Kullanıcının Azure kaynağında (`ai-ornek-swedencentral`) bugün **altı** görsel modeli
dağıtılmış durumda, ama uygulama yalnız birini konuşabiliyor:

| Dağıtım | Format | Uygulamada |
| --- | --- | --- |
| `gpt-image-2` | OpenAI | ✅ `azure-gpt-image-2` |
| `MAI-Image-2.6` | Microsoft | ❌ |
| `MAI-Image-2.6-Flash` | Microsoft | ❌ |
| `MAI-Image-2.5-Pro` | Microsoft | ❌ |
| `FLUX.2-pro` | Black Forest Labs | ❌ |
| `FLUX.2-flex` | Black Forest Labs | ❌ |

Beşi de PARASI ÖDENEN, ayakta duran dağıtımlar; uygulama onlara ulaşamadığı için
kullanıcı Foundry portalına gidip elle üretmek zorunda.

Kodun bugünkü hâli tek Azure modeline kilitli ve bu BİLİNÇLİ: `azure_client.py:15`
`MODEL_NAME = "gpt-image-2"` sabitini `build_payload`'a gömüyor,
`providers._azure_generate` de model tanımını açıkça düşürüyor ("tel üzerindeki
baytları değişmemiş bir fonksiyon üretmeye devam ediyor" güvencesi).

## Hedef

1. Beş modeli kataloğa almak ve gerçekten çalıştırmak (üretim + düzenleme).
2. Her modelin `note` alanına **hangi durumda bu seçilir** cümlesi yazmak.
   Alan zaten var ve `static/core.js:1578` onu seçicide model adının ALTINA
   yazıyor — yeni bir alan ya da arayüz işi GEREKMİYOR.
3. `azure_client.py`'ye HİÇ dokunmadan yapmak: kayıtlı Azure kullanıcısı için
   sıfır davranış değişikliği güvencesi yerinde kalsın.

## Kapsam dışı (bilinçli)

* Kaynakta **dağıtılmamış** modeller: `FLUX.1-Kontext-pro`, `FLUX-1.1-pro`,
  `MAI-Image-2.5`, `MAI-Image-2.5-Flash`. Katalogda olmayan dağıtım 404 üretir;
  `openai-dall-e-3`'ün ölçülmüş dersi bu.
* Video tarafı (`VIDEO_MODELS`) — bu spec yalnız `IMAGE_MODELS`.
* Kredi ledger'ı. Krediler bugün olduğu gibi yalnız metadata kalıyor.
* MAI 2.6'nın `auto_aspect_ratio` ve `web_grounding` bayrakları — ikisi de
  gerçek yetenek ama yeni birer eksen; bkz. "Sonraya bırakılan".
* FLUX'un `seed`, `safety_tolerance`, `prompt_upsampling` parametreleri.

## Doğrulanmış sözleşme (canlı sonda, 2026-09-08)

Aşağıdaki tablonun tamamı kullanıcının KENDİ kaynağına atılan gerçek isteklerle
ölçüldü. Ölçüm yöntemi bilerek üretimsizdi: `prompt` eksik, `prompt` yanlış
tipte, ya da alanlar yanlış tipte gönderildi — doğrulayıcı modele ulaşmadan
reddetsin diye.

| | `gpt-image-2` (mevcut) | MAI ×3 | FLUX.2 ×2 |
| --- | --- | --- | --- |
| host | `<res>.openai.azure.com` | `<res>.services.ai.azure.com` | `<res>.services.ai.azure.com` |
| yol | `/openai/v1/images/generations` | `/mai/v1/images/generations` | `/providers/blackforestlabs/v1/<model-path>?api-version=preview` |
| model-path | — | — | `flux-2-pro` · `flux-2-flex` (dağıtım adı DEĞİL) |
| dağıtım adı | gövdede `model` | gövdede `model` | gövdede `model` |
| geometri | `size:"1024x1024"` | `width`+`height` (int) | `width`+`height` (int) |
| geometri sınırı | 3 sabit jeton | w,h ≥ 768 **ve** w·h ≤ 1.048.576 | ≤ 4 MP |
| kalite | `low`/`medium`/`high` | **yok** | **yok** (flex'te `steps`+`guidance`) |
| adet | `n` ≤ 4 | **yok** (hep 1) | `num_images` |
| düzenleme | multipart `/images/edits` | multipart `/mai/v1/images/edits`, **1** görsel | aynı gövde, `input_image`, `input_image_2`… (pro 8, flex 10) |
| yanıt | `data[].b64_json` | `data[].b64_json` | `data[].b64_json` |
| yoklama | yok | yok | **yok** (senkron) |
| hata | OpenAI `error.message` | `error.code`+`message`+`details` | 422, `error.details[]` listesi |

**Kanıtlanan iki şey, ikisi de tasarımı belirliyor:**

1. **`/openai/v1` bu beş modeli SERVİS ETMİYOR.** Şema doğrulamasını geçen
   istek `"Model not supported with Responses API"` ile düşüyor. Sebep Entra
   sondasıyla kanıtlandı — iki AYRI veri eylemi:
   `Microsoft.CognitiveServices/accounts/**OpenAI**/images/generations/action`
   ve `…/accounts/**MaaS**/images/generations/action`. Yani bu modelleri
   `gpt-image-2`'nin ikizi olarak beyan etmek, `catalog.py`'nin uyardığı
   "arayüzde seçilebilir bir 400"ün tam kendisi olurdu.
2. **Aynı `api-key` üç yüzeyde de geçiyor.** Kullanıcıdan İKİNCİ bir anahtar
   istemeye gerek yok; değişen tek şey HOST.

**Ölçülmedi, varsayılmayacak:** FLUX'un 200 yanıtı bu depodan canlı
görülmedi — şekli Microsoft'un kendi örnek deposundan alındı
(`data[0]['b64_json']`, senkron). FLUX'un gerçek boyut jetonu kabulü ve
`num_images`'ın üst sınırı da ölçülmedi. Bkz. "Açık kalemler".

**Sondanın bedeli:** MAI'nin `size` diye bir parametresi OLMADIĞI için
`size:"1x1"` sessizce yutuldu ve **iki gerçek MAI görseli üretildi**
(1024×1024, birkaç sent). Bu bir kaza değil bulgu: aşağıdaki 4. karar buradan
çıktı.

## Kararlar

### 1. İki yeni adaptör modülü, mevcut Azure yolu dokunulmamış

`azure_mai_client.py` ve `azure_flux_client.py` — **kökte ve düz**.
`providers.py`'nin ve `catalog.py`'nin başlığında yazılı Chaquopy kuralı:
`android/app/build.gradle` kaynak kümesini `include "*.py"` ile kuruyor, alt
paket APK'ya girmez ve hata YALNIZ telefonda görünür.

Reddedilen iki alternatif:

* **Tek `azure_foundry_client.py`, içinde iki dal** — tek modül iki tel
  formatı taşırdı, hata eşlemesi bulanıklaşırdı ve `PROVIDER_LOGOS` tek
  anahtara düşerdi (6. kararla çelişir).
* **Mevcut azure adaptörünü genişletmek** — `build_payload`'ın donmuş
  sözleşmesini (`tests/test_azure_client.py`) ve baytların değişmezliği
  güvencesini kırardı.

`providers._ADAPTERS`'e iki satır: `"azure-mai"` ve `"azure-flux"`. Tabloya
girmeyen bir sağlayıcı çalışma anında "bilinmeyen sağlayıcı" veriyor, sessizce
Azure'a DÜŞMÜYOR — o mandal olduğu gibi kalıyor.

Adaptörler `providers.py`'nin yazılı sözleşmesine uyuyor: `generate(m, prompt,
size, quality, n, *, client=None, credentials=None) -> list[bytes]` ve
`edit(...)`. Kimliği KENDİ içlerinde, tembel biçimde çözüyorlar
(`credstore.resolve(m.credential)`) — `_azure_generate`'in yorumundaki 104
testlik ders.

### 2. Tek yeni `Credential`, anahtar mevcut Azure kimliğine düşüyor

```python
Credential(
    id="azure_foundry",
    label="Azure AI Foundry · MAI ve FLUX",
    key_env="AZURE_FOUNDRY_API_KEY",
    url_env="AZURE_FOUNDRY_BASE_URL",
    secret_field=None,          # forma GİZLİ alan eklenmiyor
    url_field="azure_foundry_base_url",
)
```

`credstore.resolve`'a `azure_chat` dalının ikizi olan bir dal: **anahtar yoksa
`AZURE_IMAGE_API_KEY`'e düşer**. Sonda bunun canlı doğru olduğunu gösterdi
(tek anahtar üç yüzeyde de geçiyor) ve bu, deponun zaten kurduğu desen.

**Adres iki kademeli çözülüyor:**

1. `AZURE_FOUNDRY_BASE_URL` doluysa o kullanılır (kullanıcı elle yazabilir).
2. Boşsa `AZURE_IMAGE_BASE_URL`'ün HOST'undan türetilir.

Türetme bir tablodur, dize ameliyatı değil — ve yalnız TANINAN üç kalıpta
çalışır:

| tanınan host | türetilen |
| --- | --- |
| `<res>.openai.azure.com` | `https://<res>.services.ai.azure.com` |
| `<res>.cognitiveservices.azure.com` | `https://<res>.services.ai.azure.com` |
| `<res>.services.ai.azure.com` | aynısı |

Tanınmayan bir host (vekil, özel alan adı) türetmez; Türkçe bir hata
`AZURE_FOUNDRY_BASE_URL`'ü ADIYLA ister. Sessiz düşme YOK — `credstore`'un
mevcut hata metinlerinin duruşu bu. Türetme tablosunu bir test donduruyor.

`secret_field=None` bilinçli: Ayarlar formuna gizli alan eklenmiyor, çünkü
anahtar zaten düşüyor. Forma giren TEK yeni alan `azure_foundry_base_url` ve o
da gizli değil — yani `app._redact_validation_errors`'ın katalogdan türettiği
redaksiyon kümesi değişmiyor.

### 3. Geometri tek alanda kalıyor — yeni katalog alanı YOK

`sizes` demetinde jetonlar `"1024x1024"` biçiminde STRING kalır; adaptör
`x`'ten bölüp `width`/`height` int'lerine çevirir. Kazanç: `ResultParams.size`,
`history.json` kayıtları, `storage.save` ve `core.js`'in oran-taşıma kademesi
HİÇ değişmiyor. Bu, `ImageModel.sizes` docstring'inde Gemini için verilen
kararın aynısı — "jeton, piksel değil".

**MAI'nin jetonları YENİDEN SEÇİLİYOR**, gpt-image-2'den kopyalanmıyor. Sebep
sert: uygulamanın `1024x1536` ve `1536x1024` jetonları 1.572.864 piksel eder,
MAI'nin tavanı 1.048.576 — yani kopyalamak iki jetonu doğrudan 400'e sokardı.
Bütçeye uyan ve mevcut oranları KARŞILAYAN küme:

| jeton | piksel | oran |
| --- | --- | --- |
| `1024x1024` | 1.048.576 | 1:1 |
| `1024x768` | 786.432 | 4:3 |
| `768x1024` | 786.432 | 3:4 |
| `1248x832` | 1.038.336 | 3:2 |
| `832x1248` | 1.038.336 | 2:3 |
| `1365x768` | 1.048.320 | 16:9 |
| `768x1365` | 1.048.320 | 9:16 |

Hepsi w,h ≥ 768 ve w·h ≤ 1.048.576. `default_size="1024x1024"` AÇIKÇA yazılı.

**FLUX mevcut üç jetonu aynen kullanabiliyor** (`1024x1024`, `1024x1536`,
`1536x1024`): üçü de ≤ 4 MP ve 32'nin katı. Kazanç somut — gpt-image-2'den
FLUX'a geçen kullanıcı "varsayılana düşüldü" uyarısı ALMIYOR.

### 4. Kalite ekseni: MAI ve FLUX.2-pro'da gizli, FLUX.2-flex'te gerçek

MAI ve FLUX.2-pro'nun `quality` parametresi YOK. `ImageModel.qualities`
docstring'inin tarif ettiği desen uygulanıyor: tek sentetik jeton +
`quality_hidden=True`. Boş bırakmak `ResultParams`'ta 422 demek, yani o
modelle üretilmiş bir oturumun bir daha kaydedilememesi.

**FLUX.2-flex'te ise gerçek bir eksen var** ve sentetik jeton israf olurdu:
belgelenmiş `steps` (≤50, varsayılan 50) ve `guidance` (1.5–10, varsayılan
4.5) parametreleri kaliteyi doğrudan belirliyor. Eşleme:

| jeton | `steps` | `guidance` |
| --- | --- | --- |
| `hızlı` | 10 | 3.0 |
| `dengeli` | 25 | 4.5 |
| `detaylı` | 50 | 6.0 |

`credits_by_quality` doğrudan bu jetonlara oturuyor.

**Bu kararın ikinci yarısı bir kapı:** MAI hatalı `size`/`n` gönderildiğinde
400 DÖNMÜYOR, sessizce varsayılanla üretiyor (sondada ölçüldü). Yani sağlayıcı
artık bir doğrulama katmanı DEĞİL — `models.check_capabilities` bu modeller
için TEK kapı. Katalogdaki `sizes` demeti eksik ya da yanlışsa kullanıcı hata
değil, **istemediği boyutta bir fatura** görür. Bu yüzden 3. karardaki jeton
listesi bir kolaylık değil, güvenlik sınırı — ve testi de öyle yazılacak.

### 5. Adet: MAI'de döngü, FLUX'ta tek

Hiçbir yeni modelde `n` yok — MAI'de parametre hiç mevcut değil, FLUX'ta
`num_images` var ama üst sınırı ölçülmedi. İkisi de `images_per_request=1`
beyan ediyor, yani adet başına AYRI istek atılıyor.

Bu bir döngüden fazlası: `ImageModel.images_per_request` docstring'inin
söylediği gibi ZAMAN AŞIMI politikasını da değiştiriyor.
`azure_client.read_timeout_for`'un `180+120*(n-1)` formülü "n görsel tek
POST'ta döner" varsayımına dayanıyor ve burada o varsayım YANLIŞ —
`providers.read_timeout_for`'un adet-başına-ayrı-istek dalı devreye giriyor
(bugün tek gerçek kullanıcısı Gemini).

| model | `max_n` | gerekçe |
| --- | --- | --- |
| MAI ×3 | 4 | `models.MAX_IMAGES_PER_RUN` tavanı; dört ayrı istek |
| FLUX ×2 | **1** | `num_images` tavanı ölçülmedi; eksik beyan bir yeteneği kullanmamak, fazla beyan seçilebilir bir hata |

FLUX'un düşük kapasitesi (dağıtımda 4, belgelenmiş RPM'de flex için 5/dk) bu
temkinli `max_n=1`i ayrıca destekliyor: dört paralel istek 429'a girerdi.

### 6. Marka: gerçek üretici

`PROVIDER_LOGOS`'a iki satır (`azure-mai` → `microsoft.svg`, `azure-flux` →
`blackforestlabs.svg`), `PROVIDER_BRANDS`'e "Microsoft" ve "Black Forest Labs".
`tests/test_provider_logos.py` adaptörü olan her sağlayıcı için dosya arıyor,
yani SVG'ler bu turda üretilecek. Dosyaların uyması gereken sözleşme o testte
yazılı ve hepsi sessiz kusur mandalı:

* geçerli XML (yorumda **çift tire yasak**),
* kökte `viewBox=`, `width=`, `height=`,
* `currentColor` YOK, `#e8eaed` rengi VAR,
* `static/img/providers/` altında ve `PROVIDER_LOGOS`'ta karşılığı olacak
  (öksüz dosya da testi kırıyor).

`label` alanı yine markayı taşıyor (`"Microsoft · MAI-Image 2.6"`), çünkü hata
metinleri ve `#model-note` ondan okuyor; şerit satırında `_drop_brand` öneki
zaten düşürüyor.

### 7. Kredi tarifesi

Çapa değişmiyor: Azure `medium` = 8 kredi ≈ 0,04 USD.

MAI token bazlı faturalanıyor ve sonda yanıtı ölçüyü verdi:
`usage.num_output_tokens = 1024` (1024×1024 görsel için).

| model | dayanak | kredi |
| --- | --- | --- |
| `MAI-Image-2.6` | 1024 tok × 38 USD/M = 0,0389 USD | **8** |
| `MAI-Image-2.5-Pro` | 1024 tok × 47 USD/M = 0,0481 USD | **10** |
| `MAI-Image-2.6-Flash` | fiyat doğrulanamadı | **4** (geçici) |
| `FLUX.2-pro` | megapiksel başına, oran doğrulanamadı | **16** (geçici) |
| `FLUX.2-flex` | megapiksel başına, oran doğrulanamadı | **10** (geçici) |

Üç "geçici" değer Açık Kalemler'de. Krediler zaten `catalog.py`'nin dediği gibi
"doğrulanacak bir olgu değil, ürün kararı" — ama ORAN yanlışsa seçicideki
karşılaştırma yalan söyler, o yüzden takip ediliyor.

**Kabul edilen yaklaşıklık:** `cost_for`'un boyut ekseni yok, oysa hem MAI
(token = piksel) hem FLUX (megapiksel) boyuta göre faturalanıyor. Kredi,
varsayılan boyuttaki maliyeti gösteriyor. Bunu düzeltmek `cost_for`a üçüncü
bir eksen eklemek demek ve bu spec'in kapsamı dışında.

### 8. Hata eşlemesi — üçüncü bir şekil

FLUX'un 422 gövdesi `error.details[]` listesi taşıyor ve mevcut hiçbir
çözümleyici onu tanımıyor. `azure_flux_client.map_error` bu listeyi tek
Türkçe cümleye indirir (`loc` + `msg`, ilk üç madde). `providers.detail_of`'a
listeyi tanıyan bir dal eklenir.

**FLUX'ta yerleşik içerik filtresi YOK** (Microsoft'un kendi uyarısı). Yani
`providers.is_content_policy` bu sağlayıcıda hiç tetiklenmeyecek; adaptörün
yorumunda bu AÇIKÇA yazılacak ki ileride "neden çalışmıyor" diye aranmasın.

MAI'nin hata gövdesi (`error.code` + `message` + `details`) OpenAI şekline
yeterince yakın — `azure_client.map_error`'ın mantığı `azure_mai_client`'a
kopyalanmıyor, ORTAK bir yardımcıya da çıkarılmıyor: iki satırlık bir
`.get("error", {}).get("message")` zinciri, paylaşılan bir soyutlamanın iki
sağlayıcıyı birbirine kaynatmasından ucuz.

### 9. `note` metinleri

Belgelenmiş konumlandırmadan türetiliyor, uydurulmuyor:

| model | not |
| --- | --- |
| `MAI-Image-2.6` | Fotogerçekçi ürün ve portre işi; metin işlemede MAI'nin en iyisi. |
| `MAI-Image-2.6-Flash` | 2.6'nın hızlı ve ucuz kardeşi; taslak ve deneme turları için. |
| `MAI-Image-2.5-Pro` | Kalabalık sahnelerde nesne ve karakter tutarlılığı; pahalı. |
| `FLUX.2-pro` | En yüksek görsel kalite, 8 referansa kadar düzenleme; yavaş. |
| `FLUX.2-flex` | Adım/yönlendirme ayarlanabiliyor; metin ağırlıklı yerleşimler ve 10 referans. |

Mevcut altı girdinin notları da bu turda gözden geçirilir — yeni satırlarla
aynı soruyu ("ne zaman bunu seçerim") cevaplasınlar diye.

## Mimari — dosya bazında

| dosya | değişiklik |
| --- | --- |
| `azure_mai_client.py` | **YENİ** — `/mai/v1/images/{generations,edits}`; JSON üretim, multipart düzenleme |
| `azure_flux_client.py` | **YENİ** — BFL yolu; `input_image_N` referansları, 422 çözümleyici |
| `static/img/providers/microsoft.svg` | **YENİ** |
| `static/img/providers/blackforestlabs.svg` | **YENİ** |
| `catalog.py` | 5 `ImageModel`, 1 `Credential`, 2 `PROVIDER_LOGOS`, 2 `PROVIDER_BRANDS` |
| `providers.py` | `_ADAPTERS`'e 2 satır + 2 geç bağlama işlevi; `detail_of`'a liste dalı |
| `credstore.py` | `azure_foundry` dalı + host türetme tablosu |
| `models.py` | `SettingsRequest.azure_foundry_base_url` |
| `app.py` | ayarlar rotasında yeni alanın gidiş-dönüşü |
| `static/settings.js` | tek yeni `<input>` ve gövdeye eklenmesi |
| `azure_client.py` | **DOKUNULMUYOR** |
| `docs/graflar/*` | `tools/graf_uret.py` ile yenilenir, AYNI commit'e girer |

## Test

| dosya | ne mandallıyor |
| --- | --- |
| `tests/test_catalog.py` | 5 yeni girdinin alan bütünlüğü; **MAI jetonlarının piksel bütçesi** (w,h ≥ 768 ve w·h ≤ 1.048.576) — 4. karardaki kapı |
| `tests/test_providers.py` | iki yeni sağlayıcının tabloda olması; tabloda olmayanın hâlâ patlaması |
| `tests/test_azure_mai_client.py` | **YENİ** — payload şekli, `x`→int çevirimi, `b64_json` çözümü, multipart düzenleme (mevcut `FakeClient` dikişiyle) |
| `tests/test_azure_flux_client.py` | **YENİ** — model-path eşlemesi (`FLUX.2-pro`→`flux-2-pro`), `input_image_N` sırası, 422 `details[]` çevirisi, flex'in `steps`/`guidance` eşlemesi |
| `tests/test_credstore.py` | host türetme tablosu; tanınmayan hostta Türkçe hata; anahtarın `AZURE_IMAGE_API_KEY`'e düşmesi |
| `tests/test_provider_logos.py` | mevcut — iki yeni SVG onun sözleşmesini geçmek zorunda |
| `tests/test_settings_route.py` | yeni alanın gidiş-dönüşü |
| `tests/test_graflar.py` | mevcut kapı — graflar yenilenmezse KIRMIZI |
| `tests/test_android_packaging.py` | mevcut kapı — iki yeni modül kökte ve düz olmalı |

Canlı çağrı YOK: adaptör testleri `FakeClient` ile, tıpkı
`tests/test_azure_client_http.py` gibi.

## Riskler

1. **FLUX yanıt şekli canlı görülmedi.** Örnek depo `data[0].b64_json` diyor
   ve MAI ile gpt-image-2 de aynı şekli döndürüyor, ama FLUX'un 200'ü bu
   depodan ölçülmedi. Kırılırsa `decode_images` `KeyError` verir. Azaltma:
   adaptör beklenmeyen şekli Türkçe bir `ImageError`'a çeviriyor, ham
   `KeyError` bırakmıyor.
2. **MAI sessiz kabul ediyor.** Katalogdaki bir jeton hatası 400 değil, yanlış
   boyutlu bir fatura üretir. Azaltma: piksel bütçesi testi (yukarıda).
3. **Kapasite asimetrik.** FLUX dağıtımları 4, MAI 10; belgelenmiş RPM'ler de
   düşük (FLUX.2-flex düşük kademede 5/dk). Sonda sırasında FLUX birkaç kez
   `RateLimitReached` yedi. 429 kullanıcıya Türkçe ve ANLAŞILIR dönmeli
   ("kota doldu, biraz bekleyin"), ham 502 değil.
4. **Üç model Preview.** MAI ailesinin üçü de önizleme; ad ya da sözleşme
   haber vermeden değişebilir. `openai-gpt-image-1` girdisinin duruşu
   benimseniyor: notta yazılı, kalkınca girdi silinir.
5. **`preview` api-version'ı sabit değil.** FLUX yolu `api-version=preview`
   alıyor; bu takma ad ileride başka bir şemaya işaret edebilir.

## Açık kalemler

1. `MAI-Image-2.6-Flash`, `FLUX.2-pro`, `FLUX.2-flex` için yayınlanmış birim
   fiyat doğrulanamadı (Azure fiyat sayfaları JS ile çiziliyor, tablo `$-`
   döndü). Tarifedeki üç değer GEÇİCİ. Fiyat bulununca çapaya bölünüp
   düzeltilecek.
2. FLUX'un `num_images` üst sınırı ölçülmedi. İlk turda `max_n=1` beyan
   edilecek — eksik beyan yalnızca bir yeteneği kullanmamak, fazla beyan
   seçilebilir bir hata.
3. FLUX'un gerçek boyut kabulü (32'nin katı mı, alt sınır ne) ölçülmedi;
   mevcut üç jeton belgelenmiş 4 MP tavanının çok altında kaldığı için ilk tur
   güvenli.

## Sonraya bırakılan

* MAI 2.6'nın `auto_aspect_ratio` ve `web_grounding` bayrakları. İkisi de
  gerçek yetenek, ama her biri yeni bir eksen (form alanı + istek modeli +
  sonuç kaydı) — `supports_last_frame`in ayrı bir eksen olarak açılmasının
  gerekçesi burada da geçerli.
* FLUX'un çok referanslı düzenlemesi 8/10 görsele kadar çıkıyor; ilk tur
  `app.MAX_EDIT_IMAGES` (4) tavanında kalıyor.
* `cost_for`a boyut ekseni.
* Kaynakta dağıtılmamış FLUX.1 / MAI-2.5 varyantları.
