"""/api/settings route'ları: durum okuma + write-only kaydetme."""
import pytest
from fastapi.testclient import TestClient

import azure_client as ac
import app as appmod
import models
import version


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "app" / "credentials.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "default.env"))
    return TestClient(appmod.app)


def test_get_settings_not_configured(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["endpoint"] is None


def test_post_settings_saves_and_status_reflects(client):
    r = client.post("/api/settings", json={
        "api_key": "SUPERSECRET", "base_url": "https://ep/openai/v1/"})
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["endpoint"] == "https://ep/openai/v1/"
    # response key sızdırmamalı
    assert "SUPERSECRET" not in r.text

    g = client.get("/api/settings")
    assert g.json()["configured"] is True
    assert "SUPERSECRET" not in g.text


def test_post_settings_rejects_bad_url(client):
    r = client.post("/api/settings", json={"api_key": "K", "base_url": "ftp://x/"})
    assert r.status_code == 422


def test_post_settings_rejects_empty_key(client):
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://x/"})
    assert r.status_code == 422


def test_post_blank_key_keeps_existing(client):
    # önce tam kayıt
    client.post("/api/settings", json={
        "api_key": "KEEPME", "base_url": "https://old/openai/v1/"})
    # sonra sadece endpoint güncelle (key boş)
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://new/openai/v1/"})
    assert r.status_code == 200
    assert r.json()["endpoint"] == "https://new/openai/v1/"
    # mevcut key korunmuş olmalı (dahili doğrulama; response'ta yok)
    key, url = ac.load_credentials()
    assert key == "KEEPME"
    assert url == "https://new/openai/v1/"


def test_validation_error_does_not_echo_api_key(client):
    # 500 karakter sınırını aşan key → pydantic doğrulama hatası; key gövdede yankılanmamalı
    secret = "S3CRET" + "x" * 600
    r = client.post("/api/settings", json={"api_key": secret, "base_url": "https://x/"})
    assert r.status_code == 422
    assert secret not in r.text
    assert "S3CRET" not in r.text


def test_get_settings_exposes_the_app_version(client):
    """Destek sorusu "hangi sürümdesiniz?" — arayüz bunu buradan okuyor.

    Sürüm azure_client'ın get_settings_status'una DEĞİL, route'a eklendi:
    kimlik bilgisi modülünün uygulama sürümünü bilmesi gereksiz bir bağ olurdu.
    """
    assert client.get("/api/settings").json()["version"] == version.APP_VERSION


def test_post_settings_does_not_claim_a_version(client):
    """Sürüm çalışma anında değişmez → mutasyon ucundan yansıtmak gürültü olur.

    settings.js'teki `if (s && s.version)` guard'ı tam bu yüzden var: aynı
    fonksiyon POST yanıtını da işliyor, guard olmadan "Kaydet"ten sonra sürüm
    satırı silinirdi.
    """
    r = client.post("/api/settings", json={"api_key": "K", "base_url": "https://x/"})
    assert "version" not in r.json()


def test_get_settings_never_returns_key(client):
    client.post("/api/settings", json={
        "api_key": "TOPSECRETKEY", "base_url": "https://ep/openai/v1/"})
    g = client.get("/api/settings")
    assert "TOPSECRETKEY" not in g.text
    assert "api_key" not in g.json()


# ── Prompt Yönetmeni dağıtım adı (v1.13) ───────────────────────────────

def test_chat_deployment_round_trips(client):
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    assert r.status_code == 200
    assert r.json()["chat_deployment"] == "gpt-5.6-luna"
    assert r.json()["chat_configured"] is True

    g = client.get("/api/settings")
    assert g.json()["chat_deployment"] == "gpt-5.6-luna"


def test_saving_only_the_endpoint_keeps_the_chat_deployment(client):
    """REGRESYON: `save_env` birleştirmezse bu test kırmızı olur.

    v1.12'nin `save_credentials`'ı dosyayı sıfırdan iki satır yazıyordu, yani
    "endpoint'i güncelle" eylemi Prompt Yönetmeni'ni sessizce kapatıyordu.
    """
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://old/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={
        "api_key": "", "base_url": "https://new/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})

    assert r.status_code == 200
    assert r.json()["endpoint"] == "https://new/openai/v1/"
    assert r.json()["chat_deployment"] == "gpt-5.6-luna"


def test_a_stale_client_that_omits_the_field_does_not_clear_it(client):
    """Alan HİÇ gönderilmediyse "dokunma" demek; boş dize "temizle" demek.

    İkisi ayrılmazsa `?v=` cache-buster'ını atlatmış bayat bir settings.js,
    kullanıcı endpoint'ini kaydettiği anda Prompt Yönetmeni'ni sessizce kapatır.
    """
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://ep/openai/v1/"})

    assert r.json()["chat_deployment"] == "gpt-5.6-luna"


def test_an_explicit_empty_value_clears_the_chat_deployment(client):
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "gpt-5.6-luna"})
    r = client.post("/api/settings", json={
        "api_key": "", "base_url": "https://ep/openai/v1/", "chat_deployment": ""})

    assert r.json()["chat_deployment"] == ""
    assert r.json()["chat_configured"] is False


