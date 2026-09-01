// Lumeo — üretim akışı: prompt, referans görseller, ilerleme, onay penceresi.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşır
// ve index.html'deki yükleme SIRASI bağlayıcıdır:
//   core.js → folders.js → assets.js → palette.js → settings.js → viewer.js → chat.js
// Her dosya yüklenirken yalnızca kendi DOM dinleyicilerini kurar; başka bir
// dosyadaki ada ancak olay anında dokunur — bu yüzden sıra TDZ hatası üretmez.
// Açılış çağrılarının tamamı settings.js'in dibinde toplanır.

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const ACCEPTED_UPLOAD_TYPES = ["image/png", "image/jpeg", "image/webp"];
// Aynı üç türün UZANTI karşılığı. `isAcceptedUpload`ın var oluş sebebi burada.
const ACCEPTED_UPLOAD_EXTS = [".png", ".jpg", ".jpeg", ".webp"];
// "Tür bildirilmedi" demenin iki yolu. Boş dize tarayıcının, octet-stream
// içerik sağlayıcısının "bilmiyorum"u — ikisi de dosya HAKKINDA bir şey
// söylemiyor, yani red için kanıt sayılmıyorlar.
const UNKNOWN_UPLOAD_TYPES = ["", "application/octet-stream", "binary/octet-stream"];

/** Seçilen dosya bu arayüzün kabul ettiği bir görsel mi?
 *
 * KURAL: red için KANIT gerekir. Kabul listesiyle eşleşen bir tür ya da uzantı
 * varsa dosya geçiyor; eşleşmiyorsa ancak dosya kendisi HAKKINDA bir şey
 * söylüyorsa (bildirilmiş bir tür ya da bir uzantı) reddediliyor. Hiçbir bilgi
 * yoksa son sözü sunucu söylüyor.
 *
 * NEDEN BÖYLE, TÜRE TEK BAŞINA GÜVENİLMİYOR: Android WebView `File.type`ı
 * ContentResolver'dan alıyor ve her sağlayıcı doğru MIME vermiyor — "Son
 * kullanılanlar", İndirilenler ve birçok bulut/OEM sağlayıcısı boş dize ya da
 * `application/octet-stream` döndürüyor; bazıları dosya adını uzantısız
 * veriyor. Yalnız türe bakan kapı o dosyaları "PNG, JPEG veya WebP bir görsel
 * seç" diye geri çeviriyordu — kullanıcı gerçekten PNG seçmiş olsa bile.
 * Masaüstünde HİÇ görünmüyor, çünkü yerel dosya diyaloğu türü her zaman doğru
 * bildiriyor; kusur bu yüzden yalnız "telefonda logo yüklenmiyor" olarak
 * görünüyordu.
 *
 * Kapının tümden kalkmaması da bilinçli: `.heic` bir fotoğrafı ya da bir PDF'i
 * ağa çıkmadan söylemek hâlâ daha iyi bir geri bildirim.
 *
 * SON SÖZ SUNUCUDA: `app._to_png` her yüklemeyi Pillow'la açıp doğruluyor ve
 * açılamayanı 422 + Türkçe cümleyle geri çeviriyor. Yani buradaki gevşeme
 * sunucuya geçersiz bir dosyanın SIZMASINA yol açmıyor.
 */
function isAcceptedUpload(file) {
  if (!file) return false;
  const tur = (file.type || "").trim().toLowerCase();
  const ad = (file.name || "").toLowerCase();
  if (ACCEPTED_UPLOAD_TYPES.includes(tur)) return true;
  if (ACCEPTED_UPLOAD_EXTS.some((uzanti) => ad.endsWith(uzanti))) return true;
  const karsiKanit = !UNKNOWN_UPLOAD_TYPES.includes(tur) || /\.[a-z0-9]{1,8}$/.test(ad);
  return !karsiKanit;
}


// Sunucudaki models.MAX_PROMPT_CHARS ile AYNI olmak zorunda (MAX_EDIT_IMAGES
// geleneği): yönetmenin ürettiği prompt buraya sığmıyorsa forma yazmak yerine
// kısaltılması isteniyor — sunucu aksi halde 422 döner.
const MAX_PROMPT_CHARS = 4000;

// ── Çalışma alanı sekmeleri ─────────────────────────────────────────
// Kabuk sorumluluğu, sohbete özel DEĞİL: bu yüzden chat.js'te değil burada.
// chat.js yalnızca showView("image") çağırıyor, böylece sadece kendinden
// önceki dosyalara bakan bir yaprak kalıyor ve yükleme sırası bozulmuyor.
let currentMode = "image";
// Ray bölümü: "studio" (tek döküm) | "media" (galeri) | "library" (bindirme varlıkları) | "tools" (görünüm + paletler).
let currentSection = "studio";

/** Bitişik segmentin kayan dolgusu: aktif düğmenin ölçüsünden okunuyor. */
function syncTabThumb() {
  const thumb = $("view-tabs-thumb");
  const tab = currentMode === "image" ? $("tab-image") : $("tab-chat");
  if (!thumb || !tab) return;
  thumb.style.width = `${tab.offsetWidth}px`;
  thumb.style.transform = `translateX(${tab.offsetLeft}px)`;
}

/** Kutunun yer tutucusu: mod × (ilk gönderim oldu mu).
 *
 * KISA HÂL bir sadeleştirme DEĞİL, bir gerekliliğin de karşılığı: telefonda
 * (390px) uzun metin İKİ SATIRA sarıyor ve boş bir textarea'nın `scrollHeight`i
 * yer tutucuyu de kapsıyor — yani `autoGrow` kutuyu 57px'e sabitliyordu ve
 * `rows` ne yazarsa yazsın küçülme GÖRÜNMÜYORDU (Chromium 390×844'te ölçüldü).
 * Uzun metnin işi zaten ilk kez yazana yol göstermek; gönderdikten sonra
 * kalıcı bir talimat olarak durması, kullanıcının kaldırılmasını istediği
 * "gereksiz yazı"nın ta kendisi.
 */
const PROMPT_YER_TUTUCU = {
  image: {
    tam: "Ne üretmek istiyorsun? Görsel tarifi, renk veya tarz yaz…",
    kisa: "Ne üretmek istiyorsun?",
  },
  director: {
    tam: "Yönetmen'e sor veya fikir danış… (öğeleri değiştir, sahne ekle)",
    kisa: "Yönetmen'e sor…",
  },
};

/** Yer tutucunun TEK yazarı. İki çağıranı var (mod değişimi ve ilk gönderim)
 * ve ikisi de aynı iki değişkeni okuyor — metin iki yerde kurulsaydı ayrışırdı.
 */
function syncPromptPlaceholder() {
  const prompt = $("prompt");
  if (!prompt) return;
  const metin = PROMPT_YER_TUTUCU[currentMode] || PROMPT_YER_TUTUCU.image;
  prompt.placeholder = $("composer").dataset.sent ? metin.kisa : metin.tam;
}

function setMode(modeName) {
  const mode = modeName === "director" ? "director" : "image";
  if (currentSection !== "studio") showSection("studio");
  currentMode = mode;
  $("composer").dataset.mode = mode;
  $("tab-image").setAttribute("aria-pressed", mode === "image" ? "true" : "false");
  $("tab-chat").setAttribute("aria-pressed", mode === "director" ? "true" : "false");
  $("tab-image").classList.toggle("active", mode === "image");
  $("tab-chat").classList.toggle("active", mode === "director");

  syncPromptPlaceholder();
  renderSource();
  syncTabThumb();
  // Kapı MODA bağlı: Yönetmen modunda sohbet yapılandırması, Görsel modunda
  // seçili modelin durumu karar veriyor. Mod değişince yeniden sorulmalı.
  // `typeof` guard'ı SIRA yüzünden: setMode bu dosyanın üst düzeyinde de
  // çağrılabiliyor ve syncGoGate aşağıda tanımlı (function bildirimi hoisted
  // ama `currentModel` gibi `let`ler değil) — bkz. dosya başındaki not.
  if (typeof syncGoGate === "function") syncGoGate();
}

$("tab-image").addEventListener("click", () => setMode("image"));
$("tab-chat").addEventListener("click", () => setMode("director"));
window.addEventListener("resize", syncTabThumb);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncTabThumb);

// ══ Flow kabuğu ══════════════════════════════════════════════════════
const APP = document.querySelector(".app");

// Ray bölümü → görünüm eşlemesi.
const SECTION_VIEWS = { studio: "view-studio", media: "view-media",
                        library: "view-library", tools: "view-tools" };

function showSection(name) {
  currentSection = name;
  const studio = name === "studio";
  for (const [key, viewId] of Object.entries(SECTION_VIEWS)) {
    if (viewId && $(viewId)) $(viewId).hidden = key !== name;
  }
  if ($("composer")) $("composer").hidden = !studio;
  for (const key of Object.keys(SECTION_VIEWS)) {
    const el = $(`rail-${key}`);
    if (!el) continue;
    const on = key === name;
    el.classList.toggle("active", on);
    if (on) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  }
  if (studio) syncTabThumb();
}

// ══ Android donanım/jest geri tuşu ══════════════════════════════════
//
// MainActivity.kt'nin `onBackPressed`i YALNIZ bunu çağırıyor. `true` = "ele
// aldım", `false` = "uygulamadan çıkılabilir" (Kotlin o noktada çıkış uyarısını
// gösteriyor).
//
// NEDEN BURADA, Kotlin'de değil: sıralama eskiden Kotlin'in içine gömülü ÜÇ CSS
// seçicisiydi (`.sheet.open`, `.modal:not([hidden])`, `.popover:not([hidden])`)
// ve index.html'in yapısına dizeyle bağlıydı — koruyan hiçbir test yoktu. İki
// somut kırılma üretmişti:
//   • sohbet menüleri (`.chat-menu`, `#chats-kebab-menu`) üç seçicinin
//     HİÇBİRİNE uymuyor, yani menü açıkken geri uygulamayı kapatıyordu,
//   • bölüm ve klasör gezintisi geri yığınında hiç yok (showSection ve
//     folders.js `goUp` geçmişe girmiyor), yani Medya'dayken ya da iç içe bir
//     klasördeyken geri DOĞRUDAN çıkışa gidiyordu.
// Karar JS'e taşınınca hem ikisi de kapandı hem sözleşme test edilebilir bir
// yere geldi (tests/test_mobile.py).
//
// `webView.canGoBack()` hâlâ KULLANILMIYOR: bu tek sayfalık bir uygulama,
// modal ve paneller gezinme geçmişine hiç girmiyor.
window.geriTusu = function () {
  // 1) Açık katman. Hangisinin kapanacağına KARIŞILMIYOR: var olan Escape
  //    şelalesi (core.js aşağısı, folders.js, assets.js, viewer.js) önceliği
  //    `stopImmediatePropagation` ile zaten çözüyor. Burada ikinci bir öncelik
  //    sırası kurmak iki mantığın ayrışmasına ve "geri bazen yanlış paneli
  //    kapatıyor" hatasına açık olurdu.
  const acik = document.querySelector(".sheet.open")
            || document.querySelector(".modal:not([hidden])")
            || document.querySelector(".popover:not([hidden])")
            || document.querySelector(".chat-menu:not([hidden])")
            || document.querySelector("#chats-kebab-menu:not([hidden])");
  if (acik) {
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", bubbles: true, cancelable: true,
    }));
    return true;
  }

  // 2) Klasörden bir üste. `goUp()`u ikinci bir çağrandan çağırmak yerine var
  //    olan düğme tıklanıyor (folders.js): kırıntı ve başlık tazelemesi böylece
  //    bedava geliyor ve tek yol kalıyor.
  //
  //    `currentSection === "media"` MUHAFAZASI ŞART, süs değil. Düğmenin
  //    `hidden`i yalnız `currentFolder`ı anlatıyor (folders.js `syncFolderView`)
  //    ve `showSection` onu HİÇ temizlemiyor: bir alt klasördeyken Stüdyo'ya
  //    geçip geri basmak, GÖRÜNMEYEN bir düğmeyi tıklayıp `true` döndürüyordu —
  //    ekranda hiçbir şey olmuyor, üstelik çıkış yolu klasör yığını boşalana
  //    kadar erişilemez kalıyordu. Arama açıkken de aynısı: `.gallery-head`
  //    tümden gizli ama düğmenin kendi `hidden`i hâlâ `false`.
  const klasorGeri = $("folder-back");
  if (currentSection === "media" && klasorGeri && !klasorGeri.hidden) {
    klasorGeri.click();
    return true;
  }

  // 3) Stüdyo dışı bir bölüm → Stüdyo.
  if (currentSection !== "studio") {
    showSection("studio");
    return true;
  }

  return false;
};

$("rail-studio").addEventListener("click", () => showSection("studio"));
$("rail-media").addEventListener("click", () => showSection("media"));
// A1/A2 (Adım 7b): Kütüphane ve Araçlar artık kendi görünümleri. Eskiden
// library-btn / palette-btn'e programatik .click() atılıyordu — kapalı bir
// panelin gizli düğmesi. Kütüphane grid'inin tazelenmesi assets.js'te
// (aynı düğmeye ikinci dinleyici, plus-menü kalıbı).
$("rail-library").addEventListener("click", () => showSection("library"));
$("rail-tools").addEventListener("click", () => showSection("tools"));

$("rail-collapse").addEventListener("click", () => {
  const on = APP.classList.toggle("rail-collapsed");
  $("rail-collapse").setAttribute("aria-pressed", on ? "true" : "false");
  syncTabThumb(); // composer genişliği değişti → kayan dolgu yeniden ölçülmeli
});

// ── Slide-over'lar ──
// Odağı iade edecek düğme (#model-btn ya da #chat-model-btn). BURADA
// tanımlanıyor, panelin kendi bölümünde değil: `closeSheets` bu dosyanın
// başında ve bir `let`e 500 satır ileriden bakmak, TDZ'ye takılmasa bile
// okuyanı yanıltır. Yazan yer `openModelSheet` (aşağıda), okuyan yer
// `closeSheets` — ikisinin ORTAK durumu, o yüzden ortak sahibi de yok.
let modelSheetTetik = null;

function closeSheets() {
  for (const el of document.querySelectorAll(".sheet.open")) el.classList.remove("open");
  $("chat-sidebar-toggle").setAttribute("aria-expanded", "false");
  $("specs-btn").setAttribute("aria-expanded", "false");
  // ODAK İADESİ. `closeSheets` kapanışın TEK kapısı (× düğmesi, "Tamam",
  // perde, Escape, Android geri tuşu hepsi buraya düşüyor), yani iadenin de
  // tek yeri burası — beş çağıranın her birine ayrı ayrı yazmak, birini
  // unutmak demekti. `isConnected` şart: kart listesi yeniden çizilirken
  // tetikleyici DOM'dan düşmüş olabilir ve kopmuş bir düğüme odaklanmak
  // odağı `<body>`ye atar (chat.js'in menü deseninin aynı kontrolü).
  //
  // `aria-expanded` DE buradan sıfırlanıyor, aynı değişkenden. Öncesinde iki
  // çip (#model-btn, #chat-model-btn) elle sayılıyordu ve o liste üçüncü
  // eksen (arena) eklenince bayatladı: #arena-btn kapanışta sıfırlanmıyor,
  // yani ekran okuyucu KAPALI bir paneli açık okuyordu. Tetikten okumak
  // listeyi tümden kaldırıyor — dördüncü eksen kendiliğinden kapsanıyor.
  // Kopmuş bir düğüme yazmak zararsız, o yüzden `isConnected` yalnız odakta.
  if (modelSheetTetik) {
    modelSheetTetik.setAttribute("aria-expanded", "false");
    if (modelSheetTetik.isConnected) modelSheetTetik.focus();
  }
  modelSheetTetik = null;
}

