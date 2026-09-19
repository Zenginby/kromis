"""`services/dosya.py` — iki depo, tek sözleşme (Faz 2 / 2).

Parametrik: aynı senaryo `YerelDepo` ve `NesneDepo` üstünde koşar ve aynı
sonucu vermek zorunda — rotalar hangisinin arkada olduğunu bilmiyor. Bir de
üç bekçi: ortamdan seçim (dördü dolu / dördü boş / yarım), yol ↔ anahtar
çevirisi ve "web rotaları depoyu HER ZAMAN söyler" kaynak taraması (`depo=`
öntanımlısı yerel disk; söylemeyen bir rota kovalı dağıtımda diske yazardı).
"""
from __future__ import annotations

import ast
import io
import os
import zipfile

import pytest
from fastapi import Request

from services import dosya, nesne_depo
from tests.conftest import posix_gerekir
from tests.sahte_s3 import SahteS3

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIMLIK = nesne_depo.Kimlik("AKID", "GIZLI", "auto")


def _yerel(kok: str) -> dosya.Depo:
    return dosya.YerelDepo(kok)


def _nesne(kok: str) -> dosya.Depo:
    sahte = SahteS3("kova", KIMLIK, sayfa=2)
    return dosya.NesneDepo(nesne_depo.S3Istemci("https://hesap.r2.example", "kova", KIMLIK,
                                                istemci=sahte.istemci()), kok)


@pytest.fixture(params=[_yerel, _nesne], ids=["yerel", "nesne"])
def depo(request, tmp_path) -> dosya.Depo:
    return request.param(str(tmp_path))


# ── sözleşme ─────────────────────────────────────────────────────────

def test_the_same_scenario_behaves_identically_on_both_depos(depo, tmp_path):
    """Yaz → var → oku → akış → listele → sil; anahtarla da mutlak yolla da."""
    kok = str(tmp_path)
    a = os.path.join(kok, "kullanicilar", "u1", "output", "a.png")          # mutlak yol (rotaların verdiği)
    b = "kullanicilar/u1/output/b.mp4"                                       # anahtar (araçların verdiği)
    c = os.path.join(kok, "kullanicilar", "u1", "assets", "logos", "c.png")
    assert not depo.var(a) and not depo.var(b)
    depo.yaz(a, b"AAA", "image/png")
    depo.yaz(b, b"B" * 5000, "video/mp4")
    depo.yaz(c, b"C", "image/png")
    assert depo.var(a) and depo.var(b) and depo.var("kullanicilar/u1/output/a.png")
    assert depo.oku(a) == b"AAA" and depo.oku(b) == b"B" * 5000
    assert b"".join(depo.oku_akis(b)) == b"B" * 5000
    assert [n.anahtar for n in depo.listele("kullanicilar/u1/output/")] == \
        ["kullanicilar/u1/output/a.png", "kullanicilar/u1/output/b.mp4"]
    assert [(n.anahtar, n.boyut) for n in depo.listele("kullanicilar/")] == [
        ("kullanicilar/u1/assets/logos/c.png", 1), ("kullanicilar/u1/output/a.png", 3),
        ("kullanicilar/u1/output/b.mp4", 5000)]
    assert [n.anahtar for n in depo.listele("kullanicilar/u1/output/a")] == ["kullanicilar/u1/output/a.png"], \
        "önek S3 anlamıyla dize başlangıcı, dizin değil"
    assert list(depo.listele("kullanicilar/yok/")) == []
    assert depo.sil(a) is True and depo.sil(a) is False and not depo.var(a)
    with pytest.raises(dosya.DosyaYok):
        depo.oku(a)
    with pytest.raises(dosya.DosyaYok):
        list(depo.oku_akis(a))
    assert [n.anahtar for n in depo.listele("kullanicilar/u1/output/")] == ["kullanicilar/u1/output/b.mp4"]


def test_url_is_none_on_disk_and_a_presigned_link_in_the_bucket(tmp_path):
    yerel, nesne = _yerel(str(tmp_path)), _nesne(str(tmp_path))
    yol = os.path.join(str(tmp_path), "kullanicilar", "u", "output", "a.png")
    assert yerel.url(yol, 900) is None
    url = nesne.url(yol, 900, indirme_adi="a.png")
    assert url is not None and url.startswith("https://hesap.r2.example/kova/kullanicilar/u/output/a.png?")
    assert "X-Amz-Expires=900" in url and "response-content-disposition=" in url


@posix_gerekir(
    "`os.sep`: kök dışı anahtar MUTLAK yol (Windows'ta ters bölülü), önek ise "
    "`_anahtar(dizin) + '/'` ile kuruluyor — iki ayraç tutmuyor, `listele` boş dönüyor")
