"""`tools/artik_dosya.py` — DB'de satırı olmayan medya/varlık dosyaları (Faz 1 / 9).

GERÇEK Postgres (`depo_db`): satırlar `depo_medya.kaydet`/`depo_varlik.kaydet`
ile (dosya + satır, üretimin yolu), artık dosyalar elle diske. Araç kendi
motorunu `DATABASE_URL`den kurar; tohum bu yüzden `commit` ediliyor.

Kurgu, aracın bulmak zorunda olduğu üç durum: (a) satırsız kalmış medya dosyası
(commit düşmüş yazım), (b) hesabı silinmiş kullanıcının dizini (CASCADE satırı
sildi, dosyayı değil), (c) `assets/` altında bilinmeyen bir tür dizini. Bir de
DOKUNMAMASI gerekenler: satırı olan dosyalar, medya olmayan dosyalar
(`guncelleme.json`), UUID olmayan dizinler.
"""
from __future__ import annotations

import io
import os
import sys
import uuid

import pytest
from sqlalchemy import func, select

from services import ayar, db, depo_medya, depo_varlik, hesap
from services.tablolar import Medya, Varlik
from tools import artik_dosya

pytestmark = pytest.mark.usefixtures("depo_db")

PNG = b"\x89PNG\r\n\x1a\n-artik-"


class Kurgu:
    def __init__(self, veri_koku: str, kullanici_id: uuid.UUID, oturum):
        self.veri_koku = veri_koku
        self.kullanici_id = kullanici_id
        self.oturum = oturum
        self.genel = ayar.Ayarlar(data_dir=veri_koku, output_dir=os.path.join(veri_koku, "output"),
                                  assets_dir=os.path.join(veri_koku, "assets"), static_dir="static")
        self.ozel = self.genel.kullanici_icin(kullanici_id)
        self.satirli: list[str] = []
        self.artik: list[str] = []
        self.medya_degil: list[str] = []

    def _yaz(self, yol: str, liste: list[str], govde: bytes = PNG) -> str:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "wb") as f:
            f.write(govde)
        liste.append(yol)
        return yol


@pytest.fixture
def kurgu(tmp_path, db_oturumu, kullanici) -> Kurgu:
    """Bir kullanıcı: 2 satırlı medya + 1 satırlı varlık, 3 artık medya, 2 medya olmayan dosya;
    bir de hesabı olmayan dizin ve UUID olmayan dizin."""
    k = Kurgu(str(tmp_path / "veri"), kullanici.id, db_oturumu)
    out, assets = k.ozel.output_dir, k.ozel.assets_dir
    os.makedirs(out)
    # Satırlı: üretimin yolu (dosya + satır birlikte).
    for kayit in (depo_medya.kaydet(db_oturumu, k.kullanici_id, PNG + b"1", {"prompt": "a"}, out),
                  depo_medya.kaydet(db_oturumu, k.kullanici_id, b"\x00mp4", {"prompt": "v", "kind": "video"}, out)):
        k.satirli.append(os.path.join(out, kayit["filename"]))
    v = depo_varlik.kaydet(db_oturumu, k.kullanici_id, "logos", PNG + b"L", "Logo", assets)
    k.satirli.append(os.path.join(assets, "logos", v["filename"]))
    db_oturumu.commit()
    # Artık: satırı olmayan medya dosyaları — commit düşmüş yazımın bıraktığı.
    k._yaz(os.path.join(out, "deadbeef0001deadbeef0001deadbeef.png"), k.artik)
    k._yaz(os.path.join(out, "deadbeef0002.mp4"), k.artik)
    k._yaz(os.path.join(assets, "logos", "deadbeef0003.png"), k.artik)
    k._yaz(os.path.join(assets, "uploads", "eski.png"), k.artik)          # bilinmeyen tür dizini
    # Medya değil: dokunulmaz.
    k._yaz(os.path.join(out, "guncelleme.json"), k.medya_degil, b'{"zaman": 0}')
    k._yaz(os.path.join(out, ".DS_Store"), k.medya_degil, b"\x00")
    # Hesabı olmayan dizin: her medya dosyası artık.
    yok = os.path.join(k.veri_koku, ayar.KULLANICILAR_DIZINI, str(uuid.uuid4()), "output")
    k._yaz(os.path.join(yok, "hayalet.png"), k.artik)
    # UUID olmayan dizin: atlanır, bildirilir.
    os.makedirs(os.path.join(k.veri_koku, ayar.KULLANICILAR_DIZINI, "eski-yedek"))
    return k


