"""Lisans, marka ve telif beyanı TEK gerçeği mi anlatıyor.

NEDEN VAR: proje 2026-09-11'de MIT ile public'e açıldı ve MIT tam olarak
korunmak istenen şeye izin veriyordu — "sublicense and/or sell", kaynağı açma
zorunluluğu olmadan. Lisans AGPL-3.0'a çevrildi (gerekçenin tamamı TELIF.md'de).

Bir lisans geçişi, kaçırılan tek bir dosya yüzünden ANLAMSIZLAŞABİLİR: LICENSE
değişip README rozeti MIT kalırsa, ya da uygulamanın içindeki künye hiç
yoksa, karşı taraf "ben MIT sanmıştım" diyebilir ve bu savunma dinlenir. Bu
yüzden geçişin her parçasının bekçisi burada:

  LICENSE           → gerçekten AGPL-3.0'ın DEĞİŞTİRİLMEMİŞ metni mi
  README(.en).md    → rozet ve lisans bölümü aynı şeyi mi söylüyor
  TELIF / MARKA     → var mı, README'den ulaşılıyor mu
  NOTICE            → kopyalarla taşınan bildirim tutarlı mı
  static/index.html → künye uygulamanın İÇİNDE duruyor mu (AGPL §13)

§Yazı geleneği: "Türetilen her şeyin bekçisi bir testtir" — elle yazılmış bir
lisans literali de türetilmiş sayılır, çünkü tek kaynağı LICENSE dosyası.
"""
from __future__ import annotations

import hashlib
import os
import re

import pytest

import guncelleme

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# AGPL-3.0'ın FSF tarafından yayımlanan metninin özeti.
#
# NEDEN PİN: LICENSE metninin KENDİSİ "Everyone is permitted to copy and
# distribute verbatim copies of this license document, but changing it is not
# allowed" diyor — yani bu dosyada yapılan iyi niyetli bir düzenleme (bir satırı
# sarmalamak, bir yazım "düzeltmek") lisansın geçerliliğini tartışmaya açar ve
# göz denetimiyle FARK EDİLMEZ. Özet, o düzenlemeyi kırmızıya çeviriyor.
#
# Metin iki BAĞIMSIZ kaynaktan (SPDX license-list-data ve AGPL-3.0 ile dağıtılan
# bir projenin LICENSE'ı) indirilip boşluk normalizasyonundan sonra birebir
# karşılaştırılarak doğrulandı.
#
# Lisans SÜRÜMÜ bilinçli olarak değiştirilirse (ör. bir gün AGPL-3.0'dan
# başkasına geçilirse) bu satır da o commit'te güncellenir — geçişin kaydı
# TELIF.md'ye yazılmadan değil.
AGPL3_SHA256 = "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6"

# Kopyalarla taşınması gereken belgeler. Yolu değil VARLIĞI sınanıyor: birinin
# silinmesi, geçişin yarısını geri almak demek.
BELGELER = ("LICENSE", "NOTICE", "TELIF.md", "MARKA.md")


