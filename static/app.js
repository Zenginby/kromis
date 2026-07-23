const $ = (id) => document.getElementById(id);
const statusEl = $("status");

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
  }
}

function showPreview(rec) {
  $("preview").className = "preview";
  $("preview").innerHTML = `<img src="/output/${rec.filename}" alt="">`;
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

    const delBtn = document.createElement("button");
    delBtn.className = "danger";
    delBtn.textContent = "Sil";
    delBtn.addEventListener("click", () => deleteImage(rec));

    const acts = document.createElement("div");
    acts.className = "acts";
    acts.appendChild(downloadLink);
    acts.appendChild(logoBtn);
    acts.appendChild(editBtn);
    acts.appendChild(delBtn);

    const card = document.createElement("div");
    card.className = "card";
    card.appendChild(img);
    card.appendChild(acts);

    g.appendChild(card);
  }
}

let editSourceId = null;

function selectEditSource(rec) {
  editSourceId = rec.id;
  $("edit-file").value = "";
  $("edit-source").textContent = `Kaynak: ${(rec.prompt || rec.id).slice(0, 50)} (galeri)`;
  $("edit-panel").open = true;
  showPreview(rec);
}

$("edit-file").addEventListener("change", () => {
  if ($("edit-file").files.length) {
    editSourceId = null;
    $("edit-source").textContent = `Kaynak: ${$("edit-file").files[0].name} (yükleme)`;
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
  statusEl.textContent = "Düzenleniyor…";
  try {
    const res = await fetch("/api/edit", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    const { images } = await res.json();
    if (images[0]) showPreview(images[0]);
    statusEl.textContent = "Düzenleme tamam.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  } finally {
    $("edit-go").disabled = false;
  }
}

async function deleteImage(rec) {
  if (!confirm("Bu görseli silmek istediğine emin misin?")) return;
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
