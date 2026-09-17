"""관련성 게이트 · 근거 발췌 · 언급 저장소 회귀 테스트.

2026-09-02 전수 점검에서 드러난 오귀속 사례를 그대로 굳혔다. 화면에 걸린
근거 532건 중 22건이 학원 이름을 품지 않았고, 원인은 넷이었다:
발췌 위치(앞 120자), 이름 후보의 중복 세기, 남의 이름 목록의 일반어,
두 글자 별칭. 여기 있는 사례가 다시 통과하면 그 원인이 되살아난 것이다.
"""
from __future__ import annotations

import json

import pytest

from edutree import analyze, evidence, mention_store


def _n(text: str) -> str:
    return analyze._norm(text)


# ── 이름 자리 ─────────────────────────────────────────────────────
def test_이름_후보가_겹쳐도_한_자리는_한_번만_센다():
    """'김선희꼼꼼국어교습소' 와 그 알맹이 '김선희꼼꼼국어' 는 같은 자리다.
    예전에는 후보마다 count() 를 더해 2 가 됐고, 그 부풀린 수가
    '내 이름은 한 번뿐' 판정을 무력화해 학원 수십 곳을 늘어놓은
    '송파구 교습소 정보 총정리' 가 근거로 통과했다."""
    cands = analyze.name_candidates({"name": "김선희꼼꼼국어교습소"})
    assert "김선희꼼꼼국어" in cands and "김선희꼼꼼국어교습소" in cands
    blob = _n("송파구 교습소 총정리 … 김선희꼼꼼국어교습소 02-000 … 다른교습소")
    assert analyze.name_occurrences(blob, cands) == 1


def test_두_글자_이름은_학원_표지가_곁에_있을_때만_이름이다():
    """'정상인가요' 의 '정상' 은 학원이 아니다. '정상어학원'·'정상반'·
    '정상 레테' 는 학원이다."""
    cands = {"정상", "정상어학원"}
    assert analyze.name_spans(_n("학원비가 이게 정상인가요"), cands) == []
    assert analyze.name_spans(_n("시대가 바뀌었다"), {"시대", "시대인재"}) == []
    assert len(analyze.name_spans(_n("정상어학원 다녀요"), cands)) == 1
    assert len(analyze.name_spans(_n("우리 애는 정상반이에요"), cands)) == 1
    assert len(analyze.name_spans(_n("정상 레테 봤어요"), cands)) == 1
    assert len(analyze.name_spans(_n("청담동 카페"), {"청담", "청담어학원"})) == 0
    # 세 글자부터는 그대로 인정한다.
    assert len(analyze.name_spans(_n("시대인재 다녀요"), {"시대", "시대인재"})) == 1


def test_match_info_는_제목_언급과_본문_첫_자리를_말한다():
    info = analyze.match_info(
        {"title": "ILE 대치 입학테스트 후기", "snippet": "오늘 ILE 레테를 봤다. ILE 는…"},
        {"ile", "아이엘이"})
    assert info["in_title"] is True
    assert info["count"] == 3
    assert info["first_body"] == 2         # '오늘' 다음


# ── 남의 학원 이름 ────────────────────────────────────────────────
def test_일반어만_남는_이름은_남의_학원이_못_된다():
    """실측: '동영어'(제목 2,711건) · '테스트'(1,815) · '원수학' 이 남의 학원
    행세를 했다. 'OO동영어학원' 의 알맹이, '테스트교습소' 의 알맹이다."""
    for junk in ("동영어", "테스트", "원수학", "고수학", "수학교습소",
                 "대치동영어", "스터디", "피아노"):
        assert not analyze.rival_eligible(junk), junk
    for real in ("시대인재", "청담어학", "와이즈만영재교육", "한우리", "깊은생각",
                 "이맥스", "트윈클", "캔비어학원"):
        assert analyze.rival_eligible(real), real


def test_남의_이름_색인은_전수_비교와_같은_답을_낸다():
    names = {"캔비어학원", "시대인재", "청담어학원", "폴리어학원", "소마"}
    idx = analyze.RivalIndex(names)
    for text in ("캔비어학원 레벨테스트 후기 시대인재도 봤다",
                 "폴리어학원 vs 청담어학원", "아무 학원도 없는 글", ""):
        flat = _n(text)
        assert idx.find(flat) == {r for r in names if r in flat}
    assert len(idx) == 5 and "소마" in idx and bool(idx)


