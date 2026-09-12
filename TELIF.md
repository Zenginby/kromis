# Telif, lisans ve ihlal bildirimi

Bu belge üç soruyu cevaplıyor: **kim sahibi**, **ne yapabilirsin**, ve
**birileri kuralı çiğnerse ne olur**. Lisansın kendisi [LICENSE](LICENSE)'dadır;
burası onun okunabilir kaydı ve çevresi. Çelişki hâlinde bağlayıcı olan
LICENSE'ın İngilizce metnidir.

Ad ve logo lisansın KAPSAMI DIŞINDA — ayrı belge: [MARKA.md](MARKA.md).

## Telif sahibi

```
Copyright (C) 2026 Alperen Zengin (@Zenginby)
```

Kromis Studio'nun kaynak kodu, belgeleri ve görsel varlıkları tek telif
sahibine ait. Depo geçmişindeki `Claude <noreply@anthropic.com>` commit'leri
telif sahibinin yönlendirmesiyle üretilmiş çalışmalardır, ayrı bir hak sahibi
doğurmaz; `github-actions[bot]` commit'leri ise yalnız sürüm numarası yazar.

Bu tekillik pratik bir şey: **lisansı değiştirmek mümkün.** Çok yazarlı bir
projede aşağıdaki geçiş, katkı veren herkesin tek tek onayını gerektirirdi.

## Lisans geçişi — MIT'ten AGPL-3.0'a

**v0.19.0 ve öncesi MIT'ti. Bu değişikliği taşıyan commit'ten sonraki her sürüm
GNU AGPL-3.0.**

### Neden

Depo 2026-09-11'de public'e açıldı ve MIT ile açıldı. MIT'in izin verdiği şey
şuydu:

> ...to deal in the Software **without restriction**, including without
> limitation the rights to use, copy, modify, merge, publish, distribute,
> **sublicense, and/or sell** copies...

Yani herhangi biri Kromis'i alıp adını değiştirebilir, kaynağını kapatabilir,
kendi ürünü olarak satabilirdi. Tek yükümlülüğü telif bildirimini kopyanın bir
yerinde bırakmaktı — kaynağı açmak, atıf vermek, haber vermek zorunda değildi.
Bu bir kusur değil, MIT'in tasarımı; yanlış olan şey bu projenin ondan
beklediğiydi.

AGPL-3.0 aynı özgürlükleri kullanıcıya verir ama **karşılığını ister**:
değiştirip dağıtan, değiştirdiği kaynağı da aynı lisansla açmak zorundadır.

### Geriye yürümüyor

Bir lisans, verildikten sonra geri alınamaz. **v0.19.0'ı MIT altında indirmiş
biri, O SÜRÜM için MIT haklarını kalıcı olarak korur** — bu belge onu
değiştirmez ve değiştirmeye çalışmıyor. Geçiş yalnız bundan sonraki sürümler
için geçerli.

Bu yüzden AGPL'in koruması zamanla derinleşir: yeni her özellik yalnız yeni
lisansla var. v0.19.0'ın kopyası, yayınlandığı gündeki uygulamadır ve orada
kalır.

### v0.19.0 ve öncesi için geçerli olan metin (MIT)

Tarihsel kayıt; yukarıdaki sürümlerin kopyalarına uygulanır:

