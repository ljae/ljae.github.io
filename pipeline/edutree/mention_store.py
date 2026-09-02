"""언급 저장소 — 한 번 찾은 근거는 다음 회차에도 남는다.

지금까지 수집 결과(naver_mentions.json)는 **회차마다 통째로 갈아끼웠다.**
그래서 두 가지가 얽혀 있었다.

  1. 이번 회차에 안 뽑힌 학원은 지난 근거까지 잃고 화면에서 사라진다.
     그래서 '랭킹에 든 학원은 자리를 지킨다' 는 규칙이 필요했고, 400칸 중
     상당수가 같은 학원을 매일 다시 보는 데 쓰였다.
  2. 예산이 늘지 않는 한 채점 대상은 400곳에서 자라지 못한다 — 등록부
     5,300곳 중 249곳이 표본 0, 248곳이 근거 0건인 채로 굳어 있었다.

글은 사라지지 않는다. 어제 찾은 후기는 오늘도 그 학원 이야기다. 그러니
근거를 **쌓고**, 예산은 아직 안 본 곳과 오래된 곳을 다시 보는 데 쓴다.
회차가 거듭될수록 채점 대상이 늘고, 최신성 가중(180일 반감)이 낡은 글의
무게를 알아서 줄인다.

저장소에는 **API 가 준 원본**만 둔다(제목·스니펫·링크·날짜). 블로그 본문
보강·감성·판정은 매 회차 원자료에서 다시 짓는다 — posts.py 의 무효화가
'다시 짓는다' 로 푸는 것과 같은 이유다. 운영자 판정과 규칙은 이 저장소가
아니라 Supabase·위키에 있으므로 여기 쌓인 글도 매번 같은 게이트를 지난다.

위치는 .cache 다. 야간 워크플로가 실행 사이에 보존하는 곳이고, 비면 이번
회차 결과로 다시 시작한다(first_seen.json 과 같은 처지). 앱 번들 디렉터리에
두지 않는 이유: 수십 MB 를 웹 앱에 실어 보낼 수 없다.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import date

from . import config

PATH = config.CACHE_DIR / "mention_store.json.gz"
VERSION = 1
# 학원 하나에 이만큼만 둔다. 검색 API 는 질의당 100건이 상한이라 실측
# 최대치(한 학원 1,500건)를 넉넉히 덮는다. 넘치면 오래 못 본 것부터 뺀다.
KEEP_PER_ACADEMY = 2000

# 저장하는 원본 필드. 분석 결과(sentiment 등)는 넣지 않는다.
RAW_FIELDS = ("source", "source_url", "url_hash", "author_hash", "title",
              "snippet", "posted_at", "collected_at", "query",
              "academy_key", "academy_name", "region_id")


def _key(m: dict) -> str:
    return f"{m.get('url_hash')}|{m.get('academy_key')}"


def exists() -> bool:
    return PATH.exists()


def load() -> dict[str, dict]:
    if not PATH.exists():
        return {}
    try:
        with gzip.open(PATH, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, EOFError):
        return {}
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return {}
    return data.get("rows") or {}


def _save(rows: dict[str, dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump({"version": VERSION, "rows": rows}, fh, ensure_ascii=False)
    tmp.replace(PATH)


def _strip(m: dict) -> dict:
    return {k: m.get(k) for k in RAW_FIELDS if m.get(k) is not None}


def merge(fresh: list[dict], today: str | None = None,
          quiet: bool = False) -> list[dict]:
    """이번 회차 원본을 저장소에 합치고, 저장소 전체를 돌려준다."""
    day = today or date.today().isoformat()
    store = load()
    added = updated = 0
    for m in fresh:
        if m.get("is_demo") or not m.get("url_hash") or not m.get("academy_key"):
            continue
        key = _key(m)
        row = store.get(key)
        raw = _strip(m)
        if row is None:
            raw["first_seen"] = day
            raw["last_seen"] = day
            store[key] = raw
            added += 1
        else:
            # 스니펫은 질의어에 따라 다른 대목이 오므로 긴 쪽을 남긴다.
            # 날짜는 있는 쪽을 남긴다.
            if len(raw.get("snippet") or "") > len(row.get("snippet") or ""):
                row["snippet"] = raw["snippet"]
            if raw.get("posted_at") and not row.get("posted_at"):
                row["posted_at"] = raw["posted_at"]
            row["last_seen"] = day
            updated += 1

    dropped = _cap(store)
    _save(store)
    if not quiet:
        print(f"  언급 저장소: {len(store):,}건 (신규 {added:,} · 재확인 {updated:,}"
              + (f" · 상한 초과 정리 {dropped:,}" if dropped else "") + ")")
    return rows_of(store)


def _cap(store: dict[str, dict]) -> int:
    by_ac: dict[str, list[str]] = defaultdict(list)
    for key, row in store.items():
        by_ac[str(row.get("academy_key"))].append(key)
    dropped = 0
    for keys in by_ac.values():
        if len(keys) <= KEEP_PER_ACADEMY:
            continue
        keys.sort(key=lambda k: (store[k].get("last_seen") or "",
                                 store[k].get("first_seen") or ""))
        for k in keys[: len(keys) - KEEP_PER_ACADEMY]:
            del store[k]
            dropped += 1
    return dropped


def rows_of(store: dict[str, dict]) -> list[dict]:
    """저장소 → 파이프라인이 쓰는 언급 목록(복사본)."""
    return [dict(r) for r in store.values()]


def rows() -> list[dict]:
    return rows_of(load())


def academy_keys() -> set[str]:
    return {str(r.get("academy_key")) for r in load().values()}


def stats(rows: list[dict]) -> str:
    by_ac: dict = defaultdict(int)
    for r in rows:
        by_ac[r.get("academy_key")] += 1
    return f"{len(rows):,}건 · 학원 {len(by_ac):,}곳"
