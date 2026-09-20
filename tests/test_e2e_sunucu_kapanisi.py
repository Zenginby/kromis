"""Test sunucularının KAPANIŞ TAVANI kapıda (2026-09-20).

NEDEN BU DOSYA VAR: `uvicorn.Config(timeout_graceful_shutdown=…)` verilmezse
öntanımlı değer `None`, yani "açık bağlantılar kapanana kadar SONSUZA KADAR
bekle". Bir test sunucusu bu hâlde `stop()` dendiği hâlde ölmeyebilir ve
ölmediğinde bedeli tek bir teste kalmıyor: `tests/conftest.py`nin autouse
`_eski_e2e_sunuculari_kapansin` fixture'ı SONRAKİ HER TESTTE o iş parçacığını
yeniden bekliyor.

İKİ KEZ ÖLÇÜLDÜ, İKİSİNDE DE TAKIM 6 DAKİKADAN 80+ DAKİKAYA ÇIKIP HİÇ BİTMEDİ.
2026-09-19'da sızan `test_playwright_hesap`in sunucusuydu, 2026-09-20'de
`test_playwright_studio`nunki — yani kusur bir dosyaya değil DESENE ait.
py-spy yığını her ikisinde de iki ucu birden gösterdi: fixture'ın `join`i ve
hâlâ `run_forever` koşan uvicorn.

KAPANIŞI TUTAN ŞEY AÇIK SOKET DEĞİL, BİTMEYEN YANIT — bu ayrım ölçüldü ve
önemli, çünkü yanlışı bir testi sessizce geçersiz kılıyordu (aşağıda
`test_a_server_with_an_unfinished_response_still_dies_after_stop`). Ürün
yüzü `isler` panelinin SSE akışı.

İlk koşumda "eş zamanlı iki takım" sanılmıştı; 2026-09-20'de kusur TEK BAŞINA
koşan bir takımda çıkınca o açıklama düştü. Kusur ARALIKLI — bir yarış — ve
aynı gün bir başka tam koşum hiç tetiklemedi. Bu yüzden "bende olmadı" bir
kanıt değil.

KAPI MEKANİK, ELLE LİSTE DEĞİL. Depoda elle tutulan kapsam listelerinin
kusuru kayıtlı (`fal_client.py` v0.23'te, `static/i18n.js` PR #12'de listede
olmadığı için kapıyı hiç görmeden geçti). Burada mekanik ölçüt temiz çalışıyor:
`uvicorn.Config(...)` çağrısı sözdiziminden kesin olarak tanınıyor, o yüzden
muafiyet defteri YOK — yarın eklenecek altıncı sunucu da kapıyı görür.

AST, `grep` DEĞİL: `test_desktop.py`de `config: uvicorn.Config` biçiminde TİP
AÇIKLAMALARI var. Metin araması onları çağrı sanıp yanlış alarm verirdi;
`ast.Call` yalnız gerçek yapıyı görüyor.
"""
from __future__ import annotations

import ast
import asyncio
import pathlib
import socket
import threading
import time

import uvicorn

from tests.conftest import JOIN_TAVANI_SN, KAPANIS_TAVANI_SN

TESTLER = pathlib.Path(__file__).resolve().parent


def _uvicorn_config_cagrilari() -> list[tuple[str, int, ast.Call]]:
    """`tests/` altındaki HER `uvicorn.Config(...)` çağrısı — (dosya, satır, düğüm)."""
    bulunan: list[tuple[str, int, ast.Call]] = []
    for yol in sorted(TESTLER.glob("test_*.py")):
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Call):
                continue
            islev = dugum.func
            if (isinstance(islev, ast.Attribute) and islev.attr == "Config"
                    and isinstance(islev.value, ast.Name) and islev.value.id == "uvicorn"):
                bulunan.append((yol.name, dugum.lineno, dugum))
    return bulunan


def test_the_scan_actually_finds_the_test_servers():
    """Kapının kendi bekçisi: tarama boş küme karşılaştırıyor olmasın.

    Alt sınır GERÇEK bir sayı değil, "hiç yoksa kapı sessizdir" koruması.
    Bu deyim depoda üç yerde daha var (`test_the_scanner_is_not_blind` ailesi);
    sebebi aynı: adı değişen bir çağrı kapıyı kırmızıya değil SESSİZLİĞE
    çevirirse kapı yokmuş gibi olur.
    """
    bulunan = _uvicorn_config_cagrilari()
    assert len(bulunan) >= 4, (
        "tests/ altında neredeyse hiç `uvicorn.Config(...)` görülmedi — "
        f"bulunan: {[(d, s) for d, s, _ in bulunan]}. Çağrı biçimi mi değişti "
        "(`from uvicorn import Config` gibi)? Öyleyse tarama da güncellenmeli.")


def test_every_test_server_sets_a_shutdown_ceiling():
    """Her test sunucusu `timeout_graceful_shutdown` VERMEK ZORUNDA.

    Vermeyeni adıyla ve satırıyla söyler; gerekçe dosyanın başındaki ölçümde.
    """
    tavansiz = [
        f"{dosya}:{satir}"
        for dosya, satir, dugum in _uvicorn_config_cagrilari()
        if not any(a.arg == "timeout_graceful_shutdown" for a in dugum.keywords)
    ]
    assert not tavansiz, (
        "şu test sunucuları `timeout_graceful_shutdown` vermiyor, yani kapanırken "
        f"açık bağlantıyı SONSUZA KADAR bekleyebilir: {tavansiz}. "
        "`tests/conftest.py::KAPANIS_TAVANI_SN` sabitini geçir.")


