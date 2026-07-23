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

    const acts = document.createElement("div");
    acts.className = "acts";
    acts.appendChild(downloadLink);
    acts.appendChild(logoBtn);

    const card = document.createElement("div");
    card.className = "card";
    card.appendChild(img);
    card.appendChild(acts);

    g.appendChild(card);
  }
}

$("go").addEventListener("click", generate);
loadHistory();
