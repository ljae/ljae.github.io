"""학원 프로필 — 후기 N건을 카드 한 장으로. **점수에 쓰지 않는다.**

한 학부모가 AI 로 오픈채팅·검색을 긁어 만든 블로그 요약이 '실제 체감과
가깝다' 는 평을 받았다(docs/PROFILES.md). 형식이 답이었다 — 학원마다 네 칸:
레테 / 숙제 / 커리큘럼 / 잘 맞는 아이·주의 (+ 위치·운영). 점수 한 줄로는
안 읽히던 것이 이 칸들로 읽힌다.

같은 카드를 **우리 근거로** 만든다. 그 블로그와 다른 점 둘.
1. 모든 문장이 원문 인용을 갖는다. 인용이 발췌에 글자 그대로 없으면 그 인용을
   버리고, 서로 다른 글 2건이 받치지 않는 절은 통째로 비운다
   (`claim_llm.verify` 와 같은 규칙 — 지어낼 자리가 없다).
2. 점수·순위·정렬 어디에도 쓰지 않는다. 요약(summarize)·사실 추출(claim_llm)
   과 같은 층이다. LLM 문장이 산식에 흘러들면 산식을 설명할 수 없다.

    build.run → 게이트·주장 뒤, export 앞
      pick     학원별 근거를 신뢰도순 40건 (표본 15건 미만은 만들지 않는다)
      excerpts 글마다 이름 곁 300자, 번호 [1]…[40] (+ [S1] 학원 자기 서술)
      call     JSON 만. 인용마다 ref 번호
      verify   quote ⊂ excerpt[ref] (띄어쓰기 무시) · 어휘 · 문턱
      cache    .cache/profiles.json — 근거가 20% 넘게 바뀌거나 30일 지나야 다시

`--from-cache` 는 캐시만 읽는다. `OPENEDU_PROFILE_PER_RUN=0` 이면 부르지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from . import config, evidence, summarize

CACHE = config.CACHE_DIR / "profiles.json"
PROMPT_VERSION = 1

MIN_SAMPLE = summarize._int_env("OPENEDU_PROFILE_MIN_SAMPLE", 15)
PER_RUN = summarize._int_env("OPENEDU_PROFILE_PER_RUN", 40)
WORKERS = max(1, min(8, summarize._int_env("OPENEDU_PROFILE_WORKERS", 4)))
MAX_EXCERPTS = 40
EXCERPT_WIDTH = 300
MAX_CHARS = 14000            # 한 학원의 입력 상한. 넘치면 신뢰도 낮은 것부터 뺀다
REFRESH_DAYS = 30
CHANGE_RATIO = 0.2           # 근거 목록이 이만큼 바뀌면 다시 만든다
QUOTE_MAX = 120

BANDS = ("S+", "S", "A+", "A", "B+", "B", "C")
LOADS = ("상", "중상", "중", "중하", "하")
SECTIONS = ("levelTest", "homework", "curriculum", "fit", "ops")
# 절마다 받쳐야 하는 서로 다른 글 수. 운영(셔틀·주차)은 학원 자기 서술 1건이면 된다.
MIN_SOURCES = {"levelTest": 2, "homework": 2, "curriculum": 2, "fit": 2, "ops": 1}
# 학원이 스스로 '숙제 적당' 이라 말한 것은 학부모 후기가 아니다.
PARENT_ONLY = {"levelTest", "homework", "fit"}

_PHONE = re.compile(r"01[016-9][-\s]?\d{3,4}[-\s]?\d{4}|0\d{1,2}-\d{3,4}-\d{4}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_WS = re.compile(r"[\s​﻿]+")

SYSTEM = """너는 학부모 후기 발췌를 읽고 학원 한 곳의 **프로필 카드**를 쓴다.
발췌는 [번호] 로 시작한다. [S1] 처럼 S 가 붙은 것은 학원이 스스로 밝힌 소개다.

다섯 칸을 채운다. 각 칸의 quotes 에는 **발췌에 글자 그대로 있는 문장**만
≤120자로 옮기고 그 발췌의 ref 번호를 함께 적는다. 발췌에 없는 문장을 인용으로
만들면 그 칸은 통째로 버려진다. 근거가 모자라면 그 칸을 null 로 둔다 — 억지로
채우지 않는다.

- levelTest: band 는 S+·S·A+·A·B+·B·C 중 하나. hard 는 무엇이 어려운지
  ≤12자('문제 자체' · '컷·인터뷰' · '라이팅' 처럼). note 한 문장.
