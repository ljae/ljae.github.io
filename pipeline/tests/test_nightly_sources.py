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


@pytest.mark.parametrize('status', ['disabled', 'rate_limited'])
def test_daum_failure_is_visible_even_when_naver_succeeded(status):
    rows = health()
    rows['daum_cafe']['status'] = status
    assert 'source_unavailable:daum_cafe' in source_health.collection_problems(
        rows, STARTED, now=NOW)


def test_unreachable_daum_publishes_on_naver_alone_with_a_warning():
    """2026-11-20: 러너에서 다음이 통째로 안 닿아 한 회차가 사라졌다."""
    rows = health()
    for name in ('daum_cafe', 'daum_blog', 'daum_web'):
        rows[name].update(status='network_error', requests=5, errors=5)
    assert source_health.collection_problems(rows, STARTED, now=NOW) == []
    assert source_health.collection_warnings(rows, STARTED, now=NOW) == [
        'source_unreachable:daum_cafe', 'source_unreachable:daum_blog',
        'source_unreachable:daum_web']


@pytest.mark.parametrize('source', ['naver_cafe', 'naver_blog'])
def test_unreachable_naver_still_blocks_publication(source):
    rows = health()
    rows[source]['status'] = 'network_error'
    assert 'source_unavailable:' + source in source_health.collection_problems(
        rows, STARTED, now=NOW)


def test_partial_naver_outage_publishes_with_a_warning():
    """2026-11-24: 네이버가 13분 '서비스 예외'·연결 실패를 냈다. 요청의 80%가
    성공했는데 마지막 요청이 실패라는 이유로 게시가 막혔다."""
    rows = health()
    rows['naver_cafe'].update(status='network_error', requests=1436, errors=285,
                              results=21459,
                              failures={'server_error': 278, 'network_error': 7})
    assert source_health.collection_problems(rows, STARTED, now=NOW) == []
    assert source_health.collection_warnings(rows, STARTED, now=NOW) == [
        'source_degraded:naver_cafe']


@pytest.mark.parametrize('failures,errors', [
    ({'server_error': 8}, 8),                       # 성공이 절반 미만
    ({'server_error': 1, 'disabled': 1}, 2),        # 키 거부가 섞임
    ({'rate_limited': 2}, 2),                       # 한도는 일시 장애가 아니다
    (None, 2),                                      # 실패 종류를 모름
])
def test_naver_outage_still_blocks_when_not_clearly_partial(failures, errors):
    rows = health()
    rows['naver_blog'].update(status='server_error', requests=10, errors=errors)
    if failures is not None:
        rows['naver_blog']['failures'] = failures
    assert 'source_unavailable:naver_blog' in source_health.collection_problems(
        rows, STARTED, now=NOW)


def test_record_counts_failure_kinds():
    source_health.reset()
    for status in ('available', 'server_error', 'network_error', 'server_error'):
        source_health.record('naver_web', status)
    row = source_health._rows['naver_web']
    source_health.reset()
    assert row['errors'] == 3 and row['failures'] == {'server_error': 2, 'network_error': 1}


def test_unreachable_daum_from_an_older_run_or_never_tried_still_blocks():
    rows = health()
    rows['daum_cafe'].update(status='network_error',
                             checkedAt=(STARTED - timedelta(seconds=1)).isoformat())
    rows['daum_blog'].update(status='network_error', requests=0)
    problems = source_health.collection_problems(rows, STARTED, now=NOW)
    assert 'not_checked_this_run:daum_cafe' in problems
    assert 'source_unavailable:daum_blog' in problems


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
