# Telif, lisans ve ihlal bildirimi

Bu belge üç soruyu cevaplıyor: **kim sahibi**, **ne yapabilirsin**, ve
**birileri kuralı çiğnerse ne olur**. Lisansın kendisi [LICENSE](LICENSE)'dadır;
burası onun okunabilir kaydı ve çevresi. Çelişki hâlinde bağlayıcı olan
LICENSE'ın İngilizce metnidir.

Ad ve logo lisansın KAPSAMI DIŞINDA — ayrı belge: [MARKA.md](MARKA.md).

**Bugünkü lisans: FSL-1.1-ALv2** (Functional Source License 1.1, Apache-2.0
Future License). Depo iki geçiş yaşadı ve ikisi de burada kayıtlı:

| Sürümler | Lisans | Kayıt |
|---|---|---|
| v0.19.0 ve öncesi | MIT | aşağıda, "MIT'ten AGPL-3.0'a" |
| v0.20.0 – v0.23.1 | GNU AGPL-3.0 | aşağıda, "AGPL-3.0'dan FSL-1.1-ALv2'ye" |
| 2026-09-24'ten sonraki sürümler | FSL-1.1-ALv2 | [LICENSE](LICENSE) |

Verilmiş bir lisans geri alınmaz: her satır, o sürümün kopyaları için kalıcı.

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

## Lisans geçişi — MIT'ten AGPL-3.0'a (2026-09-12)

