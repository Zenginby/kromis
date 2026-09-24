// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// Satış sayfasının betiği (Faz 4 / 4, belge §4) — static/planlar.html'in tek
// betiği (i18n.js dışında). Üç okuma, iki yazma ucu:
//   GET  /api/odeme/urunler   fiyat aynası + plan kuralları (oturumsuz uç)
//   GET  /api/kredi           mevcut plan ("Mevcut planın" rozeti)
//   POST /api/odeme/checkout  {urun_id, sartlar_kabul} → {url} → location.assign
//   GET  /api/odeme/portal    {url} → location.assign (409'dan sonra)
//
// IIFE İÇİNDE, giris.js'in gerekçesiyle: bu sayfa stüdyonun betiklerini
// yüklemiyor ama eslint her static/*.js dosyasına öteki betiklerin adlarını
// küresel veriyor; kapsam kapalı olunca ne çakışma var ne paylaşılan ad.
// tests/test_id_contract.py `KAPSAM_DISI`; id bağlarını tests/test_odeme_route.py sınıyor.
//
// SUNUCU KARAR VERİR, SAYFA GÖSTERİR: şartlar kutusu ancak sunucu 412
// (`err.sartlar_gerekli`) deyince, portal düğmesi ancak 409 (`err.abonelik_var`)
// deyince görünür. Onay durumunu ya da aboneliği burada kopyalamak, sunucu
// kuralı değişince bayatlayan ikinci bir karar olurdu (core.js'in 402 duruşu).
//
// 401 → `/giris?sonra=/planlar`: sayfa kapılı (302) ama oturum sayfa
// açıkken de düşebilir; core.js'in sarmalı burada yok, aynı iş elle.
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const mesaj = el("planlar-mesaj");
  const PLAN_ADI = { free: "kredi.plan_free", temel: "kredi.plan_temel", pro: "kredi.plan_pro" };
  // Ücretsiz planın kartı da çizilir (karşılaştırma için) — `PLANLAR`ın sırası sunucudan (`rank`).
  let bekleyenUrun = null; // 412'den sonra onayla yeniden gönderilecek ürün

  function mesajYaz(metin, tur) {
    mesaj.textContent = metin || "";
    mesaj.hidden = !metin;
    mesaj.dataset.tur = tur || "bilgi";
  }

  function girise() {
    window.location.replace("/giris?sonra=" + encodeURIComponent(window.location.pathname));
  }

  /** Sunucunun `detail`i: `{kod, …}` ise kodun çevirisi (alanlar değişken), düz metin ise aynen. */
  function detayMetni(govde, durum) {
    const d = govde && govde.detail;
    if (d && typeof d === "object" && typeof d.kod === "string") return t(d.kod, d);
    if (typeof d === "string") return d;
    return t("planlar.hata_genel", { durum });
  }

  async function istek(yol, secenekler) {
    const res = await fetch(yol, secenekler);
    if (res.status === 401) {
      girise();
      throw new Error("401");
    }
    const govde = await res.json().catch(() => null);
    return { res, govde };
  }

  /** Kuruş/cent → yerel para biçimi (`Intl`); para birimi Polar'ın (`usd`). */
  function fiyatMetni(kurus, birim) {
    try {
      return new Intl.NumberFormat(KROMIS_DIL, {
        style: "currency",
        currency: birim.toUpperCase(),
      }).format(kurus / 100);
    } catch {
      return `${(kurus / 100).toFixed(2)} ${birim.toUpperCase()}`;
    }
  }

  function ozellik(metin, yok) {
    const li = document.createElement("li");
    li.textContent = metin;
    if (yok) li.dataset.yok = "true";
    return li;
  }

  /** "Ticari kullanım hakkı" satırı metne BAĞLANIR (Faz 4 / 6, belge §6): cümlenin
   *  kaynağı `/hukuk/ticari-haklar`; kullanıcı "hangi ölçüde?" sorusunu orada okur. */
  function ozellikBaglantili(metin, yol, yok) {
    const li = ozellik("", yok);
    const a = document.createElement("a");
    a.href = yol;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = metin;
    li.append(a);
    return li;
  }

  function dugme(metin, tiklandi) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "planlar-birincil";
    b.textContent = metin;
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await tiklandi();
      } finally {
        b.disabled = false;
      }
    });
    return b;
  }

  function planKarti(ad, kural, urun, mevcutPlan) {
    const kart = document.createElement("article");
    kart.className = "plan-kart";
    kart.dataset.plan = ad;
    const mevcut = ad === mevcutPlan;
    if (mevcut) kart.dataset.mevcut = "true";
    const bas = document.createElement("div");
    bas.className = "plan-kart-bas";
    const h3 = document.createElement("h3");
    h3.textContent = t(PLAN_ADI[ad] || "kredi.plan_free");
    bas.append(h3);
    if (mevcut) {
      const rozet = document.createElement("span");
      rozet.className = "plan-rozet";
      rozet.textContent = t("planlar.mevcut_plan");
      bas.append(rozet);
    }
    const fiyat = document.createElement("p");
    fiyat.className = "plan-fiyat";
    if (ad === "free") fiyat.textContent = t("planlar.ucretsiz");
    else if (urun) {
      fiyat.textContent = fiyatMetni(urun.fiyat_kurus, urun.para_birimi);
      const ay = document.createElement("small");
      ay.textContent = " " + t("planlar.ayda");
      fiyat.append(ay);
    } else fiyat.textContent = t("planlar.fiyat_yok");
    const ul = document.createElement("ul");
    ul.className = "plan-ozellikler";
    ul.append(
      ozellik(t("planlar.hibe", { n: kural.aylik_hibe })),
      ozellik(t(kural.filigran ? "kredi.filigran_var" : "kredi.filigran_yok"), kural.filigran),
      ozellik(t(kural.video ? "kredi.video_acik" : "kredi.video_kapali"), !kural.video),
      ozellikBaglantili(
        t(ad === "free" ? "planlar.ticari_haklar_yok" : "planlar.ticari_haklar"),
        "/hukuk/ticari-haklar",
        ad === "free",
      ),
    );
    kart.append(bas, fiyat, ul);
    // Satın al: ücretli plan, ürün aynada ve bu plan mevcut değil. Ücretli
    // plandaki kullanıcı başka plana basarsa sunucu 409 der, portal açılır.
    if (ad !== "free" && urun && !mevcut)
      kart.append(dugme(t("planlar.abone_ol"), () => satinAl(urun.id)));
    return kart;
  }

  function paketKarti(urun) {
    const kart = document.createElement("article");
    kart.className = "plan-kart";
    kart.dataset.urun = urun.id;
    const h3 = document.createElement("h3");
    h3.textContent = urun.ad;
    const fiyat = document.createElement("p");
    fiyat.className = "plan-fiyat";
    fiyat.textContent = fiyatMetni(urun.fiyat_kurus, urun.para_birimi);
    const ul = document.createElement("ul");
    ul.className = "plan-ozellikler";
    ul.append(ozellik(t("planlar.paket_kredi", { n: urun.kredi })));
    kart.append(
      h3,
      fiyat,
      ul,
      dugme(t("planlar.satin_al"), () => satinAl(urun.id)),
    );
    return kart;
  }

  async function satinAl(urunId, sartlarKabul) {
    mesajYaz("");
    el("planlar-portal").hidden = true;
    const { res, govde } = await istek("/api/odeme/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urun_id: urunId, sartlar_kabul: Boolean(sartlarKabul) }),
    });
    if (res.ok && govde && govde.url) {
      mesajYaz(t("planlar.yonlendiriliyor"), "bilgi");
      window.location.assign(govde.url);
      return;
    }
    const kod = govde && govde.detail && govde.detail.kod;
    if (res.status === 412 && kod === "err.sartlar_gerekli") {
      bekleyenUrun = urunId;
      el("planlar-sartlar-kutu").checked = false;
      el("planlar-sartlar-onayla").disabled = true;
      el("planlar-sartlar").hidden = false;
      el("planlar-sartlar").scrollIntoView({ block: "nearest" });
      mesajYaz(t(kod), "bilgi");
      return;
    }
    if (res.status === 409 && kod === "err.abonelik_var") {
      el("planlar-portal").hidden = false;
      el("planlar-portal").scrollIntoView({ block: "nearest" });
      mesajYaz(t(kod, govde.detail), "bilgi");
      return;
    }
    mesajYaz(detayMetni(govde, res.status), "hata");
  }

  async function portalaGit() {
    mesajYaz("");
    const { res, govde } = await istek("/api/odeme/portal");
    if (res.ok && govde && govde.url) {
      window.location.assign(govde.url);
      return;
    }
    mesajYaz(detayMetni(govde, res.status), "hata");
  }

  el("planlar-sartlar-kutu").addEventListener("change", (e) => {
    el("planlar-sartlar-onayla").disabled = !e.target.checked;
  });
  el("planlar-sartlar-onayla").addEventListener("click", async () => {
    if (!bekleyenUrun || !el("planlar-sartlar-kutu").checked) return;
    const urun = bekleyenUrun;
    el("planlar-sartlar").hidden = true;
    await satinAl(urun, true);
  });
  el("planlar-portal-dugme").addEventListener("click", portalaGit);

  async function yukle() {
    const planlarKok = el("planlar-planlar");
    const paketlerKok = el("planlar-paketler");
    try {
      // Mevcut plan `GET /api/kredi`den; düşerse rozet çizilmez, kartlar yine gelir.
      const [urunler, kredi] = await Promise.all([
        istek("/api/odeme/urunler"),
        istek("/api/kredi").catch(() => ({ res: null, govde: null })),
      ]);
      if (!urunler.res.ok || !urunler.govde) throw new Error(String(urunler.res.status));
      const veri = urunler.govde;
      const mevcutPlan = (kredi.govde && kredi.govde.plan) || null;
      const planUrunu = {};
      const paketler = [];
      for (const u of veri.urunler || []) {
        if (u.tur === "plan" && u.plan) planUrunu[u.plan] = u;
        else if (u.tur === "paket") paketler.push(u);
      }
      const adlar = Object.keys(veri.planlar || {}).sort(
        (a, b) => veri.planlar[a].rank - veri.planlar[b].rank,
      );
      planlarKok.replaceChildren(
        ...adlar.map((ad) => planKarti(ad, veri.planlar[ad], planUrunu[ad] || null, mevcutPlan)),
      );
      if (paketler.length) paketlerKok.replaceChildren(...paketler.map(paketKarti));
      else {
        const p = document.createElement("p");
        p.className = "planlar-not";
        p.textContent = t("planlar.paket_yok");
        paketlerKok.replaceChildren(p);
      }
    } catch (err) {
      if (err && err.message === "401") return;
      mesajYaz(t("planlar.yuklenemedi"), "hata");
    } finally {
      delete planlarKok.dataset.yukleniyor;
    }
  }

  yukle();
})();
