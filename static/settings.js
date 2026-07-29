// GPT-Image Studio — Azure ayarları (write-only) ve açılış çağrıları.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı en sonda, settings.js'in dibinde toplanır.

// ── Azure ayarları (admin, write-only) ──────────────────────────────
// API key hiçbir zaman sunucudan çekilmez/gösterilmez; sadece yazılır.
let configured = false;

function applyConfigured(s) {
  configured = !!(s && s.configured);
  $("go").disabled = !configured;
  if (s && s.endpoint) $("set-endpoint").value = s.endpoint;
  $("set-key").placeholder = configured
    ? "Kayıtlı · değiştirmek için yeni anahtar yaz"
    : "Azure API anahtarını yapıştır";
  if (!configured) {
    statusEl.textContent = "Başlamak için Azure ayarlarını gir (sağ üstteki ⚙).";
  } else if (statusEl.textContent.startsWith("Başlamak için")) {
    statusEl.textContent = "";
  }
  // POST /api/settings yanıtında `version` YOK (sürüm çalışma anında
  // değişmediği için orada gereksiz). Bu fonksiyon hem GET hem POST yanıtı
  // için çağrılıyor; guard MEKANİZMANIN PARÇASI — olmadan "Kaydet"ten sonra
  // sürüm satırı silinirdi.
  if (s && s.version) $("settings-version").textContent = s.version;
}

async function loadSettings(openIfMissing) {
  try {
    const res = await fetch("/api/settings");
    const s = await res.json();
    applyConfigured(s);
    if (!configured && openIfMissing) openSettings();
  } catch {
    // durum alınamadıysa fail-closed: butonu kilitle, kullanıcıyı ayarlara yönlendir
    configured = false;
    $("go").disabled = true;
    statusEl.textContent = "Ayar durumu alınamadı. Azure ayarlarını kontrol et (sağ üstteki ⚙).";
    if (openIfMissing) openSettings();
  }
}

function openSettings() {
  $("set-key").value = ""; // her açılışta boş (write-only)
  $("settings-status").textContent = "";
  $("settings-modal").hidden = false;
  setTimeout(() => $("set-endpoint").focus(), 0);
}

function closeSettings() {
  $("settings-modal").hidden = true;
}

async function saveSettings() {
  const base_url = $("set-endpoint").value.trim();
  const api_key = $("set-key").value;
  const st = $("settings-status");
  if (!base_url) { st.textContent = "Endpoint gerekli."; return; }
  if (!configured && !api_key.trim()) { st.textContent = "İlk kurulumda API key gerekli."; return; }

  $("settings-save").disabled = true;
  st.textContent = "Kaydediliyor…";
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, base_url }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    applyConfigured(await res.json());
    $("set-key").value = "";
    st.textContent = "Kaydedildi.";
    setTimeout(closeSettings, 550);
  } catch (e) {
    st.textContent = e.message;
  } finally {
    $("settings-save").disabled = false;
  }
}

$("settings-btn").addEventListener("click", openSettings);
$("settings-close").addEventListener("click", closeSettings);
$("settings-save").addEventListener("click", saveSettings);
$("settings-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-close")) closeSettings();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && !$("settings-modal").hidden) closeSettings();
});

$("go").addEventListener("click", run);
syncFolderView();
loadFolders();
loadHistory();
loadSettings(true);
loadAssets("logos");
loadAssets("mottos");
loadAssets("banners");
// Palet varsayılan olarak KAPALI: açılışta öneri istenmez, prompt'a hiçbir
// şey eklenmez. Yalnızca kütüphane çekilir ki "Kayıtlı paletler" hazır olsun.
loadPalettes();
