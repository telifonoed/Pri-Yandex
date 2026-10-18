import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle: keep userdata next to the .exe.
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_DATA = PROJECT_ROOT / "userdata"
PROFILE_DIR = USER_DATA / "profile"
CACHE_DIR = USER_DATA / "cache"
TEMP_DIR = USER_DATA / "temp"
DOWNLOAD_DIR = USER_DATA / "downloads"
CONFIG_PATH = USER_DATA / "config.json"
LOG_PATH = USER_DATA / "pri.log"

def ensure_dirs():
    for d in (USER_DATA, PROFILE_DIR, CACHE_DIR, TEMP_DIR, DOWNLOAD_DIR,
              CACHE_DIR / "chromium", CACHE_DIR / "pip", TEMP_DIR / "chromium"):
        d.mkdir(parents=True, exist_ok=True)

def pin_environment():
    ensure_dirs()
    for var in ("TEMP", "TMP"):
        os.environ[var] = str(TEMP_DIR)
    os.environ.setdefault("TMPDIR", str(TEMP_DIR))
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        f"--disk-cache-dir={CACHE_DIR / 'chromium'} "
        f"--crash-dumps-dir={CACHE_DIR / 'crashes'} "
        "--disable-breakpad --disable-gpu-shader-disk-cache "
        "--disable-background-networking --disable-component-update "
        "--disable-domain-reliability --disable-sync "
        "--metrics-recording-only --no-first-run --no-default-browser-check "
        "--no-service-autorun --password-store=basic --use-mock-keychain "
        "--disable-features=TranslateUI"
    )
    os.environ["QT_OPENGL"] = "software"
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    os.environ.setdefault("PIP_CACHE_DIR", str(CACHE_DIR / "pip"))
    return str(PROJECT_ROOT)