# ── 관련성 게이트 ─────────────────────────────────────────────────
POLY = {"폴리어학원", "송파폴리어학원", "폴리"}
RIVALS = analyze.RivalIndex({"캔비어학원", "청담어학원", "청담", "시대인재",
                             "에이프릴어학원", "정상어학원", "리드101"})


def test_제목의_주인공이_남이고_나는_한_번_스칠_뿐이면_남의_글이다():
    """실측: '캔비어학원 레벨테스트 엄마표영어 초3 테스트 후기' 가 본문의
    '폴리어학원' 한 마디로 송파폴리어학원의 근거였다."""
    m = {"title": "캔비어학원 레벨테스트 엄마표영어 초3 테스트 후기",
         "snippet": "폴리어학원 다니다가 캔비로 옮겼어요. 캔비 동대문캠퍼스 레테는…"}
    assert analyze.is_relevant(m, POLY, False, RIVALS) is False


def test_제목의_주인공이_남이라도_본문에서_나를_여러_번_말하면_비교글이다():
    m = {"title": "청담어학원 후기",
         "snippet": "청담 다니다 폴리로 옮겼는데 폴리 숙제가 많다. 폴리 선생님은 좋다."}
    assert analyze.is_relevant(m, POLY, False, RIVALS) is True


def test_제목에_내_이름이_있으면_남의_이름이_함께_있어도_내_글이다():
    m = {"title": "청담 vs 폴리 고민", "snippet": "둘 다 레테 봤어요."}
    assert analyze.is_relevant(m, POLY, False, RIVALS) is True
    assert analyze.is_relevant(m, {"청담어학원", "청담"}, False, RIVALS) is True


def test_제목에_남의_학원이_둘_이상이면_나열이다():
    m = {"title": "청담어학원 에이프릴어학원 정상어학원 비교",
         "snippet": "폴리어학원도 있고요."}
    assert analyze.is_relevant(m, POLY, False, RIVALS) is False


def test_본문에_학원이_잔뜩인데_나는_한_번뿐이면_목록글이다():
    m = {"title": "대치 영어학원 총정리",
         "snippet": "청담어학원, 에이프릴어학원, 정상어학원, 폴리어학원, 리드101 순서로…"}
    assert analyze.is_relevant(m, POLY, False, RIVALS) is False
    m2 = {"title": "대치 영어학원 총정리",
          "snippet": "청담어학원, 에이프릴어학원, 정상어학원 중 폴리어학원이 최고. 폴리 숙제 많음. 폴리 강추."}
    assert analyze.is_relevant(m2, POLY, False, RIVALS) is True


def test_긴_글에서_이름이_한_번_그것도_뒤늦게_나오면_다른_이야기다():
    """실측: 부동산 기사 '[강남 대치] 학원 1만 개, 재건축 10조' 가 본문
    중간의 '시대인재' 한 마디로 시대인재수학스쿨의 근거였다."""
    filler = "대치동 아파트 재건축 이야기가 길게 이어진다. " * 40
    late = {"title": "[강남 대치] 학원 1만 개, 재건축 10조",
            "snippet": filler + "밤 10시 시대인재 앞 정류장이 붐빈다. " + filler}
    assert len(_n(late["snippet"])) > analyze.LONG_TEXT
    assert analyze.is_relevant(late, {"시대인재수학스쿨", "시대인재"}, False, RIVALS) is False
    # 앞머리에서 바로 이름을 말하면 그 글의 주제다.
    early = {"title": "레테 후기", "snippet": "시대인재 레테를 봤다. " + filler}
    assert analyze.is_relevant(early, {"시대인재수학스쿨", "시대인재"}, False, RIVALS) is True
    # 짧은 카페 스니펫에는 이 규칙이 걸리지 않는다.
    short = {"title": "질문", "snippet": "혹시 시대인재 어떤가요"}
    assert analyze.is_relevant(short, {"시대인재수학스쿨", "시대인재"}, False, RIVALS) is True


