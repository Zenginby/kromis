"""Kullanıcı tercihleri deposu (v2.0) — `prefs.json`.

Bu depo neden VAR: otomatik kayıt anahtarı (karar D1'in üçüncü güvencesi) bir
yere yazılmak zorunda ve iki aday da yanlıştı —
  · `credentials.env` bir KİMLİK dosyası (0600, `~/.config`): bir arayüz
    tercihini oraya koymak, anahtarı her tercih değişiminde yeniden yazmak
    demekti (`POST /api/settings` api_key + base_url istiyor);
  · istemci (localStorage) `desktop.py`'nin private mode penceresinde her
    kapanışta siliniyor — `chat_store`'un başındaki ölçülmüş sebep.

Yani tercihler kullanıcının VERİ dizinine, diğer beş manifestin yanına düşüyor;
mekanikler jsonstore'dan (atomik yazım + yazma kilidi) geliyor.
"""
import json
import os

import pytest

import catalog
import models
import prefs


def _read_raw(output_dir) -> dict:
    with open(os.path.join(str(output_dir), prefs.PREFS_FILE), encoding="utf-8") as f:
        return json.load(f)


# ── Varsayılanlar ───────────────────────────────────────────────────────

def test_autosave_is_on_by_default(tmp_path):
    """Karar D1: oturumlar otomatik kaydedilir. Dosya yokken de bu geçerli —
    yeni kurulumda geçmişin boş kalması D1'in tersini uygulamak olurdu."""
    assert prefs.read(str(tmp_path / "yok"))["autosave_sessions"] is True


def test_reading_does_not_create_the_file(tmp_path):
    """Okuma yan etkisiz: uygulama açılışta okuyor, dokunmadan çıkmalı."""
    out = str(tmp_path / "output")
    prefs.read(out)

    assert not os.path.exists(out)


# ── Yazma ───────────────────────────────────────────────────────────────

def test_update_writes_and_returns_the_merged_view(tmp_path):
    out = str(tmp_path / "output")

    merged = prefs.update({"autosave_sessions": False}, out)

    assert merged["autosave_sessions"] is False
    assert _read_raw(out) == {"autosave_sessions": False}
    assert prefs.read(out)["autosave_sessions"] is False


def test_update_with_nothing_to_change_leaves_the_file_alone(tmp_path):
    """Boş güncelleme dosyaya DOKUNMAZ: `chat_store.update`'in duruşunun aynısı."""
    out = str(tmp_path / "output")

    assert prefs.update({}, out)["autosave_sessions"] is True
    assert not os.path.exists(out)


def test_update_keeps_the_other_preferences(tmp_path):
    """Tema (Adım 9) buraya girecek: tek alanı yazmak diğerini düşürmemeli.

    `azure_client.save_env`'in "dosyanın geri kalanını koru" kuralının aynısı ve
    aynı sebep — orada endpoint'i tek başına kaydetmek sohbet dağıtımını sessizce
    silmişti (v1.12 hatası).
    """
    out = str(tmp_path / "output")
    prefs.update({"autosave_sessions": False}, out)
    raw = _read_raw(out)
    raw["theme"] = "amber"                      # elle/ileride yazılmış başka tercih
    prefs._write(out, raw)

    prefs.update({"autosave_sessions": True}, out)

    assert _read_raw(out) == {"autosave_sessions": True, "theme": "amber"}


def test_an_unknown_preference_is_a_loud_error(tmp_path):
    """`extra="forbid"` ethos'u: bilinmeyen anahtar sessizce yazılmaz.

    Sessizce kabul edilse yazım tipo'su "ayar çalışmıyor" olarak görünürdü ve
    dosyada hiç okunmayan bir alan birikirdi.
    """
    out = str(tmp_path / "output")

    try:
        prefs.update({"autosav_sessions": False}, out)
    except ValueError as exc:
        assert "autosav_sessions" in str(exc)
    else:
        raise AssertionError("bilinmeyen tercih sessizce kabul edildi")
    assert not os.path.exists(out)


def test_a_wrong_type_is_a_loud_error(tmp_path):
    out = str(tmp_path / "output")

    try:
        prefs.update({"autosave_sessions": "hayır"}, out)
    except ValueError:
        pass
    else:
        raise AssertionError("bool olmayan değer kabul edildi")


# ── Dayanıklılık (beş depoyla aynı duruş) ───────────────────────────────

