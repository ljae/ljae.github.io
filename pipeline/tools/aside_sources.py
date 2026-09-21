"""Aside 브라우저로 학원별 소스를 찾는다 — 공식 채널 · 대상 학년 · 네이버 플레이스 · 후기 · 디렉터리.

    .venv/bin/python pipeline/tools/aside_sources.py            # 순위권인데 학년 미확인인 학원 전부
    .venv/bin/python pipeline/tools/aside_sources.py --limit 5  # 앞 5곳만
    .venv/bin/python pipeline/tools/aside_sources.py --ids 10268,4978
    .venv/bin/python pipeline/tools/aside_sources.py --aggregate # 결과를 보고서·후보 파일로 모으기만

결과는 **후보**다. 파이프라인은 자동으로 읽지 않는다.
  - docs/reports/aside-sources-<날짜>.md          사람 검토용 보고서
  - pipeline/data/grade_source_candidates.json   대상 학년 후보(reviewStatus: candidate)
    → 원문 확인 후 verified 로 바꿔 grade_sources.json 으로 옮긴다. 대장은 verified 만 담는다.
  - 공식 채널은 확인 후 위키 academies/<id>.md 의 homepage: 에 사람이 적는다.

Aside 는 사용자 브라우저를 쓴다. Google 은 봇 차단이 뜨므로 네이버만 쓰게 한다.
세션 하나가 매달리면 배치 전체가 죽지 않게 학원마다 시간 제한을 두고, 모델 사용량
한도('usage limit')가 뜨면 남은 학원을 건너뛰고 멈춘다 — 이어서 돌리면 안 된 곳만 다시 한다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / 'app' / 'assets' / 'data'
OUT = ROOT / 'pipeline' / '.cache' / 'aside_sources'
REGION = {'daechi': '대치', 'mokdong': '목동', 'banpo': '반포', 'jamsil': '잠실'}
SUBJ = {'math': '수학', 'english': '영어', 'korean': '국어', 'science': '과학', 'arts': '예체능', 'etc': '기타'}
BAND = {'초등': ['elem_low', 'elem_high'], '초등저학년': ['elem_low'], '초등고학년': ['elem_high'],
        '예비초': ['elem_low'], '예비중': ['elem_high'], '중등': ['middle'], '중학': ['middle'],
        '예비고': ['middle'], '고등': ['high'], '고1': ['high'], '고2': ['high'], '고3': ['high'],
        '초1': ['elem_low'], '초2': ['elem_low'], '초3': ['elem_low'],
        '초4': ['elem_high'], '초5': ['elem_high'], '초6': ['elem_high'],
        '중1': ['middle'], '중2': ['middle'], '중3': ['middle']}
NO_READ = ('academy.prompie.com',)   # 오늘학교: robots ai-train=no → 근거로 쓰지 않는다
QUOTA_MARK = 'usage limit has been reached'

PROMPT = """You are researching a Korean private academy for a data pipeline. READ-ONLY: do not log in, post, write, or send anything anywhere. Use ONLY Naver (search.naver.com 통합·블로그·카페 탭, pcmap.place.naver.com / map.naver.com) and the academy's own pages. Do NOT use Google (it shows a bot challenge). Be efficient: at most ~12 page loads.

Academy: {name} ({subject} 학원, {region} 학군). NEIS 등록 주소: {address}. NEIS 전화: {tel}. Known homepage on file: {homepage}.

Find:
1. officialChannels: homepage, Naver blog, Instagram, YouTube, KakaoTalk channel. Accept a channel ONLY if it shows this address (or same building/road) or this phone, or the Naver place listing links to it. Record the evidence.
2. gradeTargets: 대상 학년 as stated by the academy itself or by a directory that lists this exact address (초등/중등/고등/예비중/고1~3 etc.), with the URL and the verbatim quote.
3. naverPlace: the Naver place listing URL for this exact address, its category, and the phone/homepage it shows.
4. reviews: up to 5 Naver blog/cafe post URLs clearly about THIS branch (same 학군/동네), with title and date if visible. Skip ads that list many academies.
5. otherSources: directory pages (강남엄마, 오늘학교, smileus, 당근 local profile, 학원비 공시 etc.) for this exact address.

