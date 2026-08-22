"""providers: sevk memuru, zaman aşımı politikası ve adaptör kayıt mandalı.

Bu dosyanın en değerli iddiası zaman aşımı: `azure_client.read_timeout_for`'un
formülü (180 + 120·(n-1)) AÇIK bir varsayıma dayanıyor ve kendi yorumunda
yazılı — `build_payload` `n`'i gövdeye koyuyor, yani 4 görsel TEK POST'ta
üretiliyor. Adet başına ayrı istek atan bir sağlayıcıda o varsayım yanlış ve
karışırsa her isteğe 540 saniye verilir: 36 dakikalık en kötü hâl.
"""
import ast
import dataclasses
import pathlib

import pytest

import azure_client as ac
import catalog
import providers

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_katalogdaki_her_saglayicinin_adaptoru_kayitli():
    """Kataloğa model eklemek yetmiyor; adaptörü de kaydedilmiş olmalı.

    Kayıtlı olmayan sağlayıcı SESSİZCE Azure'a düşmüyor, Türkçe hata veriyor —
    ama bu testin işi o hatanın hiç oluşmaması.
    """
    for m in catalog.IMAGE_MODELS:
        assert m.provider in providers.adapter_ids(), (
            f"{m.id}: `{m.provider}` adaptörü _ADAPTERS'ta yok")


def test_adaptorler_STATIK_import_ediliyor():
    """`importlib` ile dinamik import PyInstaller'ın statik analizinden KAÇAR.

    `gpt-image-studio.spec`'in `hiddenimports=[]` değeri o analize dayanıyor ve
    o dosyanın 50 satırlık yorumu bunu ölçülmüş bir değişmez sayıyor. Dinamik
    import edilen bir adaptör paketlenmiş uygulamada bulunamaz — ve hata yalnız
    .app/.apk içinde görünür, testte hiç.
    """
    tree = ast.parse((REPO / "providers.py").read_text(encoding="utf-8"))

    # Yalnızca GERÇEK import ifadeleri ve çağrılar taranıyor, ham metin DEĞİL:
    # ilk yazımda `"importlib" not in kaynak` idi ve providers.py'nin kendi
    # açıklama yorumundaki "importlib ile DEĞİL" cümlesine takıldı. Bir kuralı
    # anlatan yorumun o kuralı ihlal etmiş sayılması, testi gürültüye çevirir.
    ice_alinanlar = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            ice_alinanlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            ice_alinanlar.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute) and node.attr == "import_module":
            pytest.fail("providers.py `import_module` çağırıyor")
        elif isinstance(node, ast.Name) and node.id == "__import__":
            pytest.fail("providers.py `__import__` çağırıyor")

    assert "importlib" not in ice_alinanlar, "providers.py importlib import ediyor"


def test_bilinmeyen_model_Turkce_hata_ham_500_DEGIL():
    """Bayat bir istemci artık var olmayan bir modeli isteyebilir."""
    with pytest.raises(ac.ImageError) as exc:
        providers.generate("boyle-bir-model-yok", "p", "1024x1024", "low", 1)
    assert "boyle-bir-model-yok" in str(exc.value)


def test_adaptoru_olmayan_saglayici_SESSIZCE_azure_a_dusmuyor(monkeypatch):
    """En tehlikeli sessiz sapma bu olurdu: kullanıcı Gemini seçer, Azure üretir.

    Hem yanlış estetik hem yanlış fatura — ve 200 döndüğü için hiçbir yerde iz
    kalmaz.
    """
    hayali = dataclasses.replace(catalog.IMAGE_MODELS[0], id="hayali",
                                 provider="henuz-yazilmadi")
    monkeypatch.setattr(catalog, "IMAGE_MODELS",
                        catalog.IMAGE_MODELS + (hayali,))
    with pytest.raises(ac.ImageError) as exc:
        providers.generate("hayali", "p", "1024x1024", "low", 1)
    assert "henuz-yazilmadi" in str(exc.value)


def test_duzenlemeyi_desteklemeyen_model_reddediliyor(monkeypatch):
    tek_atis = dataclasses.replace(catalog.IMAGE_MODELS[0], id="tek-atis",
                                   supports_edit=False)
    monkeypatch.setattr(catalog, "IMAGE_MODELS",
                        catalog.IMAGE_MODELS + (tek_atis,))
    with pytest.raises(ac.ImageError) as exc:
        providers.edit("tek-atis", "p", [("a.png", b"x")], "1024x1024", "low", 1)
    assert "referans görselle çalışmıyor" in str(exc.value)


# ── Zaman aşımı politikası ─────────────────────────────────────────────

TEK_POST = catalog.IMAGE_MODELS[0]                                  # n görsel tek istekte
FANOUT = dataclasses.replace(TEK_POST, id="fanout", images_per_request=1)


