"""재채점은 저장된 본문만 반영하고 누락된 글을 수집하지 않는다."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import blog


def test_cached_enrichment_preserves_text_without_fetching(tmp_path, monkeypatch):
    monkeypatch.setattr(blog.config, "CACHE_DIR", tmp_path)
    path = tmp_path / "blog_texts.json"
    path.write_text(json.dumps({"cached": {
        "text": "저장된 학원 후기", "length": 100, "posted_at": "2026-09-01",
    }}))
    before = path.read_bytes()

    def unexpected_fetch(url):
        raise AssertionError(f"캐시 재채점 중 외부 수집: {url}")

    monkeypatch.setattr(blog, "fetch_post", unexpected_fetch)
    mentions = [
        {"source": "naver_blog", "source_url": "cached", "snippet": "짧은 글"},
        {"source": "naver_blog", "source_url": "missing", "snippet": "원래 글"},
    ]
    assert blog.enrich(mentions, cached_only=True) == 1
    assert mentions[0]["snippet"] == "저장된 학원 후기"
    assert mentions[0]["posted_at"] == "2026-09-01"
    assert mentions[1]["snippet"] == "원래 글"
    assert path.read_bytes() == before
