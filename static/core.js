// GPT-Image Studio — üretim akışı: prompt, referans görseller, ilerleme, onay penceresi.
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

// ── Üretim ayarları çipi ──
// Oranlar azure_client.ALLOWED_SIZES ile birebir: başka boyut sunucudan geçmez.
const SIZE_RATIO = { "1024x1024": "1:1", "1024x1536": "2:3", "1536x1024": "3:2" };
function syncSpecs() {
  const size = $("size").value;
  const quality = $("quality").selectedOptions[0].textContent.trim().toUpperCase();
  $("specs-label").textContent =
    `${SIZE_RATIO[size] || size} · ${quality} · x${$("n").value}`;
}
for (const id of ["size", "quality", "n"]) $(id).addEventListener("change", syncSpecs);
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

$("prompt").addEventListener("keydown", (e) => {
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

function downloadViaAnchor(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  // Ad AÇIKÇA veriliyor: boş bırakılırsa macOS kayıt panelinin ad alanını
  // WebKit'in URL'den türetmesine kalıyoruz.
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Kayıt panelini açar, seçilen dosyaya görselin baytlarını yazar.
async function downloadImage(url, filename) {
  if (!SUPPORTS_SAVE_PICKER) { downloadViaAnchor(url, filename); return; }

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
    const res = await fetch(url);
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
  showPreviewSrc(uploadPreviewUrl, file.name);
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
      body: JSON.stringify({ prompt, size, quality, n: parseInt(n, 10),
                             folder_id: currentFolder ? currentFolder.id : null,
                             ...(sessionId ? { session_id: sessionId } : {}),
                             ...pal }),
    });
  }

  $("go").disabled = true;
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
    // atar ve 200 döner. Yanıtta palet yankılanmıyorsa sunucu eskidir.
    if (pal.palette_hex && images[0] && !images[0].palette) {
      statusEl.textContent =
        "Palet uygulanmadı: sunucu eski sürüm görünüyor — ./run.sh ile yeniden başlat.";
    } else if (images[0] && images[0].palette && images[0].palette.applied === false) {
      // Ek, prompt karakter sınırına sığmadığı için düşürüldü. Kayıtta palet
      // görünür ama prompt'a girmedi; söylenmezse kullanıcı renksiz sonucu
      // açıklayamaz. Eski kayıtlarda alan yok → `=== false` bilinçli.
      statusEl.textContent =
        "Palet prompt'a sığmadı (4000 karakter sınırı): görsel renk " +
        "yönlendirmesi olmadan üretildi. Prompt'u kısaltıp tekrar dene.";
    }
    ok = true;
    // Sonuç kaydı döküme: konuşma ve üretilen görseller aynı akışta (tasarım §5).
    // `image_ids` sunucunun döndürdüğü kayıtlardan geliyor; adet ayrı
    // taşınmıyor, dizinin uzunluğundan okunuyor.
    await appendResultTurn(pending, images.map((r) => r.id),
                           { kind: editing ? "edit" : "generate", size, quality });
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
    $("go").disabled = !configured; // yapılandırma kaybolduysa kapıyı yeniden açma
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

