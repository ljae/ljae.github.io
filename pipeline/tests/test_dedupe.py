"""중복 통합 회귀 테스트.

'학원이 중복으로 보인다' 는 증상 하나에 원인이 셋이고(CLAUDE.md), 고칠
때마다 반대쪽이 무너졌다. 여기 있는 것은 전부 실제로 묶였거나 안 묶여서
신고받은 짝이다.

★ 통합은 **양쪽으로** 틀릴 수 있다. 안 묶이면 한 학원이 다섯 줄로 뜨고,
  잘못 묶이면 남남이 한 학원이 된다. 뒤쪽이 더 나쁘다 — 남의 후기가
  내 점수가 되기 때문이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import dedupe                              # noqa: E402


def rec(name: str, addr: str, aid: str = "", **kw) -> dict:
    return {
        "id": aid or name,
        "name": name,
        "road_address": addr,
        "region_id": kw.get("region_id", "mokdong"),
        "tofor_smtot": kw.get("cap", 100),
        "estbl_ymd": kw.get("estbl", "2010-01-01"),
    }


def merged_names(rows: list[dict]) -> list[set[str]]:
    out, _ = dedupe.apply(rows)
    return [set(m.get("merged_names") or [m["name"]]) for m in out]


def grouped(rows: list[dict], a: str, b: str) -> bool:
    """a 와 b 가 같은 묶음에 들었는가."""
    return any({a, b} <= g for g in merged_names(rows))


# ── 묶여야 하는 것 ───────────────────────────────────────────────
def test_같은_주소의_관은_한_학원이다():
    """'CMS 대치' 가 목록에 5번 떴다. NEIS 는 관·과정 단위로 등록한다."""
    rows = [rec("씨엠에스영재1관학원", "서울 강남구 도곡로 1"),
            rec("씨엠에스영재3관학원", "서울 강남구 도곡로 1"),
            rec("씨엠에스중등1관학원", "서울 강남구 도곡로 1")]
    assert len(merged_names(rows)) == 1


def test_주소가_달라도_관_표기가_있으면_묶는다():
    """씨앤씨가 20개 주소에 27건 등록돼 화면에 다섯 줄로 떴다."""
    rows = [rec("씨앤씨3관학원", "서울 양천구 목동동로 55"),
            rec("씨앤씨5관학원", "서울 양천구 오목로 286")]
    assert len(merged_names(rows)) == 1


def test_어학원_별관이_본관과_이어진다():
    """'아이엘이(별관)어학원' 의 hall_key 가 '아이엘이어' 로 남아 안 이어졌다.
    업종어를 **복합형부터** 떼야 '어학원' 이 떨어진다."""
    assert dedupe.hall_key("아이엘이(별관)어학원") == dedupe.hall_key("아이엘이학원")


# ── 묶이면 안 되는 것 ────────────────────────────────────────────
def test_과목이_다르면_같은_브랜드여도_다른_학원이다():
    """★ 이 리뷰에서 찾은 버그. _SUFFIX_STRONG 이 '수학학원' 을 업종어로
    알고 통째로 떼서, '대치정상수학학원' 과 '대치1관정상어학원' 이 둘 다
    '대치정상' 이 되어 **영어 학원과 수학 학원이 한 학원**이 됐다.

    과목은 같은 브랜드의 두 학원을 **가르는 정보**다. 지우면 안 된다."""
    assert dedupe.hall_key("대치정상수학학원") != dedupe.hall_key("대치1관정상어학원")
    rows = [rec("대치1관정상어학원", "서울 강남구 영동대로 227", region_id="daechi"),
            rec("대치정상수학학원", "서울 강남구 영동대로 229", region_id="daechi")]
    assert not grouped(rows, "대치1관정상어학원", "대치정상수학학원")


def test_뉴클리어학원은_뉴클리온과_남남이다():
    """접두 매칭용 _strip_suffix 는 **짧은 것부터** 뗀다. '어학원' 을 먼저
    떼면 '뉴클리' 가 되고, 그건 옆 건물 '뉴클리온' 의 접두사다."""
    assert dedupe.same_academy("뉴클리어학원", "뉴클리온학원") is False


def test_건물_이름으로_묶이지_않는다():
    """'센트럴' 은 건물 이름이었다. 3글자 겹침으로 묶었더니 예설라센트럴원·
    파피루스문해원·기파랑문해원이 한 학원이 됐다."""
    rows = [rec("예설라센트럴원", "서울 양천구 목동서로 349"),
            rec("파피루스문해원", "서울 양천구 목동서로 349"),
            rec("기파랑문해원", "서울 양천구 목동서로 349")]
    assert len(merged_names(rows)) == 3


def test_지역어는_남긴다():
    """약(light) 토큰으로 묶었더니 리드101 도곡·대치·개포가 한 학원이 됐다."""
    assert dedupe.hall_key("리드101대치학원") != dedupe.hall_key("리드101개포학원")


def test_관_표기가_없으면_이름이_같아도_안_묶는다():
    """'피아노교습소(권춘자)' 와 '피아노교습소(김옥선)' 은 원장이 다른 남남이다."""
    rows = [rec("피아노교습소(권춘자)", "서울 양천구 목동로 1"),
            rec("피아노교습소(김옥선)", "서울 양천구 목동로 2")]
    assert len(merged_names(rows)) == 2


# ── 통합체의 이름과 id ───────────────────────────────────────────
def test_대표명에_관_번호를_남기지_않는다():
    """'길벗제2관보습학원' 은 5개 관을 합친 곳의 이름으로 읽히지 않는다."""
    rows = [rec("길벗제2관보습학원", "서울 양천구 목동로 3"),
            rec("길벗제3관보습학원", "서울 양천구 목동로 3")]
    out, _ = dedupe.apply(rows)
    assert "2관" not in out[0]["name"] and "3관" not in out[0]["name"]


def test_대표_id_는_가장_오래된_등록이다():
    """이름순으로 두면 짧은 관이 새로 등록될 때마다 학원 신원이 뒤집힌다.
    id 에는 후기·판정·정정·위키가 전부 매달려 있다."""
    rows = [rec("가나1관학원", "서울 양천구 목동로 4", aid="NEW", estbl="2020-01-01"),
            rec("가나2관학원", "서울 양천구 목동로 4", aid="OLD", estbl="2001-01-01")]
    out, _ = dedupe.apply(rows)
    assert out[0]["id"] == "OLD"
    assert set(out[0]["registration_ids"]) == {"OLD", "NEW"}


def test_대표명이_과하게_깎이면_쓰지_않는다():
    """'책읽기독서논술교습소' 와 '책읽기와글쓰기리딩엠…' 의 공통 접두사
    '책읽기' 는 브랜드가 아니라 일상어다. 그 이름이 곧 검색어가 되어
    온 세상 독서 글이 근거로 딸려 왔다."""
    got = dedupe.representative_name(
        ["책읽기독서논술교습소", "책읽기와글쓰기리딩엠역삼학원"])
    assert got != "책읽기"


def test_정상_축약은_유지된다():
    """CMS·소마처럼 진짜 브랜드 축약까지 잃으면 안 된다."""
    got = dedupe.representative_name(["씨엠에스영재1관학원", "씨엠에스영재3관학원"])
    assert got == "씨엠에스영재"


# ── 통합 시 필드 ─────────────────────────────────────────────────
def test_정원은_합산_개설일은_가장_이른_것():
    rows = [rec("가나1관학원", "서울 양천구 목동로 5", cap=100, estbl="2015-03-01"),
            rec("가나2관학원", "서울 양천구 목동로 5", cap=50, estbl="2009-05-01")]
    out, _ = dedupe.apply(rows)
    assert out[0]["tofor_smtot"] == 150
    assert out[0]["estbl_ymd"] == "2009-05-01"
