"""질문 큐 — 글마다 읽는 검수를 '판단이 필요한 지점만 묻기'로 뒤집는다.

글 검수의 병목은 관리자 시간이고, 판정 한 건의 가치는 낮다. 가치는
**규칙 하나**에 있다 — 반려 사유가 크롤 규칙이 되는 기존 흐름이 그 증거다.
그렇다면 순서가 바뀌어야 한다: 사람이 글더미에서 문제를 찾는 게 아니라,
파이프라인이 의심 지점을 찾아 질문을 만들고 사람은 답만 한다.

질문 다섯 종류. 전부 결정적으로(LLM 없이) 만들어진다.

  confirm_post  경계에 걸린 중요 글 — 일상어 이름·브랜드 공유처럼 자동
                판정이 약한 부류 중 신뢰도가 높은 글만 골라 묻는다.
  exclude_word  반려 이력에서 자란 규칙 후보 — 반려된 글들에 반복되고
                확인된 글에는 없는 낱말. 답 '예' 가 곧 crawl_rule 이 된다.
  locality      같은 학군 형제 지점인데 변별어가 없는 지점 — 답이 곧
                위키 frontmatter `locality:` 가 된다(방배점이 이 경우였다).
  author        같은 작성자가 한 학원에 글을 쏟아냄 — 홍보 계정 확인.
  compare       감성이 갈리는 고신뢰 글 2건 — 어느 쪽이 현재를 더 잘
                보여주는지. 답은 두 글의 신뢰도 보정으로만 쓴다(±20%,
                산식 전체를 흔들지 않는다).

같은 질문은 두 번 묻지 않는다(fingerprint unique). '건너뛰기'도 답이다 —
다시 올라오지 않는다. 답의 적용은 다음 실행의 `apply_answers()` 가 한다:
질문에서 나온 판정·규칙도 결국 기존 mention_reviews·crawl_rules 로
들어가므로 **검수 체계는 그대로**이고, 입구만 질문으로 바뀐 것이다.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date

import requests

from . import config

QUESTION_LIMIT = 12          # 한 실행이 만드는 질문 수. 많으면 다시 노동이 된다.
COMPARE_GAP = 0.8            # 감성 차이가 이만큼 나야 비교를 묻는다
AUTHOR_MIN = 8               # 같은 작성자 글이 이만큼이면 홍보 계정을 묻는다


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _get(params: dict) -> list[dict]:
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/review_questions",
                         params=params, headers=_headers(), timeout=20)
        return r.json() if r.status_code == 200 else []
    except requests.RequestException:
        return []


_WORD = re.compile(r"[가-힣A-Za-z]{2,}")


def _title_words(title: str) -> set[str]:
    return set(_WORD.findall(title or ""))


# ── 질문 생성 ───────────────────────────────────────────────────
def generate(mentions: list[dict], academies: list[dict],
             generic: dict[str, bool], verdicts: dict[str, str],
             rules: list[dict],
             wiki_locality: dict[str, set[str]] | None = None) -> list[dict]:
    """이번 실행의 질문 후보를 만든다. 우선순위 큰 것부터 QUESTION_LIMIT 개."""
    by_id = {a["id"]: a for a in academies}
    name_of = {a["id"]: (a.get("display_name") or a.get("name") or "")
               for a in academies}
    sample = Counter(m["academy_key"] for m in mentions
                     if not m.get("is_excluded"))
    out: list[dict] = []

    def add(kind, fp, academy_key, question, payload, options, priority):
        out.append({
            "fingerprint": fp, "kind": kind,
            "academy_key": academy_key,
            "academy_name": name_of.get(academy_key),
            "question": question, "payload": payload,
            "options": options, "priority": round(priority, 2),
            "status": "pending",
        })

    # 1) confirm_post — 자동 판정이 약한 부류의 고신뢰 글
    risky = [m for m in mentions
             if not m.get("is_excluded")
             and m.get("credibility", 0) >= 0.6
             and (generic.get(m.get("academy_key"))
                  or m.get("branch_basis") == "brand")
             and f"{m.get('url_hash')}|{m.get('academy_key')}" not in verdicts]
    risky.sort(key=lambda m: -m.get("credibility", 0))
    seen_docs: set[str] = set()
    for m in risky:
        if len([q for q in out if q["kind"] == "confirm_post"]) >= 4:
            break
        if m["url_hash"] in seen_docs:
            continue
        seen_docs.add(m["url_hash"])
        aid = m["academy_key"]
        if aid not in name_of:
            continue          # 흡수된 옛 id — 이름 없는 질문은 답할 수 없다
        why = "이름이 일상어와 겹쳐" if generic.get(aid) else "지점 불명 브랜드 글이라"
        add("confirm_post", f"cp|{m['url_hash']}|{aid}", aid,
            f"{why} 자동 판정이 약합니다. 이 글은 {name_of.get(aid)} 글이 맞나요?",
            {"review_key": f"{m['url_hash']}|{aid}",
             "title": (m.get("title") or "")[:200],
             "snippet": (m.get("snippet") or "")[:300],
             "source_url": m.get("source_url")},
            [{"value": "yes", "label": "맞음"},
             {"value": "exclude", "label": "아님 — 제외"},
             {"value": "ad", "label": "광고·홍보"}],
            m.get("credibility", 0) * 10)

    # 2) exclude_word — 반려된 글들에 반복되고 확인된 글에는 없는 낱말
    rejected_rows, confirmed_rows = _fetch_reviewed()
    rej_words: dict[str, Counter] = defaultdict(Counter)
    for r in rejected_rows:
        _, _, aid = (r.get("url_hash") or "").partition("|")
        cands = _title_words(r.get("title"))
        nm = name_of.get(aid, "")
        for w in cands:
            if w not in nm:
                rej_words[aid][w] += 1
    conf_words: dict[str, set[str]] = defaultdict(set)
    for r in confirmed_rows:
        _, _, aid = (r.get("url_hash") or "").partition("|")
        conf_words[aid] |= _title_words(r.get("title"))
    ruled = {(str(r.get("academy_key")), r.get("pattern")) for r in rules}
    n_word = 0
    for aid, counter in rej_words.items():
        if n_word >= 3 or aid not in by_id:
            break
        for w, n in counter.most_common(3):
            if n < 2 or w in conf_words.get(aid, set()):
                continue
            if (aid, w) in ruled:
                continue
            add("exclude_word", f"xw|{aid}|{w}", aid,
                f"{name_of.get(aid)} 반려 글 {n}건에 '{w}' 가 반복됩니다. "
                f"이 말이 있으면 제외하는 규칙을 만들까요?",
                {"word": w, "count": n},
                [{"value": "yes", "label": "규칙으로 굳힘"},
                 {"value": "no", "label": "아니오 — 우연"}],
                n * 5)
            n_word += 1
            break

    # 3) locality — 같은 학군 형제 지점인데 변별어가 없는 지점
    from . import branches
    same_region: dict[tuple, list[dict]] = defaultdict(list)
    for a in academies:
        key = branches.sibling_key(a)
        if key:
            same_region[(key, a.get("region_id"))].append(a)
    n_loc = 0
    for rows in same_region.values():
        if len(rows) < 2 or n_loc >= 3:
            continue
        for a in rows:
            words = branches.locality_words(a) | \
                (wiki_locality or {}).get(a["id"], set())
            if words:
                continue
            peers = [name_of.get(b["id"], "") for b in rows if b["id"] != a["id"]]
            add("locality", f"loc|{a['id']}", a["id"],
                f"{name_of.get(a['id'])} 은(는) 같은 학군의 {', '.join(peers[:2])} "
                f"와 형제 지점인데 구분할 동네 말이 없습니다. 이 지점을 부르는 "
                f"동네 이름을 알려 주세요 (예: 방배).",
                {"peers": peers}, None,          # 자유 입력
                len(rows) * 8)
            n_loc += 1
            break

    # 4) author — 같은 작성자가 한 학원에 글을 쏟아냄
    heavy: dict[tuple, list[dict]] = defaultdict(list)
    for m in mentions:
        if (m.get("repeat_author_count") or 0) >= AUTHOR_MIN:
            heavy[(m["academy_key"], m.get("author_hash"))].append(m)
    for (aid, ah), rows in sorted(heavy.items(), key=lambda t: -len(t[1]))[:2]:
        if not ah or (str(aid), ah) in ruled:
            continue
        titles = [r.get("title", "")[:60] for r in rows[:3]]
        add("author", f"au|{aid}|{ah}", aid,
            f"한 작성자가 {name_of.get(aid)} 글을 {len(rows)}건 올렸습니다. "
            f"홍보 계정으로 보고 전부 제외할까요? (지금은 감쇠만 적용 중)",
            {"author_hash": ah, "count": len(rows), "titles": titles},
            [{"value": "yes", "label": "전부 제외"},
             {"value": "no", "label": "정상 이용자"}],
            len(rows) * 1.0)

    # 5) compare — 감성이 갈리는 고신뢰 글 2건. 답은 신뢰도 보정(±20%)만.
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        if not m.get("is_excluded") and m.get("credibility", 0) >= 0.55:
            by_ac[m["academy_key"]].append(m)
    n_cmp = 0
    for aid, rows in sorted(by_ac.items(), key=lambda t: -sample[t[0]]):
        if n_cmp >= 2 or sample[aid] < 30:
            continue
        rows.sort(key=lambda m: -m.get("credibility", 0))
        top = rows[:6]
        pair = None
        for i, m1 in enumerate(top):
            for m2 in top[i + 1:]:
                if abs(m1.get("sentiment", 0) - m2.get("sentiment", 0)) >= COMPARE_GAP:
                    pair = sorted([m1, m2], key=lambda m: m["url_hash"])
                    break
            if pair:
                break
        if not pair:
            continue
        fp = f"cmp|{aid}|{pair[0]['url_hash'][:12]}|{pair[1]['url_hash'][:12]}"
        add("compare", fp, aid,
            f"{name_of.get(aid)} 의 고신뢰 글 두 건의 평가가 갈립니다. "
            f"어느 글이 이 학원의 현재를 더 잘 보여주나요?",
            {"a": {"url_hash": pair[0]["url_hash"],
                   "title": (pair[0].get("title") or "")[:150],
                   "source_url": pair[0].get("source_url"),
                   "sentiment": pair[0].get("sentiment")},
             "b": {"url_hash": pair[1]["url_hash"],
                   "title": (pair[1].get("title") or "")[:150],
                   "source_url": pair[1].get("source_url"),
                   "sentiment": pair[1].get("sentiment")}},
            [{"value": "a", "label": "첫째 글"},
             {"value": "b", "label": "둘째 글"},
             {"value": "same", "label": "비슷하다"}],
            sample[aid] / 10)
        n_cmp += 1

    out.sort(key=lambda q: -q["priority"])
    return out[:QUESTION_LIMIT]


def _fetch_reviewed() -> tuple[list[dict], list[dict]]:
    """반려·확인된 글의 제목. exclude_word 후보의 원료다."""
    if not config.HAS_SUPABASE:
        return [], []
    try:
        rej = requests.get(
            f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
            params={"select": "url_hash,title", "verdict": "eq.rejected",
                    "limit": "500"},
            headers=_headers(), timeout=20)
        conf = requests.get(
            f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
            params={"select": "url_hash,title", "verdict": "eq.confirmed",
                    "limit": "1000"},
            headers=_headers(), timeout=20)
        return (rej.json() if rej.status_code == 200 else [],
                conf.json() if conf.status_code == 200 else [])
    except requests.RequestException:
        return [], []


def enqueue(questions: list[dict]) -> int:
    """질문을 올린다. fingerprint 중복은 조용히 건너뛴다 — 한 번 물은 것,
    한 번 건너뛴 것을 다시 묻지 않는다."""
    if not config.HAS_SUPABASE or not questions:
        return 0
    try:
        r = requests.post(
            f"{config.SUPABASE_URL}/rest/v1/review_questions",
            headers={**_headers(),
                     "Prefer": "resolution=ignore-duplicates,return=minimal"},
            data=json.dumps(questions), timeout=30)
        return len(questions) if r.status_code < 300 else 0
    except requests.RequestException:
        return 0


# ── 답 적용 ─────────────────────────────────────────────────────
def apply_answers() -> dict:
    """답변된 질문을 실제 조치로 바꾼다.

    질문의 답도 결국 기존 경로(mention_reviews·crawl_rules·위키)로
    들어간다 — 검수 체계는 그대로, 입구만 질문이다. 일회성 답은
    status=applied 로 밀봉하고, compare 는 계속 살아 신뢰도 보정을 준다.
    """
    stats = {"verdicts": 0, "rules": 0, "locality": 0, "compare": 0}
    boost: dict[str, float] = {}
    if not config.HAS_SUPABASE:
        return {**stats, "boost": boost}

    rows = _get({"select": "*", "status": "eq.answered"})
    today = date.today().isoformat()
    done: list[str] = []

    for q in rows:
        kind, ans = q.get("kind"), (q.get("answer") or {})
        val = ans.get("value")
        payload = q.get("payload") or {}
        aid = q.get("academy_key")

        if kind == "confirm_post" and val in ("yes", "exclude", "ad"):
            verdict = "confirmed" if val == "yes" else "rejected"
            reason = None if val == "yes" else \
                ("ad" if val == "ad" else "irrelevant")
            _upsert_review(payload.get("review_key"), aid,
                           q.get("academy_name"), payload, verdict, reason)
            stats["verdicts"] += 1
            done.append(q["id"])

        elif kind == "exclude_word":
            if val == "yes" and _add_rule(
                    aid, "exclude_keyword", payload.get("word"),
                    f"질문 답변({today}): 반려 글 {payload.get('count')}건에서 "
                    f"반복된 낱말"):
                stats["rules"] += 1
            done.append(q["id"])

        elif kind == "author":
            if val == "yes" and _add_rule(
                    aid, "exclude_author", payload.get("author_hash"),
                    f"질문 답변({today}): 동일 작성자 글 "
                    f"{payload.get('count')}건 — 홍보 계정 판정"):
                stats["rules"] += 1
            done.append(q["id"])

        elif kind == "locality":
            word = (ans.get("text") or "").strip().rstrip("동")
            if word and _write_locality(aid, word):
                stats["locality"] += 1
            done.append(q["id"])

        elif kind == "compare":
            # 일회성이 아니다 — 답이 살아 있는 동안 두 글의 신뢰도를
            # 보정한다(±20%). 산식을 흔들지 않는 상한이다.
            if val in ("a", "b"):
                win = (payload.get(val) or {}).get("url_hash")
                lose = (payload.get("b" if val == "a" else "a") or {}).get("url_hash")
                if win:
                    boost[win] = 1.2
                if lose:
                    boost[lose] = 0.8
                stats["compare"] += 1
            # same → 보정 없음. applied 로 밀봉.
            if val == "same":
                done.append(q["id"])

    if done:
        try:
            requests.patch(
                f"{config.SUPABASE_URL}/rest/v1/review_questions",
                params={"id": f"in.({','.join(done)})"},
                headers=_headers(),
                data=json.dumps({"status": "applied"}), timeout=20)
        except requests.RequestException:
            pass
    return {**stats, "boost": boost}


def _upsert_review(review_key, aid, name, payload, verdict, reason):
    if not review_key:
        return
    try:
        requests.post(
            f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
            headers={**_headers(),
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            data=json.dumps([{
                "url_hash": review_key, "academy_key": aid,
                "academy_name": name,
                "title": payload.get("title"),
                "snippet": payload.get("snippet"),
                "source_url": payload.get("source_url"),
                "verdict": verdict, "reject_reason": reason,
                "note": "질문 답변",
            }]), timeout=20)
    except requests.RequestException:
        pass


def _add_rule(aid, kind, pattern, reason) -> bool:
    if not (aid and pattern):
        return False
    try:
        r = requests.post(
            f"{config.SUPABASE_URL}/rest/v1/crawl_rules",
            headers={**_headers(),
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            data=json.dumps([{
                "scope": "academy", "academy_key": aid,
                "kind": kind, "pattern": pattern, "reason": reason,
            }]), timeout=20)
        return r.status_code < 300
    except requests.RequestException:
        return False


def _write_locality(aid: str, word: str) -> bool:
    """답을 위키 frontmatter 에 적는다. 산문은 건드리지 않는다 — 줄 단위로
    frontmatter 만 고쳐 사람이 쓴 나머지를 그대로 둔다."""
    from . import wiki as wiki_mod
    path = wiki_mod.ACADEMY_DIR / f"{aid}.md"
    if not path.exists():
        wiki_mod.ACADEMY_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'---\nid: "{aid}"\nlocality: [{word}]\n---\n# {aid}\n\n'
            f"(질문 답변으로 생성 — 규약은 ../SCHEMA.md)\n\n"
            f"## 판정 이력\n<!-- auto:review -->\n<!-- /auto:review -->\n\n"
            f"## 통계\n<!-- auto:stats -->\n<!-- /auto:stats -->\n",
            encoding="utf-8")
        return True
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---":
        return False
    end = lines[1:].index("---") + 1
    for i in range(1, end):
        m = re.match(r"locality:\s*\[(.*)\]\s*$", lines[i])
        if m:
            have = [w.strip() for w in m.group(1).split(",") if w.strip()]
            if word in have:
                return False
            lines[i] = f"locality: [{', '.join(have + [word])}]"
            break
    else:
        lines.insert(end, f"locality: [{word}]")
    path.write_text("\n".join(lines), encoding="utf-8")
    return True
