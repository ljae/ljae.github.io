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

from edutree import cases  # noqa: E402
from edutree.case_replay import check, evaluate  # noqa: E402

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
