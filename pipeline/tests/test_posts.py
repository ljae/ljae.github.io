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
    """이 구조의 존재 이유. 글 한 장이 점수 전체를 되돌린다.

    A1 의 후기를 **감성이 섞이게** 둔다. 코호트의 중심과 폭은 학원 단위
    값(가중 평균 감성)의 분포에서 나오므로, 똑같은 감성의 글만 지우면
    A1 의 평균이 그대로라 코호트가 안 움직인다 — 그건 정상이다.
    전파를 보려면 **A1 의 평균이 실제로 바뀌어야** 한다.
    """
    ms = ([mention(f"p{i}", "A1", sentiment=0.9) for i in range(6)]
          + [mention(f"r{i}", "A1", sentiment=0.1) for i in range(6)]
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

    # A1 의 긍정 후기(p*)를 전부 반려한다 — 남는 것은 0.1 짜리뿐이라
    # A1 의 평균 감성 자체가 내려간다.
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


# ── 요약: 소용없는 재시도를 하지 않는다 ─────────────────────────
def test_잔액_부족은_재시도하지_않는다():
    # 9,362건 큐에서 잔액 부족을 재시도로 취급하면 같은 오류가 로그를
    # 도배하고 정작 무엇이 문제인지가 안 보인다. 실측에서 이 한 줄이
    # 9,362번을 1번으로 줄였다(0.8초).
    from edutree import summarize
    msg = ("Error code: 400 - {'type': 'error', 'error': {'type': "
           "'invalid_request_error', 'message': 'Your credit balance is too "
           "low to access the Anthropic API.'}}")
    got = summarize._fatal(msg)
    assert got is not None
    assert got.startswith("Your credit balance")     # 사람이 읽을 사유만


def test_일시적_오류는_계속_시도한다():
    from edutree import summarize
    assert summarize._fatal("Error code: 529 - overloaded_error") is None
    assert summarize._fatal("Connection reset by peer") is None


@pytest.fixture()
def fresh_summarize(monkeypatch):
    """summarize 를 환경변수 바꿔 가며 다시 읽는다.

    모듈 상수를 import 시점에 정하므로 reload 가 필요하다. 끝나면 원래
    환경으로 되돌려 한 번 더 읽는다 — 안 그러면 뒤에 오는 테스트가
    이 테스트가 남긴 상태를 본다.
    """
    import importlib
    from edutree import summarize as mod
    keys = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GEMINI_API_KEY",
            "Gemini_API_KEY", "GOOGLE_API_KEY", "OPENEDU_SUMMARY_PROVIDER",
            "OPENEDU_SUMMARY_MODEL")

    def reload_with(**env):
        for k in keys:
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return importlib.reload(mod)

    yield reload_with
    monkeypatch.undo()
    importlib.reload(mod)


def test_제공자는_있는_키로_고른다(fresh_summarize):
    reload_with = fresh_summarize
    # 요약은 점수에 안 쓰이므로 제공자를 갈아끼워도 산식의 설명이 안 바뀐다.
    # 실제로 Anthropic 잔액이 없어 Gemini 로 옮겼다.
    m = reload_with(GEMINI_API_KEY="g")
    assert (m.PROVIDER, m.MODEL) == ("gemini", "gemini-3.7-flash")

    m = reload_with(ANTHROPIC_API_KEY="a")
    assert (m.PROVIDER, m.MODEL) == ("anthropic", "claude-opus-5")

    # 둘 다면 gemini 를 먼저 본다. 명시하면 그대로 따른다.
    m = reload_with(GEMINI_API_KEY="g", ANTHROPIC_API_KEY="a")
    assert m.PROVIDER == "gemini"
    m = reload_with(GEMINI_API_KEY="g", ANTHROPIC_API_KEY="a",
                    OPENEDU_SUMMARY_PROVIDER="anthropic")
    assert m.PROVIDER == "anthropic"

    # 키가 없으면 조용히 꺼진다.
    m = reload_with()
    assert m.PROVIDER == "" and m.HAS_KEY is False



