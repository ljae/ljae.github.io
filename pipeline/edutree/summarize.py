"""글 요약 — 사람이 읽을 한 문단. **선택 기능이다.**

글 페이지의 auto:digest 는 파이프라인이 이미 계산한 것(감성·신뢰도·과목)을
옮겨 적을 뿐이라 새로 추정하는 값이 없다. 그건 정확하지만 건조하다.
'초5 아이 레벨테스트 후기. 대기 3개월, 숙제량 많다는 언급' 같은 한 줄은
사람이 목록을 훑을 때 훨씬 빠르다.

## 없으면 조용히 건너뛴다

`ANTHROPIC_API_KEY` 가 없거나 `anthropic` 패키지가 없으면 아무 일도 하지
않는다. 요약은 **점수에 쓰이지 않는다** — auto:summary 블록에만 들어가고
게이트도 산식도 이 값을 보지 않는다. 그러니 없어도 시스템은 온전하다.
LLM 이 만든 문장이 점수에 흘러들면 그때부터 산식을 설명할 수 없게 된다.

## 한 번만 만든다

url_hash 로 캐시하고 **다시 만들지 않는다.** 같은 글을 매 실행 다시
요약하면 비용이 회차마다 붙고, 문장이 조금씩 달라져 야간 커밋이 잡음이
된다. 원문이 바뀌지 않는 한 요약도 바뀔 이유가 없다.

## 비용

한 실행에 PER_RUN 건까지만 부른다. 9천 장을 한 번에 부르지 않는 이유는
비용을 관리자가 보면서 늘릴 수 있게 하려는 것이다. 대량으로 밀어야 하면
Message Batches(비용 50%)가 맞는 자리다 — 다만 비동기라 야간 작업 흐름이
복잡해지므로 지금은 동기 호출에 상한을 뒀다.

    OPENEDU_SUMMARY_MODEL   기본 claude-opus-5. 대량이면 관리자가 정한다.
    OPENEDU_SUMMARY_PER_RUN 기본 200.
"""
from __future__ import annotations

import json
import os

from . import config

CACHE = config.CACHE_DIR / "post_summaries.json"

# 모델은 관리자가 정한다. 기본값을 낮은 모델로 깔아 두지 않는다 —
# 비용을 이유로 품질을 대신 결정하지 않는다는 뜻이다.
MODEL = os.getenv("OPENEDU_SUMMARY_MODEL", "claude-opus-5").strip()
PER_RUN = int(os.getenv("OPENEDU_SUMMARY_PER_RUN", "200"))
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY", "").strip()
               or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip())

SYSTEM = """학원 후기 글을 한국어 두 문장 이내로 요약한다.

규칙:
- 글에 **적힌 것만** 쓴다. 추측·해석·평가를 보태지 않는다.
- 학년, 과목, 대기/레벨테스트, 숙제량, 강사 언급 같은 구체를 우선한다.
- 광고·홍보로 보이면 그렇게 적는다.
- 특정인을 비방하는 표현은 옮기지 않는다.
- 학원 이름을 반복하지 않는다. 어느 학원 글인지는 이미 안다.
- 서두("이 글은…") 없이 바로 내용만."""


def _load() -> dict[str, str]:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(data: dict[str, str]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                     encoding="utf-8")


def collect(mentions: list[dict], limit: int | None = None) -> dict[str, str]:
    """{url_hash: 요약}. 키가 없으면 캐시만 돌려주고 조용히 끝낸다."""
    cache = _load()
    if not HAS_KEY:
        return cache
    try:
        import anthropic
    except ImportError:
        print("  요약: anthropic 패키지 없음 — 건너뜀 "
              "(pip install anthropic)")
        return cache

    # 아직 요약이 없는 글. 신뢰도 높은 것부터 — 사람이 먼저 볼 글이다.
    todo: dict[str, dict] = {}
    for m in mentions:
        h = m.get("url_hash")
        if not h or h in cache or m.get("source") == "edutree_review":
            continue
        cur = todo.get(h)
        if cur is None or (m.get("credibility") or 0) > (cur.get("credibility") or 0):
            todo[h] = m
    queue = sorted(todo.values(),
                   key=lambda m: -(m.get("credibility") or 0))[:limit or PER_RUN]
    if not queue:
        return cache

    client = anthropic.Anthropic()
    done = failed = 0
    for m in queue:
        body = f"제목: {m.get('title') or ''}\n본문: {(m.get('snippet') or '')[:4000]}"
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=256,
                system=SYSTEM,
                # 요약은 어려운 일이 아니다. 깊이를 낮춰 비용을 줄이는 것은
                # 모델을 낮추는 것과 다르다 — 같은 모델이 덜 생각할 뿐이다.
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": body}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                cache[m["url_hash"]] = text
                done += 1
        except anthropic.RateLimitError:
            print("  요약: 요청 한도 — 이번 회차는 여기까지")
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            failed += 1
            if failed <= 3:
                print(f"  ! 요약 실패({type(exc).__name__})")
            if failed > 10:
                print("  요약: 실패가 잦아 중단")
                break

    if done or failed:
        _save(cache)
        print(f"  요약: 신규 {done}건 (모델 {MODEL} · 누적 {len(cache):,}건)"
              + (f" · 실패 {failed}건" if failed else ""))
    return cache
