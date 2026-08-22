#!/usr/bin/env python3
"""학구도 SHP → GeoJSON 변환.

    python3 pipeline/zones_to_geojson.py /tmp/shp

학구도안내서비스가 주는 SHP 는 EPSG:5186(Korea 2000 중부원점)이다.
네이버 지도는 WGS84 를 쓰므로 좌표계를 바꿔야 한다.

폴리곤 점이 수천 개라 그대로 앱에 실으면 번들이 감당하지 못한다.
Ramer-Douglas-Peucker 로 단순화한다. 학군 경계를 보여주는 용도라
미터 단위 정밀도는 필요 없다.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pyproj
import shapefile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "assets" / "data"
TRANSFORM = pyproj.Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)

# 4개 학군이 속한 교육지원청. 서울 전체를 실을 이유가 없다.
TARGET_OFFICES = ("강남서초", "강서양천", "강동송파")
SEOUL = "11"


def _perp(pt, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify(points: list, tol: float) -> list:
    """RDP. 재귀 대신 스택으로 돌린다 — 점이 수천 개라 재귀는 한계에 걸린다."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        dmax, idx = 0.0, s
        for i in range(s + 1, e):
            d = _perp(points[i], points[s], points[e])
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    return [p for p, k in zip(points, keep) if k]


def rings(shape) -> list[list]:
    """멀티파트 폴리곤을 링 목록으로 쪼갠다."""
    parts = list(shape.parts) + [len(shape.points)]
    return [shape.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]


# 초등 통학구역은 블록 단위로 작아서 12m 로 줄이면 모양이 뭉개진다.
TOLERANCE = {"elementary": 6.0, "middle": 12.0, "high": 15.0}


def convert(path: Path, level: str, tol: float | None = None) -> dict:
    tol = tol if tol is not None else TOLERANCE.get(level, 12.0)
    reader = shapefile.Reader(str(path), encoding="euc-kr")
    fields = [f[0] for f in reader.fields[1:]]
    features = []
    kept = skipped = 0

    for rec, shape in zip(reader.records(), reader.shapes()):
        attrs = dict(zip(fields, rec))
        if str(attrs.get("SD_CD") or "") != SEOUL:
            skipped += 1
            continue
        office = str(attrs.get("EDU_NM") or "")
        if TARGET_OFFICES and not any(t in office for t in TARGET_OFFICES):
            skipped += 1
            continue

        coords = []
        for ring in rings(shape):
            simple = simplify(ring, tol)
            if len(simple) < 4:
                continue
            lonlat = [list(TRANSFORM.transform(x, y)) for x, y in simple]
            if lonlat[0] != lonlat[-1]:
                lonlat.append(lonlat[0])
            coords.append(lonlat)
        if not coords:
            continue

        kept += 1
        features.append({
            "type": "Feature",
            "properties": {
                "zoneId": attrs.get("HAKGUDO_ID"),
                "zoneName": attrs.get("HAKGUDO_NM"),
                "level": level,
                "eduOffice": office,
            },
            "geometry": {"type": "Polygon", "coordinates": coords},
        })

    print(f"  {level:<7} 전체 {len(reader)}개 → 대상 {kept}개 (제외 {skipped})")
    return {"type": "FeatureCollection", "features": features}


def main(base: str) -> None:
    base_path = Path(base)
    jobs = [("elementary", "elementary"), ("middle", "middle"), ("high", "high")]
    out: dict = {"type": "FeatureCollection", "features": []}
    for folder, level in jobs:
        shp = base_path / folder / "zone.shp"
        if not shp.exists():
            print(f"  {level}: SHP 없음 — 건너뜀")
            continue
        out["features"].extend(convert(shp, level)["features"])

    path = OUT / "zones.geojson"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    pts = sum(len(r) for f in out["features"] for r in f["geometry"]["coordinates"])
    print(f"→ {path.relative_to(ROOT)}  구역 {len(out['features'])}개 · "
          f"점 {pts:,}개 · {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/shp")
