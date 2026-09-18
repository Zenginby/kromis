"""`tools/medya_tasi.py` — yerel medya → kova, aynı anahtarla; idempotent, yereli silmez (Faz 2 / 2).

Sahte S3 imza doğruluyor; DB gerekmez (araç satırlara bakmaz: kesme anında
dosya ne varsa o taşınır, satırlarla eşleşme `artik_dosya`nın işi).
"""
from __future__ import annotations

import os
import uuid

import pytest

from services import dosya, nesne_depo
from tests.sahte_s3 import SahteS3
from tools import medya_tasi

KIMLIK = nesne_depo.Kimlik("AKID", "GIZLI", "auto")
PNG = b"\x89PNG\r\n\x1a\n-tasi-"


class Kurgu:
    def __init__(self, kaynak: str) -> None:
        self.kaynak = kaynak
        self.sahte = SahteS3("kova", KIMLIK)
        self.istemci = nesne_depo.S3Istemci("https://hesap.r2.example", "kova", KIMLIK,
                                            istemci=self.sahte.istemci())
        self.a, self.b = uuid.uuid4(), uuid.uuid4()
        self.medya: dict[str, bytes] = {}      # anahtar → bayt
        self.medya_degil: list[str] = []

    def _yaz(self, goreli: str, govde: bytes, medya: bool = True) -> None:
        yol = os.path.join(self.kaynak, *goreli.split("/"))
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "wb") as f:
            f.write(govde)
        (self.medya.__setitem__(goreli, govde) if medya else self.medya_degil.append(goreli))


@pytest.fixture
def kurgu(tmp_path) -> Kurgu:
    k = Kurgu(str(tmp_path / "veri"))
    k._yaz(f"kullanicilar/{k.a}/output/{'a' * 32}.png", PNG + b"1")
    k._yaz(f"kullanicilar/{k.a}/output/{'b' * 32}.mp4", b"\x00mp4" * 100)
    k._yaz(f"kullanicilar/{k.a}/assets/logos/{'c' * 32}.png", PNG + b"L")
    k._yaz(f"kullanicilar/{k.a}/assets/banners/{'d' * 32}.png", PNG + b"B")
    k._yaz(f"kullanicilar/{k.a}/output/guncelleme.json", b"{}", medya=False)
    k._yaz(f"kullanicilar/{k.a}/output/.DS_Store", b"\x00", medya=False)
    k._yaz(f"kullanicilar/{k.b}/output/{'e' * 32}.png", PNG + b"2")
    os.makedirs(os.path.join(k.kaynak, "kullanicilar", "eski-yedek", "output"))
    os.makedirs(os.path.join(k.kaynak, "output"))          # tek kullanıcılı eski kök: dokunulmaz
    with open(os.path.join(k.kaynak, "output", "kok.png"), "wb") as f:
        f.write(PNG)
    return k


def test_the_dry_run_counts_what_would_be_uploaded_and_uploads_nothing(kurgu):
    rapor = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak, kuru=True)
    assert rapor.kuru and rapor.yuklenen == 5 and not rapor.basarisiz
    assert kurgu.sahte.nesneler == {}
    assert all(i.yontem == "HEAD" for i in kurgu.sahte.istekler), "kuru koşu yalnız HEAD sorar"
    a = next(k for k in rapor.kullanicilar if k.kullanici_id == kurgu.a)
    assert (a.dosya, a.medya_degil, a.zaten_var, a.yuklenen) == (6, 2, 0, 4)
    assert a.bayt == sum(len(v) for k, v in kurgu.medya.items() if str(kurgu.a) in k)
    assert rapor.atlanan_dizinler == ["eski-yedek"]


def test_the_real_run_uploads_under_the_same_keys_with_the_right_mime_and_is_idempotent(kurgu):
    rapor = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak)
    assert rapor.yuklenen == 5 and not rapor.basarisiz
    assert {k: v[0] for k, v in kurgu.sahte.nesneler.items()} == kurgu.medya
    assert kurgu.sahte.nesneler[f"kullanicilar/{kurgu.a}/output/{'b' * 32}.mp4"][1] == "video/mp4"
    assert kurgu.sahte.nesneler[f"kullanicilar/{kurgu.a}/assets/logos/{'c' * 32}.png"][1] == "image/png"
    # Yerel dosyalara dokunulmadı; `output/kok.png` (kullanıcı dışı) hiç bakılmadı.
    for goreli in list(kurgu.medya) + kurgu.medya_degil:
        assert os.path.exists(os.path.join(kurgu.kaynak, *goreli.split("/")))
    assert "output/kok.png" not in kurgu.sahte.nesneler

    kurgu.sahte.istekler.clear()
    ikinci = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak)
    assert ikinci.yuklenen == 0 and sum(k.zaten_var for k in ikinci.kullanicilar) == 5
    assert all(i.yontem == "HEAD" for i in kurgu.sahte.istekler), "ikinci koşu hiç PUT atmaz"

    ucuncu = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak, yeniden=True)
    assert ucuncu.yuklenen == 5, "--yeniden aynı boyuttakini de yükler"


