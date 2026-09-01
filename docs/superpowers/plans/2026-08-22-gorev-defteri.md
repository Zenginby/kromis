# Görev defteri — sıradaki adımlar

**Tarih:** 1 Eylül 2026 · **Son dal:** `claude/project-graphs-next-tasks-7slwo1`
(`main`'den kuruldu, henüz birleşmedi)
**Bugünkü ölçüm:** `APP_VERSION` **0.11.6** (sonrakini CI yazacak),
`pytest tests/ -q` → **1861 geçti / 9 atlandı** (Playwright kuruluyken; Tur K
öncesi aynı ortamda 1854 geçti / 9 atlandı — beş yeni test, sonra kod
incelemesiyle bir tane daha)
**Defterin açılış ölçümü** (Tur A öncesi): `APP_VERSION` 0.7.0 → 1613 geçti / 10 atlandı
(atlananlar her üç ölçümde de yalnız Windows'a özgü DACL testleri + kurulu
olmayan Playwright)

> **Defter dört sürüm bayat kalmıştı** ve bu kaydın kendisi bir ders: Tur D'den
> (v0.9.2) sonra iki tur daha gönderildi (v0.10.0–v0.11.4) ama defter
> güncellenmedi, yani "sıradaki iş" diye buraya bakan bir sonraki oturum hâlâ
> 23 Ağustos'u okuyordu. Tur E ve F kutuları o boşluğu **geriye dönük** kapatıyor;
> kanıtları commit'lerden ve testlerden okunarak yazıldı, hafızadan değil.

Bu defter **canlı** bir belgedir: bitmiş turların kaydı ve sıradaki işin tanımı
burada durur. Yol haritaları (README fazları, `2026-08-10-saas-transformation-master-design.md`
§5) **ne** yapılacağını söylüyor; bu defter **sırayı** ve **kanıtı** taşıyor.

---

## Nasıl kullanılır (her oturum)

1. Bu dosyayı oku. **En üstteki açık tur** sıradaki iştir; başka bir şeye
   geçmek için gerekçe yazılır.
2. Turu bitir, sonra kutuyu **kanıtla** işaretle: test sayısı, tarayıcı ölçümü
   ve commit. Kanıtsız işaretlenmiş kutu, işaretlenmemiş kutudan kötüdür.
3. Bir madde ancak **işaretlenerek** ya da **gerekçesiyle ertelenerek** kapanır
   (flow-ui `§7` disiplininin aynısı: iddia silinmez, yeniden yazılır).
4. Kuyruktan bir madde alındığında **üste taşınır** ve kendi adım listesini
   orada kazanır. Kuyruk sırası bir söz değil, öneri: kullanıcı sırayı
   değiştirebilir.

---

## ✅ Tur K — Stüdyo sadeleşti: az metin, yalnız kullanılabilir modeller, küçülen composer

**Bitti (1 Eylül).** Kuyruk maddesi DEĞİL, **kullanıcının o gün verdiği iş**:
"stüdyo kısmındaki chat kısmını olabildiğince sadeleştirmek istiyorum, gereksiz
yazıları kaldıralım ve API key'i girilmeyen modeller gözükmesin. İleride kredi
ve üyelik sistemine geçtiğimizde aboneliği olan kişiler için belli modeller
gözükecek şekilde çalışma yapacağız… bir de chat veya görsel üretme prompt'u
gönderdikten sonra chat kısmı küçülsün."

Kuyruğun başındaki logo maddesi bu yüzden BEKLEDİ; defterin kuralı zaten bunu
söylüyor ("kuyruk sırası bir söz değil, öneri: kullanıcı sırayı değiştirebilir")
ve o madde bu oturumda ölçümle DARALDI (aşağıda, kuyrukta).

### 1. Gereksiz yazılar — üçü kalktı, biri kaldı

| kalkan | nerede | ne oldu |
| --- | --- | --- |
| 58ch'lik tanıtım paragrafı | `#chat-empty` | başlık + çipler aynı şeyi zaten söylüyor |
| klavye ipucu şeridi `.chat-hint` | `.composer-foot` | **bilgi ölmedi, taşındı**: `#go`nun `title`ı (tek yazar `syncGoGate`) |
| "ilk yanıt yarım dakikayı bulabilir" | `#chat-wait` | spinner + "Yönetmen düşünüyor…" kaldı |
| dört öneri çipi | `#chat-empty` | **KALDI** — kullanıcı kararı; boş ekranın tek eylem kapısı onlar |

Şerit telefonda zaten `display: none` idi, yani kayıp masaüstüne özgüydü;
kazanç da orada. `title` dokunmatikte hiç görünmüyor ve bu bir gerileme DEĞİL:
o metin ("⌘/Ctrl + Enter") telefonda zaten YANLIŞ bilgiydi — eski
`mobile.css` kuralının gerekçesi tam olarak buydu ve gerekçe kayda geçti.

### 2. Anahtarı girilmemiş modeller — kapı KAPANDI

Filtre (`core.js secilebilirler`) zaten vardı; kaçak **ilk kurulum kapısıydı**:
hiçbir anahtar kayıtlı değilken BÜTÜN katalog listeleniyordu. Kullanıcının
gördüğü şey buydu.

Kapının eski gerekçesi "boş bir şerit kullanıcıya hiçbir şey söylemez"di ve
**o gerekçe artık karşılıksız**, çünkü aynı soruyu üç yer cevaplıyor —
biri zaten duruyordu, ikisi bu turda kuruldu:

* Ayarlar hiçbir görsel modeli kurulu değilken **kendiliğinden açılıyor**
  (settings.js) — ilk kurulumdaki kullanıcı boş bir şeritle değil, anahtar
  formuyla karşılaşıyor;
* şerit ve panel boş hâli **anlatıyor** (`MODEL_BOS_METNI`, `.model-sheet-empty`);
* `#go` kilitli ve kilidin sebebi `title`da yazılı.

Boş hâl çizilmek ZORUNDAYDI, yoksa kapanan kapı sessiz bir kırılma üretiyordu:
`secilecek` boş dize döndürüyor, `applyModel` modeli bulamayıp erken çıkıyor ve
çip **"Modeller yükleniyor…" yazısında donuyordu**. Kaynak taraması bunu
yakalayamaz — her iki hâlde de kod doğru görünüyor, fark ekranda. O yüzden
bekçisi bir E2E testi.

Boş hâlin çizimi `syncModelChip`in İÇİNE kondu, ayrı bir fonksiyona değil:
çipin tek yazarı olması bu dosyanın çivilenmiş kuralı ve üç tripwire onu
gerçekten sayıyor — ilk yazımda ikinci bir yazar açtım, **üçü birden kırmızı
oldu** (`test_cip_dugmesinin_adi_EKSENI_de_soyluyor`,
`test_ISARET_her_iki_seride_de_baglaniyor`,
`test_model_yuzeyi_TEK_ve_IKI_ekseni_birlikte_tasiyor`). Tasarım testlerin
dediğine göre düzeltildi; testler haklıydı.

**Ölçüm (Chromium 390×844):**

| kurulum | şeritteki modeller | çip |
| --- | --- | --- |
| anahtar YOK | **0** (eskiden katalogun tamamı) | "Model yok — Ayarlar" |
| yalnız OpenAI | `openai-gpt-image-2`, `openai-gpt-image-1` | seçili modelin adı |

`#go` anahtarsız kurulumda kilitli ve `title`ı
"Kayıtlı API anahtarı yok — Ayarlar'dan ekle." diyor.

### 3. Üyelik/kredi: TEK alanlık tohum, bugün davranış değişmiyor

Bugün istemcinin sorduğu soru "anahtar var mı" (`configured`). Yarın ikinci bir
sebep doğacak: "aboneliği bu modeli kapsıyor mu". İki sebebi istemcide ayrı ayrı
sormak, görünürlük kuralının İKİ cevabı olması demek — `secilebilirler`in var
olma sebebi tam olarak o ikiliği önlemek.

Karar bu yüzden **sunucuda türetilmiş tek alana** indi:

* `catalog.ImageModel` / `ChatModel` → `plan: str = "free"`;
* `app._model_available(configured, plan)` → bugün `configured`ı aynen
  döndürüyor. **Değişecek tek yer burası.**
* `/api/settings` her modele `available` + `requires_plan` yazıyor;
  `core.js secilebilirler` artık `m.available` okuyor.
* `configured` ÖLMEDİ: mesaj yazan yerler (`#model-note`, `goBlockReason`) onu
  okumaya devam ediyor — "anahtar yok" ile "planın kapsamıyor" aynı cümle değil.

**Kapsam dışı ve bilinçli:** kullanıcı/oturum modeli, kimlik doğrulama, bakiye,
satın alma. `plan` parametresi bugün OKUNMUYOR ve imzada durmasının sebebi
kancanın yeri olması — uydurma bir plan eşleştirmesi yazmak, olmayan bir
gerçeği kodlamak olurdu. Kuyrukta kendi maddesi var.

`available` bugün `configured` ile eşit olduğu için **silinmesi hiçbir testi
düşürmezdi**; o yüzden kancanın sessizce ölmesini engelleyen bir mandal yazıldı
(`test_GORUNURLUK_karari_TEK_alandan_geliyor_ve_bugun_configured_ile_ayni`).

### 4. Gönderimden sonra composer küçülüyor

Çapa `submitComposer` — iki mod da oradan geçiyor, yani "chat VEYA görsel"in tek
karşılığı o. İşaret uzunluk kapılarının ARDINDAN yazılıyor: reddedilen bir
gönderim küçülmeyi hak etmiyor.

**Turun en öğretici kısmı burasıydı: ilk çözüm ölçümde ÇÖKTÜ.** Plan yalnız
`min-height`ı düşürmekti (2.5rem → 1.6rem) ve Chromium'da hiçbir şey
değiştirmedi — **57px → 57px**. Sebep: `autoGrow` kutuya satır içi bir `height`
yazıyor (`height: auto` → `scrollHeight`) ve o değer tabanın zaten üstünde.
Boş bir kutunun yüksekliğini fiilen `rows` belirliyor, `min-height` değil.

İkinci ölçüm ikinci bir kusuru gösterdi: `rows` düşürüldükten sonra masaüstü
küçülüyordu ama **telefon hâlâ 57px'te duruyordu**. Sebep, boş bir
`<textarea>`nın `scrollHeight`inin YER TUTUCUYU da kapsaması: 390px'de uzun yer
tutucu iki satıra sarıyor. Yani kutuyu şişiren şey metnin kendisiydi — ve o
metin zaten kullanıcının kaldırılmasını istediği türden. Yer tutucu ilk
gönderimden sonra kısa hâline geçiyor.

| ölçüm (boş kutu, odak dışında) | masaüstü 1280×860 | telefon 390×844 |
| --- | --- | --- |
| `#prompt` gönderim öncesi | 57px | 57px |
| `#prompt` gönderim sonrası | **35px** | **35px** |
| `#prompt` yeniden odaklanınca | 57px | 57px |
| `#composer` | 208 → **186px** | 248 → **226px** |
| `--composer-h` (mobil, tuvalin alt boşluğu) | — | 248 → **226px** |

Son satır elle senkron GEREKTİRMEDİ: `--composer-h`i mobile.js bir
`ResizeObserver` ile ölçüyor, yani telefonda tuvalin alt boşluğu küçülmeyi
kendiliğinden devraldı.

### Turun kanıtı

* `python3 -m pytest tests/ -q` → **1859 geçti / 9 atlandı** (tur öncesi aynı
  ortamda 1854/9). Beş yeni test: üçü kaynak mandalı, ikisi Chromium E2E.
* `python3 tools/graf_uret.py --kontrol` → yeşil; graf dosyaları bu commit'in
  içinde.
* Üç senaryo gerçek Chromium'da ölçüldü ve ekran görüntüsüyle doğrulandı
  (yukarıdaki tablolar).

### Yeniden yazılan iddialar (silinmedi)

Deponun kuralı gereği kapanan iddia silinmiyor, **yeniden yazılıyor**:

| test | eski iddia | yeni iddia |
| --- | --- | --- |
| `test_ANAHTARI_OLMAYAN_modeller_seride_GIRMIYOR` | "ilk kurulumda HEPSİ görünsün" | "kapı kapalı VE boş hâl çiziliyor" |
| `test_composer_ipucu_TEK_SATIR_…` → `…_SERIDI_KALDIRILDI_bilgi_GO_dugmesinde` | `.chat-hint`in flex geometrisi | şerit yok, bilgi `#go`nun `title`ında |
| `test_sohbet_kataloğu_…_ALANLARI_tasiyor` | 8 alanlık donmuş küme | 10 alan (`available`, `requires_plan`) |
| `test_playwright_model_sheet_alttan_aciliyor` | anahtarsız sunucuda kartları ölçüyordu | kimlikleri kayıtlı gösteriyor (kartlar VARKEN anlamlı) |

Sonuncusu turun kendi dersi: o test anahtarsız bir sunucuda koşuyordu ve
kartların varlığını ölçüyordu — filtre sıkılaşınca **haklı olarak** kırmızıya
döndü. Değişikliğin gerçekten işlediğinin ilk kanıtı o kırmızıydı.

### 7. Tur K'nın kendi kod incelemesi — dört bulgu, dördü de kapandı

PR #63 açıldıktan sonra kullanıcı bir inceleme istedi. Takım YEŞİLDİ (1859/9),
yani dördü de **kapıların görmediği** şeyler. Bu bölüm turun ikinci commit'i.

| # | bulgu | neden kapılar görmedi |
| --- | --- | --- |
| 1 | Küçülmenin çapası `submitComposer`daydı; oradaki kapılar yalnız UZUNLUK kapıları. Boş kutuyla "Üret" → `data-sent` yazılıyor, `rows` 1'e iniyor, uzun tanıtım yer tutucusu ölüyor — sonra `run()` "Önce bir prompt yaz." diyor. `sendChat`in dört kapısı ve `runArena`nın ikisi de aynı durumda. | Yeni test yalnız `submitComposer` İÇİNDEKİ iki kapıya karşı sırayı ölçüyordu |
| 2 | `test_composer_ipucu_TELEFONDA_hala_gizli` kaldırılan bir kuralın VARLIĞINI şart koşuyor ama yeşil kalıyordu: yerine bırakılan gerekçe yorumu seçicinin adını taşıyor, `css.split(".chat-hint {")` **yorumu** yakalıyordu. `test_index.py`nin "böyle bir kural olmamalı" iddiasıyla açıkça çelişen ikinci bir iddia — ikisi de yeşil. | Tripwire bedelinin deponun daha önce iki kez ödediği hâli; bu kez ödeyen bir TESTTİ |
| 3 | Boş panelin metni sabit "Kayıtlı API anahtarı yok" idi, oysa `renderModelCards` üç eksenin ortağı. Azure'da anahtar kayıtlıyken dağıtım adı boş olabiliyor (`chat_is_configured` ikisini birden arıyor): o kullanıcıya elindeki anahtarı yeniden yapıştırmasını söylüyorduk. | Metnin doğruluğunu hiçbir iddia eksene bağlamamıştı |
| 4 | Şerit İKİ kısayol taşıyordu; yalnız ⌘/Ctrl+Enter `#go`ya taşındı. ⌘/Ctrl+J (mod değiştirme, `core.js` keydown'da hâlâ çalışıyor) hiçbir yerde yazmıyordu. | "Bilgi taşındı" iddiası yalnız birinci yarıyı ölçüyordu |

Kapanışlar ve **her birinin bıraktığı yeni ölçü**:

* **1 →** çapa kutunun boşaldığı üç satıra taşındı (`run`, `runArena`,
  `sendChat`) — üç akışın da bütün kapılardan geçtikten sonra yaptığı ilk iş o,
  yani "kabul edildi"nin kaynaktan okunabilir tek işareti. Test artık
  **bitişikliği** ölçüyor (yorumlar ayıklanarak) ve `submitComposer`da
  `composerKuculsun`un HİÇ geçmemesini şart koşuyor. Chromium'da ikinci bir
  iddia: boş kutuyla "Üret"e basınca `data-sent` yazılmıyor **ve** uzun yer
  tutucu duruyor. Yan düzeltme: `sendChat`in başarısızlık dalı metni geri
  koyarken artık `autoGrow` da çağırıyor — `rows` 1'e inmişken ölçüm
  yapılmazsa geri konan çok satırlı mesaj tek satıra kırpılmış görünüyordu.
* **2 →** iddia tersine çevrildi (`…_TELEFONDA_geri_GELMIYOR`) ve yorumlar
  ÖNCE ayıklanıyor. Yanına telefona özgü ikinci bir mandal: `mobile.css`
  `.composer-input`a `min-height` yazamaz — yazarsa `.composer[data-sent]`
  tabanı medya sorgusunun altında kalır ve küçülme **telefonda** sessizce
  yutulur (bu turda bir kez neredeyse öyle oldu, bkz. yukarıdaki 4. bölüm).
* **3 →** metin eksene bağlandı (`MODEL_BOS_PANEL.anahtar` / `.kimlik`,
  `MODEL_EKSENLERI`den okunuyor). Panel artık `goBlockReason`ın yönetmen
  dalıyla aynı dili konuşuyor. Ölçüm (Chromium 390×844, anahtarsız sunucu):
  görsel ekseni "Kayıtlı API anahtarı yok…", sohbet ekseni "Kayıtlı sohbet
  kimliği yok… (anahtar, gerekiyorsa dağıtım adı)".
* **4 →** `MOD_KISAYOL` eklendi ve mod düğmelerinin `title`ına yazılıyor
  (`Görsel modu · ⌘/Ctrl + J`, `Yönetmen modu · ⌘/Ctrl + J`) — kısayolun
  yaptığı iş tam olarak o düğmelere basmak. İki kısayol sabiti yan yana
  duruyor ki "iki dosyada iki ad" kayması doğmasın.

**Turun asıl dersi:** dört bulgunun üçü (1, 2, 4) aynı biçimde doğdu — *bir
şeyin yerinin değiştiğini söyleyen bir iddia, yalnız yeni yerine baktı.*
Taşınan şeyin ESKİ yerinde bıraktığı boşluğu ölçmeyen bir test, taşımanın
yarım kaldığını göremiyor. 2 numara bunun en pahalı hâli: iddia yalnız kör
değildi, **tersini** söyleyen bir kardeşiyle birlikte yeşil duruyordu.

Ölçüm: **1861 geçti / 9 atlandı** (inceleme öncesi 1859/9 — bir yeni test, bir
de yeniden yazılan iki iddia).

---

## ✅ Tur J — Temizlik turu: üç küçük borç, üçü de ÖLÇÜLEREK kapandı

**Bitti (28 Ağustos).** Kuyruğun **1 + 2 + 3. maddeleri**, 28 Ağustos kararıyla
tek turda. Üçü de **S**, üçü de ayrı yüzeyde; ortak yanları küçük olmaları
değil, üçünün de yıllardır bir **iddia** olarak durup hiç ölçülmemiş olmasıydı.

### 1. `#picker-empty` her tuş vuruşunda yeniden duyuruyordu — DOĞRU ÇIKTI

Madde defterde "duyuruyor OLABİLİR" diye duruyordu ve Tur G'de tam da bu
yüzden dokunulmamıştı. Ölçüm önce yapıldı, düzeltme sonra.

**Ölçüm** (Chromium 1194, boş kütüphane, seçici açık, `#picker-empty` üzerinde
MutationObserver — childList + characterData + attributes; sonuçsuz kalacak
altı harf yazıldı):

| | mutasyon |
|---|---|
| düzeltmeden önce | **6** childList — beşi AYNI cümleyle ("Sonuç bulunamadı" → "Sonuç bulunamadı") |
| düzeltmeden sonra | **1** (yalnız gerçek durum değişimi) |

Kök neden `textContent` atamasının metin düğümünü KOMPLE değiştirmesi: kayıt
`characterData` değil `childList` geliyor, yani dize hiç değişmese bile canlı
bölge YENİ bir düğüm görüyor. Bir ekran okuyucunun bunu kaç kez seslendirdiği
araca göre değişir; değişmeyen şey, o kararı veren DOM sinyalinin beş kez
fazladan üretilmiş olması.

`hidden` aynı koşuda **suçsuz** çıktı (sıfır attributes kaydı: özniteliği zaten
yokken kaldırmak mutasyon üretmiyor), o yüzden oraya koşul YAZILMADI — olmayan
bir kusura kalkan yazmak bir sonraki okuyucuya yanlış bilgi bırakırdı.

- Düzeltme: `static/folders.js` — metin bir `const`ta toplanıp yalnız
  DEĞİŞİNCE atanıyor.
- Bekçi: `tests/test_index.py::test_the_empty_state_sentence_is_not_rewritten_when_it_did_not_change`.

### 2. Ölü `uploads` türü — kaldırılmadı, GÖÇTÜ

Kabul ölçütü iki yol bırakıyordu (göç ya da türün kaldırılması, ikisi de eski
kurulumları kaybetmeden). Seçilen **göç**, çünkü kaldırma yarım çözümün ikinci
yarısını çözmüyordu: tür arka uçta duruyordu ki eski varlıklar kaybolmasın, ama
o varlıklar "Tümü"de GÖRÜNÜP hâlâ hiçbir bindirmede kullanılamıyordu
(`models.OVERLAY_ASSET_KINDS` yalnız logos/mottos). Yani kullanıcı D9'un çıkmaz
sokağını bu kez sessizce yaşamaya devam ediyordu.

`assets_store.migrate_legacy_uploads` kayıtları `logos`a taşıyor (yükleme
hedefinin bugünkü varsayılanı da orası: `assets.js` `UPLOAD_TARGET.all`), sonra
`KINDS` üçe iniyor ve `/api/assets/uploads` 404 oluyor.

Göç, açılışın kullanıcı verisini yerinden oynatan **tek** adımı; o yüzden
kararların hepsi yazılı ve hepsinin bekçisi var:

| karar | gerekçe | bekçi |
|---|---|---|
| önce dosya, sonra manifest | ters sıra, araya düşen çökmede manifest'i olmayan dosyaya işaret eder — kullanıcı KIRIK karo görürdü | `test_a_half_finished_migration_is_completed_on_the_next_run` |
| id çakışmasında yeni id | aynı id ikinci kez yazılırsa duran logo listeden düşerdi | `test_an_id_collision_does_not_hide_the_existing_logo` |
| `rmdir`, `rmtree` DEĞİL | manifest'te kaydı olmayan dosya kullanıcınındır; sessizce silinmez | `test_a_file_the_app_never_listed_is_not_deleted` |
| yedekten SONRA | sürüm yedeği göç ÖNCESİ hâli taşımalı, yoksa geri dönülecek nokta kalmaz | `test_the_version_backup_runs_before_the_migration` |
| dizin yoksa no-op | yeni kurulumun maliyeti tek `isdir` | `test_the_migration_is_a_noop_without_the_dead_directory` |

### 3. `gitleaks` — Adım 1 planının son açık maddesi

"Geçmiş taramasının kaydı yok" diyordu; **artık var.** İlk koşu: **76 commit,
3.4 MB, 405 ms, 14 bulgu — hepsi bilerek sahte** test/doküman sabiti, depoda
gerçek bir sırrın izi YOK.

Tarama diff'e değil geçmişin TAMAMINA bakıyor: bir sırrın commit'ten silinmesi
onu geçmişten silmiyor. Muafiyetler `.gitleaks.toml`da tek tek yazılı sahte
DEĞERLER — `^tests/` gibi bir yol muafiyeti yazılsaydı tam da fixture'ların
yaşadığı yer kör kalırdı. Dört satırı `DUMMY` damgasından önce yazılmış
fixture'lar için ve geçmişte donmuş oldukları için kalıcı.

Resmî `gitleaks-action` yerine **sürüm + sha256 ile sabitlenmiş ikili**: eylem
organizasyonlarda lisans anahtarı istiyor ve kendi telemetrisini taşıyor;
sabitlenmiş ikilide koşan şey denetlenebilir ve yükseltme diff'te görünür bir
karar oluyor. `--redact` ile gerçek bir bulguda sır koşu günlüğüne yazılmıyor.

**Kabul ölçütü ölçüldü:** temiz depoda exit 0; bir klona gerçek biçimli bir
`sk-proj-…` anahtarı commit'lenince aynı yapılandırmayla **exit 1** — iş
kırmızı. Maliyet gerekçesi burada bağlamıyor (Tur I'in aksine): iş ubuntu'da
(1x) ve saniyenin yarısı sürüyor.

### Turun kanıtı

* Takım: **1831 → 1847 geçti / 10 atlandı** (CI'ın gördüğü sayı). Playwright bu
  oturumda kurulduğu için E2E dosyası da koştu: **1854 / 9**, yedi E2E testi
  dahil yeşil.
* **On üç mutasyon, on üçü de kırmızı:** koşulsuz atama · koşulu atlayan ikinci
  atama · göçün lifespan'dan düşmesi · yedek/göç sırasının ters çevrilmesi ·
  çakışmada aynı id'nin yeniden kullanılması · ölü dizinin koşulsuz silinmesi ·
  yarım göç kurtarmasının kalkması · ölü türün `KINDS`e geri gelmesi ·
  `fetch-depth: 0`ın düşmesi · `--redact`in kalkması · `paths` muafiyetinin
  girmesi · sha256 doğrulamasının kalkması · `gitleaks git`in `gitleaks dir`e
  dönmesi.
* Graflar aynı commit'te yenilendi; `tools/graf_uret.py --kontrol` yeşil.

### Turun kendi kusuru: sentetik koşu Windows'ta hiçbir şey ölçmüyordu

Tur I'in en iyi parçası "kapının kararı ilk kez ölçülüyor"du; o ölçüm **yalnız
Linux'ta** ölçüyordu. Windows paketleme işi `60440da`'da kırmızıya döndü ve
sebebi testin kendisiydi: sahte `git` PATH'in başına uzantısız bir betik olarak
konuyordu, Git Bash komut ararken onu atlayıp gerçek `git.exe`i buluyor, betik
depo OLMAYAN bir dizinde `git diff` koşuyor ve kapı güvenli tarafa düşüyordu.

Bedeli iki katmanlı ve ikincisi sinsi: `hayir` bekleyen beş test kırmızıya
düşüyordu (görünen yarı), `evet` bekleyen sekizi ise **doğru sebeple değil
kazara** geçiyordu — yani o platformda testin ölçtüğü hiçbir şey yoktu.

Düzeltme sahte `git`i PATH yerine bir **kabuk işlevine** taşıyor (harici
komuttan önce çözülüyor, üç platformda aynı). Yanına da o sessiz hâlin kapısı
eklendi: koşu `diff kurulamadı` yazdıysa test artık kazara geçmek yerine
bunu söylüyor. **Ölçüldü:** sahte `git` devre dışı bırakıldığında eskiden 5
test kırmızıydı, şimdi **13** — sekiz sessiz yeşil artık sesli.

**TESLİM EDİLDİ:** PR #61 (üç commit: `60440da` Tur I · `0081056` Tur J ·
`cc774e2` sentetik koşunun Windows kusuru) yedi kontrolün yedisi de yeşilken
birleşti; yayın hattı `v0.11.6`'yı kendisi yazdı. Yani Tur H'de kanıtlanan
"merge → yayın" zinciri ikinci kez ve bu kez sızıntı taraması da hattayken
yürüdü.

> **Bu turun kendi CI koşusu üç paketi de derleyecek** — `.github/workflows/`
> altına dokunuyor (gitleaks işi oraya girdi). Tur I'de daraltılan kapı
> bozulmadı; kapının kararı `tests/test_ci_paketleme_kapisi.py`de sentetik
> diff'lerle koşuyor ve orada `static/` hâlâ `hayir` diyor.

---

## ✅ Tur I — Paketleme kapısı ücretsiz bir depo varsayıyordu

**Bitti (28 Ağustos).** Kuyruğun **6. maddesi.** Tur H yayın hattını kotadan
kurtardı; bu tur onun ikizini, PR yolundaki BEDELİ ele alıyor. `ci.yml`'in
yazılı gerekçesi "Depo public olduğundan GitHub-hosted runner dakikaları
faturalanmıyor" diyordu — REST bugün `visibility: private` döndürüyor, yani
gerekçe yanlıştı ve workflow'ların kendi eski "macOS dakikası 10x" endişesi
sessizce geri gelmişti.

- [x] **Kapı daraltıldı: `static/` ve `bundled/` yol listesinden çıktı.** Karar
      ölçüye dayanıyor, tercihe değil: iki dizin de pakete **dizin bütün**
      olarak giriyor — `gpt-image-studio.spec`in `datas=[('static','static'),
      ('bundled','bundled')]` satırı ve `android/app/build.gradle`ın
      `into("resources/static") { from("../../static") }` görevi. İçerik
      değişikliği paketlemeyi kıramaz. `branding/` KALDI, çünkü onun içeriği
      dizin olarak değil ADA GÖRE okunuyor (`lumeo.ico`, `lumeo.iconset` →
      `iconutil`), yani oradaki bir yeniden adlandırma gerçekten patlar.
- [x] **Kapının gerçekten yakaladığı tek sınıf KAYBOLMADI, ucuzladı.** Üç paket
      işi paketin İÇİNDE ada göre dosya arıyor (`static/core.js`,
      `static/mobile.css`, iki woff2, `bundled/prompts/prompt-yonetmeni.md`…);
      bir yeniden adlandırma bu yüzden kırmızıya düşürüyordu. Yeni
      `tests/test_paket_icerik_listesi.py` o listeleri üç workflow'dan
      **ayrıştırıp** (elle kopyalamadan) dosyaların depoda durduğunu ölçüyor.
      Kapsam da genişledi: eski kapı yalnız `static/` değişmiş PR'da
      ateşleniyordu, test HER PR'da ve saniyenin altında koşuyor.
- [x] **Kapının KARARI ilk kez ölçülüyor.** Bugüne dek `kapsam` işinin ürettiği
      `paketle=evet|hayir` yalnız gerçek bir PR koşusunda görülebiliyordu — yani
      bir kusuru ya üç paketleme koşusu harcayarak ya da (daha kötüsü) kapı
      sessizce atlarken öğrenirdik. Betik artık YAML'dan çıkarılıp `git`in yerine
      sentetik bir diff konarak koşuluyor; Tur H'nin yayın kapısı için kurduğu
      desenin aynısı.

**Sentetik ölçüm** (betik gerçekten koşturuldu, metin okunmadı):

| değişen yollar | karar |
|---|---|
| `static/core.js`, `static/mobile.css` | **hayir** |
| `static/folders.js`, `tests/…`, `app.py` | **hayir** |
| `bundled/prompts/prompt-yonetmeni.md` | **hayir** |
| `gpt-image-studio.spec` | evet |
| `android/app/build.gradle` | evet |
| `branding/lumeo.ico` | evet |
| `static/core.js` + `tam-paket` etiketi | evet |
| diff kurulamıyor (git düşüyor) | evet (güvenli taraf) |

**Kazanç geçmişten ölçüldü:** son 12 birleşmiş PR'da eski kapı **11 kez**
ateşliyordu, yeni kapı **6 kez** — beş PR'da üç paketleme işi (macOS'ta 10x
dakika) tümüyle kalkıyor. Kalan altısı gerçekten `android/` ya da
`.github/workflows/` altına dokunmuş PR'lar, yani kapı işini bırakmadı.

- [x] **Kanıt:** takım **1809 → 1831 geçti / 10 atlandı**. **Yedi mutasyon,
      yedisi de kırmızı** — `static/`in kapıya geri gelmesi, `branding/`in
      düşmesi, güvenli tarafa düşmenin kalkması, `tam-paket` kaçış kapısının
      kalkması, bir doğrulama listesinin boşalması, `index.html`in üç listeden
      birden silinmesi ve `static/core.js`in yeniden adlandırılması.

**Aynı yanlış varsayım üçüncü bir yerde daha yaşıyordu ve orası ürün kodu.**
`docs/yayin-hatti.md`in kapı tablosu bu turda düzeltildi (o, kapının belgesiydi),
ama `guncelleme.py` de "Depo public olduğu için uç nokta anonim çalışıyor" diyor
ve GitHub'ın yayın ucunu kimliksiz çağırıyor — private bir depoda o çağrı 404
döner ve Ayarlar'daki "Yeni sürüm çıktı" satırı sessizce hiç görünmez. **Bu
turda DÜZELTİLMEDİ, çünkü ölçülemedi:** oturumun ağı vekil üzerinden geçiyor ve
GitHub isteklerine kimlik ekliyor (`X-Ratelimit-Limit: 5000`; anonim sınır 60),
yani buradan atılan çağrının 200 dönmesi kullanıcıdaki davranışı kanıtlamıyor.
Kuyruğun **5. maddesi** olarak, kanıt zinciriyle yazıldı — ve o madde teknik bir
düzeltmeden çok bir dağıtım kararı: yayın sayfası private ise kullanıcı paketi
zaten indiremiyor.

> **BU TURUN ÖLÇÜMÜ CI'DA GECİKMELİ GÖRÜNÜR.** PR'ın kendisi
> `.github/workflows/` altına dokunduğu için kendi koşusunda kapı `evet` diyecek
> — yani daraltma bu PR'da GÖRÜNMEZ. Görüneceği yer bir sonraki saf ön yüz
> PR'ının günlüğü: `karar: paketle=hayir`. Yukarıdaki sentetik tablo tam da bu
> boşluğu kapatmak için var.

---

## ✅ Tur H — Yayın, ücretsiz olmayan bir depoya bağlıydı

Tur G'nin CI onarımı birikimi durdurdu ama **yetmedi.** Saklama süreleri
kısaltıldı, depodaki 3.98 GiB'ın TAMAMI silindi (221 varlık; buradan
doğrulandı: canlı 0) — kota yine de açılmadı. Kanıt zinciri:

| saat | ne oldu |
|---|---|
| 13:27 | PR #59 CI: üç paketleme işi de `Artifact storage quota has been hit` |
| ~17:00 | merge; Yayın #36 aynı hatayla düştü — `retention-days: 1` kayıtta görünüyor, yani düzeltme canlıydı |
| ~17:30 | bakımcı 217 varlığı sildi; depo 3.98 GiB → **0.00 GiB** |
| 19:58 | **kanarya** (wheel workflow'u, 16 sn, 1.8 MB) yine aynı hata |

- [x] **Ders, sürenin ötesindeydi.** Sayaç 6-12 saatte bir hesaplanıyor ve havuz
      DEPO değil HESAP geneli — yani bu deponun temizliği kotayı açmaya
      yetmeyebilir. Yayın hattı, kendi hatasız ürettiği ikilileri teslim
      edemediği için rehin kalıyordu. Oysa yayın varlıkları (Releases
      altındakiler) o kotaya HİÇ girmiyor: kırılgan olan tek şey aradaki ARA
      KOPYAydı.
- [x] **Paketler artık TASLAK yayına yazıyor.** `taslak` işi boş bir taslak
      açıyor (tag'siz, yalnız yazma yetkisi olanlara görünür), üç paket işi
      `gh release upload` ile doğrudan ona yüklüyor, `yayinla` küme denetimini
      taslağın İÇİNDE yapıp tek `--draft=false` çağrısıyla yayımlıyor.
      Bayt akışı da kısalıyor: derleyen makineden doğrudan son yerine.
- [x] **TEK YAZICI güvencesi korunuyor.** v0.4.2'nin "95 saniye boyunca yarım
      yayın" sınıfı buraya ulaşamaz çünkü yazılan şey taslak. Mandal da o
      ayrımı öğrendi: artık YÜKLEYEN işleri değil YAYIMLAYAN işi sayıyor
      (`--draft=false`), ve tam bir tane olmalı.
- [x] **Wheel de varlıktan çıktı** — 1.8 MB'dı ve yayını yine de kırıyordu;
      kota dolunca boyut önemsiz. Teslim artık ÖNBELLEK (ayrı ve ücretsiz
      havuz, depo başına 10 GB) ve wheel zaten oraya yazılıyordu, yani yeni bir
      depolama eklenmedi. Anahtar `wheel` işinin ÇIKTISI: çivi çözme mantığı
      çağıranda ikinci kez yazılsaydı sessizce ayrışırdı.
- [x] **PR koşusu artık hiçbir yere teslim etmiyor** (`taslak` girdisi boş).
      Kapının sorusu zaten "paketleme ayakta mı"; kotayı dolduran birikimin
      büyük kısmı da PR'ların kimsenin okumadığı paketleriydi.
- [x] **İzin bloğu paket workflow'larından KALDIRILDI** — çağırandan devralınıyor.
      Sabit yazılamazdı: çağrılan workflow çağıranından fazla izin isteyemez,
      yani `contents: write` yazılsaydı `ci.yml` (read) bu workflow'u HİÇ
      çağıramaz, PR'daki paketleme kapısı tümden düşerdi.

**Kaynak deseninin göremediği bir kusuru gözle yakaladım:** teslim adımı ilk
yazımda kabuğunu bildirmiyordu. `windows-latest`'ta `run:` varsayılanı
**pwsh**'tir ve orada `set -euo pipefail` bir komut bile değil — yani "eksik
dosya adımı kırmızıya düşürür" güvencesi Windows'ta sessizce yalandı ve mandalım
da (metinde o satırı arıyordu) yeşil kalıyordu. Üç teslim tek deyime sabitlendi
(`shell: bash`) ve iddia artık kabuğu da ölçüyor.

**Bir mandal daha ANLATIYI doğrulamıştı.** "Teslim manifestteki adı kullanıyor"
iddiası adımın TAMAMINA bakıyordu; adımın sonundaki `echo` da dosya adını
yazdığı için, komuttaki adı bozan mutasyon iddiayı hayatta bıraktı. İddia
`gh release upload` SATIRINA indirildi. §0.6'nın dersi bu turda onuncu kez.

- [x] **Yayın kapısının kendisi artık bedava sınanıyor.** `yayinla` işine gömülü
      küme denetimi betiği YAML'dan çıkarılıp sentetik `varliklar.tsv` ile
      koşuluyor: tam küme geçiyor, eksik/fazla/0-bayt üçü de kırmızı. O betik
      daha önce yalnız gerçek bir yayın koşusunda çalışıyordu, yani bir kusuru
      ancak sürüm harcayarak öğrenirdik.
- [x] **Kanıt:** takım **1803 → 1809 geçti / 10 atlandı**. **On mutasyon, onu da
      kırmızı.** Yayın yolunda artık tek bir `upload-artifact` yok.

> **KANITLANDI (aynı gün, gerçek koşuyla).** Tek açık kalan soru çağrılan
> workflow'un izni çağırandan devralmasıydı: kaynakta doğrulanamıyordu ve
> yanılma belirtisi `gh release upload`ın 403 dönmesi olacaktı. PR #60 21:11'de
> birleşti, **Yayın koşusu yeşil bitti ve `v0.11.5` 21:15:35'te yayımlandı** —
> yani izin devralındı, üç paket taslağa yazdı ve tek `--draft=false` çağrısı
> tag'i de yayını da doğurdu. Kota kırılmasından beri çıkan ilk yayın bu.
>
> Yayın yolu böylece kotadan tümüyle çıktı, ama **elle bakım yolu çıkmadı:**
> `build-pydantic-core-android.yml` içindeki tek `upload-artifact` hâlâ orada
> (`varlik_yukle` bayrağına bağlı, Yol A). O yolun kotayla düştüğü aynı gün
> ölçüldü: 19:58 ve 20:10'daki iki kanarya koşusu `Artifact storage quota has
> been hit` ile bitti. Yayın etkilenmiyor; pydantic çivisi güncellenirken
> lazım olacak. Kuyrukta madde olarak duruyor.

---

## ✅ Tur G — Seçici klavye kullanıcısının YERİNİ üç ayrı yoldan kaybediyordu

**Bitti (28 Ağustos).** Kuyruğun **1. maddesi** (odak) ve **2. maddesi** (iç içe
klasör künyesi) üste alındı; ikisi `renderPickerGrid`'in aynı elli satırında
yaşıyordu ve ayrı turlarda yapmak aynı üç dosyayı iki kez açmak olurdu (Tur C'nin
gerekçesi). Tur, kod okunurken çıkan **üç bulguyla** genişledi — üçü de aynı
kusurun başka yüzeydeki kopyası, üçü de ölçüldü.

- [x] **Seçimde ızgara artık yeniden KURULMUYOR** (kuyruk 1). Tıklama
      `renderPickerGrid()` çağırıyordu ve o `grid.innerHTML = ""` ile bütün
      karoları siliyordu. **Ölçüldü (önce):** karoya Enter'a basıldıktan sonra
      `document.activeElement` = `<body>`, üç genişlikte de. Yani Tur C'nin
      `aria-pressed` kazanımı tam da onu duyacak kullanıcıda siliniyordu.
      **Ölçüldü (sonra):** odak AYNI DÜĞÜMDE (düğüme damga basılıp doğrulandı),
      basılı karo sayısı 1. Yerine `syncPickerPressed()`: var olan karolarda
      yalnız özniteliği çeviriyor. Delta yazımı (eski seçiliyi bul, kapat)
      REDDEDİLDİ — onu yazmanın yolu `querySelector('[aria-pressed="true"]')`,
      yani kaynağı BOYA yapmak; B3 mandalı zaten bunu yasaklıyor.
- [x] **`aria-pressed`in TEK yazıcısı var.** Kurulum satırı silinip
      `renderPickerGrid` de aynı süpürmeyle bitiriliyor. İki yazıcı bırakmak bu
      depoda iki tur yakmış bir desendi (Tur C'nin ikiz CSS kuralları). Sıra
      mandallı: süpürme karolar EKLENDİKTEN sonra koşmak zorunda, yoksa
      `querySelectorAll` boş küme görür ve hiçbir karo işaretlenmez — sessiz,
      hatasız bir kırılma.
- [x] **BULGU 1 — düzeltmenin kendi yan etkisi: odak halkası kayboluyordu.**
      Seçim ızgarayı yeniden kurmadığı için "seçili VE odaklı" karo artık klavye
      kullanıcısının NORMAL hâli. `.picker-tile[aria-pressed="true"]` (0,2,0)
      global `:focus-visible`i (0,1,0) `outline` yarışında EZİYOR — düzeltmeden
      önce görünmüyordu çünkü ikisi hiç bir arada olmuyordu. Yani düzeltme tek
      başına ekran okuyucu kullanıcısını kazandırıp **gören klavye
      kullanıcısını kaybettirirdi.** İki işaret AYRI kanaldan: `outline` içeride
      seçimi, `box-shadow` dışarıda odağı söylüyor. **Ölçüldü:** seçili+odaklı
      karoda `outline 2px … offset -2px` VE iki katmanlı `box-shadow`.
- [x] **BULGU 2 — aynı kusur kapsam şeridinde de vardı.** `renderPickerNav` da
      `nav.innerHTML = ""` yapıyor. **Ölçüldü (önce):** kapsam düğmesine
      klavyeyle basınca odak `<body>`. Orada yeniden kurmak KAÇINILMAZ (sayaçlar
      hem kapsamla hem her tuş vuruşuyla değişiyor), o yüzden çözüm farklı: odak
      ANAHTARDAN iade ediliyor (`chat.js:closeMenus` deseni). Koşul şart ve iki
      iş yapıyor — fareyle süzenin odağını şeride zorla taşımıyor VE arama
      kutusuna yazanın odağını her tuşta çalmıyor. `core.js`'in `isConnected`
      muhafızı BİLEREK kopyalanmadı: orada düğüm yıkımdan ÖNCE tutuluyor, burada
      yıkımdan SONRA bulunuyor. **Ölçüldü (sonra):** odak yeni düğmede ve
      `dataset.key` aynı.
- [x] **BULGU 3 — "Ek olarak ekle" kendi altındaki odağı kapatıyordu.** Ekleme
      başarılı olduğu ANDA `extraBlockReason` doluyor ve `renderPickerSide`
      düğmeyi `disabled` yapıyor; odaklı bir düğmeyi disable etmek odağı
      `<body>`ye düşürüyor. **Ölçüldü (önce):** Enter'dan sonra
      `activeElement` = `<body>`, düğme `disabled`, not "Eklendi · 1/3". Yani
      B7'nin gerekçesi ("üç ek slotu var, her biri için menüden dönmek saçma
      olurdu") klavye kullanıcısında TAM TERSİNE dönüyordu. `#picker-note`
      `role="status"` olduğu için ONAY duyuluyordu; kaybolan şey YER. Odak
      seçili KAROYA dönüyor, "Referans yap"a değil — o düğme seçiciyi kapatır,
      ikinci Space turu bitirirdi.
- [x] **Künye zincirin tamamını yazıyor, YAPRAĞI gömmeden** (kuyruk 2). Aranan
      şey zaten vardı (`folderPath`); ortak `folderPathParts` + tek ayraç sabiti
      eklendi, `pickerFolderLabel` ona devredildi. **Düz uçtan kırpma ÇÖZÜM
      DEĞİLDİ ve bu ölçüldü:** 360px'te kart 359px, ızgara 335px,
      `minmax(96px, 1fr)` üç sütun veriyor, karo **104px**, künye kutusu
      **84px** (≈12 karakter). "Kampanyalar / Bayram" sondan kırpılınca
      "Kampanyala…" kalırdı — kullanıcının aradığı YAPRAK tam da kaybolan yarı,
      yani bugünkünden ("Bayram") KÖTÜ. İki kutu: üst zincir eriyor, yaprak
      duruyor. **Ölçüldü (sonra):** üst "Kampanyalar" kırpılıyor, yaprak
      " / Bayram" 51px ile TAM, künye tek satır, karo taşması 0.
- [x] **BULGU 4 — künye kusurunun üçüncü kopyası: arama sonucu rozeti.**
      `.card-where`'in KENDİ yorumu "sonuçlar tüm klasörlerden geliyor, adsız
      iki varyant ayırt edilemez" diyerek var oluş sebebini anlatıyordu — ama
      yalnız en yakın klasörü yazdığı sürece iç içe iki ayrı "Bayram" hâlâ
      birbirinin aynısıydı, yani rozet tam da engellemek için konduğu
      belirsizliği üretiyordu. Aynı düğümden geçiyor artık. **Ölçüldü:** 360px
      ve 1024px'te rozet zinciri yazıyor, kart taşması 0, konsol temiz.
- [x] **İki CSS bildirimi yük taşıyor ve ikisi de tarayıcıda doğrulandı** —
      yorumdaki iddia "öyle olmalı" değil, ölçüm: `.zincir-yaprak`ta
      `white-space: pre` (`nowrap` DEĞİL) çünkü her esnek öğe kendi satır
      kutusunu açıyor ve satır başındaki boşluk atılıyor — **ölçüldü:** aynı
      DOM metniyle (`" / Bayram"`) çizilen genişlik `pre`de 51.4px, `nowrap`ta
      47.9px, yani ayracın boşluğu gerçekten yutuluyor ("Kampanyal…/ Bayram").
      `max-width: 100%` ise `flex: none`un bedeli: **ölçüldü** — o bildirim
      silinince uzun bir yaprak 83px'lik kapta 156px'e büyüyor, karo taşması
      63px oluyor ve `.picker-tile`ın `overflow: hidden`ı onu ÜÇ NOKTASIZ
      kesiyor.
- [x] **Ölmüş bir mandal DÖNÜŞTÜRÜLDÜ, silinmedi.** Zincir ortak yardımcıya
      taşınınca `test_the_picker_labels_folders_with_a_string_not_the_breadcrumb_array`
      seçici diliminde SIFIR eşleşme buluyordu: döngü hiç dönmüyor, iddia
      kendiliğinden vacuous olmuş ve yeşil kalarak hiçbir şey korumuyordu.
      Sessizce ölen bir mandal hiç yazılmamış olandan kötü; iddia
      `folderPathParts`e çevrildi. ("Her `folderPath(...)` çağrısının ardından
      `.map(` gelmeli" iddiası dosya geneline AÇILAMAZDI: dört çağrıdan biri
      diziyi meşru olarak bir değişkene alıyor.)
- [x] **Kanıt (inceleme öncesi):** takım **1789 → 1796 geçti / 10 atlandı** (7 yeni mandal:
      `test_index.py`'de altı, `test_mobile.py`'de yerleşim mandalı).
      **Yirmi mutasyon, yirmisi de KIRMIZI** — geri alma `git checkout --` ile
      DEĞİL scratchpad kopyalarından (Tur B'nin kaydettiği tuzak) ve betik
      hedefi bulamazsa patlıyor. Ayrıca kapta Chromium 1194'e uyan Playwright
      kurulup `tests/test_playwright_studio.py`'nin **7 gerçek tarayıcı testi
      de koşturuldu: yedisi de yeşil** (CI'da paket kurulu olmadığı için orada
      atlanmaya devam ediyor).
      Odak mandalı AD ARAMIYOR, erişilebilirlik arıyor: "ızgarayı yeniden kuran"
      işlevlerin tanımı KODDAN çıkarılıp geçişli kapanışı alınıyor. İlk yazım
      `"renderPickerGrid(" not in govde` idi ve mutasyon **2**'de hayatta
      kalırdı — `renderMediaPicker()` de aynı yıkımı yapıyor. §0.6/§0.7/§0.9'un
      "iddia kodu arar, kelimeyi değil" dersinin yedinci kurbanı.

### İnceleme turu — beş gerçek bulgu, biri turun KENDİ kusuruydu

Kod incelemesi on iki bulgu getirdi; hepsi kaynağa bakılarak doğrulandı, beşi
ölçülerek kapatıldı, kalanlar (ölü bildirimler, dolaylılık, tek yürüyüş) aynı
turda temizlendi.

- [x] **Üst zincir SIFIRA iniyordu — bu turun kendi kusuru.** İlk yazımda yaprak
      `flex: none`, üst zincir `min-width: 0` idi. **Ölçüldü:** uzun yapraklı bir
      zincirde ("Kampanyalar / Bayram / Ramazan Bayrami 2026") üst kutu **0px**
      oluyor; 0px'te `text-overflow` boyayacak yer bulamıyor, yani ÜÇ NOKTA DA
      çıkmıyor ve künye ekranda sahipsiz bir " / Ramazan Bayrami…" hâline
      geliyordu. Yani turun kendi vaadi ("üst zincir eriyor, yaprak duruyor")
      yalnız KISA yapraklarda doğruydu. Daralma artık sıralı ve TABANLI: üst
      zincirin ağırlığı yaprağın yüz katı ama `min-width: 2.5ch`, yaprak da
      `min-width: 0` ile daralabiliyor. **Ölçüldü (sonra):** üst kutu 16.5px,
      görünür ve kırpılmış; satır taşması 0.
      *Ders:* mandal `text-overflow: ellipsis`in VARLIĞINI sınıyordu;
      boyanabilmesini sınamıyordu.
- [x] **Odak kusurunun DÖRDÜNCÜSÜ: seçici kapanışı.** `hidden = true` odaklı
      karoyu `display: none` yapıyor. **Ölçüldü:** Escape'ten sonra
      `activeElement` `<body>`. `core.js`in `dialogPrevFocus` deseni geldi —
      ama **ilk yazım işe yaramadı ve sebebi ölçüldü:** açan düğme
      (`#media-pick-btn`) (+) menüsünün İÇİNDE ve o menü seçici açılırken
      kapanıyor; düğüm DOM'da (`isConnected` true) ama `[hidden]` bir kabın
      içinde, yani `.focus()` SESSİZCE hiçbir şey yapıyor. Hedef artık
      görünürlüğe göre seçiliyor, görünmezse menüyü açan `#plus-btn`e dönülüyor.
      **Ölçüldü (sonra):** iki genişlikte de odak `#plus-btn`.
      "Referans yap" dalı iadeyi bilerek KAPATIYOR (o yol odağı `#prompt`a
      taşıyor); asimetri mandallı.
- [x] **Izgaranın yeniden kurulduğu yollar açıkta kalmıştı.** Seçim artık oraya
      uğramıyor ama arama, kapsam değişimi ve `openPicker`'ın bekleyen
      `loadAllImages` yanıtı hâlâ `innerHTML = ""` yapıyor. Sonuncusu en sinsisi:
      `openPicker` `pickerImages`i temizlemiyor, yani bayat liste HEMEN
      boyanıyor, kullanıcı bir karoya geçiyor ve yanıt gelince ızgara altından
      siliniyor. `renderPickerNav`ın iadesi buraya da geldi.
- [x] **Arama rozeti EKRAN OKUYUCUYA ulaşmıyordu.** Kırpmayı CSS'e vermenin
      yazılı gerekçesi "ekran okuyucu zinciri tam duyar" idi; bu yüzeyde DOĞRU
      DEĞİLDİ, çünkü kart açık bir `aria-label` taşıyor ve açık etiket
      içindeki metnin erişilebilir ada katılmasını engelliyor. Zincir artık
      `aria-label`ın kendisine giriyor.
- [x] **Ayracın "tek sabit" iddiası doğru DEĞİLDİ.** `KLASOR_AYRACI` tanıtılmıştı
      ama kırıntı başlığı ile taşıma listesi kendi `join(" / ")`ünü yazmaya devam
      ediyordu — yani sabitin yorumu üç yüzeyi anlatırken kod ikisini dışarıda
      bırakıyordu. İkisi de ortak etikete bağlandı; dosyada `" / "` artık **bir**
      kez geçiyor ve bir mandal ikinciyi yasaklıyor. (Kuyruğun 2. maddesi bu
      turda kapandı.)
- [x] **Kaynak deseninin göremediği kusuru gerçek tarayıcı yakaladı.** Rozet
      düzeltmesinin ilk yazımında `let kartYolu` erişilebilir addan SONRA
      duruyordu; `let`in ölü bölgesi yüzünden `renderGallery` daha ilk kartta
      `ReferenceError` atıyor ve galeri HİÇ çizilmiyordu. Bütün kaynak mandalları
      yeşildi; `test_playwright_studio.py` kırmızıya döndü. Ölçümün neden bu
      defterin standardı olduğunun tazelenmiş kanıtı.
- [x] **Mutasyon turunda İKİ mandal kaçtı ve ikisi de kelime aramasıydı** —
      §0.6'nın dersi bu turda sekizinci ve dokuzuncu kez. `if (false) …focus()`
      mutasyonu `".focus()" in govde` iddiasını hayatta bırakıyordu; iddia artık
      iadenin KAPISINA bakıyor (kapı, yıkımdan önce yakalanan kimliğin ya da
      işlevin kendi parametresinin ta kendisi olmalı).
- [x] **Kanıt:** takım **1796 → 1805 geçti / 9 atlandı** (Playwright kurulu;
      CI koşulunda 1798 / 10). Mandal sayısı 7 → 9. **Otuz mutasyon, otuzu da
      kırmızı.**

**Tarayıcı ölçümü** (Chromium 1194; 12 görsel, 4 klasör, biri üç seviyeli):

| Ölçü | 360×780 önce | 360×780 sonra | 800×700 sonra | 1024×700 sonra |
|---|---|---|---|---|
| karo | 104px | 104px | 99px | 106px |
| Enter'dan sonra odak | **`<body>`** | **aynı karo** | aynı karo | aynı karo |
| kapsam Enter'ından sonra odak | **`<body>`** | **aynı çip** | aynı çip | aynı çip |
| "Ek olarak ekle" Enter'ından sonra | **`<body>`** | seçili karo | — | — |
| seçili+odaklı halka | yok (odak yok) | outline + box-shadow | aynı | aynı |
| künye (iki seviyeli) | `Bayram` | `Kampanyal… / Bayram` | aynı | `Kampanyalar / Bayram` |
| künye satır sayısı | 1 | 1 | 1 | 1 |
| yatay taşma | 0 | 0 | 0 | 0 |
| konsol | temiz | temiz | temiz | temiz |

> **Kapsam genişlemesinin gerekçesi.** Defter iki madde söylüyordu, tur beşi
> kapattı. Dördü aynı dosyanın aynı iki işlevinde ya da onların bir ekran
> ötesinde; biri (odak halkası) düzeltmenin KENDİ yan etkisi, yani onsuz tur
> yarım kalırdı — ekran okuyucu kullanıcısı kazanırken gören klavye kullanıcısı
> kaybederdi. Tur B'nin "ÜÇÜNCÜ BULGU" ve Tur C'nin "aynı bileşene iki kez
> dokunma" kayıtları emsal.

### CI onarımı — kırmızı, kod hakkında HİÇBİR ŞEY söylemiyordu

Tur G'nin PR'ında (#59) CI'ın üç paketleme işi de kırmızıya düştü. Üçünün de
sebebi aynıydı ve hiçbiri bu turun diff'i değildi:

```
Failed to CreateArtifact: Artifact storage quota has been hit.
```

Paketler DERLENİP DOĞRULANDIKTAN sonra ölüyorlardı — macOS `Info.plist 0.11.4`,
Windows `FileVersion`/`ProductVersion`/`FixedFileInfo`/`CompanyName` dördü de
yeşil, Android wheel'i etiketi ve `.so`suyla doğrulanmış. Testler de yeşildi.
Kırmızı olan yalnız `upload-artifact` adımıydı.

**Ölçüm** (GitHub REST, 28 Ağustos 2026): depoda **221 canlı varlık / 3.98 GiB**.

| varlık | adet | boyut | tüketicisi |
|---|---|---|---|
| `lumeo-windows-x64` | 48 | 1.33 GiB | `release.yml`/`yayinla` — **aynı koşu** |
| `lumeo-macos-arm64` | 47 | 1.12 GiB | aynı koşu |
| `lumeo-android-arm64` | 48 | 0.88 GiB | aynı koşu |
| eski adlandırma (`gpt-image-studio-*`) | 22 | 0.55 GiB | **hiç kimse** (ad değişti) |
| `pydantic-core-android-arm64` | 56 | 0.10 GiB | `_paket-android.yml` — aynı koşu |

- [x] **KÖK SEBEP: saklama süresi varlığın İŞİNDEN bağımsız seçilmişti.**
      Dört yükleme var, iki indirme; iki indirme de `run-id` VERMİYOR, yani
      ikisi de kendi koşusundan okuyor. Yani hiçbir varlığın tüketicisi kendi
      koşusunun dışında değil — ama paketler 30, wheel 90 gün tutuluyordu.
      Tüketicisi dakikalar sonra biten bir dosya bir ay kotada duruyordu.
      Paketler **1 güne**, wheel **7 güne** indi. Wheel'in 1 değil 7 olmasının
      sebebi ölçülü: koşu dışında GERÇEK bir insan tüketicisi olan tek varlık o
      (Yol A'da bakımcı elle tetikleyip `android/wheels/` altına işliyor) ve
      hacmin yalnız %2.5'i.
- [x] **Neden PR sürümü/atlama DEĞİL.** "Paketleri PR'da hiç yükleme" daha
      büyük bir kazanç olurdu ama `ci.yml`'in kendi gerekçesi buna karşı:
      "PR'da yeşil olan şey, yayında koşacak şeyin ta kendisi." Yükleme adımını
      PR'da atlamak, 2026-08-11'de gerçekten kusur yakalamış bir kapıyı
      (`if-no-files-found: error` + `cp` hedefi ile `path:` arasındaki kayma)
      yalnız yayın yolunda bırakırdı. Saklama süresini kısaltmak hiçbir kapıyı
      zayıflatmıyor.
- [x] **Yeni mandal:** `tests/test_ci_varlik_saklama.py` (5 iddia). Süreyi VE
      süreyi savunulabilir kılan VARSAYIMI mandallıyor: bir indirme `run-id`
      alırsa "tüketici aynı koşuda" cümlesi yanlışa döner ve o gün test, süreyi
      yeniden düşünmesi gereken kişiye tam olarak orayı gösteriyor. Ayrıca
      ayrıştırıcının boş küme toplamasına karşı sayı METİNDEN türetiliyor —
      §0.6'nın dersi. **Beş mutasyon, beşi de kırmızı.**
- [x] **Mutasyon ④ önce hayatta kaldı ve sebebi mandal değil MUTASYONDU:**
      `run-id`'yi adımın var olan `with:` bloğunun yanına ikinci bir `with:`
      olarak yazmıştım; YAML yinelenen anahtarda sessizce sonuncuyu alıyor,
      yani mutasyon hiç uygulanmamıştı. Tur B'nin "mutasyon hedefi bayatladı"
      kaydının kardeşi: **hayatta kalan bir mutasyon önce mutasyonun kendisini
      şüpheli kılar.**
- [x] **Kanıt:** takım **1798 → 1803 geçti / 10 atlandı**.

> **ÇÖZÜLMEYEN YARI — kotanın kendisi.** Yukarıdaki düzeltme birikimi
> durduruyor ama var olan 3.98 GiB'ı silmiyor; kota dolu kaldığı sürece yeni
> koşu da yükleyemez. Eski varlıkların temizliği API'den yapılabilir ve
> geri alınamaz olduğu için bakımcının kararına bırakıldı.

> **AYRICA: `ci.yml`'in bir gerekçesi artık YANLIŞ.** Dosya "Depo public
> olduğundan GitHub-hosted runner dakikaları faturalanmıyor; workflow'lardaki
> eski 'macOS dakikası 10x sayılıyor' gerekçesi artık geçerli değil" diyor.
> Depo bugün **private** (REST ile doğrulandı). Yani hem dakikalar faturalanıyor
> hem 10x çarpanı geri döndü — `static/` altına dokunan her PR üç paketi de
> derletiyor. Bu bir POLİTİKA kararı (kapı mı, maliyet mi), o yüzden kuyruğa
> yazıldı, bu turda değiştirilmedi.

---

## ✅ Tur F — Telefonda yükleme dört halkadan kırılıyordu (geriye dönük kayıt)

**Bitti (24-26 Ağustos), v0.11.1–v0.11.4, PR #55-58.** Defter o gün
güncellenmedi; kayıt commit'lerden okunarak yazıldı. Tur **kullanıcı
şikâyetiyle** açıldı ("telefonda logo yükleyemiyorum") ve şikâyet TEK bir kusur
değil, art arda dizilmiş dört kapı çıktı — her düzeltme bir sonrakini görünür
yaptı. Ders defterde duruyor: *bir yüklemenin çalışması için dört ayrı katmanın
aynı anda doğru olması gerekiyordu ve hiçbiri hata vermiyordu.*

- [x] **v0.11.1 — hedef tür.** Kütüphane sekme şeridi bir SÜZGEÇ ama yükleme
      hedefi `assetPanelKind`'dan okunuyordu: varsayılan sekmede ("Tümü") dosya
      `uploads` türüne yazılıyordu — hiçbir bindirmenin okuyamadığı ölü bir tür.
      Kullanıcı "Eklendi." okuyup sonra "Önce Kütüphane'den bir logo yükle"
      görüyordu. Düğme artık hedefini ADIYLA söylüyor ("+ Logo yükle").
      İkinci kusur aynı commit'te: `#extra-add-btn` dosya seçiciyi koşulsuz
      açıyordu, kapı seçimden SONRA soruluyordu, yani seçilen dosya sessizce
      düşüyordu.
- [x] **v0.11.2 — seçici süzgeci ve MIME.** `createIntent()` `accept`
      listesinin yalnız İLK türünü `setType()`e koyuyor: intent
      `type = "image/png"` doğuyordu ve yalnız `type`a bakan galeriler JPEG'leri
      GİZLİYORDU — logosu `.jpg` olan kullanıcı dosyayı seçemiyordu bile.
      İkinci kapı web tarafında: MIME denetimi yalnız `File.type`a bakıyordu,
      Android WebView ise onu ContentResolver'dan alıyor ve pek çok sağlayıcı
      boş dize ya da `application/octet-stream` döndürüyor. Yeni kural
      "**RED için kanıt gerekir**": dosya çelişkili bir şey iddia etmiyorsa
      sunucu karar veriyor.
- [x] **v0.11.3 — asıl kök neden: `ClipData`.** `parseResult()` yalnız
      `Intent.getData()`ya bakıyor; çoklu seçimde sonuç `getClipData()`de
      geliyor ve `parseResult` `null` dönüyor, WebView bunu "kullanıcı iptal
      etti" sanıyor. Kütüphane girdisi `multiple` olduğu için TEK dosyada bile
      URI ClipData'ya düşüyordu — Kütüphane yüklemesi telefonda hiç
      çalışmamışken referans yolunun (tek seçim) hep çalışmasının sebebi buydu.
- [x] **v0.11.4 — üç eksik kapı.** Büyeteçte "Logo ekle" yoktu (bindirmeye tek
      giriş `#logo-add-btn`, o da yalnız `currentImage` varken açık); seçim
      kipinde kartın ortası tıklanamıyordu (dokunmada eylem şeridi kartın
      ~%58'ini kaplıyor, `display: none` gerekti — görünmez şerit dokunuşu
      yutuyor); ve Medya'da **"Yükle" düğmesi hiç yoktu** — `importFiles` ile
      `/api/import` eksiksizdi ama tek tetik dokunmada çalışmayan sürükle-bırak
      olduğu için telefondan galeriye görsel koymanın YOLU YOKTU, üstelik ipucu
      metni var olmayan bir kontrolü anlatıyordu.
- [x] **Süreç boşluğu adlandırıldı.** `docs/android/mimari.md`'deki elle
      doğrulama listesinde yalnız tek-seçim satırı vardı; kusurun bir sürümü
      atlatmasının sebebi tam olarak buydu. "Çoklu seçim" satırı eklendi ve
      tek-seçimin geçmesinin bu yolu KANITLAMADIĞI yazıldı.
- [x] **Kanıt ve yöntem:** depoda Android SDK yok, o yüzden Kotlin işlevleri
      birebir çıkarılıp **Java ile yazılmış** Android stub'larına karşı
      `kotlinc -Werror` ile derlendi ve 8'er senaryoda KOŞTURULDU (Java bilerek:
      Kotlin platform tiplerini görsün diye). Mandallar `test_index.py`,
      `test_mobile.py`, `test_playwright_studio.py`'de; biri kendi kendini
      ısıran cinsten — Kotlin KDoc'una yazılan bir joker MIME yorum bloğunu
      kapatıp derlemeyi kırıyor ve bunu yalnız Android koşucusu görürdü.
- [ ] **AÇIK BIRAKILDI (gerekçeli):** `assets_store.KINDS` içindeki `uploads`
      türü ölü ama duruyor — hiçbir şey oraya yazmıyor, hiçbir sekme
      göstermiyor, ama eskiden yazılmış varlıklar "Tümü" altında görünsün ve
      silinebilsin diye tür kaldırılmadı. Gerçek bir göç yapılmadı.
- [ ] **AÇIK BIRAKILDI (gerekçeli):** istemci MIME kapısı bilerek gevşetildi;
      son söz sunucuda (`app._to_png` → 422). Android doğruluğu CI'da
      derlenmiyor, elle doğrulama tablosuna dayanıyor.

---

## ✅ Tur E — Masaüstü sunucusu tarayıcıdan korunuyor (geriye dönük kayıt)

**Bitti (23-24 Ağustos), v0.11.0, PR #54.** Defter o gün güncellenmedi; kayıt
commit'lerden okunarak yazıldı.

- [x] **`netguard.py` — istek kaynağı kapısı.** İki saldırı kapandı.
      (a) **CSRF:** `/api/edit`, `/api/import`, `/api/assets/{kind}`
      `multipart/form-data` alıyor, yani CORS'un "basit istek"i — ÖN UÇUŞ YOK.
      Kullanıcının tarayıcısındaki herhangi bir sayfa onun ücretli API kotasını
      yakabilir ve galerisine yazabilirdi. (b) **DNS rebinding:** `Host` hiç
      denetlenmiyordu, yani `/api/history`, `/api/chats` ve `/output/*` açıktı.
      Kural: `Host` loopback olmak zorunda (BAŞLIĞIN YOKLUĞU da reddediliyor —
      HTTP/1.1'de zorunlu, yokluğu "tarayıcı değil" demek); `Origin` varsa
      `http://{Host}`e eşit olmalı. Kendi kaynağı **Host'tan türetiliyor**,
      sabit yazılmıyor: `desktop.py` `port=0` ile bağlanıyor.
- [x] **Ara katman DEĞİL sarmalayıcı, ve gerekçesi ölçüldü.** `app.app` modül
      düzeyinde tekil ve Starlette ara katman yığınını ilk istekte donduruyor;
      `add_middleware` yolu `tests/test_desktop.py`'yi "Cannot add middleware
      after an application has started" ile düşürdü. Sonuç: **`app.py`'ye hiç
      dokunulmadı**, kapı `desktop.py` ve `run.sh` girişlerinde kuruluyor —
      `TestClient` (Host: `testserver`) kapıyı hiç görmüyor.
- [x] **CRLF enjeksiyonu kapandı.** `/api/folders/{id}/download` klasör adını
      `Content-Disposition`a koyuyordu ve temizlik `[^\w\s-]` desenliydi —
      `\s` CR/LF'i **koruyor**. Bugünkü uvicorn başlığı reddettiği için belirti
      yakalanmamış bir ASGI hatası ve indirilemeyen bir klasördü; başka bir ASGI
      sunucusunda gerçek yanıt bölmesi olurdu. Desenin İKİ kopyası vardı; ikisi
      de tek `folders.safe_component()`e indi. Yan fayda docstring'de yazılı:
      `.` ve `/` de düştüğü için ZIP girdileri artık `..` taşıyamıyor.
      Girişte ikinci kapı: `models.FolderRequest.name` denetim karakterlerini
      eliyor. Mandal desenin ÜÇÜNCÜ kez doğmasını engelliyor.
- [x] **Şema denetimi bütün sağlayıcılara yayıldı** (`azure_client.check_base_url`).
      `http://` bilerek kabul ediliyor — ComfyUI/Ollama orada yaşıyor.
- [x] **Kanıt:** yeni `tests/test_netguard.py` (kapıyı GERÇEK uvicorn ve gerçek
      soket üzerinden ölçüyor, artı iki mandal giriş noktalarının sarmalayıcıyı
      gerçekten kullandığını zorluyor) ve `tests/test_guvenlik_baslik.py`.
- [ ] **AÇIK BIRAKILDI (gerekçeli):** kapı `http`ye sabitli (TLS sonlandıran bir
      vekil eklenirse o satır öğretilmeli — kırılma sessiz değil, 403 olsun
      diye böyle seçildi) ve **jetonsuz**, Android'in `SessionCookieGuard`ının
      aksine: masaüstünde düşman bir yerel süreç zaten `credentials.env`i
      okuyabiliyor, paylaşılan sır bir şey satın almıyor. Ayrıca kapı yalnız
      BİLİNEN iki giriş noktasında: `app:app`i doğrudan servis eden üçüncü bir
      giriş korumasız olur.

---

## ✅ Tur D — Model Arena (o günkü kuyruk maddesi 8)

**Bitti (23 Ağustos).** Kuyruğun **8. maddesi** üste alındı. Kapsam oturumda
netleşti: 2–4 model seçilebilir · sütun başına AYRI kayıt, ortak `arena_id` ·
yalnız üretim (`/api/edit` kapsam dışı) · kazanan işaretleniyor, elenen
sonuç SİLİNMİYOR · yüzey composer'da bir anahtar · kalite ekseni SIRA ile
eşleniyor.

- [x] **Fan-out İSTEMCİDE, sunucuda değil.** Turun kendisi model başına ayrı
      bir `POST /api/generate`; sunucuya yeni bir üretim ucu, kuyruk ya da iş
      parçacığı havuzu GİRMEDİ. Üç ölçülmüş sebep: (a) zaman aşımı bütçesi
      model başına hesaplanıyor (`providers.total_budget`), tek istekte
      fan-out isteği en yavaş modele bağlardı — Nano Banana Pro'lu bir turda
      dakikalarca asılı bir bağlantı; (b) uçtaki hata modeli tek yollu
      (`except ac.ImageError → 502`, app.py:379) ve "3 modelden 1'i düştü"yü
      ifade edemiyor; (c) sunucu zaten çok iş parçacıklı (senkron `def` +
      anyio havuzu), yani N istek gerçekten paralel koşuyor.
      **Ölçüldü** (Chromium 1024×700): iki istek arasındaki fark **0.000s**,
      iki sütun **0.7s**'de doldu.
- [x] **Şema göçü YOK.** `arena_id` kayda KOŞULLU yazılıyor
      (`imported`/`session_id` deseninin aynısı, storage.py) — arena dışı
      üretimin kaydı bugünküyle bayt bayt aynı. **Ölçüldü:** arena kapalıyken
      tek istek gidiyor, son kayıtta `arena_id` anahtarı HİÇ yok.
      `ResultParams.arena_id` de boş dize varsayılanıyla geldi (v0.6'da
      `model`in girdiği yolun aynısı), yani v0.6 öncesi oturumlar geçerli
      kalıyor.
- [x] **Eksen çevirisi arenanın asıl işi ve TEK yerde.** Modellerin jeton
      kümeleri farklı: Azure `1024x1536`, Gemini `2:3`; Azure düşük/orta/yüksek,
      Gemini 1K/2K/4K. Kullanıcı TEK ayar seçiyor, `arenaSutunlari()` model
      başına çeviriyor — boyut ORAN üzerinden (`sizes[].ratio` sunucudan
      geliyor, istemci jeton ayrıştırmıyor), kalite SIRA üzerinden. Aynı
      fonksiyonu hem maliyet göstergesi hem üretim isteği okuyor: iki ayrı
      yerde çevrilseydi gösterilen fiyat ile faturalanan tur ayrışırdı.
      **Ölçüldü:** Azure "Orta" seçiliyken Gemini sütunu "2K" ile koştu, tur
      maliyeti `≈ 14 kredi · 2 model` (8 + 6) yazdı ve diskteki kayıtlar
      `credits` 8 ve 6 ile indi. Sıra varsayımının bekçisi ayrı bir test:
      katalogdaki her modelin kalite demeti ARTAN sırada olmak zorunda.
- [x] **Boyut listesi seçili modellerin KESİŞİMİ.** Kesişim dışı bir oran bazı
      sütunları sessizce kendi varsayılanına düşürürdü ve karşılaştırma farklı
      çerçevelerde yapılırdı — aynı prompt'u aynı koşulda koşturmak arenanın
      tanımı.
- [x] **İKİNCİ bir model yüzeyi açılmadı.** Arena, `#model-sheet`in ÜÇÜNCÜ
      ekseni (`MODEL_EKSENLERI`e yeni anahtar): aynı liste, aynı `secilebilirler`
      filtresi, aynı perde/Escape/Android-geri mekaniği; tek fark kartların
      radyo yerine checkbox olması. `tests/test_index.py`'nin koruduğu tekillik
      korundu, iddiası "iki çip" yerine "üç çip" olarak GÜÇLENDİRİLDİ.
- [x] **Kısmi başarısızlık gerçekten sütunda kalıyor.** **Ölçüldü:** üç modelli
      turda biri kasten düşürüldü — 3 sütun çizildi, 2'si doldu, düşenin hatası
      kendi sütununda kaldı, `#status` "2/3 model üretti. gpt-image-1: …" yazdı,
      diske yalnız 2 kayıt indi ve kazanan düğmesi yalnız dolan iki sütunda
      göründü.
- [x] **Kazananın TEK kaynağı `history.json`.** Döküm kaydına ikinci bir kopya
      yazılmadı: oturum kaydedilmeyen bir turda ikisi ayrışırdı. Depo tarafı
      tek yazımda hallediyor (kazanana `arena_win`, kardeşlerden anahtarı
      SİLİYOR) — iki ayrı yazım arada okuyan bir istemciye iki kazanan
      gösterirdi. **Ölçüldü:** işaret diske indi, fikir değiştirilince tek
      kazanan kaldı, sayfa yenilenip oturum yeniden açıldığında satır 2
      sütunuyla ve işaretiyle geri geldi.
- [x] **Adet arenada 1'e kilitli** (satır gizli): 4 model × 4 görsel hem
      ızgarayı hem faturayı okunmaz yapardı ve bir sonuç kaydının `image_ids`
      tavanı zaten bir TURUN çıktısı kadar.
- [x] **Sessiz sapma yok.** Arena açıkken referans eklenirse `#go` kilitleniyor
      ve sebebi yazıyor ("Arena düzenlemeyle çalışmıyor — referansı kaldır");
      beşinci model seçilmeye çalışılınca kutucuk geri alınıyor ve tavan
      söyleniyor. **İkisi de ölçüldü.**
- [x] **Telefon.** 360px'de satır en çok 2 sütun; ölçülen karo **143px**.
      Dört sütun bırakılsaydı karo ~73px olurdu — o karşılaştırma değil, küçük
      resim şeridi. **Ölçüldü:** 360×780'de taşma x = 0, konsol temiz.
- [x] **Kanıt:** takım **1686 → 1721 geçti / 10 atlandı** (`tests/test_arena.py`
      14 iddia: etiket, biçim kapısı, iki modelin kendi kredisi, kazananın tek
      yazımı, idempotanlık, başka turun görselinde 404; `tests/test_arena_onyuz.py`
      21 iddia: fan-out, çeviri tekliği, kesişim, tek yazar, tavan, gruplama,
      mobil ızgara). Chromium 1024×700 ve 360×780 ölçümleri yukarıda.

---

## ✅ Tur C — Medya seçici telefonda kullanılamıyordu + geçersiz ARIA

**Bitti (22 Ağustos).** Bu tur **kullanıcı şikâyetiyle** açıldı, kuyruktan
değil: telefonda (+) → "Medya'dan seç" açılınca sağ bölme ekranın tamamını
kaplıyor, ızgara bir şeride iniyor ve **üstteki görseller seçilemiyordu**.
Kuyruğun **1. maddesi** (geçersiz ARIA) aynı tura katıldı — aynı bileşene
dokunuyor, ayrı turda yapmak aynı üç dosyayı iki kez açmak olurdu.

- [x] **Sağ bölme telefonda alt şeride indi.** Kök neden ölçüldü: mobil katman
      kartı tek sütuna indiriyor (`mobile.css`, `"phead" "pnav" "pbody"
      "pside"`) ama bölmenin DÜŞTÜKTEN SONRA ne kadar yer kaplayacağı hiç
      sınırlanmamıştı — masaüstü kuralları 180px'lik bir sütun için yazılmış,
      telefonda 360px'in tamamında koşuyordu. `pbody` ise `minmax(0, 1fr)`,
      yani **tabanı sıfır**: bölmeye ne kalırsa ızgaraya o kalıyordu.
      **Ölçülen hâl 360×780'de: ızgara 21px, tam görünen karo 0, ilk karonun
      merkezine `elementFromPoint` başka bir öğe döndürüyor** — yani şikâyet
      mecazi değil, karo gerçekten tıklanamıyordu.
      Bölme artık iki sütunlu kompakt bir şerit: 72px önizleme + yanında künye,
      altında yan yana iki düğme. `.picker-side`'ın kendi `overflow-y: auto`'su
      bunu HİÇ çözmüyordu ve ayrım kuralın gövdesine yazıldı: taşan bölme
      değil, **ezilen ızgara**.
- [x] **İki emniyet kilidi.** `max-height: 40vh` + satır tanımı
      `minmax(0, 1fr) auto`: künye beklenmedik biçimde uzasa (iç içe klasör
      zinciri — kuyruktaki "iç içe klasör etiketi" maddesinin konusu) bölme
      ekranın %40'ını aşamıyor ve küçülen tek şey künye satırı oluyor — `auto` satırlar küçülmediği için
      sınıra dayanınca kırpılan ilk şey **düğmeler** olurdu.
- [x] **Alt güvenli alan payı geldi.** `.picker-card` yalnız `padding-top`
      alıyordu (`.modal-card`'ın iki kenarlı kuralı seçiciyi bilerek
      kapsamıyor, kartın kendi sınıfı var). Android'de jest çubuğu "Ek olarak
      ekle"nin üstüne biniyordu: düğme görünüyor ama basılamıyor — bu dosyanın
      açtığı kırılma sınıfının aynısı.
- [x] **İki düğme yan yana ve sarma KURALA bağlı.** `flex-basis` rem tabanlı
      (Tur B'nin `.chat-hint` dersi: Android WebView sistem yazı ölçeğini
      uyguluyor, piksel eşiği cihazdan cihaza farklı karar verir).
      **Yan yana dizince iki eski kusur görünür oldu ve ikisi de ölçüldü:**
      `.primary`nin `margin-top: 1rem`i (dikey yığın mirası) satırı 16px
      uzatıp düğmenin kendisini 16px kısaltıyordu — "Referans yap" 44px,
      "Ek olarak ekle" 60px ve ikisi alt kenarlarından hizalıydı; `.primary`
      hiç font bildirmediği için UA'nın 13.33px'ini alıyor, `.btn-ghost` ise
      `font: inherit` ile 15px'te duruyordu. İkisi de yalnız mobil blokta
      düzeltildi. `font` KISA BİÇİMİ kullanılmadı: `.primary`nin
      `font-weight: 500`ünü sıfırlar ve birincil eylem inceleşirdi.
- [x] **Kuyruk maddesi 1 — `aria-selected` → `aria-pressed`.** `.picker-tile`
      düz bir `<button>`, kapsayıcısı düz bir `<div>`; `aria-selected` yalnız
      `option`/`tab`/`row`/`treeitem`/`gridcell` rollerinde geçerli.
      **Ölçüldü:** düzeltme öncesi erişilebilirlik ağacında seçili karo için
      `pressed` özelliği YOK (ağaçtaki tek `pressed` mod anahtarınınki),
      sonrasında iki tane — yani seçim ekran okuyucuya gerçekten ulaşmıyordu.
      `role="listbox"/"option"` çifti reddedildi: gezinen tabindex + ok tuşu
      modeli ister, depoda öyle bir desen hiç yok; `aria-pressed` altı yerde
      zaten kurulu.
- [x] **İkiz kural tekilleşti.** `.picker-tile[aria-selected="true"]` **iki
      kez** tanımlıydı (biri gezinme bölümüne düşmüş); ikisi `background` ve
      `outline` için çakışıyordu, ikizden hayatta kalan tek bildirim
      `box-shadow`du. Tek kurala indirildi, boyanan sonuç birebir aynı.
- [x] **İkizin ÖTEKİ YARISI da tekilleşti** (aynı turun kapanışı, istek
      üzerine). Gezinme bölümüne düşen yapıştırma iki kuraldan oluşuyordu;
      `aria-selected` yarısı yukarıda kapandı, `.picker-tile:hover` yarısı
      kaldı. Aynı mekanizma: eşit özgüllük, kaskad sırası karo bölümündeki
      `background`ı kazandırıyor — ikizin `--accent-surface` tercihi hiç
      boyanmıyordu — ama `box-shadow`u kimse ezmediği için o BOYANIYORDU.
      **Buradaki asıl risk temizliğin kendisiydi:** ikizi yalnızca silmek,
      üzerine gelince beliren accent kenarını da sessizce götürürdü. Chromium
      ölçümü önce/sonra birebir aynı: üzerine gelinen karo
      `rgb(39,39,40)` + `inset 0 0 0 1px rgba(255,255,255,.2)`, seçili+üzerine
      gelinen karo `rgb(53,54,55)` + `outline 2px` (yani seçim hover'a
      yenilmiyor — sıra bilinçli ve mandallı).

**Kanıt.** Takım **1632 → 1637 geçti / 10 atlandı**. *(Yukarıdaki "defterin
açılış ölçümü" satırı 1631 diyordu; Tur C'nin ölçtüğü taban 1632 — defterin
sayısı bir gerideymiş, kayıt düzeltiliyor.)* Dört yeni mandal ve
**hepsi mutasyonla doğrulandı — on beş mutasyon, on beşi de kırmızı**:
kare önizlemenin sabit boyu, `max-height`, satır tanımı, kuralın medya
sorgusunun dışına kaçması, alt güvenli alan, rem tabanı, `width: auto`,
`min-height: var(--tap)`, `margin-top: 0`, JS'in özniteliği, CSS'in seçicisi,
hover kenarının düşmesi, ikizin geri konması ve iki kuralın sırasının
ters çevrilmesi.

**Tarayıcı ölçümü** (Chromium 1194, dokunmatik bağlam, seçicide 36 karo):

| Ölçü | 360×780 önce | 360×780 sonra | 360×640 sonra | 800×700 | 1024×700 |
|---|---|---|---|---|---|
| ızgara (`.picker-body`) | **21px** | **506px** | 366px | 502px | 502px |
| bölme (`.picker-side`) | 656px | **171px** | 171px | 502px×180 | 502px×180 |
| önizleme | 327px kare | 72px | 72px | 147px | 147px |
| tam görünen karo | **0** | **6** | 6 | 9 | 6 |
| ilk karo tıklanabilir | **hayır** | evet | evet | evet | evet |
| ikinci karo dokununca seçildi | **hayır** | evet | evet | — | — |
| iki düğme aynı satırda | — | evet | evet | hayır (yığın) | hayır (yığın) |
| yatay taşma | 0 | 0 | 0 | 0 | 0 |
| konsol | temiz | temiz | temiz | temiz | temiz |

Masaüstü **hiç değişmedi**: kart 776×570, yan bölme 180px, üç sütun — bütün
kurallar `@media (max-width: 768px)`in içinde ve bir mutasyon tam olarak bunu
mandallıyor (kuralı sorgunun dışına taşımak testi kırmızıya düşürüyor).

> **Ölçülen tuzak (mandalın kendisinde).** İlk yazımda mobil iddialar CSS
> gövdesini **yorumlarıyla birlikte** okuyordu ve bu dosyanın kuralları
> gerekçesini kendi gövdesinde yazıyor: `max-height` bildirimini silen mutasyon,
> "`max-height` devreye girdiği anda…" diyen YORUM sayesinde **hayatta kaldı**.
> İkinci tuzak aynı turda: `minmax(0, 1fr)` gövdede aranınca
> `grid-template-columns`taki aynı değere takılıyordu, yani satır tanımını
> `auto auto`ya çeviren mutasyon da geçiyordu. Yardımcı artık yorumları
> ayıklıyor (brace sayımından ÖNCE) ve iddia `grid-template-rows`un DEĞERİNE
> bakıyor. §0.6/§0.7/§0.9'un "iddia kodu arar, kelimeyi değil" dersinin
> beşinci ve altıncı kurbanı.

> **Plandan sapma (gerekçeli).** Plan beşinci madde olarak bir Playwright
> ölçüm testi öngörüyordu. Yazılmadı: `playwright` paketi CI'da kurulu değil
> (`test_playwright_studio.py` zaten `importorskip` ile atlanıyor) ve bu
> kaptaki tarayıcı sürümü paketinkiyle uyuşmuyor — eklenen test hiçbir yerde
> koşmaz, yalnız ikinci bir atlanan dosya olurdu. Tarayıcı ölçümü Tur A ve
> B'nin yaptığı yerde duruyor: yukarıdaki tabloda.

---

## ✅ Tur B — Tasarım ölçütünün ihlalleri + composer alt satırı

**Bitti (22 Ağustos).** Kuyruğun **1. maddesi** sıradaki işti. **6. madde**
kuyruktan alınıp aynı tura katıldı ve gerekçesi teknik: 1'in üçüncü bulgusu
(`⚙` → "Ayarlar düğmesi") `#status`'a yazılan metni ~15 karakter **uzatıyor**,
bugünkü `.chat-hint { flex: 1 }` kuralında ise uzayan `#status` ipucunu daha da
eziyordu. Yani 6 olmadan 1 sıkışmayı **kötüleştiriyordu**; ikisi ayrı turda
yapılamazdı. Üstelik `.folder-target` zaten `.composer-foot`'un içinde yaşıyor,
yani iki madde aynı satırı paylaşıyor.

- [x] **`#settings-update`'teki `🎉` düştü.** Yerine sade metin: satır artık
      `Yeni sürüm çıktı:` diyor. İşaret gerekmiyor çünkü satır varsayılan olarak
      `hidden` ve yalnız gerçekten yeni sürüm varken açılıyor — **varlığı**
      işaretin kendisi. Metin `GUNCELLEME.md` ve README'nin bu satırı anlattığı
      sözlerle birebir aynı; emoji o belgelerde hiç yoktu. Hatlı SVG glif yolu
      **reddedildi** (Tur A'nın ölçtüğü sessiz kusur — geçersiz XML →
      `naturalWidth = 0`, konsolda tek hata yok — bu yola da bulaşırdı).
      JS bağlantısı yok: JS yalnız sürüm ve adresi yazıyor, satırın metnine hiç
      dokunmuyor.
- [x] **`.folder-target`'ın vurgu renkli sol kenarı nötrleşti.** Token zinciri
      kardeş `.chat-gate`'ten **birebir** alındı
      (`var(--border-strong, var(--control-border))`) — hedef hâl elde vardı.
      Gerekçe kuralın gövdesinde yazılı: `--accent` bu kod tabanında yalnız
      DURUM anlatıyor (`flow-tokens.css`), `.folder-target` ise durum değil,
      "bulunduğun klasöre eklenecek" diye statik bir ipucu (tetikleyici
      sürükleme DEĞİL, klasörün İÇİNDE olmak).
- [x] **ÜÇÜNCÜ BULGU — 21 Ağustos denetimi bunu saymamıştı.** `settings.js`
      durum metnini üç yerde `(sağ üstteki ⚙)` diye yazıyordu; üst şeritteki
      gerçek düğme ise hatlı bir SVG dişli (`aria-label="Ayarlar"`), yani glif
      düğmenin görünüşünü **yanlış** söylüyordu. Metin artık düğmenin adını
      veriyor. **Ölçülen ikinci kusur:** dize üç kez elle yazılıydı ve biri
      **nöbetçi** (`includes(…)` — durum satırını temizleyen kapı). Biri
      değişip öteki kalsa hata VERMEZ, satır ekranda asılı kalırdı. Tek sabit:
      `AYARLAR_EKI`.
- [x] **Composer alt satırında ipucu tek satırda** (kuyruk maddesi 6).
      **Ölçülen mekanizma:** `.chat-hint { flex: 1 }` kısa biçimi
      `flex: 1 1 0%`e çözülüyor, yani taban genişliği **SIFIR**. Satırdaki tek
      esnek öğe buydu — `#status` bir `<p>` (`flex: 0 1 auto`, tabanı içerik
      genişliği), `.run-cost` ise `flex: none`. Taban artık içerikten geliyor ve
      `nowrap` sarmayı kapatıyor; satır zaten `flex-wrap: wrap`, yani sığmayan
      kardeş alta düşüyor. **`#status`'a kural EKLENMEDİ ve bu bilinçli:**
      `flex-basis: 100%` gibi bir kural durumu her zaman kendi satırına atardı
      ve ipucu telefonda zaten gizli, yani 360px'de bedava bir satır yüksekliği
      demekti. Kısa durum metni ipucuyla aynı satırda kalmaya devam ediyor.

**Kanıt.** Takım **1625 → 1631 geçti / 10 atlandı** (atlananlar yine yalnız
Windows'a özgü DACL testleri + kurulu olmayan Playwright);
`test_id_contract.py` 12 geçti. Altı yeni mandal ve **hepsi mutasyonla
doğrulandı** (sekiz mutasyon, sekizi de kırmızı): `test_index.py`'de
emoji taraması, güncelleme cümlesi, tek sabit, sol kenar ve `.chat-hint`;
`test_mobile.py`'de ipucunun telefonda hâlâ gizli olduğu.

*Emoji mandalı ölçütü mandallıyor, tek düzeltmeyi değil:* iki kademeli
(kademe 1 astral düzlem + VS16 → HTML·JS·CSS; kademe 2 Misc Symbols + Dingbats
→ HTML·JS) ve taradığı dosyaları **HTML'den keşfediyor**, yani sayfaya eklenen
yeni bir `.js`/`.css` mandalın dışında kalamıyor. **CSS kademe 2'den muaf** ve
gerekçesi testte yazılı: `content: "✓ "` tek renkli, metin sunumlu bir dingbat —
yani bu defterin `🎉` yerine **önerdiği** "hatlı glif" biçiminin kendisi.
Sol kenar mandalı da aynı biçimde genel: tek kurala değil `style.css` ve
`mobile.css`'teki **her `border-left` bildirimine** bakıyor.

**Tarayıcı ölçümü** (Chromium; `1024×700` = en küçük pencere, `800×700` =
768px kırılımı ile onun arası, `360×780` = telefon). `#status`'a
`goBlockReason`'ın en uzun çıktısı + yeni `AYARLAR_EKI` yazılıyken:

| Ölçü | 1024×700 | 800×700 | 360×780 |
|---|---|---|---|
| `.chat-hint` | **18px · 1 satır** (`flex-basis: auto`, `nowrap`) | 18px · 1 satır | `display: none` |
| ÖNCE (aynı düzenek, `flex: 1`) | **53px · 3 satır** (`flex-basis: 0%`) | — | — |
| yatay taşma | 0 | 0 | 0 |
| konsol | temiz | temiz | temiz |

`#folder-target`'ın sol kenarı **dört temada da** `rgba(255,255,255,0.18)`:
`.chat-gate` ile eşit, `--accent`'in hesaplanmış değerine eşit değil.
Güncelleme satırında astral kod noktası yok.

> **Ölçülen tuzak (ölçümün kendisinde).** İlk tema turunda `--accent`
> `documentElement`'ten okundu ve dört temada da `#e8eaed` çıktı — "tema
> değişmiyor" gibi görünen bu sonuç bir **ölçüm hatasıydı**: temalar `body`'ye
> yazılıyor (`[data-theme=…]` seçicisi), yani override `html`'de görünmüyor.
> `body`'den okununca dört tema gerçekten ayrıştı. Kayıt burada duruyor çünkü
> yanlış ölçüm "kanıt" diye yazılsa kutu kanıtsız işaretlenmiş olurdu.
>
> **İkinci tuzak (araç).** Mutasyon turunda `git checkout -- <dosya>` ile geri
> alma, henüz **commit edilmemiş** düzeltmeyi de siliyor: bir mandal o yüzden
> "hayatta kaldı" gibi göründü, oysa mutasyonun hedef dizesi dosyada artık yoktu
> ve `replace` sessizce hiçbir şey yapmadı. Geri alma scratchpad kopyalarına
> çevrildi ve mutasyon betiği artık hedefi bulamazsa **patlıyor**
> (`assert s.count(a) == 1`).

---

## ✅ Tur A — Model şeritlerinde sağlayıcı işareti + koşullu Yönetmen bölümü

**Bitti (22 Ağustos).** İki iş de kullanıcı isteğiydi; kararlar sorulup
onaylandı.

- [x] **Model şeritlerinde sağlayıcı logosu.** Seçili modelin sağlayıcısı çipin
      içinde, solda bir işaretle gösteriliyor; model değişince işaret değişiyor.
      Native `<select>` **korundu** (Android'de sistem seçicisi + ARIA gerekçesi
      `index.html`'de yazılı): native `<option>` görsel taşıyamadığı için açılan
      listede işaret yok, gösterilebilen tek şey seçili model.
      **Eşleme katalogda** (`catalog.PROVIDER_LOGOS` + `provider_logo`), adres
      sunucuda kuruluyor (`app._provider_logo_url`, `?v=` damgası `index()`in
      deseni) ve istemci yalnız `logo` alanını okuyor — sağlayıcı adı istemcide
      hiç sayılmıyor.
      **Kanıt:** `tests/test_provider_logos.py` (8 iddia; biri "adaptörü olan
      her sağlayıcının işareti var", yani logosuz yeni adaptör suite'i kırar),
      `test_index.py`'de beş işaretleme/JS mandalı, `test_mobile.py`'de iki
      sarmalayıcı mandalı. Chromium (1024×700 **ve** 360×780): işaret 14×14 ve
      çipin İÇİNDE, model değişince `src` değişiyor, mod anahtarı gizli şeridin
      **kabuğunu** da gizliyor, taşma x/y = 0, konsol temiz.
      **Ölçülen tuzak:** ilk yazımda dosyaların yorumunda çift tire (`--fg`)
      vardı; XML'de yasak olduğu için tarayıcı 200 alıp **hiçbir şey çizmedi**
      (`naturalWidth = 0`, boyanan piksellerin hepsi panel arka planı). Konsolda
      tek hata yoktu. Mandalı `test_isaretler_GECERLI_XML_ve_ICSEL_boyutlu`.
- [x] **Ayarlar'da koşullu "Prompt Yönetmeni (sohbet modeli)" bölümü.**
      Sağlayıcı dağıtım adı istemiyorsa (OpenAI · Gemini) **başlık da** gidiyor;
      "bu sağlayıcıda dağıtım adı yok" paragrafı tümden kaldırıldı (gizli bir
      başlığın altında hiç görünemezdi). Kapı yine **katalogdan** türetiliyor
      (`chat_models[].needs_deployment`) ve **fail-open** kalıyor.
      Talimat dosyası yolu **koşulsuz** duruyor, kendi başlığıyla
      ("Prompt Yönetmeni · talimat") — keşfedilebilirlik gerekçesi
      `index.html`'de yazılı.
      **Kanıt:** `test_index.py`'de üç iddia yeniden yazıldı + biri yeni
      (talimat yolunun koşullu grubun DIŞINDA olduğu). Chromium: Azure'da
      başlık + kutu var, OpenAI ve Gemini'de ikisi de `display: none`, talimat
      satırı üç sağlayıcıda da görünür.
- [x] **Şerit satırlarında marka öneki kalktı** (kullanıcı geri bildirimi, aynı
      tur). İşaret markayı söylediği için `Gemini · Nano Banana 2` satırı aynı
      bilgiyi iki kez yazıyordu; satır artık `Nano Banana 2` diyor. Kısaltma
      **sunucuda** (`catalog.short_labels` → `/api/settings`'in yeni
      `short_label` alanı): istemci ne marka adı sayıyor ne dize kırpıyor.
      `label` **değişmedi** — hata metinleri, `#model-note` ve durum satırı tam
      adı okumaya devam ediyor.
      **Çakışma kuralı** (ölçülmüş): katalogda `gpt-image-2` adını taşıyan İKİ
      model var (Azure · OpenAI). Önek ikisinden de düşerse açılan listede aynı
      iki satır oluşur ve native `<option>` işaret taşımadığı için logo onları
      ayırmaz — o yüzden kısa adı çakışan model tam etiketini koruyor.
      **Kanıt:** takım 1613 → **1622 geçti / 10 atlandı** (`test_catalog.py`'de
      altı iddia — kural, çakışma, `Azure AI Foundry dağıtımı`nın kırpılmaması,
      liste içinde tekillik; `test_settings_route.py`'de donmuş alan kümesi +
      yeni gövde iddiası; `test_index.py`'de "istemci kırpmıyor" mandalı).
      Chromium 1024×700 ve 360×780: satırlar `Nano Banana 2` / `GPT-5.6 Terra` /
      `3.7 Flash`, iki `gpt-image-2` önekli, işaret 14×14 ve `naturalWidth > 0`,
      taşma x/y = 0, konsol temiz.

---

## Bekleyen kuyruk

Sıra öneri; her madde **neden · dokunulacak yer · kabul ölçütü · büyüklük**
taşıyor. Büyüklükler: **S** tek oturum, **M** bir tur, **L** kendi planını
isteyen iş, **XL** kendi tasarım belgesi olan faz.

**NUMARALAR KAYAR.** Bir madde kapandığında kalanlar yeniden numaralanıyor, yani
yukarıdaki tur kayıtlarındaki "kuyruğun N. maddesi" atıfları O GÜNKÜ kuyruğu
gösteriyor, bugünküyle eşleşmek zorunda değil. Maddenin kimliği numarası değil
BAŞLIĞI; kapanan madde de silinmiyor, ait olduğu turun kutusunda kanıtıyla
duruyor.

> **SIRADAKİ TUR: 1. madde** — logo önizlemesi kare olmayan görselde eksik
> görünüyor. Kuyruğun başında DURUYOR: Tur K onun yerine geçmedi, kullanıcı o
> oturumda başka bir iş verdi (defterin kuralı: "kuyruk sırası bir söz değil,
> öneri"). Madde ayrıca **daraldı** — Tur K oturumunda iki adaydan biri ölçümle
> ELENDİ, aşağıda. 2. madde (arama/klasör zinciri) hemen ardından geliyor.
>
> 3. madde (güncelleme kontrolü) bir DAĞITIM kararına bağlı ve karar alındı:
> depo **şimdilik private, ileride public** — madde silinmiyor, "public'e
> dönene kadar kullanıcı kırık bir güncelleme kontrolü taşıyor mu" sorusu
> ölçülmeyi bekliyor.

### 1. Logo bindirmede kare OLMAYAN görselde önizleme eksik görünüyor · **S**
**Kullanıcı bildirdi (28 Ağustos):** "Logo ekleme kısmında görsel kare değilse
görselin aşağı veya yan kısımlarındaki logo ekleme önizlemesi gözükmüyor."
Yani 9'lu ızgarada alt/yan bir konum seçildiğinde logo önizlemede görünmüyor.

**YARISI ÖLÇÜLDÜ (1 Eylül, Tur K oturumu).** Bu defterin kuralı gereği
düzeltme, hangi katmanın suçlu olduğu ölçülmeden yazılmaz. Kod okunarak iki
aday çıkarılmıştı; **(b) elendi**, (a) ayakta:

* **(a) İstemci — görüntüleme kırpması.** `.logo-preview-wrap` (style.css)
  `overflow: hidden` + `place-items: center` taşıyor; `.logo-preview-img` ise
  `max-width: 100%` ve `max-height: min(72vh, 680px)` ile sınırlı. Görsel kabı
  aşarsa merkezleme taşmayı İKİ UÇTAN birden yapar ve `overflow: hidden` orayı
  keser — tam da "aşağı ve yan kısımlar" tarifi.
* **(b) Sunucu — yerleşim aritmetiği.** `composite.paste_position` /
  `composite_logo`: `margin_px = int(base.width * margin)` kenar boşluğunu
  YALNIZ genişlikten hesaplıyor ve aynı değeri dikeyde de kullanıyor (satırda
  bilinçli olduğunu söyleyen bir yorum var). Kare olmayan oranda dikey boşluk
  orantısız çıkıyor.

**(b) ELENDİ — ölçüldü.** `paste_position`ın tamsayı matematiği beş oranda ve
dokuz konumun **dokuzunda da** logoyu kadrajın TAMAMEN içine koyuyor
(`_clamp_px` negatif koordinatı zaten kesiyor):

| taban | logo | dokuz konumun hepsi kadrajın içinde mi |
| --- | --- | --- |
| 1024×1024 | 143×35 | evet |
| 1536×1024 | 215×53 | evet |
| 1024×1536 | 143×35 | evet |
| 2048×512 | 286×71 | evet |
| 512×2048 | 71×17 | evet |

Yani kaydedilen PNG'de logo HER ZAMAN var; sunucu bir şeyi "gözükmez" yapamaz.
Önizleme ile uygulama aynı `_composite_logo` yolundan geçtiği için (app.py) bu
sonuç önizleme için de geçerli — **kusur, sunucudan gelen doğru görselin
İSTEMCİDE nasıl çizildiğinde.**

**Kalan aday ve önde giden açıklama.** Kullanıcı kusuru **telefonda** gördü,
yani `mobile.css`in o kutuya özel kuralları devrede:
`.logo-preview-wrap { height: 38vh }` + `.logo-preview-img { max-height: 100% }`
(mobile.css:277-285), sarmalayıcıda `overflow: hidden` + `place-items: center`.
YÜZDE `max-height`, satırı `auto` boyutlanan bir ızgara öğesinde çözülmezse
`none` gibi davranır; o zaman resmi sınırlayan tek kural `max-width: 100%`
kalır ve dikey bir görsel (ör. 1024×1536) 328px genişlikte 492px yüksekliğe
çıkıp 304px'lik kutuda **ortalanır** — taşma alttan ve üstten birden kesilir.
Yatay görselde `max-width` önce bağladığı için kusur görünmez; "görsel kare
değilse" koşulu tam olarak buradan geliyor.

**SIRADAKİ ÖLÇÜM (tek adım):** 360×800'lük bir Chromium'da modalı dikey bir
görselle açıp `#logo-preview-img`in çizilen kutusunu `.logo-preview-wrap`inkiyle
karşılaştırmak — ve `getComputedStyle(img).maxHeight` okumak, çünkü yüzdenin
çözülüp çözülmediğini doğrudan o söylüyor. Aynı ölçüm 1280×800'de bir daha:
kusurun `mobile.css`e özgü olduğunu kanıtlar. (Tur K'da kurulan
`tests/test_playwright_studio.py` altyapısı bu ölçümü hazır veriyor.)
- [ ] **Kabul:** kare olmayan bir görselde dokuz konumun DOKUZU da önizlemede
      görünüyor ve önizleme uygulanan çıktıyla birebir aynı şeyi gösteriyor.
      Bekçisi iki katman: `tests/test_mobile.py`de CSS kuralının mandalı (CI'da
      Playwright her işte yok) + bir E2E ölçümü.

### 2. Arama, klasör adını yalnız EN YAKIN klasörde eşleştiriyor · **S**
Tur G'nin künye işinin arama tarafı; aynı turda kod okunurken çıktı.
`matchesSearch` (folders.js) yalnız `folder.name`e bakıyor, zincire değil.
Kullanıcı "Kampanyalar" yazınca o klasörün ALTINDAKİ görseller çıkmıyor — oysa
künye artık "Kampanyalar / Bayram" yazdığı için kullanıcı tam da o adı ekranda
okuyup aratıyor. Tur G'de YAPILMADI: eşleştirmeyi değiştirmek sonuç kümesini
değiştirir ve kendi ölçümünü ister (kaç sonuç, hangi kapsamda, kapsam sayaçları).
- [ ] **Kabul:** iç içe klasörde üst klasörün adı aratıldığında alt klasördeki
      görseller de geliyor; kapsam sayaçları buna göre.

### 3. Uygulama içi güncelleme kontrolü deponun PUBLIC olduğunu varsayıyor · **S**
Tur I'de kapının gerekçesi düzeltilirken çıktı: `guncelleme.py`'nin başlığı
"Depo public olduğu için uç nokta anonim çalışıyor — pakete gömülmüş bir token
YOK ve olmamalı" diyor ve modül `api.github.com/repos/…/releases/latest`i
kimliksiz çağırıyor. Depo bugün **private** (REST, 28 Ağustos). Private bir
deponun bu ucu anonim çağrıda 404 döner; o hâlde Ayarlar'daki *"Yeni sürüm
çıktı"* satırı hiçbir kullanıcıda görünmüyor demektir — sessizce, çünkü kontrol
zaten arka planda koşuyor ve hatası kullanıcıya çıkmıyor.

**ÖLÇÜLEMEDİ ve sebebi kayda değer:** bu oturumun ağı bir vekil üzerinden
geçiyor ve GitHub isteklerine kimlik ekliyor (`X-Ratelimit-Limit: 5000`, anonim
sınır 60 olurdu), yani buradan atılan çağrının 200 dönmesi kullanıcının
makinesindeki davranışı KANITLAMIYOR. Kanıt, kimlik taşımayan bir ağdan tek bir
`curl` ile alınır.

Aynı varsayım daha geniş bir soruyu da açıyor: yayın sayfası da private ise
kullanıcı paketi zaten indiremez (`GUNCELLEME.md` "son yayın sayfasından
indirebilirsin" diyor). Yani bu madde teknik bir düzeltme kadar bir **dağıtım
kararı**: depo public'e mi dönecek, yoksa güncelleme/indirme başka bir yüzeye mi
taşınacak.

**KARAR ALINDI (28 Ağustos, kullanıcı):** depo **şimdilik private, ileride
public** yapılacak. Bu maddeyi kapatmıyor, ikiye bölüyor: (a) public'e dönüldüğü
gün `guncelleme.py`'nin gerekçesi kendiliğinden doğru olur ve yapılacak tek şey
ölçümle onaylamaktır; (b) o güne kadar geçen sürede kullanıcı SESSİZCE kırık bir
güncelleme kontrolü taşıyor — kontrol arka planda koşuyor ve hatası kullanıcıya
çıkmıyor. Yani (b) bir dağıtım kararını beklemiyor, bugün de düzeltilebilir:
kontrol "bakılamadı" durumunu Ayarlar'da görünür kılsın yeter.
- [ ] **Kabul:** önce ölçüm (kimliksiz ağdan `curl`). Kırıksa: kontrol
      kullanıcıya görünür bir "bakılamadı" durumu döndürür ve depo public'e
      döndüğünde aynı ölçüm 200'e dönerek gerekçeyi doğrular — pakete token
      GÖMÜLMEZ (o kural durur).

### 4. Wheel'in elle bakım yolu hâlâ varlık kotasına bağlı · **S**
Tur H'nin bıraktığı uç. Yayın yolunda tek bir `upload-artifact` kalmadı ama
`build-pydantic-core-android.yml`deki teslim adımı duruyor (`varlik_yukle`
bayrağı — Yol A: bakımcı workflow'u elle tetikleyip wheel'i indiriyor ve
`android/wheels/` altına işliyor). **Ölçüldü:** 28 Ağustos 19:58 ve 20:10'daki
iki kanarya koşusu `Artifact storage quota has been hit` ile düştü, yani o yol
kota doluyken KIRIK. Yayın etkilenmiyor; lazım olacağı an pydantic çivisinin
güncellendiği gün.
- [ ] **Kabul:** ya teslim de önbellekten okunuyor (çağıran zaten öyle yapıyor)
      ya da wheel bir taslak yayına yükleniyor; her iki hâlde de kota doluyken
      Yol A yürüyor.

### 5. Sonuç kartında "Düzenle" / "+ Ek" (K14) · **M**
Karar "tam bir geçmiş kaydı ister" diye ertelenmişti; döküm bugün yalnız
`image_id` taşıyor. Kart eylemleri için kaydın kendisi lazım.
- [ ] **Kabul:** sonuç kartından doğrudan düzenlemeye/ek referansa geçilebiliyor
      ve silinmiş görselde yer tutucu davranışı bozulmuyor.

### 6. Ayarlar'da canlı bağlantı testi düğmeleri · **M**
README Faz 2'nin son açık maddesi. Bugünkü karşılık yalnız "anahtar kayıtlı mı"
listesi; gerçek bir çağrı denemesi yok.
- [ ] Sağlayıcı başına küçük bir uç (`POST /api/settings/test`?) + düğme;
      hata metinleri `providers._ICERIK_REDDI` çevirisinden geçmeli.
- **Kabul:** yanlış anahtarda anlaşılır Türkçe hata, doğru anahtarda "bağlantı
      kuruldu"; anahtar yanıtta HİÇ yankılanmıyor (write-only sözleşmesi).

### 7. Yerel sağlayıcı adaptörleri: ComfyUI · Ollama · **L**
Anahtar/adres alanları v0.2.0'dan beri kayıtlı, **adaptör ve arayüz yok**
(`azure_client.get_settings_status` yalnız durum bayrağı döndürüyor).
- [ ] `providers._ADAPTERS`'a iki adaptör, katalogda modeller, Ayarlar'da
      gruplar, `catalog.PROVIDER_LOGOS`'a iki işaret (mandal onu zorluyor).
- **Kabul:** yerel bir kurulumla üretim yapılabiliyor; sağlayıcı düşükken hata
      Türkçe ve anlaşılır.

### 8. fal.ai · Replicate adaptörleri · **L**
Aynı boşluğun bulut yarısı; ikisi de **kuyruklu** akış (`providers`'ın zaman
aşımı politikası bunu zaten öngörüyor: "adet başına ayrı istek atan sağlayıcı").
- [ ] **Kabul:** kuyruk beklerken arayüz ilerleme gösteriyor, zaman aşımı
      sağlayıcıya göre çözülüyor (`tests/test_providers.py`'nin deseni).

### 9. Maske tuvali / bölgesel düzenleme · **L**
Master spec Faz 1'in açık yarısı: bugünkü `/api/edit` tüm görsel üzerinden
çalışıyor, `mask` alanı yok.
- [ ] Fırça/silgi HTML5 Canvas + `mask` alanının adaptör sözleşmesine girmesi
      (Azure ve OpenAI destekliyor; Gemini'de karşılığı farklı).
- **Kabul:** maskelenen bölge dışında piksel değişmiyor (golden fixture).

### 10. Stil çipleri · stil şablonları · tipografi katmanı · **M**
Faz 2'nin açık yarısı. Hazır stil çipleri (*Anime*, *Cyberpunk*, *Cinematic*,
*Pixel Art*, *3D Render*) prompt'a eklenen jetonlar; tipografi katmanı
bindirmenin metin tarafı.
- [ ] **Kabul:** çip seçimi prompt'a görünür biçimde giriyor ve geri alınabiliyor.

### 11. Özel araçlar: Upscaler · Product-in-Hand · **L**
README Faz 3. Upscaler bir sağlayıcı yeteneği; Product-in-Hand bir prompt
şablonu + referans akışı.
- [ ] **Kabul:** her ikisi kendi kredi etiketiyle katalogda.

### 12. Image-to-Video motoru · **L**
README Faz 4 (master spec Faz 3'ün video payı). Yeni bir medya TÜRÜ: depo,
küçük resim, büyüteç ve indirme yolları video tanımıyor.
- [ ] **Kabul:** üretilen video kayıtta, galeride oynatılabiliyor, indirilebiliyor.

### 13. i18n (TR/EN) · **M**
Arayüz metinleri bugün HTML/JS içinde birebir Türkçe; sözlük katmanı yok.
- [ ] **Kabul:** dil anahtarı `prefs.json`'a yazılıyor, iki dilde de 360px'de
      taşma yok (İngilizce metinler daha uzun).

### 14. SaaS dönüşümü · **XL**
Kendi tasarım belgesi var: `docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md`
(Faz 5). Kredi tarifesi katalogda **metadata olarak** hazır; ledger, hesaplar,
depolama, ödeme ve filigran açık.
- [ ] **Kabul:** o belgenin kendi kabul ölçütleri; buraya alınmadan önce ayrı
      bir uygulama planı yazılır.

### 15. PWA · iOS · **L**
Android teslim (Chaquopy APK); PWA'nın service worker/manifest'i ve iOS yok.
- [ ] **Kabul:** çevrimdışı açılış ve "ana ekrana ekle" akışı çalışıyor.

### 16. Üyelik/plan görünürlüğü — kanca kondu, KARAR bekliyor · **L**
Tur K'da sunucuya tek alanlık tohum eklendi: `catalog.*Model.plan` (bugün her
modelde `"free"`), `app._model_available(configured, plan)` ve
`/api/settings`in `available` + `requires_plan` alanları. Arayüz görünürlük
kararını YALNIZ `available`dan okuyor, yani plan kapısı açıldığında istemcide
değişecek satır **sıfır**.

Eksik olan, kancanın ikinci ucu: **kullanıcı kimdir ve planı nedir**. Bugün
uygulamanın kullanıcı modeli, kimlik doğrulaması ve bakiyesi YOK — üçü de SaaS
dönüşümüne bağlı (yukarıdaki 14. madde ve kendi tasarım belgesi). `plan`
parametresi `_model_available`ın imzasında duruyor ama OKUNMUYOR; uydurma bir
eşleştirme yazmak, olmayan bir gerçeği kodlamak olurdu.
- [ ] Modellere gerçek plan etiketleri (`free` / `pro` / …) ve `plan_allows`.
- [ ] Arayüzde "Pro" rozeti — veri zaten akıyor (`requires_plan`).
- **Kabul:** planı kapsamayan model listede görünmüyor VE sebebi "anahtar yok"
      ile KARIŞMIYOR (iki ayrı cümle; `configured` bu yüzden ölmedi).

### 17. Logo kenar boşluğu iki eksende de GENİŞLİKTEN hesaplanıyor · **S**
1. maddenin ölçümü sırasında çıktı (1 Eylül) ve ondan AYRI bir olgu — kusur
değil, orantısızlık: `composite_logo`da `margin_px = int(base.width * margin)`
ve aynı piksel değeri dikeyde de kullanılıyor.

| taban | yatay boşluk | dikey boşluk |
| --- | --- | --- |
| 1024×1024 | %2.9 | %2.9 |
| 1536×1024 | %3.0 | %4.5 |
| 2048×512 | %3.0 | **%11.9** |
| 512×2048 | %2.9 | **%0.7** |

Satırdaki yorum bunun bilinçli olduğunu söylüyor (dış script'ten öyle geldi ve
golden fixture'lar ona bağlı) — yani düzeltmek fixture'ları YENİDEN ÜRETMEK
demek. Kullanıcıdan gelmiş bir şikâyet YOK; madde ölçüldüğü için duruyor.
- [ ] **Kabul:** karar önce (orantılı boşluk mu, bugünkü davranış mı); düzeltme
      seçilirse golden'lar `tools/make_logo_goldens.py` ile yeniden üretiliyor
      ve `tests/test_composite.py` kare olmayan bir oranı da sınıyor.

---

## Bilinçli olarak YAPILMAYANLAR

macOS paketleme planından devralınan liste, hâlâ geçerli: Apple
**notarization**, **universal2/Intel** paketi, **DMG** kurulumcusu. Ücretli
sertifika ve ölçülmemiş bir dağıtım yüzeyi istiyorlar; "Yine de Aç" akışı
`KURULUM.md` ve `GUNCELLEME.md`'de yazılı ve çalışıyor.