def test_chat_deployment_is_not_written_when_the_credentials_are_rejected(client):
    """Görsel kimliği doğrulamadan geçmeden sohbet ayarı yazılmaz."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "ftp://x/", "chat_deployment": "gpt-5.6-luna"})
    assert r.status_code == 422

    assert client.get("/api/settings").json()["chat_deployment"] == ""


def test_settings_expose_where_the_instructions_file_can_be_overridden(client):
    """Ezme yolu keşfedilebilir olmalı: yoksa özellik var ama kimse bulamaz."""
    body = client.get("/api/settings").json()
    assert body["chat_instructions_path"].endswith("chat-instructions.md")


def test_settings_never_leak_a_hand_written_chat_api_key(client, tmp_path, monkeypatch):
    """Ayrı bir sohbet anahtarı ELLE yazılabiliyor; uç onu asla yankılamamalı."""
    envp = tmp_path / "app" / "credentials.env"
    envp.parent.mkdir(parents=True, exist_ok=True)
    envp.write_text("AZURE_IMAGE_API_KEY=K\n"
                    "AZURE_IMAGE_BASE_URL=https://ep/openai/v1/\n"
                    "AZURE_CHAT_API_KEY=CHATTOPSECRET\n"
                    "AZURE_CHAT_DEPLOYMENT=gpt-5.6-luna\n", encoding="utf-8")

    r = client.get("/api/settings")
    assert "CHATTOPSECRET" not in r.text
    assert r.json()["chat_configured"] is True


def test_chat_deployment_with_a_newline_is_rejected(client):
    """Satır sonu dosyaya ikinci bir anahtar enjekte ederdi (save_env guard'ı)."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/",
        "chat_deployment": "d\nAZURE_IMAGE_API_KEY=kotu"})

    assert r.status_code == 422


# ── Doğrulama hatası gövdesi: MEKANİK sızıntı kapısı ───────────────────
#
# Bu blok v0.6'da eklendi ve gerekçesi ölçülmüş bir sızıntı: redaksiyon kapısı
# `loc` içinde birebir `"api_key"` arıyordu, yani `openai_api_key`, `fal_key` ve
# `replicate_api_token` (üçü de v0.2.0'dan beri KABUL EDİLİYOR) kapsam dışıydı.
# 500 karakteri aşan bir değer 422 alıyor ve anahtar `input` alanında istemciye
# aynen dönüyordu.
#
# Test ELLE SAYMIYOR, `SettingsRequest.model_fields` üzerinde dönüyor. Ayrım
# önemli: elle sayılan bir liste tam olarak yukarıdaki üç alanı kaçırmıştı.
# Bundan sonra forma eklenen her alan, eklendiği gün bu testin kapsamına giriyor.


@pytest.mark.parametrize("field", sorted(models.SettingsRequest.model_fields))
def test_dogrulama_hatasi_hicbir_alanin_degerini_yankilamiyor(client, field):
    """Sınırı aşan bir değer 422 döndürüyor ama gövdede GEÇMİYOR.

    `/api/settings` bir kimlik formu: gizli olmayan alanlar (`base_url`,
    `comfyui_url`) da yankılanmıyor. Bu bilinçli — bir alanın "gizli mi"
    olduğunu her seferinde yeniden karara bağlamak, tam olarak üç alanın
    kaçmasına yol açan mekanizmaydı.
    """
    isaret = "SIZINTI-ISARETI-" + "G" * 600      # her alanın max_length'i 500
    r = client.post("/api/settings", json={"api_key": "k",
                                          "base_url": "https://ep/openai/v1/",
                                          field: isaret})

    assert r.status_code == 422, "sınır aşımı 422 dönmeli"
    assert isaret not in r.text, f"{field} değeri doğrulama hatasında sızdı"
    assert "SIZINTI-ISARETI" not in r.text, f"{field} değeri kırpılmış olarak sızdı"


