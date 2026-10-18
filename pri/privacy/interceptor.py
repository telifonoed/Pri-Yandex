from __future__ import annotations
import time
from urllib.parse import urlsplit
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from .report import BlockedEvent
from .rules import _is_subdomain


STRIP_HEADERS = ("referer", "dnt", "sec-gpc", "x-client-data", "x-purpose", "x-requested-with")


def _rt_name(info):
    try:
        return info.resourceType().name.replace("ResourceType", "").lower() or "other"
    except Exception:
        return "other"


def _rt_value(name):
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo
    scope = QWebEngineUrlRequestInfo.ResourceType
    return getattr(scope, name, None)


class PrivacyInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, config, rules, report):
        super().__init__()
        self._cfg = config
        self._rules = rules
        self._report = report
        self._hardened = set()

    def interceptRequest(self, info):
        try:
            self._handle(info)
        except Exception as exc:
            import sys
            print("interceptor error:", repr(exc), file=sys.stderr)

    def _handle(self, info):
        url = info.requestUrl()
        url_text = url.toString()
        rtype = _rt_name(info)
        page_url = info.firstPartyUrl().toString() or url_text
        host = (urlsplit(url_text).hostname or "").lower()
        # Track current page host for third-party cookie blocking.
        try:
            import PySide6.QtWidgets as _w
            _app = _w.QApplication.instance()
            if _app is not None:
                if not hasattr(_app, "_pri_current_host"):
                    _app._pri_current_host = {"host": ""}
                if page_url:
                    _ph = (urlsplit(page_url).hostname or "").lower()
                    if _ph:
                        _app._pri_current_host["host"] = _ph
        except Exception:
            pass

        page_host = (urlsplit(page_url).hostname or "").lower()

        if any(_is_subdomain(host, d) for d in self._cfg.allowlist):
            return

        # Third-party script blocking.
        if getattr(self._cfg, "block_scripts", False):
            if rtype == "script" and page_host and host and not _is_subdomain(host, page_host) and not _is_subdomain(page_host, host):
                info.block(True)
                self._report.add(BlockedEvent(
                    at=time.time(), url=url_text, host=host,
                    resource_type=rtype, reason="third-party-script", page_url=page_url,
                    kind="block"))
                return
        if any(_is_subdomain(host, d) for d in self._cfg.blocklist):
            info.block(True)
            self._report.add(BlockedEvent(
                at=time.time(), url=url_text, host=host,
                resource_type=rtype, reason="user-blocklist", page_url=page_url,
                kind="block"))
            return

        match = self._rules.match(url, rtype)
        if match is not None:
            info.block(True)
            self._report.add(BlockedEvent(
                at=time.time(), url=url_text, host=host,
                resource_type=rtype, reason=match.reason, page_url=page_url,
                kind="block"))
            return

        if self._cfg.block_speculative:
            pv = _rt_value("ResourceTypePrefetch")
            if pv is not None and info.resourceType() == pv:
                info.block(True)
                self._report.add(BlockedEvent(
                    at=time.time(), url=url_text, host=host,
                    resource_type=rtype, reason="speculative", page_url=page_url,
                    kind="block"))
                return
            if rtype == "ping":
                info.block(True)
                self._report.add(BlockedEvent(
                    at=time.time(), url=url_text, host=host,
                    resource_type=rtype, reason="beacon", page_url=page_url,
                    kind="block"))
                return

        if self._cfg.strip_headers:
            self._rewrite_headers(info, page_url, host, rtype, url_text)

    def _rewrite_headers(self, info, page_url, host, rtype, url_text):
        try:
            headers = info.httpHeaders()
        except Exception:
            headers = {}
        items = list(headers.items()) if isinstance(headers, dict) else list(headers) if isinstance(headers, (list, tuple)) else []
        removed = []
        for key, value in items:
            name = key.decode("latin-1") if isinstance(key, (bytes, bytearray)) else str(key)
            if name.lower() in STRIP_HEADERS:
                removed.append(name)
                try:
                    info.setHttpHeader(key if isinstance(key, (bytes, bytearray)) else name.encode(), b"")
                except Exception:
                    pass
        # Polite signals (independent toggles).
        if getattr(self._cfg, "dnt_enabled", True):
            try:
                info.setHttpHeader(b"DNT", b"1")
            except Exception:
                pass
        if getattr(self._cfg, "gpc_enabled", True):
            try:
                info.setHttpHeader(b"Sec-GPC", b"1")
            except Exception:
                pass
        # Drop referrer entirely.
        try:
            info.setHttpHeader(b"Referer", b"")
        except Exception:
            pass
        # Third-party cookie blocking: strip Cookie header from cross-origin requests.
        if getattr(self._cfg, "block_third_party_cookies", False):
            page_host = (urlsplit(page_url).hostname or "").lower()
            if page_host and host and not _is_subdomain(host, page_host) and not _is_subdomain(page_host, host):
                try:
                    info.setHttpHeader(b"Cookie", b"")
                except Exception:
                    pass
                removed = removed + ["Cookie (3rd-party)"]
        if removed:
            self._report.add(BlockedEvent(
                at=time.time(), url=url_text, host=host,
                resource_type=rtype, reason="header-strip", page_url=page_url,
                stripped=removed, kind="header"))
        # Record one "hardened" entry per page so the panel shows the feature.
        if page_url not in self._hardened:
            self._hardened.add(page_url)
            self._report.add(BlockedEvent(
                at=time.time(), url=url_text, host=host,
                resource_type=rtype, reason="header-harden", page_url=page_url,
                stripped=["Referer (removed)", "DNT: 1", "Sec-GPC: 1"], kind="header"))