```
MIT License

Copyright (c) 2026 Zenginby

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## AGPL-3.0 pratikte ne demek

### Kullanıcıysan — hiçbir şey değişmedi

İndir, kur, kullan, ürettiğin görselleri istediğin gibi kullan. **Uygulamayla
ÜRETTİĞİN içerik sana ait**; AGPL kodu kapsar, kodun çıktısını değil.
Şirketinde kullanmak da serbest, üretilen görselleri satmak da.

### Kodla bir şey yapacaksan

| Yapmak istediğin | Serbest mi | Şartı |
|---|---|---|
| Kendin için değiştirip kullanmak | ✅ | Yok — dağıtmadığın sürece hiçbir yükümlülük yok |
| Çatallayıp GitHub'da yayımlamak | ✅ | Kaynak AGPL-3.0 kalır, telif bildirimi durur, **ad değişir** ([MARKA.md](MARKA.md)) |
| Paketleyip dağıtmak / satmak | ✅ | Aynı şartlar — AGPL satmayı yasaklamaz, KAPATMAYI yasaklar |
| Bir parçasını kendi projene almak | ✅ | O proje de AGPL-3.0 olmak zorunda |
| Değiştirip sunucuda servis olarak sunmak | ✅ | Kullanıcılarına değiştirilmiş kaynağı SUNMAK zorundasın (§13) |
| Kapalı kaynak bir ürüne koymak | ❌ | İhlal |
| Kaynağı kapatıp kendi ürünün gibi satmak | ❌ | İhlal — bu geçişin tam olarak engellediği şey |
| "Kromis" adıyla ya da logosuyla dağıtmak | ❌ | Lisanstan bağımsız ayrı bir hak ([MARKA.md](MARKA.md)) |

§13 (Remote Network Interaction) burada boş bir madde değil: Kromis kendi HTTP
sunucusunu koşuyor. Değiştirilmiş bir kopyayı ağ üzerinden başkasına açan
herkes, o kullanıcılara değiştirdiği kaynağı sunmak zorunda. Uygulamanın
"Hakkında" panelindeki kaynak kodu bağlantısı bu yükümlülüğün karşılandığı
yerdir — **çatallayan onu kendi deposuna çevirmek ZORUNDA, silmek yetmez.**

### Ticari lisans

AGPL şartları işine uymuyorsa (kapalı kaynak bir üründe kullanmak istiyorsan)
ayrı şartlarla konuşulabilir: telif tek elde olduğu için bu mümkün. GitHub
üzerinden bir issue açman yeterli.

## Üçüncü parti bileşenler

Kromis'in dağıttığı ve kendisine ait OLMAYAN parçalar — hepsinin lisansı
AGPL-3.0 ile uyumlu, paketin içinde kendi bildirimleriyle taşınıyor:

| Bileşen | Nerede | Lisans |
|---|---|---|
| DM Sans yazı tipi | `static/fonts/` | SIL OFL 1.1 (`static/fonts/OFL.txt`) |
| pixel-canvas (Ryan Mulligan) | `static/pixel-canvas.js` | MIT — dosyanın kendi başlığında |
| FastAPI · Uvicorn · httpx · Pillow · pywebview | `requirements.txt` | MIT / BSD / Apache-2.0 |
| Gradle wrapper | `android/gradle/` | Apache-2.0 |
| Sağlayıcı logoları | `static/img/providers/` | İlgili markaların kendi hakları; yalnız tanımlama amaçlı |

Tam liste ve bildirim metni: [NOTICE](NOTICE).

## İhlal görürsen ne yapmalı

İhlal ihtimali olan üç işaret — üçü de tek başına yeterli:

1. Kaynağı kapalı ya da eksik bir kopya dağıtılıyor (AGPL §5–6, §13).
2. Telif bildirimi silinmiş: dosya başlıkları, [NOTICE](NOTICE) ya da
   uygulamanın "Hakkında" panelindeki telif satırı kaldırılmış (AGPL §5a).
3. "Kromis" adı ya da logosu izinsiz kullanılıyor ([MARKA.md](MARKA.md)) —
   bu lisanstan bağımsız, AGPL'e tam uyan bir çatalda bile ihlaldir.

### İzlenecek yol

1. **Kanıtı dondur.** Ekran görüntüsü, paketin SHA-256 özeti, indirme adresi,
   tarih. Karşı taraf sayfayı kaldırırsa elinde kalan tek şey bu olur.
2. **Karşılaştır.** İndirilen paketle bu deponun kaynağı arasındaki örtüşme.
   Uygulama içine gömülü telif satırı ve sürüm numarası burada işe yarar:
   hangi sürümden türediğini söyler.
3. **Önce yaz.** İhlallerin çoğu kötü niyet değil bilgisizlik; "lisans AGPL,
   şu şartları karşılaman gerekiyor" diyen bir e-posta çoğu zaman yeterli.
   14 gün makul bir süre.
4. **Platforma bildir.** Cevap yoksa:
   * GitHub — <https://github.com/contact/dmca> (form: "Copyright claim")
   * Google Play — Play Console yardım merkezindeki telif şikâyeti formu
   * App Store — <https://www.apple.com/legal/internet-services/>
   * Barındırma sağlayıcısı — `abuse@` adresi
5. **Marka ihlali ayrı bir kanal.** Ad/logo şikâyeti telif formundan değil,
   platformun marka (trademark) formundan gider.

Bildirimde istenen şey hep aynı: eserin sahibi olduğunun beyanı, eserin nerede
olduğu (bu depo), ihlalin nerede olduğu, iyi niyet beyanı ve imza. Bu belge,
[NOTICE](NOTICE) ve [LICENSE](LICENSE) birinci maddeyi zaten belgeliyor.

## Katkı verenler

Bir PR gönderdiğinde katkını AGPL-3.0 altında sunmuş olursun ve telif
bildirimini değiştirmezsin. Ticari lisans verilebilmesi telifin tek elde
kalmasına bağlı; bunu gerektiren bir katkıda ayrıca konuşuruz.
