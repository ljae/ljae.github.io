#!/usr/bin/env python3
"""에듀트리 파이프라인 진입점.

    python pipeline/run.py             # 수집 → 분석 → 채점 → 앱 번들 생성
    python pipeline/run.py --check     # 자격 증명 상태만 확인
    python pipeline/run.py --with-cafe # 카페 로컬 모듈까지 사용 (옵트인, 로컬 전용)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edutree import config  # noqa: E402


def check() -> None:
    rows = [
        ("NEIS 학원교습소정보", config.HAS_NEIS, "NEIS_API_KEY", "https://open.neis.go.kr"),
        ("네이버 검색 API", config.HAS_NAVER, "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET",
         "https://developers.naver.com/apps"),
        ("Supabase", config.HAS_SUPABASE, "SUPABASE_URL / SUPABASE_SERVICE_KEY",
         "https://supabase.com/dashboard"),
    ]
    print("\n자격 증명 상태\n" + "─" * 62)
    for name, ok, env, url in rows:
        print(f"  {'✓' if ok else '✗'}  {name:<22} {env}")
        if not ok:
            print(f"     발급: {url}")
    mode = "live" if (config.HAS_NEIS or config.HAS_NAVER) else "demo"
    print("─" * 62)
    print(f"  실행 모드: {mode}")
    if mode == "demo":
        print("  → 합성 샘플 데이터로 앱이 완전히 동작합니다. docs/SETUP.md 참고.")
    print()


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        from edutree.build import run
        check()
        result = run(with_cafe="--with-cafe" in sys.argv)
        print(f"\n완료: {result}")
