// GPT-Image Studio — Prompt Yönetmeni: Türkçe sohbet → İngilizce gpt-image-2 prompt'u.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js → viewer.js → chat.js
//
// Bu dosya EN SONDA: bir YAPRAK, yalnızca kendinden önce tanımlanan adlara
// bakıyor ($, statusEl, detailText, confirmDialog, promptDialog, showView,
// MAX_PROMPT_CHARS). Sekme geçişinin kendisi core.js'te (kabuk sorumluluğu).
//
// GÜVENLİK DURUŞU: sunucudan/modelden gelen metin DOM'a yalnızca `textContent`
// ile girer (renderExtras ile aynı duruş). `innerHTML` bu dosyada tek bir yerde,
// akışı BOŞ DİZEYLE temizlemek için kullanılıyor. Yönetmenin seçenek etiketleri
// de model metnidir — onlar da aynı kapıdan geçer.

// Sunucudaki models.py sınırlarının aynası. İstemci kapısı olmadan sınır aşımı
// pydantic'in İNGİLİZCE 422 metniyle geri dönerdi.
const MAX_CHAT_MESSAGES = 24;        // models.MAX_CHAT_MESSAGES
const MAX_CHAT_MSG_CHARS = 6000;     // models.MAX_CHAT_MSG_CHARS (KULLANICI mesajı)
const MAX_CHAT_TOTAL_CHARS = 60000;  // models.MAX_CHAT_TOTAL_CHARS
// Yanıt sınırı (models.MAX_CHAT_REPLY_CHARS) BİLEREK aynalanmıyor: burada
// ölçülecek bir şey yok, gelen yanıtı sunucu zaten kapıda kesiyor. Aşağıdaki
// toplam kapısı da yanıt için yer AYIRMIYOR — kaydetme kapısı (models
// .MAX_CHAT_SAVE_TOTAL_CHARS) tam bir yanıt kadar geniş, yoksa sınırın dibinde
// geçen bir turun yanıtı hiç kaydedilemezdi.
// Başlık ilk kullanıcı mesajından türetiliyor. Modele "bu sohbete isim ver"
// diye İKİNCİ bir çağrı YAPILMIYOR: para ve gecikme, kazancı bir etiket.
// Beğenmeyen kullanıcı 3-nokta menüsünden yeniden adlandırıyor.
const CHAT_TITLE_CHARS = 48;         // models.MAX_CHAT_TITLE_CHARS'tan (120) dar

// Açık sohbetin gövdesi burada yaşıyor; her tur sonunda /api/chats'e yazılıyor
// (v1.15). currentChatId null = henüz kaydedilmemiş yeni sohbet.
let chatThread = [];
let chatBusy = false;
let currentChatId = null;
let chatSummaries = [];
let openMenuId = null;               // 3-nokta menüsü açık olan sohbet (yoksa null)

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

function chatStatus(text) {
  $("chat-status").textContent = text;
}

// ── Güvenli markdown (innerHTML YOK) ────────────────────────────────
// Kütüphane eklenmiyor; yönetmenin çıktı formatında gereken tek şey kod bloğu,
// madde, `**kalın**` ve `` `kod` ``. Tablo düz satır olarak görünür — talimat
// dosyasının zorunlu çıktı formatı tablo kullanmıyor.
const FENCE = /^\s*```(\w*)\s*$/;
const INLINE = /\*\*([^*]+)\*\*|`([^`]+)`/g;
// Prompt bloğunun hemen üstündeki tekrar başlık ("PROMPT" / "PROMPT:").
const PROMPT_HEADING = /^\s*prompt\s*:?\s*$/i;

function appendInline(host, text) {
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) host.appendChild(document.createTextNode(text.slice(last, m.index)));
    const bold = m[1] !== undefined;
    const el = document.createElement(bold ? "strong" : "code");
    el.textContent = bold ? m[1] : m[2];
    host.appendChild(el);
    last = m.index + m[0].length;
  }
  if (last < text.length) host.appendChild(document.createTextNode(text.slice(last)));
}

function codeBlock(body, lang) {
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.textContent = body;            // ← model metni yalnızca BURADAN giriyor
  if (lang) code.dataset.lang = lang;
  pre.appendChild(code);
  return pre;
}

