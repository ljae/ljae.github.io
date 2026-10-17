"""Production feedback survives git transfer and never trains a task twice."""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import agent_feedback as feedback, ranking_agents as agents

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


@pytest.fixture
def feedback_file(tmp_path, monkeypatch):
    path = tmp_path / "ranking_agent_feedback.json"
    monkeypatch.setattr(feedback, "feedback_path", lambda: path)
    return path


def empty(tmp_path):
    return agents.load_memory(tmp_path / "missing.json")


def observe(memory, task_id, *, accepted=2, error=None, at=NOW, academy_id=None):
    task = {"task_id": task_id, "academy_id": academy_id or task_id,
            "arm": "exact_local", "query": '"실제학원" 대치동 후기',
            "query_fingerprint": "known-query", "lessons": ["identity", "dates"]}
    agents.record_outcome(memory, task, collected=0 if error else 4,
                          accepted=0 if error else accepted, error=error, now=at)


def test_four_production_trials_plus_two_local_failures_merge_once(feedback_file, tmp_path):
    production = empty(tmp_path)
    for index in range(4):
        observe(production, f"prod-{index}", at=NOW + timedelta(minutes=index))
    report = feedback.export_feedback(production, now=NOW + timedelta(hours=1))
    local = copy.deepcopy(production)
    observe(local, "local-1", error="timeout", at=NOW + timedelta(minutes=10))
    observe(local, "local-2", error="connection", at=NOW + timedelta(minutes=20))
    merged = feedback.merge_memory(local, report, now=NOW + timedelta(hours=1))
    assert merged["outcomes"] == 6
    assert merged["arms"]["exact_local"]["attempts"] == 6
    assert merged["arms"]["exact_local"]["failures"] == 2
    assert merged["arms"]["exact_local"]["accepted"] == 8
    assert feedback.completed_task_ids() == {f"prod-{index}" for index in range(4)}
    assert feedback.merge_memory(merged, now=NOW + timedelta(hours=2)) == merged
    local_path = tmp_path / "local.json"
    agents.save_memory(local_path, merged, now=NOW + timedelta(hours=2))
    assert feedback.merge_memory(agents.load_memory(local_path)) == merged


def test_new_production_snapshot_absorbs_local_trial_without_double_count(feedback_file, tmp_path):
    production = empty(tmp_path)
    observe(production, "remote")
    first = feedback.export_feedback(production, now=NOW)
    local = feedback.merge_memory(empty(tmp_path), first, now=NOW)
    observe(local, "local-empty", accepted=0, at=NOW + timedelta(minutes=1))
    observe(local, "local-failed", error="timeout", at=NOW + timedelta(minutes=2))
    observe(production, "local-empty", accepted=0, at=NOW + timedelta(minutes=1))
    observe(production, "new-remote", at=NOW + timedelta(minutes=3))
    second = feedback.export_feedback(production, now=NOW + timedelta(minutes=4))
    merged = feedback.merge_memory(local, second, now=NOW + timedelta(minutes=4))
    assert merged["outcomes"] == 4
    assert merged["arms"]["exact_local"]["attempts"] == 4
    assert merged["arms"]["exact_local"]["failures"] == 1
    assert feedback.merge_memory(merged, second) == merged
    assert feedback.merge_memory(merged, first) == merged


def test_same_snapshot_does_not_erase_local_learning_after_history_pruning(
        feedback_file, tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "MAX_HISTORY", 2)
    production = empty(tmp_path)
    observe(production, "remote")
    report = feedback.export_feedback(production, now=NOW)
    local = feedback.merge_memory(empty(tmp_path), report, now=NOW)
    for index in range(5):
        observe(local, f"local-{index}", error="timeout", at=NOW + timedelta(minutes=index + 1))
    assert all(row["task_id"] != "remote" for row in local["history"])
    merged = feedback.merge_memory(local, report, now=NOW + timedelta(hours=1))
    assert merged == local and merged["outcomes"] == 6
    assert merged["arms"]["exact_local"]["failures"] == 5


