// Lumeo — görsel büyüteci (lightbox): yakınlaştırma + kaydırma.
//
// Klasik script (bkz. core.js başlığı) ve SON yüklenen dosya: yalnızca HTML'de
// zaten var olan öğelere dinleyici bağlar, hiçbir açılış çağrısı yapmaz — bu
// yüzden settings.js'in dibindeki bootstrap sözleşmesine karışmaz.
//
// Durum tek yerde: (scale, tx, ty) → #viewer-img üzerinde tek bir transform.
// scale=1 "ekrana sığdırılmış" hâldir (CSS max-width/max-height ile), 1'in
// altına inilmez; büyütme oradan yukarı çarpanla ilerler.

(() => {
  const viewer = $("viewer");
  const stage = $("viewer-stage");
  const vimg = $("viewer-img");
  const pct = $("viewer-zoom-pct");
  const dlLink = $("viewer-download");

  const MIN_SCALE = 1;
  const MAX_SCALE = 8;
  const DOUBLE_CLICK_SCALE = 2;
  const WHEEL_K = 0.0015;      // fare tekerleği: yumuşak adım
  const PINCH_K = 0.01;        // trackpad pinch (ctrl'lü wheel): 1:1'e yakın his
  const ARROW_STEP = 60;       // px — klavye okuyla kaydırma
  const RUBBER = 0.35;         // sınır ötesi direnç katsayısı (apple-design §9)
  const SETTLE_MS = 220;       // bırakınca sınıra oturma süresi

  let scale = 1;
  let tx = 0;
  let ty = 0;
  let panning = false;
  let pointerId = null;
  let grabX = 0;
  let grabY = 0;
  let rafId = 0;
  let openerRect = null;   // açılışta tıklanan küçük resmin ekrandaki yeri

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  function render() {
    rafId = 0;
    vimg.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${scale})`;
    pct.textContent = `%${Math.round(scale * 100)}`;
  }

  // Sürükleme sırasında kare başına TEK yazma: pointermove olayları ekranın
  // yenileme hızından sık gelebiliyor ve her birinde transform yazmak
  // compositor'ı gereksiz meşgul ediyor.
  function schedule() {
    if (!rafId) rafId = requestAnimationFrame(render);
  }

  // Görsel sığdırılmış hâlden büyüdükçe taşan yarım genişlik/yükseklik kadar
  // kaydırılabilir; bundan ötesi ekranda boşluk bırakır.
  //
  // Ölçü `offsetWidth`/`clientWidth` ile alınıyor — getBoundingClientRect() İLE
  // DEĞİL. Rect uygulanmış transform'u yansıtır, ama render() rAF'e ertelendiği
  // için zoomAt() clampPan()'i çağırdığında DOM hâlâ ESKİ ölçeği taşıyor:
  // ilk yakınlaştırmada rect sığdırılmış boyutu döndürüp sınırları 0 hesaplıyor
  // ve tx/ty sıfırlanıyordu — yani imleç-sabitli zoom sessizce merkeze zoom'a
  // dönüşüyordu. offset/client ölçüleri yerleşim tabanlı, transform'dan
  // etkilenmez; bu yüzden kare beklemeden doğru sonuç verir.
  function panBounds() {
    return {
      x: Math.max(0, (vimg.offsetWidth * scale - stage.clientWidth) / 2),
      y: Math.max(0, (vimg.offsetHeight * scale - stage.clientHeight) / 2),
    };
  }

  function clampPan() {
    const b = panBounds();
    tx = clamp(tx, -b.x, b.x);
    ty = clamp(ty, -b.y, b.y);
  }

  // Sınır ötesinde sert durmak yerine ilerleyici direnç: gerçek nesneler
  // durmadan önce yavaşlar (apple-design §9).
  function rubberband(value, limit) {
    if (value > limit) return limit + (value - limit) * RUBBER;
    if (value < -limit) return -limit + (value + limit) * RUBBER;
    return value;
  }

  // İmlecin ALTINDAKİ nokta sabit kalacak şekilde ölçekle: doğrudan
  // manipülasyon hissinin tamamı buradan geliyor (merkeze göre zoom yapmak
  // kullanıcının baktığı yeri kaçırır).
  function zoomAt(clientX, clientY, factor) {
    const next = clamp(scale * factor, MIN_SCALE, MAX_SCALE);
    if (next === scale) return;
    const r = stage.getBoundingClientRect();
    const cx = clientX - r.left - r.width / 2;
    const cy = clientY - r.top - r.height / 2;
    tx = cx - (cx - tx) * (next / scale);
    ty = cy - (cy - ty) * (next / scale);
    scale = next;
    clampPan();
    syncCursor();
    schedule();
  }

  function zoomCentered(factor) {
    const r = stage.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, factor);
  }

  function fit() {
    scale = 1;
    tx = 0;
    ty = 0;
    syncCursor();
    schedule();
  }

  function syncCursor() {
    stage.classList.toggle("zoomed", scale > 1);
  }

  function settle() {
    // Yalnız oturma anında geçiş açılır; sürükleme 1:1 kalmalı.
    vimg.style.transition = `transform ${SETTLE_MS}ms var(--ease)`;
    clampPan();
    render();
    setTimeout(() => { vimg.style.transition = ""; }, SETTLE_MS);
  }

  // --- açılış / kapanış -----------------------------------------------------

  // İndir bağlantısı yalnız sunucuda KAYITLI bir görsel için anlamlı:
  // henüz kaydedilmemiş yüklemeler blob: URL'i taşır ve kayıt paneline
  // anlamsız bir ad düşer.
  function syncDownload(src) {
    let name = "";
    try {
      const path = new URL(src, location.href).pathname;
      if (path.startsWith("/output/")) name = decodeURIComponent(path.slice("/output/".length));
    } catch { name = ""; }
    dlLink.hidden = !name;
    if (name) {
      dlLink.setAttribute("href", src);
      dlLink.setAttribute("download", name);
    } else {
      dlLink.removeAttribute("href");
    }
  }

  // Kayıt paneli olan tarayıcıda konumu KULLANICI seçsin (core.js). Panel
  // yoksa hiç araya girilmiyor: <a download> zaten pakette doğru davranıyor.
  dlLink.addEventListener("click", (e) => {
    const href = dlLink.getAttribute("href");
    if (!href || !SUPPORTS_SAVE_PICKER) return;
    e.preventDefault();
    downloadImage(href, dlLink.getAttribute("download"));
  });

  function open(src, alt) {
    if (!src) return;
    vimg.src = src;
    vimg.alt = alt || "";
    syncDownload(src);
    fit();
    render();

    viewer.hidden = false;
    document.body.classList.add("viewer-open");

    // Uzamsal tutarlılık (apple-design §7): büyüteç, tıklanan küçük resmin
    // BULUNDUĞU yerden büyür ve kapanırken oraya döner — nereden geldiği belli.
    const from = openerRect;
    if (from && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const to = vimg.getBoundingClientRect();
      if (to.width > 0 && to.height > 0) {
        const sx = from.width / to.width;
        const sy = from.height / to.height;
        const dx = (from.left + from.width / 2) - (to.left + to.width / 2);
        const dy = (from.top + from.height / 2) - (to.top + to.height / 2);
        vimg.style.transition = "none";
        vimg.style.transform =
          `translate3d(${dx}px, ${dy}px, 0) scale(${Math.min(sx, sy)})`;
        requestAnimationFrame(() => {
          vimg.style.transition = "transform 260ms var(--ease)";
          render();
          setTimeout(() => { vimg.style.transition = ""; }, 260);
        });
      }
    }
    stage.focus();
  }

  function close() {
    document.body.classList.remove("viewer-open");
    viewer.hidden = true;
    vimg.style.transition = "";
    vimg.removeAttribute("src");
    openerRect = null;
  }

  // Tek dışa açılan dikiş: dökümdeki sonuç kartı da büyüteci açıyor
  // (tasarım §6). Yeniden yazım YOK (§1.3) — imleç-sabitli zoom, rubberband
  // pan sınırı, ctrl+wheel pinch ve ok adımı aynen yukarıda. `rect` verilirse
  // büyüteç tıklanan karenin BULUNDUĞU yerden büyüyor: `openerRect` zaten bu
  // iş için vardı, yalnız erişimi #preview-img'e kapalıydı.
  window.openViewer = (src, alt, rect) => {
    openerRect = rect || null;
    open(src, alt);
  };

  // --- olaylar --------------------------------------------------------------

  // preventDefault ZORUNLU: WKWebView'da ctrl'lü wheel (trackpad pinch)
  // engellenmezse TÜM sayfayı zoom'lar — uygulama arayüzü bozulur ve
  // kullanıcının bunu geri alması zor.
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const k = e.ctrlKey ? PINCH_K : WHEEL_K;
    zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * k));
  }, { passive: false });

  stage.addEventListener("dblclick", (e) => {
    if (scale > 1) fit();
    else zoomAt(e.clientX, e.clientY, DOUBLE_CLICK_SCALE);
  });

  // setPointerCapture: imleç görselin dışına çıktığında bile takip sürsün —
  // aksi halde hızlı sürüklemede kaydırma yarıda kopar.
  vimg.addEventListener("pointerdown", (e) => {
    if (scale <= 1) return;
    e.preventDefault();
    panning = true;
    pointerId = e.pointerId;
    vimg.setPointerCapture(pointerId);
    grabX = e.clientX - tx;   // yakalama offset'i korunur (apple-design §2)
    grabY = e.clientY - ty;
    vimg.style.transition = "";
    stage.classList.add("panning");
  });

  vimg.addEventListener("pointermove", (e) => {
    if (!panning || e.pointerId !== pointerId) return;
    const b = panBounds();
    tx = rubberband(e.clientX - grabX, b.x);
    ty = rubberband(e.clientY - grabY, b.y);
    schedule();
  });

  function endPan(e) {
    if (!panning || (e && e.pointerId !== pointerId)) return;
    panning = false;
    stage.classList.remove("panning");
    if (pointerId !== null && vimg.hasPointerCapture(pointerId)) {
      vimg.releasePointerCapture(pointerId);
    }
    pointerId = null;
    settle();
  }
  vimg.addEventListener("pointerup", endPan);
  vimg.addEventListener("pointercancel", endPan);

  // --- iki parmak yakınlaştırma (dokunmatik) --------------------------------
  //
  // NEDEN GEREKLİ: bu dosyadaki yakınlaştırma yolları masaüstüne göre kurulmuş
  // — `wheel` (fare/trackpad) ve `dblclick`. Telefonda ikisi de yok; üstelik
  // `.viewer-stage`de `touch-action: none` (style.css:1448) tarayıcının KENDİ
  // pinch'ini de kapatıyor ve tek parmak kaydırma `if (scale <= 1) return`
  // ile korunuyor. Sonuç: telefonda büyüteçte yakınlaştırmanın tek yolu −/+
  // düğmeleriydi. Bu, bir görsel üretim uygulamasında üretilen görseli
  // inceleyememek demek.
  //
  // Dinleyiciler YAKALAMA (capture) evresinde ve `stage` üzerinde: ikinci
  // parmak `vimg`in dışına da düşebiliyor ve tek parmak kaydırmasının
  // `setPointerCapture`'ı araya girmeden iptal edilmesi gerekiyor.
  const dokunuslar = new Map();
  let pinchUzaklik = 0;
  let pinchX = 0;
  let pinchY = 0;
  let pinchBitis = 0;

  function pinchOlc() {
    const [a, b] = [...dokunuslar.values()];
    return {
      d: Math.hypot(a.x - b.x, a.y - b.y),
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2,
    };
  }

  stage.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "touch") return;
    dokunuslar.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (dokunuslar.size !== 2) return;
    endPan();                       // tek parmak kaydırması pinch'e devrediyor
    const m = pinchOlc();
    pinchUzaklik = m.d;
    pinchX = m.x;
    pinchY = m.y;
  }, true);

  stage.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "touch" || !dokunuslar.has(e.pointerId)) return;
    dokunuslar.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (dokunuslar.size !== 2) return;
    e.preventDefault();

    const m = pinchOlc();
    // İki parmağın ORTASI sabit kalacak şekilde ölçekle — `zoomAt`in imleç
    // altındaki noktayı sabitleyen mantığının birebir aynısı.
    if (pinchUzaklik > 0 && m.d > 0) zoomAt(m.x, m.y, m.d / pinchUzaklik);

    // Parmakların ORTAK kayması = kaydırma. Ayrı bir jest değil: gerçek
    // nesnelerde de iki parmakla hem ölçekleyip hem sürüklenir.
    if (scale > 1) {
      const b = panBounds();
      tx = clamp(tx + (m.x - pinchX), -b.x, b.x);
      ty = clamp(ty + (m.y - pinchY), -b.y, b.y);
      schedule();
    }

    pinchUzaklik = m.d;
    pinchX = m.x;
    pinchY = m.y;
  }, true);

  function dokunusBitti(e) {
    if (!dokunuslar.has(e.pointerId)) return;
    dokunuslar.delete(e.pointerId);
    if (dokunuslar.size >= 2) return;
    if (pinchUzaklik > 0) {
      pinchUzaklik = 0;
      pinchBitis = Date.now();      // aşağıdaki kapatma muhafızı için
      settle();
    }
  }
  stage.addEventListener("pointerup", dokunusBitti, true);
  stage.addEventListener("pointercancel", dokunusBitti, true);

  $("viewer-zoom-in").addEventListener("click", () => zoomCentered(1.4));
  $("viewer-zoom-out").addEventListener("click", () => zoomCentered(1 / 1.4));
  $("viewer-fit").addEventListener("click", fit);
  $("viewer-close").addEventListener("click", close);
  viewer.querySelector("[data-viewer-close]").addEventListener("click", close);
  stage.addEventListener("click", (e) => {
    if (e.target !== stage) return;
    // Pinch'ten HEMEN SONRAKİ tıklamayı yut. İki parmak kalkarken tarayıcı
    // sentetik bir `click` üretebiliyor ve hedefi çoğu kez sahnenin kendisi
    // oluyor — muhafızsız her yakınlaştırma jesti büyüteci KAPATIRDI.
    if (Date.now() - pinchBitis < 350) return;
    close();
  });

  document.addEventListener("keydown", (e) => {
    if (viewer.hidden) return;
    if (e.key === "Escape") { close(); return; }
    if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomCentered(1.4); return; }
    if (e.key === "-") { e.preventDefault(); zoomCentered(1 / 1.4); return; }
    if (e.key === "0") { e.preventDefault(); fit(); return; }
    const step = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
    if (step && scale > 1) {
      e.preventDefault();
      tx += step[0] * ARROW_STEP;
      ty += step[1] * ARROW_STEP;
      clampPan();
      schedule();
    }
  });
})();
