"""언급 저장소 크기 예산 — 2026-11-22·23 야간 게시 중단의 회귀 시험.

저장소가 검색 결과를 전부 쌓아 백업 검사 한도(1 GiB)를 넘었다. 쓰는 쪽이
예산을 지키고, 근거가 된 줄은 절대 지우지 않는다.
"""
from __future__ import annotations

import gzip
import json

import pytest

from pipeline.edutree import evidence_backup, mention_store


@pytest.fixture
def store_path(tmp_path, monkeypatch):
    path = tmp_path / "mention_store.json.gz"
    monkeypatch.setattr(mention_store, "PATH", path)
    return path


def _row(i, day="2026-11-01", academy="A"):
    return {"url_hash": f"u{i}", "academy_key": academy, "title": f"t{i}",
            "snippet": "가" * 200, "source": "naver_blog"}


def test_budget_is_below_backup_limit():
    assert mention_store.RAW_BUDGET_BYTES < evidence_backup.MAX_RAW_BYTES * 0.8


def test_retain_drops_only_non_evidence_oldest_first(store_path):
    mention_store.merge([_row(i) for i in range(10)], today="2026-11-01", quiet=True)
    mention_store.merge([_row(i) for i in range(10, 20)], today="2026-11-20", quiet=True)
    evidence = {"u0", "u1"}          # 가장 오래된 줄 중 둘은 근거
    one = mention_store._row_bytes("u0|A", mention_store.load()["u0|A"])
    result = mention_store.retain(evidence, today="2026-11-24",
                                  budget=one * 8, quiet=True)
    kept = mention_store.load()
    assert "u0|A" in kept and "u1|A" in kept, "근거가 된 줄은 지우지 않는다"
    assert kept["u0|A"]["evidence_seen"] == "2026-11-24"
    assert result["dropped"] > 0 and not result["overBudget"]
    loose = [k for k in kept if k not in ("u0|A", "u1|A")]
    assert all(kept[k]["last_seen"] == "2026-11-20" for k in loose), "오래 못 본 것부터 뺀다"
    # 저장 파일의 실제 원본 크기가 예산을 지킨다 — 백업이 보는 값과 같은 잣대
    with gzip.open(store_path, "rb") as fh:
        assert len(fh.read()) <= one * 8


def test_evidence_alone_over_budget_is_kept_and_reported(store_path):
    mention_store.merge([_row(i) for i in range(5)], today="2026-11-01", quiet=True)
    result = mention_store.retain({f"u{i}" for i in range(5)}, budget=10, quiet=True)
    assert result["overBudget"] and result["dropped"] == 0
    assert len(mention_store.load()) == 5


def test_cap_prefers_dropping_non_evidence(store_path, monkeypatch):
    monkeypatch.setattr(mention_store, "KEEP_PER_ACADEMY", 3)
    mention_store.merge([_row(i) for i in range(3)], today="2026-11-01", quiet=True)
    mention_store.retain({"u0"}, today="2026-11-02", budget=10**9, quiet=True)
    mention_store.merge([_row(i) for i in range(3, 5)], today="2026-11-03", quiet=True)
    assert "u0|A" in mention_store.load()


def test_oversized_local_store_is_merged_not_overwritten_on_restore(tmp_path, monkeypatch):
    """11-23: 로컬 저장소가 한도를 넘자 '읽을 수 없음' 으로 보고 옛 체크포인트로
    덮어써 그 사이 수집분을 잃었다. 로컬은 한도와 무관하게 합친다."""
    import secrets
    src, dst = tmp_path / "src", tmp_path / "dst"
    for path, key, size in ((src, "old", 10), (dst, "new", 300)):
        path.mkdir()
        (path / "mention_store.json.gz").write_bytes(gzip.compress(json.dumps(
            {"version": 1, "rows": {key: {"snippet": "x" * size}}}).encode()))
        (path / "first_seen.json").write_text(json.dumps({key: "2026-11-01"}))
    key = secrets.token_bytes(32)
    body, manifest = evidence_backup.pack(src, key)
    monkeypatch.setattr(evidence_backup, "MAX_RAW_BYTES", 200)
    evidence_backup.restore(body, key, dst)
    rows = evidence_backup.raw_rows((dst / "mention_store.json.gz").read_bytes(), local=True)
    assert set(rows) == {"old", "new"}


def test_checkpoint_records_evidence_rows_and_restore_floor_uses_them(tmp_path):
    import secrets
    src = tmp_path / "src"
    src.mkdir()
    rows = {"a": {"evidence_seen": "2026-11-24"}, "b": {}, "c": {}}
    (src / "mention_store.json.gz").write_bytes(gzip.compress(json.dumps(
        {"version": 1, "rows": rows}).encode()))
    (src / "first_seen.json").write_text("{}")
    _, manifest = evidence_backup.pack(src, secrets.token_bytes(32))
    assert manifest["rawRows"] == 3 and manifest["evidenceRows"] == 1
