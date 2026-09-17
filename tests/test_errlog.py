"""errlog: paketlenmiş uygulamanın tek teşhis çıkışı.

Kullanıcıya stderr hiç görünmediği için bu dosya silinmeden birikir; her
başarısız açılış tam bir traceback ekler. Bu yüzden büyümesi sınırlı olmalı ve
loglamanın kendisi asla asıl uyarının önüne geçmemeli.
"""
import os

import pytest

import errlog


def test_append_writes_timestamped_text(tmp_path):
    path = errlog.append(str(tmp_path), "ilk hata")

    assert path == str(tmp_path / "hata.log")
    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "ilk hata" in body
    assert "---" in body  # zaman damgası ayracı


def test_append_creates_a_missing_directory(tmp_path):
    target = tmp_path / "yok" / "bu-da-yok"

    errlog.append(str(target), "hata")

    assert (target / "hata.log").is_file()


def test_safe_append_never_raises_but_still_returns_the_path(tmp_path):
    """data_dir bir dosyaysa makedirs patlar; safe_append yine de yol döndürmeli.

    Çağıran bu yolu kullanıcıya gösterdiği uyarıya koyuyor — loglama hatası o
    uyarıyı engellememeli (bkz. desktop.main).
    """
    not_a_dir = tmp_path / "dizin-degil"
    not_a_dir.write_text("ben bir dosyayım", encoding="utf-8")

    path = errlog.safe_append(str(not_a_dir), "hata")

    assert path == str(not_a_dir / "hata.log")
    assert not_a_dir.is_file()  # dokunulmadı


