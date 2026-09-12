// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
// Kromis — Azure ayarları (write-only) ve açılış çağrıları.
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

/** Kullanıcıyı Ayarlar'a yönlendiren ek — düğmenin ADIYLA, glifle DEĞİL.
 *  Öncesinde "(sağ üstteki ⚙)" yazıyordu ve iki kusuru vardı: (1) üst şeritteki
 *  gerçek düğme hatlı bir SVG dişli (index.html, `aria-label="Ayarlar"`), yani
 *  glif düğmenin görünüşünü YANLIŞ söylüyordu; (2) "emoji ikon yok" ölçütünü
 *  (flow-redesign §11) tartışmaya açıyordu.
 *  SABİT olmasının gerekçesi ayrı ve bir kusuru kapatıyor: aynı dize ÜÇ kez
 *  elle yazılıydı ve biri aşağıdaki `includes` NÖBETÇİSİ. Biri değişip öteki
 *  kalsa hata VERMEZ — nöbetçi bir daha hiç tutmaz ve kullanıcı ayarları
 *  düzelttikten sonra durum satırı ekranda kalırdı. */
const AYARLAR_EKI = "(sağ üstteki Ayarlar düğmesi)";

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
  // Video şeridi de AYNI yanıttan ve aynı gerekçeyle. İkinci bir gerekçe de
  // var: Veo görselin `GEMINI_API_KEY`ini PAYLAŞIYOR, yani iki şeridin
  // `configured` durumu tek bir olguya bakıyor — ayrı zamanlarda gelmeleri
  // kullanıcıya çelişen iki ekran gösterirdi.
  applyVideoModels(s, seciliVideoModeliTercihi);
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
    // Bayraklar SAKLANIYOR: kartlar pencere açıldığında çiziliyor ve o an
    // elde yalnız bu sözlük oluyor. Kaydet'ten sonra applyConfigured yeniden
    // koştuğu için rozetler de kendiliğinden tazeleniyor.
    saglayiciDurumu = s.providers;
    syncProviderPick($("set-provider").value);
  }

  // Açılış mesajı artık SEÇİLİ MODELE bakıyor, Azure'a değil: yalnızca OpenAI
  // anahtarı olan bir kullanıcıya "Azure ayarlarını gir" demek onu hiç
  // ihtiyacı olmayan bir forma yönlendirirdi.
  const kapali = goBlockReason();
  if (kapali) {
    statusEl.textContent = `${kapali} ${AYARLAR_EKI}`;
  } else if (statusEl.textContent.includes(AYARLAR_EKI)
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
  if (s && s.guncelleme !== undefined) uygulaGuncelleme(s.guncelleme);

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
  // `chat_instructions_path` / `chat_video_instructions_path` ARTIK
  // OKUNMUYOR: Ayarlar'daki "Prompt Yönetmeni · talimat" bölümü kaldırıldı
  // (11 Eylül 2026, kullanıcı kararı) — iki satır salt-okunur birer dosya
  // yolu gösteriyordu ve kullanıcının panelde yapabileceği bir şey yoktu.
  // Sunucu alanları döndürmeye devam ediyor (app.get_settings); yalnız
  // ekrandaki kopyaları gitti.
}

/** "Yeni sürüm çıktı" satırı + dişli düğmesindeki rozet — İKİ yüzey, TEK kaynak.
 *
 *  Satır tek başına yetmiyordu: Ayarlar modalının DİBİNDE duruyor, yani bildirim
 *  ancak paneli zaten açıp aşağı inen kişiye ulaşıyordu. Rozet dişlinin üstünde
 *  ve telefonda da görünür — mobile.css `.ver` pill'ini gizliyor, dişliyi
 *  gizlemiyor, yani mobilde yeni sürümü haber veren TEK yüzey bu.
 *
 *  İkisini iki ayrı yerde yazmak, birini güncellerken ötekini unutmanın
 *  kapısıydı: `[data-app-version]` seçicisinin çözdüğü sorunun aynısı. */
function uygulaGuncelleme(g) {
  const varMi = !!(g && g.surum);
  if (varMi) {
    $("settings-update-version").textContent = g.surum;
    if (g.url) $("settings-update-link").href = g.url;
  }
  $("settings-update").hidden = !varMi;

  // Rozet SALT GÖRSEL olamaz: nokta bir ekran okuyucuda hiç yok. Anlamı
  // düğmenin kendi adına giriyor — `title` fare kullanıcısına, `aria-label`
  // ötekine aynı cümleyi söylüyor.
  const dis = $("settings-btn");
  if (!dis) return;
  dis.classList.toggle("has-update", varMi);
  const etiket = varMi ? `Ayarlar — yeni sürüm var (v${g.surum})` : "Ayarlar";
  dis.title = etiket;
  dis.setAttribute("aria-label", etiket);
}