// Panel açmanın TEK kapısı: dört panel aynı perdeyi ve aynı sağ/sol şeridi
// paylaşıyor — önce hepsi kapanır, sonra istenen açılır. İkisi birlikte
// açılırsa üst üste biner ve `Esc`in hangisini kapattığı belirsizleşir.
function openSheet(id) {
  closeSheets();
  $(id).classList.add("open");
}

$("specs-btn").addEventListener("click", () => {
  const willOpen = !$("specs-sheet").classList.contains("open");
  closeSheets();
  if (willOpen) {
    openSheet("specs-sheet");
    $("specs-btn").setAttribute("aria-expanded", "true");
  }
});
$("specs-close").addEventListener("click", closeSheets);
$("sessions-close").addEventListener("click", closeSheets);
$("shell-scrim").addEventListener("click", closeSheets);
// `confirm-modal` guard'ı ŞART: onay penceresi bir panelin ÜSTÜNDE açılıyor
// (palet kaydetme). Bu dinleyici confirm'in stopImmediatePropagation'ından
// ÖNCE kayıtlı, yani o çağrı bunu durduramaz — guard'sız tek Escape iki
// katmanı birden kapatırdı.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("confirm-modal").hidden && document.querySelector(".sheet.open")) closeSheets();
});

// ── (+) menüsü ──
$("plus-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  const open = $("plus-menu").hidden;
  $("plus-menu").hidden = !open;
  $("plus-btn").setAttribute("aria-expanded", open ? "true" : "false");
});
function closePlusMenu() {
  $("plus-menu").hidden = true;
  $("plus-btn").setAttribute("aria-expanded", "false");
}
document.addEventListener("click", (e) => {
  if (!e.target.closest(".plus-wrap")) closePlusMenu();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePlusMenu(); });
// Menüdeki düğmeler kendi dinleyicilerini folders.js'te kuruyor; burada yalnız
// menünün kapanması eklenir (aynı düğümde birden çok dinleyici sorun değil).
// media-pick-btn de burada: menü kapanmazsa modalın ARKASINDA açık kalıyor
// (ikisi de position:fixed, popover z-index'i modalınkinin altında) — plan B10.
for (const id of ["upload-btn", "extra-add-btn", "media-pick-btn"]) {
  $(id).addEventListener("click", closePlusMenu);
}

// ── Model kaydı ve yeteneğe göre kontroller ──
//
// Buradaki durum core.js'te yaşamak ZORUNDA: `syncSpecs()` bu dosyanın en
// üst düzeyinde çağrılıyor, yani aşağıdaki fonksiyonlar core.js YÜKLENİRKEN
// tanımlı olmalı. Ayrı bir dosyaya konsa ve core.js'ten SONRA yüklense
// üst düzey çağrı `const` bir tanıma çarpıp TDZ ReferenceError verirdi —
// dosyanın başındaki yükleme-sırası notunun tam olarak uyardığı kırılma.
// ÖNCE yüklenmesi de olmaz: orada `$` henüz tanımlı değil.
//
// TARİHÇE: burada `SIZE_RATIO` adında bir sabit vardı ve
// `azure_client.ALLOWED_SIZES`'ın elle tutulan bir AYNASIYDI. Çoklu modelde o
// ayna kaçınılmaz olarak bayatlar (Gemini'nin jetonları `WxH` biçiminde bile
// değil, doğrudan `16:9`). Artık oran da etiket de sunucudan geliyor:
// GET /api/settings → image_models[].sizes[].{value,label,ratio}.
let imageModels = [];      // sunucudan gelen katalog
let currentModel = null;   // seçili tanım (imageModels'ten bir öğe)
let runBusy = false;       // üretim sürüyor mu — #go kapısının bir girdisi
// Yönetmenin karşılığı: aynı yuvada, aynı desende (bkz. applyChatModels).
// Burada yaşamak ZORUNDA çünkü `goBlockReason` bu dosyanın üst düzeyinde
// çağrılan `syncGoGate` üzerinden ikisini de okuyor ve chat.js EN SONDA
// yükleniyor — orada tanımlansa açılıştaki ilk çağrı TDZ hatası verirdi.
let chatModels = [];       // sunucudan gelen sohbet kataloğu
let currentChatModel = null;

/** `<select>`i sunucudan gelen seçeneklerle yeniden kurar ve DEĞERİ TAŞIR.
 *
 * Taşıma sırası önemli ve üç kademeli:
 *   1. Birebir aynı `value` yeni modelde de varsa korunur — sessiz, çünkü
 *      kullanıcı için hiçbir şey değişmedi.
 *   2. Aynı `ratio` varsa ona geçilir (1024x1536 → 896x1344 gibi): kullanıcının
 *      seçtiği şey ORAN'dı, piksel sayısı sağlayıcının işi. Bu da sessiz.
 *   3. Hiçbiri yoksa modelin varsayılanına düşülür ve bu YÜKSEK SESLE söylenir.
 *
 * 3. kademe "sessiz sapma yasak" duruşunun devamı: palet sığmadığında
 * (`applied:false`) ve yönetmenin önerisi uygulanamadığında da aynısı yapılıyor.
 * Söylenmezse kullanıcı formda başka bir ayar görür ve sonucu açıklayamaz.
 */
function fillAxis(selectId, options, desired, fallback) {
  const el = $(selectId);
  const onceki = desired !== undefined ? desired : el.value;
  const oncekiRatio = [...el.options].find((o) => o.value === onceki)?.dataset.ratio;

  el.replaceChildren(...options.map((opt) => {
    const o = document.createElement("option");
    o.value = opt.value;
    // `textContent`: etiket sunucudan geliyor ve sunucu metni DOM'a yalnız bu
    // kapıdan giriyor (dosya genelindeki duruş).
    o.textContent = opt.label;
    if (opt.ratio) o.dataset.ratio = opt.ratio;
    return o;
  }));

  if (options.some((o) => o.value === onceki)) { el.value = onceki; return null; }
  const ayniOran = oncekiRatio && options.find((o) => o.ratio === oncekiRatio);
  if (ayniOran) { el.value = ayniOran.value; return null; }
  el.value = fallback;
  // Eski değer zaten boşsa (ilk çizim) bildirilecek bir sapma yok.
  return onceki ? onceki : null;
}

/** Bir eksenin kullanıcıya görünen adı. chat.js'in atlanan-öneri metni bunu
 * kullanıyor: aynı eksen bir modelde "Boyut", başkasında "Oran". */
function axisLabel(key) {
  const el = $(`label-${key}`);
  return el ? el.textContent.trim() : key;
}

/** Seçili modelin kredi maliyeti: model × boyut/kalite × adet.
 *
 * Kredi bilgisi ŞİMDİLİK yalnız METADATA — bakiye yok, satın alma yok,
 * zorlama yok. Gerçek bakiye geldiğinde değişecek yer TEK: aşağıdaki metne
 * " · N kalan" ekleniyor ve goBlockReason'a bir satır giriyor.
 *
 * Tarife SUNUCUDAN geliyor; istemci yalnız anahtar kuruyor, fiyat mantığı
 * kurmuyor — yoksa aynı hesap iki yerde birden yaşardı.
 */
function syncRunCost() {
  const el = $("run-cost");
  // ARENA: turun toplamı, çünkü kullanıcı tek bir düğmeye basıp N modeli
  // birden ödüyor. Tarife yine tek kaynaktan (`arenaSutunlari`), yani
  // gösterilen fiyat ile gönderilen istek aynı çeviriyi kullanıyor.
  if (arenaAcik) {
    const sutunlar = arenaSutunlari();
    if (!sutunlar.length) { el.hidden = true; return; }
    const toplam = sutunlar.reduce((t, s) => t + (s.birim || 0), 0);
    el.textContent = `≈ ${toplam} kredi · ${sutunlar.length} model`;
    el.hidden = false;
    return;
  }
  if (!currentModel) { el.hidden = true; return; }
  const tarife = currentModel.credits_by_quality || {};
  const birim = tarife[$("quality").value] ?? currentModel.credits;
  if (birim === undefined || birim === null) { el.hidden = true; return; }
  // `≈` bilerek: bu bir fatura değil, metadata — tilde bunu bir paragraf
  // açıklama yazmadan söylüyor.
  el.textContent = `≈ ${birim * Number($("n").value || 1)} kredi`;
  el.hidden = false;
}

/** #go'nun engel SEBEBİ — boş dize "engel yok".
 *
 * Bu fonksiyon `#go.disabled`ın TEK yazarı olmak için var. Öncesinde dört ayrı
 * yerden yazılıyordu (core.js iki, settings.js iki) ve chat.js beşinci bir
 * mantık taşıyordu; yani şimdiden iki çelişen sahip vardı. N sağlayıcıda bu
 * sürdürülemez.
 *
 * Sebep `title`'a da yazılıyor: kilitli bir düğmenin neden kilitli olduğunu
 * saklamak, #chat-gate'in reddettiği şeyin aynısı.
 */
function goBlockReason() {
  if (runBusy) return "Üretim sürüyor…";
  if (currentMode === "director") {
    // Görsel dalının AYNI kademeleri. Öncesinde tek bir `chatConfigured`
    // boolean'ı vardı ve o yalnız AZURE'u ölçüyordu: yalnızca Gemini anahtarı
    // olan bir kullanıcıda yönetmen ölü bir düğmeyle açılırdı — `#go` kapısının
    // görsel tarafında v0.6'da düzeltilen kırılmanın aynısı.
    if (!chatModels.length) return "Sohbet modeli listesi alınamadı.";
    // Liste DOLU ama seçim yok ⇒ hiçbirinin kimliği kayıtlı değil. Bu, filtre
    // anahtarsız modelleri gizlemeye başladığından beri ULAŞILABİLİR bir hâl
    // ve "seçilmedi" demek kullanıcıya yanlış bir iş verirdi (seçecek bir şey
    // yok); doğru iş Ayarlar'da.
    if (!currentChatModel) {
      return "Kayıtlı sohbet kimliği yok — Ayarlar'dan ekle.";
    }
    if (!currentChatModel.configured) {
      return `${currentChatModel.label} için kimlik yok — Ayarlar'dan ekle.`;
    }
    return "";
  }
  if (!imageModels.length) return "Model listesi alınamadı.";
  // Yönetmen dalının aynı gerekçesi (yukarısı).
  if (!currentModel) return "Kayıtlı API anahtarı yok — Ayarlar'dan ekle.";
  if (!currentModel.configured) {
    return `${currentModel.label} için anahtar yok — Ayarlar'dan ekle.`;
  }
  if (source && !currentModel.supports_edit) {
    return `${currentModel.label} referans görselle çalışmıyor.`;
  }
  if (arenaAcik) {
    // Kapının sebebi yazılı: tek modelli bir arena sessizce sıradan bir
    // üretime dönüşseydi kullanıcı karşılaştırma beklerken tek sonuç alırdı.
    const idler = arenaSecimi();
    if (idler.length < ARENA_MIN) return `Arena için en az ${ARENA_MIN} model seç.`;
    // Sessizce sıradan bir düzenlemeye düşmek YASAK (uygulamanın genel
    // duruşu): kullanıcı arena açıkken referans eklerse ne olacağını
    // görmeli. Düzenleme arenası bilinçli olarak kapsam dışı.
    if (source) return "Arena düzenlemeyle çalışmıyor — referansı kaldır.";
    const anahtarsiz = idler
      .map((id) => imageModels.find((m) => m.id === id))
      .filter((m) => m && !m.configured);
    if (anahtarsiz.length) {
      return `${anahtarsiz[0].label} için anahtar yok — Ayarlar'dan ekle.`;
    }
  }
  return "";
}

/** Klavye kısayolu, #go'nun `title`ında.
 *
 * Bir zamanlar composer'ın dibinde kalıcı bir şeritti (`.chat-hint`) ve
 * kullanıcı isteğiyle kaldırıldı — ama BİLGİ kaldırılmadı, taşındı. Buraya,
 * çünkü kısayolun yaptığı iş tam olarak bu düğmenin işi; ikinci bir yazar
 * doğmuyor (`title`ın tek sahibi `syncGoGate`).
 *
 * Eylem adı düğmenin KENDİ metninden okunuyor, burada ikinci kez KURULMUYOR:
 * `renderSource` o metni dört ayrı duruma göre yazıyor ("Üret" · "Gönder" ·
 * "Görseli düzenle" · "Görselleri birleştir") ve burada sabit bir "Üret"
 * yazmak, referans eklenmiş bir composer'da yanlış bir ipucu demekti.
 */
const GO_KISAYOL = "⌘/Ctrl + Enter";

// Şeridin İKİNCİ kısayolu. Bir tur boyunca hiçbir yerde yazmıyordu: şerit
// kalkarken yalnız ⌘/Ctrl+Enter #go'ya taşınmış, mod değiştirme kısayolu
// (aşağıda, document keydown) çalışır hâlde ama KEŞFEDİLEMEZ kalmıştı —
// yazmayan bir kısayol pratikte yok demektir. Yeri mod düğmeleri, çünkü
// kısayolun yaptığı iş tam olarak o düğmelere basmak; ikisi bir arada
// duruyor ki "iki dosyada iki ad" kayması doğmasın.
const MOD_KISAYOL = "⌘/Ctrl + J";
$("tab-image").title = `Görsel modu · ${MOD_KISAYOL}`;
$("tab-chat").title = `Yönetmen modu · ${MOD_KISAYOL}`;

function syncGoGate() {
  const sebep = goBlockReason();
  // `$("go")` bir yerel değişkene ALINMIYOR ve bu bir üslup tercihi değil:
  // tests/test_id_contract.py `#go.disabled`ın TEK yazarını satır metninden
  // arıyor (`'("go").disabled'`) — takma ad, tripwire'ı sessizce kör eder.
  $("go").disabled = !!sebep;
  // Kilitliyken SEBEP yazılıyor, kısayol değil: çalışmayan bir düğmenin
  // kısayolunu duyurmak, kilidin neden orada olduğunu saklamak olurdu
  // (#chat-gate'in reddettiği şeyin aynısı).
  $("go").title = sebep
    || `${$("go").textContent.trim()} · ${GO_KISAYOL}`;
}

