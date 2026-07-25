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

  let request;
  if (editing) {
    const fd = new FormData();
    fd.append("prompt", prompt);
    fd.append("size", size);
    fd.append("quality", quality);
    fd.append("n", n);
    if (source.kind === "upload") fd.append("file", source.file);
    else fd.append("source_id", source.id);
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
      body: JSON.stringify({ prompt, size, quality, n: parseInt(n, 10) }),
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
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    const { images } = await res.json();
    if (images[0]) showPreview(images[0]);
    clearUploadPreviewUrl(); // sonuç sunucu URL'inden gösteriliyor; blob artık gereksiz
    statusEl.textContent = editing ? "Düzenleme tamam." : `${images.length} görsel üretildi.`;
    ok = true;
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    $("go").disabled = !configured; // yapılandırma kaybolduysa kapıyı yeniden açma
    stopProgress(ok, gen);
  }
}

async function deleteImage(rec) {
  if (!confirm("Bu görseli silmek istediğinizden emin misiniz?")) return;
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

async function loadHistory() {
  const res = await fetch("/api/history");
  const { images } = await res.json();
  const g = $("gallery");
  g.innerHTML = "";
  for (const rec of images) {
    const prompt = rec.prompt || "";

    // Küçük resme tıklamak doğrudan düzenleme moduna alır (ayrı "Düzenle" butonu yok)
    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = prompt.slice(0, 60);
    img.title = prompt ? `${prompt}\n\nDüzenlemek için tıkla` : "Düzenlemek için tıkla";
    img.addEventListener("click", () => setGallerySource(rec));

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
    card.appendChild(img);
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
  if (!confirm("Bu varlığı silmek istediğinizden emin misiniz?")) return;
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
  if (e.key === "Escape" && !$("assets-modal").hidden) closeAssetsModal();
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
  $("banner-scale-val").textContent = $("banner-scale").value + "%";
  $("banner-margin-val").textContent = $("banner-margin").value + "%";
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
  if (e.key === "Escape" && !$("logo-modal").hidden) closeLogoModal();
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
  if (e.key === "Escape" && !$("settings-modal").hidden) closeSettings();
});

$("go").addEventListener("click", run);
loadHistory();
loadSettings(true);
loadAssets("logos");
loadAssets("mottos");
loadAssets("banners");
