"""학부모 제보 — 학원 한 곳에 대한 구조화 답을 수집 우선순위로만 읽는다.

앱의 /tell 화면이 로그인 없이 받는다(supabase/18_parent_reports.sql).
자유 서술도 연락처도 없고, 학년은 학년대만 있다.

★ **점수에 쓰지 않는다.** actions.py 와 같은 층이다 — 학부모가 제보한
  학원은 우리가 근거를 더 찾아야 할 학원이지 점수가 높은 학원이 아니다.
  익명 답이 곧 점수가 되면 학원이 제 답을 채우는 통로가 된다. 이 모듈이
  내보내는 것은 '학원별 서로 다른 기기 수' 하나이고, build 는 그것을
  select_for_mentions 의 수요 신호(want)에만 보탠다.

★ 답의 내용(레벨테스트·숙제량…)은 여기서 읽지 않는다. 읽어 오면 언젠가
  누군가 쓴다. 화면에 합계로 내보내는 일은 운영자의 검수 뒤에 따로 정한다.

키가 없으면 빈 값이다. 네트워크가 끊겨도 빈 값이고 한 줄만 찍는다 —
부산물 하나 때문에 실행 전체를 잃지 않는다.
"""
from __future__ import annotations

import requests

from . import config

# 기기 한 대의 제보가 갖는 무게. 버튼을 누른 것(actions: 1~3)보다 품이
# 든 행동이라 조금 높게 둔다.
WEIGHT = 4
# 한 학원이 다른 신호를 전부 눌러서는 안 된다(actions.CAP 과 같은 뜻).
CAP = 30
# PostgREST 는 한 번에 1,000행까지 준다. 넘으면 이어 받는다.
PAGE = 1000
MAX_PAGES = 50


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
    }


def _rows() -> list[dict]:
    """버리지 않은 제보의 (학원, 기기) 쌍. 실패하면 **통째로** 빈 목록이다 —
    절반만 받은 것으로 세면 그 절반이 사실처럼 읽힌다."""
    if not config.HAS_SUPABASE:
        return []
    out: list[dict] = []
    try:
        for page in range(MAX_PAGES):
            r = requests.get(
                f"{config.SUPABASE_URL}/rest/v1/parent_reports",
                params={
                    "select": "academy_key,device_hash,status",
                    "status": "neq.discarded",
                    "order": "id",
                    "limit": PAGE,
                    "offset": page * PAGE,
                },
                headers=_headers(), timeout=20)
            if r.status_code != 200:
                # 표가 아직 없을 때(마이그레이션 미적용)도 여기로 온다.
                print(f"  ! 학부모 제보: 읽지 못함(HTTP {r.status_code}) — "
                      "이번 회차는 이 신호 없이 진행")
                return []
            batch = r.json()
            if not isinstance(batch, list):
                raise ValueError("목록이 아닌 응답")
            out.extend(row for row in batch if isinstance(row, dict))
            if len(batch) < PAGE:
                break
    except (requests.RequestException, ValueError) as e:
        print(f"  ! 학부모 제보: 읽지 못함({type(e).__name__}) — "
              "이번 회차는 이 신호 없이 진행")
        return []
    return out


def counts(rows: list[dict]) -> dict[str, int]:
    """학원 id → 서로 다른 기기 수. 버린 답(discarded)은 세지 않는다.

    서버가 이미 걸러 주지만 여기서도 한 번 더 본다 — 조회 조건이 바뀌어도
    버린 답이 신호로 새지 않게.
    """
    devices: dict[str, set[str]] = {}
    for row in rows:
        if row.get("status") == "discarded":
            continue
        key = str(row.get("academy_key") or "").strip()
        device = str(row.get("device_hash") or "").strip()
        if key and device:
            devices.setdefault(key, set()).add(device)
    return {k: len(v) for k, v in devices.items()}


def load() -> dict[str, int]:
    """학원 id → 제보한 기기 수. 못 읽으면 빈 dict."""
    return counts(_rows())


def add_to(want: dict[str, int]) -> int:
    """수집 수요 신호(want)에 제보를 보탠다. 보탠 학원 수를 돌려준다.

    여기가 이 신호의 **유일한** 출구다. 점수·코호트·순위 어디에도 안 간다.
    """
    told = load()
    for aid, n in told.items():
        want[aid] = want.get(aid, 0) + min(CAP, WEIGHT * n)
    if told:
        print(f"  학부모 제보: {len(told):,}곳 (수집 우선순위에만 반영 · 점수 무관)")
    return len(told)
