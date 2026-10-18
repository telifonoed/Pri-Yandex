from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from .config import Config
from .paths import DOWNLOAD_DIR
from .privacy.urlclean import clean_url


class PriPage(QWebEnginePage):
    new_tab_requested = Signal(str)
    blocked_page_requested = Signal()

    def __init__(self, profile, config, report, parent=None):
        super().__init__(profile, parent)
        self._config = config
        self._report = report
        from PySide6.QtGui import QColor
        self.setBackgroundColor(QColor("#0f1419"))
        if hasattr(self, "newWindowRequested"):
            self.newWindowRequested.connect(self._on_new_window)
        if hasattr(self, "permissionRequested"):
            self.permissionRequested.connect(self._on_permission)
        if hasattr(self, "featurePermissionRequested"):
            self.featurePermissionRequested.connect(self._on_feature_permission)
        if hasattr(self, "downloadRequested"):
            self.downloadRequested.connect(self._on_download)
        if hasattr(self, "javaScriptDialogRequested"):
            self.javaScriptDialogRequested.connect(self._on_js_dialog)
        self._wire_navigation()

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        # Fallback for older code paths; prefer navigationRequested signal.
        if url.scheme().lower() == "pri":
            self._handle_internal(url)
            return False
        return True

    def _wire_navigation(self):
        if hasattr(self, "navigationRequested"):
            self.navigationRequested.connect(self._on_navigation_requested)

    def _on_navigation_requested(self, request):
        try:
            url = request.url()
        except Exception:
            url = request.requestUrl() if hasattr(request, "requestUrl") else None
        if url is None:
            return
        is_main = request.isMainFrame() if hasattr(request, "isMainFrame") else True
        if url.scheme().lower() == "pri":
            try:
                request.reject() if hasattr(request, "reject") else None
            except Exception:
                pass
            self._handle_internal(url)
            return
        if (is_main and self._config.clean_urls and url.scheme() in ("http", "https")):
            new_url, removed = clean_url(url)
            if removed:
                try:
                    request.reject()
                except Exception:
                    pass
                QTimer.singleShot(0, lambda u=new_url: self.setUrl(u))
                return
        # default: accept
        try:
            request.accept()
        except Exception:
            pass

    def _handle_internal(self, url):
        self._pri_handled = True
        host = url.host().lower()
        path = url.path().lower()

        if host == "set" or path.startswith("/set"):
            self._apply_setting(url)
            # Re-render settings immediately so theme change is visible.
            try:
                self.setHtml(self._settings_html(), baseUrl=QUrl("pri://settings"))
            except Exception:
                QTimer.singleShot(0, lambda: self.setHtml(self._settings_html(), baseUrl=QUrl("pri://settings")))
            return
        if host == "settings" or path.startswith("/settings"):
            self.setHtml(self._settings_html(), baseUrl=QUrl("pri://settings"))
            return
        if host == "blocked" or path.startswith("/blocked"):
            self.blocked_page_requested.emit()
            return
        if host == "newtab" or path.startswith("/newtab"):
            self.setHtml(self._newtab_html(), baseUrl=QUrl("pri://newtab"))
            return
        if host == "about" or path.startswith("/about"):
            self.setHtml(self._about_html(), baseUrl=QUrl("pri://about"))
            return
        if host == "allow":
            q = url.query()
            domain = ""
            for part in q.split("&"):
                if part.startswith("domain="):
                    domain = part[len("domain="):]
            if domain:
                self._config.allowlist.append(domain.lower())
                self._config.save()
            self.blocked_page_requested.emit()
            return
        self.setHtml(self._about_html(), baseUrl=QUrl("pri://about"))

    def _on_new_window(self, request):
        try:
            u = request.requestedUrl().toString() if hasattr(request, "requestedUrl") else "about:blank"
        except Exception:
            u = "about:blank"
        self.new_tab_requested.emit(u if u else "about:blank")

    def createWindow(self, window_type):
        page = PriPage(self.profile(), self._config, self._report)
        page.new_tab_requested.connect(self.new_tab_requested)
        page.blocked_page_requested.connect(self.blocked_page_requested)
        page.loadStarted.connect(lambda: self.new_tab_requested.emit(page.url().toString()))
        return page

    def _on_permission(self, permission):
        if not self._config.deny_permissions:
            try: permission.grant()
            except Exception: pass
            return
        try: permission.deny()
        except Exception: pass

    def _on_feature_permission(self, origin, feature):
        if self._config.deny_permissions:
            try:
                self.setFeaturePermission(
                    origin, feature,
                    QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
                )
            except Exception:
                pass

    def _on_download(self, item):
        suggested = item.downloadFileName() if hasattr(item, "downloadFileName") else "download"
        path, _ = QFileDialog.getSaveFileName(None, "Save file", str(DOWNLOAD_DIR / suggested))
        if not path:
            item.cancel()
            return
        item.setDownloadDirectory(str(Path(path).parent))
        item.setDownloadFileName(Path(path).name)
        try:
            item.accept()
        except Exception:
            pass

    def _on_js_dialog(self, request):
        msg = getattr(request, "message", "") or ""
        default = getattr(request, "defaultText", "") or ""
        title = "Pri"
        kind = str(getattr(request, "type", ""))
        if "Alert" in kind:
            QMessageBox.information(None, title, msg)
            try: request.accept()
            except Exception: pass
            return
        if "Confirm" in kind:
            r = QMessageBox.question(None, title, msg)
            try:
                request.dialogAccept(r == QMessageBox.StandardButton.Yes)
            except Exception:
                try: request.accepted = True
                except Exception: pass
            return
        text, ok = QInputDialog.getText(None, title, msg, text=default)
        try:
            if ok: request.dialogAccept(text)
            else: request.dialogReject()
        except Exception:
            pass

    def _apply_setting(self, url):
        from urllib.parse import parse_qs, unquote
        q = url.query()
        # parse_qs handles multiple; we want raw for text fields
        params = {}
        for part in q.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = unquote(v.replace("+", " "))
        bool_fields = {"block_trackers", "clean_urls", "strip_headers", "block_speculative",
                       "deny_permissions", "safe_browsing", "dns_prefetch", "block_scripts",
                       "block_fingerprinting", "block_cookie_popups", "block_third_party_cookies"}
        text_fields = {"search_template", "home_page", "search_engine", "webrtc_policy", "theme"}
        for k, v in params.items():
            if k in bool_fields:
                setattr(self._config, k, v in ("1", "true", "on", "yes"))
            elif k in text_fields:
                setattr(self._config, k, v)
            elif k == "allow_domain":
                self._config.allowlist.append(v.lower())
            elif k == "block_domain":
                self._config.blocklist.append(v.lower())
            elif k == "reset_allowlist":
                self._config.allowlist = []
            elif k == "reset_blocklist":
                self._config.blocklist = []
        # Live-apply theme.
        if "theme" in params:
            try:
                from PySide6.QtWidgets import QApplication
                a = QApplication.instance()
                if a and hasattr(a, "_apply_theme"):
                    a._apply_theme(params["theme"])
                if a and hasattr(a, "_on_theme_change"):
                    a._on_theme_change(params["theme"])
            except Exception:
                pass
        # Live-apply cookie policy.
        if "block_third_party_cookies" in params:
            try:
                pol = QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies if params["block_third_party_cookies"] in ("1","true","on","yes") else QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
                self.profile().setPersistentCookiesPolicy(pol)
            except Exception:
                pass
        # search_engine presets
        presets = {
            "duckduckgo": "https://duckduckgo.com/?q={query}",
            "google": "https://www.google.com/search?q={query}",
            "yandex": "https://yandex.ru/search/?text={query}",
            "brave": "https://search.brave.com/search?q={query}",
        }
        if "search_engine" in params and params["search_engine"] in presets:
            self._config.search_template = presets[params["search_engine"]]
        self._config.save()

    def _toggle(self, field):
        cur = getattr(self._config, field, False)
        return "1" if not cur else "0"

    def _settings_html(self):
        cfg = self._config
        from .ui.theme import colors as _colors
        c = _colors(cfg.theme)
        def cb(field):
            checked = "checked" if getattr(cfg, field, False) else ""
            return checked
        engines = [("duckduckgo","DuckDuckGo"),("google","Google"),("yandex","Yandex"),
                   ("brave","Brave")]
        engine_opts = "".join(
            f'<option value="{e}" {"selected" if cfg.search_engine==e else ""}>{n}</option>'
            for e, n in engines)
        webrtc_opts = "".join(
            f'<option value="{v}" {"selected" if cfg.webrtc_policy==v else ""}>{l}</option>'
            for v, l in [("default","По умолчанию (утечки возможны)"),
                         ("default_public_interface_only","Только публичный IP"),
                         ("disable_non_proxied_udp","Без UDP вне прокси (рекомендуется)"),
                         ("disable_udp","Полностью отключить UDP")])
        theme_opts = "".join(
            f'<option value="{v}" {"selected" if cfg.theme==v else ""}>{l}</option>'
            for v, l in [("dark","Тёмная"),("light","Светлая")])
        allow_items = "".join(f"<li>{__import__('html').escape(d)} <a href='pri://set?block_domain=@@{d}'>×</a></li>" for d in cfg.allowlist) or "<li class='muted'>пусто</li>"
        block_items = "".join(f"<li>{__import__('html').escape(d)} <a href='pri://set?block_domain=@@{d}'>×</a></li>" for d in cfg.blocklist) or "<li class='muted'>пусто</li>"
        import html as _h
        allow_items = "".join(f"<li>{_h.escape(d)}</li>" for d in cfg.allowlist) or "<li class='muted'>пусто</li>"
        block_items = "".join(f"<li>{_h.escape(d)}</li>" for d in cfg.blocklist) or "<li class='muted'>пусто</li>"
        return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{margin:0;padding:24px 40px;font-family:Segoe UI,system-ui,sans-serif;background:{c['bg']};color:{c['text']};max-width:900px}}
