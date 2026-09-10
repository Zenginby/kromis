"""Yayına giren paketlerin TEK kaynağı.

Buradaki sözlük dört yere birden akar:
  1. `.github/workflows/release.yml` → `yayinla` işinin `needs:` listesi ve
     indirilen varlıkların küme denetimi,
  2. `README.md` → "Uygulamayı İndir" tablosundaki `releases/latest/download/…`
     bağlantıları,
  3. `GUNCELLEME.md` → en üstteki "Sistem / Dosya" tablosu,
  4. `tests/test_release_manifest.py` → yukarıdaki üçünün birbirinden
     ayrışmadığını her PR'da kanıtlayan bekçi.

NEDEN VAR: v0.4.2'ye kadar "hangi paketler yayına girer" sorusunun cevabı beş
ayrı yerde, birbirinden habersiz duruyordu — iki workflow'un `files:` listesi,
README tablosu, GUNCELLEME tablosu ve APK'yı yayın adına taşıyan `mv`. Bir
platform eklemek (ya da bir işin sessizce atlanması) bu beşliyi ayrıştırmaya
birebir uygundu: yayın yeşil çıkar, yalnız bir paket eksik olur ve bunu ancak
indirmeye çalışan kullanıcı fark ederdi.

KURAL: yeni bir platform BURAYA yazılır. Yazıldığı anda pytest kırmızıya döner
ve README'si, GUNCELLEME satırı, çağrılabilir workflow'u ve `release.yml`'deki
işi gelene kadar kırmızı kalır. "Atlanmadan güncellenme" garantisi budur.

Bu modül BİLEREK bağımlılıksız (yalnız __future__), `version.py` ile aynı
gerekçeyle: CI'daki yayın işi onu depo kökünden, uygulamanın hiçbir bağımlılığı
kurulu olmadan `python -c "import release_manifest"` ile okuyor.
"""
from __future__ import annotations

# Anahtar = yayın varlığının adı. Paket işleri artifact'i BU adla yüklüyor;
# yayın işi indirdiği dosya adlarını bu kümeyle karşılaştırıyor. Ara bir ad
# (eskiden `dist-kromis-android-arm64.apk`) bilinçle bırakılmadı: ayrışabilecek
# her ek isim, ayrışacak bir yerdir.
PAKETLER: dict[str, dict[str, str]] = {
    "kromis-macOS-arm64.zip": {
        # release.yml'deki iş adı — `yayinla` işinin `needs:` listesinde
        # görünmek ZORUNDA, yoksa bu paket üretilmeden yayın oluşabilirdi.
        "is": "paket-macos",
        # Paketi üreten çağrılabilir workflow.
        "workflow": "_paket-macos.yml",
        # Kullanıcıya gösterilen sistem adı (GUNCELLEME.md tablosu).
        "sistem": "macOS (Apple Silicon)",
    },
    "kromis-windows-x64.zip": {
        "is": "paket-windows",
        "workflow": "_paket-windows.yml",
        "sistem": "Windows 10/11 (64-bit)",
    },
    "kromis-android-arm64.apk": {
        "is": "paket-android",
        "workflow": "_paket-android.yml",
        "sistem": "Android 8.0+ (arm64)",
    },
}


def varliklar() -> set[str]:
    """Yayında bulunması gereken dosya adları."""
    return set(PAKETLER)


def eksikler(bulunanlar: list[str] | set[str]) -> tuple[list[str], list[str]]:
    """(eksik, fazla) — yayın işinin küme denetimi bunu kullanıyor.

    FAZLA da hata sayılıyor: yayına beklenmeyen bir dosya girmesi, ya bir işin
    yanlış varlık yüklediği ya da manifestin bayatladığı anlamına gelir.
    İkisi de sessizce geçmemeli.
    """
    bulunan = set(bulunanlar)
    beklenen = varliklar()
    return sorted(beklenen - bulunan), sorted(bulunan - beklenen)
