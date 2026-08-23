"""Yayın kararının kuralları — CI koşusu harcamadan.

NEDEN BURADA: bu deponun yayın yolundaki her deneme geri dönüşsüz. v0.2.1'de
tag atıldıktan sonra üç koşu üst üste kırmızıya düştü ve ancak dördüncüsü yeşil
oldu; v0.4.2'de yayın iki ayrı workflow tarafından yazıldığı için ~95 saniye
eksik kaldı. Yayın artık main'e merge ile tetikleniyor, yani "kural yanlışsa
öğrenmenin bedeli" daha da yükseldi: yanlış bir karar ya gereksiz bir sürüm
yakar ya da yayınlanması gereken bir düzeltmeyi sessizce atlar.

O yüzden kararın TAMAMI saf bir fonksiyonda (`tools/surum_karari.py`) ve
buradaki iddialar onu saniyede, bedava sınıyor. YAML'da kalan tek şey bu
fonksiyonu çağırmak.
"""
from __future__ import annotations

import pytest

from tools import surum_karari as sk


def _karar(**kwargs):
    """Varsayılanları olan kısa yol: her test yalnız ilgilendiği alanı yazsın."""
    varsayilan = dict(
        mevcut_surum="0.4.2",
        son_tag="v0.4.2",
        commitler=["fix: bir şey"],
        degisen_yollar=["app.py"],
    )
    varsayilan.update(kwargs)
    return sk.karar(**varsayilan)


# --------------------------------------------------------------------------
# Sürüm aritmetiği
# --------------------------------------------------------------------------

def test_en_yeni_tag_sayisal_karsilastirir():
    """Sözlük sırası 'v0.10.0' < 'v0.9.0' derdi — onuncu minörde hat yanlış
    tag'e bakmaya başlar ve sürüm geri giderdi."""
    assert sk.en_yeni_tag(["v0.9.0", "v0.10.0", "v0.2.1"]) == "v0.10.0"


def test_en_yeni_tag_bozuk_taglari_yok_sayar():
    """Depoda `v*` kalıbına uyan ama sürüm olmayan bir tag bulunabilir."""
    assert sk.en_yeni_tag(["v0.4.2", "vitrin", "v1.2"]) == "v0.4.2"
    assert sk.en_yeni_tag(["deneme", "başka"]) is None


@pytest.mark.parametrize("seviye,beklenen", [
    ("major", "1.0.0"),
    ("minor", "0.5.0"),
    ("yama", "0.4.3"),
    ("yok", "0.4.2"),
])
def test_sonraki_surum(seviye: str, beklenen: str):
    assert sk.sonraki("0.4.2", seviye) == beklenen


# --------------------------------------------------------------------------
# 1. kural — kendi kendini onarma
# --------------------------------------------------------------------------

def test_version_py_tagin_ilerisindeyse_artirma_yok():
    """Paketlerden biri kırmızıya düşerse main'de artırılmış bir version.py
    kalır ama tag oluşmaz. Bir sonraki merge o sürümü İKİNCİ KEZ artırmamalı —
    yayınlanmamış olanı yayınlamalı. Bu kural olmasa her başarısız koşu bir
    sürüm numarası yakardı."""
    k = _karar(mevcut_surum="0.5.0", son_tag="v0.4.2")
    assert k["yayinla"] is True
    assert k["surum"] == "0.5.0"
    assert k["artir"] is False


def test_hic_tag_yoksa_version_py_yayinlanir():
    k = _karar(son_tag=None)
    assert k["yayinla"] is True
    assert k["surum"] == "0.4.2"
    assert k["artir"] is False


def test_version_py_tagin_gerisindeyse_surum_geri_gitmez():
    """Anomali (geri alınmış bir bump). Yayınlanmış bir sürümü ikinci kez
    üretmek, kullanıcıda AYNI sürüm numarasıyla FARKLI bir paket demek."""
    k = _karar(mevcut_surum="0.4.0", son_tag="v0.4.2", commitler=["fix: x"])
    assert k["surum"] == "0.4.3"
    assert k["artir"] is True
    assert "GERİSİNDE" in k["gerekce"]


