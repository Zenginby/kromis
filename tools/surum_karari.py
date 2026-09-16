#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Bir sonraki sürümün ne olacağına — ve yayın gerekip gerekmediğine — karar verir.

`release.yml`'deki `karar` işi bunu çağırıyor. Mantık YAML'a DEĞİL buraya
yazıldı, tek bir gerekçeyle: YAML'daki bir kural ancak gerçek bir koşuyla
sınanabilir ve bu deponun yayın yolundaki her deneme bir sürüm numarası (ya da
v0.2.1'de olduğu gibi üç başarısız tag koşusu) harcıyor. Buradaki `karar()` saf
bir fonksiyon — girdisi tag listesi, commit metinleri ve değişen yollar; çıktısı
bir sözlük. `tests/test_surum_karari.py` onu saniyede, bedava sınıyor.

KARAR KURALI
------------
    1) version.py son tag'den İLERİDEYSE → o sürüm henüz yayınlanmamış demektir.
       Artırma YOK, olduğu gibi yayınla.  (kendi kendini onarma)
    2) version.py son tag'le AYNIYSA → tag'den beri gelen değişikliklere bak:
         - BU İTMEDE `[yayin: yok]` varsa       → yayın YOK (yalnız kendi
                                                  merge'ini susturur; kapsam
                                                  `tetikleyen_aralik`, markör
                                                  satırı BİTİRMELİ)
         - hiçbiri pakete girmiyorsa            → yayın YOK
         - `feat` varsa                         → minör artır
         - `!`/BREAKING CHANGE varsa            → majör artır
         - aksi hâlde                           → yama artır
    3) version.py son tag'in GERİSİNDEYSE → anomali (geri alınmış bir bump).
       Sürüm asla geri gitmez: son tag'den ileri artırılır.

1. KURAL NEDEN VAR: paketlerden biri kırmızıya düşerse main'de artırılmış bir
`version.py` kalır ama tag hiç oluşmaz (yayını tek yazıcı, hepsi yeşil olunca
atıyor). Bir sonraki merge o sürümü ikinci kez artırmamalı — yayınlanmamış
olanı yayınlamalı. Aynı kural, sürümü elle bir PR içinde artıran insanı da
destekler: CI onu olduğu gibi kabul eder.

"PAKETE GİRMİYOR" NEDEN YOLA BAKARAK ÖLÇÜLÜYOR
----------------------------------------------
Bu deponun squash-merge başlıklarının bir kısmı Conventional Commits'e uymuyor
("Telefondaki üç arayüz kusurunu düzelt…", "Kromis: yeniden adlandırma…").
Yalnızca mesaja bakan bir ayrıştırıcı bunları "tip yok → yayınlanacak bir şey
yok" diye okur ve tam da yayınlanması gereken değişikliği atlardı.

O yüzden ölçü YOL: aşağıdaki GUVENLI_YOLLAR listesindeki dosyalar pakete hiçbir
biçimde girmiyor. Liste bir BEYAZ liste — tanımadığı her yol "pakete girer"
sayılır, yani belirsizlik her zaman "yayınla" tarafına düşer. Bu, version.py'nin
kendi yazılı kuralıyla birebir aynı: "gönderilen HER build APP_VERSION'ı
artırır — yalnızca bir CSS/JS düzeltmesi de olsa."

DİKKAT: `bundled/prompts/*.md` pakete GİREN bir .md dosyası. Bu yüzden liste
"bütün .md dosyaları güvenli" diye yazılamaz; kök dizindeki belgeler tek tek
sayılıyor.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# Pakete hiçbir biçimde girmeyen yollar. Bir merge YALNIZCA bunlara
# dokunuyorsa yayın yapılmaz.
#
# Dizinler sonunda "/" ile yazılı; ötekiler tam dosya adı.
GUVENLI_YOLLAR: tuple[str, ...] = (
    "docs/",
    "tests/",
    "tools/",
    ".github/",
    "README.md",
    "README.en.md",   # aynı sayfanın İngilizcesi; pakete o da girmiyor
    "KURULUM.md",
    "GUNCELLEME.md",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    "requirements-dev.txt",   # yalnız test/derleme aracı; çalışma zamanına girmiyor
    # Ajan/geliştirici düzeni; `.spec` yalnız app.py'nin import zincirini
    # izliyor ve o zincir buraya hiç uğramıyor. Listede OLMASALAR yalnız depo
    # haritasını yenileyen bir commit sürüm artırıp yayın tetiklerdi.
    "CLAUDE.md",
    ".claude/",
)