function prose(line) {
  const p = document.createElement("p");
  appendInline(p, line.replace(/^#{1,6}\s+/, ""));
  return p;
}

/** Prompt bloğu + eylem barı: sayfadaki asıl ürün, düğmeleri de kendi başında.
 *
 * Eylemler v1.14'te mesajın EN ALTINDA duruyordu (`.chat-msg-actions`): prompt'u
 * okuyan göz düğmeleri bulmak için varyasyon ve parametre listelerini geçmek
 * zorundaydı. Bar bloğun başında, bakılan şeyin yanında.
 */
function promptFigure(pre, parsed) {
  const fig = document.createElement("figure");
  fig.className = "chat-prompt";

  const bar = document.createElement("div");
  bar.className = "chat-prompt-bar";

  const label = document.createElement("span");
  label.className = "chat-prompt-label";
  label.textContent = "PROMPT";

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "btn-ghost chat-prompt-btn";
  copy.textContent = "Kopyala";
  copy.addEventListener("click", () => copyPrompt(parsed.prompt));

  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "primary chat-prompt-btn";
  apply.textContent = "Forma aktar";
  apply.addEventListener("click", () => applyToForm(parsed));

  bar.append(label, copy, apply);
  fig.append(bar, pre);
  return fig;
}

function renderMarkdownInto(host, text, parsed) {
  const lines = text.split("\n");
  let list = null;
  for (let i = 0; i < lines.length; i++) {
    const fence = FENCE.exec(lines[i]);
    if (fence) {
      list = null;
      const body = [];
      i++;
      while (i < lines.length && !FENCE.test(lines[i])) body.push(lines[i++]);
      const joined = body.join("\n");
      // Seçenek bloğu ÇİZİLMEZ: onun görünür karşılığı tıklanabilir çipler
      // (renderOptions). Atlanmasa kullanıcı ham JSON okurdu.
      if (parsed.optionsBody && joined.trim() === parsed.optionsBody) continue;
      const pre = codeBlock(joined, fence[1] || "");
      if (parsed.prompt && joined.trim() === parsed.prompt) {
        pre.classList.add("chat-prompt-block");
        // Talimat dosyası bloğun üstüne "**PROMPT**" yazdırıyor; barın etiketi de
        // aynı şeyi söylüyor. Etiket barda KALIYOR (yapısal ve her zaman doğru),
        // yalnız o tekrar satırı yutuluyor. Model başka bir şey yazdıysa
        // dokunulmaz — desen tam eşleşmeye bakıyor.
        const last = host.lastElementChild;
        if (last && last.tagName === "P" && PROMPT_HEADING.test(last.textContent)) {
          last.remove();
        }
        host.appendChild(promptFigure(pre, parsed));
        continue;
      }
      host.appendChild(pre);
      continue;
    }
    const line = lines[i];
    if (!line.trim()) { list = null; continue; }
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (bullet) {
      if (!list) { list = document.createElement("ul"); host.appendChild(list); }
      const li = document.createElement("li");
      appendInline(li, bullet[1]);
      list.appendChild(li);
      continue;
    }
    list = null;
    host.appendChild(prose(line));
  }
}

// ── Ayrıştırma: asıl kazanç ─────────────────────────────────────────

/** Fence'li bloklar + her birinin ÖNCESİNDEKİ son dolu satır (başlık ipucu). */
function fencedBlocks(text) {
  const lines = text.split("\n");
  const blocks = [];
  let heading = "";
  for (let i = 0; i < lines.length; i++) {
    const fence = FENCE.exec(lines[i]);
    if (!fence) {
      if (lines[i].trim()) heading = lines[i].trim();
      continue;
    }
    const body = [];
    i++;
    while (i < lines.length && !FENCE.test(lines[i])) body.push(lines[i++]);
    blocks.push({ lang: fence[1] || "", body: body.join("\n").trim(), heading });
    heading = "";
  }
  return blocks;
}

/** Gövdesi JSON NESNESİ olan bloğu ayrıştırır; değilse null. */
function jsonObject(block) {
  if (block.lang !== "json" && block.lang !== "options"
      && !block.body.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(block.body);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch { return null; }   // biçimi kaymış blok: prompt adayı olarak kalsın
}

// Teknik ayar bloğunun İMZASI. Blok tipini "ilk JSON nesnesi" diye seçmek
// v1.15'te KIRILDI: seçenek bloğu da `{` ile başlıyor ve yanıtta ondan ÖNCE
// geliyor — o kural yönetmenin seçeneklerini forma AYAR olarak yazardı
// (desteklenmeyen değer → üretimde 422). Tip artık anahtardan okunuyor.
const SETTING_KEYS = ["size", "quality", "n"];

/** → { prompt, settings, options, optionsBody }. Biçim kayarsa en iyi adayı seçer. */
function parseDirectorReply(text) {
  const blocks = fencedBlocks(text);
  let settings = null;
  let settingsBlock = null;
  let options = null;
  let optionsBlock = null;

  for (const b of blocks) {
    const obj = jsonObject(b);
    if (!obj) continue;
    if (!settings && SETTING_KEYS.some((k) => obj[k] !== undefined)) {
      settings = obj;
      settingsBlock = b;
      continue;
    }
    if (!options && Array.isArray(obj.secenekler) && obj.secenekler.length) {
      options = obj;
      optionsBlock = b;
    }
  }

  const candidates = blocks.filter(
    (b) => b !== settingsBlock && b !== optionsBlock && b.body);
  let promptBlock = candidates.find((b) => /PROMPT/i.test(b.heading));
  if (!promptBlock) {
    // Başlık kayarsa en UZUN blok: yönetmenin prozası her zaman en uzundur.
    promptBlock = candidates.reduce(
      (best, b) => (!best || b.body.length > best.body.length ? b : best), null);
  }
  return {
    prompt: promptBlock ? promptBlock.body : "",
    settings,
    options,
    optionsBody: optionsBlock ? optionsBlock.body : "",
  };
}

// ── Tıklanabilir seçenekler ─────────────────────────────────────────
// Yönetmen soruyu prozada da soruyor; buradaki çipler onun makine tarafı.
// Serbest yazı alanı HER ZAMAN var: "bunların hiçbiri değil" cevabı bir
// seçenek olarak listelenemez (talimat dosyası "diğer" yazmayı da yasaklıyor).

const OPTION_MAX = 8;                // savunma: model uzun bir liste döndürürse
const OPTION_JOIN = " · ";

function optionChip(label, multi, group) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chat-option";
  chip.setAttribute("role", multi ? "checkbox" : "radio");
  chip.setAttribute("aria-checked", "false");
  chip.textContent = label;          // ← model metni: yalnızca textContent
  chip.addEventListener("click", () => {
    const on = chip.getAttribute("aria-checked") === "true";
    if (!multi) {
      // Tek seçim: birbirini dışlayan eksenlerde (mecra gibi) iki cevap
      // göndermek yönetmene çelişki okutur.
      for (const other of group.querySelectorAll(".chat-option")) {
        other.setAttribute("aria-checked", "false");
      }
    }
    chip.setAttribute("aria-checked", on ? "false" : "true");
  });
  return chip;
}

function optionsValue(group) {
  const picked = [...group.querySelectorAll(".chat-option")]
    .filter((c) => c.getAttribute("aria-checked") === "true")
    .map((c) => c.textContent);
  const own = group.querySelector(".chat-own-input").value.trim();
  if (!picked.length && !own) return "";
  return picked.length && own ? `${picked.join(OPTION_JOIN)}\n${own}`
                              : (own || picked.join(OPTION_JOIN));
}

/** Grubu kilitler: eski bir soruya ikinci kez cevap gönderilmesin. */
function lockOptions(group) {
  group.classList.add("chat-options-done");
  for (const el of group.querySelectorAll("button, input")) el.disabled = true;
}

/** Yalnızca SON mesajın içindeki grup canlı kalır; geri kalanı kilitlenir.
 *
 * Ölçü "son grup" DEĞİL: kaydedilmiş bir sohbet yeniden açıldığında cevaplanmış
 * tek bir soru da "son grup" olur ve yeniden canlanırdı — kullanıcı eski bir
 * soruya ikinci kez cevap gönderirdi. Ölçü "arkasından başka mesaj gelmemiş
 * olmak"; son mesaj kullanıcıdan ise hiçbir grup canlı değil, o da doğru.
 */
function lockStaleOptions() {
  const log = $("chat-log");
  const last = log.lastElementChild;
  for (const group of log.querySelectorAll(".chat-options")) {
    if (!last || !last.contains(group)) lockOptions(group);
  }
}

function renderOptions(parsed) {
  const spec = parsed.options;
  const group = document.createElement("div");
  group.className = "chat-options";
  group.setAttribute("role", spec.coklu === false ? "radiogroup" : "group");
  group.setAttribute("aria-label", String(spec.soru || "Seçenekler"));

  if (spec.soru) {
    const q = document.createElement("p");
    q.className = "chat-options-q";
    q.textContent = String(spec.soru);
    group.appendChild(q);
  }

  const chips = document.createElement("div");
  chips.className = "chat-options-chips";
  for (const raw of spec.secenekler.slice(0, OPTION_MAX)) {
    chips.appendChild(optionChip(String(raw), spec.coklu !== false, group));
  }
  group.appendChild(chips);

  const own = document.createElement("div");
  own.className = "chat-own";
  const label = document.createElement("label");
  label.className = "chat-own-label";
  label.textContent = "Bunlardan biri değilse kendi fikrini yaz";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "chat-own-input";
  input.maxLength = MAX_CHAT_MSG_CHARS;
  input.placeholder = "Kendi fikrim…";
  const id = `chat-own-${Math.random().toString(36).slice(2, 8)}`;
  input.id = id;
  label.htmlFor = id;

  const send = document.createElement("button");
  send.type = "button";
  send.className = "primary chat-own-send";
  send.textContent = "Devam et";

  const submit = async () => {
    const value = optionsValue(group);
    if (!value) { chatStatus("Bir seçenek seç ya da kendi fikrini yaz."); return; }
    // Gönderim TEK yoldan: sınır kapıları, hata geri alma ve kaydetme
    // sendChat'te yaşıyor; ikinci bir gönderim yolu yazılmıyor.
    $("chat-input").value = value;
    if (await sendChat()) lockOptions(group);
  };
  send.addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); submit(); }
  });

  own.append(label, input, send);
  group.appendChild(own);
  return group;
}

