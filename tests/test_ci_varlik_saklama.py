"""Yüklenen varlıklar ne kadar yaşıyor — ve neden bu kadar yaşamaları yetiyor.

BU DOSYANIN VAR OLMA SEBEBİ tek bir koşu: 2026-08-28'de CI'ın ÜÇ paketleme işi
de kırmızıya düştü ve hiçbirinin sebebi kod değildi. macOS paketi derlendi,
`Info.plist` sürümü doğrulandı; Windows paketi derlendi, `FileVersion` /
`ProductVersion` / `FixedFileInfo` / `CompanyName` dördü de geçti; Android
wheel'i etiketiyle ve `.so`suyla doğrulandı. Üçü de bir sonraki adımda,
`actions/upload-artifact` üzerinde öldü:

    Failed to CreateArtifact: Artifact storage quota has been hit.

O gün depoda 221 canlı varlık ve 3.98 GiB birikmişti. Sebep, saklama süresinin
varlığın İŞİNDEN bağımsız seçilmiş olmasıydı: paketler 30, wheel 90 gün
tutuluyordu — oysa dört yüklemenin de tüketicisi KENDİ KOŞUSUNUN İÇİNDE.
`release.yml`'in `yayinla` işi `lumeo-*`ı dakikalar sonra indiriyor,
`_paket-android.yml` wheel'i saniyeler sonra. Depo private olduğu için bu
birikimin bir tavanı var ve tavana çarpınca CI, kodu hakkında hiçbir şey
söylemeden kırmızı oluyor: en pahalı kırmızı türü, çünkü yanlış yere baktırıyor.

İDDİALAR NEYE BAKIYOR: süreye VE süreyi savunulabilir kılan varsayıma. Kısa
saklamanın dayanağı "hiçbir indirme kendi koşusunun dışına uzanmıyor"; biri bir
gün `download-artifact`e `run-id` verirse o dayanak çöker ve süre yeniden
düşünülmelidir. O yüzden burada iki ayrı şey mandallanıyor — sayının kendisi ve
sayıyı doğru kılan sebep.

SONRASI — SÜRE YETMEDİ. Saklama kısaltıldıktan ve depodaki 3.98 GiB'ın tamamı
silindikten sonra bile kota SAATLERCE dolu kaldı (sayaç 6-12 saatte bir
hesaplanıyor, üstelik havuz hesap geneli). Yayın hattı o süre boyunca kendi
hatasız ürettiği ikilileri teslim edemedi. Ders, sürenin ötesinde: ücretsiz
olmayan bir depoya BAĞLI KALMAK yayının kendisini rehin veriyor. Bu yüzden
paketler artık taslak yayına, wheel de önbelleğe teslim ediliyor
(test_release_manifest.py o yapıyı mandallıyor) ve aşağıdaki son iddia varlık
TÜKETİCİSİNİN geri gelmesini yasaklıyor.

YAML gerçekten AYRIŞTIRILIYOR (test_release_manifest.py'nin gerekçesi):
biçimlendirme değişikliği iddiaları anlamsızlaştırmasın. Gerekçe yorumları da
tam bu sayıları TIRNAK İÇİNDE anlatıyor, yani metinde "30" aramak yanlış
cevabı verirdi — iddia kodu arar, kelimeyi değil.
"""
from __future__ import annotations

import os

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_AKISLARI = os.path.join(REPO, ".github", "workflows")

# ÜST SINIR. Tüketicisi kendi koşusunda biten bir dosya haftalarca kotada
# durmamalı. 7, koşu dışında GERÇEK bir insan tüketicisi olan tek varlığa göre
# seçildi (Yol A'da wheel'i indirip `android/wheels/` altına işleyen bakımcı);
# paketlerin hiçbirinin öyle bir tüketicisi yok, onlar 1 günde duruyor.
EN_UZUN_GUN = 7


def _akis_dosyalari() -> list[str]:
    return sorted(
        os.path.join(IS_AKISLARI, ad)
        for ad in os.listdir(IS_AKISLARI)
        if ad.endswith((".yml", ".yaml"))
    )


def _adimlar(yol: str) -> list[dict]:
    with open(yol, encoding="utf-8") as f:
        belge = yaml.safe_load(f)
    cikan: list[dict] = []
    for is_ in (belge.get("jobs") or {}).values():
        # Çağrılabilir workflow'u `uses:` ile kullanan işlerde `steps` yok.
        for adim in (is_.get("steps") or []):
            if isinstance(adim, dict):
                cikan.append(adim)
    return cikan


def _eylem(adim: dict) -> str:
    return str(adim.get("uses") or "")


