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
// Medya araması (A3 / Adım 7b). Boş dize = arama kapalı. Sorgu KÜÇÜK harfe
// indirilmiş tutulur; eşleşme de öyle yapılır (Türkçe İ/ı tuzağına rağmen
// toLowerCase iki tarafa da aynı biçimde uygulandığı için tutarlı).
let searchQuery = "";

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

// Şerit ipucusunun normal (seçim dışı) metni — seçim modunda geçici olarak değişir.
// İki cümle iki farklı koşula bağlı: TAŞIMA yalnız klasör varken anlamlı, İÇE
// AKTARMA her zaman geçerli (klasör hiç yokken de görseller alanına bırakılabilir).
// v1.11'e kadar ipucu klasör yokken hiç görünmüyordu; bırakma özelliği o yüzden
// yeni kullanıcı için keşfedilemez kalırdı.
const FOLDER_HINT_DEFAULT = "Bir görseli klasör kartına sürükleyip bırakarak taşıyabilirsin.";
const FOLDER_HINT_IMPORT =
  "Bilgisayarındaki bir görseli klasör kartına ya da bu alana bırakarak içe aktarabilirsin.";

function renderFolderHint() {
  const el = $("folder-hint");
  // Aramadayken ipucu gizli: klasör kartları da ekranda değil, "kartına
  // sürükle" cümlesi hedefsiz kalırdı.
  el.hidden = searchQuery.length > 0;
  if (el.hidden || selectMode) return;   // seçim modunda metni syncSelectUI yönetiyor
  el.textContent = folderCache.length
    ? `${FOLDER_HINT_DEFAULT} ${FOLDER_HINT_IMPORT}`
    : FOLDER_HINT_IMPORT;
}

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
  const searching = searchQuery.length > 0;
  // Arama klasör sınırından bağımsız (tasarım §4.1): sorgu yazıldığı an
  // kırıntı, klasör kartları ve bölüm başlığı çekilir; yerini kapsamı
  // söyleyen tek etiket alır ("Arama sonuçları — tüm klasörler").
  $("search-label").hidden = !searching;
  document.querySelector("#view-media .gallery-head").hidden = searching;
  $("images-title").hidden = searching;
  $("folder-grid").hidden = searching;
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
  renderFolderHint();
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
  renderFolderHint();
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

// Bir seferde aktarılacak azami dosya. Aşan kısım KIRPILIR ve söylenir —
// sessiz kırpma "hepsini aktardım" gibi görünür.
const MAX_IMPORT_FILES = 20;

