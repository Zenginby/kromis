// Lumeo — Prompt Yönetmeni: Türkçe sohbet → İngilizce gpt-image-2 prompt'u.
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
  // Ortada bir form da yok artık; tek composer var.
  //
  // ETİKET ARTIK HEDEFTEN ve iki adım BİRE indi: eski ad, modu değiştirip
  // AYRICA composer'ın kendi düğmesine basmanın adıydı; bu düğme artık üretimi
  // kendisi başlatıyor, ad da yalnız onun TÜRÜNÜ söylüyor.
  //
  // Bilinmeyen hedefte düğme YİNE çiziliyor: tıklama `applyToForm`un ret
  // kapısına düşüyor ve gerekçe yazılıyor. Sessizce kaybolan bir düğme,
  // kullanıcının hiç açıklayamayacağı tek hâl olurdu.
  const hedefli = hedefCoz(parsed);
  apply.textContent = hedefli ? hedefli.hedef.dugme : "Üret";
  apply.addEventListener("click", () => sohbettenUret(parsed));

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
  // üret düğmesine basmadan da hangi model/boyut/kalite önerildiğini görmesi
  // gerekiyor — düğme artık üretimi doğrudan başlattığı için bu daha da önemli.
  // Tanınmayan bir JSON bloğu da çizilir — dürüst sonuç: yönetmen anlaşılmayan
  // bir şey yazdıysa kullanıcı onu görsün.
  //
  // ⚠️ Atlama koşulu "blok VAR" değil "**panel GERÇEKTEN çizilecek**": üç panel
  // de sözleşmeye uymayan maddelerde `null` dönüyor. İkisi ayrıştığında blok ne
  // panel ne kod bloğu olarak görünüyordu, yani sessizce kayboluyordu —
  // üstteki dürüstlük kuralının tam tersi. Süzgeç bu yüzden
  // `optionItems`/`variationItems`/`axisItems` ile PAYLAŞILIYOR.
  //
  // Seçenek satırı bir süre KOŞULSUZDU ve o zaman doğruydu: madde düz dizeydi,
  // `String(raw)` her madde için bir çip üretiyordu, yani "blok var" ile "panel
  // çizilecek" aynı şeydi. Nesne biçimi gelince (`optionItem` artık `null`
  // dönebiliyor) ikisi AYRIŞTI: `{"etiket": "gri"}` gibi bir madde listesi
  // ayrıştırıcıdan geçiyor ama tek çip üretmiyordu — kullanıcı ne seçenek ne
  // ham JSON görüyordu. Alt satırların koşullu olma sebebinin aynısı.
  const skip = new Set([
    optionItems(parsed).length ? parsed.optionsBody : "",
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
//
// AYRIKLIĞIN GERÇEK GARANTİSİ yazıya geçiyor, çünkü imza artık genişledi:
// ayar bloğunun anahtarları İNGİLİZCE (`size`/`quality`/`n`/`duration`),
// öteki üç bloğunki TÜRKÇE (`secenekler`/`varyasyonlar`/`eksenler`). İki ad
// uzayı kesişmediği sürece yeni bir eksen eklemek hiçbir paneli kaçırtmaz;
// kesişecek bir ad seçilirse ayrıklık sessizce ölür.
//
// `model` bu listede DEĞİL ve olmamalı: liste "bu blok bir ayar bloğu mu"
// sorusunun cevabı, `model` ise bloğun YÜKÜ. İmzayı ona genişletmek, yalnız
// model taşıyan bir JSON'u da ayar sanmak olurdu.
const SETTING_KEYS = ["size", "quality", "n", "duration"];

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

  // SIRA KURALI: EN GENİŞ İMZA EN SONDA sorulur. Ayar dalı `SETTING_KEYS`in
  // HERHANGİ biriyle tetikleniyor, yani dördü içinde en gevşek olan o; panel
  // dalları ise tek ve kendine özgü bir dizi anahtarı arıyor. Bugün fark
  // üretmiyor (ad uzayları ayrık), ama melez bir blok geldiği gün sıra
  // panelin ayar sanılmasını önlüyor.
  for (const b of blocks) {
    const obj = jsonObject(b);
    if (!obj) continue;
    jsonBlocks.add(b);
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
      continue;
    }
    if (!settings && SETTING_KEYS.some((k) => obj[k] !== undefined)) {
      settings = obj;
      settingsBlock = b;
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

/** Seçenek maddesini normalleştirir: dize DE nesne DE gelebilir.
 *
 * Sözleşme geriye dönük uyumlu — eski yanıtlar (düz dize listesi) aynen
 * çalışıyor. Süzgeç PAYLAŞILAN bir fonksiyon, `variationItems`/`axisItems`
 * deseninin aynısı: iki panel (seçenek ve parametre) aynı soruyu soruyor ve
 * ayrı yazılırlarsa biri bir alanı okur, öteki okumaz.
 *
 * → `{ ad, aciklama, ornek }`. `ad` MODELE GİDEN değer, yani bugünkü düz
 * dizenin tam karşılığı; `aciklama` ve `ornek` yalnız ekrana ait. Bozuk bir
 * madde `null` dönüyor ve çizilmiyor: adı olmayan bir çip tıklanınca modele
 * boş bir cevap gönderirdi.
 */
function optionItem(raw) {
  if (typeof raw === "string") {
    return raw.trim() ? { ad: raw.trim(), aciklama: "", ornek: null } : null;
  }
  if (!raw || typeof raw !== "object" || typeof raw.ad !== "string" || !raw.ad.trim()) {
    return null;
  }
  return {
    ad: raw.ad.trim(),
    aciklama: typeof raw.aciklama === "string" ? raw.aciklama.trim() : "",
    ornek: raw.ornek && typeof raw.ornek === "object" ? raw.ornek : null,
  };
}

/** Bir listeden ÇİZİLEBİLİR maddeler (bozuklar düşer, tavan uygulanır).
 *
 * `variationItems`/`axisItems` ile aynı sebeple var ve aynı sebeple
 * PAYLAŞILIYOR: bloğu ham JSON olarak çizmeyi atlama kararı ile panelin
 * gerçekten çizilip çizilmeyeceği kararı TEK yerden okunmalı, yoksa
 * sözleşmesi bozuk bir blok ikisinin arasında sessizce kaybolur
 * (bkz. renderMarkdownInto'daki ⚠️ notu).
 *
 * Maddeler NORMALLEŞTİRİLMİŞ dönüyor ve `optionItem` kendi çıktısında
 * değişmez (idempotent), yani `optionChip` aynı maddeyi ikinci kez
 * normalleştirmekten zarar görmüyor.
 */
function drawableOptions(list) {
  return (Array.isArray(list) ? list : [])
    .slice(0, OPTION_MAX).map(optionItem).filter(Boolean);
}

/** Seçenek panelinin çizeceği maddeler. `variationItems(parsed)` /
 * `axisItems(parsed)` ile aynı şekil: atlama kümesi üçünü de aynı biçimde
 * soruyor. */
function optionItems(parsed) {
  return parsed.options ? drawableOptions(parsed.options.secenekler) : [];
}

// Örnek görselinin DOĞRULAYICILARI. Model metni bir `style` özelliğine
// yazılacak, o yüzden kapı dar ve BEYAZ liste: doğrulamayı geçmeyen değer
// çizilmiyor (metin yine görünüyor). `innerHTML` hiç kullanılmıyor, ama
// `style.background = "url(...)"` gibi bir değer de burada geçemez.
// Uzunluk listesi 3·4·6·8 ve bu SAYILI: CSS'in tanıdığı hex uzunlukları
// bunlar. Kapı bir süre `{3,8}` diyordu, yani 5 ve 7 haneli bir dize
// doğrulamadan GEÇİYOR ama `style.background`a yazıldığında CSSOM onu sessizce
// atıyordu — kutu yine döndüğü için çip karta yükseliyor ve kullanıcı BOŞ bir
// dikdörtgen görüyordu. "Doğrulamayı geçmeyen değer çizilmiyor" sözü ancak
// doğrulama CSS'in kabul ettiği kümeyle aynı olduğunda tutuyor.
const HEX_RE = /^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
const ORAN_RE = /^([1-9][0-9]?):([1-9][0-9]?)$/;

/** Seçeneğin ÇİZİLEBİLİR örneği (yoksa null).
 *
 * Üç şekil: tek renk · renk şeridi (2–5) · oran dikdörtgeni. Liste bilerek
 * KISA — istemcinin gerçekten çizebildiği şeyler bunlar. "soft overcast light"
 * gibi bir eksende görsel örnek üretmek üretim demek olurdu ve üretim para
 * harcıyor (bkz. `#go` otomatik tıklanmaz kararı); o eksende doğru karşılık
 * `aciklama` metni.
 */
function ornekKutusu(ornek, sessiz) {
  if (!ornek) return null;
  const kutu = document.createElement("span");
  kutu.className = "chat-option-ornek";
  // `sessiz` = maddenin bir `aciklama`sı var, yani kutunun taşıdığı bilgi
  // METİN olarak da ekranda: kutuyu ekran okuyucudan gizlemek doğru, iki kez
  // duyurmak gürültü olurdu.
  //
  // Ama `aciklama` ile `ornek` sözleşmede BİRBİRİNDEN BAĞIMSIZ isteğe bağlı
  // alanlar: `{"ad": "deep navy", "ornek": {"renk": "#0b2545"}}` geçerli bir
  // madde. Kutu orada koşulsuz `aria-hidden` olsaydı seçenekleri BİRBİRİNDEN
  // AYIRAN tek şey görsel kalır, ekran okuyucu kullanıcısı yalnız "deep navy"
  // duyardı. O yüzden açıklama yoksa kutu bir `img` gibi ADLANDIRILIYOR.
  const adlandir = (metin) => {
    if (sessiz) { kutu.setAttribute("aria-hidden", "true"); return; }
    kutu.setAttribute("role", "img");
    kutu.setAttribute("aria-label", metin);
  };

  if (typeof ornek.renk === "string" && HEX_RE.test(ornek.renk.trim())) {
    kutu.style.background = ornek.renk.trim();
    adlandir(`örnek renk ${ornek.renk.trim()}`);
    return kutu;
  }
  if (Array.isArray(ornek.renkler)) {
    const renkler = ornek.renkler
      .filter((r) => typeof r === "string" && HEX_RE.test(r.trim()))
      .map((r) => r.trim())
      .slice(0, 5);
    if (renkler.length < 2) return null;
    kutu.classList.add("chat-option-ornek-serit");
    adlandir(`örnek renkler: ${renkler.join(", ")}`);
    for (const r of renkler) {
      const dilim = document.createElement("span");
      dilim.style.background = r;
      kutu.appendChild(dilim);
    }
    return kutu;
  }
  if (typeof ornek.oran === "string") {
    const m = ORAN_RE.exec(ornek.oran.trim());
    if (!m) return null;
    kutu.classList.add("chat-option-ornek-oran");
    // `aspectRatio` sayısal: dizeyi doğrudan yazmak yerine ayrıştırılmış iki
    // sayıdan kuruluyor, yani CSS'e model metni HİÇ geçmiyor. Etiket de aynı
    // iki sayıdan kuruluyor, ham dizeden değil.
    kutu.style.aspectRatio = `${Number(m[1])} / ${Number(m[2])}`;
    adlandir(`örnek oran ${Number(m[1])}:${Number(m[2])}`);
    return kutu;
  }
  return null;
}

/** Seçilebilir çip. `scope` = DIŞLAYICILIK kapsamı, panelin kendisi olmak
 * zorunda değil: parametre panelinde eksen SATIRI geçiliyor, böylece "eksen içi
 * tek seçim, eksenler birbirinden bağımsız" semantiği bedavaya geliyor.
 *
 * `item` dize DE nesne DE olabilir (`optionItem` normalleştiriyor). Açıklaması
 * olan madde KART oluyor, olmayan bugünkü kompakt pill olarak kalıyor: kart
 * yalnız taşıyacak bilgi varken doğuyor, yoksa şerit boşuna büyürdü.
 *
 * KART DA `.chat-option` sınıfını, `role`unu ve `aria-checked`ini TAŞIYOR:
 * `lockStaleOptions`ın kilidi, odak halkası, `.chat-options-done` ve
 * `[aria-checked="true"]::before { content: "✓ " }` hepsi o sınıftan geliyor.
 */
function optionChip(item, multi, scope) {
  const veri = optionItem(item);
  if (!veri) return null;
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chat-option";
  chip.setAttribute("role", multi ? "checkbox" : "radio");
  chip.setAttribute("aria-checked", "false");
  // MODELE GİDEN değer burada, `textContent`te DEĞİL. `pickedLabels` eskiden
  // `textContent` okuyordu ve kartın açıklaması o metne karışırdı — yönetmene
  // "deep navy background Zemin gece lacivertine döner…" diye bir cevap
  // giderdi. Ayrım sessiz olurdu: ekranda kart doğru görünür, yalnız modelin
  // aldığı cevap bozuk olur.
  chip.dataset.value = veri.ad;

  const kutu = ornekKutusu(veri.ornek, !!veri.aciklama);
  if (veri.aciklama || kutu) {
    chip.classList.add("chat-option-card");
    if (kutu) chip.appendChild(kutu);
    const ad = document.createElement("span");
    ad.className = "chat-option-ad";
    ad.textContent = veri.ad;        // ← model metni: yalnızca textContent
    chip.appendChild(ad);
    if (veri.aciklama) {
      const not = document.createElement("span");
      not.className = "chat-option-not";
      not.textContent = veri.aciklama;   // ← model metni: yalnızca textContent
      chip.appendChild(not);
    }
  } else {
    chip.textContent = veri.ad;      // ← model metni: yalnızca textContent
  }

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
 * duyurmak ekran okuyucuya yalan söylemek olurdu.
 *
 * `aciklama` = maddenin `istek` alanı. O metin sözleşmede ZATEN vardı ve
 * doğrulanıyordu (`variationItems`), ama ekranda HİÇ görünmüyordu: kullanıcı
 * "Gece" yazan bir düğme görüyor ve neyin değişeceğini ancak tıklayıp
 * bekledikten sonra öğreniyordu. Metin modele giden istekle AYNI — yani
 * düğmenin ne yapacağının birebir kaydı, ikinci bir özet değil.
 */
function actionChip(label, aciklama) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chat-option chat-variation";
  if (aciklama) {
    chip.classList.add("chat-option-card");
    const ad = document.createElement("span");
    ad.className = "chat-option-ad";
    ad.textContent = label;          // ← model metni: yalnızca textContent
    const not = document.createElement("span");
    not.className = "chat-option-not";
    not.textContent = aciklama;      // ← model metni: yalnızca textContent
    chip.append(ad, not);
  } else {
    chip.textContent = label;        // ← model metni: yalnızca textContent
  }
  return chip;
}

/** Seçili çiplerin MODELE GİDEN değerleri.
 *
 * `dataset.value` okunuyor, `textContent` DEĞİL: kart varyantı çipin içine
 * açıklama ve örnek koyuyor ve `textContent` onları da toplardı. `??` düşme
 * yolu, `.chat-option` taşıyan ama `dataset.value` yazmayan bir çip
 * (varyasyon düğmesi) buraya girerse eski davranışı koruyor.
 */
function pickedLabels(scope) {
  return [...scope.querySelectorAll(".chat-option")]
    .filter((c) => c.getAttribute("aria-checked") === "true")
    .map((c) => c.dataset.value ?? c.textContent);
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
  // İKİ liste, çünkü iki eksen türü modele AYRI fiille gidiyor: takas ekseni
  // prompt'ta duran bir ifadeyi değiştiriyor, ekleme ekseni prompt'un hiç
  // söylemediği bir şeyi belirliyor. Tek cümlede toplansalardı model
  // "değiştir" fiilini var olmayan bir ifadeye uygulamak zorunda kalır ve
  // ya uydurma bir eski değer üretir ya da isteği yok sayardı.
  const takas = [];
  const ekleme = [];
  const shown = [];
  for (const row of group.querySelectorAll(".chat-axis")) {
    const picked = pickedLabels(row);
    if (!picked.length) continue;
    const name = row.dataset.axis || "";
    (row.dataset.yeni ? ekleme : takas).push(`${name} → ${picked[0]}`);
    shown.push(`${name}: ${picked[0]}`);
  }
  // Sayı YETİYOR: `[...takas, ...ekleme]` diye birleştirilmiş bir dizi
  // yalnızca `length`i için ayrılıyordu.
  const secili = takas.length + ekleme.length;
  const own = ownText(group);
  if (!secili && !own) return { content: "", display: "" };
  const sentence = [
    takas.length ? `Şu parametreleri değiştir: ${takas.join("; ")}.` : "",
    ekleme.length ? `Şunları da belirle: ${ekleme.join("; ")}.` : "",
  ].filter(Boolean).join(" ");
  // Kullanıcı noktalama koymadıysa biz koyuyoruz: yoksa serbest metin ile
  // kapanış cümlesi tek cümleye yapışıyor ("zemin daha sade Prompt'un geri
  // kalanını aynı tut") ve model sınırın nerede olduğunu tahmin etmek zorunda.
  const idea = own && !/[.!?…]$/.test(own) ? `${own}.` : own;
  const content = [sentence, idea, "Prompt'un geri kalanını aynı tut."]
    .filter(Boolean).join(" ");
  // Eksen seçilmedi: `shown` boş, o yüzden aşağıdaki birleştirme kullanılamaz
  // (başa sarkan bir ayraç üretirdi). Pilde kullanıcının yazdığı metin duruyor.
  if (!secili) return { content, display: own };
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
  // Hiç çizilebilir madde yoksa panel KURULMUYOR ve `renderMarkdownInto`
  // bloğu ham JSON olarak gösteriyor — iki karar aynı süzgeci okuduğu için
  // ayrışamıyorlar. Soru prozada da yazılı (persona bunu şart koşuyor), yani
  // kullanıcı soruyu görmeye devam ediyor; kaybolan tek şey tıklanamayan
  // boş bir şerit olurdu.
  const items = optionItems(parsed);
  if (!items.length) return null;
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
  for (const item of items) {
    // `String(raw)` KALDIRILDI: madde artık nesne de olabiliyor ve `String`
    // onu "[object Object]" yapardı — ekranda da, modele giden cevapta da.
    // Bozuk maddeyi düşüren yer artık `drawableOptions`; buradaki `if (chip)`
    // ikinci bir kemer, taşıyıcı olan süzgeç.
    const chip = optionChip(item, multi, group);
    if (chip) chips.appendChild(chip);
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

/** Sözleşmeye uyan eksenler (yoksa boş dizi). Bkz. `variationItems`.
 *
 * Kapı "dizi ve boş değil"den `drawableOptions`a GEÇTİ ve sebebi atlama
 * kümesiyle aynı: dolu ama tamamı bozuk bir `secenekler` listesi
 * (`[{"label": "soft"}]`) eski kapıdan geçiyordu, yani eksen satırı adıyla ve
 * rozetiyle çiziliyor ama TIKLANACAK hiçbir şey taşımıyordu — üstelik ham blok
 * da atlanmış olduğu için modelin ne önerdiği hiçbir yerde görünmüyordu.
 */
function axisItems(parsed) {
  if (!parsed.parameters) return [];
  return parsed.parameters.eksenler
    .filter((e) => e && typeof e.ad === "string" && e.ad.trim()
                   && drawableOptions(e.secenekler).length)
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
    const chip = actionChip(ad, item.istek.trim());
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

    // Rozet İKİ durumu anlatıyor ve ikisi de görünür olmak ZORUNDA: `simdi`
    // varsa satır bir TAKAS (prompt'ta duran ifade gösteriliyor, kullanıcı
    // neyi feda ettiğini görüyor), yoksa bir EKLEME (prompt o ekseni hiç
    // söylemiyor). Öncesinde `simdi` yokken hiçbir şey çizilmiyordu, yani
    // ekleme ekseni takas gibi görünüyordu — kullanıcı var olmayan bir
    // ifadeyi değiştirdiğini sanırdı. `dataset.yeni` bu ayrımın axesValue'nun
    // okuduğu hâli: iki eksen türü modele ayrı fiille gidiyor.
    const now = document.createElement("span");
    if (typeof axis.simdi === "string" && axis.simdi.trim()) {
      // Değer GÖRÜNÜR olmalı ama tıklanabilir GÖRÜNMEMELİ: çip değil kod rozeti.
      now.className = "chat-axis-now";
      now.textContent = axis.simdi.trim();
    } else {
      row.dataset.yeni = "1";
      now.className = "chat-axis-new";
      now.textContent = "prompt'ta yok";
    }
    row.appendChild(now);

    const chips = document.createElement("div");
    chips.className = "chat-options-chips";
    for (const item of drawableOptions(axis.secenekler)) {
      // `false` = eksen içinde TEK seçim, `row` = dışlayıcılık kapsamı
      // (panel değil SATIR): ışık + palet + kadraj birlikte seçilebilsin.
      const chip = optionChip(item, false, row);
      if (chip) chips.appendChild(chip);
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

// Yönetmenin hedefleyebileceği ÜRETİM modları. `MOD_SEKMELERI`nin kopyası
// DEĞİL: orada `director` da geçerli bir üye ama o mod üretim YAPMIYOR —
// `setMode` onu kabul ederdi ve tek tıklı üretim prompt'u yönetmene GERİ
// gönderirdi. Bilinmeyen bir hedefte `setMode`un "görsele düş" kuralına
// yaslanmak da yanlış olurdu: sessiz sapma.
//
// `eksen` bir kimlik eşlemesi gibi duruyor ama DEĞİL: `MODEL_EKSENLERI`nin
// anahtarları {image, chat, video, arena}, mod adları {image, video, director}
// — iki ad uzayı yalnız iki üyede rastlaşıyor. Adı burada YAZMAK, o rastlantıyı
// sözleşme sanmamak için.
const HEDEF_MODLAR = {
  image: { eksen: "image", dugme: "Görsel üret", ad: "Görsel" },
  video: { eksen: "video", dugme: "Video üret", ad: "Video" },
};

/** Ayar bloğunun hedefi ve önerdiği model. → {hedef, model} | null.
 *
 * TÜR `model` id'sinden TÜRETİLİYOR, telde ayrı bir `mode`/`kind` alanı YOK:
 * iki alan çelişebilirdi (`{"mode":"image","model":"gemini-veo-3-1"}`) ve
 * çözüm kuralı hem personaya öğretilmek hem burada dallanmak zorunda kalırdı.
 * Türetmenin kaynağı literal bir tablo da değil — `/api/settings`in ayrı ayrı
 * gönderdiği iki liste, yani sunucunun gerçeği.
 *
 * `model` HİÇ YOKSA hedef görsel: bugünkü davranış ve `model` alanını
 * tanımayan her eski döküm aynen çalışmaya devam ediyor.
 *
 * Listelerde SÜZGEÇ YOK (`secilebilirler` burada çağrılmıyor): "katalogda yok"
 * ile "anahtarı yok" ayrı sorular ve kullanıcının okuyacağı cümle de ayrı.
 * İkincisini `modelOnerisiniUygula` söylüyor.
 */
function hedefCoz(parsed) {
  const id = (parsed.settings && parsed.settings.model
    ? String(parsed.settings.model) : "").trim();
  if (!id) return { hedef: HEDEF_MODLAR.image, model: null };
  const video = videoModels.find((m) => m.id === id);
  if (video) return { hedef: HEDEF_MODLAR.video, model: video };
  const gorsel = imageModels.find((m) => m.id === id);
  if (gorsel) return { hedef: HEDEF_MODLAR.image, model: gorsel };
  return null;
}

// [json anahtarı = <select> id'si = `#spec-*`/`#label-*` son eki]. Tablo tek
// sütuna İNDİ: üçüncü sütun elle yazılmış sabit bir eksen adıydı ve video
// eklendiği an yanlış olurdu — `#label-size` video modunda "Oran" oluyor
// (core.js `eksenleriDoldur`), yani mesaj kullanıcının ekranında olmayan bir
// kelimeyi söylerdi. Görünen ad artık `axisLabel()`ten geliyor; core.js'teki
// "chat.js'in atlanan-öneri metni bunu kullanıyor" yorumu da bugün ilk kez
// DOĞRU.
const SETTING_TARGETS = ["size", "quality", "duration", "n"];

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
  // GİZLİ SATIR = eksen bu modda/modelde YOK. Ölçüt `hidden` özniteliği, modele
  // sorulan İKİNCİ bir soru değil — `syncSpecs`in okuduğu kuralın aynısı ve tek
  // yazarı `eksenleriDoldur`.
  //
  // Değer zaten isteneni gösteriyorsa SAPMA YOK: video modellerinin hepsi
  // `max_n=1` ve `#spec-n` gizli, yani yönetmenin `n: 1`i uygulanamamış bir
  // öneri değil GERÇEKLEŞMİŞ bir öneridir. Göstermiyorsa yazmak yanlış olurdu:
  // kullanıcının göremediği bir ekseni arkasından oynatırdı.
  //
  // Üç sızıntıyı birden kapatıyor: görsel modunda gelen `duration` (süresiz
  // modelde `#duration` TEMİZLENMİYOR, bayat seçeneklere denk gelip
  // "uygulandı" derdi), `quality_hidden` modelde kalite önerisi, arena açıkken
  // `n` önerisi.
  const satir = $(`spec-${selectId}`);
  if (satir && satir.hidden) return el.value === match.value;
  el.value = match.value;
  return true;
}

/** Yönetmenin model önerisini uygular. → "" (uygulandı ya da öneri yok) | sebep.
 *
 * DEĞER TAŞIYICIYA yazılıyor ve `change` ELLE gönderiliyor: o dinleyici
 * (core.js) `applyModel`/`applyVideoModel` + `savePref` + bellekteki tercihin
 * ÜÇÜNÜ tek yoldan koşturuyor — `#model-sheet-list`in kurduğu desenin aynısı.
 * Buradan `applyModel` çağırmak o zincirin ikinci bir kopyası, tercihi de iki
 * kez diske yazmak olurdu.
 *
 * TERCİHE YAZILMASI yalnız tutarlılık değil İŞLEVSEL bir zorunluluk:
 * `app._director_context` yönetmenin tur bağlamını `prefs`ten kuruyor. Öneri
 * tercihe yazılmazsa yönetmen bir sonraki turda hâlâ ESKİ modelin jetonlarını
 * anlatır ve `applyIfSupported`ın reddettiği önerileri yazmaya devam eder.
 */
function modelOnerisiniUygula(hedef, model) {
  if (!model) return "";
  // Arena açıkken sütunları `arenaSecimi()` sürüyor ve `#model` yalnız birinci
  // sütunun eksenlerini besliyor: öneriyi uygulamak kullanıcıya sessizce başka
  // bir şey vaat etmek olurdu.
  if (hedef.eksen === "image" && arenaAcik) {
    return `${model.label} (arena açık — önce arenayı kapat)`;
  }
  const eksen = MODEL_EKSENLERI[hedef.eksen];
  // SEÇİLEBİLİRLİK tek yerden soruluyor: `<select>`e giren küme de aynı
  // süzgeçten geçiyor, yani "listede var ama yazılamaz" hâli doğamıyor.
  if (!secilebilirler(eksen.liste(), "").some((m) => m.id === model.id)) {
    return `${model.label} (anahtar yok — Ayarlar'dan ekle)`;
  }
  const secici = $(eksen.secici);
  if (secici.value === model.id) return "";   // aynı değere ikinci dokunuş SESSİZ
  secici.value = model.id;
  secici.dispatchEvent(new Event("change", { bubbles: true }));
  return "";
}

/** Yanıtı composer'a aktarır. → önerinin TAMAMI uygulandıysa true.
 *
 * Dönüş değeri `sohbettenUret`in kapısı: kısmi uygulanmış bir öneriyle üretime
 * başlamak, aşağıdaki "uygulanamadı" mesajını `run()`ın "Üretiliyor…"suna
 * mikrosaniyede ezdirirdi — yani SESSİZ SAPMA YASAK kuralı pratikte ölürdü.
 */
function applyToForm(parsed) {
  // ── 1 · RET KAPILARI, hiçbir şey UYGULANMADAN önce ──
  // Reddedilen bir yanıt kullanıcının modunu, modelini ve tercihini de
  // değiştirmemeli: ya hep ya hiç.
  const cozum = hedefCoz(parsed);
  if (!cozum) {
    chatStatus(`Yönetmen tanınmayan bir model bildirdi `
      + `(${parsed.settings.model}) — hangi modeli kullanacağını tekrar sor.`);
    return false;
  }
  if (!parsed.prompt) {
    chatStatus("Yanıtta prompt bloğu bulunamadı — yönetmene prompt'u tekrar yazmasını söyle.");
    return false;
  }
  if (parsed.prompt.length > MAX_PROMPT_CHARS) {
    // KIRPMA YOK: kırpılmış bir prompt sessizce BAŞKA bir görsel üretir.
    chatStatus(`Prompt ${MAX_PROMPT_CHARS} karakter sınırını aşıyor `
      + `(${parsed.prompt.length}). Yönetmene kısaltmasını söyle.`);
    return false;
  }

  const { hedef, model } = cozum;
  const skipped = [];
  // ── 2 · MOD, eksenlerin SAHİBİ ──
  // Eskiden eksenler `setMode`dan ÖNCE yazılıyordu ve bu, üç mod dünyasında
  // kırılıyor: video modundan gelen kullanıcıda `#size` `16:9` jetonlarını
  // taşıyor, `1024x1024` önerisi `false` dönüyor (boşuna "uygulanamadı"),
  // sonra `aktifModeliUygula` görsel jetonlarını dolduruyor ve öneri
  // KAYBOLUYOR. `setMode` idempotent, hedef mod zaten aktifse zararsız.
  setMode(hedef.eksen);
  // ── 3 · MODEL, eksenleri KENDİ jetonlarıyla yeniden dolduruyor ──
  // Bu yüzden eksenlerden önce; ayrıca `applyModel`/`applyVideoModel`
  // `currentMode` kapısından geçiyor, yani modun 2. adımda oturmuş olması şart.
  const modelSebep = modelOnerisiniUygula(hedef, model);
  if (modelSebep) skipped.push(modelSebep);

  // ── 4 · PROMPT ──
  $("prompt").value = parsed.prompt;
  // Programatik yazım `input` olayı DOĞURMAZ: ters yönün düğmesi elle
  // eşitlenmezse dolu kutunun yanında görünmez kalırdı.
  syncAskDirector();

  // ── 5 · EKSENLER, mod ve model oturduktan SONRA ──
  // Artık `<option>` listesi hedef modun + hedef modelin listesi, yani
  // `applyIfSupported`ın `false`u GERÇEKTEN desteklenmeyen bir değer demek.
  for (const key of SETTING_TARGETS) {
    const value = parsed.settings ? parsed.settings[key] : undefined;
    if (value === undefined || value === null || value === "") continue;
    if (!applyIfSupported(key, value)) skipped.push(`${axisLabel(key)} ${value}`);
  }

  // ── 6 · EŞİTLEME ve RAPOR ──
  $("prompt").focus();
  // Programatik `.value` ataması `change` olayını DOĞURMAZ: syncSpecs elle
  // çağrılmazsa üretim ayarları çipi eski değerleri göstermeye devam eder.
  // `syncRunCost` de aynı sebeple burada: ikisi `change` dinleyicisinde TEK
  // çift olarak koşuyor (core.js → size/quality/n) ve yönetmenin önerisi
  // adet/kalite değiştirdiğinde kredi tahmini eskisinde kalıyordu.
  syncSpecs();
  syncRunCost();
  // SESSİZ SAPMA YASAK (palette applied:false ile aynı gerekçe): uygulanamayan
  // öneri açıkça söylenir, yoksa kullanıcı formda başka bir ayar görür ve
  // sonucu açıklayamaz.
  statusEl.textContent = `Prompt ${hedef.ad} moduna aktarıldı.`
    + (skipped.length ? ` Şu öneriler uygulanamadı: ${skipped.join(", ")}.`
                        + " Üretimi elle başlatabilirsin." : "");
  return !skipped.length;
}

/** Sohbet içi üretim: hazırla → kapıyı SOR → composer'ın kendi yolundan koş.
 *
 * MEVCUT yol yeniden kullanılıyor, ikinci bir üretim yolu YAZILMIYOR. Kazanç
 * yalnız kod tasarrufu değil; bunların hepsi bedava geliyor: `goBlockReason`
 * kapısı, arena dalı, referans/ek referans/son kare dalları,
 * `beginResultTurn`+`appendResultTurn` ile sonucun DÖKÜME yazılması, kredi
 * tahmini, bayat sunucu yankı denetimleri ve hata yolunda turun geri alınması.
 * Kendi `fetch`ini yazan bir düğme bunların hepsini yeniden borçlanırdı.
 *
 * Giriş `submitComposer` — `run()` DEĞİL: uzunluk kapısını ve mod dalını o
 * taşıyor, yani üç giriş noktası (`#go`, ⌘/Ctrl+Enter, bu düğme) tek
 * fonksiyonda birleşiyor. Mod `applyToForm` tarafından image|video'ya
 * çekildiği için `sendChat` dalına düşmesi imkânsız.
 *
 * KAPI BURADA YENİDEN SORULUYOR çünkü `run()` onu SORMUYOR ve `#go.disabled`
 * bu düğmeyi hiç bağlamıyor — `runArena`nın yazılı dersinin aynısı: kapıyı
 * sormayan bir giriş noktası, kapının metnini ölü bir cümleye çevirir ve
 * ÜCRETLİ bir isteği sessizce yollar.
 *
 * MEŞGULİYET için yeni bayrak gerekmiyor: `run()` `runBusy`yı kuruyor ve
 * `goBlockReason`ın ilk satırı onu okuyor. Düğmeler `disabled` da EDİLMİYOR —
 * kapı zamanla değişiyor (anahtar sonradan girilir, üretim biter) ve eski bir
 * dökümde donmuş bir `disabled` yanlış bir söz olurdu.
 */
function sohbettenUret(parsed) {
  if (!applyToForm(parsed)) return;   // gerekçeyi applyToForm yazdı
  const engel = goBlockReason();
  if (engel) { chatStatus(engel); return; }
  submitComposer();
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
      // İKİ geri bildirim, biri yedek değil: seçim pilinde (.chat-pick) etiket
      // gizli — iki düğme oraya sığmadığı için ikon-only (style.css). Etiket tek
      // onay olsaydı bir seçimi kopyalayan kullanıcı hiçbir şey görmezdi.
      copyLabel.textContent = "Kopyalandı";
      chatStatus("Panoya kopyalandı.");
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
const QUALITY_LABELS = { low: "Düşük", medium: "Orta", high: "Yüksek",
                         // Veo'nun `resolution` jetonları (v0.13).
                         "720p": "720p", "1080p": "1080p" };
const RESULT_KIND_LABELS = { generate: "Üretildi", edit: "Düzenlendi",
                             video: "Video üretildi",
                             animate: "Canlandırıldı" };

/** Bu sonuç kaydı VİDEO mu — kartın `<img>` mi `<video>` mü olacağı.
 *
 * Ölçüt `params.kind` ve küme burada LİTERAL: `models.VIDEO_RESULT_KINDS`in
 * istemci aynası. Aynanın bedeli bir satır, kazancı şu — ikinci bir alan
 * (`media_kind`) açmak `ResultParams`a yeni bir alan eklemek olurdu ve o
 * sınıf `extra="forbid"` taşıyor, yani ESKİ oturumların hepsi kaydedilemez
 * hale gelirdi. `kind` ise zaten her kayıtta var ve bu dosya onu ZATEN
 * okuyor (`resultCaption`).
 *
 * UZANTIYA BAKILMIYOR ve bu bilinçli: kart yalnız `image_ids`i biliyor,
 * dosya adını değil (`/output/{id}` adresini kendisi kuruyor). Türü adresten
 * çıkarmaya çalışmak, önce bir HEAD isteği atmak demekti.
 */
const VIDEO_RESULT_KINDS = ["video", "animate"];

function sonucVideoMu(msg) {
  return VIDEO_RESULT_KINDS.includes((msg.params || {}).kind);
}

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
  // SÜRE künyeye giriyor çünkü videoda o, faturayı belirleyen eksen (kredi
  // saniyeyle çarpılıyor) — "Video üretildi · 16:9 · 720p" yazan bir künye
  // dört saniyelik bir klibi sekiz saniyelikten ayırt edemezdi. Eski
  // kayıtlarda alan 0 (`ResultParams`ın varsayılanı) ve o zaman hiç
  // yazılmıyor: göç YOK.
  if (p.duration) parts.push(`${p.duration} sn`);
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
function resultThumb(imageId, index, caption, videoMu = false, oran = "") {
  const fig = document.createElement("figure");
  fig.className = "chat-media";

  // KARENİN ORANI VİDEODA SABİT DEĞİL. `.chat-media` görsel için kare çiziyor
  // (`aspect-ratio: 1`) ve `overflow: hidden` taşanı kırpıyor; bir 16:9 video o
  // kutuda kendi doğal ölçüsüyle (1280×720) yerleşince oynatıcının denetim
  // çubuğu karenin ALTINDA kalıp kırpılıyordu — mobilde videoyu oynatmanın TEK
  // yolu kapanıyordu, çünkü video kartına tıklama da bilerek bağlanmıyor
  // (aşağıdaki `if (!videoMu)`).
  //
  // Oran CSS'ten `:has()` ile DEĞİL buradan geliyor: metadata inene kadar
  // `<video>` 300×150 durur ve kutu sonradan zıplardı. `params.size` zaten bu
  // dosyanın okuduğu alan (`resultCaption`), ikinci bir gerçek kaynağı yok.
  //
  // SINIF ORANDAN AYRI DURUYOR. `.video` iki işi birden yapıyor ve ikisinin de
  // orana bağımlılığı YOK: `.chat-media`nın `zoom-in` imlecini düzeltiyor
  // (video kartına büyüteç bağlanmıyor, aşağıdaki `if (!videoMu)`) ve indirme
  // şeridini denetim çubuğunun üstünden çekiyor (style.css). `params.size`
  // BİLEREK allowlist'siz (`models.ResultParams`), yani iki nokta içermeyen
  // bir değer ulaşılabilir — eski bir döküm, içe aktarılmış bir oturum ya da
  // oranı jeton olarak yazmayan bir model. Tek koşula bağlanmış olsalardı o
  // hâlde İKİ düzeltme birden düşerdi.
  if (videoMu) {
    fig.classList.add("video");
    if (oran.includes(":")) fig.style.aspectRatio = oran.replace(":", " / ");
  }

  const num = document.createElement("span");
  num.className = "chat-media-num";
  num.textContent = String(index + 1).padStart(2, "0");

  // UZANTI TÜRDEN: sunucu videoyu `.mp4` olarak kaydediyor (uzantıyı kaydın
  // `kind`inden türetiyor, bkz. storage.save) ve `/output/{id}.png` bir video
  // için 404. İki uzantıyı denemek YOK — tür kaydın kendisinde yazılı ve
  // buraya `params.kind` üzerinden ulaşıyor.
  const src = `/output/${encodeURIComponent(imageId)}.${videoMu ? "mp4" : "png"}`;
  // VİDEODA `<video>`, GÖRSELDE `<img>`. Ortak dört şey aynı kalıyor: `src`,
  // erişilebilir ad, tembel yükleme ve `error` OLAYI — yani silinmiş medya
  // tespiti tür değiştirmiyor (`<video>` de `error` yayıyor).
  const media = document.createElement(videoMu ? "video" : "img");
  media.src = src;
  if (videoMu) {
    // `controls`: oynatıcının kendi denetimleri. Kart içinde otomatik
    // oynatma YOK ve bu bilinçli — bir döküm ekranında dört klibin birden
    // sesle başlaması kullanıcıya saldırı gibi gelirdi.
    media.controls = true;
    // `preload="metadata"`: ilk kare POSTER'ın yerine geçiyor. Ayrı bir
    // poster dosyası ÜRETİLMİYOR (bu, sunucuda ffmpeg bağımlılığı demekti ve
    // requirements.txt'nin dört satırlık disiplinini bozardı); tarayıcı
    // metadata ile ilk kareyi zaten çiziyor ve tam dosyayı indirmiyor.
    media.preload = "metadata";
    // iOS Safari: `playsinline` olmadan dokunma videoyu TAM EKRANA alıyor ve
    // kullanıcı dökümden kopuyor.
    media.playsInline = true;
    media.setAttribute("aria-label", caption);
  } else {
    media.alt = caption;
    media.loading = "lazy";
  }
  media.addEventListener("error", () => {
    // Kare boş KALMIYOR: kaybolan bir küçük resim "yükleniyor" ile
    // "silindi"yi ayırt edilemez yapardı.
    media.remove();
    const ph = document.createElement("span");
    ph.className = "chat-media-ph";
    ph.textContent = videoMu ? "Video silindi" : "Görsel silindi";
    fig.append(ph);
    fig.classList.add("gone");
    fig.removeAttribute("tabindex");
    fig.removeAttribute("role");
  });

  // Tıklama VE Enter: kare bir düğme değil (içinde kendi eylemi olan bir
  // <figure>), o yüzden ikisi de elle bağlanıyor.
  // VİDEODA KART TIKLANMIYOR ve bu bir eksik değil bir zorunluluk:
  // `<video controls>` kendi denetimlerini taşıyor ve karenin `click`
  // dinleyicisi oynat/durdur ile büyüteci ÇAKIŞTIRIRDI — kullanıcı oynatmaya
  // basarken büyüteç açılırdı. Büyütme yolu kapanmıyor, denetimlerin tam
  // ekran düğmesine devrediliyor.
  if (!videoMu) {
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
  }

  const actionsContainer = document.createElement("div");
  actionsContainer.className = "chat-media-actions";

  const dl = document.createElement("button");
  dl.type = "button";
  dl.className = "chat-media-act";
  dl.textContent = "İndir";
  dl.addEventListener("click", (e) => {
    e.stopPropagation();               // indirme büyüteci açmasın
    downloadImage(src, `${imageId}.${videoMu ? "mp4" : "png"}`);
  });
  dl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") e.stopPropagation();
  });

  // "REFERANS AL" VİDEODA YOK: referans yolu bir PNG bekliyor
  // (`app._output_png_path` uzantıyı çakılı tutuyor ve bir video id'sinde 404
  // veriyor) ve bir MP4'ü ilk kare olarak göndermenin karşılığı da yok.
  // Düğmeyi çizip sonra 404 göstermek, kullanıcıya olmayan bir yol
  // göstermek olurdu.
  if (videoMu) {
    actionsContainer.append(dl);
  } else {
    const refBtn = document.createElement("button");
    refBtn.type = "button";
    refBtn.className = "chat-media-act";
    refBtn.textContent = "Referans Al";
    refBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof setGallerySourceById === "function") {
        setGallerySourceById(imageId, caption);
      }
    });
    refBtn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") e.stopPropagation();
    });
    actionsContainer.append(dl, refBtn);
  }
  fig.append(media, num, actionsContainer);
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
  // Tür BİR KEZ sorulup ızgaranın tamamına veriliyor: bir sonuç kaydının
  // bütün kareleri aynı üretimden geliyor, yani kare başına sormak aynı
  // cevabı N kez hesaplamak olurdu.
  const videoMu = sonucVideoMu(msg);
  // Izgara sütunu ADETTEN geliyor: tek görsel yarım kart olarak değil geniş
  // çizilmeli (referans ekranın `.media.r32` kartı). Üst sınır SUNUCUDA
  // (`models.MAX_IMAGES_PER_RUN`), burada aynalanacak bir şey yok — CSS
  // yalnızca "1 mi, 2 mi, daha fazla mı" sorusunu soruyor.
  grid.dataset.count = String(ids.length);
  // ORAN da bir kez sorulup ızgaranın tamamına veriliyor (türle aynı gerekçe).
  // Video modellerinde `params.size` ZATEN bir oran jetonu ("16:9"/"9:16",
  // `catalog.VIDEO_ASPECT_RATIOS`); görselde "1024x1024" biçiminde ve orada
  // hiç okunmuyor.
  const oran = (msg.params || {}).size || "";
  ids.forEach((id, i) => grid.appendChild(resultThumb(id, i, caption, videoMu, oran)));
  div.appendChild(grid);

  $("chat-log").appendChild(div);
  syncEmptyState();
  scrollMessageIntoView(div);
  return div;
}

