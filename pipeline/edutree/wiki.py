"""분류 위키 엔진 — 지식을 코드 상수가 아니라 페이지로 들고 성장시킨다.

구조와 규약은 `pipeline/wiki/SCHEMA.md` 가 정의한다(karpathy LLM wiki 패턴).
이 모듈이 하는 일은 둘이다.

1. **읽기** — 학원 페이지 frontmatter 의 힌트(별칭·일상어·제외어·동네 말)를
   분류 게이트에 공급한다. 지금까지 이런 지식은 신고가 올 때마다 코드
   상수(GENERIC_NAME_PARTS, OTHER_REGION_WORDS…)에 박혔다. 상수는 왜
   넣었는지가 커밋 로그에만 남고, 페이지는 근거와 함께 남는다.
2. **쓰기** — 매 실행이 알게 된 것(표본·순위·판정·규칙·재분류)을 페이지의
   auto 블록에 되적는다. 실행이 거듭될수록 페이지가 두꺼워진다 —
   대화 기록은 사라지지만 위키는 쌓인다.

★ 위키는 관리자 검수를 대체하지 않는다. 최종 제외 권한은 여전히
  판정(verdict)과 규칙(crawl_rules)에 있다. 위키의 exclude 힌트는 같은
  게이트 경로로 흘러 실행 로그에 건수가 찍힌다 — 조용한 제외는 없다.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

from . import config

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
ACADEMY_DIR = WIKI_DIR / "academies"
CONCEPT_DIR = WIKI_DIR / "concepts"

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_AUTO = {
    name: re.compile(rf"<!-- auto:{name} -->.*?<!-- /auto:{name} -->", re.S)
    # review 판정 이력 · stats 표본/순위 · posts 이 학원의 근거 글(역링크)
    # official 공식 홈페이지 관찰
    for name in ("review", "stats", "posts", "official")
}


def _parse(path: Path) -> tuple[dict, str]:
    """(frontmatter, 본문). frontmatter 가 깨져 있으면 빈 dict."""
    text = path.read_text(encoding="utf-8")
    m = _FRONT.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text


def load() -> dict[str, dict]:
    """학원 id → 힌트. 위키가 없으면 빈 dict (신규 클론에서도 동작)."""
    hints: dict[str, dict] = {}
    if not ACADEMY_DIR.is_dir():
        return hints
    for path in sorted(ACADEMY_DIR.glob("*.md")):
        meta, _ = _parse(path)
        aid = str(meta.get("id") or path.stem)
        hints[aid] = {
            "name": meta.get("name"),
            "aliases": [str(a) for a in (meta.get("aliases") or [])],
            "generic": bool(meta.get("generic")),
            "exclude_title": [str(w) for w in (meta.get("exclude_title") or [])],
            "exclude_any": [str(w) for w in (meta.get("exclude_any") or [])],
            "locality": [str(w) for w in (meta.get("locality") or [])],
            # 공식 홈페이지. NEIS 가 주지 않으므로 사람이 적는 값이다.
            # 엔진은 적힌 것만 읽고, 이름으로 추측해 채우지 않는다.
            "homepage": (str(meta.get("homepage")).strip()
                         if meta.get("homepage") else None),
        }
    return hints


def sanity(hints: dict[str, dict], academies: list[dict]) -> list[str]:
    """모순 점검. 발견하면 그 힌트를 죽이고 경고를 돌려준다.

    잘못된 힌트는 조용히 적용되면 안 된다 — 별칭이 남의 학원 이름이면
    남의 글을 통째로 가져오고, 제외어가 자기 이름을 치면 표본이 0 이 된다.
    """
    from . import analyze

    by_id = {a["id"]: a for a in academies}
    all_names: dict[str, str] = {}
    for a in academies:
        for c in analyze.name_candidates(a):
            all_names.setdefault(c, a["id"])

    warnings: list[str] = []
    for aid, h in hints.items():
        a = by_id.get(aid)
        if a is None:
            # 통합으로 id 가 흡수됐거나 폐업. 페이지 이관은 사람 몫이다.
            warnings.append(f"{aid}: 등록부에 없는 id (페이지 이관 필요?)")
            continue
        if h.get("name") and h["name"] != a.get("name"):
            warnings.append(
                f"{aid}: 위키 name '{h['name']}' ≠ 등록명 '{a.get('name')}'")
        kept = []
        for alias in h["aliases"]:
            owner = all_names.get(analyze._norm(alias))
            if owner and owner != aid:
                warnings.append(
                    f"{aid}: 별칭 '{alias}' 은 다른 학원({owner})의 이름 — 무시")
            else:
                kept.append(alias)
        h["aliases"] = kept
        own = analyze._norm(a.get("name") or "")
        for field in ("exclude_title", "exclude_any"):
            kept = []
            for w in h[field]:
                if analyze._norm(w) and analyze._norm(w) in own:
                    warnings.append(
                        f"{aid}: 제외어 '{w}' 가 자기 이름에 포함 — 무시")
                else:
                    kept.append(w)
            h[field] = kept
    return warnings


def apply_gate(mentions: list[dict], hints: dict[str, dict]) -> tuple[list[dict], int]:
    """위키 제외 힌트를 적용한다. 규칙(crawl_rules)과 같은 지위의 게이트다."""
    if not any(h["exclude_title"] or h["exclude_any"] for h in hints.values()):
        return mentions, 0
    out, dropped = [], 0
    for m in mentions:
        h = hints.get(m.get("academy_key") or "")
        if h:
            title = m.get("title", "") or ""
            blob = f"{title} {m.get('snippet', '')}"
            if (any(w in title for w in h["exclude_title"])
                    or any(w in blob for w in h["exclude_any"])):
                dropped += 1
                continue
        out.append(m)
    return out, dropped


# ── 성장 ────────────────────────────────────────────────────────
_STUB = """---
id: "{aid}"
name: {name}
region: {region}
# 공식 홈페이지. 적으면 엔진이 robots.txt 를 확인하고 읽어
# auto:official 을 채운다. 추측해서 적지 말 것 — 이름이 겹치는 학원이 많다.
homepage:
---
# {name}

