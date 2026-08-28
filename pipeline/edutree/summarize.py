"""글 요약 — 사람이 읽을 한 문단. **선택 기능이다.**

글 페이지의 auto:digest 는 파이프라인이 이미 계산한 것(감성·신뢰도·과목)을
옮겨 적을 뿐이라 새로 추정하는 값이 없다. 그건 정확하지만 건조하다.
'초5 아이 레벨테스트 후기. 대기 3개월, 숙제량 많다는 언급' 같은 한 줄은
사람이 목록을 훑을 때 훨씬 빠르다.

## 없으면 조용히 건너뛴다

키가 없으면 아무 일도 하지 않는다. 요약은 **점수에 쓰이지 않는다** —
auto:summary 블록에만 들어가고 게이트도 산식도 이 값을 보지 않는다.
그러니 없어도 시스템은 온전하다. LLM 이 만든 문장이 점수에 흘러들면
그때부터 산식을 설명할 수 없게 된다.

## 제공자를 갈아끼울 수 있다

점수에 안 쓰이므로 **어느 모델이 썼는지가 산식의 설명을 바꾸지 않는다.**
그래서 값싼 쪽으로 옮겨 다녀도 된다. 실제로 그렇게 됐다 — Anthropic 키는
잔액이 없었고 Gemini 키가 있어서 그쪽으로 붙였다.

    OPENEDU_SUMMARY_PROVIDER  anthropic | gemini (비우면 있는 키로 자동)
    OPENEDU_SUMMARY_MODEL     제공자별 기본값이 있다
    OPENEDU_SUMMARY_WORKERS   동시 호출(기본 8)
    OPENEDU_SUMMARY_PER_RUN   한 실행 상한(기본 200)

제공자를 늘릴 때 건드릴 곳은 `_call_*` 함수 하나뿐이다.

## 한 번만 만든다

url_hash 로 캐시하고 **다시 만들지 않는다.** 같은 글을 매 실행 다시
요약하면 비용이 회차마다 붙고, 문장이 조금씩 달라져 야간 커밋이 잡음이
된다. 원문이 바뀌지 않는 한 요약도 바뀔 이유가 없다.

## 비용

한 실행에 PER_RUN 건까지만 부른다. 9천 장을 한 번에 부르지 않는 이유는
비용을 관리자가 보면서 늘릴 수 있게 하려는 것이다.

건당 2.4초라 순차로는 9,362건에 6시간이 걸린다. 동시 호출로 줄인다 —
실측 16 동시에서 초당 4건, 38분. 중간에 끊겨도 잃지 않도록 진행 중에
캐시를 저장한다(이미 만든 요약은 돈을 주고 산 것이다).
"""
from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config

CACHE = config.CACHE_DIR / "post_summaries.json"


def _env(*names: str) -> str:
    """여러 표기를 함께 받는다. 사람이 .env 를 손으로 쓰기 때문이다 —
    실제로 `Gemini_API_KEY` 처럼 대소문자가 섞여 들어온 적이 있다."""
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""


ANTHROPIC_KEY = _env("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
GEMINI_KEY = _env("GEMINI_API_KEY", "Gemini_API_KEY", "GOOGLE_API_KEY")

# 어느 쪽으로 부를까. 키가 하나뿐이면 그쪽, 둘 다면 gemini 를 먼저 본다
# (대량 요약에서 값이 싸다). 명시하면 그대로 따른다.
_PROVIDER_ENV = _env("OPENEDU_SUMMARY_PROVIDER").lower()
if _PROVIDER_ENV in ("anthropic", "gemini"):
    PROVIDER = _PROVIDER_ENV
elif GEMINI_KEY:
    PROVIDER = "gemini"
elif ANTHROPIC_KEY:
    PROVIDER = "anthropic"
else:
    PROVIDER = ""

# 모델은 관리자가 정한다. 기본값을 낮은 모델로 깔아 두지 않는다 —
# 비용을 이유로 품질을 대신 결정하지 않는다는 뜻이다.
# ★ 빈 문자열과 미설정은 다르다. GitHub Actions 는 정의 안 된 vars 를
#   **빈 문자열**로 넘기므로 os.getenv 의 기본값이 안 먹는다.
#   int("") 는 ValueError 라 야간 작업이 여기서 죽는다.
_DEFAULT_MODEL = {"anthropic": "claude-opus-5", "gemini": "gemini-3.7-flash"}
MODEL = _env("OPENEDU_SUMMARY_MODEL") or _DEFAULT_MODEL.get(PROVIDER, "")

GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/"
              "models/{model}:generateContent")


