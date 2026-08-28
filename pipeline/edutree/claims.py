"""주장(claim) — 근거의 최소 단위.

지금까지 글 한 건은 스칼라 몇 개(sentiment · spam_score · selectivity.hard)로
요약돼 집계로 넘어갔다. 요약된 뒤에는 **어느 문장이 그 숫자를 만들었는지
되짚을 수 없다.** 그래서 두 가지를 못 했다.

  1. 학부모가 실제로 묻는 것(숙제량 · 시험 횟수 · 수업 시간)을 근거와 함께
     남기지 못했다. 감성 점수 안에 녹아 사라졌다.
  2. 한 글의 일부만 취소하지 못했다. posts.py 의 무효화는 글 **전체**를
     끄는 것이라, '이 진입난이도 근거는 틀렸지만 평판 근거는 맞다' 를
     담을 자리가 없었다.

그래서 요약 대신 **분해**한다. 주장 하나가 행 하나이고, 반드시 원문
인용문을 들고 다닌다. 인용문을 못 보여주는 주장은 만들지 않는다.

★ id 는 위치도 인용문도 아닌 **주장의 알맹이**로 짓는다.
  (출처 글 · 학원 · 종류 · 값). 스니펫은 앞뒤가 잘린 채로 오고 회차마다
  길이가 달라지므로 위치로 지으면 같은 주장이 다음 회차에 다른 id 가 되어
  취소 판정이 고아가 된다. 인용문으로 지어도 마찬가지다 — 앞에 한 마디가
  더 붙어 오면 문장 경계가 달라진다(여기서 한 번 틀렸다).
  **인용문은 그 주장의 증거이지 신원이 아니다.**
  판정을 지우면 다음 실행에서 같은 id 의 주장이 그대로 되살아난다 —
  취소를 되돌릴 수 있는 이유가 이것이다.

★ 값은 학원 이름 근처에서만 읽는다.
  analyze.subjects_near 가 배운 것과 같은 함정이다. '주 3회' 라는 낱말이
  글에 있다는 것과 그것이 이 학원 이야기라는 것은 다르다. 비교글에서는
  대개 남의 학원 수업 횟수다.
"""
from __future__ import annotations

import hashlib
import re
import statistics
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime

# ── 주장의 종류 ────────────────────────────────────────────────────
#
# 기둥 근거(rep.* · sel.*)와 운영 사실(fact.*)을 한 표에 둔다. 같은 취소
# 회로를 타야 하기 때문이다 — 사용자가 '이 근거는 틀렸다' 고 할 때 그것이
# 평판 근거인지 진입난이도 근거인지는 사용자의 관심사가 아니다.
FACT_KINDS = {
    "fact.homework":      ("숙제량",      "분/일"),
    "fact.test_freq":     ("시험 횟수",   "회/월"),
    "fact.class_freq":    ("수업 횟수",   "회/주"),
    "fact.class_minutes": ("1회 수업",    "분"),
}

# 값을 숫자로 내려면 서로 다른 글이 이만큼 있어야 한다.
# 1건짜리 '주 3회' 는 그 집 아이 반 이야기지 그 학원의 사실이 아니다.
MIN_CORROBORATION = 2

# 최댓값이 최솟값의 이 배를 넘으면 중앙값을 내지 않는다.
# 반이 다르거나 오탐이 섞인 것인데, 어느 쪽이든 하나의 숫자로 단정할
# 상태가 아니다. 실측에서 '숙제량 20분 · 10분~5시간' 이 나왔다.
DISPUTE_RATIO = 3.0

# 이보다 오래된 값은 회색으로 표시한다. 지우지는 않는다 — 낡음은 가짜가
# 아니다. 커리큘럼은 해마다 바뀌지만 3년 전 주 3회가 거짓이었던 건 아니다.
STALE_DAYS = 365

# 학원 이름에서 이만큼 떨어진 수치는 이 학원 이야기로 보지 않는다.
# analyze.SUBJECT_WINDOW(45)보다 조금 넓다 — 수치 표현은 이름과 문장
# 하나쯤 떨어져 나오는 일이 흔하다("OO학원 다니는데 수업은 주 3회예요").
FACT_WINDOW = 70


