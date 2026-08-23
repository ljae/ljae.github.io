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
from datetime import date

from . import config

# 앱 번들과 같은 곳에 둔다. 야간 워크플로가 이미 이 디렉터리를 커밋하므로
# 이력이 실행 사이에 살아남는다. 캐시에 두면 캐시가 비워질 때 이력도 사라진다.
PATH = config.EXPORT_DIR / "history.json"
KEEP_DAYS = 180          # 6개월. 그 이전은 추이를 보는 데 쓰이지 않는다.


def _load() -> dict:
    if not PATH.exists():
        return {"academies": {}, "schools": {}}
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"academies": {}, "schools": {}}


def record(academies: list[dict], scores: dict,
           schools: list[dict] | None = None, today: str | None = None) -> dict:
    """오늘 자 스냅샷을 남긴다. 같은 날짜는 덮어쓴다."""
    day = today or date.today().isoformat()
    hist = _load()

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

    _prune(hist)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    days = {d for rows in acad.values() for d in rows}
    print(f"  랭킹 이력: {len(acad):,}곳 · {len(days)}일치 "
          f"({min(days) if days else '-'} ~ {max(days) if days else '-'})")
    return hist


def _prune(hist: dict) -> None:
    """오래된 점을 덜어낸다. 날짜 문자열이라 정렬 비교로 충분하다."""
    for bucket in ("academies", "schools"):
        rows = hist.get(bucket) or {}
        days = sorted({d for r in rows.values() for d in r})
        if len(days) <= KEEP_DAYS:
            continue
        cutoff = days[-KEEP_DAYS]
        for key, r in list(rows.items()):
            kept = {d: v for d, v in r.items() if d >= cutoff}
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
