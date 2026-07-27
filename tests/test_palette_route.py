"""Palet rotaları ve prompt enjeksiyonu — uçtan uca entegrasyon.

Koşum takımı tests/test_folders.py:31-37 ile aynı. `ac.generate`/`ac.edit`
KAYDEDİCİ olarak taklit edilir: bu dosyanın asıl işi, palet ekinin gerçekten
Azure'a giden metne ulaştığını kanıtlamak.

Hiçbir test ağa çıkmaz: color_names._fetch_name her testte değiştirilir.
"""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import azure_client as ac
import color_names as cn
import palette
import palette_store
import storage

SEED = "#c86a3c"
# Gömülü tablo ÖNCE denendiği için ağ katmanı yalnızca tablonun yakın karşılığı
# olmayan renkler için çalışır. Bu tohumun her paletinde en az bir boşluk var.
GAP_SEED = "#00ff00"


def _png(color=(30, 80, 200, 255), size=(64, 64)) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", size, color).save(b, "PNG")
    return b.getvalue()


def _fake_composite(cmd, capture_output, text):
    """tests/test_folders.py:20-28 ile aynı sözleşme: cmd[2]=girdi, cmd[3]=çıktı."""
    with open(cmd[2], "rb") as s, open(cmd[3], "wb") as d:
        d.write(s.read())

    class R:
        returncode = 0
        stderr = ""
    return R()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Adlandırma ağı her testte kapalı; gömülü tablo/betimleyici kullanılır."""
    cn.reset_breaker()
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    yield
    cn.reset_breaker()


def _client(tmp_path, monkeypatch, *, real_png=False):
    """Kaydedici: gönderilen prompt'ları `sent` listesinde toplar."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    sent: list[str] = []

    def rec_generate(prompt, *a, **k):
        sent.append(prompt)
        return [_png(size=(256, 256)) if real_png else b"\x89PNG"]

    def rec_edit(prompt, *a, **k):
        sent.append(prompt)
        return [_png(size=(256, 256)) if real_png else b"\x89PNG-edited"]

    monkeypatch.setattr(ac, "generate", rec_generate)
    monkeypatch.setattr(ac, "edit", rec_edit)
    return TestClient(appmod.app), sent


def _gen(client, **extra):
    body = {"prompt": "kurban afişi", "size": "1024x1024", "quality": "medium", "n": 1}
    body.update(extra)
    return client.post("/api/generate", json=body)


# ── /api/palette/suggest ────────────────────────────────────────────────────

def test_suggest_returns_all_six_harmonies_with_named_colors(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/palette/suggest", json={"hex": SEED})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seed"] == SEED
    assert [i["mode"] for i in body["items"]] == list(palette.MODES)
    for item in body["items"]:
        assert len(item["colors"]) == palette.COLORS_PER_PALETTE
        for color in item["colors"]:
            assert color["hex"].startswith("#")
            assert color["name"].strip()


def test_suggest_normalizes_hex_without_hash(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.post("/api/palette/suggest", json={"hex": "C86A3C"}).json()["seed"] == SEED


def test_suggest_writes_nothing_to_disk(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    client.post("/api/palette/suggest", json={"hex": SEED})
    assert client.get("/api/palettes").json()["items"] == []


@pytest.mark.parametrize("bad", ["", "#GGGGGG", "zzz", "#12345", "#1234567"])
def test_suggest_rejects_bad_hex(tmp_path, monkeypatch, bad):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.post("/api/palette/suggest", json={"hex": bad}).status_code == 422


def test_suggest_rejects_unknown_field(tmp_path, monkeypatch):
    """Bilinmeyen alan sessizce yok sayılmamalı — bkz. tests/test_banner.py:141."""
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/palette/suggest", json={"hex": SEED, "mode": "triad"})
    assert r.status_code == 422


def test_suggest_makes_zero_network_calls(tmp_path, monkeypatch):
    """Gerileme koruması: öneri yolu bir kez çevrimiçiydi ve 11 sn sürüyordu.

    Altı harmoniyi ayrı ayrı çözümlemek her birine yeni bir API bütçesi
    veriyordu. Keşif tamamen yerel olmalı — anında, deterministik, ve kartta
    görülen ad prompt'a giden adla birebir aynı.
    """
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: pytest.fail("öneri yolunda ağ çağrısı"))
    r = client.post("/api/palette/suggest", json={"hex": SEED})
    assert r.status_code == 200
    assert all(c["name"].strip()
               for item in r.json()["items"] for c in item["colors"])


def test_saving_a_palette_uses_the_api_for_table_gaps(tmp_path, monkeypatch):
    """thecolorapi'nin devreye girdiği tek yer: kaydetme + tablo boşluğu."""
    client, _ = _client(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: (calls.append(h), "Harlequin")[1])
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": GAP_SEED,
                                              "mode": "triad"}).json()["palette"]
    assert calls, "kaydetme yolunda API çağrısı yapılmadı"
    # Tekilleştirme: benzersiz renk sayısından fazla arama yapılmamalı.
    assert len(calls) <= palette.COLORS_PER_PALETTE
    assert any("harlequin" in c["name"] for c in saved["colors"])