def test_일상어_이름은_제목의_주인공이_남이면_횟수와_무관하게_버린다():
    m = {"title": "기파랑 레벨테스트를 치고",
         "snippet": "책읽기를 좋아하고 책읽기 학원도 알아봤다. 책읽기 선생님…"}
    assert analyze.is_relevant(m, {"책읽기"}, True, analyze.RivalIndex({"기파랑"})) is False


def test_깊은생각은_구_전체가_일상어라_학원_표지를_요구한다():
    assert analyze.is_generic_name("깊은생각학원") is True
    assert analyze.is_generic_name("깊은생각256학원") is False
    assert analyze.is_generic_name("생각하는황소학원") is False
    m = {"title": "삼시세끼 꼬마김밥 솔직 후기", "snippet": "깊은 생각 없이 들어갔는데 맛있었다."}
    assert analyze.is_relevant(m, {"깊은생각"}, True, RIVALS) is False
    ok = {"title": "대치 깊은생각 레테 후기", "snippet": "깊은생각 레벨테스트 봤어요."}
    assert analyze.is_relevant(ok, {"깊은생각"}, True, RIVALS) is True


# ── 발췌 ──────────────────────────────────────────────────────────
def test_발췌는_이름이_나온_자리를_중심으로_자른다():
    body = ("앞부분은 다른 이야기입니다. 날씨가 좋았어요. " * 6
            + "그러다가 우리 아이가 폴리어학원에 등록했어요. 레테는 어려웠고요. "
            + "뒤 이야기가 한참 이어집니다. " * 14)
    ex = evidence.excerpt({"title": "영어 고민", "snippet": body}, POLY)
    assert "폴리어학원" in ex["text"]
    assert ex["text"].startswith("…") and ex["text"].endswith("…")
    assert len(ex["text"]) <= evidence.EXCERPT_WIDTH + 80
    assert ex["in_title"] is False and ex["count"] == 1


def test_이름이_제목에만_있으면_본문_앞머리를_문장_단위로_쓴다():
    ex = evidence.excerpt(
        {"title": "폴리어학원 레테 후기", "snippet": "오늘 시험을 봤다. 결과는 다음 주. 기다린다."},
        POLY)
    assert ex["in_title"] is True
    assert ex["text"].startswith("오늘 시험을 봤다")


def test_근거_고르기는_제목_언급을_앞세우고_같은_원문은_한_번만():
    rows = [
        {"url_hash": "a", "title": "잡담", "snippet": "폴리어학원 이야기 잠깐",
         "credibility": 0.9, "substance": 1},
        {"url_hash": "b", "title": "폴리어학원 레테 후기", "snippet": "폴리 레테 봤다. 폴리 어려움.",
         "credibility": 0.6, "substance": 2},
        {"url_hash": "b", "title": "폴리어학원 레테 후기", "snippet": "폴리 레테 봤다. 폴리 어려움.",
         "credibility": 0.6, "substance": 2},
        {"url_hash": "c", "title": "광고", "snippet": "폴리어학원 상담문의",
         "credibility": 0.1, "is_excluded": True},
    ]
    chosen = evidence.select(rows, POLY)
    hashes = [m["url_hash"] for _i, m in chosen]
    assert hashes == ["b", "a"]                    # 제목 언급이 먼저, 배제 글 없음
    out = evidence.export_rows(chosen, POLY)
    assert [e["ref"] for e in out] == [1, 2]
    assert out[0]["in_title"] is True and out[0]["mentions"] >= 3
    assert all("폴리" in e["snippet"] or e["in_title"] for e in out)


def test_관점_프로필은_두_건부터_낸다():
    rows = [
        {"aspects": {"관리": 0.8, "숙제량": -0.5}, "credibility": 0.9},
        {"aspects": {"관리": 0.4}, "credibility": 0.5},
        {"aspects": {"숙제량": -0.7}, "credibility": 0.5, "is_excluded": True},
    ]
    prof = evidence.aspect_profile(rows)
    assert set(prof) == {"관리"}
    assert prof["관리"]["n"] == 2 and prof["관리"]["positive"] == 2
    assert 0.4 < prof["관리"]["mean"] < 0.8 and prof["관리"]["label"] == "관리·피드백"


