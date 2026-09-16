"""v1.8 biçimli veri hâlâ okunuyor mu — yükseltme emniyeti.

Kural şudur: yeni alan EKLENİR, `.get()` ile okunur, migration YAZILMAZ
(storage.py'deki folder_id / palette / prompt_sent yorumları bunu belgeliyor).
Kural bugüne dek doğru uygulandı ama hiçbir test korumuyordu; bir alan yeniden
adlandırılsa ofisteki çalışanın kütüphanesi okunamaz olur ve bunu ilk fark eden
çalışan olurdu.

FİXTURE'LAR: tests/fixtures/v18/, tools/make_legacy_fixtures.py ile GERÇEK
v1.8 yazıcıları çağrılarak üretildi (tek istisna cases.json'daki "handmade"
kayıtları). Beklentiler de yazıcıların döndürdüğü kayıtlardan yazıldı, elle
ikinci bir liste tutulmuyor.

İKİ TEST AİLESİ VAR ve farklı yarıları yakalıyorlar — biri diğerinin yerine
geçmez:

  (i)  ANAHTAR-ÜSTKÜMESİ testleri (aşağıda) gerçek yeniden-adlandırma
       dedektörüdür. Kuralın formal sonucu: yazılan bir kaydın anahtar kümesi
       yalnızca BÜYÜYEBİLİR.
  (ii) Tüketici testleri okuyucunun eski şekli unutmasını yakalar. İddiaları
       echo'lanan alana değil, koddan TÜRETİLEN değere basıyorlar (klasör
       sayaçları, süzülmüş id listeleri, prompt'a giren renk adları).

Neden (i) olmadan (ii) yetmez: `GET /api/assets/{kind}` ve `GET /api/palettes`
diskteki veriyi düz geçiriyor. Biri yazıcıdaki `filename`'i `file` yaparsa eski
fixture hâlâ `filename` taşır, okuma testi YEŞİL kalır — ama çalışanın
kütüphanesi "yeni kayıtlar file / eski kayıtlar filename" diye bölünür.

LIFESPAN KOŞTURULMUYOR (çıplak TestClient, `with` YOK): bu rotalar açılıştan
hiçbir şey istemiyor ve lifespan'ı koşturmak şema testine sürüm-değişimi
yedeklemesini (backup.py) bulaştırırdı. Bkz. tests/test_backup.py.
"""
import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

import app as appmod
import assets_store
import azure_client as ac
import color_names as cn
import folders
import palette_store
import storage

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "v18")


def _cases() -> dict:
    with open(os.path.join(FIXTURES, "cases.json"), encoding="utf-8") as f:
        return json.load(f)