def test_gizli_alan_adi_gizli_OLMAYAN_bir_rotada_da_redakte_ediliyor():
    """İkinci/üçüncü kapı: rota kimlik formu olmasa da ad/sonek yakalıyor.

    `/api/settings` kapısı rotaya bakıyor; ama gizli bir alan bir gün başka bir
    uca taşınırsa (ya da eklenirse) korumanın onunla birlikte gitmesi gerekiyor.
    Burada `app._is_secret_loc` doğrudan ölçülüyor: rota kapısına GÜVENMEDEN.
    """
    assert appmod._is_secret_loc(["body", "api_key"])
    assert appmod._is_secret_loc(["body", "openai_api_key"])
    assert appmod._is_secret_loc(["body", "fal_key"])
    assert appmod._is_secret_loc(["body", "replicate_api_token"])
    assert appmod._is_secret_loc(["body", "yarin_eklenen_bir_secret"])
    # Gizli OLMAYAN alan redakte EDİLMEMELİ: aşırı sansür teşhisi öldürür ve
    # `prompt`/`size` gibi alanların hatalı değerini görmek kullanıcının tek
    # ipucu (bkz. /api/generate'in 422'leri).
    assert not appmod._is_secret_loc(["body", "prompt"])
    assert not appmod._is_secret_loc(["body", "size"])
    assert not appmod._is_secret_loc(["body", "comfyui_url"])


def test_generate_422_si_hatali_degeri_HALA_gosteriyor(client):
    """Redaksiyonun genelleşmesi gizli olmayan rotaları ETKİLEMEMELİ.

    Kapı rotaya bakıyor ve `/api/generate` o listede değil; kullanıcının
    "hangi boyutu yanlış yazdım" sorusunun cevabı bu gövdede yaşıyor.
    """
    r = client.post("/api/generate", json={"prompt": "kedi", "size": "yok-boyle-boyut",
                                           "quality": "medium", "n": 1})
    assert r.status_code == 422
    assert "yok-boyle-boyut" in r.text, "geçersiz değer teşhis için gövdede kalmalı"


# ── Çoklu sağlayıcı (v0.6) ─────────────────────────────────────────────


def test_azure_YOKKEN_baska_bir_saglayicinin_anahtari_kaydedilebiliyor(client):
    """Çoklu sağlayıcının önündeki en somut engel buydu.

    Kural "ilk kurulumda Azure api_key + base_url ZORUNLU" biçimindeydi, yani
    yalnızca Gemini anahtarı olan kullanıcı HİÇBİR ŞEY kaydedemiyordu — üstelik
    aldığı 422 bambaşka bir sağlayıcıdan söz ediyordu ("İlk kurulumda API key
    gerekli"), yani hata mesajı da yanlış tarafı işaret ediyordu.
    """
    r = client.post("/api/settings",
                    json={"gemini_api_key": "AIzaSyDUMMY1234567890abcdefghij"})

    assert r.status_code == 200, r.text
    assert r.json()["providers"]["gemini"] is True
    # Azure hâlâ yapılandırılmamış olmalı: istek onu hedeflemiyordu.
    assert r.json()["configured"] is False
    assert "AIzaSyDUMMY" not in r.text


def test_azure_hedefli_istek_HALA_iki_alani_da_zorunlu_tutuyor(client):
    """Gevşetme yalnız Azure'u HEDEFLEMEYEN isteğe: kural kaybolmadı, daraldı."""
    r = client.post("/api/settings", json={"api_key": "", "base_url": "https://x/"})
    assert r.status_code == 422
    assert "API key" in r.json()["detail"]


def test_saglayici_anahtari_bos_gelirse_mevcut_KORUNUYOR(client):
    """Yalnızca-yazılır formun kuralı: istemci kayıtlı anahtarı hiç görmüyor,
    o yüzden boş bir kutu "sildim" değil "dokunmadım"dır."""
    client.post("/api/settings", json={"openai_api_key": "sk-proj-KALICI123456"})
    assert client.get("/api/settings").json()["providers"]["openai"] is True

    # İkinci kayıt anahtarı hiç göndermiyor (bayat/kısmi istemci).
    client.post("/api/settings", json={"gemini_api_key": "AIzaSyDUMMY1234567890abcdefghij"})

    body = client.get("/api/settings").json()
    assert body["providers"]["openai"] is True, "boş gönderim anahtarı sildi"
    assert body["providers"]["gemini"] is True


