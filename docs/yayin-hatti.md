# Yayın hattı

**Kısa cevap: yayın almak için hiçbir şey yapmıyorsun.** `main`'e bir PR
birleştir; sürüm artar, üç paket de derlenir ve hepsi yeşilse yayın kendiliğinden
çıkar. Bu belge o hattın nasıl kurulduğunu ve nerede durabileceğini anlatıyor.

## Neden böyle kuruldu

Eskiden yayın almanın yolu elle tag atmaktı ve bu üç somut kusur üretiyordu:

1. **Bir tag'i iki ayrı workflow yayınlıyordu.** v0.4.2'de `build-android.yml`
   yayını 16:15:29'da APK ile oluşturup *yayımladı*; masaüstü zip'leri 16:17:04'te
   eklendi. Arada ~95 saniye boyunca yayın sayfasında yalnız APK vardı — ve
   masaüstü işi kırmızıya düşseydi o eksik yayın öylece kalırdı.
2. **Tetik tag olduğu için hata geri dönüşsüzdü.** v0.2.1'de üç başarısız/iptal
   koşudan sonra ancak dördüncüsü yeşil oldu; tag çoktan atılmıştı.
3. **Ritüel elle ve atlanabilirdi:** version.py → README rozeti → GUNCELLEME.md
   → commit → tag → push. v0.4.1'de rozet v0.3.0'da kaldı; GUNCELLEME.md
   version.py 0.4.2'deyken hâlâ "Sürüm 0.4.0" anlatıyordu.

## Akış

```
main'e merge
   │
   ├─ karar         tools/surum_karari.py  → sürüm ne, yayın gerekiyor mu
   ├─ surum-yaz     tools/surum_yaz.py     → version.py + README + GUNCELLEME.md
   │                                          → main'e "chore(surum): vX.Y.Z [skip ci]"
   ├─ test          _test.yml              → hızlı kapı (Linux, ~3 dk)
   ├─ taslak        gh release create --draft → boş TASLAK (tag'siz, görünmez)
   ├─ paket-macos   _paket-macos.yml    ─┐
   ├─ paket-windows _paket-windows.yml  ─┼─ üçü paralel, TASLAĞA yükler
   ├─ paket-android _paket-android.yml  ─┘   (yayın hâlâ oluşmuyor)
   │
   └─ yayinla       TEK yazıcı → küme denetimi → --draft=false → tag + yayın
```

**Tag'i yayın işi atıyor, hattın başında değil.** Yani bir paket kırmızıya
düşerse ortada ne tag ne yayın kalır — "eksik yayın" diye bir ara durum yok.
Taslak bunu bozmuyor: taslağın tag'i yoktur ve yalnız yazma yetkisi olanlara
görünür; tag de, yayın da tek `--draft=false` çağrısında doğar.

**Paketler neden doğrudan taslağa yazıyor.** 2026-08-28'de paketler Actions
VARLIĞI olarak yükleniyor, `yayinla` onları indiriyordu. Actions varlık kotası
doldu: üç paket de hatasız derlendi ve doğrulandı ama teslim edilemedikleri
için yayın çıkmadı — depodaki 3.98 GiB'ın tamamı silindikten sonra bile sayaç
saatlerce dolu kaldı (hesaplama 6-12 saatte bir ve havuz hesap geneli). Yayın
varlıkları o kotaya hiç girmiyor; kırılgan olan tek şey aradaki ara kopyaydı.
Aynı sebeple Android wheel'i de varlıkla değil ÖNBELLEKLE taşınıyor (ayrı ve
ücretsiz havuz, depo başına 10 GB). Yayın yolunda artık tek bir
`upload-artifact` yok ve `tests/test_release_manifest.py` bunu mandallıyor.

## Sürüm nasıl belirleniyor

`tools/surum_karari.py`, `tests/test_surum_karari.py` ile sınanıyor. Kural:

| Durum | Sonuç |
|---|---|
| `version.py` son tag'in İLERİSİNDE | Artırma yok — o sürüm yayınlanır |
| `version.py` son tag'le AYNI, değişenler pakete girmiyor | **Yayın yok** |
| `version.py` son tag'le AYNI, `feat` var | Minör artar |
| `version.py` son tag'le AYNI, başka bir şey var | Yama artar |
| `!` ya da `BREAKING CHANGE` | Majör artar |

