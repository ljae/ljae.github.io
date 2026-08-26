"""글 노드 — 후기 한 건이 파일 한 장이고, 그 파일이 근거의 스위치다.

지금까지 후기는 41MB 짜리 JSON 블롭 안에만 있었다. 점수에는 쓰이는데
**가리킬 수가 없었다.** '저 글은 가짜다', '저 글은 3년 전 이야기다' 라는
말을 받아도 붙일 자리가 없었고, 무효화는 Supabase 판정으로만 가능했다.

이 모듈은 글을 위키의 1급 노드로 올린다.

    노드  글(posts/<url_hash>.md) · 학원(academies/<id>.md)
    엣지  글 → 학원. frontmatter 의 academies 와 auto:edges 가 같은 것을
          두 방향에서 적는다(글 쪽은 목록, 학원 쪽은 역링크).

**무효화가 이 구조의 존재 이유다.** 글 페이지 frontmatter 의 verdict 를
rejected 로 바꾸고 다시 돌리면 그 글의 영향이 전부 사라진다 — 그 학원의
평판·화제성뿐 아니라 **코호트 평균과 등수까지** 다시 계산되기 때문이다.
파이프라인이 매 실행 전부를 원자료에서 다시 만드는 구조라 가능한 일이고,
그래서 '지운다' 가 아니라 '다시 짓는다' 로 푼다. 부분 삭제는 어디까지
전파해야 하는지를 사람이 판단해야 하지만, 재빌드는 판단할 것이 없다.

## 사람 영역과 기계 영역

frontmatter 의 verdict·reject_reason·reassign_to·stale_after 는 **사람이
쓴다.** 엔진은 읽기만 하고 절대 덮어쓰지 않는다(골격을 처음 만들 때 빈
값으로 두는 것이 전부다). `<!-- auto:* -->` 블록은 반대로 엔진이 통째로
갈아끼운다. 학원 페이지의 규약과 같다 — SCHEMA.md 참고.

★ 위키의 판정은 관리자 검수(`mention_reviews`)를 **대체하지 않는다.**
  둘 다 같은 게이트 경로를 지나고 실행 로그에 건수가 찍힌다. 다만 성격이
  다르다: Supabase 판정은 운영자가 화면에서 끄고 켜는 것이고, 위키 판정은
  커밋이라 근거와 함께 영구히 남는다. Supabase 에 이미 있는 판정은 글
  페이지의 auto 블록에 **기록**되고, frontmatter 에 중복으로 적지 않는다.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
POST_DIR = WIKI_DIR / "posts"

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_AUTO = {
    name: re.compile(rf"<!-- auto:{name} -->.*?<!-- /auto:{name} -->", re.S)
    for name in ("digest", "summary", "edges", "review")
}

# 반려 사유. 자유 서술을 받으면 나중에 집계도 검색도 안 된다.
REJECT_REASONS = ("동명이인", "무관", "광고", "오래됨", "중복", "기타")


def _parse(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = _FRONT.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text


def _as_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def load() -> dict[str, dict]:
    """url_hash → 사람이 적은 판단. 페이지가 없으면 빈 dict.

    **auto 블록은 읽지 않는다.** 엔진이 쓴 것을 엔진이 되읽으면 한 번의
    실수가 영원히 자기를 증명한다.
    """
    out: dict[str, dict] = {}
    if not POST_DIR.is_dir():
        return out
    for path in POST_DIR.glob("*.md"):
        meta, _ = _parse(path)
        h = str(meta.get("url_hash") or path.stem)
        verdict = (meta.get("verdict") or "").strip().lower() or None
        reassign = [str(a) for a in (meta.get("reassign_to") or [])]
        stale = _as_date(meta.get("stale_after"))
        if not (verdict or reassign or stale):
            continue          # 골격만 있는 페이지 — 게이트에 실릴 것이 없다
        out[h] = {
            "verdict": verdict,
            "reason": (meta.get("reject_reason") or "").strip() or None,
            "reassign_to": reassign,
            "stale_after": stale,
            "path": path,
        }
    return out


def sanity(overrides: dict[str, dict], academies: list[dict]) -> list[str]:
    """모순 점검. 잘못된 판단은 죽이고 경고한다.

    조용히 적용되는 잘못된 무효화가 최악이다 — 멀쩡한 근거가 사라졌는데
    아무도 왜인지 모르게 된다.
    """
    known = {a["id"] for a in academies}
    warnings: list[str] = []
    for h, o in list(overrides.items()):
        v = o["verdict"]
        if v and v not in ("confirmed", "rejected", "reclassified"):
            warnings.append(f"{h[:8]}: 알 수 없는 verdict '{v}' — 무시")
            o["verdict"] = None
        if o["verdict"] == "rejected" and not o["reason"]:
            # 사유 없는 제외는 나중에 지우지도 못하고 남는다.
            warnings.append(f"{h[:8]}: reject_reason 이 없다 — 무시")
            o["verdict"] = None
        if o["reason"] and o["reason"] not in REJECT_REASONS:
            warnings.append(
                f"{h[:8]}: reject_reason '{o['reason']}' 은 목록에 없다 "
                f"({'·'.join(REJECT_REASONS)})")
        bad = [t for t in o["reassign_to"] if t not in known]
        if bad:
            warnings.append(f"{h[:8]}: reassign_to 에 없는 학원 {bad} — 무시")
            o["reassign_to"] = [t for t in o["reassign_to"] if t in known]
        if not (o["verdict"] or o["reassign_to"] or o["stale_after"]):
            overrides.pop(h)
    return warnings


def apply_gate(mentions: list[dict], overrides: dict[str, dict],
               academies: list[dict] | None = None) -> tuple[list[dict], dict]:
    """글 페이지의 판단을 언급에 적용한다.

    셋을 한다.
      rejected      그 글을 근거에서 뺀다 — 모든 학원에서.
      stale_after   지난 글은 뺀다. '가짜'와 '낡음'은 다른 상태다.
      reassign_to   지목된 학원의 근거로 **복제**한다. 원본은 판정을 따른다.

    ★ 재분류는 반려와 별개다. 네 학원 비교글이 한 곳에만 붙는 일이 있는데,
      반려만 가능하면 멀쩡한 글이 통째로 버려지고 '어느 학원 글인지'라는
      사람이 아는 정보도 함께 사라진다.
    """
    if not overrides:
        return mentions, {"rejected": 0, "stale": 0, "reassigned": 0}

    today = date.today()
    by_id = {a["id"]: a for a in (academies or [])}
    stat = {"rejected": 0, "stale": 0, "reassigned": 0}

    kept: list[dict] = []
    seen_pairs = {(m.get("url_hash"), m.get("academy_key")) for m in mentions}
    template: dict[str, dict] = {}

    for m in mentions:
        o = overrides.get(m.get("url_hash") or "")
        if o is None:
            kept.append(m)
            continue
        template.setdefault(m["url_hash"], m)
        if o["verdict"] == "rejected":
            stat["rejected"] += 1
            continue
        if o["stale_after"] and today > o["stale_after"]:
            stat["stale"] += 1
            continue
        if o["verdict"] == "reclassified":
            # 이 학원의 근거는 아니라는 판정. 재분류 대상은 아래에서 붙는다.
            stat["rejected"] += 1
            continue
        kept.append(m)

    # 재분류 — 지목된 학원으로 복제한다. 그 학원으로 수집된 적이 없어도
    # 붙는다. 그게 재분류의 목적이다.
    for h, o in overrides.items():
        src = template.get(h)
        if src is None or not o["reassign_to"]:
            continue
        if o["stale_after"] and today > o["stale_after"]:
            continue
        for target in o["reassign_to"]:
            if (h, target) in seen_pairs:
                continue
            a = by_id.get(target)
            if a is None:
                continue
            copy = dict(src)
            copy.update({
                "academy_key": target,
                "academy_name": a.get("name"),
                "region_id": a.get("region_id"),
                "branch_basis": "reclassified",
            })
            kept.append(copy)
            seen_pairs.add((h, target))
            stat["reassigned"] += 1
    return kept, stat


# ── 쓰기 ────────────────────────────────────────────────────────
_STUB = """---
url_hash: "{h}"
url: {url}
source: {source}
title: {title}
posted_at: {posted_at}
author_hash: {author_hash}
# ↓ 엔진이 읽는 판단 필드. 사람이 쓴다 — 엔진은 절대 덮어쓰지 않는다.
#   verdict: confirmed | rejected | reclassified
#   reject_reason: {reasons}
verdict:
reject_reason:
reassign_to: []
stale_after:
---
# {title}