h1{{color:{c['accent']};margin-top:0}}h2{{margin-top:32px;border-bottom:1px solid {c['border']};padding-bottom:6px;color:{c['text']}}}
h3{{margin-top:18px;color:{c['muted']};font-size:13px;text-transform:uppercase;letter-spacing:.5px}}
.card{{background:{c['card']};border:1px solid {c['border']};border-radius:10px;padding:16px;margin:12px 0}}
.row{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid {c['border']}}}
.row:last-child{{border-bottom:none}}
.row .label{{flex:1}}.row .label .t{{font-weight:600}}.row .label .s{{color:{c['muted']};font-size:12px;margin-top:2px}}
.toggle{{width:40px;height:22px;border-radius:11px;background:{c['border']};position:relative;cursor:pointer;border:none}}
.toggle.on{{background:{c['accent']}}}
.toggle::after{{content:'';position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:9px;background:#fff;transition:.2s}}
.toggle.on::after{{left:20px;background:{c['bg']}}}
select,input[type=text]{{background:{c['input']};color:{c['text']};border:1px solid {c['border']};border-radius:6px;padding:6px 10px;font-size:13px}}
button{{background:{c['accent']};color:{c['bg']};border:none;border-radius:6px;padding:6px 14px;font-weight:600;cursor:pointer;margin-left:6px}}
a{{color:{c['accent']};text-decoration:none}}.muted{{color:{c['muted']};font-size:12px}}
ul{{padding-left:18px;line-height:1.8}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:700px){{.grid2{{grid-template-columns:1fr}}}}
</style>
<script>
function tog(field,current){{
  location.href='pri://set?'+field+'='+(current?'0':'1');
}}
function setVal(field){{
  var el=document.getElementById(field);
  location.href='pri://set?'+field+'='+encodeURIComponent(el.value);
}}
function setSel(field){{
  var el=document.getElementById(field);
  location.href='pri://set?'+field+'='+encodeURIComponent(el.value);
}}
</script></head><body>
<h1>Настройки Pri</h1>
<p class="muted">Все изменения сохраняются в userdata/config.json</p>
<p class="muted" style="color:#f0a020">⚠ Настройки WebRTC и cookie третьих сторон применяются после перезапуска браузера. Тема и поисковик — сразу.</p>

<h2>Внешний вид</h2>
<div class="card">
  <div class="row"><div class="label"><div class="t">Тема</div><div class="s">Тёмная или светлая</div></div>
    <select id="theme" onchange="setSel('theme')">{theme_opts}</select></div>
  <div class="row"><div class="label"><div class="t">Домашняя страница</div><div class="s">URL при открытии новой вкладки</div></div>
    <input type="text" id="home_page" value="{_h.escape(cfg.home_page)}" style="width:260px">
    <button onclick="setVal('home_page')">Сохранить</button></div>
</div>

<h2>Поиск</h2>
<div class="card">
  <div class="row"><div class="label"><div class="t">Поисковик по умолчанию</div><div class="s">Шаблон: {{query}} — место запроса</div></div>
    <select id="search_engine" onchange="setSel('search_engine')">{engine_opts}</select></div>
  <div class="row"><div class="label"><div class="t">Свой шаблон</div><div class="s">Например https://example.com/?q={{query}}</div></div>
    <input type="text" id="search_template" value="{_h.escape(cfg.search_template)}" style="width:260px">
    <button onclick="setVal('search_template')">Сохранить</button></div>
</div>

<h2>Защита</h2>
<div class="card">
  <div class="row"><div class="label"><div class="t">Блокировка трекеров</div><div class="s">EasyList + свой список доменов</div></div>
    <button class="toggle {cb('block_trackers') and 'on' or ''}" onclick="tog('block_trackers',{str(cfg.block_trackers).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Блокировка рекламы</div><div class="s">Рекламные сети и баннеры</div></div>
    <button class="toggle {cb('block_ads') and 'on' or ''}" onclick="tog('block_ads',{str(cfg.block_ads).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Блокировка скриптов третьих сторон</div><div class="s">Блокирует JS с чужих доменов на странице</div></div>
    <button class="toggle {cb('block_scripts') and 'on' or ''}" onclick="tog('block_scripts',{str(cfg.block_scripts).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Блокировка всплывающих cookie-баннеров</div><div class="s">Скрывает типовые баннеры согласия</div></div>
    <button class="toggle {cb('block_cookie_popups') and 'on' or ''}" onclick="tog('block_cookie_popups',{str(cfg.block_cookie_popups).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Блокировка cookie третьих сторон</div><div class="s">Не принимать cookie от чужих доменов</div></div>
    <button class="toggle {cb('block_third_party_cookies') and 'on' or ''}" onclick="tog('block_third_party_cookies',{str(cfg.block_third_party_cookies).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Полная блокировка cookie</div><div class="s">Отключает все cookie. Логины и корзины перестанут работать</div></div>
    <button class="toggle {cb('block_all_cookies') and 'on' or ''}" onclick="tog('block_all_cookies',{str(cfg.block_all_cookies).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Очистка URL</div><div class="s">Удаляет utm_*, fbclid, gclid и др.</div></div>
    <button class="toggle {cb('clean_urls') and 'on' or ''}" onclick="tog('clean_urls',{str(cfg.clean_urls).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Блокировка speculative-загрузок</div><div class="s">Prefetch, prerender, beacons</div></div>
    <button class="toggle {cb('block_speculative') and 'on' or ''}" onclick="tog('block_speculative',{str(cfg.block_speculative).lower()})"></button></div>
</div>

<h2>Конфиденциальность и безопасность</h2>
<div class="card">
  <div class="row"><div class="label"><div class="t">Do Not Track (DNT)</div><div class="s">Отправляет DNT: 1 на все сайты</div></div>
    <button class="toggle {cb('dnt_enabled') and 'on' or ''}" onclick="tog('dnt_enabled',{str(cfg.dnt_enabled).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Global Privacy Control (GPC)</div><div class="s">Отправляет Sec-GPC: 1 на все сайты</div></div>
    <button class="toggle {cb('gpc_enabled') and 'on' or ''}" onclick="tog('gpc_enabled',{str(cfg.gpc_enabled).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Срез заголовков</div><div class="s">Удаляет Referer и другие идентификаторы</div></div>
    <button class="toggle {cb('strip_headers') and 'on' or ''}" onclick="tog('strip_headers',{str(cfg.strip_headers).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Помеха фингерпринтингу</div><div class="s">Маскирует webdriver, плагины, WebGL, языки</div></div>
    <button class="toggle {cb('block_fingerprinting') and 'on' or ''}" onclick="tog('block_fingerprinting',{str(cfg.block_fingerprinting).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Запрет разрешений</div><div class="s">Камера, микрофон, гео, уведомления — отказ</div></div>
    <button class="toggle {cb('deny_permissions') and 'on' or ''}" onclick="tog('deny_permissions',{str(cfg.deny_permissions).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">Политика WebRTC</div><div class="s">Защита от утечки локального IP</div></div>
    <select id="webrtc_policy" onchange="setSel('webrtc_policy')">{webrtc_opts}</select></div>
  <div class="row"><div class="label"><div class="t">Безопасный просмотр (Safe Browsing)</div><div class="s">Проверка URL через Google (отправляет хэши)</div></div>
    <button class="toggle {cb('safe_browsing') and 'on' or ''}" onclick="tog('safe_browsing',{str(cfg.safe_browsing).lower()})"></button></div>
  <div class="row"><div class="label"><div class="t">DNS-prefetch</div><div class="s">Предзагрузка DNS (утечка запросов)</div></div>
    <button class="toggle {cb('dns_prefetch') and 'on' or ''}" onclick="tog('dns_prefetch',{str(cfg.dns_prefetch).lower()})"></button></div>
</div>

<h2>Списки</h2>
<div class="grid2">
<div class="card"><h3>Разрешённые домены</h3><ul>{allow_items}</ul>
  <input type="text" id="allow_domain" placeholder="example.com" style="width:180px">
  <button onclick="setVal('allow_domain')">Добавить</button></div>
<div class="card"><h3>Заблокированные домены</h3><ul>{block_items}</ul>
  <input type="text" id="block_domain" placeholder="example.com" style="width:180px">
  <button onclick="setVal('block_domain')">Добавить</button></div>
</div>

<p style="margin-top:24px"><a href="pri://newtab">← Новая вкладка</a> · <a href="pri://blocked">Что заблокировано</a></p>
</body></html>"""

    def _newtab_html(self):
        # Embed logo as base64 so it works on pri:// pages.
        logo_b64 = ""
        try:
            import base64
            from pathlib import Path
            logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
            if logo_path.exists():
                logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
        except Exception:
            logo_b64 = ""
        tmpl = self._config.search_template.replace('"', '\\"')
        from .ui.theme import colors as _colors
        c = _colors(self._config.theme)
        return f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:{c['bg']};color:{c['text']};display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:24px 0}}
h1{{font-size:48px;margin:0;color:{c['accent']}}}p{{color:{c['muted']};margin:8px 0 24px}}
form{{display:flex;gap:8px;width:min(560px,90vw)}}
input{{flex:1;padding:12px 16px;border-radius:8px;border:1px solid {c['border']};background:{c['input']};color:{c['text']};font-size:15px;outline:none}}
input:focus{{border-color:{c['accent']}}}button{{padding:12px 20px;border-radius:8px;border:none;background:{c['accent']};color:{c['bg']};font-weight:600;cursor:pointer}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:32px;width:min(560px,90vw)}}
.card{{background:{c['card']};border:1px solid {c['border']};border-radius:10px;padding:14px;cursor:pointer}}
.card:hover{{border-color:{c['accent']}}}.card .t{{font-weight:600}}.card .s{{color:{c['muted']};font-size:12px;margin-top:4px}}
a{{color:{c['accent']};text-decoration:none}}</style>
<script>
var SEARCH_TMPL = "{tmpl}";
function doSearch(q){{
  var url = SEARCH_TMPL.replace("{{query}}", encodeURIComponent(q));
  location.href = url;
}}
</script></head><body>
{('<img src="data:image/png;base64,' + logo_b64 + '" style="height:80px;margin-bottom:16px;display:block;image-rendering:-webkit-optimize-contrast;image-rendering:crisp-edges;" alt="Pri-Yandex">') if logo_b64 else ''}
<h1>Pri</h1><p>Privacy, not profiling.</p>
<form onsubmit="event.preventDefault();doSearch(this.q.value)">
<input name="q" placeholder="Search or enter address" autofocus><button type="submit">Go</button></form>
<div class="grid">
<div class="card" onclick="location.href='https://en.wikipedia.org'"><div class="t">Wikipedia</div><div class="s">Knowledge</div></div>
<div class="card" onclick="location.href='pri://blocked'"><div class="t">Blocked</div><div class="s">What Pri stopped</div></div>
<div class="card" onclick="location.href='pri://about'"><div class="t">About</div><div class="s">Version &amp; info</div></div>
<div class="card" onclick="location.href='pri://settings'"><div class="t">Settings</div><div class="s">Privacy &amp; protection</div></div>
</div></body></html>"""

    def _about_html(self):
        from . import APP_VERSION, APP_TAGLINE
        cfg = self._config
        from .ui.theme import colors as _colors
        c = _colors(cfg.theme)
        return f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;padding:40px;font-family:Segoe UI,system-ui,sans-serif;background:{c['bg']};color:{c['text']}}}
h1{{color:{c["accent"]}}}code{{background:{c["card"]};padding:2px 6px;border-radius:4px}}
ul{{line-height:1.8}}.muted{{color:{c["muted"]}}}</style></head><body>
<h1>Pri {APP_VERSION}</h1><p class="muted">{APP_TAGLINE}</p>
<h2>Settings</h2><ul>
<li>Block trackers: <b>{cfg.block_trackers}</b></li>
<li>Clean URLs: <b>{cfg.clean_urls}</b></li>
<li>Strip headers: <b>{cfg.strip_headers}</b></li>
<li>Block speculative: <b>{cfg.block_speculative}</b></li>
<li>Deny permissions: <b>{cfg.deny_permissions}</b></li>
</ul>
<p><a href="pri://blocked">See what was blocked</a> · <a href="pri://newtab">New tab</a></p>
</body></html>"""


class PriView(QWebEngineView):
    def __init__(self, page):
        super().__init__()
        self.setPage(page)
