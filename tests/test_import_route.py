"""POST /api/import — bilgisayardan bırakılan dosyanın galeriye aktarılması.

Neden ayrı dosya: bu rota, kayıtların ÜRETİMDEN DOĞMASI kuralını kıran ilk
yer. Diğer bütün `storage.save` çağrıları Azure'dan dönen baytları kaydediyor;
burada baytlar kullanıcının diskinden geliyor, prompt yok, Azure'a hiç
çıkılmıyor. O yüzden sınırlar (doğrulama, PNG'ye kodlama, klasör, etiket) tek
tek çivilenmeli — arayüzde sürükle-bırak sessizce başarısız olabilen bir yol.
"""
import io

from fastapi.testclient import TestClient
from PIL import Image

import app as appmod
import azure_client as ac

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png(color=(30, 80, 200, 255), size=(48, 24)) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", size, color).save(b, "PNG")
    return b.getvalue()


def _jpeg(color=(200, 40, 40), size=(40, 30)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "JPEG")
    return b.getvalue()


def _client(tmp_path, monkeypatch) -> TestClient:
    """Ağa çıkmayan istemci — tests/test_folders.py:20 ile aynı kalıp."""
    monkeypatch.setattr(appmod, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(appmod, "ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png(size=(64, 64))])
    monkeypatch.setattr(ac, "edit", lambda *a, **k: [_png(size=(64, 64))])
    return TestClient(appmod.app)


def _new_folder(c, name="Kurban") -> str:
    r = c.post("/api/folders", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["folder"]["id"]


def _import(c, data=None, filename="kedi.png", content_type="image/png", folder_id=None):
    form = {"folder_id": folder_id} if folder_id is not None else None
    return c.post("/api/import",
                  files={"file": (filename, _png() if data is None else data, content_type)},
                  data=form)


# ── nereye düşüyor ──────────────────────────────────────────────────────
def test_import_lands_in_the_root_when_no_folder_given(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = _import(c)
    assert r.status_code == 200, r.text
    rec = r.json()["image"]
    assert rec["folder_id"] is None
    assert [h["id"] for h in c.get("/api/history").json()["images"]] == [rec["id"]]


def test_import_files_the_image_into_the_named_folder(tmp_path, monkeypatch):
    """Klasör sayacı AYRI bir yoldan hesaplanıyor (list_folders_route), o yüzden
    hem geçmiş hem sayaç ölçülür: biri tutup diğeri tutmayabilir."""
    c = _client(tmp_path, monkeypatch)
    fid = _new_folder(c, "Afiş")
    rec = _import(c, folder_id=fid).json()["image"]
    assert rec["folder_id"] == fid

    filed = c.get(f"/api/history?folder_id={fid}").json()["images"]
    assert [h["id"] for h in filed] == [rec["id"]]
    # kökte görünmemeli: klasöre girdi
    assert c.get("/api/history").json()["images"] == []
    assert c.get("/api/folders").json()["items"][0]["count"] == 1


def test_import_with_unknown_folder_404(tmp_path, monkeypatch):
    """Var olmayan klasöre aktarma kökte birikmemeli — sessiz yanlış yerleşim.

    Mesaj da ölçülüyor: rota HİÇ yokken FastAPI de 404 döndürüyor, yalnız
    duruma bakan bir iddia rota silinse bile yeşil kalırdı.
    """
    c = _client(tmp_path, monkeypatch)
    r = _import(c, folder_id="yokboyleklasor")
    assert r.status_code == 404
    assert r.json()["detail"] == "Klasör bulunamadı."
    assert c.get("/api/history").json()["images"] == []


# ── dosyanın kendisi ────────────────────────────────────────────────────
def test_import_reencodes_a_jpeg_as_png(tmp_path, monkeypatch):
    """PNG'ye kodlama pazarlık konusu DEĞİL: `/output/{filename}`, silme ve
    `_output_png_path` hepsi dosyanın `{id}.png` olduğunu varsayıyor. JPEG
    olduğu gibi kaydedilirse kayıt görünür ama görsel açılmaz."""
    c = _client(tmp_path, monkeypatch)
    rec = _import(c, data=_jpeg(), filename="foto.jpg",
                  content_type="image/jpeg").json()["image"]
    assert rec["filename"].endswith(".png")
    served = c.get(f"/output/{rec['filename']}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content.startswith(PNG_MAGIC)


def test_import_rejects_a_non_image_file(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = _import(c, data=b"bu bir metin dosyasi", filename="notlar.txt",
                content_type="text/plain")
    assert r.status_code == 422
    assert c.get("/api/history").json()["images"] == []


def test_import_rejects_an_oversized_file(tmp_path, monkeypatch):
    """10 MB sınırı `_read_upload_png` ile paylaşılıyor (tek çoban)."""
    c = _client(tmp_path, monkeypatch)
    big = b"\x00" * (10 * 1024 * 1024 + 1)
    r = _import(c, data=big, filename="buyuk.png")
    assert r.status_code == 413


def test_import_records_the_real_pixel_dimensions(tmp_path, monkeypatch):
    """`size` üretimde Azure'ın boyut dizesi; içe aktarmada uydurulacak bir
    değer yok, gerçek çözünürlük yazılır (history.json adli kayıt)."""
    c = _client(tmp_path, monkeypatch)
    rec = _import(c, data=_png(size=(48, 24))).json()["image"]
    assert rec["size"] == "48x24"
    assert rec["quality"] == ""


# ── etiket ve kayıt biçimi ──────────────────────────────────────────────
def test_import_label_is_the_bare_filename(tmp_path, monkeypatch):
    """Dosya adı yalnızca ETİKET; dosya adı olarak kullanılmıyor (uuid üretiliyor).
    Yine de basename'e indirilir: galeri başlığında yol parçaları görünmesin."""
    c = _client(tmp_path, monkeypatch)
    rec = _import(c, filename="../../gizli/kedi.png").json()["image"]
    assert rec["prompt"] == "kedi.png"


def test_import_truncates_a_very_long_filename(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rec = _import(c, filename="a" * 300 + ".png").json()["image"]
    assert len(rec["prompt"]) == 120


def test_import_falls_back_to_a_label_when_the_filename_is_empty(tmp_path, monkeypatch):
    """Adsız parça gelirse kart başlıksız kalmasın (galeri `rec.prompt` gösteriyor)."""
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/import", files={"file": (".", _png(), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["image"]["prompt"].strip() != ""


def test_imported_record_has_no_parent_and_no_palette(tmp_path, monkeypatch):
    """Türev zinciri ve palet şeridi uydurma veri görmemeli: içe aktarılanın
    ne ebeveyni ne paleti var."""
    c = _client(tmp_path, monkeypatch)
    rec = _import(c).json()["image"]
    assert rec["parent_id"] is None
    assert rec["palette"] is None
    assert rec["prompt_sent"] is None


def test_import_marks_the_record_as_imported(tmp_path, monkeypatch):
    """Galeri işareti buna bakıyor; düşerse içe aktarılan üretilmiş gibi görünür."""
    c = _client(tmp_path, monkeypatch)
    assert _import(c).json()["image"]["imported"] is True


def test_two_imports_both_survive_in_history(tmp_path, monkeypatch):
    """history.json her kayıtta baştan yazılıyor. Arayüz dosyaları SIRAYLA
    gönderiyor; sunucu tarafında da iki ardışık aktarmanın ikisi de kalmalı."""
    c = _client(tmp_path, monkeypatch)
    first = _import(c, filename="bir.png").json()["image"]["id"]
    second = _import(c, filename="iki.png").json()["image"]["id"]
    ids = {h["id"] for h in c.get("/api/history").json()["images"]}
    assert ids == {first, second}


def test_ice_aktarilan_gorsel_bir_MODEL_iddia_ETMIYOR(tmp_path, monkeypatch):
    """İçe aktarım bir üretim değil: görsel başka bir araçta yapıldı.

    `credits: 0` ("bedeli yok") ile aynı duruş — alan var, değeri boş. Önce
    varsayılan model yazılıyordu, yani kullanıcının Photoshop'tan attığı bir
    PNG geçmişte "azure-gpt-image-2 üretti" diye duruyordu.
    """
    r = _import(_client(tmp_path, monkeypatch))

    assert r.status_code == 200, r.text
    kayit = r.json()["image"]
    assert kayit["imported"] is True
    assert kayit["model"] == "", "içe aktarılan görsele üretici modeli yazıldı"
    assert kayit["credits"] == 0
