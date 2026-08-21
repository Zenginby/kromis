// Lumeo — Azure ayarları (write-only) ve açılış çağrıları.
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
  // Model kataloğu AYNI yanıttan okunuyor: ayrı bir uçtan çekilse ikisi ayrı
  // zamanlarda gelir ve seçici bir an "hepsi kullanılabilir" gösterip sonra
  // fikir değiştirirdi (`guncelleme` alanı için yazılı olan gerekçe).
  // `prefs` HENÜZ okunmadıysa (ilk çizim) sunucunun varsayılanı kullanılıyor;
  // loadPrefs sonra gelip kullanıcının tercihini uyguluyor.
  applyModels(s, seciliModelTercihi);
  // Yönetmenin şeridi AYNI yanıttan: ayrı bir uçtan çekilse ikisi ayrı
  // zamanlarda gelir ve seçici bir an "hepsi kullanılabilir" gösterip sonra
  // fikir değiştirirdi (`guncelleme` alanı için yazılı olan gerekçe).
  applyChatModels(s, seciliSohbetModeliTercihi);
  // `#go` artık BURADA yazılmıyor: tek yazar core.js'teki syncGoGate ve o,
  // yapılandırma + mod + seçili modelin durumunu BİRLİKTE görüyor. Öncesinde
  // dört ayrı yerden yazılıyordu ve `!configured` yalnız AZURE'u ölçtüğü için
  // yalnızca OpenAI anahtarı olan bir kullanıcıda ölü bir düğme bırakırdı.
  syncGoGate();
  if (s && s.endpoint) $("set-endpoint").value = s.endpoint;
  $("set-key").placeholder = configured
    ? "Kayıtlı · değiştirmek için yeni anahtar yaz"
    : "Azure API anahtarını yapıştır";

  // Sağlayıcı başına "Kayıtlı" durumu. `!== undefined` guard'ı `version` ve
  // `guncelleme` ile AYNI gerekçeye sahip: POST /api/settings yanıtı GET'ten
  // daha dar olabilir ve guard olmadan "Kaydet"ten sonra durumlar silinirdi.
  if (s && s.providers !== undefined) {
    // Yer tutucu "kayıtlı mı"yı SÖYLÜYOR, anahtarı göstermiyor: yalnızca-yazılır
    // formda boş bir kutu yoksa kullanıcı anahtarını hiç kaydetmediğini sanır.
    // Tablo halinde: her sağlayıcının kimlik id'si + boş hâlin yer tutucusu.
    for (const [alan, kimlik, bos] of [
      ["set-openai-key", "openai", "sk-…"],
      ["set-gemini-key", "gemini", "AIza…"],
    ]) {
      $(alan).placeholder = s.providers[kimlik]
        ? "Kayıtlı · değiştirmek için yeni anahtar yaz"
        : bos;
    }
    renderProviderStatus(s.providers);
  }

  // Açılış mesajı artık SEÇİLİ MODELE bakıyor, Azure'a değil: yalnızca OpenAI
  // anahtarı olan bir kullanıcıya "Azure ayarlarını gir" demek onu hiç
  // ihtiyacı olmayan bir forma yönlendirirdi.
  const kapali = goBlockReason();
  if (kapali) {
    statusEl.textContent = `${kapali} (sağ üstteki ⚙)`;
  } else if (statusEl.textContent.includes("(sağ üstteki ⚙)")
             || statusEl.textContent.startsWith("Başlamak için")) {
    statusEl.textContent = "";
  }
  // POST /api/settings yanıtında `version` YOK (sürüm çalışma anında
  // değişmediği için orada gereksiz). Bu fonksiyon hem GET hem POST yanıtı
  // için çağrılıyor; guard MEKANİZMANIN PARÇASI — olmadan "Kaydet"ten sonra
  // sürüm satırı silinirdi.
  // Tek id yerine `[data-app-version]`: sürüm İKİ yerde görünüyor (üst şeritteki
  // pill + Ayarlar'ın dibindeki satır) çünkü pill telefonda gizli ve orada başka
  // kaynak yok. İkisini iki ayrı satırla yazmak, birini eklerken diğerini
  // unutmanın kapısıydı — sürüm de sessizce "—" kalırdı.
  if (s && s.version) {
    for (const el of document.querySelectorAll("[data-app-version]")) {
      el.textContent = s.version;
    }
  }

  // ── "Yeni sürüm çıktı" satırı ──
  // `!== undefined` guard'ı, hemen yukarıdaki `version` guard'ıyla AYNI
  // gerekçeye sahip: POST /api/settings yanıtında `guncelleme` alanı YOK.
  // Guard olmadan "Kaydet"e basmak satırı sessizce gizlerdi.
  //
  // GET'te alan HER ZAMAN var ama `null` olabilir — üç ayrı durumu birden
  // anlatıyor ve arayüz için üçü de aynı: kontrol kapalı, henüz cevap yok,
  // ya da zaten en yeni sürümdeyiz (bkz. guncelleme.py → bilgi()).
  if (s && s.guncelleme !== undefined) {
    const satir = $("settings-update");
    if (s.guncelleme && s.guncelleme.surum) {
      $("settings-update-version").textContent = s.guncelleme.surum;
      if (s.guncelleme.url) $("settings-update-link").href = s.guncelleme.url;
      satir.hidden = false;
    } else {
      satir.hidden = true;
    }
  }

  // ── Prompt Yönetmeni kapısı ──
  // Sekmenin KENDİSİ kilitlenmiyor: kilitli bir sekme "neden kapalı" bilgisini
  // de saklar. Yalnızca "Gönder" kilitli ve panelde açıklama görünüyor.
  chatConfigured = !!(s && s.chat_configured);
  if (typeof syncSendButton === "function") syncSendButton();
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
    // Kapı `configured`e BAKMIYOR: o bayrak yalnız AZURE'u ölçüyor ve
    // yalnızca OpenAI anahtarı olan kullanıcıya her açılışta Ayarlar
    // panelini zorla açıyordu — tam olarak 180342a'nın kapatmaya çalıştığı
    // durum. Ölçüt "hiçbir modelin anahtarı yok", yani ilk kurulum.
    //
    // `goBlockReason()` BİLEREK kullanılmıyor: o SEÇİLİ modeli ölçüyor ve
    // başka bir modeli yapılandırmış kullanıcı sırf anahtarsız bir model
    // seçtiği için paneli yüzünde bulurdu.
    if (openIfMissing && !imageModels.some((m) => m.configured)) openSettings();
  } catch {
    // durum alınamadıysa fail-closed: butonu kilitle, kullanıcıyı ayarlara yönlendir
    configured = false;
    // Katalog da boşaltılıyor: eski bir listeyle kapı açık kalırsa kullanıcı
    // artık geçerli olmayan bir modelle üretmeye çalışır.
    imageModels = [];
    currentModel = null;
    syncGoGate();
    statusEl.textContent = "Ayar durumu alınamadı. Sağlayıcı ayarlarını kontrol et (sağ üstteki ⚙).";
    if (openIfMissing) openSettings();
  }
}