**v0.19.0 ve öncesi MIT'ti. Bu değişikliği taşıyan commit'ten (`d0f6ee2`)
sonraki sürümler — v0.20.0'dan v0.23.1'e — GNU AGPL-3.0.** (AGPL dönemi
2026-09-24'te kapandı; bir sonraki bölüm.)

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

Bu yüzden lisans koruması zamanla derinleşir: yeni her özellik yalnız yeni
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

### MIT dönemi paketlerinin parmak izleri

v0.17.3, v0.18.0 ve v0.19.0'ın hazır paketleri (apk/zip) **2026-09-13'te
yayın sayfalarından kaldırıldı.** Gerekçe lisans değil dağıtım hijyeni: o üç
sürümün `SHA256SUMS.txt`'si YOK — paket doğrulama v0.20.0'da başladı — yani
oradan indirilen bir dosyanın gerçekten bu hattan çıktığı kanıtlanamıyordu.
Kanaldaki doğrulanamayan tek nokta orasıydı. Silmek MIT'i geri almaz ve öyle
bir amacı da yok; kaynağın kendisi `main`'in geçmişinde, herkese açık duruyor.

Yayın kayıtları, tarihleri ve notları YERİNDE: hangi sürümün hangi lisansla
çıktığının cevabı, sonradan düzenlenebilecek bir belgede değil GitHub'ın
tarihli kaydında kalsın diye. Silinen yalnız dosyalar.

Özetler burada, çünkü **dosyayı silmek parmak izini de silerdi.** Yarın
ortaya MIT dönemine ait bir ikili çıkarsa, onun bu depodan çıktığını — ya da
ÇIKMADIĞINI — gösterebilecek tek şey bu liste. Değerler GitHub'ın kendi
bağımsız hesabı; silme işleminden ÖNCE yayın API'sinden okundu. Biçim
`sha256sum` ile uyumlu, doğrudan `sha256sum -c` verilebilir.

**v0.17.3** — 2026-09-11 12:55:42 UTC · indirme sayacı: 2 / 3 / 3

```
911de3ed46572901f761c993c5e781b2f1a8bf733e6524efb8d0356aa4ccc60a  kromis-android-arm64.apk
b9fd91b716b4692a2459a4b167d0bee5a3903f0dcad508c975a0a70c62c8f427  kromis-macOS-arm64.zip
2d6b047a8b7d36630f91e7cf703dd885db3da8106ae61aad0778386d34efae5d  kromis-windows-x64.zip
```

**v0.18.0** — 2026-09-11 16:46:19 UTC · indirme sayacı: 3 / 1 / 1

```
988d9d6a6612ccdd4456cb8754d06e78ac2eca7d5d2e29b5f283f1bdc5bef349  kromis-android-arm64.apk
ed48bc79fdcc3ef765370d7f74b8fb22aefaa22ff6d7f279f3fc52dc5c29d9a7  kromis-macOS-arm64.zip
586f044f620fd93d2fec80a8c2016f497d2b0fcb3b13a966cad6292153c7905e  kromis-windows-x64.zip
```

**v0.19.0** — 2026-09-11 19:03:34 UTC · indirme sayacı: 1 / 1 / 1

```
eea42bdbc8c4f44fec029c13f31275d2633b56e0234c92ca8b4a1261012e2443  kromis-android-arm64.apk
2f0dae6ac1fcfa1b1202d2ce8d3d437e6f86bf09b6458e4b4b37efb5035dbb02  kromis-macOS-arm64.zip
669043ebbfefcfc63d2a5100903be09c7e2452bc908c2f0fd23fb6f7de6ae2a6  kromis-windows-x64.zip
```

İndirme sayacı toplamı 16. Sayaç KİMİN indirdiğini söylemez; üç sürüm ve üç
platform üzerinden birkaç kişilik bir dağılımla tutarlı, ama "kimse almadı"
diye okunamaz. Bu belge o yüzden ihtimale değil kayda dayanıyor.

## Lisans geçişi — AGPL-3.0'dan FSL-1.1-ALv2'ye (2026-09-24)

**v0.20.0'dan v0.23.1'e kadar çıkan sürümler GNU AGPL-3.0. Bu değişikliği
taşıyan commit'ten sonra çıkan her sürüm FSL-1.1-ALv2.** Karar telif sahibinin;
tek geliştirici ve tek telif sahibi olduğu için (yukarıda) üçüncü bir kişinin
onayı gerekmedi.

### Neden

AGPL'in kapatmadığı bir boşluk vardı. AGPL şunu ister: değiştirip dağıtan ya
da ağ üzerinden sunan, kaynağını da açar. Şunu İSTEMEZ: rekabet etmemek.
Yani herhangi biri Kromis'i olduğu gibi alıp, kaynağını açık tutarak, kendi
adıyla **ücretli bir barındırılan hizmet** olarak sunabilirdi — ve buna
"AGPL'e tam uyum" denirdi. Kromis'in kendisi bir barındırılan hizmet olduğu
için (Faz 0'dan beri web-first) bu boşluk kuramsal değil, iş modelinin tam
ortasındaydı. Telif sahibinin amacı da açıkça bu: *"insanların kendi adıyla
ücretli olarak yayınlamasını istemiyorum."*

FSL bu boşluğu adıyla kapatıyor. Lisansın verdiği izin **"Permitted Purpose"**
ile sınırlı ve Permitted Purpose, **Competing Use** dışındaki her amaç. Yani:

* **Serbest:** kullanmak, okumak, değiştirmek, kendin için barındırmak, kurum
  içinde kullanmak, ticari olmayan eğitim ve araştırma, Kromis kullanan bir
  müşteriye profesyonel hizmet vermek — ve **rekabet etmeyen her ticari
  kullanım**.
* **Yasak:** Kromis'i ya da değiştirilmiş bir kopyasını, Kromis'le rekabet
  eden bir ticari ürün ya da hizmet içinde başkalarına sunmak.
* **Süreli:** her sürüm, yayımlanmasından **iki yıl sonra Apache-2.0** olur
  ("Grant of Future License"). Bu taahhüt lisansın içinde ve geri alınamaz;
  yani kısıt kalıcı değil, iki yıllık bir öncelik.

### "Rakip kullanım" ne demek — lisansın tanımı, Türkçesiyle

LICENSE'ın "Permitted Purpose" maddesi (bağlayıcı olan İngilizce metin):

> A Permitted Purpose is any purpose other than a Competing Use. A Competing
> Use means making the Software available to others in a commercial product or
> service that: 1. substitutes for the Software; 2. substitutes for any other
> product or service we offer using the Software that exists as of the date we
> make the Software available; or 3. offers the same or substantially similar
> functionality as the Software.

Türkçesi: **Rakip Kullanım**, Yazılımı başkalarına, (1) Yazılımın yerine geçen,
(2) Yazılımı kullanarak sunduğumuz ve Yazılımı erişilebilir kıldığımız tarihte
var olan başka bir ürün ya da hizmetin yerine geçen, ya da (3) Yazılımla aynı
ya da esasen benzer işlevselliği sunan **ticari** bir ürün ya da hizmet içinde
sunmaktır. İzinli amaçlar arasında lisansın kendisi şunları ayrıca sayıyor:
kurum içi kullanım ve erişim, ticari olmayan eğitim, ticari olmayan araştırma,
ve Kromis'i lisansa uygun kullanan birine verilen profesyonel hizmetler.

Somut çeviri: Kromis'i kendi sunucuna kurup ekibinle kullanmak serbest.
Müşterine Kromis'i kurup bakımını yapmak serbest. Kromis'in görsel üretim
motorunu kendi, farklı bir ürününün içinde bir parça olarak kullanmak —
ürünün Kromis'in yerine geçmiyorsa — serbest. "Kromis'in aynısı, ayda 10
dolar" diye bir site açmak **yasak**; adını değiştirsen de yasak (ad ayrıca
[MARKA.md](MARKA.md) ile korunuyor ama yasağın kaynağı bu kez lisansın
kendisi). İki yıl sonra o sürüm için yasak kendiliğinden kalkar.

### Geriye yürümüyor

AGPL da geri alınamaz. **v0.20.0–v0.23.1'i AGPL-3.0 altında almış biri, O
SÜRÜMLER için AGPL haklarını kalıcı olarak korur** — onlarla rakip bir hizmet
kurabilir, yeter ki kaynağını açsın. Bu belge onu değiştirmez. v0.23.1'den
sonra `main`'e giren ama etiketlenmemiş commit'ler de bu commit'e kadar
AGPL-3.0 ile yayımlandı; kural aynı. FSL yalnız bu commit'ten sonraki kaynak
ve sürümler için geçerli. AGPL-3.0'ın metni kamuya açık ve değişmez
(<https://www.gnu.org/licenses/agpl-3.0.txt>); burada yeniden basılmıyor,
çünkü MIT'in aksine kaybolma riski yok.

### Vazgeçilen şey — dürüst kayıt

FSL'in AGPL'de olmayan bir kısıtı var (rekabet); AGPL'in FSL'de olmayan bir
şartı var: **kaynağı açma zorunluluğu**. FSL altında birisi Kromis'i alıp
kurum içinde değiştirebilir ve değişikliklerini asla açmaz; bu FSL'e uygundur.
Telif sahibi bu takası bilerek yaptı: korunmak istenen şey "değişiklikler
geri gelsin" değil, "rakip hizmet çıkmasın"dı. Bu paragraf ileride "AGPL daha
iyi korurdu" tartışması çıkarsa kararın gerekçesi hazır olsun diye burada.

### Açık kaynak mı?

Hayır — OSI'nin "Open Source Definition"ı alan ayrımı yapan lisansları
dışlar ve FSL bunu yapar. Doğru ad "kaynağı açık" ya da FSL'in kendi
deyimiyle **Fair Source**. README ve belgeler bu yüzden "özgür yazılım" ya da
"açık kaynak lisansı" demiyor; GitHub'ın lisans etiketi de "Other" gösterir.
İki yıl geçince o sürüm Apache-2.0 olur ve o noktadan sonra açık kaynaktır.

### Ad ve logo — değişmedi

Lisans değişti, marka politikası değişmedi: "Kromis" adı ve logosu lisansın
kapsamı dışında, çatal ad değiştirir ([MARKA.md](MARKA.md)). FSL'in kendi
"Trademarks" maddesi de aynı şeyi söylüyor: kaynağı göstermek dışında ad ve
marka üzerinde hiçbir hak verilmiyor.

## FSL-1.1-ALv2 pratikte ne demek

### Kullanıcıysan — hiçbir şey değişmedi

İndir, kur, kullan, ürettiğin görselleri istediğin gibi kullan. **Uygulamayla
ÜRETTİĞİN içerik sana ait**; lisans kodu kapsar, kodun çıktısını değil.
Şirketinde kullanmak da serbest, üretilen görselleri satmak da. Kullanım
Şartları ve Ticari Haklar sayfaları (`bundled/hukuk/`) bunu ayrıca söylüyor
ve kod lisansından bağımsız.

### Kodla bir şey yapacaksan

| Yapmak istediğin | Serbest mi | Şartı |
|---|---|---|
| Kendin için değiştirip kullanmak | ✅ | Yok — kurum içi kullanım izinli amaçların ilki |
| Kendi sunucunda barındırmak (kendin / ekibin için) | ✅ | Yok |
| Çatallayıp GitHub'da yayımlamak | ✅ | LICENSE ve telif bildirimleri durur, **ad değişir** ([MARKA.md](MARKA.md)) |
| Paketleyip dağıtmak | ✅ | Aynı şartlar; kaynağı açmak zorunda DEĞİLSİN |
| Bir parçasını kendi, farklı ürününe almak | ✅ | Ürün Kromis'in yerine geçmiyorsa; LICENSE taşınır |
| Müşterine kurmak, bakımını yapmak, eğitim vermek | ✅ | "Professional services" izinli amaç |
| Kromis'i ya da çatalını **rakip bir ürün / barındırılan hizmet** olarak sunmak | ❌ | Competing Use — iki yıl geçince o sürüm için kalkar |
| Telif bildirimini ya da LICENSE'ı kaldırmak | ❌ | İhlal ("Redistribution" maddesi) |
| "Kromis" adıyla ya da logosuyla dağıtmak | ❌ | Lisanstan bağımsız ayrı bir hak ([MARKA.md](MARKA.md)); lisansın "Trademarks" maddesi de yasaklar |
| İki yaşını doldurmuş bir sürümü Apache-2.0 ile kullanmak | ✅ | Apache-2.0'ın şartları (bildirim, NOTICE) |

"Redistribution" maddesi burada boş bir madde değil: Kromis'i alan herkes,
dağıttığı her kopya ve türevle birlikte LICENSE'ı (ya da bağlantısını)
taşımak ve telif bildirimlerine dokunmamak zorunda. Uygulamanın "Hakkında"
panelindeki LICENSE ve kaynak bağlantıları bu yükümlülüğün kullanıcıya
görünen yüzüdür — **çatallayan kaynak bağlantısını kendi deposuna çevirir,
LICENSE bağlantısını ve telif satırını yerinde bırakır.**

### Ticari lisans

Yapmak istediğin şey "Competing Use" tanımına giriyorsa ayrı şartlarla
konuşulabilir: telif tek elde olduğu için bu mümkün. GitHub üzerinden bir
issue açman yeterli. İki yıl bekleyip Apache-2.0 ile kullanmak da her zaman
açık bir yol.

## Üçüncü parti bileşenler

Kromis'in dağıttığı ve kendisine ait OLMAYAN parçalar — hepsi izin verici
(MIT / BSD / Apache-2.0 / OFL) lisanslı, FSL ile birlikte taşınmalarına engel
yok; psycopg LGPL-3.0'dır ve dinamik bağlanan kütüphane olarak kullanılır, bu
kullanım Kromis'in lisansını etkilemez. Hepsi paketin içinde kendi
bildirimleriyle taşınıyor:

| Bileşen | Nerede | Lisans |
|---|---|---|
| DM Sans yazı tipi | `static/fonts/` | SIL OFL 1.1 (`static/fonts/OFL.txt`) |
| pixel-canvas (Ryan Mulligan) | `static/pixel-canvas.js` | MIT — dosyanın kendi başlığında |
| FastAPI · Uvicorn · httpx · Pillow · pywebview · SQLAlchemy · Alembic · ötekiler | `requirements.txt` | MIT / BSD / Apache-2.0 |
| psycopg | `requirements.txt` | LGPL-3.0 — dinamik bağlanır |
| Gradle wrapper | `android/gradle/` | Apache-2.0 |
| Sağlayıcı logoları | `static/img/providers/` | İlgili markaların kendi hakları; yalnız tanımlama amaçlı |

Tam liste ve bildirim metni: [NOTICE](NOTICE).

## İhlal görürsen ne yapmalı

İhlal ihtimali olan üç işaret — üçü de tek başına yeterli:

1. Kromis ya da bir çatalı, iki yaşını doldurmamış bir sürümden, rakip bir
   ürün ya da barındırılan hizmet olarak sunuluyor ("Competing Use").
2. Telif bildirimi ya da lisans silinmiş: dosya başlıkları, [NOTICE](NOTICE),
   [LICENSE](LICENSE) ya da uygulamanın "Hakkında" panelindeki telif satırı
   kaldırılmış ("Redistribution" maddesi).
3. "Kromis" adı ya da logosu izinsiz kullanılıyor ([MARKA.md](MARKA.md) ve
   lisansın "Trademarks" maddesi) — lisansa tam uyan bir çatalda bile
   ihlaldir.

AGPL dönemi sürümleri (v0.20.0–v0.23.1) için 1. madde geçerli değil; orada
işaret "kaynağı kapalı kopya"dır (AGPL §5–6, §13).

### İzlenecek yol

1. **Kanıtı dondur.** Ekran görüntüsü, paketin SHA-256 özeti, indirme adresi,
   tarih. Karşı taraf sayfayı kaldırırsa elinde kalan tek şey bu olur.
2. **Karşılaştır.** İndirilen paketle bu deponun kaynağı arasındaki örtüşme.
   Uygulama içine gömülü telif satırı ve sürüm numarası burada işe yarar:
   hangi sürümden türediğini söyler.
3. **Önce yaz.** İhlallerin çoğu kötü niyet değil bilgisizlik; "lisans
   FSL-1.1-ALv2, rakip kullanım yasak / bildirimi geri koy" diyen bir e-posta
   çoğu zaman yeterli. 14 gün makul bir süre.
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

Bir PR gönderdiğinde katkını FSL-1.1-ALv2 altında (ve onun Apache-2.0
gelecek lisansıyla) sunmuş olursun ve telif bildirimini değiştirmezsin. Ticari
lisans verilebilmesi ve lisansın yeniden değiştirilebilmesi telifin tek elde
kalmasına bağlı; bunu gerektiren bir katkıda ayrıca konuşuruz.
