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
const VIEWS = { image: ["view-image", "tab-image"], chat: ["view-chat", "tab-chat"] };
// Sekme SIRASI yönü belirliyor: sağdaki sekmeye geçerken panel sağdan, soldakine
// dönerken soldan giriyor. Yön olmadan iki taraf aynı görünür ve hareket
// "nereden nereye" bilgisini taşımaz.
const VIEW_ORDER = ["image", "chat"];
let currentView = "image";
// Ray bölümü: "studio" (mod anahtarıyla iki panel) | "media" (galeri) |
// "library" (bindirme varlıkları) | "tools" (görünüm + paletler).
// Dördü de GÖRÜNÜM (tasarım §4.1) — Adım 7b'ye kadar son ikisi gizli
// düğmelere programatik tıklıyordu ve ray grameri bozuktu.
let currentSection = "studio";

/** Bitişik segmentin kayan dolgusu: aktif düğmenin ölçüsünden okunuyor.
 *
 * Genişlik CSS'e SABİTLENEMEZ — "Görsel" ile "Prompt Yönetmeni" farklı
 * genişlikte ve etiketler çeviriyle/yazı tipiyle değişiyor.
 */
function syncTabThumb() {
  const thumb = $("view-tabs-thumb");
  const tab = $(VIEWS[currentView][1]);
  thumb.style.width = `${tab.offsetWidth}px`;
  thumb.style.transform = `translateX(${tab.offsetLeft}px)`;
}

function showView(name) {
  // Medya'dayken bir mod çağrısı gelirse (ör. chat.js prompt'u forma aktarıp
  // showView("image") diyor) önce Stüdyo'ya dönülür. `fromShowView` bayrağı
  // showSection'ın buraya geri dönmesini engelliyor.
  if (currentSection !== "studio") showSection("studio", true);
  const forward = VIEW_ORDER.indexOf(name) > VIEW_ORDER.indexOf(currentView);
  const changed = name !== currentView;
  currentView = name;
  for (const [key, [viewId, tabId]] of Object.entries(VIEWS)) {
    const active = key === name;
    const view = $(viewId);
    // `hidden` ANINDA çevriliyor (çift panelli cross-fade YOK): iki paneli
    // birlikte görünür tutmak katman + çift odak + sıçrayan yerleşim demekti.
    // Animasyon yalnızca GİREN panelde ve `hidden` kalkar kalkmaz başlıyor.
    view.hidden = !active;
    if (active && changed) {
      view.classList.remove("view-in-left", "view-in-right");
      // reflow: sınıf aynı karede kaldırılıp eklenirse animasyon yeniden başlamaz
      void view.offsetWidth;
      view.classList.add(forward ? "view-in-right" : "view-in-left");
    }
    $(tabId).classList.toggle("active", active);
    // aria-selected tel üzerinde güncellenmeli: role="tab" verildiği anda
    // ekran okuyucu hangi sekmenin seçili olduğunu SINIFTAN değil bundan okur.
    $(tabId).setAttribute("aria-selected", active ? "true" : "false");
  }
  // Composer'ın hangi yarısı görünecek: karar CSS'te (`#composer[data-mode=…]`).
  // Sebep: #chat-gate ve #chat-send'in `hidden`/`disabled`'ını settings.js ve
  // chat.js yönetiyor (sohbet yapılandırma kapısı). Aynı öznitelikleri moda
  // göre buradan da oynatmak iki sahip demekti; `display` ayrı bir eksen.
  $("composer").dataset.mode = name === "image" ? "image" : "director";
  syncTabThumb();
}

$("tab-image").addEventListener("click", () => showView("image"));
$("tab-chat").addEventListener("click", () => showView("chat"));
// Yazı tipi geldiğinde ve pencere değiştiğinde dolgu kayar: ölçüm tazelenmeli.
window.addEventListener("resize", syncTabThumb);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncTabThumb);
syncTabThumb();

// ══ Flow kabuğu ══════════════════════════════════════════════════════
// Ray gezinme, slide-over'lar, (+) menüsü, composer modu. Kabuk sorumluluğu
// olduğu için BURADA (bkz. yukarıdaki sekme notu): chat.js bir yaprak dosya.
//
// Perde (#shell-scrim) JS ile YÖNETİLMİYOR: görünürlüğü CSS'te `:has()` ile
// açık panelden türetiliyor. Sebebi somut — oturum listesini açan dinleyici
// chat.js'te ve o dosya core.js'ten SONRA yükleniyor; perdeyi buradan
// senkronlamak "diğer dinleyici çalıştıktan sonra oku" gibi kırılgan bir
// sıralama numarası gerektirirdi. Türetilmiş durum o numarayı gereksiz kılıyor.

const APP = document.querySelector(".app");

// Ray bölümü → görünüm eşlemesi. "studio" burada null: onun iki paneli
// (view-image / view-chat) showView'un işi, bölüm anahtarının değil.
const SECTION_VIEWS = { studio: null, media: "view-media",
                        library: "view-library", tools: "view-tools" };

