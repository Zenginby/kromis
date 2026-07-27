const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const ACCEPTED_UPLOAD_TYPES = ["image/png", "image/jpeg", "image/webp"];

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
    if (pal.palette_hex) {
      fd.append("palette_hex", pal.palette_hex);
      fd.append("palette_mode", pal.palette_mode);
      fd.append("palette_strength", pal.palette_strength);
    }
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
      body: JSON.stringify({ prompt, size, quality, n: parseInt(n, 10),
                             folder_id: currentFolder ? currentFolder.id : null,
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
    }
    ok = true;
    await loadHistory();
  } catch (e) {
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

// ── Klasörler ────────────────────────────────────────────────────────
// Açık klasör AYNI ZAMANDA hedeftir: içindeysen yeni görseller oraya kaydedilir,
// kökteysen klasörsüz kaydedilir. Tek durum → "nerede görüyorum" ile "nereye
// kaydediliyor" ayrışmaz. null = kök.
//
// Hiyerarşi: klasörler `parent_id` ile ağaç kurar (kök = null) ve şerit yalnızca
// BULUNULAN seviyenin çocuklarını gösterir. `folderCache` düz listeyi tutar;
// süzme burada yapılır, sunucuya seviye parametresi gitmez.
let currentFolder = null;
let folderCache = [];

const parentOf = (f) => (f && f.parent_id) || null;
const folderById = (id) => (id ? folderCache.find((f) => f.id === id) || null : null);

// Kökten bulunulan klasöre kadarki zincir (kırıntı başlığı için)
function folderPath(id) {
  const path = [];
  let node = folderById(id);
  while (node && !path.some((f) => f.id === node.id)) {   // bozuk zincire karşı guard
    path.unshift(node);
    node = folderById(parentOf(node));
  }
  return path;
}

// Bir klasörün kendisi + tüm alt klasörleri (silme onayında sayı vermek için)
function folderSubtree(id) {
  const out = [];
  const queue = [id];
  const seen = new Set(queue);
  while (queue.length) {
    const current = queue.shift();
    const rec = folderById(current);
    if (rec) out.push(rec);
    for (const f of folderCache) {
      if (parentOf(f) === current && !seen.has(f.id)) { seen.add(f.id); queue.push(f.id); }
    }
  }
  return out;
}

// Sürükle-bırak taşıma: kart bu MIME türünü taşır, klasör hedefleri onu arar.
// Böylece dosya sürükleme (stage'e görsel bırakma) ile karışmaz.
const IMAGE_DND_TYPE = "application/x-gpt-image-id";

// Şerit ipucusunun normal (seçim dışı) metni — seçim modunda geçici olarak değişir
const FOLDER_HINT_DEFAULT = "Bir görseli klasör kartına sürükleyip bırakarak taşıyabilirsin.";

function renderFolderTarget() {
  const el = $("folder-target");
  if (currentFolder) {
    el.textContent = `Yeni görseller "${currentFolder.name}" klasörüne eklenecek.`;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}

function syncFolderView() {
  const inFolder = currentFolder !== null;
  $("folder-back").hidden = !inFolder;
  // Silme yalnızca klasörün İÇİNDE (sağ üstte); seçim modunda şerit görsellere ayrılır
  $("folder-delete").hidden = !inFolder || selectMode;
  $("folder-new").hidden = selectMode;
  const path = inFolder ? folderPath(currentFolder.id) : [];
  // kırıntı: "A / B / C" — cache henüz gelmediyse en azından klasörün adı
  $("gallery-title").textContent = inFolder
    ? (path.length ? path.map((f) => f.name).join(" / ") : currentFolder.name)
    : "Klasörler";
  $("images-title").textContent = inFolder ? "Klasördeki görseller" : "Klasörsüz görseller";
  // Şerit klasör içinde de görünür: taşıma hedefleri oradan geliyor.
  $("folder-hint").hidden = !folderCache.length;
  renderFolderTarget();
  renderFolders();
}

async function loadFolders() {
  try {
    const res = await fetch("/api/folders");
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    folderCache = (await res.json()).items || [];
  } catch {
    folderCache = [];
    statusEl.textContent = "Klasörler alınamadı.";
  }
  $("folder-hint").hidden = !folderCache.length;
  renderFolders();
}

// Görsel(ler)i klasöre (veya köke) taşır. Dosya taşınmaz; yalnızca etiket değişir.
// Sürüklenen kart seçiliyse TÜM seçim birlikte gider; değilse yalnızca o kart.
// Tek uç kullanılır (tek görselde de): sunucu tarafında tek yazım → kayıp güncelleme yok.
async function moveImages(imageId, folderId, targetName) {
  const ids = selectMode && selected.has(imageId) ? [...selected] : [imageId];
  try {
    const res = await fetch("/api/images", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, folder_id: folderId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    const { moved } = await res.json();
    statusEl.textContent = moved > 1
      ? `${moved} görsel "${targetName}" içine taşındı.`
      : `Görsel "${targetName}" içine taşındı.`;
    selected.clear();   // taşınanlar bu görünümden düştü
    await Promise.all([loadFolders(), loadHistory()]);
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

// Bir öğeyi görsel-bırakma hedefi yapar (klasör kartı / "Klasörsüz" kartı)
function makeDropTarget(el, folderId, targetName) {
  const carriesImage = (e) => !!e.dataTransfer && [...e.dataTransfer.types].includes(IMAGE_DND_TYPE);
  el.addEventListener("dragover", (e) => {
    if (!carriesImage(e)) return;      // dosya sürüklemesine karışma
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    el.classList.add("drop-hover");
  });
  el.addEventListener("dragleave", () => el.classList.remove("drop-hover"));
  el.addEventListener("drop", (e) => {
    el.classList.remove("drop-hover");
    if (!carriesImage(e)) return;
    e.preventDefault();
    e.stopPropagation();
    const imageId = e.dataTransfer.getData(IMAGE_DND_TYPE);
    if (imageId) moveImages(imageId, folderId, targetName);
  });
}

function renderFolders() {
  const grid = $("folder-grid");
  grid.innerHTML = "";

  // Bir klasörün içindeyken "yukarı" kartı: bir seviye üstü gösterir (kökte "Klasörsüz"),
  // hem çıkış hem de o seviyeye taşıma hedefi.
  if (currentFolder) {
    const parent = folderById(parentOf(currentFolder));
    const upName = parent ? parent.name : "Klasörsüz";
    const out = document.createElement("button");
    out.type = "button";
    out.className = "folder-open folder-root";
    out.title = `${upName} · buraya bırakarak bir üst seviyeye taşı`;
    const label = document.createElement("span");
    label.className = "folder-name";
    label.textContent = parent ? `↑ ${upName}` : upName;
    const sub = document.createElement("span");
    sub.className = "folder-count";
    sub.textContent = "buraya bırak → bir üst";
    out.appendChild(label);
    out.appendChild(sub);
    out.addEventListener("click", goUp);

    const cell = document.createElement("div");
    cell.className = "folder-cell";
    cell.appendChild(out);
    makeDropTarget(cell, parent ? parent.id : null, upName);
    grid.appendChild(cell);
  }

  // Yalnızca bulunulan seviyenin klasörleri: kökte kök klasörler, içeride alt klasörler
  const children = folderCache.filter((f) => parentOf(f) === (currentFolder ? currentFolder.id : null));
  if (!children.length) {
    const empty = document.createElement("p");
    empty.className = "folder-empty";
    empty.textContent = currentFolder
      ? "Bu klasörde alt klasör yok · + Yeni klasör ile oluştur"
      : "Henüz klasör yok · + Yeni klasör ile oluştur";
    grid.appendChild(empty);
    return;
  }
  for (const f of children) {
    // SVG: 🗀 gibi glyph'ler sistem fontunda eksik olabiliyor (tofu/yanlış render)
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "folder-icon");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("width", "26");
    icon.setAttribute("height", "26");
    icon.setAttribute("fill", "none");
    icon.setAttribute("stroke", "currentColor");
    icon.setAttribute("stroke-width", "1.8");
    icon.setAttribute("stroke-linecap", "round");
    icon.setAttribute("stroke-linejoin", "round");
    icon.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M4 20a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2z");
    icon.appendChild(path);

    const name = document.createElement("span");
    name.className = "folder-name";
    name.textContent = f.name;

    const count = document.createElement("span");
    count.className = "folder-count";
    count.textContent = f.child_count
      ? `${f.count} görsel · ${f.child_count} klasör`
      : `${f.count} görsel`;

    const open = document.createElement("button");
    open.type = "button";
    open.className = "folder-open";
    open.title = `${f.name} klasörünü aç`;
    open.appendChild(icon);
    open.appendChild(name);
    open.appendChild(count);
    open.addEventListener("click", () => openFolder(f));

    // Silme butonu kartta DEĞİL: klasörün içine girilince başlık şeridinin sağ üstünde.
    const cell = document.createElement("div");
    cell.className = "folder-cell";
    cell.appendChild(open);
    makeDropTarget(cell, f.id, f.name);
    grid.appendChild(cell);
  }
}

async function openFolder(f) {
  currentFolder = { id: f.id, name: f.name, parent_id: parentOf(f) };
  syncFolderView();
  await Promise.all([loadFolders(), loadHistory()]);
}

// Bir seviye yukarı: alt klasördeyse ebeveyne, kök klasördeyse köke (klasörsüz)
async function goUp() {
  const parent = folderById(parentOf(currentFolder));
  currentFolder = parent ? { id: parent.id, name: parent.name, parent_id: parentOf(parent) } : null;
  syncFolderView();
  await Promise.all([loadFolders(), loadHistory()]);
}

async function createFolder() {
  const where = currentFolder ? `"${currentFolder.name}" içinde` : "kökte";
  const name = await promptDialog("Yeni klasör", `Klasör ${where} oluşturulacak.`);
  if (!name) return;
  try {
    const res = await fetch("/api/folders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_id: currentFolder ? currentFolder.id : null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    statusEl.textContent = "Klasör oluşturuldu.";
    await loadFolders();
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

// İçinde bulunulan klasörü siler (başlık şeridindeki çöp kutusu). Alt klasörler de
// silinir; GÖRSELLER silinmez, klasörsüz hale döner.
async function deleteCurrentFolder() {
  if (!currentFolder) return;
  const target = currentFolder;
  const subtree = folderSubtree(target.id);
  // Klasör listesi alınamadıysa subtree boş kalır → sayıları 0 göster, eksiye düşme
  const subCount = Math.max(0, subtree.length - 1);
  const images = subtree.reduce((sum, f) => sum + (f.count || 0), 0);
  const parts = [
    subCount ? `${subCount} alt klasör de silinecek.` : null,
    images ? `${images} görsel SİLİNMEZ, klasörsüz hale döner.` : "İçinde görsel yok.",
  ].filter(Boolean);
  const ok = await confirmDialog(`"${target.name}" klasörünü sil`, parts.join(" "),
                                 { okLabel: "Klasörü sil" });
  if (!ok) return;
  try {
    const res = await fetch(`/api/folders/${target.id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    const { unfiled } = await res.json();
    statusEl.textContent = unfiled
      ? `Klasör silindi · ${unfiled} görsel klasörsüz hale döndü.`
      : "Klasör silindi.";
    await goUp();   // silinen klasörün içindeydik → bir üst seviyeye çık
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

$("folder-back").addEventListener("click", goUp);
$("folder-delete").addEventListener("click", deleteCurrentFolder);
$("folder-new").addEventListener("click", createFolder);

// ── Çoklu seçim ──────────────────────────────────────────────────────
// Seçim YALNIZCA görseller için: klasörler seçilmez, toplu klasör silme yok.
// Seçim modunda kart tıklaması seçim değiştirir (düzenlemeye alma devre dışı),
// eylemler üst şeritte toplanır ve seçili görseller birlikte sürüklenebilir.
let selectMode = false;
let selected = new Set();      // seçili görsel id'leri
let historyCache = [];         // son çekilen galeri kayıtları (renderGallery kaynağı)

function setSelectMode(on) {
  selectMode = on;
  if (!on) selected.clear();
  document.body.classList.toggle("select-mode", on);
  renderGallery();
  syncFolderView();   // klasör butonlarının görünürlüğü tek yerden: syncFolderView
  syncSelectUI();
}

function toggleSelected(id) {
  if (selected.has(id)) selected.delete(id);
  else selected.add(id);
  renderGallery();
  syncSelectUI();
}

// Kart üstündeki kare/tik işareti (sol üst köşe)
function makeCheckbox(rec) {
  const box = document.createElement("button");
  box.type = "button";
  box.className = "card-check";
  const isOn = selected.has(rec.id);
  box.setAttribute("aria-pressed", String(isOn));
  box.setAttribute("aria-label", isOn ? "Seçimi kaldır" : "Görseli seç");
  // Tik SVG olarak çizilir; kare çerçeve CSS'ten gelir (glyph'e güvenmiyoruz)
  const tick = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  tick.setAttribute("viewBox", "0 0 24 24");
  tick.setAttribute("width", "14");
  tick.setAttribute("height", "14");
  tick.setAttribute("fill", "none");
  tick.setAttribute("stroke", "currentColor");
  tick.setAttribute("stroke-width", "3");
  tick.setAttribute("stroke-linecap", "round");
  tick.setAttribute("stroke-linejoin", "round");
  tick.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M20 6 9 17l-5-5");
  tick.appendChild(path);
  box.appendChild(tick);
  box.addEventListener("click", (e) => { e.stopPropagation(); toggleSelected(rec.id); });
  return box;
}

function syncSelectUI() {
  $("select-bar").hidden = !selectMode;
  $("select-toggle").hidden = selectMode;
  $("folder-hint").textContent = selectMode
    ? (selected.size
        ? "Seçili görselleri taşımak için birini klasör kartına sürükle."
        : "Görselleri seç, sonra taşımak için birini klasör kartına sürükle.")
    : FOLDER_HINT_DEFAULT;
  if (!selectMode) return;

  const total = historyCache.length;
  $("select-count").textContent = `${selected.size} seçili`;
  const allSelected = total > 0 && selected.size === total;
  $("select-all").textContent = allSelected ? "Seçimi temizle" : "Tümünü seç";
  $("select-all").disabled = total === 0;
  $("select-delete").disabled = selected.size === 0;
}

async function deleteSelected() {
  const ids = [...selected];
  if (!ids.length) return;
  const ok = await confirmDialog(`${ids.length} görseli sil`,
    `Seçili ${ids.length} görsel diskten kalıcı olarak silinecek. Bu işlem geri alınamaz.`);
  if (!ok) return;
  statusEl.textContent = "Siliniyor…";
  try {
    const res = await fetch("/api/images", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    const { deleted } = await res.json();
    // silinenler referans/önizlemede duruyorsa oradan da düşür
    if (source && source.kind === "gallery" && ids.includes(source.id)) clearSource();
    extras = extras.filter((it) => !(it.kind === "gallery" && ids.includes(it.id)));
    if (currentImage && ids.includes(currentImage.id)) clearPreview();
    renderSource();
    selected.clear();
    statusEl.textContent = `${deleted} görsel silindi.`;
    await Promise.all([loadFolders(), loadHistory()]);
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

$("select-toggle").addEventListener("click", () => setSelectMode(true));
$("select-cancel").addEventListener("click", () => setSelectMode(false));
$("select-delete").addEventListener("click", deleteSelected);
$("select-all").addEventListener("click", () => {
  const allSelected = historyCache.length > 0 && selected.size === historyCache.length;
  selected = allSelected ? new Set() : new Set(historyCache.map((r) => r.id));
  renderGallery();
  syncSelectUI();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && selectMode && $("confirm-modal").hidden) setSelectMode(false);
});

async function loadHistory() {
  const url = currentFolder ? `/api/history?folder_id=${encodeURIComponent(currentFolder.id)}` : "/api/history";
  const res = await fetch(url);
  if (!res.ok) {
    // klasör başka bir sekmede silinmiş olabilir → köke düş
    if (currentFolder) { currentFolder = null; syncFolderView(); return loadHistory(); }
    statusEl.textContent = "Geçmiş alınamadı.";
    return;
  }
  const { images } = await res.json();
  historyCache = images;
  // Seçim modundayken listeden düşen görsellerin seçimi de düşer
  selected = new Set([...selected].filter((id) => images.some((r) => r.id === id)));
  renderGallery();
  syncSelectUI();
}

// Galeri kartlarını `historyCache`'ten çizer. loadHistory'den ayrı: seçim moduna
// girip çıkmak yeniden istek atmaz, yalnızca yeniden çizer.
function renderGallery() {
  const g = $("gallery");
  g.innerHTML = "";
  for (const rec of historyCache) {
    const prompt = rec.prompt || "";

    // Küçük resme tıklamak doğrudan düzenleme moduna alır (ayrı "Düzenle" butonu yok)
    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = prompt.slice(0, 60);
    img.title = selectMode
      ? "Seçmek için tıkla · seçili görselleri taşımak için klasöre sürükle"
      : prompt
        ? `${prompt}\n\nDüzenlemek için tıkla · taşımak için klasöre sürükle`
        : "Düzenlemek için tıkla · taşımak için klasöre sürükle";
    img.addEventListener("click", () => { if (!selectMode) setGallerySource(rec); });
    // img'in yerel sürüklemesi kapatılır ki sürükleme kartın kendisinden başlasın
    // (aksi halde dataTransfer'a görsel URL'i düşer ve sürükleme hayaleti bozulur)
    img.draggable = false;

    const downloadLink = document.createElement("a");
    downloadLink.setAttribute("href", `/output/${rec.filename}`);
    downloadLink.setAttribute("download", "");
    downloadLink.textContent = "İndir";

    // ana görsele ek referans olarak ekle (AI ile birleştirme)
    const extraBtn = document.createElement("button");
    extraBtn.textContent = "+Ek";
    extraBtn.title = "Ek referans görseli olarak ekle";
    extraBtn.addEventListener("click", () => addGalleryExtra(rec));

    const acts = document.createElement("div");
    acts.className = "acts";
    acts.appendChild(downloadLink);
    acts.appendChild(extraBtn);

    const delBtn = document.createElement("button");
    delBtn.className = "card-del";
    delBtn.textContent = "×";
    delBtn.title = "Sil";
    delBtn.setAttribute("aria-label", "Görseli sil");
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteImage(rec);
    });

    const card = document.createElement("div");
    card.className = "card";
    if (selectMode && selected.has(rec.id)) card.classList.add("selected");
    card.draggable = true;
    card.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData(IMAGE_DND_TYPE, rec.id);
      e.dataTransfer.effectAllowed = "move";
      card.classList.add("dragging");
      document.body.classList.add("dnd-active");   // klasör hedeflerini belirginleştir
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      document.body.classList.remove("dnd-active");
    });
    // Seçim modunda kartın her yeri seçer; kart içi eylemler (İndir/+Ek/×) hariç
    card.addEventListener("click", (e) => {
      if (!selectMode) return;
      if (e.target.closest(".acts") || e.target.closest(".card-del")) return;
      toggleSelected(rec.id);
    });
    card.appendChild(img);
    if (selectMode) card.appendChild(makeCheckbox(rec));
    card.appendChild(delBtn);
    card.appendChild(acts);

    g.appendChild(card);
  }
}

// Görsel ekle butonu + gizli dosya girişi
// Önizlemeyi ekrandan kaldır (silmez): referansı da temizleyip "Üret" moduna döner
$("preview-clear").addEventListener("click", () => {
  clearSource();
  clearPreview();
  statusEl.textContent = "";
});

$("upload-btn").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", () => {
  const files = $("file-input").files;
  if (files.length) setUploadSource(files[0]);
});
$("ref-clear").addEventListener("click", clearSource);

$("extra-add-btn").addEventListener("click", () => $("extra-file-input").click());
$("extra-file-input").addEventListener("change", () => {
  for (const file of $("extra-file-input").files) addExtraUpload(file);
  $("extra-file-input").value = "";
});

// Sürükle-bırak: merkez alana bırakılan görseli referans olarak yükle
const stageEl = document.querySelector(".stage");

function hasFiles(e) {
  return !!e.dataTransfer && [...e.dataTransfer.types].includes("Files");
}

// Tarayıcı, sayfaya bırakılan hiçbir dosyayı/bağlantıyı asla açmasın (koşulsuz).
["dragover", "drop"].forEach((evt) =>
  window.addEventListener(evt, (e) => e.preventDefault())
);

["dragenter", "dragover"].forEach((evt) =>
  stageEl.addEventListener(evt, (e) => {
    if (hasFiles(e)) stageEl.classList.add("dragover");
  })
);

stageEl.addEventListener("dragleave", (e) => {
  if (e.target === stageEl) stageEl.classList.remove("dragover");
});

stageEl.addEventListener("drop", (e) => {
  stageEl.classList.remove("dragover");
  if (hasFiles(e)) setUploadSource(e.dataTransfer.files[0]);
});

function selectInGroup(groupSel, btn) {
  document.querySelectorAll(groupSel + " button").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}

// ── Logo/banner kütüphanesi (prompt altı panel) ─────────────────────
let assetCache = { logos: [], banners: [], mottos: [] };
let assetPanelKind = "logos";
const ASSET_EMPTY_TEXT = {
  logos: "Henüz logo yok · + Yükle ile ekle",
  mottos: "Henüz motto yok · + Yükle ile ekle",
  banners: "Henüz banner yok · + Yükle ile ekle",
};
const OVERLAY_EMPTY_TEXT = {
  motto: "Önce Kütüphane'den bir motto yükle.",
  banner: "Önce Kütüphane'den bir banner yükle.",
};

function assetStatus(msg) { $("asset-status").textContent = msg || ""; }

async function loadAssets(kind) {
  try {
    const res = await fetch(`/api/assets/${kind}`);
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    assetCache[kind] = (await res.json()).items || [];
  } catch {
    assetCache[kind] = [];
    assetStatus("Kütüphane alınamadı.");
  }
  if (kind === assetPanelKind) renderAssetPanel();
  if (!$("logo-modal").hidden) renderOverlayPicker(); // modal açıksa seçiciyi tazele
}

function renderAssetPanel() {
  const grid = $("asset-grid");
  grid.innerHTML = "";
  const items = assetCache[assetPanelKind];
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "asset-empty";
    empty.textContent = ASSET_EMPTY_TEXT[assetPanelKind] || "Henüz varlık yok · + Yükle ile ekle";
    grid.appendChild(empty);
    return;
  }
  for (const item of items) {
    const img = document.createElement("img");
    img.src = `/assets/${assetPanelKind}/${item.filename}`;
    img.alt = item.name;
    img.title = item.name;

    const del = document.createElement("button");
    del.className = "asset-del";
    del.textContent = "×";
    del.title = "Sil";
    del.setAttribute("aria-label", `${item.name} sil`);
    del.addEventListener("click", () => deleteAssetItem(assetPanelKind, item.id));

    const name = document.createElement("span");
    name.className = "asset-name";
    name.textContent = item.name;

    const cell = document.createElement("div");
    cell.className = "asset-cell";
    cell.appendChild(img);
    cell.appendChild(del);
    cell.appendChild(name);
    grid.appendChild(cell);
  }
}

async function uploadAsset(kind, file) {
  if (!file || !ACCEPTED_UPLOAD_TYPES.includes(file.type)) {
    assetStatus("PNG, JPEG veya WebP bir görsel seç.");
    return;
  }
  assetStatus("Yükleniyor…");
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", file.name.replace(/\.[^.]+$/, ""));
  try {
    const res = await fetch(`/api/assets/${kind}`, { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    assetStatus("Eklendi.");
    await loadAssets(kind);
  } catch (e) {
    assetStatus(e.message);
  }
}

async function deleteAssetItem(kind, id) {
  const ok = await confirmDialog("Varlığı sil",
    "Bu logo/motto/banner kütüphaneden kalıcı olarak silinecek.");
  if (!ok) return;
  try {
    const res = await fetch(`/api/assets/${kind}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    // modalda seçili öğe silindiyse seçimi güvenli varsayılana düşür
    if (kind === "logos" && selectedAsset.logo === id) selectedAsset.logo = "builtin";
    if (kind === "mottos" && selectedAsset.motto === id) selectedAsset.motto = null;
    if (kind === "banners" && selectedAsset.banner === id) selectedAsset.banner = null;
    assetStatus("Silindi.");
    await loadAssets(kind);
    if (!$("logo-modal").hidden) { syncColorRow(); refreshLogoPreview(); }
  } catch {
    assetStatus("Silinemedi.");
  }
}

$("asset-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-akind]");
  if (!btn) return;
  selectInGroup("#asset-tabs", btn);
  assetPanelKind = btn.dataset.akind;
  assetStatus("");
  renderAssetPanel();
});
$("asset-upload-btn").addEventListener("click", () => $("asset-file-input").click());
$("asset-file-input").addEventListener("change", async () => {
  const files = [...$("asset-file-input").files];
  $("asset-file-input").value = "";
  for (const file of files) await uploadAsset(assetPanelKind, file); // sırayla: manifest yazımı atomik
});

// ── Kütüphane modalı (logo/motto/banner yükle-sil) ───────────────────
function openAssetsModal() {
  assetStatus("");
  renderAssetPanel();
  $("assets-modal").hidden = false;
}

function closeAssetsModal() {
  $("assets-modal").hidden = true;
}

$("library-btn").addEventListener("click", openAssetsModal);
$("assets-close").addEventListener("click", closeAssetsModal);
$("assets-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-assets-close")) closeAssetsModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("assets-modal").hidden) closeAssetsModal();
});

// ── Bindirme modalı: logo VEYA banner + canlı önizleme ──────────────
let logoId = null;
let rawPreviewSrc = "";                                 // ham (bindirmesiz) görsel URL'i
let overlayMode = "logo";                               // "logo" | "motto" | "banner"
// logo: "builtin"|id · motto: id|null · banner: id|null
let selectedAsset = { logo: "builtin", motto: null, banner: null };
let logoPreviewTimer = null;
let logoPreviewToken = 0;

// Logo ve motto aynı (konumlanabilir, 9-grid) yerleşimi paylaşır; yalnızca
// varlık hangi kütüphaneden geldiği ve renk varyantı (yalnız yerleşik logo) farklıdır.
function readLogoOpts() {
  const active = (sel) => document.querySelector(sel + " button.active");
  const pos = active("#logo-grid");
  const col = active("#logo-color");
  const sizePct = parseInt($("logo-size").value, 10);
  const shadowPct = parseInt($("logo-shadow").value, 10);
  const blur = parseInt($("logo-blur").value, 10);
  const isMotto = overlayMode === "motto";
  return {
    id: logoId,
    asset_kind: isMotto ? "mottos" : "logos",
    asset_id: isMotto ? selectedAsset.motto : (selectedAsset.logo === "builtin" ? null : selectedAsset.logo),
    position: pos ? pos.dataset.pos : "bottom-right",
    color: col ? col.dataset.color : "auto",
    size: +(sizePct / 100).toFixed(3),
    shadow_alpha: Math.round((shadowPct / 100) * 255),
    shadow_blur: blur,
  };
}

function readBannerOpts() {
  const edge = document.querySelector("#banner-edge button.active");
  const align = document.querySelector("#banner-align button.active");
  return {
    id: logoId,
    asset_id: selectedAsset.banner,
    edge: edge ? edge.dataset.edge : "bottom",
    // %100 = tam genişlik (v1.4 davranışı)
    scale: +(parseInt($("banner-scale").value, 10) / 100).toFixed(3),
    align: align ? align.dataset.align : "center",
    margin: +(parseInt($("banner-margin").value, 10) / 100).toFixed(3),
  };
}

function syncLogoLabels() {
  $("logo-size-val").textContent = $("logo-size").value + "%";
  $("logo-shadow-val").textContent = $("logo-shadow").value + "%";
  $("logo-blur-val").textContent = $("logo-blur").value;
}

function syncBannerLabels() {
  const scale = parseInt($("banner-scale").value, 10);
  $("banner-scale-val").textContent = scale + "%";
  $("banner-margin-val").textContent = $("banner-margin").value + "%";
  // %100'de yatayda boş alan yok → hizalama matematiksel olarak etkisiz.
  // Ölü kontrole basılmasın diye kilitlenir ve nedeni yazılır.
  const fullWidth = scale >= 100;
  $("banner-align").querySelectorAll("button").forEach((b) => { b.disabled = fullWidth; });
  $("banner-align-note").hidden = !fullWidth;
}

// Renk (Oto/Mavi/Beyaz) yalnızca yerleşik KURUM logosu için anlamlı
function syncColorRow() {
  $("logo-color-row").hidden = !(overlayMode === "logo" && selectedAsset.logo === "builtin");
}

function renderOverlayPicker() {
  const wrap = $("overlay-picker");
  wrap.innerHTML = "";
  const options = [];
  if (overlayMode === "logo") {
    options.push({ id: "builtin", name: "Yerleşik KURUM", src: null });
    for (const it of assetCache.logos) options.push({ id: it.id, name: it.name, src: `/assets/logos/${it.filename}` });
  } else if (overlayMode === "motto") {
    for (const it of assetCache.mottos) options.push({ id: it.id, name: it.name, src: `/assets/mottos/${it.filename}` });
  } else {
    for (const it of assetCache.banners) options.push({ id: it.id, name: it.name, src: `/assets/banners/${it.filename}` });
  }
  if (!options.length) {
    const hint = document.createElement("p");
    hint.className = "overlay-empty";
    hint.textContent = OVERLAY_EMPTY_TEXT[overlayMode] || "Önce Kütüphane'den bir varlık yükle.";
    wrap.appendChild(hint);
    return;
  }
  const current = selectedAsset[overlayMode];
  for (const opt of options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "overlay-chip" + (opt.id === current ? " active" : "");
    btn.dataset.asset = opt.id;
    btn.title = opt.name;
    if (opt.src) {
      const img = document.createElement("img");
      img.src = opt.src;
      img.alt = opt.name;
      btn.appendChild(img);
    } else {
      const badge = document.createElement("span");
      badge.className = "overlay-builtin";
      badge.textContent = "KURUM";
      btn.appendChild(badge);
    }
    btn.addEventListener("click", () => {
      selectedAsset[overlayMode] = opt.id;
      renderOverlayPicker();
      syncColorRow();
      refreshLogoPreview();
    });
    wrap.appendChild(btn);
  }
}

function setOverlayMode(mode) {
  overlayMode = mode;
  selectInGroup("#logo-type", document.querySelector(`#logo-type button[data-type="${mode}"]`));
  // logo ve motto aynı konumlanabilir kontrolleri paylaşır; yalnız banner farklı
  $("logo-only").hidden = mode === "banner";
  $("banner-only").hidden = mode !== "banner";
  renderOverlayPicker();
  syncColorRow();
  refreshLogoPreview();
}

function openLogoModal(rec) {
  logoId = rec.id;
  rawPreviewSrc = `/output/${rec.filename}`;
  // varsayılanlara sıfırla
  overlayMode = "logo";
  selectedAsset = {
    logo: "builtin",
    motto: assetCache.mottos[0] ? assetCache.mottos[0].id : null,
    banner: assetCache.banners[0] ? assetCache.banners[0].id : null,
  };
  selectInGroup("#logo-type", document.querySelector('#logo-type button[data-type="logo"]'));
  $("logo-only").hidden = false;
  $("banner-only").hidden = true;
  selectInGroup("#logo-grid", document.querySelector('#logo-grid button[data-pos="bottom-right"]'));
  selectInGroup("#logo-color", document.querySelector('#logo-color button[data-color="auto"]'));
  selectInGroup("#banner-edge", document.querySelector('#banner-edge button[data-edge="bottom"]'));
  selectInGroup("#banner-align", document.querySelector('#banner-align button[data-align="center"]'));
  $("logo-size").value = 14;
  $("logo-shadow").value = 47;
  $("logo-blur").value = 6;
  $("banner-scale").value = 100;
  $("banner-margin").value = 0;
  syncLogoLabels();
  syncBannerLabels();
  $("logo-status").textContent = "";
  $("logo-preview-img").src = rawPreviewSrc; // önce ham görsel
  renderOverlayPicker();
  syncColorRow();
  $("logo-modal").hidden = false;
  refreshLogoPreview();
}

function closeLogoModal() {
  $("logo-modal").hidden = true;
  logoId = null;
  clearTimeout(logoPreviewTimer);
  logoPreviewToken++; // uçuştaki önizlemeleri iptal et
}

// motto/banner için henüz varlık seçilmediyse ham görseli göster, sunucuya gitme
function overlayNeedsAsset() {
  if (overlayMode === "motto") return !selectedAsset.motto;
  if (overlayMode === "banner") return !selectedAsset.banner;
  return false; // logo modunda her zaman yerleşik KURUM vardır
}

async function fetchOverlayPreview() {
  if (!logoId) return;
  if (overlayNeedsAsset()) {
    $("logo-preview-img").src = rawPreviewSrc;
    $("logo-status").textContent = overlayMode === "banner" ? "Bir banner seç." : "Bir motto seç.";
    return;
  }
  const token = ++logoPreviewToken;
  const url = overlayMode === "banner" ? "/api/banner/preview" : "/api/logo/preview";
  const body = overlayMode === "banner" ? readBannerOpts() : readLogoOpts();
  $("logo-preview-spin").hidden = false;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    const { b64 } = await res.json();
    if (token !== logoPreviewToken) return; // daha yeni bir önizleme devraldı
    $("logo-preview-img").src = b64;
    $("logo-status").textContent = "";
  } catch (e) {
    if (token === logoPreviewToken) $("logo-status").textContent = e.message;
  } finally {
    if (token === logoPreviewToken) $("logo-preview-spin").hidden = true;
  }
}

// debounce: slider sürüklerken sunucuyu boğmayalım
function refreshLogoPreview() {
  clearTimeout(logoPreviewTimer);
  logoPreviewTimer = setTimeout(fetchOverlayPreview, 220);
}

const OVERLAY_DONE_TEXT = { logo: "Logo eklendi.", motto: "Motto eklendi.", banner: "Banner eklendi." };

async function applyOverlay() {
  if (!logoId) return;
  if (overlayNeedsAsset()) {
    $("logo-status").textContent = overlayMode === "banner" ? "Bir banner seç." : "Bir motto seç.";
    return;
  }
  $("logo-apply").disabled = true;
  $("logo-status").textContent = "Uygulanıyor…";
  const url = overlayMode === "banner" ? "/api/banner" : "/api/logo";
  const body = overlayMode === "banner" ? readBannerOpts() : readLogoOpts();
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Hata (${res.status})`);
    }
    const { image } = await res.json();
    const doneText = OVERLAY_DONE_TEXT[overlayMode] || "Eklendi.";
    closeLogoModal();
    showPreview(image);
    statusEl.textContent = doneText;
    await loadHistory();
  } catch (e) {
    $("logo-status").textContent = e.message;
  } finally {
    $("logo-apply").disabled = false;
  }
}

$("logo-type").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-type]");
  if (btn) setOverlayMode(btn.dataset.type);
});
$("logo-grid").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-pos]");
  if (!btn) return;
  selectInGroup("#logo-grid", btn);
  refreshLogoPreview();
});
$("logo-color").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-color]");
  if (!btn) return;
  selectInGroup("#logo-color", btn);
  refreshLogoPreview();
});
$("banner-edge").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-edge]");
  if (!btn) return;
  selectInGroup("#banner-edge", btn);
  refreshLogoPreview();
});
$("banner-align").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-align]");
  if (!btn) return;
  selectInGroup("#banner-align", btn);
  refreshLogoPreview();
});
["logo-size", "logo-shadow", "logo-blur"].forEach((id) =>
  $(id).addEventListener("input", () => { syncLogoLabels(); refreshLogoPreview(); })
);
["banner-scale", "banner-margin"].forEach((id) =>
  $(id).addEventListener("input", () => { syncBannerLabels(); refreshLogoPreview(); })
);
// Sol paneldeki "Logo ekle": bindirmeyi önizlemedeki görsele uygular
$("logo-add-btn").addEventListener("click", () => {
  if (currentImage) openLogoModal(currentImage);
});
$("logo-close").addEventListener("click", closeLogoModal);
$("logo-apply").addEventListener("click", applyOverlay);
$("logo-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-logo-close")) closeLogoModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("logo-modal").hidden) closeLogoModal();
});

// ── Tema rengi / renk paleti ────────────────────────────────────────
// Palet `(seed, mode)` çiftinin SAF FONKSİYONU: tel üzerinde iki skaler
// (+ baskı kademesi) yeterli, istemci renk listesi göndermez. Renk
// matematiği ve isimlendirme sunucuda — tek doğruluk kaynağı, thecolorapi
// için CORS yok, ve repodaki tek test altyapısıyla (pytest) test edilebilir.
let activePalette = null;      // { seed, mode, colors:[{hex,name}], name } | null
let paletteStrength = "balanced";
let paletteCache = [];         // GET /api/palettes
let paletteTab = "new";
let suggestions = [];          // son öneri seti
let suggestSeed = "";          // önerilerin ÜRETİLDİĞİ tohum (input'tan değil, sunucudan)
let selectedSuggestion = null; // seçili harmoni modu
let suggestTimer = null;
let suggestToken = 0;

const HARMONY_LABELS = {
  monochrome: "Tek renk",
  analogic: "Komşu",
  complement: "Karşıt",
  "analogic-complement": "Komşu + karşıt",
  triad: "Üçlü",
  quad: "Dörtlü",
};
const STRENGTH_LABELS = { hint: "İpucu", balanced: "Dengeli", strict: "Katı" };
const DEFAULT_SEED = "#c86a3c";

// ── Renk seçici (HSV karesi + ton kaydırıcısı) ───────────────────────
// Model HSV: alanın zemini iki gradyanla kurulan klasik HSV karesi
// (x = doygunluk, y = 1 - parlaklık), o yüzden nişangah konumunun renge
// birebir karşılık gelmesi için iç model de HSV olmak zorunda.
//
// HSV state AYRI tutuluyor, hex'ten her seferinde türetilmiyor: sürüklerken
// hex'e gidip dönmek yuvarlama yüzünden nişangahı zıplatır.
let pick = { h: 24, s: 0.7, v: 0.78 };

function hsvToRgb(h, s, v) {
  const c = v * s;
  const hp = ((((h % 360) + 360) % 360) / 60);
  const x = c * (1 - Math.abs((hp % 2) - 1));
  const [r, g, b] =
    hp < 1 ? [c, x, 0] : hp < 2 ? [x, c, 0] : hp < 3 ? [0, c, x] :
    hp < 4 ? [0, x, c] : hp < 5 ? [x, 0, c] : [c, 0, x];
  const m = v - c;
  return [r + m, g + m, b + m].map((n) => Math.round(n * 255));
}

function rgbToHsv(r, g, b) {
  const [rn, gn, bn] = [r / 255, g / 255, b / 255];
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const d = max - min;
  let h = null; // akromatik: ton tanımsız (bkz. setPickFromHex)
  if (d) {
    if (max === rn) h = (((gn - bn) / d) % 6 + 6) % 6;
    else if (max === gn) h = (bn - rn) / d + 2;
    else h = (rn - gn) / d + 4;
    h *= 60;
  }
  return { h, s: max ? d / max : 0, v: max };
}

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
}

function pickHex() { return rgbToHex(hsvToRgb(pick.h, pick.s, pick.v)); }

function setPickFromHex(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  const hsv = rgbToHsv(...rgb);
  // Gri/siyah/beyazda ton sayısal olarak anlamsız — MEVCUT tonu koru, yoksa
  // kullanıcı beyaza sürüklediğinde alanın zemini kırmızıya sıçrar.
  pick = { h: hsv.h === null ? pick.h : hsv.h, s: hsv.s, v: hsv.v };
  return true;
}

function renderPicker({ syncHexField = true } = {}) {
  const hex = pickHex();
  const field = $("palette-field");
  field.style.background =
    `linear-gradient(0deg, #000, transparent),` +
    `linear-gradient(90deg, #fff, hsl(${pick.h} 100% 50%))`;
  field.setAttribute("aria-valuetext", `doygunluk ${Math.round(pick.s * 100)}%, ` +
    `parlaklık ${Math.round(pick.v * 100)}%, ${hex}`);
  const thumb = $("palette-field-thumb");
  thumb.style.left = `${pick.s * 100}%`;
  thumb.style.top = `${(1 - pick.v) * 100}%`;
  thumb.style.background = hex;
  $("palette-hue").value = String(Math.round(pick.h));
  $("palette-seed-sw").style.background = hex;
  // Kullanıcı yazarken alanı ezmemek için hex girdisi opsiyonel güncellenir.
  if (syncHexField) $("palette-seed-hex").value = hex;
}

/** Alandaki bir noktadan doygunluk/parlaklık. */
function setPickFromPoint(clientX, clientY) {
  const r = $("palette-field").getBoundingClientRect();
  if (!r.width || !r.height) return;
  pick.s = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
  pick.v = 1 - Math.min(1, Math.max(0, (clientY - r.top) / r.height));
  renderPicker();
  scheduleSuggest();
}

function paletteStatus(msg) { $("palette-status").textContent = msg || ""; }
function paletteModalStatus(msg) { $("palette-modal-status").textContent = msg || ""; }

/** 422 gövdesi bir dizi olabiliyor; `err.detail` doğrudan basılırsa çöp çıkar. */
function detailText(err) {
  const d = err && err.detail;
  if (!d) return "";
  if (typeof d === "string") return d;
  if (!Array.isArray(d)) return "";
  if (d.some((e) => e && e.type === "extra_forbidden")) {
    return "Sunucu bu alanı tanımıyor — eski bir sunucu süreci çalışıyor. " +
           "./run.sh ile yeniden başlat.";
  }
  return d.map((e) => (e && e.msg) || "").filter(Boolean).join("; ");
}

/** Renk örneği şeridi. Örneklerin ÜSTÜNE metin yazılmaz — bkz. style.css notu. */
function swatchRow(colors) {
  const row = document.createElement("span");
  row.className = "palette-sw-row";
  for (const c of colors || []) {
    const sw = document.createElement("span");
    sw.className = "palette-sw";
    // Keyfi kullanıcı rengi: bu dosyadaki tek meşru satır-içi stil kullanımı,
    // çünkü değer çalışma anında belli oluyor ve CSS'e yazılamıyor.
    sw.style.background = c.hex;
    sw.title = `${c.name} · ${c.hex}`;
    row.appendChild(sw);
  }
  return row;
}

function paletteTitleOf(pal) {
  return pal.name || HARMONY_LABELS[pal.mode] || pal.mode;
}

function renderPalettePanel() {
  const chip = $("palette-chip");
  if (!activePalette) {
    chip.hidden = true;
    $("palette-strength-row").hidden = true;
    $("palette-mode-note").hidden = true;
    return;
  }
  chip.hidden = false;
  const holder = $("palette-chip-sw");
  holder.innerHTML = "";
  holder.appendChild(swatchRow(activePalette.colors));
  $("palette-label").textContent =
    `${paletteTitleOf(activePalette)} · ${STRENGTH_LABELS[paletteStrength]}`;

  $("palette-strength-row").hidden = false;
  selectInGroup("#palette-strength",
    document.querySelector(`#palette-strength button[data-strength="${paletteStrength}"]`));

  // Aynı palet iki farklı ifadeyle gidiyor: üretimde "bu renkleri kullan",
  // düzenlemede "renkleri kaydır, kompozisyonu koru". Kullanıcı hangisinin
  // geçerli olduğunu görmeli.
  const note = $("palette-mode-note");
  note.hidden = false;
  note.textContent = source
    ? "Referans görselde renk derecelendirmesi olarak uygulanır — kompozisyon korunur."
    : "Renk yönlendirmesi prompt'un sonuna İngilizce eklenir.";
}

function readPaletteOpts() {
  if (!activePalette) return {};
  const opts = {
    palette_hex: activePalette.seed,
    palette_mode: activePalette.mode,
    palette_strength: paletteStrength,
  };
  // Kayıtlı palette id de gider: sunucu adları kaydın dondurulmuş halinden
  // okur, böylece kütüphanede görünen ad ile prompt'a giden ad ayrışmaz.
  if (activePalette.id) opts.palette_id = activePalette.id;
  return opts;
}

function applyPalette({ seed, mode, colors, name = "", strength = null, id = null }) {
  activePalette = { seed, mode, colors, name, id };
  if (strength) paletteStrength = strength;
  renderPalettePanel();
  paletteStatus(`Palet uygulandı: ${paletteTitleOf(activePalette)}`);
}

function clearPalette() {
  activePalette = null;
  renderPalettePanel();
  paletteStatus("Palet kaldırıldı.");
}

// ── Öneriler ────────────────────────────────────────────────────────
function scheduleSuggest() {
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(fetchSuggestions, 220);
}

async function fetchSuggestions() {
  const token = ++suggestToken;
  paletteModalStatus("Paletler hesaplanıyor…");
  try {
    const res = await fetch("/api/palette/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hex: pickHex() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const body = await res.json();
    // Sıra dışı yanıt guard'ı (logoPreviewToken deseni). DOM'dan ÖNCE state'i
    // korumak asıl önemli olan: geç gelen bir yanıt kullanıcının sonra
    // KAYDEDECEĞİ palete yanlış renk/isim yazarsa hata kalıcı olur.
    if (token !== suggestToken) return;
    suggestions = body.items || [];
    suggestSeed = body.seed;
    selectedSuggestion = null;
    renderSuggestions();
    paletteModalStatus("");
  } catch (e) {
    if (token !== suggestToken) return;
    suggestions = [];
    suggestSeed = "";
    selectedSuggestion = null;
    renderSuggestions();
    paletteModalStatus(e.message);
  }
}

function makeChoiceButton({ title, colors, subtitle }) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "palette-choice";
  const names = (colors || []).map((c) => c.name).join(", ");
  // Bilgi hiçbir zaman renk algısına bağlı olmasın: ad + hex her zaman metinde.
  btn.setAttribute("aria-label", `${title}: ${names}`);

  const titleEl = document.createElement("span");
  titleEl.className = "palette-choice-title";
  titleEl.textContent = title;
  btn.appendChild(titleEl);
  btn.appendChild(swatchRow(colors));

  const sub = document.createElement("span");
  sub.className = "palette-choice-names";
  sub.textContent = subtitle === undefined ? names : subtitle;
  btn.appendChild(sub);
  return btn;
}

function emptyNote(grid, text) {
  const p = document.createElement("p");
  p.className = "palette-empty";
  p.textContent = text;
  grid.appendChild(p);
}

function renderSuggestions() {
  const grid = $("palette-suggestions");
  grid.innerHTML = "";
  if (!suggestions.length) {
    emptyNote(grid, "Palet önerisi yok — bir tema rengi seç.");
  } else {
    for (const item of suggestions) {
      const btn = makeChoiceButton({
        title: HARMONY_LABELS[item.mode] || item.mode,
        colors: item.colors,
      });
      btn.setAttribute("aria-pressed", String(selectedSuggestion === item.mode));
      btn.addEventListener("click", () => {
        selectedSuggestion = item.mode;
        renderSuggestions();
      });
      grid.appendChild(btn);
    }
  }
  const ready = currentSuggestion() !== null;
  $("palette-save").disabled = !ready;
  $("palette-apply").disabled = !ready;
}

function currentSuggestion() {
  return suggestions.find((s) => s.mode === selectedSuggestion) || null;
}

// ── Kütüphane ───────────────────────────────────────────────────────
async function loadPalettes() {
  try {
    const res = await fetch("/api/palettes");
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    paletteCache = (await res.json()).items || [];
  } catch {
    paletteCache = [];
    paletteStatus("Palet kütüphanesi alınamadı.");
  }
  if (!$("palette-modal").hidden && paletteTab === "saved") renderPaletteLibrary();
}

function renderPaletteLibrary() {
  const grid = $("palette-lib-grid");
  grid.innerHTML = "";
  if (!paletteCache.length) {
    emptyNote(grid, "Henüz kayıtlı palet yok — \"Yeni palet\" sekmesinden oluştur.");
    return;
  }
  for (const rec of paletteCache) {
    const cell = document.createElement("div");
    cell.className = "palette-lib-cell";

    const btn = makeChoiceButton({
      title: rec.name,
      colors: rec.colors,
      subtitle: `${HARMONY_LABELS[rec.mode] || rec.mode} · ` +
                `${STRENGTH_LABELS[rec.strength] || rec.strength}`,
    });
    btn.addEventListener("click", () => {
      // Kayıttaki renkler zaten dondurulmuş — yeniden hesaplamaya gerek yok.
      applyPalette({ seed: rec.seed, mode: rec.mode, colors: rec.colors,
                     name: rec.name, strength: rec.strength, id: rec.id });
      closePaletteModal();
    });
    cell.appendChild(btn);

    const del = document.createElement("button");
    del.type = "button";
    del.className = "palette-lib-del";
    del.setAttribute("aria-label", `${rec.name} paletini sil`);
    del.title = "Paleti sil";
    del.textContent = "×";
    del.addEventListener("click", (e) => { e.stopPropagation(); deletePalette(rec); });
    cell.appendChild(del);

    grid.appendChild(cell);
  }
}

async function savePalette() {
  const item = currentSuggestion();
  if (!item) return;
  const name = await promptDialog(
    "Paleti kaydet",
    "\"Kayıtlı paletler\" sekmesinden sonraki üretimlerde yeniden seçebilirsin.",
    { okLabel: "Kaydet" });
  if (!name) return;
  try {
    const res = await fetch("/api/palettes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, seed: suggestSeed, mode: item.mode,
                             strength: paletteStrength }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const saved = (await res.json()).palette;
    await loadPalettes();
    applyPalette({ seed: saved.seed, mode: saved.mode, colors: saved.colors,
                   name: saved.name, strength: saved.strength, id: saved.id });
    closePaletteModal();
  } catch (e) {
    paletteModalStatus(e.message);
  }
}

async function deletePalette(rec) {
  const ok = await confirmDialog(
    `"${rec.name}" paletini sil?`,
    "Palet kütüphaneden kaldırılır. Üretilmiş görseller etkilenmez.");
  if (!ok) return;
  try {
    const res = await fetch(`/api/palettes/${rec.id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    await loadPalettes();
    renderPaletteLibrary();
    paletteModalStatus("Palet silindi.");
  } catch (e) {
    paletteModalStatus(e.message);
  }
}

// ── Modal ───────────────────────────────────────────────────────────
function setPaletteTab(tab) {
  paletteTab = tab;
  $("palette-new").hidden = tab !== "new";
  $("palette-saved").hidden = tab !== "saved";
  selectInGroup("#palette-tabs",
    document.querySelector(`#palette-tabs button[data-ptab="${tab}"]`));
  if (tab === "saved") renderPaletteLibrary();
}

function openPaletteModal() {
  // openLogoModal dersi: HER kontrol açılışta varsayılana döndürülmeli,
  // yoksa modal önceki tohumu/seçimi sızdırır.
  setPickFromHex(activePalette ? activePalette.seed : DEFAULT_SEED);
  renderPicker();
  suggestions = [];
  suggestSeed = "";
  selectedSuggestion = null;
  renderSuggestions();
  paletteModalStatus("");
  setPaletteTab("new");
  $("palette-modal").hidden = false;
  fetchSuggestions();
}

function closePaletteModal() { $("palette-modal").hidden = true; }

$("palette-btn").addEventListener("click", openPaletteModal);
$("palette-close").addEventListener("click", closePaletteModal);
$("palette-clear").addEventListener("click", clearPalette);
$("palette-save").addEventListener("click", savePalette);
$("palette-apply").addEventListener("click", () => {
  const item = currentSuggestion();
  if (!item) return;
  // Tohum sunucunun döndürdüğü normalize edilmiş değer — arada input
  // değiştiyse önerilerle tutarsız bir palet uygulanmasın.
  applyPalette({ seed: suggestSeed, mode: item.mode, colors: item.colors });
  closePaletteModal();
});

$("palette-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-palette-close")) closePaletteModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("palette-modal").hidden) {
    closePaletteModal();
  }
});