def test_품질_감사는_발췌에_이름이_있는_줄을_센다():
    payload = [{
        "name": "폴리어학원", "brand": None, "aliases": ["폴리"],
        "evidence": [
            {"title": "폴리어학원 후기", "snippet": "좋았다", "in_title": True},
            {"title": "잡담", "snippet": "아무 말", "in_title": False},
        ]}, {"name": "없음", "evidence": []}]
    q = evidence.audit(payload)
    assert q == {"academies": 2, "withEvidence": 1, "rows": 2,
                 "nameInExcerpt": 1, "inTitle": 1, "spacedName": 0,
                 "basis": {"direct": 2}}


def test_품질_감사는_이름이_띄어_쓰인_발췌를_따로_센다():
    """'이름 포함' 만 세면 만점이 나온다 — 정규화가 공백을 지우기 때문이다.

    9/3 실측: 발췌 1,309건 중 '이름 포함' 이 1,309건(만점)이었는데 그중
    셋은 '새로운 학원' 이라는 구였다. 게이트를 고쳐도 이 지표로는
    나빠지는 순간을 볼 수 없었다.
    """
    payload = [{
        "name": "새로운학원", "brand": None, "aliases": [],
        "evidence": [
            {"title": "초보 강사, 새로운 학원 제안", "snippet": "조교로 근무",
             "in_title": True},
            {"title": "새로운학원 레벨테스트 후기", "snippet": "원장님 상담",
             "in_title": True},
        ]}]
    q = evidence.audit(payload)
    assert q["nameInExcerpt"] == 2, "옛 지표로는 둘 다 '이름 포함' 이다"
    assert q["spacedName"] == 1, "구(句)로 걸린 발췌가 따로 세어져야 한다"


# ── 언급 저장소 ───────────────────────────────────────────────────
@pytest.fixture
def store_path(tmp_path, monkeypatch):
    p = tmp_path / "mention_store.json.gz"
    monkeypatch.setattr(mention_store, "PATH", p)
    return p


def _m(h, key, snippet="s", **kw):
    return {"url_hash": h, "academy_key": key, "source": "naver_cafe",
            "source_url": f"https://x/{h}", "title": "t", "snippet": snippet, **kw}


def test_저장소는_새_글을_더하고_옛_글을_잃지_않는다(store_path):
    day1 = mention_store.merge([_m("h1", "A"), _m("h2", "A")], today="2026-09-01", quiet=True)
    assert len(day1) == 2 and all(r["first_seen"] == "2026-09-01" for r in day1)
    # 다음 회차: A 는 안 뽑히고 B 만 수집됐다. A 의 근거는 그대로 남는다.
    day2 = mention_store.merge([_m("h3", "B"), _m("h1", "A", snippet="더 긴 스니펫이다")],
                               today="2026-09-02", quiet=True)
    by = {(r["url_hash"], r["academy_key"]): r for r in day2}
    assert set(by) == {("h1", "A"), ("h2", "A"), ("h3", "B")}
    assert by[("h1", "A")]["snippet"] == "더 긴 스니펫이다"     # 긴 쪽을 남긴다
    assert by[("h1", "A")]["first_seen"] == "2026-09-01"
    assert by[("h1", "A")]["last_seen"] == "2026-09-02"
    assert by[("h2", "A")]["last_seen"] == "2026-09-01"
    assert mention_store.academy_keys() == {"A", "B"}


def test_저장소는_분석_결과와_데모_글을_저장하지_않는다(store_path):
    rows = mention_store.merge([
        _m("h1", "A", sentiment=0.9, credibility=0.8, is_excluded=True),
        _m("h9", "Z", is_demo=True)], quiet=True)
    assert len(rows) == 1 and "sentiment" not in rows[0] and "is_excluded" not in rows[0]