# --------------------------------------------------------------------------
# 2. kural — seviye
# --------------------------------------------------------------------------

def test_feat_minor_artirir():
    assert _karar(commitler=["feat(android): yeni panel"])["surum"] == "0.5.0"


def test_fix_yama_artirir():
    assert _karar(commitler=["fix(ui): hizalama"])["surum"] == "0.4.3"


def test_tipsiz_turkce_baslik_yama_sayilir():
    """Bu deponun squash-merge başlıklarının bir kısmı Conventional Commits'e
    uymuyor ("Telefondaki üç arayüz kusurunu düzelt…"). Yalnız mesaja bakan bir
    ayrıştırıcı bunu "yayınlanacak bir şey yok" diye okur ve tam da
    yayınlanması gereken düzeltmeyi atlardı."""
    k = _karar(commitler=["Telefondaki üç arayüz kusurunu düzelt (#34)"])
    assert k["yayinla"] is True
    assert k["surum"] == "0.4.3"


def test_unlem_major_artirir():
    assert _karar(commitler=["feat(api)!: eski uç kaldırıldı"])["surum"] == "1.0.0"


def test_breaking_change_govdesi_major_artirir():
    k = _karar(commitler=["fix: küçük\n\nBREAKING CHANGE: veri biçimi değişti"])
    assert k["surum"] == "1.0.0"


def test_en_guclu_seviye_kazanir():
    """Bir merge aralığında hem `fix` hem `feat` varsa minör kazanmalı."""
    assert _karar(commitler=["fix: a", "feat: b", "fix: c"])["surum"] == "0.5.0"


# --------------------------------------------------------------------------
# 2. kural — "pakete giriyor mu"
# --------------------------------------------------------------------------

def test_yalniz_belge_degisirse_yayin_yok():
    k = _karar(degisen_yollar=["docs/android/mimari.md", "README.md"])
    assert k["yayinla"] is False


def test_yalniz_test_ve_ci_degisirse_yayin_yok():
    k = _karar(degisen_yollar=["tests/test_app.py", ".github/workflows/ci.yml",
                               "tools/surum_karari.py"])
    assert k["yayinla"] is False


def test_tek_bir_urun_dosyasi_bile_yayin_gerektirir():
    """version.py'nin kendi kuralı: "gönderilen HER build APP_VERSION'ı artırır
    — yalnızca bir CSS/JS düzeltmesi de olsa." Cache-buster buna bağlı."""
    k = _karar(degisen_yollar=["docs/x.md", "static/core.js"])
    assert k["yayinla"] is True


def test_pakete_giren_md_dosyasi_guvenli_sayilmaz():
    """`bundled/prompts/*.md` pakete GİREN bir .md dosyası. "Bütün .md'ler
    güvenli" diyen bir kural Prompt Yönetmeni değişikliğini sessizce yutardı."""
    assert sk.yol_guvenli("bundled/prompts/prompt-yonetmeni.md") is False
    assert sk.yol_guvenli("docs/android/mimari.md") is True


def test_ajan_duzeni_yayin_gerektirmez():
    """`CLAUDE.md` ve `.claude/` pakete girmiyor — yalnız harita yenilemek
    için atılan bir commit sürüm artırmamalı. Bekçi burada, çünkü ikisi de
    GUVENLI_YOLLAR'a SONRADAN eklendi ve beyaz listeden düşmeleri sessizce
    "her graf güncellemesi bir yayın" demeye dönerdi."""
    assert sk.yol_guvenli("CLAUDE.md") is True
    assert sk.yol_guvenli(".claude/settings.json") is True
    assert sk.yol_guvenli("docs/graflar/moduller.md") is True
    # Kaynak tarafı hâlâ yayın gerektiriyor: harita üreticisi tools/ altında,
    # ama app.py'ye dokunan bir commit graf yenilemesiyle birlikte gelirse
    # karar yine "yayınla" olmalı.
    assert sk.yol_guvenli("app.py") is False


