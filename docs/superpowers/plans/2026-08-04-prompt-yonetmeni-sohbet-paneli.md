# Prompt Yönetmeni — Azure sohbet modelini gpt-image-studio'ya gömme (v1.13.0)

## Context

Kullanıcı Azure AI Foundry'de bir sohbet modeli (`gpt-5.6-luna`) yayınladı ve bu model için
Türkçe bir sistem talimatı yazdı: kullanıcı Türkçe anlatıyor, model İngilizce bir `gpt-image-2`
prompt'u + teknik ayar JSON'u + varyasyonlar üretiyor. Bugün bu akış kopyala-yapıştır ile
uygulamanın DIŞINDA çalışıyor: prompt'u başka bir yerde üretip `#prompt` alanına elle taşımak
gerekiyor.

Hedef: sohbeti uygulamanın içine almak ve modelin ürettiği prompt + ayarları **tek tıkla**
üretim formuna yazmak. Böylece "fikir → prompt → görsel" tek pencerede kapanıyor.

Kararlaştırılan üç nokta:
1. **Yanıt tek seferde gelir** (streaming yok) — depoda hiç SSE/streaming kodu yok ve
   yönetmenin çıktısı zaten ancak tamamlanınca (PROMPT + JSON blokları) işe yarıyor.
2. **Üst barda sekmeler**: "Görsel" ve "Prompt Yönetmeni". Sohbet kendi sayfası.
3. **Talimat dosyası kısıtlanır ve düzeltilir** — uygulamanın destekleyemediği ayarları
   önermeyecek, ayrıca araştırmayla çıkan gerçek hatalar giderilecek (aşağıda).

---

## Araştırma bulgusu: talimat dosyasındaki düzeltilecek noktalar

