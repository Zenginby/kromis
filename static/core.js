// Lumeo — üretim akışı: prompt, referans görseller, ilerleme, onay penceresi.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js → viewer.js → chat.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı settings.js'in dibinde toplanır.

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const ACCEPTED_UPLOAD_TYPES = ["image/png", "image/jpeg", "image/webp"];

// Sunucudaki models.MAX_PROMPT_CHARS ile AYNI olmak zorunda (MAX_EDIT_IMAGES
// geleneği): yönetmenin ürettiği prompt buraya sığmıyorsa forma yazmak yerine
// kısaltılması isteniyor — sunucu aksi halde 422 döner.
const MAX_PROMPT_CHARS = 4000;

// ── Çalışma alanı sekmeleri ─────────────────────────────────────────
// Kabuk sorumluluğu, sohbete özel DEĞİL: bu yüzden chat.js'te değil burada.
// chat.js yalnızca showView("image") çağırıyor, böylece sadece kendinden
// önceki dosyalara bakan bir yaprak kalıyor ve yükleme sırası bozulmuyor.
let currentMode = "image";
// Ray bölümü: "studio" (tek döküm) | "media" (galeri) | "library" (bindirme varlıkları) | "tools" (görünüm + paletler).
let currentSection = "studio";

/** Bitişik segmentin kayan dolgusu: aktif düğmenin ölçüsünden okunuyor. */
function syncTabThumb() {
  const thumb = $("view-tabs-thumb");
  const tab = currentMode === "image" ? $("tab-image") : $("tab-chat");
  if (!thumb || !tab) return;
  thumb.style.width = `${tab.offsetWidth}px`;
  thumb.style.transform = `translateX(${tab.offsetLeft}px)`;
}

function setMode(modeName) {
  const mode = modeName === "director" ? "director" : "image";
  if (currentSection !== "studio") showSection("studio");
  currentMode = mode;
  $("composer").dataset.mode = mode;
  $("tab-image").setAttribute("aria-pressed", mode === "image" ? "true" : "false");
  $("tab-chat").setAttribute("aria-pressed", mode === "director" ? "true" : "false");
  $("tab-image").classList.toggle("active", mode === "image");
  $("tab-chat").classList.toggle("active", mode === "director");

  const prompt = $("prompt");
  if (prompt) {
    if (mode === "image") {
      prompt.placeholder = "Ne üretmek istiyorsun? Görsel tarifi, renk veya tarz yaz…";
    } else {
      prompt.placeholder = "Yönetmen'e sor veya fikir danış… (öğeleri değiştir, sahne ekle)";
    }
  }
  renderSource();
  syncTabThumb();
  // Kapı MODA bağlı: Yönetmen modunda sohbet yapılandırması, Görsel modunda
  // seçili modelin durumu karar veriyor. Mod değişince yeniden sorulmalı.
  // `typeof` guard'ı SIRA yüzünden: setMode bu dosyanın üst düzeyinde de
  // çağrılabiliyor ve syncGoGate aşağıda tanımlı (function bildirimi hoisted
  // ama `currentModel` gibi `let`ler değil) — bkz. dosya başındaki not.
  if (typeof syncGoGate === "function") syncGoGate();
}

$("tab-image").addEventListener("click", () => setMode("image"));
$("tab-chat").addEventListener("click", () => setMode("director"));
window.addEventListener("resize", syncTabThumb);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncTabThumb);

// ══ Flow kabuğu ══════════════════════════════════════════════════════
const APP = document.querySelector(".app");

// Ray bölümü → görünüm eşlemesi.
const SECTION_VIEWS = { studio: "view-studio", media: "view-media",
                        library: "view-library", tools: "view-tools" };

function showSection(name) {
  currentSection = name;
  const studio = name === "studio";
  for (const [key, viewId] of Object.entries(SECTION_VIEWS)) {
    if (viewId && $(viewId)) $(viewId).hidden = key !== name;
  }
  if ($("composer")) $("composer").hidden = !studio;
  for (const key of Object.keys(SECTION_VIEWS)) {
    const el = $(`rail-${key}`);
    if (!el) continue;
    const on = key === name;
    el.classList.toggle("active", on);
    if (on) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  }
  if (studio) syncTabThumb();
}

// ══ Android donanım/jest geri tuşu ══════════════════════════════════
//
// MainActivity.kt'nin `onBackPressed`i YALNIZ bunu çağırıyor. `true` = "ele
// aldım", `false` = "uygulamadan çıkılabilir" (Kotlin o noktada çıkış uyarısını
// gösteriyor).
//
// NEDEN BURADA, Kotlin'de değil: sıralama eskiden Kotlin'in içine gömülü ÜÇ CSS
// seçicisiydi (`.sheet.open`, `.modal:not([hidden])`, `.popover:not([hidden])`)
// ve index.html'in yapısına dizeyle bağlıydı — koruyan hiçbir test yoktu. İki
// somut kırılma üretmişti:
//   • sohbet menüleri (`.chat-menu`, `#chats-kebab-menu`) üç seçicinin
//     HİÇBİRİNE uymuyor, yani menü açıkken geri uygulamayı kapatıyordu,
//   • bölüm ve klasör gezintisi geri yığınında hiç yok (showSection ve
//     folders.js `goUp` geçmişe girmiyor), yani Medya'dayken ya da iç içe bir
//     klasördeyken geri DOĞRUDAN çıkışa gidiyordu.
// Karar JS'e taşınınca hem ikisi de kapandı hem sözleşme test edilebilir bir
// yere geldi (tests/test_mobile.py).
//
// `webView.canGoBack()` hâlâ KULLANILMIYOR: bu tek sayfalık bir uygulama,
// modal ve paneller gezinme geçmişine hiç girmiyor.
window.geriTusu = function () {
  // 1) Açık katman. Hangisinin kapanacağına KARIŞILMIYOR: var olan Escape
  //    şelalesi (core.js aşağısı, folders.js, assets.js, viewer.js) önceliği
  //    `stopImmediatePropagation` ile zaten çözüyor. Burada ikinci bir öncelik
  //    sırası kurmak iki mantığın ayrışmasına ve "geri bazen yanlış paneli
  //    kapatıyor" hatasına açık olurdu.
  const acik = document.querySelector(".sheet.open")
            || document.querySelector(".modal:not([hidden])")
            || document.querySelector(".popover:not([hidden])")
            || document.querySelector(".chat-menu:not([hidden])")
            || document.querySelector("#chats-kebab-menu:not([hidden])");
  if (acik) {
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", bubbles: true, cancelable: true,
    }));
    return true;
  }

  // 2) Klasörden bir üste. `goUp()`u ikinci bir çağrandan çağırmak yerine var
  //    olan düğme tıklanıyor (folders.js): kırıntı ve başlık tazelemesi böylece
  //    bedava geliyor ve tek yol kalıyor.
  //
  //    `currentSection === "media"` MUHAFAZASI ŞART, süs değil. Düğmenin
  //    `hidden`i yalnız `currentFolder`ı anlatıyor (folders.js `syncFolderView`)
  //    ve `showSection` onu HİÇ temizlemiyor: bir alt klasördeyken Stüdyo'ya
  //    geçip geri basmak, GÖRÜNMEYEN bir düğmeyi tıklayıp `true` döndürüyordu —
  //    ekranda hiçbir şey olmuyor, üstelik çıkış yolu klasör yığını boşalana
  //    kadar erişilemez kalıyordu. Arama açıkken de aynısı: `.gallery-head`
  //    tümden gizli ama düğmenin kendi `hidden`i hâlâ `false`.
  const klasorGeri = $("folder-back");
  if (currentSection === "media" && klasorGeri && !klasorGeri.hidden) {
    klasorGeri.click();
    return true;
  }

  // 3) Stüdyo dışı bir bölüm → Stüdyo.
  if (currentSection !== "studio") {
    showSection("studio");
    return true;
  }

  return false;
};

