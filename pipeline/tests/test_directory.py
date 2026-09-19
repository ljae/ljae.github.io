"""학원 자기 서술(directory.py) — 강남엄마 소개 페이지에서 학원이 밝힌 것만.

세 가지를 고정한다. ① 실제 페이지(픽스처)에서 셔틀·대상·소개·소식 제목이
뽑히고 **후기 문장은 어디에도 남지 않는다.** ② robots 가 거부하면 페이지를
한 장도 열지 않는다. ③ 이름+동이 같아도 주소가 다르면 잇지 않는다 —
'메이플' 미용실 사고의 반대편.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import directory  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "gangmom_institute.html"
HTML = FIXTURE.read_text(encoding="utf-8")
PAGE = "https://www.gangmom.kr/institute/65b7afaeb836838137327ade"
ROBOTS_OK = ("User-agent: *\nAllow: /\n\nSitemap: https://www.gangmom.kr/sitemap.xml\n"
             "Disallow: /user/\nDisallow: /internal/\nDisallow: /review/\n")


class _Resp:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code, self.text = status, text
        self.encoding = self.apparent_encoding = "utf-8"


class FakeSession:
    """URL → (status, 본문). 무엇을 열었는지 전부 기록한다."""

    def __init__(self, pages: dict[str, tuple[int, str]]) -> None:
        self.pages, self.calls = pages, []

    def get(self, url, **kw):
        self.calls.append(url)
        status, text = self.pages.get(url, (404, ""))
        return _Resp(status, text)


def _wire(monkeypatch, tmp_path, session: FakeSession) -> None:
    monkeypatch.setattr(directory, "CACHE", tmp_path / "directory.json")
    monkeypatch.setattr(directory, "SITEMAP_CACHE", tmp_path / "sitemap.json")
    monkeypatch.setattr(directory, "PUBLISHED", tmp_path / "published.json")
    monkeypatch.setattr(directory.time, "sleep", lambda *_: None)
    import requests
    monkeypatch.setattr(requests, "Session", lambda: session)


def _academy(aid: str, name: str, dong: str, road: str) -> dict:
    return {"id": aid, "name": name, "dong": dong, "road_address": road,
            "region_id": "daechi"}


GROTON = _academy("A1", "그로튼아카데미학원", "대치동",
                  "서울특별시 강남구 도곡로 418 (대치동, 강원빌딩)")


# ── ① 파싱 ────────────────────────────────────────────────────────
def test_픽스처에서_셔틀_대상_소개_소식제목이_뽑힌다():
    p = directory.parse_page(HTML)
    assert (p["name"], p["gu"], p["dong"]) == ("그로튼아카데미", "강남구", "대치동")
    assert p["shuttle"] is True
    assert p["target"] == ["초1~중3"]
    assert p["subjects"] == ["영어"]
    assert p["address"].startswith("서울 강남구 도곡로 418")
    assert p["text"].startswith("글쓰기 강화를 기본 모토로")
    assert len(p["text"]) <= directory.TEXT_LIMIT
    assert p["events"] and len(p["events"]) <= directory.EVENTS_MAX
    assert any("입학설명회" in t for t in p["events"])
    assert "입학시험 안내" in p["events"][0]


def test_후기_문장은_어느_필드에도_없다():
    """소개 페이지에 SSR 로 실린 리뷰 3건('아이가 즐겁게…')은 읽지 않는다."""
    p = directory.parse_page(HTML)
    assert "아이가 즐겁게" in HTML                      # 페이지에는 있다
    blob = " ".join(str(v) for v in p.values())
    assert "아이가 즐겁게" not in blob
    assert "4대영역" not in blob
    assert all("학원비 안내" not in t for t in p["events"])   # 학원비 글도 소식이 아니다


def test_없는_항목은_None():
    p = directory.parse_page("<html><title>무명학원 (강남구 대치동) | 강남엄마</title></html>")
    assert p["name"] == "무명학원" and p["dong"] == "대치동"
    assert p["shuttle"] is None and p["target"] is None and p["events"] is None
    assert p["text"] is None


def test_소개가_1500자를_넘으면_자른다():
    long = "가" * 3000
    html = ('<html><head><title>긴학원 (강남구 대치동) | 강남엄마</title>'
            f'<meta name="description" content="{long}, 평점 4.0, 셔틀 미제공"></head></html>')
    p = directory.parse_page(html)
    assert len(p["text"]) == directory.TEXT_LIMIT
    assert p["shuttle"] is False


# ── ② robots ──────────────────────────────────────────────────────
def test_robots가_거부하면_페이지를_열지_않는다(monkeypatch, tmp_path):
    s = FakeSession({"https://www.gangmom.kr/robots.txt": (200, "User-agent: *\nDisallow: /\n"),
                     PAGE: (200, HTML)})
    _wire(monkeypatch, tmp_path, s)
    got = directory.collect([GROTON], [{"source_url": PAGE, "academy_key": "A1"}], live=True)
    assert got == {}
    assert PAGE not in s.calls
    assert s.calls == ["https://www.gangmom.kr/robots.txt"]
    assert not (tmp_path / "directory.json").exists()


def test_ai_train_no_도_거부다(monkeypatch, tmp_path):
    s = FakeSession({"https://www.gangmom.kr/robots.txt":
                     (200, "User-agent: *\nAllow: /\nContent-Signal: ai-train=no\n"),
                     PAGE: (200, HTML)})
    _wire(monkeypatch, tmp_path, s)
    assert directory.collect([GROTON], [{"source_url": PAGE, "academy_key": "A1"}]) == {}
    assert PAGE not in s.calls


def test_robots_확인_실패도_거부다(monkeypatch, tmp_path):
    s = FakeSession({PAGE: (200, HTML)})                 # robots.txt → 404 는 허용,
    s.pages["https://www.gangmom.kr/robots.txt"] = (503, "")   # 5xx 는 거부
    _wire(monkeypatch, tmp_path, s)
    assert directory.collect([GROTON], [{"source_url": PAGE, "academy_key": "A1"}]) == {}
    assert PAGE not in s.calls


def test_후기_경로는_파서가_뭐라_하든_열지_않는다():
    """파이썬 RobotFileParser 는 빈 줄 뒤의 Disallow: /review/ 를 버린다(실측).
    그래도 코드가 그 경로를 막는다."""
    s = FakeSession({"https://www.gangmom.kr/review/abc": (200, "<html>후기</html>")})
    html, err = directory._fetch(s, "https://www.gangmom.kr/review/abc")
    assert html is None and err == "robots 거부 경로"
    assert s.calls == []


# ── ③ 대조 ────────────────────────────────────────────────────────
def test_이름과_동이_같아도_주소가_다르면_잇지_않는다(monkeypatch, tmp_path):
    other_addr = _academy("A2", "그로튼아카데미학원", "대치동",
                          "서울특별시 강남구 선릉로 100")
    other_dong = _academy("A3", "그로튼아카데미학원", "목동",
                          "서울특별시 양천구 목동서로 349")
    page = directory.parse_page(HTML)
    reg = directory.Registry([GROTON, other_addr, other_dong])
    assert directory.match_academy(page, reg) == "A1"
    assert directory.match_academy(page, directory.Registry([other_addr])) is None
    assert directory.match_academy(page, directory.Registry([other_dong])) is None
    # 후보를 낸 학원(prefer)이라도 주소가 다르면 잇지 않는다.
    assert directory.match_academy(page, directory.Registry([other_addr]), prefer="A2") is None


def test_주소를_모르는_동명_둘이면_어느_쪽도_잇지_않는다():
    a = _academy("A1", "그로튼아카데미학원", "대치동", "")
    b = _academy("A2", "그로튼아카데미학원", "대치동", "")
    page = directory.parse_page(HTML)
    assert directory.match_academy(page, directory.Registry([a, b])) is None
    # 후보를 낸 쪽이 둘 중 하나면 그것 — 페이지가 그 학원 검색에서 나온 것이다.
    assert directory.match_academy(page, directory.Registry([a, b]), prefer="A2") is None


def test_언급_링크로_잇고_캐시에는_후기가_없다(monkeypatch, tmp_path):
    s = FakeSession({"https://www.gangmom.kr/robots.txt": (200, ROBOTS_OK),
                     PAGE: (200, HTML),
                     "https://www.gangmom.kr/sitemap.xml": (404, "")})
    _wire(monkeypatch, tmp_path, s)
    wrong = _academy("A2", "그로튼아카데미학원", "대치동", "서울특별시 강남구 선릉로 100")
    mentions = [{"source_url": PAGE + "?tab=news", "academy_key": "A1"},
                {"source_url": "https://blog.naver.com/x/1", "academy_key": "A1"},
                {"source_url": PAGE, "academy_key": "A2"}]
    got = directory.collect([GROTON, wrong], mentions, live=True)
    assert set(got) == {"A1"}
    row = got["A1"]
    assert row["shuttle"] is True and row["target"] == ["초1~중3"]
    assert row["url"] == PAGE and row["source"] == "gangmom"
    assert "아이가 즐겁게" not in (tmp_path / "directory.json").read_text(encoding="utf-8")
    # A2 는 같은 페이지를 후보로 냈지만 주소가 달라 불일치로 남고, 결과에서 빠진다.
    import json
    cache = json.loads((tmp_path / "directory.json").read_text(encoding="utf-8"))
    assert "불일치" in cache["A2"]["error"]
    # 캐시가 있으면 live=False 로도 같은 것을 돌려준다 — 네트워크 없이.
    s.calls.clear()
    assert set(directory.collect([GROTON, wrong], [], live=False)) == {"A1"}
    assert s.calls == []


def test_큰_sitemap은_걷지_않는다(monkeypatch, tmp_path):
    many = "".join(f"<url><loc>https://www.gangmom.kr/institute/{i:024x}</loc></url>"
                   for i in range(directory.SITEMAP_MAX + 1))
    s = FakeSession({
        "https://www.gangmom.kr/robots.txt": (200, ROBOTS_OK),
        "https://www.gangmom.kr/sitemap.xml":
            (200, '<sitemapindex><sitemap><loc>https://www.gangmom.kr/sitemaps/academies/sitemap_academy_0.xml</loc></sitemap></sitemapindex>'),
        "https://www.gangmom.kr/sitemaps/academies/sitemap_academy_0.xml": (200, f"<urlset>{many}</urlset>"),
    })
    _wire(monkeypatch, tmp_path, s)
    assert directory.collect([GROTON], [], live=True) == {}
    assert not any("/institute/" in u for u in s.calls)


def test_작은_sitemap은_걷고_제목으로_잇는다(monkeypatch, tmp_path):
    other = "https://www.gangmom.kr/institute/000000000000000000000001"
    s = FakeSession({
        "https://www.gangmom.kr/robots.txt": (200, ROBOTS_OK),
        "https://www.gangmom.kr/sitemap.xml":
            (200, f"<urlset><url><loc>{PAGE}</loc></url><url><loc>{other}</loc></url></urlset>"),
        PAGE: (200, HTML),
        other: (200, "<html><title>남의학원 (송파구 잠실동) | 강남엄마</title></html>"),
    })
    _wire(monkeypatch, tmp_path, s)
    got = directory.collect([GROTON], [], live=True)
    assert set(got) == {"A1"} and got["A1"]["url"] == PAGE
    # 두 번째 실행은 이미 본 것을 다시 열지 않는다.
    s.calls.clear()
    directory.collect([GROTON], [], live=True)
    assert PAGE not in s.calls and other not in s.calls


def test_네트워크가_죽어도_실행은_계속된다(monkeypatch, tmp_path):
    class Boom:
        def get(self, *a, **k):
            import requests
            raise requests.ConnectionError("down")
    _wire(monkeypatch, tmp_path, Boom())
    assert directory.collect([GROTON], [{"source_url": PAGE, "academy_key": "A1"}]) == {}


def test_status는_네트워크_없이_한_줄(monkeypatch, tmp_path):
    monkeypatch.setattr(directory, "CACHE", tmp_path / "directory.json")
    assert directory.status().startswith("✗")
    directory._save(directory.CACHE, {"A1": {"fetched_at": "2026-09-17", "url": PAGE},
                                      "A2": {"fetched_at": "2026-09-17", "error": "HTTP 403"}})
    line = directory.status()
    assert line.startswith("✓") and "1곳" in line and "1곳" in line and "ai-train=no" in line


@pytest.mark.parametrize("url,ok", [
    (PAGE, True), (PAGE + "?tab=news", True), (PAGE + "/", True),
    ("https://gangmom.kr/institute/65b7afaeb836838137327ade", True),
    ("https://www.gangmom.kr/review/65b7afaeb836838137327ade", False),
    ("https://www.gangmom.kr/institute", False),
    ("https://blog.naver.com/x/1", False), (None, False),
])
def test_소개_페이지_링크_판별(url, ok):
    got = directory.page_url(url)
    assert bool(got) is ok
    if ok:
        assert got == ("gangmom", PAGE)


def test_public_listing_discovers_without_web_search(monkeypatch, tmp_path):
    s = FakeSession({
        'https://www.gangmom.kr/robots.txt': (200, ROBOTS_OK),
        'https://www.gangmom.kr/browse': (200, '<a href="/institute/65b7afaeb836838137327ade">소개</a><a href="/browse?page=2">다음</a>'),
        'https://www.gangmom.kr/browse?page=2': (200, '<p>없음</p>'),
        PAGE: (200, HTML),
    })
    _wire(monkeypatch, tmp_path, s)
    got = directory.collect([GROTON], [], live=True)
    assert got['A1']['url'] == PAGE
    assert 'https://www.gangmom.kr/browse?page=2' in s.calls
    notes = directory.source_notes([GROTON])
    assert notes[0]['notes'][0]['kind'] == 'directory'
    assert '아이가 즐겁게' not in str(notes)


def test_known_directory_is_revisited_without_new_mention(monkeypatch, tmp_path):
    import json
    s = FakeSession({'https://www.gangmom.kr/robots.txt': (200, ROBOTS_OK), PAGE: (200, HTML)})
    _wire(monkeypatch, tmp_path, s)
    directory.CACHE.write_text(json.dumps({'A1': {'url': PAGE, 'fetched_at': '2020-01-01'}}))
    assert directory.collect([GROTON], [], live=True)['A1']['url'] == PAGE


def test_published_sources_are_rechecked_when_ci_cache_is_missing(monkeypatch, tmp_path):
    import json
    s = FakeSession({'https://www.gangmom.kr/robots.txt': (200, ROBOTS_OK), PAGE: (200, HTML)})
    _wire(monkeypatch, tmp_path, s)
    directory.PUBLISHED.write_text(json.dumps([{'academyId':'A1','notes':[{'url':PAGE}]}]))
    assert directory.collect([GROTON], [], live=True)['A1']['url'] == PAGE
    assert PAGE in s.calls
