// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// Giriş sayfasının betiği (Faz 1 / 3. görev) — static/giris.html'in tek betiği
// (i18n.js dışında). Dört form, tek mesaj satırı, dört sunucu yolu:
//   POST /api/hesap/giris · /api/hesap/kayit · /api/hesap/sifirla ·
//   /api/hesap/sifirla/dogrula, artı açılışta /api/hesap/dogrula (bağlantıdan)
//   ve /api/hesap/ben (zaten oturum varsa stüdyoya).
//
// IIFE İÇİNDE ve bilerek: bu sayfa stüdyonun betiklerini yüklemiyor ama eslint
// (eslint.config.js) her static/*.js dosyasına ÖTEKİ betiklerin üst düzey
// adlarını küresel olarak veriyor — üst düzeyde `const $ = …` yazmak core.js'in
// `$`ıyla `no-redeclare`a düşerdi. Kapsam kapalı olunca ne çakışma var ne de
// paylaşılan ad defterine girecek bir şey; tests/test_id_contract.py bu dosyayı
// o gerekçeyle `KAPSAM_DISI`nda tutuyor, id bağlarını tests/test_hesap.py sınıyor.
//
// GİRİŞTEN SONRA NEREYE (`?sonra=`): stüdyo betiği 401 görünce buraya
// `?sonra=<bıraktığı yol>` ile gelir (static/core.js); giriş başarılıysa oraya
// dönülür. Kapı `hedef()`: değer YALNIZ aynı kökene ait bir yol olabilir —
// `/` ile başlar ve tarayıcının `URL` ayrıştırıcısı onu BİZİM kökene çözer
// (şemasız `//`, ters bölü, sekme/satır sonu gibi ayrıştırıcı hileleri hep
// aynı soruya iner: `origin` bizim mi). Aksi hâlde `/`. Yoksa bu sayfa bir
// "açık yönlendirici" olurdu: `/giris?sonra=https://sahte.site` bağlantısı
// gerçek giriş sayfasından sahte siteye taşırdı (tests/test_playwright_hesap.py).
//
// E-POSTA BAĞLANTILARI GET, İŞLEM POST: bağlantı `/giris?dogrula=<jeton>` ya da
// `/giris?sifirla=<jeton>` — sayfa parametreyi okur, POST'a çevirir ve adres
// çubuğundan SİLER (`history.replaceState`): jeton tarayıcı geçmişinde, `Referer`
// başlığında ve ekran paylaşımında kalmasın. Doğrulama otomatik (tek tıklama
// yeter); sıfırlama yeni parolayı ister, jeton bellekte bekler.
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const mesaj = el("giris-mesaj");
  const SEKMELER = ["giris", "kayit", "sifirla", "yeni-parola"];

  /** Tek mesaj satırı: `tur` CSS'in rengi için (`bilgi` | `basari` | `hata`). */
  function mesajYaz(metin, tur) {
    mesaj.textContent = metin || "";
    mesaj.hidden = !metin;
    mesaj.dataset.tur = tur || "bilgi";
  }

  function sekmeAc(ad) {
    for (const s of SEKMELER) el("form-" + s).hidden = s !== ad;
    for (const dugme of document.querySelectorAll("#giris-sekmeler [data-sekme]")) {
      dugme.setAttribute("aria-selected", String(dugme.dataset.sekme === ad));
    }
    const ilk = document.querySelector(`#form-${ad} input`);
    if (ilk) ilk.focus();
  }

  /** Sunucunun `detail`i: düz metin (i18n'li cümle) ya da pydantic listesi.
   *  Pydantic'in "Value error, " öneki kullanıcıya bir şey söylemiyor, atılıyor. */
  function detayMetni(govde, durum) {
    const d = govde && govde.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const m = d
        .map((e) => (e && e.msg) || "")
        .filter(Boolean)
        .map((s) => s.replace(/^Value error, /, ""))
        .join(" ");
      if (m) return m;
    }
    return t("giris.hata_genel", { durum });
  }

  async function gonder(yol, govde) {
    let res;
    try {
      res = await fetch(yol, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(govde),
      });
    } catch {
      throw new Error(t("giris.baglanti_yok"));
    }
    const veri = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detayMetni(veri, res.status));
    return veri;
  }

  /** Gönderim sırasında düğme kilitli: çift tıklama iki kayıt isteği (ve iki
   *  e-posta) üretirdi. Hata mesaj satırına, başarı `isle`nin kararına. */
  function formBagla(form, isle) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const dugme = form.querySelector("button[type=submit]");
      dugme.disabled = true;
      mesajYaz(t("giris.bekleniyor"), "bilgi");
      try {
        await isle(new FormData(form));
      } catch (err) {
        mesajYaz(err.message, "hata");
      } finally {
        dugme.disabled = false;
      }
    });
  }

  let sifirlamaJetonu = null;

  /** Girişten sonra gidilecek yol: `?sonra=` aynı kökene çözülüyorsa yolu + sorgusu, değilse `/`.
   *
   *  Karar TARAYICININ ayrıştırıcısına bırakılıyor (`new URL(sonra, origin)`), dize
   *  kurallarına değil: eski hâl `startsWith("//")` ve `\` denetimiydi ve WHATWG'nin
   *  sekme/satır sonu SOYMASINI ıskalıyordu — `/%09/evil.example` (`/\t/evil…`) dize
   *  olarak `//` ile başlamaz ama tarayıcı sekmeyi atıp `//evil.example`e gider
   *  (inceleme bulgusu, 2026-09-22). Ayrıştırıcı ne yapacaksa onu yapıp kökeni
   *  karşılaştırmak tek doğru soru; göreli değer (`galeri`) de kökene çözülür ve
   *  `/galeri` olur — eskisi gibi `/`e düşmesi için `/` ile başlama şartı duruyor. */
  function hedef() {
    const sonra = new URLSearchParams(window.location.search).get("sonra");
    if (typeof sonra !== "string" || !sonra.startsWith("/")) return "/";
    try {
      const u = new URL(sonra, window.location.origin);
      return u.origin === window.location.origin ? u.pathname + u.search : "/";
    } catch {
      return "/";
    }
  }

  formBagla(el("form-giris"), async (veri) => {
    await gonder("/api/hesap/giris", { eposta: veri.get("eposta"), parola: veri.get("parola") });
    // `replace`: giriş sayfası geri tuşuyla dönülecek bir yer değil.
    window.location.replace(hedef());
  });

  formBagla(el("form-kayit"), async (veri) => {
    // Şartlar kutusu (Faz 4 / 6): değer sunucuya gider, kararı sunucu verir —
    // işaretsizse 422 ve cümlesi mesaj satırına düşer (giris.html'in gerekçesi).
    await gonder("/api/hesap/kayit", {
      eposta: veri.get("eposta"),
      parola: veri.get("parola"),
      sartlar: el("kayit-sartlar").checked,
    });
    el("form-kayit").reset();
    sekmeAc("giris");
    mesajYaz(t("giris.kayit_gonderildi"), "basari");
  });

  formBagla(el("form-sifirla"), async (veri) => {
    await gonder("/api/hesap/sifirla", { eposta: veri.get("eposta") });
    el("form-sifirla").reset();
    sekmeAc("giris");
    mesajYaz(t("giris.sifirla_gonderildi"), "basari");
  });

  formBagla(el("form-yeni-parola"), async (veri) => {
    await gonder("/api/hesap/sifirla/dogrula", {
      jeton: sifirlamaJetonu,
      parola: veri.get("parola"),
    });
    sifirlamaJetonu = null;
    el("form-yeni-parola").reset();
    sekmeAc("giris");
    mesajYaz(t("giris.parola_degisti"), "basari");
  });

  el("giris-sekmeler").addEventListener("click", (e) => {
    const dugme = e.target.closest("[data-sekme]");
    if (!dugme) return;
    mesajYaz("");
    sekmeAc(dugme.dataset.sekme);
  });

  async function baslat() {
    const parametreler = new URLSearchParams(window.location.search);
    const dogrula = parametreler.get("dogrula");
    const sifirla = parametreler.get("sifirla");
    if (dogrula || sifirla) {
      window.history.replaceState(null, "", window.location.pathname);
    }
    if (dogrula) {
      try {
        await gonder("/api/hesap/dogrula", { jeton: dogrula });
        mesajYaz(t("giris.dogrulandi"), "basari");
      } catch (err) {
        mesajYaz(err.message, "hata");
      }
      sekmeAc("giris");
      return;
    }
    if (sifirla) {
      sifirlamaJetonu = sifirla;
      sekmeAc("yeni-parola");
      return;
    }
    // Oturum zaten açıksa form göstermenin anlamı yok. 401/503 ya da ağ
    // hatası: form açılır — bu sayfanın işi tam olarak o durum.
    try {
      const res = await fetch("/api/hesap/ben");
      if (res.ok) {
        window.location.replace(hedef());
        return;
      }
    } catch {
      /* sunucuya ulaşılamadı: formu göster, hata ilk gönderimde görünür */
    }
    sekmeAc("giris");
  }

  baslat();
})();
