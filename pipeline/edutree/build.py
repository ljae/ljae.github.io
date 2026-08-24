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
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import analyze, config, scoring
from . import neis
from .neis import normalize_name


# ── 학원 로딩 ──────────────────────────────────────────────────────
def load_academies(from_cache: bool = False) -> tuple[list[dict], str]:
    cache = config.CACHE_DIR / "neis_academies.json"
    if from_cache and cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))
        print(f"캐시에서 NEIS {len(rows)}곳 로드")
        return _prepare_live(rows), "live"

    if config.HAS_NEIS:
        from . import neis
        print("NEIS 수집 중…")
        rows = neis.fetch_all()
        return _prepare_live(rows), "live"

    # demo 모드는 통합하지 않는다. 시드 주소가 '강남구 대치동' 수준이라
    # 주소 기준으로 묶으면 학군 전체가 한 학원이 된다.
    print("NEIS 키 없음 → 시드 학원으로 진행 (demo 모드)")
    return _expand_seed(), "demo"


def _prepare_live(rows: list[dict]) -> list[dict]:
    """NEIS 원본 → 큐레이션 매핑 → 중복 등록 통합."""
    from . import dedupe
    rows = _merge_seed_into_neis(rows)
    merged, saved = dedupe.apply(rows)
    if saved:
        multi = sum(1 for m in merged if m.get("registration_count", 1) > 1)
        print(f"  중복 등록 통합: {len(rows):,}곳 → {len(merged):,}곳 "
              f"({multi}곳이 2건 이상, {saved:,}건 흡수)")
    return merged


def _expand_seed() -> list[dict]:
    """브랜드 × 학군 조합을 학원 레코드로 펼친다."""
    regions = {r["id"]: r for r in config.regions()}
    tree = config.banded_techtree()
    stage_track = {s["id"]: t for t in tree["tracks"] for s in t["stages"]}

    out: list[dict] = []
    for brand in config.seed_academies():
        for region_id in brand["regions"]:
            region = regions[region_id]
            display = f"{region['name_ko']} {brand['name']}"
            # 한 단계가 두 구간에 걸치면 둘 다 들어간다.
            bands = {stage_track[s]["grade_band"] for s in brand["stages"]}
            bands = [b for b in config.GRADE_BANDS if b in bands]
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
                "grade_bands": bands,
                "stages": brand["stages"],
                "curated_stages": True,
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
    year = rng.randint(2003, 2022)
    rec["estbl_ymd"] = f"{year}-{rng.randint(1, 12):02d}-01"


def _merge_seed_into_neis(neis_rows: list[dict]) -> list[dict]:
    """NEIS 실데이터에 시드의 테크트리 매핑(stages)을 붙인다.

    NEIS 는 어떤 학원이 어느 단계를 담당하는지 모른다. 그 지식은 큐레이션
    쪽에만 있으므로, 이름 매칭으로 연결한다.
    """
    # 브랜드 → 매칭 키. 이름과 별칭 모두에서 뽑는다.
    seed_keys: list[tuple[str, dict]] = []
    for brand in config.seed_academies():
        for label in [brand["name"], *brand.get("aliases", [])]:
            key = normalize_name(label)
            if len(key) >= 2:
                seed_keys.append((key, brand))
    # 긴 키를 먼저 본다. '청담어학원'과 '청담'이 함께 있으면 긴 쪽이 맞다.
    seed_keys.sort(key=lambda kv: -len(kv[0]))

    def find_brand(row: dict) -> tuple[dict | None, bool]:
        """브랜드를 찾는다. (브랜드, 단정해도 되는가)

        과목이 어긋나면 버린다. 접두만으로는 '청담동수학학원'이
        청담어학원(영어)이 된다 — 동 이름과 브랜드 이름이 같은 경우다.

        strict 가 아니면 브랜드로 **단정하지 않는다.** '폴리매그넷',
        '폴리박사' 는 폴리어학원일 수도 아닐 수도 있다. 확실하지 않은 것을
        확실한 것처럼 적으면 그게 곧 거짓이고, 실명 사업자를 다루는
        서비스에서는 특히 그렇다. 대신 '눈여겨볼 곳' 표시만 남긴다.
        """
        guess = set(_infer_subjects(row))
        loose: dict | None = None
        for key, brand in seed_keys:
            kind = neis.matches_brand(row["name"], key)
            if not kind:
                continue
            if guess and not (guess & set(brand["subjects"])):
                continue
            if neis.matches_brand(row["name"], key, strict=True):
                return brand, True
            loose = loose or brand
        return loose, False

    before = len(neis_rows)
    # 예체능·기타까지 받는다. 독서실만 계속 제외한다 — 학원이 아니다.
    keep = (config.ACADEMIC_REALMS | config.ARTS_REALMS | config.OTHER_REALMS)
    neis_rows = [r for r in neis_rows if (r.get("realm_sc_nm") or "") in keep]
    print(f"  분야 필터: {before}곳 → {len(neis_rows)}곳 "
          f"(독서실 등 {before - len(neis_rows)}곳 제외)")

    matched = 0
    hinted = 0
    for row in neis_rows:
        brand, certain = find_brand(row)
        if brand and certain:
            matched += 1
            row["brand"] = brand["name"]
            row["aliases"] = brand.get("aliases", [])
            row["stages"] = brand["stages"]
            # 큐레이션으로 붙은 것임을 남긴다. 수집 대상 선정에서
            # '유명 브랜드' 신호로 쓰는데, 자동 매핑과 섞이면 신호가 죽는다.
            row["curated_stages"] = True
            row["flagship"] = brand.get("flagship", [])
            row["subjects"] = brand["subjects"]
        else:
            # 이름이 유명 브랜드로 시작하지만 단정할 수 없는 경우.
            # 수집 대상 선정에서만 가산점으로 쓴다.
            if brand:
                row["brand_hint"] = True
                hinted += 1
            row.setdefault("stages", [])
            row.setdefault("flagship", [])
            row.setdefault("subjects", _infer_subjects(row))
        # 학교급을 반드시 채운다. 비워 두면 헤더의 초·중·고 필터가 아무것도
        # 거르지 못한다(실측에서 채점 대상 400곳이 전부 비어 있었다).
        if not row.get("grade_bands"):
            row["grade_bands"] = _bands_from_stages(row) or _infer_bands(row)
        # 큐레이션에 없는 곳은 과목·구간에서 자동으로 단계를 붙인다.
        # curated_stages 는 켜지 않는다 — 선정 우선순위와 무관해야 한다.
        if not row.get("stages"):
            row["stages"] = _auto_stages(row)
        row.setdefault("id", row.get("aca_asnum") or f"n-{row['name_normalized']}")
    print(f"  테크트리 매핑: {matched}/{len(neis_rows)}곳이 큐레이션 브랜드와 연결됨"
          + (f" (이름이 겹쳐 단정하지 않은 곳 {hinted}곳은 수집 우선순위로만 반영)"
             if hinted else ""))
    return neis_rows


