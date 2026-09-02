"""수집된 언급의 감성 · 신뢰도 · 스팸 분석.

사전 기반이다. 학원 도메인 한국어는 일반 감성사전이 잘 못 다룬다
("빡세다"는 부정어처럼 보이지만 이 바닥에선 칭찬에 가깝다).
그래서 도메인 사전을 직접 들고 간다.

★ 업그레이드 경로: 이 모듈의 score_sentiment() 만 KoBERT/LLM 분류기로
  교체하면 나머지 파이프라인은 그대로 동작한다. 인터페이스를 고정해 두었다.
"""
from __future__ import annotations

import functools
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime

# ── 감성 사전 ──────────────────────────────────────────────────────
POSITIVE = {
    "좋아요": 1.0, "좋았": 1.0, "좋은": 0.9, "만족": 1.0, "추천": 1.1,
    "최고": 1.2, "잘가르": 1.2, "실력": 0.7, "친절": 0.8, "꼼꼼": 1.0,
    "체계적": 1.0, "성적올": 1.3, "올랐": 1.2, "향상": 1.0, "효과": 0.9,
    "감사": 0.8, "믿음": 0.9, "신뢰": 0.9, "적성에맞": 0.9, "재밌": 0.8,
    "이해가": 0.8, "케어": 0.7, "관리잘": 1.1, "빡세": 0.5, "탄탄": 0.9,
    "명강": 1.1, "합격": 1.2, "붙었": 1.1, "통과": 0.7, "괜찮": 0.6,
}
NEGATIVE = {
    "별로": -1.0, "실망": -1.2, "비싸": -0.8, "비추": -1.3, "그만": -0.7,
    "옮겼": -0.8, "옮길": -0.7, "불친절": -1.2, "방치": -1.3, "산만": -0.9,
    "떨어졌": -1.0, "안맞": -0.9, "후회": -1.3, "최악": -1.5, "무성의": -1.2,
    "대충": -1.1, "숙제만": -0.8, "안늘": -1.0, "효과없": -1.2, "돈아까": -1.3,
    "차별": -1.2, "짜증": -1.0, "힘들어해": -0.7, "스트레스": -0.7, "그만두": -1.0,
}
# 부정 표현. 앞선 감성어의 부호를 뒤집는다.
NEGATORS = ("안 ", "안", "않", "못", "없", "아니", "별로")
INTENSIFIERS = {"정말": 1.3, "너무": 1.25, "진짜": 1.25, "완전": 1.3,
                "강추": 1.4, "엄청": 1.25, "매우": 1.2, "조금": 0.7, "약간": 0.7}

# ── 관점(aspect) 사전 ──────────────────────────────────────────────
ASPECTS = {
    "강사": ("선생님", "쌤", "강사", "원장", "티칭", "설명"),
    "관리": ("관리", "케어", "피드백", "상담", "오답", "출결", "질문"),
    "커리큘럼": ("커리큘럼", "커리", "진도", "교재", "커리큘럼이", "수업방식", "심화"),
    "가격": ("가격", "학원비", "수업료", "교습비", "비용", "만원", "가성비"),
    "반편성": ("레벨테스트", "레테", "반배정", "반편성", "레벨", "테스트"),
    "숙제량": ("숙제", "과제", "숙제량", "양이", "빡세"),
    "시설": ("시설", "자리", "교실", "셔틀", "위치", "거리"),
}

# ── 스팸/바이럴 신호 ───────────────────────────────────────────────
SPAM_PHRASES = (
    "상담문의", "문의주세요", "카톡", "오픈채팅", "지금등록", "선착순",
    "이벤트", "할인", "무료체험", "원장님이하시는", "제휴", "협찬",
    "체험단", "소정의", "원고료", "블로그체험", "포스팅",
)
# 학원이 직접 올리는 홍보글에 자주 나오는 표현.
# 학부모 후기에는 거의 안 쓰이고, 짧은 스니펫에서도 잘 잡힌다.
PROMO_PHRASES = (
    "신청마감", "등록문의", "상담예약", "모집중", "모집합니다",
    "런칭", "개강안내", "설명회신청", "특강안내", "얼리버드", "마감임박",
    "지금바로", "문의하세요", "예약하기", "커리큘럼안내", "입학설명회",
)
# 스니펫이 짧아(평균 120자) 긴 글 기준으로 잡은 임계값은 거의 발동하지 않는다.
# 실측 분포에서 명백한 홍보글이 0.18~0.53 에 몰려 있어 여기에 맞춘다.
SPAM_EXCLUDE_THRESHOLD = 0.35
# 연락처 신호는 세기가 다르다. 전화번호와 카톡 아이디는 광고의 강한 증거지만,
# 링크는 아니다 — 카페 스니펫은 본문 첫 줄이 URL인 경우가 흔해서, 링크만으로
# 배제하면 "OO학원 어떤가요?" 같은 평범한 질문글까지 걷어내게 된다.
PHONE = re.compile(r"01[016-9][-\s]?\d{3,4}[-\s]?\d{4}")
KAKAO = re.compile(r"카톡\s*:|오픈\s*채팅|kakao|카카오톡\s*문의")
URL = re.compile(r"https?://")
EMOJI_RUN = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]{3,}")

# ── 진입난이도 신호 ────────────────────────────────────────────────
SELECTIVITY_HARD = ("떨어졌", "탈락", "재수", "어렵", "난이도", "빡세", "합격률",
                    "커트라인", "컷", "경쟁", "몇번째", "재응시")
SELECTIVITY_WAIT = ("대기", "웨이팅", "마감", "자리없", "티오", "T.O", "빈자리",
                    "등록전쟁", "오픈런", "결원")


# 등급반(레벨반) 사다리. 위로 갈수록 들어가기 어렵다.
#
# 학원마다 반 이름이 제각각이라 표기를 티어로 묶는다. 정확한 반 이름을
# 맞히려는 것이 아니라 '어느 층인가'만 본다 — 층은 학원이 달라도 통한다.
CLASS_TIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("top", ("최상위", "탑반", "top반", "마스터", "올림피아드", "경시반",
             "킬러반", "에이스")),
    ("advanced", ("심화", "어드밴스", "인텐시브", "특목", "영재", "고급")),
    ("regular", ("정규", "일반반", "내신반", "표준")),
    ("basic", ("기초", "베이직", "입문", "파닉스", "초급")),
)

TIER_LABELS = {
    "top": "최상위반", "advanced": "심화반",
    "regular": "정규반", "basic": "기초반",
}


# 반 이름 주변에서 난이도 단어를 찾을 범위(글자). 한 글에 여러 반이
# 나오면 '기초반에서 시작해 심화반 가기 어렵다' 처럼 난이도가 엉뚱한 반에
# 붙는다. 반 이름 근처만 본다.
TIER_WINDOW = 40