def test_adres_alani_bos_gelirse_varsayilana_donuyor(client):
    """Adres GİZLİ DEĞİL, o yüzden boş "varsayılana dön" demek — gizli
    anahtarların "boş = korunur" kuralının bilinçli tersi."""
    client.post("/api/settings", json={"openai_api_key": "sk-proj-DUMMY1234567890",
                                       "openai_base_url": "https://vekil.ornek/v1"})
    import credstore
    assert credstore.resolve("openai")[1] == "https://vekil.ornek/v1"

    client.post("/api/settings", json={"openai_base_url": ""})

    import catalog
    assert (credstore.resolve("openai")[1]
            == catalog.credential("openai").default_base_url)


def test_ayarlar_hangi_modellerin_var_oldugunu_yayinliyor(client):
    """Arayüz model seçicisini bu listeden kuruyor.

    `configured` TEK türetilmiş alan ve `#go` kapısının girdisi: bugün o karar
    tek bir Azure boolean'ına bağlı ve yalnızca OpenAI'si olan bir kullanıcıda
    ölü bir düğme üretirdi.
    """
    body = client.get("/api/settings").json()

    assert body["default_image_model"]
    ids = [m["id"] for m in body["image_models"]]
    assert body["default_image_model"] in ids
    varsayilan = next(m for m in body["image_models"]
                      if m["id"] == body["default_image_model"])
    assert varsayilan["configured"] is False       # bu kurulumda Azure yok
    # Yetenekler arayüzün seçenek listelerini kurabilmesi için TAM olmalı.
    assert varsayilan["sizes"] and varsayilan["qualities"]
    assert varsayilan["max_n"] >= 1
    assert "supports_edit" in varsayilan and "quality_hidden" in varsayilan


def test_anahtar_kaydedilince_model_kullanilabilir_oluyor(client):
    """Kapının GERÇEKTEN kimliğe bağlı olduğunun kanıtı."""
    def azure_modeli():
        body = client.get("/api/settings").json()
        return next(m for m in body["image_models"]
                    if m["id"] == body["default_image_model"])

    assert azure_modeli()["configured"] is False

    client.post("/api/settings", json={"api_key": "K", "base_url": "https://ep/openai/v1/"})

    assert azure_modeli()["configured"] is True


def test_model_listesi_HICBIR_anahtar_tasimiyor(client):
    """Son dört hane, uzunluk ya da maskelenmiş hâl DE dönmüyor.

    `get_settings_status`'un sözleşmesi "API key'i ASLA döndürmez"; "sadece
    son dört hane" o sözleşmenin öldüğü yerdir.
    """
    client.post("/api/settings", json={
        "api_key": "COKGIZLIAZURE", "base_url": "https://ep/openai/v1/",
        "openai_api_key": "sk-proj-COKGIZLIOPENAI",
        "gemini_api_key": "AIzaSyCOKGIZLIGEMINI1234567890",
        "anthropic_api_key": "sk-ant-COKGIZLIANTHROPIC"})

    g = client.get("/api/settings")
    for gizli in ("COKGIZLIAZURE", "COKGIZLIOPENAI", "COKGIZLIGEMINI",
                  "COKGIZLIANTHROPIC"):
        assert gizli not in g.text, gizli
    # Ama durum bayrakları DOLU olmalı, yoksa arayüz hiçbir şeyi açamaz.
    assert all(g.json()["providers"][p] for p in ("azure_image", "openai",
                                                 "gemini", "anthropic"))


def test_POST_yaniti_da_model_listesini_tasiyor(client):
    """"Kaydet"ten sonra arayüz listeyi YENİDEN çekmek zorunda kalmamalı.

    Ama `version` yine YOK: POST gövdesi bilerek daha dar ve settings.js'in
    `!== undefined` guard'ları tam olarak buna dayanıyor.
    """
    r = client.post("/api/settings", json={"api_key": "K", "base_url": "https://ep/v1/"})

    assert "image_models" in r.json() and "providers" in r.json()
    assert "version" not in r.json()
    assert "guncelleme" not in r.json()