# 다시 시도해도 소용없는 실패. 9천 번을 더 불러도 같은 답이 온다.
_FATAL = ("credit balance", "billing", "permission", "not_found_error",
          "model not found", "invalid_api_key")


def _fatal(message: str) -> str | None:
    """치명적이면 사람이 읽을 사유, 아니면 None.

    잔액 부족을 재시도로 취급하면 로그가 같은 오류로 도배되고, 정작
    무엇이 문제인지가 안 보인다. 한 번 보고 바로 멈춘다.
    """
    low = message.lower()
    if not any(k in low for k in _FATAL):
        return None
    # API 오류는 dict 를 문자열로 찍은 꼴이라 message 만 뽑아 읽기 쉽게 한다.
    brief = message.split("'message': '")[-1].split("'")[0]
    return (brief or message)[:140]


# 한국어 서술문은 이렇게 끝난다. 잘린 조각은 안 그렇다.
_ENDINGS = (".", "!", "?", "다", "요", "음", "임", "함", ")", "”", "\"")


def _looks_truncated(text: str) -> bool:
    """잘린 요약인가.

    사고 예산을 껐는데도 간헐적으로 출력 자리가 모자라 문장이 중간에
    끊기는 응답이 있었다(실측 1,091건 중 8건: '12월 1일 개', '수학 9').
    지금은 finishReason 으로 막지만, **이미 캐시에 들어간 것**은 다시
    만들지 않으므로 영원히 남는다. 그래서 읽을 때도 한 번 더 본다.
    """
    t = (text or "").strip()
    # ★ 길이로 재지 않는다. '내용 없음.' 은 **본문이 없는 글의 옳은 요약**
    #   인데 짧다는 이유로 잘렸다고 보면 매 실행 다시 만들고, 그때마다
    #   돈이 든다(캐시가 영원히 안 채워지는 셈이다). 끝맺음만 본다.
    return len(t) < 5 or not t.endswith(_ENDINGS)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


PER_RUN = _int_env("OPENEDU_SUMMARY_PER_RUN", 200)
# 동시 호출 수. 올리면 빨라지지만 429 가 늘고, 429 는 그냥 버리는 시간이다.
WORKERS = max(1, min(32, _int_env("OPENEDU_SUMMARY_WORKERS", 8)))
HAS_KEY = bool(PROVIDER)

SYSTEM = """학원 후기 글을 한국어 두 문장 이내로 요약한다.

규칙:
- 글에 **적힌 것만** 쓴다. 추측·해석·평가를 보태지 않는다.
- 학년, 과목, 대기/레벨테스트, 숙제량, 강사 언급 같은 구체를 우선한다.
- 광고·홍보로 보이면 그렇게 적는다.
- 특정인을 비방하는 표현은 옮기지 않는다.
- 학원 이름을 반복하지 않는다. 어느 학원 글인지는 이미 안다.
- 서두("이 글은…") 없이 바로 내용만."""


def status() -> str:
    """자격 증명 확인 화면 한 줄. 왜 안 도는지가 바로 보여야 한다."""
    if not HAS_KEY:
        return "키 없음 — 요약 건너뜀 (선택 기능)"
    if PROVIDER == "anthropic":
        try:
            import anthropic                               # noqa: F401
        except ImportError:
            # anthropic 1.x 는 파이썬 3.10+ 다. 이 사실을 안 적어 두면
            # '키를 넣었는데 왜 안 도나' 를 사람이 한참 찾게 된다.
            ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            hint = (f" — 현재 파이썬 {ver}, anthropic 1.x 는 3.10+ 필요"
                    if sys.version_info < (3, 10) else " (pip install anthropic)")
            return f"키는 있으나 anthropic 패키지 없음{hint}"
    done = len(_load())
    return (f"사용 가능 ✓  {PROVIDER} · 모델 {MODEL} · "
            f"한 실행 {PER_RUN}건 · 누적 {done:,}건")


