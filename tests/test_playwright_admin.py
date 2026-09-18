# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""E2E — admin `/admin`e girer, üç sekmeyi gezer, bir kullanıcının tavanını yazar; admin olmayan 403 görür (Faz 2 / 8).

Belge §8 çıkış ölçütünün tarayıcı yüzü. Sunucu `tests/test_playwright_studio.py`nin
`ServerThread`i (uvicorn + işçi iş parçacığı), kullanıcılar `e2e_oturum` (gerçek
çerez; admin bayrağı satıra yazılır). Metin çapaları `i18n.t` ile okunur, kopyalanmaz.
"""
from __future__ import annotations

import time

import pytest
from sqlalchemy import select, text

pytest.importorskip("playwright", reason="playwright kurulu değil — E2E testleri atlanıyor")

from playwright.sync_api import sync_playwright

import i18n
from services import kuyruk, tablolar
from tests.test_playwright_studio import ServerThread, get_free_port

pytestmark = pytest.mark.gercek_kimlik


def _admin_yap(oturum) -> None:
    with oturum.db() as db:
        db.execute(text("UPDATE kullanicilar SET is_admin = true WHERE id = :id"), {"id": oturum.kullanici_id})
        db.commit()


def test_the_admin_walks_the_three_tabs_and_sets_a_users_cap_while_a_non_admin_gets_403(veritabani, e2e_oturum):
    port = get_free_port()
    server = ServerThread(port)
    server.start()
    admin = e2e_oturum(dil="tr")
    _admin_yap(admin)
    kullanici = e2e_oturum(dil="en")
    with kullanici.db() as db:
        kuyruk.ekle(db, kullanici.kullanici_id, "generate", {"prompt": "x"}, "m", 3)
        db.commit()
    time.sleep(1.0)
    taban = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(headless=True)
            # 1. Admin olmayan: 403 HTML, isteğin dilinde (hesap dili en).
            baglam = tarayici.new_context()
            page = baglam.new_page()
            kullanici.cerez(page, taban)
            cevap = page.goto(f"{taban}/admin")
            assert cevap is not None and cevap.status == 403
            assert i18n.t("admin.yetki_yok", "en") in page.content()
            baglam.close()

            # 2. Admin: sayfa hesabın dilinde (tr), kullanıcılar sekmesi dolu.
            baglam = tarayici.new_context()
            page = baglam.new_page()
            admin.cerez(page, taban)
            page.goto(f"{taban}/admin")
            page.wait_for_selector("#admin-kullanicilar tr[data-id]")
            assert page.get_attribute("html", "lang") == "tr"
            assert page.inner_text('#admin-sekmeler [data-sekme="kuyruk"]') == i18n.t("admin.sekme_kuyruk", "tr")
            satir = page.locator(f'#admin-kullanicilar tr[data-id="{kullanici.kullanici_id}"]')
            assert satir.count() == 1
            assert kullanici.eposta in satir.inner_text()
            # İşçi iş parçacığı B'nin işini bu arada almış olabilir (bilinmeyen model → `hata`);
            # sütun bir sayı, kesin değeri kuyruğun o anki hâline bağlı.
            assert satir.locator("td").nth(5).inner_text() in ("0", "1"), "aktif iş sütunu sayı"

            # 3. Tavan yaz: kutuya 500, "Yaz" → satır DB'de, mesaj satırı başarı, "Öntanımlıya dön" görünür.
            satir.locator('input[type="number"]').fill("500")
            satir.get_by_role("button", name=i18n.t("admin.tavan_yaz", "tr")).click()
            page.wait_for_function(
                f'document.querySelector("#admin-mesaj").textContent === {i18n.t("admin.tavan_yazildi", "tr")!r}')
            with kullanici.db() as db:
                assert db.scalar(select(tablolar.Kullanici.gunluk_kredi_tavani)
                                 .where(tablolar.Kullanici.id == kullanici.kullanici_id)) == 500
            # `.value` özelliği, `value` özniteliği değil (betik özelliği yazıyor) — CSS seçici görmez.
            page.wait_for_function(
                f'document.querySelector(\'#admin-kullanicilar tr[data-id="{kullanici.kullanici_id}"] input\').value === "500"')
            assert satir.get_by_role("button", name=i18n.t("admin.tavan_sil", "tr")).is_visible()

            # 4. Kuyruk sekmesi: B'nin işi sahibiyle (durumu işçiye bağlı), özet satırı çevrili ve dolu.
            page.click('#admin-sekmeler [data-sekme="kuyruk"]')
            page.wait_for_selector("#admin-isler tr[data-id]")
            assert kullanici.eposta in page.inner_text("#admin-isler")
            ozet = page.inner_text("#admin-kuyruk-ozet")
            assert ozet.startswith(i18n.t("admin.kuyruk_ozet", "tr").split("{")[0]) and "{" not in ozet
            assert page.get_attribute('#admin-sekmeler [data-sekme="kuyruk"]', "aria-selected") == "true"
            assert page.is_hidden("#sekme-kullanicilar")

            # 5. Metrikler sekmesi: altı kart, işçi listesi (E2E sunucusunun işçisi kayıt yazmıyor → "yok" satırı ya da satır).
            page.click('#admin-sekmeler [data-sekme="metrikler"]')
            page.wait_for_selector("#admin-kartlar .admin-kart")
            assert page.locator("#admin-kartlar .admin-kart").count() == 6
            assert page.inner_text("#admin-kartlar").count(i18n.t("admin.metrik_kuyruk", "tr")) == 1
            assert page.locator("#admin-isciler li").count() >= 1
            baglam.close()
            tarayici.close()
    finally:
        server.stop()
