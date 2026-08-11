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

function makeSvgIcon(dPath) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "13");
  svg.setAttribute("height", "13");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", dPath);
  svg.appendChild(path);
  return svg;
}

// Sunucudaki models.py sınırlarının aynası. İstemci kapısı olmadan sınır aşımı

// pydantic'in İNGİLİZCE 422 metniyle geri dönerdi.
const MAX_CHAT_MESSAGES = 24;        // models.MAX_CHAT_MESSAGES (yalnız KONUŞMA)
const MAX_CHAT_MSG_CHARS = 6000;     // models.MAX_CHAT_MSG_CHARS (KULLANICI mesajı)
const MAX_CHAT_TOTAL_CHARS = 60000;  // models.MAX_CHAT_TOTAL_CHARS
// Dökümün TOPLAM öğe sınırı (models.MAX_CHAT_ITEMS = MAX_CHAT_MESSAGES +
// MAX_CHAT_RESULTS). Sonuç kayıtları konuşma kotasını PAYLAŞMIYOR: paylaşsalardı
// üretim yapan bir oturum ~8 turda dolardı (§0.4/K4).
//
// ⚠️ `MAX_CHAT_RESULTS` BİLEREK aynalanmıyor: sunucu sonuç ADEDİNİ ayrıca
// kapamıyor, yalnız "konuşma ≤ 24" ve "toplam ≤ 48" diyor. İstemci burada 24'te
// durursa SUNUCUDAN KATI olur ve bu tam olarak düzeltilen hatanın kendisi —
// sohbetsiz bir oturum 24. üretimde sebepsiz kilitlenirdi.
const MAX_CHAT_ITEMS = 48;
// Üçüncü rol (models.RESULT_ROLE). Bu dize İKİ kapıda ve üç çizim dalında
// geçiyor — sabit olarak duruyor ki biri yanlış yazıldığında sessizce
// "konuşma mesajı" sayılmasın.
const RESULT_ROLE = "result";
// Yanıt sınırı (models.MAX_CHAT_REPLY_CHARS) BİLEREK aynalanmıyor: burada
// ölçülecek bir şey yok, gelen yanıtı sunucu zaten kapıda kesiyor. Aşağıdaki
// toplam kapısı da yanıt için yer AYIRMIYOR — kaydetme kapısı (models
// .MAX_CHAT_SAVE_TOTAL_CHARS) tam bir yanıt kadar geniş, yoksa sınırın dibinde
// geçen bir turun yanıtı hiç kaydedilemezdi.
// Başlık SUNUCUDA türetiliyor (v2.0 / `app._auto_title`) ve istemcideki
// `deriveTitle` bu yüzden kalktı: başlıksız yazım artık "bu otomatik kayıt"
// işareti (bkz. persistThread). Modele "bu sohbete isim ver" diye İKİNCİ bir
// çağrı hâlâ yapılmıyor — para ve gecikme, kazancı bir etiket. Beğenmeyen
// kullanıcı kebap menüsünden yeniden adlandırıyor.
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
  statusEl.textContent = text;
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
  // Devrin manşeti (tasarım §4.2): sekmeler bu düğme uğruna kaldırıldı — eski
  // etiketin vaat ettiği "diğer sekmeye git" yolculuğu ortadan kalkacaktı.
  // Ortada bir form da yok artık; tek composer var, düğme onun MODUNU söylüyor.
  apply.textContent = "Görsel modunda üret";
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
  // "Görsel modunda üret"e basmadan da hangi boyut/kalite önerildiğini görmesi gerekiyor.
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
    $("prompt").value = content;
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
      $("prompt").value = `"${ad}" varyasyonunu uygula: ${item.istek.trim()}`;
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
    $("prompt").value = content;
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
  // Programatik yazım `input` olayı DOĞURMAZ: ters yönün düğmesi elle
  // eşitlenmezse dolu kutunun yanında görünmez kalırdı.
  syncAskDirector();
  const skipped = [];
  for (const [key, selectId, label] of SETTING_TARGETS) {
    const value = parsed.settings ? parsed.settings[key] : undefined;
    if (value === undefined || value === null || value === "") continue;
    if (!applyIfSupported(selectId, value)) skipped.push(`${label} ${value}`);
  }

  setMode("image");
  $("prompt").focus();
  // Programatik `.value` ataması `change` olayını DOĞURMAZ: syncSpecs elle
  // çağrılmazsa üretim ayarları çipi eski değerleri göstermeye devam eder.
  syncSpecs();
  // SESSİZ SAPMA YASAK (palette applied:false ile aynı gerekçe): uygulanamayan
  // öneri açıkça söylenir, yoksa kullanıcı formda başka bir ayar görür ve
  // sonucu açıklayamaz.
  statusEl.textContent = "Prompt Görsel moduna aktarıldı."
    + (skipped.length ? ` Şu öneriler uygulanamadı: ${skipped.join(", ")}`
                        + " — üretim ayarlarındaki seçeneklerde yok." : "");
}