# 이름·교습과정에서 대상 학년대를 읽는다. 애매하면 여러 개를 넣는다 —
# 하나도 없는 것보다 넓게 잡히는 편이 필터에서 덜 해롭다.
#
# 초등을 저·고학년으로 가르면서, 어느 쪽인지 분명한 낱말만 각각에 두고
# 그냥 '초등'처럼 구간을 못 가르는 낱말은 양쪽에 넣는다. 억지로 한쪽에
# 몰면 없는 정보를 만들어 내는 셈이다.
_BAND_HINTS = {
    "elem_low": ("예비초", "유아", "키즈", "어린이", "아동", "7세", "6세",
                 "초1", "초2", "초3", "한글", "파닉스", "연산",
                 "초등", "초교", "사고력"),
    "elem_high": ("초4", "초5", "초6", "경시", "영재원", "초등부",
                  "초등", "초교", "사고력"),
    "middle": ("중등", "중학", "중1", "중2", "중3", "특목고", "영재고", "과학고",
               "자사고", "고입", "KMO"),
    # '입시'·'내신'·'논술' 은 뺐다. 분야구분이 대부분 '입시.검정 및 보습' 이라
    # 이 낱말들을 쓰면 거의 모든 학원이 고등으로 잡힌다(319/400 이 그랬다).
    "high": ("고등", "고교", "고1", "고2", "고3", "수능", "재수", "N수", "정시",
             "수시", "대입", "의대", "재종", "수학의정석"),
}


# 단계별 특징어. 이름·교습과정에 이 말이 있으면 그 단계로 좁힌다.
#
# 없으면 과목·학년만으로 붙는데, 그러면 한 학원이 그 구간의 모든 단계에
# 달라붙어 '어느 단계 학원인지' 정보가 사라진다. 단서가 있으면 그것만,
# 없으면 그 구간의 대표 단계(_STAGE_DEFAULT)에만 붙인다.
_STAGE_HINTS: dict[str, tuple[str, ...]] = {
    "math_el_basic": ("연산", "교과", "기초", "학교진도", "구몬", "눈높이"),
    "math_el_thinking": ("사고력", "창의", "교구", "퍼즐", "영재", "CMS", "시매쓰",
                         "소마", "와이즈만"),
    "math_el_competition": ("경시", "올림피아드", "KMO", "심화", "최상위"),
    "math_el_preview": ("선행", "중등선행", "예비중"),
    "math_mid_naesin": ("내신", "중등내신", "기출"),
    "math_mid_kmo": ("KMO", "올림피아드", "경시"),
    "math_mid_preview": ("고등선행", "고1", "공통수학", "대수"),
    "math_mid_gifted": ("영재고", "과학고", "특목", "구술"),
    "math_hi_naesin": ("내신", "고등내신"),
    "math_hi_suneung": ("수능", "정시", "미적분", "기하", "확통"),
    "math_hi_top": ("의대", "최상위", "킬러"),
    "math_hi_nsu": ("재수", "N수", "재종"),

    "eng_el_phonics": ("파닉스", "리딩", "기초", "유아", "키즈"),
    "eng_el_academy": ("어학원", "정규", "레벨"),
    "eng_el_rw": ("라이팅", "에세이", "디베이트", "토론", "심화"),
    "eng_el_bridge": ("문법", "중등", "토플", "시험"),
    "eng_mid_naesin": ("내신", "중등내신", "기출"),
    "eng_mid_test": ("토플", "텝스", "특목", "국제고"),
    "eng_mid_preview": ("수능", "고등선행", "독해", "어법"),
    "eng_hi_naesin": ("내신", "고등내신"),
    "eng_hi_suneung": ("수능", "절대평가"),
    "eng_hi_adv": ("논술", "심화", "최상위"),

    "kor_el_reading": ("독서", "논술", "토론", "읽기", "한우리", "기초"),
    "kor_el_literacy": ("문해력", "어휘", "비문학", "독해"),
    "kor_el_preview": ("중등", "선행", "예비중"),
    "kor_mid_naesin": ("내신", "중등내신", "기출"),
    "kor_mid_deep": ("문법", "문학", "심화"),
    "kor_mid_preview": ("고등", "선행", "수능형"),
    "kor_hi_naesin": ("내신", "고등내신"),
    "kor_hi_suneung": ("수능", "비문학", "화작", "언매"),
    "kor_hi_nonsul": ("논술", "대학별"),

    "sci_el_lab": ("실험", "탐구", "체험", "관찰"),
    "sci_el_gifted": ("영재원", "영재", "대학부설"),
    "sci_el_preview": ("중등", "선행", "예비중"),
    "sci_mid_naesin": ("내신", "중등내신"),
    "sci_mid_preview": ("물리", "화학", "생물", "지구과학", "물화생지", "개념"),
    "sci_mid_olympiad": ("영재고", "과학고", "올림피아드", "특목"),
    "sci_hi_naesin": ("내신", "고등내신"),
    "sci_hi_suneung": ("수능", "과탐"),
    "sci_hi_adv": ("의대", "II", "심화", "최상위"),
}

