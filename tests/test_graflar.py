"""`docs/graflar/` kaynakla AYNI mı — kalıcı kapı.

NEDEN VAR: elle tutulan bir mimari belgesi kaçınılmaz olarak yanlışa döner ve
yanlış bir harita, hiç harita olmamasından KÖTÜDÜR — çünkü güvenilir görünür.
Bu deponun kendi tarihi de aynı sınıf kusurla dolu: sürüm literali README'de
elle duruyordu ve v0.4.1'de geride kaldı (bkz. tests/test_version.py),
depo adresi dört dosyada elle yazılıydı ve taşınmada biri kaçtı (bkz.
tests/test_depo_adresi.py). Ders her ikisinde de aynı: TÜRETİLEN bir şeyin
bekçisi bir test olmak zorunda, yoksa gelenek olur ve gelenek unutulur.

Bu yüzden kapı ÜÇ ayrı şeyi ölçüyor:

  1. Commit'lenmiş dosyalar tazeyken üretilenle bayt bayt aynı mı (bayat harita
     kırmızı verir; düzeltmesi `python3 tools/graf_uret.py`).
  2. Tarayıcı kör mü — sayılar depodan BAĞIMSIZ biçimde yeniden ölçülüyor.
     Sessizce boş dönen bir tarayıcı, 1. testi de yeşil bırakırdı.
  3. Tarayıcının en kırılgan iki parçası (yol eşleştirici, yorum ayıklayıcı)
     doğrudan sınanıyor: ikisi de regex'e dayanıyor ve ikisi de yanlış
     çalıştığında GÜRÜLTÜSÜZ yanlış üretiyor.
"""
from __future__ import annotations

import os
import re

import pytest

from tools import graf_uret as gu

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _diskteki(yol: str) -> str:
    with open(os.path.join(REPO, yol), encoding="utf-8") as f:
        return f.read()


def test_committed_graphs_are_identical_to_a_fresh_scan():
    """Depodaki graflar, şu anki kaynaktan üretilenle aynı olmalı."""
    taze = gu.uret()
    bayat = [yol for yol, icerik in sorted(taze.items())
             if not os.path.exists(os.path.join(REPO, yol))
             or _diskteki(yol) != icerik]
    assert not bayat, (
        "Depo haritası kaynakla aynı değil: " + ", ".join(bayat)
        + "\nYenilemek için: python3 tools/graf_uret.py")


def test_the_scanner_is_not_blind():
    """Sayılar depodan BAĞIMSIZ ölçülüyor — boş dönen bir tarayıcı kapı değildir.

    1. test yalnız "diskteki dosya = üretilen dosya" der; tarayıcı hiçbir şey
    görmese o eşitlik yine kurulur. Buradaki ölçümler bu yüzden grafın kendi
    mantığını kullanmıyor: rotalar app.py'den regex'le, modüller dizin
    listesinden sayılıyor.
    """
    g = gu.graf_topla()

    with open(os.path.join(REPO, "app.py"), encoding="utf-8") as f:
        app_kaynak = f.read()
    beklenen_rota = len(re.findall(
        r"^@app\.(?:get|post|put|delete|patch|head|options)\(",
        app_kaynak, re.M))
    assert beklenen_rota > 0, "regex sayımı bozuk — testin kendisi anlamsız"
    assert len(g["uc_noktalar"]) == beklenen_rota

    kok_modul = {a[:-3] for a in os.listdir(REPO) if a.endswith(".py")}
    graf_modul = {m["ad"] for m in g["moduller"] if "." not in m["ad"]}
    assert graf_modul == kok_modul

    js = {f"static/{a}" for a in os.listdir(os.path.join(REPO, "static"))
          if a.endswith(".js")}
    assert {b["dosya"] for b in g["onyuz"]["betikler"]} == js

    # Her rota bir işleve ve gerçek bir satıra bağlı olmalı.
    for r in g["uc_noktalar"]:
        assert r["islev"] and r["satir"] > 0, r


