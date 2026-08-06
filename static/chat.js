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
const MAX_CHAT_DISPLAY_CHARS = 400;  // models.MAX_CHAT_DISPLAY_CHARS

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
  // Görünür karşılığı OLAN bloklar çizilmez: seçenek, varyasyon ve parametre
  // bloklarının karşılığı tıklanabilir çipler (renderOptions / renderVariations /
  // renderParameters). Atlanmasalar kullanıcı ham JSON okurdu.
  //
  // Ayar JSON'u listede YOK ve çizilmeye devam ediyor (bilinçli): kullanıcının
  // "Forma aktar"a basmadan da hangi boyut/kalite önerildiğini görmesi gerekiyor.
  // Tanınmayan bir JSON bloğu da çizilir — dürüst sonuç: yönetmen anlaşılmayan
  // bir şey yazdıysa kullanıcı onu görsün.
  //
  // ⚠️ Atlama koşulu "blok VAR" değil "**panel GERÇEKTEN çizilecek**": varyasyon
  // ve parametre panelleri sözleşmeye uymayan maddelerde `null` dönüyor. İkisi
  // ayrıştığında blok ne panel ne kod bloğu olarak görünüyordu, yani sessizce
  // kayboluyordu — üstteki dürüstlük kuralının tam tersi. Süzgeç bu yüzden
  // `variationItems`/`axisItems` ile PAYLAŞILIYOR.
  const skip = new Set([
    parsed.optionsBody,
    variationItems(parsed).length ? parsed.variationsBody : "",
    axisItems(parsed).length ? parsed.parametersBody : "",
  ].filter(Boolean));
  let list = null;
  for (let i = 0; i < lines.length; i++) {
    const fence = FENCE.exec(lines[i]);
    if (fence) {
      list = null;
      const body = [];
      i++;
      while (i < lines.length && !FENCE.test(lines[i])) body.push(lines[i++]);
      const joined = body.join("\n");
      if (skip.has(joined.trim())) continue;
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
//
// Fence ETİKETİ hiçbir yerde yük taşımıyor (```json / ```variations yalnızca
// belge): tip dört imzadan okunuyor ve imzalar ayrık. Dallar bilerek bu
// fonksiyonun İÇİNDE — tests/test_index.py imzaları buranın gövdesinden greple
// arıyor, modül düzeyi bir tabloya taşımak o tripwire'ı düşürürdü.
const SETTING_KEYS = ["size", "quality", "n"];

/** → { prompt, settings, options, variations, parameters, *Body }.
 *
 * Prompt adaylığı kuralı v1.16'da DEĞİŞTİ: JSON nesnesi olarak ayrıştırılan HER
 * blok adaylıktan düşüyor. Eskiden yalnız ayar ve seçenek blokları elle
 * dışlanıyordu; varyasyon/parametre blokları eklenince kural şöyle kırılıyordu —
 * promptlar KISALDIĞI için (v1.16'nın diğer hedefi) varyasyon JSON'u "en uzun
 * blok" olabiliyor, `applyToForm` da onu forma yazıyordu. Kırılma sessiz: düğme
 * çalışıyor, yalnız yanlış metni aktarıyor.
 *
 * Kural neden GÜVENLİ: gpt-image-2 prompt'u akıcı İngilizce prozadır, hiçbir
 * zaman JSON nesnesi olamaz. Biçimi kaymış (ayrıştırılamayan) blok `null`
 * döndüğü için aday KALMAYA DEVAM EDİYOR — mevcut ve doğru davranış. Yan kazanç:
 * modelin uydurduğu tanınmayan bir JSON bloğu da artık prompt sanılamıyor.
 */
function parseDirectorReply(text) {
  const blocks = fencedBlocks(text);
  const jsonBlocks = new Set();
  let settings = null;
  let settingsBlock = null;
  let options = null;
  let optionsBlock = null;
  let variations = null;
  let variationsBlock = null;
  let parameters = null;
  let parametersBlock = null;

  for (const b of blocks) {
    const obj = jsonObject(b);
    if (!obj) continue;
    jsonBlocks.add(b);
    if (!settings && SETTING_KEYS.some((k) => obj[k] !== undefined)) {
      settings = obj;
      settingsBlock = b;
      continue;
    }
    if (!options && Array.isArray(obj.secenekler) && obj.secenekler.length) {
      options = obj;
      optionsBlock = b;
      continue;
    }
    if (!variations && Array.isArray(obj.varyasyonlar) && obj.varyasyonlar.length) {
      variations = obj;
      variationsBlock = b;
      continue;
    }
    // `secenekler` parametre bloğunda EKSENİN İÇİNDE, üst düzeyde değil — bu
    // yüzden yukarıdaki seçenek dalı bu bloğa yanılıp el koymuyor.
    if (!parameters && Array.isArray(obj.eksenler) && obj.eksenler.length) {
      parameters = obj;
      parametersBlock = b;
    }
  }

  const candidates = blocks.filter((b) => b.body && !jsonBlocks.has(b));
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
    variations,
    variationsBody: variationsBlock ? variationsBlock.body : "",
    parameters,
    parametersBody: parametersBlock ? parametersBlock.body : "",
  };
}

// ── Tıklanabilir seçenekler ─────────────────────────────────────────
// Yönetmen soruyu prozada da soruyor; buradaki çipler onun makine tarafı.
// Serbest yazı alanı HER ZAMAN var: "bunların hiçbiri değil" cevabı bir
// seçenek olarak listelenemez (talimat dosyası "diğer" yazmayı da yasaklıyor).

const OPTION_MAX = 8;                // savunma: model uzun bir liste döndürürse
const VARIATION_MAX = 4;
const AXIS_MAX = 6;
const OPTION_JOIN = " · ";

/** Üç panelin de kökü. Sınıf `.chat-options` PAYLAŞILIYOR ve bu bir gereklilik:
 *
 * `lockStaleOptions` grupları o sınıfla buluyor. Yeni paneller başka bir kök
 * sınıf kullansa test yine GEÇERDİ ama davranış sessizce bozulurdu — yeniden
 * açılan bir sohbette eski varyasyon düğmeleri sonsuza dek canlı kalır ve
 * kullanıcı artık var olmayan bir prompt'a delta gönderirdi. Odak halkası ve
 * `.chat-options-done` da aynı sınıftan geliyor.
 */
function answerGroup(label, { radio = false } = {}) {
  const group = document.createElement("div");
  group.className = "chat-options";
  group.setAttribute("role", radio ? "radiogroup" : "group");
  group.setAttribute("aria-label", label);
  return group;
}

/** Seçilebilir çip. `scope` = DIŞLAYICILIK kapsamı, panelin kendisi olmak
 * zorunda değil: parametre panelinde eksen SATIRI geçiliyor, böylece "eksen içi
 * tek seçim, eksenler birbirinden bağımsız" semantiği bedavaya geliyor. */
function optionChip(label, multi, scope) {
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
      for (const other of scope.querySelectorAll(".chat-option")) {
        other.setAttribute("aria-checked", "false");
      }
    }
    chip.setAttribute("aria-checked", on ? "false" : "true");
  });
  return chip;
}

