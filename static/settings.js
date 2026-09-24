// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
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
let chatConfigured = false; // chat.js okuyor (o dosya BUNDAN SONRA yükleniyor)

/** Kullanıcıyı Ayarlar'a yönlendiren ek — düğmenin ADIYLA, glifle DEĞİL.
 *  Öncesinde "(sağ üstteki ⚙)" yazıyordu ve iki kusuru vardı: (1) üst şeritteki
 *  gerçek düğme hatlı bir SVG dişli (index.html, `aria-label="Ayarlar"`), yani
 *  glif düğmenin görünüşünü YANLIŞ söylüyordu; (2) "emoji ikon yok" ölçütünü
 *  (flow-redesign §11) tartışmaya açıyordu.
 *  SABİT olmasının gerekçesi ayrı ve bir kusuru kapatıyor: aynı dize ÜÇ kez
 *  elle yazılıydı ve biri aşağıdaki `includes` NÖBETÇİSİ. Biri değişip öteki
 *  kalsa hata VERMEZ — nöbetçi bir daha hiç tutmaz ve kullanıcı ayarları
 *  düzelttikten sonra durum satırı ekranda kalırdı. */
const AYARLAR_EKI = t("settings.button_suffix");

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
    ? t("settings.key_saved_placeholder")
    : t("settings.azure_key_placeholder");

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
      ["set-fal-key", "fal", t("settings.fal_key_placeholder")],
    ]) {
      $(alan).placeholder = s.providers[kimlik] ? t("settings.key_saved_placeholder") : bos;
    }
    // Bayraklar SAKLANIYOR: kartlar pencere açıldığında çiziliyor ve o an
    // elde yalnız bu sözlük oluyor. Kaydet'ten sonra applyConfigured yeniden
    // koştuğu için rozetler de kendiliğinden tazeleniyor.
    saglayiciDurumu = s.providers;
    // KAYNAK (Faz 2 / 6): `providers` "kurulu mu", `kaynaklar` "kimin
    // anahtarıyla" — `kullanici` | `platform` | null. Aynı yanıtta, aynı
    // guard'la: GET ve POST ikisini de taşıyor (services/modeller.py).
    if (s.kaynaklar !== undefined) saglayiciKaynagi = s.kaynaklar || {};
    platformNotlariniCiz();
    syncProviderPick($("set-provider").value);
  }

  // Açılış mesajı artık SEÇİLİ MODELE bakıyor, Azure'a değil: yalnızca OpenAI
  // anahtarı olan bir kullanıcıya "Azure ayarlarını gir" demek onu hiç
  // ihtiyacı olmayan bir forma yönlendirirdi.
  const kapali = goBlockReason();
  if (kapali) {
    statusEl.textContent = `${kapali} ${AYARLAR_EKI}`;
  } else if (statusEl.textContent.includes(AYARLAR_EKI)) {
    // İKİNCİ bir nöbetçi daha vardı: `startsWith("Başlamak için")`. ÖLÜYDÜ —
    // depoda o cümleyi yazan hiçbir yer kalmamış, yani koşul hiç doğru
    // olmuyordu. Çeviriyle birlikte zararsızlıktan çıkıyordu: sabit bir Türkçe
    // dizeye bakan bir nöbetçi İngilizce arayüzde hiçbir zaman tutmaz, yani
    // "ölü ama masum" olan şey "dile bağlı ve sessizce yanlış" olurdu.
    //
    // Kalan nöbetçi `t()`den geçen AYNI dizeyi arıyor, yani dil değişse de
    // iki taraf birlikte değişiyor — settings.js'in en başındaki
    // "aynı dize ÜÇ kez elle yazılıydı" dersinin devamı.
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

  // ── Web yapısı: güncelleme denetimi KAPALI ──
  // Sunucu `web: true` diyorsa (GET /api/settings; DATABASE_URL verilmiş —
  // routers/ayarlar.py) "şimdi kontrol et" satırı, tercih anahtarı ve onun
  // ipucu gizleniyor: web'de sunucuyu işleten güncelliyor, kullanıcıya
  // "yeni sürüm var" demek yapamayacağı bir iş söylemek olurdu. `=== true`:
  // POST /api/settings yanıtında alan YOK (`version` guard'ıyla aynı sebep),
  // alan hiç gelmezse (bayat sunucu) hiçbir şey gizlenmez. index.html
  // DEĞİŞMİYOR (dondurulmuş kabuk aynı sayfayı kullanıyor): çapalar
  // düğmenin ve anahtarın kendi `<p>`/`<label>` ebeveyni, ipucu etiketin
  // hemen ardındaki `<p>` — anahtarla aynı bloğun parçası.
  if (s && s.web === true) webKipineGec();

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
  // Sunucu alanları döndürmeye devam ediyor (routers/ayarlar.py) — web'de
  // `null` (Faz 2 / 6: yol sunucunun diski, kullanıcının değil), kabukta
  // dosya yolu; ekranda okuyan bir satır olmadığı için gizlenecek şey yok.
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
  const etiket = varMi
    ? t("settings.btn_update_available", { surum: g.surum })
    : t("settings.title");
  dis.title = etiket;
  dis.setAttribute("aria-label", etiket);
}

/** Web yapısında güncelleme arayüzünü gizler (gerekçe `applyConfigured`ta). */
function webKipineGec() {
  const kontrol = $("settings-update-check");
  if (kontrol) kontrol.closest("p").hidden = true;
  const anahtar = $("pref-guncelleme");
  if (!anahtar) return;
  const etiket = anahtar.closest("label");
  etiket.hidden = true;
  const ipucu = etiket.nextElementSibling;
  if (ipucu && ipucu.classList.contains("field-note")) ipucu.hidden = true;
}

