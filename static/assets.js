// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
// Kromis — logo/motto/banner kütüphanesi ve bindirme modalı.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

// ── Logo/banner kütüphanesi (prompt altı panel) ─────────────────────
let assetCache = { all: [], logos: [], banners: [], mottos: [] };
let assetPanelKind = "all";
// Değerler ETİKET değil ANAHTAR (palette.js'teki HARMONY_KEYS'in gerekçesi):
// çözüm okundukları yerde `t()` ile yapılıyor, tabloda değil.
const ASSET_EMPTY_KEYS = {
  all: "library.empty_all",
  logos: "library.empty_logos",
  mottos: "library.empty_mottos",
  banners: "library.empty_banners",
};

// ── Yükleme HEDEFİ ──────────────────────────────────────────────────
//
// Sekme şeridi bir FİLTRE, hedef DEĞİL. Bu ayrım kaybolduğunda ("Tümü"
// seçiliyken hedef `uploads` oluyordu) yüklenen logo hiçbir yerde
// kullanılamıyordu: `renderOverlayPicker` yalnız logos/mottos/banners okuyor ve
// sunucu da yalnız o türleri kabul ediyor (`models.OVERLAY_ASSET_KINDS`,
// banner'ın kendi ucu). Kullanıcının gördüğü tam olarak şuydu: "kütüphaneye
// logo yüklenmiyor" — dosya gidiyor, "Eklendi." yazıyor, logo ortada yok.
//
// İKİ MANDAL birlikte tutuyor: hedef ARTIK ölü bir türe düşemiyor (aşağıdaki
// tablo) ve düğmenin ETİKETİ hedefi söylüyor, yani bir daha görünmez bir
// varsayılana dönüşemez. Bekçisi tests/test_index.py.
const UPLOAD_TARGET = {
  all: "logos",       // "Tümü" bir hedef değil; en sık kullanılan türe düşer
  logos: "logos",
  mottos: "mottos",
  banners: "banners",
};
const UPLOAD_LABEL_KEYS = {
  logos: "library.upload_logo", mottos: "library.upload_motto",
  banners: "library.upload_banner",
};
const UPLOAD_DONE_KEYS = {
  logos: "library.added_logo", mottos: "library.added_motto",
  banners: "library.added_banner",
};
// Tür ADI ayrı bir tablo ve bu bir tekrar DEĞİL: düğme etiketinden ilk kelimeyi
// kesip tür adı olarak kullanmak ("Logo yükle".split(" ")[0]) Türkçe'de kazara
// çalışıyordu, İngilizce'de "Upload" verirdi. Dil bilgisi sırasına dayanan bir
// çıkarım, çeviriyle birlikte sessizce yanlışa döner.
const ASSET_KIND_KEYS = {
  logos: "library.kind_logo_one", mottos: "library.kind_motto_one",
  banners: "library.kind_banner_one",
};

function uploadTargetKind() {
  return UPLOAD_TARGET[assetPanelKind] || "logos";
}

/** Boş durum cümlesi — düğmenin GERÇEK adını söyleyerek.
 *
 * Sabit "+ Yükle ile ekle" metni, düğme hedefiyle adlandırıldığı an ("+ Logo
 * yükle") var olmayan bir kontrolü tarif etmeye başlıyordu. Aynı kusurun kaydı
 * settings.js'te de var (`AYARLAR_EKI`: tek düğme için iki ad); ikisi de tek
 * kaynaktan türetilerek kapanıyor.
 */
function assetEmptyText(kind) {
  const baslik = t(ASSET_EMPTY_KEYS[kind] || "library.empty_all");
  return t("library.empty_hint",
           { baslik, dugme: t(UPLOAD_LABEL_KEYS[uploadTargetKind()]) });
}

function syncUploadLabel() {
  const kind = uploadTargetKind();
  $("asset-upload-label").textContent = t(UPLOAD_LABEL_KEYS[kind]);
  $("asset-upload-btn").title =
    t("library.upload_btn_title", { tur: t(ASSET_KIND_KEYS[kind]) });
}

const OVERLAY_EMPTY_KEYS = {
  // `logo` girdisi, yerleşik logo kaldırıldığında eklendi: o seçenek
  // listeyi hiç boş bırakmadığı için logo modunun boş hâli daha önce YOKTU.
  logo: "overlay.need_logo",
  motto: "overlay.need_motto",
  banner: "overlay.need_banner",
};

