"""Immutable public-search batches bridge local Ego Lite and production caches.

Only raw observations cross the boundary. Production recomputes identity,
exclusions and scores; local acceptance decisions are never imported.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from . import config, ego_reviews, mention_store, ranking_agents, review_integrity

VERSION = 1
MAX_BATCHES = 200
MAX_ATTEMPTS = 12
MAX_ROWS = 20
MAX_BYTES = 1_000_000
TASK_FIELDS = {"task_id", "academy_id", "academy_name", "region_id", "query",
               "arm", "source", "query_fingerprint"}
ROW_FIELDS = {"source", "source_url", "url_hash", "author_hash", "title", "snippet",
              "posted_at", "date_source", "collected_at", "collector", "search_url",
              "query", "academy_key", "academy_name", "region_id"}


def batch_dir():
    return config.DATA_DIR / "ego_review_batches"


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _string(value, label, maximum, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum
            or (not empty and not value.strip()) or any(ord(c) < 32 for c in value)):
        raise ValueError(f"invalid batch {label}")
    return value


def _time(value):
    _string(value, "collected_at", 40)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
        raise ValueError("batch collection time must be an observed past instant")
    return parsed


def _validate_attempt(attempt):
    if not isinstance(attempt, dict) or set(attempt) != {"task", "rows", "collected_at"}:
        raise ValueError("invalid batch attempt fields")
    collected = _time(attempt["collected_at"])
    task, rows = attempt["task"], attempt["rows"]
    if not isinstance(task, dict) or set(task) - TASK_FIELDS:
        raise ValueError("unexpected batch task fields")
    if not re.fullmatch(r"[a-f0-9]{24}", str(task.get("task_id") or "")):
        raise ValueError("invalid batch task_id")
    _string(task.get("academy_id"), "academy_id", 40)
    _string(task.get("academy_name"), "academy_name", 200)
    _string(task.get("region_id"), "region_id", 40)
    _string(task.get("query"), "query", 300)
    if task.get("arm") not in ranking_agents.ARMS or task.get("source") not in {"naver_blog", "naver_cafe"}:
        raise ValueError("unsupported batch search strategy or source")
    if task.get("query_fingerprint") is not None and not re.fullmatch(r"[a-f0-9]{16}", task["query_fingerprint"]):
        raise ValueError("invalid batch query fingerprint")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("batch requires 1–20 observations per attempt")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - ROW_FIELDS:
            raise ValueError("unexpected batch raw fields; scores/verdicts are not transportable")
        url = row.get("source_url")
        if not isinstance(url, str) or ego_reviews.canonical_url(url) != url:
            raise ValueError("batch URL must be a canonical public Naver article")
        expected_source = "naver_blog" if url.startswith("https://blog.naver.com/") else "naver_cafe"
        expected_hash = hashlib.sha256(url.encode()).hexdigest()[:32]
        expected_author = hashlib.sha256(url.rsplit("/", 1)[0].encode()).hexdigest()[:32] \
            if expected_source == "naver_blog" else None
        if (row.get("url_hash") != expected_hash or row.get("author_hash") != expected_author
                or row.get("source") != expected_source or row.get("source") != task["source"]
                or row.get("collector") != "ego_lite"):
            raise ValueError("batch source, hash or acquisition provenance mismatch")
        for row_key, task_key in (("academy_key", "academy_id"), ("academy_name", "academy_name"),
                                  ("region_id", "region_id"), ("query", "query")):
            if row.get(row_key) != task[task_key]:
                raise ValueError(f"batch {row_key} does not match its task")
        if row.get("search_url") != ego_reviews._search_url(task["query"], expected_source):
            raise ValueError("batch search URL does not match its query")
        _string(row.get("title"), "title", ego_reviews.MAX_TITLE)
        _string(row.get("snippet"), "snippet", ego_reviews.MAX_SNIPPET, empty=True)
        observed = _time(row.get("collected_at"))
        if observed > collected:
            raise ValueError("batch row cannot be collected after its receipt")
        posted = row.get("posted_at")
        if posted is not None:
            if (not isinstance(posted, str) or len(posted) != 10
                    or date.fromisoformat(posted) > observed.astimezone(ZoneInfo("Asia/Seoul")).date()
                    or row.get("date_source") != "ego_search"):
                raise ValueError("invalid observed publication date")
        elif row.get("date_source") is not None:
            raise ValueError("date provenance requires a publication date")
        doc = review_integrity.canonical_document(url)
        if doc in seen:
            raise ValueError("duplicate observations inside one batch attempt")
        seen.add(doc)


def _validate_batch(payload):
    if (not isinstance(payload, dict) or set(payload) != {"version", "attempts"}
            or payload["version"] != VERSION or isinstance(payload["version"], bool)):
        raise ValueError("unsupported Ego batch schema")
    attempts = payload["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= MAX_ATTEMPTS:
        raise ValueError("batch requires 1–12 attempts")
    ids = set()
    for attempt in attempts:
        _validate_attempt(attempt)
        tid = attempt["task"]["task_id"]
        if tid in ids:
            raise ValueError("duplicate task in Ego batch")
        ids.add(tid)
    if len(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")) > MAX_BYTES:
        raise ValueError("Ego batch exceeds size limit")


def _batches():
    paths = sorted(batch_dir().glob("*.json"))
    if len(paths) > MAX_BATCHES:
        raise ValueError("Ego batch archive exceeds bounded import limit")
    result = []
    tasks = {}
    for path in paths:
        if path.is_symlink() or not re.fullmatch(r"[a-f0-9]{64}\.json", path.name) or path.stat().st_size > MAX_BYTES:
            raise ValueError(f"invalid Ego batch file: {path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_batch(payload)
        if _digest(payload) != path.stem:
            raise ValueError(f"Ego batch content hash mismatch: {path.name}")
        for attempt in payload["attempts"]:
            tid = attempt["task"]["task_id"]
            signature = _digest(attempt)
            if tid in tasks and tasks[tid] != signature:
                raise ValueError(f"conflicting immutable Ego task: {tid}")
            tasks[tid] = signature
        result.append((path.stem, payload))
    return result


def export_pending():
    """Publish a bounded raw snapshot before finalize removes local receipts."""
    from . import agent_cycle
    with agent_cycle._lock():
        receipts = [row for row in agent_cycle._pending().values()
                    if row.get("state") == "pending" and row.get("rows") and not row.get("source_batch")]
        if not receipts:
            return {"batch": None, "path": None, "attempts": 0, "rows": 0}
        if len(receipts) > MAX_ATTEMPTS:
            raise ValueError("bundle supports at most 12 pending attempts; settle existing batches first")
        attempts = [{"task": {k: v for k, v in row["task"].items() if k in TASK_FIELDS},
                     "rows": [{k: v for k, v in item.items() if k in ROW_FIELDS} for item in row["rows"]],
                     "collected_at": row["collected_at"]} for row in receipts]
        for attempt in attempts:
            # Early plans called the exact/year strategy "web", while the
            # collector executed a blog-only tab. Preserve its observed source.
            if attempt["task"].get("source") == "web" and all(
                    row.get("source") == "naver_blog" for row in attempt["rows"]):
                attempt["task"]["source"] = "naver_blog"
        attempts.sort(key=lambda row: row["task"]["task_id"])
        payload = {"version": VERSION, "attempts": attempts}
        _validate_batch(payload)
        existing = _batches()
        known = {a["task"]["task_id"]: _digest(a) for _, batch in existing for a in batch["attempts"]}
        if any(a["task"]["task_id"] in known and known[a["task"]["task_id"]] != _digest(a) for a in attempts):
            raise ValueError("cannot overwrite a previously exported Ego attempt")
        digest = _digest(payload)
        path = batch_dir() / f"{digest}.json"
        if not path.exists():
            if len(existing) >= MAX_BATCHES:
                raise ValueError("Ego batch archive is full")
            agent_cycle._write(path, payload)
        return {"batch": digest, "path": str(path), "attempts": len(attempts),
                "rows": sum(len(a["rows"]) for a in attempts)}


def _ledger(path):
    if not path.exists():
        return {"version": VERSION, "tasks": {}}
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(ledger, dict) or set(ledger) != {"version", "tasks"}
            or ledger["version"] != VERSION or not isinstance(ledger["tasks"], dict)
            or len(ledger["tasks"]) > MAX_BATCHES * MAX_ATTEMPTS
            or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v)
                   for k, v in ledger["tasks"].items())):
        raise ValueError("invalid Ego batch import ledger")
    return ledger


def import_batches(academies=None):
    """Restore raw candidates and stage each actual attempt for learning once.

