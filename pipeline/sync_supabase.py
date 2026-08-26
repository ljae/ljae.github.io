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


def prune(table: str, key: str, keep: list[str]) -> None:
    """페이로드에 없는 행을 지운다. **미러는 미러여야 한다.**

    id 만 보고 upsert 하면 옛 행이 영원히 남는다. 실제로 학년 구간을
    가르면서 트랙 id 가 바뀌었는데(math_elementary → math_elem_low·
    math_elem_high) 옛 4행이 남아 `unique (subject, grade_band)` 를
    점유하는 바람에 새 트랙이 들어가지 못했다.

        duplicate key … Key (subject, grade_band)=(math, elem_low) already exists

    FK 가 전부 on delete cascade 라 딸린 stages·edges·academy_stages 도
    함께 지워지고, 바로 뒤 upsert 가 다시 넣는다.
    """
    if not keep:
        return
    quoted = ",".join(f'"{k}"' for k in keep)
    url = f"{config.SUPABASE_URL}/rest/v1/{table}?{key}=not.in.({quoted})"
    resp = requests.delete(url, headers=_headers(), timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f"{table} 정리 실패 {resp.status_code}: {resp.text[:300]}")


def dedupe(rows: list[dict], *keys: str) -> list[dict]:
    """같은 키가 두 번 오면 첫 것만 남긴다.

    한 배치에 같은 키가 두 번 들어가면 Postgres 가 거부한다
    ("ON CONFLICT DO UPDATE command cannot affect row a second time").

    ★ 테크트리에서는 정상적인 일이다. 경계에 걸친 단계(사고력 초1~초4)는
      **두 구간 트랙에 모두** 든다 — 한쪽에서 빼면 길이 끊기기 때문이다.
      실측 49행 중 8개 id 가 그렇다. 그런데 stages 는 track_id 를 하나만
      갖는 표라 그 사실을 담을 수 없다. 앱은 이 표가 아니라 정적 JSON 을
      읽으므로(테크트리 화면은 techtree.json), 미러에서는 첫 트랙에
      매단다. 트랙 순서가 고정이라 결과도 매번 같다.
    """
    if not keys:
        # 키 없이 부르면 모든 행이 같은 빈 키가 되어 한 행만 남는다.
        # 조용히 데이터를 지우느니 여기서 터지는 편이 낫다.
        raise ValueError("dedupe: 키를 하나 이상 주어야 한다")
    seen, out = set(), []
    for r in rows:
        k = tuple(r[x] for x in keys)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


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

    # 옛 트랙을 먼저 치운다. unique(subject, grade_band) 를 점유하고 있어
    # 그대로 두면 새 트랙이 못 들어간다.
    prune("tracks", "id", [t["id"] for t in tree["tracks"]])
    upsert("tracks", [{
        "id": t["id"], "subject": t["subject"], "grade_band": t["grade_band"],
        "title": t["title"], "summary": t.get("summary"),
        "sort_order": t.get("sort_order", 0),
    } for t in tree["tracks"]], on_conflict="id")

    upsert("stages", dedupe([{
        "id": s["id"], "track_id": t["id"], "title": s["title"],
        "subtitle": s.get("subtitle"), "goal": s.get("goal"),
        "exit_criteria": s.get("exit_criteria"),
        "typical_grade_min": s["grade"][0], "typical_grade_max": s["grade"][1],
        "depth": s.get("depth", 0), "lane": s.get("lane", 0),
    } for t in tree["tracks"] for s in t["stages"]], "id"), on_conflict="id")

    upsert("stage_edges", dedupe([{
        "from_stage_id": e[0], "to_stage_id": e[1],
        "condition_text": e[2] if len(e) > 2 else None,
        "edge_type": e[3] if len(e) > 3 else "standard",
    } for t in tree["tracks"] for e in t.get("edges", [])],
        "from_stage_id", "to_stage_id"),
        on_conflict="from_stage_id,to_stage_id")

    # 학원: aca_asnum 이 있으면 그걸로, 없으면(시드) 이름으로 충돌 해결
    verified = [a for a in academies if a.get("isVerified")]
    print(f"  검증된 학원 {len(verified)} / 전체 {len(academies)}")

    # ★ academies 는 **절대 prune 하지 않는다.**
    #   수집 대상 400곳은 회차마다 순환한다(coverage). 이번 회차에 안 뽑힌
    #   학원을 지우면 user_reviews · bookmarks · corrections · score_history
    #   가 전부 on delete cascade 로 함께 사라진다 — 사용자가 쓴 후기와
    #   정정 요청, 그리고 되돌릴 수 없는 순위 이력이다.
    #   미러에 학원이 쌓이는 것은 오류가 아니라 '한 번이라도 평가한 곳'
    #   이라는 뜻이다. tracks 와 대칭으로 보고 prune 을 붙이지 말 것.
    upsert("academies", [{
        "aca_asnum": a["id"] if a.get("isVerified") else None,
        "name": a["name"],
        "name_normalized": a["id"],
        "aliases": a.get("aliases", []),
        "region_id": a.get("regionId"),
        "reg_stttus_nm": a.get("registrationStatus"),
        "estbl_ymd": a.get("establishedOn"),
        "tofor_smtot": a.get("capacity"),
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
