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
    # 교습비 **금액**(PSNBY_THCC_CNTNT)은 읽지 않는다. NEIS 가 금액만 주고
    # **교습시간을 주지 않아** 주2회 26만원과 주5회 26만원이 같은 값으로
    # 선다. 비교가 성립하지 않는 값을 화면에 올리면 그건 정보가 아니라
    # 오해의 원인이다. 시세도 지역·과목마다 달라 금액만으로는 못 읽는다.
    #
    # 다만 같은 필드의 **과정명**은 다른 물건이다 — normalize() 에서
    # 금액을 버리고 이름만 뽑아 course_names 로 남긴다. 아래 참고.
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


# 도로명주소에는 법정동이 없다. 대신 상세주소 끝 괄호에 들어 있다.
#   ", 3층 301호 (개포동, 삼성빌딩)"  →  개포동
# NEIS 4개 구 표본에서 99% 이상 추출된다.
_DONG = re.compile(r"[（(]\s*([가-힣]+\d*동)\s*[,，)）]")


def extract_dong(row: dict) -> str | None:
    """법정동을 뽑는다. 학군 판정의 유일하게 신뢰할 수 있는 근거."""
    blob = f"{row.get('FA_RDNDA') or ''} {row.get('FA_RDNMA') or ''}"
    m = _DONG.search(blob)
    return m.group(1) if m else None


# 교습비 항목에서 **과정명만** 뽑는다. 금액은 버린다.
#
# '교습비는 쓰지 않는다'는 **금액** 이야기다(교습시간이 없어 비교가 성립하지
# 않는다). 같은 필드에 들어 있는 **과정명**은 전혀 다른 물건이다.
# '초등수학'·'중학내신'·'수능독해' 는 학원이 스스로 밝힌 대상 학년과 과정이고,
# 학원명·교습과정목록에는 없는 신호다. 실측 9,324건 중 1,836곳(20%)에 있다.
#
# 형식: `과정명:금액, 과정명:금액` — 과정명 안에 쉼표가 들어가는 경우가 있어
# ('초등수학(주3회, 회60분):100000') 쉼표로 자르면 '회60분)' 같은 조각이 남는다.
# 금액 자리에서 자르고 괄호를 통째로 지운다.
_THCC_AMOUNT = re.compile(r":\s*\d[\d,]*")
_THCC_PAREN = re.compile(r"\([^)]*\)?|\uff08[^\uff09]*\uff09?")


def course_names(text: str | None) -> list[str]:
    """교습비 문자열 → 과정명 목록. 금액·시간 표기는 버린다."""
    if not text or not text.strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for chunk in _THCC_AMOUNT.split(text):
        name = _THCC_PAREN.sub(" ", chunk).strip(" ,\u00b7:/\t\n")
        name = re.sub(r"\s+", " ", name)
        # 1글자는 과정명이 아니고, 30자 넘는 것은 설명문이다.
        if 2 <= len(name) <= 30 and name not in seen:
            seen.add(name)
            out.append(name)
    # 한 학원이 40개 과정을 적어 두기도 한다. 단서로 쓰기에는 앞쪽으로 충분하다.
    return out[:24]


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
    # 과정명만. 금액은 들어오지 않는다.
    out["course_names"] = course_names(row.get("PSNBY_THCC_CNTNT"))
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


# 법인격 표기. 이름 어디에 있든 지운다.
_CORP = re.compile(r"(주식회사|㈜|유한회사|학교법인)")

