"""Model Arena: aynı prompt'un birden çok modelde koşturulduğu tur.

Turun sütunları AYRI `/api/generate` istekleriyle geliyor — fan-out sunucuda
DEĞİL istemcide. Bu sunucu tarafının en önemli sonucu şu: uçta "arena" diye bir
kavram YOK, yalnızca kayıtları birbirine bağlayan bir ETİKET (`arena_id`) ve
kazananı işaretleyen bir uç var. Aşağıdaki iddialar tam olarak o iki şeyi
kovalıyor; paralelliğin kendisi ön yüzün işi (tests/test_index.py).

Fan-out'un neden sunucuda olmadığı `models.GenerateRequest.arena_id`de yazılı.
"""
import pytest
from fastapi.testclient import TestClient

import app as appmod
import azure_client as ac
import catalog
import storage

# Galeri/klasör/üretim rotaları DB'de (Faz 1 / 5): test kullanıcısı gerçek satır,
# `db.oturum` bu dosyanın motoruna bağlı — gerekçe tests/conftest.py::depo_db.
pytestmark = pytest.mark.usefixtures("depo_db")

ARENA = "aaaa1111bbbb"


@pytest.fixture
def client(tmp_path, monkeypatch, dizinler):
    dizinler(output_dir=str(tmp_path))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    return TestClient(appmod.app)


def _uret(client, **ek):
    govde = {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1}
    govde.update(ek)
    return client.post("/api/generate", json=govde)


# ── Etiket ─────────────────────────────────────────────────────────────


def test_arena_id_reaches_the_record(client):
    r = _uret(client, arena_id=ARENA)

    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["arena_id"] == ARENA


def test_a_plain_run_carries_no_arena_key_at_all(client):
    """Arena DIŞI üretim bugünküyle bayt bayt aynı kalıyor.

    `session_id`/`imported` ile aynı koşullu desen: alanın YOKLUĞU "arena değil"
    demek. `"arena_id": null` yazmak history.json'ın tamamını değiştirirdi ve
    eski-biçim testlerinin kovaladığı şey tam olarak bu.
    """
    kayit = _uret(client).json()["images"][0]

    assert "arena_id" not in kayit
    assert "arena_win" not in kayit


def test_an_empty_arena_id_is_not_an_arena(client):
    """Boş dize = alan gönderilmemiş gibi. İstemcinin koşullu gövdesinin karşılığı."""
    assert "arena_id" not in _uret(client, arena_id="").json()["images"][0]


def test_a_malformed_arena_id_is_rejected_loudly(client):
    """Sessizce düşürmek seçenek değil: sütunlar birbirini bulamaz ve sebebi görünmez."""
    r = _uret(client, arena_id="../kacis")

    assert r.status_code == 422
    assert "arena_id" in r.json()["detail"]


def test_two_models_in_one_round_share_the_tag_and_keep_their_own_credit(
        client, monkeypatch):
    """Defterin kabul ölçütü: iki üretim tek turda, künyelerinde model + kredi.

    Kayıt başına TEK model, TEK kredi — turun ortak yanı yalnızca `arena_id`.
    Kredi model başına ayrı çözülüyor, yani karşılaştırma gerçek bir fatura
    farkı gösteriyor (Gemini Pro'nun 27'si Azure'ın 8'inin üç katı).
    """
    monkeypatch.setattr(appmod.providers, "generate", lambda *a, **k: [b"\x89PNG"])

    azure = _uret(client, arena_id=ARENA, model="azure-gpt-image-2",
                  quality="medium").json()["images"][0]
    gemini = _uret(client, arena_id=ARENA, model="gemini-nano-banana-pro",
                   size="1:1", quality="2K").json()["images"][0]

    assert azure["arena_id"] == gemini["arena_id"] == ARENA
    assert azure["id"] != gemini["id"]
    assert azure["model"] == "azure-gpt-image-2"
    assert gemini["model"] == "gemini-nano-banana-pro"
    assert azure["credits"] == catalog.cost_for(
        catalog.image_model("azure-gpt-image-2"), "medium")
    assert gemini["credits"] == catalog.cost_for(
        catalog.image_model("gemini-nano-banana-pro"), "2K")


# ── Kazanan ────────────────────────────────────────────────────────────


@pytest.fixture
def tur(client, monkeypatch):
    """İki sütunlu bitmiş bir arena turu döndürür: (client, [kayıt, kayıt])."""
    monkeypatch.setattr(appmod.providers, "generate", lambda *a, **k: [b"\x89PNG"])
    a = _uret(client, arena_id=ARENA, model="azure-gpt-image-2").json()["images"][0]
    b = _uret(client, arena_id=ARENA, model="openai-gpt-image-2").json()["images"][0]
    return client, [a, b]


def _kayitlar(client):
    return {r["id"]: r for r in client.get("/api/history").json()["images"]}


