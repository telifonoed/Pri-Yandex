# Contributing to Pri-Yandex

Thanks for wanting to help.

## Dev setup

```bash
git clone https://github.com/YOUR_USER/Pri-Yandex.git
cd Pri-Yandex
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe run.py
```

Build dependencies (for the `.exe`):

```bash
venv\Scripts\python.exe -m pip install -r requirements-build.txt
venv\Scripts\pyinstaller.exe Pri-Yandex.spec
```

## Tests

Both run headless and don't need a display:

```bash
venv\Scripts\python.exe tests\test_privacy.py     # blocking, URL cleaning, headers
venv\Scripts\python.exe tests\test_fingerprint.py # spoofing values
```

They talk to a local HTTP server and a real QtWebEngine page — no network access
required beyond `example.com` in the fingerprint test.

## Adding blocklist rules

- `pri/privacy/lists/trackers.txt` — analytics, telemetry, fingerprinting
- `pri/privacy/lists/ads.txt` — ad networks

Format is EasyList-style:

```
||domain.com^          block domain and all subdomains
||domain.com/path^     block host + path prefix
@@domain.com^          allowlist (exception wins over blocks)
type:prefetch          block by resource type
/regex/                regex match
```

Comments start with `!`.

## Adding injected scripts

Drop a `.js` file in `pri/js/` and wire it up in `pri/app.py` via `_add_script`.
Scripts run at `DocumentCreation` in the main world, so they execute before any
page script.

## Rules of thumb

- **Nothing goes to disk `C:`.** All paths come from `pri/paths.py`.
- **Privacy logic lives at the network layer** (`privacy/interceptor.py`).
  JS injection is for fingerprinting only.
- **Don't block by hardcoded constants.** A constant value is still a stable
  fingerprint — randomize per page load instead.
- **Test before claiming it works.** Both test files exist for a reason.

## Reporting bugs

Include: Pri version, Windows version, what you expected, what happened, and the
`pri://blocked` panel contents if trackers were involved.