def class_tier_signals(text: str, exclude: str = "") -> dict[str, dict]:
    """등급반별 난이도 신호. {tier: {'hard': n, 'wait': n}}

    [exclude] 로 학원 이름을 먼저 지운다. '최상위수학교습소' 같은 이름이
    그대로 '최상위반' 신호로 잡히면 학원 이름이 곧 난이도가 되어 버린다.

    난이도 단어는 **반 이름 주변에서만** 센다. 글 전체에서 세면 한 글에
    여러 반이 나올 때 서로의 난이도를 훔쳐 간다 — 실제로 그렇게 짰다가
    기초반이 최상위반보다 어렵다는 결과가 나왔다.
    """
    flat = _norm(text)
    if exclude:
        flat = flat.replace(_norm(exclude), " ")

    out: dict[str, dict] = {}
    for tier, kws in CLASS_TIERS:
        windows: list[str] = []
        for kw in kws:
            k = _norm(kw)
            start = 0
            while True:
                i = flat.find(k, start)
                if i < 0:
                    break
                windows.append(flat[max(0, i - TIER_WINDOW): i + len(k) + TIER_WINDOW])
                start = i + len(k)
        if not windows:
            continue
        near = " ".join(windows)
        out[tier] = {
            "hard": sum(1 for w in SELECTIVITY_HARD if _norm(w) in near),
            "wait": sum(1 for w in SELECTIVITY_WAIT if _norm(w) in near),
        }
    return out


def class_tiers(text: str, exclude: str = "") -> list[str]:
    """본문에서 언급된 등급반 티어."""
    return list(class_tier_signals(text, exclude))


def _windowed(text: str, term: str, before: int = 6) -> str:
    idx = text.find(term)
    return text[max(0, idx - before): idx] if idx >= 0 else ""


def score_sentiment(text: str) -> tuple[float, dict[str, float]]:
    """텍스트 → (전체 감성 [-1,1], 관점별 감성).

    이 함수의 시그니처가 곧 계약이다. 모델로 교체할 때 이것만 맞추면 된다.
    """
    if not text:
        return 0.0, {}

    flat = text.replace(" ", "")
    hits: list[tuple[str, float]] = []

    for lexicon in (POSITIVE, NEGATIVE):
        for term, weight in lexicon.items():
            if term not in flat:
                continue
            w = weight
            prefix = _windowed(flat, term)
            if any(neg in prefix for neg in NEGATORS):
                w = -w * 0.8                       # 부정 표현은 부호 반전 + 감쇠
            for booster, mult in INTENSIFIERS.items():
                if booster in prefix:
                    w *= mult
                    break
            hits.append((term, w))

    if not hits:
        return 0.0, {}

    total = sum(w for _, w in hits)
    # tanh 로 [-1,1] 로 눌러 담는다. 감성어를 많이 쓴 글이 무한정 강해지지 않도록.
    overall = math.tanh(total / 2.5)

    aspects: dict[str, float] = {}
    for aspect, keywords in ASPECTS.items():
        if not any(k in flat for k in keywords):
            continue
        near = [w for term, w in hits if abs(flat.find(term) - min(
            (flat.find(k) for k in keywords if k in flat), default=10 ** 6)) < 40]
        if near:
            aspects[aspect] = round(math.tanh(sum(near) / 2.0), 3)
    return round(overall, 3), aspects


def score_spam(text: str, title: str = "") -> float:
    """광고/바이럴 의심도 [0,1]. 높을수록 점수 반영에서 배제된다."""
    blob = f"{title} {text}"
    flat = blob.replace(" ", "")
    score = 0.0
    score += 0.18 * sum(1 for p in SPAM_PHRASES if p in flat)
    score += 0.20 * sum(1 for p in PROMO_PHRASES if p in flat)
    if PHONE.search(blob):
        score += 0.35
    if KAKAO.search(blob):
        score += 0.30
    if URL.search(blob):
        score += 0.12
    # 【브랜드】 [브랜드] 로 시작하는 제목 + 홍보 표현 = 학원 공식 계정 글
    if re.match(r"^\s*[\[【(]", title or "") and (
            any(p in flat for p in PROMO_PHRASES + SPAM_PHRASES)):
        score += 0.25
    if EMOJI_RUN.search(blob):
        score += 0.15
    if blob.count("#") >= 5:                       # 해시태그 도배
        score += 0.2
    if len(flat) > 40:
        # 같은 어절 반복 = 기계 생성 냄새
        words = re.findall(r"[가-힣]{2,}", blob)
        if words:
            top = Counter(words).most_common(1)[0][1]
            if top / len(words) > 0.25:
                score += 0.15
    return round(min(1.0, score), 3)


def score_credibility(text: str, title: str = "", source: str = "") -> float:
    """구체성 기반 신뢰도 [0,1]. 길고 구체적인 글에 더 큰 가중치."""
    blob = f"{title} {text}"
    flat = blob.replace(" ", "")
    score = 0.25

    length = len(flat)
    score += min(0.30, length / 400 * 0.30)        # 길이 (상한 있음)

    if re.search(r"\d+(학년|개월|년|등급|점|반|레벨)", blob):
        score += 0.15                              # 구체적 수치
    if any(k in flat for k in ("우리아이", "저희아이", "제아이", "둘째", "첫째", "아들", "딸")):
        score += 0.10                              # 1인칭 경험
    if any(k in flat for k in ("다녔", "다니는", "보냈", "보내는", "등록", "그만둔")):
        score += 0.10                              # 실제 수강 이력
    if source == "naver_cafe":
        score += 0.05                              # 카페가 블로그보다 광고 비중이 낮음
    if len(flat) < 40:
        score -= 0.15                              # 한 줄짜리는 신뢰도 낮음

    return round(max(0.0, min(1.0, score)), 3)


# ── 정보량 등급 ────────────────────────────────────────────────────
#
# '홍보글이나 정보가 제한적인 글을 제거' 라는 요구에서, 둘은 결과가 달라야
# 한다. 홍보글은 증거가 아니므로 배제한다. 정보가 얕은 글은 증거가 아닌
# 게 아니라 **어떤 종류의 증거가 아닐 뿐**이다.
#
#   0  이름만 스침 — 의견도 사실도 없다
#   1  의견은 있다 — 감성어가 있다
#   2  검증 가능한 사실이 있다 — 수치나 사건 표현이 있다
#
# ★ 얕은 글을 통째로 버리면 안 된다. 화제성은 '얼마나 회자되는가' 라서
#   한 줄짜리 '거기 좋대요' 도 회자의 증거로는 유효하다. 그 글을 지우면
#   화제성이 정보량을 재는 지표로 변질된다. 반대로 그 글을 평판에 넣으면
#   감성 0.0 이 코호트 평균을 끌어당긴다. 버리는 대신 **쓸 수 있는 곳에서만**
#   쓴다 — 기둥마다 문턱이 다르다(scoring.SUBSTANCE_FLOOR).
_NUMERIC = re.compile(r"\d+\s*(?:회|번|분|시간|명|주|달|개월|만원|등급|점|권|장)")