$("palette-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-ptab]");
  if (btn) setPaletteTab(btn.dataset.ptab);
});

// ── Seçici olayları ─────────────────────────────────────────────────
// Sürükleme: pointer capture kullanılıyor — window'a dinleyici ekleyip
// kaldırmaya gerek kalmıyor, imleç alanın dışına çıksa da takip sürüyor ve
// sızdırılacak bir dinleyici olmuyor.
const paletteField = $("palette-field");
paletteField.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  paletteField.setPointerCapture(e.pointerId);
  setPickFromPoint(e.clientX, e.clientY);
});
paletteField.addEventListener("pointermove", (e) => {
  if (paletteField.hasPointerCapture(e.pointerId)) setPickFromPoint(e.clientX, e.clientY);
});

// Alan klavyeyle de ayarlanabilir: yalnızca fare ile çalışan bir renk seçici
// klavye kullanıcısı için ton kaydırıcısı + hex alanına mahkûm ederdi.
const PICK_STEP = 0.01;
const PICK_STEP_BIG = 0.1;
paletteField.addEventListener("keydown", (e) => {
  const step = e.shiftKey ? PICK_STEP_BIG : PICK_STEP;
  const moves = {
    ArrowLeft: [-step, 0], ArrowRight: [step, 0],
    ArrowUp: [0, step], ArrowDown: [0, -step],
  };
  const move = moves[e.key];
  if (!move) return;
  e.preventDefault();
  pick.s = Math.min(1, Math.max(0, pick.s + move[0]));
  pick.v = Math.min(1, Math.max(0, pick.v + move[1]));
  renderPicker();
  scheduleSuggest();
});

