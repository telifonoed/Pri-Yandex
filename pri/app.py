import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

from .paths import pin_environment, PROJECT_ROOT
NOTES = pin_environment()

from .browser import BrowserWindow
from .config import Config

JS_DIR = PROJECT_ROOT / "pri" / "js"

def _js_dirs():
    """Candidate locations for pri/js: source tree and PyInstaller bundle."""
    dirs = [PROJECT_ROOT / "pri" / "js"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.insert(0, Path(meipass) / "pri" / "js")
    return dirs

def _load_js(name: str) -> str:
    """Load an injected script from pri/js/ (source tree or frozen bundle)."""
    for d in _js_dirs():
        try:
            p = d / name
            if p.exists():
                return p.read_text(encoding="utf-8")
        except OSError:
            continue
    import sys as _s
    print(f"WARNING: could not load {name}", file=_s.stderr)
    return ""

def _add_script(profile, name, code, world_id=None):
    from PySide6.QtWebEngineCore import QWebEngineScript
    if not code:
        return
    sc = QWebEngineScript()
    sc.setName(name)
    sc.setSourceCode(code)
    sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    sc.setRunsOnSubFrames(True)
    profile.scripts().insert(sc)

def main():
    cfg = Config.load()
    app = QApplication(sys.argv)
    app.setApplicationName("Pri")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("Pri")
    app.setStyle("Fusion")

    def apply_theme(theme):
        pal = QPalette()
        if theme == "light":
            pal.setColor(QPalette.ColorRole.Window, QColor("#f2f2f2"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a1a"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#eaeaea"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#1a1a1a"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#e0e0e0"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a1a"))
            pal.setColor(QPalette.ColorRole.Highlight, QColor("#0078d4"))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        else:
            pal.setColor(QPalette.ColorRole.Window, QColor("#0f1419"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#d6dde6"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#161b22"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c222b"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#d6dde6"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#1c222b"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#d6dde6"))
            pal.setColor(QPalette.ColorRole.Highlight, QColor("#3ddc97"))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f1419"))
        app.setPalette(pal)
    apply_theme(cfg.theme)
    app._apply_theme = apply_theme

    # ---- Chromium flags ----
    import os
    base_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    extra = []
    wp = cfg.webrtc_policy
    if wp and wp != "default":
        extra.append(f"--force-webrtc-ip-handling-policy={wp}")
    if cfg.block_third_party_cookies or cfg.block_all_cookies:
        extra.append("--block-third-party-cookies")
    if extra:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (base_flags + " " + " ".join(extra)).strip()

    profile = QWebEngineProfile("pri-default")
    if cfg.block_all_cookies or cfg.block_third_party_cookies:
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    else:
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setHttpCacheMaximumSize(512 * 1024 * 1024)

    s = profile.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, cfg.dns_prefetch)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.XSSAuditingEnabled, True)

    # ---- cookie enforcement ----
    if cfg.block_third_party_cookies or cfg.block_all_cookies:
        store = profile.cookieStore()

        def _on_cookie_added(cookie):
            try:
                if cfg.block_all_cookies:
                    store.deleteCookie(cookie)
                    return
                domain = (cookie.domain() or "").lstrip(".")
                if not domain:
                    return
                a = QApplication.instance()
                host = getattr(a, "_pri_current_host", {}).get("host", "") if hasattr(a, "_pri_current_host") else ""
                if not host:
                    return
                same = (domain == host
                        or host.endswith("." + domain)
                        or domain.endswith("." + host))
                if not same:
                    store.deleteCookie(cookie)
            except Exception:
                pass

        store.cookieAdded.connect(_on_cookie_added)
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, store.deleteAllCookies)
        except Exception:
            pass

    # ---- injected scripts ----
    # DNT + GPC (independent toggles, not tied to fingerprinting)
    dnt_js = ""
    if cfg.dnt_enabled:
        dnt_js += "try{Object.defineProperty(navigator,'doNotTrack',{get:function(){return '1';},configurable:true});}catch(e){}"
    if cfg.gpc_enabled:
        dnt_js += "try{Object.defineProperty(navigator,'globalPrivacyControl',{get:function(){return true;},configurable:true});}catch(e){}"
    if dnt_js:
        _add_script(profile, "pri-dnt-gpc", "(function(){" + dnt_js + "})();")

    if cfg.block_fingerprinting:
        _add_script(profile, "pri-fingerprint", _load_js("fingerprint.js"))

    if cfg.block_cookie_popups:
        _add_script(profile, "pri-cookiepopups", _load_js("cookiebanner.js"))

    if cfg.block_all_cookies:
        _add_script(profile, "pri-cookie-lock", _load_js("cookielock.js"))

    window = BrowserWindow(cfg, profile)
    app._on_theme_change = window.apply_theme

    from PySide6.QtGui import QIcon
    icon_path = PROJECT_ROOT / "assets" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        window.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    if "--print-notes" in sys.argv:
        for n in NOTES:
            print(n)
    return app.exec()