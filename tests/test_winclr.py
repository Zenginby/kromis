"""winclr — .NET köprüsü önyükleme denetiminin mandalı.

`tests/test_winsec.py`'nin TAMAMI Linux'ta atlanıyor (DACL yalnız Windows'ta
var). Burası öyle DEĞİL ve sebebi ölçülebilir: NTFS'in "indirme işareti"
akışı `yol + ":Zone.Identifier"` diye adresleniyor, Linux'ta bu yalnızca iki
noktalı bir dosya adı. Yani tarama, silme, rapor ve eşik mantığı GERÇEK
dosyalarla burada koşuyor; Windows'a kalan tek şey akışın gerçekten bir NTFS
akışı olduğu ve kayıt defterinin okunduğu.

O iki Windows testi CI'da gerçekten koşuyor: `build.ps1:82` paketleme sırasında
tam pytest takımını Windows yorumlayıcısıyla çalıştırıyor.
"""
from __future__ import annotations

import os

import pytest

import winclr


def _paket(kok, *parcalar: str, icerik: bytes = b"MZ") -> str:
    """Sahte paket ağacında bir dosya doğurur; yolunu döner."""
    yol = os.path.join(str(kok), *parcalar)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "wb") as f:
        f.write(icerik)
    return yol


def _isaretle(yol: str) -> None:
    """Dosyaya "internetten indi" akışını iliştirir (Linux'ta: yandaki dosya)."""
    with open(winclr.ads_yolu(yol), "w", encoding="utf-8") as f:
        f.write("[ZoneTransfer]\nZoneId=3\n")


# --- saf yardımcılar --------------------------------------------------------

def test_the_zone_marker_is_addressed_as_a_stream_beside_the_file():
    """Akış adı yola EKLENİYOR, ayrı bir dosya adı olarak kurulmuyor.

    Bu satır `Unblock-File`'ın yaptığı şeyin birebir karşılığı; bozulursa
    aşağıdaki bütün testler yanlış dosyaya bakar ve sessizce yeşil kalır.
    """
    assert winclr.ads_yolu(r"C:\x\Python.Runtime.dll") == \
        r"C:\x\Python.Runtime.dll:Zone.Identifier"


def test_a_file_without_a_marker_is_reported_as_clean(tmp_path):
    yol = _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")
    assert not winclr.zone_isareti_var_mi(yol)


def test_removing_the_zone_marker_leaves_the_dll_bytes_untouched(tmp_path):
    """Silinen şey akış; dosyanın KENDİSİ bir bayt bile değişmemeli."""
    yol = _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll",
                 icerik=b"MZ\x90\x00PAKET")
    _isaretle(yol)
    assert winclr.zone_isareti_var_mi(yol)

    assert winclr.zone_isaretini_kaldir(yol) is None

    assert not winclr.zone_isareti_var_mi(yol)
    with open(yol, "rb") as f:
        assert f.read() == b"MZ\x90\x00PAKET"


def test_removing_an_absent_marker_is_not_an_error(tmp_path):
    """İşaretsiz dosya olağan hâl — "yapacak bir şey yok" hata değildir."""
    yol = _paket(tmp_path, "webview", "lib", "WebBrowserInterop.x64.dll")
    assert winclr.zone_isaretini_kaldir(yol) is None


def test_removal_reports_the_error_instead_of_raising(tmp_path, monkeypatch):
    """Salt-okunur kurulum dizini bir ÇÖKME değil, bir BULGUDUR.

    `chmod` ile kurulamıyor: testler konteynerde root olarak koşuyor ve root
    salt-okunur dosyayı da siler — kurulum sessizce anlamsızlaşırdı. Bu
    yüzden hatanın kendisi enjekte ediliyor.
    """
    yol = _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")
    _isaretle(yol)

    def _reddet(_yol):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(winclr.os, "remove", _reddet)

    hata = winclr.zone_isaretini_kaldir(yol)
    assert hata is not None
    assert "PermissionError" in hata


# --- tarama -----------------------------------------------------------------