def test_the_winner_is_marked_and_the_loser_is_kept(tur):
    """İşaret bir tercih kaydı, çöp kutusu değil: elenen sonuç galeride duruyor."""
    client, (a, b) = tur

    r = client.post(f"/api/arena/{ARENA}/winner", json={"image_id": b["id"]})

    assert r.status_code == 200, r.text
    kayitlar = _kayitlar(client)
    assert kayitlar[b["id"]]["arena_win"] is True
    assert "arena_win" not in kayitlar[a["id"]]
    assert len(kayitlar) == 2


def test_a_second_choice_moves_the_mark_instead_of_adding_one(tur):
    """Tur başına TEK kazanan. İki işaret, karşılaştırmanın kendisini anlamsız yapardı."""
    client, (a, b) = tur

    client.post(f"/api/arena/{ARENA}/winner", json={"image_id": b["id"]})
    client.post(f"/api/arena/{ARENA}/winner", json={"image_id": a["id"]})

    kayitlar = _kayitlar(client)
    assert kayitlar[a["id"]]["arena_win"] is True
    assert "arena_win" not in kayitlar[b["id"]]


def test_marking_the_same_winner_twice_is_idempotent(tur):
    client, (a, b) = tur

    client.post(f"/api/arena/{ARENA}/winner", json={"image_id": a["id"]})
    ilk = _kayitlar(client)
    client.post(f"/api/arena/{ARENA}/winner", json={"image_id": a["id"]})

    assert _kayitlar(client) == ilk


def test_a_winner_from_another_round_is_a_404(tur):
    """Görsel VAR ama o turun içinde değil: sessiz bir no-op yerine 404.

    Sessiz kalsaydı istemci işareti çizer, yenilemede kaybolurdu.
    """
    client, (a, _) = tur
    baska = _uret(client, arena_id="cccc3333dddd").json()["images"][0]

    r = client.post(f"/api/arena/{ARENA}/winner", json={"image_id": baska["id"]})

    assert r.status_code == 404
    assert "arena_win" not in _kayitlar(client)[baska["id"]]


def test_an_unknown_round_is_a_404(tur):
    client, (a, _) = tur

    r = client.post("/api/arena/ffff9999ffff/winner", json={"image_id": a["id"]})

    assert r.status_code == 404


def test_a_path_traversal_arena_id_cannot_reach_the_store(tur):
    """Yol parçası taşıyan id `os.path.basename` + `_SAFE_ID` kapısında ölüyor."""
    client, (a, _) = tur

    r = client.post("/api/arena/..%2F..%2Fetc/winner", json={"image_id": a["id"]})

    assert r.status_code in (307, 404)


# ── Depo katmanı ───────────────────────────────────────────────────────


def test_the_store_writes_the_mark_in_a_single_pass(tmp_path):
    """Kazanana yazmak ve kardeşten silmek TEK yazım: arada iki kazanan görünmesin.

    İki ayrı yazım olsaydı `_write_history` dosyanın tamamını iki kez
    değiştirir, arada okuyan bir istemci tutarsız bir tur görürdü
    (`set_folder_many`'nin gerekçesinin aynısı).
    """
    yazimlar = []
    gercek = storage._write_history

    def sayan(output_dir, history):
        yazimlar.append([dict(r) for r in history])
        return gercek(output_dir, history)

    a = storage.save(b"\x89PNG", {"arena_id": ARENA}, str(tmp_path), now="2026-01-01T00:00:00")
    b = storage.save(b"\x89PNG", {"arena_id": ARENA}, str(tmp_path), now="2026-01-01T00:00:01")
    storage._write_history = sayan
    try:
        assert storage.set_arena_winner(ARENA, b["id"], str(tmp_path))
    finally:
        storage._write_history = gercek

    assert len(yazimlar) == 1
    assert [r.get("arena_win") for r in yazimlar[0]] == [None, True]
    assert a["id"] != b["id"]


def test_the_store_rejects_an_id_that_is_not_hex(tmp_path):
    storage.save(b"\x89PNG", {"arena_id": ARENA}, str(tmp_path), now="2026-01-01T00:00:00")

    assert storage.set_arena_winner(ARENA, "../kacis", str(tmp_path)) is False
    assert storage.set_arena_winner("../kacis", ARENA, str(tmp_path)) is False


def test_records_outside_the_round_are_not_touched(tmp_path):
    """Başka turların (ve arena olmayan kayıtların) işareti korunuyor."""
    disarda = storage.save(b"\x89PNG", {}, str(tmp_path), now="2026-01-01T00:00:00")
    onceki = storage.save(b"\x89PNG", {"arena_id": "cccc3333dddd"}, str(tmp_path),
                          now="2026-01-01T00:00:01")
    storage.set_arena_winner("cccc3333dddd", onceki["id"], str(tmp_path))
    bizim = storage.save(b"\x89PNG", {"arena_id": ARENA}, str(tmp_path),
                         now="2026-01-01T00:00:02")

    storage.set_arena_winner(ARENA, bizim["id"], str(tmp_path))

    kayitlar = {r["id"]: r for r in storage.list_history(str(tmp_path))}
    assert kayitlar[onceki["id"]]["arena_win"] is True
    assert "arena_win" not in kayitlar[disarda["id"]]