def test_저장소는_학원당_상한을_넘기면_오래_못_본_것부터_뺀다(store_path, monkeypatch):
    monkeypatch.setattr(mention_store, "KEEP_PER_ACADEMY", 3)
    mention_store.merge([_m(f"h{i}", "A") for i in range(3)], today="2026-08-01", quiet=True)
    rows = mention_store.merge([_m("new", "A")], today="2026-09-01", quiet=True)
    assert len(rows) == 3 and any(r["url_hash"] == "new" for r in rows)


def test_깨진_저장소는_빈_것으로_읽는다(store_path):
    store_path.write_bytes(b"not gzip")
    assert mention_store.load() == {}
    store_path.write_bytes(b"")
    assert mention_store.rows() == []


# ── 2026-09-02 재빌드 뒤 남은 것 셋 ───────────────────────────────
def test_업종어가_잔뜩인_목록글은_등록부_밖_학원만_늘어놓아도_잡는다():
    """'보령 동대동 영수과외' 글의 '시대인재2관학원' 한 마디. 남의 이름
    색인은 등록부(4개 학군)만 알아서 못 걸렀다."""
    listing = ("보령 동대동 죽정동 영수과외 수학과외 영어과외 … 와이수학전문학원 "
               "시대인재2관학원 이길동수학영어학원 한빛학원 청람교습소 대성학원 "
               "샘물어학원 명문학원 으뜸교습소 하나학원")
    m = {"title": "보령 동대동 죽정동 영수과외 수학과외 영어과외", "snippet": listing}
    assert analyze.is_relevant(m, {"시대인재수학스쿨", "시대인재"}, False, RIVALS) is False
    # 보통 후기는 '학원' 을 서너 번 쓴다 — 걸리지 않는다.
    ok = {"title": "레테 후기", "snippet": "시대인재 학원 레테 봤어요. 학원 분위기 좋고 다른 학원보다 낫네요."}
    assert analyze.is_relevant(ok, {"시대인재수학스쿨", "시대인재"}, False, RIVALS) is True


def test_브랜드_별칭이_일상어면_학원_표지를_요구한다():
    a = {"name": "한우리독서토론논술교습소", "brand": "한우리", "aliases": ["한우리"]}
    assert analyze.is_generic_academy(a) is True
    assert analyze.is_generic_academy({"name": "시매쓰학원", "brand": "시매쓰"}) is False
    m = {"title": "[서울 목동 현대백화점] 한우리 목동샤브샤브 맛집",
         "snippet": "한우리 HANWOORY 목동현대백화점 소고기 샤브샤브"}
    assert analyze.is_relevant(m, {"한우리독서토론논술교습소", "한우리"}, True, RIVALS) is False


def test_강남점_홍대점은_다른_지점이다():
    ours, other = analyze.region_hints("아트아뜰리에 강남점 후기")
    assert ours == {"daechi"} and other is False
    ours, other = analyze.region_hints("홍대 성인취미미술 아트아뜰리에")
    assert other is True


def test_일상어_이름의_표지는_이름_곁에_있어야_한다():
    """블로그 본문 2,000자 어딘가의 '지점' 한 마디로 샤브샤브 글이 통과했다."""
    far = ("한우리 HANWOORY 목동현대백화점 소고기 샤브샤브 맛집. " + "고기가 부드럽고 국물이 진하다. " * 30
           + "근처 학원 끝난 아이들도 많이 온다. 지점이 여럿이다.")
    m = {"title": "[서울 목동 현대백화점] 한우리 목동샤브샤브 맛집", "snippet": far}
    assert analyze.is_relevant(m, {"한우리독서토론논술교습소", "한우리"}, True, RIVALS) is False
    near = {"title": "목동 한우리 독서논술 후기", "snippet": "한우리 다닌 지 1년, 선생님이 꼼꼼해요."}
    assert analyze.is_relevant(near, {"한우리독서토론논술교습소", "한우리"}, True, RIVALS) is True


