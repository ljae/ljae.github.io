"""지식 그래프 감사 — 노드(학원)와 엣지(후기→학원)의 무결성을 매 실행 증명한다.

이 시스템의 그래프는 이렇다.

  노드: 학원. id = NEIS 학원지정번호(통합 시 가장 오래된 등록의 것).
        registration_ids 가 흡수된 등록들을 담는다.
  엣지: 언급(후기) → 학원. academy_key 가 가리키고, branch_basis 가
        연결의 근거를 밝힌다:
          direct       그 학원을 수집해 이름 매칭으로 걸림
          region       글이 그 권역을 밝힘
          brand        지점 불명 → 브랜드 형제들에 공유
          reclassified 운영자가 재분류로 지목

무결성은 만들 때 한 번 보장하는 것이 아니라 **매 실행 다시 증명**해야
한다. 통합 규칙은 계속 바뀌고(3글자 겹침 → 접두사 → 관 기준…), 바뀐
규칙은 이미 묶인 그룹을 다시 심사하지 않으면 옛 오결합이 화석이 된다.
실제로 그렇게 화석이 될 뻔한 것들: 예설라센트럴원+파피루스문해원(건물명),
뉴클리+뉴클리온(접미사), 책읽기+리딩엠(대표명).
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import dedupe


def _connected(name: str, others: list[str]) -> bool:
    """이 이름이 묶음의 다른 이름 중 하나와라도 정당하게 이어지는가.

    정당한 근거는 통합이 실제로 쓰는 세 가지뿐이다:
    브랜드 접두사 일치, 관(館) 표기만 다른 같은 이름, 완전 동일.
    """
    for o in others:
        if name == o or dedupe.same_academy(name, o):
            return True
        hk_a, hk_b = dedupe.hall_key(name), dedupe.hall_key(o)
        if hk_a and hk_a == hk_b:
            return True
    return False


def audit(academies: list[dict], mentions: list[dict]) -> dict:
    """(위반 목록, 통계) 를 찍고 돌려준다."""
    problems: list[str] = []

    # ── 노드: id 유일, 등록 서로소 ────────────────────────────────
    ids = Counter(a["id"] for a in academies)
    for aid, n in ids.items():
        if n > 1:
            problems.append(f"학원 id 중복: {aid} × {n}")

    owner: dict[str, str] = {}
    for a in academies:
        for rid in a.get("registration_ids") or [a["id"]]:
            rid = str(rid)
            if rid in owner and owner[rid] != a["id"]:
                problems.append(
                    f"등록 {rid} 이중 흡수: {owner[rid]} 와 {a['id']}")
            owner[rid] = a["id"]

    # ── 노드: 결합 재검증 — 서로 다른 두 학원이 합쳐지지 않았는가 ──
    # 묶음의 각 이름이 나머지와 정당한 근거로 이어져야 한다. 통합 규칙이
    # 바뀌면 여기서 옛 그룹이 다시 심사된다.
    suspect = 0
    for a in academies:
        names = [n for n in (a.get("merged_names") or []) if n]
        if len(names) < 2:
            continue
        for n in names:
            others = [o for o in names if o is not n]
            if not _connected(n, others):
                suspect += 1
                problems.append(
                    f"결합 의심: '{n}' 이 '{a['name']}'({a['id']}) 묶음과 "
                    f"이어지지 않음 — {names[:4]}")
                break

    # ── 엣지: 모든 후기가 실존 학원을 가리키는가 ─────────────────
    node_ids = {a["id"] for a in academies}
    orphan = 0
    basis = Counter()
    for m in mentions:
        if m.get("academy_key") not in node_ids:
            orphan += 1
            if orphan <= 3:
                problems.append(
                    f"고아 엣지: {str(m.get('academy_key'))[:16]} ← "
                    f"{(m.get('title') or '')[:30]}")
        basis[m.get("branch_basis") or "direct"] += 1
    if orphan > 3:
        problems.append(f"고아 엣지 … 외 {orphan - 3}건")

    stats = {
        "nodes": len(academies),
        "registrations": len(owner),
        "edges": len(mentions),
        "orphans": orphan,
        "suspect_merges": suspect,
        "basis": dict(basis),
    }

    basis_str = " · ".join(f"{k} {v:,}" for k, v in sorted(basis.items()))
    if problems:
        print(f"  ! 그래프 점검 위반 {len(problems)}건:")
        for p in problems[:10]:
            print(f"      {p}")
    else:
        print(f"  그래프 점검: 노드 {stats['nodes']:,} (등록 "
              f"{stats['registrations']:,}건 서로소) · 엣지 "
              f"{stats['edges']:,} 전부 연결 ✓  [{basis_str}]")
    return {"problems": problems, **stats}
