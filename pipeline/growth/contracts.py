"""Versioned, dimension-aware search data contracts (no third-party dependencies)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def stable_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def normalize_query(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).lower().split())


def normalize_url(value: str) -> str:
    """Preserve meaningful paths, query strings, and app fragments."""
    p = urlsplit(value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("INVALID_URL")
    host = p.hostname.lower()
    port = p.port
    if port and (p.scheme, port) not in (("http", 80), ("https", 443)):
        host += f":{port}"
    return urlunsplit((p.scheme.lower(), host, p.path or "/", p.query, p.fragment))


@dataclass(frozen=True)
class Metrics:
    clicks: int
    impressions: int
    position_numerator: float = 0

    def __post_init__(self):
        if self.clicks < 0 or self.impressions < self.clicks:
            raise ValueError("INVALID_METRICS")
        if not math.isfinite(self.position_numerator) or self.position_numerator < 0:
            raise ValueError("INVALID_POSITION")

    @property
    def ctr(self):
        return self.clicks / self.impressions if self.impressions else None

    @property
    def position(self):
        return self.position_numerator / self.impressions if self.impressions else None

    def to_dict(self):
        return dict(asdict(self), ctr=self.ctr, position=self.position)


def aggregate(rows: list[dict]) -> Metrics:
    return Metrics(sum(r["clicks"] for r in rows), sum(r["impressions"] for r in rows),
                   sum(r.get("position_numerator", 0) for r in rows))
