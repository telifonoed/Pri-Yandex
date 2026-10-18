# Changelog

All notable changes to Pri-Yandex. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.14] — Полигон

### Added
- Per-page-load fingerprint randomization: WebGL vendor/renderer pair, canvas,
  audio (`AnalyserNode`, `AudioBuffer`), font enumeration, hardware profile
  (`hardwareConcurrency`, `deviceMemory`).
- `WEBGL_debug_renderer_info` hidden so raw GPU strings can't be read.
- Optional full cookie lock (`navigator.cookieEnabled = false`, writes blocked,
  store purged).
- Dedicated ad-network blocklist (~80 domains) with its own toggle.
- Separate `Do Not Track` and `Global Privacy Control` toggles.
- Injected scripts moved to `pri/js/` (loadable from source tree and PyInstaller
  bundle).

### Fixed
- WebGL VENDOR/RENDERER returned spoofed-but-constant values, which was itself
  a stable fingerprint. Now randomized per page load.
- Vendor and renderer were selected independently, producing impossible
  combinations (AMD vendor + Intel renderer). Now selected as a consistent pair.
- Audio noise was a no-op because `-Infinity` values swallowed the offset.
- Font enumeration reported 19 of 25 probed fonts as present.

## [0.13] — Заслон

### Added
- Ad blocking (dedicated list + toggle).
- Cookie-banner hiding: OneTrust, Cookiebot, Usercentrics, Quantcast, Sourcepoint,
  IAB TCF; Shadow DOM traversal; `MutationObserver`; auto-click on reject.
- Third-party cookie stripping via interceptor plus cookie-store enforcement.
- Expanded fingerprint masking.

## [0.12] — Чистка

### Changed
- Removed debug logging.
- Updated README with run and rebuild instructions.

## [0.11] — Поиск

### Fixed
- Start page hardcoded DuckDuckGo instead of using the configured engine.
- Address bar now re-reads config from disk before searching.
- Removed Kagi (registration required) and Startpage (slow verification).

## [0.10] — Свет

### Fixed
- Internal pages (`newtab`, `blocked`, `settings`) stayed dark after switching to
  the light theme. `apply_theme` now re-renders all open internal pages.

## [0.9] — Коробка

### Added
- PyInstaller build (`Pri-Yandex.spec`), single-file `.exe` (~249 MB).
- Fixed `paths.py` so `userdata` is created next to the `.exe` in frozen mode,
  not in the PyInstaller temp directory.

## [0.8] — Лицо

### Added
- Logo (shield + "P"), background removed, anti-aliased edges.
- Embedded in the start page and used as the window icon.

## [0.7] — Маскировка

### Added
- JavaScript injection via `QWebEngineScript` at `DocumentCreation`.
- Fingerprint masking and cookie-banner hiding.
- Third-party script blocking at the interceptor level.

## [0.6] — Панель управления

### Added
- `pri://settings` with appearance, search, protection, privacy and list sections.
- Persistent settings in `config.json`.

## [0.5] — Хром

### Changed
- Rewrote `browser.py` into a Chrome-like layout: tabs on top, omnibox, nav
  buttons, shield counter.

## [0.4] — Анти-перезагрузка

### Fixed
- `pri://blocked` reloaded every 250 ms; now re-renders only when new events arrive.

## [0.3] — Лекарство

### Fixed
- Corrected Qt6 WebEngine API usage (`requestUrl()`, `setHttpHeader()`).
- Moved URL cleaning to `navigationRequested`.
- Fixed resource-type name resolution and event timestamps.

## [0.2] — Щит

### Added
- Request interception, tracker blocking, URL cleaning, header hardening,
  speculative-navigation blocking, permissions denied by default.
- "Blocked" panel with a counter in the address bar.

## [0.1] — Искра

### Added
- Initial browser shell on PySide6 + QtWebEngine.
- Tabs, address bar, navigation, hotkeys.
- All paths pinned to the project directory (disk `C:` untouched).