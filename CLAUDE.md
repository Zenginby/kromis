# Bu depoda çalışma düzeni

## 1. Önce depo haritasını oku — her seferinde

Kod okumaya başlamadan önce **[docs/graflar/README.md](docs/graflar/README.md)**
ve dokunacağın alanın grafı:

| dokunduğun şey | ilk bakılacak graf |
| --- | --- |
| bir Python modülü | [docs/graflar/moduller.md](docs/graflar/moduller.md) — `ithal eden` sütunu değişikliğin etki alanıdır |
| bir HTTP ucu / `app.py` | [docs/graflar/uc-noktalar.md](docs/graflar/uc-noktalar.md) — rota → modül → onu çağıran betik |
| `static/` altındaki bir betik | [docs/graflar/onyuz.md](docs/graflar/onyuz.md) — yükleme sırası, betikler arası çağrı, çağrılan uçlar |
| ne sınanacak sorusu | [docs/graflar/testler.md](docs/graflar/testler.md) — modül → o modüle dokunan test dosyaları |
| makineyle sorgu (grep/jq) | [docs/graflar/graf.json](docs/graflar/graf.json) |

Graflar `tools/graf_uret.py` tarafından KAYNAKTAN üretiliyor; elle yazılmış bir
mimari anlatısı değil, kodun o anki hâli. Bu yüzden onlara güvenilebilir — ve
bu yüzden bayat bırakılmamaları gerekir.

Haritanın görmediği şeyler (dinamik gönderim, `.spec` gizli ithalleri, ön
yüzdeki ad çakışmaları) `docs/graflar/README.md`'nin son bölümünde yazılı.
Harita bir başlangıç noktasıdır, kanıt değil: bir kenar şüpheliyse kaynağa bak.

## 2. Her değişiklikten sonra haritayı yenile

```sh
python3 tools/graf_uret.py            # yeniden üretir (Windows: python ...)
python3 tools/graf_uret.py --kontrol  # bayat mı? CI kapısı bunu koşar
python3 tools/graf_uret.py --ozet     # tek ekranlık özet
```

Değişen graf dosyaları, onları değiştiren commit'in İÇİNE girer — ayrı bir
"graf güncelleme" commit'i bırakılmaz; harita ile kod aynı commit'te aynı
gerçeği anlatmalı.

Üç mekanizma bunu unutmaya karşı koruyor, biri kaçarsa öteki yakalar:

1. **`tests/test_graflar.py`** — commit'lenmiş graflar kaynakla aynı değilse
   pytest KIRMIZI. Asıl kapı bu; her PR'da koşuyor.
