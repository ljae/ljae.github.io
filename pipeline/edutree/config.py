"""설정 · 상수 · 경로."""
from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # dotenv 없이도 동작
    pass

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT / "pipeline"
DATA_DIR = PIPELINE_DIR / "data"
CACHE_DIR = PIPELINE_DIR / ".cache"
# Flutter 앱이 번들로 읽는 출력 경로
EXPORT_DIR = ROOT / "app" / "assets" / "data"

for _d in (CACHE_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── 자격 증명 (없으면 시드 모드로 동작) ────────────────────────────
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "").strip()

# 네이버 검색 API 자격 증명.
# 두 콘솔 모두 'Client ID + Client Secret' 한 쌍을 주지만, 호출 방식이 다르다.
#   legacy : developers.naver.com    → openapi.naver.com/v1/search/*.json
#            헤더 X-Naver-Client-Id / X-Naver-Client-Secret
#   hub    : console.ncloud.com      → naverapihub.apigw.ntruss.com/search/v1/*
#            헤더 X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
# 어느 쪽 키를 넣든 동작하도록 NAVER_API_MODE=auto 가 기본값이며,
# 첫 호출에서 실제로 통하는 쪽을 자동으로 찾는다.
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
NAVER_API_MODE = os.getenv("NAVER_API_MODE", "auto").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

HAS_NEIS = bool(NEIS_API_KEY)
HAS_NAVER = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)
HAS_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

# ── 트리스코어 가중치 (docs/SPEC.md §4 와 반드시 일치) ──────────────
# 기둥 가중치.
#
# 평판과 진입난이도를 가장 무겁게 둔다. 학부모가 실제로 묻는 것이
# '평이 좋은가'와 '가고 싶어도 갈 수 있는가' 둘이기 때문이다. 들어가기
# 어렵다는 사실 자체가 수요의 가장 정직한 표현이고, 자리가 남는 학원과
# 대기를 거는 학원을 같은 저울에 놓으면 지금 학원가 현황이 안 보인다.
#
# 교습비는 뺐다. NEIS 는 금액만 주고 **교습시간을 주지 않는다.** 주2회
# 26만원과 주5회 26만원이 같은 값으로 서 있으면 비교가 아니라 오해다.
# 시세도 지역·과목마다 달라 금액 자체로는 순위에 쓸 수 없다.
WEIGHTS = {
    "reputation": 0.35,
    "selectivity": 0.35,
    "momentum": 0.15,
    "transparency": 0.15,
}

# 진입난이도의 축소 사전표본. 평판과 같은 이유다 — 가중치가 0.35 로
# 올라간 만큼 적은 표본이 극단값을 만들면 안 된다.
SELECTIVITY_PRIOR_COUNT = 10

# 등급반별 난이도를 내보낼 최소 표본. 이 아래는 반 이름만 스쳤을 뿐
# 난이도를 말할 수 있는 양이 아니다.
MIN_SAMPLE_FOR_TIER = 5
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "가중치 합이 1이 아닙니다"

# 평판 베이지안 축소 사전 표본수. 후기 소수 학원의 극단값을 막는다.
REPUTATION_PRIOR_COUNT = 12
# 최신성 반감기(일)
RECENCY_HALFLIFE_DAYS = 180
# 순위 노출 최소 표본
MIN_SAMPLE_FOR_RANK = 10
CONFIDENCE_HIGH = 30

# 네이버 수집은 유료 한도가 있는 자원이다. 학원 하나에 3~5질의 × 3소스가
# 나가므로 4,000곳을 전부 돌면 6만 회를 넘긴다. 그래서 예산을 정하고
# 우선순위대로 고른다. 수집하지 않은 학원은 점수를 매기지 않고 등록부에만 남긴다.
NAVER_MAX_ACADEMIES = int(os.getenv("NAVER_MAX_ACADEMIES", "400"))

# 진학 테크트리와 무관한 분야는 등록부에서 제외한다.
# (예능·기예·직업기술·독서실 등)
# 예체능으로 분류할 NEIS 분야구분.
ARTS_REALMS = {"예능(대)", "기예(대)"}

# 기타(그 외 학술·직업). 독서실은 학원이 아니므로 계속 제외한다.
OTHER_REALMS = {"기타(대)", "직업기술", "정보"}

ACADEMIC_REALMS = {
    "입시.검정 및 보습",
    "국제화",
    "종합(대)",
    "인문사회(대)",
}

SUBJECTS = {
    "math": "수학",
    "english": "영어",
    "korean": "국어·논술",
    "science": "과학",
    # 예체능·기타는 성격이 다르다. 진학 경로(테크트리)가 없고 공시로
    # 확인할 것도 적어, 만족도와 화제성 두 축으로만 본다.
    "arts": "예체능",
    "etc": "기타",
}

