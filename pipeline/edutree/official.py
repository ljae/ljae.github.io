"""공식 홈페이지 수집 — 학원이 스스로 밝히는 것을 학원 페이지에 되적는다.

후기는 남이 하는 말이고 NEIS 는 3년 전 공시일 수 있다. 학원이 자기
사이트에 적은 것(개설 과정·시간표·공지)은 셋 중 가장 최신이고, 무엇보다
**학원 본인의 말**이라 반박당할 여지가 없다.

## 이 모듈이 하지 않는 것

- **URL 을 추측하지 않는다.** NEIS 는 홈페이지 주소를 주지 않는다. 학원
  페이지 frontmatter 의 `homepage:` 에 사람이 적은 것만 읽는다. 이름으로
  검색해 맞히려 들면 남의 사이트를 그 학원 것이라고 적게 된다 —
  '지엘피'·'피아이' 처럼 이름이 겹치는 곳이 이미 많다.
- **robots.txt 가 막으면 읽지 않는다.** 도구를 바꿔 우회하지 않는다.
  스터디홀릭을 수집하지 않기로 한 것과 같은 기준이다(CLAUDE.md).
- **본문을 저장하지 않는다.** 남의 저작물이다. 우리가 남기는 것은 '무엇이
  몇 개 있고 언제 바뀌었나' 라는 관찰뿐이다.

## 왜 변화만 적는가

'개설 과정 12개' 한 줄은 그 자체로는 별것 아니지만, 지난 확인 대비
`+1` 이면 그 학원이 과정을 늘렸다는 뜻이다. 우리가 후기로는 절대 못 잡는
신호이고, 무엇보다 **검증 가능하다** — 출처 URL 과 확인 날짜가 함께 적힌다.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from . import config

CACHE = config.CACHE_DIR / "official.json"
UA = "openedu-bot"
# 사람이 읽는 속도에 가깝게. 학원 홈페이지는 대개 작은 호스팅이다.
SLEEP = 2.0
TIMEOUT = 15
# 한 실행에 볼 곳. 홈페이지가 적힌 학원이 늘어도 야간 작업이 길어지지 않게.
PER_RUN = 40
# 다시 확인하기까지. 학원 홈페이지는 매일 바뀌지 않는다.
REVISIT_DAYS = 14

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_MARKUP = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# 과정·시간표로 볼 낱말. 페이지에 이런 항목이 몇 개 있는지만 센다.
_COURSE_HINTS = ("초등", "중등", "고등", "예비", "정규", "특강", "심화",
                 "선행", "내신", "수능", "레벨", "반편성", "시간표")
_NOTICE_HINTS = ("공지", "안내", "모집", "설명회", "개강")
# 페이지에 보이는 날짜. 한국 사이트는 '2025년 4월 4일'·'2025.04.04'·
# '2025-04-04' 를 섞어 쓴다. 셋을 다 받아 **YYYY-MM-DD 로 맞춰** 적는다 —
# 원문 그대로 두면 '2025년 4월 4' 같은 조각이 위키에 남는다.
_DATE = re.compile(
    r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?")


def _dates(text: str) -> list[str]:
    out = set()
    for y, m, d in _DATE.findall(text):
        month, day = int(m), int(d)
        if 1 <= month <= 12 and 1 <= day <= 31:
            out.add(f"{y}-{month:02d}-{day:02d}")
    return sorted(out)


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(data: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def _allowed(url: str, session) -> tuple[bool, str]:
    """robots.txt 를 **먼저** 본다. 못 읽으면 읽지 않는다.

    robots.txt 가 없는 사이트는 허용으로 본다(표준 해석). 하지만 가져오다
    실패한 것과 없는 것은 다르다 — 실패는 거부로 친다. 서버가 잠깐 죽은
    사이에 마음대로 긁는 셈이 되면 안 된다.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "주소 형식이 아님"
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        r = session.get(robots_url, timeout=TIMEOUT,
                        headers={"User-Agent": UA})
    except Exception as exc:                             # noqa: BLE001
        return False, f"robots.txt 확인 실패 — {type(exc).__name__}"
    if r.status_code == 404:
        return True, "robots.txt 없음"
    if r.status_code >= 400:
        return False, f"robots.txt HTTP {r.status_code}"

    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    if not rp.can_fetch(UA, url) or not rp.can_fetch("*", url):
        return False, "robots.txt 가 거부"
    # Content-Signal(ai-train=no 등)을 명시한 곳도 읽지 않는다.
    if "ai-train=no" in r.text.replace(" ", "").lower():
        return False, "Content-Signal ai-train=no"
    return True, "허용"