$("palette-hue").addEventListener("input", () => {
  pick.h = Number($("palette-hue").value);
  renderPicker();
  scheduleSuggest();
});

// Marka rehberi sana tekerlek konumu değil hex verir; elle yazılabilmeli.
// syncHexField=false: kullanıcı yazarken girdiyi normalize edip imleci
// zıplatmamak için.
$("palette-seed-hex").addEventListener("input", () => {
  if (!setPickFromHex($("palette-seed-hex").value)) return;
  renderPicker({ syncHexField: false });
  scheduleSuggest();
});
$("palette-seed-hex").addEventListener("blur", () => renderPicker());

// EyeDropper yalnızca Chromium'da var; yoksa buton hiç gösterilmez.
if (window.EyeDropper) {
  $("palette-eyedrop").hidden = false;
  $("palette-eyedrop").addEventListener("click", async () => {
    try {
      const { sRGBHex } = await new EyeDropper().open();
      if (setPickFromHex(sRGBHex)) { renderPicker(); scheduleSuggest(); }
    } catch {
      // Kullanıcı Esc ile vazgeçti — hata değil, sessizce geç.
    }
  });
}

$("palette-strength").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-strength]");
  if (!btn) return;
  paletteStrength = btn.dataset.strength;
  renderPalettePanel();
});

