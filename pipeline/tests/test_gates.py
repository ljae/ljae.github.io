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

from edutree import analyze, branches, wiki            # noqa: E402


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


def used(name: str, **kw) -> set[str]:
    """build 가 게이트에 실제로 넘기는 후보 집합.

    손으로 후보를 적으면 파이프라인이 쓰지도 않는 표기를 시험하게 된다 —
    `weak_candidates` 가 일상어 낱말('포인트')을 이미 빼고 넘긴다.
    """
    c = analyze.name_candidates({"name": name, **kw})
    return c - analyze.weak_candidates(c)


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
    # '깊은생각' 은 **구 전체가 정확히 일치**하는 경우라 다르다(부분 일치가
    # 아니다). 띄어쓰기를 지우면 '깊은 생각 없이' 와 같아져 '삼시세끼
    # 꼬마김밥 솔직 후기' 가 근거였다(2026-09-02). 학원 표지를 이름 곁에
    # 요구할 뿐이라 진짜 후기('깊은생각 레테 후기')는 그대로 산다.
    assert analyze.is_generic_name("깊은생각") is True
    assert analyze.is_generic_name("깊은생각256학원") is False


def test_레벨테스트가_테스트학원의_근거가_되지_않는다():
    """실측: 캐시 5만 글에서 '테스트' 1,815건 대 '테스트학원' 1건.

    표본 201건이 전부 기파랑·에이프릴의 **레벨테스트** 후기였다.
    같은 종류로 '새로운'·'피아노'·'로드맵'·'포인트'·'갈무리'·'음악' 을
    함께 넣었다 — 근거 글을 하나씩 열어 확인했다.
    """
    # ★ 같은 신고에서 나온 일곱 곳이 **두 종류**로 갈린다. 알맹이가 남으면
    #   그 알맹이가 일상어인 것이고(조건을 더한다), 아무것도 안 남으면
    #   애초에 이름이 아닌 것이다(후보가 비어 표본 0). 뒤쪽이 더 세다.
    for name in ("새로운학원", "목동로드맵학원", "포인트학원", "갈무리학원"):
        assert analyze.is_generic_name(name) is True, name
        assert analyze.name_candidates({"name": name}), name

    for name in ("테스트학원", "잠실피아노학원", "서울음악학원"):
        assert analyze.name_core(name) == "", name
        assert analyze.name_candidates({"name": name}) == set(), name

    # 이름 안에 들어 있을 뿐인 곳은 걸리지 않는다 — 부분 일치가 아니다.
    assert analyze.is_generic_name("피아노포르테음악학원") is False
    assert analyze.is_generic_name("뉴포인트영어학원") is False

    # 지점마다 판정이 갈리지 않는다 — 알맹이는 `name_core` 하나로 구한다.
    assert analyze.is_generic_name("깊은생각목동학원") is True
    assert analyze.is_generic_name("한우리서초독서논술학원") is True
    assert analyze.is_generic_name("생각하는황소") is False


def test_일상어_낱말_일곱_개가_실제로_그_글을_거른다():
    """목록에 낱말을 넣는 것과 **그 글이 실제로 걸리는 것**은 다르다.

    8/31 에 일곱 개를 넣고 `is_generic_name(...) is True` 만 확인했다.
    장치가 무력해도 그 단언은 초록이라, '새로운학원' 은 그 뒤로도
    사흘 동안 순위에 남아 있었다. 여기서는 CLAUDE.md 에 적힌 **그때
    그 글**을 넣고 거부되는지 본다.
    """
    # 낱말 하나로만 걸린 표기는 게이트에 오기 전에 빠진다(`weak_candidates`).
    for name in ("로드맵학원", "갈무리학원", "포인트학원", "새로운학원"):
        assert analyze.weak_candidates(analyze.name_candidates({"name": name})), name

    # 로드맵 121건 — '초2 수학 로드맵 고민'.
    assert analyze.is_relevant(
        post("초2 수학 로드맵 고민이에요", "선행을 어디까지 해야 할까요"),
        used("로드맵학원"), True, frozenset()) is False

    # 갈무리 148건 — 해양수산부 합격수기·게임 모음.
    assert analyze.is_relevant(
        post("해양수산부 합격수기 갈무리", "공부 방법을 갈무리해 둡니다"),
        used("갈무리학원"), True, frozenset()) is False

    # 포인트 160건 — '터닝포인트'. 남의 브랜드 **안에** 내 이름이 들어 있다.
    assert analyze.is_relevant(
        post("터닝포인트 영어학원 레벨테스트 후기", "원장님 상담 받았어요"),
        used("포인트학원"), True, frozenset()) is False

    # 테스트 201건 — '기파랑 레벨테스트 후기'. 이름 자체가 알맹이가 없어
    # 후보가 비고, 후보가 비면 어떤 글도 걸리지 않는다.
    assert analyze.name_candidates({"name": "테스트학원"}) == set()

    # 피아노·음악도 같은 종류다(9/3 실측: 넷 다 표본 0 이 됐다).
    for name in ("잠실피아노학원", "서울음악학원", "대치피아노교습소"):
        assert analyze.name_candidates({"name": name}) == set(), name


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