def _observe(html: str, base_url: str) -> dict:
    """페이지에서 **세는 것만** 한다. 본문은 남기지 않는다."""
    text = _MARKUP.sub(" ", _TAG.sub(" ", html))
    text = _WS.sub(" ", text)
    links = set(re.findall(r'href=["\']([^"\']+)["\']', html, re.I))
    dates = _dates(text)
    return {
        "courses": sum(1 for h in _COURSE_HINTS if h in text),
        "notices": sum(1 for h in _NOTICE_HINTS if h in text),
        "latest_date": dates[-1] if dates else None,
        "pages": len({urljoin(base_url, l) for l in links
                      if not l.startswith(("#", "mailto:", "tel:", "javascript:"))}),
        "length": len(text),
    }


# ── 연락처 조회 (2026-09-05) ──────────────────────────────────────
#
# 위의 '**URL 을 추측하지 않는다**' 는 그대로다. 여기서 하는 것은 추측이
# 아니라 **조회**다 — 네이버 지역검색은 상호와 함께 **주소**를 돌려주므로,
# 우리가 아는 도로명주소와 대조해 맞을 때만 쓴다. 이름만 보고 웹 검색
# 결과의 첫 줄을 집는 것과는 다른 일이다.
#
# 이것이 필요한 이유(실측 2026-09-04):
#   홈페이지가 적힌 학원  **0곳** — 사람이 적은 것만 읽는데 아무도 안 적었다
#   전화번호 894곳 중     **187곳이 `02-0000-0000` 류** — 걸리지 않는다
# 레벨테스트를 학원에 **직접** 신청하게 하려면(예약 대행 폐지) 전화든
# 신청 페이지든 닿을 곳이 있어야 한다.
CONTACT_CACHE = config.CACHE_DIR / "local_lookup.json"
CONTACT_PER_RUN = 120
CONTACT_REVISIT_DAYS = 90