// Bilgisayardan bırakılan dosyaları hedefe (klasör ya da kök) aktarır.
//
// SIRAYLA gönderilir, paralel DEĞİL: sunucuda her aktarma history.json'ın
// TAMAMINI yeniden yazıyor; eşzamanlı istekler aynı listeyi okur ve biri
// diğerinin kaydını ezer — dosya diskte olur, galeride görünmez, hiçbir hata
// mesajı da çıkmaz. (storage.set_folder_many/delete_many'nin "tek yazım"
// gerekçesiyle aynı sebep.)
async function importFiles(fileList, folderId, targetName) {
  const dropped = [...fileList];
  const images = dropped.filter((f) => ACCEPTED_UPLOAD_TYPES.includes(f.type));
  // Finder'dan bir KLASÖR sürüklenirse tür boş gelir → buradan elenir.
  const wrongType = dropped.length - images.length;
  const batch = images.slice(0, MAX_IMPORT_FILES);
  const overflow = images.length - batch.length;
  if (!batch.length) {
    statusEl.textContent = dropped.length
      ? "PNG, JPEG veya WebP bir görsel bırak."
      : "Bırakılan dosya okunamadı.";
    return;
  }

  const failures = [];
  let done = 0;
  for (const file of batch) {
    statusEl.textContent = `"${targetName}" içine aktarılıyor… ${done + 1}/${batch.length}`;
    const fd = new FormData();
    fd.append("file", file);
    if (folderId) fd.append("folder_id", folderId);
    try {
      const res = await fetch("/api/import", { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(detailText(err) || `Hata (${res.status})`);
      }
      done++;
    } catch (e) {
      // Tek dosyanın hatası kalanları düşürmez; hepsi sonda sayılır.
      failures.push(`${file.name}: ${e.message}`);
    }
  }

  statusEl.textContent = [
    done
      ? (done > 1 ? `${done} görsel "${targetName}" içine aktarıldı.`
                  : `Görsel "${targetName}" içine aktarıldı.`)
      : "Hiçbir görsel aktarılamadı.",
    wrongType ? `${wrongType} dosya atlandı (PNG, JPEG veya WebP değil).` : null,
    overflow ? `${overflow} dosya alınmadı (bir seferde en fazla ${MAX_IMPORT_FILES}).` : null,
    failures.length ? failures.join(" · ") : null,
  ].filter(Boolean).join(" ");
  await Promise.all([loadFolders(), loadHistory()]);
}

// Bir öğeyi bırakma hedefi yapar (klasör kartı / "Klasörsüz" / bir üst seviye kartı).
// TEK hedef, İKİ iş — ayırt eden şey sürüklenenin türü:
//   iç sürükleme (IMAGE_DND_TYPE) → galerideki görseli o klasöre TAŞI
//   bilgisayardan dosya (Files)   → o klasöre İÇE AKTAR
// İmleç de farklı (move / copy), böylece bırakmadan önce hangi iş olduğu belli.
function makeDropTarget(el, folderId, targetName) {
  const carriesImage = (e) => !!e.dataTransfer && [...e.dataTransfer.types].includes(IMAGE_DND_TYPE);
  el.addEventListener("dragover", (e) => {
    const image = carriesImage(e);
    if (!image && !hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = image ? "move" : "copy";
    el.classList.add("drop-hover");
  });
  el.addEventListener("dragleave", () => el.classList.remove("drop-hover"));
  el.addEventListener("drop", (e) => {
    el.classList.remove("drop-hover");
    const image = carriesImage(e);
    if (!image && !hasFiles(e)) return;
    e.preventDefault();
    // stopPropagation ŞART: olay .gallery-wrap bölgesine çıkarsa aynı dosya
    // İKİNCİ kez (bu kez bulunulan görünüme) aktarılır — "bazen iki kopya
    // oluşuyor" diye görünen, teşhisi zor bir kirlenme.
    e.stopPropagation();
    if (image) {
      const imageId = e.dataTransfer.getData(IMAGE_DND_TYPE);
      if (imageId) moveImages(imageId, folderId, targetName);
      return;
    }
    importFiles(e.dataTransfer.files, folderId, targetName);
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
  if (selectMode) {
    $("folder-hint").textContent = selected.size
      ? "Seçili görselleri taşımak için birini klasör kartına sürükle."
      : "Görselleri seç, sonra taşımak için birini klasör kartına sürükle.";
  } else {
    renderFolderHint();   // seçim dışı metnin TEK kaynağı (taşıma + içe aktarma)
  }
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
// `media-picker` muhafızı (plan B10): seçici açıkken Escape ONU kapatmalı.
// Muhafız olmasaydı tek Escape hem seçiciyi kapatır hem arkadaki seçim
// modundan çıkarırdı — kullanıcı bir tuşla iki şey kaybederdi.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && selectMode && $("confirm-modal").hidden
      && $("media-picker").hidden) setSelectMode(false);
});

// ── Medya araması (A3 / Adım 7b) ─────────────────────────────────────
// Arama üç alanda (tasarım §4.1): prompt, klasör adı, boyut. İçe aktarılan
// kayıtların prompt'u yok, onlar dosya adıyla bulunur.
// `q` parametreli: TEK yüklem, iki çağıran (Medya araması + Medya seçicisi).
// Seçici kendi eşleştirmesini yazsaydı arama iki yerde ayrışırdı — birinde
// klasör adı aranır, diğerinde aranmaz ve fark sessiz olurdu (plan B5).
function matchesSearch(rec, q = searchQuery) {
  const folder = folderById(rec.folder_id);
  const folderName = folder ? folder.name : "";
  const size = rec.size || "";
  const prompt = rec.prompt || rec.filename || "";
  return `${prompt} ${folderName} ${size}`.toLowerCase().includes(q);
}

// Tüm klasörlerin görselleri: `/api/history` klasörsüzleri, `?folder_id=` tek
// klasörü döndürüyor — "tüm klasörler" görünümü için hepsi ayrı ayrı çekilip
// birleştiriliyor. GET'ler paralel: importFiles'ın "sırayla" kuralı YAZAN
// uçlar için, okuma yarışı yok.
async function loadAllImages() {
  const requests = [fetch("/api/history"), ...folderCache.map(
    (f) => fetch(`/api/history?folder_id=${encodeURIComponent(f.id)}`))];
  const all = [];
  for (const res of await Promise.all(requests)) {
    if (!res.ok) continue;   // tek klasörün hatası aramanın kalanını düşürmez
    all.push(...((await res.json()).images || []));
  }
  return all;
}

// Yavaş yanıt yarışı: kullanıcı yazmaya devam ederse eski sorgunun sonucu
// yenisini ezmesin diye jeton karşılaştırılıyor (viewer'ın token kalıbı).
let searchToken = 0;

async function refreshSearch(token = searchToken) {
  const all = await loadAllImages();
  if (token !== searchToken || !searchQuery) return;
  historyCache = all.filter(matchesSearch);
  selected = new Set([...selected].filter((id) => historyCache.some((r) => r.id === id)));
  renderGallery();
  syncSelectUI();
}

$("media-search").addEventListener("input", async () => {
  searchQuery = $("media-search").value.trim().toLowerCase();
  const token = ++searchToken;
  syncFolderView();
  // Sorgu silinince bulunulan klasörün normal görünümüne dönülür.
  if (!searchQuery) { await loadHistory(); return; }
  await refreshSearch(token);
});

// ══════════════════════════════════════════════════════════════════════
// Medya seçici (Adım 12) — composer'ın (+) menüsünden açılan modal
//
// Sahibi bu dosya, sekizinci bir dosya DEĞİL (plan B1): `folderCache`,
// `folderById`, `folderPath`, `loadAllImages`, `matchesSearch` zaten burada.
// Asıl risk sekizinci dosyanın `tests/test_id_contract.py:36 JS_FILES`'a
// eklenmemesiydi — o zaman içindeki tüm `$()` bağları id mandalının DIŞINDA
// kalırdı.
//
// Bölüm banner'la sınırlı ve testler bu dilimi kesip iddia kuruyor: "seçici
// historyCache yazmıyor" iddiası tüm dosyaya bakarsa hep kırmızı kalır
// (galeri onu meşru olarak yazıyor).
// ══════════════════════════════════════════════════════════════════════

// Seçici KENDİ kopyasını tutar (B3). `historyCache`, `searchQuery`, `selected`
// ve `renderGallery()` buradan HİÇ yazılmaz: modal kapandığında Medya görünümü
// bıraktığı yerde durmalı, filtresi değişmiş bir liste bulunmamalı.
let pickerImages = [];
let pickerScope = "";
let pickerQuery = "";
let pickerSelectedId = null;
let pickerToken = 0;

// Sol gezinme (B4). "İçe aktarılanlar" bir BÖLME değil kesişen süzgeç:
// Klasörsüz + klasörler zaten Tümü'nü tüketiyor, bu satır onların İÇİNDEN
// geçiyor. Toplam bilerek tutmuyor — `crossing` sınıfı hairline ile bunu gözle
// söylüyor, yoksa sonraki okuyucu "toplam yanlış" diye düzeltmeye kalkar.
const PICKER_ICONS = {
  all: [["rect", { x: 3, y: 3, width: 7, height: 7, rx: 1.5 }],
        ["rect", { x: 14, y: 3, width: 7, height: 7, rx: 1.5 }],
        ["rect", { x: 3, y: 14, width: 7, height: 7, rx: 1.5 }],
        ["rect", { x: 14, y: 14, width: 7, height: 7, rx: 1.5 }]],
  loose: [["rect", { x: 3, y: 4, width: 18, height: 16, rx: 2 }],
          ["path", { d: "M3 15l4.5-4 3.5 3 3-2.5L21 17" }]],
  folder: [["path", { d: "M4 6.5A1.5 1.5 0 0 1 5.5 5H9l1.8 2H18.5A1.5 1.5 0 0 1 20 8.5V17a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17z" }]],
  imported: [["path", { d: "M12 16V4" }], ["path", { d: "M8 8l4-4 4 4" }],
             ["path", { d: "M4 16v3.5h16V16" }]],
};

// `folderPath` bir ETİKET DEĞİL, klasör NESNELERİNDEN oluşan kırıntı zinciri
// döndürüyor (bkz. tanımı: `path.unshift(node)`). Doğrudan `textContent`e
// verilirse "[object Object],[object Object]" yazıyor — canlı turda tam olarak
// bu görüldü. Ayraç kod tabanından alınıyor: galeri başlığı da " / " ile
// birleştiriyor (bu dosyada `path.map((f) => f.name).join(" / ")`).
const pickerFolderLabel = (id) => folderPath(id).map((f) => f.name).join(" / ");

function pickerScopes() {
  return [
    { key: "", label: "Tümü", icon: PICKER_ICONS.all, test: () => true },
    { key: "none", label: "Klasörsüz", icon: PICKER_ICONS.loose,
      test: (r) => !r.folder_id },
    ...folderCache.map((f) => ({
      key: `f:${f.id}`, label: pickerFolderLabel(f.id), icon: PICKER_ICONS.folder,
      test: (r) => r.folder_id === f.id,
    })),
    { key: "imported", label: "İçe aktarılanlar", icon: PICKER_ICONS.imported,
      test: (r) => !!r.imported, crossing: true },
  ];
}

const pickerScopeOf = (key) =>
  pickerScopes().find((s) => s.key === key) || pickerScopes()[0];

const pickerById = (id) => pickerImages.find((r) => r.id === id) || null;

function pickerVisible() {
  const scope = pickerScopeOf(pickerScope);
  return pickerImages.filter((r) => scope.test(r) && matchesSearch(r, pickerQuery));
}

// İkon SVG'si tek yerde kuruluyor: `innerHTML` bu dosyada YALNIZ boş dizeyle
// çağrılıyor (chat.js:12'nin yazdığı ev kuralı), o yüzden path'ler de
// createElementNS ile geliyor — prompt ve dosya adı kullanıcı verisi.
function pickerIcon(paths, size = 18) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of paths) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    svg.appendChild(node);
  }
  return svg;
}