Completed imports may restore missing raw rows after partial cache loss, without
reopening a trial or refreshing its original acquisition date.
"""
    from . import agent_cycle
    manifests = _batches()
    report = {"batches": len(manifests), "attempts": 0, "rows": 0, "restored": 0,
              "unchanged": 0, "deferred": [], "pending": 0}
    if not manifests:
        return report
    if academies is None:
        registry_path = config.CACHE_DIR / "neis_academies.json"
        academies = agent_cycle.cached_academies() if registry_path.exists() else []
    identities = {str(registration): str(academy["id"]) for academy in academies
                  for registration in [academy["id"], *(academy.get("registration_ids") or [])]}
    with agent_cycle._lock():
        ledger_path = agent_cycle.state_dir() / "batch_imports.json"
        ledger = _ledger(ledger_path)
        pending = agent_cycle._pending()
        from . import agent_feedback
        memory = agent_cycle.load_memory()
        completed = {row["task_id"] for row in memory["history"]} | agent_feedback.completed_task_ids()
        attempts = {}
        for batch, payload in manifests:
            for attempt in payload["attempts"]:
                attempts.setdefault(attempt["task"]["task_id"], (batch, attempt))
        with mention_store._store_lock():
            stored = agent_cycle._store_rows()
            known_documents = {(identities.get(str(r.get("academy_key")), str(r.get("academy_key"))),
                                review_integrity.canonical_document(r.get("source_url") or "")) for r in stored}
            known_rows = {(identities.get(str(r.get("academy_key")), str(r.get("academy_key"))), r.get("url_hash"))
                          for r in stored}
            for tid, (batch, attempt) in sorted(attempts.items(), key=lambda item: (item[1][1]["collected_at"], item[0])):
                signature = _digest(attempt)
                if tid in ledger["tasks"] and ledger["tasks"][tid] != signature:
                    raise ValueError(f"changed imported Ego attempt: {tid}")
                original = attempt["task"]["academy_id"]
                if original not in identities:
                    report["deferred"].append({"task_id": tid, "academy_id": original,
                                                "reason": "unknown_registered_identity"})
                    continue
                aid = identities[original]
                rows = [dict(row, academy_key=aid) for row in attempt["rows"]]
                task = dict(attempt["task"], academy_id=aid)
                acquisition_day = _time(attempt["collected_at"]).date().isoformat()
                is_new = tid not in ledger["tasks"]
                if is_new and tid not in completed:
                    if tid not in pending:
                        if len(pending) >= agent_cycle.MAX_PENDING:
                            report["deferred"].append({"task_id": tid, "academy_id": original,
                                                        "reason": "pending_limit"})
                            continue
                        duplicates = [review_integrity.canonical_document(row["source_url"]) for row in rows
                                      if (aid, review_integrity.canonical_document(row["source_url"])) in known_documents]
                        pending[tid] = {"state": "staged", "task": task, "rows": rows,
                                        "duplicates": duplicates, "collected_at": attempt["collected_at"],
                                        "acquisition_day": acquisition_day, "source_batch": batch}
                        agent_cycle._write(agent_cycle.state_dir() / "pending.json", pending)
                missing = [row for row in rows if (aid, row["url_hash"]) not in known_rows]
                if missing:
                    mention_store._merge_unlocked(missing, today=acquisition_day, quiet=True)
                    report["rows"] += len(missing)
                    report["restored"] += len(missing) if not is_new else 0
                    known_rows.update((aid, row["url_hash"]) for row in missing)
                    known_documents.update((aid, review_integrity.canonical_document(row["source_url"])) for row in missing)
                if tid in pending and pending[tid]["state"] == "staged":
                    pending[tid]["state"] = "pending"
                    agent_cycle._write(agent_cycle.state_dir() / "pending.json", pending)
                ledger["tasks"][tid] = signature
                agent_cycle._write(ledger_path, ledger)
                report["attempts"] += int(is_new and tid not in completed)
                report["unchanged"] += int(not is_new)
        report["pending"] = len(pending)
        return report