/** Açılıştaki cevap "bilmiyorum" ise güncelleme cevabını ARDINDAN yoklar.
 *
 *  NEDEN VAR: `/api/settings`'in ilk cevabı çoğu açılışta `null`dur — önbellek
 *  bayatsa `guncelleme.bilgi()` tazelemeyi arka plana atıp hemen dönüyor
 *  (guncelleme.py'nin 2. sözleşmesi: istek yolunu asla bekletme). O modül bunu
 *  "birkaç saniye sonrakinde gerçek cevap gelir" diye yazmıştı, ama bu dosyada
 *  `loadSettings` YALNIZ bir kez çağrılıyor: "sonraki" istek hiç gelmiyordu ve
 *  tazelenen cevap bir sonraki uygulama açılışına kadar diskte kalıyordu.
 *  Kullanıcı tarafından bakıldığında bu, bildirimin hiç gelmemesiyle aynı şey.
 *
 *  Gecikmeler arka plan kontrolünün ömrüne göre seçildi: GitHub çağrısının
 *  zaman aşımı 5sn (guncelleme.ZAMAN_ASIMI_SANIYE), yani 3sn normal cevabı,
 *  8sn yavaş ağı, 20sn zaman aşımına düşmüş kontrolün bıraktığı damgayı
 *  yakalıyor. İlk dolu cevapta duruyor; üç deneme bitince de duruyor —
 *  sonsuz yoklama, kullanıcının kapatamayacağı bir arka plan isteğidir.
 *
 *  `/api/settings` yeniden çağrılamaz: o yanıt `applyConfigured()` üzerinden
 *  formun tamamını yeniden yazar ve kullanıcının o sırada doldurduğu alanları
 *  ezerdi. Ayrı uç tam olarak bunun için var (bkz. app.py → get_guncelleme). */
const GUNCELLEME_YOKLAMA_MS = [3000, 8000, 20000];

async function yoklaGuncelleme(sira = 0) {
  if (sira >= GUNCELLEME_YOKLAMA_MS.length) return;
  await new Promise((r) => setTimeout(r, GUNCELLEME_YOKLAMA_MS[sira]));
  try {
    const { guncelleme } = await (await fetch("/api/guncelleme")).json();
    if (guncelleme && guncelleme.surum) {
      uygulaGuncelleme(guncelleme);
      return;                                   // bulundu: yoklama biter
    }
  } catch {
    // Sessiz: guncelleme.py'nin 1. sözleşmesinin ön yüzdeki karşılığı. Bir
    // sürüm kontrolünün kullanıcıya hata göstermesi, hiçbir şey kazandırmadan
    // çalışan uygulamayı bozuk gösterir.
  }
  yoklaGuncelleme(sira + 1);
}

async function loadSettings(openIfMissing) {
  try {
    const res = await fetch("/api/settings");
    const s = await res.json();
    applyConfigured(s);
    // Cevap henüz yoksa ardıl yoklama (gerekçe: yoklaGuncelleme'nin başlığı).
    // `s.guncelleme` doluysa gereksiz — üç istek, zaten bilinen bir cevap için.
    if (!s.guncelleme) yoklaGuncelleme();
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
    // Video kataloğu da boşalıyor, aynı gerekçeyle: eski bir listeyle kapı
    // açık kalırsa kullanıcı artık geçerli olmayan bir modelle dakikalarca
    // süren ve faturalanan bir üretim başlatmaya çalışır.
    videoModels = [];
    currentVideoModel = null;
    syncGoGate();
    statusEl.textContent = `Ayar durumu alınamadı. Sağlayıcı ayarlarını kontrol et ${AYARLAR_EKI}.`;
    if (openIfMissing) openSettings();
  }
}

/** Sağlayıcı bayrakları (`GET /api/settings` → `providers`). AYRI bir
 *  değişken çünkü kartlar pencere AÇILIRKEN çiziliyor, bayraklar ise
 *  `/api/settings` döndüğünde geliyor — iki ayrı zaman. `seciliModelTercihi`
 *  ile aynı desen. */
