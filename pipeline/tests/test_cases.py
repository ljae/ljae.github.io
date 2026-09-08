"""사례 대장 · 사례 픽스처.

두 가지를 시험한다.
1. `cases.py` 자체 — 접수를 파일로 옮기고, 상태를 줄 단위로 고치고, 산문을
   덧붙이고, 조용히 묻히는 것을 경고하는지.
2. `tests/cases/*.yaml` — 고친 신고가 되살아나지 않는지. 형식은 그 디렉터리의
   README.md. 픽스처 하나가 테스트 하나다.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import analyze, branches, build, cases, claims, dedupe  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "cases"
FIXTURES = sorted(p for p in FIXTURE_DIR.glob("*.yaml"))


# ── cases.py ─────────────────────────────────────────────────────
@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, "CASE_DIR", tmp_path / "cases")
    monkeypatch.setattr(cases, "FIXTURE_DIR", tmp_path / "fixtures")
    return tmp_path


def test_수동_사례는_파일_한_장이고_상태는_open_이다(ledger):
    path = cases.new_manual("1000035161", "대치정상수학학원",
                            "수학·영어를 결합했는데 이름이 수학학원이라 부적절하다",
                            reason="other")
    c = cases.get(path.stem)
    assert c["status"] == "open" and c["entity_key"] == "1000035161"
    assert c["source"] == "manual" and c["entity_type"] == "academy"
    assert "결합" in c["_body"]          # 접수 원문이 auto:report 에 남는다


def test_set_fields_는_frontmatter_만_줄_단위로_고치고_산문은_두지_않는다(ledger):
    path = cases.new_manual("A", "가학원", "신고 문장")
    cases.append_section(path.stem, "진단", "- 종류: relevance — 근거는 파일:줄")
    before_prose = cases.get(path.stem)["_body"]
    assert cases.set_fields(path.stem, status="triaged", category="relevance")
    c = cases.get(path.stem)
    assert c["status"] == "triaged" and c["category"] == "relevance"
    assert c["_body"] == before_prose    # 산문은 한 글자도 안 바뀐다
    # 값이 같으면 아무것도 안 한다
    assert cases.set_fields(path.stem, status="triaged") is False
    # 없는 상태·종류는 거부한다 — 오타가 조용히 새 상태가 되면 안 된다
    with pytest.raises(ValueError):
        cases.set_fields(path.stem, status="done")
    with pytest.raises(ValueError):
        cases.set_fields(path.stem, category="names")


def test_append_section_은_안내문을_걷고_기록을_날짜와_함께_쌓는다(ledger):
    path = cases.new_manual("A", "가학원", "신고")
    cases.append_section(path.stem, "조치", "첫 조치")
    cases.append_section(path.stem, "조치", "둘째 조치")
    body = cases.get(path.stem)["_body"]
    assert "(담당 gate-*" not in body     # 안내 괄호문은 사라진다
    assert body.index("첫 조치") < body.index("둘째 조치")
    assert body.count(f"### {date.today().isoformat()}") == 2
    assert "## 확인\n" in body            # 다른 절은 그대로


def test_고쳤는데_픽스처가_없으면_감사가_경고한다(ledger):
    path = cases.new_manual("A", "가학원", "신고")
    cases.set_fields(path.stem, status="fixed", resolution=["code"])
    warns = cases.audit()
    assert any("회귀 픽스처가 없다" in w for w in warns)
    # 픽스처를 두면 사라진다
    cases.FIXTURE_DIR.mkdir()
    (cases.FIXTURE_DIR / f"{path.stem}.yaml").write_text(
        f"case: {path.stem}\nkind: name\n", encoding="utf-8")
    assert not any("픽스처" in w for w in cases.audit())


def test_오래_열린_사례와_근거_없는_verified_를_경고한다(ledger):
    path = cases.new_manual("A", "가학원", "신고")
    cases.set_fields(path.stem, reported_at="2026-01-01")
    warns = cases.audit(today=date(2026, 3, 1))
    assert any("일째 open" in w for w in warns)
    cases.set_fields(path.stem, status="verified", resolution=["wiki"],
                     fixture="tests/cases/x.yaml")
    warns = cases.audit(today=date(2026, 3, 1))
    assert any("landed_in" in w for w in warns)


def test_요약은_상태와_진행_중_종류를_센다(ledger):
    a = cases.new_manual("A", "가", "x"); b = cases.new_manual("B", "나", "y")
    cases.set_fields(a.stem, status="triaged", category="subject")
    cases.set_fields(b.stem, status="fixed", resolution=["code"], fixture="t")
    s = cases.summary()
    assert "triaged 1" in s and "fixed 1" in s and "subject 1" in s


def test_사례_id_는_접수_id_에서_딴다():
    assert cases.case_id("evidence_report", "1a2b3c4d-5e6f-…") == "er-1a2b3c4d"
    assert cases.case_id("correction", "ABCDEF0123456789") == "co-abcdef01"
    assert cases.case_id("claim_dispute", "") == "cd-00000000"


# ── 픽스처 ───────────────────────────────────────────────────────
def _post(d: dict, key: str = "A") -> dict:
    return {
        "url_hash": d.get("url_hash", (d.get("title") or "h")[:12]),
        "source": d.get("source", "naver_cafe"),
        "source_url": d.get("source_url", "https://cafe.naver.com/x/1"),
        "title": d.get("title", ""),
        "snippet": d.get("snippet", ""),
        "posted_at": d.get("posted_at"),
        "academy_key": d.get("academy_key", key),
        "region_id": d.get("region_id", "daechi"),
    }


def _row(a: dict) -> dict:
    """build._infer_* 가 읽는 등록 행. README 의 짧은 키를 NEIS 키로 편다."""
    return {"name": a["name"],
            "realm_sc_nm": a.get("realm", "입시.검정 및 보습"),
            "le_crse_list_nm": a.get("course", ""),
            "le_crse_nm": a.get("crse", ""),
            "id": a.get("id", a["name"])}


def _rec(r: dict) -> dict:
    return {"id": r.get("id") or r["name"], "name": r["name"],
            "road_address": r.get("addr", ""),
            "region_id": r.get("region_id", "daechi"),
            "tofor_smtot": r.get("cap", 100),
            "estbl_ymd": r.get("estbl", "2010-01-01")}


def _candidates(academy: dict, wiki: dict | None) -> tuple[set[str], bool]:
    a = {"name": academy.get("name"), "brand": academy.get("brand"),
         "aliases": list(academy.get("aliases") or [])}
    c = analyze.name_candidates(a)
    for alias in (wiki or {}).get("aliases") or []:
        n = analyze._norm(alias)
        if len(n) >= 2:
            c.add(n)
    c -= analyze.weak_candidates(c)
    generic = analyze.is_generic_academy(a) or bool((wiki or {}).get("generic"))
    return c, generic


def evaluate(fx: dict) -> dict:
    kind = fx["kind"]
    if kind == "relevance":
        c, generic = _candidates(fx["academy"], fx.get("wiki"))
        rivals = analyze.RivalIndex({analyze._norm(r) for r in fx.get("rivals") or []})
        return {"relevant": analyze.is_relevant(_post(fx["mention"]), c, generic, rivals)}
    if kind == "name":
        c, _ = _candidates(fx["academy"], fx.get("wiki"))
        return {"candidates": sorted(c)}
    if kind == "subject":
        row = _row(fx["academy"])
        return {"subjects": build._infer_subjects(row),
                "bands": build._infer_bands(row)}
    if kind == "merge":
        out, _ = dedupe.apply([_rec(r) for r in fx["rows"]])
        n = len(fx["rows"])
        return {"merged": len(out) == 1, "groups": len(out), "rows": n}
    if kind == "branch":
        academies = [dict(a) for a in fx["academies"]]
        cands = {a["id"]: analyze.name_candidates(a) for a in academies}
        generic = {a["id"]: analyze.is_generic_academy(a) for a in academies}
        extra = {k: set(v) for k, v in (fx.get("locality") or {}).items()}
        mentions = fx.get("mentions") or [fx["mention"]]
        kept, _ = branches.apply([_post(m) for m in mentions], academies,
                                 cands, generic, set(), extra_locality=extra)
        return {"kept_for": sorted({m["academy_key"] for m in kept})}
    if kind == "claim":
        c, _ = _candidates(fx["academy"], fx.get("wiki"))
        rivals = frozenset(analyze._norm(r) for r in fx.get("rivals") or [])
        rows = claims.extract(_post(fx["mention"]), names=c, rivals=rivals)
        return {"claim_kinds": sorted({r["kind"] for r in rows}),
                "claims": [{"kind": r["kind"], "value": r.get("value")} for r in rows]}
    raise ValueError(f"모르는 kind {kind!r} — tests/cases/README.md 참고")


def check(expect: dict, got: dict) -> list[str]:
    problems: list[str] = []
    for key, want in expect.items():
        if key.endswith("_include"):
            base = key[:-8]
            have = got.get(base) or []
            missing = [w for w in want if w not in have]
            if missing:
                problems.append(f"{base} 에 {missing} 가 없다 (실제 {have})")
        elif key.endswith("_exclude"):
            base = key[:-8]
            have = got.get(base) or []
            leaked = [w for w in want if w in have]
            if leaked:
                problems.append(f"{base} 에 {leaked} 가 있다 (실제 {have})")
        else:
            if key not in got:
                problems.append(f"결과에 {key} 가 없다 ({sorted(got)})")
            elif got[key] != want:
                problems.append(f"{key}: 기대 {want!r} · 실제 {got[key]!r}")
    return problems


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_사례_픽스처(path: Path):
    fx = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for k in ("case", "kind", "expect"):
        assert k in fx, f"{path.name}: '{k}' 가 없다"
    got = evaluate(fx)
    problems = check(fx["expect"], got)
    assert not problems, f"{path.name} ({fx.get('why', '').strip()[:80]}): " + "; ".join(problems)


def test_픽스처_디렉터리가_비어_있지_않다():
    """이력 픽스처(hist-*)가 최소한 있어야 이 장치가 도는 것이 보인다."""
    assert any(p.stem.startswith("hist-") for p in FIXTURES)
