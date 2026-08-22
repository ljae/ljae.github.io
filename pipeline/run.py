#!/usr/bin/env python3
"""에듀트리 파이프라인 진입점.

    python pipeline/run.py             # 수집 → 분석 → 채점 → 앱 번들 생성
    python pipeline/run.py --check     # 자격 증명 상태만 확인
    python pipeline/run.py --with-cafe # 카페 로컬 모듈까지 사용 (옵트인, 로컬 전용)
    python pipeline/run.py --test      # 발급받은 키가 실제로 통하는지 호출해 확인
    python pipeline/run.py --from-cache # 캐시로 재채점 (API 호출 없음, 산식 실험용)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edutree import config  # noqa: E402


def check() -> None:
    rows = [
        ("NEIS 학원교습소정보", config.HAS_NEIS, "NEIS_API_KEY",
         "https://open.neis.go.kr/portal/myPage/actKeyPage.do"),
        ("네이버 검색 API", config.HAS_NAVER, "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET",
         "https://console.ncloud.com/naver-api-hub/application  (또는 developers.naver.com)"),
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


def test_keys() -> None:
    """실제로 한 번씩 호출해 본다. 키를 넣자마자 맞는지 바로 알 수 있도록."""
    print("\n실제 호출 테스트\n" + "─" * 62)

    # NEIS
    if not config.HAS_NEIS:
        print("  ✗ NEIS         키 없음 — 건너뜀")
    else:
        from edutree import neis
        try:
            region = config.regions()[0]
            payload = neis._request(1, region["atpt_code"], region["sigungu"])
            rows, total = neis._rows(payload)
            print(f"  ✓ NEIS         정상 — {region['sigungu']} 학원 {total}건 조회")
        except Exception as exc:                      # noqa: BLE001
            print(f"  ✗ NEIS         실패 — {exc}")

    # 네이버
    if not config.HAS_NAVER:
        print("  ✗ 네이버       키 없음 — 건너뜀")
    else:
        from edutree import naver
        any_ok = False
        for mode in naver.MODE_ORDER:
            ok, detail = naver.probe(mode)
            mark = "✓" if ok else "✗"
            print(f"  {mark} 네이버 {mode:<6} {naver.MODES[mode]['label']}")
            if not ok:
                print(f"                 {detail}")
            any_ok = any_ok or ok
        if any_ok:
            try:
                rows = naver.search("naver_cafe", "대치 학원 후기", max_results=3)
                print(f"  ✓ 카페글 검색  {len(rows)}건 수신")
                for r in rows[:2]:
                    print(f"                 · {r['title'][:44]}")
            except Exception as exc:                  # noqa: BLE001
                print(f"  ✗ 카페글 검색  실패 — {exc}")
        else:
            print("     두 방식 모두 실패했습니다. 키를 다시 확인하세요.")

    # Supabase
    if not config.HAS_SUPABASE:
        print("  ✗ Supabase     키 없음 — 건너뜀 (선택 사항)")
    else:
        import requests
        try:
            r = requests.get(
                f"{config.SUPABASE_URL}/rest/v1/regions?select=id&limit=1",
                headers={"apikey": config.SUPABASE_SERVICE_KEY,
                         "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}"},
                timeout=15)
            print(f"  {'✓' if r.status_code < 300 else '✗'} Supabase     HTTP {r.status_code}")
        except Exception as exc:                      # noqa: BLE001
            print(f"  ✗ Supabase     실패 — {exc}")

    print("─" * 62 + "\n")


if __name__ == "__main__":
    if "--test" in sys.argv:
        check()
        test_keys()
    elif "--check" in sys.argv:
        check()
    else:
        from edutree.build import run
        check()
        result = run(with_cafe="--with-cafe" in sys.argv,
                     from_cache="--from-cache" in sys.argv)
        print(f"\n완료: {result}")