def test_대소문자가_섞인_키_이름도_받는다(fresh_summarize):
    # .env 는 사람이 손으로 쓴다. 실제로 `Gemini_API_KEY` 로 들어왔다.
    m = fresh_summarize(Gemini_API_KEY="g")
    assert m.PROVIDER == "gemini" and m.GEMINI_KEY == "g"


def test_잘린_요약은_저장해_두고도_다시_만든다():
    # 사고 예산을 껐는데도 간헐적으로 출력이 모자라 문장이 끊겼다
    # (실측 1,091건 중 8건: '12월 1일 개', '수학 9'). 캐시는 '한 번만
    # 만든다'가 원칙이지만 잘린 조각은 요약이 아니라 잡음이다.
    from edutree import summarize
    assert summarize._looks_truncated("12월 1일 개")
    assert summarize._looks_truncated("수학 9")
    assert summarize._looks_truncated("대치동에서 시작해 20년 이상의 경력과 좋은")
    assert summarize._looks_truncated("")
    # ★ 짧다고 잘린 것이 아니다. '내용 없음.' 은 본문이 없는 글의 옳은
    #   요약인데, 길이로 재면 매 실행 다시 만들고 그때마다 돈이 든다.
    assert not summarize._looks_truncated("내용 없음.")
    assert not summarize._looks_truncated("작성된 본문 내용이 없습니다.")
    # 제대로 끝난 문장은 건드리지 않는다.
    assert not summarize._looks_truncated("초등 교재로 시판 문제집을 쓰는지 질문했습니다.")
    assert not summarize._looks_truncated("홍보성 글이다. 원장의 약력이 적혀 있다.")


def test_학교_수집이_끊기면_캐시로_진행한다(tmp_path, monkeypatch):
    # 여기까지 오면 NEIS 학원·언급 분석·채점이 이미 다 끝난 상태다.
    # 연결이 한 번 끊겼다고 그걸 통째로 버리면 야간 작업이 아무것도
    # 내놓지 못한다. schooldistrict 에서 겪고 schools 에서 또 겪었다.
    import json as _json
    import requests
    from edutree import schools, config

    monkeypatch.setattr(config, "HAS_NEIS", True)
    monkeypatch.setattr(schools.config, "CACHE_DIR", tmp_path)
    (tmp_path / "schools.json").write_text(
        _json.dumps([{"name": "대치초등학교"}]), encoding="utf-8")

    def boom(*a, **k):
        raise requests.ConnectionError("Can't assign requested address")

    monkeypatch.setattr(schools, "_request", boom)
    got = schools.fetch_all()
    assert got == [{"name": "대치초등학교"}]      # 캐시로 진행