(자동 생성된 골격. 분류 유의점을 알게 되면 근거와 함께 적을 것 —
 규약은 ../SCHEMA.md)

## 공식 홈페이지
<!-- auto:official -->
<!-- /auto:official -->

## 판정 이력
<!-- auto:review -->
<!-- /auto:review -->

## 통계
<!-- auto:stats -->
<!-- /auto:stats -->

## 이 학원의 근거 글
<!-- auto:posts -->
<!-- /auto:posts -->
"""


# 블록이 없는 옛 페이지에 새로 넣을 때 붙일 제목.
_SECTION = {
    "official": "## 공식 홈페이지",
    "review": "## 판정 이력",
    "stats": "## 통계",
    "posts": "## 이 학원의 근거 글",
}


def _fill(text: str, block: str, body: str) -> str:
    """auto 블록을 갈아끼운다. 블록이 없으면 **끝에 새로 만든다.**

    옛 골격으로 만들어진 페이지가 이미 있다(실측 95장). 마커가 없다고
    조용히 넘어가면 그 페이지들은 영원히 새 정보를 못 받는다 — 스키마가
    자라도 옛 페이지는 제자리에 머무는 셈이다.
    """
    filled = f"<!-- auto:{block} -->\n{body}\n<!-- /auto:{block} -->"
    if _AUTO[block].search(text):
        return _AUTO[block].sub(lambda _: filled, text)
    return text.rstrip("\n") + f"\n\n{_SECTION.get(block, '')}\n{filled}\n"


def update(academies: list[dict], scores: dict, rules: list[dict],
           verdicts: dict[str, str], reassign: dict[str, list[str]],
           run_stats: dict, post_links: dict[str, list[str]] | None = None,
           official_cache: dict | None = None) -> dict:
    """매 실행의 결과를 페이지에 되적는다. 마커 밖(산문)은 건드리지 않는다."""
    ACADEMY_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # 판정·규칙·재분류를 학원별로 모은다
    rules_by: dict[str, list[dict]] = {}
    for r in rules:
        if r.get("scope") == "academy" and r.get("academy_key"):
            rules_by.setdefault(str(r["academy_key"]), []).append(r)
    verd_by: dict[str, dict[str, int]] = {}
    for key, v in verdicts.items():
        _, _, aid = key.partition("|")
        if aid:
            verd_by.setdefault(aid, {}).setdefault(v, 0)
            verd_by[aid][v] += 1
    reassigned_to: dict[str, int] = {}
    for targets in reassign.values():
        for t in targets:
            reassigned_to[t] = reassigned_to.get(t, 0) + 1

    by_id = {a["id"]: a for a in academies}
    # 페이지를 만들 조건: 랭킹 진입, 또는 사람 손길(판정·규칙·재분류)이 닿음
    want = {aid for aid, s in scores.items() if s.get("is_ranked")}
    want |= set(rules_by) | set(verd_by) | set(reassigned_to)
    want &= set(by_id)

    created = updated = 0
    existing = {p.stem for p in ACADEMY_DIR.glob("*.md")}
    for aid in sorted(want | existing):
        a = by_id.get(aid)
        path = ACADEMY_DIR / f"{aid}.md"
        if not path.exists():
            if a is None:
                continue
            path.write_text(_STUB.format(
                aid=aid, name=a.get("name") or aid,
                region=a.get("region_id") or "?"), encoding="utf-8")
            created += 1
        if a is None:
            continue          # 등록부에서 사라진 페이지 — sanity 가 경고한다

        # 날짜를 넣지 않는다 — 넣으면 내용이 같아도 페이지가 매일 갈려
        # 야간 커밋이 85개 파일 잡음이 된다. 실행 날짜는 log.md 의 몫이다.
        s = scores.get(aid) or {}
        stat_lines = []
        if s:
            stat_lines.append(
                f"- 표본 {s.get('sample_size') or 0}건 · 총점 {s.get('total')}"
                + (" · 순위 진입" if s.get("is_ranked") else " · 순위 밖"))
        if not stat_lines:
            stat_lines = ["- (채점 안 됨)"]
        rv_lines = []
        for r in rules_by.get(aid, []):
            rv_lines.append(f"- 규칙 {r.get('kind')} `{r.get('pattern')}` — "
                            f"{r.get('reason') or '(사유 없음)'}"
                            + ("" if r.get("active", True) else " (비활성)"))
        counts = verd_by.get(aid)
        if counts:
            rv_lines.append("- 판정 누적: " + " · ".join(
                f"{k} {v}건" for k, v in sorted(counts.items())))
        if reassigned_to.get(aid):
            rv_lines.append(f"- 재분류 유입 {reassigned_to[aid]}건")
        if not rv_lines:
            rv_lines = ["- (아직 없음)"]

        text = path.read_text(encoding="utf-8")
        new = _fill(_fill(text, "stats", "\n".join(stat_lines)),
                    "review", "\n".join(rv_lines))
        # 근거 글 역링크. 글 페이지의 auto:edges 와 같은 엣지를 반대편에서
        # 적는다 — 어느 쪽에서 읽어도 그래프를 따라갈 수 있어야 한다.
        links = (post_links or {}).get(aid)
        new = _fill(new, "posts",
                    "\n".join(links) if links else "- (아직 없음)")
        if official_cache is not None:
            from . import official as official_mod
            new = _fill(new, "official", official_mod.block(aid, official_cache))
        if new != text:
            path.write_text(new, encoding="utf-8")
            updated += 1

    # index.md — 전부 자동
    lines = ["# 색인", "",
             "(자동 생성 — 손대지 말 것. 규약은 SCHEMA.md)", "",
             "## 개념"]
    for p in sorted(CONCEPT_DIR.glob("*.md")):
        lines.append(f"- [{p.stem}](concepts/{p.name})")
    lines += ["", "## 학원"]
    for p in sorted(ACADEMY_DIR.glob("*.md")):
        meta, _ = _parse(p)
        nm = meta.get("name") or p.stem
        lines.append(f"- [{nm}](academies/{p.name}) — {meta.get('region', '?')}")
    (WIKI_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # log.md — 한 실행 한 줄
    log = WIKI_DIR / "log.md"
    head = "# 실행 일지\n\n(자동 append — 손대지 말 것)\n"
    body = log.read_text(encoding="utf-8") if log.exists() else head
    body += (f"- {today} · 언급 {run_stats.get('mentions', 0):,}건 · "
             f"위키 게이트 {run_stats.get('wiki_dropped', 0)}건 제외 · "
             f"페이지 {len(list(ACADEMY_DIR.glob('*.md')))}장"
             f"(신규 {created} · 갱신 {updated})\n")
    log.write_text(body, encoding="utf-8")

    return {"created": created, "updated": updated}
