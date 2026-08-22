"""언급을 처음 본 시점 기록 — 날짜 없는 카페 글의 화제성 보정.

카페글 검색 API 는 작성일을 주지 않는다. 실측에서 카페 글의 91%가 날짜
없이 들어왔고, 화제성 기둥이 나머지 9%로 계산됐다.

날짜를 긁어오는 대신, 매일 도는 수집 자체를 시계로 쓴다. 어제 없던 URL 이
오늘 보이면 그 글은 최근 글이다. 크롤링도, 계정 위험도, 추가 한도 소모도
없이 정확한 신호가 나온다.

주의: 첫 실행에서 본 URL 은 '기준선'으로 표시하고 날짜를 추정하지 않는다.
전부 오늘 것으로 처리하면 기존 글 수만 년치가 오늘 쏟아진 것처럼 보인다.
기준선 글은 posted_at 없이 두고, 점수 계산에서 중립 가중치를 받는다.
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

    STORE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    label = "기준선 등록" if is_first_run else "신규 발견"
    print(f"  발견 시점 기록: {label} {added:,}건 (누적 {len(store):,}건)")
    return store


def apply(mentions: list[dict], store: dict) -> int:
    """기준선 이후 새로 나타난 글에만 발견일을 작성일로 채운다."""
    filled = 0
    for m in mentions:
        if m.get("posted_at"):
            continue
        rec = store.get(m.get("url_hash", ""))
        if rec and not rec.get("baseline"):
            m["posted_at"] = rec["first_seen"]
            m["date_source"] = "discovery"
            filled += 1
    return filled