# 단서가 하나도 없을 때 붙일 대표 단계. 각 과목·구간에서 가장 넓은 곳.
_STAGE_DEFAULT = {
    ("math", "elem_low"): "math_el_basic",
    ("math", "elem_high"): "math_el_competition",
    ("math", "middle"): "math_mid_naesin",
    ("math", "high"): "math_hi_naesin",
    ("english", "elem_low"): "eng_el_academy",
    ("english", "elem_high"): "eng_el_academy",
    ("english", "middle"): "eng_mid_naesin",
    ("english", "high"): "eng_hi_naesin",
    ("korean", "elem_low"): "kor_el_reading",
    ("korean", "elem_high"): "kor_el_literacy",
    ("korean", "middle"): "kor_mid_naesin",
    ("korean", "high"): "kor_hi_naesin",
    ("science", "elem_low"): "sci_el_lab",
    ("science", "elem_high"): "sci_el_gifted",
    ("science", "middle"): "sci_mid_naesin",
    ("science", "high"): "sci_hi_naesin",
}


def _auto_stages(row: dict) -> list[str]:
    """큐레이션에 없는 학원을 단계에 붙인다.

    단계 매핑이 시드 브랜드 매칭에만 의존하고 있었다. 400곳 중 42곳만
    붙었고, 41개 단계 × 4학군 = 164개 조합 중 111개가 **0곳**이었다.
    국어·과학은 전 단계가 비어 있었다. 로드맵에서 단계를 눌러도 학원이
    안 나오면 로드맵이 랭킹으로 이어지지 않는다.

    과목과 학년 구간은 이미 안다. 그 교집합에 드는 단계 중, 이름·교습과정에
    단서가 있으면 그 단계로 좁히고 없으면 대표 단계 하나에만 붙인다.
    구간의 모든 단계에 달라붙게 두면 '어느 단계 학원인지'가 사라진다.
    """
    subjects = [s for s in (row.get("subjects") or []) if s != "etc"]
    bands = row.get("grade_bands") or []
    if not subjects or not bands:
        return []

    blob = " ".join(str(row.get(k) or "") for k in
                    ("name", "le_crse_list_nm", "le_crse_nm")).upper()
    tree = config.techtree()
    by_id = {st["id"]: (t["subject"], st)
             for t in tree["tracks"] for st in t["stages"]
             if not st.get("roadmap_only")}

    out: list[str] = []
    for subject in subjects:
        for band in bands:
            lo, hi = config.GRADE_BANDS[band][1], config.GRADE_BANDS[band][2]
            # 이 과목·구간에 걸치는 단계들
            fits = [sid for sid, (subj, st) in by_id.items()
                    if subj == subject
                    and st["grade"][0] <= hi and st["grade"][1] >= lo]
            hinted = [sid for sid in fits
                      if any(h.upper() in blob for h in _STAGE_HINTS.get(sid, ()))]
            if hinted:
                picked = hinted
            else:
                # 단서가 없으면 대표 단계에 붙인다. 다만 대표 하나에만
                # 몰면 '선행'·'심화' 같은 보조 단계가 영원히 0곳으로 남는다
                # (실측: 160개 조합 중 52개가 비었고 대부분 선행 단계였다).
                # 학원 id 해시로 보조 단계에도 고르게 흩는다. 무작위가
                # 아니라 해시라 매 빌드 같은 결과가 나온다.
                default = _STAGE_DEFAULT.get((subject, band))
                others = [x for x in fits if x != default]
                picked = [default] if default in fits else []
                if others:
                    idx = int(hashlib.md5(
                        f"{row.get('id')}|{subject}|{band}".encode()
                    ).hexdigest(), 16)
                    picked.append(others[idx % len(others)])
            for sid in picked:
                if sid and sid not in out:
                    out.append(sid)
    return out


def _bands_from_stages(row: dict) -> list[str]:
    """큐레이션 단계에 매핑됐다면 그 단계가 걸치는 학년 구간을 그대로 쓴다.

    한 단계가 두 구간에 걸치면(사고력 초1~초4) 둘 다 들어간다.
    실제로 두 구간 학부모가 같이 찾는 곳이라 한쪽으로 몰 이유가 없다.
    """
    stages = row.get("stages") or []
    if not stages:
        return []
    tree = config.techtree()
    stage_grade = {s["id"]: s["grade"]
                   for t in tree["tracks"] for s in t["stages"]}
    out: list[str] = []
    for sid in stages:
        grade = stage_grade.get(sid)
        if not grade:
            continue
        for band in config.bands_for_range(grade[0], grade[1]):
            if band not in out:
                out.append(band)
    return [b for b in config.GRADE_BANDS if b in out]


def _infer_bands(row: dict) -> list[str]:
    # 분야구분(realm)은 쓰지 않는다. 전 학원이 같은 값이라 신호가 없다.
    blob = " ".join(str(row.get(k) or "") for k in
                    ("name", "le_crse_list_nm", "le_crse_nm"))
    found = [b for b, hints in _BAND_HINTS.items()
             if any(h in blob for h in hints)]
    # 아무것도 안 잡히면 특정 구간에 한정되지 않는 곳으로 본다.
    # 빈 배열은 앱에서 '모든 구간에 해당'으로 처리한다.
    return found