# ── 제공자별 호출 ────────────────────────────────────────────────
#
# 요약은 이 시스템에서 **가장 갈아끼우기 쉬운 부품**이어야 한다. 점수에
# 쓰이지 않으니 어느 모델이 썼는지가 산식의 설명을 바꾸지 않고, 그래서
# 값싼 쪽으로 옮겨 다녀도 된다. 제공자를 늘릴 때 건드릴 곳은 여기뿐이다.
class _Fatal(RuntimeError):
    """다시 시도해도 소용없는 실패. 바로 멈추라는 신호."""


def _call_gemini(session, body: str, system: str | None = None,
                 max_tokens: int = 2048) -> str:
    """Gemini REST. SDK 를 새로 들이지 않는다 — 호출이 한 종류뿐이라
    requests(이미 의존) 로 충분하다.

    [system]·[max_tokens] 는 이 계층을 요약 말고도 쓰기 위한 것이다
    (claim_llm 이 같은 제공자 배선을 그대로 쓴다). 기본값은 요약이다.
    """
    payload = {
        "system_instruction": {"parts": [{"text": system or SYSTEM}]},
        "contents": [{"parts": [{"text": body}]}],
        "generationConfig": {
            # 두 문장이면 100토큰이면 충분하지만 넉넉히 준다. 사고 예산을
            # 껐는데도 간헐적으로 사고가 도는 듯한 응답이 있었고, 그때
            # 남은 자리가 모자라 문장이 잘렸다(실측 1,091건 중 8건).
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
            # 요약에 사고 예산을 쓰지 않는다. 켜 두면 maxOutputTokens 를
            # 사고가 먼저 먹어 본문이 빈 채로 끝난다.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    r = session.post(GEMINI_URL.format(model=MODEL),
                     params={"key": GEMINI_KEY}, json=payload, timeout=60)
    if r.status_code in (400, 403, 404):
        reason = _fatal(r.text)
        if reason:
            raise _Fatal(reason)
    r.raise_for_status()
    cand = (r.json().get("candidates") or [{}])[0]
    # ★ 잘린 문장을 저장하지 않는다. '12월 1일 개' 같은 조각이 위키에
    #   남으면 요약이 아니라 잡음이고, 캐시라 다시 만들지도 않는다.
    #   STOP 이 아니면 실패로 보고 이번 회차에서 버린다.
    finish = cand.get("finishReason")
    if finish and finish != "STOP":
        raise RuntimeError(f"응답이 끝나지 않았다(finishReason={finish})")
    parts = (cand.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


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


def _anthropic_caller():
    """(호출 함수, 정리 함수). 패키지가 없으면 None."""
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY or None)
    # 요약은 어려운 일이 아니다. 깊이를 낮춰 비용을 줄이는 것은 모델을
    # 낮추는 것과 다르다 — 같은 모델이 덜 생각할 뿐이다.
    #
    # ★ 다만 effort 를 못 받는 모델이 있다. 모델 목록을 코드에 박으면 새
    #   모델이 나올 때마다 낡는다. **한 번 시도해 보고 거부하면 그 실행
    #   동안 끄는** 쪽이 스스로 낫는다.
    state = {"effort": True}

    def call(_session, body: str, system: str | None = None,
             max_tokens: int = 256) -> str:
        sys_prompt = system or SYSTEM
        extra = {"output_config": {"effort": "low"}} if state["effort"] else {}
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=max_tokens, system=sys_prompt,
                messages=[{"role": "user", "content": body}], **extra)
        except anthropic.BadRequestError as exc:
            reason = _fatal(str(exc))
            if reason:
                raise _Fatal(reason) from exc
            if not state["effort"] or "effort" not in str(exc).lower():
                raise
            print(f"  요약: {MODEL} 은 effort 를 안 받는다 — 끄고 계속")
            state["effort"] = False
            resp = client.messages.create(
                model=MODEL, max_tokens=max_tokens, system=sys_prompt,
                messages=[{"role": "user", "content": body}])
        except anthropic.AuthenticationError as exc:
            raise _Fatal("키가 거부됐다 — ANTHROPIC_API_KEY 확인") from exc
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    return call


