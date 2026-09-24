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


def test_unknown_does_not_inherit_previous_bands_or_single_author_reviews():
    """이전 회차의 추정도, 한 사람이 백 번 말한 것도 근거가 아니다."""
    a = {'id': 'A', 'name': '부엉이학원', 'subjects': ['math'], 'grade_bands': ['elem_low', 'high']}
    grade_targets.apply_all([a], {'A': {'name': '부엉이학원', 'le_crse_nm': '보습'}})
    build._bands_from_mentions([a], {'A': [{'band': 'elem_low', 'author_hash': 'one'}
                                           for _ in range(100)]})
    assert a['grade_bands'] == []
    assert a['grade_target']['status'] == 'unknown'
    assert a['grade_review_signals']['elem_low'] == 100
    assert a['grade_target']['unverifiedPreviousBands'] == ['elem_low', 'high']


def _mentions(band, n, subject=None, start=0):
    return [{'band': band, 'subject': subject, 'author_hash': f'a{start + i}'} for i in range(n)]


def test_repeated_review_mentions_confirm_a_band_with_reviews_basis():
    """서로 다른 작성자 2명 · 3건 · 그 과목 학년 언급의 25% 이상이면 reviews 등급."""
    a = {'id': 'A', 'name': '명인학원', 'subjects': ['math']}
    grade_targets.apply_all([a], {'A': {'name': '명인학원', 'le_crse_nm': '보습'}})
    rows = _mentions('high', 53) + _mentions('middle', 31, start=100) \
        + _mentions('elem_low', 1, start=200) + _mentions('elem_high', 1, start=300)
    assert build._bands_from_mentions([a], {'A': rows}) == 1
    assert a['grade_bands_by_subject'] == {'math': ['middle', 'high']}
    assert a['grade_target']['bandBasis'] == {'math': {'middle': 'reviews', 'high': 'reviews'}}
    assert a['grade_target']['status'] == 'review_mentions'
    assert a['grade_review_by_subject']['math']['high'] == {'mentions': 53, 'authors': 53}
    fields = [e['field'] for e in a['grade_target']['evidence']]
    assert fields.count('review_mentions') == 2


def test_review_share_below_threshold_is_not_a_band():
    """띵킹어학원(초저 16 · 고 6 · 초고 2 · 중 1): 고등 24% 는 문턱 아래."""
    a = {'id': 'A', 'name': '띵킹어학원', 'subjects': ['english']}
    grade_targets.apply_all([a], {'A': {}})
    rows = _mentions('elem_low', 16) + _mentions('high', 6, start=50) \
        + _mentions('elem_high', 2, start=80) + _mentions('middle', 1, start=90)
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_bands_by_subject'] == {'english': ['elem_low']}


def test_detached_review_band_is_aspiration_not_a_class():
    """대치소마(초저 54 · 고 24 · 초고 8 · 중 4): 고등 27% 지만 떨어져 있다."""
    a = {'id': 'A', 'name': '대치소마학원', 'subjects': ['math']}
    grade_targets.apply_all([a], {'A': {}})
    rows = _mentions('elem_low', 54) + _mentions('high', 24, start=100) \
        + _mentions('elem_high', 8, start=200) + _mentions('middle', 4, start=300)
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_bands_by_subject'] == {'math': ['elem_low']}


def test_review_band_must_touch_the_known_bands():
    """렉스김(큐레이션 초등 + 후기 고 31% · 중 21%): 고등은 중등 없이 못 잇는다."""
    a = {'id': 'A', 'name': '렉스김어학원', 'subjects': ['english'],
         'stages': ['eng_el_academy'], 'stage_basis': {'eng_el_academy': 'curated'}}
    grade_targets.apply_all([a], {'A': {}})
    assert a['grade_bands_by_subject'] == {'english': ['elem_low', 'elem_high']}
    rows = _mentions('elem_low', 35) + _mentions('high', 28, start=100) \
        + _mentions('middle', 19, start=200) + _mentions('elem_high', 7, start=300)
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_bands_by_subject'] == {'english': ['elem_low', 'elem_high']}
    # 정상어학원(큐레이션 초등 + 후기 중 46 · 고 45): 중등이 잇고 고등이 따라온다.
    rows = _mentions('middle', 46) + _mentions('high', 45, start=100) \
        + _mentions('elem_low', 17, start=200) + _mentions('elem_high', 15, start=300)
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_bands_by_subject'] == {'english': list(grade_targets.BANDS)}
    assert a['grade_target']['bandBasis']['english']['high'] == 'reviews'


