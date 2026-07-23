const $ = (id) => document.getElementById(id);
const statusEl = $("status");

function setLoading(on) {
  $("progress").hidden = !on;
}

async function generate() {
  const prompt = $("prompt").value.trim();
  if (!prompt) { statusEl.textContent = "Önce bir prompt yaz."; return; }
  const body = {
    prompt,
    size: $("size").value,
    quality: $("quality").value,
    n: parseInt($("n").value, 10),
  };
  $("go").disabled = true;
  clearUploadPreviewUrl();
  setLoading(true);
  statusEl.textContent = "Üretiliyor…";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    const { images } = await res.json();
    if (images[0]) showPreview(images[0]);
    statusEl.textContent = `${images.length} görsel üretildi.`;
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    $("go").disabled = false;
    setLoading(false);
  }
}

function showPreviewSrc(src, alt = "") {
  const preview = $("preview");
  preview.className = "preview";
  preview.innerHTML = "";
  const img = document.createElement("img");
  img.src = src;
  img.alt = alt;
  preview.appendChild(img);
}

function showPreview(rec) {
  showPreviewSrc(`/output/${rec.filename}`, (rec.prompt || "").slice(0, 60));
}

async function addLogo(id) {
  statusEl.textContent = "Logo bindiriliyor…";
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
    editBtn.addEventListener("click", () => selectEditSource(rec));

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

let editSourceId = null;
let uploadPreviewUrl = null;

function clearUploadPreviewUrl() {
  if (uploadPreviewUrl) {
    URL.revokeObjectURL(uploadPreviewUrl);
    uploadPreviewUrl = null;
  }
}

function selectEditSource(rec) {
  editSourceId = rec.id;
  $("edit-file").value = "";
  clearUploadPreviewUrl();
  $("edit-source").textContent = `Kaynak: ${(rec.prompt || rec.id).slice(0, 50)} (galeri)`;
  $("edit-panel").open = true;
  showPreview(rec);
}

$("edit-file").addEventListener("change", () => {
  const files = $("edit-file").files;
  if (files.length) {
    editSourceId = null;
    $("edit-source").textContent = `Kaynak: ${files[0].name} (yükleme)`;
    clearUploadPreviewUrl();
    uploadPreviewUrl = URL.createObjectURL(files[0]);
    showPreviewSrc(uploadPreviewUrl, files[0].name);
  }
});

async function runEdit() {
  const prompt = $("edit-prompt").value.trim();
  if (!prompt) { statusEl.textContent = "Düzenleme promptu yaz."; return; }
  const hasFile = $("edit-file").files.length > 0;
  if (!hasFile && !editSourceId) { statusEl.textContent = "Bir görsel yükle veya galeriden seç."; return; }

  const fd = new FormData();
  fd.append("prompt", prompt);
  fd.append("size", $("size").value);
  fd.append("quality", $("quality").value);
  fd.append("n", "1");
  if (hasFile) fd.append("file", $("edit-file").files[0]);
  else fd.append("source_id", editSourceId);

  $("edit-go").disabled = true;
  setLoading(true);
  statusEl.textContent = "Düzenleniyor…";
  try {
    const res = await fetch("/api/edit", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    const { images } = await res.json();
    if (images[0]) showPreview(images[0]);
    clearUploadPreviewUrl();
    statusEl.textContent = "Düzenleme tamam.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    $("edit-go").disabled = false;
    setLoading(false);
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
    if (editSourceId === rec.id) {
      editSourceId = null;
      $("edit-source").textContent = "";
    }
    statusEl.textContent = "Silindi.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

$("go").addEventListener("click", generate);
$("edit-go").addEventListener("click", runEdit);
loadHistory();
