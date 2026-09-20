from edutree import grade_targets, build, analyze
import pytest


@pytest.mark.parametrize('text,bands', [
    ('초등수학', ['elem_low', 'elem_high']),
    ('초등저학년 영어', ['elem_low']),
    ('초등고학년 영어', ['elem_high']),
    ('초1~초6', ['elem_low', 'elem_high']),
    ('초5~중2', ['elem_high', 'middle']),
    ('중1~고3', ['middle', 'high']),
    ('고등국어', ['high']), ('수능국어', ['high']),
    ('예비중1 수학', ['elem_high']), ('예비고1 영어', ['middle']),
    ('예비고2 영어', ['high']),
    ('초등 고등수학 선행', []), ('사고력 연산 파닉스 의대', []),
    ('학원 3학년반', []), ('보습', []),
    ('중고급 영어', []), ('초고속 연산', []),
    ('키즈 유아 5세', []), ('17세 영어', []), ('7세 영어', ['elem_low']),
])
def test_explicit_grades_only(text, bands):
    assert grade_targets.parse(text) == bands


def test_course_grade_is_not_transferred_to_other_subject():
    a = {'id': 'A', 'name': '종합학원', 'subjects': ['math', 'english'], 'grade_bands': ['middle']}
    grade_targets.apply_all([a], {'A': {'course_names': ['초등영어', '고등수학']}})
    assert a['grade_bands_by_subject'] == {'math': ['high'], 'english': ['elem_low', 'elem_high']}
    assert a['grade_target']['unverifiedPreviousBands'] == ['middle']
    assert len(a['grade_target']['evidence']) == 2


def test_unknown_does_not_inherit_curated_or_review_grades():
    a = {'id': 'A', 'name': '부엉이학원', 'subjects': ['math'], 'grade_bands': ['elem_low', 'high']}
    grade_targets.apply_all([a], {'A': {'name': '부엉이학원', 'le_crse_nm': '보습'}})
    build._bands_from_mentions([a], {'A': [{'band': 'elem_low'} for _ in range(100)]})
    assert a['grade_bands'] == []
    assert a['grade_target']['status'] == 'unknown'
    assert a['grade_review_signals']['elem_low'] == 100


def test_all_merged_registrations_are_audited():
    a = {'id': 'A', 'name': '통합학원', 'subjects': ['math'], 'registration_ids': ['A','B']}
    grade_targets.apply_all([a], {'A': {'course_names': ['초등수학']}, 'B': {'course_names': ['중등수학']}})
    assert a['grade_bands'] == ['elem_low','elem_high','middle']
    assert {r['registrationId'] for r in a['grade_target']['evidence']} == {'A','B'}


def test_combined_course_field_does_not_cross_subject_grades():
    a = {'id': 'A', 'name': '종합학원', 'subjects': ['math','english']}
    grade_targets.apply_all([a], {'A': {'le_crse_list_nm': '초등영어, 고등수학'}})
    assert a['grade_bands_by_subject'] == {'math': ['high'], 'english': ['elem_low','elem_high']}


def test_ambiguous_combined_field_is_held():
    a = {'id': 'A', 'name': '종합학원', 'subjects': ['math','english']}
    grade_targets.apply_all([a], {'A': {'course_names': ['초등영어고등수학']}})
    assert a['grade_target']['status'] == 'unknown'
    assert a['grade_bands'] == []
    assert a['grade_target']['heldCourseSignals']


def test_foreign_language_category_does_not_claim_all_school_grades():
    a = {'id': 'A', 'name': '어학원', 'subjects': ['english', 'korean']}
    grade_targets.apply_all([a], {'A': {
        'le_crse_nm': '실용외국어(유아/초·중·고)',
        'course_names': ['초등실용외국어A'],
    }})
    assert a['grade_bands_by_subject'] == {'english': ['elem_low', 'elem_high'], 'korean': []}
    assert a['grade_bands'] == ['elem_low', 'elem_high']
    assert a['grade_target']['heldCourseSignals'][0]['reason'] == '교습과정 분류명이며 실제 모집 학년 아님'


def test_foreign_category_does_not_hide_a_separate_course():
    a = {'id': 'A', 'name': '종합학원', 'subjects': ['math', 'english']}
    grade_targets.apply_all([a], {'A': {'le_crse_list_nm': '실용외국어(유아/초·중·고),고등수학'}})
    assert a['grade_bands_by_subject'] == {'math': ['high'], 'english': []}


def test_chinese_course_does_not_populate_korean_or_english():
    a = {'id': 'A', 'name': '어학원', 'subjects': ['english', 'korean', 'etc']}
    grade_targets.apply_all([a], {'A': {'course_names': ['초등중국어', '고등국어']}})
    assert a['grade_bands_by_subject'] == {'english': [], 'korean': ['high'], 'etc': ['elem_low', 'elem_high']}


@pytest.mark.parametrize('title,snippet', [
    ('부엉이라이브러리 좌석신청', '시대인재 부엉이 좌석을 신청했습니다.'),
    ('황금부엉이 초등2학년 어린이 스도쿠', '학원에서 일하는 작가의 책입니다.'),
    ('서울 대치동 수학하는부엉이학원 후기', '초등 수학하는부엉이학원에 다녔습니다.'),
])
def test_owl_homonyms_are_not_the_owl_academy(title, snippet):
    a = {'name': '부엉이학원'}
    candidates = analyze.name_candidates(a)
    candidates -= analyze.weak_candidates(candidates)
    rivals = analyze.RivalIndex({'수학하는부엉이학원', '수학하는부엉이', '시대인재'})
    assert not analyze.is_relevant({'title': title, 'snippet': snippet}, candidates, True, rivals)


def test_owl_full_name_with_real_context_is_kept():
    a = {'name': '부엉이학원'}
    candidates = analyze.name_candidates(a)
    candidates -= analyze.weak_candidates(candidates)
    assert analyze.is_relevant({'title':'대치 부엉이학원 수강 후기', 'snippet':'부엉이학원에서 고등 국어 수업을 들었습니다.'}, candidates, True)
