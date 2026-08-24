"""지점 판별 — 같은 브랜드의 어느 지점 이야기인가.

유명 학원은 전국에 지점이 있다. '정상어학원'은 우리 4개 권역에만 5곳이고
분당·평촌에도 있다. 그런데 수집은 학원 단위라, '분당 정상어학원 레테 후기'가
대치 정상어학원의 근거로 붙어 버린다. 실측에서 대치에이프릴어학원 언급
377건 중 60건이 타 지역 글이었다.

규칙은 둘이다.

  1. **글이 지역을 밝히면 그 권역 지점만** 근거로 삼는다.
     '목동 정상어학원' 후기는 대치 지점의 근거가 아니다.
     우리 4개 권역이 아닌 곳(분당·평촌…)을 가리키면 어디에도 안 붙인다.

  2. **글이 지역을 밝히지 않으면 걸리는 지점 전부**에 똑같이 붙인다.
     그냥 '정상어학원 레벨테스트 후기'는 어느 지점인지 알 수 없다.
     한 곳에만 몰아주면 그건 추측이고, 버리면 브랜드 전체의 근거가 사라진다.
     양쪽 다 사실보다 나쁘다 — 알 수 없으면 알 수 있는 만큼만 말한다.

★ 지역 단정은 **글이 말한 것**만 쓴다. 검색 질의어에 지역이 들어 있어도
  그건 우리가 넣은 말이지 글쓴이가 쓴 말이 아니다.
"""
from __future__ import annotations

from collections import defaultdict

from . import analyze, dedupe

# 이 길이 미만의 브랜드 토큰은 지점 묶음에 쓰지 않는다. 짧은 토큰은
# 서로 무관한 학원을 우연히 잇는다.
MIN_TOKEN = 3


def sibling_key(academy: dict) -> str | None:
    """같은 브랜드의 지점들이 공유하는 키.

    큐레이션 브랜드명이 있으면 그것이 가장 정확하다. 없으면 이름에서
    지역·업종어를 뗀 토큰을 쓴다 — '대치에이프릴어학원'과
    '서초에이프릴어학원'이 모두 '에이프릴'이 된다.
    """
    brand = (academy.get("brand") or "").strip()
    if brand:
        return f"brand:{brand}"
    token = dedupe.brand_token(academy.get("name") or "")
    return f"token:{token}" if len(token) >= MIN_TOKEN else None


