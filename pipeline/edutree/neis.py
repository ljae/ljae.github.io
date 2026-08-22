"""NEIS 교육정보 개방 포털 — 학원교습소정보 수집기.

엔드포인트: https://open.neis.go.kr/hub/acaInsTiInfo
키 발급   : https://open.neis.go.kr  (무료, 즉시 발급)

이 모듈이 서비스의 원장(原帳)이다. 여기서 나온 학원만 '검증됨'으로 표시한다.
"""
from __future__ import annotations

import json
import re
import time
from typing import Iterator

import requests

from . import config

ENDPOINT = "https://open.neis.go.kr/hub/acaInsTiInfo"
PAGE_SIZE = 1000
TIMEOUT = 20

# NEIS 응답 필드 → 내부 필드. 응답에 없는 키는 조용히 무시한다.
FIELD_MAP = {
    "ACA_ASNUM": "aca_asnum",              # 학원지정번호 (기본키)
    "ACA_NM": "name",                       # 학원명
    "ADMST_ZONE_NM": "admst_zone_nm",       # 행정구역명
    "REALM_SC_NM": "realm_sc_nm",           # 분야구분명
    "LE_ORD_NM": "le_ord_nm",               # 교습계열명
    "LE_CRSE_LIST_NM": "le_crse_list_nm",   # 교습과정목록명
    "LE_CRSE_NM": "le_crse_nm",             # 교습과정명
    "REG_STTUS_NM": "reg_stttus_nm",        # 등록상태명
    "ESTBL_YMD": "estbl_ymd",               # 개설일자
    "TOFOR_SMTOT": "tofor_smtot",           # 정원합계
    "DTM_RCPTN_ABLTY_NMPR_SMTOT": "dtm_rcptn_ablty_nmpr_smtot",  # 동시수용인원합계
    "THCC_CTNT": "thcc_ctnt",               # 교습비내용
    "FA_RDNMA": "road_address",             # 도로명주소
    "FA_RDNDA": "address_detail",           # 상세주소 — 괄호 안에 법정동이 있다
    "FA_TELNO": "tel",                      # 전화번호
    "BRHS_ACA_YN": "brhs_aca_yn",           # 기숙사학원여부
}


class NeisError(RuntimeError):
    pass


def _request(page: int, atpt_code: str, admst_zone: str | None) -> dict:
    params = {
        "KEY": config.NEIS_API_KEY,
        "Type": "json",
        "pIndex": page,
        "pSize": PAGE_SIZE,
        "ATPT_OFCDC_SC_CODE": atpt_code,
    }
    if admst_zone:
        params["ADMST_ZONE_NM"] = admst_zone
    resp = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _rows(payload: dict) -> tuple[list[dict], int]:
    """NEIS 특유의 중첩 응답에서 (행 목록, 전체 건수)를 뽑는다.

    정상 응답:  {"acaInsTiInfo": [{"head": [...]}, {"row": [...]}]}
    결과 없음:  {"RESULT": {"CODE": "INFO-200", ...}}
    """
    if "RESULT" in payload:
        code = payload["RESULT"].get("CODE", "")
        if code.startswith("INFO-200"):      # 해당 데이터 없음
            return [], 0
        raise NeisError(f"{code}: {payload['RESULT'].get('MESSAGE')}")

    body = payload.get("acaInsTiInfo")
    if not body:
        raise NeisError(f"예상치 못한 응답 형태: {list(payload)[:5]}")

    rows: list[dict] = []
    total = 0
    for block in body:
        if "row" in block:
            rows = block["row"]
        if "head" in block:
            for h in block["head"]:
                if "list_total_count" in h:
                    total = h["list_total_count"]
    return rows, total


def parse_tuition(thcc_ctnt: str | None) -> int | None:
    """교습비 원문에서 월 교습비(원)를 추출한다.

    NEIS 원문은 '월 350,000원', '1개월 350000', '주2회 280,000원' 등 형태가 제각각이다.
    실패하면 None — 투명성 점수에서 '금액 미공개'로 처리된다.
    """
    if not thcc_ctnt:
        return None
    amounts = [int(m.replace(",", "")) for m in re.findall(r"\d{1,3}(?:,\d{3})+|\d{5,8}", thcc_ctnt)]
    plausible = [a for a in amounts if 30_000 <= a <= 3_000_000]
    if not plausible:
        return None
    # 여러 과정이 나열된 경우가 많다. 중앙값이 대표값으로 가장 안정적이다.
    plausible.sort()
    mid = len(plausible) // 2
    if len(plausible) % 2:
        return plausible[mid]
    return (plausible[mid - 1] + plausible[mid]) // 2


# 도로명주소에는 법정동이 없다. 대신 상세주소 끝 괄호에 들어 있다.
#   ", 3층 301호 (개포동, 삼성빌딩)"  →  개포동
# NEIS 4개 구 표본에서 99% 이상 추출된다.
_DONG = re.compile(r"[（(]\s*([가-힣]+\d*동)\s*[,，)）]")


def extract_dong(row: dict) -> str | None:
    """법정동을 뽑는다. 학군 판정의 유일하게 신뢰할 수 있는 근거."""
    blob = f"{row.get('FA_RDNDA') or ''} {row.get('FA_RDNMA') or ''}"
    m = _DONG.search(blob)
    return m.group(1) if m else None