// ── Arena satırı ─────────────────────────────────────────────────────
//
// Bir arena turu, dökümde SÜTUNLARI olan TEK satır; kalıcılıkta ise sütun
// başına AYRI bir `result` kaydı (hepsi aynı `params.arena_id`). Ayrı
// kayıtlar, çünkü bir kaydın `image_ids` tavanı bir TURUN çıktısı kadar
// (`models.MAX_IMAGES_PER_RUN`) ve bir kayıtta tek `model` alanı var — dört
// modeli tek kayda sıkıştırmak ikisini de bozardı.
//
// Satırı ARDIŞIKLIK topluyor (`renderThread`): kayıtlar tura ait sırayla
// yazılıyor ve araya başka bir tur giremiyor (üretim sırasında `#go` kilitli).

/** Sütun künyesi: "Nano Banana 2 · 2:3 · 2K · 12 kredi". */
function arenaColumnCaption(msg, model) {
  const p = msg.params || {};
  const parts = [(model && (model.short_label || model.label)) || p.model || "Model"];
  if (p.size) parts.push(SIZE_LABELS[p.size] || p.size);
  if (p.quality) parts.push(QUALITY_LABELS[p.quality] || p.quality);
  return parts.join(" · ");
}

/** Turun kazananını işaretler: uç + satırdaki basılı durum.
 *
 * İŞARETİN TEK KAYNAĞI `history.json` (bkz. storage.set_arena_winner) — döküm
 * kaydına ikinci bir kopya yazılsaydı oturum kaydedilmeyen bir turda ikisi
 * ayrışırdı. Bu yüzden düğme önce ucu çağırıyor, ancak BAŞARIDA basılı hâle
 * geçiyor: ekranda gösterilen şey diskte olanla aynı kalıyor.
 */
