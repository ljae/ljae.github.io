"""졸업생 진로 현황 — 학교알리미 웹 공시에서 읽는다.

OpenAPI 에는 이 항목이 없다(apiType 1~70 전수 확인, 51은 졸업자 수뿐).
웹 공시 화면은 있다. 학교 상세는 POST /ei/ss/Pneiss_b01_s0.do 에
SHL_IDF_CD(uuid) 를 넘기는 구조이고, 이 uuid 는 OpenAPI apiType 0
(학교 기본정보) 응답에 들어 있다 — 두 체계가 여기서 이어진다.

진로 현황 항목 자체는
  POST /ei/pp/Pneipp_b06_s0p.do   (GS_HANGMOK_CD=06, 응답은 EUC-KR)
로 부분 HTML 을 돌려준다.

★ 반드시 천천히. 연속 호출 몇 번에 '서비스 일시 중단 안내'로 차단됐다.
  학교 75곳(중·고)이라 2초 간격이면 3분이 안 걸린다. 서두를 이유가 없다.

서울대 진학률은 여기에도 없다. 학교알리미 고교 공시는 진학 '분류'
(전문대/대학/기타)까지만 준다. 대학별 수치는 공공 공시가 아니므로
data/school_outcomes_extra.yaml 수기 보완으로만 다루고 출처를 붙인다.
"""
from __future__ import annotations

import json
import re
import time

import requests

from . import config, schoolinfo

BASE = "https://www.schoolinfo.go.kr"
CACHE = config.CACHE_DIR / "careers.json"
SLEEP = 2.0
TIMEOUT = 25

# 중학교 진로 분류(공시 표의 열 순서와 무관하게 이름으로 잡는다)
_MIDDLE_CATS = ("일반고", "특성화고", "특수목적고", "자율고", "기타", "진학률")
_HIGH_CATS = ("전문대학", "대학", "국외", "기타", "진학률", "취업")


def _detail_uuid_map() -> dict[str, str]:
    """학교명 → SHL_IDF_CD. OpenAPI 기본정보(apiType 0)에서 얻는다."""
    out: dict[str, str] = {}
    for region_id, sgg in schoolinfo.SGG_CODES.items():
        for level, knd in schoolinfo.SCHOOL_KIND.items():
            if level == "elementary":
                continue            # 초등은 진로 공시가 없다
            rows = schoolinfo.fetch(schoolinfo.API_BASIC, region_id, level) or []
            for r in rows:
                nm, cd = r.get("SCHUL_NM"), r.get("SHL_IDF_CD")
                if nm and cd:
                    out[nm] = cd
            time.sleep(0.3)
    return out


def _fetch_one(name: str, uuid: str, year: str) -> dict | None:
    body = {
        "GS_HANGMOK_CD": "06", "GS_HANGMOK_NO": "13-다",
        "GS_HANGMOK_NM": "졸업생의 진로 현황",
        "GS_BURYU_CD": "JG030", "JG_BURYU_CD": "JG030",
        "JG_YEAR2": year, "JG_YEAR": year,
        "CHOSEN_JG_YEAR": year, "PRE_JG_YEAR": year,
        "HG_NM": name, "SHL_IDF_CD": uuid,
        "GS_TYPE": "Y", "SORT": "BR", "LOAD_TYPE": "single",
    }
    try:
        resp = requests.post(f"{BASE}/ei/pp/Pneipp_b06_s0p.do", data=body,
                             timeout=TIMEOUT)
        html = resp.content.decode("euc-kr", errors="replace")
    except requests.RequestException:
        return None
    if "일시 중단" in html:            # 차단 신호 — 즉시 멈춰야 한다
        raise RuntimeError("학교알리미가 요청을 차단했습니다. 나중에 다시.")
    if "데이터가 없습니다" in html:
        return None
    # 표를 통째로 긁어 숫자 셀을 이름 붙은 열과 짝짓는다.
    text = re.sub(r"<[^>]+>", "|", html)
    cells = [c.strip() for c in text.split("|") if c.strip()]
    pairs: dict[str, float] = {}
    for i, c in enumerate(cells):
        for cat in _MIDDLE_CATS + _HIGH_CATS:
            if c.startswith(cat) and i + 1 < len(cells):
                nxt = cells[i + 1].replace(",", "").rstrip("%명")
                try:
                    pairs.setdefault(cat, float(nxt))
                except ValueError:
                    pass
    return pairs or None


def collect(year: str = "2025") -> dict:
    """중·고 전체의 진로 현황을 캐시에 모은다. 이어받기 가능."""
    cache: dict = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    uuids = _detail_uuid_map()
    todo = [(n, u) for n, u in uuids.items() if n not in cache]
    print(f"  진로 공시 수집 대상 {len(todo)}곳 (캐시 {len(cache)}곳)")
    for name, uuid in todo:
        try:
            got = _fetch_one(name, uuid, year)
        except RuntimeError as exc:
            print(f"    ! {exc}")
            break
        cache[name] = {"year": year, "data": got}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")
        time.sleep(SLEEP)
    return cache


def attach(schools: list[dict]) -> int:
    """학교 레코드에 진로 공시와 수기 보완(외부 집계)을 붙인다."""
    cache: dict = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    try:
        extra = (config.load_yaml("school_outcomes_extra.yaml") or {}) \
            .get("schools") or []
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
