// GPT-Image Studio — klasörler (iç içe) ve galeri çoklu seçimi.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

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

