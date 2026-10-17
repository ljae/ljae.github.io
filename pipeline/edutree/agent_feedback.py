"""Portable production feedback for the next local Ego collection plan.

The committed document contains counters and operational task traces only, not
review excerpts, authors, credentials, scoring weights, or generated labels.
Production is the baseline; still-retained local trials absent from that
baseline are replayed once. Cache provenance prevents a repeated/stale snapshot
from rolling back local learning after its short trace history has been pruned.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

from . import config, ranking_agents

VERSION = 1
# The committed archive holds at most 2400 tasks. Keep a larger completion
# index across time so restoring an empty CI cache cannot retrain old batches.
MAX_COMPLETED = 4096
MAX_BYTES = 8 * 1024 * 1024
_MEMORY_KEYS = {"version", "arms", "academies", "history", "outcomes"}
_HISTORY_KEYS = {"task_id", "academy_id", "arm", "at", "query", "collected", "accepted",
                 "duplicates", "unknown_dates", "rejections", "error", "gate_yield",
                 "measurement", "role", "lessons"}
_ACADEMY_KEYS = {"last_attempt", "cooldown_until", "failure_streak", "query_fingerprint",
                 "last_arm", "last_accepted", "last_collected"}


def feedback_path() -> Path:
    return config.DATA_DIR / "ranking_agent_feedback.json"


def _text(value, field: str, maximum: int = 128, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"invalid feedback {field}")


def _completed(value) -> None:
    if not isinstance(value, dict) or len(value) > MAX_COMPLETED:
        raise ValueError("invalid feedback completion ledger")
    for task_id, at in value.items():
        _text(task_id, "task_id")
        _text(at, "completed at", 40)
        ranking_agents._now(at)


def validate_provenance(value: dict) -> None:
    """Called by ranking_agents for its optional local-only provenance field."""
    if not isinstance(value, dict) or set(value) != {
            "snapshot_sha256", "remote_outcomes", "remote_completed"}:
        raise ValueError("invalid feedback provenance fields")
    digest = value["snapshot_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 \
            or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid feedback snapshot hash")
    ranking_agents._count(value["remote_outcomes"], "remote_outcomes")
    _completed(value["remote_completed"])


def _validate_memory(memory: dict) -> None:
    """Reject arbitrary extra data even inside otherwise valid learner state."""
    ranking_agents._validate(memory)
    if set(memory) - (_MEMORY_KEYS | {"feedback"}):
        raise ValueError("invalid feedback memory fields")
    if len(memory["academies"]) > ranking_agents.MAX_ACADEMIES \
            or len(memory["history"]) > ranking_agents.MAX_HISTORY:
        raise ValueError("feedback memory exceeds retention limits")
    for stats in memory["arms"].values():
        if set(stats) - (set(ranking_agents.COUNTERS) | {"rejections"}):
            raise ValueError("unexpected feedback arm fields")
        if len(stats.get("rejections", {})) > 32:
            raise ValueError("too many feedback rejection categories")
        for reason in stats.get("rejections", {}):
            _text(reason, "rejection category", 100)
    for academy_id, stats in memory["academies"].items():
        _text(academy_id, "academy_id")
        if set(stats) - _ACADEMY_KEYS:
            raise ValueError("unexpected feedback academy fields")
        if stats.get("last_arm") not in ranking_agents.ARMS:
            raise ValueError("invalid feedback academy arm")
        _text(stats.get("query_fingerprint"), "query fingerprint", 128, nullable=True)
        for field in ("last_accepted", "last_collected"):
            ranking_agents._count(stats.get(field, 0), field)
        if stats.get("last_accepted", 0) > stats.get("last_collected", 0):
            raise ValueError("invalid feedback academy counts")
    seen = set()
    for row in memory["history"]:
        if set(row) != _HISTORY_KEYS:
            raise ValueError("unexpected feedback trace fields")
        _text(row["task_id"], "task_id")
        _text(row["academy_id"], "academy_id")
        if row["task_id"] in seen or row["arm"] not in ranking_agents.ARMS:
            raise ValueError("duplicate task or invalid feedback trace arm")
        seen.add(row["task_id"])
        if not isinstance(row["query"], str) or len(row["query"]) > 512:
            raise ValueError("invalid feedback query")
        _text(row["error"], "error", 512, nullable=True)
        if row["measurement"] != "verified gate yield; not factual accuracy" \
                or row["role"] != "reflection":
            raise ValueError("invalid feedback measurement")
        allowed_lessons = {lesson["id"] for lesson in ranking_agents.LESSONS}
        if not isinstance(row["lessons"], list) or len(row["lessons"]) > len(allowed_lessons) \
                or any(lesson not in allowed_lessons for lesson in row["lessons"]):
            raise ValueError("invalid feedback lesson references")
        for field in ("collected", "accepted", "duplicates", "unknown_dates"):
            ranking_agents._count(row[field], field)
        if row["accepted"] + row["duplicates"] > row["collected"] \
                or row["unknown_dates"] > row["accepted"] or (row["error"] and row["accepted"]):
            raise ValueError("inconsistent feedback outcome counts")
        if not isinstance(row["rejections"], dict) or len(row["rejections"]) > 32:
            raise ValueError("invalid feedback rejections")
        for reason, count in row["rejections"].items():
            _text(reason, "rejection category", 100)
            ranking_agents._count(count, "rejections")
        if sum(row["rejections"].values()) > row["collected"] - row["accepted"] - row["duplicates"]:
            raise ValueError("feedback rejections exceed available results")
        value = row["gate_yield"]
        expected = round(row["accepted"] / row["collected"], 4) if row["collected"] else None
        if value != expected or (value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value))):
            raise ValueError("invalid feedback gate yield")


def _validate_feedback(feedback: dict) -> None:
    if not isinstance(feedback, dict) or set(feedback) != {
            "version", "exported_at", "memory", "completed_tasks"} or feedback["version"] != VERSION:
        raise ValueError("unsupported feedback schema")
    _text(feedback["exported_at"], "exported_at", 40)
    ranking_agents._now(feedback["exported_at"])
    memory = feedback["memory"]
    if not isinstance(memory, dict) or set(memory) != _MEMORY_KEYS:
        raise ValueError("portable feedback must not contain cache provenance")
    _validate_memory(memory)
    _completed(feedback["completed_tasks"])
    if any(feedback["completed_tasks"].get(row["task_id"]) != row["at"]
           for row in memory["history"]):
        raise ValueError("feedback completion ledger is missing observed tasks")


def _digest(feedback: dict) -> str:
    payload = json.dumps(feedback, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_feedback(path: Path | str | None = None) -> dict | None:
    path = Path(path) if path is not None else feedback_path()
    if not path.exists():
        return None
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("feedback document is too large")
    result = json.loads(path.read_text(encoding="utf-8"))
    _validate_feedback(result)
    return result


def completed_task_ids(feedback: dict | None = None) -> set[str]:
    feedback = load_feedback() if feedback is None else feedback
    if feedback is None:
        return set()
    _validate_feedback(feedback)
    return set(feedback["completed_tasks"])


def export_feedback(memory: dict, path: Path | str | None = None, now=None) -> dict:
    """Atomically export bounded production observations; no local provenance."""
    _validate_memory(memory)
    instant = ranking_agents._now(now)
    path = Path(path) if path is not None else feedback_path()
    previous = load_feedback(path)
    if previous and ranking_agents._now(previous["exported_at"]) > instant:
        raise ValueError("refusing to overwrite newer production feedback")
    snapshot = ranking_agents._bounded(memory, instant)
    provenance = snapshot.pop("feedback", {})
    completed = dict((previous or {}).get("completed_tasks", {}))
    completed.update(provenance.get("remote_completed", {}))
    completed.update({row["task_id"]: row["at"] for row in snapshot["history"]})
    completed = dict(sorted(completed.items(), key=lambda item: (item[1], item[0]))[-MAX_COMPLETED:])
    # Only the fact of transport failure is needed by the learner. Do not ship
    # arbitrary exception text which might contain a URL payload or credentials.
    for row in snapshot["history"]:
        if row["error"]:
            row["error"] = "collection_failed"
    result = {"version": VERSION, "exported_at": ranking_agents._iso(instant),
              "memory": snapshot, "completed_tasks": completed}
    _validate_feedback(result)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("feedback document is too large")
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
    return result


def merge_memory(local_memory: dict, feedback: dict | None = None, now=None) -> dict:
    """Return remote baseline plus retained unseen local trials without I/O writes.

    The same or older remote epoch keeps local aggregate counts intact, even
    after its copied remote trace has aged out. A newer remote epoch replaces
    the baseline and replays only retained local observations absent from both
    completion ledgers. This deliberately bounds learning to retained trials.
    """
    _validate_memory(local_memory)
    feedback = load_feedback() if feedback is None else feedback
    if feedback is None:
        return copy.deepcopy(local_memory)
    _validate_feedback(feedback)
    digest = _digest(feedback)
    previous = local_memory.get("feedback", {})
    remote = feedback["memory"]
    if previous and (previous["snapshot_sha256"] == digest
                     or remote["outcomes"] <= previous["remote_outcomes"]):
        return copy.deepcopy(local_memory)
    completed = set(feedback["completed_tasks"]) | set(previous.get("remote_completed", {}))
    result = copy.deepcopy(remote)
    for row in sorted(local_memory["history"], key=lambda r: (r["at"], r["task_id"])):
        if row["task_id"] in completed:
            continue
        local_academy = local_memory["academies"].get(row["academy_id"], {})
        task = {key: row[key] for key in ("task_id", "academy_id", "arm", "query", "lessons")}
        task["query_fingerprint"] = local_academy.get("query_fingerprint")
        prior_academy = copy.deepcopy(result["academies"].get(row["academy_id"]))
        ranking_agents.record_outcome(result, task, collected=row["collected"],
            accepted=row["accepted"], duplicates=row["duplicates"], unknown_dates=row["unknown_dates"],
            rejections=row["rejections"], error=row["error"], now=row["at"])
        # Replaying a delayed local failure must not move a newer production
        # refresh backwards or weaken its cooldown.
        if prior_academy and ranking_agents._now(prior_academy["last_attempt"]) > ranking_agents._now(row["at"]):
            result["academies"][row["academy_id"]] = prior_academy
        elif local_academy.get("last_attempt") == row["at"]:
            result["academies"][row["academy_id"]] = copy.deepcopy(local_academy)
    result["feedback"] = {"snapshot_sha256": digest, "remote_outcomes": remote["outcomes"],
                          "remote_completed": dict(feedback["completed_tasks"])}
    result = ranking_agents._bounded(result, ranking_agents._now(now))
    _validate_memory(result)
    return result
