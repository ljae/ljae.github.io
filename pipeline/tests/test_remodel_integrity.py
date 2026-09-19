"""광고 고지와 같은 학군 동명 지점에 대한 긍정/부정 대조 사례."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edutree import analyze, branches, ranking_quality


@pytest.mark.parametrize('text', [
    '이 글은 수강권을 제공받아 작성했습니다.',
    '소정의 원고료를 받았지만 솔직하게 작성했습니다.',
    '유료 광고를 포함하고 있습니다.',
    '경제적 대가를 제공받은 후기입니다.',
    '수강권을\n제공\u200b받아 작성한 포스팅입니다.',
])
def test_paid_disclosure_is_excluded_even_when_only_one_signal(text):
    m = analyze.analyze({'snippet': text, 'title': '학원 체험 후기'})
    assert m['is_excluded']
    assert m['exclude_reason'] == 'sponsored'


@pytest.mark.parametrize('text', [
    '협찬 없이 직접 수강한 후기입니다. 아이가 3개월 다녔어요.',
    '원고료를 받지 않았어요. 우리 아이는 수업을 좋아해요.',
    '수강료가 비싸지만 선생님이 꼼꼼해요.',
    '내돈내산 후기입니다. 광고 아님.',
    '수강권을 제공받지 않았습니다.',
    '학원으로부터 시간표 자료를 제공받아 아이와 살펴봤어요.',
])
def test_unpaid_parent_reviews_survive(text):
    assert not analyze.analyze({'snippet': text})['is_excluded']


ACADEMIES = [
    {'id': 'A', 'name': '가나다수학학원', 'brand': '가나다수학',
     'region_id': 'daechi', 'dong': '대치동'},
    {'id': 'B', 'name': '가나다수학학원', 'brand': '가나다수학',
     'region_id': 'daechi', 'dong': '도곡동'},
]


def apply(title, body='', key='A', academies=None):
    rows = academies or ACADEMIES
    return branches.apply([
        {'academy_key': key, 'title': title, 'snippet': body, 'url_hash': 'post1'},
    ], rows, {a['id']: {'가나다수학'} for a in rows}, {}, set())


def test_shared_region_does_not_identify_a_branch():
    for key in ('A', 'B'):
        kept, stats = apply('강남 가나다수학 레테 후기', key=key)
        assert kept == []
        assert stats['local_unknown'] == 1


def test_ambiguous_same_region_name_without_location_is_held():
    kept, stats = apply('가나다수학 레테 후기')
    assert kept == []
    assert stats['local_unknown'] == 1


def test_precise_location_identifies_only_the_right_branch():
    kept, _ = apply('대치동 가나다수학 레테 후기')
    assert [m['academy_key'] for m in kept] == ['A']
    assert apply('대치동 가나다수학 레테 후기', key='B')[0] == []


def test_body_locality_can_identify_branch_but_comparison_cannot():
    assert apply('가나다수학 레테 후기', '대치동 가나다수학에서 시험봤어요')[0]
    assert apply('가나다수학 비교', '대치동과 도곡동 두 곳 고민 중')[0] == []


def test_solo_academy_does_not_need_extra_branch_evidence():
    assert apply('가나다수학 레테 후기', academies=ACADEMIES[:1])[0]


def test_exact_homonyms_in_same_neighborhood_still_need_identity():
    rows = [dict(a, dong='대치동') for a in ACADEMIES]
    assert apply('대치동 가나다수학학원 후기', academies=rows)[0] == []


def test_quality_report_preserves_exclusion_reason_counts():
    rows = [analyze.analyze({'snippet': '원고료를 제공받아 작성했습니다.'}),
            analyze.analyze({'snippet': '우리 아이가 만족해요.'})]
    result = ranking_quality.summarize([], rows, {})
    assert result['validMentions'] == 1
    assert result['excludedMentions'] == 1
    assert result['exclusionReasons'] == {'sponsored': 1}


def test_rehoming_requires_the_same_specific_branch_evidence():
    rows = ACADEMIES + [
        {'id': 'C', 'name': '가나다수학학원', 'brand': '가나다수학',
         'region_id': 'mokdong', 'dong': '목동'},
    ]
    assert apply('강남 가나다수학 레테 후기', key='C', academies=rows)[0] == []
    kept, _ = apply('대치동 가나다수학 레테 후기', key='C', academies=rows)
    assert [m['academy_key'] for m in kept] == ['A']
    assert apply('대치동 도곡동 가나다수학 비교', key='C', academies=rows)[0] == []


def test_distinct_registration_name_can_identify_same_neighborhood_branch():
    rows = [dict(a, name='가나다수학' + a['id'] + '학원', dong='대치동')
            for a in ACADEMIES]
    assert apply('가나다수학A학원 레테 후기', academies=rows)[0]
    assert apply('가나다수학A학원 레테 후기', key='B', academies=rows)[0] == []
