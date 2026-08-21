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
