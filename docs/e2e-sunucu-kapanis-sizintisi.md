# E2E sunucu kapanış sızıntısı — takımı 6 dakikadan 80+ dakikaya çıkaran kusur

> Bu belge bir TEŞHİS KAYDI: kusurun nasıl bulunduğunu, hangi açıklamaların
> ölçümle çürüdüğünü ve hangi aracın işe yaradığını tutuyor. Onarımın kendisi
> `tests/conftest.py::KAPANIS_TAVANI_SN` ve `tests/test_e2e_sunucu_kapanisi.py`
> içinde, gerekçeleriyle birlikte. Burası kapı DEĞİL, kapının hikâyesi.

**Tarih:** 2026-09-19 gecesi / 2026-09-20
**Belirti:** `pytest tests/ -q` bu makinede normalde **6 dakika** sürerken **80+ dakika** sürdü ve bitmedi. İki kez görüldü: 19 Eylül'de eş zamanlı koşan iki dalda, 20 Eylül'de tek başına koşan bir dalda.

## Teşhis (kesin, `py-spy dump` ile)

Asılan süreçte iki iş parçacığı:

```
join (threading.py:1133)
_eski_e2e_sunuculari_kapansin (tests/conftest.py:368)
```

```
run_forever (asyncio/base_events.py:678)
run (uvicorn/server.py:86)
run (tests/test_playwright_hesap.py:55)
```

`tests/conftest.py`'deki autouse fixture, hâlâ yaşayan her uvicorn iş parçacığını
`t.join(timeout=10)` ile bekliyor. `test_playwright_hesap.py`'nin sunucusu
ölmediği için **o dosyadan sonraki her test 10 saniye ödüyor.**

## Mekanizma

1. Test `finally: sunucu.stop()` diyor — ama `stop()` yalnız `should_exit = True` yazıyor, beklemiyor.
2. uvicorn kapanırken **biten bir yanıt** bekliyor. `timeout_graceful_shutdown` verilmemiş → öntanımlı `None` → **süresiz** bekliyor.
3. Bekletiyor olan şey **bitmeyen bir yanıt** (ürün yüzü: `isler` panelinin SSE akışı). Bkz. aşağıdaki "Mekanizma ölçüldü".
4. İş parçacığı ölmüyor, fixture her testte 10 sn bekleyip vazgeçiyor, sonraki testte yine deniyor.

Fixture'ın kendi belgesi "zaman aşımı: `stop()` denmemiş bir sunucu takımı
asmasın" diyor. Gerçekten asmıyor — ama takımı sürüngen hâle getiriyor.
**Zaman aşımı asılmayı kusurdan yavaşlığa çeviriyor, kusuru kaldırmıyor.**

## Ölçümler

| ne | değer |
| --- | --- |
| tek koşum tabanı (2026-09-19) | 6 dk 13 sn — 3813 passed, 10 skipped, 0 failed |
| asılı koşumda 110–115 arası dosyalar | 134 test / 19 dakika ≈ **8,5 sn/test** |
| 25 sn'de harcanan CPU | 0,02–0,16 sn (uyuyor, çalışmıyor) |
| DB'ye açık bağlantı | yok — yani DB darboğazı DEĞİL |
| alt süreç | yok |

8,5 sn/test ile fixture'ın 10 sn'lik zaman aşımı örtüşüyor: yavaşlığın kaynağı
DB ya da Windows değil, doğrudan bu vergi.

## Kök sebep — eş zamanlılık hipotezi ÇÜRÜDÜ (2026-09-20)

İlk gün iki takım aynı anda koşuyordu, o yüzden şüphe port çakışmasına gitmişti:
`get_free_port()` portu 0'a bağlayıp alıyor, kapatıyor, sonra uvicorn onu bağlıyor;
iki koşum aynı boş portu seçerse biri ötekinin sunucusuna bağlanabilir.

**Bu açıklama düştü.** Ertesi gün kusur, **tek başına** koşan ve o değişikliği
içermeyen bir dalda yeniden çıktı (sızan sunucu bu sefer `test_playwright_studio`,
önceki gün `test_playwright_hesap` idi). Aynı gün bir başka tam koşum ise hiç
tetiklemedi — yani kusur **aralıklı bir yarış**, eş zamanlılığa bağlı değil.

Buradan çıkan pratik kural: **"bende olmadı" bir kanıt değil.** Yeşil tek bir
koşum bu kusurun yokluğunu göstermiyor.

## Mekanizma ölçüldü (2026-09-20)

İki kurgu yan yana denendi, `stop()` sonrası sunucu kaç saniyede ölüyor:

| kurgu | tavan yok | tavan 1 sn |
| --- | --- | --- |
| açık soket, **yarım** HTTP isteği | 0,20 sn — **ölüyor** | 0,18 sn |
| **bitmeyen yanıt** (SSE benzeri) | 8 sn sonra hâlâ yaşıyor | 1,21 sn — ölüyor |

Yani kapanışı tutan şey **açık soket değil, bitmeyen yanıt**. Bu ayrım pratik
sonuç doğurdu: ilk yazdığım davranışsal test yarım-istek kurgusunu kullanıyordu
ve **tavan kaldırılsa bile yeşil kalıyordu** — yani kapı değildi. Ölçüm olmasa
sahte bir bekçi commit'lenmiş olacaktı.

## Onarım

- Beş test sunucusunun hepsi `timeout_graceful_shutdown=KAPANIS_TAVANI_SN` alıyor;
  sabit `tests/conftest.py`de, `join` süresiyle yan yana duruyor ki ilişkileri okunabilsin.
- `tests/test_e2e_sunucu_kapanisi.py` üç kapı kuruyor: (1) AST taramasıyla hiçbir
  sunucunun tavansız kalmaması, (2) tavanın `join` süresinden küçük kalması,
  (3) bitmeyen yanıtla kurulan davranışsal yeniden üretim.
- Kapı AST ile taranıyor, `grep` ile değil: `test_desktop.py`de `config: uvicorn.Config`
  biçiminde tip açıklamaları var, metin araması onları çağrı sanardı.

## Kalıcı olarak işe yarayan iki şey

- **Teşhis aracı:** `py-spy dump --pid <pid>`. Asılı takımda tek atışta cevabı
  verdi; CPU/DB/soket bakmaktan çok daha hızlıydı. Kasada: `pip install --target <dizin> py-spy`.
- **Uzun koşumu `| tail` ile başlatma, `| tee <günlük>` ile başlat.** `tail`
  her şeyi tamponda tutuyor; koşum öldürülürse elde hiçbir şey kalmıyor ve
  "nereye kadar geldi" sorusu cevapsız kalıyor. Bu bir kez tam olarak yaşandı.

## Notlar

- Bu, sabit `time.sleep(1.0)` → `sunucu_hazir(port)` değişikliğinden **kaynaklanmıyor**.
  Kanıt: değişikliği içermeyen öteki dal da tıpatıp aynı imzayla asıldı.
- CI'da (ubuntu-latest) bugüne dek görülmedi: `_test.yml`de `timeout-minutes: 20`
  ve takım orada geçiyor. Ama kusur aralıklı olduğu için "Linux'ta yok" demek
  için yeterli kanıt YOK — yalnız "henüz tetiklenmedi" denebilir.
