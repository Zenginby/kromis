// Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
// GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
// Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
// Kromis — arayüz sözlüğünün istemci tarafı.
//
// Klasik script (ES module DEĞİL): bütün parçalar TEK global kapsamı paylaşıyor
// ve bu dosya index.html'deki yükleme sırasının BAŞINDA. Sıra bağlayıcı —
// aşağıdaki her betik `t()`yi üst düzeyinde çağırabiliyor ve tanımsız bir ada
// dokunmak o betiğin TAMAMINI düşürür.
//
// ── Bu dosya neden var ───────────────────────────────────────────────
// Şablondaki metinleri SUNUCU çeviriyor (`i18n.render`), yani ilk boyamada
// hiçbir şey yanıp sönmüyor. Ama arayüzün yarısı çalışma anında kuruluyor:
// durum satırları, onay metinleri, hata mesajları, sayı taşıyan cümleler.
// Onlar bir yer tutucuyla ifade edilemez, bu yüzden aynı sözlük tarayıcıya da
// veriliyor.
//
// Sözlük `window.KROMIS_I18N` olarak index.html'e GÖMÜLÜ geliyor; burada bir
// `fetch` YOK ve olmamalı — o istek dönene kadar `t()` çağıran her betik
// dilsiz kalırdı ve bu dosya sıranın başında olduğu için o pencere tam olarak
// arayüzün kurulduğu an.

/** Sunucunun seçtiği dil. Yalnız OKUNUYOR: dili değiştiren yol
 *  `POST /api/prefs` + sayfa yenileme (settings.js), çünkü sunucu HTML'i
 *  yeniden üretmeden şablondaki metinler eski dilde kalırdı.
 *
 *  `||` dalı yalnız SUNUCUSUZ açılan bir şablonda çalışıyor (yer tutucu
 *  değiştirilmemiş) ve değeri `i18n.DEFAULT` ile aynı olmak zorunda: ayrı
 *  düşselerdi aynı sayfanın şablon metinleri bir dilde, betiklerin ürettiği
 *  cümleler başka bir dilde görünürdü. */
const KROMIS_DIL = window.KROMIS_LANG || "en";

/** Sözlük. `||` ile boş nesneye düşüyor: index.html'i BU dosyayla birlikte
 *  ama sunucusuz açan bir okur (ya da yer tutucusu değiştirilmemiş bir
 *  şablon) `t()` çağrısında TypeError almasın — o durumda her anahtar
 *  kendisi olarak görünür, ki teşhisi kolay. */
const KROMIS_SOZLUK = window.KROMIS_I18N || {};

// `{ad}` — sunucu tarafındaki `i18n._VAR` ile BİREBİR aynı desen. İki taraf
// ayrışırsa aynı metin bir yerde değişkenli, öbüründe ham görünürdü.
const I18N_DEGISKEN = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;

/** Anahtarın karşılığı; sözlükte yoksa ANAHTARIN KENDİSİ.
 *
 * Sessiz boşluk değil görünür anahtar — sunucu tarafındaki `i18n.t` ile aynı
 * karar ve aynı gerekçe: çevrilmemiş bir yüzey fark edilebilir olmalı.
 * Kullanıcıya ulaşmasını `tests/test_i18n.py` kapatıyor; o test bu dosyadaki
 * sabit dizeli `t("…")` çağrılarını tarayıp her anahtarın İKİ katalogda da
 * bulunduğunu doğruluyor.
 *
 * Bilinmeyen bir değişken adı SİLİNMİYOR, olduğu gibi bırakılıyor: eksik bir
 * argüman yüzünden cümlenin ortasının buharlaşması, ekranda duran `{adet}`ten
 * çok daha sessiz bir kusur olurdu (sunucu tarafının kararının aynısı).
 *
 * @param {string} anahtar
 * @param {Object<string, *>} [degiskenler]
 * @returns {string}
 */
function t(anahtar, degiskenler) {
  const metin = KROMIS_SOZLUK[anahtar];
  if (metin === undefined) return anahtar;
  if (!degiskenler) return metin;
  return metin.replace(I18N_DEGISKEN,
    (tam, ad) => (ad in degiskenler ? String(degiskenler[ad]) : tam));
}

/** Sayıya göre tekil/çoğul seçen ince bir sarmalayıcı.
 *
 * Türkçe'de çoğul eki sayıdan sonra KULLANILMAZ ("3 görsel", "3 görseller"
 * değil), İngilizce'de kullanılır ("3 images"). Yani "{n} görsel" tek bir
 * anahtarla Türkçe'de doğru, İngilizce'de yanlış olurdu — ve bu, çeviriyi
 * yapan kişinin fark etmesi beklenen bir şey değil, MEKANİK bir fark.
 *
 * İki anahtar (`…_one` / `…_many`) yerine tek anahtar + burada seçim: bir
 * dilin ayrımı yoksa iki anahtarın değeri aynı yazılır ve katalogda hiçbir
 * şey bozulmaz. Daha karmaşık çoğul kuralları olan diller (Rusça, Arapça)
 * buraya geldiğinde bu fonksiyon büyür — bugün gereğinden fazla genel olması
 * gerekmiyor.
 */
function tc(anahtarTekil, anahtarCogul, adet, degiskenler) {
  const secili = adet === 1 ? anahtarTekil : anahtarCogul;
  return t(secili, Object.assign({ n: adet }, degiskenler || {}));
}