async function markArenaWinner(row, arenaId, imageId) {
  try {
    await chatApi(`/api/arena/${encodeURIComponent(arenaId)}/winner`,
                  { method: "POST", body: { image_id: imageId } });
  } catch (e) {
    chatStatus(`Kazanan işaretlenemedi: ${e.message}`);
    return;
  }
  syncArenaWinner(row, imageId);
  // Galeri rozeti aynı kaydı okuyor; tazelenmezse işaret orada bir sonraki
  // yenilemeye kadar görünmez kalırdı.
  if (typeof loadHistory === "function") loadHistory();
}

/** Satırdaki basılı durumun TEK yazarı: tur başına tek kazanan. */
function syncArenaWinner(row, imageId) {
  for (const btn of row.querySelectorAll(".arena-win")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.imageId === imageId));
  }
}

/** Diskteki işareti satıra yansıtır. Sessiz başarısızlık BİLİNÇLİ: işaret bir
 * tercih göstergesi, veri değil — uç düşerse satır işaretsiz çiziliyor ve
 * kullanıcı yeniden işaretleyebiliyor. */
async function refreshArenaWinner(row, arenaId) {
  try {
    const { images } = await chatApi(`/api/arena/${encodeURIComponent(arenaId)}`);
    const kazanan = (images || []).find((r) => r.arena_win);
    if (kazanan) syncArenaWinner(row, kazanan.id);
  } catch (e) { /* işaretsiz kalıyor */ }
}

