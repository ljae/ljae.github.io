"""Replay reviewed case fixtures through the same gates used by the pipeline.

Fixture expectations are human-maintained labels. Collection agents must never
replace them with their own judgements or promote an open report to a label.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from . import analyze, branches, claims, config, dedupe, scoring


def _post(value: dict, key: str = "A") -> dict:
    return {"url_hash": value.get("url_hash", (value.get("title") or "h")[:12]),
            "source": value.get("source", "naver_cafe"),
            "source_url": value.get("source_url", "https://cafe.naver.com/x/1"),
            "title": value.get("title", ""), "snippet": value.get("snippet", ""),
            "posted_at": value.get("posted_at"),
            "academy_key": value.get("academy_key", key),
            "region_id": value.get("region_id", "daechi")}


def _candidates(academy: dict, hints: dict | None = None) -> tuple[set[str], bool]:
    names = analyze.name_candidates(academy)
    for alias in (hints or {}).get("aliases") or []:
        normalized = analyze._norm(alias)
        if len(normalized) >= 2:
            names.add(normalized)
    names -= analyze.weak_candidates(names)
    return names, analyze.is_generic_academy(academy) or bool((hints or {}).get("generic"))


def evaluate(fixture: dict) -> dict:
    """Run a fixture without network access, exports, or state changes."""
    kind = fixture["kind"]
    if kind in ("relevance", "name", "claim"):
        names, generic = _candidates(fixture["academy"], fixture.get("wiki"))
        rivals = {analyze._norm(r) for r in fixture.get("rivals") or []}
        if kind == "name":
            return {"candidates": sorted(names)}
        if kind == "relevance":
            return {"relevant": analyze.is_relevant(
                _post(fixture["mention"]), names, generic, analyze.RivalIndex(rivals))}
        extracted = claims.extract(_post(fixture["mention"]), names=names,
                                   rivals=frozenset(rivals))
        return {"claim_kinds": sorted({r["kind"] for r in extracted}),
                "claims": [{"kind": r["kind"], "value": r.get("value")} for r in extracted]}
    if kind == "branch":
        academies = [dict(a) for a in fixture["academies"]]
        names = {a["id"]: analyze.name_candidates(a) for a in academies}
        generic = {a["id"]: analyze.is_generic_academy(a) for a in academies}
        extra = {key: set(value) for key, value in (fixture.get("locality") or {}).items()}
        posts = fixture.get("mentions") or [fixture["mention"]]
        kept, _ = branches.apply([_post(m) for m in posts], academies,
                                 names, generic, set(), extra_locality=extra)
        return {"kept_for": sorted({m["academy_key"] for m in kept})}
    if kind == "subject":
        # Lazy import avoids a build → agent_cycle → replay → build cycle.
        from . import build
        academy = fixture["academy"]
        row = {"name": academy["name"], "id": academy.get("id", academy["name"]),
               "realm_sc_nm": academy.get("realm", "입시.검정 및 보습"),
               "le_crse_list_nm": academy.get("course", ""),
               "le_crse_nm": academy.get("crse", "")}
        return {"subjects": build._infer_subjects(row), "bands": build._infer_bands(row)}
    if kind == "merge":
        rows = [{"id": r.get("id") or r["name"], "name": r["name"],
                 "road_address": r.get("addr", ""), "region_id": r.get("region_id", "daechi"),
                 "tofor_smtot": r.get("cap", 100), "estbl_ymd": r.get("estbl", "2010-01-01")}
                for r in fixture["rows"]]
        merged, _ = dedupe.apply(rows)
        return {"merged": len(merged) == 1, "groups": len(merged), "rows": len(rows)}
    raise ValueError(f"unsupported fixture kind: {kind!r}")


def check(expect: dict, actual: dict) -> list[str]:
    problems = []
    for key, wanted in expect.items():
        if key.endswith("_include"):
            missing = [v for v in wanted if v not in (actual.get(key[:-8]) or [])]
            if missing:
                problems.append(f"{key}: missing {missing!r}")
        elif key.endswith("_exclude"):
            leaked = [v for v in wanted if v in (actual.get(key[:-8]) or [])]
            if leaked:
                problems.append(f"{key}: leaked {leaked!r}")
        elif key not in actual or actual[key] != wanted:
            problems.append(f"{key}: expected {wanted!r}, got {actual.get(key)!r}")
    return problems


def verify_history(fixture_dir: Path | None = None) -> dict:
    """Fail closed on missing, malformed, unknown, or failing fixtures."""
    directory = Path(fixture_dir) if fixture_dir is not None else config.PIPELINE_DIR / "tests" / "cases"
    results = []
    corpus = hashlib.sha256()
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = path.read_bytes()
            corpus.update(path.name.encode() + b"\0" + raw + b"\0")
            fixture = yaml.safe_load(raw.decode("utf-8"))
            if not isinstance(fixture, dict) or not fixture.get("case") \
                    or not isinstance(fixture.get("expect"), dict) or not fixture["expect"]:
                raise ValueError("case and nonempty expect are required")
            actual = evaluate(fixture)
            problems = check(fixture["expect"], actual)
            results.append({"case": fixture["case"], "kind": fixture["kind"],
                            "source": str(path), "passed": not problems, "problems": problems})
        except Exception as exc:
            # One broken case must not hide the remaining regression results.
            results.append({"case": path.stem, "source": str(path), "passed": False,
                            "problems": [f"{type(exc).__name__}: {exc}"]})
    passed = sum(row["passed"] for row in results)
    policy = hashlib.sha256()
    for name in ("analyze.py", "branches.py", "claims.py", "dedupe.py", "build.py",
                 "evidence.py", "review_integrity.py", "scoring.py", "config.py", "wiki.py"):
        path = Path(__file__).parent / name
        policy.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return {"ok": bool(results) and passed == len(results), "total": len(results),
            "passed": passed, "failed": len(results) - passed,
            "results": results, "corpus_sha256": corpus.hexdigest(),
            "policy_version": {"scoring": scoring.SCORING_VERSION, "gates_sha256": policy.hexdigest()},
            "error": None if results else "no historical fixtures found"}
