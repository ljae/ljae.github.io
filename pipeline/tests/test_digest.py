"""대치 학년 구간별 아침 소식·한 달 일정 — 단정하지 않을 것을 단정하지 않는지 본다."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import digest

TODAY = date(2026, 11, 15)


def row(key, region="daechi", opened="20261110", **kw):
    return {"id": key, "name": f"학원{key}", "regionId": region,
            "establishedOn": opened, **kw}


def scored(key, total, bands, subject="math", sample=20, ranked=True, by_subject=None):
    s = {"total": total, "sampleSize": sample, "isRanked": ranked}
    return {"id": key, "name": f"학원{key}", "regionId": "daechi", "subjects": [subject],
            "gradeBands": bands, "gradeBandsBySubject": by_subject or {},
            "score": s, "subjectScores": {subject: s}}


# ── 랭킹: 화면의 ranking() 과 같은 순서 ──────────────────────────
def test_band_ranks_follow_the_app_ordering():
    rows = [scored("thin", 90, ["elem_high"], sample=2, ranked=False),
            scored("B", 60, ["elem_high"]), scored("A", 60, ["elem_high"]),
            scored("C", 70, ["elem_high"]),
            scored("none", 99, ["elem_high"], sample=0),          # 표본 0 은 줄에 없다
            scored("low", 99, ["elem_low"]),                       # 다른 방
            scored("unknown", 99, ["elem_high"], by_subject={"math": []})]  # 과목별 미확인
    got = [r["id"] for r in digest.band_ranks(rows)[("math", "elem_high")]]
    assert got == ["C", "A", "B", "thin"]


def test_moves_are_per_room_and_skip_thin_evidence():
    before = [scored("A", 70, ["elem_high", "middle"]), scored("B", 60, ["elem_high"]),
              scored("C", 50, ["elem_high"]), scored("D", 40, ["elem_high"]),
              scored("E", 30, ["elem_high"])]
    now = [scored("A", 50, ["elem_high", "middle"]), scored("B", 60, ["elem_high"]),
           scored("C", 45, ["elem_high"]), scored("D", 41, ["elem_high"]),
           scored("E", 80, ["elem_high"])]
    m = digest.band_moves(now, before)
    assert [(x["name"], x["from"], x["to"]) for x in m["elem_high"]["newFirsts"]] == [("학원E", 5, 1)]
    assert m["middle"]["newFirsts"] == [] and m["middle"]["rises"] == []   # 혼자라 그대로 1위
    assert m["elem_low"] == {"newFirsts": [], "rises": []}


def test_no_previous_export_means_no_moves():
    assert digest.band_moves([scored("A", 70, ["high"])], [])["high"]["newFirsts"] == []


# ── 등록부 ──────────────────────────────────────────────────────
def test_new_needs_a_recent_opening_and_no_prior_presence():
    before = [row("A"), row("B", registrationIds=["C"])]
    now = [row("A"), row("B", registrationIds=["C"]), row("C"), row("D", gradeBands=["middle"]),
           row("E", opened="20190301"), row("F", region="mokdong")]
    got = digest.registry_changes(now, before, TODAY)
    assert [(x["name"], x["bands"]) for x in got["new"]] == [("학원D", ["middle"])]


def test_gone_excludes_merges_and_bulk_drops_are_not_listed():
    got = digest.registry_changes([row("A", registrationIds=["B"])],
                                  [row("A"), row("B"), row("C")], TODAY)
    assert [x["name"] for x in got["gone"]] == ["학원C"]
    many = [row(str(i)) for i in range(digest.GONE_BULK + 1)]
    got = digest.registry_changes([], many, TODAY)
    assert got["goneBulk"] and got["gone"] == []


def test_first_export_reports_nothing_rather_than_everything_as_new():
    got = digest.registry_changes([row("A")], [], TODAY)
    assert got["new"] == [] and got["goneCount"] == 0


# ── 일정 ────────────────────────────────────────────────────────
def ev(title, url, posted="2026-11-14", snippet="", source="naver_blog"):
    return {"title": title, "source_url": url, "posted_at": posted,
            "snippet": snippet, "source": source}


def test_dates_are_read_within_a_month_and_roll_into_next_year():
    assert digest.event_dates("11/25 · 12/6 · 12/20 설명회", TODAY) == ["2026-11-25", "2026-12-06"]
    assert digest.event_dates("1월 9일 개강", date(2026, 12, 20)) == ["2027-01-09"]
    assert digest.event_dates("2026.11.10 마감", TODAY) == []


def test_classify_filters_place_branch_kind_and_the_preschool_test_ban():
    rows = [
        ev("대치 수학학원 겨울방학 설명회 안내", "u1", snippet="11월 28일(토) 오후 2시"),
        ev("분당 영어학원 설명회", "u2"),
        ev("[대치명인성북]예비고2입시전략설명회", "u3"),
        ev("대치동 영어 레벨테스트, 합격만 생각하십니까?", "u4"),
        ev("대치 어학원 예비초 레벨테스트 접수 안내", "u5"),     # 10/1 부터 금지
        ev("대치 어학원 초3 레벨테스트 일정 안내", "u6", snippet="12월 5일"),
        ev("대치 중등 개강 안내", "u7", posted="2026-09-01"),     # 한 달보다 오래됨
    ]
    got, banned = digest.classify(rows, TODAY)
    assert banned == 1
    assert [(e["url"], e["kind"], e["bands"], e["dates"]) for e in got] == [
        ("u1", "session", [], ["2026-11-28"]),
        ("u6", "test", ["elem_low"], ["2026-12-05"]),
    ]


def test_calendar_accumulates_and_drops_only_past_dates():
    prev = [{"url": "old", "title": "a", "dates": ["2026-11-10"]},
            {"url": "keep", "title": "b", "dates": ["2026-11-10", "2026-12-01"]}]
    found = [{"url": "new", "title": "c", "dates": ["2026-11-20"]},
             {"url": "nodate", "title": "d", "dates": []}]
    got = digest.merge_calendar(prev, found, TODAY)
    assert [(e["url"], e["dates"]) for e in got] == [("new", ["2026-11-20"]),
                                                      ("keep", ["2026-12-01"])]


def test_rooms_split_by_band_and_share_unbanded_items():
    cal = [{"url": "all", "title": "공통", "dates": ["2026-11-18"], "bands": []},
           {"url": "hi", "title": "고등", "dates": ["2026-11-19"], "bands": ["high"]},
           {"url": "later", "title": "나중", "dates": ["2026-12-10"], "bands": ["high"]}]
    news = [{"url": "hi", "title": "고등", "bands": ["high"]},
            {"url": "mid", "title": "중등", "bands": ["middle"]}]
    reg = {"new": [{"name": "N", "bands": []}], "gone": [], "goneBulk": False}
    r = digest.rooms({}, cal, news, reg, TODAY)
    assert [e["url"] for e in r["high"]["thisWeek"]] == ["all", "hi"]
    assert r["high"]["news"] == []                      # 이번 주 일정에 이미 있다
    assert [e["url"] for e in r["middle"]["news"]] == ["mid"]
    assert [e["url"] for e in r["elem_low"]["thisWeek"]] == ["all"]
    assert all(r[b]["newAcademies"] == [{"name": "N", "bands": []}] for b in digest.BANDS)


def test_cache_runs_do_not_search_but_keep_the_calendar(monkeypatch):
    monkeypatch.setattr(digest, "LIVE_SEARCH", False)
    prev = [{"url": "keep", "title": "b", "dates": ["2026-12-01"], "bands": []}]
    brief, cal = digest.build([], [], prev, today=TODAY)
    assert brief["searched"] is False and [e["url"] for e in cal] == ["keep"]
    assert brief["rooms"]["high"]["news"] == []


# ── 공식 홈페이지 공지 ──────────────────────────────────────────
def test_homepage_notices_keep_titles_and_date_tokens_only():
    from edutree import official
    html = """<html><script>var x='설명회 12/1';</script><ul>
      <li><a>2027 겨울학기 신입생 설명회</a></li><li><span>11월 28일(토) 10:00</span></li>
      <li><a>초3 레벨테스트 접수 안내</a></li><li>12.05</li>
      <li>오시는 길</li></ul><p>본문 단락 설명회 """ + "가" * 200 + "</p></html>"
    got = official._notices(html)
    assert [n["title"] for n in got] == ["2027 겨울학기 신입생 설명회", "초3 레벨테스트 접수 안내"]
    assert got[0]["dateHints"][0].startswith("11월 28일")
    assert official._observe(html, "https://a.kr")["events"] == got


def test_homepage_events_use_academy_bands_and_respect_the_ban():
    rows = [{"id": "H", "name": "트윈클어학원", "regionId": "daechi",
             "gradeBands": ["elem_low", "elem_high"]},
            {"id": "M", "name": "목동학원", "regionId": "mokdong"}]
    cache = {"H": {"url": "https://h.kr", "checked_on": "2026-11-14", "blocked": None,
                   "observed": {"events": [
                       {"title": "겨울학기 설명회", "dateHints": ["11월 28일"]},
                       {"title": "11월 28일(토) 겨울학기 설명회 안내", "dateHints": ["11월 28일"]},
                       {"title": "예비초 레벨테스트 안내", "dateHints": ["11월 29일"]},
                       {"title": "중등 개강", "dateHints": []},                  # 날짜 없음
                       {"title": "중등 입학테스트 일정", "dateHints": ["12/3"]},
                       {"title": "2027년 분당 예비초2 입학시험 안내", "dateHints": ["12/4"]},
                       {"title": "예비초2 입학시험 안내", "dateHints": ["12/5"]}]}},
             "M": {"url": "https://m.kr", "checked_on": "2026-11-14",
                   "observed": {"events": [{"title": "설명회", "dateHints": ["11/30"]}]}}}
    got, banned = digest.homepage_events(cache, rows, TODAY)
    assert banned == 1
    assert [(e["title"], e["bands"], e["dates"]) for e in got] == [
        ("트윈클어학원 · 겨울학기 설명회", ["elem_low", "elem_high"], ["2026-11-28"]),
        ("트윈클어학원 · 중등 입학테스트 일정", ["middle"], ["2026-12-03"]),
        ("트윈클어학원 · 예비초2 입학시험 안내", ["elem_low"], ["2026-12-05"])]   # 지금 초1 — 금지 아님
    cal = digest.merge_calendar([], got, TODAY)
    assert len(cal) == 3                     # 같은 주소의 공지 둘이 서로를 덮지 않는다


def test_priority_is_the_thickest_daechi_academic_academies():
    rows = [{"id": i, "regionId": "daechi", "subjects": ["math"], "score": {"sampleSize": i}}
            for i in range(40)]
    rows += [{"id": 999, "regionId": "daechi", "subjects": ["arts"], "score": {"sampleSize": 999}},
             {"id": 998, "regionId": "mokdong", "subjects": ["math"], "score": {"sampleSize": 998}}]
    got = digest.homepage_priority(rows)
    assert len(got) == digest.PRIORITY_TOP and "39" in got and "999" not in got and "998" not in got
