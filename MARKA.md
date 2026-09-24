# Marka politikası — "Kromis" adı ve logosu

**Kod FSL-1.1-ALv2. Ad ve logo DEĞİL.**

Bu ayrım bilinçli ve bütün amacı şu: kodu özgürce alabilmen ama aldığın şeyin
**Kromis olduğunu söyleyememen**. Firefox, Rust, Signal ve Chromium aynı ayrımı
kullanır — kaynağını açık tutmanın kimliğini feda etmeyi gerektirmediği yer
burasıdır.

Bir lisans (FSL) kodun nasıl kullanılacağını söyler. Marka hakkı, bir ürünün
**kim tarafından yapıldığına** dair kullanıcıyı yanıltmayı engeller. FSL'e
harfiyen uyan bir çatal bile, adı "Kromis" kaldığı sürece bu politikayı ihlal
eder — lisansın kendi "Trademarks" maddesi de bunu açıkça söylüyor: kaynağı
göstermek dışında ad, marka ve ürün adı üzerinde hiçbir hak verilmiyor.

> Adın kendisinin nereden geldiği, hangi ticaret unvanıyla ve hangi alan
> adlarıyla ilişkilendiği ayrı bir belgede:
> [docs/marka-ve-unvan.md](docs/marka-ve-unvan.md).

## Kapsam

Aşağıdakiler telif sahibine ait ve [LICENSE](LICENSE)'ın verdiği izinlerin
DIŞINDADIR:

| Ne | Nerede |
|---|---|
| "Kromis" ve "Kromis Studio" adları | ürün adı, depo adı, uygulama adı |
| Logo, işaret ve ikonlar | `branding/` (SVG, `.ico`, `.iconset`) |
| Uygulama ikonları | `static/favicon.svg`, `static/favicon.ico`, `static/apple-touch-icon.png`, `android/app/src/main/res/mipmap-*` |
| Motto/banner varlıkları | `docs/flow-ui/assets/brand/` |
| Uygulama kimlikleri | `com.zenginby.kromis` (Android `applicationId`, macOS `bundle_identifier`) |
| Ürünün görsel kimliği | bir bütün olarak; kullanıcıyı Kromis'e baktığına inandıracak taklit |

`branding/` altındaki dosyalar depoda lisans kapsamında durmuyor: paket
üretilebilsin diye oradalar, yeniden kullanılabilsin diye değil.

## Yapabileceklerin — izin istemeden

* **Kromis'ten söz etmek.** İncelemek, anlatmak, eleştirmek, kıyaslamak,
  öğretmek, ekran görüntüsü koymak. Adı ürünü tanımlamak için kullanmak
  serbesttir.
* **Kaynağın Kromis olduğunu söylemek** — hatta bunu yapman gerekir:
  > "Bu proje, Kromis Studio'dan (https://github.com/Zenginby/kromis) türetilmiştir."

  Bu cümle bir ihlal değil, tam tersi: lisansın "Trademarks" maddesinin
  serbest bıraktığı tek kullanım — kaynağı göstermek — tam olarak bu.
* **Değiştirilmemiş resmî paketleri yeniden dağıtmak** (ayna, USB, kurum içi
  depo) — dosyalara dokunulmadığı sürece.
* **Logoyu, Kromis'i gösteren bir bağlantının yanında kullanmak** — bloglarda,
  listelerde, "şu araçla üretildi" satırlarında.

## Yapamayacakların

* Çatalını, yeniden paketlemeni ya da servisini **"Kromis"** ya da ona
  karışacak bir adla (Kromis Pro, KromisAI, Kromiz, Chromis…) adlandırmak.
* Logoyu, ikonları ya da işareti **kendi ürününün kimliği olarak** kullanmak.
* "Kromis" içeren alan adı, sosyal medya hesabı, uygulama mağazası kaydı
  açmak.
* Resmî, onaylı, sponsorlu ya da bağlantılı olduğunu ima etmek.
* Değiştirilmiş bir paketi resmî paket gibi dağıtmak — özellikle
  `com.zenginby.kromis` kimliğiyle imzalanmış bir APK gibi görünecek biçimde.

## Çatal yapıyorsan — değiştirilecekler listesi

FSL sana çatal hakkını veriyor (rakip bir ürün ya da hizmet olarak sunmamak
şartıyla — [TELIF.md](TELIF.md)); bu liste o hakkı kullanırken markayı temiz
bırakmanın somut karşılığı. Uzun görünüyor ama tek oturumluk iş:

1. **Ad.** `README.md`, `README.en.md`, `static/index.html` (`<title>`),
   `desktop.py` pencere başlığı, `kromis.spec` içindeki ürün adı,
   `android/app/src/main/res/values/strings.xml`.
2. **Uygulama kimliği.** `android/app/build.gradle` → `applicationId` ve
   `namespace`; `kromis.spec` → `bundle_identifier`. Kendi ters alan adını
   kullan: `com.seninadin.urunun`.
3. **İkon ve logolar.** `branding/`, `static/favicon.*`,
   `static/apple-touch-icon.png`, Android `mipmap-*` klasörleri. Silmek
   yetmez — kendi varlıklarınla DEĞİŞTİR, yoksa paket derlenmez.
4. **Güncelleme kanalı.** `guncelleme.py` → `DEPO = "Zenginby/kromis"`. Bunu
   değiştirmemek iki şeyi birden kırar: kullanıcılarına BAŞKASININ sürümünü
   "güncelleme var" diye gösterirsin ve resmî depoya kendi kullanıcılarının
   trafiğini bindirirsin. (`tests/test_depo_adresi.py` tek kaynağı zaten
   zorluyor; çatalda o testi yeşile döndürmek tam olarak bu adımı yapmaktır.)
5. **Kaynak kodu bağlantısı.** `static/index.html` → "Hakkında" panelindeki
   kaynak ve LICENSE bağlantıları ile telif satırı. Bağlantılar **kendi deponu**
   göstermeli (kullanıcı neyi çalıştırdığını bilsin; Kromis'in köken olduğunu
   ayrıca söyleyebilirsin), lisans bağlantısı durmalı (FSL → Redistribution)
   — burayı silmek bir çözüm değil, ihlaldir.
6. **Telif bildirimi DURUR.** Kendi telifini EKLERSİN, var olanı kaldırmazsın
   (FSL → Redistribution: "not remove any copyright notices"). Doğrusu şöyle
   görünür:
   ```
   Copyright (C) 2026 Alperen Zengin (@Zenginby)
   Copyright (C) 2026 Senin Adın — değişiklikler
   ```

## İzin istemek

Yukarıda "yapamazsın" diyen bir şeye ihtiyacın varsa sorabilirsin — bu depoda
bir issue aç, ne yapmak istediğini anlat. Kurum içi dağıtım, akademik kullanım
ve entegrasyon ortaklıkları için izin verilmesi olağan.

## İhlal

Marka şikâyeti telif şikâyetinden AYRI bir kanaldan gider (platformların
"trademark" formu). Yol haritası: [TELIF.md](TELIF.md) → "İhlal görürsen ne
yapmalı".