def test_saving_a_table_matched_palette_skips_the_api(tmp_path, monkeypatch):
    """Kanonik yerel ad varken API'ye sormak gereksiz — ve daha kötü sinyal."""
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: pytest.fail("tablo eşi varken ağ çağrısı"))
    r = client.post("/api/palettes", json={"name": "Marka", "seed": SEED,
                                           "mode": "complement"})
    assert r.status_code == 200, r.text


def test_names_map_shares_one_budget_and_dedupes(monkeypatch):
    """Tohum rengi altı palette de geçer; her tekrar için arama yapılmamalı."""
    cn.reset_breaker()
    calls = []
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: (calls.append(h), "Harlequin")[1])
    resolved = cn.names_map([GAP_SEED, GAP_SEED, GAP_SEED, "#0000ff", GAP_SEED])
    assert len(calls) == 2, calls
    assert set(resolved) == {GAP_SEED, "#0000ff"}
    cn.reset_breaker()


def test_suggest_still_works_when_the_naming_api_is_down(tmp_path, monkeypatch):
    """thecolorapi çökse bile öneri 200 dönmeli, adlar yerelden gelmeli."""
    client, _ = _client(tmp_path, monkeypatch)

    def boom(_hex):
        raise RuntimeError("ağ yok")

    monkeypatch.setattr(cn, "_fetch_name", boom)
    r = client.post("/api/palette/suggest", json={"hex": SEED})
    assert r.status_code == 200
    assert all(c["name"].strip()
               for item in r.json()["items"] for c in item["colors"])


# ── Palet kütüphanesi CRUD ──────────────────────────────────────────────────

def test_palette_crud_round_trip(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/palettes", json={"name": "Kurban sıcak", "seed": SEED,
                                           "mode": "analogic", "strength": "strict"})
    assert r.status_code == 200, r.text
    saved = r.json()["palette"]
    assert saved["name"] == "Kurban sıcak"
    assert saved["mode"] == "analogic"
    assert saved["strength"] == "strict"
    assert len(saved["colors"]) == palette.COLORS_PER_PALETTE

    assert [p["id"] for p in client.get("/api/palettes").json()["items"]] == [saved["id"]]
    assert client.delete(f"/api/palettes/{saved['id']}").json() == {"deleted": saved["id"]}
    assert client.get("/api/palettes").json()["items"] == []