function renderPickerNav() {
  const nav = $("picker-kinds");
  nav.innerHTML = "";
  for (const s of pickerScopes()) {
    const n = pickerImages.filter((r) => s.test(r) && matchesSearch(r, pickerQuery)).length;

    const label = document.createElement("span");
    label.textContent = s.label;
    const count = document.createElement("em");
    count.textContent = String(n);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = s.crossing ? "picker-nav-item crossing" : "picker-nav-item";
    btn.dataset.key = s.key;
    btn.title = s.label;                       // 208px'te uzun klasör yolu kırpılır
    btn.setAttribute("aria-current", String(s.key === pickerScope));
    btn.appendChild(pickerIcon(s.icon));
    btn.appendChild(label);
    btn.appendChild(count);
    nav.appendChild(btn);
  }
}

function renderPickerGrid() {
  const grid = $("picker-grid");
  grid.innerHTML = "";
  const list = pickerVisible();
  for (const rec of list) {
    const title = rec.prompt || rec.filename || rec.id;
    const folder = folderById(rec.folder_id);

    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = "";                              // başlık künyede, çift okunmasın
    img.loading = "lazy";

    const name = document.createElement("b");
    name.textContent = title.slice(0, 60);
    const cap = document.createElement("span");
    cap.className = "picker-cap";
    cap.appendChild(name);
    cap.appendChild(document.createTextNode(folder ? folder.name : "Klasörsüz"));

    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "picker-tile";
    tile.dataset.id = rec.id;
    tile.title = title;
    tile.setAttribute("aria-selected", String(rec.id === pickerSelectedId));
    tile.appendChild(img);
    if (rec.size) {
      const badge = document.createElement("span");
      badge.className = "card-badge";
      badge.textContent = rec.size;
      tile.appendChild(badge);
    }
    tile.appendChild(cap);
    grid.appendChild(tile);
  }
  $("picker-empty").hidden = list.length > 0;
  $("picker-empty-text").textContent = pickerQuery
    ? "Sonuç bulunamadı" : "Bu kapsamda görsel yok";
}