/** Bir sütunun gövdesi: künye + görseller + "Kazanan" düğmesi. */
function arenaColumn(row, msg, arenaId) {
  const p = msg.params || {};
  const model = (typeof imageModels !== "undefined" ? imageModels : [])
    .find((m) => m.id === p.model);
  const caption = arenaColumnCaption(msg, model);

  const col = document.createElement("div");
  col.className = "arena-col";

  const head = document.createElement("span");
  head.className = "chat-role";
  head.textContent = caption;
  col.appendChild(head);

  const ids = msg.image_ids || [];
  const grid = document.createElement("div");
  grid.className = "chat-result-grid";
  grid.dataset.count = String(ids.length);
  // Arena bugün YALNIZ görsel (video modunda #arena-pick gizli, bkz.
  // style.css) — yani bu değer bugün her zaman false. Sabit `false` yazmak
  // yerine kaydın kendisine sormak, arena bir gün video da koşturursa
  // burada hatırlanacak bir şey bırakmıyor.
  const videoMu = sonucVideoMu(msg);
  // ORAN DA GEÇİYOR, aynı gerekçeyle: `videoMu`yu kayda sormak ama oranı
  // sormamak yarım bir hazırlık olurdu — arena bir gün video koşturursa kart
  // kare çizilir, klip şeritlenir ve `.video` sınıfı hiç eklenmediği için
  // indirme hapı denetim çubuğunun üstünde kalırdı. `p.size` zaten burada.
  ids.forEach((id, i) => grid.appendChild(resultThumb(id, i, caption, videoMu, p.size || "")));
  col.appendChild(grid);

  // Kazanan işareti: iki durumlu düğmenin depodaki standart deseni
  // (`aria-pressed`). Elenen sonuç SİLİNMİYOR — işaret bir tercih kaydı.
  if (arenaId && ids.length) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-ghost arena-win";
    btn.dataset.imageId = ids[0];
    btn.setAttribute("aria-pressed", "false");
    btn.textContent = "Kazanan";
    btn.addEventListener("click", () => markArenaWinner(row, arenaId, ids[0]));
    col.appendChild(btn);
  }
  return col;
}

