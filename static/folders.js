// Lumeo — klasörler (iç içe) ve galeri çoklu seçimi.
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
let searchQuery = "";
let mediaSortOrder = "date"; // "date" (Yeni-Eski) veya "name" (A-Z)

function updateMediaRailCount() {
  const el = $("media-rail-count");
  if (!el) return;
  const imgCount = historyCache ? historyCache.length : 0;
  const foldCount = folderCache ? folderCache.length : 0;
  if (currentFolder) {
    el.textContent = `${imgCount} görsel`;
  } else {
    el.textContent = `${foldCount} klasör · ${imgCount} görsel`;
  }
}

function toggleMediaSort() {
  mediaSortOrder = mediaSortOrder === "date" ? "name" : "date";
  if ($("media-sort-label")) {
    $("media-sort-label").textContent = mediaSortOrder === "date" ? "Tarih" : "İsim";
  }
  renderFolders();
  renderGallery();
}

if ($("media-sort-btn")) {
  $("media-sort-btn").addEventListener("click", toggleMediaSort);
}

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

// Ayraç TEK sabitte: künye, kırıntı ve taşıma listesi aynı klasörü aynı
// yazımla anlatmak zorunda. İkisi ayrışırsa kullanıcı aynı klasörü iki yüzeyde
// iki farklı ad sanır.
const KLASOR_AYRACI = " / ";

/** Zinciri {ust, yaprak} olarak verir — kök/bilinmeyen id'de ikisi de "".
 *
 *  "Klasörsüz" YEDEĞİ BURAYA KONMUYOR: `pickerFolderLabel` bilinmeyen id'de
 *  boş dize döndürüyor ve `renderPickerSide` (folders.js) kendi yedeğine
 *  güveniyor. Yedek buraya taşınsaydı o sözleşme sessizce değişirdi.
 */
function folderPathParts(id) {
  const zincir = folderPath(id).map((f) => f.name);
  return {
    ust: zincir.slice(0, -1).join(KLASOR_AYRACI),
    yaprak: zincir.length ? zincir[zincir.length - 1] : "",
  };
}

/** Klasör künyesi: zincirin TAMAMI, ama kırpma yükü ÜST zincire biniyor.
 *
 *  Künye bugüne kadar yalnız EN YAKIN klasörü yazıyordu, yani iç içe
 *  klasörlerde "hangi A altındaki B" sorusu cevapsızdı. Aynı ders taşıma
 *  listesinde zaten yazılı (bu dosyada, `sec.appendChild(o)` döngüsü): orada
 *  tam yol yazılıyor çünkü "Ağustos" iki ayrı klasörde de aynı olabiliyor.
 *
 *  Tek `<span>` + `text-overflow: ellipsis` DENENMEDİ ve sebebi ÖLÇÜLÜ
 *  (Chromium 1194, 360×780): kart 359px, ızgara 335px, `minmax(96px, 1fr)`
 *  üç sütun veriyor, karo 104px ve `.picker-cap`'in yatay dolgusundan sonra
 *  metne ~84px kalıyor — 12px'lik yazıda ≈12 karakter. "Kampanyalar / Bayram"
 *  sondan kırpılınca ekranda "Kampanyala…" kalırdı: kullanıcının aradığı
 *  YAPRAK klasör tam da kaybolan yarı, yani bugünkü "yalnız Bayram" hâlinden
 *  DAHA KÖTÜ. İki kutu bu yüzden: üst zincir daralıyor, yaprak daralmıyor.
 *
 *  Kırpma JS'te DEĞİL CSS'te: karakter bütçesi hem erişilebilirlik ağacını da
 *  kırpardı (ekran okuyucu zinciri tam duyuyor, gören kullanıcı kısaltılmışını
 *  görüyor) hem de Android WebView'ın sistem yazı ölçeğinde piksel eşiği
 *  cihazdan cihaza kayardı — `.chat-hint`in dersi (Tur B).
 */
/** Aynı parçalardan düz metin etiket ("A / B") — ipucu ve `<option>` için. */
function klasorZinciriEtiketi(parcalar) {
  const { ust, yaprak } = parcalar;
  return ust ? ust + KLASOR_AYRACI + yaprak : yaprak;
}

