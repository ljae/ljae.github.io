"""수집기가 바뀌거나 동시에 저장해도 원본과 수집 경로를 함께 보존한다."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import blog, config, mention_store


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mention_store, "PATH", tmp_path / "mentions.json.gz")
    return tmp_path


def _row(snippet, **fields):
    return {"academy_key": "A", "source": "naver_blog",
            "source_url": "https://blog.naver.com/parent/123", "url_hash": "123",
            "title": "다라학원 후기", "snippet": snippet, **fields}


def test_browser_snippet_replaces_api_provenance_and_cannot_fetch_body(store, monkeypatch):
    mention_store.merge([_row("짧은 API 스니펫", query="옛 검색", collected_at="2026-09-01")], quiet=True)
    browser = _row("더 긴 브라우저 검색 결과 스니펫입니다", collector="ego_lite",
                   search_url="https://search.naver.com/search.naver?query=test",
                   query="새 검색", collected_at="2026-10-17")
    mention_store.merge([browser], quiet=True)
    saved = mention_store.rows()
    for field in ("snippet", "collector", "search_url", "query", "collected_at"):
        assert saved[0][field] == browser[field]
    monkeypatch.setattr(blog, "fetch_post", lambda _: pytest.fail("browser-only body fetch"))
    assert blog.enrich(saved) == 0


def test_api_snippet_replaces_browser_provenance_without_stale_search_link(store):
    mention_store.merge([_row("브라우저 스니펫", collector="ego_lite",
                              search_url="https://search.naver.com/old", query="옛 검색",
                              collected_at="2026-09-01", posted_at="2026-08-01",
                              date_source="ego_search")], quiet=True)
    api = _row("API에서 다시 받은 더 긴 스니펫입니다", query="새 검색", collected_at="2026-10-17")
    saved = mention_store.merge([api], quiet=True)[0]
    assert saved["snippet"] == api["snippet"]
    assert "collector" not in saved and "search_url" not in saved
    assert saved["query"] == api["query"] and saved["collected_at"] == api["collected_at"]
    # 날짜는 스니펫 수집 경로와 별개다. 확인된 작성일의 근거를 잃지 않는다.
    assert saved["posted_at"] == "2026-08-01" and saved["date_source"] == "ego_search"


def test_shorter_incoming_snippet_does_not_change_existing_provenance(store):
    original = _row("현재 저장된 충분히 긴 API 스니펫입니다", query="기존 검색", collected_at="2026-09-01")
    mention_store.merge([original], quiet=True)
    saved = mention_store.merge([_row("짧은 글", collector="ego_lite",
                                      search_url="https://search.naver.com/new")], quiet=True)[0]
    assert saved["snippet"] == original["snippet"]
    assert saved["query"] == original["query"]
    assert "collector" not in saved and "search_url" not in saved


def test_concurrent_collectors_keep_both_batches(store, monkeypatch):
    first_loaded = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    real_load = mention_store.load

    def hold_first_load():
        rows = real_load()
        if not first_loaded.is_set():
            first_loaded.set()
            assert release_first.wait(5), "first merge was not released"
        return rows

    monkeypatch.setattr(mention_store, "load", hold_first_load)

    def second_merge():
        second_started.set()
        return mention_store.merge([_row("두 번째 수집", url_hash="456")], quiet=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(mention_store.merge, [_row("첫 번째 수집")], quiet=True)
        try:
            assert first_loaded.wait(5)
            second = pool.submit(second_merge)
            assert second_started.wait(5)
        finally:
            release_first.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert {row["url_hash"] for row in mention_store.rows()} == {"123", "456"}


def test_failed_merge_releases_store_lock_for_retry(store, monkeypatch):
    real_save = mention_store._save
    def fail(_):
        raise OSError("interrupted write")
    monkeypatch.setattr(mention_store, "_save", fail)
    with pytest.raises(OSError, match="interrupted"):
        mention_store.merge([_row("첫 시도")], quiet=True)
    monkeypatch.setattr(mention_store, "_save", real_save)
    with ThreadPoolExecutor(max_workers=1) as pool:
        rows = pool.submit(mention_store.merge, [_row("재시도")], quiet=True).result(timeout=5)
    assert rows[0]["snippet"] == "재시도"
