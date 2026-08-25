"""수요 신호 — 이미 수집한 글이 '다음에 무엇을 수집해야 하는지' 알고 있다.

수집 대상 선정은 정원(수용인원) 순이었다. 학년 구간으로 층을 나눠 재종반
편향은 잡았지만, **구간 안에서는 여전히 정원이 순위를 정한다.** 그래서
반포 초등 영어 후보 69곳 중 자리 19개를 대형 어학원이 가져가고,
학부모가 실제로 이야기하는 소규모 학원(우승희 32명, 잉글리쉬부띠끄 12명)은
영원히 수집되지 않는다. 랭킹에 없는 이유가 '평가해서 낮음'이 아니라
'보지도 않음'인 상태가 한 층 아래에서 반복되고 있었다.

그런데 신호는 이미 우리 손에 있었다. 실측(2026-08-25, 캐시 50,228건):

    해빛나인   176회 등장 · 미수집
    현재어학원   66회 등장 · 미수집
    리딩타운     51회 등장 · 미수집

비교글·나열글은 근거로는 버리지만(analyze 의 나열 판정), **발견의 재료로는
가장 값지다.** '대치 빅3의 프로그램! 피아이 해빛나인 지엘피' 라는 글은
해빛나인이 중요하다고 말하고 있었고, 우리는 그걸 버리기만 했다.

★ 이 신호는 점수에 쓰지 않는다. **수집 대상 선정에만** 쓴다.
  등장 횟수는 '이 학원이 화제다'가 아니라 '이 학원을 아직 안 봤다'를
  말할 뿐이고, 점수는 그 학원을 실제로 수집한 뒤 언급이 정한다.
"""
from __future__ import annotations

import json
from collections import defaultdict

from . import analyze, config

PATH = config.CACHE_DIR / "demand.json"

# 이만큼은 나와야 신호로 친다. 1~2회는 우연한 부분 문자열일 수 있다.
MIN_HITS = 3
# 상한. 한 곳이 수백 회 나온다고 다른 신호를 전부 눌러서는 안 된다.
CAP = 60


def load() -> dict[str, int]:
    if not PATH.exists():
        return {}
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def measure(academies: list[dict], mentions: list[dict]) -> dict[str, int]:
    """등록부 학원 이름이 수집된 글에 몇 번 나오는가.

    학군별로 나눠 센다 — 남의 학군 글에 이름이 겹치는 것까지 세면
    같은 브랜드의 다른 지점 때문에 부풀려진다.
    """
    blobs: dict[str, str] = defaultdict(str)
    parts: dict[str, list[str]] = defaultdict(list)
    for m in mentions:
        parts[m.get("region_id") or ""].append(
            f"{m.get('title', '')} {m.get('snippet', '')}")
    for region, chunks in parts.items():
        blobs[region] = " ".join(chunks)

    out: dict[str, int] = {}
    for a in academies:
        name = a.get("name") or ""
        # 이름이 일상어인 곳은 세지 않는다 — '책읽기' 는 온 세상 글에 나온다.
        if analyze.is_generic_name(name):
            continue
        blob = blobs.get(a.get("region_id") or "", "")
        if not blob:
            continue
        best = 0
        for cand in analyze.name_candidates(a):
            # 짧은 후보는 우연히 겹친다. 통합 대표명 규칙과 같은 하한.
            if len(cand) < 3:
                continue
            best = max(best, blob.count(cand))
        if best >= MIN_HITS:
            out[a["id"]] = min(best, CAP)
    return out


def save(scores: dict[str, int]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
    if scores:
        top = sorted(scores.items(), key=lambda t: -t[1])[:3]
        print(f"  수요 신호: {len(scores):,}곳이 기존 글에 등장 "
              f"(최다 {', '.join(str(v) for _, v in top)}회)")