Birinci satır **kendi kendini onarma** kuralı: paketlerden biri kırmızıya
düşerse main'de artırılmış bir `version.py` kalır ama tag oluşmaz. Bir sonraki
merge o sürümü ikinci kez artırmaz — yayınlanmamış olanı yayınlar. Aynı kural,
sürümü elle bir PR içinde artıran insanı da destekler.

### "Pakete girmiyor" ne demek

Mesaja değil **yola** bakılıyor. Bu deponun squash-merge başlıklarının bir kısmı
Conventional Commits'e uymuyor ("Telefondaki üç arayüz kusurunu düzelt…") ve
yalnız mesajı okuyan bir kural tam da yayınlanması gereken düzeltmeyi atlardı.

`docs/`, `tests/`, `tools/`, `.github/` ve kök dizindeki belgeler dışındaki
**her şey** yayın gerektirir. Liste bir beyaz liste: tanımadığı yol "pakete
girer" sayılıyor, yani belirsizlik her zaman "yayınla" tarafına düşüyor.

### Elle geçersiz kılmalar

Commit ya da PR başlığına yazılır:

- `[yayin: yok]` — bu merge yayın üretmesin
- `[surum: minor]` / `[surum: major]` / `[surum: patch]` — seviyeyi ez
- `[not] Kullanıcıya şu şekilde anlat.` — GUNCELLEME.md'ye **bu** cümle girsin

Son madde önemli: not verilmezse GUNCELLEME.md commit başlıklarından üretiliyor
ve `fix(ci): ABI kapısı aapt2'nin tek tırnağını da silsin` satırı kullanıcı için
hiçbir şey ifade etmiyor.

## "Hiçbiri atlanmadan" garantisi nerede

`release_manifest.py` — yayına giren paketlerin tek kaynağı. İki yerde
tüketiliyor:

- **Çalışma anında:** `yayinla` işi TASLAĞIN içeriğini manifestle **küme
  eşitliği** olarak karşılaştırıyor. Eksik varlık da fazla varlık da yayını
  durduruyor; 0 baytlık bir dosya da geçemiyor.
- **pytest'te:** `tests/test_release_manifest.py` her PR'da README indirme
  tablosunu, GUNCELLEME.md dosya tablosunu, `yayinla` işinin `needs:` listesini
  ve her paket işinin TESLİM KOMUTUNDAKİ dosya adını manifestle
  karşılaştırıyor.

Dördüncü bir platform eklemek için manifeste bir satır yazmak **yetmez**:
README'si, GUNCELLEME satırı, çağrılabilir workflow'u ve `release.yml`'deki işi
gelene kadar takım kırmızı kalır. (Bu davranış gerçekten sınandı: manifeste
sahte bir Linux paketi eklemek altı testi birden düşürüyor.)

Ayrıca `test_yayini_yalnizca_tek_is_olusturuyor`, yayına yazan ikinci bir işin
geri gelmesini engelliyor — v0.4.2'deki yarışın tekrarını yapısal olarak
imkânsız kılan iddia bu.

## PR'da ne koşuyor

| Değişiklik | PR'da koşan |
|---|---|
| Her PR | pytest (~3 dk) **+ sızıntı taraması** (~1 dk) |
| `.spec`, `build.sh`, `build.ps1`, `android/`, `branding/`, `requirements.txt`, `.github/workflows/` | pytest **+ üç paket** |
| `tam-paket` etiketi | pytest **+ üç paket** |
| `static/`, `bundled/` | yalnız pytest — bkz. aşağısı |

**Depo `private`, yani runner dakikaları faturalanıyor** ve macOS dakikası 10x
sayılıyor. (Bu paragraf bir zamanlar tersini söylüyordu; 2026-08-28'de REST ile
ölçüldü: `visibility: private`.) Kapı bu yüzden daraltıldı: `static/` ve
`bundled/` pakete **dizin bütün** olarak giriyor, yani içerikleri paketlemenin
sonucunu değiştiremiyor. Kapının orada gerçekten yakaladığı tek sınıf —
doğrulamaların ADA GÖRE aradığı bir dosyanın yeniden adlandırılması — üç runner
yerine `tests/test_paket_icerik_listesi.py`de, her PR'da ve saniyenin altında
ölçülüyor. `static/`e dokunan bir PR'da yine de tam matris isteniyorsa yol
`tam-paket` etiketi.

