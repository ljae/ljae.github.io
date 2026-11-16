"""Nightly success requires new Naver and Daum observations, including empty searches."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from pipeline.edutree import source_health


NOW = datetime(2026, 11, 16, 17, tzinfo=timezone.utc)
STARTED = NOW - timedelta(hours=3)
SOURCES = ('naver_cafe', 'naver_blog', 'daum_cafe', 'daum_blog', 'daum_web')


def health():
    return {name: {'status': 'available', 'requests': 1, 'results': 0,
                   'errors': 0, 'checkedAt': NOW.isoformat()}
            for name in SOURCES}


def test_live_zero_results_are_successful_checks():
    assert source_health.collection_problems(health(), STARTED, now=NOW) == []


@pytest.mark.parametrize('source', SOURCES)
def test_old_success_cannot_stand_in_for_tonights_collection(source):
    rows = health()
    rows[source]['checkedAt'] = (STARTED - timedelta(seconds=1)).isoformat()
    assert 'not_checked_this_run:' + source in source_health.collection_problems(
        rows, STARTED, now=NOW)


@pytest.mark.parametrize('status', ['disabled', 'rate_limited', 'network_error'])
def test_daum_failure_is_visible_even_when_naver_succeeded(status):
    rows = health()
    rows['daum_cafe']['status'] = status
    assert 'source_unavailable:daum_cafe' in source_health.collection_problems(
        rows, STARTED, now=NOW)


@pytest.mark.parametrize('value', [None, '', '2026-11-16', 'bad', 123])
def test_missing_or_invalid_source_dates_fail_closed(value):
    rows = health()
    rows['daum_blog']['checkedAt'] = value
    assert 'not_checked_this_run:daum_blog' in source_health.collection_problems(
        rows, STARTED, now=NOW)


def test_missing_sources_requests_and_future_dates_fail_closed():
    rows = health()
    del rows['daum_web']
    rows['daum_cafe']['requests'] = 0
    rows['naver_blog']['checkedAt'] = (NOW + timedelta(hours=1)).isoformat()
    problems = source_health.collection_problems(rows, STARTED, now=NOW)
    assert 'source_unavailable:daum_web' in problems
    assert 'source_unavailable:daum_cafe' in problems
    assert 'not_checked_this_run:naver_blog' in problems


def test_cli_rejects_missing_keys_before_starting_and_retains_check_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(source_health.config, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(source_health, 'PATH', tmp_path / 'source_health.json')
    monkeypatch.setattr(source_health.config, 'HAS_NAVER', True)
    monkeypatch.setattr(source_health.config, 'HAS_NEIS', True)
    monkeypatch.setattr(source_health.config, 'HAS_DAUM', False)
    assert source_health.main(['start']) == 1
    assert not (tmp_path / 'nightly-source-start.json').exists()
    monkeypatch.setattr(source_health.config, 'HAS_DAUM', True)
    assert source_health.main(['start']) == 0
    started = json.loads((tmp_path / 'nightly-source-start.json').read_text())['startedAt']
    rows = health()
    for row in rows.values():
        row['checkedAt'] = started
    source_health.PATH.write_text(json.dumps(rows))
    assert source_health.main(['check']) == 0
    del rows['daum_cafe']
    source_health.PATH.write_text(json.dumps(rows))
    assert source_health.main(['check']) == 1
    report = json.loads((tmp_path / 'nightly-source-check.json').read_text())
    assert report['healthy'] is False
    assert 'source_unavailable:daum_cafe' in report['problems']