Kaynak: [OpenAI Cookbook — GPT Image Generation Models Prompting Guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
(gpt-image-2'yi adıyla ele alan, konuya birebir uyan kaynak).

> Not: kullanıcının bulduğu [gpt-4-v-prompt-engineering](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/gpt-4-v-prompt-engineering)
> sayfası görsel **üretimi** değil, görseli **girdi olarak alan** vision modellerini anlatıyor.
> Oradan yalnızca sistem-talimatı yazımına dair genel ilkeler taşınabilir (bağlamsal özgüllük,
> göreve yönelik prompt, çıktı formatını açıkça tanımlama, örnek verme, karmaşık isteği
> parçalama) — görsel prompt'unun içeriğine dair teknik detay için doğru kaynak Cookbook.

**Olgusal hatalar (mutlaka düzeltilmeli):**

| Dosyadaki ifade | Gerçek |
|---|---|
| `input_fidelity` — "Referans görselle çalışırken öner" | gpt-image-2'de **yok** (yalnızca gpt-image-1 / 1.5). Öneri satırı kaldırılmalı. |
| `background: auto \| transparent` — "Şeffaf zemin için png zorunlu" | gpt-image-2 şeffaf zemin **üretmiyor**; zemin sonradan kaldırılmalı. |
| `3840x2160` baskı için önerilir | Güvenilirlik sınırı **2560×1440 (2K)**; üstü deneysel. Kayıt düşülmeli. |
| Lens/teknik katmanı (`85mm, f/1.8`) belirgin bir katman olarak | Ayrıntılı kamera değerleri "gevşek yorumlanıyor"; üst düzey görünüm tarifi tercih edilmeli. |
| "Pozitif dille yaz" (mutlak kural) | Cookbook dışlamaları **açıkça yazmayı** öneriyor: `no watermark`, `no extra text`, `no logos`. Kural yumuşatılmalı. |
| "60–150 kelime, tek blok akıcı proza" (mutlak kural) | Karmaşık brief'lerde **kısa etiketli bölümler / satır sonları** tek uzun paragraftan iyi. Proza varsayılan kalsın, karmaşık işte etiketli yapı serbest. |

**Eklenecek teknikler:**
- Katman sırası **sahne/arka plan → konu → ayrıntı → kısıt**, artı **kullanım amacı** (mod belirliyor).
- Fotorealizm isteniyorsa prompt'a doğrudan **`photorealistic`** kelimesi; doku için
  `pores, wrinkles, fabric wear, imperfections`; `glamorized / retouched / cinematic grading` gibi
  sahneleme çağrıştıran kelimelerden kaçınma.
- **Metin**: tırnak veya BÜYÜK HARF + `text appears once and is perfectly legible`,
  `no extra characters`. **Türkçe karakter sorununun somut çaresi**: zor yazımları
  *harf harf hecele* (`spell out letter-by-letter`) — dosyanın mevcut Türkçe uyarısına
  eklenecek en değerli satır. Küçük/yoğun metinde `quality: medium|high`.
- **Referans görsel**: görselleri indeksle (`Image 1: … Image 2: …`), etkileşimi tarif et
  (`apply Image 2's style to Image 1`), kimliği kilitle
  (`Do not change her face, facial features, skin tone, body shape, pose, or identity`).
- **İterasyon**: `change only X` + `keep everything else the same`, ve **koruma listesini her
  turda tekrarla** (drift'i azaltıyor). Dosyanın 5. davranış kuralıyla uyumlu, onu güçlendirir.
- gpt-image-2 metin doğruluğu %95+ ve **Native Thinking Mode** var (kompozisyon/nesne sayısı/kısıtlar
  üzerine render öncesi akıl yürütüyor) → uzun kısıt listeleri artık daha güvenilir.

**Uygulamaya göre kısıtlama (kullanıcı kararı):** teknik ayar bölümü yalnızca uygulamanın
gerçekten gönderdiği alanları önerecek — `size` ∈ {`1024x1024`, `1024x1536`, `1536x1024`},
`quality` ∈ {`low`, `medium`, `high`}, `n` ∈ 1–4. `output_format`, `background`,
`input_fidelity`, `stream`, `partial_images` ve 2K üstü boyutlar tabloları dosyadan çıkarılır
(`azure_client.build_payload` bunları hiç göndermiyor — önerilmesi ölü öneri).
İçerik filtresi, fotorealistik çocuk görseli kısıtı, maliyet farkındalığı ve sınırlar bölümü
**aynen korunur**; oradaki bilgi doğru ve değerli.

---

## Kararlar

| # | Karar | Seçim |
|---|---|---|
| 1 | Talimat dosyası nerede | `bundled/prompts/prompt-yonetmeni.md` (gömülü varsayılan) + `data_dir()/chat-instructions.md` (kullanıcı ezmesi) |
| 2 | Kimlik bilgileri | Sohbet, görselin key + base_url'ünü **paylaşır**; tek yeni ve arayüzde görünen alan `AZURE_CHAT_DEPLOYMENT` |
| 3 | Uç | Streaming YOK — senkron `def` `POST /api/chat` |
| 4 | Sohbet geçmişi | Yalnızca istemcide JS dizisi; diske yazılmaz |
| 5 | Yerleşim | Üst barda `.seg` sekmeleri → `#view-image` / `#view-chat` |
| 6 | Sürüm | `1.12.0` → `1.13.0` |

---

## 1. Talimat dosyası — `bundled/prompts/prompt-yonetmeni.md`

**Girdi:** kullanıcının yazdığı ham talimat repoda —
`docs/superpowers/specs/2026-08-04-prompt-yonetmeni-talimat-girdi.md`.
Bu dosya **olduğu gibi paketlenmez**: yukarıdaki 6 olgusal hata düzeltilip teknik ayar bölümü
uygulamanın desteklediği değerlere kısıtlandıktan sonra `bundled/prompts/prompt-yonetmeni.md`
olarak yazılır. Girdi dosyası, neyin neden değiştiğinin izi olarak `specs/`'te kalır.

`bundled/` zaten PyInstaller data dizini (`gpt-image-studio.spec:56-59` → `('bundled','bundled')`),
yani **spec değişikliği gerekmez**.

Neden gömülü + ezme: 200 satırlık Türkçe markdown'ı `.py` içine gömmek okunamaz ve paketlenmiş
`.app` içinde düzenlenemez; `seed.py`'nin "bir kez kopyala" deseni ise yanlış olur — o desen
*kullanıcı varlıkları silinse de dönmesin* diye var, talimat ise tam tersi: v1.14'te iyileştirilen
varsayılan, kendi dosyasını özelleştirmemiş herkese **ulaşmalı**.

`paths.py`'ye (`bundled_logos_dir` yanına, paths.py:52-60):

```python
def bundled_prompts_dir() -> str:
    return os.path.join(resource_dir(), "bundled", "prompts")

def chat_instructions_override() -> str:
    """Kullanıcının düzenleyebildiği talimat dosyası (varsa gömülü olanı EZER)."""
    return os.path.join(data_dir(), "chat-instructions.md")
```

Yeni `chat_prompt.py` (üçüncü parti import YOK):

```python
INSTRUCTIONS_FILE = "prompt-yonetmeni.md"
MIN_INSTRUCTIONS_CHARS = 500   # boş/kırpık dosya sessizce persona'yı öldürür

def candidate_paths() -> list[str]: ...   # [ezme, gömülü]

def load_instructions(*, paths_override=None) -> str:
    """İlk okunabilir VE yeterince uzun talimat dosyasının metni; yoksa ValueError."""
```

Döngüsel import olmaması için: `chat_prompt` düz `ValueError` yükseltir, `chat_client` onu
`ChatError`'a çevirir (tek yönlü bağımlılık: `chat_client` → `chat_prompt`).

Ezme yolu keşfedilebilir olsun: `GET /api/settings` `chat_instructions_path` döndürür, ayarlar
modalinde `.field-note` olarak gösterilir (`version`'ın rota katmanında eklenmesiyle aynı desen,
app.py:486-497).

---

## 2. `azure_client.py` — birleştirmeli yazım (kritik)

Engel: `save_credentials()` (azure_client.py:98-132) dosyayı **sıfırdan iki satır** yazıyor —
görsel ayarı kaydetmek `AZURE_CHAT_DEPLOYMENT`'ı **siler**. Mevcut imzalar korunarak:

```python
CHAT_KEYS = ("AZURE_CHAT_API_KEY", "AZURE_CHAT_BASE_URL", "AZURE_CHAT_DEPLOYMENT")
KNOWN_KEYS = ("AZURE_IMAGE_API_KEY", "AZURE_IMAGE_BASE_URL", *CHAT_KEYS)

def _parse_env_all(path) -> dict[str, str]: ...      # mevcut gövde, iki isme sabitlenmeden
def _parse_env_file(path) -> tuple[str, str]: ...    # GERİYE UYUM: OSError sözleşmesi korunur
def read_env_values(env_path=None) -> dict[str, str]: ...  # aday dosyaların BİRLEŞİK görünümü
def save_env(updates: dict, env_path=None) -> str: ...     # OKU→BİRLEŞTİR→atomik yaz (mkstemp+0600+replace)
def save_credentials(api_key, base_url, env_path=None) -> str:
    ...  # mevcut doğrulamalar aynen, sonra save_env({...})
```

Görsel kimliği **`_first_complete_credentials` ile okunmaya devam eder** (üretimde kanıtlanmış
tek yol); sohbet ayarları birleşik görünümden okunur — `AZURE_CHAT_DEPLOYMENT` app dosyasında,
görsel kimliği eski `claude-tools` dosyasında olabilir.

`get_settings_status()` iki **gizli olmayan** alan kazanır: `chat_deployment`, `chat_configured`.
`AZURE_CHAT_API_KEY` **asla** dönmez (test_settings.py:128'in `"key" not in status` iddiası korunur).

**Neden forma ikinci bir gizli alan eklenmiyor:** app.py:105-116'daki redaksiyon `loc`'ta
`api_key` arıyor; `chat_api_key` diye bir form alanı bu redaksiyonu sessizce atlatır. Ayrı kaynak
gerekiyorsa `AZURE_CHAT_BASE_URL` / `AZURE_CHAT_API_KEY` `credentials.env`'e elle yazılır.

---

## 3. `chat_client.py` — `azure_client.py`'nin ikizi

Ham `httpx`, fonksiyon içinde lazy import, kendi hata sınıfı, Türkçe `map_error`.
`requirements.txt` **değişmez** (httpx zaten var) ⇒ `spec` `hiddenimports` da değişmez.

```python
REQUEST_TIMEOUT = 180.0   # azure_client'takinden UZUN: akıl yürüten model + ~9 bin karakter talimat

class ChatError(Exception): ...

def map_error(status_code, body) -> str:
    # 401 / 429 / 400+content → azure_client ile aynı Türkçe metinler, ARTI:
    # 404 → "Sohbet dağıtımı bulunamadı (404): Ayarlar'daki dağıtım adını
    #        Azure AI Foundry'deki adla karşılaştır."   ← BU uçta en sık hata

def load_credentials(env_path=None) -> tuple[str, str, str]:
    """(key, base_url, deployment). Sohbet key/url'si yoksa GÖRSEL olanlara düşer."""

def build_payload(messages, deployment, instructions) -> dict:
    """MİNİMAL ve savunmacı: yalnızca model + messages.

    temperature/top_p/max_tokens BİLEREK YOK: GPT-5 sınıfı akıl yürüten dağıtımlar
    bunları 400 ile reddedebiliyor (max_tokens yerine max_completion_tokens istiyorlar)
    ve hiçbiri gerekli değil — persona'nın tamamı sistem talimatında.
    """
    return {"model": deployment,   # DAĞITIM adı, model ailesi adı DEĞİL
            "messages": [{"role": "system", "content": instructions}, *messages]}

def extract_content(response_json) -> tuple[str, str]:
    """(content, finish_reason). Boş içerik GÜRÜLTÜLÜ hata olur, boş baloncuk DEĞİL —
    finish_reason mesaja girer ki tek turda teşhis edilebilsin."""

def complete(messages, *, client=None, credentials=None, instructions=None) -> dict:
    # endpoint = base_url.rstrip("/") + "/chat/completions"
    # headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    # 200 değilse → ChatError(map_error(...))
```

---

## 4. Rota ve modeller

`models.py` sonuna:

```python
MAX_CHAT_MESSAGES = 24          # ~12 tur
MAX_CHAT_MSG_CHARS = 6000
MAX_CHAT_TOTAL_CHARS = 60000
CHAT_ROLES = {"user", "assistant"}

class ChatMessage(BaseModel):     # extra="forbid"
    role: str        # "system" BİLEREK KABUL EDİLMİYOR — sistem mesajını sunucu koyar;
                     # izin verilse istemci persona'yı değiştirir ve extra="forbid" yakalamaz
    content: str = Field(min_length=1, max_length=MAX_CHAT_MSG_CHARS)

class ChatRequest(BaseModel):     # extra="forbid"
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_CHAT_MESSAGES)
    # validator: son mesaj role="user" olmalı; toplam karakter MAX_CHAT_TOTAL_CHARS'ı aşmamalı
```

`SettingsRequest` (models.py:136) `chat_deployment: str = Field(default="", max_length=200)`
kazanır. Bu model `extra="forbid"` istisnasıdır (models.py:11-12) — **o docstring paragrafı
güncellenmeli**. Burada boş değer "temizle" demek (`api_key`'in aksine) ve sorun değil: gizli
bilgi değil, alan `GET /api/settings`'ten önceden doldurulmuş geliyor.

`app.py`'ye (`post_settings`'ten hemen sonra, app.py:517):

```python
@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    """Prompt yönetmeni: Türkçe sohbet → İngilizce gpt-image-2 prompt'u.

    SENKRON `def` (bilinçli): httpx çağrısı bloklayıcı, Starlette bunu kendi
    threadpool'unda koşturur ve olay döngüsü — yani pencere — donmaz;
    /api/generate'in aynısı. Yanıt DİSKE YAZILMAZ.
    """
    try:
        return cc.complete([m.model_dump() for m in req.messages])
    except cc.ChatError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

`import chat_client as cc` + `ChatRequest`'i `from models import (...)` bloğuna ekle.
`post_settings` içinde `ac.save_credentials(...)` başarılıysa ayrı bir çağrı ile
`ac.save_env({"AZURE_CHAT_DEPLOYMENT": ...})` — görsel kimliği doğrulamadan geçmeden sohbet
ayarı yazılmaz.

**Sohbet geçmişi diske yazılmaz** (karar 4): tek kalıcı çıktı prompt'un kendisi ve o zaten
üretim anında `storage.save` ile `history.json`'a giriyor (app.py:322-332). Bir `chat_store.py`
dördüncü bir "prompt yaşayan yer" üretirdi. Kayıp riski `confirmDialog()` (core.js:392) ile
kapatılır: "Sohbeti temizle" onay ister.

---

## 5. Frontend — sekmeli kabuk

### 5a. Sekmeler

`index.html` topbar'da, `.sub` satırının altına — mevcut `.seg` bileşeni (style.css:148-157)
yeniden kullanılır:

```html
<div class="seg view-tabs" role="tablist" aria-label="Çalışma alanı">
  <button id="tab-image" class="active" role="tab" aria-selected="true"  aria-controls="view-image">Görsel</button>
  <button id="tab-chat"                 role="tab" aria-selected="false" aria-controls="view-chat">Prompt Yönetmeni</button>
</div>
```

Gövde iki görünüme sarılır. `<main class="layout">` → `<div class="layout">` olur (CSS sınıf
seçicisi olduğu için stil bozulmaz) ve **tek** `<main>` ikisini kapsar:

```html
<main>
  <div id="view-image" role="tabpanel" aria-labelledby="tab-image">
    <div class="layout">…mevcut .controls + .stage…</div>
    <section class="gallery-wrap">…</section>
  </div>
  <div id="view-chat" role="tabpanel" aria-labelledby="tab-chat" hidden>…</div>
</main>
```

`showView(name)` ve sekme dinleyicileri **core.js**'te yaşar (kabuk sorumluluğu, sohbete özel
değil); `chat.js` yalnızca `showView("image")` çağırır — böylece `chat.js` sadece kendinden
önceki dosyalara bakan bir yaprak kalır ve yükleme sırası sözleşmesi bozulmaz.

### 5b. Sohbet sayfası

Ortalanmış tek kolon (`max-width: 860px`), dipte yapışkan besteci, üstte akış:

- **Boş durum**: kısa açıklama + 3–4 başlangıç çipi ("Kurban Bayramı için Instagram kare
  görseli", "Blog kapağı — sıcak editoryal fotoğraf", "Düz vektör illüstrasyon"). Tıklayınca
  `#chat-input`'a yazar. Boş bir sohbet ekranının "ne yazacağım" sürtünmesini kaldırır.
- **Mesaj baloncukları**: kullanıcı sağa yapışık ve `--panel-2` zeminli; yönetmen tam genişlikte
  `--panel` üzerinde, `<pre>` blokları `--panel-2` ve `overflow-x: auto`.
- **Bekleme göstergesi**: mevcut `.spinner` (style.css:489) + `#chat-status`.
  **DİKKAT:** `startProgress()` `#progress-fill`/`#progress-pct`'ye dokunuyor (core.js:31-70)
  ve o düğümler `.stage` içinde, yani **diğer sekmede** — sohbette kullanılamaz.
- **Eylem satırı** (yalnızca ayrıştırma başarılıysa): "Forma aktar (prompt + ayarlar)" +
  "Prompt'u kopyala".
- Cmd/Ctrl+Enter gönderir. Sekme açıldığında, akış boşsa ve `#prompt` doluysa `#chat-input`
  o metinle ön doldurulur (mevcut taslağı brainstorm'a çevirmek).

### 5c. Güvenli markdown (innerHTML YOK)

Ev kuralı: sunucudan/modelden gelen metin **yalnızca `textContent`** ile DOM'a girer
(`renderExtras`, core.js:150-177 ile aynı duruş). Kütüphane eklenmez; gereken tek şey kod bloğu,
madde ve `**kalın**`:

```js
const FENCE = /^\s*```(\w*)\s*$/;
function renderMarkdownInto(host, text)   // satır satır: fence topla → <pre><code textContent>
function codeBlock(body, lang)            // code.textContent = body
function prose(line)                      // ** → <strong>, gerisi createTextNode
```

`#chat-log` yalnızca `innerHTML = ""` ile temizlenir (core.js:152 ile aynı) — asla sunucu metni
atanmaz. Tablolar düz satır olarak görünür; talimat dosyasının zorunlu çıktı formatı fence ve
madde kullanıyor, tablo kullanmıyor — kabul edilebilir.

### 5d. Asıl kazanç: ayrıştır ve uygula

```js
function fencedBlocks(text)        // {lang, body, heading} — heading = fence'ten önceki son dolu satır
function parseDirectorReply(text)  // → { prompt, settings }
```

- `settings`: `lang === "json"` veya `{` ile başlayan, `JSON.parse` edilebilen **ilk nesne**.
- `prompt`: başlığında `PROMPT` geçen blok; yoksa **en uzun** kalan blok (yönetmen prozası uzundur).
  Format kayarsa sessizce boş dönmez.

Forma uygulama — **yalnızca `<option>` listesinde var olan değerler**:

```js
const SETTING_TARGETS = [["size","size","Boyut"], ["quality","quality","Kalite"], ["n","n","Adet"]];

function applyIfSupported(selectId, value) {
  // DİKKAT: #n seçeneklerinde value ATTRIBUTE'u YOK (index.html:48) → option.value metne
  // düşer, "2" doğru eşleşir. Hem o.value hem o.text kontrol edilir ki bir gün value
  // eklenirse de çalışsın.
}

function applyToForm(parsed) {
  // prompt MAX_PROMPT_CHARS'ı aşıyorsa KIRPMA — yönetmene kısaltmasını söyle (sunucu 422 verir)
  // $("prompt").value = parsed.prompt;  → showView("image"); $("prompt").focus();
  // Sessiz sapma YASAK (palette applied:false gerekçesi, core.js:327-333):
  //   uygulanamayan öneriler "…uygulanamadı: Boyut 2048x1152" diye AÇIKÇA söylenir.
}
```

`MAX_PROMPT_CHARS` JS sabiti olarak aynalanır, yorumu models.py:21'e işaret eder
(core.js:20-21'deki `MAX_EDIT_IMAGES` geleneği).

`#go` **otomatik tıklanmaz**: üretim para harcıyor ve talimat dosyası 5 görsel/dakika kotasını
kendisi uyarıyor.

Gönderim akışı `detailText(err)` (palette.js:128) ile hata metnini çıkarır; **başarısız tur
geçmişte kalmaz** (`chatThread` son eleman geri alınır) ki yeniden gönderim aynı hatayı
tekrarlamasın.

### 5e. Yükleme sırası ve test sözleşmesi

`static/chat.js` **en sona**, `viewer.js`'ten sonra: yaprak dosya, yalnızca `$`, `statusEl`,
`detailText`, `confirmDialog`, `showView`, `MAX_PROMPT_CHARS`'a bakıyor — hepsi o noktada tanımlı.

- `index.html`: `<script src="/static/chat.js?v=__APP_VERSION__">` (elle sürüm YAZMA).
- `tests/test_index.py:500-512` `order` listesine `"chat.js"` eklenir.
- Başlık yorumları altı dosyayı listeleyecek şekilde güncellenir: core.js:1-8 (bugün beş dosya
  sayıyor, `viewer.js` eksik), settings.js:1-8, index.html:474-484.
- `settings.js` `applyConfigured()` (settings.js:14-31) sohbet kapısını kurar — chat.js'ten ÖNCE
  yüklenmesi sorun değil, yalnızca DOM id'lerine dokunuyor:
  `#tab-chat` / `#chat-send` `disabled = !s.chat_configured`, `#set-chat-deployment` doldurulur,
  `chat_instructions_path` `.field-note`'a yazılır.

---

## 6. Ayarlar modali

`#settings-modal` içinde, API key alanından sonra (index.html:230):
alt başlık "Prompt Yönetmeni (sohbet modeli)", `#set-chat-deployment` metin girdisi
(placeholder `ör. gpt-5.6-luna`) ve not: *"Azure AI Foundry'deki **deployment** adı — model
ailesi adı değil. Boş bırakılırsa Prompt Yönetmeni kapalı kalır."*

`saveSettings()` (settings.js:59-87) gövdeye `chat_deployment` ekler. `openSettings()`
(settings.js:48-53) `#set-key`'i her açılışta temizliyor — `#set-chat-deployment`'ı
**temizlememeli** (yazma-yalnız değil; GET'ten doluyor).

---

## 7. Testler

`tests/test_chat_client.py` — `tests/test_azure_client_http.py`'nin `FakeResponse`/`FakeClient`'ını aynala:
uç `/chat/completions`; `Authorization: Bearer`; `payload["model"] == <dağıtım>`;
`messages[0]` sistem mesajı ve talimat metni; **tripwire `set(payload) == {"model","messages"}`**
(örnekleme parametresi eklenirse canlı doğrulanmalı); `map_error` 401/**404**/429/400+content Türkçe;
`extract_content` boş `choices` / `content: null` / `content: ""` durumlarında `ChatError`
(`IndexError`/`KeyError` DEĞİL) ve `finish_reason` mesaja giriyor; `load_credentials` görsel
kimliğine düşüyor / sohbet anahtarlarını tercih ediyor / dağıtım yoksa Türkçe hata.

`tests/test_chat_route.py` — fixture `appmod.cc.complete`'i, yani **modül niteliğini**
monkeypatch eder (conftest.py:60-62 uyarısı: `from x import y` bunu boşa çıkarır);
200 gövdesi; `ChatError` → 502 + Türkçe `detail` birebir; 422: istemciden `role:"system"`,
boş `messages`, sınır aşımı, toplam karakter aşımı, son mesaj `assistant`, bilinmeyen alan;
ve çağrı sonrası `history.json`'ın **olmadığı** (kalıcılık yok kararı mekanik hale gelir).

`tests/test_chat_prompt.py` — gömülü varsayılan repoda var, `>= MIN_INSTRUCTIONS_CHARS`, ve
frontend ayrıştırıcısının dayandığı çıpaları içeriyor (`PROMPT` ve bir ` ```json ` fence)
→ talimatı ayrıştırıcının okuyamayacağı bir formata çevirmeyi engelleyen tripwire;
ezme gömülüyü yeniyor; kısa/boş ezme **atlanıyor**; ikisi de yoksa Türkçe hata;
`bundled/prompts`'un spec'in `('bundled','bundled')` girdisi altında olduğu (test_version.py:28-33 tekniği).

`tests/test_settings_route.py` — `chat_deployment` POST→GET turu; **birleştirmeli yazım
regresyon testi**: dağıtımı kaydet → yalnızca görsel kimliğini POST et → `AZURE_CHAT_DEPLOYMENT`
hayatta mı (`save_env` birleştirmezse bu test kırmızı); aynası (dağıtım kaydı `load_credentials`'ı
bozmuyor); elle yazılmış `AZURE_CHAT_API_KEY` değeri `r.text`'te **yok**;
`chat_configured` dağıtım boşken `False`.

`tests/test_index.py` — servis edilen id'ler (`tab-image`, `tab-chat`, `view-image`, `view-chat`,
`chat-log`, `chat-input`, `chat-send`, `chat-clear`, `set-chat-deployment`); `chat.js` sıra
listesine eklendi; **güvenlik tripwire'ı** `chat.js`'te `innerHTML` yalnızca boş-string temizliği
olarak geçiyor; **savunmacı-uygulama tripwire'ı** `\.options` aranıyor (yoksa `2048x1152` önerisi
forma girip sunucudan 422 alır); **sessiz-sapma tripwire'ı** `"uygulanamadı"` metni var;
istemci asla `"system"` göndermiyor.

---

## 8. Sürüm ve dokümanlar

- `version.py:26` → `APP_VERSION = "1.13.0"` (yeni kullanıcıya dönük özellik ⇒ MINOR).
  Aynı zamanda `?v=` cache-buster; `tests/test_index.py:397` her `?v=`'nin buna eşit olduğunu
  doğruluyor.
- `README.md`: "Özellikler"e prompt yönetmeni maddesi; "Kimlik" bölümüne (README.md:10-12)
  `AZURE_CHAT_DEPLOYMENT` (+ opsiyonel `AZURE_CHAT_BASE_URL` / `AZURE_CHAT_API_KEY`);
  `bundled/prompts/prompt-yonetmeni.md` ve `chat-instructions.md` ezmesi.
- `KURULUM.md`: "Azure kimliğini gir" adımından sonra dağıtım adı adımı (Foundry *deployment* adı).
- `GUNCELLEME.md`: "Sürüm 1.13.0'da ne değişti" bölümü. **Not:** bu dosya hâlâ 1.10.0'dan
  bahsediyor, uygulama 1.12.0'da — bu bayatlık ayrı bir iş, sessizce yeniden yazılmayacak.
- `requirements.txt` ve `gpt-image-studio.spec` **değişmez**.

---

## 9. Doğrulama

1. **Canlı uç doğrulaması (kod yazmadan ÖNCE, en güçlü varsayım).** `POST {base}/chat/completions`
   ve `api-version`'sız çalışma:
   ```bash
   curl -sS -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d '{"model":"<dağıtım>","messages":[{"role":"user","content":"ping"}]}' "$BASE_URL/chat/completions"
   ```
   404 dönerse `?api-version=preview` veya `/deployments/<ad>/chat/completions` gerekir —
   `complete()`'te tek satır fark.
2. `pytest` — tüm suite yeşil (`build.sh:35` bunu paketlemeden önce zaten koşuyor).
3. `./run.sh` → tarayıcıda: sekmeler geçiş yapıyor, "Prompt Yönetmeni" dağıtım adı girilmeden
   kilitli; Ayarlar'dan dağıtım adı girilince açılıyor.
4. Gerçek bir tur: "Kurban Bayramı için kare Instagram görseli" → yönetmen yanıtı geliyor,
   PROMPT ve JSON blokları render ediliyor, "Forma aktar" prompt'u `#prompt`'a yazıp Görsel
   sekmesine dönüyor, `size/quality/n` uygulanıyor.
5. Uyumsuz öneri testi: yönetmene bilerek `2048x1152` isteyip "…uygulanamadı" mesajının
   göründüğünü doğrula.
6. `#go` ile gerçek üretim → görsel geliyor, `history.json`'da prompt kayıtlı.
7. Ayarlar regresyonu: dağıtım adı girildikten sonra Azure endpoint'ini tek başına kaydet →
   dağıtım adı hayatta.
8. Dar pencere (1024×700) ve `prefers-reduced-motion` ile sohbet sayfası kontrolü.

---

## 10. Riskler / açık noktalar

1. **`api-version`'sız `chat/completions`** — planın en güçlü varsayımı. Adım 9.1 ile önce doğrula.
2. **Akıl yürüten model tuhaflıkları** — `finish_reason: "length"` + boş içerik gelirse
   `max_completion_tokens` gerekir. `extract_content` bunu boş baloncuk değil **gürültülü Türkçe
   hata** yapıyor, yani tek turda teşhis edilebilir. Önleyici olarak örnekleme parametresi eklenmez.
3. **Gecikme** — ~9 bin karakter talimat + akıl yürütme `azure_client`'ın 120 s'sini aşabilir;
   bu yüzden `chat_client.REQUEST_TIMEOUT = 180.0`. İlk gerçek çağrıyı ölç: 40 s+ ise streaming
   yükseltmesi öne alınır (yol: `StreamingResponse` **senkron** generator kabul ediyor —
   Starlette `iterate_in_threadpool` ile sarar, yani `httpx.Client.stream` düz `def` içinde
   asyncio'suz çalışır; §5d dokunulmadan kalır).
4. **Talimat her turda gider** — ~9 bin karakter × her mesaj, bu ham httpx yüzeyinde prompt
   caching yok. Tek kullanıcılı masaüstü araç için kabul edilebilir; token maliyeti kullanıcının bilgisinde.
5. **İçerik filtresi sohbette de var** — engellenen konuda 400/`contentFilter`; `map_error` kapsıyor.
6. **`.seg` sekmeleri klavye** — `role="tablist"` eklendiğine göre ok tuşu gezinmesi beklenir;
   ilk sürümde Tab+Enter ile yetinilecek (mevcut modal içi `.seg` kullanımları da öyle),
   `aria-selected` doğru güncellenir.