// ── Ters yön: "Yönetmen'e sor" (tasarım §4.2 · D13) ──────────────────

function syncAskDirector() {
  $("ask-director").hidden = !$("prompt").value.trim();
}

function askDirector() {
  setMode("director");
  $("prompt").focus();
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

// ── Sayım: iki kotanın tek kaynağı ──────────────────────────────────
// Sunucudaki `models._check_chat_counts` ile aynı ayrımı yapıyor. Ayrı ayrı
// `filter(...).length` yazılsa iki kapı zamanla ayrışırdı.
function conversationCount() {
  return chatThread.filter((m) => m.role !== RESULT_ROLE).length;
}

/** Konuşma kotası dolu mu (`models._check_chat_counts`'un aynası). */
function conversationIsFull() {
  return conversationCount() >= MAX_CHAT_MESSAGES;
}

/** `slots` öğe daha sığmıyor mu (`ChatSaveRequest.messages`'ın alan sınırı). */
function transcriptIsFull(slots) {
  return chatThread.length + slots > MAX_CHAT_ITEMS;
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
    const textSpan = document.createElement("span");
    textSpan.className = "chat-msg-text";
    textSpan.textContent = msg.content;
    div.appendChild(textSpan);
  }

  const actions = document.createElement("div");
  actions.className = "chat-bubble-actions";

  const restoreBtn = document.createElement("button");
  restoreBtn.type = "button";
  restoreBtn.className = "chat-action-btn";
  restoreBtn.title = "Metni düzenlemek üzere kutuya aktar";
  const editLabel = document.createElement("span");
  editLabel.textContent = "Düzenle";
  restoreBtn.append(makeSvgIcon("M9 14L4 9l5-5M20 20v-7a4 4 0 0 0-4-4H4"), editLabel);
  restoreBtn.addEventListener("click", () => {
    $("prompt").value = msg.content;
    autoGrow($("prompt"));
    syncAskDirector();
    $("prompt").focus();
    chatStatus("Metin düzenlenmek üzere kutuya aktarıldı.");
  });

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "chat-action-btn";
  copyBtn.title = "Metni panoya kopyala";
  const copyIcon = makeSvgIcon("M9 9h13v13H9zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1");
  const copyLabel = document.createElement("span");
  copyLabel.textContent = "Kopyala";
  copyBtn.append(copyIcon, copyLabel);
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(msg.content);
      copyLabel.textContent = "Kopyalandı";
      setTimeout(() => {
        copyLabel.textContent = "Kopyala";
      }, 2000);
    } catch {
      chatStatus("Kopyalanamadı.");
    }
  });

  actions.append(restoreBtn, copyBtn);
  div.appendChild(actions);


  $("chat-log").appendChild(div);
  syncEmptyState();
  scrollMessageIntoView(div);
  return div;
}