def test_bos_adres_kayitli_endpointi_SILMIYOR(client):
    """Boş `base_url` ile gelen bir kayıt, çalışan Azure kurulumunu bozmamalı.

    ÖLÇÜLEN veri kaybıydı: rota `api_key` ve `base_url`den biri boşken
    `save_credentials`ı bilerek atlayıp mevcut endpoint'i KORUYOR, ama hemen
    ardından gelen adres döngüsü aynı env anahtarını "" ile eziyordu — tek
    istekte biri koruyup öteki siliyordu ve cevap 200'dü.

    İstemci tarafında soyut değil: `saveSettings` `base_url`i KOŞULSUZ
    gönderiyor ve boş-adres kapısı yalnız sağlayıcı "azure" seçiliyken
    kuruluyor. Yani `/api/settings` bir kez okunamayıp endpoint kutusu boş
    kaldıysa, yalnızca OpenAI anahtarını kaydeden kullanıcı Azure kurulumunu
    kaybediyordu.
    """
    client.post("/api/settings", json={
        "api_key": "K1", "base_url": "https://ep/openai/v1/"})

    r = client.post("/api/settings", json={"api_key": "K2", "base_url": ""})

    assert r.status_code == 200, r.text
    assert r.json()["configured"] is True, "endpoint silindi — kurulum koptu"
    assert r.json()["endpoint"] == "https://ep/openai/v1/"
    assert client.get("/api/settings").json()["endpoint"] == "https://ep/openai/v1/"


def test_varsayilani_OLAN_saglayicida_bos_adres_hala_varsayilana_donuyor(client):
    """Üstteki kapı adres alanlarının tamamını dondurmamalı.

    Ayrım kataloğun kendisinden okunuyor: `default_base_url`ü olan kimlikte
    (openai/gemini/anthropic) düşülecek bir varsayılan VAR, o yüzden boş
    gönderim hâlâ "varsayılana dön" demek. Yalnız azure_image'de öyle bir
    varsayılan yok ve boş adres "bağlantıyı kopar" demek olurdu.
    """
    client.post("/api/settings", json={
        "openai_api_key": "sk-K", "openai_base_url": "https://vekil.ornek/v1"})
    assert ac.read_env_values().get("OPENAI_BASE_URL") == "https://vekil.ornek/v1"

    r = client.post("/api/settings", json={"openai_base_url": ""})

    assert r.status_code == 200, r.text
    assert ac.read_env_values().get("OPENAI_BASE_URL") == "", \
        "boş adres varsayılana dönmedi — vekil ayarı silinemez hâle geldi"


# ── Sohbet model kataloğu (v0.7) ───────────────────────────────────────
#
# `#chat-model` şeridi bu alanlardan çiziliyor. Eksik bir alan arayüzde SESSİZ
# bir bozulma demek: `needs_deployment` yoksa dağıtım kutusu hiç görünmez,
# `configured` yoksa her model kurulu sanılır.


def _sohbet(body, model_id):
    return next(m for m in body["chat_models"] if m["id"] == model_id)


def test_sohbet_kataloğu_arayuzun_ihtiyaci_olan_ALANLARI_tasiyor(client):
    """Alan kümesi TAM eşitlikle donmuş: eksik alan sessiz bir bozulma, fazla
    alan ise ölçülmemiş bir sözleşme genişlemesi. `logo` v0.8'de eklendi —
    şeridin sağlayıcı işareti (bkz. tests/test_provider_logos.py); `short_label`
    de onunla birlikte: marka işaretle geldiği için ŞERİDİN adı `label`den ayrı
    (bkz. catalog.short_labels).

    `available` + `requires_plan` üyelik turunda eklendi ve ikisi de ölçülmüş
    bir gerekçeyle: arayüzün görünürlük filtresi TEK alan okumak zorunda
    (`static/core.js secilebilirler`), yoksa kredi/üyelik geldiğinde "hangi
    modeller görünür" sorusunun iki cevabı doğar. Bugünkü eşitliği bir sonraki
    test çiviliyor."""
    body = client.get("/api/settings").json()
    assert body["default_chat_model"] in {m["id"] for m in body["chat_models"]}
    for m in body["chat_models"]:
        assert set(m) == {"id", "label", "short_label", "provider", "configured",
                          "needs_deployment", "note", "logo",
                          "available", "requires_plan"}, m["id"]


