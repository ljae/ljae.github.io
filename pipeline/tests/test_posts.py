"""글 노드 무효화 회귀 테스트.

이 구조의 약속은 하나다: **글 페이지 한 장을 고치면 그 글의 영향이 전부
사라진다.** 그 약속이 지켜지는지를 여기서 증명한다.

특히 마지막 테스트가 핵심이다 — 글 하나를 반려했을 때 그 학원의 표본만
줄어드는 것이 아니라 **코호트 평균과 등수까지** 다시 계산되어야 한다.
부분 삭제였다면 '어디까지 지워야 하나'를 사람이 판단해야 하지만, 매 실행
전부를 다시 짓는 구조라 판단할 것이 없다. 그 성질이 깨지지 않았는지 본다.

실행: python3 -m pytest pipeline/tests -q
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import posts, scoring                     # noqa: E402


ACADEMIES = [
    {"id": "A1", "name": "가나수학학원", "region_id": "daechi",
     "subjects": ["math"], "grade_bands": ["middle"]},
    {"id": "A2", "name": "다라수학학원", "region_id": "daechi",
     "subjects": ["math"], "grade_bands": ["middle"]},
]


def mention(url_hash: str, academy: str, *, sentiment: float = 0.5,
            title: str = "후기") -> dict:
    return {
        "url_hash": url_hash,
        "source": "naver_cafe",
        "source_url": f"https://cafe.naver.com/x/{url_hash}",
        "title": title,
        "snippet": "레벨테스트 보고 왔습니다",
        "posted_at": "2026-06-01",
        "author_hash": "au" + url_hash,
        "academy_key": academy,
        "academy_name": "가나수학학원" if academy == "A1" else "다라수학학원",
        "region_id": "daechi",
        "sentiment": sentiment,
        "credibility": 0.7,
        "spam_score": 0.0,
        "is_excluded": False,
        "subjects": ["math"],
        "selectivity": {},
        "class_tier_signals": {},
        "branch_basis": "direct",
    }


@pytest.fixture()
def wiki(tmp_path, monkeypatch):
    """글 페이지 디렉터리를 임시로 옮긴다. 진짜 위키를 건드리지 않는다."""
    monkeypatch.setattr(posts, "POST_DIR", tmp_path / "posts")
    posts.POST_DIR.mkdir(parents=True)
    return posts.POST_DIR


def write(wiki: Path, url_hash: str, **fields) -> None:
    front = "\n".join(f"{k}: {v}" for k, v in fields.items())
    (wiki / f"{url_hash}.md").write_text(
        f'---\nurl_hash: "{url_hash}"\n{front}\n---\n# 글\n', encoding="utf-8")


# ── 읽기 ────────────────────────────────────────────────────────
def test_골격만_있는_페이지는_게이트에_실리지_않는다(wiki):
    # 9천 장 대부분은 판단이 안 적힌 골격이다. 그것들이 매 실행 게이트를
    # 지나면 비용만 들고 하는 일이 없다.
    write(wiki, "h1", verdict="", reject_reason="", stale_after="")
    assert posts.load() == {}


def test_판단이_적힌_페이지만_읽는다(wiki):
    write(wiki, "h1", verdict="rejected", reject_reason="동명이인")
    got = posts.load()
    assert got["h1"]["verdict"] == "rejected"
    assert got["h1"]["reason"] == "동명이인"


# ── 안전장치 ────────────────────────────────────────────────────
def test_사유_없는_반려는_무시한다(wiki):
    # 이유 모르는 제외는 나중에 지우지도 못하고 남는다.
    write(wiki, "h1", verdict="rejected")
    overrides = posts.load()
    warnings = posts.sanity(overrides, ACADEMIES)
    assert any("reject_reason" in w for w in warnings)
    assert overrides == {}          # 통째로 빠진다 — 조용히 적용되지 않는다


def test_알_수_없는_판정은_무시한다(wiki):
    write(wiki, "h1", verdict="삭제해주세요")
    overrides = posts.load()
    posts.sanity(overrides, ACADEMIES)
    assert overrides == {}


def test_없는_학원으로의_재분류는_무시한다(wiki):
    write(wiki, "h1", verdict="reclassified", reassign_to="[A1, 없는학원]")
    overrides = posts.load()
    warnings = posts.sanity(overrides, ACADEMIES)
    assert any("없는 학원" in w for w in warnings)
    assert overrides["h1"]["reassign_to"] == ["A1"]


# ── 적용 ────────────────────────────────────────────────────────
def test_반려하면_모든_학원에서_빠진다(wiki):
    # 같은 글이 여러 학원에 걸려 있다. '이 글은 가짜다'는 한 곳이 아니라
    # 전부에 대한 판단이다.
    ms = [mention("h1", "A1"), mention("h1", "A2"), mention("h2", "A1")]
    write(wiki, "h1", verdict="rejected", reject_reason="광고")
    overrides = posts.load()
    posts.sanity(overrides, ACADEMIES)
    kept, stat = posts.apply_gate(ms, overrides, ACADEMIES)
    assert stat["rejected"] == 2
    assert [m["url_hash"] for m in kept] == ["h2"]


def test_기한이_지나면_빠지고_남아_있으면_통과한다(wiki):
    ms = [mention("h1", "A1")]
    write(wiki, "h1", stale_after=(date.today() - timedelta(days=1)).isoformat())
    kept, stat = posts.apply_gate(ms, posts.load(), ACADEMIES)
    assert stat["stale"] == 1 and kept == []

    write(wiki, "h1", stale_after=(date.today() + timedelta(days=1)).isoformat())
    kept, stat = posts.apply_gate(ms, posts.load(), ACADEMIES)
    assert stat["stale"] == 0 and len(kept) == 1


def test_재분류는_지목된_학원에_붙인다(wiki):
    # 반려와는 다르다. 원본에서는 빼되 진짜 주인에게는 준다 —
    # 반려만 가능하면 네 학원 비교글이 통째로 버려진다.
    ms = [mention("h1", "A1")]
    write(wiki, "h1", verdict="reclassified", reassign_to="[A2]")
    overrides = posts.load()
    posts.sanity(overrides, ACADEMIES)
    kept, stat = posts.apply_gate(ms, overrides, ACADEMIES)
    assert stat["reassigned"] == 1
    assert [(m["academy_key"], m["branch_basis"]) for m in kept] \
        == [("A2", "reclassified")]


def test_이미_붙어_있는_학원에_두_번_붙이지_않는다(wiki):
    ms = [mention("h1", "A1"), mention("h1", "A2")]
    write(wiki, "h1", reassign_to="[A2]")
    kept, stat = posts.apply_gate(ms, posts.load(), ACADEMIES)
    assert stat["reassigned"] == 0
    assert len(kept) == 2


def test_판단이_없으면_아무것도_건드리지_않는다(wiki):
    ms = [mention("h1", "A1"), mention("h2", "A2")]
    kept, stat = posts.apply_gate(ms, {}, ACADEMIES)
    assert kept == ms and not any(stat.values())


# ── 쓰기 ────────────────────────────────────────────────────────
def test_페이지를_만들고_두_번째_실행에는_안_고친다(wiki):
    # 매 실행 9천 장이 갈리면 야간 커밋이 잡음이 된다.
    ms = [mention("h1", "A1"), mention("h1", "A2")]
    first = posts.update(ms, ACADEMIES)
    assert first["created"] == 1 and first["posts"] == 1
    second = posts.update(ms, ACADEMIES)
    assert second["created"] == 0 and second["updated"] == 0


def test_사람이_쓴_판단과_산문을_덮어쓰지_않는다(wiki):
    ms = [mention("h1", "A1")]
    posts.update(ms, ACADEMIES)
    path = wiki / "h1.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("verdict:", "verdict: rejected")
            .replace("reject_reason:", "reject_reason: 광고")
        + "\n이 글은 학원이 직접 쓴 홍보다. 작성자가 같은 글을 5개 카페에 올렸다.\n",
        encoding="utf-8")

    posts.update(ms, ACADEMIES)          # 다시 돌려도
    after = path.read_text(encoding="utf-8")
    assert "verdict: rejected" in after
    assert "reject_reason: 광고" in after
    assert "학원이 직접 쓴 홍보다" in after


def test_양쪽에서_같은_엣지를_적는다(wiki):
    ms = [mention("h1", "A1"), mention("h1", "A2")]
    posts.update(ms, ACADEMIES)
    page = (wiki / "h1.md").read_text(encoding="utf-8")
    assert "../academies/A1" in page and "../academies/A2" in page

    links = posts.backlinks(ms)
    assert "../posts/h1" in links["A1"][0]
    assert "../posts/h1" in links["A2"][0]


def test_합성_언급은_글_노드를_만들지_않는다(wiki):
    # 학원실록 자체 후기는 별점 집계를 언급 형태로 바꾼 것이다.
    # 원문이 없으니 가리킬 페이지도 없다.
    own = mention("rv1", "A1")
    own["source"] = "edutree_review"
    own["source_url"] = "internal://review/A1/v0"
    assert posts.update([own], ACADEMIES)["posts"] == 0


# ── 약속: 무효화가 점수까지 전파된다 ────────────────────────────
def test_반려하면_표본과_코호트와_등수가_함께_다시_계산된다(wiki):
    """이 구조의 존재 이유. 글 한 장이 점수 전체를 되돌린다."""
    ms = ([mention(f"p{i}", "A1", sentiment=0.9) for i in range(12)]
          + [mention(f"q{i}", "A2", sentiment=0.1) for i in range(12)])

    def score(rows):
        by_key: dict[str, list[dict]] = {"A1": [], "A2": []}
        for m in rows:
            by_key[m["academy_key"]].append(m)
        cohorts = scoring.build_cohorts(ACADEMIES, by_key)
        return {a["id"]: scoring.compute_all(a, by_key[a["id"]], cohorts)[0]
                for a in ACADEMIES}

    before = score(ms)
    assert before["A1"]["sample_size"] == 12
    assert before["A1"]["is_ranked"] is True

    # A1 의 긍정 후기 절반을 반려한다.
    for i in range(6):
        write(wiki, f"p{i}", verdict="rejected", reject_reason="광고")
    overrides = posts.load()
    posts.sanity(overrides, ACADEMIES)
    kept, stat = posts.apply_gate(ms, overrides, ACADEMIES)
    assert stat["rejected"] == 6

    after = score(kept)
    # 1) 표본이 줄었다 — 그리고 10건 미만이라 순위에서 빠진다.
    assert after["A1"]["sample_size"] == 6
    assert after["A1"]["is_ranked"] is False
    # 2) ★ 남의 점수까지 움직였다. 코호트가 다시 계산됐다는 뜻이다.
    #    부분 삭제로는 절대 얻을 수 없는 성질이다.
    assert after["A2"]["total"] != before["A2"]["total"]


# ── 공식 홈페이지 ───────────────────────────────────────────────
class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class _Session:
    def __init__(self, resp):
        self._resp = resp

    def get(self, url, **kw):
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


def test_robots_가_거부하면_읽지_않는다():
    from edutree import official
    s = _Session(_Resp(200, "User-agent: *\nDisallow: /\n"))
    ok, why = official._allowed("https://x.test/", s)
    assert ok is False and "거부" in why


def test_ai_train_no_는_거부한다():
    # 스터디홀릭을 수집하지 않기로 한 것과 같은 기준이다.
    from edutree import official
    s = _Session(_Resp(200, "User-agent: *\nAllow: /\nContent-Signal: ai-train=no\n"))
    ok, why = official._allowed("https://x.test/", s)
    assert ok is False and "ai-train" in why


def test_robots_가_없으면_허용이고_못_가져오면_거부다():
    # 없는 것과 실패한 것은 다르다. 서버가 잠깐 죽은 사이에 긁으면 안 된다.
    from edutree import official
    assert official._allowed("https://x.test/", _Session(_Resp(404)))[0] is True
    assert official._allowed(
        "https://x.test/", _Session(RuntimeError("boom")))[0] is False


def test_날짜는_표기가_섞여_있어도_맞춰_적는다():
    from edutree import official
    assert official._dates("공지 2025년 4월 4일") == ["2025-04-04"]
    assert official._dates("2025.04.04 / 2024/12/31") == ["2024-12-31", "2025-04-04"]
    assert official._dates("2025년 13월 99일") == []      # 없는 날짜는 버린다


def test_홈페이지가_없으면_안내만_남는다():
    from edutree import official
    assert "미등록" in official.block("A1", {})


def test_음의_0_은_찍지_않는다():
    # f"{-0.0:+.2f}" 는 '-0.00' 이다. 중립인데 부정으로 읽히고, 파이썬
    # 버전에 따라 같은 계산이 0.0 이 되기도 -0.0 이 되기도 해서 내용이
    # 안 바뀐 페이지가 갈린다(3.9 → 3.12 에서 실제로 한 장이 그랬다).
    assert posts._signed(-0.0) == "+0.00"
    assert posts._signed(0.0) == "+0.00"
    assert posts._signed(None) == "+0.00"
    # 표시 자릿수로 반올림해 0 이면 마이너스를 붙이지 않는다.
    assert posts._signed(-0.004) == "+0.00"
    # 진짜 값은 그대로.
    assert posts._signed(-0.006) == "-0.01"
    assert posts._signed(-0.42) == "-0.42"
    assert posts._signed(0.42) == "+0.42"


def test_감성_표기가_페이지에_음의_0_으로_새지_않는다(wiki):
    m = mention("h1", "A1", sentiment=-0.0)
    posts.update([m], ACADEMIES)
    page = (wiki / "h1.md").read_text(encoding="utf-8")
    assert "-0.00" not in page
    assert "+0.00" in page
    assert "-0.00" not in "\n".join(posts.backlinks([m])["A1"])
