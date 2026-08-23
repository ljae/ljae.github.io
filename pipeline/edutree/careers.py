"""졸업생 진로 현황 — 학교알리미 웹 공시에서 읽는다.

OpenAPI 에는 이 항목이 없다(apiType 1~70 전수 확인, 51은 졸업자 수뿐).
웹 공시에는 있고, 두 체계를 잇는 고리는 OpenAPI apiType 0 이 주는
SHL_IDF_CD(uuid) 다.

★ 요청은 2단계다. 여기서 한참 헤맸다.
  1) POST /ei/pp/Pneipp_b06_s0p.do   → 항목 껍데기 + 지표 폼(goJipyoForm01/02)
  2) POST /ei/ss/pneiss_a03_s0p.do   → 실제 표. 1)이 준 JIPYO_CD/COLUMN 을 그대로 보낸다
  1)만 부르면 자바스크립트 껍데기만 온다.

★ 연도 주의. 진로 현황은 **직전 공시연도**에만 있다. 2026 공시 목록에는
  항목 자체가 없고(45개), 2025 목록에 있다(48개). 최신 연도로 부르면
  '데이터 없음'이 아니라 항목이 아예 없다.

★ 파라미터는 화면의 loadGongSi 인자에서 그대로 가져왔다. 추측하면 틀린다.
  GS_BURYU_CD=JG040, JG_BURYU_CD=JG130, JG_HANGMOK_CD=52, JG_GUBUN=1, JG_CHASU=4

★ 차단. 연속 호출에 '서비스 일시 중단 안내'가 온다. 이 페이지는 본문이
  없어 조용히 '데이터 없음'처럼 보인다 — 실제로 157곳을 그렇게 날렸다.
  그래서 길이(약 3.8KB)와 마커를 함께 본다. 차단이면 즉시 중단한다.

서울대 진학률은 여기에도 없다. 고교 공시는 전문대/대학/국외/취업 비율까지다.
대학별 수치는 공시 항목이 아니므로 data/school_outcomes_extra.yaml 수기
보완으로만 다루고 출처를 반드시 붙인다.
"""
from __future__ import annotations

import json
import re
import time

import requests

from . import config, schoolinfo

BASE = "https://www.schoolinfo.go.kr"
CACHE = config.CACHE_DIR / "careers.json"
STEP1 = f"{BASE}/ei/pp/Pneipp_b06_s0p.do"
STEP2 = f"{BASE}/ei/ss/pneiss_a03_s0p.do"

SLEEP = 6.0          # 2초로도 막혔다. 넉넉히 둔다 — 157곳이면 16분이다.
TIMEOUT = 25
BLOCK_MARK = "일시 중단"
BLOCK_LEN = 4200     # 차단 페이지는 본문이 없어 4KB 안쪽이다

# 화면의 goJipyoForm 에 박혀 있는 지표 목록. (JIPYO_CD, JIPYO_COLUMN, 표시명)
JIPYO_MIDDLE = [
    ("JG1305220", "MI_ERTDS_RAT", "진학률"),
    ("JG1305221", "GNRL_ORD_HS_ERTDS_RAT", "일반고"),
    ("JG1305222", "CHRTR_ORD_HS_ERTDS_RAT", "특성화고"),
    ("JG1305223", "SPCLY_ORD_HS_ERTDS_RAT", "특수목적고"),
    ("JG1305224", "SLCTL_ORD_HS_ERTDS_RAT", "자율고"),
    ("JG1305225", "ETC_RAT", "기타"),
]
JIPYO_HIGH = [
    ("JG1305226", "HG_ERTDS_RAT", "진학률"),
    ("JG1305227", "JNCLL_UNIV_ERTDS_RAT", "전문대학"),
    ("JG1305228", "UNIV_ERTDS_RAT", "대학"),
    ("JG1305229", "OCNTY_ERTDS_RAT", "국외"),
    ("JG1305230", "EMPLO_RAT", "취업"),
    ("JG1305231", "ETC_RAT", "기타"),
]


class Blocked(RuntimeError):
    pass


def _decode(resp: requests.Response) -> str:
    return resp.content.decode("euc-kr", errors="replace")


def _check_block(html: str) -> None:
    if BLOCK_MARK in html or len(html) < BLOCK_LEN:
        raise Blocked("학교알리미가 요청을 막았습니다. 시간을 두고 다시 하세요.")


def uuid_map() -> dict[str, tuple[str, str]]:
    """학교명 → (uuid, level). OpenAPI 기본정보(apiType 0)에서 얻는다."""
    out: dict[str, tuple[str, str]] = {}
    for region_id in schoolinfo.SGG_CODES:
        for level in ("middle", "high"):     # 초등은 진로 공시가 없다
            for r in schoolinfo.fetch(schoolinfo.API_BASIC, region_id, level) or []:
                nm, cd = r.get("SCHUL_NM"), r.get("SHL_IDF_CD")
                if nm and cd:
                    out[nm] = (cd, level)
            time.sleep(0.3)
    return out