def collect(mentions: list[dict], limit: int | None = None) -> dict[str, str]:
    """{url_hash: 요약}. 키가 없으면 캐시만 돌려주고 조용히 끝낸다."""
    cache = _load()
    if not HAS_KEY:
        return cache

    import requests

    if PROVIDER == "anthropic":
        call = _anthropic_caller()
        if call is None:
            print(f"  요약: 건너뜀 — {status()}")
            return cache
    else:
        call = _call_gemini

    # 아직 요약이 없는 글. 신뢰도 높은 것부터 — 사람이 먼저 볼 글이다.
    todo: dict[str, dict] = {}
    redo = 0
    for m in mentions:
        h = m.get("url_hash")
        if not h or m.get("source") == "edutree_review":
            continue
        if h in cache:
            # 잘린 채 저장된 것은 다시 만든다. 캐시는 '한 번만 만든다'가
            # 원칙이지만 잘린 조각은 요약이 아니라 잡음이다.
            if not _looks_truncated(cache[h]):
                continue
            redo += 1
        cur = todo.get(h)
        if cur is None or (m.get("credibility") or 0) > (cur.get("credibility") or 0):
            todo[h] = m
    queue = sorted(todo.values(),
                   key=lambda m: -(m.get("credibility") or 0))[:limit or PER_RUN]
    if not queue:
        return cache
    if redo:
        print(f"  요약: 잘린 채 저장된 {redo}건을 다시 만든다")

    # 건당 2.4초라 9,362건이면 순차로 6시간이다. 동시에 부른다.
    # requests.Session 은 스레드마다 따로 둔다 — 연결 풀을 공유시키면
    # 드물게 응답이 섞인다.
    local = threading.local()

    def session_for():
        s = getattr(local, "s", None)
        if s is None:
            s = local.s = requests.Session()
        return s

    lock = threading.Lock()
    stop = threading.Event()
    done = failed = 0
    reason_out: list[str] = []
    # 오래 걸리는 작업이라 중간에 잃지 않는다. 한 번 끊기면 처음부터
    # 다시 부르게 된다 — 이미 만든 요약은 돈을 주고 산 것이다.
    checkpoint = max(50, len(queue) // 40)

    def work(m: dict) -> tuple[str, str] | None:
        if stop.is_set():
            return None
        body = f"제목: {m.get('title') or ''}\n본문: {(m.get('snippet') or '')[:4000]}"
        text = call(session_for(), body)
        return (m["url_hash"], text) if text else None

    print(f"  요약: {len(queue):,}건 · {PROVIDER} {MODEL} · 동시 {WORKERS}")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(work, m): m for m in queue}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                got = fut.result()
                if got:
                    with lock:
                        cache[got[0]] = got[1]
                        done += 1
            except _Fatal as exc:
                # 다시 시도해도 소용없다. 잔액 부족·권한 없음은 9천 번을
                # 더 불러도 같은 답이 온다. 즉시 멈춘다 — 안 그러면 로그가
                # 같은 오류로 도배되고 무엇이 문제인지 오히려 안 보인다.
                if not stop.is_set():
                    stop.set()
                    reason_out.append(str(exc))
            except Exception as exc:                      # noqa: BLE001
                reason = _fatal(str(exc))
                if reason and not stop.is_set():
                    stop.set()
                    reason_out.append(reason)
                    continue
                with lock:
                    failed += 1
                    if failed <= 3:
                        print(f"  ! 요약 실패({type(exc).__name__}) {str(exc)[:90]}")
                    if failed > max(20, len(queue) // 10) and not stop.is_set():
                        stop.set()
                        reason_out.append("실패가 잦아 중단")
            if done and i % checkpoint == 0:
                with lock:
                    _save(cache)
                print(f"    … {i:,}/{len(queue):,} · 신규 {done:,}건 (저장됨)")

    if reason_out:
        print(f"  요약: 중단 — {reason_out[0]}")
    if done or failed:
        _save(cache)
        print(f"  요약: 신규 {done:,}건 ({PROVIDER} {MODEL} · 누적 {len(cache):,}건)"
              + (f" · 실패 {failed}건" if failed else ""))
    return cache