// Kütüphane DOLU ama seçim yapılmamış hâli (OVERLAY_EMPTY_KEYS'ten farklı: orada
// yüklenecek bir şey yok, burada seçilecek). `logo` girdisi de üç modun üçünün
// de seçim gerektirmesiyle birlikte eklendi — bkz. overlayNeedsAsset.
const OVERLAY_PICK_KEYS = {
  logo: "overlay.pick_logo",
  motto: "overlay.pick_motto",
  banner: "overlay.pick_banner",
};

function assetStatus(msg) { $("asset-status").textContent = msg || ""; }

async function loadAssets(kind) {
  try {
    const res = await fetch(`/api/assets/${kind}`);
    if (!res.ok) throw new Error(t("err.http", { durum: res.status }));
    assetCache[kind] = (await res.json()).items || [];
  } catch {
    assetCache[kind] = [];
    assetStatus(t("library.load_failed"));
  }
  if (kind === assetPanelKind) renderAssetPanel();
  if (!$("logo-modal").hidden) renderOverlayPicker(); // modal açıksa seçiciyi tazele
}

function renderAssetPanel() {
  const grid = $("asset-grid");
  grid.innerHTML = "";
  const items = assetCache[assetPanelKind] || [];
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "asset-empty";
    empty.textContent = assetEmptyText(assetPanelKind);
    grid.appendChild(empty);
    return;
  }
  for (const item of items) {
    const itemKind = item.kind || assetPanelKind;
    const img = document.createElement("img");
    img.src = `/assets/${itemKind}/${item.filename}`;
    img.alt = item.name;
    img.title = item.name;

    const del = document.createElement("button");
    del.className = "asset-del";
    del.textContent = "×";
    del.title = t("common.delete");
    del.setAttribute("aria-label", `${item.name} sil`);
    del.addEventListener("click", () => deleteAssetItem(itemKind, item.id));

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
  if (!isAcceptedUpload(file)) {
    assetStatus(t("library.bad_format"));
    return;
  }
  assetStatus(t("library.uploading"));
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", file.name.replace(/\.[^.]+$/, ""));
  try {
    const res = await fetch(`/api/assets/${kind}`, { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : t("err.http", { durum: res.status }));
    }
    // Hangi türe gittiğini SÖYLÜYOR: "Eklendi." tek başına, varlığın
    // kullanılamaz bir türe düştüğü hâlde de aynı cümleyi yazıyordu.
    assetStatus(t(UPLOAD_DONE_KEYS[kind] || "library.added"));
    await Promise.all([loadAssets(kind), loadAssets("all")]);
  } catch (e) {
    assetStatus(e.message);
  }
}

