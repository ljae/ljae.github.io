"""회차별 랭킹 품질 관측. 이 지표는 정확도의 정답률이 아닌 점검 신호다.

건수 증가만으로 정확도가 좋아졌다고 판단하지 않는다. 날짜 확인율과
코호트별 비교 가능한 점수 수를 함께 남겨 다음 회차와 비교한다.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from . import config, scoring


def summarize(academies: list[dict], mentions: list[dict], subject_scores: dict) -> dict:
    valid = [m for m in mentions if not m.get("is_excluded")]
    dated = sum(scoring.publication_date(m) is not None for m in valid)
    cohorts = {}
    for a in academies:
        for subject, score in (subject_scores.get(a["id"]) or {}).items():
            key = f"{a.get('region_id')}:{subject}"
            row = cohorts.setdefault(key, {"evaluated": 0, "withEvidence": 0,
                                           "ranked": 0, "incomplete": 0})
            row["evaluated"] += 1
            row["withEvidence"] += int(score.get("sample_size", 0) > 0)
            row["ranked"] += int(bool(score.get("is_ranked")))
            row["incomplete"] += int(not score.get("is_complete", False))
    return {
        "version": scoring.SCORING_VERSION,
        "mentions": len(mentions), "validMentions": len(valid),
        "datedMentions": dated,
        "datedShare": round(dated / len(valid), 4) if valid else None,
        "sources": dict(sorted(Counter(m.get("source") or "unknown" for m in valid).items())),
        "cohorts": dict(sorted(cohorts.items())),
    }


def record(report: dict, today: str | None = None) -> dict:
    """같은 날은 교체, 이전 날짜와 비교, 실제 180일 보존. live에서만 호출."""
    day = today or date.today().isoformat()
    path = config.EXPORT_DIR / "ranking_quality.json"
    # 읽기 실패를 빈 이력으로 덮지 않는다. 기존 이력을 보존하고 실패를 알린다.
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    previous_days = [d for d in history if d < day]
    previous = history[max(previous_days)] if previous_days else None
    if previous and previous.get("version") == report["version"]:
        delta = report["validMentions"] - previous["validMentions"]
        print(f"  랭킹 품질: 이전 회차 대비 유효 근거 {delta:+,}건")
        old_share, new_share = previous.get("datedShare"), report["datedShare"]
        if old_share is not None and new_share is not None and new_share < old_share:
            print(f"  ! 작성일 확인율 하락: {old_share:.1%} → {new_share:.1%}")
        for key, old in previous.get("cohorts", {}).items():
            current = report["cohorts"].get(key, {}).get("ranked", 0)
            if current < old["ranked"]:
                print(f"  ! 순위 대상 감소 {key}: {old['ranked']} → {current}곳")
    cutoff = (date.fromisoformat(day) - timedelta(days=179)).isoformat()
    history = {d: row for d, row in history.items() if cutoff <= d <= day}
    history[day] = report
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(history, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return history