let saglayiciDurumu = {};

/** Seçicideki değer → `providers` sözlüğündeki kimlik. Azure'ın SEÇİCİ değeri
 *  `azure`, KİMLİĞİ `azure_image` ve ikisi aynı şey değil: eşitlemek rozeti
 *  Azure'da kalıcı olarak "kayıtlı değil" bırakırdı (aynı ayrım index.html'de
 *  `prov-azure` grubu için de yazılı). Ötekiler kendi adlarını kullanıyor, o
 *  yüzden tabloda yalnız istisna var. */
const SAGLAYICI_KIMLIGI = { azure: "azure_image" };

function saglayiciKayitli(deger) {
  return !!saglayiciDurumu[SAGLAYICI_KIMLIGI[deger] || deger];
}

/** Sağlayıcı işaretinin adresi — KATALOGDAN okunuyor, istemcide dize
 *  birleştirilmiyor. Adresi sunucu kuruyor (`app._provider_logo_url`, sürüm
 *  damgası dâhil) ve `setModelLogo`un gerekçesi burada da geçerli: yarın yeni
 *  bir sağlayıcı eklenince işaret kendiliğinden geliyor. İşareti olmayan
 *  sağlayıcıda `undefined` — kutu boş kalıyor (renderModelCards'ın kaçış
 *  yolunun aynısı). */
function saglayiciLogosu(deger) {
  const m = imageModels.find((x) => x.provider === deger);
  return m && m.logo;
}

/** Sağlayıcı penceresinin kartları. `<option>`lardan türüyor — ikinci bir
 *  sağlayıcı listesi yazmak, seçici ile pencerenin ayrışması demekti; kapı
 *  zaten `syncProviderFields`in okuduğu aynı değerler.
 *
 *  ROZET, kaldırılan #provider-status listesinin işini devralıyor: "hangisi
 *  kurulu?" sorusu artık seçimin yapıldığı YERDE cevaplanıyor, formun
 *  başındaki ayrı bir satırda değil. Kaynak aynı `providers` bayrakları, yani
 *  ikinci bir doğruluk kaynağı doğmuyor. */
function renderProviderCards() {
  const secici = $("set-provider");
  const kok = $("provider-list");
  const legend = kok.querySelector("legend");

  const kartlar = [...secici.options].map((o) => {
    const kart = document.createElement("label");
    kart.className = "radio-row model-row";

    const kutu = document.createElement("span");
    kutu.className = "model-row-ic";
    const logo = saglayiciLogosu(o.value);
    if (logo) {
      const img = document.createElement("img");
      img.src = logo;
      // `alt=""`: sağlayıcının adı kartın metninde ZATEN var.
      img.alt = "";
      kutu.append(img);
    }

    const metin = document.createElement("span");
    metin.className = "model-row-txt";
    const ad = document.createElement("b");
    // `textContent`: sunucudan gelen hiçbir şey innerHTML'e girmiyor.
    ad.textContent = o.textContent;
    const rozet = document.createElement("span");
    rozet.className = "model-row-badge";
    rozet.textContent = saglayiciKayitli(o.value) ? "kayıtlı" : "kayıtlı değil";
    ad.append(rozet);
    metin.append(ad);

    // GERÇEK RADYO: ok tuşu gezintisi, grup semantiği ve `:checked` durumu
    // tarayıcıdan geliyor (#model-sheet'in kendi kararı).
    const kutucuk = document.createElement("input");
    kutucuk.type = "radio";
    kutucuk.name = "provider-pick";
    kutucuk.value = o.value;
    kutucuk.checked = o.value === secici.value;

    kart.append(kutu, metin, kutucuk);
    return kart;
  });

  // `legend` YAYILARAK veriliyor: `replaceChildren(null, …)` argümanı dizeye
  // çevirip listenin tepesine "null" METNİ basardı (renderModelCards'ın notu).
  kok.replaceChildren(...(legend ? [legend] : []), ...kartlar);
}

/** Düğmenin görünen yüzü: seçili `<option>`un metni + sağlayıcı işareti.
 *  TEK YAZAR burası — adı ikinci bir yerden yazmak, `<select>`in değeriyle
 *  ekranda okunan adın ayrışmasına kapı açardı. */