# 예체능 세부. 표시는 '예체능' 하나로 묶되, 추론에는 쓴다.
_ARTS_HINTS = ("미술", "피아노", "바이올린", "첼로", "음악", "무용", "발레",
               "태권도", "체육", "축구", "수영", "댄스", "보컬", "실용음악",
               "드럼", "기타(악기)", "만화", "웹툰", "디자인", "사진", "연기")

_SUBJECT_HINTS = {
    "math": ("수학", "산수", "사고력", "매쓰", "MATH", "Math"),
    # '잉글리쉬'(쉬)와 '잉글리시'(시)가 둘 다 실존한다 — 알파잉글리쉬학원이
    # '쉬' 표기 하나 때문에 국어 학원으로 추론돼 브랜드 매칭에서 튕겼다.
    "english": ("영어", "어학", "English", "ENGLISH", "잉글리시", "잉글리쉬",
                "어학원"),
    "korean": ("국어", "논술", "독서", "문해", "언어"),
    "science": ("과학", "물리", "화학", "생물", "지구과학"),
}


def _subject_from_realm(row: dict) -> str | None:
    """분야구분으로 정해지는 과목. 이름 추론보다 우선한다 —
    공시가 '예능(대)'이라고 말하는데 이름에 '수학'이 있다고
    수학 학원으로 볼 이유가 없다."""
    realm = (row.get("realm_sc_nm") or "").strip()
    if realm in config.ARTS_REALMS:
        return "arts"
    if realm in config.OTHER_REALMS:
        return "etc"
    return None


def _infer_subjects(row: dict) -> list[str]:
    """과목 추론.

    학원명이 가장 정확한 신호다('○○수학학원'). 교습과정은 '보습'처럼
    과목을 특정하지 않는 값이 많아 보조로만 쓴다. 아무것도 안 잡히면
    'etc'(종합·보습)로 둔다 — 억지로 배정하지 않는다.
    """
    # 공시 분야가 예체능·기타라고 말하면 그것을 따른다. 이름에 '수학'이
    # 들어 있어도 '예능(대)' 로 등록된 곳을 수학 학원으로 볼 이유가 없다.
    by_realm = _subject_from_realm(row)
    if by_realm:
        return [by_realm]

    name = str(row.get("name") or "")

    # 학술 과목이 먼저다. 공시 분야가 '입시.검정 및 보습' 인 곳에서
    # 이름의 낱말만 보고 예체능으로 넘기면 안 된다 — '수영수학교습소' 가
    # '수영' 때문에 예체능이 됐다.
    found = [s for s, hints in _SUBJECT_HINTS.items() if any(h in name for h in hints)]
    if found:
        return found

    # 학술 신호가 없을 때만 예체능 힌트를 본다. 그마저도 공시 분야가
    # 학술이면 쓰지 않는다 — 공시가 '보습' 이라는데 이름의 한 낱말로
    # 뒤집을 근거가 없다.
    realm = (row.get("realm_sc_nm") or "").strip()
    if realm not in config.ACADEMIC_REALMS and any(h in name for h in _ARTS_HINTS):
        return ["arts"]

    course = " ".join(str(row.get(k) or "") for k in ("le_crse_list_nm", "le_crse_nm"))
    found = [s for s, hints in _SUBJECT_HINTS.items() if any(h in course for h in hints)]
    if found:
        return found

    if (row.get("realm_sc_nm") or "") == "국제화" or "외국어" in course:
        return ["english"]

    # 과목을 특정하지 못했다. 분야에 따라 다르게 둔다.
    #
    # 학술 분야(입시·보습·국제화 등)인데 과목이 안 잡히는 곳은 종합·보습
    # 학원이다. 이들을 'etc' 로 두면 예체능·기타 랭킹에 섞인다 —
    # '대치수능선배2관학원' 이 기타 랭킹에 뜨는 식이다.
    # 'general'(종합·보습)로 따로 둬서 어느 과목 랭킹에도 넣지 않는다.
    if (row.get("realm_sc_nm") or "").strip() in config.ACADEMIC_REALMS:
        return ["general"]
    return ["etc"]


# ── 언급 로딩 ──────────────────────────────────────────────────────
def _previous_scores() -> dict:
    """직전 빌드의 랭킹 상태. app 번들에 이미 나가 있는 것을 읽는다."""
    path = config.EXPORT_DIR / "academies.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return {r["id"]: {"is_ranked": (r.get("score") or {}).get("isRanked", False)}
            for r in rows}


