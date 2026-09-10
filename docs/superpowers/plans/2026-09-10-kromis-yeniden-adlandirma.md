# Kromis Studio — Yeniden Adlandırma + Yeni İmza Anahtarı (Uygulama Planı)

**Goal:** Uygulamanın kimliğini `Lumeo` (+ Android'de eski kurum alan adına dayalı bir `applicationId`)
adından **Kromis Studio**'ya taşımak, Android için sıfırdan bir imza anahtarı üretmek ve
bunu MEVCUT KULLANICININ VERİSİNİ KAYBETMEDEN yapmak.

**Architecture:** Değişiklik üç sınıfa ayrılıyor ve sınıflar birbirine karışmadan
uygulanıyor: (1) **ad literalleri** — kaynakta, workflow'larda ve bekçi testlerinde eşleşen
çiftler; (2) **kimlik** — `applicationId`, `bundle_identifier`, imza anahtarı, depo adı;
(3) **göç** — eski adla açılmış kullanıcı dizinlerinin yeni ada taşınması. Üçüncüsü bu
planın ASIL yeniliği: önceki yeniden adlandırma (`gpt-image-studio` → `lumeo`) göç
gerektirmemişti çünkü uygulama kullanımda değildi (`paths.credentials_path` gerekçesi).
Artık v0.15.0 yayında ve `winclr.py`'nin başlığı 2026-09-04'te gerçek bir Windows
kullanıcısını kaydediyor — o gerekçe artık geçerli DEĞİL.

## Durum — 2026-09-10

| Faz | Durum |
| --- | --- |
| 0 — depo adı | ✅ `Zenginby/kromis`; boş "taşındı" deposu bilerek AÇILMADI (gerekçe Faz 0'da) |
| 1 — imza anahtarı | ✅ keystore repo D I Ş I N D A üretildi, dört sır tanımlandı |
| 2–9 | ✅ uygulandı; `main` (v0.17.2) birleştirildi, tam takım **2359 geçti, 1 atlandı** |
| 10 — doğrulama/yayın | ⏳ imza ve parmak izi ÖLÇÜLDÜ (koşu 34505244509); üç cihaz denetimi gerçek yayın varlıklarını bekliyor |
| 11 — public'e açılma | ⏳ denetim BİTTİ (sır/lisans/Actions yüzeyi temiz); geçmiş VE GitHub tarafı temizliği ŞART, sıra Faz 11'de |

PR: [Zenginby/kromis#75](https://github.com/Zenginby/kromis/pull/75) — bütün
kapılar yeşil (sızıntı taraması, paketleme kapsamı, pytest, Android paketi).

### `main` ile birleşme — 2026-09-10

Dal v0.15.0 tabanında açılmıştı; arada `main`'e iki yayın daha girdi (v0.16.0,
v0.17.2) ve ikisi de tam bu planın dokunduğu yerlere dokundu — 22 içerik
çakışması. Kural: **sözcük `main`'in, adlar bu dalın.** Sebebi, iki tarafın
AYNI "eski kurum" cümlelerini birbirinden bağımsız temizlemesi: `main` "teknik desteğe"
ve "yerleşik logo" dedi, bu dal "geliştiriciye" ve "kurumsal logo". `main`
YAYIMLANMIŞ ve uygulama İÇİ metinleri (`desktop.py`, `app.py`, `strings.xml`,
`winclr.py`) onun sözcüklerini taşıyor; belgelerin aynı sözlükten konuşması için
1. ve 3. sınıfın sözcüğü `main`'den alındı. Fixture'lar da o sözcüğe hizalandı
(`kurumsal-logo-*.png` → `yerlesik-logo-*.png`).

**Kimlik cümleleri (2. sınıf) bunun DIŞINDA kaldı.** `main` orada yalnız markayı
temizlemiş ("yöneticinizden aldığın bilgiler") — yani eski dağıtım modeli, adı
silinmiş hâliyle duruyor. Projenin kayıtlı yönü BYOK
(`2026-08-10-step-1-byok-versioning-open-source.md`) ve bu dalın metni onu
anlatıyor: anahtar kullanıcının KENDİ Azure kaynağından geliyor. Muhatap
sözcüğü `main`'in, kimlik anlatısı bu dalın.

Üç istisna daha, gerekçeleriyle: `tools/render_brand_assets.py`'de `main`'in
çoklu çözünürlük DÜZELTMESİ esas alındı (`--ours` seçilse simge yeniden 16x16'ya
düşerdi, PR #73); `GUNCELLEME.md`'de sürüm numarasını "yönetici" değil YAYIN
SAYFASI söylüyor (aynı belgenin 9. satırı ve `guncelleme.YAYIN_SAYFASI` oraya
yönlendiriyor); `prompt-yonetmeni.md`'de örnek "LUMEO" değil "İZMİR KAHVESİ"
kaldı — madde Türkçe karakter bozulmasını anlatıyor ve "LUMEO"da hiç Türkçe
karakter yok.

**Birleşmenin SESSİZCE geçirdiği şey.** `tests/test_brand_assets.py` `main`'de
YENİ bir dosya: çakışma çıkmadı, birleşme onu olduğu gibi aldı ve dosya eski
simge adlarını arıyordu — iki test kırmızı düştü. Ders: yeniden adlandırma
dalı bir birleşmeden sonra ÇAKIŞMA LİSTESİNE değil, TAKIMA bakmak zorunda;
karşı tarafın YENİ dosyaları eski adı hiç çakışmadan getiriyor.

**Planın ötesine geçen üç iş** (gerekçeleri ilgili fazlarda):

* **Kaybolan Türkçe-karakter güvencesi geri alındı.** `FileDescription` =
  `Kromis Studio — görsel üretim`; `_paket-windows.yml`'in kapısı beklentiyi
  yine KOD NOKTALARINDAN kuruyor. Yeni eşleşen çiftin bekçisi
  `tests/test_version.py::test_the_windows_gate_expects_exactly_what_the_spec_writes`
  (iki yönden de mutasyonla kanıtlandı) — kapı ASCII'ye inerse de kırmızı.
* **Göç için DÖRDÜNCÜ conftest guard'ı.** `ensure_data_dirs()` artık gerçek
  `~/.config/lumeo`'yu taşıyor; `with TestClient(app)` kullanan tek bir test
  geliştiricinin ev dizinini oynatırdı. `_guard_against_real_migration`
  varsayılanı no-op yapıyor, `test_paths.py` muaf (yedek guard'ının aynısı).
* **Eski GitHub hesabının adı da silindi** (`guncelleme.py`, `mimari.md`,
  `GUNCELLEME.md`, iki test): "eski kurum" kuralının kapsamındaydı ama önceki taramada
  küçük harfli olduğu için kaçmıştı. Gerekçeler ("boşalan ad başkası tarafından
  alınabilir") ad-nötr yazılarak KORUNDU.

**Bilinçli olarak eski adı TAŞIMAYA devam eden yerler** — üç sınıf, hepsi
savunulabilir:

1. **Göç makinesi:** `paths.OLD_APP_NAME` / `OLD_CONFIG_DIRNAME` + bekçileri.
   Eski ad kodda OLMAK ZORUNDA, yoksa taşınacak dizin bulunamaz.
2. **Alıntılanan kanıt:** 2026-09-04 kullanıcı `hata.log`'undaki üç satır
   (`desktop.py`, `winclr.py`, `branding/Kromis.exe.config`). Yeniden yazılırsa
   teşhisin dayandığı gözlem uydurulmuş olur; üçünde de alıntının TARİHSEL
   olduğu cümleye yazıldı.
3. **Kayıtlı kusur tarihi:** `test_syntax_warnings.py`'nin `\G`/`\L`/`\K`
   dizisi. Örneğin kendisi bugünkü ada çevrildi (kapı bugünkü tuzağı ölçüyor),
   yalnız harflerin tarihi duruyor.

## Karar defteri

| # | Karar | Sonucu |
| --- | --- | --- |
| a | `APP_NAME` DEĞİŞİYOR (`Lumeo` → `Kromis`) | Veri dizini adı değişiyor → **göç kodu + bekçi testi ZORUNLU** (Faz 2) |
| b | Eski uygulama adı hiçbir yerde kalmıyor | `GIS_`/`gis_` önekleri ve `gpt-image-studio.spec` DOSYA ADI da kapsamda (Faz 5, Faz 6) |
| c | Sahiplik `Zenginby` | `CompanyName`, `LICENSE`, sertifika `O=` alanı hizalanıyor |

**Görsel marka adı:** `Kromis Studio` · **Kod/dizin adı:** `Kromis` · **Paket kimliği:**
`com.zenginby.kromis` · **Depo:** `Zenginby/kromis`

### Kapsam DIŞI — bilinçli olarak dokunulmayanlar

Bunlar "eski ad" değil; ya tarihsel kayıt ya üçüncü tarafın kimliği:

* **`gpt-image-1` / `gpt-image-2` model kimlikleri** (`catalog.py`'de 6 kez, ayrıca
  `models.py`, `providers.py`). Bunlar OpenAI/Azure'ın MODEL ADI. `gpt-image` üzerinde
  toplu değiştirme uygulamanın görsel üretimini bozar. **Global sed YASAK.**
* `docs/superpowers/plans/`, `docs/superpowers/specs/`, `.superpowers/sdd/` — tarihsel
  kayıt. Eski PR bağlantıları yeni adla yazılırsa var olmayan adresler olur
  (`tests/test_depo_adresi.py` bu dizini bilerek taramıyor).
* `tests/test_surum_karari.py:242`'deki `claude/gis-keystore-mobile-app-mgakyw` — gerçek
  bir commit mesajı, yani git verisi.
* `hata.log` — üretilmiş kayıt, depoya girmiyor.
* `docs/android/mimari.md`'deki ESKİ anahtarın parmak izi tablosu — silinmiyor, "v0.15.0'a
  kadarki anahtar" olarak etiketleniyor; yeni tablo yanına ekleniyor.

## Ek bulgu: "eski kurum" (eski kurum) izleri — 2026-09-10'da TEMİZLENDİ

**Karar: "eski kurum" yazısı hiçbir yerde geçmeyecek.** Proje özel bir proje; Azure
kimliği de kullanıcının KENDİ kaynağından geliyor, kurumdan gelen bir şey yok.
Aşağıdaki altı sınıfın beşi uygulandı; kalan tek iz paket kimliği (Faz 5).

**Uygulandı — 33 dosya:** destek yönlendirmeleri (`teknik desteğe` — ilk
uygulamada `geliştiriciye` yazılmıştı, `main`'in birleşmesinde onun sözcüğüne
hizalandı), dağıtım ve kimlik cümleleri (kendi Azure kaynağı anlatısı — BYOK,
birleşmede KORUNDU), kaldırılmış yerleşik logo yorumları (`yerleşik logo`,
`main`'in sözcüğü), fixture/örnek varlık adları (`Logo Mavi`,
`yerlesik-logo-*.png`),
`prompt-yonetmeni.md`'deki noktalı-İ dersi (`İZMİR`, ders korundu),
`docs/flow-ui` maketlerinin marka etiketleri (`Kurumsal mavi`, tema jetonu
(eski kurum kısaltması) → `kurumsal`), `CompanyName` (`Zenginby`) ve test/maketlerdeki gerçek
Azure ana bilgisayar adları (gerçek kaynak adı → `ai-ornek-swedencentral`).

> **Yan bulgu — kaybolan güvence.** `CompanyName` ASCII'ye indiği için
> `_paket-windows.yml`'in Türkçe karakter kodlama kapısı KONUSUZ kaldı: eskiden
> VERSIONINFO'da Türkçe karakter turunu ölçen tek alan orasıydı ve beklenti kod
> noktalarından kuruluyordu. Bugün alanların tamamı ASCII. Gerekçe workflow'a
> yazıldı; geri kazanmanın yolu bir alana (ör. `FileDescription`) bilinçli bir
> Türkçe karakter koymak — Kromis adı buna uygun bir fırsat.

> **Yan bulgu — sızıntı hijyeni.** Testlerde ve maketlerde kullanıcının GERÇEK
> Azure kaynak adının kendisi yazılıydı; depo public olacaksa bu
> zaten kalmamalıydı. Örnek ada çevrildi.

### Karar (a) — tarihsel kayıtlar: TEMİZLENDİ (2026-09-10)

Öneri `.superpowers/sdd/`'yi depodan çıkarmaktı; **ölçünce o dizinin depoda
hiç olmadığı görüldü** — `.gitignore:31` onu zaten kapsıyor, izlenen dosya
sayısı SIFIR. Yani seçenek (b) baştan gerçekleşmiş durumdaydı ve geriye kalan
tek soru `docs/superpowers/` idi: 7 izlenen belgede 83 geçiş.

Uygulanan: **hepsi yeniden yazıldı**, karşılıklar canlı koddaki taramayla
BİREBİR aynı (`Şirket Logosu Mavi`, `kurumsal logolar`, `kurumsal mavi`,
`İZMİR`), yani depo kendi içinde tutarlı. Gerekçe: bunlar tasarım kaydı, kusur
KANITI değil — "o gün ne olduğu" sorusunun cevabı `Şirket Logosu Mavi` yazınca
okunamaz hâle gelmiyor. Üç yan kazanç:

* **Sızıntı hijyeni.** Kullanıcının gerçek Azure ana bilgisayar adı
  (24 geçiş) ve gerçek yerel kullanıcı adı (macOS ev dizini yolunda)
  bu belgelerde yazılıydı. Depo public olacaksa ikisi
  de kalmamalıydı; testlerde ve maketlerde zaten örnek ada çevrilmişti.
* **Ölü bağlantı YOK — tersine.** Plan "eski PR bağlantıları yeni adla
  yazılırsa var olmayan adresler olur" diyordu; bu YANLIŞ. PR numaraları depo
  ve hesap yeniden adlandırmasında korunuyor, yani kanonik adres
  `Zenginby/kromis/pull/16`. Eski adresler yalnız GitHub'ın yönlendirmesi
  yaşadığı sürece çalışıyordu.
* Eski `applicationId` (eski kurum alan adına dayalıydı) da bu belgelerdeydi.

**DÜZELTME (2026-09-10, Faz 11 denetimi): bu belge de istisna DEĞİL.**
Plan başta "kuralı kaydeden yer burası, sözcük buradan silinemez" diyordu
ve depo ÖZEL kaldığı sürece bu tutarlıydı. Public'e açılırken istisna
kendini bozuyor: temizlenen dizelerin HEAD'deki TEK taşıyıcısı bu dosya
kalıyordu — gerçek Azure kaynak adını, gerçek yerel kullanıcı adını, eski
kurumun alan adına dayalı `applicationId`'yi ve eski hesap adını düzgün
bir tabloyla yayımlıyordu. Ölçüldü: 31 geçiş, hepsi bu dosyada, başka
hiçbir izlenen dosyada yok. Kayıt korundu, harfler çıkarıldı: karar
"eski kurum" adlandırmasıyla hâlâ okunuyor, ölçüm sayıları yerinde duruyor.

### Kalan açık karar

Paket kimliği 2026-09-10'da temizlendi (Faz 5) ve tarihsel kayıtlar da yeniden
yazıldı (karar (a), yukarıda). Depoda tek bir açık madde kaldı:

* **`docs/flow-ui/assets/brand/*.png` (7 dosya) — ÇÖZÜLDÜ (2026-09-10):
  çıkarıldı.** Metin temizlenmişti ama bunlar eski kurumun GÖRSEL
  logoları/mottolarıydı ve depo public'e açılacak (aşağıdaki karar) — metinden
  silinen izin görselde kalması tutarsız olurdu. Yerlerine aynı adla, aynı
  ORANDA nötr SVG yer tutucular kondu (476 KB PNG → 6 KB SVG) ve maketlerdeki
  23 atıf onlara bağlandı: maket hâlâ "burada portre bir logo, şurada geniş bir
  şerit var" diyor, kimsenin markasını söylemeden. `data-px` değerleri
  tasarımın varsaydığı gerçek boyutları kaydetmeye devam ediyor.
  Gerekçe maketlerin kendi belgesinde: `docs/flow-ui/flow-redesign-plan.md`.
  (Atıf sayısı 12 değil 23 çıktı: ilk tarama yalnız `<img src>`leri saymış,
  `data-src` niteliklerini atlamıştı.)

Aşağıdaki sınıflandırma neyin NEDEN öyle çözüldüğünü saklıyor.

**1. Kullanıcıya dönük destek yönlendirmeleri — 2026-09-10'da TEMİZLENDİ.**
"lütfen bu dosyayı kuruma iletin" / "kuruma yaz" / "kuruma gönder" ifadeleri
`teknik desteğe` ile değiştirildi: `android/.../strings.xml`
(`sunucu_baslatilamadi_detay`), `desktop.py`, `app.py`, `KURULUM.md` (4),
`GUNCELLEME.md` (5), ve o cümleyi ALINTILAYAN `winclr.py` yorumu (hata.log
sözleşmesi). Marka-nötr sözcük bilinçli: yeniden adlandırmadan sonra yeniden
düzenlenmesi gerekmiyor.

> Bu sınıf ilk uygulamada `geliştiriciye` yazılmıştı. `main` aynı cümleleri
> BAĞIMSIZ olarak `teknik desteğe` diye temizleyip v0.17.2'de YAYIMLADI; iki
> sözcük bir arada, aynı deponun iki yerinde aynı şeyi başka türlü söylüyor
> olurdu. Birleşmede `main`'in sözcüğü esas alındı — uygulama İÇİ metinler
> zaten onu taşıyor ve kullanıcının ekranında gördüğü sözcük o.

**2. Dağıtım/kimlik modelini anlatan cümleler — KARAR GEREKİYOR.** Bunlar
sözcük değil, bir MODEL anlatıyor: uygulamayı kurum dağıtıyor ve Azure kimliğini
kurum veriyor. Yeni kimlikte (public Releases + kullanıcının kendi anahtarı) bu
cümleler yalnız eski adı değil, YANLIŞ bir işleyişi de taşıyor — o yüzden
sözcük değişimiyle kapatılmadı:

| yer | cümle |
| --- | --- |
| `KURULUM.md:148` | "Endpoint ve API key alanlarını kurumdan aldığın bilgilerle doldur" |
| `KURULUM.md:173` | "Dağıtım adı alanına kurumdan aldığın adı yaz" |
| `KURULUM.md:280` | "kurum yeni bir `.zip` gönderdiğinde…" |
| `KURULUM.md:323` | "kuruma doğru adı sor" |
| `GUNCELLEME.md:143,469` | "kurumun söylediği numarayla aynıysa/karşılaştır" |
| `GUNCELLEME.md:617` | "Dağıtım adı (kurum verecek, ör. `gpt-5.6-luna`)" |
| `GUNCELLEME.md:660` | "Geri yüklemek gerekirse (kurum söylerse)…" |

**Karar (Faz 8, 2026-09-10): BYOK anlatısı.** "Kendi Azure kaynağından aldığın
endpoint/anahtar", "Azure portalı → kaynağın → *Keys and Endpoint*", "Azure'da
oluşturduğun dağıtımın adı" — gerekçesi
`docs/superpowers/plans/2026-08-10-step-1-byok-versioning-open-source.md`.

> `main` bu cümleleri bağımsız olarak "yöneticinizden aldığın bilgiler" diye
> temizledi. O bir sözcük değişimi: eski dağıtım modeli, yalnız adı silinmiş
> hâliyle duruyor ve "size anahtarı veren bir kurum var" diyor. Bu yüzden 1. ve
> 3. sınıfın aksine bu sınıfta `main`'in sözcüğü AL I N M A D I — tek istisna,
> bir MODEL anlattığı için.

**3. Kaldırılmış özelliğin tarihsel kaydı — DOKUNULMUYOR.** `app.py:91,1774`,
`composite.py:13`, `models.py:561`, `assets_store.py:65` pakete gömülü "kurum logo
çifti"nden söz ediyor; o özellik marka-nötr olsun diye KALDIRILDI
(`docs/flow-ui/id-defteri.md:46`) ve yorumlar o kararın gerekçesi. Deponun yazı
geleneği bu yorumları korumayı söylüyor. `assets_store.py:65` ayrıca cp1254
kodlama dersini "Kurum Logo Mavi" örneğiyle kaydediyor — örnek değişirse ders
okunmaz hâle gelir.

**4. `bundled/prompts/prompt-yonetmeni.md:99,102` — DİKKATLİ DEĞİŞTİR.** eski kurumun adı ve o adı `spelled letter-by-letter as I-with-dot, L, A`
diye yazdıran yönerge burada
marka değil, **noktalı büyük İ'nin görsel modellerde bozulması** dersinin örneği.
`KROMIS` ile değiştirmek dersi yok eder (Kromis'te noktalı İ yok). Değişecekse
örnek yine noktalı İ taşıyan bir sözcük olmalı (ör. `İSTANBUL`).

**5. `docs/flow-ui/` — 26 izlenen dosya, eski kurumun markasıyla dolu tasarım maketi.**
`data-set-theme="kurumsal"` + kurumsal mavi (`#085888`), kurumsal motto ve
logo etiketleri, `alt` metinlerinde kurumun adı ve **7 gerçek marka
PNG'si** (`docs/flow-ui/assets/brand/{banner,logo-beyaz,logo-mavi,motto-*}.png`).
İyi haber: bunların hiçbiri ÜRÜNE girmiyor — `models.ALLOWED_THEMES` =
`("mono", "ocean", "amber", "viola")`, yani canlı uygulamada o tema YOK ve
depo kökündeki `assets/` git'te izlenmiyor. Karar: maket tarihsel kayıt olarak
kalsın mı, yoksa üçüncü tarafa ait marka görselleri depodan çıkarılsın mı? İkinci
seçenek yeniden adlandırmadan bağımsız ve ayrıca savunulabilir.

## Global Constraints

Her fazın gereksinimleri bu bölümü ÖRTÜK olarak içeriyor.

* **Eşleşen çiftler AYNI commit'te değişir.** Bu deponun en pahalı kırılma sınıfı, iki
  dosyanın kendi içinde tutarlı ama BİRLEŞTİKLERİ yerde ayrışmış olması
  (`tests/test_android_apk_name.py` başlığı bunu birebir anlatıyor). Bu planda dört çift
  var: Gradle `outputFileName` ↔ `_paket-android.yml`; `branding/*.exe.config` ↔ `build.ps1`
  + `_paket-windows.yml`; `android_main.SESSION_COOKIE` ↔ `MainActivity.OTURUM_CEREZI`;
  `static/core.js` köprü adı ↔ `MainActivity.KOPRU_ADI`.
* **Her commit graf dosyalarını İÇERİR.** `.py` ya da `static/` dosyası değişen her
  commit'te önce:

  ```bash
  python tools/graf_uret.py && python tools/graf_uret.py --kontrol
  ```

  Mandal: `tests/test_graflar.py`.
* **Yazı geleneği:** yorumlar ve kullanıcıya dönen metinler Türkçe; test işlev adları
  İngilizce cümleler. Yorum NEDEN'i anlatır. Metin dosyası açan her çağrı `encoding` verir
  (`tests/test_encoding_contract.py`). Satır sonları LF.
* **Türetilen her şeyin bekçisi bir testtir.** Bu planda ÜÇ yeni bekçi doğuyor: göç
  davranışı, oturum çerezi adının iki dildeki eşleşmesi, yeni sertifika parmak izi.
* **`\K` kaçış tuzağı:** `%LOCALAPPDATA%\Kromis` bir Python dizesinde `\K` üretir ve `\L`
  gibi geçersiz bir kaçış dizisidir. `tests/test_syntax_warnings.py` ile
  `tests/test_version.py` bunun bekçisi — literal ya raw dize ya çift ters bölü olmalı.
* **Tam takım her fazın sonunda:** `python -m pytest tests/ -q`.

---

## Faz 0 — Depo adı ÖNCE (planın en kritik sıra düzeltmesi)

Eski plan bunu en sona koyuyordu. Ters: `guncelleme.DEPO` yeni adı gösteren bir sürüm
yayına girip depo hâlâ eski adda kalırsa, güncelleme kontrolü 404 alır ve `guncelleme.py`
sözleşmesi gereği **sessizce** hiçbir şey göstermez. GitHub eski→yeni yönlendirmeyi kurar,
tersini kurmaz.

* [ ] GitHub → Settings → depo adı: `gpt-image-studio` → `kromis`
* [ ] Yerelde: `git remote set-url origin https://github.com/Zenginby/kromis.git`
* [ ] **Boşalan adı KULLANMA — boş bir "taşındı" deposu AÇMA.** (Bu madde
      2026-09-10'da tersine çevrildi; eski hâli iki yönden hatalıydı.)
      1. Korumaya çalıştığı risk YOK: depo adları sahibin ad alanına bağlı, yani
         `Zenginby/gpt-image-studio`'yu `Zenginby` hesabından başka kimse açamaz.
         `guncelleme._guvenli_url`'in yazdığı tuzak bir HESAP adının boşalmasıydı
         (kullanıcı ad alanları gerçekten başkasına geçebiliyor) — depo adına
         genellenemez.
      2. Yapılırsa ZARARI var: GitHub'ın eski→yeni yönlendirmesi, eski ad yeni bir
         depoyla DOLDURULDUĞU anda ölür. O zaman yayınlanmış eski istemcilerin
         `YAYIN_SAYFASI` isteği yönlendirilmek yerine boş depoya düşer ve
         `releases/latest` 404 verir — `guncelleme.py` sözleşmesi gereği güncelleme
         kontrolü SESSİZCE hiçbir şey göstermez. Yani madde, tam olarak korumak
         istediği şeyi kırardı.
      Doğru davranış: adı boş bırak, yönlendirme eski istemcileri taşımaya devam etsin.
* [ ] Doğrula: eski istemci yolu hâlâ çalışıyor mu —
      `curl -sIL https://github.com/Zenginby/gpt-image-studio/releases/latest`

## Faz 1 — Yeni imza anahtarı + GitHub Secrets

Eski anahtarın kimliği (ölçülmüş, `docs/android/mimari.md`): `CN=GPT-Image Studio, OU=Unknown,
O=Unknown, L=İstanbul, ST=Unknown, C=Unknown`, SHA-256 `b24743de…768b`.

**Araç `keytool`, openssl DEĞİL.** `docs/android/mimari.md:184` üretim yolunu keytool ile
belgeliyor; imzayı okuyan da Gradle/apksigner'ın JDK'sı. OpenSSL 3'ün PKCS12'si PBES2/AES
ile yazılıyor — JDK çoğunlukla okur, ama bu, bir kez ölçülmüş yoldan iki komutla sapmak.

* [ ] Anahtarı **depo ağacının DIŞINDA** üret (`.gitignore` yalnız `*.keystore`'u kapsıyor,
      `.key`/`.crt`'yi kapsamıyor — özel anahtarın depoya yaklaşmasının hiçbir sebebi yok):

      keytool -genkeypair -v -keystore kromis.keystore -alias kromis \
              -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12 \
              -dname "CN=Kromis Studio, O=Zenginby, C=TR"

      Parola SORULARAK alınıyor — komut satırına yazılmıyor, kabuk geçmişine düşmesin.
* [ ] **Anahtarı YEDEKLE:** parola yöneticisine ya da şifreli bir yedeğe. GitHub Secret
      geri OKUNAMAZ; anahtar kaybı = bu paket kimliğiyle bir daha güncelleme yayınlayamama
      (`docs/android/mimari.md` bunu ayrıca yazıyor).
* [ ] Base64: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("kromis.keystore")) | Set-Clipboard`
* [ ] Dört sırrı GÜNCELLE (adlar `_paket-android.yml`'in okuduklarıyla birebir — eski planda
      da doğruydu): `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`,
      `ANDROID_KEY_ALIAS` = `kromis`, `ANDROID_KEY_PASSWORD` = depo parolasının AYNISI
      (PKCS12 kuralı; farklı yazılırsa Gradle parola hatasıyla düşer).
* [ ] Çalışma kopyasını temizle (yedek alındıktan sonra).

> Parmak izi ölçümü Faz 9'da: yeni SHA-256/SHA-1 ancak ilk imzalı koşudan sonra bilinebilir.

## Faz 2 — `paths.py` + VERİ GÖÇÜ (kararın (a) bedeli) ✅ UYGULANDI (2026-09-10)

* [ ] `APP_NAME = "Kromis"`; `credentials_path()` → `~/.config/kromis/credentials.env`
* [ ] `ANDROID_DATA_ENV` / `ANDROID_RESOURCE_ENV` değerleri → `KROMIS_ANDROID_DATA_DIR` /
      `KROMIS_ANDROID_RESOURCE_DIR`. **Tek dosyalık değişiklik:** `android_main.py:119` ve
      `tests/conftest.py` sabiti kullanıyor, literali değil.
* [ ] **Göç fonksiyonu** — `ensure_data_dirs()`'in İÇİNDE, `makedirs`'ten ÖNCE çağrılıyor
      (üç giriş noktası da orayı çağırıyor: `app.py:97`, `desktop.py:359`,
      `android_main.py:147`; `tests/test_paths.py:212` "açılışta, import'ta değil"i zaten
      mandallıyor). Sözleşme:
      1. Yalnız masaüstünde koşar. Android'de `data_dir()` = `filesDir` ve uygulama adı
         içermiyor; üstelik paket kimliği değiştiği için eski verinin durduğu dizin yeni
         uygulamaya KAPALI (bkz. Faz 5 notu).
      2. Yeni dizin YOKSA ya da BOŞSA ve eski dizin varsa: `os.rename` (aynı birim,
         atomik, bedava). Yeni dizinde zaten veri varsa HİÇBİR ŞEY yapılmaz.
      3. Hiçbir şey SİLİNMEZ. `OSError` (kilit, salt-okunur, farklı birim) yutulur ve
         `errlog`'a yazılır — bir göç hatası uygulamayı açılamaz hâle getirmemeli.
      4. `~/.config/lumeo/credentials.env` → `~/.config/kromis/credentials.env` aynı üç
         kuralla. `rename` kip bitlerini korur (0o700/0o600).
* [ ] Bekçi testleri (`tests/test_paths.py`): eski dizin taşınır · yeni dizin doluysa
      dokunulmaz · eski dizin yokken sessiz · Android dalında hiç koşmaz · iki kez
      çağrılınca idempotent · `OSError` yutulur.
* [ ] Mevcut yol testlerini güncelle: `tests/test_paths.py:38,46,56,69,175`

## Faz 3 — Çekirdek Python katmanı ✅ UYGULANDI (2026-09-10)

* [ ] `app.py:1` başlık yorumu + `app.py:111` `FastAPI(title="Kromis Studio")`
* [ ] `desktop.py:57` `WINDOW_TITLE = "Kromis Studio"`; ayrıca `:20`, `:229`, `:268-271`, `:478`
* [ ] `guncelleme.py` → `DEPO = "Zenginby/kromis"`
* [ ] `winclr.py:3,9,35,103,244` (yorumlar + `Kromis.exe.config` atıfları)
* [ ] `backup.py:4`, `azure_client.py:4`, `netguard.py:22` (yol yorumları)
* [ ] `tests/test_desktop.py:441`, `tests/test_index.py:15`, `tests/test_prefs.py:217`

## Faz 4 — Ön yüz ✅ UYGULANDI (2026-09-10)

* [ ] `static/index.html:11` `<title>Kromis Studio</title>` + GUNCELLEME.md bağlantısı
* [ ] `static/core.js:1` başlık, `:2032` `window.KromisIndirme`
* [ ] `static/favicon.svg:3` yorum · `static/{assets,chat,folders,palette,settings,viewer}.js` başlıkları
* [ ] **Çiftin öteki yarısı:** `MainActivity.kt:606` `KOPRU_ADI = "KromisIndirme"`.
      Bekçisi `tests/test_mobile.py:736` — ayrışırsa telefonda indirme SESSİZCE hiç olmaz.

## Faz 5 — Android: paket kimliği + iç adlar ✅ UYGULANDI (2026-09-10)

> **Bilinçli olarak ERTELENEN tek madde:** `outputFileName` (`lumeo-android-arm64-*.apk`).
> O ad üç platformun yayın varlığı adıyla TEK küme yaşıyor (`release_manifest.py`
> → README tablosu → GUNCELLEME tablosu → `_paket-android.yml`, mandalı
> `tests/test_release_manifest.py`); yalnız Android'i çevirmek yayına karışık
> isimli bir küme sokardı (`kromis-android` + `lumeo-macOS` + `lumeo-windows`).
> Faz 7 ile birlikte, tek seferde çevrilecek.
>
> **Yerelde DOĞRULANAMAYAN:** Gradle/Kotlin derlemesi. Bu makinede Android SDK
> + NDK yok; paket taşımasının gerçekten derlendiğini ancak `_paket-android.yml`
> kanıtlar. Yerelde koşan mandallar kaynak düzeyinde tutuyor
> (`test_android_packaging`, `test_android_geri`, `test_mobile`, 2302 test yeşil).

* [ ] `android/settings.gradle` → `rootProject.name = "kromis-android"`
* [ ] `build.gradle`: `namespace` + `applicationId` = `com.zenginby.kromis`;
      `outputFileName = "kromis-android-arm64-${variant.buildType.name}.apk"`
* [ ] Kaynakları taşı: `android/app/src/main/java/` altındaki eski paket dizini →
      `android/app/src/main/java/com/zenginby/kromis/`; beş dosyada `package` bildirimi.
      `AndroidManifest.xml` göreli ad kullanıyor (`.MainActivity`, `.ServerService`,
      `.StudioApplication`) ve `BuildConfig` aynı paketten çözülüyor — ikisi de
      kendiliğinden düzeliyor, dokunma.
* [ ] `proguard-rules.pro:10` → `-keep class com.zenginby.kromis.** { *; }`
* [ ] `strings.xml`: `app_name` = `Kromis Studio`, `bildirim_basligi` = `Kromis Studio
      çalışıyor`, ve **`sunucu_baslatilamadi_detay`** — "lütfen bu dosyayı kuruma iletin"
      yeni sahiplikle uyumlu metne döner (karar (c)). Kullanıcıya görünen son eski-kimlik izi.
* [ ] `Downloader.kt:42` → `ALT_KLASOR = "Kromis"`
* [ ] İç adlar (karar (b)): `gis_session` → `kromis_session` (`android_main.py:37` **VE**
      `MainActivity.kt:598`), `gis_sunucu` → `kromis_sunucu` (`ServerService.kt:93`),
      `gis-baslatici` → `kromis-baslatici` (`MainActivity.kt:129`), `gis-resources` →
      `kromis-resources` (`build.gradle:130,206`), `-PgisBuildPython` →
      `-PkromisBuildPython` (`build.gradle:70,72,73` + `_paket-android.yml:209` +
      `docs/android/mimari.md:111` + **`tests/test_python_surumu.py:54` regex'i**),
      `GIS_ALLOW_OLD_PYTHON` → `KROMIS_ALLOW_OLD_PYTHON` (`tests/conftest.py:45`
      sabiti + `:107` yönlendirme metni; sabit üzerinden okunuyor, tek dosya).
* [ ] **YENİ BEKÇİ:** çerez adının iki dilde eşleştiğini ölçen test. Bugün bunu tutan
      hiçbir şey yok — `tests/test_android_main.py` sabiti kullanıyor, literali değil.
      Tek taraf değişirse oturum kapısı her isteği reddeder ve bu YALNIZ telefonda görünür.
      Desen `tests/test_android_apk_name.py`'nin aynısı: `MainActivity.kt`'yi regex'le oku,
      `android_main.SESSION_COOKIE` ile karşılaştır.
* [ ] `ic_launcher_foreground.xml:2` "Lumeo diyafram işareti" yorumu

> **Kullanıcı etkisi — belgelenmesi ZORUNLU:** `applicationId` değiştiği için (anahtar da
> değiştiği için ayrıca) yeni APK telefondaki Lumeo'nun üzerine yazmaz, YAN YANA kurulur.
> Eski uygulamanın app-private verisi (`credentials.env` dahil) yeni uygulamaya geçmez ve
> okunamaz; kaldırma onu siler. `Pictures/Lumeo/` altındaki üretilmiş görseller yerinde
> kalır. Faz 8 bunu KURULUM.md + GUNCELLEME.md'ye yazıyor.

## Faz 6 — Masaüstü paketleme + marka varlıkları ✅ UYGULANDI (2026-09-10)

* [ ] **`gpt-image-studio.spec` → `kromis.spec`** (karar (b)). Atıflardan ikisi SESSİZ
      kırılma riski taşıyor:
      * **`.github/workflows/ci.yml:198`** — paketleme kapısının regex'i dosya adını
        LİTERAL taşıyor (`^(gpt-image-studio\.spec|build\.sh|…)`). Güncellenmezse spec'e
        dokunan bir PR paketleme koşmadan geçer. Bekçisi
        `tests/test_ci_paketleme_kapisi.py:301` (sentetik diff'le kapıyı gerçekten
        koşturuyor) — o parametre de yeni ada döner.
      * `build.sh:47`, `build.ps1:5,93` — çağıran taraf.
      * Yorum atıfları: `version.py:4,16` · `catalog.py:23,317` · `chat_client.py:5` ·
        `chat_providers.py:30` · `providers.py:49` · `requirements-dev.txt:27` ·
        `tools/__init__.py:9` · `tools/make_legacy_fixtures.py:12` ·
        `android/app/build.gradle` (pip yorumu) · `_paket-windows.yml:259` · `ci.yml:172`
* [ ] `kromis.spec` içeriği — **`APP_NAME` diye bir değişken YOK**, ad birden çok literal:
      `name='Kromis'` (EXE ve COLLECT), `name='Kromis.app'`, `_exe_icon` →
      `branding/kromis.ico`, `_icns_path` → `branding/kromis.icns`,
      `bundle_identifier='com.zenginby.kromis'`, ve VERSIONINFO: `CompanyName` →
      **`Zenginby`** (karar (c); bugün `eski kurum adı`), `FileDescription`/`InternalName` →
      `Kromis`, `OriginalFilename` → `Kromis.exe`, `ProductName` → `Kromis Studio`.
* [ ] `branding/Lumeo.exe.config` → `branding/Kromis.exe.config`. **Ad exe adıyla BİREBİR
      olmak zorunda** (CLR `<exe>.config` arıyor); çifti `build.ps1:110` ve
      `_paket-windows.yml:192`. Bekçileri `tests/test_windows_acilis.py:31,110,116,124` ve
      `tests/test_paket_icerik_listesi.py` (workflow'un ADA GÖRE aradığı dosyaların depoda
      gerçekten durduğunu ölçüyor).
* [ ] `branding/lumeo-mark.svg`, `lumeo-icon-square.svg`, `lumeo.ico`, `lumeo.iconset/` →
      `kromis.*`; `tools/render_brand_assets.py:5,6,18,19,48,53,66,67`; `ci.yml:186`
      yorumundaki `branding/lumeo.ico` atfı; `tests/test_ci_paketleme_kapisi.py:311`.
      **NOT:** bu bir yeniden ADLANDIRMA, yeniden tasarım DEĞİL — dosyaların içindeki Lumeo
      diyafram geometrisi olduğu gibi kalıyor. Yeni bir marka işareti isteniyorsa ayrı bir
      iş; kaynak SVG'ler değişince `.ico`/`.iconset` `tools/render_brand_assets.py` ile
      yeniden üretilir ve `tests/test_logo.py` altın kopyaları güncellenir.
* [ ] `build.sh:2,11,12,44` (`dist/Kromis.app`, `dist/Kromis.zip`, iconset yolu)
* [ ] `build.ps1:1,28,108,110` (`$AppName = 'Kromis'`)
* [ ] `LICENSE:3` → `Copyright (c) 2026 Zenginby` (karar (c))
* [ ] `static/favicon.svg`, `docs/flow-ui/assets/brand/*` — marka varlıkları (görsel içerik
      değişmiyorsa yalnız yorum/ad hizası)

## Faz 7 — CI/CD ve yayın hattı ✅ UYGULANDI (2026-09-10)

* [ ] `release_manifest.py`: `kromis-macOS-arm64.zip`, `kromis-windows-x64.zip`,
      `kromis-android-arm64.apk` (+ `dist-lumeo-…` ara adına dair yorum)
* [ ] `_paket-android.yml`: aranan APK yolu, `cp` hedefi, `$RUNNER_TEMP/gis.keystore` →
      `kromis.keystore` (`:198,199,205`)
* [ ] `_paket-macos.yml`: `dist/Kromis.app`, `Contents/MacOS/Kromis` (lipo), **ara ad
      `dist/Kromis.zip`** (`:77,78,99,137,138`)
* [ ] `_paket-windows.yml`: **ara ad `dist\Kromis-windows.zip` (`:109` ve `:291`)**,
      `*/Kromis.exe` (`:145`), `*/Kromis.exe.config` (`:192,194`), `:248` yayın adı, ve
      **`:229` CompanyName kapısı** — hex diziyle yazılmış `eski kurum adı` yerine `Zenginby`
      (ASCII olduğu için hex kaçışına artık gerek yok; kapının NEDEN'i yorumda kalmalı)
* [ ] `ci.yml:172,186,198` (yukarıda) · `release.yml` yorum atıfları
* [ ] `tests/test_ci_varlik_saklama.py:15` (`lumeo-*` → `kromis-*`, yorum)

## Faz 8 — Belgeler ✅ UYGULANDI (2026-09-10)

* [ ] `README.md` (indirme tablosu + rozetler), `GUNCELLEME.md` (**H1: `# Kromis Studio —
      Güncelleme (macOS, Windows ve Android)`** + sistem/dosya tablosu), `KURULUM.md`,
      `CLAUDE.md`
* [ ] **Göç notu** (yeni bölüm, KURULUM.md + GUNCELLEME.md): masaüstünde veri
      kendiliğinden taşınıyor (Faz 2), eski `Lumeo` kurulum klasörü elle silinebilir;
      **Android'de eski Lumeo elle kaldırılmalı**, kaldırma o uygulamanın verisini siler,
      `Pictures/Lumeo` yerinde kalır.
* [ ] `docs/android/mimari.md`: paket adı, `KROMIS_ANDROID_*` değişkenleri,
      `-PkromisBuildPython`, keystore komutu; parmak izi bölümü İKİYE ayrılıyor —
      "v0.15.0'a kadarki anahtar (tarihsel)" + "yeni anahtar" (Faz 9'da doldurulacak)
* [ ] `docs/yayin-hatti.md`, `docs/android/pydantic-karari.md`,
      `bundled/prompts/prompt-yonetmeni.md` içindeki marka örnekleri
* [ ] `tools/surum_karari.py:32` örnek commit metni

## Faz 9 — Bekçi testleri (eski planın en eksik yeriydi) ✅ UYGULANDI (2026-09-10)

Eski plan altı test sayıyordu; gerçek liste bu. **`tests/test_depo_adresi.py` en
tehlikelisi:** kalıbı `github\.com/([...]+)/gpt-image-studio` — depo adı bekçinin İÇİNE
gömülü. Güncellenmezse kalıp hiçbir şey bulamaz ve tek-kaynak bekçisi tümden kör kalır
(kendi öz-bekçisi kırmızıya düşerek haber verir, ama düzeltilecek olan kalıptır).

* [ ] `tests/test_depo_adresi.py` — kalıptaki depo adı (**eski planda hiç yoktu**)
* [ ] `tests/test_android_apk_name.py:26` — `_APK` literali
* [ ] `tests/test_paths.py` — yollar + YENİ göç testleri
* [ ] `tests/test_release_manifest.py:328` · `tests/test_index.py:15` ·
      `tests/test_desktop.py:441` · `tests/test_windows_acilis.py:31,110,116,124`
* [ ] `tests/test_mobile.py:736` — `KromisIndirme` sözleşmesi
* [ ] **`tests/test_android_geri.py:20` ve `tests/test_mobile.py:40`** — Kotlin
      Kotlin kaynak yolunu eski paket adının parçalarından kuruyorlar;
      paket taşınınca ikisi de dosyayı bulamaz (eski planda YOKTU)
* [ ] `tests/test_ci_paketleme_kapisi.py:190,301,311,312` — spec adı + `branding/kromis.ico`
* [ ] `tests/test_python_surumu.py:54` — `PkromisBuildPython` regex'i
* [ ] `tests/test_paket_icerik_listesi.py` — ADA GÖRE aranan dosyalar
* [ ] `tests/test_prefs.py:217` · `tests/test_winclr.py:296` · `tests/test_surum_yaz.py:69` ·
      `tests/test_syntax_warnings.py:143` · `tests/test_version.py:56` (`\K` tuzağı!)
* [ ] YENİ: oturum çerezi çift-dil bekçisi (Faz 5)
* [ ] `python tools/graf_uret.py && python tools/graf_uret.py --kontrol`

## Faz 10 — Doğrulama ve yayın

* [x] `python -m pytest tests/ -q` — tam takım yeşil (2359/1, `main` birleşmesinden sonra)
* [x] `release.yml`'i `workflow_dispatch` + kuru prova ile daldan koştur — koşu
      34503743056, `surum=0.17.3`, beş iş de yeşil; dal kapısı ve taslak kapısı
      tasarlandığı gibi çalıştı (sürüm commit'i atılmadı, yayın oluşmadı)
* [x] **`İmzayı doğrula` adımının ATLANMADIĞINI** gör — 2. koşuda (34505244509)
      KOŞTU; 1. koşuda atlanmıştı

  > **Ölçüm — 2026-09-10, koşu 34503743056.** `gh secret list` dördünü de
  > gösteriyordu ve `ANDROID_KEYSTORE_PASSWORD` koşuda `***` olarak çözüldü — yani
  > `secrets: inherit` çalışıyor. Buna rağmen `KEYSTORE_B64` BOŞ geldi: sır VAR,
  > değeri boş. Muhtemel sebep, `base64` çıktısı boşken (dosya bulunamadığında
  > `base64` stderr'e yazar, stdout boş kalır) borunun `gh secret set`e boş girdi
  > vermesi. İki ders: (1) `gh secret list`te görünmek değerin dolu olduğunu
  > KANITLAMIYOR — tek güvenilir işaret `İmzayı doğrula`nın koşması; (2) adımın
  > "sır yok" metni yanlış yere baktırıyordu, "tanımlı DEĞİL ya da BOŞ" olarak
  > düzeltildi ve özete `wc -c` doğrulaması eklendi.
* [x] `apksigner verify --print-certs` çıktısındaki yeni DN + SHA-256 + SHA-1'i
      `docs/android/mimari.md`'nin yeni tablosuna yaz (aynı PR'da) — iki tablo
      birden duruyor: geçerli anahtar ve v0.17.2'ye kadarki tarihsel anahtar
* [x] Windows: zip'i indirip `Kromis.exe --onyukleme-denetimi` — gerçek makinede,
      gerçek indirilmiş paketle: dört kademe de GEÇTİ (`import clr` → AddReference
      → winforms → `guilib.initialize()`, renderer=edgechromium), sürüm 0.17.3

  > **MOTW yarısı yerelde ÖLÇÜLMEDİ, CI'da ölçüldü.** Yerel raporda
  > `indirme işareti : yok` çıktı — zip ya *Engellemeyi kaldır* ile ya da
  > damgayı yaymayan bir araçla (7-Zip, `Expand-Archive`) açılmış. Aynı ikili
  > için `_paket-windows.yml`'in kapısı MOTW'li senaryoyu koşuturuyor ve DAHA
  > SIKI koşuturuyor: 235/235 dosyaya `Zone.Identifier` basıyor (Gezgin yalnız
  > çıkardığı dosyalara basıyor), `winclr` 106 DLL'den damgayı kaldırıyor, çıkış
  > kodu 0. Yani MOTW kapsamı var; eksik olan yalnız "bu makinede" olması.

  > **Bulunan belge kusuru — düzeltildi.** Kullanıcı denetimi koşturdu ve
  > "dosya oluşmadı" dedi; dosya baştan yazılmıştı. İki sebep birden:
  > (1) `KURULUM.md` "PowerShell penceresi aç" diyip arasından `%LOCALAPPDATA%`
  > yazımı veriyordu — o yazım cmd/Gezgin için doğru, PowerShell onu
  > genişletmez; (2) paket `console=False` olduğu için kabuk exe'yi BEKLEMEZ,
  > komut hemen döner ve dosya bir iki saniye sonra oluşur. İkisi de belgeye
  > yazıldı; `Start-Process -PassThru` + `WaitForExit` + çıkış kodu tablosu
  > verildi (CI kapısı zaten bu sebeple `& $exe` kullanmıyor).
* [ ] Android: eski kurulu bir cihaza yeni APK'yı kur — yan yana kurulum ve göç
      notunun doğruluğu ölçülür
* [ ] Masaüstünde göç: eski veri dizini duran bir makinede yeni sürümü aç;
      kütüphane ve API anahtarlarının yerinde olduğunu gör

> **SIRA DÜZELTMESİ — son üç madde kuru provayla YAPILAMAZ.** Paketler artık
> Actions varlığı olarak yüklenmiyor, doğrudan taslak yayına yazılıyor
> (`release.yml`'in "TASLAK YAYIN" gerekçesi: 2026-08-28'de Actions varlık
> kotası dolup üç paket de teslim edilemedi) ve kuru provada taslak
> AÇILMIYOR — yani indirilebilir bir paket yok. Parmak izi ölçümü kuru
> provayla yapılabildi çünkü `apksigner` çıktısı KOŞU KAYDINDA duruyor;
> cihaz denetimleri için gerçek yayının varlıkları gerekiyor. Windows MOTW
> senaryosu için bu zaten daha doğru: o kapı gerçekten İNDİRİLMİŞ bir zip
> istiyor (`KURULUM.md` → Mark-of-the-Web).

## Faz 11 — Depo public'e açılmadan ÖNCE: geçmiş temizliği

**Karar (2026-09-10): depo public olacak.** Bu, `guncelleme.py`'nin yazılı
şartını (anonim `releases/latest`) doğrular ve güncelleme bildirimini
diriltir — o güne kadar özel depoda 404 alarak sessizce ölüydü (ölçüm
modülün docstring'inde).

### Public'e açılma denetimi — 2026-09-10

"Public yapmak bizim açımızdan sorun oluşturur mu" sorusu tahminle değil
ölçümle cevaplandı. Ayrım şu: bir yüzey `git filter-repo` ile temizlenebilir
mi, yoksa GitHub tarafında AYRI bir iş mi?

#### Temiz çıkanlar — ek iş gerekmiyor

| ne arandı | nasıl | sonuç |
| --- | --- | --- |
| sır: OpenAI/GitHub/AWS/Google/Slack anahtarı, JWT, özel anahtar bloğu | ulaşılabilir 2723 nesnenin 1849 metin blobu (her dosyanın her sürümü) tek tek tarandı | isabetlerin TAMAMI test kuklası (`sk-proj-DUMMY…`) ya da yanlış pozitif (`icon_16x16@2x.png` e-posta kalıbına takılıyor) |
| `.env` / `secrets*` dosyası | `git log --all --diff-filter=A` | hiç commit edilmemiş |
| keystore / jks / p12 / pem / crt | aynı tarama | hiç girmemiş — geçmişte anahtar malzemesi YOK |
| lisans ve telif | `LICENSE` MIT (© 2026 Zenginby); `static/fonts/OFL.txt` fontun yanında duruyor (OFL 1.1'in ŞARTI); `gradle-wrapper.jar` Apache-2.0 | dağıtım hakkı yerinde |
| Actions saldırı yüzeyi | `pull_request_target` / `workflow_run` YOK; `github.event.*` yalnız `env:` üzerinden geçiyor (enjeksiyona karşı önerilen kalıp); `permissions: contents: read`; self-hosted runner yok | çatal PR'ı sır alamaz |
| çatal PR'ı CI'da haksız kırmızıya düşer mi | `ci.yml`'de `imza_zorunlu` BİLEREK verilmiyor, gerekçesi orada yazılı | çatal katkısı kapıdan geçebilir |
| yayın notları | 38 yayının gövdesi tarandı | izli not: 0 |

> **Yan kazanç — kalkacak bir kısıt.** Public depoda standart runner'lar
> ücretsiz. 2026-08-28'de Actions varlık kotasını dolduran birikim ve "macOS
> dakikası 10x sayılıyor" maliyet kararı (`ci.yml`'deki yol süzgeci,
> paketlerin doğrudan taslak yayına yazması) bu yüzden vardı; public'e
> geçtikten sonra o GEREKÇE geçersiz. Bu Faz'ın işi değil, ama kararı yeniden
> açmanın yolu artık var. Ayrıca secret scanning ve Dependabot uyarıları
> public depoda ücretsiz açılıyor.

#### A) Git geçmişi — `filter-repo` çözüyor

| iz | dosya içeriği | commit mesajı | dosya YOLU |
| --- | --- | --- | --- |
| gerçek Azure ana bilgisayarı | 10 commit | 1 | — |
| gerçek yerel kullanıcı adı | 8 | 2 | — |
| eski kurumun alan adı (eski `applicationId`) | 9 | 2 | 5 Kotlin dosyası |
| eski hesap/depo adı | 20 | 5 | — |

Sayılar planın ilk yazımındaki 9/7/8/19'dan birer fazla: PR #75'in birleşmesi
her ize bir commit daha ekledi — bir dizeyi SİLEN commit de o dizeye "dokunan"
commit'tir ve `git log -S` onu sayar.

**Planın ilk hâli üç yerde yetersizdi; düzeltildi:**

1. **`--replace-text` YETMEZ.** Commit ÜSTVERİSİ kimliği taşıyor ve üstveri
   dosya içeriği değil. Ölçüldü: 103 yazar + 96 committer commit'i eski kurum
   adıyla ve o kurumun alan adındaki GERÇEK bir posta adresiyle, 31+7 commit
   eski hesap adıyla, 1 commit bir ÜNİVERSİTE e-posta adresiyle (kişisel
   veri), 2 commit ayrı bir kişisel gmail ile imzalı. Bunlar ancak `--mailmap`
   ile taşınıyor. Mesajlar için de ayrıca `--replace-message` gerekiyor —
   `--replace-text` mesajlara dokunmuyor.
2. **`Lumeo` karşılık tablosuna GİRMEMELİ.** Plan "karşılık tablosu çalışma
   ağacındakinin aynısı olacak" diyordu; bu YANLIŞ olurdu. `paths.py:32`
   `OLD_APP_NAME = "Lumeo"` ve göç işlevi bu dizeye BAĞLI, bekçisi
   `tests/test_paths.py`'de 11 geçiş. Blanket bir karşılık HEAD'i de yeniden
   yazar ve v0.15.0'dan gelen kullanıcının verisini bulan kodu bozar. Kaldı ki
   `Lumeo` bir gizlilik sorunu değil: eski ÜRÜN adı, kimse değil. Geçmişteki
   14 `branding/lumeo*` yolu da aynı sebeple duruyor.
3. **Yolları içerikten ayrı düşünmek gerekiyor.** `--replace-text` yalnız
   içeriğe dokunuyor, `git log --stat` ise YOLLARI gösteriyor: eski paket
   dizini 5 Kotlin dosyasının yolunda yazılı. `--path-rename` şart.

**Karşılık tablosu nerede duruyor.** Tablonun KENDİSİ harfleri taşıdığı için
depoya girmiyor — keystore ile aynı gerekçe. Depo dışında tutuldu; içeriği
tarif olarak şu: gerçek Azure ana bilgisayarı → `ai-ornek-swedencentral`
(çalışma ağacında kullanılanın aynısı), eski kurum alan adı → `zenginby`,
gerçek yerel kullanıcı adı → `kullanici`, eski hesap adı → `Zenginby`; artı
eski Kotlin paket dizini için bir `--path-rename` ve altı girdilik bir
`--mailmap` (bütün insan commit'leri hesabın GitHub `users.noreply` adresine
toplanıyor: katkı grafiği korunuyor, gerçek posta adresi yayımlanmıyor).

#### B) GitHub tarafı — `filter-repo` DOKUNAMAZ

Bu tabloyu kaçırmak, geçmişi temizleyip "bitti" demek olurdu.

| yüzey | ölçüm | neden git dışı |
| --- | --- | --- |
| **45 uzak dal** | `git ls-remote --heads` | yalnız `main` yeniden yazılırsa kalan 44 dal eski commit'leri REFERANSLA canlı tutar (SHA ile değil, dalla) — yeniden yazma hiçbir şey ifade etmez. Çözüm: `filter-repo` hepsini aynı geçişte yazıyor, hepsi gönderiliyor. |
| **76 PR'ın başlık/gövdesi** | eski hesap adı 9 PR'da (#75, 40, 36, 34, 33, 32, 31, 30, 2), eski kurum alan adı 3'te (#75, #35, #31), yerel kullanıcı adı 1'de (#75), Azure kaynağı 2'de (#75, #9) | PR gövdesi git nesnesi değil, GitHub verisi; ancak `gh api PATCH` ile tek tek düzenlenir |
| **201 Actions koşu günlüğü** | ölçüldü: 2026-09-09 Yayın koşusunun günlüğünde eski `applicationId`'yi yazan `aapt` satırı duruyor | günlükler public okuma yetkisiyle görünür ve DÜZENLENEMEZ; yalnız koşunun tamamı silinebilir |
| **38 yayın ve varlıkları** | yayın notları temiz (0 iz); ama v0.17.2 ve öncesinin APK'ları içlerinde eski `applicationId`'yi ve eski sertifika DN'ini taşıyor | varlık içeriği değiştirilemez: yayın ya silinir ya olduğu gibi kalır |
| 76 PR'ın inceleme yorumları | sayılmadı | aynı sınıf — GitHub verisi, git değil |

### Sıra ŞART

1. [x] PR #75 `main`'e girsin (geçmiş yeniden yazılmadan ÖNCE — sonra yazılsa
       PR'ın commit'leri geçersiz olurdu). #76 da girdi.
2. [x] Bu belgenin harfleri çıkarılsın (yukarıdaki DÜZELTME). Yan faydası
       ölçülebilir bir güvence: HEAD artık hiçbir hassas dize taşımadığı için
       yeniden yazma HEAD'in AĞACINI DEĞİŞTİRMEMEK zorunda — "yeniden
       yazılmış HEAD ağacı == özgün HEAD ağacı" iddiası, karşılık tablosunun
       kaçak bir eşleşme yapmadığının kanıtı oluyor.
3. [ ] Geçmiş yeniden yazılsın: `--replace-text` + `--replace-message` +
       `--mailmap` + `--path-rename`, 45 dalın ve 38 tag'in TAMAMI, taze bir
       klonda; sonra `--force-with-lease` ile gönderilsin.
4. [ ] Aynı tarama DÖRDÜNÜ DE 0 demeli — içerikte, mesajda, yolda ve
       yazar/committer üstverisinde.
5. [ ] GitHub tarafı (B tablosu) için karar uygulanmalı: PR gövdeleri,
       Actions günlükleri, eski yayınlar.
6. [ ] Görünürlük public'e alınsın (**kullanıcı işi** — depo ayarı).
7. [ ] Anonim uç nokta ölçülsün: `curl` 200 demeli; sonra uygulamada
       güncelleme bildiriminin gerçekten göründüğü görülsin.

> **Faz 10'un cihaz denetimleri bu sırayı BEKLETMİYOR.** Planın ilk hâli
> onları 3. adımın önüne koymuştu; ölçünce bağımlılık olmadığı görüldü:
> v0.17.3'ün varlıkları yayında duruyor ve geçmişi yeniden yazmak yayın
> varlıklarına dokunmuyor. Tag'ler yeni SHA'lara taşınıyor, dosyalar aynı
> kalıyor.

> **Uyarı — zorla gönderme her şeyi silmiyor.** Force-push'tan sonra eski
> commit'ler ulaşılamaz olur ama GitHub onları bir süre DOĞRUDAN SHA ile
> sunmaya devam ediyor (GC'ye kadar). Tam güvence isteniyorsa yol, temiz
> geçmişi YENİ bir depoya açmak ve eskisini özel arşiv olarak bırakmak —
> karşılığı PR geçmişinin, yayın/tag tarihinin ve yıldız/izleyici sayısının
> geride kalması.