/** Şeridin sağlayıcı işaretini seçili modele göre çizer.
 *
 * TEK yardımcı, iki şerit: görsel ve sohbet aynı alanı (`logo`) okuyor ve adres
 * SUNUCUDAN geliyor (`app._provider_logo_url`) — istemcide sağlayıcı adı
 * sayılmıyor, dize birleştirilmiyor. Gerekçe `settings.js`in dağıtım kutusu
 * kapısıyla aynı: yarın yeni bir sağlayıcı eklendiğinde işaret kendiliğinden
 * geliyor, kimsenin burada bir liste güncellemesi gerekmiyor.
 *
 * `src` YALNIZ DEĞİŞİNCE yazılıyor: aynı adresi yeniden atamak Chromium'da
 * yeni bir istek doğurmuyor ama `hidden`ı her `applyModel` çağrısında (eksen
 * doldurma, tercih yükleme, katalog tazeleme) oynatmak gereksiz bir yeniden
 * çizim demekti.
 *
 * İşareti OLMAYAN model sessizce işaretsiz çiziliyor: `catalog.provider_logo`
 * None döndürebiliyor ve bir logo eksikliği şeridi bozmamalı. Eksikliği
 * yüksek sesle söyleyen yer test (tests/test_provider_logos.py).
 */
function setModelLogo(imgId, model) {
  const img = $(imgId);
  const src = (model && model.logo) || "";
  if (src && img.getAttribute("src") !== src) img.setAttribute("src", src);
  img.hidden = !src;
}

/** `#n` ekseninin seçenekleri: 1..max_n.
 *
 * Tek yerde, çünkü İKİ çağıranı var — `applyModel` ve arena kapanışındaki geri
 * açma (`arenaUygula`). İki kopyadan biri modelin tavanını unutabilirdi.
 */
function adetSecenekleri(model) {
  return Array.from({ length: model.max_n },
                    (_, i) => ({ value: String(i + 1), label: String(i + 1) }));
}

/** Seçili modeli uygular: eksenleri doldurur, notu yazar, tercihi kaydeder. */
function applyModel(id, { announce = true } = {}) {
  const model = imageModels.find((m) => m.id === id);
  // BOŞ HÂL: kullanılabilir model yok (anahtarsız modeller artık listelenmiyor).
  // Erken çıkış TEK BAŞINA yetmiyordu — çip "Modeller yükleniyor…"da donuyor ve
  // kullanıcı sonsuza kadar yüklenen bir şerit görüyordu. `currentModel` de
  // sıfırlanıyor, yoksa katalog daralınca ESKİ model seçili sanılırdı.
  if (!model) {
    if (!id) { currentModel = null; modelBosHali("image"); }
    return;
  }
  currentModel = model;
  // ŞERİT SEÇİLİ MODELİ HER ZAMAN İÇERİYOR. Bu satır `applyModels` dışındaki
  // çağıranlar için: `loadModelPref` katalog geldikten sonra tercihi uyguluyor
  // ve o tercih filtrelenmiş olabilir (anahtarı yok). O durumda `select.value`
  // seçenekler arasında bulunmaz, <select> BOŞ görünür ve şerit "model yok"
  // der — üretim ise çalışır. Yeniden çizim id'yi zorunlu tutuyor.
  if (![...$("model").options].some((o) => o.value === id)) {
    renderModelOptions(id);
  }
  $("model").value = model.id;
  // Çipin işareti + metni + panelin radyosu tek yerden (aşağısı).
  syncModelChip("image", model);

  const dusenler = [];
  const s = fillAxis("size", model.sizes, undefined, model.default_size);
  if (s) dusenler.push(`${axisLabel("size")} ${s}`);
  const q = fillAxis("quality", model.qualities, undefined, model.default_quality);
  if (q) dusenler.push(`${axisLabel("quality")} ${q}`);
  const nn = fillAxis("n", adetSecenekleri(model), undefined, "1");
  if (nn) dusenler.push(`${axisLabel("n")} ${nn}`);

  // `quality_hidden` beyan eden model: satır tümden gizleniyor. Tel üzerinde
  // yine geçerli bir jeton gidiyor — katalogdaki sentetik "standard".
  // Örnek olarak burada "Gemini" yazıyordu ve YANLIŞTI: Nano Banana'nın
  // çözünürlük ekseni var (1K/2K/4K) ve fiyatı da onunla değişiyor, yani
  // gizlenmesi gereken bir eksen değil — `image_size` jetonları `qualities`
  // olarak geliyor ve satır GÖRÜNÜYOR.
  $("spec-quality").hidden = !!model.quality_hidden;
  // Eksenin ADI modele göre değişiyor: piksel boyutu seçen model "Boyut",
  // oran seçen model "Oran" diyor. chat.js'in atlanan-öneri metni buradan okuyor.
  $("label-size").textContent =
    model.sizes.some((o) => o.value.includes("x")) ? "Boyut" : "Oran";

  // Şerit YALNIZCA EYLEM GEREKTİĞİNDE açılıyor: anahtar eksikse.
  //
  // Modelin tanıtım notu (`model.note`) buraya KONMUYOR ve bu ölçülmüş bir
  // karar: 360px'de o not 36px yer kaplıyor ve `--composer-h` üzerinden
  // tuvalin alt boşluğunu KALICI olarak yiyor — üstelik varsayılan modelde,
  // yani kullanıcının hiçbir şey yapmasını gerektirmeyen durumda. Bilgi
  // seçicinin `title`ında yaşıyor (aşağıda, renderModelOptions); eylem
  // gerektiren tek durum burada.
  const not = $("model-note");
  if (model.configured) {
    not.hidden = true;
  } else {
    $("model-note-text").textContent =
      `${model.label} için API anahtarı kayıtlı değil.`;
    not.hidden = false;
  }

  syncSpecs();
  syncRunCost();
  syncGoGate();
  if (announce && dusenler.length) {
    statusEl.textContent = `${model.label} bu ayarları desteklemiyor, `
      + `varsayılana düşüldü: ${dusenler.join(", ")}.`;
  }
}

/** Seçiciye GİRECEK modeller: KULLANILABİLİR olanlar (+ zorunlu tutulan id).
 *
 * FİLTRE, "10+ modele ölçeklenirken alan duvarına dönüşmesin" isteğinin model
 * şeridindeki karşılığı: kullanıcı Azure anahtarıyla çalışıyorsa OpenAI ve
 * Gemini satırlarının hepsi seçilebilir bir 502'den başka bir şey değil.
 *
 * ÖLÇÜT `available`, `configured` DEĞİL — ve bu ayrım ileriye dönük.
 * Bugün sunucu `available`ı birebir `configured`dan türetiyor (app.py), yani
 * davranış aynı. Yarın kredi/üyelik geldiğinde bir modelin GÖRÜNMEME sebebi
 * ikiye çıkıyor ("anahtar yok" · "abonelik kapsamıyor") ve o iki sebebi
 * İSTEMCİDE ayrı ayrı sormak, görünürlük kuralının iki cevabı olması demek —
 * bu fonksiyonun var olma sebebi tam olarak o ikiliği önlemek. Karar sunucuda
 * TEK alana indirgeniyor; buradaki soru hep aynı kalıyor.
 * `configured` ÖLMÜYOR: mesaj yazan yerler (#model-note, goBlockReason) onu
 * okumaya devam ediyor, çünkü "anahtar yok" ile "planın kapsamıyor" aynı
 * cümle değil.
 *
 * TEK KAÇIŞ KAPISI KALDI: `zorunluId` her zaman listede duruyor. `applyModel`
 * seçili id'yi `select.value`'ya yazıyor ve o id seçenekler arasında yoksa
 * <select> BOŞ görünür — şerit "model yok" der ama üretim çalışır.
 *
 * İKİNCİ KAPI KAPANDI (kullanıcı isteği: anahtarı girilmemiş modeller hiç
 * görünmesin). Eskiden hiçbiri kurulu değilken HEPSİ listeleniyordu ve
 * gerekçesi "boş bir <select> kullanıcıya hiçbir şey söylemez"di. O gerekçe
 * bugün karşılıksız, çünkü söyleyen üç yer var ve üçü de bu turda kuruldu ya
 * da zaten duruyordu:
 *   · `settings.js` hiçbir görsel modeli kurulu değilken Ayarlar'ı
 *     KENDİLİĞİNDEN açıyor — ilk kurulumdaki kullanıcı boş bir şeritle değil,
 *     anahtar formuyla karşılaşıyor;
 *   · şerit ve panel boş hâli açıkça anlatıyor (`MODEL_BOS_METNI`);
 *   · Ayarlar'daki #provider-status hangi sağlayıcıların VAR olduğunu tek tek
 *     sayıyor, yani keşfedilebilirlik oraya taşındı.
 */
function secilebilirler(liste, zorunluId) {
  return liste.filter((m) => m.available || m.id === zorunluId);
}

/** Hangi model SEÇİLİ olacak: tercih → varsayılan → ilk kullanılabilir.
 *
 * Üç kademe, hepsi "KULLANILABİLİR olan kazanır" kuralına tabi:
 *
 *   1. Kullanıcının TERCİHİ — kullanılabilir ise.
 *   2. Sunucunun varsayılanı — kullanılabilir ise.
 *   3. İlk kullanılabilir model. HİÇBİRİ yoksa BOŞ DİZE: "seçim yok" artık
 *      ifade edilebilen bir durum (eskiden son çare listenin ilkiydi ve
 *      kullanılamaz bir modeli seçili gösteriyordu).
 *
 * KURULU OLMAYAN TERCİH ARTIK YAPIŞMIYOR ve bu bilinçli bir değişiklik.
 * v0.6'da tersi yazılıydı ("seçili kalıyor, yoksa anahtarı kaydetmek
 * kullanıcının seçimini geri getirmezdi") ve o gerekçe o gün doğruydu; bugün
 * karşılığı kalmadı çünkü tercihi TAŞIYAN yer değişti: `seciliModelTercihi`
 * burada YAZILMIYOR ve diskteki değere hiç dokunulmuyor, yani kullanıcı
 * anahtarı sonradan girdiğinde `applyModels` yeniden koşuyor ve ESKİ SEÇİM
 * kendiliğinden geri geliyor. Yapışmanın bedeli ise gerçek chromium
 * koşumunda ölçüldü: `prefs`in `image_model` VARSAYILANI Azure'ın id'si
 * (`chat_model`in aksine boş dize değil), yani "hiç seçmedim" ile "Azure'ı
 * seçtim" istemcide ayırt edilemiyor — sonuç, yalnızca Gemini anahtarı olan
 * kullanıcının açılışta ölü bir #go düğmesiyle karşılanmasıydı.
 */
function secilecek(liste, tercih, varsayilan) {
  const kullanilabilir = liste.filter((m) => m.available);
  // "Seçilebilir" TEK koşula indi: model kullanılabilir olacak. Eskiden ikinci
  // bir dal vardı ("hiçbiri kurulu değilse hepsi uygun") ve o, `secilebilirler`in
  // kapanan kaçış kapısının bu fonksiyondaki ikiziydi — biri kapanıp öteki
  // kalsaydı, listede OLMAYAN bir model seçili görünürdü.
  const uygun = (id) => kullanilabilir.some((m) => m.id === id);
  if (tercih && uygun(tercih)) return tercih;
  if (uygun(varsayilan)) return varsayilan;
  // Hiçbiri kullanılabilir değilse BOŞ DİZE — "seçim yok" gerçek bir durum ve
  // artık ifade edilebiliyor. `applyModel`/`applyChatModel` bunu boş hâl olarak
  // çiziyor, `goBlockReason` da kapıyı gerekçesiyle kapatıyor.
  return (kullanilabilir[0] || {}).id || "";
}

/** Kredi aralığı: `credits_by_quality` varsa min–max, yoksa tek tarife.
 *
 * AYRI fonksiyon çünkü İKİ yer okuyor — <option> metni ve panelin kart
 * satırı. Aynı aralığı iki yerde kurmak, ikisinin sessizce ayrışması demekti
 * (biri "kredi" yazarken öteki "kr." yazan gün kimse fark etmez).
 */
function modelKrediAraligi(m) {
  const tarife = Object.values(m.credits_by_quality || {});
  return tarife.length
    ? `${Math.min(...tarife)}–${Math.max(...tarife)} kredi`
    : `${m.credits} kredi`;
}

/** Çipin ve <option>un PAYLAŞTIĞI metin.
 *
 * Bir zamanlar bu metin yalnızca `<option>`da kuruluyordu ve çip onu bedavaya
 * alıyordu — native `<select>` seçili seçeneğin metnini kendisi yazar. Çip
 * `<button>` olunca o bedava yol kapandı; metin İKİ yerde gerekiyor ve iki
 * yerde ayrı kurulursa ayrışır. O yüzden tek kaynak burada.
 *
 * AD `short_label`: sağlayıcı markasını çipin solundaki işaret söylüyor,
 * etiketin de söylemesi aynı bilgiyi iki kez yazmak olurdu. Kısaltma SUNUCUDA
 * yapılıyor (catalog.short_labels) — istemci marka adı saymıyor ve çakışan
 * adlar tam etiketini koruyor. `|| m.label` eski bir yanıtta alan yoksa
 * şeridin adsız kalmaması için.
 *
 * `kredi` eksene göre: sohbet modellerinin kredi tarifesi YOK (`ChatModel`de
 * alan bile yok) ve uydurma bir aralık yanlış bir karşılaştırma sunardı.
 */
function modelSecenekMetni(m, kredi) {
  const ad = m.short_label || m.label;
  return (kredi ? `${ad} — ${modelKrediAraligi(m)}` : ad)
    + (m.configured ? "" : " · kurulum gerekli");
}

function renderModelOptions(zorunluId) {
  const el = $("model");
  el.replaceChildren(...secilebilirler(imageModels, zorunluId).map((m) => {
    const o = document.createElement("option");
    o.value = m.id;
    // Maliyet ve kurulum durumu ETİKETTE: karşılaştırma ("hangisi ucuz?")
    // burada yapılıyor ve native bir <option> yalnız metin taşıyabiliyor.
    o.textContent = modelSecenekMetni(m, true);
    // Tanıtım notu `title`da: <option> görsel taşıyamıyor ve bu liste artık
    // KULLANICIYA GÖRÜNMÜYOR (değer tutucu; seçim #model-sheet'te). Satır yine
    // de duruyor: `title` bedava ve <select> bir gün geri görünür olursa bilgi
    // onunla birlikte geri gelir. Notun GÖRÜNEN yeri panelin kart satırı.
    if (m.note) o.title = m.note;
    return o;
  }));
}

/** Katalog + hangi modellerin kullanılabilir olduğunu sunucudan çeker.
 *
 * `/api/settings` ile AYNI yanıttan okunuyor, ayrı bir uçtan değil: ikisi ayrı
 * zamanlarda gelirse seçici bir an "hepsi kullanılabilir" gösterip sonra fikir
 * değiştirirdi (GET /api/settings'in `guncelleme` alanı için yazılı olan
 * gerekçenin aynısı).
 */
