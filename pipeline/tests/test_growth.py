"""Protect dataset grain, missing data, and non-causal incident reporting."""
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.growth.csv_import import read_export
from pipeline.growth.rules import analyze, detect_drop
from pipeline.growth.store import Store
from pipeline.growth.contracts import Metrics, normalize_url


def export(tmp_path, *, pages=1, malformed=False, unsafe=False):
    path = tmp_path / 'export.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('../escape.csv' if unsafe else 'Chart.csv',
                   'Date,Clicks,Impressions,CTR,Position\n2026-09-17,3,100,3%,8\n2026-09-18,2,88,2.27%,10\n')
        z.writestr('Queries.csv', 'Top queries,Clicks,Impressions,CTR,Position\n테스트학원,0,13,0%,9\n')
        body = io.StringIO()
        w = csv.writer(body)
        w.writerow(['Top pages', 'Clicks', 'Impressions', 'CTR', 'Position'])
        for i in range(pages):
            w.writerow([f'https://example.org/a/{i}.html', 0, 'bad' if malformed else 1, '0%', 9])
        z.writestr('Pages.csv', body.getvalue())
        z.writestr('Filters.csv', 'Filter,Value\nSearch type,Web (text-based)\nDate,Last 28 days\n')
    return path


def test_period_tables_are_not_added_to_daily_totals(tmp_path):
    s = read_export(export(tmp_path), 'sc-domain:example.org')
    report = analyze(s)
    assert report['totals']['clicks'] == 5
    assert report['totals']['impressions'] == 188
    assert s['datasets']['query']['grain'] == 'period'
    assert report['quality']['queryClickCoverage'] == 0
    assert report['evaluation'] == 'insufficient_evidence'
    assert report['totals']['position'] == pytest.approx((100*8+88*10)/188)


def test_idempotency_and_bad_import_preserves_previous_snapshot(tmp_path):
    store = Store(tmp_path / 'private' / 'ledger.db')
    s = read_export(export(tmp_path), 'sc-domain:example.org')
    assert store.import_snapshot(s)[1] is True
    assert store.import_snapshot(s)[1] is False
    with pytest.raises(ValueError):
        store.import_snapshot(read_export(export(tmp_path, malformed=True), 'sc-domain:example.org'))
    assert len(store.snapshots('sc-domain:example.org')) == 1
    assert store.snapshots('sc-domain:example.org')[0]['totals']['impressions'] == 188
    store.close()


def test_csv_row_limit_and_zip_path_are_explicit(tmp_path):
    s = read_export(export(tmp_path, pages=1000), 'sc-domain:example.org')
    assert s['datasets']['page']['truncated']
    assert 'PAGE_ROW_LIMIT_REACHED' in s['warnings']
    with pytest.raises(ValueError, match='UNSAFE_ZIP_PATH'):
        read_export(export(tmp_path, unsafe=True), 'sc-domain:example.org')


def test_latest_revision_of_same_period_is_selected(tmp_path):
    store = Store(tmp_path / 'ledger.db')
    old = read_export(export(tmp_path), 'sc-domain:example.org', exported_at='2026-10-16T00:00:00Z')
    new = dict(old, checksum='corrected-export', exportedAt='2026-10-17T00:00:00Z')
    old_id, _ = store.import_snapshot(old)
    new_id, _ = store.import_snapshot(new)
    assert [s['id'] for s in store.snapshots(old['property'])] == [new_id, old_id]
    store.close()


def test_drop_has_evidence_but_does_not_invent_cause():
    rows = [dict(date=(date(2026, 9, 1)+timedelta(days=i)).isoformat(),
                 clicks=0, impressions=300 if i < 10 else 7,
                 position_numerator=2400 if i < 10 else 56) for i in range(24)]
    findings = detect_drop(rows)
    assert len(findings) == 1
    assert findings[0]['subjectKey'] == '2026-09-11'
    assert findings[0]['cause'] == 'insufficient_evidence'
    del rows[7]
    assert detect_drop(rows) == []  # Missing is not an observed zero.


def test_zero_denominator_and_url_semantics():
    assert Metrics(0, 0).ctr is None
    assert Metrics(0, 0).position is None
    assert normalize_url('https://EXAMPLE.org:443/#/rank?region=mokdong') == 'https://example.org/#/rank?region=mokdong'
    assert normalize_url('https://example.org/a?next=one') != normalize_url('https://example.org/a?next=two')
    with pytest.raises(ValueError):
        Metrics(2, 1)


def test_recorded_baseline_uses_actual_days_and_sums():
    baseline = json.loads((Path(__file__).resolve().parents[2] / 'docs/reports/search-growth-baseline-2026-10-17.json').read_text())
    assert len(baseline['daily']) == 55
    assert sum(r['clicks'] for r in baseline['daily']) == 121
    assert sum(r['impressions'] for r in baseline['daily']) == 5439
    assert sum(r['impressions'] for r in baseline['daily'] if r['date'] >= '2026-09-17') == 188
