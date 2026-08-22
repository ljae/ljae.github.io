"""설정 · 상수 · 경로."""
from __future__ import annotations

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
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

HAS_NEIS = bool(NEIS_API_KEY)
HAS_NAVER = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)
HAS_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

# ── 트리스코어 가중치 (docs/SPEC.md §4 와 반드시 일치) ──────────────
WEIGHTS = {
    "reputation": 0.35,
    "momentum": 0.20,
    "transparency": 0.25,
    "selectivity": 0.20,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "가중치 합이 1이 아닙니다"

# 평판 베이지안 축소 사전 표본수. 후기 소수 학원의 극단값을 막는다.
REPUTATION_PRIOR_COUNT = 12
# 최신성 반감기(일)
RECENCY_HALFLIFE_DAYS = 180
# 순위 노출 최소 표본
MIN_SAMPLE_FOR_RANK = 10
CONFIDENCE_HIGH = 30

SUBJECTS = {
    "math": "수학",
    "english": "영어",
    "korean": "국어·논술",
    "science": "과학",
}
SCHOOL_LEVELS = {
    "elementary": "초등",
    "middle": "중등",
    "high": "고등",
}


def grade_label(g: int) -> str:
    """1..12 → '초1'..'고3'."""
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


def techtree() -> dict:
    return load_yaml("techtree.yaml")


def seed_academies() -> list[dict]:
    return load_yaml("seed_academies.yaml")["academies"]