/** Sağlayıcı durum satırları. Seçici + tek alan grubu deseninin bedeli olan
 *  "hangisi kurulu?" görünümünü geri veriyor; kaynak `providers` bayrakları. */
function renderProviderStatus(providers) {
  const satirlar = [
    ["azure_image", "Azure OpenAI"],
    ["openai", "OpenAI"],
    ["gemini", "Google Gemini"],
  ];
  $("provider-status").replaceChildren(...satirlar.map(([id, ad]) => {
    const li = document.createElement("li");
    // `textContent`: sunucudan gelen hiçbir şey innerHTML'e girmiyor.
    li.textContent = `${ad}: ${providers[id] ? "kayıtlı" : "kayıtlı değil"}`;
    li.classList.toggle("ok", !!providers[id]);
    return li;
  }));
}

/** Seçilen sağlayıcının alan grubunu gösterir, ötekileri gizler. */
function syncProviderFields() {
  const secili = $("set-provider").value;
  for (const p of ["azure", "openai", "gemini"]) {
    $(`prov-${p}`).hidden = p !== secili;
  }
  syncChatDeployField(secili);
}

/** Dağıtım adı kutusu YALNIZCA onu isteyen sağlayıcıda görünüyor.
 *
 * Kutu öncesinde koşulsuzdu: OpenAI ya da Gemini anahtarı girmeye gelen
 * kullanıcı, o sağlayıcılarda karşılığı OLMAYAN bir alan görüyordu ("dağıtım"
 * Azure'a özgü — ötekilerde model adı katalogda yazılı). Yanlış bir soru,
 * üstelik 360px'lik bir slide-over'da ödenmiş yer.
 *
 * KAPI KATALOGDAN türetiliyor: `chat_models[].needs_deployment` bayrağı
 * `catalog.chat_needs_deployment`ten geliyor ve o da tek bir olguya bakıyor —
 * modelin adı ortamdan mı okunuyor. Sağlayıcı adını burada LİTERAL saymak,
 * adı ortamdan okunan ikinci bir sağlayıcı eklendiği gün kutunun sessizce
 * görünmez kalması demekti.
 *
 * FAIL-OPEN: katalog henüz gelmediyse (ilk çizim, ya da `/api/settings`
 * başarısız) kutu GÖRÜNÜYOR. Tersi, ayar durumu alınamayan bir kullanıcının
 * dağıtım adını hiç giremeyeceği anlamına gelirdi — yani bugün çalışan tek
 * sağlayıcı kurtarılamaz olurdu.
 */
