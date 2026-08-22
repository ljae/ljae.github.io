"""학교알리미 공시정보 수집.

발급: https://www.schoolinfo.go.kr → OpenAPI (네이버/카카오 인증)

요청 형식 (공식 가이드 + 실측으로 확인)
    https://www.schoolinfo.go.kr/openApi.do
      ?apiKey=인증키
      &apiType=API종류
      &pbanYr=공시연도        (apiType=0 은 불필요)
      &sidoCode=시도코드       ← 행정표준코드. 서울=11 (교육청코드 B10 아님)
      &sggCode=시군구코드      ← 강남 11680 · 양천 11470 · 서초 11650 · 송파 11710
      &schulKndCode=학교급     ← 02 초등 · 03 중학 · 04 고등

★ 확인된 한계 — 졸업생 진로현황(특목고·자사고 진학 실적)은 이 API에 없다.
  API 제공목록은 학사/학생(학생수·교원), 재정/시설/설비, 보건/복지 뿐이다.
  진학 실적은 학교알리미 웹 화면에서 학교별로 조회하거나,
  에듀데이터서비스(EDSS)에 별도 신청·심사를 거쳐야 받을 수 있다.
  또한 최근 3년치만 공시되며 그 이전은 EDSS 영역이다.

  → 진학 실적 기반 학교 랭킹은 이 키만으로는 만들 수 없다.
     대신 이 API로 얻는 지표(학교 규모, 학년별 학생수, 전·출입 등)로
     '학군 지표'를 구성할 수 있다.
"""
from __future__ import annotations

import json
import os
import time

import requests

from . import config

ENDPOINT = "https://www.schoolinfo.go.kr/openApi.do"
API_KEY = os.getenv("SCHOOLINFO_API_KEY", "").strip()
HAS_SCHOOLINFO = bool(API_KEY)
TIMEOUT = 25

# 4개 학군이 속한 자치구의 행정표준코드
SGG_CODES = {
    "daechi": "11680",    # 강남구
    "mokdong": "11470",   # 양천구
    "banpo": "11650",     # 서초구
    "jamsil": "11710",    # 송파구
}
SCHOOL_KIND = {"elementary": "02", "middle": "03", "high": "04"}

# 실측으로 확인한 apiType. 공식 문서에 번호 표가 없어 응답 구조로 판별했다.
API_BASIC = 0        # 학교기본정보 (좌표 포함, pbanYr 불필요)
API_STUDENTS = 10    # 학년별·학급별 학생수


def _get(params: dict) -> dict | None:
    try:
        resp = requests.get(ENDPOINT, params={"apiKey": API_KEY, **params},
                            timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    if body.get("resultCode") != "success":
        return None
    return body


def fetch(api_type: int, region_id: str, level: str,
          year: int | None = None) -> list[dict]:
    sgg = SGG_CODES.get(region_id)
    kind = SCHOOL_KIND.get(level)
    if not (HAS_SCHOOLINFO and sgg and kind):
        return []
    params = {"apiType": api_type, "sidoCode": "11",
              "sggCode": sgg, "schulKndCode": kind}
    if year:
        params["pbanYr"] = year
    body = _get(params)
    return (body or {}).get("list", []) or []


def student_counts(year: int = 2024) -> dict[str, dict]:
    """학교코드 → 학생 규모. 학군 지표의 기초.

    학급당 학생수(과밀)는 학부모가 학군을 볼 때 실제로 따지는 항목이고,
    진학 실적과 달리 공개돼 있다.
    """
    out: dict[str, dict] = {}
    for region_id in SGG_CODES:
        for level in SCHOOL_KIND:
            for row in fetch(API_STUDENTS, region_id, level, year):
                code = row.get("SCHUL_CODE")
                if not code:
                    continue
                total = row.get("STDNT_SUM")
                by_grade = {k: v for k, v in row.items()
                            if k.startswith("STDNT_SUM_")}
                out[str(code)] = {
                    "total_students": int(total) if str(total).isdigit() else None,
                    "by_grade": by_grade,
                    "year": year,
                }
            time.sleep(0.15)
    print(f"  학교알리미 학생수: {len(out)}곳")
    return out


def cache_all(year: int = 2024) -> dict:
    data = {"year": year, "students": student_counts(year)}
    path = config.CACHE_DIR / "schoolinfo.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data
