"""Windows'ta dosya izinlerinin POSIX karşılığı: DACL ile "yalnız sahibi".

NEDEN VAR: `credentials.env` Azure API anahtarını tutuyor ve v1.2'den beri
"0600 + atomik yazım" güvencesi altında. Windows'ta `os.chmod`/`os.fchmod`
POSIX bitlerini UYGULAMIYOR — yalnızca salt-okunur bayrağını çeviriyor. Faz 0'da
birebir ölçüldü: `os.fchmod(fd, 0o600)`'dan sonra dosya `0o666` kalıyor
(`assert 438 == 384`). Yani bu modül olmadan Windows sürümü anahtarı, makinedeki
her kullanıcının okuyabildiği bir dosyada tutardı — paketleme düzelse bile
gönderilemezdi.

Windows'taki karşılık DACL: dosyanın kendi erişim listesi. İki şey gerekiyor —
(1) **kalıtımı kes** (`P` bayrağı), yoksa üst dizine sonradan eklenen bir izin
dosyaya da sızar; (2) tek ACE bırak: mevcut kullanıcıya tam erişim.
SYSTEM ve Administrators BİLEREK listede yok: 0600'ün anlamı "yalnız sahibi" ve
yönetici zaten sahipliği devralarak her dosyaya erişebilir — onları listeye
yazmak güvencenin adını zayıflatır, gücünü artırmaz.

NEDEN ctypes, `icacls` DEĞİL:
  • `--windowed` pakette her subprocess bir konsol penceresi çaktırır;
  • `icacls` çıktısı hesap ADLARINI yerelleştirilmiş yazar (Türkçe Windows'ta
    "Yöneticiler") — doğrulama makinenin diline bağlanırdı.
SDDL dizesi (`D:P(A;;FA;;;S-1-5-…)`) dilden bağımsız ve SID tabanlı; hem
uygulama hem testler aynı biçimi okuyor.

⚠️ Ama SDDL dilden bağımsız olsa da **TEMSİLDEN bağımsız değil**: Windows aynı
hesabı geri okurken sayısal SID yerine iki harfli takma ad yazabiliyor
(`LA`, `BA`, `SY`). Bu yüzden SID karşılaştırması metin üzerinde YAPILMAZ,
`_resolve_sid` ile çözülmüş SID üzerinde yapılır — nedeni orada ölçümle yazılı.

POSIX'te bu modül hiçbir şey yapmaz: `restrict_to_current_user` sessizce döner,
çağıran taraf işi `os.chmod`/`os.fchmod` ile zaten yapmış olur.
"""
from __future__ import annotations

import os
import re
import sys

# ACE alanları: (tür;bayraklar;haklar;nesne_guid;kalıtım_guid;SID)
# "FA" = FILE_ALL_ACCESS. Dizinlere "OICI" (object + container inherit) veriliyor
# ki dizin içinde AÇILAN dosyalar da doğar doğmaz yalnız sahibine ait olsun —
# geçici dosyanın yazımdan önceki penceresini kapatan şey bu.
_FILE_ACE_FLAGS = ""
_DIR_ACE_FLAGS = "OICI"

# `D:` ile başlayan DACL dizesinde ACE'lerden önceki bayrak bölümü; "P"
# (SDDL_PROTECTED) kalıtımın kesildiğini söyler.
_DACL_PREFIX = re.compile(r"^D:([A-Z]*)")
_ACE = re.compile(r"\(([^)]*)\)")


def is_supported() -> bool:
    """Bu makinede DACL sıkılaştırması anlamlı mı? (Windows dışında hayır.)"""
    return sys.platform == "win32"


