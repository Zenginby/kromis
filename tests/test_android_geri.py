"""MainActivity'nin kullandığı metin kaynakları `strings.xml`'de GERÇEKTEN var mı.

Bu test var, çünkü kırılma sınıfı sinsi ve tam olarak `test_android_apk_name.py`
ile aynı: iki dosya da kendi içinde tutarlı, hata yalnızca BİRLEŞTİKLERİ yerde.
`getString(R.string.olmayan_ad)` derlemede yakalanır — ama adı `strings.xml`'den
silip Kotlin'de bırakmak ya da tersini yapmak, derlemeyi geçip çalışma anında
`Resources.NotFoundException` ile çöker. Üstelik bu yalnız Android runner'ında
(dakikalar süren bir NDK + Gradle işi) ve ancak o kod yolu ÇALIŞTIRILDIĞINDA
görünür: "geri tuşuna bastım, uygulama çöktü".

Yerelde koşan bu ucuz iddia aynı kaymayı saniyede yakalıyor.
"""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOTLIN = os.path.join(
    REPO, "android", "app", "src", "main", "java", "org", "zenginby",
    "gptimagestudio", "MainActivity.kt",
)
STRINGS = os.path.join(REPO, "android", "app", "src", "main", "res", "values", "strings.xml")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _tanimli_adlar() -> set[str]:
    return set(re.findall(r'<string name="([^"]+)"', _read(STRINGS)))


def _kullanilan_adlar() -> set[str]:
    return set(re.findall(r"R\.string\.(\w+)", _read(KOTLIN)))


def test_every_string_the_activity_asks_for_is_defined():
    eksik = _kullanilan_adlar() - _tanimli_adlar()
    assert not eksik, f"strings.xml'de tanımlı olmayan metinler: {sorted(eksik)}"


def test_the_double_back_warning_exists_and_is_used():
    """Çıkış uyarısının metni ile onu isteyen kod AYNI adı taşımalı.

    Ayrıca boş olmamalı: boş bir Toast görünmez ve kullanıcı "ilk basış hiçbir şey
    yapmadı" diye ikinci kez basar — yani uyarı olmadan çift basış korumasının
    kullanıcı açısından hiçbir karşılığı kalmaz.
    """
    ad = "cikmak_icin_tekrar_geri"
    assert ad in _kullanilan_adlar(), f"MainActivity {ad} metnini hiç istemiyor"
    metin = re.search(rf'<string name="{ad}">([^<]*)</string>', _read(STRINGS))
    assert metin, f"{ad} strings.xml'de tanımlı değil"
    assert metin.group(1).strip(), f"{ad} boş"