function syncProviderPick(secili) {
  const secenek = [...$("set-provider").options].find((o) => o.value === secili);
  $("set-provider-label").textContent = secenek ? secenek.textContent : "Sağlayıcı seç";
  const kutu = $("set-provider-ic");
  const logo = saglayiciLogosu(secili);
  if (!logo) { kutu.replaceChildren(); return; }
  const img = document.createElement("img");
  img.src = logo;
  img.alt = "";
  kutu.replaceChildren(img);
}

/** Seçilen sağlayıcının alan grubunu gösterir, ötekileri gizler. */
function syncProviderFields() {
  const secili = $("set-provider").value;
  for (const p of ["azure", "openai", "gemini"]) {
    $(`prov-${p}`).hidden = p !== secili;
  }
  // Düğmenin yüzü BURADA tazeleniyor, seçim yapılan yerde değil: değer üç
  // yoldan değişebiliyor (pencere, derin bağlantı `openSettings(provider)`,
  // açılıştaki varsayılan) ve üçüne ayrı ayrı yazmak birini unutmak demekti.
  syncProviderPick(secili);
  syncChatDeployField(secili);
}

/** Dağıtım adı bölümü — BAŞLIK DAHİL — yalnızca onu isteyen sağlayıcıda.
 *
 * Kutu bir zamanlar koşulsuzdu: OpenAI ya da Gemini anahtarı girmeye gelen
 * kullanıcı, o sağlayıcılarda karşılığı OLMAYAN bir alan görüyordu ("dağıtım"
 * Azure'a özgü — ötekilerde model adı katalogda yazılı). Yanlış bir soru,
 * üstelik 360px'lik bir slide-over'da ödenmiş yer.
 *
 * SONRAKİ TUR BAŞLIĞI DA ALDI: kutu gizlenince yerine "bu sağlayıcıda dağıtım
 * adı yok" cümlesi geliyordu, yani kullanıcının yapacağı bir şey olmadığı hâlde
 * bölüm iki satır yer tutmaya devam ediyordu. Şimdi başlık (`chat-deploy-head`)
 * ve grup BİRLİKTE gizleniyor; o cümlenin elemanı (`chat-no-deploy-note`)
 * tümden kaldırıldı — gizli bir başlığın altında hiç görünemeyecek bir
 * paragraftı. Kaybolan bilgi yok: talimat dosyası yolu Ayarlar'da koşulsuz
 * duruyor ve sohbet modelinin nereden seçildiğini composer'ın üstündeki şerit
 * kendisi söylüyor.
 *
 * KAPI KATALOGDAN türetiliyor: `chat_models[].needs_deployment` bayrağı
 * `catalog.chat_needs_deployment`ten geliyor ve o da tek bir olguya bakıyor —
 * modelin adı ortamdan mı okunuyor. Sağlayıcı adını burada LİTERAL saymak,
 * adı ortamdan okunan ikinci bir sağlayıcı eklendiği gün bölümün sessizce
 * görünmez kalması demekti.
 *
 * FAIL-OPEN: katalog henüz gelmediyse (ilk çizim, ya da `/api/settings`
 * başarısız) bölüm GÖRÜNÜYOR. Tersi, ayar durumu alınamayan bir kullanıcının
 * dağıtım adını hiç giremeyeceği anlamına gelirdi — yani bugün çalışan tek
 * sağlayıcı kurtarılamaz olurdu.
 */
function syncChatDeployField(provider) {
  const isteyen = chatModels.length
    ? chatModels.some((m) => m.needs_deployment && m.provider === provider)
    : true;
  $("chat-deploy-head").hidden = !isteyen;
  $("chat-deploy-group").hidden = !isteyen;
  // GEZİNME DÜĞMESİ DE AYNI KAPIDA. Bölmeli düzenin getirdiği yeni kusur bu:
  // başlık ve grup gizlenince "Yönetmen" bölmesinde görünecek hiçbir şey
  // kalmıyor, ama düğme duruyordu — tıklanınca bomboş açılan bir bölme,
  // kaldırılan "bu sağlayıcıda dağıtım adı yok" cümlesinin daha kötü hâli.
  $("settings-nav-director").hidden = !isteyen;
  // Bölme O AN AÇIKSA geri düşüyor. Bugün bu satır bir kusuru DEĞİL bir
  // TUTARLILIĞI koruyor: seçici yalnız "Erişim" bölmesinde olduğu için
  // sağlayıcı Yönetmen açıkken çevrilemiyor, ve `openSettings` zaten
  // "Erişim"e dönüyor. Satırın işi kuralı bu fonksiyonun İÇİNDE tutmak —
  // "gezinme düğmesi gizliyse o bölme açık kalamaz" kararının iki ayrı yerde
  // yaşaması, ikisinin ayrışmasının kapısı olurdu (aynı gerekçe başlık ve
  // grubun birlikte gizlenmesinde de yazılı).
  if (!isteyen && acikBolme === "director") showSettingsPane("access");
}