SEVIYELER = ("yok", "yama", "minor", "major")

# Commit metnine yazılan elle geçersiz kılmalar.
# Veto markörü SATIRI BİTİRMEK ZORUNDA ($ + re.M): "… kapatildi [yayin: yok]"
# bir direktiftir, "[yayin: yok] artik yalniz kendi merge'ini susturuyor" ise
# ondan SÖZ EDEN bir başlık. Ayrım olmadan, v0.18.0'dan sonra vetonun kapsamını
# daraltan commit'in kendisi vetolandı — üstelik iki kez, çünkü GitHub aynı
# metni merge commit'inin gövdesine de yazıyor. Çapa satır sonunda; deponun tek
# gerçek kullanımı (başlığın SONUNA eklemek) korunuyor, `^…$` (markör yalnız
# kendi satırında) onu bozardı.
_YAYIN_YOK = re.compile(r"\[yayin:\s*yok\][ \t\r]*$", re.I | re.M)
_SEVIYE = re.compile(r"\[surum:\s*(major|minor|yama|patch)\]", re.I)
# Conventional Commits başlığı: "feat(android)!: ..." / "fix: ..."
_BASLIK = re.compile(r"^(?P<tip>[a-zA-Z]+)(?:\([^)]*\))?(?P<kir>!)?:", re.M)
_KIRICI = re.compile(r"^BREAKING[ -]CHANGE:", re.M | re.I)
_NOT = re.compile(r"^\s*\[not\]\s*(.+)$", re.M)
# Birleştirme commit'inin başlığı: "Merge pull request #40 from Zenginby/claude/…",
# "Merge branch 'main' into …". Conventional Commits öneki YOK, o yüzden
# `degisiklik_notlari` içindeki tip süzgeci bunları eleyemiyor ve başlık ham
# hâliyle GUNCELLEME.md'ye düşüyor (v0.5.3'te gerçekten oldu: kullanıcıya
# yazılmış bir belgeye ham dal adı girdi). Squash-merge edilen sürümlerde bu
# commit hiç oluşmadığı için hata o güne kadar görünmedi.
_BIRLESTIRME = re.compile(r"^Merge\s+(?:pull request|branch|remote-tracking|commit|tag)\b", re.I)