function syncChatDeployField(provider) {
  const isteyen = chatModels.length
    ? chatModels.some((m) => m.needs_deployment && m.provider === provider)
    : true;
  $("chat-deploy-group").hidden = !isteyen;
  $("chat-no-deploy-note").hidden = isteyen;
}

$("set-provider").addEventListener("change", syncProviderFields);

function openSettings(provider) {
  // Gizli alanların HEPSİ temizleniyor (write-only): kayıtlı anahtar hiçbir
  // zaman forma dolmuyor, o yüzden boş kutu "sildim" değil "dokunmadım"dır.
  $("set-openai-key").value = "";
  $("set-gemini-key").value = "";
  // Belirli bir sağlayıcıya derin bağlantı: #model-settings-link buradan
  // geliyor, "anahtar yok" uyarısı doğrudan doğru gruba açsın.
  if (provider) $("set-provider").value = provider;
  syncProviderFields();
  $("set-key").value = ""; // her açılışta boş (write-only)
  // #set-chat-deployment BİLEREK temizlenmiyor: write-only değil, GET'ten dolu
  // geliyor. Temizlenirse kullanıcı endpoint'ini güncellemek için paneli açıp
  // kaydettiğinde dağıtım adını da silmiş olurdu.
  $("settings-status").textContent = "";
  // A5 (Adım 7b): panel sağdan slide-over (tasarım §2.4/3). Açma/kapama tek
  // kapıdan (core.openSheet); perde ve Escape kabuğun ortak dinleyicilerinde.
  openSheet("settings-modal");
  setTimeout(() => $("set-endpoint").focus(), 0);
}

function closeSettings() { closeSheets(); }

