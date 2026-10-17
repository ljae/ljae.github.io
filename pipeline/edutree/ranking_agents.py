"""Bounded reflection → planning → verified feedback for review collection.

Only search allocation learns. Scores, gate rules, case verdicts and publication
dates remain the responsibility of their existing owners. A high gate yield is
an operational observation, not an estimate of factual accuracy.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import cases as case_ledger, config
from .case_replay import verify_history

VERSION = 1
MAX_TASKS = 200
MAX_HISTORY = 256
MAX_ACADEMIES = 5000
RETENTION_DAYS = 180
REFRESH_DAYS = 7
ARMS = ("exact_local", "cafe_local", "blog_local", "dated_local")
COUNTERS = ("attempts", "collected", "accepted", "duplicates", "unknown_dates", "failures")
STATE_PATH = config.CACHE_DIR / "ranking_agents" / "memory.json"

# These are curated constraints distilled from actual repository history. Prose
# from arbitrary web pages/cases never becomes executable policy or a new label.
LESSONS = (
    {"id": "identity", "category": "relevance",
     "rule": "Search full registered names; keep ordinary words and lists behind existing name gates.",
     "sources": ["CLAUDE.md:902", "pipeline/wiki/concepts/일상어-학원명.md",
                 "pipeline/wiki/concepts/나열형-비교글.md"]},
    {"id": "branch", "category": "branch",
     "rule": "Add local place names to queries; a brand result does not establish its branch.",
     "sources": ["CLAUDE.md:2409",
                 "pipeline/wiki/concepts/지점-구분.md"]},
    {"id": "coverage", "category": "coverage",
     "rule": "Explore missing evidence across regions and subjects; capacity and rank are not demand labels.",
     "sources": ["CLAUDE.md:178", "pipeline/wiki/concepts/선정-편향.md"]},
    {"id": "dates", "category": "date",
     "rule": "Unknown publication dates remain unknown; discovery dates cannot create freshness.",
     "sources": ["CLAUDE.md:794", "pipeline/edutree/scoring.py"]},
    {"id": "retention", "category": "duplicate",
     "rule": "Keep raw evidence across runs; repeated URLs are not new successful discoveries.",
     "sources": ["CLAUDE.md:2172", "pipeline/edutree/mention_store.py"]},
    {"id": "retry", "category": "failure",
     "rule": "Bound retries and shorten dry-search cooldown; changed queries may retry immediately.",
     "sources": ["CLAUDE.md:2543"]},
    {"id": "fixed_policy", "category": "score",
     "rule": "Improve collection allocation only; human-reviewed fixtures and scoring weights are fixed.",
     "sources": ["docs/AGENTS.md", "pipeline/tests/cases/README.md"]},
)


def _now(value: datetime | date | str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _count(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _new_memory() -> dict:
    return {"version": VERSION, "arms": {}, "academies": {}, "history": [], "outcomes": 0}


def _validate(memory: dict) -> None:
    if not isinstance(memory, dict) or memory.get("version") != VERSION:
        raise ValueError("unsupported ranking agent memory version")
    if set(memory) - {"feedback"} != {"version", "arms", "academies", "history", "outcomes"}:
        raise ValueError("unexpected ranking agent memory fields")
    if "feedback" in memory:
        from . import agent_feedback
        agent_feedback.validate_provenance(memory["feedback"])
    for field in ("arms", "academies"):
        if not isinstance(memory.get(field), dict):
            raise ValueError(f"invalid memory {field}")
    if not isinstance(memory.get("history"), list):
        raise ValueError("invalid memory history")
    _count(memory.get("outcomes"), "outcomes")
    for arm, stats in memory["arms"].items():
        if arm not in ARMS or not isinstance(stats, dict):
            raise ValueError(f"invalid query arm: {arm}")
        for field in COUNTERS:
            _count(stats.get(field, 0), field)
        if stats.get("accepted", 0) + stats.get("duplicates", 0) > stats.get("collected", 0):
            raise ValueError("accepted + duplicates exceeds collected")
        if stats.get("unknown_dates", 0) > stats.get("accepted", 0):
            raise ValueError("unknown_dates exceeds accepted")
        if not isinstance(stats.get("rejections", {}), dict):
            raise ValueError("invalid rejection counts")
        for count in stats.get("rejections", {}).values():
            _count(count, "rejections")
    for key, stats in memory["academies"].items():
        if not isinstance(key, str) or not isinstance(stats, dict):
            raise ValueError("invalid academy memory")
        for field in ("last_attempt", "cooldown_until"):
            if stats.get(field):
                _now(stats[field])
        _count(stats.get("failure_streak", 0), "failure_streak")
    for row in memory["history"]:
        if not isinstance(row, dict) or not row.get("task_id") or not row.get("at"):
            raise ValueError("invalid outcome trace")
        _now(row["at"])


def load_memory(path: Path | str | None = None) -> dict:
    """Missing state starts fresh; corrupt existing state is never silently reset."""
    path = Path(path) if path is not None else STATE_PATH
    if not path.exists():
        return _new_memory()
    memory = json.loads(path.read_text(encoding="utf-8"))
    _validate(memory)
    return memory


def _bounded(memory: dict, now: datetime) -> dict:
    result = copy.deepcopy(memory)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    result["history"] = sorted(
        (row for row in result["history"] if _now(row["at"]) >= cutoff),
        key=lambda row: (row["at"], row["task_id"]))[-MAX_HISTORY:]
    result["academies"] = dict(sorted(result["academies"].items(),
        key=lambda pair: (pair[1].get("last_attempt", ""), pair[0]))[-MAX_ACADEMIES:])
    for stats in result["arms"].values():
        # Preserve approximate historical ratios while keeping counters bounded.
        while max((stats.get(key, 0) for key in COUNTERS), default=0) > 1_000_000:
            for key in COUNTERS:
                stats[key] = stats.get(key, 0) // 2
            stats["rejections"] = {key: value // 2 for key, value in stats.get("rejections", {}).items()}
    return result


def save_memory(path: Path | str, memory: dict, now=None) -> None:
    """Atomic replace using a unique temporary file; do not overwrite corrupt state."""
    _validate(memory)
    path = Path(path)
    if path.exists():
        load_memory(path)
    bounded = _bounded(memory, _now(now))
    payload = json.dumps(bounded, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    memory.clear()
    memory.update(bounded)


def historical_lessons(case_dir: Path | None = None, fixture_dir: Path | None = None) -> list[dict]:
    """Attach auditable sources, without interpreting ledger prose as policy."""
    fixture_dir = Path(fixture_dir) if fixture_dir is not None else case_ledger.FIXTURE_DIR
    case_dir = Path(case_dir) if case_dir is not None else case_ledger.CASE_DIR
    lessons = copy.deepcopy(list(LESSONS))
    by_category = {row["category"]: row for row in lessons}
    for path in sorted(fixture_dir.glob("*.yaml")):
        fixture = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        category = fixture.get("kind")
        if category not in by_category:
            # Subject/merge/claim are verification obligations, never new search labels.
            category = "score"
        lesson = by_category[category]
        reference = str(path.relative_to(config.ROOT)) if path.is_relative_to(config.ROOT) else str(path)
        lesson.setdefault("fixtures", []).append(reference)
    for path in sorted(case_dir.glob("*.md")):
        case = case_ledger._parse(path)
        lesson = by_category.get(case.get("category"))
        if lesson is not None:
            reference = str(path.relative_to(config.ROOT)) if path.is_relative_to(config.ROOT) else str(path)
            lesson.setdefault("cases", []).append({"source": reference, "status": case.get("status")})
    return lessons


def reflect(memory: dict, quality: dict | None = None, cases: list[dict] | None = None) -> dict:
    """Observe gate failures and case backlog without inventing correctness labels."""
    _validate(memory)
    reasons = Counter()
    for stats in memory["arms"].values():
        reasons.update(stats.get("rejections", {}))
    quality = quality or {}
    reasons.update(quality.get("exclusionReasons") or {})
    ledger = case_ledger.load() if cases is None else cases
    unresolved = Counter(str(case.get("category") or "other") for case in ledger
                         if case.get("status") in ("open", "triaged", "fixed"))
    return {"role": "reflection", "rejections": dict(reasons.most_common(16)),
            "open_case_categories": dict(sorted(unresolved.items())),
            "dated_share": quality.get("datedShare"),
            "lessons": historical_lessons(),
            "measurement": "verified gate yield; not factual accuracy",
            "policy": "query allocation only; fixed gates, weights, and human fixture labels"}


def _fingerprint(academy: dict) -> str:
    # Only fields used in the query/branch identity can bypass cooldown. An
    # unused alias or a changed sample count is not a new collection strategy.
    identity = [academy.get("name"), academy.get("region_id"), academy.get("dong")]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:16]


def _arm_score(arm: str, memory: dict, observation: dict) -> tuple[float, dict]:
    stats = memory["arms"].get(arm, {})
    attempts = stats.get("attempts", 0)
    collected = stats.get("collected", 0)
    accepted = stats.get("accepted", 0)
    known_dates = accepted - stats.get("unknown_dates", 0)
    # Every raw result stays in the denominator, including old/duplicate URLs.
    # Unknown dates get no freshness reward; they are not treated as old dates.
    reward = accepted * 0.7 + known_dates * 0.3
    yield_estimate = (reward + 1) / (collected + 4)
    exploration = math.sqrt(math.log(memory["outcomes"] + 2) / (attempts + 1)) * 0.15
    penalty = min(0.3, stats.get("failures", 0) / max(attempts, 1) * 0.3)
    adaptation = 0.0
    failures = observation["rejections"]
    identity_rejections = sum(n for reason, n in failures.items()
                              if any(term in reason.lower() for term in ("branch", "region", "relev", "name")))
    if arm == "exact_local" and identity_rejections:
        adaptation += 0.08
    if arm in ("blog_local", "dated_local") and observation["dated_share"] is not None \
            and observation["dated_share"] < 0.5:
        adaptation += 0.08
    value = yield_estimate + exploration + adaptation - penalty
    return value, {"attempts": attempts, "collected": collected,
                   "accepted": accepted, "duplicates": stats.get("duplicates", 0),
                   "unknown_dates": stats.get("unknown_dates", 0),
                   "gate_yield": round(accepted / collected, 4) if collected else None,
                   "allocation_value": round(value, 4)}


def _query(academy: dict, arm: str, regions: dict, now: datetime) -> tuple[str, str]:
    # A short alias is not automatically a safe independent identity query.
    name = " ".join(str(academy["name"]).replace('"', " ").split())
    locality = academy.get("dong") or regions.get(academy.get("region_id"), academy.get("region_id", ""))
    query = f'"{name}" {locality} 후기'.strip()
    source = "naver_blog"
    if arm == "cafe_local":
        query += " site:cafe.naver.com"
        source = "naver_cafe"
    elif arm == "blog_local":
        query += " site:blog.naver.com"
        source = "naver_blog"
    elif arm == "dated_local":
        query += f" {now.year}"
    return query, source


def plan(academies: list[dict], memory: dict, limit: int = 12, now=None,
         quality: dict | None = None, cases: list[dict] | None = None) -> list[dict]:
    """Read-only, deterministic and budgeted; rotate across region/subject cohorts."""
    _count(limit, "limit")
    if limit > MAX_TASKS:
        raise ValueError(f"limit exceeds {MAX_TASKS}")
    instant = _now(now)
    observation = reflect(memory, quality, cases)
    regions = {r["id"]: r["name_ko"] for r in config.regions()}
    ledger = case_ledger.load() if cases is None else cases
    case_targets = {str(case.get("entity_key")) for case in ledger
                    if case.get("status") in ("open", "triaged", "fixed")}
    arm_values = {arm: _arm_score(arm, memory, observation) for arm in ARMS}
    planned_arms = Counter()
    cohorts = defaultdict(list)
    seen = set()
    for academy in academies:
        key = str(academy.get("id") or "")
        if not key or key in seen or not academy.get("name"):
            continue
        seen.add(key)
        if academy.get("is_excluded") or academy.get("ranking_eligible") is False \
                or config.is_homeschool_franchise(academy) or config.is_vocational(academy):
            continue
        previous = memory["academies"].get(key, {})
        unchanged = previous.get("query_fingerprint") == _fingerprint(academy)
        if unchanged and previous.get("cooldown_until") and _now(previous["cooldown_until"]) > instant:
            continue
        reasons = []
        score = academy.get("score") or {}
        sample = academy.get("sample_size", score.get("sampleSize", 0)) or 0
        priority = 0.0
        if sample == 0:
            priority += 100
            reasons.append("no_review_evidence")
        elif sample < config.MIN_SAMPLE_FOR_RANK:
            priority += 60
            reasons.append("thin_review_evidence")
        last = previous.get("last_attempt") or academy.get("last_collected_at")
        age = max(0, (instant - _now(last)).days) if last else RETENTION_DAYS
        priority += min(age, RETENTION_DAYS) / 6
        if not last:
            reasons.append("never_collected_by_agents")
        elif age >= REFRESH_DAYS:
            reasons.append("collection_due")
        publication = academy.get("latest_evidence_at") or academy.get("latest_review_at")
        if publication:
            try:
                if (instant - _now(publication)).days >= 90:
                    priority += 25
                    reasons.append("old_publication_evidence")
            except (ValueError, TypeError):
                reasons.append("unknown_publication_date")
        else:
            reasons.append("unknown_publication_date")
        if key in case_targets:
            priority += 20
            reasons.append("unresolved_case_for_review")
        subjects = academy.get("subjects") or ["unknown"]
        cohort = f"{academy.get('region_id') or 'unknown'}:{sorted(subjects)[0]}"
        cohorts[cohort].append((priority, key, academy, reasons))
    queues = {key: deque(sorted(rows, key=lambda row: (-row[0], row[1])))
              for key, rows in cohorts.items()}
    served_regions = Counter()
    served_cohorts = Counter()
    result = []
    while queues and len(result) < limit:
        # Rotate regions before subjects: with a small budget, lexically sorted
        # region:subject cohorts can otherwise spend every slot in one region.
        # Within equally served regions/cohorts, evidence need still decides.
        region_cohorts = defaultdict(list)
        for cohort in queues:
            region_cohorts[cohort.partition(":")[0]].append(cohort)
        least_served = min(served_regions[region] for region in region_cohorts)
        candidates = []
        for region, available in region_cohorts.items():
            if served_regions[region] != least_served:
                continue
            cohort = min(available, key=lambda c: (
                served_cohorts[c], -queues[c][0][0], c))
            candidates.append((region, cohort))
        region, cohort = min(candidates, key=lambda pair: (
            -queues[pair[1]][0][0], pair[0], pair[1]))
        served_regions[region] += 1
        served_cohorts[cohort] += 1
        priority, key, academy, reasons = queues[cohort].popleft()
        if not queues[cohort]:
            del queues[cohort]
        untried = [arm for arm in ARMS
                   if memory["arms"].get(arm, {}).get("attempts", 0) + planned_arms[arm] == 0]
        arm = untried[0] if untried else max(ARMS, key=lambda a: (
            arm_values[a][0] - planned_arms[a] * 0.05, -ARMS.index(a)))
        planned_arms[arm] += 1
        query, source = _query(academy, arm, regions, instant)
        last_attempt = memory["academies"].get(key, {}).get("last_attempt", "never")
        task_id = hashlib.sha256(
            f"{instant.date()}|{key}|{last_attempt}|{arm}|{query}".encode()).hexdigest()[:24]
        result.append({"task_id": task_id, "academy_id": key,
                       "academy_name": academy["name"], "region_id": academy.get("region_id"),
                       "query_fingerprint": _fingerprint(academy), "cohort": cohort,
                       "arm": arm, "query": query, "source": source,
                       "priority": round(priority, 3), "reasons": reasons,
                       "lessons": [lesson["id"] for lesson in observation["lessons"]],
                       "strategy_trace": arm_values[arm][1], "role": "planner"})
    return result


def record_outcome(memory: dict, task: dict, *, collected: int, accepted: int,
                   duplicates: int = 0, unknown_dates: int = 0,
                   rejections: dict | None = None, error: str | None = None, now=None) -> dict:
    """Learn once from an actual attempt whose new results passed existing gates.

