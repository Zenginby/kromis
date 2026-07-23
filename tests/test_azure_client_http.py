import base64
import pytest
import azure_client as ac


class FakeResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json


class FakeClient:
    """httpx.Client yerine geçen minimal sahte istemci."""
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json}
        return self._response


def test_generate_calls_correct_endpoint_and_decodes():
    raw = b"\x89PNG"
    b64 = base64.b64encode(raw).decode()
    client = FakeClient(FakeResponse(200, {"data": [{"b64_json": b64}]}))
    out = ac.generate(
        "cat", "1024x1024", "medium", 1,
        client=client,
        credentials=("secret-key", "https://ex.azure.com/openai/v1/"),
    )
    assert out == [raw]
    assert client.last_call["url"] == "https://ex.azure.com/openai/v1/images/generations"
    assert client.last_call["headers"]["Authorization"] == "Bearer secret-key"
    assert client.last_call["json"]["model"] == "gpt-image-2"


def test_generate_raises_friendly_on_error():
    client = FakeClient(FakeResponse(401, {"error": {"message": "nope"}}))
    with pytest.raises(ac.AzureImageError) as exc:
        ac.generate("cat", "1024x1024", "medium", 1,
                    client=client, credentials=("k", "https://ex/"))
    assert "401" in str(exc.value)


def test_load_credentials_reads_env(tmp_path):
    env = tmp_path / "creds.env"
    env.write_text('AZURE_IMAGE_API_KEY=abc123\nAZURE_IMAGE_BASE_URL=https://x/openai/v1/\n')
    key, url = ac.load_credentials(str(env))
    assert key == "abc123"
    assert url == "https://x/openai/v1/"
