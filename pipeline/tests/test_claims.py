"""주장(claim) 추출·집계 회귀 테스트.

이 구조의 약속은 둘이다.

  1. **인용문 없는 주장은 만들지 않는다.** 값만 남고 근거가 사라지면
     화면에서 '이 학원은 주 3회'라고 단정하게 되는데, 그 근거를 되짚을
     수 없으면 정정 요청을 받아도 붙일 자리가 없다.
  2. **1건은 숫자가 아니다.** 한 사람의 아이 반 이야기를 그 학원의 사실로
     적으면 그건 측정이 아니라 확대다.

실행: python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, claims, config, scoring     # noqa: E402


NAMES = {"가나수학학원", "가나수학", "가나"}
RIVALS = {"다라영어학원", "다라영어", "다라"}
TODAY = date(2026, 8, 28)


def mention(text: str, *, url_hash: str = "h1", posted: str = "2026-06-01",
            author: str = "a1", band: str | None = None) -> dict:
    return {
        "url_hash": url_hash,
        "academy_key": "A1",
        "academy_name": "가나수학학원",
        "title": "",
        "snippet": text,
        "posted_at": posted,
        "author_hash": author,
        "source_url": f"https://cafe.naver.com/x/{url_hash}",
        "band": band,
        "is_excluded": False,
    }


def kinds(text: str) -> list[tuple[str, float, float | None]]:
    """운영 사실만. 진입 사건은 events() 로 따로 본다."""
    got = claims.extract(mention(text), NAMES, RIVALS)
    return [(c["kind"], c["value"], c["value_high"]) for c in got
            if c["kind"] in claims.FACT_KINDS]


def events(text: str, names=NAMES) -> list[str]:
    got = claims.extract(mention(text), names, RIVALS)
    return sorted(c["kind"] for c in got if c["kind"].startswith("sel."))


# ── 추출 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("가나수학학원 다니는데 수업은 주 3회예요",
     [("fact.class_freq", 3.0, None)]),
    # 아라비아 숫자만 보면 절반을 놓친다. 수사 표기가 그만큼 흔하다.
    ("가나수학학원은 일주일에 세 번 가고 한 번에 90분 수업입니다",
     [("fact.class_freq", 3.0, None), ("fact.class_minutes", 90.0, None)]),
    ("가나수학학원 숙제가 하루 두 시간쯤 됩니다",
     [("fact.homework", 120.0, None)]),
    ("가나수학학원은 한 달에 두 번 시험을 봅니다",
     [("fact.test_freq", 2.0, None)]),
    # 매주 시험 = 월 4회. 낱말 자체가 빈도인 표현.
    ("가나수학학원 매주 단어시험 봐요", [("fact.test_freq", 4.0, None)]),
    # 어림수는 범위로 남긴다. 하나로 눌러 담으면 없던 정밀도가 생긴다.
    ("가나수학학원 수업 주 두세 번이에요",
     [("fact.class_freq", 2.0, 3.0)]),
])
def test_extracts(text, expected):
    assert kinds(text) == expected


def test_level_test_is_not_a_regular_exam():
    """레벨테스트는 입반 절차지 정기시험이 아니다.

    시험 횟수에 넣으면 '매달 시험 보는 학원'으로 읽힌다. 진입난이도 쪽
    신호이므로 그쪽에서 따로 센다.
    """
    assert kinds("가나수학학원 레벨테스트는 월 1회 있어요") == []


def test_number_belongs_to_the_name_on_its_left():
    """★ 거리로 정하면 남의 학원 수치를 가져온다.

    '다라영어학원은 주 5회인데 가나수학학원은 모르겠어요' 에서 '주 5회'는
    가나수학학원 쪽이 글자 수로는 더 가깝다. 한국어는 수식어가 앞에
    오므로 왼쪽 이름이 임자다.
    """
    assert kinds("다라영어학원은 주 5회인데 가나수학학원은 모르겠어요") == []
    # 왼쪽에 아무 이름도 없으면 거리로 정한다.
    assert kinds("수업 주 3회인 가나수학학원 다닙니다") == \
        [("fact.class_freq", 3.0, None)]


def test_no_name_no_claim():
    assert kinds("요즘 물가가 3만원씩 올라요") == []


# ── 실측이 드러낸 오탐 (2026-08-28, 캐시 재실행) ──────────────────
def test_clock_time_is_not_a_duration():
    """'화,목 4시20분' 의 20분은 수업 길이가 아니라 시작 시각이다."""
    assert kinds("가나수학학원 수업은 화,목 4시20분입니다") == []
    # 진짜 길이는 그대로 잡힌다
    assert kinds("가나수학학원 수업 90분씩 합니다") == \
        [("fact.class_minutes", 90.0, None)]


def test_negated_numbers_are_not_facts():
    """'숙제할 때도 10분도 못 앉아있고' 는 숙제량이 아니라 집중력 이야기다.

    한국어는 부정어가 수치 뒤에 온다 — 감성 쪽 NEGATORS 가 앞을 보는
    것과 반대다.
    """
    assert kinds("가나수학학원 숙제할 때도 10분도 못 앉아있어요") == []
    assert kinds("가나수학학원 수업 주 3회도 안 되더라고요") == []


def test_another_academy_called_by_its_category():
    """상호가 아니라 업종어로 부른 남의 학원도 임자가 될 수 있다.

    '주3회 2시간씩 영어학원을 35만원에 다니고있어요' 가 정상수학학원의
    수업 횟수로 잡혔던 글이다. rival_names 는 상호 목록이라 못 잡는다.
    """
    assert kinds("가나수학학원도 보는데 주3회 2시간씩 영어학원을 다녀요") == []
    # 업종어가 멀면 내 근거다 — '수학학원 알아보다가' 정도로 밀리지 않는다
    assert kinds("수학학원 알아보다가 가나수학학원으로 정했고 수업은 주 3회예요") == \
        [("fact.class_freq", 3.0, None)]


def test_sentence_about_an_unnamed_other_academy():
    """★ 거리 규칙이 못 잡는 경우가 있다.

    실측: 제목 '학원비 시간이 줄어도 가격이 같은게 정상인가요' 가 일상어
    '정상' 때문에 정상어학원 글로 잡혔고, 본문 '지금 주3회 2시간씩
    영어학원을 35만원에 다니고있어요' 가 그 학원의 수업 횟수가 됐다.
    그 문장에는 '정상' 이 없다 — 남의 학원을 업종어로 부르면서 내 이름은
    없는 문장은 내 근거가 아니다.
    """
    m = mention("지금 주3회 2시간씩 영어학원을 35만원에 다니고있어요")
    m["title"] = "학원비 시간이 줄어도 가격이 같은게 정상인가요"
    m["academy_name"] = "목동1관정상어학원"
    assert claims.extract(m, {"목동1관정상어학원", "정상어학", "정상"}) == []


def test_questions_and_hearsay_are_not_facts():
    """'주1회 1시간이라도 할까 하는데 어떨까요?' 는 그 학원의 사실이 아니다.

    진입난이도에서 질문글이 경험담과 같은 점수를 받던 것과 같은 결함이다.
    """
    assert kinds("가나수학학원 주1회 1시간이라도 할까 하는데 어떨까요?") == []
    assert kinds("가나수학학원 수업 주 3회라던데 맞나요") == []


def test_a_purchase_is_not_a_weekly_schedule():
    """'쿠킹스튜디오에서 한번 주문했어요' 가 '주 1회' 가 됐던 글."""
    assert kinds("가나수학학원 근처 가게에서 한번 주문했어요") == []
    # 빗금 형태는 그대로 잡는다
    assert kinds("가나수학학원 수업 3회/주 입니다") == \
        [("fact.class_freq", 3.0, None)]


def test_every_claim_carries_a_quote():
    got = claims.extract(mention("가나수학학원 수업 주 3회입니다"), NAMES)
    assert got and all(c["quote"] for c in got)
    assert "주 3회" in got[0]["quote"]


def test_id_survives_a_differently_truncated_snippet():
    """★ 취소 판정이 고아가 되지 않는 조건.

    스니펫은 회차마다 다른 길이로 잘려 온다. 위치로도 인용문으로도 id 를
    지으면 앞에 한 마디가 더 붙어 오는 것만으로 id 가 갈린다. 알맹이
    (글·학원·종류·값)로 지어야 같은 주장이 같은 id 로 되살아난다.
    """
    a = claims.extract(mention("가나수학학원 수업 주 3회입니다"), NAMES)[0]
    b = claims.extract(mention("아 그리고 가나수학학원 수업 주 3회입니다"), NAMES)[0]
    assert a["id"] == b["id"]
    assert a["quote"] != b["quote"]      # 인용문은 달라도 같은 주장이다

    # 다른 글이면 다른 id
    c = claims.extract(mention("가나수학학원 수업 주 3회입니다",
                               url_hash="h2"), NAMES)[0]
    assert a["id"] != c["id"]
    # 값이 다르면 다른 주장이다
    d = claims.extract(mention("가나수학학원 수업 주 5회입니다"), NAMES)[0]
    assert a["id"] != d["id"]


def test_same_value_twice_in_one_post_is_one_claim():
    """한 사람이 두 번 말한 것이 두 사람이 말한 것처럼 보이면 안 된다."""
    got = claims.extract(
        mention("가나수학학원 수업 주 3회예요. 가나수학학원 주 3회 맞아요"),
        NAMES)
    assert len([c for c in got if c["kind"] == "fact.class_freq"]) == 1


def test_excluded_mentions_yield_nothing():
    """홍보글의 '주 5회 집중반!' 은 사실 진술이 아니라 광고 문구다."""
    m = mention("가나수학학원 주 5회 집중반 모집합니다")
    m["is_excluded"] = True
    assert claims.extract_all([m], {"A1": NAMES}, RIVALS) == []


# ── 진입난이도 사건 ────────────────────────────────────────────────
#
# 옛 식(낱말 세기)을 캐시로 재 봤을 때 나온 세 가지 결함을 그대로 굳힌다.
# 언급 30건·정원 200 조건에서:
#     레테 얘기 없음                24.7   '모른다' 가 '쉽다' 로
#     '난이도 높아 떨어졌어요'       74.1   기준점
#     '어렵지 않았어요, 대기 없이'   70.6   부정문이 그대로 난이도
#     '어렵다던데 걸리나요?'         74.1   질문글이 경험담과 동일
def test_experience_produces_events():
    assert events("가나수학학원 레벨테스트 난이도가 높아 떨어졌어요 대기도 걸렸습니다") == \
        ["sel.test_exists", "sel.test_failed", "sel.waitlist"]


def test_negation_produces_no_events():
    """★ 부정문이 난이도가 되던 결함(70.6점).

    한국어는 부정어가 뒤에도 온다 — '어렵지 않았어요' 와 '대기 없이'.
    감성에는 NEGATORS 가 걸려 있었는데 진입난이도에는 없었다.
    """
    assert events("가나수학학원 레테 어렵지 않았어요 대기 없이 바로 등록했습니다") == []


def test_questions_produce_no_events():
    """★ 질문글이 경험담과 같은 점수를 받던 결함(둘 다 74.1점)."""
    assert events("가나수학학원 레테 어렵다던데 대기 걸리나요?") == []


def test_grade_drop_is_not_a_failed_placement_test():
    """'성적이 떨어져서' 는 레벨테스트 탈락이 아니다."""
    assert events("가나수학학원 다니는데 성적이 떨어져서 고민이에요") == []
    # 시험 맥락이 있으면 어간형도 잡는다
    assert "sel.test_failed" in events("가나수학학원 레테 두 번 떨어지고 세 번째에 붙었어요")


def test_a_waiting_room_is_not_a_waitlist():
    """'대기실 비디오에서 보니' 가 대기자 명단으로 잡혔던 글(실측)."""
    assert events("가나수학학원 대기실 비디오에서 보니 쌤들이 캐나다분들") == []
    assert events("가나수학학원 대기 두 달 걸린대요") == ["sel.waitlist"]


def test_events_need_the_academy_nearby():
    """과목·학급이 지키는 창(窓) 규칙을 진입난이도만 안 지키고 있었다."""
    far = "가나수학학원 이야기는 여기까지고 " + "그냥 잡담이 이어집니다 " * 4 + \
          "다른 곳은 레테에서 떨어졌대요"
    assert events(far) == []


# ── 집계 ───────────────────────────────────────────────────────────
def _rows(texts: list[tuple[str, str]]) -> list[dict]:
    """(본문, 작성자) 목록 → 주장들."""
    out = []
    for i, (text, author) in enumerate(texts):
        out += claims.extract(
            mention(text, url_hash=f"h{i}", author=author), NAMES, RIVALS)
    return out


def test_one_source_gives_no_number():
    """★ 1건이면 숫자를 내지 않는다. 인용문만 보여준다."""
    card = claims.facts_for(_rows([("가나수학학원 수업 주 3회예요", "a1")]),
                            TODAY)["fact.class_freq"]
    assert card["n"] == 1
    assert card["value"] is None and card["text"] is None
    assert card["quotes"][0]["quote"]


def test_two_sources_give_a_number():
    card = claims.facts_for(_rows([
        ("가나수학학원 수업 주 3회예요", "a1"),
        ("가나수학학원은 주 3회 갑니다", "a2"),
    ]), TODAY)["fact.class_freq"]
    assert card["value"] == 3.0
    assert card["text"] == "3회"


def test_disagreement_shows_a_range_not_an_average():
    """주2회와 주5회의 평균 3.5회는 어느 반에도 없는 숫자다."""
    card = claims.facts_for(_rows([
        ("가나수학학원 수업 주 2회예요", "a1"),
        ("가나수학학원 수업 주 5회입니다", "a2"),
        ("가나수학학원은 주 5회 갑니다", "a3"),
    ]), TODAY)["fact.class_freq"]
    assert card["low"] == 2.0 and card["high"] == 5.0
    assert "2회~5회" in card["text"]


def test_wildly_scattered_values_get_no_number():
    """★ '숙제량 20분 · 10분~5시간' 의 중앙값 20분은 근거에 없는 정밀도다.

    반이 다르거나 오탐이 섞인 것인데, 어느 쪽이든 하나의 숫자로 단정할
    상태가 아니다. 범위와 '후기마다 다름' 만 적는다.
    """
    card = claims.facts_for(_rows([
        ("가나수학학원 숙제 10분이면 끝나요", "a1"),
        ("가나수학학원 숙제 하루 5시간 걸려요", "a2"),
        ("가나수학학원 숙제 30분쯤 합니다", "a3"),
    ]), TODAY)["fact.homework"]
    assert card["disputed"] is True
    assert card["value"] is None
    assert "후기마다 다름" in card["text"]
    assert card["low"] == 10.0 and card["high"] == 300.0


def test_splits_by_grade_band_when_values_really_differ():
    """구간이 다르면 다른 값인 게 정상이다 — 합치면 둘 다 틀린다."""
    rows = []
    for i, (text, band) in enumerate([
        ("가나수학학원 수업 주 2회예요", "elem_low"),
        ("가나수학학원은 주 2회 갑니다", "elem_low"),
        ("가나수학학원 수업 주 5회입니다", "high"),
        ("가나수학학원은 주 5회예요", "high"),
    ]):
        rows += claims.extract(
            mention(text, url_hash=f"b{i}", author=f"a{i}", band=band), NAMES)
    card = claims.facts_for(rows, TODAY)["fact.class_freq"]
    assert set(card["byBand"]) == {"elem_low", "high"}
    assert card["byBand"]["elem_low"]["value"] == 2.0
    assert card["byBand"]["high"]["value"] == 5.0


def test_old_values_are_marked_stale_not_deleted():
    """낡음은 가짜가 아니다. 회색으로 표시할 뿐 지우지 않는다."""
    old = (TODAY - timedelta(days=800)).isoformat()
    rows = []
    for i in range(2):
        rows += claims.extract(
            mention("가나수학학원 수업 주 3회예요", url_hash=f"o{i}",
                    author=f"a{i}", posted=old), NAMES)
    card = claims.facts_for(rows, TODAY)["fact.class_freq"]
    assert card["stale"] is True
    assert card["value"] == 3.0          # 값은 그대로 남는다


def test_weekly_hours_derived_only_when_both_are_established():
    """★ 한쪽이 1건뿐인데 곱하면 그 글이 말하지 않은 값을 지어내게 된다."""
    # 횟수만 확정, 길이는 1건 → 파생 없음
    thin = _rows([
        ("가나수학학원 수업 주 3회예요", "a1"),
        ("가나수학학원은 주 3회 갑니다", "a2"),
        ("가나수학학원 수업 90분씩 해요", "a3"),
    ])
    assert "derived.class_hours" not in claims.facts_for(thin, TODAY)

    # 둘 다 확정 → 주당 4.5시간
    full = thin + _rows([("가나수학학원 수업은 90분 수업입니다", "a4")])
    card = claims.facts_for(full, TODAY)["derived.class_hours"]
    assert card["value"] == 4.5


def test_revoked_claims_leave_the_card():
    """취소는 삭제가 아니라 스위치다 — 꺼진 주장은 집계에서 빠진다."""
    rows = _rows([
        ("가나수학학원 수업 주 3회예요", "a1"),
        ("가나수학학원은 주 3회 갑니다", "a2"),
    ])
    assert claims.facts_for(rows, TODAY)["fact.class_freq"]["value"] == 3.0
    rows[0]["status"] = "revoked"
    card = claims.facts_for(rows, TODAY)["fact.class_freq"]
    assert card["n"] == 1 and card["value"] is None


# ── 진입난이도 산식 ────────────────────────────────────────────────
def _sel_mentions(text: str, n: int, *, posted: str = "2026-06-01") -> list[dict]:
    out = []
    for i in range(n):
        m = mention(text, url_hash=f"s{i}", author=f"au{i}", posted=posted)
        claims.attach_events([m], claims.extract(m, NAMES))
        out.append(m)
    return out


def test_no_events_means_no_score_not_a_low_score():
    """★ '모른다' 를 '쉽다' 로 적지 않는다.

    옛 식은 레테 얘기가 한 번도 없는 학원에 24.7점을 줬다. 배점 30%인
    '정원 대비 수요' 가 후기 없이도 값을 만들었기 때문이다.
    """
    rows = _sel_mentions("가나수학학원 선생님 친절하고 아이가 잘 다녀요", 30)
    score, bd = scoring.selectivity(rows, {"tofor_smtot": 200})
    assert score is None
    assert bd["사건"] == {}
    assert scoring.selectivity_tier(bd) is None


def test_events_outrank_a_bare_level_test_mention():
    """무게가 살아 있어야 한다.

    처음에는 사건을 전부 더했더니 '레벨테스트 있음'(0.3)이 양으로 쌓여
    96점이 됐다 — 무게를 0.3 으로 둔 뜻이 통째로 상쇄됐다. 종류별로
    포화시켜야 '레테가 있다는 것만으로는 난이도가 아니다' 가 성립한다.
    """
    bare, _ = scoring.selectivity(
        _sel_mentions("가나수학학원 레테 보고 등록했어요", 30), {})
    real, _ = scoring.selectivity(
        _sel_mentions("가나수학학원 레벨테스트 난이도가 높아 떨어졌어요 대기도 걸렸습니다",
                      30), {})
    assert bare < real
    assert bare < 50            # 레테가 있다는 것만으로는 어렵지 않다


def test_missing_pillar_is_dropped_not_filled():
    """근거 없는 기둥은 남은 기둥으로 가중치를 다시 나눈다."""
    academy = {"id": "A1", "name": "가나수학학원", "region_id": "daechi",
               "subjects": ["math"], "reg_stttus_nm": "정상",
               "tofor_smtot": 200, "le_crse_list_nm": "수학"}
    cohort = {"mean_sentiment": 0.0, "sd_sentiment": 0.12, "volumes": [],
              "mention_capacity_ratio": 1.0, "size": 5}
    quiet = _sel_mentions("가나수학학원 선생님 친절하고 아이가 잘 다녀요", 12)
    for m in quiet:
        m.update({"sentiment": 0.5, "credibility": 0.7, "substance": 1})
    out = scoring.compute(academy, quiet, cohort, subject="math")
    assert out["selectivity"] is None
    w = out["breakdown"]["weights"]
    assert "selectivity" not in w
    assert abs(sum(w.values()) - 1.0) < 1e-6


# ── 게이트 B ───────────────────────────────────────────────────────
def test_substance_grades():
    """얕은 글을 버리지 않고 등급을 매긴다 — 기둥마다 문턱이 다르다."""
    assert analyze.score_substance("가나수학학원 다녀요") == 0
    assert analyze.score_substance("가나수학학원 좋아요 만족합니다") == 1
    assert analyze.score_substance("가나수학학원 주 3회 수업합니다") == 2


def test_shallow_posts_count_for_buzz_but_not_reputation():
    """★ 층을 섞지 않는다.

    한 줄짜리 '거기 좋대요' 는 회자의 증거로는 유효하지만 감성은 아니다.
    통째로 버리면 화제성이 정보량을 재는 지표로 변질된다.
    """
    rows = [{"url_hash": f"q{i}", "posted_at": "2026-08-01", "sentiment": 0.0,
             "credibility": 0.5, "substance": 0, "is_excluded": False}
            for i in range(6)]
    _, bd = scoring.reputation(rows, 0.0)
    assert bd["표본"] == 0                       # 평판에는 안 들어간다
    _, mbd, _ = scoring.momentum(rows, [1.0, 2.0, 3.0])
    assert mbd["전체_유효언급"] == 6             # 화제성에는 들어간다


def test_near_duplicates_keep_the_oldest_only():
    """같은 원고를 여러 곳에 옮긴 바이럴 배치. 개별 글은 스팸 점수가 낮다."""
    body = ("이 학원 정말 좋습니다 아이가 즐겁게 다니고 성적도 올랐어요 "
            "선생님들도 친절하시고 관리가 꼼꼼합니다")
    rows = [{"academy_key": "A1", "snippet": body, "posted_at": d,
             "is_excluded": False}
            for d in ("2026-05-01", "2026-05-02", "2026-05-03")]
    rows, hit = analyze.flag_near_duplicates(rows)
    assert hit == 2
    assert [r["is_excluded"] for r in rows] == [False, True, True]


def test_bursts_ignore_discovery_dates():
    """★ 발견일은 작성일이 아니다.

    한 회차에 발견한 글 수천 건이 같은 날짜를 갖는다. 처음에 이걸
    빼먹었더니 3,256건이 버스트로 잡혔다 — 캠페인이 아니라 우리 수집
    일정이었다.
    """
    rows = [{"academy_key": "A1", "author_hash": "z", "posted_at": "2026-08-01",
             "date_source": "discovery", "is_excluded": False}
            for _ in range(5)]
    _, hit = analyze.flag_author_bursts(rows)
    assert hit == 0
    for r in rows:
        r["date_source"] = "cafe_list"
    _, hit = analyze.flag_author_bursts(rows)
    assert hit == 5


# ── 취소 회로 ──────────────────────────────────────────────────────
#
# 이 구조의 약속: **한 글의 일부만 끌 수 있다.** posts.py 의 무효화는 글
# 전체를 끄므로 '이 진입난이도 근거는 틀렸지만 평판 근거는 맞다' 를 담을
# 자리가 없었다.
def test_revoking_one_claim_leaves_the_rest_of_the_post():
    m = mention("가나수학학원 레테에서 떨어졌어요. 수업은 주 3회입니다")
    rows = claims.extract(m, NAMES)
    kinds_before = {r["kind"] for r in rows}
    assert "sel.test_failed" in kinds_before
    assert "fact.class_freq" in kinds_before

    target = next(r for r in rows if r["kind"] == "sel.test_failed")
    rows, stat = claims.apply_verdicts(
        rows, {target["id"]: {"verdict": "revoked", "reason": "사실 아님"}})
    assert stat["revoked"] == 1

    claims.attach_events([m], rows)
    assert "sel.test_failed" not in m["sel_events"]        # 사건은 꺼졌고
    card = claims.facts_for(rows, TODAY)
    assert "fact.class_freq" in card                      # 사실은 살아 있다


def test_a_revocation_without_a_reason_is_ignored():
    """사유 없는 취소는 나중에 지우지도 못하고 남는다. posts.py 와 같은 규칙."""
    m = mention("가나수학학원 레테에서 떨어졌어요")
    rows = claims.extract(m, NAMES)
    target = next(r for r in rows if r["kind"] == "sel.test_failed")
    rows, stat = claims.apply_verdicts(
        rows, {target["id"]: {"verdict": "revoked", "reason": "  "}})
    assert stat["revoked"] == 0
    assert target["status"] == "active"


def test_deleting_the_verdict_brings_the_claim_back():
    """★ 취소는 삭제가 아니라 스위치다.

    claim_id 가 결정적이라 같은 원문에서 같은 id 가 다시 나온다.
    판정을 지우면 그 주장이 그대로 되살아난다 — 되돌릴 수 있다는 것이
    이 설계의 조건이다.
    """
    m = mention("가나수학학원 레테에서 떨어졌어요")
    first = claims.extract(m, NAMES)
    target = next(r for r in first if r["kind"] == "sel.test_failed")
    claims.apply_verdicts(first, {target["id"]: {"verdict": "revoked",
                                                 "reason": "사실 아님"}})
    assert target["status"] == "revoked"

    # 판정을 지운 뒤 다시 지어 보면
    again = claims.extract(m, NAMES)
    revived = next(r for r in again if r["kind"] == "sel.test_failed")
    assert revived["id"] == target["id"]
    again, stat = claims.apply_verdicts(again, {})
    assert revived["status"] == "active" and stat["revoked"] == 0


def test_outdated_disputes_go_stale_by_themselves_only_when_old():
    """자동 반영은 이것 하나뿐이다 — 낡음은 가짜가 아니고 되돌리기도 쉽다."""
    old = mention("가나수학학원 레테에서 떨어졌어요", posted="2023-01-01")
    rows = claims.extract(old, NAMES)
    target = next(r for r in rows if r["kind"] == "sel.test_failed")
    disputes = [{"claim_id": target["id"], "reason": "outdated"}]
    rows, stat = claims.apply_verdicts(rows, {}, disputes, TODAY)
    assert stat["auto_stale"] == 1 and target["status"] == "stale"

    # 최근 글이면 자동으로 넘기지 않는다. 사람이 본다.
    recent = mention("가나수학학원 레테에서 떨어졌어요", posted="2026-06-01")
    rows = claims.extract(recent, NAMES)
    t2 = next(r for r in rows if r["kind"] == "sel.test_failed")
    rows, stat = claims.apply_verdicts(
        rows, {}, [{"claim_id": t2["id"], "reason": "outdated"}], TODAY)
    assert stat["auto_stale"] == 0 and t2["status"] == "active"


def test_other_dispute_reasons_never_auto_apply():
    """'사실 아님' 은 사람이 본다. 접수가 곧 편집권이 되면 안 된다."""
    old = mention("가나수학학원 레테에서 떨어졌어요", posted="2020-01-01")
    rows = claims.extract(old, NAMES)
    target = next(r for r in rows if r["kind"] == "sel.test_failed")
    rows, stat = claims.apply_verdicts(
        rows, {}, [{"claim_id": target["id"], "reason": "not_true"}], TODAY)
    assert stat["auto_stale"] == 0 and target["status"] == "active"


def test_revocation_removes_the_score_it_does_not_raise_it():
    """★ 취소가 유리해지는 통로가 되면 안 된다.

    사건이 0건이 되면 점수는 올라가는 게 아니라 **사라진다**.
    """
    rows = _sel_mentions("가나수학학원 레테에서 떨어졌어요 대기도 걸렸습니다", 6)
    before, _ = scoring.selectivity(rows, {})
    assert before is not None

    all_claims = []
    for m in rows:
        all_claims += claims.extract(m, NAMES)
    all_claims, _ = claims.apply_verdicts(
        all_claims,
        {c["id"]: {"verdict": "revoked", "reason": "다른 학원 이야기"}
         for c in all_claims})
    claims.attach_events(rows, all_claims)
    after, bd = scoring.selectivity(rows, {})
    assert after is None
    assert "모른다" in bd["주의"]


def test_dispute_rate_is_reported_not_hidden():
    """숨기면 그 자체가 왜곡이다."""
    m = mention("가나수학학원 레테에서 떨어졌어요. 수업은 주 3회입니다")
    rows = claims.extract(m, NAMES)
    target = next(r for r in rows if r["kind"] == "sel.test_failed")
    claims.apply_verdicts(rows, {target["id"]: {"verdict": "revoked",
                                                "reason": "광고"}})
    rate = claims.dispute_rate(rows)["A1"]
    assert rate["dropped"] == 1 and rate["total"] == len(rows)
