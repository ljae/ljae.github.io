"""학구도(통학구역) 연계정보 수집 — data.go.kr 표준데이터.

엔드포인트 (403 응답으로 존재 확인됨)
    https://api.data.go.kr/openapi/tn_pubr_public_schul_atndskl_zn_drw_lnkinfo_api

이 API 는 '학구 ID ↔ 학교' 연계표를 준다. 경계 폴리곤 자체는 여기 없고,
학구도안내서비스(schoolzone.emac.kr)의 SHP 파일에 있다. 지도에 구역을
그리려면 SHP 가 필요하고, '어느 학교에 배정되는가'의 연결은 이 API 로 얻는다.

★ 활용신청이 필요하다.
  data.go.kr 키는 서비스별로 승인된다. 신청하지 않은 API 는 키가 멀쩡해도
  403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR 를 돌려준다.
  https://www.data.go.kr/data/15021158/standard.do → 오픈API → 활용신청
"""
from __future__ import annotations

import json
import os
import time

import requests

from . import config

ENDPOINT = ("https://api.data.go.kr/openapi/"
            "tn_pubr_public_schul_atndskl_zn_drw_lnkinfo_api")
# data.go.kr 은 인코딩된 키를 URL 에 그대로 붙여야 한다.
# requests 의 params 로 넘기면 이중 인코딩돼 인증에 실패한다.
KEY = os.getenv("DATA_GO_KR_KEY_ENCODED", "").strip()
HAS_KEY = bool(KEY)
TIMEOUT = 25
PAGE = 500


class NotRegistered(RuntimeError):
    """키는 유효하나 해당 서비스에 활용신청이 안 된 상태."""


def _fetch_page(page: int) -> tuple[list[dict], int]:
    url = (f"{ENDPOINT}?serviceKey={KEY}&pageNo={page}"
           f"&numOfRows={PAGE}&type=json")
    resp = requests.get(url, timeout=TIMEOUT)
    text = resp.text
    if "SERVICE_KEY_IS_NOT_REGISTERED" in text:
        raise NotRegistered(
            "활용신청이 필요합니다: "
            "https://www.data.go.kr/data/15021158/standard.do → 오픈API → 활용신청")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {text[:160]}")
    try:
        body = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"JSON 파싱 실패: {text[:160]}") from exc

    # 표준데이터 응답 봉투는 서비스마다 다르다. 이 API 는 response 래퍼 없이
    # 바로 {header, body} 로 오고, items 안에 item 배열이 한 겹 더 있다.
    inner = body.get("response", body).get("body", body)
    items = inner.get("items") or []
    if isinstance(items, dict):
        items = items.get("item") or []
    if isinstance(items, dict):
        items = [items]
    total = int(inner.get("totalCount") or 0)
    return items, total


def fetch_all(max_pages: int = 200) -> list[dict]:
    if not HAS_KEY:
        print("  data.go.kr 키 없음 — 학구도 수집 건너뜀")
        return []
    out: list[dict] = []
    page = 1
    try:
        while page <= max_pages:
            items, total = _fetch_page(page)
            if not items:
                break
            out.extend(items)
            if len(out) >= total:
                break
            page += 1
            time.sleep(0.15)
    except NotRegistered as exc:
        print(f"  학구도: {exc}")
        return []
    except RuntimeError as exc:
        print(f"  학구도 수집 실패: {exc}")
        return []

    path = config.CACHE_DIR / "school_district.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"  학구도 연계정보 {len(out):,}건")
    return out


def zone_names() -> dict[str, dict]:
    """학구 ID → 이름. 표준데이터 XML 에서 뽑아 둔 것을 읽는다.

    API 는 학구 ID 만 주고 이름을 주지 않는다. 'Z000300008' 보다
    '강남서초학교군' 이 학부모에게 훨씬 쓸모 있다.
    """
    out: dict[str, dict] = {}
    for level in ("elementary", "middle", "high"):
        path = config.DATA_DIR / "zones" / f"{level}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if row.get("zone_id"):
                out[row["zone_id"]] = row
    return out


def attach_to_schools(schools: list[dict]) -> int:
    """학교 목록에 학구 ID 를 붙인다.

    중·고는 여러 학교가 같은 학구 ID 를 공유한다(학교군 추첨 배정).
    초등만 1:1 통학구역이다. 화면에서 '배정'이라고 단정할 수 있는 것은
    초등뿐이고, 중·고는 '이 학교군에 속함'으로 써야 한다.
    """
    path = config.CACHE_DIR / "school_district.json"
    if not path.exists():
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    seoul = [r for r in rows if str(r.get("cddcCode")) == "7010000"]
    by_name = {r.get("schulNm"): r for r in seoul}

    # 학구 ID 하나에 학교가 몇 곳인지 — 추첨 배정 여부의 근거
    per_zone: dict[str, list[str]] = {}
    for r in seoul:
        per_zone.setdefault(r.get("atndsklId"), []).append(r.get("schulNm"))

    names = zone_names()
    hit = 0
    for s in schools:
        r = by_name.get(s.get("name"))
        if not r:
            continue
        zone = r.get("atndsklId")
        peers = [n for n in per_zone.get(zone, []) if n != s.get("name")]
        s["zone_id"] = zone
        s["zone_name"] = (names.get(zone) or {}).get("zone_name")
        s["edu_office"] = r.get("edcSportNm")
        s["zone_peers"] = peers
        # 초등은 1:1 배정, 중·고는 학교군 추첨
        s["assignment"] = "통학구역" if s.get("level") == "elementary" and not peers \
            else ("학교군 추첨" if peers else "통학구역")
        hit += 1
    named = sum(1 for s in schools if s.get("zone_name"))
    print(f"  학구 ID 매칭 {hit}/{len(schools)}곳 (학구명 확보 {named}곳)")
    return hit


def status() -> str:
    """활용신청 상태를 한 줄로 알려준다."""
    if not HAS_KEY:
        return "키 없음"
    try:
        _fetch_page(1)
        return "사용 가능 ✓"
    except NotRegistered:
        return "활용신청 필요 (키는 유효)"
    except RuntimeError as exc:
        return f"오류: {exc}"
