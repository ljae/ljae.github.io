"""트리스코어 회귀 테스트.

실명 사업자를 점수로 줄 세우는 서비스라, 여기서 지키는 것은 '숫자가
맞나' 보다 **'그 숫자가 무엇을 뜻하는지 설명할 수 있나'** 에 가깝다.

  · 안 본 것에 점수를 붙이지 않는다
  · 근거가 없는 기둥은 0 이 아니라 없음(None)이다
  · 가중치가 곧 영향력이어야 한다
  · 한 글은 한 학원에 대해 한 과목만 말한다
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import config, scoring                     # noqa: E402

TODAY = scoring.TODAY


def m(academy: str = "A", *, sentiment: float = 0.5, cred: float = 0.7,
      days: int | None = 30, subject: str | None = None,
      src: str | None = None, sel: dict | None = None,
      events: list[str] | None = None) -> dict:
    posted = None if days is None else (TODAY - timedelta(days=days)).isoformat()
    row = {
        "academy_key": academy, "sentiment": sentiment, "credibility": cred,
        "posted_at": posted, "is_excluded": False,
        "selectivity": sel or {}, "subjects": [subject] if subject else [],
        "subject": subject, "url_hash": f"{academy}{sentiment}{days}{subject}",
        # 진입난이도는 '사건이 확인됐는가' 다. 학술 과목은 이게 없으면
        # 네 기둥을 못 채워 순위에 서지 않는다.
        "sel_events": events or [],
    }
    if src:
        row["date_source"] = src
    return row


def academy(aid: str = "A", subjects=("math",), **kw) -> dict:
    return {"id": aid, "name": kw.get("name", f"{aid}수학학원"),
            "region_id": "daechi", "subjects": list(subjects),
            "tofor_smtot": kw.get("cap", 100),
            "reg_stttus_nm": "정상", "le_crse_list_nm": "수학",
            "estbl_ymd": "2010-01-01"}


def cohort(**kw) -> dict:
    return {"mean_sentiment": kw.get("mean", 0.3),
            "sd_sentiment": kw.get("sd", 0.2),
            "volumes": kw.get("volumes", [1.0, 2.0, 3.0]),
            "mention_capacity_ratio": 1.0, "size": 5}


# ── 표본 0 은 '적다' 가 아니라 '없다' ────────────────────────────
def test_표본0_은_순위를_매기지_않는다():
    """점수가 코호트 평균(50)으로 채워지므로 등수를 붙이면 그건 평가가
    아니라 기본값이다. '아직 안 봤다' 와 '보고서 낮았다' 는 다른 상태다."""
    s = scoring.compute(academy(), [], cohort())
    assert s["sample_size"] == 0
    assert s["is_ranked"] is False


def test_표본이_얇으면_순위에_넣되_표본_부족이라_적는다():
    """통째로 빼던 때는 96개 조합 중 95개가 빈 화면이었다."""
    s = scoring.compute(academy(), [m() for _ in range(3)], cohort())
    assert s["sample_size"] == 3
    assert s["is_ranked"] is False          # 10건 미만
    assert s["confidence"] == "low"

    # 사건을 넣어 네 기둥을 채운다 — 이 시험이 보는 것은 **표본 수**다.
    s10 = scoring.compute(
        academy(),
        [m(events=["rejected"], sentiment=0.5 + i * 0.01) for i in range(12)],
        cohort())
    assert s10["is_ranked"] is True
    assert s10["confidence"] == "medium"


# ── 예체능·기타는 기둥을 다 적용하지 않는다 ──────────────────────
def test_예체능은_없는_기둥을_None_으로_낸다():
    """없는 것을 0점으로 치면 그게 곧 왜곡이다."""
    s = scoring.compute(academy("B", ("arts",), name="가나미술교습소"),
                        [m("B") for _ in range(12)], cohort(), subject="arts")
    assert s["transparency"] is None and s["selectivity"] is None
    assert s["subject_group"] == "non_academic"


def test_예체능_총점은_평판과_화제성만으로_만들어진다():
    ms = [m("B") for _ in range(12)]
    s = scoring.compute(academy("B", ("arts",)), ms, cohort(), subject="arts")
    w = config.NON_ACADEMIC_WEIGHTS
    assert abs(s["total"] - (w["reputation"] * s["reputation"]
                             + w["momentum"] * s["momentum"])) < 0.06


def test_general_은_어느_과목_랭킹에도_안_들어간다():
    """어느 과목으로 견줄지 정할 수 없으면 등수도 매길 수 없다."""
    a = academy("C", (config.UNRANKED_SUBJECT,))
    s = scoring.compute(a, [m("C") for _ in range(30)], cohort())
    assert s["is_ranked"] is False
    assert scoring.ranked_subjects(a) == []


# ── 과목별 채점 ──────────────────────────────────────────────────
def test_과목이_여럿이면_그_과목을_말한_글만_근거다():
    """수학 후기 496건짜리 종합학원이 그 점수로 과학 3위가 됐다."""
    a = academy("D", ("math", "science"))
    ms = ([m("D", subject="math") for _ in range(20)]
          + [m("D", subject="science") for _ in range(3)])
    assert len(scoring.subject_mentions(a, ms, "science")) == 3
    assert len(scoring.subject_mentions(a, ms, "math")) == 20


def test_과목_불명_글은_대표_과목에만_넣는다():
    a = academy("D", ("math", "science"))
    ms = [m("D", subject=None) for _ in range(5)]
    assert len(scoring.subject_mentions(a, ms, "math")) == 5      # 대표
    assert len(scoring.subject_mentions(a, ms, "science")) == 0


def test_과목이_하나면_다른_과목_태그가_붙은_글도_근거다():
    """일부러 이렇게 둔다. 재 보고 판단한 결과다.

    실측(2026-08-30, 글 노드 8,076건): 과목 하나짜리 학원의 근거 중 11%가
    **다른 과목** 태그를 달고 있었다(수학 20% · 국어 12% · 영어 8%).
    '시대인재수학스쿨' 글의 이름 근처 낱말이 우연히 '영어' 인 식이다.

    그래도 버리지 않는다. 과목 태그는 **여러 과목 중 어디로 보낼지**
    고르는 신호이지 '이 글이 이 학원 이야기인가' 를 가리는 신호가 아니다
    (그건 관련성 게이트가 이미 했다). 과목이 하나면 보낼 곳도 하나뿐이라
    고를 것이 없다.

    게다가 과목 신호가 **있는** 글 자체가 12%뿐이다. 그 약한 신호로
    근거의 11%를 버리면 표본만 얇아지고 얻는 것이 없다.
    """
    a = academy("F", ("math",))
    ms = [m("F", subject="english") for _ in range(4)]
    assert len(scoring.subject_mentions(a, ms, "math")) == 4


def test_코호트와_산식이_같은_대표과목을_쓴다():
    """cohort_for 가 subjects[0] 을, build_cohorts 가 primary_subject() 를
    써서 예체능 학원이 수학 코호트에서 상대평가될 수 있었다."""
    a = academy("E", ("arts", "math"))
    assert scoring.primary_subject(a) == "math"      # 학술이 대표
    cohorts = scoring.build_cohorts([a], {"E": [m("E")]})
    assert ("daechi", "math") in cohorts and ("daechi", "arts") in cohorts


# ── ★ 이 리뷰에서 고친 것 ────────────────────────────────────────
def test_유효표본은_사전표본과_같은_단위다():
    """축소의 분모로 Σw 를 쓰면 글 한 건의 무게가 0.2~0.5 라 표본 30건도
    사전값(12)에 눌린다. 유효표본수는 가중치가 고르면 표본 수와 같다."""
    assert abs(scoring.effective_n([1.0] * 30) - 30) < 1e-9
    assert abs(scoring.effective_n([0.3] * 30) - 30) < 1e-9      # 척도 무관
    # 한 건이 지배하면 유효표본이 준다
    assert scoring.effective_n([10.0] + [0.1] * 9) < 2


def test_표본이_두꺼우면_축소에_덜_눌린다():
    """표본 40건과 4건이 같은 정도로 눌리면 축소가 아니라 뭉개기다."""
    c = cohort(mean=0.0, sd=0.2)
    thin = scoring.reputation([m(sentiment=0.8) for _ in range(4)], 0.0, 0.2)[0]
    thick = scoring.reputation([m(sentiment=0.8) for _ in range(40)], 0.0, 0.2)[0]
    assert thick > thin > 50
    _ = c


def test_화제성의_자와_코호트의_자가_같다():
    """자기 값은 최신성 가중합, 코호트 분포는 log1p(건수)로 재고 있었다.
    다른 자로 재면 z 가 통째로 치우친다."""
    ms = [m(days=None) for _ in range(10)]      # 날짜 불명 → 가중치 0.6
    a = academy()
    cohorts = scoring.build_cohorts([a], {"A": ms})
    assert cohorts[("daechi", "math")]["volumes"] == [scoring.volume_of(ms)]


def test_추세는_발견일을_쓰지_않는다():
    """발견일은 '언제 우리가 봤나' 이지 '언제 쓰였나' 가 아니다. 수집
    일정이 x축이 되면 화살표가 우리 크롤 일정을 가리킨다(실측: 추세가
    잡힌 44곳 중 40곳이 '상승' 이었다)."""
    found = [m(days=d, src="discovery") for d in (5, 6, 7, 8, 9, 10)]
    assert scoring._trend(found) == (0.0, "stable")


def test_추세는_빈_달을_0_으로_채운다():
    """빈 달을 건너뛰면 1월과 6월이 인접한 두 점이 된다 — 언급이 끊긴
    학원의 하락이 안 잡힌다."""
    old = [m(days=d) for d in (330, 325, 320, 300, 295, 290, 260, 255)]
    rel, direction = scoring._trend(old)
    assert direction == "falling" and rel < 0


def test_추세_임계값은_규모에_무관하다():
    """절대 기울기는 학원 규모에 딸려 다닌다. 월 50건이 30건으로 주는 것과
    월 5건이 0건이 되는 것은 같은 '줄어듦' 이다."""
    small = [m(days=d) for d in (330, 325, 300, 295, 260)]
    big = [m(days=d) for d in (330, 325, 300, 295, 260) for _ in range(10)]
    assert scoring._trend(small)[1] == scoring._trend(big)[1]


def test_실효_기여를_잰다_그리고_역전을_알린다():
    """가중치가 같아도 분산이 다르면 영향이 다르다. 손으로 재서야 알았던
    역전(0.15 짜리 화제성이 0.35 짜리 평판을 누름)을 자동으로 잡는다."""
    scores = {
        "A": {"math": {"subject_group": "academic", "sample_size": 20,
                       "reputation": 50.0, "momentum": 10.0,
                       "transparency": 50.0, "selectivity": 50.0}},
        "B": {"math": {"subject_group": "academic", "sample_size": 20,
                       "reputation": 50.0, "momentum": 90.0,
                       "transparency": 50.0, "selectivity": 50.0}},
    }
    table = scoring.effective_contribution(scores)
    assert table["momentum"]["sd"] > 0 and table["reputation"]["sd"] == 0
    warnings = scoring.audit_contribution(scores)
    assert any("역전" in w for w in warnings)


def test_가중치가_같은데_영향이_갈리면_알린다():
    """역전만 보면 놓친다. 같은 0.35 를 주었는데 한쪽이 두 배로 순위를
    가르면 '두 기둥을 똑같이 본다' 는 공개된 설명이 사실이 아니게 된다.
    이 서비스의 첫 사고가 정확히 그것이었다(평판 0.87 대 진입 3.27)."""
    def row(rep, sel):
        return {"subject_group": "academic", "sample_size": 20,
                "reputation": rep, "selectivity": sel,
                "momentum": 50.0, "transparency": 50.0}

    # 평판은 49~51 로 좁고, 진입난이도는 20~80 으로 넓다 — 가중치는 같다.
    scores = {
        "A": {"math": row(49.0, 20.0)},
        "B": {"math": row(51.0, 80.0)},
    }
    assert config.WEIGHTS["reputation"] == config.WEIGHTS["selectivity"]
    warnings = scoring.audit_contribution(scores)
    assert any("쏠림" in w for w in warnings)


def test_최신성은_날짜를_모르는_글을_중간으로_둔다():
    """모르는 것을 최신으로도, 오래된 것으로도 취급하지 않는다."""
    assert scoring.recency_weight(None) == 0.6
    fresh = scoring.recency_weight(TODAY.isoformat())
    old = scoring.recency_weight((TODAY - timedelta(days=720)).isoformat())
    assert fresh > 0.6 > old


# ── 투명성은 검증 가능한 것만 ────────────────────────────────────
def test_교습비는_투명성_배점에_없다():
    """NEIS 가 교습시간을 안 줘서 금액만으로는 비교가 성립하지 않는다."""
    labels = {k for k, _ in scoring.TRANSPARENCY_RUBRIC}
    assert not any("교습비" in k for k in labels)
    assert sum(v for _, v in scoring.TRANSPARENCY_RUBRIC) == 100


def test_총점은_공개된_가중치의_가중합이다():
    """산식을 공개하기로 했으면 총점이 **그 화면에 적힌 산식대로** 나와야 한다.

    ★ `config.WEIGHTS` 가 아니라 `breakdown['weights']` 로 견준다.
      학술 과목은 넷을 그대로 쓰고, 예체능·기타는 두 기둥 산식이 정본이라
      저울이 다르다. 화면은 그 저울을 그대로 찍는다 — 검증해야 하는 것은
      화면에 적힌 쪽이다.
    """
    ms = [m(events=["rejected"], sentiment=0.5 + i * 0.01) for i in range(15)]
    s = scoring.compute(academy(), ms, cohort())
    w = s["breakdown"]["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9, "공개하는 가중치의 합은 정확히 1"
    assert all(s[k] is not None for k in w), "저울에 오른 기둥은 값이 있어야 한다"
    assert abs(s["total"] - sum(w[k] * s[k] for k in w)) < 0.06


def test_근거가_없는_기둥은_채우지도_재정규화하지도_않는다():
    """없는 값을 코호트 평균으로 채우면 '모른다' 가 '보통' 이 되고,
    0 으로 치면 '쉽다' 가 된다. 그렇다고 **남은 기둥으로 다시 나누면
    없는 기둥이 유리해진다** — 남은 기둥의 몫이 커지기 때문이다.

    실측 신고: 모닝에듀(투명 100 · 표본 13)가 진입난이도가 없다는 이유로
    투명성 몫을 15% → 23% 로 받아, 진입난이도를 실제로 가진 렉스김어학원
    (표본 127)을 총점에서 앞질렀다.

    → 가중치는 넷 그대로 두고, 채운 기둥만 더한다(합 0.65). 그 값은
      4기둥 총점과 견줄 수 없으므로 **순위에 넣지 않는다.**
    """
    ms = [m() for _ in range(15)]          # 진입 사건이 없는 글들
    s = scoring.compute(academy(), ms, cohort())
    assert s["selectivity"] is None
    # 가중치는 공개한 그대로다 — 화면과 산식 페이지가 이 값을 찍는다.
    assert set(s["breakdown"]["weights"]) == {
        "reputation", "momentum", "transparency", "selectivity"}
    assert abs(sum(s["breakdown"]["weights"].values()) - 1.0) < 1e-9
    # 네 기둥을 못 채웠으므로 순위에 서지 않는다.
    assert s["is_complete"] is False
    assert s["is_ranked"] is False
    _ = (config, date)