def test_the_graph_records_the_deferred_imports_that_break_the_cycle():
    """`providers` ↔ `openai_client` döngüsü ERTELİ kenarla kırılmış olarak durmalı.

    Bu ayrım grafın en kolay kaybedilen bilgisi: iki ithal biçimini aynı sayan
    bir tarama, bilinçle kırılmış bir döngüyü kusur gibi bildirir (bkz.
    providers.py'nin gerekçesi). Kaybı ancak bu test yakalar.
    """
    moduller = {m["ad"]: m for m in gu.graf_topla()["moduller"]}
    assert "providers" in moduller["openai_client"]["ithal"]
    assert "openai_client" in moduller["providers"]["erteli_ithal"]
    assert "providers" not in moduller["openai_client"]["erteli_ithal"]


@pytest.mark.parametrize("cagri, rota, beklenen", [
    ("/api/generate", "/api/generate", "tam"),
    ("/api/chats/{}", "/api/chats/{}", "tam"),
    ("/assets/logos/{}", "/assets/{}/{}", "tam"),     # sabit ↔ yer tutucu
    ("/output/{}.png", "/output/{}", "tam"),          # tek parçanın içi serbest
    ("/api/output/{}/download", "/api/output/{}/download", "tam"),
    ("/output/", "/output/{}", "önek"),               # elle kurulan adres
    ("/api/folders", "/api/folders/{}", "önek"),
    ("/api/generate", "/api/edit", None),
    ("/api/chats/{}", "/api/chats", None),            # çağrı rotadan UZUN
])
def test_the_route_matcher_maps_written_paths_to_route_patterns(cagri, rota, beklenen):
    """Tarayıcının yazdığı adres ile rotanın kalıbı aynı dile çekilmeli.

    Eşleştirici kırılırsa graf iki yalan üretir: "bu rotayı kimse çağırmıyor"
    (ölü rota sanılır) ve "bu çağrı hiçbir rotaya oturmuyor" (var olmayan bir
    kusur bildirilir). İkisi de sessiz.
    """
    assert gu.oturur(cagri, rota) == beklenen


def test_comment_lines_are_not_read_as_calls():
    """Yorumda geçen bir adres çağrı DEĞİLDİR — core.js'de tam bu var."""
    ornek = (
        '// `/output/<id>.png` → `/api/output/<id>/download`\n'
        ' * `/api/settings` ile aynı yanıt\n'
        'const u = "/api/prefs";\n'
        'fetch(`/api/output/${ad.slice(0, -".png".length)}/download`);\n'
    )
    assert gu._cagrilan_yollar(ornek) == ["/api/output/{}/download", "/api/prefs"]


def test_generated_files_declare_that_they_are_generated():
    """Elle düzenlenmesin: her graf dosyası kendi kaynağını söylüyor olmalı."""
    for yol, icerik in gu.uret().items():
        if yol.endswith(".md"):
            assert icerik.startswith("<!-- ÜRETİLMİŞ DOSYA"), yol
        assert "\r" not in icerik, f"{yol}: CRLF (bkz. .gitattributes)"


def test_the_hook_only_reacts_to_files_that_can_change_the_graph():
    """Kanca kipi ilgisiz düzenlemede iş yapmamalı; ilgili olanı kaçırmamalı."""
    ilgili = ["app.py", "tools/graf_uret.py", "tests/test_app.py",
              "static/core.js", "static/index.html", "static/style.css"]
    ilgisiz = ["README.md", "GUNCELLEME.md", "docs/graflar/moduller.md",
               "android/app/build.gradle", "", "/etc/passwd"]
    for yol in ilgili:
        assert gu._ilgili_dosya(os.path.join(REPO, yol)), yol
    for yol in ilgisiz:
        assert not gu._ilgili_dosya(
            os.path.join(REPO, yol) if yol and not yol.startswith("/") else yol), yol