def test_새로운_학원이라는_구는_새로운학원의_근거가_아니다():
    """9/3 배포 근거 실측(`app/assets/data/academies.json`).

    '새로운 학원' 은 학원 이야기라면 어디에나 나오는 말이라 **표지가 늘
    곁에 있다** — 표지 요구로는 원리적으로 못 막는다. 정규화가 공백을
    지우므로 '새로운 학원' 과 '새로운학원' 이 같은 글자열이 되는 것이
    뿌리다. 붙여 쓴 것만 이름으로 친다.
    """
    used = cands("새로운학원")
    for m in (
        post("초보 강사, 새로운 학원 제안 왔는데 도전해도 될까요?",
             "약 1년 정도 조교 경력을 쌓은 뒤 새로운 학원에서 다시 조교로 근무"),
        post("새로운 학원 오픈 구상의 고민", "고민 상담 ▶ 개인 과외 운영중"),
        post("레벨테스트란?",
             "아이들에게 레벨테스트, 새로운 학원 상담이 엄청난 부담감일 줄은 몰랐어요."),
    ):
        assert analyze.is_relevant(m, used, True, frozenset()) is False, m["title"]

    # 붙여 쓴 진짜 이름은 남는다 (불당동 글은 지역 게이트가 맡는다)
    real = post("목동 새로운학원 레벨테스트 후기", "새로운학원 원장님 상담 받고 등록했어요")
    assert analyze.is_relevant(real, used, True, frozenset()) is True


def test_업종어를_품지_않은_구는_엔진이_못_가른다_위키_몫이다():
    """425 선행과심화학원. 9/3 근거 8건이 전부 공부법 글이었다.

    ★ 여기가 낱말 규칙의 **경계**다. '새로운 학원' 은 몸통과 업종어 사이가
      벌어져 구(句)임이 드러나지만, '선행과 심화' 에는 업종어가 없어
      `trade_seam` 이 볼 자리가 없다. 알맹이('선행과심화')에 붙임을
      요구하면 '깊은 생각' 처럼 **띄어 쓴 진짜 브랜드**가 함께 죽는다
      (9/3 실측: "'깊은 생각' 수학학원 입학테스트 후기" 는 진짜 후기다).

      그래서 엔진은 여기서 멈추고 사람이 위키에 적는다 — 자동으로 조이면
      멀쩡한 학원의 근거가 조용히 사라지는 쪽으로 틀린다.
      `pipeline/wiki/academies/425.md` 의 `unusable: true` 가 그것이다.
    """
    used = cands("선행과심화학원", "선행과심화")
    leak = post("예비중1 수학학원", "중등 때 선행과 심화로... 레벨테스트 있고 정원 초9명",
                academy_key="425")
    assert analyze.is_relevant(leak, used, True, frozenset()) is True, "엔진만으로는 못 가른다"

    # 위키가 닫는다. 이 학원의 글은 통째로 빠져 표본 0 이 된다.
    hint = {"name": "선행과심화학원", "aliases": [], "generic": True,
            "exclude_title": [], "exclude_any": [], "locality": [],
            "unusable": True}
    kept, dropped = wiki.apply_gate([leak], {"425": hint})
    assert dropped == 1 and kept == []


