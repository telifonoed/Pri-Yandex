import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from .paths import CONFIG_PATH

@dataclass
class Config:
    block_trackers: bool = True
    block_ads: bool = True
    clean_urls: bool = True
    strip_headers: bool = True
    block_speculative: bool = True
    deny_permissions: bool = True
    safe_browsing: bool = True
    dns_prefetch: bool = False
    block_scripts: bool = False
    block_fingerprinting: bool = True
    block_cookie_popups: bool = True
    block_third_party_cookies: bool = True
    block_all_cookies: bool = False
    dnt_enabled: bool = True
    gpc_enabled: bool = True
    webrtc_policy: str = "disable_non_proxied_udp"
    search_template: str = "https://duckduckgo.com/?q={query}"
    search_engine: str = "duckduckgo"
    home_page: str = "pri://newtab"
    theme: str = "dark"
    allowlist: list = field(default_factory=list)
    blocklist: list = field(default_factory=list)

    @classmethod
    def load(cls, path=None):
        path = path or CONFIG_PATH
        cfg = cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        names = {f.name for f in fields(cls)}
        for k, v in raw.items():
            if k in names:
                setattr(cfg, k, v)
        cfg.allowlist = [str(s).lower() for s in cfg.allowlist]
        cfg.blocklist = [str(s).lower() for s in cfg.blocklist]
        return cfg

    def save(self, path=None):
        path = path or CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