def test_총정리_제목과_업소_명부는_짧은_스니펫이라도_잡는다():
    m = {"title": "송파구 교습소 정보 총정리 ( ㄱ~ㅅ )",
         "snippet": "…검정 및 보습 김선희꼼꼼국어교습소 서울 송파구 위례성대로12길 34"}
    cands = analyze.name_candidates({"name": "김선희꼼꼼국어교습소"})
    assert analyze.is_relevant(m, cands, False, RIVALS) is False
    m2 = {"title": "송파구 교습소 정보",
          "snippet": "02-000-0000 김선희꼼꼼국어교습소 위례성대로12길 34 02-415-4193 김성은영어교습소"}
    assert analyze.is_relevant(m2, cands, False, RIVALS) is False
    # 내 이름이 제목에 있으면 목록글이라도 내 글이다.
    ok = {"title": "김선희꼼꼼국어교습소 후기 총정리", "snippet": "다닌 지 2년."}
    assert analyze.is_relevant(ok, cands, False, RIVALS) is True


def test_일상어_이름_곁에_가게_말이_있으면_그_자리는_학원이_아니다():
    """실측 원문: '…한우리 HANWOORY 목동현대백화점 25년지기 우리가 활보했던 곳
    하교 후 방앗간처럼 근처 학원을 다녔기 때문에' — 학원 이야기가 40자 뒤에 온다."""
    body = ("서울 목동 현대백화점 한우리 목동샤브샤브 현대백화점 맛집. 현대백화점 목동점 나의 10대 "
            "20대 모든 추억이 묻어있는 이곳 오목교 그때 그 시절 늘 함께했던 친구들과의 만남 "
            "한우리 HANWOORY 목동현대백화점 25년지기 우리가 활보했던 곳 하교 후 방앗간처럼 "
            "근처 학원을 다녔기 때문에 자주 왔다. " + "고기가 부드럽다. " * 40)
    m = {"title": "[서울 목동 현대백화점] 한우리 목동샤브샤브 맛집", "snippet": body}
    assert analyze.is_relevant(m, {"한우리독서토론논술교습소", "한우리"}, True, RIVALS) is False


# ── 교재 문맥 (2026-09-13, ma-26091319-2) ──────────────────────────
#
# 사고력 브랜드는 출판사를 겸한다. 시매쓰 네이버 재조회 957건 중 게이트를
# 지난 685건의 37% 가 교재 글이었다. 이름 곁에 교재 표지가 있고 학원 표지는
# 어느 곁에도 없으면 문제집 이야기다 — 브랜드를 가리지 않는다.
_CMATH = {"사고력수학시매쓰학원", "사고력수학시매쓰", "시매쓰", "시매쓰수학"}


def test_출판사_교재평가_글은_학원_근거가_아니다():
    """cmath_rows 원문. '[교재평가]시매쓰/1학년/수학/영리한수학1'."""
    m = {"title": "[교재평가]시매쓰/1학년/수학/영리한수학1",
         "snippet": "출판사 : 시매쓰 6. 가격 : 14000원 * 평가 항목 * 1) 회원님이 느끼는 "
                    "교재의 난이도는? 중 … 구입처 : 대치동 서점"}
    assert analyze.is_relevant(m, _CMATH, False, RIVALS) is False
    m = {"title": "시매쓰출판 16기 서포터즈 모집(~3/3)",
         "snippet": "서포터즈 활동 혜택 - 체험 교재 4권 증정 - 시매쓰출판 서포터즈 기념 선물"}
    assert analyze.is_relevant(m, _CMATH, False, RIVALS) is False
    m = {"title": "6~7세 시매쓰교재 판매할께요~",
         "snippet": "새책입니다..구겨진곳도 없어요.. 상위권연산 960 각권 정가 8000원(2012년인쇄)"}
    assert analyze.is_relevant(m, _CMATH, False, RIVALS) is False


def test_교재_규칙은_브랜드를_가리지_않는다():
    """소마·CMS 도 교재를 낸다(소마셈·CMS 영재사고력). 원문이 캐시에 없어
    카페 교재평가 템플릿 꼴로 지어 굳힌다."""
    soma = {"소마사고력수학학원", "소마사고력수학", "소마"}
    m = {"title": "[교재평가]소마/초1/수학/소마셈 A1",
         "snippet": "문제집 이름 : 소마셈 A1 5. 출판사 : 소마 6. 가격 : 9000원"}
    assert analyze.is_relevant(m, soma, False, RIVALS) is False
    # 같은 이름이 학원 후기에서 '소마셈' 을 말하면 남는다 — 레테·학원이 곁에 있다.
    m = {"title": "7세 소마 사고력수학 레벨테스트 후기",
         "snippet": "집에서 소마셈A, 1031 pre로 공부하다가 아무래도 학원을 다니는게 좋을 것 같아"}
    assert analyze.is_relevant(m, soma, False, RIVALS) is True


