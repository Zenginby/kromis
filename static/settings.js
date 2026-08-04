// GPT-Image Studio — Azure ayarları (write-only) ve açılış çağrıları.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js → viewer.js → chat.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrıları bu dosyanın dibinde toplanır; chat.js sonra yükleniyor ama
// sorun değil — aşağıdaki kapı yalnızca DOM id'lerine dokunuyor.

// ── Azure ayarları (admin, write-only) ──────────────────────────────
// API key hiçbir zaman sunucudan çekilmez/gösterilmez; sadece yazılır.
// Dağıtım adı GİZLİ DEĞİL: GET'ten geliyor ve forma önceden doluyor.
let configured = false;
let chatConfigured = false;   // chat.js okuyor (o dosya BUNDAN SONRA yükleniyor)

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

  // ── Prompt Yönetmeni kapısı ──
  // Sekmenin KENDİSİ kilitlenmiyor: kilitli bir sekme "neden kapalı" bilgisini
  // de saklar. Yalnızca "Gönder" kilitli ve panelde açıklama görünüyor.
  chatConfigured = !!(s && s.chat_configured);
  $("chat-send").disabled = !chatConfigured;
  $("chat-gate").hidden = chatConfigured;
  // `!== undefined`: boş dize "temizlendi" demek ve forma YANSIMASI gerekir.
  if (s && s.chat_deployment !== undefined) {
    $("set-chat-deployment").value = s.chat_deployment;
  }
  // Yalnızca GET'te var (yol çalışma anında değişmez) — version ile aynı guard.
  if (s && s.chat_instructions_path) {
    $("chat-instructions-path").textContent = s.chat_instructions_path;
  }
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
  // #set-chat-deployment BİLEREK temizlenmiyor: write-only değil, GET'ten dolu
  // geliyor. Temizlenirse kullanıcı endpoint'ini güncellemek için modalı açıp
  // kaydettiğinde dağıtım adını da silmiş olurdu.
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
      // chat_deployment HER ZAMAN gönderiliyor: sunucu "alan yok" ile "boş"
      // arasında ayrım yapıyor (bkz. models.SettingsRequest) ve boş dize
      // "Prompt Yönetmeni'ni kapat" demek.
      body: JSON.stringify({ api_key, base_url,
                             chat_deployment: $("set-chat-deployment").value.trim() }),
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
