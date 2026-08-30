"""이름·게이트 회귀 테스트 — 2026-08-29 신고에서 나온 것들.

신고: '대치정상수학학원 은 수학과 영어를 결합했는데 이름이 수학학원이라
대표 이름으로 부적절하다. 진입난이도는 대부분 잘못된 정보다.'

전수로 재 보니 원인이 셋이었고 전부 **조용히 틀리는** 종류였다.

  1. 시드 별칭 `정상` 이 일상어라 '어느 정도가 정상인지'(인테리어 상담),
     '정상적인 면역기능'(건강식품 광고)이 근거가 됐다.
  2. `flat` 이 공백을 지우면서 '8대 기능성' → '8대기능성' 이 되어
     **대기**·웨이팅 사건이 잡혔다.
  3. 대표명이 최단 이름이라, 과목이 다른 관이 묶이면 한 과목이 전체를
     대표했다(영어 표본 337 · 수학 61 인데 이름은 '…수학학원').

실행: python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, claims, dedupe  # noqa: E402


# ── 1. 일상어 별칭 ────────────────────────────────────────────────────

def _cands(name: str, brand: str | None = None, aliases=()) -> set[str]:
    return analyze.name_candidates(
        {"name": name, "brand": brand, "aliases": list(aliases)})


def test_일상어_별칭은_근거가_못_된다():
    cand = _cands("대치정상수학학원", "정상어학원", ["정상", "정상영어"])
    weak = analyze.weak_candidates(cand)
    assert weak == {"정상"}, weak


def test_줄임말_별칭은_그대로_둔다():
    """'소마'·'폴리'는 학부모가 실제로 쓰는 말이다. 길이가 기준이 아니다 —
    이 말로만 걸리는 글이 각각 210·240건이고 대부분 진짜다."""
    for name, brand, alias in (("대치소마사고력수학학원", "소마사고력수학", "소마"),
                               ("대치폴리어학원", "폴리어학원", "폴리")):
        weak = analyze.weak_candidates(_cands(name, brand, [alias]))
        assert weak == set(), (name, weak)


def test_일상어_별칭을_뺀_뒤에도_진짜_글은_걸린다():
    cand = _cands("대치정상수학학원", "정상어학원", ["정상", "정상영어"])
    cand -= analyze.weak_candidates(cand)
    ok = {"title": "정상어학원 대치분원 레벨테스트 후기",
          "snippet": "레테 보고 등록했어요"}
    junk = {"title": "인테리어 금액 상담 어느 정도가 정상인지 어떻게 판단하나요?",
            "snippet": "도배 장판 견적 비교"}
    assert analyze.is_relevant(ok, cand)
    assert not analyze.is_relevant(junk, cand)


def test_학원_표지만으로는_일상어를_못_거른다():
    """왜 별칭을 빼야 했는지 — '금액 상담'의 '상담'이 표지로 통과한다.
    문턱을 높이는 것으로는 안 되고 낱말 자체를 빼야 했다."""
    junk = {"title": "인테리어 금액 상담 어느 정도가 정상인지",
            "snippet": "견적 비교"}
    assert analyze.is_relevant(junk, {"정상"}, generic=True)


# ── 2. 사건 낱말이 원문에서 붙어 있는가 ───────────────────────────────

def _hit(text: str, trig: str) -> bool:
    flat, idx = claims._norm_map(text)
    t = "".join(c.lower() for c in trig if c.isalnum())
    i = flat.find(t)
    assert i >= 0, (text, trig)
    return claims._contiguous(idx, i, len(t), trig)


def test_공백을_넘어_생긴_낱말은_사건이_아니다():
    # '과학적인 8대 기능성' → flat '…8대기능성…' → '대기'
    assert not _hit("과학적인 8대 기능성 영양설계", "대기")


def test_진짜_사건은_그대로_잡힌다():
    assert _hit("대기가 길다고 하네요", "대기")
    assert _hit("이번 기수는 마감됐대요", "마감")


def test_공백을_품은_표기는_그대로_찾는다():
    """'자리 없'은 붙여 찾는 것이 목적이다. 연속성 검사를 걸면 안 된다."""
    assert _hit("자리 없어요", "자리 없")


# ── 3. 대표명 ────────────────────────────────────────────────────────

def _rep(names: list[str]) -> str:
    """merge() 의 이름 결정 부분과 같은 순서로 — names[0] 이 최고참."""
    rep = dedupe.representative_name(names)
    if dedupe.has_hall_mark(rep):
        bare = dedupe._strip_hall_mark(rep)
        same = [n for n in names if not dedupe.has_hall_mark(n) and n == bare]
        rep = same[0] if same else bare
    return rep


def test_과목이_다른_관이_묶이면_신원을_따른다():
    # 신고 사례. 영어(표본 337)가 수학(61) 이름으로 나가 있었다.
    assert _rep(["대치1관정상어학원", "대치정상수학학원"]) == "대치정상어학원"


def test_공통_접두사가_있으면_그것이_브랜드다():
    # 최고참 이름이 길다고 접두사를 버리면 '메이플' 이
    # '메이플리틀쇼팽음악학원' 으로 퇴화한다. 실측에서 이렇게 틀렸다.
    assert _rep(["메이플리틀쇼팽음악학원", "메이플자이비발디음악학원",
                 "메이플수학교습소"]) == "메이플"


def test_관_없는_이름이_있으면_그것을_쓴다():
    assert _rep(["길벗제2관보습학원", "길벗보습학원"]) == "길벗보습학원"


def test_관_번호만_있으면_번호를_뗀다():
    assert _rep(["길벗제2관보습학원", "길벗제3관보습학원"]) == "길벗보습학원"
