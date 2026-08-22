"""주소 → 좌표 (네이버 지오코딩).

NEIS 는 도로명주소만 준다. 지도에 학원을 찍으려면 좌표가 필요하고,
좌표는 지오코딩으로만 얻는다.

이 키는 **서버 전용**이다. 지도 SDK 용 키(NAVER_MAP_KEY_ID, 브라우저에
노출됨)와 다르다. 지오코딩은 시크릿까지 필요하므로 앱에 넣으면 안 된다.

발급: NCP 콘솔 → Services → Application Services → Maps → Application 등록
      (Web Dynamic Map + Geocoding 을 함께 선택)

결과는 캐시한다. 주소는 거의 바뀌지 않으므로 한 번 받으면 재사용한다.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from . import config

ENDPOINT = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
CACHE = config.CACHE_DIR / "geocode.json"
TIMEOUT = 15
SLEEP = 0.06

KEY_ID = os.getenv("NAVER_MAP_CLIENT_ID", "").strip()
KEY_SECRET = os.getenv("NAVER_MAP_CLIENT_SECRET", "").strip()
HAS_GEOCODE = bool(KEY_ID and KEY_SECRET)


def _headers() -> dict:
    return {
        "X-NCP-APIGW-API-KEY-ID": KEY_ID,
        "X-NCP-APIGW-API-KEY": KEY_SECRET,
        "Accept": "application/json",
    }


def _load() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def lookup(address: str) -> tuple[float, float] | None:
    try:
        resp = requests.get(ENDPOINT, params={"query": address},
                            headers=_headers(), timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    items = (resp.json() or {}).get("addresses") or []
    if not items:
        return None
    try:
        return float(items[0]["y"]), float(items[0]["x"])   # (위도, 경도)
    except (KeyError, TypeError, ValueError):
        return None


def enrich(academies: list[dict], workers: int = 4) -> int:
    """학원 목록에 lat/lng 를 채운다. 채운 건수를 돌려준다."""
    cache = _load()

    if HAS_GEOCODE:
        todo = [a for a in academies
                if a.get("road_address") and a["road_address"] not in cache]
        if todo:
            print(f"  지오코딩 대상 {len(todo):,}건 (캐시 {len(cache):,}건)")
            lock = threading.Lock()
            done = 0

            def work(a: dict) -> None:
                nonlocal done
                got = lookup(a["road_address"])
                time.sleep(SLEEP)
                with lock:
                    done += 1
                    if got:
                        cache[a["road_address"]] = {"lat": got[0], "lng": got[1]}
                    if done % 500 == 0:
                        print(f"    [{done}/{len(todo)}] 성공 {len(cache):,}")

            with ThreadPoolExecutor(max_workers=workers) as pool:
                for f in as_completed([pool.submit(work, a) for a in todo]):
                    f.result()
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    elif not cache:
        print("  지오코딩 키 없음 — 좌표 없이 진행 (지도는 모식도로 동작)")

    filled = 0
    for a in academies:
        got = cache.get(a.get("road_address") or "")
        if got:
            a["lat"], a["lng"] = got["lat"], got["lng"]
            filled += 1
    return filled
