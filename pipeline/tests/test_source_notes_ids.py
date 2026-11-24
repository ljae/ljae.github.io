"""출처 카드의 학원 id 는 지금 살아 있는 학원 id 여야 한다.

2026-11-24: 생각하는황소 서초 관을 합치자 서초4관(3000040159)이 흡수 등록이
되어 대표 id(3000029897)가 바뀌었다. 손으로 적은 출처 카드가 옛 id 를 들고
있어 앱 시험이 배포 단계에서야 실패했다(데이터 커밋은 이미 끝난 뒤).
흡수된 등록 id 를 가리키면 여기서 먼저 잡는다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_source_notes_point_to_current_academy_ids():
    notes = json.loads((ROOT / 'app/assets/research/source_notes.json').read_text())
    academies = json.loads((ROOT / 'app/assets/data/academies.json').read_text())
    absorbed = {str(rid): a['id'] for a in academies
                for rid in a.get('registrationIds') or [] if str(rid) != a['id']}
    stale = {n['academyId']: absorbed[n['academyId']] for n in notes
             if n['academyId'] in absorbed}
    assert not stale, f'흡수된 등록 id → 현재 id 로 바꿀 것: {stale}'
