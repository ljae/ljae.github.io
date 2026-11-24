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

import fcntl
import gzip
import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import date

from . import config

PATH = config.CACHE_DIR / "mention_store.json.gz"
VERSION = 1
# 학원 하나에 이만큼만 둔다. 검색 API 는 질의당 100건이 상한이라 실측
# 최대치(한 학원 1,500건)를 넉넉히 덮는다. 넘치면 오래 못 본 것부터 뺀다.
KEEP_PER_ACADEMY = 2000

# ★ 저장소 원본(JSON) 크기 예산 (2026-11-24).
#   저장소는 검색 결과를 **전부** 쌓았다. 실측 11-23: 127만 줄 중 게이트를
#   지나 근거가 된 것은 10만 줄(8%)이고, 밤마다 12만 줄씩 늘었다. 11-16 에
#   백업 검사 한도(512 MiB)를 넘어 1 GiB 로 올렸고, 11-22 에 그것도 넘어
#   야간 게시가 이틀 연속 멈췄다. 한도를 또 올리면 같은 일이 또 온다 —
#   한도는 넘지 않게 **쓰는 쪽이 지켜야** 한다.
#   evidence_backup.MAX_RAW_BYTES(1 GiB)의 70%. 남는 30% 는 하룻밤 증가분
#   (약 110 MiB)을 몇 번 받아낼 여유다.
RAW_BUDGET_BYTES = 700 * 1024 * 1024
# 근거 표시. 게이트를 지나 근거 후보가 된 적이 있는 글(url_hash)의 줄에
# 마지막으로 그랬던 날을 적는다. **보존 순서에만 쓴다** — 점수·게이트는
# 이 값을 읽지 않는다(매 회차 원자료에서 다시 판정한다는 원칙 그대로).
EVIDENCE_FIELD = "evidence_seen"
# 근거만으로 예산의 이만큼을 넘으면 알린다. 근거는 지우지 않으므로 이때가
# 사람이 보존 정책을 다시 볼 차례다(밤 3천 줄 남짓 늘어 1년 넘게 남는다).
EVIDENCE_WARN_SHARE = 0.6

# 저장하는 원본 필드. 분석 결과(sentiment 등)는 넣지 않는다.
RAW_FIELDS = ("source", "source_url", "url_hash", "author_hash", "title",
              "snippet", "posted_at", "date_source", "collected_at", "query",
              "academy_key", "academy_name", "region_id", "collector", "search_url")


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


@contextmanager
def _store_lock():
    """모든 수집기가 같은 저장소의 읽기·병합·교체를 직렬화한다."""
    PATH.parent.mkdir(parents=True, exist_ok=True)
    # 교체되는 gzip 파일 자체를 잠그면 다음 쓰기와 서로 다른 inode를
    # 잠글 수 있다. 저장소마다 별도의 영구 lock 파일을 둔다.
    lock_path = PATH.with_name(PATH.name + ".lock")
    with lock_path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def merge(fresh: list[dict], today: str | None = None,
          quiet: bool = False) -> list[dict]:
    """이번 회차 원본을 저장소에 합치고, 저장소 전체를 돌려준다."""
    with _store_lock():
        return _merge_unlocked(fresh, today=today, quiet=quiet)


def _merge_unlocked(fresh: list[dict], today: str | None = None,
                    quiet: bool = False) -> list[dict]:
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
                # 선택한 스니펫의 수집 경로를 함께 교체한다. API 글에
                # Ego 스니펫만 섞이면 이후 본문 수집 제한을 잃게 되고,
                # 반대 방향은 API 글을 옛 브라우저 검색으로 오인하게 된다.
                for field in ("collector", "search_url", "query", "collected_at"):
                    row.pop(field, None)
                    if field in raw:
                        row[field] = raw[field]
            if raw.get("posted_at") and (
                    not row.get("posted_at") or (
                        row.get("date_source") == "discovery"
                        and raw.get("date_source") != "discovery")):
                row["posted_at"] = raw["posted_at"]
                row.pop("date_source", None)
                if raw.get("date_source"):
                    row["date_source"] = raw["date_source"]
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
        # 근거가 된 적 없는 줄부터 뺀다. 그 안에서는 오래 못 본 것부터.
        keys.sort(key=lambda k: (bool(store[k].get(EVIDENCE_FIELD)),
                                 store[k].get("last_seen") or "",
                                 store[k].get("first_seen") or ""))
        for k in keys[: len(keys) - KEEP_PER_ACADEMY]:
            del store[k]
            dropped += 1
    return dropped


