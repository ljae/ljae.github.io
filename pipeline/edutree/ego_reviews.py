"""Ego Lite 공개 검색 결과 수집. 원문 방문·본문 저장·브라우저 재점유는 하지 않는다.

``collect(query, academy_id, space_id, ...)`` returns a dict with ``status``,
``rows``, ``query`` and ``error_code``. Only ``ok`` and ``empty`` are successful;
all other statuses contain no rows. The caller owns one existing TaskSpace and
must stop on failures, especially user_control/blocked/login_required/timeout.
The caller also owns normal relevance, branch, advertisement and policy gates:
these are unverified raw mentions, never pre-approved ranking evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ego_reviews.mjs"
MARKER = "EDUTREE_EGO_REVIEWS_JSON:"
FAILURES = frozenset({"cli_missing", "timeout", "blocked", "login_required",
                      "user_control", "browser_error", "parse_error"})
MAX_RESULTS = 50
MAX_SNIPPET = 600
MAX_TITLE = 200


def _search_url(query: str, source: str) -> str:
    tab = "tab.blog.all" if source == "naver_blog" else "tab.cafe.all"
    return "https://search.naver.com/search.naver?" + urlencode({"ssc": tab, "query": query})


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def canonical_url(value: str) -> str | None:
    """Only known public Naver article URL forms; discard tracking parameters.

    Cafe numeric-club and named-club paths cannot be equated without evidence.
    They deliberately stay separate rather than guessing a club identifier.
    """
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        p = urlsplit(value.strip())
        if (p.scheme not in {"http", "https"} or p.username or p.password
                or p.port or re.search(r"[\x00-\x20]", value)):
            return None
        host = (p.hostname or "").lower()
        q = parse_qs(p.query)
        if host in {"blog.naver.com", "m.blog.naver.com"}:
            match = re.fullmatch(r"/([A-Za-z0-9_-]+)/(\d+)/?", p.path)
            if match:
                return f"https://blog.naver.com/{match[1]}/{match[2]}"
            if p.path.lower() == "/postview.naver":
                author, number = q.get("blogId", [""])[0], q.get("logNo", [""])[0]
                if re.fullmatch(r"[A-Za-z0-9_-]+", author) and number.isascii() and number.isdigit():
                    return f"https://blog.naver.com/{author}/{number}"
        if host in {"cafe.naver.com", "m.cafe.naver.com"}:
            match = re.fullmatch(r"/([A-Za-z0-9_-]+)/(\d+)/?", p.path)
            if match:
                return f"https://cafe.naver.com/{match[1]}/{match[2]}"
            match = re.fullmatch(r"/ca-fe/(?:web/)?cafes/(\d+)/articles/(\d+)/?", p.path)
            if match:
                return f"https://cafe.naver.com/ca-fe/cafes/{match[1]}/articles/{match[2]}"
            if p.path.lower() in {"/articleread.nhn", "/articleread.naver"}:
                club, article = q.get("clubid", [""])[0], q.get("articleid", [""])[0]
                if all(s.isascii() and s.isdigit() for s in (club, article)):
                    return f"https://cafe.naver.com/ca-fe/cafes/{club}/articles/{article}"
    except (ValueError, TypeError):
        pass
    return None


def publication_date(value: str | None, *, today: date | None = None,
                     now: datetime | None = None) -> str | None:
    """Parse only the result's separate visible date label, never snippet text."""
    # Historical date-only replay cannot resolve hours/minutes across midnight.
    reference = now or (datetime.now(ZoneInfo("Asia/Seoul")) if today is None else None)
    today = today or reference.date()
    if not isinstance(value, str):
        return None
    label = value.strip()
    match = re.fullmatch(r"(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\.?", label)
    try:
        if match:
            parsed = date(*(int(part) for part in match.groups()))
        elif match := re.fullmatch(r"(\d{1,4})\s*일\s*전", label):
            parsed = today - timedelta(days=int(match[1]))
        elif match := re.fullmatch(r"(\d{1,3})\s*(시간|분|초)\s*전", label):
            if reference is None:
                return None
            seconds = int(match[1]) * {"시간": 3600, "분": 60, "초": 1}[match[2]]
            parsed = (reference - timedelta(seconds=seconds)).date()
        elif re.fullmatch(r"오늘|방금(?:\s*전)?", label):
            parsed = today
        elif label == "어제":
            parsed = today - timedelta(days=1)
        else:
            return None
    except (ValueError, OverflowError):
        return None
    return parsed.isoformat() if parsed <= today else None


def _text(value: object, limit: int) -> str:
    # Browser innerText is already plain text. HTML stripping would erase a
    # literal academy name such as '<생각하는 황소>' from a public result title.
    return re.sub(r"\s+", " ", value if isinstance(value, str) else "").strip()[:limit]