/** Varyasyon düğmesi. `role="checkbox"`/`aria-checked` BİLEREK YOK: varyasyon bir
 * EYLEM, açılıp kapanan bir anahtar değil — işaretlenmemiş bir onay kutusu diye
 * duyurmak ekran okuyucuya yalan söylemek olurdu. */
function actionChip(label) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chat-option chat-variation";
  chip.textContent = label;          // ← model metni: yalnızca textContent
  return chip;
}

function pickedLabels(scope) {
  return [...scope.querySelectorAll(".chat-option")]
    .filter((c) => c.getAttribute("aria-checked") === "true")
    .map((c) => c.textContent);
}

/** Serbest yazı alanı: etiket + input. Düğme YOK — her panel kendi düğmesini
 * kuruyor, çünkü etiketi ("Devam et" / "Uygula") ve boş-durum mesajı farklı. */
function ownField(labelText, placeholder) {
  const own = document.createElement("div");
  own.className = "chat-own";
  const label = document.createElement("label");
  label.className = "chat-own-label";
  label.textContent = labelText;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "chat-own-input";
  input.maxLength = MAX_CHAT_MSG_CHARS;
  input.placeholder = placeholder;
  const id = `chat-own-${Math.random().toString(36).slice(2, 8)}`;
  input.id = id;
  label.htmlFor = id;
  own.append(label, input);
  return { own, input };
}

