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

# 검수 대기로 올릴 최대 건수. 한 번에 수천 건을 올리면 사람이 못 본다.
QUEUE_LIMIT = 300

REJECT_REASONS = {
    "person": "동명이인 (사람 이름)",
    "different_academy": "다른 학원",
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
        if verdicts.get(_key(m)) == "rejected":
            dropped += 1
            continue
        out.append(m)
    return out, dropped


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
    todo = todo[:QUEUE_LIMIT]
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