$("set-provider").addEventListener("change", syncProviderFields);

// ── Bölmeler (sol gezinme) ──────────────────────────────────────────
// Ayarlar formu dört konu taşıyor ve hepsi tek kayan gövdedeydi: 19 blok,
// kullanıcının "çok karışık" dediği şey buydu. Bölmek bilgiyi silmiyor, AYNI
// ANDA GÖRÜNENİ azaltıyor.
//
// Açık bölmenin adı BİR DEĞİŞKENDE, DOM'dan okunarak DEĞİL: `syncChatDeployField`
// (yukarısı) "bölme şu an açık mı" sorusunu soruyor ve `hidden` özniteliklerini
// tarayan bir cevap, kapının kendisinin yazdığı özniteliği geri okumak olurdu.
let acikBolme = "access";

function showSettingsPane(ad) {
  acikBolme = ad;
  // `aria-current="false"` ARIA'da "geçerli değil" demek — `aria-pressed`in
  // #palette-tabs'taki kalıbının aynısı; öznitelik SİLİNMİYOR ki CSS seçicisi
  // (`.picker-nav-item[aria-current="true"]`) tek kuralla çalışsın.
  for (const dugme of $("settings-nav").querySelectorAll(".picker-nav-item")) {
    dugme.setAttribute("aria-current", String(dugme.dataset.pane === ad));
  }
  for (const bolme of document.querySelectorAll("#settings-modal .settings-pane")) {
    bolme.hidden = bolme.dataset.pane !== ad;
  }
}

// TEK dinleyici, olay yetkilendirmeyle (#model-sheet-list'in kalıbı): düğme
// başına bağ kurmak, bir gün beşinci bölme eklendiğinde sessizce eksik kalırdı.
$("settings-nav").addEventListener("click", (e) => {
  const dugme = e.target.closest(".picker-nav-item");
  if (dugme) showSettingsPane(dugme.dataset.pane);
});

// ── Sağlayıcı penceresi ─────────────────────────────────────────────
// Pencereyi açan düğme — odak ona iade edilecek. `.sheet`lerin `sheetTetik`i
// ve `.modal`ların `dialogPrevFocus`u ile aynı iş; ayrı bir değişken çünkü bu
// katman ikisinin de ÜSTÜNDE açılıyor ve onların kapanışıyla ilgisi yok.
let providerModalTetik = null;

function openProviderModal() {
  // Kartlar HER AÇILIŞTA yeniden çiziliyor: `providers` bayrakları Kaydet'ten
  // sonra değişiyor ve bayat bir liste, anahtarı yeni girilmiş bir sağlayıcıyı
  // "kayıtlı değil" diye gösterirdi (openModelSheet'in gerekçesinin aynısı).
  renderProviderCards();
  $("provider-modal").hidden = false;
  providerModalTetik = $("set-provider-btn");
  providerModalTetik.setAttribute("aria-expanded", "true");
  // Odak İŞARETLİ radyoya: ok tuşlarıyla gezinme ilk tuş basımında çalışsın.
  const isaretli = $("provider-list").querySelector("input:checked");
  setTimeout(() => (isaretli || $("provider-close")).focus(), 0);
}

function closeProviderModal() {
  if ($("provider-modal").hidden) return;
  $("provider-modal").hidden = true;
  if (providerModalTetik) {
    providerModalTetik.setAttribute("aria-expanded", "false");
    // `isConnected`: pencere Ayarlar kapanırken de kapatılabiliyor ve kopmuş
    // bir düğmeye odaklanmak odağı <body>ye atar (closeSheets'in aynı kontrolü).
    if (providerModalTetik.isConnected) providerModalTetik.focus();
  }
  providerModalTetik = null;
}

$("set-provider-btn").addEventListener("click", openProviderModal);
$("provider-close").addEventListener("click", closeProviderModal);
$("provider-modal").addEventListener("click", (e) => {
  if (e.target.hasAttribute("data-provider-close")) closeProviderModal();
});