async function saveSettings() {
  const base_url = $("set-endpoint").value.trim();
  const api_key = $("set-key").value;
  const st = $("settings-status");
  // Kapı SAĞLAYICIYA BAĞLI. Öncesinde koşulsuzdu ve "Endpoint gerekli" hatası
  // OpenAI anahtarı eklemeye çalışan kullanıcıya BAŞKA bir sağlayıcı hakkında
  // konuşuyordu — sunucu tarafındaki aynı kilidin istemci yarısı.
  if ($("set-provider").value === "azure") {
    if (!base_url) { st.textContent = "Endpoint gerekli."; return; }
    if (!configured && !api_key.trim()) {
      st.textContent = "İlk kurulumda API key gerekli."; return;
    }
  }

  $("settings-save").disabled = true;
  st.textContent = "Kaydediliyor…";
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // chat_deployment HER ZAMAN gönderiliyor: sunucu "alan yok" ile "boş"
      // arasında ayrım yapıyor (bkz. models.SettingsRequest) ve boş dize
      // "Prompt Yönetmeni'ni kapat" demek.
      // Boş gizli alan "mevcut korunur" demek (sunucunun kuralı), o yüzden
      // her sağlayıcının alanı KOŞULSUZ gönderilebiliyor — istemcinin hangi
      // grubun açık olduğuna göre dallanmasına gerek yok.
      body: JSON.stringify({ api_key, base_url,
                             chat_deployment: $("set-chat-deployment").value.trim(),
                             openai_api_key: $("set-openai-key").value,
                             gemini_api_key: $("set-gemini-key").value }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Hata (${res.status})`);
    }
    applyConfigured(await res.json());
    $("set-key").value = "";
    $("set-openai-key").value = "";
    $("set-gemini-key").value = "";
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

// ── Tema seçici (A6 / Adım 7b) ──────────────────────────────────────
// Dört temanın token'ları flow-tokens.css'te Adım 1'den beri hazırdı
// ([data-theme=…]); burası onları GERÇEKTEN uygulayan taraf. Monokrom =
// öznitelik yok: varsayılan --accent zaten monokrom, sahte bir "mono"
// değeri yazmak token katmanında karşılığı olmayan bir durum üretirdi.
// KALICILIK BİLEREK YOK — SettingsRequest'te tema alanı yok; o Adım 9'un
// arka uç işi ve panel bunu kullanıcıya açıkça söylüyor.
function applyTheme(theme) {
  if (theme === "mono") delete document.body.dataset.theme;
  else document.body.dataset.theme = theme;
}

async function saveThemePref(theme) {
  try {
    await chatApi("/api/prefs", { method: "POST", body: { theme } });
  } catch (e) {
    console.warn("Tema tercihi kaydedilemedi:", e);
  }
}

$("tool-look").addEventListener("click", () => openSheet("look-sheet"));
$("look-close").addEventListener("click", closeSheets);
$("theme-picker").addEventListener("change", (e) => {
  if (e.target.name === "theme") {
    const theme = e.target.value;
    applyTheme(theme);
    saveThemePref(theme);
  }
});

/** Kullanıcının kayıtlı model tercihi. `applyModels` bunu okuyor.
 *
 * Ayrı bir değişken çünkü İKİ uç iki farklı zamanda dönüyor: `/api/settings`
 * kataloğu, `/api/prefs` tercihi getiriyor. Hangisi önce gelirse gelsin doğru
 * sonuç çıkmalı — katalog önce gelirse sunucunun varsayılanı çiziliyor ve
 * tercih gelince düzeltiliyor; tercih önce gelirse burada bekliyor.
 */
let seciliModelTercihi = "";
/** Yönetmenin karşılığı. AYRI değişken, aynı gerekçe: iki uç iki farklı
 *  zamanda dönüyor ve hangisi önce gelirse gelsin doğru sonuç çıkmalı.
 *
 *  `chat_provider` BURADA TUTULMUYOR: model id'si sağlayıcıyı zaten belirliyor
 *  (`chat_models[].provider`) ve ikinci bir değişken ikisinin ayrışmasına kapı
 *  açardı — diskte "azure" + OpenAI modeli gibi bir çift `prefs.update`
 *  tarafından zaten reddediliyor. */
let seciliSohbetModeliTercihi = "";

async function loadModelPref() {
  try {
    const res = await fetch("/api/prefs");
    if (!res.ok) return;
    const p = await res.json();
    // Sohbet tercihi GÖRSELDEN BAĞIMSIZ okunuyor: `image_model` boşsa erken
    // dönmek, sohbet seçimini de sessizce yutardı.
    if (p.chat_model) {
      seciliSohbetModeliTercihi = p.chat_model;
      if (chatModels.length) {
        applyChatModel(secilecek(chatModels, seciliSohbetModeliTercihi, ""));
      }
    }
    if (!p.image_model) return;
    seciliModelTercihi = p.image_model;
    // Katalog zaten geldiyse tercihi ŞİMDİ uygula; gelmediyse applyModels
    // yukarıdaki değişkeni okuyacak.
    //
    // TERCİH DOĞRUDAN UYGULANMIYOR, `secilecek`ten geçiyor: bu uç `/api/settings`
    // ile YARIŞIYOR ve buraya `applyModels`ten SONRA gelirse anahtarı olmayan
    // bir tercihi geri yazardı — yani filtrenin kararını sessizce iptal
    // ederdi. Gerçek chromium koşumunda ölçüldü: yalnız Gemini anahtarı olan
    // kullanıcı, `prefs`in Azure olan VARSAYILANI yüzünden ölü bir #go
    // düğmesiyle karşılanıyordu. Varsayılan argüman boş: bu çağrının
    // varsayılan modeli dayatacak bir işi yok, sunucunun kararı zaten
    // uygulanmış durumda.
    if (imageModels.length) {
      applyModel(secilecek(imageModels, seciliModelTercihi, ""), { announce: false });
    }
  } catch {
    // Tercih okunamadı: sunucunun varsayılan modeli geçerli kalıyor. Sessiz —
    // kullanıcı üretebiliyor, yalnız seçimi hatırlanmamış oluyor.
  }
}

syncFolderView();
loadFolders();
loadHistory();
loadSettings(true);
loadModelPref();
loadAssets("all");
loadAssets("logos");
loadAssets("mottos");
loadAssets("banners");
loadAssets("uploads");
// Palet varsayılan olarak KAPALI: açılışta öneri istenmez, prompt'a hiçbir
// şey eklenmez. Yalnızca kütüphane çekilir ki "Kayıtlı paletler" hazır olsun.
loadPalettes();
