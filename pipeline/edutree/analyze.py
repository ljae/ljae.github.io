"""수집된 언급의 감성 · 신뢰도 · 스팸 분석.

사전 기반이다. 학원 도메인 한국어는 일반 감성사전이 잘 못 다룬다
("빡세다"는 부정어처럼 보이지만 이 바닥에선 칭찬에 가깝다).
그래서 도메인 사전을 직접 들고 간다.

★ 업그레이드 경로: 이 모듈의 score_sentiment() 만 KoBERT/LLM 분류기로
  교체하면 나머지 파이프라인은 그대로 동작한다. 인터페이스를 고정해 두었다.
"""
from __future__ import annotations

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
CONTACT = re.compile(r"01[016-9][-\s]?\d{3,4}[-\s]?\d{4}|https?://|카톡\s*:|kakao")
EMOJI_RUN = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]{3,}")

# ── 진입난이도 신호 ────────────────────────────────────────────────
SELECTIVITY_HARD = ("떨어졌", "탈락", "재수", "어렵", "난이도", "빡세", "합격률",
                    "커트라인", "컷", "경쟁", "몇번째", "재응시")
SELECTIVITY_WAIT = ("대기", "웨이팅", "마감", "자리없", "티오", "T.O", "빈자리",
                    "등록전쟁", "오픈런", "결원")


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
    if CONTACT.search(blob):
        score += 0.35
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


def selectivity_signals(text: str) -> dict[str, int]:
    flat = (text or "").replace(" ", "")
    return {
        "hard": sum(1 for k in SELECTIVITY_HARD if k in flat),
        "wait": sum(1 for k in SELECTIVITY_WAIT if k in flat),
    }


def analyze(mention: dict) -> dict:
    """언급 한 건을 분석해 필드를 채워 돌려준다."""
    text = mention.get("snippet", "")
    title = mention.get("title", "")
    blob = f"{title} {text}"

    sentiment, aspects = score_sentiment(blob)
    spam = score_spam(text, title)
    credibility = score_credibility(text, title, mention.get("source", ""))

    # 스팸 의심이 높을수록 신뢰도를 깎는다. 0.6 이상이면 아예 배제.
    credibility *= max(0.0, 1.0 - spam)

    mention = dict(mention)
    mention.update({
        "sentiment": sentiment,
        "aspects": aspects,
        "spam_score": spam,
        "credibility": round(credibility, 3),
        "is_excluded": spam >= 0.6,
        "selectivity": selectivity_signals(blob),
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
