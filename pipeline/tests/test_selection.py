"""수집 대상 선정 — 근거가 저장소에 남으므로 순위권을 매일 다시 보지 않는다."""
from __future__ import annotations

from edutree import build, config, coverage, demand


def _academy(i: int, **kw) -> dict:
    return {"id": f"a{i}", "name": f"학원{i}", "region_id": "daechi",
            "subjects": ["math"], "grade_bands": ["elem_low"], "stages": [],
            "tofor_smtot": 100, **kw}


def test_순위권은_주기가_지났을_때만_다시_보고_그_자리를_안_본_곳에_준다(monkeypatch):
    monkeypatch.setattr(config, "NAVER_MAX_ACADEMIES", 80)   # 학군당 20
    stale = [_academy(i) for i in range(5)]                  # 순위권 · 8일 전
    recent = [_academy(i) for i in range(5, 10)]             # 순위권 · 어제
    unseen = [_academy(i) for i in range(10, 30)]            # 한 번도 안 봄
    hist = {a["id"]: {"tries": 3, "dry": 0, "last": 20, "last_at": "2026-08-25"}
            for a in stale}
    hist.update({a["id"]: {"tries": 3, "dry": 0, "last": 20, "last_at": "2026-09-01"}
                 for a in recent})
    monkeypatch.setattr(coverage, "load", lambda: hist)
    monkeypatch.setattr(demand, "load", lambda: {})
    import datetime as _dt
    real_date = _dt.date

    class _Today(_dt.date):
        @classmethod
        def today(cls):
            return real_date(2026, 9, 2)
    monkeypatch.setattr(coverage, "date", _Today, raising=False)

    prev = {a["id"]: {"is_ranked": True} for a in stale + recent}
    selected, skipped = build.select_for_mentions(stale + recent + unseen, prev,
                                                  known={a["id"] for a in stale + recent})
    ids = {a["id"] for a in selected}
    assert len(selected) == 20
    assert all(a["id"] in ids for a in stale), "주기가 지난 순위권은 다시 본다"
    assert not any(a["id"] in ids for a in recent), "어제 본 순위권은 쉰다"
    assert sum(1 for a in unseen if a["id"] in ids) == 15
    assert len(skipped) == 10


def test_며칠_지났는지는_기록이_없으면_모른다():
    assert coverage.days_since(None) is None
    assert coverage.days_since({"tries": 1}) is None
    from datetime import date
    assert coverage.days_since({"last_at": "2026-09-01"}, today=date(2026, 9, 8)) == 7