def test_캐시도_없으면_빈_목록이지_예외가_아니다(tmp_path, monkeypatch):
    import requests
    from edutree import schools, config
    monkeypatch.setattr(config, "HAS_NEIS", True)
    monkeypatch.setattr(schools.config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(schools, "_request",
                        lambda *a, **k: (_ for _ in ()).throw(
                            requests.ConnectionError("boom")))
    assert schools.fetch_all() == []


def test_키가_없어도_캐시가_있으면_그것으로_간다(tmp_path, monkeypatch):
    """네트워크 **실패** 에는 캐시로 물러서면서 키 **없음** 에는 빈 목록을
    돌려주고 있었다. 그 차이 때문에 키 없는 환경에서 `--from-cache` 로
    산식을 실험하면(문서가 권하는 사용법이다) schools.json 이 0KB 로
    덮어써져 학교·아파트 배정이 통째로 사라졌다.

    둘 다 '지금 새로 못 가져온다' 는 같은 상황이다. 학교는 하루 이틀
    사이에 새로 생기지 않는다."""
    import json as _json
    from edutree import schools, config

    monkeypatch.setattr(config, "HAS_NEIS", False)
    monkeypatch.setattr(schools.config, "CACHE_DIR", tmp_path)
    (tmp_path / "schools.json").write_text(
        _json.dumps([{"name": "목동초등학교"}]), encoding="utf-8")
    assert schools.fetch_all() == [{"name": "목동초등학교"}]


# ── 과목 추론: '보습·논술' 은 과목 선언이 아니다 ─────────────────
def test_보습논술은_국어_신호가_아니다():
    """NEIS 의 '보습·논술' 은 보습학원 기본 등록값이지 과목 선언이 아니다.

    '논술' 이 국어 힌트에 걸려, 이름에 과목 단서가 없는 학원 827곳이
    국어로 분류돼 있었다 — 시대인재·강남대성·러셀·대치파인만이 전부
    '대치 예비초~초3 국어' 랭킹에 있었다(신고: '아이엘이는 영어학원인데
    국어에 있다'). 진짜 국어 학원은 이름에 단서가 있으므로 잃는 것이 없다.
    """
    from edutree import build
    보습 = {"name": "아이엘이학원", "realm_sc_nm": "입시.검정 및 보습",
           "le_crse_nm": "보습·논술"}
    assert build._infer_subjects(보습) == ["general"]

    # 이름에 단서가 있으면 그쪽이 이긴다. (주의: '논구술' 은 '논술' 을
    # 부분문자열로 갖지 않는다 — 이 테스트를 쓰며 한 번 헛짚었다.)
    논술 = {"name": "대치한우리독서토론논술교습소",
           "realm_sc_nm": "입시.검정 및 보습", "le_crse_nm": "보습·논술"}
    assert "korean" in build._infer_subjects(논술)

    # 진짜 과목 신호는 그대로 살아 있어야 한다.
    외국어 = {"name": "아이엘이어학원", "realm_sc_nm": "종합(대)",
            "le_crse_list_nm": "실용외국어(유아/초·중·고)"}
    assert build._infer_subjects(외국어) == ["english"]


def test_종합학원_과목은_후기가_말한_것으로_정한다():
    """general 은 '모른다' 는 뜻이라 어느 랭킹에도 안 나온다. 표본 342건
    짜리 시대인재가 통째로 사라지므로, 후기가 반복해 말한 과목만 확정한다."""
    from edutree import build
    a = {"id": "X", "subjects": ["general"]}
    many = [{"academy_key": "X", "subjects": ["math"], "is_excluded": False}
            for _ in range(20)]
    few = [{"academy_key": "X", "subjects": ["science"], "is_excluded": False}]
    assert build._subjects_from_mentions([a], {"X": many + few}) == 1
    # 반복된 과목만 붙고, 한 번 스친 과목은 안 붙는다. general 은 빠진다.
    assert a["subjects"] == ["math"]

    # 근거가 얇으면 아무것도 확정하지 않는다 — general 로 남는다.
    b = {"id": "Y", "subjects": ["general"]}
    assert build._subjects_from_mentions([b], {"Y": few}) == 0
    assert b["subjects"] == ["general"]


# ── 한 글은 한 학원에 대해 한 과목·한 학급만 말한다 ──────────────
def test_한_글은_한_학원에_한_과목만_붙는다():
    """집합으로 두면 같은 글이 수학 근거이자 과학 근거가 된다.
    표본이 부풀고 코호트 평균까지 함께 밀린다."""
    from edutree import analyze, scoring
    t = "대치 시대인재 수학 재종반 다니는데 과학탐구도 같이 들어요"
    assert analyze.subject_near_one(t, {"시대인재"}) == "math"   # 이름에 가장 가까운 것
    m = analyze.analyze({"snippet": t, "title": "", "source": "naver_cafe"},
                        "시대인재", {"시대인재"})
    assert m["subject"] == "math"
    assert m["subjects"] == ["math"]        # 목록이어도 길이는 1 이하

    # 과목별로 갈랐을 때 같은 글이 두 곳에 들어가지 않는다.
    aca = {"id": "X", "subjects": ["math", "science"], "region_id": "daechi"}
    rows = ([{"url_hash": f"m{i}", "subjects": ["math"], "is_excluded": False}
             for i in range(3)]
            + [{"url_hash": "s0", "subjects": ["science"], "is_excluded": False}]
            + [{"url_hash": "n0", "subjects": [], "is_excluded": False}])
    seen: dict[str, list[str]] = {}
    for sub in ("math", "science"):
        for m in scoring.subject_mentions(aca, rows, sub):
            seen.setdefault(m["url_hash"], []).append(sub)
    assert all(len(v) == 1 for v in seen.values())   # 겹치는 글 없음
    assert len(seen) == len(rows)                    # 빠지는 글도 없음


def test_학급도_이름_근처에서_하나만_읽는다():
    """학원을 학급별로 갈라 줄 세우려면 글도 학급별로 갈려야 한다.
    이 신호는 원래 없었다 — 없으면 같은 글이 모든 학급에 복사된다."""
    from edutree import analyze
    assert analyze.band_near_one("아이엘이 초3 파닉스반 후기", {"아이엘이"}) == "elem_low"
    assert analyze.band_near_one("시대인재 고3 재종반", {"시대인재"}) == "high"
    assert analyze.band_near_one("중2 내신 대비로 다원", {"다원"}) == "middle"
    # 학원 이름이 없으면 아무것도 읽지 않는다.
    assert analyze.band_near_one("고3 수능 이야기", {"없는학원"}) is None
    # 구간을 못 정하는 말은 넘기지 않는다 — '초등'은 저·고학년 어느 쪽도 아니다.
    assert analyze.band_near_one("초등 대상 학원 아이엘이", {"아이엘이"}) is None


def test_빈_학급은_후기로_정하되_못_정하면_비워_둔다():
    """빈 grade_bands 는 앱이 '네 구간 모두'로 읽는다. 그래서 수능 재종반
    시대인재가 '대치 예비초~초3 국어' 1위였다(신고). 후기로 정한다."""
    from edutree import build
    a = {"id": "X", "grade_bands": []}
    high = [{"band": "high", "is_excluded": False} for _ in range(20)]
    stray = [{"band": "elem_low", "is_excluded": False}]
    assert build._bands_from_mentions([a], {"X": high + stray}) == 1
    assert a["grade_bands"] == ["high"]          # 스친 한 건은 안 붙는다

    # 근거가 얇으면 비운 채로 둔다 — 정말 전 학년을 받는 곳이 있고,
    # 그런 곳을 한 구간에 가두면 그게 또 다른 오류다.
    b = {"id": "Y", "grade_bands": []}
    assert build._bands_from_mentions([b], {"Y": stray}) == 0
    assert b["grade_bands"] == []

    # 이미 공시로 정해져 있으면 건드리지 않는다.
    c = {"id": "Z", "grade_bands": ["elem_low"]}
    assert build._bands_from_mentions([c], {"Z": high}) == 0
    assert c["grade_bands"] == ["elem_low"]


# ── 성인 직업·전문 학원은 등록부에 넣지 않는다 ──────────────────
def test_직업학원은_분야구분으로_뺀다():
    """이 서비스는 초·중·고 학부모가 본다. 미용·승무원·간호조무사·
    편입·변리사는 그 학부모가 찾는 학원이 아니다.

    ★ 이름이 아니라 **분야구분**으로 거른다. 이름으로 거르면
      '게임캔버스'·'디자인센트럴' 처럼 판단이 안 서는 것이 남고,
      반대로 '미용' 이 든 아이 대상 학원을 잘못 지운다.
    """
    from edutree import config
    keep = config.ACADEMIC_REALMS | config.ARTS_REALMS | config.OTHER_REALMS

    for realm in ("직업기술", "인문사회(대)", "독서실"):
        assert realm not in keep, f"{realm} 은 제외돼야 한다"
        assert realm in config.EXCLUDED_REALMS

    # 아이들이 다니는 곳은 남는다.
    for realm in ("입시.검정 및 보습", "국제화", "종합(대)",
                  "예능(대)", "기예(대)", "기타(대)", "정보"):
        assert realm in keep, f"{realm} 은 남아야 한다"

    # '정보' 는 두 곳뿐인데 둘 다 어린이 코딩학원이라 기타로 남긴다.
    assert "정보" in config.OTHER_REALMS


def test_직업학원은_분야만으로_다_안_걸린다():
    """같은 미용학원이라도 '기타(대)' 로, 승무원학원이 '기타(대)' 로,
    김영편입이 '종합(대)' 로 등록돼 있다. 분야 → 교습과정 → 이름 순."""
    from edutree import config
    # 분야가 통과해도 교습과정이 말한다.
    assert config.is_vocational(
        {"name": "목동아뜰리에미용전문학원", "realm_sc_nm": "기타(대)",
         "le_crse_nm": "이·미용"})
    assert config.is_vocational(
        {"name": "김영편입강남단과캠퍼스학원", "realm_sc_nm": "종합(대)",
         "le_crse_nm": "대학편입"})
    # 교습과정도 비어 있으면 이름이 마지막이다.
    assert config.is_vocational(
        {"name": "스카이항공승무원학원", "realm_sc_nm": "기타(대)"})
    # 미대편입은 과정이 '미술' 이라 이름으로만 걸린다.
    assert config.is_vocational(
        {"name": "미대편입강남창조학원", "realm_sc_nm": "기예(대)",
         "le_crse_nm": "미술"})


def test_뷰티는_이름_규칙에_넣지_않는다():
    """★ '뷰티' 16곳 중 뷰티풀마인드수학학원·뷰티풀마인드고등관수학학원은
    진짜 수학학원이다. '미용' 이 든 이름은 전부 미용학원이지만 '뷰티' 는
    아니다 — 낱말 하나 차이로 멀쩡한 학원이 사라진다."""
    from edutree import config
    assert "뷰티" not in config.VOCATIONAL_NAME_WORDS
    for n in ("뷰티풀마인드수학학원", "뷰티풀마인드고등관수학학원"):
        assert not config.is_vocational(
            {"name": n, "realm_sc_nm": "입시.검정 및 보습", "le_crse_nm": "보습"})
    # 아이 대상은 남는다.
    assert not config.is_vocational(
        {"name": "와이코딩정보교습소", "realm_sc_nm": "정보"})
    assert not config.is_vocational(
        {"name": "은마바둑교습소", "realm_sc_nm": "기타(대)"})


# ── 진로 목적지 (테크트리 종점) ──────────────────────────────────
def test_목적지가_참조하는_단계는_전부_실재한다():
    """오타를 그냥 두면 경로가 **조용히 비어** 목적지 카드가 빈 채로
    나가고, 그건 '이 길이 없다' 는 거짓말이 된다."""
    from edutree import config
    tree = config.techtree()
    valid = {s["id"] for t in tree["tracks"] for s in t["stages"]}
    dests = config.destinations()
    assert len(dests) == 7
    for d in dests:
        for subject, ids in d["requires"].items():
            assert ids, f"{d['id']} 의 {subject} 경로가 비었다"
            for i in ids:
                assert i in valid, f"{d['id']} → 없는 단계 {i}"


def test_근거가_얇은_목적지는_학원을_잇지_않는다():
    """조기졸업 15건 · 예체능 28건. 길이 있다는 것은 보여 주되
    누가 그 길인지는 말하지 않는다."""
    from edutree import config
    by = {d["id"]: d for d in config.destinations()}
    assert by["dest_early"]["linkable"] is False
    assert by["dest_art"]["linkable"] is False
    # 근거가 선 목적지는 잇는다.
    for k in ("dest_medical", "dest_abroad", "dest_science_hs"):
        assert by[k]["linkable"] is True


def test_목적지마다_되돌리기_어려운_지점이_있다():
    """'언제 갈리는가' 가 이 서비스가 줄 수 있는 가장 실용적인 정보다."""
    from edutree import config
    for d in config.destinations():
        assert d.get("gates"), f"{d['id']} 에 관문이 없다"
        for g in d["gates"]:
            assert -2 <= g["grade"] <= 12
            assert g["note"].strip()