def test_tanimadigi_yol_yayin_gerektirir():
    """GUVENLI_YOLLAR bir BEYAZ liste: belirsizlik her zaman "yayınla"
    tarafına düşmeli. Yeni bir üst dizin eklendiğinde varsayılan davranış
    "atla" olsaydı, o dizin sessizce yayının dışında kalırdı."""
    assert sk.yol_guvenli("yeni_klasor/dosya.py") is False


def test_hic_degisiklik_yoksa_yayin_yok():
    assert _karar(degisen_yollar=[])["yayinla"] is False


# --------------------------------------------------------------------------
# Elle geçersiz kılmalar
# --------------------------------------------------------------------------

def test_yayin_yok_etiketi_yayini_durdurur():
    k = _karar(commitler=["fix: acil", "[yayin: yok]"], degisen_yollar=["app.py"])
    assert k["yayinla"] is False


def test_surum_etiketi_seviyeyi_ezer():
    k = _karar(commitler=["fix: küçük görünen ama büyük değişiklik [surum: minor]"])
    assert k["surum"] == "0.5.0"


def test_surum_etiketi_patch_de_kabul_eder():
    assert _karar(commitler=["feat: x [surum: patch]"])["surum"] == "0.4.3"


# --------------------------------------------------------------------------
# GUNCELLEME.md notları
# --------------------------------------------------------------------------

def test_not_satiri_varsa_yalniz_o_kullanilir():
    """`fix(ci): ABI kapısı aapt2'nin tek tırnağını da silsin` satırı kullanıcı
    için hiçbir şey ifade etmiyor; GUNCELLEME.md'yi okuyan kişi teknik ekip
    değil."""
    notlar = sk.degisiklik_notlari([
        "fix(ci): aapt2 tırnağı\n\n[not] Telefonda kurulum hatası düzeldi.",
        "feat: başka bir şey",
    ])
    assert notlar == ["Telefonda kurulum hatası düzeldi."]


def test_not_yoksa_basliklardan_uretilir_ve_tip_oneki_atilir():
    notlar = sk.degisiklik_notlari(["feat(android): yeni panel (#42)"])
    assert notlar == ["yeni panel"]


def test_kullaniciya_bir_sey_soylemeyen_tipler_nota_girmez():
    notlar = sk.degisiklik_notlari([
        "chore(git): yazı tipleri ikili işaretlendi",
        "ci: kapı eklendi",
        "fix: hizalama düzeldi",
    ])
    assert notlar == ["hizalama düzeldi"]


def test_tipsiz_baslik_nota_oldugu_gibi_girer():
    notlar = sk.degisiklik_notlari(["Telefondaki üç arayüz kusurunu düzelt (#34)"])
    assert notlar == ["Telefondaki üç arayüz kusurunu düzelt"]


def test_birlestirme_basligi_nota_girmez():
    """v0.5.3'te GUNCELLEME.md'ye "Merge pull request #40 from Zenginby/claude/…"
    satırı yazıldı: kullanıcıya yazılmış bir belgeye ham dal adı girdi.

    Sebep, tipsiz başlığın olduğu gibi geçmesi (bir üstteki test) ile
    birleştirme commit'inin Conventional Commits öneki taşımaması. Squash-merge
    edilen sürümlerde bu commit hiç oluşmadığı için hata görünmedi; merge
    commit'iyle birleşen ilk sürümde ortaya çıktı ve her merge'de yinelerdi.
    """
    notlar = sk.degisiklik_notlari([
        "Merge pull request #40 from Zenginby/claude/gis-keystore-mobile-app-mgakyw",
        "Merge branch 'main' into ozellik",
        "fix: depo adresi yeni hesaba çevrildi",
    ])
    assert notlar == ["depo adresi yeni hesaba çevrildi"]