/** "Şimdi kontrol et" — TTL'i baypas eden, cevabı BEKLEYEN elle kontrol.
 *
 *  NEDEN AYRI BİR YOL: `yoklaGuncelleme` yalnız SORUYOR (`GET`), sunucunun
 *  önbelleği bayatsa arka plan kontrolünün bitmesini umuyor. Önbellek "taze"
 *  ama cevabı eski olduğunda (24 saatlik TTL, ondan hızlı çıkan yayınlar) o
 *  yoklama sonsuza kadar aynı eski cevabı okur. `POST` sunucuya kontrolü
 *  ZORLA koşturuyor.
 *
 *  DÖRT DURUM, DÖRT CÜMLE: sunucunun `durum` alanı olmasa "güncelsin" ile
 *  "soramadım" ayırt edilemezdi — ikisinde de `guncelleme` alanı `null` gelir.
 *  Düğmeye basan kullanıcı için o fark cevabın kendisi; sessizlik ya da tek
 *  bir "bir şey yok" cümlesi, kontrolün çalışıp çalışmadığını gizlerdi.
 *
 *  `uygulaGuncelleme` HER durumda çağrılıyor, yalnız "yeni"de değil: cevap
 *  `null` ise satırın ve rozetin GİZLENMESİ gerekiyor. Kullanıcı bu arada
 *  güncellemiş olabilir ve ekranda asılı kalan bir "yeni sürüm var" satırı,
 *  hiç görünmeyen bir satır kadar yanlış. */
async function simdiKontrolEt() {
  const dugme = $("settings-update-check");
  const yazi = $("settings-update-check-status");

  // Düğme kilitleniyor: her basış GERÇEK bir GitHub isteği ve anonim API
  // saatte 60 istekle sınırlı (guncelleme.py'deki TTL gerekçesi). Üst üste
  // basan bir kullanıcının o sınırı kendi başına yakmasının anlamı yok.
  dugme.disabled = true;
  yazi.textContent = t("settings.update_checking");
  try {
    const res = await fetch("/api/guncelleme", { method: "POST" });
    if (!res.ok) throw new Error(t("err.http", { durum: res.status }));
    const cevap = await res.json();
    uygulaGuncelleme(cevap.guncelleme);
    if (cevap.durum === "yeni") {
      yazi.textContent = t("settings.update_found", { surum: cevap.guncelleme.surum });
    } else if (cevap.durum === "guncel") {
      yazi.textContent = t("settings.update_current");
    } else if (cevap.durum === "kapali") {
      yazi.textContent = t("settings.update_off");
    } else {
      yazi.textContent = t("settings.update_failed");
    }
  } catch {
    // Ağ hatası ile sunucunun "hata" durumu kullanıcı için AYNI şey: kontrol
    // yapılamadı. İkisini iki ayrı cümleye ayırmak, hiçbir kararı
    // değiştirmeyen bir ayrım olurdu.
    yazi.textContent = t("settings.update_failed");
  } finally {
    dugme.disabled = false;
  }
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
      return; // bulundu: yoklama biter
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
    // Web yapısında (`s.web`) hiç: sunucu `{"web": true}` döner, yoklamak üç
    // boş istek olurdu.
    if (!s.guncelleme && s.web !== true) yoklaGuncelleme();
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
    statusEl.textContent = t("settings.status_unavailable", { ek: AYARLAR_EKI });
    if (openIfMissing) openSettings();
  }
}

/** Sağlayıcı bayrakları (`GET /api/settings` → `providers`). AYRI bir
 *  değişken çünkü kartlar pencere AÇILIRKEN çiziliyor, bayraklar ise
 *  `/api/settings` döndüğünde geliyor — iki ayrı zaman. `seciliModelTercihi`
 *  ile aynı desen. */
let saglayiciDurumu = {};
/** `GET /api/settings` → `kaynaklar` ({kimlik: "kullanici" | "platform" | null}, Faz 2 / 6). */
let saglayiciKaynagi = {};

/** Sağlayıcı grubunun altına "platform sağlıyor" notu ve "kendi anahtarımı sil"
 *  düğmesi — index.html DEĞİŞMİYOR (çapalar `#prov-<p>` grupları), elemanlar
 *  ilk çizimde yaratılıp sonra yalnız gizlenip gösteriliyor.
 *
 *  Not yalnız kaynak `platform`ken: kullanıcı kutuyu boş bırakabilir, üretim
 *  platformun anahtarıyla çıkar; kendi anahtarını girerse o kazanır (sunucunun
 *  çözüm sırası, services/platform_anahtari.py). Düğme yalnız kaynak
 *  `kullanici`yken: yalnızca-yazılır formda kutuyu boşaltmak "dokunmadım"
 *  demek (saveSettings'in gerekçesi), yani anahtarı geri almanın tek yolu
 *  açık bir eylem — `POST /api/settings` `anahtar_sil: [kimlik]`. */