@pytest.fixture(scope="module")
def yuklemeler() -> list[tuple[str, dict]]:
    """(dosya, adım) çiftleri — her `actions/upload-artifact` kullanımı."""
    return [
        (os.path.basename(yol), adim)
        for yol in _akis_dosyalari()
        for adim in _adimlar(yol)
        if _eylem(adim).startswith("actions/upload-artifact")
    ]


@pytest.fixture(scope="module")
def indirmeler() -> list[tuple[str, dict]]:
    return [
        (os.path.basename(yol), adim)
        for yol in _akis_dosyalari()
        for adim in _adimlar(yol)
        if _eylem(adim).startswith("actions/download-artifact")
    ]


def test_the_collector_sees_every_upload_step(yuklemeler):
    """Boş bir küme aşağıdaki iddiaların HEPSİNİ sessizce yeşil yapardı.

    Sayı elle yazılmıyor, metinden türetiliyor: adım `- uses:` yerine
    `- name:` + `uses:` biçiminde yazıldığında ya da yeni bir çağrılabilir
    workflow eklendiğinde ayrıştırıcı sessizce eksik toplarsa burası kırmızı
    olur. Deponun altı kez düştüğü tuzak bu — mandalın kendisi bozulunca
    takım hâlâ yeşil kalıyor.
    """
    metinde = 0
    for yol in _akis_dosyalari():
        with open(yol, encoding="utf-8") as f:
            metinde += f.read().count("uses: actions/upload-artifact")
    assert metinde > 0, "hiç yükleme adımı yok — ayrıştırıcı da metin de şüpheli"
    assert len(yuklemeler) == metinde, (
        f"ayrıştırıcı {len(yuklemeler)} yükleme gördü, metinde {metinde} var"
    )


def test_every_uploaded_artifact_says_how_long_it_is_kept(yuklemeler):
    """`retention-days` verilmeyen varlık 90 GÜN yaşıyor (GitHub varsayılanı).

    Sessiz olduğu için tehlikeli: kotayı dolduran şey her zaman biri unutulmuş
    bir alan oluyor, yanlış yazılmış bir alan değil.
    """
    for dosya, adim in yuklemeler:
        ile = adim.get("with") or {}
        assert "retention-days" in ile, (
            f"{dosya}: '{ile.get('name')}' varlığı saklama süresi vermiyor — "
            "GitHub varsayılanı 90 gün"
        )


def test_the_retention_is_a_plain_number_the_gate_can_read(yuklemeler):
    """`${{ … }}` bir ifade; üst sınır iddiası onun üzerinde ölçüm yapamaz.

    İfade yasak değil, ama girdiğinde bu kapı sessizce hiçbir şey ölçmemeye
    başlar — o yüzden kapı, ölçemediği bir değeri kabul etmiyor.
    """
    for dosya, adim in yuklemeler:
        gun = (adim.get("with") or {})["retention-days"]
        assert isinstance(gun, int), (
            f"{dosya}: '{(adim.get('with') or {}).get('name')}' saklama süresi "
            f"düz bir sayı değil ({gun!r}) — üst sınır kapısı onu ölçemez"
        )


def test_no_artifact_outlives_the_run_that_needs_it(yuklemeler):
    """Asıl kapı: 2026-08-28'de kotayı dolduran 30 ve 90 buradan geçemez."""
    for dosya, adim in yuklemeler:
        ile = adim.get("with") or {}
        assert 1 <= ile["retention-days"] <= EN_UZUN_GUN, (
            f"{dosya}: '{ile.get('name')}' {ile['retention-days']} gün "
            f"saklanıyor; üst sınır {EN_UZUN_GUN}. Varlığı okuyan iş kendi "
            "koşusunun içinde — uzun saklama kotayı doldurup CI'ı kod hakkında "
            "hiçbir şey söylemeden kırmızıya düşürüyor."
        )


def test_nothing_consumes_an_artifact_any_more(indirmeler):
    """Kısa saklama bir ÖNLEMdi; teslimi varlıktan çıkarmak ÇÖZÜMdü.

    Bir `download-artifact` adımı geri geldiği an, o adımın işi yeniden Actions
    varlık deposuna bağımlı olur: kota dolduğunda (ki 2026-08-28'de doldu ve
    depo boşaltıldıktan sonra bile saatlerce açılmadı) iş, ürettiği şey kusursuz
    olsa bile kırmızıya düşer. Ne yükleme ne indirme kaldı; iddia bunu koruyor.

    `run-id` de ayrıca yasak DEĞİL, çünkü zaten hiç indirme yok — ama bir gün
    biri eklerse bu iddia onu yakalar ve bu dosyanın başlığına yönlendirir.
    """
    assert indirmeler == [], (
        "varlık indiren adım(lar) geri geldi: "
        + ", ".join(f"{d}:{(a.get('with') or {}).get('name')}" for d, a in indirmeler)
    )