def test_only_the_three_dotnet_directories_are_scanned(tmp_path):
    """Kapsam dar TUTULUYOR — gerekçe winclr modül başlığında."""
    beklenen = {
        _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll"),
        _paket(tmp_path, "clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll"),
        _paket(tmp_path, "webview", "lib", "WebBrowserInterop.x64.dll"),
    }
    # Kapsam DIŞI kalması gerekenler: sıradan bir uzantı modülü, bir veri
    # dosyası ve exe'nin kendisi.
    _paket(tmp_path, "_ctypes.pyd")
    _paket(tmp_path, "python314.dll")
    _paket(tmp_path, "static", "core.js")

    assert set(winclr.izlenen_dosyalar(str(tmp_path))) == beklenen


def test_the_scan_survives_a_missing_tree(tmp_path):
    """Paket yerleşimi PyInstaller'ın meselesi; eksik dizin çökme sebebi değil."""
    assert winclr.izlenen_dosyalar(str(tmp_path / "boyle-bir-yer-yok")) == []


def test_the_scan_ignores_files_that_are_not_assemblies(tmp_path):
    _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.xml")
    _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.deps.json")
    dll = _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")

    assert winclr.izlenen_dosyalar(str(tmp_path)) == [dll]


# --- .NET Framework eşiği ---------------------------------------------------

def test_an_old_dotnet_framework_is_a_finding(tmp_path):
    """4.7.1 (461308) yetmiyor: netstandard2.0 assembly'si 4.7.2 ile başlıyor."""
    b = winclr.topla(str(tmp_path), oku_net=lambda: 461308)
    assert winclr.kayda_deger(b)
    assert "ESKİ" in winclr.rapor(b)


def test_a_current_dotnet_framework_is_not_a_finding(tmp_path):
    _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")
    b = winclr.topla(str(tmp_path), oku_net=lambda: winclr.ASGARI_NET_RELEASE)
    assert not winclr.kayda_deger(b)


def test_an_unreadable_registry_is_a_finding(tmp_path):
    """Okunamayan sürüm "yeterli" sayılamaz — sessiz varsayım tam da bu kusur."""
    _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")
    b = winclr.topla(str(tmp_path), oku_net=lambda: None)
    assert winclr.kayda_deger(b)
    assert "okunamadı" in winclr.rapor(b)


# --- bulgular ve rapor ------------------------------------------------------

def _saglikli(kok) -> str:
    """İşaretsiz, DLL'i yerinde, .NET'i güncel bir paket ağacı."""
    return _paket(kok, "pythonnet", "runtime", "Python.Runtime.dll")


def test_a_missing_runtime_dll_is_a_finding(tmp_path):
    """DLL'in yokluğu da AYNI "Failed to resolve" mesajını üretiyor —
    ikisini ayırt eden tek şey bu satır."""
    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)
    assert b.dll_boyutu is None
    assert winclr.kayda_deger(b)
    assert "YOK" in winclr.rapor(b)


def test_an_empty_runtime_dll_is_a_finding(tmp_path):
    """0 baytlık dosya "var" sayılırsa kapı boş bir paketi onaylar."""
    _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll", icerik=b"")
    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)
    assert winclr.kayda_deger(b)


def test_the_report_says_nothing_when_there_is_nothing_to_say(tmp_path):
    """HATA.LOG SÖZLEŞMESİ: temiz makinede dosyaya HİÇBİR ŞEY yazılmamalı."""
    _saglikli(tmp_path)
    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)
    assert not winclr.kayda_deger(b)
    assert winclr.rapor(b)          # rapor yine de dolu — filtre `kayda_deger`


def test_the_report_names_every_file_whose_marker_was_removed(tmp_path):
    """"3 dosya" demek yetmez: hangi dosya olduğu teşhisin kendisi."""
    dll = _saglikli(tmp_path)
    clr = _paket(tmp_path, "clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll")
    _isaretle(dll)
    _isaretle(clr)

    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)

    assert len(b.zone_bulunan) == 2
    assert set(b.zone_kaldirilan) == set(b.zone_bulunan)
    assert not b.zone_kaldirilamayan
    metin = winclr.rapor(b)
    assert os.path.join("pythonnet", "runtime", "Python.Runtime.dll") in metin
    assert "kaldırıldı" in metin


