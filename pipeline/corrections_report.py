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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--done", metavar="ID")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    if a.done:
        rows = _req("PATCH", f"corrections?id=like.{a.done}*",
                    json={"status": "done", "resolution": a.note,
                          "resolved_at": "now()"})
        print(f"처리 완료: {len(rows)}건")
        return

    q = "corrections?select=*&order=created_at.desc"
    if not a.all:
        q += "&status=eq.open"
    show(_req("GET", q))


if __name__ == "__main__":
    main()
