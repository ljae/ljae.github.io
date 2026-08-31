"""근거 게이트 회귀 테스트 — 관련성·지점·일상어 이름.

CLAUDE.md 에 사고 기록은 자세한데 **시험이 없었다.** 문서는 다음 사람이
같은 실수를 하는 것을 막아 주지 못한다. 여기 있는 것은 전부 실제로
신고받았거나 실측에서 드러난 오분류다. 고치기 전에는 실패한다.

실행: .venv/bin/python -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, branches                  # noqa: E402


def post(title: str, snippet: str = "", **kw) -> dict:
    return {
        "url_hash": kw.get("url_hash", title[:12] or "h"),
        "source": "naver_cafe",
        "source_url": kw.get("url", "https://cafe.naver.com/x/1"),
        "title": title,
        "snippet": snippet,
        "posted_at": None,
        "academy_key": kw.get("academy_key", "A"),
        "region_id": kw.get("region_id", "daechi"),
    }


def cands(*names: str) -> set[str]:
    return {analyze._norm(n) for n in names}


# ── 관련성 게이트 ────────────────────────────────────────────────
def test_학원명이_본문에_없으면_근거가_아니다():
    """실측: 수집분의 68%가 그랬다. 가중치를 낮추는 정도로는 부족하다."""
    m = post("대치동 입시 설명회 후기", "요즘 학원가 분위기가 어떤지 궁금해요")
    assert analyze.is_relevant(m, cands("지엘피아카데미학원")) is False


def test_업종어를_뗀_이름으로도_걸린다():
    """사람들은 '지엘피아카데미학원' 이라고 쓰지 않고 '지엘피' 라고 쓴다.

    후보에 알맹이를 안 넣으면 그 글이 **다른 학원 차지**가 된다 —
    '대치 빅3의 프로그램! 피아이 해빛나인 지엘피' 가 피아이 근거로 잡혔다.
    """
    c = analyze.name_candidates({"name": "지엘피아카데미학원"})
    assert "지엘피" in c
    m = post("지엘피 레벨테스트 후기", "지엘피 다녀왔어요. 원장님 상담 친절")
    assert analyze.is_relevant(m, c) is True


def test_여러_학원을_늘어놓은_글은_곁다리가_아니다():
    """제목이 나열이고 내 이름은 제목에 없으면 그 글의 주인공이 아니다."""
    rivals = cands("해빛나인", "지엘피", "청담어학원", "에이프릴")
    m = post("대치 빅3의 프로그램! 해빛나인 지엘피 비교",
             "피아이도 잠깐 봤는데 해빛나인이 낫더라구요")
    assert analyze.is_relevant(m, cands("피아이어학원"), False, rivals) is False


def test_내_이름이_제목에_있으면_비교글이어도_내_글이다():
    """'대치 깊은생각 레벨테스트 후기' 는 다른 학원이 함께 나와도 이 학원 글이다."""
    rivals = cands("해빛나인", "지엘피", "청담어학원")
    m = post("대치 깊은생각 레벨테스트 후기",
             "청담어학원이랑 고민하다 깊은생각으로 정했어요. 깊은생각 레테 어려웠어요")
    assert analyze.is_relevant(m, cands("깊은생각"), False, rivals) is True


# ── 일상어 이름 ──────────────────────────────────────────────────
def test_일상어_이름은_전체가_일상어일_때만():
    """부분 일치로 보면 '생각하는황소' 까지 걸려 정상 근거가 사라진다."""
    assert analyze.is_generic_name("책읽기교습소") is True
    assert analyze.is_generic_name("대치책읽기") is True
    assert analyze.is_generic_name("생각하는황소") is False
    assert analyze.is_generic_name("깊은생각") is False


def test_레벨테스트가_테스트학원의_근거가_되지_않는다():
    """실측: 캐시 5만 글에서 '테스트' 1,815건 대 '테스트학원' 1건.

    표본 201건이 전부 기파랑·에이프릴의 **레벨테스트** 후기였다.
    같은 종류로 '새로운'·'피아노'·'로드맵'·'포인트'·'갈무리'·'음악' 을
    함께 넣었다 — 근거 글을 하나씩 열어 확인했다.
    """
    for name in ("테스트학원", "새로운학원", "잠실피아노학원",
                 "목동로드맵학원", "포인트학원", "갈무리학원", "서울음악학원"):
        assert analyze.is_generic_name(name) is True, name

    # 이름 안에 들어 있을 뿐인 곳은 걸리지 않는다 — 부분 일치가 아니다.
    assert analyze.is_generic_name("피아노포르테음악학원") is False
    assert analyze.is_generic_name("뉴포인트영어학원") is False


def test_일상어_이름은_학원_표지를_요구한다():
    """'아이 책읽기 습관' 같은 육아 글이 전부 근거로 잡혔다(382건 중 36%)."""
    parenting = post("아이 책읽기 습관 들이기", "매일 밤 책읽기를 함께 합니다")
    assert analyze.is_relevant(parenting, cands("책읽기"), generic=True) is False

    real = post("책읽기 레벨테스트 후기", "책읽기 원장님 상담 받고 등록했어요")
    assert analyze.is_relevant(real, cands("책읽기"), generic=True) is True


def test_제목의_주인공이_다른_학원이면_일상어_이름은_버린다():
    """제보: '기파랑 레벨테스트를 치고' 글이 본문의 '책읽기를 좋아하고'
    때문에 책읽기 학원 근거가 됐다."""
    m = post("기파랑 레벨테스트를 치고 왔습니다",
             "우리 아이가 책읽기를 좋아하고 원장님도 친절하셨어요")
    assert analyze.is_relevant(m, cands("책읽기"), True, cands("기파랑")) is False


# ── 과목·학급은 이름 근처에서 하나만 ─────────────────────────────
def test_과목은_이름에_가장_가까운_것_하나만():
    """집합으로 두면 같은 글이 수학 근거이자 과학 근거가 된다
    (실측: 시대인재 379건 중 124건 중복 계산)."""
    text = "시대인재 수학 후기입니다. 그리고 대치동 과학 학원들 이야기도 들었어요"
    got = analyze.subject_near_one(text, cands("시대인재"))
    assert got == "math"


def test_멀리_있는_과목어는_그_학원_이야기가_아니다():
    """'대치동 부동산 가격형성요인' 이 과학 근거가 됐다."""
    text = ("김태호과학학원 다녀왔어요. " + "가" * 80 + " 그리고 수학 이야기")
    assert analyze.subject_near_one(text, cands("김태호과학학원")) == "science"


def test_구간을_못_정하는_말은_어느_쪽으로도_안_넘긴다():
    """'초등' 은 저·고학년 어느 쪽인지 말하지 않는다. 반씩 나누면 둘 다 틀린다."""
    assert analyze.band_near_one("초등 대상 학원이에요", cands("가나")) is None
    assert analyze.band_near_one("가나 초3 반 후기", cands("가나")) == "elem_low"


# ── 지점 게이트 ──────────────────────────────────────────────────
ACADEMIES = [
    {"id": "D", "name": "대치정상어학원", "region_id": "daechi",
     "brand": "정상어학원", "dong": "대치동"},
    {"id": "M", "name": "목동정상어학원", "region_id": "mokdong",
     "brand": "정상어학원", "dong": "목동"},
]
CANDS = {a["id"]: analyze.name_candidates(a) for a in ACADEMIES}
GENERIC = {a["id"]: False for a in ACADEMIES}


def _apply(mentions):
    return branches.apply(mentions, ACADEMIES, CANDS, GENERIC, set())


def test_제목의_타지역이_우선한다():
    """본문의 지역명은 대개 **남의 상호**다. '세종 엄마표영어' 글이
    본문의 '대치M수학' 때문에 대치 근거가 됐다."""
    m = post("세종 엄마표영어 정리", "대치M수학 이야기도 들었고 정상어학원도 봤어요",
             academy_key="D")
    kept, stats = _apply([m])
    assert kept == []
    assert stats["other_region"] == 1


def test_브랜드에_박힌_지역명은_지역이_아니다():
    """'[송도 논술 학원] 대치메이드학원 송도점' 은 송도 글이다.
    제목에 우리 권역 말이 함께 있어도 권역 밖이 있으면 버린다."""
    m = post("[송도 논술 학원] 대치 정상어학원 송도점 후기", "", academy_key="D")
    kept, _ = _apply([m])
    assert kept == []


def test_지역을_밝힌_글은_그_권역_지점의_근거로_옮겨진다():
    """★ 버리기만 하면 진짜 주인도 잃는다. '목동 정상어학원' 글이 대치
    지점에서 걸렸다면 대치 근거는 아니지만 **목동 지점 근거는 맞다.**"""
    m = post("목동 정상어학원 레테 후기", "정상어학원 다녀왔어요", academy_key="D")
    kept, stats = _apply([m])
    assert [k["academy_key"] for k in kept] == ["M"]
    assert kept[0]["branch_basis"] == "region"
    assert stats["rehomed"] == 1


def test_지역_불명은_형제_지점_전부에_붙고_그렇게_표시된다():
    """한 곳에 몰아주면 추측이고, 버리면 브랜드 근거가 사라진다.
    '지점 불명 · 브랜드 공통' 이라 **적어야** 중복 신고가 안 들어온다."""
    m = post("정상어학원 레벨테스트 후기", "정상어학원 레테 봤어요", academy_key="D")
    kept, stats = _apply([m])
    assert sorted(k["academy_key"] for k in kept) == ["D", "M"]
    assert all(k["branch_basis"] == "brand" for k in kept)
    assert stats["shared"] == 1


def test_구_이름은_변별어가_못_된다():
    """반포동·방배동이 모두 서초구다. '서초 시매쓰' 를 방배점 것으로만
    치면 반포점 근거가 통째로 날아간다(실측 135 → 62건)."""
    assert "서초" in branches.BROAD_WORDS
    sibs = [{"id": "B", "name": "반포시매쓰학원", "region_id": "banpo",
             "dong": "반포동"},
            {"id": "V", "name": "시매쓰학원", "region_id": "banpo",
             "dong": "서초동"}]
    assert "서초" not in branches.locality_words(sibs[1])
    assert "반포" in branches.locality_words(sibs[0])