def normalize_item(item: dict, *, academy_id: str, query: str,
                   academy_name: str = "", region_id: str = "",
                   today: date | None = None) -> dict | None:
    """Whitelist fields; do not retain raw author names, HTML or full bodies."""
    if not isinstance(item, dict):
        return None
    url = canonical_url(item.get("url"))
    title = _text(item.get("title"), MAX_TITLE)
    if not url or not title:
        return None
    blog = urlsplit(url).hostname == "blog.naver.com"
    posted = publication_date(item.get("date_text"), today=today)
    row = {
        "source": "naver_blog" if blog else "naver_cafe",
        "source_url": url,
        "url_hash": _hash(url),
        # Same scheme as naver._author_hash(bloggerlink); communities != authors.
        "author_hash": _hash(url.rsplit("/", 1)[0]) if blog else None,
        "title": title,
        "snippet": _text(item.get("snippet"), MAX_SNIPPET),
        "posted_at": posted,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "collector": "ego_lite",
        "search_url": _search_url(query, "naver_blog" if blog else "naver_cafe"),
        "query": query,
        "academy_key": str(academy_id),
        "academy_name": academy_name,
        "region_id": region_id,
    }
    if posted:
        row["date_source"] = "ego_search"
    return row


def _error_status(message: str) -> str:
    message = message.lower()
    if any(s in message for s in ("user_control", "user control", "user-owned", "ownership",
                                   "inactive", "unassigned", "not agent-owned", "사용자 제어")):
        return "user_control"
    if any(s in message for s in ("captcha", "robot", "blocked", "access denied", "자동입력", "접근 제한")):
        return "blocked"
    if any(s in message for s in ("login_required", "login required", "sign in required", "로그인이 필요")):
        return "login_required"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    return "browser_error"


def collect(query: str, academy_id: str, space_id: int, *, academy_name: str = "",
            region_id: str = "", source: str = "naver_blog", max_results: int = 20,
            timeout: float = 45) -> dict:
    """Read one bounded search page in the supplied space's p1 (no retries).

    This method never creates, claims or finishes TaskSpaces. Calls sharing a
    space must be sequential. A caller must not turn a failure into an empty
    successful collection or retry by creating a different space.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError("query must be nonempty and at most 300 characters")
    if not str(academy_id).strip() or isinstance(space_id, bool) or not isinstance(space_id, int) or space_id < 1:
        raise ValueError("academy_id and a positive existing space_id are required")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 5 <= timeout <= 90:
        raise ValueError("timeout must be between 5 and 90 seconds")
    if source not in {"naver_blog", "naver_cafe"}:
        raise ValueError("source must be naver_blog or naver_cafe")
    query = query.strip()
    base = {"query": query, "academy_id": str(academy_id), "rows": []}

    def fail(status: str) -> dict:
        return {**base, "status": status, "error_code": status}

    options = {"query": query, "spaceId": space_id, "limit": max_results,
               "source": source, "searchUrl": _search_url(query, source),
               "timeoutMs": max(1000, int((timeout - 2) * 1000))}
    try:
        script = "const __EDUTREE_EGO_OPTIONS__ = " + json.dumps(options, ensure_ascii=False) + ";\n" + SCRIPT.read_text(encoding="utf-8")
    except OSError:
        return fail("browser_error")
    try:
        result = subprocess.run(["ego-browser", "nodejs"], input=script,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, check=False,
                                shell=False)
    except FileNotFoundError:
        return fail("cli_missing")
    except subprocess.TimeoutExpired:
        return fail("timeout")
    except OSError:
        return fail("browser_error")
    if result.returncode:
        return fail(_error_status((result.stderr or "") + "\n" + (result.stdout or "")))
    # Ego Lite 0.5.1 routes Node console.log to stderr when called with pipes.
    # Read the explicit protocol marker from either stream; ignore notices.
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    payloads = [line[len(MARKER):] for line in output.splitlines() if line.startswith(MARKER)]
    if len(payloads) != 1 or len(payloads[0]) > 200_000:
        return fail("parse_error")
    try:
        payload = json.loads(payloads[0])
    except (TypeError, ValueError):
        return fail("parse_error")
    if not isinstance(payload, dict) or payload.get("status") not in FAILURES | {"ok", "empty"}:
        return fail("parse_error")
    if payload["status"] in FAILURES:
        return fail(payload["status"])
    raw = payload.get("rows")
    if not isinstance(raw, list) or len(raw) > max_results or (payload["status"] == "empty" and raw):
        return fail("parse_error")
    rows, seen = [], set()
    for item in raw:
        row = normalize_item(item, academy_id=str(academy_id), query=query,
                             academy_name=academy_name, region_id=region_id)
        if row and row["source"] == source and row["url_hash"] not in seen:
            rows.append(row)
            seen.add(row["url_hash"])
    if (raw or payload["status"] == "ok") and not rows:
        return fail("parse_error")
    return {**base, "status": "ok" if rows else "empty", "rows": rows,
            "error_code": None, "rejected_count": len(raw) - len(rows),
            "search_url": _search_url(query, source),
            "update_available": "[ego-browser:notice]" in output}