def test_위키가_425_와_새로운학원을_실제로_모으지_않는다():
    """T1 이 적은 frontmatter 가 살아 있는지. 파일이 되돌려지면 여기서 걸린다."""
    hints = wiki.load()
    for aid in ("3000040050", "425"):
        assert hints.get(aid, {}).get("unusable") is True, aid


def test_붙여_쓴_일상어_이름은_로드맵학원처럼_살아남는다():
    """반대쪽을 깨지 않는지. 9/3 실측: 로드맵학원 근거는 전부 붙여 쓴 진짜 후기다."""
    used = cands("로드맵학원", "목동로드맵", "목동로드맵학원")
    m = post("양천구 목동 로드맵학원 후기 - 믿고 다니기 좋은 학원입니다",
             "[ 로드맵학원 전화번호 및 주소 ] 서울 양천구 목동동로 387")
    assert analyze.is_relevant(m, used, True, frozenset()) is True


def test_이름_안의_업종어는_학원_표지가_아니다():
    """'새로운학원' 의 '학원' 이 스스로의 표지가 되어 표지 요구가 무력했다.

    실측(9/3): 강사 구인 글의 이름 자리 바깥 ±25자에는 표지가 하나도 없는데
    게이트를 통과했다. 표지는 **이름 바깥**에 있어야 한다.
    """
    m = post("초보 강사, 새로운학원 제안 왔는데", "대학교 근처로 이사하면서 새로운학원에서 근무")
    assert analyze.is_relevant(m, cands("새로운학원"), True, frozenset()) is False

    ok = post("새로운학원 다닌 지 1년", "원장님이 꼼꼼해요")
    assert analyze.is_relevant(ok, cands("새로운학원"), True, frozenset()) is True

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


def test_목록에_없는_동은_제목에_있으면_남의_동네다():
    """'불당동 새로운 학원'(천안)이 목동 새로운학원의 근거였다(9/3 실측).

    사람이 채우는 `OTHER_REGION_WORDS` 로는 끝이 없다 — 뒤집어서
    **우리 학군의 동이 아니면 남의 동네**로 본다.
    """
    ours = {"대치동", "도곡동", "개포동", "역삼동", "목동", "신정동",
            "반포동", "잠원동", "서초동", "잠실동", "신천동", "방이동"}
    assert analyze.foreign_dong("불당동 새로운 학원", ours, {"새로운학원"}) is True
    assert analyze.foreign_dong("정자동 한국영재교육원", ours, {"한국영재"}) is True
    assert analyze.foreign_dong("서대문구 북가좌동 플라즈마학원 후기", ours,
                                {"플라즈마"}) is True
    assert analyze.foreign_dong("대치동 수학학원 레벨테스트", ours, set()) is False


def test_동으로_끝나는_흔한_말은_동네가_아니다():
    """'운동'·'활동' 은 두 글자라 안 본다. 낱말 속의 '동' 도 마찬가지다."""
    ours = {"목동"}
    for title in ("운동 후 간식 추천", "동아리활동 후기", "아동 심리 상담",
                  "자동 채점 프로그램", "행동 발달 검사"):
        assert analyze.foreign_dong(title, ours, set()) is False, title


def test_이름에_박힌_지역명은_동네가_아니다():
    """'러셀목동'·'대치청담어학학원' 의 그 말은 지역이 아니라 이름이다 —
    '[송도 논술 학원] 대치메이드학원 송도점' 함정의 뒷면이다."""
    ours = {"목동", "대치동"}
    assert analyze.foreign_dong("【수강후기】 러셀목동 수학 강영찬T", ours,
                                {"러셀목동학원"}) is False
    assert analyze.foreign_dong("청담동 영어학원 비교", ours,
                                {"대치청담어학학원", "청담어학"}) is False
    # 이름과 무관한 학원에는 그대로 남의 동네다
    assert analyze.foreign_dong("청담동 영어학원 비교", ours, {"가나학원"}) is True


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