function renderPickerSide() {
  // Seçim `pickerSelectedId`'den okunuyor, DOM'dan SORULMUYOR: ızgara yeniden
  // çizildiğinde (arama, kapsam değişimi) `querySelector('[aria-selected]')`
  // sessizce null döner ve commit düğmeleri "hiçbir şey seçili" sanar.
  const rec = pickerById(pickerSelectedId);
  const img = $("picker-preview-img");
  img.src = rec ? `/output/${rec.filename}` : "";
  img.hidden = !rec;
  const folder = rec ? folderById(rec.folder_id) : null;
  const meta = $("picker-meta");
  meta.innerHTML = "";
  const rows = rec
    ? [["Klasör", folder ? pickerFolderLabel(folder.id) : "Klasörsüz"],
       ["Boyut", rec.size || "—"],
       ["Kaynak", rec.imported ? "İçe aktarıldı" : "Üretildi"]]
    : [];
  for (const [key, value] of rows) {
    const label = document.createElement("span");
    label.textContent = key;
    const val = document.createElement("b");
    val.textContent = String(value);
    const row = document.createElement("div");
    row.appendChild(label);
    row.appendChild(val);
    meta.appendChild(row);
  }

  const why = extraBlockReason(rec);
  $("picker-use-ref").disabled = !rec;
  $("picker-use-extra").disabled = !!why;
  // Sayaç gerekçeyi YENER: 3/3'te "En fazla 4 görsel gönderilebilir." demek,
  // az önce olan şeyi (üçüncü ek eklendi) söylemeden reddi tekrarlamak olur.
  // Paydası olan sayaç zaten kapalı düğmeyi açıklıyor.
  $("picker-note").textContent = extras.length
    ? `Eklendi · ${extras.length}/${MAX_EDIT_IMAGES - 1}` : why;
}