// ── Sonuç kartı (üçüncü rol) ────────────────────────────────────────
// Döküm konuşmayı VE üretilen görselleri aynı akışta gösteriyor: kayıt
// `{role:"result", image_ids:[…], params:{kind,size,quality}}` (models.py).
//
// Kart kendi başına yetiyor, ikinci bir istek YOK: dosya adı sözleşmesi
// `{id}.png` (bkz. storage.save / delete_many docstring'i), yani URL id'den
// kuruluyor. `/api/history` KULLANILAMAZDI — o uç klasöre göre süzülüyor ve
// başka bir klasöre taşınmış bir sonuç görselini hiç döndürmezdi.

// Sunucu bu değerleri allowlist'e karşı DOĞRULAMIYOR (§0.4/K5): allowlist bir
// gün daralırsa eski oturumlar kaydedilemez hale gelirdi. Tanınmayan bir değer
// bu yüzden burada da hata değil — ham hâliyle gösteriliyor.
const SIZE_LABELS = { "1024x1024": "1024²", "1024x1536": "1024×1536",
                      "1536x1024": "1536×1024" };
const QUALITY_LABELS = { low: "Düşük", medium: "Orta", high: "Yüksek" };
const RESULT_KIND_LABELS = { generate: "Üretildi", edit: "Düzenlendi" };

/** Kart künyesi: "Üretildi · 1024² · Orta · x2".
 *
 * Adet `image_ids`'in UZUNLUĞUNDAN geliyor, `params`'tan değil (tasarım §5):
 * silinmiş bir görsel bile o sayıyı dürüst tutuyor.
 */
function resultCaption(msg) {
  const p = msg.params || {};
  const parts = [RESULT_KIND_LABELS[p.kind] || "Üretildi"];
  if (p.size) parts.push(SIZE_LABELS[p.size] || p.size);
  if (p.quality) parts.push(QUALITY_LABELS[p.quality] || p.quality);
  parts.push(`x${(msg.image_ids || []).length}`);
  return parts.join(" · ");
}

/** Tek kare. Sarkan id'de "görsel silindi" yer tutucusu çiziliyor.
 *
 * Ölçü `error` OLAYI, bayat bir dizin değil: sunucu sarkan `image_id`'yi kasten
 * budamıyor (test_a_deleted_image_leaves_the_transcript_readable) ve dosya
 * gerçekten yoksa `/output/{id}.png` 404 döner. Gerçek koşulu ölçmek, ayrıca
 * tutulacak bir liste de bırakmıyor.
 */
function resultThumb(imageId, index, caption) {
  const fig = document.createElement("figure");
  fig.className = "chat-media";

  const num = document.createElement("span");
  num.className = "chat-media-num";
  num.textContent = String(index + 1).padStart(2, "0");

  const src = `/output/${encodeURIComponent(imageId)}.png`;
  const img = document.createElement("img");
  img.src = src;
  img.alt = caption;
  img.loading = "lazy";
  img.addEventListener("error", () => {
    // Kare boş KALMIYOR: kaybolan bir küçük resim "yükleniyor" ile
    // "silindi"yi ayırt edilemez yapardı.
    img.remove();
    const ph = document.createElement("span");
    ph.className = "chat-media-ph";
    ph.textContent = "Görsel silindi";
    fig.append(ph);
    fig.classList.add("gone");
    fig.removeAttribute("tabindex");
    fig.removeAttribute("role");
  });

  // Tıklama VE Enter: kare bir düğme değil (içinde kendi eylemi olan bir
  // <figure>), o yüzden ikisi de elle bağlanıyor.
  fig.tabIndex = 0;
  fig.setAttribute("role", "button");
  fig.setAttribute("aria-label", `${caption} — büyüt`);
  const zoom = () => {
    if (fig.classList.contains("gone")) return;
    window.openViewer(src, caption, fig.getBoundingClientRect());
  };
  fig.addEventListener("click", zoom);
  fig.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); zoom(); }
  });

  const dl = document.createElement("button");
  dl.type = "button";
  dl.className = "chat-media-act";
  dl.textContent = "İndir";
  dl.addEventListener("click", (e) => {
    e.stopPropagation();               // indirme büyüteci açmasın
    downloadImage(src, `${imageId}.png`);
  });

  // "Düzenle" ve "+ Ek" BİLEREK yok: ikisi de tam bir geçmiş KAYDI istiyor
  // (prompt, boyut, klasör), döküm ise yalnız id taşıyor. Çalışmayan bir düğme
  // çizmek yerine composer turuna (Adım 8) bırakıldı.
  fig.append(img, num, dl);
  return fig;
}

