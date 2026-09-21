# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Sağlayıcı meta verisinin yan kanalı — `usage`, `request_id`, `maliyet_usd` (Faz 3 / 5, K8).

`kimlik_baglami`nın İKİZİ, ters yönde: o bağlam adaptöre KİMLİK taşır, bu
bağlam adaptörden yukarıya, işçiye VERİ taşır. İşçi `_uret`i sarar —

    with saglayici_meta.toplayici() as meta:
        sonuclar = _uret(is_, depo)
    kuyruk.bitir(…, saglayici_meta=meta.sozluk(), saglayici_maliyet_usd=meta.maliyet_usd)

— adaptörler İSTEĞE BAĞLI `kaydet(usage=…, request_id=…, maliyet_usd=…)` der.
Bağlam yoksa `kaydet` SESSİZ no-op: istek yolu (`routers/uretim.py` adaptörü
artık çağırmıyor ama testleri çağırıyor) ve ~40 test dosyasının `FakeClient`
koşumu hiçbir şey değişmeden geçer.

NEDEN YAN KANAL, İMZA DEĞİŞİMİ DEĞİL (belge §5, K8): `-> list[bytes]` beş
istemci + `providers.py` + işçi + ~40 test dosyasının yamaladığı sözleşme
(Faz 1 / 7'nin 104 testlik dersi). `list[Sonuc]`e çevirmek hepsine dokunur
ve bugün taşınacak veri iki alan. `ContextVar` kimlik bağlamının zaten
kullandığı mekanizma; sağlayıcılar fiyat/usage vermeye başladıkça adaptör
adaptör açılır. Bedeli örtük bağlam: bir iş parçacığına geçilirse kaybolur —
işçi `to_thread` KULLANMIYOR, `kos` tek parçacıkta `_uret`i çağırır
(tests/test_saglayici_meta.py bunu ölçer: sahte adaptör bağlamı görür).

KAYIT LİSTESİ, TEK SÖZLÜK DEĞİL: MAI `n` görsel için `n` istek atar ve her
yanıtın kendi `usage`ı var; fal her turda ayrı `request_id` verir. `kayitlar`
her çağrıyı sırayla tutar, `sozluk()` onu JSONB'ye gidecek biçime koyar.
`maliyet_usd` toplanır (`Decimal`, `numeric(10,6)` sütununa gidecek — float
yuvarlaması olmasın); hiçbir adaptör vermediyse `None` kalır ve rapor o
satırı "bilinmiyor" sayar. BUGÜN hiçbir adaptör `maliyet_usd` vermiyor
(sağlayıcılar yanıtla fiyat söylemiyor); alan hazır, sahip fatura CSV'siyle
ya da bir gün API'yle doldurur.

REDAKSİYON BURADA DEĞİL, YAZAN YERDE (`kuyruk.bitir`; `dusur`un aynı kararı):
bu modül sağlayıcının verdiğini olduğu gibi toplar, sütuna giderken
`errlog.redact_secrets`ten geçer.

YAPRAK: yalnız standart kütüphane. Adaptörler kök modül (`azure_mai_client`,
`fal_client`) ve `services/`den ilk kez ithal ediyorlar; bu modül hiçbir
depo modülünü ithal etmez ki `providers ↔ adaptör` erteli döngüsüne
katılmasın.
"""
from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from decimal import Decimal
from typing import Any

__all__ = ["Toplayici", "toplayici", "kaydet", "aktif", "sifirla"]


@dataclasses.dataclass
class Toplayici:
    """Bir işin (bir `_uret` çağrısının) topladığı sağlayıcı kayıtları."""
    kayitlar: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    maliyet_usd: Decimal | None = None

    def kaydet(self, **alanlar: Any) -> None:
        """Bir sağlayıcı yanıtının alanları; `None` değerler düşer, boş çağrı kayıt üretmez."""
        maliyet = alanlar.pop("maliyet_usd", None)
        if maliyet is not None:
            # `Decimal(str(float))`: 0.0389 → "0.0389" (float'ın ikili kuyruğu değil).
            miktar = maliyet if isinstance(maliyet, Decimal) else Decimal(str(maliyet))
            self.maliyet_usd = miktar if self.maliyet_usd is None else self.maliyet_usd + miktar
            alanlar["maliyet_usd"] = str(miktar)
        kayit = {ad: deger for ad, deger in alanlar.items() if deger is not None}
        if kayit:
            self.kayitlar.append(kayit)

    def sozluk(self) -> dict[str, Any] | None:
        """`isler.saglayici_meta` JSONB'sine gidecek hâl; hiç kayıt yoksa `None` (sütun NULL kalır)."""
        if not self.kayitlar:
            return None
        return {"kayitlar": list(self.kayitlar), "adet": len(self.kayitlar)}


_AKTIF: ContextVar[Toplayici | None] = ContextVar("kromis_saglayici_meta", default=None)


@contextlib.contextmanager
def toplayici() -> Iterator[Toplayici]:
    """`with toplayici() as meta:` — blok boyunca `kaydet` bu nesneye yazar; çıkışta HER yolda çözülür.

    İç içe bloklar birbirini görmez: içteki kendi nesnesini alır, dıştaki
    içtekinin kayıtlarını görmez (jeton `reset`). Kimlik bağlamının `bagla`/`coz`
    çiftinin aynısı, tek sarmalayıcıda.
    """
    meta = Toplayici()
    jeton = _AKTIF.set(meta)
    try:
        yield meta
    finally:
        _AKTIF.reset(jeton)


def kaydet(*, usage: Mapping[str, Any] | None = None, request_id: str | None = None,
           maliyet_usd: Decimal | float | str | None = None, **ek: Any) -> bool:
    """Adaptörün çağrısı: aktif toplayıcıya yazar, bağlam yoksa SESSİZCE `False` döner.

    Üç adlı alan sözleşmenin parçası (`usage` sağlayıcının kendi sözlüğü,
    `request_id` sağlayıcı tarafındaki iş kimliği, `maliyet_usd` yanıtla
    gelen fiyat); `ek` ileride bir adaptörün taşıyacağı başka alan için.
    """
    meta = _AKTIF.get()
    if meta is None:
        return False
    # Sözlük olmayan `usage` (sağlayıcı bir gün sayı ya da dize döndürürse) DÜŞER, patlamaz:
    # yan kanal üretimi hiçbir koşulda düşürmez — adaptör çoktan görseli elde etmiş.
    meta.kaydet(usage=dict(usage) if isinstance(usage, Mapping) else None, request_id=request_id,
                maliyet_usd=maliyet_usd, **ek)
    return True


def aktif() -> Toplayici | None:
    """Bu bağlamın toplayıcısı; `toplayici()` bloğu dışında `None`."""
    return _AKTIF.get()


def sifirla() -> None:
    """Bağlamı boşaltır — testler arası sızıntıya karşı (`kimlik_baglami.sifirla` deseni)."""
    _AKTIF.set(None)