// Adı `renderPicker` DEĞİL: `palette.js:96` aynı adı çoktan kullanıyor (renk
// seçicinin render'ı) ve o dosya `index.html`'de folders.js'ten SONRA
// yükleniyor — klasik script'ler tek global alanı paylaştığı için sonraki
// tanım öncekini SESSİZCE eziyordu. Sonuç: `openPicker()` medya seçicisini
// değil renk paletini çiziyordu, seçici bomboş açılıyordu. Hata vermiyordu,
// o yüzden yalnız canlı turda görüldü. Çarpışmayı `test_id_contract.py`
// mandallıyor artık.
function renderMediaPicker() {
  renderPickerNav();
  renderPickerGrid();
  renderPickerSide();
}

async function openPicker() {
  // `.sheet` ve `.modal` aynı z-index 50'yi paylaşıyor: açık kalan bir
  // slide-over "Escape neyi kapatır" belirsizliği yaratır (B10).
  closeSheets();
  $("media-picker").hidden = false;
  $("picker-search").value = "";
  pickerQuery = "";
  pickerScope = "";
  renderMediaPicker();
  $("picker-search").focus();
  // "Tümü" `loadAllImages()` ile toplanıyor, satır içine kopyalanmıyor (B2):
  // `GET /api/history` klasör-DIŞLAYICI (klasörsüz VEYA tek klasör; "hepsi"
  // ucu yok) ve bu incelik ikinci kez keşfedilmek zorunda kalmamalı.
  const token = ++pickerToken;
  const all = await loadAllImages();
  if (token !== pickerToken || $("media-picker").hidden) return;
  pickerImages = all;
  if (!pickerById(pickerSelectedId)) pickerSelectedId = all.length ? all[0].id : null;
  renderMediaPicker();
}

// Kapanış SINIF değil ÖZNİTELİK çeviriyor: `.modal[hidden]` `display: none`
// oluyor ve içindeki kontroller sekme sırasından çıkıyor. Yalnız görünürlükle
// (opacity/pointer-events) kapatılan bir kapta 25 kontrol odaklanabilir
// kalıyordu — Faz 0 mock'unda ölçüldü.
function closePicker() {
  $("media-picker").hidden = true;
  pickerToken++;   // uçuşta olan loadAllImages yanıtı kapalı modalı boyamasın
}

$("media-pick-btn").addEventListener("click", openPicker);
$("picker-close").addEventListener("click", closePicker);
$("media-picker").querySelector("[data-picker-close]")
  .addEventListener("click", closePicker);

$("picker-search").addEventListener("input", () => {
  pickerQuery = $("picker-search").value.trim().toLowerCase();
  renderMediaPicker();
});

