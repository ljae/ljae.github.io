"""An optional body backlog must not consume the whole nightly CI job."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edutree import blog


def mention(number, **fields):
    return {"source": "naver_blog", "source_url": f"https://blog.naver.com/parent/{number}",
            "snippet": "검색 결과 스니펫", "academy_key": "A", **fields}


@pytest.fixture
def transport(tmp_path, monkeypatch):
    monkeypatch.setattr(blog.config, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("OPENEDU_BLOG_PER_RUN", raising=False)
    monkeypatch.delenv("OPENEDU_BLOG_BUDGET_SECONDS", raising=False)
    monkeypatch.setattr(blog, "SLEEP", 0)
    calls = []
    def get(url, **kwargs):
        params = parse_qs(urlsplit(url).query)
        calls.append(params["logNo"][0])
        assert kwargs["timeout"] == blog.TIMEOUT
        return SimpleNamespace(status_code=200, text='<div class="se-main-container"><p>' +
                               "우리 아이가 다니는 학원 수업과 숙제를 설명하는 실제 공개 후기입니다. " * 3 + '</p></div>')
    monkeypatch.setattr(blog.requests, "get", get)
    return tmp_path, calls, get


def test_default_budget_is_300_documents_even_with_large_backlog(transport):
    directory, calls, _ = transport
    rows = [mention(number) for number in range(1, 1001)]
    assert blog.enrich(rows, workers=1) == 300
    assert len(calls) == len(set(calls)) == 300
    assert len(json.loads((directory / "blog_texts.json").read_text())) == 300
    assert rows[300]["snippet"] == "검색 결과 스니펫"


def test_canonical_url_dedup_retains_every_academy_evidence_row(transport):
    _, calls, _ = transport
    rows = [mention(123), mention(123, academy_key="B"),
            mention(123, source_url="http://m.blog.naver.com/parent/123?from=search"),
            mention(123, source_url="https://blog.naver.com/PostView.naver?blogId=parent&logNo=123")]
    assert blog.enrich(rows) == 4
    assert calls == ["123"]
    assert rows[0]["academy_key"] == "A" and rows[1]["academy_key"] == "B"
    assert all(row["full_text_length"] > 60 for row in rows)


def test_legacy_mobile_cache_satisfies_canonical_document_without_new_request(transport):
    directory, calls, _ = transport
    (directory / "blog_texts.json").write_text(json.dumps({
        "https://m.blog.naver.com/parent/123?old=tracking": {"text": "보존한 본문", "length": 100}}))
    assert blog.enrich([mention(123)]) == 1
    assert calls == []


def test_explicit_zero_means_no_requests_but_still_uses_cache(transport, monkeypatch):
    directory, calls, _ = transport
    monkeypatch.setenv("OPENEDU_BLOG_PER_RUN", "500")
    (directory / "blog_texts.json").write_text(json.dumps({
        "https://blog.naver.com/parent/1": {"text": "기존 본문", "length": 100}}))
    rows = [mention(1), mention(2)]
    assert blog.enrich(rows, limit=0) == 1
    assert calls == []
    assert not (directory / "blog_failures.json").exists()


@pytest.mark.parametrize("configured,expected", [("3", 3), ("-50", 0), ("invalid", 300), ("100000", 2000)])
def test_environment_request_limit_is_bounded(transport, monkeypatch, configured, expected):
    _, calls, _ = transport
    monkeypatch.setenv("OPENEDU_BLOG_PER_RUN", configured)
    assert blog.enrich([mention(n) for n in range(1, 2005)], workers=1) == expected
    assert len(calls) == expected


def test_wall_budget_stops_new_dispatch_and_preserves_finished_requests(transport, monkeypatch):
    directory, calls, original = transport
    clock = [0.0]
    monkeypatch.setenv("OPENEDU_BLOG_BUDGET_SECONDS", "8")
    monkeypatch.setattr(blog.time, "monotonic", lambda: clock[0])
    def delayed(url, **kwargs):
        clock[0] += 5
        return original(url, **kwargs)
    monkeypatch.setattr(blog.requests, "get", delayed)
    assert blog.enrich([mention(n) for n in range(1, 20)], workers=1) == 2
    assert calls == ["1", "2"]
    assert len(json.loads((directory / "blog_texts.json").read_text())) == 2


def test_environment_time_budget_has_a_hard_ceiling(transport, monkeypatch):
    _, calls, original = transport
    clock = [0.0]
    monkeypatch.setenv("OPENEDU_BLOG_BUDGET_SECONDS", "999999999")
    monkeypatch.setattr(blog.time, "monotonic", lambda: clock[0])
    def delayed(url, **kwargs):
        clock[0] += 1000
        return original(url, **kwargs)
    monkeypatch.setattr(blog.requests, "get", delayed)
    assert blog.enrich([mention(n) for n in range(1, 20)], workers=1) == 2
    assert len(calls) == 2


def test_executor_never_accumulates_an_unbounded_future_queue(transport, monkeypatch):
    _, calls, _ = transport
    real_wait = blog.wait
    sizes = []
    def observe(futures, **kwargs):
        sizes.append(len(futures))
        return real_wait(futures, **kwargs)
    monkeypatch.setattr(blog, "wait", observe)
    assert blog.enrich([mention(n) for n in range(1, 201)], workers=3) == 200
    assert len(calls) == 200
    assert sizes and max(sizes) <= 3


def test_successful_bodies_checkpoint_every_50_completions(transport, monkeypatch):
    directory, _, _ = transport
    real_save = blog._save_json
    checkpoints = []
    def save(path, data):
        real_save(path, data)
        if path.name == "blog_texts.json":
            checkpoints.append(len(json.loads(path.read_text())))
    monkeypatch.setattr(blog, "_save_json", save)
    assert blog.enrich([mention(n) for n in range(1, 56)], workers=1) == 55
    assert checkpoints == [50, 55]
    assert not list(directory.glob("*.tmp"))


def test_completed_downloads_survive_interruption_before_next_checkpoint(transport, monkeypatch):
    directory, calls, original = transport
    def interrupted(url, **kwargs):
        if len(calls) == 2:
            raise KeyboardInterrupt
        return original(url, **kwargs)
    monkeypatch.setattr(blog.requests, "get", interrupted)
    with pytest.raises(KeyboardInterrupt):
        blog.enrich([mention(n) for n in range(1, 10)], workers=1)
    saved = json.loads((directory / "blog_texts.json").read_text())
    assert len(saved) == 2
    assert "https://blog.naver.com/parent/1" in saved
    assert "https://blog.naver.com/parent/2" in saved


def test_interrupted_atomic_write_does_not_destroy_previous_checkpoint(transport, monkeypatch):
    directory, _, _ = transport
    path = directory / "blog_texts.json"
    path.write_text('{"old": "preserved"}')
    def interrupted(data, file, **kwargs):
        file.write('{"unfinished":')
        raise KeyboardInterrupt
    monkeypatch.setattr(blog.json, "dump", interrupted)
    with pytest.raises(KeyboardInterrupt):
        blog._save_json(path, {"new": "unfinished"})
    assert json.loads(path.read_text()) == {"old": "preserved"}
    assert not list(directory.glob("*.tmp"))


def test_failed_documents_wait_seven_days_and_do_not_starve_new_documents(transport, monkeypatch):
    directory, calls, original = transport
    def unavailable(url, **kwargs):
        if parse_qs(urlsplit(url).query)["logNo"][0] == "1":
            calls.append("1")
            return SimpleNamespace(status_code=404, text="")
        return original(url, **kwargs)
    monkeypatch.setattr(blog.requests, "get", unavailable)
    assert blog.enrich([mention(1), mention(2)], limit=1, workers=1) == 0
    assert calls == ["1"]
    assert blog.enrich([mention(1), mention(2)], limit=1, workers=1) == 1
    assert calls == ["1", "2"]
    path = directory / "blog_failures.json"
    failed = json.loads(path.read_text())
    failed["https://blog.naver.com/parent/1"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    path.write_text(json.dumps(failed))
    monkeypatch.setattr(blog.requests, "get", original)
    assert blog.enrich([mention(1)], workers=1) == 1
    assert calls == ["1", "2", "1"]
    assert json.loads(path.read_text()) == {}


def test_browser_results_do_not_inherit_a_canonical_cached_body(transport):
    directory, calls, _ = transport
    (directory / "blog_texts.json").write_text(json.dumps({
        "https://m.blog.naver.com/parent/123": {"text": "본문", "length": 100}}))
    row = mention(123, collector="ego_lite")
    assert blog.enrich([row]) == 0
    assert row["snippet"] == "검색 결과 스니펫" and not calls


@pytest.mark.parametrize("url", ["https://evil.test/blog.naver.com/parent/123", "https://cafe.naver.com/parent/123"])
def test_non_blog_documents_never_enter_body_queue(transport, url):
    _, calls, _ = transport
    assert blog.enrich([mention(123, source_url=url)]) == 0
    assert calls == []