# 과목 랭킹 어디에도 넣지 않는 분류.
#
# 학술 분야로 공시됐지만 과목이 특정되지 않는 곳(종합·보습·재종·컨설팅)이다.
# 'etc'(기타)로 두면 예체능·기타 랭킹에 학술 학원이 섞인다 — 실제로
# '대치수능선배2관학원' 이 기타 랭킹에 있었다. 등록부에는 남지만 순위는
# 매기지 않는다: 어느 과목으로 견줄지 정할 수 없기 때문이다.
UNRANKED_SUBJECT = "general"

# 트리스코어 네 기둥을 다 적용하는 과목. 나머지는 축소 산식을 쓴다.
ACADEMIC_SUBJECTS = ("math", "english", "korean", "science")

# 예체능·기타 전용 가중치. 평판(만족도)과 화제성만 본다.
#
# 투명성을 빼는 이유: 예능 학원은 교습과정 공시가 '미술', '피아노' 한 줄인
# 경우가 많아 상세도를 점수로 치면 실제 차이가 아니라 공시 습관을 잰다.
# 진입난이도를 빼는 이유: 레벨테스트·대기 개념이 없는 곳이 대부분이라
# 신호가 거의 안 잡힌다. 없는 것을 0점으로 치면 그게 곧 왜곡이다.
NON_ACADEMIC_WEIGHTS = {"reputation": 0.6, "momentum": 0.4}
# 학원이 대상으로 하는 학년대.
#
# 학교(초등학교·중학교·고등학교)와는 다른 축이다. 학교는 건물이고,
# 이건 '몇 학년을 받는 학원인가'다. 섞어 쓰다 헷갈려서 이름을 갈랐다.
#
# 초등을 둘로 나눈 이유: 학원가에서 저학년과 고학년은 사실상 다른 시장이다.
# 예비초~초3 은 사고력·연산·파닉스가 중심이고, 초4~초6 은 경시·선행으로
# 갈린다. 한 덩어리로 두면 학부모가 자기 구간이 아닌 것을 계속 보게 된다.
#
# 값은 (표시명, 최소학년, 최대학년). 예비초1 = 0, 초1 = 1 … 고3 = 12.
# 학년 코드는 유아까지 내려간다(5세 = -2, 6세 = -1, 7세/예비초 = 0).
# 단, 이것은 **테크트리 표시 전용**이다. 랭킹 구간(GRADE_BANDS)은 0부터
# 시작한다 — 5~6세 영유·유아 사고력은 로드맵의 방향 안내일 뿐, 그 나이대
# 학원을 순위에 세울 근거 데이터가 없다. 근거 없는 순위는 만들지 않는다.
GRADE_BANDS = {
    "elem_low": ("예비초~초3", 0, 3),
    "elem_high": ("초4~초6", 4, 6),
    "middle": ("중등", 7, 9),
    "high": ("고등", 10, 12),
}

GRADE_BAND_NAMES = {k: v[0] for k, v in GRADE_BANDS.items()}


def band_for_grade(g: int) -> str:
    """학년 하나가 어느 구간에 드는지."""
    for key, (_, lo, hi) in GRADE_BANDS.items():
        if lo <= g <= hi:
            return key
    return "high" if g > 12 else "elem_low"


def bands_for_range(lo: int, hi: int) -> list[str]:
    """학년 범위가 걸치는 구간 전부. 경계를 걸치는 단계는 양쪽에 든다."""
    return [key for key, (_, blo, bhi) in GRADE_BANDS.items()
            if lo <= bhi and hi >= blo]