def score_substance(text: str, title: str = "") -> int:
    """이 글이 어느 층까지 근거가 될 수 있는가. 0·1·2."""
    flat = f"{title} {text}".replace(" ", "")
    if not flat:
        return 0
    if _NUMERIC.search(f"{title} {text}") or any(
            k in flat for k in SELECTIVITY_HARD + SELECTIVITY_WAIT):
        return 2
    if any(t in flat for t in POSITIVE) or any(t in flat for t in NEGATIVE):
        return 1
    return 0


def selectivity_signals(text: str) -> dict[str, int]:
    flat = (text or "").replace(" ", "")
    return {
        "hard": sum(1 for k in SELECTIVITY_HARD if k in flat),
        "wait": sum(1 for k in SELECTIVITY_WAIT if k in flat),
    }


_NORM = re.compile(r"[^가-힣A-Za-z0-9]")


def _norm(text: str) -> str:
    return _NORM.sub("", text or "").lower()


# 학원명이 일반 낱말과 겹칠 때, 본문에 함께 있어야 하는 표지.
# 하나라도 있으면 '학원 이야기'로 본다.
_ACADEMY_MARKERS = (
    "학원", "교습소", "어학원", "레테", "레벨테스트", "입반", "수강", "등원",
    "원장", "선생님", "셔틀", "설명회", "상담", "반편성", "커리큘럼", "교재비",
    "학원비", "수업료", "퇴원", "재원", "결석", "숙제", "분원", "지점",
)

# 학원명이지만 일상어로도 흔히 쓰이는 말.
#
# '책읽기' 학원이 실제로 있는데, 이 말은 그냥 동사구이기도 하다. 그래서
# '아이 책읽기 습관' 같은 육아 글이 전부 그 학원의 근거로 잡혔다
# (382건 중 학원 맥락이 있는 것은 64%, 나머지는 일상 글).
#
# 동명이인(윤도영)과는 다른 문제다. 그쪽은 '뮤지컬' 같은 제외어로 막히지만,
# 일반 명사는 제외할 낱말을 특정할 수 없다 — 대신 **학원 표지를 요구**한다.
GENERIC_NAME_PARTS = (
    "책읽기", "책읽는", "독서", "생각", "공부", "배움", "나눔", "우리",
    "함께", "성장", "미래", "희망", "사랑", "행복", "지혜", "열정",
    # 2026-08-31 추가. 채점 대상 400곳의 알맹이를 훑어 표본이 큰 순으로
    # 근거 글을 눈으로 확인했다(CLAUDE.md 규칙: 낱말을 넣기 전에 본문으로
    # 오탐을 본다). 일곱 곳 모두 근거가 대부분 남의 이야기였다.
    #
    #   테스트 201건 — 기파랑·에이프릴 **레벨테스트** 후기가 전부 걸린다
    #   피아노 196건 — 엄마표 독서·뮤지션 대담·남의 피아노 교습소
    #   새로운 166건 — '**새로운** 영어학원을 찾고 계시나요?(러닝하이)'
    #   포인트 160건 — '터닝**포인트**', 불당동 학원
    #   갈무리 148건 — 해양수산부 합격수기·게임 모음·아이스링크 강습
    #   로드맵 121건 — 'CMS 설명회', '초2 수학 **로드맵** 고민'
    #   음악    51건 — 실용음악·명일동·상일동 남의 음악학원
    #
    # 이름을 지우는 게 아니라 **조건을 더한다**(학원 표지 요구 + 제목의
    # 주인공 판정). 진짜 근거는 대개 제목에 그 이름이 있어 살아남는다.
    "새로운", "테스트", "피아노", "음악", "로드맵", "포인트", "갈무리",
)


# 낱말 하나가 아니라 **구(句) 전체가 일상어**인 이름.
#
# '깊은생각' 은 고유한 브랜드지만 띄어쓰기를 지우면 '깊은 생각을 했다' 의
# '깊은생각' 과 같아진다. 실측: '삼시세끼 꼬마김밥 솔직 후기' 가 본문의
# "깊은 생각 없이" 때문에 깊은생각의 근거였다. 부분 일치('생각')로 잡으면
# 황소까지 걸리지만, 구 전체가 정확히 일치할 때만 보면 잃는 것이 없다 —
# 학원 표지(학원·레테·선생님…)를 하나 더 요구할 뿐이고, 진짜 후기에는
# 그 말이 거의 늘 들어 있다.
GENERIC_PHRASES = ("깊은생각", "한우리")


def is_generic_academy(academy: dict) -> bool:
    """등록명만이 아니라 **브랜드·별칭**까지 본다.

    '한우리독서토론논술교습소' 의 등록명 알맹이는 일상어가 아니지만, 후기는
    '한우리' 라고 부르고 그 말은 샤브샤브 체인이기도 하다(실측: 목동
    현대백화점 맛집 글이 목동 국어 1위의 근거였다). 검색어가 되는 표기
    하나라도 일상어면 학원 표지를 요구한다.
    """
    if is_generic_name(academy.get("name") or ""):
        return True
    phrases = {_norm(g) for g in GENERIC_PHRASES} | {
        _norm(g) for g in GENERIC_NAME_PARTS}
    for label in (academy.get("brand"), *(academy.get("aliases") or [])):
        if label and _norm(label) in phrases:
            return True
    return False


def is_generic_name(name: str) -> bool:
    """학원명이 그 자체로 일상어인가.

    **이름 전체가 일상어일 때만** 해당한다. 부분 일치로 보면
    '생각하는황소' 처럼 고유한 이름까지 걸려 정상 근거가 사라진다.
    실제로 그렇게 짰다가 황소·깊은생각이 함께 잡혔다.
    """
    flat = _norm(name)
    # 지역 접두어와 업종어를 뗀 알맹이로 판단한다.
    core = re.sub(r"^(대치|목동|반포|잠실|서울)", "", flat)
    core = re.sub(r"(학원|교습소|어학원)$", "", core)
    return (core in {_norm(g) for g in GENERIC_NAME_PARTS}
            or core in {_norm(g) for g in GENERIC_PHRASES})


# 이름 끝에 붙는 업종어. 짧은 것부터, 끝에서만 뗀다.
_TRADE_SUFFIX = re.compile(
    r"(학원|교습소|어학원|아카데미|에듀|스쿨|캠퍼스|센터|연구소)+$")


def name_candidates(academy: dict) -> set[str]:
    """이 학원을 가리킬 수 있는 표기들.

    ★ 업종어를 뗀 형태를 반드시 넣는다.
      사람들은 '지엘피아카데미학원' 이라고 쓰지 않고 '지엘피' 라고 쓴다.
      전체 이름만 후보로 두면 본문의 '지엘피' 와 매칭되지 않아, 그 글이
      다른 학원(피아이) 근거로 넘어간다 — 실제로 그렇게 잘못 분류됐다.
    """
    raw = [academy.get("brand"), academy.get("name"), *(academy.get("aliases") or [])]
    out: set[str] = set()
    for n in raw:
        if not n:
            continue
        flat = _norm(n)
        out.add(flat)
        # 지역 접두어를 뗀 형태
        stripped = _norm(re.sub(r"^(대치|목동|반포|잠실|서울)\s*", "", n))
        out.add(stripped)
        # 업종어를 뗀 알맹이. 너무 짧아지면(2자 미만) 오매칭이 나므로 버린다.
        for base in (flat, stripped):
            core = _TRADE_SUFFIX.sub("", base)
            if len(core) >= 3:
                out.add(core)
    return {c for c in out if len(c) >= 2}