def test_iki_katalog_da_SERIT_ADINI_ayri_alanda_donduruyor(client):
    """`label` TAM ad (hata metinleri onu okuyor), `short_label` ŞERİDİN adı.

    İkisi ayrı alan çünkü ayrı işleri var: `#model-note`un "… anahtarı kayıtlı
    değil" cümlesinde marka ayırt edici (katalogda iki `gpt-image-2` var), şerit
    satırındaysa sağlayıcı işaretinin tekrarı. Alanı istemcide türetmek, marka
    adını istemcide literal saymak olurdu.
    """
    body = client.get("/api/settings").json()
    for anahtar in ("image_models", "chat_models"):
        assert body[anahtar], f"{anahtar} boş"
        for m in body[anahtar]:
            assert m["short_label"].strip(), f"{m['id']} şerit adı boş"
            assert len(m["short_label"]) <= len(m["label"]), (
                f"{m['id']}: kısa ad uzun addan uzun olamaz")
    gorsel = {m["id"]: m for m in body["image_models"]}
    # Somut iki uç: markası tekil olan model önekini bırakıyor, katalogda iki
    # kez bulunan ad markasını KORUYOR (bkz. catalog.short_labels).
    assert gorsel["gemini-nano-banana-2"]["short_label"] == "Nano Banana 2"
    assert gorsel["gemini-nano-banana-2"]["label"] == "Gemini · Nano Banana 2"
    assert gorsel["azure-gpt-image-2"]["short_label"] == "Azure · gpt-image-2"


def test_GORUNURLUK_karari_TEK_alandan_geliyor_ve_bugun_configured_ile_ayni(client):
    """Arayüzün görünürlük filtresi TEK alan okuyor: `available`.

    NEDEN AYRI BİR ALAN: bugün bir modelin görünmeme sebebi tek ("anahtar
    kayıtlı değil") ve `available == configured`. Kredi/üyelik sistemi
    geldiğinde ikincisi ekleniyor ("kullanıcının planı kapsamıyor") ve o karar
    SUNUCUDA, `app._model_available`da veriliyor. İstemcide iki sebebi ayrı ayrı
    sormak, "hangi modeller görünür" sorusuna ikinci bir cevap yazmak olurdu —
    `static/core.js secilebilirler`in var olma sebebi tam olarak o ikiliği
    önlemek.

    Bu test alanın SESSİZCE ÖLMESİNİ engelliyor: bugün ikisi eşit olduğu için
    `available`ı silmek hiçbir testi düşürmezdi ve kanca fark edilmeden
    kaybolurdu. Bugünkü eşitlik de burada çivili — ayrıştığı gün bu iddia
    BİLEREK güncellenir, kazara değil.
    """
    body = client.get("/api/settings").json()
    for anahtar in ("image_models", "chat_models"):
        assert body[anahtar], f"{anahtar} boş"
        for m in body[anahtar]:
            assert isinstance(m["available"], bool), m["id"]
            assert m["available"] == m["configured"], (
                f"{m['id']}: bugün görünürlük yalnız anahtara bağlı olmalı")
            # Bugün her model ücretsiz katmanda. Alan şimdiden AKIYOR ki
            # "Pro" rozeti geldiğinde şema değişikliği gerekmesin.
            assert m["requires_plan"] == "free", m["id"]


def test_DAGITIM_ADI_bayragi_yalnizca_ADI_ORTAMDAN_okunan_modelde(client):
    """Ayarlar formundaki dağıtım kutusunun kapısı. Bayrak katalogdan türetiliyor
    (`catalog.chat_needs_deployment`), istemcide sağlayıcı adı sayılmıyor."""
    body = client.get("/api/settings").json()
    assert _sohbet(body, "azure-deployment")["needs_deployment"] is True
    assert _sohbet(body, "gemini-3.7-flash")["needs_deployment"] is False


def test_AZURE_modeli_ANAHTAR_VARKEN_DAGITIM_YOKKEN_kurulu_gorunmuyor(client):
    """Kimliği tam, dağıtımı boş: istek 404 döner. Arayüz "kurulu" gösterirse
    kullanıcı yönetmeni açar, ilk mesaj 502 olur ve sebebi görünmez.

    `providers` (KİMLİK tablosu) bu ayrımı ifade EDEMİYOR — `azure_chat` orada
    `true` olur; `chat_models[].configured` MODEL tablosundan geliyor.
    """
    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ep/openai/v1/"})
    body = client.get("/api/settings").json()

    assert body["providers"]["azure_chat"] is True
    assert _sohbet(body, "azure-deployment")["configured"] is False
    assert body["chat_configured"] is False