// ── Forma uygulama ──────────────────────────────────────────────────
// [json anahtarı, <select> id'si, kullanıcıya görünen ad]
const SETTING_TARGETS = [["size", "size", "Boyut"], ["quality", "quality", "Kalite"],
                         ["n", "n", "Adet"]];

/** Yalnızca <option> listesinde GERÇEKTEN var olan değeri uygular. */
function applyIfSupported(selectId, value) {
  const el = $(selectId);
  const wanted = String(value).trim();
  // DİKKAT: #n seçeneklerinde value ATTRIBUTE'u YOK → option.value metne düşer
  // ve "2" doğru eşleşir. Yine de İKİSİ de kontrol ediliyor ki bir gün value
  // eklenirse de çalışsın. Bu savunma olmadan yönetmenin önerdiği desteklenmeyen
  // bir değer forma girer ve üretim sunucudan 422 alır.
  const match = [...el.options].find(
    (o) => o.value === wanted || o.text.trim() === wanted);
  if (!match) return false;
  el.value = match.value;
  return true;
}

function applyToForm(parsed) {
  if (!parsed.prompt) {
    chatStatus("Yanıtta prompt bloğu bulunamadı — yönetmene prompt'u tekrar yazmasını söyle.");
    return;
  }
  if (parsed.prompt.length > MAX_PROMPT_CHARS) {
    // KIRPMA YOK: kırpılmış bir prompt sessizce BAŞKA bir görsel üretir.
    chatStatus(`Prompt ${MAX_PROMPT_CHARS} karakter sınırını aşıyor `
      + `(${parsed.prompt.length}). Yönetmene kısaltmasını söyle.`);
    return;
  }

  $("prompt").value = parsed.prompt;
  const skipped = [];
  for (const [key, selectId, label] of SETTING_TARGETS) {
    const value = parsed.settings ? parsed.settings[key] : undefined;
    if (value === undefined || value === null || value === "") continue;
    if (!applyIfSupported(selectId, value)) skipped.push(`${label} ${value}`);
  }

  showView("image");
  $("prompt").focus();
  // SESSİZ SAPMA YASAK (palette applied:false ile aynı gerekçe): uygulanamayan
  // öneri açıkça söylenir, yoksa kullanıcı formda başka bir ayar görür ve
  // sonucu açıklayamaz.
  statusEl.textContent = "Prompt forma aktarıldı."
    + (skipped.length ? ` Şu öneriler uygulanamadı: ${skipped.join(", ")}`
                        + " — formdaki seçeneklerde yok." : "");
}

