"""트리스코어 (TreeScore) 계산.

    TreeScore = 0.35·평판 + 0.35·진입난이도 + 0.15·화제성 + 0.15·투명성
    (가중치의 출처는 언제나 config.WEIGHTS 다 — 여기 숫자는 설명일 뿐)

설계 원칙
  1. 각 기둥은 0–100 으로 독립 계산되고, breakdown 에 계산 근거를 남긴다.
     서비스가 산식을 전면 공개하기로 했으므로 근거를 못 만들면 점수도 못 낸다.
  2. 표본이 적은 학원은 코호트 평균으로 끌어당긴다(베이지안 축소).
     후기 3건짜리 학원이 1위로 튀는 것을 막는 핵심 장치다.
  3. 표본 10건 미만은 순위에서 아예 제외한다. 소수 악평으로 하위권을
     만들어 두면 그게 곧 명예훼손 리스크다.
  4. **근거가 없는 기둥은 채우지 않고 뺀다.** 없는 값을 코호트 평균으로
     채우면 '모른다' 가 '보통' 이 되고, 0 으로 치면 '쉽다' 가 된다.
     남은 기둥으로 가중치를 다시 나눈다(compute 참고).

기둥마다 문턱이 다르다 — 같은 글이 화제성에는 들어가고 평판에는 안
들어가는 것이 정상이다(analyze.score_substance).

    화제성      정보량 0 이상   회자되는 것 자체가 신호다
    평판        정보량 1 이상   의견 없는 글은 감성이 아니다
    진입난이도   사건이 확인된 글만
    투명성      후기를 보지 않는다 (NEIS 공시)
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone

from . import analyze, config

TODAY = date.today()


# ── 유틸 ───────────────────────────────────────────────────────────
def _to_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def recency_weight(posted_at) -> float:
    """반감기 180일 지수 감쇠.

    날짜를 모르는 글(카페글 API는 날짜를 안 준다)은 0.6 — 6개월쯤 된 글과
    같은 취급. 모르는 것을 최신으로도, 오래된 것으로도 취급하지 않는다.
    """
    d = _to_date(posted_at)
    if d is None:
        return 0.6
    days = max(0, (TODAY - d).days)
    return math.exp(-days / config.RECENCY_HALFLIFE_DAYS)


# ── 기둥 1. 평판 (35%) ─────────────────────────────────────────────
# 평판에 쓰려면 의견이 있어야 한다(analyze.score_substance ≥ 1).
#
# ★ 화제성에는 이 문턱을 걸지 않는다. 화제성은 '얼마나 회자되는가' 라서
#   한 줄짜리 '거기 좋대요' 도 회자의 증거로는 유효하다. 같은 글을 두
#   기둥이 다르게 쓰는 것이 정상이다 — 층을 섞지 않는다.
REPUTATION_SUBSTANCE_FLOOR = 1


def reputation(mentions: list[dict], cohort_mean: float,
               cohort_sd: float = 0.12) -> tuple[float, dict]:
    valid = [m for m in mentions
             if not m.get("is_excluded")
             and m.get("substance", 1) >= REPUTATION_SUBSTANCE_FLOOR]
    if not valid:
        return 50.0, {
            "표본": 0, "설명": "유효 표본 없음 — 코호트 평균으로 대체",
        }

    num = den = 0.0
    for m in valid:
        w = float(m.get("credibility", 0.5)) * recency_weight(m.get("posted_at"))
        num += w * float(m.get("sentiment", 0.0))
        den += w

    # 긍정률 — 점수 하나만으로는 무엇을 뜻하는지 읽히지 않는다.
    # 트리스코어가 어디서 왔는지 가늠하게 해 주는 값을 함께 둔다.
    #
    # 분모는 **의견을 낸 후기**만 센다. 중립까지 넣으면 어디나 25~40%로
    # 몰려 변별이 안 되고, 실제로는 좋게 말한 사람이 많은 곳도 '29%' 처럼
    # 나빠 보인다. 국내 커뮤니티 글은 중립 서술이 많아 특히 그렇다.
    pos = neg = 0.0
    for m in valid:
        w = float(m.get("credibility", 0.5)) * recency_weight(m.get("posted_at"))
        sent = float(m.get("sentiment", 0.0))
        if sent > 0.05:
            pos += w
        elif sent < -0.05:
            neg += w
    opinionated = pos + neg
    recommend = round(pos / opinionated * 100, 1) if opinionated > 0 else None

    m0 = config.REPUTATION_PRIOR_COUNT
    shrunk = (num + m0 * cohort_mean) / (den + m0)      # 베이지안 축소

    # 코호트 대비 z 점수로 옮긴다. [-1,1] 을 [0,100] 에 선형 매핑하면
    # 실제 감성이 0.00~0.78 구간에만 살아서 점수가 53~65 로 눌린다.
    # 가중치가 0.35 인데 순위를 거의 못 가르는 상태였다 — 가중치가
    # 뜻하는 바와 실제 영향이 어긋나면 산식을 공개하는 의미가 없다.
    #
    # 화제성이 이미 같은 방식(코호트 z점수)을 쓴다. 기둥끼리 저울을
    # 맞춰야 가중치가 곧 영향력이 된다.
    sd = cohort_sd or 0.12
    z = (shrunk - cohort_mean) / sd
    score = _clamp(50 + 15 * z)

    excluded = len(mentions) - len(valid)
    return round(score, 1), {
        "표본": len(valid),
        "긍정률": recommend,
        "의견_표명_가중치": round(opinionated, 2),
        "제외된_스팸": excluded,
        "가중_감성합": round(num, 2),
        "가중치_총합": round(den, 2),
        "코호트_평균감성": round(cohort_mean, 3),
        "코호트_감성표준편차": round(cohort_sd, 3),
        "축소_사전표본": m0,
        "설명": f"신뢰도·최신성 가중 감성 {round(num/den, 3) if den else 0} 를 "
                f"코호트 평균 {round(cohort_mean, 3)} 쪽으로 {m0}건만큼 축소",
    }


# ── 기둥 2. 화제성 (20%) ───────────────────────────────────────────
def momentum(mentions: list[dict], cohort_volumes: list[float]) -> tuple[float, dict, str]:
    valid = [m for m in mentions if not m.get("is_excluded")]
    recent = [m for m in valid
              if (d := _to_date(m.get("posted_at"))) and (TODAY - d).days <= 90]
    # 90일 창은 경계가 딱딱하다 — 91일 된 글이 0이 되고 89일 된 글이 1이 된다.
    # 최신성 가중 합을 함께 써서 경계를 부드럽게 한다. 날짜 없는 글은
    # 여전히 0.6 으로 들어가므로 전체가 0 이 되지는 않는다.
    weighted = sum(recency_weight(m.get("posted_at")) for m in valid)
    volume = math.log1p(max(len(recent), weighted))

    if len(cohort_volumes) >= 3:
        mu = statistics.mean(cohort_volumes)
        sd = statistics.pstdev(cohort_volumes) or 1.0
        z = (volume - mu) / sd
    else:
        z = 0.0
    volume_score = _clamp(50 + z * 18)

    slope, direction = _trend(valid)
    slope_score = _clamp(50 + slope * 12)

    score = 0.6 * volume_score + 0.4 * slope_score
    return round(score, 1), {
        "최근90일_언급": len(recent),
        "최신성_가중합": round(weighted, 1),
        "전체_유효언급": len(valid),
        "코호트_z점수": round(z, 2),
        "월별_추세기울기": round(slope, 3),
        "설명": "코호트 내 언급량 z점수 60% + 12개월 월별 추세 40%",
    }, direction


def _trend(mentions: list[dict]) -> tuple[float, str]:
    """월별 언급 수의 단순 선형 기울기와 방향 라벨."""
    buckets: dict[str, int] = defaultdict(int)
    for m in mentions:
        d = _to_date(m.get("posted_at"))
        if d and (TODAY - d).days <= 365:
            buckets[f"{d.year}-{d.month:02d}"] += 1
    if len(buckets) < 3:
        return 0.0, "stable"

    ys = [buckets[k] for k in sorted(buckets)]
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom

    direction = "rising" if slope > 0.35 else "falling" if slope < -0.35 else "stable"
    return slope, direction


# ── 기둥 3. 투명성 (25%) ───────────────────────────────────────────
# 교습비 공개(25점)를 뺐다. NEIS 가 교습시간을 주지 않아 금액만으로는
# 비교가 성립하지 않고, 비교할 수 없는 값을 공개했다고 점수를 주면
# 그 점수가 무엇을 뜻하는지 설명할 수 없다. 빠진 배점은 나머지에 나눈다.
TRANSPARENCY_RUBRIC = (
    ("등록상태 정상", 30),
    ("정원 공시", 20),
    ("교습과정 상세", 25),
    ("운영 지속기간", 25),
)


def transparency(academy: dict) -> tuple[float, dict]:
    """NEIS 공시 기반 규칙 채점. 100% 검증 가능한 유일한 기둥."""
    earned: dict[str, int] = {}

    status = (academy.get("reg_stttus_nm") or "").strip()
    earned["등록상태 정상"] = 30 if status in ("정상", "운영중", "개원") else (
        12 if status else 0)

    earned["정원 공시"] = 20 if academy.get("tofor_smtot") else 0
    earned["교습과정 상세"] = 25 if (academy.get("le_crse_list_nm")
                                 or academy.get("le_ord_nm")) else 0

    estbl = _to_date(academy.get("estbl_ymd"))
    if estbl:
        years = (TODAY - estbl).days / 365.25
        earned["운영 지속기간"] = round(_clamp(math.log1p(max(0, years)) / math.log(21) * 25, 0, 25))
    else:
        earned["운영 지속기간"] = 0

    total = sum(earned.values())
    return float(total), {
        "항목별": earned,
        "만점": {k: v for k, v in TRANSPARENCY_RUBRIC},
        "검증여부": bool(academy.get("is_verified")),
        "설명": "NEIS 학원교습소정보 공시 항목 기반 규칙 채점",
    }


# ── 기둥 4. 진입난이도 (20%) ───────────────────────────────────────
#
# 낱말 세기에서 **사건 판정**으로 바꿨다(2026-08-28).
#
# 옛 식을 캐시로 재 보니(언급 30건·정원 200) 이렇게 나왔다:
#
#   레테 얘기가 아예 없는 학원         24.7   '모른다' 가 '쉽다' 로
#   '난이도 높아 떨어졌어요'(경험담)    74.1   기준점
#   '레테 어렵지 않았어요, 대기 없이'   70.6   부정문이 그대로 난이도
#   '레테 어렵다던데 대기 걸리나요?'    74.1   질문글이 경험담과 동일
#
# 원인이 셋이었다. ① selectivity_signals 가 창(窓) 없이 글 전체를 봤다 —
# 과목·학급은 이름 근처 45자만 보는데 진입난이도만 그 규칙 밖에 있었다.
# ② 감성에는 NEGATORS 가 걸리는데 진입난이도에는 안 걸렸다. ③ 전문·의문을
# 사실과 구분하지 않았다. 게다가 배점 30%인 '정원 대비 수요' 는 후기
# 내용이 아니라 언급 수 ÷ 정원이라 화제성과 같은 재료를 두 번 썼다.
#
# 사건 판정은 claims._extract_events 가 한다. 여기서는 세기만 한다.

# ★ 강도는 **종류별로** 포화시킨다. 같은 종류를 몇 번 말했는지가 아니라
#   어떤 종류가 확인됐는지가 진입난이도다.
#
#   처음에는 사건을 전부 더했다. 그랬더니 '레벨테스트 있음'(무게 0.3)이
#   양으로 쌓여 소마·개념폴리아가 96~97점을 받았다 — 무게를 0.3 으로 둔
#   뜻('레테가 있다는 것만으로는 난이도가 아니다')이 통째로 상쇄됐다.
#   실측 1,555건 중 대부분이 이 종류였다.
#
#   종류마다 서로 다른 작성자 수로 포화시키면(둘이면 거의 최대) 무게가
#   그대로 살아난다. 100점은 다섯 종류가 모두 확인된 곳이다.
EVENT_AUTHOR_SCALE = 2.0

# 표본 수로 나누지 않는다. 진입난이도는 '사건이 일어났는가' 이지 '글 중
# 몇 %가 그 얘기를 하는가' 가 아니다. 나누면 후기가 많은 큰 학원이
# 자동으로 쉬운 곳이 된다.

# 서로 다른 작성자 수 → 확인율. 한 사람 말은 아직 한 사람 말이다.
CORROBORATION = ((5, 1.00), (3, 0.70), (2, 0.50), (1, 0.30))


def _corroboration(authors: int) -> float:
    for need, value in CORROBORATION:
        if authors >= need:
            return value
    return 0.0


def selectivity(mentions: list[dict], academy: dict,
                cohort_ratio_mean: float | None = None):
    """(점수 또는 None, 근거). 사건이 없으면 **점수를 내지 않는다.**

    ★ 표본 0 을 코호트 평균(50)으로 채우지 않는다.
      '아직 안 봤다' 와 '보고서 보통이었다' 는 다른 상태다. 이 원칙은
      이미 평판·표본 0 에 적용돼 있었는데 진입난이도만 빠져 있었다.
      예체능에서 진입난이도를 뺄 때 적어 둔 말이 그대로 해당한다 —
      **없는 것을 0점으로 치면 그게 곧 왜곡이다.**

    ★ 등급반별 점수는 여전히 만들지 않는다.
      반 이름과 난이도 단어가 함께 붙은 언급이 400곳 전체에서 186건뿐이고
      결과가 뒤집혔다(기초반이 최상위반보다 어렵게). 주장 단위로 바꿔도
      표본이 늘지는 않는다.
    """
    valid = [m for m in mentions if not m.get("is_excluded")]

    counts: dict[str, int] = defaultdict(int)
    # 종류 → {작성자: 그 작성자의 가장 최신 글 가중치}
    by_kind: dict[str, dict] = defaultdict(dict)
    authors: set = set()
    newest = None
    for m in valid:
        events = m.get("sel_events") or []
        if not events:
            continue
        rw = recency_weight(m.get("posted_at"))
        who = m.get("author_hash") or m.get("url_hash")
        for kind in events:
            counts[kind] += 1
            by_kind[kind][who] = max(by_kind[kind].get(who, 0.0), rw)
        authors.add(who)
        d = _to_date(m.get("posted_at"))
        if d and (newest is None or d > newest):
            newest = d

    if not counts:
        return None, {
            "사건": {},
            "설명": "진입 관련 후기가 없어 점수를 내지 않습니다.",
            "주의": "'쉽다' 가 아니라 '아직 모른다' 는 뜻입니다.",
        }

    strength = sum(
        analyze_weight(kind) * math.tanh(sum(ws.values()) / EVENT_AUTHOR_SCALE)
        for kind, ws in by_kind.items())
    ceiling = sum(w for _k, w, _t, _c in _sel_events()) or 1.0
    strength_score = _clamp(strength / ceiling * 100)
    corr = _corroboration(len(authors))
    recency = _clamp(recency_weight(newest) * 100) if newest else 60.0

    score = 0.55 * strength_score + 0.25 * corr * 100 + 0.20 * recency
    return round(score, 1), {
        "사건": {SEL_LABEL_KO.get(k, k): v for k, v in sorted(counts.items())},
        "사건_강도": round(strength, 2),
        "서로_다른_작성자": len(authors),
        "확인율": corr,
        "최신_사건": newest.isoformat() if newest else None,
        "정원": academy.get("tofor_smtot") or None,
        "설명": "사건 강도 55% + 확인율(서로 다른 작성자) 25% + 최신성 20%. "
                "레벨테스트 탈락 1.0 · 대기 0.8 · 마감 0.6 · 어렵게 통과 0.5 · "
                "레벨테스트 있음 0.3 으로 무게가 다릅니다.",
        "주의": "커뮤니티 후기에서 확인된 사건입니다. 공식 경쟁률이 아닙니다.",
    }


def analyze_weight(kind: str) -> float:
    from . import claims
    return claims.SEL_WEIGHT.get(kind, 0.0)


def _sel_events():
    from . import claims
    return claims.SEL_EVENTS


SEL_LABEL_KO = {
    "sel.test_failed": "레벨테스트 탈락", "sel.waitlist": "대기·웨이팅",
    "sel.full": "정원 마감", "sel.test_hard": "어렵게 통과",
    "sel.test_exists": "레벨테스트 있음",
}

# 화면에 낼 등급. 0–100 숫자보다 등급이 정직하다 — 표본 3건짜리
# '난이도 74점' 은 정밀해 보이지만 그 정밀도가 근거에 없다.
def selectivity_tier(breakdown: dict) -> str | None:
    events = breakdown.get("사건") or {}
    if not events:
        return None
    authors = breakdown.get("서로_다른_작성자", 0)
    if events.get("레벨테스트 탈락", 0) >= 3 and authors >= 3:
        return "high"
    if authors >= 2 and (events.get("대기·웨이팅", 0)
                         + events.get("정원 마감", 0)) >= 2:
        return "medium"
    return "mentioned"


# ── 종합 ───────────────────────────────────────────────────────────
def confidence_label(sample: int) -> str:
    if sample >= config.CONFIDENCE_HIGH:
        return "high"
    if sample >= config.MIN_SAMPLE_FOR_RANK:
        return "medium"
    return "low"


def primary_subject(academy: dict) -> str:
    """이 학원을 어느 과목으로 볼 것인가. 코호트와 산식이 이걸 따른다."""
    subjects = academy.get("subjects") or [config.UNRANKED_SUBJECT]
    for s in subjects:
        if s in config.ACADEMIC_SUBJECTS:
            return s
    if "arts" in subjects:
        return "arts"
    if "etc" in subjects:
        return "etc"
    # 종합·보습처럼 과목을 정할 수 없는 곳. 순위를 매기지 않는다.
    return config.UNRANKED_SUBJECT


def ranked_subjects(academy: dict) -> list[str]:
    """이 학원이 랭킹에 오를 수 있는 과목들.

    한 학원이 여러 과목을 가르치는 것은 정상이다. 하지만 **랭킹은 과목별
    로 따로** 매겨야 한다 — 수학 후기가 496건인 종합학원이 그 점수를
    그대로 들고 과학 랭킹 3위에 오르면, 그 순위는 '이 학원의 과학이
    좋다'가 아니라 '이 학원이 유명하다'를 뜻하게 된다.
    """
    subs = [s for s in (academy.get("subjects") or [])
            if s in config.ACADEMIC_SUBJECTS or s in ("arts", "etc")]
    return subs or []


def subject_mentions(academy: dict, mentions: list[dict],
                     subject: str) -> list[dict]:
    """그 과목의 근거로 쓸 수 있는 글만.

    - 과목이 하나인 학원: 모든 글이 그 과목 이야기다.
    - 여러 과목인 학원: **글이 그 과목을 명시해야** 근거로 친다.
      과목을 밝히지 않은 글은 대표 과목에만 넣는다 — '시대인재수학스쿨
      좋아요' 는 수학 이야기로 보는 것이 가장 그럴듯하고, 과학 근거로
      치는 것은 근거 없는 확대다.
    """
    subs = ranked_subjects(academy)
    if len(subs) <= 1:
        return mentions
    primary = primary_subject(academy)
    out = []
    for m in mentions:
        tagged = set(m.get("subjects") or [])
        if subject in tagged:
            out.append(m)
        elif not (tagged & set(subs)) and subject == primary:
            out.append(m)          # 과목 불명 → 대표 과목에만
    return out


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    """남은 기둥으로 가중치를 다시 나눈다. 합은 **정확히 1** 이어야 한다.

    화면과 산식 페이지가 이 값을 그대로 찍는다. 반올림해서 0.5385 +
    0.2308 + 0.2308 = 1.0001 이 나오면 공개한 산식이 틀린 것이 된다.
    가장 무거운 기둥이 나머지를 흡수한다.
    """
    scale = sum(weights.values()) or 1.0
    out = {k: round(v / scale, 4) for k, v in weights.items()}
    top = max(out, key=out.get)
    out[top] = round(out[top] + (1.0 - sum(out.values())), 4)
    return out


def compute(academy: dict, mentions: list[dict], cohort: dict,
            subject: str | None = None) -> dict:
    rep, rep_bd = reputation(mentions, cohort["mean_sentiment"],
                             cohort.get("sd_sentiment") or 0.12)
    mom, mom_bd, direction = momentum(mentions, cohort["volumes"])

    # 예체능·기타는 만족도와 화제성만 본다.
    #
    # 투명성은 공시가 '미술' 한 줄인 경우가 많아 상세도를 재면 실제 차이가
    # 아니라 공시 습관을 재게 된다. 진입난이도는 레벨테스트·대기 개념이
    # 없는 곳이 대부분이라 신호가 안 잡히고, 없는 것을 0점으로 치면
    # 그게 곧 왜곡이다.
    subject = subject or primary_subject(academy)
    academic = subject in config.ACADEMIC_SUBJECTS
    rankable = subject != config.UNRANKED_SUBJECT

    if academic:
        tra, tra_bd = transparency(academy)
        sel, sel_bd = selectivity(mentions, academy,
                                  cohort["mention_capacity_ratio"])
        w = dict(config.WEIGHTS)
        if sel is None:
            # 진입 관련 후기가 없는 학원. 없는 기둥을 코호트 평균으로
            # 채우면 '모른다' 가 '보통' 이 되고, 0 으로 치면 '쉽다' 가
            # 된다. 대신 **남은 기둥으로 다시 나눈다** — 그러면 총점이
            # '우리가 아는 것만으로 매긴 점수' 라고 말할 수 있다.
            w.pop("selectivity")
            w = _renormalize(w)
            total = (w["reputation"] * rep + w["momentum"] * mom
                     + w["transparency"] * tra)
        else:
            total = (w["reputation"] * rep + w["momentum"] * mom
                     + w["transparency"] * tra + w["selectivity"] * sel)
    else:
        tra, sel = None, None
        tra_bd = {"설명": "예체능·기타는 투명성을 채점하지 않습니다."}
        sel_bd = {"설명": "예체능·기타는 진입난이도를 채점하지 않습니다."}
        w = config.NON_ACADEMIC_WEIGHTS
        total = w["reputation"] * rep + w["momentum"] * mom

    sample = len([m for m in mentions if not m.get("is_excluded")])
    return {
        "academy_key": academy["id"],
        "subject": subject,
        "subject_group": "academic" if academic else "non_academic",
        "total": round(total, 1),
        "reputation": rep,
        "momentum": mom,
        "transparency": tra,
        "selectivity": sel,
        "sample_size": sample,
        "confidence": confidence_label(sample),
        # 과목을 정할 수 없는 곳은 순위에서 뺀다. 어느 과목으로 견줄지
        # 정할 수 없으면 등수도 매길 수 없다.
        "is_ranked": rankable and sample >= config.MIN_SAMPLE_FOR_RANK,
        "momentum_direction": direction,
        # 숫자 대신 화면에 낼 등급. 없으면 '진입 관련 후기 없음'.
        "selectivity_tier": (selectivity_tier(sel_bd) if academic else None),
        "breakdown": {
            "weights": w,
            "reputation": rep_bd,
            "momentum": mom_bd,
            "transparency": tra_bd,
            "selectivity": sel_bd,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_all(academy: dict, mentions: list[dict],
                cohorts: dict) -> tuple[dict, dict]:
    """(대표 점수, {과목: 점수}).

    대표 점수는 학원 카드·상세의 기본 얼굴이고, 과목별 점수가 각 과목
    랭킹의 근거다. 같은 학원이라도 과목마다 표본과 등수가 다르다.
    """
    subs = ranked_subjects(academy)
    primary = primary_subject(academy)
    by_subject: dict[str, dict] = {}
    for sub in subs:
        ms = subject_mentions(academy, mentions, sub)
        by_subject[sub] = compute(academy, ms, cohort_for(academy, cohorts, sub),
                                  subject=sub)
    main = by_subject.get(primary)
    if main is None:
        # 과목을 정할 수 없는 곳(종합·보습). 순위는 안 매기지만 상세는 보인다.
        main = compute(academy, mentions, cohort_for(academy, cohorts, primary),
                       subject=primary)
    return main, by_subject


def build_cohorts(academies: list[dict], mentions_by_key: dict) -> dict:
    """코호트 = 지역 × 대표과목. 이 안에서 상대 평가한다."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for a in academies:
        # 학원은 가르치는 과목 수만큼의 코호트에 든다. 상대평가는 언제나
        # **같은 과목끼리** 여야 한다 — 수학 코호트에 든 학원의 과학
        # 점수를 과학 코호트 평균과 견주면 그 z 점수는 뜻이 없다.
        for sub in ranked_subjects(a) or [primary_subject(a)]:
            groups[(a.get("region_id"), sub)].append(a)

    cohorts: dict[tuple, dict] = {}
    for key, members in groups.items():
        sentiments, volumes, ratios = [], [], []
        per_academy: list[float] = []
        subject = key[1]
        for a in members:
            ms = [m for m in subject_mentions(
                      a, mentions_by_key.get(a["id"], []), subject)
                  if not m.get("is_excluded")]
            if ms:
                sentiments.extend(float(m.get("sentiment", 0.0)) for m in ms)
                # 학원 단위 평균도 따로 모은다. z 점수의 분모는 '학원끼리
                # 얼마나 벌어지는가'여야 한다 — 언급 단위 편차를 쓰면
                # 글마다의 잡음이 분모에 들어간다.
                per_academy.append(
                    statistics.mean(float(m.get("sentiment", 0.0)) for m in ms))
                volumes.append(math.log1p(len(ms)))
                cap = a.get("tofor_smtot") or 0
                if cap:
                    ratios.append(len(ms) / cap)
        cohorts[key] = {
            "mean_sentiment": round(statistics.mean(sentiments), 4) if sentiments else 0.0,
            "sd_sentiment": (round(statistics.pstdev(per_academy), 4)
                             if len(per_academy) >= 3 else 0.12),
            "volumes": volumes,
            "mention_capacity_ratio": statistics.mean(ratios) if ratios else 1.0,
            "size": len(members),
        }
    return cohorts


def cohort_for(academy: dict, cohorts: dict, subject: str | None = None) -> dict:
    """★ build_cohorts 와 같은 기준을 써야 한다. 예전에는 여기서
    subjects[0] 을, 저기서 primary_subject() 를 써서 예체능 학원이
    수학 코호트에서 상대평가될 수 있었다."""
    subject = subject or primary_subject(academy)
    return cohorts.get((academy.get("region_id"), subject), {
        "mean_sentiment": 0.0, "sd_sentiment": 0.12,
        "volumes": [], "mention_capacity_ratio": 1.0, "size": 0,
    })
