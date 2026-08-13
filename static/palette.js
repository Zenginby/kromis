// GPT-Image Studio — tema rengi, renk seçici, palet önerileri ve kütüphanesi.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

// ── Tema rengi / renk paleti ────────────────────────────────────────
// Palet `(seed, mode)` çiftinin SAF FONKSİYONU: tel üzerinde iki skaler
// (+ baskı kademesi) yeterli, istemci renk listesi göndermez. Renk
// matematiği ve isimlendirme sunucuda — tek doğruluk kaynağı, thecolorapi
// için CORS yok, ve repodaki tek test altyapısıyla (pytest) test edilebilir.
// dropped: bu üretimde paletten çıkarılan renklerin indeks kümesi (Set<number>).
// activePalette YALNIZCA applyPalette ile kurulur, o yüzden dropped hep var.
let activePalette = null;      // { seed, mode, colors:[{hex,name}], name, id, dropped } | null
let paletteStrength = "balanced";
let paletteCache = [];         // GET /api/palettes
let paletteTab = "new";
let suggestions = [];          // son öneri seti
let suggestSeed = "";          // önerilerin ÜRETİLDİĞİ tohum (input'tan değil, sunucudan)
let selectedSuggestion = null; // seçili harmoni modu
let suggestTimer = null;
let suggestToken = 0;

const HARMONY_LABELS = {
  monochrome: "Tek renk",
  analogic: "Komşu",
  complement: "Karşıt",
  "analogic-complement": "Komşu + karşıt",
  triad: "Üçlü",
  quad: "Dörtlü",
};
const STRENGTH_LABELS = { hint: "İpucu", balanced: "Dengeli", strict: "Katı" };
const DEFAULT_SEED = "#c86a3c";

// ── Renk seçici (HSV karesi + ton kaydırıcısı) ───────────────────────
// Model HSV: alanın zemini iki gradyanla kurulan klasik HSV karesi
// (x = doygunluk, y = 1 - parlaklık), o yüzden nişangah konumunun renge
// birebir karşılık gelmesi için iç model de HSV olmak zorunda.
//
// HSV state AYRI tutuluyor, hex'ten her seferinde türetilmiyor: sürüklerken
// hex'e gidip dönmek yuvarlama yüzünden nişangahı zıplatır.
let pick = { h: 24, s: 0.7, v: 0.78 };

function hsvToRgb(h, s, v) {
  const c = v * s;
  const hp = ((((h % 360) + 360) % 360) / 60);
  const x = c * (1 - Math.abs((hp % 2) - 1));
  const [r, g, b] =
    hp < 1 ? [c, x, 0] : hp < 2 ? [x, c, 0] : hp < 3 ? [0, c, x] :
    hp < 4 ? [0, x, c] : hp < 5 ? [x, 0, c] : [c, 0, x];
  const m = v - c;
  return [r + m, g + m, b + m].map((n) => Math.round(n * 255));
}

function rgbToHsv(r, g, b) {
  const [rn, gn, bn] = [r / 255, g / 255, b / 255];
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const d = max - min;
  let h = null; // akromatik: ton tanımsız (bkz. setPickFromHex)
  if (d) {
    if (max === rn) h = (((gn - bn) / d) % 6 + 6) % 6;
    else if (max === gn) h = (bn - rn) / d + 2;
    else h = (rn - gn) / d + 4;
    h *= 60;
  }
  return { h, s: max ? d / max : 0, v: max };
}

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
}

function pickHex() { return rgbToHex(hsvToRgb(pick.h, pick.s, pick.v)); }

function setPickFromHex(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  const hsv = rgbToHsv(...rgb);
  // Gri/siyah/beyazda ton sayısal olarak anlamsız — MEVCUT tonu koru, yoksa
  // kullanıcı beyaza sürüklediğinde alanın zemini kırmızıya sıçrar.
  pick = { h: hsv.h === null ? pick.h : hsv.h, s: hsv.s, v: hsv.v };
  return true;
}