/** Bir arena turunun sütunlarını tek satır olarak döküme basar. */
function appendArenaRow(kayitlar) {
  const arenaId = ((kayitlar[0] || {}).params || {}).arena_id || "";
  const row = document.createElement("div");
  row.className = "chat-result arena-row";
  row.dataset.count = String(kayitlar.length);
  if (arenaId) row.dataset.arenaId = arenaId;
  for (const msg of kayitlar) row.appendChild(arenaColumn(row, msg, arenaId));

  $("chat-log").appendChild(row);
  syncEmptyState();
  scrollMessageIntoView(row);
  if (arenaId) refreshArenaWinner(row, arenaId);
  return row;
}

/** Dökümü çizer: ardışık arena sütunları TEK satırda toplanıyor.
 *
 * AYRI fonksiyon çünkü İKİ yer çiziyor (oturum açma ve — ileride — dökümün
 * yeniden kurulduğu her yer); döngüyü iki kez yazmak, gruplamanın birinde
 * sessizce eksik kalması demekti.
 */
function renderThread(mesajlar) {
  for (let i = 0; i < mesajlar.length; i++) {
    const m = mesajlar[i];
    const aid = m.role === RESULT_ROLE ? (m.params || {}).arena_id : "";
    if (aid) {
      const grup = [];
      while (i < mesajlar.length && mesajlar[i].role === RESULT_ROLE
             && (mesajlar[i].params || {}).arena_id === aid) {
        grup.push(mesajlar[i]);
        i += 1;
      }
      i -= 1;                     // döngü sayacı grubun SON öğesinde kalmalı
      appendArenaRow(grup);
    } else if (m.role === RESULT_ROLE) appendResult(m);
    else if (m.role === "user") appendUser(m);
    else appendBot(m.content);
  }
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
  if (parsed.options) {
    // `null` olabiliyor (çizilebilir madde yok) — diğer iki panelin çağrı
    // yeriyle aynı şekil; `appendChild(null)` TypeError atardı.
    const panel = renderOptions(parsed);
    if (panel) div.appendChild(panel);
  }
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
  // `#go`nun tek yazarı core.js'teki syncGoGate: mod, meşguliyet, sohbet
  // yapılandırması ve seçili görsel modelini BİRLİKTE görüyor. Burada ayrı
  // yazılsa iki sahip olurdu ve hangisinin son sözü söylediği çağrı sırasına
  // kalırdı — Yönetmen modunda kapı bir an açılıp kapanıyordu.
  if ($("go")) { runBusy = busy; syncGoGate(); }
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
  // `content` + `display`, sonuç kayıtları HARİÇ. Gerekçe "onlar modele
  // gitmiyor" idi ve ARTIK DOĞRU DEĞİL (sunucu onları kısa bir nota çeviriyor,
  // bkz. models.wire_messages); sayaç yine de onları saymıyor çünkü sunucunun
  // kapısı da saymıyor — iki taraf aynı şeyi ölçmek ZORUNDA, yoksa istemci
  // "yer var" derken sunucu 422 döndürürdü. Notun ağırlığı sunucuda sabit ve
  // sınırlı (MAX_RESULT_NOTE_CHARS × MAX_CHAT_RESULTS).
  // `m.content.length` yazılamaz: sonuç kaydında `content` HİÇ YOK ve okumak
  // TypeError atardı — gönderim tümden ölürdü.
  const used = chatThread.reduce(
    (n, m) => (m.role === RESULT_ROLE ? n
      : n + (m.content || "").length + (m.display || "").length), 0);
  if (used + message.length + label.length > MAX_CHAT_TOTAL_CHARS) {
    chatStatus("Sohbet çok uzadı — soldaki \"Yeni sohbet\" ile devam et. (Son prompt'u "
      + "kaybetmemek için önce prompt bloğundaki üret düğmesine bas.)");
    return false;
  }

  const turn = { role: "user", content: message };
  if (label) turn.display = label;
  chatThread.push(turn);
  const bubble = appendUser(turn);
  input.value = "";
  // Dört kapının da ARDINDA: kutunun boşaldığı an gönderimin kabul edildiği
  // andır ve composer ancak o zaman küçülmeli (core.js composerKuculsun).
  // `chatBusy`, boş mesaj, dolu konuşma ve toplam karakter kapıları yukarıda
  // `return false` ile çıkıyor — hiçbiri buraya ulaşmıyor.
  composerKuculsun();
  chatStatus("");
  setChatBusy(true);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // MODEL TEL ÜZERİNE ÇIKIYOR (v0.7): şerit gerçek bir seçim ve sunucu
      // onu `chat_providers`e veriyor. `undefined` alan `JSON.stringify`
      // tarafından ATILIYOR, yani katalog henüz gelmemişse gövde eskisiyle
      // bayt bayt aynı kalıyor ve sunucu varsayılana düşüyor — `extra="forbid"`
      // altında `null` göndermek de geçerli, ama alanı hiç göndermemek bayat
      // bir sunucuyla da çalışıyor.
      body: JSON.stringify({ messages: chatThread,
                             model: currentChatModel ? currentChatModel.id : undefined }),
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
    // ÖLÇÜM geri yazmanın parçası: gönderim `rows`u 1'e indirdi ve satır içi
    // `height` o dar hâlde donmuş durumda. `autoGrow` çağrılmazsa geri konan
    // çok satırlı mesaj tek satıra kırpılmış görünür — kullanıcı metnini
    // kaybettiğini sanır, oysa yalnız kutu ölçülmemiştir.
    if (!label) { input.value = message; autoGrow(input); }
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
  // Kartın TEK içeriği bekleme kutusu: üretilecek görselin yerini tutuyor ve
  // pixel-canvas ile titriyor (static/pixel-canvas.js). Eskiden burada
  // taşınabilir bir yüzde çubuğu da vardı — kaldırıldı, gerekçesi core.js'te.
  const shimmer = document.createElement("div");
  shimmer.className = "pending-shimmer";
  const pixels = document.createElement("pixel-canvas");
  pixels.setAttribute("data-manual", "");   // tetik fare değil, üretimin kendisi
  shimmer.appendChild(pixels);
  pendingDiv.appendChild(shimmer);
  $("chat-log").appendChild(pendingDiv);
  // DOM'a girdikten SONRA başlatılıyor: bileşen ilk karede kendini
  // getBoundingClientRect ile ölçüyor, bağlanmamış bir düğümde o ölçü 0'dır
  // ve tek bir piksel bile üretilmez.
  if (typeof pixels.start === "function") pixels.start();
  // Kaydırma HEDEFİ artık bekleme kartı, `appendUser`ın kaydırdığı baloncuk
  // değil. Eski bekleme satırı 72px'ti, baloncuğun altında kendiliğinden
  // görünüyordu; shimmer kutusu ile kart bir görsel yüksekliğinde, yani
  // baloncuğa kaydırıldığında kutunun altı görünür şeridin dışında kalıyor
  // (#composer akışın üstünde yüzüyor). İzlenecek şey bekleme, son söz onun.
  scrollMessageIntoView(pendingDiv);

  return { turn, bubble, pendingDiv };
}