def _row_bytes(key: str, row: dict) -> int:
    """저장 파일 안에서 이 줄이 차지하는 대략의 바이트(UTF-8, 구분자 포함)."""
    return (len(json.dumps(key, ensure_ascii=False).encode())
            + len(json.dumps(row, ensure_ascii=False).encode()) + 4)


def retain(evidence_hashes: set[str], today: str | None = None,
           budget: int | None = None, quiet: bool = False) -> dict:
    """근거 표시를 남기고, 저장소를 크기 예산 안으로 줄인다.

    - 이번 회차 게이트를 지난 글의 줄에 `evidence_seen` 을 적는다.
    - 예산을 넘으면 **근거가 된 적 없는 줄만**, 오래 못 본 것부터 뺀다.
      근거가 된 줄은 지우지 않는다 — '한 번 찾은 근거는 남는다' 는 이
      저장소의 약속이다. 뺀 줄도 검색에 다시 걸리면 다음 회차에 새로 들어온다.
    - 근거만으로 예산을 넘기면 지우지 않고 알린다(`overBudget`).
    """
    limit = RAW_BUDGET_BYTES if budget is None else budget
    day = today or date.today().isoformat()
    with _store_lock():
        store = load()
        if not store:
            return {"rows": 0, "evidenceRows": 0, "bytes": 0, "dropped": 0,
                    "budget": limit, "overBudget": False}
        for row in store.values():
            if row.get("url_hash") in evidence_hashes:
                row[EVIDENCE_FIELD] = day
        sizes = {k: _row_bytes(k, r) for k, r in store.items()}
        total = sum(sizes.values()) + 32
        dropped = 0
        if total > limit:
            loose = sorted((k for k, r in store.items() if not r.get(EVIDENCE_FIELD)),
                           key=lambda k: (store[k].get("last_seen") or "",
                                          store[k].get("first_seen") or ""))
            for k in loose:
                if total <= limit:
                    break
                total -= sizes.pop(k)
                del store[k]
                dropped += 1
        evidence = sum(1 for r in store.values() if r.get(EVIDENCE_FIELD))
        evidence_bytes = sum(sizes[k] for k, r in store.items() if r.get(EVIDENCE_FIELD))
        _save(store)
    result = {"rows": len(store), "evidenceRows": evidence, "bytes": total,
              "dropped": dropped, "budget": limit, "overBudget": total > limit,
              "evidenceShare": round(evidence_bytes / limit, 3)}
    if not quiet:
        print(f"  언급 저장소 보존: {len(store):,}줄 · 근거 {evidence:,}줄 · "
              f"{total / 2**20:,.0f}/{limit / 2**20:,.0f} MiB"
              + (f" · 근거 아닌 줄 {dropped:,}건 정리" if dropped else ""))
        if result["overBudget"]:
            print("  ! 언급 저장소: 근거만으로 크기 예산을 넘었다 — 지우지 않았다. "
                  "백업 한도(evidence_backup.MAX_RAW_BYTES)에 닿기 전에 보존 정책을 정할 것")
        elif result["evidenceShare"] >= EVIDENCE_WARN_SHARE:
            print(f"  ! 언급 저장소: 근거가 크기 예산의 {result['evidenceShare']:.0%} — "
                  "보존 정책을 다시 볼 때가 다가온다")
    return result


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