def test_a_changed_local_file_is_uploaded_again_because_the_size_differs(kurgu):
    medya_tasi.tasi(kurgu.istemci, kurgu.kaynak)
    anahtar = f"kullanicilar/{kurgu.a}/output/{'a' * 32}.png"
    kurgu.sahte.nesneler[anahtar] = (b"yarim", "image/png")     # kesik bir PUT kalıntısı gibi
    rapor = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak)
    assert rapor.yuklenen == 1 and kurgu.sahte.nesneler[anahtar][0] == PNG + b"1"


def test_a_failed_verification_is_reported_and_not_counted_as_uploaded(kurgu, monkeypatch):
    asil = kurgu.istemci.bas

    def _bas(anahtar):
        n = asil(anahtar)
        return nesne_depo.Nesne(anahtar, n.boyut + 1) if n is not None and anahtar.endswith(".mp4") else n
    monkeypatch.setattr(kurgu.istemci, "bas", _bas)
    rapor = medya_tasi.tasi(kurgu.istemci, kurgu.kaynak)
    assert rapor.yuklenen == 4 and len(rapor.basarisiz) == 1 and "dogrulanamadi" in rapor.basarisiz[0]


# ── main: çıkış kodları ──────────────────────────────────────────────

def _ortam(monkeypatch, **degerler):
    for ad in dosya.ZORUNLU_ENV:
        monkeypatch.delenv(ad, raising=False)
    for ad, deger in degerler.items():
        monkeypatch.setenv(ad, deger)


def test_main_refuses_without_object_storage_or_without_a_source(kurgu, monkeypatch, capsys, tmp_path):
    _ortam(monkeypatch)
    assert medya_tasi.main(["--kaynak", kurgu.kaynak]) == medya_tasi.CIKIS_ORTAM
    assert "KROMIS_NESNE_DEPO_URL" in capsys.readouterr().err
    _ortam(monkeypatch, KROMIS_NESNE_DEPO_URL="https://x.example", KROMIS_NESNE_DEPO_KOVA="k")
    assert medya_tasi.main(["--kaynak", kurgu.kaynak]) == medya_tasi.CIKIS_ORTAM
    assert "eksik" in capsys.readouterr().err
    assert medya_tasi.main(["--kaynak", str(tmp_path / "yok")]) == medya_tasi.CIKIS_KULLANICI


def test_main_exit_codes_follow_the_work_left(kurgu, monkeypatch, capsys):
    monkeypatch.setattr(dosya, "depo_kur", lambda kok, **k: dosya.NesneDepo(kurgu.istemci, kok))
    assert medya_tasi.main(["--kaynak", kurgu.kaynak, "--kuru"]) == medya_tasi.CIKIS_KALDI
    out = capsys.readouterr().out
    assert "KURU KOSU" in out and "5 yuklenecek" in out and "DOKUNULMADI" in out
    assert kurgu.sahte.nesneler == {}
    assert medya_tasi.main(["--kaynak", kurgu.kaynak]) == medya_tasi.CIKIS_TAMAM
    out = capsys.readouterr().out
    assert "5 yuklendi" in out and "atlandi (UUID degil): kullanicilar/eski-yedek" in out
    assert f"{kurgu.a}: 6 dosya, 0 zaten kovada, 4 yuklendi" in out
    assert medya_tasi.main(["--kaynak", kurgu.kaynak, "--kuru"]) == medya_tasi.CIKIS_TAMAM, "her şey kovada"
    assert "0 yuklenecek" in capsys.readouterr().out


def test_a_bucket_error_is_an_environment_exit_and_never_prints_the_secret(kurgu, monkeypatch, capsys):
    kirik = nesne_depo.S3Istemci("https://hesap.r2.example", "kova",
                                 nesne_depo.Kimlik("AKID", "COK_GIZLI", "auto"), istemci=kurgu.sahte.istemci())
    monkeypatch.setattr(dosya, "depo_kur", lambda kok, **k: dosya.NesneDepo(kirik, kok))
    assert medya_tasi.main(["--kaynak", kurgu.kaynak]) == medya_tasi.CIKIS_ORTAM
    err = capsys.readouterr().err
    assert "403" in err and "COK_GIZLI" not in err