async function copyPrompt(text) {
  try {
    await navigator.clipboard.writeText(text);
    chatStatus("Prompt kopyalandı.");
  } catch {
    chatStatus("Kopyalanamadı — prompt bloğunu elle seçip kopyala.");
  }
}

// ── Akışa yazma ─────────────────────────────────────────────────────

// Adı native API'den KASITLI olarak farklı (global kapsamda `scrollIntoView`
// adlı bir fonksiyon DOM metoduyla karışıyordu). Gövde native metodu çağırmak
// ZORUNDA: bir kez toplu değiştirme buranın içini de yeniden adlandırdı ve
// gönderme tümden öldü (bkz. tests/test_index.py'deki tripwire).
function scrollMessageIntoView(node) {
  node.scrollIntoView({
    behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "start",
  });
}

function appendUser(text) {
  const div = document.createElement("div");
  div.className = "chat-msg-user";
  div.textContent = text;
  $("chat-log").appendChild(div);
  syncEmptyState();
  scrollMessageIntoView(div);
  return div;
}

function appendBot(text) {
  const parsed = parseDirectorReply(text);
  const div = document.createElement("div");
  div.className = "chat-msg-bot";

  const role = document.createElement("span");
  role.className = "chat-role";
  role.textContent = "Yönetmen";
  div.appendChild(role);

  renderMarkdownInto(div, text, parsed);
  if (parsed.options) div.appendChild(renderOptions(parsed));

  $("chat-log").appendChild(div);
  syncEmptyState();
  scrollMessageIntoView(div);
  return div;
}