def test_delayed_local_failure_cannot_replace_newer_production_cooldown(feedback_file, tmp_path):
    production, local = empty(tmp_path), empty(tmp_path)
    observe(production, "prod-new", at=NOW, academy_id="same-academy")
    observe(local, "local-old", error="timeout", at=NOW - timedelta(days=1), academy_id="same-academy")
    report = feedback.export_feedback(production, now=NOW)
    merged = feedback.merge_memory(local, report, now=NOW)
    assert merged["academies"]["same-academy"] == production["academies"]["same-academy"]
    assert merged["outcomes"] == 2


def test_missing_feedback_keeps_local_and_export_removes_provenance_and_error_text(
        feedback_file, tmp_path):
    local = empty(tmp_path)
    observe(local, "failed", error="timeout with private transport details")
    assert feedback.load_feedback() is None
    assert feedback.completed_task_ids() == set()
    assert feedback.merge_memory(local) == local
    first = feedback.export_feedback(local, now=NOW)
    assert first["memory"]["history"][0]["error"] == "collection_failed"
    merged = feedback.merge_memory(local, first, now=NOW)
    exported = feedback.export_feedback(merged, now=NOW)
    assert "feedback" not in exported["memory"]
    assert "private transport" not in feedback_file.read_text()
    assert local["history"][0]["error"] == "timeout with private transport details"


def test_completion_ledger_outlives_short_history_and_stays_bounded(feedback_file, tmp_path, monkeypatch):
    monkeypatch.setattr(agents, "MAX_HISTORY", 1)
    monkeypatch.setattr(feedback, "MAX_COMPLETED", 3)
    production = empty(tmp_path)
    for index in range(5):
        observe(production, f"done-{index}", at=NOW + timedelta(minutes=index))
        feedback.export_feedback(production, now=NOW + timedelta(minutes=index))
    assert feedback.completed_task_ids() == {"done-2", "done-3", "done-4"}
    assert len(feedback.load_feedback()["memory"]["history"]) == 1


def test_durable_completion_ids_outlive_strategy_retention(feedback_file, tmp_path):
    production = empty(tmp_path)
    observe(production, "old-archived-task", at=NOW - timedelta(days=200))
    feedback.export_feedback(production, now=NOW - timedelta(days=200))
    observe(production, "new-task", at=NOW)
    feedback.export_feedback(production, now=NOW)
    assert feedback.completed_task_ids() == {"old-archived-task", "new-task"}
    assert [row["task_id"] for row in feedback.load_feedback()["memory"]["history"]] == ["new-task"]


@pytest.mark.parametrize("change", [
    lambda report: report.update(authors=["not operational"]),
    lambda report: report["memory"]["history"][0].update(excerpt="review text"),
    lambda report: report["memory"]["academies"]["remote"].update(author="name"),
    lambda report: report["memory"]["history"][0].update(accepted=99),
    lambda report: report["completed_tasks"].clear(),
    lambda report: report["memory"].update(feedback={}),
])
def test_feedback_schema_rejects_extra_content_and_inconsistent_counts(
        feedback_file, tmp_path, change):
    production = empty(tmp_path)
    observe(production, "remote")
    report = feedback.export_feedback(production, now=NOW)
    change(report)
    feedback_file.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        feedback.load_feedback()
    with pytest.raises(ValueError):
        feedback.export_feedback(production, now=NOW)
    assert json.loads(feedback_file.read_text()) == report


def test_atomic_export_keeps_previous_document_on_replace_failure(feedback_file, tmp_path, monkeypatch):
    production = empty(tmp_path)
    observe(production, "remote")
    feedback.export_feedback(production, now=NOW)
    before = feedback_file.read_bytes()

    def fail_replace(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        feedback.export_feedback(production, now=NOW)
    assert feedback_file.read_bytes() == before
    assert not list(feedback_file.parent.glob("*.tmp"))


def test_provenance_is_strictly_validated(tmp_path):
    memory = empty(tmp_path)
    memory["feedback"] = {"snapshot_sha256": "x" * 64, "remote_outcomes": 1,
                          "remote_completed": {}}
    with pytest.raises(ValueError, match="snapshot hash"):
        agents._validate(memory)