function appendResult(msg) {
  const div = document.createElement("div");
  div.className = "chat-result";

  const caption = resultCaption(msg);
  const role = document.createElement("span");
  role.className = "chat-role";
  role.textContent = caption;
  div.appendChild(role);

  const grid = document.createElement("div");
  grid.className = "chat-result-grid";
  const ids = msg.image_ids || [];
  // Izgara sütunu ADETTEN geliyor: tek görsel yarım kart olarak değil geniş
  // çizilmeli (referans ekranın `.media.r32` kartı). Üst sınır SUNUCUDA
  // (`models.MAX_IMAGES_PER_RUN`), burada aynalanacak bir şey yok — CSS
  // yalnızca "1 mi, 2 mi, daha fazla mı" sorusunu soruyor.
  grid.dataset.count = String(ids.length);
  ids.forEach((id, i) => grid.appendChild(resultThumb(id, i, caption)));
  div.appendChild(grid);

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

  const actions = document.createElement("div");
  actions.className = "chat-bubble-actions";
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "chat-action-btn";
  copyBtn.title = "Yönetmen yanıtını panoya kopyala";
  const copyIcon = makeSvgIcon("M9 9h13v13H9zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1");
  const copyLabel = document.createElement("span");
  copyLabel.textContent = "Kopyala";
  copyBtn.append(copyIcon, copyLabel);
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      copyLabel.textContent = "Kopyalandı";
      setTimeout(() => {
        copyLabel.textContent = "Kopyala";
      }, 2000);
    } catch {
      chatStatus("Kopyalanamadı.");
    }
  });
  actions.appendChild(copyBtn);
  div.appendChild(actions);


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
  if ($("go")) $("go").disabled = busy || !chatConfigured;
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
  const input = $("prompt");
  const message = input ? input.value.trim() : "";
  const label = (typeof display === "string" && display)
    ? display.replace(/\s+/g, " ").trim().slice(0, MAX_CHAT_DISPLAY_CHARS) : "";
  if (!message) { chatStatus("Önce bir mesaj yaz."); return false; }
  if (message.length > MAX_CHAT_MSG_CHARS) {
    chatStatus(`Mesaj çok uzun (${message.length}/${MAX_CHAT_MSG_CHARS} karakter).`);
    return false;
  }
  // İKİ kapı, çünkü sunucuda da iki tane var: konuşma turu sayısı
  // (`_check_chat_counts`) ve TOPLAM öğe sayısı (alan sınırı). `chatThread.length`
  // tek başına konuşma kapısı olarak sayılsaydı dökümdeki her sonuç kartı bir
  // tur çalar ve üretim yapan oturum ~8 turda kilitlenirdi.
  if (conversationIsFull() || transcriptIsFull(1)) {
    chatStatus("Bu sohbet doldu (en fazla 12 tur). Üst şeritteki \"Yeni oturum\" ile devam et.");
    return false;
  }
  // Toplam, sunucunun `models._check_chat_total` ile AYNI şeyi sayıyor:
  // `content` + `display`, sonuç kayıtları HARİÇ (onlar modele gitmiyor).
  // `m.content.length` yazılamaz: sonuç kaydında `content` HİÇ YOK ve okumak
  // TypeError atardı — gönderim tümden ölürdü.
  const used = chatThread.reduce(
    (n, m) => (m.role === RESULT_ROLE ? n
      : n + (m.content || "").length + (m.display || "").length), 0);
  if (used + message.length + label.length > MAX_CHAT_TOTAL_CHARS) {
    chatStatus("Sohbet çok uzadı — soldaki \"Yeni sohbet\" ile devam et. (Son prompt'u "
      + "kaybetmemek için önce \"Görsel modunda üret\"e bas.)");
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
    const e = new Error(detailText(err) || `Hata (${res.status})`);
    // Durum kodu METİNDEN okunamaz: `detail` varsa `${res.status}` hiç
    // yazılmıyor. 409'u (otomatik kayıt kapalı) beklenen bir durum olarak
    // ayırmak için kodun kendisi taşınıyor.
    e.status = res.status;
    throw e;
  }
  return res.json();
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

