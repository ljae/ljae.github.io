"""신고 학원 소수만 추가 수집. 기존 누적 근거는 보존하고 같은 게이트로 재채점한다."""
import re
from . import build, config, coverage, mention_store, naver


def collect(value):
    ids = {v.strip() for v in value.split(',') if v.strip()}
    if not ids or len(ids) > 20 or any(not re.fullmatch(r'\d+', v) for v in ids):
        raise ValueError('등록번호를 1~20개 지정해 주세요')
    academies, mode = build.load_academies(from_cache=True)
    if mode != 'live':
        raise ValueError('실제 교육청 등록부가 필요합니다')
    chosen = [a for a in academies if ids & {a['id'], *map(str, a.get('registration_ids') or [])}]
    found = {v for a in chosen for v in [a['id'], *map(str, a.get('registration_ids') or [])]}
    if ids - found:
        raise ValueError(f'등록부에서 찾지 못한 번호: {sorted(ids-found)}')
    rows = naver.collect_all(chosen, {r['id']:r['name_ko'] for r in config.regions()})
    mention_store.merge(rows)
    coverage.record(chosen, rows)
    print(f'신고 학원 추가 수집: {len(chosen)}곳 · 원자료 {len(rows)}건 (후기 인정 전)')
    return rows
