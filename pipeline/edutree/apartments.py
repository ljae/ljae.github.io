"""공동주택(아파트) 수집 — 배정 아파트 기능의 재료.

'이 아파트는 어느 학교 배정인가'는 학부모가 가장 많이 검색하는 질문이고,
학구도 폴리곤 + 아파트 좌표로 내부 판정을 돌려야 답할 수 있다.

두 서비스를 쓴다 (각각 data.go.kr 활용신청 대상)
  AptListService3       법정동별 단지 목록 → kaptCode 를 얻는다
  AptBasisInfoServiceV4 kaptCode 로 단지 상세 (세대수·동수·주소·준공)

★ 현재 상태: BasisInfo 는 승인됨, List 는 미승인.
  목록 API 없이는 단지를 나열할 방법이 없어(상세는 kaptCode 를 이미 알아야
  한다) 전체 수집이 막힌다.
  https://www.data.go.kr/data/15057332/openapi.do → 활용신청
"""
from __future__ import annotations

import json
import os
import time

import requests

from . import config

BASE = "https://apis.data.go.kr/1613000"
LIST_OP = f"{BASE}/AptListService3/getLegaldongAptList3"
INFO_OP = f"{BASE}/AptBasisInfoServiceV4/getAphusBassInfoV4"

# 인코딩된 키를 URL 에 그대로 붙인다. params 로 넘기면 이중 인코딩된다.
KEY = os.getenv("DATA_GO_KR_KEY_ENCODED", "").strip()
HAS_KEY = bool(KEY)
TIMEOUT = 25

# 4개 학군의 법정동 코드.
# 잠실동(1171010100)은 API 응답으로 검증했다. 나머지는 목록 API 승인 후
# 실제 응답으로 확인이 필요하다 — 틀리면 그 동만 0건으로 나온다.
BJD_CODES = {
    "daechi": {"대치동": "1168010600", "도곡동": "1168011800", "개포동": "1168010300"},
    "mokdong": {"목동": "1147010100", "신정동": "1147010200"},
    "banpo": {"반포동": "1165010700", "잠원동": "1165010800", "서초동": "1165010600"},
    "jamsil": {"잠실동": "1171010100", "신천동": "1171010200", "방이동": "1171010300"},
}


class NotRegistered(RuntimeError):
    pass


def _get(url: str, retries: int = 2) -> dict:
    # data.go.kr 은 간헐적으로 연결이 끊긴다. 단건 실패로 수집 전체가
    # 죽지 않도록 여기서 재시도하고, 끝내 안 되면 RuntimeError 로 좁힌다.
    last = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            break
        except requests.RequestException as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"연결 실패: {last}")
    text = resp.text
    if "SERVICE_KEY_IS_NOT_REGISTERED" in text:
        raise NotRegistered(
            "활용신청 필요: https://www.data.go.kr/data/15057332/openapi.do")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {text[:140]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise RuntimeError(f"JSON 파싱 실패: {text[:140]}") from exc


def _items(body: dict) -> list[dict]:
    """응답에서 레코드 목록을 꺼낸다.

    같은 기관의 API 인데도 봉투가 다르다.
      목록(AptListService3)      → response.body.items = [ {...} ]
      상세(AptBasisInfoServiceV4) → response.body.item  = {...}   (단수!)
    이 차이 때문에 상세가 363건 전부 조용히 빈 결과로 처리됐다.
    """
    inner = body.get("response", body).get("body", {})
    items = inner.get("items")
    if items is None:
        items = inner.get("item")      # 단수형 봉투
    if items is None:
        return []
    if isinstance(items, dict):
        inner_item = items.get("item")
        items = inner_item if inner_item is not None else items
    if isinstance(items, dict):
        return [items]
    return items if isinstance(items, list) else [items]


def list_by_dong(bjd_code: str, max_pages: int = 20) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        body = _get(f"{LIST_OP}?serviceKey={KEY}&bjdCode={bjd_code}"
                    f"&pageNo={page}&numOfRows=100&_type=json")
        items = _items(body)
        if not items:
            break
        out.extend(items)
        if len(items) < 100:
            break
        time.sleep(0.12)
    return out


def detail(kapt_code: str) -> dict | None:
    try:
        body = _get(f"{INFO_OP}?serviceKey={KEY}&kaptCode={kapt_code}&_type=json")
    except Exception:                       # noqa: BLE001 — 단건 실패는 넘어간다
        return None
    items = _items(body)
    return items[0] if items else None


def fetch_all() -> list[dict]:
    """4개 학군의 아파트 단지를 모은다."""
    if not HAS_KEY:
        print("  data.go.kr 키 없음 — 아파트 수집 건너뜀")
        return []

    out: list[dict] = []
    try:
        for region_id, dongs in BJD_CODES.items():
            for dong, code in dongs.items():
                rows = list_by_dong(code)
                for r in rows:
                    r["region_id"] = region_id
                    r["dong"] = dong
                    r["name"] = r.get("kaptName")
                out.extend(rows)
                print(f"    {dong}: {len(rows)}단지")
                time.sleep(0.1)
    except NotRegistered as exc:
        print(f"  아파트 목록: {exc}")
        return []
    except RuntimeError as exc:
        print(f"  아파트 목록 실패: {exc}")
        return []

    # 목록을 먼저 저장한다. 상세 수집이 중간에 끊겨도 목록은 남아야 한다.
    path = config.CACHE_DIR / "apartments.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    # 상세로 세대수·동수·주소를 채운다.
    filled = 0
    for i, a in enumerate(out, 1):
        d = detail(a.get("kaptCode") or "")
        if d:
            filled += 1
            a.update({
                "name": d.get("kaptName"),
                "households": d.get("kaptdaCnt"),
                "buildings": d.get("kaptDongCnt"),
                "address": d.get("doroJuso") or d.get("kaptAddr"),
                "used_date": d.get("kaptUsedate"),
            })
        if i % 100 == 0:
            print(f"    상세 [{i}/{len(out)}] 성공 {filled}")
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.08)

    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"  아파트 {len(out):,}단지 (상세 {filled}건)")
    return out


def status() -> str:
    if not HAS_KEY:
        return "키 없음"
    try:
        _get(f"{LIST_OP}?serviceKey={KEY}&bjdCode=1171010100&pageNo=1&numOfRows=1&_type=json")
        return "사용 가능 ✓"
    except NotRegistered:
        return "단지목록 활용신청 필요 (상세조회는 승인됨)"
    except RuntimeError as exc:
        return f"오류: {str(exc)[:50]}"
