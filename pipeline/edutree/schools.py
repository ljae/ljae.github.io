"""학교 수집 — NEIS 학교기본정보.

학군지도는 학원이 아니라 학교의 이야기다. 어느 학교에 배정되느냐가 곧
학군이고, 학부모가 집을 고를 때 보는 것도 그것이다.

엔드포인트: https://open.neis.go.kr/hub/schoolInfo
학원 수집과 같은 NEIS 키를 쓴다. 별도 발급이 필요 없다.

주의: 이 모듈은 학교를 **줄 세우지 않는다.** 진학 실적 기반 랭킹은
학교알리미 공시 자료가 있어야 하고, 그건 별도 키가 필요하다.
여기서는 위치와 기본 정보만 모은다.
"""
from __future__ import annotations

import json
import re
import time

import requests

from . import config

ENDPOINT = "https://open.neis.go.kr/hub/schoolInfo"
PAGE_SIZE = 1000
TIMEOUT = 20

# 학원 쪽과 같은 이유로 법정동은 상세주소 괄호 안에서 뽑는다.
_DONG = re.compile(r"[（(]\s*([가-힣]+\d*동)\s*[,，)）]")

LEVELS = {
    "초등학교": "elementary",
    "중학교": "middle",
    "고등학교": "high",
}


def extract_dong(row: dict) -> str | None:
    blob = f"{row.get('ORG_RDNDA') or ''} {row.get('ORG_RDNMA') or ''}"
    m = _DONG.search(blob)
    return m.group(1) if m else None


def _request(page: int, atpt: str) -> dict:
    resp = requests.get(ENDPOINT, params={
        "KEY": config.NEIS_API_KEY, "Type": "json",
        "pIndex": page, "pSize": PAGE_SIZE,
        "ATPT_OFCDC_SC_CODE": atpt,
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _rows(payload: dict) -> tuple[list[dict], int]:
    if "RESULT" in payload:
        return [], 0
    body = payload.get("schoolInfo") or []
    rows, total = [], 0
    for block in body:
        if "row" in block:
            rows = block["row"]
        if "head" in block:
            for h in block["head"]:
                if "list_total_count" in h:
                    total = h["list_total_count"]
    return rows, total


def _cached(cache, why: str) -> list[dict]:
    """캐시로 물러선다. 없으면 빈 목록."""
    if cache.exists():
        try:
            rows = json.loads(cache.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            rows = []
        if rows:
            print(f"  학교 {why} — 캐시 {len(rows):,}곳으로 진행")
            return rows
    print(f"  학교 {why} · 캐시도 없음 — 건너뜀")
    return []


def fetch_all() -> list[dict]:
    """4개 학군에 속한 학교만 남긴다."""
    cache = config.CACHE_DIR / "schools.json"

    # ★ 키가 없어도 캐시가 있으면 그것으로 간다.
    #
    #   네트워크 **실패** 에는 캐시로 물러서면서 키 **없음** 에는 빈 목록을
    #   돌려주고 있었다. 그 차이 때문에 키 없는 환경에서 `--from-cache` 로
    #   산식을 실험하면(문서가 권하는 사용법이다) schools.json 이 0KB 로
    #   덮어써져 학교·아파트 배정이 통째로 사라졌다.
    #
    #   두 경우 모두 '지금 새로 못 가져온다' 는 같은 상황이다. 학교는
    #   하루 이틀 사이에 새로 생기지 않는다 — schooldistrict·schools 에서
    #   이미 두 번 겪은 함정의 세 번째 갈래다.
    if not config.HAS_NEIS:
        return _cached(cache, "수집 건너뜀(NEIS 키 없음)")

    regions = config.regions()
    dong_to_region = {d: r["id"] for r in regions for d in r["dong_list"]}

    collected: list[dict] = []
    page = 1
    try:
        while True:
            payload = _request(page, "B10")
            rows, total = _rows(payload)
            if not rows:
                break
            collected.extend(rows)
            if len(collected) >= total or len(rows) < PAGE_SIZE:
                break
            page += 1
            time.sleep(0.2)
    except requests.RequestException as exc:
        # ★ 네트워크 오류로 실행 전체를 잃지 않는다. 여기까지 오면 NEIS
        #   학원·언급 분석·채점이 이미 다 끝난 상태다. 학교 목록은 캐시가
        #   있고 하루 이틀 묵어도 학교가 새로 생기지 않는다.
        #   (같은 함정을 schooldistrict 에서 이미 한 번 겪었다)
        return _cached(cache, f"수집 실패({type(exc).__name__})")

    out: list[dict] = []
    for row in collected:
        dong = extract_dong(row)
        region_id = dong_to_region.get(dong or "")
        if not region_id:
            continue
        level = LEVELS.get(row.get("SCHUL_KND_SC_NM") or "")
        if not level:
            continue
        out.append({
            "id": row.get("SD_SCHUL_CODE"),
            "name": row.get("SCHUL_NM"),
            "level": level,
            "level_label": row.get("SCHUL_KND_SC_NM"),
            "region_id": region_id,
            "dong": dong,
            "foundation": row.get("FOND_SC_NM"),        # 공립 / 사립
            "coed": row.get("COEDU_SC_NM"),             # 남여공학 / 남 / 여
            "high_kind": row.get("HS_SC_NM"),           # 일반고 / 특목고 …
            "road_address": row.get("ORG_RDNMA"),
            "tel": row.get("ORG_TELNO"),
            "homepage": row.get("HMPG_ADRES"),
        })

    print(f"  학교 {len(out)}곳 (서울 전체 {len(collected)}곳 중 4개 학군)")
    for r in regions:
        n = sum(1 for s in out if s["region_id"] == r["id"])
        by = {}
        for s in out:
            if s["region_id"] == r["id"]:
                by[s["level_label"]] = by.get(s["level_label"], 0) + 1
        print(f"    {r['name_ko']:>4}: {n:>3}곳  {by}")

    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
