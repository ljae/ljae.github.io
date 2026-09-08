"""사례 대장(case ledger) — 웹의 신고 한 건이 분류 시스템의 개선 한 건이 된다.

지금까지 신고는 세 창구(corrections · evidence_reports · claim_disputes)에
쌓였고, 처리는 판정·규칙·위키 힌트로 **그 글 하나**를 바로잡는 데서
끝났다. 같은 종류의 신고가 다시 오면 다시 처음부터였다 — CLAUDE.md 의
'같은 신고가 또 들어오면' 이 그 기록이다.

이 모듈은 신고를 **사례**로 만든다. 사례는 파일 한 장이고
(`pipeline/wiki/cases/<id>.md`), 위키의 학원·글 노드와 같은 규약을 따른다:
frontmatter 는 상태 기계, 산문은 사람/에이전트의 진단과 조치, auto 블록은
엔진이 갈아끼운다.

    접수(앱) ─→ intake() ─→ cases/<id>.md  (status: open)
      → /triage-reports  · case-triage 에이전트가 category 를 정한다   (triaged)
      → gate-* 전문 에이전트가 고친다: 판정·위키·규칙·코드            (fixed)
        ★ 고친 것은 반드시 회귀 픽스처가 된다 → tests/cases/<id>.yaml
      → pipeline-verifier 가 테스트·--from-cache·데이터 커밋으로 확인    (verified)
      → 다음 야간 산출물에서 화면이 바뀐 것을 본 뒤                     (closed)

★ 이 파일이 하는 일은 셋뿐이다: 접수를 파일로 옮기고, 상태를 읽고, 요약을
  찍는다. **판단하지 않는다.** 판단은 에이전트와 사람이 산문에 적는다.
★ 엔진은 산문을 되읽지 않는다(wiki 와 같은 규칙). 되읽는 것은 frontmatter
  의 상태 필드뿐이고, 그것도 요약·감사에만 쓴다 — 점수에는 절대 안 쓴다.
★ 사례 id 는 접수 id 에서 딴다. 같은 접수가 두 번 파일이 되지 않는다.
★ 학원(academy) 만이 아니다. `entity_type` 이 있다 — 교재(textbook) 랭킹이
  붙으면 같은 대장을 쓴다. 후기를 이름으로 잇는 문제는 교재도 똑같다
  ('최상위수학' 이 학원 이름이자 문제집 이름이었다).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import requests

from . import config

CASE_DIR = config.PIPELINE_DIR / "wiki" / "cases"
FIXTURE_DIR = config.PIPELINE_DIR / "tests" / "cases"

# 접수 창구 → 사례 id 접두. 접수 id(uuid) 앞 8자를 붙인다.
SOURCES = {
    "correction": "co",        # 관계자 정정 요청 (corrections)
    "evidence_report": "er",   # '이 학원 글이 아니에요' (evidence_reports)
    "claim_dispute": "cd",     # 주장 이의 (claim_disputes)
    "manual": "ma",            # 대화·메일로 받은 신고를 사람이 적은 것
}

# 진단 종류. case-triage 에이전트가 정한다. 각 종류의 담당 에이전트와
# 판정 절차는 .claude/agents/*.md 에 있다.
CATEGORIES = {
    "relevance": "이름·관련성 게이트 — 남의 글이 붙었다 (analyze.py)",
    "branch":    "지점·지역 — 다른 지점·다른 동네 글이 붙었다 (branches.py)",
    "subject":   "과목·학년 구간 — 엉뚱한 랭킹에 있다 (build._infer_subjects…)",
    "merge":     "통합·신원 — 중복으로 보이거나 남남이 합쳐졌다 (dedupe.py)",
    "claim":     "주장·진입난이도 — 사실 카드·난이도 근거가 틀렸다 (claims.py)",
    "score":     "산식·기둥 — 점수·등수 자체가 이상하다 (scoring.py)",
    "coverage":  "수집 대상 — 애초에 본 적이 없다 (select_for_mentions)",
    "data_lag":  "코드는 고쳐졌고 데이터가 아직 안 만들어졌다",
    "display":   "표시 계층 — 파이프라인은 맞고 화면이 틀렸다 (app/)",
    "other":     "기타",
}
STATUSES = ("open", "triaged", "fixed", "verified", "closed", "declined")
RESOLUTIONS = ("post", "wiki", "rule", "code", "fixture", "data", "none")

# 접수 화면의 사유 코드 → 한국어. 세 표의 어휘가 조금씩 다르다.
REASON_KO = {
    "other_academy": "다른 학원 이야기", "not_review": "학원 후기 아님",
    "ad": "광고·홍보", "outdated": "오래된 이야기", "not_true": "사실 아님",
    "fix": "정보 정정", "claim": "관계자 확인", "remove": "삭제 요청",
    "other": "기타",
}

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_REPORT = re.compile(r"<!-- auto:report -->.*?<!-- /auto:report -->", re.S)


# ── Supabase ───────────────────────────────────────────────────
def _headers() -> dict:
    return {"apikey": config.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"}


def _get(path: str, params: dict) -> list[dict]:
    """부산물이다. 네트워크가 한 번 끊겼다고 실행 전체를 잃지 않는다."""
    if not config.HAS_SUPABASE:
        return []
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/{path}",
                         params=params, headers=_headers(), timeout=20)
        return r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []


def _fetch_open() -> list[dict]:
    """세 창구의 미처리 접수를 하나의 모양으로 모은다."""
    out: list[dict] = []
    for r in _get("corrections", {
            "select": "*", "status": "in.(received,open,reviewing)",
            "order": "created_at.desc"}):
        out.append({
            "source": "correction", "source_id": str(r.get("id") or ""),
            "source_status": r.get("status"),
            "entity_key": str(r.get("academy_key") or ""),
            "entity_name": r.get("academy_name") or "",
            "reported_at": (r.get("created_at") or "")[:10],
            "reason": r.get("claim_type") or "other",
            "note": r.get("body") or "",
            "requester": r.get("requester") or "",
        })
    for r in _get("evidence_reports", {
            "select": "*", "status": "in.(open,queued)",
            "order": "created_at.desc"}):
        out.append({
            "source": "evidence_report", "source_id": str(r.get("id") or ""),
            "source_status": r.get("status"),
            "entity_key": str(r.get("academy_key") or ""),
            "entity_name": "",
            "reported_at": (r.get("created_at") or "")[:10],
            "reason": r.get("reason") or "other",
            "note": r.get("note") or "",
            "url_hash": r.get("url_hash") or "",
            "title": r.get("title") or "",
            "source_url": r.get("source_url") or "",
        })
    for r in _get("claim_disputes", {
            "select": "*", "status": "eq.open", "order": "created_at.desc"}):
        out.append({
            "source": "claim_dispute", "source_id": str(r.get("id") or ""),
            "source_status": r.get("status"),
            "entity_key": str(r.get("academy_key") or ""),
            "entity_name": "",
            "reported_at": (r.get("created_at") or "")[:10],
            "reason": r.get("reason") or "other",
            "note": r.get("note") or "",
            "claim_id": r.get("claim_id") or "",
            "claim_kind": r.get("claim_kind") or "",
            "quote": r.get("quote") or "",
        })
    return out


# ── 이름 찾기 ──────────────────────────────────────────────────
def _names() -> dict[str, str]:
    """학원 id → 표시명. 앱 번들에서 읽는다(등록부 포함). 없으면 빈 dict."""
    out: dict[str, str] = {}
    for fname in ("academies.json", "registry.json"):
        path = config.EXPORT_DIR / fname
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rows, dict):
            rows = rows.get("academies") or rows.get("items") or []
        for a in rows or []:
            aid = str(a.get("id") or "")
            name = a.get("displayName") or a.get("display_name") or a.get("name")
            if aid and name:
                out.setdefault(aid, str(name))
            for rid in a.get("registrationIds") or a.get("registration_ids") or []:
                out.setdefault(str(rid), str(name))
    return out


# ── 파일 ──────────────────────────────────────────────────────
def case_id(source: str, source_id: str) -> str:
    prefix = SOURCES.get(source, "xx")
    tail = re.sub(r"[^0-9a-zA-Z가-힣]", "", source_id)[:8].lower() or "00000000"
    return f"{prefix}-{tail}"


def _yaml_scalar(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple, set)):
        return "[" + ", ".join(_yaml_scalar(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{}\"'\n]|^\s|\s$", s) or s.isdigit() \
            or s.lower() in ("true", "false", "null", "yes", "no"):
        return json.dumps(s, ensure_ascii=False)
    return s


def _stub(row: dict, cid: str) -> str:
    name = row.get("entity_name") or row.get("entity_key") or cid
    reason = REASON_KO.get(row.get("reason"), row.get("reason") or "기타")
    front = [
        f"id: {cid}",
        f"source: {row['source']}",
        f"source_id: {_yaml_scalar(row.get('source_id'))}",
        f"source_status: {_yaml_scalar(row.get('source_status'))}",
        f"entity_type: {row.get('entity_type') or 'academy'}",
        f"entity_key: {_yaml_scalar(row.get('entity_key'))}",
        f"entity_name: {_yaml_scalar(row.get('entity_name'))}",
        f"reported_at: {row.get('reported_at') or date.today().isoformat()}",
        f"reason: {row.get('reason') or 'other'}",
    ]
    for k in ("url_hash", "claim_id", "claim_kind"):
        if row.get(k):
            front.append(f"{k}: {_yaml_scalar(row[k])}")
    front += [
        "# ↓ 상태 기계. 에이전트·사람이 바꾼다. 엔진은 요약·감사에만 읽는다.",
        "status: open              # open → triaged → fixed → verified → closed | declined",
        "category:                 # " + " | ".join(CATEGORIES),
        "resolution: []            # " + " | ".join(RESOLUTIONS),
        "fixture:                  # tests/cases/<id>.yaml — 고친 것은 반드시 픽스처가 된다",
        "landed_in:                # 화면이 바뀐 데이터 커밋 sha (verified 로 갈 때)",
    ]
    report_lines = []
    if row.get("title"):
        report_lines.append(f"- 제목: {row['title']}")
    if row.get("source_url"):
        report_lines.append(f"- 원문: {row['source_url']}")
    if row.get("claim_kind"):
        report_lines.append(f"- 주장 종류: {row['claim_kind']}")
    if row.get("quote"):
        report_lines.append(f"- 인용문: {row['quote']}")
    if row.get("requester"):
        report_lines.append(f"- 요청자: {row['requester']}")
    note = (row.get("note") or "").strip()
    if note:
        report_lines.append("- 내용:")
        report_lines += [f"  > {ln}" for ln in note.splitlines()]
    if not report_lines:
        report_lines.append("- (접수 본문 없음)")
    return (
        "---\n" + "\n".join(front) + "\n---\n"
        f"# {name} — {reason}\n\n"
        "## 신고\n<!-- auto:report -->\n" + "\n".join(report_lines) +
        "\n<!-- /auto:report -->\n\n"
        "## 진단\n"
        "(case-triage 가 쓴다 — 어느 종류인지, 왜 그렇게 봤는지, 근거는 "
        "`파일:줄`·실측 수치·원문 URL 로. 판단 절차는 .claude/agents/case-triage.md)\n\n"
        "## 조치\n"
        "(담당 gate-* 에이전트가 쓴다 — 무엇을 어느 층(판정·위키·규칙·코드)에 "
        "바꿨는지, 같은 원인의 다른 학원은 몇 곳인지, 픽스처 경로)\n\n"
        "## 확인\n"
        "(pipeline-verifier 가 쓴다 — 테스트·`--from-cache` 수치·데이터 커밋. "
        "캐시 수치로 '해결됐다' 고 적지 않는다)\n"
    )


def intake() -> dict:
    """미처리 접수를 사례 파일로 옮긴다. 있는 파일은 source_status 만 맞춘다."""
    stats = {"fetched": 0, "created": 0, "updated": 0}
    rows = _fetch_open()
    stats["fetched"] = len(rows)
    if not rows:
        return stats
    names = _names()
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if not row.get("source_id"):
            continue
        row["entity_name"] = row.get("entity_name") or names.get(row["entity_key"], "")
        cid = case_id(row["source"], row["source_id"])
        path = CASE_DIR / f"{cid}.md"
        if path.exists():
            if set_fields(path, source_status=row.get("source_status")):
                stats["updated"] += 1
            continue
        path.write_text(_stub(row, cid), encoding="utf-8")
        stats["created"] += 1
    return stats


def new_manual(entity_key: str, entity_name: str, text: str,
               reason: str = "other", entity_type: str = "academy",
               url_hash: str | None = None) -> Path:
    """대화·메일로 받은 신고를 사례로 적는다. id 는 날짜+이름에서 딴다."""
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%y%m%d%H%M")
    cid = case_id("manual", stamp + re.sub(r"\W", "", entity_key)[:3])
    path = CASE_DIR / f"{cid}.md"
    n = 2
    while path.exists():
        path = CASE_DIR / f"{cid}-{n}.md"
        n += 1
    row = {"source": "manual", "source_id": stamp, "source_status": "open",
           "entity_type": entity_type, "entity_key": entity_key,
           "entity_name": entity_name, "reported_at": date.today().isoformat(),
           "reason": reason, "note": text, "url_hash": url_hash or ""}
    path.write_text(_stub(row, path.stem), encoding="utf-8")
    return path


# ── 읽기·쓰기 ───────────────────────────────────────────────────
def _parse(path: Path) -> dict:
    import yaml
    text = path.read_text(encoding="utf-8")
    m = _FRONT.match(text)
    meta: dict = {}
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("id", path.stem)
    meta["_path"] = path
    meta["_body"] = text[m.end():] if m else text
    for k in ("status", "category", "reason", "source", "entity_type"):
        if meta.get(k) is not None:
            meta[k] = str(meta[k])
    if not isinstance(meta.get("resolution"), list):
        meta["resolution"] = [meta["resolution"]] if meta.get("resolution") else []
    return meta


def load() -> list[dict]:
    if not CASE_DIR.is_dir():
        return []
    return [_parse(p) for p in sorted(CASE_DIR.glob("*.md"))]


def get(cid: str) -> dict | None:
    path = CASE_DIR / f"{cid}.md"
    return _parse(path) if path.exists() else None


def set_fields(target: Path | str, **fields) -> bool:
    """frontmatter 를 줄 단위로 고친다. 산문은 절대 건드리지 않는다.

    questions._write_flag 와 같은 규칙이다. 값이 같으면 아무것도 안 한다.
    모르는 키는 frontmatter 끝에 더한다.
    """
    path = Path(target) if isinstance(target, (str, Path)) and str(target).endswith(".md") \
        else CASE_DIR / f"{target}.md"
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---":
        return False
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return False
    changed = False
    for key, val in fields.items():
        if key == "status" and val not in STATUSES:
            raise ValueError(f"status {val!r} 는 {STATUSES} 중 하나여야 한다")
        if key == "category" and val and val not in CATEGORIES:
            raise ValueError(f"category {val!r} 는 {tuple(CATEGORIES)} 중 하나여야 한다")
        if key == "resolution":
            bad = [v for v in (val or []) if v not in RESOLUTIONS]
            if bad:
                raise ValueError(f"resolution {bad} 는 {RESOLUTIONS} 중 하나여야 한다")
        rendered = _yaml_scalar(val)
        for i in range(1, end):
            m = re.match(rf"{re.escape(key)}:\s*(.*?)(\s+#.*)?$", lines[i])
            if m:
                comment = m.group(2) or ""
                new = f"{key}: {rendered}{comment}" if rendered else f"{key}:{comment}"
                if lines[i] != new:
                    lines[i] = new
                    changed = True
                break
        else:
            lines.insert(end, f"{key}: {rendered}")
            end += 1
            changed = True
    if changed:
        path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def append_section(target: Path | str, section: str, text: str) -> bool:
    """`## 진단`·`## 조치`·`## 확인` 아래에 산문을 덧붙인다.

    절 머리 바로 아래의 안내 괄호문은 첫 기록 때 지운다. 기존 기록은
    지우지 않고 그 뒤에 날짜와 함께 붙인다 — 진단이 바뀐 경위가 남아야
    같은 신고가 다시 왔을 때 어디서 틀렸는지 알 수 있다.
    """
    path = Path(target) if str(target).endswith(".md") else CASE_DIR / f"{target}.md"
    if not path.exists():
        return False
    body = path.read_text(encoding="utf-8")
    head = f"## {section}\n"
    i = body.find(head)
    if i < 0:
        body = body.rstrip("\n") + f"\n\n{head}"
        i = body.find(head)
    j = body.find("\n## ", i + len(head))
    j = len(body) if j < 0 else j
    block = body[i + len(head):j]
    # 첫 기록이면 안내문(괄호로 시작하는 한 문단)을 걷어낸다.
    stripped = block.strip()
    if stripped.startswith("(") and stripped.endswith(")") and "\n\n" not in stripped:
        block = ""
    stamp = date.today().isoformat()
    block = block.rstrip("\n") + f"\n\n### {stamp}\n{text.strip()}\n\n"
    path.write_text(body[:i + len(head)] + block + body[j:], encoding="utf-8")
    return True


# ── 요약·감사 ───────────────────────────────────────────────────
STALE_DAYS = 14


def fixtures() -> dict[str, Path]:
    """사례 id → 픽스처 파일. 픽스처는 `case:` 로 사례를 가리킨다."""
    out: dict[str, Path] = {}
    if not FIXTURE_DIR.is_dir():
        return out
    import yaml
    for p in sorted(FIXTURE_DIR.glob("*.yaml")):
        try:
            fx = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        cid = str(fx.get("case") or p.stem)
        out.setdefault(cid, p)
    return out


def summary(cases: list[dict] | None = None) -> str:
    cases = load() if cases is None else cases
    if not cases:
        return "사례 대장: 비어 있음"
    by_status = Counter(c.get("status") or "open" for c in cases)
    by_cat = Counter(c.get("category") or "미분류"
                     for c in cases if (c.get("status") or "open") in ("open", "triaged"))
    parts = [f"{s} {by_status[s]}" for s in STATUSES if by_status.get(s)]
    line = "사례 대장: " + " · ".join(parts)
    if by_cat:
        line += " ‖ 진행 중 " + " · ".join(f"{k} {n}" for k, n in by_cat.most_common())
    return line


def audit(cases: list[dict] | None = None,
          today: date | None = None) -> list[str]:
    """조용히 묻히는 것을 소리 낸다. 판단하지 않는다 — 알린다.

    - 접수된 지 오래됐는데 아직 open/triaged
    - 고쳤다(fixed 이상)는데 픽스처가 없다 → 같은 신고가 되돌아온다
    - fixed 인데 코드·규칙·위키 어느 층에 고쳤는지(resolution) 비어 있다
    """
    cases = load() if cases is None else cases
    today = today or date.today()
    fx = fixtures()
    out: list[str] = []
    for c in cases:
        cid, status = str(c.get("id")), str(c.get("status") or "open")
        try:
            age = (today - date.fromisoformat(str(c.get("reported_at")))).days
        except (TypeError, ValueError):
            age = 0
        if status in ("open", "triaged") and age >= STALE_DAYS:
            out.append(f"{cid}: 접수 {age}일째 {status} — "
                       f"{c.get('entity_name') or c.get('entity_key')}")
        if status in ("fixed", "verified", "closed"):
            res = set(c.get("resolution") or [])
            if not res:
                out.append(f"{cid}: {status} 인데 resolution 이 비어 있다 — "
                           "어느 층에 고쳤는지 적을 것")
            needs_fixture = res & {"code", "rule", "wiki"}
            if needs_fixture and cid not in fx and not c.get("fixture"):
                out.append(f"{cid}: {'/'.join(sorted(needs_fixture))} 로 고쳤는데 "
                           "회귀 픽스처가 없다 — tests/cases/ 에 적을 것")
        if status == "verified" and not c.get("landed_in"):
            out.append(f"{cid}: verified 인데 landed_in(데이터 커밋)이 없다 — "
                       "캐시 수치로 확인한 것이면 fixed 로 되돌릴 것")
    return out


def report() -> str:
    """`run.py --cases` 가 찍는 한 화면."""
    cases = load()
    lines = [summary(cases)]
    for c in cases:
        if (c.get("status") or "open") in ("open", "triaged"):
            lines.append(f"  [{c['id']}] {c.get('entity_name') or c.get('entity_key')}"
                         f" · {REASON_KO.get(str(c.get('reason')), c.get('reason'))}"
                         f" · {c.get('reported_at')} · {c.get('status')}"
                         + (f" · {c.get('category')}" if c.get("category") else ""))
    for w in audit(cases):
        lines.append(f"  ! {w}")
    if len(lines) == 1 and not cases:
        return lines[0]
    lines.append("  → Claude Code 에서 /triage-reports 로 진단·조치한다")
    return "\n".join(lines)