if sys.platform == "win32":  # pragma: no cover - platforma bağlı dal
    import ctypes
    from ctypes import wintypes

    _SDDL_REVISION_1 = 1
    _SE_FILE_OBJECT = 1
    _DACL_SECURITY_INFORMATION = 0x00000004
    _PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
    _TOKEN_QUERY = 0x0008
    _TOKEN_USER = 1

    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _SID_AND_ATTRIBUTES(ctypes.Structure):
        """TOKEN_USER ile aynı yerleşim: tek SID işaretçisi + öznitelikler."""

        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    # İmzalar (`argtypes`) ELLE veriliyor. ctypes imza yokken Python tamsayısını
    # C `int`'e çevirir ve 64-bit'te işaretçiyi 32 bite KIRPAR — çağrı patlamaz,
    # sessizce yanlış adresle çalışır. Bir güvenlik yolunda kabul edilemez.
    # (`LocalFree` imzasız: ona yalnız ctypes işaretçi NESNELERİ geçiyor, onlar
    # imzasız da doğru genişlikte gider.)
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.LocalFree.restype = ctypes.c_void_p

    _advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    _advapi32.OpenProcessToken.restype = wintypes.BOOL

    _advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    _advapi32.GetTokenInformation.restype = wintypes.BOOL

    _advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    _advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

    # Ters yön: SDDL'in SID alanını (sayısal YA DA takma adlı) gerçek SID'e
    # çevirir. `is_owner_only`'nin temsilden bağımsız olmasını sağlayan çağrı;
    # gerekçe modül docstring'inde ("dilden bağımsız, temsilden DEĞİL").
    _advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    _advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL

    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD)]
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = \
        wintypes.BOOL

    _advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
    _advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = \
        wintypes.BOOL

    _advapi32.GetSecurityDescriptorDacl.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    _advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL

    # Bu ikisi BOOL DEĞİL, Win32 hata kodu döndürür (0 = başarı). restype'ı BOOL
    # vermek "başarılı" görünen bir başarısızlık üretirdi.
    _advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    _advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD

    _advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p)]
    _advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD

    def _last_error(func: str) -> OSError:
        return ctypes.WinError(ctypes.get_last_error(), f"{func} başarısız")

    def _current_user_sid() -> str:
        """Süreç jetonundaki kullanıcının SID'i (`S-1-5-21-…`).

        Jetondan okunuyor, `%USERNAME%`'den DEĞİL: ortam değişkeni taklit
        edilebilir ve etki alanı adlarında hesap adı SID'e birebir çözülmez.
        """
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(),
                                          _TOKEN_QUERY, ctypes.byref(token)):
            raise _last_error("OpenProcessToken")
        try:
            # İlk çağrı ERROR_INSUFFICIENT_BUFFER ile döner ve gereken boyu yazar.
            size = wintypes.DWORD(0)
            _advapi32.GetTokenInformation(token, _TOKEN_USER, None, 0,
                                          ctypes.byref(size))
            buf = ctypes.create_string_buffer(size.value)
            if not _advapi32.GetTokenInformation(token, _TOKEN_USER, buf, size,
                                                ctypes.byref(size)):
                raise _last_error("GetTokenInformation")
            sid = ctypes.cast(buf,
                              ctypes.POINTER(_SID_AND_ATTRIBUTES)).contents.Sid
            text = wintypes.LPWSTR()
            if not _advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                raise _last_error("ConvertSidToStringSidW")
            try:
                return str(text.value)
            finally:
                _kernel32.LocalFree(text)
        finally:
            _kernel32.CloseHandle(token)

    def _resolve_sid(text: str) -> str | None:
        """SDDL'in SID alanını kanonik sayısal SID'e çevirir; çözülemezse None.

        NEDEN VAR: Windows DACL'i GERİ OKURKEN SID'i sayısal yazmak zorunda
        değil — yerleşik bir hesaba denk gelirse SDDL'in iki harfli TAKMA ADINI
        yazıyor. CI Windows koşusunda birebir ölçüldü: yazılan
        `D:P(A;;FA;;;S-1-5-21-…-500)` geri okunurken `D:PAI(A;;FA;;;LA)` oldu
        (`LA` = yerleşik Administrator, RID 500; runner o hesapla koşuyor).
        Metin karşılaştıran eski sürüm bu yüzden 6 testi YANLIŞ kırmızıya
        düşürdü — DACL doğruydu, okuyan taraf yanlıştı.

        `ConvertStringSidToSidW` iki biçimi de kabul ediyor (ölçüldü:
        `LA`/`BA`/`SY`/`WD` çözülüyor, sayısal SID aynen dönüyor, geçersiz
        girdide ERROR_INVALID_SID=1337). Geçersiz girdide None dönmek bilinçli:
        çözülemeyen bir SID "sahibi" SAYILMAMALI — hata yutulup True dönmesi
        güvenceyi sessizce boşaltırdı.
        """
        psid = ctypes.c_void_p()
        if not _advapi32.ConvertStringSidToSidW(text, ctypes.byref(psid)):
            return None
        try:
            out = wintypes.LPWSTR()
            if not _advapi32.ConvertSidToStringSidW(psid, ctypes.byref(out)):
                return None
            try:
                return str(out.value)
            finally:
                _kernel32.LocalFree(out)
        finally:
            _kernel32.LocalFree(psid)

    def _set_dacl(path: str, sddl: str) -> None:
        psd = ctypes.c_void_p()
        if not _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, _SDDL_REVISION_1, ctypes.byref(psd), None):
            raise _last_error("ConvertStringSecurityDescriptorToSecurityDescriptorW")
        try:
            present = wintypes.BOOL()
            dacl = ctypes.c_void_p()
            defaulted = wintypes.BOOL()
            if not _advapi32.GetSecurityDescriptorDacl(
                    psd, ctypes.byref(present), ctypes.byref(dacl),
                    ctypes.byref(defaulted)):
                raise _last_error("GetSecurityDescriptorDacl")
            # PROTECTED_DACL kalıtımı kesen bayrak. Yalnız DACL_SECURITY_
            # INFORMATION verilseydi liste yazılır ama üst dizinden gelen
            # ACE'ler de listede kalırdı — sıkılaştırma yarım olurdu.
            err = _advapi32.SetNamedSecurityInfoW(
                path, _SE_FILE_OBJECT,
                _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION,
                None, None, dacl, None)
            if err != 0:
                raise ctypes.WinError(err, f"SetNamedSecurityInfoW: {path}")
        finally:
            _kernel32.LocalFree(psd)

    def _get_dacl_sddl(path: str) -> str:
        psd = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        err = _advapi32.GetNamedSecurityInfoW(
            path, _SE_FILE_OBJECT, _DACL_SECURITY_INFORMATION, None, None,
            ctypes.byref(dacl), None, ctypes.byref(psd))
        if err != 0:
            raise ctypes.WinError(err, f"GetNamedSecurityInfoW: {path}")
        try:
            text = wintypes.LPWSTR()
            length = wintypes.DWORD()
            if not _advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    psd, _SDDL_REVISION_1, _DACL_SECURITY_INFORMATION,
                    ctypes.byref(text), ctypes.byref(length)):
                raise _last_error(
                    "ConvertSecurityDescriptorToStringSecurityDescriptorW")
            try:
                return str(text.value)
            finally:
                _kernel32.LocalFree(text)
        finally:
            _kernel32.LocalFree(psd)


