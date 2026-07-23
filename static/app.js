const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const ACCEPTED_UPLOAD_TYPES = ["image/png", "image/jpeg", "image/webp"];

// Referans görsel: null | { kind: "upload", file, label } | { kind: "gallery", id, label }
let source = null;
let uploadPreviewUrl = null;

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
}

function showPreview(rec) {
  showPreviewSrc(`/output/${rec.filename}`, (rec.prompt || "").slice(0, 60));
}

// Referans durumunu arayüze yansıt: chip + ana buton etiketi
function renderSource() {
  const chip = $("ref-chip");
  if (source) {
    $("ref-label").textContent = source.label;
    chip.hidden = false;
    $("go").textContent = "Görseli düzenle";
  } else {
    chip.hidden = true;
    $("go").textContent = "Üret";
  }
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
  renderSource();
}

function setGallerySource(rec) {
  clearUploadPreviewUrl();
  $("file-input").value = "";
  source = { kind: "gallery", id: rec.id, label: `Referans: ${(rec.prompt || rec.id).slice(0, 40)}` };
  showPreview(rec);
  renderSource();
  $("prompt").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearSource() {
  clearUploadPreviewUrl();
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
  statusEl.textContent = editing ? "Düzenleniyor…" : "Üretiliyor…";
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

async function addLogo(id) {
  statusEl.textContent = "Logo bindiriliyor…";
  const gen = startProgress();
  let ok = false;
  try {
    const res = await fetch("/api/logo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    const { image } = await res.json();
    showPreview(image);
    statusEl.textContent = "Logo eklendi.";
    ok = true;
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
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

    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = prompt.slice(0, 60);
    img.title = prompt;
    img.addEventListener("click", () => showPreview(rec));

    const downloadLink = document.createElement("a");
    downloadLink.setAttribute("href", `/output/${rec.filename}`);
    downloadLink.setAttribute("download", "");
    downloadLink.textContent = "İndir";

    const logoBtn = document.createElement("button");
    logoBtn.textContent = "Logo";
    logoBtn.addEventListener("click", () => addLogo(rec.id));

    const editBtn = document.createElement("button");
    editBtn.textContent = "Düzenle";
    editBtn.addEventListener("click", () => setGallerySource(rec));

    const acts = document.createElement("div");
    acts.className = "acts";
    acts.appendChild(downloadLink);
    acts.appendChild(logoBtn);
    acts.appendChild(editBtn);

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