_SURUM = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def ayristir(surum: str) -> tuple[int, int, int]:
    """'v0.4.2' ya da '0.4.2' → (0, 4, 2). Biçim bozuksa ValueError."""
    m = _SURUM.match(surum.strip())
    if not m:
        raise ValueError(f"MAJOR.MINOR.PATCH bekleniyordu: {surum!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def en_yeni_tag(taglar: list[str]) -> str | None:
    """Biçime uyan tag'lerin en YÜKSEĞİ (sözlük sırası değil sayısal).

    Sözlük sırası burada gerçek bir tuzak: 'v0.10.0' < 'v0.9.0' derdi ve
    onuncu minör sürümde hat sessizce yanlış tag'e bakmaya başlardı.
    """
    uygun = []
    for t in taglar:
        try:
            uygun.append((ayristir(t), t))
        except ValueError:
            continue          # v-önekli olmayan ya da bozuk tag'ler yok sayılır
    if not uygun:
        return None
    return max(uygun)[1]


def sonraki(surum: str, seviye: str) -> str:
    """(0,4,2) + 'minor' → '0.5.0'."""
    buyuk, kucuk, yama = ayristir(surum)
    if seviye == "major":
        return f"{buyuk + 1}.0.0"
    if seviye == "minor":
        return f"{buyuk}.{kucuk + 1}.0"
    if seviye == "yama":
        return f"{buyuk}.{kucuk}.{yama + 1}"
    if seviye == "yok":
        return f"{buyuk}.{kucuk}.{yama}"
    raise ValueError(f"bilinmeyen seviye: {seviye!r}")


def yol_guvenli(yol: str) -> bool:
    """Bu dosya pakete giriyor mu? (True = girmiyor, yayın gerekmez)"""
    for kalip in GUVENLI_YOLLAR:
        if kalip.endswith("/"):
            if yol.startswith(kalip):
                return True
        elif yol == kalip:
            return True
    return False


def _seviye_commitlerden(commitler: list[str]) -> str:
    """Conventional Commits'ten seviye çıkarır; tip yoksa 'yama'.

    Tipsiz başlık 'yayınlanacak bir şey yok' DEĞİL 'yama' sayılıyor: bu depoda
    tipsiz başlıklar kullanıcıyı doğrudan etkileyen düzeltmeler oldu.
    """
    seviye = "yama"
    for metin in commitler:
        if _KIRICI.search(metin):
            return "major"
        m = _BASLIK.search(metin)
        if not m:
            continue
        if m.group("kir"):
            return "major"
        if m.group("tip").lower() == "feat":
            seviye = "minor"
    return seviye


def _elle_seviye(commitler: list[str]) -> str | None:
    """`[surum: minor]` gibi bir geçersiz kılma varsa EN GÜÇLÜSÜNÜ döndürür."""
    bulunan = None
    for metin in commitler:
        m = _SEVIYE.search(metin)
        if not m:
            continue
        s = m.group(1).lower()
        s = "yama" if s == "patch" else s
        if bulunan is None or SEVIYELER.index(s) > SEVIYELER.index(bulunan):
            bulunan = s
    return bulunan


def karar(
    *,
    mevcut_surum: str,
    son_tag: str | None,
    commitler: list[str],
    tetikleyen_commitler: list[str],
    degisen_yollar: list[str],
) -> dict[str, object]:
    """Yayın kararı. Saf fonksiyon — git'e, ağa, dosya sistemine dokunmaz.

    Dönen sözlük:
      yayinla  (bool)  — yayın oluşturulacak mı
      surum    (str)   — yayınlanacak sürüm ("0.5.0")
      artir    (bool)  — version.py'ye yazma gerekiyor mu
      seviye   (str)   — 'yok' | 'yama' | 'minor' | 'major'
      gerekce  (str)   — koşu özetine basılan Türkçe açıklama
    """
    if son_tag is None:
        # Hiç tag yok: version.py ne diyorsa o yayınlanır. Depoyu ilk kez
        # yayına açan durum ve tag'leri elle temizlenmiş bir depo da buraya
        # düşer — ikisinde de doğru davranış "elimizdekini yayınla".
        return {
            "yayinla": True,
            "surum": mevcut_surum,
            "artir": False,
            "seviye": "yok",
            "gerekce": f"Hiç sürüm tag'i yok — version.py'deki {mevcut_surum} yayınlanacak.",
        }

    mevcut = ayristir(mevcut_surum)
    sonuncu = ayristir(son_tag)

    if mevcut > sonuncu:
        # 1. KURAL — kendi kendini onarma. Modül başlığındaki gerekçe.
        return {
            "yayinla": True,
            "surum": mevcut_surum,
            "artir": False,
            "seviye": "yok",
            "gerekce": (
                f"version.py ({mevcut_surum}) son tag'in ({son_tag}) ilerisinde — "
                "bu sürüm henüz yayınlanmamış. Artırma yok, olduğu gibi yayınlanacak."
            ),
        }

    if mevcut < sonuncu:
        # 3. KURAL — anomali. Sürüm geri gitmez.
        taban = ".".join(str(p) for p in sonuncu)
        seviye = _elle_seviye(commitler) or _seviye_commitlerden(commitler)
        return {
            "yayinla": True,
            "surum": sonraki(taban, seviye),
            "artir": True,
            "seviye": seviye,
            "gerekce": (
                f"UYARI: version.py ({mevcut_surum}) son tag'in ({son_tag}) GERİSİNDE. "
                f"Sürüm geri gitmez; {son_tag} tabanından {seviye} artırıldı."
            ),
        }

    # 2. KURAL — version.py son tag'le aynı.
    #
    # Veto YALNIZ bu itmenin getirdiği commit'lerde aranıyor, aralığın
    # tamamında DEĞİL. Fark kozmetik değil: veto yeni tag atılmasını da
    # engellediği için etiketi taşıyan commit pencereden hiç çıkmıyordu ve
    # ondan sonraki HER merge sessizce yayınsız kalıyordu (v0.17.3'ten sonra
    # gerçekten oldu — bkz. tests/test_surum_karari.py'deki
    # test_onceki_bir_turun_yayin_yok_etiketi_bu_merge_i_susturmuyor).
    # Seviye tespiti ise BİLEREK tüm aralığa bakmaya devam ediyor: yayınlanmamış
    # bir `feat:` sonraki yayında da minörü hak ediyor.
    if any(_YAYIN_YOK.search(m) for m in tetikleyen_commitler):
        return {
            "yayinla": False,
            "surum": mevcut_surum,
            "artir": False,
            "seviye": "yok",
            "gerekce": "Commit metninde [yayin: yok] var — yayın atlandı.",
        }

    if degisen_yollar and all(yol_guvenli(y) for y in degisen_yollar):
        return {
            "yayinla": False,
            "surum": mevcut_surum,
            "artir": False,
            "seviye": "yok",
            "gerekce": (
                f"{son_tag}'den beri değişen {len(degisen_yollar)} dosyanın hiçbiri "
                "pakete girmiyor (belge/test/CI) — yayın gerekmiyor."
            ),
        }

    if not degisen_yollar:
        return {
            "yayinla": False,
            "surum": mevcut_surum,
            "artir": False,
            "seviye": "yok",
            "gerekce": f"{son_tag}'den beri değişen dosya yok — yayın gerekmiyor.",
        }

    elle = _elle_seviye(commitler)
    seviye = elle or _seviye_commitlerden(commitler)
    yeni = sonraki(mevcut_surum, seviye)
    nasil = "commit metnindeki [surum: …] ile" if elle else "commit tiplerinden"
    return {
        "yayinla": True,
        "surum": yeni,
        "artir": True,
        "seviye": seviye,
        "gerekce": (
            f"{son_tag} → v{yeni} ({seviye}, {nasil}). "
            f"{len(degisen_yollar)} dosya değişti."
        ),
    }


def degisiklik_notlari(commitler: list[str]) -> list[str]:
    """GUNCELLEME.md'ye yazılacak Türkçe madde listesi.

    Öncelik sırası bilinçli: commit metninde `[not] …` satırı varsa YALNIZCA o
    kullanılır. Gerekçe — otomatik üretilen "fix(ci): ABI kapısı aapt2'nin tek
    tırnağını da silsin" satırı kullanıcı için hiçbir şey ifade etmiyor; oysa
    GUNCELLEME.md'yi okuyan kişi teknik ekip değil. `[not]` satırı, yazan kişiye
    "bunu kullanıcı görecek" demenin ucuz yolu.

    `[not]` hiç yoksa commit başlıkları kullanılır; Conventional Commits tipi
    varsa atılır (kullanıcı 'feat(android):' önekini okumak zorunda değil) ve
    yalnızca gerçekten kullanıcıya bir şey söyleyen tipler alınır. Birleştirme
    commit'leri de atılır — bkz. `_BIRLESTIRME`.
    """
    notlar: list[str] = []
    for metin in commitler:
        notlar.extend(n.strip() for n in _NOT.findall(metin))
    if notlar:
        return notlar

    atilacak = {"chore", "ci", "test", "docs", "build", "style", "refactor"}
    for metin in commitler:
        baslik = metin.strip().splitlines()[0].strip() if metin.strip() else ""
        if not baslik:
            continue
        # Squash-merge başlığındaki "(#36)" numarası kullanıcıya bir şey demiyor.
        baslik = re.sub(r"\s*\(#\d+\)\s*$", "", baslik)
        # Birleştirme başlığı kullanıcıya hiçbir şey söylemiyor; dalın kendi
        # commit'leri zaten aynı `git log` çıktısında, notlar oradan geliyor.
        if _BIRLESTIRME.match(baslik):
            continue
        m = _BASLIK.match(baslik)
        if m:
            if m.group("tip").lower() in atilacak:
                continue
            baslik = baslik[m.end():].strip()
        if baslik:
            notlar.append(baslik)
    return notlar


# --------------------------------------------------------------------------
# CI kabuğu: git'i okuyup kararı GITHUB_OUTPUT'a yazan ince katman.
# Buradaki hiçbir satır karar VERMİYOR — hepsi yukarıdaki saf fonksiyonlara
# girdi topluyor. Test edilecek şey orada, burada değil.
# --------------------------------------------------------------------------

def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _cikti_yaz(karar_sozlugu: dict[str, object]) -> None:
    hedef = os.environ.get("GITHUB_OUTPUT")
    satirlar = {
        "yayinla": "evet" if karar_sozlugu["yayinla"] else "hayir",
        "surum": karar_sozlugu["surum"],
        "artir": "evet" if karar_sozlugu["artir"] else "hayir",
        "seviye": karar_sozlugu["seviye"],
    }
    if hedef:
        with open(hedef, "a", encoding="utf-8") as f:
            for k, v in satirlar.items():
                f.write(f"{k}={v}\n")
    for k, v in satirlar.items():
        print(f"{k}={v}")
    print(karar_sozlugu["gerekce"])

    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write("### Sürüm kararı\n\n")
            f.write(f"{karar_sozlugu['gerekce']}\n\n")
            f.write(f"- Yayın: **{satirlar['yayinla']}**\n")
            f.write(f"- Sürüm: **{satirlar['surum']}**\n")


def tetikleyen_aralik(ebeveyn_sayisi: int) -> str:
    """Bu itmenin GETİRDİĞİ commit'lerin git aralığı.

    İki ayrı biçim, çünkü `main`'e iki ayrı yoldan yazılıyor:

    * **Birleştirme commit'i** (iki ebeveyn): `HEAD^1..HEAD` — dalın bütün
      commit'leri ARTI merge commit'i. Yalnız HEAD'e bakmak YETMEZ: bu depoda
      `[yayin: yok]` etiketi DAL commit'ine yazılıyor (`docs(faz11): …`),
      merge commit'inin metni ise "Merge pull request #N …". Dar bir kapsam
      kullanıcının niyetini kaçırır ve istenmeyen bir yayın çıkarırdı.
    * **Düz/squash itme** (tek ebeveyn): `HEAD~1..HEAD` — getirdiği tek commit
      HEAD'in kendisi.
    """
    return "HEAD^1..HEAD" if ebeveyn_sayisi >= 2 else "HEAD~1..HEAD"


def _commit_metinleri(aralik: str) -> list[str]:
    return [c for c in _git("log", aralik, "--format=%B%x00").split("\0") if c.strip()]


def _head_ebeveyn_sayisi() -> int:
    # "<head> <ebeveyn1> [<ebeveyn2>]" — ilk alan commit'in kendisi.
    return len(_git("rev-list", "--parents", "-n", "1", "HEAD").split()) - 1


def _gecmis(son: str | None) -> tuple[list[str], list[str], list[str]]:
    """(commit metinleri, bu itmenin commit metinleri, değişen yollar).

    İlk liste son tag'den HEAD'e kadar HER ŞEY (seviye ve notlar oradan
    geliyor); ikincisi yalnız bu itmenin getirdikleri (veto kapsamı).
    """
    if not son:
        return [], [], []
    commitler = _commit_metinleri(f"{son}..HEAD")
    tetikleyen = _commit_metinleri(tetikleyen_aralik(_head_ebeveyn_sayisi()))
    yollar = [y for y in _git("diff", "--name-only", f"{son}...HEAD").splitlines() if y]
    return commitler, tetikleyen, yollar


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import version  # noqa: E402  (yol yukarıda kuruluyor)

    taglar = _git("tag", "--list", "v*").splitlines()
    son = en_yeni_tag(taglar)

    # `--notlar`: GUNCELLEME.md'ye yazılacak maddeleri satır satır basar.
    # `surum-yaz` işi bunu okuyup `surum_yaz.py`'ye argüman olarak veriyor —
    # böylece not üretimi de karar mantığıyla aynı yerde, aynı testlerin
    # altında kalıyor.
    if "--notlar" in sys.argv[1:]:
        commitler, _, _ = _gecmis(son)
        for n in degisiklik_notlari(commitler):
            print(n)
        return 0

    elle_surum = (os.environ.get("ELLE_SURUM") or "").strip()

    if elle_surum:
        # Elle verilen sürüm her kuralı geçersiz kılar — ama yine de geriye
        # gitmesin diye denetleniyor.
        ayristir(elle_surum)
        if son and ayristir(elle_surum) <= ayristir(son):
            print(f"HATA: elle verilen {elle_surum}, son tag {son}'den büyük olmalı",
                  file=sys.stderr)
            return 1
        _cikti_yaz({
            "yayinla": True,
            "surum": elle_surum,
            "artir": elle_surum != version.APP_VERSION,
            "seviye": "yok",
            "gerekce": f"Sürüm elle verildi: {elle_surum}.",
        })
        return 0

    commitler, tetikleyen, yollar = _gecmis(son)

    _cikti_yaz(karar(
        mevcut_surum=version.APP_VERSION,
        son_tag=son,
        commitler=commitler,
        tetikleyen_commitler=tetikleyen,
        degisen_yollar=yollar,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