function renderPicker({ syncHexField = true } = {}) {
  const hex = pickHex();
  const field = $("palette-field");
  field.style.background =
    `linear-gradient(0deg, #000, transparent),` +
    `linear-gradient(90deg, #fff, hsl(${pick.h} 100% 50%))`;
  field.setAttribute("aria-valuetext", `doygunluk ${Math.round(pick.s * 100)}%, ` +
    `parlaklık ${Math.round(pick.v * 100)}%, ${hex}`);
  const thumb = $("palette-field-thumb");
  thumb.style.left = `${pick.s * 100}%`;
  thumb.style.top = `${(1 - pick.v) * 100}%`;
  thumb.style.background = hex;
  $("palette-hue").value = String(Math.round(pick.h));
  $("palette-seed-sw").style.background = hex;
  // Kullanıcı yazarken alanı ezmemek için hex girdisi opsiyonel güncellenir.
  if (syncHexField) $("palette-seed-hex").value = hex;
}

/** Alandaki bir noktadan doygunluk/parlaklık. */
function setPickFromPoint(clientX, clientY) {
  const r = $("palette-field").getBoundingClientRect();
  if (!r.width || !r.height) return;
  pick.s = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
  pick.v = 1 - Math.min(1, Math.max(0, (clientY - r.top) / r.height));
  renderPicker();
  scheduleSuggest();
}

function paletteStatus(msg) { $("palette-status").textContent = msg || ""; }
function paletteModalStatus(msg) { $("palette-modal-status").textContent = msg || ""; }

/** 422 gövdesi bir dizi olabiliyor; `err.detail` doğrudan basılırsa çöp çıkar. */
function detailText(err) {
  const d = err && err.detail;
  if (!d) return "";
  if (typeof d === "string") return d;
  if (!Array.isArray(d)) return "";
  if (d.some((e) => e && e.type === "extra_forbidden")) {
    return "Sunucu bu alanı tanımıyor — eski bir sunucu süreci çalışıyor. " +
           "./run.sh ile yeniden başlat.";
  }
  return d.map((e) => (e && e.msg) || "").filter(Boolean).join("; ");
}

/** Renk örneği şeridi. Örneklerin ÜSTÜNE metin yazılmaz — bkz. style.css notu. */
// `interactive`: her swatch bir <button> olur ve tıklanınca renk paletten
// çıkarılır/geri alınır. YALNIZCA çipte açılıyor — öneri kartları
// makeChoiceButton içinde bir <button>'ın içinde duruyor ve iç içe buton
// geçersiz HTML.
function swatchRow(colors, { interactive = false, dropped = null, onToggle = null } = {}) {
  const row = document.createElement("span");
  row.className = "palette-sw-row";
  (colors || []).forEach((c, index) => {
    const isDropped = dropped ? dropped.has(index) : false;
    const sw = document.createElement(interactive ? "button" : "span");
    sw.className = "palette-sw" + (isDropped ? " palette-sw-dropped" : "");
    // Keyfi kullanıcı rengi: bu dosyadaki tek meşru satır-içi stil kullanımı,
    // çünkü değer çalışma anında belli oluyor ve CSS'e yazılamıyor.
    //
    // `background` DEĞİL `backgroundColor`: kısayol satır-içi olarak
    // background-image'ı da `none`'a çeker ve satır-içi stil sınıfı yendiği
    // için .palette-sw-dropped'ın çapraz çizgisi hiç görünmezdi.
    sw.style.backgroundColor = c.hex;
    sw.title = `${c.name} · ${c.hex}`;
    if (interactive) {
      sw.type = "button";
      // Bilgi renk algısına bağlı olmasın: durum hem aria-pressed hem metinde.
      sw.setAttribute("aria-pressed", String(isDropped));
      sw.setAttribute("aria-label",
        `${c.name} ${c.hex} — ${isDropped ? "geri ekle" : "paletten çıkar"}`);
      sw.addEventListener("click", () => onToggle(index));
    }
    row.appendChild(sw);
  });
  return row;
}

function paletteTitleOf(pal) {
  return pal.name || HARMONY_LABELS[pal.mode] || pal.mode;
}

