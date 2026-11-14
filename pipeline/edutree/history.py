"""랭킹 이력 — 매 수집마다 스냅샷을 남긴다.

'지난주보다 올랐나'는 학부모가 가장 먼저 보는 것 중 하나이고, 지금
화면의 상승·보합 화살표는 언급량 추세일 뿐 **순위 변동이 아니다**.
둘은 다른 이야기다.

과거 이력은 없다. 공개된 어디에도 우리 산식의 과거 순위가 없으니
만들어 낼 수 없다 — **오늘부터 쌓는다.** 지어내는 것보다 비어 있는
편이 낫고, 화면도 '집계 시작 이후'라고 그대로 말한다.

★ 저장 형식
  파일 하나에 날짜별 스냅샷을 쌓는다(history.json). 학원 400곳 ×
  하루 한 번이면 1년에 15만 행 정도라 파일 하나로 충분하다.
  용량이 문제가 되면 그때 나누면 된다 — 지금 나누면 복잡하기만 하다.

★ 같은 날 두 번 돌면 덮어쓴다. 하루에 여러 번 수집하는 날이 있는데
  그때마다 점이 늘면 추이가 아니라 잡음이 된다.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from . import config, scoring

# 앱 번들과 같은 곳에 둔다. 야간 워크플로가 이미 이 디렉터리를 커밋하므로
# 이력이 실행 사이에 살아남는다. 캐시에 두면 캐시가 비워질 때 이력도 사라진다.
PATH = config.EXPORT_DIR / "history.json"
KEEP_DAYS = 180          # 6개월. 그 이전은 추이를 보는 데 쓰이지 않는다.


def _load() -> dict:
    if not PATH.exists():
        return {"academies": {}, "schools": {}}
    # 깨진 이력을 빈 값으로 읽으면 다음 기록이 정상 이력까지 지운다.
    return json.loads(PATH.read_text(encoding="utf-8"))


def record(academies: list[dict], scores: dict,
           schools: list[dict] | None = None, today: str | None = None) -> dict:
    """오늘 자 스냅샷을 남긴다. 같은 날짜는 덮어쓴다."""
    day = today or date.today().isoformat()
    hist = _load()

    # 같은 날 재채점에서 탈락·삭제된 행도 지운다. 과거 날짜는 보존한다.
    for bucket in ("academies", "schools"):
        for rows in hist.setdefault(bucket, {}).values():
            rows.pop(day, None)

    acad = hist.setdefault("academies", {})
    for a in academies:
        s = scores.get(a["id"])
        if not s or not s.get("is_ranked"):
            continue
        row = acad.setdefault(a["id"], {})
        row[day] = {
            "r": s.get("rank_in_region"),
            "t": round(float(s["total"]), 1),
            "n": s.get("sample_size"),
            "subject": s.get("subject") or scoring.primary_subject(a),
            "region": a.get("region_id"),
            "cohortSize": s.get("region_ranked_count"),
            "version": scoring.SCORING_VERSION,
        }

    # 학교는 진로 공시가 붙은 곳만. 공시가 연 1회라 점이 드물게 찍힌다.
    sch = hist.setdefault("schools", {})
    for s in schools or []:
        c = s.get("careers")
        if not c:
            continue
        if s.get("level") == "middle":
            v = (c.get("특수목적고") or 0) + (c.get("자율고") or 0)
        else:
            v = c.get("대학")
        if v is None:
            continue
        sch.setdefault(s["id"], {})[day] = {"v": round(float(v), 1)}

    _prune(hist, day)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    tmp.replace(PATH)
    days = {d for rows in acad.values() for d in rows}
    print(f"  랭킹 이력: {len(acad):,}곳 · {len(days)}일치 "
          f"({min(days) if days else '-'} ~ {max(days) if days else '-'})")
    return hist


def _prune(hist: dict, today: str | None = None) -> None:
    """관측 횟수가 아닌 실제 180일을 보존한다."""
    day = date.fromisoformat(today) if today else date.today()
    cutoff = (day - timedelta(days=KEEP_DAYS - 1)).isoformat()
    for bucket in ("academies", "schools"):
        rows = hist.get(bucket) or {}
        for key, r in list(rows.items()):
            kept = {d: v for d, v in r.items() if cutoff <= d <= day.isoformat()}
            if kept:
                rows[key] = kept
            else:
                del rows[key]


def brief(academies: list[dict], generated_at: str | None = None,
          region: str | None = None) -> dict:
    """마지막 회차가 직전 회차에서 무엇을 바꿨는지 — 아침 알림 한 통 분량.

    순위는 (학군 × 과목) 안에서만 뜻이 있으므로 같은 코호트끼리만 견준다.
    산식 판이 바뀐 회차는 그렇게 적는다 — 그날의 변동은 학원이 아니라
    우리가 만든 것이다.
    """
    acad = _load().get("academies", {})
    if region:
        # 한 학군만. 그 학군에 있었던 날이 하루라도 있는 학원.
        acad = {k: v for k, v in acad.items()
                if any(row.get("region") == region for row in v.values())}
    days = sorted({d for rows in acad.values() for d in rows})
    if not days:
        return {"day": None, "generatedAt": generated_at}
    day, prev = days[-1], (days[-2] if len(days) > 1 else None)
    names = {a["id"]: (a.get("display_name") or a.get("name") or a["id"]) for a in academies}
    regions = {r["id"]: r.get("name_ko") or r["id"] for r in config.regions()}

    def item(key: str, now: dict, before: dict | None) -> dict:
        return {"name": names.get(key, key),
                "region": regions.get(now.get("region"), now.get("region")),
                "subject": config.SUBJECTS.get(now.get("subject"), now.get("subject")),
                "from": before.get("r") if before else None, "to": now.get("r")}

    entered = left = moved = 0
    firsts, rises = [], []
    versions = set()
    for key, rows in acad.items():
        now, before = rows.get(day), rows.get(prev) if prev else None
        if now and before and (now.get("region"), now.get("subject")) != (
                before.get("region"), before.get("subject")):
            before = None                    # 코호트가 바뀌면 등수를 견줄 수 없다
        if now:
            versions.add(now.get("version"))
        if before:
            versions.add(before.get("version"))
        if now and not before:
            entered += 1 if prev else 0
        elif before and not now:
            left += 1
        if not (now and before) or now.get("r") is None or before.get("r") is None:
            if now and prev and now.get("r") == 1:
                firsts.append(item(key, now, None))
            continue
        if now["r"] != before["r"]:
            moved += 1
            if now["r"] == 1:
                firsts.append(item(key, now, before))
            elif before["r"] - now["r"] > 0:
                rises.append(item(key, now, before))
    rises.sort(key=lambda x: (-(x["from"] - x["to"]), x["to"], x["name"]))
    firsts.sort(key=lambda x: (x["region"] or "", x["subject"] or "", x["name"]))
    ranked = sum(1 for rows in acad.values() if day in rows)
    return {
        "day": day, "previousDay": prev, "generatedAt": generated_at,
        "ranked": ranked,
        "rankedBefore": sum(1 for rows in acad.values() if prev in rows) if prev else None,
        "entered": entered, "left": left, "moved": moved,
        "scoringChanged": len(versions - {None}) > 1,
        "newFirsts": firsts[:5], "newFirstCount": len(firsts),
        "topRises": rises[:3],
    }


def payload() -> dict:
    """앱 번들로 내보낼 형태. 저장 형태를 그대로 쓴다."""
    hist = _load()
    return {
        "academies": hist.get("academies", {}),
        "schools": hist.get("schools", {}),
    }
