// GPT-Image Studio — Prompt Yönetmeni: Türkçe sohbet → İngilizce gpt-image-2 prompt'u.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js → viewer.js → chat.js
//
// Bu dosya EN SONDA: bir YAPRAK, yalnızca kendinden önce tanımlanan adlara
// bakıyor ($, statusEl, detailText, confirmDialog, showView, MAX_PROMPT_CHARS).
// Sekme geçişinin kendisi core.js'te (kabuk sorumluluğu), burada değil.
//
// GÜVENLİK DURUŞU: sunucudan/modelden gelen metin DOM'a yalnızca `textContent`
// ile girer (renderExtras ile aynı duruş). `innerHTML` bu dosyada tek bir yerde,
// akışı BOŞ DİZEYLE temizlemek için kullanılıyor.

// Sunucudaki models.py sınırlarının aynası. İstemci kapısı olmadan sınır aşımı
// pydantic'in İNGİLİZCE 422 metniyle geri dönerdi.
const MAX_CHAT_MESSAGES = 24;        // models.MAX_CHAT_MESSAGES
const MAX_CHAT_MSG_CHARS = 6000;     // models.MAX_CHAT_MSG_CHARS
const MAX_CHAT_TOTAL_CHARS = 60000;  // models.MAX_CHAT_TOTAL_CHARS

// Sohbet geçmişi YALNIZCA burada yaşar; diske yazılmaz (karar 4). Kayıp riski
// "Sohbeti temizle"nin onay penceresiyle kapatılıyor.
let chatThread = [];
let chatBusy = false;

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

function renderMarkdownInto(host, text, promptBody) {
  const lines = text.split("\n");
  let list = null;
  for (let i = 0; i < lines.length; i++) {
    const fence = FENCE.exec(lines[i]);
    if (fence) {
      list = null;
      const body = [];
      i++;
      while (i < lines.length && !FENCE.test(lines[i])) body.push(lines[i++]);
      const pre = codeBlock(body.join("\n"), fence[1] || "");
      // Sayfadaki asıl ürün prompt bloğu: akışta gözle bulunabilmeli.
      if (promptBody && body.join("\n").trim() === promptBody) {
        pre.classList.add("chat-prompt-block");
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

/** → { prompt, settings }. Biçim kayarsa SESSİZCE boş dönmez, en iyi adayı seçer. */
function parseDirectorReply(text) {
  const blocks = fencedBlocks(text);
  let settings = null;
  let settingsBlock = null;
  for (const b of blocks) {
    if (b.lang !== "json" && !b.body.startsWith("{")) continue;
    try {
      const parsed = JSON.parse(b.body);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        settings = parsed;
        settingsBlock = b;
        break;
      }
    } catch { /* biçimi kaymış blok: prompt adayı olarak kalsın */ }
  }
  const candidates = blocks.filter((b) => b !== settingsBlock && b.body);
  let promptBlock = candidates.find((b) => /PROMPT/i.test(b.heading));
  if (!promptBlock) {
    // Başlık kayarsa en UZUN blok: yönetmenin prozası her zaman en uzundur.
    promptBlock = candidates.reduce(
      (best, b) => (!best || b.body.length > best.body.length ? b : best), null);
  }
  return { prompt: promptBlock ? promptBlock.body : "", settings };
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

  renderMarkdownInto(div, text, parsed.prompt);

  if (parsed.prompt) {
    const actions = document.createElement("div");
    actions.className = "chat-msg-actions";

    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "primary";
    apply.textContent = "Forma aktar (prompt + ayarlar)";
    apply.addEventListener("click", () => applyToForm(parsed));

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "btn-ghost";
    copy.textContent = "Prompt'u kopyala";
    copy.addEventListener("click", () => copyPrompt(parsed.prompt));

    actions.appendChild(apply);
    actions.appendChild(copy);
    div.appendChild(actions);
  }

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

async function sendChat() {
  if (chatBusy) return;
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) { chatStatus("Önce bir mesaj yaz."); return; }
  if (message.length > MAX_CHAT_MSG_CHARS) {
    chatStatus(`Mesaj çok uzun (${message.length}/${MAX_CHAT_MSG_CHARS} karakter).`);
    return;
  }
  if (chatThread.length >= MAX_CHAT_MESSAGES) {
    chatStatus("Bu sohbet doldu (en fazla 12 tur). \"Sohbeti temizle\" ile yeni bir sohbet başlat.");
    return;
  }
  const total = chatThread.reduce((n, m) => n + m.content.length, 0) + message.length;
  if (total > MAX_CHAT_TOTAL_CHARS) {
    chatStatus("Sohbet çok uzadı — yeni bir sohbet başlat. (Son prompt'u kaybetmemek "
      + "için önce \"Forma aktar\"a bas.)");
    return;
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
    chatStatus(finish_reason === "length"
      ? "Yanıt uzunluk sınırında kesilmiş olabilir — kısa bir brief'le tekrar dene." : "");
  } catch (e) {
    // BAŞARISIZ TUR GEÇMİŞTE KALMAZ: kalsaydı her yeniden gönderim aynı hatayı
    // tekrarlardı. Mesaj kaybolmasın diye girdiye geri konuyor.
    chatThread.pop();
    bubble.remove();
    input.value = message;
    syncEmptyState();
    chatStatus(e.message);
  } finally {
    setChatBusy(false);
  }
}

async function clearChat() {
  if (!chatThread.length) { $("chat-input").value = ""; return; }
  const ok = await confirmDialog("Sohbeti temizle",
    "Bu sohbetin tamamı silinecek. Sohbet diske kaydedilmiyor, geri alınamaz.",
    { okLabel: "Temizle" });
  if (!ok) return;
  chatThread = [];
  $("chat-log").innerHTML = "";   // ← innerHTML yalnız BOŞ DİZEYLE (core.js:renderExtras deseni)
  syncEmptyState();
  chatStatus("");
  $("chat-input").focus();
}

// ── Dinleyiciler ────────────────────────────────────────────────────

$("chat-send").addEventListener("click", sendChat);
$("chat-clear").addEventListener("click", clearChat);
$("chat-input").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); sendChat(); }
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
