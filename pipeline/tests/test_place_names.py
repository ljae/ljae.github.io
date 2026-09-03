"""지역어·업종어만으로 된 이름 — 2026-09-02 신고 '대치학원 후기 매칭 오류'.

'대치학원'(강남구 삼성로 347)이 대치 수학 11위 · 표본 191건이었는데 근거가
'역삼이편한세상 임장후기 #대치학원가'·'대치 학원들은 시험 수준이…' 였다.
두 겹으로 샜다: 지역 접두어를 뗀 후보가 '학원' 이었고, 이름 전체가
'대치 학원(가)' 라는 구(句)와 같았다. 같은 꼴이 채점 대상에 8곳(목동학원
212 · 잠실피아노학원 64 …), 등록부에 162곳이었다.

여기 있는 사례가 다시 통과하면 그 구멍이 되살아난 것이다.

실행: python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze  # noqa: E402


def _cands(name: str, brand: str | None = None, aliases=()) -> set[str]:
    return analyze.name_candidates(
        {"name": name, "brand": brand, "aliases": list(aliases)})


def _n(text: str) -> str:
    return analyze._norm(text)


# ── 알맹이 ────────────────────────────────────────────────────────

def test_지역어_업종어뿐인_이름은_알맹이가_없다():
    for name in ("대치학원", "목동학원", "잠실피아노학원", "서울음악학원",
                 "대치피아노교습소", "피아노교습소", "서울아카데미학원",
                 "고등학원", "대치동영어교습소", "강남미술학원"):
        assert analyze.name_core(name) == "", name
        assert analyze.is_place_name({"name": name}), name


def test_브랜드가_있으면_알맹이가_남는다():
    for name, core in (("곰수학학원", "곰"), ("대치폴리어학원", "폴리"),
                       ("강남대성학원", "대성"), ("종로학원", "종로"),
                       ("시대인재수학스쿨학원", "시대인재"),
                       ("한우리독서토론논술교습소", "한우리"),
                       ("강한대치학원", "강한")):
        assert analyze.name_core(name) == core, (name, analyze.name_core(name))
        assert not analyze.is_place_name({"name": name}), name


# ── 후보 ──────────────────────────────────────────────────────────

def test_지역_접두어를_뗀_형태가_업종어만_남으면_후보가_아니다():
    """'대치학원' → '학원' 이 후보였다. 두 글자라 표지 검사를 받지만 곁에
    '수학'·'다니'·'후기' 만 있으면 통과하니 학원 이야기 전부가 걸렸다."""
    assert _cands("대치학원") == set()
    assert _cands("목동학원") == set()
    assert "수학학원" not in _cands("대치수학학원")
    assert "어학원" not in _cands("잠실어학원")
    assert "동영어" not in _cands("대치동영어교습소")


def test_브랜드_후보는_그대로다():
    assert _cands("곰수학학원") == {"곰수학", "곰수학학원"}
    cand = _cands("대치폴리어학원", "폴리어학원", ["폴리"])
    assert {"폴리", "폴리어학원", "대치폴리어학원"} <= cand
    # 시드·별칭이 알맹이를 주면 지역어 이름이라도 다시 이어진다.
    assert _cands("대치학원", None, ["써머스쿨대치"]) == {"써머스쿨대치"}


def test_위키_별칭이_구_이면_약한_후보로_빠진다():
    weak = analyze.weak_candidates({"학원", "수학학원", "폴리", "정상"})
    assert weak == {"학원", "수학학원", "정상"}, weak


def test_지역어_업종어뿐인_이름은_남의_학원도_못_된다():
    for name in ("서울학원", "대치학원", "대치동영어", "목동영어학원"):
        assert not analyze.rival_eligible(name), name
    assert analyze.rival_eligible("강남대성")
    assert analyze.rival_eligible("강한대치학원")


# ── 게이트 ────────────────────────────────────────────────────────

def test_대치학원의_근거였던_글은_이제_어떤_것도_안_걸린다():
    cand = _cands("대치학원")
    junk = [
        {"title": "역삼이편한세상 임장후기 #대치학원가 + 도성초 + 한티역 역세권",
         "snippet": "강남에서도 학군으로 유명한 역삼동"},
        {"title": "이맥스어학원 레벨테스트 후기 : 5학년 레테 대장정 마지막",
         "snippet": "올해는 대치어학원을 돌면서 테스트를 보았다. 대치 학원들은 시험 수준이"},
        {"title": "역삼동 동부센트레빌 임장후기 도성초 학군·대치 학원가 누리는",
         "snippet": "선릉역 분당선 더블역세권"},
        {"title": "강한대치학원 송파 후기", "snippet": "학원 다녀요 수학 선생님"},
    ]
    for m in junk:
        assert not analyze.is_relevant(m, cand), m["title"]


def test_같은_글이_브랜드_학원에는_여전히_걸린다():
    """이름을 죽인 것이지 게이트를 죽인 게 아니다."""
    cand = _cands("강한대치학원")
    ok = {"title": "강한대치학원 송파 후기", "snippet": "학원 다녀요 수학 선생님"}
    assert analyze.is_relevant(ok, cand)
