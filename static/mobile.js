// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
// Mobil yerleşimin ÖLÇÜM katmanı — CSS'in tek başına yapamadığı tek iş.
//
// Klasik script (bkz. core.js başlığı), en son yüklenen dosya: yalnızca zaten
// var olan öğeleri ölçüyor, hiçbir açılış çağrısı yapmıyor.
//
// NEDEN VAR: `.canvas`ın alt boşluğu bugün 260px'lik bir SABİT (style.css:211)
// ve composer'ın yüksekliğini karşılaması gerekiyor — akışın son satırı onun
// altında kalmasın diye. Masaüstünde bu iyi bir yaklaşıklık; telefonda değil:
//   • 260px, 390×844'lük bir ekranda viewport'un ~%31'i — boşuna kayıp,
//   • composer referans görselleri (.composer-refs) eklenince UZUYOR ve
//     260px'i aşıyor; o anda son satır composer'ın ALTINDA kalıyor ve
//     kullanıcı ona hiç ulaşamıyor.
// CSS bir öğenin yüksekliğini başka bir öğenin padding'ine bağlayamıyor, bu
// yüzden ölçüm JS'te. Yazılan tek şey bir CSS değişkeni (`--composer-h`);
// yerleşim kararlarının tamamı mobile.css'te kalıyor.
//
// GERİ DÜŞÜŞ: bu dosya hiç çalışmasa (yüklenemedi, ResizeObserver yok)
// `--composer-h` mobile.css'teki 260px varsayılanında kalır — yani bugünkü
// davranış. Bozulma değil, iyileştirmenin yokluğu.

(() => {
  const composer = $("composer");
  const kok = document.documentElement;
  if (!composer) return;

  function olc() {
    // `hidden` composer (Araçlar/Kütüphane görünümleri) 0 yükseklik verir;
    // o durumda tuvalin altında boşluk tutmanın anlamı yok.
    const h = composer.hidden ? 0 : composer.offsetHeight;
    // Composer'ın kendi alt boşluğu (mobile.css: 12px) ölçüye girmiyor —
    // padding hesabı orada ayrıca ekleniyor.
    kok.style.setProperty("--composer-h", `${Math.round(h)}px`);
  }

  olc();

  if (typeof ResizeObserver === "function") {
    new ResizeObserver(olc).observe(composer);
  } else {
    // ResizeObserver yoksa (çok eski WebView) en azından yön değişiminde
    // yeniden ölç: composer'ın genişliği değişince satır sayısı da değişir.
    window.addEventListener("resize", olc);
  }

  // `hidden` özniteliği ResizeObserver'ı TETİKLEMEZ (öğe yerleşimden
  // düştüğünde gözlemci son ölçüde kalır), o yüzden görünüm değişimi ayrıca
  // izleniyor — aksi halde Araçlar görünümünde tuval 260px boşlukla açılırdı.
  new MutationObserver(olc).observe(composer, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
})();