/** Turu diske yazar. Başlık GÖNDERİLMİYOR — ve bu bir güvenlik mandalı.
 *
 * "Başlıksız yazım = otomatik yazım" sunucunun anahtarı uygulamak için
 * kullandığı işaret (§0.5/K8): uydurulamaz, çünkü otomatik kaydın verecek bir
 * adı yok. İstemci burada bir başlık türetirse (v1.15'te türetiyordu) o işaret
 * yok olur ve "oturumları otomatik kaydet" anahtarı SESSİZCE delinir — kapalıyken
 * de yazım geçer. Adı sunucu türetiyor (`app._auto_title`); kullanıcı kebaptan
 * yeniden adlandırabiliyor, o yol adlandırılmış yazım olduğu için hep çalışıyor.
 */
async function persistThread() {
  try {
    const path = currentChatId ? `/api/chats/${currentChatId}` : "/api/chats";
    const { chat } = await chatApi(path, {
      method: currentChatId ? "PUT" : "POST", body: { messages: chatThread },
    });
    currentChatId = chat.id;
    upsertSummary(chat);
    syncSessionHeader(chat);
  } catch (e) {
    // 409 = anahtar KAPALI. Bu bir hata değil, kullanıcının kendi kararı:
    // "kaydedilemedi" tonuyla söylenirse her turda bir arıza sanılır. Yanıt
    // ekranda duruyor ve elle kaydetmek (yeniden adlandırma) hâlâ çalışıyor.
    if (e.status === 409) {
      chatStatus("Otomatik kayıt kapalı — bu oturum diske yazılmadı. "
        + "Ayarlar'dan açabilirsin.");
      return;
    }
    // Tur DÜŞMÜYOR: yanıt ekranda ve bellekte duruyor, yalnız diske yazılamadı.
    // Sessiz geçilse kullanıcı sohbetin kaydedildiğini sanardı.
    chatStatus(`Sohbet kaydedilemedi (${e.message}) — yanıt ekranda duruyor.`);
  }
}

// ── Görsel modundaki üretimin döküme yazılması ───────────────────────
// core.js'in `run()`'ı bu üç fonksiyonu OLAY ANINDA çağırıyor (yükleme sırası
// bozulmuyor: chat.js en sonda yükleniyor, core.js yalnız tıklama anında
// buraya bakıyor — dosyanın başındaki yaprak kuralının aynısı).
//
// Görsel modu KENDİ oturumunu başlatıyor (Adım 8 · tasarım §4.2): prompt yapısı
// gereği bir döküm turu. Oturum yoksa `persistThread`'in POST'u açıyor ve bu
// SIRA kritik — yazma yalnızca başarılı üretimden sonra oluyor, yani başarısız
// üretim diskte cevapsız bir kullanıcı turu bırakmıyor (K10'un asıl itirazı).
//
// Üretim isteğine uydurma id konmuyor: `session_id` biçim kapısından geçiyor ama
// varlık kapısı yok (§0.4/K2). Bedeli ilk partide ters bağın (görsel kaydındaki
// `session_id`) eksik kalması; ileri bağ (`result.image_ids`) tam.

