"""학교 산출물의 물려받기 — 학구와 배정 아파트는 다른 출처다 (2026-09-07).

'학교별로 배정 아파트가 안 보인다' 는 신고. `schools.json` 140곳 전부
`apartments: []` 였다. `_carry_zone_fields` 가 "이번에 zoneId 를 하나라도
얻었으면 물려받지 않는다" 였는데, 학구(학구도 API)를 얻은 회차에 아파트
(공동주택 API + 지오코딩 캐시)만 비면 그대로 빈 채 나갔다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import build                                   # noqa: E402


def _prev(tmp_path: Path) -> Path:
    path = tmp_path / "schools.json"
    path.write_text(json.dumps([
        {"id": "S1", "zoneId": "Z1", "zoneName": "강남서초1", "assignment": "추첨",
         "apartments": [{"id": "A1", "name": "래미안"}], "apartmentHouseholds": 1200},
        {"id": "S2", "zoneId": None, "apartments": [], "apartmentHouseholds": None},
    ]), encoding="utf-8")
    return path


def test_학구는_얻고_아파트만_비면_아파트만_물려받는다(tmp_path):
    path = _prev(tmp_path)
    rows = [{"id": "S1", "zoneId": "Z1-new", "zoneName": "새 학구", "apartments": [],
             "apartmentHouseholds": None},
            {"id": "S2", "zoneId": "Z2", "apartments": [], "apartmentHouseholds": None}]
    moved = build._carry_zone_fields(path, rows)
    assert moved == 1
    # 이번에 얻은 학구는 이번 값이 이긴다
    assert rows[0]["zoneId"] == "Z1-new" and rows[0]["zoneName"] == "새 학구"
    # 아파트는 지난 파일에서 온다
    assert rows[0]["apartments"] == [{"id": "A1", "name": "래미안"}]
    assert rows[0]["apartmentHouseholds"] == 1200
    # 지난 파일에도 없던 학교는 그대로 빈다 — 없는 것을 만들지 않는다
    assert rows[1]["apartments"] == []


def test_학구를_하나도_못_얻으면_학구만_물려받고_이번_아파트는_지킨다(tmp_path):
    path = _prev(tmp_path)
    rows = [{"id": "S1", "zoneId": None, "apartments": [{"id": "A9"}],
             "apartmentHouseholds": 50}]
    moved = build._carry_zone_fields(path, rows)
    assert moved == 1
    assert rows[0]["zoneId"] == "Z1" and rows[0]["assignment"] == "추첨"
    assert rows[0]["apartments"] == [{"id": "A9"}]          # 이번 값이 이긴다


def test_둘_다_얻었으면_아무것도_물려받지_않는다(tmp_path):
    path = _prev(tmp_path)
    rows = [{"id": "S1", "zoneId": "Z1", "apartments": [{"id": "A9"}]}]
    assert build._carry_zone_fields(path, rows) == 0
    assert rows[0]["apartments"] == [{"id": "A9"}]
