"""과목·학년 구간 판정 회귀 테스트.

과목을 잘못 정하면 그 학원이 **엉뚱한 랭킹에 실명으로 뜬다.** '아이엘이는
영어학원인데 국어 랭킹에 있다' 는 신고가 그렇게 들어왔고, 뿌리를 파 보니
827곳이 같은 상태였다.

★ 여기서 고칠 때마다 반대쪽이 무너졌다. 'general' 로 밀면 어느 랭킹에도
  안 나오고(표본 342건짜리가 화면에서 사라진다), 억지로 배정하면 없는
  사실을 만든다. 그래서 양쪽을 다 시험한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edutree import build, config                       # noqa: E402


def row(name: str, realm: str = "입시.검정 및 보습", course: str = "",
        **kw) -> dict:
    return {"name": name, "realm_sc_nm": realm,
            "le_crse_list_nm": course, "le_crse_nm": kw.get("crse", ""),
            "id": kw.get("id", name)}


# ── 이름이 가장 정확한 신호다 ────────────────────────────────────
def test_이름의_과목이_시드_과목보다_구체적이다():
    """'시대인재수학스쿨' 이 시드 '시대인재'(국영수과)로 단정돼 과학 랭킹
    3위에 올랐다 — 이름이 수학 전문이라고 말하는데도."""
    assert build._subjects_from_name(row("시대인재수학스쿨학원")) == ["math"]


def test_보습_논술은_과목_선언이_아니다():
    """NEIS 보습학원의 기본 등록값이 '보습·논술' 이고, 거기 '논술' 이 국어
    힌트에 걸려 **827곳이 국어 학원**이 됐다(시대인재·러셀·두각·황소…)."""
    got = build._infer_subjects(row("대치대성학원", course="보습·논술"))
    assert got == [config.UNRANKED_SUBJECT]


def test_과목을_못_정한_학술_학원은_어느_랭킹에도_안_넣는다():
    """'etc' 로 두면 예체능·기타 랭킹에 학술 학원이 섞인다 —
    '대치수능선배2관학원' 이 기타 랭킹에 떴다."""
    got = build._infer_subjects(row("대치수능선배2관학원", course="보습"))
    assert got == [config.UNRANKED_SUBJECT] != ["etc"]


def test_공시_분야가_예체능이면_이름의_과목어보다_우선한다():
    """'아담리즈수학대치센터학원' 은 이름에 수학이 있어도 공시가 '기타(대)'
    라 그대로 둔다. 학원이 그렇게 등록했다."""
    assert build._infer_subjects(row("아담리즈수학대치센터학원", "기타(대)")) == ["etc"]


def test_학술_이름이_예체능_힌트를_이긴다():
    """'수영수학교습소' 가 '수영' 때문에 예체능이 됐다."""
    assert build._infer_subjects(row("수영수학교습소")) == ["math"]


# ── ★ 이 리뷰에서 찾은 것: 과목어가 낱말에 걸쳐 생긴다 ───────────
def test_재수학원은_수학_학원이_아니다():
    """'독학**재수학원**' 에 '수학' 이 들어 있어 재수 학원 19곳이 수학
    학원이 됐다. 부분 문자열은 형태소 경계를 모른다."""
    assert "math" not in build._infer_subjects(row("잇올스파르타독학재수학원",
                                                   course="보습"))
    assert "math" not in build._infer_subjects(row("대치720재수학원",
                                                   course="보습"))


def test_인재수학스쿨은_여전히_수학이다():
    """'시대인**재수학**스쿨' 은 '인재' + '수학' 이다. '재수학원' 이 아니므로
    이음매를 갈라도 수학이 남아야 한다 — 고치다 이쪽을 깨면 안 된다."""
    assert build._subjects_from_name(row("시대인재수학스쿨학원")) == ["math"]
    assert "math" in build._infer_subjects(row("미래영재수학교습소"))
    assert "math" in build._infer_subjects(row("자유자재수학보습학원"))


def test_국어학원은_영어_학원이_아니다():
    """'권미나**국어학원**' 에 '어학' 이 들어 있어 국어 학원 65곳이 영어
    학원으로도 분류됐다."""
    got = build._infer_subjects(row("권미나국어학원"))
    assert got == ["korean"]


def test_진짜_어학원은_영어로_남는다():
    assert "english" in build._infer_subjects(row("우승희영어학원"))
    assert "english" in build._infer_subjects(row("윌로우잉글리쉬외국어학원"))


def test_실용외국어는_국어가_아니다():
    """9/5 신고: '그로튼아카데미는 영어학원인데 국어 3위에 있다'.

    NEIS 표준 교습과정 '실용외국어' 안에 **'국어' 가 부분 문자열**로 들어
    있다. `_infer_subjects` 에 '외국어 → english' 규칙이 이미 있는데,
    그 앞의 교습과정 힌트 검사에서 '국어' 가 먼저 걸려 거기까지 가지
    못했다. 전수 74건 · 그중 25곳이 실제 국어 랭킹에 있었다
    (반포 국어 1·2위, 대치 3위).
    """
    grotten = row("그로튼아카데미학원", realm="종합(대)",
                  course="실용외국어(유아/초·중·고)")
    assert build._infer_subjects(grotten) == ["english"]

    # 중국어·일본어 교습소도 같은 자리에서 국어가 됐다.
    for name, realm in (("대치해법중국어교습소", "국제화"),
                        ("동경일본어교습소", "국제화"),
                        ("밍중국어교습소", "입시.검정 및 보습")):
        got = build._infer_subjects(row(name, realm=realm,
                                        course="실용외국어(유아/초·중·고)"))
        assert "korean" not in got, (name, got)

    # 공시가 '국제화' 면 이름의 '언어' 한 낱말로 국어를 붙이지 않는다.
    forty = row("포티언어학원", realm="국제화", course="실용외국어(유아/초·중·고)")
    assert build._infer_subjects(forty) == ["english"]


def test_진짜_국어_학원은_그대로_국어다():
    """반대쪽을 깨지 않는지. 이 셋은 이름이 국어라고 말한다."""
    for name in ("권미나국어학원", "기파랑문해원", "예섬독서논술학원"):
        assert "korean" in build._infer_subjects(
            row(name, course="보습·논술")), name


def test_과학논술은_국어가_아니다():
    """앞말이 뒷말을 한정한다. '과학논술' 은 과학 글쓰기이지 국어 논술이 아니다."""
    assert build._infer_subjects(row("주광호샘네모과학논술교습소")) == ["science"]
    assert build._infer_subjects(row("김정훈수리논술교습소")) == ["math"]


# ── 학년 구간 ────────────────────────────────────────────────────
def test_빈_구간은_모든_구간에_단계를_붙인다():
    """★ 가장 크게 샜던 곳. 앱의 필터는 빈 구간을 '한정되지 않음' 으로
    읽는데 _auto_stages 는 '해당 구간 없음' 으로 읽어 단계를 하나도 안
    붙였다. 등록부 6,092곳 중 4,771곳(78%)이 여기 해당했다."""
    stages, _ = build._auto_stages({"subjects": ["math"], "grade_bands": [],
                                    "name": "가나수학학원"})
    assert stages, "빈 grade_bands 는 '아무 구간도 아님' 이 아니다"


def test_단서가_없으면_대표_단계_하나에만_붙인다():
    """단서 없는 학원을 해시로 흩뿌리던 것을 없앴다 — 실명 사업자를 근거
    없이 '영재고 대비 학원' 이라고 적은 셈이었다(3,000건+)."""
    stages, basis = build._auto_stages(
        {"subjects": ["math"], "grade_bands": ["elem_high"], "name": "가나수학학원"})
    assert len(stages) == 1
    assert basis[stages[0]] == "inferred"


def test_대표_단계는_가장_넓은_곳이지_가장_높은_곳이_아니다():
    """초4~6 수학의 대표가 '경시·심화' 라 단서 없는 941곳이 경시 학원이
    됐다(잠실 경시 목록에 '청진컴퓨터교습소' 가 있었다)."""
    assert build._STAGE_DEFAULT[("math", "elem_high")] == "math_el_basic"
    assert build._STAGE_DEFAULT[("science", "elem_high")] == "sci_el_lab"


def test_단서가_있으면_그_단계로_좁히고_근거를_남긴다():
    stages, basis = build._auto_stages(
        {"subjects": ["math"], "grade_bands": ["elem_high"],
         "name": "가나올림피아드수학학원"})
    assert "math_el_competition" in stages
    assert basis["math_el_competition"] == "hinted"


# ── 성인 직업·전문 학원 ──────────────────────────────────────────
def test_성인_직업_학원은_등록부에서_뺀다():
    """'반포 기타 고등' 목록이 성인 학원으로 채워졌다."""
    assert config.is_vocational(row("김영편입학원", "종합(대)")) is True
    assert config.is_vocational(row("스카이항공승무원학원", "기타(대)")) is True


def test_뷰티풀마인드는_미용학원이_아니다():
    """'뷰티' 를 낱말 목록에 넣으면 뷰티풀마인드수학학원이 사라진다.
    낱말 하나 차이로 멀쩡한 학원이 없어진다."""
    assert config.is_vocational(row("뷰티풀마인드수학학원")) is False


# ── 영유 연차 표시 ────────────────────────────────────────────────
#
# 신고(2026-09-05): '영유 2년차·3년차 대상의 초등 저학년 학원이 있으니
# 뱃지를 달아 달라'. NEIS 공시에는 없고 후기에만 있는 사실이다.
def test_영유_연차는_이름_근처에서만_센다():
    from edutree import analyze
    names = {analyze._norm("트윈클")}
    near = "대치동 초1, 영유3년차 영어학원 어디로? 트윈클 어떤가요"
    assert analyze.entry_tags_near(near, names) == {"eng_kinder_3y"}

    # 이름에서 먼 자리의 낱말은 그 학원 이야기가 아니다.
    far = ("영유 3년차 아이 키우는 이야기입니다. " + "그냥 잡담 " * 20
           + "트윈클은 나중에 알아볼게요")
    assert analyze.entry_tags_near(far, names) == set()

    # 이름이 없으면 아무것도 아니다.
    assert analyze.entry_tags_near(near, {analyze._norm("가나")}) == set()


def test_연차를_알면_출신보다_구체적이다():
    from edutree import analyze
    names = {analyze._norm("트윈클")}
    both = "트윈클 영유출신 영유3년차 아이들이 많아요"
    assert analyze.entry_tags_near(both, names) == {"eng_kinder_3y"}


def test_영유_표시는_작성자_둘_이상이_말해야_붙는다():
    """한 사람 말은 아직 한 사람 말이다 — 진입난이도 확인율과 같은 규칙."""
    a = {"id": "A", "name": "트윈클어학원", "subjects": ["english"],
         "brand": None, "aliases": []}
    def m(author):
        return {"academy_key": "A", "author_hash": author,
                "title": "트윈클 후기", "snippet": "영유 3년차 아이가 다녀요"}
    one = build.entry_tags_from_mentions([dict(a)], {"A": [m("u1")]}, {})
    assert one == 0, "한 사람이면 안 붙는다"

    acad = dict(a)
    build.entry_tags_from_mentions([acad], {"A": [m("u1"), m("u2")]}, {})
    assert acad["entry_tags"] == ["eng_kinder_3y"]


def test_영유_표시는_영어_학원에만_붙는다():
    """영유는 영어유치원이다. '영유 3년차인데 수학은…' 은 그 아이 이야기다."""
    math = {"id": "B", "name": "가나수학학원", "subjects": ["math"],
            "brand": None, "aliases": []}
    rows = {"B": [{"academy_key": "B", "author_hash": f"u{i}",
                   "title": "가나수학학원 후기",
                   "snippet": "영유 3년차인데 수학은 여기 다녀요"} for i in range(3)]}
    assert build.entry_tags_from_mentions([math], rows, {}) == 0


def test_네이버_업종이_과목을_말하면_모르는_곳만_채운다():
    """MSC 신고. 교습과정이 '보습·논술' 뿐이라 과목 미상이었는데,
    네이버 업종은 '교육,학문>논술' 이라고 분명히 말한다."""
    rows = [
        {"subjects": ["general"], "place_category": "교육,학문>논술"},
        {"subjects": ["general"], "place_category": "교습학원,교습소>수학교육"},
        # 업종 전부가 갖는 값은 신호가 아니다 — '보습·논술' 과 같은 처지다.
        {"subjects": ["general"], "place_category": "교습학원,교습소>입시교육"},
        # 이미 아는 곳은 덮지 않는다.
        {"subjects": ["math"], "place_category": "교육,학문>논술"},
    ]
    assert build.subjects_from_category(rows) == 2
    assert [r["subjects"] for r in rows] == [
        ["korean"], ["math"], ["general"], ["math"]]


# ── 못 찾은 조회는 오래 붙들지 않는다 ─────────────────────────────
def test_질의어가_늘면_다시_묻는다(tmp_path, monkeypatch):
    """MSC 를 위키 aliases 로 이어 놓고 다음 회차를 돌렸는데 여전히 과목
    미상이었다. 앞 회차에서 **등록명으로 물어 못 찾은 결과**가 캐시에 남아
    90일간 다시 묻지 않았기 때문이다 — 고친 보람이 90일 뒤에나 온다."""
    import json as _json
    from datetime import date
    from edutree import official
    cache = tmp_path / "local_lookup.json"
    monkeypatch.setattr(official, "CONTACT_CACHE", cache)
    cache.write_text(_json.dumps({
        "A": {"checked": date.today().isoformat(), "tried": ["엠에스씨학원"]},
    }), encoding="utf-8")

    from edutree import naver as _naver
    asked = []
    monkeypatch.setattr(_naver, "local_lookup",
                        lambda n, a, al=(): asked.append((n, al)) or None)

    row = {"id": "A", "name": "엠에스씨학원", "road_address": "서울 양천구 목동서로 349",
           "lookup_aliases": ("MSC",), "tel": None}
    official.lookup_contacts([row], live=True, limit=5)
    assert asked, "별칭이 늘었으면 다시 물어야 한다"

    # 같은 표기로 이미 물었고 찾았으면 다시 묻지 않는다.
    cache.write_text(_json.dumps({
        "A": {"checked": date.today().isoformat(),
              "tried": ["엠에스씨학원", "MSC"], "link": "https://x"},
    }), encoding="utf-8")
    asked.clear()
    official.lookup_contacts([row], live=True, limit=5)
    assert not asked, "찾았고 표기도 그대로면 다시 묻지 않는다"