**Sızıntı taraması her PR'da ve geçmişin TAMAMINDA koşuyor** (`gitleaks`,
sürüm + sha256 ile sabitlenmiş ikili). Diff'e bakmıyor, çünkü bir sırrın
commit'ten silinmesi onu geçmişten silmiyor — depoyu klonlayan herkes eski
commit'i okuyabiliyor. İlk koşunun kaydı: 76 commit, 3.4 MB, 405 ms, gerçek
sır yok. Muafiyetler `.gitleaks.toml`da tek tek yazılı SAHTE değerler; hiçbir
dizin bütün olarak muaf değil (yoksa fixture'ların yaşadığı yer kör kalırdı).
Maliyet gerekçesi burada bağlamıyor: iş ubuntu'da (1x) ve saniyenin yarısı
sürüyor.

## Yeni bir kapıyı sürüm harcamadan denemek

1. **pytest.** Karar mantığı ve sürüm yazıcısı saf Python:
   `pytest tests/test_surum_karari.py tests/test_surum_yaz.py` saniyeler sürüyor.
2. **Kuru prova.** Actions → *Yayın* → *Run workflow* → `kuru_prova: true`.
   Karar basılır, üç paket de derlenir; sürüm commit'i atılmaz, yayın oluşmaz.
   Dal üzerinden koşulabilir.
3. **Elle sürüm.** Aynı ekrandaki `surum` alanına `0.6.0` yazmak kararı ezer
   (geriye gitmediği denetlenir).

## Ne zaman durur — ve ne yapmalı

| Belirti | Sebep | Ne yapmalı |
|---|---|---|
| Yayın hiç çıkmadı, koşu yeşil | `karar` "pakete girmiyor" dedi | Beklenen davranış. Gerekiyorsa `[surum: patch]` ile yeniden birleştir |
| `yayinla` "yayına girmesi gereken paket YOK" dedi | Bir paket işi düştü | O işin kaydına bak; sorunu düzeltip main'e merge et — sürüm İKİNCİ kez artmaz |
| Android işi "imza ZORUNLU" dedi | Keystore sırları yok ya da `secrets: inherit` eksik | `docs/android/mimari.md` → İmzalama |
| Koşu hiç başlamadı | Workflow YAML'ı bozuk (GitHub onu sessizce yok sayar) | `pytest tests/test_release_manifest.py` — `test_butun_workflowlar_gecerli_yaml` bunu yakalar |

## İmzalama ve notarization

- **Android:** dört GitHub Secret gerekiyor (`ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`).
  Yayın yolunda imzasız APK'ya izin yok — kullanıcı onu kuramaz.
- **macOS:** ad-hoc imza var, **notarization yok**. Kullanıcı ilk açılışta
  Sistem Ayarları → Gizlilik ve Güvenlik → "Yine de Aç" yapıyor (KURULUM.md).
  Bu hattın kapsamı dışında; değiştirmek Apple Developer üyeliği gerektirir.
- **Windows:** kod imzası yok; SmartScreen uyarısı çıkıyor (KURULUM.md).

## Kapsam dışı

**iOS.** Depoda hiçbir iOS yapılandırması yok ve Android tarafı Chaquopy'ye
dayanıyor — Chaquopy iOS'a taşınmıyor. iOS ayrı bir CPython gömme zinciri
(python-apple-support), Apple Developer üyeliği ve TestFlight/App Store
dağıtımı demek; bu hattın bir uzantısı değil, ayrı bir proje.

**Intel Mac (x86_64) ve Windows ARM64.** Şu an paketlenmiyor. Gerekirse
`release_manifest.py`'ye bir satır eklemek yeter — testler geri kalanı (README,
GUNCELLEME, workflow, CI işi) tamamlanana kadar kırmızı kalarak yol gösterir.