/** İki kotanın TEK kapısı; dolu ise gerekçesini de yazar.
 *
 * Paylaşılıyor çünkü iki yer aynı soruyu soruyor: turu AÇAN `beginResultTurn`
 * ve turu KAPATAN `appendResultTurn`. Ayrı yazılsalar açılan ama kapatılamayan
 * bir tur doğardı — dökümde cevapsız bir kullanıcı satırı kalırdı.
 */
function transcriptHasRoom(slots) {
  if (conversationIsFull() || transcriptIsFull(slots)) {
    // Üretimin KENDİSİ engellenmiyor: görsel diske yazılıyor ve Medya'da
    // duruyor. Sessiz sapma yasak (applyToForm geleneği), o yüzden döküme
    // girmediği açıkça söyleniyor.
    chatStatus("Oturum doldu — bu üretim döküme eklenmedi. "
      + "Üst şeritteki \"Yeni oturum\" ile devam et.");
    return false;
  }
  return true;
}

/** Prompt'u kullanıcı turu olarak döküme basar. → tur nesnesi | null.
 *
 * Üretimden ÖNCE çağrılıyor: kullanıcı kendi repliğini beklerken görüyor
 * (sendChat'in aynı sırası). Başarısızlıkta `dropPendingTurn` geri alıyor.
 */
function beginResultTurn(prompt) {
  if (!transcriptHasRoom(2)) return null;
  const turn = { role: "user", content: prompt.slice(0, MAX_CHAT_MSG_CHARS) };
  chatThread.push(turn);
  const bubble = appendUser(turn);

  const pendingDiv = document.createElement("div");
  pendingDiv.className = "chat-result is-pending";
  const progressEl = $("progress");
  if (progressEl) pendingDiv.appendChild(progressEl);
  $("chat-log").appendChild(pendingDiv);

  return { turn, bubble, pendingDiv };
}

function dropPendingTurn(pending) {
  if (!pending || pending.done) return;
  chatThread = chatThread.filter((m) => m !== pending.turn);
  if (pending.bubble) pending.bubble.remove();
  if (pending.pendingDiv) {
    const progressEl = $("progress");
    if (progressEl && pending.pendingDiv.contains(progressEl)) {
      const flow = document.querySelector(".studio-flow");
      if (flow) flow.appendChild(progressEl);
    }
    pending.pendingDiv.remove();
  }
  syncEmptyState();
}

async function appendResultTurn(pending, imageIds, params) {
  if (!pending || !transcriptHasRoom(1)) return;
  if (!imageIds.length) { dropPendingTurn(pending); return; }
  pending.done = true;
  if (pending.pendingDiv) {
    const progressEl = $("progress");
    if (progressEl && pending.pendingDiv.contains(progressEl)) {
      const flow = document.querySelector(".studio-flow");
      if (flow) flow.appendChild(progressEl);
    }
    pending.pendingDiv.remove();
  }
  const record = { role: RESULT_ROLE, image_ids: imageIds, params };
  chatThread.push(record);
  appendResult(record);
  await persistThread();
}

