// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// İş paneli (Faz 2 / 5. görev; docs/faz2-kuyruk-anahtarlar-depolama.md §5).
//
// Üretim rotaları 202 + bir `is` kaydı döndürüyor ve üretimi ayrı bir işçi
// süreci yapıyor (services/isci.py). Bu betik o işlerin TEK ekranı: açılışta
// `GET /api/isler` (aktifler + son 50) paneli doldurur, sonra `EventSource`
// `GET /api/isler/akis`e bağlanır ve değişen her iş `event: is` olarak
// düşer. Sekme yenilenince aktif işler geri gelir (liste), biten iş galeriyi
// `loadHistory` ile yeniler — 4. görevin "sekme yenilenirse iş sürer, ekran
// onu göstermez" ara durumu burada kapanır.
//
// SSE, WebSocket DEĞİL, salt yoklama DEĞİL (belge K2): akış tek yönlü
// (istemci POST'la konuşur), `EventSource` yeniden bağlanmayı ve
// `Last-Event-ID`yi tarayıcıda ücretsiz verir, oturum çerezi aynı kökende
// kendiliğinden gider. Salt yoklama (`GET /api/isler`, 3 sn) YEDEK yol:
// `EventSource` arada `open` görmeden üç kez düşerse (SSE'nin desteklenmediği
// ya da vekilin kestiği ortam) ya da bağlantı KAPALI durumla düşerse (401,
// 404, yanlış içerik türü) buraya geçilir; liste yine çalışır.
//
// 401: `EventSource` `fetch` değil, core.js'in `window.fetch` sarmalı (401 →
// `/giris`) onu görmez. `onerror`da `GET /api/hesap/ben` sorulur — cevap 401
// ise sarmal giriş sayfasına gider (Faz 1'den devralınan tek kapı kuralı).
//
// core.js İLE SÖZLEŞME: `kromisIsler.kaydetIs(is, baglam)`. 202 gövdesindeki
// iş panele teslim edilir; `baglam` yalnız BU SEKMEDE yaşayan iki geri
// çağrı taşır — `bitince(is, kayitlar)` (galeri kayıtları, `GET /api/history`den
// iş sırasıyla) ve `hatada(mesaj)`. Sekme yenilenirse geri çağrılar gider,
// iş panelde kalır ve bitince galeri yine yenilenir: döküm turu (chat.js)
// kaybolur ama ürün kaybolmaz. core.js'in 4. görevdeki 2 sn yoklaması
// (`isiBekle`) bu yüzden kalktı: iki izleyici aynı işi iki kez sorardı.
//
// IIFE İÇİNDE, TEK üst düzey ad (`kromisIsler`): giris.js'in deyimi. Öteki
// betiklerin adlarına (`$`, `t`, `loadHistory`, `openSheet`, `imageModels`…)
// yalnız olay anında ya da çağrı içinde dokunuluyor — dosya `settings.js`ten
// ÖNCE yükleniyor (index.html), yani `imageModels` ilk çizimde boş olabilir;
// model etiketi o yüzden çizim ANINDA aranıyor, panel her açılışta yeniden
// çiziliyor. eslint defteri: eslint.paylasilan-adlar.json → static/isler.js.
//
// "YENİDEN GÖNDER" sunucuda (`POST /api/isler/{id}/yeniden`): `istek` (prompt,
// girdi anahtarları) istemciye hiç dökülmüyor (routers/isler.py), kopyayı rota
// alır ve girdi nesnelerine REFERANS verir — burada yalnız düğme var.
//
// #go KİLİDİ KALKTI: birden fazla iş sıraya girebilir (eş zamanlılık sınırı
// sunucuda 429 + `Retry-After`, core.js onu `uyar` ile buraya bırakır); çift
// tıklamaya karşı core.js düğmeyi 1 sn soğutur (`goSogut`).
const kromisIsler = (() => {
  "use strict";

  const AKIS_YOLU = "/api/isler/akis";
  const LISTE_YOLU = "/api/isler";
  // Yedek yoklama aralığı (belge §5: 3 sn) ve akışın "düştü" sayılacağı eşik.
  const YOKLAMA_MS = 3000;
  const DUSUS_ESIGI = 3;
  const KAPANMIS = new Set(["bitti", "hata", "iptal"]);
  const AKTIF = new Set(["bekliyor", "calisiyor"]);
  // Anahtarlar TABLODA ve harfiyen: tests/test_i18n.py betikleri anahtar
  // BİÇİMİNE uyan dizelerle tarıyor; ön ek + durum diye BİRLEŞTİRİLEREK kurulan
  // bir anahtar taramaya görünmez ve katalogdan silinince ölü sanılırdı.
  const DURUM_ANAHTARI = {
    bekliyor: "isler.durum_bekliyor",
    calisiyor: "isler.durum_calisiyor",
    bitti: "isler.durum_bitti",
    hata: "isler.durum_hata",
    iptal: "isler.durum_iptal",
  };
  const TUR_ANAHTARI = {
    generate: "isler.tur_generate",
    edit: "isler.tur_edit",
    video: "isler.tur_video",
    animate: "isler.tur_animate",
  };
  const VIDEO_TURLERI = new Set(["video", "animate"]);

  const isler = new Map(); // id → sunucudan gelen son hâl
  const baglamlar = new Map(); // id → { bitince, hatada } — yalnız bu sekmede
  const kayitlarCep = new Map(); // id → biten işin galeri kayıtları (önizleme)
  let kaynak = null; // EventSource
  let dususler = 0; // `open` görülmeden art arda düşüş sayısı
  let yoklama = null; // yedek yolun setInterval'i
  let oturumSoruldu = false; // düşüşte `ben` bir kez sorulur, her düşüşte değil

  const panel = $("isler-sheet");
  const liste = $("isler-liste");
  const bosYazi = $("isler-bos");
  const durumSatiri = $("isler-durum");
  const dugme = $("isler-btn");
  const sayac = $("isler-sayac");

  function durumYaz(metin) {
    durumSatiri.textContent = metin || "";
    durumSatiri.hidden = !metin;
  }

  /** Model etiketi katalogdan (`etiket`): şeritler sunucunun `label`ını taşıyor;
   *  katalog henüz yüklenmemişse ya da model listeden düşmüşse id görünür. */
  function modelEtiketi(id) {
    const kataloglar = [];
    if (typeof imageModels !== "undefined" && Array.isArray(imageModels))
      kataloglar.push(imageModels);
    if (typeof videoModels !== "undefined" && Array.isArray(videoModels))
      kataloglar.push(videoModels);
    for (const liste_ of kataloglar) {
      const m = liste_.find((x) => x && x.id === id);
      if (m) return m.short_label || m.label || id;
    }
    return id || "";
  }

  /** `zaman.damga` biçimi (`2026-09-18T12:00:00`, yerel saat, dilimsiz): tarayıcı
   *  dilimsiz ISO'yu yerel saat okur — sunucuyla aynı makine saati varsayımı,
   *  galerinin `created_at`i için de geçerli. */
  function an(damga) {
    if (!damga) return null;
    const d = new Date(damga);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  /** Geçen süre: `basladi` (yoksa `olusturuldu`) → `bitti` (yoksa şimdi). "12 sn" / "1:05". */
  function sureMetni(is) {
    const bas = an(is.basladi) || an(is.olusturuldu);
    if (!bas) return "";
    const son = an(is.bitti) || new Date();
    const sn = Math.max(0, Math.round((son - bas) / 1000));
    if (sn < 60) return t("isler.sure_sn", { sn });
    const dk = Math.floor(sn / 60);
    return `${dk}:${String(sn % 60).padStart(2, "0")}`;
  }

  function aktifSayisi() {
    let n = 0;
    for (const is of isler.values()) if (AKTIF.has(is.durum)) n++;
    return n;
  }

  function rozetCiz() {
    const n = aktifSayisi();
    sayac.textContent = n ? String(n) : "";
    sayac.hidden = !n;
    dugme.classList.toggle("is-aktif", n > 0);
    dugme.setAttribute(
      "aria-label",
      n ? `${t("isler.title")} · ${t("isler.aktif_aria", { adet: n })}` : t("isler.title"),
    );
  }

  /** Sunucudan gelen `detail`: düz metin ya da pydantic listesi (palette.js `detailText`). */
  function hataMetni(govde, durum) {
    return detailText(govde) || t("err.http", { durum });
  }

  async function gonder(yol) {
    const res = await fetch(yol, { method: "POST" });
    const govde = await res.json().catch(() => ({}));
    if (!res.ok) {
      const mesaj = hataMetni(govde, res.status);
      if (res.status === 429) {
        uyar(mesaj, res.headers.get("Retry-After"));
      } else {
        durumYaz(mesaj);
      }
      return null;
    }
    return govde.is || null;
  }

  // ── Çizim ──────────────────────────────────────────────────────────

  function onizleme(is) {
    const kayitlar = kayitlarCep.get(is.id) || [];
    if (!kayitlar.length) return null;
    const kutu = document.createElement("div");
    kutu.className = "is-onizleme";
    for (const rec of kayitlar.slice(0, 4)) {
      // Video karesi `<video>`; `#t=0.1` ilk kareyi çizdiriyor (folders.js'in kalıbı).
      const videoMu = VIDEO_TURLERI.has(rec.kind) || VIDEO_TURLERI.has(is.tur);
      const el = document.createElement(videoMu ? "video" : "img");
      el.src = `/output/${rec.filename}${videoMu ? "#t=0.1" : ""}`;
      if (videoMu) {
        el.muted = true;
        el.preload = "metadata";
      } else {
        el.alt = rec.prompt || "";
        el.loading = "lazy";
      }
      el.addEventListener("click", () => {
        // Panel kapanır, önizleme büyütece: `showPreview` core.js'in tek kapısı.
        closeSheets();
        showPreview(rec);
      });
      kutu.appendChild(el);
    }
    return kutu;
  }

  function satirCiz(is) {
    const li = document.createElement("li");
    li.className = "is-satir";
    li.dataset.id = is.id;
    li.dataset.durum = is.durum;
    li.dataset.tur = is.tur;
    if (is.arena_id) li.dataset.arena = is.arena_id;

    const bas = document.createElement("div");
    bas.className = "is-bas";
    const tur = document.createElement("span");
    tur.className = "is-tur";
    tur.textContent = t(TUR_ANAHTARI[is.tur] || "isler.tur_generate");
    const model = document.createElement("span");
    model.className = "is-model";
    model.textContent = modelEtiketi(is.model);
    const durum = document.createElement("span");
    durum.className = "is-durum";
    durum.textContent = t(DURUM_ANAHTARI[is.durum] || "isler.durum_bekliyor");
    const sure = document.createElement("span");
    sure.className = "is-sure";
    sure.textContent = sureMetni(is);
    bas.append(tur, model, durum, sure);
    li.appendChild(bas);

    if (is.durum === "bitti") {
      const kutu = onizleme(is);
      if (kutu) li.appendChild(kutu);
    } else if (is.durum === "hata" || is.durum === "iptal") {
      if (is.hata) {
        const p = document.createElement("p");
        p.className = "is-hata";
        p.textContent = is.hata;
        li.appendChild(p);
      }
      const yeniden = document.createElement("button");
      yeniden.type = "button";
      yeniden.className = "is-eylem is-yeniden";
      yeniden.textContent = t("isler.yeniden");
      yeniden.addEventListener("click", async () => {
        yeniden.disabled = true;
        const yeni = await gonder(`/api/isler/${encodeURIComponent(is.id)}/yeniden`);
        if (yeni) {
          guncelle(yeni);
          durumYaz(t("isler.yeniden_gonderildi"));
        } else {
          yeniden.disabled = false;
        }
      });
      li.appendChild(yeniden);
    } else if (is.durum === "bekliyor") {
      const iptal = document.createElement("button");
      iptal.type = "button";
      iptal.className = "is-eylem is-iptal";
      iptal.textContent = t("isler.iptal");
      iptal.addEventListener("click", async () => {
        iptal.disabled = true;
        const sonuc = await gonder(`/api/isler/${encodeURIComponent(is.id)}/iptal`);
        if (sonuc) guncelle(sonuc);
        else iptal.disabled = false;
      });
      li.appendChild(iptal);
    }
    return li;
  }

  /** Bütün listeyi yeniden çizer: en yeni üstte; aynı `arena_id`li sütunlar bir
   *  grup başlığı altında ardışık. Liste ≤ ~60 satır, tam çizim ucuz; geçen
   *  süre sayacı ise her saniye YALNIZ metni günceller (`sureleriTazele`). */
  function ciz() {
    const sirali = [...isler.values()].sort((a, b) =>
      (b.olusturuldu || "").localeCompare(a.olusturuldu || ""),
    );
    liste.replaceChildren();
    const gruplar = new Map(); // arena_id → <ul>
    for (const is of sirali) {
      const satir = satirCiz(is);
      if (!is.arena_id) {
        liste.appendChild(satir);
        continue;
      }
      let grup = gruplar.get(is.arena_id);
      if (!grup) {
        const kapsayici = document.createElement("li");
        kapsayici.className = "is-grup";
        kapsayici.dataset.arena = is.arena_id;
        const baslik = document.createElement("span");
        baslik.className = "is-grup-baslik";
        baslik.textContent = t("isler.arena");
        grup = document.createElement("ul");
        grup.className = "isler-liste is-grup-liste";
        kapsayici.append(baslik, grup);
        liste.appendChild(kapsayici);
        gruplar.set(is.arena_id, grup);
      }
      grup.appendChild(satir);
    }
    bosYazi.hidden = isler.size > 0;
    rozetCiz();
  }

  function sureleriTazele() {
    for (const li of liste.querySelectorAll(".is-satir")) {
      const is = isler.get(li.dataset.id);
      if (!is || !AKTIF.has(is.durum)) continue;
      const sure = li.querySelector(".is-sure");
      if (sure) sure.textContent = sureMetni(is);
    }
  }

  // ── Durum akışı ────────────────────────────────────────────────────

  /** Biten işin `sonuc.medya` id'lerini galeri kayıtlarına çevirir, iş sırasıyla.
   *  Klasör işin kendisinden (`folder_id`): `GET /api/history` klasöre göre
   *  süzüyor ve kökte yalnız klasörsüzler var — sekme yenilendiyse gönderim
   *  anındaki klasörü hatırlayan kimse yok, o yüzden sunucu söylüyor. */
  async function sonucKayitlari(is) {
    const ids = (is.sonuc && is.sonuc.medya) || [];
    if (!ids.length) return [];
    const yol = is.folder_id
      ? `/api/history?folder_id=${encodeURIComponent(is.folder_id)}`
      : "/api/history";
    const res = await fetch(yol);
    if (!res.ok) throw new Error(t("err.http", { durum: res.status }));
    const { images } = await res.json();
    const kayitlar = new Map(images.map((r) => [r.id, r]));
    return ids.map((id) => kayitlar.get(id)).filter(Boolean);
  }

  /** İş kapandı: geri çağrıyı (varsa) çözer, önizlemeyi çeker, galeriyi yeniler.
   *  Galeri yenilemesi geri çağrıdan BAĞIMSIZ — yenilenmiş bir sekmede geri
   *  çağrı yok ama ürün var; `loadHistory` yoksa (ayrı sayfa) sessiz. */
  async function kapanis(is) {
    const baglam = baglamlar.get(is.id);
    baglamlar.delete(is.id);
    if (is.durum === "bitti") {
      let kayitlar = [];
      try {
        kayitlar = await sonucKayitlari(is);
      } catch (e) {
        durumYaz(t("history.refresh_failed", { hata: e.message }));
      }
      kayitlarCep.set(is.id, kayitlar);
      ciz();
      if (baglam && typeof baglam.bitince === "function") {
        try {
          await baglam.bitince(is, kayitlar);
        } catch (e) {
          durumYaz(e.message);
        }
      } else if (typeof loadHistory === "function") {
        // Geri çağrı galeriyi kendi yeniliyor (core.js'in akışı); yoksa burası.
        loadHistory().catch(() => {});
      }
      return;
    }
    const mesaj =
      is.durum === "iptal"
        ? t("gen.job_cancelled")
        : t("gen.job_failed", { hata: is.hata || t("common.unknown") });
    if (baglam && typeof baglam.hatada === "function") baglam.hatada(mesaj);
  }

  /** Sunucudan gelen bir iş hâli: birleştir, çiz, kapanışsa tepki ver. Aynı hâlin
   *  ikinci kez gelmesi (akışın örtüşmesi, yoklama) zararsız: id'ye göre yazılır. */
  function guncelle(is) {
    if (!is || !is.id) return;
    const eski = isler.get(is.id);
    isler.set(is.id, is);
    const degisti =
      !eski ||
      eski.durum !== is.durum ||
      eski.bitti !== is.bitti ||
      eski.basladi !== is.basladi ||
      eski.hata !== is.hata;
    if (degisti) ciz();
    if (KAPANMIS.has(is.durum) && !(eski && KAPANMIS.has(eski.durum))) kapanis(is);
  }

  /** 202 gövdesindeki iş core.js'ten teslim (sözleşme dosya başında). */
  function kaydetIs(is, baglam) {
    if (!is || !is.id) return;
    if (baglam) baglamlar.set(is.id, baglam);
    const mevcut = isler.get(is.id);
    if (mevcut && KAPANMIS.has(mevcut.durum)) {
      // Akış işin bitişini teslimden ÖNCE getirdi (sahte/çok hızlı işçi): geri
      // çağrı yine çalışmalı, yoksa döküm turu sonsuza kadar bekleme kutusunda kalır.
      kapanis(mevcut);
      return;
    }
    guncelle(is);
  }

  /** core.js'in 429'u: sunucunun cümlesi + `Retry-After` ipucu panelin durum satırında. */
  function uyar(mesaj, retryAfter) {
    const sn = parseInt(retryAfter || "", 10);
    durumYaz(sn > 0 ? `${mesaj} ${t("isler.retry_after", { sn })}` : mesaj);
    dugme.classList.add("is-uyari");
    setTimeout(() => dugme.classList.remove("is-uyari"), 4000);
  }

  // ── Kaynak: liste, akış, yedek yoklama ─────────────────────────────

  async function yukle() {
    const res = await fetch(LISTE_YOLU);
    if (!res.ok) throw new Error(hataMetni(await res.json().catch(() => ({})), res.status));
    const { isler: gelen } = await res.json();
    for (const is of gelen) guncelle(is);
    // Bitmiş işlerin önizlemesi yenilenmiş sekmede de olsun; `guncelle` bunu
    // yalnız kapanış ANINDA çekiyor (listeden gelen iş çoktan kapanmış).
    for (const is of gelen) {
      if (is.durum === "bitti" && !kayitlarCep.has(is.id) && !baglamlar.has(is.id)) {
        kayitlarCep.set(is.id, []);
        sonucKayitlari(is)
          .then((k) => {
            kayitlarCep.set(is.id, k);
            if (k.length) ciz();
          })
          .catch(() => {});
      }
    }
    ciz();
  }

  function yoklamayiDurdur() {
    if (yoklama) clearInterval(yoklama);
    yoklama = null;
  }

  function yoklamayaGec() {
    if (yoklama) return;
    durumYaz(t("isler.yoklama"));
    yoklama = setInterval(() => yukle().catch(() => {}), YOKLAMA_MS);
  }

  /** Düşüşte oturum soruluyor: `EventSource` 401'i göremez, `fetch` sarmalı görür. */
  function oturumKontrol() {
    if (oturumSoruldu) return;
    oturumSoruldu = true;
    fetch("/api/hesap/ben")
      .then(() => {
        oturumSoruldu = false;
      })
      .catch(() => {
        oturumSoruldu = false;
      });
  }

  function bagla() {
    if (typeof EventSource !== "function") {
      yoklamayaGec();
      return;
    }
    kaynak = new EventSource(AKIS_YOLU);
    kaynak.addEventListener("is", (e) => {
      try {
        guncelle(JSON.parse(e.data));
      } catch {
        /* bozuk olay: bir sonraki tur aynı işi yine getirir */
      }
    });
    kaynak.onopen = () => {
      dususler = 0;
      yoklamayiDurdur();
      if (durumSatiri.textContent === t("isler.yoklama")) durumYaz("");
    };
    kaynak.onerror = () => {
      dususler++;
      oturumKontrol();
      // Sunucu 10 dk'da akışı kendi kapatır: tarayıcı `error` verir ve
      // yeniden bağlanır (CONNECTING) — bu bir düşüş değil, `open` sayacı
      // sıfırlar. KAPALI (CLOSED: 401/404/yanlış içerik türü) ya da art arda
      // üç düşüş → yedek yoklama; akış bu sekmede bir daha denenmez.
      if (kaynak.readyState === EventSource.CLOSED || dususler >= DUSUS_ESIGI) {
        kaynak.close();
        kaynak = null;
        yoklamayaGec();
      }
    };
  }

  // ── Panel yüzeyi ───────────────────────────────────────────────────

  dugme.addEventListener("click", () => {
    const acilacak = !panel.classList.contains("open");
    closeSheets();
    if (acilacak) {
      ciz(); // model etiketleri katalog geldikten sonra doğru okunsun
      openSheet("isler-sheet");
      dugme.setAttribute("aria-expanded", "true");
      sheetTetik = dugme;
    }
  });
  $("isler-close").addEventListener("click", closeSheets);

  setInterval(sureleriTazele, 1000);
  // Sekme arka planda kalıp geri gelince liste bir kez tazelenir: tarayıcı
  // gizli sekmede zamanlayıcıları kısıyor, akış düşmüş olabilir.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") yukle().catch(() => {});
  });

  yukle()
    .catch((e) => durumYaz(e.message))
    .then(bagla);

  return { kaydetIs, uyar, yukle };
})();
