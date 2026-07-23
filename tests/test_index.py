from fastapi.testclient import TestClient
import app as appmod


def test_index_served():
    c = TestClient(appmod.app)
    r = c.get("/")
    assert r.status_code == 200
    assert "GPT-Image Studio" in r.text
    assert 'id="prompt"' in r.text
    # v1.1: düzenle akışı UI'da var
    assert 'id="edit-prompt"' in r.text
    assert 'id="edit-file"' in r.text