def test_the_shutdown_ceiling_stays_under_the_join_deadline():
    """Tavan, fixture'ın bekleme süresinden KÜÇÜK olmalı.

    İki sayı ayrı ayrı doğru olup birlikte yanlış olabilir: tavan `join`
    süresine eşit ya da ondan büyükse fixture sunucu ölmeden vazgeçer, iş
    parçacığı yaşamaya devam eder ve her testte yeniden beklenir — onarılan
    kusurun ta kendisi geri gelir. Bu yüzden ilişkinin kendisi sınanıyor,
    sayıların değeri değil.
    """
    assert 0 < KAPANIS_TAVANI_SN < JOIN_TAVANI_SN, (
        f"kapanış tavanı {KAPANIS_TAVANI_SN} sn, fixture'ın beklemesi "
        f"{JOIN_TAVANI_SN} sn — tavan küçük OLMALI, yoksa fixture sunucu "
        "ölmeden vazgeçer ve 10 sn'lik vergi geri gelir")


async def _bitmeyen_akis(scope, receive, send):
    """Hiç bitmeyen bir yanıt — ürünün SSE uçlarının sadeleştirilmiş hâli."""
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/event-stream")]})
    while True:
        await send({"type": "http.response.body", "body": b": ping\n\n", "more_body": True})
        await asyncio.sleep(0.2)


def test_a_server_with_an_unfinished_response_still_dies_after_stop():
    """KUSURU YENİDEN ÜRETEN test — yukarıdaki iki kapı statik, bu davranışsal.

    AST kapısı "parametre geçilmiş mi" diye bakıyor; bu test "parametre İŞE
    YARIYOR mu" diye bakıyor. İkisi ayrı kusuru yakalıyor: biri unutmayı,
    öteki değerin yanlış olmasını (0, çok büyük, ya da uvicorn'un anlamının
    değişmesi).

    KURGUNUN NEDEN TAM BÖYLE OLDUĞU ÖLÇÜLDÜ (2026-09-20). Önce yalnızca AÇIK
    BİR SOKET denendi (yarım HTTP isteği, son boş satır yok): kapanışı HİÇ
    tutmadı, sunucu tavansız da 0,20 sn'de öldü — yani o kurguyla yazılmış
    bir test tavan kaldırılsa bile YEŞİL kalırdı, kapı olmazdı. Tutan şey
    BİTMEYEN YANIT:

        tavan yok -> 8 sn sonra hâlâ yaşıyor (yani sonsuza kadar)
        tavan 1sn -> 1,21 sn'de ölüyor ("Cancel 1 running task(s)")

    Ürün yüzü: `isler` panelinin SSE akışı. Tarayıcı bağlantısı kapanmadan
    sunucuya `stop()` denirse uvicorn o yanıtın bitmesini bekler — 2026-09-19
    ve 2026-09-20'de takımı sürüngene çeviren şey buydu.

    ZAMAN AŞIMI TAVANIN KATI DEĞİL, TAVAN + 4: çarpan olsaydı tavan büyüdükçe
    test gevşerdi; toplamda pay sabit kalıyor ve yavaş makinede yanlış kırmızı
    vermeyecek kadar geniş.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    sunucu = uvicorn.Server(uvicorn.Config(
        _bitmeyen_akis, host="127.0.0.1", port=port, log_level="error", ws="none",
        timeout_graceful_shutdown=KAPANIS_TAVANI_SN))
    is_parcacigi = threading.Thread(target=sunucu.run, daemon=True)
    is_parcacigi.start()
    try:
        son = time.monotonic() + 10
        while time.monotonic() < son and not sunucu.started:
            time.sleep(0.02)
        assert sunucu.started, "sunucu 10 sn içinde açılmadı — bu testin kurgusu kurulamadı"

        asili = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            asili.sendall(b"GET /akis HTTP/1.1\r\nHost: kapanis-testi\r\n\r\n")
            # İlk baytı BEKLEMEK şart: yanıt gerçekten başlamadan `stop()`
            # dersek kurgu kurulmamış olur ve test kusuru ıskalar.
            assert asili.recv(64), "akış hiç başlamadı — kurgu kurulamadı"
            sunucu.should_exit = True
            is_parcacigi.join(timeout=KAPANIS_TAVANI_SN + 4)
            assert not is_parcacigi.is_alive(), (
                f"sunucu bitmeyen bir yanıtla {KAPANIS_TAVANI_SN + 4} sn içinde ÖLMEDİ. "
                "`timeout_graceful_shutdown` ya geçilmiyor ya da artık işlemiyor; "
                "bu hâlde `_eski_e2e_sunuculari_kapansin` sonraki HER teste "
                f"{JOIN_TAVANI_SN} sn ekler")
        finally:
            asili.close()
    finally:
        # Kendi sızıntımızı BIRAKMAYALIM: test düşse bile iş parçacığı ölsün,
        # yoksa onardığımız vergiyi takımın geri kalanına biz yüklemiş oluruz.
        sunucu.force_exit = True
        is_parcacigi.join(timeout=JOIN_TAVANI_SN)
