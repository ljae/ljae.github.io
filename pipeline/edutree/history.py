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


def payload() -> dict:
    """앱 번들로 내보낼 형태. 저장 형태를 그대로 쓴다."""
    hist = _load()
    return {
        "academies": hist.get("academies", {}),
        "schools": hist.get("schools", {}),
    }