# ── 한국어 수량 표현 ───────────────────────────────────────────────
#
# 아라비아 숫자만 보면 절반을 놓친다. '주 3회' 만큼 '일주일에 세 번' 이
# 흔하다. 실측 스니펫에서 수사 표기가 4할 가까이 됐다.
_KO_NUM = {
    "한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "석": 3, "서": 3,
    "네": 4, "넷": 4, "넉": 4, "너": 4, "다섯": 5, "여섯": 6, "일곱": 7,
    "여덟": 8, "아홉": 9, "열": 10,
}
# 어림수. '두세 번' 은 2도 3도 아니라 범위다. 하나로 눌러 담으면 그 글이
# 말하지 않은 정밀도를 지어내게 된다.
_KO_RANGE = {
    "한두": (1, 2), "두세": (2, 3), "서너": (3, 4), "네다섯": (4, 5),
    "대여섯": (5, 6), "예닐곱": (6, 7),
}
# 긴 것부터 봐야 한다. '한' 을 먼저 보면 '한두' 가 1 이 된다.
_NUM_WORDS = sorted([*_KO_RANGE, *_KO_NUM], key=len, reverse=True)
_NUM_PAT = r"(?:\d{1,3}|" + "|".join(_NUM_WORDS) + r")"


def _num(token: str) -> tuple[float, float] | None:
    """수량 표기 → (하한, 상한). 범위가 아니면 둘이 같다."""
    token = token.strip()
    if token.isdigit():
        n = float(token)
        return (n, n) if 0 < n <= 500 else None
    if token in _KO_RANGE:
        lo, hi = _KO_RANGE[token]
        return float(lo), float(hi)
    if token in _KO_NUM:
        n = float(_KO_NUM[token])
        return n, n
    return None


# ── 정규화와 원문 위치 ─────────────────────────────────────────────
def _norm_map(text: str) -> tuple[str, list[int]]:
    """정규화 문자열과 (정규화 위치 → 원문 위치) 대응표.

    이름 매칭은 띄어쓰기를 무시해야 하고('청담 어학원' = '청담어학원'),
    인용문은 원문 그대로여야 한다. 두 요구가 충돌하므로 대응표를 든다.
    """
    chars: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        if ch.isalnum():
            chars.append(ch.lower())
            idx.append(i)
    return "".join(chars), idx


def _to_norm_pos(idx: list[int], orig_pos: int) -> int:
    """원문 위치 → 가장 가까운 정규화 위치."""
    return bisect_left(idx, orig_pos)


def _name_spots(flat: str, names) -> list[int]:
    spots: list[int] = []
    for name in names or ():
        n = "".join(c.lower() for c in str(name) if c.isalnum())
        if len(n) < 2:
            continue
        i = flat.find(n)
        while i >= 0:
            spots.append(i)
            i = flat.find(n, i + 1)
    return spots


# 문장 경계. 스니펫은 마침표를 자주 빠뜨리므로 종결어미도 함께 본다.
_SENT_END = re.compile(r"[.!?…\n]|(?<=[다요])\s")


def _sentence_at(text: str, start: int, end: int) -> str:
    """수치가 들어 있는 문장. 인용문은 이 값이 그대로 화면에 나간다."""
    left = 0
    for m in _SENT_END.finditer(text, 0, start):
        left = m.end()
    right = len(text)
    m = _SENT_END.search(text, end)
    if m:
        right = m.start() + 1
    quote = text[left:right].strip()
    # 너무 길면 수치 주변만. 화면에 한 줄로 들어가야 한다.
    if len(quote) > 90:
        a = max(left, start - 40)
        b = min(right, end + 40)
        quote = ("…" if a > left else "") + text[a:b].strip() + ("…" if b < right else "")
    return quote


# ── 주제 판별 ──────────────────────────────────────────────────────
#
# '주 3회' 하나로는 수업인지 시험인지 숙제인지 알 수 없다. 수치 주변의
# 낱말을 봐야 한다. 여기서 틀리면 숙제 횟수가 수업 횟수로 둔갑한다.
_TOPIC_WORDS = {
    "test": ("시험", "테스트", "쪽지", "단어시험", "모의고사", "평가", "퀴즈",
             "데일리테스트", "클리닉"),
    "homework": ("숙제", "과제", "숙제량", "복습지", "워크북"),
    "class": ("수업", "등원", "수강", "강의", "주당", "커리", "반"),
}
# 레벨테스트는 시험이 아니라 **입반 절차**다. 진입난이도 쪽 신호이므로
# 시험 횟수에 넣으면 안 된다 — 매달 보는 정기시험처럼 읽힌다.
_NOT_TEST = ("레벨테스트", "레테", "입반", "배치고사", "반배정", "편성고사")