2. **`.claude/settings.json`** — Claude Code oturumunda bir `.py` ya da
   `static/` dosyası düzenlendiğinde graflar kendiliğinden yenilenir; oturum
   başında da özet gösterilir. (Kanca `bash` varsayıyor: Git Bash'siz
   Windows'ta çalışmaz, orada 2. madde yok sayılıp 1. madde iş görür.)
3. **Bu dosya** — ilk okunacak yerin neresi olduğunu söyler.

## 3. Testler — ve "yeşil"in ne zaman yeşil OLMADIĞI

**KURAL: bir değişiklik ancak E2E DÂHİL tam takım bu makinede koşmuşsa
itilir.** Bu bir üslup tercihi değil, ölçülmüş bir kusurun kapısı.

```sh
python3 tools/test_ortami.py           # ortamı CI'ınkiyle AYNI yapar (bir kez)
python3 tools/test_ortami.py --kontrol # hazır mı? (0 = evet)
.venv/bin/python -m pytest tests/ -q   # tam takım
```

NEDEN AYRI BİR ADIM VAR: `pytest tests/ -q` tek başına "CI'ın koştuğu şey"
DEĞİL. `tests/test_playwright_*.py` dosyaları `pytest.importorskip("playwright")`
ile başlıyor; playwright kurulu olmayan bir makinede o dosyalar ATLANIYOR ve
pytest yine "passed" diyor. 2026-09-13'te ölçüldü: `ci.yml` bu depoda dokuz kez
kırmızıya döndü, SEKİZİNDE düşen testler tam olarak o atlanan dosyalardaydı
(arayüz metni, ön tanımlı dil ve DOM çapası değişiklikleri yalnız orada
görünüyor). Dokuzuncusu da aynı ailenin öteki yüzüydü: takım hiç koşmamıştı.

Taze bir Claude Code oturumunun konteynerinde durum daha da sessiz — aynı gün
ölçüldü: `python3` orada 3.11 (bu depo 3.13+ istiyor), `pytest` kurulu değil ve
`pip install -r requirements.txt` sistem Python'uyla derlenmiyor. Yani "testler
yeşil" cümlesi çoğu zaman "testler hiç koşmadı" anlamına geliyordu.
`tools/test_ortami.py` bu ikisini birden kapatıyor: 3.13+ bir `.venv` kuruyor,
`_test.yml`in kurduğu HER ŞEYİ kuruyor (pinleri o dosyadan okuyarak) ve tarayıcı
indirilemeyen ortamlarda makinede hazır duran chromium'a bağ atıyor.

Üç mekanizma bu kuralı unutmaya karşı koruyor:

1. **`tests/conftest.py`** — E2E atlandıysa takımın sonunda gürültülü bir uyarı
   basar. `KROMIS_E2E_ZORUNLU=1` ile atlama HATAYA döner; CI bu değişkeni
   veriyor, yani orada kurulum adımı kaybolursa takım yeşil kalmaz.
2. **`.claude/settings.json`** — oturum başında ortamın E2E koşup koşamadığını
   söyler.
3. **`tests/test_test_ortami.py`** — aracın okuduğu pinler `_test.yml`le aynı
   mı, kapıyı kapıda tutar.

```sh
python3 -m pytest tests/test_graflar.py -q   # yalnız harita kapısı
```

Kurulum ve uygulamayı çalıştırma: [KURULUM.md](KURULUM.md). Sürüm/yayın
düzeni: [docs/yayin-hatti.md](docs/yayin-hatti.md).

## 4. Aynı depoda birden fazla oturum

Her Claude Code oturumu KENDİ konteynerinde, kendi klonuyla açılıyor: git
dışında hiçbir şey paylaşılmıyor. Bu yüzden yukarıdaki düzen bir oturumda ancak
o oturumun dalında `CLAUDE.md` + `.claude/settings.json` + `tools/graf_uret.py`
VARSA geçerli. Bunlar `main`'de olduğunda her yeni oturum düzeni kendiliğinden
alır; bir dal `main`'in gerisindeyse oturum düzeni HİÇ görmez.

Oturum ORTASINDA `git pull`/dal değişimi yapıldıysa kancalar o oturumda
devreye girmeyebilir (ayar dosyası oturum başında okunuyor). Zararsız: kapı ve
elle yenileme yerinde duruyor — `python3 tools/graf_uret.py` koşmak yeter.

`docs/graflar/` altında ÇATIŞMA çıkarsa tartışılacak bir şey yok, çünkü o
dosyalar türetilmiş: iki taraftan herhangi birini al (`git checkout --ours` ya
da `--theirs`), sonra

```sh
python3 tools/graf_uret.py && python3 tools/graf_uret.py --kontrol
```

Doğruyu birleştirme değil ÜRETİCİ belirliyor; `--kontrol` yeşilse çatışma
gerçekten kapanmıştır. Aynı sebeple graf dosyalarını elle düzeltmeye çalışmak
kayıp emek.

## 5. Bu deponun yazı geleneği

Kod okurken hemen görülür, yenisini yazarken de sürdürülmeli:

* Yorumlar ve belgeler **Türkçe**; test işlev adları İngilizce cümleler.
* Yorum "ne yaptığını" değil **NEDEN öyle olduğunu** anlatır — çoğu yorum
  gerçekten yaşanmış bir kusuru kaydediyor. Bir kararı değiştirirken önce o
  gerekçeyi oku; hâlâ geçerliyse karar durur.
* Türetilen her şeyin bekçisi bir testtir (sürüm literalleri, depo adresi,
  `encoding` sözleşmesi, satır sonları, artık depo haritası da).
* Elle tutulan her KAPSAM listesinin bekçisi de bir testtir. Bir kapı "şu
  dosyaları tara" diyorsa, listede olmayan dosyanın öntanımlı hâli *muaf*
  demektir ve yeni gelen dosya kapıyı hiç görmeden geçer — `fal_client.py`
  v0.23'te, `static/i18n.js` PR #12'de tam olarak böyle kaçtı. Liste elle
  kalabilir (mekanik ölçüt çoğu yerde gürültü üretiyor, ölçüldü), ama
  EKSİKSİZ olmak zorunda: her öğe ya taranan listede ya da GEREKÇESİYLE
  muafiyet defterinde. Deyimi üç yerde görebilirsin —
  `test_every_shipped_module_is_classified` (i18n),
  `test_the_scan_covers_every_shipped_script` (id sözleşmesi),
  `test_the_scan_actually_covers_the_files_that_matter` (telif).
* Metin dosyası açan her çağrı `encoding` VERMEK ZORUNDA
  (`tests/test_encoding_contract.py`), satır sonları LF (`.gitattributes`).
