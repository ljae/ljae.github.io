"""수집 대상 선정 — 근거가 선 곳은 자리를 지킨다.

랭킹에 든 학원이 수집 대상에서 밀리면 **화면에서 사라진다.** 근거가
나빠져서가 아니라 우리가 안 봐서다. 그런데 그 보호가 두 번 샜다.

1. 기억이 **잘려 나가는 파일에만** 있었다. `_previous_scores()` 는
   academies.json 을 읽는데 그 파일이 곧 선정의 결과물이다. 한 회차
   밀리면 다음 회차에는 '순위였던 적 없는 곳' 이 되어 영영 못 돌아온다.
2. 정렬로 앞세우는 것만으로는 모자랐다. 구간·과목마다 자리가 열아홉
   칸 남짓이라 같은 층이 넘치면 마지막 열쇠인 **정원**이 승부를 갈랐다.

실측: 렉스김어학원(대치 빅3 영어 · 표본 111 · 총점 49.7 · 정원 60)이
23회를 수집하고도 화면에서 사라져 있었다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import build, config  # noqa: E402


def test_general_registration_does_not_block_curated_thinking_bull_match():
    raw = {
        "id": "3000029897", "aca_asnum": "3000029897", "name": "생각하는황소서초2관학원",
        "le_crse_list_nm": "보습,보습·논술", "le_crse_nm": "보습",
        "realm_sc_nm": "입시.검정 및 보습", "reg_sttus_nm": "정상",
        "tofor_smtot": 100, "estbl_ymd": "2020-01-01",
        "road_address": "서울특별시 서초구 고무래로10길 26",
        "region_id": "banpo", "subjects": ["general"],
    }
    [matched] = build._merge_seed_into_neis([raw])
    assert matched["brand"] == "생각하는황소"
    assert matched["subjects"] == ["math"]
    assert matched["curated_stages"] is True
    assert matched["collection_priority"] == 100
    assert matched["display_name"] == "생각하는황소 서초 본관·2관"


def test_curated_branch_name_survives_display_name_assignment():
    rows = [{"id": "main", "name": "생각하는황소학원",
             "display_name": "생각하는황소 대치 본관",
             "region_id": "daechi", "road_address": "서울특별시 강남구 영동대로 302"}]
    build.assign_display_names(rows)
    assert rows[0]["display_name"] == "생각하는황소 대치 본관"


def academy(aid, *, capacity, subjects=("english",), region="daechi",
            bands=("elem_low", "elem_high"), curated=False):
    return {
        "id": aid,
        "name": f"학원{aid}",
        "region_id": region,
        "subjects": list(subjects),
        "grade_bands": list(bands),
        "tofor_smtot": capacity,
        "curated_stages": curated,
    }


def test_순위였던_작은_학원이_큰_학원들에_밀리지_않는다(monkeypatch):
    # 같은 구간·같은 과목에 정원이 큰 후보를 자리 수보다 많이 둔다.
    # 예산(학군당 100곳)보다 후보가 많아야 경쟁이 실제로 일어난다.
    big = [academy(f"big{i}", capacity=5000) for i in range(300)]
    small = academy("rex", capacity=60, curated=True)

    # 지난 회차 파일에는 없다(한 번 밀려난 상태) — 이력만 남아 있다.
    monkeypatch.setattr(build, "_previous_scores", lambda: {})
    from edutree import coverage, demand
    monkeypatch.setattr(coverage, "load",
                        lambda: {"rex": {"tries": 23, "dry": 0, "last": 115}})
    monkeypatch.setattr(coverage, "stage_gaps", lambda *a, **k: {})
    monkeypatch.setattr(coverage, "priority_bonus", lambda *a, **k: (0,))
    monkeypatch.setattr(demand, "load", lambda: {})

    evaluated, _ = build.select_for_mentions(
        big + [small], build._previous_scores())
    assert "rex" in {a["id"] for a in evaluated}, \
        "이력이 남은 순위 학원이 수집 대상에서 빠졌다"

    # 대비군: 이력도 없고 큐레이션도 안 된 작은 학원은 밀리는 것이 정상이다.
    # (큐레이션만 있고 이력이 없으면 '한 번도 안 본 시드' 예비석으로 뽑히는
    #  것이 맞으므로, 대비군에서는 둘 다 뺀다.)
    # 이 대비가 없으면 위 단언이 '늘 통과' 라 시험이 아니다.
    monkeypatch.setattr(coverage, "load", lambda: {})
    evaluated2, _ = build.select_for_mentions(
        big + [academy("rex", capacity=60)], build._previous_scores())
    assert "rex" not in {a["id"] for a in evaluated2}, \
        "대비군이 통과해 버리면 위 단언이 아무것도 증명하지 않는다"


def test_자리를_먼저_떼도_예산이_불어나지_않는다(monkeypatch):
    """지킨 자리를 예산에 더하면 회차마다 대상이 불어난다(실측 400 → 442)."""
    rows = [academy(f"a{i}", capacity=1000 + i) for i in range(300)]
    keep = {f"a{i}" for i in range(40)}

    monkeypatch.setattr(build, "_previous_scores",
                        lambda: {k: {"is_ranked": True} for k in keep})
    from edutree import coverage, demand
    monkeypatch.setattr(coverage, "load", lambda: {})
    monkeypatch.setattr(coverage, "stage_gaps", lambda *a, **k: {})
    monkeypatch.setattr(coverage, "priority_bonus", lambda *a, **k: (0,))
    monkeypatch.setattr(demand, "load", lambda: {})

    evaluated, _ = build.select_for_mentions(rows, build._previous_scores())
    per_region = config.NAVER_MAX_ACADEMIES // len(config.regions())

    assert keep <= {a["id"] for a in evaluated}, "지킨 자리가 빠졌다"
    assert len(evaluated) <= per_region, f"예산이 샜다: {len(evaluated)}곳"


# ── 근거는 저장소에 남는다 — 순위권은 주기가 지났을 때만 다시 본다 ──
# (mention_store 도입 뒤. 위 '자리를 지킨다' 는 이제 REFRESH_DAYS 가 지난
#  순위권에만 걸린다 — 안 봐도 화면에서 안 사라지므로 그 자리를 아직 안 본
#  곳에 준다.)

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
    from edutree import coverage, demand
    monkeypatch.setattr(coverage, "load", lambda: hist)
    monkeypatch.setattr(demand, "load", lambda: {})
    # ★ `coverage.days_since` 는 `date` 를 함수 안에서 import 한다. 모듈 속성
    #   `coverage.date` 를 갈아끼워도 아무 효과가 없어, 이 테스트는 실제
    #   달력에 따라 갈렸다(실측 2026-09-08: last_at 09-01 이 정확히 7일이라
    #   '어제 본 순위권' 이 주기가 지난 것으로 잡혀 실패). 오늘을 함수
    #   인자로 고정한다 — 시험은 달력을 보면 안 된다.
    from datetime import date as _date
    _real = coverage.days_since
    monkeypatch.setattr(coverage, "days_since",
                        lambda row, today=None: _real(row, _date(2026, 9, 2)))

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
    from edutree import coverage
    assert coverage.days_since(None) is None
    assert coverage.days_since({"tries": 1}) is None
    from datetime import date
    assert coverage.days_since({"last_at": "2026-09-01"}, today=date(2026, 9, 8)) == 7


@pytest.fixture
def selection_history(monkeypatch):
    """No live coverage/wiki/action state may determine budget regressions."""
    from datetime import date
    from edutree import actions, coverage, demand, wiki
    history = {}
    monkeypatch.setattr(config, "regions", lambda: [
        {"id": region} for region in ("daechi", "mokdong", "banpo", "jamsil")])
    monkeypatch.setattr(coverage, "load", lambda: history)
    monkeypatch.setattr(coverage, "stage_gaps", lambda *args, **kwargs: {})
    monkeypatch.setattr(coverage, "priority_bonus", lambda *args, **kwargs: (0,))
    days_since = coverage.days_since
    monkeypatch.setattr(coverage, "days_since",
                        lambda row, today=None: days_since(row, date(2026, 10, 17)))
    monkeypatch.setattr(demand, "load", lambda: {})
    monkeypatch.setattr(actions, "load", lambda: {})
    monkeypatch.setattr(wiki, "load", lambda: {})
    return history


def test_ranked_overload_stays_in_budget_and_keeps_exploration(monkeypatch, selection_history):
    monkeypatch.setattr(config, "NAVER_MAX_ACADEMIES", 400)
    rows, ranked = [], set()
    for region in ("daechi", "mokdong", "banpo", "jamsil"):
        for index in range(450):
            aid = f"{region}-ranked-{index:03}"
            rows.append(academy(aid, capacity=100 + index, region=region))
            ranked.add(aid)
            selection_history[aid] = {
                "last": 30, "last_at": "2026-08-01" if index < 80 else "2026-09-01"}
        rows.extend(academy(f"{region}-new-{index}", capacity=1, region=region)
                    for index in range(50))
    selected, skipped = build.select_for_mentions(
        rows, {aid: {"is_ranked": True} for aid in ranked}, known=ranked)
    ids = {a["id"] for a in selected}
    assert len(selected) == len(ids) == 400
    assert len(skipped) == 1600
    for region in ("daechi", "mokdong", "banpo", "jamsil"):
        local = [a for a in selected if a["region_id"] == region]
        assert len(local) == 100
        assert sum(a["id"] not in ranked for a in local) == 20
        assert {f"{region}-ranked-{index:03}" for index in range(80)} <= ids
    # Existing evidence outside this refresh batch remains available to build.run.
    assert ranked - ids <= {a["id"] for a in skipped}
    assert len(ranked) == 1800


@pytest.mark.parametrize("budget", [0, 1, 2, 3, 4, 5, 7, 11, 20])
def test_small_budgets_seeds_and_band_quotas_never_overflow(
        monkeypatch, selection_history, budget):
    monkeypatch.setattr(config, "NAVER_MAX_ACADEMIES", budget)
    rows = [academy(f"{region}-seed-{index}", capacity=100, region=region,
                    bands=tuple(config.GRADE_BANDS), curated=True)
            for region in ("daechi", "mokdong", "banpo", "jamsil")
            for index in range(20)]
    selected, skipped = build.select_for_mentions(rows)
    assert len(selected) == budget
    selected_ids = {a["id"] for a in selected}
    skipped_ids = {a["id"] for a in skipped}
    assert selected_ids.isdisjoint(skipped_ids)
    assert selected_ids | skipped_ids == {a["id"] for a in rows}
    regional_counts = [sum(a["region_id"] == region for a in selected)
                       for region in ("daechi", "mokdong", "banpo", "jamsil")]
    assert max(regional_counts) - min(regional_counts) <= 1


def test_new_seeds_share_exploration_budget_with_old_ranked_refresh(
        monkeypatch, selection_history):
    monkeypatch.setattr(config, "NAVER_MAX_ACADEMIES", 40)  # 10 per region
    ranked = [academy(f"ranked{i:02}", capacity=5000) for i in range(30)]
    seeds = [academy(f"seed{i:02}", capacity=1, curated=True) for i in range(20)]
    for index, row in enumerate(ranked):
        selection_history[row["id"]] = {
            "last": 40, "last_at": "2026-08-01" if index < 8 else "2026-09-01"}
    selected, _ = build.select_for_mentions(ranked + seeds)
    assert len(selected) == 10
    ids = {a["id"] for a in selected}
    assert {f"ranked{i:02}" for i in range(8)} <= ids
    assert sum(a["curated_stages"] for a in selected) == 2


def test_unknown_regions_are_skipped_without_stealing_budget(
        monkeypatch, selection_history):
    monkeypatch.setattr(config, "NAVER_MAX_ACADEMIES", 3)
    rows = [academy("known", capacity=1),
            academy("outside", capacity=999999, region="outside", curated=True)]
    selected, skipped = build.select_for_mentions(rows)
    assert [a["id"] for a in selected] == ["known"]
    assert [a["id"] for a in skipped] == ["outside"]
    monkeypatch.setattr(config, "regions", lambda: [])
    assert build.select_for_mentions(rows) == ([], rows)