function renderPalettePanel() {
  const chip = $("palette-chip");
  if (!activePalette) {
    chip.hidden = true;
    $("palette-strength-row").hidden = true;
    $("palette-mode-note").hidden = true;
    return;
  }
  chip.hidden = false;
  const holder = $("palette-chip-sw");
  holder.innerHTML = "";
  holder.appendChild(swatchRow(activePalette.colors, {
    interactive: true,
    dropped: activePalette.dropped,
    onToggle: toggleDroppedColor,
  }));

  const total = (activePalette.colors || []).length;
  const kept = total - activePalette.dropped.size;
  // Sayaç YALNIZCA bir şey çıkarıldığında görünüyor: her zaman "5/5" yazmak
  // kullanıcıya taşımadığı bir bilgiyi sürekli okutur.
  const count = activePalette.dropped.size ? ` · ${kept}/${total} renk` : "";
  $("palette-label").textContent =
    `${paletteTitleOf(activePalette)} · ${STRENGTH_LABELS[paletteStrength]}${count}`;

  $("palette-strength-row").hidden = false;
  selectInGroup("#palette-strength",
    document.querySelector(`#palette-strength button[data-strength="${paletteStrength}"]`));

  // Aynı palet iki farklı ifadeyle gidiyor: üretimde "bu renkleri kullan",
  // düzenlemede "renkleri kaydır, kompozisyonu koru". Kullanıcı hangisinin
  // geçerli olduğunu görmeli.
  const note = $("palette-mode-note");
  note.hidden = false;
  note.textContent = source
    ? "Referans görselde renk derecelendirmesi olarak uygulanır — kompozisyon korunur."
    : "Renk yönlendirmesi prompt'un sonuna İngilizce eklenir.";
}

function readPaletteOpts() {
  if (!activePalette) return {};
  const opts = {
    palette_hex: activePalette.seed,
    palette_mode: activePalette.mode,
    palette_strength: paletteStrength,
  };
  // Kayıtlı palette id de gider: sunucu adları kaydın dondurulmuş halinden
  // okur, böylece kütüphanede görünen ad ile prompt'a giden ad ayrışmaz.
  if (activePalette.id) opts.palette_id = activePalette.id;
  // YALNIZCA bir şey çıkarıldığında gönderiliyor: hiçbir şey çıkarılmadığında
  // tel v1.10'dakiyle birebir aynı kalıyor.
  //
  // /api/generate (JSON) bunu dizi olarak alır; /api/edit multipart olduğu için
  // core.js'in genel döngüsü aynı diziyi FormData'ya "0,3" diye yazar (JS
  // Array→String) ve sunucu orada ayrıştırır. Döngüyü elle sayıma çevirmek bir
  // kez palette_id'yi düşürmüştü — bkz. core.js'teki not.
  if (activePalette.dropped.size) {
    opts.palette_drop = [...activePalette.dropped].sort((a, b) => a - b);
  }
  return opts;
}

// Çıkarma O ÜRETİME özel: yeni palet seçilince sıfırlanır. Kalıcı olarak daha
// az renkli bir palet isteyen kullanıcı çıkarıp KAYDEDİYOR — kayıt donmuş renk
// listesi tuttuğu için o palet 4 renkle donar (bkz. sunucudaki SavePaletteRequest.drop).
function applyPalette({ seed, mode, colors, name = "", strength = null, id = null }) {
  activePalette = { seed, mode, colors, name, id, dropped: new Set() };
  if (strength) paletteStrength = strength;
  renderPalettePanel();
  paletteStatus(`Palet uygulandı: ${paletteTitleOf(activePalette)}`);
}

function toggleDroppedColor(index) {
  if (!activePalette) return;
  const dropped = activePalette.dropped;
  if (!dropped.has(index) && dropped.size + 1 >= activePalette.colors.length) {
    // Son rengi de çıkarmak paleti anlamsız kılar (sunucu da 422 verir).
    // Kapıyı burada tutmak kullanıcıya nedenini söylüyor; sunucuya bırakmak
    // "üret" anında patlayan bir hata olurdu.
    paletteStatus("En az bir renk kalmalı.");
    return;
  }
  if (dropped.has(index)) dropped.delete(index);
  else dropped.add(index);
  renderPalettePanel();
  paletteStatus("");
}

function clearPalette() {
  activePalette = null;
  renderPalettePanel();
  paletteStatus("Palet kaldırıldı.");
}

// ── Öneriler ────────────────────────────────────────────────────────
function scheduleSuggest() {
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(fetchSuggestions, 220);
}

