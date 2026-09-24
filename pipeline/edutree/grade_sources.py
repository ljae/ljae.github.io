"""지점과 과목을 대조한 웹 모집 안내를 대상 학년에 연결한다.

검색 결과는 후보일 뿐이다. 검토한 근거 대장 또는 주소를 보존한 디렉터리의
명시적 대상 필드만 적용한다. 교재 수준·후기 속 자녀 학년은 사용하지 않는다.
"""
from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlparse

from . import config

SOURCE_FILE = config.DATA_DIR / 'grade_sources.json'


def load():
    return json.loads(SOURCE_FILE.read_text(encoding='utf-8')) if SOURCE_FILE.exists() else []


def valid_record(record, today):
    from .grade_targets import BANDS
    try:
        checked = date.fromisoformat(record['checkedAt'])
        until = date.fromisoformat(record['reviewBy'])
        if not checked <= today <= until or (until - checked).days > 180:
            return False
        if record['sourceType'] not in ('official', 'directory'):
            return False
        if record['scope'] not in ('branch', 'branch_program'):
            return False
        if record.get('reviewStatus') != 'verified':
            return False
        if not all(record.get(k) for k in ('registrationId', 'name', 'address', 'identityText', 'summary')):
            return False
        for key in ('identityUrl', 'gradeUrl'):
            parsed = urlparse(record[key])
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                return False
        mapping = record['bySubject']
        return bool(mapping) and all(
            subject in ('math', 'english', 'korean', 'science', 'arts', 'etc')
            and isinstance(bands, list) and bands and set(bands) <= set(BANDS)
            for subject, bands in mapping.items())
    except (KeyError, TypeError, ValueError):
        return False


def apply(academies, records=None, today=None, registrations=None):
    from .grade_targets import BANDS
    today = today or date.today()
    records = load() if records is None else records
    by_id = {}
    for r in records:
        if valid_record(r, today):
            by_id.setdefault(str(r['registrationId']), []).append(r)
    for a in academies:
        ids = {str(a['id']), *map(str, a.get('registration_ids') or [])}
        target = a['grade_target']
        mapping = a['grade_bands_by_subject']
        for aid in sorted(ids):
            for r in by_id.get(aid, []):
                # 등록번호가 통합체 안에 있다는 사실만으로 지점 안내를
                # 적용하지 않는다. 원 등록의 도로명주소까지 같아야 한다.
                registration = (registrations or {}).get(aid) or {}
                if registrations is not None and registration.get('road_address') != r['address']:
                    continue
                # 대장의 ID만 맞아도 주소·이름이 달라졌으면 재검토해야 한다.
                if r['address'] != a.get('road_address') or r['name'] != a.get('name'):
                    continue
                # 주소·등록번호·대표명을 모두 대조한 공식 과정 안내는
                # NEIS 의 포괄 분류(general)보다 구체적인 과목 정보를 준다.
                # 확인된 과목을 먼저 보강한 뒤 학년을 같은 과목에 연결한다.
                subjects = set(r['bySubject'])
                if not subjects:
                    continue
                a['subjects'] = list(dict.fromkeys([*(a.get('subjects') or []), *sorted(subjects)]))
                for subject in subjects:
                    mapping[subject] = [b for b in BANDS
                                        if b in mapping.get(subject, []) or b in r['bySubject'][subject]]
                item = {
                    'registrationId': aid, 'field': 'web_grade_guidance',
                    'text': r['summary'], 'subjects': sorted(subjects),
                    'bands': [b for b in BANDS if any(b in r['bySubject'][s] for s in subjects)],
                    'bySubject': {s: r['bySubject'][s] for s in sorted(subjects)},
                    'url': r['gradeUrl'], 'identityUrl': r['identityUrl'],
                    'identityText': r['identityText'], 'sourceType': r['sourceType'],
                    'scope': r['scope'], 'checkedAt': r['checkedAt'], 'reviewBy': r['reviewBy'],
                }
                if item not in target['evidence']:
                    target['evidence'].append(item)
        web = [e for e in target['evidence'] if e['field'] == 'web_grade_guidance']
        if not web:
            continue
        a['grade_bands'] = [b for b in BANDS if b in a['grade_bands'] or any(b in bs for bs in mapping.values())]
        official = any(e['sourceType'] == 'official' for e in web)
        target.update(
            status='official_guidance' if official or target['status'] == 'official_guidance' else 'directory_guidance',
            basis='공시·공식 모집 안내·학원 소개 대조' if official else '공시·학원 소개의 대상 학년 대조',
            bands=a['grade_bands'], bySubject=mapping,
            caveat='확인한 모집 대상 기준입니다. 선행 교재의 학년은 포함하지 않습니다. 현재 개설 반은 지점에 확인해 주세요.',
        )
        target['unverifiedPreviousBands'] = [b for b in target.get('unverifiedPreviousBands', [])
                                           if b not in a['grade_bands']]


def source_notes(academies):
    """앱의 출처 패널에 학년 배분 근거와 확인일을 함께 공개한다."""
    out = []
    for a in academies:
        target = a.get('grade_target') or {}
        notes = []
        for e in target.get('evidence') or []:
            if e.get('field') != 'web_grade_guidance':
                continue
            notes.append({'topic': '대상 학년', 'title': '대상 학년 확인 근거',
                          'summary': e['text'], 'url': e['url'],
                          'checkedAt': e['checkedAt'], 'kind': e['sourceType'],
                          'sourceScope': 'brand' if e['scope'] == 'branch_program' else 'branch',
                          'subjects': e['subjects']})
        if notes:
            out.append({'academyId': a['id'], 'name': a['name'],
                        'scope': '학원명·등록번호·주소를 대조한 학년 안내',
                        'caveat': target['caveat'], 'notes': notes})
    return out