// Seçim `<select>`e YÖNLENDİRİLİYOR, doğrudan uygulanmıyor: değerin tek sahibi
// o ve `change` dinleyicisi (syncProviderFields → alan grupları + dağıtım
// kapısı + düğmenin yüzü) oraya bağlı. Buradan ayrıca çağırmak o zincirin
// ikinci bir kopyası olurdu (#model-sheet-list'in kararı).
$("provider-list").addEventListener("change", (e) => {
  const secici = $("set-provider");
  // AYNI DEĞERE ikinci dokunuş sessiz: native <select> de değişmeyen bir değer
  // için `change` atmıyor.
  if (e.target.value && secici.value !== e.target.value) {
    secici.value = e.target.value;
    secici.dispatchEvent(new Event("change", { bubbles: true }));
  }
  // Kapanış SEÇİMİN KENDİSİ: üç satırlık bir listede ayrıca "Tamam"a basmak,
  // #model-sheet'in dipteki düğmesinin (başparmakla ulaşılan şerit) telefona
  // özgü gerekçesi olmadan ödenen fazladan bir tık olurdu.
  closeProviderModal();
});

// ESCAPE MUHAFIZI — YAKALAMA EVRESİNDE (`, true`) ve bu ŞART, üslup değil:
// core.js'teki `.sheet` dinleyicisi bu dosyadan ÖNCE kayıtlı, yani kabarma
// evresinde yazılan bir `stopImmediatePropagation` onu DURDURAMAZ ve tek
// Escape hem pencereyi hem arkasındaki Ayarlar'ı kapatırdı. Aynı desen
// folders.js'teki taşıma penceresi için de kurulu.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || $("provider-modal").hidden) return;
  e.stopImmediatePropagation();
  closeProviderModal();
}, true);

function openSettings(provider) {
  // Gizli alanların HEPSİ temizleniyor (write-only): kayıtlı anahtar hiçbir
  // zaman forma dolmuyor, o yüzden boş kutu "sildim" değil "dokunmadım"dır.
  $("set-openai-key").value = "";
  $("set-gemini-key").value = "";
  // Belirli bir sağlayıcıya derin bağlantı: #model-settings-link buradan
  // geliyor, "anahtar yok" uyarısı doğrudan doğru gruba açsın.
  //
  // İKİNCİ KAPI (`some`), çağıranın doğru davranmasına GÜVENMİYOR: eşleşmeyen
  // bir dizeyi `select.value`ya yazmak seçimi sessizce düşürüyor
  // (`selectedIndex = -1`) ve `syncProviderFields` o anda BÜTÜN alan
  // gruplarını gizliyor — panel boş açılıyor, konsolda hiçbir hata olmuyor.
  // #settings-btn'in bağı tam bu tuzağa düşmüştü (aşağıdaki gerekçe).
  // Katalogdan gelen bir sağlayıcı adı bir gün seçicide bulunmazsa da aynı
  // yol açılırdı, yani kapı çağıranın düzeltilmesiyle gereksizleşmiyor.
  if (provider && [...$("set-provider").options].some((o) => o.value === provider)) {
    $("set-provider").value = provider;
  }
  syncProviderFields();
  $("set-key").value = ""; // her açılışta boş (write-only)
  // #set-chat-deployment BİLEREK temizlenmiyor: write-only değil, GET'ten dolu
  // geliyor. Temizlenirse kullanıcı endpoint'ini güncellemek için paneli açıp
  // kaydettiğinde dağıtım adını da silmiş olurdu.
  $("settings-status").textContent = "";
  // Her açılış "Erişim"den başlıyor: pencere kapandığında bölme hatırlansa,
  // anahtarını girmeye gelen kullanıcı bir önceki turda baktığı "Hakkında"
  // bölmesiyle karşılanırdı. Derin bağlantı da (openSettings(provider)) zaten
  // bu bölmeyi hedefliyor.
  showSettingsPane("access");
  // Panel ALTTAN açılıyor (model seçicisiyle aynı yüzey). Açma/kapama tek
  // kapıdan (core.openSheet); perde ve Escape kabuğun ortak dinleyicilerinde.
  openSheet("settings-modal");
  // ODAK METİN KUTUSUNA DEĞİL SEÇİCİYE. Burada `#set-endpoint` vardı ve yüzey
  // alttan açılmaya başlayınca o satır bir kırılmaya dönüştü: bir metin
  // kutusuna odaklanmak Android'de klavyeyi AÇIYOR, klavye de `bottom: 0`a
  // yapışmış paneli olduğu gibi kapatıyor — yani Ayarlar her açılışta klavye
  // altında doğuyordu. `<select>`e odaklanmak klavyeyi açmıyor ve panelin ilk
  // kontrolü zaten o, yani sekme sırası ve Escape'in beklediği "odak panelin
  // içinde" koşulu korunuyor.
  //
  // İkinci kazanç: `#set-endpoint` YALNIZCA Azure seçiliyken görünür
  // (`syncProviderFields`). Gemini'ye derin bağlantıyla açıldığında
  // (#model-settings-link) odak gizli bir kutuya gidiyordu, yani hiçbir yere.
  setTimeout(() => $("set-provider-btn").focus(), 0);
}

