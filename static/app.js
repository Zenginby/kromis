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
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <img src="/output/${rec.filename}" alt="${(rec.prompt || "").slice(0, 60)}"
           title="${(rec.prompt || "").replace(/"/g, "'")}">
      <div class="acts">
        <a href="/output/${rec.filename}" download>İndir</a>
        <button>Logo</button>
      </div>`;
    card.querySelector("img").addEventListener("click", () => showPreview(rec));
    card.querySelector("button").addEventListener("click", () => addLogo(rec.id));
    g.appendChild(card);
  }
}

$("go").addEventListener("click", generate);
loadHistory();
