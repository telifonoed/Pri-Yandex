import http.server, socketserver, threading, time, os, sys
sys.path.insert(0, "D:/Pri-yandex")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PORT = 8790
RECORDS = {"requests": [], "lock": threading.Lock()}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with RECORDS["lock"]:
            RECORDS["requests"].append({"path": self.path, "headers": dict(self.headers)})
        body = b"<html><body>ok<img src='/pixel.gif'></body></html>"
        if self.path.startswith("/pixel"):
            body = b"GIF89a"
        self.send_response(200)
        self.send_header("Content-Type", "image/gif" if self.path.startswith("/pixel") else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
time.sleep(0.3)

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile

from pri.config import Config
from pri.page import PriPage
from pri.privacy.interceptor import PrivacyInterceptor
from pri.privacy.report import BlockedRegistry
from pri.privacy.rules import load_default_rules, RuleSet, Rule, RuleKind

app = QApplication([])
profile = QWebEngineProfile("test")
cfg = Config()
reg = BlockedRegistry()
rules = load_default_rules()
extra = RuleSet()
extra.rules.append(Rule(RuleKind.HOSTPATH, "127.0.0.1/pixel", "tracker", "test"))
rules = rules.merged(extra)
interceptor = PrivacyInterceptor(cfg, rules, reg)
profile.setUrlRequestInterceptor(interceptor)

page = PriPage(profile, cfg, reg)
state = {"loaded": False, "url": None, "done": False}

events = []
def on_finished(ok):
    events.append((ok, page.url().toString()))
    state["url"] = page.url().toString()
    state["loaded"] = ok

page.loadFinished.connect(on_finished)
target = f"http://127.0.0.1:{PORT}/page.html?utm_source=news&fbclid=abc&keep=1"
page.setUrl(QUrl(target))
QTimer.singleShot(6000, app.quit)
app.exec()

httpd.shutdown()

with RECORDS["lock"]:
    reqs = list(RECORDS["requests"])
print("=== requests received ===")
for r in reqs:
    print(r["path"])
    print("   Referer:", r["headers"].get("Referer"))
    print("   DNT:", r["headers"].get("DNT"))
    print("   Sec-GPC:", r["headers"].get("Sec-GPC"))
print("=== final url ===", state["url"])
print("=== blocked events ===")
for e in reg.snapshot():
    print(e.kind, e.reason, (e.url if e.kind=="block" else e.stripped))
pixel_seen = any("/pixel" in r["path"] for r in reqs)
print("pixel reached server (should be False):", pixel_seen)
print("utm cleaned (final url no utm):", "utm_source" not in (state["url"] or ""))
print("keep preserved:", "keep=1" in (state["url"] or ""))
print("header stripped events:", sum(1 for e in reg.snapshot() if e.kind=="header"))