function ownText(group) {
  const input = group.querySelector(".chat-own-input");
  return input ? input.value.trim() : "";
}

/** → { content, display }. `content` modele gider, `display` akışa çizilir.
 *
 * İkisi AYRI çünkü v1.15'te aynıydı: birleştirilmiş `"Instagram karesi · Blog
 * kapağı"` dizesi normal bir kullanıcı baloncuğu olarak çiziliyordu ve kullanıcı
 * onu kendi yazdığı bir replik sanıyordu. Artık `content` modele, `display` ise
 * sessiz bir "seçim" piline gidiyor.
 *
 * Yalnız serbest metin girildiyse `display` BOŞ: o cümleyi kullanıcı gerçekten
 * yazdı, baloncuk olarak kalması doğru. Pil makine tarafından kurulan turlara ait.
 */
function optionsValue(group) {
  const picked = pickedLabels(group);
  const own = ownText(group);
  if (!picked.length && !own) return { content: "", display: "" };
  const joined = picked.join(OPTION_JOIN);
  if (!picked.length) return { content: own, display: "" };
  return { content: own ? `${joined}\n${own}` : joined,
           display: own ? `${joined}${OPTION_JOIN}${own}` : joined };
}

/** Parametre panelinin değeri. Türkçe iskelet İSTEMCİDE sabit; modelden yalnızca
 * eksen adı ve İngilizce ifade geliyor.
 *
 * Kapanış cümlesi ("geri kalanını aynı tut") süs değil: personanın 6. adım
 * disiplinini makine turuna da uyguluyor, yoksa tek bir ışık değişikliği bütün
 * prompt'u yeniden yazdırabilir.
 *
 * `display` BURADA hiç eksen seçilmese de doluyor ve bu, `optionsValue`'dan
 * BİLEREK ayrılıyor. Ayrımın ölçüsü "kullanıcı seçim mi yaptı" değil, **turu kim
 * yazdı**: seçenek panelinde serbest metin modele AYNEN gidiyor (tur kullanıcının,
 * baloncuk doğru), burada ise iskelet + kapanış cümlesi istemci tarafından
 * ekleniyor. `display: ""` bırakılsaydı `appendUser` baloncuğa düşer ve kullanıcı
 * akışta kendi yazmadığı bir cümleyi ("… Prompt'un geri kalanını aynı tut.")
 * kendi repliği olarak görürdü — v1.16'nın pili getirme sebebi tam olarak bu
 * yanlış atıftı. Pilde yalnız kullanıcının yazdığı metin görünüyor; makine
 * iskeleti `content`'te kalıyor, yani görünmüyor.
 */
function axesValue(group) {
  const parts = [];
  const shown = [];
  for (const row of group.querySelectorAll(".chat-axis")) {
    const picked = pickedLabels(row);
    if (!picked.length) continue;
    const name = row.dataset.axis || "";
    parts.push(`${name} → ${picked[0]}`);
    shown.push(`${name}: ${picked[0]}`);
  }
  const own = ownText(group);
  if (!parts.length && !own) return { content: "", display: "" };
  const sentence = parts.length
    ? `Şu parametreleri değiştir: ${parts.join("; ")}.` : "";
  // Kullanıcı noktalama koymadıysa biz koyuyoruz: yoksa serbest metin ile
  // kapanış cümlesi tek cümleye yapışıyor ("zemin daha sade Prompt'un geri
  // kalanını aynı tut") ve model sınırın nerede olduğunu tahmin etmek zorunda.
  const idea = own && !/[.!?…]$/.test(own) ? `${own}.` : own;
  const content = [sentence, idea, "Prompt'un geri kalanını aynı tut."]
    .filter(Boolean).join(" ");
  // Eksen seçilmedi: `shown` boş, o yüzden aşağıdaki birleştirme kullanılamaz
  // (başa sarkan bir ayraç üretirdi). Pilde kullanıcının yazdığı metin duruyor.
  if (!parts.length) return { content, display: own };
  return { content, display: own ? `${shown.join(OPTION_JOIN)}${OPTION_JOIN}${own}`
                                 : shown.join(OPTION_JOIN) };
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
  const multi = spec.coklu !== false;
  const group = answerGroup(String(spec.soru || "Seçenekler"), { radio: !multi });

  if (spec.soru) {
    const q = document.createElement("p");
    q.className = "chat-options-q";
    q.textContent = String(spec.soru);
    group.appendChild(q);
  }

  const chips = document.createElement("div");
  chips.className = "chat-options-chips";
  for (const raw of spec.secenekler.slice(0, OPTION_MAX)) {
    chips.appendChild(optionChip(String(raw), multi, group));
  }
  group.appendChild(chips);

  const { own, input } = ownField("Bunlardan biri değilse kendi fikrini yaz",
                                 "Kendi fikrim…");
  const send = document.createElement("button");
  send.type = "button";
  send.className = "primary chat-own-send";
  send.textContent = "Devam et";

  const submit = async () => {
    const { content, display } = optionsValue(group);
    if (!content) { chatStatus("Bir seçenek seç ya da kendi fikrini yaz."); return; }
    // Gönderim TEK yoldan: sınır kapıları, hata geri alma ve kaydetme
    // sendChat'te yaşıyor; ikinci bir gönderim yolu yazılmıyor.
    $("chat-input").value = content;
    if (await sendChat(display)) lockOptions(group);
  };
  send.addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); submit(); }
  });

  own.appendChild(send);
  group.appendChild(own);
  return group;
}

