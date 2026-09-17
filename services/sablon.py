# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""HTML sayfa şablonu — `static/*.html`i sürüm, dil ve sözlük yerleştirip servis eder.

Faz 0'a kadar bu iş `routers/kok.py::index`in gövdesindeydi ve tek sayfa
vardı. Faz 1 / 3 ikinci bir sayfa getirdi (`static/giris.html`, `GET /giris`);
router'lar birbirini ithal edemez (routers/__init__.py sözleşmesi), yerleştirme
de iki router'da iki kez yazılmamalı — yani yeri burası. `kok.py`nin
gerekçeleri aynen geçerli ve buraya taşındı:

1. `?v=` cache-buster'ı `version.py`den TÜRETİLİYOR: şablondaki
   `__APP_VERSION__` burada gerçek sürümle değiştiriliyor, elle artırılan
   ikinci bir sürüm literali kalmıyor (bekçisi tests/test_index.py).
2. `no-store` şart, süs değil: WKWebView HTML BELGESİNİN KENDİSİNİ de
   önbelleğe alır; belge bayatlarsa içindeki `?v=` de bayatlar. `/static`e bu
   başlık BİLEREK konmuyor (app.py'deki mount açıklaması).
3. Okuma hatası sessiz değil: `FileResponse` gönderim anında yakalanmayan bir
   `RuntimeError`dı ve --windowed pakette stderr olmadığı için kullanıcı boş
   pencere görür, `hata.log`a hiçbir şey düşmezdi. `HTMLResponse` 500 dönüyor
   — çalışan çıplak JSON görmesin — ve traceback `hata.log`a yazılıyor.

Şablon her istekte diskten okunuyor, BELLEKTE TUTULMUYOR: `run.sh` ile
geliştirirken "HTML'i düzenle → yenile → gör" akışı böyle korunuyor.

YER TUTUCU SIRASI: önce sabitler, EN SON `{{t:…}}`. Ters sırada bir çevirinin
içindeki `__APP_VERSION__` benzeri bir dizi de değiştirilirdi — bugün öyle bir
çeviri yok ama sıranın bunu imkânsız kılması, o çevirinin bir gün
yazılmamasına güvenmekten ucuz. `__APP_LANG_OPTIONS__` yalnız `index.html`de
var; `giris.html`de `replace` boşa döner, zararsız.
"""
from __future__ import annotations

import os
import traceback

from fastapi.responses import HTMLResponse

import errlog
import i18n
import version
from services import ayar, dil


def sayfa(ayarlar: ayar.Ayarlar, dosya: str) -> HTMLResponse:
    """`static/<dosya>`yı isteğin dilinde, sürüm ve sözlük yerleştirilmiş servis eder."""
    dil_kodu = dil.aktif()
    try:
        with open(os.path.join(ayarlar.static_dir, dosya), encoding="utf-8") as f:
            template = f.read()
    except OSError:
        log_path = errlog.safe_append(ayarlar.data_dir, traceback.format_exc())
        # `<code>` etiketi BURADA, katalogda DEĞİL: `i18n.render`ın kaçışı
        # çeviri metnine HTML yazılmasını kasten imkânsız kılıyor (bkz. o
        # fonksiyonun docstring'i). Etiket şablon tarafında kalınca çevirmen
        # biçimlendirmeyi bozamıyor.
        kayit = "<code>" + (log_path or "hata.log") + "</code>"
        return HTMLResponse(
            "<h1>" + i18n.t("boot.load_failed.title", dil_kodu) + "</h1>"
            "<p>" + i18n.t("boot.load_failed.body", dil_kodu, log=kayit) + "</p>",
            status_code=500, headers={"Cache-Control": "no-store"})
    govde = (template
             .replace("__APP_VERSION__", version.APP_VERSION)
             .replace("__APP_LANG__", dil_kodu)
             .replace("__APP_I18N__", i18n.js_payload(dil_kodu))
             .replace("__APP_LANG_OPTIONS__", i18n.language_options_html(dil_kodu)))
    return HTMLResponse(i18n.render(govde, dil_kodu),
                        headers={"Cache-Control": "no-store"})