/** Arena turunu döküme AÇAR: tek kullanıcı repliği + N sütunlu bekleme satırı.
 *
 * `beginResultTurn`in arena kardeşi. Kota N+1 sorularak isteniyor: turu AÇAN
 * ve KAPATAN aynı kapıdan geçmek zorunda (bkz. transcriptHasRoom), yoksa
 * sütunları döküme sığmayan bir tur açılırdı.
 *
 * Bekleme kutusu SÜTUN BAŞINA ayrı: `pixel-canvas` singleton değil, her örnek
 * kendi rAF döngüsünü taşıyor ve DOM'a girdikten SONRA başlatılıyor (bağlanmamış
 * düğümde ölçü 0'dır, tek piksel bile üretilmez).
 */
function beginArenaTurn(prompt, sutunlar) {
  if (!sutunlar.length || !transcriptHasRoom(sutunlar.length + 1)) return null;
  const turn = { role: "user", content: prompt.slice(0, MAX_CHAT_MSG_CHARS) };
  chatThread.push(turn);
  const bubble = appendUser(turn);

  const row = document.createElement("div");
  row.className = "chat-result arena-row is-pending";
  row.dataset.count = String(sutunlar.length);

  const slots = sutunlar.map((s) => {
    const col = document.createElement("div");
    col.className = "arena-col";
    const head = document.createElement("span");
    head.className = "chat-role";
    // Künye BEKLERKEN de tam: hangi modelin hangi ayarla koştuğu, sonuç
    // gelmeden önce de görünüyor — kolonlar birbirine karışmasın.
    head.textContent = arenaColumnCaption(
      { params: { size: s.size, quality: s.quality, model: s.model.id } }, s.model);
    const shimmer = document.createElement("div");
    shimmer.className = "pending-shimmer";
    const pixels = document.createElement("pixel-canvas");
    pixels.setAttribute("data-manual", "");
    shimmer.appendChild(pixels);
    col.append(head, shimmer);
    row.appendChild(col);
    return { col, pixels };
  });

  $("chat-log").appendChild(row);
  for (const s of slots) {
    if (typeof s.pixels.start === "function") s.pixels.start();
  }
  scrollMessageIntoView(row);
  return { turn, bubble, pendingDiv: row, row, slots };
}

