"""공시 캐시와 검토한 웹 근거로 학년만 재배포. 평점·후기 재채점 없음.

python -m pipeline.edutree.refresh_grades
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from . import build, config, grade_sources, grade_targets, verified_branches


def refresh(payloads, registrations):
    """출력 레코드의 학년/단계 필드만 갱신한다. 입력은 수정하지 않는다."""
    result = deepcopy(payloads)
    rows = []
    for p in result:
        ids = [str(p['id']), *map(str, p.get('registrationIds') or [])]
        missing = [aid for aid in ids if aid not in registrations]
        if missing:
            raise ValueError(f"등록 공시 누락: {', '.join(missing)}")
        r = {**registrations[str(p['id'])], 'id': p['id'], 'name': p['name'],
             'road_address': p['address'], 'region_id': p['regionId'],
             'subjects': list(p['subjects']), 'registration_ids': ids,
             'grade_bands': list(dict.fromkeys([
                 *p.get('gradeBands', []),
                 *(p.get('gradeTarget') or {}).get('unverifiedPreviousBands', [])])),
             'grade_review_signals': p.get('gradeReviewSignals') or {}}
        rows.append(r)
    verified_branches.apply(rows)
    # 이 명령은 과목/동일성 수정용이 아니다. 기존 출력의 과목으로만 배분한다.
    for r, p in zip(rows, result):
        r['subjects'] = list(p['subjects'])
    grade_targets.apply_all(rows, registrations)
    stage_grades = {s['id']: (t['subject'], s['grade'])
                    for t in config.techtree()['tracks'] for s in t['stages']}
    for p, r in zip(result, rows):
        grades_changed = p.get('gradeBandsBySubject') != r['grade_bands_by_subject']
        p.update(gradeBands=r['grade_bands'],
                 gradeBandsBySubject=r['grade_bands_by_subject'], gradeTarget=r['grade_target'])
        if 'stages' not in p:
            continue
        stages = [s for s in p['stages'] if s in stage_grades and
                  set(r['grade_bands_by_subject'].get(stage_grades[s][0], [])).intersection(
                      config.bands_for_range(*stage_grades[s][1]))]
        basis = {s: b for s, b in p.get('stageBasis', {}).items() if s in stages}
        auto, auto_basis = build._auto_stages(r) if grades_changed else ([], {})
        # 새 학년 구간의 대표 단계도 연결하되 기존 큐레이션을 보존한다.
        for s in auto:
            if s not in stages:
                stages.append(s)
                basis[s] = auto_basis[s]
        p.update(stages=stages, stageBasis=basis,
                 flagship=[s for s in p.get('flagship', []) if s in stages])
    return result, rows


def run(asset_dir, registrations_path):
    def read(name):
        return json.loads((asset_dir / name).read_text(encoding='utf-8'))

    originals = read('academies.json')
    registry = read('registry.json')
    raw = json.loads(registrations_path.read_text(encoding='utf-8'))
    registrations = {str(r['id']): r for r in raw}
    updated, rows = refresh(originals + registry, registrations)
    report = grade_targets.report(rows)
    # 리뷰에서 관찰한 학년은 근거와 별도로 기존 감사 보고서에 보존한다.
    prior = {r['academyId']: r for r in read('grade_targets.json')['rows']}
    for row in report['rows']:
        row['reviewSignals'] = prior.get(row['academyId'], {}).get('reviewSignals', {})
    meta = read('meta.json')
    meta['gradeTargetAudit'] = {k: v for k, v in report.items() if k != 'rows'}
    meta['gradeTargetUpdatedAt'] = datetime.now(timezone.utc).isoformat()
    tree = read('techtree.json')
    counts = {d['id']: d for d in build._destination_payload(updated[:len(originals)])}
    for d in tree['destinations']:
        d.update({k: counts[d['id']][k] for k in ('stageCounts', 'academyCount')})
    files = {'academies.json': updated[:len(originals)], 'registry.json': updated[len(originals):],
             'grade_targets.json': report, 'grade_sources.json': grade_sources.source_notes(rows),
             'meta.json': meta, 'techtree.json': tree}
    # 전체 검증·직렬화를 끝낸 후 파일별 원자적 교체.
    encoded = {name: json.dumps(data, ensure_ascii=False, indent=1)
               for name, data in files.items()}
    for name, data in encoded.items():
        temp = asset_dir / (name + '.tmp')
        temp.write_text(data, encoding='utf-8')
        temp.replace(asset_dir / name)
    before = sum(bool(a.get('gradeBands')) for a in originals + registry)
    after = sum(bool(a.get('gradeBands')) for a in updated)
    print(f'학년 확인: {before:,} → {after:,} / {len(updated):,}곳 (평점·후기 보존)')
    return updated


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--asset-dir', type=Path, default=config.EXPORT_DIR)
    ap.add_argument('--registrations', type=Path, default=config.CACHE_DIR / 'neis_academies.json')
    args = ap.parse_args()
    run(args.asset_dir, args.registrations)