def _sayilar(oturum, kullanici_id) -> tuple[int, int]:
    m = oturum.scalar(select(func.count()).select_from(Medya).where(Medya.kullanici_id == kullanici_id))
    v = oturum.scalar(select(func.count()).select_from(Varlik).where(Varlik.kullanici_id == kullanici_id))
    return int(m or 0), int(v or 0)


def _kos(kurgu: Kurgu, *ek: str) -> int:
    return artik_dosya.main(["--veri-dizini", kurgu.veri_koku, *ek])


def test_the_dry_run_lists_exactly_the_stray_files_and_touches_nothing(kurgu, capsys):
    """ASIL İDDİA: yalnız satırsız medya dosyaları listede; diskte ve DB'de hiçbir şey değişmiyor;
    çıkış 3 (artık var) — cron 'temiz mi' sorusunu koddan okur."""
    once = _sayilar(kurgu.oturum, kurgu.kullanici_id)
    assert _kos(kurgu) == artik_dosya.CIKIS_ARTIK_VAR
    out = capsys.readouterr().out
    listelenen = {os.path.join(kurgu.veri_koku, s.split("artik: ", 1)[1].strip())
                  for s in out.splitlines() if "artik: " in s}
    assert listelenen == set(kurgu.artik)
    assert all(os.path.exists(y) for y in kurgu.satirli + kurgu.artik + kurgu.medya_degil)
    assert _sayilar(kurgu.oturum, kurgu.kullanici_id) == once
    assert "hicbir sey silinmedi" in out
    # Özet satırları: kullanıcı başına, hesabı olmayan dizin işaretli, UUID olmayan atlandı.
    assert f"{kurgu.kullanici_id}: 9 dosya, 4 artik" in out and "2 medya degil" in out
    assert "HESABI YOK" in out
    assert "atlandi (UUID degil): kullanicilar/eski-yedek" in out
    assert "toplam: 2 kullanici, 5 artik dosya" in out


def test_sil_without_a_tty_and_without_evet_refuses_and_deletes_nothing(kurgu, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))          # TTY değil
    assert _kos(kurgu, "--sil") == artik_dosya.CIKIS_KULLANICI
    assert "--evet" in capsys.readouterr().err
    assert all(os.path.exists(y) for y in kurgu.artik)


def test_sil_with_evet_removes_only_the_strays_and_the_second_run_finds_nothing(kurgu, capsys):
    once = _sayilar(kurgu.oturum, kurgu.kullanici_id)
    assert _kos(kurgu, "--sil", "--evet") == artik_dosya.CIKIS_TAMAM
    assert "silindi: 5" in capsys.readouterr().out
    assert not any(os.path.exists(y) for y in kurgu.artik)
    assert all(os.path.exists(y) for y in kurgu.satirli), "satırı olan dosyaya dokunuldu"
    assert all(os.path.exists(y) for y in kurgu.medya_degil), "medya olmayan dosya silindi"
    assert _sayilar(kurgu.oturum, kurgu.kullanici_id) == once, "araç DB'ye yazmaz"
    # Satırlı dosyalar hâlâ satırdan bulunuyor — depo sözleşmesi bozulmadı.
    for satir in kurgu.oturum.scalars(select(Medya).where(Medya.kullanici_id == kurgu.kullanici_id)):
        assert depo_medya.dosya_yolu(kurgu.oturum, kurgu.kullanici_id, satir.id, kurgu.ozel.output_dir)

    assert _kos(kurgu) == artik_dosya.CIKIS_TAMAM
    assert "0 artik dosya" in capsys.readouterr().out