# 업종어. **끝에서만, 긴 것부터** 뗀다. 과목어가 붙은 복합형을 먼저 둔다.
#
# 예전에는 하나의 정규식으로 어디서든 지웠다. 그래서 '우승희영어학원' 에서
# '어학원' 이 걸려 '우승희영' 이라는 조각이 남았고, 실측 322곳(…영어학원)이
# 전부 이 꼴이라 브랜드 단정(strict)이 통째로 막혔다.
#
# 반대로 짧은 것부터 떼면 '씨앤씨어학원' 이 '씨앤씨어' 가 된다 — '학원' 을
# 먼저 떼고 나면 '어학원' 이 끝에 없기 때문이다. 그래서 **복합형을 목록에
# 명시하고 긴 것부터** 본다.
_TRADE_WORDS = ("영어학원", "국어학원", "수학학원", "과학학원", "논술학원",
                "보습학원", "어학원", "교습소", "교육원", "아카데미",
                "캠퍼스", "분원", "센터", "학원")
# 이름 끝의 지점 표기. 업종어와 번갈아 벗겨야 안쪽까지 닿는다.
_BRANCH_TAIL = re.compile(r"(제?\d+관|\d+호점|본관|신관|별관|본원|분원|점)$")
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
    s = _CORP.sub("", s)
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", s)
    # 끝에서만, 긴 업종어부터. 지점 표기도 함께 벗긴다 —
    # '해빛나인어학원1관학원' 은 학원 → 1관 → 어학원 순으로 벗겨야
    # '해빛나인' 에 닿는다. 업종어만 보면 '…어학원1관' 에서 멈춘다.
    changed = True
    while changed:
        changed = False
        for w in _TRADE_WORDS:
            if s.endswith(w) and len(s) - len(w) >= 2:
                s, changed = s[: -len(w)], True
                break
        if changed:
            continue
        m = _BRANCH_TAIL.search(s)
        if m and m.start() >= 2:
            s, changed = s[: m.start()], True
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


# 이름 앞에 흔히 붙는 지역·관 번호. 브랜드 이름은 그 뒤에 온다.
_LEAD_REGION = re.compile(
    r"^(대치|목동|반포|잠실|서초|강남|송파|양천|개포|도곡|신정|잠원|방이|신천|"
    r"은마|본원|본관)")
_LEAD_NUM = re.compile(r"^\d+관?")


def brand_stems(name: str) -> list[str]:
    """이름 앞의 지역·관 번호를 한 겹씩 벗겨 낸 후보들.

    '대치1관정상어학원' → 대치1관정상 / 1관정상 / 정상
    브랜드는 보통 이 껍질 뒤에 온다.
    """
    stem = normalize_name(name)
    out = [stem]
    for _ in range(4):
        nxt = _LEAD_NUM.sub("", _LEAD_REGION.sub("", stem))
        if nxt == stem or len(nxt) < 2:
            break
        stem = nxt
        out.append(stem)
    return out


# 브랜드 이름 뒤에 흔히 붙는 업종어. 여기까지 떼면 브랜드만 남는다.
_TRADE_TAIL = re.compile(
    r"(어학|영어|수학|국어|논술|과학|독서|교육|학습|스쿨|아카데미)+$")

# 브랜드 뒤에 붙는 지점 표기. '청담어학원 대치브랜치2관' 처럼
# 브랜드와 지점 사이에 지역이 끼기도 한다.
_BRANCH = re.compile(r"(브랜치|캠퍼스|센터|지점|\d*관|\d+호점|점)")


