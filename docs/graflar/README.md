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

* 94 Python modülü, 385 modül düzeyi ithal kenarı (15 erteli)
* 57 HTTP uç noktası
* 11 tarayıcı betiği, 29 betik-arası bağ
* 125 test dosyası; 15 modülü hiçbir test ithal etmiyor, 14 test de hiçbir modülü (artefakt sınıyorlar; bkz. testler.md)
* 1 ithal döngüsü, 0 rotaya oturmayan tarayıcı çağrısı

En büyük dosyalar: `catalog` (1461), `models` (1127), `fal_client` (757), `veo_client` (629), `desktop` (588).
En çok ithal edilenler: `i18n` (37), `services.tablolar` (25), `catalog` (24), `services.db` (19), `services.zaman` (16).

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
* `Depends(ayar.ayarlar)` ile gelen ayar nesnesi: rotanın `ayarlar.output_dir` okuması bir öznitelik erişimi, çağrı değil — uç nokta sütunu `paths`e varmaz. Dizinlerin kaynağı `app.py`deki `Ayarlar.varsayilan()`; `paths.py`ye dokunmak yine her ucu etkiler, harita bunu `app` → `services.ayar` → `paths` ithal kenarıyla gösterir, rota satırında değil.
* Şablondan/yapılandırmadan gelen bağlar (ör. `.spec` dosyasının gizli ithalleri) burada yok.
* Ön yüz kenarları AD eşleşmesine dayanıyor; küresel bir işlevle aynı adı taşıyan yerel bir değişken kenarı fazla sayabilir.
* Test sütunu ithal ilişkisidir, satır kapsamı DEĞİLDİR.
* İKİ BİLEŞİM KÖKÜ (Faz 2 / 3): `app.py` web sürecinin, `isci.py` işçi sürecinin girişi (`python isci.py`; compose `isci` servisi). Uç nokta tablosu yalnız `app`ı tarar — işçi rota tanımlamaz, kuyruktan okur (`services/isci.py` → `services/kuyruk.py`); bir rota ile işçi arasındaki bağ HTTP değil `isler` tablosudur ve harita onu kenar olarak göstermez.
* ARA KATMANLAR rota değil: `services/koken.py` (köken kapısı) ve `services/dil.py` (dil bağlamı) her isteğin önünde koşuyor ama uç nokta tablosunda satırları yok; sıraları (`köken → dil → rota`) `app.py`de yazılı, harita yalnız `app` → `services.koken` ithal kenarını gösterir.
* `alembic/` (göç betikleri) BİLEREK dışarıda (`tools/graf_uret.py` `DISLANAN_DIZINLER`): `env.py` yalnız `services.db`/`services.tablolar`ı ithal eder, `versions/*.py` ise şema tarihçesidir — her göç bir modül olarak sayılsa harita göç sayısı kadar şişer ve hiçbir kenar anlam taşımaz. Göç hattının bekçisi `tests/test_db.py` (upgrade/downgrade/check), dağıtım öncesi koşucusu `tools/goc.py` (o haritada, `tools.` altında).

