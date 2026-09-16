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
import assets_store as astore
import azure_client as ac
import color_names as cn
import palette

SEED = "#c86a3c"
# Gömülü tablo ÖNCE denendiği için ağ katmanı yalnızca tablonun yakın karşılığı
# olmayan renkler için çalışır. Bu tohumun her paletinde en az bir boşluk var.
GAP_SEED = "#00ff00"


def _png(color=(30, 80, 200, 255), size=(64, 64)) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", size, color).save(b, "PNG")
    return b.getvalue()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Adlandırma ağı her testte kapalı; gömülü tablo/betimleyici kullanılır."""
    cn.reset_breaker()
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    yield
    cn.reset_breaker()


def _client(tmp_path, monkeypatch, dizinler, *, real_png=False):
    """Kaydedici: gönderilen prompt'ları `sent` listesinde toplar."""
    dizinler(output_dir=str(tmp_path / "output"), assets_dir=str(tmp_path / "assets"))
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

def test_suggest_returns_all_six_harmonies_with_named_colors(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
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


def test_suggest_normalizes_hex_without_hash(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert client.post("/api/palette/suggest", json={"hex": "C86A3C"}).json()["seed"] == SEED


def test_suggest_writes_nothing_to_disk(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    client.post("/api/palette/suggest", json={"hex": SEED})
    assert client.get("/api/palettes").json()["items"] == []


@pytest.mark.parametrize("bad", ["", "#GGGGGG", "zzz", "#12345", "#1234567"])
def test_suggest_rejects_bad_hex(tmp_path, monkeypatch, bad, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert client.post("/api/palette/suggest", json={"hex": bad}).status_code == 422


def test_suggest_rejects_unknown_field(tmp_path, monkeypatch, dizinler):
    """Bilinmeyen alan sessizce yok sayılmamalı — bkz. tests/test_banner.py:141."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = client.post("/api/palette/suggest", json={"hex": SEED, "mode": "triad"})
    assert r.status_code == 422


def test_suggest_makes_zero_network_calls(tmp_path, monkeypatch, dizinler):
    """Gerileme koruması: öneri yolu bir kez çevrimiçiydi ve 11 sn sürüyordu.

    Altı harmoniyi ayrı ayrı çözümlemek her birine yeni bir API bütçesi
    veriyordu. Keşif tamamen yerel olmalı — anında, deterministik, ve kartta
    görülen ad prompt'a giden adla birebir aynı.
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: pytest.fail("öneri yolunda ağ çağrısı"))
    r = client.post("/api/palette/suggest", json={"hex": SEED})
    assert r.status_code == 200
    assert all(c["name"].strip()
               for item in r.json()["items"] for c in item["colors"])


def test_saving_a_palette_uses_the_api_for_table_gaps(tmp_path, monkeypatch, dizinler):
    """thecolorapi'nin devreye girdiği tek yer: kaydetme + tablo boşluğu."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    calls = []
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: (calls.append(h), "Harlequin")[1])
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": GAP_SEED,
                                              "mode": "triad"}).json()["palette"]
    assert calls, "kaydetme yolunda API çağrısı yapılmadı"
    # Tekilleştirme: benzersiz renk sayısından fazla arama yapılmamalı.
    assert len(calls) <= palette.COLORS_PER_PALETTE
    assert any("harlequin" in c["name"] for c in saved["colors"])


def test_saving_a_table_matched_palette_skips_the_api(tmp_path, monkeypatch, dizinler):
    """Kanonik yerel ad varken API'ye sormak gereksiz — ve daha kötü sinyal."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
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


def test_suggest_still_works_when_the_naming_api_is_down(tmp_path, monkeypatch, dizinler):
    """thecolorapi çökse bile öneri 200 dönmeli, adlar yerelden gelmeli."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)

    def boom(_hex):
        raise RuntimeError("ağ yok")

    monkeypatch.setattr(cn, "_fetch_name", boom)
    r = client.post("/api/palette/suggest", json={"hex": SEED})
    assert r.status_code == 200
    assert all(c["name"].strip()
               for item in r.json()["items"] for c in item["colors"])


# ── Palet kütüphanesi CRUD ──────────────────────────────────────────────────

def test_palette_crud_round_trip(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
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


def test_saved_palettes_are_newest_first(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    first = client.post("/api/palettes", json={"name": "ilk", "seed": SEED,
                                              "mode": "triad"}).json()["palette"]
    second = client.post("/api/palettes", json={"name": "ikinci", "seed": "#2e5fa3",
                                               "mode": "quad"}).json()["palette"]
    ids = [p["id"] for p in client.get("/api/palettes").json()["items"]]
    assert ids == [second["id"], first["id"]]


def test_delete_unknown_palette_is_404(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert client.delete("/api/palettes/deadbeefcafe").status_code == 404


def test_delete_traversal_id_is_404_not_a_write(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert client.delete("/api/palettes/..%2F..%2Fetc").status_code == 404


def test_save_rejects_blank_name(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = client.post("/api/palettes", json={"name": "   ", "seed": SEED, "mode": "triad"})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", [
    {"name": "x", "seed": SEED, "mode": "kaleidoscope"},
    {"name": "x", "seed": "#GGGGGG", "mode": "triad"},
    {"name": "x", "seed": SEED, "mode": "triad", "strength": "loud"},
    {"name": "x", "seed": SEED, "mode": "triad", "colors": []},
])
def test_save_rejects_bad_payloads(tmp_path, monkeypatch, payload, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert client.post("/api/palettes", json=payload).status_code == 422


def test_corrupt_palettes_file_is_tolerated(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "palettes.json").write_text("{bozuk", encoding="utf-8")
    assert client.get("/api/palettes").json()["items"] == []


# ── Asıl kanıt: ek Azure'a giden metne ulaşıyor mu ──────────────────────────

def test_generate_appends_the_palette_to_the_prompt_sent_to_azure(tmp_path, monkeypatch, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="triad", palette_strength="balanced")
    assert r.status_code == 200, r.text
    assert len(sent) == 1
    assert sent[0].startswith("kurban afişi")
    assert "Color direction" in sent[0]
    # Paletin gerçek hex'leri metinde geçmeli
    for hex_color in palette.harmony(SEED, "triad"):
        assert hex_color in sent[0]


def test_generate_without_a_palette_sends_the_prompt_verbatim(tmp_path, monkeypatch, dizinler):
    """Gerileme testi: palet kullanılmadığında katman tamamen atıl olmalı."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client)
    assert r.status_code == 200, r.text
    assert sent == ["kurban afişi"]
    record = r.json()["images"][0]
    assert record["palette"] is None
    assert record["prompt_sent"] is None


def test_generate_stores_the_user_prompt_not_the_augmented_one(tmp_path, monkeypatch, dizinler):
    """`prompt` alanı galeri başlıklarını ve türev kopyalamayı besliyor."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    record = _gen(client, palette_hex=SEED, palette_mode="analogic").json()["images"][0]
    assert record["prompt"] == "kurban afişi"
    assert record["prompt_sent"] == sent[0]
    assert record["prompt_sent"] != record["prompt"]


def test_generate_snapshots_the_palette_in_history(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    record = _gen(client, palette_hex=SEED, palette_mode="quad",
                  palette_strength="strict").json()["images"][0]
    pal = record["palette"]
    assert pal["seed"] == SEED
    assert pal["mode"] == "quad"
    assert pal["strength"] == "strict"
    assert [c["hex"] for c in pal["colors"]] == list(palette.harmony(SEED, "quad"))


@pytest.mark.parametrize("strength", palette.STRENGTHS)
def test_every_strength_produces_a_distinct_prompt(tmp_path, monkeypatch, strength, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    _gen(client, palette_hex=SEED, palette_strength=strength)
    # Beklenen metni gerçek çözümleme yolundan kur — mantığı testte
    # kopyalamak dedupe gibi bir adımı atlayıp yanlış yeşil verirdi.
    expected = palette.prompt_suffix(
        appmod._resolve_palette(SEED, "analogic", offline=True),
        strength, task="generate")
    assert sent[0] == "kurban afişi" + expected


def test_generation_never_calls_the_naming_network(tmp_path, monkeypatch, dizinler):
    """Üretim yolunun yapısal garantisi: thecolorapi üretimi hiç etkilemez."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    monkeypatch.setattr(cn, "_fetch_name",
                        lambda h: pytest.fail("üretim yolunda ağ çağrısı"))
    assert _gen(client, palette_hex=SEED).status_code == 200
    assert "Color direction" in sent[0]


def test_palette_suffix_is_dropped_when_the_prompt_is_already_at_the_limit(tmp_path, monkeypatch, dizinler):
    """Palet üretimi ASLA bloke etmemeli; ek düşer, kullanıcı metni kırpılmaz."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
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


def test_an_applied_palette_is_marked_as_applied(tmp_path, monkeypatch, dizinler):
    """`applied` bayrağının karşı ucu: normal yolda True olmalı."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    record = _gen(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    assert record["palette"]["applied"] is True


@pytest.mark.parametrize("field,bad", [
    ("palette_hex", "#GGGGGG"), ("palette_hex", "zzz"),
    ("palette_mode", "kaleidoscope"), ("palette_strength", "loud"),
])
def test_generate_rejects_bad_palette_fields(tmp_path, monkeypatch, field, bad, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert _gen(client, **{field: bad}).status_code == 422


def test_generate_rejects_unknown_field(tmp_path, monkeypatch, dizinler):
    """Yeni eklenen extra="forbid": bayat sunucu sessiz kalmasın."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert _gen(client, palette_hexx=SEED).status_code == 422


def test_empty_palette_hex_means_no_palette(tmp_path, monkeypatch, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
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


def test_edit_appends_the_palette_and_uses_edit_framing(tmp_path, monkeypatch, dizinler):
    """En kritik ayrım: üretim ifadesi referans görselin kompozisyonunu yok eder."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _edit(client, palette_hex=SEED, palette_mode="complement")
    assert r.status_code == 200, r.text
    assert sent[0].startswith("arka planı sadeleştir")
    assert "composition" in sent[0]
    assert "do not repaint or move anything" in sent[0].lower()


def test_edit_without_a_palette_sends_the_prompt_verbatim(tmp_path, monkeypatch, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _edit(client)
    assert r.status_code == 200, r.text
    assert sent == ["arka planı sadeleştir"]
    assert r.json()["images"][0]["palette"] is None


def test_edit_echoes_the_palette_so_a_stale_server_is_detectable(tmp_path, monkeypatch, dizinler):
    """multipart'ta extra="forbid" yok; arayüz bayat sunucuyu bu yankıyla anlar."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    record = _edit(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    assert record["palette"]["seed"] == SEED
    assert record["palette"]["mode"] == "triad"


@pytest.mark.parametrize("field,bad", [
    ("palette_hex", "#GGGGGG"), ("palette_mode", "kaleidoscope"),
    ("palette_strength", "loud"),
])
def test_edit_rejects_bad_palette_fields(tmp_path, monkeypatch, field, bad, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    assert _edit(client, **{field: bad}).status_code == 422


# ── Kayıtlı paletin dondurulmuş adları ──────────────────────────────────────

def test_saved_palette_frozen_names_are_used_in_the_prompt(tmp_path, monkeypatch, dizinler):
    """Kütüphanede görünen ad ile prompt'a giden ad ayrışmamalı.

    Palet çevrimiçi adlarla kaydedilir; sonra önbellek temizlenir (sunucu
    yeniden başlamış gibi). Yeniden hesaplasaydık yerel adlara düşerdi.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    monkeypatch.setattr(cn, "_fetch_name", lambda h: "Harlequin")
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": GAP_SEED,
                                              "mode": "triad"}).json()["palette"]
    assert any("harlequin" in c["name"] for c in saved["colors"])

    cn.reset_breaker()  # önbellek boş: yeniden hesaplama betimleyiciye düşerdi
    monkeypatch.setattr(cn, "_fetch_name", lambda h: None)
    _gen(client, palette_hex=GAP_SEED, palette_mode="triad", palette_id=saved["id"])
    for color in saved["colors"]:
        assert color["name"] in sent[0]


def test_saved_palette_id_wins_over_a_mismatched_mode(tmp_path, monkeypatch, dizinler):
    """Kayıt kaynak: id verilmişse kaydın modu/renkleri geçerli."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    saved = client.post("/api/palettes", json={"name": "Marka", "seed": SEED,
                                              "mode": "quad"}).json()["palette"]
    record = _gen(client, palette_hex="#2e5fa3", palette_mode="triad",
                  palette_id=saved["id"]).json()["images"][0]
    assert record["palette"]["mode"] == "quad"
    assert record["palette"]["seed"] == SEED
    assert record["palette"]["id"] == saved["id"]
    assert record["palette"]["name"] == "Marka"


def test_a_deleted_palette_does_not_block_generation(tmp_path, monkeypatch, dizinler):
    """Silinmiş palet hata vermez, (seed, mode)'dan yeniden hesaplanır."""
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="triad",
             palette_id="deadbeefcafe")
    assert r.status_code == 200, r.text
    assert "Color direction" in sent[0]
    assert r.json()["images"][0]["palette"]["mode"] == "triad"


def test_edit_also_honors_a_saved_palette_id(tmp_path, monkeypatch, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
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

def test_logo_derivative_inherits_the_palette(tmp_path, monkeypatch, fake_composite, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler, real_png=True)
    monkeypatch.setattr(appmod.composite, "composite_logo", fake_composite)

    src = _gen(client, palette_hex=SEED, palette_mode="triad").json()["images"][0]
    # Yerleşik logo kaldırıldı: bindirme artık kütüphaneden bir varlık istiyor.
    asset = astore.save_asset("logos", b"\x89PNG-logo", "logo",
                              str(tmp_path / "assets"), now="2026-07-23T10:00:00")
    r = client.post("/api/logo", json={"id": src["id"], "asset_id": asset["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["image"]["palette"]["seed"] == SEED


def test_legacy_history_records_without_palette_are_tolerated(tmp_path, monkeypatch, dizinler):
    """Eski kayıtlarda alan hiç yok — geçiş (migration) gerekmemeli."""
    client, _ = _client(tmp_path, monkeypatch, dizinler)
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


# ── Bozuk palettes.json ─────────────────────────────────────────────────────

@pytest.mark.parametrize("broken", [
    {"mode": "bogus", "colors": []},                    # geçersiz mod
    {"seed": "kırmızı", "colors": []},                  # geçersiz hex
    {"mode": None, "seed": None, "colors": []},         # alanlar boş
    {"colors": [{"hex": "#c86a3c"}]},                   # ad yok
    {"colors": "yeşil"},                                # liste bile değil
    {"colors": [{"name": "copper orange"}]},            # hex yok
])
def test_a_corrupt_saved_palette_does_not_break_generation(tmp_path, monkeypatch, broken, dizinler):
    """Elle düzenlenmiş/bozulmuş kayıt üretimi 500'e düşürmemeli.

    Bütün okuma katmanları bozuk JSON'da boş listeye düşüyor (palette_store._read,
    storage._read_history, folders._read); kaydın İÇERİĞİ tek istisnaydı:
    `mode`/`seed` doğrudan palette.harmony'ye gidiyor, ValueID yakalanmadan
    500 dönüyordu. Silinmiş palet zaten bloke etmiyor (bkz. yukarıdaki test) —
    bozuk palet de etmemeli.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    record = {"id": "a1b2c3d4e5f6", "name": "Bozuk", "seed": SEED,
              "mode": "triad", "strength": "balanced", **broken}
    (output / "palettes.json").write_text(json.dumps([record]), encoding="utf-8")

    r = _gen(client, palette_hex=SEED, palette_mode="analogic",
             palette_id="a1b2c3d4e5f6")
    assert r.status_code == 200, r.text
    assert "Color direction" in sent[0]


def test_the_prompt_limit_is_declared_once(tmp_path, monkeypatch):
    """Sınır iki yerde ayrı ayrı yazılırsa biri değişip diğeri kalır."""
    field = appmod.GenerateRequest.model_fields["prompt"]
    limits = [m.max_length for m in field.metadata if hasattr(m, "max_length")]
    assert limits == [appmod.MAX_PROMPT_CHARS]


# ── palette_drop: seçili paletten renk çıkarma ──────────────────────────────
#
# Palet 5 rengi zorluyordu; kullanıcı bazen 3-4 tanesini istiyor. Çıkarma
# İNDEKSLE yapılıyor, hex'le değil: renk SIRASI prompt'ta anlam taşıyor
# (_ORDER_CUE) ve aynı hex bir palette iki kez düşebilir — hex'le çıkarmak
# ikisini birden düşürürdü.

def _colors_of(seed=SEED, mode="analogic"):
    """Sunucunun çözeceği renklerin aynısı (ağ kapalı, aynı deterministik yol)."""
    return appmod._resolve_palette(seed, mode, offline=True)


def test_palette_drop_removes_only_the_named_indices(tmp_path, monkeypatch, dizinler):
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    colors = _colors_of()
    dropped, kept = colors[2], colors[:2] + colors[3:]

    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=[2])
    assert r.status_code == 200, r.text

    assert dropped["hex"] not in sent[0], "çıkarılan renk hâlâ prompt'ta"
    for color in kept:
        assert color["hex"] in sent[0], f"kalan renk düştü: {color['hex']}"


def test_palette_drop_preserves_the_order_of_the_survivors(tmp_path, monkeypatch, dizinler):
    """Sıra prompt'ta ANLAM taşıyor: "baştaki renkler geniş alanlara, sondaki
    küçük vurgu olarak" (palette._ORDER_CUE). Ortadan bir renk çıkarılınca
    kalanlar yeniden dizilmemeli, yoksa kullanıcının gördüğü şerit ile modele
    giden ağırlık sırası ayrışır.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    colors = _colors_of()
    kept = colors[:1] + colors[2:4]      # 1 ve 4 çıkarıldı

    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=[1, 4])
    assert r.status_code == 200, r.text

    positions = [sent[0].index(c["hex"]) for c in kept]
    assert positions == sorted(positions), "kalan renklerin sırası değişti"


def test_palette_drop_is_echoed_in_the_record(tmp_path, monkeypatch, dizinler):
    """Kayıt hem KALANLARI (çip/galeri onu gösteriyor) hem çıkarılan
    indeksleri taşımalı — ikincisi olmadan geçmişten aynı durum kurulamaz.
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=[3, 0])
    assert r.status_code == 200, r.text

    pal = r.json()["images"][0]["palette"]
    assert len(pal["colors"]) == palette.COLORS_PER_PALETTE - 2
    assert pal["dropped"] == [0, 3], "çıkarılan indeksler sıralı kaydedilmeli"
    assert pal["applied"] is True


def test_no_drop_leaves_the_record_and_prompt_untouched(tmp_path, monkeypatch, dizinler):
    """GERİLEME BEKÇİSİ: alan gönderilmeyince her şey v1.10'daki gibi.

    Bu özellik palet yolunun en sıcak noktasına dokunuyor; varsayılan davranışın
    birebir korunduğu ayrıca çivilenmeli.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="analogic")
    assert r.status_code == 200, r.text

    pal = r.json()["images"][0]["palette"]
    assert len(pal["colors"]) == palette.COLORS_PER_PALETTE
    assert pal["dropped"] == []
    for color in _colors_of():
        assert color["hex"] in sent[0]


@pytest.mark.parametrize("drop", [[0, 1, 2, 3, 4], [4, 3, 2, 1, 0]])
def test_palette_drop_rejects_dropping_every_color(tmp_path, monkeypatch, drop, dizinler):
    """Hepsi çıkarılırsa prompt_suffix boş metin döner ve kullanıcı renksiz
    sonucu açıklayamaz — tam olarak `applied: False` bayrağının var olma
    nedeni olan sessiz sapma. Gürültülü 422 tercih edildi.
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=drop)
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("drop", [[5], [-1], [0, 99]])
def test_palette_drop_rejects_out_of_range_index(tmp_path, monkeypatch, drop, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=drop)
    assert r.status_code == 422, r.text


def test_palette_drop_tolerates_repeated_indices(tmp_path, monkeypatch, dizinler):
    """Aynı indeks iki kez gelirse küme gibi davranılır — istemci hatası
    yüzünden üretim bloke edilmemeli (silinmiş/bozuk paletteki duruşun aynısı).
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = _gen(client, palette_hex=SEED, palette_mode="analogic", palette_drop=[2, 2])
    assert r.status_code == 200, r.text
    pal = r.json()["images"][0]["palette"]
    assert len(pal["colors"]) == palette.COLORS_PER_PALETTE - 1
    assert pal["dropped"] == [2]


def test_palette_drop_indexes_a_saved_palettes_frozen_colors(tmp_path, monkeypatch, dizinler):
    """KAYITLI palette indeksler DONMUŞ listeye göre çözülmeli.

    Kayıt 4 renkle donmuşsa (kullanıcı çıkarıp kaydetmişse) indeks 3 o
    listenin dördüncüsü demektir, yeniden hesaplanan 5'linin değil. Filtre bu
    yüzden `colors` çözüldükten SONRA, tek noktada uygulanıyor.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    frozen = [{"hex": "#111111", "name": "bir"}, {"hex": "#222222", "name": "iki"},
              {"hex": "#333333", "name": "üç"}]
    record = {"id": "a1b2c3d4e5f6", "name": "Donmuş", "seed": SEED,
              "mode": "triad", "strength": "balanced", "colors": frozen}
    (output / "palettes.json").write_text(json.dumps([record]), encoding="utf-8")

    r = _gen(client, palette_hex=SEED, palette_mode="analogic",
             palette_id="a1b2c3d4e5f6", palette_drop=[1])
    assert r.status_code == 200, r.text
    assert "#111111" in sent[0] and "#333333" in sent[0]
    assert "#222222" not in sent[0], "donmuş listenin ikincisi çıkarılmadı"


def test_palette_drop_rejects_emptying_a_saved_palette(tmp_path, monkeypatch, dizinler):
    """Donmuş liste 5'ten kısa olabilir; model sınırı tek başına yetmez.

    3 renkli bir kayıtta [0,1,2] model doğrulamasını GEÇER (5'ten az) ama
    sonuç boş palet olur. İkinci kapı çözümlemeden sonra.
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    frozen = [{"hex": "#111111", "name": "bir"}, {"hex": "#222222", "name": "iki"},
              {"hex": "#333333", "name": "üç"}]
    record = {"id": "a1b2c3d4e5f6", "name": "Donmuş", "seed": SEED,
              "mode": "triad", "strength": "balanced", "colors": frozen}
    (output / "palettes.json").write_text(json.dumps([record]), encoding="utf-8")

    r = _gen(client, palette_hex=SEED, palette_mode="analogic",
             palette_id="a1b2c3d4e5f6", palette_drop=[0, 1, 2])
    assert r.status_code == 422, r.text


def test_edit_parses_comma_separated_palette_drop(tmp_path, monkeypatch, dizinler):
    """Multipart yolu: arayüz diziyi FormData'ya "0,3" olarak yazıyor.

    core.js paleti genel bir döngüyle (`Object.entries`) forma basıyor — orada
    JS dizisi kendiliğinden virgüllü metne dönüyor. Elle sayıma çevirmek bir
    kez `palette_id`'yi düşürmüştü (core.js'teki not), o yüzden döngü kalıyor
    ve ayrıştırma sunucu tarafında çivileniyor.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    colors = _colors_of(mode="complement")

    r = _edit(client, palette_hex=SEED, palette_mode="complement",
              palette_drop="0,3")
    assert r.status_code == 200, r.text
    assert colors[0]["hex"] not in sent[0]
    assert colors[3]["hex"] not in sent[0]
    assert colors[1]["hex"] in sent[0]
    assert r.json()["images"][0]["palette"]["dropped"] == [0, 3]


@pytest.mark.parametrize("bad", ["abc", "0;3", "1.5", "0,,3", "0,99"])
def test_edit_rejects_a_malformed_palette_drop(tmp_path, monkeypatch, bad, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = _edit(client, palette_hex=SEED, palette_mode="complement", palette_drop=bad)
    assert r.status_code == 422, r.text


def test_edit_treats_an_empty_palette_drop_as_no_drop(tmp_path, monkeypatch, dizinler):
    """Arayüz hiçbir şey çıkarılmadığında alanı hiç göndermiyor; boş dize de
    (ör. elle kurulmuş bir istek) "çıkarma yok" demek — 422 değil.
    """
    client, sent = _client(tmp_path, monkeypatch, dizinler)
    r = _edit(client, palette_hex=SEED, palette_mode="complement", palette_drop="")
    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["palette"]["dropped"] == []


def test_saving_a_palette_freezes_only_the_survivors(tmp_path, monkeypatch, dizinler):
    """Kalıcı 4 renkli palet yolu: çıkar → kaydet.

    Kayıt donmuş `colors` tuttuğu için (palette_store başlığı) 4 renkle donar
    ve sonraki kullanımlarda çıkarma göndermek GEREKMEZ. Kayıtlı paleti
    sonradan düzenleme özelliği bu yüzden yazılmadı.
    """
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    full = _colors_of(mode="triad")

    r = client.post("/api/palettes", json={"name": "Dörtlü", "seed": SEED,
                                           "mode": "triad", "drop": [2]})
    assert r.status_code == 200, r.text
    saved = r.json()["palette"]
    assert len(saved["colors"]) == palette.COLORS_PER_PALETTE - 1
    assert full[2]["hex"] not in [c["hex"] for c in saved["colors"]]

    # Kaydedilen palet ÇIKARMASIZ kullanıldığında da 4 renk gitmeli.
    client2, sent2 = _client(tmp_path, monkeypatch, dizinler)
    r2 = _gen(client2, palette_hex=SEED, palette_mode="triad",
              palette_id=saved["id"])
    assert r2.status_code == 200, r2.text
    assert full[2]["hex"] not in sent2[0]
    assert r2.json()["images"][0]["palette"]["dropped"] == []


def test_saving_a_palette_rejects_dropping_everything(tmp_path, monkeypatch, dizinler):
    client, _ = _client(tmp_path, monkeypatch, dizinler)
    r = client.post("/api/palettes", json={"name": "Boş", "seed": SEED,
                                           "mode": "triad", "drop": [0, 1, 2, 3, 4]})
    assert r.status_code == 422, r.text