def _load_contacts() -> dict:
    if CONTACT_CACHE.exists():
        try:
            return json.loads(CONTACT_CACHE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def lookup_contacts(academies: list[dict], live: bool = True,
                    limit: int = CONTACT_PER_RUN) -> dict:
    """학원에 `homepage` 를 붙이고 가짜 전화번호를 조회값으로 갈아 끼운다.

    ★ 위키 `homepage:` 가 언제나 이긴다 — 사람이 적은 것이 먼저다.
      여기서는 **비어 있는 자리만** 채운다.
    """
    from . import naver, neis
    cache = _load_contacts()
    today = date.today().isoformat()

    def stale(aid: str) -> bool:
        row = cache.get(aid) or {}
        seen = row.get("checked")
        if not seen:
            return True
        try:
            return (date.today() - date.fromisoformat(seen)).days >= CONTACT_REVISIT_DAYS
        except ValueError:
            return True

    # 화면에 이미 보이는 곳(근거가 있는 곳)과 **걸 수 없는 곳**이 먼저다.
    def priority(a: dict) -> tuple:
        no_tel = 0 if neis.clean_tel(a.get("tel")) else -1
        return (no_tel, -(a.get("sample_size") or 0))

    asked = 0
    if live and config.HAS_NAVER:
        todo = [a for a in academies
                if a.get("road_address") and stale(a["id"])]
        todo.sort(key=priority)
        for a in todo[:limit]:
            got = naver.local_lookup(a.get("name") or "", a.get("road_address"))
            cache[a["id"]] = {"checked": today, **(got or {})}
            asked += 1
            time.sleep(0.15)          # 초당 한도를 넘기지 않는다
        if asked:
            CONTACT_CACHE.parent.mkdir(parents=True, exist_ok=True)
            CONTACT_CACHE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    filled_hp = filled_tel = filled_cat = 0
    for a in academies:
        row = cache.get(a["id"]) or {}
        if not a.get("homepage") and row.get("link"):
            a["homepage"] = row["link"]
            filled_hp += 1
        if not neis.clean_tel(a.get("tel")) and row.get("telephone"):
            a["tel"] = row["telephone"]
            filled_tel += 1
        # 업종(category)도 남긴다. '어학교육>영어교육'·'교습학원,교습소>수학교육'
        # 처럼 **과목을 말해 주는** 값이라, 과목 미상 학원의 단서가 된다.
        # 지금은 저장만 한다 — 과목 판정에 넣는 것은 전수 확인 뒤에.
        if row.get("category"):
            a["place_category"] = row["category"]
            filled_cat += 1
    return {"asked": asked, "homepage": filled_hp, "tel": filled_tel,
            "category": filled_cat, "cached": len(cache)}


def collect(homepages: dict[str, str], limit: int = PER_RUN) -> dict:
    """{학원 id: 홈페이지} → {학원 id: 관찰}. 캐시에 누적한다.

    오래 안 본 곳부터 본다. 매 실행 전부 부르지 않는 이유는 예의이기도
    하고, 학원 홈페이지가 매일 바뀌지 않기 때문이기도 하다.
    """
    if not homepages:
        return {}
    import requests

    cache = _load_cache()
    today = date.today()

    def staleness(aid: str) -> float:
        seen = (cache.get(aid) or {}).get("checked_on")
        if not seen:
            return 1e9                    # 한 번도 안 본 곳이 먼저
        try:
            return (today - date.fromisoformat(seen)).days
        except ValueError:
            return 1e9

    due = [aid for aid in homepages if staleness(aid) >= REVISIT_DAYS]
    due.sort(key=staleness, reverse=True)
    due = due[:limit]
    if not due:
        return cache

    session = requests.Session()
    ok = blocked = failed = changed = 0
    robots_cache: dict[str, tuple[bool, str]] = {}

    for aid in due:
        url = homepages[aid]
        host = urlparse(url).netloc
        if host not in robots_cache:
            robots_cache[host] = _allowed(url, session)
            time.sleep(SLEEP)
        allowed, why = robots_cache[host]
        if not allowed:
            blocked += 1
            cache[aid] = {**(cache.get(aid) or {}), "url": url,
                          "checked_on": today.isoformat(),
                          "blocked": why, "observed": None}
            continue
        try:
            r = session.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
            r.raise_for_status()
            r.encoding = r.apparent_encoding or r.encoding
            observed = _observe(r.text, url)
        except Exception as exc:                          # noqa: BLE001
            failed += 1
            cache[aid] = {**(cache.get(aid) or {}), "url": url,
                          "checked_on": today.isoformat(),
                          "error": f"{type(exc).__name__}"}
            time.sleep(SLEEP)
            continue

        prev = (cache.get(aid) or {}).get("observed")
        if prev and prev != observed:
            changed += 1
        cache[aid] = {
            "url": url,
            "checked_on": today.isoformat(),
            "observed": observed,
            "previous": prev,
            "blocked": None,
            "error": None,
        }
        ok += 1
        time.sleep(SLEEP)

    _save_cache(cache)
    print(f"  공식 홈페이지: {ok}곳 확인"
          + (f" · 변화 {changed}곳" if changed else "")
          + (f" · robots 거부 {blocked}곳" if blocked else "")
          + (f" · 실패 {failed}곳" if failed else "")
          + f" (대상 {len(homepages)}곳 중 {len(due)}곳 차례)")
    return cache


def block(aid: str, cache: dict) -> str:
    """학원 페이지의 auto:official 블록 내용."""
    row = cache.get(aid)
    if not row:
        return "- (homepage 미등록 — frontmatter 에 적으면 이 자리가 채워진다)"
    lines = [f"- 출처 {row['url']} ({row.get('checked_on')} 확인)"]
    if row.get("blocked"):
        lines.append(f"- 읽지 않음 — {row['blocked']}")
        return "\n".join(lines)
    if row.get("error"):
        lines.append(f"- 확인 실패 — {row['error']}")
        return "\n".join(lines)
    o = row.get("observed") or {}
    prev = row.get("previous") or {}

    def delta(key: str) -> str:
        if not prev or prev.get(key) is None or o.get(key) is None:
            return ""
        d = o[key] - prev[key]
        return f" (지난 확인 대비 {d:+d})" if d else ""

    lines.append(f"- 과정 관련 항목 {o.get('courses', 0)}개{delta('courses')}"
                 f" · 공지 항목 {o.get('notices', 0)}개{delta('notices')}")
    if o.get("latest_date"):
        lines.append(f"- 페이지에 보이는 최신 날짜 {o['latest_date']}")
    lines.append(f"- 링크 {o.get('pages', 0)}개 · 본문 {o.get('length', 0):,}자"
                 " (본문은 저장하지 않는다 — 남의 저작물이다)")
    return "\n".join(lines)
