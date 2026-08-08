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


def _bundled_text() -> str:
    """GÖMÜLÜ dosyanın metni. `load_instructions()` DEĞİL: içerik testleri repoyu
    doğruluyor, geliştiricinin `data_dir()`'deki kişisel ezme dosyasını değil —
    yoksa kendi personasını yazan biri repo suite'ini kırmış olurdu."""
    path = os.path.join(paths.bundled_prompts_dir(), chat_prompt.INSTRUCTIONS_FILE)
    with open(path, encoding="utf-8") as f:
        return f.read()


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
    "Görsel modunda üret" düğmesi SESSİZCE hiçbir şey uygulamaz — ayrıştırıcının
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


def test_the_persona_teaches_the_clickable_options_contract():
    """v1.15: çiplerin var olma koşulu, personanın `options` bloğu yazması.

    Arayüz tarafı sağlam olsa bile talimat dosyası bu bloğu istemezse yönetmen
    seçenekleri prozada bırakır ve özellik SESSİZCE ölür — kırılma "hata" gibi
    değil "model bugün öyle cevap vermedi" gibi görünür. Bu tripwire persona
    yeniden yazıldığında sözleşmenin düşmesini engelliyor
    (chat_prompt.MIN_INSTRUCTIONS_CHARS ile aynı ruh).
    """
    path = os.path.join(paths.bundled_prompts_dir(), chat_prompt.INSTRUCTIONS_FILE)
    with open(path, encoding="utf-8") as f:
        text = f.read()

    assert "```options" in text, "seçenek bloğu sözleşmesi yok"
    assert '"secenekler"' in text, "arayüzün okuduğu anahtar örneklenmemiş"
    # İstemci bu iki anahtarı da okuyor (chat.js: spec.soru, spec.coklu).
    assert '"soru"' in text and '"coklu"' in text
    # Prompt üretilen yanıtta blok OLMAMALI: aksi halde her yanıtta çip çıkar.
    assert re.search(r"[Ss]oru sormadığın yanıta bu bloğu KOYMA", text), \
        "bloğun NEREDE olmayacağı söylenmemiş"


# ── v1.16: tıklanabilir varyasyon/parametre + kapsam sınırı ─────────────

def test_the_persona_teaches_the_clickable_variation_contract():
    """Varyasyon çiplerinin var olma koşulu, personanın `variations` bloğu yazması.

    Arayüz tarafı sağlam olsa bile bu blok gelmezse panel HİÇ çizilmez ve özellik
    sessizce v1.15'e döner: kullanıcı yine prozadan okuyup prompt'u elle düzenler.
    `istek` alanı ayrıca kritik — uygulama onu kullanıcının bir sonraki MESAJI
    olarak gönderiyor, yani kendi başına anlaşılır olmak zorunda.
    """
    text = _bundled_text()
    assert "```variations" in text, "varyasyon bloğu sözleşmesi yok"
    for key in ('"varyasyonlar"', '"ad"', '"istek"'):
        assert key in text, f"arayüzün okuduğu anahtar örneklenmemiş: {key}"


def test_the_persona_teaches_the_clickable_parameter_contract():
    """`simdi` alanı prompt'ta AYNEN geçen ifade olmak zorunda.

    Geçmezse kullanıcı panelde takas ettiğini sandığı bir ifadeyi görür ama
    prompt'ta o ifade yoktur — yönetmen de deltayı uygulayacak yeri bulamaz.
    """
    text = _bundled_text()
    assert "```parameters" in text, "parametre bloğu sözleşmesi yok"
    for key in ('"eksenler"', '"simdi"', '"secenekler"'):
        assert key in text, f"arayüzün okuduğu anahtar örneklenmemiş: {key}"
    assert "AYNEN geçen" in text, "`simdi`nin prompt'ta birebir bulunma şartı yok"


def test_the_persona_does_not_repeat_the_panels_in_prose():
    """İki liste hem blokta hem prozada yazılırsa yanıt iki katına çıkar.

    Sınır somut: `models.MAX_CHAT_REPLY_CHARS` (12.000) aşıldığında
    `chat_client.extract_content` turu Türkçe bir hatayla düşürüyor. Panel
    başlıklarını arayüz kendisi yazdığı için prozada tekrar GEREKSİZ.
    """
    text = _bundled_text()
    assert "PROZADA TEKRARLAMA" in text, "prozada tekrar yasağı düşmüş"
    # v1.15'in proza varyasyon listesi (`- **A — [isim]:**`) geri gelmemeli.
    assert not re.search(r"^-\s+\*\*[A-C]\s+—", text, re.M), \
        "proza varyasyon listesi geri eklenmiş — blokla birlikte iki kat yanıt"


def test_the_persona_refuses_off_topic_requests_without_drawing_a_form_button():
    """Ret yanıtında kod bloğu KALIRSA arayüz "Görsel modunda üret" düğmesi çizer.

    `parseDirectorReply` prompt'u "JSON olmayan en uzun fence" diye seçiyor: ret
    cümlesinin yanına konan herhangi bir blok prompt sanılır ve `applyToForm` onu
    doğrudan #prompt alanına yazar. Kırılma sessiz — düğme çalışır, yalnızca
    alakasız metni aktarır.
    """
    text = _bundled_text()
    assert "sohbet için değilim" in text, "kapsam reddinin cümlesi kaybolmuş"
    assert re.search(r"[Rr]et yanıtına hiçbir kod bloğu KOYMA", text), \
        "reddin BLOKSUZ olacağı söylenmemiş"


