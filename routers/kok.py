# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# GNU AGPL-3.0 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (AGPL-3.0 §5a); ad ve logo lisans DIŞIDIR (MARKA.md).
"""Kök sayfa: `index.html`in sürüm ve çeviri yerleştirilmiş hâli.

`/static` mount'u BURADA DEĞİL, `app.py`de: mount bir rota değil bir alt
uygulama ve `include_router` onu taşıyamaz. İki şeyin ayrı yerde durmasının
gerekçesi `app.py`deki mount yorumunda (no-store / önbellek asimetrisi).
"""
from __future__ import annotations

import os
import traceback

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import errlog
import i18n
import paths
import version
from services import dil, yollar

router = APIRouter()


@router.get("/")
def index() -> HTMLResponse:
    """index.html'i sürüm yerine konarak servis eder.

    Neden FileResponse DEĞİL, üç sebep:

    1. `?v=` cache-buster'ı artık version.py'den TÜRETİLİYOR. Şablonda
       `__APP_VERSION__` yer tutucusu duruyor, burada gerçek sürümle
       değiştiriliyor — elle artırılan ikinci bir sürüm literali kalmıyor.

    2. `no-store` şart, süs değil: WKWebView (pywebview) HTML BELGESİNİN
       KENDİSİNİ de önbelleğe alır. Belge bayatlarsa içindeki `?v=` de
       bayatlar ve cache-buster hiçbir işe yaramaz — kullanıcı .app'i
       değiştirse bile eski arayüzü görür. Bu delik paket tarafında bugün
       desktop.py'nin `port=0`'ı sayesinde KAZARA kapalı (her açılış farklı
       origin); `run.sh` tarafında ise CANLI (sabit 8765 + Cache-Control yok
       + frozen'da Last-Modified = build tarihi → sezgisel tazelik penceresi
       günlere çıkabilir). Portu bir gün sabitleme kararı deliği sessizce
       geri getirirdi. `/static`'e bu başlık BİLEREK konmuyor — orada `?v=`
       her sürüme ayrı URL veriyor (bkz. app.py'deki mount açıklaması).

    3. Okuma hatası artık sessiz değil: FileResponse'ın davranışı gönderim
       anında yakalanmayan bir RuntimeError'dı ve --windowed pakette stderr
       olmadığı için kullanıcı boş pencere görür, hata.log'a hiçbir şey
       düşmezdi. HTTPException değil HTMLResponse dönüyor — çalışan çıplak
       JSON görmesin.

    Şablon her istekte diskten okunuyor, BELLEKTE TUTULMUYOR: run.sh ile
    geliştirirken "HTML'i düzenle → yenile → gör" akışı böyle korunuyor.
    """
    dil_kodu = dil.aktif()
    try:
        with open(os.path.join(yollar.static_dir(), "index.html"), encoding="utf-8") as f:
            template = f.read()
    except OSError:
        log_path = errlog.safe_append(paths.data_dir(), traceback.format_exc())
        # `<code>` etiketi BURADA, katalogda DEĞİL: `i18n.render`ın kaçışı
        # çeviri metnine HTML yazılmasını kasten imkânsız kılıyor (bkz. o
        # fonksiyonun docstring'i). Etiket şablon tarafında kalınca çevirmen
        # biçimlendirmeyi bozamıyor.
        kayit = "<code>" + (log_path or "hata.log") + "</code>"
        return HTMLResponse(
            "<h1>" + i18n.t("boot.load_failed.title", dil_kodu) + "</h1>"
            "<p>" + i18n.t("boot.load_failed.body", dil_kodu, log=kayit) + "</p>",
            status_code=500, headers={"Cache-Control": "no-store"})
    # SIRA: önce sabit yer tutucular, EN SON `{{t:…}}`. Ters sırada bir
    # çevirinin içindeki `__APP_VERSION__` benzeri bir dizi de değiştirilirdi
    # — bugün öyle bir çeviri yok ama sıranın bunu imkânsız kılması, o
    # çevirinin bir gün yazılmamasına güvenmekten ucuz.
    sayfa = (template
             .replace("__APP_VERSION__", version.APP_VERSION)
             .replace("__APP_LANG__", dil_kodu)
             .replace("__APP_I18N__", i18n.js_payload(dil_kodu))
             .replace("__APP_LANG_OPTIONS__", i18n.language_options_html(dil_kodu)))
    return HTMLResponse(i18n.render(sayfa, dil_kodu),
                        headers={"Cache-Control": "no-store"})
