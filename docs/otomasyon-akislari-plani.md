# Otomasyon akışları — üret, onayla, yayınla: plan

**Tarih:** 2026-09-23 · **Kaynak:** sahibin fikri ve aynı günkü karar oturumu
(aşağıda "Sahibin kararları") · **Durum:** plan, görev DEĞİL — hiçbir madde bu
belgeyle göreve dönüşmüyor; bir aşama başladığında kendi görev listesi
(`docs/faz*` biçiminde) bu belgeden türetilir · **Yerleşim:** öneri, karar
sahibin — Faz 4 (ödeme/KVKK) bitmeden başlamaz; A0 ve A1 Faz 5 (işletme) ile
paralel gidebilir, ödeme koduna dokunmuyor.

**Fikir (sahibin cümlesi, özet):** n8n gibi; görsel, video ve sohbet
modellerini zincirleyen otomasyonlarla içerik üretmek ve üretileni bağlanan
sosyal medya hesaplarına, depolara ya da tasarım uygulamalarına aktarmak. İkinci
senaryo (aynı gün): bir YouTube üreticisi KENDİ videosunu webhook ile verir;
akış altyazıları çok dilde üretir, videoyu analiz edip başlık seçer, videodan bir
kare alıp kapak hazırlar ve videoyu paylaşır.

Bu belge dört şeyi kaybolmayacağı yere koyuyor: pazarda ne var (araştırma),
hangi entegrasyon yolu gerçekçi (fizibilite), sahibin verdiği kararlar ve üç
bölümlük tasarım. Araştırmadaki her iddia kaynağıyla; doğrulanamayanlar
**doğrulanmadı** diye işaretli. Tarih bağımlı bilgi (fiyat, kota, denetim
kuralı) 2026-09-23'te okundu — aşama başlarken A0 bunları yeniden doğrular.

---

## Sahibin kararları (2026-09-23)