def normalize(row: dict) -> dict:
    out = {internal: row.get(neis) for neis, internal in FIELD_MAP.items()}

    for key in ("tofor_smtot", "dtm_rcptn_ablty_nmpr_smtot"):
        try:
            out[key] = int(out[key]) if out[key] not in (None, "") else None
        except (TypeError, ValueError):
            out[key] = None

    ymd = out.get("estbl_ymd")
    if ymd and re.fullmatch(r"\d{8}", str(ymd)):
        out["estbl_ymd"] = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    else:
        out["estbl_ymd"] = None

    out["dong"] = extract_dong(row)
    out["tuition_monthly_krw"] = parse_tuition(out.get("thcc_ctnt"))
    out["name_normalized"] = normalize_name(out.get("name") or "")
    # 학원지정번호(ACA_ASNUM)를 고유 식별자로 쓴다.
    #
    # 처음에는 정규화한 학원명을 id 로 썼는데, 지점이 여럿인 브랜드가 전부
    # 한 키로 뭉쳤다. '목동 청담어학원'과 '잠실 청담어학원'이 같은 '청담'이
    # 되어 언급과 점수를 공유했고, 표본 1,028건짜리 유령이 두 학군 랭킹에
    # 동시에 1위로 올랐다. 지정번호는 4개 구 9,324건에서 결측 없이 고유하다.
    out["id"] = out.get("aca_asnum") or f"n-{out['name_normalized']}"
    out["is_verified"] = True
    out["data_source"] = "neis"
    return out


_NOISE = re.compile(
    r"(주식회사|㈜|유한회사|학교법인|교습소|보습학원|어학원|학원|교육원|아카데미|캠퍼스|분원|센터)"
)
# 학원명 앞뒤에 붙는 지역/지점 수식어.
_REGION_WORDS = (
    "대치|도곡|개포|목동|신정|반포|잠원|서초|잠실|신천|방이|강남|송파|양천|서울"
)
_PREFIX = re.compile(rf"^(?:{_REGION_WORDS})+")
_SUFFIX = re.compile(rf"(?:{_REGION_WORDS})?(?:점|관|본원|분원|본점)$|(?:{_REGION_WORDS})$")


def normalize_name(name: str) -> str:
    """정규 키. 법인격·업종어·기호만 제거하는 보수적 정규화.

    지역명은 여기서 지우지 않는다. '대치국어논술' 처럼 지역명이 브랜드의
    일부인 경우가 있어, 지우면 서로 다른 학원이 같은 키로 충돌한다.
    """
    s = re.sub(r"[\(\[].*?[\)\]]", "", name)          # 괄호 안 제거
    s = _NOISE.sub("", s)
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", s)
    return s.lower()


def match_keys(name: str) -> set[str]:
    """매칭 후보 키 집합.

    정규 키와 함께 '지역 수식어를 뗀 변형'을 같이 돌려준다. 지점명이 붙은
    NEIS 레코드('청담어학원 잠실점')와 브랜드 시드('청담어학원')를 잇되,
    정규 키는 충돌 없이 보존하기 위한 구조다.
    """
    base = normalize_name(name)
    keys = {base}
    stripped = base
    prev = None
    while prev != stripped:
        prev = stripped
        stripped = _SUFFIX.sub("", _PREFIX.sub("", stripped))
    if len(stripped) >= 2:          # 너무 짧아지면 오매칭 위험 — 버린다
        keys.add(stripped)
    return {k for k in keys if k}


def fetch_region(region: dict) -> list[dict]:
    """한 학군의 학원을 전부 수집한다. 행정구역(구) 단위로 받고 동으로 거른다."""
    if not config.HAS_NEIS:
        raise NeisError("NEIS_API_KEY 가 없습니다. .env 를 확인하세요.")

    collected: list[dict] = []
    page = 1
    while True:
        payload = _request(page, region["atpt_code"], region["sigungu"])
        rows, total = _rows(payload)
        if not rows:
            break
        collected.extend(rows)
        if len(collected) >= total or len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.2)

    # 법정동 정확 일치로 거른다.
    #
    # 처음에는 도로명주소에 동 이름이 들어 있으리라 보고 부분 문자열로 걸렀는데
    # 완전히 틀린 접근이었다. 도로명주소는 애초에 동 기반 주소를 대체한 체계라
    # 동 이름이 없다. 그 결과 '반포'는 서초구 대부분에 헛매칭되고(1,812곳),
    # 송파구는 도로명에 '잠실'이 없어 3곳만 남았다.
    dongs = set(region["dong_list"])
    out, unmatched = [], 0
    for row in collected:
        dong = extract_dong(row)
        if dong is None:
            unmatched += 1
            continue
        if dongs and dong not in dongs:
            continue
        rec = normalize(row)
        rec["region_id"] = region["id"]
        out.append(rec)
    if unmatched:
        print(f"    (법정동 미추출 {unmatched}곳 제외)")
    return out


def fetch_all() -> list[dict]:
    academies: list[dict] = []
    for region in config.regions():
        found = fetch_region(region)
        print(f"  NEIS {region['name_ko']:>4}: {len(found)}곳")
        academies.extend(found)

    cache = config.CACHE_DIR / "neis_academies.json"
    cache.write_text(json.dumps(academies, ensure_ascii=False, indent=2), encoding="utf-8")
    return academies