async function deleteAssetItem(kind, id) {
  const ok = await confirmDialog(t("library.delete_title"),
    t("library.delete_body"));
  if (!ok) return;
  try {
    const res = await fetch(`/api/assets/${kind}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(t("err.http", { durum: res.status }));
    // modalda seçili öğe silindiyse seçimi güvenli varsayılana düşür
    if (kind === "logos" && selectedAsset.logo === id) selectedAsset.logo = null;
    if (kind === "mottos" && selectedAsset.motto === id) selectedAsset.motto = null;
    if (kind === "banners" && selectedAsset.banner === id) selectedAsset.banner = null;
    assetStatus(t("library.deleted"));
    await Promise.all([loadAssets(kind), loadAssets("all")]);
    if (!$("logo-modal").hidden) refreshLogoPreview();
  } catch {
    assetStatus(t("library.delete_failed"));
  }
}

$("asset-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-akind]");
  if (!btn) return;
  selectInGroup("#asset-tabs", btn);
  assetPanelKind = btn.dataset.akind;
  assetStatus("");
  syncUploadLabel();   // sekme hedefi de değiştirir; etiket bayat kalmasın
  renderAssetPanel();
});
$("asset-upload-btn").addEventListener("click", () => $("asset-file-input").click());
$("asset-file-input").addEventListener("change", async () => {
  const files = [...$("asset-file-input").files];
  $("asset-file-input").value = "";
  const targetKind = uploadTargetKind();
  for (const file of files) await uploadAsset(targetKind, file); // sırayla: manifest yazımı atomik
});

// ── Kütüphane görünümü (logo/motto/banner yükle-sil) ─────────────────
// A1 (Adım 7b): Kütüphane modaldan GÖRÜNÜME taşındı — ray öğesi bölüm
// değiştiriyor (core.js). Buradaki dinleyiciler görünüme girişte panelin
// bayat durumunu tazeliyor; aynı düğmede ikinci dinleyici plus-menü kalıbı.
function openLibraryView() {
  assetStatus("");
  syncUploadLabel();
  renderAssetPanel();
}

$("rail-library").addEventListener("click", openLibraryView);
// Üretim ayarları panelindeki "Kütüphane" kısayolu da aynı görünüme gider;
// id ve bağ duruyor (152 id sözleşmesi), yalnız hedefi değişti.
$("library-btn").addEventListener("click", () => {
  closeSheets();
  openLibraryView();
  showSection("library");
});

// ── Bindirme modalı: logo VEYA banner + canlı önizleme ──────────────
let logoId = null;
let rawPreviewSrc = "";                                 // ham (bindirmesiz) görsel URL'i
let overlayMode = "logo";                               // "logo" | "motto" | "banner"
// logo/motto/banner: id|null — üçü de kullanıcı kütüphanesinden gelir.
// Logonun eskiden "builtin" adlı bir dördüncü hâli vardı (pakete gömülü yerleşik
// logo çifti); uygulama marka-nötr olduğundan kaldırıldı.
let selectedAsset = { logo: null, motto: null, banner: null };
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

// Logo ve motto aynı (konumlanabilir, 9-grid) yerleşimi paylaşır; tek fark
// varlığın hangi kütüphaneden geldiği.
function readLogoOpts() {
  const active = (sel) => document.querySelector(sel + " button.active");
  const pos = active("#logo-grid");
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
    asset_id: isMotto ? selectedAsset.motto : selectedAsset.logo,
    position: pos ? pos.dataset.pos : "bottom-right",
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

function renderOverlayPicker() {
  const wrap = $("overlay-picker");
  wrap.innerHTML = "";
  const options = [];
  if (overlayMode === "logo") {
    for (const it of assetCache.logos) options.push({ id: it.id, name: it.name, src: `/assets/logos/${it.filename}` });
  } else if (overlayMode === "motto") {
    for (const it of assetCache.mottos) options.push({ id: it.id, name: it.name, src: `/assets/mottos/${it.filename}` });
  } else {
    for (const it of assetCache.banners) options.push({ id: it.id, name: it.name, src: `/assets/banners/${it.filename}` });
  }
  if (!options.length) {
    const hint = document.createElement("p");
    hint.className = "overlay-empty";
    hint.textContent = t(OVERLAY_EMPTY_KEYS[overlayMode] || "overlay.need_asset");
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
    const img = document.createElement("img");
    img.src = opt.src;
    img.alt = opt.name;
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      selectedAsset[overlayMode] = opt.id;
      renderOverlayPicker();
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
  refreshLogoPreview();
}

function openLogoModal(rec) {
  logoId = rec.id;
  rawPreviewSrc = `/output/${rec.filename}`;
  // varsayılanlara sıfırla
  overlayMode = "logo";
  selectedAsset = {
    logo: assetCache.logos[0] ? assetCache.logos[0].id : null,
    motto: assetCache.mottos[0] ? assetCache.mottos[0].id : null,
    banner: assetCache.banners[0] ? assetCache.banners[0].id : null,
  };
  selectInGroup("#logo-type", document.querySelector('#logo-type button[data-type="logo"]'));
  $("logo-only").hidden = false;
  $("banner-only").hidden = true;
  selectInGroup("#logo-grid", document.querySelector('#logo-grid button[data-pos="bottom-right"]'));
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
  return !selectedAsset.logo;   // yerleşik logo yok: kütüphaneden seçim şart
}

async function fetchOverlayPreview() {
  if (!logoId) return;
  if (overlayNeedsAsset()) {
    $("logo-preview-img").src = rawPreviewSrc;
    $("logo-status").textContent = t(OVERLAY_PICK_KEYS[overlayMode] || "overlay.pick_asset");
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
      throw new Error(typeof err.detail === "string" ? err.detail : t("err.http", { durum: res.status }));
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

const OVERLAY_DONE_KEYS = { logo: "library.added_logo", motto: "library.added_motto",
                            banner: "library.added_banner" };

async function applyOverlay() {
  if (!logoId) return;
  if (overlayNeedsAsset()) {
    $("logo-status").textContent = t(OVERLAY_PICK_KEYS[overlayMode] || "overlay.pick_asset");
    return;
  }
  $("logo-apply").disabled = true;
  $("logo-status").textContent = t("overlay.applying");
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
      throw new Error(typeof err.detail === "string" ? err.detail : t("err.http", { durum: res.status }));
    }
    const { image } = await res.json();
    const doneText = t(OVERLAY_DONE_KEYS[overlayMode] || "library.added");
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

