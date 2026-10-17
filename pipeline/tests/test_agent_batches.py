"""Local public observations survive production cache turnover without new labels."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import agent_batches, agent_cycle, config, ego_reviews, mention_store, ranking_agents


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "export")
    monkeypatch.setattr(mention_store, "PATH", config.CACHE_DIR / "mentions.json.gz")
    monkeypatch.setattr(ranking_agents, "verify_history", lambda: {"ok": True})
    return tmp_path


def _attempt(aid="100", number="123", seed="task"):
    task = {"task_id": hashlib.sha256(seed.encode()).hexdigest()[:24], "academy_id": aid,
            "academy_name": "다라학원", "region_id": "daechi", "arm": "blog_local",
            "source": "naver_blog", "query": "대치 다라학원 후기", "query_fingerprint": "a" * 16}
    row = ego_reviews.normalize_item({"url": f"https://blog.naver.com/parent/{number}",
                                     "title": "다라학원 후기", "snippet": "다라학원에 다니고 있어요"},
                                    academy_id=aid, academy_name=task["academy_name"],
                                    query=task["query"], region_id=task["region_id"])
    row["collected_at"] = "2026-01-10T00:00:00+00:00"
    return {"task": task, "rows": [row], "collected_at": "2026-01-10T00:00:01+00:00"}


def _pending(attempt):
    tid = attempt["task"]["task_id"]
    agent_cycle._write(agent_cycle.state_dir() / "pending.json", {
        tid: dict(copy.deepcopy(attempt), state="pending", duplicates=[])
    })
    return tid


def _manifest(attempt):
    payload = {"version": 1, "attempts": [attempt]}
    path = agent_batches.batch_dir() / f"{agent_batches._digest(payload)}.json"
    agent_cycle._write(path, payload)
    return path


def _fresh_server_cache():
    if config.CACHE_DIR.exists():
        shutil.rmtree(config.CACHE_DIR)


def test_export_is_immutable_idempotent_and_strips_decisions_and_secrets(sandbox):
    attempt = _attempt()
    attempt["task"]["api_key"] = "secret-value"
    attempt["rows"][0]["accepted"] = True
    attempt["rows"][0]["token"] = "secret-value"
    _pending(attempt)
    first = agent_batches.export_pending()
    second = agent_batches.export_pending()
    assert first == second and first["attempts"] == first["rows"] == 1
    content = Path(first["path"]).read_text()
    assert "secret-value" not in content and '"accepted"' not in content
    assert len(list(agent_batches.batch_dir().glob("*.json"))) == 1
    assert not agent_cycle.memory_path().exists()


def test_legacy_web_task_exports_its_actual_blog_acquisition(sandbox):
    attempt = _attempt()
    attempt["task"]["source"] = "web"
    _pending(attempt)
    exported = agent_batches.export_pending()
    payload = json.loads(Path(exported["path"]).read_text())
    assert payload["attempts"][0]["task"]["source"] == "naver_blog"


def test_import_requires_production_gates_then_replays_without_relearning(sandbox):
    attempt = _attempt()
    tid = _pending(attempt)
    agent_batches.export_pending()
    _fresh_server_cache()
    imported = agent_batches.import_batches([{"id": "100"}])
    assert imported["attempts"] == imported["rows"] == imported["pending"] == 1
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 0
    assert mention_store.rows()[0]["first_seen"] == "2026-01-10"
    assert agent_cycle._pending()[tid]["state"] == "pending"
    # This stands in for the completed production gate output; import itself
    # must never manufacture an accepted count.
    agent_cycle.finalize([dict(attempt["rows"][0], is_excluded=True, exclude_reason="promotional")], [{"id": "100"}])
    assert ranking_agents.load_memory(agent_cycle.memory_path())["history"][-1]["accepted"] == 0
    assert (sandbox / "export" / "review_agents.json").exists()
    again = agent_batches.import_batches([{"id": "100"}])
    assert again["attempts"] == again["rows"] == again["pending"] == 0
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 1


def test_missing_raw_cache_restores_original_acquisition_without_retraining(sandbox):
    attempt = _attempt()
    _manifest(attempt)
    agent_batches.import_batches([{"id": "100"}])
    agent_cycle.finalize(attempt["rows"], [{"id": "100"}])
    mention_store.PATH.unlink()
    restored = agent_batches.import_batches([{"id": "100"}])
    assert restored["rows"] == restored["restored"] == 1
    assert restored["attempts"] == restored["pending"] == 0
    assert mention_store.rows()[0]["first_seen"] == mention_store.rows()[0]["last_seen"] == "2026-01-10"
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 1


def test_missing_registry_defers_then_current_alias_mapping_avoids_false_reward(sandbox):
    attempt = _attempt(aid="OLD")
    _manifest(attempt)
    deferred = agent_batches.import_batches()
    assert deferred["deferred"][0]["academy_id"] == "OLD"
    assert not mention_store.exists()
    existing = dict(attempt["rows"][0], source_url="https://m.blog.naver.com/parent/123?ref=x", url_hash="legacy")
    mention_store.merge([existing], today="2026-02-01", quiet=True)
    current = [{"id": "NEW", "registration_ids": ["OLD", "NEW"]}]
    report = agent_batches.import_batches(current)
    receipt = agent_cycle._pending()[attempt["task"]["task_id"]]
    assert report["attempts"] == 1 and not report["deferred"]
    assert receipt["task"]["academy_id"] == receipt["rows"][0]["academy_key"] == "NEW"
    assert len(receipt["duplicates"]) == 1
    agent_cycle.finalize([dict(existing, academy_key="NEW")], current)
    outcome = ranking_agents.load_memory(agent_cycle.memory_path())["history"][-1]
    assert outcome["accepted"] == 0 and outcome["duplicates"] == 1


def test_warm_import_does_not_refresh_existing_last_seen(sandbox):
    attempt = _attempt()
    _manifest(attempt)
    mention_store.merge(attempt["rows"], today="2026-03-01", quiet=True)
    agent_batches.import_batches([{"id": "100"}])
    assert mention_store.rows()[0]["last_seen"] == "2026-03-01"
    agent_batches.import_batches([{"id": "100"}])
    assert mention_store.rows()[0]["last_seen"] == "2026-03-01"


@pytest.mark.parametrize("change", [
    lambda a: a["rows"][0].update(source_url="https://example.com/post/123"),
    lambda a: a["rows"][0].update(url_hash="forged"),
    lambda a: a["rows"][0].update(accepted=True),
    lambda a: a["rows"][0].update(author_hash="invented-author"),
    lambda a: a["rows"][0].update(academy_key="someone-else"),
    lambda a: a["rows"][0].update(snippet="x" * 601),
    lambda a: a["rows"][0].update(search_url="https://search.naver.com/?token=secret"),
    lambda a: a.update(rows=a["rows"] * 21),
])
def test_invalid_raw_transport_fails_before_store_mutation(sandbox, change):
    attempt = _attempt()
    change(attempt)
    _manifest(attempt)
    with pytest.raises(ValueError):
        agent_batches.import_batches([{"id": "100"}])
    assert not mention_store.exists() and not agent_cycle.memory_path().exists()


def test_tampered_immutable_manifest_is_not_imported(sandbox):
    path = _manifest(_attempt())
    payload = json.loads(path.read_text())
    payload["attempts"][0]["rows"][0]["snippet"] += " 변조"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="hash mismatch"):
        agent_batches.import_batches([{"id": "100"}])
    assert not mention_store.exists()


def test_crash_after_journal_recovers_original_baseline_without_browser(sandbox, monkeypatch):
    attempt = _attempt()
    _manifest(attempt)
    real_merge = mention_store._merge_unlocked
    def interrupted(*args, **kwargs):
        raise OSError("interrupted import")
    monkeypatch.setattr(mention_store, "_merge_unlocked", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        agent_batches.import_batches([{"id": "100"}])
    receipt = agent_cycle._pending()[attempt["task"]["task_id"]]
    assert receipt["state"] == "staged" and not receipt["duplicates"]
    monkeypatch.setattr(mention_store, "_merge_unlocked", real_merge)
    recovered = agent_batches.import_batches([{"id": "100"}])
    assert recovered["rows"] == 1
    receipt = agent_cycle._pending()[attempt["task"]["task_id"]]
    assert receipt["state"] == "pending" and not receipt["duplicates"]
    assert mention_store.rows()[0]["first_seen"] == "2026-01-10"


def test_old_completed_task_does_not_retrain_after_history_is_trimmed(sandbox):
    attempt = _attempt()
    _manifest(attempt)
    agent_batches.import_batches([{"id": "100"}])
    agent_cycle.finalize(attempt["rows"], [{"id": "100"}])
    memory = ranking_agents.load_memory(agent_cycle.memory_path())
    memory["history"] = []
    ranking_agents.save_memory(agent_cycle.memory_path(), memory)
    assert agent_batches.import_batches([{"id": "100"}])["pending"] == 0
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 1


def test_crash_after_raw_commit_keeps_original_novelty_baseline(sandbox, monkeypatch):
    attempt = _attempt()
    tid = attempt["task"]["task_id"]
    _manifest(attempt)
    real_write = agent_cycle._write
    def interrupted(path, data):
        if path.name == "pending.json" and data[tid]["state"] == "pending":
            raise OSError("interrupted after raw commit")
        real_write(path, data)
    monkeypatch.setattr(agent_cycle, "_write", interrupted)
    with pytest.raises(OSError, match="after raw commit"):
        agent_batches.import_batches([{"id": "100"}])
    assert mention_store.rows() and agent_cycle._pending()[tid]["state"] == "staged"
    monkeypatch.setattr(agent_cycle, "_write", real_write)
    assert agent_batches.import_batches([{"id": "100"}])["rows"] == 0
    assert agent_cycle._pending()[tid]["duplicates"] == []
    agent_cycle.finalize(attempt["rows"], [{"id": "100"}])
    assert ranking_agents.load_memory(agent_cycle.memory_path())["history"][-1]["accepted"] == 1
