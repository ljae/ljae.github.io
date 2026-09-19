"""학원 자기 서술 — 디렉터리 페이지에서 학원이 **스스로 밝힌 것**만 읽는다.

후기는 남의 말이고 NEIS 공시는 3년 전일 수 있다. 학원이 디렉터리에 적은
소개·대상 학년·셔틀·설명회 소식은 학원 본인의 말이라 반박당할 여지가 없고,
프로필의 `kind: self` 근거가 된다(profiles.py 가 이 모듈을 부른다).

## 출처

- **강남엄마 학원 소개** `https://www.gangmom.kr/institute/<id>`.
  robots.txt(2026-09-17 확인): `User-agent: *` Allow / 에 `/user/`·`/internal/`·
  `/review/` Disallow. 소개 페이지는 허용이고 **후기(`/review/`)는 거부**라
  읽지 않는다. 소개 페이지 안에도 후기 발췌 몇 건이 SSR 로 들어 있는데, 그
  부분은 파싱하지 않는다 — 소식 제목은 NUXT 상태의 `news` 블록에서만 뽑고
  `reviews` 가 시작되는 자리에서 자른다(`_events`).
- **오늘학교 아카데미** `academy.prompie.com` 은 robots 에 `Content-Signal:
  ai-train=no` 가 있어 **우리 규칙상 읽지 않는다**(CLAUDE.md '타 사이트 후기
  수집 — robots.txt 를 먼저 본다', `official._allowed` 가 그 신호를 거부로
  친다). 규칙을 바꾸기로 하면 **여기부터**: `SOURCES` 에 호스트·페이지 패턴을
  더하고 `official._allowed` 판정을 그대로 지나게 한다. 판정 코드를 우회하는
  방식으로는 넣지 않는다 — 도구를 바꿔 우회하지 않는다는 규칙과 같다.

## 발견 — 두 길, 그리고 sitemap 이 왜 사실상 안 쓰이는가

(a) 언급의 `source_url` 이 소개 페이지면(웹문서 API 가 켜지면 들어온다) 그
    글이 붙은 학원의 **후보**로 삼는다. 후보일 뿐이다 — '대치 정상어학원'
    질의가 목동 정상어학원의 소개 페이지를 돌려줄 수 있다.
(b) `sitemap.xml` 을 읽어 `/institute/<id>` 목록을 얻는다. **실측(2026-09-17):
    색인 아래 학원 sitemap 11개 × 10,000건 ≈ 11만 건이고 이름도 지역도 없다.**
    어느 것이 우리 학군인지는 페이지를 열어 봐야만 안다. 하루 40곳씩 11만
    곳을 여는 것은 발견이 아니라 전수 크롤이라, `SITEMAP_MAX` 를 넘으면
    sitemap 을 걷지 않고 (a) 로만 잇는다. 작은 sitemap(시험 픽스처)에서만 돈다.
    '학군 4곳만' 으로 좁힐 길이 sitemap 에는 없다 — 지역이 적혀 있지 않다.

어느 길로 왔든 **페이지 제목 '학원명 (구 동)' 을 등록부와 대조해 맞을 때만
잇는다**(`match_academy`) — 이름 알맹이(`analyze.name_core`)가 같고 동이
같아야 하며, 양쪽에 도로명주소가 있으면 건물번호까지 같아야 한다. 같은
건물의 다른 업소를 이름으로 잇던 '메이플' 미용실 사고(official.py)의 반대편
이다: 이름이 같아도 **주소가 다르면 다른 학원**이다. 둘 이상이 남으면 잇지
않는다 — 어느 쪽인지 모르는 것을 한쪽에 몰아주면 추측이다.

## 읽는 방식

- robots.txt 를 **먼저** 본다(`official._allowed`). 거부·확인 실패면 페이지를
  한 장도 열지 않는다.
- 봇 UA(`openedu-bot`)에는 403 이 온다(실측, robots.txt 는 200). 페이지는
  `blog.UA`(브라우저 UA)로 읽되 robots 는 `*` 규칙으로 판정한다 — UA 를 바꿔
  robots 를 우회하는 것이 아니라, robots 가 허용한 것을 읽는 것이다.
- 한 실행 `OPENEDU_DIRECTORY_PER_RUN`(기본 40)곳, 1초 간격, 14일 캐시. 실패는
  `error` 로 남기고 7일 뒤 다시 본다 — 실패를 성공만큼 오래 붙들지 않는다.
- **본문을 저장하지 않는다.** 소개 단락 ≤1500자, 대상·과목·셔틀, 소식 제목
  ≤5 만 남긴다(`.cache/directory.json`). 후기 문장은 어느 필드에도 없다.
- 네트워크가 끊겨도 실행은 계속된다. 키가 없는 것과 실패한 것은 같은
  결과다 — 캐시에 있는 것만 돌려준다.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import date
from html import unescape
from urllib.parse import urlparse

from . import config
from .blog import UA as BROWSER_UA

CACHE = config.CACHE_DIR / "directory.json"
SITEMAP_CACHE = config.CACHE_DIR / "directory_sitemap.json"
PUBLISHED = config.EXPORT_DIR / "directory_sources.json"
# ★ 빈 환경변수와 미설정은 다르다 — Actions 는 미정의 vars 를 "" 로 넘긴다.
PER_RUN = int(os.getenv("OPENEDU_DIRECTORY_PER_RUN") or "40")
REVISIT_DAYS = 14
RETRY_DAYS = 7
SLEEP = 1.0
TIMEOUT = 15
TEXT_LIMIT = 1500
EVENTS_MAX = 5
# sitemap 의 학원 페이지가 이보다 많으면 걷지 않는다(위 '발견' 참고).
SITEMAP_MAX = 5000
SITEMAP_DAYS = 14

SOURCES = {
    "gangmom": {
        "label": "강남엄마",
        "host": "www.gangmom.kr",
        "page": re.compile(
            r"https?://(?:www\.)?gangmom\.kr/institute/([0-9a-f]{24})(?:[/?#]|$)"),
        "sitemap": "https://www.gangmom.kr/sitemap.xml",
    },
    # 오늘학교 아카데미(academy.prompie.com)는 넣지 않는다 — 모듈 docstring.
}

_TITLE = re.compile(r"<title>\s*(.+?)\s*\((\S+)\s+(\S+)\)\s*\|", re.S)
_META_DESC = re.compile(
    r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)
_NUXT = re.compile(r"window\.__NUXT__=(.*?)</script>", re.S)
_JS_STR = r'"((?:[^"\\]|\\.)*)"'
_NUXT_DESC = re.compile(r"\bdescription:" + _JS_STR)
_NUXT_SHUTTLE = re.compile(r"\bshuttleBus:" + _JS_STR)
_NUXT_TITLE = re.compile(r"\btitle:" + _JS_STR)
_SPAN_NEWS_TITLE = re.compile(
    r'<span class="[^"]*\bbody1-bold2 title\b[^"]*"[^>]*>([^<]+)</span>')
_GRADE_RANGE = re.compile(r"^학년\s+(\S+?)부터\s+(\S+?)까지$")
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_ADDR_HEAD = ("서울", "경기", "인천")


# ── 파싱 ──────────────────────────────────────────────────────────
def _js(s: str) -> str:
    """NUXT 상태의 JS 문자열 리터럴을 푼다(`\\u002F`·`\\"`). 못 풀면 그대로."""
    try:
        return json.loads(f'"{s}"')
    except ValueError:
        return s


def _events(html: str) -> list[str] | None:
    """소식(설명회·입학시험·모집) 제목. **`reviews` 앞에서 자른다** — 후기는
    읽지 않는다. NUXT 상태가 없으면 소식 제목 span 만 본다(리뷰 제목 span 은
    class 가 다르다)."""
    m = _NUXT.search(html)
    titles: list[str] = []
    if m:
        state = m.group(1)
        i = state.find("news:{news:[")
        if i >= 0:
            j = state.find("reviews:", i)
            block = state[i:j] if j > i else state[i:]
            titles = [_js(t) for t in _NUXT_TITLE.findall(block)]
    if not titles:
        titles = [unescape(t).strip() for t in _SPAN_NEWS_TITLE.findall(html)]
    titles = [t for t in titles if t]
    return titles[:EVENTS_MAX] or None


def parse_page(html: str) -> dict:
    """소개 페이지 하나에서 **학원이 밝힌 것**만 뽑는다. 없는 항목은 None.

    - name·gu·dong: `<title>학원명 (구 동) | …</title>`
    - text: 소개 단락(NUXT `description`, 없으면 meta description 의 첫 절)
    - target·subjects·shuttle·address: meta description 의 절들
      ('학년 초1부터 중3까지'·'과목 영어'·'셔틀 제공'·'서울 강남구 도곡로 418 …')
    - events: 소식 제목 ≤5 (`_events`)
    """
    out: dict = {"name": None, "gu": None, "dong": None, "address": None,
                 "text": None, "target": None, "subjects": None,
                 "shuttle": None, "events": None}
    m = _TITLE.search(html)
    if m:
        out["name"] = unescape(m.group(1)).strip()
        out["gu"], out["dong"] = m.group(2), m.group(3)
    else:
        # 현재 페이지는 제목에서 (구 동)을 생략한다. 주소로만 대조한다.
        title = re.search(r"<title>([^<]+?)\s*\|", html)
        if title:
            out["name"] = unescape(title.group(1)).strip()

    meta = _META_DESC.search(html)
    desc = unescape(meta.group(1)) if meta else ""
    segs = [s.strip() for s in desc.split(", ") if s.strip()]
    for seg in segs:
        g = _GRADE_RANGE.match(seg)
        if g:
            out["target"] = [f"{g.group(1)}~{g.group(2)}"]
        elif seg.startswith("학년 ") and out["target"] is None:
            out["target"] = [s.strip() for s in seg[3:].split("·") if s.strip()] or None
        elif seg.startswith("과목 "):
            out["subjects"] = [s.strip() for s in seg[3:].split("·") if s.strip()] or None
        elif seg.startswith("셔틀 "):
            out["shuttle"] = "미제공" not in seg
        elif seg.startswith(_ADDR_HEAD) and out["address"] is None:
            out["address"] = seg

    nuxt = _NUXT.search(html)
    state = nuxt.group(1) if nuxt else ""
    d = _NUXT_DESC.search(state)
    text = _js(d.group(1)).strip() if d else ""
    if not text and desc:
        # meta 는 '소개., 평점 4.3, …' 꼴이라 첫 절이 소개다.
        text = desc.split(", 평점")[0].strip()
    out["text"] = text[:TEXT_LIMIT] or None
    if out["shuttle"] is None:
        s = _NUXT_SHUTTLE.search(state)
        if s:
            val = _js(s.group(1))
            out["shuttle"] = ("제공" in val and "미제공" not in val) if val else None
    out["events"] = _events(html)
    return out


def parse_sitemap(xml: str) -> tuple[str, list[str]]:
    """('index'|'urlset', loc 목록)."""
    kind = "index" if "<sitemapindex" in xml else "urlset"
    return kind, [unescape(u) for u in _LOC.findall(xml)]


def page_url(url: str | None) -> tuple[str, str] | None:
    """소개 페이지 링크면 (source, 정규 URL). 아니면 None."""
    if not url:
        return None
    for key, spec in SOURCES.items():
        m = spec["page"].match(url.strip())
        if m:
            return key, f"https://{spec['host']}/institute/{m.group(1)}"
    return None


# ── 대조 ──────────────────────────────────────────────────────────
class Registry:
    """등록부 색인. (이름 알맹이, 동) 과 (도로명 건물번호) 두 열쇠."""

    def __init__(self, academies: list[dict]) -> None:
        from . import analyze, naver
        self.by_id = {a["id"]: a for a in academies if a.get("id")}
        self.core = {aid: analyze.name_core(a.get("name") or "")
                     for aid, a in self.by_id.items()}
        # build 내부 dict 는 road_address, 앱 export 는 address 다. 둘 다 받는다.
        self.addr = {aid: naver.addr_key(a.get("road_address") or a.get("address"))
                     for aid, a in self.by_id.items()}
        self.by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.by_addr: dict[str, list[str]] = defaultdict(list)
        for aid, a in self.by_id.items():
            if self.core[aid] and a.get("dong"):
                self.by_key[(self.core[aid], a["dong"])].append(aid)
            if self.addr[aid]:
                self.by_addr[self.addr[aid]].append(aid)


def match_academy(page: dict, reg: Registry,
                  prefer: str | None = None) -> str | None:
    """페이지가 등록부의 어느 학원인가. 확신이 없으면 None.

    1. 알맹이가 같고 동이 같다. 양쪽에 주소가 있으면 건물번호도 같아야 한다.
    2. 1 이 없으면, 주소가 같고 동이 같고 알맹이가 서로를 품는다
       ('그로튼' ⊂ '그로튼프리미어'). 주소 없이는 품는 것으로 잇지 않는다.
    둘 이상 남으면 [prefer](후보를 낸 학원)가 그중 하나일 때만 그것, 아니면 None.
    """
    from . import analyze, naver
    core = analyze.name_core(page.get("name") or "")
    dong = page.get("dong")
    if not core:
        return None
    want = naver.addr_key(page.get("address"))
    found = [aid for aid in reg.by_key.get((core, dong), ())
             if not (want and reg.addr.get(aid) and reg.addr[aid] != want)]
    if not found and want:
        for aid in reg.by_addr.get(want, ()):
            a = reg.by_id[aid]
            c = reg.core.get(aid) or ""
            if (not dong or a.get("dong") == dong) and len(c) >= 3 and (c in core or core in c):
                found.append(aid)
    if len(found) == 1:
        return found[0]
    # 검색된 학원을 prefer로 넘겼다는 사실은 동일 학원이라는 증거가 아니다.
    return None


# ── 캐시 ──────────────────────────────────────────────────────────
def _load(path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def _age(stamp: str | None, today: date) -> int | None:
    if not stamp:
        return None
    try:
        return (today - date.fromisoformat(stamp[:10])).days
    except ValueError:
        return None


def _due(row: dict | None, today: date) -> bool:
    if not row:
        return True
    age = _age(row.get("fetched_at"), today)
    if age is None:
        return True
    return age >= (RETRY_DAYS if row.get("error") else REVISIT_DAYS)


def _ok_rows(cache: dict, ids) -> dict[str, dict]:
    return {aid: row for aid, row in cache.items()
            if aid in ids and row and not row.get("error")}


# ── 수집 ──────────────────────────────────────────────────────────
# ★ 후기 경로는 코드로 막는다. 강남엄마 robots.txt 는 `User-agent: *` 묶음의
#   `Allow: /` 뒤에 빈 줄이 오고 그 아래 `Disallow: /review/` 가 적혀 있는데,
#   파이썬 `RobotFileParser` 는 빈 줄에서 묶음을 닫아 그 Disallow 를 **버린다**
#   (실측: can_fetch('*', '/review/x') == True). 사이트의 뜻은 분명하므로
#   파서가 뭐라 하든 이 경로는 열지 않는다. 열 수 있는 것은 소개 페이지와
#   sitemap 뿐이다.
_NEVER = re.compile(r"^/(review|user|internal)(/|$)")


def _fetch(session, url: str) -> tuple[str | None, str | None]:
    """(html, error). 브라우저 UA — 봇 UA 는 403 이 온다(실측)."""
    if _NEVER.match(urlparse(url).path or ""):
        return None, "robots 거부 경로"
    try:
        r = session.get(url, headers={"User-Agent": BROWSER_UA}, timeout=TIMEOUT)
    except Exception as exc:                              # noqa: BLE001
        return None, type(exc).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        r.encoding = r.apparent_encoding or r.encoding
    except Exception:                                     # noqa: BLE001
        pass
    return r.text or "", None


def _sitemap_pool(session, src: str, today: date) -> dict:
    """sitemap 의 소개 페이지 목록. 크면 걷지 않는다(`too_big`). 14일 캐시."""
    spec = SOURCES[src]
    store = _load(SITEMAP_CACHE)
    row = store.get(src) or {}
    age = _age(row.get("fetched_at"), today)
    if age is not None and age < SITEMAP_DAYS and "count" in row:
        return row
    row = {"fetched_at": today.isoformat(), "count": 0, "too_big": False,
           "urls": [], "visited": row.get("visited") or {}, "error": None}
    html, err = _fetch(session, spec["sitemap"])
    if err or html is None:
        row["error"] = err or "empty"
    else:
        kind, locs = parse_sitemap(html)
        subs = locs if kind == "index" else []
        pages = [u for u in locs if spec["page"].match(u)] if kind != "index" else []
        # 색인이면 학원 sitemap 만 차례로 연다. 상한을 넘는 순간 멈춘다 —
        # 11만 건짜리를 다 받아 봐야 걷지 않을 목록이다.
        for sub in subs:
            if not re.search(r"academ|institute", sub, re.I):
                continue
            time.sleep(SLEEP)
            xml, e2 = _fetch(session, sub)
            if e2 or not xml:
                continue
            pages.extend(u for u in parse_sitemap(xml)[1] if spec["page"].match(u))
            if len(pages) > SITEMAP_MAX:
                break
        row["count"] = len(pages)
        row["too_big"] = len(pages) > SITEMAP_MAX
        row["urls"] = [] if row["too_big"] else pages
    store[src] = row
    _save(SITEMAP_CACHE, store)
    return row


def collect(academies: list[dict], mentions: list[dict],
            live: bool = True) -> dict[str, dict]:
    """학원 id → 자기 서술 항목(`error` 인 것은 뺀다). `live=False` 면 캐시만.

    항목: {source, url, fetched_at, name, dong, text, target, subjects,
           shuttle, events}
    """
    cache = _load(CACHE)
    reg = Registry(academies)
    if not live or not reg.by_id:
        return _ok_rows(cache, reg.by_id)

    # (a) 언급 링크 → 후보 (학원 id → 정규 URL)
    cands: dict[str, tuple[str, str]] = {}
    # 공개 출처도 재확인 후보로 이어 준다. 실제 연결은 이름·주소를 다시 대조한다.
    try:
        published = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        published = []
    for group in published:
        aid = group.get("academyId")
        for note in group.get("notes") or []:
            got = page_url(note.get("url"))
            if got and aid in reg.by_id:
                cands[aid] = got
    for aid, row in cache.items():
        got = page_url(row.get("url")) if row else None
        if got and aid in reg.by_id:
            cands[aid] = got
    for m in mentions or ():
        # 후기 점수에서 제외된 웹문서도 소개 URL의 발견 경로가 될 수 있다.
        # 실제 연결은 아래 등록명·주소 대조를 반드시 거친다.
        got = page_url(m.get("source_url"))
        aid = m.get("academy_key")
        if got and aid in reg.by_id and aid not in cands:
            cands[aid] = got
    today = date.today()
    due = [(aid, src, url) for aid, (src, url) in cands.items()
           if _due(cache.get(aid), today)]
    # 한 번도 안 본 곳이 먼저, 그다음 오래된 순.
    due.sort(key=lambda t: (cache.get(t[0]) is not None,
                            (cache.get(t[0]) or {}).get("fetched_at") or ""))

    try:
        import requests
        session = requests.Session()
    except Exception as exc:                              # noqa: BLE001
        print(f"  학원 자기서술: 세션을 못 열어 건너뜀 ({type(exc).__name__})")
        return _ok_rows(cache, reg.by_id)

    from . import official
    robots: dict[str, tuple[bool, str]] = {}

    def allowed(src: str, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in robots:
            robots[host] = official._allowed(url, session)
            if not robots[host][0]:
                print(f"  학원 자기서술({SOURCES[src]['label']}): 읽지 않음 — "
                      f"{robots[host][1]}")
        return robots[host][0]

    budget = PER_RUN
    ok = mismatch = failed = 0

    def visit(src: str, url: str, prefer: str | None) -> str | None:
        """한 장 읽어 대조하고 캐시에 적는다. 이어진 학원 id 를 돌려준다."""
        nonlocal ok, mismatch, failed
        html, err = _fetch(session, url)
        stamp = today.isoformat()
        if err or html is None:
            failed += 1
            if prefer:
                cache[prefer] = {"source": src, "url": url, "fetched_at": stamp,
                                 "error": err or "empty"}
            return None
        page = parse_page(html)
        aid = match_academy(page, reg, prefer)
        if aid and prefer and aid != prefer:
            # 후보를 낸 학원의 페이지가 아니라 형제·동명 학원의 페이지다. 그쪽에
            # 잇고, 낸 쪽에는 불일치로 적어 둔다 — 안 적으면 매 실행 같은
            # 링크를 다시 연다.
            cache[prefer] = {"source": src, "url": url, "fetched_at": stamp,
                             "error": f"등록부와 불일치: 다른 학원({aid})의 페이지"}
        if not aid:
            mismatch += 1
            if prefer:
                cache[prefer] = {"source": src, "url": url, "fetched_at": stamp,
                                 "error": f"등록부와 불일치: {page.get('name')} "
                                          f"({page.get('gu')} {page.get('dong')})"}
            return None
        ok += 1
        cache[aid] = {
            "source": src, "url": url, "fetched_at": stamp,
            "name": page["name"], "dong": page["dong"],
            "text": page["text"], "target": page["target"],
            "subjects": page["subjects"], "shuttle": page["shuttle"],
            "events": page["events"],
        }
        return aid

    for aid, src, url in due:
        if budget <= 0:
            break
        if not allowed(src, url):
            continue
        visit(src, url, aid)
        budget -= 1
        time.sleep(SLEEP)

    # 공개 탐색 목록과 거기에 실제로 연결된 다음 페이지를 순환한다.
    # URL을 추측하지 않고 큐를 캐시에 보존한다. 목록 순서/별점은 점수와 무관하다.
    listing = "https://www.gangmom.kr/browse"
    if budget > 0 and allowed("gangmom", listing):
        store = _load(SITEMAP_CACHE)
        progress = store.setdefault("browse", {"queue": [listing], "pages": {}, "details": {}})
        queue = progress["queue"]
        if not queue:
            queue.append(listing)
        linked = {r.get("url") for r in cache.values() if r and not _due(r, today)}
        for _ in range(3):
            if not queue or budget <= 0:
                break
            listing_url = queue.pop(0)
            html, err = _fetch(session, listing_url)
            if err or not html:
                print(f"  학원 자기서술: 공개 목록 확인 실패 ({err or 'empty'}) · {listing_url}")
                queue.append(listing_url)
                break
            progress["pages"][listing_url] = today.isoformat()
            for path in dict.fromkeys(re.findall(r'href=["\'](/browse\?page=\d+)["\']', html)):
                url = "https://www.gangmom.kr" + path
                age = _age(progress["pages"].get(url), today)
                if url not in queue and (age is None or age >= REVISIT_DAYS):
                    queue.append(url)
            paths = dict.fromkeys(re.findall(r'href=["\'](/institute/[a-f0-9]{24})["\']', html))
            if not paths:
                print(f"  학원 자기서술: 공개 목록에서 소개 링크 0건 · {listing_url}")
            for path in paths:
                url = "https://www.gangmom.kr" + path
                if budget <= 0:
                    # 예산 때문에 못 읽은 링크를 다음 회차에 잃지 않는다.
                    queue.insert(0, listing_url)
                    break
                age = _age(progress["details"].get(url), today)
                if url in linked or (age is not None and age < REVISIT_DAYS):
                    continue
                visit("gangmom", url, None)
                progress["details"][url] = today.isoformat()
                budget -= 1
                time.sleep(SLEEP)
        _save(SITEMAP_CACHE, store)

    # (b) sitemap — 작을 때만 걷는다. 남은 예산으로.
    pool_note = ""
    for src, spec in SOURCES.items():
        if budget <= 0 or not allowed(src, spec["sitemap"]):
            continue
        pool = _sitemap_pool(session, src, today)
        if pool.get("error"):
            pool_note = f" · sitemap 확인 실패({pool['error']})"
            continue
        if pool.get("too_big"):
            pool_note = (f" · sitemap {pool['count']:,}건+ 이름 없음 → 걷지 않음"
                         " (언급 링크로만 잇는다)")
            continue
        visited = pool.setdefault("visited", {})
        linked = {row.get("url") for row in cache.values() if row and row.get("url")}
        for url in pool.get("urls") or ():
            if budget <= 0:
                break
            if url in visited or url in linked:
                continue
            visited[url] = today.isoformat()
            visit(src, url, None)
            budget -= 1
            time.sleep(SLEEP)
        store = _load(SITEMAP_CACHE)
        store[src] = pool
        _save(SITEMAP_CACHE, store)

    if ok or mismatch or failed:
        _save(CACHE, cache)
    if due or ok or mismatch or failed or pool_note:
        print(f"  학원 자기서술: {ok}곳 확인"
              + (f" · 등록부 불일치 {mismatch}곳" if mismatch else "")
              + (f" · 실패 {failed}곳" if failed else "")
              + f" (후보 {len(cands)}곳 중 {len(due)}곳 차례)" + pool_note)
    return _ok_rows(cache, reg.by_id)


def status() -> str:
    """run.py --check 용 한 줄. 네트워크를 쓰지 않는다."""
    cache = _load(CACHE)
    good = [r for r in cache.values() if r and not r.get("error")]
    bad = len(cache) - len(good)
    note = " · 오늘학교는 ai-train=no 로 보류"
    if not cache:
        return ("✗ 캐시 없음 — 언급에 강남엄마 링크가 들어오면(웹문서 API) "
                "다음 실행에서 읽는다" + note)
    last = max((r.get("fetched_at") or "" for r in cache.values()), default="")
    return (f"✓ 강남엄마 소개 {len(good)}곳"
            + (f" · 실패·불일치 {bad}곳" if bad else "")
            + f" · 마지막 확인 {last[:10]}" + note)


def source_notes(academies: list[dict]) -> list[dict]:
    """원문 복제 없이 구조화한 대상·과목·셔틀만 출처 카드로 공개한다."""
    cache = _load(CACHE)
    out = []
    for a in academies:
        row = cache.get(a["id"]) or {}
        if not row or row.get("error"):
            continue
        parts = []
        if row.get("target"):
            parts.append("대상: " + " · ".join(row["target"]))
        if row.get("subjects"):
            parts.append("과목: " + " · ".join(row["subjects"]))
        if row.get("shuttle") is not None:
            parts.append("셔틀 " + ("제공 안내" if row["shuttle"] else "미제공 안내"))
        if not parts:
            continue
        out.append({
            "academyId": a["id"], "name": a.get("name") or row["name"],
            "scope": "학원 소개 페이지 · 등록명과 주소 대조",
            "caveat": "학원 측 안내로, 독립적인 수강 후기가 아닙니다. 순위 점수에는 반영하지 않습니다. 현재 운영 여부는 학원에 확인해 주세요.",
            "notes": [{"topic": "운영·일정", "title": "강남엄마 학원 소개",
                       "summary": "; ".join(parts), "url": row["url"],
                       "checkedAt": row["fetched_at"], "kind": "directory",
                       "sourceScope": "branch", "subjects": []}],
        })
    return out