def test_tek_POST_lu_saglayicida_sure_adetle_BUYUYOR():
    """Bugünkü Azure davranışı: tek istek n görsel döndürüyor."""
    assert providers.read_timeout_for(TEK_POST, 1) == ac.read_timeout_for(1)
    assert providers.read_timeout_for(TEK_POST, 4) == ac.read_timeout_for(4)
    # Tek istek olduğu için toplam da tek isteğin süresi.
    assert providers.total_budget(TEK_POST, 4) == ac.read_timeout_for(4)


def test_adet_basina_ayri_istekte_TEK_ISTEGIN_suresi_SABIT():
    """Asıl bulgu: n=4'te her isteğe 540 saniye vermek 36 dakika demekti."""
    assert providers.read_timeout_for(FANOUT, 4) == ac.read_timeout_for(1)
    assert providers.read_timeout_for(FANOUT, 1) == ac.read_timeout_for(1)


def test_adet_basina_ayri_istekte_TOPLAM_butce_adetle_buyuyor():
    """Büyüyen şey döngünün toplamı — tek isteğin süresi değil."""
    assert providers.total_budget(FANOUT, 4) == ac.read_timeout_for(1) * 4
    assert providers.total_budget(FANOUT, 4) < providers.total_budget(
        dataclasses.replace(FANOUT, images_per_request=1), 12)


def test_kuyruklu_saglayici_kendi_suresini_dayatiyor():
    """fal/Replicate tarzı kuyruklu akış: süre Azure formülünden gelmiyor."""
    kuyruklu = dataclasses.replace(FANOUT, id="kuyruklu", poll_timeout=45.0)
    assert providers.read_timeout_for(kuyruklu, 4) == 45.0
    assert providers.total_budget(kuyruklu, 4) == 180.0


# ── Paylaşılan hata gövdesi çözümlemesi ────────────────────────────────


@pytest.mark.parametrize("body,beklenen", [
    ({"error": {"message": "içerik reddedildi"}}, "içerik reddedildi"),
    ({"error": "düz metin hata"}, "düz metin hata"),
    ({"baska": 1}, ""),
    (None, ""),
    ("hiç sözlük değil", ""),
])
def test_detail_of_dort_saglayicinin_ORTAK_seklini_cozuyor(body, beklenen):
    """`{"error": {"message": …}}` biçimini Azure, OpenAI, Gemini ve Anthropic
    dördü de kullanıyor. ŞEKİL paylaşılıyor, Türkçe MESAJ paylaşılmıyor."""
    assert providers.detail_of(body) == beklenen


# Google'ın GERÇEK hata gövdesi, `generativelanguage.googleapis.com`a yapılan
# canlı çağrıdan AYNEN kopyalandı (22 Ağustos 2026). Sarmal bir NESNE değil,
# tek öğelik bir DİZİ — ve aynı sarmal iki uçta da geliyor:
# `/v1beta/interactions` (görsel) ve `/v1beta/openai/chat/completions` (sohbet).
GOOGLE_GERCEK_400 = [{
    "error": {
        "code": 400,
        "message": "API key not valid. Please pass a valid API key.",
        "status": "INVALID_ARGUMENT",
        "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                     "reason": "API_KEY_INVALID",
                     "domain": "googleapis.com"}],
    }
}]


def test_detail_of_googlein_TEK_OGELIK_DIZI_sarmalini_aciyor():
    """Bu iddia canlı bir çağrıyla ölçüldü ve elle yazılmış sözlük gövdeleri
    onu kaçırıyordu.

    Google hata gövdesini `{"error": …}` olarak DEĞİL, `[{"error": …}]` olarak
    döndürüyor. Dizi açılmazsa `isinstance(body, dict)` kapısı boş dize
    döndürüyor ve BÜTÜN Gemini hataları çıplak bir "HTTP 400"a çöküyor: 400'ü
    ikiye ayıran dal (geçersiz anahtar ↔ desteklenmeyen jeton) hiç
    tetiklenmiyor, yani anahtarı doğru olan kullanıcı sebebi hiçbir yerde
    okumuyor — bu deponun "sessiz sapma yasak" duruşunun tam karşıtı.
    """
    assert providers.detail_of(GOOGLE_GERCEK_400) == (
        "API key not valid. Please pass a valid API key.")


def test_detail_of_COK_OGELI_diziyi_BILEREK_acmiyor():
    """İlkini seçmek, geri kalanını sessizce yutmak olurdu.

    Tek öğelik sarmal ölçülmüş bir olgu; çok öğeli bir dizi ise bu depoda
    hiçbir sağlayıcıdan görülmedi. Görülmeyen bir şekli tahminle çözmek,
    kullanıcıya eksik bir hata metni göstermenin sessiz yolu.
    """
    assert providers.detail_of([{"error": {"message": "bir"}},
                                {"error": {"message": "iki"}}]) == ""
    assert providers.detail_of([]) == ""