| soru | karar | sonucu |
| --- | --- | --- |
| Kim kullanacak? | **Önce yalnız sahip (iç araç)** | Platform denetimleri (Meta App Review, YouTube audit, TikTok audit) ilk sürümün önünde değil; özellik kapısı başta yalnız admin |
| İnsan onayı? | **Hedefe göre** | Depo/Canva gibi hedeflere aktarım otomatik; sosyal yayın öntanımlı ONAYLI; akış başına `otomatik_yayin` anahtarı |
| İlk hedefler | **Instagram + Facebook, YouTube Shorts** | Depo (Drive/S3), Canva, TikTok → "Sonra" |
| Tetikleyiciler | **Zamanlama, elle, konu listesi, dış tetikleyici** (dördü de) | Webhook + RSS dâhil |
| İçerik türleri | **Tek görsel + açıklama, carousel, kısa dikey video, görsel → video** (dördü de) | Adım türleri buna göre |
| Akış biçimi | **Sıralı adım listesi** (önerilen; düğüm kanvası ve Yönetmen güdümlü ajan reddedildi) | Doğrusal, deterministik, çalışmadan önce kredi tahmini |
| Yayın yolu | **Birleşik API ile başla** (önerilen) | Tek bağlayıcı; resmi bağlayıcılar herkese açılırken |
| Dublaj (video senaryosu) | **Şimdilik yok** | Altyazı + analiz + kapak + yayın ilk sürümde; dublaj "Sonra", üç seçeneğiyle |
| Sohbet modeli (tasarım 1'e ek) | **Kromis Ajanı** — ileride | Aşağıda ayrı bölüm |

Reddedilen iki akış biçiminin gerekçesi: **düğüm kanvası** (n8n / Figma Weave
tarzı) en esnek ama vanilla JS ön yüze bir kanvas düzenleyici, çizge doğrulayıcı
ve zor bir E2E getiriyor; **Yönetmen güdümlü ajan** (akış = doğal dil brief'i,
adımları her çalışmada model seçer) en az arayüzü istiyor ama maliyet ve çıktı
önceden bilinmiyor, test ve tekrar edilebilirlik zayıf. Sıralı listenin veri
modeli (geriye dönük yapısal referanslar) ileride dallı bir çizgeye
büyüyebilir; o gün bu karar yeniden açılır.

---

## Pazar — benzer yapan var mı (araştırma, 2026-09-23)

**Kısaca:** üretim + zamanlama + yayını TEK üründe iyi yapan yok. Güçlü medya
kanvaslarının hiçbirinde zamanlayıcı ya da sosyal yayın yok; yayın araçlarının
üretimi sığ ve şablon kokulu. n8n kullanıcıları boşluğu kendileri kapatıyor
(n8n + Veo/Sora + Blotato/Upload-Post şablonları —
[örnek](https://n8n.io/workflows/11276-generate-and-publish-ai-videos-with-sora-2-veo-31-gemini-and-blotato/)).

| grup | örnekler | bıraktığı boşluk |
| --- | --- | --- |
| Genel otomasyon | **n8n** (OpenAI düğümünde Sora-2, Gemini düğümünde görsel/video; TikTok/IG yerel düğümü yok; Starter €20/ay 2.500 çalıştırma — [pricing](https://n8n.io/pricing/)), **Zapier** (15.06.2026'dan beri AI adımları model katmanına göre 1x/3x/5x görev — [help](https://help.zapier.com/hc/en-us/articles/46597632373389-AI-by-Zapier-new-model-based-pricing-starting-June-15-2026)), **Make** (kredi modeli — [help](https://help.make.com/credits)), **Activepieces** (MIT, kendi sunucunda) | Model başına maliyet ve kalite görünmüyor, önizleme yok, anahtarlar kullanıcıda; adım başı fiyat medya zincirini pahalı yapıyor |
| Düğüm tabanlı yaratıcı kanvas | **Figma Weave** (eski Weavy), **Flora** (API/MCP $18/koltuktan), **Magnific** (Freepik 28.04.2026'da bu adı aldı; Spaces akışı "Flow" olarak paketlenebiliyor), **Krea Nodes** (App Builder), **Runway Workflows** (akış tek tıkla özel API ucu — [help](https://help.runwayml.com/hc/en-us/articles/50085269258643-Publishing-a-Workflow-as-an-Endpoint)), **Comfy Cloud** ([pricing](https://comfy.org/pricing)), Leonardo Blueprints, Higgsfield, Google Flow | Üretim güçlü; tetikleyici, zamanlama ve hedef platform YOK — hepsinde "dışa aktar" |
| Üretim + yayın bir arada | **Blotato** ($29/$97/$499; resmi n8n/Make düğümü ve MCP — [site](https://www.blotato.com/)), **Predis.ai**, **Postiz** (AGPL, ~30 ağ, açık API; AI kotası planda sınırlı — [pricing](https://postiz.com/pricing)), **Opus Clip** (yalnız yeniden kurgu), **HeyGen** (avatar video, yayın yok), **Adobe Express** (ücretsiz planda ayda 1.000 gönderiye kadar zamanlama — [helpx](https://helpx.adobe.com/express/web/publish-and-share/schedule-manage-posts/content-scheduler-overview.html)), Later / Metricool / Hootsuite (üretim yok) | Yayın var, üretim sığ; model seçimi dar |

Doğrulanmadı: Figma Weave'de hiçbir planda API olmadığı (yalnız rakip Wireflow
söylüyor), Canva Content Planner'ın reels zamanlayamadığı, Creatify/Invideo'nun
doğrudan yayını.

**Kromis'in sahiplenebileceği boşluk:**

1. Üretim ve yayın tek, kontrollü akışta — iş kuyruğu, çoklu model ve Prompt
   Yönetmeni zaten burada.
2. **Önce onay, sonra yayın** bir özellik olarak: TikTok'un rıza kuralı ve
   YouTube'un "inauthentic content" politikası (Ocak 2026'da 16 kanal kapandı —
   [TechCrunch](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/))
   tam otomatiği riskli kılıyor; rakipler bunu kullanıcıya bırakıyor.
3. **Çalışmadan önce maliyet tahmini** — katalog kredisi bunu bugün
   hesaplayabiliyor; n8n ve Zapier hiç göstermiyor.
4. Köken bilgisini (C2PA) koruyan boru hattı ve otomatik AI etiketi — AB AI Act
   Madde 50 uyumu satış argümanı olur (aşağıda "Uyum").

---

## Fizibilite — hedeflere bağlanmak

### Sosyal medya, resmi API'ler

| platform | kapı | limit / maliyet | Kromis için anlamı |
| --- | --- | --- | --- |
| **Instagram** | Başkasının hesabına yayın Advanced Access + App Review; Instagram Login ile Facebook Page gerekmiyor ([overview](https://developers.facebook.com/docs/instagram-platform/overview)) | 24 saatte 100 gönderi; medya **herkese açık URL'de** olmalı ([publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)) | Yerel disk kipi URL vermiyor (`dosya.Depo.url` → `None`); nesne deposu ya da birleşik API'ye bayt yükleme |
| **Facebook Pages** | `pages_manage_posts` için App Review + işletme doğrulaması | — | Reels `/video_reels` ucundan |
| **YouTube** | 28.07.2020 sonrası açılmış, denetimden geçmemiş projenin yüklemeleri **private**e kilitli ([audit](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits)) | 01.06.2026'dan beri `videos.insert` ayrı kovada, günde 100 ([revision](https://developers.google.com/youtube/v3/revision_history)) | AI beyanı `status.containsSyntheticMedia` ([videos](https://developers.google.com/youtube/v3/docs/videos)) |
| **TikTok** | Denetimsiz istemci yalnız `SELF_ONLY`, 24 saatte en fazla 5 kullanıcı, hesap gizli olmalı ([guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)) | Jeton başına dakikada 6 istek | Önizleme + açık rıza şart, filigran eklenemez → **gözetimsiz zamanlanmış gönderi kurala aykırı**; doğru yol taslak/inbox yükleme; `is_aigc` alanı var |
| **X** | Kullanım başına ödeme: gönderi $0,015, **URL'li gönderi $0,20** ([pricing](https://docs.x.com/x-api/getting-started/pricing)) | — | Aynı içeriği çok hesaba basmak yasak ([rules](https://help.x.com/en/rules-and-policies/x-automation)) |
| **LinkedIn** | Kişinin kendi akışına `w_member_social` incelemesiz; şirket sayfası Community Management API | Development katmanı 500 istek | — |
| **Pinterest** | Trial katmanında pin'ler yalnız sahibine görünür | Ücretsiz | Standard için demo videolu inceleme |

### Sosyal medya, birleşik yayın API'leri — seçilen yol

Denetimleri kendileri üstleniyor; iç araç için en hızlı yol.

| API | fiyat | YouTube'da | not |
| --- | --- | --- | --- |
| **Upload-Post** | Ücretsiz ayda 10 yükleme; Basic $24 (5 profil), Pro $50 (25 profil) ([pricing](https://www.upload-post.com/pricing-comparison/)) | Kapak (`thumbnail_url`, ≤ 2 MB), **çok dilli altyazı** (`youtube_subtitle_file_N` / `_language_N`), `containsSyntheticMedia` ([docs](https://docs.upload-post.com/api/upload-video/)) | Video senaryosu (A5) için öne çıkıyor |
| **Zernio** (eski Late / getlate.dev) | İlk 2 hesap ücretsiz, sonra hesap başı $6 → $3 → $1 ([docs](https://docs.zernio.com/pricing)) | Kapak var (Shorts'ta yok), **altyazı yükleme yok** ([docs](https://docs.zernio.com/platforms/youtube)) | Medya URL'sinin kimliksiz ve süresiz olmasını istiyor |
| **Ayrshare** | $149 (1 profil) / $299 / $599 ([pricing](https://www.ayrshare.com/pricing/)) | Kapak, tek altyazı parçası | Pahalı |
| Postiz | Açık API, kendi sunucunda | — | Seçenek |
| Buffer API | Yeniden yazılıyor, "early access" | — | Şimdilik dışarıda |

Hiçbirinde YouTube'a **ek ses parçası** yok (aşağıda A5). Seçim A0'ın işi;
bugünkü eğilim **Upload-Post** (altyazı desteği yüzünden).

### Depo ve tasarım uygulamaları ("Sonra")

* **Google Drive:** `drive.file` kapsamı hassas DEĞİL (yalnız uygulamanın
  oluşturduğu / Picker'la seçilen dosyalar) → doğrulama yok; tam `drive` kısıtlı,
  yıllık CASA ister ([Google](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)).
* **Dropbox:** geliştirme modunda ≤ 500 kullanıcı, 50'de iki hafta içinde
  production onayı. **OneDrive:** çok kiracılı yeni uygulamada yayıncı
  doğrulaması. **S3 uyumlu:** kullanıcının anahtarıyla, engel yok.
* **Canva Connect:** varlık yükleme var (`asset:write`; görsel < 50 MB, video
  < 500 MB), ama **URL'den yükleme ucu "preview"** ve preview kullanan herkese
  açık entegrasyon incelemeden geçmiyor → İKİLİ yükleme ucu
  ([docs](https://www.canva.dev/docs/connect/api-reference/assets/create-url-asset-upload-job/)).
* **Figma:** REST API dosyaya görsel YÜKLEYEMİYOR; yalnız eklenti
  (`createImageAsync`) — sunucudan gerçekçi değil.
* **Adobe Express:** Embed SDK işletme onayı istiyor; sunucudan "hesaba gönder"
  REST yolu bulunamadı — gerçekçi değil.
* Kısa yol, herkese açılırken: yönetilen OAuth (Pipedream Connect $99/ay,
  Nango, Composio) onaylı istemci kimlikleriyle incelemeleri hızlandırıyor.

---

## Bugünkü zemin — plan hangi parçaların üstüne konuşuyor

Koda bakılarak (2026-09-23, `main` `664c4e6` — #82 Faz 4 / 5 dâhil):

| parça | nerede | akış için anlamı |
| --- | --- | --- |
| İş kuyruğu (Postgres, `SKIP LOCKED`) | `services/kuyruk.py::ekle`, `services/tablolar.py::IS_TURLERI` (`generate`, `edit`, `video`, `animate`) | Adımların çoğu SIRADAN iş olur; yeni türler (`yazi`, `yayin`, A5'tekiler) CHECK kümesine girer |
| İşçi + bakım turu | `services/isci.py::kos`, `bakim_turu` (ayrı cron YOK — tek sürekli süreç) | Zamanlayıcı ve ilerletme güvenlik ağı buraya bağlanır; yeni süreç yok |
| Kredi defteri (rezerv → onay → iade) | `services/kapilar.py::check_bakiye` / `rezerve_kredi`, `services/defter.py` | Para yolu değişmez; akış yalnız TOPLAM tahmini önceden sorar |
| Planlar, video kuralı | `services/planlar.py::Plan`, `kapsiyor` | `Plan.otomasyon` aynı desenle (bugün `Plan.video`) |
| Şifreli anahtar deposu | `services/sifre.py`, `services/depo_kimlik_bilgisi.py` | OAuth jetonları (resmi bağlayıcılar) aynı şifreyle |
| Nesne deposu + imzalı URL | `services/dosya.py::Depo.url` (yerel kip `None` döner) | IG herkese açık URL istiyor → nesne deposu ya da bayt yükleme |
| SSRF kapısı | `fal_client.py::_guvenli_hedef_mi` | RSS okuma ve A5 video çekme aynı kapıdan |
| Prompt Yönetmeni | `routers/sohbet.py` (`POST /api/chat`), `chat_client.complete` | Bugün **eşzamanlı** ve **kredisiz** (rota defterle konuşmuyor) → işçide `yazi` iş türü; kredi ekseni Kromis Ajanı'yla |
| Sunucuda video aracı YOK | Faz 3 K7: ffmpeg imaja girmiyor (+~100 MB, yeni ikili) | Kare çıkarma / ses birleştirme BARINDIRILAN uçlardan (fal ffmpeg-api) — karar yeniden açılmıyor |
| Hesap silme (Faz 4 / 5, #82) | `routers/hesap.py::sil` (anında: bekleyen işler iptal + rezerv iadesi, BYOK anahtarları, oturumlar/jetonlar, Polar aboneliği), `services/isci.py::silme_turu` (7 gün sonra kiracı satırları ELLE TUTULAN listeyle: `isler`, `medya`, `klasorler`, `sohbetler`, `paletler`, `varliklar`, `tercihler` + nesne öneki) | Yeni tabloların her biri iki listeden birine girmek zorunda — aşağıda "Hesap silme ve dışa aktarma" |
| Veri dışa aktarma (Faz 4 / 5, #82) | `services/disa_aktar.py` — dokuz dosyalık ZIP, yine ELLE TUTULAN liste; `saglayici_meta` dökülmez | Akışlar ve çalışmalar kullanıcının verisi → ZIP'e girer; jeton ve sırlar girmez |

---

## Tasarım 1 — Veri modeli ve çalıştırma motoru

**Yeni tablolar** (tek göç, hepsi kullanıcı başına RLS — bugünkü tabloların
deseni):

* `akislar` — `ad`, `durum` (`etkin` / `duraklatildi`), `tanim` (sürümlü JSON
  `{"surum": 1, "adimlar": [...]}`), `tetik` (tür + ayar), `otomatik_yayin`,
  `sonraki_calisma`, `butce_tavani`.
* `akis_konulari` — konu listesi (`akis_id`, `sira`, `metin`, `kullanildi_at`);
  her çalışma sıradaki kullanılmamışı alır.
* `akis_calismalari` — her çalışma bir satır: `tetik_turu`, `girdi`,
  `tanim_kopyasi`, `kredi_tahmini`, `durum` (`bekliyor → calisiyor →
  onay_bekliyor → yayinlandi` | `hata` | `iptal`), adım durumları. Çalışma
  başlarken tanımın KOPYASINI alır: akışı düzenlemek süren çalışmayı değiştirmez.
* `isler` + boş bırakılabilir `calisma_id`, `adim_no`.

**Adımlar sıradan işlerdir.** Görsel / düzenleme / video / canlandırma adımı
bugünkü kuyrukta normal bir iş: kredi rezerv/onay/iade, filigran kuralı, iş
paneli, saatlik ve günlük tavanlar DEĞİŞMEDEN işler. Yeni para yolu açılmaz.

**Adım türleri (v1):** `yonetmen` (konu → prompt(lar) + açıklama + etiket;
çıktı şemayla doğrulanan JSON; işçide yeni `yazi` iş türü), `gorsel`, `duzenle`,
`video`, `canlandir`, `yayinla`.

**Adımlar arası bağ yapısal referans**, metin şablonu değil:
`{"adim": 2, "indeks": 0}`. Yalnız ÖNCEKİ adımı gösterebilir, kayıtta
doğrulanır → döngü imkânsız.

**İlerletme yeni süreç istemiyor.** İşçi bir iş bittiğinde AYNI işlemde
`akis.ilerlet(calisma)` çağırır ve sıradaki adımı kuyruğa koyar; bakım turu
aynı çağrıyı güvenlik ağı olarak yapar. Benzersizlik kısıtı `(calisma_id,
adim_no, indeks)` iki kez kuyruğa girmeyi imkânsız kılar — iki çağrı yarışsa
bile.

**Zamanlayıcı:** bakım turu zamanı gelmiş akışları `SKIP LOCKED` ile alır,
çalışma açar, `sonraki_calisma`yı hesaplar. Takvim biçimi KISITLI: haftanın
günleri + saat + saat dilimi. Cron ifadesi ve kütüphanesi (yeni bağımlılık)
YAGNI — gerekirse aynı sütuna ikinci bir biçim girer.

**Maliyet ve hata:**
* Çalışmadan önce tahmin = adımların katalog kredisi × adet (× süre). Bakiye
  tahmini karşılamıyorsa çalışma BAŞLAMAZ (`check_bakiye`nin aynı sorusu, tek
  sefer, toplamla); akış başına bütçe tavanı.
* Adım düşerse çalışma `hata`, kalan adımlar koşmaz, düşen işin kredisi bugünkü
  kuralla iade. **Otomatik yeniden deneme YOK** — Faz 2 K8'in gerekçesi aynen
  (çağrının gidip gitmediği bilinmez, çift fatura).

## Hesap silme ve dışa aktarma — Faz 4 / 5 ile uyum

#82 (2026-09-23) hesap silmeyi ve dışa aktarmayı ELLE TUTULAN iki listeyle
kurdu. Akışların getirdiği her tablo bu listelerde yer almak zorunda; yoksa
silinen hesabın akışı zamanlayıcıda çalışmaya, bağlı sosyal hesabı yayına devam
eder.

* **Silme anında** (`routers/hesap.py::sil`, bugünkü "BYOK anahtarları HEMEN"
  deseni): bütün akışlar `duraklatildi`; süren çalışmalar `iptal` (bekleyen
  adım işleri zaten `kuyruk.sahibin_islerini_iptal` ile iade ediliyor —
  `calisma_id`li işler de sıradan iş); webhook jetonları silinir; `baglantilar`
  satırları silinir ve birleşik API'deki bağlı profil KOPARILIR. Koparma dış
  bir çağrı: Polar iptalinin deyimiyle, başarısızlık silmeyi durdurmaz, sahibe
  uyarı düşer.
* **Silme turunda** (`isci.silme_turu`, 7 gün sonra): `akislar`,
  `akis_konulari`, `akis_calismalari` (ve RSS'in görülen öğe kayıtları) kiracı
  bağlamında silinir; A5'in video girdileri zaten `kullanicilar/<id>/`
  önekinde, nesne süpürmesine girer.
* **Dışa aktarmada** (`services/disa_aktar.py`): `akislar.json` (tanım, tetik,
  konular — webhook jetonu HARİÇ), `akis_calismalari.json` (durum, girdi,
  kredi tahmini; `tanim_kopyasi` dâhil). Bağlantılardan yalnız platform ve hesap
  adı; jeton ve profil kimliği girmez. Dosya sayısı dokuzdan on bire çıkar —
  `test_the_export_zip_carries_the_nine_files…` ve "boş hesap" testi birlikte
  güncellenir.
* **Bekçi (A1'de, önce):** bugün iki listeyi koruyan bir KAPSAM testi yok —
  `tests/test_hesap_silme.py` listelerin içeriğini ölçüyor ama yeni bir kiracı
  tablosunun hiçbir listeye girmediğini yakalamıyor. CLAUDE.md §5'in deyimi:
  RLS'li her tablo ya silme turunda ya gerekçeli muafiyette (bugün
  `kredi_hareketleri`, `siparisler` — mali kayıt, K9), ya dışa aktarmada ya
  gerekçeli muafiyette (`saglayici_kimlikleri`, `oturumlar`, `jetonlar` gibi
  sırlar). Bu bekçi akışlardan BAĞIMSIZ olarak da Faz 4 / 5'in bir eksiği; A1
  başlamadan ayrı küçük bir PR olarak gelebilir.

## Tasarım 2 — Bağlantılar, yayın, onay, tetikleyiciler

**Bağlantılar** (`baglantilar` tablosu): birleşik API'nin anahtarı PLATFORMUN
(ortamda, `KROMIS_PLATFORM_…` deseni); kullanıcı sosyal hesabını birleşik API'nin
barındırdığı OAuth sayfasıyla bağlar, biz yalnız profil/hesap kimliğini tutarız.
Resmi bağlayıcılar gelince OAuth jetonları `sifre.sifreci()` ile, anahtarların
şifresiyle aynı.

**Hedef bağlayıcı arayüzü** (`providers._ADAPTERS` deseni), üç işlev:
`dogrula(icerik)` → platform kuralları (IG carousel 2–10, en-boy aralıkları,
açıklama uzunluğu; YT başlık ≤ 100, Shorts dikey), `yayinla(icerik)` → dış kimlik
+ adres, `durum(dis_id)`. Doğrulama İKİ kez: akış KAYDEDİLİRKEN ("16:9 video IG
Reels'e gidiyor") ve yayından hemen önce.

**Yayın da bir iş** (`yayin` türü, aynı kuyruk). Otomatik yeniden deneme YOK
(çift gönderi); dış kimlik saklanır; birleşik API idempotency anahtarı
veriyorsa kullanılır (A0 doğrular). Medya bayt olarak yüklenir (yerel kipte de
çalışır) ya da kısa ömürlü imzalı URL.

**Onay kuyruğu:** sıradaki adım `yayinla` ve `otomatik_yayin` kapalıysa çalışma
`onay_bekliyor`. Onay panelinde her çıktının önizlemesi, düzenlenebilir
açıklama / başlık / etiket, platformun zorunlu alanları (YT: başlık,
görünürlük); **Onayla ve yayınla** · **Zamanla** (saat) · **Reddet** (çalışma
iptal, çıktılar galeride kalır). İsteğe bağlı "onay bekleyen içerik" postası
(bugünkü posta altyapısı). `otomatik_yayin` açıksa kuyruk atlanır.

**AI etiketi öntanımlı ve kapatılamaz:** API'de alanı olan her yerde
(`containsSyntheticMedia`, TikTok `is_aigc`); Meta'da API alanı var mı —
**doğrulanmadı** (A0).

**Tetikleyiciler:**
* **Zamanlama** — Tasarım 1.
* **Elle** — `POST /api/akislar/{id}/calistir`.
* **Konu listesi** — bitince akış duraklar ve sahibine haber verir.
* **Webhook** — `POST /api/akis-tetik/{jeton}`: jeton akış başına, oturum
  jetonları gibi ÖZETİYLE saklanır; gövde konu/değişken taşır; hız sınırlı.
  n8n / Zapier bu adresi çağırabilir.
* **RSS** — bakım turu aralıklarla okur, görülen öğe kimliklerini saklar. İstek
  `_guvenli_hedef_mi`den geçer: kullanıcının verdiği adres iç ağa uzanamaz.

## Tasarım 3 — Arayüz, sınırlar, uyum, testler

**Arayüz:** rayda **Akışlar** bölümü — akış listesi (durum, sonraki çalışma,
son sonuç), dikey adım kartlarıyla düzenleyici (model seçimi, "önceki adımın
çıktısı" seçicisi, kayıtta doğrulama ve çalışma başına kredi tahmini),
çalışma geçmişi (adım adım, işlere bağlantı), **onay paneli** (rayda bekleyen
sayısı rozeti). tr/en, `flow-ui/flow-redesign-plan.md` desenleri, sağdan
paneller.

**Sınırlar:** özellik kapısı başta yalnız admin, sonra `Plan.otomasyon`;
kullanıcı başına akış sayısı, günlük çalışma sayısı, çalışma başına bütçe;
bugünkü saatlik iş ve günlük kredi tavanları akış işlerini de sayar; webhook hız
sınırı.

**Uyum:**
* **C2PA köken bilgisi:** OpenAI 19.05.2026'dan beri her API görseline C2PA +
  SynthID gömüyor ([OpenAI](https://openai.com/index/advancing-content-provenance/));
  Meta ve TikTok C2PA'yı okuyup otomatik etiket basıyor. Depoda C2PA'yı koruyan
  hiçbir şey yok ve iki yer baytı YENİDEN KODLUYOR: `fal_client._png_garantile`
  (PNG olmayanı, örn. Seedream'in JPEG'ini) ve ücretsiz plandaki filigran
  (`services/filigran.py`). PNG döndüren sağlayıcının baytı filigransızsa aynen
  geçer. v1: her çıktının `saglayici_meta`sına "C2PA var/yok" yazılır ve
  platform AI etiketleri HER durumda işaretlenir. Korumak (manifesti kopyalamak
  ya da kendimiz imzalamak) herkese açılmadan önce ayrı iş — yeni bağımlılık.
* **AB AI Act Madde 50** 2 Ağustos 2026'dan beri yürürlükte; makinece
  okunabilir işaretleme (50(2)) için yalnız o tarihten önce piyasaya çıkmış
  sistemlere 2 Aralık 2026'ya kadar süre var
  ([EC FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)).
  Kromis'in 50(2) anlamında "sağlayıcı" sayılıp sayılmadığı **hukuki görüş
  ister** — bu belge görüş değil.

**Testler** (deponun kuralları):
* Birim: tanım doğrulaması (yalnız geriye referans, tür uyumu), kredi tahmini,
  `ilerlet`in iki çağrıda tek kuyruklama, zamanlayıcının sonraki çalışma hesabı
  (saat dilimi dâhil), webhook jetonunun özetle saklanması.
* E2E: SAHTE hedef bağlayıcısıyla akış → çalışma → onay → yayın (bugünkü sahte
  sağlayıcı deseni).
* Kapsam bekçileri: her adım türünün işçide karşılığı; her hedef bağlayıcısı ya
  taranan listede ya da gerekçeli muafiyette (CLAUDE.md §5 deyimi).
* CI'da canlı yayın YOK; bağlayıcılar kaydedilmiş cevaplarla.

---

## İkinci senaryo — kendi videonu işle (YouTube)

Üretici KENDİ videosunu verir (webhook ya da arayüz); akış altyazı, analiz,
başlık ve kapak üretir, videoyu yayınlar. Araştırmanın hükmü (2026-09-23):

| adım | hüküm | yol (sunucuda ffmpeg YOK) |
| --- | --- | --- |
| Altyazı, çok dilli | **yapılabilir** | fal `fal-ai/elevenlabs/speech-to-text/scribe-v2` ($0,008/dk; kelime başına zaman + konuşmacı — SRT'yi biz kurarız; [api](https://fal.ai/models/fal-ai/elevenlabs/speech-to-text/scribe-v2/api)) → Gemini ile segment segment çeviri (zaman kodları korunur) → dil başına altyazı parçası. OpenAI transkripsiyonu 25 MB sınırı yüzünden ffmpeg'siz zayıf |
| Analiz: başlık, açıklama, etiket, bölüm, kapak anı | **yapılabilir** | Gemini File API videoyu doğrudan okuyor (ücretli planda ≤ 20 GB, düşük çözünürlükte ~100 jeton/sn — [docs](https://ai.google.dev/gemini-api/docs/video-understanding)); 20 dk ≈ $0,03–0,18 (kaba tahmin). JSON çıktı YouTube kurallarıyla doğrulanır: başlık ≤ 100, açıklama ≤ 5000 bayt, etiketler toplam ≤ 500; bölümler 00:00'la başlar, en az 3, her biri ≥ 10 sn ([yardım](https://support.google.com/youtube/answer/9884579?hl=en)) |
| Kapak | **yapılabilir** | Gemini'nin verdiği an → fal `workflow-utilities/trim-video` + `ffmpeg-api/extract-frame` (`first`; extract-frame keyfi zaman ALMIYOR — [api](https://fal.ai/models/fal-ai/ffmpeg-api/extract-frame/api)) ya da `workflow-utilities/extract-nth-frame` → bugünkü düzenleme işi (örn. Nano Banana Pro edit, $0,15) → `thumbnails.set`. Özel kapak için kanal DOĞRULANMIŞ olmalı |
| Yayın | **kısmen** | Video + kapak + çok dilli altyazı + `containsSyntheticMedia`: Upload-Post; başlık/açıklamanın dil sürümleri (`localizations`) için ek `videos.update` |
| Dublaj | **şimdilik yok** (sahibin kararı) | Aşağıda |

**Yeni adım türleri:** `video_girdisi` (webhook adresi → işçi SSRF kapısından,
boyut sınırıyla nesne deposuna AKITIR; büyük dosyada imzalı çok parçalı
yükleme), `transkript`, `ceviri`, `analiz`, `kare`, `kapak` (bugünkü `edit`).

**Önkoşullar:** doğrulanmış YouTube kanalı; kota planı — `captions.insert` 400
birim (dil başına), `thumbnails.set` 50: 5 dil ≈ 2.050 birim, günlük 10.000 ile
günde ~4 video, fazlası kota artış formu
([captions](https://developers.google.com/youtube/v3/docs/captions/insert),
[thumbnails](https://developers.google.com/youtube/v3/docs/thumbnails/set));
sohbet/analiz için kredi ekseni (Kromis Ajanı'nın önkoşuluyla aynı).

**Dublaj neden şimdilik yok — sert engel:** YouTube Data API'de **ek ses
parçası yükleme YOK**; çok dilli ses yalnız Studio'dan, masaüstünde
([yardım](https://support.google.com/youtube/answer/13338784?hl=en)).
Birleşik API'lerin hiçbirinde de yok. Açıldığında üç seçenek:
(a) ElevenLabs Dubbing ile sesi üret (yaratıcının klonu; v1 $0,33–0,50/dk —
[pricing](https://elevenlabs.io/pricing/api)), onay kuyruğunda dil başına
"Studio'da ekle" görevi — yeni sağlayıcı (doğrudan ElevenLabs; fal ucu yalnız
video döndürüyor); (b) YouTube'un ücretsiz otomatik dublajı (4 Şubat 2026'dan
beri tüm kanallar; Türkçe → İngilizce VAR, İngilizce → Türkçe YOK —
[yardım](https://support.google.com/youtube/answer/15569972?hl=en));
(c) dil başına ayrı video (fal dublaj + isteğe bağlı lipsync, `sync-lipsync`
$3–8/dk) — tam otomatik ama ana videonun izlenmesi bölünür. Dudak senkronu yeni
video ürettiği için AYNI videoya hiçbir yoldan eklenemez.

**Politika:** yaratıcının KENDİ sesini klonlaması YouTube'da açıklama
gerektirmiyor ([yardım](https://support.google.com/youtube/answer/14328491?hl=en));
ama ElevenLabs dublajı videodaki TÜM konuşmacıları klonluyor → misafir varsa
rızası ya da klon kapalı; onay kuyruğunda rıza kutusu.

---

## Kromis Ajanı — sohbet modeli (ileride)

Sahibin eki (Tasarım 1 onayında): akıştaki `yonetmen` adımı ve normal Prompt
Yönetmeni aynı sohbet katmanını kullanır.

* **Platform kredisiyle:** kullanıcı ya planına göre açık olan katalog sohbet
  modellerinden birini seçer (`ChatModel.plan`, görsel modellerle aynı eşik) ya
  da öntanımlı **Kromis Ajanı**'nı. Ajanın arkasındaki modeli biz seçer, hız ve
  maliyet için ayarlar, değiştiririz; kullanıcı modeli görmez.
* **Kendi anahtarıyla (BYOK):** kullanıcı kendi modelini bağlar ve seçer,
  krediden düşülmez — bugünkü BYOK kuralı.
* **Önkoşul — sohbet kredi ekseni:** bugün sohbet HİÇ kredilenmiyor. Jeton ya
  da tur başına kredi (`KREDI_USD_CAPASI` = 0,005 USD, aynı çapa) ve defterde
  rezerv/onay; yapılmadan platform anahtarıyla akış herkese açılamaz.
* **Kısıt:** model arayüzde gizlenebilir, ama arkadaki sağlayıcı gizlilik
  politikasının **alt işleyenler** listesinde adıyla yazılmak zorunda (KVKK;
  Faz 4'ün 6. görevi, hukuk metinleri) — model değişince liste de değişir. AB
  AI Act modelin adını değil "yapay zekâyla konuştuğunu" söylemeyi istiyor.

---

## Aşamalar

Her aşama kendi görev listesi ve PR'larıyla; sıra bağımlılığa göre.

| aşama | içerik | çıkış kriteri |
| --- | --- | --- |
| **A0 — doğrulama** | Upload-Post / Zernio karşılaştırması (IG/FB/YT, Shorts'un herkese açık yayını, idempotency, AI etiketi alanları, altyazı/kapak, güncel fiyat); Meta'da AI etiketi API alanı; C2PA'nın bizim yolumuzda nerede düştüğünün ölçümü | Karar notu; kod TUTULMAZ |
| **A1 — motor** | Silme/dışa aktarma kapsam bekçisi (önce); göç (`akislar`, `akis_calismalari`, `isler` sütunları), tanım şeması + doğrulama, `yazi` iş türü, `ilerlet`, elle çalıştırma, kredi tahmini, Akışlar arayüzü (liste, düzenleyici, geçmiş); yeni tablolar silme turunda ve dışa aktarmada | Elle çalıştırılan akış dört içerik türünü üretir, çıktılar galeriye düşer; yayın YOK |
| **A2 — zamanlama** | Takvim + `akis_konulari` | Zamanlanmış çalışma konu listesinden sıradakini alır; liste bitince akış duraklar |
| **A3 — yayın** | `baglantilar`, birleşik API bağlayıcısı, `yayin` iş türü, onay kuyruğu, AI etiketi, `otomatik_yayin`; hesap silmede bağlantı koparma | IG + FB + YT Shorts'a onaylı yayın, sahibin hesaplarında |
| **A4 — dış tetikleyiciler** | Webhook + RSS | n8n/Zapier'den ve bir blog akışından tetiklenen çalışma |
| **A5 — kendi videonu işle** | `video_girdisi`, `transkript`, `ceviri`, `analiz`, `kare`, `kapak`; YouTube çok dilli altyazı + kapak + `localizations` | Webhook'la verilen video çok dilli altyazı, başlık, bölüm ve kapakla onaydan geçip yayınlanır |
| **Sonra** | Kromis Ajanı + sohbet kredi ekseni; dublaj (üç seçenek); Drive (`drive.file`) / S3 / Canva (ikili yükleme); TikTok (taslak/inbox); resmi bağlayıcılar (Meta App Review, YouTube audit); `Plan.otomasyon` ve fiyatlandırma; C2PA koruma | Herkese açılış |

**Bağımlılıklar:** A1 her şeyin önünde; A2, A3, A4 A1'den sonra birbirinden
bağımsız; A5 A3 ve A4'e dayanır (yayın + webhook). Kromis Ajanı'nın kredi
ekseni, platform anahtarıyla herkese açılışın önkoşulu — iç araçta (sahibin
kendi anahtarları ya da admin) beklemez.

---

## Açık kararlar ve doğrulanacaklar

* **Birleşik API seçimi** (A0): Upload-Post mu Zernio mu — eğilim Upload-Post.
* **Meta'da AI etiketi** için API alanı — doğrulanmadı.
* **`youtube.upload` kapsamının sınıfı** (resmi bağlayıcıda OAuth doğrulaması
  gerekir mi) — tam doğrulanmadı.
* **C2PA**: koruma mı, yeniden imzalama mı; hukuki görüş (Madde 50).
* **Sohbet kredisinin birimi** (jeton mu tur mu) — Kromis Ajanı aşamasında.
* **Dublaj** — üç seçenekten biri, açıldığında.
* **Sıralı liste → çizge** — ihtiyaç doğarsa; veri modeli buna açık.

## Riskler

* **Platform politikası:** YouTube "inauthentic content" (seri şablon içerik
  YPP'den çıkarılıyor), X'in toplu otomasyon yasağı, TikTok'un gözetimsiz yayın
  yasağı. Onay kuyruğunun öntanımlı olması bu riskin karşılığı; `otomatik_yayin`
  açık akışlar için arayüzde uyarı.
* **Üçüncü tarafa jeton emaneti** (birleşik API): kullanıcının sosyal hesap
  erişimi onların elinde. İç araçta kabul; herkese açılırken resmi bağlayıcı ya
  da yönetilen OAuth.
* **Maliyet kaçağı:** zamanlanmış akış sessizce kredi eritebilir → çalışma başı
  bütçe, günlük çalışma tavanı, bakiye yetmezse çalışma başlamaz.
* **Kota:** YouTube altyazı ve kapak kotası video senaryosunu günde ~4 videoyla
  sınırlıyor.

---

## Kaynaklar (erişim 2026-09-23)

Pazar: [n8n pricing](https://n8n.io/pricing/) ·
[n8n OpenAI video](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-langchain.openai/video-operations/) ·
[Zapier AI fiyatı](https://help.zapier.com/hc/en-us/articles/46597632373389-AI-by-Zapier-new-model-based-pricing-starting-June-15-2026) ·
[Make kredileri](https://help.make.com/credits) ·
[Activepieces](https://github.com/activepieces/activepieces) ·
[Figma Weave](https://weave.figma.com/) ·
[Runway Workflows uç](https://help.runwayml.com/hc/en-us/articles/50085269258643-Publishing-a-Workflow-as-an-Endpoint) ·
[Krea Nodes](https://www.krea.ai/docs/user-guide/features/nodes) ·
[Comfy pricing](https://comfy.org/pricing) · [Blotato](https://www.blotato.com/) ·
[Postiz pricing](https://postiz.com/pricing) ·
[Adobe Express scheduler](https://helpx.adobe.com/express/web/publish-and-share/schedule-manage-posts/content-scheduler-overview.html).

Platformlar: [TikTok content sharing](https://developers.tiktok.com/doc/content-sharing-guidelines) ·
[TikTok direct post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) ·
[YouTube audit](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits) ·
[YouTube revision history](https://developers.google.com/youtube/v3/revision_history) ·
[YouTube videos](https://developers.google.com/youtube/v3/docs/videos) ·
[captions.insert](https://developers.google.com/youtube/v3/docs/captions/insert) ·
[thumbnails.set](https://developers.google.com/youtube/v3/docs/thumbnails/set) ·
[resumable upload](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol) ·
[Instagram overview](https://developers.facebook.com/docs/instagram-platform/overview) ·
[Instagram publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/) ·
[X pricing](https://docs.x.com/x-api/getting-started/pricing) ·
[X automation rules](https://help.x.com/en/rules-and-policies/x-automation) ·
[LinkedIn erişim](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-06) ·
[Pinterest katmanları](https://developers.pinterest.com/docs/key-concepts/access-tiers/).

Birleşik API'ler: [Upload-Post pricing](https://www.upload-post.com/pricing-comparison/) ·
[Upload-Post upload-video](https://docs.upload-post.com/api/upload-video/) ·
[Zernio pricing](https://docs.zernio.com/pricing) ·
[Zernio YouTube](https://docs.zernio.com/platforms/youtube) ·
[Ayrshare pricing](https://www.ayrshare.com/pricing/) ·
[Ayrshare YouTube](https://www.ayrshare.com/docs/apis/post/social-networks/youtube).

Depo/tasarım: [Drive kapsamları](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) ·
[Canva URL upload](https://www.canva.dev/docs/connect/api-reference/assets/create-url-asset-upload-job/) ·
[Figma MCP write](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas) ·
[Adobe Embed SDK FAQ](https://developer.adobe.com/express/embed-sdk/docs/guides/troubleshooting/faq/).

Video senaryosu: [fal Scribe v2](https://fal.ai/models/fal-ai/elevenlabs/speech-to-text/scribe-v2/api) ·
[fal extract-frame](https://fal.ai/models/fal-ai/ffmpeg-api/extract-frame/api) ·
[fal extract-nth-frame](https://fal.ai/models/fal-ai/workflow-utilities/extract-nth-frame/api) ·
[fal trim-video](https://fal.ai/models/fal-ai/workflow-utilities/trim-video/api) ·
[fal nano-banana-pro edit](https://fal.ai/models/fal-ai/nano-banana-pro/edit) ·
[Gemini video](https://ai.google.dev/gemini-api/docs/video-understanding) ·
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) ·
[ElevenLabs API pricing](https://elevenlabs.io/pricing/api) ·
[ElevenLabs dubbing](https://elevenlabs.io/docs/overview/capabilities/dubbing) ·
[YouTube auto-dubbing](https://support.google.com/youtube/answer/15569972?hl=en) ·
[YouTube çok dilli ses](https://support.google.com/youtube/answer/13338784?hl=en) ·
[YouTube AI açıklama](https://support.google.com/youtube/answer/14328491?hl=en) ·
[YouTube bölümler](https://support.google.com/youtube/answer/9884579?hl=en).

Uyum: [OpenAI provenance](https://openai.com/index/advancing-content-provenance/) ·
[EC Madde 50 SSS](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act) ·
[YouTube AI slop politikası](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/).
