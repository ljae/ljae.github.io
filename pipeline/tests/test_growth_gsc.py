"""Transport pagination, authentication retry, and atomic partitions."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.growth.gsc import DATASETS, GscClient, GscError, api_snapshot, sync
from pipeline.growth.store import Store


class Response:
    def __init__(self, status, data):
        self.status_code, self.data = status, data
    def json(self):
        return self.data


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return next(self.responses)


def row(query):
    return {'keys': ['2026-09-01', query], 'clicks': 1, 'impressions': 10, 'position': 8}


def test_pagination_and_one_auth_refresh():
    session = Session([Response(401, {}),
                       Response(200, {'rows':[row('a'),row('b')], 'responseAggregationType':'byProperty'}),
                       Response(200, {'rows':[row('c')], 'responseAggregationType':'byProperty'})])
    tokens = iter(['expired','fresh'])
    client = GscClient(session=session, token_provider=lambda: next(tokens), sleep=lambda _: None)
    result = client.query_day('sc-domain:example.org','2026-09-01','query',row_limit=2)
    assert len(result['rows']) == 3
    assert session.requests[-1][1]['json']['startRow'] == 2
    assert session.requests[-1][1]['headers']['Authorization'] == 'Bearer fresh'
    assert result['dataState'] == 'final'
    assert 'sc-domain%3Aexample.org' in session.requests[0][0]


def test_quota_failure_is_bounded_and_does_not_print_response_secrets():
    session = Session([Response(429, {'secret':'never log this'}) for _ in range(5)])
    client = GscClient(session=session, token_provider=lambda: 'token', sleep=lambda _: None)
    with pytest.raises(GscError, match='QUOTA_OR_SOURCE_UNAVAILABLE') as e:
        client.query_day('sc-domain:example.org','2026-09-01','query')
    assert 'secret' not in str(e.value)
    assert len(session.requests) == 5


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
    def query_day(self, property_id, day, dataset, **kwargs):
        if self.fail and dataset == 'query_page':
            raise GscError('SOURCE_UNAVAILABLE', True)
        return {'rows':[dict(keys=[day]+['sample']*(len(DATASETS[dataset])-1),
                             clicks=1,impressions=10,position_numerator=80)],
                'aggregationType':'byProperty','dataState':'final'}


def test_day_partition_rolls_back_when_a_later_dimension_fails(tmp_path):
    store = Store(tmp_path/'ledger.sqlite')
    sync(FakeClient(),store,'sc-domain:example.org','2026-09-01','2026-09-01')
    before = store.partitions('sc-domain:example.org','web','2026-09-01','2026-09-01')
    with pytest.raises(GscError):
        sync(FakeClient(fail=True),store,'sc-domain:example.org','2026-09-01','2026-09-01')
    assert store.partitions('sc-domain:example.org','web','2026-09-01','2026-09-01') == before
    snapshot = api_snapshot(store,'sc-domain:example.org','2026-09-01','2026-09-01')
    assert snapshot['totals']['impressions'] == 10  # Six dimensions must not become 60.
    assert snapshot['source'] == 'gsc_api_final'
    with pytest.raises(ValueError,match='INCOMPLETE_PARTITION'):
        api_snapshot(store,'sc-domain:example.org','2026-09-01','2026-09-02')
    store.close()