def test_YALNIZCA_GEMINI_anahtari_olan_kullanicida_yonetmen_ACIK(client):
    """Ölçütün değiştiği yer. `chat_configured` eskiden yalnız Azure'ı ölçüyordu
    ve tek sağlayıcı varken doğruydu; bugün yalnızca Gemini anahtarı olan bir
    kullanıcıda Prompt Yönetmeni'ni kapalı gösterirdi — yani #chat-gate
    kullanıcıya girmesi gerekmeyen bir Azure alanını işaret ederdi.
    """
    client.post("/api/settings", json={
        "api_key": "", "base_url": "", "gemini_api_key": "AIza-x"})
    body = client.get("/api/settings").json()

    assert body["configured"] is False, "Azure hiç yapılandırılmadı"
    assert body["chat_configured"] is True
    assert _sohbet(body, "gemini-3.7-flash")["configured"] is True
    assert _sohbet(body, "openai-gpt-5.6-terra")["configured"] is False


def test_AZURE_CLIENT_in_kendi_bayragi_DEGISMEDI(client):
    """`ac.get_settings_status()`'in `chat_configured` alanı hâlâ "AZURE sohbeti
    hazır mı" sorusunu cevaplıyor; rota onu bilerek eziyor.

    İkisi karışırsa tests/test_settings.py'deki donmuş sözleşme ile rotanın
    yanıtı aynı adı iki farklı anlamda kullanır ve hangisinin okunduğu
    çağıranın şansına kalır.
    """
    client.post("/api/settings", json={
        "api_key": "", "base_url": "", "gemini_api_key": "AIza-x"})
    assert ac.get_settings_status()["chat_configured"] is False
    assert client.get("/api/settings").json()["chat_configured"] is True


# ── Azure AI Foundry adresi (MAI + FLUX) ───────────────────────────────


def test_foundry_adresi_gidip_geliyor(client):
    """`post_settings`in adres döngüsü KATALOGDAN türetiliyor, elle
    sayılmıyor — yani yeni bir `url_field` rotada kod değişikliği İSTEMİYOR.

    Bu test o sözü ölçüyor: söz tutulmazsa alan sessizce hiç yazılmaz,
    kullanıcı "kaydettim" sanır ve üretim "adres çözülemedi" der.
    """
    import credstore

    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "https://ozel.ornek/foundry"})

    assert r.status_code == 200, r.text
    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"


def test_foundry_adresi_YOKKEN_gorselin_adresinden_turetiliyor(client):
    """Kullanıcı hiçbir şey yazmadan MAI/FLUX çalışmalı: forma yeni bir
    ZORUNLU alan eklemek, bugün Azure'ı kurulu olan herkesi yeniden
    yapılandırmaya zorlamak olurdu."""
    import credstore

    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/"})

    assert credstore.resolve("azure_foundry") == (
        "K", "https://ai-ornek.services.ai.azure.com")


def test_SEMASIZ_foundry_adresi_reddediliyor(client):
    """Adres kapısı (`ac.check_base_url`) katalog döngüsünde duruyor: şemasız
    bir yapıştırma 200 almamalı, hata ilk üretimde "bağlanılamadı" kılığında
    görünmemeli."""
    r = client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "ai-ornek.services.ai.azure.com"})

    assert r.status_code == 422


def test_BOS_foundry_adresi_yazilmis_degeri_KORUYOR(client):
    """`default_base_url`ü olmayan kimlikte boş adres "varsayılana dön" değil
    "dokunmadım" demek (app.post_settings'in ölçülmüş veri kaybı düzeltmesi).

    İstemci alanı KOŞULSUZ gönderiyor, yani bu kural olmasa Foundry adresini
    yazan kullanıcı bir sonraki kayıtta onu kaybederdi.
    """
    import credstore

    client.post("/api/settings", json={
        "api_key": "K", "base_url": "https://ai-ornek.openai.azure.com/openai/v1/",
        "azure_foundry_base_url": "https://ozel.ornek/foundry"})

    client.post("/api/settings", json={"azure_foundry_base_url": ""})

    assert credstore.resolve("azure_foundry")[1] == "https://ozel.ornek/foundry"