$("picker-kinds").addEventListener("click", (e) => {
  const btn = e.target.closest(".picker-nav-item");
  if (!btn) return;
  pickerScope = btn.dataset.key;
  renderMediaPicker();
});

$("picker-grid").addEventListener("click", (e) => {
  const tile = e.target.closest(".picker-tile");
  if (!tile) return;
  pickerSelectedId = tile.dataset.id;
  renderPickerGrid();
  renderPickerSide();
});

// Commit bilerek ASİMETRİK (B7).
// "Referans yap": önce kapat, sonra kaynağı kur. Sıra bağlayıcı —
// `setGallerySource` `$("prompt").focus()` çağırıyor ve açık bir
// `aria-modal="true"` diyaloğun ARKASINA odak verilirse ekran okuyucu
// kullanıcısı diyalogda kilitli kalır.
$("picker-use-ref").addEventListener("click", () => {
  const rec = pickerById(pickerSelectedId);
  if (!rec) return;
  closePicker();
  setGallerySource(rec);
});

// "Ek olarak ekle": seçici AÇIK kalır. Üç ek slotu var, her biri için menüden
// dönmek saçma olurdu. Gerekçe/sayaç #picker-note'ta; `addGalleryExtra` ADIYLA
// yeniden kullanılıyor ve gerekçeyi DÖNDÜRÜYOR (statusEl'e yazmıyor — o yüzey
// modalın arkasında).
$("picker-use-extra").addEventListener("click", () => {
  const rec = pickerById(pickerSelectedId);
  if (!rec) return;
  const why = addGalleryExtra(rec);
  if (why) { $("picker-note").textContent = why; return; }
  renderPickerSide();
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || $("media-picker").hidden) return;
  // #confirm-modal her zaman üstte (native confirm() yerine geçiyor):
  // açıkken Escape ONU kapatmalı, altındaki seçiciyi değil.
  if (!$("confirm-modal").hidden) return;
  e.stopImmediatePropagation();
  closePicker();
});

// ══════════════════════════════════════════════════════════════════════
// Medya seçici sonu
// ══════════════════════════════════════════════════════════════════════

// ── Izgara boyutu S/M/L (A4 / Adım 7b) ───────────────────────────────
// Ölçü CSS'te: düğme yalnızca `data-size` yazar, kutucuk genişliğini
// `.gallery[data-size=…]`nin --tile değeri belirler. grid-template-columns'u
// JS'ten yazmak duyarlılık kurallarını sessizce ezerdi.
$("size-seg").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-size]");
  if (!btn) return;
  for (const b of $("size-seg").querySelectorAll("button[data-size]")) {
    b.setAttribute("aria-pressed", String(b === btn));
  }
  $("gallery").dataset.size = btn.dataset.size;
});

