"""Prompt Yönetmeni sistem talimatının yüklenmesi: gömülü varsayılan + kullanıcı ezmesi.

Neden `seed.py` deseni DEĞİL: tohumlama "bir kez kopyala" yapıyor çünkü orada
amaç kullanıcı varlıkları silinse de geri gelmesin. Talimat tam tersi — v1.14'te
iyileştirilen varsayılan, kendi dosyasını özelleştirmemiş HERKESE ulaşmalı. Bu
yüzden gömülü dosya her açılışta yeniden okunuyor, kopyalanmıyor.
"""
import os
import re

import chat_prompt
import paths

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_bundled_default_ships_with_the_repo():
    """Gömülü varsayılan yoksa özellik ilk açılışta ölür (ezme dosyası da yok)."""
    path = os.path.join(paths.bundled_prompts_dir(), chat_prompt.INSTRUCTIONS_FILE)
    assert os.path.isfile(path), path


def test_bundled_default_is_long_enough_to_carry_a_persona():
    """Kırpılmış/boş bir dosya SESSİZCE persona'yı öldürür — uzunluk kapısı o yüzden var."""
    text = chat_prompt.load_instructions()
    assert len(text) >= chat_prompt.MIN_INSTRUCTIONS_CHARS


def test_bundled_default_keeps_the_anchors_the_frontend_parser_needs():
    """chat.js yanıtı `PROMPT` başlığı ve bir ```json fence'i üzerinden ayrıştırıyor.

    Talimat dosyası bir gün "daha okunaklı" bir çıktı formatına çevrilirse
    "Forma aktar" düğmesi SESSİZCE hiçbir şey uygulamaz — ayrıştırıcının
    dayandığı çıpalar bu yüzden testle sabitlendi.
    """
    text = chat_prompt.load_instructions()
    assert "PROMPT" in text, "çıktı formatındaki PROMPT çıpası kaybolmuş"
    assert "```json" in text, "teknik ayarlar json fence'i kaybolmuş"


def test_bundled_default_only_offers_settings_the_app_actually_sends():
    """Uygulamanın göndermediği parametreyi önermek ÖLÜ öneridir.

    `azure_client.build_payload` yalnızca model/prompt/size/quality/n gönderiyor;
    `output_format`, `background`, `input_fidelity`, `stream` önerilirse kullanıcı
    yönetmenin dediğini formda bulamaz. Ayrıca `input_fidelity` gpt-image-2'de
    HİÇ yok (yalnız gpt-image-1/1.5) — olgusal hata olarak da geri gelmemeli.
    """
    text = chat_prompt.load_instructions()
    for dead in ("input_fidelity", "output_format", "partial_images", "output_compression"):
        assert dead not in text, f"uygulamanın göndermediği parametre önerilmiş: {dead}"
    # Yalnızca formun sunduğu üç boyut geçerli (index.html'deki <option> listesi).
    for unsupported in ("3840x2160", "2048x1152", "2560x1024", "1088x1920", "1152x1536"):
        assert unsupported not in text, f"formda olmayan boyut önerilmiş: {unsupported}"


def test_override_wins_over_the_bundled_default(tmp_path, monkeypatch):
    override = tmp_path / "chat-instructions.md"
    override.write_text("Ö" * (chat_prompt.MIN_INSTRUCTIONS_CHARS + 1), encoding="utf-8")
    monkeypatch.setattr(paths, "chat_instructions_override", lambda: str(override))

    assert chat_prompt.load_instructions().startswith("Ö")


def test_short_override_is_skipped_in_favour_of_the_bundled_default(tmp_path, monkeypatch):
    """Yarım kaydedilmiş/boşaltılmış bir ezme dosyası persona'yı düşürmemeli."""
    override = tmp_path / "chat-instructions.md"
    override.write_text("kısa", encoding="utf-8")
    monkeypatch.setattr(paths, "chat_instructions_override", lambda: str(override))

    text = chat_prompt.load_instructions()
    assert len(text) >= chat_prompt.MIN_INSTRUCTIONS_CHARS
    assert "PROMPT" in text, "kısa ezme gömülü varsayılana düşmedi"


def test_missing_everything_raises_a_turkish_value_error(tmp_path, monkeypatch):
    """Düz ValueError — ChatError'a çeviren chat_client (tek yönlü bağımlılık)."""
    monkeypatch.setattr(paths, "chat_instructions_override",
                        lambda: str(tmp_path / "yok.md"))
    monkeypatch.setattr(paths, "bundled_prompts_dir", lambda: str(tmp_path / "yok"))

    try:
        chat_prompt.load_instructions()
    except ValueError as e:
        assert "talimat" in str(e).lower()
    else:
        raise AssertionError("talimat dosyası yokken hata beklenirdi")


def test_candidate_order_puts_the_override_first(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "chat_instructions_override", lambda: "/x/override.md")
    monkeypatch.setattr(paths, "bundled_prompts_dir", lambda: "/x/bundled")

    assert chat_prompt.candidate_paths() == [
        "/x/override.md", os.path.join("/x/bundled", chat_prompt.INSTRUCTIONS_FILE)]


def test_bundled_prompts_are_packaged_by_the_spec():
    """Talimat dosyası pakete girmezse özellik yalnızca .app'te ölür — testle yakalanır.

    `datas` girdisi bütün `bundled/` ağacını taşıyor, yani `bundled/prompts` de
    dahil; burada o girdinin VARLIĞI doğrulanıyor (tests/test_version.py'deki
    metin-üzerinden-spec tekniğinin aynısı: spec'i pytest çalıştıramaz).
    """
    with open(os.path.join(REPO, "gpt-image-studio.spec"), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r"\(\s*'bundled'\s*,\s*'bundled'\s*\)", text), \
        "spec bundled/ ağacını paketlemiyor — talimat dosyası .app'e girmez"


def test_override_path_is_writable_user_data_not_read_only_resources(monkeypatch):
    """Ezme dosyası data_dir()'de olmalı: paket içi resource_dir() salt-okunur.

    Yanlış kökte olsa kullanıcı paketlenmiş .app'te talimatı hiç düzenleyemez
    (ve frozen'da _MEIPASS her açılışta silinir).
    """
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/meipass-test", raising=False)

    override = paths.chat_instructions_override()
    assert override.startswith(paths.data_dir())
    assert not override.startswith(paths.resource_dir())
    assert paths.bundled_prompts_dir() == "/tmp/meipass-test/bundled/prompts"
