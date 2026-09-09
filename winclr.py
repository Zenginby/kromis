"""winclr — Windows'ta .NET köprüsünün açılış öncesi denetimi ve onarımı.

NEDEN VAR: 2026-09-04'te bir kullanıcı `lumeo-windows-x64.zip`'i indirip
`Downloads` altına açtı ve uygulama HİÇ açılmadı. `hata.log`:

    webview/guilib.py:74 import_winforms -> clr.py:6 -> pythonnet/__init__.py:143
    -> clr_loader/netfx.py:47 _get_callable
    RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize from
      ...\\Lumeo\\_internal\\pythonnet\\runtime\\Python.Runtime.dll

Bu mesaj TEK bir sebebi anlatmıyor; en az dört ayrı kusur onu üretiyor:
işaretli (Mark of the Web) bir DLL, eksik/bozuk bir DLL, .NET Framework'ün
eskiliği, ya da pythonnet'in kendi bağımlılıklarının çözülememesi.

VE HANGİSİ OLDUĞU SÖYLENMİYOR. clr_loader'ın `ClrLoader.dll` shim'i
(`DomainData.GetFunctor`) sırayla `AssemblyName.GetAssemblyName(yol)` →
`domain.Load(...)` → çözülemezse `AssemblyResolve` → `Assembly.LoadFrom(yol)`
yapıyor; `pyclr_get_function` bu adımların HER istisnasını yutup NULL dönüyor
ve shim'in `Print()` fonksiyonu Release derlemede boş gövde (`#if DEBUG`).
Yani üst katmandan gelen tek bilgi yukarıdaki tek satır. Teşhisi üretecek
başka kimse yok — bu modül o yüzden var.

MARK OF THE WEB, EN GÜÇLÜ ADAY. İnternetten inen bir zip Dosya Gezgini ile
açıldığında ÇIKAN HER DOSYAYA `Zone.Identifier` adlı bir alternatif veri akışı
(ADS) yapışıyor. .NET Framework böyle işaretlenmiş bir assembly'yi
`Assembly.LoadFrom` ile yüklemeyi reddedebiliyor (`FileLoadException`).
Kullanıcının yolu tam olarak `C:\\Users\\...\\Downloads\\...` idi ve paket
bugüne dek yalnız YERELDE derlenmiş hâliyle (yani işaretsiz) çalıştırılmıştı.

NEDEN TÜM AĞAÇ TARANMIYOR — üç gerekçe, üçü de ölçülebilir:
  1. İşaret yalnız YÖNETİLEN yüklemeyi (`Assembly.LoadFrom`) engelliyor;
     `.pyd`/`.dll` native yüklemesi (`LoadLibrary`) etkilenmiyor. 200+ dosyada
     işaret silmenin kazancı sıfır.
  2. "Uygulama, indirdiğin her dosyanın güvenlik işaretini siliyor"
     savunulabilir bir cümle değil. `Lumeo.exe`'ye BİLEREK dokunulmuyor:
     SmartScreen kararı kullanıcınındır ve o kapıdan zaten geçmiştir.
  3. Dar liste denetlenebilir; testi bir şey ölçer.
Listenin körlüğü CI'da kapanıyor: `_paket-windows.yml`'deki açılış denetimi
işareti ağacın TAMAMINA basıp exe'yi çalıştırıyor, yani eksik bir dizin
kırmızıya düşer.

POSIX'te bu modülün tamamı no-op: `onyukle` sessizce "" döner. Ama saf
yardımcıları (yol kurma, tarama, rapor) platform bağımsız ve Linux'ta GERÇEK
dosyalarla sınanabiliyor — ADS `yol + ":Zone.Identifier"` diye adresleniyor ve
Linux'ta bu yalnızca iki noktalı bir dosya adı. `winsec.py`'nin testleri
Linux'ta tümüyle atlanıyor; buranınkiler atlanmıyor.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable

# NTFS'te bir dosyaya iliştirilen adlandırılmış akış, yolun sonuna ":ad"
# eklenerek adresleniyor. `Unblock-File`'ın yaptığı şey de tam olarak bu
# akışı silmek.
ZONE_ADS = ":Zone.Identifier"

# .NET assembly'si YÜKLENEN üç dizin (paket kökü = `paths.resource_dir()`,
# frozen'da `_internal`). Gerekçe modül başlığında.
IZLENEN_DIZINLER = ("pythonnet/runtime", "clr_loader/ffi/dlls", "webview/lib")

# pythonnet `__init__.py` bu yolu KENDİ `__file__`inden kuruyor; hata
# mesajındaki yol da bu. Varlığı ayrıca denetleniyor çünkü yokluğu da aynı
# "Failed to resolve" mesajını üretir ve ikisi tamamen farklı kusurlar.
RUNTIME_DLL_PARCALARI = ("pythonnet", "runtime", "Python.Runtime.dll")

# .NET Framework 4.7.2 = 461808. pythonnet 3.x'in `Python.Runtime.dll`i
# netstandard2.0 hedefliyor ve o, .NET Framework tarafında 4.7.2 ile
# başlıyor — altındaki bir sürümde assembly hiç yüklenmez.
ASGARI_NET_RELEASE = 461808
_NET_ANAHTARI = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"


def is_supported() -> bool:
    """Bu modülün gerçekten bir iş yaptığı platform mu?"""
    return sys.platform == "win32"


def ads_yolu(yol: str) -> str:
    """Dosyanın `Zone.Identifier` akışının yolu. SAF — dosya sistemine bakmaz."""
    return yol + ZONE_ADS


def zone_isareti_var_mi(yol: str) -> bool:
    """Dosyada "internetten indi" işareti duruyor mu? ASLA fırlatmaz."""
    try:
        return os.path.exists(ads_yolu(yol))
    except OSError:
        # Uzun yol, bozuk bağlantı, erişilemeyen paylaşım: bilmiyoruz demek
        # "yok" demekten daha doğru olurdu ama bu fonksiyonun çağrıldığı yerde
        # bilinmezliği taşıyacak bir kanal yok — kaldırma denemesi zaten
        # kendi hatasını rapor ediyor.
        return False


def zone_isaretini_kaldir(yol: str) -> str | None:
    """İşareti siler. Başarı (ya da işaretin hiç olmaması) → None; hata → metin.

    ASLA FIRLATMAZ. Salt-okunur bir kurulum dizininde (ör. `Program Files`,
    kurumsal politika) silme başarısız olur ve bu bir ÇÖKME değil bir
    BULGUDUR: o senaryoyu `Lumeo.exe.config`'teki `loadFromRemoteSources`
    kurtarıyor, çünkü o dosya yazma izni istemiyor.
    """
    try:
        os.remove(ads_yolu(yol))
    except FileNotFoundError:
        return None          # zaten yoktu — yapılacak bir şey de yok
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def runtime_dll_yolu(kok: str) -> str:
    """`Python.Runtime.dll`in paket içindeki tam yolu. SAF."""
    return os.path.join(kok, *RUNTIME_DLL_PARCALARI)


def izlenen_dosyalar(kok: str) -> list[str]:
    """`IZLENEN_DIZINLER` altındaki `.dll` dosyaları; sıralı. ASLA fırlatmaz.

    Olmayan bir dizin sessizce atlanıyor: paketin yerleşimi PyInstaller'ın
    ve hook'ların meselesi ve sürüm sürüm değişebiliyor. Eksik dizin burada
    bir hata değil; asıl eksiklik (`Python.Runtime.dll` yok) ayrıca ölçülüyor.
    """
    bulunan: list[str] = []
    for goreli in IZLENEN_DIZINLER:
        dizin = os.path.join(kok, *goreli.split("/"))
        for taban, _alt, dosyalar in os.walk(dizin):
            for ad in dosyalar:
                if ad.lower().endswith(".dll"):
                    bulunan.append(os.path.join(taban, ad))
    return sorted(bulunan)


def _winreg_release() -> int | None:
    """Kayıt defterinden .NET Framework 4.x `Release` numarası; yoksa None."""
    if not is_supported():
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _NET_ANAHTARI) as anahtar:
            deger, _tur = winreg.QueryValueEx(anahtar, "Release")
        return int(deger)
    except Exception:
        return None


def net_release(*, oku: Callable[[], int | None] | None = None) -> int | None:
    """Kurulu .NET Framework 4.x sürümü (`Release` numarası); okunamazsa None.

    Okuyucu ENJEKTE EDİLEBİLİR — `screencolor.pick(show_sampler=…)` deseninin
    aynısı ve aynı gerekçeyle: kayıt defterine dokunan tek yer
    `_winreg_release`, eşik karşılaştırması ise saf mantık. Böylece "eski
    .NET bir bulgudur" iddiası Linux'ta da ölçülebiliyor; `winsec`'in
    `skipif` duvarı buraya gerekmiyor.
    """
    return (oku or _winreg_release)()


@dataclass(frozen=True)
class Bulgular:
    """Tek bir önyükleme denetiminin sonucu. Rapor bundan TÜRETİLİR."""

    kok: str
    dll_yolu: str
    dll_boyutu: int | None                              # None = yok ya da okunamıyor
    taranan_dosya: int
    zone_bulunan: tuple[str, ...]                       # koke göreli, sıralı
    zone_kaldirilan: tuple[str, ...]
    zone_kaldirilamayan: tuple[tuple[str, str], ...]    # (göreli yol, hata metni)
    net_release: int | None


def _goreli(kok: str, yol: str) -> str:
    """Raporda okunabilirlik için: paket kökünden itibaren yol."""
    try:
        return os.path.relpath(yol, kok)
    except ValueError:
        return yol          # farklı sürücü (Windows) — mutlak yol da iş görür


def topla(kok: str, *, kaldir: bool = True,
          oku_net: Callable[[], int | None] | None = None) -> Bulgular:
    """Denetimi koşturur (ve `kaldir` ise işaretleri siler); bulguları döner.

    `kaldir=False` yalnız testler ve salt-okuma teşhisi için: gerçek açılış
    yolunda işaretin SİLİNMESİ isteniyor, çünkü rapor yazmak uygulamayı
    açmıyor.
    """
    dosyalar = izlenen_dosyalar(kok)
    bulunan: list[str] = []
    kaldirilan: list[str] = []
    kaldirilamayan: list[tuple[str, str]] = []

    for yol in dosyalar:
        if not zone_isareti_var_mi(yol):
            continue
        bulunan.append(_goreli(kok, yol))
        if not kaldir:
            continue
        hata = zone_isaretini_kaldir(yol)
        if hata is None:
            kaldirilan.append(_goreli(kok, yol))
        else:
            kaldirilamayan.append((_goreli(kok, yol), hata))

    dll = runtime_dll_yolu(kok)
    try:
        boyut: int | None = os.path.getsize(dll)
    except OSError:
        boyut = None

    return Bulgular(
        kok=kok,
        dll_yolu=dll,
        dll_boyutu=boyut,
        taranan_dosya=len(dosyalar),
        zone_bulunan=tuple(bulunan),
        zone_kaldirilan=tuple(kaldirilan),
        zone_kaldirilamayan=tuple(kaldirilamayan),
        net_release=net_release(oku=oku_net),
    )


def kayda_deger(b: Bulgular) -> bool:
    """Bu bulgular hata.log'a yazılmayı hak ediyor mu?

    HATA.LOG SÖZLEŞMESİ. KURULUM.md kullanıcıya "`hata.log` dosyasına bak,
    VARSA içeriğini teknik desteğe gönder" diyor — yani o dosyanın varlığı başlı
    başına "kötü haber" demek. Her açılışta bir satır yazmak onu sıradan bir
    günlüğe çevirir ve sözleşmeyi sessizce bozar. Bu yüzden temiz bir
    makinede HİÇBİR ŞEY yazılmıyor; tam rapor yalnız `--onyukleme-denetimi`
    kipinde, ayrı bir dosyaya düşüyor.

    ONARILMIŞ BİR İŞARET DE BULGU DEĞİL. Zip'i Dosya Gezgini ile açmak
    işaretin OLAĞAN sebebi — yani beklenen durum, arıza değil — ve `topla()`
    onu `import clr`'dan önce siliyor: uygulama ardından sorunsuz açılıyor.
    O yolda hata.log yaratmak kullanıcıya kendi kendine kapanmış bir sorunu
    bildirtir ve dosyanın varlığını tam olarak yukarıdaki paragrafın
    reddettiği şeye çevirir. KALAN işaret ise bulgudur: silinemediyse
    (salt-okunur dizin, kilit) uygulama `Lumeo.exe.config`'teki
    `loadFromRemoteSources`a kalmıştır ve o kurtarmadıysa sebebi bilinmeli.
    """
    # Bulunup KALDIRILMAMIŞ olan: hem silme hatası alanlar hem `kaldir=False`
    # ile hiç denenmeyenler. Ölçüt "işaret var mıydı" değil, "işaret HÂLÂ
    # duruyor mu" — .NET yüklemesini engelleyen tek şey bu.
    kalan_isaret = [y for y in b.zone_bulunan if y not in b.zone_kaldirilan]
    return bool(
        kalan_isaret
        # Gereksiz görünüyor ama duruyor: yukarıdaki liste `zone_bulunan`'a
        # dayanıyor ve elle kurulmuş bir `Bulgular`'da (test kurgusu, ileride
        # başka bir çağıran) bir silme hatası o listede olmayabilir. Bir
        # hatayı SESSİZ geçmenin bedeli, bir fazla koşulun bedelinden büyük.
        or b.zone_kaldirilamayan
        or not b.dll_boyutu
        or b.net_release is None
        or b.net_release < ASGARI_NET_RELEASE
    )


def rapor(b: Bulgular) -> str:
    """Bulguların Türkçe, insan-okunur dökümü. SAF; her zaman doludur.

    Okuyucusu iki kişi: hatayı yaşayan kullanıcı (dosyayı olduğu gibi
    gönderiyor) ve onu okuyan geliştirici. Bu yüzden her satır kendi başına
    anlamlı — "3 dosya" değil, hangi dosyalar.
    """
    satirlar = [
        "[.NET köprüsü önyükleme denetimi]",
        f"paket kökü        : {b.kok}",
    ]

    if b.dll_boyutu:
        satirlar.append(f"Python.Runtime.dll: var ({b.dll_boyutu} bayt)")
    else:
        satirlar.append(f"Python.Runtime.dll: YOK ya da okunamıyor — {b.dll_yolu}")

    if b.net_release is None:
        satirlar.append(".NET Framework    : okunamadı (kayıt defteri anahtarı yok?)")
    elif b.net_release < ASGARI_NET_RELEASE:
        satirlar.append(f".NET Framework    : ESKİ (Release={b.net_release}, "
                        f"en az {ASGARI_NET_RELEASE} = 4.7.2 gerekiyor)")
    else:
        satirlar.append(f".NET Framework    : Release={b.net_release}")

    satirlar.append(f"taranan .dll      : {b.taranan_dosya}")
    if not b.zone_bulunan:
        satirlar.append("indirme işareti   : yok")
    else:
        satirlar.append(f"indirme işareti   : {len(b.zone_bulunan)} dosyada bulundu")
        # ÜÇ DURUM, İKİ DEĞİL. `topla(kaldir=False)` (yaptırımlı salt-okuma
        # teşhisi) hiç silme denemiyor; orada "KALDIRILAMADI" yazmak olmayan
        # bir izin hatası uydurur ve raporu okuyan kişiyi — kullanıcının
        # bilgisayarını göremeyen kişiyi — yanlış yere bakmaya gönderir.
        # Üstelik o satırı düzeltecek `!` satırı da yoktur: gerekçe yalnız
        # `zone_kaldirilamayan`da tutuluyor ve o dalda boş.
        kaldirilamayan = {yol for yol, _hata in b.zone_kaldirilamayan}
        for yol in b.zone_bulunan:
            if yol in b.zone_kaldirilan:
                durum = "kaldırıldı"
            elif yol in kaldirilamayan:
                durum = "KALDIRILAMADI"
            else:
                durum = "duruyor (silme denenmedi)"
            satirlar.append(f"  - {yol}: {durum}")
    for yol, hata in b.zone_kaldirilamayan:
        satirlar.append(f"  ! {yol}: {hata}")

    return "\n".join(satirlar)


def onyukle(kok: str) -> str:
    """Açılış yolunun çağırdığı tek fonksiyon. "" = anlatılacak bir şey yok.

    ASLA FIRLATMAZ ve Windows dışında hiçbir şey yapmaz. Çağıran taraf
    (`desktop._run`) dönen metin boşsa hata.log'a dokunmuyor — gerekçe
    `kayda_deger`'de.
    """
    if not is_supported():
        return ""
    try:
        b = topla(kok)
    except Exception:
        # Bir ÖNYÜKLEME DENETİMİNİN açılışı engellemesinden kötü bir sonuç
        # yok. Sözleşme "fırlatmam" diyor; sözleşmeye GÜVENİLMİYOR.
        import traceback
        return "[.NET köprüsü önyükleme denetimi çöktü]\n" + traceback.format_exc()
    return rapor(b) if kayda_deger(b) else ""
