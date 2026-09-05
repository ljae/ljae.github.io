"""네이버 검색 오픈 API 수집기 — 카페글 · 블로그 · 지식iN.

키 발급: https://developers.naver.com/apps  (검색 API 선택, 무료)
한도   : 앱당 일 25,000 호출. display 최대 100, start 최대 1000.

★ 이 모듈은 API가 돌려주는 '스니펫'만 저장한다. 게시물 본문을 통째로
  가져오거나 재배포하지 않는다. 원문은 링크로만 제공한다.
"""
from __future__ import annotations

import hashlib
import html
import threading
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

import requests

from . import config

# ── 두 가지 호출 방식 ──────────────────────────────────────────────
# 네이버가 검색 API를 개발자센터에서 NAVER API Hub 로 옮기는 중이다.
# 두 콘솔이 주는 자격 증명 이름은 똑같이 'Client ID / Client Secret' 인데
# 도메인·경로·헤더가 전부 달라서, 도메인만 바꿔서는 동작하지 않는다.
#
# 어느 콘솔에서 키를 받았든 그대로 쓰게 하려고 양쪽을 다 구현하고
# 실제로 통하는 쪽을 첫 호출에서 자동으로 고른다(NAVER_API_MODE=auto).
MODES = {
    "hub": {
        "label": "NAVER API Hub (console.ncloud.com)",
        "base": "https://naverapihub.apigw.ntruss.com/search/v1",
        "suffix": "",
        "header_id": "X-NCP-APIGW-API-KEY-ID",
        "header_secret": "X-NCP-APIGW-API-KEY",
    },
    "legacy": {
        "label": "개발자센터 (developers.naver.com)",
        "base": "https://openapi.naver.com/v1/search",
        "suffix": ".json",
        "header_id": "X-Naver-Client-Id",
        "header_secret": "X-Naver-Client-Secret",
    },
}
# 자동 탐지 순서. 신규 발급은 Hub 이므로 Hub 를 먼저 본다.
MODE_ORDER = ("hub", "legacy")

SOURCES = {
    "naver_cafe": "cafearticle",
    "naver_blog": "blog",
    "naver_kin": "kin",
}
DISPLAY = 100
MAX_START = 1000
TIMEOUT = 15
SLEEP = 0.12          # 초당 ~8회. 공식 한도보다 넉넉히 낮게 유지한다.

_resolved_mode: str | None = None
# 애플리케이션에서 활성화되지 않은 소스. 한 번 확인하면 이후 호출을 건너뛴다.
# (지식iN 처럼 콘솔에서 따로 켜야 하는 API가 있다. 400곳 × 5질의를 전부
#  실패시키면 한도만 태우고 로그도 못 읽게 된다.)
_disabled_sources: set[str] = set()

_TAG = re.compile(r"<[^>]+>")


class NaverError(RuntimeError):
    pass


def _headers(mode: str) -> dict:
    if not config.HAS_NAVER:
        raise NaverError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 없습니다.")
    spec = MODES[mode]
    return {
        spec["header_id"]: config.NAVER_CLIENT_ID,
        spec["header_secret"]: config.NAVER_CLIENT_SECRET,
    }


def _url(mode: str, service: str) -> str:
    spec = MODES[mode]
    return f"{spec['base']}/{service}{spec['suffix']}"


