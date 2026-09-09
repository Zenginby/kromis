r"""Hiçbir kaynak dosya SyntaxWarning basmamalı — kalıcı, depo geneli kapı.

NEDEN VAR: bu kusur sınıfı burada İKİ KEZ geçti ve ikisi de aynı desendeydi —
kod DOĞRU çalışıyor, uyarı gürültünün içinde kayboluyor, borç sessizce ileriye
yazılıyor:

  • v0.3.0 — `gpt-image-studio.spec`: yorumdaki `%LOCALAPPDATA%\Lumeo` yolu
    `\L`'yi geçersiz bir kaçış dizisi yaptı. Uyarı yalnız DERLEME sırasında,
    pyinstaller'ın onlarca INFO satırı arasında görünüyordu — kaybolmaya birebir
    uygun. Kapısı `tests/test_version.py::test_spec_has_no_syntax_warnings`
    olarak yazıldı, ama YALNIZ spec'e bakıyordu.
  • `tests/test_mobile.py:639` — bir docstring eski bir regex'i alıntılıyordu:
    `re.search(r"\n\s*height:", govde)`. Docstring HAM DEĞİLDİ, yani `\s`
    geçersiz kaçış (SyntaxWarning) oldu. İkinci ve daha sinsi yarısı: `\n`
    GEÇERLİ bir kaçış, yani hiç uyarı basmadan cümlenin ortasına gerçek bir
    satır sonu koyuyordu — alıntı artık alıntıladığı kodu göstermiyordu.

Bu dosyanın var oluş sebebi ikinci olayın dersi: ilk kapı doğru kusuru
arıyordu ama YANLIŞ YERDE, çünkü kusur sınıfı spec'e özgü değil. Yorumunda
Windows yolu ya da regex ALINTILAYAN her dosya aynı tuzağa basabilir — ve bu
depo, yorumların "neden öyle"yi anlatmasını ve kodu birebir alıntılamasını
İSTEDİĞİ için (bkz. CLAUDE.md) tuzağa basma olasılığı sıradan bir depodan
YÜKSEK. Kapı bu yüzden ürünü DE testleri DE araçları DE spec'i DE tarıyor.

NEDEN ACELE: geçersiz kaçış dizileri Python 3.12'de DeprecationWarning'den
SyntaxWarning'e yükseltildi ve SyntaxError olmaya adaylar. Yani bugün gürültü
olan şey yarın uygulamayı hiç açtırmaz; kapının bedeli bugün bir `r` harfi,
yarın bir sürüm yükseltmesinin çökmesi.

NEDEN `compile`, regex DEĞİL: bir ters bölünün geçerli olup olmadığı dizenin
ÖNEKİNE (ham mı değil mi) ve Python'un kendi geçerli-kaçış tablosuna bağlı.
Kaynağa regex atan bir tarayıcı o tabloyu yeniden yazmak zorunda kalır ve
kaçınılmaz olarak ham `r"\s"`i (geçerli) yanlışlıkla yakalayıp `"\p"`yi
(geçersiz) kaçırır. Derleyici bu sorunun TEK doğru hakemi.

NEDEN `compile` ve ÇALIŞTIRMA değil: `compile` yalnız derler. Spec'in
Analysis/EXE çağrıları, testlerin fixture'ları, modüllerin içe aktarma yan
etkileri burada hiç uğranmıyor — tarayıcı bu yüzden hem güvenli, hem de çalışma
anında HİÇ girilmeyen satırları da görüyor.

NEDEN yalnız kaçış dizileri DEĞİL, TÜM SyntaxWarning: `is` ile literal
karşılaştırma, demet üzerine `assert` (her zaman doğru!) — hepsi aynı sınıf:
derlenir, ama yazanın kastettiğinden BAŞKA şey ifade eder ve sessizdir. Demet
üzerine yazılmış tek bir `assert` bu depoda bir testi sahte-yeşil yapardı;
ayrıca aramaya gerek yok, aynı ağa düşüyor.
"""
import os
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Taranmayan ağaçlar: bize ait olmayan ya da üretilmiş kod.
# tests/test_encoding_contract.py'deki liste ile bilinçli olarak İKİZ: test
# dosyaları birbirinden içe aktarma yapmıyor (her sözleşme tek başına
# okunabilsin diye), o yüzden küçük yürüteç burada tekrarlanıyor.
#
# `.claude` NEDEN atlanıyor: `.claude/worktrees/` altında git worktree'leri,
# yani BAŞKA commit'lerin tam çalışma kopyaları yaşıyor. Bu kapı bir
# worktree'nin İÇİNDE yazıldı ve orada `.claude/worktrees/` HİÇ yoktu, yani
# yazıldığı yerde yeşildi; ana çalışma kopyasında ilk koşuda eski bir
# commit'in DÜZELTİLMEMİŞ `tests/test_mobile.py`sini bulup kırmızıya döndü —
# düzelttiği kusuru başka bir commit'te yeniden okuyordu. Atlamak bir
# istisna DEĞİL, listenin başındaki "bize ait olmayan kod" sözü: o ağaç
# `.gitignore:43` ile yok sayılıyor (`.claude/*`, yalnız `settings.json`
# muaf) ve `.claude` altında İZLENEN tek bir `.py` yok — ölçüldü, yani
# atlamak hiçbir kaynağı kör noktaya sokmuyor. `tools/graf_uret.py` aynı
# tuzağa hiç düşmedi çünkü özyineli yürüteç kullanmıyor.
ATLANAN_DIZINLER = {
    ".venv", ".git", ".claude", "__pycache__", "dist", "build",
    "graphify-out", "output", "node_modules", ".pytest_cache",
}