/** Açık oturumun id'si — core.js üretimi ona etiketliyor (yoksa null). */
function openSessionId() {
  return currentChatId;
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

// ── Üst şerit: hangi oturumdayım ─────────────────────────────────────
// `#session-title` / `#session-stamp` PR 1'de kondu, hiç bağlanmamıştı.
// Bağlanması bir GEREKLİLİK, süs değil: kabuk iki modda da aynı ve Görsel
// modunda üretilen görsel açık oturumun dökümüne düşüyor — kullanıcı hangi
// oturumda olduğunu görmezse görsel bilmediği bir yere gitmiş olurdu.
function syncSessionHeader(chat) {
  $("session-title").textContent = chat ? (chat.title || "Adsız oturum") : "Yeni oturum";
  $("session-stamp").textContent = chat ? shortStamp(chat.updated_at) : "";
}

/** Karar D1'in güvence (b)'si: tümünü sil.
 *
 * Onay ZORUNLU ve tek kayıt silmekten daha güçlü bir gerekçeyle: burada geri
 * alınamayan işlem TOPLU. Anahtardan bağımsız (§0.5/K8) — anahtar YAZIMI
 * kısıtlıyor, kullanıcının kendi verisini silmesini değil.
 */
async function deleteAllChats() {
  const count = chatSummaries.length;
  if (!count) { chatStatus("Silinecek oturum yok."); return; }
  const ok = await confirmDialog("Tüm oturumları sil",
    `${count} oturum kalıcı olarak silinecek. Üretilen görseller SİLİNMEZ — `
    + "yalnızca oturum dökümleri gider. Bu işlem geri alınamaz.",
    { okLabel: "Tümünü sil" });
  if (!ok) return;
  try {
    const { deleted } = await chatApi("/api/chats", { method: "DELETE" });
    resetThread();                    // açık oturum da silindi
    chatSummaries = [];
    renderChatList();
    syncSessionHeader(null);
    chatStatus(`${deleted} oturum silindi.`);
  } catch (e) {
    chatStatus(`Silinemedi: ${e.message}`);
  }
}

// ── "Oturumları otomatik kaydet" anahtarı ────────────────────────────
// Uç BİLEREK `/api/settings` değil `/api/prefs` (§0.5/K7): bir tercihi çevirmek
// Azure kimliğini yeniden yazmak zorunda kalmasın ve Azure hiç
// yapılandırılmamışken de anahtar çevrilebilsin.
async function loadPrefs() {
  try {
    const p = await chatApi("/api/prefs");
    $("pref-autosave").checked = p.autosave_sessions !== false;
    if (p.theme) {
      applyTheme(p.theme);
      const radio = document.querySelector(`input[name="theme"][value="${p.theme}"]`);
      if (radio) radio.checked = true;
    }
  } catch {
    // Tercih alınamadı: anahtarın GÖRÜNEN hâli varsayılana (açık) düşüyor,
    // ama yazımı sunucu zaten kendisi kapıyor — burada fail-open yok.
    $("pref-autosave").checked = true;
  }
}

async function saveAutosavePref() {
  const on = $("pref-autosave").checked;
  try {
    const p = await chatApi("/api/prefs",
      { method: "POST", body: { autosave_sessions: on } });
    // Anahtar SUNUCUNUN döndürdüğü değere göre kuruluyor: yazım reddedilmişse
    // kutucuk kullanıcıya yalan söylemesin.
    $("pref-autosave").checked = p.autosave_sessions !== false;
    $("settings-status").textContent = p.autosave_sessions
      ? "Oturumlar otomatik kaydedilecek."
      : "Otomatik kayıt kapatıldı — yalnızca elle kaydedilen oturumlar yazılır.";
  } catch (e) {
    $("pref-autosave").checked = !on;   // gerçekleşmeyen değişikliği geri al
    $("settings-status").textContent = `Tercih kaydedilemedi: ${e.message}`;
  }
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
  syncSessionHeader(null);
}

function newChat() {
  if (chatBusy) { chatStatus("Yönetmen yanıtlıyor — bitmesini bekle."); return; }
  closeMenus();
  resetThread();
  renderChatList();                   // seçili işaret kalkar
  closeSidebarOnMobile();
  $("prompt").focus();
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
      if (m.role === RESULT_ROLE) appendResult(m);
      else if (m.role === "user") appendUser(m);
      else appendBot(m.content);
    }
    lockStaleOptions();
    syncEmptyState();
    renderChatList();
    syncSessionHeader(chat);
    closeSidebarOnMobile();
    $("prompt").focus();
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
    if (chat.id === currentChatId) syncSessionHeader(chat);
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

$("chat-new").addEventListener("click", newChat);

$("chat-sidebar-toggle").addEventListener("click", () => {
  const open = $("chat-sidebar").classList.toggle("open");
  $("chat-sidebar-toggle").setAttribute("aria-expanded", open ? "true" : "false");
});

document.addEventListener("click", (e) => {
  if (openMenuId && !e.target.closest(".chat-item")) closeMenus();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && openMenuId) closeMenus();
});