function applyModels(s, tercih) {
  if (!s || !Array.isArray(s.image_models)) return;
  imageModels = s.image_models;
  // SIRA: önce seçilecek id, SONRA çizim. Ters olsaydı filtre seçili modeli
  // listeden atabilirdi ve <select> boş görünürdü (bkz. secilebilirler).
  // Kayıtlı tercih artık katalogda olmayabilir (model kaldırıldı) ya da
  // anahtarı olmayabilir; ikisinin de cevabı `secilecek`te.
  const id = secilecek(imageModels, tercih, s.default_image_model);
  renderModelOptions(id);
  applyModel(id, { announce: false });
  // Arena kümesinin seçenekleri de aynı katalogdan; Ayarlar kaydedildiğinde
  // (anahtar girildi → `configured` değişti) burası da tazelenmezse arena
  // paneli bayat bir listeyle çizilirdi.
  renderArenaOptions();
  // Ve kümenin GÖRÜNEN sonuçları da tazeleniyor: katalogdan düşen bir model
  // seçimden de düşer, ama çip "2 model" demeye devam ederdi — tek yazardan
  // geçmeyen tek yol tam olarak burasıydı.
  arenaUygula();
}

// ── Arena: aynı prompt, birden çok model ─────────────────────────────
//
// Arena TURU, model başına AYRI bir `POST /api/generate` isteğidir; fan-out
// istemcide, sunucuda DEĞİL. Üç ölçülmüş sebep (uzunu models.py'de):
//   · zaman aşımı bütçesi model başına hesaplanıyor (providers.total_budget),
//     tek istekte fan-out isteği en yavaş modele bağlardı;
//   · uçtaki hata modeli tek yollu (502), "3 modelden 1'i düştü" ifade
//     edilemiyor — ayrı istekte her sütun kendi hatasını taşıyor;
//   · sunucu zaten çok iş parçacıklı (senkron `def` + anyio havuzu), yani
//     N istek gerçekten paralel koşuyor.
//
// EKSEN ÇEVİRİSİ arenanın asıl işi: modellerin jeton kümeleri farklı
// (Azure `1024x1536`, Gemini `2:3`; Azure düşük/orta/yüksek, Gemini 1K/2K/4K).
// Kullanıcı TEK ayar seçiyor, `arenaSutunlari` onu model başına çeviriyor —
// boyut ORAN üzerinden (sunucu her jetonun oranını yayınlıyor), kalite ise
// SIRA üzerinden. İkinci bir "hangi ayar" kaynağı doğmuyor.

const ARENA_MIN = 2;
const ARENA_MAX = 4;

let arenaAcik = false;

/** Arena kümesi: `<select multiple>`in seçili id'leri, DOM SIRASINDA.
 *
 * Sıra bir süs değil sözleşme: İLK id birinci sütun, yani `#size`/`#quality`
 * eksenlerini süren model ve öteki sütunların çevirisinin KAYNAĞI.
 */
function arenaSecimi() {
  return [...$("arena-models").selectedOptions].map((o) => o.value);
}

/** Kümenin seçeneklerini katalogdan çizer; seçili olanlar korunur. */
function renderArenaOptions() {
  const secili = new Set(arenaSecimi());
  $("arena-models").replaceChildren(...imageModels.map((m) => {
    const o = document.createElement("option");
    o.value = m.id;
    // Ad kurgusu görsel şeridiyle TEK kaynaktan (`modelSecenekMetni`).
    o.textContent = modelSecenekMetni(m, true);
    o.selected = secili.has(m.id);
    return o;
  }));
}

/** Panelde bir kutucuğa dokunuldu: kümeye gir ya da çık.
 *
 * TAVAN kutucuğun kendisinde uygulanıyor (`checked` geri alınıyor), çünkü
 * beşinci modeli sessizce yok saymak "bastım, hiçbir şey olmadı" demek olurdu
 * — kapalı `#go`nun sebebini `title`a yazan duruşun aynısı.
 */
function arenaKutucuk(kutucuk) {
  if (!kutucuk || !kutucuk.value) return;
  const idler = arenaSecimi();
  if (kutucuk.checked && !idler.includes(kutucuk.value)) {
    if (idler.length >= ARENA_MAX) {
      kutucuk.checked = false;
      statusEl.textContent = `Arena en çok ${ARENA_MAX} model karşılaştırıyor.`;
      return;
    }
    idler.push(kutucuk.value);
  } else if (!kutucuk.checked) {
    const yer = idler.indexOf(kutucuk.value);
    if (yer >= 0) idler.splice(yer, 1);
  }
  arenaSecimiYaz(idler);
}

/** Kümeyi yazan TEK yer: `<select multiple>` değerin sahibi, `arenaUygula`
 * da o değerin bütün görünen sonuçlarının tek yazarı. */
function arenaSecimiYaz(idler) {
  const kume = new Set(idler);
  for (const o of $("arena-models").options) o.selected = kume.has(o.value);
  arenaUygula();
}

/** Seçili modellerin ORTAK oranları — birinci sütunun jetonlarıyla ifade edilmiş.
 *
 * Kesişim, çünkü kesişim dışı bir oran seçilirse bazı sütunlar sessizce kendi
 * varsayılanına düşer ve karşılaştırma farklı çerçevelerde yapılırdı: aynı
 * prompt'u aynı koşulda koşturmak arenanın tanımı.
 */
function arenaOrtakBoyutlar(idler) {
  const modeller = idler.map((id) => imageModels.find((m) => m.id === id))
                        .filter(Boolean);
  if (!modeller.length) return [];
  const [ilk, ...digerleri] = modeller;
  return ilk.sizes.filter(
    (s) => digerleri.every((m) => m.sizes.some((o) => o.ratio === s.ratio)));
}

/** Arena sütunları: model başına ÇEVRİLMİŞ eksen + birim kredi.
 *
 * TEK KAYNAK: maliyet göstergesi de üretim isteği de buradan okuyor. İki ayrı
 * yerde çevrilseydi kullanıcıya gösterilen fiyat ile faturalanan tur sessizce
 * ayrışırdı — bu deponun en sevmediği kırılma sınıfı.
 *
 * Boyut ORAN üzerinden eşleniyor (`sizes[].ratio` sunucudan geliyor, istemci
 * jeton AYRIŞTIRMIYOR); oranı olmayan modelde varsayılana düşülüyor.
 * Kalite SIRA üzerinden: `qualities` demetleri artan sırada ve
 * `credits_by_quality` bunu doğruluyor (4/8/16 · 6/6/12 · 27/27/48), yani
 * "yüksek" ile "4K" aynı basamağın iki adı. Demet daha kısaysa son basamağa
 * kırpılıyor.
 */
function arenaSutunlari() {
  const oran = $("size").selectedOptions[0]?.dataset.ratio || $("size").value;
  const sira = Math.max(0, [...$("quality").options]
    .findIndex((o) => o.value === $("quality").value));
  return arenaSecimi().map((id) => {
    const m = imageModels.find((x) => x.id === id);
    if (!m || !m.sizes.length || !m.qualities.length) return null;
    const boyut = m.sizes.find((s) => s.ratio === oran)
                  || m.sizes.find((s) => s.value === m.default_size)
                  || m.sizes[0];
    const kalite = m.qualities[Math.min(sira, m.qualities.length - 1)];
    const tarife = m.credits_by_quality || {};
    return { model: m, size: boyut.value, quality: kalite.value,
             birim: tarife[kalite.value] ?? m.credits };
  }).filter(Boolean);
}

/** Arena durumunun görünen her sonucunun TEK yazarı.
 *
 * `#model`e YAZIYOR ama `change` ATMIYOR ve bu bilinçli: `change` dinleyicisi
 * tercihi diske yazıyor (`savePref`) — arena kümesindeki bir gezinme
 * kullanıcının kalıcı model tercihini değiştirmemeli. `applyModel` doğrudan
 * çağrılıyor, yani eksen doldurma/geri düşme mekanizması ikinci kez
 * kurulmuyor.
 */
function arenaUygula() {
  const idler = arenaSecimi();
  $("arena-toggle").setAttribute("aria-pressed", String(arenaAcik));
  $("arena-btn").hidden = !arenaAcik;
  $("model-pick").hidden = arenaAcik;
  $("arena-btn-label").textContent = `${idler.length} model`;
  // Adet arenada 1'e kilitli: sütun başına tek görsel karşılaştırmanın
  // kendisi. 4 model × 4 görsel hem ızgarayı hem faturayı okunmaz yapardı.
  $("spec-n").hidden = arenaAcik;
  if (arenaAcik) {
    if (idler.length && idler[0] !== $("model").value) {
      applyModel(idler[0], { announce: false });
    }
    const ortak = arenaOrtakBoyutlar(idler);
    if (ortak.length) {
      const dusen = fillAxis("size", ortak, undefined, ortak[0].value);
      if (dusen) {
        statusEl.textContent = "Seçilen modellerin ortak oranı bu değil, "
          + `${$("size").selectedOptions[0]?.textContent.trim()} seçildi.`;
      }
    }
    if ($("n").value !== "1") $("n").value = "1";
    syncSpecs();
  } else if (currentModel) {
    // ARENA KAPANIŞI eksenleri GERİ AÇIYOR ve bu iki satır açılışın birebir
    // tersi: açılışta `#size` modellerin KESİŞİMİNE daraltılıyor, `#n` de 1'e
    // kilitleniyor. Geri açan kod yoktu ve kırılma arena KAPANDIKTAN sonra
    // görülüyordu — Nano Banana (10 oran) ile Azure (3) arasında bir arena
    // kurup kapatan kullanıcı, TEK MODEL üretiminde de oran ekseninde 3
    // seçenek görmeye devam ediyordu; adet de 1'e mıhlı kalıyordu. Model
    // yeniden seçilmeden düzelmiyordu, yani sessiz.
    //
    // Kullanıcının seçimi bozulmuyor: kesişim modelin kümesinin ALT kümesi,
    // `fillAxis` de birebir aynı `value`yu koruyor (1. kademe). `applyModel`
    // çağırmak yerine iki eksenin doldurulması, çünkü arena YALNIZ bu ikisine
    // dokunuyor — kalite/şerit/tercih zincirini yeniden koşturmak kapsam dışı.
    fillAxis("size", currentModel.sizes, undefined, currentModel.default_size);
    fillAxis("n", adetSecenekleri(currentModel), undefined, "1");
    syncSpecs();
  }
  syncRunCost();
  syncGoGate();
}

$("arena-toggle").addEventListener("click", () => {
  arenaAcik = !arenaAcik;
  // Kapatırken açık arena paneli de kapanıyor: kapalı bir arenanın "hangi
  // modeller" listesi ekranda asılı kalırdı.
  if (!arenaAcik) { closeSheets(); arenaUygula(); return; }
  // AÇILIŞ TOHUMU: küme boşsa o anki model birinci sütun olarak giriyor —
  // boş bir arena "hangi modeller" sorusunu cevapsız bırakırdı. Panel de
  // hemen açılıyor, çünkü tek modelli arena diye bir şey yok ve kullanıcının
  // sıradaki işi zaten ikinciyi seçmek.
  if (arenaSecimi().length < ARENA_MIN && $("model").value) {
    arenaSecimiYaz([$("model").value]);
  } else {
    arenaUygula();
  }
  openModelSheet("arena");
});



// ── Prompt Yönetmeni'nin model şeridi ────────────────────────────────
//
// Görsel şeridinin AYNI deseni, üç bilinçli farkla:
//   · Etikette kredi YOK: sohbetin kredi tarifesi yok (`ChatModel`'de `credits`
//     alanı bile yok) ve uydurma bir aralık yazmak yanlış bir karşılaştırma
//     sunardı. Bilgi yine `title`da (`note`).
//   · Eksen (boyut/kalite/adet) YOK: sohbetin ayarı yok.
//   · "kurulu" ölçütü MODEL BAŞINA geliyor, kimlik başına değil: Azure'ın
//     dağıtım adı boşken kimliği tamdır ama model konuşulamaz
//     (bkz. credstore.chat_is_configured).

function renderChatModelOptions(zorunluId) {
  const el = $("chat-model");
  el.replaceChildren(...secilebilirler(chatModels, zorunluId).map((m) => {
    const o = document.createElement("option");
    o.value = m.id;
    // `textContent`: sunucudan gelen hiçbir şey innerHTML'e girmiyor.
    // Ad kurgusu görsel şeridiyle TEK kaynaktan (`modelSecenekMetni`);
    // `false` = kredi yok, gerekçesi o fonksiyonun notunda.
    o.textContent = modelSecenekMetni(m, false);
    if (m.note) o.title = m.note;
    return o;
  }));
}

/** Seçili sohbet modelini uygular. `applyModel`in yönetmen karşılığı.
 *
 * UYGULANAN MODELİ DÖNDÜRÜYOR (yoksa `null`) ve bu dönüş değeri bir kolaylık
 * değil, `change` dinleyicisinin gereği: erken çıkış `currentChatModel`i
 * OLDUĞU GİBİ bırakıyor — ilk çizimden önce `null`, sonrasında ESKİ model.
 * Dinleyici o küresel değişkeni okuyup `.provider`ına eriştiği için, erken
 * çıkışta ya `TypeError` atardı (konsolda kırmızı, tercih yazılmaz) ya da
 * kullanıcının SEÇMEDİĞİ bir modeli diske tercih olarak yazardı — ikincisi
 * daha sessiz ve daha kötü. `applyModel`de bu tuzak yok çünkü onun
 * dinleyicisi `$("model").value`yu okuyor, küresel değişkeni değil.
 *
 * `id` katalogda YOKKEN çağrılmak gerçek bir yol: `secilecek` liste boşken
 * (`chat_models: []`) boş dize döndürüyor ve settings.js onu doğrudan buraya
 * veriyor.
 */
function applyChatModel(id) {
  const model = chatModels.find((m) => m.id === id);
  // `applyModel`in boş hâlinin ikizi; gerekçesi orada.
  if (!model) {
    if (!id) { currentChatModel = null; modelBosHali("chat"); }
    return null;
  }
  currentChatModel = model;
  // `applyModel`in aynı gerekçesi: seçili id şeritte yoksa şerit boş görünür.
  if (![...$("chat-model").options].some((o) => o.value === id)) {
    renderChatModelOptions(id);
  }
  $("chat-model").value = model.id;
  syncModelChip("chat", model);
  syncGoGate();
  // SON SATIR ve gerçek bir kırılmanın bekçisi: dönüş eklenirken bu satır
  // unutulduğunda fonksiyon `undefined` döndürdü, dinleyici de her seferinde
  // erken çıktı — yani şerit doğru modeli GÖSTERİYOR, tercih diske HİÇ
  // yazılmıyordu ve konsolda tek bir hata bile yoktu. Kaynak taraması
  // ("`return null` var mı?") bunu yeşil geçti; yalnız gerçek Chromium'da
  // görüldü (POST /api/prefs hiç gitmiyor).
  return model;
}

