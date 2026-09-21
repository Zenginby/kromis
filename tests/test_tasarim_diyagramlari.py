"""`docs/tasarim-diyagramlari/` hâlâ kodu mu anlatıyor — elle yazılanın kapısı.

NEDEN VAR: `docs/graflar/` kaynaktan ÜRETİLİR, burası ELLE yazılır. Aradaki fark
tests/test_graflar.py'nin dersini bu klasöre aynen taşır — "yanlış bir harita,
hiç harita olmamasından KÖTÜDÜR, çünkü güvenilir görünür" — ama çözümü aynı
olamaz: elle yazılmış bir diyagram baytı baytına yeniden üretilemez, çünkü
üreteni yok.

Bu kapı bu yüzden bayt değil ATIF ölçüyor. Diyagramın metninde geçen her kod
adının kaynakta hâlâ var olduğunu doğruluyor. Gerekçesi ölçülmüş bir olaydır:
bu klasörün ilk diyagramı yazıldıktan saatler sonra `services/defter.py` iki
kovaya geçti (Faz 4 / 2, +387/-154) ve kartların yarısı o anda eskidi. Kapı
olmasaydı sessizce eskimiş kalırdı.

Kapı DÖRT şeyi ölçüyor:

  1. Her diyagram geçerli JSON mu ve bildiği bir tür mü — 2. ile 3. testin
     anlamlı olması buna bağlı; bozuk dosya ikisini de sessizce atlatırdı.
  2. KOD AYNASI diyagramların durum kümesi `tablolar.IS_DURUMLARI` ile
     BİREBİR aynı mı. Yeni bir `isler.durum` eklendiğinde ya da biri yeniden
     adlandırıldığında diyagram eksik kalır; o sözleşme zaten CHECK'te kilitli
     (bkz. services/tablolar.py §`IS_DURUMLARI`), diyagram da ona uymalı.
  3. Metinde geçen her `<modül>.<ad>` atfı o modülde gerçekten TANIMLI mı.
     `kuyruk.bayatlari_dusur` bir gün yeniden adlandırılırsa takım kırmızı olur.
     Henüz YAZILMAMIŞ bir modüle atıf (`odeme.isle`, Faz 4 / 3) sessizce
     atlanır ve o dosya indiği gün kendiliğinden korunmaya başlar.
  4. 2. testin elle tutulan kapsam listesi EKSİKSİZ mi — her diyagram ya
     taranıyor ya da muafiyet defterinde gerekçesiyle duruyor (CLAUDE.md §5).

Kapının YAKALAMADIĞI: anlamsal kayma. Yarın `calisiyor` iptal edilebilir hâle
gelirse her ad yerinde durur, test yeşil kalır ve diyagram yalan söylemeye
devam eder. Bunun ucuz bir bekçisi yok; kod aynası bir diyagram eklerken bu
sınırı bilerek ekleyin.
"""
from __future__ import annotations

import ast
import json
import os
import re

import pytest

from services.tablolar import IS_DURUMLARI

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIZIN = os.path.join(REPO, "docs", "tasarim-diyagramlari")

# Archify'ın ürettiği türler; dosya adı `<ad>.<tür>.json` biçiminde.
TURLER = frozenset({"architecture", "workflow", "sequence", "dataflow", "lifecycle"})

# KOD AYNASI diyagramlar — 2. test yalnız bunlara uygulanır.
KOD_AYNASI_DURUM = {"kromis-is-yasam-dongusu.lifecycle.json": set(IS_DURUMLARI)}

# MUAFİYET DEFTERİ — 2. testin dışında kalan her diyagram, GEREKÇESİYLE.
# Bu deponun deyimi (CLAUDE.md §5): elle tutulan bir kapsam listesinde OLMAYAN
# dosyanın öntanımlı hâli *muaf*tır ve yeni gelen dosya kapıyı hiç görmeden
# geçer — `fal_client.py` v0.23'te, `static/i18n.js` PR #12'de böyle kaçtı.
# 4. test iki listenin BİRLİKTE eksiksiz olmasını zorluyor; buraya bir satır
# yazmadan yeni diyagram ekleyemezsiniz.
DURUM_MUAF = {
    "kromis-polar-webhook.sequence.json":
        "Sıra diyagramı, durum makinesi değil: `states` yok, `IS_DURUMLARI` ile "
        "kıyaslanacak bir küme taşımıyor. Kod atıfları 3. testte korunuyor.",
}

# Atıf deseni: `kuyruk.al`, `defter.onayla` … Yalnız services/ altındaki modüller
# aranır; `isler.durum` gibi tablo/sütun atıfları modül değildir, eşleşmez.
ATIF = re.compile(r"\b([a-z_]+)\.([a-z_][a-z0-9_]*)\b")


def diyagramlar() -> list[str]:
    """`<ad>.<tür>.json` biçimindeki dosyalar — yan ürünler DEĞİL.

    Deseni dar tutmak bilinçli: `archify visual-check` aynı klasöre
    `<ad>.visual-check.json` bırakıyor ve "her .json diyagramdır" varsayımı
    onu diyagram sanmıştı (bu testler yazılırken ölçüldü).
    """
    if not os.path.isdir(DIZIN):
        return []
    return sorted(a for a in os.listdir(DIZIN)
                  if a.endswith(".json") and a.rsplit(".", 2)[-2] in TURLER)


