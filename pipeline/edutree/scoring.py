"""트리스코어 (TreeScore) 계산.

    TreeScore = 0.35·평판 + 0.35·진입난이도 + 0.15·화제성 + 0.15·투명성
    (예체능·기타 = 0.6·평판 + 0.4·화제성 — 나머지 두 기둥은 null)

가중치는 `config.WEIGHTS` 하나가 갖는다. **docs/SPEC.md §4 와 반드시
일치해야 한다** — 산식을 공개하기로 한 서비스라 문서와 코드가 어긋나면
공개하는 의미가 없다. 실제로 문서가 두 세대 뒤처져 있던 적이 있다.

설계 원칙
  1. 각 기둥은 0–100 으로 독립 계산되고, breakdown 에 계산 근거를 남긴다.
     근거를 못 만들면 점수도 못 낸다.
  2. 표본이 적은 학원은 코호트 평균으로 끌어당긴다(베이지안 축소).
     후기 3건짜리 학원이 1위로 튀는 것을 막는 핵심 장치다.
     **축소의 분모는 사전 표본수와 같은 단위여야 한다** — 가중치 합을
     그대로 쓰면 글 한 건의 무게가 0.2~0.5 라 표본 30건도 사전값에
     눌린다(§ effective_n).
  3. **표본 0 은 순위를 매기지 않는다.** 점수가 코호트 평균(50)으로
     채워져 있어 등수를 붙이면 그건 평가가 아니라 기본값이다.
     표본 1~9 건은 순위에 넣되 화면에 '표본 부족' 이라 적는다 —
     예전처럼 통째로 빼면 96개 조합 중 95개가 빈 화면이 된다.
  4. 점수는 **(학원 × 과목)** 마다 따로 낸다. 수학 후기 496건짜리
     종합학원이 그 점수로 과학 랭킹에 오르면 안 된다.

★ 가중치를 바꾸면 **실효 기여(가중치 × 표준편차)를 반드시 다시 잰다.**
  가중치가 같아도 분산이 다르면 영향이 다르다. `effective_contribution()`
  이 매 실행 재고, 명목 순서와 어긋나면 빌드가 경고한다.
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


# 코호트 z 점수를 0–100 으로 펼칠 때 쓰는 배수. **기둥이 공유한다.**
#
# ★ 기둥끼리 저울이 다르면 가중치가 곧 영향력이 되지 않는다. 평판은 15,
#   화제성은 18 을 쓰고 있었는데 그 차이에 근거가 없었다. 같은 z 축에
#   올리기로 한 이유가 저울을 맞추기 위해서였으니 배수도 같아야 한다.
Z_SCALE = 15

# 추세 화살표 임계값. **월평균 언급 수 대비 비율**이다(절대 건수가 아니다).
# 0.12 = '월평균의 12%씩 늘거나 줄고 있다'. 실측 분포를 보고 정한다 —
# 눈으로 정한 임계값은 다음 회차에서 또 깨진다.
TREND_THRESHOLD = 0.12
# 상대 기울기를 점수로 펼칠 때의 배수. rel 이 [-1, 1] 근처라 절대
# 기울기에 쓰던 배수(12)를 그대로 쓰면 slope_score 가 50 에 붙어 버린다.
TREND_SCALE = 30


def mention_weight(m: dict) -> float:
    """글 한 건의 무게. 신뢰도 × 최신성."""
    return float(m.get("credibility", 0.5)) * recency_weight(m.get("posted_at"))


def weighted_sentiment(mentions: list[dict]) -> float | None:
    """신뢰도·최신성 가중 평균 감성. **자기 값과 코호트 분포가 함께 쓴다.**

    ★ 예전에는 `reputation()` 이 가중 평균을 쓰고 `build_cohorts()` 는
      **단순 평균**의 표준편차를 z 의 분모로 줬다. 분자와 분모를 다른
      통계로 재면 z 가 뜻하는 바가 흐려진다 — 화제성에서 자기 값과
      코호트 분포를 다른 자로 재던 것과 같은 실수다.
    """
    num = den = 0.0
    for m in mentions:
        w = mention_weight(m)
        num += w * float(m.get("sentiment", 0.0))
        den += w
    return (num / den) if den else None


def effective_n(weights: list[float]) -> float:
    """유효 표본수 (Kish) = (Σw)² / Σw².

    **베이지안 축소의 분모는 사전 표본수와 같은 단위여야 한다.**
    예전에는 가중치 합(Σw)을 그대로 썼는데, 글 한 건의 무게가 보통
    0.2~0.5 라 표본 30건이면 Σw ≈ 7 이다. 사전표본 12 와 견주면 축소
    계수가 0.37 — 표본이 아무리 두꺼워도 사전값이 이긴다. 그래서 평판의
    분산이 코호트 z 축 위에서 짓눌렸고(실측 sd 4.03), 가중치 0.35 짜리
    기둥의 실효 기여가 0.15 짜리 화제성보다 작았다.

    Kish 유효 표본수는 가중치가 고르면 표본 수 n 과 같고, 신뢰도 낮은
    글이 섞인 만큼만 줄어든다. 이제 '사전표본 12건' 이라는 말이 실제로
    '글 12건만큼' 을 뜻한다.
    """
    s1 = sum(weights)
    s2 = sum(w * w for w in weights)
    return (s1 * s1 / s2) if s2 > 0 else 0.0


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
        w = mention_weight(m)
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
        w = mention_weight(m)
        sent = float(m.get("sentiment", 0.0))
        if sent > 0.05:
            pos += w
        elif sent < -0.05:
            neg += w
    opinionated = pos + neg
    recommend = round(pos / opinionated * 100, 1) if opinionated > 0 else None

    # 베이지안 축소. **유효 표본수 단위로** 끌어당긴다 — 가중치 합으로
    # 하면 표본 30건짜리도 사전값에 눌린다(effective_n 참고).
    m0 = config.REPUTATION_PRIOR_COUNT
    n_eff = effective_n([mention_weight(m) for m in valid])
    obs = num / den if den else cohort_mean
    shrunk = (obs * n_eff + m0 * cohort_mean) / (n_eff + m0)

    # 코호트 대비 z 점수로 옮긴다. [-1,1] 을 [0,100] 에 선형 매핑하면
    # 실제 감성이 0.00~0.78 구간에만 살아서 점수가 53~65 로 눌린다.
    # 가중치가 0.35 인데 순위를 거의 못 가르는 상태였다 — 가중치가
    # 뜻하는 바와 실제 영향이 어긋나면 산식을 공개하는 의미가 없다.
    #
    # 화제성이 이미 같은 방식(코호트 z점수)을 쓴다. 기둥끼리 저울을
    # 맞춰야 가중치가 곧 영향력이 된다.
    sd = cohort_sd or 0.12
    z = (shrunk - cohort_mean) / sd
    score = _clamp(50 + Z_SCALE * z)

    excluded = len(mentions) - len(valid)
    return round(score, 1), {
        "표본": len(valid),
        "유효표본": round(n_eff, 1),
        "긍정률": recommend,
        "의견_표명_가중치": round(opinionated, 2),
        "제외된_스팸": excluded,
        "가중_감성합": round(num, 2),
        "가중치_총합": round(den, 2),
        "코호트_평균감성": round(cohort_mean, 3),
        "코호트_감성표준편차": round(cohort_sd, 3),
        "축소_사전표본": m0,
        "설명": f"신뢰도·최신성 가중 감성 {round(obs, 3)} 를 코호트 평균 "
                f"{round(cohort_mean, 3)} 쪽으로 {m0}건만큼 축소 "
                f"(유효표본 {round(n_eff, 1)}건)",
    }


# ── 기둥 2. 화제성 (15%) ───────────────────────────────────────────
def volume_of(mentions: list[dict]) -> float:
    """언급량의 로그 스케일 값. **자기 값과 코호트 분포가 이걸 함께 쓴다.**

    90일 창은 경계가 딱딱하다 — 91일 된 글이 0이 되고 89일 된 글이 1이
    된다. 최신성 가중 합과 큰 쪽을 써서 경계를 무르게 한다. 날짜 없는
    글은 0.6 으로 들어가므로 전체가 0 이 되지는 않는다.

    ★ 예전에는 `momentum()` 이 이 식을 쓰고 `build_cohorts()` 는
      `log1p(전체 언급 수)` 를 썼다. 자기 값과 분포를 **다른 자로 재면**
      z 점수가 통째로 치우친다 — 날짜 불명 글의 무게가 0.6 이라 자기
      값만 체계적으로 낮게 나왔다. 같은 함수를 쓰게 해서 없앤다.
    """
    valid = [m for m in mentions if not m.get("is_excluded")]
    recent = [m for m in valid
              if (d := _to_date(m.get("posted_at"))) and (TODAY - d).days <= 90]
    weighted = sum(recency_weight(m.get("posted_at")) for m in valid)
    return math.log1p(max(len(recent), weighted))


def momentum(mentions: list[dict], cohort_volumes: list[float]) -> tuple[float, dict, str]:
    valid = [m for m in mentions if not m.get("is_excluded")]
    recent = [m for m in valid
              if (d := _to_date(m.get("posted_at"))) and (TODAY - d).days <= 90]
    weighted = sum(recency_weight(m.get("posted_at")) for m in valid)
    volume = volume_of(mentions)

    if len(cohort_volumes) >= 3:
        mu = statistics.mean(cohort_volumes)
        sd = statistics.pstdev(cohort_volumes) or 1.0
        z = (volume - mu) / sd
    else:
        z = 0.0
    volume_score = _clamp(50 + z * Z_SCALE)

    slope, direction = _trend(valid)
    slope_score = _clamp(50 + slope * TREND_SCALE)

    score = 0.6 * volume_score + 0.4 * slope_score
    return round(score, 1), {
        "최근90일_언급": len(recent),
        "최신성_가중합": round(weighted, 1),
        "전체_유효언급": len(valid),
        "코호트_z점수": round(z, 2),
        # 월평균 대비 증감 비율. 절대 건수가 아니다 — 규모가 다른 학원의
        # 추세를 같은 자로 재려면 상대값이어야 한다.
        "월별_추세_상대기울기": round(slope, 3),
        "설명": "코호트 내 언급량 z점수 60% + 12개월 월별 추세 40% "
                "(추세는 월평균 대비 상대 기울기)",
    }, direction


def _month_index(d: date) -> int:
    return d.year * 12 + d.month


def _trend(mentions: list[dict]) -> tuple[float, str]:
    """월별 언급 수의 상대 기울기와 방향 라벨.

    ★ **발견일로 채운 날짜는 쓰지 않는다.** 추세는 '언제 쓰였나' 의
      시계열인데, 발견일은 '언제 우리가 봤나' 다. 수집 일정이 곧 x축이
      되어 버리면 화살표가 학원의 화제성이 아니라 우리 크롤 일정을
      가리킨다 — 실측에서 발견 도장이 사흘(8/22~24)에 몰려 있어 추세가
      잡히는 학원 44곳 중 40곳이 '상승' 으로 나왔다.

      최신성 가중치와 90일 창에는 발견일을 그대로 쓴다. 거기서는 '최근에
      처음 본 글은 대체로 최근 글' 이라는 원래 논리가 성립한다. 시계열의
      모양을 만들 때만 못 쓴다.

      그래서 대부분의 학원은 '보합' 으로 남는다. 실제 작성일을 아는 글이
      9%뿐이기 때문이다 — **모르는 것을 모른다고 두는 편이** 수집 일정을
      추세로 파는 것보다 낫다.

    ★ **관측이 없는 달을 0 으로 채운다.** 예전에는 언급이 있는 달만
      버킷에 담아서, 1월(5건)과 6월(1건)이 인접한 두 점으로 계산됐다.
      사이의 빈 넉 달이 사라지므로 **언급이 끊긴 학원의 하락이 잡히지
      않았고**, 카드의 상승·보합 화살표가 실제보다 낙관적이었다.

      채우는 구간은 '처음 관측된 달 ~ 이번 달' 이다. 최근에 아무 글도
      없다는 것도 추세다 — 마지막 관측에서 끊으면 그 사실이 사라진다.

    ★ 다만 **관측된 달이 3개 미만이면 기울기를 내지 않는다.** 0 을
      채워 점을 늘리면 관측 한 달짜리로도 12점이 만들어져, 근거 한 줌으로
      '하락' 이라 단정하게 된다. 날짜를 아는 글이 절반뿐이라 특히 그렇다.
    """
    buckets: dict[int, int] = defaultdict(int)
    for m in mentions:
        if m.get("date_source") == "discovery":
            continue          # 발견일 — 작성 시점의 근거가 아니다
        d = _to_date(m.get("posted_at"))
        if d and 0 <= (TODAY - d).days <= 365:
            buckets[_month_index(d)] += 1
    if len(buckets) < 3:
        return 0.0, "stable"

    # 첫 관측 달부터 이번 달까지 빈 달을 0 으로 채운다.
    start, end = min(buckets), _month_index(TODAY)
    ys = [buckets.get(i, 0) for i in range(start, max(end, max(buckets)) + 1)]
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom

    # ★ 기울기를 **월평균 언급 수로 나눈다.** 절대 기울기는 학원 규모에
    #   딸려 다닌다 — 월 50건짜리가 30건으로 주는 것과 월 5건짜리가 0건이
    #   되는 것은 같은 '줄어듦' 인데 절대 기울기는 6배 차이가 난다.
    #   빈 달을 채우면서 점이 늘어 기울기 크기가 더 희석되므로, 옛 절대
    #   임계값(±0.35)을 그대로 두면 **거의 전부 '보합'** 이 된다(실측:
    #   하락 3곳 → 0곳). 상대값으로 재야 임계값이 규모와 무관해진다.
    rel = slope / my if my > 0 else 0.0
    direction = ("rising" if rel > TREND_THRESHOLD
                 else "falling" if rel < -TREND_THRESHOLD else "stable")
    return rel, direction


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
                # 학원 단위 값도 따로 모은다. z 점수의 분모는 '학원끼리
                # 얼마나 벌어지는가'여야 한다 — 언급 단위 편차를 쓰면
                # 글마다의 잡음이 분모에 들어간다.
                #
                # ★ reputation() 이 재는 것과 **같은 통계**여야 한다.
                #   여기서 단순 평균의 편차를 주고 저기서 가중 평균을
                #   견주면 z 가 무엇을 뜻하는지 말할 수 없다.
                wm = weighted_sentiment(ms)
                if wm is not None:
                    per_academy.append(wm)
                # ★ momentum() 과 **같은 함수**로 잰다. 다른 자로 재면
                #   z 점수가 통째로 치우친다 — 여기서 log1p(건수)를 쓰고
                #   저기서 최신성 가중합을 쓰고 있었다.
                volumes.append(volume_of(ms))
                cap = a.get("tofor_smtot") or 0
                if cap:
                    ratios.append(len(ms) / cap)
        cohorts[key] = {
            # μ 와 σ 는 **같은 분포**에서 나와야 한다. 예전에는 μ 를 글
            # 단위 평균(언급 많은 학원이 지배)으로, σ 를 학원 단위 편차로
            # 재서 z 의 중심과 폭이 서로 다른 것을 가리켰다.
            "mean_sentiment": (round(statistics.mean(per_academy), 4)
                               if per_academy else 0.0),
            "sd_sentiment": (round(statistics.pstdev(per_academy), 4)
                             if len(per_academy) >= 3 else 0.12),
            # 글 단위 평균은 참고용으로 남긴다(화면의 근거 설명에 쓰인다).
            "mean_sentiment_per_post": (round(statistics.mean(sentiments), 4)
                                        if sentiments else 0.0),
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


# ── 실효 기여 감시 ─────────────────────────────────────────────────
PILLARS = ("reputation", "selectivity", "momentum", "transparency")


def effective_contribution(subject_scores: dict,
                           min_sample: int = 1) -> dict[str, dict]:
    """기둥별 `가중치 × 표준편차`. 가중치와 실제 영향력이 맞는지 잰다.

    **가중치가 같아도 분산이 다르면 영향이 다르다.** 평판·진입난이도를
    각 0.35 로 올렸는데도 순위를 가른 것은 진입난이도뿐이었던 적이 있고,
    나중에는 0.15 짜리 화제성이 0.35 짜리 평판을 눌렀다(실효 2.55 대 1.41).
    둘 다 손으로 재서야 알았다 — 그래서 매 실행 잰다.

    학술 과목 점수만 본다. 예체능·기타는 저울 자체가 다르다.
    """
    values: dict[str, list[float]] = {p: [] for p in PILLARS}
    for per_subject in subject_scores.values():
        for sc in (per_subject or {}).values():
            if sc.get("subject_group") != "academic":
                continue
            if sc.get("sample_size", 0) < min_sample:
                continue
            for p in PILLARS:
                v = sc.get(p)
                if v is not None:
                    values[p].append(float(v))

    out: dict[str, dict] = {}
    for p in PILLARS:
        rows = values[p]
        sd = statistics.pstdev(rows) if len(rows) > 1 else 0.0
        w = config.WEIGHTS[p]
        out[p] = {"weight": w, "sd": round(sd, 2),
                  "effective": round(w * sd, 2), "n": len(rows)}
    return out


def audit_contribution(subject_scores: dict) -> list[str]:
    """명목 가중치 순서와 실효 기여 순서가 어긋나면 경고 문자열을 낸다.

    ★ 어긋난 채로 두면 '평판 35%' 라고 공개해 놓고 실제로는 화제성이
      순위를 가르는 상태가 된다. 산식을 공개하는 서비스에서 그건
      숫자가 틀린 것보다 나쁘다 — 설명이 틀린 것이기 때문이다.
    """
    table = effective_contribution(subject_scores)
    if not any(v["n"] for v in table.values()):
        return []

    line = " · ".join(
        f"{p} {v['weight']:.2f}×{v['sd']:.1f}={v['effective']:.2f}"
        for p, v in sorted(table.items(), key=lambda kv: -kv[1]["effective"]))
    out = [f"실효 기여(가중치×표준편차): {line}"]

    by_weight = sorted(PILLARS, key=lambda p: -config.WEIGHTS[p])
    by_effect = sorted(PILLARS, key=lambda p: -table[p]["effective"])
    # 가벼운 기둥이 무거운 기둥을 실제로 이기고 있는 짝만 짚는다.
    for i, heavy in enumerate(by_weight):
        for light in by_weight[i + 1:]:
            if config.WEIGHTS[light] >= config.WEIGHTS[heavy]:
                continue
            if table[light]["effective"] > table[heavy]["effective"]:
                out.append(
                    f"! 가중치 역전: {light}({config.WEIGHTS[light]:.2f}) 가 "
                    f"{heavy}({config.WEIGHTS[heavy]:.2f}) 보다 순위를 더 가른다 "
                    f"— 실효 {table[light]['effective']:.2f} > "
                    f"{table[heavy]['effective']:.2f}")
    _ = by_effect
    return out