원문: {url}

## 요약
<!-- auto:digest -->
<!-- /auto:digest -->

<!-- auto:summary -->
<!-- /auto:summary -->

## 이 글이 붙은 학원
<!-- auto:edges -->
<!-- /auto:edges -->

## 검수
<!-- auto:review -->
<!-- /auto:review -->

<!-- 여기부터 산문. 이 글을 어떻게 읽어야 하는지 근거와 함께 적을 것. -->
"""


# 학원실록 자체 후기는 별점 집계를 언급 형태로 바꾼 **합성 행**이다.
# 원문이 없고(본문을 보관하지 않기로 했다) url 도 internal:// 이라
# 글 노드를 만들 대상이 아니다. demo 모드의 합성 언급도 마찬가지다.
_SYNTHETIC = ("edutree_review",)


def _is_real_post(m: dict) -> bool:
    return bool(m.get("url_hash")) and not m.get("is_demo") \
        and m.get("source") not in _SYNTHETIC


def _yaml_str(value) -> str:
    """frontmatter 에 안전하게 넣을 스칼라. 콜론·따옴표가 흔하다."""
    if value in (None, ""):
        return ""
    text = str(value).replace("\n", " ").strip()
    return yaml.safe_dump(text, allow_unicode=True, default_flow_style=True
                          ).strip().rstrip("\n...").strip()


def _fill(text: str, block: str, body: str) -> str:
    if block not in _AUTO:
        return text
    # 치환문을 문자열로 주면 본문의 역참조(\\1, \\g<..>)가 해석된다.
    # 글 제목에 그런 문자가 들어오는 일이 실제로 있다.
    filled = f"<!-- auto:{block} -->\n{body}\n<!-- /auto:{block} -->"
    return _AUTO[block].sub(lambda _: filled, text)


_SENTIMENT_LABEL = ((0.25, "긍정"), (0.05, "약긍정"),
                    (-0.05, "중립"), (-0.25, "약부정"))


def _signed(value: float | None) -> str:
    """부호 붙은 두 자리. **음의 0 을 없앤다.**

    `f"{-0.0:+.2f}"` 는 '-0.00' 이다. 중립인데 부정으로 읽히고, 파이썬
    버전에 따라 같은 계산이 0.0 이 되기도 -0.0 이 되기도 해서 내용이
    안 바뀌었는데도 페이지가 갈린다(3.9 → 3.12 에서 실제로 한 장이 그랬다).
    """
    # **표시 자릿수로 반올림한 뒤** 0 인지 본다. -0.001 은 0 이 아니지만
    # 두 자리로는 '-0.00' 으로 찍혀 부정으로 읽힌다. 화면에 0.00 이라
    # 적을 값에 마이너스를 붙이지 않는다.
    x = round(float(value or 0.0), 2)
    return f"{0.0 if x == 0 else x:+.2f}"


def _label(sentiment: float) -> str:
    for cut, name in _SENTIMENT_LABEL:
        if sentiment >= cut:
            return name
    return "부정"


def _digest(rows: list[dict]) -> str:
    """결정적 요약. LLM 없이, 파이프라인이 이미 계산한 것으로 만든다.

    감성·신뢰도·과목·스팸은 이미 매 실행 계산된다. 그것을 사람이 읽을 수
    있는 자리에 옮겨 적는 것뿐이라 **새로 추정하는 값이 하나도 없다.**
    """
    top = max(rows, key=lambda m: m.get("credibility") or 0)
    subjects = sorted({s for m in rows for s in (m.get("subjects") or [])})
    tiers = sorted({t for m in rows
                    for t in (m.get("class_tier_signals") or {})})
    sel = sorted({k for m in rows
                  for k, v in (m.get("selectivity") or {}).items() if v})
    sent = top.get("sentiment")
    lines = [
        f"- 감성 {_signed(sent)} ({_label(sent)}) · 신뢰도 "
        f"{top.get('credibility', 0):.2f}"
        + (f" · 스팸 {top['spam_score']:.2f}" if top.get("spam_score") else "")
        + (" · **스팸 배제**" if top.get("is_excluded") else ""),
        f"- 붙은 학원 {len({m.get('academy_key') for m in rows})}곳"
        + (f" · 과목 {'·'.join(subjects)}" if subjects else " · 과목 불명"),
    ]
    if sel:
        lines.append(f"- 진입난이도 신호: {'·'.join(sel)}")
    if tiers:
        lines.append(f"- 등급반 언급: {'·'.join(tiers)}")
    if top.get("posted_at") is None:
        lines.append("- 작성일 불명 — 최신성 가중 0.6(6개월 된 글과 같은 취급)")
    return "\n".join(lines)


def _edges(rows: list[dict], names: dict[str, str]) -> str:
    """이 글이 어느 학원에 왜 붙었는지. 그래프 엣지를 사람이 읽는 형태로."""
    basis_ko = {
        "direct": "이름이 본문에 등장",
        "region": "글이 이 권역을 밝힘",
        "brand": "지점 불명 · 브랜드 공통",
        "reclassified": "재분류로 지목",
    }
    out = []
    for m in sorted(rows, key=lambda x: -(x.get("credibility") or 0)):
        aid = m.get("academy_key")
        basis = m.get("branch_basis") or "direct"
        nm = names.get(aid) or m.get("academy_name") or aid
        out.append(f"- [[../academies/{aid}|{nm}]] — {basis_ko.get(basis, basis)}"
                   + (f" · 감성 {_signed(m['sentiment'])}"
                      if m.get("sentiment") is not None else ""))
    return "\n".join(out) or "- (없음)"


def update(mentions: list[dict], academies: list[dict],
           verdicts: dict[str, str] | None = None,
           summaries: dict[str, str] | None = None) -> dict:
    """게이트를 통과한 글마다 페이지를 만들고 auto 블록을 갈아끼운다.

    **날짜를 페이지에 넣지 않는다.** 넣으면 내용이 같아도 매일 전부 갈려
    야간 커밋이 수천 파일 잡음이 된다. 실행 날짜는 log.md 의 몫이다.
    """
    POST_DIR.mkdir(parents=True, exist_ok=True)
    names = {a["id"]: a.get("name") or a["id"] for a in academies}

    by_post: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        if not _is_real_post(m):
            continue
        by_post[m["url_hash"]].append(m)

    # Supabase 판정을 글별로 모은다. 기록만 하고 frontmatter 는 안 건드린다.
    verd_by: dict[str, list[str]] = defaultdict(list)
    for key, v in (verdicts or {}).items():
        url, _, aid = key.partition("|")
        verd_by[url].append(f"{names.get(aid, aid)}: {v}")

    created = updated = 0
    for h, rows in by_post.items():
        top = max(rows, key=lambda m: m.get("credibility") or 0)
        path = POST_DIR / f"{h}.md"
        if not path.exists():
            path.write_text(_STUB.format(
                h=h,
                url=top.get("source_url") or "",
                source=top.get("source") or "",
                title=_yaml_str(top.get("title")) or "(제목 없음)",
                posted_at=top.get("posted_at") or "",
                author_hash=top.get("author_hash") or "",
                reasons=" | ".join(REJECT_REASONS),
            ), encoding="utf-8")
            created += 1

        text = path.read_text(encoding="utf-8")
        new = _fill(text, "digest", _digest(rows))
        new = _fill(new, "edges", _edges(rows, names))
        rv = verd_by.get(h)
        new = _fill(new, "review",
                    "\n".join(f"- 운영자 판정 — {r}" for r in rv) if rv
                    else "- (운영자 판정 없음)")
        if summaries and summaries.get(h):
            new = _fill(new, "summary", summaries[h])
        if new != text:
            path.write_text(new, encoding="utf-8")
            updated += 1

    return {"created": created, "updated": updated, "posts": len(by_post)}


def audit(mentions: list[dict], overrides: dict[str, dict]) -> list[str]:
    """디스크의 글 페이지와 이번 실행의 근거가 어긋나는지 본다.

    **고아 페이지 자체는 오류가 아니다.** 우리가 반려했거나 기한을 넘긴 글은
    당연히 이번 근거에 없다 — 그게 무효화가 동작했다는 증거다. 문제는
    **우리가 뺀 적 없는데 사라진 글**이다. 규칙이 바뀌었거나 그 학원이 수집
    대상에서 빠졌다는 뜻이고, 페이지에 적힌 산문이 이제 아무것도 가리키지
    않는다.

    ★ 페이지를 지우지 않는다. 사람이 적은 산문이 거기 있고, 다음 회차에
      그 글이 다시 들어올 수도 있다. 알리기만 한다.
    """
    if not POST_DIR.is_dir():
        return []
    live = {m["url_hash"] for m in mentions if _is_real_post(m)}
    on_disk = {p.stem for p in POST_DIR.glob("*.md")}

    # 우리가 의도적으로 뺀 것 — 정상이다.
    intended = {h for h, o in overrides.items()
                if o["verdict"] in ("rejected", "reclassified") or o["stale_after"]}
    drifted = sorted(on_disk - live - intended)

    # 판단은 적혀 있는데 그 글이 아예 수집된 적이 없는 경우.
    # 오타이거나, 그 학원이 수집 대상에서 빠진 것이다.
    dangling = sorted(h for h in overrides
                      if h not in live and h not in on_disk)

    out: list[str] = []
    if drifted:
        out.append(
            f"글 페이지 {len(drifted)}장이 이번 근거에 없다(우리가 뺀 것이 "
            f"아님) — 규칙 변경이나 수집 대상 변동: {', '.join(h[:8] for h in drifted[:3])}"
            + (" …" if len(drifted) > 3 else ""))
    if dangling:
        out.append(f"판단이 적힌 글 {len(dangling)}건이 수집분에 없다: "
                   + ", ".join(h[:8] for h in dangling[:3]))
    return out


def backlinks(mentions: list[dict], limit: int = 8) -> dict[str, list[str]]:
    """학원 id → 그 학원 페이지에 걸 글 링크. 신뢰도 높은 것부터."""
    by_academy: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        aid = m.get("academy_key")
        if aid and _is_real_post(m):
            by_academy[aid].append(m)

    out: dict[str, list[str]] = {}
    for aid, rows in by_academy.items():
        rows.sort(key=lambda m: -(m.get("credibility") or 0))
        total = len({m["url_hash"] for m in rows})
        seen: set[str] = set()
        lines: list[str] = []
        for m in rows:
            h = m["url_hash"]
            if h in seen:
                continue
            seen.add(h)
            title = (m.get("title") or "(제목 없음)").replace("|", "·")[:44]
            lines.append(
                f"- [[../posts/{h}|{title}]] — 감성 "
                f"{_signed(m.get('sentiment'))} · 신뢰도 "
                f"{m.get('credibility', 0):.2f}")
            if len(lines) >= limit:
                break
        if total > len(lines):
            lines.append(f"- … 외 {total - len(lines)}건")
        out[aid] = lines
    return out