async function loadHistory() {
  // Arama açıkken geçmişin tazelenmesi (silme, taşıma, içe aktarma sonrası)
  // arama sonuçlarını tazelemek demek — klasör görünümüne sessizce dönülmez.
  if (searchQuery) { await refreshSearch(); return; }
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

    // Karta tıklamak BÜYÜTECİ açar (tasarım §6 / media-browser.html). Küçük
    // resmin eski gizli "düzenleme kısayolu" kaldırıldı: aynı tıklama iki iş
    // yapamaz ve referans atama artık .acts şeridinde adı yazan bir düğme.
    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = prompt.slice(0, 60);
    img.title = selectMode
      ? "Seçmek için tıkla · seçili görselleri taşımak için klasöre sürükle"
      : prompt
        ? `${prompt}\n\nBüyütmek için tıkla · taşımak için klasöre sürükle`
        : "Büyütmek için tıkla · taşımak için klasöre sürükle";
    // img'in yerel sürüklemesi kapatılır ki sürükleme kartın kendisinden başlasın
    // (aksi halde dataTransfer'a görsel URL'i düşer ve sürükleme hayaleti bozulur)
    img.draggable = false;

    // download'a dosya adı AÇIKÇA veriliyor: boş bırakılırsa macOS kayıt
    // panelinin ad alanını WebKit'in URL'den türetmesine kalıyoruz.
    const downloadLink = document.createElement("a");
    downloadLink.setAttribute("href", `/output/${rec.filename}`);
    downloadLink.setAttribute("download", rec.filename);
    downloadLink.textContent = "İndir";
    // Kayıt paneli olan tarayıcıda konumu KULLANICI seçsin (core.js). Panel
    // yoksa hiç araya girilmiyor: <a download> zaten pakette doğru davranıyor.
    downloadLink.addEventListener("click", (e) => {
      if (!SUPPORTS_SAVE_PICKER) return;
      e.preventDefault();
      downloadImage(`/output/${rec.filename}`, rec.filename);
    });

    // Bu görseli ana referans yap. Eskiden küçük resmin GİZLİ tıklamasıydı;
    // artık adı yazan bir düğme (sözleşmenin .acts şeridi).
    //
    // Önce Stüdyo'ya dönülüyor: composer Medya'dayken `hidden` (core.js'in
    // `$("composer").hidden = !studio` satırı), yani `setGallerySource`'un
    // yazdığı #ref-chip ve #status gizli kapların içinde kalıyordu — referans
    // gerçekten atanıyor ama kullanıcı hiçbir geri bildirim görmüyordu.
    const refBtn = document.createElement("button");
    refBtn.textContent = "Referans";
    refBtn.title = "Bu görseli ana referans yap";
    refBtn.addEventListener("click", () => {
      showSection("studio");
      setGallerySource(rec);
    });

    // Şerit İKİ pill: İndir · Referans — media-browser.html'in yazdığı
    // kompozisyonun aynısı. Eski "+Ek" düğmesi ÖLÇÜMLE düştü (A9): üçüncü
    // pill 184.8px istiyor, karonun şeride verdiği genişlik S'de 97px, M'de
    // 138px. Sonuç S'de üç satır (karonun %89'u) ve M'de iki satır (%43) —
    // şerit görselin kendisini yutuyordu. İki pill'le: S %58, M %21, L %13.
    //
    // Yetenek kaybı bilerek ve ölçülü: o düğme bugüne kadar zaten GÖRÜNMEZ
    // çalışıyordu (geri bildirimi Medya'da `hidden` composer'ın içindeydi),
    // yani tamamlanmamış bir yol geri çekildi. Galeri görselini ek referans
    // yapmanın yeri Adım 12'nin Medya seçicisi: orada "Ek olarak ekle" kendi
    // gerekçeli kapalı hâliyle duruyor (plan B6/B7).
    const acts = document.createElement("div");
    acts.className = "acts";
    acts.appendChild(downloadLink);
    acts.appendChild(refBtn);

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
    // Kartın TEK etkinleştirme gövdesi: seçim modu kazanır, yoksa büyüteç.
    // Tıklama ve klavye aynı gövdeyi çağırıyor; iki kopya yazmak, birinde
    // seçim modu dalını unutmakla biten klasik ayrışma olurdu.
    //
    // `rect` veriliyor: büyüteç tıklanan karonun BULUNDUĞU yerden büyüsün
    // (viewer.js'in `openerRect`'i zaten bunun için var).
    const activateCard = () => {
      if (selectMode) { toggleSelected(rec.id); return; }
      window.openViewer(`/output/${rec.filename}`, prompt || rec.filename,
                        card.getBoundingClientRect());
    };
    // Kart içi eylemler kartın işini tetiklemez: şerit, silme, seçim kutusu.
    // Tek muhafızda toplanıyor — dağınık muhafızlar birinin unutulmasıyla
    // bitiyordu (.card-check bu listede yeni; kendi stopPropagation'ı duruyor).
    card.addEventListener("click", (e) => {
      if (e.target.closest(".acts, .card-del, .card-check")) return;
      activateCard();
    });
    // Kart bir <div>, yani klavyeye kendiliğinden açık değil: düğme gibi
    // duyurulup Enter/Space'e bağlanıyor.
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label",
      `${prompt ? prompt.slice(0, 60) : rec.filename} — ${selectMode ? "seç" : "büyüt"}`);
    card.addEventListener("keydown", (e) => {
      // Kart İÇİNDEKİ düğmeye basılan Enter kartı da tetiklemesin: olay
      // oradan köpürür ve tek tuş iki eylem çalıştırır. (chat.js:908-910'un
      // taşımadığı muhafız — o gizli çift-tetikleme buraya kopyalanmıyor.)
      if (e.target !== card) return;
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();   // Space sayfayı kaydırır
      activateCard();
    });
    card.appendChild(img);
    if (selectMode) card.appendChild(makeCheckbox(rec));
    // İçe aktarılan görsel üretilmiş gibi görünmesin: prompt'u yoktur, dosya
    // adı taşır. Seçim modunda sol üst köşe card-check'in, o yüzden gizlenir.
    if (rec.imported && !selectMode) {
      const badge = document.createElement("span");
      badge.className = "card-badge";
      badge.textContent = "içe aktarıldı";
      card.appendChild(badge);
    }
    // Arama sonucu kartı hangi klasörden geldiğini söyler (§4.1 künye kuralı):
    // sonuçlar tüm klasörlerden geliyor, adsız iki varyant ayırt edilemez.
    // Sol ALT köşede — sol üst card-check/card-badge'in, sağ alt .acts'ın.
    if (searchQuery) {
      const where = document.createElement("span");
      where.className = "card-badge card-where";
      const folder = folderById(rec.folder_id);
      where.textContent = folder ? folder.name : "Klasörsüz";
      card.appendChild(where);
    }
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
// Görseller alanı = BULUNULAN klasör. Şerit yalnız BAŞKA klasörleri hedef
// yapıyor (içinde olduğun klasörün kartı yok) ve hiç klasör yokken şeritte
// hiçbir kart yok — bu bölge iki boşluğu da kapatıyor.
const galleryWrapEl = document.querySelector(".gallery-wrap");

