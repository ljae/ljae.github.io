"""Browser attempts become learning observations only after production gates."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edutree import agent_cycle, blog, config, mention_store, ranking_agents


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "export")
    from edutree import agent_batches, agent_feedback
    monkeypatch.setattr(agent_batches, "batch_dir", lambda: tmp_path / "batches")
    monkeypatch.setattr(agent_feedback, "feedback_path", lambda: tmp_path / "feedback.json")
    monkeypatch.setattr(mention_store, "PATH", tmp_path / "mentions.json.gz")
    return tmp_path


def task():
    return {"task_id": "trial-1", "academy_id": "A", "academy_name": "다라학원",
            "arm": "blog_local", "query": "대치 다라학원 후기", "source": "naver_blog"}


def row(article="123", **extra):
    return {"source": "naver_blog", "source_url": f"https://blog.naver.com/parent/{article}",
            "url_hash": article, "academy_key": "A", "title": "다라학원 후기",
            "snippet": "다라학원 다녀왔어요", "collector": "ego_lite", **extra}


def test_collect_waits_for_gates_and_cache_replay_learns_only_once(sandbox):
    result = agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {
        "status": "ok", "rows": [row()], "query": kw["query"]})
    assert result["pending"] == 1
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 0
    assert mention_store.rows()[0]["collector"] == "ego_lite"
    first = agent_cycle.finalize([row()], [{"id": "A"}])
    assert first["finalized"] == 1
    memory = ranking_agents.load_memory(agent_cycle.memory_path())
    assert memory["outcomes"] == 1
    assert memory["history"][-1]["accepted"] == 1
    assert agent_cycle.finalize([row()], [{"id": "A"}])["finalized"] == 0


def test_existing_url_variant_is_never_rewarded(sandbox):
    mention_store.merge([row(source_url="https://m.blog.naver.com/parent/123?tracking=x")], quiet=True)
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "ok", "rows": [row()]})
    agent_cycle.finalize([row()], [{"id": "A"}])
    history = ranking_agents.load_memory(agent_cycle.memory_path())["history"]
    assert history[-1]["accepted"] == 0
    assert history[-1]["duplicates"] == 1


def test_absorbed_registration_is_not_a_new_document(sandbox):
    mention_store.merge([row(academy_key="OLD")], quiet=True)
    agent_cycle.collect_tasks([dict(task(), registration_ids=["OLD", "A"])], 10,
                             collector=lambda **kw: {"status": "ok", "rows": [row()]})
    agent_cycle.finalize([row()], [{"id": "A", "registration_ids": ["OLD", "A"]}])
    history = ranking_agents.load_memory(agent_cycle.memory_path())["history"]
    assert history[-1]["accepted"] == 0
    assert history[-1]["duplicates"] == 1


def test_interrupted_journal_is_recovered_before_build_reads_store(sandbox):
    agent_cycle._write(agent_cycle.state_dir() / "pending.json", {"trial-1": {
        "state": "staged", "task": task(), "rows": [row()], "duplicates": []}})
    assert agent_cycle.pending_snapshot() == {"trial-1"}
    assert mention_store.rows()[0]["source_url"] == row()["source_url"]
    assert agent_cycle._pending()["trial-1"]["state"] == "pending"


def test_rejected_and_reassigned_rows_do_not_reward_query(sandbox):
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {
        "status": "ok", "rows": [row("1"), row("2"), row("3")]})
    agent_cycle.finalize([row("1", is_excluded=True, exclude_reason="ad"),
                          row("2", academy_key="B")], [{"id": "A"}, {"id": "B"}])
    memory = ranking_agents.load_memory(agent_cycle.memory_path())
    assert memory["history"][-1]["accepted"] == 0


def test_browser_failure_stops_batch_and_does_not_create_empty_trial(sandbox):
    calls = []
    def failed(**kw):
        calls.append(kw)
        return {"status": "user_control", "rows": []}
    result = agent_cycle.collect_tasks([task(), dict(task(), task_id="next")], 10, collector=failed)
    assert len(calls) == 1
    assert result["pending"] == 0
    assert not mention_store.exists()
    memory = ranking_agents.load_memory(agent_cycle.memory_path())
    assert memory["history"][-1]["error"] == "user_control"


def test_incomplete_scoring_keeps_pending(sandbox):
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "ok", "rows": [row()]})
    assert agent_cycle.finalize([], [{"id": "B"}])["pending"] == 1


def test_new_collection_during_build_is_not_mislearned_as_rejection(sandbox):
    snapshot = agent_cycle.pending_snapshot()
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "ok", "rows": [row()]})
    assert agent_cycle.finalize([], [{"id": "A"}], receipt_ids=snapshot)["pending"] == 1
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 0


def test_empty_search_settles_without_scoring_an_unselected_academy(sandbox):
    report = agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "empty", "rows": []})
    assert report["pending"] == 0
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 1


def test_regression_failure_keeps_previous_policy(sandbox, monkeypatch):
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "ok", "rows": [row()]})
    monkeypatch.setattr(ranking_agents, "verify_history", lambda: {"ok": False})
    assert agent_cycle.finalize([row()], [{"id": "A"}])["blocked"] == "regression_failed"
    assert ranking_agents.load_memory(agent_cycle.memory_path())["outcomes"] == 0


def test_missing_cache_never_collects_or_synthesizes(sandbox, monkeypatch):
    from edutree import build, naver
    monkeypatch.setattr(config, "HAS_NAVER", True)
    monkeypatch.setattr(naver, "collect_all", lambda *args: pytest.fail("live fetch"))
    assert build.load_mentions([{"id": "A"}], "live", from_cache=True) == []


def test_browser_rows_never_fetch_or_inherit_body(sandbox, monkeypatch):
    (sandbox / "blog_texts.json").write_text(json.dumps({row()["source_url"]: {
        "text": "원문 본문", "length": 100, "posted_at": "2026-01-01"}}))
    monkeypatch.setattr(blog, "fetch_post", lambda _: pytest.fail("body fetch"))
    rows = [row(), row("456")]
    assert blog.enrich(rows) == 0
    assert rows[0]["snippet"] == "다라학원 다녀왔어요"


def test_plan_requires_real_cached_registry(sandbox, monkeypatch):
    from edutree import build
    monkeypatch.setattr(build, "load_academies", lambda **kw: pytest.fail("network/demo fallback"))
    with pytest.raises(ValueError, match="NEIS"):
        agent_cycle.cached_academies()


@pytest.mark.parametrize("export_fails", [False, True])
def test_production_build_gates_and_scores_before_learning(sandbox, monkeypatch, export_fails):
    """Exercise the real orchestration/gates/scoring; isolate external effects."""
    import requests
    from edutree import (build, claims, claim_llm, coverage, discovery, directory,
                         official, posts, profiles, wiki)
    monkeypatch.setattr(config, "HAS_SUPABASE", False)
    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *a, **kw: pytest.fail("unexpected network"))
    monkeypatch.setattr(discovery, "STORE", sandbox / "first_seen.json")
    monkeypatch.setattr(coverage, "PATH", sandbox / "collect_history.json")
    monkeypatch.setattr(wiki, "load", lambda: {})
    monkeypatch.setattr(posts, "load", lambda: {})
    monkeypatch.setattr(claims, "load_verdicts", lambda: {})
    monkeypatch.setattr(claims, "load_disputes", lambda: [])
    monkeypatch.setattr(claim_llm, "collect", lambda *a, **kw: [])
    monkeypatch.setattr(directory, "collect", lambda *a, **kw: {})
    monkeypatch.setattr(profiles, "collect", lambda *a, **kw: {})
    monkeypatch.setattr(official, "lookup_contacts", lambda *a, **kw:
                        dict.fromkeys(["asked", "homepage", "tel", "category", "cached"], 0))
    monkeypatch.setattr(posts, "update", lambda *a, **kw:
                        dict.fromkeys(["posts", "created", "updated"], 0))
    monkeypatch.setattr(wiki, "update", lambda *a, **kw: {"created": 0, "updated": 0})
    academy = build._expand_seed()[0]
    academy["id"] = "A"
    rows = [row("1", title=academy["name"] + " 수강 후기",
                snippet="대치 소마사고력수학 우리 아이 다니고 있어요. 수학 선생님이 꼼꼼하게 봐주셔서 만족합니다.",
                author_hash="parent", posted_at="2026-09-01"),
            row("2", title="여행 후기", snippet="다른 지역 여행 이야기입니다.")]
    monkeypatch.setattr(build, "load_academies", lambda **kw: ([academy], "live"))
    monkeypatch.setattr(build, "select_for_mentions", lambda *a, **kw: ([academy], []))
    exported = []
    def export(academies, registry, mentions, scores, *args, **kw):
        assert {m["url_hash"] for m in mentions if not m.get("is_excluded")} == {"1"}
        assert scores["A"]["sample_size"] == 1
        assert scores["A"]["is_ranked"] is False
        if export_fails:
            raise RuntimeError("export failed")
        exported.append(scores)
    monkeypatch.setattr(build, "export", export)
    agent_cycle.collect_tasks([task()], 10, collector=lambda **kw: {"status": "ok", "rows": rows})
    if export_fails:
        with pytest.raises(RuntimeError, match="export failed"):
            build.run(from_cache=True, skip_blog_text=True)
        assert len(agent_cycle._pending()) == 1
        assert not agent_cycle.memory_path().exists()
    else:
        build.run(from_cache=True, skip_blog_text=True)
        assert exported
        history = ranking_agents.load_memory(agent_cycle.memory_path())["history"]
        assert history[-1]["accepted"] == 1
        assert history[-1]["rejections"] == {"identity_or_policy_gate": 1}