function klasorZinciriDugumu(folderId, sinif, parcalar = folderPathParts(folderId)) {
  const { ust, yaprak } = parcalar;
  const kap = document.createElement("span");
  kap.className = sinif;
  if (ust) {
    const ustEl = document.createElement("span");
    ustEl.className = "zincir-ust";
    ustEl.textContent = ust;
    kap.appendChild(ustEl);
  }
  const yaprakEl = document.createElement("span");
  yaprakEl.className = "zincir-yaprak";
  // Ayraç YAPRAKLA taşınıyor, üst zincirin sonunda DEĞİL: esnek kutuda satır
  // başındaki boşluk kırpılıyor ve künye "Kampanyal…/ Bayram" diye okunurdu.
  yaprakEl.textContent = yaprak
    ? (ust ? KLASOR_AYRACI + yaprak : yaprak)
    : "Klasörsüz";
  kap.appendChild(yaprakEl);
  return kap;
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
// DOKUNMATİKTE İPUÇLARI BAŞKA: HTML5 sürükle-bırak dokunmatik ekranda HİÇ
// çalışmıyor (bu dosyadaki üç yol da: klasör kartına bırakma 242-268, kart
// sürükleme 1164-1174, dosya bırakma alanları 1282-1320). Telefonda "sürükleyip
// bırak" yazan bir ipucu, çalışmayan bir yolu tarif etmek olurdu — yani
// yardımcı değil, yanıltıcı. Taşımanın dokunmatikteki yolu seçim modundaki
// "Taşı…" düğmesi, içe aktarmanınki ise "Yükle" düğmesi.
//
// O "Yükle" düğmesi bu cümle YAZILDIĞINDA YOKTU: ipucu bir dönem var olmayan
// bir kontrolü tarif etti ve telefondan içe aktarmanın gerçekten hiçbir yolu
// kalmadı. Düğme artık `#media-import-btn` olarak şeritte; cümle ile kontrol
// birlikte yaşıyor (aynı kusurun kaydı: assets.js `assetEmptyText`).
const FOLDER_HINT_DEFAULT = IS_TOUCH
  ? 'Görselleri taşımak için "Seç" ile işaretleyip "Taşı…" düğmesini kullan.'
  : "Bir görseli klasör kartına sürükleyip bırakarak taşıyabilirsin.";
const FOLDER_HINT_IMPORT = IS_TOUCH
  ? 'Cihazındaki bir görseli "Yükle" düğmesiyle içe aktarabilirsin.'
  : 'Bilgisayarındaki bir görseli "Yükle" düğmesiyle, klasör kartına ya da bu alana bırakarak içe aktarabilirsin.';

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
  $("folder-back").hidden = !inFolder;
  // Silme yalnızca klasörün İÇİNDE (sağ üstte); seçim modunda şerit görsellere ayrılır
  $("folder-delete").hidden = !inFolder || selectMode;
  if ($("folder-rename")) $("folder-rename").hidden = !inFolder || selectMode;
  if ($("folder-download")) $("folder-download").hidden = !inFolder || selectMode;
  $("folder-new").hidden = selectMode;
  // "Yükle" de `#folder-new` ile aynı davranışta: seçim modunda şerit görsel
  // eylemlerine kalıyor. Aramadayken DE çekiliyor — hedef bulunulan klasör ve
  // arama sırasında "bulunulan klasör" diye bir şey yok (sonuçlar tüm
  // klasörlerden geliyor), yani düğme nereye aktardığını söyleyemezdi.
  $("media-import-btn").hidden = selectMode || searching;

  // kırıntı: "A / B / C" — cache henüz gelmediyse en azından klasörün adı
  $("gallery-title").textContent = inFolder
    ? (klasorZinciriEtiketi(folderPathParts(currentFolder.id)) || currentFolder.name)
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
  const images = dropped.filter(isAcceptedUpload);
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

function createFolderCell(f) {
  const coverRec = historyCache ? historyCache.find((r) => r.folder_id === f.id) : null;
  let icon;
  if (coverRec && coverRec.filename) {
    icon = document.createElement("img");
    icon.className = "folder-thumb";
    icon.src = `/output/${coverRec.filename}`;
    icon.alt = "";
  } else {
    icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
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
  }

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

  const cell = document.createElement("div");
  cell.className = "folder-cell";
  cell.appendChild(open);
  makeDropTarget(cell, f.id, f.name);
  return cell;
}

function renderFolders() {
  const grid = $("folder-grid");
  grid.innerHTML = "";
  const searching = searchQuery.length > 0;

  if (searching) {
    const q = searchQuery.toLowerCase();
    const matching = folderCache.filter((f) => f.name.toLowerCase().includes(q));
    if (!matching.length) {
      grid.hidden = true;
      updateMediaRailCount();
      return;
    }
    grid.hidden = false;
    matching.sort((a, b) => {
      if (mediaSortOrder === "name") return a.name.localeCompare(b.name, "tr");
      return (b.created_at || "").localeCompare(a.created_at || "");
    });
    for (const f of matching) {
      grid.appendChild(createFolderCell(f));
    }
    updateMediaRailCount();
    return;
  }

  grid.hidden = false;

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
  children.sort((a, b) => {
    if (mediaSortOrder === "name") return a.name.localeCompare(b.name, "tr");
    return (b.created_at || "").localeCompare(a.created_at || "");
  });

  if (!children.length) {
    const empty = document.createElement("p");
    empty.className = "folder-empty";
    empty.textContent = currentFolder
      ? "Bu klasörde alt klasör yok · + Yeni klasör ile oluştur"
      : "Henüz klasör yok · + Yeni klasör ile oluştur";
    grid.appendChild(empty);
    updateMediaRailCount();
    return;
  }
  for (const f of children) {
    grid.appendChild(createFolderCell(f));
  }
  updateMediaRailCount();
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

async function renameCurrentFolder() {
  if (!currentFolder) return;
  const target = currentFolder;
  const newName = await promptDialog(`"${target.name}" klasörünü yeniden adlandır`,
    "Yeni klasör adını girin.", { defaultValue: target.name, okLabel: "Kaydet" });
  if (!newName || !newName.trim() || newName.trim() === target.name) return;
  try {
    const res = await fetch(`/api/folders/${target.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim() }),
    });
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    const { folder } = await res.json();
    currentFolder.name = folder.name;
    const found = folderById(target.id);
    if (found) found.name = folder.name;
    statusEl.textContent = "Klasör yeniden adlandırıldı.";
    syncFolderView();
  } catch (e) {
    statusEl.textContent = `Yeniden adlandırılamadı: ${e.message}`;
  }
}

async function downloadCurrentFolder() {
  if (!currentFolder) return;
  const target = currentFolder;
  statusEl.textContent = `"${target.name}" klasörü ZIP olarak indiriliyor...`;
  const url = `/api/folders/${target.id}/download`;
  downloadViaAnchor(url, `${target.name}.zip`);
}

$("folder-back").addEventListener("click", goUp);
$("folder-delete").addEventListener("click", deleteCurrentFolder);
if ($("folder-rename")) $("folder-rename").addEventListener("click", renameCurrentFolder);
if ($("folder-download")) $("folder-download").addEventListener("click", downloadCurrentFolder);
$("folder-new").addEventListener("click", createFolder);

// İçe aktarmanın dokunmatik yolu. `importFiles` YENİDEN YAZILMIYOR: MIME kapısı
// (`isAcceptedUpload`), 20 dosya sınırı, SIRAYLA gönderim ve
// `loadFolders()+loadHistory()` tazelemesi olduğu gibi devralınıyor — bırakma
// yoluyla tek fark dosyaların nereden geldiği.
$("media-import-btn").addEventListener("click", () => $("media-import-input").click());
$("media-import-input").addEventListener("change", (e) => {
  const dosyalar = [...(e.target.files || [])];
  // Değer HEMEN sıfırlanıyor: aynı dosya ikinci kez seçildiğinde `change`
  // hiç ateşlenmez ve düğme sessizce ölü görünür.
  e.target.value = "";
  if (!dosyalar.length) return;
  // Hedef BULUNULAN yer: klasörün içindeysek o klasör, değilse kök. Bırakma
  // yolundaki `.gallery-wrap` kuralının aynısı.
  importFiles(dosyalar, currentFolder ? currentFolder.id : null,
              currentFolder ? currentFolder.name : "Klasörsüz");
});


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
      ? (IS_TOUCH
        ? 'Seçili görselleri taşımak için "Taşı…" düğmesine dokun.'
        : "Seçili görselleri taşımak için birini klasör kartına sürükle.")
      : (IS_TOUCH
        ? 'Görselleri seç, sonra "Taşı…" düğmesine dokun.'
        : "Görselleri seç, sonra taşımak için birini klasör kartına sürükle.");
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
  $("select-move").disabled = selected.size === 0;
}

// ── Taşıma penceresi ────────────────────────────────────────────────
//
// Sürükle-bırakın DOKUNMATİK KARŞILIĞI. Dokunmatikte sürükleme hiç çalışmıyor
// (bkz. FOLDER_HINT_DEFAULT) ve taşıma bu uygulamada ikincil bir özellik
// değil: klasörler tüm medya düzeninin belkemiği.
//
// Düğme her cihazda görünüyor, yalnız dokunmatikte DEĞİL: klavye kullanan biri
// için de sürükle-bırak erişilebilir bir yol değildi — yani bu, mobil için
// eklenip masaüstünde de eksiği kapatan bir yol.
//
// Hedef seçici NATIVE `<select>`: Android'de sistemin kendi seçicisi olarak
// açılıyor (uzun listede kaydırma, arama, geri tuşu — hepsi bedava) ve
// masaüstünde de tanıdık. Kendi listemizi çizmek, `.picker-card`ın telefonda
// yaşadığı yerleşim sorunlarının aynısını yeni bir yüzeyde tekrarlardı.
function openMoveDialog() {
  if (!selected.size) return;
  const modal = $("move-modal");
  const sec = $("move-target");
  const sayi = selected.size;

  $("move-desc").textContent = sayi > 1
    ? `${sayi} görsel seçili hedefe taşınacak.`
    : "Seçili görsel hedefe taşınacak.";

  sec.replaceChildren();
  const kok = document.createElement("option");
  kok.value = "";
  kok.textContent = "Klasörsüz (kök)";
  sec.appendChild(kok);
  // Tam yol yazılıyor: iç içe klasörlerde yalnız ad ("Ağustos") iki farklı
  // klasörde de aynı olabiliyor ve kullanıcı hangisini seçtiğini bilemezdi.
  for (const f of folderCache) {
    const o = document.createElement("option");
    o.value = f.id;
    o.textContent = pickerFolderLabel(f.id) || f.name;
    sec.appendChild(o);
  }
  // Bulunulan klasör hedef olarak anlamsız (görseller zaten orada).
  if (currentFolder) sec.value = "";

  modal.hidden = false;
  sec.focus();
}

function closeMoveDialog() {
  $("move-modal").hidden = true;
}

async function confirmMove() {
  const sec = $("move-target");
  const folderId = sec.value || null;
  const ad = sec.options[sec.selectedIndex]?.textContent || "kök";
  // `moveImages` seçim modunda TÜM seçimi taşıyor (ids'i kendisi kuruyor);
  // buradan tek bir id vermek yeterli ve taşıma mantığı tek yerde kalıyor.
  const ilk = [...selected][0];
  closeMoveDialog();
  if (!ilk) return;
  await moveImages(ilk, folderId, ad);
  setSelectMode(false);
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
    if (currentImage && ids.includes(currentImage.id)) setCurrentImage(null);
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
$("select-move").addEventListener("click", openMoveDialog);
$("move-cancel").addEventListener("click", closeMoveDialog);
$("move-ok").addEventListener("click", confirmMove);
$("move-modal").querySelector("[data-move-close]").addEventListener("click", closeMoveDialog);
// Escape muhafızı: taşıma penceresi AÇIKKEN Escape onu kapatmalı, arkadaki
// seçim modunu değil. Aynı desen `media-picker` için de kurulu (aşağıda) —
// muhafızsız tek Escape iki katmanı birden kapatırdı.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || $("move-modal").hidden) return;
  e.stopImmediatePropagation();
  closeMoveDialog();
}, true);
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
// Dönüş `{ images, failed }`: düşen uç SAYISI da geliyor. `fetch` HTTP hatasında
// **reddetmez** — `res.ok === false` ile çözülür — yani aşağıdaki `continue`
// 500'leri sessizce yutuyor ve çağıranın `try/catch`ine hiçbir şey ulaşmıyor.
// Sayaç olmadan "liste boş çünkü gerçekten boş" ile "liste boş çünkü uçlar
// düştü" ayırt edilemiyor (PR #23 incelemesi). Sayı DÖNÜŞTE taşınıyor, modül
// değişkeninde değil: iki çağıran (Medya araması + seçici) çakışabilir.
async function loadAllImages() {
  const requests = [fetch("/api/history"), ...folderCache.map(
    (f) => fetch(`/api/history?folder_id=${encodeURIComponent(f.id)}`))];
  const images = [];
  let failed = 0;
  for (const res of await Promise.all(requests)) {
    if (!res.ok) { failed++; continue; }   // tek klasörün hatası kalanını düşürmez
    images.push(...((await res.json()).images || []));
  }
  return { images, failed };
}

// Yavaş yanıt yarışı: kullanıcı yazmaya devam ederse eski sorgunun sonucu
// yenisini ezmesin diye jeton karşılaştırılıyor (viewer'ın token kalıbı).
let searchToken = 0;

async function refreshSearch(token = searchToken) {
  const { images: all } = await loadAllImages();
  if (token !== searchToken || !searchQuery) return;
  historyCache = all.filter((r) => matchesSearch(r));
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
let pickerAcan = null;      // seçiciyi açan düğüm — kapanışta odak oraya döner
let pickerToken = 0;
// Boş ızgaranın ÜÇ ayrı nedeni var — yükleniyor, alınamadı, gerçekten boş — ve
// üçü tek cümleyle anlatılırsa ikisi yalan olur (PR #23 incelemesi, H2).
let pickerState = "loading";   // "loading" · "error" · "ready"

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
// bu görüldü. Zincir artık `folderPathParts` üzerinden geliyor ve ayraç tek
// sabitte (`KLASOR_AYRACI`): künye ile bu etiket ayrışamıyor.
const pickerFolderLabel = (id) => klasorZinciriEtiketi(folderPathParts(id));

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

const pickerScopeOf = (key, scopes = pickerScopes()) =>
  scopes.find((s) => s.key === key) || scopes[0];

const pickerById = (id) => pickerImages.find((r) => r.id === id) || null;

const pickerFilter = (scope, query = pickerQuery) =>
  pickerImages.filter((r) => scope.test(r) && matchesSearch(r, query));

function pickerVisible(scopes = pickerScopes()) {
  const scope = pickerScopeOf(pickerScope, scopes);
  return pickerFilter(scope);
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

function renderPickerNav(scopes = pickerScopes()) {
  const nav = $("picker-kinds");
  // Şerit yeniden KURULMAK zorunda — ızgaranın çözümü (yalnız özniteliği
  // çevir) buraya uymuyor: sayaçlar hem kapsamla hem HER TUŞ VURUŞUYLA
  // değişiyor (`pickerFilter(s).length`). O yüzden odak ADIYLA iade ediliyor;
  // desen `chat.js`teki `closeMenus`ün aynısı. Ölçüldü: iade olmadan bir
  // kapsam düğmesine klavyeyle basan kullanıcının odağı `<body>`ye düşüyor,
  // yani süzgeci daralttığı anda diyaloğun başına atılıyordu.
  //
  // Odak ŞERİTTE miydi sorusu şart ve İKİ iş yapıyor: fareyle süzenin odağını
  // şeride zorla taşımıyor VE arama kutusuna yazan kullanıcının odağını her
  // tuşta çalmıyor (her tuş bu işlevi yeniden çağırıyor).
  //
  // Anahtar TUTULUYOR, düğüm değil: düğümün kendisi birazdan silinecek.
  // `core.js`teki `isConnected` muhafızı burada YOK ve olmamalı — orada düğüm
  // yıkımdan ÖNCE tutuluyor, burada yıkımdan SONRA bulunuyor.
  const odakli = document.activeElement;
  const seritteydi = odakli && odakli.closest && odakli.closest(".picker-nav-item");
  const odakAnahtari = seritteydi ? seritteydi.dataset.key : null;
  nav.innerHTML = "";
  let geriVerilecek = null;
  for (const s of scopes) {
    const n = pickerFilter(s).length;

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
    if (s.key === odakAnahtari) geriVerilecek = btn;
    nav.appendChild(btn);
  }
  // Kapsam listeden düşmüşse (klasör silindi) iade EDİLMİYOR: rastgele bir
  // düğmeye atlamak kullanıcıyı yerinden etmenin başka bir biçimi olurdu.
  if (geriVerilecek) geriVerilecek.focus();
}

function renderPickerGrid(scopes = pickerScopes()) {
  const grid = $("picker-grid");
  // Izgaranın yeniden KURULDUĞU yollar hâlâ var (arama, kapsam değişimi ve
  // `openPicker`'ın bekleyen `loadAllImages` yanıtı) — seçim artık buraya
  // uğramıyor ama o yollarda odak yine `<body>`ye düşerdi. `openPicker`
  // yarışı en sinsisi: bayat liste hemen boyanıyor, kullanıcı bir karoya
  // geçiyor, yanıt gelince ızgara altından siliniyor.
  // İade `renderPickerNav`'daki mekanizmanın aynısı, tek fark anahtarın adı.
  const odakli = document.activeElement;
  const odakId = odakli && odakli.closest && odakli.closest(".picker-tile")
    ? odakli.closest(".picker-tile").dataset.id : null;
  grid.innerHTML = "";
  const list = pickerVisible(scopes);
  for (const rec of list) {
    const title = rec.prompt || rec.filename || rec.id;

    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = "";                              // başlık künyede, çift okunmasın
    img.loading = "lazy";

    const name = document.createElement("b");
    name.textContent = title.slice(0, 60);
    const cap = document.createElement("span");
    cap.className = "picker-cap";
    cap.appendChild(name);
    // Zincir karo başına BİR kez yürünüyor: hem künye düğümü hem ipucu aynı
    // parçalardan besleniyor. İki ayrı çağrı `folderPath`i (klasör başına
    // doğrusal `find` + döngü muhafızı) her karo için iki kez koşturuyordu ve
    // ızgara her tuş vuruşunda yeniden kuruluyor.
    const parcalar = folderPathParts(rec.folder_id);
    cap.appendChild(klasorZinciriDugumu(rec.folder_id, "picker-cap-folder", parcalar));

    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "picker-tile";
    tile.dataset.id = rec.id;
    // İpucu zinciri de taşıyor: künye dar kutuda üst zinciri kırpıyor, tam yol
    // fareyle bekleyen kullanıcıya burada açılıyor (yan bölmedeki "Klasör"
    // satırının aynısı).
    // Klasörsüz karoda da satır YAZILIYOR: künye "Klasörsüz" diyor ve yan
    // bölmenin "Klasör" satırı da öyle — ipucu ikisiyle aynı şeyi söylemeli,
    // yoksa yalnız o karolarda sessiz kalırdı.
    tile.title = `${title}\n${klasorZinciriEtiketi(parcalar) || "Klasörsüz"}`;
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
  // Seçim işaretinin TEK yazıcısı: kurulum da güncelleme de aynı süpürmeden
  // geçiyor. Karolar eklendikten SONRA çağrılmak zorunda — önce koşarsa
  // `querySelectorAll` boş küme görür ve hiçbir karo işaretlenmez (sessiz,
  // hatasız bir kırılma).
  syncPickerPressed();
  if (odakId) {
    const geri = pickerKaro(odakId);
    // Karo listeden düşmüşse (arama daralttı) iade EDİLMİYOR: rastgele bir
    // karoya atlamak kullanıcıyı yerinden etmenin başka bir biçimi olurdu.
    if (geri) geri.focus();
  }
  $("picker-empty").hidden = list.length > 0;
  $("picker-empty-text").textContent =
    pickerState === "loading" ? "Görseller yükleniyor…"
    : pickerState === "error" ? "Görseller alınamadı."
    : pickerQuery ? "Sonuç bulunamadı"
    : "Bu kapsamda görsel yok";
}

/** Izgaradaki bir karoyu id'siyle bulur. Klasör id'leri çıplak onaltılık
 *  (`uuid4().hex[:12]`, storage.py), yani seçiciye gömmek güvenli. */
const pickerKaro = (id) =>
  $("picker-grid").querySelector(`.picker-tile[data-id="${id}"]`);

/** Seçim işaretini VAR OLAN karolara yazar — ızgarayı yeniden KURMADAN.
 *
 *  Tıklama eskiden `renderPickerGrid()` çağırıyordu ve o `grid.innerHTML = ""`
 *  ile bütün karoları siliyordu. ÖLÇÜLDÜ (Chromium 1194, üç genişlikte de):
 *  bir karoya klavyeyle Enter'a basıldıktan sonra `document.activeElement`
 *  `<body>`. Yani Tur C'de kazanılan `aria-pressed="true"`yi tam da onu
 *  duyacak kullanıcı HİÇ duymuyordu; üstelik gezinmeye diyaloğun başından
 *  devam etmek zorunda kalıyordu. İkinci belirti gözle görülür: görünen her
 *  `<img>` yeniden kuruluyor, `loading="lazy"` durumu sıfırlanıyor.
 *
 *  Yeniden kurmanın taşıdığı başka bir bilgi YOK: seçim değişince değişen tek
 *  şey bu öznitelik (ve ona bağlı iki CSS kuralı). Boş-durum metni `list`e,
 *  gezinme sayaçları `pickerFilter`a bağlı — ikisi de seçimden bağımsız.
 *
 *  DELTA yazımı (eski seçiliyi bul, kapat) BİLEREK yazılmadı: onu yazmanın
 *  yolu `querySelector('[aria-pressed="true"]')`, yani kaynağı BOYA yapmak.
 *  Seçim `pickerSelectedId` demek, işaret onun sonucu (B3) — ve o kural bu
 *  dosyada bir mandalla korunuyor.
 *
 *  ÖZNİTELİĞİN KENDİSİ (Tur C'nin kararı, kurulumdan buraya taşındı):
 *  `aria-selected` DEĞİL, çünkü `.picker-tile` düz bir `<button>` ve
 *  kapsayıcısı düz bir `<div>` — `aria-selected` yalnız
 *  `option`/`tab`/`row`/`treeitem`/`gridcell` rollerinde geçerli, düğmede
 *  tarayıcı onu erişilebilirlik ağacına HİÇ koymuyordu. `role="option"`
 *  seçeneği reddedildi: gezinen tabindex + ok tuşu modeli ister ve depoda
 *  öyle bir desen hiç yok; `aria-pressed` altı yerde zaten kurulu.
 */
function syncPickerPressed() {
  for (const tile of $("picker-grid").querySelectorAll(".picker-tile")) {
    tile.setAttribute("aria-pressed", String(tile.dataset.id === pickerSelectedId));
  }
}

function renderPickerSide() {
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
  // GEREKÇE kazanır: kapalı bir düğme sebepsiz kalmaz. Eski hâl
  // `extras.length ? sayaç : gerekçe` idi — "3/3'te sayaç gerekçeyi yener"
  // savunması doğruydu ama yalnız KAPASİTE gerekçesi için, oysa koşul
  // `extras.length`e bağlıydı: ilk ek eklenir eklenmez "zaten ana referans" ve
  // "zaten ek referans listesinde" cümleleri de susuyordu. Kullanıcı 1/3
  // okuyup (yer var) ölü düğmeye basıyordu (PR #23 incelemesi, H1).
  //
  // Buradaki sayaç DURAN bir okuma ("şu an şu kadar ek var"), eylem onayı değil
  // — o yüzden fiil taşımıyor. Onay ("Eklendi") yalnız ekleme ANINDA, çağrı
  // yerinde yazılıyor. İki cümle AYRI olmak zorunda: aynı dize kullanılsaydı
  // hiç eklenmemiş bir karoya geçince de "Eklendi" yazardı ve kullanıcı o karoyu
  // eklemiş sanırdı (`why` boş olan HER karo bu dala düşüyor).
  $("picker-note").textContent = why
    || (extras.length ? `Ek referans · ${extras.length}/${MAX_EDIT_IMAGES - 1}` : "");
}

// Adı `renderPicker` DEĞİL: `palette.js:96` aynı adı çoktan kullanıyor (renk
// seçicinin render'ı) ve o dosya `index.html`'de folders.js'ten SONRA
// yükleniyor — klasik script'ler tek global alanı paylaştığı için sonraki
// tanım öncekini SESSİZCE eziyordu. Sonuç: `openPicker()` medya seçicisini
// değil renk paletini çiziyordu, seçici bomboş açılıyordu. Hata vermiyordu,
// o yüzden yalnız canlı turda görüldü. Çarpışmayı `test_id_contract.py`
// mandallıyor artık.
function renderMediaPicker() {
  const scopes = pickerScopes();
  const visible = pickerVisible(scopes);
  if (!visible.some((r) => r.id === pickerSelectedId)) {
    pickerSelectedId = visible.length ? visible[0].id : null;
  }
  renderPickerNav(scopes);
  renderPickerGrid(scopes);
  renderPickerSide();
}

async function openPicker() {
  // Kapanışta odağın döneceği düğüm: `core.js`in `dialogPrevFocus` deseni.
  // Onsuz Escape (ya da ×) odaklı karoyu `display: none` yapıyor ve odak
  // `<body>`ye düşüyordu — bu turun düzelttiği kusurun DÖRDÜNCÜ kopyası,
  // üstelik en sık yürünen yolu. "Referans yap" dalı zaten bilinçli olarak
  // odağı `#prompt`a taşıyor; eksik olan yalnız KAPATMA yoluydu.
  pickerAcan = document.activeElement;
  // `.sheet` ve `.modal` aynı z-index 50'yi paylaşıyor: açık kalan bir
  // slide-over "Escape neyi kapatır" belirsizliği yaratır (B10).
  closeSheets();
  $("media-picker").hidden = false;
  $("picker-search").value = "";
  pickerQuery = "";
  pickerScope = "";
  pickerState = "loading";
  renderMediaPicker();
  $("picker-search").focus();
  // "Tümü" `loadAllImages()` ile toplanıyor, satır içine kopyalanmıyor (B2):
  // `GET /api/history` klasör-DIŞLAYICI (klasörsüz VEYA tek klasör; "hepsi"
  // ucu yok) ve bu incelik ikinci kez keşfedilmek zorunda kalmamalı.
  const token = ++pickerToken;
  // Arıza İKİ ayrı yoldan geliyor ve ikisi de karşılanmak zorunda:
  //   • ağ katmanı (sunucu kapalı, bağlantı koptu) → `fetch` REDDEDER → catch
  //   • sunucu tarafı (500, 404) → `fetch` REDDETMEZ, `res.ok` false olur ve
  //     `loadAllImages` onu yutar → catch HİÇ çalışmaz, liste boş döner
  // İkincisi ilk düzeltmede atlanmıştı: kullanıcı 500 alınca yine "görselin yok"
  // okuyordu. Ayrım `failed` sayacıyla yapılıyor (PR #23 incelemesi).
  let res;
  try {
    res = await loadAllImages();
  } catch {
    if (token !== pickerToken || $("media-picker").hidden) return;
    pickerState = "error";
    pickerImages = [];   // bayat listeyi hata cümlesinin altında bırakma
    renderMediaPicker();
    return;
  }
  if (token !== pickerToken || $("media-picker").hidden) return;
  // Boş liste TEK BAŞINA "görselin yok" demek değil. Kısmi arızada (bir klasör
  // düştü, gerisi geldi) ızgara doluyor ve akış bozulmuyor — sözleşme yalnız
  // "boşluk gerçek mi" sorusunu koruyor.
  pickerState = res.images.length === 0 && res.failed > 0 ? "error" : "ready";
  pickerImages = res.images;
  if (!pickerById(pickerSelectedId)) {
    pickerSelectedId = res.images.length ? res.images[0].id : null;
  }
  renderMediaPicker();
}

// Kapanış SINIF değil ÖZNİTELİK çeviriyor: `.modal[hidden]` `display: none`
// oluyor ve içindeki kontroller sekme sırasından çıkıyor. Yalnız görünürlükle
// (opacity/pointer-events) kapatılan bir kapta 25 kontrol odaklanabilir
// kalıyordu — Faz 0 mock'unda ölçüldü.
/** Kapanışta odağın döneceği düğüm.
 *
 *  `isConnected` YETMİYOR ve bu ölçüldü: seçiciyi açan düğme (+) menüsünün
 *  İÇİNDE (`#media-pick-btn`, `#plus-menu`) ve o menü seçici açılırken
 *  kapanıyor. Düğüm DOM'da duruyor, yani `isConnected` true — ama `[hidden]`
 *  bir kabın içinde olduğu için `.focus()` SESSİZCE hiçbir şey yapmıyor ve
 *  odak `<body>`de kalıyordu. İlk yazım tam olarak bu yüzden işe yaramadı;
 *  Escape ölçümü hâlâ `BODY` diyordu.
 *
 *  Görünmez bir açan varsa menüyü AÇAN düğmeye dönülüyor — `chat.js`teki
 *  `closeMenus`ün "tetiğe dön" kuralının aynısı, ve kullanıcının seçiciye
 *  girerken bastığı ilk görünür kontrol o.
 */
function pickerOdakHedefi() {
  return pickerAcan && pickerAcan.isConnected && !pickerAcan.closest("[hidden]")
    ? pickerAcan : $("plus-btn");
}

function closePicker(odakIadeEt = true) {
  $("media-picker").hidden = true;
  pickerToken++;   // uçuşta olan loadAllImages yanıtı kapalı modalı boyamasın
  if (odakIadeEt) pickerOdakHedefi().focus();
  pickerAcan = null;
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
  syncPickerPressed();
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
  // Odak iadesi KAPALI: `setGallerySource` odağı `#prompt`a taşıyor ve bu
  // yolun kararı zaten o (yukarıdaki B7 notu). İade açık kalsaydı odak önce
  // (+) düğmesine dönüp hemen composer'a sıçrardı — ekran okuyucuya iki
  // ayrı yer duyurulurdu.
  closePicker(false);
  setGallerySource(rec);
});

// "Ek olarak ekle": seçici AÇIK kalır. Üç ek slotu var, her biri için menüden
// dönmek saçma olurdu. Gerekçe/sayaç #picker-note'ta; `addGalleryExtra` ADIYLA
// yeniden kullanılıyor ve gerekçeyi DÖNDÜRÜYOR (statusEl'e yazmıyor — o yüzey
// modalın arkasında).
$("picker-use-extra").addEventListener("click", () => {
  const rec = pickerById(pickerSelectedId);
  if (!rec) return;
  // `activeElement` HER ŞEYDEN ÖNCE okunuyor: `addGalleryExtra` kendi
  // yüzeyini yeniden çiziyor (`renderSource`) ve odağı taşıyan bir kabı
  // yıkarsa bu okuma sonradan sessizce `false` olurdu — düzeltme hatasızca
  // buharlaşırdı.
  const odakDugmedeydi = document.activeElement === $("picker-use-extra");
  const why = addGalleryExtra(rec);
  if (why) { $("picker-note").textContent = why; return; }
  // Ekleme BAŞARILI olduğu anda `extraBlockReason(rec)` doluyor ("Bu görsel
  // zaten ek referans listesinde.") ve `renderPickerSide` bu düğmeyi
  // `disabled` yapıyor. Odaklı bir düğmeyi disable etmek odağı `<body>`ye
  // düşürüyor — ÖLÇÜLDÜ: Enter'dan sonra `document.activeElement` `<body>`,
  // düğme `disabled`. Yani B7'nin gerekçesi ("üç ek slotu var, her biri için
  // menüden dönmek saçma olurdu") klavye kullanıcısında TAM TERSİNE dönüyordu:
  // ikinci ek için diyaloğun başından Tab'lamak gerekiyordu. `#picker-note`
  // `role="status"` olduğu için ONAY duyuluyor, kaybolan şey YER.
  renderPickerSide();
  // Onay ekleme ANINDA yazılıyor. `renderPickerSide` gerekçeyi öne aldığı için
  // (H1) az önce eklenen karo hemen "zaten ek referans listesinde" derdi ve
  // kullanıcı eyleminin işlediğini hiç göremezdi. Fiil ("Eklendi") YALNIZ burada
  // geçiyor; karo değişince not duran okumaya ("Ek referans · N/3") ya da
  // gerekçeye döner.
  $("picker-note").textContent = `Eklendi · ${extras.length}/${MAX_EDIT_IMAGES - 1}`;
  // Odak SEÇİLİ KAROYA dönüyor, "Referans yap"a DEĞİL: o düğme seçiciyi
  // KAPATIYOR, yani ikinci kez Space'e basan kullanıcı ek eklemek yerine turu
  // bitirirdi. Karo, oradan bir sonraki karoya geçmenin de doğal başlangıcı.
  if (odakDugmedeydi) {
    const karo = pickerKaro(pickerSelectedId);
    if (karo) karo.focus();
  }
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

  const sorted = [...historyCache].sort((a, b) => {
    if (mediaSortOrder === "name") {
      const nameA = a.prompt || a.filename || a.id;
      const nameB = b.prompt || b.filename || b.id;
      return nameA.localeCompare(nameB, "tr");
    }
    return (b.created_at || b.id || "").localeCompare(a.created_at || a.id || "");
  });

  const emptyEl = $("media-empty-state");
  const emptyText = $("media-empty-text");
  if (emptyEl) {
    if (sorted.length === 0) {
      emptyEl.hidden = false;
      if (emptyText) {
        emptyText.textContent = searchQuery
          ? "Aramanızla eşleşen görsel bulunamadı."
          : (currentFolder ? "Bu klasörde henüz görsel yok." : "Henüz görsel üretilmedi.");
      }
    } else {
      emptyEl.hidden = true;
    }
  }

  for (const rec of sorted) {
    const prompt = rec.prompt || "";

    // Karta tıklamak BÜYÜTECİ açar (tasarım §6 / media-browser.html). Küçük
    // resmin eski gizli "düzenleme kısayolu" kaldırıldı: aynı tıklama iki iş
    // yapamaz ve referans atama artık .acts şeridinde adı yazan bir düğme.
    const img = document.createElement("img");
    img.src = `/output/${rec.filename}`;
    img.alt = prompt.slice(0, 60);
    // Taşıma cümlesi girdi türüne göre değişiyor: dokunmatikte sürükleme yok
    // (bkz. FOLDER_HINT_DEFAULT). `title` zaten dokunmatikte hiç GÖRÜNMÜYOR,
    // ama ekran okuyucular okuyor — yanlış yönerge orada da yanlış.
    const tasimaIpucu = IS_TOUCH
      ? '"Taşı…" ile klasöre taşı'
      : "taşımak için klasöre sürükle";
    img.title = selectMode
      ? `Seçmek için tıkla · seçili görselleri ${tasimaIpucu}`
      : prompt
        ? `${prompt}\n\nBüyütmek için tıkla · ${tasimaIpucu}`
        : `Büyütmek için tıkla · ${tasimaIpucu}`;
    // img'in yerel sürüklemesi kapatılır ki sürükleme kartın kendisinden başlasın
    // (aksi halde dataTransfer'a görsel URL'i düşer ve sürükleme hayaleti bozulur)
    img.draggable = false;

    // download'a dosya adı AÇIKÇA veriliyor: boş bırakılırsa macOS kayıt
    // panelinin ad alanını WebKit'in URL'den türetmesine kalıyoruz.
    const downloadLink = document.createElement("a");
    // href ÇİZİM adresi değil İNDİRME adresi (core.js `indirmeAdresi`): sağ tık →
    // "Bağlantıyı kaydet" ve dinleyicinin hiç çalışmadığı durum da doğru dosyayı
    // vermeli.
    downloadLink.setAttribute("href", indirmeAdresi(`/output/${rec.filename}`));
    downloadLink.setAttribute("download", rec.filename);
    downloadLink.textContent = "İndir";
    // HER ZAMAN araya giriliyor, `SUPPORTS_SAVE_PICKER` kontrolü YOK: eskiden
    // panel olmayan ortamda çıpanın kendi gezinmesine bırakılıyordu ve Android
    // WebView'de bu, indirmenin hiç olmaması demekti (app.py `output_download`).
    // `downloadImage` panel yokken kendisi `downloadViaAnchor`'a düşüyor
    // (core.js) — yani pakette mekanizma AYNI, sadece karar tek yerde.
    downloadLink.addEventListener("click", (e) => {
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
    // Zincir erişilebilir addan ÖNCE hesaplanıyor. İlk yazımda `let kartYolu`
    // rozet bloğunda, yani BU SATIRIN ALTINDA duruyordu: `let`in ölü bölgesi
    // yüzünden `renderGallery` daha ilk kartta `ReferenceError` atıyor ve
    // galeri hiç çizilmiyordu. Kaynak deseni arayan mandallar bunu göremezdi —
    // gerçek tarayıcıda koşan `test_playwright_studio.py` yakaladı.
    const kartParcalari = searchQuery ? folderPathParts(rec.folder_id) : null;
    const kartYolu = kartParcalari
      ? (klasorZinciriEtiketi(kartParcalari) || "Klasörsüz") : "";
    card.setAttribute("aria-label",
      `${prompt ? prompt.slice(0, 60) : rec.filename}`
      + (kartYolu ? ` — ${kartYolu}` : "")
      + ` — ${selectMode ? "seç" : "büyüt"}`);
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
      // Rozetin kendi gerekçesi (yukarıda) "adsız iki varyant ayırt edilemez"
      // diyor — ama yalnız EN YAKIN klasörü yazdığı sürece iç içe iki ayrı
      // "Bayram" klasörü hâlâ birbirinin aynısı görünüyordu, yani rozet tam da
      // engellemek için konduğu belirsizliği üretiyordu. Arama tüm klasörleri
      // tarayan TEK yüzey olduğu için zincir en çok burada gerekiyor.
      card.appendChild(
        klasorZinciriDugumu(rec.folder_id, "card-badge card-where", kartParcalari));
      // Zincir kartın ERİŞİLEBİLİR ADINA da giriyor. Kırpmayı CSS'e vermenin
      // gerekçesi "ekran okuyucu zinciri tam duyar" idi ve BU YÜZEYDE o
      // doğru DEĞİLDİ: kart açık bir `aria-label` taşıyor (aşağıda) ve açık
      // bir etiket, içindeki metnin erişilebilir ada katılmasını engelliyor —
      // yani rozet hiç kimseye okunmuyordu. Arama tüm klasörleri tarayan tek
      // yüzey, yani ayırt edici bilgi tam da burada gerekiyor.
    }
    card.appendChild(delBtn);
    card.appendChild(acts);

    g.appendChild(card);
  }
}

// Görsel ekle butonu + gizli dosya girişi

$("upload-btn").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", () => {
  const files = $("file-input").files;
  if (files.length) setUploadSource(files[0]);
});
$("ref-clear").addEventListener("click", clearSource);

// KAPI SEÇİCİDEN ÖNCE sorulur. Eskiden dosya seçici KOŞULSUZ açılıyordu ve
// engel ancak dosya SEÇİLDİKTEN sonra `addExtraUpload` içinde sorulduğu için
// kullanıcının seçtiği görsel sessizce çöpe gidiyordu: ana referans yokken
// "Ek görsel" hiçbir şey yapmıyor gibi görünüyordu ("ek görsel eklenmiyor").
// `canAddExtra` gerekçeyi #status'a yazıyor — tek kaynak `extraBlockReason`.
$("extra-add-btn").addEventListener("click", () => {
  if (!canAddExtra()) return;
  $("extra-file-input").click();
});
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
  if (stageEl) stageEl.classList.remove("dragover");
  if (galleryWrapEl) galleryWrapEl.classList.remove("dropzone");
  document.querySelectorAll(".drop-hover")
    .forEach((el) => el.classList.remove("drop-hover"));
}

// Tarayıcı, sayfaya bırakılan hiçbir dosyayı/bağlantıyı asla açmasın (koşulsuz).
["dragover", "drop"].forEach((evt) =>
  window.addEventListener(evt, (e) => e.preventDefault())
);

// Vurguların temizliği de pencere seviyesinde
["drop", "dragend"].forEach((evt) =>
  window.addEventListener(evt, clearDropHighlights, true)
);

if (stageEl) {
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
}

if (galleryWrapEl) {
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
}

function selectInGroup(groupSel, btn) {
  document.querySelectorAll(groupSel + " button").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}