def sibling_map(academies: list[dict]) -> dict[str, list[dict]]:
    """학원 id → 같은 브랜드의 **다른 권역** 지점들.

    같은 권역 안의 여러 관은 이미 dedupe 가 하나로 묶었다. 여기서 다루는
    것은 권역을 건너뛴 지점이다.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for a in academies:
        key = sibling_key(a)
        if key:
            groups[key].append(a)

    out: dict[str, list[dict]] = {}
    for rows in groups.values():
        if len(rows) < 2:
            continue
        for a in rows:
            others = [b for b in rows
                      if b["id"] != a["id"]
                      and b.get("region_id") != a.get("region_id")]
            if others:
                out[a["id"]] = others
    return out


# 구(區) 이름은 변별어가 못 된다. 반포동·방배동이 모두 서초구라,
# '서초 시매쓰' 라는 글을 방배점 것으로만 치면 반포점 근거가 통째로
# 날아간다(실측 135건 → 62건). 동네 이름만 쓴다.
BROAD_WORDS = frozenset({"강남", "서초", "송파", "양천", "강남구"})


def locality_words(academy: dict) -> set[str]:
    """이 지점을 가리키는 동네 말. 법정동과 이름에서 뽑는다.

    같은 학군 안에도 지점이 둘 이상인 브랜드가 있다. 시매쓰는 반포점과
    방배점이 모두 '반포' 학군이라 권역만으로는 갈리지 않는다.
    실측: 방배점 수집분 415건 중 120건이 제목에 '반포' 가 든 반포점 글이었다.
    """
    words: set[str] = set()
    vocab = [w for ws in analyze.REGION_WORDS.values() for w in ws
             if w not in BROAD_WORDS]
    dong = (academy.get("dong") or "").rstrip("동")
    if dong and dong not in BROAD_WORDS:
        words.add(dong)
    name = academy.get("name") or ""
    for w in vocab:
        if w in name:
            words.add(w)
    return words


def apply(mentions: list[dict], academies: list[dict],
          candidates: dict[str, set[str]],
          generic: dict[str, bool],
          rivals: set[str]) -> tuple[list[dict], dict[str, int]]:
    """권역 규칙을 적용한 언급 목록과 집계를 돌려준다."""
    home = {a["id"]: a.get("region_id") for a in academies}
    siblings = sibling_map(academies)
    by_id = {a["id"]: a for a in academies}

    # 같은 학군 안 형제 지점 — 권역 판별로는 갈리지 않는다. 동네 말로 가른다.
    local: dict[str, set[str]] = {}
    same_region: dict[str, list[dict]] = defaultdict(list)
    for a in academies:
        key = sibling_key(a)
        if key:
            same_region[(key, a.get("region_id"))].append(a)
    for rows in same_region.values():
        if len(rows) < 2:
            continue
        mine = {a["id"]: locality_words(a) for a in rows}
        for a in rows:
            others: set[str] = set()
            for b in rows:
                if b["id"] != a["id"]:
                    others |= mine[b["id"]]
            # 형제만 가진 말이 곧 '나는 아니다' 의 신호다.
            local[a["id"]] = others - mine[a["id"]]

    kept: list[dict] = []
    seen: set[tuple[str, str]] = set()
    stats = {"elsewhere": 0, "other_region": 0, "shared": 0, "sibling": 0,
             "branches": len(siblings)}

    for m in mentions:
        key = m.get("academy_key")
        pair = (m.get("url_hash", ""), key or "")
        if pair in seen:
            continue
        seen.add(pair)

        # ★ 제목이 지역을 말하면 제목만 본다.
        #   본문의 지역명은 남의 학원 이름에 박혀 있는 경우가 많다.
        #   '세종 엄마표영어 …' 글이 본문의 '대치M수학' 때문에 대치 근거로
        #   잡혔다. 제목은 글쓴이가 그 글을 무엇이라 부르는지이므로 더 세다.
        t_ours, t_other = analyze.region_hints(m.get("title", ""))

        # 제목에 권역 밖 지역이 있으면 그쪽 지점 글이다. 제목에 우리 권역
        # 말이 함께 있어도 마찬가지다 — 그 말은 대개 브랜드에 박힌 것이다.
        # '[송도 논술 학원] 대치메이드학원 송도점' 은 송도 글이지 대치 글이
        # 아니다. 여기서 '대치'는 지역이 아니라 학원 이름의 일부다.
        if t_other:
            stats["other_region"] += 1
            continue

        ours, other = t_ours, False
        if not ours:
            ours, other = analyze.region_hints(
                f"{m.get('title', '')} {m.get('snippet', '')}")
        mine = home.get(key)

        # 같은 학군 안 형제 지점의 동네 이름이 제목에 있으면 그쪽 글이다.
        theirs = local.get(key or "")
        if theirs:
            title = analyze._norm(m.get("title", ""))
            if any(analyze._norm(w) in title for w in theirs):
                stats["sibling"] += 1
                continue

        if ours:
            # 지역을 밝힌 글. 내 권역이 아니면 내 근거가 아니다.
            if mine not in ours:
                stats["elsewhere"] += 1
                continue
            m["branch_basis"] = "region"
            kept.append(m)
            continue

        if other:
            # 우리 권역 밖의 지점 이야기다.
            stats["other_region"] += 1
            continue

        # 지역을 알 수 없는 글. 걸리는 지점 전부의 근거로 삼는다.
        m["branch_basis"] = "brand"
        kept.append(m)

        for sib in siblings.get(key, []):
            pair = (m.get("url_hash", ""), sib["id"])
            if pair in seen:
                continue
            # 그 지점 이름으로도 실제로 걸리는 글인지 다시 확인한다.
            if not analyze.is_relevant(m, candidates.get(sib["id"], set()),
                                       generic.get(sib["id"], False), rivals):
                continue
            seen.add(pair)
            copy = dict(m)
            copy["academy_key"] = sib["id"]
            copy["academy_name"] = sib.get("name")
            copy["region_id"] = sib.get("region_id")
            copy["branch_basis"] = "brand"
            kept.append(copy)
            stats["shared"] += 1

    _ = by_id
    return kept, stats
