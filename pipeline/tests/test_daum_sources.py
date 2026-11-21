"""다음(카카오) 검색 소스 — 네이버와 같은 언급 행으로 (2026-11-15).

응답은 documents[] · meta.is_end 이고 모든 글에 datetime 이 온다. 키가
없거나 거부되면 이 소스만 빠지고 실행은 계속된다 — 보탬이지 기둥이 아니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, daum, naver, review_integrity  # noqa: E402


class _Resp:
    def __init__(self, status: int, payload=None, text: str = "") -> None:
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(daum.config, "HAS_DAUM", True)
    monkeypatch.setattr(daum.config, "KAKAO_REST_API_KEY", "key")
    monkeypatch.setattr(daum, "_disabled_sources", set())
    monkeypatch.setattr(daum.time, "sleep", lambda *_: None)
    monkeypatch.setattr(daum.source_health, "save", lambda: None)
    routes: dict[str, _Resp] = {}
    calls: list[tuple[str, dict, dict]] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        name = url.rsplit("/", 1)[-1]
        calls.append((name, dict(params or {}), dict(headers or {})))
        return routes.get(name, _Resp(200, {"documents": [],
                                            "meta": {"is_end": True}}))

    monkeypatch.setattr(daum.requests, "get", fake_get)
    return routes, calls


def _page(docs, is_end=True):
    return _Resp(200, {"documents": docs, "meta": {"is_end": is_end}})


CAFE = {"title": "대치 <b>렉스김</b> 레벨테스트 후기",
        "contents": "지난주에 <b>렉스김</b>어학원 레테 보고 왔어요.",
        "url": "https://cafe.daum.net/daechimom/AbCd/123",
        "cafename": "대치맘", "datetime": "2026-11-02T09:12:00.000+09:00"}
BLOG = {"title": "렉스김어학원 다닌 지 1년", "contents": "숙제가 많은 편입니다.",
        "url": "https://edumom.tistory.com/45", "blogname": "교육 일기",
        "datetime": "2026-10-20T21:00:00.000+09:00"}
ACADEMY = {"id": "1000", "name": "렉스김어학원", "region_id": "daechi"}


def test_카페글은_태그를_벗기고_작성일을_갖는다(api):
    routes, calls = api
    routes["cafe"] = _page([CAFE])
    rows = daum.search("daum_cafe", "대치 렉스김어학원 후기")
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "daum_cafe"
    assert r["title"] == "대치 렉스김 레벨테스트 후기"
    assert r["snippet"] == "지난주에 렉스김어학원 레테 보고 왔어요."
    assert r["posted_at"] == "2026-11-02"            # 발견일이 아니라 작성일
    assert r["url_hash"] == naver._hash(CAFE["url"])  # 네이버와 같은 해시
    assert r["author_hash"] is None                   # 카페는 작성자가 아니다
    assert calls[0][2] == {"Authorization": "KakaoAK key"}


def test_블로그_작성자는_주소에서_온다(api):
    routes, _ = api
    routes["blog"] = _page([BLOG, {**BLOG, "url": "https://edumom.tistory.com/46"},
                            {**BLOG, "url": "https://blog.naver.com/abc/1"},
                            {**BLOG, "url": "https://blog.naver.com/xyz/2"}])
    a, b, c, d = daum.search("daum_blog", "q")
    assert a["author_hash"] == b["author_hash"]       # 같은 티스토리 = 한 사람
    assert c["author_hash"] != d["author_hash"]       # 같은 호스트, 다른 사람
    assert a["author_hash"] != c["author_hash"]


def test_날짜가_없거나_깨지면_지어내지_않는다(api):
    routes, _ = api
    routes["web"] = _page([{**BLOG, "datetime": ""},
                           {**BLOG, "url": "https://a.kr/2", "datetime": "어제"}])
    assert [r["posted_at"] for r in daum.search("daum_web", "q")] == [None, None]


def test_is_end_가_거짓이면_다음_쪽을_읽는다(api, monkeypatch):
    pages = [_page([{**CAFE, "url": f"https://cafe.daum.net/a/{i}"}
                    for i in range(50)], is_end=False),
             _page([{**CAFE, "url": "https://cafe.daum.net/a/last"}])]
    seen: list[int] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.append(params["page"])
        return pages[params["page"] - 1]

    monkeypatch.setattr(daum.requests, "get", fake_get)
    assert len(daum.search("daum_cafe", "q", max_results=100)) == 51
    assert seen == [1, 2]


def test_키가_거부되면_그_소스만_한_번에_빠진다(api):
    routes, calls = api
    routes["cafe"] = _Resp(401, text='{"errorType":"AccessDeniedError"}')
    routes["blog"] = _page([BLOG])
    rows = daum.collect_for_academy(ACADEMY, "대치")
    assert {r["source"] for r in rows} == {"daum_blog"}
    assert [c[0] for c in calls].count("cafe") == 1   # 같은 실패를 되풀이하지 않는다


def test_한도에_걸리면_세_번_뒤_그_소스를_뺀다(api):
    routes, calls = api
    routes["cafe"] = _Resp(429, text="quota")
    assert daum.collect_for_academy(ACADEMY, "대치") == []
    assert [c[0] for c in calls].count("cafe") == 3
    assert "daum_cafe" in daum._disabled_sources


def test_웹문서는_학원당_한_질의_나머지는_전부(api):
    _, calls = api
    daum.collect_for_academy(ACADEMY, "대치")
    by = [c[0] for c in calls]
    full = len(naver.queries_for(ACADEMY, "대치"))
    assert (by.count("cafe"), by.count("blog"), by.count("web")) == (full, full, 1)
    assert all("대치" in c[1]["query"] for c in calls)  # 지역명은 반드시 건다


def test_키가_없으면_부르지_않는다(api, monkeypatch):
    _, calls = api
    monkeypatch.setattr(daum.config, "HAS_DAUM", False)
    assert daum.collect_all([ACADEMY], {"daechi": "대치"}) == []
    assert calls == []


def test_수집은_실패를_밖으로_던지지_않고_학원_키를_단다(api, monkeypatch):
    routes, _ = api
    routes["cafe"] = _page([CAFE])

    real = daum.collect_for_academy

    def flaky(academy, region_name, per_query=daum.SIZE):
        if academy["id"] == "boom":
            raise RuntimeError("x")
        return real(academy, region_name, per_query)

    monkeypatch.setattr(daum, "collect_for_academy", flaky)
    rows = daum.collect_all([ACADEMY, {**ACADEMY, "id": "boom"}], {"daechi": "대치"})
    assert [(r["academy_key"], r["region_id"]) for r in rows] == [("1000", "daechi")]


def test_다음_카페는_네이버_카페와_같은_대접을_받는다():
    text = "우리아이 6개월 다녔는데 숙제가 많고 선생님이 꼼꼼해요. " * 3
    assert analyze.score_credibility(text, "후기", "daum_cafe") == \
        analyze.score_credibility(text, "후기", "naver_cafe")
    assert review_integrity.evidence_kind({"source": "daum_web"}) == "web_information"
    assert naver.SOURCE_LABELS["daum_cafe"] == "다음 카페"


def test_연결이_안_되는_소스는_다섯_번_뒤_이번_실행에서_뺀다(api, monkeypatch):
    """2026-11-20 야간: dapi.kakao.com 이 러너에서 통째로 안 닿아 질의
    2,539건이 15초씩 기다렸고, 10분짜리 단계가 4시간 반을 돌다 죽었다."""
    _, _ = api
    monkeypatch.setattr(daum, "_network_failures", {})
    calls: list[str] = []

    def unreachable(url, params=None, headers=None, timeout=None):
        calls.append(url.rsplit("/", 1)[-1])
        raise daum.requests.ConnectTimeout("no route")

    monkeypatch.setattr(daum.requests, "get", unreachable)
    academies = [{**ACADEMY, "id": str(i)} for i in range(40)]
    assert daum.collect_all(academies, {"daechi": "대치"}, workers=1) == []
    assert daum._disabled_sources == set(daum.SOURCES)
    for name in ("cafe", "blog", "web"):
        assert calls.count(name) == daum.NETWORK_FAILURE_LIMIT


def test_응답이_한_번_오면_연결_실패를_다시_센다(api, monkeypatch):
    routes, _ = api
    monkeypatch.setattr(daum, "_network_failures", {})
    routes["cafe"] = _page([CAFE])
    state = {"n": 0}
    real = daum.requests.get

    def flaky(url, params=None, headers=None, timeout=None):
        state["n"] += 1
        if state["n"] % 5:                     # 다섯 번에 네 번 끊긴다
            raise daum.requests.ConnectionError("reset")
        return real(url, params=params, headers=headers, timeout=timeout)

    monkeypatch.setattr(daum.requests, "get", flaky)
    for _ in range(20):
        try:
            daum.search("daum_cafe", "q")
        except daum.DaumError:
            pass
    assert "daum_cafe" not in daum._disabled_sources   # 간헐 실패로는 안 뺀다
