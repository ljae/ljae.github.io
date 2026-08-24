"""참조 글 검수 큐 — 사람의 판정을 크롤러 규칙으로 되먹인다.

관련성 게이트는 '학원명이 본문에 있는가'만 본다. 그래서 사람 이름과
학원명이 같으면 걸러내지 못한다. 실측: '윤도영' 등장 글 146건 중
10건이 뮤지컬 배우 윤도영에 대한 글이었고 그대로 평판에 반영됐다.

이 모듈이 하는 일은 셋이다.

1. **올린다** — 검수가 필요한 글을 `mention_reviews` 에 넣는다.
   전부 올리지 않는다. 이미 판정된 것과, 규칙으로 자동 처리된 것은 뺀다.
2. **적용한다** — 사람이 rejected 로 판정한 글은 다음 수집부터 제외한다.
3. **규칙으로 굳힌다** — `crawl_rules` 를 읽어 수집 단계에서 미리 거른다.
   판정이 쌓여도 규칙이 안 생기면 사람이 영원히 같은 걸 누르게 된다.

★ 키는 url_hash 다. 같은 글이 여러 학원에 걸릴 수 있지만, 판정은
  글 단위가 아니라 (글, 학원) 단위여야 한다 — '윤도영'을 뺀 글이
  다른 학원에서는 정상 근거일 수 있다. url_hash 에 학원키를 섞는다.
"""
from __future__ import annotations

import json
import re

import requests

from . import config

# 검수 대기로 올릴 최대 **글** 수. 한 글이 여러 학원에 걸리면 판정은
# 학원별로 여러 건이 되지만, 사람이 읽는 것은 글 하나다. 판정 수로 세면
# 실제로 보는 글이 절반도 안 된다(실측: 292건 → 231글).
QUEUE_LIMIT = 200

REJECT_REASONS = {
    "person": "동명이인 (사람 이름)",
    "different_academy": "다른 학원",
    "other_region": "다른 지역 지점",
    "reclassified": "다른 학원 글로 재분류",
    "ad": "광고·홍보글",
    "sale": "판매·중고거래",
    "irrelevant": "학원과 무관",
    "other": "기타",
}


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _key(mention: dict) -> str:
    """(글, 학원) 단위 식별자."""
    return f"{mention.get('url_hash')}|{mention.get('academy_key')}"


# ── 규칙 ────────────────────────────────────────────────────────
def load_rules() -> list[dict]:
    """활성 크롤 규칙. 없거나 실패하면 빈 목록으로 조용히 넘어간다."""
    if not config.HAS_SUPABASE:
        return []
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/crawl_rules",
                         params={"select": "*", "active": "eq.true"},
                         headers=_headers(), timeout=20)
        return r.json() if r.status_code == 200 else []
    except requests.RequestException:
        return []


def apply_rules(mentions: list[dict], rules: list[dict]) -> tuple[list[dict], int]:
    """규칙에 걸리는 글을 뺀다. (남은 글, 걸러낸 수)"""
    if not rules:
        return mentions, 0

    out, dropped = [], 0
    for m in mentions:
        blob = f"{m.get('title', '')} {m.get('snippet', '')}"
        title = m.get("title", "") or ""
        url = m.get("source_url") or ""
        key = m.get("academy_key")
        drop = False
        for rule in rules:
            if rule.get("scope") == "academy" and rule.get("academy_key") != key:
                continue
            pat = rule.get("pattern") or ""
            if not pat:
                continue
            kind = rule.get("kind")
            if kind == "exclude_keyword" and re.search(pat, blob, re.I):
                drop = True
            elif kind == "exclude_domain" and pat.lower() in url.lower():
                drop = True
            elif kind == "require_keyword" and not re.search(pat, blob, re.I):
                drop = True
            elif kind == "exclude_region" and re.search(pat, title, re.I):
                # 지역 규칙은 **제목만** 본다. 본문의 지역명은 대개 남의
                # 상호다 — '세종 엄마표영어' 글이 본문의 '대치M수학' 때문에
                # 대치 근거가 됐던 것과 같은 함정이다(branches.py 참고).
                drop = True
            if drop:
                break
        if drop:
            dropped += 1
        else:
            out.append(m)
    return out, dropped


# ── 판정 ────────────────────────────────────────────────────────
def load_verdicts() -> dict[str, str]:
    """{키: verdict}. rejected 인 글은 다음 수집부터 근거에서 뺀다."""
    if not config.HAS_SUPABASE:
        return {}
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
                         params={"select": "url_hash,verdict",
                                 "verdict": "neq.pending"},
                         headers=_headers(), timeout=20)
        if r.status_code != 200:
            return {}
        return {row["url_hash"]: row["verdict"] for row in r.json()}
    except requests.RequestException:
        return {}


def apply_verdicts(mentions: list[dict], verdicts: dict[str, str]) -> tuple[list[dict], int]:
    if not verdicts:
        return mentions, 0
    out, dropped = [], 0
    for m in mentions:
        # reclassified 는 '이 학원의 근거는 아니다' — 여기서는 반려와 같다.
        # '대신 어느 학원의 근거인가'는 apply_reassignments 가 따로 붙인다.
        if verdicts.get(_key(m)) in ("rejected", "reclassified"):
            dropped += 1
            continue
        out.append(m)
    return out, dropped


