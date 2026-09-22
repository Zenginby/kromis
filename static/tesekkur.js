// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// Teşekkür sayfasının betiği (Faz 4 / 4, belge §4) — static/tesekkur.html'in
// tek betiği (i18n.js dışında). Tek uç: GET /api/kredi, 2 sn'de bir, en çok 30 sn.
//
// NEDEN YOKLAMA: kredi Polar'ın webhook'uyla yatar (services/odeme.py) ve o
// teslimat kullanıcının geri dönüşünden önce de sonra da gelebilir; sayfa
// "işlendi" demeden önce KANIT bekler. Kanıt: `siparisler`in en yenisi son
// 15 dakika içinde — bu sayfaya yalnız Polar'ın `success_url`uyla gelinir,
// yani "az önce" bir sipariş olmalı. Bakiye farkına bakılmaz: webhook
// yönlendirmeden önce geldiyse ilk okuma zaten yeni bakiyeyi taşır ve fark
// sıfır görünürdü. 30 sn'de kanıt yoksa dürüst cümle: "birkaç dakika
// sürebilir" — Polar üstel geri çekilmeyle yeniden dener, kredi gelir.
//
// IIFE, giris.js/planlar.js'in gerekçesiyle; tests/test_id_contract.py `KAPSAM_DISI`.
(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const ARALIK_MS = 2000;
  const TAVAN_MS = 30000;
  const YENI_SIPARIS_MS = 15 * 60 * 1000;
  const baslangic = Date.now();

  function durumYaz(durum, metin) {
    const m = el("tesekkur-mesaj");
    m.dataset.durum = durum;
    m.textContent = metin;
  }

  function yeniSiparisVar(k) {
    const s = (k.siparisler || [])[0];
    if (!s || !s.olusturuldu) return false;
    const zaman = new Date(s.olusturuldu).getTime();
    return !Number.isNaN(zaman) && Date.now() - zaman < YENI_SIPARIS_MS;
  }

  async function yokla() {
    let k = null;
    try {
      const res = await fetch("/api/kredi");
      if (res.status === 401) {
        window.location.replace("/giris?sonra=" + encodeURIComponent(window.location.pathname));
        return;
      }
      if (res.ok) k = await res.json();
    } catch {
      k = null;
    }
    if (k) {
      const toplam = k.toplam ?? k.bakiye;
      el("tesekkur-toplam").textContent = String(toplam);
      if (yeniSiparisVar(k)) {
        durumYaz("islendi", t("tesekkur.islendi", { toplam }));
        return;
      }
    }
    if (Date.now() - baslangic >= TAVAN_MS) {
      durumYaz("gecikti", t("tesekkur.gecikti"));
      return;
    }
    setTimeout(yokla, ARALIK_MS);
  }

  yokla();
})();
