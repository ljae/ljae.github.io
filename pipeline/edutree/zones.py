"""학구 폴리곤과 아파트/학교를 잇는다.

'이 아파트는 어느 학교군인가' 는 데이터셋에 없는 값이다. 폴리곤 안에
점이 들어 있는지 직접 판정해서 만들어야 한다.

★ 중요 — 중·고는 '배정'이 아니다.
  한 학교군에 학교가 여러 곳이고 추첨으로 배정된다. 그래서 결과를
  '배정 학교'가 아니라 '이 학교군에 속함 (N개교 중 추첨)' 으로 표기한다.
  1:1 배정이 성립하는 초등 통학구역 폴리곤은 아직 확보하지 못했다.
"""
from __future__ import annotations

import math

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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def _likely(apartment: dict, schools_in: list[dict]) -> list[dict]:
    """중·고 학교군 안에서 배정 가능성이 높은 순으로 세운다.

    서울 중학교는 학교군 안 추첨이고 고등학교도 단계별 추첨이라 '어디로
    간다'고 말할 수 없다. 하지만 완전한 제비뽑기도 아니다. 두 경우 모두
    **통학 편의(근거리)** 가 배정에 반영되므로, 같은 학교군이라도 집에서
    가까운 학교로 갈 확률이 눈에 띄게 높다.

    학부모가 실제로 아는 것도 그 감각이다. '추첨이지만 보통 저기 간다'.
    그걸 숨기면 화면이 현실보다 덜 알려 주는 셈이고, 반대로 단정하면
    거짓이 된다. 그래서 **거리순과 거리값을 그대로** 보여주고, 확률로
    환산하지는 않는다. 실제 배정 결과 데이터가 없는 상태에서 퍼센트를
    붙이면 근거 없는 숫자가 되기 때문이다.
    """
    lat, lng = apartment.get("lat"), apartment.get("lng")
    if not (lat and lng):
        return []
    rows = []
    for s in schools_in:
        if not (s.get("lat") and s.get("lng")):
            continue
        rows.append({
            "name": s["name"],
            "km": round(_haversine_km(lat, lng, s["lat"], s["lng"]), 2),
            # 남고·여고를 안 밝히면 목록이 거짓말이 된다. 아들만 있는
            # 집에 '1순위 숙명여고' 라고 적어 놓는 셈이다.
            "coed": s.get("coed"),
        })
    rows.sort(key=lambda r: r["km"])
    return rows


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
            rows_in = by_zone.get(z.get("zoneId"), [])
            schools_in = [s["name"] for s in rows_in]
            nearby = _likely(a, rows_in) if z.get("level") != "elementary" else []
            entries.append({
                "zoneId": z.get("zoneId"),
                "zoneName": z.get("zoneName"),
                "level": z.get("level"),
                "schools": schools_in,
                # 추첨이지만 근거리가 반영된다 — 가까운 순으로만 알려 준다.
                "nearby": nearby[:5],
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