def test_review_bands_follow_the_subject_the_post_spoke_of():
    """수학 후기의 고등이 영어 학년이 되지 않는다. 과목 불명 글은 대표 과목 몫."""
    a = {'id': 'A', 'name': '종합학원', 'subjects': ['math', 'english']}
    grade_targets.apply_all([a], {'A': {}})
    rows = _mentions('high', 5, 'math') + _mentions('elem_low', 5, 'english', 10) \
        + _mentions('middle', 5, None, 20)
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_bands_by_subject'] == {'math': ['middle', 'high'], 'english': ['elem_low']}
    assert a['grade_bands'] == ['elem_low', 'middle', 'high']


def test_review_confirmation_is_idempotent_and_yields_to_registered():
    a = {'id': 'A', 'name': '학원', 'subjects': ['math']}
    grade_targets.apply_all([a], {'A': {'course_names': ['고등수학']}})
    rows = _mentions('high', 5) + _mentions('middle', 5, start=10)
    build._bands_from_mentions([a], {'A': rows})
    build._bands_from_mentions([a], {'A': rows})
    assert a['grade_target']['bandBasis'] == {'math': {'high': 'registered', 'middle': 'reviews'}}
    assert [e['field'] for e in a['grade_target']['evidence']].count('review_mentions') == 1
    # 후기가 사라지면 reviews 등급도 사라진다 — 공시 근거는 남는다.
    build._bands_from_mentions([a], {'A': []})
    assert a['grade_bands_by_subject'] == {'math': ['high']}
    assert a['grade_target']['status'] == 'registered_courses'


def test_curated_seed_stages_give_bands_to_their_own_subject():
    """시드 큐레이션 단계(사람이 적은 것)는 그 과목의 학년 근거다."""
    a = {'id': 'A', 'name': '소마학원', 'subjects': ['math', 'science'],
         'stages': ['math_el_thinking', 'sci_hi_naesin'],
         'stage_basis': {'math_el_thinking': 'curated', 'sci_hi_naesin': 'inferred'}}
    grade_targets.apply_all([a], {'A': {'le_crse_nm': '보습·논술'}})
    assert a['grade_bands_by_subject']['math'] == ['elem_low', 'elem_high']
    assert a['grade_bands_by_subject']['science'] == []          # inferred 는 근거가 아니다
    assert a['grade_target']['bandBasis']['math'] == {'elem_low': 'curated', 'elem_high': 'curated'}
    assert a['grade_target']['status'] == 'curated_stages'
    assert a['grade_target']['evidence'][0]['field'] == 'curated_stage'


def test_rebind_keeps_curated_and_review_bands():
    a = {'id': 'A', 'name': '학원', 'subjects': ['general'],
         'stages': ['math_hi_nsu'], 'stage_basis': {'math_hi_nsu': 'curated'}}
    grade_targets.apply_all([a], {'A': {}})
    assert a['grade_bands_by_subject'] == {'general': []}
    a['subjects'] = ['math']                     # 후기가 과목을 정했다
    grade_targets.rebind_subjects([a])
    assert a['grade_bands_by_subject'] == {'math': ['high']}
    build._bands_from_mentions([a], {'A': _mentions('middle', 4)})
    grade_targets.rebind_subjects([a])
    assert a['grade_target']['bandBasis'] == {'math': {'middle': 'reviews', 'high': 'curated'}}


def test_refresh_reapplies_curated_and_review_signals():
    from edutree import refresh_grades
    payload = {'id': 'A', 'name': '소마학원', 'address': '서울 대치동 1', 'regionId': 'daechi',
               'subjects': ['math'], 'registrationIds': [], 'gradeBands': [],
               'gradeBandsBySubject': {'math': []}, 'gradeTarget': {'status': 'unknown'},
               'stages': ['math_el_thinking'], 'stageBasis': {'math_el_thinking': 'curated'}}
    signals = {'A': {'math': {'middle': {'mentions': 4, 'authors': 3}}}}
    (out,), _ = refresh_grades.refresh([payload], {'A': {'le_crse_nm': '보습'}}, signals)
    assert out['gradeBandsBySubject'] == {'math': ['elem_low', 'elem_high', 'middle']}
    assert out['gradeTarget']['bandBasis']['math']['middle'] == 'reviews'
    assert 'math_el_thinking' in out['stages'] and out['stageBasis']['math_el_thinking'] == 'curated'
    assert 'math_mid_naesin' in out['stages'] and out['stageBasis']['math_mid_naesin'] == 'inferred'


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