def test_corrupt_json_reads_as_defaults_instead_of_crashing(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        f.write("{bu json değil")

    assert prefs.read(out)["autosave_sessions"] is True


def test_a_json_list_instead_of_an_object_reads_as_defaults(tmp_path):
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        json.dump(["yanlış şekil"], f)

    assert prefs.read(out)["autosave_sessions"] is True


def test_a_hand_edited_wrong_type_falls_back_to_the_default(tmp_path):
    """Elle `"false"` yazılmış bir dosya TAHMİN edilmiyor.

    `bool("false")` True'dur: dizeyi bool'a çevirmeye çalışmak kullanıcının
    "kapat" niyetini tam tersine döndürebilirdi. Yazma yolu bunu zaten
    reddediyor, okuma yolu da varsayılana düşüyor.
    """
    out = str(tmp_path / "output")
    os.makedirs(out)
    with open(os.path.join(out, prefs.PREFS_FILE), "w", encoding="utf-8") as f:
        json.dump({"autosave_sessions": "false"}, f)

    assert prefs.read(out)["autosave_sessions"] is True


def test_write_leaves_no_temp_file(tmp_path):
    out = str(tmp_path / "output")

    prefs.update({"autosave_sessions": False}, out)

    assert os.listdir(out) == [prefs.PREFS_FILE]


def test_theme_preference_persistence(tmp_path):
    out = str(tmp_path / "output")
    merged = prefs.update({"theme": "ocean"}, out)
    assert merged["theme"] == "ocean"
    assert prefs.read(out)["theme"] == "ocean"


def test_theme_validation_in_models():
    from models import PrefsRequest, ALLOWED_THEMES
    assert "ocean" in ALLOWED_THEMES
    req = PrefsRequest(theme="ocean")
    assert req.theme == "ocean"
    try:
        PrefsRequest(theme="gecersiz_tema")
    except ValueError as exc:
        assert "geçersiz theme" in str(exc)
    else:
        raise AssertionError("geçersiz theme kabul edildi")


# ── Enum tablosu ve model tercihi (v0.6) ───────────────────────────────


def test_bilinmeyen_enum_DEGERI_okurken_varsayilana_dusuyor(tmp_path):
    """v0.6'ya kadar yalnız TÜR kontrol ediliyordu, DEĞER değil.

    Elle yazılmış `theme: "neon"` `read()`'ten geçip arayüze ulaşıyor ve
    karşılığı olmayan bir CSS sınıfına dönüşüyordu — sessiz ve teşhisi zor.
    Bayat bir `image_model` bundan kesinlikle daha kötü: arayüz var olmayan bir
    modeli seçili gösterir, üretim "bilinmeyen model" der.
    """
    (tmp_path / "prefs.json").write_text(
        json.dumps({"theme": "neon", "image_model": "yok-boyle-model",
                    "chat_provider": "yok"}), encoding="utf-8")

    okunan = prefs.read(str(tmp_path))

    assert okunan["theme"] == "mono"
    assert okunan["image_model"] == catalog.DEFAULT_IMAGE_MODEL
    assert okunan["chat_provider"] == catalog.DEFAULT_CHAT_PROVIDER


def test_bozuk_deger_okurken_diske_YAZILMIYOR(tmp_path):
    """`read()`'in yan etkisiz olma sözü korunuyor (kendi docstring'i).

    Düzeltme bir sonraki `update()`'te kendiliğinden diske iniyor.
    """
    bozuk = {"theme": "neon"}
    (tmp_path / "prefs.json").write_text(json.dumps(bozuk), encoding="utf-8")

    prefs.read(str(tmp_path))

    assert json.loads((tmp_path / "prefs.json").read_text(encoding="utf-8")) == bozuk


def test_yapilandirilmamis_model_secili_KALIYOR(tmp_path, monkeypatch):
    """"Var mı?" katalogdan, "ulaşılabilir mi?" credstore'dan — ayrı sorular.

    Anahtarı girilmemiş bir modeli tercihten DÜŞÜRMEK, kullanıcı Gemini'yi
    seçip anahtarı sonra kaydettiğinde seçimini sessizce Azure'a döndürürdü.

    KİMLİK YOLLARI İZOLE EDİLİYOR ve bu satırlar bedava değil: ilk yazımda
    yoktular ve test, geliştiricinin makinesinde GERÇEK bir
    `~/.config/lumeo/credentials.env` oluştuğu anda düştü (tarayıcıda elle
    doğrulama yapılırken tam bu oldu). O hâliyle iddia "anahtar yokken" değil
    "geliştiricinin makinesinde anahtar yokken" diyordu — conftest.py'nin
    "kaçak damga" guard'larıyla aynı sınıf sızıntı. `DEFAULT_ENV_PATH` de
    kapatılıyor: paylaşılan `claude-tools` dosyası varsa Azure oradan
    yapılandırılmış görünürdü.
    """
    import azure_client as ac
    import credstore

    monkeypatch.setattr(ac, "APP_ENV_PATH", str(tmp_path / "kimlik" / "credentials.env"))
    monkeypatch.setattr(ac, "DEFAULT_ENV_PATH", str(tmp_path / "yok.env"))

    prefs.update({"image_model": catalog.DEFAULT_IMAGE_MODEL}, str(tmp_path))

    spec = catalog.image_model(catalog.DEFAULT_IMAGE_MODEL)
    assert credstore.is_configured(spec.credential) is False
    assert prefs.read(str(tmp_path))["image_model"] == catalog.DEFAULT_IMAGE_MODEL


def test_bilinmeyen_model_YAZILIRKEN_reddediliyor(tmp_path):
    with pytest.raises(ValueError, match="image_model"):
        prefs.update({"image_model": "yok-boyle-model"}, str(tmp_path))


def test_chat_model_SAGLAYICIYA_gore_dogrulaniyor(tmp_path):
    """Çapraz kural: geçerlilik `chat_provider`'a bağlı, yani anahtar-başına
    bir tablo onu ifade edemiyor."""
    gecerli = catalog.chat_models_for(catalog.DEFAULT_CHAT_PROVIDER)[0].id

    prefs.update({"chat_provider": catalog.DEFAULT_CHAT_PROVIDER,
                  "chat_model": gecerli}, str(tmp_path))
    assert prefs.read(str(tmp_path))["chat_model"] == gecerli

    with pytest.raises(ValueError, match="chat_model"):
        prefs.update({"chat_model": "yok-boyle-model"}, str(tmp_path))


def test_chat_model_tek_basina_gonderilirse_saglayici_DISKTEN_okunuyor(tmp_path):
    """İstek yalnız modeli gönderiyorsa sağlayıcı diskteki değerden okunmalı,
    yoksa geçerli bir çift reddedilirdi."""
    prefs.update({"chat_provider": catalog.DEFAULT_CHAT_PROVIDER}, str(tmp_path))
    gecerli = catalog.chat_models_for(catalog.DEFAULT_CHAT_PROVIDER)[0].id

    prefs.update({"chat_model": gecerli}, str(tmp_path))

    assert prefs.read(str(tmp_path))["chat_model"] == gecerli


def test_tema_listesi_models_ten_geliyor_KOPYA_degil():
    """prefs.py tema listesini LİTERAL olarak tekrarlıyordu (models.ALLOWED_THEMES
    varken). Tek örnek kazaydı; ikinci bir enum eklenirken desen olurdu."""
    assert prefs._ENUMS["theme"] is models.ALLOWED_THEMES


def test_SOHBET_modeli_saglayicisiyla_BIRLIKTE_yazilabiliyor(tmp_path):
    """Çoklu sağlayıcının tercih tarafındaki karşılığı.

    `chat_model` ÇAPRAZ bir kural: geçerliliği `chat_provider`'a bağlı. Arayüz
    ikisini TEK çağrıda yazıyor (core.js'teki `#chat-model` dinleyicisi) çünkü
    yalnız modeli göndermek diskteki eski sağlayıcıya karşı doğrulanır ve 422
    döner — yani kullanıcının seçimi sessizce hiç kaydedilmez.
    """
    m = next(m for m in catalog.CHAT_MODELS if m.provider != catalog.DEFAULT_CHAT_PROVIDER)

    with pytest.raises(ValueError) as e:
        prefs.update({"chat_model": m.id}, str(tmp_path))
    assert "geçersiz chat_model" in str(e.value)

    out = prefs.update({"chat_provider": m.provider, "chat_model": m.id},
                       str(tmp_path))
    assert (out["chat_provider"], out["chat_model"]) == (m.provider, m.id)