function platformNotlariniCiz() {
  for (const [grup, kimlik] of [
    ["prov-azure", "azure_image"],
    ["prov-openai", "openai"],
    ["prov-gemini", "gemini"],
    ["prov-fal", "fal"],
  ]) {
    const kok = $(grup);
    if (!kok) continue;
    let not = kok.querySelector(".platform-notu");
    if (!not) {
      not = document.createElement("p");
      not.className = "field-note platform-notu";
      not.textContent = t("settings.platform_sagliyor");
      kok.appendChild(not);
    }
    // Kendi anahtarı kayıtlıyken düğmenin üstünde bir cümle (Faz 2 / 8): "Kendi
    // anahtarımı sil" tek başına bir TALİMAT gibi okunuyordu (sahibin geri
    // bildirimi); not, düğmenin bir DURUMU değiştirdiğini söyler.
    let kendi = kok.querySelector(".kendi-anahtar-notu");
    if (!kendi) {
      kendi = document.createElement("p");
      kendi.className = "field-note kendi-anahtar-notu";
      kendi.textContent = t("settings.kendi_anahtar_kullaniliyor");
      kok.appendChild(kendi);
    }
    let sil = kok.querySelector(".anahtar-sil");
    if (!sil) {
      sil = document.createElement("button");
      sil.type = "button";
      sil.className = "btn-secondary anahtar-sil";
      sil.textContent = t("settings.anahtar_sil");
      sil.addEventListener("click", () => anahtariSil(kimlik, sil));
      kok.appendChild(sil);
    }
    const kaynak = saglayiciKaynagi[kimlik] || null;
    not.hidden = kaynak !== "platform";
    kendi.hidden = kaynak !== "kullanici";
    sil.hidden = kaynak !== "kullanici";
  }
}

/** Kullanıcının KENDİ anahtarını siler; sunucu yeni durumu döndürür (platforma düşmüş olabilir). */
async function anahtariSil(kimlik, dugme) {
  const st = $("settings-status");
  dugme.disabled = true;
  st.textContent = t("common.saving");
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anahtar_sil: [kimlik] }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || t("err.http", { durum: res.status }));
    }
    applyConfigured(await res.json());
    st.textContent = t("settings.anahtar_silindi");
  } catch (e) {
    st.textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
}

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
  // İKİ KATALOG birden taranıyor ve bu bir tamlık düzeltmesi değil, ÖLÇÜLMÜŞ
  // bir sessiz kusur: fal yalnız VİDEO sağlayıcısı, yani `imageModels`te HİÇ
  // görünmüyor ve tek başına o listeye bakmak fal'ın işaretini kalıcı olarak
  // kaybettirirdi. Kusur sessiz olurdu — kutu boş kalır, konsolda bir şey
  // yazmaz (test_provider_logos.py'nin başlığındaki sınıfın aynısı).
  const m =
    imageModels.find((x) => x.provider === deger) || videoModels.find((x) => x.provider === deger);
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
    // Üç hâl (Faz 2 / 6): kendi anahtarı kayıtlı / platform sağlıyor / yok.
    const kaynak = saglayiciKaynagi[SAGLAYICI_KIMLIGI[o.value] || o.value] || null;
    rozet.textContent = t(
      kaynak === "platform"
        ? "settings.platform_badge"
        : saglayiciKayitli(o.value)
          ? "settings.saved"
          : "settings.not_saved",
    );
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
  $("set-provider-label").textContent = secenek ? secenek.textContent : t("settings.pick_provider");
  const kutu = $("set-provider-ic");
  const logo = saglayiciLogosu(secili);
  if (!logo) {
    kutu.replaceChildren();
    return;
  }
  const img = document.createElement("img");
  img.src = logo;
  img.alt = "";
  kutu.replaceChildren(img);
}

