from datetime import datetime, timezone
import pytest
from pipeline.edutree.parent_service_audit import audit

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


def metadata(date=None, mode='live'):
    return {'generatedAt': date or NOW.isoformat(), 'mode': mode,
            'rankingQuality': {'sourceHealth': {name: {
                'checkedAt': NOW.isoformat(), 'status': 'available'}
                for name in ('naver_blog', 'naver_cafe')}}}


def academy(key, bands=None, ranked=False):
    return {'id': key, 'name': key, 'regionId': 'mokdong', 'subjects': ['math'],
            'gradeBandsBySubject': {'math': bands or []},
            'subjectScores': {'math': {'isRanked': ranked}}}


def test_stale_and_future_data_never_pass_health():
    for date, reason in [('2026-10-19T23:00:00Z', 'stale_public_data'),
                         ('2027-01-01T00:00:00Z', 'future_generation_time'),
                         ('2026-11-09', 'unknown_generation_time')]:
        report = audit(metadata(date), [], now=NOW)
        assert not report['healthy'] and reason in report['problems']


def test_subject_grades_not_general_grades_and_unknown_not_a_match():
    a = academy('unknown'); a['gradeBands'] = ['elem_low']
    a['gradeBandsBySubject']['english'] = ['elem_low']
    report = audit(metadata(),
                   [a, academy('yes', ['elem_low']), academy('upper', ['elem_high']),
                    academy('no', ['high'])], now=NOW)
    assert report['healthy']
    assert report['pilot']['eligible'] == 2
    assert report['pilot']['gradeUnknown'] == 1
    rows = {r['id']: r for r in report['researchQueue']}
    assert rows['unknown']['gradeStatus'] == 'unknown'
    assert 'no' not in rows
    assert all(r['fitVerdict'] == 'not_assessed' for r in rows.values())


def test_queue_bounded_and_explores_all_strata_without_changing_input():
    rows = [academy(str(i), ['elem_low'], True) for i in range(30)]
    rows += [academy('unranked', ['elem_high']), academy('unknown')]
    report = audit(metadata(), rows, now=NOW)
    assert len(report['researchQueue']) == 20
    assert {r['id'] for r in report['researchQueue']} >= {'unranked', 'unknown'}
    assert 'gaps' not in rows[0]
    assert report['modelCalls'] == 0
    with pytest.raises(ValueError):
        audit({}, rows, limit=21)


def test_duplicate_identity_and_demo_are_unhealthy():
    report = audit(metadata(mode='demo'),
                   [academy('same'), academy('same')], now=NOW)
    assert set(report['problems']) == {'not_live_data', 'invalid_academy_identity'}


def test_republishing_old_evidence_does_not_make_collection_fresh():
    m = metadata()
    m['rankingQuality']['sourceHealth']['naver_blog']['checkedAt'] = '2026-10-19T00:00:00Z'
    report = audit(m, [], now=NOW)
    assert not report['healthy']
    assert 'stale_source:naver_blog' in report['problems']
    m['rankingQuality']['sourceHealth'] = {}
    assert 'source_health_unknown:naver_blog' in audit(m, [], now=NOW)['problems']


def test_publication_holds_a_large_drop_without_loosening_source_filters():
    from pipeline.edutree.parent_service_audit import publication_comparison
    old = metadata(); old['rankingQuality']['validMentions'] = 26116
    new = metadata(); new['rankingQuality']['validMentions'] = 6182
    result = publication_comparison(new, old)
    assert result['problems'] == ['evidence_coverage_drop_requires_review']
    assert result['retainedShare'] < .25
    for count in (18282, 26116, 30000):
        new['rankingQuality']['validMentions'] = count
        assert not publication_comparison(new, old)['problems']
    assert old['rankingQuality']['validMentions'] == 26116


@pytest.mark.parametrize('count', [None, '26116', True, -1])
def test_unknown_publication_baseline_cannot_silently_pass(count):
    from pipeline.edutree.parent_service_audit import publication_comparison
    old = metadata(); old['rankingQuality']['validMentions'] = count
    new = metadata(); new['rankingQuality']['validMentions'] = 20000
    assert publication_comparison(new, old)['problems'] == ['publication_baseline_unknown']
