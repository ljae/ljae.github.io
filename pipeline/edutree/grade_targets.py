"""학원별 대상 학년 전수 감사 — 근거의 등급을 나누고, 어느 등급이 정했는지 남긴다.

    official    주소·등록번호까지 대조한 공식 모집 안내 (verified_branches · grade_sources)
    directory   주소를 대조한 학원 소개 디렉터리 (grade_sources)
    registered  교육청 등록명·교습과정·과정명에 **명시된** 학년
    curated     시드 브랜드의 사람 큐레이션 단계(seed_academies.yaml)가 걸치는 구간
    reviews     후기가 이름 곁(±45자)에서 **반복해** 말한 구간 — 서로 다른 작성자
                REVIEW_MIN_AUTHORS 명 이상 · REVIEW_MIN_MENTIONS 건 이상 ·
                그 과목의 학년 언급 중 REVIEW_MIN_SHARE 이상

공시 과정은 현재 모집 학년의 전수 확인과 같지 않다. 명시된 학년만 registered 로
읽고, 선행 과정처럼 재학 학년과 구별할 수 없는 문구는 보류한다. 다섯 등급 중
하나도 없으면 미확인이다 — 미확인은 '전 학년' 도 '해당 없음' 도 아니다.

★ 2026-09-19 에는 registered·official 만 인정했다. 그러자 채점된 (학원×과목)
  581쌍 중 457쌍(79%)이 어느 학년 랭킹에도 못 들어갔다 — 강대·트윈클·렉스김·
  소마처럼 표본 100건이 넘는 곳이 전부 '미확인' 이었다. NEIS 교습과정이
  '보습·논술'·'실용외국어(유아/초·중·고)' 뿐인 학원이 대부분이라 공시만으로는
  영영 못 채운다. 그래서 등급을 넓히되 **어느 등급인지를 학년마다 적는다**
  (`bandBasis`) — 화면이 그것을 구분해 적지 않으면 후기 추정이 공시처럼 읽힌다.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

BANDS = ('elem_low', 'elem_high', 'middle', 'high')
VERSION = '2026-09-20.3'
NEIS_URL = 'https://open.neis.go.kr/hub/acaInsTiInfo'
NEIS_FIELDS = ('name', 'le_crse_list_nm', 'le_crse_nm', 'course_names')

# 근거 등급. 같은 학년에 둘 이상이 있으면 높은 쪽을 적는다.
BASIS_RANK = {'official': 4, 'directory': 3, 'registered': 2, 'curated': 1, 'reviews': 0}
BASIS_LABEL = {
    'official': '공식 모집 안내',
    'directory': '학원 소개 대조',
    'registered': '교육청 등록명·교습과정',
    'curated': '브랜드 큐레이션 단계',
    'reviews': '후기 반복 언급',
}
STATUS_BY_BASIS = {
    'official': 'official_guidance',
    'directory': 'directory_guidance',
    'registered': 'registered_courses',
    'curated': 'curated_stages',
    'reviews': 'review_mentions',
}

# 후기로 학년을 확정하는 문턱. 한 사람 말은 아직 한 사람 말이고(진입난이도
# 확인율·영유 연차와 같은 규칙), 한두 건은 형제 학년·선행 진도일 수 있다.
# 25% 는 실측에서 정했다 — 명인학원(고 53 · 중 31 · 초 2)은 중·고, 띵킹어학원
# (초저 16 · 고 6 · 초고 2)은 초저만 남는 선이다.
REVIEW_MIN_MENTIONS = 3
REVIEW_MIN_AUTHORS = 2
REVIEW_MIN_SHARE = 0.25

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
    # '서초2관/서초3관'은 서초 지역의 관 번호다. GRADE 정규식이 내부의
    # '초2/초3'만 읽으면 관 번호가 학생 학년으로 둔갑한다.
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


# ── 근거 장부 ────────────────────────────────────────────────────────

def note_bands(a, subject, bands, basis):
    """과목의 학년에 근거를 적는다. 이미 더 높은 등급이 있으면 등급은 그대로.

    돌려주는 것은 **새로 생긴** 학년이다 — 근거 항목을 한 번만 적기 위해.
    """
    if basis not in BASIS_RANK:
        raise ValueError(f'알 수 없는 근거 등급 {basis!r}')
    mapping = a.setdefault('grade_bands_by_subject', {})
    ledger = a.setdefault('grade_band_basis', {}).setdefault(subject, {})
    have = set(mapping.get(subject) or [])
    new = [b for b in BANDS if b in bands and b not in have]
    for b in bands:
        if b not in BANDS:
            continue
        if BASIS_RANK[basis] >= BASIS_RANK.get(ledger.get(b), -1):
            ledger[b] = basis
    mapping[subject] = [b for b in BANDS if b in have or b in bands]
    return new


def _drop_basis(a, basis, field):
    """한 등급의 근거를 전부 걷어 낸다(다시 적기 전에). 멱등을 위해서다."""
    target = a.get('grade_target') or {}
    target['evidence'] = [e for e in target.get('evidence') or [] if e.get('field') != field]
    for subject, ledger in (a.get('grade_band_basis') or {}).items():
        gone = [b for b, k in ledger.items() if k == basis]
        for b in gone:
            del ledger[b]
        if gone:
            a['grade_bands_by_subject'][subject] = [
                b for b in a['grade_bands_by_subject'].get(subject, []) if b not in gone]


def sync(a):
    """장부에서 전역 학년·상태·근거 문구를 다시 짓는다. 한 곳에서만 짓는다."""
    mapping = a.setdefault('grade_bands_by_subject', {})
    ledger = a.setdefault('grade_band_basis', {})
    for subject in list(mapping):
        keep = [b for b in mapping[subject] if b in ledger.get(subject, {})]
        mapping[subject] = [b for b in BANDS if b in keep]
    a['grade_bands'] = [b for b in BANDS if any(b in bs for bs in mapping.values())]
    present = {k for l in ledger.values() for k in l.values()}
    ordered = sorted(present, key=lambda k: -BASIS_RANK[k])
    target = a.setdefault('grade_target', {'evidence': []})
    best = ordered[0] if ordered else None
    if 'reviews' in present or 'curated' in present:
        caveat = ('공시에 없는 학년은 브랜드 단계·후기 반복 언급으로 정했습니다. '
                  '현재 개설 반은 학원에 확인해 주세요.')
    elif best in ('official', 'directory'):
        caveat = ('확인한 모집 대상 기준입니다. 선행 교재의 학년은 포함하지 않습니다. '
                  '현재 개설 반은 지점에 확인해 주세요.')
    else:
        caveat = '공시 과정 기준이며 현재 모집 학년은 학원에 확인이 필요합니다.'
    target.update(
        status=STATUS_BY_BASIS[best] if best else 'unknown',
        basis=' + '.join(BASIS_LABEL[k] for k in ordered) if ordered else '대상 학년 미확인',
        bands=a['grade_bands'], bySubject=mapping,
        bandBasis={s: dict(l) for s, l in ledger.items() if l},
        caveat=caveat,
    )
    target['unverifiedPreviousBands'] = [
        b for b in target.get('unverifiedPreviousBands', []) if b not in a['grade_bands']]
    return a


# ── 등급별 적용 ──────────────────────────────────────────────────────

_STAGE_MAP: dict | None = None


def _stage_map():
    """단계 id → (과목, (시작 학년, 끝 학년), 제목). 로드맵 전용 단계는 뺀다."""
    global _STAGE_MAP
    if _STAGE_MAP is None:
        from . import config
        _STAGE_MAP = {st['id']: (t['subject'], tuple(st['grade']), st.get('title', st['id']))
                      for t in config.techtree()['tracks'] for st in t['stages']
                      if not st.get('roadmap_only')}
    return _STAGE_MAP


def apply_curated(a):
    """시드 큐레이션 단계(stage_basis == curated)가 걸치는 구간을 그 과목에 적는다.

    seed_academies.yaml 은 사람이 적은 것이다 — '소마는 사고력(초등)', '강남대성은
    N수(고등)'. 9/19 이후 이것이 통째로 버려져 시드 학원의 단계까지 함께
    사라졌다(학년이 비면 `_prepare_live` 가 단계를 전부 거른다).
    """
    from . import config
    stage_basis = a.get('stage_basis') or {}
    stages = [s for s in a.get('stages') or []
              if stage_basis.get(s) == 'curated' or (not stage_basis and a.get('curated_stages'))]
    mapping = a.setdefault('grade_bands_by_subject', {})
    added = 0
    for sid in stages:
        info = _stage_map().get(sid)
        if not info:
            continue
        subject, (lo, hi), title = info
        if subject not in mapping:
            continue
        bands = config.bands_for_range(lo, hi)
        if not bands:
            continue
        new = note_bands(a, subject, bands, 'curated')
        if new:
            added += 1
            a['grade_target']['evidence'].append({
                'registrationId': str(a['id']), 'field': 'curated_stage', 'stageId': sid,
                'text': f'큐레이션 단계 {title}', 'bands': bands,
                'subjects': [subject], 'basis': 'curated'})
    return added


def confirm_from_reviews(a, signals):
    """후기가 반복해 말한 구간을 그 과목의 학년으로 적는다.

    signals = {과목: {구간: {'mentions': n, 'authors': k}}}. 과목은 글이 이름
    곁에서 말한 과목이고, 과목 불명 글은 대표 과목 몫이다(채점과 같은 규칙).
    멱등이다 — 지난 실행의 reviews 근거를 걷어 내고 다시 적는다.
    """
    a['grade_review_by_subject'] = signals or {}
    target = a.setdefault('grade_target', {'evidence': []})
    _drop_basis(a, 'reviews', 'review_mentions')
    changed = False
    for subject in a.get('subjects') or []:
        bands = (signals or {}).get(subject) or {}
        total = sum(v.get('mentions', 0) for v in bands.values())
        if not total:
            continue
        passed = {}
        for band in BANDS:
            v = bands.get(band)
            if not v:
                continue
            n, k = v.get('mentions', 0), v.get('authors', 0)
            if n < REVIEW_MIN_MENTIONS or k < REVIEW_MIN_AUTHORS or n / total < REVIEW_MIN_SHARE:
                continue
            passed[band] = (n, k)
        known = set(a['grade_bands_by_subject'].get(subject) or [])
        for band in _contiguous(known, passed):
            n, k = passed[band]
            new = note_bands(a, subject, [band], 'reviews')
            if new:
                changed = True
                target['evidence'].append({
                    'registrationId': str(a['id']), 'field': 'review_mentions',
                    'text': f'후기 {n}건(작성자 {k}명)이 이름 곁에서 이 구간을 말함',
                    'bands': [band], 'subjects': [subject], 'basis': 'reviews',
                    'mentions': n, 'authors': k, 'share': round(n / total, 2)})
    sync(a)
    return changed


def _contiguous(known, passed):
    """문턱을 넘은 후기 구간 중 **이어지는** 것만 남긴다.

    학원은 이어진 학년을 받는다 — 초1~3 과 고등을 받으면서 초4~중등은 안 받는
    곳은 드물다. 그런데 초등 학원의 후기에는 '의대'·'수능까지'·'고등 가면'
    같은 **바람**이 이름 곁에 자주 온다. 실측(운영 산출물 9/20): 대치소마
    초저 54 · 고 24, 렉스김 초저 35 · 고 28, 반포시매쓰 초저 34 · 고 23 —
    셋 다 초등 학원인데 고등이 25% 를 넘었다. 떨어진 구간은 바람이지 반이
    아니다.

    이미 아는 구간(공시·큐레이션·공식)이 있으면 거기서 이어지는 것만, 없으면
    가장 많이 말한 구간에서 이어지는 것만 받는다. 동점이면 낮은 학년부터 —
    구간 순서가 곧 정렬 키라 결정적이다.
    """
    if not passed:
        return []
    order = list(BANDS)
    if known:
        seed = set(known)
    else:
        top = max(passed, key=lambda b: (passed[b][0], -order.index(b)))
        seed = {top}
    accepted = {b for b in passed if b in seed}
    grown = True
    while grown:
        grown = False
        for band in passed:
            if band in accepted or band in seed:
                continue
            i = order.index(band)
            neighbours = {order[j] for j in (i - 1, i + 1) if 0 <= j < len(order)}
            if neighbours & (seed | accepted):
                accepted.add(band)
                grown = True
    return [b for b in order if b in accepted]


def _apply_registered(a, registrations):
    evidence, held = [], []
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
            if not bands:
                continue
            named_subjects = _subjects(value)
            school_levels = {'elementary' if b.startswith('elem_') else b for b in bands}
            if len(named_subjects) > 1 and len(school_levels) > 1:
                held.append({'registrationId': str(aid), 'field': field, 'text': value,
                             'reason': '과목별 학년 구분 불명'})
                continue
            for subject in named_subjects or set(a['grade_bands_by_subject']):
                if subject in a['grade_bands_by_subject']:
                    note_bands(a, subject, bands, 'registered')
            evidence.append({'registrationId': str(aid), 'field': field,
                             'text': value, 'bands': bands, 'subjects': sorted(named_subjects),
                             'url': NEIS_URL, 'basis': 'registered'})
    return evidence, held


def apply_all(academies, registrations):
    """통합된 학원의 모든 등록 원문을 다시 대조. 과거 추정 값을 물려받지 않는다."""
    from . import grade_sources, verified_branches
    for a in academies:
        previous = a.get('grade_bands') or []
        a['grade_bands_by_subject'] = {s: [] for s in a.get('subjects', [])}
        a['grade_band_basis'] = {}
        a['grade_target'] = {
            'evidence': [], 'heldCourseSignals': [],
            'unverifiedPreviousBands': list(previous),
            'auditedAt': date.today().isoformat(), 'version': VERSION,
        }
        evidence, held = _apply_registered(a, registrations)
        a['grade_target']['evidence'] = evidence
        a['grade_target']['heldCourseSignals'] = held
        apply_curated(a)
        verified_branches.apply_grades(a)
        sync(a)
    grade_sources.apply(academies, registrations=registrations)


def report(academies):
    rows = []
    for a in academies:
        target = a.get('grade_target') or {'status': 'unknown', 'bands': [], 'evidence': []}
        rows.append({'academyId': a['id'], 'name': a['name'],
                     'regionId': a.get('region_id'), 'address': a.get('road_address'),
                     **target, 'reviewSignals': a.get('grade_review_signals') or {},
                     'reviewSignalsBySubject': a.get('grade_review_by_subject') or {}})
    statuses = Counter(r['status'] for r in rows)
    bases = Counter(k for r in rows for l in (r.get('bandBasis') or {}).values() for k in l.values())
    return {'version': VERSION, 'auditedAt': date.today().isoformat(),
            'total': len(rows), 'statuses': dict(statuses), 'bandBasisCounts': dict(bases),
            'rows': rows}


def rebind_subjects(academies):
    """과목 보강 뒤 학년을 다시 연결한다. 근거 장부를 새 과목 목록으로 되짚는다."""
    from . import grade_sources, verified_branches
    for a in academies:
        target = a.get('grade_target')
        if not target:
            continue
        a['grade_bands_by_subject'] = {s: [] for s in a.get('subjects') or []}
        a['grade_band_basis'] = {}
        kept = []
        for e in target['evidence']:
            if e.get('field') in NEIS_FIELDS:
                kept.append(e)
                for subject in e.get('subjects') or list(a['grade_bands_by_subject']):
                    if subject in a['grade_bands_by_subject']:
                        note_bands(a, subject, e['bands'], 'registered')
            # curated·official·web·reviews 근거는 아래에서 다시 적는다.
        target['evidence'] = kept
        apply_curated(a)
        verified_branches.apply_grades(a)
        sync(a)
    # 처음 공시를 읽을 때 과목 미상이어서 적용하지 못한 지점 근거도 재대조한다.
    grade_sources.apply([a for a in academies if a.get('grade_target')])
    for a in academies:
        if a.get('grade_target') and a.get('grade_review_by_subject'):
            confirm_from_reviews(a, a['grade_review_by_subject'])
