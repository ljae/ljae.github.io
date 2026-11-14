"""누적 갱신에서 잘못된 순위·품질 이력이 남지 않도록 검증한다."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import config, history, ranking_quality, scoring


def test_same_day_unranking_removes_stale_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json")
    academies = [{"id": "A", "region_id": "daechi", "subjects": ["math"]}]
    scores = {"A": {"is_ranked": True, "total": 65, "rank_in_region": 1,
                    "sample_size": 12, "subject": "math", "region_ranked_count": 3}}
    history.record(academies, scores, today="2026-09-16")
    hist = history.record(academies, scores, today="2026-09-17")
    assert hist["academies"]["A"]["2026-09-17"]["version"] == scoring.SCORING_VERSION
    assert hist["academies"]["A"]["2026-09-17"]["cohortSize"] == 3
    scores["A"]["is_ranked"] = False
    hist = history.record(academies, scores, today="2026-09-17")
    assert list(hist["academies"]["A"]) == ["2026-09-16"]
    assert history.payload() == hist


def test_history_retention_uses_calendar_days():
    hist = {"academies": {"old": {"2025-01-01": {}},
                          "A": {"2026-03-21": {}, "2026-03-22": {}, "2026-09-17": {}}},
            "schools": {"S": {"2025-01-01": {}}}}
    history._prune(hist, "2026-09-17")
    assert hist == {"academies": {"A": {"2026-03-22": {}, "2026-09-17": {}}}, "schools": {}}


def test_quality_measures_valid_publication_dates_and_subjects(monkeypatch):
    from datetime import date
    monkeypatch.setattr(scoring, "TODAY", date(2026, 9, 17))
    report = ranking_quality.summarize(
        [{"id": "A", "region_id": "daechi"}],
        [{"posted_at": "2026-09-01", "source": "blog"},
         {"posted_at": "2026-09-01", "date_source": "discovery"},
         {"posted_at": "2027-01-01"}, {"posted_at": "bad-date"},
         {"posted_at": "2026-09-01", "is_excluded": True}],
        {"A": {"math": {"sample_size": 12, "is_ranked": True, "is_complete": True},
               "science": {"sample_size": 1, "is_ranked": False, "is_complete": False}}})
    assert report["mentions"] == 5
    assert report["validMentions"] == 4
    assert report["datedShare"] == 0.25
    assert report["cohorts"]["daechi:math"]["ranked"] == 1
    assert report["cohorts"]["daechi:science"]["incomplete"] == 1
    assert ranking_quality.summarize([], [], {})["datedShare"] is None


def test_quality_history_detects_regression_and_replaces_same_day(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path)
    report = {"version": scoring.SCORING_VERSION, "validMentions": 100,
              "datedShare": 0.5, "cohorts": {"daechi:math": {"ranked": 3}}}
    ranking_quality.record(report, "2025-01-01")
    ranking_quality.record(report, "2026-09-16")
    new = dict(report, validMentions=80, datedShare=0.3, cohorts={})
    ranking_quality.record(new, "2026-09-17")
    output = capsys.readouterr().out
    assert "확인율 하락" in output and "순위 대상 감소" in output
    result = ranking_quality.record(report, "2026-09-17")
    assert set(result) == {"2026-09-16", "2026-09-17"}
    assert result["2026-09-17"]["validMentions"] == 100
    assert json.loads((tmp_path / "ranking_quality.json").read_text()) == result


def test_quality_corrupt_history_is_not_overwritten(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path)
    path = tmp_path / "ranking_quality.json"
    path.write_text("broken")
    with pytest.raises(ValueError):
        ranking_quality.record({}, "2026-09-17")
    assert path.read_text() == "broken"


def test_brief_compares_only_within_the_same_cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json")
    monkeypatch.setattr(config, "regions", lambda: [{"id": "daechi", "name_ko": "대치"}])
    def row(rank, subject="math", version="v1"):
        return {"r": rank, "t": 50.0, "n": 12, "subject": subject,
                "region": "daechi", "version": version}
    (tmp_path / "history.json").write_text(json.dumps({"schools": {}, "academies": {
        "A": {"2026-11-13": row(2), "2026-11-14": row(1)},
        "B": {"2026-11-13": row(1), "2026-11-14": row(2)},
        "C": {"2026-11-13": row(9), "2026-11-14": row(4)},
        "D": {"2026-11-13": row(3)},
        "E": {"2026-11-14": row(5)},
        "F": {"2026-11-13": row(7, "english"), "2026-11-14": row(3)},
    }}), encoding="utf-8")
    b = history.brief([{"id": "A", "name": "가나"}, {"id": "C", "display_name": "다라 (대치동)"}],
                      "2026-11-14T19:00:00+00:00")
    assert (b["day"], b["previousDay"], b["ranked"], b["rankedBefore"]) == (
        "2026-11-14", "2026-11-13", 5, 5)
    # F 는 과목이 바뀌어 견줄 수 없다 — 새로 들어온 것으로 센다.
    assert (b["entered"], b["left"], b["moved"]) == (2, 1, 3)
    assert b["newFirsts"] == [{"name": "가나", "region": "대치", "subject": "수학", "from": 2, "to": 1}]
    assert b["topRises"] == [{"name": "다라 (대치동)", "region": "대치", "subject": "수학", "from": 9, "to": 4}]
    assert b["scoringChanged"] is False


def test_brief_without_history_reports_no_day(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json")
    assert history.brief([])["day"] is None
