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
def reputation(mentions: list[dict], cohort_mean: float,
               cohort_sd: float = 0.12) -> tuple[float, dict]:
    valid = [m for m in mentions if not m.get("is_excluded")]
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
def _selectivity_raw(rows: list[dict], capacity: int,
                     cohort_ratio_mean: float) -> tuple[float, dict]:
    """진입난이도의 알맹이. 학원 전체에도, 등급반 하나에도 같은 식을 쓴다.

    난이도·대기 신호에도 최신성을 건다. 3년 전 '대기 걸렸다'와 지난달
    '대기 걸렸다'가 같은 무게일 이유가 없다 — 진입난이도야말로 지금
    상황을 말해야 하는 값이다.
    """
    hard = sum(m.get("selectivity", {}).get("hard", 0)
               * recency_weight(m.get("posted_at")) for m in rows)
    wait = sum(m.get("selectivity", {}).get("wait", 0)
               * recency_weight(m.get("posted_at")) for m in rows)
    n = max(1, len(rows))
    hard_score = _clamp(math.tanh(hard / n * 2.2) * 100)
    wait_score = _clamp(math.tanh(wait / n * 2.2) * 100)

    if capacity > 0 and rows:
        ratio = len(rows) / capacity
        rel = ratio / cohort_ratio_mean if cohort_ratio_mean else 1.0
        demand_score = _clamp(50 + math.log1p(rel) * 30)
    else:
        rel = None
        demand_score = 50.0

    score = 0.4 * hard_score + 0.3 * wait_score + 0.3 * demand_score
    return score, {
        "난이도_언급": round(hard, 1),
        "대기·마감_언급": round(wait, 1),
        "표본": len(rows),
        "언급÷정원_상대값": round(rel, 3) if rel is not None else None,
    }


def selectivity(mentions: list[dict], academy: dict,
                cohort_ratio_mean: float) -> tuple[float, dict]:
    """커뮤니티 신호에서 추정. 공식 경쟁률이 아니므로 UI 에 '추정' 표기.

    가중치가 0.35 로 올라가면서 축소(shrinkage)를 넣었다. 표본 12건짜리
    학원이 '난이도 100' 으로 서면 그건 측정이 아니라 잡음이다. 표본이
    적을수록 중앙(50)으로 끌어당긴다.

    ★ 등급반별 점수는 만들지 않는다.
      학부모가 실제로 묻는 것은 '그 학원 심화반 들어갈 수 있나'가 맞다.
      그래서 반 이름 주변에서 난이도 단어를 세어 봤는데, 400곳 전체에서
      반 이름과 난이도 단어가 함께 붙은 언급이 **186건**뿐이었고 그중
      상당수가 키워드 나열형 광고였다('파주 … 심화반 난이도 음악 미술').
      결과도 기초반이 최상위반보다 어렵게 나왔다.

      숫자를 내면 정밀해 보이지만 잡음이다. 반별 난이도는 큐레이션
      테크트리의 단계별 진입 기준(exit_criteria)으로 대신한다 — 그쪽은
      사람이 적은 것이라 근거가 분명하다.
    """
    valid = [m for m in mentions if not m.get("is_excluded")]
    capacity = academy.get("tofor_smtot") or 0
    raw, detail = _selectivity_raw(valid, capacity, cohort_ratio_mean)

    # 표본이 적으면 중앙으로 끌어당긴다. 평판의 베이지안 축소와 같은 이유.
    m0 = config.SELECTIVITY_PRIOR_COUNT
    n = len(valid)
    score = (raw * n + 50.0 * m0) / (n + m0)

    # ── 등급반별 ────────────────────────────────────────────────
    return round(score, 1), {
        **detail,
        "정원": capacity or None,
        "축소_사전표본": m0,
        "설명": "레벨테스트 난이도 40% + 대기/마감 30% + 정원 대비 수요 30%"
                f" (표본 {n}건, 사전표본 {m0}건만큼 중앙으로 축소)",
        "주의": "커뮤니티 언급에서 추정한 값입니다. 공식 경쟁률이 아닙니다.",
    }


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


def compute(academy: dict, mentions: list[dict], cohort: dict) -> dict:
    rep, rep_bd = reputation(mentions, cohort["mean_sentiment"],
                             cohort.get("sd_sentiment") or 0.12)
    mom, mom_bd, direction = momentum(mentions, cohort["volumes"])

    # 예체능·기타는 만족도와 화제성만 본다.
    #
    # 투명성은 공시가 '미술' 한 줄인 경우가 많아 상세도를 재면 실제 차이가
    # 아니라 공시 습관을 재게 된다. 진입난이도는 레벨테스트·대기 개념이
    # 없는 곳이 대부분이라 신호가 안 잡히고, 없는 것을 0점으로 치면
    # 그게 곧 왜곡이다.
    subject = primary_subject(academy)
    academic = subject in config.ACADEMIC_SUBJECTS
    rankable = subject != config.UNRANKED_SUBJECT

    if academic:
        tra, tra_bd = transparency(academy)
        sel, sel_bd = selectivity(mentions, academy,
                                  cohort["mention_capacity_ratio"])
        w = config.WEIGHTS
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
        # compute() 와 같은 기준을 써야 한다. 다르면 예체능 학원이
        # 수학 코호트에서 상대평가되는 일이 생긴다.
        groups[(a.get("region_id"), primary_subject(a))].append(a)

    cohorts: dict[tuple, dict] = {}
    for key, members in groups.items():
        sentiments, volumes, ratios = [], [], []
        per_academy: list[float] = []
        for a in members:
            ms = [m for m in mentions_by_key.get(a["id"], [])
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


def cohort_for(academy: dict, cohorts: dict) -> dict:
    subject = (academy.get("subjects") or ["etc"])[0]
    return cohorts.get((academy.get("region_id"), subject), {
        "mean_sentiment": 0.0, "sd_sentiment": 0.12,
        "volumes": [], "mention_capacity_ratio": 1.0, "size": 0,
    })
