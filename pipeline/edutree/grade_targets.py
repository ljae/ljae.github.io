"""학원별 대상 학년 전수 감사. 공시 과정과 후기·브랜드 추정을 구분한다.

공시 과정은 현재 모집 학년의 전수 확인과 같지 않다. 공시에 명시된 학년만
필터에 사용하며 선행 과정처럼 재학 학년과 구별할 수 없는 문구는 보류한다.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

BANDS = ('elem_low', 'elem_high', 'middle', 'high')
VERSION = '2026-09-20.2'
NEIS_URL = 'https://open.neis.go.kr/hub/acaInsTiInfo'
SUBJECT_WORDS = {
    'math': ('수학', '수리'), 'english': ('영어',),
    'korean': ('국어', '독서', '문해'),
    'science': ('과학', '과탐', '물리', '화학', '생명', '지구'),
    'arts': ('미술', '음악', '피아노', '발레', '무용', '체육'),
    'etc': ('코딩', '로봇', '바둑'),
}


def _subjects(value):
    # 외국어·중국어 안의 '국어'는 국어/논술 수업이 아니다.
    other_language = '중국어' in value
    foreign_language = '외국어' in value
    value = value.replace('중국어', '').replace('외국어', '')
    subjects = {s for s, words in SUBJECT_WORDS.items() if any(w in value for w in words)}
    if other_language:
        subjects.add('etc')
    if foreign_language:
        # 영어 과목이 별도로 확인된 학원에만 연결된다. 과목 자체를 추가하지 않는다.
        subjects.add('english')
    return subjects


# 교육청의 교습과정 분류명은 실제 개설 반의 대상 학년을 뜻하지 않는다.
FOREIGN_CATEGORY = re.compile(r'실용외국어\s*\(\s*유아\s*/\s*초\s*·\s*중\s*·\s*고\s*\)')


def _parts(value):
    # 한 필드에 초등영어, 고등수학이 함께 있으면 과정을 나누어 읽는다.
    if len(_subjects(value)) > 1:
        return re.split(r'[,;/|]|\s+(?=(?:초등|중등|고등|초[1-6]|중[1-3]|고[1-3]))', value)
    return [value]
# 학교급과 숫자가 함께 나온 경우만 학년 숫자로 읽는다. '3학년' 단독은 미상.
GRADE = r'(초(?:등(?:학교)?)?|중(?:학교|등)?|고(?:등학교|등)?)\s*([1-6])(?:학년)?'
RANGE = re.compile(GRADE + r'\s*[~∼～\-–—]\s*(?:(초(?:등(?:학교)?)?|중(?:학교|등)?|고(?:등학교|등)?)\s*)?([1-6])(?:학년)?')
NUMBERED = re.compile(GRADE)


def _number(school, grade):
    n = int(grade)
    return n if school.startswith('초') else n + (6 if school.startswith('중') else 9)


def _band(n):
    return 'elem_low' if n <= 3 else 'elem_high' if n <= 6 else 'middle' if n <= 9 else 'high'


def parse(text):
    """명시된 학교급/범위만. 난이도·교재·학습방법은 학생 학년이 아니다."""
    text = str(text or '')
    if '선행' in text:
        return []
    # '서초2관/서초3관'은 서초 지역의 관 번호다. GRADE 정규식이
    # 내부의 '초2/초3'만 읽으면 관 번호가 학생 학년으로 둔갑한다.
    text = re.sub(r'서초\s*[1-6]\s*관', '서초관', text)
    found = set()
    text = re.sub(r'초중급|중고급|초급|중급|고급', '', text)
    # 예비중/예비고는 진학 전 재학 학년으로 해석한다.
    for m in re.finditer(r'예비(초|중|고)\s*([1-6])?', text):
        found.add(_band(max(0, _number(m[1], m[2] or '1') - 1)))
    text = re.sub(r'예비(초|중|고)\s*[1-6]?(?:학년)?', '', text)
    for word, band in [('저', 'elem_low'), ('고', 'elem_high')]:
        pattern = r'초등\s*' + word + r'학년'
        if re.search(pattern, text):
            found.add(band)
            text = re.sub(pattern, '', text)
    for m in RANGE.finditer(text):
        s1, n1, s2, n2 = m.groups()
        s2 = s2 or s1
        if (not s1.startswith('초') and int(n1) > 3) or (not s2.startswith('초') and int(n2) > 3):
            continue
        lo, hi = _number(s1, n1), _number(s2, n2)
        if lo <= hi <= 12:
            found.update(_band(n) for n in range(lo, hi + 1))
    text = RANGE.sub('', text)
    for m in NUMBERED.finditer(text):
        school, n = m.groups()
        if school.startswith('초') or int(n) <= 3:
            found.add(_band(_number(school, n)))
    text = NUMBERED.sub('', text)
    if re.search(r'초등|초교|초\s*[·,/]\s*중|초중|초고(?=등|부|\s|$)', text):
        found.update(('elem_low', 'elem_high'))
    if re.search(r'중등|중학|초중|중고|초\s*[·,/]\s*중', text):
        found.add('middle')
    if re.search(r'고등|고교|수능|재수|재종|중고|초고(?=등|부|\s|$)|중\s*[·,/]\s*고', text):
        found.add('high')
    # 유아·키즈만으로 초등 대상이라고 할 수 없고, '17세'의 '7세'도 아니다.
    if re.search(r'(?<!\d)7세', text):
        found.add('elem_low')
    return [b for b in BANDS if b in found]


def apply_all(academies, registrations):
    """통합된 학원의 모든 등록 원문을 다시 대조. 과거 추정 값을 물려받지 않는다."""
    for a in academies:
        evidence, found, held = [], set(), []
        by_subject = {s: set() for s in a.get('subjects', [])}
        ids = list(dict.fromkeys([a['id'], *(a.get('registration_ids') or [])]))
        for aid in ids:
            row = registrations.get(str(aid)) or {}
            fields = [('name', row.get('name')),
                      ('le_crse_list_nm', row.get('le_crse_list_nm')),
                      ('le_crse_nm', row.get('le_crse_nm'))]
            fields += [('course_names', value) for value in row.get('course_names') or []]
            for field, value in fields:
                if value and FOREIGN_CATEGORY.search(value):
                    held.append({'registrationId': str(aid), 'field': field, 'text': value,
                                 'reason': '교습과정 분류명이며 실제 모집 학년 아님'})
            fields = [(field, part) for field, value in fields if value
                      for part in _parts(FOREIGN_CATEGORY.sub('', value))]
            for field, value in fields:
                if not value:
                    continue
                if '선행' in value:
                    held.append({'registrationId': str(aid), 'field': field, 'text': value})
                bands = parse(value)
                if bands:
                    named_subjects = _subjects(value)
                    school_levels = {'elementary' if b.startswith('elem_') else b for b in bands}
                    if len(named_subjects) > 1 and len(school_levels) > 1:
                        held.append({'registrationId': str(aid), 'field': field, 'text': value,
                                     'reason': '과목별 학년 구분 불명'})
                        continue
                    found.update(bands)
                    for subject in named_subjects or set(by_subject):
                        if subject in by_subject:
                            by_subject[subject].update(bands)
                    evidence.append({'registrationId': str(aid), 'field': field,
                                     'text': value, 'bands': bands, 'subjects': sorted(named_subjects), 'url': NEIS_URL})
        previous = a.get('grade_bands') or []
        a['grade_bands'] = [b for b in BANDS if b in found]
        a['grade_bands_by_subject'] = {s: [b for b in BANDS if b in bs] for s, bs in by_subject.items()}
        a['grade_target'] = {
            'status': 'registered_courses' if found else 'unknown',
            'basis': '교육청 등록명·교습과정' if found else '대상 학년 미확인',
            'bands': a['grade_bands'], 'evidence': evidence,
            'bySubject': a['grade_bands_by_subject'],
            'heldCourseSignals': held,
            'unverifiedPreviousBands': [b for b in previous if b not in found],
            'auditedAt': date.today().isoformat(), 'version': VERSION,
            'caveat': '공시 과정 기준이며 현재 모집 학년은 학원에 확인이 필요합니다.'
        }

        from . import verified_branches
        verified_branches.apply_grades(a)

    from . import grade_sources
    grade_sources.apply(academies, registrations=registrations)


def report(academies):
    rows = []
    for a in academies:
        target = a.get('grade_target') or {'status': 'unknown', 'bands': [], 'evidence': []}
        rows.append({'academyId': a['id'], 'name': a['name'],
                     'regionId': a.get('region_id'), 'address': a.get('road_address'),
                     **target, 'reviewSignals': a.get('grade_review_signals') or {}})
    return {'version': VERSION, 'auditedAt': date.today().isoformat(),
            'total': len(rows), 'statuses': dict(Counter(r['status'] for r in rows)),
            'rows': rows}


def rebind_subjects(academies):
    """과목 보강 뒤 공시 학년을 다시 연결한다. 후기 학년을 배분하지 않는다."""
    from . import grade_sources
    for a in academies:
        target = a.get('grade_target')
        if not target:
            continue
        mapping = {s: set(a.get('grade_bands_by_subject', {}).get(s, []))
                   for s in a.get('subjects') or []}
        for e in target['evidence']:
            if e['field'] not in ('name', 'le_crse_list_nm', 'le_crse_nm', 'course_names'):
                continue
            for subject in e.get('subjects') or mapping:
                if subject in mapping:
                    mapping[subject].update(e['bands'])
        a['grade_bands_by_subject'] = {s: [b for b in BANDS if b in bs] for s, bs in mapping.items()}
        target['bySubject'] = a['grade_bands_by_subject']
    # 처음 공시를 읽을 때 과목 미상이어서 적용하지 못한 지점 근거도 재대조한다.
    grade_sources.apply([a for a in academies if a.get('grade_target')])
