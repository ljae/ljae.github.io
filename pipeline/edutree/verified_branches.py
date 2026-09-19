"""주소·등록번호까지 대조한 공식 안내. 점수가 아니라 검색·대상 정보만 보강한다."""
from __future__ import annotations
import json
from datetime import date
from . import config


def load():
    return json.loads((config.DATA_DIR / 'verified_branches.json').read_text())


def apply(academies, records=None, today=None):
    today = today or date.today()
    records = load() if records is None else records
    active = [r for r in records if date.fromisoformat(r['checkedAt']) <= today <= date.fromisoformat(r['reviewBy'])]
    for a in academies:
        # 가족 관계는 글을 더 붙이는 근거가 아니라 지점 불명 글을 보류하는 장치다.
        for r in active:
            if a.get('name', '').startswith(r['nameToken']):
                a['identity_family'] = r['nameToken']
        ids = {str(a['id']), *map(str, a.get('registration_ids') or [])}
        for r in records:
            # 같은 건물의 다른 학원이나 같은 이름의 다른 지점으로 전파하지 않는다.
            if str(r['registrationId']) not in ids or r['address'] != a.get('road_address'):
                continue
            if r['nameToken'] not in a.get('name', ''):
                continue
            if not date.fromisoformat(r['checkedAt']) <= today <= date.fromisoformat(r['reviewBy']):
                continue
            a['aliases'] = list(dict.fromkeys([*(a.get('aliases') or []), *r['aliases']]))
            a['subjects'] = list(dict.fromkeys([s for s in a.get('subjects', []) if s != 'general'] + r['subjects']))
            a['homepage'] = r['homepage']
            a['branch_identity_words'] = r.get('identityTerms', [])
            a['verified_branch'] = r


def apply_grades(a):
    r = a.get('verified_branch')
    if not r:
        return
    target = a['grade_target']
    by_subject = a['grade_bands_by_subject']
    for subject, bands in r['bySubject'].items():
        by_subject[subject] = list(bands)
    from .grade_targets import BANDS
    a['grade_bands'] = [b for b in BANDS if any(b in bs for bs in by_subject.values())]
    target.update(status='official_guidance', basis=r['basis'], bands=a['grade_bands'], bySubject=by_subject,
                  caveat=r['caveat'], checkedAt=r['checkedAt'], reviewBy=r['reviewBy'])
    target['evidence'].append({'registrationId':r['registrationId'], 'field':'official_guidance',
                              'text':r['summary'], 'bands':a['grade_bands'], 'subjects':r['subjects'],
                              'url':r['gradeUrl'], 'identityUrl':r['identityUrl'], 'checkedAt':r['checkedAt']})
