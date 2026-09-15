# Kromis Studio

[![Release](https://img.shields.io/badge/version-v0.18.0-blue.svg)](https://github.com/Zenginby/kromis/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
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
> **The interface is Turkish only** — there is no language switch yet, so every
> screenshot below shows Turkish labels. The Prompt Director takes your idea in
> Turkish and writes the image prompt in English; the rest of the UI has not been
> translated. The same is true of the in-repo documentation: this README is the
> English entry point, the deeper documents are Turkish.

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

## ✨ What it does (v0.18.0)

### Say what you want; the Director writes the prompt

Describe the idea in everyday Turkish. The Director turns it into an optimised
English prompt plus the technical settings (size, quality, count), asks you about
anything it had to guess using **clickable options**, and offers variations and
parameter axes. One click sends the prompt you like to generation.

![The Prompt Director: generated prompt, technical settings, variations and parameter axes](docs/gorseller/studyo-yonetmen.png)

### Generate and edit — many models, one strip

Azure OpenAI (`gpt-image-2`), Google Gemini (Nano Banana 2 / Pro), Azure AI
Foundry (MAI-Image, FLUX.2) and OpenAI are all picked from the same strip. Each
model card states in one line what it is good at and shows its credit range, and
the strip lists only providers **whose key you have saved**. In edit (inpainting)
mode you can attach up to three extra reference images beside the main one.

![The model picker on a phone: one card per model with provider mark and credit range](docs/gorseller/mobil-model-secici.png)

### Video from text, or from an image you already made

The composer's third mode is video: all three tiers of Gemini · Veo 3.1 (Lite /
Fast / full) plus three fal.ai models — Alibaba Wan 3.0, PixVerse C1, Kling V3
Turbo Pro. Veo tops out at 8 seconds; PixVerse and Kling can go **up to 15
seconds**. The aspect-ratio axis widened too: all six models now offer **1:1**
alongside 16:9/9:16. Veo shares the image side's key; fal reads its own key
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

Releases need no manual step: merge a PR into `main`, the version is bumped, all
three packages are built, and the release is cut only if every one of them is
green. Details: [docs/yayin-hatti.md](docs/yayin-hatti.md) (Turkish).

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

MIT — see [LICENSE](LICENSE).