def test_a_tty_confirmation_is_honoured_both_ways(kurgu, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _soru: "h")
    assert _kos(kurgu, "--sil") == artik_dosya.CIKIS_KULLANICI
    assert all(os.path.exists(y) for y in kurgu.artik)

    monkeypatch.setattr("builtins.input", lambda _soru: "E")
    assert _kos(kurgu, "--sil") == artik_dosya.CIKIS_TAMAM
    assert not any(os.path.exists(y) for y in kurgu.artik)


def test_a_second_user_with_only_rows_is_reported_clean(kurgu, db_oturumu, capsys):
    """İzolasyon: B'nin satırlı dosyaları A'nın taramasında artık sanılmıyor ve tersi."""
    b = hesap.kullanici_olustur(db_oturumu, f"b-{uuid.uuid4().hex[:8]}@example.com", "cok-gizli-parola-b", None)
    db_oturumu.flush()
    ozel_b = kurgu.genel.kullanici_icin(b.id)
    kayit = depo_medya.kaydet(db_oturumu, b.id, PNG + b"B", {"prompt": "b"}, ozel_b.output_dir)
    db_oturumu.commit()
    assert _kos(kurgu, "--sil", "--evet") == artik_dosya.CIKIS_TAMAM
    out = capsys.readouterr().out
    assert f"{b.id}: 1 dosya, 0 artik" in out
    assert os.path.exists(os.path.join(ozel_b.output_dir, kayit["filename"]))


def test_environment_and_user_errors_have_their_own_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    assert artik_dosya.main(["--veri-dizini", str(tmp_path)]) == artik_dosya.CIKIS_ORTAM
    assert db.DATABASE_URL_ENV in capsys.readouterr().err


def test_a_missing_data_root_is_a_user_error(kurgu, capsys):
    assert artik_dosya.main(["--veri-dizini", os.path.join(kurgu.veri_koku, "yok")]) == artik_dosya.CIKIS_KULLANICI
    assert "veri koku yok" in capsys.readouterr().err


def test_an_empty_data_root_is_clean(tmp_path, capsys):
    kok = tmp_path / "bos"
    kok.mkdir()
    assert artik_dosya.main(["--veri-dizini", str(kok)]) == artik_dosya.CIKIS_TAMAM
    assert "0 kullanici, 0 artik" in capsys.readouterr().out


# ── kova kipi (Faz 2 / 2) ────────────────────────────────────────────
#
# Aynı üç durum kovada: satırsız nesne, hesabı silinmiş kullanıcının nesneleri,
# bilinmeyen tür/biçim; dokunulmayanlar: satırlı nesne, medya olmayan anahtar.
# Sahte S3 imza doğruluyor; araç depoyu `dosya.depo_kur`dan alır, test onu
# sahteye bağlar (ortam değişkenleri conftest'te süpürülü).

def _kova_kurgusu(db_oturumu, kullanici, tmp_path):
    from services import dosya, nesne_depo
    from tests.sahte_s3 import SahteS3

    kimlik = nesne_depo.Kimlik("AKID", "GIZLI", "auto")
    sahte = SahteS3("kova", kimlik)
    depo = dosya.NesneDepo(nesne_depo.S3Istemci("https://hesap.r2.example", "kova", kimlik,
                                                istemci=sahte.istemci()), str(tmp_path))
    kok = str(tmp_path)
    ozel = ayar.Ayarlar(data_dir=kok, output_dir=os.path.join(kok, "output"),
                        assets_dir=os.path.join(kok, "assets"), static_dir="").kullanici_icin(kullanici.id)
    satirli = []
    for kayit in (depo_medya.kaydet(db_oturumu, kullanici.id, PNG + b"1", {"prompt": "a"}, ozel.output_dir, depo=depo),
                  depo_medya.kaydet(db_oturumu, kullanici.id, b"\x00mp4", {"prompt": "v", "kind": "video"},
                                    ozel.output_dir, depo=depo)):
        satirli.append(f"kullanicilar/{kullanici.id}/output/{kayit['filename']}")
    v = depo_varlik.kaydet(db_oturumu, kullanici.id, "logos", PNG + b"L", "Logo", ozel.assets_dir, depo=depo)
    satirli.append(f"kullanicilar/{kullanici.id}/assets/logos/{v['filename']}")
    db_oturumu.commit()
    artik = [f"kullanicilar/{kullanici.id}/output/deadbeef0001deadbeef0001deadbeef.png",
             f"kullanicilar/{kullanici.id}/output/deadbeef0002.mp4",
             f"kullanicilar/{kullanici.id}/assets/logos/deadbeef0003.png",
             f"kullanicilar/{kullanici.id}/assets/uploads/eski.png",
             f"kullanicilar/{uuid.uuid4()}/output/hayalet.png"]
    medya_degil = [f"kullanicilar/{kullanici.id}/output/guncelleme.json",
                   f"kullanicilar/{kullanici.id}/output/derin/dizin/x.png"]   # biçim dışı anahtar
    for anahtar in artik + medya_degil:
        depo.istemci.koy(anahtar, PNG, "image/png")
    depo.istemci.koy("kullanicilar/eski-yedek/output/y.png", PNG, "image/png")
    return depo, sahte, set(satirli), set(artik), set(medya_degil)