def test_a_marker_that_cannot_be_removed_is_reported_as_such(tmp_path, monkeypatch):
    dll = _saglikli(tmp_path)
    _isaretle(dll)
    monkeypatch.setattr(winclr, "zone_isaretini_kaldir", lambda _y: "OSError: kilitli")

    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)

    assert b.zone_bulunan and not b.zone_kaldirilan
    assert b.zone_kaldirilamayan
    metin = winclr.rapor(b)
    assert "KALDIRILAMADI" in metin
    assert "kilitli" in metin


def test_a_marker_nobody_tried_to_remove_is_not_called_a_failure(tmp_path):
    """ÜÇ DURUM, İKİ DEĞİL. `kaldir=False` hiç silme denemiyor; orada
    "KALDIRILAMADI" yazmak olmayan bir izin hatası uydurur ve raporu okuyanı
    — kullanıcının bilgisayarını göremeyen kişiyi — yanlış yere bakmaya
    gönderir. Üstelik o satırı düzeltecek `!` satırı da yok: gerekçe yalnız
    `zone_kaldirilamayan`da tutuluyor ve bu dalda o boş."""
    _isaretle(_saglikli(tmp_path))

    metin = winclr.rapor(winclr.topla(str(tmp_path), kaldir=False,
                                      oku_net=lambda: 533320))

    assert "KALDIRILAMADI" not in metin
    assert "denenmedi" in metin


def test_collecting_without_removal_leaves_the_marker_in_place(tmp_path):
    """`kaldir=False` salt-okuma teşhisi için — dosyaya dokunmamalı."""
    dll = _saglikli(tmp_path)
    _isaretle(dll)

    b = winclr.topla(str(tmp_path), kaldir=False, oku_net=lambda: 533320)

    assert b.zone_bulunan and not b.zone_kaldirilan
    assert winclr.zone_isareti_var_mi(dll)


def test_the_report_paths_are_relative_to_the_package_root(tmp_path):
    """Rapor kullanıcıdan geliyor: mutlak yol kullanıcının adını taşır."""
    dll = _saglikli(tmp_path)
    _isaretle(dll)
    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)
    assert b.zone_bulunan[0] == os.path.join(
        "pythonnet", "runtime", "Python.Runtime.dll")


def test_a_marker_that_was_removed_is_not_worth_an_error_log(tmp_path):
    """ONARILAN İŞARET BULGU DEĞİL. Zip'i Dosya Gezgini ile açmak işaretin
    OLAĞAN sebebi — beklenen durum, arıza değil — ve denetim onu `import clr`
    öncesinde siliyor: uygulama ardından sorunsuz açılıyor. hata.log yaratmak
    kullanıcıya kendi kendine kapanmış bir sorunu bildirtirdi ve KURULUM.md'nin
    "varsa gönder" cümlesini anlamsızlaştırırdı."""
    _isaretle(_saglikli(tmp_path))

    b = winclr.topla(str(tmp_path), oku_net=lambda: 533320)

    assert b.zone_bulunan and set(b.zone_kaldirilan) == set(b.zone_bulunan)
    assert not winclr.kayda_deger(b)


def test_a_marker_still_in_place_is_worth_an_error_log(tmp_path):
    """Ölçüt "işaret var mıydı" değil, "işaret HÂLÂ duruyor mu": .NET
    yüklemesini engelleyen tek şey bu."""
    _isaretle(_saglikli(tmp_path))

    b = winclr.topla(str(tmp_path), kaldir=False, oku_net=lambda: 533320)

    assert winclr.kayda_deger(b)


# --- açılış yolundaki sözleşme ----------------------------------------------

def test_the_boot_step_does_nothing_off_windows(tmp_path, monkeypatch):
    """POSIX'te tam no-op: ne dosya okunur ne rapor üretilir."""
    dll = _saglikli(tmp_path)
    _isaretle(dll)
    monkeypatch.setattr(winclr.sys, "platform", "darwin")

    assert winclr.onyukle(str(tmp_path)) == ""
    assert winclr.zone_isareti_var_mi(dll)      # dokunulmadı