function syncEmptyState() {
  $("chat-empty").hidden = chatThread.length > 0;
}

function setChatBusy(busy) {
  chatBusy = busy;
  $("chat-wait").hidden = !busy;
  // Kapı kapalıysa (dağıtım adı yok) düğme kilitli KALIR: settings.js'in
  // kurduğu kilidi buradan geri açmıyoruz.
  $("chat-send").disabled = busy || !chatConfigured;
}

// ── Gönderim ────────────────────────────────────────────────────────

/** → true yalnızca tur BAŞARIYLA tamamlandıysa (seçenek grubu buna göre kilitlenir). */
async function sendChat() {
  if (chatBusy) return false;
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) { chatStatus("Önce bir mesaj yaz."); return false; }
  if (message.length > MAX_CHAT_MSG_CHARS) {
    chatStatus(`Mesaj çok uzun (${message.length}/${MAX_CHAT_MSG_CHARS} karakter).`);
    return false;
  }
  if (chatThread.length >= MAX_CHAT_MESSAGES) {
    chatStatus("Bu sohbet doldu (en fazla 12 tur). Soldaki \"Yeni sohbet\" ile devam et.");
    return false;
  }
  const total = chatThread.reduce((n, m) => n + m.content.length, 0) + message.length;
  if (total > MAX_CHAT_TOTAL_CHARS) {
    chatStatus("Sohbet çok uzadı — soldaki \"Yeni sohbet\" ile devam et. (Son prompt'u "
      + "kaybetmemek için önce \"Forma aktar\"a bas.)");
    return false;
  }

  chatThread.push({ role: "user", content: message });
  const bubble = appendUser(message);
  input.value = "";
  chatStatus("");
  setChatBusy(true);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatThread }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const { content, finish_reason } = await res.json();
    chatThread.push({ role: "assistant", content });
    appendBot(content);
    lockStaleOptions();
    chatStatus(finish_reason === "length"
      ? "Yanıt uzunluk sınırında kesilmiş olabilir — kısa bir brief'le tekrar dene." : "");
    // Kaydetme EN SONDA ve turu düşürmüyor: başarısız olursa yanıt ekranda kalır
    // ve durum satırı bunu söyler (bkz. persistThread).
    await persistThread();
    return true;
  } catch (e) {
    // BAŞARISIZ TUR GEÇMİŞTE KALMAZ: kalsaydı her yeniden gönderim aynı hatayı
    // tekrarlardı. Mesaj kaybolmasın diye girdiye geri konuyor.
    chatThread.pop();
    bubble.remove();
    input.value = message;
    syncEmptyState();
    chatStatus(e.message);
    return false;
  } finally {
    setChatBusy(false);
  }
}