def test_학원_표지가_곁에_있으면_교재_이야기가_있어도_남긴다():
    """'1031' 은 교재 이름이자 반 이름이다. 레벨테스트 후기는 후기다."""
    m = {"title": "대치 초등 사고력 수학 시매쓰 레벨테스트 후기 (1031 기프티드 진도)",
         "snippet": "레테 보고 왔어요. 1031 기프티드 반 배정."}
    assert analyze.is_relevant(m, _CMATH, False, RIVALS) is True
    # 지점 블로그가 출판 교재 할인을 알려도 '학원입니다'·'재원생' 이 곁에 있다.
    m = {"title": "[시매쓰 서초반포센터] 겨울방학기념 할인 이벤트",
         "snippet": "안녕하세요, 반포시매쓰 학원입니다.^^ 시매쓰 출판에서 겨울방학을 맞아 "
                    "시매쓰 재원생을 대상으로 세트 할인 이벤트를 진행하여 안내드립니다."}
    assert analyze.is_relevant(m, {"반포시매쓰학원", "반포시매쓰", "시매쓰"}, False, RIVALS) is True


def test_맨_가격_워크북_교재는_교재_표지가_아니다():
    """캐시 실측 — 이 낱말들로 걸면 진짜 후기가 죽는다.
    '시대인재 화학2 단과 후기, 가격' · '아이엔 어학원 교재비 내역 … 워크북' ·
    학원 후기 템플릿의 '수업교재 : 자체교재'."""
    m = {"title": "시대인재 화학2 강준호T 단과 (화2 서바이벌 후기, 가격)",
         "snippet": "투과목 때문에 대치 단과 처음 다녀보는 마음에 공개적으로 적어봅니다. 1. 비용"}
    assert analyze.is_relevant(m, {"시대인재"}, False, RIVALS) is True
    m = {"title": "대치 IN 아이엔 어학원 초4 5월 수강료와 교재비 내역",
         "snippet": "초4 교재비 G4 Workbook Vol.3 30,000원 워크북은 아이엔 어학원 자체 제작"}
    assert analyze.is_relevant(m, {"아이엔어학원", "아이엔"}, False, RIVALS) is True
    m = {"title": "양천구 목동 씨엠에스(CMS) 후기 - 좋아요",
         "snippet": "[ 씨엠에스(CMS) 목동입시센터 수업방식 ] - 수업교재 : 원리해설 - 숙제분량 : 적당함"}
    assert analyze.is_relevant(m, {"씨엠에스", "cms"}, False, RIVALS) is True
    # 만원 단위는 원비다. 구조화된 교재 값(4~5자리 원·N천원)만 표지다.
    assert analyze._TEXTBOOK_PRICE.search("원비45만원") is None
    assert analyze._TEXTBOOK_PRICE.search("가격14000원") is not None
    assert analyze._TEXTBOOK_PRICE.search("확정가운고") is None


# ── 합성 후보 — 두 이름의 이어붙임 (2026-09-13, ma-26091319) ───────────
#
# '그로튼에밀튼' 은 자매 브랜드 '그로튼'(다른 등록)과 '에밀튼' 의 이어붙임이라
# 계열을 늘어놓은 글이 정규화 뒤 이 이름과 같아졌다. 기호로 갈라진 자리는
# 이름이 아니다. 공백 하나는 이름이다 — 학원 자신이 '그로튼 에밀튼' 이라 쓴다.
_GROTON = {"그로튼에밀튼어학원", "그로튼에밀튼", "리딩타운", "대치리딩타운"}
_GROTON_RIVALS = analyze.RivalIndex({"그로튼아카데미", "그로튼", "스와튼", "프라우드7", "프라우드7어퍼"})


