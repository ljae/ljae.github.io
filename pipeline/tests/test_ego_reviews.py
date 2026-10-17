"""Ego search collector privacy, failure semantics and document identity."""
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edutree import analyze, ego_reviews, naver, review_integrity


def item(**changes):
    return {"url": "https://m.blog.naver.com/parent/123?art=private-tracking",
            "title": "대치 가나다 학원 후기", "snippet": "우리 아이를 3개월 보내고 있습니다. 수업에 만족했어요.",
            "date_text": "2026. 09. 17.", **changes}


def normalized(**changes):
    return ego_reviews.normalize_item(item(**changes), academy_id="A", query="대치 가나다 후기", today=date(2026, 10, 17))


@pytest.mark.parametrize("url,expected", [
    ("https://blog.naver.com/parent/123?art=x#hash", "https://blog.naver.com/parent/123"),
    ("http://m.blog.naver.com/parent/123/", "https://blog.naver.com/parent/123"),
    ("https://blog.naver.com/PostView.naver?logNo=123&blogId=parent&x=y", "https://blog.naver.com/parent/123"),
    ("https://m.cafe.naver.com/moms/456?art=private", "https://cafe.naver.com/moms/456"),
    ("https://cafe.naver.com/ArticleRead.nhn?clubid=12&articleid=456", "https://cafe.naver.com/ca-fe/cafes/12/articles/456"),
    ("https://m.cafe.naver.com/ca-fe/web/cafes/12/articles/456?from=search", "https://cafe.naver.com/ca-fe/cafes/12/articles/456"),
])
def test_article_urls_are_canonical_and_tracking_free(url, expected):
    assert ego_reviews.canonical_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://blog.naver.com/parent", "https://cafe.naver.com/moms",
    "https://evil.test/?url=https://blog.naver.com/parent/123",
    "https://blog.naver.com.evil.test/parent/123", "javascript:alert(1)",
    "https://user:password@blog.naver.com/parent/123", "https://blog.naver.com:9000/parent/123",
    "https://blog.naver.com/PostView.naver?blogId=parent&logNo=not-an-article",
    "https://blog.naver.com/parent/123\n", None,
])
def test_profiles_external_urls_and_malformed_links_are_rejected(url):
    assert ego_reviews.canonical_url(url) is None


@pytest.mark.parametrize("value,expected", [
    ("2026. 09. 17.", "2026-09-17"), ("4일 전", "2026-10-13"),
    ("어제", "2026-10-16"), ("3시간 전", None),
    (None, None), ("", None), ("2026년에 다니기 시작했어요", None),
    ("2026.02.31.", None), ("2026.10.18.", None), ("09.17.", None),
])
def test_unknown_or_ambiguous_date_is_not_collection_day(value, expected):
    assert ego_reviews.publication_date(value, today=date(2026, 10, 17)) == expected


def test_only_bounded_snippets_and_hashed_authors_are_retained():
    row = normalized(author="원본 개인정보", author_id="raw_id", body="full body", html="<html>secret</html>",
                     snippet="긴 글 " * 1000, title="수강 후기")
    assert row["author_hash"] == naver._author_hash({"bloggerlink": "https://blog.naver.com/parent"})
    assert row["url_hash"] == naver._hash("https://blog.naver.com/parent/123")
    assert row["title"] == "수강 후기"
    assert len(row["snippet"]) <= ego_reviews.MAX_SNIPPET
    assert not {"author", "author_id", "body", "html"} & row.keys()
    assert "private-tracking" not in json.dumps(row)
    assert row["collector"] == "ego_lite"
    assert "ssc=tab.blog.all" in row["search_url"]
    assert row["academy_key"] == "A"


def test_cafe_community_is_not_an_author_and_date_is_unknown():
    row = normalized(url="https://cafe.naver.com/moms/456", date_text=None, author="수천 명이 쓰는 맘카페")
    assert row["source"] == "naver_cafe"
    assert row["author_hash"] is None and row["posted_at"] is None
    assert "date_source" not in row


def test_browser_plain_text_does_not_lose_angle_bracketed_academy_name():
    assert normalized(title="<생각하는 황소> 수강 후기")["title"] == "<생각하는 황소> 수강 후기"


def test_relative_time_near_midnight_uses_reference_timestamp():
    assert ego_reviews.publication_date("3시간 전", now=datetime(2026, 10, 17, 1, 30)) == "2026-10-16"
    assert ego_reviews.publication_date("10분 전", now=datetime(2026, 10, 17, 0, 5)) == "2026-10-16"


def test_collected_sponsored_results_remain_subject_to_existing_gates():
    row = normalized(snippet="원고료를 제공받아 작성했습니다. 3개월 다니고 있습니다.")
    assert not {"is_excluded", "sentiment", "relevance_score", "score"} & row.keys()
    assert analyze.analyze(row)["exclude_reason"] == "sponsored"
    assert review_integrity.canonical_document(row["source_url"]) == "naver-blog:parent:123"


def process(monkeypatch, payload, *, returncode=0, stderr=""):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=returncode, stdout="runtime startup\n" + ego_reviews.MARKER + json.dumps(payload), stderr=stderr)
    monkeypatch.setattr(ego_reviews.subprocess, "run", run)
    return calls