def select_for_mentions(academies: list[dict],
                        prev_scores: dict | None = None
                        ) -> tuple[list[dict], list[dict]]:
    """네이버 수집 대상을 예산 안에서 고른다.

    학군마다 예산을 똑같이 나눈다. 전체를 한 줄로 세우면 대치가 예산을
    독식해 다른 학군 랭킹이 비어버린다.

    ★ 학군 안에서는 **학년 구간별로 다시 나눈다.**

    예전에는 정원(수용인원) 순으로 한 줄 세웠다. 그랬더니 대치 100칸의
    윗자리를 러셀 자습전용관(정원 54,361)·대찬·시대인재 같은 재수종합반이
    통째로 가져갔다. 정원은 규모의 대리 지표로 보였지만 실은 **업종 편향**
    이었다 — 재종반·자습실형은 수용인원이 수만이고 저학년 어학원은 72~158
    명이다. 그 결과 대치 저학년 영어의 대표 학원(청담·폴리매그넷·정상·
    리드101)이 한 곳도 수집되지 않았다. 랭킹에 없는 이유가 '평가해서 낮음'
    이 아니라 '보지도 않음' 이었다.

    지금은 구간마다 자리를 먼저 떼어 준 뒤, 그 안에서 과목을 번갈아 가며
    정원 순으로 고른다. 정원 비교는 같은 구간·같은 과목끼리만 한다.
    구간이 안 잡힌 곳(종합·보습·재종)은 남은 자리를 나눠 갖는다.
    """
    budget = config.NAVER_MAX_ACADEMIES
    regions = [r["id"] for r in config.regions()]
    per_region = max(1, budget // max(1, len(regions)))

    # 지난 회차 결과를 반영한다. 언급이 안 나오던 곳은 뒤로 밀고,
    # 아직 비어 있는 단계를 채우는 곳을 앞으로 당긴다. 한 번에 끝나지
    # 않고 매 회차 조금씩 순환하면서 커버리지가 올라간다.
    from . import coverage
    hist = coverage.load()
    gaps = coverage.stage_gaps(academies, prev_scores or {})

    bands = list(config.GRADE_BANDS)
    # 학년 구간에 76%, 예체능·기타에 12%, 구간 미상에 12%.
    #
    # 예체능은 별도 몫을 떼어 준다. 학년 구간으로만 나누면 학년 단서가
    # 약한 예체능이 매번 뒤로 밀려 랭킹에 한 곳도 못 든다(실측: 90곳을
    # 뽑았는데 언급이 잡힌 곳은 2곳뿐이었다).
    per_band = max(1, int(per_region * 0.76) // len(bands))
    per_arts = max(1, int(per_region * 0.12))

    def capacity(a: dict) -> float:
        try:
            return float(a.get("tofor_smtot") or 0)
        except (TypeError, ValueError):
            return 0.0

    def take(pool: list[dict], quota: int, chosen: set[str]) -> list[dict]:
        """과목을 번갈아 가며 정원 순으로 고른다.

        한 과목이 자리를 쓸어 가지 않게 한다. 대치 영어처럼 후보가 많은
        과목이 있으면 라운드로빈이 없을 때 수학이 통째로 밀린다.
        """
        by_subject: dict[str, list[dict]] = {}
        for a in pool:
            for sub in (a.get("subjects") or ["etc"]):
                by_subject.setdefault(sub, []).append(a)
        # 같은 구간·같은 과목 안에서만 정원을 비교한다.
        # 큐레이션에 매핑된 곳과 유명 브랜드로 보이는 곳을 앞세운다 —
        # 테크트리 화면이 전자에 의존하고, 후자는 학부모가 실제로 찾는 이름이다.
        for rows in by_subject.values():
            rows.sort(key=lambda a: (
                0 if a.get("curated_stages") else 1,
                *coverage.priority_bonus(a, hist, gaps),
                0 if a.get("brand_hint") else 1,
                -capacity(a)))

        out: list[dict] = []
        cursors = {k: 0 for k in by_subject}
        while len(out) < quota and any(
                cursors[k] < len(by_subject[k]) for k in by_subject):
            for sub in sorted(by_subject):
                if len(out) >= quota:
                    break
                rows, i = by_subject[sub], cursors[sub]
                while i < len(rows) and rows[i]["id"] in chosen:
                    i += 1
                cursors[sub] = i
                if i < len(rows):
                    chosen.add(rows[i]["id"])
                    out.append(rows[i])
                    cursors[sub] = i + 1
        return out

    selected, skipped = [], []
    band_counts: dict[str, int] = {}
    for region_id in regions:
        rows = [a for a in academies if a.get("region_id") == region_id]
        chosen: set[str] = set()
        picked: list[dict] = []

        for band in bands:
            pool = [a for a in rows if band in (a.get("grade_bands") or [])]
            got = take(pool, per_band, chosen)
            picked += got
            band_counts[band] = band_counts.get(band, 0) + len(got)

        # 예체능·기타 몫. 이들은 학년 구간 신호가 약해 위에서 잘 안 뽑힌다.
        arts = [a for a in rows
                if a["id"] not in chosen
                and not (set(a.get("subjects") or []) & set(config.ACADEMIC_SUBJECTS))]
        picked += take(arts, per_arts, chosen)

        # 구간 미상(종합·보습·재종) + 위에서 후보가 모자라 남은 자리
        rest = [a for a in rows if a["id"] not in chosen]
        picked += take(rest, per_region - len(picked), chosen)

        selected.extend(picked)
        skipped.extend(a for a in rows if a["id"] not in chosen)

    other = [a for a in academies if a.get("region_id") not in regions]
    skipped.extend(other)

    print(f"  네이버 수집 대상 {len(selected)}곳 선별 "
          f"(학군당 {per_region}곳, 구간당 {per_band}곳, 예산 {budget})")
    print("    구간별: " + " · ".join(
        f"{config.GRADE_BANDS[b][0]} {band_counts.get(b, 0)}" for b in bands))
    print(f"  미수집 {len(skipped)}곳은 등록부에만 남기고 점수를 매기지 않습니다")
    return selected, skipped


def load_mentions(academies: list[dict], mode: str,
                  with_cafe: bool = False,
                  from_cache: bool = False) -> list[dict]:
    mentions: list[dict] = []

    cache = config.CACHE_DIR / "naver_mentions.json"
    if from_cache and cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))
        # 통합으로 id 가 바뀐 학원의 언급을 대표 id 로 옮긴다.
        # 옮기지 않으면 통합된 쪽 언급이 통째로 사라진다.
        alias: dict[str, str] = {}
        for a in academies:
            for rid in a.get("registration_ids") or []:
                if rid and rid != a["id"]:
                    alias[str(rid)] = a["id"]
        moved = 0
        for r in rows:
            new = alias.get(str(r.get("academy_key")))
            if new:
                r["academy_key"] = new
                moved += 1
        print(f"캐시에서 언급 {len(rows):,}건 로드 (API 호출 없음)"
              + (f" · 통합에 따라 {moved:,}건 재귀속" if moved else ""))
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
        # 지난 회차 랭킹을 커버리지 계산의 기준으로 쓴다. 없으면(첫 실행)
        # 빈 dict 라 모든 단계가 '비어 있음'으로 잡혀 골고루 뽑힌다.
        prev = _previous_scores()
        evaluated, registry_only = select_for_mentions(academies, prev)
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
    # 이름이 그 자체로 일상어인 학원('책읽기')은 학원 표지를 함께 요구한다.
    generic = {a["id"]: analyze.is_generic_name(a.get("name") or "")
               for a in evaluated}

    # 다른 학원 이름 후보. 모든 학원에 쓴다.
    #
    # 두 가지를 판별한다.
    #  - 일상어 이름('책읽기')일 때: 제목의 주인공이 다른 학원인가
    #  - 모든 학원: 여러 학원을 늘어놓은 비교글·목록글·광고인가
    #
    # 등록부까지 넣는다. 글에 나오는 학원이 채점 대상이 아닐 수 있다.
    rival_names: set[str] = set()
    for a in evaluated + registry_only:
        if analyze.is_generic_name(a.get("name") or ""):
            continue
        for c in analyze.name_candidates(a):
            if len(c) >= 3:          # 짧은 이름은 우연히 겹친다
                rival_names.add(c)

    before = len(mentions)
    mentions = [m for m in mentions
                if analyze.is_relevant(
                    m,
                    candidates.get(m["academy_key"], set()),
                    generic.get(m["academy_key"], False),
                    rival_names)]
    dropped = before - len(mentions)
    if before:
        print(f"  관련성 게이트: {before:,}건 → {len(mentions):,}건 "
              f"(학원명 미등장 {dropped:,}건 제외, {dropped/before*100:.0f}%)")

    # 지점 게이트 — 유명 브랜드는 전국에 지점이 있다. 글이 지역을 밝히면
    # 그 권역 지점만, 안 밝히면 걸리는 지점 전부의 근거로 삼는다.
    from . import branches
    mentions, bstat = branches.apply(mentions, evaluated,
                                     candidates, generic, rival_names)
    if bstat["branches"]:
        print(f"  지점 게이트: 다권역 지점 {bstat['branches']}곳 · "
              f"타권역 지점 글 {bstat['elsewhere']:,}건 · "
              f"권역 밖 지점 글 {bstat['other_region']:,}건 제외 · "
              f"지역 불명 {bstat['shared']:,}건은 지점 공유")

    names = {a["id"]: a.get("name", "") for a in evaluated}
    # 운영자 판정과 크롤 규칙을 반영한다. 관련성 게이트가 못 거르는
    # 동명이인·광고를 사람이 판정한 결과가 여기서 되먹여진다.
    from . import review_queue
    rules = review_queue.load_rules()
    mentions, by_rule = review_queue.apply_rules(mentions, rules)
    verdicts = review_queue.load_verdicts()
    mentions, by_verdict = review_queue.apply_verdicts(mentions, verdicts)
    # 재분류 — '이 글은 사실 저 학원 글' 이라는 판정을 근거로 되돌린다.
    # 반려만 가능하던 때는 네 학원 비교글이 통째로 버려졌다.
    moved = 0
    reassign = review_queue.load_reassignments()
    if reassign:
        mentions, moved = review_queue.apply_reassignments(
            mentions, reassign, evaluated)
    if by_rule or by_verdict or moved:
        print(f"  운영자 검수 반영: 규칙 {by_rule:,}건 · 반려 {by_verdict:,}건 제외"
              f"{f' · 재분류 {moved:,}건 추가' if moved else ''}")

    mentions = [analyze.analyze(m, names.get(m.get("academy_key"), ""))
                for m in mentions]
    mentions = analyze.flag_repeat_authors(mentions)

    if mode == "live":
        # 이번 회차 결과를 남긴다. 다음 회차 선정이 이걸 보고 순환한다.
        from . import coverage
        coverage.record(evaluated, mentions)

        # 검수 대기 큐에 올린다. 신뢰도 높은 글부터 — 점수에 영향이 큰
        # 글을 먼저 봐야 검수 한 번의 값어치가 크다.
        queued = review_queue.enqueue(mentions, evaluated, verdicts)
        if queued:
            print(f"  검수 큐: {queued:,}건 대기")

    # 학원실록 자체 후기를 같은 채점 로직에 태운다.
    # 스크랩 글보다 신뢰도를 높게 주되, 별도 기둥을 만들지는 않는다 —
    # 평판은 하나의 축이고 출처에 따라 가중치만 다르면 된다.
    if config.HAS_SUPABASE:
        from . import reviews as own_reviews
        summaries = own_reviews.fetch_summaries()
        extra = own_reviews.as_mentions(summaries)
        if extra:
            mentions.extend(extra)
            print(f"  학원실록 후기 {len(extra):,}건 반영 ({len(summaries)}곳)")
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


