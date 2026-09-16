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


# ── SID TEMSİLİ (CI Windows'un 6 yanlış kırmızısının sınıfı) ────────────
#
# CI runner'ı yerleşik Administrator (RID 500) hesabıyla koşuyor. Yazılan DACL
# sayısal SID içeriyor ama Windows geri okurken SDDL'in takma adını yazıyor:
# `D:PAI(A;;FA;;;LA)`. Metin karşılaştıran sürüm bu yüzden DOĞRU bir DACL'i
# yanlış sayıyordu. Aşağıdaki testler o mekanizmayı kullanıcının makinesinde de
# üretiyor (hesap RID 1001 olsa bile), yani düzeltme yalnız runner'da değil HER
# YERDE ölçülüyor. Eski kodda ilk ikisi kırmızıya düşer.


def _sid_ile_dacl_kur(path: str, sid_ifadesi: str) -> None:
    """DACL'i verilen SID İFADESİYLE kurar (takma ad olabilir).

    `restrict_to_current_user` her zaman sayısal SID yazıyor, yani takma adlı
    hâli üretmenin başka yolu yok — runner'daki durum burada elle kuruluyor.
    """
    # `_set_dacl` win32 dalında tanımlı; mypy `platform = "linux"` ile o dalı
    # okumuyor (pyproject.toml → [tool.mypy]). Dosya zaten `skipif` ile Windows'a
    # bağlı.
    winsec._set_dacl(path, f"D:P(A;;FA;;;{sid_ifadesi})")  # type: ignore[attr-defined]


def test_takma_adli_sid_ayni_hesabi_gosterirse_owner_only_sayilir(tmp_path):
    """`LA` ile yazılmış DACL, çözülmüş SID mevcut kullanıcıyla aynıysa geçmeli.

    CI'daki 6 kırmızının birebir mekanizması: DACL'de takma ad, beklentide
    sayısal SID. Eski kod `"LA" != "S-1-5-21-…-500"` diye False dönüyordu.
    """
    path = _yaz(tmp_path / "takma.env")
    gercek_sid = winsec._current_user_sid()
    la_sid = winsec._resolve_sid("LA")
    assert la_sid and la_sid.endswith("-500"), la_sid

    try:
        _sid_ile_dacl_kur(path, "LA")
        # Windows'un GERÇEKTEN takma adla geri okuduğunu doğrula — bu satır
        # düşerse testin öncülü çürür ve asıl iddia anlamsızlaşır.
        assert "LA)" in winsec.dacl_sddl(path), winsec.dacl_sddl(path)

        # Mevcut kullanıcı "LA"nın çözüldüğü hesapmış gibi ölç.
        orig = winsec._current_user_sid
        winsec._current_user_sid = lambda: la_sid
        try:
            assert winsec.is_owner_only(path), winsec.dacl_sddl(path)
        finally:
            winsec._current_user_sid = orig
    finally:
        # DACL yalnız LA'ya izin veriyor; tmp'de erişilemez dosya bırakmayalım.
        _sid_ile_dacl_kur(path, gercek_sid)


def test_baska_hesabin_takma_adi_owner_only_sayilmaz(tmp_path):
    """Negatif kutup: düzeltme "her SID'i eşleştir" DEMEK DEĞİL.

    Bu test olmadan `_resolve_sid`'i hep mevcut kullanıcıya eşitleyen bir sürüm
    de yeşil kalırdı — güvence sessizce boşalırdı, üstelik dosya API anahtarını
    tutuyor. `BA` (Administrators, S-1-5-32-544) mevcut kullanıcının SID'i değil.
    """
    path = _yaz(tmp_path / "baskasi.env")
    gercek_sid = winsec._current_user_sid()
    try:
        _sid_ile_dacl_kur(path, "BA")
        assert not winsec.is_owner_only(path), winsec.dacl_sddl(path)
    finally:
        _sid_ile_dacl_kur(path, gercek_sid)


def test_resolve_sid_bicimden_bagimsizdir():
    """Çözücünün sözleşmesi: takma ad ve sayısal biçim aynı SID'e inmeli.

    `BA` sabit ve makineden bağımsız (S-1-5-32-544) — iddia bu yüzden bu
    makineye özgü bir değere dayanmıyor. Geçersiz girdi None dönmeli: hatanın
    yutulup "eşleşti" sayılması güvenceyi boşaltan sessiz başarısızlık olurdu.
    """
    assert winsec._resolve_sid("BA") == "S-1-5-32-544"
    assert winsec._resolve_sid("S-1-5-32-544") == "S-1-5-32-544"
    assert winsec._resolve_sid("SY") == "S-1-5-18"
    assert winsec._resolve_sid("ZZZ") is None
    assert winsec._resolve_sid("") is None


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