async function fetchSuggestions() {
  const token = ++suggestToken;
  paletteModalStatus("Paletler hesaplanıyor…");
  try {
    const res = await fetch("/api/palette/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hex: pickHex() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const body = await res.json();
    // Sıra dışı yanıt guard'ı (logoPreviewToken deseni). DOM'dan ÖNCE state'i
    // korumak asıl önemli olan: geç gelen bir yanıt kullanıcının sonra
    // KAYDEDECEĞİ palete yanlış renk/isim yazarsa hata kalıcı olur.
    if (token !== suggestToken) return;
    suggestions = body.items || [];
    suggestSeed = body.seed;
    selectedSuggestion = null;
    renderSuggestions();
    paletteModalStatus("");
  } catch (e) {
    if (token !== suggestToken) return;
    suggestions = [];
    suggestSeed = "";
    selectedSuggestion = null;
    renderSuggestions();
    paletteModalStatus(e.message);
  }
}

function makeChoiceButton({ title, colors, subtitle }) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "palette-choice";
  const names = (colors || []).map((c) => c.name).join(", ");
  // Bilgi hiçbir zaman renk algısına bağlı olmasın: ad + hex her zaman metinde.
  btn.setAttribute("aria-label", `${title}: ${names}`);

  const titleEl = document.createElement("span");
  titleEl.className = "palette-choice-title";
  titleEl.textContent = title;
  btn.appendChild(titleEl);
  btn.appendChild(swatchRow(colors));

  const sub = document.createElement("span");
  sub.className = "palette-choice-names";
  sub.textContent = subtitle === undefined ? names : subtitle;
  btn.appendChild(sub);
  return btn;
}

function emptyNote(grid, text) {
  const p = document.createElement("p");
  p.className = "palette-empty";
  p.textContent = text;
  grid.appendChild(p);
}

function renderSuggestions() {
  const grid = $("palette-suggestions");
  grid.innerHTML = "";
  if (!suggestions.length) {
    emptyNote(grid, "Palet önerisi yok — bir tema rengi seç.");
  } else {
    for (const item of suggestions) {
      const btn = makeChoiceButton({
        title: HARMONY_LABELS[item.mode] || item.mode,
        colors: item.colors,
      });
      btn.setAttribute("aria-pressed", String(selectedSuggestion === item.mode));
      btn.addEventListener("click", () => {
        selectedSuggestion = item.mode;
        renderSuggestions();
      });
      grid.appendChild(btn);
    }
  }
  const ready = currentSuggestion() !== null;
  $("palette-save").disabled = !ready;
  $("palette-apply").disabled = !ready;
}

function currentSuggestion() {
  return suggestions.find((s) => s.mode === selectedSuggestion) || null;
}

// ── Kütüphane ───────────────────────────────────────────────────────
async function loadPalettes() {
  try {
    const res = await fetch("/api/palettes");
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    paletteCache = (await res.json()).items || [];
  } catch {
    paletteCache = [];
    paletteStatus("Palet kütüphanesi alınamadı.");
  }
  // Panel slide-over: açıklık `hidden` ile değil `.open` sınıfıyla anlatılıyor.
  if ($("palette-modal").classList.contains("open") && paletteTab === "saved") {
    renderPaletteLibrary();
  }
}

function renderPaletteLibrary() {
  const grid = $("palette-lib-grid");
  grid.innerHTML = "";
  if (!paletteCache.length) {
    emptyNote(grid, "Henüz kayıtlı palet yok — \"Yeni palet\" sekmesinden oluştur.");
    return;
  }
  for (const rec of paletteCache) {
    const cell = document.createElement("div");
    cell.className = "palette-lib-cell";

    const btn = makeChoiceButton({
      title: rec.name,
      colors: rec.colors,
      subtitle: `${HARMONY_LABELS[rec.mode] || rec.mode} · ` +
                `${STRENGTH_LABELS[rec.strength] || rec.strength}`,
    });
    btn.addEventListener("click", () => {
      // Kayıttaki renkler zaten dondurulmuş — yeniden hesaplamaya gerek yok.
      applyPalette({ seed: rec.seed, mode: rec.mode, colors: rec.colors,
                     name: rec.name, strength: rec.strength, id: rec.id });
      closePaletteModal();
    });
    cell.appendChild(btn);

    const del = document.createElement("button");
    del.type = "button";
    del.className = "palette-lib-del";
    del.setAttribute("aria-label", `${rec.name} paletini sil`);
    del.title = "Paleti sil";
    del.textContent = "×";
    del.addEventListener("click", (e) => { e.stopPropagation(); deletePalette(rec); });
    cell.appendChild(del);

    grid.appendChild(cell);
  }
}

