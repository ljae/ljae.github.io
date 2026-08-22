"""네이버 검색 오픈 API 수집기 — 카페글 · 블로그 · 지식iN.

키 발급: https://developers.naver.com/apps  (검색 API 선택, 무료)
한도   : 앱당 일 25,000 호출. display 최대 100, start 최대 1000.

★ 이 모듈은 API가 돌려주는 '스니펫'만 저장한다. 게시물 본문을 통째로
  가져오거나 재배포하지 않는다. 원문은 링크로만 제공한다.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
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
            raise NaverError(f"{source} {resp.status_code}: {resp.text[:200]}")

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


def collect_all(academies: Iterable[dict], region_names: dict[str, str]) -> list[dict]:
    all_mentions: list[dict] = []
    for academy in academies:
        region_name = region_names.get(academy.get("region_id"), "")
        found = collect_for_academy(academy, region_name)
        for row in found:
            row["academy_key"] = academy["name_normalized"]
            row["academy_name"] = academy["name"]
            row["region_id"] = academy.get("region_id")
        print(f"  네이버 {academy['name']:<16} {len(found):>4}건")
        all_mentions.extend(found)

    cache = config.CACHE_DIR / "naver_mentions.json"
    cache.write_text(json.dumps(all_mentions, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_mentions