// ── Varyasyonlar ve ayarlanabilir parametreler (v1.16) ───────────────
// v1.15'te ikisi de PROZA listesiydi: kullanıcı okuyup prompt'u ELLE
// düzenlemek zorundaydı. Artık makine bloğundan çiplere dönüyorlar.
//
// Varyasyon tıklaması prompt'u YERELDE DEĞİŞTİRMİYOR, yönetmene tek turluk bir
// istek gönderiyor. Sebep: varyasyonlar `x → y` çifti değil cümle düzeyi
// düzenlemeler ("photorealistic + doku + derinlik cümlelerini kaldır"), yani
// yerel bir metin değiştirme eşleşme tutmadığında SESSİZCE yanlış prompt
// üretirdi — kod tabanının duruşu bunu yasaklıyor (bkz. applyToForm'un kırpma
// reddi). Resmî gpt-image-2 kılavuzu da aynı yolu öneriyor: "start with a clean
// base prompt and refine with small, single-change follow-ups".

/** Sözleşmeye uyan varyasyon maddeleri (yoksa boş dizi).
 *
 * Süzgeç PAYLAŞILAN bir fonksiyon çünkü iki yer AYNI soruyu soruyor: paneli çizen
 * `renderVariations` ve bloğu ham JSON olarak çizmeyi atlayan `renderMarkdownInto`.
 * Ayrı yazıldıklarında sessiz bir kayıp doğuyordu — sözleşmeye uymayan bir blok
 * (örn. `istek` alanı düşmüş) panel olarak çizilmiyor AMA atlama kümesinde
 * olduğu için kod bloğu olarak da çizilmiyordu, yani kullanıcı **hiçbir şey**
 * görmüyordu. Tek kaynak olduğu için artık ikisi ayrışamıyor: madde geçerliyse
 * panel çizilir, değilse blok ham JSON olarak görünür.
 */
function variationItems(parsed) {
  if (!parsed.variations) return [];
  return parsed.variations.varyasyonlar
    .filter((v) => v && typeof v.ad === "string" && typeof v.istek === "string"
                   && v.ad.trim() && v.istek.trim())
    .slice(0, VARIATION_MAX);
}

/** Sözleşmeye uyan eksenler (yoksa boş dizi). Bkz. `variationItems`. */
function axisItems(parsed) {
  if (!parsed.parameters) return [];
  return parsed.parameters.eksenler
    .filter((e) => e && typeof e.ad === "string" && e.ad.trim()
                   && Array.isArray(e.secenekler) && e.secenekler.length)
    .slice(0, AXIS_MAX);
}

