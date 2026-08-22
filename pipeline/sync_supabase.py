#!/usr/bin/env python3
"""파이프라인 산출물을 Supabase 로 업서트한다.

    python pipeline/sync_supabase.py

SUPABASE_URL / SUPABASE_SERVICE_KEY 가 없으면 아무것도 하지 않고 종료한다.
PostgREST 만 쓰므로 supabase-py 의존성이 없다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edutree import config  # noqa: E402

BATCH = 200


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def upsert(table: str, rows: list[dict], on_conflict: str) -> None:
    if not rows:
        return
    url = f"{config.SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        resp = requests.post(url, headers=_headers(), data=json.dumps(chunk), timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"{table} 업서트 실패 {resp.status_code}: {resp.text[:400]}")
    print(f"  {table}: {len(rows)}행")


def load(name: str):
    return json.loads((config.EXPORT_DIR / name).read_text(encoding="utf-8"))


def main() -> None:
    if not config.HAS_SUPABASE:
        print("Supabase 자격 증명이 없습니다. 건너뜁니다.")
        return

    regions = load("regions.json")
    tree = load("techtree.json")
    academies = load("academies.json")

    upsert("regions", [{
        "id": r["id"], "name_ko": r["name_ko"], "name_en": r["name_en"],
        "sigungu": r["sigungu"], "dong_list": r["dong_list"],
        "atpt_code": r["atpt_code"], "tagline": r.get("tagline"),
        "sort_order": r.get("sort_order", 0),
    } for r in regions], on_conflict="id")

    upsert("tracks", [{
        "id": t["id"], "subject": t["subject"], "grade_band": t["grade_band"],
        "title": t["title"], "summary": t.get("summary"),
        "sort_order": t.get("sort_order", 0),
    } for t in tree["tracks"]], on_conflict="id")

    upsert("stages", [{
        "id": s["id"], "track_id": t["id"], "title": s["title"],
        "subtitle": s.get("subtitle"), "goal": s.get("goal"),
        "exit_criteria": s.get("exit_criteria"),
        "typical_grade_min": s["grade"][0], "typical_grade_max": s["grade"][1],
        "depth": s.get("depth", 0), "lane": s.get("lane", 0),
    } for t in tree["tracks"] for s in t["stages"]], on_conflict="id")

    upsert("stage_edges", [{
        "from_stage_id": e[0], "to_stage_id": e[1],
        "condition_text": e[2] if len(e) > 2 else None,
        "edge_type": e[3] if len(e) > 3 else "standard",
    } for t in tree["tracks"] for e in t.get("edges", [])],
        on_conflict="from_stage_id,to_stage_id")

    # 학원: aca_asnum 이 있으면 그걸로, 없으면(시드) 이름으로 충돌 해결
    verified = [a for a in academies if a.get("isVerified")]
    print(f"  검증된 학원 {len(verified)} / 전체 {len(academies)}")

    upsert("academies", [{
        "aca_asnum": a["id"] if a.get("isVerified") else None,
        "name": a["name"],
        "name_normalized": a["id"],
        "aliases": a.get("aliases", []),
        "region_id": a.get("regionId"),
        "reg_stttus_nm": a.get("registrationStatus"),
        "estbl_ymd": a.get("establishedOn"),
        "tofor_smtot": a.get("capacity"),
        "thcc_ctnt": a.get("tuitionRaw"),
        "tuition_monthly_krw": a.get("tuitionMonthly"),
        "road_address": a.get("address"),
        "tel": a.get("tel"),
        "subjects": a.get("subjects", []),
        "grade_bands": a.get("gradeBands", []),
        "is_verified": a.get("isVerified", False),
    } for a in academies], on_conflict="aca_asnum")

    print("\n주의: scores / academy_stages 업서트는 academies 의 uuid 가 필요합니다.")
    print("      최초 1회 동기화 후 name_normalized 로 id 를 조회해 연결하세요.")
    print("      (자세한 절차는 docs/SETUP.md 6단계 참고)")


if __name__ == "__main__":
    main()