- homework: load 는 상·중상·중·중하·하 중 하나. note 한 문장(양·난도·시기 변화).
- curriculum: note 한 문장(교재·영역·수업 방식·반 구성).
- fit: goodFor 는 '이런 아이·이런 집' ≤4개 각 ≤40자, caution 은 '확인할 것' ≤4개.
- ops: note 한 문장(위치·셔틀·주차·설명회), shuttle 은 true/false/null.

지킬 것: 사람 이름·닉네임·아이 점수·전화번호는 옮기지 않는다. 학원 이름을
반복하지 않는다. 광고·홍보 문장은 인용하지 않는다. 한 사람의 말을 학원의
성격으로 적지 않는다 — 두 글 이상이 같은 말을 할 때만 note 에 적는다.

JSON 만 출력한다. 설명하지 않는다.
{"levelTest":{"band":"S","hard":"컷·라이팅","note":"…","quotes":[{"ref":3,"quote":"…"}]},
 "homework":{"load":"중상","note":"…","quotes":[{"ref":1,"quote":"…"}]},
 "curriculum":{"note":"…","quotes":[…]},
 "fit":{"goodFor":["…"],"caution":["…"],"quotes":[…]},
 "ops":{"note":"…","shuttle":false,"quotes":[{"ref":"S1","quote":"…"}]}}"""


# ── 입력 ────────────────────────────────────────────────────────
def _norm(text: str) -> str:
    return _WS.sub("", text or "")


def pick(rows: list[dict], limit: int = MAX_EXCERPTS) -> list[dict]:
    """근거를 신뢰도순으로, 글마다 한 번만."""
    seen: set[str] = set()
    out: list[dict] = []
    for m in sorted(rows, key=lambda m: (-float(m.get("credibility") or 0),
                                         -int(m.get("substance") or 0))):
        if m.get("is_excluded"):
            continue
        h = m.get("url_hash") or ""
        if not h or h in seen:
            continue
        seen.add(h)
        out.append(m)
        if len(out) >= limit:
            break
    return out


def excerpts(rows: list[dict], candidates, self_note: dict | None = None,
             width: int = EXCERPT_WIDTH) -> list[dict]:
    """[{ref, kind, text, url_hash, url, posted_at}] — 이름 곁을 잘라 번호를 매긴다."""
    out: list[dict] = []
    total = 0
    for i, m in enumerate(rows, 1):
        ex = evidence.excerpt(m, candidates or set(), width=width)
        text = (ex.get("text") or "").strip()
        title = (m.get("title") or "").strip()
        if not text:
            text = (m.get("snippet") or "")[:width]
        body = f"{title} / {text}" if title else text
        if total + len(body) > MAX_CHARS:
            break
        total += len(body)
        out.append({"ref": str(i), "kind": "parent", "text": body,
                    "url_hash": m.get("url_hash"), "url": m.get("source_url"),
                    "posted_at": (m.get("posted_at") or None)})
    if self_note and (self_note.get("text") or "").strip():
        out.append({"ref": "S1", "kind": "self",
                    "text": self_note["text"][:1500],
                    "url_hash": self_note.get("url_hash") or "self",
                    "url": self_note.get("url"), "posted_at": None})
    return out


def fingerprint(exs: list[dict]) -> str:
    keys = sorted(str(e.get("url_hash")) for e in exs)
    return hashlib.sha1(("|".join(keys) + f"#v{PROMPT_VERSION}").encode()).hexdigest()


def body(name: str, exs: list[dict]) -> str:
    lines = [f"학원: {name}", ""]
    for e in exs:
        lines.append(f"[{e['ref']}] {e['text']}")
    return "\n".join(lines)


# ── 출력 검증 — 이 모듈의 존재 이유 ──────────────────────────────
def parse(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_quote(q: str) -> str:
    q = (q or "").strip().strip("\"'“”‘’")
    return q


def _verify_quotes(items, exs: list[dict], parent_only: bool) -> list[dict]:
    by_ref = {e["ref"]: e for e in exs}
    out: list[dict] = []
    seen: set[str] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        ref = str(it.get("ref") or "").strip().upper()
        e = by_ref.get(ref)
        quote = _clean_quote(str(it.get("quote") or ""))
        if not e or not quote or len(quote) > QUOTE_MAX:
            continue
        if _norm(quote) not in _norm(e["text"]):
            continue                       # 지어낸 문장. 여기서 전부 걸린다
        if _PHONE.search(quote) or _EMAIL.search(quote):
            continue
        if parent_only and e["kind"] != "parent":
            continue
        if quote in seen:
            continue
        seen.add(quote)
        out.append({"quote": quote, "url": e.get("url"),
                    "urlHash": e.get("url_hash"), "postedAt": e.get("posted_at"),
                    "kind": e["kind"]})
    return out


def _short(s, limit: int) -> str | None:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:limit] if s else None


def _list(v, n: int = 4, limit: int = 40) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        s = _short(x, limit)
        if s and s not in out:
            out.append(s)
        if len(out) >= n:
            break
    return out


def verify(data: dict, exs: list[dict]) -> dict | None:
    """모델 출력 → 화면 계약. 절마다 문턱을 못 넘으면 null, 전부 null 이면 None."""
    result: dict = {}
    for sec in SECTIONS:
        raw = data.get(sec) if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            result[sec] = None
            continue
        quotes = _verify_quotes(raw.get("quotes"), exs, sec in PARENT_ONLY)
        distinct = {q["urlHash"] for q in quotes}
        if len(distinct) < MIN_SOURCES[sec]:
            result[sec] = None
            continue
        section: dict = {"note": _short(raw.get("note"), 140), "quotes": quotes}
        if sec == "levelTest":
            band = str(raw.get("band") or "").strip()
            if band not in BANDS:
                result[sec] = None
                continue
            section["band"] = band
            section["hard"] = _short(raw.get("hard"), 12)
        elif sec == "homework":
            load = str(raw.get("load") or "").strip()
            if load not in LOADS:
                result[sec] = None
                continue
            section["load"] = load
        elif sec == "fit":
            section["goodFor"] = _list(raw.get("goodFor"))
            section["caution"] = _list(raw.get("caution"))
            if not section["goodFor"] and not section["caution"]:
                result[sec] = None
                continue
        elif sec == "ops":
            sh = raw.get("shuttle")
            section["shuttle"] = sh if isinstance(sh, bool) else None
        if not section["note"] and sec in ("curriculum", "ops"):
            result[sec] = None
            continue
        result[sec] = section
    if all(result[s] is None for s in SECTIONS):
        return None
    return result


def one_liner(p: dict | None) -> str | None:
    """카드 한 줄. 모델 문장을 그대로 올리지 않는다 — 어휘값과 앞 몇 글자만."""
    if not p:
        return None
    parts = []
    lt, hw, cu = p.get("levelTest"), p.get("homework"), p.get("curriculum")
    if lt and lt.get("band"):
        parts.append(f"레테 {lt['band']}")
    if hw and hw.get("load"):
        parts.append(f"숙제 {hw['load']}")
    if cu and cu.get("note"):
        head = re.split(r"[·,.;/(]", cu["note"])[0].strip()
        if head:
            parts.append(head[:14])
    return " · ".join(parts) or None


# ── 캐시 ────────────────────────────────────────────────────────
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


def _stale(entry: dict | None, hashes: set[str], today: date) -> bool:
    if not entry or entry.get("version") != PROMPT_VERSION:
        return True
    try:
        made = date.fromisoformat(str(entry.get("generated_at"))[:10])
        if (today - made).days >= REFRESH_DAYS:
            return True
    except (TypeError, ValueError):
        return True
    old = set(entry.get("hashes") or [])
    union = old | hashes
    if not union:
        return False
    changed = len(old ^ hashes) / len(union)
    return changed >= CHANGE_RATIO


def _export(entry: dict) -> dict | None:
    res = entry.get("result")
    if not res:
        return None
    return {
        "version": entry.get("version", PROMPT_VERSION),
        "generatedAt": str(entry.get("generated_at") or "")[:10],
        "model": entry.get("model"),
        "sample": entry.get("sample", 0),
        "sources": entry.get("sources", 0),
        **{s: res.get(s) for s in SECTIONS},
        "oneLiner": one_liner(res),
    }


# ── 실행 ────────────────────────────────────────────────────────
def collect(academies: list[dict], by_key: dict[str, list[dict]],
            candidates: dict, self_notes: dict[str, dict] | None = None,
            live: bool = True, today: date | None = None) -> dict[str, dict]:
    """{학원 id: profile}. 키가 없거나 live=False 면 캐시만 돌려준다."""
    cache = _load()
    today = today or date.today()
    names = {a["id"]: (a.get("display_name") or a.get("name") or a["id"])
             for a in academies}
    todo: list[tuple[str, list[dict]]] = []
    for a in academies:
        aid = a["id"]
        rows = pick(by_key.get(aid) or [])
        if len(rows) < MIN_SAMPLE:
            continue
        exs = excerpts(rows, candidates.get(aid), (self_notes or {}).get(aid))
        hashes = {str(e["url_hash"]) for e in exs}
        if _stale(cache.get(aid), hashes, today):
            todo.append((aid, exs))
    # 표본 큰 곳부터 — 학부모가 먼저 볼 학원이다.
    todo.sort(key=lambda t: -len(t[1]))

    if todo and live and summarize.HAS_KEY and PER_RUN > 0:
        _run(todo[:PER_RUN], names, cache, today)
        _save(cache)
    elif todo:
        why = ("키 없음" if not summarize.HAS_KEY else
               "PER_RUN=0" if PER_RUN <= 0 else "캐시 실행")
        print(f"  프로필: {why} — 건너뜀 (대기 {len(todo):,}곳)")

    out: dict[str, dict] = {}
    for aid, entry in cache.items():
        if aid in names:
            p = _export(entry)
            if p:
                out[aid] = p
    return out


def _run(todo, names: dict[str, str], cache: dict, today: date) -> None:
    import requests
    caller = (summarize._anthropic_caller()
              if summarize.PROVIDER == "anthropic" else summarize._call_gemini)
    if caller is None:
        return
    print(f"  프로필: {len(todo):,}곳 · {summarize.PROVIDER} "
          f"{summarize.MODEL} · 동시 {WORKERS}")
    session = requests.Session()
    stopped = {"why": None}

    def one(item):
        aid, exs = item
        if stopped["why"]:
            return aid, None
        try:
            raw = caller(session, body(names.get(aid, aid), exs), SYSTEM, 2048)
        except summarize._Fatal as exc:
            stopped["why"] = str(exc)
            return aid, None
        except Exception:                                     # noqa: BLE001
            return aid, None
        return aid, (verify(parse(raw), exs), exs)

    made = empty = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for f in as_completed([pool.submit(one, it) for it in todo]):
            aid, got = f.result()
            if got is None:
                continue
            result, exs = got
            cache[aid] = {
                "version": PROMPT_VERSION,
                "generated_at": today.isoformat(),
                "model": summarize.MODEL,
                "hashes": sorted(str(e["url_hash"]) for e in exs),
                "sample": len(exs),
                "sources": len({e["url_hash"] for e in exs if e["kind"] == "parent"}),
                "result": result,          # None 도 캐시한다 — 근거가 바뀌기 전엔 다시 안 묻는다
            }
            if result:
                made += 1
            else:
                empty += 1
    if stopped["why"]:
        print(f"  프로필: 중단 — {stopped['why']}")
    else:
        print(f"  프로필: {made:,}곳 작성 · {empty:,}곳은 근거 부족(인용 검증 통과분만)")


def status() -> str:
    if not summarize.HAS_KEY:
        return "키 없음 — 프로필 건너뜀 (선택 기능)"
    n = sum(1 for e in _load().values() if e.get("result"))
    return f"사용 가능 ✓  {summarize.PROVIDER} · {summarize.MODEL} · 한 실행 {PER_RUN}곳 · 누적 {n:,}곳"


# ── 위키 ────────────────────────────────────────────────────────
def block(aid: str, profiles: dict[str, dict]) -> str:
    p = profiles.get(aid)
    if not p:
        return "- (아직 없음 — 표본 15건부터 만든다)"
    lines = []
    lt, hw, cu, ft, op = (p.get(k) for k in SECTIONS)
    if lt:
        lines.append(f"- 레테 **{lt['band']}** · {lt.get('hard') or ''} — {lt.get('note') or ''}")
    if hw:
        lines.append(f"- 숙제 **{hw['load']}** — {hw.get('note') or ''}")
    if cu:
        lines.append(f"- 커리큘럼 — {cu.get('note') or ''}")
    if ft:
        if ft.get("goodFor"):
            lines.append("- 잘 맞는 아이 — " + " · ".join(ft["goodFor"]))
        if ft.get("caution"):
            lines.append("- 주의 — " + " · ".join(ft["caution"]))
    if op:
        lines.append(f"- 운영 — {op.get('note') or ''}")
    lines.append(f"- (근거 {p.get('sources', 0)}건 · {p.get('generatedAt')} · "
                 f"{p.get('model')} · 점수에 쓰지 않음)")
    return "\n".join(lines)
