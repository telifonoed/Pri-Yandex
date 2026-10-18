import enum
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass
class Rule:
    kind: str
    pattern: str
    reason: str
    raw: str

@dataclass
class Match:
    rule: Rule
    reason: str

class RuleKind:
    HOST = "host"
    HOSTPATH = "hostpath"
    SUBSTRING = "substring"
    REGEX = "regex"
    TYPE = "type"

@dataclass
class RuleSet:
    rules: list = field(default_factory=list)
    exceptions: list = field(default_factory=list)
    source: str = "<memory>"

    @classmethod
    def from_lines(cls, lines, source="<memory>"):
        rs = cls(source=source)
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("!") or line.startswith("#"):
                continue
            if line.startswith("@@"):
                r = _parse(line[2:].strip())
                if r: rs.exceptions.append(r)
                continue
            r = _parse(line)
            if r: rs.rules.append(r)
        return rs

    @classmethod
    def from_file(cls, path):
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError:
            return cls(source=str(path))
        return cls.from_lines(lines, source=str(path))

    def merged(self, other):
        out = RuleSet(source=f"{self.source}+{other.source}")
        out.rules = list(self.rules) + list(other.rules)
        out.exceptions = list(self.exceptions) + list(other.exceptions)
        return out

    def match(self, url, resource_type=""):
        text = url.toString() if hasattr(url, "toString") else str(url)
        parts = urlsplit(text)
        host = (parts.hostname or "").lower().rstrip(".")
        path = parts.path or "/"
        full = ((parts.hostname or "") + parts.path + (("?" + parts.query) if parts.query else "")).lower()
        # exceptions
        for exc in self.exceptions:
            if _matches(exc, host, path, full, resource_type):
                return None
        for rule in self.rules:
            if _matches(rule, host, path, full, resource_type):
                return Match(rule=rule, reason=rule.reason)
        return None

def _parse(line):
    line = line.strip()
    if not line:
        return None
    if line.startswith("||"):
        body = line[2:].split("^", 1)[0]
        if "/" in body:
            return Rule(RuleKind.HOSTPATH, body.lower(), "tracker", line)
        return Rule(RuleKind.HOST, body.lower(), "tracker", line)
    if line.startswith("/") and line.endswith("/") and len(line) > 2:
        return Rule(RuleKind.REGEX, line[1:-1], "pattern", line)
    if line.lower().startswith("type:"):
        return Rule(RuleKind.TYPE, line[5:].strip().lower(), "speculative", line)
    return Rule(RuleKind.SUBSTRING, line.lower(), "substring", line)

def _is_subdomain(host, domain):
    host = host.lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)

def _matches(rule, host, path, full, resource_type):
    if rule.kind == RuleKind.HOST:
        return _is_subdomain(host, rule.pattern)
    if rule.kind == RuleKind.HOSTPATH:
        if "/" in rule.pattern:
            ph, pp = rule.pattern.split("/", 1)
            pp = "/" + pp.lstrip("/")
            return _is_subdomain(host, ph) and path.lower().startswith(pp.lower())
        return _is_subdomain(host, rule.pattern)
    if rule.kind == RuleKind.SUBSTRING:
        return rule.pattern in full
    if rule.kind == RuleKind.REGEX:
        try:
            return re.search(rule.pattern, full) is not None
        except re.error:
            return False
    if rule.kind == RuleKind.TYPE:
        return resource_type.lower() == rule.pattern
    return False

def load_default_rules():
    base = Path(__file__).parent / "lists" / "trackers.txt"
    return RuleSet.from_file(base)
