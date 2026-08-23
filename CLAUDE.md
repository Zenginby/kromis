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

## 3. Testler

```sh
python3 -m pytest tests/ -q                  # tam takım (CI'ın koştuğu şey)
python3 -m pytest tests/test_graflar.py -q   # yalnız harita kapısı
```

Kurulum ve uygulamayı çalıştırma: [KURULUM.md](KURULUM.md). Sürüm/yayın
düzeni: [docs/yayin-hatti.md](docs/yayin-hatti.md).

## 4. Bu deponun yazı geleneği

Kod okurken hemen görülür, yenisini yazarken de sürdürülmeli:

* Yorumlar ve belgeler **Türkçe**; test işlev adları İngilizce cümleler.
* Yorum "ne yaptığını" değil **NEDEN öyle olduğunu** anlatır — çoğu yorum
  gerçekten yaşanmış bir kusuru kaydediyor. Bir kararı değiştirirken önce o
  gerekçeyi oku; hâlâ geçerliyse karar durur.
* Türetilen her şeyin bekçisi bir testtir (sürüm literalleri, depo adresi,
  `encoding` sözleşmesi, satır sonları, artık depo haritası da).
* Metin dosyası açan her çağrı `encoding` VERMEK ZORUNDA
  (`tests/test_encoding_contract.py`), satır sonları LF (`.gitattributes`).
