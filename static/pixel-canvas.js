// pixel-canvas — Ryan Mulligan'ın "shimmering pixel background" bileşeni
// (https://ryanmulligan.dev/blog/pixel-canvas/, MIT). Studio'da üretim
// beklenirken bekleyen sonuç kartını dolduruyor: eski morph eden kare
// (`.spinner`) tek bir 20px nesneydi, bu ise görselin YERİNİ tutuyor —
// bekleme, boş bir kutu değil "burada bir görsel oluşuyor" olarak okunuyor.
//
// Kaynaktan İKİ sapma var, ikisi de bu deponun kullanımından doğdu:
//
//  1. `data-manual` — özgün bileşen hover/odak ile canlanıyor. Bizim tetiğimiz
//     fare değil ÜRETİMİN KENDİSİ, o yüzden manuel kipte ana düğüme hiç
//     dinleyici bağlanmıyor; chat.js `start()`/`stop()` çağırıyor.
//  2. `disconnectedCallback` artık `cancelAnimationFrame` da yapıyor. Özgün
//     hâlde yalnız ResizeObserver ve dinleyiciler bırakılıyordu; "appear"
//     döngüsü hiçbir zaman kendiliğinden durmadığı için (o kipte `isIdle`
//     asla true olmuyor) kart DOM'dan silindikten sonra rAF döngüsü kopmuş
//     bir canvas'a çizmeye devam ediyordu. Her üretim bir döngü daha
//     bırakırdı — hover ile açılıp kapanan bir kartta görünmeyen, burada
//     kaçınılmaz olan bir sızıntı.
//
// Betik KÜRESEL kapsamda yükleniyor (deponun düzeni: modül yok), ama `Pixel`
// gibi genel bir ad küresel kapsamda durmamalı — bu yüzden IIFE içinde. Dışa
// açılan tek şey `<pixel-canvas>` özel elemanının kendisi; chat.js ona
// eleman üstünden (`start`/`stop`) ulaşıyor, küresel bir ada ihtiyaç yok.
(() => {
  "use strict";

  class Pixel {
    constructor(canvas, context, x, y, color, speed, delay) {
      this.width = canvas.width;
      this.height = canvas.height;
      this.ctx = context;
      this.x = x;
      this.y = y;
      this.color = color;
      this.speed = this.getRandomValue(0.1, 0.9) * speed;
      this.size = 0;
      this.sizeStep = Math.random() * 0.4;
      this.minSize = 0.5;
      this.maxSizeInteger = 2;
      this.maxSize = this.getRandomValue(this.minSize, this.maxSizeInteger);
      this.delay = delay;
      this.counter = 0;
      this.counterStep = Math.random() * 4 + (this.width + this.height) * 0.01;
      this.isIdle = false;
      this.isReverse = false;
      this.isShimmer = false;
    }

    getRandomValue(min, max) {
      return Math.random() * (max - min) + min;
    }

    draw() {
      const centerOffset = this.maxSizeInteger * 0.5 - this.size * 0.5;

      this.ctx.fillStyle = this.color;
      this.ctx.fillRect(
        this.x + centerOffset,
        this.y + centerOffset,
        this.size,
        this.size
      );
    }

    appear() {
      this.isIdle = false;

      if (this.counter <= this.delay) {
        this.counter += this.counterStep;
        return;
      }

      if (this.size >= this.maxSize) {
        this.isShimmer = true;
      }

      if (this.isShimmer) {
        this.shimmer();
      } else {
        this.size += this.sizeStep;
      }

      this.draw();
    }

    disappear() {
      this.isShimmer = false;
      this.counter = 0;

      if (this.size <= 0) {
        this.isIdle = true;
        return;
      } else {
        this.size -= 0.1;
      }

      this.draw();
    }

    shimmer() {
      if (this.size >= this.maxSize) {
        this.isReverse = true;
      } else if (this.size <= this.minSize) {
        this.isReverse = false;
      }

      if (this.isReverse) {
        this.size -= this.speed;
      } else {
        this.size += this.speed;
      }
    }
  }

  class PixelCanvas extends HTMLElement {
    static register(tag = "pixel-canvas") {
      // İki kez tanımlamak atılan bir istisna: betik iki kez yüklenirse
      // (sürüm sorgusu değişip önbellek ıskalarsa) sayfa TÜMDEN ölmemeli.
      if ("customElements" in window && !customElements.get(tag)) {
        customElements.define(tag, this);
      }
    }

    static css = `
      :host {
        display: grid;
        inline-size: 100%;
        block-size: 100%;
        overflow: hidden;
      }
    `;

    get colors() {
      return this.dataset.colors?.split(",") || ["#f8fafc", "#f1f5f9", "#cbd5e1"];
    }

    get gap() {
      const value = this.dataset.gap || 5;
      const min = 4;
      const max = 50;

      if (value <= min) {
        return min;
      } else if (value >= max) {
        return max;
      } else {
        return parseInt(value);
      }
    }

    get speed() {
      const value = this.dataset.speed || 35;
      const min = 0;
      const max = 100;
      const throttle = 0.001;

      if (value <= min || this.reducedMotion) {
        return min;
      } else if (value >= max) {
        return max * throttle;
      } else {
        return parseInt(value) * throttle;
      }
    }

    get noFocus() {
      return this.hasAttribute("data-no-focus");
    }

    // Manuel kip: tetik fare/odak değil, çağıran kod. Deponun kullanımı bu.
    get manual() {
      return this.hasAttribute("data-manual");
    }

    connectedCallback() {
      const canvas = document.createElement("canvas");
      const sheet = new CSSStyleSheet();

      this._parent = this.parentNode;
      this.shadowroot = this.attachShadow({ mode: "open" });

      sheet.replaceSync(PixelCanvas.css);

      this.shadowroot.adoptedStyleSheets = [sheet];
      this.shadowroot.append(canvas);
      this.canvas = this.shadowroot.querySelector("canvas");
      this.ctx = this.canvas.getContext("2d");
      this.timeInterval = 1000 / 60;
      this.timePrevious = performance.now();
      // Hareket azaltma isteği: gecikme sıfırlanıp hız 0'a çekiliyor —
      // pikseller topluca beliriyor ve TİTREMİYOR. Bu, style.css'teki
      // `prefers-reduced-motion` bloğunun canvas karşılığı; oradaki
      // `animation: none` kuralları bir canvas'ı susturamaz.
      this.reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;

      this.init();
      this.resizeObserver = new ResizeObserver(() => this.init());
      this.resizeObserver.observe(this);

      if (this.manual) return;

      this._parent.addEventListener("mouseenter", this);
      this._parent.addEventListener("mouseleave", this);

      if (!this.noFocus) {
        this._parent.addEventListener("focusin", this);
        this._parent.addEventListener("focusout", this);
      }
    }

    disconnectedCallback() {
      // Sızıntı kapısı (dosya başındaki 2. sapma): döngü DOM'dan kopmuş bir
      // canvas'a çizmeye devam etmesin.
      cancelAnimationFrame(this.animation);
      this.resizeObserver.disconnect();

      if (!this.manual) {
        this._parent.removeEventListener("mouseenter", this);
        this._parent.removeEventListener("mouseleave", this);

        if (!this.noFocus) {
          this._parent.removeEventListener("focusin", this);
          this._parent.removeEventListener("focusout", this);
        }
      }

      delete this._parent;
    }

    handleEvent(event) {
      this[`on${event.type}`](event);
    }

    onmouseenter() {
      this.handleAnimation("appear");
    }

    onmouseleave() {
      this.handleAnimation("disappear");
    }

    onfocusin(e) {
      if (e.currentTarget.contains(e.relatedTarget)) return;
      this.handleAnimation("appear");
    }

    onfocusout(e) {
      if (e.currentTarget.contains(e.relatedTarget)) return;
      this.handleAnimation("disappear");
    }

    /** Manuel kipin dışa açılan yüzü: üretim başladı / bitti. */
    start() {
      this.handleAnimation("appear");
    }

    stop() {
      this.handleAnimation("disappear");
    }

    handleAnimation(name) {
      cancelAnimationFrame(this.animation);
      this.animation = this.animate(name);
    }

    init() {
      const rect = this.getBoundingClientRect();
      const width = Math.floor(rect.width);
      const height = Math.floor(rect.height);

      this.pixels = [];
      this.canvas.width = width;
      this.canvas.height = height;
      this.canvas.style.width = `${width}px`;
      this.canvas.style.height = `${height}px`;
      this.createPixels();
    }

    getDistanceToCanvasCenter(x, y) {
      const dx = x - this.canvas.width / 2;
      const dy = y - this.canvas.height / 2;
      const distance = Math.sqrt(dx * dx + dy * dy);

      return distance;
    }

    createPixels() {
      for (let x = 0; x < this.canvas.width; x += this.gap) {
        for (let y = 0; y < this.canvas.height; y += this.gap) {
          const color = this.colors[
            Math.floor(Math.random() * this.colors.length)
          ];
          const delay = this.reducedMotion
            ? 0
            : this.getDistanceToCanvasCenter(x, y);

          this.pixels.push(
            new Pixel(this.canvas, this.ctx, x, y, color, this.speed, delay)
          );
        }
      }
    }

    animate(fnName) {
      this.animation = requestAnimationFrame(() => this.animate(fnName));

      const timeNow = performance.now();
      const timePassed = timeNow - this.timePrevious;

      if (timePassed < this.timeInterval) return;

      this.timePrevious = timeNow - (timePassed % this.timeInterval);

      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

      for (let i = 0; i < this.pixels.length; i++) {
        this.pixels[i][fnName]();
      }

      if (this.pixels.every((pixel) => pixel.isIdle)) {
        cancelAnimationFrame(this.animation);
      }
    }
  }

  PixelCanvas.register();
})();