_TOPIC_WINDOW = 16


def _topic_near(flat: str, pos: int) -> str | None:
    """정규화 위치 pos 주변의 주제. 없으면 None."""
    lo = max(0, pos - _TOPIC_WINDOW)
    hi = min(len(flat), pos + _TOPIC_WINDOW)
    win = flat[lo:hi]
    if any(w in win for w in _NOT_TEST):
        return "level_test"
    best, best_d = None, None
    for topic, words in _TOPIC_WORDS.items():
        for w in words:
            i = win.find(w)
            while i >= 0:
                d = abs((lo + i) - pos)
                if best_d is None or d < best_d:
                    best, best_d = topic, d
                i = win.find(w, i + 1)
    return best


# ── 추출 규칙 ──────────────────────────────────────────────────────
#
# (정규식, 기본 주제, 단위 환산). 원문에서 찾는다 — 띄어쓰기가 살아 있어야
# '주 3회' 와 '주3회' 를 같은 식으로 잡는다.
_N = _NUM_PAT

# 빈도: 주 N회 / 일주일에 N번 / N회/주
#
# ★ 뒤쪽 형태는 빗금(/)을 반드시 요구한다. `[회번]\s*주` 로 열어 두면
#   '쿠킹스튜디오에서 한번 주문했어요' 가 '주 1회' 가 된다(실측).
_FREQ_WEEK = re.compile(
    rf"(?:주에?\s*|일\s*주일?에\s*|매주\s*)({_N})\s*[회번]"
    rf"|({_N})\s*[회번]\s*/\s*주")
# 빈도: 한 달에 N번 / 월 N회
_FREQ_MONTH = re.compile(
    rf"(?:한?\s*달에\s*|월\s*|매달\s*)({_N})\s*[회번]")
# 기간 표현 자체가 빈도인 것들
_FREQ_WORD = re.compile(r"격주|매주|매일|주말반|매달|한\s*달에\s*한\s*[번회]")
# 길이: N분 / N시간
_DURATION = re.compile(rf"({_N})\s*(시간|분)")

# ★ 시각을 길이로 읽지 않는다.
#   '화,목 4시20분' 의 '20분' 은 수업 길이가 아니라 시작 시각이다.
#   실측에서 도곡시매쓰의 '1회 수업 20분' 이 여기서 나왔다.
_CLOCK = re.compile(r"\d\s*시\s*$")

# ★ 부정문을 사실로 읽지 않는다.
#   '숙제할 때도 10분도 못 앉아있고' 는 숙제량이 아니라 집중력 이야기다.
#   부정어가 수치 **뒤에** 오는 것이 한국어라 오른쪽을 본다.
_NEGATED = re.compile(r"^\s*(?:도|밖에|조차|마저)?\s*(?:못|안|않|없)")

# ★ 남의 학원을 가리키는 일반 명사.
#   '주3회 2시간씩 영어학원을 35만원에 다니고있어요' 는 정상수학학원 글에
#   섞여 있었지만 영어학원 이야기다. 상호가 아니라 업종어로 부르므로
#   rival_names(학원명 목록)로는 잡히지 않는다.
_GENERIC_ACADEMY = re.compile(
    r"(?:영어|수학|국어|과학|논술|독서|미술|피아노|체육|코딩|중국어|일어)"
    r"\s*(?:학원|교습소|어학원)")

# ★ 묻는 글과 전해 들은 말은 사실이 아니다.
#   '주1회 1시간이라도 할까 하는데 어떨까요?' 는 그 학원의 수업 횟수가
#   아니라 이 사람의 고민이다. 질문글이 후기와 같은 무게를 갖는 것이
#   진입난이도 기둥에서 확인된 결함이고(측정 74.1점), 사실 추출에도
#   그대로 해당한다.
#
# ★ 어미를 넓게 잡으면 안 된다. '나요' 를 넣었더니 '숙제 10분이면 끝나요'
#   가 의문문이 됐다 — '끝나요' 의 '나요' 는 어간의 일부다. 물음표와
#   중의성 없는 표지만 쓴다. 한국어 질문글은 대개 물음표를 찍는다.
_HEARSAY = re.compile(
    r"\?|인가요|어떤가요|어떨까|할까|을까요|ㄹ까요|던데|카더라|"
    r"라던|라는데|라고\s*함|맞나요")


