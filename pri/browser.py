from __future__ import annotations
import html
from urllib.parse import urlparse
from pathlib import Path

from PySide6.QtCore import QUrl, QTimer, Qt, QSize
from PySide6.QtGui import QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QTabBar, QStackedWidget,
    QToolBar, QVBoxLayout, QWidget, QPushButton, QSizePolicy,
)

from .config import Config
from .page import PriPage, PriView
from .privacy.interceptor import PrivacyInterceptor
from .privacy.report import BlockedEvent, BlockedRegistry
from .privacy.rules import RuleSet, load_default_rules


class BrowserWindow(QMainWindow):
    def __init__(self, config, profile):
        super().__init__()
        self._config = config
        self._profile = profile
        self._report = BlockedRegistry()

        self._rules = load_default_rules()
        lists_dir = Path(__file__).resolve().parent / "privacy" / "lists"
        if getattr(config, "block_ads", True):
            ads_path = lists_dir / "ads.txt"
            if ads_path.exists():
                self._rules = self._rules.merged(RuleSet.from_file(ads_path))
        for extra in sorted(lists_dir.glob("extra-*.txt")):
            self._rules = self._rules.merged(RuleSet.from_file(extra))

        self._interceptor = PrivacyInterceptor(config, self._rules, self._report)
        profile.setUrlRequestInterceptor(self._interceptor)

        self.setWindowTitle("Pri")
        self.resize(1280, 820)

        # ---- central: Chrome-like layout ----
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tab bar row
        tabrow = QWidget()
        tabrow.setObjectName("tabrow")
        tabrow_layout = QHBoxLayout(tabrow)
        tabrow_layout.setContentsMargins(8, 6, 8, 0)
        tabrow_layout.setSpacing(4)

        self._tabbar = QTabBar()
        self._tabbar.setTabsClosable(True)
        self._tabbar.setMovable(True)
        self._tabbar.setExpanding(False)
        self._tabbar.setDrawBase(False)
        self._tabbar.tabCloseRequested.connect(self._close_tab)
        self._tabbar.currentChanged.connect(self._on_tab_changed)
        self._tabbar.setStyleSheet("""
            QTabBar::tab { background:#232a33; color:#c9d1d9; padding:6px 14px;
                margin-right:2px; border-top-left-radius:8px; border-top-right-radius:8px;
                min-width:120px; max-width:220px; }
            QTabBar::tab:selected { background:#0f1419; color:#ffffff; }
            QTabBar::tab:hover { background:#2c3440; }
            QTabBar::close-button { subcontrol-position: right; }
        """)
        tabrow_layout.addWidget(self._tabbar, 1)

        self._newtab_btn = QPushButton("+")
        self._newtab_btn.setFixedSize(28, 28)
        self._newtab_btn.setStyleSheet("background:#232a33; color:#c9d1d9; border:none; border-radius:6px; font-size:16px;")
        self._newtab_btn.clicked.connect(lambda: self.new_tab(self._config.home_page))
        tabrow_layout.addWidget(self._newtab_btn)

        root.addWidget(tabrow)

        # Address bar row (omnibox)
        addrrow = QWidget()
        addrrow.setStyleSheet("background:#0f1419; padding:6px 8px;")
        addr_layout = QHBoxLayout(addrrow)
        addr_layout.setContentsMargins(8, 4, 8, 6)
        addr_layout.setSpacing(6)

        self._back = QPushButton("←")
        self._fwd = QPushButton("→")
        self._reload = QPushButton("⟳")
        for b in (self._back, self._fwd, self._reload):
            b.setFixedSize(30, 30)
            b.setStyleSheet("background:#1c222b; color:#d6dde6; border:none; border-radius:6px; font-size:14px;")
        self._back.clicked.connect(lambda: self._cv().back() if self._cv() else None)
        self._fwd.clicked.connect(lambda: self._cv().forward() if self._cv() else None)
        self._reload.clicked.connect(self._reload_or_stop)
        addr_layout.addWidget(self._back)
        addr_layout.addWidget(self._fwd)
        addr_layout.addWidget(self._reload)

        self._address = QLineEdit()
        self._address.setPlaceholderText("Search or enter address")
        self._address.returnPressed.connect(self._navigate_address)
        self._address.setStyleSheet("""
            QLineEdit { background:#1c222b; color:#d6dde6; border:1px solid #2a313b;
                border-radius:16px; padding:6px 14px; font-size:14px; }
            QLineEdit:focus { border-color:#3ddc97; }
        """)
        addr_layout.addWidget(self._address, 1)

        self._go_btn = QPushButton("→")
        self._go_btn.setFixedSize(30, 30)
        self._go_btn.setStyleSheet("background:#3ddc97; color:#0f1419; border:none; border-radius:6px; font-size:14px; font-weight:700;")
        self._go_btn.clicked.connect(self._navigate_address)
        addr_layout.addWidget(self._go_btn)

        self._shield = QLabel("🛡 0")
        self._shield.setStyleSheet("padding:0 8px; font-weight:600; color:#3ddc97;")
        addr_layout.addWidget(self._shield)

        self._blocked_btn = QPushButton("Blocked")
        self._blocked_btn.setStyleSheet("background:#1c222b; color:#d6dde6; border:none; border-radius:6px; padding:6px 10px;")
        self._blocked_btn.clicked.connect(self._open_blocked)
        addr_layout.addWidget(self._blocked_btn)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(30, 30)
        self._settings_btn.setStyleSheet("background:#1c222b; color:#d6dde6; border:none; border-radius:6px; font-size:14px;")
        self._settings_btn.clicked.connect(lambda: self.new_tab("pri://settings"))
        addr_layout.addWidget(self._settings_btn)

        root.addWidget(addrrow)

        # Stacked views
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:#0f1419;")
        root.addWidget(self._stack, 1)

        # status bar
        sb = self.statusBar()
        self._status = QLabel("Pri ready")
        sb.addWidget(self._status, 1)
        self._counts = QLabel("")
        sb.addPermanentWidget(self._counts)

        # drain timer
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(250)
        self._drain_timer.timeout.connect(self._drain_report)
        self._drain_timer.start()

        self._tabs = []  # list of dicts: {page, view, container}
        self._current_page_url = ""
        self._pending = []
        self._last_blocked_render = 0

        # shortcuts
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.new_tab(self._config.home_page))
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self._address.setFocus())
        QShortcut(QKeySequence("Ctrl+R"), self, lambda: self._cv().reload() if self._cv() else None)

        self.apply_theme(self._config.theme)
        self.new_tab(self._config.home_page)

    def apply_theme(self, theme):
        dark = (theme != "light")
        if dark:
            tabrow_bg = "#1a1f27"; tab_bg = "#232a33"; tab_sel = "#0f1419"
            tab_hover = "#2c3440"; text = "#c9d1d9"; text_sel = "#ffffff"
            addr_bg = "#1c222b"; addr_border = "#2a313b"; addr_focus = "#3ddc97"
            btn_bg = "#1c222b"; accent = "#3ddc97"; status_bg = "#0f1419"
        else:
            tabrow_bg = "#e4e6ea"; tab_bg = "#d8dae0"; tab_sel = "#ffffff"
            tab_hover = "#cfd2d8"; text = "#1a1a1a"; text_sel = "#000000"
            addr_bg = "#ffffff"; addr_border = "#c8ccd2"; addr_focus = "#0078d4"
            btn_bg = "#e0e0e0"; accent = "#0078d4"; status_bg = "#f2f2f2"
        # tab row
        for w in self.findChildren(QWidget):
            if w.objectName() == "tabrow":
                w.setStyleSheet(f"background:{tabrow_bg};")
        self._tabbar.setStyleSheet(f"""
            QTabBar::tab {{ background:{tab_bg}; color:{text}; padding:6px 14px;
                margin-right:2px; border-top-left-radius:8px; border-top-right-radius:8px;
                min-width:120px; max-width:220px; }}
            QTabBar::tab:selected {{ background:{tab_sel}; color:{text_sel}; }}
            QTabBar::tab:hover {{ background:{tab_hover}; }}
        """)
        self._newtab_btn.setStyleSheet(f"background:{tab_bg}; color:{text}; border:none; border-radius:6px; font-size:16px;")
        for b in (self._back, self._fwd, self._reload, self._blocked_btn, self._settings_btn):
            b.setStyleSheet(f"background:{btn_bg}; color:{text}; border:none; border-radius:6px; padding:6px 10px;")
        self._address.setStyleSheet(f"""
            QLineEdit {{ background:{addr_bg}; color:{text}; border:1px solid {addr_border};
                border-radius:16px; padding:6px 14px; font-size:14px; }}
            QLineEdit:focus {{ border-color:{accent}; }}
        """)
        self._shield.setStyleSheet(f"padding:0 8px; font-weight:600; color:{accent};")
        self._stack.setStyleSheet(f"background:{status_bg};")
        self.statusBar().setStyleSheet(f"background:{status_bg}; color:{text};")
        # app palette
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor
        from PySide6.QtCore import QUrl
        app = QApplication.instance()
        if app and hasattr(app, "_apply_theme"):
            app._apply_theme(theme)
        # Re-render ALL internal pages so they pick up the new theme.
        from PySide6.QtCore import QUrl
        for info in self._tabs:
            if info is None:
                continue
            pg = info["page"]
            if pg.url().scheme() != "pri":
                continue
            host = pg.url().host().lower()
            try:
                if host == "newtab":
                    pg.setHtml(pg._newtab_html(), baseUrl=QUrl("pri://newtab"))
                elif host == "settings":
                    pg.setHtml(pg._settings_html(), baseUrl=QUrl("pri://settings"))
                elif host == "blocked":
                    # re-render blocked with current data
                    pg.setHtml(self._build_blocked_html(self._pending), baseUrl=QUrl("pri://blocked"))
            except Exception:
                pass

    # ---- tab management ----
    def new_tab(self, url="pri://newtab"):
        page = PriPage(self._profile, self._config, self._report)
        page.new_tab_requested.connect(self.new_tab)
        page.blocked_page_requested.connect(lambda: self._render_blocked(page))
        view = PriView(page)
        page.loadStarted.connect(lambda: self._on_load_started(page))
        page.loadProgress.connect(lambda p: self._on_progress(page, p))
        page.loadFinished.connect(lambda ok: self._on_load_finished(page, ok))
        page.urlChanged.connect(lambda u: self._on_url_changed(page, u))
        page.titleChanged.connect(lambda t: self._on_title_changed(page, t))

        self._stack.addWidget(view)
        idx = self._tabbar.addTab("New tab")
        self._tabbar.setTabData(idx, len(self._tabs))
        self._tabs.append({"page": page, "view": view, "title": "New tab"})
        self._tabbar.setCurrentIndex(idx)
        self._stack.setCurrentWidget(view)

        if url.startswith("pri://"):
            QTimer.singleShot(0, lambda p=page, u=url: p._handle_internal(QUrl(u)))
        else:
            page.setUrl(QUrl(url))

    def _close_tab(self, index):
        if self._tabbar.count() <= 1:
            return
        tab_idx = self._tabbar.tabData(index)
        if tab_idx is None or tab_idx >= len(self._tabs):
            return
        info = self._tabs[tab_idx]
        # remove from stack
        self._stack.removeWidget(info["view"])
        info["view"].deleteLater()
        # mark slot as None (keep indices stable-ish) — simpler: remove and rebuild
        # We'll just remove the tabbar tab and the slot
        self._tabbar.removeTab(index)
        self._tabs[tab_idx] = None
        # fix tab data indices
        self._reindex_tabs()

    def _reindex_tabs(self):
        # rebuild _tabs list without None, fix tabbar data
        new_tabs = [t for t in self._tabs if t is not None]
        # map old positions
        self._tabs = new_tabs
        for i in range(self._tabbar.count()):
            self._tabbar.setTabData(i, i)

    def _close_current_tab(self):
        self._close_tab(self._tabbar.currentIndex())

    def _current_index(self):
        return self._tabbar.currentIndex()

    def _current_tab_info(self):
        idx = self._tabbar.currentIndex()
        if idx < 0 or idx >= len(self._tabs):
            return None
        data = self._tabbar.tabData(idx)
        if data is None or data >= len(self._tabs):
            return None
        return self._tabs[data]

    def _current_page(self):
        info = self._current_tab_info()
        return info["page"] if info else None

    def _cv(self):
        info = self._current_tab_info()
        return info["view"] if info else None

    # ---- signals ----
    def _on_load_started(self, page):
        page._pri_handled = False
        self._status.setText("Loading…")

    def _on_progress(self, page, progress):
        if page is self._current_page():
            self._status.setText(f"Loading {progress}%")

    def _on_load_finished(self, page, ok):
        if page is self._current_page():
            if page.url().scheme() == "pri" or getattr(page, "_pri_handled", False):
                self._status.setText("Done")
                page._pri_handled = False
            else:
                self._status.setText("Done" if ok else "Failed to load")

    def _on_url_changed(self, page, url):
        if page is self._current_page():
            self._address.setText(url.toString())
            self._current_page_url = url.toString()
            # Track current host for third-party cookie blocking.
            try:
                import PySide6.QtWidgets as _w
                app = _w.QApplication.instance()
                # store on app for access by cookie store callback
                host = url.host().lower()
                if not hasattr(app, "_pri_current_host"):
                    app._pri_current_host = {"host": ""}
                app._pri_current_host["host"] = host
            except Exception:
                pass

    def _on_title_changed(self, page, title):
        for i in range(self._tabbar.count()):
            data = self._tabbar.tabData(i)
            if data is not None and data < len(self._tabs) and self._tabs[data] and self._tabs[data]["page"] is page:
                self._tabbar.setTabText(i, (title or "New tab")[:24])
                if self._tabs[data]:
                    self._tabs[data]["title"] = title or "New tab"
                break

    def _on_tab_changed(self, index):
        info = self._current_tab_info()
        if info:
            page = info["page"]
            self._address.setText(page.url().toString())
            self._current_page_url = page.url().toString()
            self._stack.setCurrentWidget(info["view"])
        self._update_shield()

    # ---- nav ----
    def _navigate_address(self):
        text = self._address.text().strip()
        if not text:
            return
        if "://" not in text and "." not in text.split("/")[0]:
            # Reload config from disk so settings changes always take effect.
            from .config import Config
            fresh = Config.load()
            self._config.search_template = fresh.search_template
            url = self._config.search_template.format(query=text.replace(" ", "+"))
        elif "://" not in text:
            url = "https://" + text
        else:
            url = text
        view = self._cv()
        if view:
            view.setUrl(QUrl(url))

    def _reload_or_stop(self):
        view = self._cv()
        if view:
            view.reload()

    # ---- report ----
    def _drain_report(self):
        new = self._report.drain()
        if new:
            self._pending.extend(new)
            if len(self._pending) > 2000:
                self._pending = self._pending[-2000:]
        self._update_shield()
        page = self._current_page()
        if page is not None and page.url().scheme() == "pri" and page.url().host() == "blocked":
            if len(self._pending) != self._last_blocked_render:
                self._last_blocked_render = len(self._pending)
                self._render_blocked(page)

    def _page_blocked_count(self, page_url):
        return sum(1 for e in self._pending if e.kind == "block" and e.page_url == page_url)

    def _update_shield(self):
        n = self._page_blocked_count(self._current_page_url)
        self._shield.setText(f"🛡 {n}")
        total = sum(1 for e in self._pending if e.kind == "block")
        self._counts.setText(f"blocked: {total}")

    def _open_blocked(self):
        self.new_tab("pri://blocked")

    def _render_blocked(self, page):
        page.setHtml(self._build_blocked_html(self._pending), baseUrl=QUrl("pri://blocked"))

    def _build_blocked_html(self, events):
        from .ui.theme import colors as _colors
        c = _colors(self._config.theme)
        blocks = [e for e in events if e.kind == "block"]
        cleans = [e for e in events if e.kind == "clean"]
        headers = [e for e in events if e.kind == "header"]
        from collections import Counter
        reasons = Counter(e.reason for e in blocks)
        reason_rows = "".join(f"<tr><td>{html.escape(r)}</td><td>{n}</td></tr>" for r, n in sorted(reasons.items(), key=lambda x: -x[1]))
        block_rows = "".join(
            f"<tr><td>{html.escape(e.resource_type)}</td><td class='host'>{html.escape(e.host)}</td>"
            f"<td>{html.escape(e.reason)}</td><td class='muted'>{html.escape(_short(e.page_url))}</td></tr>"
            for e in reversed(blocks[-200:]))
        clean_rows = "".join(f"<tr><td class='host'>{html.escape(e.url)}</td><td>{html.escape(', '.join(e.stripped))}</td></tr>" for e in reversed(cleans[-50:]))
        header_rows = "".join(f"<tr><td class='host'>{html.escape(e.host)}</td><td>{html.escape(', '.join(e.stripped))}</td></tr>" for e in reversed(headers[-50:]))
        return f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;padding:24px;font-family:Segoe UI,system-ui,sans-serif;background:{c['bg']};color:{c['text']}}}
