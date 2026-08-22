"""학구 폴리곤과 아파트/학교를 잇는다.

'이 아파트는 어느 학교군인가' 는 데이터셋에 없는 값이다. 폴리곤 안에
점이 들어 있는지 직접 판정해서 만들어야 한다.

★ 중요 — 중·고는 '배정'이 아니다.
  한 학교군에 학교가 여러 곳이고 추첨으로 배정된다. 그래서 결과를
  '배정 학교'가 아니라 '이 학교군에 속함 (N개교 중 추첨)' 으로 표기한다.
  1:1 배정이 성립하는 초등 통학구역 폴리곤은 아직 확보하지 못했다.
"""
from __future__ import annotations

import json

from . import config


def _in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray casting. 경계 위의 점은 안쪽으로 친다."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _in_polygon(lon: float, lat: float, coords: list) -> bool:
    """첫 링은 외곽, 나머지는 구멍."""
    if not coords or not _in_ring(lon, lat, coords[0]):
        return False
    return not any(_in_ring(lon, lat, hole) for hole in coords[1:])


def load() -> list[dict]:
    path = config.EXPORT_DIR / "zones.geojson"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("features", [])


def locate(lon: float, lat: float, features: list[dict],
           level: str | None = None) -> list[dict]:
    """점이 속한 학구들. 학교급마다 하나씩 나온다."""
    out = []
    for f in features:
        props = f["properties"]
        if level and props.get("level") != level:
            continue
        # 경계상자로 먼저 걸러 낸다. 폴리곤 판정은 비싸다.
        ring = f["geometry"]["coordinates"][0]
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        if not (min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats)):
            continue
        if _in_polygon(lon, lat, f["geometry"]["coordinates"]):
            out.append(props)
    return out


def assign(apartments: list[dict], schools: list[dict]) -> dict:
    """아파트에 학교군을, 학교군에 소속 학교를 붙인다."""
    features = load()
    if not features:
        print("  학구 폴리곤 없음 — 배정 계산 건너뜀")
        return {"zones": 0, "assigned": 0}

    # 학교군 → 그 안의 학교들 (학구 ID 로 잇는다)
    by_zone: dict[str, list[dict]] = {}
    for s in schools:
        zid = s.get("zone_id")
        if zid:
            by_zone.setdefault(zid, []).append(s)

    assigned = 0
    for a in apartments:
        if not (a.get("lat") and a.get("lng")):
            continue
        zones = locate(a["lng"], a["lat"], features)
        if not zones:
            continue
        assigned += 1
        a["zones"] = [{
            "zoneId": z.get("zoneId"),
            "zoneName": z.get("zoneName"),
            "level": z.get("level"),
            "schools": [s["name"] for s in by_zone.get(z.get("zoneId"), [])],
        } for z in zones]

    print(f"  학구 폴리곤 {len(features)}개 · 아파트 {assigned}/{len(apartments)}단지 배정")
    return {"zones": len(features), "assigned": assigned}