def test_log_rotates_when_it_grows_past_the_cap(tmp_path):
    path = errlog.log_path(str(tmp_path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("e" * (errlog.MAX_LOG_BYTES + 1))

    errlog.append(str(tmp_path), "yeni hata")

    assert os.path.isfile(path + ".1")  # önceki içerik kaybolmaz
    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "yeni hata" in body
    assert len(body) < errlog.MAX_LOG_BYTES  # yeni dosya baştan başlar


def test_log_under_the_cap_is_not_rotated(tmp_path):
    errlog.append(str(tmp_path), "birinci")
    errlog.append(str(tmp_path), "ikinci")

    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "birinci" in body and "ikinci" in body
    assert not os.path.exists(errlog.log_path(str(tmp_path)) + ".1")


def test_rotation_keeps_exactly_one_previous_file(tmp_path):
    """İkinci döndürme .1'i ezer — .2, .3 birikmez (disk sınırsız dolmasın)."""
    path = errlog.log_path(str(tmp_path))

    for marker in ("eski", "yeni"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(marker + "e" * errlog.MAX_LOG_BYTES)
        errlog.append(str(tmp_path), "tetikleyici")

    assert not os.path.exists(path + ".2")
    assert open(path + ".1", encoding="utf-8").read().startswith("yeni")


def test_redact_secrets_masks_api_keys(tmp_path):
    text = "Hata: sk-1234567890abcdefghijklmnopqrstuvwxyz ve AZURE_IMAGE_API_KEY='abcdef1234567890abcdef'"
    redacted = errlog.redact_secrets(text)
    assert "sk-1234567890" not in redacted
    assert "[REDACTED_API_KEY]" in redacted

    # append loglamasında da çalışmalı
    path = errlog.append(str(tmp_path), text)
    body = (tmp_path / "hata.log").read_text(encoding="utf-8")
    assert "sk-1234567890" not in body
    assert "[REDACTED_API_KEY]" in body



# ── Sansürleme kapsamı: elle tutulan liste yerine MEKANİK kapı ──────────
#
# Bu blok v0.6'da eklendi, çünkü elle tutulan bir alternasyonun sessizce
# bayatladığı ÖLÇÜLDÜ: `_KEY_PATTERNS`'in 4. deseni sağlayıcı adlarını birebir
# sayıyordu ve `GEMINI_API_KEY=AIza…` hiçbir desene uymuyordu — üstelik
# Google'ın değer biçimi de listede olmadığı için anahtar iki kapıdan birden
# kaçıyor, `hata.log`'a düz metin olarak düşüyordu.
#
# Bundan sonraki koruma kataloğa BAĞLI: bir sağlayıcı `catalog.CREDENTIALS`'a
# girdiği gün aşağıdaki döngü onu da ölçüyor, yani "yeni sağlayıcı ekledim,
# log sansürünü de güncellemeliydim" diye hatırlanacak bir şey kalmıyor.

import catalog


@pytest.mark.parametrize("env_name", sorted(catalog.secret_env_names()))
def test_katalogdaki_her_gizli_env_adi_sansurleniyor(env_name):
    gizli = "COKGIZLIANAHTARDEGERI1234567890"
    redacted = errlog.redact_secrets(f"{env_name}={gizli}")
    assert gizli not in redacted, f"{env_name} değeri sansürlenmedi"


@pytest.mark.parametrize("ornek", [
    # (a) ailesi: DEĞERİN biçimi, anahtar adı olmadan. httpx'in URL'i ya da
    # repr'i traceback'e çıplak bir anahtar bırakabiliyor.
    "AIzaSyDUMMYgoogleKEY_1234567890abcdefghij",   # Google / Gemini
    "sk-ant-api03-DUMMYanthropicKEY1234567890",    # Anthropic
    "sk-proj-DUMMYopenaiKEY1234567890abcd",        # OpenAI
    "fal-DUMMYfalKEY1234567890",                   # fal.ai
    "r8_DUMMYreplicateTOKEN1234",                  # Replicate
])
def test_ciplak_anahtar_bicimleri_sansurleniyor(ornek):
    assert ornek not in errlog.redact_secrets(f"istek başarısız: {ornek}")


@pytest.mark.parametrize("header", [
    "authorization: Bearer DUMMYbearerTOKEN1234567890",
    "api-key: DUMMYazureKEY1234567890",
    "x-api-key: DUMMYanthropicHEADER1234567890",      # Anthropic
    "x-goog-api-key: AIzaSyDUMMY1234567890abcdefghij",  # Gemini
])
def test_baslik_bicimleri_sansurleniyor(header):
    """Anthropic `x-api-key`, Gemini `x-goog-api-key` kullanıyor.

    İkisi de bugün `api-key` alt dizesi sayesinde eşleşiyor; desende AÇIKÇA
    yazılı olmalarının sebebi o tesadüfü sözleşmeye çevirmek.
    """
    redacted = errlog.redact_secrets(header)
    assert "DUMMY" not in redacted and "AIzaSy" not in redacted


def test_sansur_masum_metni_bozmuyor():
    """Aşırı sansürleme de bir hata: traceback teşhis edilemez hale gelir.

    `KEY=ok` gibi kısa değerler ve sıradan Türkçe hata metni geçmeli — desenin
    8 karakter alt sınırı ve BÜYÜK HARF ad kuralı tam bunun için var.
    """
    masum = "Görsel kaydedilemedi: dosya yok (boyut=12), KEY=ok, adres=/output"
    assert errlog.redact_secrets(masum) == masum


# ── SQLAlchemy istisnaları (Faz 1 / 7) ───────────────────────────────────
#
# Bir `IntegrityError`/`DataError` mesajı ifadenin BÜTÜN bağlı parametrelerini
# `[parameters: {...}]` ile taşıyor ve o blok `hata.log`a düşüyor. Değer
# `AD=değer` biçiminde DEĞİL `'AD': 'değer'` biçiminde — 4. desen onu
# görmüyordu; blok bütünüyle düşüyor (c deseni), sözlük biçimi de ayrıca (b').


def test_a_sqlalchemy_error_message_loses_its_bound_parameters():
    from sqlalchemy.exc import IntegrityError

    hata = IntegrityError(
        "INSERT INTO saglayici_kimlikleri (kullanici_id, ad, sifreli_deger) VALUES (%(k)s, %(ad)s, %(d)s)",
        {"k": "a1b2", "ad": "OPENAI_API_KEY", "d": "DUZ-METIN-ANAHTAR-DUMMY-98765"},
        Exception("duplicate key value violates unique constraint"))
    metin = str(hata)
    assert "DUZ-METIN-ANAHTAR-DUMMY-98765" in metin and "[parameters:" in metin, metin
    sansurlu = errlog.redact_secrets(metin)
    assert "DUZ-METIN-ANAHTAR-DUMMY-98765" not in sansurlu
    assert "[parameters:" not in sansurlu, "blok bütünüyle düşmeli, değeri tanımaya çalışmamalı"
    # Teşhis için gereken kısım DURUYOR: hangi ifade, hangi kısıt.
    assert "INSERT INTO saglayici_kimlikleri" in sansurlu
    assert "duplicate key value" in sansurlu


@pytest.mark.parametrize("metin", [
    "{'OPENAI_API_KEY': 'DUMMY-plain-value-12345'}",
    '{"AZURE_IMAGE_API_KEY": "DUMMY-plain-value-12345"}',
    "params={'FAL_KEY': 'DUMMY-plain-value-12345', 'n': 1}",
])
def test_the_dict_form_of_a_secret_name_is_redacted(metin):
    sansurlu = errlog.redact_secrets(metin)
    assert "DUMMY-plain-value-12345" not in sansurlu, sansurlu
    assert "[REDACTED_API_KEY]" in sansurlu


def test_a_dict_with_an_innocent_name_keeps_its_value():
    """Aşırı sansür teşhisi öldürür: `size`/`prompt` gibi alanlar okunur kalmalı."""
    masum = "{'prompt': 'kirmizi kedi', 'size': '1024x1024', 'folder_id': 'abcdef123456'}"
    assert errlog.redact_secrets(masum) == masum