$("rail-studio").addEventListener("click", () => showSection("studio"));
$("rail-media").addEventListener("click", () => showSection("media"));
// A1/A2 (Adım 7b): Kütüphane ve Araçlar artık kendi görünümleri. Eskiden
// library-btn / palette-btn'e programatik .click() atılıyordu — kapalı bir
// panelin gizli düğmesi. Kütüphane grid'inin tazelenmesi assets.js'te
// (aynı düğmeye ikinci dinleyici, plus-menü kalıbı).
$("rail-library").addEventListener("click", () => showSection("library"));
$("rail-tools").addEventListener("click", () => showSection("tools"));

$("rail-collapse").addEventListener("click", () => {
  const on = APP.classList.toggle("rail-collapsed");
  $("rail-collapse").setAttribute("aria-pressed", on ? "true" : "false");
  syncTabThumb(); // composer genişliği değişti → kayan dolgu yeniden ölçülmeli
});

// ── Slide-over'lar ──
function closeSheets() {
  for (const el of document.querySelectorAll(".sheet.open")) el.classList.remove("open");
  $("chat-sidebar-toggle").setAttribute("aria-expanded", "false");
  $("specs-btn").setAttribute("aria-expanded", "false");
}

// Panel açmanın TEK kapısı: dört panel aynı perdeyi ve aynı sağ/sol şeridi
// paylaşıyor — önce hepsi kapanır, sonra istenen açılır. İkisi birlikte
// açılırsa üst üste biner ve `Esc`in hangisini kapattığı belirsizleşir.
function openSheet(id) {
  closeSheets();
  $(id).classList.add("open");
}

$("specs-btn").addEventListener("click", () => {
  const willOpen = !$("specs-sheet").classList.contains("open");
  closeSheets();
  if (willOpen) {
    openSheet("specs-sheet");
    $("specs-btn").setAttribute("aria-expanded", "true");
  }
});
$("specs-close").addEventListener("click", closeSheets);
$("sessions-close").addEventListener("click", closeSheets);
$("shell-scrim").addEventListener("click", closeSheets);
// `confirm-modal` guard'ı ŞART: onay penceresi bir panelin ÜSTÜNDE açılıyor
// (palet kaydetme). Bu dinleyici confirm'in stopImmediatePropagation'ından
// ÖNCE kayıtlı, yani o çağrı bunu durduramaz — guard'sız tek Escape iki
// katmanı birden kapatırdı.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && document.querySelector(".sheet.open")) closeSheets();
});

// ── (+) menüsü ──
$("plus-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  const open = $("plus-menu").hidden;
  $("plus-menu").hidden = !open;
  $("plus-btn").setAttribute("aria-expanded", open ? "true" : "false");
});
function closePlusMenu() {
  $("plus-menu").hidden = true;
  $("plus-btn").setAttribute("aria-expanded", "false");
}
document.addEventListener("click", (e) => {
  if (!e.target.closest(".plus-wrap")) closePlusMenu();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePlusMenu(); });
// Menüdeki düğmeler kendi dinleyicilerini folders.js'te kuruyor; burada yalnız
// menünün kapanması eklenir (aynı düğümde birden çok dinleyici sorun değil).
// media-pick-btn de burada: menü kapanmazsa modalın ARKASINDA açık kalıyor
// (ikisi de position:fixed, popover z-index'i modalınkinin altında) — plan B10.
for (const id of ["upload-btn", "extra-add-btn", "media-pick-btn"]) {
  $(id).addEventListener("click", closePlusMenu);
}

// ── Model kaydı ve yeteneğe göre kontroller ──
//
// Buradaki durum core.js'te yaşamak ZORUNDA: `syncSpecs()` bu dosyanın en
// üst düzeyinde çağrılıyor, yani aşağıdaki fonksiyonlar core.js YÜKLENİRKEN
// tanımlı olmalı. Ayrı bir dosyaya konsa ve core.js'ten SONRA yüklense
// üst düzey çağrı `const` bir tanıma çarpıp TDZ ReferenceError verirdi —
// dosyanın başındaki yükleme-sırası notunun tam olarak uyardığı kırılma.
// ÖNCE yüklenmesi de olmaz: orada `$` henüz tanımlı değil.
//
// TARİHÇE: burada `SIZE_RATIO` adında bir sabit vardı ve
// `azure_client.ALLOWED_SIZES`'ın elle tutulan bir AYNASIYDI. Çoklu modelde o
// ayna kaçınılmaz olarak bayatlar (Gemini'nin jetonları `WxH` biçiminde bile
// değil, doğrudan `16:9`). Artık oran da etiket de sunucudan geliyor:
// GET /api/settings → image_models[].sizes[].{value,label,ratio}.
let imageModels = [];      // sunucudan gelen katalog
let currentModel = null;   // seçili tanım (imageModels'ten bir öğe)
let runBusy = false;       // üretim sürüyor mu — #go kapısının bir girdisi

/** `<select>`i sunucudan gelen seçeneklerle yeniden kurar ve DEĞERİ TAŞIR.
 *
 * Taşıma sırası önemli ve üç kademeli:
 *   1. Birebir aynı `value` yeni modelde de varsa korunur — sessiz, çünkü
 *      kullanıcı için hiçbir şey değişmedi.
 *   2. Aynı `ratio` varsa ona geçilir (1024x1536 → 896x1344 gibi): kullanıcının
 *      seçtiği şey ORAN'dı, piksel sayısı sağlayıcının işi. Bu da sessiz.
 *   3. Hiçbiri yoksa modelin varsayılanına düşülür ve bu YÜKSEK SESLE söylenir.
 *
 * 3. kademe "sessiz sapma yasak" duruşunun devamı: palet sığmadığında
 * (`applied:false`) ve yönetmenin önerisi uygulanamadığında da aynısı yapılıyor.
 * Söylenmezse kullanıcı formda başka bir ayar görür ve sonucu açıklayamaz.
 */
function fillAxis(selectId, options, desired, fallback) {
  const el = $(selectId);
  const onceki = desired !== undefined ? desired : el.value;
  const oncekiRatio = [...el.options].find((o) => o.value === onceki)?.dataset.ratio;

  el.replaceChildren(...options.map((opt) => {
    const o = document.createElement("option");
    o.value = opt.value;
    // `textContent`: etiket sunucudan geliyor ve sunucu metni DOM'a yalnız bu
    // kapıdan giriyor (dosya genelindeki duruş).
    o.textContent = opt.label;
    if (opt.ratio) o.dataset.ratio = opt.ratio;
    return o;
  }));

  if (options.some((o) => o.value === onceki)) { el.value = onceki; return null; }
  const ayniOran = oncekiRatio && options.find((o) => o.ratio === oncekiRatio);
  if (ayniOran) { el.value = ayniOran.value; return null; }
  el.value = fallback;
  // Eski değer zaten boşsa (ilk çizim) bildirilecek bir sapma yok.
  return onceki ? onceki : null;
}