def restrict_to_current_user(path: str) -> None:
    """Yolu yalnız mevcut kullanıcıya bırakır (Windows). POSIX'te no-op.

    Dizinlerde ACE kalıtılabilir işaretlenir (`OICI`): içeride açılan geçici
    dosya böylece daha DOĞARKEN yalnız sahibine ait olur. Bu, "izinleri
    yazımdan ÖNCE sıkılaştır" disiplininin (`os.fchmod`'un gerekçesi)
    Windows'taki karşılığı.

    Başarısızlıkta SESSİZ KALMAZ, OSError yükseltir. Bilinçli: bu yol bir API
    anahtarı yazıyor ve yutulmuş bir hata, "0600 güvencesi" adını taşıyan ama
    aslında herkese okunabilir bir dosya bırakır — testlerin yeşil olduğu bir
    yalan. `os.fchmod` de aynı sebeple korumasız çağrılıyor.
    """
    if not is_supported():
        return
    flags = _DIR_ACE_FLAGS if os.path.isdir(path) else _FILE_ACE_FLAGS
    _set_dacl(path, f"D:P(A;{flags};FA;;;{_current_user_sid()})")


def dacl_sddl(path: str) -> str:
    """Yolun DACL'ini SDDL dizesi olarak döndürür (teşhis + testler için)."""
    if not is_supported():
        raise RuntimeError("dacl_sddl yalnızca Windows'ta anlamlı")
    return _get_dacl_sddl(path)


def is_owner_only(path: str) -> bool:
    """DACL 0600'ün karşılığı mı: kalıtım kesik + tek izin, mevcut kullanıcı.

    POSIX'teki `stat.S_IMODE(...) == 0o600` iddiasının Windows karşılığı;
    testler platforma göre bu ikisinden birini kullanıyor.
    """
    if not is_supported():
        raise RuntimeError("is_owner_only yalnızca Windows'ta anlamlı")

    sddl = _get_dacl_sddl(path)
    prefix = _DACL_PREFIX.match(sddl)
    if prefix is None or "P" not in prefix.group(1):
        return False  # kalıtım kesilmemiş → üst dizinden izin sızabilir

    aces = _ACE.findall(sddl)
    if not aces:
        return False  # boş DACL herkesi ENGELLER ama "sahibine ait" değil

    sid = _current_user_sid()
    for ace in aces:
        fields = ace.split(";")
        if len(fields) != 6:
            return False
        ace_type, _flags, _rights, _obj_guid, _inherit_guid, ace_sid = fields
        # SID'ler METİN olarak DEĞİL, çözülmüş hâlleriyle karşılaştırılıyor:
        # aynı hesabı `S-1-5-21-…-500` ve `LA` diye iki biçimde yazan Windows
        # yüzünden metin karşılaştırması temsile bağımlıydı (bkz. _resolve_sid).
        if ace_type != "A" or _resolve_sid(ace_sid) != sid:
            return False
    return True