# 사람이 시드·위키에 적었지만 **그 자체로 일상어인 별칭.**
#
# 짧은 별칭은 학부모가 실제로 쓰는 줄임말이라 대체로 값지다 —
# '소마'·'폴리'·'필즈'·'청담' 은 이 말로만 걸리는 글이 각각 210·240·80·157건
# 이고 대부분 진짜다. **길이가 기준이 아니다. 일상어인지가 기준이다.**
#
# `정상`(정상어학원): 실측 2026-08-29 에 이런 글들이 근거가 됐다 —
#   '인테리어 금액 상담 어느 정도가 정상인지 …' → 진입난이도 '정원 마감'
#   '하이뮨 프로틴 … 정상적인 면역기능'        → 진입난이도 '대기·웨이팅'
#   '호빵찜기기' · '변기막힘 출장 업체' · '진주과외'
# 다섯 지점(대치·목동·서초·잠실·송파)에 같은 오탐이 함께 붙었다 — 지역을
# 안 밝힌 글은 형제 지점 전부의 근거가 되므로, 별칭 하나가 다섯 학원의
# 점수를 흔든다. 이 말로만 걸린 글이 대치 76·서초 153·잠실 92·송파 122건.
#
# ★ 새 낱말을 넣기 전에 **그 말로만 걸린 글을 눈으로 확인할 것.**
#   '시대'(시대인재 130건)·'강대'(강대학원 206건)도 같은 냄새가 나지만
#   확인 전에는 넣지 않는다. 지우는 쪽도 조용히 틀릴 수 있다.
EVERYDAY_ALIASES = ("정상",)


def weak_candidates(candidates: set[str]) -> set[str]:
    """혼자서는 근거가 못 되는 표기 — 일상어 별칭.

    이름 전체가 일상어인 것(`is_generic_name`)과 **별칭 하나가 일상어인
    것**은 다른 상태인데, 예전에는 앞의 것만 걸렀다. 학원은 멀쩡한 이름
    ('정상어학원')을 갖고 있고 별칭만 일상어일 수 있다.
    """
    bad = {_norm(g) for g in (*GENERIC_NAME_PARTS, *EVERYDAY_ALIASES)}
    return {c for c in candidates if c in bad}


# ── 이름이 나온 자리 ──────────────────────────────────────────────
#
# 두 글자 이름(정상·시대·청담·강대)은 일상어와 구별이 안 된다. '정상인가요'
# 의 '정상', '시대가 바뀌어' 의 '시대', '청담동' 의 '청담' 이 전부 그 학원
# 이었다(실측: 대치정상수학학원의 근거에 '학원 맞춤 시공 청칠판' 광고와
# '5월에는 학생부종합전형을 준비하자' 가 있었다 — 본문 어딘가의 '정상').
# 두 글자는 **곁에 학원 표지가 있을 때만** 이름으로 친다. 세 글자부터는
# 우연히 겹치는 일이 드물어 그대로 인정한다.
_SHORT_MARKERS = ("학원", "어학원", "수학", "영어", "국어", "과학", "논술",
                  "레테", "레벨", "입테", "테스트", "다니", "다녀", "다닌",
                  "등록", "상담", "원장", "쌤", "선생", "캠퍼스", "센터",
                  "지점", "후기", "수업", "숙제", "교습소",
                  # 학원을 고르고 옮기는 말. '청담 vs 폴리 고민' 의 청담.
                  "vs", "고민", "추천", "비교", "옮", "붙었", "합격", "떨어",
                  "대기", "그만", "중에")
_SHORT_WINDOW = 6


def _short_ok(flat: str, i: int, n: int) -> bool:
    after = flat[i + n: i + n + _SHORT_WINDOW]
    before = flat[max(0, i - 4): i]
    if after[:1] in ("반", "관", "점"):          # 정상반 · 청담관 · 폴리점
        return True
    return any(w in after or w in before for w in _SHORT_MARKERS)


def name_spans(flat: str, candidates) -> list[tuple[int, int]]:
    """정규화 문자열에서 이 학원 이름이 나온 (시작, 끝) 자리들.

    **겹치지 않게** 센다. 긴 후보부터 잡아 '김선희꼼꼼국어교습소' 와 그
    알맹이 '김선희꼼꼼국어' 가 같은 자리를 두 번 세지 않는다 — 예전에는
    후보마다 count() 를 더해 한 번 나온 이름이 두 번으로 세어졌고, 그
    부풀린 수가 '내 이름은 한 번뿐' 판정을 통째로 무력화했다(실측: 학원
    이름을 수십 개 늘어놓은 '송파구 교습소 정보 총정리' 가 그렇게 통과했다).
    """
    spans: list[tuple[int, int]] = []
    for c in sorted({_norm(x) for x in candidates if x}, key=len, reverse=True):
        if len(c) < 2:
            continue
        i = flat.find(c)
        while i >= 0:
            j = i + len(c)
            if not any(s < j and i < e for s, e in spans):
                if len(c) >= 3 or _short_ok(flat, i, len(c)):
                    spans.append((i, j))
            i = flat.find(c, i + 1)
    spans.sort()
    return spans


def name_occurrences(blob: str, candidates) -> int:
    return len(name_spans(blob, candidates))


def match_info(mention: dict, candidates) -> dict:
    """이 글이 이 학원을 **어떻게** 부르는가. 화면의 발췌·근거 고르기가 쓴다.

      in_title    제목에 이름이 있다 — 그 글의 주인공이다
      count       겹치지 않게 센 등장 횟수
      first_body  본문에서 처음 나온 자리(정규화 기준). 없으면 -1
      body_len    정규화한 본문 길이
    """
    title = _norm(mention.get("title", ""))
    body = _norm(mention.get("snippet", ""))
    spans = name_spans(title + body, candidates)
    return {
        "count": len(spans),
        "in_title": any(s < len(title) for s, _ in spans),
        "first_body": min((s - len(title) for s, _ in spans if s >= len(title)),
                          default=-1),
        "body_len": len(body),
    }