Output ONLY one JSON object (no prose before or after) with keys: officialChannels [{{type,url,identityEvidence}}], gradeTargets [{{url,quote,bands}}], naverPlace {{url,category,phone,homepage}}, reviews [{{url,title,date}}], otherSources [{{url,note}}], notes (string). Empty list / null when not found. Never guess URLs."""


def targets(ids: set[str] | None) -> list[tuple[dict, str]]:
    academies = json.loads((EXPORT / 'academies.json').read_text(encoding='utf-8'))
    rows = []
    for a in academies:
        for s, sc in (a.get('subjectScores') or {}).items():
            if ids is not None:
                if a['id'] in ids:
                    rows.append((sc.get('sampleSize') or 0, a, s))
                    break
            elif (sc or {}).get('isRanked') and not (a.get('gradeBandsBySubject') or {}).get(s):
                rows.append((sc['sampleSize'], a, s))
    rows.sort(key=lambda t: -t[0])
    seen, out = set(), []
    for _, a, s in rows:
        if a['id'] not in seen:
            seen.add(a['id'])
            out.append((a, s))
    return out


def last_json(text: str) -> dict | None:
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    result = None
    for m in re.finditer(r'\{\s*"officialChannels"', text):
        chunk, depth = text[m.start():], 0
        for i, ch in enumerate(chunk):
            depth += ch == '{'
            depth -= ch == '}'
            if depth == 0:
                try:
                    result = json.loads(chunk[:i + 1])    # 마지막 **완전한** 덩어리
                except json.JSONDecodeError:
                    pass
                break
    return result


def run_one(job: tuple[dict, str], timeout: int) -> tuple[str, str]:
    a, s = job
    done = OUT / f"{a['id']}.json"
    if done.exists():
        return a['id'], 'cached'
    log = OUT / f"{a['id']}.log"
    prompt = PROMPT.format(name=a['name'], subject=SUBJ.get(s, s), region=REGION.get(a['regionId'], a['regionId']),
                           address=a.get('address') or '?', tel=a.get('tel') or '없음',
                           homepage=a.get('homepage') or '없음')
    t0 = time.time()
    with open(log, 'w') as f:
        try:
            proc = subprocess.run(['aside', 'exec', '--effort', 'medium', prompt],
                                  stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    text = log.read_text(errors='replace')
    if QUOTA_MARK in text:
        return a['id'], 'quota'
    result = last_json(text)
    if result is None:
        return a['id'], f'no-json({code})'
    done.write_text(json.dumps({
        'academyId': a['id'], 'name': a['name'], 'regionId': a['regionId'], 'subject': s,
        'address': a.get('address'), 'tel': a.get('tel'), 'homepageOnFile': a.get('homepage'),
        'result': result, 'exit': code, 'seconds': round(time.time() - t0),
        'checkedAt': date.today().isoformat()}, ensure_ascii=False, indent=1))
    return a['id'], 'ok'


def bands_of(labels) -> list[str]:
    out: list[str] = []
    for label in labels or []:
        for b in BAND.get(str(label).replace(' ', ''), []):
            if b not in out:
                out.append(b)
    return out


def host_ok(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ('http', 'https') and bool(p.netloc) and not any(h in p.netloc for h in NO_READ)
    except Exception:                                          # noqa: BLE001
        return False


def aggregate() -> dict:
    today = date.today().isoformat()
    records = [json.loads(p.read_text()) for p in sorted(OUT.glob('*.json'))]
    records.sort(key=lambda r: (r['regionId'], r['name']))
    lines = [f'# Aside 소스 탐색 — {today}', '',
             '읽기 전용 브라우저 조사(네이버만) 결과. **전부 후보다.** 파이프라인은 자동으로 읽지 않는다.',
             '- 공식 채널·홈페이지 → 확인 후 위키 `academies/<id>.md` 의 `homepage:`',
             '- 대상 학년 → `pipeline/data/grade_source_candidates.json` 의 후보를 원문 확인 후 '
             '`reviewStatus: verified` 로 바꿔 `grade_sources.json` 으로 옮긴다',
             '- 후기 → 수집 대상·수요 신호 참고. 광고성 소개글은 근거가 아니다.',
             '- 오늘학교(academy.prompie.com)는 `ai-train=no` 라 근거로 쓰지 않는다 (목록에서 뺐다).', '']
    grade_new, stats = [], {'academies': 0, 'official': 0, 'grade': 0, 'place': 0, 'reviews': 0, 'other': 0}
    for r in records:
        res = r.get('result') or {}
        stats['academies'] += 1
        lines += [f"## {r['name']} ({r['regionId']} · {SUBJ.get(r['subject'], r['subject'])}) — id {r['academyId']}",
                  f"- 주소 {r['address']} · 전화 {r['tel'] or '없음'} · 홈페이지(등록) {r['homepageOnFile'] or '없음'}"]
        oc = [c for c in res.get('officialChannels') or [] if host_ok(c.get('url', ''))]
        if oc:
            stats['official'] += 1
            lines.append('- 공식 채널:')
            lines += [f"  - {c.get('type')}: {c['url']} — {c.get('identityEvidence', '')}" for c in oc]
        place = res.get('naverPlace') or {}
        if place.get('url'):
            stats['place'] += 1
            lines.append(f"- 네이버 플레이스: {place['url']} · {place.get('category') or ''} · "
                         f"전화 {place.get('phone') or '-'} · 홈 {place.get('homepage') or '-'}")
        gts = [g for g in res.get('gradeTargets') or [] if host_ok(g.get('url', ''))]
        if gts:
            stats['grade'] += 1
            lines.append('- 대상 학년 후보:')
            for g in gts:
                bands = bands_of(g.get('bands'))
                quote = (g.get('quote') or '').strip()
                lines.append(f"  - {bands or g.get('bands')} ← {g['url']}  “{quote[:140]}”")
                if bands and r['subject'] not in ('arts', 'etc', 'general'):
                    grade_new.append({
                        'registrationId': str(r['academyId']), 'name': r['name'], 'address': r['address'],
                        'bySubject': {r['subject']: bands},
                        'identityUrl': place.get('url') or g['url'], 'gradeUrl': g['url'],
                        'identityText': f'Aside 조사 {today}: 네이버 플레이스/디렉터리의 주소가 NEIS 주소와 일치. '
                                        f'전화 대조·법적 동일성은 사람이 확인할 것.',
                        'summary': quote[:300], 'sourceType': 'directory', 'scope': 'branch',
                        'reviewStatus': 'candidate', 'checkedAt': today,
                        'reviewBy': (date.today() + timedelta(days=180)).isoformat(), 'foundBy': 'aside'})
        rv = [v for v in res.get('reviews') or [] if host_ok(v.get('url', ''))]
        if rv:
            stats['reviews'] += len(rv)
            lines.append(f'- 후기 후보 {len(rv)}건:')
            lines += [f"  - {v.get('date') or '----'} {v['url']} — {v.get('title', '')}" for v in rv]
        others = [o for o in res.get('otherSources') or [] if host_ok(o.get('url', ''))]
        if others:
            stats['other'] += len(others)
            lines.append('- 그 밖의 소스:')
            lines += [f"  - {o['url']} — {(o.get('note') or '')[:120]}" for o in others]
        if res.get('notes'):
            lines.append(f"- 메모: {res['notes'][:400]}")
        lines.append('')
    report = ROOT / 'docs' / 'reports' / f'aside-sources-{today}.md'
    report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    cand = ROOT / 'pipeline' / 'data' / 'grade_source_candidates.json'
    have = json.loads(cand.read_text(encoding='utf-8')) if cand.exists() else []
    keys = {(g['registrationId'], g['gradeUrl']) for g in have}
    added = [g for g in grade_new if (g['registrationId'], g['gradeUrl']) not in keys]
    cand.write_text(json.dumps(have + added, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {**stats, 'gradeCandidatesAdded': len(added), 'report': str(report.relative_to(ROOT))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--ids', help='쉼표로 구분한 학원 id')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--timeout', type=int, default=900, help='학원당 초')
    ap.add_argument('--aggregate', action='store_true', help='조사 없이 결과만 모은다')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.aggregate:
        jobs = targets(set(args.ids.split(',')) if args.ids else None)
        if args.limit:
            jobs = jobs[:args.limit]
        print(f'{len(jobs)}곳 조사 (동시 {args.workers} · 학원당 {args.timeout}초)', flush=True)
        quota = False
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for aid, status in ex.map(lambda j: run_one(j, args.timeout), jobs):
                print(f'  {aid} {status}', flush=True)
                if status == 'quota':
                    quota = True
                    ex.shutdown(cancel_futures=True)
                    break
        if quota:
            print('! Aside 모델 사용량 한도 — 남은 학원은 건너뛰었다. 한도가 풀리면 같은 명령을 다시 돌리면 된 곳은 건너뛴다.')
    print(json.dumps(aggregate(), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
