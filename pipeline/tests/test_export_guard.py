"""빈 결과로 좋은 데이터를 덮지 않는다.

외부 API 가 실패해도 파이프라인은 캐시로 계속 간다 — 그건 맞다. 그런데
**CI 러너에는 캐시가 없다.** 그래서 실패한 회차가 빈 목록을 그대로
내보내 이미 배포된 파일을 지웠고, 실행은 성공으로 끝났다.

실측(2026-08-31 야간): 공동주택 API HTTP 400, 학구도 ReadTimeout.
  apartments.json  795KB → 2바이트('[]')
  schools.json     zoneId 140곳 → 0곳
지도에서 아파트가 통째로 사라졌다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import build  # noqa: E402


def test_빈_목록은_기존_파일을_덮지_않는다(tmp_path):
    p = tmp_path / "apartments.json"
    p.write_text(json.dumps([{"id": "A1"}, {"id": "A2"}]), encoding="utf-8")

    assert build._would_erase(p, []) is True, "빈 결과가 그대로 나가면 안 된다"
    assert build._would_erase(p, [{"id": "A1"}]) is False, "내용이 있으면 쓴다"


def test_처음_만드는_파일은_비어도_쓴다(tmp_path):
    """없던 파일까지 막으면 첫 실행이 아무것도 못 만든다."""
    assert build._would_erase(tmp_path / "new.json", []) is False


def test_딕셔너리_산출물은_대상이_아니다(tmp_path):
    """meta 처럼 비는 일이 정상인 값이 섞여 있다."""
    p = tmp_path / "meta.json"
    p.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert build._would_erase(p, {}) is False


def test_학구를_못_얻으면_지난_값을_물려받는다(tmp_path):
    """학교 목록은 NEIS 로 늘 채워져 행이 남는다 — 그래서 위 검사에
    안 걸린다. 비는 것은 **필드**다."""
    p = tmp_path / "schools.json"
    p.write_text(json.dumps([
        {"id": "S1", "zoneId": "Z1", "zoneName": "강남서초학교군",
         "zonePeers": ["가고", "나고"]},
        {"id": "S2", "zoneId": None},
    ]), encoding="utf-8")

    fresh = [{"id": "S1", "zoneId": None}, {"id": "S2", "zoneId": None}]
    moved = build._carry_zone_fields(p, fresh)

    assert moved == 1
    assert fresh[0]["zoneId"] == "Z1"
    assert fresh[0]["zoneName"] == "강남서초학교군"
    assert fresh[0]["zonePeers"] == ["가고", "나고"]


def test_이번에_학구를_얻었으면_손대지_않는다(tmp_path):
    """성공한 회차의 새 값을 옛 값으로 덮으면 갱신이 영영 안 된다."""
    p = tmp_path / "schools.json"
    p.write_text(json.dumps([{"id": "S1", "zoneId": "옛값"}]), encoding="utf-8")

    fresh = [{"id": "S1", "zoneId": "새값"}]
    assert build._carry_zone_fields(p, fresh) == 0
    assert fresh[0]["zoneId"] == "새값"