def test_a_bucket_depo_refuses_an_absolute_path_outside_its_root(tmp_path):
    nesne = _nesne(str(tmp_path / "veri"))
    with pytest.raises(dosya.DosyaHatasi):
        nesne.yaz(str(tmp_path / "baska" / "x.png"), b"x", "image/png")
    with pytest.raises(dosya.DosyaHatasi):
        nesne.var("../x.png")
    # Yerel depoda köke dışı mutlak yol geçerli: testler `dizinler(output_dir=tmp_path)` diyor.
    yerel = _yerel(str(tmp_path / "veri"))
    yerel.yaz(str(tmp_path / "baska" / "x.png"), b"x", "image/png")
    assert (tmp_path / "baska" / "x.png").read_bytes() == b"x"
    assert [n.anahtar for n in yerel.listele(str(tmp_path / "baska") + os.sep)] == [str(tmp_path / "baska" / "x.png")]


def test_the_bucket_key_is_the_path_relative_to_the_data_root_with_forward_slashes(tmp_path):
    nesne = _nesne(str(tmp_path))
    assert nesne._anahtar(os.path.join(str(tmp_path), "kullanicilar", "u", "output", "a.png")) == \
        "kullanicilar/u/output/a.png"
    assert nesne._anahtar("kullanicilar/u/output/a.png") == "kullanicilar/u/output/a.png"
    assert nesne._anahtar("") == "" and nesne._anahtar(str(tmp_path)) == ""


# ── ortamdan seçim ───────────────────────────────────────────────────

def _ortam(monkeypatch, **degerler: str) -> None:
    for ad in dosya.ZORUNLU_ENV + (dosya.BOLGE_ENV,):
        monkeypatch.delenv(ad, raising=False)
    for ad, deger in degerler.items():
        monkeypatch.setenv(ad, deger)


def test_no_variables_means_the_local_disk_rooted_at_the_data_dir(monkeypatch, tmp_path):
    _ortam(monkeypatch)
    depo = dosya.depo_kur(str(tmp_path))
    assert isinstance(depo, dosya.YerelDepo) and depo.kok == str(tmp_path)
    assert not dosya.nesne_depo_mu()


def test_all_four_variables_mean_the_bucket_with_auto_as_the_default_region(monkeypatch, tmp_path):
    _ortam(monkeypatch, KROMIS_NESNE_DEPO_URL=" https://hesap.r2.cloudflarestorage.com ",
           KROMIS_NESNE_DEPO_KOVA="kromis", KROMIS_NESNE_DEPO_ANAHTAR_ID="AKID",
           KROMIS_NESNE_DEPO_GIZLI="GIZLI")
    depo = dosya.depo_kur(str(tmp_path))
    assert isinstance(depo, dosya.NesneDepo) and dosya.nesne_depo_mu()
    assert depo.istemci.uc_nokta == "https://hesap.r2.cloudflarestorage.com"
    assert depo.istemci.kova == "kromis" and depo.istemci.kimlik.bolge == "auto"
    assert "GIZLI" not in repr(depo)
    monkeypatch.setenv(dosya.BOLGE_ENV, "eu-central-1")
    assert dosya.depo_kur(str(tmp_path)).istemci.kimlik.bolge == "eu-central-1"


@pytest.mark.parametrize("eksik", sorted(dosya.ZORUNLU_ENV))
def test_a_half_configuration_refuses_to_start_and_names_the_missing_variable(monkeypatch, tmp_path, eksik):
    degerler = {ad: "x" for ad in dosya.ZORUNLU_ENV if ad != eksik}
    degerler[dosya.URL_ENV] = "https://hesap.r2.example" if eksik != dosya.URL_ENV else degerler.get(dosya.URL_ENV, "")
    _ortam(monkeypatch, **{k: v for k, v in degerler.items() if v})
    with pytest.raises(dosya.YapilandirmaHatasi) as hata:
        dosya.depo_kur(str(tmp_path))
    assert eksik in str(hata.value)


def test_a_bad_endpoint_is_a_configuration_error_too(monkeypatch, tmp_path):
    _ortam(monkeypatch, KROMIS_NESNE_DEPO_URL="hesap.r2.example", KROMIS_NESNE_DEPO_KOVA="k",
           KROMIS_NESNE_DEPO_ANAHTAR_ID="a", KROMIS_NESNE_DEPO_GIZLI="g")
    with pytest.raises(dosya.YapilandirmaHatasi):
        dosya.depo_kur(str(tmp_path))


def test_the_test_process_never_sees_object_storage_variables():
    """conftest `pytest_configure` süpürüyor: geliştiricinin kabuğundaki gerçek R2 değerleri
    178 rota testini gerçek kovaya yazdırmasın (services/dosya.py ithal anında okuyor)."""
    assert not [ad for ad in os.environ if ad.startswith("KROMIS_NESNE_DEPO_")]
    import app as appmod
    assert isinstance(appmod.app.state.dosya, dosya.YerelDepo)