def _duration_minutes(token: str, unit: str) -> tuple[float, float] | None:
    got = _num(token)
    if not got:
        return None
    mul = 60.0 if unit == "시간" else 1.0
    lo, hi = got[0] * mul, got[1] * mul
    # 사람이 쓸 법한 범위 밖은 오탐이다. '2000분 수업' 은 없다.
    if not (10 <= lo <= 600):
        return None
    return lo, hi


def _extract_facts(text: str, flat: str, idx: list[int], spots: list[int],
                   rival_spots: list[int], generic_spots: list[int],
                   mine_flat=frozenset()) -> list[dict]:
    """운영 사실 후보. (kind, value, value_high, unit, span, quote)"""
    out: list[dict] = []

    owners = [(s, "mine") for s in spots] + [(s, "rival") for s in rival_spots]

    def near_name(orig_pos: int) -> bool:
        """이 수치가 **이 학원** 것인가. 임자를 두 단계로 가린다.

        ① 상호끼리는 **왼쪽 우선**.
           '다라영어학원은 주 5회인데 가나수학학원은 모르겠어요' 에서
           '주 5회' 는 가나수학학원 쪽이 글자 수로는 가깝지만 다라영어학원
           이야기다. 한국어는 수식어가 앞에 온다. (왼쪽에 아무 이름도
           없을 때만 거리로 정한다 — '주 3회인 가나수학학원' 도 있다)

        ② 업종어는 **더 가까울 때만** 임자.
           '주3회 2시간씩 영어학원을 다녀요' 의 '영어학원' 은 수치보다
           뒤에 있지만 그 수치의 임자다(다니다의 목적어). 왼쪽 우선
           규칙으로는 못 잡는다. 그렇다고 업종어에 왼쪽 우선을 주면
           '수학학원 알아보다가 가나수학학원 주 3회로 정했어요' 처럼
           멀쩡한 근거가 날아간다. 그래서 거리로만 견준다.
        """
        if not spots:
            return False
        p = _to_norm_pos(idx, orig_pos)
        left = [(p - s, who) for s, who in owners if 0 <= p - s <= FACT_WINDOW]
        if left:
            if min(left)[1] != "mine":
                return False
        else:
            near = [(abs(p - s), who) for s, who in owners
                    if abs(p - s) <= FACT_WINDOW]
            if not near or min(near)[1] != "mine":
                return False
        mine_d = min(abs(p - s) for s in spots)
        return not any(abs(p - g) < mine_d for g in generic_spots)

    def negated(m: re.Match) -> bool:
        return bool(_NEGATED.match(text[m.end(): m.end() + 8]))

    def add(kind: str, lo: float, hi: float, m: re.Match) -> None:
        if negated(m):
            return
        quote = _sentence_at(text, m.start(), m.end())
        if _HEARSAY.search(quote):            # 묻는 글·전해 들은 말은 사실이 아니다
            return
        # ★ 문장이 남의 학원을 업종어로 부르면서 내 이름은 없으면 남의 값이다.
        #   거리 규칙만으로는 못 잡는 경우가 있다. 실측: 제목 '학원비 …
        #   같은게 정상인가요' 가 일상어 '정상' 때문에 정상어학원 글로
        #   잡혔고, 본문 '주3회 2시간씩 영어학원을 다니고있어요' 가 그
        #   학원의 수업 횟수가 됐다. 그 문장에 정상은 없다.
        if _GENERIC_ACADEMY.search(quote):
            qflat = "".join(c.lower() for c in quote if c.isalnum())
            if not any(c and c in qflat for c in mine_flat):
                return
        out.append({
            "kind": kind,
            "value": round(lo, 1),
            "value_high": round(hi, 1) if hi != lo else None,
            "quote": quote,
        })

    # ── 주당 빈도 ──
    for m in _FREQ_WEEK.finditer(text):
        if not near_name(m.start()):
            continue
        token = m.group(1) or m.group(2)
        got = _num(token)
        if not got or got[1] > 14:            # 주 14회 넘는 건 오탐
            continue
        topic = _topic_near(flat, _to_norm_pos(idx, m.start()))
        if topic == "test":
            add("fact.test_freq", got[0] * 4, got[1] * 4, m)   # 주→월
        elif topic in ("class", None):
            add("fact.class_freq", got[0], got[1], m)
        # homework/level_test 는 '주 N회' 로 세지 않는다. 숙제는 분량이지
        # 횟수가 아니고, 레벨테스트는 정기시험이 아니다.

    # ── 월간 빈도 ──
    for m in _FREQ_MONTH.finditer(text):
        if not near_name(m.start()):
            continue
        got = _num(m.group(1))
        if not got or got[1] > 30:
            continue
        topic = _topic_near(flat, _to_norm_pos(idx, m.start()))
        if topic == "test":
            add("fact.test_freq", got[0], got[1], m)

    # ── 낱말 자체가 빈도인 것 ──
    for m in _FREQ_WORD.finditer(text):
        if not near_name(m.start()):
            continue
        topic = _topic_near(flat, _to_norm_pos(idx, m.start()))
        if topic != "test":
            continue
        word = m.group(0).replace(" ", "")
        per_month = {"격주": 2.0, "매주": 4.0, "매일": 20.0,
                     "매달": 1.0}.get(word)
        if per_month is None and word.startswith("한달에한"):
            per_month = 1.0
        if per_month:
            add("fact.test_freq", per_month, per_month, m)

    # ── 길이 ──
    for m in _DURATION.finditer(text):
        if not near_name(m.start()):
            continue
        if m.group(2) == "분" and _CLOCK.search(text[:m.start()]):
            continue                          # '4시 20분' 은 시각이다
        got = _duration_minutes(m.group(1), m.group(2))
        if not got:
            continue
        topic = _topic_near(flat, _to_norm_pos(idx, m.start()))
        if topic == "homework":
            # 숙제는 하루 기준으로 본다. 주 단위로 쓴 글은 드물다.
            add("fact.homework", got[0], got[1], m)
        elif topic == "class":
            add("fact.class_minutes", got[0], got[1], m)

    return out