# ── 재분류 ──────────────────────────────────────────────────────
def load_reassignments() -> dict[str, list[str]]:
    """{url_hash: [학원 id, ...]}.

    네 학원을 비교하는 글이 한 곳에만 붙는 일이 있다. 반려만 가능하면
    글은 멀쩡한데 통째로 버려진다 — 어느 학원 글인지 사람이 아는데도
    그 정보를 못 남기는 것이다.
    """
    if not config.HAS_SUPABASE:
        return {}
    try:
        r = requests.get(f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
                         params={"select": "url_hash,reassign_to",
                                 "reassign_to": "not.is.null"},
                         headers=_headers(), timeout=20)
        if r.status_code != 200:
            return {}
    except requests.RequestException:
        return {}

    out: dict[str, list[str]] = {}
    for row in r.json():
        # 검수 키는 'url_hash|academy_key' 다. 재분류는 글 단위이므로
        # 앞자리만 쓴다.
        doc = str(row.get("url_hash") or "").split("|")[0]
        targets = row.get("reassign_to") or []
        if not doc or not targets:
            continue
        seen = out.setdefault(doc, [])
        for t in targets:
            if t not in seen:
                seen.append(t)
    return out


def apply_reassignments(mentions: list[dict], targets: dict[str, list[str]],
                        academies: list[dict]) -> tuple[list[dict], int]:
    """사람이 지목한 학원에 그 글을 근거로 붙인다.

    원문은 이미 수집돼 있으므로 복제만 하면 된다. 그 학원으로 수집된
    적이 없어도 붙는다 — 그게 재분류의 목적이다.
    """
    if not targets:
        return mentions, 0

    by_id = {a["id"]: a for a in academies}
    have = {(m.get("url_hash"), m.get("academy_key")) for m in mentions}
    # 복제의 원본은 그 글이면 아무거나 좋다. 제목·본문은 같다.
    source: dict[str, dict] = {}
    for m in mentions:
        source.setdefault(m.get("url_hash"), m)

    added = 0
    out = list(mentions)
    for doc, keys in targets.items():
        base = source.get(doc)
        if base is None:
            continue          # 이번 회차에 그 글이 안 잡혔다
        for key in keys:
            academy = by_id.get(key)
            if academy is None or (doc, key) in have:
                continue
            copy = dict(base)
            copy["academy_key"] = key
            copy["academy_name"] = academy.get("name")
            copy["region_id"] = academy.get("region_id")
            copy["branch_basis"] = "reclassified"
            out.append(copy)
            have.add((doc, key))
            added += 1
    return out, added


# ── 큐 적재 ─────────────────────────────────────────────────────
def enqueue(mentions: list[dict], academies: list[dict],
            verdicts: dict[str, str]) -> int:
    """검수가 필요한 글을 올린다.

    우선순위: 평판에 실제로 실린 글(신뢰도 높은 순). 점수에 영향이 큰
    글부터 봐야 검수 한 번의 값어치가 크다.
    """
    if not config.HAS_SUPABASE:
        return 0
    names = {a["id"]: (a.get("display_name") or a.get("name") or "")
             for a in academies}

    todo = [m for m in mentions
            if not m.get("is_excluded") and _key(m) not in verdicts]
    todo.sort(key=lambda m: -float(m.get("credibility", 0)))

    # 글 단위로 세어 상한을 건다. 같은 글에 걸린 학원은 함께 올린다 —
    # 화면에서 한 번에 판정하므로 쪼개 올리면 다음 회차에 나머지가
    # 또 올라와 같은 글을 두 번 보게 된다.
    picked, seen = [], set()
    for m in todo:
        doc = m.get("source_url") or m.get("url_hash")
        if doc not in seen:
            if len(seen) >= QUEUE_LIMIT:
                continue
            seen.add(doc)
        picked.append(m)
    todo = picked
    if not todo:
        return 0

    rows = [{
        "url_hash": _key(m),
        "academy_key": m.get("academy_key"),
        "academy_name": names.get(m.get("academy_key")),
        "title": (m.get("title") or "")[:300],
        "snippet": (m.get("snippet") or "")[:600],
        "source": m.get("source"),
        "source_url": m.get("source_url"),
        "posted_at": m.get("posted_at"),
        "verdict": "pending",
    } for m in todo]

    try:
        r = requests.post(
            f"{config.SUPABASE_URL}/rest/v1/mention_reviews",
            headers={**_headers(),
                     "Prefer": "resolution=ignore-duplicates,return=minimal"},
            data=json.dumps(rows), timeout=60)
        if r.status_code >= 300:
            print(f"  검수 큐 적재 실패 {r.status_code}: {r.text[:120]}")
            return 0
    except requests.RequestException as exc:
        print(f"  검수 큐 적재 실패: {exc}")
        return 0
    return len(rows)
