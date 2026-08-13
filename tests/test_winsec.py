"""winsec — Windows'ta 0600'ün karşılığı olan DACL sıkılaştırması.

Bu dosyanın tamamı Windows'a bağlı: POSIX'te `os.chmod` işi zaten yapıyor ve
modül no-op. macOS/CI Linux'ta atlanıyor, yani bu güvenceyi yalnız gerçek
Windows koşusu ölçebiliyor — Faz 0'ın dersi bu (CI "yeşil ama boş" çıkmıştı).

Ölçülen üç şey ayrı ayrı önemli:
  1. Sıkılaştırma gerçekten uyguluyor mu (SDDL SID tabanlı okunuyor, hesap
     ADIYLA değil — Türkçe Windows'ta ad yerelleşir).
  2. Dizindeki kalıtılabilir ACE, içeride SONRADAN doğan dosyaya geçiyor mu —
     `azure_client._atomic_write`'ın geçici dosyası bu sayede yazımdan önce
     korunuyor.
  3. `os.replace` DACL'i taşıyor mu — taşımasa atomik yazım her kaydetmede
     izinleri sıfırlar ve güvence sessizce kaybolurdu.
"""
import os

import pytest

import winsec

pytestmark = pytest.mark.skipif(not winsec.is_supported(),
                                reason="DACL yalnızca Windows'ta anlamlı")

SAHTE_ICERIK = "AZURE_IMAGE_API_KEY=SAHTE-ANAHTAR\n"


def _yaz(path) -> str:
    path.write_text(SAHTE_ICERIK, encoding="utf-8")
    return str(path)


def test_sikilastirilmamis_dosya_owner_only_degildir(tmp_path):
    """Negatif kutup: kalıtımla gelen ACE'ler (SYSTEM, Administrators) varken
    iddia YANLIŞ dönmeli — yoksa test her koşulda yeşil olurdu."""
    assert not winsec.is_owner_only(_yaz(tmp_path / "acik.env"))


def test_sikilastirma_tek_ace_birakir(tmp_path):
    path = _yaz(tmp_path / "cred.env")
    winsec.restrict_to_current_user(path)

    assert winsec.is_owner_only(path)
    sddl = winsec.dacl_sddl(path)
    assert sddl.startswith("D:P")          # kalıtım kesik
    assert sddl.count("(") == 1            # tek ACE
    assert "S-1-5-18" not in sddl          # SYSTEM bilerek listede değil


def test_sikilastirma_icerigi_bozmaz(tmp_path):
    """DACL yazımı dosyanın kendisine dokunmaz — anahtar yerinde kalmalı."""
    path = _yaz(tmp_path / "cred.env")
    winsec.restrict_to_current_user(path)

    assert (tmp_path / "cred.env").read_text(encoding="utf-8") == SAHTE_ICERIK


def test_sikilastirilmis_dizinde_dogan_dosya_kalitimla_korunur(tmp_path):
    """`_atomic_write`'ın geçici dosyası bu kalıtıma dayanıyor.

    Dizin ACE'si `OICI` ile işaretlenmezse geçici dosya kalıtımla üst dizinin
    geniş izinlerini alır ve içeriği (API anahtarı) o pencerede okunabilir olur.
    """
    d = tmp_path / "cfg"
    d.mkdir()
    winsec.restrict_to_current_user(str(d))

    sonradan = _yaz(d / "sonradan.tmp")
    sddl = winsec.dacl_sddl(sonradan)
    assert "S-1-5-18" not in sddl, f"SYSTEM kalıtımla sızdı: {sddl}"
    assert sddl.count("(") == 1, f"beklenmeyen ACE sayısı: {sddl}"


def test_os_replace_dacli_tasir(tmp_path):
    """Atomik yazımın taşıyıcısı: replace izinleri sıfırlamamalı."""
    kaynak = _yaz(tmp_path / "yeni.tmp")
    hedef = _yaz(tmp_path / "cred.env")
    winsec.restrict_to_current_user(kaynak)

    os.replace(kaynak, hedef)

    assert winsec.is_owner_only(str(hedef))


def test_acik_dosyanin_daclini_degistirebiliriz(tmp_path):
    """`_atomic_write` dosyayı AÇIK tutarken sıkılaştırıyor (mkstemp'in fd'si).

    Windows'ta paylaşım kipi yüzünden ikinci bir tanıtıcı açılamazsa
    sıkılaştırma orada patlardı; o durumda sıra "yaz → kapat → sıkılaştır"a
    çevrilmek zorunda kalırdı. Bu test o varsayımı sabitliyor.
    """
    path = str(tmp_path / "acik.env")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAHTE_ICERIK)
        winsec.restrict_to_current_user(path)

    assert winsec.is_owner_only(path)
