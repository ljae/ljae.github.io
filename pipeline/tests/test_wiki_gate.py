"""위키 제외 게이트 — 조이는 것과 **모으지 않는 것**은 다른 층이다.

'클라우드'(대치) 를 쫓다가 알게 된 것. 낱말을 빼는 방식이 통하는 이름과
안 통하는 이름이 다르다.

    새로운·테스트   일상어 문장       generic 으로 조인다
    피드백         같은 동네 남의 학원  generic 까지. 낱말을 빼면 진짜도 죽는다
    클라우드        IT 세계 전체       조여도 끝나지 않는다 → 모으지 않는다

실측: '클라우드' 는 붙은 글 227건 중 **제목에 이름이 든 22건마저** 전부
IT·국비 취업 글이었다. 넓은 제외어로 191 → 31 까지 줄였지만 남은 31건은
주식·유학원·육아 글이라 공통 낱말이 없었다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import wiki  # noqa: E402


def hint(**kw):
    base = {"name": "가나", "aliases": [], "generic": False,
            "exclude_title": [], "exclude_any": [], "locality": [],
            "unusable": False, "excluded": False, "moved_to": None}
    base.update(kw)
    return base


def m(aid, title, snippet=""):
    return {"academy_key": aid, "title": title, "snippet": snippet}


def test_제외어가_없으면_아무것도_안_거른다():
    rows = [m("a1", "가나학원 후기")]
    out, dropped = wiki.apply_gate(rows, {"a1": hint()})
    assert dropped == 0 and out == rows


def test_exclude_any_는_제목과_본문_어디든_본다():
    rows = [m("a1", "가나학원 후기"),
            m("a1", "아이폰 복구 후기", "가나 어쩌고"),
            m("a1", "정상 후기", "아이폰 이야기")]
    out, dropped = wiki.apply_gate(rows, {"a1": hint(exclude_any=["아이폰"])})
    assert dropped == 2 and len(out) == 1


def test_unusable_은_그_학원_글을_통째로_뺀다():
    """낱말로 끝나지 않는 이름이 있다. 그때는 조이는 것이 아니라 **모으지
    않는 것**이 맞다 — 표본 0 이 되어 점수도 등수도 없어지는데, 그것이
    '아직 아무것도 모른다' 는 정직한 상태다."""
    rows = [m("a1", "무슨 글이든"), m("a1", "또 다른 글"), m("a2", "남의 글")]
    out, dropped = wiki.apply_gate(rows, {"a1": hint(unusable=True)})
    assert dropped == 2
    assert [r["academy_key"] for r in out] == ["a2"], "남의 학원은 안 건드린다"


def test_unusable_만_있어도_게이트가_돈다():
    """제외어가 하나도 없으면 일찍 빠져나가던 최적화에 걸리면 안 된다."""
    rows = [m("a1", "글")]
    _, dropped = wiki.apply_gate(rows, {"a1": hint(unusable=True)})
    assert dropped == 1


# ── 답한 경고는 다시 묻지 않는다 ──────────────────────────────────
#
# 9/3 실측: 매 실행 위키 경고 12줄이 찍혔고 그중 11줄은 답이 정해진 것
# (제외 분류·폐업·이관 완료)이었다. 답한 경고를 계속 찍으면 그 옆의
# 진짜 경고가 함께 안 읽힌다.
def test_제외_분류로_확인한_페이지는_다시_경고하지_않는다():
    acs = [{"id": "a1", "name": "가나학원", "aliases": [], "registration_ids": []}]
    assert wiki.sanity({"zz": hint(name="변리사스쿨")}, acs), "확인 전에는 경고한다"
    assert wiki.sanity({"zz": hint(name="변리사스쿨", excluded=True)}, acs) == []


def test_이관을_마친_페이지는_다시_경고하지_않는다():
    acs = [{"id": "a1", "name": "아이엘이", "aliases": [],
            "registration_ids": ["a1", "old"]}]
    warned = wiki.sanity({"old": hint(name="아이엘이별관")}, acs)
    assert warned and "a1" in warned[0], "이관 전에는 어디로 갈지 알려 준다"

    hints = {"old": hint(name="아이엘이별관", moved_to="a1")}
    assert wiki.sanity(hints, acs) == []
    # 경고를 멈춰도 힌트는 대표 id 로 넘어간다 — 별칭이 죽으면 안 된다.
    assert "a1" in hints