function applyChatModels(s, tercih) {
  if (!s || !Array.isArray(s.chat_models)) return;
  chatModels = s.chat_models;
  const id = secilecek(chatModels, tercih, s.default_chat_model);
  renderChatModelOptions(id);
  applyChatModel(id);
}

/** Tercihi diske yazar. Hata SESSİZ yutulmuyor ama üretimi de engellemiyor.
 *
 * `chatApi` KULLANILMIYOR: o chat.js'te ve bu dosya ondan ÖNCE yükleniyor —
 * olay anında erişilebilir olsa da tercih yazımı için üç satırlık bir fetch
 * yeterli, ve bağ ne kadar az olursa yükleme sırası o kadar az kırılgan.
 *
 * Yazım BAŞARISIZ olsa bile seçim ekranda kalıyor: kullanıcı bu turda seçtiği
 * modelle üretebiliyor, yalnız seçim bir sonraki açılışa taşınmıyor. Tersi
 * (seçimi geri almak) çalışan bir şeyi bozardı.
 */
async function savePref(body) {
  try {
    const res = await fetch("/api/prefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    statusEl.textContent = `Tercih kaydedilemedi (seçim bu oturumda geçerli): ${e.message}`;
  }
}

// ── Model seçici popup'ı (#model-sheet) ──────────────────────────────
//
// TEK yüzey, İKİ eksen. Gerekçe index.html'de yazılı (iki çip
// `#composer[data-mode]` ekseniyle birbirini dışlıyor, yani ikisi birden açık
// olamaz) ve deseni `setModelLogo` kurdu: "TEK yardımcı, iki şerit". Bu tablo
// o iki ekseni ADRESLERE bağlıyor — aşağıdaki kodun hiçbir yerinde "görsel mi
// sohbet mi" diye ikinci bir şart yok, hepsi buradan okuyor.
//
// `liste` bir FONKSİYON, dizinin kendisi DEĞİL ve bu ayrım zorunlu:
// `imageModels`/`chatModels` `applyModels`te YENİDEN ATANIYOR
// (`imageModels = s.image_models`). Diziyi burada yakalamak, Ayarlar
// kaydedildikten sonra panelin ESKİ katalogu göstermesi olurdu — üstelik
// sessizce, çünkü eski dizide de geçerli modeller var.
// BOŞ PANELİN metni EKSENE bağlı, çünkü "model yok"un SEBEBİ eksene göre
// değişiyor. Görsel tarafında eksik olan gerçekten API anahtarı. Sohbet
// tarafında eksik olan kimliğin BÜTÜNÜ: Azure'da anahtar kayıtlıyken dağıtım
// adı boş olabiliyor (credstore.chat_is_configured ikisini birden arıyor) ve o
// kullanıcıya "anahtar yok" demek, elinde ZATEN olan anahtarı yeniden
// yapıştırmasını söylemek olurdu — yapıştırır, hiçbir şey değişmez, sebep de
// hâlâ görünmez. `goBlockReason`ın yönetmen dalı bu ayrımı yapıyor
// ("Kayıtlı sohbet kimliği yok"); panel de aynı dili konuşmak zorunda, yoksa
// aynı hâl iki yerde iki ayrı iş buyurur.
const MODEL_BOS_PANEL = {
  anahtar: "Kayıtlı API anahtarı yok. Ayarlar'dan bir sağlayıcının anahtarını "
    + "kaydedince modelleri burada göreceksin.",
  kimlik: "Kayıtlı sohbet kimliği yok. Ayarlar'dan bir sağlayıcının kimlik "
    + "bilgilerini (anahtar, gerekiyorsa dağıtım adı) tamamlayınca modelleri "
    + "burada göreceksin.",
};

const MODEL_EKSENLERI = {
  image: {
    secici: "model", dugme: "model-btn", etiket: "model-btn-label",
    logo: "model-logo", baslik: "Görsel modeli", kredi: true,
    bosMetin: MODEL_BOS_PANEL.anahtar,
    liste: () => imageModels,
  },
  chat: {
    secici: "chat-model", dugme: "chat-model-btn", etiket: "chat-model-btn-label",
    logo: "chat-model-logo", baslik: "Yönetmen modeli", kredi: false,
    bosMetin: MODEL_BOS_PANEL.kimlik,
    liste: () => chatModels,
  },
  // ÜÇÜNCÜ EKSEN, ikinci bir panel DEĞİL: arena aynı listeyi, aynı filtreyi
  // (`secilebilirler`) ve aynı kapanma mekaniğini kullanıyor. Tek farkı
  // `coklu` — kartlar radyo yerine checkbox çiziyor.
  //
  // `logo` YOK: arena çipi birden çok sağlayıcıyı temsil ediyor ve tek bir
  // işaret onlardan birini seçmek zorunda kalırdı. Çipin metnini
  // `arenaUygula` yazıyor (tek yazar), `syncModelChip` bu eksene hiç
  // dokunmuyor.
  arena: {
    secici: "arena-models", dugme: "arena-btn", etiket: "arena-btn-label",
    logo: null, baslik: "Arena modelleri", kredi: true, coklu: true,
    // Arena görsel modellerini listeliyor, yani eksik olan da aynı şey.
    bosMetin: MODEL_BOS_PANEL.anahtar,
    liste: () => imageModels,
  },
};

// Panel o an hangi ekseni gösteriyor. `#model-sheet[data-axis]` ile İKİZ ve
// bilerek: öznitelik CSS/test tarafının okuduğu yüz, bu değişken kod tarafının.
// Tek kaynaktan yazılıyorlar (`openModelSheet`), yani ayrışamıyorlar.
let modelSheetEkseni = "image";
// Odak iadesinin diğer yarısı `closeSheets`in yanında (yukarısı): iade
// olmadan `Escape` odağı kapanan katmanın içinde bırakıyor ve klavye
// kullanıcısı sekmeye baştan başlıyor (chat.js'in menü deseninin aynısı).

/** Çipi seçili modele göre tazeler: işaret, metin, ve panelin radyosu.
 *
 * `applyModel`/`applyChatModel`in ÇAĞIRDIĞI tek satır bu — yani seçim hangi
 * yolla gelirse gelsin (panel, tercih yükleme, katalog tazeleme) çip aynı
 * yerden yazılıyor.
 *
 * ÜÇÜNCÜ İŞ, panelin radyosu, sonsuz döngünün kapandığı yer: `checked`
 * ÖZELLİĞİNE yazmak `change` DOĞURMUYOR (yalnız kullanıcı etkileşimi
 * doğurur). Panel → <select> → applyModel → panel zinciri burada duruyor,
 * ikinci bir "şu an uyguluyorum" bayrağına gerek yok.
 */
function syncModelChip(eksenAdi, model) {
  const eksen = MODEL_EKSENLERI[eksenAdi];
  // `model` NULL OLABİLİR: anahtarı girilmemiş modeller artık hiç
  // listelenmediği için "seçili model yok" gerçek bir hâl (ilk kurulumun ta
  // kendisi). Boş hâl BURADA çiziliyor, ayrı bir fonksiyonda DEĞİL — çipin
  // tek yazarı olması bu dosyanın çivilenmiş kuralı ve ikinci bir yazar,
  // işaretle metnin ayrışabildiği anlamına gelirdi. Kural gerçekten ÖLÇÜLÜYOR:
  // tests/test_index.py işaretin ve etiket atamasının kaç kez geçtiğini SAYAR —
  // bu yorum o dizeleri taşımıyor, çünkü sayan bir tripwire'ı bir yorum da
  // kandırabilir (deponun daha önce ödediği bir bedel; bkz. index.html'deki
  // `<b id="model-btn-label">` notu).
  setModelLogo(eksen.logo, model);       // model yoksa işaret de yok
  $(eksen.etiket).textContent = model
    ? modelSecenekMetni(model, eksen.kredi)
    : MODEL_BOS_METNI;
  if (modelSheetEkseni === eksenAdi) {
    for (const r of $("model-sheet-list").querySelectorAll("input")) {
      r.checked = !!model && r.value === model.id;
    }
  }
}

/** Şeritte gösterilecek "hiç kullanılabilir model yok" metni.
 *
 * TEK dize, üç yer okuyor (çip · panel · testler) — ikinci bir yerde yeniden
 * kurulsaydı ikisi zamanla ayrışırdı; `modelSecenekMetni`nin aynı dersi.
 */
const MODEL_BOS_METNI = "Model yok — Ayarlar";

/** Kullanılabilir model KALMADIĞINDA şeridi ve notu boş hâle çeker.
 *
 * Anahtarı girilmemiş modeller artık hiç listelenmediği için bu durum GERÇEK
 * ve ilk kurulumun ta kendisi. Önceden erişilemezdi (filtre o hâlde bütün
 * kataloğu gösteriyordu), yani çizilmemiş bir ekrandı: çip "Modeller
 * yükleniyor…" yazısında donuyordu.
 *
 * Kullanıcı burada çıkmaz sokakta DEĞİL — üç kapı birden açık: Ayarlar ilk
 * kurulumda kendiliğinden açılıyor (settings.js), `#model-note` doğrudan
 * "Ayarlar'ı aç" düğmesi taşıyor ve `#go` kilidinin sebebi `title`da yazılı.
 */
function modelBosHali(eksenAdi) {
  // Çizim TEK yazardan (yukarısı); burası yalnız "model yok"u ona söylüyor.
  syncModelChip(eksenAdi, null);
  // Not YALNIZ görsel ekseninde: Yönetmen'in karşılığı #chat-gate ve onun
  // yazarı settings.js (`chat_configured`). İki yazar tek düğüme yazsaydı
  // hangisinin son sözü söylediği çağrı sırasına kalırdı.
  if (eksenAdi === "image") {
    $("model-note-text").textContent = "Kayıtlı API anahtarı yok.";
    $("model-note").hidden = false;
  }
  // Panel YENİDEN ÇİZİLMİYOR: kartların tek çağıranı `openModelSheet` ve o
  // her açılışta çiziyor (bayat liste riski orada kapatılmış). Buradan ikinci
  // bir çağrı, o tek-çağıran kuralını bozardı.
  syncGoGate();
}

/** Paneli seçili eksenin modelleriyle çizer.
 *
 * Filtre `secilebilirler` — <option> listesinin AYNISI, yani "hangi modeller
 * görünür" sorusunun ikinci bir cevabı doğmuyor (o cevabın iki kaçış kapısı
 * da orada yazılı: ilk kurulumda hepsi görünür, seçili id her zaman listede).
 *
 * `textContent` ve `img.src`: sunucudan gelen hiçbir şey `innerHTML`e
 * girmiyor — `renderChatModelOptions`ın kuralının aynısı.
 *
 * `<legend>` KORUNUYOR: `replaceChildren` onu da silerdi ve `<fieldset>`
 * adsız kalırdı (ekran okuyucu "grup" der, neyin grubu demez).
 */
function renderModelCards(eksenAdi) {
  const eksen = MODEL_EKSENLERI[eksenAdi];
  // ÇOKLU eksende değer bir DİZİ (<select multiple>'ın seçili seçenekleri),
  // tekilde tek dize. `secilebilirler`in "seçili id her zaman listede" kaçış
  // kapısı ikisinde de İLK id ile besleniyor: arenada birinci sütun zaten
  // eksenleri süren model, yani listede kalması gereken de o.
  const secililer = eksen.coklu ? arenaSecimi() : [$(eksen.secici).value];
  const secili = secililer[0] || "";
  const kok = $("model-sheet-list");
  const legend = kok.querySelector("legend");

  const kartlar = secilebilirler(eksen.liste(), secili).map((m) => {
    const kart = document.createElement("label");
    kart.className = "radio-row model-row";

    // İŞARET SUNUCUDAN (`model.logo`, app._provider_logo_url) — istemcide
    // sağlayıcı adı sayılmıyor, dize birleştirilmiyor. `setModelLogo`un aynı
    // gerekçesi: yarın yeni bir sağlayıcı eklenince işaret kendiliğinden
    // geliyor. `alt=""` çünkü sağlayıcı adı kartın metninde ZATEN var.
    const kutu = document.createElement("span");
    kutu.className = "model-row-ic";
    if (m.logo) {
      const img = document.createElement("img");
      img.src = m.logo;
      img.alt = "";
      kutu.append(img);
    }

    const metin = document.createElement("span");
    metin.className = "model-row-txt";
    const ad = document.createElement("b");
    ad.textContent = m.short_label || m.label;
    // Kurulum durumu ROZETLE: `<option>` metninde " · kurulum gerekli" diye
    // yazıyordu ve bilgi kaybolmuyor, yalnız okunabilir bir biçime geçiyor.
    if (!m.configured) {
      const rozet = document.createElement("span");
      rozet.className = "model-row-badge";
      rozet.textContent = "kurulum gerekli";
      ad.append(rozet);
    }
    metin.append(ad);
    // ASIL KAZANÇ: tanıtım notu ekranda. `option.title`da gömülüydü ve
    // telefonda `title` hiç görünmüyor.
    if (m.note) {
      const not = document.createElement("span");
      not.textContent = m.note;
      metin.append(not);
    }
    if (eksen.kredi) {
      const tarife = document.createElement("span");
      tarife.className = "model-row-meta";
      tarife.textContent = modelKrediAraligi(m);
      metin.append(tarife);
    }

    // GERÇEK RADYO / CHECKBOX: ok tuşu gezintisi, grup semantiği ve
    // `:checked` durumu tarayıcıdan geliyor. Eski native <select> kararının
    // itirazı ("ARIA listbox'ı sıfırdan getirirdi") tam olarak burada
    // karşılanıyor — çoklu eksende de, çünkü checkbox grubu zaten native.
    //
    // `name` çoklu eksende de yazılıyor: checkbox'lar için gruplama etkisi
    // yok, ama testler ve CSS tek bir seçiciyle ikisini birden buluyor.
    const kutucuk = document.createElement("input");
    kutucuk.type = eksen.coklu ? "checkbox" : "radio";
    kutucuk.name = "model-sheet-pick";
    kutucuk.value = m.id;
    kutucuk.checked = eksen.coklu ? secililer.includes(m.id) : m.id === secili;

    kart.append(kutu, metin, kutucuk);
    return kart;
  });

  // BOŞ PANEL bir hâl DEĞİL bir soru: "modeller nerede?". Anahtarsız modeller
  // artık hiç listelenmediği için panel gerçekten boş kalabiliyor ve o boşluk
  // kendi başına hiçbir şey söylemez. Tek satırlık açıklama, kartların yerine
  // geçiyor — çipin `MODEL_BOS_METNI`si ile aynı gerçeği anlatıyor, ama
  // burada yer var, o yüzden NE YAPILACAĞINI da söylüyor.
  //
  // Metin EKSENDEN okunuyor, burada KURULMUYOR: bu fonksiyon üç eksenin
  // ortağı ve sabit bir "API anahtarı" cümlesi sohbet ekseninde yanlış iş
  // buyuruyordu (gerekçe MODEL_BOS_PANEL'in başında).
  if (!kartlar.length) {
    const bos = document.createElement("p");
    bos.className = "model-sheet-empty";
    bos.textContent = eksen.bosMetin;
    kartlar.push(bos);
  }

  // `legend` YAYILARAK veriliyor, doğrudan DEĞİL: `replaceChildren(null, …)`
  // argümanı dizeye çevirip panelin tepesine "null" METNİ basar — hata da
  // vermez. Düğüm bugün index.html'de duruyor (bekçisi tests/test_index.py),
  // yani ulaşılmaz bir dal; yazılışı niyeti de söylüyor: legend varsa korunur.
  kok.replaceChildren(...(legend ? [legend] : []), ...kartlar);
}

/** Paneli açar. Kartlar HER AÇILIŞTA yeniden çiziliyor.
 *
 * Neden her seferinde: katalog `applyModels` ile değişebiliyor (Ayarlar'a
 * anahtar girildi → `configured` bayrakları değişti) ve bayat bir liste
 * "anahtarı olan model kurulum gerektiriyor" diye görünürdü. Çizim maliyeti
 * beş kart, ölçülecek bir bedel değil.
 */
function openModelSheet(eksenAdi) {
  // İKİNCİ TIK KAPATIYOR — #specs-btn'in kalıbının aynısı. Çip açık bir panelin
  // altında duruyor (panel ekranın dibinde, çip composer'da) ve tıklanabilir
  // kalıyor: kapanmayan bir tetikleyici "bastım, hiçbir şey olmadı" demek.
  const acilacak = !($("model-sheet").classList.contains("open")
                     && modelSheetEkseni === eksenAdi);
  closeSheets();
  if (!acilacak) return;

  modelSheetEkseni = eksenAdi;
  $("model-sheet").dataset.axis = eksenAdi;
  $("model-sheet-title").textContent = MODEL_EKSENLERI[eksenAdi].baslik;
  renderModelCards(eksenAdi);
  openSheet("model-sheet");                       // tek kapı (yukarısı)

  // SIRA BAĞLAYICI ve sessiz bir kırılmanın mandalı: `openSheet` İÇİNDE
  // `closeSheets` koşuyor ve o `modelSheetTetik`i null'a çekiyor. Atama
  // `openSheet`ten ÖNCE yapılsaydı odak iadesi hiç çalışmazdı — ekranda
  // hiçbir iz bırakmadan, çünkü panel yine açılıyor ve seçim yine işliyor.
  const tetik = $(MODEL_EKSENLERI[eksenAdi].dugme);
  modelSheetTetik = tetik;
  tetik.setAttribute("aria-expanded", "true");

  // Odak İŞARETLİ radyoya: ok tuşlarıyla gezinme ilk tuş basımında çalışsın
  // (odak listenin dışında kalırsa ilk ok tuşu sayfayı kaydırır). Liste boş
  // olabiliyor (katalog gelmemiş) — o durumda dipteki düğme.
  const isaretli = $("model-sheet-list").querySelector("input:checked");
  setTimeout(() => (isaretli || $("model-sheet-ok")).focus(), 0);
}

// Kart seçimi: TEK dinleyici, olay yetkilendirmeyle. Kartlar her açılışta
// yeniden çiziliyor, yani düğüm başına dinleyici bağlamak her açılışta
// yenilenmesi gereken bir bağ olurdu.
//
// Seçim <select>e YÖNLENDİRİLİYOR, doğrudan uygulanmıyor: değerin tek sahibi
// o ve `change` dinleyicileri (applyModel, savePref, tercihin bellekteki
// tazelenmesi) oraya bağlı. Panelden ayrıca `applyModel` çağırmak o zincirin
// ikinci bir kopyası olurdu.
$("model-sheet-list").addEventListener("change", (e) => {
  const eksen = MODEL_EKSENLERI[modelSheetEkseni];
  // Çoklu eksende yönlendirilecek tek bir değer yok: kutucuk kümeye giriyor
  // ya da çıkıyor (bkz. arenaKutucuk).
  if (eksen.coklu) { arenaKutucuk(e.target); return; }
  const secici = $(eksen.secici);
  // AYNI DEĞERE ikinci dokunuş sessiz: native <select> de değişmeyen bir
  // değer için `change` atmıyor. Bu satır olmadan aynı karta her dokunuş
  // diske bir `POST /api/prefs` yazardı — ekranda hiçbir iz bırakmadan.
  if (!e.target.value || secici.value === e.target.value) return;
  secici.value = e.target.value;
  secici.dispatchEvent(new Event("change", { bubbles: true }));
});

$("model-btn").addEventListener("click", () => openModelSheet("image"));
$("chat-model-btn").addEventListener("click", () => openModelSheet("chat"));
$("arena-btn").addEventListener("click", () => openModelSheet("arena"));
$("model-sheet-close").addEventListener("click", closeSheets);
// "Tamam" yalnızca KAPATIYOR: seçim dokunulduğu an uygulanmış ve tercih
// yazılmış oluyor (#pref-autosave ve tema seçicisinin deseni). Bir onay
// kapısı olsaydı "seçtim ama uygulanmadı" durumu doğardı ve panel kazayla
// kapandığında seçim kaybolurdu.
$("model-sheet-ok").addEventListener("click", closeSheets);

$("model").addEventListener("change", () => {
  applyModel($("model").value);
  // Tercih ANINDA yazılıyor, "Kaydet" düğmesine bağlı DEĞİL: #pref-autosave ve
  // tema seçicisinin deseni. O düğme kimlik formuna ait ve Azure hiç
  // yapılandırılmamışken basılamıyor.
  savePref({ image_model: $("model").value });
  // Diske YAZMAK yetmiyor, BELLEKTEKİ tercih de tazelenmeli: `applyModels`
  // her çağrıldığında `seciliModelTercihi`yi okuyor ve o değişken yalnızca
  // açılışta (`loadModelPref`) yazılıyordu. Ayarlar'ı kaydetmek
  // `applyConfigured`i yeniden çalıştırdığı için, kullanıcının bu turda
  // seçtiği model AÇILIŞTAKİ değere geri sıçrıyordu — yani PR #41'in ana
  // akışı ("OpenAI modelini seç → anahtarını gir → kaydet") seçimi geri
  // alıyordu. settings.js'in adına OLAY ANINDA dokunuluyor: yükleme sırası
  // kuralının izin verdiği tek yol (#model-settings-link ile aynı desen).
  seciliModelTercihi = $("model").value;
});

$("chat-model").addEventListener("change", () => {
  // Dönüş değeri KÜRESEL DEĞİŞKEN YERİNE kullanılıyor: `applyChatModel`
  // uygulamadıysa yazılacak bir tercih de yok (bkz. o fonksiyonun notu).
  const model = applyChatModel($("chat-model").value);
  if (!model) return;
  // TERCİH ÇİFT YAZILIYOR ve bu zorunlu: `prefs.update` `chat_model`i
  // `chat_provider`a göre doğruluyor (çapraz kural, bkz. prefs.py) ve yalnız
  // modeli göndermek "bu sağlayıcıda yok" hatasıyla 422 dönerdi — kullanıcı
  // OpenAI modeline geçtiğinde diskteki sağlayıcı hâlâ "azure" olurdu.
  savePref({ chat_provider: model.provider, chat_model: model.id });
  // Bellekteki tercih de tazeleniyor: `applyChatModels` her Ayarlar
  // kaydedişinde yeniden koşuyor ve o değişkeni okuyor — yazılmazsa
  // kullanıcının bu turda seçtiği model AÇILIŞTAKİ değere geri sıçrardı
  // (görsel tarafında ölçülmüş kırılmanın aynısı).
  seciliSohbetModeliTercihi = model.id;
});

$("model-settings-link").addEventListener("click", () => {
  // Doğrudan seçili modelin SAĞLAYICI grubunu açıyor: "anahtar yok" uyarısının
  // düğmesi kullanıcıyı doğru kutuya götürmezse uyarı yarım kalır.
  // settings.js'in adına OLAY ANINDA dokunuluyor — yükleme sırası kuralının
  // izin verdiği tek yol (settings.js core.js'ten SONRA yükleniyor).
  openSettings(currentModel ? currentModel.provider : undefined);
});

// ── Üretim ayarları çipi ──
function syncSpecs() {
  const parts = [];
  const size = $("size").selectedOptions[0];
  if (size) parts.push(size.dataset.ratio || $("size").value);
  // Kalite ekseni olmayan modelde çipte de yazmıyor: boş bir "·" bırakmak
  // "kalite kayboldu" gibi okunurdu.
  if (!$("spec-quality").hidden && $("quality").selectedOptions[0]) {
    parts.push($("quality").selectedOptions[0].textContent.trim().toUpperCase());
  }
  parts.push(`x${$("n").value}`);
  $("specs-label").textContent = parts.join(" · ");
}
for (const id of ["size", "quality", "n"]) {
  $(id).addEventListener("change", () => { syncSpecs(); syncRunCost(); });
}
syncSpecs();

// ── Composer: otomatik büyüyen kutu + ⌘Enter + ⌘J ──
// Yükseklik satır sayısıyla büyür, `.composer-input`'un max-height'ı tavan.
function autoGrow(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight}px`;
}
$("prompt").addEventListener("input", () => autoGrow($("prompt")));

/** İlk gönderimden SONRA composer küçülür (kullanıcı isteği).
 *
 * Öznitelik, sınıf değil: `data-sent` bir DURUM ve CSS onu mod ekseniyle
 * (`#composer[data-mode]`) aynı dilde okuyor.
 *
 * ÇAPA `submitComposer` çünkü iki mod da buradan geçiyor — "chat veya görsel
 * üretme prompt'u gönderildikten sonra" isteğinin tek karşılığı bu. Uzunluk
 * kapılarının ARDINDAN yazılıyor: reddedilen bir gönderim küçülmeyi hak
 * etmiyor, kullanıcı hâlâ o metni düzenliyor.
 *
 * GERİ ALINMIYOR: bir kez gönderdikten sonra ekranın odağı akış, composer
 * ise araç. Yazmaya dönen kullanıcı kutuyu `:focus-within` ile tam boyunda
 * geri buluyor (style.css), yani dar bir kutuya sıkışmıyor.
 */
// Küçük ve tam boy hâlin satır sayısı. `rows` ÖZNİTELİĞİ, CSS DEĞİL — ve bu
// ölçülmüş bir karar: `autoGrow` yüksekliği `height: auto` yapıp `scrollHeight`
// okuyarak yazıyor, yani BOŞ bir kutunun yüksekliğini fiilen `rows` belirliyor.
// Yalnız `min-height` düşürmek hiçbir şey değiştirmedi (Chromium'da ölçüldü:
// 57px → 57px), çünkü satır içi `height` o tabanın zaten üstündeydi.
const PROMPT_SATIR_TAM = 2;
const PROMPT_SATIR_KUCUK = 1;

/** Kutunun satır sayısını duruma göre yazar; TEK yazar burası.
 *
 * Küçük hâlin iki koşulu birden gerekiyor: gönderim OLMUŞ olacak VE kutu odakta
 * OLMAYACAK. İkincisi olmazsa yazmaya dönen kullanıcı tek satırlık bir kutuya
 * sıkışırdı — küçülme akışa yer açmak içindi, yazmayı zorlaştırmak için değil.
 * (CSS tarafındaki `:focus-within` ikizi `min-height` tabanını aynı anda geri
 * veriyor; ikisi ayrışırsa hangisi kazanırsa o görünür, o yüzden ikisi de aynı
 * koşulu anlatıyor.)
 *
 * `autoGrow` SONDA çağrılıyor: satır içi `height`i o yazıyor ve yeni `rows`
 * ancak yeniden ölçülünce ekrana çıkıyor.
 */
function syncComposerSatirlari() {
  const el = $("prompt");
  const kucuk = !!$("composer").dataset.sent && document.activeElement !== el;
  el.rows = kucuk ? PROMPT_SATIR_KUCUK : PROMPT_SATIR_TAM;
  autoGrow(el);
}

/** İlk KABUL EDİLEN gönderimden sonraki küçük hâle geçirir.
 *
 * ÇAĞIRANLAR, üçü de "kutu boşaldı" satırının hemen ardında: `run`, `runArena`
 * (core.js) ve `sendChat` (chat.js). Kutunun boşalması bu üç akışta da
 * gönderimin bütün kapılardan geçtiği anın işareti — `submitComposer` ise
 * yalnız uzunluk kapılarını biliyor, o yüzden çapa orada DEĞİL (gerekçe
 * submitComposer'ın başında).
 */
function composerKuculsun() {
  $("composer").dataset.sent = "true";
  syncPromptPlaceholder();   // uzun talimat işini bitirdi
  syncComposerSatirlari();   // …ve satır sayısını SONRA ölçüyor
}

// Odak ekseni: kutu odağa gelince tam boy, odaktan çıkınca (gönderim olduysa)
// küçük. `focus`/`blur` KABARMIYOR, o yüzden dinleyici kutunun kendisinde.
$("prompt").addEventListener("focus", syncComposerSatirlari);
$("prompt").addEventListener("blur", syncComposerSatirlari);

/** İki modun ortak gönderim kapısı — ama KÜÇÜLMENİN ÇAPASI DEĞİL.
 *
 * Çapa bir tur burada durdu ve yanlıştı: buradaki kapılar yalnız UZUNLUK
 * kapıları, oysa gönderimi reddeden asıl kapılar aşağıda — `run()`ın "Önce bir
 * prompt yaz."ı, `runArena`nın iki kapısı, `sendChat`in dördü. Çapa yukarıda
 * kalınca boş bir kutuyla "Üret"e basmak composer'ı KALICI olarak küçültüyor,
 * `data-sent`i yazıyor ve uzun tanıtım yer tutucusunu kısasıyla değiştiriyordu:
 * hiç gönderim olmadan onboarding metni ölüyordu. Küçülme artık kutunun
 * gerçekten boşaldığı üç yerde — o an gönderimin KABUL EDİLDİĞİ andır.
 */
function submitComposer() {
  const promptVal = $("prompt").value.trim();
  if (currentMode === "image") {
    if (promptVal.length > MAX_PROMPT_CHARS) {
      statusEl.textContent = `İstem çok uzun (${promptVal.length}/${MAX_PROMPT_CHARS} karakter).`;
      return;
    }
    run();
  } else {
    if (promptVal.length > 6000) {
      statusEl.textContent = `Mesaj çok uzun (${promptVal.length}/6000 karakter).`;
      return;
    }
    sendChat();
  }
}

$("go").addEventListener("click", submitComposer);

// Dokunmatik girdi: hover'ı VE ince imleci olmayan cihaz. İki koşul birlikte
// aranıyor — tek başına `hover: none` bazı televizyon tarayıcılarında da
// doğru, `pointer: coarse` ise dokunmatik ekranlı bir dizüstüde fare
// takılıyken de doğru kalabiliyor.
//
// SIRA BAĞIMLILIĞI — core.js `folders.js`'ten ÖNCE yüklenmek zorunda:
// `folders.js` bu değeri KENDİ üst düzeyinde okuyor (FOLDER_HINT_DEFAULT /
// FOLDER_HINT_IMPORT). Üst düzey `const` küresel sözlüksel kapsamda duruyor,
// yani sıra bir gün ters çevrilirse sonuç sessiz bir `undefined` değil, TDZ
// `ReferenceError`'ı olur ve `folders.js`'in TAMAMI (klasörler, galeri, seçim
// modu, taşıma) hiç yüklenmez. index.html'deki script sırası bu yüzden
// gelişigüzel değil.
const IS_TOUCH = window.matchMedia("(hover: none) and (pointer: coarse)").matches;

$("prompt").addEventListener("keydown", (e) => {
  // DOKUNMATİKTE Enter GÖNDERMEZ, satır atlar.
  //
  // Masaüstünde "Enter = gönder" doğru kısayol. Telefonda ise sanal klavyenin
  // Enter tuşu SATIR ATLAMANIN TEK YOLU: Shift+Enter'ı Android klavyesinde
  // basmak pratikte mümkün değil. Kural aynı bırakılsaydı çok satırlı bir
  // prompt telefonda hiç yazılamaz, her satır denemesi yarım bir üretim
  // isteği gönderirdi — üstelik üretim ÜCRETLİ. Gönderme yolu #go düğmesi
  // (composer'da, her zaman görünür).
  if (IS_TOUCH && !e.metaKey && !e.ctrlKey) return;

  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitComposer();
  } else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    submitComposer();
  }
});

