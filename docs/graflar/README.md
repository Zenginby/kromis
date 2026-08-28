<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py · yenilemek için: python3 tools/graf_uret.py -->

# Depo haritası (graflar)

**Bu depoda çalışmaya başlarken ilk okunacak yer burasıdır.** Grafların tamamı kaynaktan üretiliyor; elle yazılmış bir mimari anlatısı değil, kodun o anki hâli.

| graf | ne söyler |
| --- | --- |
| [moduller.md](moduller.md) | Python modülleri, katmanlar, ithal kenarları, döngüler, öksüzler |
| [uc-noktalar.md](uc-noktalar.md) | HTTP rotaları → dokundukları modüller → onları çağıran tarayıcı betiği |
| [onyuz.md](onyuz.md) | `static/` betiklerinin yükleme sırası, birbirine bağlılığı, çağırdığı sunucu yolları |
| [testler.md](testler.md) | Modül → o modüle dokunan test dosyaları |
| [graf.json](graf.json) | Aynı verinin makine okuyabilir hâli |

## Ölçüler

* 39 Python modülü, 83 modül düzeyi ithal kenarı (9 erteli)
* 41 HTTP uç noktası
* 9 tarayıcı betiği, 21 betik-arası bağ
* 70 test dosyası; 3 modülü hiçbir test ithal etmiyor, 6 test de hiçbir modülü (artefakt sınıyorlar; bkz. testler.md)
* 1 ithal döngüsü, 0 rotaya oturmayan tarayıcı çağrısı

En büyük dosyalar: `app` (1719), `models` (780), `catalog` (769), `azure_client` (458), `color_names` (418).
En çok ithal edilenler: `catalog` (10), `azure_client` (9), `jsonstore` (8), `credstore` (6), `paths` (6).

## Nasıl güncellenir

```sh
python3 tools/graf_uret.py            # yeniden üretir
python3 tools/graf_uret.py --kontrol  # bayat mı? (CI kapısı bunu koşar)
python3 tools/graf_uret.py --ozet     # tek ekranlık özet
```

Üç ayrı mekanizma haritanın bayatlamasını engelliyor — biri unutulsa öteki yakalar:

1. `tests/test_graflar.py` — dosyalar kaynakla aynı değilse takım KIRMIZI. Kapı bu; her PR'da koşuyor.
2. `.claude/settings.json` — Claude Code oturumunda bir `.py`/`static/` dosyası düzenlendiğinde graflar kendiliğinden yenilenir, oturum başında da bu özet gösterilir.
3. `CLAUDE.md` — çalışmaya başlamadan önce buranın okunmasını söyler.

## Statik taramanın görmediği şeyler

Harita çalışma anını değil KAYNAĞI okuyor. Bu bilinçli (bkz. tools/graf_uret.py'nin gerekçesi), ama sınırı var:

* Dinamik gönderim (`getattr`, sözlükten çağrılan işlev) kenar üretmez.
* Şablondan/yapılandırmadan gelen bağlar (ör. `.spec` dosyasının gizli ithalleri) burada yok.
* Ön yüz kenarları AD eşleşmesine dayanıyor; küresel bir işlevle aynı adı taşıyan yerel bir değişken kenarı fazla sayabilir.
* Test sütunu ithal ilişkisidir, satır kapsamı DEĞİLDİR.

