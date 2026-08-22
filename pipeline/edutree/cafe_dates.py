"""카페 글 날짜 보강 — 목록 페이지 기반.

왜 이 모듈이 필요한가
    카페글 검색 API 는 날짜를 주지 않는다. 실측에서 수집한 카페 글의 91%가
    날짜 없이 들어왔고, 화제성(20%) 기둥이 나머지 9%로 계산되고 있었다.

왜 개별 글을 열지 않는가
    12,233건을 하나씩 열면 13시간이 걸리고 차단이 거의 확실하다. 목록
    페이지는 한 번에 10~30건의 (링크, 날짜) 쌍을 준다. 같은 정보를 3% 의
    트래픽으로 얻는다.

수집 방식
    이 모듈은 직접 접속하지 않는다. 브라우저에서 저장한 검색 결과 페이지를
    읽거나(방식 A), 이미 로그인된 브라우저를 사람이 보는 앞에서 천천히
    움직이는 경로(방식 B)만 제공한다. cafe_local.py 와 같은 원칙이다.

산출물
    {url_hash: "YYYY-MM-DD"} 매핑. 본문은 저장하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

CACHE = config.CACHE_DIR / "cafe_dates.json"

# 목록 페이지에 섞여 나오는 날짜 표기들
_ABS = re.compile(r"(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})")
_REL_DAY = re.compile(r"(\d+)\s*일\s*전")
_REL_HOUR = re.compile(r"(\d+)\s*시간\s*전")
_TODAY = re.compile(r"오늘|방금|분\s*전")
_LINK = re.compile(r"https?://cafe\.naver\.com/[^\s\"'<>]+")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def parse_date(text: str, today: date | None = None) -> str | None:
    """'2026.03.15' · '3일 전' · '오늘' 을 전부 절대 날짜로 바꾼다."""
    today = today or date.today()
    m = _ABS.search(text)
    if m:
        try:
            return datetime(*(int(g) for g in m.groups())).date().isoformat()
        except ValueError:
            return None
    m = _REL_DAY.search(text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    if _REL_HOUR.search(text) or _TODAY.search(text):
        return today.isoformat()
    return None


_DATE_SPAN = re.compile(
    r">\s*(20\d{2}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2}\.?|\d+\s*일\s*전|\d+\s*시간\s*전|오늘)\s*<")


def parse_listing(html_text: str, window: int = 4000) -> dict[str, str]:
    """목록 페이지 HTML 에서 (카페글 링크 → 날짜) 를 뽑는다.

    행 단위로 끊어 읽는 방식은 실패했다. 네이버 검색 결과는 div 가 깊게
    중첩돼 있어 </div> 로 자르면 링크와 날짜가 다른 조각으로 흩어진다.

    그래서 문서상 '위치'로 짝짓는다. 링크와 날짜의 오프셋을 각각 모은 뒤
    링크 뒤쪽 가장 가까운 날짜를 붙인다. 클래스명에 의존하지 않으므로
    네이버가 마크업을 바꿔도 잘 버틴다.
    """
    links = [(m.start(), m.group(0)) for m in _LINK.finditer(html_text)]
    dates = [(m.start(), m.group(1)) for m in _DATE_SPAN.finditer(html_text)]
    if not links or not dates:
        return {}

    out: dict[str, str] = {}
    seen: set[str] = set()
    for pos, url in links:
        url = url.rstrip('\\"\'>').split("?")[0]
        if url in seen:
            continue
        best = None
        for dpos, dtext in dates:
            gap = dpos - pos
            if 0 <= gap <= window and (best is None or gap < best[0]):
                best = (gap, dtext)
        if best is None:      # 링크 앞쪽도 한 번 본다
            for dpos, dtext in dates:
                gap = pos - dpos
                if 0 <= gap <= window // 2 and (best is None or gap < best[0]):
                    best = (gap, dtext)
        if best:
            parsed = parse_date(best[1])
            if parsed:
                seen.add(url)
                out[_hash(url)] = parsed
    return out


def ingest_saved_pages(directory: str) -> dict[str, str]:
    """방식 A — 브라우저에서 저장한 검색 결과 페이지들을 읽는다."""
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise RuntimeError(f"폴더가 없습니다: {root}")

    found: dict[str, str] = {}
    files = sorted(p for p in root.rglob("*.htm*") if p.is_file())
    for path in files:
        try:
            found.update(parse_listing(path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    print(f"  목록 페이지 {len(files)}개에서 날짜 {len(found):,}건 추출")
    return found


def merge(new_dates: dict[str, str]) -> dict[str, str]:
    cache: dict[str, str] = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    cache.update(new_dates)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def apply(mentions: list[dict]) -> int:
    """캐시된 날짜를 언급에 채워 넣는다. 채운 건수를 돌려준다."""
    if not CACHE.exists():
        return 0
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    filled = 0
    for m in mentions:
        if m.get("posted_at"):
            continue
        got = cache.get(m.get("url_hash", ""))
        if got:
            m["posted_at"] = got
            filled += 1
    return filled


def coverage(mentions: list[dict]) -> str:
    total = len(mentions) or 1
    dated = sum(1 for m in mentions if m.get("posted_at"))
    return f"{dated:,}/{total:,} ({dated / total * 100:.0f}%)"
