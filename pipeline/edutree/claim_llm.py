"""LLM 사실 추출 — **값을 만들지 않고 문장을 가리킨다.**

CLAUDE.md 는 못박아 두었다: *"LLM 문장이 산식에 흘러들면 그때부터 산식을
설명할 수 없다."* summarize.py 가 점수에 안 쓰이는 이유가 그것이다.
이 모듈은 그 선을 넘지 않는다. 경계가 셋이다.

  ① **기둥 점수(평판·진입난이도)에는 쓰지 않는다.** 규칙 추출만 쓴다.
     산식은 지금처럼 결정적이다.
  ② **원문 인용문을 반드시 함께 뱉게 하고, 그 인용문이 원문의 글자 그대로의
     부분 문자열이 아니면 버린다.** 기계가 검증할 수 있고 화면에도 그
     문장이 그대로 나간다. 지어낼 자리가 없다.
  ③ **사실 카드는 트리스코어에 들어가지 않는다.** 학부모에게 보여주는
     정보일 뿐 순위를 바꾸지 않는다.

그래서 제공자를 갈아끼울 수 있다 — 요약과 같은 성질이다. 배선은
summarize 의 것을 그대로 쓴다(제공자를 늘릴 때 건드릴 곳이 한 군데로 남는다).

규칙 추출이 아무것도 못 찾은 글에만 부른다. 규칙이 잡은 것을 다시 물어봐야
비용만 든다. 캐시는 (url_hash|academy_key) 로 잡아 한 번만 만든다.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import claims, config, summarize

CACHE = config.CACHE_DIR / "claim_llm.json"

# 한 실행에 부를 최대 건수. 사실 카드는 순위를 바꾸지 않으므로 급할 게
# 없다 — 회차가 쌓이며 늘면 된다.
LIMIT = summarize._int_env("OPENEDU_CLAIM_LLM_LIMIT", 300)
WORKERS = summarize._int_env("OPENEDU_CLAIM_LLM_WORKERS", 4)

# 뽑을 항목. 규칙 추출과 같은 종류만 받는다 — 새 종류를 LLM 이 만들어
# 내면 그 종류가 무엇을 뜻하는지 아무도 정한 적이 없게 된다.
_ALLOWED = {
    "homework": ("fact.homework", "분/일"),
    "test_freq": ("fact.test_freq", "회/월"),
    "class_freq": ("fact.class_freq", "회/주"),
    "class_minutes": ("fact.class_minutes", "분"),
}

SYSTEM = """너는 한국 학원 후기에서 **운영 사실**만 뽑는다.

뽑을 것은 넷뿐이다.
  homework       숙제량 (분/일)
  test_freq      정기 시험 횟수 (회/월) — 레벨테스트·입반테스트는 제외
  class_freq     수업 횟수 (회/주)
  class_minutes  1회 수업 길이 (분)

규칙:
- 지정된 학원에 대한 값만 뽑는다. 글에 다른 학원이 나오면 그쪽 값은 버린다.
- **quote 는 원문에서 글자 그대로 복사한다.** 고치거나 줄이거나 띄어쓰기를
  바꾸지 않는다. 원문에 없는 문장은 절대 쓰지 않는다.
- 묻는 글·전해 들은 말·계획("~할까요", "~라던데")은 사실이 아니다. 버린다.
- 부정문("숙제 10분도 못")은 값이 아니다. 버린다.
- 확실하지 않으면 뽑지 않는다. 빈 배열이 정답인 경우가 대부분이다.

JSON 만 출력한다. 설명하지 않는다.
{"facts":[{"kind":"class_freq","value":3,"value_high":null,"quote":"원문 그대로"}]}
"""


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _load() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(data: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                     encoding="utf-8")


def _parse(raw: str) -> list[dict]:
    """모델 출력 → 항목 목록. 형식이 어긋나면 통째로 버린다."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    got = data.get("facts") if isinstance(data, dict) else data
    return got if isinstance(got, list) else []


def verify(items: list[dict], source: str) -> list[dict]:
    """★ 이 함수가 이 모듈의 존재 이유다.

    인용문이 원문에 **글자 그대로** 있어야 통과한다. 띄어쓰기만 무시한다 —
    모델이 '주3회' 를 '주 3회' 로 적는 정도는 같은 문장이지만, 없는 문장을
    지어낸 것은 여기서 전부 걸린다.
    """
    flat = _norm(source)
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = _ALLOWED.get(str(it.get("kind") or ""))
        quote = str(it.get("quote") or "").strip()
        if not kind or not quote or _norm(quote) not in flat:
            continue
        try:
            lo = float(it.get("value"))
        except (TypeError, ValueError):
            continue
        hi = it.get("value_high")
        try:
            hi = float(hi) if hi is not None else None
        except (TypeError, ValueError):
            hi = None
        if not (0 < lo <= 600) or (hi is not None and not (lo <= hi <= 600)):
            continue
        out.append({"kind": kind[0], "unit": kind[1], "value": round(lo, 1),
                    "value_high": round(hi, 1) if hi and hi != lo else None,
                    "quote": quote})
    return out


