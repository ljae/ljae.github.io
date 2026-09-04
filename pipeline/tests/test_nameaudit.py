"""이름이 오염원인 학원을 전수로 찾는다.

'새로운학원' 신고를 낱말 추가로 고쳤더니, 같은 성질의 학원이 여섯 곳 더
있었다. 신고는 한 곳으로 오지만 원인은 낱말이다 — 그래서 매 실행 전수로
잰다. 사전이 아니라 **코퍼스**로 재는 것이 요점이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import nameaudit, questions, wiki  # noqa: E402


def post(title, body=""):
    return {"title": title, "snippet": body}


def mention(aid, title):
    return {"academy_key": aid, "title": title, "snippet": ""}


def academy(aid, name):
    return {"id": aid, "name": name, "display_name": name, "region_id": "daechi"}


def test_일반명사_이름은_코퍼스에서_넓게_퍼져_걸린다():
    """'테스트' 는 레벨테스트 글마다 나온다 — 제 근거보다 훨씬 넓다."""
    corpus = [post(f"에이프릴 레벨테스트 후기 {i}") for i in range(200)]
    corpus += [post(f"테스트 학원 다녀왔어요 {i}") for i in range(10)]
    mentions = [mention("a1", f"테스트 관련 글 {i}") for i in range(10)]

    rows = nameaudit.measure(
        [academy("a1", "테스트학원")], mentions, corpus, {"a1": {"테스트"}})

    assert len(rows) == 1
    r = rows[0]
    assert r["token"] == "테스트"
    assert r["wide"] == 210 and r["own"] == 10
    assert r["spread"] == 21.0
    assert "퍼짐" in r["why"]


def test_제_이름만_가리키는_학원은_안_걸린다():
    """'렉스김' 은 코퍼스에서도 제 근거만큼만 나온다 — 정상이다."""
    corpus = [post(f"렉스김 어학원 레테 후기 {i}") for i in range(40)]
    corpus += [post(f"대치 영어학원 고민 {i}") for i in range(300)]
    mentions = [mention("a1", f"렉스김 어학원 후기 {i}") for i in range(35)]

    rows = nameaudit.measure(
        [academy("a1", "렉스김어학원")], mentions, corpus, {"a1": {"렉스김"}})
    assert rows == []


def test_사람_이름_학원은_제목에_이름이_없어서_걸린다():
    """동명이인은 넓이로는 안 걸릴 수 있다. 그 글들의 **주인공이 남**이라
    제목에 이름이 안 나오는 것으로 드러난다(윤도영·뮤지컬 배우)."""
    corpus = [post(f"뮤지컬 커튼콜 후기 {i}", "배우 류다현") for i in range(60)]
    mentions = [mention("a1", f"공연 관람기 {i}") for i in range(20)]

    rows = nameaudit.measure(
        [academy("a1", "류다현수학학원")], mentions, corpus, {"a1": {"류다현"}})

    assert len(rows) == 1
    assert rows[0]["title_ratio"] == 0.0
    assert "제목에 이름 없음" in rows[0]["why"]


def test_근거가_적으면_판단하지_않는다():
    """비율이 요동친다. 모르는 것을 아는 척하지 않는다."""
    corpus = [post("테스트") for _ in range(500)]
    mentions = [mention("a1", "글") for _ in range(3)]
    assert nameaudit.measure(
        [academy("a1", "테스트학원")], mentions, corpus, {"a1": {"테스트"}}) == []


def test_두_글자_후보는_보지_않는다():
    """우연이 너무 잦다. 그건 EVERYDAY_ALIASES 가 다루는 층이다."""
    corpus = [post("정상적인 면역기능") for _ in range(200)]
    mentions = [mention("a1", "글") for _ in range(20)]
    assert nameaudit.measure(
        [academy("a1", "정상어학원")], mentions, corpus, {"a1": {"정상"}}) == []


def test_보고는_이미_표시된_곳과_새로_걸린_곳을_가른다():
    """매 실행 같은 목록을 뒤섞어 찍으면 새 신호가 묻힌다 — **가른다.**

    ★ 2026-09-03 정정. 예전에는 이미 표시된 곳을 **아예 안 찍었다.**
      그래서 '새로운학원' 이 8/31 에 generic 으로 표시된 뒤에도 계속
      퍼지고 있다는 사실이 로그에서 한 번도 보이지 않았고, 그동안 그
      학원은 목동 영어 순위에 남아 있었다. 조여 놓았는데도 퍼진다는 것은
      **조이는 것이 안 먹는다는 신호**다 — 새로 걸린 곳과 나란히 두되
      섞지 않고, 다른 말을 붙여 따로 적는다.
    """
    rows = [
        {"id": "a1", "name": "테스트", "region_id": "jamsil", "token": "테스트",
         "own": 10, "wide": 210, "spread": 21.0, "title_ratio": 0.1, "why": "퍼짐"},
        {"id": "a2", "name": "새로운학원", "region_id": "mokdong", "token": "새로운",
         "own": 12, "wide": 61, "spread": 5.1, "title_ratio": 0.0, "why": "퍼짐"},
    ]
    lines = nameaudit.report(rows, 400, already={"a1"})
    head = lines[0]
    assert "2곳" in head and "새로 걸린 곳 1" in head
    assert any("새로운학원" in x for x in lines)

    # 이미 표시된 곳은 **따로, 다른 말과 함께** 적는다.
    warn = [i for i, x in enumerate(lines) if "generic 인데 여전히" in x]
    assert warn, "조여 놓았는데도 퍼지면 그것이 신호다"
    assert any("테스트" in x for x in lines[warn[0]:])
    # 새로 걸린 곳이 먼저다 — 급한 것이 위에 온다.
    assert next(i for i, x in enumerate(lines) if "새로운학원" in x) < warn[0]


def test_걸리는_곳이_없으면_그렇게_적는다():
    assert "없음" in nameaudit.report([], 400, already=set())[0]


def test_형제_지점이_많은_브랜드는_퍼져_보이지_않는다():
    """넓이는 **그 이름 전체**를 세고 근거는 한 지점 몫이라, 그대로
    나누면 지점이 많은 유명 브랜드가 무조건 걸린다.

    실측에서 깊은생각(5.1배)·시대인재(4.8배)·한우리(4.5배)·시매쓰(4.4배)가
    그렇게 걸렸다 — 전부 멀쩡한 학원이고 그 글들은 형제 지점 이야기였다.
    같은 이름을 쓰는 학원의 근거를 모아서 견주면 사라진다(22곳 → 4곳).
    """
    corpus = [post(f"깊은생각 후기 {i}") for i in range(300)]
    academies = [academy(f"a{i}", "깊은생각") for i in range(4)]
    mentions = [mention(f"a{i}", f"깊은생각 후기 {j}")
                for i in range(4) for j in range(30)]
    cands = {f"a{i}": {"깊은생각"} for i in range(4)}

    assert nameaudit.measure(academies, mentions, corpus, cands) == []

    # 지점이 하나뿐이면 같은 숫자라도 걸린다 — 그때는 진짜 넓은 것이다.
    solo = nameaudit.measure(
        [academy("a0", "깊은생각")],
        [mention("a0", f"깊은생각 후기 {j}") for j in range(30)],
        corpus, {"a0": {"깊은생각"}})
    assert len(solo) == 1


def test_좁게_퍼진_이름도_제목으로_걸린다():
    """문턱(MIN_WIDE)은 **퍼짐 규칙의 것**이다. 제목 규칙까지 막으면 안 된다.

    실측: 모닝에듀(표본 13 · 제목 비율 0.08)는 근거 대부분이 에듀윌
    자격증 인강 글이었는데, 본문에 이름이 박힌 키워드 나열형 광고글이라
    코퍼스에 넓게 깔리지 않았다. 넓이 문턱에 막혀 이 점검을 통과했다.
    """
    # 이름이 코퍼스에 몇 건 없다 — 퍼짐으로는 못 잡는다.
    corpus = [post(f"에듀윌 소방시설관리사 인강 할인 {i}", "모닝에듀") for i in range(12)]
    mentions = [mention("a1", f"에듀윌 자격증 글 {i}") for i in range(12)]

    rows = nameaudit.measure(
        [academy("a1", "모닝에듀")], mentions, corpus, {"a1": {"모닝에듀"}})

    assert len(rows) == 1, "넓이가 작아도 제목 규칙으로 걸려야 한다"
    assert rows[0]["why"] == "제목에 이름 없음"
    assert rows[0]["wide"] < nameaudit.MIN_WIDE


def test_넓이가_작으면_퍼짐으로는_걸리지_않는다():
    """제목에 이름이 잘 나오면 좁게 퍼진 것은 문제가 아니다."""
    corpus = [post(f"가나학원 후기 {i}") for i in range(12)]
    mentions = [mention("a1", f"가나학원 후기 {i}") for i in range(10)]
    assert nameaudit.measure(
        [academy("a1", "가나학원")], mentions, corpus, {"a1": {"가나학원"}}) == []


def test_제목은_모든_표기로_본다():
    """대표 토큰 하나로만 재면 표기가 여럿인 학원이 통째로 오탐이 된다.

    실측: 렉스김어학원의 대표 토큰이 별칭 '렉스킴' 으로 잡혀 제목 비율이
    6% 로 나왔다 — 정작 제목에는 '렉스김' 으로 적혀 있었다. 근거 130건짜리
    멀쩡한 학원이 그렇게 걸렸다.
    """
    corpus = [post(f"렉스김 어학원 레테 후기 {i}") for i in range(40)]
    mentions = [mention("a1", f"렉스김 어학원 레테 후기 {i}") for i in range(30)]

    # 후보에 두 표기가 다 있다.
    rows = nameaudit.measure(
        [academy("a1", "렉스김어학원")], mentions, corpus,
        {"a1": {"렉스김", "렉스킴"}})
    assert rows == [], "제목에 다른 표기로 적혀 있으면 걸리면 안 된다"

    # 어느 표기도 제목에 없으면 그때는 걸린다.
    quiet = [mention("a1", f"공연 관람기 {i}") for i in range(30)]
    assert len(nameaudit.measure(
        [academy("a1", "렉스김어학원")], quiet, corpus,
        {"a1": {"렉스김", "렉스킴"}})) == 1


# ── 알림에서 질문으로 ─────────────────────────────────────────────
#
# 이 장치는 매 실행 "새로 걸린 곳 11" 을 찍었고 아무도 보지 않았다.
# 알림은 읽히지 않으면 없는 것과 같다.
def test_이름_위험은_답할_수_있는_질문이_된다():
    risky = [{"id": "a1", "name": "새로운학원", "region_id": "mokdong",
              "token": "새로운", "own": 24, "wide": 166, "spread": 5.1,
              "title_ratio": 0.04, "why": "퍼짐 · 제목에 이름 없음"}]
    qs = questions.generate(
        mentions=[], academies=[{"id": "a1", "name": "새로운학원",
                                 "region_id": "mokdong"}],
        generic={"a1": True}, verdicts={}, rules=[], name_risk=risky)
    q = [x for x in qs if x["kind"] == "name_risk"]
    assert len(q) == 1
    assert "새로운" in q[0]["question"] and "166" in q[0]["question"]
    # 답이 곧 frontmatter 다 — 세 갈래를 그대로 준다.
    assert {o["value"] for o in q[0]["options"]} == {"ok", "generic", "unusable"}
    # 이미 조여 놓았는데도 퍼지는 곳이 더 급하다.
    assert q[0]["priority"] > 60


def test_한_실행이_이름_위험을_두_건까지만_묻는다():
    """열한 건을 한꺼번에 물으면 그것도 다시 노동이다."""
    risky = [{"id": f"a{i}", "name": f"학원{i}", "region_id": "mokdong",
              "token": f"토큰{i}", "own": 10, "wide": 100, "spread": 10.0 - i,
              "title_ratio": 0.1, "why": "퍼짐"} for i in range(11)]
    qs = questions.generate(
        mentions=[], academies=[{"id": f"a{i}", "name": f"학원{i}"}
                                for i in range(11)],
        generic={}, verdicts={}, rules=[], name_risk=risky)
    assert len([x for x in qs if x["kind"] == "name_risk"]) == questions.NAME_RISK_LIMIT


def test_답은_위키_frontmatter_에_적히고_산문은_그대로다(tmp_path, monkeypatch):
    monkeypatch.setattr(wiki, "ACADEMY_DIR", tmp_path)
    page = tmp_path / "a1.md"
    page.write_text('---\nid: "a1"\nname: 새로운학원\n---\n# 새로운학원\n\n'
                    "사람이 쓴 산문. 엔진이 건드리면 안 된다.\n", encoding="utf-8")

    assert questions._write_flag("a1", "unusable") is True
    text = page.read_text(encoding="utf-8")
    assert "generic: true" in text and "unusable: true" in text
    assert "사람이 쓴 산문. 엔진이 건드리면 안 된다." in text
    # 두 번 적지 않는다.
    assert questions._write_flag("a1", "unusable") is False


def test_generic_답은_unusable_까지_적지_않는다(tmp_path, monkeypatch):
    """조이는 것과 모으지 않는 것은 다른 층이다."""
    monkeypatch.setattr(wiki, "ACADEMY_DIR", tmp_path)
    assert questions._write_flag("a2", "generic") is True
    text = (tmp_path / "a2.md").read_text(encoding="utf-8")
    assert "generic: true" in text and "unusable" not in text
