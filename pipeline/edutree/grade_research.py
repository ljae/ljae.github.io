"""미확인 과목의 검색 대기열. 검색 스니펫은 확정 학년으로 승격하지 않는다.

python -m pipeline.edutree.grade_research [--discover --limit 40]
출력: pipeline/.cache/grade_research.json (Aside 등에서 읽을 지점별 질의/후보)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from . import config


def queue(academies, previous=None):
    previous = previous or {}
    out = []
    regions = {r['id']: r['name_ko'] for r in config.regions()}
    for a in academies:
        unknown = [s for s in a['subjects']
                   if not a.get('gradeBandsBySubject', {}).get(s)]
        if not unknown:
            continue
        score = a.get('score') or {}
        old = previous.get(a['id'], {})
        out.append({'academyId': a['id'], 'name': a['name'], 'address': a['address'],
                    'regionId': a['regionId'], 'subjectsToCheck': unknown,
                    'homepage': a.get('homepage'),
                    'query': f"{a['name']} {regions.get(a['regionId'], '')} 대상 학년 입학 모집",
                    'identityQuery': f"{a['name']} {a['address']}",
                    'priority': [bool(score.get('isRanked')), score.get('sampleSize') or 0,
                                 bool(a.get('homepage')), 'general' not in unknown],
                    'lastSearchedAt': old.get('lastSearchedAt'),
                    'searchStatus': old.get('searchStatus', 'pending'),
                    'candidates': old.get('candidates', [])})
    # 첫 검색을 마친 학원은 뒤로 보낸다. 실패만 반복해 같은 학원을 붙들지 않는다.
    return sorted(out, key=lambda r: (r['lastSearchedAt'] or '',
                                     *[-int(n) for n in r['priority']], r['academyId']))


def discover(rows, limit, search):
    for row in rows[:max(0, limit)]:
        row['lastSearchedAt'] = datetime.now(timezone.utc).isoformat()
        try:
            results = search('naver_web', row['query'], max_results=5)
            row['candidates'] = [{k: item.get(k) for k in ('title', 'url', 'snippet')}
                                 for item in results]
            row['searchStatus'] = 'needs_review' if results else 'no_results'
        except Exception as exc:
            # 오류 문자열에는 인증 정보가 섞일 수 있어 타입만 기록한다.
            row['searchStatus'] = f'error:{type(exc).__name__}'
    return rows


def run(discovery=False, limit=40):
    path = config.CACHE_DIR / 'grade_research.json'
    previous = json.loads(path.read_text()) if path.exists() else {'rows': []}
    academies = []
    for name in ('academies.json', 'registry.json'):
        academies.extend(json.loads((config.EXPORT_DIR / name).read_text()))
    rows = queue(academies, {r['academyId']: r for r in previous['rows']})
    if discovery and config.HAS_NAVER:
        from . import naver
        discover(rows, limit, naver.search)
    report = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'total': len(rows),
              'instruction': '공식 원문에서 지점명·주소·과목·재학/모집 학년을 대조 후 data/grade_sources.json에 verified로 기록. 후기·교재 학년·검색 스니펫만으로 배분 금지.',
              'discovery': 'enabled' if discovery and config.HAS_NAVER else 'not_run',
              'rows': rows}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'학년 조사 대기열: {len(rows):,}곳 → {path}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--discover', action='store_true')
    ap.add_argument('--limit', type=int, default=40)
    args = ap.parse_args()
    run(args.discover, args.limit)
