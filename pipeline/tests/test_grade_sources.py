from copy import deepcopy
from datetime import date

import pytest

from edutree import grade_sources, grade_targets, grade_research, refresh_grades


TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def fixed_date(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY
    monkeypatch.setattr(grade_sources, 'date', FixedDate)


def source(**kwargs):
    return {'registrationId': 'A', 'name': '샘플학원', 'address': '서울특별시 강남구 도곡로 1',
            'identityText': '같은 학원명, 도로명 주소 확인',
            'identityUrl': 'https://example.com/branch', 'gradeUrl': 'https://example.com/admission',
            'sourceType': 'official', 'scope': 'branch', 'reviewStatus': 'verified',
            'checkedAt': '2026-09-20', 'reviewBy': '2026-12-19',
            'summary': '중학생 수학반 모집', 'bySubject': {'math': ['middle']}, **kwargs}


def academy(**kwargs):
    a = {'id': 'A', 'name': '샘플학원', 'road_address': '서울특별시 강남구 도곡로 1',
         'subjects': ['math', 'english'], **kwargs}
    grade_targets.apply_all([a], {'A': {'course_names': ['초등영어']}})
    return a


def test_web_grade_preserves_registered_grades_and_subject_boundary():
    a = academy()
    grade_sources.apply([a], [source()], TODAY)
    assert a['grade_bands_by_subject'] == {'math': ['middle'], 'english': ['elem_low', 'elem_high']}
    assert a['grade_target']['status'] == 'official_guidance'
    evidence = deepcopy(a['grade_target']['evidence'])
    grade_sources.apply([a], [source()], TODAY)
    assert a['grade_target']['evidence'] == evidence
    note = grade_sources.source_notes([a])[0]['notes'][0]
    assert note['url'] == 'https://example.com/admission'
    assert note['subjects'] == ['math']
    assert note['checkedAt'] == '2026-09-20'


@pytest.mark.parametrize('change', [
    {'registrationId': 'B'}, {'address': '서울특별시 강남구 도곡로 2'}, {'name': '샘플학원2관'},
    {'reviewStatus': 'candidate'}, {'sourceType': 'review'}, {'scope': 'brand'},
    {'checkedAt': '2026-09-21'}, {'reviewBy': '2026-09-19'}, {'reviewBy': '2027-09-20'},
    {'gradeUrl': 'javascript:alert(1)'}, {'identityText': ''},
    {'bySubject': {'science': ['high']}}, {'bySubject': {'math': ['university']}},
])
def test_unreviewed_expired_or_other_branch_is_not_applied(change):
    a = academy()
    old = deepcopy(a)
    grade_sources.apply([a], [source(**change)], TODAY)
    assert a == old


def test_refresh_preserves_every_non_grade_field_and_retracts_expired_source(monkeypatch):
    monkeypatch.setattr(grade_sources, 'load', lambda: [source()])
    p = {'id': 'A', 'name': '샘플학원', 'address': source()['address'], 'regionId': 'daechi',
         'subjects': ['math', 'english'], 'gradeBands': [], 'gradeBandsBySubject': {},
         'score': {'total': 91, 'sampleSize': 53}, 'subjectScores': {'math': {'total': 92}},
         'evidence': [{'excerpt': '기존 후기'}], 'stages': [], 'flagship': []}
    raw = {'A': {'id': 'A', 'course_names': ['초등영어']}}
    updated, _ = refresh_grades.refresh([p], raw)
    assert p['gradeBands'] == []
    for key in ('score', 'subjectScores', 'evidence', 'subjects', 'id', 'name', 'address'):
        assert updated[0][key] == p[key]
    assert 'math_mid_naesin' in updated[0]['stages']
    monkeypatch.setattr(grade_sources, 'load', lambda: [source(reviewBy='2026-09-19')])
    expired, _ = refresh_grades.refresh(updated, raw)
    assert expired[0]['gradeBandsBySubject']['math'] == []
    assert 'math_mid_naesin' not in expired[0]['stages']
    assert expired[0]['gradeBandsBySubject']['english'] == ['elem_low', 'elem_high']


def test_refresh_refuses_missing_registration():
    with pytest.raises(ValueError, match='등록 공시 누락'):
        refresh_grades.refresh([{'id': 'A'}], {})


def test_newly_identified_subject_gets_public_and_web_grades_only(monkeypatch):
    monkeypatch.setattr(grade_sources, 'load', lambda: [source()])
    a = academy(subjects=['general'])
    # 공시의 초등영어는 math로 전파되지 않고, 검토한 수학 지점 자료만 연결한다.
    a['subjects'] = ['math', 'english']
    a['grade_review_signals'] = {'high': 30}
    grade_targets.rebind_subjects([a])
    assert a['grade_bands_by_subject'] == {'math': ['middle'], 'english': ['elem_low', 'elem_high']}
    assert 'high' not in a['grade_bands']


def test_general_high_school_registration_survives_subject_promotion():
    a = {'id': 'A', 'name': '샘플고등관', 'subjects': ['general']}
    grade_targets.apply_all([a], {'A': {'name': '샘플고등관'}})
    a['subjects'] = ['math']
    grade_targets.rebind_subjects([a])
    assert a['grade_bands_by_subject'] == {'math': ['high']}


def test_research_prioritizes_ranked_but_rotates_and_keeps_partial_subjects():
    def p(aid, ranked=False, mapping=None):
        return {'id': aid, 'name': '샘플', 'address': '주소', 'regionId': 'daechi',
                'subjects': ['math', 'english'], 'score': {'isRanked': ranked},
                'gradeBandsBySubject': mapping or {}}
    academies = [p('A'), p('B', True, {'math': ['middle']}),
                 p('C', True, {'math': ['middle'], 'english': ['high']})]
    rows = grade_research.queue(academies)
    assert [r['academyId'] for r in rows] == ['B', 'A']
    assert rows[0]['subjectsToCheck'] == ['english']
    grade_research.discover(rows, 1, lambda *a, **k: [{'title': '고등수학 선행', 'url': 'https://example.com'}])
    assert rows[0]['searchStatus'] == 'needs_review'
    assert 'gradeBands' not in rows[0]
    again = grade_research.queue(academies, {r['academyId']: r for r in rows})
    assert [r['academyId'] for r in again] == ['A', 'B']


def test_curated_ledger_is_valid_on_its_review_date():
    for record in grade_sources.load():
        assert grade_sources.valid_record(record, date.fromisoformat(record['checkedAt']))
