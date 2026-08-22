"""수집 → 분석 → 채점 → 앱 번들(JSON) 내보내기.

두 가지 모드로 동작한다.
  live : .env 에 NEIS/네이버 키가 있으면 실제 수집
  demo : 키가 없으면 결정론적 합성 데이터. 앱은 배너로 '샘플'임을 명시한다.

demo 모드 합성 데이터는 실제 평가가 아니다. 특정 학원을 낮게 보이게 하지
않도록 감성 분포를 양(+)으로 치우치게 만들고, 하위 랭킹 화면은 앱에서
demo 모드일 때 노출하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import analyze, config, scoring
from .neis import match_keys, normalize_name


# ── 학원 로딩 ──────────────────────────────────────────────────────
def load_academies(from_cache: bool = False) -> tuple[list[dict], str]:
    cache = config.CACHE_DIR / "neis_academies.json"
    if from_cache and cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))
        print(f"캐시에서 NEIS {len(rows)}곳 로드")
        return _merge_seed_into_neis(rows), "live"

    if config.HAS_NEIS:
        from . import neis
        print("NEIS 수집 중…")
        rows = neis.fetch_all()
        merged = _merge_seed_into_neis(rows)
        return merged, "live"

    print("NEIS 키 없음 → 시드 학원으로 진행 (demo 모드)")
    return _expand_seed(), "demo"


def _expand_seed() -> list[dict]:
    """브랜드 × 학군 조합을 학원 레코드로 펼친다."""
    regions = {r["id"]: r for r in config.regions()}
    tree = config.techtree()
    stage_track = {s["id"]: t for t in tree["tracks"] for s in t["stages"]}

    out: list[dict] = []
    for brand in config.seed_academies():
        for region_id in brand["regions"]:
            region = regions[region_id]
            display = f"{region['name_ko']} {brand['name']}"
            levels = sorted({stage_track[s]["school_level"] for s in brand["stages"]})
            rec = {
                "aca_asnum": None,
                "name": display,
                "brand": brand["name"],
                "name_normalized": normalize_name(display),
                # 시드에는 지정번호가 없으니 학군+브랜드로 고유 키를 만든다
                "id": f"{region_id}-{normalize_name(brand['name'])}",
                "aliases": brand.get("aliases", []),
                "region_id": region_id,
                "subjects": brand["subjects"],
                "school_levels": levels,
                "stages": brand["stages"],
                "flagship": brand.get("flagship", []),
                "reg_stttus_nm": "정상",
                "le_ord_nm": "보통교과",
                "le_crse_list_nm": "·".join(config.SUBJECTS[s] for s in brand["subjects"]),
                "road_address": f"서울특별시 {region['sigungu']} {region['dong_list'][0]}",
                "is_verified": False,
                "data_source": "seed",
            }
            _synthesize_official_fields(rec)
            out.append(rec)
    return out


def _synthesize_official_fields(rec: dict) -> None:
    """demo 모드용 공시 필드. rng 는 학원명 해시로 고정 — 빌드마다 동일하다."""
    rng = _rng(rec["name"] + "|official")
    rec["tofor_smtot"] = rng.choice([60, 90, 120, 150, 180, 240, 300])
    rec["dtm_rcptn_ablty_nmpr_smtot"] = int(rec["tofor_smtot"] * rng.uniform(0.5, 0.8))
    if rng.random() < 0.75:
        amount = rng.choice([280_000, 320_000, 380_000, 420_000, 480_000, 550_000, 620_000])
        rec["thcc_ctnt"] = f"월 {amount:,}원"
        rec["tuition_monthly_krw"] = amount
    else:
        rec["thcc_ctnt"] = None
        rec["tuition_monthly_krw"] = None
    year = rng.randint(2003, 2022)
    rec["estbl_ymd"] = f"{year}-{rng.randint(1, 12):02d}-01"


def _merge_seed_into_neis(neis_rows: list[dict]) -> list[dict]:
    """NEIS 실데이터에 시드의 테크트리 매핑(stages)을 붙인다.

    NEIS 는 어떤 학원이 어느 단계를 담당하는지 모른다. 그 지식은 큐레이션
    쪽에만 있으므로, 이름 매칭으로 연결한다.
    """
    seed_by_key: dict[str, dict] = {}
    for brand in config.seed_academies():
        for key in match_keys(brand["name"]):
            seed_by_key[key] = brand
        for alias in brand.get("aliases", []):
            for key in match_keys(alias):
                seed_by_key.setdefault(key, brand)

    before = len(neis_rows)
    neis_rows = [r for r in neis_rows
                 if (r.get("realm_sc_nm") or "") in config.ACADEMIC_REALMS]
    print(f"  학술 분야 필터: {before}곳 → {len(neis_rows)}곳 "
          f"(예능·기예·독서실 등 {before - len(neis_rows)}곳 제외)")

    matched = 0
    for row in neis_rows:
        brand = next((seed_by_key[k] for k in match_keys(row["name"]) if k in seed_by_key), None)
        if brand:
            matched += 1
            row["brand"] = brand["name"]
            row["aliases"] = brand.get("aliases", [])
            row["stages"] = brand["stages"]
            row["flagship"] = brand.get("flagship", [])
            row["subjects"] = brand["subjects"]
        else:
            row.setdefault("stages", [])
            row.setdefault("flagship", [])
            row.setdefault("subjects", _infer_subjects(row))
        row.setdefault("school_levels", [])
        row.setdefault("id", row.get("aca_asnum") or f"n-{row['name_normalized']}")
    print(f"  테크트리 매핑: {matched}/{len(neis_rows)}곳이 큐레이션 브랜드와 연결됨")
    return neis_rows


_SUBJECT_HINTS = {
    "math": ("수학", "산수", "사고력", "매쓰", "MATH", "Math"),
    "english": ("영어", "어학", "English", "ENGLISH", "잉글리시", "어학원"),
    "korean": ("국어", "논술", "독서", "문해", "언어"),
    "science": ("과학", "물리", "화학", "생물", "지구과학"),
}


def _infer_subjects(row: dict) -> list[str]:
    """과목 추론.

    학원명이 가장 정확한 신호다('○○수학학원'). 교습과정은 '보습'처럼
    과목을 특정하지 않는 값이 많아 보조로만 쓴다. 아무것도 안 잡히면
    'etc'(종합·보습)로 둔다 — 억지로 배정하지 않는다.
    """
    name = str(row.get("name") or "")
    found = [s for s, hints in _SUBJECT_HINTS.items() if any(h in name for h in hints)]
    if found:
        return found

    course = " ".join(str(row.get(k) or "") for k in ("le_crse_list_nm", "le_crse_nm"))
    found = [s for s, hints in _SUBJECT_HINTS.items() if any(h in course for h in hints)]
    if found:
        return found

    if (row.get("realm_sc_nm") or "") == "국제화" or "외국어" in course:
        return ["english"]
    return ["etc"]


# ── 언급 로딩 ──────────────────────────────────────────────────────
def select_for_mentions(academies: list[dict]) -> tuple[list[dict], list[dict]]:
    """네이버 수집 대상을 예산 안에서 고른다.

    학군마다 예산을 똑같이 나눈다. 전체를 점수순으로 자르면 대치가 예산을
    독식해 다른 학군 랭킹이 비어버린다.

    우선순위
      1. 큐레이션 테크트리에 매핑된 학원 (테크트리 화면이 이들에 의존한다)
      2. 과목이 특정된 학원 (종합·보습보다 커뮤니티 언급이 잡히기 쉽다)
      3. 정원이 큰 학원 (규모가 클수록 언급이 많다는 대리 지표)

    고르지 못한 학원은 점수를 계산하지 않는다. 언급 0건으로 채점하면
    '평가했는데 낮은 점수'처럼 보이지만 실제로는 '보지도 않은' 것이라
    그렇게 표시하는 편이 정직하다.
    """
    budget = config.NAVER_MAX_ACADEMIES
    regions = [r["id"] for r in config.regions()]
    per_region = max(1, budget // max(1, len(regions)))

    def priority(a: dict):
        return (
            0 if a.get("stages") else 1,
            0 if (a.get("subjects") or ["etc"]) != ["etc"] else 1,
            -(a.get("tofor_smtot") or 0),
        )

    selected, skipped = [], []
    for region_id in regions:
        rows = [a for a in academies if a.get("region_id") == region_id]
        rows.sort(key=priority)
        selected.extend(rows[:per_region])
        skipped.extend(rows[per_region:])

    other = [a for a in academies if a.get("region_id") not in regions]
    skipped.extend(other)

    print(f"  네이버 수집 대상 {len(selected)}곳 선별 "
          f"(학군당 {per_region}곳, 예산 {budget})")
    print(f"  미수집 {len(skipped)}곳은 등록부에만 남기고 점수를 매기지 않습니다")
    return selected, skipped


def load_mentions(academies: list[dict], mode: str,
                  with_cafe: bool = False,
                  from_cache: bool = False) -> list[dict]:
    mentions: list[dict] = []

    cache = config.CACHE_DIR / "naver_mentions.json"
    if from_cache and cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))
        print(f"캐시에서 언급 {len(rows):,}건 로드 (API 호출 없음)")
        return rows

    if config.HAS_NAVER:
        from . import naver
        print("네이버 검색 API 수집 중…")
        region_names = {r["id"]: r["name_ko"] for r in config.regions()}
        mentions.extend(naver.collect_all(academies, region_names))
    else:
        print("네이버 키 없음 → 합성 언급 생성 (demo 모드)")
        mentions.extend(_synthesize_mentions(academies))

    # 카페 심층 수집은 선택 사항이다. 꺼져 있으면 빈 목록이 오고 그대로 진행한다.
    if with_cafe:
        from . import cafe_local
        print("카페 로컬 모듈 시도 중…")
        extra = cafe_local.try_collect(academies)
        seen = {m["url_hash"] for m in mentions}
        mentions.extend(m for m in extra if m["url_hash"] not in seen)

    return mentions


def _rng(seed_text: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16))


_DEMO_SNIPPETS = [
    "우리 아이 {m}개월째 다니는 중인데 {aspect} 부분이 특히 만족스러워요.",
    "{grade} 올라가면서 옮겼는데 확실히 체계적이라 좋았어요.",
    "레벨테스트 보고 들어갔습니다. 반 편성이 촘촘한 편이에요.",
    "숙제량이 좀 있는 편이지만 그만큼 탄탄하게 잡아줍니다.",
    "선생님이 꼼꼼하게 봐주셔서 성적 올랐어요. 상담도 자주 해주시고요.",
    "대기 걸어두고 두 달 만에 자리 났어요. 인기 많은 곳이라 서둘러야 해요.",
    "가격은 좀 있는 편인데 관리 생각하면 괜찮은 것 같아요.",
    "커리큘럼이 잘 짜여 있어서 진도 따라가기 좋았습니다.",
    "우리 아이랑은 조금 안 맞아서 한 학기 하고 그만뒀어요.",
    "설명이 이해가 잘 된다고 하네요. 재밌게 다니는 중입니다.",
]
_DEMO_ASPECTS = ["선생님", "관리", "커리큘럼", "숙제", "상담", "반 편성"]


def _synthesize_mentions(academies: list[dict]) -> list[dict]:
    """결정론적 합성 언급.

    감성 분포를 양(+)으로 치우치게 둔다. 샘플 데이터로 특정 실명 학원이
    나쁘게 보이는 상황을 만들지 않기 위한 의도적 선택이다.
    """
    today = date.today()
    out: list[dict] = []
    for a in academies:
        rng = _rng(a["name"] + "|mentions")
        n = rng.choice([4, 8, 12, 18, 24, 31, 38, 46, 55])
        for i in range(n):
            days_ago = int(abs(rng.gauss(0, 1)) * 200) % 700
            posted = today - timedelta(days=days_ago)
            has_date = rng.random() < 0.55       # 카페글은 날짜가 없다
            body = rng.choice(_DEMO_SNIPPETS).format(
                m=rng.randint(2, 30),
                aspect=rng.choice(_DEMO_ASPECTS),
                grade=config.grade_label(rng.randint(1, 12)),
            )
            source = rng.choice(["naver_cafe", "naver_cafe", "naver_blog", "naver_kin"])
            is_ad = rng.random() < 0.12
            if is_ad:
                body = "★신규 오픈 이벤트★ 선착순 무료체험 상담문의 카톡 주세요 #학원 #추천 #할인 #최고 #이벤트"
            out.append({
                "source": source,
                "source_url": f"https://demo.local/{a['id']}/{i}",
                "url_hash": hashlib.sha256(f"{a['name']}{i}".encode()).hexdigest()[:32],
                "author_hash": hashlib.sha256(f"author{rng.randint(1, 400)}".encode()).hexdigest()[:32],
                "title": f"{a.get('brand', a['name'])} 후기",
                "snippet": body,
                "posted_at": posted.isoformat() if has_date else None,
                "academy_key": a["id"],
                "academy_name": a["name"],
                "region_id": a.get("region_id"),
                "is_demo": True,
            })
    return out


# ── 조립 ───────────────────────────────────────────────────────────
def run(with_cafe: bool = False, from_cache: bool = False,
        skip_blog_text: bool = False) -> dict:
    academies, mode = load_academies(from_cache=from_cache)
    print(f"학원 {len(academies)}곳 · 모드 {mode}")

    if mode == "live":
        evaluated, registry_only = select_for_mentions(academies)
    else:
        evaluated, registry_only = academies, []

    mentions = load_mentions(evaluated, mode, with_cafe=with_cafe,
                             from_cache=from_cache)

    # 블로그 본문 보강 — 관련성 게이트보다 먼저 한다.
    # 스니펫에는 학원명이 안 나와도 본문에는 나오는 글이 많아서, 순서가
    # 바뀌면 멀쩡한 근거를 게이트에서 버리게 된다.
    if mode == "live" and not skip_blog_text:
        from . import blog
        filled = blog.enrich(mentions)
        print(f"  블로그 본문 반영 {filled:,}건")

    # 날짜 보강 — 순서대로 신뢰도가 높은 출처를 먼저 쓴다.
    if mode == "live":
        from . import cafe_dates, discovery
        got = cafe_dates.apply(mentions)
        if got:
            print(f"  카페 목록 페이지에서 날짜 {got:,}건 보강")
        store = discovery.update(mentions)
        new = discovery.apply(mentions, store)
        if new:
            print(f"  발견 시점으로 날짜 {new:,}건 보강")
        print(f"  날짜 확보율: {cafe_dates.coverage(mentions)}")

    # 관련성 게이트 — 학원명이 실제로 등장하는 글만 근거로 인정한다.
    candidates = {a["id"]: analyze.name_candidates(a) for a in evaluated}
    before = len(mentions)
    mentions = [m for m in mentions
                if analyze.is_relevant(m, candidates.get(m["academy_key"], set()))]
    dropped = before - len(mentions)
    if before:
        print(f"  관련성 게이트: {before:,}건 → {len(mentions):,}건 "
              f"(학원명 미등장 {dropped:,}건 제외, {dropped/before*100:.0f}%)")

    mentions = [analyze.analyze(m) for m in mentions]
    mentions = analyze.flag_repeat_authors(mentions)
    print(f"언급 {len(mentions)}건 분석 완료 "
          f"(스팸 배제 {sum(1 for m in mentions if m['is_excluded'])}건)")

    by_key: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        by_key[m["academy_key"]].append(m)

    cohorts = scoring.build_cohorts(evaluated, by_key)
    scores = {}
    for a in evaluated:
        s = scoring.compute(a, by_key.get(a["id"], []),
                            scoring.cohort_for(a, cohorts))
        scores[a["id"]] = s

    _assign_ranks(evaluated, scores)
    export(evaluated, registry_only, mentions, scores, cohorts, mode)
    return {
        "mode": mode,
        "evaluated": len(evaluated),
        "registry": len(evaluated) + len(registry_only),
        "mentions": len(mentions),
        "ranked": sum(1 for s in scores.values() if s["is_ranked"]),
    }


def _assign_ranks(academies: list[dict], scores: dict) -> None:
    by_region: dict[str, list] = defaultdict(list)
    for a in academies:
        s = scores[a["id"]]
        if s["is_ranked"]:
            by_region[a["region_id"]].append((s["total"], a["id"]))
    for region_id, rows in by_region.items():
        # 동점일 때도 매 실행 같은 순서가 나오도록 (총점 내림차순, id 오름차순)
        rows.sort(key=lambda t: (-t[0], t[1]))
        for rank, (_, key) in enumerate(rows, start=1):
            scores[key]["rank_in_region"] = rank
        for _, key in rows:
            scores[key]["region_ranked_count"] = len(rows)


def export(evaluated, registry_only, mentions, scores, cohorts, mode) -> None:
    out = config.EXPORT_DIR
    regions = config.regions()
    tree = config.techtree()

    # 언급은 학원별 상위 근거 몇 건만 앱에 싣는다(원문 전재 금지 · 번들 크기).
    top_evidence: dict[str, list] = defaultdict(list)
    for m in sorted(mentions, key=lambda x: -x.get("credibility", 0)):
        key = m["academy_key"]
        if len(top_evidence[key]) < 5 and not m["is_excluded"]:
            top_evidence[key].append({
                "source": m["source"],
                "url": m["source_url"],
                "title": m["title"],
                "snippet": m["snippet"][:120],
                "posted_at": m["posted_at"],
                "sentiment": m["sentiment"],
                "credibility": m["credibility"],
            })

    def base(a: dict) -> dict:
        return {
            "id": a["id"],
            "name": a["name"],
            "regionId": a.get("region_id"),
            "dong": a.get("dong"),
            "subjects": a.get("subjects", []),
            "address": a.get("road_address"),
            "capacity": a.get("tofor_smtot"),
            "tuitionMonthly": a.get("tuition_monthly_krw"),
            "registrationStatus": a.get("reg_stttus_nm"),
            "isVerified": a.get("is_verified", False),
        }

    payload_academies = []
    for a in evaluated:
        key = a["id"]
        s = scores[key]
        row = base(a)
        row.update({
            "brand": a.get("brand"),
            "aliases": a.get("aliases", []),
            "schoolLevels": a.get("school_levels", []),
            "stages": a.get("stages", []),
            "flagship": a.get("flagship", []),
            "tel": a.get("tel"),
            "tuitionRaw": a.get("thcc_ctnt"),
            "establishedOn": a.get("estbl_ymd"),
            "dataSource": a.get("data_source", "seed"),
            "score": {
                "total": s["total"],
                "reputation": s["reputation"],
                "momentum": s["momentum"],
                "transparency": s["transparency"],
                "selectivity": s["selectivity"],
                "sampleSize": s["sample_size"],
                "confidence": s["confidence"],
                "isRanked": s["is_ranked"],
                "momentumDirection": s["momentum_direction"],
                "rankInRegion": s.get("rank_in_region"),
                "regionRankedCount": s.get("region_ranked_count"),
                "breakdown": s["breakdown"],
            },
            "evidence": top_evidence.get(key, []),
        })
        payload_academies.append(row)

    # 등록부: 수집 대상이 아니었던 학원. 점수를 붙이지 않는다.
    # '평가했는데 낮음'과 '아직 보지 않음'은 다르고, 섞으면 그게 곧 왜곡이다.
    payload_registry = [base(a) for a in registry_only]

    files = {
        "regions.json": regions,
        "techtree.json": tree,
        "academies.json": payload_academies,
        "registry.json": payload_registry,
        "meta.json": {
            "mode": mode,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "evaluatedCount": len(payload_academies),
            "registryCount": len(payload_academies) + len(payload_registry),
            "mentionCount": len(mentions),
            "naverBudget": config.NAVER_MAX_ACADEMIES,
            "weights": config.WEIGHTS,
            "minSampleForRank": config.MIN_SAMPLE_FOR_RANK,
            "reputationPriorCount": config.REPUTATION_PRIOR_COUNT,
            "recencyHalflifeDays": config.RECENCY_HALFLIFE_DAYS,
            "sources": {
                "official": "NEIS 학원교습소정보 (open.neis.go.kr)" if config.HAS_NEIS else None,
                "community": "네이버 검색 API" if config.HAS_NAVER else None,
            },
        },
    }
    for name, data in files.items():
        path = out / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  → {path.relative_to(config.ROOT)}  ({path.stat().st_size // 1024}KB)")