# ── 남의 학원 이름 ────────────────────────────────────────────────
#
# 등록부 5천 곳의 이름 후보를 그대로 '남의 학원' 으로 쓰면 일반어가 섞인다.
# 실측(2026-09-02, 제목 5만 건): '동영어'(2,711건) · '테스트'(1,815) ·
# '원수학'(855) · '고수학' · '스터디' · '피아노' · '수학교습소' 가 남의
# 학원 이름 행세를 했다 — 'OO동영어학원' 의 알맹이가 '동영어' 로 남은 것,
# '테스트' 라는 이름의 교습소가 실제로 있는 것 등이다. 그 결과 '레벨테스트
# 후기' 라는 제목마다 '테스트 학원' 이 등장한 셈이 되어, 비교글 판정이
# 멀쩡한 후기를 버리고 진짜 비교글은 못 걸렀다.
#
# 이름에서 지역어·과목어·업종어·교육 일반어를 지웠을 때 두 글자 이상이
# 남아야 남의 이름으로 인정한다. '동영어' → '동', '수학교습소' → '' 은
# 못 쓰고 '와이즈만영재교육' → '와이즈만', '청담어학' → '청담' 은 쓴다.
@functools.lru_cache(maxsize=1)
def _rival_generic_words() -> tuple[str, ...]:
    words = {
        "학원", "교습소", "어학원", "아카데미", "에듀", "스쿨", "캠퍼스",
        "센터", "연구소", "교실", "공부방", "테스트", "레벨", "스터디",
        "피아노", "미술", "음악", "영재", "교육", "학습", "클래스", "러닝",
        "리딩", "사고력", "창의", "입시", "보습", "종합", "전문", "과외",
        "독서", "토론", "문해", "글쓰기", "코딩", "로봇", "체육", "태권도",
        "발레", "무용", "보컬", "실용", "키즈", "주니어", "베이직",
        "프리미엄", "초등", "중등", "고등", "유아", "어린이",
        "수학", "영어", "국어", "과학", "논술", "어학", "잉글리시", "잉글리쉬",
    }
    words |= {w for ws in REGION_WORDS.values() for w in ws}
    return tuple(sorted((_norm(w) for w in words if _norm(w)),
                        key=len, reverse=True))


def rival_eligible(cand: str) -> bool:
    """남의 학원 이름 후보로 쓸 수 있는가 — 일반어를 걷어내고도 알맹이가 남아야."""
    if len(cand) < 3:
        return False
    core = cand
    for w in _rival_generic_words():
        core = core.replace(w, "")
    return len(core) >= 2


class RivalIndex:
    """남의 이름 색인. 앞 두 글자로 묶어 두고 글의 자리마다 그 묶음만 본다.

    글마다 만 개 이름을 `in` 으로 훑으면 5만 건 × 1만 = 5억 번이다. 색인은
    글자 수 × 묶음 크기라 수백 배 싸고, 결과는 같다.
    """

    def __init__(self, names) -> None:
        self.names = frozenset(n for n in names if len(n) >= 2)
        self._buckets: dict[str, list[str]] = defaultdict(list)
        for n in self.names:
            self._buckets[n[:2]].append(n)
        for rows in self._buckets.values():
            rows.sort(key=len, reverse=True)

    def find(self, text: str) -> set[str]:
        out: set[str] = set()
        for i in range(max(0, len(text) - 1)):
            for n in self._buckets.get(text[i:i + 2], ()):
                if text.startswith(n, i):
                    out.add(n)
        return out

    def __iter__(self):
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)

    def __contains__(self, item) -> bool:
        return item in self.names

    def __bool__(self) -> bool:
        return bool(self.names)


def _find_rivals(text: str, rivals) -> set[str]:
    if isinstance(rivals, RivalIndex):
        return rivals.find(text)
    return {r for r in rivals if r in text}


# 한 글에 이만큼 많은 학원이 나오면 특정 학원의 후기가 아니라
# 비교글·목록글·광고로 본다.
RIVAL_CROWD = 3

# 블로그 전문처럼 긴 글에서 이름이 **한 번**, 그것도 앞머리를 지나서 나오면
# 그 글의 주제가 아니다. 실측: '[강남 대치] 학원 1만 개, 재건축 10조' 라는
# 부동산 기사가 본문 중간의 '시대인재' 한 마디로 시대인재수학스쿨의 근거가
# 됐다. 짧은 카페 스니펫(120자)에는 걸리지 않는다 — 길이 문턱이 그 뜻이다.
LONG_TEXT = 600
LATE_MENTION = 300

# 학원 목록글의 제목. 카페 스니펫은 120자라 본문의 나열이 안 보이는데,
# 제목이 그 글의 성격을 말한다('송파구 교습소 정보 총정리'). 내 이름이
# 제목에 없고 본문에 한 번뿐일 때만 적용한다 — '대치 영어학원 추천 5곳' 에
# 내 이름이 여러 번이면 그 글은 나를 다루는 글이다.
_LISTING_TITLE = re.compile(
    r"총정리|모음|목록|리스트|전체정리|정리\(|top\d|추천\d+곳|\d+곳비교|\d+곳정리")
# 유선 전화번호가 둘 이상이면 업소 명부다. 광고 판정(PHONE)은 휴대폰만 본다.
_LANDLINE = re.compile(r"0\d{1,2}-?\d{3,4}-?\d{4}")

# 이름이 일상어인 학원의 표지는 **이름 곁**에 있어야 한다. 글 어디든 있으면
# 되게 두면 블로그 본문 2,000자 어딘가의 '지점'·'학원' 한 마디로 샤브샤브
# 맛집 글이 통과한다(실측: 한우리 목동 현대백화점점). 45자로 두었더니 그
# 글의 "…한우리 HANWOORY 목동현대백화점 25년지기 … 근처 학원을 다녔기" 가
# 40자 뒤에서 걸렸다 — 대치·목동 맛집 글은 늘 학원 이야기를 곁들인다.
# 25자면 '한우리 다닌 지 1년' 은 잡고 저 글은 놓친다.
GENERIC_MARKER_WINDOW = 25
# 이름 곁에 이것이 있으면 그 자리는 학원이 아니라 가게다.
_OFF_TOPIC_NEAR = ("맛집", "식당", "메뉴", "샤브", "배달", "주문", "뷔페",
                   "회식", "브런치", "디저트", "카페거리")

# 업종어가 이만큼 나오면 학원 목록글·지역 과외 광고다. 등록부 밖 학원을
# 늘어놓은 글은 남의 이름 색인으로는 못 잡는다 — '보령 동대동 영수과외'
# 글이 '시대인재2관학원' 한 마디로 시대인재수학스쿨의 근거였고, '송파구
# 교습소 정보 총정리' 는 등록부 밖 동네 교습소 수십 곳을 늘어놓았다.
# 보통 후기는 '학원' 을 서너 번 쓴다. 내 이름이 한 번뿐일 때만 적용한다.
TRADE_CROWD = 8
_TRADE_TOKEN = re.compile(r"학원|교습소|어학원|과외")


# 권역을 가리키는 말. 유명 브랜드는 전국에 지점이 있어, 어느 지점
# 이야기인지 가려야 한다. '분당 정상어학원' 후기가 대치 정상어학원의
# 근거가 되면 안 된다.
REGION_WORDS: dict[str, tuple[str, ...]] = {
    # '강남' 은 넣지 않지만 '강남점·강남본점·강남역' 은 지점을 가리키는
    # 말이라 넣는다. 잠실 아트아뜰리에의 근거에 강남점·홍대점 후기가 있었다.
    "daechi": ("대치", "도곡", "개포", "역삼", "강남구", "은마", "선릉", "한티",
               "강남점", "강남본점", "강남역"),
    "mokdong": ("목동", "신정", "양천", "오목교", "등촌"),
    "banpo": ("반포", "잠원", "서초", "고속터미널", "교대", "방배"),
    "jamsil": ("잠실", "신천", "방이", "송파", "가락", "석촌", "위례"),
}