# ── 주장 만들기 ────────────────────────────────────────────────────
def claim_id(url_hash: str, academy_key: str, kind: str, anchor: str) -> str:
    """결정적 id. 같은 글의 같은 주장은 언제나 같은 id 다.

    [anchor] 는 그 주장을 그 글 안에서 구별하는 알맹이다. 사실형은 값
    ('3.0' · '2.0~3.0'), 사건형은 촉발 낱말('떨어졌').
    """
    seed = "|".join([str(url_hash), str(academy_key), kind, str(anchor)])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def extract(mention: dict, names=None, rivals=frozenset()) -> list[dict]:
    """언급 한 건 → 주장 여러 건.

    [names]  이 학원을 가리키는 표기들(analyze.name_candidates). 원문에서
             이름이 어디 나오는지 알아야 '그 수치가 이 학원 것인가' 를 안다.
    [rivals] 다른 학원 이름들(build.rival_names). 남의 이름이 더 가까우면
             그 수치는 남의 것이다.
    """
    title = mention.get("title") or ""
    body = mention.get("snippet") or ""
    text = f"{title} {body}".strip()
    if not text:
        return []

    flat, idx = _norm_map(text)
    targets = set(names or ())
    if mention.get("academy_name"):
        targets.add(mention["academy_name"])
    spots = _name_spots(flat, targets)
    # 내 이름과 겹치는 후보는 남이 아니다. '가나수학' 과 '가나수학학원' 이
    # 서로를 밀어내면 정상 근거가 통째로 사라진다.
    mine = {"".join(c.lower() for c in str(t) if c.isalnum()) for t in targets}
    strangers = {r for r in rivals
                 if not any(r in c or c in r for c in mine if c)}
    rival_spots = _name_spots(flat, strangers)
    # 상호 대신 업종어로 부른 남의 학원('영어학원')도 임자가 될 수 있다.
    # 내 이름 자리와 겹치는 것은 뺀다 — '대치정상수학학원' 안의 '수학학원'
    # 까지 남으로 치면 자기 근거를 자기가 밀어낸다.
    mine_ranges = [(s, s + len(c)) for c in mine if c
                   for s in _name_spots(flat, {c})]
    generic_spots: list[int] = []
    for gm in _GENERIC_ACADEMY.finditer(text):
        p = _to_norm_pos(idx, gm.start())
        if not any(a <= p < b for a, b in mine_ranges):
            generic_spots.append(p)

    url_hash = mention.get("url_hash") or ""
    key = mention.get("academy_key") or ""
    posted = mention.get("posted_at")

    out: list[dict] = []
    seen: set[str] = set()
    for raw in _extract_facts(text, flat, idx, spots, rival_spots,
                              generic_spots, {c for c in mine if len(c) >= 2}):
        quote = raw["quote"]
        if not quote:
            continue
        anchor = (f'{raw["value"]}~{raw["value_high"]}'
                  if raw["value_high"] is not None else str(raw["value"]))
        cid = claim_id(url_hash, key, raw["kind"], anchor)
        # 한 글이 같은 값을 두 번 말해도 주장은 하나다. 두 번 세면 한 사람이
        # 두 번 말한 것이 두 사람이 말한 것처럼 보인다.
        if cid in seen:
            continue
        seen.add(cid)
        out.append({
            "id": cid,
            "url_hash": url_hash,
            "academy_key": key,
            "kind": raw["kind"],
            "value": raw["value"],
            "value_high": raw["value_high"],
            "unit": FACT_KINDS[raw["kind"]][1],
            "quote": quote,
            "extractor": "rule:fact_v1",
            "posted_at": posted,
            "author_hash": mention.get("author_hash"),
            "source_url": mention.get("source_url"),
            "band": mention.get("band"),
            "status": "active",
        })
    return out