/** Bir eksenin kullanıcıya görünen adı. chat.js'in atlanan-öneri metni bunu
 * kullanıyor: aynı eksen bir modelde "Boyut", başkasında "Oran". */
function axisLabel(key) {
  const el = $(`label-${key}`);
  return el ? el.textContent.trim() : key;
}

/** Seçili modelin kredi maliyeti: model × boyut/kalite × adet.
 *
 * Kredi bilgisi ŞİMDİLİK yalnız METADATA — bakiye yok, satın alma yok,
 * zorlama yok. Gerçek bakiye geldiğinde değişecek yer TEK: aşağıdaki metne
 * " · N kalan" ekleniyor ve goBlockReason'a bir satır giriyor.
 *
 * Tarife SUNUCUDAN geliyor; istemci yalnız anahtar kuruyor, fiyat mantığı
 * kurmuyor — yoksa aynı hesap iki yerde birden yaşardı.
 */
function syncRunCost() {
  const el = $("run-cost");
  if (!currentModel) { el.hidden = true; return; }
  const tarife = currentModel.credits_by_quality || {};
  const birim = tarife[$("quality").value] ?? currentModel.credits;
  if (birim === undefined || birim === null) { el.hidden = true; return; }
  // `≈` bilerek: bu bir fatura değil, metadata — tilde bunu bir paragraf
  // açıklama yazmadan söylüyor.
  el.textContent = `≈ ${birim * Number($("n").value || 1)} kredi`;
  el.hidden = false;
}

/** #go'nun engel SEBEBİ — boş dize "engel yok".
 *
 * Bu fonksiyon `#go.disabled`ın TEK yazarı olmak için var. Öncesinde dört ayrı
 * yerden yazılıyordu (core.js iki, settings.js iki) ve chat.js beşinci bir
 * mantık taşıyordu; yani şimdiden iki çelişen sahip vardı. N sağlayıcıda bu
 * sürdürülemez.
 *
 * Sebep `title`'a da yazılıyor: kilitli bir düğmenin neden kilitli olduğunu
 * saklamak, #chat-gate'in reddettiği şeyin aynısı.
 */
function goBlockReason() {
  if (runBusy) return "Üretim sürüyor…";
  if (currentMode === "director") {
    return chatConfigured ? "" : "Sohbet modeli yapılandırılmadı.";
  }
  if (!imageModels.length) return "Model listesi alınamadı.";
  if (!currentModel) return "Model seçilmedi.";
  if (!currentModel.configured) {
    return `${currentModel.label} için anahtar yok — Ayarlar'dan ekle.`;
  }
  if (source && !currentModel.supports_edit) {
    return `${currentModel.label} referans görselle çalışmıyor.`;
  }
  return "";
}

function syncGoGate() {
  const sebep = goBlockReason();
  $("go").disabled = !!sebep;
  $("go").title = sebep || "Üret";
}

/** Seçili modeli uygular: eksenleri doldurur, notu yazar, tercihi kaydeder. */
function applyModel(id, { announce = true } = {}) {
  const model = imageModels.find((m) => m.id === id);
  if (!model) return;
  currentModel = model;
  $("model").value = model.id;

  const dusenler = [];
  const s = fillAxis("size", model.sizes, undefined, model.default_size);
  if (s) dusenler.push(`${axisLabel("size")} ${s}`);
  const q = fillAxis("quality", model.qualities, undefined, model.default_quality);
  if (q) dusenler.push(`${axisLabel("quality")} ${q}`);
  const adetler = Array.from({ length: model.max_n },
                             (_, i) => ({ value: String(i + 1), label: String(i + 1) }));
  const nn = fillAxis("n", adetler, undefined, "1");
  if (nn) dusenler.push(`${axisLabel("n")} ${nn}`);

  // Kalite ekseni OLMAYAN model (Gemini): satır tümden gizleniyor. Tel üzerinde
  // yine geçerli bir jeton gidiyor — katalogdaki sentetik "standard".
  $("spec-quality").hidden = !!model.quality_hidden;
  // Eksenin ADI modele göre değişiyor: piksel boyutu seçen model "Boyut",
  // oran seçen model "Oran" diyor. chat.js'in atlanan-öneri metni buradan okuyor.
  $("label-size").textContent =
    model.sizes.some((o) => o.value.includes("x")) ? "Boyut" : "Oran";

  // Şerit YALNIZCA EYLEM GEREKTİĞİNDE açılıyor: anahtar eksikse.
  //
  // Modelin tanıtım notu (`model.note`) buraya KONMUYOR ve bu ölçülmüş bir
  // karar: 360px'de o not 36px yer kaplıyor ve `--composer-h` üzerinden
  // tuvalin alt boşluğunu KALICI olarak yiyor — üstelik varsayılan modelde,
  // yani kullanıcının hiçbir şey yapmasını gerektirmeyen durumda. Bilgi
  // seçicinin `title`ında yaşıyor (aşağıda, renderModelOptions); eylem
  // gerektiren tek durum burada.
  const not = $("model-note");
  if (model.configured) {
    not.hidden = true;
  } else {
    $("model-note-text").textContent =
      `${model.label} için API anahtarı kayıtlı değil.`;
    not.hidden = false;
  }

  syncSpecs();
  syncRunCost();
  syncGoGate();
  if (announce && dusenler.length) {
    statusEl.textContent = `${model.label} bu ayarları desteklemiyor, `
      + `varsayılana düşüldü: ${dusenler.join(", ")}.`;
  }
}

function renderModelOptions() {
  const el = $("model");
  el.replaceChildren(...imageModels.map((m) => {
    const o = document.createElement("option");
    o.value = m.id;
    // Maliyet ve kurulum durumu ETİKETTE: karşılaştırma ("hangisi ucuz?")
    // burada yapılıyor ve native bir <option> yalnız metin taşıyabiliyor.
    const tarife = Object.values(m.credits_by_quality || {});
    const aralik = tarife.length
      ? `${Math.min(...tarife)}–${Math.max(...tarife)} kredi`
      : `${m.credits} kredi`;
    o.textContent = `${m.label} — ${aralik}`
      + (m.configured ? "" : " · kurulum gerekli");
    // Tanıtım notu `title`da: bilgi kaybolmuyor ama composer'ın yüksekliğine
    // bedel ödemiyor (bkz. applyModel'deki gerekçe).
    if (m.note) o.title = m.note;
    return o;
  }));
}

/** Katalog + hangi modellerin kullanılabilir olduğunu sunucudan çeker.
 *
 * `/api/settings` ile AYNI yanıttan okunuyor, ayrı bir uçtan değil: ikisi ayrı
 * zamanlarda gelirse seçici bir an "hepsi kullanılabilir" gösterip sonra fikir
 * değiştirirdi (GET /api/settings'in `guncelleme` alanı için yazılı olan
 * gerekçenin aynısı).
 */
