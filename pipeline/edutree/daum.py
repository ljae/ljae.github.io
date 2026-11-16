"""다음(카카오) 검색 API 수집기 — 다음 카페 · 블로그(티스토리 등) · 웹문서.

키 발급: https://developers.kakao.com  (앱 → REST API 키, 무료)
한도   : 다음 검색 전체 일 50,000 · 카페/블로그/웹문서 각 일 30,000
         (2026-11-15 문서 기준. 바뀔 수 있다고 적혀 있다)
         size 최대 50, page 최대 50.

네이버만 보면 네이버 안에서 쓰인 글만 보인다. 다음 카페와 티스토리는
네이버 검색에 거의 안 잡힌다 — 같은 학원을 다른 사람들이 말하는 자리다.

★ naver.py 와 같은 규칙이다. API 가 돌려주는 스니펫만 저장하고 본문은
  가져오지 않는다. 원문은 링크로만 제공한다.

★ 네이버와 다른 점 하나가 크다: **모든 글에 작성 시각(`datetime`)이 온다.**
  네이버 카페 검색은 날짜를 안 줘서 날짜를 아는 글이 9%뿐이었다. 여기서 온
  날짜는 발견일이 아니라 실제 작성일이라 추세 시계열에도 쓸 수 있다.

★ 수집기는 키가 없거나 꺼져 있으면 건너뛰고 네이버 결과를 보존한다.
  전체 야간 실행은 source_health의 별도 검사로 두 검색의 실제 갱신을
  요구한다. 다음 실패도 근거 캐시는 남기지만 게시 성공으로 처리하지 않는다.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

import requests

from . import config, naver, source_health

BASE = "https://dapi.kakao.com/v2/search"
SOURCES = {
    "daum_cafe": "cafe",
    "daum_blog": "blog",
    "daum_web": "web",
}
# 웹문서는 네이버 웹문서와 같은 이유로 학원당 1질의만 돈다.
LIGHT_SOURCES = ("daum_web",)
SIZE = 50
MAX_PAGE = 50
TIMEOUT = 15
SLEEP = 0.12

_disabled_sources: set[str] = set()


class DaumError(RuntimeError):
    pass


def _headers() -> dict:
    if not config.HAS_DAUM:
        raise DaumError("KAKAO_REST_API_KEY 가 없습니다.")
    return {"Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}"}


def _parse_date(doc: dict) -> str | None:
    """'2026-11-02T09:12:00.000+09:00' → '2026-11-02'. 형식이 다르면 None —
    없는 날짜를 수집일로 채우지 않는다(naver._parse_date 와 같은 규칙)."""
    raw = doc.get("datetime") or ""
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except (TypeError, ValueError):
        return None


def _author_hash(source: str, url: str) -> str | None:
    """작성자 식별용 해시. 원본 ID 는 저장하지 않는다.

    블로그는 **주소가 곧 작성자**다 — 티스토리는 호스트 하나가 한 사람이고
    (abc.tistory.com), 네이버·브런치는 호스트 뒤 첫 마디가 사람이다
    (blog.naver.com/abc). `blogname` 은 쓰지 않는다. 이름은 겹친다.
    카페는 수천 명이 쓰는 공간이라 작성자가 아니다.
    """
    if source == "daum_cafe":
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.netloc or "").lower().removeprefix("www.").removeprefix("m.")
    if not host:
        return None
    if source == "daum_web":
        return naver._hash(host)
    if host.endswith(".tistory.com"):
        return naver._hash(host)
    first = parsed.path.strip("/").split("/", 1)[0]
    return naver._hash(f"{host}/{first}" if first else host)


def normalize_item(source: str, doc: dict) -> dict | None:
    """API 응답 한 건을 네이버와 **같은 모양**의 언급 행으로.

        cafe  title · contents · url · cafename · datetime
        blog  title · contents · url · blogname · datetime
        web   title · contents · url · datetime
    """
    link = (doc.get("url") or "").strip()
    if not link:
        return None
    return {
        "source": source,
        "source_url": link,
        "url_hash": naver._hash(link),
        "author_hash": _author_hash(source, link),
        "title": naver.clean(doc.get("title")),
        "snippet": naver.clean(doc.get("contents")),
        "posted_at": _parse_date(doc),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def search(source: str, query: str, max_results: int = SIZE) -> list[dict]:
    """한 소스에서 질의어 하나를 수집한다."""
    if source in _disabled_sources:
        return []
    out: list[dict] = []
    page = 1
    retries = 0
    while page <= MAX_PAGE and len(out) < max_results:
        params = {"query": query, "page": page, "sort": "accuracy",
                  "size": min(SIZE, max_results - len(out))}
        try:
            resp = requests.get(f"{BASE}/{SOURCES[source]}", params=params,
                                headers=_headers(), timeout=TIMEOUT)
        except requests.RequestException as exc:
            source_health.record(source, "network_error")
            raise DaumError(f"{source}: {type(exc).__name__}") from exc
        if resp.status_code == 429:
            source_health.record(source, "rate_limited")
            retries += 1
            if retries >= 3:
                # 한도는 내일까지 안 풀린다. 남은 학원에서 같은 실패를
                # 수천 번 되풀이하지 않는다.
                _disabled_sources.add(source)
                raise DaumError(f"{source}: 요청 한도 — 이번 실행에서 제외")
            time.sleep(2.0)
            continue
        retries = 0
        if resp.status_code != 200:
            fatal = resp.status_code in (401, 403)
            source_health.record(source, "disabled" if fatal
                                 else f"http_{resp.status_code}")
            if fatal:
                # 키가 틀렸거나 앱에서 다음 검색이 꺼져 있다. 다시 불러도
                # 같은 답이다 — 한 번 알리고 이 소스를 뺀다.
                _disabled_sources.add(source)
                print(f"    ! {source} 를 쓸 수 없습니다(HTTP {resp.status_code}) "
                      f"— 이번 실행에서 제외합니다.")
                print(f"      응답: {resp.text[:120]}")
                return out
            raise DaumError(f"{source} {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        docs = body.get("documents") or []
        source_health.record(source, "available", len(docs))
        for doc in docs:
            row = normalize_item(source, doc)
            if row:
                out.append(row)
        if not docs or (body.get("meta") or {}).get("is_end", True):
            break
        page += 1
        time.sleep(SLEEP)
    return out


def collect_for_academy(academy: dict, region_name: str,
                        per_query: int = SIZE) -> list[dict]:
    """질의는 네이버와 같은 것을 쓴다 — 지역명과 학원 맥락어를 반드시 건다."""
    seen: set[str] = set()
    mentions: list[dict] = []
    full = naver.queries_for(academy, region_name)
    for source in SOURCES:
        queries = [naver.light_query(academy, region_name)] \
            if source in LIGHT_SOURCES else full
        for query in queries:
            try:
                results = search(source, query, max_results=per_query)
            except DaumError as exc:
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
    """학원별 수집을 병렬로 돌린다. 어떤 실패도 밖으로 던지지 않는다 —
    여기까지 오면 네이버 수집이 이미 끝나 있고, 그것을 버릴 이유가 없다."""
    academies = list(academies)
    if not config.HAS_DAUM or not academies:
        return []
    _disabled_sources.clear()
    out: list[dict] = []
    lock = threading.Lock()
    done = 0

    def work(academy: dict) -> list[dict]:
        if len(_disabled_sources) == len(SOURCES):
            return []
        region_name = region_names.get(academy.get("region_id"), "")
        found = collect_for_academy(academy, region_name)
        for row in found:
            row["academy_key"] = academy["id"]
            row["academy_name"] = academy["name"]
            row["region_id"] = academy.get("region_id")
        return found

    # 첫 학원은 혼자 돌린다 — 키 오류를 여기서 한 번만 겪는다.
    try:
        out.extend(work(academies[0]))
    except Exception as exc:                              # noqa: BLE001
        print(f"    ! {academies[0]['name']} 다음 수집 실패: {exc}")
    done = 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, a): a for a in academies[1:]}
        for future in as_completed(futures):
            try:
                found = future.result()
            except Exception as exc:                      # noqa: BLE001
                print(f"    ! {futures[future]['name']} 다음 수집 실패: {exc}")
                found = []
            with lock:
                out.extend(found)
                done += 1
                if done % 100 == 0 or done == len(academies):
                    print(f"  [다음 {done}/{len(academies)}] 누적 {len(out)}건")

    source_health.save()
    return out
