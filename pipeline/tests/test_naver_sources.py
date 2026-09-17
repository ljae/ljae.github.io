"""네이버 웹문서·뉴스 소스 — 응답 모양이 다른 것을 같은 언급 행으로 (2026-09-17).

webkr 은 title·link·description 뿐(날짜 없음), news 는 originallink·link·
description·pubDate(RFC 2822). 뉴스는 언론사 도메인이 작성자이고 신뢰도에
상한이 걸린다. 콘솔에서 안 켠 소스는 첫 401 에서 빠진다. 웹문서·뉴스는
학원당 1질의만 돈다 — 소스가 늘어도 예산이 배로 늘지 않는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, naver  # noqa: E402


class _Resp:
    def __init__(self, status: int, payload=None, text: str = "") -> None:
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload


@pytest.fixture
def api(monkeypatch):
    """requests.get 을 엔드포인트별 응답으로 바꾼다. 실제 호출은 없다."""
    monkeypatch.setattr(naver.config, "HAS_NAVER", True)
    monkeypatch.setattr(naver.config, "NAVER_CLIENT_ID", "id")
    monkeypatch.setattr(naver.config, "NAVER_CLIENT_SECRET", "secret")
    monkeypatch.setattr(naver, "_resolved_mode", "hub")
    monkeypatch.setattr(naver, "_disabled_sources", set())
    monkeypatch.setattr(naver.time, "sleep", lambda *_: None)
    routes: dict[str, _Resp] = {}
    calls: list[tuple[str, dict]] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url.rsplit("/", 1)[-1], dict(params or {})))
        resp = routes.get(url.rsplit("/", 1)[-1], _Resp(200, {"items": []}))
        # 실제 API 처럼 첫 페이지에만 결과가 있다 — 안 그러면 300건까지 넘긴다.
        if resp.status_code == 200 and (params or {}).get("start", 1) != 1:
            return _Resp(200, {"items": []})
        return resp

    monkeypatch.setattr(naver.requests, "get", fake_get)
    return routes, calls


NEWS_ITEM = {
    "title": "대치동 <b>그로튼아카데미</b>, 2027 예비초 설명회 개최",
    "originallink": "https://www.edaily.co.kr/news/read?newsId=01",
    "link": "https://n.news.naver.com/mnews/article/018/0001",
    "description": "그로튼아카데미가 10월 입학설명회를 연다고 밝혔다.",
    "pubDate": "Wed, 17 Sep 2026 09:12:00 +0900",
}
WEB_ITEM = {
    "title": "<b>그로튼아카데미</b> (강남구 대치동) | 강남엄마",
    "link": "https://www.gangmom.kr/institute/65b7afaeb836838137327ade",
    "description": "글쓰기 강화를 기본 모토로 하는 미국교과서 전문센터",
}


def test_뉴스는_원문링크_날짜_언론사도메인(api):
    routes, _ = api
    routes["news"] = _Resp(200, {"items": [NEWS_ITEM]})
    rows = naver.search("naver_news", "대치 그로튼아카데미학원")
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "naver_news"
    assert r["source_url"] == NEWS_ITEM["originallink"]      # 네이버 주소가 아니라 원문
    assert r["posted_at"] == "2026-09-17"                     # RFC 2822 → YYYY-MM-DD
    assert r["author_hash"] == naver._hash("edaily.co.kr")    # 언론사 도메인
    assert r["title"] == "대치동 그로튼아카데미, 2027 예비초 설명회 개최"
    assert r["url_hash"] == naver._hash(NEWS_ITEM["originallink"])


def test_뉴스에_원문링크가_없으면_link(api):
    item = {**NEWS_ITEM, "originallink": ""}
    routes, _ = api
    routes["news"] = _Resp(200, {"items": [item]})
    r = naver.search("naver_news", "q")[0]
    assert r["source_url"] == item["link"]
    assert r["author_hash"] == naver._hash("n.news.naver.com")


def test_웹문서는_날짜없음_host가_작성자(api):
    routes, _ = api
    routes["webkr"] = _Resp(200, {"items": [WEB_ITEM]})
    r = naver.search("naver_web", "대치 그로튼아카데미학원")[0]
    assert r["source"] == "naver_web"
    assert r["posted_at"] is None
    assert r["author_hash"] == naver._hash("gangmom.kr")     # www. 는 뗀다
    assert r["title"] == "그로튼아카데미 (강남구 대치동) | 강남엄마"


def test_잘못된_pubDate는_None():
    assert naver._parse_date({"pubDate": "언제인지 모름"}) is None
    assert naver._parse_date({"postdate": "20260917"}) == "2026-09-17"
    assert naver._parse_date({}) is None


def test_안_켠_소스는_첫_401에서_빠진다(api):
    routes, calls = api
    routes["webkr"] = _Resp(
        401, text='{"error":{"errorCode":401,"message":"요청한 API는 이 Application에서 활성화되어 있지 않습니다."}}')
    assert naver.search("naver_web", "q") == []
    assert "naver_web" in naver._disabled_sources
    n = len(calls)
    assert naver.search("naver_web", "q2") == []            # 두 번째는 호출 자체가 없다
    assert len(calls) == n


def test_웹문서와_뉴스는_학원당_1질의(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_search(source, query, max_results=300):
        seen.append((source, query))
        return [{"url_hash": f"{source}|{query}", "source": source}]

    monkeypatch.setattr(naver, "search", fake_search)
    academy = {"id": "A1", "name": "그로튼아카데미학원", "aliases": ["그로튼"]}
    naver.collect_for_academy(academy, "대치")
    full = naver.queries_for(academy, "대치")
    by = {}
    for s, q in seen:
        by.setdefault(s, []).append(q)
    assert by["naver_cafe"] == full and by["naver_blog"] == full
    assert by["naver_web"] == ["대치 그로튼아카데미학원"]
    assert by["naver_news"] == ["대치 그로튼아카데미학원"]
    # 호출 수: 기존 셋 × len(full) + 웹·뉴스 각 1.
    assert len(seen) == 3 * len(full) + 2


def test_같은_URL이_두_소스에서_오면_블로그가_임자(monkeypatch):
    """웹문서는 블로그 글도 돌려준다. 본문 보강이 naver_blog 를 보므로 그쪽이 남아야 한다."""
    def fake_search(source, query, max_results=300):
        if source in ("naver_blog", "naver_web"):
            return [{"url_hash": "same", "source": source}]
        return []
    monkeypatch.setattr(naver, "search", fake_search)
    rows = naver.collect_for_academy({"id": "A1", "name": "가나학원"}, "대치")
    assert [r["source"] for r in rows] == ["naver_blog"]


def test_뉴스_신뢰도는_블로그의_절반_아래_웹문서는_블로그와_같다():
    text = ("우리 아이 3학년 때 2년 다녔는데 레벨테스트 보고 반 배정받았고 "
            "숙제도 주 3회 꾸준히 있었어요. 등록하고 6개월 만에 2등급 올랐습니다.")
    title = "그로튼아카데미 후기"
    blog = analyze.score_credibility(text, title, "naver_blog")
    assert blog > 0.6                                        # 가산을 다 받는 글
    assert analyze.score_credibility(text, title, "naver_web") == blog
    news = analyze.score_credibility(text, title, "naver_news")
    assert news == analyze.NEWS_CREDIBILITY_CAP <= 0.35
    assert news < blog / 2 + 0.05
    # 짧은 뉴스는 상한 아래로 그냥 낮다 — 상한은 올려 주지 않는다.
    assert analyze.score_credibility("한 줄", "뉴스", "naver_news") < analyze.NEWS_CREDIBILITY_CAP


def test_새_소스는_라벨과_엔드포인트를_갖는다():
    assert naver.SOURCES["naver_web"] == "webkr"
    assert naver.SOURCES["naver_news"] == "news"
    for key in naver.SOURCES:
        assert key in naver.SOURCE_LABELS
    assert set(naver.LIGHT_SOURCES) <= set(naver.SOURCES)
    # 블로그가 웹문서보다 앞이어야 중복 URL 의 임자가 블로그다.
    order = list(naver.SOURCES)
    assert order.index("naver_blog") < order.index("naver_web")
