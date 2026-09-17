# Faz 0 — web-first zemin: görev listesi

**Tarih:** 2026-09-16 · **Karar:** web-first (Alperen Zengin, Slack) · **Dondurulan:** masaüstü + Android, v0.23.1
**Üst belge:** [superpowers/specs/2026-08-10-saas-transformation-master-design.md](superpowers/specs/2026-08-10-saas-transformation-master-design.md)

Faz 0'ın amacı ürün davranışını DEĞİŞTİRMEDEN, SaaS fazlarının (hesap, veri
tabanı, kredi, kuyruk) üstüne oturacağı zemini kurmak. Her madde bir PR; her
PR tek başına yeşil ve geri alınabilir. Sıra bağımlılığa göre: 2 → 3/4 (ikisi
2'ye dayanır), 5 ve 6 her an, 7 ve 8 sona.

Ölçüler bu belge yazılırken alındı (`98c781e` üstünde, Adım 1 dalında):
`app.py` 2.286 satır / 45 rota (`app.py:481` ilk, `app.py:2222` son rota);
takım 2.683 test, E2E dâhil 90 sn; ruff temiz (kapatılan kurallar
`pyproject.toml`da), mypy 77 bulgu / 24 dosya.

---

## 1. Web-first zemin — paketleme elle, düz-modül kilidi kalktı, ruff + mypy ✅ (bu PR)

**Kapsam.** `release.yml` yalnız `workflow_dispatch`; `ci.yml`den `kapsam` ve
üç paket işi silindi, `lint` işi eklendi (ruff kapı, mypy bilgi). Chaquopy
düz-modül mandalı `tests/test_android_packaging.py` silindi;
`tests/test_ci_paketleme_kapisi.py` silindi, yerine `tests/test_paketleme_dondurma.py`
(push/PR → paket YOK değişmezi + README'lerin dondurmayı söylediği).
`pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`), `requirements-dev.txt`e
`ruff==0.16.*`, `mypy==2.3.*`. Güvenli otomatik düzeltmeler uygulandı (64
bulgu, 42 dosya: ithal sırası, kullanılmayan ithal, `collections.abc.Callable`,
tırnaksız tip notu).

**Dokunulan.** `.github/workflows/{ci,release,_paket-*,build-pydantic-core-android}.yml`,
`catalog.py:28-38`, `providers.py:57-62` (docstring), `README.md`, `README.en.md`,
`docs/yayin-hatti.md`, `docs/dal-korumasi.md`, `docs/graflar/*`.

**Risk.** Düşük. Ürün kodu davranışı değişmiyor. Tek geri dönüşsüz etki:
main'e merge artık sürüm artırmaz; elle yayın yolu `Actions → Yayın`.

**Çıkış ölçütü.** Tam takım E2E dâhil yeşil, `ruff check .` temiz,
`graf_uret.py --kontrol` 0, PR açık.

---

## 2. `app.py` monolitini `routers/` + `services/` paketlerine böl ✅ (PR: `faz0/app-bolme`)

**Kapsam.** 45 rota ve yardımcıları alan bazlı `APIRouter`lara taşınır
(öneri: `routers/uretim.py` generate/edit/video/animate, `routers/galeri.py`
history/image/images/folders/import/output, `routers/sohbet.py` chat/chats,
`routers/ayarlar.py` settings/prefs/guncelleme, `routers/palet.py`,
`routers/bindirme.py` logo/banner/assets, `routers/kok.py` `/` + static).
Rota-dışı mantık (`_to_png`, `_read_png_file`, `_output_png_path`, redaksiyon,
`_model_available`) `services/` altına. `app.py` yalnız `FastAPI()` kurulumu,
middleware, `include_router` ve mount olur (~150 satır hedef).

**Test etkisi — ÖNCE ölçüldü.** Testler `import app as appmod` deyip modül
özniteliğini yamalıyor: `monkeypatch.setattr(appmod, "OUTPUT_DIR", …)` **47**
yerde, `ASSETS_DIR` **17**, `_to_png` **16**, `_dil` **3**, `STATIC_DIR` **2**
(ör. `tests/test_app.py:10`). Rota bir router modülüne taşınınca o modül
`appmod.OUTPUT_DIR`ı DEĞİL kendi kopyasını görür ve yama boşa gider — 47 test
sessizce geliştiricinin gerçek veri dizinine yazar (`tests/conftest.py`nin
lifespan koruması bunu kısmen yakalar). Bu yüzden 2, 4 ile birlikte
tasarlanmalı: dizinler bir ayar nesnesinden okunursa yamanın tek hedefi
kalır. Ara çözüm kabul edilebilir: router modülleri `import app` yapmadan
(döngü!) `services.ayarlar.OUTPUT_DIR()` gibi bir işlev çağırır; testler o
tek işlevi yamalar.

**Dokunulan.** `app.py` (bölünür), yeni `routers/__init__.py`, `services/__init__.py`;
`tools/graf_uret.py` (uç-nokta tarayıcısı `app.py`de `@app.<fiil>` arıyor —
`@router.<fiil>` ve `include_router(prefix=)` okumayı öğrenmeli, yoksa
`docs/graflar/uc-noktalar.md` boşalır ve `test_graflar` kırmızı olur);
`tests/test_i18n.py::test_every_shipped_module_is_classified` (yeni modüller
sınıflandırılmalı); `tests/test_telif_basligi.py` (`routers/*.py`,
`services/*.py` telif başlığı kapsamına girmeli — kalıp bugün yalnız kök ve
`tools/`); `kromis.spec` DOKUNULMAZ (dondurulmuş, PyInstaller `hiddenimports=[]`
varsayımı orada kalır ama artık yayın yolunda değil).

**Risk.** Orta-yüksek: en büyük diff, en çok test dokunuşu. Küçültme: bir
PR'da bir router (önce en bağımsızı `palet`), her adımda takım yeşil.

**Çıkış ölçütü.** `app.py` < 300 satır, 45 rota `uc-noktalar.md`de aynı yol ve
fiille görünüyor, hiçbir test `appmod.<rota yardımcısı>` yamalamıyor, takım yeşil.

**Yapıldığında (2026-09-16) plandan sapmalar.** Router adı `palet` değil
`paletler` (`services/palet.py` ile ad çakışması). Dizin ara çözümü
`services/ayarlar.py` değil `services/yollar.py` (`routers/ayarlar.py`
ile çakışırdı; `ayarlar` adı 4. görevin ayar nesnesine kalıyor) ve testler
DEĞİŞMEDİ: `yollar.output_dir()` `app.OUTPUT_DIR`ı `sys.modules` üzerinden
okuyor, 47+17+2 yama olduğu yerde çalışıyor — gerekçe o dosyanın başında.
Yalnız YARDIMCI yamaları taşındı: `appmod._to_png` (16) → `services.gorsel.to_png`,
`appmod._dil` (3) → `services.dil.aktif`, `_output_png_path`/`_read_png_file`/
`MAX_IMAGE_PIXELS` (1'er) → `services.gorsel`. Bekçi: `tests/test_app_bolme.py`
(satır tavanı, `@app.<fiil>` yok, katman yönü, her router takılı).
`tools/graf_uret.py` kapanışı artık modüller ARASI yürüyor ve `uc-noktalar.md`nin
`modüller` sütunu 45 rotada da bölünme öncesiyle birebir aynı çıktı (ölçüldü).

---

## 3. Dilin (i18n) istek/hesap bağlamına taşınması ✅ (PR: `faz0/dil-tercihi`)

**Kapsam.** `i18n._AKTIF` ZATEN bir `contextvars.ContextVar`
(`i18n.py:121`; yazan `set_active` `i18n.py:126`, okuyan `i18n.py:138`) —
yani ASGI altında istek başına doğru izole. Asıl sorun KAYNAĞI: middleware
her istekte `prefs.read(OUTPUT_DIR).get("language")` okuyor
(`app.py:133-163`), yani dil tek kullanıcının `prefs.json`undan geliyor.
Çok kullanıcılı web'de dil isteğin kendisinden (çerez → `Accept-Language` →
hesap tercihi) çözülmeli; `prefs.json` yolu yalnız geriye dönük.

**Dokunulan.** `app.py` middleware (2'den sonra `services/dil.py`), `i18n.py`
(`set_active` imzası değişmez), `prefs.py` (dil alanı okunur ama yazar
kalmaz), `static/settings.js` dil seçimi (çerez yazacak), `bundled/i18n/*.json`
DEĞİŞMEZ; `tests/test_i18n.py`, `tests/test_playwright_dil.py`.

**Risk.** Orta. E2E `test_playwright_dil.py` ön tanımlı dilin İngilizce
kaldığını sınıyor (v0.22 kararı) — çerezsiz ilk istek İngilizce kalmalı.

**Çıkış ölçütü.** Aynı süreçte eş zamanlı iki istek farklı dille doğru cevap
alıyor (yeni test: iki `TestClient`, iki çerez); `prefs.json` okunmadan dil
çözülüyor; takım yeşil.

**Yapıldığında (2026-09-16) plandan sapmalar.** Zincir `services/dil.py::coz`:
`X-Kromis-Lang` başlığı → `kromis_lang` çerezi → diskteki KAYITLI tercih →
`Accept-Language` → `i18n.DEFAULT`. Plandaki "hesap tercihi" halkası Faz 1'e
kaldı; takılacağı yer 3. halka (`services/tercih.py::dil`). Sapmalar:
(a) `static/settings.js` DEĞİŞMEDİ — çerezi `POST /api/prefs` cevabı kuruyor
(`routers/ayarlar.py`), ön yüz yazımdan sonra zaten `location.reload()`
yapıyor ve yeni sayfa çerezle geliyor; betiğin çerez yazmasına gerek kalmadı.
(b) `prefs.py` "yazar kalmaz" OLMADI — `language` hâlâ diske yazılıyor
(çerezsiz istemci ve geriye dönük yol için) ve yeni `prefs.read_stored()`
"hiç yazılmamış" ile "varsayılana eşit yazılmış"ı ayırıyor; `read()` onun
üstünden geçiyor. (c) `prefs.json` istek başına OKUNMUYOR ama tümüyle
devre dışı da değil: `services/tercih.py` dosya imzalı (`st_ino`,
`st_mtime_ns`, `st_size`) bir önbellek — istek başına tek `stat`, rota
yazınca `sifirla()`. Ölçü: 20 istekte ≤1 okuma (`tests/test_dil.py`).
(d) Ön tanımlı dil hiç işaret yokken İngilizce KALDI; yeni olan şey yalnız
tarayıcı başlığının diskte kayıt YOKKEN konuşması. Bekçiler: `tests/test_dil.py`
(sıra, çerez öznitelikleri, önbellek bayatlamıyor, iki çerezli istemci eş
zamanlı), `tests/conftest.py` (önbellek testler arasında sıfırlanıyor),
`tests/test_playwright_dil.py` (kurgu `read_stored`ı da yamalıyor).

---

## 4. `OUTPUT_DIR` / `ASSETS_DIR` / `STATIC_DIR` → ayar nesnesi (bağımlılık enjeksiyonu) ✅ (PR: `faz0/dizin-enjeksiyonu`)

**Kapsam.** `app.py:76-78` modül sabitleri (`paths.output_dir()` vb. ithal
anında hesaplanıyor) yerine tek `Ayarlar` (pydantic-settings YOK — stdlib
`dataclass` yeter, `catalog.py`nin deyimiyle) ve FastAPI `Depends(ayarlar)`.
Her store işlevi zaten dizini parametre alıyor (`storage.list_history(output_dir)`
`storage.py:250`, `jsonstore.write_atomic(path, …)` `jsonstore.py:68`) — yani
değişiklik STORE'larda değil, ÇAĞIRAN rotalarda. `paths.data_dir()`
(`paths.py:90`) dört dallı; web'de tek dal (env `KROMIS_DATA_DIR`) + dondurulmuş
kabuk dalları dokunulmadan kalır.

**Dokunulan.** `app.py`/`routers/*`, yeni `services/ayarlar.py`, `paths.py`
(yeni env), `tests/conftest.py` (tek `ayarlar` fixture'ı 47+17 yamanın yerine),
`.env.example` (8'de).

**Risk.** Orta. `tests/conftest.py`nin "gerçek veri dizinine yazma" koruması
fixture'a taşınmalı, yoksa 2'deki sızıntı sınıfı geri gelir.

**Çıkış ölçütü.** `grep -rn 'setattr(appmod, "OUTPUT_DIR"' tests/` → 0;
uygulama `KROMIS_DATA_DIR=/tmp/x` ile açılıp oraya yazıyor; takım yeşil.

**Yapıldığında (2026-09-16) plandan sapmalar.** Modül adı `services/ayarlar.py`
değil `services/ayar.py`: `routers/ayarlar.py` ile `app.py`de aynı satırda
ithal edilince ad çakışırdı; parametre adı `ayarlar` kaldı
(`ayarlar: ayar.Ayarlar = Depends(ayar.ayarlar)` → gövdede `ayarlar.output_dir`).
`Ayarlar(data_dir, output_dir, assets_dir, static_dir)` donmuş `dataclass`,
alanlar `str` (`Path` DEĞİL — depo `os.path.join` deyiminde, store'lar `str`
alıyor, 60'tan fazla test `str(tmp_path)` veriyor; türü değiştirmek bu PR'ın
konusu değildi). Nesne `app.state.ayarlar`da ve İTHAL ANINDA kuruluyor,
lifespan'da değil: saf yol hesabı, dizin açmaz ve `TestClient(app)`i `with`siz
kullanan testler lifespan'ı hiç koşturmuyor. `services/yollar.py` SİLİNDİ
(`sys.modules["app"]` bakışıyla birlikte); `app.OUTPUT_DIR/STATIC_DIR/
ASSETS_DIR/BASE_DIR` ve `__all__`daki adları kalktı — dışarıda okuyan yoktu
(`desktop.py`, `android_main.py`, `netguard.py` yalnız `app.app` okuyor).
Store'lara DOKUNULMADI; dizini artık ÇAĞIRAN veriyor: 45 rotanın 37'si
`Depends(ayar.ayarlar)` alıyor, 7 service işlevi (`kapilar.check_folder`,
`gorsel.output_png_path/output_media_path`, `palet.saved_palette/palette_prompt`,
`modeller.director_context`) ve router yardımcıları dizini parametre olarak
alıyor. Dil ara katmanı (`services/dil.py::coz`) `Depends` alamadığı için
`ayar.ayarlar(request)`i doğrudan çağırıyor — okuma noktası tek.
`paths.data_dir()` `KROMIS_DATA_DIR`ı EN ÖNDE okuyor (açık işletmen kararı
frozen/Android tahminini yener; `resource_dir` etkilenmez);
`paths.ensure_data_dirs(*dizinler)` isteğe bağlı dizin alıyor, lifespan ayar
nesnesininkini geçiyor, dondurulmuş kabuklar argümansız çağırmaya devam
ediyor. Testler: `tests/conftest.py::dizinler` TEK fixture (fabrika —
`dizinler(output_dir=…, assets_dir=…)`; fabrika olması şart, testlerin yarısı
`output_dir=tmp_path`, yarısı `tmp_path/"output"` yerleşimine iddia yazıyor)
66 yamanın (47+17+2) yerine geçti; `tests/test_app_bolme.py` artık
`sys.modules` okuyan modül yok + `app`te dizin sabiti yok + yönlendirme rotaya
ulaşıyor iddialarını taşıyor. `tests/conftest.py`nin gerçek-dizin koruması
yerinde: `_isolate_lifespan` (test_backup) `data_dir`i de ayar nesnesinden
yönlendiriyor. Bilinen sonuç: `docs/graflar/uc-noktalar.md`nin `modüller`
sütunundan `paths` düştü — dizin artık çağrı değil öznitelik, statik kapanış
onu izlemiyor; gerekçe README'nin son bölümüne madde olarak eklendi.
`.env.example` 8. göreve kaldı.

---

## 5. Bağımlılık pinlerini yükselt: FastAPI / uvicorn / httpx / Pillow ✅ (PR: `faz0/bagimlilik-pinleri`)

**Kapsam.** `requirements.txt`: `fastapi==0.115.*` (2024), `uvicorn[standard]==0.32.*`,
`httpx==0.27.*`, `Pillow==11.*`, `python-multipart==0.0.*` → güncel kararlı
sürümlere. `pywebview`, `pythonnet`, `clr-loader` DONDURULMUŞ kabuğa ait —
bu PR'da ellenmez; web çalışma zamanı ayrı bir `requirements.txt` kümesine
ayrılabilir (`requirements-web.txt`?) ama `tools/test_ortami.py` gereksinim
dosyalarını `_test.yml`den okuyor, ekleme orada da görünmeli.

**Tripwire'lar.** `tests/test_bagimlilik_pinleri.py` (her satır pinli — biçim
korunur), `tests/test_python_surumu.py` (3.13 tabanı), `tests/test_test_ortami.py`
(gereksinim sırası `_test.yml`le aynı), `tests/test_playwright_kurulumu.py`
(playwright `requirements-dev.txt`e GİRMEZ). httpx 0.28 `proxies=` kaldırdı ve
istemci enjeksiyonu deseni (`azure_client.generate(client=…)`, `tests/test_azure_client_http.py`)
`httpx.MockTransport` kullanıyorsa imza değişikliği orada görünür. Pillow
sürüm atlaması `tests/fixtures/logo` altın görüntülerini bayt bayt değiştirebilir
(`tests/test_logo.py`, `tools/make_logo_goldens.py`) — altınlar yeniden
üretilir, fark gözle onaylanır.

**Risk.** Orta. Kırılma sınıfı: sessiz davranış farkı (Pillow yeniden örnekleme,
Starlette `TestClient` çerez davranışı).

**Çıkış ölçütü.** Pinler güncel, `pip install -r requirements.txt` temiz, tam
takım yeşil, altın farkları PR'da açıklanmış.

**Yapıldığında (2026-09-16) plandan sapmalar ve ölçümler.** Pinler:
`fastapi 0.115.*→0.141.*` (dolaylı starlette 0.46.2→1.6.0), `uvicorn[standard]
0.32.*→0.53.*`, `httpx 0.27.*→0.28.*`, `Pillow 11.*→12.*`, `pytest 8.*→9.*`;
`_test.yml`de `playwright 1.62.*→1.63.*`. `python-multipart 0.0.*` zaten
güncel (0.0.32); `pyinstaller-hooks-contrib 2026.7`, `ruff 0.16.*`, `mypy 2.3.*`
zaten en son. `pyinstaller 6.21.*` BİLEREK yerinde: dondurulmuş paketleme
kabuğuna ait (`kromis.spec`, v0.23.1). `requirements-web.txt` ayrımı
yapılmadı — pywebview ve .NET köprüsü işaretçili pinleriyle `requirements.txt`te
durdu; ayrım 8. göreve (Dockerfile) kaldı, iki farklı kurulum kümesi orada
doğuyor. `android/app/build.gradle`deki pinler dondurulmuş, dokunulmadı.

Kırılan dört yer, hepsi test tarafında (ürün kodunda yalnız bir yorum):
(a) FastAPI 0.137 `include_router` kopyalamayı bıraktı, `app.routes` ağaç
oldu → `tests/conftest.py::duz_rotalar` (`test_app_bolme`, `test_arena_onyuz`);
(b) FastAPI 0.141 dosya adı BOŞ multipart parçasını `UploadFile | None` için
`None` sayıyor (0.115: 422; Starlette hâlâ boş `str` ayrıştırıyor) →
`test_video_route` yeniden yazıldı + "düz metin → 422" testi eklendi,
`routers/uretim.py` yorumu düzeltildi; (c) Starlette 1.0 `on_event`i kaldırdı →
`test_android_main` `lifespan=`e geçti; (d) Pillow 12.3 `Image.getdata()`i
kullanımdan kaldırdı → `test_playwright_studio` `tobytes()`. Öngörülen riskler
gerçekleşmedi: httpx `proxies=`/`app=` depoda yoktu, `MockTransport` yok
(sahte istemciler elle), `tests/fixtures/logo` altınları bayt bayt aynı
(yeniden üretim gerekmedi), TestClient çerez davranışı aynı, ön yüzün 15
JSON `fetch`inin hepsi `Content-Type` veriyor (FastAPI 0.132 `strict_content_type`).
Ölçüm: takım 2761→2762 test (yeni 422 testi), uyarı 7→4 (giden: `on_event` ×2,
`websockets.legacy` ×2 — uvicorn 0.50 `websockets-sansio`ya geçti; gelen:
`StarletteDeprecationWarning` — Starlette 1.6 test istemcisi için `httpx2`
istiyor, `fastapi/testclient.py`den, üçüncü parti; takip: 6. görev), mypy 72
bulgu / 25 dosya (`mypy .`; belge yazılırken 77, Adım 4 sonrası 75 — yükseliş
sayıyı artırmadı), ruff temiz.

---

## 6. mypy'yi kapıya çevir (kademeli sıkılaştırma) + ruff `ignore` listesini eritme ✅ mypy yarısı (PR: `faz0/mypy-zorunlu`)

**Kapsam.** Bugün: mypy 77 bulgu / 24 dosya — `app.py` 22, `providers.py` 8,
`winsec.py` 6 (dondurulmuş, `exclude`a alınabilir), `desktop.py` 4 (aynı),
`tools/graf_uret.py` 4; kod türleri `arg-type` 23, `attr-defined` 16,
`union-attr` 13, `name-defined` 6. Yol: (a) dondurulmuş kabuk modüllerini
`[tool.mypy] exclude`a al, (b) `app.py`/`providers.py` bulgularını 2 ile
birlikte kapat (bölünürken imza yazılır), (c) sıfıra inince `ci.yml`deki
`continue-on-error: true` kalkar, (d) `check_untyped_defs = true`, sonra
modül modül `strict`. Ruff tarafı: `pyproject.toml`daki `ignore` listesi
(E501 41, B904 17, E702 12, B905 11, B008 5 [kalıcı, FastAPI deyimi],
E741 4, UP031 4) ve dosya-bazlı F841/E402/E731 kural kural kapatılır;
`ruff format` ayrı bir "yalnız biçim" PR'ı (141/153 dosya değişir — tek
commit, `git blame` için `.git-blame-ignore-revs`).

**Dokunulan.** `pyproject.toml`, `ci.yml` (`lint` işi), dokunulan modüller.

**Risk.** Düşük; yalnız tip notu ve `from err` zincirleme. `B904`
düzeltmesi `providers.detail_of` gibi hata eşlemelerinde istisna zincirini
görünür kılar — hata mesajı redaksiyonu (`errlog.py`, `tests/test_errlog.py`)
zincirdeki `__cause__`ü de sansürlüyor mu, ölçülmeli.

**Çıkış ölçütü.** `mypy .` 0 bulgu ve `continue-on-error` kalkmış;
`[tool.ruff.lint] ignore` yalnız `B008` içeriyor.

**Yapıldığında (2026-09-16) — mypy yarısı; ruff yarısı AYRI PR'a kaldı.**
Taban 72 bulgu / 25 dosya (Adım 5 sonrası ölçüm), hepsi kapandı: `mypy .`
0, `ci.yml` `lint` işinden `continue-on-error: true` kalktı. Kırılım koda
göre — `arg-type` 21, `attr-defined` 15, `union-attr` 13, `name-defined` 6,
`dict-item` 6, `index` 4, `operator` 3, `assignment` 3, `list-item` 1.
Yola göre: **60 gerçek düzeltme** (daraltma, tip notu, eşdeğer yeniden
yazım — hiçbiri davranış değiştirmiyor), **6 bulgu 5 satır `# type: ignore[...]`**
ile gerekçeli (`guncelleme._zaman`: `float(object)` bilerek, `TypeError`
yakalanıyor; `winclr` ×2 `winreg`, `desktop` `ctypes.windll`, `test_winsec`
`_set_dacl`: typeshed bunları yalnız win32'de tanımlıyor), **6 bulgu tek
modül muafiyeti** (`winsec`, `name-defined`: win32 dalı Linux'ta okunmaz;
ruff F821 aynı kusuru platformdan bağımsız yakalıyor). Stub paketi
GEREKMEDİ. Plandaki "dondurulmuş kabukları `exclude`a al" YAPILMADI ve
yapılamazdı: `exclude` ithal edilen modülü susturmaz (mypy ithali izler),
`ignore_errors` susturur ama görünmez — kabuk modüllerinin 12 bulgusu da
düzeltildi.

Düzeltmelerin biçimi, okurken şaşırtmasın diye: `routers/uretim.py`nin 18
bulgusu doğrulayıcının ZATEN garantilediği iki değişmezin (`req.model`
normalleştirildi, katalog kaydı var) tip düzeyindeki karşılığı olan 9
`assert`; `providers`/`chat_providers`'ta `bool(m) and …` → `m is not None
and …` (dataclass her zaman doğru, aynı anlam); `storage.valid_id`/
`chat_store.valid_id` iki adıma açıldı; `_ADAPTERS` tabloları
`tuple | Callable[[], tuple]`; `Image.LANCZOS` → `Image.Resampling.LANCZOS`
(aynı değer, 1 — Pillow 12 modül sabitini tip dosyasından düşürdü;
`tests/fixtures/logo` altınları bayt bayt aynı); `tests/test_desktop.py`nin
sahte `webview` modüllerine nitelik `vars(m).update(...)` ile yazılıyor
(typeshed `ModuleType`a yazımı tanımlamıyor); `tools/graf_uret.py`de aynı
işlevde `str` olarak bağlanmış `hedef` adı yeniden kullanılıyordu → `rota`.

Yapılandırma (`pyproject.toml` → `[tool.mypy]`): `platform = "linux"` (CI'ın
platformu; yazılmasa Windows'ta koşan mypy `sys.platform == "win32"`
dallarını okur, Linux'ta okumaz — aynı commit iki sayı verirdi ve platform
gerekçeli ignore'lar Windows'ta "kullanılmıyor" hatasına dönerdi),
`warn_unused_ignores`, `warn_redundant_casts`, `strict_equality`,
`extra_checks`, `no_implicit_reexport` — hepsi ölçüldü, sıfır ek bulgu.
`check_untyped_defs` AÇILMADI: ölçüldü, tek başına 393 bulgu / 63 dosya
(imzasız test gövdeleri ve `_capabilities_fit_the_model` gibi imzasız
doğrulayıcılar); `warn_return_any` +55, `warn_unreachable` +2
(`screencolor.py:99`, `color_names.py:212`). Bunlar ve modül modül `strict`
sıradaki kademe — ayrı PR. Bekçiler: `tests/test_mypy_kapisi.py`
(bayraklar gevşemez, `ignore_errors` yok, muafiyet yalnız `winsec`/
`name-defined`), `tests/test_paketleme_dondurma.py` (mypy adımı var ve
`continue-on-error` yok). Ruff `ignore` listesinin eritilmesi (E501, B904,
E702, B905, E741, UP031) bu PR'da YOK — `B904` için `errlog` redaksiyon
ölçümü gerekiyor (yukarıdaki risk notu), ayrı PR.

---

## 7. Ön yüz: eslint + prettier, paketleme (bundler) kararı ✅ (PR: `faz0/onyuz-araclari`)

**Kapsam.** `static/` 10 betik / ~10.900 satır, `static/index.html:1967-1988`
11 `<script>` etiketi, modül sistemi yok, tek küresel kapsam
(`docs/graflar/onyuz.md`). İki karar: (a) eslint (`no-undef`, `no-unused-vars`,
`eqeqeq`) + prettier `--check` — `package.json` + `ci.yml`e `lint-onyuz` işi;
(b) ES modüle geçilecek mi? Karşı ölçü: `tests/test_index.py` (286 test) ve
`tests/test_id_contract.py` (14) kaynak METNİNE ve küresel ad çakışmasına
iddia yazıyor; ES modül her `function foo()`yu yerel yapar ve 286 iddianın
bir bölümü anlamsızlaşır. Öneri: Faz 0'da yalnız (a); (b) SaaS ön yüzünün
çerçeve kararıyla (React/Svelte/vanilla) birlikte Faz 1'de.

**Dokunulan.** yeni `package.json`, `.eslintrc`/`eslint.config.js`,
`.prettierrc`, `ci.yml`; `static/*.js` yalnız otomatik düzeltme.
`tests/test_id_contract.py::test_the_scan_covers_every_shipped_script` ve
`test_telif_basligi.py` kapsamı değişmez.

**Risk.** Düşük (a) / yüksek (b). Node CI'da zaten var (Playwright `node.exe`
soğuk açılışı `tests/test_search_predicate.py` → `NODE_ZAMAN_ASIMI` — ikinci
bir Node aracı aynı süreyi ödeyebilir).

**Çıkış ölçütü.** `npx eslint static/` ve `npx prettier --check static/`
CI'da yeşil; bundler kararı bir `docs/superpowers/specs/…-onyuz-paketleme.md`
belgesiyle kayda geçmiş.

**Yapıldığında (2026-09-17) ölçümler ve sapmalar.** Yalnız (a); (b)
`docs/superpowers/specs/2026-09-17-onyuz-paketleme.md`de karara bağlandı:
ES modül/paketleyici Faz 1'in çerçeve kararıyla birlikte, testlerde
değişmesi gerekenlerin envanteri o belgede. eslint **10.x** (9.x kayıt
tarihinde "artık desteklenmiyor" uyarısı veriyor; düz yapılandırma ikisinde
aynı), prettier 3.x, `globals`; tam pin + `package-lock.json`, CI `npm ci`.
Taban, yalnız tarayıcı küreselleriyle: **1060 hata** — 1035 `no-undef` (92
ayrı ad, hepsi başka betikte tanımlı) + 25 `no-unused-vars` (23'ü başka
betikten çağrılan üst düzey işlev). Kural `off`a çekilmedi: dosyalar arası
adlar `eslint.paylasilan-adlar.json`a yazıldı (7 tanımlayan dosya, 91 ad;
10'u `writable` — başka dosyanın atadığı; 1 iyimser kanca `syncSendButton`;
haritanın 3 fazla sayımı gerekçesiyle) ve `eslint.config.js` her betiğe yalnız
ÖTEKİ betiklerin adlarını veriyor — yan kazanç: `no-redeclare` iki dosyada
aynı adı yakalıyor. `no-unused-vars` `vars: "local"` (üst düzey ölü ad
denetimi bekçi teste taşındı: bugün 0). Sonuç **0 hata, 0 uyarı**;
`eslint --fix` hiçbir şey değiştirmedi; elle 2 düzeltme (`chat.js`:
hiç okunmayan `settingsBlock` değişkeni silindi, `catch (e)` → `catch`).
Prettier: yalnız `printWidth: 100`, ölçüldü — 80: 2823, 100: 2182, 120: 1978
fark satırı (ekle+sil); geri kalan varsayılan (çift tırnak, noktalı virgül,
2 boşluk — dosyaların bugünkü stili). 8 dosya, +1352/−809 satır; `mobile.js`
zaten uyumlu, `pixel-canvas.js` üçüncü parti (kapsam dışı, `.prettierignore`).
`static/*.css` ve `index.html` prettier KAPSAMINDA DEĞİL (`test_index.py`
metin iddiaları; karar Faz 1'e). `tests/test_index.py`'de 7, `tests/test_video_onyuz.py`'de 2 — **9 regex** biçimden
bağımsız hâle getirildi (`function f({` parametre nesnesi satırlara bölündü,
`addEventListener(\n "wheel"`, `new Set(\n [`, `card.setAttribute(\n
"aria-label"`, settings.js `keydown` + `}, true);` kapanışı, `{ deger: source,` nesnesi, `picker-note`
üçlü ifadesi) — niyet aynı,
`// prettier-ignore` ile beş çok satırlı işlevi biçimsiz dondurmak yerine.
Bekçi: `tests/test_onyuz_lint_kapisi.py` (defterdeki her ad tanımlı ve başka
dosyada kullanılıyor, tek dosyada; yazılabilirler gerçekten atanıyor; kanca
yalnız `typeof` ile yoklanıyor; graf kenarlarıyla tutarlılık; ölü üst düzey ad
yok; kurallar `off`/`warn` değil; `lint-onyuz` işi iki komutla kesici, Node
majoru pinli; `package.json` private, `dependencies` yok, pinler tam ve kilitle
aynı). Sonraki: `tools/graf_uret.py` betik-arası kenarı yorumsuz metinden
çıkarsın (3 fazla sayım kalkar) — ayrı, küçük PR.

---

## 8. `Dockerfile` + `/health` + `.env.example`

**Kapsam.** Çok aşamalı `Dockerfile` (python:3.13-slim; `uvicorn app:app
--host 0.0.0.0` — `netguard:korumali_app` fabrikası DEĞİL: `run.sh:38`deki
loopback kapısı konteynerde her isteği 403'ler, `netguard` dondurulmuş
masaüstü kabuğuna ait), `.dockerignore` (`tests/`, `android/`, `docs/`,
`.venv/`), `GET /health` (`{"ok": true, "version": APP_VERSION}` — 4'teki
ayar nesnesinin veri dizinine yazılabilirliğini de raporlar),
`.env.example` (`KROMIS_DATA_DIR`, `PORT`, sağlayıcı anahtarlarının adları
`catalog.CREDENTIALS`tan türetilir — elle liste DEĞİL, `tests/test_settings_route.py`
dersi). `compose.yaml` yalnız yerel geliştirme için.

**Dokunulan.** yeni `Dockerfile`, `.dockerignore`, `compose.yaml`,
`.env.example`, `app.py`/`routers/kok.py` (`/health`), `ci.yml` (`docker
build` işi, imaj itmez), `docs/graflar/uc-noktalar.md` (yeni rota),
`README.md` geliştirici rehberi (`docker run` satırı), `tests/test_health.py`
(yeni), `tests/test_i18n.py` sınıflandırması (rota metni i18n'e girmiyor).

**Risk.** Düşük. Kimlik dosyası `~/.config/kromis/credentials.env`
(`paths.py:187`) konteynerde yok — BYOK web'de `POST /api/settings` ile
yazılıyor, yani `KROMIS_DATA_DIR` altındaki dizin yazılabilir olmalı;
`azure_client._atomic_write`in `os.fchmod(0o600)` çağrısı bind-mount'ta
çalışır, `tmpfs`te de çalışır.

**Çıkış ölçütü.** `docker build . && docker run -p 8765:8765 kromis` sonra
`curl /health` 200 ve `/` arayüzü açılıyor; CI `docker build` yeşil; takım yeşil.

---

## Faz 0 dışı, ama burada not edilen

* `guncelleme.py` (GitHub Releases sürüm denetimi, 39 test): dondurulmuş
  masaüstü kullanıcıya "yeni sürüm" demeye devam eder — web sürümleri
  tag'lendiğinde yanlış pozitif. Faz 1'de "son masaüstü sürümü" işaretçisi ya
  da web'de kapatma.
* `tests/test_release_manifest.py`, `test_paket_icerik_listesi.py`,
  `test_ci_varlik_saklama.py`, `test_windows_acilis.py`, `test_desktop.py`,
  `test_winclr.py`, `test_winsec.py`, `test_screencolor.py`, `test_netguard.py`,
  `test_android_*.py` (~190 test) dondurulmuş kabuğu koruyor. Silinmiyor —
  elle yayın yolu hâlâ onlara dayanıyor; kabuk ince WebView'a dönüştüğü gün
  toptan giderler.