def test_process_uses_stdin_without_shell_and_deduplicates(monkeypatch):
    calls = process(monkeypatch, {"status": "ok", "rows": [item(), item(url="https://blog.naver.com/PostView.naver?blogId=parent&logNo=123")]})
    query = '학원 `touch /tmp/never` $(secret) "후기"'
    result = ego_reviews.collect(query, "A", 10)
    assert result["status"] == "ok" and len(result["rows"]) == 1
    assert calls[0][0] == ["ego-browser", "nodejs"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == 45
    config_line = calls[0][1]["input"].splitlines()[0]
    config = json.loads(config_line.removeprefix("const __EDUTREE_EGO_OPTIONS__ = ").removesuffix(";"))
    assert config["query"] == query and config["spaceId"] == 10
    assert len(calls) == 1


def test_empty_success_is_distinct_from_failure(monkeypatch):
    process(monkeypatch, {"status": "empty", "rows": []})
    result = ego_reviews.collect("후기", "A", 10)
    assert result["status"] == "empty" and result["error_code"] is None
    assert result["rows"] == []


@pytest.mark.parametrize("status", sorted(ego_reviews.FAILURES))
def test_browser_failures_never_expose_partial_rows(monkeypatch, status):
    calls = process(monkeypatch, {"status": status, "rows": [item()]})
    result = ego_reviews.collect("후기", "A", 10)
    assert result["status"] == status and result["rows"] == []
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [
    {"status": "ok", "rows": []}, {"status": "ok", "rows": [None]},
    {"status": "ok", "rows": [item(url="https://example.test/fake")]},
    {"status": "empty", "rows": [item()]}, {"status": "ok", "rows": "invalid"},
    {"status": "invented", "rows": []}, [],
])
def test_malformed_or_unusable_results_fail_closed(monkeypatch, payload):
    process(monkeypatch, payload)
    result = ego_reviews.collect("후기", "A", 10)
    assert result["status"] == "parse_error" and result["rows"] == []


@pytest.mark.parametrize("error,status", [
    (FileNotFoundError("missing"), "cli_missing"),
    (subprocess.TimeoutExpired("ego-browser", 45), "timeout"),
    (OSError("unavailable"), "browser_error"),
])
def test_process_failures(monkeypatch, error, status):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(ego_reviews.subprocess, "run", fail)
    assert ego_reviews.collect("후기", "A", 10)["status"] == status


@pytest.mark.parametrize("message,status", [
    ("TaskSpace is user-owned", "user_control"), ("space inactive", "user_control"),
    ("CAPTCHA", "blocked"), ("login required", "login_required"),
    ("operation timed out", "timeout"), ("disconnected", "browser_error"),
])
def test_cli_nonzero_result_never_counts_as_success(monkeypatch, message, status):
    process(monkeypatch, {"status": "ok", "rows": [item()]}, returncode=1, stderr=message)
    result = ego_reviews.collect("후기", "A", 10)
    assert result["status"] == status and result["rows"] == []


@pytest.mark.parametrize("kwargs", [
    {"space_id": 0}, {"space_id": True}, {"space_id": "10"},
    {"max_results": 51}, {"max_results": 0}, {"max_results": True},
    {"timeout": 0}, {"timeout": float("nan")}, {"timeout": 91},
    {"query": ""}, {"query": "x" * 301}, {"source": "web"},
])
def test_invalid_configuration_does_not_touch_browser(monkeypatch, kwargs):
    calls = process(monkeypatch, {"status": "empty", "rows": []})
    options = {"query": "후기", "academy_id": "A", "space_id": 10, **kwargs}
    with pytest.raises(ValueError):
        ego_reviews.collect(**options)
    assert not calls


def test_cafe_source_uses_grounded_tab_and_rejects_mixed_source(monkeypatch):
    calls = process(monkeypatch, {"status": "ok", "rows": [item(url="https://cafe.naver.com/moms/456"), item()]})
    result = ego_reviews.collect("후기", "A", 10, source="naver_cafe")
    assert len(result["rows"]) == 1 and result["rows"][0]["source"] == "naver_cafe"
    assert "tab.cafe.all" in calls[0][1]["input"]


def test_extra_output_without_exact_protocol_marker_is_not_success(monkeypatch):
    monkeypatch.setattr(ego_reviews.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"rows":[]}', stderr=""))
    assert ego_reviews.collect("후기", "A", 10)["status"] == "parse_error"


def test_ego_console_protocol_on_stderr_and_update_notice(monkeypatch):
    # Observed live with Ego Lite 0.5.1.13 on 2026-10-17: piped Node console
    # output goes to stderr despite a successful exit status.
    payload = ego_reviews.MARKER + json.dumps({"status": "ok", "rows": [item()]})
    monkeypatch.setattr(ego_reviews.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="", stderr="[ego-browser:notice] update available\n" + payload))
    result = ego_reviews.collect("후기", "A", 10)
    assert result["status"] == "ok" and len(result["rows"]) == 1
    assert result["update_available"] is True


def test_conflicting_protocol_messages_are_rejected(monkeypatch):
    payload = ego_reviews.MARKER + json.dumps({"status": "empty", "rows": []})
    monkeypatch.setattr(ego_reviews.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=payload, stderr=payload))
    assert ego_reviews.collect("후기", "A", 10)["status"] == "parse_error"