async function savePalette() {
  const item = currentSuggestion();
  if (!item) return;
  const name = await promptDialog(
    "Paleti kaydet",
    "\"Kayıtlı paletler\" sekmesinden sonraki üretimlerde yeniden seçebilirsin.",
    { okLabel: "Kaydet" });
  if (!name) return;
  try {
    const res = await fetch("/api/palettes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, seed: suggestSeed, mode: item.mode,
                             strength: paletteStrength }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err) || `Hata (${res.status})`);
    }
    const saved = (await res.json()).palette;
    await loadPalettes();
    applyPalette({ seed: saved.seed, mode: saved.mode, colors: saved.colors,
                   name: saved.name, strength: saved.strength, id: saved.id });
    closePaletteModal();
  } catch (e) {
    paletteModalStatus(e.message);
  }
}

async function deletePalette(rec) {
  const ok = await confirmDialog(
    `"${rec.name}" paletini sil?`,
    "Palet kütüphaneden kaldırılır. Üretilmiş görseller etkilenmez.");
  if (!ok) return;
  try {
    const res = await fetch(`/api/palettes/${rec.id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Hata (${res.status})`);
    await loadPalettes();
    renderPaletteLibrary();
    paletteModalStatus("Palet silindi.");
  } catch (e) {
    paletteModalStatus(e.message);
  }
}

// ── Modal ───────────────────────────────────────────────────────────
function setPaletteTab(tab) {
  paletteTab = tab;
  $("palette-new").hidden = tab !== "new";
  $("palette-saved").hidden = tab !== "saved";
  selectInGroup("#palette-tabs",
    document.querySelector(`#palette-tabs button[data-ptab="${tab}"]`));
  if (tab === "saved") renderPaletteLibrary();
}

function openPaletteModal() {
  // openLogoModal dersi: HER kontrol açılışta varsayılana döndürülmeli,
  // yoksa modal önceki tohumu/seçimi sızdırır.
  setPickFromHex(activePalette ? activePalette.seed : DEFAULT_SEED);
  renderPicker();
  suggestions = [];
  suggestSeed = "";
  selectedSuggestion = null;
  renderSuggestions();
  paletteModalStatus("");
  setPaletteTab("new");
  // A5 (Adım 7b): ortalanmış modal değil sağdan slide-over — renk seçilirken
  // arkadaki tuval görünür kalmalı. Açma/kapama tek kapıdan (core.openSheet).
  openSheet("palette-modal");
  fetchSuggestions();
}

function closePaletteModal() { closeSheets(); }

$("palette-btn").addEventListener("click", openPaletteModal);
// Araçlar görünümündeki kart da aynı paneli açıyor (tasarım §4.1).
$("tool-palette").addEventListener("click", openPaletteModal);
$("palette-close").addEventListener("click", closePaletteModal);
$("palette-clear").addEventListener("click", clearPalette);
$("palette-save").addEventListener("click", savePalette);
$("palette-apply").addEventListener("click", () => {
  const item = currentSuggestion();
  if (!item) return;
  // Tohum sunucunun döndürdüğü normalize edilmiş değer — arada input
  // değiştiyse önerilerle tutarsız bir palet uygulanmasın.
  applyPalette({ seed: suggestSeed, mode: item.mode, colors: item.colors });
  closePaletteModal();
});

// Perde tıklaması ve Escape artık kabuğun ortak slide-over dinleyicilerinde
// (core.js: #shell-scrim + confirm-modal guard'lı Escape) — panele özel
// backdrop/Escape kodu bilerek yok.

$("palette-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-ptab]");
  if (btn) setPaletteTab(btn.dataset.ptab);
});

// ── Seçici olayları ─────────────────────────────────────────────────
// Sürükleme: pointer capture kullanılıyor — window'a dinleyici ekleyip
// kaldırmaya gerek kalmıyor, imleç alanın dışına çıksa da takip sürüyor ve
// sızdırılacak bir dinleyici olmuyor.
const paletteField = $("palette-field");
paletteField.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  paletteField.setPointerCapture(e.pointerId);
  setPickFromPoint(e.clientX, e.clientY);
});
paletteField.addEventListener("pointermove", (e) => {
  if (paletteField.hasPointerCapture(e.pointerId)) setPickFromPoint(e.clientX, e.clientY);
});

