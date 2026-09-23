// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// Yönetim sayfasının betiği (Faz 2 / 8) — static/admin.html'in tek betiği
// (i18n.js dışında). Dört sekme, dört okuma ucu, beş yazma ucu:
//   GET  /api/admin/kullanicilar?q=&sayfa=   · POST /api/admin/kullanicilar/{id}/tavan
//   GET  /api/admin/isler?durum=             · POST /api/admin/kullanicilar/{id}/oturum-dusur
//   GET  /api/admin/metrikler                · POST /api/admin/isler/{id}/iptal
//   (Faz 3 / 3)                              · POST /api/admin/kullanicilar/{id}/plan
//                                            · POST /api/admin/kullanicilar/{id}/kredi
//   GET  /api/admin/odeme-olaylari?hata=1    (Faz 4 / 3: Polar webhook teslimatları;
//                                            Faz 4 / 4: özetin `urunler_bayat`ı uyarı satırı)
//
// "Ödeme" sekmesi (Faz 4 / 3): son 100 teslimat — tür, Polar nesnesi, kullanıcı,
// işlendi damgası ve `hata` KODU (`kullanici_yok`, `urun_yok` …). Kod çevrilmez:
// sağlayıcı sözlüğü, sahip aynı adı günlükte ve belgede arar. Gövde gösterilmez
// (e-posta/adres taşır; içerik Polar panelinde).
//
// Plan seçici ve "kredi ekle" (Faz 3 / 3): plan adları SUNUCUDAN gelmiyor, listeyi
// `PLANLAR` sabiti tutuyor — üç ad kodda katalog (services/planlar.py, K5) ve
// bilinmeyen adı sunucu 422 ile reddeder; bir plan eklendiği gün iki liste
// birlikte değişir (bekçisi tests/test_planlar.py). Kredi düzeltmesi açıklama
// İSTER: sunucu boş açıklamayı 422 yapar, kutu o yüzden zorunlu.
//
// IIFE İÇİNDE (giris.js'in gerekçesi): eslint her static/*.js dosyasına öteki
// betiklerin üst düzey adlarını küresel veriyor; kapalı kapsam çakışmayı ve
// paylaşılan ad defterine girmeyi önler. tests/test_id_contract.py bu dosyayı
// `KAPSAM_DISI`nda tutar, id bağlarını tests/test_admin.py sınar.
//
// 401 → /giris?sonra=/admin (core.js'in sarmalı burada yok, sayfa kendi bakar);
// 403 → mesaj satırı (admin bayrağı bu arada düşmüş olabilir). Açık sekme
// 30 sn'de bir yenilenir (belge §8); gizli sekmede zamanlayıcı durmaz ama
// `visibilitychange` görünür olunca bir kez erken çeker.
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const mesaj = el("admin-mesaj");
  const SEKMELER = ["kullanicilar", "kuyruk", "metrikler", "odeme"];
  const PLANLAR = ["free", "temel", "pro"];
  const YENILEME_MS = 30000;
  const SAYFA_ADEDI = 50;
  // Durum/tür etiketleri isler.js'in aynı anahtarları — tablo hâlinde, çünkü
  // tests/test_i18n.py anahtarı DİZE olarak arar (birleştirilen anahtar görünmez).
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

  let sekme = "kullanicilar";
  let sayfa = 1;
  let toplam = 0;
  let aramaZamanlayici = null;

  function mesajYaz(metin, tur) {
    mesaj.textContent = metin || "";
    mesaj.hidden = !metin;
    mesaj.dataset.tur = tur || "bilgi";
  }

  /** `zaman.damga` biçimi (`2026-09-18T12:00:00`) → `2026-09-18 12:00`; yoksa tire. */
  /** Sunucunun damgası UTC ve dilimli (`zaman.damga_utc`, Faz 2 / 10); gösterim
   *  yöneticinin YEREL saatinde `YYYY-AA-GG SS:DD`. `toLocaleString` değil: biçim
   *  tarayıcının diline göre değişir, tablo sütunu sabit genişlikte kalsın. Süre
   *  sayacı (`sureMetni`) da aynı dizeyi `Date`e verir — dilimsiz dize orada
   *  saat dilimi farkı kadar yanlış süre gösteriyordu (isler.js `an` yorumu). */
  function tarih(damga) {
    if (!damga) return "—";
    const d = new Date(damga);
    if (Number.isNaN(d.getTime())) return damga;
    const iki = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())} ${iki(d.getHours())}:${iki(d.getMinutes())}`;
  }

  function detayMetni(govde, durum) {
    const d = govde && govde.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const m = d
        .map((e) => (e && e.msg) || "")
        .filter(Boolean)
        .join(" ");
      if (m) return m;
    }
    return t("admin.hata_genel", { durum });
  }

  async function istek(yol, secenekler) {
    let res;
    try {
      res = await fetch(yol, secenekler);
    } catch {
      throw new Error(t("admin.baglanti_yok"));
    }
    if (res.status === 401) {
      window.location.replace("/giris?sonra=" + encodeURIComponent("/admin"));
      throw new Error(t("admin.hata_genel", { durum: 401 }));
    }
    const veri = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detayMetni(veri, res.status));
    return veri;
  }

  function gonder(yol, govde) {
    return istek(yol, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(govde || {}),
    });
  }

  function yenilendiYaz() {
    const saat = new Date().toTimeString().slice(0, 8);
    el("admin-yenilendi").textContent = t("admin.yenilendi", { saat });
  }

  function hucre(metin, sinif) {
    const td = document.createElement("td");
    td.textContent = metin;
    if (sinif) td.className = sinif;
    return td;
  }

  /** Düğme/kutu taşıyan hücre: `td` tablo hücresi KALIR, esnek yerleşim içteki
   *  `div`de — `td { display: flex }` hücreyi tablodan düşürüp ölçüsüz bırakıyordu
   *  (ölçüldü: E2E'de düğme "görünmez" sayıldı). */
  function islemHucresi(...cocuklar) {
    const td = document.createElement("td");
    const kap = document.createElement("div");
    kap.className = "admin-islem";
    kap.append(...cocuklar);
    td.append(kap);
    return td;
  }

  function dugme(metin, tiklandi, tehlike) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "admin-dugme";
    b.textContent = metin;
    if (tehlike) b.dataset.tehlike = "1";
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await tiklandi();
      } catch (err) {
        mesajYaz(err.message, "hata");
      } finally {
        b.disabled = false;
      }
    });
    return b;
  }

  function bosSatir(tbody, sutun) {
    const tr = document.createElement("tr");
    tr.className = "admin-bos";
    const td = hucre(t("admin.bos"));
    td.colSpan = sutun;
    tr.append(td);
    tbody.replaceChildren(tr);
  }

  // ── Kullanıcılar ───────────────────────────────────────────────────

  function kullaniciSatiri(k) {
    const tr = document.createElement("tr");
    tr.dataset.id = k.id;
    const eposta = hucre(k.eposta);
    if (k.is_admin) {
      const rozet = document.createElement("span");
      rozet.className = "admin-rozet";
      rozet.textContent = t("admin.rozet_admin");
      eposta.append(rozet);
    }
    if (!k.dogrulandi) {
      const rozet = document.createElement("span");
      rozet.className = "admin-rozet";
      rozet.dataset.tur = "uyari";
      rozet.textContent = t("admin.rozet_dogrulanmamis");
      eposta.append(rozet);
    }
    // Faz 4 / 5: silinmiş hesap — anonim e-posta, iki damga (istek anı; içerik temizliği).
    // `temizlendi_at` boşken içerik hâlâ bekleme süresinde (7 gün), bakım turu silecek.
    if (k.silindi_at) {
      const rozet = document.createElement("span");
      rozet.className = "admin-rozet";
      rozet.dataset.tur = "silindi";
      rozet.textContent = k.temizlendi_at
        ? t("admin.rozet_temizlendi", { tarih: tarih(k.temizlendi_at) })
        : t("admin.rozet_silindi", { tarih: tarih(k.silindi_at) });
      eposta.append(rozet);
    }
    // Faz 4 / 4: Polar müşteri kimliği (panelde arama için); NULL = hiç satın almamış.
    if (k.polar_musteri_id) {
      const musteri = document.createElement("span");
      musteri.className = "admin-not admin-musteri";
      musteri.textContent = t("admin.musteri_id", { id: k.polar_musteri_id });
      eposta.append(musteri);
    }
    const kutu = document.createElement("input");
    kutu.type = "number";
    kutu.min = "1";
    kutu.step = "1";
    kutu.placeholder = t("admin.tavan_ontanimli");
    kutu.value = k.gunluk_kredi_tavani === null ? "" : String(k.gunluk_kredi_tavani);
    kutu.setAttribute("aria-label", t("admin.sutun_tavan"));
    const yaz = dugme(t("admin.tavan_yaz"), async () => {
      const deger = kutu.value.trim() === "" ? null : Number(kutu.value);
      await gonder(`/api/admin/kullanicilar/${k.id}/tavan`, { tavan: deger });
      mesajYaz(t("admin.tavan_yazildi"), "basari");
      await kullanicilariYukle();
    });
    const sil = dugme(t("admin.tavan_sil"), async () => {
      await gonder(`/api/admin/kullanicilar/${k.id}/tavan`, { tavan: null });
      mesajYaz(t("admin.tavan_yazildi"), "basari");
      await kullanicilariYukle();
    });
    sil.hidden = k.gunluk_kredi_tavani === null;
    const tavan = islemHucresi(kutu, yaz, sil);
    // Plan seçici: değişince hemen yazar (ayrı bir "Yaz" düğmesi üç seçenek için fazla).
    const secici = document.createElement("select");
    secici.className = "admin-plan";
    secici.setAttribute("aria-label", t("admin.sutun_plan"));
    for (const ad of PLANLAR) {
      const o = document.createElement("option");
      o.value = ad;
      o.textContent = ad;
      o.selected = ad === k.plan;
      secici.append(o);
    }
    secici.addEventListener("change", async () => {
      secici.disabled = true;
      try {
        await gonder(`/api/admin/kullanicilar/${k.id}/plan`, { plan: secici.value });
        mesajYaz(t("admin.plan_yazildi", { plan: secici.value }), "basari");
        await kullanicilariYukle();
      } catch (err) {
        mesajYaz(err.message, "hata");
        secici.value = k.plan;
      } finally {
        secici.disabled = false;
      }
    });
    const plan = islemHucresi(secici);
    // Bakiye (iki kova, Faz 4 / 4) + "kredi ekle": miktar ± tam sayı, açıklama zorunlu
    // (sunucu 422), kova seçici (`hibe` öntanımlı; `paket` = "paket kredisi ekle").
    const bakiye = document.createElement("span");
    bakiye.className = "admin-bakiye";
    bakiye.textContent = t("admin.bakiye_kovalar", { hibe: k.bakiye, paket: k.paket_bakiye ?? 0 });
    const kova = document.createElement("select");
    kova.className = "admin-kova";
    kova.setAttribute("aria-label", t("admin.kredi_kova"));
    // Anahtarlar tabloda, kalıpla kurulmuyor: i18n bekçisi (tests/test_i18n.py) anahtarı metinde arar.
    const KOVA_ANAHTARI = { hibe: "admin.kova_hibe", paket: "admin.kova_paket" };
    for (const ad of ["hibe", "paket"]) {
      const o = document.createElement("option");
      o.value = ad;
      o.textContent = t(KOVA_ANAHTARI[ad]);
      kova.append(o);
    }
    const miktar = document.createElement("input");
    miktar.type = "number";
    miktar.step = "1";
    miktar.placeholder = "±";
    miktar.setAttribute("aria-label", t("admin.kredi_miktar"));
    const aciklama = document.createElement("input");
    aciklama.type = "text";
    aciklama.maxLength = 500;
    aciklama.placeholder = t("admin.kredi_aciklama");
    aciklama.setAttribute("aria-label", t("admin.kredi_aciklama"));
    const ekle = dugme(t("admin.kredi_ekle"), async () => {
      const cevap = await gonder(`/api/admin/kullanicilar/${k.id}/kredi`, {
        miktar: Number(miktar.value),
        aciklama: aciklama.value.trim(),
        kova: kova.value,
      });
      mesajYaz(
        t("admin.kredi_yazildi", { bakiye: cevap.bakiye, paket: cevap.paket_bakiye }),
        "basari",
      );
      await kullanicilariYukle();
    });
    const kredi = islemHucresi(bakiye, kova, miktar, aciklama, ekle);
    const islem = islemHucresi(
      dugme(
        t("admin.oturum_dusur"),
        async () => {
          const cevap = await gonder(`/api/admin/kullanicilar/${k.id}/oturum-dusur`);
          mesajYaz(t("admin.oturum_dusuruldu", { adet: cevap.dusurulen }), "basari");
          await kullanicilariYukle();
        },
        true,
      ),
    );
    tr.append(
      eposta,
      hucre(tarih(k.olusturuldu)),
      hucre(tarih(k.son_gorulme)),
      tavan,
      hucre(String(k.kredi_24sa)),
      hucre(String(k.aktif_is)),
      plan,
      kredi,
      islem,
    );
    return tr;
  }

  async function kullanicilariYukle() {
    const q = el("admin-ara").value.trim();
    const yol =
      `/api/admin/kullanicilar?sayfa=${sayfa}&adet=${SAYFA_ADEDI}` +
      (q ? `&q=${encodeURIComponent(q)}` : "") +
      (el("admin-silinmis").checked ? "&silinmis=true" : "");
    const veri = await istek(yol);
    toplam = veri.toplam;
    const tbody = el("admin-kullanicilar");
    if (!veri.kullanicilar.length) bosSatir(tbody, 9);
    else tbody.replaceChildren(...veri.kullanicilar.map(kullaniciSatiri));
    el("admin-toplam").textContent = t("admin.toplam", { toplam, sayfa });
    el("admin-onceki").disabled = sayfa <= 1;
    el("admin-sonraki").disabled = sayfa * SAYFA_ADEDI >= toplam;
    yenilendiYaz();
  }

  // ── Kuyruk ─────────────────────────────────────────────────────────

  function sure(is) {
    if (!is.basladi) return "—";
    const bitis = is.bitti ? new Date(is.bitti) : new Date();
    const sn = Math.max(0, Math.round((bitis - new Date(is.basladi)) / 1000));
    return t("isler.sure_sn", { sn });
  }

  function isSatiri(is) {
    const tr = document.createElement("tr");
    tr.dataset.id = is.id;
    tr.dataset.durum = is.durum;
    const durum = hucre(t(DURUM_ANAHTARI[is.durum] || is.durum), "admin-durum");
    durum.dataset.durum = is.durum;
    const islem = islemHucresi();
    if (is.durum === "bekliyor") {
      islem.firstChild.append(
        dugme(
          t("admin.iptal"),
          async () => {
            await gonder(`/api/admin/isler/${is.id}/iptal`);
            mesajYaz(t("admin.iptal_edildi"), "basari");
            await kuyruguYukle();
          },
          true,
        ),
      );
    }
    tr.append(
      hucre(is.eposta || is.kullanici_id),
      hucre(t(TUR_ANAHTARI[is.tur] || is.tur)),
      hucre(is.model),
      durum,
      hucre(tarih(is.olusturuldu)),
      hucre(sure(is)),
      islem,
    );
    return tr;
  }

  async function kuyruguYukle() {
    const durum = el("admin-durum").value;
    const veri = await istek(
      "/api/admin/isler" + (durum ? `?durum=${encodeURIComponent(durum)}` : ""),
    );
    const tbody = el("admin-isler");
    if (!veri.isler.length) bosSatir(tbody, 7);
    else tbody.replaceChildren(...veri.isler.map(isSatiri));
    const o = veri.ozet;
    el("admin-kuyruk-ozet").textContent = t("admin.kuyruk_ozet", {
      bekleyen: o.bekleyen,
      calisan: o.calisan,
      hata: o.hata_24sa,
      sn: o.en_eski_bekleyen_sn === null ? 0 : o.en_eski_bekleyen_sn,
    });
    yenilendiYaz();
  }

  // ── Metrikler ──────────────────────────────────────────────────────

  function kart(etiket, deger, alt) {
    const div = document.createElement("div");
    div.className = "admin-kart";
    const e = document.createElement("span");
    e.className = "admin-kart-etiket";
    e.textContent = etiket;
    const d = document.createElement("span");
    d.className = "admin-kart-deger";
    d.textContent = String(deger);
    div.append(e, d);
    if (alt) {
      const a = document.createElement("span");
      a.className = "admin-kart-alt";
      a.textContent = alt;
      div.append(a);
    }
    return div;
  }

  function pencereMetni(p) {
    return t("admin.metrik_is_hata", {
      is: p.is,
      hata: p.hata,
      oran: Math.round(p.hata_orani * 1000) / 10,
    });
  }

  async function metrikleriYukle() {
    const m = await istek("/api/admin/metrikler");
    el("admin-kartlar").replaceChildren(
      kart(t("admin.metrik_kuyruk"), m.kuyruk.derinlik),
      kart(t("admin.metrik_calisan"), m.kuyruk.calisan),
      kart(
        t("admin.metrik_en_eski"),
        m.kuyruk.en_eski_bekleyen_sn === null ? "—" : m.kuyruk.en_eski_bekleyen_sn,
      ),
      kart(t("admin.metrik_son_1sa"), m.son_1sa.is, pencereMetni(m.son_1sa)),
      kart(t("admin.metrik_son_24sa"), m.son_24sa.is, pencereMetni(m.son_24sa)),
      // Faz 3 / 5: sayı GERÇEK kredi (bitende), alt satır rezerv edilen tahmin.
      kart(
        t("admin.metrik_platform_kredi"),
        m.son_24sa.platform_kredi,
        t("admin.metrik_rezerv", { kredi: m.son_24sa.platform_kredi_rezerv }),
      ),
    );
    const modeller = el("admin-modeller");
    if (!m.modeller.length) bosSatir(modeller, 4);
    else {
      modeller.replaceChildren(
        ...m.modeller.map((s) => {
          const tr = document.createElement("tr");
          tr.append(
            hucre(s.model),
            hucre(String(s.adet)),
            hucre(String(s.p50_sn)),
            hucre(String(s.p95_sn)),
          );
          return tr;
        }),
      );
    }
    // Marj (Faz 3 / 5): 7 ve 30 günlük satırlar tek tabloda, `gun` sütunuyla. Sağlayıcı
    // USD'si bugün çoğunlukla bilinmiyor (hiçbir adaptör fiyat vermiyor) — hücre
    // "bilinmiyor (0/N)" der, sıfır YAZMAZ: bilinmeyen maliyet sıfır maliyet değil.
    const marj = el("admin-marj");
    if (!m.marj.length) bosSatir(marj, 8);
    else {
      marj.replaceChildren(
        ...m.marj.map((s) => {
          const tr = document.createElement("tr");
          const maliyet =
            s.maliyet_usd === null
              ? t("admin.marj_bilinmiyor", { bilinen: s.maliyet_bilinen, toplam: s.adet })
              : t("admin.marj_maliyet", {
                  usd: s.maliyet_usd.toFixed(4),
                  bilinen: s.maliyet_bilinen,
                  toplam: s.adet,
                });
          tr.append(
            hucre(String(s.gun)),
            hucre(s.model),
            hucre(String(s.adet)),
            hucre(String(s.kredi)),
            hucre(s.usd.toFixed(2)),
            hucre(maliyet),
            hucre(s.ort_sure_sn === null ? "—" : String(s.ort_sure_sn)),
            hucre(t("admin.marj_hata", { adet: s.hata, kredi: s.hata_kredi })),
          );
          return tr;
        }),
      );
    }
    const isciler = el("admin-isciler");
    if (!m.isciler.length) {
      const li = document.createElement("li");
      li.textContent = t("admin.isci_yok");
      isciler.replaceChildren(li);
    } else {
      isciler.replaceChildren(
        ...m.isciler.map((i) => {
          const li = document.createElement("li");
          li.dataset.canli = String(i.canli);
          li.textContent = `${i.konak} · v${i.surum} · ×${i.es_zamanli} · ${tarih(i.son_kalp)} · ${t(i.canli ? "admin.canli" : "admin.bayat")}`;
          return li;
        }),
      );
    }
    yenilendiYaz();
  }

  async function odemeyiYukle() {
    const yalnizHata = el("admin-odeme-yalniz-hata").checked;
    const m = await istek("/api/admin/odeme-olaylari" + (yalnizHata ? "?hata=1" : ""));
    el("admin-odeme-ozet").textContent = t("admin.odeme_ozet", m.ozet);
    // Faz 4 / 4: ayna 7 günden eski ya da boş → uyarı satırı (sunucu `olay=odeme.urunler_bayat` düşürür).
    el("admin-odeme-uyari").hidden = !m.ozet.urunler_bayat;
    const govde = el("admin-odeme-olaylar");
    if (!m.olaylar.length) bosSatir(govde, 6);
    else {
      govde.replaceChildren(
        ...m.olaylar.map((o) => {
          const tr = document.createElement("tr");
          tr.dataset.hata = String(Boolean(o.hata));
          tr.append(
            hucre(tarih(o.alindi)),
            hucre(o.tur),
            hucre(o.nesne || "—"),
            hucre(o.eposta || "—"),
            hucre(tarih(o.islendi_at)),
            hucre(o.hata || "—"),
          );
          return tr;
        }),
      );
    }
    yenilendiYaz();
  }

  // ── Sekmeler ve yenileme ───────────────────────────────────────────

  const YUKLEYICI = {
    kullanicilar: kullanicilariYukle,
    kuyruk: kuyruguYukle,
    metrikler: metrikleriYukle,
    odeme: odemeyiYukle,
  };

  async function yenile() {
    try {
      await YUKLEYICI[sekme]();
    } catch (err) {
      mesajYaz(err.message, "hata");
    }
  }

  function sekmeAc(ad) {
    sekme = ad;
    for (const s of SEKMELER) el("sekme-" + s).hidden = s !== ad;
    for (const d of document.querySelectorAll("#admin-sekmeler [data-sekme]")) {
      d.setAttribute("aria-selected", String(d.dataset.sekme === ad));
    }
    mesajYaz("");
    yenile();
  }

  el("admin-sekmeler").addEventListener("click", (e) => {
    const d = e.target.closest("[data-sekme]");
    if (d) sekmeAc(d.dataset.sekme);
  });
  el("admin-ara").addEventListener("input", () => {
    clearTimeout(aramaZamanlayici);
    aramaZamanlayici = setTimeout(() => {
      sayfa = 1;
      yenile();
    }, 300);
  });
  el("admin-silinmis").addEventListener("change", () => {
    sayfa = 1;
    yenile();
  });
  el("admin-onceki").addEventListener("click", () => {
    sayfa = Math.max(1, sayfa - 1);
    yenile();
  });
  el("admin-sonraki").addEventListener("click", () => {
    sayfa += 1;
    yenile();
  });
  el("admin-durum").addEventListener("change", yenile);
  el("admin-odeme-yalniz-hata").addEventListener("change", yenile);
  setInterval(yenile, YENILEME_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") yenile();
  });

  mesajYaz(t("admin.yukleniyor"), "bilgi");
  sekmeAc("kullanicilar");
})();