for (const chip of document.querySelectorAll(".chat-chip")) {
  chip.addEventListener("click", () => {
    $("prompt").value = chip.textContent.trim();
    $("prompt").focus();
  });
}

$("tab-chat").addEventListener("click", () => {
  $("prompt").focus();
});

// Ters yönün düğmesi (§4.2/D13). Yukarıdaki dinleyici bir NEZAKET (boş kutuya
// taslağı kopyalar); bu düğme bir KARAR — her koşulda devrediyor ve metni
// Görsel modundan alıyor. İlk çağrı ilk kareyi eşitliyor: kutu boş olduğu için
// düğme gizli kalır, işaretlemedeki `hidden` ile aynı şeyi söylüyor.
$("ask-director").addEventListener("click", askDirector);
$("prompt").addEventListener("input", syncAskDirector);
syncAskDirector();

// ── D15: Üst Şeritte Kebap Menüsü (Oturum seçenekleri) ─────────────
function toggleKebabMenu(show) {
  const kebab = $("chats-kebab");
  const menu = $("chats-kebab-menu");
  if (!kebab || !menu) return;
  const isHidden = show !== undefined ? !show : !menu.hidden;
  menu.hidden = isHidden;
  kebab.setAttribute("aria-expanded", String(!isHidden));
}

function closeKebabMenu() {
  toggleKebabMenu(false);
}

if ($("chats-kebab")) {
  $("chats-kebab").addEventListener("click", (e) => {
    e.stopPropagation();
    toggleKebabMenu();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".kebab-wrap")) {
      closeKebabMenu();
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeKebabMenu();
  });
}

if ($("chats-rename")) {
  $("chats-rename").addEventListener("click", async () => {
    closeKebabMenu();
    if (!currentChatId) {
      chatStatus("Yeniden adlandırılacak açık oturum yok.");
      return;
    }
    const cur = chatSummaries.find((c) => c.id === currentChatId);
    const title = await promptDialog("Oturumu yeniden adlandır",
      "Yeni oturum başlığını girin.", { defaultValue: cur ? cur.title : "Yeni oturum", okLabel: "Kaydet" });
    if (!title || !title.trim()) return;
    try {
      await chatApi(`/api/chats/${currentChatId}`, {
        method: "PUT",
        body: { title: title.trim() },
      });
      if (cur) cur.title = title.trim();
      $("session-title").textContent = title.trim();
      renderChatList();
      chatStatus("Oturum yeniden adlandırıldı.");
    } catch (e) {
      chatStatus(`Adlandırılamadı: ${e.message}`);
    }
  });
}

if ($("chats-clear-current")) {
  $("chats-clear-current").addEventListener("click", async () => {
    closeKebabMenu();
    if (!chatThread.length) {
      chatStatus("Temizlenecek mesaj yok.");
      return;
    }
    const ok = await confirmDialog("Sohbeti temizle",
      "Açık oturumdaki tüm mesaj dökümü temizlenecek. Üretilen görseller SİLİNMEZ.",
      { okLabel: "Temizle" });
    if (!ok) return;
    resetThread();
    if (currentChatId) {
      try {
        await chatApi(`/api/chats/${currentChatId}`, {
          method: "PUT",
          body: { messages: [] },
        });
      } catch (e) {
        console.error("Clearing thread failed:", e);
      }
    }
    chatStatus("Sohbet dökümü temizlendi.");
  });
}

if ($("chats-delete-all")) {
  $("chats-delete-all").addEventListener("click", () => {
    closeKebabMenu();
    deleteAllChats();
  });
}
if ($("chats-kebab-delete-all")) {
  $("chats-kebab-delete-all").addEventListener("click", () => {
    closeKebabMenu();
    deleteAllChats();
  });
}
$("pref-autosave").addEventListener("change", saveAutosavePref);


syncEmptyState();
loadChats();
loadPrefs();

