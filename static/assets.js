// GPT-Image Studio — logo/motto/banner kütüphanesi ve bindirme modalı.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

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
  const ok = await confirmDialog("Varlığı sil",
    "Bu logo/motto/banner kütüphaneden kalıcı olarak silinecek.");
  if (!ok) return;
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
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("assets-modal").hidden) closeAssetsModal();
});

// ── Bindirme modalı: logo VEYA banner + canlı önizleme ──────────────
let logoId = null;
let rawPreviewSrc = "";                                 // ham (bindirmesiz) görsel URL'i
let overlayMode = "logo";                               // "logo" | "motto" | "banner"
// logo: "builtin"|id · motto: id|null · banner: id|null
let selectedAsset = { logo: "builtin", motto: null, banner: null };
// Kaydırma, boyut/gölgenin AKSİNE mod başına hatırlanır: motto genelde logodan
// farklı bir noktaya konur, ortak tutulsa tür değiştirmek diğerinin ince
// ayarını sessizce devralırdı (kullanıcı kararı). Banner burada yok — onun
// yerleşimi ayrı (edge/align/margin), #logo-only kontrolleri ona görünmüyor.
let overlayOffset = { logo: { x: 0, y: 0 }, motto: { x: 0, y: 0 } };
let logoPreviewTimer = null;
let logoPreviewToken = 0;

const OFFSET_ZERO = () => ({ logo: { x: 0, y: 0 }, motto: { x: 0, y: 0 } });

// İşaretli gösterim. Eksi U+2212 (−), ASCII tire değil: viewer.js'in
// uzaklaştırma düğmesi de onu kullanıyor, tipografik tutarlılık.
function formatOffset(value) {
  const n = parseInt(value, 10);
  if (n === 0) return "0";
  return (n > 0 ? "+%" : "−%") + Math.abs(n);
}

function readOffsetSliders() {
  return { x: parseInt($("logo-offset-x").value, 10),
           y: parseInt($("logo-offset-y").value, 10) };
}

function writeOffsetSliders({ x, y }) {
  $("logo-offset-x").value = x;
  $("logo-offset-y").value = y;
}

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
  // Slider'lar aktif modun değerini taşır ⇒ tek kaynak onlar; overlayOffset
  // yalnızca mod değişiminde geri yükleme için tutuluyor.
  const offset = readOffsetSliders();
  return {
    id: logoId,
    asset_kind: isMotto ? "mottos" : "logos",
    asset_id: isMotto ? selectedAsset.motto : (selectedAsset.logo === "builtin" ? null : selectedAsset.logo),
    position: pos ? pos.dataset.pos : "bottom-right",
    color: col ? col.dataset.color : "auto",
    size: +(sizePct / 100).toFixed(3),
    shadow_alpha: Math.round((shadowPct / 100) * 255),
    shadow_blur: blur,
    offset_x: +(offset.x / 100).toFixed(3),
    offset_y: +(offset.y / 100).toFixed(3),
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
  $("logo-offset-x-val").textContent = formatOffset($("logo-offset-x").value);
  $("logo-offset-y-val").textContent = formatOffset($("logo-offset-y").value);
}

function syncBannerLabels() {
  const scale = parseInt($("banner-scale").value, 10);
  $("banner-scale-val").textContent = scale + "%";
  $("banner-margin-val").textContent = $("banner-margin").value + "%";
  // %100'de yatayda boş alan yok → hizalama matematiksel olarak etkisiz.
  // Ölü kontrole basılmasın diye kilitlenir ve nedeni yazılır.
  const fullWidth = scale >= 100;
  $("banner-align").querySelectorAll("button").forEach((b) => { b.disabled = fullWidth; });
  $("banner-align-note").hidden = !fullWidth;
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
  // Kaydırmayı o TÜRÜN değerine geri yükle. Bu satır düşerse logo ve motto
  // kaydırmaları sessizce birleşir — gözle fark edilmesi zor, o yüzden
  // tests/test_index.py'de bir tripwire var.
  if (overlayOffset[mode]) {
    writeOffsetSliders(overlayOffset[mode]);
    syncLogoLabels();
  }
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
  overlayOffset = OFFSET_ZERO();
  writeOffsetSliders(overlayOffset.logo);
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
// Kaydırma slider'ları yukarıdaki listeye KATILMIYOR: ayrıca overlayOffset'e
// yazmaları gerek. Mod guard'ı savunma amaçlı — banner modunda #logo-only
// gizli olduğu için olay gelmemeli, ama gelirse banner'ın olmayan kaydırma
// durumunu yaratmasın.
["logo-offset-x", "logo-offset-y"].forEach((id) =>
  $(id).addEventListener("input", () => {
    if (overlayOffset[overlayMode]) overlayOffset[overlayMode] = readOffsetSliders();
    syncLogoLabels();
    refreshLogoPreview();
  })
);
// Bipolar bir slider'da fareyle tam 0'a dönmek zor (ok tuşları 1 birim
// adımlıyor, o yol açık ama tek tıkla dönüş de olmalı).
$("logo-offset-reset").addEventListener("click", () => {
  writeOffsetSliders({ x: 0, y: 0 });
  if (overlayOffset[overlayMode]) overlayOffset[overlayMode] = { x: 0, y: 0 };
  syncLogoLabels();
  refreshLogoPreview();
});
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
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("logo-modal").hidden) closeLogoModal();
});

