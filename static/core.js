// GPT-Image Studio — üretim akışı: prompt, referans görseller, ilerleme, onay penceresi.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

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
    // Alanlar TEK TEK sayılmaz: JSON dalı `...pal` ile hepsini gönderirken
    // burada elle saymak `palette_id`'yi düşürmüştü — kayıtlı palet
    // düzenlemede dondurulmuş adlarını kaybediyor, sunucu (seed, mode)'dan
    // çevrimdışı yeniden hesaplıyordu. Anahtarları dolaşmak iki dalı eşitler
    // ve ileride eklenecek alanlar da kendiliğinden gider.
    for (const [key, value] of Object.entries(pal)) fd.append(key, value);
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
    } else if (images[0] && images[0].palette && images[0].palette.applied === false) {
      // Ek, prompt karakter sınırına sığmadığı için düşürüldü. Kayıtta palet
      // görünür ama prompt'a girmedi; söylenmezse kullanıcı renksiz sonucu
      // açıklayamaz. Eski kayıtlarda alan yok → `=== false` bilinçli.
      statusEl.textContent =
        "Palet prompt'a sığmadı (4000 karakter sınırı): görsel renk " +
        "yönlendirmesi olmadan üretildi. Prompt'u kısaltıp tekrar dene.";
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