_ROAD = re.compile(r"([가-힣A-Za-z0-9]+(?:대?로|길))\s*([\d-]+)")


def _road_short(address: str | None) -> str | None:
    """'서울특별시 양천구 목동서로 389' → '목동서로 389'"""
    m = _ROAD.search(address or "")
    return f"{m.group(1)} {m.group(2)}" if m else None


# 지점 이름에 붙는 지역어. '반포시매쓰' 의 '반포' 같은 것들이다.
_LOCALITY = (
    "대치", "도곡", "개포", "역삼", "목동", "신정", "양천",
    "반포", "잠원", "서초", "방배", "잠실", "신천", "방이", "송파", "강남",
)


def assign_display_names(rows: list[dict]) -> dict[str, int]:
    """화면에 찍을 이름을 정하고 중복을 없앤다.

    카드가 오래 'brand ?? name' 을 찍고 있었다. 큐레이션 브랜드는 지점을
    구분하지 않으므로, 목동서로 133 과 목동서로 349 의 서로 다른 CMS 지점이
    똑같이 'CMS영재교육' 으로 나왔다. 학부모 눈에는 같은 학원이 두 번 뜬 것이다.

    그래서 표시명의 뿌리는 항상 NEIS 실제 학원명으로 둔다. 그래도 같은 이름이
    한 학군에 여럿이면(씨앤씨 5곳) 도로명을 붙여 갈라 준다. 지점이 다르다는
    사실 자체가 학부모에게 필요한 정보다.
    """
    from collections import Counter, defaultdict

    base = {r["id"]: (r.get("name") or "").strip() for r in rows}

    # ★ 이름이 겹치지 않아도 헷갈리는 경우가 있다.
    #   '시매쓰학원'(서초 방배점) 과 '반포시매쓰학원'(서초 반포점) 은 서로
    #   다른 지점인데, 앞의 것은 이름에 지점 단서가 없어 브랜드 본점처럼
    #   읽힌다. 같은 학군에 같은 브랜드가 또 있는데 내 이름에 지점 단서가
    #   없으면, 동 이름을 붙여 어느 지점인지 말해 준다.
    from . import dedupe as _dd

    def _bare_brand(name: str) -> str | None:
        """지점 단서가 없는 브랜드 이름이면 그 브랜드 토큰을 돌려준다."""
        token = _dd.brand_token(name)
        if len(token) < 2:
            return None
        # 업종어만 뗀 알맹이로 견준다. brand_token_light 는 지역어까지
        # 떼므로 '반포시매쓰학원' 도 단서 없음으로 잘못 잡힌다.
        return token if _dd.core_name(name) == token else None

    by_brand = defaultdict(list)
    for r in rows:
        token = _dd.brand_token(base[r["id"]])
        if len(token) >= 2:
            by_brand[(r.get("region_id"), token)].append(r)

    for r in rows:
        token = _bare_brand(base[r["id"]])
        dong = (r.get("dong") or "").strip()
        if not token or not dong:
            continue
        # ★ 동이 형제와 다를 때만 붙인다.
        #   같은 브랜드의 여러 관은 대개 같은 동에 있다('깊은생각'과
        #   '깊은생각256학원'은 둘 다 대치동). 거기에 '(대치동)' 을 붙이면
        #   구분은 안 되고 이름만 길어진다. 동이 실제로 갈릴 때만 정보다.
        others = [x for x in by_brand[(r.get("region_id"), token)]
                  if x["id"] != r["id"]]
        dongs = {(x.get("dong") or "").strip() for x in others} - {""}
        if not dongs or dong in dongs:
            continue
        # ★ 헷갈리는 꼴은 하나뿐이다: 형제가 '지역명+브랜드' 인데
        #   내 이름은 맨 브랜드인 경우. '반포시매쓰학원' 옆의 '시매쓰학원'
        #   은 다른 지점(방배점)인데 브랜드 본점처럼 읽힌다.
        #
        #   브랜드 토큰만 같으면 붙이도록 두면 우연히 겹친 것까지 잡힌다
        #   ('폴리어학원'과 '폴리어수학학원'은 다른 학원이다). 여기서
        #   한 번 틀려 26곳이 엉뚱하게 갈렸다.
        core = _dd.core_name(base[r["id"]])
        if not any(_dd.core_name(x.get("name") or "") in
                   {f"{w}{core}", f"{core}{w}"} for x in others
                   for w in _LOCALITY):
            continue
        base[r["id"]] = f"{base[r['id']]} ({dong})"

    counts = Counter((r.get("region_id"), base[r["id"]]) for r in rows)

    stats = defaultdict(int)
    for r in rows:
        name = base[r["id"]]
        if counts[(r.get("region_id"), name)] > 1:
            road = _road_short(r.get("road_address"))
            r["display_name"] = f"{name} ({road})" if road else f"{name} ({r['id']})"
            stats["disambiguated"] += 1
        else:
            r["display_name"] = name

    # 도로명까지 같으면(같은 건물) 마지막 수단으로 등록번호를 붙인다
    final = Counter((r.get("region_id"), r["display_name"]) for r in rows)
    for r in rows:
        if final[(r.get("region_id"), r["display_name"])] > 1:
            r["display_name"] = f"{r['display_name']} #{r['id']}"
            stats["id_suffixed"] += 1
    return dict(stats)


