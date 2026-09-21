# Tasarım diyagramları

**Buradaki dosyalar ELLE yazılmıştır.** `docs/graflar/` ile karıştırmayın: orası
kaynaktan üretilir ve bayt bayt bir kapıyla korunur, burası üretilmez. Bu ayrım
bu klasörün var oluş sebebidir, dipnot değil.

## Neden ayrı bir klasör

`docs/graflar/` statik tarama yapıyor ve kendi sınırını dürüstçe yazmış: dinamik
gönderim kenar üretmez, şablondan gelen bağlar görünmez, ve en önemlisi —

> "bir rota ile işçi arasındaki bağ HTTP değil `isler` tablosudur ve harita onu
> kenar olarak göstermez"

`app.py` ile `isci.py` iki ayrı bileşim kökü; aralarında ithal kenarı yok, bu
yüzden tarayıcı ikisini birleştiremez. Burası tam olarak o boşluk için: statik
taramanın YAPISAL olarak göremediği şeyler, ve henüz kodu yazılmamış tasarım
kararları.

Buraya her diyagram konmaz. Kaynaktan çıkarılabilen bir şey `docs/graflar/`in
işidir ve orada kalmalıdır.

## İki tür diyagram, iki ayrı risk

| Tür | Örnek | Bayatlama riski |
| --- | --- | --- |
| **Kod aynası** | iş yaşam döngüsü | Var — kod değişir, diyagram sessizce yalan söyler |
| **Melez** | Polar webhook akışı | Kısmi — şeması inmiş (`0008_odeme`), işleyicileri inmemiş |

Saf "kod öncesi" diyagram pratikte az çıkıyor: bir akışı çizmeye değer hâle
geldiğinde şemasının bir kısmı genellikle çoktan inmiş oluyor. Webhook akışı
`defter.paket_yukle` gibi VAR OLAN adlara da, `odeme.isle` gibi HENÜZ YAZILMAMIŞ
adlara da atıf yapıyor.

`tests/test_tasarim_diyagramlari.py` ikisini de doğru ele alıyor: var olan ad
denetleniyor, yazılmamış modüle atıf sessizce atlanıyor ve **o dosya indiği gün
diyagram kendiliğinden korunmaya başlıyor**. Yani bir tasarım diyagramı,
tasarladığı kod yazıldığı anda kod aynasına dönüşüyor ve kapı bunu kendisi
devralıyor.

Kapının dört ölçümü ve YAKALAMADIĞI şey o testin başında yazılı; diyagram
eklemeden önce okuyun. Yeni bir diyagram ya taranan listede ya da muafiyet
defterinde gerekçesiyle yer almak zorunda (CLAUDE.md §5) — dördüncü test bunu
zorluyor, sessizce muaf kalınamıyor.

## Dosya düzeni

Commit'lenen şey **JSON**'dur, HTML değil:

| | Boyut | Üretim maliyeti |
| --- | --- | --- |
| `<ad>.<tür>.json` (kaynak) | 3–5 KB | Pahalı — kaynağı okumak, doğrulama turları |
| `<ad>.html` (çıktı) | ~800 KB | Bedava — tek komut, saniyeler |

`archify visual-check` aynı klasöre ekran görüntüleri ve bir makbuz
(`<ad>.visual-check.json`) bırakır; onlar da çıktıdır ve `.gitignore`dadır.

800 KB'lık bir çıktıyı 13 MB'lık bir depoya her sürümde yazmanın anlamı yok;
üstelik diff'i okunamaz. HTML `.gitignore`da.

## HTML'i yeniden üretmek

[Archify](https://github.com/tt-a1i/archify) skill'i kurulu olmalı
(`~/.claude/skills/archify`, MIT). Node 18+ ister:

```sh
node ~/.claude/skills/archify/bin/archify.mjs deliver lifecycle \
  docs/tasarim-diyagramlari/kromis-is-yasam-dongusu.lifecycle.json \
  docs/tasarim-diyagramlari/kromis-is-yasam-dongusu.html --quality showcase --json
```

Çıktıyı bu klasörün İÇİNE yazın: `.gitignore` kuralı (`docs/tasarim-diyagramlari/*.html`)
yalnız burayı kapsıyor, başka bir yere yazılan HTML yanlışlıkla commit'lenebilir.

Çıktı tek dosyalık, kendi kendine yeten interaktif bir HTML: tema değiştirme,
arama, odak, ilişki izleme ve dışa aktarma gömülü. Tarayıcıda açmanız yeterli.

Diyagramın kendi arayüzü (`Legend`, `Light/Dark`, `PATH MAP LENS`) İNGİLİZCEDİR
ve öyle kalacaktır: renderer yalnız `en` ile `zh-CN` biliyor. Sizin yazdığınız
içeriğin tamamı Türkçe.

## Mevcut diyagramlar

| Dosya | Anlattığı | Tür |
| --- | --- | --- |
| [`kromis-is-yasam-dongusu.lifecycle.json`](kromis-is-yasam-dongusu.lifecycle.json) | `isler.durum` geçişleri ve her geçişin tetiklediği defter hareketi | Kod aynası |
| [`kromis-polar-webhook.sequence.json`](kromis-polar-webhook.sequence.json) | Polar olayının imzadan deftere yolu; hangi dalın hangi HTTP kodunu döndürdüğü ve yeniden deneme döngüsü | Melez (Faz 4 / 3) |

HTML'i üretirken tür adını komuta da yazın: `deliver sequence …`, `deliver
lifecycle …`.