def test_합성_후보는_남의_이름과_알맹이의_이어붙임일_때만():
    assert analyze.composite_candidates(_GROTON, _GROTON_RIVALS) == {"그로튼에밀튼"}
    # 남의 이름 색인이 없으면 판단할 근거가 없다.
    assert analyze.composite_candidates(_GROTON, analyze.RivalIndex(set())) == frozenset()
    # 브랜드 + 관·점 꼬리는 합성이 아니다 — '씨앤씨(11관)' 처럼 괄호로 붙여 쓴다.
    assert analyze.composite_candidates({"씨앤씨11관학원", "씨앤씨11관"},
                                        analyze.RivalIndex({"씨앤씨"})) == frozenset()
    assert analyze.composite_candidates({"시대인재커피관학원", "시대인재커피관"},
                                        analyze.RivalIndex({"시대인재"})) == frozenset()
    # 영문이 섞인 쪽은 보지 않는다 — '엘브라운(El.Brown)' 은 등록명에 마침표가 있다.
    assert analyze.composite_candidates({"엘브라운elbrown"},
                                        analyze.RivalIndex({"엘브라운"})) == frozenset()


def test_기호로_갈라진_자리는_이름이_아니다():
    for title in ("스와튼/그로튼/에밀튼 계열 셔틀 5시20수업",
                  "예비초1 그로튼 ,에밀튼, 크레오 합격",
                  "그로튼? 에밀튼? 어디가 나을까요",
                  "스와튼 / 프라우드 7 / 그로튼 / 에밀튼 진급 순서"):
        m = {"title": title, "snippet": "안녕하세요 수업시간이 변경될 예정이라"}
        assert analyze.is_relevant(m, _GROTON, False, _GROTON_RIVALS) is False, title
    assert analyze.split_seam("그로튼/에밀튼") and analyze.split_seam("그로튼>에밀튼")
    assert analyze.split_seam("그로튼\n에밀튼")          # 줄바꿈은 목록의 구분자다
    # 진짜 별칭('리딩타운')이 함께 있으면 그 표기로 산다 — 계열 글도 이 학원 글이다.
    m = {"title": "스와튼 / 프라우드 7 / 그로튼 / 에밀튼 / 리딩타운", "snippet": ""}
    assert analyze.is_relevant(m, _GROTON, False, _GROTON_RIVALS) is True


def test_공백_하나와_붙여_쓴_것은_이름이다():
    for title, body in (("★2027학년도 예비초 1학년 입학설명회", "그로튼에밀튼 아카데미 안녕하세요"),
                        ("안녕하세요, 그로튼 에밀튼입니다", "2027 입학설명회"),
                        ("그로튼 에밀튼 어학원 셔틀 문의", "")):
        m = {"title": title, "snippet": body}
        assert analyze.is_relevant(m, _GROTON, False, _GROTON_RIVALS) is True, title
    assert not analyze.split_seam("그로튼 에밀튼")
    assert not analyze.split_seam("시대인재(유니아나")   # 괄호는 이름에 붙는다


def test_보통_이름은_기호가_끼어도_그대로다():
    """이 검사는 합성 후보에만 건다. '깊은 생각' 수학학원·'씨앤씨(11관)' 은 그 학원이다."""
    m = {"title": "씨앤씨(11관) 중등 수학 후기", "snippet": "씨앤씨/11관 다닌 지 1년"}
    assert analyze.is_relevant(m, {"씨앤씨11관학원", "씨앤씨11관"}, False,
                               analyze.RivalIndex({"씨앤씨"})) is True


def test_stored_discovery_date_can_be_replaced_by_publication_date(store_path):
    mention_store.merge([_m("h1", "A", posted_at="2026-09-01", date_source="discovery")], quiet=True)
    assert mention_store.rows()[0]["date_source"] == "discovery"
    rows = mention_store.merge([_m("h1", "A", posted_at="2026-01-01")], quiet=True)
    assert rows[0]["posted_at"] == "2026-01-01"
    assert "date_source" not in rows[0]
    rows = mention_store.merge([_m("h1", "A", posted_at="2026-09-02", date_source="discovery")], quiet=True)
    assert rows[0]["posted_at"] == "2026-01-01"
    assert "date_source" not in rows[0]
