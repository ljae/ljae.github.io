"""트리스코어 (TreeScore) 계산.

    TreeScore = 0.35·평판 + 0.20·화제성 + 0.25·투명성 + 0.20·진입난이도

설계 원칙
  1. 각 기둥은 0–100 으로 독립 계산되고, breakdown 에 계산 근거를 남긴다.
     서비스가 산식을 전면 공개하기로 했으므로 근거를 못 만들면 점수도 못 낸다.
  2. 표본이 적은 학원은 코호트 평균으로 끌어당긴다(베이지안 축소).
     후기 3건짜리 학원이 1위로 튀는 것을 막는 핵심 장치다.
  3. 표본 10건 미만은 순위에서 아예 제외한다. 소수 악평으로 하위권을
     만들어 두면 그게 곧 명예훼손 리스크다.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone

from . import config

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
def reputation(mentions: list[dict], cohort_mean: float) -> tuple[float, dict]:
    valid = [m for m in mentions if not m.get("is_excluded")]
    if not valid:
        return _clamp((cohort_mean + 1) / 2 * 100), {
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
    score = _clamp((shrunk + 1) / 2 * 100)              # [-1,1] → [0,100]

    excluded = len(mentions) - len(valid)
    return round(score, 1), {
        "표본": len(valid),
        "긍정률": recommend,
        "의견_표명_가중치": round(opinionated, 2),
        "제외된_스팸": excluded,
        "가중_감성합": round(num, 2),
        "가중치_총합": round(den, 2),
        "코호트_평균감성": round(cohort_mean, 3),
        "축소_사전표본": m0,
        "설명": f"신뢰도·최신성 가중 감성 {round(num/den, 3) if den else 0} 를 "
                f"코호트 평균 {round(cohort_mean, 3)} 쪽으로 {m0}건만큼 축소",
    }


# ── 기둥 2. 화제성 (20%) ───────────────────────────────────────────
def momentum(mentions: list[dict], cohort_volumes: list[float]) -> tuple[float, dict, str]:
    valid = [m for m in mentions if not m.get("is_excluded")]
    recent = [m for m in valid
              if (d := _to_date(m.get("posted_at"))) and (TODAY - d).days <= 90]
    # 날짜 없는 글은 최근 90일 분자에서 빠지지만 전체 볼륨에는 남는다.
    volume = math.log1p(len(recent) if recent else len(valid) * 0.4)

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
TRANSPARENCY_RUBRIC = (
    ("등록상태 정상", 25),
    ("교습비 공개", 25),
    ("정원 공시", 15),
    ("교습과정 상세", 15),
    ("운영 지속기간", 20),
)


def transparency(academy: dict) -> tuple[float, dict]:
    """NEIS 공시 기반 규칙 채점. 100% 검증 가능한 유일한 기둥."""
    earned: dict[str, int] = {}

    status = (academy.get("reg_stttus_nm") or "").strip()
    earned["등록상태 정상"] = 25 if status in ("정상", "운영중", "개원") else (
        10 if status else 0)

    # NEIS 의 '교습비 공개여부'(THCC_OTHBC_YN)는 쓰지 않는다. 9,324곳 중
    # 9,224곳이 'Y' 라 아무것도 가르지 못한다. 실제로 금액이 적혀 있는 곳은
    # 1,836곳뿐이다. 신고 여부가 아니라 **실제 공개**를 점수로 친다.
    tuition = academy.get("tuition_monthly_krw")
    if tuition:
        earned["교습비 공개"] = 25
    elif academy.get("thcc_ctnt"):
        earned["교습비 공개"] = 12          # 원문은 있으나 금액 파싱 실패
    else:
        earned["교습비 공개"] = 0

    earned["정원 공시"] = 15 if academy.get("tofor_smtot") else 0
    earned["교습과정 상세"] = 15 if (academy.get("le_crse_list_nm")
                                 or academy.get("le_ord_nm")) else 0

    estbl = _to_date(academy.get("estbl_ymd"))
    if estbl:
        years = (TODAY - estbl).days / 365.25
        earned["운영 지속기간"] = round(_clamp(math.log1p(max(0, years)) / math.log(21) * 20, 0, 20))
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
def selectivity(mentions: list[dict], academy: dict,
                cohort_ratio_mean: float) -> tuple[float, dict]:
    """커뮤니티 신호에서 추정. 네 기둥 중 신뢰도가 가장 낮아 UI에 '추정' 표기."""
    valid = [m for m in mentions if not m.get("is_excluded")]
    hard = sum(m.get("selectivity", {}).get("hard", 0) for m in valid)
    wait = sum(m.get("selectivity", {}).get("wait", 0) for m in valid)

    n = max(1, len(valid))
    hard_score = _clamp(math.tanh(hard / n * 2.2) * 100)
    wait_score = _clamp(math.tanh(wait / n * 2.2) * 100)

    capacity = academy.get("tofor_smtot") or 0
    if capacity > 0 and valid:
        ratio = len(valid) / capacity
        rel = ratio / cohort_ratio_mean if cohort_ratio_mean else 1.0
        demand_score = _clamp(50 + math.log1p(rel) * 30)
    else:
        demand_score = 50.0

    score = 0.4 * hard_score + 0.3 * wait_score + 0.3 * demand_score
    return round(score, 1), {
        "난이도_언급": hard,
        "대기·마감_언급": wait,
        "정원": capacity or None,
        "언급÷정원_상대값": round(rel, 3) if capacity and valid else None,
        "설명": "레벨테스트 난이도 40% + 대기/마감 30% + 정원 대비 수요 30%",
        "주의": "커뮤니티 언급에서 추정한 값입니다. 공식 경쟁률이 아닙니다.",
    }


# ── 종합 ───────────────────────────────────────────────────────────
def confidence_label(sample: int) -> str:
    if sample >= config.CONFIDENCE_HIGH:
        return "high"
    if sample >= config.MIN_SAMPLE_FOR_RANK:
        return "medium"
    return "low"


def compute(academy: dict, mentions: list[dict], cohort: dict) -> dict:
    rep, rep_bd = reputation(mentions, cohort["mean_sentiment"])
    mom, mom_bd, direction = momentum(mentions, cohort["volumes"])
    tra, tra_bd = transparency(academy)
    sel, sel_bd = selectivity(mentions, academy, cohort["mention_capacity_ratio"])

    w = config.WEIGHTS
    total = (w["reputation"] * rep + w["momentum"] * mom
             + w["transparency"] * tra + w["selectivity"] * sel)

    sample = len([m for m in mentions if not m.get("is_excluded")])
    return {
        "academy_key": academy["id"],
        "total": round(total, 1),
        "reputation": rep,
        "momentum": mom,
        "transparency": tra,
        "selectivity": sel,
        "sample_size": sample,
        "confidence": confidence_label(sample),
        "is_ranked": sample >= config.MIN_SAMPLE_FOR_RANK,
        "momentum_direction": direction,
        "breakdown": {
            "weights": w,
            "reputation": rep_bd,
            "momentum": mom_bd,
            "transparency": tra_bd,
            "selectivity": sel_bd,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def build_cohorts(academies: list[dict], mentions_by_key: dict) -> dict:
    """코호트 = 지역 × 대표과목. 이 안에서 상대 평가한다."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for a in academies:
        subject = (a.get("subjects") or ["etc"])[0]
        groups[(a.get("region_id"), subject)].append(a)

    cohorts: dict[tuple, dict] = {}
    for key, members in groups.items():
        sentiments, volumes, ratios = [], [], []
        for a in members:
            ms = [m for m in mentions_by_key.get(a["id"], [])
                  if not m.get("is_excluded")]
            if ms:
                sentiments.extend(float(m.get("sentiment", 0.0)) for m in ms)
                volumes.append(math.log1p(len(ms)))
                cap = a.get("tofor_smtot") or 0
                if cap:
                    ratios.append(len(ms) / cap)
        cohorts[key] = {
            "mean_sentiment": round(statistics.mean(sentiments), 4) if sentiments else 0.0,
            "volumes": volumes,
            "mention_capacity_ratio": statistics.mean(ratios) if ratios else 1.0,
            "size": len(members),
        }
    return cohorts


def cohort_for(academy: dict, cohorts: dict) -> dict:
    subject = (academy.get("subjects") or ["etc"])[0]
    return cohorts.get((academy.get("region_id"), subject), {
        "mean_sentiment": 0.0, "volumes": [], "mention_capacity_ratio": 1.0, "size": 0,
    })