def test_the_boot_step_repairs_a_marked_package_without_shouting(tmp_path,
                                                                 monkeypatch):
    """Onarım GERÇEKTEN oluyor ama sessizce: kullanıcının uygulaması açıldı ve
    ona bildirilecek bir şey kalmadı. Tam döküm `--onyukleme-denetimi`
    kipinde, ayrı dosyada duruyor."""
    dll = _saglikli(tmp_path)
    _isaretle(dll)
    monkeypatch.setattr(winclr.sys, "platform", "win32")
    monkeypatch.setattr(winclr, "_winreg_release", lambda: 533320)

    assert winclr.onyukle(str(tmp_path)) == ""
    assert not winclr.zone_isareti_var_mi(dll)


def test_a_marker_that_survives_the_repair_is_reported(tmp_path, monkeypatch):
    """Silinemeyen işaret bulgudur: uygulama artık `Lumeo.exe.config`'teki
    `loadFromRemoteSources`a kalmıştır ve o da kurtarmadıysa sebebi bilinmeli
    (salt-okunur kurulum dizini, kurumsal politika, kilit)."""
    _isaretle(_saglikli(tmp_path))
    monkeypatch.setattr(winclr.sys, "platform", "win32")
    monkeypatch.setattr(winclr, "_winreg_release", lambda: 533320)
    monkeypatch.setattr(winclr, "zone_isaretini_kaldir", lambda _y: "OSError: kilitli")

    metin = winclr.onyukle(str(tmp_path))

    assert "KALDIRILAMADI" in metin
    assert "kilitli" in metin


def test_the_boot_step_stays_quiet_on_a_healthy_package(tmp_path, monkeypatch):
    _saglikli(tmp_path)
    monkeypatch.setattr(winclr.sys, "platform", "win32")
    monkeypatch.setattr(winclr, "_winreg_release", lambda: 533320)

    assert winclr.onyukle(str(tmp_path)) == ""


def test_the_boot_step_never_raises_even_when_collection_explodes(monkeypatch):
    """Bir ÖNYÜKLEME DENETİMİNİN açılışı engellemesi en kötü sonuç olurdu."""
    monkeypatch.setattr(winclr.sys, "platform", "win32")

    def _patla(*_a, **_k):
        raise RuntimeError("beklenmedik")

    monkeypatch.setattr(winclr, "topla", _patla)

    metin = winclr.onyukle("herhangi")
    assert "çöktü" in metin
    assert "beklenmedik" in metin


# --- yalnız Windows: yukarıdaki varsayımların gerçek NTFS'te bekçisi --------

pytestmark_windows = pytest.mark.skipif(
    not winclr.is_supported(), reason="NTFS akışı ve kayıt defteri yalnız Windows'ta")


@pytestmark_windows
def test_a_real_alternate_data_stream_can_be_created_and_removed(tmp_path):
    """BU TESTİN İŞİ: Linux'taki sekiz testin dayandığı varsayımı doğrulamak.

    Orada `yol + ":Zone.Identifier"` sıradan bir dosya adı; burada gerçek bir
    NTFS akışı. Bu düşerse Linux tarafı aynı anda anlamsızlaşmış demektir —
    çünkü o zaman `Unblock-File`'ın sildiği şeyle bizim sildiğimiz şey aynı
    değildir.
    """
    yol = _paket(tmp_path, "pythonnet", "runtime", "Python.Runtime.dll")
    _isaretle(yol)

    # Akış AYRI bir dosya DEĞİL: dizin listesinde görünmemeli.
    assert os.listdir(os.path.dirname(yol)) == ["Python.Runtime.dll"]
    assert winclr.zone_isareti_var_mi(yol)
    assert winclr.zone_isaretini_kaldir(yol) is None
    assert not winclr.zone_isareti_var_mi(yol)


@pytestmark_windows
def test_the_real_registry_reports_a_supported_dotnet_framework():
    """Derleme makinesinin kendisi eşiği geçiyor mu — paketin tabanı bu."""
    release = winclr.net_release()
    assert release is not None
    assert release >= winclr.ASGARI_NET_RELEASE