# 우리 권역이 아닌 곳. 이 말이 나오면 그 지점 이야기다.
#
# '강남' 처럼 넓은 말은 넣지 않는다. 대치를 강남이라 부르는 글이 많아
# 오히려 정상 근거를 지운다.
OTHER_REGION_WORDS: tuple[str, ...] = (
    "분당", "평촌", "일산", "동탄", "수지", "판교", "광교", "중계", "노원",
    "부산", "대구", "광주", "대전", "울산", "천안", "세종", "청주", "전주",
    "김포", "용인", "안양", "산본", "화성", "청라", "송도", "인천", "수원",
    "의정부", "구리", "남양주", "고양", "파주", "제주", "창원", "포항",
    "상계", "은평", "마포", "성북", "강서", "구로", "관악", "동작", "성남",
    "군포", "안산", "시흥", "부천", "광명", "하남", "강동", "도봉", "금천",
    "중랑", "광진", "성동", "용산", "노원", "양주", "김해", "원주", "춘천",
    "홍대", "신촌", "건대", "왕십리",
)
# '종로'는 넣지 않는다 — 종로학원은 전국 브랜드라 지역명이 아니다.
# 브랜드에 지역 이름이 박힌 경우가 이렇게 있어, 새 지역어를 넣을 때는
# 그 이름의 학원이 있는지부터 확인해야 한다.


def region_hints(text: str) -> tuple[set[str], bool]:
    """본문이 가리키는 권역. (우리 권역 집합, 타지역 언급 여부)

    둘 다 볼 수 있어야 한다. '분당 정상어학원' 은 타지역이고,
    '대치 정상어학원' 은 대치이고, 그냥 '정상어학원' 은 알 수 없다.
    """
    flat = _norm(text)
    ours = {r for r, words in REGION_WORDS.items()
            if any(_norm(w) in flat for w in words)}
    other = any(_norm(w) in flat for w in OTHER_REGION_WORDS)
    return ours, other


# 글이 어느 과목을 말하고 있는가. 한 학원이 여러 과목을 가르쳐도
# **근거는 과목별로 갈려야 한다** — 수학 후기가 잔뜩 있는 종합학원이
# 과학 랭킹 상위에 오르면 그 순위는 아무것도 뜻하지 않는다.
SUBJECT_WORDS = {
    "math": ("수학", "미적분", "기하", "확률과통계", "확통", "수1", "수2",
             "사고력수학", "연산", "경시", "올림피아드", "매쓰", "math"),
    "english": ("영어", "어학", "리딩", "리스닝", "파닉스", "토플", "토익",
                "텝스", "회화", "원서", "english"),
    "korean": ("국어", "논술", "독서", "문학", "비문학", "언매", "화작",
               "문해", "글쓰기", "독해"),
    "science": ("과학", "물리", "화학", "생명과학", "생물", "지구과학",
                "통합과학", "물화생지"),
}


# 학원 이름에서 이만큼 떨어진 과목어는 그 학원 이야기로 보지 않는다.
SUBJECT_WINDOW = 45


def subjects_in(text: str) -> set[str]:
    """글 어디에든 나온 과목들. 창(窓) 없이 통째로 본다."""
    flat = _norm(text)
    return {sub for sub, words in SUBJECT_WORDS.items()
            if any(_norm(w) in flat for w in words)}


# 학년 구간(학급)을 말하는 낱말. 과목과 같은 방식으로 **이름 근처**만 본다.
#
# 구간을 못 정하는 말('초등')은 어느 쪽으로도 넘기지 않는다 — 저학년과
# 고학년은 학원가에서 사실상 다른 시장이라(저=연산·파닉스, 고=경시·선행)
# 반씩 나눠 갖게 두면 둘 다 틀린다.
BAND_WORDS = {
    "elem_low": ("예비초", "7세", "6세", "5세", "초1", "초2", "초3",
                 "일학년", "이학년", "삼학년", "파닉스", "한글", "유치"),
    "elem_high": ("초4", "초5", "초6", "사학년", "오학년", "육학년",
                  "예비중", "경시", "영재원"),
    "middle": ("중1", "중2", "중3", "중등", "중학교", "중학생", "예비고",
               "고입", "특목고", "영재고", "과학고", "자사고"),
    "high": ("고1", "고2", "고3", "고등", "고등학교", "고등학생", "수능",
             "재수", "n수", "정시", "수시", "내신등급", "모의고사", "의대"),
}


def _nearest(flat: str, spots: list[int], words) -> int | None:
    """이름 자리(spots)에서 가장 가까운 낱말까지의 거리. 없으면 None."""
    best = None
    for w in words:
        n = _norm(w)
        if not n:
            continue
        i = flat.find(n)
        while i >= 0:
            d = min(abs(i - s) for s in spots)
            if d <= SUBJECT_WINDOW and (best is None or d < best):
                best = d
            i = flat.find(n, i + 1)
    return best


def _name_spots(flat: str, names: set[str]) -> list[int]:
    """이름이 나온 자리들. 두 글자 이름의 표지 요구까지 name_spans 와 같다 —
    과목·학급을 재는 창(窓)이 '정상인가요' 의 '정상' 을 중심으로 열리면
    안 된다."""
    return [s for s, _ in name_spans(flat, names)]


def nearest_of(text: str, names: set[str], vocab: dict) -> str | None:
    """**하나만** 고른다 — 학원 이름에 가장 가까운 낱말의 갈래.

    ★ 한 글이 한 학원에 대해 여러 갈래로 세어지면 안 된다. 예전에는
      subjects_near() 가 집합을 돌려줘서 같은 글이 수학 근거이자 과학
      근거였다(실측: 시대인재 379건 중 124건이 중복 계산, 와이즈만은
      225건 중 111건). 표본이 부풀면 그 학원이 실제보다 두껍게 논의된
      것처럼 보이고, 코호트 평균까지 함께 밀린다.

      '가장 가까운 것' 을 쓰는 이유: 글이 그 학원을 말하며 바로 옆에 둔
      낱말이 그 글의 주제다. 멀리 떨어진 낱말은 대개 다른 학원 이야기다.
    """
    flat = _norm(text)
    spots = _name_spots(flat, names)
    if not spots:
        return None
    best, best_d = None, None
    for key, words in vocab.items():
        d = _nearest(flat, spots, words)
        if d is not None and (best_d is None or d < best_d):
            best, best_d = key, d
    return best


def subject_near_one(text: str, names: set[str]) -> str | None:
    """이 글이 이 학원에 대해 말하는 **과목 하나.**"""
    return nearest_of(text, names, SUBJECT_WORDS)


