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


# ── İndirme ucu ─────────────────────────────────────────────────────
#
# Bu üç iddianın ortak yanı: koruduğu kırılma YALNIZCA telefonda görünüyor ve
# CI'da telefon yok. Android WebView, HTML'in `download` özniteliğini YOK
# SAYIYOR; `Content-Disposition` taşımayan bir `image/png` adresi onun
# çizebileceği bir şey olduğu için kayıt dinleyicisi hiç tetiklenmiyor ve
# indirme SESSİZCE hiç olmuyor. Masaüstünde ve tarayıcıda aynı kod kusursuz
# çalıştığı için başlığın düşmesi hiçbir yerde fark edilmezdi.


def test_the_download_endpoint_marks_the_png_as_an_attachment(tmp_path, monkeypatch):
    """`/api/output/{id}/download` indirmeyi İNDİRME olarak işaretlemek zorunda.

    Dosya adı da buradan geliyor: Android tarafı adı
    `URLUtil.guessFileName(url, contentDisposition, mimeType)` ile üretiyor, yani
    çıpanın `download=` değerinden DEĞİL bu başlıktan okuyor. Başlık düşerse
    telefonda indirme hiç olmaz; ad düşerse dosya URL yolundan türetilmiş
    anlamsız bir adla iner.
    """
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    rec = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()["images"][0]

    r = c.get(f"/api/output/{rec['id']}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment;"), cd
    assert f'filename="{rec["id"]}.png"' in cd, cd
    assert r.content == b"\x89PNG"


def test_the_drawing_route_stays_inline(tmp_path, monkeypatch):
    """`/output/{filename}` `attachment` DEMEMELİ — o adres bir ÇİZİM adresi.

    Aynı adres her galeri küçük resminin ve büyüteç görselinin `<img src>`'i.
    İndirme başlığını oraya eklemek, görsellerin ÇİZİLMESİNİ bir indirme
    başlığına bağlamak olurdu: kazanılacak şeyin bedeli, kaybetmeye hiç razı
    olunmayacak şey. İndirme bu yüzden AYRI bir uçta.
    """
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [b"\x89PNG"])
    c = _client(tmp_path, monkeypatch)
    rec = c.post("/api/generate", json={"prompt": "cat", "size": "1024x1024",
                                        "quality": "medium", "n": 1}).json()["images"][0]

    r = c.get(f"/output/{rec['filename']}")
    assert r.status_code == 200
    assert "attachment" not in r.headers.get("content-disposition", "")


def test_the_download_endpoint_reuses_the_single_traversal_guard(tmp_path, monkeypatch):
    """Uydurma ve yol kaçışlı id'ler 404 — kendi guard'ını yazmıyor.

    Koruma `_output_png_path`ten geliyor (deponun tek kapısı). Yeni uç kendi
    `os.path.basename`ini yazmaya kalkarsa bu iddia onu yakalamaz — ama guard'ın
    HİÇ olmadığı hâli yakalar, ki tehlikeli olan o.
    """
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/output/deadbeef0000/download").status_code == 404
    # `..%2F..%2Fetc%2Fpasswd` — kodlanmış yol kaçışı
    assert c.get("/api/output/..%2F..%2Fetc%2Fpasswd/download").status_code == 404
