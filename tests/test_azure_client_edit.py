import base64
import pytest
import azure_client as ac


class FakeResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json


class FakeMultipartClient:
    """httpx.Client yerine geçer; data+files ile POST'u yakalar."""
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "data": data, "files": files}
        return self._response


def test_edit_calls_edits_endpoint_with_multipart_and_decodes():
    raw = b"\x89PNG-edited"
    b64 = base64.b64encode(raw).decode()
    client = FakeMultipartClient(FakeResponse(200, {"data": [{"b64_json": b64}]}))
    out = ac.edit(
        "make it blue", b"\x89PNG-src", "src.png", "1024x1024", "low", 1,
        client=client, credentials=("secret-key", "https://ex.azure.com/openai/v1/"),
    )
    assert out == [raw]
    call = client.last_call
    assert call["url"] == "https://ex.azure.com/openai/v1/images/edits"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    # Content-Type multipart client tarafından set edilmeli -> header'da elle Content-Type YOK
    assert "Content-Type" not in call["headers"]
    assert call["data"]["model"] == "gpt-image-2"
    assert call["data"]["prompt"] == "make it blue"
    assert call["data"]["size"] == "1024x1024"
    assert call["data"]["quality"] == "low"
    assert str(call["data"]["n"]) == "1"
    # image dosya olarak gönderilmeli: (filename, bytes, content-type)
    fname, fbytes, ctype = call["files"]["image"]
    assert fname == "src.png"
    assert fbytes == b"\x89PNG-src"
    assert ctype == "image/png"


def test_edit_raises_friendly_on_error():
    client = FakeMultipartClient(FakeResponse(429, None))
    with pytest.raises(ac.AzureImageError) as exc:
        ac.edit("x", b"img", "a.png", "1024x1024", "low", 1,
                client=client, credentials=("k", "https://ex/"))
    assert "429" in str(exc.value)