# `.spec` PyInstaller'ın Python kaynağıdır: uzantısı `.py` OLMADIĞI için
# yürüteç onu adıyla almak zorunda — v0.3.0 kusuru tam orada yaşandı, yani
# `.py` süzgeci tek başına kapıyı ilk olayına karşı kör bırakırdı.
EK_KAYNAKLAR = ("gpt-image-studio.spec",)


def _kaynak_dosyalari():
    for kok, dizinler, dosyalar in os.walk(REPO):
        dizinler[:] = [d for d in dizinler if d not in ATLANAN_DIZINLER]
        for ad in dosyalar:
            if ad.endswith(".py"):
                yield os.path.join(kok, ad)
    for ad in EK_KAYNAKLAR:
        yol = os.path.join(REPO, ad)
        if os.path.exists(yol):
            yield yol


def uyarilar(kaynak: str, yol: str = "<kaynak>"):
    """Kaynağı derler; SyntaxWarning'leri (satır, mesaj) olarak sıralı verir.

    `catch_warnings` + `simplefilter("always")` ŞART: Python aynı konumdaki bir
    uyarıyı `__warningregistry__` üzerinden İKİNCİ kez basmaz. Varsayılan
    süzgeçle tarayıcı, kendisinden önce koşan bir testin uyarıyı "harcamış"
    olmasına bağlı hâle gelirdi — kapının en sinsi kör noktası bu olurdu, çünkü
    tek başına koşarken yeşil, tüm takımla koşarken de yeşil ama SEBEBİ yanlış.
    """
    with warnings.catch_warnings(record=True) as kayit:
        warnings.simplefilter("always")
        compile(kaynak, yol, "exec")
        return sorted((u.lineno, str(u.message)) for u in kayit
                      if issubclass(u.category, SyntaxWarning))


def test_no_source_file_emits_a_syntax_warning():
    """Ürün, testler, araçlar ve spec: SyntaxWarning basan dosya kalmamalı.

    Kapı yazıldığında `tests/test_mobile.py:639`'u buldu — yani yazıldığı anda
    KIRMIZIYDI; modül docstring'indeki ikinci olay bu.
    """
    bulgular = []
    for yol in _kaynak_dosyalari():
        with open(yol, encoding="utf-8") as fh:
            kaynak = fh.read()
        for satir, mesaj in uyarilar(kaynak, yol):
            bulgular.append(f"{os.path.relpath(yol, REPO)}:{satir} → {mesaj}")

    assert not bulgular, (
        f"{len(bulgular)} kaynak SyntaxWarning basıyor; geçersiz kaçış dizisi "
        "ileride SyntaxError olacak. Regex ya da Windows yolu ALINTILAYAN bir "
        "docstring'i HAM yapmak (üç tırnağın önüne `r`) çoğu durumda doğru "
        "düzeltmedir: ters bölüler alıntılanan kodla birebir kalır ve `n`/`t`"
        " gibi GEÇERLİ kaçışlar metni sessizce bozmaz.\n  "
        + "\n  ".join(sorted(bulgular)))


def test_the_scanner_sees_the_defects_it_was_written_for():
    r"""Kapının kendisi ölçülüyor: sessizce boş dönen bir tarayıcı kapı değildir.

    Yukarıdaki testin yeşil olması iki şey demek olabilir — uyarı yok, YA DA
    tarayıcı kör. Bu test ikincisini eliyor: örnek, modül docstring'indeki İKİ
    gerçek olayı da taşıyor (`\L` yolu ve `\s` regex'i) ve yanlış-pozitif
    üretmemesi gereken ÜÇ geçerli biçimi — çünkü aşırı hevesli bir tarayıcı da
    kapı değildir, deponun 90 ham regex'ini kırmızıya boyar.

    Örnek satırları HAM dize olarak yazılı: böyle bir örnekte ters bölüyü
    ikilemek iki kat kaçış katmanı doğurur ve örneğin NE sınadığı okunamaz hâle
    gelir — bu kapının konusu tam olarak o karışıklık.
    """
    ornek = "\n".join((
        r'"""Yol: %LOCALAPPDATA%\Lumeo."""',   # 1 ← v0.3.0: geçersiz `\L`
        r'DESEN = "\s+"',                      # 2 ← test_mobile: geçersiz `\s`
        r'HAM = r"\s+"',                       # 3 ham dize: geçerli
        r'KACIS = "\\s+"',                     # 4 kaçırılmış ters bölü: geçerli
        r'SATIR = "bitti\n"',                  # 5 `\n` GEÇERLİ kaçış
    )) + "\n"
    assert [s for s, _ in uyarilar(ornek)] == [1, 2], uyarilar(ornek)


def test_the_scanner_also_catches_non_escape_syntax_warnings():
    """Kaçış dizileri kapının tek işi değil (bkz. modül docstring'i).

    Demet üzerine `assert` HER ZAMAN doğrudur: böyle yazılmış bir test hiçbir
    şey sınamadan yeşil yanar. Ağın bu sınıfı da tuttuğu ölçülüyor, yoksa "TÜM
    SyntaxWarning" iddiası yalnız docstring'de kalırdı.
    """
    bulgular = uyarilar('assert (1 == 2, "mesaj")\n')
    assert [s for s, _ in bulgular] == [1], bulgular
