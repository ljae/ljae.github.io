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
        entries = []
        for z in zones:
            schools_in = [s["name"] for s in by_zone.get(z.get("zoneId"), [])]
            entries.append({
                "zoneId": z.get("zoneId"),
                "zoneName": z.get("zoneName"),
                "level": z.get("level"),
                "schools": schools_in,
                # 초등 통학구역은 학교 하나에 구역 하나다 → '배정'이라 말할 수 있다.
                # 중·고 학교군은 여러 학교가 묶여 추첨이므로 '소속'이 정확하다.
                "certain": z.get("level") == "elementary" and len(schools_in) == 1,
            })
        a["zones"] = entries

    print(f"  학구 폴리곤 {len(features)}개 · 아파트 {assigned}/{len(apartments)}단지 배정")
    return {"zones": len(features), "assigned": assigned}


def attach_apartments(schools: list[dict], apartments: list[dict]) -> int:
    """학교 → 배정 아파트 (아파트 → 학교의 역방향).

    학부모는 양방향으로 묻는다. '이 집은 어느 학교냐' 만큼이나
    '이 학교 보내려면 어디 살아야 하냐' 를 많이 찾는다.

    배정 세대수 합계도 같이 낸다. 학교 규모를 가늠하는 실질 지표이고,
    공시 학생수와 달리 '앞으로 들어올 수요' 를 보여준다.
    """
    by_zone: dict[str, list[dict]] = {}
    for a in apartments:
        for z in a.get("zones") or []:
            zid = z.get("zoneId")
            if zid:
                by_zone.setdefault(zid, []).append((a, z))

    hit = 0
    for s in schools:
        zid = s.get("zone_id")
        if not zid:
            continue
        pairs = by_zone.get(zid, [])
        if not pairs:
            continue
        hit += 1
        rows = []
        total = 0
        for a, z in pairs:
            households = a.get("households")
            n = int(float(households)) if households else None
            if n:
                total += n
            rows.append({
                "name": a.get("name") or a.get("kaptName"),
                "dong": a.get("dong"),
                "households": n,
                # 초등 단독 구역이면 이 학교로 확정 배정된다
                "certain": bool(z.get("certain")),
            })
        rows.sort(key=lambda r: -(r["households"] or 0))
        s["apartments"] = rows
        s["apartment_households"] = total or None

    print(f"  학교별 배정 아파트: {hit}곳에 연결")
    return hit
