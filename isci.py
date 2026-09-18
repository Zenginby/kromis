#!/usr/bin/env python3
# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kromis Studio — İŞÇİ SÜRECİ: ikinci bileşim kökü (Faz 2 / 3. görev).

    python isci.py              # ana döngü: al → üret → yaz → bitir, SIGTERM'e kadar
    python isci.py --tek-tur    # bir iş al ve çık (boş kuyrukta 0) — CI `docker` işi

`app.py` web'in girişi nasılsa bu da işçinin: aynı imaj, aynı ortam, başka
komut (`Dockerfile` CMD DEĞİŞMEZ; platform ikinci süreci bu komutla açar —
compose'ta `isci` servisi). Burada yalnız SÜRECİN kurulumu var: kapılar,
motor, işçi satırı, iş parçacıkları, kalp atışı, kapanış. Bir işin nasıl
koştuğu `services/isci.py`de (`kos`/`tek_tur`); testler onu çağırır, bu
dosyayı yalnız iki bayrak testi süreç olarak açar (anahtarsız açılmaz,
`--tek-tur` boş kuyrukta 0).

AÇILIŞ KAPILARI web'inkilerle AYNI ve aynı sırayla (`app._lifespan`):
`DATABASE_URL` yoksa çıkış 2 (işçi DB'siz anlamsız — web'de o "açılır ama
503" idi, burada açılacak bir şey yok); `sifre.dogrula_ortam()` — anahtarsız
işçi AÇILMAZ, çünkü çözeceği satır var (`saglayici_kimlikleri`) ve sessiz
bir varsayılan anahtar şifreli sütunu herkese açardı; `dosya.depo_kur()` —
yarım nesne depolama yapılandırması ithali durdurur (web'deki duruş);
`db.motor_kur(url, pool_size=es_zamanli + 1)` — her iş parçacığı alım/yazım
anında bir bağlantı, kalp kendi bağlantısında, sağlayıcı çağrısı boyunca
hiçbiri (services/isci.py).

DÖNGÜ: `KROMIS_ISCI_ES_ZAMANLI` (öntanımlı 4) iş parçacığı, her biri
`kuyruk.al` → yoksa 1 sn uyu → varsa `kos`. Kalp atışı AYRI iş parçacığında
30 sn'de bir (`isciler.son_kalp` + eldeki işlerin `kalp_atisi` + bayat
düşürme) — sağlayıcı çağrısı adaptörün içinde dakikalarca bloklar, çağıran
iş parçacığı atamaz. Bir iş parçacığında beklenmeyen istisna (DB düştü,
ağ) döngüyü ÖLDÜRMEZ: iz `hata.log`a, 1 sn uyku, devam — ölen bir iş
parçacığı sessizce kapasite düşürürdü.

KAPANIŞ: SIGTERM/SIGINT → almayı bırak, eldeki işleri BİTİR (sağlayıcı
çağrısı faturalandı, yarıda kesmek sonucu çöpe atmak), sonra `isciler`
satırını sil ve çık. Platformun `kill_timeout`ı yetmezse iş `calisiyor`da
kalır ve bayat düşürme onu `hata` yapar (K8; süreler 10. görevde).

GÜNLÜK stdout'a, ASCII, tek satır (`goc.py`nin duruşu): platform günlüğü
okuyor; 9. görev bunu JSON satıra çevirir. Türkçe yorum, ASCII çıktı.

ÇIKIŞ KODLARI öteki araçlarla bir (`tools/goc.py`): 0 tamam · 1 çalışma
zamanı (işçi satırı yazılamadı) · 2 ortam (`DATABASE_URL`/anahtar/depo).
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import traceback
import uuid
from types import FrameType

from sqlalchemy.orm import Session

import errlog
import version
from services import ayar, db, dosya, isci, kuyruk, sifre, zaman

CIKIS_TAMAM = 0
CIKIS_CALISMA = 1
CIKIS_ORTAM = 2


def _yaz(mesaj: str, *, hata: bool = False) -> None:
    print(f"isci: {mesaj}", file=sys.stderr if hata else sys.stdout, flush=True)


class Surec:
    """Süreç durumu: motor, depo, işçi kimliği, eldeki işler, durdurma bayrağı."""

    def __init__(self, motor, depo: dosya.Depo, ayarlar: ayar.Ayarlar, es_zamanli: int,
                 esik, kalp_araligi: float) -> None:
        self.motor = motor
        self.depo = depo
        self.ayarlar = ayarlar
        self.es_zamanli = es_zamanli
        self.esik = esik
        self.kalp_araligi = kalp_araligi
        self.durdur = threading.Event()
        self.isci_id: uuid.UUID | None = None
        # Eldeki işlerin id'leri — kalp atışı bunları `kalp_atisi`yle diri tutar.
        self._eldekiler: set[uuid.UUID] = set()
        self._kilit = threading.Lock()

    # ── kayıt ──

    def kaydol(self) -> uuid.UUID:
        with Session(self.motor) as oturum:
            satir = kuyruk.isci_kaydet(oturum, socket.gethostname(), version.APP_VERSION,
                                       self.es_zamanli, zaman.an())
            oturum.commit()
            self.isci_id = satir.id
        return self.isci_id

    def kaydi_sil(self) -> None:
        if self.isci_id is None:
            return
        with Session(self.motor) as oturum:
            kuyruk.isci_sil(oturum, self.isci_id)
            oturum.commit()

    # ── iş parçacıkları ──

    def _gunluk(self, baslik: str) -> None:
        errlog.safe_append(self.ayarlar.data_dir, f"isci {baslik}:\n{traceback.format_exc()}")
        _yaz(f"{baslik} (iz: hata.log)", hata=True)

    def dongu(self) -> None:
        """Bir iş parçacığının ömrü: durdurma bayrağına kadar al → kos."""
        assert self.isci_id is not None
        motor = self.motor
        while not self.durdur.is_set():
            try:
                with Session(motor) as oturum:
                    is_ = isci.siradakini_al(oturum, self.isci_id, zaman.an())
            except Exception:
                self._gunluk("alim dustu")
                self.durdur.wait(isci.YOKLAMA_ARALIGI_SN)
                continue
            if is_ is None:
                self.durdur.wait(isci.YOKLAMA_ARALIGI_SN)
                continue
            with self._kilit:
                self._eldekiler.add(is_.id)
            _yaz(f"is aldi id={is_.id} tur={is_.tur} model={is_.model}")
            try:
                bitti = isci.kos(is_, lambda: Session(motor), self.depo, self.ayarlar)
                _yaz(f"is {'bitti' if bitti else 'hata'} id={is_.id}")
            except Exception:
                # `kos` kendi istisnalarını yutuyor; buraya varan şey onun dışındaki
                # bir kırılma (ör. `hata.log` yazılamadı). Döngü ölmez.
                self._gunluk(f"is {is_.id} beklenmeyen kirilma")
            finally:
                with self._kilit:
                    self._eldekiler.discard(is_.id)

    def kalp(self) -> None:
        """Kalp atışı iş parçacığı: `kalp_araligi` saniyede bir `isci.kalp_turu`."""
        assert self.isci_id is not None
        while not self.durdur.wait(self.kalp_araligi):
            with self._kilit:
                eldekiler = list(self._eldekiler)
            try:
                with Session(self.motor) as oturum:
                    dusen = isci.kalp_turu(oturum, self.isci_id, eldekiler, zaman.an(), self.esik)
                if dusen:
                    _yaz(f"bayat is dusuruldu: {dusen}")
            except Exception:
                self._gunluk("kalp atisi dustu")

    def eldeki_sayisi(self) -> int:
        with self._kilit:
            return len(self._eldekiler)


def _sinyal_kur(surec: Surec) -> None:
    def _dur(sinyal: int, _cerceve: FrameType | None) -> None:
        if not surec.durdur.is_set():
            _yaz(f"sinyal {sinyal}: yeni is alinmiyor, eldeki {surec.eldeki_sayisi()} is bitirilecek")
        surec.durdur.set()

    signal.signal(signal.SIGTERM, _dur)
    signal.signal(signal.SIGINT, _dur)


def hazirla(*, tek_tur: bool, kalp_araligi: float) -> Surec | int:
    """Kapılar sırayla; hepsi geçerse `Surec`, geçmezse çıkış kodu (mesaj stderr'e)."""
    url = db.baglanti_dizesi()
    if not url:
        _yaz(f"{db.DATABASE_URL_ENV} verilmedi: isci veri tabanisiz calisamaz", hata=True)
        return CIKIS_ORTAM
    ayarlar = ayar.Ayarlar.varsayilan()
    try:
        sifre.dogrula_ortam()
    except sifre.AnahtarHatasi as e:
        errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
        _yaz(str(e), hata=True)
        return CIKIS_ORTAM
    try:
        depo = dosya.depo_kur(ayarlar.data_dir)
    except dosya.YapilandirmaHatasi as e:
        _yaz(str(e), hata=True)
        return CIKIS_ORTAM
    try:
        es_zamanli = 1 if tek_tur else isci.es_zamanli()
        esik = isci.kalp_esigi()
    except ValueError as e:
        _yaz(str(e), hata=True)
        return CIKIS_ORTAM
    motor = db.motor_kur(url, pool_size=es_zamanli + 1)
    return Surec(motor, depo, ayarlar, es_zamanli, esik, kalp_araligi)


def main(argv: list[str]) -> int:
    ayristirici = argparse.ArgumentParser(prog="isci.py", description="Kromis is kuyrugu iscisi")
    ayristirici.add_argument("--tek-tur", action="store_true",
                             help="bir is al, kostur ve cik; bos kuyrukta hemen 0")
    # Testler ve duman için: 30 sn'lik kalp atışını beklemeden gözlemlenebilsin.
    ayristirici.add_argument("--kalp-araligi", type=float, default=isci.KALP_ARALIGI_SN,
                             metavar="SN", help=argparse.SUPPRESS)
    secenekler = ayristirici.parse_args(argv)

    surec = hazirla(tek_tur=secenekler.tek_tur, kalp_araligi=secenekler.kalp_araligi)
    if isinstance(surec, int):
        return surec

    if secenekler.tek_tur:
        try:
            with Session(surec.motor) as oturum:
                kostu = isci.tek_tur(oturum, surec.depo, ayarlar=surec.ayarlar)
        finally:
            surec.motor.dispose()
        _yaz("tek tur: " + ("bir is kostu" if kostu else "kuyruk bos"))
        return CIKIS_TAMAM

    try:
        isci_id = surec.kaydol()
    except Exception as e:
        _yaz(f"isci satiri yazilamadi ({type(e).__name__}): veri tabanina ulasilamiyor "
             f"ya da sema kurulmamis (python tools/goc.py)", hata=True)
        surec.motor.dispose()
        return CIKIS_ORTAM
    _sinyal_kur(surec)
    _yaz(f"basladi id={isci_id} konak={socket.gethostname()} surum={version.APP_VERSION} "
         f"es_zamanli={surec.es_zamanli} depo={surec.depo!r} pid={os.getpid()}")

    parcaciklar = [threading.Thread(target=surec.dongu, name=f"kromis-isci-{i}", daemon=True)
                   for i in range(surec.es_zamanli)]
    kalp = threading.Thread(target=surec.kalp, name="kromis-isci-kalp", daemon=True)
    for p in parcaciklar:
        p.start()
    kalp.start()
    # `join()` süresiz beklerse sinyal işleyici ana iş parçacığında koşamaz;
    # kısa aralıklarla yoklanıyor.
    try:
        while any(p.is_alive() for p in parcaciklar):
            for p in parcaciklar:
                p.join(timeout=0.5)
    finally:
        surec.durdur.set()
        kalp.join(timeout=5)
        try:
            surec.kaydi_sil()
        except Exception:
            _yaz("isci satiri silinemedi (bayat kalir; /health worker_alive bunu gorur)", hata=True)
        surec.motor.dispose()
    _yaz("kapandi")
    return CIKIS_TAMAM


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
