"""Bounded Ego Lite collection → production gates → durable retrieval learning.

Search excerpts are observations, never labels. Pending browser receipts are
settled only by build.run after scoring/export succeeds. Replaying the same
cache without a new receipt cannot train the policy again.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
import json
from pathlib import Path

from . import config, mention_store, ranking_agents, review_integrity

MAX_TASKS = 12
MAX_PENDING = 200


def state_dir():
    return config.CACHE_DIR / "ranking_agents"


def memory_path():
    return state_dir() / "memory.json"


def load_memory():
    """Use landed operational feedback in the next local collection cycle."""
    from . import agent_feedback
    return agent_feedback.merge_memory(ranking_agents.load_memory(memory_path()))


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


@contextmanager
def _lock():
    state_dir().mkdir(parents=True, exist_ok=True)
    with (state_dir() / "cycle.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("다른 랭킹 에이전트 실행이 진행 중입니다") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _pending():
    result = _read(state_dir() / "pending.json", {})
    if not isinstance(result, dict) or len(result) > MAX_PENDING:
        raise ValueError("잘못된 에이전트 수집 영수증: pending.json")
    return result


def pending_snapshot():
    """Freeze the receipts this build can evaluate before it reads raw evidence."""
    if not (state_dir() / "pending.json").exists():
        return set()
    with _lock():
        pending = _pending()
        if any(row["state"] == "staged" for row in pending.values()):
            _store_rows()
            for row in pending.values():
                if row["state"] == "staged":
                    mention_store.merge(row["rows"], today=row.get("acquisition_day"), quiet=True)
                    row["state"] = "pending"
            _write(state_dir() / "pending.json", pending)
        return set(pending)


def _document(row):
    return review_integrity.canonical_document(row.get("source_url") or "")


def _store_rows():
    # The legacy store reader returns {} on corruption. An agent must not
    # silently overwrite a damaged evidence archive with a small new batch.
    if mention_store.PATH.exists():
        with gzip.open(mention_store.PATH, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("version") != mention_store.VERSION or not isinstance(payload.get("rows"), dict):
            raise ValueError("언급 저장소 형식 오류 — 원본을 보존했습니다")
    return mention_store.rows()


def cached_academies():
    from . import build
    path = config.CACHE_DIR / "neis_academies.json"
    rows = _read(path, [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("실제 NEIS 등록부 캐시가 필요합니다. 합성 학원으로 수집하지 않습니다")
    return build._prepare_live(rows)


def latest_quality():
    history = _read(config.EXPORT_DIR / "ranking_quality.json", {})
    return history[max(history)] if history else {}


def make_plan(limit=6, academy_ids=None):
    if not 1 <= limit <= MAX_TASKS:
        raise ValueError(f"회차 예산은 1~{MAX_TASKS}개 질의입니다")
    academies = cached_academies()
    # Registry rows carry identity, not ranking history. Join the current
    # published evidence counts and actual collection ledger before prioritizing.
    previous = {str(a["id"]): a for a in _read(config.EXPORT_DIR / "academies.json", [])}
    from . import coverage
    collected = coverage.load()
    for academy in academies:
        prior = previous.get(str(academy["id"]), {})
        academy["score"] = prior.get("score") or {}
        academy["last_collected_at"] = (collected.get(str(academy["id"])) or {}).get("last_at")
    if academy_ids:
        requested = set(academy_ids)
        academies = [a for a in academies if requested.intersection(
            {str(a["id"]), *map(str, a.get("registration_ids") or [])})]
        found = {str(i) for a in academies for i in [a["id"], *(a.get("registration_ids") or [])]}
        if requested - found:
            raise ValueError(f"등록부에서 찾지 못한 번호: {sorted(requested - found)}")
    from . import agent_feedback
    memory = load_memory()
    completed = agent_feedback.completed_task_ids()
    pending_ids = {r["task"]["academy_id"] for key, r in _pending().items()
                   if key not in completed}
    academies = [a for a in academies if str(a["id"]) not in pending_ids
                 and not config.is_homeschool_franchise(a)]
    from . import wiki
    hints = wiki.load()
    academies = [a for a in academies if not hints.get(a["id"], {}).get("unusable")]
    from . import analyze
    def matchable(academy):
        candidates = analyze.name_candidates(academy) | {
            analyze._norm(alias) for alias in hints.get(academy["id"], {}).get("aliases", [])}
        return bool(candidates - analyze.weak_candidates(candidates))
    academies = [a for a in academies if matchable(a)]
    tasks = ranking_agents.plan(academies, memory, limit=limit, quality=latest_quality())
    registrations = {str(a["id"]): list(map(str, a.get("registration_ids") or [a["id"]]))
                     for a in academies}
    for task in tasks:
        task["registration_ids"] = registrations[task["academy_id"]]
    return tasks


def collect_tasks(tasks, space_id, *, collector=None):
    """Collect at most 12 attempts, preserving receipts across process crashes."""
    from . import ego_reviews
    if not isinstance(space_id, int) or isinstance(space_id, bool) or space_id <= 0:
        raise ValueError("활성 Ego Lite TaskSpace 번호가 필요합니다")
    if len(tasks) > MAX_TASKS:
        raise ValueError("회차 수집 예산 초과")
    collector = collector or ego_reviews.collect
    with _lock():
        from . import agent_feedback
        memory = load_memory()
        pending = _pending()
        completed_remote = agent_feedback.completed_task_ids()
        pending = {key: receipt for key, receipt in pending.items() if key not in completed_remote}
        if len(pending) + len(tasks) > MAX_PENDING:
            raise ValueError("검증 대기 수집이 많습니다. 먼저 --from-cache로 재채점하세요")
        _store_rows()
        # A crash between journal and raw-store commits is resumed without a
        # second browser call and without changing the pre-collection baseline.
        for receipt in pending.values():
            if receipt["state"] == "staged":
                mention_store.merge(receipt["rows"], today=receipt.get("acquisition_day"), quiet=True)
                receipt["state"] = "pending"
        _write(state_dir() / "pending.json", pending)
        aliases = {str(rid): str(task["academy_id"]) for task in tasks
                   for rid in task.get("registration_ids") or []}
        known = {(aliases.get(str(r.get("academy_key")), str(r.get("academy_key"))), _document(r))
                 for r in _store_rows()}
        completed = {h.get("task_id") for h in memory.get("history", [])} | completed_remote
        attempts = []
        stopped = None
        update_available = False
        for task in tasks:
            if task["task_id"] in pending or task["task_id"] in completed:
                continue
            source = task.get("source")
            if source not in {"naver_blog", "naver_cafe"}:
                source = "naver_blog"
            task = dict(task, source=source)
            result = collector(query=task["query"], academy_id=task["academy_id"],
                               academy_name=task.get("academy_name", ""),
                               region_id=task.get("region_id", ""),
                               source=source, space_id=space_id, max_results=20)
            status = result["status"]
            update_available = update_available or result.get("update_available", False)
            attempts.append({"task_id": task["task_id"], "status": status,
                             "count": len(result.get("rows") or [])})
            if status not in {"ok", "empty"}:
                ranking_agents.record_outcome(memory, task, collected=0, accepted=0, error=status)
                ranking_agents.save_memory(memory_path(), memory)
                stopped = status
                # A stopped/unavailable browser is a session condition, not
                # permission to try the next academy or create another space.
                break
            rows = result.get("rows") or []
            if not rows:
                # A genuine empty search has no evidence awaiting a gate. It
                # must not strand an unselected academy in pending forever.
                ranking_agents.record_outcome(memory, task, collected=0, accepted=0)
                ranking_agents.save_memory(memory_path(), memory)
                continue
            seen = set(known)
            duplicate_keys = []
            for row in rows:
                key = (str(row["academy_key"]), _document(row))
                if key in seen:
                    duplicate_keys.append(_document(row))
                seen.add(key)
            receipt = {"state": "staged", "task": task, "rows": rows,
                       "duplicates": duplicate_keys,
                       "collected_at": datetime.now(timezone.utc).isoformat()}
            pending[task["task_id"]] = receipt
            _write(state_dir() / "pending.json", pending)
            if rows:
                mention_store.merge(rows, quiet=True)
            receipt["state"] = "pending"
            known = seen
            _write(state_dir() / "pending.json", pending)
        report = {"attempts": attempts, "pending": len(pending), "stopped": stopped,
                  "ego_update_available": update_available,
                  "note": "수집 후보입니다. 기존 게이트와 재채점 완료 뒤 학습합니다"}
        _write(state_dir() / "collection.json", report)
        return report


def finalize(mentions, academies, *, receipt_ids=None):
    """Called only after a successful production scoring/export transaction.

