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
        'grade_target': {'bandBasis': {}},
    }
    report = audit_rows([row])
    assert not report['valid']
    assert any('근거 등급 없음' in error for error in report['errors'])
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
