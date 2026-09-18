# Marka, ticaret unvanı ve alan adı

**Tarih:** 2026-09-18 · **Karar:** şahıs şirketi · marka `Kromis`, çatı `Zenginby`,
resmî unvan `Alperen Zengin` · **İlgili:** [MARKA.md](../MARKA.md) (adın ve logonun
lisans dışı olduğu politika), [TELIF.md](../TELIF.md) (telif sahibi),
[superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md)
("Ödeme Altyapısı" maddesi — MoR kararı bu belgenin ticari öncülü)

Bu belge "şirket adı ne olsun" sorusunun cevabı. Kısa cevap: soruyu "ya soyad ya
ürün adı" diye kurmak yanlış — birbirine karışan **üç ayrı katman** var ve ikisi
zaten karara bağlanmış durumda.

## Üç katman

| Katman | Nerede görünür | Değer |
|---|---|---|
| **Ticaret unvanı** (hukuki) | vergi levhası, e-arşiv fatura, Polar'a kesilen hizmet ihracı faturası, sözleşmeler | `Alperen Zengin` |
| **Marka** (müşteriye görünen) | ürün adı, alan adı, uygulama mağazası, logo | `Kromis` / `Kromis Studio` |
| **Çatı / telif kimliği** | copyright satırı, GitHub org, uygulama kimliği | `Zenginby` |

Soyad çatıda, ürün adı vitrinde. Gerilim burada çözülüyor; ikisinden birini
seçmek gerekmiyor.

### Ticaret unvanı neden tartışmaya kapalı

Şahıs şirketinde seçim hakkı yok: **TTK 41**, gerçek kişi tacirin ticaret
unvanının *kısaltılmadan yazılan ad ve soyadından* oluşmasını istiyor. Üzerine
**TTK 46**'ya uygun ek yapılabilir — `Alperen Zengin — Kromis Yazılım` gibi.
Ekin sınırı: ortaklık izlenimi yaratan çoğul ekler ("… ve Ortakları") ve başka
kişilerin adları kullanılamaz, ek işletmenin genişliği konusunda yanıltıcı
olamaz.

Bunun ticari ağırlığı düşük, çünkü **MoR modelinde bu adı müşteri görmüyor**:
satıcı hukuken Polar, müşterinin faturasında Polar yazıyor. Unvan yalnız
Polar'a kesilen faturada ve vergi levhasında görünüyor.

### Çatı adı: yeni bir şey icat etme

`Zenginby` zaten kullanımda — `com.zenginby.kromis` (Android `applicationId`,
macOS `bundle_identifier`), GitHub org, `Copyright (C) 2026 Alperen Zengin
(@Zenginby)`. İleride başka ürünler çıkarsa çatı bu, Kromis onun altında bir
marka. Kimlikleri çoğaltmak yalnız karışıklık üretir.

## Alan adı durumu (2026-09-18 itibarıyla ölçüldü)

| Alan adı | Durum |
|---|---|
| `kromis.com` | **ALINMIŞ.** 2011'de tescil, 2028'e kadar ödenmiş, registrar *Alpine Domains Inc.*, ad sunucuları `power-dns.com`, TLS sertifikası süresi dolmuş. Aktif bir iş değil, **park/satılık profili**. |
| `kromis.com.tr` | **ALINMIŞ.** Üstünde *"Krom İş — Soğutma Paslanmaz"* adlı bir WordPress sitesi çalışıyor; paslanmaz/soğutma sektörü. |
| `kromis.net` · `.app` · `.studio` · `.io` · `.co` · `.dev` · `.ai` · `.org` | **BOŞ.** |

**Karar:** `.com` peşine düşülmez. Sahibi park eden bir aracı olduğu için satın
alma pazarlığı hem pahalı hem belirsiz; web-first ürün için `.app` ya da
`.studio` en az onun kadar iyi okunuyor. Öneri sırası: **`kromis.app`** (ürün
web uygulaması), yedek **`kromis.studio`** (ad zaten "Kromis Studio").
`.ai` pahalı ve konumlandırmayı daraltır. Hangisi seçilirse seçilsin **ikisi de
aynı anda alınır** — fiyatı düşük, sonradan kapılmasının maliyeti yüksek.

## Marka tescili

**Ölçülemedi.** TÜRKPATENT'in anonim marka araştırması yalnız etkileşimli
portaldan çalışıyor, TMview API'si dışarıdan kapalı. Yani "Kromis" 9. ve 42.
sınıflarda boş mu, **teyit edilmedi** — başvurudan önce bir marka vekiline
resmî araştırma yaptırılmalı. Bu zaten standart pratik: benzerlik
değerlendirmesi otomatik aramayla değil, vekil yorumuyla yapılır.

Bulunabilen dolaylı işaret: Türkiye'de `Krom-` öneki **metal/endüstri**
tarafında yoğun — Kromaş, Kromel, Kromser, Kromlüks, Krom İş. Hepsi 6/7/11.
sınıf dünyası (metal, makine, soğutma). Yazılım sınıflarında (9 ve 42) şerit
büyük ihtimalle açık; asıl risk hukuki değil **algısal**: Türk kulağı "Kromis"i
"krom iş" diye bölüp endüstriyel çağrışım kurabiliyor — `kromis.com.tr`
altındaki paslanmaz firması bunun canlı kanıtı. Küresel kitle hedeflendiği için
bu kabul edilebilir bir maliyet, ama Türkiye pazarına dönük iletişimde ad
"Kromis Studio" bütünüyle kullanılmalı; tek başına "Kromis" bırakılmamalı.

**Başvuru:** 9. sınıf (bilgisayar yazılımı) + 42. sınıf (yazılım hizmetleri,
SaaS). Şahıs şirketinde başvuru gerçek kişi adına yapılır; limitede geçilirse
marka şirkete devredilir. Tescil, [MARKA.md](../MARKA.md)'deki hak iddiasını
uygulanabilir kılan şey: tescilsiz kullanımda da koruma var (haksız rekabet,
SMK önceliği) ama uygulama mağazası şikâyeti ve alan adı itirazı pratikte
tescille yürüyor.

## Sıradaki adımlar

1. `kromis.app` + `kromis.studio` alınır. **Şirket kurulumundan önce** — ucuz
   sigorta, sıra beklemez.
2. Vergi dairesinde şahıs açılışı, e-arşiv fatura. Unvana `Kromis Yazılım` eki
   eklenir.
3. Marka vekiline 9. ve 42. sınıf araştırması yaptırılır, sonuç temizse başvuru.
4. Polar hesabı sole proprietor/individual olarak açılır (TCKN + vergi levhası
   ile Stripe Connect Express doğrulaması).
5. Limitede geçiş: ortak/yatırım, sorumluluk sınırı ya da muhasebe avantajı
   döndüğünde. Şimdi değil — hizmet ihracatı %100 kazanç indirimi şahısta da
   geçerli (GVK 89/13) ve limitedi vuran asgari kurumlar vergisi şahısta yok.

## Ölçülmemiş olanlar

* "Kromis" 9/42. sınıflarda tescilli mi — vekil araştırması bekliyor.
* `kromis.com` sahibinin satış fiyatı — sorulmadı, peşine düşülmemesi
  önerildiği için.
* Sosyal medya kullanıcı adlarının (X, Instagram, YouTube) müsaitliği.