def band_near_one(text: str, names: set[str]) -> str | None:
    """이 글이 이 학원에 대해 말하는 **학년 구간 하나.**

    과목과 달리 이 신호는 원래 없었다. 학원을 학급별로 갈라 줄을 세우려면
    글도 학급별로 갈려야 하는데, 그게 없으면 같은 글이 모든 학급에 복사돼
    과목에서 겪은 중복 계산이 한 층 아래에서 되풀이된다.
    """
    return nearest_of(text, names, BAND_WORDS)


def subjects_near(text: str, names: set[str]) -> set[str]:
    """**학원 이름 근처**의 과목어만.

    글 전체에서 과목어를 찾으면 대치동 잡담이 전부 과학 근거가 된다.
    실측: 시대인재의 '과학' 태그 31건을 열어 보니 '대치동 부동산 가격
    형성요인', '목동 러셀 윈터스쿨 후기' 같은 글이 섞여 있었고, 실제로
    그 학원의 과학을 말한 글은 소수였다.

    branches.py 가 '본문의 지역명은 대개 남의 상호' 라는 것을 배운 것과
    같은 함정이다 — 낱말이 있다는 것과 그 학원 이야기라는 것은 다르다.
    """
    flat = _norm(text)
    spots = _name_spots(flat, names)
    if not spots:
        return set()
    windows = " ".join(
        flat[max(0, i - SUBJECT_WINDOW): i + SUBJECT_WINDOW] for i in spots)
    return {sub for sub, words in SUBJECT_WORDS.items()
            if any(_norm(w) in windows for w in words)}


def is_relevant(mention: dict, candidates: set[str],
                generic: bool = False,
                rivals: set[str] = frozenset()) -> bool:
    """이 글이 정말 그 학원에 대한 글인가.

    네이버 검색은 질의와 느슨하게 관련된 결과를 폭넓게 돌려준다.
    '대치 OO학원 후기'로 검색해도 학원 이름이 한 번도 안 나오는 입시 잡담이
    대량으로 딸려 온다. 실측에서 수집분의 68%가 그랬다.

    학원명이 제목이나 본문에 실제로 등장하지 않으면 그 학원에 대한 근거가
    아니므로 버린다. 가중치를 낮추는 정도로는 부족하다 — 애초에 증거가 아니다.

    [generic] 이면 이름만으로는 부족하다. '책읽기' 처럼 일상어와 겹치는
    이름은 육아 글·독서 후기가 전부 걸리므로, 학원 표지가 함께 있어야
    근거로 인정한다.

    일상어 별칭('정상')은 애초에 [candidates] 에서 빠져서 들어온다 —
    `weak_candidates` 와 build 의 게이트 준비 부분 참고. 여기서 학원 표지를
    요구하는 정도로는 못 거른다: '인테리어 금액 상담 어느 정도가 정상인지'
    가 '상담' 때문에 통과한다(실측).
    """
    title = _norm(mention.get("title", ""))
    body = _norm(mention.get("snippet", ""))
    blob = title + body
    # 이름 자리는 겹치지 않게, 두 글자 이름은 표지가 곁에 있을 때만 센다.
    spans = name_spans(blob, candidates)
    if not spans:
        return False
    if generic and not _marker_near(blob, spans):
        return False

    mine_in_title = any(s < len(title) for s, _ in spans)
    n = len(spans)

    if rivals:
        def strangers(found: set[str]) -> set[str]:
            # 내 이름과 겹치는 후보는 남이 아니다 — '정상' 과 '정상어학원'.
            others = {r for r in found
                      if not any(r in c or c in r for c in candidates)}
            # 한 학원의 여러 표기('청담'·'청담어학원')는 한 학원이다.
            # 긴 표기에 포함되는 짧은 표기는 세지 않는다.
            return {r for r in others
                    if not any(r != o and r in o for o in others)}

        # 1) 제목의 주인공이 남이다.
        #
        #    제목은 글쓴이가 그 글을 무엇이라 부르는지다. 거기에 남의 학원이
        #    있고 내 이름은 없으면, 내가 그 글의 주제일 가능성은 본문에서
        #    내 이름이 **여러 번** 나올 때뿐이다('청담 vs 폴리' 비교글).
        #    한 번 스칠 뿐이면 남의 글이다 — 실측: '캔비어학원 레벨테스트
        #    엄마표영어 초3 테스트 후기' 가 본문의 '폴리어학원' 한 마디로
        #    송파폴리어학원의 근거였다. 이름이 일상어인 학원(책읽기)은
        #    횟수와 무관하게 버린다. 남의 학원이 둘 이상이면 나열이다.
        in_title = strangers(_find_rivals(title, rivals))
        if in_title and not mine_in_title:
            if generic or n <= 1 or len(in_title) >= 2:
                return False

        # 2) 본문에 학원이 잔뜩 나오는데 내 이름은 스치듯 한 번뿐인 경우.
        #    '에이프릴 vs 청담' 처럼 두 곳을 실제로 다루는 글은 남긴다 —
        #    그때는 내 이름도 여러 번 나온다. 제보받은 예: '대치 빅3의
        #    프로그램! 피아이 해빛나인 지엘피 잉글리쉬' — 지엘피 후기인데
        #    피아이 근거로 잡혔다.
        if n <= 1 and len(strangers(_find_rivals(blob, rivals))) >= RIVAL_CROWD:
            return False

    # 3) 긴 글의 스침. 블로그 전문 수천 자 가운데 이름이 한 번, 그것도
    #    앞머리를 지나서 나오면 그 글은 다른 이야기다.
    if len(body) > LONG_TEXT and not mine_in_title and n == 1:
        first = spans[0][0] - len(title)
        if first > LATE_MENTION:
            return False

    # 4) 학원 목록글·업소 명부. 내 이름이 한 번뿐이고 제목에도 없을 때:
    #    업종어가 잔뜩이거나, 제목이 '총정리' 류이거나, 유선 번호가 둘 이상.
    if n <= 1 and not mine_in_title:
        if len(_TRADE_TOKEN.findall(blob)) >= TRADE_CROWD:
            return False
        if _LISTING_TITLE.search(title):
            return False
        if len(_LANDLINE.findall(mention.get("snippet") or "")) >= 2:
            return False
    return True


def _marker_near(flat: str, spans: list[tuple[int, int]],
                 window: int = GENERIC_MARKER_WINDOW) -> bool:
    """이름 자리 곁(±window)에 학원 표지가 있는가.

    '후기'·'고민'·'추천' 같은 말은 여기서 표지가 아니다 — 어느 블로그 글에나
    있다. '삼시세끼 꼬마김밥 솔직 후기' 의 '후기' 가 "깊은 생각 없이" 옆에
    있었다. 다니는 말과 학원살이 말만 표지로 친다.
    """
    markers = {_norm(k) for k in _ACADEMY_MARKERS} | {
        _norm(k) for k in ("다니", "다녀", "다닌", "수업", "쌤", "입테", "레벨")}
    for s, e in spans:
        near = flat[max(0, s - window): e + window]
        if any(off in near for off in _OFF_TOPIC_NEAR):
            continue
        if any(k and k in near for k in markers):
            return True
    return False


