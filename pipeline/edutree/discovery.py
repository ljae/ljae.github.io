"""언급을 처음 본 시점 기록 — 날짜 없는 카페 글의 화제성 보정.

카페글 검색 API 는 작성일을 주지 않는다. 실측에서 카페 글의 91%가 날짜
없이 들어왔고, 화제성 기둥이 나머지 9%로 계산됐다.

날짜를 긁어오는 대신, 매일 도는 수집 자체를 시계로 쓴다. 어제 없던 URL 이
오늘 보이면 그 글은 최근 글이다. 크롤링도, 계정 위험도, 추가 한도 소모도
없이 정확한 신호가 나온다.

주의: 첫 실행에서 본 URL 은 '기준선'으로 표시하고 날짜를 추정하지 않는다.
전부 오늘 것으로 처리하면 기존 글 수만 년치가 오늘 쏟아진 것처럼 보인다.
기준선 글은 posted_at 없이 두고, 점수 계산에서 중립 가중치를 받는다.

★ 기준선 방어는 **실행 단위로만** 걸려 있었고, 그래서 새지 않는 척했다.
  수집 예산은 400곳이고 회차마다 **대상이 순환한다.** 어떤 학원을 처음
  수집하면 그 학원의 글이 수십 년치라도 전부 '오늘 처음 본 것' 이 되어
  오늘 날짜를 받는다. 새로 쓰인 것이 아니라 **우리가 이제 본 것**인데도.

  실측(2026-08-30): 발견분 27,533건이 단 사흘(8/22~24)에 몰려 있었고,
  날짜를 아는 글의 81%가 그 사흘짜리 봉우리였다. 그 결과 추세가 있는
  학원 44곳 중 40곳이 '상승' 으로 나왔다 — 화살표가 학원의 화제성이
  아니라 **우리 수집 일정**을 가리키고 있었다.

  → 이전 회차에 **이미 보고 있던 학원**의 글에만 발견일을 채운다.
    그 학원을 처음 수집하는 회차라면 '어제 없던 URL' 이라는 말 자체가
    성립하지 않는다. 학원 단위로도 기준선을 두는 셈이다.
"""
from __future__ import annotations

import json
from datetime import date

from . import config

STORE = config.CACHE_DIR / "first_seen.json"


def load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def mark_initial_sweeps(store: dict, mentions: list[dict]) -> int:
    """학원을 **처음 수집한 날**의 도장을 소급해 기준선으로 바꾼다.

    실행 단위 기준선만으로는 이미 굳어 버린 봉우리를 못 지운다. 학원
    하나를 처음 수집하면 그 학원의 글이 몇 년치든 **같은 하루**에 전부
    도장을 받는데, 그 날짜가 곧 작성일로 쓰이고 있었다.

    거꾸로 읽으면 판별할 수 있다: 어떤 학원의 도장 날짜 중 **가장 이른
    하루**가 그 학원의 첫 수집일이고, 그날 찍힌 글은 '새로 쓰인 것' 이
    아니라 '그때 처음 본 것' 이다. 그 뒤 다른 날에 나타난 글만 진짜
    발견이다.

    ★ 여러 학원에 걸친 글은 **모든 학원에서** 첫 수집일일 때만 기준선으로
      돌린다. 한 곳이라도 이미 보고 있던 학원이 있었다면 그 학원에게는
      진짜 새 글이다 — 지우면 멀쩡한 최신성 신호가 사라진다.
    """
    first_day: dict[str, str] = {}
    posts: dict[str, set[str]] = {}
    for m in mentions:
        h, aid = m.get("url_hash"), m.get("academy_key")
        rec = store.get(h or "")
        if not (h and aid and rec):
            continue
        posts.setdefault(h, set()).add(aid)
        day = rec["first_seen"]
        if aid not in first_day or day < first_day[aid]:
            first_day[aid] = day

    changed = 0
    for h, owners in posts.items():
        rec = store[h]
        if rec.get("baseline"):
            continue
        if all(rec["first_seen"] == first_day.get(aid) for aid in owners):
            rec["baseline"] = True
            rec["baseline_reason"] = "initial_sweep"
            changed += 1
    return changed


def update(mentions: list[dict]) -> dict:
    """처음 보는 URL 을 오늘 날짜로 기록한다.

    저장소가 비어 있으면 이번 실행 전체가 기준선이다.
    """
    store = load()
    is_first_run = not store
    today = date.today().isoformat()

    added = 0
    for m in mentions:
        h = m.get("url_hash")
        if not h or h in store:
            continue
        store[h] = {"first_seen": today, "baseline": is_first_run}
        added += 1

    # 이미 굳은 첫 수집 스윕을 소급해 기준선으로 돌린다. 멱등이라 매
    # 실행 돌려도 같은 결과가 나온다.
    healed = mark_initial_sweeps(store, mentions)

    STORE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    label = "기준선 등록" if is_first_run else "신규 발견"
    print(f"  발견 시점 기록: {label} {added:,}건 (누적 {len(store):,}건)"
          + (f" · 첫 수집 스윕 {healed:,}건을 기준선으로 정정" if healed else ""))
    return store


def apply(mentions: list[dict], store: dict,
          watched: set[str] | None = None) -> tuple[int, int]:
    """기준선 이후 새로 나타난 글에만 발견일을 작성일로 채운다.

    [watched] 는 **이번 회차 전에 이미 수집해 본 학원** id 다. 그 학원을
    처음 보는 회차라면 '어제 없던 URL' 이 아니라 '어제 안 찾아본 URL' 이라
    발견일이 작성일의 근거가 못 된다 — 모듈 docstring 의 ★ 참고.
    None 이면(이력을 모르면) 옛 동작대로 전부 채운다.

    (채운 수, 학원을 처음 봐서 보류한 수) 를 돌려준다.
    """
    filled = held = 0
    for m in mentions:
        if m.get("posted_at"):
            continue
        rec = store.get(m.get("url_hash", ""))
        if not rec or rec.get("baseline"):
            continue
        if watched is not None and m.get("academy_key") not in watched:
            held += 1          # 이 학원을 처음 본 회차 — 날짜를 지어내지 않는다
            continue
        m["posted_at"] = rec["first_seen"]
        m["date_source"] = "discovery"
        filled += 1
    return filled, held