function applyModels(s, tercih) {
  if (!s || !Array.isArray(s.image_models)) return;
  imageModels = s.image_models;
  renderModelOptions();
  const istenen = tercih || s.default_image_model;
  // Kayıtlı tercih artık katalogda olmayabilir (model kaldırıldı): varsayılana
  // düşülüyor. YAPILANDIRILMAMIŞ olması ise geçerli bir durum — seçili kalıyor,
  // yoksa anahtarı kaydetmek kullanıcının seçimini geri getirmezdi.
  const id = imageModels.some((m) => m.id === istenen)
    ? istenen : s.default_image_model;
  applyModel(id, { announce: false });
}

/** Tercihi diske yazar. Hata SESSİZ yutulmuyor ama üretimi de engellemiyor.
 *
 * `chatApi` KULLANILMIYOR: o chat.js'te ve bu dosya ondan ÖNCE yükleniyor —
 * olay anında erişilebilir olsa da tercih yazımı için üç satırlık bir fetch
 * yeterli, ve bağ ne kadar az olursa yükleme sırası o kadar az kırılgan.
 *
 * Yazım BAŞARISIZ olsa bile seçim ekranda kalıyor: kullanıcı bu turda seçtiği
 * modelle üretebiliyor, yalnız seçim bir sonraki açılışa taşınmıyor. Tersi
 * (seçimi geri almak) çalışan bir şeyi bozardı.
 */
