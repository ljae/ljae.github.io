"""학원실록 자체 후기를 평판 점수에 반영한다.

스크랩한 커뮤니티 글과 성격이 다르다. 작성자가 로그인해 있고, 별점이
구조화돼 있고, 학원당 1인 1건으로 제한된다. 그래서 신뢰도를 높게 준다.

Supabase 키가 없으면 빈 결과를 돌려주고 파이프라인은 그대로 진행한다.
"""
from __future__ import annotations

import requests

from . import config

# 자체 후기의 신뢰도. 스크랩 스니펫의 상한(약 0.65)보다 높게 둔다.
# 로그인·구조화·1인1건이라는 조건이 붙어 있어서다.
REVIEW_CREDIBILITY = 0.9

# 재원 증빙이 확인된 후기. 여기가 우리가 가진 가장 단단한 근거다.
# 1.0 을 주지 않는 이유: 확인한 것은 '다녔다'이지 '이 평가가 옳다'가 아니다.
VERIFIED_CREDIBILITY = 0.96


def fetch_summaries() -> dict[str, dict]:
    """학원별 후기 요약. {academy_key: {count, avg_rating}}"""
    if not config.HAS_SUPABASE:
        return {}
    try:
        resp = requests.get(
            f"{config.SUPABASE_URL}/rest/v1/v_review_summary",
            params={"select": "academy_key,review_count,avg_rating,"
                              "verified_count,verified_avg"},
            headers={
                "apikey": config.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  후기 요약 조회 실패: {exc}")
        return {}
    if resp.status_code != 200:
        print(f"  후기 요약 조회 실패 {resp.status_code}")
        return {}
    return {r["academy_key"]: r for r in resp.json()}


def as_mentions(summaries: dict[str, dict]) -> list[dict]:
    """요약을 언급 형태로 바꿔 기존 채점 로직에 그대로 태운다.

    후기 하나하나를 가져오지 않는 이유: 본문을 파이프라인에 복사해 두면
    보관 범위가 넓어진다. 점수에 필요한 것은 별점 평균과 건수뿐이다.
    """
    out = []
    for key, row in summaries.items():
        count = int(row.get("review_count") or 0)
        avg = float(row.get("avg_rating") or 0)
        if not count:
            continue
        verified = int(row.get("verified_count") or 0)
        v_avg = float(row.get("verified_avg") or avg)

        def emit(n: int, mean: float, cred: float, tag: str) -> None:
            # 1~5 별점을 -1~+1 감성으로 선형 변환
            sentiment = round((mean - 3.0) / 2.0, 3)
            for i in range(n):
                out.append({
                    "source": "edutree_review",
                    "source_url": f"internal://review/{key}/{tag}{i}",
                    "url_hash": f"rv{tag}{key}{i}",
                    "academy_key": key,
                    "title": "학원실록 후기",
                    "snippet": "",
                    "posted_at": None,
                    "sentiment": sentiment,
                    "credibility": cred,
                    "spam_score": 0.0,
                    "is_excluded": False,
                    "aspects": {},
                    "selectivity": {"hard": 0, "wait": 0},
                })

        # 인증분과 나머지를 나눠 싣는다. 신뢰도가 다르므로 한 덩어리로
        # 평균 내면 인증의 의미가 사라진다.
        emit(verified, v_avg, VERIFIED_CREDIBILITY, "v")
        rest = count - verified
        if rest > 0:
            # 전체 평균에서 인증분을 빼 나머지 평균을 되돌린다.
            rest_avg = ((avg * count) - (v_avg * verified)) / rest
            emit(rest, rest_avg, REVIEW_CREDIBILITY, "u")
    return out
