"""수집 대상 순환 — 단계 커버리지를 지속적으로 채운다.

문제. 수집 예산 400곳 중 **235곳이 표본 0건**이었다. 검색해도 글이
안 나오는 학원을 매 회차 붙들고 있으면 그 자리만큼 다른 후보가
밀린다. 그 결과 41개 단계 × 4학군 = 160개 조합에서 랭킹 진입 학원이
3곳 이상인 곳이 19개뿐이었다.

방안은 둘이다.

1. **헛수고 이력을 기억한다.** 수집했는데 언급이 0건이면 기록해 두고
   다음 회차에서 뒤로 민다. 두 번 비면 사실상 후보에서 내린다.
   완전히 버리지는 않는다 — 새로 생긴 학원이 나중에 회자될 수 있다.

2. **부족한 단계를 먼저 채운다.** 이미 3곳이 찬 단계보다, 0곳인
   단계의 후보에 자리를 준다. 전체 평균을 올리는 것보다 빈 칸을
   없애는 쪽이 화면에서 체감된다.

매 야간 실행마다 후보가 조금씩 순환하면서 커버리지가 올라간다.
한 번에 끝나는 작업이 아니라 **누적되는 작업**이다.
"""
from __future__ import annotations

import json

from . import config

PATH = config.CACHE_DIR / "collect_history.json"

# 이만큼 연속으로 언급 0건이면 후보에서 뒤로 민다.
DRY_LIMIT = 2

# 단계 하나당 목표 학원 수. 화면에서 '최소 3곳'을 보장하려는 값이다.
TARGET_PER_STAGE = 3


def load() -> dict:
    if not PATH.exists():
        return {}
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def record(selected: list[dict], mentions: list[dict]) -> dict:
    """이번 회차 결과를 기록한다. {학원id: {tries, dry, last}}"""
    counts: dict[str, int] = {}
    for m in mentions:
        key = m.get("academy_key")
        if key:
            counts[key] = counts.get(key, 0) + 1

    hist = load()
    for a in selected:
        aid = a["id"]
        row = hist.setdefault(aid, {"tries": 0, "dry": 0, "last": 0})
        row["tries"] += 1
        row["last"] = counts.get(aid, 0)
        row["dry"] = 0 if row["last"] else row["dry"] + 1

    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    dry = sum(1 for r in hist.values() if r["dry"] >= DRY_LIMIT)
    print(f"  수집 이력: {len(hist):,}곳 기록 · 연속 {DRY_LIMIT}회 이상 "
          f"언급 0건 {dry:,}곳(후순위)")
    return hist


def stage_gaps(academies: list[dict], scores: dict) -> dict[tuple, int]:
    """(단계, 학군) → 아직 모자란 수. 이미 찬 곳은 0."""
    have: dict[tuple, int] = {}
    for a in academies:
        s = scores.get(a["id"])
        if not (s and s.get("is_ranked")):
            continue
        for sid in a.get("stages") or []:
            key = (sid, a.get("region_id"))
            have[key] = have.get(key, 0) + 1

    tree = config.techtree()
    gaps: dict[tuple, int] = {}
    for track in tree["tracks"]:
        for st in track["stages"]:
            if st.get("roadmap_only"):
                continue
            for r in config.regions():
                key = (st["id"], r["id"])
                gaps[key] = max(0, TARGET_PER_STAGE - have.get(key, 0))
    return gaps


def priority_bonus(academy: dict, hist: dict, gaps: dict[tuple, int]) -> tuple:
    """선정 정렬에 얹을 키. 작을수록 먼저 뽑힌다.

    (헛수고 여부, 커버리지 기여 역순) — 언급이 안 나오던 곳은 뒤로,
    빈 단계를 채우는 곳은 앞으로.
    """
    row = hist.get(academy["id"]) or {}
    dry = 1 if row.get("dry", 0) >= DRY_LIMIT else 0

    region = academy.get("region_id")
    fills = sum(gaps.get((sid, region), 0) for sid in academy.get("stages") or [])
    return (dry, -fills)
