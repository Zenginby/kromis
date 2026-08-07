import os
from fastapi.testclient import TestClient
import azure_client as ac
import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path))
    return TestClient(appmod.app)


def test_generate_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 200
    imgs = r.json()["images"]
    assert len(imgs) == 1 and imgs[0]["prompt"] == "cat"


def test_generate_labels_the_image_with_the_session_it_was_born_in(tmp_path, monkeypatch):
    """Birleşik döküm: oturum içinde üretilen görsel o oturumu taşır."""
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG", b"\x89PNG2"])
    c = _client(tmp_path, monkeypatch)

    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 2,
                                      "session_id": "beef1234beef"})

    assert r.status_code == 200, r.text
    assert [i["session_id"] for i in r.json()["images"]] == ["beef1234beef"] * 2


def test_generate_without_a_session_writes_no_session_key(tmp_path, monkeypatch):
    """Medya'dan doğrudan üretim ve otomatik kayıt KAPALI hâli: etiket yok."""
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)

    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 1})

    assert "session_id" not in r.json()["images"][0]


def test_generate_rejects_a_malformed_session_id(tmp_path, monkeypatch):
    """Biçim kapısı VAR, varlık kapısı YOK (bkz. app._check_session).

    Sessizce düşürmek olmaz: kullanıcı üretimini oturumda göremez ve sebebi
    hiçbir yerde görünmez.
    """
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)

    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 1,
                                      "session_id": "../../etc/passwd"})

    assert r.status_code == 422


def test_generate_accepts_a_session_that_is_not_saved_yet(tmp_path, monkeypatch):
    """Etiket BİLEREK zayıf: chats.json'da karşılığı olmayan id de yazılır.

    Varlık kapısı konsaydı — `_check_folder`'ın yaptığı gibi — oturum kaydı
    yazılmadan önce (ya da başka bir sekmede silindikten sonra) yapılan üretim
    422 ile düşerdi: pahalı bir Azure turu bir ETİKET yüzünden kaybedilirdi.
    Ters yön zaten hoşgörülü (silinmiş görselin sarkan id'si dökümü çökertmiyor),
    simetrik duruş tutarlı olan.
    """
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)

    r = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                      "quality": "medium", "n": 1,
                                      "session_id": "0123456789ab"})

    assert r.status_code == 200
    assert r.json()["images"][0]["session_id"] == "0123456789ab"


def test_generate_rejects_bad_size(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "x", "size": "99x99",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 422


def test_generate_maps_azure_error(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ac.AzureImageError("Azure isteği başarısız (HTTP 429).")
    monkeypatch.setattr(ac, "generate", boom)
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/generate", json={"prompt": "x", "size": "1024x1024",
                                      "quality": "medium", "n": 1})
    assert r.status_code == 502
    assert "429" in r.json()["detail"]


def test_history_returns_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                  "quality": "low", "n": 1})
    r = c.get("/api/history")
    assert r.status_code == 200 and len(r.json()["images"]) == 1


def test_output_directory_name_returns_404(tmp_path, monkeypatch):
    os.makedirs(os.path.join(str(tmp_path), "sub"))
    c = _client(tmp_path, monkeypatch)
    r = c.get("/output/sub")
    assert r.status_code == 404


def test_output_missing_file_returns_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/output/nope.png")
    assert r.status_code == 404