function renderVariations(parsed) {
  const items = variationItems(parsed);
  if (!items.length) return null;      // eksik alanlı blok: panel hiç çizilmez

  const group = answerGroup("Varyasyonlar");
  group.classList.add("chat-variations");
  const q = document.createElement("p");
  q.className = "chat-options-q";
  // Başlığı İSTEMCİ yazıyor: model prozada tekrarlamasın diye (yanıt uzunluğu).
  q.textContent = "Varyasyonlar — birine tıkla, yönetmen prompt'u ona göre yazsın";
  group.appendChild(q);

  const chips = document.createElement("div");
  chips.className = "chat-options-chips";
  for (const item of items) {
    const ad = item.ad.trim();
    const chip = actionChip(ad);
    chip.addEventListener("click", async () => {
      $("chat-input").value = `"${ad}" varyasyonunu uygula: ${item.istek.trim()}`;
      if (await sendChat(`Varyasyon: ${ad}`)) lockOptions(group);
    });
    chips.appendChild(chip);
  }
  group.appendChild(chips);
  return group;
}

function renderParameters(parsed) {
  const axes = axisItems(parsed);
  if (!axes.length) return null;

  const group = answerGroup("Ayarlanabilir parametreler");
  group.classList.add("chat-axes");
  const q = document.createElement("p");
  q.className = "chat-options-q";
  q.textContent = "Ayarlanabilir parametreler — seç ya da kendi fikrini yaz";
  group.appendChild(q);

  for (const axis of axes) {
    const name = axis.ad.trim();
    const row = document.createElement("div");
    row.className = "chat-axis";
    // Eksen SATIRI kendi radyo grubu: eksen içinde tek seçim, eksenler
    // birbirinden bağımsız. `dataset.axis` axesValue'nun okuduğu ad.
    row.setAttribute("role", "radiogroup");
    row.setAttribute("aria-label", name);
    row.dataset.axis = name;

    const label = document.createElement("span");
    label.className = "chat-axis-name";
    label.textContent = name;
    row.appendChild(label);

    if (typeof axis.simdi === "string" && axis.simdi.trim()) {
      // Takas edilen değer GÖRÜNÜR olmalı ama tıklanabilir GÖRÜNMEMELİ:
      // o yüzden çip değil kod rozeti.
      const now = document.createElement("span");
      now.className = "chat-axis-now";
      now.textContent = axis.simdi.trim();
      row.appendChild(now);
    }

    const chips = document.createElement("div");
    chips.className = "chat-options-chips";
    for (const raw of axis.secenekler.slice(0, OPTION_MAX)) {
      chips.appendChild(optionChip(String(raw), false, row));
    }
    row.appendChild(chips);
    group.appendChild(row);
  }

  const { own, input } = ownField("Listede yoksa kendi fikrini yaz",
                                  "Örn. arka plan daha sade olsun…");
  const send = document.createElement("button");
  send.type = "button";
  send.className = "primary chat-own-send";
  send.textContent = "Uygula";

  const submit = async () => {
    const { content, display } = axesValue(group);
    if (!content) { chatStatus("Bir parametre seç ya da kendi fikrini yaz."); return; }
    $("chat-input").value = content;
    if (await sendChat(display)) lockOptions(group);
  };
  send.addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); submit(); }
  });

  own.appendChild(send);
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

/** Kullanıcı turu. `msg.display` VARSA baloncuk değil sessiz bir "seçim" pili.
 *
 * v1.15'te çip seçimleri `" · "` ile birleştirilip normal baloncuk olarak
 * çiziliyordu ve kullanıcı o metni kendi yazdığı bir replik sanıyordu. Ayrım
 * MESAJIN İÇİNDE taşınıyor (models.ChatMessage.display), istemcide ayrı bir
 * durumda değil: `openChat` sohbeti `chatThread`'den yeniden çiziyor, yani
 * işaret mesajda olmasa kaydedilmiş bir sohbet açıldığında piller baloncuğa
 * dönerdi.
 *
 * Elle yazılan tur `display` ALMIYOR ve baloncuk olarak kalıyor — o cümleyi
 * kullanıcı gerçekten yazdı.
 */