h1{{color:{c['accent']};margin-top:0}}h2{{margin-top:28px;border-bottom:1px solid {c['border']};padding-bottom:6px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}}
.card{{background:{c['card']};border:1px solid {c['border']};border-radius:10px;padding:14px}}
.card .n{{font-size:28px;font-weight:700;color:{c['accent']}}}.card .l{{color:{c['muted']};font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid {c['border']};vertical-align:top}}
th{{color:{c['muted']};font-weight:600}}.host{{color:#7dd3fc;word-break:break-all}}
.muted{{color:{c['muted']};font-size:12px;word-break:break-all}}
input{{padding:8px 12px;border-radius:6px;border:1px solid {c['border']};background:{c['input']};color:{c['text']};width:320px}}
a{{color:{c['accent']}}}</style>
<script>function filt(){{const q=document.getElementById('q').value.toLowerCase();
document.querySelectorAll('tbody tr').forEach(r=>{{r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'}});}}</script>
</head><body>
<h1>Blocked by Pri</h1><p class="muted">Everything Pri refused to load.</p>
<div class="cards">
<div class="card"><div class="n">{len(blocks)}</div><div class="l">requests blocked</div></div>
<div class="card"><div class="n">{len(cleans)}</div><div class="l">URLs cleaned</div></div>
<div class="card"><div class="n">{len(headers)}</div><div class="l">header sets stripped</div></div>
<div class="card"><div class="n">{len(reasons)}</div><div class="l">distinct reasons</div></div>
</div>
<input id="q" placeholder="filter…" oninput="filt()">
<h2>By reason</h2>
<table><thead><tr><th>reason</th><th>count</th></tr></thead><tbody>{reason_rows or '<tr><td colspan=2 class=muted>nothing yet</td></tr>'}</tbody></table>
<h2>Blocked requests</h2>
<table><thead><tr><th>type</th><th>host</th><th>reason</th><th>page</th></tr></thead><tbody>{block_rows or '<tr><td colspan=4 class=muted>nothing yet</td></tr>'}</tbody></table>
<h2>Cleaned URLs</h2>
<table><thead><tr><th>url</th><th>removed params</th></tr></thead><tbody>{clean_rows or '<tr><td colspan=2 class=muted>nothing yet</td></tr>'}</tbody></table>
<h2>Stripped headers</h2>
<table><thead><tr><th>host</th><th>removed</th></tr></thead><tbody>{header_rows or '<tr><td colspan=2 class=muted>nothing yet</td></tr>'}</tbody></table>
<p style="margin-top:24px"><a href="pri://newtab">← New tab</a></p>
</body></html>"""


def _short(url):
    if not url: return ""
    try:
        p = urlparse(url)
        return (p.netloc + p.path)[:60]
    except Exception:
        return url[:60]
