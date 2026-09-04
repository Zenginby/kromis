"""Arama yüklemini GERÇEKTEN koşturan test — kaynak mandalı değil.

NEDEN AYRI BİR DOSYA VE NEDEN NODE: `tests/test_index.py`deki mandallar
`folders.js`in ŞEKLİNİ kanıtlıyor — yüklemin klasör alanını zincirden aldığını,
belleğin tazelendiğini. Hiçbiri `Bayram`daki bir görselin `kampanyalar`
sorgusuyla gerçekten DÖNDÜĞÜNÜ kanıtlamıyor. `folderPath`in döngü muhafızı ince
biçimde yanlış olsa, `slice(0, -1)` bir kaysa ya da bellek bayat nesne döndürse
o iddiaların hepsi yeşil kalırdı — bu depo tam o kusur sınıfına tur yaktı
(§0.6/§0.7/§0.9 ve Tur G'nin "sessizce ölen mandal" dersi).

Playwright'in aksine bu dosya CI'DA GERÇEKTEN KOŞUYOR: `_test.yml`in koştuğu
`ubuntu-latest` imajı Node ile geliyor. Node bulunmayan bir kurulumda temiz bir
SKIP üretiliyor ve kaynak mandalları görevde kalıyor.

BU TESTİN DE KANITLAYAMADIĞI: yüklemi `refreshSearch`/`pickerFilter`in doğru
`q` ile çağırdığı, `loadFolders`ın sıfırlamaya gerçekten bağlı olduğu ve
sayaçların ekrana çizildiği. Onlar kaynak mandallarında ve
`test_playwright_studio.py`de.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

import app as appmod

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    NODE is None, reason="node yok — yüklem yalnız KAYNAK düzeyinde sınanıyor")

# `node -e` için üst sınır. İKİ AYRI SÜREYİ KARIŞTIRMAMAK için cömert:
# ölçülen iş (yüklemi birkaç kayıt üzerinde koşturmak) mikrosaniyeler sürüyor,
# bütçenin tamamı `node.exe`nin AÇILMASINA gidiyor. Windows runner'ında ilk
# açılış Defender taramasıyla birlikte on saniyeyi aşabiliyor: 2026-09-04'te
# v0.13.1 yayını tam olarak buna düştü — `build.ps1`in paketlemeden önce
# koşturduğu takımda bu dosyanın İLK testi (yani takımdaki ilk node çağrısı)
# 10 sn'de zaman aşımına uğradı, pytest kırmızı oldu ve Windows paketi hiç
# üretilmedi. Aynı test aynı kodla dakikalar önce PR koşusunda geçmişti.
#
# Sınırın KENDİSİ yine de bir iddianın parçası ve kaldırılamaz: döngüsel bir
# klasör zinciri `folderPath`i sonsuz döndürürse takım KİLİTLENMEK yerine
# DÜŞMELİ (bkz. test_a_cyclic_parent_chain_terminates). O kusur sonsuz sürer,
# yani 10 ile 60 arasındaki fark onu yakalamayı hiç etkilemiyor — takımın
# tamamı ~60 sn, asılı kalan bir node oradan gizlenemez.
NODE_ZAMAN_ASIMI = 60

# Yüklemin gerçekten bağlı olduğu bildirimler. Liste ELDE tutuluyor ki bir gün
# yüklem yeni bir yardımcıya dayandığında kesim SESSİZCE eksik kalmasın:
# eksik bir bildirim aşağıda ReferenceError'a değil, AÇIK bir iddiaya çarpıyor.
BILDIRIMLER = (
    "const KLASOR_AYRACI",
    "const parentOf",
    "const folderById",
    "const zincirBellegi",
    "function zincirBellegiSifirla(",
    "function folderPath(",
    "function folderPathParts(",
    "function klasorZinciriEtiketi(",
    "function matchesSearch(",
)


def _folders_js() -> str:
    return TestClient(appmod.app).get("/static/folders.js").text


def _dengeli(src: str, capa: str) -> str:
    """`capa`dan başlayıp bildirimi KAPANDIĞI yerde biten dilim.

    `test_index.py:_balanced_body`nin aynısı, ama tanımın kendisini de
    döndürüyor: buradaki amaç iddia kurmak değil ÇALIŞTIRILABİLİR kaynak
    üretmek, yani `function foo(...) {...}` bütünüyle gerekiyor.
    """
    bas = src.find(capa)
    assert bas >= 0, f"{capa} bulunamadı"
    if capa.startswith("const "):
        son = src.find(";", bas)
        assert son > 0, f"{capa} noktalı virgülle bitmiyor"
        return src[bas:son + 1]
    ac = src.find("{", bas)
    assert ac > 0, f"{capa} gövdesiz"
    derinlik = 0
    for i in range(ac, len(src)):
        if src[i] == "{":
            derinlik += 1
        elif src[i] == "}":
            derinlik -= 1
            if derinlik == 0:
                return src[bas:i + 1]
    raise AssertionError(f"{capa} gövdesi kapanmıyor")


def _kaynak() -> str:
    """GÖNDERİLEN `folders.js`ten kesilmiş, çalıştırılabilir yüklem katmanı.

    Parafraz DEĞİL: her bildirim dosyadan birebir kesiliyor. Bir bildirim
    bulunamazsa test node'a hiç girmeden düşüyor — sessizce boşalan bir kesim,
    her şeye `true` diyen bir yüklemle aynı kapıyı açardı.
    """
    js = _folders_js()
    parcalar = [_dengeli(js, b) for b in BILDIRIMLER]
    for b, p in zip(BILDIRIMLER, parcalar):
        assert p.strip(), f"{b} boş kesildi"
    return "let folderCache = [];\nlet searchQuery = \"\";\n" + "\n".join(parcalar)


def _kosturucu(govde: str) -> dict:
    """Kesilmiş yüklemi node'da koşturur; `govde` JSON basar.

    `timeout` şart ve bir iddianın parçası: döngüsel bir zincir testi takılırsa
    takım kilitlenmek yerine DÜŞMELİ. Değerin neden cömert olduğu
    `NODE_ZAMAN_ASIMI`de yazılı — sayı bir başarım bütçesi değil, bir kilit
    kapısı.
    """
    betik = _kaynak() + "\n" + govde
    sonuc = subprocess.run([NODE, "-e", betik], capture_output=True,
                           text=True, timeout=NODE_ZAMAN_ASIMI)
    assert sonuc.returncode == 0, f"node düştü:\n{sonuc.stderr}"
    return json.loads(sonuc.stdout)


# Kampanyalar > Bayram ve YEM olarak Yılbaşı > Bayram: yem, "ağaçta geçen
# herhangi bir ad" ile "gerçekten ATA olan ad" arasındaki farkı ölçüyor.
KUTUPHANE = """
folderCache = [
  { id: "k", name: "Kampanyalar", parent_id: null },
  { id: "b", name: "Bayram", parent_id: "k" },
  { id: "y", name: "Yılbaşı", parent_id: null },
  { id: "yb", name: "Bayram", parent_id: "y" },
];
const KAYITLAR = {
  alt:   { id: "1", prompt: "kırmızı balon", size: "1024x1024", folder_id: "b" },
  yem:   { id: "2", prompt: "mavi balon",    size: "1024x1024", folder_id: "yb" },
  kok:   { id: "3", prompt: "yeşil balon",   size: "1024x1024", folder_id: null },
  sarkan:{ id: "4", prompt: "sarı balon",    size: "1024x1024", folder_id: "yok-boyle" },
};
"""


def _sorgu(sorgular: dict[str, tuple[str, str]]) -> dict:
    """{ad: (kayıt, sorgu)} → {ad: bool}."""
    satirlar = ", ".join(
        f'"{ad}": matchesSearch(KAYITLAR.{kayit}, {json.dumps(q)})'
        for ad, (kayit, q) in sorgular.items())
    return _kosturucu(KUTUPHANE + f"console.log(JSON.stringify({{ {satirlar} }}));")


def test_an_ancestor_folder_name_finds_the_images_in_its_subfolder():
    """KABUL ÖLÇÜTÜ, koşturulmuş hâli.

    Kullanıcı kart rozetinde "Kampanyalar / Bayram" okuyup üst klasörün adını
    aratıyor. Eskiden yüklem yalnız `folder.name`e (yaprağa) bakıyordu ve sonuç
    boş dönüyordu.
    """
    assert _sorgu({"ata": ("alt", "kampanyalar")})["ata"] is True, (
        "üst klasörün adı alt klasördeki görseli bulmuyor")


def test_the_leaf_folder_name_still_finds_its_own_images():
    """Zincire açılmak eski davranışı GÖTÜRMÜYOR."""
    assert _sorgu({"yaprak": ("alt", "bayram")})["yaprak"] is True


def test_a_sibling_branch_is_not_dragged_in_by_the_ancestor_query():
    """Eşleşen ATA, "ağaçta geçen herhangi bir ad" DEĞİL.

    `Yılbaşı / Bayram` da bir "Bayram" ama atası Kampanyalar değil. Bu satır
    olmadan "zincir aranıyor" iddiası, tüm klasör adlarını tek samanlığa döken
    bir hatayı da geçirirdi.
    """
    assert _sorgu({"yem": ("yem", "kampanyalar")})["yem"] is False


def test_a_query_matching_nothing_returns_false():
    """NEGATİF KONTROL: her şeye `true` diyen bir kesim bu satırda düşer.

    Kesim sessizce boşalırsa (bildirim adı değişti, dilim kaydı) node'da
    `matchesSearch` tanımsız kalır ve koşucu zaten patlar; bu iddia ötekini
    kapatıyor — yüklemin gerçekten AYIRT ETTİĞİNİ.
    """
    assert _sorgu({"yok": ("alt", "zzz-hicbir-sey")})["yok"] is False


def test_the_caption_string_can_be_pasted_back_into_the_search_box():
    """Künyeyi olduğu gibi yapıştırmak çalışıyor.

    Ayraç yüklemde satır içine yazılmıyor, `klasorZinciriEtiketi`ten geliyor —
    yani samanlık ile künye AYNI dizeyi üretiyor. Bu satır o dikişi ölçüyor.
    """
    sonuc = _sorgu({
        "tam": ("alt", "kampanyalar / bayram"),
        "ayraci_asan": ("alt", "lar / bay"),
    })
    assert sonuc["tam"] is True, "künye yapıştırılınca eşleşmiyor"
    assert sonuc["ayraci_asan"] is True, "samanlık ayraçta kopuyor"


def test_a_root_image_matches_its_prompt_but_carries_no_folder_word():
    """Kök görselin "Klasörsüz" rozeti ARANAMIYOR — kararın yürütülmüş hâli.

    Aynı kusur SINIFI (ekranda yazan kelime aranamıyor) ama ayrı bir sonuç
    kümesi değişikliği: taze bir kütüphanede her görsel klasörsüz olduğu için o
    sorgu kütüphanenin TAMAMINI döndürür ve kendi ölçümünü ister. Kuyrukta
    kendi maddesi var; burada bir inanç değil BUGÜNKÜ davranış kayıtlı.
    """
    sonuc = _sorgu({"prompt": ("kok", "yeşil"), "klasorsuz": ("kok", "klasörsüz")})
    assert sonuc["prompt"] is True
    assert sonuc["klasorsuz"] is False, (
        "kök görsel 'klasörsüz' ile eşleşiyor: davranış değişmişse kuyruk "
        "maddesi kapanmış demektir, bu iddia da yeniden yazılmalı")


def test_a_dangling_folder_id_matches_on_prompt_without_throwing():
    """Silinmiş klasöre işaret eden kayıt patlamıyor.

    `folderById` null döner, zincir boş kalır: görsel yalnız prompt/boyutla
    eşleşir. Kartın rozeti de aynı durumda "Klasörsüz" yazıyor, yani ekran ile
    arama uyumlu.
    """
    sonuc = _sorgu({"prompt": ("sarkan", "sarı"), "klasor": ("sarkan", "kampanyalar")})
    assert sonuc["prompt"] is True
    assert sonuc["klasor"] is False


def test_a_cyclic_parent_chain_terminates():
    """Döngüsel `parent_id` zinciri SONLANIYOR — muhafız gerçekten çalışıyor.

    Sunucuda yeniden ebeveynleme ucu yok (`folders.py`), yani döngü ancak elle
    bozulmuş bir `folders.json` ile oluşur. Yine de: bir döngü burada takılırsa
    kullanıcının arama kutusu her tuşta kilitlenirdi.

    İDDİA `subprocess` ZAMAN AŞIMININ KENDİSİ: takılan bir yürüyüş testi
    düşürüyor, takımı kilitlemiyor. Bellek ayrıca döngünün bedelini tuş başına
    N×(F+3) kez değil BİR kez ödetiyor.
    """
    sonuc = _kosturucu("""
      folderCache = [
        { id: "a", name: "A", parent_id: "b" },
        { id: "b", name: "B", parent_id: "a" },
      ];
      const rec = { id: "1", prompt: "p", size: "s", folder_id: "a" };
      console.log(JSON.stringify({ a: matchesSearch(rec, "a"), p: matchesSearch(rec, "p") }));
    """)
    assert sonuc["p"] is True, "döngülü zincirde prompt eşleşmesi de kayboldu"
    assert sonuc["a"] is True, "döngü muhafızı zinciri tümden yutmuş"


def test_renaming_a_folder_is_searchable_only_after_the_memo_reset():
    """Belleğin geçersizlenmesi ÖLÇÜLÜYOR, varsayılmıyor.

    `renameCurrentFolder` `loadFolders()` çağırmıyor ve önbellekteki nesnenin
    `name`ini yerinde değiştiriyor — dizinin iki atamasının yanındaki ÜÇÜNCÜ
    yazar. Sıfırlama olmasaydı kullanıcı YENİ adı aratınca hiçbir şey bulamaz,
    ESKİ adı aratınca sonuç almaya devam ederdi. Aşağıdaki iki aşama tam olarak
    o iki cümleyi koşturuyor.
    """
    sonuc = _kosturucu(KUTUPHANE + """
      const rec = KAYITLAR.alt;
      matchesSearch(rec, "kampanyalar");              // belleği doldur
      folderById("k").name = "Promosyonlar";          // renameCurrentFolder'ın yaptığı
      const bayat = { yeni: matchesSearch(rec, "promosyonlar"),
                      eski: matchesSearch(rec, "kampanyalar") };
      zincirBellegiSifirla();
      const taze = { yeni: matchesSearch(rec, "promosyonlar"),
                     eski: matchesSearch(rec, "kampanyalar") };
      console.log(JSON.stringify({ bayat, taze }));
    """)
    assert sonuc["bayat"] == {"yeni": False, "eski": True}, (
        "testin ÖNCÜLÜ düştü: bellek sıfırlanmadan bayat kalmıyorsa bu turun "
        "sıfırlama satırı da gereksiz demektir")
    assert sonuc["taze"] == {"yeni": True, "eski": False}, (
        "sıfırlamadan sonra bile eski ad aranabiliyor: `zincirBellegiSifirla` "
        "belleği gerçekten boşaltmıyor")


def test_the_separator_is_never_written_twice():
    """Ayraç TEK sabitte: samanlık ile künye aynı dizeyi üretmek zorunda."""
    assert _folders_js().count('" / "') == 1, (
        "ayraç ikinci kez satır içi yazılmış: künye ile arama ayrışabilir")


def test_the_extracted_layer_is_the_shipped_source():
    """Kesim GÖNDERİLEN dosyadan geliyor, elle yazılmış bir kopyadan değil.

    Bu dosyanın tamamı bu satıra dayanıyor: kesim bir gün elle tutulan bir
    kopyaya kayarsa yukarıdaki dokuz test hâlâ yeşil koşar ama artık uygulamayı
    ölçmez.
    """
    js = _folders_js()
    for bildirim in BILDIRIMLER:
        assert bildirim in js, f"{bildirim} artık folders.js'te yok"
    kaynak = _kaynak()
    assert "function matchesSearch(rec, q = searchQuery)" in kaynak
    assert re.search(r"return `\$\{prompt\} \$\{klasorZinciri\} \$\{size\}`", kaynak), (
        "kesilen yüklem beklenen samanlığı kurmuyor")
