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
| **Kod öncesi tasarım** | ödeme/MoR akışı | Yok — kayacağı bir kaynak henüz yok |

Kod aynası olan her diyagram `tests/test_tasarim_diyagramlari.py` ile korunur.
Kapının ne yakalayıp ne yakalamadığı o testin başında yazılı; eklemeden önce
okuyun.

## Dosya düzeni

Commit'lenen şey **JSON**'dur, HTML değil:

| | Boyut | Üretim maliyeti |
| --- | --- | --- |
| `*.lifecycle.json` (kaynak) | ~3 KB | Pahalı — kaynağı okumak, doğrulama turları |
| `*.html` (çıktı) | ~800 KB | Bedava — tek komut, saniyeler |

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
