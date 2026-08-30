"""과목·학년 구간 판정 회귀 테스트.

과목을 잘못 정하면 그 학원이 **엉뚱한 랭킹에 실명으로 뜬다.** '아이엘이는
영어학원인데 국어 랭킹에 있다' 는 신고가 그렇게 들어왔고, 뿌리를 파 보니
827곳이 같은 상태였다.

★ 여기서 고칠 때마다 반대쪽이 무너졌다. 'general' 로 밀면 어느 랭킹에도
  안 나오고(표본 342건짜리가 화면에서 사라진다), 억지로 배정하면 없는
  사실을 만든다. 그래서 양쪽을 다 시험한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import build, config                       # noqa: E402


def row(name: str, realm: str = "입시.검정 및 보습", course: str = "",
        **kw) -> dict:
    return {"name": name, "realm_sc_nm": realm,
            "le_crse_list_nm": course, "le_crse_nm": kw.get("crse", ""),
            "id": kw.get("id", name)}


# ── 이름이 가장 정확한 신호다 ────────────────────────────────────
def test_이름의_과목이_시드_과목보다_구체적이다():
    """'시대인재수학스쿨' 이 시드 '시대인재'(국영수과)로 단정돼 과학 랭킹
    3위에 올랐다 — 이름이 수학 전문이라고 말하는데도."""
    assert build._subjects_from_name(row("시대인재수학스쿨학원")) == ["math"]


def test_보습_논술은_과목_선언이_아니다():
    """NEIS 보습학원의 기본 등록값이 '보습·논술' 이고, 거기 '논술' 이 국어
    힌트에 걸려 **827곳이 국어 학원**이 됐다(시대인재·러셀·두각·황소…)."""
    got = build._infer_subjects(row("대치대성학원", course="보습·논술"))
    assert got == [config.UNRANKED_SUBJECT]


def test_과목을_못_정한_학술_학원은_어느_랭킹에도_안_넣는다():
    """'etc' 로 두면 예체능·기타 랭킹에 학술 학원이 섞인다 —
    '대치수능선배2관학원' 이 기타 랭킹에 떴다."""
    got = build._infer_subjects(row("대치수능선배2관학원", course="보습"))
    assert got == [config.UNRANKED_SUBJECT] != ["etc"]


def test_공시_분야가_예체능이면_이름의_과목어보다_우선한다():
    """'아담리즈수학대치센터학원' 은 이름에 수학이 있어도 공시가 '기타(대)'
    라 그대로 둔다. 학원이 그렇게 등록했다."""
    assert build._infer_subjects(row("아담리즈수학대치센터학원", "기타(대)")) == ["etc"]


def test_학술_이름이_예체능_힌트를_이긴다():
    """'수영수학교습소' 가 '수영' 때문에 예체능이 됐다."""
    assert build._infer_subjects(row("수영수학교습소")) == ["math"]


# ── ★ 이 리뷰에서 찾은 것: 과목어가 낱말에 걸쳐 생긴다 ───────────
def test_재수학원은_수학_학원이_아니다():
    """'독학**재수학원**' 에 '수학' 이 들어 있어 재수 학원 19곳이 수학
    학원이 됐다. 부분 문자열은 형태소 경계를 모른다."""
    assert "math" not in build._infer_subjects(row("잇올스파르타독학재수학원",
                                                   course="보습"))
    assert "math" not in build._infer_subjects(row("대치720재수학원",
                                                   course="보습"))


def test_인재수학스쿨은_여전히_수학이다():
    """'시대인**재수학**스쿨' 은 '인재' + '수학' 이다. '재수학원' 이 아니므로
    이음매를 갈라도 수학이 남아야 한다 — 고치다 이쪽을 깨면 안 된다."""
    assert build._subjects_from_name(row("시대인재수학스쿨학원")) == ["math"]
    assert "math" in build._infer_subjects(row("미래영재수학교습소"))
    assert "math" in build._infer_subjects(row("자유자재수학보습학원"))


def test_국어학원은_영어_학원이_아니다():
    """'권미나**국어학원**' 에 '어학' 이 들어 있어 국어 학원 65곳이 영어
    학원으로도 분류됐다."""
    got = build._infer_subjects(row("권미나국어학원"))
    assert got == ["korean"]


def test_진짜_어학원은_영어로_남는다():
    assert "english" in build._infer_subjects(row("우승희영어학원"))
    assert "english" in build._infer_subjects(row("윌로우잉글리쉬외국어학원"))


def test_과학논술은_국어가_아니다():
    """앞말이 뒷말을 한정한다. '과학논술' 은 과학 글쓰기이지 국어 논술이 아니다."""
    assert build._infer_subjects(row("주광호샘네모과학논술교습소")) == ["science"]
    assert build._infer_subjects(row("김정훈수리논술교습소")) == ["math"]


# ── 학년 구간 ────────────────────────────────────────────────────
def test_빈_구간은_모든_구간에_단계를_붙인다():
    """★ 가장 크게 샜던 곳. 앱의 필터는 빈 구간을 '한정되지 않음' 으로
    읽는데 _auto_stages 는 '해당 구간 없음' 으로 읽어 단계를 하나도 안
    붙였다. 등록부 6,092곳 중 4,771곳(78%)이 여기 해당했다."""
    stages, _ = build._auto_stages({"subjects": ["math"], "grade_bands": [],
                                    "name": "가나수학학원"})
    assert stages, "빈 grade_bands 는 '아무 구간도 아님' 이 아니다"


def test_단서가_없으면_대표_단계_하나에만_붙인다():
    """단서 없는 학원을 해시로 흩뿌리던 것을 없앴다 — 실명 사업자를 근거
    없이 '영재고 대비 학원' 이라고 적은 셈이었다(3,000건+)."""
    stages, basis = build._auto_stages(
        {"subjects": ["math"], "grade_bands": ["elem_high"], "name": "가나수학학원"})
    assert len(stages) == 1
    assert basis[stages[0]] == "inferred"


def test_대표_단계는_가장_넓은_곳이지_가장_높은_곳이_아니다():
    """초4~6 수학의 대표가 '경시·심화' 라 단서 없는 941곳이 경시 학원이
    됐다(잠실 경시 목록에 '청진컴퓨터교습소' 가 있었다)."""
    assert build._STAGE_DEFAULT[("math", "elem_high")] == "math_el_basic"
    assert build._STAGE_DEFAULT[("science", "elem_high")] == "sci_el_lab"


def test_단서가_있으면_그_단계로_좁히고_근거를_남긴다():
    stages, basis = build._auto_stages(
        {"subjects": ["math"], "grade_bands": ["elem_high"],
         "name": "가나올림피아드수학학원"})
    assert "math_el_competition" in stages
    assert basis["math_el_competition"] == "hinted"


# ── 성인 직업·전문 학원 ──────────────────────────────────────────
def test_성인_직업_학원은_등록부에서_뺀다():
    """'반포 기타 고등' 목록이 성인 학원으로 채워졌다."""
    assert config.is_vocational(row("김영편입학원", "종합(대)")) is True
    assert config.is_vocational(row("스카이항공승무원학원", "기타(대)")) is True


def test_뷰티풀마인드는_미용학원이_아니다():
    """'뷰티' 를 낱말 목록에 넣으면 뷰티풀마인드수학학원이 사라진다.
    낱말 하나 차이로 멀쩡한 학원이 없어진다."""
    assert config.is_vocational(row("뷰티풀마인드수학학원")) is False
