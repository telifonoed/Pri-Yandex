"""Headless verification of Pri's fingerprint spoofing (uses the real pri/js files)."""
import os, sys, json
from pathlib import Path

# Make the repo importable regardless of where this file lives.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pri.paths import pin_environment, PROJECT_ROOT
pin_environment()
import os as _os
_os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    _os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    + " --force-webrtc-ip-handling-policy=disable_non_proxied_udp --block-third-party-cookies"
)

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineScript

JS_DIR = PROJECT_ROOT / "pri" / "js"

app = QApplication([])
profile = QWebEngineProfile("fp-test")
profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)

def add(name, src):
    code = src if "\n" in src else (JS_DIR / src).read_text(encoding="utf-8")
    sc = QWebEngineScript()
    sc.setName(name)
    sc.setSourceCode(code)
    sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    sc.setRunsOnSubFrames(True)
    profile.scripts().insert(sc)

add("pri-fingerprint", "fingerprint.js")
add("pri-cookie-lock", "cookielock.js")
add("pri-dnt-gpc", "dntgpc.js")

store = profile.cookieStore()
def _kill(c):
    store.deleteCookie(c)
store.cookieAdded.connect(_kill)

PROBE = r"""
(function(){
  var c = document.createElement('canvas');
  var gl = c.getContext('webgl');
  var out = {
    webdriver: (typeof navigator.webdriver === 'undefined') ? 'UNDEFINED' : String(navigator.webdriver),
    cores: navigator.hardwareConcurrency,
    mem: navigator.deviceMemory,
    plugins: navigator.plugins.length,
    mime: navigator.mimeTypes.length,
    dnt: navigator.doNotTrack,
    gpc: navigator.globalPrivacyControl,
    cookieEnabled: navigator.cookieEnabled,
    dbgExt: (function(){ try{ var g=document.createElement('canvas').getContext('webgl');
        return g.getExtension('WEBGL_debug_renderer_info'); }catch(e){ return 'err'; } })(),
    vendor: null, renderer: null, maxTex: null,
    fonts: (function(){ try { return [document.fonts.check('12px Arial'),
        document.fonts.check('12px Wingdings'), document.fonts.check('12px NoSuchFontXYZ')]; }catch(e){ return 'err'; } })()
  };
  if (gl) {
    out.vendor = gl.getParameter(gl.VENDOR);
    out.renderer = gl.getParameter(gl.RENDERER);
    out.maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  }
  var cv = document.createElement('canvas'); cv.width=200; cv.height=20;
  var cx = cv.getContext('2d'); cx.textBaseline='top'; cx.font='14px Arial';
  cx.fillText('Pri-FP-test', 2, 2);
  out.canvas = cv.toDataURL().slice(-44);
  // audio signature
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    var ac = new AC();
    var osc = ac.createOscillator(); var an = ac.createAnalyser();
    osc.connect(an); osc.frequency.value = 10000; osc.type='triangle';
    an.fftSize = 2048; osc.start(0);
    var arr = new Float32Array(an.frequencyBinCount);
    an.getFloatFrequencyData(arr);
    var sig = 0; for (var i=0;i<arr.length;i++){ sig += arr[i]; }
    out.audio = sig.toFixed(6);
  } catch(e){ out.audio = 'err:'+e.message; }
  return JSON.stringify(out);
})()
"""

page = QWebEnginePage(profile)
results = []
def probe():
    page.runJavaScript(PROBE, lambda r: results.append(r))
def on_load(ok):
    QTimer.singleShot(500, probe)
    QTimer.singleShot(1400, probe)
    QTimer.singleShot(3000, app.quit)
page.loadFinished.connect(on_load)
page.setUrl(QUrl("https://example.com"))
QTimer.singleShot(25000, app.quit)
app.exec()

print("=== probe results ===")
for i, r in enumerate(results):
    if not r:
        print(i, "EMPTY"); continue
    try:
        d = json.loads(r)
    except Exception:
        print(i, "RAW:", str(r)[:200]); continue
    print(f"--- probe {i} ---")
    for k, v in d.items():
        print(f"  {k}: {v}")