def test_bucket_mode_lists_exactly_the_stray_objects_and_deletes_only_them(tmp_path, monkeypatch, db_oturumu,
                                                                            kullanici, capsys):
    from services import dosya
    depo, sahte, satirli, artik, medya_degil = _kova_kurgusu(db_oturumu, kullanici, tmp_path)
    monkeypatch.setattr(dosya, "depo_kur", lambda kok, **k: depo)

    # Kova kipinde veri kökü dizini ARANMAZ: olmayan bir dizin verilse de tarama kovaya gider.
    assert artik_dosya.main(["--veri-dizini", str(tmp_path / "yok")]) == artik_dosya.CIKIS_ARTIK_VAR
    out = capsys.readouterr().out
    assert out.startswith("kova: kova")
    listelenen = {s.split("artik: ", 1)[1].strip() for s in out.splitlines() if "artik: " in s}
    assert listelenen == artik
    assert f"{kullanici.id}: 9 dosya, 4 artik" in out and "2 medya degil" in out
    assert "HESABI YOK" in out and "atlandi (UUID degil): kullanicilar/eski-yedek" in out
    assert "toplam: 2 kullanici, 5 artik dosya" in out
    assert set(sahte.nesneler) >= satirli | artik | medya_degil, "kuru koşu hiçbir şey silmez"

    assert artik_dosya.main(["--veri-dizini", str(tmp_path), "--sil", "--evet"]) == artik_dosya.CIKIS_TAMAM
    assert "silindi: 5" in capsys.readouterr().out
    kalan = set(sahte.nesneler)
    assert not (kalan & artik) and satirli <= kalan and medya_degil <= kalan
    assert "kullanicilar/eski-yedek/output/y.png" in kalan
    # Satırlı nesneler hâlâ satırdan bulunuyor.
    ozel = ayar.Ayarlar(data_dir=str(tmp_path), output_dir="", assets_dir="", static_dir="").kullanici_icin(kullanici.id)
    for satir in db_oturumu.scalars(select(Medya).where(Medya.kullanici_id == kullanici.id)):
        assert depo_medya.dosya_yolu(db_oturumu, kullanici.id, satir.id, ozel.output_dir, depo=depo)

    assert artik_dosya.main(["--veri-dizini", str(tmp_path)]) == artik_dosya.CIKIS_TAMAM
    assert "0 artik dosya" in capsys.readouterr().out


def test_a_half_configured_bucket_is_an_environment_error(tmp_path, monkeypatch, capsys, kullanici):
    from services import dosya
    monkeypatch.setenv(dosya.URL_ENV, "https://hesap.r2.example")
    monkeypatch.setenv(dosya.KOVA_ENV, "kova")
    assert artik_dosya.main(["--veri-dizini", str(tmp_path)]) == artik_dosya.CIKIS_ORTAM
    assert "eksik" in capsys.readouterr().err
