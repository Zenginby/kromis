import base64
import pytest
import azure_client as ac


def test_build_payload_includes_required_fields():
    payload = ac.build_payload("a cat", "1024x1024", "medium", 2)
    assert payload == {
        "model": "gpt-image-2",
        "prompt": "a cat",
        "size": "1024x1024",
        "quality": "medium",
        "n": 2,
    }


def test_decode_images_returns_png_bytes():
    raw = b"\x89PNG\r\n"
    b64 = base64.b64encode(raw).decode()
    out = ac.decode_images({"data": [{"b64_json": b64}, {"b64_json": b64}]})
    assert out == [raw, raw]


def test_map_error_401_is_friendly():
    msg = ac.map_error(401, {"error": {"message": "bad key"}})
    assert "yetki" in msg.lower() or "key" in msg.lower()
    assert "429" not in msg


def test_map_error_429_mentions_rate():
    assert "429" in ac.map_error(429, None) or "limit" in ac.map_error(429, None).lower()
