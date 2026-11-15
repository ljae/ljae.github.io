"""학부모 제보 — 수집 우선순위로만, 실패하면 빈 값으로.

세 가지를 굳힌다.
1. 세는 것은 '학원별 서로 다른 기기 수' 다. 버린 답은 안 센다.
2. 못 읽으면(키 없음·네트워크·표 없음·깨진 응답) 빈 값이고 실행은 계속된다.
3. 이 신호가 닿는 곳은 수요 신호(want)뿐이다. 채점 모듈은 이 모듈을 모른다.
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import config, parent_reports  # noqa: E402


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _row(academy, device, status="received"):
    return {"academy_key": academy, "device_hash": device, "status": status}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "HAS_SUPABASE", True)
    monkeypatch.setattr(config, "SUPABASE_URL", "https://test.invalid")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "service-test-key")


def test_counts_distinct_devices_per_academy():
    rows = [_row("A1", "d1"), _row("A1", "d2"), _row("A1", "d1", "kept"),
            _row("A2", "d1"), _row("", "d9"), _row("A3", "")]
    assert parent_reports.counts(rows) == {"A1": 2, "A2": 1}


def test_discarded_is_not_counted():
    rows = [_row("A1", "d1", "discarded"), _row("A1", "d2", "kept"),
            _row("A2", "d3", "discarded")]
    # A2 는 0 이 아니라 아예 없다 — 버린 답뿐인 학원에는 신호가 없다.
    assert parent_reports.counts(rows) == {"A1": 1}


def test_query_excludes_discarded_and_reads_only_pair_columns(
        configured, monkeypatch):
    seen = []

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.append((url, params, headers))
        return _Resp([_row("A1", "d1")])

    monkeypatch.setattr(parent_reports.requests, "get", fake_get)
    assert parent_reports.load() == {"A1": 1}
    [(url, params, headers)] = seen
    assert url == "https://test.invalid/rest/v1/parent_reports"
    assert params["status"] == "neq.discarded"
    # 답의 내용(레벨테스트·숙제량…)은 파이프라인으로 가져오지 않는다.
    assert params["select"] == "academy_key,device_hash,status"
    assert headers["apikey"] == "service-test-key"


def test_pagination_continues_until_short_page(configured, monkeypatch):
    monkeypatch.setattr(parent_reports, "PAGE", 2)
    pages = [[_row("A1", "d1"), _row("A1", "d2")], [_row("A2", "d3")]]
    offsets = []

    def fake_get(url, params=None, headers=None, timeout=None):
        offsets.append(params["offset"])
        return _Resp(pages[len(offsets) - 1])

    monkeypatch.setattr(parent_reports.requests, "get", fake_get)
    assert parent_reports.load() == {"A1": 2, "A2": 1}
    assert offsets == [0, 2]


def test_unconfigured_does_not_touch_network(monkeypatch):
    monkeypatch.setattr(config, "HAS_SUPABASE", False)

    def boom(*a, **k):
        raise AssertionError("키가 없는데 네트워크를 불렀다")

    monkeypatch.setattr(parent_reports.requests, "get", boom)
    want = {"A1": 3}
    assert parent_reports.load() == {}
    assert parent_reports.add_to(want) == 0
    assert want == {"A1": 3}


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("down"),
    requests.Timeout("slow"),
])
def test_network_failure_is_empty_with_one_log_line(
        configured, monkeypatch, capsys, failure):
    def fake_get(*a, **k):
        raise failure

    monkeypatch.setattr(parent_reports.requests, "get", fake_get)
    want = {"A1": 3}
    assert parent_reports.add_to(want) == 0
    assert want == {"A1": 3}
    lines = [x for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert len(lines) == 1 and "학부모 제보" in lines[0]


@pytest.mark.parametrize("resp", [
    _Resp({"message": "relation does not exist"}, status=404),  # 표 미적용
    _Resp(ValueError("not json")),                               # 깨진 본문
    _Resp({"unexpected": "object"}),                             # 목록 아님
])
def test_bad_response_is_empty_with_one_log_line(
        configured, monkeypatch, capsys, resp):
    monkeypatch.setattr(parent_reports.requests, "get", lambda *a, **k: resp)
    assert parent_reports.load() == {}
    lines = [x for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert len(lines) == 1 and "학부모 제보" in lines[0]


def test_failure_on_later_page_drops_everything(configured, monkeypatch):
    """절반만 받은 것으로 세지 않는다."""
    monkeypatch.setattr(parent_reports, "PAGE", 1)
    calls = []

    def fake_get(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            return _Resp([_row("A1", "d1")])
        raise requests.ConnectionError("down")

    monkeypatch.setattr(parent_reports.requests, "get", fake_get)
    assert parent_reports.load() == {}


def test_priority_bonus_is_capped(configured, monkeypatch):
    rows = [_row("A1", f"d{i}") for i in range(50)] + [_row("A2", "d1")]
    monkeypatch.setattr(parent_reports, "_rows", lambda: rows)
    want = {"A2": 5}
    assert parent_reports.add_to(want) == 2
    assert want == {"A1": parent_reports.CAP,
                    "A2": 5 + parent_reports.WEIGHT}


def test_signal_reaches_selection_only():
    """채점·기둥·순위 모듈은 이 모듈을 모른다. 닿는 곳은 build 의 선정뿐이다."""
    pkg = Path(parent_reports.__file__).parent
    users = sorted(p.name for p in pkg.glob("*.py")
                   if p.name != "parent_reports.py"
                   and "parent_reports" in p.read_text(encoding="utf-8"))
    assert users == ["build.py"]
    src = (pkg / "build.py").read_text(encoding="utf-8")
    assert src.count("parent_reports.") == 1
    assert "parent_reports.add_to(want)" in src
    # 그 한 번의 호출은 수집 대상 선정 함수 안에 있다.
    start = src.index("def select_for_mentions(")
    end = src.index("\ndef ", start + 1)
    assert start < src.index("parent_reports.add_to(want)") < end
