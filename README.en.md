# Kromis Studio

[![Release](https://img.shields.io/badge/version-v0.23.1-blue.svg)](https://github.com/Zenginby/kromis/releases/latest)
[![License: FSL-1.1-ALv2](https://img.shields.io/badge/License-FSL--1.1--ALv2-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Build & Test](https://github.com/Zenginby/kromis/actions/workflows/release.yml/badge.svg)](https://github.com/Zenginby/kromis/actions)

**Describe the idea in plain language; the app writes the prompt.** Kromis Studio
brings image and video generation, image editing, colour palettes and brand
overlays (logo / motto / banner) together in a single window. It is the same
program whether you run it as a desktop app or as a local web page on your own
machine.

You bring your own keys, and everything you generate stays on your disk — there
is no server in between.

🇹🇷 [Türkçe](README.md) · 📦 [Installation](KURULUM.md) *(Turkish)* · 📖 [Full feature list](docs/ozellikler.md) *(Turkish)*

> [!NOTE]
> **The interface speaks English out of the box** (the default since v0.22) —
> switch it in Settings → **Dil / Language** (the button is deliberately named
> in both languages so you can find it from either side). The choice is saved
> to disk, so it survives a restart; an installation that already picked a
> language keeps it.
>
> The screenshots below still show the Turkish interface, and the in-repo
> documentation is Turkish: this README is the English entry point, the deeper
> documents are not translated.

![Kromis Studio — a generated image in the studio flow](docs/gorseller/uretim-sonucu.png)

---

## 🚀 Download

| Platform | Architecture | Download |
|---|---|---|
| 🍏 **macOS** | Apple Silicon (M1–M4) | [ZIP / ARM64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-macOS-arm64.zip) |
| 🪟 **Windows** | x64 (Windows 10 / 11) | [ZIP / x64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-windows-x64.zip) |
| 🤖 **Android** | arm64-v8a (Android 8.0+) | [APK / arm64](https://github.com/Zenginby/kromis/releases/latest/download/kromis-android-arm64.apk) |

Every link always points at the **latest release**, so the address does not change
when the version does.

> [!IMPORTANT]
> **The desktop and Android builds are frozen at v0.23.1 (2026-09-16).**
> The packages above stay downloadable and keep working: they are BYOK (your own
> keys), they never talk to a Kromis server, so no server shutdown can break
> them. But no further desktop or Android release will be cut automatically; the
> project is moving **web-first** — a studio that runs in the browser, with
> accounts and credits. Roadmap:
> [docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md](docs/superpowers/specs/2026-08-10-saas-transformation-master-design.md)
> (Turkish); the first steps: [docs/faz0-web-first.md](docs/faz0-web-first.md)
> (Turkish), then database and accounts: [docs/faz1-veritabani-hesaplar.md](docs/faz1-veritabani-hesaplar.md)
> (Turkish), then job queue, platform keys and object storage:
> [docs/faz2-kuyruk-anahtarlar-depolama.md](docs/faz2-kuyruk-anahtarlar-depolama.md)
> (Turkish), then credit ledger, plans and watermark: [docs/faz3-kredi-defteri-filigran.md](docs/faz3-kredi-defteri-filigran.md)
> (Turkish), then payments (Polar), credit packs, account deletion and legal texts (plan):
> [docs/faz4-odeme-abonelik-kvkk.md](docs/faz4-odeme-abonelik-kvkk.md)
> (Turkish). If desktop/Android come back one day, they come back as thin
> shells around the web app.

> [!TIP]
> The Android build is not on Play Store; the APK is sideloaded — and the phone
> runs the FULL app: generation, editing, palettes and overlays all execute in the
> Python runtime on the device. When updating, **install over the old build
> instead of uninstalling it**: the packages are signed with the same key, so your
> data stays in place.
>
> Gatekeeper, SmartScreen and "unknown sources" walkthroughs live in
> [KURULUM.md](KURULUM.md) (Turkish).

---

## ✨ What it does (v0.23.1)

### Say what you want; the Director writes the prompt

Describe the idea in everyday language — **you get an answer in whatever
language you wrote in**; the limit is whichever languages the chat model you
picked as the Director supports. The Director turns it into an optimised
**English** prompt plus the technical settings (size, quality, count), asks you
about anything it had to guess using **clickable options**, and offers
variations and parameter axes. One click sends the prompt you like to
generation.

The prompt being English is not a language preference but a measured behaviour:
image models produce noticeably more faithful results when the same scene is
described in English. Ask for a prompt in another language and the Director will
give you one, with the English version alongside it.

![The Prompt Director: generated prompt, technical settings, variations and parameter axes](docs/gorseller/studyo-yonetmen.png)

### Generate and edit — many models, one strip

Azure OpenAI (`gpt-image-2`), OpenAI (`gpt-image-2`, GPT Image 2.5), Google
Gemini (Nano Banana 2 / Pro), Azure AI Foundry (MAI-Image, FLUX.2) and fal.ai
(Qwen Image, Seedream V4, FLUX.1 schnell) are all picked from the same strip —
13 image models, ordered from the strongest to the cheapest. Each
model card states in one line what it is good at and shows its credit range, and
the strip lists only providers **whose key you have saved**. In edit (inpainting)
mode you can attach up to three extra reference images beside the main one.

![The model picker on a phone: one card per model with provider mark and credit range](docs/gorseller/mobil-model-secici.png)

### Video from text, or from an image you already made

The composer's third mode is video: all three tiers of Gemini · Veo 3.1 (Lite /
Fast / full) plus seven fal.ai models — ByteDance Seedance 2.5, Black Forest
Labs FLUX 3, Kling V3 Turbo Pro / V3 Pro, PixVerse C1, Alibaba Wan 3.0, MiniMax
H3. Veo tops out at 8 seconds; the fal models can go **up to 15 seconds**. The
aspect-ratio axis widened too: the fal models add **1:1** alongside 16:9/9:16. Veo shares the image side's key; fal reads its own key
from Settings — both live in the same composer, no new screen appeared. You
can also turn a gallery image into the first frame of a clip; the record keeps
the link back to its parent.

![Video mode: a four-second clip generated with Veo 3.1 Lite, with player and credit estimate](docs/gorseller/video-modu.png)

> [!WARNING]
> Video generation **takes 1–6 minutes and is synchronous** — closing the tab
> loses the job. Veo has no free tier; **fal.ai is prepaid too** — generation
> won't start until the account has credit. **Known defect (Veo):** when a
> start frame and an end frame are supplied TOGETHER, the request fails with
> `HTTP 400 — "your use case is currently not supported"`
> ([the measurement](docs/ozellikler.md)).

### Folders, search, bulk actions

Every image and video lands in the gallery: nested folders, drag-and-drop moves,
sorting by date or name, instant search over prompt / size / folder name,
multi-select for bulk moves and deletes, and a whole folder can be downloaded as
a ZIP.

![Media view: folder cards and loose images, with a duration badge on the video tile](docs/gorseller/medya-klasorler.png)

### Palettes from colour theory

Pick a theme colour and harmonious palettes (monochrome, analogous, complementary,
analogous + complementary) are derived in OKLCH space and listed with colour
names. The palette you choose is appended to the prompt as colour guidance, and
you can drop a colour you dislike by clicking its chip. An eyedropper picks colour
from anywhere on screen.

![Theme colour and palettes panel: colour picker with four harmony suggestions](docs/gorseller/palet.png)

### Logo, motto and banner overlays

Place a logo, motto or banner from your library on top of a generated image: a
nine-point anchor grid, fine offset, size and shadow — all with live preview.

![Overlay window: live preview, nine-point anchor grid, size and offset controls](docs/gorseller/bindirme.png)

### Your keys, your machine

Keys are stored only on this machine and are **never shown on screen**:
`GET /api/settings` returns no key at all, only "is one saved" flags, and keys
that reach logs or tracebacks are redacted. The local server rejects any request
carrying a foreign `Host` or `Origin`.

![Settings: the saved key is not displayed, only the fact that one exists](docs/gorseller/ayarlar-byok.png)

Four dark themes (Mono · Ocean · Amber · Viola), `prefers-reduced-motion` support
and full-screen sheets on phones are in the box as well.

### Plans and credits (web build)

In the web build a user who generates with the platform's key spends
**credits**; one who brings their own key does not. Three plans (`free` /
`temel` / `pro`): the free plan gets a monthly grant (200 credits by default,
"top up to the grant" — no rollover), its images are watermarked and video
models are locked; paid plans are watermark-free. The estimate is reserved when
a job is queued, confirmed at the real cost when it finishes and the difference
refunded; errors and cancellations refund in full. The balance shows in the
composer line ("this run takes 8 · 192 left") and in Settings → **Credits**;
operators get plan, credit adjustments and a **Margin** table in `/admin`.
Setup and the go-live checklist: [KURULUM.md → Web build, step 10](KURULUM.md#web-sürümü-sunucu-kurulumu)
(Turkish); decision record [docs/faz3-kredi-defteri-filigran.md](docs/faz3-kredi-defteri-filigran.md).
**Payment goes through Polar** (Merchant of Record — card, tax and invoice live
at Polar, we only keep the row its signed webhook writes): credit packs roll
over, the `temel`/`pro` subscription grant does not; account deletion and data
export are in Settings → Account. Setup order and go-live checklist:
[KURULUM.md → Web build, step 11 "Ödeme (Polar)"](KURULUM.md#web-sürümü-sunucu-kurulumu)
(Turkish); decision record [docs/faz4-odeme-abonelik-kvkk.md](docs/faz4-odeme-abonelik-kvkk.md).

The complete list — what works per provider, and the roadmap — is in
**[docs/ozellikler.md](docs/ozellikler.md)** (Turkish).

---

## 💻 Developer guide

Before reading the code, start with
**[docs/graflar/README.md](docs/graflar/README.md)**: modules, HTTP endpoints,
`static/` scripts and the tests touching each module, all generated from source.
The full working agreement is in [CLAUDE.md](CLAUDE.md) (Turkish).

### Requirements

- **Python 3.13+** — mandatory on Windows: `azure_client._atomic_write` calls
  `os.fchmod` to tighten permissions *before* writing the credentials file, and
  that call only reached CPython's Windows build in 3.13. On anything older every
  test that writes credentials fails. (The docs once claimed "3.10+"; that is what
  made 45 tests red.)
- macOS or Windows. Building the Android package also needs JDK 17 + the Android
  SDK (see `android/`).

### Run, test, build

```bash
./run.sh                      # serves http://127.0.0.1:8765
python3 -m pytest tests/ -q   # full suite
./build.sh                    # PyInstaller output into dist/
```

Packaging has been **manual since 2026-09-16**: merging into `main` no longer
bumps the version or builds packages. When needed, Actions → *Yayın* → *Run
workflow* runs the old pipeline unchanged (three packages, one release). Details:
[docs/yayin-hatti.md](docs/yayin-hatti.md) (Turkish). Gates that run on every PR:
pytest (E2E included), the leak scan, `ruff check`, `mypy` (informational for now).

---

## 🕰️ About this repository's history

The repository was **rebuilt with a clean history on 2026-09-11**: traces of a
former organisation were removed from the commit history before the project went
public. All of the code, 47 branches and 38 version tags were carried over; pull
request discussions and older releases stayed in a private archive. In practice
this means `#NN` style PR references in the documents no longer resolve here —
the measurements themselves are written down in those documents, only the links
are dead.

## 📜 License

**FSL-1.1-ALv2** (Functional Source License 1.1, Apache-2.0 Future License) —
see [LICENSE](LICENSE).

The source is open: download it, read it, change it, self-host it for your own
use; use it inside your company, build services on top of it, use it in
commercial work that does not compete with Kromis. The one thing you may not do
is **offer Kromis, or a modified copy of it, to others as a product or hosted
service that competes with Kromis** — what the licence calls a "Competing Use".
Every version becomes **Apache-2.0 two years after its release**; that
conversion is written into the licence itself and is irrevocable. FSL is not an
OSI-approved open source licence: the source is open, the use is restricted.

Whatever you **create with** the app — images and videos — is entirely yours.
The licence covers the code, not its output, and commercial use is unrestricted.

* Copyright, the previous licences (the project was opened under MIT, then
  AGPL-3.0; which versions shipped under which licence is recorded there), what
  "competing use" means and how to report an infringement: [TELIF.md](TELIF.md)
* **The "Kromis" name and logo are NOT covered by the licence.** Forking is
  free; the name is not — with a concrete rename checklist: [MARKA.md](MARKA.md)
* Third-party components and their notices: [NOTICE](NOTICE)

The packages are distributed unsigned; every release publishes the SHA-256 of
each package so you can verify that the file you downloaded really came from
this repository — see [KURULUM.md](KURULUM.md).