`collected` includes duplicate results; `accepted` counts only new unique accepted
URLs, and `unknown_dates` only those among accepted. Failed transport attempts
are recorded with accepted=0 and cool down even if no result was returned.
"""
    _validate(memory)
    arm, key, task_id = task.get("arm"), str(task.get("academy_id") or ""), task.get("task_id")
    if arm not in ARMS or not key or not task_id:
        raise ValueError("outcome requires a planned arm, academy_id and task_id")
    for row in memory["history"]:
        if row["task_id"] == task_id:
            return dict(row, already_recorded=True)
    counts = {"collected": collected, "accepted": accepted, "duplicates": duplicates,
              "unknown_dates": unknown_dates}
    for field, value in counts.items():
        _count(value, field)
    if accepted + duplicates > collected or unknown_dates > accepted or (error and accepted):
        raise ValueError("inconsistent verified outcome counts")
    rejections = dict(rejections or {})
    if len(rejections) > 32 or any(not isinstance(key, str) or len(key) > 100 for key in rejections):
        raise ValueError("too many or invalid rejection categories")
    for value in rejections.values():
        _count(value, "rejections")
    if sum(rejections.values()) > collected - duplicates - accepted:
        raise ValueError("rejections exceed rejected unique results")
    instant = _now(now)
    updated = copy.deepcopy(memory)
    stats = updated["arms"].setdefault(arm, dict.fromkeys(COUNTERS, 0))
    stats["attempts"] = stats.get("attempts", 0) + 1
    stats["failures"] = stats.get("failures", 0) + int(bool(error))
    for field, value in counts.items():
        stats[field] = stats.get(field, 0) + value
    rejection_counts = Counter(stats.get("rejections", {}))
    rejection_counts.update(rejections)
    stats["rejections"] = dict(rejection_counts.most_common(32))
    previous = updated["academies"].get(key, {})
    streak = previous.get("failure_streak", 0) + 1 if error else 0
    cooldown = timedelta(hours=min(168, 2 ** min(streak - 1, 8))) if error \
        else timedelta(days=REFRESH_DAYS if accepted else 1)
    updated["academies"][key] = {"last_attempt": _iso(instant),
        "cooldown_until": _iso(instant + cooldown), "failure_streak": streak,
        "query_fingerprint": task.get("query_fingerprint"),
        "last_arm": arm, "last_accepted": accepted, "last_collected": collected}
    trace = {"task_id": task_id, "academy_id": key, "arm": arm, "at": _iso(instant),
             "query": str(task.get("query") or "")[:512], **counts,
             "rejections": rejections, "error": str(error)[:512] if error else None,
             "gate_yield": round(accepted / collected, 4) if collected else None,
             "measurement": "verified gate yield; not factual accuracy",
             "role": "reflection", "lessons": task.get("lessons", [])}
    updated["history"].append(trace)
    updated["outcomes"] += 1
    updated = _bounded(updated, instant)
    _validate(updated)
    memory.clear()
    memory.update(updated)
    return trace
