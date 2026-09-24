# Kromis Studio — Copyright (C) 2026 Alperen Zengin (@Zenginby)
# FSL-1.1-ALv2 ile lisanslı. Kaynak: https://github.com/Zenginby/kromis
# Bu bildirim kaldırılamaz (LICENSE); ad ve logo lisans DIŞIDIR (MARKA.md).
#
# Web sürümünün konteyner imajı (Faz 0 / Adım 8, docs/faz0-web-first.md → 8).
#
#   docker build -t kromis .
#   docker run -p 8765:8765 -v kromis-data:/data kromis
#   curl localhost:8765/health
#
# İKİ AŞAMA: birincisi bağımlılıkları bir sanal ortama kurar, ikincisi yalnız
# o ortamı ve kaynağı alır. Kazanç imaj boyutundan çok KATMAN ÖNBELLEĞİ:
# `requirements.txt` değişmediği sürece pip hiç koşmaz, kaynak her commit'te
# değişse de yalnız son `COPY` katmanı yeniden yazılır. pip'in indirme
# artıkları da ilk aşamada kalır.
#
# `python:3.13-slim`: deponun ASGARİ Python'u (requirements-dev.txt'in
# gerekçesi: `os.fchmod` 3.13'te Windows'a geldi — Linux'ta sorun değil ama
# tek bir taban sayısı olsun). `slim`, `alpine` DEĞİL: Pillow, pydantic-core
# ve uvloop manylinux tekerlekleriyle geliyor; musl'da derleyici gerekirdi.
#
# ÇALIŞMA ZAMANI BAĞIMLILIKLARI `requirements.txt`in KENDİSİ — ayrı bir
# `requirements-web.txt` YOK ve bu ölçüldü: dosyadaki web dışı iki paket
# (`pytest`, `pywebview` ve onun `bottle`/`proxy_tools`u) Linux'ta toplam
# ~6 MB; `pythonnet`/`clr-loader` `sys_platform == "win32"` işaretçisiyle
# zaten kurulmuyor. İkinci bir pin listesi + onu birinciyle aynı tutan bir
# bekçi test, 6 MB için fazla. İmaj bir gün gerçekten küçültülmek istenirse
# ilk aday orası.
FROM python:3.13-slim AS bagimliliklar

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt


FROM python:3.13-slim

# HOME=/data, BİLEREK ve HÂLÂ: Faz 1 / 7'ye kadar gerekçe kimlik dosyasıydı
# (`~/.config/kromis/credentials.env`, `POST /api/settings` oraya yazıyordu);
# artık sağlayıcı anahtarları kullanıcı başına ŞİFRELİ olarak DB'de
# (`saglayici_kimlikleri`, services/depo_kimlik_bilgisi.py) ve web yolu o
# dosyayı hiç açmıyor. Satır yine duruyor, gerekçesi ZAYIFLADI ama bitmedi:
# `HOME` konteynerin kendi katmanında kalsa `~`ye yazan her şey (pip/uvicorn
# önbellekleri, `paths.credentials_path`ın dondurulmuş kabuk için hâlâ ürettiği
# yol) konteyner yeniden yaratıldığında yok olur ve yazılamayan bir `~`
# beklenmedik yerlerde 500 üretir. Veri birimine bağlı tek ev dizini, sürpriz
# bırakmıyor. Sağlayıcı anahtarları SÜREÇ ORTAMINDAN OKUNMUYOR — bkz.
# .env.example'daki uyarı; ŞİFRELEME anahtarı ise ortamdan: `KROMIS_SECRET_KEY`
# ZORUNLU, yoksa uygulama açılmaz (app._lifespan, services/sifre.py).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    KROMIS_DATA_DIR=/data \
    HOME=/data \
    PORT=8765

# ROOT DEĞİL: uygulama kullanıcı anahtarı tutuyor ve ağa açık. Konteynerden
# bir kaçış bile olsa root olmaması gerekir. Sabit UID (10001): bind-mount
# edilen bir dizinin sahibini işletmen `chown 10001` ile önceden ayarlayabilsin
# — `/health` yazılamayan dizini 503 ile söyler (routers/saglik.py).
# `--create-home --home-dir /data`: birim dizini imajda bu kullanıcıya ait
# doğuyor; adlandırılmış bir Docker birimi ilk bağlanışta bu sahipliği kopyalar.
RUN useradd --system --uid 10001 --user-group --create-home --home-dir /data kromis

COPY --from=bagimliliklar /opt/venv /opt/venv

WORKDIR /app
# Bağlamın tamamı; imaja girmemesi gerekenler `.dockerignore`da GEREKÇESİYLE.
# Sahibi root, izinleri salt okunur kalıyor: kaynak kullanıcı verisi değil ve
# uygulama `static/`e yazmıyor (`app.py`deki `makedirs(exist_ok=True)` var
# olan dizinde hiçbir şey yapmaz).
COPY . /app

VOLUME /data
EXPOSE 8765
USER kromis

# Sonda `curl` DEĞİL, standart kütüphane: `slim`de curl yok ve onu kurmak
# yalnız bu satır için bir `apt-get` katmanı + ~5 MB demek. `urlopen` 4xx/5xx'te
# istisna fırlatır → sıfır dışı çıkış → "unhealthy"; yani `/health`in 503'ü
# (yazılamayan veri dizini) tam olarak buraya düşer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8765'), timeout=4)"]

# GÖÇ BURADA YOK (Faz 1 / 9, K6): CMD `alembic upgrade head && uvicorn` DEĞİL.
# İki replika aynı anda açılırsa iki `upgrade` yarışır (Alembic kilit tutmaz);
# şema dağıtım ÖNCESİ tek seferlik komutla kurulur — `python tools/goc.py`,
# imajda duruyor (`.dockerignore` `tools/`u içeride bırakıyor). Fly
# `release_command`, Railway/Render pre-deploy, yerelde compose'un `goc`
# servisi (KURULUM.md, docs/isletme.md). "Açılışta göç" bayrağı bilerek yok.
#
# `uvicorn app:app`, `--factory netguard:korumali_app` DEĞİL — `run.sh`in
# aksine. `netguard` masaüstü kabuğunun kapısı: yalnız loopback `Host`
# başlığını ve pencerenin kendi `Origin`ini kabul eder (netguard.py). Bir
# konteynerde her istek bir vekilden ya da başka bir konağın adıyla gelir;
# o kapı burada HER isteği 403'lerdi. Köken/kimlik denetimi web'de Faz 1'in
# konusu (oturum, kiracı) ve o, uygulamanın içinde kurulacak, ASGI sarmalında
# değil. `0.0.0.0`: konteynerin ağ ad alanında loopback dışarıdan görünmez.
# Kabuk biçimi (`sh -c`) `${PORT}`ün genişlemesi için; `exec` uvicorn'un PID
# 1 olması ve SIGTERM'i doğrudan alması için.
#
# `--no-access-log` (Faz 2 / 9): erişim satırını uygulama yazar
# (services/istek_kimligi.py — JSON, `istek_id`, süre, kullanıcı, `X-Request-ID`
# ile eşleşir); uvicorn'unki aynı isteği ikinci kez ve yapısız söylerdi.
# uvicorn'un yaşam döngüsü satırları (`Started server process`) stderr'e düz
# metin gitmeye devam eder; uygulama günlüğü stdout'ta satır başına JSON
# (`KROMIS_GUNLUK_BICIMI`, .env.example).
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8765} --no-access-log"]