def test_detail_of_duz_NESNE_yolunu_degistirmiyor():
    """Azure ve OpenAI düz nesne döndürüyor: dizi kapısı onların yolunu
    baytça değiştirmemeli — tripwire, sarmal açma bir gün genelleşirse."""
    assert providers.detail_of({"error": {"message": "azure der ki"}}) == "azure der ki"
    assert providers.detail_of([["iç içe dizi"]]) == ""


def test_azure_yolu_kimligi_ONCEDEN_cozmuyor():
    """Kimlik `ac.generate`'in İÇİNDE, tembel biçimde çözülüyor.

    İlk yazımda shim `credstore.resolve(...)` çağırıyordu ve 104 test birden
    düştü: rota testlerinin tamamı `ac.generate`'i monkeypatch'liyor ve kimliği
    hiç yapılandırmıyor. Testlerin ölçtüğü doğruydu — çözümü öne almak davranış
    DEĞİŞİKLİĞİ. Bu iddia o regresyonu kalıcı olarak kapatıyor.
    """
    cagrildi = {}

    def fake_generate(prompt, size, quality, n, *, client=None, credentials=None):
        cagrildi["credentials"] = credentials
        return [b"PNG"]

    import providers as prov
    orijinal = ac.generate
    try:
        ac.generate = fake_generate
        out = prov.generate(catalog.DEFAULT_IMAGE_MODEL, "p", "1024x1024", "low", 1)
    finally:
        ac.generate = orijinal

    assert out == [b"PNG"]
    assert cagrildi["credentials"] is None, (
        "shim kimliği önceden çözdü: stub'lanmış çağrı gerçek credentials.env ister")


# ── Gövdenin ANLAMI: iki paylaşılan yüklem ─────────────────────────────


@pytest.mark.parametrize("detail", [
    "API key not valid. Please pass a valid API key.",
    "API_KEY_INVALID",
    "Incorrect API key provided: sk-***",
])
def test_is_invalid_key_ANAHTAR_metinlerini_taniyor(detail):
    """400'ün iki anlamı bu yüklemle ayrılıyor. Tanımazsa geçersiz anahtar
    çıplak bir "HTTP 400" olur ve kullanıcı sebebi hiçbir yerde okumaz."""
    assert providers.is_invalid_key(detail)


@pytest.mark.parametrize("detail", [
    "Unsupported aspect_ratio: 7:3",
    "Unknown name \"content\": Cannot find field.",
    "",
])
def test_is_invalid_key_BASKA_hatalari_anahtar_SANMIYOR(detail):
    """Yanlış pozitif buradaki en pahalı hata: anahtarı DOĞRU olan kullanıcıya
    "anahtarını yeniden kaydet" demek, onu çalışan kurulumunu bozmaya davet
    etmek olurdu (`gemini_client.map_error`ın 400 dalının gerekçesi)."""
    assert not providers.is_invalid_key(detail)


@pytest.mark.parametrize("detail", [
    "content policy violation",                      # OpenAI
    "Your request was rejected as a result of our safety system.",
    "content filter triggered",                      # Azure sohbet
    "The response was filtered due to the prompt triggering Azure "
    "OpenAI's content management policy.",
    "Candidate was blocked due to safety",           # Google
    "PROHIBITED_CONTENT",
])
def test_is_content_policy_GERCEK_reddi_taniyor(detail):
    """Dört sağlayıcının ölçülmüş metinleri. Biri tanınmazsa kullanıcı
    "istek başarısız (HTTP 400)" okuyor ve prompt'unu değiştirmesi
    gerektiğini hiçbir yerden anlamıyor."""
    assert providers.is_content_policy(detail)


def test_is_content_policy_SEMA_hatasini_icerik_reddi_SANMIYOR():
    """ÖLÇÜLMÜŞ YANLIŞ POZİTİF ve bu testin varlık sebebi bu.

    Öncesinde beş `map_error`ın üçünde ölçüt çıplak `"content" in detail`
    idi. Google şema hatasını `Unknown name "content": Cannot find field.`
    diye anlatıyor — yani GÖVDEDEKİ BİR ALAN ADINDAN söz ediyor, kullanıcının
    mesajından değil — ve o dize "İçerik politikası reddi: mesaj engellendi"
    olarak gösteriliyordu. Kullanıcı hiç engellenmemiş bir mesajı yeniden
    yazmaya çalışıyor, gerçek sebep (istemcinin yanlış alan göndermesi)
    hiçbir yerde görünmüyordu.
    """
    assert not providers.is_content_policy(
        'Unknown name "content": Cannot find field.')
    assert not providers.is_content_policy(
        "Invalid value for 'content': expected a string")
    assert not providers.is_content_policy(
        "messages[0].content is required")
    assert not providers.is_content_policy("")