// ── Kayıtlı sohbetler (kenar panel) ─────────────────────────────────
// Kalıcılık SUNUCUDA: `desktop.py` pencereyi pywebview'ın private mode
// varsayılanıyla açıyor ve orada localStorage her kapanışta silinir — paketli
// .app'te geçmiş sessizce buharlaşırdı.

async function chatApi(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(detailText(err) || `Hata (${res.status})`);
  }
  return res.json();
}

/** Başlık = ilk kullanıcı mesajı, kelime sınırında kısaltılmış. */
function deriveTitle() {
  const first = chatThread.find((m) => m.role === "user");
  const text = (first ? first.content : "").replace(/\s+/g, " ").trim();
  if (!text) return "Adsız sohbet";
  if (text.length <= CHAT_TITLE_CHARS) return text;
  const cut = text.slice(0, CHAT_TITLE_CHARS);
  const space = cut.lastIndexOf(" ");
  return `${space > 20 ? cut.slice(0, space) : cut}…`;
}

/** Sunucunun döndürdüğü kaydı panel listesine işler — İKİNCİ bir istek YOK.
 *
 * Eskiden her tur sonunda `loadChats()` çağrılıyordu: aynı chats.json'ı bir kez
 * yazıp hemen ardından gövdeleriyle birlikte baştan okumak demekti (sohbet
 * başına 60 bin karaktere kadar metin). Yazan istek zaten güncel kaydı
 * döndürüyor, liste ondan kurulabiliyor.
 *
 * Sıralama kuralı `chat_store.list_chats` ile AYNI olmak zorunda: `updated_at`
 * azalan. Damga ISO 8601, yani dizi karşılaştırması = zaman karşılaştırması.
 */
function upsertSummary(chat) {
  const summary = {
    id: chat.id,
    title: chat.title,
    created_at: chat.created_at,
    updated_at: chat.updated_at,
    message_count: (chat.messages || []).length,
  };
  // Dokunulan kayıt başa, sonra damgaya göre sırala: `sort` KARARLI olduğu için
  // eşit damgalı kayıtlarda az önce yazılan üstte kalır (kullanıcının içinde
  // olduğu sohbet), sunucunun "eşitlikte yeni olan başta" kuralıyla aynı yön.
  chatSummaries = [summary, ...chatSummaries.filter((c) => c.id !== summary.id)]
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  renderChatList();
}

function dropSummary(chatId) {
  chatSummaries = chatSummaries.filter((c) => c.id !== chatId);
  renderChatList();
}

async function persistThread() {
  try {
    const path = currentChatId ? `/api/chats/${currentChatId}` : "/api/chats";
    const method = currentChatId ? "PUT" : "POST";
    const body = currentChatId ? { messages: chatThread }
                               : { title: deriveTitle(), messages: chatThread };
    const { chat } = await chatApi(path, { method, body });
    currentChatId = chat.id;
    upsertSummary(chat);
  } catch (e) {
    // Tur DÜŞMÜYOR: yanıt ekranda ve bellekte duruyor, yalnız diske yazılamadı.
    // Sessiz geçilse kullanıcı sohbetin kaydedildiğini sanardı.
    chatStatus(`Sohbet kaydedilemedi (${e.message}) — yanıt ekranda duruyor.`);
  }
}