document.addEventListener("keydown", (e) => {
  if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "j") return;
  if (currentSection !== "studio") return;
  e.preventDefault();
  setMode(currentMode === "image" ? "director" : "image");
});

// Ana referans görsel: null | { kind: "upload", file, label } | { kind: "gallery", id, label }
let source = null;
let uploadPreviewUrl = null;

// Ek referanslar (ana görselin yanında gpt-image-2'ye gönderilir).
// Öğe: { kind: "upload", file, label, src } | { kind: "gallery", id, label, src }
// Sunucudaki MAX_EDIT_IMAGES ile aynı: 1 ana + 3 ek.
const MAX_EDIT_IMAGES = 4;
let extras = [];

// İlerleme yüzdesi KALDIRILDI (eski `startProgress`/`stopProgress`).
// Sağlayıcı tek yanıt döndürüyor, gerçek bir % akışı yok: bar 160ms'lik bir
// setInterval ile ~%90'a doğru asimptotik dolup orada bekliyor, iş bitince
// %100'e sıçrıyordu — yani sayı bir ÖLÇÜM değil, süsleme. Beklemeyi artık
// shimmer kutusu anlatıyor (chat.js `beginResultTurn`, static/pixel-canvas.js)
// ve o hiçbir şey ölçtüğünü iddia etmiyor. Geri getirilecekse ölçülecek bir
// şey de gelmeli: sağlayıcıdan akış (stream) yanıtı.