CASES = _cases()
EXPECT = CASES["expect"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Renk adlandırma ağı kapalı (tests/test_palette_route.py ile aynı)."""
    cn.reset_breaker()
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    yield
    cn.reset_breaker()


def _client(tmp_path, monkeypatch, dizinler, *, sent=None):
    """v1.8 fixture ağacını tmp_path'e kopyalar ve istemci döndürür.

    `with` KULLANILMIYOR — lifespan bilerek koşmuyor (bkz. modül docstring'i).
    """
    shutil.copytree(FIXTURES, tmp_path, dirs_exist_ok=True)
    dizinler(output_dir=str(tmp_path / "output"), assets_dir=str(tmp_path / "assets"))
    if sent is not None:
        def _fake_generate(prompt, size, quality, n=1, **kwargs):
            sent.append(prompt)
            return [b"\x89PNG"]
        monkeypatch.setattr(ac, "generate", _fake_generate)
    return TestClient(appmod.app)


# ── (i) anahtar-üstkümesi: gerçek yeniden-adlandırma dedektörü ────────────

def _legacy_keys(path_parts: tuple[str, ...]) -> set[str]:
    with open(os.path.join(FIXTURES, *path_parts), encoding="utf-8") as f:
        return set(json.load(f)[0])


def test_history_writer_still_writes_every_v18_field(tmp_path):
    """storage.save'in anahtar kümesi küçülemez / yeniden adlandırılamaz.

    Yalnızca eski veriyi OKUYAN testler bir yeniden adlandırmayı yakalayamaz:
    okuma yolu ne bulursa geçiriyor, eski kayıt eski adı taşımaya devam ediyor
    ve test yeşil kalırken kullanıcının kütüphanesi bölünüyor. Kırılmayı gören
    tek yer üreticinin ANAHTAR KÜMESİ.
    """
    legacy = _legacy_keys(("output", "history.json"))
    produced = storage.save(b"x", {"prompt": "p", "size": "1024x1024",
                                   "quality": "high"},
                            str(tmp_path), now="2026-07-29T00:00:00")
    assert not (legacy - set(produced)), \
        f"v1.8 alanları kayboldu: {sorted(legacy - set(produced))}"


def test_folders_writer_still_writes_every_v18_field(tmp_path):
    legacy = _legacy_keys(("output", "folders.json"))
    produced = folders.create("x", str(tmp_path), parent_id=None,
                              now="2026-07-29T00:00:00")
    assert not (legacy - set(produced)), \
        f"v1.8 alanları kayboldu: {sorted(legacy - set(produced))}"


def test_palette_writer_still_writes_every_v18_field(tmp_path):
    legacy = _legacy_keys(("output", "palettes.json"))
    produced = palette_store.create("x", "#c86a3c", "triad", "balanced",
                                    [{"hex": "#c86a3c", "name": "Kiremit"}],
                                    str(tmp_path), now="2026-07-29T00:00:00")
    assert not (legacy - set(produced)), \
        f"v1.8 alanları kayboldu: {sorted(legacy - set(produced))}"


LEGACY_ASSET_KINDS = ("logos", "banners", "mottos")


@pytest.mark.parametrize("kind", LEGACY_ASSET_KINDS)
def test_asset_writer_still_writes_every_v18_field(kind, tmp_path):
    legacy = _legacy_keys(("assets", kind, "index.json"))
    produced = assets_store.save_asset(kind, b"x", "ad", str(tmp_path),
                                       now="2026-07-29T00:00:00")
    assert not (legacy - set(produced)), \
        f"v1.8 alanları kayboldu: {sorted(legacy - set(produced))}"


def test_frozen_palette_colors_still_carry_hex_and_name(tmp_path):
    """app._saved_colors HER girdide hem `hex` hem `name` istiyor.

    Biri yeniden adlandırılırsa _saved_colors [] döner ve üretim yolu SESSİZCE
    yeniden hesaplamaya düşer (bkz. aşağıdaki prompt testi). Bu yüzden alan
    adları kayıt düzeyinde de kilitleniyor.
    """
    for color in EXPECT["palette"]["colors"]:
        assert set(color) >= {"hex", "name"}, color
    assert appmod._saved_colors({"colors": EXPECT["palette"]["colors"]}) \
        == EXPECT["palette"]["colors"]


# ── (ii) tüketici testleri: türetilmiş değerlere basıyorlar ───────────────

def test_root_history_includes_the_record_without_a_folder_id_key(tmp_path, monkeypatch, dizinler):
    """Anahtarı HİÇ OLMAYAN pre-v1.6 kaydı kökte görünmek zorunda.

    app.py'deki `not r.get("folder_id")` ifadesi `r["folder_id"] is None`
    olursa bu kayıtta KeyError → 500 olur; süzme tersine dönerse kayıt kaybolur.
    """
    c = _client(tmp_path, monkeypatch, dizinler)
    ids = [r["id"] for r in c.get("/api/history").json()["images"]]
    assert ids == EXPECT["root_history_ids"]
    legacy_id = CASES["handmade"][0]
    assert legacy_id in ids
    legacy = next(r for r in c.get("/api/history").json()["images"]
                  if r["id"] == legacy_id)
    assert "folder_id" not in legacy, "fixture bozulmuş: anahtar var olmamalı"


def test_foldered_history_still_filters_by_the_frozen_folder_id(tmp_path, monkeypatch, dizinler):
    """Okuyucudaki bir yeniden adlandırma bu listeyi [] yapar."""
    c = _client(tmp_path, monkeypatch, dizinler)
    for folder_id, image_ids in EXPECT["foldered"].items():
        got = c.get(f"/api/history?folder_id={folder_id}").json()["images"]
        assert [r["id"] for r in got] == image_ids


def test_folder_counts_are_derived_from_the_v18_fields(tmp_path, monkeypatch, dizinler):
    """count ve child_count TÜRETİLMİŞ değerler — okuma tarafındaki dedektör.

    `>= 0` değil TAM sayı iddia ediliyor: folder_id/parent_id yeniden
    adlandırılırsa sayaçlar sessizce sıfırlanır.
    """
    c = _client(tmp_path, monkeypatch, dizinler)
    items = {f["id"]: f for f in c.get("/api/folders").json()["items"]}
    child = items[EXPECT["folders"]["child"]]
    root = items[EXPECT["folders"]["root"]]
    assert child["count"] == 1, "klasördeki görsel sayılmıyor"
    assert root["child_count"] == 1, "alt klasör sayılmıyor"
    assert root["count"] == 0


def test_legacy_folder_without_parent_id_key_reads_as_root(tmp_path, monkeypatch, dizinler):
    """`parent_id` anahtarı olmayan klasör kök kabul edilmeli (app.py'deki
    `{"parent_id": None, **f}` varsayılanı)."""
    c = _client(tmp_path, monkeypatch, dizinler)
    items = {f["id"]: f for f in c.get("/api/folders").json()["items"]}
    legacy = items[EXPECT["folders"]["legacy_no_parent_id"]]
    assert legacy["parent_id"] is None


def test_derivative_chain_survives(tmp_path, monkeypatch, dizinler):
    """parent_id türev zinciri: hedef kayıt aynı yanıt kümesinde olmalı."""
    c = _client(tmp_path, monkeypatch, dizinler)
    images = {r["id"]: r for r in c.get("/api/history").json()["images"]}
    derivative = images[EXPECT["derivative"]["id"]]
    assert derivative["parent_id"] == EXPECT["derivative"]["parent_id"]
    assert derivative["parent_id"] in images


def test_history_record_palette_round_trips(tmp_path, monkeypatch, dizinler):
    """Kayıttaki palet dict'i (Türkçe adlar dahil) birebir geri gelmeli."""
    c = _client(tmp_path, monkeypatch, dizinler)
    images = {r["id"]: r for r in c.get("/api/history").json()["images"]}
    rec = images[EXPECT["palette_record_image_id"]]
    assert rec["palette"]["seed"] == EXPECT["palette"]["seed"]
    assert rec["palette"]["mode"] == EXPECT["palette"]["mode"]
    assert rec["palette"]["strength"] == EXPECT["palette"]["strength"]
    assert rec["palette"]["colors"] == EXPECT["palette"]["colors"]
    assert rec["prompt_sent"] and rec["prompt_sent"] != rec["prompt"]


def test_saved_palettes_are_listed_newest_first(tmp_path, monkeypatch, dizinler):
    c = _client(tmp_path, monkeypatch, dizinler)
    items = c.get("/api/palettes").json()["items"]
    assert len(items) == 2
    # en yeni başta: üretici "Sonbahar"ı ÖNCE yazdı → listede İKİNCİ
    frozen = next(p for p in items if p["id"] == EXPECT["palette"]["id"])
    for key in ("name", "seed", "mode", "strength", "colors"):
        assert frozen[key] == EXPECT["palette"][key], key


@pytest.mark.parametrize("kind", LEGACY_ASSET_KINDS)
def test_assets_still_listed_and_served(kind, tmp_path, monkeypatch, dizinler):
    c = _client(tmp_path, monkeypatch, dizinler)
    items = c.get(f"/api/assets/{kind}").json()["items"]
    assert [a["id"] for a in items] == EXPECT["assets"][kind]
    for a in items:
        r = c.get(f"/assets/{kind}/{a['filename']}")
        assert r.status_code == 200, a
        assert r.headers["content-type"] == "image/png"


def test_saved_v18_palette_still_reaches_the_prompt_with_frozen_names(tmp_path, monkeypatch, dizinler):
    """Task 3'ün en güçlü testi: sessiz düşüşü yakalayan tek iddia.

    app._palette_prompt kayıtlı paleti bulup DONDURULMUŞ renkleri
    _saved_colors üzerinden alıyor; o da her girdide hem `hex` hem `name`
    istiyor. Biri yeniden adlandırılırsa _saved_colors [] döner ve kod
    HATA VERMEDEN `(seed, mode)`'dan yeniden hesaplamaya düşer — kütüphanede
    görünen adlarla prompt'a giden adlar ayrışır ve kimse fark etmez.

    palette_store.py'nin sözü ("yeniden seçilen bir palet kaydedildiği günkü
    prompt'u üretmeye devam eder") ancak böyle korunur.
    """
    sent = []
    c = _client(tmp_path, monkeypatch, dizinler, sent=sent)
    r = c.post("/api/generate", json={
        "prompt": "afiş", "size": "1024x1024", "quality": "high", "n": 1,
        "palette_hex": EXPECT["palette"]["seed"],
        "palette_mode": EXPECT["palette"]["mode"],
        "palette_strength": EXPECT["palette"]["strength"],
        "palette_id": EXPECT["palette"]["id"],
    })
    assert r.status_code == 200, r.text
    assert sent, "ac.generate çağrılmadı"
    for color in EXPECT["palette"]["colors"]:
        assert color["name"] in sent[0], (
            f"dondurulmuş renk adı prompt'a girmedi: {color['name']!r} — "
            "kayıtlı palet yeniden hesaplamaya düşmüş olabilir")
    assert r.json()["images"][0]["palette"]["colors"] == EXPECT["palette"]["colors"]


# ── fixture künyesinin kendisi ────────────────────────────────────────────

def test_fixture_manifest_records_its_provenance():
    """Fixture v1.9 yazıcı değişikliğinden SONRA üretilirse v1.8 adı altında
    v1.9 şeklini dondurur — yalan söyleyen bir fixture. Künye incelemede
    kontrol edilebilsin diye zorunlu."""
    assert CASES["app_version"] == "1.8.0"
    assert len(CASES["produced_from"]) == 40, "üretildiği commit sha'sı eksik"
    assert CASES["handmade"], "elle yazılan kayıtlar etiketlenmeli"