def analyze(mention: dict, academy_name: str = "",
            names: set[str] | None = None) -> dict:
    """언급 한 건을 분석해 필드를 채워 돌려준다.

    [academy_name] 은 등급반 추출에서 학원 이름을 지우는 데 쓴다.
    '최상위수학교습소' 같은 이름이 그대로 '최상위반' 신호가 되면
    학원 이름이 곧 난이도가 되어 버린다.
    """
    text = mention.get("snippet", "")
    title = mention.get("title", "")
    blob = f"{title} {text}"

    targets = names or {academy_name}
    subject = subject_near_one(blob, targets)

    sentiment, aspects = score_sentiment(blob)
    spam = score_spam(text, title)
    credibility = score_credibility(text, title, mention.get("source", ""))

    # 스팸 의심이 높을수록 신뢰도를 깎는다. 임계값 이상이면 아예 배제.
    credibility *= max(0.0, 1.0 - spam)

    mention = dict(mention)
    mention.update({
        "sentiment": sentiment,
        "aspects": aspects,
        "spam_score": spam,
        "credibility": round(credibility, 3),
        "is_excluded": spam >= SPAM_EXCLUDE_THRESHOLD,
        # 이 글이 어느 기둥까지 근거가 될 수 있는가. 배제가 아니라 등급이다.
        "substance": score_substance(text, title),
        "selectivity": selectivity_signals(blob),
        "class_tier_signals": class_tier_signals(blob, exclude=academy_name),
        # 이 글이 **이 학원에 대해** 말하는 과목·학급. 이름 근처만 본다.
        #
        # ★ 각각 **하나씩만** 정한다. 집합으로 두면 같은 글이 수학 근거이자
        #   과학 근거가 되어 표본이 부풀고(실측 시대인재 124건 중복),
        #   코호트 평균까지 함께 밀린다. 한 글은 한 학원에 대해 한 가지를
        #   말한다고 본다 — 이름에 가장 가까운 낱말이 그것이다.
        "subject": subject,
        # 하위 호환: 0개 또는 1개짜리 목록. 여러 개가 될 수 없다.
        "subjects": [subject] if subject else [],
        "band": band_near_one(blob, targets),
    })
    return mention


def flag_repeat_authors(mentions: list[dict], threshold: int = 4) -> list[dict]:
    """같은 작성자가 한 학원에 반복 등장하면 바이럴로 보고 감쇠한다."""
    counts: dict[tuple, int] = Counter(
        (m.get("academy_key"), m.get("author_hash"))
        for m in mentions if m.get("author_hash")
    )
    out = []
    for m in mentions:
        key = (m.get("academy_key"), m.get("author_hash"))
        n = counts.get(key, 0)
        if n >= threshold:
            decay = threshold / n
            m = dict(m)
            m["credibility"] = round(m.get("credibility", 0.5) * decay, 3)
            m["spam_score"] = round(min(1.0, m.get("spam_score", 0.0) + 0.2), 3)
            m["repeat_author_count"] = n
        out.append(m)
    return out


# 같은 작성자가 며칠 안에 한 학원 글을 이만큼 쓰면 바이럴 배치로 본다.
#
# ★ flag_repeat_authors 에는 시간 창이 없다. 3년에 걸친 4건과 사흘 만의
#   4건이 같은 취급이었다 — 앞은 단골 학부모이고 뒤는 캠페인이다.
#   문헌(opinion spam detection)에서 burst 가 가장 값싼 행위 신호다.
BURST_DAYS = 7
BURST_MIN = 3


def flag_author_bursts(mentions: list[dict]) -> tuple[list[dict], int]:
    """짧은 기간에 몰린 같은 작성자의 글을 배제한다.

    ★ 발견일(date_source='discovery')로 채워진 날짜는 쓰지 않는다.
      그것은 '우리가 언제 봤나' 이지 '언제 썼나' 가 아니고, 한 회차에
      발견한 글 수천 건이 **같은 날짜**를 갖는다. 처음에 이걸 빼먹었더니
      3,256건이 버스트로 잡혔다 — 캠페인이 아니라 우리 수집 일정이었다.
    """
    by_author: dict[tuple, list[dict]] = defaultdict(list)
    for m in mentions:
        if (m.get("author_hash") and m.get("posted_at")
                and m.get("date_source") != "discovery"):
            by_author[(m.get("academy_key"), m["author_hash"])].append(m)

    burst: set[int] = set()
    for rows in by_author.values():
        dated = sorted(
            ((d, m) for m in rows if (d := _as_day(m.get("posted_at")))),
            key=lambda x: x[0])
        for i, (day, _) in enumerate(dated):
            window = [r for r in dated[i:] if (r[0] - day).days <= BURST_DAYS]
            if len(window) >= BURST_MIN:
                burst.update(id(m) for _, m in window)

    hit = 0
    for m in mentions:
        if id(m) in burst and not m.get("is_excluded"):
            m["is_excluded"] = True
            m["exclude_reason"] = "author_burst"
            hit += 1
    return mentions, hit


def _as_day(value):
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None


# 두 글이 이만큼 닮으면 같은 원고를 옮긴 것으로 본다.
# 문헌 기준값(2-gram Jaccard 0.9)을 그대로 쓴다.
DUPLICATE_JACCARD = 0.9
# 이보다 짧은 글은 견주지 않는다. 짧으면 우연히 닮는다.
DUPLICATE_MIN_LEN = 40


def _bigrams(text: str) -> set[str]:
    flat = _NORM.sub("", text or "")
    return {flat[i:i + 2] for i in range(len(flat) - 1)}


def flag_near_duplicates(mentions: list[dict]) -> tuple[list[dict], int]:
    """같은 문구를 여러 곳에 옮긴 바이럴 배치를 걸러낸다.

    개별 글은 스팸 점수가 낮아 전부 통과한다 — 홍보 문구가 없는 '후기체'
    원고를 여러 카페에 뿌리기 때문이다. **묶음으로 봐야** 잡힌다.
    가장 오래된 한 건만 남긴다. 원본까지 버리면 근거가 통째로 사라진다.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        if m.get("is_excluded"):
            continue
        text = m.get("snippet") or ""
        if len(_NORM.sub("", text)) >= DUPLICATE_MIN_LEN:
            # 학원별로만 견준다. 전수 비교는 O(n²) 라 감당이 안 되고,
            # 다른 학원의 닮은 글은 애초에 서로의 근거가 아니다.
            groups[m.get("academy_key")].append(m)

    hit = 0
    for rows in groups.values():
        grams = [(m, _bigrams(m.get("snippet") or "")) for m in rows]
        grams.sort(key=lambda x: str(x[0].get("posted_at") or "9999"))
        kept: list[tuple[dict, set]] = []
        for m, g in grams:
            twin = next((k for _, k in kept
                         if len(g & k) / max(1, len(g | k)) >= DUPLICATE_JACCARD),
                        None)
            if twin is not None:
                m["is_excluded"] = True
                m["exclude_reason"] = "near_duplicate"
                hit += 1
            else:
                kept.append((m, g))
    return mentions, hit
