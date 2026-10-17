"""네이버 블로그 본문 수집.

검색 API 는 120자 남짓의 스니펫만 준다. 그 정도로는 감성도 관점도 제대로
읽히지 않는다. 블로그 본문은 로그인 없이 공개돼 있어, 카페와 달리 계정
위험 없이 전문을 가져올 수 있다. 실측에서 스니펫 120자 → 본문 3,500자였다.

카페 본문을 긁지 않는 이유는 docs/SETUP.md 7단계에 적어 두었다.
"""
from __future__ import annotations

import html
import json
import os
import re
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config
from .ego_reviews import canonical_url

VIEW = ("https://blog.naver.com/PostView.naver"
        "?blogId={blog_id}&logNo={log_no}"
        "&redirect=Dlog&widgetTypeCall=true&directAccess=false")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 20
SLEEP = 0.25          # 사람이 읽는 속도에 가깝게. 서두를 이유가 없다.
PER_RUN = 300
BUDGET_SECONDS = 600
MAX_PER_RUN = 2000
MAX_BUDGET_SECONDS = 1800
MAX_WORKERS = 8
CHECKPOINT_EVERY = 50
FAILED_RETRY_DAYS = 7

_URL = re.compile(r"blog\.naver\.com/([^/?#]+)/(\d+)")
_DIV = re.compile(r"<(/?)div\b", re.I)
_DATE_PATTERNS = (
    re.compile(r"se_publishDate[^>]*>([^<]+)<"),
    re.compile(r'"date"\s*:\s*"([^"]+)"'),
    re.compile(r"blog2_container[^>]*>.*?(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)", re.S),
)


def parse_url(url: str) -> tuple[str, str] | None:
    normalized = canonical_url(url)
    m = _URL.search(normalized or "")
    return (m.group(1), m.group(2)) if m else None


def _blog_url(url: str) -> str | None:
    parts = parse_url(url)
    return f"https://blog.naver.com/{parts[0]}/{parts[1]}" if parts else None


def _int_setting(name: str, default: int, maximum: int, *, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, "").strip())
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    """A cancellation during a checkpoint must not destroy the old cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _recent_failures(path: Path, now: datetime) -> dict[str, str]:
    out = {}
    cutoff = now - timedelta(days=FAILED_RETRY_DAYS)
    for url, stamp in _load_json(path).items():
        try:
            attempted = datetime.fromisoformat(stamp)
            if attempted.tzinfo is None:
                attempted = attempted.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        canonical = _blog_url(url)
        if canonical and cutoff < attempted <= now:
            out[canonical] = stamp
    return out


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
           workers: int = 3, *, cached_only: bool = False) -> int:
    """Bound optional body enrichment, retaining cached evidence for every row.

    OPENEDU_BLOG_PER_RUN: 0..2000 (default 300 unique documents).
    OPENEDU_BLOG_BUDGET_SECONDS: 1..1800 (default 600 seconds).
    At the deadline, stop dispatching; at most ``workers`` requests already in
    flight may finish using the existing per-request TIMEOUT. Checkpoint every
    50 completions and on exit, including interruption. Failed documents wait
    seven days before retry; success remains cached until explicitly removed.

    The 2026-10-16 job queued 423,109 mention rows and hit the six-hour CI limit
    before saving any successful bodies. One document can belong to many
    academies: only the download is deduplicated, never the evidence rows.
    """
    deadline = time.monotonic() + _int_setting(
        "OPENEDU_BLOG_BUDGET_SECONDS", BUDGET_SECONDS, MAX_BUDGET_SECONDS, minimum=1)
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError("blog limit must be a nonnegative integer or None")
    cap = min(limit, MAX_PER_RUN) if limit is not None else _int_setting(
        "OPENEDU_BLOG_PER_RUN", PER_RUN, MAX_PER_RUN)
    workers = max(1, min(MAX_WORKERS, int(workers)))
    cache_path = config.CACHE_DIR / "blog_texts.json"
    failure_path = config.CACHE_DIR / "blog_failures.json"
    cache = _load_json(cache_path)
    # Keep legacy keys on disk; add a transient canonical index for lookup.
    by_document = {_blog_url(url): row for url, row in cache.items()
                   if isinstance(row, dict) and _blog_url(url)}
    failures = _recent_failures(failure_path, datetime.now(timezone.utc)) if not cached_only and cap else {}
    targets, seen = [], set()
    if not cached_only and cap:
        for m in mentions:
            if m.get("source") != "naver_blog" or m.get("collector") == "ego_lite":
                continue
            url = _blog_url(m.get("source_url"))
            if not url or url in by_document or url in failures or url in seen:
                continue
            seen.add(url)
            targets.append(url)
            if len(targets) >= cap:
                break
    print(f"  블로그 본문 수집 대상 {len(targets):,}개 문서 "
          f"(회차 상한 {cap:,} · 캐시 {len(cache):,}건 · 실패 대기 {len(failures):,}건)", flush=True)

    if targets:
        done = 0

        def checkpoint():
            _save_json(cache_path, cache)
            _save_json(failure_path, failures)

        def work(url):
            if time.monotonic() >= deadline:
                return False, None
            got = fetch_post(url)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(SLEEP, remaining))
            return True, got

        def remember(future, url):
            nonlocal done
            try:
                attempted, got = future.result()
            except Exception:  # Optional enrichment never blocks scoring on one malformed page.
                attempted, got = True, None
            if not attempted:
                return
            done += 1
            if got:
                cache[url] = by_document[url] = got
                failures.pop(url, None)
            else:
                failures[url] = datetime.now(timezone.utc).isoformat()

        pool = ThreadPoolExecutor(max_workers=workers)
        pending = {}
        queue = iter(targets)
        try:
            while True:
                while len(pending) < workers and time.monotonic() < deadline:
                    url = next(queue, None)
                    if url is None:
                        break
                    pending[pool.submit(work, url)] = url
                if not pending:
                    break
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    url = pending.pop(future)
                    remember(future, url)
                    if done and done % CHECKPOINT_EVERY == 0:
                        checkpoint()
                        print(f"    [{done}/{len(targets)}] 본문 캐시 {len(cache):,}건 저장", flush=True)
        finally:
            # Only a bounded set can be in flight. Preserve successes that
            # finish while an interrupted main thread waits for their shutdown.
            pool.shutdown(wait=True, cancel_futures=True)
            for future, url in pending.items():
                if future.done() and not future.cancelled():
                    try:
                        remember(future, url)
                    except BaseException:
                        pass  # Preserve the original interrupt, without losing other results.
            if done:
                checkpoint()
        if done < len(targets):
            print(f"  블로그 본문 시간 예산 종료: {done}/{len(targets)}개 처리 · 다음 회차로 이월", flush=True)

    filled = 0
    for m in mentions:
        # Browser evidence is a public search excerpt. Do not replace its
        # provenance with an original-page fetch or an old body cache.
        if m.get("collector") == "ego_lite":
            continue
        url = m.get("source_url", "")
        got = cache.get(url) or by_document.get(_blog_url(url))
        if not isinstance(got, dict) or not isinstance(got.get("text"), str):
            continue
        # 스니펫을 본문으로 바꾼다. 감성·관점 분석이 훨씬 정확해진다.
        m["snippet"] = got["text"][:2000]
        m["full_text_length"] = got.get("length", len(got["text"]))
        if got.get("posted_at") and not m.get("posted_at"):
            m["posted_at"] = got["posted_at"]
        filled += 1
    return filled
