<div align="center">

# Pri-Yandex

### Privacy, not profiling.

**A Chromium-based browser that goes the opposite way from Yandex Browser.**

**English** · [Русский](README-ru.md)

</div>

---

## What is this?

Pri-Yandex is a small, privacy-first browser built on a real Chromium engine
(QtWebEngine — Blink + V8), with a privacy layer that does the work browsers
should be doing by default:

- **No telemetry.** No sync, no background uploads, no profiling.
- **Trackers blocked** — EasyList-style rules, including Yandex's own
  `metrica`, `webvisor`, and `appmetrica`.
- **URLs cleaned** — `utm_*`, `fbclid`, `gclid`, `msclkid`, `yclid` and ~40 other
  tracking parameters stripped from every navigation.
- **Headers hardened** — `Referer` removed, `DNT: 1` and `Sec-GPC: 1` sent.
- **Fingerprint randomized** per page load — WebGL, canvas, audio, fonts,
  hardware profile.
- **Ads blocked** — ~80 ad networks in a dedicated list.
- **Cookies under control** — third-party cookies dropped; optional full cookie lock.
- **Nothing leaves your project folder.** Profile, cache, temp, downloads and
  settings all live next to the binary. Disk `C:` is never written.

> **Pri** = *Privacy*. A fork of Yandex Browser in the *opposite* direction:
> same Chromium base, none of the surveillance.

## Quick start

```bash
git clone https://github.com/YOUR_USER/Pri-Yandex.git
cd Pri-Yandex
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe run.py
```

### Prebuilt binary

Download `Pri-Yandex.exe` from the Releases page (~249 MB — Python, Chromium and
all resources are bundled). Double-click to run.

## Build your own .exe

```bash
venv\Scripts\python.exe -m pip install pyinstaller
venv\Scripts\pyinstaller.exe Pri-Yandex.spec
```

Output: `dist\Pri-Yandex.exe`

## Built-in pages

| Page | What it does |
|---|---|
| `pri://newtab` | Start page — search box, shortcuts, logo |
| `pri://settings` | All settings (appearance, search, protection, privacy) |
| `pri://blocked` | Everything Pri refused to load, grouped by reason |
| `pri://about` | Version and active settings |

## Settings

**Appearance** — light/dark theme, home page.
**Search** — DuckDuckGo, Google, Yandex, Brave, or a custom template.
**Protection** — tracker blocking, ad blocking, third-party script blocking,
cookie-banner hiding, cookie control, URL cleaning, speculative-navigation blocking.
**Privacy & Security** — DNT, GPC, fingerprint protection, permissions (denied by
default), WebRTC leak policy, Safe Browsing, DNS prefetch.

All settings persist to `userdata/config.json`.

## Project layout

```
pri/
  app.py                entry point, profile, injected scripts
  browser.py            main window, tabs, toolbar, blocked panel
  page.py               PriPage (pri:// scheme, JS dialogs, downloads)
  config.py             settings
  paths.py              all paths pinned to the project directory
  js/                   injected anti-fingerprinting / cookie scripts
  ui/theme.py           light + dark palettes
  privacy/
    interceptor.py      QWebEngineUrlRequestInterceptor — the privacy core
    rules.py            EasyList-style rule engine
    urlclean.py         tracking-parameter stripper
    report.py           thread-safe event store
    lists/              tracker + ad blocklists
tests/                  headless verification (privacy, fingerprinting)
assets/                 logo and icon
Pri-Yandex.spec         PyInstaller build spec
```

## How it works

All privacy enforcement happens at the network layer, via a
`QWebEngineUrlRequestInterceptor` installed on the profile. Every request is
inspected before it leaves the browser: matched against domain rules, stripped
of tracking headers, or blocked outright.

Fingerprinting is handled by JavaScript injected at `DocumentCreation` in the
main world, so it runs before any page script can read the real values.

## Honest limitations

- **Not Tor.** Your IP is still visible to sites. Pri anonymizes nothing —
  use a VPN or Tor for that.
- **Domain-level blocking only.** No cosmetic filtering, no script-level
  ad removal (uBlock-grade). Ads served from a site's own domain won't be blocked.
- **Chromium base.** The engine is Google's code. Pri removes telemetry and
  sync, but the foundation remains Chromium.
- **Cross-origin isolation** can't be forced — those are server headers.
- **Some sites break** when blocking is aggressive (Yandex, Ozon, marketplaces).
  Add them to the allowlist if you need them.

## Requirements

- Windows (tested on Windows 10/11)
- Python 3.11+ (developed on 3.14)
- PySide6 6.12

## License

MIT — see [LICENSE](LICENSE).

QtWebEngine is licensed under LGPLv3; this project is MIT and is not affiliated
with or endorsed by Google or Yandex.