function hasFiles(e) {
  return !!e.dataTransfer && [...e.dataTransfer.types].includes("Files");
}

// BİLİNÇLİ ASİMETRİ: merkez alana dosya bırakmak "referans olarak yükle"
// (kaydetmez), galeri alanına bırakmak "kütüphaneye aktar" (kaydeder).
// İki bölge kardeş (.stage ile .gallery-wrap iç içe değil), o yüzden çakışmaz.

function clearDropHighlights() {
  stageEl.classList.remove("dragover");
  galleryWrapEl.classList.remove("dropzone");
  document.querySelectorAll(".drop-hover")
    .forEach((el) => el.classList.remove("drop-hover"));
}

// Tarayıcı, sayfaya bırakılan hiçbir dosyayı/bağlantıyı asla açmasın (koşulsuz).
["dragover", "drop"].forEach((evt) =>
  window.addEventListener(evt, (e) => e.preventDefault())
);

// Vurguların temizliği de pencere seviyesinde: `dragleave` çocuk öğeye
// geçildiğinde tetiklenmediği için sürükleme iptal edilir ya da pencere
// dışında bırakılırsa vurgu takılı kalıyordu.
//
// YAKALAMA fazı (üçüncü argüman `true`) ŞART ve ÖLÇÜLDÜ: klasör kartının
// `drop` dinleyicisi çift aktarmayı önlemek için `stopPropagation` çağırıyor,
// bu da pencereye BALONLANAN temizliği yutuyor — kartın üstüne bırakınca
// galeri alanının kesikli çerçevesi ekranda takılı kalıyordu. Yakalama fazı
// hedeften ÖNCE koştuğu için stopPropagation onu engelleyemez.
["drop", "dragend"].forEach((evt) =>
  window.addEventListener(evt, clearDropHighlights, true)
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

["dragenter", "dragover"].forEach((evt) =>
  galleryWrapEl.addEventListener(evt, (e) => {
    if (!hasFiles(e)) return;          // iç taşıma sürüklemesi bu bölgeyi ilgilendirmez
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    galleryWrapEl.classList.add("dropzone");
  })
);

galleryWrapEl.addEventListener("dragleave", (e) => {
  if (e.target === galleryWrapEl) galleryWrapEl.classList.remove("dropzone");
});

galleryWrapEl.addEventListener("drop", (e) => {
  galleryWrapEl.classList.remove("dropzone");
  if (!hasFiles(e)) return;
  e.preventDefault();
  importFiles(e.dataTransfer.files, currentFolder ? currentFolder.id : null,
              currentFolder ? currentFolder.name : "Klasörsüz");
});

function selectInGroup(groupSel, btn) {
  document.querySelectorAll(groupSel + " button").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}