def matches_brand(name: str, brand_key: str, strict: bool = False) -> str | None:
    """NEIS 학원명이 큐레이션 브랜드에 해당하는가.

    확신의 강도를 둘로 나눈다. 이 구분이 필요한 이유가 있다.

      strict — 지역·관 번호·업종어를 떼면 브랜드 이름만 남는다.
               '대치청담어학학원' → 청담. 이때만 '이 학원은 그 브랜드다'
               라고 **단정**하고 큐레이션 단계를 붙인다.

      loose  — 접두로 시작하기는 한다. '폴리매그넷', '폴리박사' 처럼.
               같은 브랜드일 수도, 이름만 겹칠 수도 있다. 단정하지 않고
               '눈여겨볼 만한 곳' 표시만 남겨 수집 대상 선정에 쓴다.

    예전에는 완전일치만 봤다. 그래서 '대치청담어학학원'이 청담어학원과
    이어지지 않았고, 대치 저학년 영어의 대표 학원들이 통째로 수집 대상
    밖에 있었다. 반대로 접두만 보면 '뮤엠영어**폴리**오국어논술'이
    폴리어학원이 된다 — 그래서 접두는 맨 앞에서만 인정한다.
    """
    if len(brand_key) < 2:
        return None
    for stem in brand_stems(name):
        if not stem.startswith(brand_key):
            continue
        if not strict:
            return "loose"
        rest = stem[len(brand_key):]
        if stem == brand_key or _TRADE_TAIL.sub("", stem) == brand_key:
            return "strict"
        # 뒤가 지점 표기뿐이면 같은 브랜드로 본다.
        # 업종어만 지우면 '1관' 의 '관' 이 남아 '해빛나인어학원1관학원' 이
        # strict 가 못 됐다 — 지점 표기(_BRANCH)도 함께 지우고 판정한다.
        if rest and _BRANCH.search(rest) and not _BRANCH.sub(
                "", _TRADE_TAIL.sub("", rest)).strip("0123456789"):
            return "strict"
        if rest and _LEAD_REGION.match(rest) and _BRANCH.search(rest):
            return "strict"
    return None


RAW_CACHE = config.CACHE_DIR / "neis_raw.json"


def _filter_and_normalize(collected: list[dict], region: dict) -> list[dict]:
    """법정동으로 거르고 정규화한다.

    처음에는 도로명주소에 동 이름이 들어 있으리라 보고 부분 문자열로 걸렀는데
    완전히 틀린 접근이었다. 도로명주소는 애초에 동 기반 주소를 대체한 체계라
    동 이름이 없다. 그 결과 '반포'는 서초구 대부분에 헛매칭되고(1,812곳),
    송파구는 도로명에 '잠실'이 없어 3곳만 남았다.
    """
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


def renormalize() -> list[dict]:
    """원본 캐시에서 다시 정규화한다. API 를 부르지 않는다.

    컬럼 매핑이 틀렸던 적이 있다(교습비를 THCC_CTNT 로 읽고 있었는데 실제
    이름은 PSNBY_THCC_CNTNT 였다). 그럴 때 9,324건을 다시 받을 이유가 없다 —
    원본은 그대로고 해석만 바뀌었을 뿐이다.
    """
    if not RAW_CACHE.exists():
        raise NeisError("원본 캐시가 없습니다. 먼저 한 번 수집하세요.")
    raw = json.loads(RAW_CACHE.read_text(encoding="utf-8"))
    academies: list[dict] = []
    for region in config.regions():
        rows = raw.get(region["sigungu"]) or []
        found = _filter_and_normalize(rows, region)
        print(f"  재정규화 {region['name_ko']:>4}: {len(found)}곳 (원본 {len(rows)}건)")
        academies.extend(found)
    (config.CACHE_DIR / "neis_academies.json").write_text(
        json.dumps(academies, ensure_ascii=False, indent=2), encoding="utf-8")
    return academies


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

    # 원본을 그대로 남긴다. 컬럼 매핑을 고칠 때 다시 받지 않아도 되도록.
    raw = {}
    if RAW_CACHE.exists():
        try:
            raw = json.loads(RAW_CACHE.read_text(encoding="utf-8"))
        except ValueError:
            raw = {}
    raw[region["sigungu"]] = collected
    RAW_CACHE.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    return _filter_and_normalize(collected, region)


def fetch_all() -> list[dict]:
    academies: list[dict] = []
    for region in config.regions():
        found = fetch_region(region)
        print(f"  NEIS {region['name_ko']:>4}: {len(found)}곳")
        academies.extend(found)

    cache = config.CACHE_DIR / "neis_academies.json"
    cache.write_text(json.dumps(academies, ensure_ascii=False, indent=2), encoding="utf-8")
    return academies
