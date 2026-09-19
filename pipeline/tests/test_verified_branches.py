from copy import deepcopy
from datetime import date
from pipeline.edutree import verified_branches, grade_targets


def academy():
    return {'id':'3000015117','registration_ids':['3000023042'], 'name':'엠에스씨',
            'road_address':'서울특별시 강남구 영동대로50길 10','subjects':['math','general']}


def test_official_branch_uses_absorbed_registration_and_keeps_subject_grades_separate():
    a=academy()
    verified_branches.apply([a], today=date(2026,9,19))
    grade_targets.apply_all([a], {})
    assert 'MSC' in a['aliases']
    assert 'korean' in a['subjects']
    assert a['grade_bands_by_subject']['korean']==['elem_low','elem_high']
    assert a['grade_bands_by_subject']['math']==[]
    assert a['grade_target']['status']=='official_guidance'
    assert a['grade_target']['evidence'][-1]['registrationId']=='3000023042'


def test_same_name_or_building_cannot_borrow_official_evidence():
    original=academy()
    for change in ({'id':'other','registration_ids':[]}, {'road_address':'서울특별시 강남구 삼성로71길 9'}, {'name':'다른학원'}):
        a={**deepcopy(original),**change}
        verified_branches.apply([a], today=date(2026,9,19))
        assert 'verified_branch' not in a


def test_expired_or_future_official_evidence_is_not_reused():
    for day in (date(2026,9,18),date(2026,12,19)):
        a=academy();verified_branches.apply([a],today=day)
        assert 'verified_branch' not in a


def test_kiparang_daechi_elementary_intake_does_not_imply_low_grades():
    a={'id':'5279','name':'기파랑문해원대치본원학원','road_address':'서울특별시 강남구 역삼로64길 9','subjects':['korean']}
    verified_branches.apply([a],today=date(2026,9,19))
    grade_targets.apply_all([a],{})
    assert a['grade_bands']==['elem_high']
    assert '기파랑' in a['aliases']


def test_targeted_collection_preserves_store_and_rejects_unknown_ids(monkeypatch):
    from pipeline.edutree import targeted
    a=academy();events=[]
    monkeypatch.setattr(targeted.build,'load_academies',lambda **kw:([a],'live'))
    monkeypatch.setattr(targeted.naver,'collect_all',lambda academies,regions:[{'academy_key':academies[0]['id']}])
    monkeypatch.setattr(targeted.mention_store,'merge',lambda rows:events.append(('merge',rows)))
    monkeypatch.setattr(targeted.coverage,'record',lambda academies,rows:events.append(('coverage',rows)))
    assert targeted.collect('3000023042')==[{'academy_key':'3000015117'}]
    assert [event[0] for event in events]==['merge','coverage']
    import pytest
    for ids in ['unknown','12345',','.join(str(i) for i in range(21))]:
        with pytest.raises(ValueError):targeted.collect(ids)


def test_same_region_halls_require_specific_branch_even_when_not_scored():
    from pipeline.edutree import branches, analyze
    academies=[
        {'id':'5279','name':'기파랑문해원대치본원학원','road_address':'서울특별시 강남구 역삼로64길 9','region_id':'daechi','dong':'대치동','subjects':['korean']},
        {'id':'3000041721','name':'기파랑문해원대치원3관학원','road_address':'서울특별시 강남구 도곡로 422','region_id':'daechi','dong':'대치동','subjects':['korean']},
        {'id':'middle','name':'기파랑문해원대치원중등','road_address':'다른 주소','region_id':'daechi','dong':'대치동','subjects':['korean']},
    ]
    verified_branches.apply(academies,today=date(2026,9,19))
    assert len({branches.sibling_key(a) for a in academies})==1
    # 중등관이 수집되지 않았더라도 본원과 3관에 후기를 나눠주면 안 된다.
    candidates={a['id']:analyze.name_candidates(a) for a in academies[:2]}
    for title,expected in [('대치 기파랑 후기',[]),('대치 기파랑 대치본원 후기',['5279']),('대치 기파랑 대치3관 후기',['3000041721'])]:
        mentions=[{'academy_key':a['id'],'url_hash':'same','title':title,'snippet':'아이를 보내고 수업에 만족합니다.'} for a in academies[:2]]
        kept,_=branches.apply(mentions,academies,candidates,{},set())
        assert [m['academy_key'] for m in kept]==expected


def test_banpo_middle_hall_review_cannot_enter_elementary_branch():
    from pipeline.edutree import branches,analyze
    academies=[
        {'id':'14153','name':'기파랑문해원서초학원','road_address':'서울특별시 서초구 고무래로10길 10','region_id':'banpo','dong':'반포동','subjects':['korean']},
        {'id':'3000051686','name':'기파랑국풀반포학원','road_address':'서울특별시 서초구 반포대로 300','region_id':'banpo','dong':'반포동','subjects':['korean']},
    ]
    verified_branches.apply(academies,today=date(2026,9,19))
    m={'academy_key':'14153','url_hash':'middle','title':'기파랑중등관 서초반포원','snippet':'반포대로 300 중1 아람반. 아이가 수업을 잘 듣고 있습니다.'}
    kept,_=branches.apply([m],academies,{a['id']:analyze.name_candidates(a) for a in academies},{},set())
    assert kept==[]