async function savePref(body) {
  try {
    const res = await fetch("/api/prefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    statusEl.textContent = `Tercih kaydedilemedi (seçim bu oturumda geçerli): ${e.message}`;
  }
}

$("model").addEventListener("change", () => {
  applyModel($("model").value);
  // Tercih ANINDA yazılıyor, "Kaydet" düğmesine bağlı DEĞİL: #pref-autosave ve
  // tema seçicisinin deseni. O düğme kimlik formuna ait ve Azure hiç
  // yapılandırılmamışken basılamıyor.
  savePref({ image_model: $("model").value });
  // Diske YAZMAK yetmiyor, BELLEKTEKİ tercih de tazelenmeli: `applyModels`
  // her çağrıldığında `seciliModelTercihi`yi okuyor ve o değişken yalnızca
  // açılışta (`loadModelPref`) yazılıyordu. Ayarlar'ı kaydetmek
  // `applyConfigured`i yeniden çalıştırdığı için, kullanıcının bu turda
  // seçtiği model AÇILIŞTAKİ değere geri sıçrıyordu — yani PR #41'in ana
  // akışı ("OpenAI modelini seç → anahtarını gir → kaydet") seçimi geri
  // alıyordu. settings.js'in adına OLAY ANINDA dokunuluyor: yükleme sırası
  // kuralının izin verdiği tek yol (#model-settings-link ile aynı desen).
  seciliModelTercihi = $("model").value;
});

$("model-settings-link").addEventListener("click", () => {
  // Doğrudan seçili modelin SAĞLAYICI grubunu açıyor: "anahtar yok" uyarısının
  // düğmesi kullanıcıyı doğru kutuya götürmezse uyarı yarım kalır.
  // settings.js'in adına OLAY ANINDA dokunuluyor — yükleme sırası kuralının
  // izin verdiği tek yol (settings.js core.js'ten SONRA yükleniyor).
  openSettings(currentModel ? currentModel.provider : undefined);
});

// ── Üretim ayarları çipi ──
function syncSpecs() {
  const parts = [];
  const size = $("size").selectedOptions[0];
  if (size) parts.push(size.dataset.ratio || $("size").value);
  // Kalite ekseni olmayan modelde çipte de yazmıyor: boş bir "·" bırakmak
  // "kalite kayboldu" gibi okunurdu.
  if (!$("spec-quality").hidden && $("quality").selectedOptions[0]) {
    parts.push($("quality").selectedOptions[0].textContent.trim().toUpperCase());
  }
  parts.push(`x${$("n").value}`);
  $("specs-label").textContent = parts.join(" · ");
}
for (const id of ["size", "quality", "n"]) {
  $(id).addEventListener("change", () => { syncSpecs(); syncRunCost(); });
}
syncSpecs();

// ── Composer: otomatik büyüyen kutu + ⌘Enter + ⌘J ──
// Yükseklik satır sayısıyla büyür, `.composer-input`'un max-height'ı tavan.
function autoGrow(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight}px`;
}
$("prompt").addEventListener("input", () => autoGrow($("prompt")));

function submitComposer() {
  const promptVal = $("prompt").value.trim();
  if (currentMode === "image") {
    if (promptVal.length > MAX_PROMPT_CHARS) {
      statusEl.textContent = `İstem çok uzun (${promptVal.length}/${MAX_PROMPT_CHARS} karakter).`;
      return;
    }
    run();
  } else {
    if (promptVal.length > 6000) {
      statusEl.textContent = `Mesaj çok uzun (${promptVal.length}/6000 karakter).`;
      return;
    }
    sendChat();
  }
}

$("go").addEventListener("click", submitComposer);

// Dokunmatik girdi: hover'ı VE ince imleci olmayan cihaz. İki koşul birlikte
// aranıyor — tek başına `hover: none` bazı televizyon tarayıcılarında da
// doğru, `pointer: coarse` ise dokunmatik ekranlı bir dizüstüde fare
// takılıyken de doğru kalabiliyor.
//
// SIRA BAĞIMLILIĞI — core.js `folders.js`'ten ÖNCE yüklenmek zorunda:
// `folders.js` bu değeri KENDİ üst düzeyinde okuyor (FOLDER_HINT_DEFAULT /
// FOLDER_HINT_IMPORT). Üst düzey `const` küresel sözlüksel kapsamda duruyor,
// yani sıra bir gün ters çevrilirse sonuç sessiz bir `undefined` değil, TDZ
// `ReferenceError`'ı olur ve `folders.js`'in TAMAMI (klasörler, galeri, seçim
// modu, taşıma) hiç yüklenmez. index.html'deki script sırası bu yüzden
// gelişigüzel değil.
const IS_TOUCH = window.matchMedia("(hover: none) and (pointer: coarse)").matches;

$("prompt").addEventListener("keydown", (e) => {
  // DOKUNMATİKTE Enter GÖNDERMEZ, satır atlar.
  //
  // Masaüstünde "Enter = gönder" doğru kısayol. Telefonda ise sanal klavyenin
  // Enter tuşu SATIR ATLAMANIN TEK YOLU: Shift+Enter'ı Android klavyesinde
  // basmak pratikte mümkün değil. Kural aynı bırakılsaydı çok satırlı bir
  // prompt telefonda hiç yazılamaz, her satır denemesi yarım bir üretim
  // isteği gönderirdi — üstelik üretim ÜCRETLİ. Gönderme yolu #go düğmesi
  // (composer'da, her zaman görünür).
  if (IS_TOUCH && !e.metaKey && !e.ctrlKey) return;

  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitComposer();
  } else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    submitComposer();
  }
});

document.addEventListener("keydown", (e) => {
  if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "j") return;
  if (currentSection !== "studio") return;
  e.preventDefault();
  setMode(currentMode === "image" ? "director" : "image");
});

// Ana referans görsel: null | { kind: "upload", file, label } | { kind: "gallery", id, label }
let source = null;
let uploadPreviewUrl = null;

// Ek referanslar (ana görselin yanında gpt-image-2'ye gönderilir).
// Öğe: { kind: "upload", file, label, src } | { kind: "gallery", id, label, src }
// Sunucudaki MAX_EDIT_IMAGES ile aynı: 1 ana + 3 ek.
const MAX_EDIT_IMAGES = 4;
let extras = [];

// Simüle ilerleme: Azure tek yanıt döndürür (gerçek % akışı yok), bu yüzden
// beklerken ~%90'a doğru yumuşakça doldurup, iş bitince %100'e tamamlarız.
// generation token: eski/örtüşen bir işlemin stop/hide'ı yeni işlemin barını etkilemez.
let progressTimer = null;
let progressHideTimer = null;
let progressGen = 0;

function startProgress() {
  const gen = ++progressGen;
  clearInterval(progressTimer);
  clearTimeout(progressHideTimer);
  const fill = $("progress-fill");
  const pct = $("progress-pct");
  $("progress").hidden = false;
  let value = 0;
  fill.style.width = "0%";
  pct.textContent = "0%";
  progressTimer = setInterval(() => {
    if (gen !== progressGen) return;
    const remaining = 90 - value;
    if (remaining <= 0) return;
    value += Math.max(0.25, remaining * 0.02); // asimptotik + yavaş: yaklaştıkça iyice yavaşlar
    if (value > 90) value = 90;
    fill.style.width = value.toFixed(1) + "%";
    pct.textContent = Math.round(value) + "%";
  }, 160);
  return gen;
}

function stopProgress(complete, gen) {
  if (gen !== progressGen) return; // daha yeni bir işlem barı devraldı; dokunma
  clearInterval(progressTimer);
  progressTimer = null;
  const fill = $("progress-fill");
  const pct = $("progress-pct");
  if (complete) {
    fill.style.width = "100%";
    pct.textContent = "100%";
  }
  clearTimeout(progressHideTimer);
  progressHideTimer = setTimeout(() => {
    if (gen !== progressGen) return; // gizleme beklerken yeni işlem başladıysa dokunma
    $("progress").hidden = true;
    fill.style.width = "0%";
    pct.textContent = "0%";
  }, complete ? 450 : 200);
}

// ── İndirme ─────────────────────────────────────────────────────────
// Konum seçtiren TEK yol. Galeri kartı da (folders.js) büyüteç de
// (viewer.js) buradan geçiyor: v1.10'daki "İndir düzeltmesi" iki yerde ayrı
// ayrı yapılmıştı ve biri düzeltilip diğeri unutulduğunda kırılma
// "bazen çalışıyor" diye geri döner.
//
// Neden gerekti: `.app`'te WKWebView `ALLOW_DOWNLOADS` ile <a download>'u bir
// macOS kayıt paneline çeviriyor (desktop.py) — kullanıcı konumu SEÇİYOR.
// Tarayıcıda öyle bir panel yok; <a download> dosyayı sormadan indirme
// klasörüne atar. Kullanıcı tarafından bu "app'te indirebiliyorum, web'de
// indiremiyorum" olarak görünüyordu.
//
// Özellik yoksa (paketin WKWebView'ı — WebKit File System Access'i hiç
// uygulamadı — ayrıca Safari ve Firefox) eski <a download> yolu AYNEN kalır:
// pakette davranış değişmiyor.
const SUPPORTS_SAVE_PICKER = typeof window.showSaveFilePicker === "function";

// `/output/<id>.png` → `/api/output/<id>/download`.
//
// NEDEN VAR: `/output/…` bir ÇİZİM adresi (galeri küçük resimleri ve büyütecin
// `<img src>`'i), indirme adresi değil — `Content-Disposition` taşımıyor.
// Android WebView ise HTML'in `download` özniteliğini yok sayıyor: başlıksız bir
// `image/png`'ye gitmek onun çizebileceği bir şey olduğu için kayıt dinleyicisi
// hiç tetiklenmiyor ve indirme sessizce hiç olmuyordu (app.py'deki
// `output_download` notu). Çevirme TEK yerde: üç indirme yolunun hepsi
// `downloadImage`/`downloadViaAnchor`'dan geçiyor.
//
// ETKİSİZ-TEKRARLI: zaten indirme adresi verilirse aynısı dönüyor, yani iki kez
// uygulanması zararsız. Çevrilemeyen adres (blob:, data:, /assets/…) olduğu gibi
// dönüyor — bu işlev bir yönlendirme tablosu, bir doğrulayıcı değil.
const OUTPUT_ONEKI = "/output/";

function indirmeAdresi(url) {
  if (typeof url !== "string" || !url.startsWith(OUTPUT_ONEKI)) return url;
  const ad = url.slice(OUTPUT_ONEKI.length);
  if (!ad.endsWith(".png")) return url;
  // Ad zaten kodlanmış olarak geliyor (chat.js:920 `encodeURIComponent`,
  // folders.js kayıt adını olduğu gibi yazıyor); yeniden kodlamak `%` işaretini
  // ikinci kez kaçırıp adresi bozardı.
  return `/api/output/${ad.slice(0, -".png".length)}/download`;
}

// Android APK'nın enjekte ettiği indirme köprüsü (MainActivity `IndirmeKoprusu`).
//
// NEDEN VAR — `<a download>` Android'de HİÇBİR GARANTİ TAŞIMIYOR. Chromium'da o
// tıklama bir gezinme değil, "renderer kaynaklı indirme" üretiyor; WebView'in
// indirme sistemi yok, isteği tanır tanımaz İPTAL ediyor ve olayı uygulamaya
// `DownloadListener` ile veriyor (AwDownloadManagerDelegate). O halkanın
// kopması — WebView sürümü, bir OEM yaması, `AwContentsClientBridge`in
// bulunamaması — hiçbir hata üretmiyor: tıklama sessizce hiçbir şey yapmıyor.
// Telefonda "indirme çalışmıyor"un tarifi tam olarak bu.
//
// Köprü o halkayı tümden çıkarıyor: adres ve dosya adı doğrudan Kotlin'e
// geçiyor. Yan kazanç, `URLUtil.guessFileName`in de devreden çıkması — adı
// zaten BİLEN taraf frontend, tahmin etmesi gereken bir regex kalmıyor
// (klasör ZIP'lerinin telefona `download.zip` diye inmesinin sebebi oydu).
//
// Köprü YOKSA (tarayıcı, masaüstü paketi) hiçbir şey değişmiyor: eski
// `<a download>` yolu aynen duruyor.
function androidKoprusu() {
  const kopru = window.LumeoIndirme;
  return kopru && typeof kopru.indir === "function" ? kopru : null;
}

function downloadViaAnchor(url, filename) {
  const adres = indirmeAdresi(url);

  const kopru = androidKoprusu();
  if (kopru) {
    // MUTLAK adres: köprünün öbür ucu Kotlin, `location`ı yok. Kotlin ayrıca
    // adresin KENDİ sunucumuzu gösterdiğini doğruluyor.
    kopru.indir(new URL(adres, location.href).href, filename || "");
    return;
  }

  const a = document.createElement("a");
  a.href = adres;
  // Ad AÇIKÇA veriliyor: boş bırakılırsa macOS kayıt panelinin ad alanını
  // WebKit'in URL'den türetmesine kalıyoruz.
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Kayıt panelini açar, seçilen dosyaya görselin baytlarını yazar.
async function downloadImage(url, filename) {
  // Köprü varsa panel HİÇ denenmiyor: Android'de `showSaveFilePicker` zaten yok,
  // ama bir gün gelirse kayıt paneli köprünün sessizce devre dışı kalması demek
  // olurdu — indirmenin telefonda çalışmasının tek garantisi köprü.
  if (!SUPPORTS_SAVE_PICKER || androidKoprusu()) { downloadViaAnchor(url, filename); return; }

  let handle;
  try {
    handle = await window.showSaveFilePicker({
      suggestedName: filename,
      types: [{ description: "PNG görsel", accept: { "image/png": [".png"] } }],
    });
  } catch (e) {
    // Vazgeçmek hata değil: panel kapatıldıysa hiçbir şey yapma. Panelin
    // KENDİSİ açılamadıysa indirme hiç olmamasındansa eski yola düşülür.
    if (e.name === "AbortError") return;
    downloadViaAnchor(url, filename);
    return;
  }

  try {
    const res = await fetch(indirmeAdresi(url));
    if (!res.ok) throw new Error(`sunucu ${res.status}`);
    const stream = await handle.createWritable();
    await stream.write(await res.blob());
    await stream.close();
    statusEl.textContent = `İndirildi: ${filename}`;
  } catch (e) {
    // Hem söyle hem kurtar: durum satırı büyüteç açıkken perdenin ARKASINDA
    // kalıyor, o yüzden tek başına yeterli değil — geri düşüş dosyayı hiç
    // olmazsa indirme klasörüne bırakır. `createWritable` yazmayı takas
    // dosyasında biriktirdiği için yarım dosya kalmaz.
    statusEl.textContent = `İndirilemedi (${e.message}); indirme klasörüne kaydediliyor.`;
    downloadViaAnchor(url, filename);
  }
}

function clearUploadPreviewUrl() {
  if (uploadPreviewUrl) {
    URL.revokeObjectURL(uploadPreviewUrl);
    uploadPreviewUrl = null;
  }
}

// Merkez önizlemede görünen sunucu kaydı: logo/motto/banner bindirmesinin hedefi.
// Yüklenmiş (henüz kaydedilmemiş) bir görsel gösterilirken null'dır.
let currentImage = null;

function setCurrentImage(rec) {
  currentImage = rec;
  $("logo-add-btn").disabled = !rec;
}

function showPreview(rec) {
  setCurrentImage(rec);
}

// Referans durumunu arayüze yansıt: chip + ana buton etiketi + ek görsel şeridi
function renderSource() {
  const chip = $("ref-chip");
  const chipImg = $("ref-chip-img");
  const goBtn = $("go");
  if (source) {
    $("ref-label").textContent = source.label;
    chip.hidden = false;
    if (chipImg && uploadPreviewUrl) {
      chipImg.src = uploadPreviewUrl;
      chipImg.hidden = false;
    } else if (chipImg) {
      chipImg.hidden = true;
      chipImg.removeAttribute("src");
    }
    if (currentMode === "image") {
      goBtn.textContent = extras.length ? "Görselleri birleştir" : "Görseli düzenle";
    } else {
      goBtn.textContent = "Gönder";
    }
  } else {
    chip.hidden = true;
    if (chipImg) { chipImg.hidden = true; chipImg.removeAttribute("src"); }
    if (currentMode === "image") {
      goBtn.textContent = "Üret";
    } else {
      goBtn.textContent = "Gönder";
    }
  }
  // Ek görsel yalnızca bir ana görsel varken anlamlı
  $("extra-row").hidden = !source;
  renderExtras();
  // Palet notu referans görsel varken değişir (üretim ≠ düzenleme ifadesi)
  renderPalettePanel();
  // Referans görsel eklenip kaldırıldığında kapı yeniden sorulmalı:
  // düzenlemeyi desteklemeyen bir model seçiliyken referans varsa üretim
  // engelli olmak zorunda (bkz. goBlockReason).
  if (typeof syncGoGate === "function") syncGoGate();
}

// ── Ek referans görselleri ──────────────────────────────────────────
function revokeExtraUrls() {
  for (const item of extras) {
    if (item.kind === "upload") URL.revokeObjectURL(item.src);
  }
}

function clearExtras() {
  revokeExtraUrls();
  extras = [];
  $("extra-file-input").value = "";
}

function extraSlotsLeft() {
  return MAX_EDIT_IMAGES - 1 - extras.length;
}

function renderExtras() {
  const strip = $("extra-strip");
  strip.innerHTML = "";
  for (const item of extras) {
    const img = document.createElement("img");
    img.src = item.src;
    img.alt = item.label;

    const del = document.createElement("button");
    del.type = "button";
    del.className = "extra-del";
    del.textContent = "×";
    del.title = "Kaldır";
    del.setAttribute("aria-label", `${item.label} kaldır`);
    del.addEventListener("click", () => removeExtra(item));

    const cell = document.createElement("div");
    cell.className = "extra-chip";
    cell.title = item.label;
    cell.appendChild(img);
    cell.appendChild(del);
    strip.appendChild(cell);
  }
  $("extra-count").textContent = extras.length
    ? `${extras.length}/${MAX_EDIT_IMAGES - 1}`
    : "";
  $("extra-add-btn").disabled = extraSlotsLeft() <= 0;
}

function removeExtra(item) {
  if (item.kind === "upload") URL.revokeObjectURL(item.src);
  extras = extras.filter((it) => it !== item);
  renderSource();
}

// Ek referans reddinin TEK kaynağı (plan B6). İki çağıranı var ve ikisi
// gerekçeyi FARKLI yüzeylerde gösteriyor: `canAddExtra` #status'a yazar,
// Medya seçicisi #picker-note'a. Cümleler burada bir kez geçiyor — iki yere
// kopyalansaydı biri güncellenip diğeri bayatlardı (test sayıyor).
//
// K26: "Önce ana görseli seç." parantezsiz. Eski hâli "(Görsel ekle veya
// galeriden Düzenle)" diyordu; galeri kartının "+Ek" düğmesi Adım 11'de
// ölçümle kaldırıldığı için (§0.9) o kurtuluş yolu ARTIK YOK — cümle var
// olmayan bir kapıyı tarif ediyordu.
//
// Boş dize = engel yok. Çağıranlar `if (why)` ile okuyor.
function extraBlockReason(rec) {
  if (!source) return "Önce ana görseli seç.";
  if (extraSlotsLeft() <= 0) return `En fazla ${MAX_EDIT_IMAGES} görsel gönderilebilir.`;
  if (!rec) return "";
  if (source.kind === "gallery" && source.id === rec.id) return "Bu görsel zaten ana referans.";
  if (extras.some((it) => it.kind === "gallery" && it.id === rec.id)) {
    return "Bu görsel zaten ek referans listesinde.";
  }
  return "";
}

function canAddExtra() {
  const why = extraBlockReason(null);
  if (why) { statusEl.textContent = why; return false; }
  return true;
}

function addExtraUpload(file) {
  if (!canAddExtra()) return;
  if (!file || !ACCEPTED_UPLOAD_TYPES.includes(file.type)) {
    statusEl.textContent = "PNG, JPEG veya WebP bir görsel seç.";
    return;
  }
  extras = [...extras, { kind: "upload", file, label: file.name, src: URL.createObjectURL(file) }];
  statusEl.textContent = "";
  renderSource();
}

// Adım 11'den Adım 12'ye bekleyen dikişti; çağıranı artık Medya seçicisi
// (folders.js, "Ek olarak ekle"). Adı korundu — plan B6/B7 bunu şart koşuyordu.
//
// Ret gerekçesini KENDİ yazmıyor, `extraBlockReason`'dan alıp DÖNDÜRÜYOR:
// çağıran onu kendi görünür yüzeyine koyuyor. Eskiden buradan doğrudan
// `statusEl`e yazılıyordu ve Medya görünümündeyken #status gizli bir kabın
// içinde kalıyordu — eylem çalışıyor, geri bildirimi görünmüyordu (§0.9).
// Dönüş: engel varsa gerekçe cümlesi, eklendiyse boş dize.
function addGalleryExtra(rec) {
  const why = extraBlockReason(rec);
  if (why) return why;
  extras = [...extras, {
    kind: "gallery", id: rec.id,
    label: (rec.prompt || rec.id).slice(0, 40),
    src: `/output/${rec.filename}`,
  }];
  renderSource();
  return "";
}

function setUploadSource(file) {
  if (!file || !ACCEPTED_UPLOAD_TYPES.includes(file.type)) {
    statusEl.textContent = "PNG, JPEG veya WebP bir görsel seç.";
    return;
  }
  clearUploadPreviewUrl();
  source = { kind: "upload", file, label: `Yüklendi: ${file.name}` };
  uploadPreviewUrl = URL.createObjectURL(file);
  setCurrentImage(null); // henüz sunucuda kayıt yok → bindirme uygulanamaz
  renderSource();
}

function setGallerySource(rec) {
  clearUploadPreviewUrl();
  $("file-input").value = "";
  source = { kind: "gallery", id: rec.id, label: `Referans: ${(rec.prompt || rec.id).slice(0, 40)}` };
  // aynı görsel ek listesindeyse çift göndermemek için çıkar
  extras = extras.filter((it) => !(it.kind === "gallery" && it.id === rec.id));
  showPreview(rec);
  renderSource();
  $("prompt").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setGallerySourceById(id, prompt) {
  const rec = (typeof historyCache !== "undefined" && historyCache)
    ? historyCache.find((r) => r.id === id)
    : null;
  if (rec) {
    setGallerySource(rec);
  } else {
    setGallerySource({ id, prompt: prompt || id, filename: `${id}.png` });
  }
  showSection("studio");
  statusEl.textContent = "Görsel ana referans olarak ayarlandı.";
}



function clearSource() {
  clearUploadPreviewUrl();
  clearExtras();
  source = null;
  $("file-input").value = "";
  renderSource();
}

// Tek eylem: referans varsa düzenle, yoksa üret
async function run() {
  const prompt = $("prompt").value.trim();
  if (!prompt) { statusEl.textContent = "Önce bir prompt yaz."; return; }

  $("prompt").value = "";
  autoGrow($("prompt"));
  syncAskDirector();


  const size = $("size").value;
  const quality = $("quality").value;
  const n = $("n").value;
  // TEK yerde okunup İKİ dala aynı değişkenden veriliyor. Paletin dersi
  // (aşağıda, FormData döngüsünün yorumu): alanları elle saymak bir kez
  // `palette_id`'yi düşürmüştü.
  const model = $("model").value;
  const editing = source !== null;
  // Palet İKİ dalın da payload'ına eklenmeli — biri atlanırsa o yolda renk
  // sessizce kaybolur. Palet kapalıyken {} döner, böylece gövde bugünküyle
  // bayt bayt aynı kalır ve extra="forbid" boş bir alan görmez.
  const pal = readPaletteOpts();

  // ── Birleşik oturum (tasarım §5 · §4.2) ──
  // Görsel modu artık kendi oturumunu BAŞLATIYOR (Adım 8, K10'un ikinci yarısı):
  // prompt yapısı gereği bir döküm turu, o yüzden koşulsuz basılıyor. Oturum
  // yoksa `persistThread` üretimden SONRA POST ile açıyor.
  //
  // K10'un durduğu yer korunuyor: üretim isteğine UYDURMA id konmuyor. Oturum
  // henüz yazılmadığı için ilk partinin görsel kaydında ters bağ (`session_id`)
  // olmuyor — ileri bağ (`result.image_ids`) tam, dökümün çizdiği de o.
  //
  // chat.js'in adlarına OLAY ANINDA dokunuluyor (tıklama) — dosyanın başındaki
  // yükleme sırası kuralının izin verdiği tek yol.
  const sessionId = openSessionId();
  // Kullanıcının repliği üretimden ÖNCE döküme basılıyor (sendChat'in sırası):
  // beklerken kendi cümlesini görüyor. Başarısızlıkta geri alınıyor — diske de
  // hiçbir şey yazılmamış olur, çünkü yazan taraf başarıdan sonraki sonuç kaydı.
  const pending = beginResultTurn(prompt);

  let request;
  if (editing) {
    const fd = new FormData();
    fd.append("prompt", prompt);
    fd.append("size", size);
    fd.append("quality", quality);
    fd.append("n", n);
    fd.append("model", model);
    if (source.kind === "upload") fd.append("file", source.file);
    else fd.append("source_id", source.id);
    if (currentFolder) fd.append("folder_id", currentFolder.id);
    if (sessionId) fd.append("session_id", sessionId);
    // Alanlar TEK TEK sayılmaz: JSON dalı `...pal` ile hepsini gönderirken
    // burada elle saymak `palette_id`'yi düşürmüştü — kayıtlı palet
    // düzenlemede dondurulmuş adlarını kaybediyor, sunucu (seed, mode)'dan
    // çevrimdışı yeniden hesaplıyordu. Anahtarları dolaşmak iki dalı eşitler
    // ve ileride eklenecek alanlar da kendiliğinden gider.
    for (const [key, value] of Object.entries(pal)) fd.append(key, value);
    // ek referanslar: sunucu sırayı ana görsel → yüklemeler → galeri id'leri olarak kurar
    for (const item of extras) {
      if (item.kind === "upload") fd.append("extra_files", item.file);
      else fd.append("extra_source_ids", item.id);
    }
    request = fetch("/api/edit", { method: "POST", body: fd });
  } else {
    request = fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // `session_id` KOŞULLU: oturum yoksa alan hiç gönderilmiyor, böylece
      // gövde bugünküyle bayt bayt aynı kalıyor (palet dalının gerekçesi).
      body: JSON.stringify({ prompt, size, quality, n: parseInt(n, 10), model,
                             folder_id: currentFolder ? currentFolder.id : null,
                             ...(sessionId ? { session_id: sessionId } : {}),
                             ...pal }),
    });
  }

  runBusy = true;
  syncGoGate();
  const gen = startProgress();
  statusEl.textContent = !editing ? "Üretiliyor…"
    : extras.length ? "Görseller birleştiriliyor…" : "Düzenleniyor…";
  let ok = false;
  try {
    const res = await request;
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const { images } = await res.json();
    if (images[0]) showPreview(images[0]);
    clearUploadPreviewUrl(); // sonuç sunucu URL'inden gösteriliyor; blob artık gereksiz
    statusEl.textContent = editing ? "Düzenleme tamam." : `${images.length} görsel üretildi.`;
    // Bayat sunucu tespiti — /api/edit multipart olduğu için orada
    // extra="forbid" karşılığı YOK: Starlette bilinmeyen form alanını sessizce
    // atar ve 200 döner. Tek savunma yanıtın alanı geri YANKILAMASI.
    //
    // Uyarılar bir LİSTEDE toplanıyor, if/else zincirinde değil: zincir, ikisi
    // birden düştüğünde yalnızca birini söylüyordu. Model ilk sırada çünkü
    // sonucu İKİ yönden bozuyor — yanlış estetik VE yanlış fatura.
    const warnings = [];
    if (images[0] && images[0].model !== model) {
      // `undefined !== "azure-gpt-image-2"` eski bir sunucuda DOĞRU sonuç:
      // alanı hiç yankılamayan sunucu gerçekten de alanı yok saymıştır.
      warnings.push(`Model uygulanmadı: "${model}" istendi, sunucu `
        + `"${images[0].model || "bilinmiyor"}" ile üretti — sunucu eski sürüm `
        + "görünüyor, ./run.sh ile yeniden başlat.");
    }
    if (pal.palette_hex && images[0] && !images[0].palette) {
      warnings.push(
        "Palet uygulanmadı: sunucu eski sürüm görünüyor — ./run.sh ile yeniden başlat.");
    } else if (images[0] && images[0].palette && images[0].palette.applied === false) {
      // Ek, prompt karakter sınırına sığmadığı için düşürüldü. Kayıtta palet
      // görünür ama prompt'a girmedi; söylenmezse kullanıcı renksiz sonucu
      // açıklayamaz. Eski kayıtlarda alan yok → `=== false` bilinçli.
      warnings.push(
        "Palet prompt'a sığmadı (4000 karakter sınırı): görsel renk " +
        "yönlendirmesi olmadan üretildi. Prompt'u kısaltıp tekrar dene.");
    }
    if (warnings.length) statusEl.textContent = warnings.join(" · ");
    ok = true;
    // Sonuç kaydı döküme: konuşma ve üretilen görseller aynı akışta (tasarım §5).
    // `image_ids` sunucunun döndürdüğü kayıtlardan geliyor; adet ayrı
    // taşınmıyor, dizinin uzunluğundan okunuyor.
    // `model` de params'a: sonuç kartı hangi modelin ürettiğini söyleyebilmeli
    // ve döküm kaydı üretimin tam bağlamını taşımalı. Sunucu tarafı
    // (`models.ResultParams`) alanı v0.6'da öğrendi — bu iki taraf AYNI
    // sürümde inmek zorunda, yoksa `extra="forbid"` kaydı 422 yapar ve
    // görsel diske düşerken oturum turu sessizce kaybolur.
    await appendResultTurn(pending, images.map((r) => r.id),
                           { kind: editing ? "edit" : "generate", size, quality,
                             model });
    await loadHistory();
  } catch (e) {
    // BAŞARISIZ TUR GEÇMİŞTE KALMAZ (sendChat'in kuralı): kalsaydı döküme
    // cevapsız bir kullanıcı turu düşer, yeniden denemek onu ikinci kez
    // eklerdi. Prompt kutuda duruyor — core.js kutuyu hiç temizlemiyor.
    dropPendingTurn(pending);
    $("prompt").value = prompt;
    autoGrow($("prompt"));
    syncAskDirector();
    statusEl.textContent = e.message;
  } finally {
    runBusy = false;
    syncGoGate();   // kapının tek yazarı — yapılandırma/mod/model hepsini birden görüyor
    stopProgress(ok, gen);
  }
}

// ── Onay / ad sorma penceresi ────────────────────────────────────────
// Tek temalı modal, native confirm() ve prompt()'un yerine geçer:
// confirmDialog → Promise<boolean>, promptDialog → Promise<string|null>.
let dialogResolve = null;      // açık diyaloğun resolve'u (kapalıysa null)
let dialogMode = "confirm";
let dialogPrevFocus = null;    // kapanışta odak buraya döner

function openDialog({ mode = "confirm", title, desc = "", okLabel = "Onayla",
                      danger = false, initial = "" }) {
  closeDialog(mode === "prompt" ? null : false);   // üst üste açılmayı engelle
  dialogMode = mode;
  $("confirm-title").textContent = title;
  const descEl = $("confirm-desc");
  descEl.textContent = desc;
  descEl.hidden = !desc;
  $("confirm-icon").hidden = !danger;
  const ok = $("confirm-ok");
  ok.textContent = okLabel;
  ok.classList.toggle("btn-danger", danger);
  const input = $("confirm-input");
  $("confirm-field").hidden = mode !== "prompt";
  if (mode === "prompt") input.value = initial;
  dialogPrevFocus = document.activeElement;
  $("confirm-modal").hidden = false;
  if (mode === "prompt") { input.focus(); input.select(); } else { ok.focus(); }
  return new Promise((resolve) => { dialogResolve = resolve; });
}

function closeDialog(value) {
  if (!dialogResolve) return;
  const resolve = dialogResolve;
  dialogResolve = null;
  $("confirm-modal").hidden = true;
  if (dialogPrevFocus && dialogPrevFocus.isConnected) dialogPrevFocus.focus();
  dialogPrevFocus = null;
  resolve(value);
}

function submitDialog() {
  if (dialogMode !== "prompt") return closeDialog(true);
  const value = $("confirm-input").value.trim();
  if (!value) { $("confirm-input").focus(); return; }   // boş adla kapanma
  closeDialog(value);
}

function cancelDialog() { closeDialog(dialogMode === "prompt" ? null : false); }

function confirmDialog(title, desc, { okLabel = "Sil" } = {}) {
  return openDialog({ mode: "confirm", title, desc, okLabel, danger: true });
}

function promptDialog(title, desc, { okLabel = "Oluştur", initial = "" } = {}) {
  return openDialog({ mode: "prompt", title, desc, okLabel, initial });
}

$("confirm-ok").addEventListener("click", submitDialog);
$("confirm-cancel").addEventListener("click", cancelDialog);
$("confirm-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-confirm-close")) cancelDialog();
});
$("confirm-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); submitDialog(); }
});
// En üstteki katman: Escape yalnızca BU pencereyi kapatır. stopImmediatePropagation
// şart — aksi halde aynı olayda sonra çalışan modal handler'ları "confirm kapandı"
// görüp altındaki modalı da kapatıyor (bu handler'dan ÖNCE kayıtlı olanlar için de
// aşağıdaki `confirm-modal.hidden` guard'ları var).
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("confirm-modal").hidden) {
    e.stopImmediatePropagation();
    cancelDialog();
  }
});

async function deleteImage(rec) {
  const ok = await confirmDialog("Görseli sil",
    "Bu görsel diskten kalıcı olarak silinecek. Bu işlem geri alınamaz.");
  if (!ok) return;
  statusEl.textContent = "Siliniyor…";
  try {
    const res = await fetch(`/api/image/${rec.id}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    if (source && source.kind === "gallery" && source.id === rec.id) clearSource();
    extras = extras.filter((it) => !(it.kind === "gallery" && it.id === rec.id));
    if (currentImage && currentImage.id === rec.id) setCurrentImage(null);
    renderSource();
    statusEl.textContent = "Silindi.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