// Alan klavyeyle de ayarlanabilir: yalnızca fare ile çalışan bir renk seçici
// klavye kullanıcısı için ton kaydırıcısı + hex alanına mahkûm ederdi.
const PICK_STEP = 0.01;
const PICK_STEP_BIG = 0.1;
paletteField.addEventListener("keydown", (e) => {
  const step = e.shiftKey ? PICK_STEP_BIG : PICK_STEP;
  const moves = {
    ArrowLeft: [-step, 0], ArrowRight: [step, 0],
    ArrowUp: [0, step], ArrowDown: [0, -step],
  };
  const move = moves[e.key];
  if (!move) return;
  e.preventDefault();
  pick.s = Math.min(1, Math.max(0, pick.s + move[0]));
  pick.v = Math.min(1, Math.max(0, pick.v + move[1]));
  renderPicker();
  scheduleSuggest();
});

$("palette-hue").addEventListener("input", () => {
  pick.h = Number($("palette-hue").value);
  renderPicker();
  scheduleSuggest();
});

// Marka rehberi sana tekerlek konumu değil hex verir; elle yazılabilmeli.
// syncHexField=false: kullanıcı yazarken girdiyi normalize edip imleci
// zıplatmamak için.
$("palette-seed-hex").addEventListener("input", () => {
  if (!setPickFromHex($("palette-seed-hex").value)) return;
  renderPicker({ syncHexField: false });
  scheduleSuggest();
});
$("palette-seed-hex").addEventListener("blur", () => renderPicker());

// ── Damlalık: iki ortam, iki API, AYNI davranış ─────────────────────
//
// Tarayıcı        → EyeDropper (Chromium'a özel)
// Paket (macOS)    → window.pywebview.api.pick_screen_color (NSColorSampler)
// Paket (Windows)  → EyeDropper: WebView2 Chromium tabanlı, API orada VAR
//
// Üçü de EKRAN GENELİ seçim yapıyor, yani kullanıcı ortam farkını görmüyor.
// Köprü v1.11'de eklendi: pywebview'ın macOS arka ucu WKWebView (WebKit) ve
// WebKit EyeDropper'ı hiç uygulamadı — o yüzden düğme v1.10'a kadar app'te
// gizli kalıyordu (bug değil, motor farkıydı).
//
// SIRA ÖNEMLİ — EyeDropper ÖNCE denenir. Köprü platformdan bağımsız enjekte
// ediliyor, yani Windows paketinde `pick_screen_color` DA var ama orada
// bilinçli olarak hep null dönüyor (screencolor: NSColorSampler yalnız macOS).
// Native yol önce sorulursa Windows'ta çalışan EyeDropper hiç denenmez ve
// düğme "tıklıyorum, hiçbir şey olmuyor" durumuna düşer.

function nativeScreenPicker() {
  return window.pywebview && window.pywebview.api
    && window.pywebview.api.pick_screen_color;
}

async function pickScreenColor() {
  if (window.EyeDropper) {
    const { sRGBHex } = await new EyeDropper().open();
    return sRGBHex;
  }
  return await nativeScreenPicker()();
}

function enableEyedropper() {
  const btn = $("palette-eyedrop");
  if (btn.dataset.wired) return;      // iki yoklama birden geçmesin
  btn.dataset.wired = "1";
  btn.hidden = false;
  btn.addEventListener("click", async () => {
    try {
      const hex = await pickScreenColor();
      // Native yol iptalde null döner (istisna DEĞİL); EyeDropper ise
      // fırlatır. İki sözleşme de "seçim yok" demek, ikisi de sessiz.
      if (hex && setPickFromHex(hex)) { renderPicker(); scheduleSuggest(); }
    } catch {
      // Kullanıcı Esc ile vazgeçti — hata değil, sessizce geç.
    }
  });
}

// TUZAK: pywebview köprüsü sayfa yüklendikten SONRA enjekte ediliyor, yani bu
// dosya koşarken `window.pywebview` henüz yok olabilir. Yalnızca senkron
// kontrol yapılsa app'te yanlış negatif çıkar ve düzeltme "bazen görünmüyor"
// diye geri dönerdi. Bu yüzden hem şimdi bakılıyor hem de pywebview'ın kendi
// hazır olayı dinleniyor.
if (window.EyeDropper || nativeScreenPicker()) {
  enableEyedropper();
} else {
  window.addEventListener("pywebviewready", enableEyedropper, { once: true });
}

$("palette-strength").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-strength]");
  if (!btn) return;
  paletteStrength = btn.dataset.strength;
  renderPalettePanel();
});