def test_saved_palettes_are_newest_first(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    first = client.post("/api/palettes", json={"name": "ilk", "seed": SEED,
                                              "mode": "triad"}).json()["palette"]
    second = client.post("/api/palettes", json={"name": "ikinci", "seed": "#2e5fa3",
                                               "mode": "quad"}).json()["palette"]
    ids = [p["id"] for p in client.get("/api/palettes").json()["items"]]
    assert ids == [second["id"], first["id"]]


def test_delete_unknown_palette_is_404(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.delete("/api/palettes/deadbeefcafe").status_code == 404


def test_delete_traversal_id_is_404_not_a_write(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.delete("/api/palettes/..%2F..%2Fetc").status_code == 404


def test_save_rejects_blank_name(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/api/palettes", json={"name": "   ", "seed": SEED, "mode": "triad"})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", [
    {"name": "x", "seed": SEED, "mode": "kaleidoscope"},
    {"name": "x", "seed": "#GGGGGG", "mode": "triad"},
    {"name": "x", "seed": SEED, "mode": "triad", "strength": "loud"},
    {"name": "x", "seed": SEED, "mode": "triad", "colors": []},
])
def test_save_rejects_bad_payloads(tmp_path, monkeypatch, payload):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.post("/api/palettes", json=payload).status_code == 422


def test_corrupt_palettes_file_is_tolerated(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "palettes.json").write_text("{bozuk", encoding="utf-8")
    assert client.get("/api/palettes").json()["items"] == []


# ── Asıl kanıt: ek Azure'a giden metne ulaşıyor mu ──────────────────────────

def test_generate_appends_the_palette_to_the_prompt_sent_to_azure(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    r = _gen(client, palette_hex=SEED, palette_mode="triad", palette_strength="balanced")
    assert r.status_code == 200, r.text
    assert len(sent) == 1
    assert sent[0].startswith("kurban afişi")
    assert "Color direction" in sent[0]
    # Paletin gerçek hex'leri metinde geçmeli
    for hex_color in palette.harmony(SEED, "triad"):
        assert hex_color in sent[0]


def test_generate_without_a_palette_sends_the_prompt_verbatim(tmp_path, monkeypatch):
    """Gerileme testi: palet kullanılmadığında katman tamamen atıl olmalı."""
    client, sent = _client(tmp_path, monkeypatch)
    r = _gen(client)
    assert r.status_code == 200, r.text
    assert sent == ["kurban afişi"]
    record = r.json()["images"][0]
    assert record["palette"] is None
    assert record["prompt_sent"] is None


def test_generate_stores_the_user_prompt_not_the_augmented_one(tmp_path, monkeypatch):
    """`prompt` alanı galeri başlıklarını ve türev kopyalamayı besliyor."""
    client, sent = _client(tmp_path, monkeypatch)
    record = _gen(client, palette_hex=SEED, palette_mode="analogic").json()["images"][0]
    assert record["prompt"] == "kurban afişi"
    assert record["prompt_sent"] == sent[0]
    assert record["prompt_sent"] != record["prompt"]


def test_generate_snapshots_the_palette_in_history(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    record = _gen(client, palette_hex=SEED, palette_mode="quad",
                  palette_strength="strict").json()["images"][0]
    pal = record["palette"]
    assert pal["seed"] == SEED
    assert pal["mode"] == "quad"
    assert pal["strength"] == "strict"
    assert [c["hex"] for c in pal["colors"]] == list(palette.harmony(SEED, "quad"))


@pytest.mark.parametrize("strength", palette.STRENGTHS)
def test_every_strength_produces_a_distinct_prompt(tmp_path, monkeypatch, strength):
    client, sent = _client(tmp_path, monkeypatch)
    _gen(client, palette_hex=SEED, palette_strength=strength)
    # Beklenen metni gerçek çözümleme yolundan kur — mantığı testte
    # kopyalamak dedupe gibi bir adımı atlayıp yanlış yeşil verirdi.
    expected = palette.prompt_suffix(
        appmod._resolve_palette(SEED, "analogic", offline=True),
        strength, task="generate")
    assert sent[0] == "kurban afişi" + expected


def test_generation_never_calls_the_naming_network(tmp_path, monkeypatch):
    """Üretim yolunun yapısal garantisi: thecolorapi üretimi hiç etkilemez."""
    client, sent = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: pytest.fail("üretim yolunda ağ çağrısı"))
    assert _gen(client, palette_hex=SEED).status_code == 200
    assert "Color direction" in sent[0]


def test_palette_suffix_is_dropped_when_the_prompt_is_already_at_the_limit(
        tmp_path, monkeypatch):
    """Palet üretimi ASLA bloke etmemeli; ek düşer, kullanıcı metni kırpılmaz."""
    client, sent = _client(tmp_path, monkeypatch)
    long_prompt = "a" * appmod.MAX_PROMPT_CHARS
    r = client.post("/api/generate", json={
        "prompt": long_prompt, "size": "1024x1024", "quality": "medium", "n": 1,
        "palette_hex": SEED})
    assert r.status_code == 200, r.text
    assert sent[0] == long_prompt
    assert len(sent[0]) <= appmod.MAX_PROMPT_CHARS
    # Palet yine de kayda geçer: "istedim ama sığmadı" görünür kalsın.
    record = r.json()["images"][0]
    assert record["palette"]["seed"] == SEED
    # ...ama "istedim" ile "oldu" AYIRT EDİLEBİLİR olmalı: bayrak olmadan
    # arayüz düşen eki uygulanmış paletten ayıramaz ve sessizce renksiz
    # görsel gösterir (bkz. 15c6646 — bayat sunucu sapmasını yüzeye çıkarma).
    assert record["palette"]["applied"] is False
    # prompt_sent sözleşmesi: "Azure'a giden metin, YALNIZCA prompt'tan
    # farklıysa" (bkz. storage.save). Ek düştüyse metin birebir aynı.
    assert record["prompt_sent"] is None


def test_an_applied_palette_is_marked_as_applied(tmp_path, monkeypatch):
    """`applied` bayrağının karşı ucu: normal yolda True olmalı."""
    client, _ = _client(tmp_path, monkeypatch)
    record = _gen(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    assert record["palette"]["applied"] is True


@pytest.mark.parametrize("field,bad", [
    ("palette_hex", "#GGGGGG"), ("palette_hex", "zzz"),
    ("palette_mode", "kaleidoscope"), ("palette_strength", "loud"),
])
def test_generate_rejects_bad_palette_fields(tmp_path, monkeypatch, field, bad):
    client, _ = _client(tmp_path, monkeypatch)
    assert _gen(client, **{field: bad}).status_code == 422


def test_generate_rejects_unknown_field(tmp_path, monkeypatch):
    """Yeni eklenen extra="forbid": bayat sunucu sessiz kalmasın."""
    client, _ = _client(tmp_path, monkeypatch)
    assert _gen(client, palette_hexx=SEED).status_code == 422


def test_empty_palette_hex_means_no_palette(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    r = _gen(client, palette_hex="")
    assert r.status_code == 200, r.text
    assert sent == ["kurban afişi"]
    assert r.json()["images"][0]["palette"] is None


# ── /api/edit ───────────────────────────────────────────────────────────────

def _edit(client, **extra):
    data = {"prompt": "arka planı sadeleştir", "size": "1024x1024",
            "quality": "medium", "n": "1"}
    data.update(extra)
    return client.post("/api/edit", data=data,
                       files={"file": ("r.png", _png(), "image/png")})


def test_edit_appends_the_palette_and_uses_edit_framing(tmp_path, monkeypatch):
    """En kritik ayrım: üretim ifadesi referans görselin kompozisyonunu yok eder."""
    client, sent = _client(tmp_path, monkeypatch)
    r = _edit(client, palette_hex=SEED, palette_mode="complement")
    assert r.status_code == 200, r.text
    assert sent[0].startswith("arka planı sadeleştir")
    assert "composition" in sent[0]
    assert "do not repaint or move anything" in sent[0].lower()


def test_edit_without_a_palette_sends_the_prompt_verbatim(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    r = _edit(client)
    assert r.status_code == 200, r.text
    assert sent == ["arka planı sadeleştir"]
    assert r.json()["images"][0]["palette"] is None


def test_edit_echoes_the_palette_so_a_stale_server_is_detectable(tmp_path, monkeypatch):
    """multipart'ta extra="forbid" yok; arayüz bayat sunucuyu bu yankıyla anlar."""
    client, _ = _client(tmp_path, monkeypatch)
    record = _edit(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    assert record["palette"]["seed"] == SEED
    assert record["palette"]["mode"] == "triad"


@pytest.mark.parametrize("field,bad", [
    ("palette_hex", "#GGGGGG"), ("palette_mode", "kaleidoscope"),
    ("palette_strength", "loud"),
])
def test_edit_rejects_bad_palette_fields(tmp_path, monkeypatch, field, bad):
    client, _ = _client(tmp_path, monkeypatch)
    assert _edit(client, **{field: bad}).status_code == 422


# ── Kayıtlı paletin dondurulmuş adları ──────────────────────────────────────

def test_saved_palette_frozen_names_are_used_in_the_prompt(tmp_path, monkeypatch):
    """Kütüphanede görünen ad ile prompt'a giden ad ayrışmamalı.

    Palet çevrimiçi adlarla kaydedilir; sonra önbellek temizlenir (sunucu
    yeniden başlamış gibi). Yeniden hesaplasaydık yerel adlara düşerdi.
    """
    client, sent = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(cn, "_fetch_name", lambda h: "Harlequin")
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": GAP_SEED,
                                              "mode": "triad"}).json()["palette"]
    assert any("harlequin" in c["name"] for c in saved["colors"])

    cn.reset_breaker()  # önbellek boş: yeniden hesaplama betimleyiciye düşerdi
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    _gen(client, palette_hex=GAP_SEED, palette_mode="triad", palette_id=saved["id"])
    for color in saved["colors"]:
        assert color["name"] in sent[0]


def test_saved_palette_id_wins_over_a_mismatched_mode(tmp_path, monkeypatch):
    """Kayıt kaynak: id verilmişse kaydın modu/renkleri geçerli."""
    client, sent = _client(tmp_path, monkeypatch)
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": SEED,
                                              "mode": "quad"}).json()["palette"]
    record = _gen(client, palette_hex="#2e5fa3", palette_mode="triad",
                  palette_id=saved["id"]).json()["images"][0]
    assert record["palette"]["mode"] == "quad"
    assert record["palette"]["seed"] == SEED
    assert record["palette"]["id"] == saved["id"]
    assert record["palette"]["name"] == "Marka"


def test_a_deleted_palette_does_not_block_generation(tmp_path, monkeypatch):
    """Silinmiş palet hata vermez, (seed, mode)'dan yeniden hesaplanır."""
    client, sent = _client(tmp_path, monkeypatch)
    r = _gen(client, palette_hex=SEED, palette_mode="triad",
             palette_id="deadbeefcafe")
    assert r.status_code == 200, r.text
    assert "Color direction" in sent[0]
    assert r.json()["images"][0]["palette"]["mode"] == "triad"


def test_edit_also_honors_a_saved_palette_id(tmp_path, monkeypatch):
    client, sent = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(cn, "_fetch_name", lambda h: "Harlequin")
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": GAP_SEED,
                                              "mode": "complement"}).json()["palette"]
    cn.reset_breaker()
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    r = _edit(client, palette_hex=GAP_SEED, palette_id=saved["id"])
    assert r.status_code == 200, r.text
    assert "composition" in sent[0]
    for color in saved["colors"]:
        assert color["name"] in sent[0]


# ── Türevler ve eski kayıtlar ───────────────────────────────────────────────

def test_logo_derivative_inherits_the_palette(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch, real_png=True)
    monkeypatch.setattr(appmod.subprocess, "run", _fake_composite)
    monkeypatch.setattr(appmod, "COMPOSITE_SCRIPT", str(tmp_path / "fake.py"))
    (tmp_path / "fake.py").write_text("#", encoding="utf-8")

    src = _gen(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    r = client.post("/api/logo", json={"id": src["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["image"]["palette"]["seed"] == SEED


def test_legacy_history_records_without_palette_are_tolerated(tmp_path, monkeypatch):
    """Eski kayıtlarda alan hiç yok — geçiş (migration) gerekmemeli."""
    client, _ = _client(tmp_path, monkeypatch)
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "history.json").write_text(json.dumps([{
        "id": "abc123abc123", "filename": "abc123abc123.png", "prompt": "eski",
        "size": "1024x1024", "quality": "medium", "created_at": "2025-01-01T00:00:00",
        "parent_id": None,
    }]), encoding="utf-8")

    r = client.get("/api/history")
    assert r.status_code == 200, r.text
    record = r.json()["images"][0]
    assert record["id"] == "abc123abc123"
    assert record.get("palette") is None
