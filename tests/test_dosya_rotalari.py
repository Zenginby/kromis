"""Rotalar nesne depolamada — 302 ön imzalı URL, kovaya yazım, kovadan okuma (Faz 2 / 2, K7).

Sahte S3 (`tests/sahte_s3.py`, imza DOĞRULAYAN) `app.state.dosya`ya
`NesneDepo` olarak takılır; rota testleri `dizinler(...)` deyimiyle aynı,
tek farkla: kullanıcı dizinleri `data_dir` ALTINDA (`kullanicilar/<uuid>/…`),
çünkü kovadaki anahtar o yolun köke göreli hâli. Her iddia rotanın HTTP
yüzünü ölçer — hangi anahtar yazıldı, 302 nereye gitti, ZIP'te ne var.
Yerel dal (`FileResponse` 200) mevcut 170+ rota testinde aynen duruyor;
buradaki son test iki dalı yan yana koyuyor.
"""
from __future__ import annotations

import io
import os
import uuid
import zipfile
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event
from sqlalchemy.orm import Session

import app as appmod
import azure_client as ac
from services import depo_medya, dosya, hesap, nesne_depo, tablolar
from tests.sahte_s3 import SahteS3

pytestmark = pytest.mark.usefixtures("depo_db")

KIMLIK = nesne_depo.Kimlik("AKID", "GIZLI", "auto")
UC = "https://hesap.r2.example"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png(size=(16, 16), color=(200, 60, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color + (255,)).save(buf, format="PNG")
    return buf.getvalue()


class Kova:
    def __init__(self, tmp_path, kullanici_id: uuid.UUID) -> None:
        self.kok = str(tmp_path)
        self.sahte = SahteS3("kova", KIMLIK)
        self.istemci = nesne_depo.S3Istemci(UC, "kova", KIMLIK, istemci=self.sahte.istemci())
        self.depo = dosya.NesneDepo(self.istemci, self.kok)
        self.onek = f"kullanicilar/{kullanici_id}"

    def anahtarlar(self) -> list[str]:
        return sorted(self.sahte.nesneler)

    def takip(self, cevap) -> httpx.Response:
        """302'nin `Location`ını kovaya (sahte S3) sor — tarayıcının `<img>` için yaptığı."""
        assert cevap.status_code == 302, cevap.text
        return self.sahte.istemci().get(cevap.headers["location"])


@pytest.fixture
def kova(tmp_path, monkeypatch, dizinler, kullanici) -> Kova:
    k = Kova(tmp_path, kullanici.id)
    # `ayar.ayarlar` testte paylaşılan nesneyi veriyor (conftest `kullanici`); kullanıcı
    # dizinleri burada ELLE `data_dir` altına konur ki kovadaki anahtar üretimdekiyle aynı olsun.
    dizinler(data_dir=k.kok, output_dir=os.path.join(k.kok, "kullanicilar", str(kullanici.id), "output"),
             assets_dir=os.path.join(k.kok, "kullanicilar", str(kullanici.id), "assets"))
    monkeypatch.setattr(appmod.app.state, "dosya", k.depo)
    monkeypatch.setattr(ac, "generate", lambda *a, **k_: [_png()])
    return k


@pytest.fixture
def c(kova) -> TestClient:
    return TestClient(appmod.app)


def _uret(uret_ve_bitir, c: TestClient) -> dict:
    r = uret_ve_bitir(c, "/api/generate", json={"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1})
    assert r.status_code == 200, r.text
    return r.json()["images"][0]


# ── yazım ─────────────────────────────────────────────────────────────

def test_generate_writes_the_object_under_the_users_key_and_nothing_to_disk(c, kova, tmp_path, uret_ve_bitir):
    kayit = _uret(uret_ve_bitir, c)
    assert kova.anahtarlar() == [f"{kova.onek}/output/{kayit['filename']}"]
    veri, mime = kova.sahte.nesneler[kova.anahtarlar()[0]]
    assert veri.startswith(PNG_MAGIC) and mime == "image/png"
    assert not (tmp_path / "kullanicilar").exists() or not any(
        p.is_file() for p in (tmp_path / "kullanicilar").rglob("*")), "kovalı kipte diske dosya düşmez"


def test_the_object_is_put_before_the_row_is_flushed(c, kova, db_oturumu, uret_ve_bitir):
    """Belge §2: nesne → satır → flush. Satır düşerse nesne artık kalır (artik_dosya bulur);
    tersi galeride kırık bir kutu olurdu ve kimse aramıyor."""
    sira: list[str] = []
    asil = kova.depo.yaz

    def _yaz(*a, **k):
        sira.append("nesne")
        return asil(*a, **k)

    def _flush(session, ctx, instances):
        if any(isinstance(o, tablolar.Medya) for o in session.new):
            sira.append("satir")

    kova.depo.yaz = _yaz
    event.listen(Session, "before_flush", _flush)
    try:
        _uret(uret_ve_bitir, c)
    finally:
        event.remove(Session, "before_flush", _flush)
    assert sira == ["nesne", "satir"]


def test_import_and_asset_upload_write_to_the_bucket(c, kova, kullanici):
    r = c.post("/api/import", files={"file": ("foto.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    ice = r.json()["image"]["filename"]
    r = c.post("/api/assets/logos", files={"file": ("logo.png", _png((8, 8)), "image/png")})
    assert r.status_code == 200, r.text
    logo = r.json()["asset"]["filename"]
    assert kova.anahtarlar() == sorted([f"{kova.onek}/output/{ice}", f"{kova.onek}/assets/logos/{logo}"])


# ── servis: 302 ─────────────────────────────────────────────────────

def test_output_redirects_to_a_presigned_url_that_serves_the_bytes(c, kova, uret_ve_bitir):
    kayit = _uret(uret_ve_bitir, c)
    r = c.get(f"/output/{kayit['filename']}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["cache-control"] == "private, max-age=600"
    konum = urlsplit(r.headers["location"])
    assert f"{konum.scheme}://{konum.netloc}" == UC
    assert konum.path == f"/kova/{kova.onek}/output/{kayit['filename']}"
    sorgu = {k: v[0] for k, v in parse_qs(konum.query).items()}
    assert sorgu["X-Amz-Expires"] == str(dosya.URL_SURESI) and "X-Amz-Signature" in sorgu
    assert "response-content-disposition" not in sorgu, "çizim adresi attachment DEMEZ"
    hedef = kova.takip(r)
    assert hedef.status_code == 200 and hedef.content.startswith(PNG_MAGIC)
    assert hedef.headers["content-type"] == "image/png"


def test_a_range_request_on_the_presigned_url_reaches_the_bucket_directly(c, kova, uret_ve_bitir):
    """`<video>` ileri sarma: aralık isteği 302'nin hedefine gider, uygulama bayt taşımaz."""
    kayit = _uret(uret_ve_bitir, c)
    r = c.get(f"/output/{kayit['filename']}", follow_redirects=False)
    parca = kova.sahte.istemci().get(r.headers["location"], headers={"Range": "bytes=0-7"})
    assert parca.status_code == 206 and parca.content == PNG_MAGIC
    assert parca.headers["content-range"].startswith("bytes 0-7/")


def test_download_redirects_with_the_filename_as_an_attachment(c, kova, uret_ve_bitir):
    kayit = _uret(uret_ve_bitir, c)
    r = c.get(f"/api/output/{kayit['id']}/download", follow_redirects=False)
    assert r.status_code == 302 and r.headers["cache-control"] == "private, max-age=600"
    sorgu = {k: v[0] for k, v in parse_qs(urlsplit(r.headers["location"]).query).items()}
    assert sorgu["response-content-disposition"] == \
        f"attachment; filename=\"{kayit['filename']}\"; filename*=UTF-8''{kayit['filename']}"
    hedef = kova.takip(r)
    assert hedef.status_code == 200 and hedef.headers["content-disposition"].startswith("attachment;")


def test_asset_serving_redirects_too(c, kova):
    r = c.post("/api/assets/banners", files={"file": ("b.png", _png((40, 8)), "image/png")})
    ad = r.json()["asset"]["filename"]
    r = c.get(f"/assets/banners/{ad}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["cache-control"] == "private, max-age=600"
    assert urlsplit(r.headers["location"]).path == f"/kova/{kova.onek}/assets/banners/{ad}"
    assert kova.takip(r).status_code == 200
    assert c.get("/assets/banners/deadbeef0000.png").status_code == 404


def test_ownership_is_still_the_row_and_a_missing_object_is_404_not_a_broken_redirect(c, kova, db_oturumu, kullanici, uret_ve_bitir):
    kayit = _uret(uret_ve_bitir, c)
    # Başkasının satırı: B'nin dosyası kovada dursa da bu kullanıcıya 404 (id uzayı sızmaz).
    b = tablolar.Kullanici(eposta=f"b-{uuid.uuid4().hex[:8]}@example.com", parola_ozeti=None,
                           dogrulandi_at=hesap.simdi())
    db_oturumu.add(b)
    db_oturumu.flush()
    b_kayit = depo_medya.kaydet(db_oturumu, b.id, _png(), {"prompt": "b"},
                                os.path.join(kova.kok, "kullanicilar", str(b.id), "output"), depo=kova.depo)
    db_oturumu.commit()
    assert f"kullanicilar/{b.id}/output/{b_kayit['filename']}" in kova.anahtarlar()
    assert c.get(f"/output/{b_kayit['filename']}").status_code == 404
    assert c.get(f"/api/output/{b_kayit['id']}/download").status_code == 404
    # Satırı var, nesnesi yok: 404 (satır VE nesne — Faz 1 / 5 sözleşmesi kovada da).
    del kova.sahte.nesneler[f"{kova.onek}/output/{kayit['filename']}"]
    assert c.get(f"/output/{kayit['filename']}", follow_redirects=False).status_code == 404
    assert c.get(f"/api/output/{kayit['id']}/download", follow_redirects=False).status_code == 404
    assert c.get("/output/yok.png").status_code == 404 and c.get("/output/..%2Fx").status_code == 404


# ── okuyanlar: bindirme, düzenleme, ZIP, silme ───────────────────────

def test_logo_overlay_reads_source_and_asset_from_the_bucket_and_writes_the_result_back(c, kova, monkeypatch, uret_ve_bitir):
    kaynak = _uret(uret_ve_bitir, c)
    logo = c.post("/api/assets/logos", files={"file": ("l.png", _png((8, 8), (0, 0, 255)), "image/png")}).json()["asset"]
    gorulen: list[bytes] = []

    def _fake(base_path, *, logo_path, **kw):
        gorulen.append(base_path.read()[:8])
        gorulen.append(logo_path.read()[:8])
        return _png((4, 4))
    monkeypatch.setattr(appmod.composite, "composite_logo", _fake)
    r = c.post("/api/logo", json={"id": kaynak["id"], "asset_id": logo["id"]})
    assert r.status_code == 200, r.text
    assert gorulen == [PNG_MAGIC, PNG_MAGIC], "kaynak ve logo kovadan bayt olarak okundu"
    turev = r.json()["image"]
    assert f"{kova.onek}/output/{turev['filename']}" in kova.anahtarlar()
    assert turev["parent_id"] == kaynak["id"]
    # Önizleme diske/kovaya yazmaz.
    once = kova.anahtarlar()
    assert c.post("/api/logo/preview", json={"id": kaynak["id"], "asset_id": logo["id"]}).status_code == 200
    assert kova.anahtarlar() == once
    # Banner gerçek Pillow ile: kovadan okunan gerçek PNG'ler bindirilebiliyor.
    afis = c.post("/api/assets/banners", files={"file": ("b.png", _png((40, 8)), "image/png")}).json()["asset"]
    r = c.post("/api/banner", json={"id": kaynak["id"], "asset_id": afis["id"]})
    assert r.status_code == 200, r.text
    assert kova.sahte.nesneler[f"{kova.onek}/output/{r.json()['image']['filename']}"][0].startswith(PNG_MAGIC)


def test_edit_reads_the_reference_from_the_bucket(c, kova, monkeypatch, uret_ve_bitir):
    kaynak = _uret(uret_ve_bitir, c)
    alinan: list[list[str]] = []

    def _edit(model, prompt, refs, size, quality, n):
        alinan.append([ad for ad, _ in refs])
        assert all(veri.startswith(PNG_MAGIC) for _, veri in refs)
        return [_png((4, 4))]
    monkeypatch.setattr(appmod.providers, "edit", _edit)
    r = uret_ve_bitir(c, "/api/edit", data={"prompt": "mavi yap", "size": "1024x1024", "quality": "medium", "n": 1,
                                  "source_id": kaynak["id"]})
    assert r.status_code == 200, r.text
    assert alinan == [[f"{kaynak['id']}.png"]]
    assert r.json()["images"][0]["parent_id"] == kaynak["id"]
    # Kovada olmayan referans 404 (HEAD): sessiz bir boş referans değil.
    r = uret_ve_bitir(c, "/api/edit", data={"prompt": "x", "size": "1024x1024", "quality": "medium", "n": 1,
                                  "source_id": "deadbeef0000"})
    assert r.status_code == 404


def test_folder_zip_streams_the_files_out_of_the_bucket(c, kova, uret_ve_bitir):
    klasor = c.post("/api/folders", json={"name": "Tatil"}).json()["folder"]
    kayit = _uret(uret_ve_bitir, c)
    assert c.patch(f"/api/image/{kayit['id']}", json={"folder_id": klasor["id"]}).status_code == 200
    r = c.get(f"/api/folders/{klasor['id']}/download")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="Tatil.zip"' in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert zf.testzip() is None
        assert f"Tatil/{kayit['filename']}" in zf.namelist()
        assert zf.read(f"Tatil/{kayit['filename']}").startswith(PNG_MAGIC)
    # Kovadan silinen dosya ZIP'te yok, arşiv yine geçerli (eski `os.path.exists` kararı).
    del kova.sahte.nesneler[f"{kova.onek}/output/{kayit['filename']}"]
    r = c.get(f"/api/folders/{klasor['id']}/download")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert kayit["filename"] not in " ".join(zf.namelist()) and zf.testzip() is None


def test_delete_removes_the_object_and_the_bulk_variant_too(c, kova, uret_ve_bitir):
    a, b = _uret(uret_ve_bitir, c), _uret(uret_ve_bitir, c)
    assert len(kova.anahtarlar()) == 2
    assert c.delete(f"/api/image/{a['id']}").status_code == 200
    assert kova.anahtarlar() == [f"{kova.onek}/output/{b['filename']}"]
    assert c.request("DELETE", "/api/images", json={"ids": [b["id"]]}).status_code == 200
    assert kova.anahtarlar() == []
    assert c.get("/api/history").json()["images"] == []
    logo = c.post("/api/assets/logos", files={"file": ("l.png", _png((8, 8)), "image/png")}).json()["asset"]
    assert c.delete(f"/api/assets/logos/{logo['id']}").status_code == 200
    assert kova.anahtarlar() == []


# ── karşıt: yerel dal aynı rotada 200 `FileResponse` ────────────────

def test_the_same_route_serves_a_file_response_on_the_local_disk(tmp_path, monkeypatch, dizinler, uret_ve_bitir):
    dizinler(output_dir=str(tmp_path))
    assert isinstance(appmod.app.state.dosya, dosya.YerelDepo)
    monkeypatch.setattr(ac, "generate", lambda *a, **k: [_png()])
    c = TestClient(appmod.app)
    kayit = _uret(uret_ve_bitir, c)
    assert (tmp_path / kayit["filename"]).exists()
    r = c.get(f"/output/{kayit['filename']}", follow_redirects=False)
    assert r.status_code == 200 and r.content.startswith(PNG_MAGIC) and "location" not in r.headers
    r = c.get(f"/api/output/{kayit['id']}/download", follow_redirects=False)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