function showSection(name, fromShowView = false) {
  currentSection = name;
  const studio = name === "studio";
  for (const [key, viewId] of Object.entries(SECTION_VIEWS)) {
    if (viewId) $(viewId).hidden = key !== name;
  }
  // Composer yalnız Stüdyo'da: prompt bir oturumun repliği (tasarım §4.2),
  // Medya/Kütüphane/Araçlar'da gönderilecek bir döküm yok.
  $("composer").hidden = !studio;
  if (studio) {
    // Panelleri ve mod anahtarını geri kur — showView'dan gelindiyse o zaten
    // yapacak, ikinci kez çağırmak animasyonu boşa tetiklerdi.
    if (!fromShowView) showView(currentView);
  } else {
    for (const [viewId] of Object.values(VIEWS)) $(viewId).hidden = true;
  }
  for (const key of Object.keys(SECTION_VIEWS)) {
    const on = key === name;
    $(`rail-${key}`).classList.toggle("active", on);
    if (on) $(`rail-${key}`).setAttribute("aria-current", "page");
    else $(`rail-${key}`).removeAttribute("aria-current");
  }
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
for (const id of ["upload-btn", "extra-add-btn"]) {
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
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight}px`;
}
for (const id of ["prompt", "chat-input"]) {
  const el = $(id);
  el.addEventListener("input", () => autoGrow(el));
}

// Görsel modunda ⌘/Ctrl+Enter üretime gider. Sohbette bu davranış zaten vardı
// (chat.js:1162); composer'ın altındaki ipucu iki modda da geçerli olduğu için
// eksik taraf tamamlandı.
$("prompt").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); $("go").click(); }
});

document.addEventListener("keydown", (e) => {
  if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "j") return;
  if (currentSection !== "studio") return;
  e.preventDefault();
  // `.click()` çünkü chat.js'in kendi tab-chat dinleyicisi de var (taslağı
  // sohbete taşıyıp kutuya odaklanıyor); showView'ı doğrudan çağırmak onu atlar.
  $(currentView === "image" ? "tab-chat" : "tab-image").click();
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

function showPreviewSrc(src, alt = "") {
  const img = $("preview-img");
  img.src = src;
  img.alt = alt;
  img.hidden = false;
  $("preview-empty").hidden = true;
  $("preview-clear").hidden = false;
  $("preview").classList.remove("empty");
}

// Görseli yalnızca ekrandan kaldırır (silme yok) ve boş duruma döner.
function clearPreview() {
  const img = $("preview-img");
  img.hidden = true;
  img.removeAttribute("src");
  img.alt = "";
  $("preview-empty").hidden = false;
  $("preview-clear").hidden = true;
  $("preview").classList.add("empty");
  setCurrentImage(null);
}

// Merkez önizlemede görünen sunucu kaydı: logo/motto/banner bindirmesinin hedefi.
// Yüklenmiş (henüz kaydedilmemiş) bir görsel gösterilirken null'dır.
let currentImage = null;

function setCurrentImage(rec) {
  currentImage = rec;
  $("logo-add-btn").disabled = !rec;
}

function showPreview(rec) {
  showPreviewSrc(`/output/${rec.filename}`, (rec.prompt || "").slice(0, 60));
  setCurrentImage(rec);
}

// Referans durumunu arayüze yansıt: chip + ana buton etiketi + ek görsel şeridi
function renderSource() {
  const chip = $("ref-chip");
  if (source) {
    $("ref-label").textContent = source.label;
    chip.hidden = false;
    $("go").textContent = extras.length ? "Görselleri birleştir" : "Görseli düzenle";
  } else {
    chip.hidden = true;
    $("go").textContent = "Üret";
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

function canAddExtra() {
  if (!source) {
    statusEl.textContent = "Önce ana görseli seç (Görsel ekle veya galeriden Düzenle).";
    return false;
  }
  if (extraSlotsLeft() <= 0) {
    statusEl.textContent = `En fazla ${MAX_EDIT_IMAGES} görsel gönderilebilir.`;
    return false;
  }
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

// ŞU AN ÇAĞRISIZ — bilerek duruyor, ölü kod değil bekleyen dikiş.
// Tek çağıranı galeri kartının "+Ek" düğmesiydi; o düğme Adım 11'de ÖLÇÜMLE
// düştü (üç pill S'de karonun %89'unu kaplıyordu, bkz. folders.js'teki A9
// notu). Yeni çağıranı Adım 12'nin Medya seçicisi olacak: plan B6/B7 bu
// fonksiyonu ve `canAddExtra`'yı ADIYLA yeniden kullanmayı şart koşuyor —
// silinip yeniden yazılırsa oradaki "ret gerekçesi tek kaynakta" kuralı
// (Türkçe cümleler kodda bir kez geçer) kırılır.
function addGalleryExtra(rec) {
  if (!canAddExtra()) return;
  if (source.kind === "gallery" && source.id === rec.id) {
    statusEl.textContent = "Bu görsel zaten ana referans.";
    return;
  }
  if (extras.some((it) => it.kind === "gallery" && it.id === rec.id)) {
    statusEl.textContent = "Bu görsel zaten ek referans listesinde.";
    return;
  }
  extras = [...extras, {
    kind: "gallery", id: rec.id,
    label: (rec.prompt || rec.id).slice(0, 40),
    src: `/output/${rec.filename}`,
  }];
  statusEl.textContent = "";
  renderSource();
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
    if (currentImage && currentImage.id === rec.id) clearPreview();
    renderSource();
    statusEl.textContent = "Silindi.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

