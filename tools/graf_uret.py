#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Depo haritası — `docs/graflar/` altındaki grafları STATİK tarama ile üretir.

NEDEN VAR: bu depo onlarca Python modülü, kırka yakın HTTP uç noktası, bir
tutam tarayıcı betiği ve altmıştan fazla test dosyasından oluşuyor; `app.py`
tek başına deponun en büyük dosyası. (Güncel sayılar burada DEĞİL, üretilen
`docs/graflar/README.md`'de — yoksa bu yorum ilk değişiklikte yanlışa döner.)
"Bu değişiklik neyi kırar?" sorusunun cevabı hiçbir yerde YAZILI DEĞİLDİ:
her seferinde grep'le yeniden keşfediliyordu ve keşif eksik kalıyordu — örneğin
`/api/history`'nin `folders` modülüne dokunduğu ancak `storage`'ı okuyan biri
tarafından fark ediliyordu. Graflar o keşfi bir kez yapıp DEPOYA yazıyor.

NEDEN ÜRETİLEN (elle yazılan DEĞİL): elle tutulan bir mimari belgesi kaçınılmaz
olarak yanlışa döner ve yanlış harita, hiç harita olmamasından kötüdür — çünkü
güvenilir görünür. Buradaki her satır kaynaktan okunuyor; `--kontrol` kipi
belgelerin kaynakla aynı olduğunu KANITLIYOR ve `tests/test_graflar.py` bunu
CI kapısına bağlıyor. Yani harita bayatlarsa takım kırmızıya döner.

NEDEN AST (regex DEĞİL) — Python tarafında: `import azure_client as ac` takma
adı ve `from models import GenerateRequest` gibi ad ithalleri regex'le doğru
çözülemez; oysa uç nokta→modül kenarlarının tamamı bu çözüme dayanıyor.
`tests/test_encoding_contract.py` aynı gerekçeyle AST kullanıyor.

NEDEN REGEX — tarayıcı tarafında: depoda JS ayrıştırıcısı yok ve bir tane
eklemek üçüncü parti bağımlılık demek. Betikler küresel kapsamda yükleniyor
(bkz. static/index.html'in script sırası), yani "üst düzey işlev tanımı" ile
"başka dosyada o adın çağrılması" desenleri kararlı biçimde okunabiliyor.
SINIRI AÇIKÇA YAZILI: yerel bir değişken küresel bir işlevle aynı adı taşırsa
kenar fazla sayılabilir — graf bu yüzden AĞIRLIKLI (kaç ad) veriliyor, kesin
sayı değil yön ve yoğunluk okunsun diye.

DETERMİNİST: çıktıda tarih/saat YOK ve her liste sıralı. Zaman damgası olsaydı
`--kontrol` her koşuda farklı sonuç verir, kapı da anlamsızlaşırdı.

Satır sonu AÇIKÇA LF (`newline="\\n"`): bu depo CRLF'ten iki kez yandı
(bkz. .gitattributes). Windows'ta üretilen bir graf CRLF ile yazılsaydı
`--kontrol` sebepsiz kırmızıya döner, ağaç da sebepsiz kirli görünürdü.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Depo göreli yol, AÇIKÇA eğik çizgiyle: bu değer hem dosya yolu kurmakta
# (os.path.join Windows'ta da eğik çizgiyi kabul ediyor) hem de "/" ile
# normalleştirilmiş yollarla KARŞILAŞTIRMAKTA kullanılıyor. `os.path.join` ile
# kurulsaydı Windows'ta "docs\\graflar" olur ve o karşılaştırma sessizce
# yanlış cevap verirdi.
GRAF_DIZINI = "docs/graflar"

# Uygulamanın gerçek giriş noktaları — "kimse ithal etmiyor" listesinde
# ÖKSÜZ gibi görünmesinler diye adları burada yazılı.
GIRIS_NOKTALARI = ("app", "desktop", "android_main")


# ─────────────────────────────────────────────────────────────────────
#  Toplama — Python tarafı
# ─────────────────────────────────────────────────────────────────────
def _oku(yol: str) -> str:
    with open(os.path.join(KOK, yol), encoding="utf-8") as f:
        return f.read()


def python_dosyalari() -> dict[str, str]:
    """{modül adı: depo göreli yol} — kök, `tools/` ve `tests/` ayrı adlanır."""
    bulunan: dict[str, str] = {}
    for ad in sorted(os.listdir(KOK)):
        if ad.endswith(".py"):
            bulunan[ad[:-3]] = ad
    for dizin in ("tools", "tests"):
        tam = os.path.join(KOK, dizin)
        if not os.path.isdir(tam):
            continue
        for ad in sorted(os.listdir(tam)):
            if ad.endswith(".py") and ad != "__init__.py":
                bulunan[f"{dizin}.{ad[:-3]}"] = f"{dizin}/{ad}"
    return bulunan


def _yerel_ad(hedef: str, yerel: dict[str, str]) -> str | None:
    """`import x` / `from x import y`'deki modülü depo modülüne çevirir."""
    if hedef in yerel:
        return hedef
    kok_parca = hedef.split(".")[0]
    return kok_parca if kok_parca in yerel else None


def ithaller(kaynak: str, yol: str, yerel: dict[str, str]) -> tuple[
        dict[str, str], dict[str, str], dict[str, str]]:
    """(kenarlar, takma adlar, ad→modül) üçlüsünü verir.

    * kenarlar   : {modül: "modül"|"erteli"} — erteli = işlev/sınıf İÇİNDE
      yapılan ithal. Ayrım şart: `providers` ↔ `openai_client` döngüsü BİLEREK
      erteli bir ithalle kırılmış (bkz. providers.py'nin yorumu); ikisini aynı
      kefeye koyan bir graf var olmayan bir kusuru bildirirdi.
    * takma adlar: {"ac": "azure_client"} — uç nokta taramasının dayanağı.
    * ad→modül   : {"GenerateRequest": "models"} — `from models import ...`.
    """
    kenar: dict[str, str] = {}
    takma: dict[str, str] = {}
    ad_modul: dict[str, str] = {}

    def gez(dugum, ic: bool) -> None:
        for cocuk in ast.iter_child_nodes(dugum):
            derin = ic or isinstance(
                cocuk, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            if isinstance(cocuk, ast.Import):
                for a in cocuk.names:
                    mod = _yerel_ad(a.name, yerel)
                    if mod:
                        if ic:
                            kenar.setdefault(mod, "erteli")
                        else:
                            kenar[mod] = "modül"
                        takma[a.asname or a.name] = mod
            elif isinstance(cocuk, ast.ImportFrom) and cocuk.level == 0 and cocuk.module:
                mod = _yerel_ad(cocuk.module, yerel)
                if mod:
                    if not ic:
                        kenar[mod] = "modül"
                    else:
                        kenar.setdefault(mod, "erteli")
                    for a in cocuk.names:
                        ad_modul[a.asname or a.name] = mod
                else:
                    # `from tools import surum_yaz as sy` — ithal edilen AD bir
                    # alt modül. tests/test_surum_yaz.py tam bu biçimi kullanıyor
                    # ve yalnız `cocuk.module`'e bakan bir tarama, o iki modülü
                    # "hiçbir test ithal etmiyor" diye bildiriyordu.
                    for a in cocuk.names:
                        alt = f"{cocuk.module}.{a.name}"
                        if alt in yerel:
                            if not ic:
                                kenar[alt] = "modül"
                            else:
                                kenar.setdefault(alt, "erteli")
                            takma[a.asname or a.name] = alt
            gez(cocuk, derin)

    gez(ast.parse(kaynak, filename=yol), False)
    return kenar, takma, ad_modul


# ─────────────────────────────────────────────────────────────────────
#  Toplama — HTTP uç noktaları (app.py)
# ─────────────────────────────────────────────────────────────────────
HTTP_YONTEMLERI = ("get", "post", "put", "delete", "patch", "head", "options")


def _kullanilan_moduller(dugum, takma: dict[str, str],
                         ad_kaynaklari: dict[str, set[str]]) -> set[str]:
    """Bir işlev gövdesinin DOĞRUDAN dokunduğu depo modülleri."""
    bulunan: set[str] = set()
    for d in ast.walk(dugum):
        if isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name):
            mod = takma.get(d.value.id)
            if mod:
                bulunan.add(mod)
        elif isinstance(d, ast.Name):
            # İki kaynak: `from models import GenerateRequest` gibi ad ithalleri
            # (tür açıklamaları da buraya düşer) ve app.py'nin modül düzeyi
            # sabitleri — `OUTPUT_DIR = paths.output_dir()`. İkincisi olmadan
            # `GET /output/{filename}` rotası "hiçbir modüle dokunmuyor" gibi
            # görünüyordu; oysa yolun tamamı paths'ten geliyor.
            bulunan |= ad_kaynaklari.get(d.id, set())
    return bulunan


def uc_noktalar(kaynak: str, takma: dict[str, str],
                ad_modul: dict[str, str]) -> list[dict]:
    """app.py'deki rotaları, YARDIMCILARIYLA BİRLİKTE dokundukları modüllerle verir.

    Neden kapanış (transitive) hesabı: `POST /api/generate` gövdesinde
    `storage` adı hiç geçmiyor — kaydı `_kaydet_ve_dondur` gibi app.py içi bir
    yardımcı yapıyor. Yalnız gövdeye bakan bir harita o kenarı KAÇIRIR ve
    tam kaçırdığı yerde yanlış güven verir.
    """
    agac = ast.parse(kaynak, filename="app.py")
    islevler = {n.name: n for n in agac.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    ad_kaynaklari: dict[str, set[str]] = {ad: {mod} for ad, mod in ad_modul.items()}
    for dugum in agac.body:
        if isinstance(dugum, (ast.Assign, ast.AnnAssign)) and dugum.value is not None:
            moduller = _kullanilan_moduller(dugum.value, takma, ad_kaynaklari)
            if not moduller:
                continue
            hedefler = (dugum.targets if isinstance(dugum, ast.Assign)
                        else [dugum.target])
            for hedef in hedefler:
                if isinstance(hedef, ast.Name):
                    ad_kaynaklari.setdefault(hedef.id, set()).update(moduller)

    dogrudan: dict[str, set[str]] = {}
    ic_cagri: dict[str, set[str]] = {}
    for ad, dugum in islevler.items():
        dogrudan[ad] = _kullanilan_moduller(dugum, takma, ad_kaynaklari)
        ic_cagri[ad] = {
            d.func.id for d in ast.walk(dugum)
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
            and d.func.id in islevler and d.func.id != ad
        }

    def kapanis(ad: str) -> tuple[set[str], list[str]]:
        goruldu: set[str] = set()
        yigin = [ad]
        moduller: set[str] = set()
        while yigin:
            su = yigin.pop()
            if su in goruldu:
                continue
            goruldu.add(su)
            moduller |= dogrudan[su]
            yigin.extend(ic_cagri[su] - goruldu)
        return moduller, sorted(goruldu - {ad})

    rotalar: list[dict] = []
    for dugum in agac.body:
        if not isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sus in dugum.decorator_list:
            if not (isinstance(sus, ast.Call)
                    and isinstance(sus.func, ast.Attribute)
                    and isinstance(sus.func.value, ast.Name)
                    and sus.func.value.id == "app"
                    and sus.func.attr in HTTP_YONTEMLERI):
                continue
            if not (sus.args and isinstance(sus.args[0], ast.Constant)):
                continue
            moduller, yardimcilar = kapanis(dugum.name)
            rotalar.append({
                "yontem": sus.func.attr.upper(),
                "yol": sus.args[0].value,
                "islev": dugum.name,
                "satir": dugum.lineno,
                "moduller": sorted(moduller),
                "yardimci_sayisi": len(yardimcilar),
            })
    rotalar.sort(key=lambda r: (r["yol"], r["yontem"]))
    return rotalar


# ─────────────────────────────────────────────────────────────────────
#  Toplama — tarayıcı tarafı (static/)
# ─────────────────────────────────────────────────────────────────────
_JS_ISLEV = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)
_JS_SABIT = re.compile(
    r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\(|function)", re.M)
# Dize/şablon literalinin TAMAMI alınıyor, "yol gibi görünen parça" değil:
# core.js'de gerçek bir çağrı `\`/api/output/${ad.slice(0, -".png".length)}/download\``
# biçiminde yazılı ve içinde ÇİFT TIRNAK var. Yolu tırnaksız karakterlerle
# arayan bir kalıp o satırı sessizce kaçırıyordu — kaçırdığı da tam olarak
# indirme ucuydu.
_JS_LITERAL = re.compile(
    r"`([^`]*)`"
    r"|\"((?:[^\"\\\n]|\\.)*)\""
    r"|'((?:[^'\\\n]|\\.)*)'",
    re.S)
_SUNUCU_YOLU = re.compile(r"^/(?:api|output|assets)(?:/|$)")
_HTML_BETIK = re.compile(r"""<script[^>]*\ssrc=["']([^"']+)["']""")
_HTML_STIL = re.compile(r"""<link[^>]*\srel=["']stylesheet["'][^>]*\shref=["']([^"']+)["']""")


def _yorumsuz(metin: str) -> str:
    """Yorum SATIRLARINI atar — yorumda geçen bir adres çağrı değildir.

    core.js'in "// `/output/<id>.png` → `/api/output/<id>/download`" yorumu
    ayıklanmasaydı graf "hiçbir rotaya oturmayan çağrı" diye üç yalancı bulgu
    bildirirdi; yalancı bulgu bildiren bir harita okunmayı bırakır.

    SINIRI: yalnız satır BAŞINDAKİ yorumlar atılıyor (`//`, `/*`, `*`). Satır
    ortasındaki bir yorum kalır — `"https://..."` gibi dizeleri bozmamak için
    bilinçli tercih; depoda bugün satır ortasında adres geçen yorum yok.
    """
    return "\n".join(
        "" if s.lstrip().startswith(("//", "/*", "*")) else s
        for s in metin.splitlines())


def _yol_kalibi(yol: str) -> str:
    """`/api/chats/${id}?x=1` → `/api/chats/{}` — iki taraf aynı dile çekilsin."""
    yol = yol.split("?", 1)[0]
    yol = re.sub(r"\$\{[^}]*\}", "{}", yol)
    yol = re.sub(r"\{[^}]*\}", "{}", yol)
    return yol


def oturur(cagri: str, rota: str) -> str | None:
    """Tarayıcı çağrısı bu rotaya oturuyor mu: "tam", "önek" ya da None.

    Parça parça karşılaştırılıyor, çünkü iki taraf AYNI adresi farklı yazıyor:
    rota `/assets/{kind}/{filename}` diyor, betik `/assets/logos/${ad}`.
    Rotanın yer tutucusu her parçaya, betiğin yer tutucusu her sabite oturur.

    "önek": betik adresi elle kuruyor (`const OUTPUT_ONEKI = "/output/"`).
    Ayrı işaretli, çünkü bunlar rotayı doğrudan çağırmıyor ama o rota
    ailesine DOKUNUYOR — eşleşmeyen sayılsalar uyarı listesi yalancı olurdu.
    """
    c = cagri.split("/")
    r = rota.split("/")
    onek = c[-1] == ""
    if onek:
        c = c[:-1]
    if len(c) > len(r):
        return None
    if len(c) < len(r):
        onek = True
    for cs, rs in zip(c, r):
        if cs == rs or rs == "{}" or cs == "{}":
            continue
        return None
    return "önek" if onek else "tam"


def _cagrilan_yollar(metin: str) -> list[str]:
    """Bir betiğin çağırdığı sunucu yolları — yorumlar ayıklanmış, kalıba çevrilmiş."""
    bulunan = set()
    for parcalar in _JS_LITERAL.findall(_yorumsuz(metin)):
        for literal in parcalar:
            if literal and _SUNUCU_YOLU.match(literal):
                bulunan.add(_yol_kalibi(literal))
    return sorted(bulunan)


def onyuz() -> dict:
    """static/ altındaki betik/stil bağlarını ve çağrılan sunucu yollarını verir."""
    dizin = os.path.join(KOK, "static")
    js_dosyalari = sorted(a for a in os.listdir(dizin) if a.endswith(".js"))
    kaynaklar = {f"static/{a}": _oku(f"static/{a}") for a in js_dosyalari}

    tanimlar = {
        yol: sorted(set(_JS_ISLEV.findall(m)) | set(_JS_SABIT.findall(m)))
        for yol, m in kaynaklar.items()
    }

    kenarlar: list[dict] = []
    for kaynak_yol, metin in sorted(kaynaklar.items()):
        for hedef_yol, adlar in sorted(tanimlar.items()):
            if hedef_yol == kaynak_yol:
                continue
            paylasilan = [ad for ad in adlar
                          if re.search(r"\b" + re.escape(ad) + r"\s*\(", metin)]
            if paylasilan:
                kenarlar.append({"kaynak": kaynak_yol, "hedef": hedef_yol,
                                 "adlar": paylasilan})

    cagrilar = {
        yol: _cagrilan_yollar(metin) for yol, metin in sorted(kaynaklar.items())
    }

    index = _oku("static/index.html")
    return {
        "betikler": [
            {"dosya": yol,
             "satir": len(kaynaklar[yol].splitlines()),
             "tanim": len(tanimlar[yol]),
             "cagrilan_yollar": cagrilar[yol]}
            for yol in sorted(kaynaklar)
        ],
        "kenarlar": kenarlar,
        "yukleme_sirasi": [y.split("?", 1)[0] for y in _HTML_BETIK.findall(index)],
        "stiller": [y.split("?", 1)[0] for y in _HTML_STIL.findall(index)],
    }


# ─────────────────────────────────────────────────────────────────────
#  Katmanlar ve döngüler (SCC + yoğunlaştırma)
# ─────────────────────────────────────────────────────────────────────
def gucel_bilesenler(kenar: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan — birbirini ithal eden modül öbekleri (döngüler)."""
    indeks: dict[str, int] = {}
    kok: dict[str, int] = {}
    yigin: list[str] = []
    yigindaki: set[str] = set()
    sonuc: list[list[str]] = []
    sayac = [0]

    def gez(v: str) -> None:
        # Özyineleme DEĞİL: 37 modülde sorun olmaz ama tekrarlı biçim, bir gün
        # depo büyüdüğünde `RecursionError` ile kırılmasın diye seçildi.
        is_yigini = [(v, iter(sorted(kenar.get(v, ()))))]
        indeks[v] = kok[v] = sayac[0]
        sayac[0] += 1
        yigin.append(v)
        yigindaki.add(v)
        while is_yigini:
            dugum, komsular = is_yigini[-1]
            ilerledi = False
            for w in komsular:
                if w not in indeks:
                    indeks[w] = kok[w] = sayac[0]
                    sayac[0] += 1
                    yigin.append(w)
                    yigindaki.add(w)
                    is_yigini.append((w, iter(sorted(kenar.get(w, ())))))
                    ilerledi = True
                    break
                if w in yigindaki:
                    kok[dugum] = min(kok[dugum], indeks[w])
            if ilerledi:
                continue
            is_yigini.pop()
            if is_yigini:
                ust = is_yigini[-1][0]
                kok[ust] = min(kok[ust], kok[dugum])
            if kok[dugum] == indeks[dugum]:
                obek = []
                while True:
                    w = yigin.pop()
                    yigindaki.discard(w)
                    obek.append(w)
                    if w == dugum:
                        break
                sonuc.append(sorted(obek))

    for v in sorted(kenar):
        if v not in indeks:
            gez(v)
    return sonuc


def katmanlar(dugumler: list[str], kenar: dict[str, set[str]]) -> dict[str, int]:
    """Her modüle derinlik verir: 0 = hiçbir depo modülüne dayanmayan taban.

    Döngüler yoğunlaştırılıyor (aynı öbekteki modüller aynı katmanda), yoksa
    "en uzun yol" tanımsız olurdu.
    """
    obekler = gucel_bilesenler({d: kenar.get(d, set()) for d in dugumler})
    obek_no = {d: i for i, obek in enumerate(obekler) for d in obek}
    obek_kenar: dict[int, set[int]] = {i: set() for i in range(len(obekler))}
    for d in dugumler:
        for h in kenar.get(d, ()):
            if h in obek_no and obek_no[h] != obek_no[d]:
                obek_kenar[obek_no[d]].add(obek_no[h])

    derinlik: dict[int, int] = {}

    def hesap(i: int, yol: frozenset) -> int:
        if i in derinlik:
            return derinlik[i]
        alt = [hesap(j, yol | {i}) for j in sorted(obek_kenar[i]) if j not in yol]
        derinlik[i] = 1 + max(alt) if alt else 0
        return derinlik[i]

    for i in range(len(obekler)):
        hesap(i, frozenset())
    return {d: derinlik[obek_no[d]] for d in dugumler}


# ─────────────────────────────────────────────────────────────────────
#  Modelin tamamı
# ─────────────────────────────────────────────────────────────────────
def graf_topla() -> dict:
    """Deponun tümünü tek bir sözlüğe okur — yazıcıların TEK girdisi."""
    hepsi = python_dosyalari()
    urun = {ad: yol for ad, yol in hepsi.items() if not ad.startswith("tests.")}

    kenarlar: dict[str, dict[str, str]] = {}
    takmalar: dict[str, dict[str, str]] = {}
    ad_modul_leri: dict[str, dict[str, str]] = {}
    satirlar: dict[str, int] = {}
    for ad, yol in sorted(urun.items()):
        kaynak = _oku(yol)
        satirlar[ad] = len(kaynak.splitlines())
        kenarlar[ad], takmalar[ad], ad_modul_leri[ad] = ithaller(kaynak, yol, urun)

    # Testler ürün grafına düğüm olarak GİRMİYOR (63 dosya grafı okunmaz
    # yapardı); yalnız hangi modülü sınadıkları kaydediliyor.
    # `tests/conftest.py` DIŞARIDA: paylaşılan fixture'lar bir modülü sınamıyor,
    # yalnız ithal ediyor (backup, paths). Sayılsaydı "bu modülün testi var"
    # der, oysa bekçisi yoktur.
    test_haritasi: dict[str, list[str]] = {ad: [] for ad in urun}
    test_dosyalari = sorted(ad for ad in hepsi
                            if ad.startswith("tests.test_"))
    # Hiçbir ürün modülünü ithal ETMEYEN testler ayrıca tutuluyor, çünkü
    # aşağıdaki tabloda HİÇBİR satırda görünmüyorlar: sütun ithal ilişkisinden
    # çıkıyor, ithali olmayan test de hiçbir modülün altında listelenemiyor.
    # Sayıya giriyorlardı ama haritada yoktular ve boşluk ÖLÇÜLDÜ: PR#51
    # `ci.yml`'ın paketleme kapısına bir bekçi ekledi (test_ci_paketleme_
    # kapisi.py), CLAUDE.md "ne sınanacak?" sorusunu bu grafa yönlendiriyor ve
    # graf o bekçiyi göstermiyordu. Bu testler ARTEFAKT sınıyor (workflow
    # YAML'ı, kodlama sözleşmesi, paketleme adı, Android geri tuşu), yani
    # "modülü yok" onların kusuru değil — haritanın kör noktasıydı.
    modulsuz_testler: list[str] = []
    for ad in test_dosyalari:
        kenar, _, _ = ithaller(_oku(hepsi[ad]), hepsi[ad], urun)
        if not kenar:
            modulsuz_testler.append(hepsi[ad])
        for hedef in sorted(kenar):
            test_haritasi[hedef].append(hepsi[ad])

    duz = {ad: set(kenarlar[ad]) for ad in urun}
    kat = katmanlar(sorted(urun), duz)
    gelen: dict[str, list[str]] = {ad: [] for ad in urun}
    for ad in sorted(urun):
        for hedef in sorted(kenarlar[ad]):
            gelen[hedef].append(ad)

    dongular = [obek for obek in gucel_bilesenler(duz) if len(obek) > 1]
    dongular.sort()

    app_uc = uc_noktalar(_oku("app.py"), takmalar["app"], ad_modul_leri["app"])
    on = onyuz()

    # Tarayıcı çağrısı ↔ sunucu rotası eşlemesi. `önek` eşleşmesi ayrı
    # işaretleniyor: `/output/` gerçek bir rota değil, `/output/{filename}`
    # rotasının ön ekini elle kuran bir img src'si — ikisini aynı saymak
    # "eşleşmeyen çağrı" uyarısını yalancı yapardı.
    for r in app_uc:
        r["onyuz"] = []
    eslesmeyen: list[dict] = []
    for betik in on["betikler"]:
        for cagri in betik["cagrilan_yollar"]:
            tam = [r for r in app_uc if oturur(cagri, _yol_kalibi(r["yol"])) == "tam"]
            # Tam eşleşme varsa ön ek eşleşmeleri sayılmıyor: `/api/folders`
            # hem kendi rotasına TAM hem `/api/folders/{id}` ailesine ÖN EK
            # oturur; ikisini birden saymak sütunu şişirir, ayırt etmez.
            hedefler = tam or [r for r in app_uc
                               if oturur(cagri, _yol_kalibi(r["yol"])) == "önek"]
            if not hedefler:
                eslesmeyen.append({"dosya": betik["dosya"], "yol": cagri})
                continue
            for hedef in hedefler:
                if betik["dosya"] not in hedef["onyuz"]:
                    hedef["onyuz"].append(betik["dosya"])

    return {
        "surum": 1,
        "moduller": [
            {
                "ad": ad,
                "yol": urun[ad],
                "satir": satirlar[ad],
                "katman": kat[ad],
                "ithal": sorted(k for k, t in kenarlar[ad].items() if t == "modül"),
                "erteli_ithal": sorted(k for k, t in kenarlar[ad].items() if t == "erteli"),
                "ithal_eden": gelen[ad],
                "testler": test_haritasi[ad],
            }
            for ad in sorted(urun)
        ],
        "uc_noktalar": app_uc,
        "onyuz": on,
        "eslesmeyen_cagrilar": sorted(
            eslesmeyen, key=lambda e: (e["dosya"], e["yol"])),
        "dongular": dongular,
        "test_dosyasi_sayisi": len(test_dosyalari),
        "modulsuz_testler": modulsuz_testler,
    }


# ─────────────────────────────────────────────────────────────────────
#  Yazıcılar
# ─────────────────────────────────────────────────────────────────────
UYARI = ("<!-- ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: tools/graf_uret.py "
         "· yenilemek için: python3 tools/graf_uret.py -->")


def _kimlik(ad: str) -> str:
    """Mermaid düğüm kimliği: nokta ve eğik çizgi kimlik olarak geçersiz."""
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", ad)


def _tablo(basliklar: list[str], satirlar: list[list[str]]) -> list[str]:
    cizgi = ["| " + " | ".join(basliklar) + " |",
             "|" + "|".join(" --- " for _ in basliklar) + "|"]
    cizgi += ["| " + " | ".join(s) + " |" for s in satirlar]
    return cizgi


def moduller_md(g: dict) -> str:
    mods = g["moduller"]
    ana = [m for m in mods if not m["ad"].startswith("tools.")]
    yardimci = [m for m in mods if m["ad"].startswith("tools.")]

    s = [UYARI, "", "# Modül grafı", "",
         f"{len(mods)} Python modülü, "
         f"{sum(len(m['ithal']) for m in mods)} modül düzeyi + "
         f"{sum(len(m['erteli_ithal']) for m in mods)} erteli ithal kenarı.",
         "",
         "Katman, o modülün depo içindeki en uzun bağımlılık zincirinin uzunluğu:",
         "**katman 0 hiçbir depo modülüne dayanmaz**, en üst katman uygulamanın",
         "giriş noktasıdır. Bir modülü değiştirdiğinizde etkilenebilecek yer,",
         "onun `ithal eden` sütunudur — okuma yönü budur.", ""]

    s += ["## Uygulama", "", "```mermaid", "flowchart TD"]
    en_ust = max((m["katman"] for m in ana), default=0)
    for k in range(en_ust, -1, -1):
        obek = [m for m in ana if m["katman"] == k]
        if not obek:
            continue
        s.append(f'  subgraph katman{k}["katman {k}"]')
        for m in obek:
            s.append(f'    {_kimlik(m["ad"])}["{m["ad"]}<br/>{m["satir"]} satır"]')
        s.append("  end")
    ana_adlar = {m["ad"] for m in ana}
    for m in ana:
        for hedef in m["ithal"]:
            if hedef in ana_adlar:
                s.append(f'  {_kimlik(m["ad"])} --> {_kimlik(hedef)}')
        for hedef in m["erteli_ithal"]:
            if hedef in ana_adlar:
                s.append(f'  {_kimlik(m["ad"])} -.->|erteli| {_kimlik(hedef)}')
    s += ["```", ""]

    if g["dongular"]:
        s += ["## Döngüler", "",
              "Birbirini ithal eden öbekler. Kesikli (`erteli`) bir kenarla",
              "kırılmış döngü KUSUR DEĞİL — işlev içinde yapılan ithal, import",
              "anında bir zincir kurmuyor (bkz. providers.py'nin gerekçesi).", ""]
        for obek in g["dongular"]:
            uyeler = {m["ad"]: m for m in mods}
            erteli_var = any(h in obek for a in obek for h in uyeler[a]["erteli_ithal"])
            not_ = "erteli bir ithalle kırılmış" if erteli_var else "**modül düzeyinde kapalı**"
            s.append(f"* {' ↔ '.join(obek)} — {not_}")
        s.append("")

    s += ["## Modüller", ""]
    s += _tablo(
        ["modül", "satır", "katman", "ithal ettiği", "ithal eden", "test"],
        [[f"`{m['yol']}`", str(m["satir"]), str(m["katman"]),
          ", ".join([f"`{a}`" for a in m["ithal"]]
                    + [f"`{a}` (erteli)" for a in m["erteli_ithal"]]) or "—",
          str(len(m["ithal_eden"])), str(len(m["testler"])) or "—"]
         for m in ana])
    s.append("")

    oksuz = [m["ad"] for m in ana
             if not m["ithal_eden"] and m["ad"] not in GIRIS_NOKTALARI]
    s += ["## Giriş noktaları ve öksüzler", "",
          "Kimsenin ithal etmediği modüller. `" + "`, `".join(GIRIS_NOKTALARI)
          + "` uygulamanın giriş noktaları — geri kalanı ya bir betikten "
          "çağrılıyor ya da artık kullanılmıyor; ikincisi bir bulgudur.", ""]
    for m in ana:
        if not m["ithal_eden"]:
            etiket = ("giriş noktası" if m["ad"] in GIRIS_NOKTALARI
                      else "ithal eden yok — kullanımı elle doğrulanmalı")
            s.append(f"* `{m['ad']}` — {etiket}")
    s.append("")

    if yardimci:
        s += ["## Yardımcılar (`tools/`)", "",
              "Pakete girmiyor, çalışma zamanına dokunmuyor (bkz. tools/__init__.py).",
              "", "```mermaid", "flowchart LR"]
        for m in yardimci:
            s.append(f'  {_kimlik(m["ad"])}["{m["ad"]}"]')
            for hedef in m["ithal"] + m["erteli_ithal"]:
                s.append(f'  {_kimlik(m["ad"])} --> {_kimlik(hedef)}["{hedef}"]')
        s += ["```", ""]
    return "\n".join(s) + "\n"


def uc_noktalar_md(g: dict) -> str:
    uc = g["uc_noktalar"]
    s = [UYARI, "", "# Uç nokta grafı", "",
         f"`app.py` içinde {len(uc)} HTTP rotası. `modüller` sütunu, rotanın "
         "gövdesinin VE app.py içi yardımcılarının dokunduğu depo modülleridir "
         "— yani bir modülü değiştirirken hangi isteklerin sınanması gerektiği "
         "burada yazılı. `ön yüz` sütunu o yolu çağıran tarayıcı betiği.", "",
         "`paths` neredeyse her satırda görünüyor ve bu doğru: çıktı/varlık "
         "dizinleri app.py'nin modül düzeyi sabitlerinden akıyor "
         "(`OUTPUT_DIR = paths.output_dir()`) ve rotalar o sabiti depo "
         "modüllerine geçiriyor — yani `paths.py`'ye dokunmak gerçekten "
         "neredeyse her ucu etkiler.", ""]
    s += _tablo(
        ["yöntem", "yol", "işlev (app.py)", "modüller", "ön yüz"],
        [[r["yontem"], f"`{r['yol']}`", f"`{r['islev']}`:{r['satir']}",
          ", ".join(f"`{m}`" for m in r["moduller"]) or "—",
          ", ".join(f"`{os.path.basename(o)}`" for o in r["onyuz"]) or "—"]
         for r in uc])
    s.append("")

    # Öbekleme: 39 rotanın hepsini tek şemaya koymak okunmaz olurdu; yol
    # önekleri (ör. /api/chats) doğal öbek ve rotalar zaten öyle tasarlanmış.
    obekler: dict[str, set[str]] = {}
    for r in uc:
        parca = [p for p in r["yol"].split("/") if p and not p.startswith("{")]
        onek = "/" + "/".join(parca[:2]) if parca else "/"
        obekler.setdefault(onek, set()).update(r["moduller"])
    s += ["## Öbek → modül", "", "```mermaid", "flowchart LR"]
    for onek in sorted(obekler):
        s.append(f'  {_kimlik(onek)}["{onek}"]')
        for mod in sorted(obekler[onek]):
            s.append(f'  {_kimlik(onek)} --> {_kimlik(mod)}["{mod}"]')
    s += ["```", ""]

    sessiz = [r for r in uc if not r["onyuz"]]
    if sessiz:
        s += ["## Tarayıcıdan çağrılmayan rotalar", "",
              "Bu rotaları `static/` altındaki hiçbir betik çağırmıyor. Sebebi "
              "meşru olabilir (masaüstü/Android kabuğu, tarayıcının doğrudan "
              "açtığı adres, indirme bağlantısı) — ama ölü bir rota da böyle "
              "görünür.", ""]
        for r in sessiz:
            s.append(f"* `{r['yontem']} {r['yol']}` → `{r['islev']}`")
        s.append("")
    return "\n".join(s) + "\n"


def onyuz_md(g: dict) -> str:
    on = g["onyuz"]
    s = [UYARI, "", "# Ön yüz grafı", "",
         "Betikler küresel kapsamda, `static/index.html`'deki SIRAYLA yükleniyor "
         "— modül sistemi yok, yani bir betiğin başka bir betiğin işlevini "
         "çağırması sıradan. Aşağıdaki kenarlar o çağrılardan çıkarıldı; "
         "ağırlık, paylaşılan ad sayısıdır (yöntem ve sınırı: tools/graf_uret.py).",
         "", "## Yükleme sırası", ""]
    for i, yol in enumerate(on["yukleme_sirasi"], 1):
        s.append(f"{i}. `{yol}`")
    s += ["", "Stiller: " + ", ".join(f"`{y}`" for y in on["stiller"]), "",
          "## Betikler arası çağrı", "", "```mermaid", "flowchart LR"]
    for k in on["kenarlar"]:
        kaynak, hedef = os.path.basename(k["kaynak"]), os.path.basename(k["hedef"])
        s.append(f'  {_kimlik(kaynak)}["{kaynak}"] -->|{len(k["adlar"])}| '
                 f'{_kimlik(hedef)}["{hedef}"]')
    s += ["```", "", "## Betikler", ""]
    s += _tablo(
        ["betik", "satır", "üst düzey tanım", "çağırdığı sunucu yolları"],
        [[f"`{b['dosya']}`", str(b["satir"]), str(b["tanim"]),
          ", ".join(f"`{y}`" for y in b["cagrilan_yollar"]) or "—"]
         for b in on["betikler"]])
    s.append("")
    if g["eslesmeyen_cagrilar"]:
        s += ["## Hiçbir rotaya oturmayan çağrılar", "",
              "Tarayıcı bu yolları çağırıyor ama `app.py`'de karşılığı yok — "
              "ya yol yanlış yazılmış ya da rota kaldırılmış. Her satır "
              "bakılması gereken bir bulgudur.", ""]
        for e in g["eslesmeyen_cagrilar"]:
            s.append(f"* `{e['yol']}` ← `{e['dosya']}`")
        s.append("")
    return "\n".join(s) + "\n"


def testler_md(g: dict) -> str:
    mods = g["moduller"]
    testsiz = [m for m in mods if not m["testler"]]
    s = [UYARI, "", "# Test haritası", "",
         f"`tests/` altında {g['test_dosyasi_sayisi']} dosya. Bir modülü "
         "değiştirirken koşturulacak testler burada; sütun, test dosyasının o "
         "modülü İTHAL ETMESİNDEN çıkarıldı (kapsam ölçümü değil — hangi testin "
         "o modüle dokunduğunun haritası).", ""]
    s += _tablo(
        ["modül", "testler"],
        [[f"`{m['ad']}`", ", ".join(f"`{os.path.basename(t)}`" for t in m["testler"])
          or "—"] for m in mods])
    s += ["", "## Hiç ithal edilmeyen modüller", "",
          "Bu modülleri hiçbir test dosyası ithal etmiyor. Dolaylı olarak "
          "sınanıyor olabilirler (`import app` app'in ithal ettiği her şeyi "
          "çalıştırır), ama doğrudan bekçileri yok.", ""]
    for m in testsiz:
        s.append(f"* `{m['ad']}` ({m['satir']} satır)")
    s += ["", "## Hiçbir modülü ithal etmeyen testler", "",
          "Yukarıdaki tablonun kör noktası: sütun ithal ilişkisinden çıktığı "
          "için ithali olmayan bir test hiçbir satırda görünmez. Bu dosyalar "
          "modül değil ARTEFAKT sınıyor (workflow YAML'ı, kodlama sözleşmesi, "
          "paketleme adı, Android geri tuşu) — yani bir `.yml`e ya da bir "
          "sözleşmeye dokunuyorsan koşturulacak testler burada.", ""]
    for t in g["modulsuz_testler"]:
        s.append(f"* `{t}`")
    s.append("")
    return "\n".join(s) + "\n"


def readme_md(g: dict) -> str:
    mods = g["moduller"]
    urun_mod = [m for m in mods if not m["ad"].startswith("tools.")]
    en_buyuk = sorted(urun_mod, key=lambda m: -m["satir"])[:5]
    en_bagli = sorted(urun_mod, key=lambda m: (-len(m["ithal_eden"]), m["ad"]))[:5]
    s = [UYARI, "", "# Depo haritası (graflar)", "",
         "**Bu depoda çalışmaya başlarken ilk okunacak yer burasıdır.** Grafların "
         "tamamı kaynaktan üretiliyor; elle yazılmış bir mimari anlatısı değil, "
         "kodun o anki hâli.", "",
         "| graf | ne söyler |", "| --- | --- |",
         "| [moduller.md](moduller.md) | Python modülleri, katmanlar, ithal "
         "kenarları, döngüler, öksüzler |",
         "| [uc-noktalar.md](uc-noktalar.md) | HTTP rotaları → dokundukları "
         "modüller → onları çağıran tarayıcı betiği |",
         "| [onyuz.md](onyuz.md) | `static/` betiklerinin yükleme sırası, "
         "birbirine bağlılığı, çağırdığı sunucu yolları |",
         "| [testler.md](testler.md) | Modül → o modüle dokunan test dosyaları |",
         "| [graf.json](graf.json) | Aynı verinin makine okuyabilir hâli |", "",
         "## Ölçüler", "",
         f"* {len(mods)} Python modülü, "
         f"{sum(len(m['ithal']) for m in mods)} modül düzeyi ithal kenarı "
         f"({sum(len(m['erteli_ithal']) for m in mods)} erteli)",
         f"* {len(g['uc_noktalar'])} HTTP uç noktası",
         f"* {len(g['onyuz']['betikler'])} tarayıcı betiği, "
         f"{len(g['onyuz']['kenarlar'])} betik-arası bağ",
         f"* {g['test_dosyasi_sayisi']} test dosyası; "
         f"{sum(1 for m in mods if not m['testler'])} modülü hiçbir test ithal "
         f"etmiyor, {len(g['modulsuz_testler'])} test de hiçbir modülü "
         "(artefakt sınıyorlar; bkz. testler.md)",
         f"* {len(g['dongular'])} ithal döngüsü, "
         f"{len(g['eslesmeyen_cagrilar'])} rotaya oturmayan tarayıcı çağrısı",
         "",
         "En büyük dosyalar: "
         + ", ".join(f"`{m['ad']}` ({m['satir']})" for m in en_buyuk) + ".",
         "En çok ithal edilenler: "
         + ", ".join(f"`{m['ad']}` ({len(m['ithal_eden'])})" for m in en_bagli) + ".",
         "", "## Nasıl güncellenir", "",
         "```sh",
         "python3 tools/graf_uret.py            # yeniden üretir",
         "python3 tools/graf_uret.py --kontrol  # bayat mı? (CI kapısı bunu koşar)",
         "python3 tools/graf_uret.py --ozet     # tek ekranlık özet",
         "```", "",
         "Üç ayrı mekanizma haritanın bayatlamasını engelliyor — biri unutulsa "
         "öteki yakalar:", "",
         "1. `tests/test_graflar.py` — dosyalar kaynakla aynı değilse takım "
         "KIRMIZI. Kapı bu; her PR'da koşuyor.",
         "2. `.claude/settings.json` — Claude Code oturumunda bir `.py`/`static/` "
         "dosyası düzenlendiğinde graflar kendiliğinden yenilenir, oturum "
         "başında da bu özet gösterilir.",
         "3. `CLAUDE.md` — çalışmaya başlamadan önce buranın okunmasını söyler.",
         "", "## Statik taramanın görmediği şeyler", "",
         "Harita çalışma anını değil KAYNAĞI okuyor. Bu bilinçli (bkz. "
         "tools/graf_uret.py'nin gerekçesi), ama sınırı var:", "",
         "* Dinamik gönderim (`getattr`, sözlükten çağrılan işlev) kenar üretmez.",
         "* Şablondan/yapılandırmadan gelen bağlar (ör. `.spec` dosyasının "
         "gizli ithalleri) burada yok.",
         "* Ön yüz kenarları AD eşleşmesine dayanıyor; küresel bir işlevle aynı "
         "adı taşıyan yerel bir değişken kenarı fazla sayabilir.",
         "* Test sütunu ithal ilişkisidir, satır kapsamı DEĞİLDİR.",
         ""]
    return "\n".join(s) + "\n"


def graf_json(g: dict) -> str:
    return json.dumps(g, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


YAZICILAR = {
    "README.md": readme_md,
    "moduller.md": moduller_md,
    "uc-noktalar.md": uc_noktalar_md,
    "onyuz.md": onyuz_md,
    "testler.md": testler_md,
    "graf.json": graf_json,
}


def uret() -> dict[str, str]:
    """{depo göreli yol: içerik} — dosya sistemine DOKUNMAZ.

    Saf olması şart: `tests/test_graflar.py` diskteki dosyaları bununla
    karşılaştırıyor, yani kapı testin kendi ürettiği bir çıktıyı değil
    COMMIT'LENMİŞ dosyayı ölçüyor.
    """
    g = graf_topla()
    return {os.path.join(GRAF_DIZINI, ad).replace(os.sep, "/"): yazici(g)
            for ad, yazici in YAZICILAR.items()}


# ─────────────────────────────────────────────────────────────────────
#  Komut satırı
# ─────────────────────────────────────────────────────────────────────
def _diskteki(yol: str) -> str | None:
    try:
        with open(os.path.join(KOK, yol), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _bayatlar(dosyalar: dict[str, str]) -> list[str]:
    return sorted(yol for yol, icerik in dosyalar.items()
                  if _diskteki(yol) != icerik)


def yaz(dosyalar: dict[str, str]) -> list[str]:
    """Yalnız DEĞİŞENLERİ yazar; dokunulmamış dosyanın mtime'ı bozulmasın."""
    degisen = _bayatlar(dosyalar)
    os.makedirs(os.path.join(KOK, GRAF_DIZINI), exist_ok=True)
    for yol in degisen:
        with open(os.path.join(KOK, yol), "w", encoding="utf-8", newline="\n") as f:
            f.write(dosyalar[yol])
    return degisen


def _ozet(g: dict) -> str:
    mods = g["moduller"]
    return (
        f"Depo haritası: {GRAF_DIZINI}/README.md — {len(mods)} modül, "
        f"{len(g['uc_noktalar'])} uç nokta, "
        f"{len(g['onyuz']['betikler'])} tarayıcı betiği, "
        f"{g['test_dosyasi_sayisi']} test dosyası. "
        "Bir modüle dokunmadan önce oradaki `ithal eden` ve `test` "
        "sütunlarına bakın."
    )


def main(argv: list[str]) -> int:
    secenekler = set(argv[1:])
    bilinmeyen = secenekler - {"--kontrol", "--ozet", "--kanca", "--sessiz",
                               "--json"}
    if bilinmeyen:
        print(f"bilinmeyen seçenek: {' '.join(sorted(bilinmeyen))}\n"
              "kullanım: graf_uret.py [--kontrol|--ozet|--kanca] "
              "[--sessiz] [--json]", file=sys.stderr)
        return 2

    # Kanca kipi: Claude Code'un PostToolUse kancası JSON'u stdin'den verir.
    # İlgisiz bir dosya düzenlendiğinde hiç iş yapmıyoruz — kanca her düzenlemede
    # koşuyor ve gereksiz iş, kancanın kapatılmasına yol açan şeydir.
    if "--kanca" in secenekler:
        try:
            veri = json.loads(sys.stdin.read() or "{}")
        except (ValueError, OSError):
            veri = {}
        girdi = veri.get("tool_input") or {}
        hedef = str(girdi.get("file_path") or girdi.get("notebook_path") or "")
        if not _ilgili_dosya(hedef):
            return 0
        degisen = yaz(uret())
        if degisen:
            print("graflar yenilendi: "
                  + ", ".join(os.path.basename(y) for y in degisen))
        return 0

    if "--ozet" in secenekler:
        g = graf_topla()
        bayat = _bayatlar(uret())
        metin = _ozet(g)
        if bayat:
            metin += ("\nUYARI: graflar bayat (" + ", ".join(
                os.path.basename(y) for y in bayat)
                + ") — `python3 tools/graf_uret.py` ile yenileyin.")
        if "--json" in secenekler:
            # SessionStart kancası: düz metin de bağlama giriyor ama zarf
            # AÇIKÇA yazılı olsun — Claude Code'un belgelediği yol bu ve
            # sessizce yutulan bir çıktı, kancanın hiç çalışmamasından
            # ayırt edilemez.
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": metin}}, ensure_ascii=False))
        else:
            print(metin)
        return 0

    dosyalar = uret()
    if "--kontrol" in secenekler:
        bayat = _bayatlar(dosyalar)
        if bayat:
            print("Graflar kaynakla aynı DEĞİL:", file=sys.stderr)
            for yol in bayat:
                print(f"  {yol}", file=sys.stderr)
            print("Düzeltmek için: python3 tools/graf_uret.py", file=sys.stderr)
            return 1
        if "--sessiz" not in secenekler:
            print(f"graflar güncel ({len(dosyalar)} dosya)")
        return 0

    degisen = yaz(dosyalar)
    if "--sessiz" not in secenekler:
        if degisen:
            for yol in degisen:
                print(f"yazıldı: {yol}")
        else:
            print(f"graflar zaten güncel ({len(dosyalar)} dosya)")
    return 0


def _ilgili_dosya(yol: str) -> bool:
    """Bu dosya grafları değiştirebilir mi? (kanca kipinin tek kararı)"""
    if not yol:
        return False
    goreli = os.path.relpath(os.path.abspath(yol), KOK).replace(os.sep, "/")
    if goreli.startswith(".."):
        return False           # depo dışı
    if goreli.startswith(GRAF_DIZINI):
        return False           # grafın kendisi
    if goreli.endswith(".py"):
        return "/" not in goreli or goreli.startswith(("tools/", "tests/"))
    return goreli.startswith("static/") and goreli.endswith((".js", ".html", ".css"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