/** Bir sütun sonuçlandı: bekleme kutusunun yerine gerçek sütun geçiyor.
 *
 * Sütunu `arenaColumn` kuruyor — yani CANLI satır ile yeniden yüklenen satır
 * AYNI çizim yolundan geçiyor. İki ayrı çizim, ikisinin zamanla ayrışması
 * demekti (künye bir yerde krediyi yazar, öteki yazmaz).
 */
function fillArenaSlot(pending, index, msg, arenaId) {
  const slot = pending && pending.slots && pending.slots[index];
  if (!slot) return;
  const yeni = arenaColumn(pending.row, msg, arenaId);
  slot.col.replaceWith(yeni);
  slot.col = yeni;
}

/** Bir sütun DÜŞTÜ: hata o sütunda kalıyor, tur devam ediyor.
 *
 * Arenanın istemci fan-out'uyla kazandığı şey tam olarak bu: tek istekte
 * fan-out olsaydı bir sağlayıcının 502'si turun tamamını götürürdü.
 */
function failArenaSlot(pending, index, mesaj) {
  const slot = pending && pending.slots && pending.slots[index];
  if (!slot) return;
  const not = document.createElement("p");
  not.className = "arena-fail";
  not.setAttribute("role", "status");
  not.textContent = mesaj;
  const shimmer = slot.col.querySelector(".pending-shimmer");
  if (shimmer) shimmer.replaceWith(not);
  else slot.col.appendChild(not);
}

