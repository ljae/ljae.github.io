"""사용자 행동 — 접수·신고·전화가 다음 회차의 수집을 정한다.

앱이 세 가지를 Supabase 에 남긴다(supabase/14_reservations_reports.sql).

  academy_actions    전화·예약 버튼을 누른 사실. 누가인지는 없다.
  test_reservations  레벨테스트 예약 요청. 운영자가 학원에 연락해 잇는다.
  evidence_reports   '이 글은 이 학원 글이 아니에요'. 질문 큐 맨 앞으로.

★ 셋 다 **점수에 쓰지 않는다.** 행동은 수집 우선순위(demand 와 같은 층)에,
  신고는 검수 질문에 들어간다. 학부모가 전화를 거는 학원은 우리가 근거를
  더 찾아야 할 학원이지 점수가 높은 학원이 아니고, 익명 신고가 곧 삭제가
  되면 학원이 불리한 글만 지우는 통로가 된다.

키가 없으면 전부 빈 값이다. 파이프라인은 그대로 돈다.
"""
from __future__ import annotations

import json

import requests

from . import config

# 행동 종류별 무게. 예약 요청이 전화보다, 전화가 번호 복사보다 강한 신호다.
WEIGHTS = {"call": 2, "reserve": 3, "copy_tel": 1, "map": 1}
# 한 학원이 다른 신호를 전부 눌러서는 안 된다(demand.CAP 과 같은 뜻).
CAP = 30


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict) -> list[dict]:
    if not config.HAS_SUPABASE:
        return []
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/{path}",
                         params=params, headers=_headers(), timeout=20)
        return r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        # 부산물이다. 네트워크가 한 번 끊겼다고 실행 전체를 잃지 않는다.
        return []


def load() -> dict[str, int]:
    """학원 id → 행동 점수(최근 30일). 수집 우선순위에만 쓴다."""
    out: dict[str, int] = {}
    for row in _get("v_academy_action_counts",
                    {"select": "academy_key,action,n"}):
        key = str(row.get("academy_key") or "")
        w = WEIGHTS.get(row.get("action") or "", 0)
        if key and w:
            out[key] = min(CAP, out.get(key, 0) + w * int(row.get("n") or 0))
    return out


def open_reservations() -> list[dict]:
    return _get("test_reservations",
                {"select": "*", "status": "eq.open", "order": "created_at.desc"})


def open_reports() -> list[dict]:
    return _get("evidence_reports",
                {"select": "*", "status": "eq.open", "order": "created_at.desc"})


def mark_reports_queued(ids: list[str]) -> None:
    """질문으로 올린 신고는 queued 로 밀봉한다. 매일 같은 신고로 같은 질문을
    만들지 않기 위해서다 — 답은 질문 쪽에서 판정·규칙이 된다."""
    if not ids or not config.HAS_SUPABASE:
        return
    try:
        requests.patch(
            f"{config.SUPABASE_URL}/rest/v1/evidence_reports",
            params={"id": f"in.({','.join(ids)})"},
            headers=_headers(), data=json.dumps({"status": "queued"}),
            timeout=20)
    except requests.RequestException:
        pass