def _fetch(name: str, uuid: str, level: str, year: str) -> dict | None:
    course_gb = "3" if level == "middle" else "4"
    jipyo = JIPYO_MIDDLE if level == "middle" else JIPYO_HIGH

    common = {
        "SHL_IDF_CD": uuid, "HG_NM": name,
        "GS_BURYU_CD": "JG040", "GS_HANGMOK_CD": "06",
        "JG_BURYU_CD": "JG130", "JG_HANGMOK_CD": "52",
        "GS_HANGMOK_NO": "13-다", "GS_HANGMOK_NM": "졸업생의 진로 현황",
        "JG_YEAR": year, "JG_CHASU": "4", "SORT": "BR",
        "POP_YN": "", "adminYN": "N", "LOAD_TYPE": "single",
    }
    # 1단계 — 껍데기. 여기서 TRANS_DT(공시 차수·시점)를 받아 2단계에 넘긴다.
    r1 = requests.post(STEP1, data={**common, "JG_GUBUN": "1",
                                    "GS_TYPE": "Y", "PRE_JG_YEAR": year},
                       timeout=TIMEOUT)
    html1 = _decode(r1)
    _check_block(html1)
    m = re.search(r'id="select_trans_dt"[^>]*>([^<]*)', html1)
    trans_dt = (m.group(1).strip().split("\n")[0] if m else f"(4차) {year}년 11월")

    # 2단계 — 실제 표.
    body: list[tuple[str, str]] = [
        *common.items(),
        ("HG_JONGRYU_GB", "03" if level == "middle" else "04"),
        ("HG_COURSE_GB", course_gb),
        ("HIGH_JONGRYU_GB", ""),
        ("TRANS_DT", trans_dt),
    ]
    for cd, col, _ in jipyo:
        body.append(("JIPYO_CD", cd))
        body.append(("JIPYO_COLUMN", col))
    for v in ("1", "2", "3"):
        body.append(("SULRIP_GB", v))

    r2 = requests.post(STEP2, data=body, timeout=TIMEOUT)
    html2 = _decode(r2)
    _check_block(html2)

    # 표에서 이 학교 행의 퍼센트를 뽑는다. 지표 순서는 우리가 보낸 순서다.
    cells = [c.strip() for c in re.sub(r"<[^>]+>", "|", html2).split("|") if c.strip()]
    nums: list[float] = []
    for c in cells:
        t = c.replace("%", "").replace(",", "")
        try:
            nums.append(float(t))
        except ValueError:
            continue
    if len(nums) < len(jipyo):
        return None
    return {label: nums[i] for i, (_, _, label) in enumerate(jipyo)}


def collect(year: str = "2025") -> dict:
    """중·고 전체의 진로 현황을 캐시에 모은다. 차단되면 멈추고 이어받는다."""
    cache: dict = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    # 이전 실행에서 차단 페이지를 '데이터 없음'으로 잘못 저장한 것들은 버린다.
    cache = {k: v for k, v in cache.items() if v.get("data")}

    schools = uuid_map()
    todo = [(n, u, lv) for n, (u, lv) in schools.items() if n not in cache]
    print(f"  진로 공시 수집 대상 {len(todo)}곳 (캐시 {len(cache)}곳, {year} 공시)")
    for i, (name, uuid, level) in enumerate(todo, 1):
        try:
            got = _fetch(name, uuid, level, year)
        except Blocked as exc:
            print(f"    ! {exc} ({i-1}곳까지 저장됨)")
            break
        except requests.RequestException as exc:
            print(f"    ? {name}: {exc}")
            continue
        if got:
            cache[name] = {"year": year, "level": level, "data": got}
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")
        if i % 20 == 0:
            print(f"    [{i}/{len(todo)}] 확보 {len(cache)}곳")
        time.sleep(SLEEP)
    print(f"  진로 공시 확보 {len(cache)}곳")
    return cache


def attach(schools: list[dict]) -> int:
    """학교 레코드에 진로 공시와 수기 보완(외부 집계)을 붙인다."""
    cache: dict = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    try:
        extra = (config.load_yaml("school_outcomes_extra.yaml") or {}).get("schools") or []
    except FileNotFoundError:
        extra = []
    extra_by_name = {e["name"]: e for e in extra if e.get("name")}

    n = 0
    for s in schools:
        hit = cache.get(s["name"])
        if hit and hit.get("data"):
            s["careers"] = {"year": hit["year"], **hit["data"],
                            "source": "학교알리미 공시"}
            n += 1
        ex = extra_by_name.get(s["name"])
        if ex:
            # 수기 보완은 공시와 절대 섞지 않는다. 출처가 다른 숫자다.
            s["outcomes_extra"] = {k: v for k, v in ex.items() if k != "name"}
    if n:
        print(f"  진로 공시 연결: {n}곳")
    return n
