# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Diskteki tercihlerin İSTEK YOLUNDAKİ okuyucusu — önbellekli.

NEDEN VAR: dil ara katmanı (services/dil.py) Faz 0 / Adım 3'e kadar her
istekte `prefs.read` çağırıyordu — bir `open` + `json.load`, istek başına.
Loopback'te ölçülebilir bir bedeli yoktu ve bilerek öyle yazılmıştı ("tercih
çalışırken değişebiliyor, donmuş bir değer eski dili gösterir"). Web'de aynı
süreç yüzlerce isteğe bakacak ve hepsi aynı dosyayı okuyacak; bu modül
dosyayı ancak DEĞİŞMİŞSE yeniden okur ve eski gerekçeyi de korur: değişen
dosya bir sonraki istekte görünür, sunucu yeniden başlatılmaz.

NEDEN DOSYA İMZASIYLA, TTL İLE DEĞİL: TTL "en fazla N saniye bayat" demek —
dili çeviren kullanıcı sayfayı yeniledikten sonra N saniye eski dili görürdü
ve bu tam olarak eski docstring'in kaçındığı kusur. İmza
(`st_ino`, `st_mtime_ns`, `st_size`) değişmemişse içerik de değişmemiştir:
`jsonstore.write_atomic` geçici dosyaya yazıp `os.replace` ediyor, yani her
yazım YENİ bir inode getiriyor — mtime saati kaba (Linux'ta jiffy, ~4 ms)
olsa bile ardışık iki yazım aynı imzayı üretemiyor. Dosya YOKSA imza `None`
ve o da bir imza: "kayıt yok" cevabı da önbelleğe giriyor, yoksa hiç tercih
yazmamış bir kurulumda her istek diske `open` denerdi. `i18n.catalog`ın
sözlük önbelleğiyle aynı fikir; bedeli istek başına tek bir `stat`.

NEDEN yine de `sifirla()` var: `POST /api/prefs` yazdığı anda önbelleği
düşürüyor. İmza zaten yakalardı; açık çağrı, yazan ile okuyanın aynı süreçte
olduğu tek durumda mekanizmaya değil SÖZLEŞMEYE dayanmak için. Testler de onu
testler arasında sızıntıya karşı kullanıyor (tests/conftest.py): iki test
aynı dizini (geliştiricinin gerçek `output/`u) paylaşıp `prefs.read_stored`ı
farklı değerlerle yamalayabiliyor ve dosya ikisinde de değişmiyor —
yamanın gördüğü şey önbellekse ikinci test birincinin dilini okurdu.

FAZ 1 NOTU: kullanıcı hesabı geldiğinde "kayıtlı tercih" buradan değil
hesaptan gelecek. Ara katmanın gördüğü tek şey `dil(output_dir)` imzası;
değişecek yer bu dosyanın içi, zincir (services/dil.py) değil.

Bu modül `prefs`'e bakıyor, ayar nesnesine DEĞİL: dizini çağıran veriyor.
Böylece testler bir `tmp_path`i doğrudan sorabiliyor ve önbellek anahtarı
da o dizin — iki test iki ayrı dizinle birbirini göremiyor.
"""
from __future__ import annotations

import os
import threading

import prefs

# dizin → (dosya imzası, o imzada okunan kayıtlı tercihler)
_onbellek: dict[str, tuple[tuple[int, int, int] | None, dict]] = {}

# Kilit ÖNBELLEK için (i18n._lock'un gerekçesi): iki istek aynı anda ilk kez
# okuyabilir; `dict` ataması atomik olsa da yarım yazılmış bir çift olmasın.
_kilit = threading.Lock()


def _imza(output_dir: str) -> tuple[int, int, int] | None:
    try:
        st = os.stat(os.path.join(output_dir, prefs.PREFS_FILE))
    except OSError:
        return None     # dosya yok → "kayıt yok" imzası (bkz. modül başlığı)
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def kayitli(output_dir: str) -> dict:
    """Diskte AÇIKÇA yazılmış ve geçerli tercihler (`prefs.read_stored`), önbellekten.

    Dönen sözlük paylaşılıyor; çağıran DEĞİŞTİRMEZ (kopya almanın bedeli her
    istekte ödenirdi, bugün tek okuyucu `.get` yapıyor).
    """
    imza = _imza(output_dir)
    with _kilit:
        giris = _onbellek.get(output_dir)
        if giris is not None and giris[0] == imza:
            return giris[1]
    # Okuma kilidin DIŞINDA: disk I/O kilit altında olsa ilk isteğin okuması
    # ötekileri bekletirdi. Yarış zararsız — iki okuma aynı içeriği getirir ve
    # `stat` ile `read` arasında dosya değişse bile bir sonraki `stat` yeni
    # imzayı görür ve yeniden okur.
    degerler = prefs.read_stored(output_dir)
    with _kilit:
        _onbellek[output_dir] = (imza, degerler)
    return degerler


def dil(output_dir: str) -> str | None:
    """Kayıtlı arayüz dili; hiç seçilmemişse `None` (varsayılan DEĞİL).

    `None` anlamlı: dil zinciri (services/dil.py) "kayıt yok" cevabında sırayı
    tarayıcının `Accept-Language` başlığına geçiriyor. `prefs.read`in
    döndürdüğü birleşik görünüm bu farkı gösteremezdi — varsayılanı doldurur.
    """
    return kayitli(output_dir).get("language")


def sifirla() -> None:
    """Önbelleği düşürür — yazan taraf (`POST /api/prefs`) ve testler çağırıyor."""
    with _kilit:
        _onbellek.clear()
