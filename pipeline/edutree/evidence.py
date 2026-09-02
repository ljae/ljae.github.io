"""근거 발췌 — 화면에 나가는 인용은 그 학원의 이름을 품어야 한다.

앱의 '평판 점수에 반영된 근거' 는 오래 스니펫의 **앞 120자**를 잘라 실었다.
관련성 게이트는 제목+본문(블로그는 2,000자) 어디든 이름이 있으면 통과시키는데,
화면은 앞 120자만 보여주니 학부모 눈에는 **학원 이름이 한 번도 안 나오는
글**이 근거로 걸려 있었다(실측 2026-09-02: 532건 중 22건, 그중 절반은 진짜
오귀속이고 절반은 발췌 위치 문제였다). 둘은 원인이 다르다 — 게이트는
analyze.is_relevant 가, 발췌는 이 모듈이 맡는다.

원칙 셋.
  1. 발췌는 이름이 처음 나온 자리를 중심으로 자른다. 이름이 제목에만 있으면
     본문 앞머리를 쓴다 — 제목이 이미 그 학원을 말하고 있다.
  2. 근거 순서는 신뢰도만이 아니라 **이 글이 이 학원을 얼마나 분명히
     말하는가**로 정한다. 제목에 이름이 있는 글, 이름이 여러 번 나오는 글이
     앞이다. 신뢰도가 높아도 스치듯 한 번 나온 글은 뒤로 간다.
  3. 줄마다 번호([1]·[2]…)를 붙여 내보낸다. 같은 학원 페이지의 다른 인용
     (사실 카드·진입난이도)이 같은 원문이면 같은 번호를 쓴다 — 앱이 URL 로
     잇는다.

원문 본문은 여전히 저장·전재하지 않는다. 발췌 150자는 검색 스니펫과 같은
길이이고 링크로 원문을 안내한다.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import analyze

EXCERPT_WIDTH = 150
# 이름 앞으로 이만큼은 보여 준다. 문장 경계가 있으면 거기서 자른다.
LEAD = 50
DEFAULT_LIMIT = 6

_WS = re.compile(r"[\s​﻿]+")
_SENT = re.compile(r"[.!?…\n]")

ASPECT_LABELS = {
    "강사": "선생님",
    "관리": "관리·피드백",
    "커리큘럼": "커리큘럼·진도",
    "가격": "비용",
    "반편성": "레벨테스트·반편성",
    "숙제량": "숙제량",
    "시설": "시설·통학",
}


def _clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


def _norm_map(text: str) -> tuple[str, list[int]]:
    """정규화 문자열과 원문 위치 대응표. claims._norm_map 과 같은 규칙이다 —
    analyze._norm 이 지우는 글자를 똑같이 지워야 자리가 맞는다."""
    chars: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        if ch.isalnum():
            chars.append(ch.lower())
            idx.append(i)
    return "".join(chars), idx


def excerpt(mention: dict, candidates, width: int = EXCERPT_WIDTH) -> dict:
    """{'text', 'in_title', 'count'}. text 는 원문 글자 그대로의 발췌다."""
    title = _clean(mention.get("title"))
    body = _clean(mention.get("snippet"))
    flat_t, _ = _norm_map(title)
    flat_b, idx_b = _norm_map(body)
    spans = analyze.name_spans(flat_t + flat_b, candidates)
    in_title = any(s < len(flat_t) for s, _ in spans)
    body_spans = [(s - len(flat_t), e - len(flat_t)) for s, e in spans
                  if s >= len(flat_t)]

    if not body:
        return {"text": "", "in_title": in_title, "count": len(spans)}

    if not body_spans:
        # 이름이 제목에만 있다. 본문 앞머리를 문장 단위로.
        text = body[:width]
        cut = _SENT.search(body, min(len(body), width // 2),
                           min(len(body), width + 40))
        if cut:
            text = body[:cut.end()].rstrip()
        return {"text": text + ("…" if len(body) > len(text) else ""),
                "in_title": in_title, "count": len(spans)}

    s_norm, e_norm = body_spans[0]
    start = idx_b[s_norm] if s_norm < len(idx_b) else 0
    end = idx_b[min(e_norm, len(idx_b)) - 1] + 1 if idx_b else len(body)

    # 앞: 가까운 문장 경계, 없으면 LEAD 만큼.
    lo = max(0, start - LEAD)
    last = None
    for last in _SENT.finditer(body, lo, start):
        pass
    if last is not None:
        lo = last.end()
    # 뒤: width 를 채우되 문장 경계에서 끝낸다. 이름이 잘리는 일은 없다 —
    # 이름 끝(end)보다 앞에서는 절대 자르지 않는다.
    limit = max(lo + width, end + 20)
    if limit >= len(body):
        hi = len(body)
    else:
        tail = _SENT.search(body, max(end, limit - 40),
                            min(len(body), limit + 40))
        hi = tail.end() if tail else limit
    text = body[lo:hi].strip()
    return {
        "text": ("…" if lo > 0 else "") + text + ("…" if hi < len(body) else ""),
        "in_title": in_title,
        "count": len(spans),
    }


def _strength(info: dict, m: dict) -> float:
    """이 글이 이 학원을 얼마나 분명히 말하는가 + 근거로서의 무게."""
    s = 0.0
    if info["in_title"]:
        s += 2.0
    if info["count"] >= 2:
        s += 1.0
    if info["count"] >= 4:
        s += 0.5
    # 스친 언급(긴 글에 한 번)은 뒤로.
    if info["count"] == 1 and info["body_len"] > analyze.LONG_TEXT:
        s -= 1.0
    s += float(m.get("credibility") or 0)
    s += 0.3 * int(m.get("substance") or 0)
    if m.get("posted_at"):
        s += 0.2
    # 지점 불명 브랜드 공통 글은 지점을 밝힌 글보다 뒤로.
    if m.get("branch_basis") == "brand":
        s -= 0.4
    return s


def select(rows: list[dict], candidates, limit: int = DEFAULT_LIMIT) -> list:
    """화면에 실을 근거를 고른다. 배제된 글은 안 싣고, 같은 원문은 한 번만.

    돌려주는 것은 (match_info, 언급) 쌍의 목록이다.
    """
    pool = []
    for m in rows:
        if m.get("is_excluded"):
            continue
        info = analyze.match_info(m, candidates)
        if not info["count"]:
            continue
        pool.append((_strength(info, m), info, m))
    pool.sort(key=lambda t: (-t[0], str(t[2].get("posted_at") or "")))
    out, seen = [], set()
    for _s, info, m in pool:
        h = m.get("url_hash") or m.get("source_url")
        if h in seen:
            continue
        seen.add(h)
        out.append((info, m))
        if len(out) >= limit:
            break
    return out


def export_rows(chosen: list, candidates) -> list[dict]:
    """번호 붙은 근거 행. 앱 models.Evidence 와 1:1."""
    out = []
    for i, (info, m) in enumerate(chosen, start=1):
        ex = excerpt(m, candidates)
        out.append({
            "ref": i,
            "source": m.get("source"),
            "url": m.get("source_url"),
            # 신고·판정의 키. 앱이 '잘못 붙은 글' 신고에 실어 보낸다.
            "url_hash": m.get("url_hash"),
            "title": _clean(m.get("title")),
            # 필드 이름은 옛 앱과의 호환을 위해 그대로 둔다. 내용이 바뀌었다 —
            # 앞 120자가 아니라 이름을 품은 발췌다.
            "snippet": ex["text"][:EXCERPT_WIDTH + 60],
            "posted_at": m.get("posted_at"),
            "sentiment": m.get("sentiment"),
            "credibility": m.get("credibility"),
            "branch_basis": m.get("branch_basis"),
            "in_title": info["in_title"],
            "mentions": info["count"],
            "substance": m.get("substance"),
            "subject": m.get("subject"),
            "band": m.get("band"),
        })
    return out


def aspect_profile(rows: list[dict], min_n: int = 2) -> dict:
    """학부모가 말한 관점별 감성. {관점: {n, mean, positive, negative, label}}.

    점수에 쓰지 않는다. '선생님은 좋은데 숙제가 많다' 를 한 숫자로 뭉개지
    않고 나눠 보여 주는 것이 목적이다. 한 건짜리 관점은 내지 않는다 —
    한 사람의 아이 이야기가 학원의 성격으로 읽힌다.
    """
    acc: dict[str, dict] = defaultdict(lambda: {"w": 0.0, "sum": 0.0,
                                               "n": 0, "pos": 0, "neg": 0})
    for m in rows:
        if m.get("is_excluded"):
            continue
        for aspect, value in (m.get("aspects") or {}).items():
            w = float(m.get("credibility") or 0.5)
            a = acc[aspect]
            a["w"] += w
            a["sum"] += w * float(value)
            a["n"] += 1
            if value > 0.05:
                a["pos"] += 1
            elif value < -0.05:
                a["neg"] += 1
    out = {}
    for aspect, a in acc.items():
        if a["n"] < min_n or not a["w"]:
            continue
        out[aspect] = {
            "label": ASPECT_LABELS.get(aspect, aspect),
            "n": a["n"],
            "mean": round(a["sum"] / a["w"], 3),
            "positive": a["pos"],
            "negative": a["neg"],
        }
    return out


def audit(payload: list[dict]) -> dict:
    """내보낸 근거의 품질을 잰다. 매 실행 로그와 meta.json 에 남긴다.

    오귀속은 한 번 고치고 끝나는 것이 아니다. 새 낱말·새 학원·새 글이
    매일 들어오므로 **회차마다 다시 재야** 나빠지는 순간을 잡는다.
    """
    rows = 0
    named = 0
    titled = 0
    with_ev = 0
    basis: dict[str, int] = defaultdict(int)
    for a in payload:
        ev = a.get("evidence") or []
        if ev:
            with_ev += 1
        cands = analyze.name_candidates({
            "name": a.get("name"), "brand": a.get("brand"),
            "aliases": a.get("aliases") or []})
        for e in ev:
            rows += 1
            blob = analyze._norm(f"{e.get('title', '')} {e.get('snippet', '')}")
            if analyze.name_spans(blob, cands):
                named += 1
            if e.get("in_title"):
                titled += 1
            basis[e.get("branch_basis") or "direct"] += 1
    return {
        "academies": len(payload),
        "withEvidence": with_ev,
        "rows": rows,
        "nameInExcerpt": named,
        "inTitle": titled,
        "basis": dict(basis),
    }