def test_the_dependency_reads_the_live_state_object():
    import app as appmod
    istek = Request({"type": "http", "app": appmod.app, "headers": []})
    assert dosya.depo(istek) is appmod.app.state.dosya


# ── akışlı ZIP tamponu ───────────────────────────────────────────────

def test_the_write_buffer_lets_zipfile_stream_a_valid_archive():
    tampon = dosya.YazmaTamponu()
    parcalar: list[bytes] = []
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open(zipfile.ZipInfo("k/a.bin"), "w", force_zip64=True) as h:
            h.write(b"A" * 3000)
            parcalar.append(tampon.bosalt())
            h.write(b"B" * 3000)
            parcalar.append(tampon.bosalt())
        parcalar.append(tampon.bosalt())
    parcalar.append(tampon.bosalt())
    assert sum(map(len, parcalar)) > 0 and any(parcalar[:2]), "veri yazılırken parça çıkıyor, sonda değil"
    with zipfile.ZipFile(io.BytesIO(b"".join(parcalar))) as okunan:
        assert okunan.namelist() == ["k/a.bin"] and okunan.read("k/a.bin") == b"A" * 3000 + b"B" * 3000
        assert okunan.testzip() is None


# ── bekçi: rotalar depoyu söyler ─────────────────────────────────────

# Dizin alan depo işlevleri — `depo=` almadan çağrılırlarsa yerel diske düşerler.
DEPO_ISTEYEN = {
    ("depo_medya", "kaydet"), ("depo_medya", "dosya_yolu"), ("depo_medya", "dosya_yolu_adiyla"),
    ("depo_medya", "sil"), ("depo_medya", "sil_coklu"),
    ("depo_varlik", "kaydet"), ("depo_varlik", "dosya_yolu"), ("depo_varlik", "dosya_yolu_adiyla"),
    ("depo_varlik", "sil"),
    ("depo_klasor", "zip_disa_aktar"),
    ("gorsel", "output_png_path"), ("gorsel", "read_png_file"),
}


def _cagrilar(yol: str):
    with open(yol, encoding="utf-8") as f:
        agac = ast.parse(f.read(), filename=yol)
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Attribute) \
                and isinstance(dugum.func.value, ast.Name):
            yield dugum, (dugum.func.value.id, dugum.func.attr)


@pytest.mark.parametrize("dosya_adi", ["galeri.py", "bindirme.py", "uretim.py"])
def test_every_file_touching_call_in_the_routers_names_the_depo(dosya_adi):
    """`depo=` öntanımlısı yerel disk (testlerin doğrudan çağrıları için); bir rota onu
    söylemeyi unutursa kovalı dağıtımda dosya diske, satır DB'ye düşer ve `/output` 404
    verir. Kaynak taraması: `run_in_threadpool(depo_medya.kaydet, …)` biçimi de dâhil."""
    yol = os.path.join(REPO, "routers", dosya_adi)
    bulunan = 0
    for cagri, hedef in _cagrilar(yol):
        if hedef == ("run_in_threadpool", "") or (hedef[0] == "" and hedef[1] == ""):
            continue
        if hedef in DEPO_ISTEYEN:
            bulunan += 1
            assert any(kw.arg == "depo" for kw in cagri.keywords), \
                f"{dosya_adi}:{cagri.lineno} {hedef[0]}.{hedef[1]}(…) depoyu söylemiyor"
    # `run_in_threadpool(depo_medya.kaydet, …, depo=depo)`: işlev argüman, çağrı sarmalayıcıda.
    with open(yol, encoding="utf-8") as f:
        agac = ast.parse(f.read())
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name) \
                and dugum.func.id == "run_in_threadpool" and dugum.args:
            ilk = dugum.args[0]
            if isinstance(ilk, ast.Attribute) and isinstance(ilk.value, ast.Name) \
                    and (ilk.value.id, ilk.attr) in DEPO_ISTEYEN:
                bulunan += 1
                assert any(kw.arg == "depo" for kw in dugum.keywords), \
                    f"{dosya_adi}:{dugum.lineno} run_in_threadpool({ilk.value.id}.{ilk.attr}) depoyu söylemiyor"
    assert bulunan >= 2, f"{dosya_adi}: tarama şüpheli biçimde az çağrı buldu ({bulunan})"


def test_the_guard_list_names_real_functions_that_really_take_a_depo():
    import importlib
    for modul, ad in sorted(DEPO_ISTEYEN):
        islev = getattr(importlib.import_module(f"services.{modul}"), ad)
        import inspect
        assert "depo" in inspect.signature(islev).parameters, f"services/{modul}.py::{ad} `depo` almıyor"