def _metinler(nesne: object) -> list[str]:
    """Diyagramdaki tüm insan metnini toplar — etiket, alt etiket, kart maddesi."""
    if isinstance(nesne, str):
        return [nesne]
    if isinstance(nesne, dict):
        return [p for d in nesne.values() for p in _metinler(d)]
    if isinstance(nesne, list):
        return [p for d in nesne for p in _metinler(d)]
    return []


def _tanimlar(modul: str) -> set[str] | None:
    """`services/<modul>.py`nin üst düzey adları — İTHAL ETMEDEN, ast ile.

    İthal etmek veri tabanı zeminini ve ortam sırlarını ayağa kaldırırdı; bu
    kapının ölçtüğü şeyin onlarla ilgisi yok.
    """
    yol = os.path.join(REPO, "services", f"{modul}.py")
    if not os.path.isfile(yol):
        return None
    with open(yol, encoding="utf-8") as f:
        agac = ast.parse(f.read(), filename=yol)
    adlar: set[str] = set()
    for dugum in agac.body:
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            adlar.add(dugum.name)
        elif isinstance(dugum, ast.Assign):
            adlar.update(h.id for h in dugum.targets if isinstance(h, ast.Name))
        elif isinstance(dugum, ast.AnnAssign) and isinstance(dugum.target, ast.Name):
            adlar.add(dugum.target.id)
    return adlar


@pytest.mark.parametrize("ad", diyagramlar())
def test_diyagram_okunabilir(ad: str) -> None:
    """1. Geçerli JSON ve bilinen tür — 2. ile 3. testin zemini."""
    with open(os.path.join(DIZIN, ad), encoding="utf-8") as f:
        d = json.load(f)
    tur = ad.rsplit(".", 2)[-2]
    assert tur in TURLER, f"{ad}: bilinmeyen tür {tur!r}"
    assert d.get("diagram_type") == tur, f"{ad}: dosya adı {tur!r}, içerik {d.get('diagram_type')!r}"
    # Düğüm koleksiyonunun adı türe göre değişiyor: lifecycle `states`, sequence
    # `participants`, ötekiler `nodes`.
    assert d.get("states") or d.get("participants") or d.get("nodes"), f"{ad}: boş diyagram"


@pytest.mark.parametrize("ad", sorted(KOD_AYNASI_DURUM))
def test_durum_kumesi_sozlesmeyle_ayni(ad: str) -> None:
    """2. Kod aynası diyagramın durumları `IS_DURUMLARI` ile BİREBİR aynı."""
    yol = os.path.join(DIZIN, ad)
    assert os.path.isfile(yol), f"{ad} yok — KOD_AYNASI_DURUM güncellenmeli"
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    cizilen = {s["id"] for s in d["states"]}
    assert cizilen == KOD_AYNASI_DURUM[ad], (
        f"{ad}: diyagram {sorted(cizilen)} çiziyor, sözleşme {sorted(KOD_AYNASI_DURUM[ad])} diyor "
        f"(services/tablolar.py IS_DURUMLARI)"
    )


def test_her_diyagram_ya_taranir_ya_muaftir() -> None:
    """4. Kapsam listesi EKSİKSİZ mi — sessizce muaf kalan diyagram yok.

    Kapının kapısı. 2. test elle tutulan bir listeye bakıyor; o liste eksik
    kalırsa yeni diyagram kapıyı hiç görmeden geçer. Burası her dosyanın
    listelerden BİRİNDE ve yalnız birinde olmasını zorluyor.
    """
    dosyalar = set(diyagramlar())
    taranan, muaf = set(KOD_AYNASI_DURUM), set(DURUM_MUAF)
    assert not (taranan & muaf), f"hem taranan hem muaf: {sorted(taranan & muaf)}"
    assert not (dosyalar - taranan - muaf), (
        f"sınıflandırılmamış diyagram: {sorted(dosyalar - taranan - muaf)} — "
        f"KOD_AYNASI_DURUM'a ekleyin ya da DURUM_MUAF'a gerekçesiyle yazın"
    )
    assert not ((taranan | muaf) - dosyalar), (
        f"listede olup diskte olmayan: {sorted((taranan | muaf) - dosyalar)}"
    )
    assert all(DURUM_MUAF.values()), "muafiyet gerekçesiz olamaz"


@pytest.mark.parametrize("ad", diyagramlar())
def test_kod_atiflari_hala_var(ad: str) -> None:
    """3. Metinde geçen her `<modül>.<ad>` services/ altında hâlâ tanımlı."""
    with open(os.path.join(DIZIN, ad), encoding="utf-8") as f:
        d = json.load(f)
    kayip: list[str] = []
    for metin in _metinler(d):
        for modul, cagrilan in ATIF.findall(metin):
            if cagrilan == "py":          # `services/polar.py` bir DOSYA ADI, `polar.py` atfı değil —
                continue                  # modül doğunca (Faz 4 / 3) yanlış pozitif verdi, ölçüldü
            tanimlar = _tanimlar(modul)
            if tanimlar is None:          # services/ altında böyle bir modül yok
                continue                  # → atıf değil, sıradan metin
            if cagrilan not in tanimlar:
                kayip.append(f"{modul}.{cagrilan}")
    assert not kayip, f"{ad}: kaynakta bulunamayan atıf(lar): {sorted(set(kayip))}"