// ── İndirme ─────────────────────────────────────────────────────────
// Konum seçtiren TEK yol. Galeri kartı da (folders.js) büyüteç de
// (viewer.js) buradan geçiyor: v1.10'daki "İndir düzeltmesi" iki yerde ayrı
// ayrı yapılmıştı ve biri düzeltilip diğeri unutulduğunda kırılma
// "bazen çalışıyor" diye geri döner.
//
// Neden gerekti: `.app`'te WKWebView `ALLOW_DOWNLOADS` ile <a download>'u bir
// macOS kayıt paneline çeviriyor (desktop.py) — kullanıcı konumu SEÇİYOR.
// Tarayıcıda öyle bir panel yok; <a download> dosyayı sormadan indirme
// klasörüne atar. Kullanıcı tarafından bu "app'te indirebiliyorum, web'de
// indiremiyorum" olarak görünüyordu.
//
// Özellik yoksa (paketin WKWebView'ı — WebKit File System Access'i hiç
// uygulamadı — ayrıca Safari ve Firefox) eski <a download> yolu AYNEN kalır:
// pakette davranış değişmiyor.
const SUPPORTS_SAVE_PICKER = typeof window.showSaveFilePicker === "function";

// `/output/<id>.png` → `/api/output/<id>/download`.
//
// NEDEN VAR: `/output/…` bir ÇİZİM adresi (galeri küçük resimleri ve büyütecin
// `<img src>`'i), indirme adresi değil — `Content-Disposition` taşımıyor.
// Android WebView ise HTML'in `download` özniteliğini yok sayıyor: başlıksız bir
// `image/png`'ye gitmek onun çizebileceği bir şey olduğu için kayıt dinleyicisi
// hiç tetiklenmiyor ve indirme sessizce hiç olmuyordu (app.py'deki
// `output_download` notu). Çevirme TEK yerde: üç indirme yolunun hepsi
// `downloadImage`/`downloadViaAnchor`'dan geçiyor.
//
// ETKİSİZ-TEKRARLI: zaten indirme adresi verilirse aynısı dönüyor, yani iki kez
// uygulanması zararsız. Çevrilemeyen adres (blob:, data:, /assets/…) olduğu gibi
// dönüyor — bu işlev bir yönlendirme tablosu, bir doğrulayıcı değil.
const OUTPUT_ONEKI = "/output/";

function indirmeAdresi(url) {
  if (typeof url !== "string" || !url.startsWith(OUTPUT_ONEKI)) return url;
  const ad = url.slice(OUTPUT_ONEKI.length);
  if (!ad.endsWith(".png")) return url;
  // Ad zaten kodlanmış olarak geliyor (chat.js:920 `encodeURIComponent`,
  // folders.js kayıt adını olduğu gibi yazıyor); yeniden kodlamak `%` işaretini
  // ikinci kez kaçırıp adresi bozardı.
  return `/api/output/${ad.slice(0, -".png".length)}/download`;
}

// Android APK'nın enjekte ettiği indirme köprüsü (MainActivity `IndirmeKoprusu`).
//
// NEDEN VAR — `<a download>` Android'de HİÇBİR GARANTİ TAŞIMIYOR. Chromium'da o
// tıklama bir gezinme değil, "renderer kaynaklı indirme" üretiyor; WebView'in
// indirme sistemi yok, isteği tanır tanımaz İPTAL ediyor ve olayı uygulamaya
// `DownloadListener` ile veriyor (AwDownloadManagerDelegate). O halkanın
// kopması — WebView sürümü, bir OEM yaması, `AwContentsClientBridge`in
// bulunamaması — hiçbir hata üretmiyor: tıklama sessizce hiçbir şey yapmıyor.
// Telefonda "indirme çalışmıyor"un tarifi tam olarak bu.
//
// Köprü o halkayı tümden çıkarıyor: adres ve dosya adı doğrudan Kotlin'e
// geçiyor. Yan kazanç, `URLUtil.guessFileName`in de devreden çıkması — adı
// zaten BİLEN taraf frontend, tahmin etmesi gereken bir regex kalmıyor
// (klasör ZIP'lerinin telefona `download.zip` diye inmesinin sebebi oydu).
//
// Köprü YOKSA (tarayıcı, masaüstü paketi) hiçbir şey değişmiyor: eski
// `<a download>` yolu aynen duruyor.
function androidKoprusu() {
  const kopru = window.LumeoIndirme;
  return kopru && typeof kopru.indir === "function" ? kopru : null;
}