def test_the_scope_gate_keeps_its_valve_against_over_refusal():
    """Kapsam kapısının en olası kırılması FAZLA reddetmek.

    "Bu prompt'u Türkçe açıklar mısın" ya da "görsel neden bulanık çıktı"
    reddedilirse kullanıcı işini yapamaz ve bunu hata olarak da bildirmez —
    "yönetmen bugün huysuz" der. İki valf de silinmemeli: şüphe kuralı ve sınırı
    kelimeye değil hedefe göre çizme kuralı.
    """
    text = _bundled_text()
    assert "Şüphedeyken prompt işi say" in text, "aşırı-ret valfi kaldırılmış"
    assert "kelimeye değil HEDEFE" in text, "hedef-tabanlı sınır kuralı düşmüş"


def test_the_persona_does_not_set_a_minimum_prompt_length():
    """Alt sınır bir DOLGU EMRİdir.

    v1.15'teki "Varsayılan biçim: 60–150 kelime" kuralı, brief'in belirlemediği
    katmanları modele uydurtuyordu: brief 25 kelime belirlediğinde dosya 60 kelime
    sipariş ediyordu. Uygulama sahibinin şikâyeti (her çıktıyı elle kısaltmak)
    doğrudan o satırdan geliyordu. gpt-image-2 için KAYNAKLI bir kelime sınırı
    yok — ne alt ne üst; resmî kılavuz "minimal prompts … can all work well"
    diyor. Bu test uydurma bir sınırın geri sızmasını engelliyor.
    """
    assert not re.search(r"\d+\s*[–-]\s*\d+\s*kelime", _bundled_text()), \
        "prompt uzunluğuna sayısal aralık geri eklenmiş"


def test_the_worked_example_prompt_stays_short_enough_to_imitate():
    """Örnek, çıktı uzunluğunun GERÇEK şartnamesi — kural metninden güçlü.

    Model kuralı okuyup örneği taklit ediyor: v1.15'te örnek prompt 126 kelimeydi
    ve 12 kelimelik bir brief'ten üretilmişti (saksı, palet, altın ışık, cilt
    gözenekleri — hiçbiri brief'te yok). Bütün çıktılar da o boya çıkıyordu.

    Buradaki 60 MODEL HAKKINDA bir iddia değil, bu uygulamanın ev kuralı.
    Desen aynı zamanda `**PROMPT**` satırının fence'in HEMEN üstünde durmasını
    sabitliyor: ayrıştırıcının ilk tercihi o başlık, yoksa "en uzun blok"
    yedeğine düşüyor.
    """
    prompts = re.findall(r"\*\*PROMPT\*\*\s*\n+```[a-z]*\n(.*?)\n```",
                         _bundled_text(), re.S)
    assert prompts, "PROMPT başlığının hemen altında fence'li örnek yok"
    for body in prompts:
        # Şablondaki köşeli parantezli yer tutucu ("[İngilizce prompt — …]")
        # gerçek bir örnek değil; ölçülen şey modelin taklit ettiği metin.
        if body.strip().startswith("["):
            continue
        assert len(body.split()) <= 60, f"örnek prompt {len(body.split())} kelime"


def test_the_persona_repeats_the_whole_prompt_on_iteration_turns():
    """`applyToForm` #prompt alanının ÜSTÜNE yazıyor: fark yeterli değil.

    v1.15'in "prompt'u baştan yazma, sadece ilgili katmanı değiştir" kuralı
    modeli kod bloğuna bir FARK koymaya itiyordu ("… yerine …"). "Görsel modunda
    üret" o farkı prompt sanıp composer'a yazar ve kullanıcı bambaşka bir görsel
    üretir — yine sessiz kırılma.
    """
    assert "prompt'un TAMAMINI" in _bundled_text(), \
        "iterasyonda tam prompt şartı düşmüş"


def test_the_persona_does_not_ship_unsourced_model_claims():
    """Yönetmen bunları kullanıcıya OLGU gibi söylüyor; yanlışsa uygulama yalancı olur.

    Silinen iddialar ve neden: "%95+ metin doğruluğu" (OpenAI böyle bir oran
    yayımlamadı) · "render öncesi akıl yürütme" (model içi mekanizma iddiası,
    doğrulanamaz) · desteklenen dil listesi ve "Türkçe bu listede yok" çıkarımı
    (resmî gpt-image-2 kılavuzunda böyle bir liste HİÇ yok — üstelik uygulamanın
    ANA DİLİ hakkında dayanaksız olumsuz bir iddia) · "2K güvenilirlik sınırı"
    (uydurma sayı; formda 1536'nın üstü zaten yok).

    Kaynak bulunursa iddiayı geri koymak serbest — ama o zaman bu testi de
    kaldırmak gerekir, yani karar BİLİNÇLİ olur.
    """
    text = _bundled_text()
    for claim in ("%95", "render öncesi", "Bengalce", "2K"):
        assert claim not in text, f"kaynaksız iddia geri eklenmiş: {claim}"


def test_the_bundled_default_stays_within_its_budget():
    """Talimat HER turda sistem mesajı olarak gidiyor: her satır kalıcı maliyet.

    Dosya birikimle 9 binden 15,4 bin karaktere çıktı ve kimse fark etmedi —
    koddaki iki yorum hâlâ eski sayıları söylüyordu. v1.16 iki YENİ sözleşme
    ekledi (kapsam/ret + iki makine bloğu), yani dosya bilinçli olarak büyüdü;
    tavan o yüzden 18 bin. Bu bir BÜTÇE: yükseltmek serbest ama gerekçesi commit
    mesajında yazılmak zorunda.

    Tavan neden çalışma zamanında DEĞİL: uzun bir dosyayı kırpmak persona'yı
    sessizce öldürür — tam olarak `MIN_INSTRUCTIONS_CHARS`'ın engellediği kırılma,
    ters yönde.
    """
    text = _bundled_text()
    assert len(text) <= 18000, f"talimat bütçesi aşıldı: {len(text)} karakter"
