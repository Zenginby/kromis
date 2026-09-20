"""Sağlayıcı meta yan kanalı — `services/saglayici_meta.py` (Faz 3 / 5; docs/faz3-kredi-defteri-filigran.md §5, K8).

Sorular: (i) bağlam yokken `kaydet` no-op — istek yolu ve ~40 `FakeClient`
koşumu hiçbir şey görmez; (ii) `toplayici()` içinde kayıtlar toplanır, `sozluk()`
JSONB biçimi; (iii) iç içe bağlamlar sızmaz, istisnada çözülür; (iv) `maliyet_usd`
`Decimal` toplanır; (v) azure_mai sahte 200 → her isteğin `usage`ı; (vi) fal →
doğrulanmış `request_id`; (vii) `kuyruk.bitir` sütuna REDAKTE yazar (yapı
korunur, `sk-…` ve `api-key` değeri düşer) ve `numeric` USD; (viii) işçi: `_uret`
AYNI iş parçacığında koşar, sahte adaptör bağlamı görür, satıra iner — ve
`services/isci.py` `to_thread`/`ThreadPool` kullanmaz (bağlam kaybolurdu).

Sağlayıcı sahte, çağrı yeri aynen (belge "Test stratejisi"). DB'li testler
GERÇEK Postgres (`depo_db`), tests/test_kuyruk.py ve tests/test_isci.py'nin
fixture deyimiyle.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import inspect
import os
import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

import azure_mai_client
import catalog
import fal_client
import providers
from services import ayar, dosya, isci, kuyruk, saglayici_meta, tablolar

pytestmark = pytest.mark.usefixtures("depo_db")

ISCI = uuid.uuid4()
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(16))
MP4 = b"\x00\x00\x00\x18ftypmp42"
GIZLI = "sk-proj-DUMMY-cok-gizli-anahtar-1234567890"


def _an(saniye: float = 0.0) -> dt.datetime:
    return dt.datetime(2026, 9, 20, 12, 0, 0, tzinfo=dt.UTC) + dt.timedelta(seconds=saniye)


@pytest.fixture(autouse=True)
def _bagram_temiz():
    """Bir önceki testin toplayıcısı sonrakine görünmesin (`kimlik_baglami.sifirla` deseni)."""
    saglayici_meta.sifirla()
    yield
    saglayici_meta.sifirla()


# ── (i)-(iv) yan kanalın kendisi ─────────────────────────────────────────

def test_without_a_collector_kaydet_is_a_silent_no_op():
    assert saglayici_meta.aktif() is None
    assert saglayici_meta.kaydet(usage={"num_output_tokens": 1024}, request_id="abc") is False
    assert saglayici_meta.kaydet() is False
    assert saglayici_meta.aktif() is None, "bağlamsız çağrı bağlam YARATMAZ"


def test_inside_a_collector_every_call_is_kept_in_order_and_dumped_as_jsonb_shape():
    with saglayici_meta.toplayici() as meta:
        assert saglayici_meta.aktif() is meta
        assert saglayici_meta.kaydet(usage={"num_output_tokens": 1024}) is True
        assert saglayici_meta.kaydet(request_id="abc123", usage=None) is True
        assert saglayici_meta.kaydet() is True, "boş çağrı bağlam VARKEN de True — kayıt üretmez"
        assert saglayici_meta.kaydet(usage="1024") is True, "sözlük olmayan `usage` düşer, patlamaz"
    assert saglayici_meta.aktif() is None, "blok çıkışında çözüldü"
    assert meta.kayitlar == [{"usage": {"num_output_tokens": 1024}}, {"request_id": "abc123"}]
    assert meta.sozluk() == {"kayitlar": [{"usage": {"num_output_tokens": 1024}},
                                          {"request_id": "abc123"}], "adet": 2}
    assert meta.maliyet_usd is None, "hiçbir adaptör fiyat vermedi: bilinmiyor, sıfır DEĞİL"
    assert saglayici_meta.Toplayici().sozluk() is None, "hiç kayıt yoksa sütun NULL kalır"


def test_nested_collectors_do_not_leak_and_an_exception_still_resets_the_context():
    with saglayici_meta.toplayici() as dis:
        saglayici_meta.kaydet(request_id="dis1")
        with saglayici_meta.toplayici() as ic:
            saglayici_meta.kaydet(request_id="ic1")
            assert saglayici_meta.aktif() is ic
        assert saglayici_meta.aktif() is dis, "iç blok bitti, dıştaki geri geldi"
        saglayici_meta.kaydet(request_id="dis2")
    assert [k["request_id"] for k in dis.kayitlar] == ["dis1", "dis2"]
    assert [k["request_id"] for k in ic.kayitlar] == ["ic1"]
    with pytest.raises(RuntimeError):
        with saglayici_meta.toplayici():
            saglayici_meta.kaydet(request_id="x")
            raise RuntimeError("sağlayıcı düştü")
    assert saglayici_meta.aktif() is None, "istisnada da çözülür — bir sonraki iş temiz başlar"


def test_the_usd_cost_is_summed_as_decimal_and_echoed_into_the_record_as_text():
    with saglayici_meta.toplayici() as meta:
        saglayici_meta.kaydet(maliyet_usd=0.0389)                 # float → `Decimal(str(...))`
        saglayici_meta.kaydet(maliyet_usd=Decimal("0.0111"), request_id="r2")
        saglayici_meta.kaydet(request_id="r3")                    # fiyatsız kayıt toplamı oynatmaz
    assert meta.maliyet_usd == Decimal("0.0500"), "0.0389 + 0.0111 tam — float yuvarlaması yok"
    assert meta.kayitlar[0] == {"maliyet_usd": "0.0389"}
    assert meta.kayitlar[1] == {"request_id": "r2", "maliyet_usd": "0.0111"}
    assert meta.kayitlar[2] == {"request_id": "r3"}


# ── (v) azure_mai ────────────────────────────────────────────────────────

class _MaiYanit:
    def __init__(self, govde):
        self.status_code = 200
        self._govde = govde

    def json(self):
        return self._govde


class _MaiIstemci:
    def __init__(self, govde):
        self.govde = govde
        self.calls: list[str] = []

    def post(self, url, headers=None, json=None, data=None, files=None, timeout=None):
        self.calls.append(url)
        return _MaiYanit(self.govde)


def test_azure_mai_records_the_usage_block_of_every_request_and_nothing_without_a_context():
    m = catalog.image_model("azure-mai-image-2-6")
    assert m is not None
    govde = {"data": [{"b64_json": base64.b64encode(PNG).decode()}],
             "usage": {"num_output_tokens": 1024, "input_tokens": 12}}
    istemci = _MaiIstemci(govde)
    with saglayici_meta.toplayici() as meta:
        out = azure_mai_client.generate(m, "kedi", "1024x1024", "standard", 2,
                                        client=istemci, credentials=("anahtar", "https://r.services.ai.azure.com"))
    assert out == [PNG, PNG] and len(istemci.calls) == 2, "MAI'de `n` yok: n görsel n istek"
    assert meta.kayitlar == [{"usage": govde["usage"]}] * 2, "her isteğin `usage`ı ayrı kayıt"
    assert meta.maliyet_usd is None, "MAI yanıtla fiyat vermiyor"
    # Bağlam YOKKEN aynı çağrı: baytlar aynı, yan kanal sessiz — mevcut testlerin dünyası.
    assert azure_mai_client.generate(m, "kedi", "1024x1024", "standard", 1, client=_MaiIstemci(govde),
                                     credentials=("anahtar", "https://r.services.ai.azure.com")) == [PNG]
    assert saglayici_meta.aktif() is None
    # `usage` yoksa kayıt da yok (eski gövde şekli).
    with saglayici_meta.toplayici() as bos:
        azure_mai_client.generate(m, "kedi", "1024x1024", "standard", 1, client=_MaiIstemci({"data": govde["data"]}),
                                  credentials=("anahtar", "https://r.services.ai.azure.com"))
    assert bos.kayitlar == [] and bos.sozluk() is None


# ── (vi) fal ─────────────────────────────────────────────────────────────

class _FalYanit:
    def __init__(self, govde=None, content=b""):
        self.status_code = 200
        self._govde = govde
        self.content = content
        self.headers: dict[str, str] = {}

    def json(self):
        if self._govde is None:
            raise ValueError("gövde JSON değil")
        return self._govde


class _FalIstemci:
    def __init__(self, *yanitlar):
        self._yanitlar = list(yanitlar)
        self.calls: list[str] = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append(f"{method} {url}")
        return self._yanitlar[min(len(self.calls) - 1, len(self._yanitlar) - 1)]

    def close(self):
        pass


def test_fal_records_the_validated_request_id_of_the_queue_submit(monkeypatch):
    monkeypatch.setattr(fal_client, "_bekle", lambda s: None)
    wan = catalog.ImageModel(id="fal-wan-3-0", label="wan", provider="fal", wire_model="alibaba/wan-3.0/text-to-video",
                             wire_model_edit="alibaba/wan-3.0/image-to-video", credential="fal",
                             sizes=("16:9",), qualities=("720p",), max_n=1, credits=16, durations=(5,),
                             kind="video", supports_edit=True)
    istemci = _FalIstemci(_FalYanit({"request_id": "abc123", "status_url": "https://evil.example/s"}),
                          _FalYanit({"status": "COMPLETED"}),
                          _FalYanit({"video": {"url": "https://v3.fal.media/x.mp4", "content_type": "video/mp4"}}),
                          _FalYanit(content=MP4))
    with saglayici_meta.toplayici() as meta:
        out = fal_client.generate(wan, "kedi", "16:9", "720p", 5, 1, client=istemci, credentials=("FALKEY", "https://queue.fal.run"))
    assert out == [MP4]
    assert meta.kayitlar == [{"request_id": "abc123"}], "yalnız doğrulanmış id; `status_url` gibi düşmanca alanlar yok"
    assert meta.maliyet_usd is None


# ── (vii) `kuyruk.bitir` redakte yazar ───────────────────────────────────

def test_redaction_keeps_the_structure_and_drops_key_shaped_values_and_key_named_fields():
    ham = {"kayitlar": [{"usage": {"num_output_tokens": 1024, "izi": f"token {GIZLI} sonu"}},
                        {"request_id": "abc123", "headers": {"api-key": "duz-metin-anahtar", "x": "y"},
                         "AZURE_IMAGE_API_KEY": "COKGIZLI"}],
           "adet": 2, "sayi": Decimal("0.5")}
    temiz = kuyruk._redakte(ham)
    assert temiz["adet"] == 2 and temiz["sayi"] == "0.5" and temiz["kayitlar"][1]["request_id"] == "abc123"
    assert temiz["kayitlar"][0]["usage"]["num_output_tokens"] == 1024, "sayılar dokunulmaz"
    assert GIZLI not in repr(temiz) and "[REDACTED_API_KEY]" in temiz["kayitlar"][0]["usage"]["izi"]
    assert temiz["kayitlar"][1]["headers"] == {"api-key": "[REDACTED]", "x": "y"}, "adı anahtar kokan alanın değeri düşer"
    assert temiz["kayitlar"][1]["AZURE_IMAGE_API_KEY"] == "[REDACTED]"
    assert kuyruk._redakte(None) is None


def test_bitir_writes_the_redacted_meta_and_the_decimal_cost_to_the_row(db_oturumu, kullanici):
    is_ = kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "x"}, "m", 8, an=_an())
    db_oturumu.commit()
    assert kuyruk.al(db_oturumu, ISCI, _an(1)) is not None
    meta = {"kayitlar": [{"usage": {"num_output_tokens": 1024}, "request_id": "abc123",
                          "not": f"Authorization: Bearer {GIZLI}"}], "adet": 1}
    assert kuyruk.bitir(db_oturumu, is_.id, {"medya": []}, _an(9), kredi_gercek=6,
                        saglayici_meta=meta, saglayici_maliyet_usd=Decimal("0.038900")) is True
    db_oturumu.commit()
    ham, usd = db_oturumu.execute(text(
        "SELECT saglayici_meta::text, saglayici_maliyet_usd FROM isler WHERE id = :id"), {"id": is_.id}).one()
    # `pg_dump`ın göreceği metin: anahtar yok, yapı ve öteki alanlar yerinde.
    assert GIZLI not in ham and "DUMMY" not in ham and "[REDACTED_API_KEY]" in ham
    assert '"num_output_tokens": 1024' in ham and '"request_id": "abc123"' in ham and '"adet": 1' in ham
    assert usd == Decimal("0.038900"), "`numeric(10,6)`: milyonda bir dolar tam"
    # Kullanıcıya dökülen `_json`da ikisi de YOK (tests/test_kuyruk.py'nin on dört anahtarı).
    dokum = kuyruk.bul(db_oturumu, kullanici.id, is_.id)
    assert dokum is not None and "saglayici_meta" not in dokum and "saglayici_maliyet_usd" not in dokum
    # `bitir` meta'sız (eski çağrı biçimi) → sütunlar NULL.
    is2 = kuyruk.ekle(db_oturumu, kullanici.id, "generate", {"prompt": "x"}, "m", 8, an=_an(20))
    db_oturumu.commit()
    kuyruk.al(db_oturumu, ISCI, _an(21))
    assert kuyruk.bitir(db_oturumu, is2.id, {"medya": []}, _an(29)) is True
    db_oturumu.commit()
    assert db_oturumu.execute(text("SELECT saglayici_meta, saglayici_maliyet_usd FROM isler WHERE id = :id"),
                              {"id": is2.id}).one() == (None, None)


# ── (viii) işçi: aynı iş parçacığı, satıra iner ─────────────────────────

@pytest.fixture
def yerlesim(tmp_path) -> ayar.Ayarlar:
    return dataclasses.replace(ayar.Ayarlar.varsayilan(), data_dir=str(tmp_path),
                               output_dir=os.path.join(str(tmp_path), "output"),
                               assets_dir=os.path.join(str(tmp_path), "assets"))


def test_the_worker_runs_the_adapter_in_its_own_thread_so_the_collector_is_visible_and_lands_in_the_row(
        db_oturumu, kullanici, yerlesim, tmp_path, monkeypatch):
    gorulen: list[tuple[int, saglayici_meta.Toplayici | None]] = []

    def sahte(*a, **k):
        gorulen.append((threading.get_ident(), saglayici_meta.aktif()))
        saglayici_meta.kaydet(usage={"num_output_tokens": 1024}, request_id="abc123")
        return [PNG]

    monkeypatch.setattr(providers, "generate", sahte)
    is_ = kuyruk.ekle(db_oturumu, kullanici.id, "generate",
                      {"prompt": "kedi", "size": "1024x1024", "quality": "medium", "n": 1,
                       "folder_id": None, "session_id": None}, catalog.DEFAULT_IMAGE_MODEL, 999, an=_an())
    db_oturumu.commit()
    assert isci.tek_tur(db_oturumu, dosya.YerelDepo(str(tmp_path)), _an(5), ayarlar=yerlesim, isci_id=ISCI) is True
    (parcacik, aktif), = gorulen
    assert parcacik == threading.get_ident(), "`_uret` çağıranın iş parçacığında — ContextVar ancak böyle görünür"
    assert aktif is not None, "adaptör bağlamı GÖRDÜ: işçi `_uret`i `toplayici()` ile sarıyor"
    assert saglayici_meta.aktif() is None, "iş bitti, bağlam çözüldü"
    db_oturumu.expire_all()
    satir = db_oturumu.get(tablolar.Is, is_.id)
    assert satir is not None and satir.durum == "bitti"
    assert satir.saglayici_meta == {"kayitlar": [{"usage": {"num_output_tokens": 1024}, "request_id": "abc123"}], "adet": 1}
    assert satir.saglayici_maliyet_usd is None, "adaptör fiyat vermedi → bilinmiyor (marj 'bilinen 0/1' der)"


def test_the_worker_module_never_hops_threads_between_collector_and_adapter():
    """Bağlamın bedeli (belge §5 K8): `to_thread`/`ThreadPool`/`run_in_threadpool` bağlamı kopyalamadan
    başka bir iş parçacığına geçerdi ve adaptörün `kaydet`i sessizce no-op olurdu. İşçi mantığı tek parçacık;
    süreç kabuğu (`isci.py`) iş BAŞINA parçacık açar, `kos`un tamamı o parçacıkta."""
    kaynak = inspect.getsource(isci)
    for yasak in ("to_thread", "ThreadPool", "run_in_threadpool", "run_sync"):
        assert yasak not in kaynak, yasak
    # Sarmalama `_uret` çağrısının ETRAFINDA: toplayıcı açılır, `_uret` içinde, `_yaz`a `meta` gider.
    govde = inspect.getsource(isci._kos)
    assert govde.index("saglayici_meta.toplayici()") < govde.index("_uret(is_, depo)") < govde.index("saglayici=meta")


def test_the_first_two_adapters_call_the_side_channel_and_the_rest_do_not_yet():
    """Belge §5: ilk iki adaptör azure_mai (`usage`) ve fal (`request_id`); ötekiler sonra, adaptör adaptör.
    Bu test bugünün haritası — bir adaptör daha açıldığında listeye eklenir."""
    assert "saglayici_meta.kaydet(usage=" in inspect.getsource(azure_mai_client)
    assert "saglayici_meta.kaydet(request_id=rid)" in inspect.getsource(fal_client)
    for ad in ("azure_client", "azure_flux_client", "gemini_client", "openai_client", "veo_client"):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"{ad}.py"),
                  encoding="utf-8") as f:
            assert "saglayici_meta" not in f.read(), f"{ad}: yan kanala bağlandıysa bu listeyi ve belgeyi güncelle"