/** Arena turunu KAPATIR: sütun başına bir `result` kaydı, TEK kalıcılaştırma.
 *
 * Kayıtlar `chatThread`e ARDIŞIK yazılıyor — dökümü yeniden çizen `renderThread`
 * satırı tam olarak bu ardışıklıktan topluyor.
 *
 * Hiç sütun tutmadıysa tur geri alınıyor (`run`ın "başarısız tur geçmişte
 * kalmaz" kuralı): cevapsız bir kullanıcı repliği kalırdı.
 */
async function finishArenaTurn(pending, kayitlar) {
  if (!pending) return;
  if (!kayitlar.length) { dropPendingTurn(pending); return; }
  pending.done = true;
  pending.row.classList.remove("is-pending");
  // Rolü BURASI yazıyor: `RESULT_ROLE` bu dosyanın sabiti ve core.js'in onu
  // ikinci kez tanımlaması (ya da dizeyi elle yazması) iki gerçek doğururdu.
  for (const kayit of kayitlar) {
    chatThread.push({ role: RESULT_ROLE, ...kayit });
  }
  await persistThread();
}

function dropPendingTurn(pending) {
  if (!pending || pending.done) return;
  chatThread = chatThread.filter((m) => m !== pending.turn);
  if (pending.bubble) pending.bubble.remove();
  // Kartı silmek yeterli: shimmer kutusu onun İÇİNDE, birlikte gidiyor ve
  // bileşenin `disconnectedCallback`i rAF döngüsünü kapatıyor.
  if (pending.pendingDiv) pending.pendingDiv.remove();
  syncEmptyState();
}

async function appendResultTurn(pending, imageIds, params) {
  if (!pending || !transcriptHasRoom(1)) return;
  if (!imageIds.length) { dropPendingTurn(pending); return; }
  pending.done = true;
  if (pending.pendingDiv) pending.pendingDiv.remove();
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
    $("pref-guncelleme").checked = p.guncelleme_kontrolu !== false;
    // `|| ""`: alanı hiç tanımayan bayat bir sunucu `undefined` döndürür ve
    // `undefined` bir textarea'ya yazıldığında ekranda "undefined" YAZAR.
    $("director-guidance").value = p.director_guidance || "";
    if (p.theme) {
      applyTheme(p.theme);
      const radio = document.querySelector(`input[name="theme"][value="${p.theme}"]`);
      if (radio) radio.checked = true;
    }
  } catch {
    // Tercih alınamadı: anahtarın GÖRÜNEN hâli varsayılana (açık) düşüyor,
    // ama yazımı sunucu zaten kendisi kapıyor — burada fail-open yok.
    $("pref-autosave").checked = true;
    $("pref-guncelleme").checked = true;
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

/** Kalıcı yönlendirmeyi yazar. Anında yazım DEĞİL, düğmeye bağlı.
 *
 * `saveAutosavePref`ten AYRILIYOR ve sebebi tür farkı: bir onay kutusunun
 * değeri tek bit, yazım reddedilirse kutu geri döner ve kullanıcı hiçbir şey
 * kaybetmez. Burada değer uzun bir serbest metin — her tuş vuruşunda POST
 * atmak hem gereksiz, hem de sessizce başarısız olan bir yazım kullanıcının
 * yazdığını kaybettirir. Metin alanının kalıbı #settings-modal'ın "Kaydet"i.
 *
 * Ekrandaki değer SUNUCUNUN döndürdüğünden kuruluyor (autosave deseninin
 * aynısı): sunucu kırpmışsa kullanıcı kırpılmış hâli görür, yani kaydedilenle
 * ekranda duran ayrışmaz.
 */
async function saveDirectorGuidance() {
  const metin = $("director-guidance").value;
  // Düğme UÇUŞ SIRASINDA kilitli (`#settings-save`ın kalıbı): iki tık iki POST
  // atıyordu ve ikisi de dönüşte AYNI iki alana yazıyor — `textarea`ya ve durum
  // satırına. Sonuç yarışa kalıyordu: ilki ağda düşüp ikincisi başarırsa
  // kullanıcı başarılı bir yazımın üstünde "Kaydedilemedi: …" okuyabiliyordu.
  // `finally` şart — hata dalında da açılmalı, yoksa bir ağ hatası düğmeyi
  // temelli kilitler.
  $("director-save").disabled = true;
  $("director-status").textContent = "Kaydediliyor…";
  try {
    const p = await chatApi("/api/prefs",
      { method: "POST", body: { director_guidance: metin } });
    $("director-guidance").value = p.director_guidance || "";
    $("director-status").textContent = p.director_guidance
      ? "Yönlendirme kaydedildi — bundan sonraki her turda geçerli."
      : "Yönlendirme temizlendi.";
  } catch (e) {
    // Metin KUTUDA BIRAKILIYOR: kullanıcının yazdığını bir ağ hatası yüzünden
    // silmek, sendChat'in başarısızlık dalının reddettiği şeyin aynısı.
    $("director-status").textContent = `Kaydedilemedi: ${e.message}`;
  } finally {
    $("director-save").disabled = false;
  }
}

// "Yeni sürüm çıkınca haber ver" anahtarı — yukarıdaki desenin birebir eşi.
// Ayrı bir fonksiyon çünkü geri bildirim metni farklı: kullanıcının kapattığı
// şey bir kayıt davranışı değil, uygulamanın AĞA ÇIKMASI ve onayın karşılığını
// görmesi gerekiyor.
async function saveGuncellemePref() {
  const on = $("pref-guncelleme").checked;
  try {
    const p = await chatApi("/api/prefs",
      { method: "POST", body: { guncelleme_kontrolu: on } });
    $("pref-guncelleme").checked = p.guncelleme_kontrolu !== false;
    $("settings-status").textContent = p.guncelleme_kontrolu
      ? "Yeni sürüm çıkınca haber verilecek."
      : "Sürüm kontrolü kapatıldı — uygulama bu iş için ağa çıkmayacak.";
    // Satır ANINDA gizlensin: kontrolü kapatıp açık kalan bir bildirim,
    // anahtarın işe yaramadığı izlenimi verir.
    if (!p.guncelleme_kontrolu) $("settings-update").hidden = true;
  } catch (e) {
    $("pref-guncelleme").checked = !on;   // gerçekleşmeyen değişikliği geri al
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
    renderThread(chatThread);
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
$("pref-guncelleme").addEventListener("change", saveGuncellemePref);

// ── Yönetmen ayarları çekmecesi ──────────────────────────────────────
// İKİNCİ TIK KAPATIYOR — #specs-btn'in kalıbının aynısı (core.js). Açık bir
// panelin çipine yeniden dokunmak onu kapatmalı, yoksa `openSheet` aynı paneli
// kapatıp yeniden açar ve kullanıcı bir titreme görür.
//
// `aria-expanded`ın SIFIRLANMASI burada DEĞİL `closeSheets`te: kapanışın beş
// kapısı var (× · perde · Escape · Android geri · başka bir panelin açılması)
// ve her birine ayrı ayrı yazmak birini unutmak demekti (bkz. core.js'in
// #arena-btn dersi).
$("director-btn").addEventListener("click", () => {
  const willOpen = !$("director-sheet").classList.contains("open");
  closeSheets();
  if (willOpen) {
    openSheet("director-sheet");
    // SIRA BAĞLAYICI: `openSheet` içinde `closeSheets` koşuyor ve o
    // `sheetTetik`i null'a çekiyor — atama ÖNCE yapılsaydı odak iadesi hiç
    // çalışmazdı (openModelSheet'in aynı mandalı).
    sheetTetik = $("director-btn");
    $("director-btn").setAttribute("aria-expanded", "true");
    // Durum satırı her AÇILIŞTA sıfırlanıyor (`openSettings`ın kalıbı).
    // Yoksa eski "Yönlendirme kaydedildi" satırı panelde asılı kalıyor ve
    // çekmece Kaydet'e basılmadan kapatılıp yeniden açıldığında KAYDEDİLMEMİŞ
    // metnin yanında duruyordu — kullanıcı yönlendirmesinin etkin olduğunu
    // sanırken `/api/chat` hâlâ eski metni gönderiyor olurdu.
    $("director-status").textContent = "";
    // Odak BAŞLIĞA, metin alanına DEĞİL: Android'de klavye alttan açılıyor ve
    // bir metin alanına odaklanmak paneli yutuyor (settings.js'in ölçülmüş
    // dersi, `#set-provider` yerine `set-provider` seçilmesinin sebebi).
    // `tabIndex = -1` şart: `<h2>` odaklanabilir bir öğe değil.
    const head = $("director-sheet").querySelector(".sheet-head h2");
    if (head) { head.tabIndex = -1; head.focus(); }
  }
});
$("director-close").addEventListener("click", closeSheets);
$("director-save").addEventListener("click", saveDirectorGuidance);


syncEmptyState();
loadChats();
loadPrefs();