def probe(mode: str) -> tuple[bool, str]:
    """해당 모드로 실제 호출이 되는지 한 번 찔러본다."""
    try:
        resp = requests.get(
            _url(mode, "blog"),
            params={"query": "학원", "display": 1},
            headers=_headers(mode),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, f"연결 실패: {exc}"
    if resp.status_code == 200:
        return True, "정상"
    return False, f"HTTP {resp.status_code}: {resp.text[:160]}"


def resolve_mode(force: bool = False) -> str:
    """쓸 수 있는 호출 방식을 확정한다. 결과는 프로세스 내에서 재사용한다."""
    global _resolved_mode
    if _resolved_mode and not force:
        return _resolved_mode

    if config.NAVER_API_MODE in MODES:
        _resolved_mode = config.NAVER_API_MODE
        print(f"  네이버 API 모드(지정): {MODES[_resolved_mode]['label']}")
        return _resolved_mode

    errors = []
    for mode in MODE_ORDER:
        ok, detail = probe(mode)
        if ok:
            _resolved_mode = mode
            print(f"  네이버 API 모드(자동 감지): {MODES[mode]['label']}")
            return mode
        errors.append(f"    - {MODES[mode]['label']}: {detail}")

    raise NaverError(
        "네이버 검색 API 자격 증명으로 어느 방식도 호출되지 않았습니다.\n"
        + "\n".join(errors)
        + "\n  키를 다시 확인하거나 NAVER_API_MODE=hub|legacy 로 직접 지정하세요."
    )


def clean(text: str | None) -> str:
    """<b> 강조 태그와 HTML 엔티티를 제거한다."""
    if not text:
        return ""
    return html.unescape(_TAG.sub("", text)).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _parse_date(item: dict) -> str | None:
    """블로그는 postdate(YYYYMMDD)를 준다.

    카페글 검색 API는 날짜 필드를 주지 않는다. 없는 값을 수집일로 채우면
    모든 카페글이 '오늘 글'이 되어 최신성 가중이 망가지므로 None으로 둔다.
    점수 계산에서는 중립 가중치를 적용한다.
    """
    raw = item.get("postdate")
    if raw and re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return None


def _author_hash(item: dict) -> str | None:
    """작성자 식별용 해시. 원본 ID는 저장하지 않는다(개인정보 최소수집)."""
    for key in ("bloggerlink", "bloggername", "cafename"):
        if item.get(key):
            return _hash(str(item[key]))
    return None


def search(source: str, query: str, max_results: int = 300) -> list[dict]:
    """한 소스에서 질의어 하나를 페이지네이션하며 수집한다."""
    if source in _disabled_sources:
        return []

    mode = resolve_mode()
    endpoint = SOURCES[source]
    out: list[dict] = []
    start = 1
    while start <= MAX_START and len(out) < max_results:
        params = {
            "query": query,
            "display": min(DISPLAY, max_results - len(out)),
            "start": start,
            "sort": "date" if source == "naver_blog" else "sim",
        }
        resp = requests.get(_url(mode, endpoint), params=params,
                            headers=_headers(mode), timeout=TIMEOUT)
        if resp.status_code == 429:
            time.sleep(2.0)
            continue
        if resp.status_code != 200:
            body = resp.text[:200]
            if resp.status_code in (401, 403) and "활성화" in body:
                _disabled_sources.add(source)
                print(f"    ! {source} 는 이 애플리케이션에서 활성화되어 있지 않습니다 "
                      f"— 이번 실행에서 제외합니다.")
                print(f"      콘솔에서 해당 API를 추가하면 다음 수집부터 반영됩니다.")
                return out
            raise NaverError(f"{source} {resp.status_code}: {body}")

        items = resp.json().get("items", [])
        if not items:
            break
        for item in items:
            link = item.get("link") or ""
            if not link:
                continue
            out.append({
                "source": source,
                "source_url": link,
                "url_hash": _hash(link),
                "author_hash": _author_hash(item),
                "title": clean(item.get("title")),
                "snippet": clean(item.get("description")),
                "posted_at": _parse_date(item),
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })
        start += len(items)
        time.sleep(SLEEP)
    return out


# ── 지역(로컬) 검색 ──────────────────────────────────────────────
#
# 학원의 **공식 링크와 전화번호**를 얻는 유일한 조회 경로다. NEIS 는
# 홈페이지를 주지 않고, 이름으로 웹을 검색해 맞히는 것은 추측이라
# 하지 않기로 했다(`official.py` 의 'URL 을 추측하지 않는다').
#
# 지역검색은 다르다 — 상호와 함께 **주소**를 돌려준다. 우리가 아는
# 도로명주소와 대조해 **맞을 때만** 쓴다. 그건 추측이 아니라 조회다.
# 같은 검색 API 라 새 키가 필요 없다.
# 부번('418-3')은 남기고 층·호는 버려야 한다. '-' 를 지우면 '418-3' 과
# '418 3층' 이 구별되지 않으므로 '-' 를 남긴 채 자른다.
_ADDR_NOISE = re.compile(r"[^0-9가-힣\-]")
_ADDR_KEY = re.compile(r"(서울\s*\S+구\s*\S+(?:로|길)\s*\d+(?:-\d+)?)")


def addr_key(addr: str | None) -> str | None:
    """도로명주소 비교 키. **건물번호까지만** 본다 — 층·호는 표기가 제각각이라
    '서울특별시 강남구 도곡로 418' 과 '서울 강남구 도곡로 418 3층' 이 같은
    곳으로 읽혀야 한다."""
    if not addr:
        return None
    s = _ADDR_NOISE.sub(" ", str(addr)).strip()
    s = re.sub(r"^서울특별시", "서울", s)
    m = _ADDR_KEY.match(s)
    return re.sub(r"\s+", "", m.group(1)) if m else None


# 교육 업종. 지역검색 category 는 '어학교육>영어교육' 처럼 계층으로 온다.
_EDU_CATEGORY = ("교육", "학원", "교습", "어학", "학문", "입시", "유치원", "논술")

_local_disabled = False


def local_lookup(name: str, road_address: str | None) -> dict | None:
    """상호+주소로 한 곳을 찾는다. **주소가 안 맞으면 None.**

    돌려주는 것: {'title', 'link', 'telephone', 'road_address', 'category'}
    """
    if not config.HAS_NAVER or not name:
        return None
    want = addr_key(road_address)
    if not want:                      # 대조할 것이 없으면 쓰지 않는다
        return None
    global _local_disabled
    if _local_disabled:
        return None
    mode = resolve_mode()
    params = {"query": f"{name} {road_address}".strip(), "display": 5}
    try:
        resp = requests.get(_url(mode, "local"), params=params,
                            headers=_headers(mode), timeout=TIMEOUT)
        if resp.status_code in (401, 403):
            # 콘솔에서 '지역' 검색을 켜야 쓸 수 있다. 한 번만 알리고 만다 —
            # 수백 번 같은 줄을 찍으면 정작 무엇이 문제인지가 안 보인다.
            _local_disabled = True
            print("    ! 네이버 **지역검색**이 이 애플리케이션에서 활성화되어 "
                  "있지 않습니다 — 홈페이지·전화 보강을 건너뜁니다.")
            print("      콘솔에서 '검색 > 지역' 을 추가하면 다음 실행부터 채워집니다.")
            return None
        if resp.status_code != 200:
            return None
        rows = resp.json().get("items", []) or []
    except Exception:                                          # noqa: BLE001
        return None
    from . import neis, analyze
    core = analyze.name_core(name)
    for r in rows:
        if addr_key(r.get("roadAddress") or r.get("address")) != want:
            continue
        # ★ 주소만으로는 모자란다. 한 건물에 여러 업소가 있다 — 실측:
        #   '메이플'(반포 · 표본 390)이 같은 주소의 **미용실**로 잡혔다.
        #   상호까지 '메이플…' 이라 이름 대조로도 안 걸렸다.
        #   → **업종이 교육이어야 한다.** 업종이 아예 없을 때만 이름으로
        #     대조한다. 표본 40곳에서 교육이 아닌 것은 그 미용실 하나였다.
        cat = r.get("category") or ""
        title = analyze._norm(clean(r.get("title")))
        if cat:
            if not any(w in cat for w in _EDU_CATEGORY):
                continue
        elif not (core and core in title):
            continue
        link = (r.get("link") or "").strip()
        return {
            "title": clean(r.get("title")),
            "link": link or None,
            "telephone": neis.clean_tel(r.get("telephone")),
            "road_address": r.get("roadAddress"),
            "category": r.get("category"),
        }
    return None


# ── 검색어 트렌드 (데이터랩) ──────────────────────────────────────
#
# 검색량은 후기 수와 **다른 것을 잰다.** 후기는 누가 썼는가(공급), 검색은
# 누가 찾았는가(수요)다. 화제성에 쓸 수 있는지는 별도 문서에서 검증했다
# (docs/TREND_VERIFICATION_2026-09-05.md) — 요지는 **점수에는 못 쓰고
# 수집 우선순위에는 쓸 수 있다** 이다.
#
# ★ 값이 절대량이 아니다. 한 요청 안에서 최댓값을 100 으로 놓은 **상대비**라,
#   요청이 다르면 비교할 수 없다. 여러 학원을 견주려면 모든 요청에 같은
#   기준 낱말(anchor)을 넣고 그 값으로 나눠야 한다.
#
# 엔드포인트가 검색과 다르다. 검색은 naverapihub, 데이터랩은 naveropenapi 다.
DATALAB_URL = "https://naveropenapi.apigw.ntruss.com/datalab/v1/search"
DATALAB_MAX_GROUPS = 5          # 한 요청에 키워드 그룹 5개까지
_datalab_disabled = False


def trend(groups: list[dict], start: str, end: str,
          unit: str = "month") -> list[dict] | None:
    """검색어 트렌드. [groups] 는 [{'groupName':..., 'keywords':[...]}] 최대 5개.

    돌려주는 것은 그룹별 `{'title','data':[{'period','ratio'}]}`.
    구독이 없으면 한 번만 알리고 None.
    """
    global _datalab_disabled
    if _datalab_disabled or not config.HAS_NAVER or not groups:
        return None
    body = {"startDate": start, "endDate": end, "timeUnit": unit,
            "keywordGroups": groups[:DATALAB_MAX_GROUPS]}
    headers = {**_headers("hub"), "Content-Type": "application/json"}
    try:
        resp = requests.post(DATALAB_URL, headers=headers, json=body,
                             timeout=TIMEOUT)
    except Exception:                                          # noqa: BLE001
        return None
    if resp.status_code in (401, 403):
        _datalab_disabled = True
        print("    ! 네이버 **검색어 트렌드(데이터랩)** 구독이 이 키에 없습니다 "
              "— 건너뜁니다.")
        print(f"      응답: {resp.text[:120]}")
        return None
    if resp.status_code != 200:
        return None
    return resp.json().get("results") or None


def queries_for(academy: dict, region_name: str) -> list[str]:
    """학원 하나에 대한 검색 질의어들.

    브랜드명 단독 질의는 동명이인/타지역 글을 대량으로 끌고 온다.
    지역명과 학원 맥락어를 반드시 함께 건다.
    """
    name = academy["name"]
    qs = [
        f"{region_name} {name} 후기",
        f"{name} 레벨테스트",
        f"{name} 학원 어때요",
    ]
    for alias in (academy.get("aliases") or [])[:2]:
        qs.append(f"{region_name} {alias} 학원")
    return qs


def collect_for_academy(academy: dict, region_name: str,
                        per_query: int = 100) -> list[dict]:
    """중복 제거된 언급 목록을 돌려준다."""
    seen: set[str] = set()
    mentions: list[dict] = []
    for query in queries_for(academy, region_name):
        for source in SOURCES:
            try:
                results = search(source, query, max_results=per_query)
            except NaverError as exc:
                print(f"    ! {source} 실패 ({query}): {exc}")
                continue
            for row in results:
                if row["url_hash"] in seen:
                    continue
                seen.add(row["url_hash"])
                row["query"] = query
                mentions.append(row)
    return mentions


def collect_all(academies: Iterable[dict], region_names: dict[str, str],
                workers: int = 3) -> list[dict]:
    """학원별 수집을 병렬로 돌린다.

    순차로 돌리면 학원 하나에 10~15회 요청 × 수백 곳이라 몇 시간이 걸린다.
    동시성은 3으로 묶어 둔다 — 초당 20회 안쪽이라 한도에 여유가 있고,
    그 이상 올리면 429를 유발해 오히려 느려진다.
    """
    academies = list(academies)
    all_mentions: list[dict] = []
    lock = threading.Lock()
    done = 0

    def work(academy: dict) -> list[dict]:
        region_name = region_names.get(academy.get("region_id"), "")
        found = collect_for_academy(academy, region_name)
        for row in found:
            row["academy_key"] = academy["id"]
            row["academy_name"] = academy["name"]
            row["region_id"] = academy.get("region_id")
        return found

    # 첫 학원은 혼자 돌린다. 여기서 모드 판별과 비활성 소스 감지가 끝나므로
    # 나머지 스레드가 같은 실패를 반복하지 않는다.
    if academies:
        first = work(academies[0])
        all_mentions.extend(first)
        done = 1
        print(f"  [{done}/{len(academies)}] {academies[0]['name']}: {len(first)}건")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, a): a for a in academies[1:]}
        for future in as_completed(futures):
            academy = futures[future]
            try:
                found = future.result()
            except Exception as exc:                      # noqa: BLE001
                print(f"    ! {academy['name']} 수집 실패: {exc}")
                found = []
            with lock:
                all_mentions.extend(found)
                done += 1
                if done % 20 == 0 or done == len(academies):
                    print(f"  [{done}/{len(academies)}] 누적 {len(all_mentions)}건")

    cache = config.CACHE_DIR / "naver_mentions.json"
    cache.write_text(json.dumps(all_mentions, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_mentions