Only attempted academies evaluated in this run are settled. A rehomed post is
not a reward for the original query's academy. Existing canonical documents
are duplicates even when their original API URL hash differs.
"""
    if not (state_dir() / "pending.json").exists():
        return {"finalized": 0, "pending": 0}
    with _lock():
        pending = _pending()
        if not pending:
            return {"finalized": 0, "pending": 0}
        replay = ranking_agents.verify_history()
        _write(state_dir() / "regression.json", replay)
        if not replay["ok"]:
            # Preserve raw observations and the previous policy for diagnosis.
            return {"finalized": 0, "pending": len(pending), "blocked": "regression_failed"}
        from . import agent_feedback
        memory = load_memory()
        evaluated = {str(a["id"]) for a in academies}
        aliases = {str(rid): str(a["id"]) for a in academies
                   for rid in a.get("registration_ids") or []}
        final_rows = {(str(m.get("academy_key")), _document(m)): m for m in reversed(mentions)}
        completed = {h.get("task_id") for h in memory.get("history", [])} | agent_feedback.completed_task_ids()
        settled = []
        for key, receipt in pending.items():
            if receipt_ids is not None and key not in receipt_ids:
                continue
            if key in completed:
                settled.append(key)
                continue
            task = receipt["task"]
            aid = aliases.get(str(task["academy_id"]), str(task["academy_id"]))
            if receipt["state"] != "pending" or (receipt["rows"] and aid not in evaluated):
                continue
            accepted = unknown_dates = 0
            reasons = Counter()
            duplicates = set(receipt["duplicates"])
            seen = set()
            for row in receipt["rows"]:
                doc = _document(row)
                if doc in duplicates or doc in seen:
                    continue
                seen.add(doc)
                admitted = final_rows.get((aid, doc))
                if admitted and not admitted.get("is_excluded"):
                    accepted += 1
                    from . import scoring
                    unknown_dates += scoring.publication_date(admitted) is None
                else:
                    reasons[(admitted or {}).get("exclude_reason") or "identity_or_policy_gate"] += 1
            ranking_agents.record_outcome(
                memory, task, collected=len(receipt["rows"]), accepted=accepted,
                duplicates=len(receipt["duplicates"]), unknown_dates=unknown_dates,
                rejections=dict(reasons))
            settled.append(key)
        ranking_agents.save_memory(memory_path(), memory)
        for key in settled:
            pending.pop(key)
        _write(state_dir() / "pending.json", pending)
        report = {"finalized": len(settled), "pending": len(pending),
                  "outcomes": memory["outcomes"],
                  "metric": "collection_utility_not_accuracy",
                  "evaluated_at": datetime.now(timezone.utc).isoformat(),
                  "regression": {key: replay[key] for key in
                                 ("total", "passed", "failed", "corpus_sha256", "policy_version")
                                 if key in replay},
                  "totals": {key: sum(arm.get(key, 0) for arm in memory["arms"].values())
                             for key in ("attempts", "collected", "accepted", "duplicates",
                                         "unknown_dates", "failures")}}
        _write(state_dir() / "last_cycle.json", report)
        # Only aggregates are public; candidate excerpts and query receipts are
        # not added to app assets. This verifies the deployed cycle separately
        # from successful code compilation.
        if settled:
            _write(config.EXPORT_DIR / "review_agents.json", report)
            agent_feedback.export_feedback(memory)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "collect", "run", "status", "replay", "bundle", "import"], nargs="?", default="plan")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--academy", action="append", default=[])
    parser.add_argument("--space-id", type=int)
    args = parser.parse_args(argv)
    if args.action == "bundle":
        from . import agent_batches
        output = agent_batches.export_pending()
    elif args.action == "import":
        from . import agent_batches
        output = agent_batches.import_batches()
    elif args.action == "status":
        output = {"memory": load_memory(), "pending": len(_pending()),
                  "last_cycle": _read(state_dir() / "last_cycle.json", {})}
    elif args.action == "replay":
        output = ranking_agents.verify_history()
    elif args.action == "plan":
        output = {"tasks": make_plan(args.limit, args.academy), "quality": latest_quality()}
    else:
        if args.space_id is None:
            parser.error("collect/run에는 --space-id가 필요합니다")
        replay = ranking_agents.verify_history()
        if not replay["ok"]:
            raise RuntimeError("과거 오류 회귀 검증 실패: " + json.dumps(replay, ensure_ascii=False))
        _write(state_dir() / "regression.json", replay)
        output = collect_tasks(make_plan(args.limit, args.academy), args.space_id)
        if args.action == "run" and output["pending"] and not output["stopped"]:
            import os
            from . import build, agent_batches
            output["handoff"] = agent_batches.export_pending()
            os.environ["OPENEDU_CLAIM_LLM_LIMIT"] = "0"
            os.environ["OPENEDU_SUMMARY_PER_RUN"] = "0"
            output["scoring"] = build.run(from_cache=True, skip_blog_text=True)
            output["cycle"] = _read(state_dir() / "last_cycle.json", {})
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    main()