/** "14:32" (bugünse) ya da "5 Ağu" — panelde tek satır sığacak kadar kısa. */
function shortStamp(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

/** Açık menüyü kapatır ve ODAĞI TETİKLEYİCİYE geri verir.
 *
 * Odak iadesi olmadan `Escape`/dışa tıklama, kapanan katmanın içindeki odağı
 * `body`'ye düşürüyordu: klavye kullanıcısı listede yerini kaybediyor ve Tab'a
 * baştan başlıyordu. `document.activeElement` kontrolü şart — fare ile
 * kapatanın odağı zorla panele taşınmasın.
 */
function closeMenus() {
  const list = $("chat-list");
  const focusWasInMenu = document.activeElement
    && document.activeElement.closest && document.activeElement.closest(".chat-menu");
  const trigger = openMenuId
    ? list.querySelector(`.chat-item-menu[data-chat-id="${openMenuId}"]`) : null;
  openMenuId = null;
  for (const menu of list.querySelectorAll(".chat-menu")) menu.hidden = true;
  for (const btn of list.querySelectorAll(".chat-item-menu")) {
    btn.setAttribute("aria-expanded", "false");
  }
  if (focusWasInMenu && trigger) trigger.focus();
}

function chatMenu(summary) {
  const menu = document.createElement("div");
  menu.className = "chat-menu";
  menu.hidden = true;
  // `aria-haspopup="true"` tetikleyicide bir MENÜ vaat ediyor; rolleri
  // vermezsek ekran okuyucu iki düğmeli düz bir grup okur ve vaat tutulmaz.
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", `${summary.title || "Adsız sohbet"} — işlemler`);

  const rename = document.createElement("button");
  rename.type = "button";
  rename.className = "chat-menu-item";
  rename.setAttribute("role", "menuitem");
  rename.textContent = "Yeniden adlandır";
  rename.addEventListener("click", () => { closeMenus(); renameChat(summary); });

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "chat-menu-item chat-menu-danger";
  remove.setAttribute("role", "menuitem");
  remove.textContent = "Sil";
  remove.addEventListener("click", () => { closeMenus(); deleteChat(summary); });

  menu.append(rename, remove);
  return menu;
}

function chatItem(summary) {
  const li = document.createElement("li");
  li.className = "chat-item";
  if (summary.id === currentChatId) {
    li.classList.add("active");
    li.setAttribute("aria-current", "true");
  }

  const open = document.createElement("button");
  open.type = "button";
  open.className = "chat-item-open";
  const title = document.createElement("span");
  title.className = "chat-item-title";
  title.textContent = summary.title || "Adsız sohbet";
  const meta = document.createElement("span");
  meta.className = "chat-item-meta";
  meta.textContent = shortStamp(summary.updated_at);
  open.append(title, meta);
  open.addEventListener("click", () => openChat(summary.id));

  const menuBtn = document.createElement("button");
  menuBtn.type = "button";
  menuBtn.className = "chat-item-menu";
  menuBtn.setAttribute("aria-haspopup", "true");
  menuBtn.setAttribute("aria-expanded", "false");
  menuBtn.setAttribute("aria-label", `${title.textContent} — işlemler`);
  menuBtn.dataset.chatId = summary.id;   // closeMenus odağı buraya geri veriyor
  menuBtn.title = "İşlemler";
  menuBtn.textContent = "⋯";

  const menu = chatMenu(summary);
  menuBtn.addEventListener("click", () => {
    const wasOpen = openMenuId === summary.id;
    closeMenus();
    if (wasOpen) return;            // aynı düğme ikinci tıklamada kapatır
    openMenuId = summary.id;
    menu.hidden = false;
    menuBtn.setAttribute("aria-expanded", "true");
    menu.querySelector(".chat-menu-item").focus();
  });

  li.append(open, menuBtn, menu);
  return li;
}

function renderChatList() {
  const list = $("chat-list");
  list.innerHTML = "";               // ← innerHTML yalnız BOŞ DİZEYLE
  for (const summary of chatSummaries) list.appendChild(chatItem(summary));
  $("chat-list-empty").hidden = chatSummaries.length > 0;
}

async function loadChats() {
  try {
    const { chats } = await chatApi("/api/chats");
    chatSummaries = chats;
    renderChatList();
  } catch {
    // Panel boş kalır ama sohbet ÇALIŞMAYA devam eder: liste bir kolaylık,
    // turun ön koşulu değil.
    $("chat-list-empty").hidden = false;
    $("chat-list-empty").textContent = "Sohbet listesi alınamadı.";
  }
}

function resetThread() {
  chatThread = [];
  currentChatId = null;
  $("chat-log").innerHTML = "";       // ← innerHTML yalnız BOŞ DİZEYLE
  chatStatus("");
  syncEmptyState();
}

function newChat() {
  if (chatBusy) { chatStatus("Yönetmen yanıtlıyor — bitmesini bekle."); return; }
  closeMenus();
  resetThread();
  renderChatList();                   // seçili işaret kalkar
  closeSidebarOnMobile();
  $("chat-input").focus();
}

async function openChat(chatId) {
  if (chatBusy) { chatStatus("Yönetmen yanıtlıyor — bitmesini bekle."); return; }
  closeMenus();
  if (chatId === currentChatId) { closeSidebarOnMobile(); return; }
  try {
    const { chat } = await chatApi(`/api/chats/${chatId}`);
    resetThread();
    currentChatId = chat.id;
    chatThread = chat.messages || [];
    for (const m of chatThread) {
      if (m.role === "user") appendUser(m.content); else appendBot(m.content);
    }
    // Eski turların seçenekleri BAYAT: yalnız son grup canlı kalır.
    lockStaleOptions();
    syncEmptyState();
    renderChatList();
    closeSidebarOnMobile();
    $("chat-input").focus();
  } catch (e) {
    chatStatus(`Sohbet açılamadı: ${e.message}`);
  }
}

async function renameChat(summary) {
  const name = await promptDialog("Sohbeti yeniden adlandır",
    "Kenar panelinde görünecek ad.", { okLabel: "Kaydet", initial: summary.title || "" });
  if (name === null) return;
  try {
    const { chat } = await chatApi(`/api/chats/${summary.id}`,
                                   { method: "PUT", body: { title: name } });
    upsertSummary(chat);              // dönen kayıt yeter, listeyi baştan çekme
  } catch (e) {
    chatStatus(`Yeniden adlandırılamadı: ${e.message}`);
  }
}

async function deleteChat(summary) {
  const ok = await confirmDialog("Sohbeti sil",
    `"${summary.title || "Adsız sohbet"}" kalıcı olarak silinecek. Bu işlem geri alınamaz.`,
    { okLabel: "Sil" });
  if (!ok) return;
  try {
    await chatApi(`/api/chats/${summary.id}`, { method: "DELETE" });
    // Açık sohbet silindiyse ekranda bırakmak yanıltıcı olurdu: bir sonraki tur
    // 404 alır ve kullanıcı "kaydedilmiyor" sanır.
    if (summary.id === currentChatId) resetThread();
    dropSummary(summary.id);
  } catch (e) {
    chatStatus(`Silinemedi: ${e.message}`);
  }
}

// Dar ekranda panel bir çekmece (CSS 900px altında üstüne biniyor).
function closeSidebarOnMobile() {
  $("chat-sidebar").classList.remove("open");
  $("chat-sidebar-toggle").setAttribute("aria-expanded", "false");
}

// ── Dinleyiciler ────────────────────────────────────────────────────

$("chat-send").addEventListener("click", sendChat);
$("chat-new").addEventListener("click", newChat);
$("chat-input").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); sendChat(); }
});