function downloadViaAnchor(url, filename) {
  const adres = indirmeAdresi(url);

  const kopru = androidKoprusu();
  if (kopru) {
    // MUTLAK adres: köprünün öbür ucu Kotlin, `location`ı yok. Kotlin ayrıca
    // adresin KENDİ sunucumuzu gösterdiğini doğruluyor.
    kopru.indir(new URL(adres, location.href).href, filename || "");
    return;
  }

  const a = document.createElement("a");
  a.href = adres;
  // Ad AÇIKÇA veriliyor: boş bırakılırsa macOS kayıt panelinin ad alanını
  // WebKit'in URL'den türetmesine kalıyoruz.
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// Kayıt panelini açar, seçilen dosyaya görselin baytlarını yazar.
async function downloadImage(url, filename) {
  // Köprü varsa panel HİÇ denenmiyor: Android'de `showSaveFilePicker` zaten yok,
  // ama bir gün gelirse kayıt paneli köprünün sessizce devre dışı kalması demek
  // olurdu — indirmenin telefonda çalışmasının tek garantisi köprü.
  if (!SUPPORTS_SAVE_PICKER || androidKoprusu()) { downloadViaAnchor(url, filename); return; }

  let handle;
  try {
    handle = await window.showSaveFilePicker({
      suggestedName: filename,
      types: [{ description: "PNG görsel", accept: { "image/png": [".png"] } }],
    });
  } catch (e) {
    // Vazgeçmek hata değil: panel kapatıldıysa hiçbir şey yapma. Panelin
    // KENDİSİ açılamadıysa indirme hiç olmamasındansa eski yola düşülür.
    if (e.name === "AbortError") return;
    downloadViaAnchor(url, filename);
    return;
  }

  try {
    const res = await fetch(indirmeAdresi(url));
    if (!res.ok) throw new Error(`sunucu ${res.status}`);
    const stream = await handle.createWritable();
    await stream.write(await res.blob());
    await stream.close();
    statusEl.textContent = `İndirildi: ${filename}`;
  } catch (e) {
    // Hem söyle hem kurtar: durum satırı büyüteç açıkken perdenin ARKASINDA
    // kalıyor, o yüzden tek başına yeterli değil — geri düşüş dosyayı hiç
    // olmazsa indirme klasörüne bırakır. `createWritable` yazmayı takas
    // dosyasında biriktirdiği için yarım dosya kalmaz.
    statusEl.textContent = `İndirilemedi (${e.message}); indirme klasörüne kaydediliyor.`;
    downloadViaAnchor(url, filename);
  }
}

function clearUploadPreviewUrl() {
  if (uploadPreviewUrl) {
    URL.revokeObjectURL(uploadPreviewUrl);
    uploadPreviewUrl = null;
  }
}

// Merkez önizlemede görünen sunucu kaydı: logo/motto/banner bindirmesinin hedefi.
// Yüklenmiş (henüz kaydedilmemiş) bir görsel gösterilirken null'dır.
let currentImage = null;

function setCurrentImage(rec) {
  currentImage = rec;
  $("logo-add-btn").disabled = !rec;
}

function showPreview(rec) {
  setCurrentImage(rec);
}

// Referans durumunu arayüze yansıt: chip + ana buton etiketi + ek görsel şeridi
function renderSource() {
  const chip = $("ref-chip");
  const chipImg = $("ref-chip-img");
  const goBtn = $("go");
  if (source) {
    $("ref-label").textContent = source.label;
    chip.hidden = false;
    if (chipImg && uploadPreviewUrl) {
      chipImg.src = uploadPreviewUrl;
      chipImg.hidden = false;
    } else if (chipImg) {
      chipImg.hidden = true;
      chipImg.removeAttribute("src");
    }
    if (currentMode === "image") {
      goBtn.textContent = extras.length ? "Görselleri birleştir" : "Görseli düzenle";
    } else {
      goBtn.textContent = "Gönder";
    }
  } else {
    chip.hidden = true;
    if (chipImg) { chipImg.hidden = true; chipImg.removeAttribute("src"); }
    if (currentMode === "image") {
      goBtn.textContent = "Üret";
    } else {
      goBtn.textContent = "Gönder";
    }
  }
  // Ek görsel yalnızca bir ana görsel varken anlamlı
  $("extra-row").hidden = !source;
  renderExtras();
  // Palet notu referans görsel varken değişir (üretim ≠ düzenleme ifadesi)
  renderPalettePanel();
  // Referans görsel eklenip kaldırıldığında kapı yeniden sorulmalı:
  // düzenlemeyi desteklemeyen bir model seçiliyken referans varsa üretim
  // engelli olmak zorunda (bkz. goBlockReason).
  if (typeof syncGoGate === "function") syncGoGate();
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

// Ek referans reddinin TEK kaynağı (plan B6). İki çağıranı var ve ikisi
// gerekçeyi FARKLI yüzeylerde gösteriyor: `canAddExtra` #status'a yazar,
// Medya seçicisi #picker-note'a. Cümleler burada bir kez geçiyor — iki yere
// kopyalansaydı biri güncellenip diğeri bayatlardı (test sayıyor).
//
// K26: "Önce ana görseli seç." parantezsiz. Eski hâli "(Görsel ekle veya
// galeriden Düzenle)" diyordu; galeri kartının "+Ek" düğmesi Adım 11'de
// ölçümle kaldırıldığı için (§0.9) o kurtuluş yolu ARTIK YOK — cümle var
// olmayan bir kapıyı tarif ediyordu.
//
// Boş dize = engel yok. Çağıranlar `if (why)` ile okuyor.
function extraBlockReason(rec) {
  if (!source) return "Önce ana görseli seç.";
  if (extraSlotsLeft() <= 0) return `En fazla ${MAX_EDIT_IMAGES} görsel gönderilebilir.`;
  if (!rec) return "";
  if (source.kind === "gallery" && source.id === rec.id) return "Bu görsel zaten ana referans.";
  if (extras.some((it) => it.kind === "gallery" && it.id === rec.id)) {
    return "Bu görsel zaten ek referans listesinde.";
  }
  return "";
}

function canAddExtra() {
  const why = extraBlockReason(null);
  if (why) { statusEl.textContent = why; return false; }
  return true;
}

function addExtraUpload(file) {
  if (!canAddExtra()) return;
  if (!isAcceptedUpload(file)) {
    statusEl.textContent = "PNG, JPEG veya WebP bir görsel seç.";
    return;
  }
  extras = [...extras, { kind: "upload", file, label: file.name, src: URL.createObjectURL(file) }];
  statusEl.textContent = "";
  renderSource();
}

// Adım 11'den Adım 12'ye bekleyen dikişti; çağıranı artık Medya seçicisi
// (folders.js, "Ek olarak ekle"). Adı korundu — plan B6/B7 bunu şart koşuyordu.
//
// Ret gerekçesini KENDİ yazmıyor, `extraBlockReason`'dan alıp DÖNDÜRÜYOR:
// çağıran onu kendi görünür yüzeyine koyuyor. Eskiden buradan doğrudan
// `statusEl`e yazılıyordu ve Medya görünümündeyken #status gizli bir kabın
// içinde kalıyordu — eylem çalışıyor, geri bildirimi görünmüyordu (§0.9).
// Dönüş: engel varsa gerekçe cümlesi, eklendiyse boş dize.
function addGalleryExtra(rec) {
  const why = extraBlockReason(rec);
  if (why) return why;
  extras = [...extras, {
    kind: "gallery", id: rec.id,
    label: (rec.prompt || rec.id).slice(0, 40),
    src: `/output/${rec.filename}`,
  }];
  renderSource();
  return "";
}

function setUploadSource(file) {
  if (!isAcceptedUpload(file)) {
    statusEl.textContent = "PNG, JPEG veya WebP bir görsel seç.";
    return;
  }
  clearUploadPreviewUrl();
  source = { kind: "upload", file, label: `Yüklendi: ${file.name}` };
  uploadPreviewUrl = URL.createObjectURL(file);
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

function setGallerySourceById(id, prompt) {
  const rec = (typeof historyCache !== "undefined" && historyCache)
    ? historyCache.find((r) => r.id === id)
    : null;
  if (rec) {
    setGallerySource(rec);
  } else {
    setGallerySource({ id, prompt: prompt || id, filename: `${id}.png` });
  }
  showSection("studio");
  statusEl.textContent = "Görsel ana referans olarak ayarlandı.";
}



function clearSource() {
  clearUploadPreviewUrl();
  clearExtras();
  source = null;
  $("file-input").value = "";
  renderSource();
}

// Tek eylem: referans varsa düzenle, yoksa üret
/** Turun ORTAK kimliği. `storage._SAFE_ID` ile uyumlu 12 hex.
 *
 * İSTEMCİ üretiyor çünkü sütunlar AYRI isteklerle gidiyor ve hepsinin aynı
 * etiketi taşıması gerekiyor; sunucudan almak turun başına fazladan bir
 * gidiş-dönüş koyardı. Çakışma riski yok: etiket yalnızca kayıtları
 * gruplamak için, kimlik uzayı da tura özel.
 */
function arenaKimlik() {
  const ham = (typeof crypto !== "undefined" && crypto.randomUUID)
    ? crypto.randomUUID().replace(/-/g, "")
    : Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2);
  return ham.replace(/[^0-9a-f]/g, "").slice(0, 12).padEnd(12, "0");
}

/** ARENA TURU: aynı prompt, N model, N PARALEL istek.
 *
 * `run()`ın kardeşi ve ondan ayrı, çünkü akışın üç yeri birden farklı: istek
 * çoğul, bekleme sütunlu, başarısızlık KISMİ. Ortak yerler (palet okuma,
 * oturum etiketi, prompt kutusunun boşaltılıp hatada geri konması) aynı
 * fonksiyonlardan geçiyor.
 *
 * `Promise.all` bir BARİYER değil: her sütun kendi `then`inde ekrana basılıyor
 * (`fillArenaSlot`), yani ilk biten ilk görünüyor. Beklenen tek şey turun
 * KAPANIŞI — döküm kaydı ve `#go` kilidi hepsi bitince açılıyor.
 */
async function runArena(prompt) {
  // Klavye yolu (⌘/Ctrl+Enter) `#go.disabled`a hiç bakmıyor, yani kapı burada
  // yeniden sorulmak zorunda — ve TAMAMI sorulmak zorunda. Öncesinde yalnız
  // sütun SAYISI ölçülüyordu ve o eksiklik `goBlockReason`ın referans engelini
  // ("Arena düzenlemeyle çalışmıyor") ölü bir metne çeviriyordu: referans
  // ekliyken Enter, kaynağı sessizce düşürüp N tane ÜCRETLİ istek atıyordu —
  // üstelik #go "Görseli düzenle" yazarken ve kullanıcı referansı EKRANDA
  // görürken. Kapının tek sahibi `goBlockReason`; burada ikinci bir kopyası
  // kurulmuyor, olduğu gibi soruluyor.
  const engel = goBlockReason();
  if (engel) { statusEl.textContent = engel; return; }
  // Sayı kapıdan SONRA da ölçülüyor, çünkü kapı SEÇİMİ sayıyor
  // (`arenaSecimi`) ama koşacak olan sütunlar `arenaSutunlari` — katalogda
  // bulunmayan bir id orada düşüyor (`filter(Boolean)`), yani ikisi ayrışabilir.
  const sutunlar = arenaSutunlari();
  if (sutunlar.length < ARENA_MIN) {
    statusEl.textContent = `Arena için en az ${ARENA_MIN} model seç.`;
    return;
  }

  $("prompt").value = "";
  autoGrow($("prompt"));
  composerKuculsun();   // kutu boşaldı ⇒ gönderim KABUL EDİLDİ
  syncAskDirector();

  const pal = readPaletteOpts();
  const sessionId = openSessionId();
  const arenaId = arenaKimlik();
  const pending = beginArenaTurn(prompt, sutunlar);

  runBusy = true;
  syncGoGate();
  statusEl.textContent = `${sutunlar.length} model üretiyor…`;

  const sonuclar = new Array(sutunlar.length).fill(null);
  const hatalar = [];
  // `try/finally` `run()`ın deseni ve AYNI gerekçeyle: `runBusy = false` düz
  // akışta duruyordu, oysa aşağıdaki `finishArenaTurn`/`loadHistory` kendi
  // try/catch'ini TUTMUYOR. Orada kopan bir bağlantı `runBusy`i true bırakıp
  // #go'yu sayfa yenilenene kadar "Üretim sürüyor…" diye kilitliyordu —
  // görseller çoktan diske düşmüşken, yani kilidin sebebi de yalan.
  try {
    await Promise.all(sutunlar.map(async (s, i) => {
      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          // Adet sütun başına 1 (bkz. arenaUygula). `arena_id` bayat bir
          // sunucuda `extra="forbid"`e takılıp 422 döner ve `detailText` bunu
          // Türkçe bir "sunucu eski sürüm" mesajına çeviriyor — sessiz sapma yok.
          body: JSON.stringify({ prompt, size: s.size, quality: s.quality, n: 1,
                                 model: s.model.id, arena_id: arenaId,
                                 folder_id: currentFolder ? currentFolder.id : null,
                                 ...(sessionId ? { session_id: sessionId } : {}),
                                 ...pal }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(detailText(err) || `Hata (${res.status})`);
        }
        const { images } = await res.json();
        if (!images.length) throw new Error("Sunucu görsel döndürmedi.");
        const kayit = { image_ids: images.map((r) => r.id),
                        params: { kind: "generate", size: s.size,
                                  quality: s.quality, model: s.model.id,
                                  arena_id: arenaId } };
        sonuclar[i] = kayit;
        fillArenaSlot(pending, i, kayit, arenaId);
        // Önizleme İLK BİTENE değil ilk SÜTUNA ait: sıra kullanıcının seçtiği
        // sıra ve yarışın hızlısı, karşılaştırmanın birincisi değil.
        if (i === 0) showPreview(images[0]);
      } catch (e) {
        hatalar.push(`${s.model.short_label || s.model.label}: ${e.message}`);
        failArenaSlot(pending, i, e.message);
      }
    }));

    const tutan = sonuclar.filter(Boolean);
    // Sayı ÖNCE, sebep sonra: "2/3" turun sonucunu tek bakışta veriyor, düşen
    // sütunun sebebi de kaybolmuyor (uyarıların listede toplanma kuralı).
    //
    // Özet döküm/geçmiş adımından ÖNCE yazılıyor: o adım patlarsa turun
    // sonucu yine ekranda kalmalı, hata metni aşağıda onun ARDINA ekleniyor.
    const ozet = `${tutan.length}/${sutunlar.length} model üretti.`;
    statusEl.textContent = hatalar.length ? `${ozet} ${hatalar.join(" · ")}` : ozet;
    if (!tutan.length) {
      // HİÇ sütun tutmadı: tur geçmişte kalmıyor ve prompt kutuya geri dönüyor
      // (`run`ın kuralı) — yeniden denemek onu ikinci kez eklemesin.
      dropPendingTurn(pending);
      $("prompt").value = prompt;
      autoGrow($("prompt"));
      syncAskDirector();
    } else {
      await finishArenaTurn(pending, tutan);
      await loadHistory();
    }
  } catch (e) {
    // Buraya YALNIZ döküm/geçmiş adımı düşüyor (sütun hataları kendi
    // `catch`inde kalıyor). Görseller diskte, satır ekranda: söylenmezse
    // kullanıcı sayfayı yenileyene kadar EKSİK bir geçmiş görür ve bunu
    // açıklayamaz — "sessiz sapma yasak" duruşunun buradaki karşılığı.
    statusEl.textContent = `${statusEl.textContent} Geçmiş yenilenemedi: ${e.message}`;
  } finally {
    runBusy = false;
    syncGoGate();   // kapının tek yazarı (run()'ın deseni)
  }
}

async function run() {
  const prompt = $("prompt").value.trim();
  if (!prompt) { statusEl.textContent = "Önce bir prompt yaz."; return; }
  // ARENA kendi akışı: N istek, N sütun, kısmi başarısızlık.
  if (arenaAcik) return runArena(prompt);

  $("prompt").value = "";
  autoGrow($("prompt"));
  composerKuculsun();   // kutu boşaldı ⇒ gönderim KABUL EDİLDİ
  syncAskDirector();


  const size = $("size").value;
  const quality = $("quality").value;
  const n = $("n").value;
  // TEK yerde okunup İKİ dala aynı değişkenden veriliyor. Paletin dersi
  // (aşağıda, FormData döngüsünün yorumu): alanları elle saymak bir kez
  // `palette_id`'yi düşürmüştü.
  const model = $("model").value;
  const editing = source !== null;
  // Palet İKİ dalın da payload'ına eklenmeli — biri atlanırsa o yolda renk
  // sessizce kaybolur. Palet kapalıyken {} döner, böylece gövde bugünküyle
  // bayt bayt aynı kalır ve extra="forbid" boş bir alan görmez.
  const pal = readPaletteOpts();

  // ── Birleşik oturum (tasarım §5 · §4.2) ──
  // Görsel modu artık kendi oturumunu BAŞLATIYOR (Adım 8, K10'un ikinci yarısı):
  // prompt yapısı gereği bir döküm turu, o yüzden koşulsuz basılıyor. Oturum
  // yoksa `persistThread` üretimden SONRA POST ile açıyor.
  //
  // K10'un durduğu yer korunuyor: üretim isteğine UYDURMA id konmuyor. Oturum
  // henüz yazılmadığı için ilk partinin görsel kaydında ters bağ (`session_id`)
  // olmuyor — ileri bağ (`result.image_ids`) tam, dökümün çizdiği de o.
  //
  // chat.js'in adlarına OLAY ANINDA dokunuluyor (tıklama) — dosyanın başındaki
  // yükleme sırası kuralının izin verdiği tek yol.
  const sessionId = openSessionId();
  // Kullanıcının repliği üretimden ÖNCE döküme basılıyor (sendChat'in sırası):
  // beklerken kendi cümlesini görüyor. Başarısızlıkta geri alınıyor — diske de
  // hiçbir şey yazılmamış olur, çünkü yazan taraf başarıdan sonraki sonuç kaydı.
  const pending = beginResultTurn(prompt);

  let request;
  if (editing) {
    const fd = new FormData();
    fd.append("prompt", prompt);
    fd.append("size", size);
    fd.append("quality", quality);
    fd.append("n", n);
    fd.append("model", model);
    if (source.kind === "upload") fd.append("file", source.file);
    else fd.append("source_id", source.id);
    if (currentFolder) fd.append("folder_id", currentFolder.id);
    if (sessionId) fd.append("session_id", sessionId);
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
      // `session_id` KOŞULLU: oturum yoksa alan hiç gönderilmiyor, böylece
      // gövde bugünküyle bayt bayt aynı kalıyor (palet dalının gerekçesi).
      body: JSON.stringify({ prompt, size, quality, n: parseInt(n, 10), model,
                             folder_id: currentFolder ? currentFolder.id : null,
                             ...(sessionId ? { session_id: sessionId } : {}),
                             ...pal }),
    });
  }

  runBusy = true;
  syncGoGate();
  statusEl.textContent = !editing ? "Üretiliyor…"
    : extras.length ? "Görseller birleştiriliyor…" : "Düzenleniyor…";
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
    // atar ve 200 döner. Tek savunma yanıtın alanı geri YANKILAMASI.
    //
    // Uyarılar bir LİSTEDE toplanıyor, if/else zincirinde değil: zincir, ikisi
    // birden düştüğünde yalnızca birini söylüyordu. Model ilk sırada çünkü
    // sonucu İKİ yönden bozuyor — yanlış estetik VE yanlış fatura.
    const warnings = [];
    if (images[0] && images[0].model !== model) {
      // `undefined !== "azure-gpt-image-2"` eski bir sunucuda DOĞRU sonuç:
      // alanı hiç yankılamayan sunucu gerçekten de alanı yok saymıştır.
      warnings.push(`Model uygulanmadı: "${model}" istendi, sunucu `
        + `"${images[0].model || "bilinmiyor"}" ile üretti — sunucu eski sürüm `
        + "görünüyor, ./run.sh ile yeniden başlat.");
    }
    if (pal.palette_hex && images[0] && !images[0].palette) {
      warnings.push(
        "Palet uygulanmadı: sunucu eski sürüm görünüyor — ./run.sh ile yeniden başlat.");
    } else if (images[0] && images[0].palette && images[0].palette.applied === false) {
      // Ek, prompt karakter sınırına sığmadığı için düşürüldü. Kayıtta palet
      // görünür ama prompt'a girmedi; söylenmezse kullanıcı renksiz sonucu
      // açıklayamaz. Eski kayıtlarda alan yok → `=== false` bilinçli.
      warnings.push(
        "Palet prompt'a sığmadı (4000 karakter sınırı): görsel renk " +
        "yönlendirmesi olmadan üretildi. Prompt'u kısaltıp tekrar dene.");
    }
    if (warnings.length) statusEl.textContent = warnings.join(" · ");
    // Sonuç kaydı döküme: konuşma ve üretilen görseller aynı akışta (tasarım §5).
    // `image_ids` sunucunun döndürdüğü kayıtlardan geliyor; adet ayrı
    // taşınmıyor, dizinin uzunluğundan okunuyor.
    // `model` de params'a: sonuç kartı hangi modelin ürettiğini söyleyebilmeli
    // ve döküm kaydı üretimin tam bağlamını taşımalı. Sunucu tarafı
    // (`models.ResultParams`) alanı v0.6'da öğrendi — bu iki taraf AYNI
    // sürümde inmek zorunda, yoksa `extra="forbid"` kaydı 422 yapar ve
    // görsel diske düşerken oturum turu sessizce kaybolur.
    await appendResultTurn(pending, images.map((r) => r.id),
                           { kind: editing ? "edit" : "generate", size, quality,
                             model });
    await loadHistory();
  } catch (e) {
    // BAŞARISIZ TUR GEÇMİŞTE KALMAZ (sendChat'in kuralı): kalsaydı döküme
    // cevapsız bir kullanıcı turu düşer, yeniden denemek onu ikinci kez
    // eklerdi. Prompt kutuda duruyor — core.js kutuyu hiç temizlemiyor.
    dropPendingTurn(pending);
    $("prompt").value = prompt;
    autoGrow($("prompt"));
    syncAskDirector();
    statusEl.textContent = e.message;
  } finally {
    runBusy = false;
    syncGoGate();   // kapının tek yazarı — yapılandırma/mod/model hepsini birden görüyor
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
    if (currentImage && currentImage.id === rec.id) setCurrentImage(null);
    renderSource();
    statusEl.textContent = "Silindi.";
    await loadHistory();
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

