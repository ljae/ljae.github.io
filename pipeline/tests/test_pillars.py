"""학술 과목은 **네 기둥을 다 채운 곳끼리만** 순위를 맺는다.

남은 기둥으로 가중치를 다시 나누면 **없는 기둥이 유리해진다** — 남은
기둥의 몫이 커지기 때문이다.

실측 신고: 모닝에듀(투명 100 · 표본 13)가 진입난이도가 없다는 이유로
투명성 몫을 15% → 23% 로 받아 총점 57.9 가 됐고, 진입난이도 56.9 를
**실제로 가진** 렉스김어학원(표본 127 · 총점 57.3)을 앞질렀다.
근거가 얇을수록 유리한 산식이었다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import config  # noqa: E402


W = config.WEIGHTS


def total4(rep, mom, tra, sel):
    return (W["reputation"] * rep + W["momentum"] * mom
            + W["transparency"] * tra + W["selectivity"] * sel)


def total_partial(rep, mom, tra):
    """채운 기둥만 더한 값. 가중치 합이 0.65 라 4기둥과 견줄 수 없다."""
    return W["reputation"] * rep + W["momentum"] * mom + W["transparency"] * tra


def test_재정규화하면_없는_기둥이_유리해진다():
    """고치기 전 산식을 그대로 재현해 역전을 보인다 — 이게 신고의 내용이다."""
    rex = total4(40.3, 57.2, 98.0, 56.9)          # 렉스김: 네 기둥 다 있음
    # 옛 방식: selectivity 를 빼고 남은 셋으로 재정규화(합 0.65 → 1.0)
    scale = W["reputation"] + W["momentum"] + W["transparency"]
    morning_old = (W["reputation"] / scale * 45.6
                   + W["momentum"] / scale * 44.7
                   + W["transparency"] / scale * 100.0)

    assert round(rex, 1) == 57.3
    assert round(morning_old, 1) == 57.9
    assert morning_old > rex, "옛 산식에서는 기둥이 빈 쪽이 이겼다"


def test_채운_기둥만_더하면_역전이_사라진다():
    rex = total4(40.3, 57.2, 98.0, 56.9)
    morning = total_partial(45.6, 44.7, 100.0)
    assert morning < rex, "빈 기둥이 더는 유리하지 않다"


def test_가중치는_넷의_합이_1이다():
    """화면과 산식 페이지가 이 값을 그대로 찍는다."""
    assert set(W) == {"reputation", "momentum", "transparency", "selectivity"}
    assert round(sum(W.values()), 6) == 1.0
    assert W["selectivity"] == 0.35


def test_예체능은_두_기둥_산식이_정본이다():
    """진입난이도가 없다고 순위에서 빼면 예체능이 통째로 사라진다."""
    n = config.NON_ACADEMIC_WEIGHTS
    assert set(n) == {"reputation", "momentum"}
    assert round(sum(n.values()), 6) == 1.0