def extract_all(mentions: list[dict], candidates: dict,
                rivals=frozenset()) -> list[dict]:
    """수집분 전체 → 주장 전체.

    스팸으로 배제된 글에서는 뽑지 않는다. 홍보글의 '주 5회 집중반!' 은
    사실 진술이 아니라 광고 문구다.
    """
    out: list[dict] = []
    for m in mentions:
        if m.get("is_excluded"):
            continue
        out.extend(extract(m, candidates.get(m.get("academy_key")), rivals))
    return out


# ── 집계 — 사실 카드 ───────────────────────────────────────────────
def _as_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None


def _fmt(value: float, unit: str) -> str:
    if unit == "분/일" and value >= 60:
        hours = value / 60
        return f"{hours:.0f}시간" if abs(hours - round(hours)) < 0.05 \
            else f"{hours:.1f}시간"
    n = f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"
    return n + {"회/주": "회", "회/월": "회", "분": "분", "분/일": "분"}[unit]


def _summarize(rows: list[dict], unit: str, today: date) -> dict:
    """근거 건수에 따라 무엇을 말할 수 있는지 정한다.

    ★ 1건이면 숫자를 내지 않는다. 그 집 아이 반 이야기일 수 있고, 숫자로
      적는 순간 그것이 그 학원의 사실처럼 읽힌다. 인용문만 보여준다.
    """
    rows = sorted(rows, key=lambda r: str(r.get("posted_at") or ""), reverse=True)
    authors = {r.get("author_hash") for r in rows if r.get("author_hash")}
    newest = max((d for r in rows if (d := _as_date(r.get("posted_at")))),
                 default=None)
    card = {
        "n": len(rows),
        "sources": max(len(authors), 1) if authors else len(rows),
        "quotes": [{"quote": r["quote"], "url": r.get("source_url"),
                    "claimId": r["id"], "postedAt": str(r["posted_at"])
                    if r.get("posted_at") else None}
                   for r in rows[:4]],
        "stale": bool(newest and (today - newest).days > STALE_DAYS),
        "value": None, "low": None, "high": None, "text": None,
        "disputed": False,
    }
    if len(rows) < MIN_CORROBORATION:
        return card

    lows = [r["value"] for r in rows]
    highs = [r.get("value_high") or r["value"] for r in rows]
    mid = statistics.median(lows)
    lo, hi = min(lows), max(highs)
    card.update({"low": lo, "high": hi})

    # ★ 값이 이만큼 벌어지면 중앙값을 내지 않는다.
    #   실측에서 '숙제량 20분 · 10분~5시간' 이 나왔다. 중앙값 20분은
    #   정밀해 보이지만 근거에 그 정밀도가 없다. 반이 다르거나 오탐이
    #   섞인 것인데, 어느 쪽이든 숫자로 단정할 상태가 아니다.
    #   구간별로 갈릴 수 있으면 facts_for 가 byBand 로 쪼갠다.
    if hi >= max(lo, 1) * DISPUTE_RATIO:
        card["disputed"] = True
        card["text"] = f"{_fmt(lo, unit)}~{_fmt(hi, unit)} · 후기마다 다름"
        return card

    card["value"] = mid
    if lo == hi:
        card["text"] = _fmt(mid, unit)
    elif unit in ("회/주", "회/월"):
        # 횟수의 중앙값은 화면에서 읽히지 않는다. 주1회와 주2회 두 건의
        # 중앙값 '1.5회' 는 어느 반에도 없는 값이다. 범위만 적는다.
        card["text"] = f"{_fmt(lo, unit)}~{_fmt(hi, unit)}"
    else:
        card["text"] = f"{_fmt(mid, unit)} · {_fmt(lo, unit)}~{_fmt(hi, unit)}"
    return card


