"""Read-only public freshness audit and bounded parent-decision research queue.

No model calls, ranking edits, source collection or publication. Unknown evidence
stays unknown; the output is a research worklist, never a recommendation score.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

LIVE = 'https://openedu4u.com/assets/assets/data/'
QUESTIONS = {
    'foundations': '현재 수준을 어떻게 확인하고 기초가 부족한 단원은 어떻게 보완하나요?',
    'homework': '해당 학년·반의 하루 과제 시간과 미완료 시 지도 방식은 무엇인가요?',
    'questions': '아이가 질문하기 어려워할 때 개별 피드백을 어떻게 제공하나요?',
    'travel': '이 지점의 실제 수업 종료 시간과 하원·셔틀 경로를 확인할 수 있나요?',
}


def read_public(name):
    # Fixed origin and asset names; fetched documents never become instructions.
    if name not in ('meta.json', 'academies.json'):
        raise ValueError('unsupported public asset')
    with urlopen(LIVE + name, timeout=30) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('public asset too large')
    return json.loads(data)


def audit(meta, academies, *, now=None, region='mokdong', subject='math',
          grade='elementary', limit=20, max_age_days=3):
    if not 1 <= limit <= 20:
        raise ValueError('research limit must be 1..20')
    now = now or datetime.now(timezone.utc)
    problems = []
    age = None
    try:
        generated = datetime.fromisoformat(meta['generatedAt'].replace('Z', '+00:00'))
        if generated.tzinfo is None:
            raise ValueError('missing timezone')
        age = (now - generated).total_seconds() / 86400
        if age < -0.01:
            problems.append('future_generation_time')
        elif age > max_age_days:
            problems.append('stale_public_data')
    except (KeyError, TypeError, ValueError):
        problems.append('unknown_generation_time')
    if meta.get('mode') != 'live':
        problems.append('not_live_data')
    source_ages = {}
    for name in ('naver_blog', 'naver_cafe'):
        source = meta.get('rankingQuality', {}).get('sourceHealth', {}).get(name, {})
        try:
            checked = datetime.fromisoformat(source['checkedAt'].replace('Z', '+00:00'))
            if checked.tzinfo is None:
                raise ValueError('missing timezone')
            source_ages[name] = round((now - checked).total_seconds() / 86400, 2)
            if source_ages[name] < -0.01 or source_ages[name] > 7:
                problems.append('stale_source:' + name)
            if source.get('status') != 'available':
                problems.append('source_unavailable:' + name)
        except (KeyError, TypeError, ValueError):
            source_ages[name] = None
            problems.append('source_health_unknown:' + name)
    ids = [a.get('id') for a in academies]
    if len(ids) != len(set(ids)) or None in ids:
        problems.append('invalid_academy_identity')
    eligible, unknown = [], []
    wanted_bands = {'elem_low', 'elem_high'} if grade == 'elementary' else {grade}
    for a in academies:
        if a.get('regionId') != region or subject not in a.get('subjects', []):
            continue
        # Subject-specific evidence only. Never broaden from another subject.
        bands = a.get('gradeBandsBySubject', {}).get(subject, [])
        if not bands:
            unknown.append(a)
        elif wanted_bands.intersection(bands):
            eligible.append(a)

    def item(a, grade_unknown=False):
        score = a.get('subjectScores', {}).get(subject, {})
        gaps = []
        if grade_unknown:
            gaps.append('subject_grade_unconfirmed')
        if not a.get('tel') and not a.get('homepage'):
            gaps.append('branch_contact_missing')
        if not a.get('profile'):
            gaps.append('decision_profile_missing')
        if not a.get('evidence'):
            gaps.append('review_evidence_missing')
        target = a.get('gradeTarget') or {}
        return {'id': a['id'], 'name': a.get('displayName') or a['name'],
                'address': a.get('address'), 'gradeStatus': 'unknown' if grade_unknown else 'recorded',
                'gradeBasis': {band: basis for band, basis in
                               target.get('bandBasis', {}).get(subject, {}).items()
                               if band in wanted_bands},
                'ranked': bool(score.get('isRanked')), 'gaps': gaps,
                'nextAction': 'verify_branch_official_sources',
                'searchQuery': ' '.join(filter(None, [a['name'], a.get('dong'), '초등 모집 공식'])),
                'consultationQuestions': QUESTIONS,
                'profileUrl': 'https://openedu4u.com/a/' + str(a['id']) + '.html',
                'fitVerdict': 'not_assessed'}

    # Three strata: documented grades/ranked, documented grades/unranked, unknown.
    # Round-robin prevents the research budget going entirely to popular brands.
    groups = [[], [], []]
    for a in eligible:
        row = item(a)
        groups[0 if row['ranked'] else 1].append(row)
    groups[2] = [item(a, True) for a in unknown]
    for group in groups:
        group.sort(key=lambda r: (-len(r['gaps']), str(r['id'])))
    queue = []
    while len(queue) < limit and any(groups):
        for group in groups:
            if group and len(queue) < limit:
                queue.append(group.pop(0))
    quality = meta.get('rankingQuality', {})
    return {'checkedAt': now.isoformat(), 'generatedAt': meta.get('generatedAt'),
            'ageDays': round(age, 2) if age is not None else None,
            'healthy': not problems, 'problems': problems,
            'sourceAgeDays': source_ages,
            'pilot': {'region': region, 'subject': subject, 'grade': grade,
                      'eligible': len(eligible), 'gradeUnknown': len(unknown)},
            'datedShare': quality.get('datedShare'), 'researchQueue': queue,
            'publication': 'research_only', 'modelCalls': 0,
            'acceptance': 'Every fit reason must resolve to branch-specific evidence; unknowns remain visible.'}


def publication_comparison(current, previous):
    """Hold unexplained evidence cliffs for review; never relax attribution gates.

    Counts are operational coverage, not proof of correctness. The 30% hold is a
    conservative release threshold, not a new ranking weight or fit criterion.
    """
    before = previous.get('rankingQuality', {}).get('validMentions')
    after = current.get('rankingQuality', {}).get('validMentions')
    valid = lambda n: isinstance(n, int) and not isinstance(n, bool) and n >= 0
    problems = []
    retained = None
    if previous.get('mode') != 'live' or not valid(before) or not valid(after):
        problems.append('publication_baseline_unknown')
    elif before:
        retained = after / before
        if retained < 0.70:
            problems.append('evidence_coverage_drop_requires_review')
    return {'previousGeneratedAt': previous.get('generatedAt'),
            'previousValidMentions': before, 'candidateValidMentions': after,
            'retainedShare': retained, 'minimumRetainedShare': 0.70,
            'problems': problems}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true')
    p.add_argument('--compare-live', action='store_true',
                   help='Hold large coverage drops against the deployed snapshot')
    p.add_argument('--asset-dir', type=Path, default=Path('app/assets/data'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fail-unhealthy', action='store_true')
    args = p.parse_args(argv)
    load = read_public if args.live else lambda n: json.loads((args.asset_dir / n).read_text())
    report = audit(load('meta.json'), load('academies.json'))
    if args.compare_live:
        comparison = publication_comparison(load('meta.json'), read_public('meta.json'))
        report['publicationComparison'] = comparison
        report['problems'].extend(comparison['problems'])
        report['healthy'] = not report['problems']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['healthy', 'ageDays', 'problems', 'pilot', 'modelCalls']}))
    return 1 if args.fail_unhealthy and not report['healthy'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
