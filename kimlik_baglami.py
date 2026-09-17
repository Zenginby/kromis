# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""İsteğin sağlayıcı kimlikleri — istek başına bir kez çözülen düz sözlüğün bağlamı (Faz 1 / 7).

`services/kimlik.py::kimlik_bilgileri` kullanıcının `saglayici_kimlikleri`
satırlarını DB'den bir kez çözüyor, `request.state.kimlikler`e koyuyor ve
BURAYA bağlıyor; rota dönünce çözüyor. Okuyanlar: `credstore` (açık
`kimlikler` verilmediğinde), `azure_client.generate/edit` ve
`chat_client.complete` (`credentials=None` düşmesi).

NEDEN BİR ContextVar, yalnız `request.state` DEĞİL: sağlayıcı adaptörleri
kimliği TEMBEL çözüyor — `providers._azure_generate`in ölçtüğü 104 testlik
ders: rota testleri `ac.generate`i yamalıyor ve kimliği hiç kurmuyor; sevk
memuru kimliği çağrıdan önce çözse o testlerin hepsi 502 alırdı. Sekiz
adaptörün imzasına bir `kimlikler` parametresi eklemek yerine düşme noktası
(`credentials=None`) isteğin bağlamına bakıyor. Deyim `services/dil.py`nin
aynısı: async bağımlılık isteğin görevinde kurar, senkron rota iş parçacığı
havuzuna bağlamın KOPYASIYLA gider ve değeri görür (anyio `run_sync`).

Hangi rotanın kimlik okuduğu yine İMZASINDA yazılı (`kimlik.KIMLIKLER`
bağımlılığı; bekçisi tests/test_kimlik.py) — bağlam kapı değil, taşıyıcı.
Bağlam YOKSA (`aktif()` → `None`) okuyan taraf "hiçbir şey yapılandırılmamış"
sayar ya da dondurulmuş kabuğun dosyasına düşer; hiçbir yerde başka bir
kullanıcının sözlüğüne düşülmez, çünkü bağlam isteğin kendi görevine ait.

KÖKTE ve YAPRAK (hiçbir şey ithal etmiyor): `azure_client` de `credstore` da
okuyor ve ikisi arasında zaten `credstore → azure_client` kenarı var; bağlam
ikisinden birinde dursa öteki ona döngüyle bağlanırdı.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token

_AKTIF: ContextVar[Mapping[str, str] | None] = ContextVar("kromis_kimlikler", default=None)


def bagla(kimlikler: Mapping[str, str]) -> Token[Mapping[str, str] | None]:
    """İsteğin sözlüğünü bağlar; dönen jeton `coz`a verilir."""
    return _AKTIF.set(kimlikler)


def coz(jeton: Token[Mapping[str, str] | None]) -> None:
    """`bagla`nın geri alınışı — rota döner dönmez, aynı görevde."""
    _AKTIF.reset(jeton)


def aktif() -> Mapping[str, str] | None:
    """Bu isteğin kimlikleri; istek bağlamı yoksa `None`."""
    return _AKTIF.get()


def sifirla() -> None:
    """Bağlamı boşaltır — testler arası sızıntıya karşı (tests/conftest.py)."""
    _AKTIF.set(None)