function appendUser(msg) {
  const div = document.createElement("div");
  if (msg.display) {
    div.className = "chat-pick";
    const tag = document.createElement("span");
    tag.className = "chat-pick-tag";
    // Gerçek bir eleman, CSS `content` DEĞİL: ekran okuyucu etiketi güvenilir
    // biçimde okusun.
    tag.textContent = "Seçim";
    const text = document.createElement("span");
    text.textContent = msg.display;   // ← model metni: yalnızca textContent
    div.append(tag, text);
  } else {
    div.className = "chat-msg-user";
    div.textContent = msg.content;
  }
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
  // Paneller mesajın SONUNDA: okuma sırası prompt → ayarlar → "Sonraki adım"
  // cümlesi → varyasyonlar → parametreler. Her biri null dönebilir (blok eksik
  // ya da içi bozuk) — o durumda panel hiç çizilmiyor, hata verilmiyor.
  if (parsed.options) div.appendChild(renderOptions(parsed));
  if (parsed.variations) {
    const panel = renderVariations(parsed);
    if (panel) div.appendChild(panel);
  }
  if (parsed.parameters) {
    const panel = renderParameters(parsed);
    if (panel) div.appendChild(panel);
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

/** → true yalnızca tur BAŞARIYLA tamamlandıysa (seçenek grubu buna göre kilitlenir).
 *
 * `display` = akışa çizilecek kısa etiket; verilirse mesaj baloncuk değil pil
 * olarak görünür (bkz. appendUser). Boş bırakılırsa kullanıcının elle yazdığı
 * normal bir tur.
 */
async function sendChat(display = "") {
  if (chatBusy) return false;
  const input = $("chat-input");
  const message = input.value.trim();
  // Etiket de kapıdan geçiyor: sunucu `MAX_CHAT_DISPLAY_CHARS` ile reddeder ve
  // hata İngilizce pydantic metni olurdu. Satır sonu pilde işe yaramaz.
  const label = display
    ? display.replace(/\s+/g, " ").trim().slice(0, MAX_CHAT_DISPLAY_CHARS) : "";
  if (!message) { chatStatus("Önce bir mesaj yaz."); return false; }
  if (message.length > MAX_CHAT_MSG_CHARS) {
    chatStatus(`Mesaj çok uzun (${message.length}/${MAX_CHAT_MSG_CHARS} karakter).`);
    return false;
  }
  if (chatThread.length >= MAX_CHAT_MESSAGES) {
    chatStatus("Bu sohbet doldu (en fazla 12 tur). Soldaki \"Yeni sohbet\" ile devam et.");
    return false;
  }
  // Toplam, sunucunun `models._check_chat_total` ile AYNI şeyi sayıyor:
  // `content` + `display`. Ayrışsalar istemci sınırın dibinde geçen bir turu
  // gönderir ve sunucu 422 ile geri çevirirdi.
  const used = chatThread.reduce(
    (n, m) => n + m.content.length + (m.display || "").length, 0);
  if (used + message.length + label.length > MAX_CHAT_TOTAL_CHARS) {
    chatStatus("Sohbet çok uzadı — soldaki \"Yeni sohbet\" ile devam et. (Son prompt'u "
      + "kaybetmemek için önce \"Forma aktar\"a bas.)");
    return false;
  }

  const turn = { role: "user", content: message };
  if (label) turn.display = label;
  chatThread.push(turn);
  const bubble = appendUser(turn);
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
    // tekrarlardı. Mesaj kaybolmasın diye girdiye geri konuyor — ama YALNIZCA
    // kullanıcının kendi yazdığı turda. Çip turunda grup kilitlenmemiş oluyor
    // (sendChat false döndü), yani tıklama zaten tekrarlanabilir; yönetmenin uzun
    // Türkçe delta cümlesini besteciye dökmek tam olarak kaldırılan çirkinliği
    // geri getirirdi.
    chatThread.pop();
    bubble.remove();
    if (!label) input.value = message;
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
      // Mesaj NESNESİ geçiliyor, `content` değil: pil/baloncuk ayrımı
      // `m.display`'de yaşıyor ve yeniden açılışta da aynı kalması gerekiyor.
      if (m.role === "user") appendUser(m); else appendBot(m.content);
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

// ⚠️ SARMALAYICI ZORUNLU. `("click", sendChat)` yazılsa tarayıcı `MouseEvent`'i
// birinci argüman olarak geçirir ve o da `sendChat(display)` olur: pilde
// "[object MouseEvent]" görünür ve o dize `display` alanı olarak SUNUCUYA gider.
// Tek karakterlik bir sadeleştirmenin bedeli bu; tripwire testi de var.
$("chat-send").addEventListener("click", () => sendChat());
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
