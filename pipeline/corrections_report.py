#!/usr/bin/env python3
"""정정 요청 처리 대장.

접수는 앱이 하고(로그인 불요), 검토는 사람이 한다. 그 사이를 잇는 도구다.
매일 열어 볼 화면이 아니라 **미처리 건이 있을 때만** 알려 주는 쪽이 맞다.

  python3 pipeline/corrections_report.py            # 미처리 목록
  python3 pipeline/corrections_report.py --all      # 전체
  python3 pipeline/corrections_report.py --done ID --note "교습비 반영"

읽기·수정은 service_role 키로만 된다(RLS 가 접수만 열어 두었다).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
KIND = {"fix": "정정", "claim": "관계자 확인", "remove": "삭제 요청"}


def _req(method: str, path: str, **kw):
    if not (URL and KEY):
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY 가 .env 에 없습니다.")
    headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
               "Content-Type": "application/json", "Prefer": "return=representation"}
    r = requests.request(method, f"{URL}/rest/v1/{path}", headers=headers,
                         timeout=30, **kw)
    if r.status_code >= 300:
        sys.exit(f"{r.status_code}: {r.text[:300]}")
    return r.json() if r.text else []


def show(rows: list[dict]) -> None:
    if not rows:
        print("미처리 정정 요청 없음.")
        return
    print(f"\n미처리 {len(rows)}건\n" + "─" * 72)
    for r in rows:
        print(f"[{r['id'][:8]}] {r.get('academy_name') or r.get('academy_key')}"
              f"  · {KIND.get(r.get('claim_type'), r.get('claim_type'))}"
              f"  · {(r.get('created_at') or '')[:10]}")
        print(f"    요청자: {r.get('requester') or '미기재'}   회신: {r.get('contact')}")
        body = (r.get("body") or "").replace("\n", "\n           ")
        print(f"    내용: {body}\n")
    print("처리: python3 pipeline/corrections_report.py --done <ID앞8자> --note '...'")


DISPUTE_REASON = {
    "not_true": "사실 아님", "outdated": "지금은 다름",
    "other_academy": "다른 학원 이야기", "ad": "광고", "other": "기타",
}


def show_disputes(show_all: bool = False) -> list[dict]:
    """미처리 주장 이의. 근거 한 줄에 대한 이의라 정정 요청보다 잘다.

    같은 주장에 여러 건이 들어오면 한 줄로 묶어 보여준다 — 쪼개 보면
    같은 판단을 여러 번 하게 된다.
    """
    q = "claim_disputes?select=*&order=created_at.desc"
    if not show_all:
        q += "&status=eq.open"
    rows = _req("GET", q)
    if not rows:
        print("미처리 주장 이의 없음.")
        return []

    by_claim: dict[str, list[dict]] = {}
    for r in rows:
        by_claim.setdefault(r["claim_id"], []).append(r)
    print(f"\n미처리 주장 이의 {len(rows)}건 ({len(by_claim)}개 주장)\n" + "─" * 72)
    for cid, group in by_claim.items():
        head = group[0]
        reasons = " · ".join(sorted({DISPUTE_REASON.get(g.get("reason"), "?")
                                     for g in group}))
        print(f"[{cid[:10]}] {head.get('academy_key')}  · {head.get('claim_kind')}"
              f"  · 이의 {len(group)}건  · {reasons}")
        if head.get("quote"):
            print(f"    근거: {head['quote'][:70]}")
        for g in group:
            if g.get("note"):
                print(f"    메모: {g['note'][:70]}")
    print("\n취소하려면 claim_verdicts 에 (claim_id, academy_key, reason) 을 넣는다.")
    print("판정을 지우면 다음 실행에서 그 주장이 그대로 되살아난다.")
    return rows


BAND = {"elem_low": "예비초~초3", "elem_high": "초4~초6",
        "middle": "중등", "high": "고등"}


def show_reservations(show_all: bool = False) -> list[dict]:
    """레벨테스트 예약 요청. 운영자가 학원에 연락해 잇고 연락처로 회신한다.

    접수는 확정이 아니다 — 여기 남아 있는 동안은 학부모가 답을 기다리는
    중이다. 정정 요청과 같은 창구이고 같은 알림을 탄다.
    """
    q = "test_reservations?select=*&order=created_at.desc"
    if not show_all:
        q += "&status=eq.open"
    rows = _req("GET", q)
    if not rows:
        print("미처리 레벨테스트 예약 요청 없음.")
        return []
    print(f"\n미처리 예약 요청 {len(rows)}건\n" + "─" * 72)
    for r in rows:
        who = " · ".join(x for x in (BAND.get(r.get("child_band") or ""),
                                     r.get("subject")) if x)
        print(f"[{r['id'][:8]}] {r.get('academy_name')}  · {who or '학년 미기재'}"
              f"  · {(r.get('created_at') or '')[:10]}")
        print(f"    보호자: {r.get('parent_name') or '미기재'}   회신: {r.get('contact')}")
        if r.get("preferred"):
            print(f"    희망 일시: {r['preferred']}")
        if r.get("note"):
            print(f"    메모: {(r['note'] or '')[:100]}")
    print("처리: python3 pipeline/corrections_report.py --reservation-done <ID앞8자> --note '...'")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--done", metavar="ID")
    ap.add_argument("--reservation-done", metavar="ID",
                    help="예약 요청을 처리 완료로 닫는다 (id 앞자리)")
    ap.add_argument("--note", default="")
    ap.add_argument("--fail-on-open", action="store_true",
                    help="미처리가 있으면 종료 코드 2 (CI 알림용)")
    a = ap.parse_args()

    if a.reservation_done:
        found = [r for r in _req("GET", "test_reservations?select=id,academy_name")
                 if str(r["id"]).startswith(a.reservation_done)]
        if len(found) != 1:
            sys.exit(f"'{a.reservation_done}' 로 {len(found)}건이 잡혔습니다. "
                     "id 앞자리를 더 길게 주세요.")
        rows = _req("PATCH", f"test_reservations?id=eq.{found[0]['id']}",
                    json={"status": "done", "handler_note": a.note,
                          "handled_at": "now()"})
        print(f"처리 완료: {found[0].get('academy_name')} ({len(rows)}건)")
        return

    if a.done:
        # id 가 uuid 라 like 를 못 쓴다. 앞자리로 찾아 전체 id 를 구한 뒤
        # 정확히 지정한다. 실수로 여러 건을 한꺼번에 닫지 않도록 1건일
        # 때만 처리한다.
        # uuid 는 like 도, 범위 비교도 다루기 번거롭다. 목록을 받아
        # 파이썬에서 앞자리를 맞춘다 — 미처리 건이 수천 건이 될 일은 없다.
        found = [r for r in _req("GET", "corrections?select=id,academy_name")
                 if str(r["id"]).startswith(a.done)]
        if len(found) != 1:
            sys.exit(f"'{a.done}' 로 {len(found)}건이 잡혔습니다. "
                     "id 앞자리를 더 길게 주세요.")
        rows = _req("PATCH", f"corrections?id=eq.{found[0]['id']}",
                    json={"status": "done", "resolution": a.note,
                          "resolved_at": "now()"})
        print(f"처리 완료: {found[0].get('academy_name')} ({len(rows)}건)")
        return

    q = "corrections?select=*&order=created_at.desc"
    if not a.all:
        # 미처리 상태가 둘이다. 01_schema 의 기본값은 'received' 이고
        # 06 에서 policy 를 손대며 'open' 을 썼다. 둘 다 미처리로 본다 —
        # 한쪽만 보다가 접수된 요청을 통째로 못 봤다.
        q += "&status=in.(received,open,reviewing)"
    rows = _req("GET", q)
    show(rows)
    # 주장 이의도 같은 창구다. 접수만 되고 아무도 안 보면 정정 요청이
    # 조용히 묻히던 것과 똑같은 일이 반복된다.
    disputes = show_disputes(a.all)
    reservations = show_reservations(a.all)
    # 미처리가 있으면 0 이 아닌 코드로 끝낸다. 야간 작업이 실패로 표시되고
    # 깃허브가 알림을 보낸다 — 로그에만 찍히면 아무도 안 본다.
    if (rows or disputes or reservations) and a.fail_on_open:
        sys.exit(2)


if __name__ == "__main__":
    main()