def _oku(*parcalar: str) -> str:
    with open(os.path.join(REPO, *parcalar), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------
# LICENSE
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ad", BELGELER)
def test_the_licence_documents_all_exist(ad: str):
    yol = os.path.join(REPO, ad)
    assert os.path.isfile(yol), f"{ad} yok — lisans geçişinin bir parçası eksik"
    assert os.path.getsize(yol) > 0, f"{ad} boş"


def test_license_is_the_unmodified_agpl3_text():
    ham = open(os.path.join(REPO, "LICENSE"), "rb").read()
    bulunan = hashlib.sha256(ham).hexdigest()
    assert bulunan == AGPL3_SHA256, (
        "LICENSE, AGPL-3.0'ın yayımlanan metninden SAPIYOR.\n"
        f"  beklenen sha256: {AGPL3_SHA256}\n"
        f"  bulunan  sha256: {bulunan}\n"
        "Lisans metni değiştirilemez (metnin kendi şartı). Değişiklik bilinçliyse "
        "bu sabiti ve TELIF.md'deki geçiş kaydını AYNI commit'te güncelle."
    )


def test_license_carries_the_network_clause_that_the_transition_was_for():
    """§13 bu geçişin ASIL kazancı: GPL'de olmayan, ağ üzerinden sunulan
    değiştirilmiş kopyaların da kaynağını açmayı zorunlu kılan madde.
    Kromis kendi HTTP sunucusunu koşuyor, yani madde boş değil."""
    metin = _oku("LICENSE")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in metin
    assert "13. Remote Network Interaction" in metin, \
        "§13 yok — bu metin AGPL değil, büyük ihtimalle düz GPL-3.0"


def test_no_mit_licence_claim_survives_in_the_licence_file():
    metin = _oku("LICENSE")
    assert "MIT License" not in metin, \
        "LICENSE hâlâ MIT diyor — geçiş yarım kalmış"


# --------------------------------------------------------------------------
# README'ler — kullanıcının lisansa BAKTIĞI yer
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ad", ("README.md", "README.en.md"))
def test_readme_badge_and_licence_section_agree_with_the_license_file(ad: str):
    """Rozet ile LICENSE'ın ayrışması, "ben MIT sanmıştım" savunmasını
    besleyen tam olarak o kusur — v0.4.1'de sürüm rozetiyle yaşanan
    ayrışmanın (test_version.py) lisanstaki karşılığı, ama bedeli hukuki."""
    metin = _oku(ad)

    rozet = re.search(r"img\.shields\.io/badge/License-([A-Za-z0-9_.+-]+)-", metin)
    assert rozet, f"{ad}: lisans rozeti bulunamadı"
    assert rozet.group(1) == "AGPL_v3", \
        f"{ad}: rozet {rozet.group(1)!r} — LICENSE ise AGPL-3.0"

    assert "AGPL-3.0" in metin, f"{ad}: metinde AGPL-3.0 geçmiyor"
    # "MIT" yalnız GEÇMİŞE atıf olarak geçebilir; rozette ya da lisans
    # beyanında geçerse ayrışma var demektir.
    assert "License: MIT" not in metin and "Lisans: MIT" not in metin, \
        f"{ad}: hâlâ MIT beyanı taşıyor"


@pytest.mark.parametrize("ad", BELGELER)
def test_readme_links_to_every_licence_document(ad: str):
    """Bulunamayan bir belge, olmayan bir belgeyle aynı şey: ihlal iddiasında
    "nereden bilecektim" cevabının kapatıldığı yer README'nin lisans bölümü."""
    metin = _oku("README.md")
    assert f"({ad})" in metin, f"README.md, {ad} belgesine bağlantı vermiyor"


# --------------------------------------------------------------------------
# NOTICE — kopyalarla TAŞINAN bildirim
# --------------------------------------------------------------------------

def test_notice_states_licence_source_and_the_trademark_carve_out():
    metin = _oku("NOTICE")
    assert "AGPL" in metin, "NOTICE lisansı söylemiyor"
    assert f"https://github.com/{guncelleme.DEPO}" in metin, \
        "NOTICE kaynak adresini vermiyor — AGPL §13'ün istediği bilgi bu"
    assert "MARKA.md" in metin, \
        "NOTICE, ad/logo ayrımını söylemiyor — lisansa uyan bir çatal adı da " \
        "alabileceğini sanır"


def test_trademark_policy_names_what_a_fork_has_to_change():
    """MARKA.md'nin işe yaraması, yasak listesine değil DEĞİŞTİRİLECEKLER
    listesine bağlı: çatallayan kişi ne yapacağını bilmiyorsa politika
    caydırmaz, yalnızca tartışma üretir. Güncelleme kanalı listede olmak
    ZORUNDA — değiştirilmezse çatalın kullanıcıları resmî depoya sorar."""
    metin = _oku("MARKA.md")
    for beklenen in ("applicationId", "bundle_identifier", "guncelleme.py",
                     "branding/", "favicon"):
        assert beklenen in metin, \
            f"MARKA.md, çatalın değiştirmesi gereken {beklenen!r} adımını anlatmıyor"


def test_the_copyright_record_keeps_the_previous_licence_text():
    """MIT geri alınamaz: v0.19.0'ı o lisansla alan kişinin hakları duruyor.
    Metnin kaydı tutulmazsa o sürümlerin gerçekte hangi şartlarla dağıtıldığı
    yalnızca git geçmişinde kalır — ihlal tartışmasında ilk sorulacak şey bu."""
    metin = _oku("TELIF.md")
    assert "MIT License" in metin, "TELIF.md eski lisans metnini saklamıyor"
    assert "v0.19.0" in metin, "TELIF.md geçişin sürüm sınırını söylemiyor"
    assert "AGPL-3.0" in metin


# --------------------------------------------------------------------------
# Uygulamanın İÇİ — künye (AGPL §13)
# --------------------------------------------------------------------------

def test_the_app_itself_shows_copyright_licence_and_a_source_link():
    """Depodaki LICENSE, yeniden paketleyen birinin tek hamlede düşürebileceği
    bir dosya. Künye ARAYÜZDE durduğu için onu kaldırmak HTML düzenlemek
    demek — yani kazara değil bilerek yapılır ve ihlal iddiasında aradaki fark
    tam olarak budur (TELIF.md → "İhlal görürsen ne yapmalı").

    Ayrıca AGPL §13'ün şartı: Kromis ağ üzerinden erişilen bir program, yani
    kullanıcısına kaynağa ulaşma yolunu SUNMAK zorunda."""
    metin = _oku("static", "index.html")
    kunye = re.search(r'<p class="field-note settings-legal">(.*?)</p>',
                      metin, re.S)
    assert kunye, "Ayarlar → Hakkında panelinde künye (.settings-legal) yok"
    govde = kunye.group(1)

    assert "©" in govde, "künyede telif işareti yok"
    assert "AGPL-3.0" in govde, "künye lisansı söylemiyor"
    assert f"https://github.com/{guncelleme.DEPO}/blob/main/LICENSE" in govde, \
        "künye LICENSE'a bağlantı vermiyor"
    assert f'href="https://github.com/{guncelleme.DEPO}"' in govde, \
        "künyede kaynak kodu bağlantısı yok — AGPL §13'ün istediği şey bu"
    assert "data-app-version" in govde, \
        "künye sürümü göstermiyor; hangi sürümden türediği ihlal iddiasının kanıtı"


def test_the_stylesheet_actually_renders_the_notice():
    """Künye görünmezse yok sayılır. `.settings-legal` sınıfı HTML'de var olup
    CSS'te karşılığı OLMAYAN bir sınıf olarak kalabilirdi — bu deponun daha
    önce yaşadığı kusur (`settings-update-row`, style.css'teki gerekçesi)."""
    assert ".settings-legal" in _oku("static", "style.css"), \
        "style.css'te .settings-legal kuralı yok"


# --------------------------------------------------------------------------
# Geri çekilen MIT dönemi paketleri

# v0.17.3 / v0.18.0 / v0.19.0 paketlerinin, YAYIN SAYFASINDAN SİLİNMEDEN ÖNCE
# GitHub'ın kendi hesapladığı SHA-256 değerleri.
#
# NEDEN PİN: o üç sürümün hazır paketleri 2026-09-13'te kaldırıldı (gerekçe
# TELIF.md'de: `SHA256SUMS.txt` v0.20.0'da başladı, öncesi doğrulanamıyordu).
# Dosya silinince GitHub'ın hesabı da silindi — geriye kalan TEK nüsha
# TELIF.md'deki liste. Oradan bir satır düşerse o sürüm için "bu ikili benim
# derlememdir" diyebilme imkânı da düşer ve kayıp SESSİZ olur: hiçbir şey
# kırılmaz, kimse fark etmez. Fark etmek bu testin işi.
MIT_DONEMI_OZETLERI: dict[str, tuple[str, ...]] = {
    "v0.17.3": (
        "911de3ed46572901f761c993c5e781b2f1a8bf733e6524efb8d0356aa4ccc60a",
        "b9fd91b716b4692a2459a4b167d0bee5a3903f0dcad508c975a0a70c62c8f427",
        "2d6b047a8b7d36630f91e7cf703dd885db3da8106ae61aad0778386d34efae5d",
    ),
    "v0.18.0": (
        "988d9d6a6612ccdd4456cb8754d06e78ac2eca7d5d2e29b5f283f1bdc5bef349",
        "ed48bc79fdcc3ef765370d7f74b8fb22aefaa22ff6d7f279f3fc52dc5c29d9a7",
        "586f044f620fd93d2fec80a8c2016f497d2b0fcb3b13a966cad6292153c7905e",
    ),
    "v0.19.0": (
        "eea42bdbc8c4f44fec029c13f31275d2633b56e0234c92ca8b4a1261012e2443",
        "2f0dae6ac1fcfa1b1202d2ce8d3d437e6f86bf09b6458e4b4b37efb5035dbb02",
        "669043ebbfefcfc63d2a5100903be09c7e2452bc908c2f0fd23fb6f7de6ae2a6",
    ),
}

PAKET_ADLARI = (
    "kromis-android-arm64.apk",
    "kromis-macOS-arm64.zip",
    "kromis-windows-x64.zip",
)


@pytest.mark.parametrize("surum", sorted(MIT_DONEMI_OZETLERI))
def test_TELIF_keeps_every_fingerprint_of_the_withdrawn_MIT_packages(surum):
    """Silinen paketin parmak izi belgede duruyor mu — sürüm sürüm.

    İhlal iddiasının en somut anı şudur: karşı tarafta bir dosya var, "bu
    seninkinden mi çıktı?" diye soruluyor. Cevabı verecek şey özet. MIT
    dönemi için o özetin başka nüshası kalmadı."""
    metin = _oku("TELIF.md")
    assert surum in metin, f"TELIF.md {surum}'ı hiç anmıyor"
    for ozet, ad in zip(MIT_DONEMI_OZETLERI[surum], PAKET_ADLARI):
        assert f"{ozet}  {ad}" in metin, \
            f"{surum} için {ad} özeti TELIF.md'de yok (ya da biçimi bozuldu)"


def test_TELIF_says_WHY_the_MIT_packages_were_withdrawn():
    """Kayıt, gerekçesi olmadan yarım.

    Paketlerin kaldırılması lisansla karıştırılırsa belge kendi anlattığı
    şeyle çelişir: MIT geri alınamaz ve bu belge zaten öyle diyor. Kaldırma
    DAĞITIM hijyeni — v0.20.0 öncesinde `SHA256SUMS.txt` yoktu. Bu ayrımın
    yazılı durması, ileride 'demek ki lisansı gizlemeye çalışmış' okumasının
    önündeki tek şey."""
    metin = _oku("TELIF.md")
    assert "SHA256SUMS.txt" in metin, \
        "TELIF.md kaldırmanın gerekçesini (doğrulanamayan paket) söylemiyor"
    assert "geri alma" in metin or "geri alınamaz" in metin, \
        "TELIF.md MIT'in geri alınamadığını söylemeyi bırakmış"


def test_the_withdrawn_releases_still_exist_as_a_dated_record():
    """Kaldırılan DOSYALAR; yayın kayıtları değil.

    Sürüm kayıtlarını da silmek, 'hangi sürüm MIT'ti' sorusunun cevabını
    yalnız telif sahibinin düzenleyebildiği bir belgeye indirger — yani
    kanıt değerini düşürür. Belge bu ayrımı açıkça yazmak zorunda ki
    ileride biri 'madem sildin, hepsini silseydin' dediğinde gerekçe
    hazır olsun."""
    metin = _oku("TELIF.md")
    assert "Silinen yalnız dosyalar" in metin, \
        "TELIF.md yayın kaydı ile paket dosyası ayrımını yapmıyor"