def _body(mention: dict, name: str) -> str:
    return (f"학원: {name}\n제목: {mention.get('title') or ''}\n"
            f"본문: {mention.get('snippet') or ''}")


def collect(mentions: list[dict], rule_rows: list[dict],
            names: dict[str, str]) -> list[dict]:
    """규칙이 못 찾은 글에서 사실을 더 뽑는다. 키가 없으면 캐시만 쓴다."""
    cache = _load()
    covered = {(r["url_hash"], r["academy_key"]) for r in rule_rows
               if r["kind"] in claims.FACT_KINDS}

    todo: list[tuple[str, dict]] = []
    for m in mentions:
        if m.get("is_excluded") or m.get("substance", 0) < 2:
            continue
        key = f"{m.get('url_hash')}|{m.get('academy_key')}"
        if key in cache or (m.get("url_hash"), m.get("academy_key")) in covered:
            continue
        todo.append((key, m))

    if todo and summarize.HAS_KEY:
        _run(todo[:LIMIT], names, cache)
        _save(cache)
    elif todo:
        print(f"  사실 추출(LLM): 키 없음 — 건너뜀 (대기 {len(todo):,}건)")

    # 캐시에 있는 것을 전부 주장으로 바꾼다. 키가 없어도 지난 회차 결과는
    # 그대로 살아 있다.
    out: list[dict] = []
    for m in mentions:
        if m.get("is_excluded"):
            continue
        key = f"{m.get('url_hash')}|{m.get('academy_key')}"
        for it in cache.get(key) or []:
            anchor = (f'{it["value"]}~{it["value_high"]}'
                      if it.get("value_high") is not None else str(it["value"]))
            out.append({
                "id": claims.claim_id(m.get("url_hash"), m.get("academy_key"),
                                      it["kind"], anchor),
                "url_hash": m.get("url_hash"),
                "academy_key": m.get("academy_key"),
                "kind": it["kind"],
                "value": it["value"],
                "value_high": it.get("value_high"),
                "unit": it["unit"],
                "quote": it["quote"],
                # 화면이 이걸 구분해 적어야 한다. 규칙과 LLM 을 같은
                # 얼굴로 보여주면 다음 사람이 둘을 같은 근거로 읽는다.
                "extractor": f"llm:{summarize.PROVIDER}",
                "posted_at": m.get("posted_at"),
                "author_hash": m.get("author_hash"),
                "source_url": m.get("source_url"),
                "band": m.get("band"),
                "status": "active",
            })
    return out


def _run(todo: list[tuple[str, dict]], names: dict[str, str],
         cache: dict) -> None:
    import requests
    caller = (summarize._anthropic_caller()
              if summarize.PROVIDER == "anthropic" else summarize._call_gemini)
    if caller is None:
        return
    print(f"  사실 추출(LLM): {len(todo):,}건 · {summarize.PROVIDER} "
          f"{summarize.MODEL} · 동시 {WORKERS}")

    session = requests.Session()
    stopped = {"why": None}

    def one(item):
        key, m = item
        if stopped["why"]:
            return key, None
        name = names.get(m.get("academy_key")) or m.get("academy_name") or ""
        try:
            raw = caller(session, _body(m, name), SYSTEM, 1024)
        except summarize._Fatal as exc:
            # 소용없는 재시도를 하지 않는다. 잔액 부족·권한 없음은
            # 9천 번을 더 불러도 같은 답이 온다.
            stopped["why"] = str(exc)
            return key, None
        except Exception:                                     # noqa: BLE001
            return key, None
        return key, verify(_parse(raw), _body(m, name))

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(one, it) for it in todo]
        for f in as_completed(futures):
            key, got = f.result()
            if got is None:
                continue
            cache[key] = got            # 빈 목록도 캐시한다. 다시 묻지 않는다
            done += len(got)
    if stopped["why"]:
        print(f"  사실 추출(LLM): 중단 — {stopped['why']}")
    else:
        print(f"  사실 추출(LLM): {done:,}건 확보 (인용문 검증 통과분만)")


def status() -> str:
    if not summarize.HAS_KEY:
        return "✗ 키 없음 (규칙 추출만 동작)"
    return f"사용 가능 ✓  {summarize.PROVIDER} · {summarize.MODEL}"