def banded_techtree() -> dict:
    """테크트리를 학년 구간별 트랙으로 갈라 준다.

    YAML 은 과목 × 학교급(초·중·고)으로 적혀 있다. 초등 한 덩어리가
    예비초부터 초6까지라 그래프가 길고, 저학년 학부모에게는 절반이
    남의 이야기다. 단계마다 적힌 학년 범위를 보고 구간별로 나눈다.

    경계에 걸친 단계(예: 사고력 초1~초4)는 양쪽에 모두 든다. 실제로
    두 구간에 걸쳐 다니는 단계라 어느 한쪽에서 빼면 길이 끊긴다.

    구간 밖이지만 그 구간으로 들어오는 길의 출발점인 단계는 'inbound'
    로 표시해 함께 남긴다. 빼면 '어디서 오는 길인지'가 사라진다.
    """
    tree = techtree()
    out_tracks = []
    for track in tree["tracks"]:
        stages = track["stages"]
        by_band: dict[str, list[dict]] = {}
        for st in stages:
            # 로드맵 전용 단계(영유 등)는 구간 트리에 넣지 않는다.
            # 랭킹으로 이어지는 화면에 나타나는 순간 '순위 매길 대상'처럼
            # 읽히는데, 그 나이대는 근거 데이터가 없다.
            if st.get("roadmap_only"):
                continue
            lo, hi = st["grade"]
            for band in bands_for_range(lo, hi):
                by_band.setdefault(band, []).append(st)

        # 구간이 하나뿐이면 가르지 않는다. 이름만 새 축으로 바꾼다.
        if len(by_band) <= 1:
            band = next(iter(by_band), track.get("school_level", "high"))
            out_tracks.append({**track, "id": f"{track['subject']}_{band}",
                               "grade_band": band})
            continue

        for band in GRADE_BANDS:
            kept = by_band.get(band)
            if not kept:
                continue
            ids = {st["id"] for st in kept}
            edges = [e for e in track["edges"] if e[1] in ids]
            # 이 구간으로 들어오는 길의 출발점을 끌어온다.
            inbound = {e[0] for e in edges} - ids
            extra = [st for st in stages if st["id"] in inbound]
            band_stages = [
                {**st, "inbound": st["id"] in inbound}
                for st in stages if st["id"] in ids | inbound
            ]
            # depth 를 0부터 다시 매긴다. 구간마다 그래프가 새로 시작한다.
            depths = sorted({st["depth"] for st in band_stages})
            remap = {d: i for i, d in enumerate(depths)}
            for st in band_stages:
                st["depth"] = remap[st["depth"]]

            label = GRADE_BANDS[band][0]
            # 요약은 구간별로 따로 적은 것을 쓴다. 부모 요약을 물려주면
            # 이 구간에 없는 단계(경시·선행 …)를 약속하게 된다.
            summary = (track.get("band_summaries") or {}).get(band)
            out_tracks.append({
                **track,
                "id": f"{track['subject']}_{band}",
                "grade_band": band,
                "title": f"{label} {SUBJECTS[track['subject']]}",
                "summary": summary or track["summary"],
                "stages": band_stages,
                "edges": [e for e in edges
                          if e[0] in ids | inbound and e[1] in ids],
                "sort_order": track["sort_order"] * 10
                + list(GRADE_BANDS).index(band),
            })
            del extra
    for t in out_tracks:
        t.pop("school_level", None)
        t.pop("band_summaries", None)
    return {**tree, "tracks": out_tracks}


def roadmap_payload() -> dict:
    """통합 로드맵 — 과목·구간으로 가르지 않은 전체 그림.

    구간별 트리는 '지금 내 아이 구간'을 보는 데 좋지만, 5세 영어 →
    6세 수학 → 7세 국어 → 초4 재편으로 이어지는 전체 흐름은 과목을
    나란히 놓아야 보인다. 여기서는 로드맵 전용 단계(영유)도 포함한다 —
    방향 안내일 뿐 랭킹과 연결되지 않는다.
    """
    tree = techtree()
    stages, edges = [], []
    for track in tree["tracks"]:
        for st in track["stages"]:
            stages.append({
                "id": st["id"],
                "subject": track["subject"],
                "title": st["title"],
                "subtitle": st.get("subtitle"),
                "goal": st.get("goal"),
                "exit_criteria": st.get("exit_criteria"),
                "grade": st["grade"],
                "lane": st.get("lane", 0),
                "roadmap_only": bool(st.get("roadmap_only")),
            })
        edges.extend(track["edges"])
    return {
        "milestones": tree.get("roadmap_milestones", []),
        "subjects": list(SUBJECTS),
        "stages": stages,
        "edges": edges,
    }


def grade_label(g: int) -> str:
    """-2..12 → '5세'..'고3'."""
    if g <= -2:
        return "5세"
    if g == -1:
        return "6세"
    if g == 0:
        return "예비초"
    if 1 <= g <= 6:
        return f"초{g}"
    if 7 <= g <= 9:
        return f"중{g - 6}"
    if 10 <= g <= 12:
        return f"고{g - 9}"
    return str(g)


def grade_range_label(lo: int, hi: int) -> str:
    return grade_label(lo) if lo == hi else f"{grade_label(lo)}~{grade_label(hi)}"


def load_yaml(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def regions() -> list[dict]:
    return load_yaml("regions.yaml")


@functools.lru_cache(maxsize=1)
def techtree() -> dict:
    """테크트리 원본. **한 번만 읽는다.**

    학원 한 곳의 단계를 정할 때마다 불리는데(실측 6,092회) 그때마다
    530줄 YAML 을 다시 파싱하고 있었다. 반환값을 고쳐 쓰는 곳은 없다 —
    banded_techtree() 도 roadmap_payload() 도 `{**st}` 로 베껴서 쓴다.
    """
    return load_yaml("techtree.yaml")


def seed_academies() -> list[dict]:
    return load_yaml("seed_academies.yaml")["academies"]
