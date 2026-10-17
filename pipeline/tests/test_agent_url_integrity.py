"""검색 API와 Ego Lite가 찾은 같은 카페 글은 표본 하나로 센다."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import review_integrity


@pytest.mark.parametrize("url", [
    "https://cafe.naver.com/parent_cafe/1234?art=external-search",
    "https://m.cafe.naver.com/parent_cafe/1234?tc=shared_link",
    "http://cafe.naver.com/parent_cafe/1234/#comment",
    "https://m.cafe.naver.com/parent_cafe/1234/?from=search&query=academy",
])
def test_cafe_mobile_and_tracking_variants_share_one_document(url):
    canonical = review_integrity.canonical_document
    assert canonical(url) == canonical("https://cafe.naver.com/parent_cafe/1234")


def test_cafe_cross_collector_duplicates_do_not_inflate_samples():
    rows = [
        {"academy_key": "A", "source": "naver_cafe", "source_url":
         "https://cafe.naver.com/parents/123"},
        {"academy_key": "A", "source": "naver_cafe", "collector": "ego_lite",
         "source_url": "https://m.cafe.naver.com/parents/123?tc=shared_link"},
        {"academy_key": "B", "source": "naver_cafe", "collector": "ego_lite",
         "source_url": "https://m.cafe.naver.com/parents/123"},
    ]
    review_integrity.flag_duplicate_urls(rows)
    assert not rows[0].get("is_excluded")
    assert rows[1]["exclude_reason"] == "duplicate_url"
    assert not rows[2].get("is_excluded")  # 한 글의 다른 학원 귀속은 별도 게이트의 일이다.


def test_cafe_identity_keeps_cafe_and_article_ids_distinct():
    canonical = review_integrity.canonical_document
    urls = ["https://cafe.naver.com/parents/123",
            "https://cafe.naver.com/parents/124",
            "https://cafe.naver.com/otherparents/123"]
    assert len({canonical(url) for url in urls}) == len(urls)


@pytest.mark.parametrize("url", [
    "https://cafe.naver.com/parents?articleid=123",
    "https://cafe.naver.com/parents/123/other?ref=search",
    "https://cafe.naver.com.example.org/parents/123?ref=search",
    "https://example.org/parents/123?ref=search",
    "https://cafe.naver.com/ArticleRead.nhn?clubid=parents&articleid=123",
    "https://cafe.naver.com/ArticleRead.nhn?clubid=42",
    "https://cafe.naver.com/ca-fe/cafes/parents/articles/123",
])
def test_unconfirmed_cafe_shapes_and_hosts_keep_original_identity(url):
    assert review_integrity.canonical_document(url) == url


def test_numeric_cafe_slug_does_not_imply_numeric_club_id():
    canonical = review_integrity.canonical_document
    assert canonical("https://cafe.naver.com/42/123") != canonical(
        "https://cafe.naver.com/ArticleRead.nhn?clubid=42&articleid=123")


@pytest.mark.parametrize("url", [
    "https://cafe.naver.com/ArticleRead.nhn?clubid=42&articleid=123&ref=search",
    "https://m.cafe.naver.com/ArticleRead.naver?articleid=123&clubid=42",
    "https://cafe.naver.com/ca-fe/web/cafes/42/articles/123?ref=search",
    "https://m.cafe.naver.com/ca-fe/cafes/42/articles/123/#comment",
])
def test_numeric_cafe_variants_match_collector_document_identity(url):
    from edutree import ego_reviews
    canonical = review_integrity.canonical_document
    collected = ego_reviews.canonical_url(url)
    assert collected == "https://cafe.naver.com/ca-fe/cafes/42/articles/123"
    assert canonical(url) == canonical(collected) == "naver-cafe:club:42:123"


def test_numeric_cafe_cross_collector_variants_count_only_once():
    rows = [{"academy_key": "A", "source_url": url} for url in [
        "https://cafe.naver.com/ArticleRead.nhn?clubid=42&articleid=123",
        "https://cafe.naver.com/ca-fe/cafes/42/articles/123",
        "https://m.cafe.naver.com/ca-fe/web/cafes/42/articles/123",
        "https://cafe.naver.com/ca-fe/cafes/43/articles/123",
        "https://cafe.naver.com/ca-fe/cafes/42/articles/124",
    ]]
    review_integrity.flag_duplicate_urls(rows)
    assert [bool(row.get("is_excluded")) for row in rows] == [False, True, True, False, False]
