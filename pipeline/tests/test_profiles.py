"""학원 프로필 — 인용 검증이 이 모듈의 존재 이유다.

모델이 무엇을 내놓든, 발췌에 글자 그대로 없는 인용은 버려지고, 서로 다른 글
2건이 받치지 않는 절은 비고, 어휘 밖의 등급은 절을 통째로 죽인다. 여기 있는
것이 통과하지 못하면 지어낸 문장이 화면에 나갈 수 있는 것이다.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, profiles  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "profile_sample.json"


def _m(h: str, title: str, snippet: str, cred: float = 0.8, **kw) -> dict:
    return {"url_hash": h, "source_url": f"https://cafe.naver.com/x/{h}",
            "title": title, "snippet": snippet, "credibility": cred,
            "substance": 2, "posted_at": kw.get("posted_at"),
            "is_excluded": kw.get("excluded", False), "academy_key": "A"}


CANDS = analyze.name_candidates({"name": "가나영어학원"})
ROWS = [
    _m("h1", "가나영어학원 레테 후기", "가나영어학원 문제는 어렵지 않은데 라이팅 컷이 높아서 떨어졌어요. 숙제가 날마다 달라서 어떤 날은 두 시간."),
    _m("h2", "초2 가나영어 고민", "가나영어 레테 합격이 문제 난이도랑은 별개더라구요. 양은 많은데 애가 재밌어해서 부담이 덜해요."),
    _m("h3", "가나영어학원 커리", "가나영어학원은 자체교재로 주제별로 리딩 라이팅을 같이 해요. 노블 한 권을 정독하는 게 여기 특징."),
    _m("h4", "가나영어 반 배정", "가나영어 반마다 선생님 편차가 커서 꼭 확인하세요. 책 좋아하고 발표 좋아하는 아이면 잘 맞아요.", cred=0.6),
]
SELF = {"text": "가나영어학원 소개. 셔틀은 운행하지 않습니다. 대상 초1~초6.",
        "url": "https://www.gangmom.kr/institute/abc", "url_hash": "s1"}


def _exs():
    return profiles.excerpts(profiles.pick(ROWS), CANDS, SELF)


def _model_output(**over) -> dict:
    base = {
        "levelTest": {"band": "S", "hard": "컷·라이팅", "note": "컷이 어렵다는 평",
                      "quotes": [{"ref": 1, "quote": "라이팅 컷이 높아서 떨어졌어요"},
                                 {"ref": 2, "quote": "레테 합격이 문제 난이도랑은 별개더라구요"}]},
        "homework": {"load": "중상", "note": "편차가 크다",
                     "quotes": [{"ref": 1, "quote": "숙제가 날마다 달라서 어떤 날은 두 시간"},
                                {"ref": 2, "quote": "양은 많은데 애가 재밌어해서"}]},
        "curriculum": {"note": "자체교재 · 노블 정독",
                       "quotes": [{"ref": 3, "quote": "자체교재로 주제별로 리딩 라이팅을 같이"},
                                  {"ref": 3, "quote": "노블 한 권을 정독하는 게 여기 특징"}]},
        "fit": {"goodFor": ["책 좋아하고 발표 좋아하는 아이"], "caution": ["반·교사차 확인"],
                "quotes": [{"ref": 4, "quote": "책 좋아하고 발표 좋아하는 아이면 잘 맞아요"},
                           {"ref": 4, "quote": "반마다 선생님 편차가 커서"}]},
        "ops": {"note": "셔틀 없음", "shuttle": False,
                "quotes": [{"ref": "S1", "quote": "셔틀은 운행하지 않습니다"}]},
    }
    base.update(over)
    return base


def test_발췌는_이름_곁을_번호와_함께_자르고_자기_서술은_S1이다():
    exs = _exs()
    assert [e["ref"] for e in exs] == ["1", "2", "3", "4", "S1"]
    assert all("가나영어" in e["text"] for e in exs[:4])
    assert exs[-1]["kind"] == "self"


def test_인용은_발췌에_글자_그대로_있어야_한다_띄어쓰기는_무시():
    exs = _exs()
    out = profiles.verify(_model_output(
        levelTest={"band": "S", "hard": "컷", "note": "n",
                   "quotes": [{"ref": 1, "quote": "라이팅컷이 높아서 떨어졌어요"},   # 띄어쓰기만 다름 → 통과
                              {"ref": 2, "quote": "레테가 아주 쉬웠어요"}]}),        # 지어냄 → 탈락
        exs)
    assert out["levelTest"] is None          # 검증 통과 1건뿐 → 문턱(2) 미달
    assert out["homework"]["load"] == "중상"


def test_서로_다른_글_2건이_받쳐야_절이_나간다():
    exs = _exs()
    out = profiles.verify(_model_output(
        curriculum={"note": "n", "quotes": [{"ref": 3, "quote": "자체교재로 주제별로"},
                                           {"ref": 3, "quote": "노블 한 권을 정독"}]}), exs)
    assert out["curriculum"] is None         # 같은 글 두 인용은 한 건이다
    out2 = profiles.verify(_model_output(
        curriculum={"note": "n", "quotes": [{"ref": 3, "quote": "자체교재로 주제별로"},
                                           {"ref": 1, "quote": "숙제가 날마다 달라서"}]}), exs)
    assert out2["curriculum"] is not None


def test_어휘_밖_등급은_절을_통째로_버린다():
    exs = _exs()
    out = profiles.verify(_model_output(
        levelTest={"band": "SS", "hard": "컷", "note": "n",
                   "quotes": [{"ref": 1, "quote": "라이팅 컷이 높아서"}, {"ref": 2, "quote": "레테 합격이"}]},
        homework={"load": "매우많음", "note": "n",
                  "quotes": [{"ref": 1, "quote": "숙제가 날마다"}, {"ref": 2, "quote": "양은 많은데"}]}), exs)
    assert out["levelTest"] is None and out["homework"] is None


def test_자기_서술만으로는_레테_숙제_적합을_만들지_않는다():
    exs = _exs()
    out = profiles.verify(_model_output(
        homework={"load": "중", "note": "n",
                  "quotes": [{"ref": "S1", "quote": "셔틀은 운행하지 않습니다"},
                             {"ref": "S1", "quote": "대상 초1~초6"}]}), exs)
    assert out["homework"] is None
    assert out["ops"]["shuttle"] is False and out["ops"]["quotes"][0]["kind"] == "self"


def test_전화번호가_든_인용과_120자_넘는_인용은_버린다():
    rows = ROWS + [_m("h5", "가나영어 상담", "가나영어 상담은 010-1234-5678 로 주세요. " + "아주 " * 60 + "길다")]
    exs = profiles.excerpts(profiles.pick(rows), CANDS)
    got = profiles._verify_quotes([{"ref": 5, "quote": "상담은 010-1234-5678 로 주세요"},
                                   {"ref": 5, "quote": "아주 " * 40}], exs, True)
    assert got == []


def test_전부_비면_None_이고_한_줄_요약은_어휘값만_쓴다():
    exs = _exs()
    assert profiles.verify({"levelTest": {"band": "S", "quotes": []}}, exs) is None
    p = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert profiles.one_liner(p) == "레테 S · 숙제 중상 · 주제 중심 자체교재로 리딩"
    assert profiles.one_liner({"levelTest": None, "homework": None, "curriculum": None}) is None


def test_캐시는_근거가_20퍼센트_넘게_바뀌거나_30일_지나야_다시_만든다():
    entry = {"version": profiles.PROMPT_VERSION, "generated_at": "2026-09-01",
             "hashes": [f"h{i}" for i in range(10)]}
    today = date(2026, 9, 10)
    assert not profiles._stale(entry, {f"h{i}" for i in range(10)}, today)
    assert not profiles._stale(entry, {f"h{i}" for i in range(1, 11)}, today)   # 2/11 바뀜
    assert profiles._stale(entry, {f"h{i}" for i in range(3, 13)}, today)       # 6/13 바뀜
    assert profiles._stale(entry, {f"h{i}" for i in range(10)}, date(2026, 10, 2))
    assert profiles._stale({**entry, "version": 0}, {f"h{i}" for i in range(10)}, today)


def test_collect_은_표본_문턱_아래는_만들지_않고_캐시만_돌려준다(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "CACHE", tmp_path / "profiles.json")
    monkeypatch.setattr(profiles, "MIN_SAMPLE", 3)
    calls = []
    monkeypatch.setattr(profiles, "_run", lambda todo, names, cache, today: calls.append([t[0] for t in todo]))
    monkeypatch.setattr(profiles.summarize, "HAS_KEY", True)
    acs = [{"id": "A", "name": "가나영어학원"}, {"id": "B", "name": "다라수학학원"}]
    by_key = {"A": ROWS, "B": ROWS[:2]}
    out = profiles.collect(acs, by_key, {"A": CANDS, "B": set()}, live=True)
    assert calls == [["A"]] and out == {}
    # 캐시가 있으면 live=False 여도 그대로 나간다
    (tmp_path / "profiles.json").write_text(json.dumps({"A": {
        "version": profiles.PROMPT_VERSION, "generated_at": "2026-09-17",
        "model": "m", "hashes": ["h1", "h2", "h3", "h4", "s1"], "sample": 5, "sources": 4,
        "result": profiles.verify(_model_output(), _exs())}}), encoding="utf-8")
    out = profiles.collect(acs, by_key, {"A": CANDS, "B": set()}, live=False)
    assert out["A"]["oneLiner"].startswith("레테 S") and out["A"]["sources"] == 4
    assert "B" not in out