/** Seçilen sağlayıcının alan grubunu gösterir, ötekileri gizler. */
function syncProviderFields() {
  const secili = $("set-provider").value;
  for (const p of ["azure", "openai", "gemini", "fal"]) {
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
  // "Kredi" bölmesi açılırken bir kez `/api/kredi` (Faz 3 / 6): içerik eldeki
  // hâlden hemen çizilir, taze cevap gelince yeniden — ikinci istek yok, composer
  // satırı da aynı cevaptan yenilenir (core.js `krediYenile`).
  if (ad === "kredi") {
    krediBolmesiniCiz();
    krediYenile();
  }
}

// ── Kredi bölmesi (Faz 3 / 6) ───────────────────────────────────────
// İçerik DİNAMİK, index.html'de yalnız kök (#settings-kredi): #settings-hesap
// satırının deseni — belgenin metin çapalarına dokunulmuyor. Kaynak core.js'in
// `krediDurumu`su (`GET /api/kredi`): toplam ve iki kova (Faz 4 / 2, K3: `bakiye`
// aylık hibe — devretmez; `paket_bakiye` satın alınan kredi — devreder), plan,
// aylık hibe ve tarihi, plan kuralları (filigran/video — `PLANLAR`dan, arayüz
// kataloğu tekrar etmez), son 20 hareket. Hareketin işi varsa düğme paneldeki
// satıra gider (`kromisIsler.goster`).
//
// Anahtarlar TABLODA ve harfiyen (isler.js `DURUM_ANAHTARI`nın gerekçesi):
// tests/test_i18n.py betikleri anahtar biçimine uyan dizelerle tarıyor.
const KREDI_PLAN_ANAHTARI = {
  free: "kredi.plan_free",
  temel: "kredi.plan_temel",
  pro: "kredi.plan_pro",
};
// `HAREKET_TURLERI`nin (services/tablolar.py) her türü burada — bekçi
// tests/test_kredi_route.py: tanınmayan tür "düzeltme"ye düşer, sessiz kalmaz.
const KREDI_HAREKET_ANAHTARI = {
  hibe: "kredi.tur_hibe",
  rezerv: "kredi.tur_rezerv",
  onay: "kredi.tur_onay",
  iade: "kredi.tur_iade",
  duzeltme: "kredi.tur_duzeltme",
  sona_erme: "kredi.tur_sona_erme",
  paket: "kredi.tur_paket",
};

/** `zaman.damga_utc` (`…Z`) → kullanıcının dilinde kısa tarih(+saat). */
function krediTarihi(damga, saatli) {
  const d = new Date(damga);
  if (Number.isNaN(d.getTime())) return damga || "";
  return saatli
    ? d.toLocaleString(KROMIS_DIL, { dateStyle: "short", timeStyle: "short" })
    : d.toLocaleDateString(KROMIS_DIL, { dateStyle: "long" });
}

function krediNotu(metin, sinif) {
  const p = document.createElement("p");
  p.className = sinif ? `field-note ${sinif}` : "field-note";
  p.textContent = metin;
  return p;
}

function krediHareketSatiri(h) {
  const li = document.createElement("li");
  li.className = "kredi-hareket";
  li.dataset.tur = h.tur;
  // Satırın oynattığı kova (Faz 4 / 2): `rezerv:<is_id>:paket` gibi ikinci kova
  // satırı da `rezerv` türünde — hangi kova olduğunu yalnız bu alan söyler.
  if (h.kova) li.dataset.kova = h.kova;
  const tur = document.createElement("span");
  tur.className = "kredi-tur";
  tur.textContent = t(KREDI_HAREKET_ANAHTARI[h.tur] || "kredi.tur_duzeltme");
  const miktar = document.createElement("span");
  miktar.className = `kredi-miktar ${h.miktar < 0 ? "eksi" : "arti"}`;
  // İmzalı: defter satırı zaten imzalı (`miktar` rezervde eksi), `−` tipografik.
  miktar.textContent = h.miktar < 0 ? `−${Math.abs(h.miktar)}` : `+${h.miktar}`;
  const zaman = document.createElement("span");
  zaman.className = "kredi-zaman";
  zaman.textContent = krediTarihi(h.olusturuldu, true);
  li.append(tur, miktar, zaman);
  if (h.aciklama) li.appendChild(krediNotu(h.aciklama, "kredi-aciklama"));
  if (h.is_id) {
    const dugme = document.createElement("button");
    dugme.type = "button";
    dugme.className = "btn-ghost kredi-is";
    dugme.textContent = t("kredi.ise_git");
    dugme.addEventListener("click", () => {
      closeSettings();
      kromisIsler.goster(h.is_id);
    });
    li.appendChild(dugme);
  }
  return li;
}

function krediBolmesiniCiz() {
  const kok = $("settings-kredi");
  if (!kok) return;
  kok.replaceChildren();
  const k = krediDurumu;
  if (!k) {
    kok.appendChild(krediNotu(t("kredi.yuklenemedi")));
    return;
  }
  const bakiye = document.createElement("p");
  bakiye.className = "kredi-bakiye";
  const sayi = document.createElement("strong");
  sayi.id = "settings-kredi-bakiye";
  // Büyük sayı iki kovanın TOPLAMI (composer "kalan" ile aynı sayı); `??` eski cevap için.
  sayi.textContent = String(k.toplam ?? k.bakiye);
  const birim = document.createElement("span");
  birim.textContent = ` ${t("kredi.bakiye_birim")}`;
  bakiye.append(sayi, birim);
  kok.appendChild(bakiye);
  // İki kova satırı (Faz 4 / 2, K3): aylık hibe devretmez, paket devreder — kullanıcı
  // hangisinin ne kadar olduğunu görsün; satın alma ve sipariş listesi 4. görevde.
  kok.appendChild(
    krediNotu(
      t("kredi.kova_satiri", { hibe: k.bakiye, paket: k.paket_bakiye ?? 0 }),
      "kredi-kovalar",
    ),
  );
  kok.appendChild(
    krediNotu(
      t("kredi.plan_satiri", { plan: t(KREDI_PLAN_ANAHTARI[k.plan] || "kredi.plan_free") }),
      "kredi-plan",
    ),
  );
  // İptal edilmiş abonelik (Faz 4 / 4): plan dönem sonuna kadar kalır, sonra ücretsiz (K6).
  if (k.plan_bitis) {
    kok.appendChild(
      krediNotu(
        t("kredi.plan_bitis_satiri", { tarih: krediTarihi(k.plan_bitis, false) }),
        "kredi-plan-bitis",
      ),
    );
  }
  kok.appendChild(
    krediNotu(
      k.hibe > 0
        ? t("kredi.hibe_satiri", { n: k.hibe, tarih: krediTarihi(k.sonraki_hibe, false) })
        : t("kredi.hibe_yok"),
      "kredi-hibe",
    ),
  );
  kok.appendChild(krediNotu(t(k.filigran ? "kredi.filigran_var" : "kredi.filigran_yok")));
  kok.appendChild(krediNotu(t(k.video ? "kredi.video_acik" : "kredi.video_kapali")));
  kok.appendChild(krediNotu(t("kredi.byok_notu")));
  kok.appendChild(krediEylemleri());
  krediSiparisleriCiz(kok, k.siparisler || []);
  const baslik = document.createElement("h3");
  baslik.className = "modal-subhead";
  baslik.textContent = t("kredi.hareketler");
  kok.appendChild(baslik);
  const hareketler = k.son_hareketler || [];
  if (!hareketler.length) {
    kok.appendChild(krediNotu(t("kredi.hareket_yok")));
    return;
  }
  const ul = document.createElement("ul");
  ul.id = "settings-kredi-hareketler";
  ul.className = "kredi-hareketler";
  for (const h of hareketler) ul.appendChild(krediHareketSatiri(h));
  kok.appendChild(ul);
}

/** Bölmenin iki eylemi (Faz 4 / 4, belge §4): "Plan değiştir / kredi al" → `/planlar`
 *  (gerçek bağlantı, satış sayfası ayrı belge); "Aboneliğimi ve faturalarımı yönet" →
 *  `GET /api/odeme/portal` → Polar müşteri portalı (`location.assign`; iptal, kart,
 *  FATURALAR orada — bizde fatura sayfası yok, K7). 404 `err.musteri_yok` (hiç satın
 *  almamış) düğmeyi kilitler ve sebebini yazar; sunucu söyler, bölme kopyalamaz. */
function krediEylemleri() {
  const kutu = document.createElement("div");
  kutu.className = "kredi-eylemler";
  const planlar = document.createElement("a");
  planlar.id = "settings-kredi-planlar";
  planlar.className = "btn-ghost";
  planlar.href = "/planlar";
  planlar.textContent = t("kredi.plan_degistir");
  const portal = document.createElement("button");
  portal.id = "settings-kredi-portal";
  portal.type = "button";
  portal.className = "btn-ghost";
  portal.textContent = t("kredi.portal");
  // Tek not satırı: her başarısız tıklama yeni bir `krediNotu` EKLEMEZ, öncekinin yerine yazar
  // (ölçüldü: üç tıklama üç aynı satır).
  const notYaz = (metin, sinif) => {
    const eski = kutu.querySelector(".kredi-portal-notu");
    const yeni = krediNotu(metin, `kredi-portal-notu ${sinif}`);
    if (eski) eski.replaceWith(yeni);
    else kutu.appendChild(yeni);
  };
  portal.addEventListener("click", async () => {
    portal.disabled = true;
    try {
      const res = await fetch("/api/odeme/portal");
      const govde = await res.json().catch(() => null);
      if (res.ok && govde && govde.url) {
        window.location.assign(govde.url);
        return;
      }
      const kod = govde && govde.detail && govde.detail.kod;
      if (res.status === 404 && kod === "err.musteri_yok") {
        portal.title = t("kredi.portal_yok");
        notYaz(t("kredi.portal_yok"), "kredi-portal-yok");
        return; // kilitli kalır
      }
      notYaz(kod ? t(kod, govde.detail) : t("kredi.yuklenemedi"), "kredi-portal-hata");
    } catch {
      notYaz(t("kredi.yuklenemedi"), "kredi-portal-hata");
    }
    portal.disabled = false;
  });
  kutu.append(planlar, portal);
  return kutu;
}

/** Son siparişler ÖZET (tarih · ürün · tutar) + "faturalar Polar portalında" (K7). */
function krediSiparisleriCiz(kok, siparisler) {
  const baslik = document.createElement("h3");
  baslik.className = "modal-subhead";
  baslik.textContent = t("kredi.siparisler");
  kok.appendChild(baslik);
  if (!siparisler.length) {
    kok.appendChild(krediNotu(t("kredi.siparis_yok")));
    return;
  }
  const ul = document.createElement("ul");
  ul.id = "settings-kredi-siparisler";
  ul.className = "kredi-siparisler";
  for (const s of siparisler) {
    const li = document.createElement("li");
    li.className = "kredi-siparis";
    const zaman = document.createElement("span");
    zaman.className = "kredi-zaman";
    zaman.textContent = krediTarihi(s.olusturuldu, false);
    const urun = document.createElement("span");
    urun.className = "kredi-urun";
    urun.textContent = s.urun;
    const tutar = document.createElement("span");
    tutar.className = "kredi-miktar";
    tutar.textContent = krediTutari(s.tutar_kurus, s.para_birimi);
    li.append(zaman, urun, tutar);
    ul.appendChild(li);
  }
  kok.appendChild(ul);
  kok.appendChild(krediNotu(t("kredi.faturalar_polar"), "kredi-faturalar"));
}

/** Kuruş/cent → yerel para biçimi; Polar'ın para birimi (`usd`). `Intl` bilinmeyen kodda fırlatır → düz. */
function krediTutari(kurus, birim) {
  try {
    return new Intl.NumberFormat(KROMIS_DIL, {
      style: "currency",
      currency: birim.toUpperCase(),
    }).format(kurus / 100);
  } catch {
    return `${(kurus / 100).toFixed(2)} ${String(birim).toUpperCase()}`;
  }
}

/** core.js'in 402 toast'ından (Faz 3 / 6): Ayarlar'ı "Kredi" bölmesinde açar. */
function openKrediBolmesi() {
  openSettings();
  showSettingsPane("kredi");
  // `openSettings` odağı Erişim bölmesinin seçicisine veriyor (0 ms sonra); o bölme
  // artık gizli, odak boşa düşerdi — gezinmedeki "Kredi" düğmesine, aynı gecikmeyle sonra.
  setTimeout(() => $("settings-nav").querySelector('[data-pane="kredi"]').focus(), 0);
}

// Bakiye başka bir olayla yenilendiyse (iş bitti, 402) açık bölme de yenilensin.
document.addEventListener("kromis:kredi", () => {
  if (acikBolme === "kredi" && $("settings-modal").classList.contains("open")) krediBolmesiniCiz();
});

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
document.addEventListener(
  "keydown",
  (e) => {
    if (e.key !== "Escape" || $("provider-modal").hidden) return;
    e.stopImmediatePropagation();
    closeProviderModal();
  },
  true,
);

function openSettings(provider) {
  // Gizli alanların HEPSİ temizleniyor (write-only): kayıtlı anahtar hiçbir
  // zaman forma dolmuyor, o yüzden boş kutu "sildim" değil "dokunmadım"dır.
  $("set-openai-key").value = "";
  $("set-gemini-key").value = "";
  $("set-fal-key").value = "";
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
function closeSettings() {
  closeProviderModal();
  closeSheets();
}

async function saveSettings() {
  const base_url = $("set-endpoint").value.trim();
  const api_key = $("set-key").value;
  const st = $("settings-status");
  // Kapı SAĞLAYICIYA BAĞLI. Öncesinde koşulsuzdu ve "Endpoint gerekli" hatası
  // OpenAI anahtarı eklemeye çalışan kullanıcıya BAŞKA bir sağlayıcı hakkında
  // konuşuyordu — sunucu tarafındaki aynı kilidin istemci yarısı.
  if ($("set-provider").value === "azure") {
    if (!base_url) {
      st.textContent = t("settings.endpoint_required");
      return;
    }
    if (!configured && !api_key.trim()) {
      st.textContent = t("settings.key_required");
      return;
    }
  }

  $("settings-save").disabled = true;
  st.textContent = t("common.saving");
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
      body: JSON.stringify({
        api_key,
        base_url,
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
        gemini_api_key: $("set-gemini-key").value,
        fal_key: $("set-fal-key").value,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || t("err.http", { durum: res.status }));
    }
    applyConfigured(await res.json());
    $("set-key").value = "";
    $("set-openai-key").value = "";
    $("set-gemini-key").value = "";
    $("set-fal-key").value = "";
    st.textContent = t("common.saved");
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
$("settings-update-check").addEventListener("click", simdiKontrolEt);
$("settings-save").addEventListener("click", saveSettings);

// ── Tema seçici (A6 / Adım 7b) ──────────────────────────────────────
// Dört temanın token'ları flow-tokens.css'te Adım 1'den beri hazırdı
// ([data-theme=…]); burası onları GERÇEKTEN uygulayan taraf. Monokrom =
// öznitelik yok: varsayılan --accent zaten monokrom, sahte bir "mono"
// değeri yazmak token katmanında karşılığı olmayan bir durum üretirdi.
// KALICI: seçim `POST /api/prefs` ile prefs.json'a yazılıyor (aşağıdaki
// `saveThemePref`) ve açılışta chat.js'in `loadPrefs`'i geri okuyor. Burada
// bir zamanlar "KALICILIK BİLEREK YOK" yazılıydı ve o cümle Adım 9 geldikten
// sonra bayatladı — panelin içindeki "yeniden başlatınca sıfırlanır" notuyla
// birlikte kaldırıldı.
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

// ── Dil seçici ───────────────────────────────────────────────────────
//
// Tema seçicisinin kalıbı ama İKİ noktada bilerek ayrılıyor:
//
//   1. SAYFA YENİLENİYOR. Temayı bir CSS özniteliği taşıyor, dili ise HTML'in
//      KENDİSİ: metinler sunucuda `{{t:…}}` yer tutucularından çözülüyor
//      (`i18n.render`) ve `<html lang>` de orada yazılıyor. İstemcide DOM'u
//      gezip yeniden yazmak ikinci bir çeviri yolu açardı — iki yol zamanla
//      ayrışır ve arayüzün bir köşesi eski dilde kalırdı. Yenileme tek yolu
//      korur; bedeli bir sayfa yüklemesi, loopback'te ölçülemez.
//   2. ÖNCE ONAY — ama yalnız kaybedilecek bir şey varsa. Yenileme
//      composer'da yazılı metni siler ve bu, kullanıcının hiç beklemediği bir
//      kayıp olurdu (sendChat'in başarısızlık dalının reddettiği şeyin
//      aynısı). Kutu boşken soru sormak ise gereksiz bir tık.
//
// Seçili seçenek `window.KROMIS_LANG`ten kuruluyor, `/api/prefs`ten DEĞİL:
// sunucu sayfayı zaten o dille çizdi, yani ekranda duran metin ile listede
// işaretli dil TANIM GEREĞİ aynı olmak zorunda. Ayrı bir uçtan sormak,
// ikisinin ayrışabildiği bir an açardı (`applyConfigured`ın "aynı yanıttan"
// gerekçesi).
//
// Sunucu `selected` özniteliğini zaten yazıyor (`i18n.language_options_html`);
// bu satır onun kopyası değil GERİ ALMA yolu: onay penceresinden "vazgeç"
// çıkınca liste kullanıcının seçtiği dilde kalırdı, oysa arayüz eski dilde.
function syncLanguagePicker() {
  const secici = $("language-select");
  if (secici) secici.value = KROMIS_DIL;
}

async function saveLanguagePref(dil) {
  const durum = $("language-status");
  const yazili = ($("prompt").value || "").trim();
  if (
    yazili &&
    !(await confirmDialog(t("settings.language_unsaved"), t("settings.language_unsaved_body"), {
      okLabel: t("settings.language_switch_ok"),
    }))
  ) {
    syncLanguagePicker(); // gerçekleşmeyen değişikliği geri al
    return;
  }
  durum.textContent = t("settings.language_switching");
  try {
    await chatApi("/api/prefs", { method: "POST", body: { language: dil } });
    // `reload()` YAZIMDAN SONRA: önce yenilenip sonra yazmak, yazım
    // başarısız olduğunda kullanıcıyı eski dilde ve hiçbir açıklama olmadan
    // bırakırdı.
    window.location.reload();
  } catch (e) {
    syncLanguagePicker();
    durum.textContent = t("prefs.write_failed", { hata: e.message });
  }
}

$("language-select").addEventListener("change", (e) => saveLanguagePref(e.target.value));

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
        applyVideoModel(secilecek(videoModels, seciliVideoModeliTercihi, ""), { announce: false });
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
// Ağa ÇIKMIYOR: seçili dil sayfanın kendisinden (`window.KROMIS_LANG`) okunuyor.
syncLanguagePicker();
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

// ── Hesap (Faz 1 / 3) ────────────────────────────────────────────────
//
// Açılışta `GET /api/hesap/ben`: oturum varsa "Hakkında" bölmesinin başına
// e-posta + "Çıkış yap". Satır DİNAMİK kuruluyor, index.html'e yazılmıyor: o
// belge 286 metin çapası taşıyor ve bu turda dokunulmuyor
// (docs/faz1-veritabani-hesaplar.md → 3). 401 ARTIK BURAYA DÜŞMEZ (Faz 1 / 4):
// `core.js`in `window.fetch` sarmalı 401'i görür görmez `/giris?sonra=`e
// gidiyor ve sunucu `GET /`yi oturumsuz zaten 302'liyor — yani bu betik
// koşuyorsa oturum var. `/giris` bağlantısı dalı yine de duruyor: sarmal bir
// gün kaldırılır ya da yönlendirme engellenirse (gömülü çerçeve) kullanıcı
// bir çıkış yolu görsün. 503 (veri tabanı yok — dondurulmuş kabuk) ve ağ
// hatasında satır hiç çizilmez: hesabın olmadığı bir kurulumda "giriş yap"
// demek yanlış olurdu.
async function hesapDurumunuYaz() {
  const bolme = document.querySelector('#settings-modal .settings-pane[data-pane="about"]');
  if (!bolme) return;
  let res;
  try {
    res = await fetch("/api/hesap/ben");
  } catch {
    return;
  }
  if (!res.ok && res.status !== 401) return;
  const satir = document.createElement("p");
  satir.id = "settings-hesap";
  satir.className = "field-note settings-hesap-row";
  if (res.status === 401) {
    const baglanti = document.createElement("a");
    baglanti.href = "/giris";
    baglanti.className = "btn-ghost";
    baglanti.textContent = t("hesap.giris_baglantisi");
    satir.append(baglanti);
  } else {
    const ben = await res.json();
    const metin = document.createElement("span");
    metin.textContent = t("hesap.oturum_acik", { eposta: ben.eposta });
    const cikis = document.createElement("button");
    cikis.type = "button";
    cikis.id = "settings-cikis";
    cikis.className = "btn-ghost";
    cikis.textContent = t("hesap.cikis");
    cikis.addEventListener("click", async () => {
      cikis.disabled = true;
      try {
        await chatApi("/api/hesap/cikis", { method: "POST", body: {} });
        // `replace`: çıkılan oturuma geri tuşuyla dönülmez.
        window.location.replace("/giris");
      } catch (e) {
        cikis.disabled = false;
        metin.textContent = t("hesap.cikis_hatasi", { hata: e.message });
      }
    });
    satir.append(metin, " ", cikis);
    // Admin ise `/admin` bağlantısı (Faz 2 / 8): bayrağı `ben` taşıyor, sayfa
    // kendi kapısını sunucuda sorar — burada göstermemek yalnız görünürlük.
    if (ben.is_admin) {
      const admin = document.createElement("a");
      admin.href = "/admin";
      admin.id = "settings-admin";
      admin.className = "btn-ghost";
      admin.textContent = t("hesap.admin_baglantisi");
      satir.append(" ", admin);
    }
    sartlarBanneriniCiz(ben);
  }
  bolme.prepend(satir);
}
hesapDurumunuYaz();

// ── Şartlar güncellendi banner'ı (Faz 4 / 6, belge §6) ───────────────
// SUNUCU KARAR VERİR: `ben.sartlar_guncel` `false` ise (onaylanan sürüm ≠
// `HUKUK_SURUMU`, ya da hiç onay yok) banner çizilir; sayfa sürümü bilmez ve
// kopyalamaz (planlar.js'in 412 duruşu). Düğme `POST /api/hesap/sartlar-kabul`
// — gövde yok, sürümü sunucu yazar. Kök `#settings-sartlar-banner` index.html'de,
// bölmelerin ÜSTÜNDE: hangi sekme açık olsun görünür.
function sartlarBanneriniCiz(ben) {
  const kok = $("settings-sartlar-banner");
  if (!kok || ben.sartlar_guncel !== false) return;
  kok.replaceChildren();
  const metin = document.createElement("span");
  metin.textContent = t("hukuk.guncellendi");
  const oku = document.createElement("a");
  oku.href = "/hukuk/kullanim-sartlari";
  oku.target = "_blank";
  oku.rel = "noopener";
  oku.textContent = t("hukuk.kullanim_sartlari");
  const kabul = document.createElement("button");
  kabul.type = "button";
  kabul.id = "settings-sartlar-kabul";
  kabul.className = "btn-ghost";
  kabul.textContent = t("hukuk.kabul_dugme");
  const durum = document.createElement("span");
  durum.id = "settings-sartlar-durum";
  durum.className = "modal-status";
  kabul.addEventListener("click", async () => {
    kabul.disabled = true;
    try {
      await chatApi("/api/hesap/sartlar-kabul", { method: "POST", body: {} });
      kok.hidden = true;
    } catch (e) {
      kabul.disabled = false;
      durum.textContent = t("hukuk.kabul_hatasi", { hata: e.message });
    }
  });
  kok.append(metin, " ", oku, " ", kabul, " ", durum);
  kok.hidden = false;
}

// ── Hesap bölmesi (Faz 4 / 5) ───────────────────────────────────────
// İçerik DİNAMİK, index.html'de yalnız kök (#settings-hesap-islemleri): #settings-kredi
// deseni. İki iş: (1) "Verimi indir" — `GET /api/hesap/disa-aktar` ZIP'i; indirme
// `fetch` + blob ile (düz `<a href>` değil): 429 (saatte 1) cevabının cümlesi
// kullanıcıya gösterilmeli, tarayıcının "indirme başarısız"ı değil. (2) "Hesabımı
// sil" — parola + ikinci onay metni ("SİL"), `POST /api/hesap/sil`; 200'de
// `/giris` (`replace`: silinen hesaba geri tuşuyla dönülmez — K9 geri alma yok).
// Onay metni SUNUCUYA GİTMEZ: kapı parola, metin yalnız yanlış tıklamaya karşı
// tarayıcı tarafı sürtünme; sözlükten okunur (`hesap.sil_onay_metni`) ki İngilizce
// arayüzde "DELETE" istenebilsin.
function hesapNotu(anahtar, sinif) {
  const p = document.createElement("p");
  p.className = sinif ? `field-note ${sinif}` : "field-note";
  p.textContent = t(anahtar);
  return p;
}

function hesapBaslik(anahtar) {
  const h = document.createElement("h3");
  h.className = "palette-picker-title";
  h.textContent = t(anahtar);
  return h;
}

async function hesapVerisiniIndir(dugme, durum) {
  dugme.disabled = true;
  durum.textContent = t("hesap.disa_aktar_hazirlaniyor");
  try {
    const res = await fetch("/api/hesap/disa-aktar");
    if (!res.ok) {
      const veri = await res.json().catch(() => ({}));
      throw new Error(typeof veri.detail === "string" ? veri.detail : String(res.status));
    }
    const blob = await res.blob();
    const eslesme = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
    // Büyük K bilinçli: küçük harfli `ad.uzanti` dizesi i18n bekçisinin anahtar deseniyle çakışıyor.
    const ad = eslesme ? eslesme[1] : "Kromis-verim.zip";
    const url = URL.createObjectURL(blob);
    downloadViaAnchor(url, ad);
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    durum.textContent = t("hesap.disa_aktar_indi");
  } catch (e) {
    durum.textContent = t("hesap.disa_aktar_hata", { hata: e.message });
  } finally {
    dugme.disabled = false;
  }
}

function hesapBolmesiniCiz() {
  const kok = $("settings-hesap-islemleri");
  if (!kok) return;
  kok.replaceChildren();

  // (1) Veri dışa aktarma
  kok.appendChild(hesapBaslik("hesap.disa_aktar_baslik"));
  kok.appendChild(hesapNotu("hesap.disa_aktar_aciklama"));
  const indir = document.createElement("button");
  indir.type = "button";
  indir.id = "hesap-disa-aktar";
  indir.className = "btn-ghost";
  indir.textContent = t("hesap.disa_aktar_dugme");
  const indirDurum = document.createElement("p");
  indirDurum.id = "hesap-disa-aktar-durum";
  indirDurum.className = "modal-status";
  indirDurum.setAttribute("role", "status");
  indir.addEventListener("click", () => hesapVerisiniIndir(indir, indirDurum));
  kok.append(indir, indirDurum);

  // (2) Hesap silme
  const form = document.createElement("form");
  form.id = "hesap-sil-form";
  form.className = "hesap-sil-form";
  form.autocomplete = "off";
  form.appendChild(hesapBaslik("hesap.sil_baslik"));
  form.appendChild(hesapNotu("hesap.sil_aciklama", "hesap-sil-uyari"));
  const parolaEtiket = document.createElement("label");
  parolaEtiket.htmlFor = "hesap-sil-parola";
  parolaEtiket.textContent = t("hesap.sil_parola");
  const parola = document.createElement("input");
  parola.type = "password";
  parola.id = "hesap-sil-parola";
  parola.name = "parola";
  parola.required = true;
  parola.autocomplete = "current-password";
  const onayEtiket = document.createElement("label");
  onayEtiket.htmlFor = "hesap-sil-onay";
  onayEtiket.textContent = t("hesap.sil_onay", { metin: t("hesap.sil_onay_metni") });
  const onay = document.createElement("input");
  onay.type = "text";
  onay.id = "hesap-sil-onay";
  onay.name = "onay";
  onay.required = true;
  onay.autocomplete = "off";
  const sil = document.createElement("button");
  sil.type = "submit";
  sil.id = "hesap-sil-dugme";
  sil.className = "btn-ghost hesap-sil-dugme";
  sil.textContent = t("hesap.sil_dugme");
  const silDurum = document.createElement("p");
  silDurum.id = "hesap-sil-durum";
  silDurum.className = "modal-status";
  silDurum.setAttribute("role", "status");
  form.append(parolaEtiket, parola, onayEtiket, onay, sil, silDurum);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (onay.value.trim() !== t("hesap.sil_onay_metni")) {
      silDurum.textContent = t("hesap.sil_onay_uyusmuyor");
      onay.focus();
      return;
    }
    sil.disabled = true;
    silDurum.textContent = t("hesap.siliniyor");
    try {
      await chatApi("/api/hesap/sil", { method: "POST", body: { parola: parola.value } });
      window.location.replace("/giris");
    } catch (err) {
      sil.disabled = false;
      silDurum.textContent = t("hesap.sil_hata", { hata: err.message });
    }
  });
  kok.appendChild(form);
}
hesapBolmesiniCiz();
// Bakiye açılışta bir kez (Faz 3 / 6): composer'ın "kalan"ı ilk çizimde dolu gelsin;
// sonrası iş olaylarına bağlı (isler.js). Kapılı rota: 401'i `fetch` sarmalı görür.
krediYenile();