// ── Azure ayarları (admin, write-only) ──────────────────────────────
// API key hiçbir zaman sunucudan çekilmez/gösterilmez; sadece yazılır.
let configured = false;

function applyConfigured(s) {
  configured = !!(s && s.configured);
  $("go").disabled = !configured;
  if (s && s.endpoint) $("set-endpoint").value = s.endpoint;
  $("set-key").placeholder = configured
    ? "Kayıtlı · değiştirmek için yeni anahtar yaz"
    : "Azure API anahtarını yapıştır";
  if (!configured) {
    statusEl.textContent = "Başlamak için Azure ayarlarını gir (sağ üstteki ⚙).";
  } else if (statusEl.textContent.startsWith("Başlamak için")) {
    statusEl.textContent = "";
  }
}

async function loadSettings(openIfMissing) {
  try {
    const res = await fetch("/api/settings");
    const s = await res.json();
    applyConfigured(s);
    if (!configured && openIfMissing) openSettings();
  } catch {
    // durum alınamadıysa fail-closed: butonu kilitle, kullanıcıyı ayarlara yönlendir
    configured = false;
    $("go").disabled = true;
    statusEl.textContent = "Ayar durumu alınamadı. Azure ayarlarını kontrol et (sağ üstteki ⚙).";
    if (openIfMissing) openSettings();
  }
}