def audit_uniqueness(rows: list[dict]) -> list[str]:
    """전수 점검. 남아 있는 중복을 전부 문자열로 돌려준다."""
    from collections import Counter

    problems = []
    for label, key in (("id", lambda r: r["id"]),
                       ("표시명(학군내)", lambda r: (r.get("region_id"), r["display_name"]))):
        dup = {k: v for k, v in Counter(key(r) for r in rows).items() if v > 1}
        for k, v in sorted(dup.items(), key=lambda t: -t[1]):
            problems.append(f"{label} 중복: {k} × {v}")
    return problems


def _district_trends() -> list[dict]:
    try:
        from . import edss
        return edss.load_districts()
    except Exception:                       # noqa: BLE001
        return []


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
                # 지역을 밝히지 않은 글은 같은 브랜드의 여러 지점에 함께
                # 붙는다. 그 사실을 화면에서 밝혀야 '중복'으로 읽히지 않는다.
                "branch_basis": m.get("branch_basis"),
            })

    # 표시명은 채점 대상과 등록부를 한꺼번에 놓고 정해야 한다.
    # 따로 정하면 두 목록에 같은 이름이 남는다.
    school_rows: list[dict] = []
    apt_rows: list[dict] = []
    if mode == "live":
        from . import geocode, schools as school_mod
        school_rows = school_mod.fetch_all()
        if school_rows:
            geocode.enrich(school_rows)
            from . import schooldistrict
            schooldistrict.fetch_all()
            schooldistrict.attach_to_schools(school_rows)
        # 아파트는 수집이 오래 걸려 캐시를 그대로 읽는다.
        # (pipeline/edutree/apartments.py 를 따로 돌려 캐시를 만든다)
        apt_cache = config.CACHE_DIR / "apartments.json"
        if apt_cache.exists():
            apt_rows = json.loads(apt_cache.read_text(encoding="utf-8"))
            print(f"  아파트 캐시 {len(apt_rows):,}단지")
            # 의무관리대상이 아니라 API 에 없는 소규모 단지를 얹는다.
            from . import apartments as apt_mod
            apt_rows = apt_mod.merge_extra(apt_rows)
            geocode.fill_coords(apt_rows)
            from . import zones as zone_mod
            zone_mod.assign(apt_rows, school_rows)
            zone_mod.attach_apartments(school_rows, apt_rows)
        # 진로 공시(캐시가 있을 때만)와 수기 보완을 학교에 붙인다.
        from . import careers
        careers.attach(school_rows)
        got = geocode.enrich(evaluated + registry_only)
        if got:
            print(f"  좌표 확보 {got:,}곳 / {len(evaluated) + len(registry_only):,}곳")

    # 오늘 자 랭킹 스냅샷. 과거 이력이 없으므로 오늘부터 쌓는다.
    from . import history
    history.record(evaluated, scores, school_rows)

    stats = assign_display_names(evaluated + registry_only)
    if stats:
        print(f"  표시명 중복 해소: 도로명 부기 {stats.get('disambiguated', 0)}곳"
              + (f", 등록번호 부기 {stats['id_suffixed']}곳" if stats.get("id_suffixed") else ""))
    problems = audit_uniqueness(evaluated + registry_only)
    if problems:
        print("  ! 남아 있는 중복:")
        for p in problems[:10]:
            print(f"      {p}")
    else:
        print(f"  전수 점검: {len(evaluated) + len(registry_only):,}곳 모두 고유 ✓")

    def base(a: dict) -> dict:
        return {
            "id": a["id"],
            "name": a["name"],
            "displayName": a.get("display_name") or a["name"],
            "regionId": a.get("region_id"),
            "dong": a.get("dong"),
            "subjects": a.get("subjects", []),
            "address": a.get("road_address"),
            "capacity": a.get("tofor_smtot"),
            "registrationStatus": a.get("reg_stttus_nm"),
            "isVerified": a.get("is_verified", False),
            "registrationCount": a.get("registration_count", 1),
            "lat": a.get("lat"),
            "lng": a.get("lng"),
        }

    payload_academies = []
    for a in evaluated:
        key = a["id"]
        s = scores[key]
        row = base(a)
        row.update({
            "brand": a.get("brand"),
            "aliases": a.get("aliases", []),
            "gradeBands": a.get("grade_bands", []),
            "stages": a.get("stages", []),
            "flagship": a.get("flagship", []),
            "tel": a.get("tel"),
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
                # academic | non_academic. 예체능·기타는 만족도·화제성만 본다.
                "subjectGroup": s.get("subject_group", "academic"),
                # 표본이 적으면 내보내지 않는다. 3건으로 만든 '긍정률 67%' 는
                # 숫자처럼 보이지만 아무것도 말하지 않는다.
                "positiveRate": (
                    (s.get("breakdown", {}).get("reputation", {}) or {}).get("긍정률")
                    if s["sample_size"] >= config.MIN_SAMPLE_FOR_RANK else None),
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
        # 학군별 학원 수를 여기에 미리 넣는다. 앱이 이걸 세려면 등록부
        # 전체(1.4MB)를 첫 화면에서 읽어야 했는데, 정작 쓰는 건 숫자 넷이다.
        "regions.json": [{
            **r,
            "academy_count": sum(1 for a in evaluated if a["region_id"] == r["id"])
                           + sum(1 for a in registry_only if a["region_id"] == r["id"]),
            "evaluated_count": sum(1 for a in evaluated if a["region_id"] == r["id"]),
            "trends": [
                t for t in _district_trends() if t["regionId"] == r["id"]],
        } for r in regions],
        "schools.json": [{
            "id": s["id"], "name": s["name"], "level": s["level"],
            "levelLabel": s["level_label"], "regionId": s["region_id"],
            "dong": s["dong"], "foundation": s["foundation"], "coed": s["coed"],
            "highKind": s["high_kind"], "address": s["road_address"],
            "tel": s["tel"], "homepage": s["homepage"],
            "lat": s.get("lat"), "lng": s.get("lng"),
            "zoneId": s.get("zone_id"), "zoneName": s.get("zone_name"),
            "eduOffice": s.get("edu_office"),
            "zonePeers": s.get("zone_peers") or [],
            "assignment": s.get("assignment"),
            "apartments": s.get("apartments") or [],
            "apartmentHouseholds": s.get("apartment_households"),
            "careers": s.get("careers"),
            "outcomesExtra": s.get("outcomes_extra"),
        } for s in school_rows],
        "apartments.json": [{
            "id": a.get("kaptCode"),
            "name": a.get("name") or a.get("kaptName"),
            "regionId": a.get("region_id"),
            "dong": a.get("dong"),
            "address": a.get("address"),
            "households": int(float(a["households"])) if a.get("households") else None,
            "buildings": int(a["buildings"]) if str(a.get("buildings") or "").isdigit() else None,
            "usedDate": a.get("used_date"),
            "lat": a.get("lat"), "lng": a.get("lng"),
            "zones": a.get("zones") or [],
            # 'manual' 은 공동주택 API 밖에서 손으로 넣은 단지.
            # 출처가 다르면 다르다고 적어 둔다.
            "source": a.get("source"),
        } for a in apt_rows if a.get("kaptCode")],
        "techtree.json": {**config.banded_techtree(),
                          "roadmap": config.roadmap_payload()},
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
