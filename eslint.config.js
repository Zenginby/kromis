// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
//
// Ön yüz lint yapılandırması (eslint düz yapılandırma, Faz 0 / Adım 7).
//
// static/ altındaki betikler modül DEĞİL: static/index.html onları sırayla,
// tek küresel kapsama yüklüyor (docs/graflar/onyuz.md). Bu yüzden:
//
//   * `sourceType: "script"` — ES modül sayılsalar her `function foo()` yerel
//     olur ve dosyalar arası çağrılar ayrıştırıcı düzeyinde yanlış okunur.
//   * Dosyalar arası adlar `eslint.paylasilan-adlar.json`dan geliyor: her
//     dosyaya yalnız ÖTEKİ dosyaların üst düzey adları `globals` olarak
//     veriliyor. Kendi adları verilmiyor — böylece aynı adı iki dosya
//     tanımlarsa `no-redeclare` (recommended) bunu hata olarak yakalıyor;
//     tests/test_id_contract.py'nin "hiçbir üst düzey ad iki dosyada tanımlı
//     değil" iddiasının lint yüzü. Liste elle tutuluyor ve bekçisi
//     tests/test_onyuz_lint_kapisi.py: her ad gerçekten o dosyada tanımlı,
//     her ad başka bir dosyada kullanılıyor, depo haritasının betik-arası
//     kenarları listeyle tutarlı. Eksik bir adı eslint'in kendisi yakalar
//     (`no-undef`), fazla/bayat olanı test.
//   * `no-unused-vars` `vars: "local"`: üst düzey bir işlev başka dosyadan
//     çağrılıyorsa eslint bunu tek dosyaya bakarak bilemez (ölçüldü: 23
//     yalancı bulgu — `beginResultTurn`, `applyModels`, `promptDialog`…).
//     Üst düzey ölü ad denetimi eslint'ten alınıp bekçi teste verildi:
//     orada hiçbir betikte ve index.html'de geçmeyen üst düzey ad kırmızı.
//     İşlev İÇİ kullanılmayan değişken burada hâlâ hata.
//
// `pixel-canvas.js` kapsam dışı: üçüncü parti (Ryan Mulligan, MIT) —
// tests/test_telif_basligi.py ve tests/test_id_contract.py de onu ayrı tutuyor;
// başkasının dosyasını `--fix` ile yeniden yazmak istemiyoruz.
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const js = require("@eslint/js");
const globals = require("globals");
const paylasilan = require("./eslint.paylasilan-adlar.json");

function baskaDosyalarinAdlari(dosya) {
  const sonuc = {};
  for (const [tanimlayan, adlar] of Object.entries(paylasilan.paylasilan)) {
    if (tanimlayan === dosya) continue;
    for (const ad of adlar) {
      // "writable": başka dosyanın atadığı adlar (`currentModel = …`); geri
      // kalanı salt okunur ki yanlışlıkla üzerine yazma `no-global-assign`a düşsün.
      sonuc[ad] = paylasilan.yazilabilir.includes(ad) ? "writable" : "readonly";
    }
  }
  return sonuc;
}

const ORTAK_KURALLAR = {
  "no-undef": "error",
  "no-unused-vars": ["error", { vars: "local", args: "after-used", caughtErrors: "all" }],
  eqeqeq: "error",
};

module.exports = [
  {
    ignores: [
      "node_modules/",
      ".venv/",
      "dist/",
      "build/",
      "docs/",
      "android/",
      "tests/",
      "static/pixel-canvas.js",
    ],
  },
  js.configs.recommended,
  {
    files: ["static/**/*.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "script", globals: { ...globals.browser } },
    rules: ORTAK_KURALLAR,
  },
  // Her betiğe ÖTEKİ betiklerin adları. Yalnız tüketen dosyalar (mobile.js,
  // viewer.js) listede anahtar değil, onlar da herkesin adını alır. Kendi
  // adları verilmez (no-redeclare gerekçesi yukarıda). Dosya listesi diskten:
  // listeye girmeyen yeni bir betik de aynı sözleşmeyle lintlenir.
  ...fs
    .readdirSync(path.join(__dirname, "static"))
    .filter((ad) => ad.endsWith(".js"))
    .map((ad) => `static/${ad}`)
    .map((dosya) => ({
      files: [dosya],
      languageOptions: {
        globals: {
          ...baskaDosyalarinAdlari(dosya),
          // index.html satır içi betiği: `window.KROMIS_LANG` / `window.KROMIS_I18N`
          // sunucu şablonundan geliyor (routers/kok.py); i18n.js bunları okuyor.
          KROMIS_LANG: "readonly",
          KROMIS_I18N: "readonly",
        },
      },
    })),
  {
    files: ["static/settings.js"],
    languageOptions: {
      globals: Object.fromEntries(Object.keys(paylasilan.iyimser_kancalar).map((ad) => [ad, "readonly"])),
    },
  },
  {
    files: ["eslint.config.js"],
    languageOptions: { sourceType: "commonjs", globals: { ...globals.node } },
  },
];