$("chat-sidebar-toggle").addEventListener("click", () => {
  const open = $("chat-sidebar").classList.toggle("open");
  $("chat-sidebar-toggle").setAttribute("aria-expanded", open ? "true" : "false");
});

// Menü dışına tıklama ve Escape kapatır. `#confirm-modal` açıkken core.js'in
// Escape dinleyicisi stopImmediatePropagation çağırıyor — bu handler o
// dosyadan SONRA kayıtlı olduğu için diyalogun Escape'i buraya sızmıyor.
document.addEventListener("click", (e) => {
  if (openMenuId && !e.target.closest(".chat-item")) closeMenus();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && openMenuId) closeMenus();
});

for (const chip of document.querySelectorAll(".chat-chip")) {
  chip.addEventListener("click", () => {
    $("chat-input").value = chip.textContent.trim();
    $("chat-input").focus();
  });
}

// core.js'in sekme dinleyicisi ÖNCE kayıtlı → buraya gelindiğinde görünüm
// zaten değişmiş oluyor. Burada yalnızca sohbete özel açılış işi var: eldeki
// prompt taslağını brainstorm'a çevirmek.
$("tab-chat").addEventListener("click", () => {
  if (!chatThread.length && !$("chat-input").value.trim()) {
    const draft = $("prompt").value.trim();
    if (draft) $("chat-input").value = draft;
  }
  $("chat-input").focus();
});

syncEmptyState();
loadChats();
