"""네이버 블로그 본문 수집.

검색 API 는 120자 남짓의 스니펫만 준다. 그 정도로는 감성도 관점도 제대로
읽히지 않는다. 블로그 본문은 로그인 없이 공개돼 있어, 카페와 달리 계정
위험 없이 전문을 가져올 수 있다. 실측에서 스니펫 120자 → 본문 3,500자였다.

카페 본문을 긁지 않는 이유는 docs/SETUP.md 7단계에 적어 두었다.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from . import config

VIEW = ("https://blog.naver.com/PostView.naver"
        "?blogId={blog_id}&logNo={log_no}"
        "&redirect=Dlog&widgetTypeCall=true&directAccess=false")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 20
SLEEP = 0.25          # 사람이 읽는 속도에 가깝게. 서두를 이유가 없다.

_URL = re.compile(r"blog\.naver\.com/([^/?#]+)/(\d+)")
_DIV = re.compile(r"<(/?)div\b", re.I)
_DATE_PATTERNS = (
    re.compile(r"se_publishDate[^>]*>([^<]+)<"),
    re.compile(r'"date"\s*:\s*"([^"]+)"'),
    re.compile(r"blog2_container[^>]*>.*?(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)", re.S),
)


def parse_url(url: str) -> tuple[str, str] | None:
    m = _URL.search(url or "")
    return (m.group(1), m.group(2)) if m else None


def _extract_block(raw: str, anchor: str) -> str | None:
    """anchor 를 품은 div 를 여는 태그부터 닫는 태그까지 통째로 잘라낸다.

    정규식으로 </div> 를 먼저 만나는 지점까지 자르면 중첩 div 때문에 본문이
    37자만 나온다. depth 를 세는 수밖에 없다.
    """
    m = re.search(anchor, raw)
    if not m:
        return None
    start = raw.rfind("<div", 0, m.end())
    if start < 0:
        return None
    depth, i = 0, start
    while i < len(raw):
        t = _DIV.search(raw, i)
        if not t:
            break
        depth += -1 if t.group(1) else 1
        i = t.end()
        if depth == 0:
            return raw[start:i]
    return raw[start:start + 200_000]


def _to_text(chunk: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", chunk, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</div>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def _parse_date(raw: str) -> str | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(raw)
        if not m:
            continue
        s = m.group(1).strip()
        nums = re.findall(r"\d+", s)
        if len(nums) >= 3:
            try:
                y, mo, d = int(nums[0]), int(nums[1]), int(nums[2])
                if y > 2000:
                    return datetime(y, mo, d).date().isoformat()
            except ValueError:
                continue
    return None


def fetch_post(url: str) -> dict | None:
    parts = parse_url(url)
    if not parts:
        return None
    blog_id, log_no = parts
    try:
        resp = requests.get(VIEW.format(blog_id=blog_id, log_no=log_no),
                            headers={"User-Agent": UA}, timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    raw = resp.text
    chunk = (_extract_block(raw, r'class="[^"]*se-main-container[^"]*"')
             or _extract_block(raw, r'id="postViewArea"'))
    if not chunk:
        return None
    text = _to_text(chunk)
    if len(text) < 60:
        return None
    return {
        "url": url,
        # 본문 전체를 그대로 보관하지 않는다. 분석에 필요한 앞부분만 남긴다.
        "text": text[:4000],
        "length": len(text),
        "posted_at": _parse_date(raw),
    }


def enrich(mentions: list[dict], limit: int | None = None,
           workers: int = 3) -> int:
    """블로그 언급에 본문과 날짜를 채워 넣는다. 채운 건수를 돌려준다."""
    cache_path = config.CACHE_DIR / "blog_texts.json"
    cache: dict[str, dict] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    targets = [m for m in mentions
               if m.get("source") == "naver_blog" and m["source_url"] not in cache]
    if limit:
        targets = targets[:limit]
    print(f"  블로그 본문 수집 대상 {len(targets):,}건 (캐시 {len(cache):,}건)")

    lock = threading.Lock()
    done = 0

    def work(m: dict):
        nonlocal done
        got = fetch_post(m["source_url"])
        time.sleep(SLEEP)
        with lock:
            done += 1
            if got:
                cache[m["source_url"]] = got
            if done % 200 == 0:
                print(f"    [{done}/{len(targets)}] 성공 {len(cache):,}")

    if targets:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for f in as_completed([pool.submit(work, m) for m in targets]):
                f.result()
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    filled = 0
    for m in mentions:
        got = cache.get(m.get("source_url", ""))
        if not got:
            continue
        # 스니펫을 본문으로 바꾼다. 감성·관점 분석이 훨씬 정확해진다.
        m["snippet"] = got["text"][:2000]
        m["full_text_length"] = got["length"]
        if got.get("posted_at") and not m.get("posted_at"):
            m["posted_at"] = got["posted_at"]
        filled += 1
    return filled
