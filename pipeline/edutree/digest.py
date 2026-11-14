"""대치 학부모방 아침 소식과 한 달 일정 — 학년 구간(방)마다 따로.

방은 화면의 학년 구간과 같은 넷이다(config.GRADE_BANDS):
예비초~초3 · 초4~초6 · 중등 · 고등. 저학년과 고학년은 사실상 다른 시장이라
(CLAUDE.md '학교급과 학년 구간') 한 방에 섞으면 둘 다 읽지 않는다.

야간 산출물 두 곳으로 나간다.
- `nightly_brief.json` 의 `daechi` — 방마다 지난밤 바뀐 것. 로컬 알림 작업이
  07:30 슬랙에 '카톡방 붙여넣기용' 블록 넷으로 붙인다. 사람이 읽고 붙여
  넣는다 — 오픈채팅 자동 게시는 카카오 운영정책(봇·매크로 금지)상 쓰지 않는다.
- `calendar.json` — **네 학군**(대치·목동·잠실·반포)의 앞으로 두 달 설명회·
  테스트·개강 일정. 항목마다 `regions` 와 달력 칸에 쓸 짧은 말(`label`).
  회차마다 새로 찾은 것을 **쌓고**, 날짜가 지난 것만 뺀다(검색 API 는 최근
  글만 돌려주므로 2주 전에 공지된 12월 설명회가 오늘 검색에는 안 나올 수 있다).

싣는 것은 전부 우리가 정당하게 가진 것이다.
1. 랭킹 변동 — **화면과 같은 규칙으로** (과목 × 학년 구간) 순위를 세워
   지난 회차와 견준다(`band_ranks` 가 app/lib/data/repository.dart 의
   `ranking()` 을 그대로 옮겼다). 화면에서 '초4~초6 수학 1위' 인 곳이 소식에도
   1위여야 한다. 표본 부족(isRanked=false)인 자리의 변동은 싣지 않는다.
2. 일정 — 네이버 **공식 검색 API**(블로그·뉴스)의 제목·링크와, 제목·요약에
   적힌 날짜만. 본문은 저장하지 않는다. 카페 본문·오픈채팅·디스쿨은 읽지
   않는다. 학원 홍보 글이 대부분이라 '학원 측 안내' 라 적고 **점수에는 절대
   쓰지 않는다.**
3. 교육청 등록부 변화 — 새로 등록된 학원(개설일이 최근인 것만)과 빠진 학원.
   빠진 것은 폐원·이전·통합일 수 있어 '폐원' 이라 단정하지 않는다.

★ 유아 레벨테스트 금지(학원법 시행령, 2026-10-01 시행). 만 3세~취학 전
  (예비초 포함) 대상의 필기·구술·실기·**면접** 시험이 금지다. 예비초 대상
  테스트로 보이는 글은 일정에도 소식에도 싣지 않는다 — 실으면 금지된 시험을
  안내하는 셈이다. 몇 건을 뺐는지는 운영자에게만 알린다(`bannedCount`).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from . import config
from .analyze import OTHER_REGION_WORDS

REGION = "daechi"
BANDS = tuple(config.GRADE_BANDS)             # elem_low · elem_high · middle · high
NEW_WITHIN_DAYS = 60          # 개설일이 이보다 오래면 '새 학원' 이 아니라 새로 잡힌 것
GONE_BULK = 15                # 하루에 이만큼 넘게 빠지면 필터 변화로 본다
NEWS_DAYS = 3                 # 이보다 오래된 글은 '지난밤 소식' 이 아니다
WINDOW_DAYS = 62              # 일정 달력의 앞쪽 끝 — 이번 달과 다음 달을 덮는다
WEEK_DAYS = 7                 # 아침 소식의 '이번 주 일정'
RISE_MIN = 3                  # 이만큼은 올라야 '상승' 으로 적는다
RISE_TOP = 10                 # 10위 밖의 움직임은 싣지 않는다
# 학군마다 같은 질의를 한다. 대치가 아닌 학군도 달력에 오른다.
REGIONS = ("daechi", "mokdong", "jamsil", "banpo")
_QUERY_TAILS = ("설명회", "학원 설명회", "설명회 일정", "레벨테스트 일정",
                "입학테스트", "개강")
_REGION_QUERY = {"daechi": "대치", "mokdong": "목동", "jamsil": "잠실", "banpo": "반포"}


def event_queries() -> list[str]:
    return [f"{_REGION_QUERY[r]} {t}" for r in REGIONS for t in _QUERY_TAILS]
EVENT_SOURCES = ("naver_blog", "naver_news")
LIVE_SEARCH = False           # build.run 이 캐시 실행이 아닐 때만 켠다

_TEST = re.compile(r"(레벨\s*테스트|레테|입학\s*(시험|테스트)|진단\s*평가)"
                   r".{0,8}(일정|접수|신청|안내|모집|실시|응시)"
                   r"|입학\s*(시험|테스트)|진단\s*평가")
_SESSION = re.compile(r"설명회")
_OPEN = re.compile(r"개강|신규\s*모집|신입생\s*모집")
# 제목이 우리 학군을 가리켜야 한다. 다른 지역 '설명회' 가 섞여 온다.
# regions.yaml 의 dong_list 에 학부모가 실제로 쓰는 말을 더했다.
_PLACES = {
    "daechi": re.compile(r"대치|도곡|은마|한티|개포"),
    "mokdong": re.compile(r"목동|신정동|양천|오목교"),
    "jamsil": re.compile(r"잠실|신천동|방이동|송파|석촌"),
    "banpo": re.compile(r"반포|잠원|서초|방배|고속터미널"),
}
KIND_WORDS = {"session": "설명회", "test": "테스트", "open": "개강"}
_BRACKET = re.compile(r"\[([^\]]{2,20})\]")
# 구청 설명회('서초구, 대입 정시 설명회') — 학원이 아니어도 학부모 일정이다.
_DISTRICT = re.compile(r"(강남구|서초구|송파구|양천구)")
# '[설명회] 뉴파인 반포본원…' — 꼬리표 바로 뒤 낱말.
_AFTER_TAG = re.compile(r"\]\s*([가-힣A-Za-z][가-힣A-Za-z0-9]{1,9})")
_ACADEMY_TOKEN = re.compile(r"([가-힣A-Za-z0-9]{2,16}(?:어학원|학원|아카데미|논술|수학|영어|에듀))")


def short_name(text: str) -> str | None:
    """달력 칸에 들어갈 학원 이름 — 대괄호 안이나 '…학원' 낱말의 알맹이."""
    from .analyze import name_core
    for m in [*_BRACKET.finditer(text), *_ACADEMY_TOKEN.finditer(text),
              *_AFTER_TAG.finditer(text)]:
        core = name_core(m.group(1))
        if 2 <= len(core) <= 8 and not _NOT_NAMES.search(core):
            return core
    m = _DISTRICT.search(text)
    return m.group(1) if m else None


def label_for(kind: str, name: str | None) -> str:
    return f"{name} {KIND_WORDS[kind]}" if name else KIND_WORDS[kind]
# 유아(만 3세~취학 전). '예비초'·'예비초1' 은 취학 전 1년이지만 '예비초2~6' 은
# 지금 초등학생이다 — 금지 대상이 아니다(실측: 에디센 '예비초2 입학시험').
_PRESCHOOL = re.compile(r"예비\s*초(?!\s*[2-6])|[5-7]\s*세|유치|유아|영유")
_BAND_WORDS = {
    "elem_low": re.compile(r"예비\s*초|초\s*[1-3](?!\d)|초등\s*저학년|저학년|[5-7]\s*세"),
    "elem_high": re.compile(r"초\s*[4-6](?!\d)|초등\s*고학년|고학년|예비\s*중|영재원"),
    "middle": re.compile(r"중등|중학|중\s*[1-3](?!\d)|예비\s*고|특목|자사고|과학고|외고|영재고|국제고"),
    "high": re.compile(r"고등|고\s*[1-3](?!\d)|수능|정시|수시|대입|의대|N수|재수|입시"),
}
# 날짜. 연도가 있으면 '.', '-', '/', 년월일 무엇이든. 연도가 없으면 '11월 28일'
# 꼴이나 '11/28'·'11.28' 꼴만 — '1-1 시작반'(교재 단원)·'1.5년차'(영유 연차)를
# 1월 1일·1월 5일로 읽던 것을 막는다(실측 2026-11-14).
_DATE = re.compile(
    r"(20\d\d)\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})"
    r"|(?<![\d.])(\d{1,2})\s*월\s*(\d{1,2})\s*일"
    r"|(?<![\d.\-])(\d{1,2})\s*[./]\s*(\d{1,2})(?![\d.]|\s*(?:년|학년|배|%|시간|회|명|점|세|개월))")
# 검색 결과가 학원 이야기여야 한다. '목동 재건축 현장설명회' 같은 것이 온다.
_ACADEMY_CONTEXT = re.compile(r"학원|어학원|교습|학부모|입시|레벨|수학|영어|국어|과학|논술|"
                              r"초등|중등|고등|유치원|영재|특목|정시|수시|대입|학년|수능")
_NOT_ACADEMY = re.compile(r"재건축|재개발|분양|수주|시공|아파트|부동산|입주|청약")
# 지점 규칙의 남의 동네 목록에 없는데 실측에 나온 곳. 전역 목록(analyze)에
# 넣기 전에 같은 이름의 학원 브랜드가 있는지 봐야 하므로 여기 둔다.
_OTHER_PLACES = ("남양읍", "남양주")
# 대괄호 안이 학원 이름이 아닌 경우('[설명회]'·'[이슈]').
_NOT_NAMES = re.compile(r"설명회|이슈|공지|안내|속보|단독|모집|개강|특강|무료|후기|정보|관$")


# ── 랭킹 ─────────────────────────────────────────────────────────
def _bands_for(row: dict, subject: str) -> list[str]:
    """app `bandsForSubject`: 과목별 맵이 있으면 키 없는 과목은 '미확인'."""
    by = row.get("gradeBandsBySubject") or {}
    return (row.get("gradeBands") or []) if not by else (by.get(subject) or [])


def _score(row: dict, subject: str) -> dict:
    """app `scoreFor`: 과목 점수, 없으면 대표 점수."""
    return (row.get("subjectScores") or {}).get(subject) or row.get("score") or {}


def band_ranks(rows: list[dict], region: str = REGION) -> dict:
    """{(과목, 구간): [행…]} — 화면의 `ranking()` 과 같은 순서."""
    out = {}
    for subject in config.SUBJECTS:
        for band in BANDS:
            hits = [r for r in rows
                    if r.get("regionId") == region and subject in (r.get("subjects") or [])
                    and band in _bands_for(r, subject)
                    and (_score(r, subject).get("sampleSize") or 0) > 0]
            hits.sort(key=lambda r: (not _score(r, subject).get("isRanked"),
                                     -(_score(r, subject).get("total") or 0), str(r["id"])))
            if hits:
                out[(subject, band)] = hits
    return out


def band_moves(now_rows: list[dict], before_rows: list[dict],
               region: str = REGION) -> dict:
    """방마다 새 1위와 큰 상승. 지난 회차 순위가 없으면 비운다."""
    now, before = band_ranks(now_rows, region), band_ranks(before_rows, region)
    out = {b: {"newFirsts": [], "rises": []} for b in BANDS}
    for (subject, band), rows in now.items():
        prev = before.get((subject, band))
        if not prev:
            continue
        name = config.SUBJECTS[subject]
        was = {str(r["id"]): i + 1 for i, r in enumerate(prev)
               if _score(r, subject).get("isRanked")}
        for i, r in enumerate(rows[:RISE_TOP]):
            if not _score(r, subject).get("isRanked"):
                break
            rank, old = i + 1, was.get(str(r["id"]))
            item = {"name": r.get("displayName") or r.get("name"), "subject": name,
                    "from": old, "to": rank}
            if rank == 1 and old != 1:
                out[band]["newFirsts"].append(item)
            elif old and old - rank >= RISE_MIN:
                out[band]["rises"].append(item)
    for b in out.values():
        b["rises"].sort(key=lambda x: (-(x["from"] - x["to"]), x["to"], x["name"]))
        b["rises"] = b["rises"][:3]
    return out


# ── 등록부 ───────────────────────────────────────────────────────
def registry_changes(now_rows: list[dict], before_rows: list[dict],
                     today: date | None = None, region: str = REGION) -> dict:
    """등록부(채점 대상 + 등록부만)의 지난 회차 대비 변화. 각 항목에 학년 구간을
    단다 — 비어 있으면 '대상 학년 미확인' 이고 모든 방에 간다."""
    today = today or date.today()
    if not before_rows:
        return {"new": [], "newCount": 0, "gone": [], "goneCount": 0, "goneBulk": False}
    now = {r["id"]: r for r in now_rows if r.get("regionId") == region}
    before = {r["id"]: r for r in before_rows if r.get("regionId") == region}
    absorbed = {str(x) for r in now_rows for x in (r.get("registrationIds") or [])}
    seen_before = set(before) | {str(x) for r in before_rows
                                 for x in (r.get("registrationIds") or [])}
    cutoff = (today - timedelta(days=NEW_WITHIN_DAYS)).isoformat()

    def opened(r):
        raw = str(r.get("establishedOn") or "")
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if re.fullmatch(r"\d{8}", raw) else (raw or None)

    def bands(r):
        got = set(r.get("gradeBands") or [])
        for v in (r.get("gradeBandsBySubject") or {}).values():
            got |= set(v or [])
        return [b for b in BANDS if b in got]

    new = []
    for key, r in now.items():
        when = opened(r)
        if key in seen_before or not when or when < cutoff:
            continue
        new.append({"name": r.get("displayName") or r.get("name"),
                    "subjects": r.get("subjects") or [], "openedOn": when,
                    "bands": bands(r)})
    gone = [{"name": r.get("displayName") or r.get("name"), "bands": bands(r)}
            for key, r in before.items() if key not in now and key not in absorbed]
    new.sort(key=lambda x: (x["openedOn"], x["name"] or ""), reverse=True)
    gone.sort(key=lambda x: x["name"] or "")
    bulk = len(gone) > GONE_BULK
    return {"new": new[:12], "newCount": len(new),
            "gone": [] if bulk else gone[:12], "goneCount": len(gone), "goneBulk": bulk}


# ── 일정 ─────────────────────────────────────────────────────────
def _resolve(match: tuple, today: date) -> date | None:
    """한 날짜 조각을 날짜로. 연도가 없으면 가까운 쪽(11월에 '1월 9일' 은 내년)."""
    y, m1, d1, m2, d2, m3, d3 = match
    m, d = int(m1 or m2 or m3), int(d1 or d2 or d3)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    year = int(y) if y else (today.year if m >= today.month - 1 else today.year + 1)
    try:
        return date(year, m, d)
    except ValueError:
        return None


def event_dates(text: str, today: date, first_only: bool = False) -> list[str]:
    """적힌 날짜 중 오늘부터 두 달 안의 것.

    `first_only` — 홈페이지 공지는 첫 날짜가 행사일이고 뒤의 날짜는 기간의 끝
    이나 게시일이다('가을학기 개강 8.31 ~ 12.27'). 첫 날짜가 지났으면 지난
    공지라 아무것도 내지 않는다(실측: 청담 가을학기 개강이 12/27 로 올랐다).
    """
    end = today + timedelta(days=WINDOW_DAYS)
    found = [w for w in (_resolve(m, today) for m in _DATE.findall(text)) if w]
    if first_only:
        found = found[:1]
    return sorted({w.isoformat() for w in found if today <= w <= end})


def classify(rows: list[dict], today: date | None = None) -> tuple[list[dict], int]:
    """검색 결과 → 일정 항목. (항목, 유아 테스트로 빼 낸 수)."""
    today = today or date.today()
    oldest = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    out, seen, banned = [], set(), 0
    for r in sorted(rows, key=lambda x: x.get("posted_at") or "", reverse=True):
        title = (r.get("title") or "").strip()
        url, posted = r.get("source_url") or r.get("url"), r.get("posted_at")
        if not url or url in seen or not posted or posted < oldest or posted > today.isoformat():
            continue
        regions = [r for r, p in _PLACES.items() if p.search(title)]
        if not regions or not _ACADEMY_CONTEXT.search(title) or _NOT_ACADEMY.search(title):
            continue
        if any(w in title for w in _OTHER_PLACES):
            continue
        # '[대치명인성북]' — 브랜드에 '대치' 가 박힌 다른 지역 지점(CLAUDE.md 지점 절).
        if any(w in title for w in OTHER_REGION_WORDS):
            continue
        kind = ("test" if _TEST.search(title) else "session" if _SESSION.search(title)
                else "open" if _OPEN.search(title) else None)
        if not kind:
            continue
        seen.add(url)
        if kind == "test" and _PRESCHOOL.search(title):
            banned += 1
            continue
        text = title + " " + (r.get("snippet") or "")
        out.append({"title": title, "url": url, "postedAt": posted, "kind": kind,
                    "regions": regions, "label": label_for(kind, short_name(title)),
                    "source": "news" if r.get("source") == "naver_news" else "blog",
                    "dates": event_dates(text, today),
                    "bands": [b for b in BANDS if _BAND_WORDS[b].search(title)]})
    return out, banned


def pick_events(rows: list[dict], today: date | None = None) -> list[dict]:
    """지난밤 새로 올라온 것만(아침 소식용)."""
    today = today or date.today()
    cutoff = (today - timedelta(days=NEWS_DAYS)).isoformat()
    return [e for e in classify(rows, today)[0] if e["postedAt"] >= cutoff]


def search_rows() -> list[dict] | None:
    """검색 API. 못 찾은 것과 못 물어본 것을 가른다(None)."""
    if not LIVE_SEARCH:
        return None
    from . import naver
    rows = []
    for query in event_queries():
        for source in EVENT_SOURCES:
            try:
                for r in naver.search(source, query, max_results=30):
                    r["source"] = source
                    rows.append(r)
            except Exception as error:    # 부산물이다 — 실패해도 회차를 잃지 않는다
                print(f"  ! 일정 검색 실패 {source} '{query}': {type(error).__name__}")
    return rows


PRIORITY_TOP = 15             # 학군마다 홈페이지를 자주 볼 대표 학원 수


def homepage_priority(rows: list[dict], regions=REGIONS) -> set[str]:
    """홈페이지를 사흘마다 볼 학원 — 학군마다 근거가 가장 두꺼운 학술 학원."""
    out: set[str] = set()
    for region in regions:
        picked = [r for r in rows if r.get("regionId") == region
                  and set(r.get("subjects") or []) - {"arts", "etc", "general"}]
        picked.sort(key=lambda r: -((r.get("score") or {}).get("sampleSize") or 0))
        out |= {str(r["id"]) for r in picked[:PRIORITY_TOP]}
    return out


def _academy_bands(r: dict) -> list[str]:
    got = set(r.get("gradeBands") or [])
    for v in (r.get("gradeBandsBySubject") or {}).values():
        got |= set(v or [])
    return [b for b in BANDS if b in got]


def homepage_events(cache: dict, rows: list[dict], today: date,
                    regions=REGIONS) -> tuple[list[dict], int]:
    """공식 홈페이지 공지(official.collect 의 events) → 일정 항목.

    제목에 학년 표지가 없으면 **그 학원의 대상 학년**을 쓴다 — 홈페이지 공지는
    '겨울학기 설명회' 처럼 학년을 안 적는 것이 보통이고, 학원이 누구를 받는지는
    이미 안다. 한 달 넘게 못 본 홈페이지의 공지는 믿지 않는다.
    """
    by_id = {str(r["id"]): r for r in rows if r.get("regionId") in regions}
    oldest = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    out, banned, seen = [], 0, set()
    for aid, c in (cache or {}).items():
        r, c = by_id.get(str(aid)), c or {}
        obs = c.get("observed") or {}
        if not r or c.get("blocked") or (c.get("checked_on") or "") < oldest:
            continue
        name = r.get("displayName") or r.get("name")
        for n in obs.get("events") or []:
            title = (n.get("title") or "").strip()
            # 같은 브랜드 다른 지점 공지('분당 예비초2 입학시험')는 이 학원 일정이 아니다.
            if any(w in title for w in OTHER_REGION_WORDS):
                continue
            kind = ("test" if _TEST.search(title) else "session" if _SESSION.search(title)
                    else "open" if _OPEN.search(title) else None)
            if not kind:
                continue
            if kind == "test" and _PRESCHOOL.search(title):
                banned += 1
                continue
            dates = event_dates(" ".join(n.get("dateHints") or []), today, first_only=True)
            # 같은 행사를 홈페이지 여러 곳이 말한다('겨울학기 개강' 배너와 공지 줄).
            if not dates or (aid, kind, dates[0]) in seen:
                continue
            seen.add((aid, kind, dates[0]))
            out.append({"title": f"{name} · {title}", "url": c.get("url"),
                        "key": f'{c.get("url")}#{title}', "postedAt": c.get("checked_on"),
                        "kind": kind, "source": "homepage", "dates": dates,
                        "regions": [r["regionId"]],
                        "label": label_for(kind, short_name(name) or name),
                        "bands": [b for b in BANDS if _BAND_WORDS[b].search(title)]
                                 or _academy_bands(r)})
    return out, banned


def merge_calendar(previous: list[dict], found: list[dict], today: date) -> list[dict]:
    """지난 달력 + 새로 찾은 것. 날짜가 다 지난 항목만 뺀다. 같은 글은 새 쪽.
    홈페이지 공지는 한 주소에 여럿이라 `key`(주소#제목)로 가른다."""
    keep = {e.get("key") or e["url"]: e for e in previous or []}
    for e in found:
        if e["dates"]:
            keep[e.get("key") or e["url"]] = e
    out, same = [], set()
    for e in sorted(keep.values(), key=lambda e: e.get("source") != "homepage"):
        dates = [d for d in e.get("dates") or [] if d >= today.isoformat()]
        if not dates:
            continue
        # 같은 행사를 기사 여러 건이 쓴다. 이름 붙은 말(label)이 같고 첫 날이
        # 같으면 하나만. 이름 없는 '설명회' 는 서로 다른 행사일 수 있어 남긴다.
        kind_only = e.get("label") in KIND_WORDS.values()
        sig = (dates[0], e.get("label"), tuple(e.get("regions") or []))
        if not kind_only and sig in same:
            continue
        same.add(sig)
        out.append({**e, "dates": dates})
    out.sort(key=lambda e: (e["dates"][0], e["title"]))
    return out


# ── 방마다 ───────────────────────────────────────────────────────
def _for_band(items: list[dict], band: str) -> list[dict]:
    """구간 표지가 없는 항목은 '학년 공통' 으로 모든 방에 간다."""
    return [x for x in items if not x.get("bands") or band in x["bands"]]


def rooms(moves: dict, calendar: list[dict], news: list[dict] | None,
          registry: dict, today: date) -> dict:
    week_end = (today + timedelta(days=WEEK_DAYS)).isoformat()
    # 방은 대치 학부모방이다. 달력은 네 학군을 담지만 방에는 대치 일정만.
    calendar = [e for e in calendar if REGION in (e.get("regions") or [REGION])]
    news = [e for e in news or [] if REGION in (e.get("regions") or [REGION])]
    out = {}
    for band in BANDS:
        week = [e for e in _for_band(calendar, band) if e["dates"][0] <= week_end]
        listed = {e["url"] for e in week}
        out[band] = {
            "label": config.GRADE_BAND_NAMES[band],
            "ranking": moves.get(band, {"newFirsts": [], "rises": []}),
            "thisWeek": week[:6],
            "news": [e for e in _for_band(news or [], band) if e["url"] not in listed][:4],
            "newAcademies": _for_band(registry.get("new") or [], band)[:5],
            "goneAcademies": [] if registry.get("goneBulk")
                             else _for_band(registry.get("gone") or [], band)[:5],
        }
    return out


def build(now_rows: list[dict], before_rows: list[dict], previous_calendar: list[dict],
          scoring_changed: bool = False, today: date | None = None,
          official: dict | None = None) -> tuple[dict, list[dict]]:
    """(nightly_brief 의 daechi 키, calendar.json 내용)."""
    today = today or date.today()
    rows = search_rows()
    found, banned = classify(rows or [], today) if rows is not None else ([], 0)
    home, home_banned = homepage_events(official or {}, now_rows, today)
    banned += home_banned
    calendar = merge_calendar(previous_calendar, found + home, today)
    news = None if rows is None else [
        e for e in found if e["postedAt"] >= (today - timedelta(days=NEWS_DAYS)).isoformat()]
    registry = registry_changes(now_rows, before_rows, today)
    brief = {"region": "대치", "scoringChanged": scoring_changed,
             "searched": rows is not None, "bannedCount": banned,
             "calendarCount": len(calendar), "homepageEvents": len(home),
             "rooms": rooms(band_moves(now_rows, before_rows), calendar, news, registry, today)}
    return brief, calendar


def load_calendar(path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("events") or []
    except (OSError, ValueError, AttributeError):
        return []