// Sağlayıcı penceresi de kapanıyor: normalde perdesi Ayarlar'ı örttüğü için
// ikisi birlikte kapanmıyor, ama "Kaydet" 550ms sonra kendiliğinden kapatıyor
// (saveSettings) — o yolla açık bir pencere sahipsiz kalırdı.
function closeSettings() { closeProviderModal(); closeSheets(); }

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
                             // Adres alanı KOŞULSUZ gidiyor, gizli alanlarla
                             // aynı gerekçeyle: sunucu "alan yok" ile "boş"
                             // arasında ayrım yapıyor ve boş değer
                             // `default_base_url`ü olmayan kimlikte
                             // "dokunmadım" demek (app.post_settings). Yani
                             // yazılmış bir Foundry adresi bir sonraki
                             // kayıtta silinmiyor.
                             azure_foundry_base_url: $("set-foundry-url").value.trim(),
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

// SARMALAYICI ŞART, çıplak `openSettings` DEĞİL — ve bu ölçülmüş bir kırılmanın
// düzeltmesi. `addEventListener("click", openSettings)` fonksiyona MouseEvent'i
// ARGÜMAN olarak veriyor, yani `provider` truthy oluyor ve aşağıdaki satır
// koşuyordu:
//     if (provider) $("set-provider").value = provider;
// `select.value` eşleşmeyen bir dizeye ("[object MouseEvent]") atandığında
// tarayıcı seçimi DÜŞÜRÜYOR (`selectedIndex = -1`, `value = ""`) ve hemen
// ardından koşan `syncProviderFields` üç alan grubunun HEPSİNİ gizliyordu.
// Sonucu somut: dişliye basarak açılan Ayarlar panelinde HİÇBİR anahtar
// kutusu görünmüyordu — kullanıcı anahtarını yalnızca ilk kurulumun kendi
// açtığı panelden ya da "Ayarlar'ı aç" derin bağlantısından girebiliyordu.
// Konsolda tek bir hata bile yok; gerçek Chromium koşumunda görüldü.
$("settings-btn").addEventListener("click", () => openSettings());
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

/** Kullanıcının VİDEO modeli tercihi. `seciliModelTercihi`nin ikizi ve AYRI
 *  bir değişken: iki şerit iki listeden besleniyor ve tek değişkende tutmak,
 *  mod değiştiren kullanıcının seçimini karşı listede geçersiz kılardı
 *  (gerekçenin uzunu prefs.py'nin `video_model` girdisinde). */
let seciliVideoModeliTercihi = "";

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
    // Video tercihi GÖRSELDEN BAĞIMSIZ okunuyor — sohbet tercihinin aynı
    // gerekçesi: `image_model` boşsa erken dönmek video seçimini de sessizce
    // yutardı.
    if (p.video_model) {
      seciliVideoModeliTercihi = p.video_model;
      if (videoModels.length) {
        applyVideoModel(secilecek(videoModels, seciliVideoModeliTercihi, ""),
                        { announce: false });
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
// `uploads` ÇEKİLMİYOR çünkü ARTIK YOK: o türe hiçbir yükleme gitmiyordu ve
// panelde sekmesi de yoktu (bkz. assets.js UPLOAD_TARGET); eskiden oraya
// yazılmış varlıklar açılışta `logos`a göçüyor
// (assets_store.migrate_legacy_uploads). `/api/assets/all` bugün üç türü
// harmanlıyor, dördüncüsü kalmadı.
// Palet varsayılan olarak KAPALI: açılışta öneri istenmez, prompt'a hiçbir
// şey eklenmez. Yalnızca kütüphane çekilir ki "Kayıtlı paletler" hazır olsun.
loadPalettes();