_BAND_LABEL = {"elem_low": "예비초~초3", "elem_high": "초4~초6",
               "middle": "중등", "high": "고등"}


def facts_for(rows: list[dict], today: date | None = None) -> dict:
    """한 학원의 주장들 → 화면에 낼 사실 카드.

    ★ 값이 갈리면 평균 내지 않는다. 주2회와 주5회의 평균 3.5회는 어느
      반에도 없는 숫자다. band_near_one 이 이미 글마다 학년 구간을 달아
      두므로 구간별로 쪼갠다. 못 쪼개면 범위로 보여준다.
    """
    today = today or date.today()
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("status") != "active" or r["kind"] not in FACT_KINDS:
            continue
        by_kind[r["kind"]].append(r)

    out: dict[str, dict] = {}
    for kind, group in by_kind.items():
        label, unit = FACT_KINDS[kind]
        card = _summarize(group, unit, today)
        card.update({"label": label, "unit": unit})

        # 구간별로 갈라야 하는가. 두 구간 이상이 각각 근거를 충분히 갖고,
        # 값이 실제로 다를 때만 가른다. 그 조건이 아니면 쪼개 봐야 같은
        # 말을 두 번 하는 것이다.
        by_band: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            if r.get("band"):
                by_band[r["band"]].append(r)
        solid = {b: rs for b, rs in by_band.items()
                 if len(rs) >= MIN_CORROBORATION}
        if len(solid) >= 2:
            parts = {b: _summarize(rs, unit, today) for b, rs in solid.items()}
            values = {p["value"] for p in parts.values()}
            # 구간마다 값이 확정되고 서로 달라야 가른다. 한쪽이 여전히
            # 갈리는 상태면 쪼개도 같은 말을 두 번 하는 것이다.
            if None not in values and len(values) > 1:
                card["byBand"] = {
                    b: {**p, "label": _BAND_LABEL.get(b, b)}
                    for b, p in parts.items()
                }
        out[kind] = card

    # 주당 수업시간 — 횟수와 길이가 **둘 다** 확정됐을 때만 곱한다.
    # 한쪽이 1건뿐인데 곱하면 그 글이 말하지 않은 값을 지어내게 된다.
    freq, mins = out.get("fact.class_freq"), out.get("fact.class_minutes")
    if freq and mins and freq["value"] and mins["value"]:
        total = freq["value"] * mins["value"] / 60
        out["derived.class_hours"] = {
            "label": "주당 수업시간",
            "unit": "시간/주",
            "text": f"{total:.0f}시간" if abs(total - round(total)) < 0.05
                    else f"{total:.1f}시간",
            "value": round(total, 1),
            "n": min(freq["n"], mins["n"]),
            "derivedFrom": ["fact.class_freq", "fact.class_minutes"],
            "stale": freq["stale"] or mins["stale"],
            "quotes": [],
        }
    return out


def by_academy(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r["academy_key"]].append(r)
    return dict(out)


def summary(rows: list[dict]) -> str:
    """실행 로그 한 줄."""
    if not rows:
        return "주장 0건"
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r["kind"]] += 1
    parts = " · ".join(f"{FACT_KINDS.get(k, (k, ''))[0]} {n:,}"
                       for k, n in sorted(counts.items()))
    return f"주장 {len(rows):,}건 ({parts})"
