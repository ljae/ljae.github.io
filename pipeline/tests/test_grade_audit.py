from pipeline.edutree.grade_audit import audit_rows


def test_grade_audit_rejects_missing_subject_mapping():
    report = audit_rows([{
        'id': 'a', 'name': '학원', 'subjects': ['math'],
        'grade_bands': ['middle'], 'grade_bands_by_subject': {},
    }])
    assert not report['valid']
    assert any('맵 누락' in error for error in report['errors'])


def test_grade_audit_warns_ranked_rows_without_grade_evidence():
    report = audit_rows([{
        'id': 'a', 'name': '학원', 'subjects': ['math'],
        'grade_bands': [], 'grade_bands_by_subject': {'math': []},
        'subject_scores': {'math': {'is_ranked': True}},
    }])
    assert report['valid']
    assert report['rankedWithoutGrade'] == {'math': 1}
    assert report['warnings']


def test_grade_audit_requires_a_basis_for_every_band():
    row = {
        'id': 'a', 'name': '학원', 'subjects': ['math'],
        'grade_bands': ['middle'], 'grade_bands_by_subject': {'math': ['middle']},
        'grade_target': {'bandBasis': {}, 'version': '2026-09-20.3'},
    }
    report = audit_rows([row])
    assert not report['valid']
    assert any('근거 등급 없음' in error for error in report['errors'])
    # 장부 이전 버전이 만든 산출물은 경고로만 — 야간 워크플로가 수집 전에
    # 지난 산출물을 감사하므로, 오류로 막으면 새 산출물을 만들 수 없다.
    row['grade_target'] = {'version': '2026-09-20.2'}
    report = audit_rows([row])
    assert report['valid']
    assert any('이전 버전' in w for w in report['warnings'])
    row['grade_target'] = {}
    assert audit_rows([row])['valid']
    row['grade_target']['bandBasis'] = {'math': {'middle': 'reviews'}}
    report = audit_rows([row])
    assert report['valid']
    assert report['bandBasisCounts'] == {'reviews': 1}


def test_grade_audit_rejects_global_subject_mismatch():
    report = audit_rows([{
        'id': 'a', 'name': '학원', 'subjects': ['math'],
        'grade_bands': ['middle'], 'grade_bands_by_subject': {'math': ['high']},
    }])
    assert not report['valid']