function openSettings() {
  $("set-key").value = ""; // her açılışta boş (write-only)
  $("settings-status").textContent = "";
  $("settings-modal").hidden = false;
  setTimeout(() => $("set-endpoint").focus(), 0);
}

function closeSettings() {
  $("settings-modal").hidden = true;
}

async function saveSettings() {
  const base_url = $("set-endpoint").value.trim();
  const api_key = $("set-key").value;
  const st = $("settings-status");
  if (!base_url) { st.textContent = "Endpoint gerekli."; return; }
  if (!configured && !api_key.trim()) { st.textContent = "İlk kurulumda API key gerekli."; return; }

  $("settings-save").disabled = true;
  st.textContent = "Kaydediliyor…";
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, base_url }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    applyConfigured(await res.json());
    $("set-key").value = "";
    st.textContent = "Kaydedildi.";
    setTimeout(closeSettings, 550);
  } catch (e) {
    st.textContent = e.message;
  } finally {
    $("settings-save").disabled = false;
  }
}

$("settings-btn").addEventListener("click", openSettings);
$("settings-close").addEventListener("click", closeSettings);
$("settings-save").addEventListener("click", saveSettings);
$("settings-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-close")) closeSettings();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("settings-modal").hidden) closeSettings();
});

$("go").addEventListener("click", run);
syncFolderView();
loadFolders();
loadHistory();
loadSettings(true);
loadAssets("logos");
loadAssets("mottos");
loadAssets("banners");
// Palet varsayılan olarak KAPALI: açılışta öneri istenmez, prompt'a hiçbir
// şey eklenmez. Yalnızca kütüphane çekilir ki "Kayıtlı paletler" hazır olsun.
loadPalettes();
