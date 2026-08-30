"""같은 학원의 여러 등록을 하나로 묶는다.

NEIS 는 '관'과 '과정' 단위로 따로 등록한다. 학부모가 'CMS 대치' 하나로
아는 곳이 원장에는 영재1관·영재3관·영재4관·중등1관·중등2관 다섯 건으로
잡혀 있고, 주소는 전부 삼성로 345 로 같다.

이걸 그대로 두면 두 가지가 망가진다.
  1. 목록에 같은 학원이 여러 번 뜬다.
  2. 언급이 등록별로 쪼개진다. 한 곳에 300건 붙을 신호가 다섯으로 갈려
     전부 표본 부족이 되거나, 같은 학원이 순위에 중복으로 오른다.

묶는 기준: **같은 주소 + 이름에 공통 브랜드 토큰**.
주소만으로 묶으면 안 된다. 대치동 상가 한 건물에 서로 다른 학원이
수십 개 들어 있다. 이름만으로도 안 된다. 지점이 다르면 다른 학원이다.
"""
from __future__ import annotations

import re
from collections import defaultdict

# 브랜드를 식별하지 못하는 일반 낱말. 이것만 겹치는 건 같은 학원의 근거가 아니다.
STOPWORDS = (
    "학원", "교습소", "보습학원", "어학원", "교육원", "교육센터", "센터", "캠퍼스",
    "영재교육", "영재", "교육", "입시", "보습", "종합", "전문", "스쿨", "아카데미",
    "초등", "중등", "고등", "유아", "성인", "재수", "관", "본관", "분관", "본원", "분원",
    # 건물 이름. 한 상가에 든 서로 다른 학원을 이어버리는 주범이다.
    "센트럴", "프라임", "타워", "플라자", "빌딩", "스퀘어", "파크", "메인",
    "영어", "수학", "국어", "과학", "논술", "독서", "미술", "음악", "체육", "코딩",
    "대치", "도곡", "개포", "목동", "신정", "반포", "잠원", "서초", "잠실", "신천",
    "방이", "강남", "송파", "양천", "서울", "제", "점", "호점", "에듀", "edu",
)
_NON = re.compile(r"[^가-힣A-Za-z0-9]")
_NUM = re.compile(r"\d+")
_ADDR_TAIL = re.compile(r"\s*(지하)?\s*\d+층.*$")


def address_key(address: str | None) -> str | None:
    """도로명주소를 건물 단위 키로. '서울특별시 강남구 삼성로 345' → 강남구삼성로345"""
    if not address:
        return None
    a = _ADDR_TAIL.sub("", address)
    a = re.sub(r"^(서울특별시|서울시|서울)\s*", "", a.strip())
    a = _NON.sub("", a)
    return a or None


# 업종·지점 수식어만 떼는 최소 정리. 브랜드에 과목명이 들어간 경우를 지킨다.
#
# 관(館) 수식어를 여기 둔 이유: '신관씨앤씨학원' 과 '씨앤씨16관학원' 은
# 같은 주소(목동동로 196)의 같은 학원인데 안 묶였다. 강한 정리는 낱말
# '관' 을 **이름 가운데서도** 지워 '신관씨앤씨' 를 '신씨앤씨' 로 만들어
# 버려서, 접두사 비교가 어긋났다. 관 수식어는 통째로 떼야 한다.
_LIGHT = (
    "제",
    "신관", "본관", "별관", "분관", "구관",
    "대치", "도곡", "개포", "목동", "신정", "반포", "잠원", "서초", "잠실", "신천",
    "방이", "강남", "송파", "양천", "서울",
)


# 업종어는 이름 끝에 붙는다. 가운데에서 지우면 브랜드가 망가진다.
# '뉴클리어학원'은 뉴클리어+학원인데 긴 것부터 지우면 '어학원'이 먼저 걸려
# '뉴클리'가 되고, 옆 건물 '뉴클리온'과 같은 학원으로 묶여 버렸다.
# 그래서 짧은 접미사부터, 끝에서만 뗀다.
_SUFFIX = ("학원", "교습소", "어학원", "보습학원", "교육원", "교육센터",
           "센터", "캠퍼스", "본원", "분원", "본관", "분관", "관", "호점", "점")


def _strip_suffix(s: str) -> str:
    changed = True
    while changed:
        changed = False
        for w in _SUFFIX:                       # 짧은 것부터 시도한다
            if s.endswith(w) and len(s) > len(w) + 1:
                s = s[: -len(w)]
                changed = True
                break
    return s


def _strip(name: str, words) -> str:
    s = re.sub(r"[（(].*?[)）]", "", name or "")
    s = _NUM.sub("", _NON.sub("", s).lower())
    s = _strip_suffix(s)
    for w in sorted(words, key=len, reverse=True):
        s = s.replace(w.lower(), "")
    return _strip_suffix(s)


def core_name(name: str) -> str:
    """업종어만 뗀 알맹이. 지역·지점 수식어는 남긴다.

    '시매쓰학원' → 시매쓰 / '반포시매쓰학원' → 반포시매쓰.
    브랜드 토큰과 견주면 '이름에 지점 단서가 있는가'를 알 수 있다.
    brand_token_light 는 지역어까지 떼므로 이 판단에 쓸 수 없다.
    """
    s = re.sub(r"[（(].*?[)）]", "", name or "")
    s = _NUM.sub("", _NON.sub("", s).lower())
    return _strip_suffix(s)


def brand_token(name: str) -> str:
    """강한 정리 — 일반 낱말을 최대한 걷어낸 브랜드 부분."""
    return _strip(name, STOPWORDS)


def brand_token_light(name: str) -> str:
    """약한 정리 — 업종·지점어만 뗀다.

    강한 정리만 쓰면 과목명이 브랜드에 박힌 곳이 무너진다.
    '목동깡수학과학2관학원'에서 수학·과학까지 떼면 '깡' 한 글자만 남아
    같은 브랜드의 1호관·6관·7관과 이어지지 않는다.
    """
    return _strip(name, _LIGHT)


def _share_brand(a: str, b: str) -> bool:
    """두 브랜드 토큰이 같은 학원을 가리키는가.

    '겹치는 3글자가 있으면 같다'로 시작했다가 크게 틀렸다. 목동서로 349
    한 건물에 든 예설라센트럴원·파피루스문해원·기파랑문해원·목동센트럴영재관이
    전부 한 학원으로 묶였다. '센트럴'은 브랜드가 아니라 건물 이름이었다.

    한국 학원 이름은 브랜드가 앞에 오고 뒤에 관·과정이 붙는다
    (씨앤씨 → 씨앤씨3관, 파인만 → 파인만영재고센터). 그래서 접두사 일치만
    인정한다. 건물명은 이름 중간에 박히므로 자연히 걸러진다.
    """
    if not a or not b:
        return False
    if a == b:
        return len(a) >= 2
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 3 and long_.startswith(short)


def same_academy(name_a: str, name_b: str) -> bool:
    """강한 정리·약한 정리 중 어느 쪽으로든 접두사가 맞으면 같은 학원으로 본다."""
    if _share_brand(brand_token(name_a), brand_token(name_b)):
        return True
    return _share_brand(brand_token_light(name_a), brand_token_light(name_b))


def group(records: list[dict]) -> dict[str, list[dict]]:
    """묶음 키 → 레코드 목록."""
    by_addr: dict[str, list[dict]] = defaultdict(list)
    loners: list[dict] = []
    for r in records:
        key = address_key(r.get("road_address"))
        (by_addr[key] if key else loners).append(r)

    groups: dict[str, list[dict]] = {}
    for addr, rows in by_addr.items():
        clusters: list[list[dict]] = []
        for r in rows:
            placed = False
            for c in clusters:
                if same_academy(r.get("name", ""), c[0].get("name", "")):
                    c.append(r)
                    placed = True
                    break
            if not placed:
                clusters.append([r])
        for i, c in enumerate(clusters):
            groups[f"{addr}#{i}"] = c
    for i, r in enumerate(loners):
        groups[f"noaddr#{i}"] = [r]
    return groups


# 관(館) 표기. 한 학원이 건물을 나눠 쓸 때 붙는 말이다.
# ★ 지역어는 여기 넣지 않는다. '책나무대치' 와 '책나무개포' 는 서로 다른
#   지점이고, 지역어까지 지우면 그 둘이 한 학원이 된다. 실측에서 약(light)
#   토큰으로 묶었더니 리드101 도곡·대치·개포가 한 곳이 됐다.
_HALL = ("신관", "본관", "별관", "분관", "구관", "관")
_HALL_MARK = re.compile(r"(제?\d+관|신관|본관|별관|분관|구관)")


# 업종어를 **복합형부터** 떼는 판. `_SUFFIX` 와 반대 순서다.
#
# 왜 둘로 나누는가:
#   _strip_suffix       는 브랜드 토큰(접두 매칭)에 쓰인다. 과하게 떼면
#                       '뉴클리어학원' 이 '뉴클리' 가 되고, 그건 옆 건물
#                       '뉴클리온' 의 **접두사**라 남남이 묶인다.
#   _strip_suffix_strong 는 hall_key(관 통합)에만 쓰인다. 이쪽은 같은
#                       학군 안에서 **완전일치**로 견주고, 게다가 한쪽에
#                       관 표기가 있어야 묶는다. '뉴클리' 와 '뉴클리온' 은
#                       글자가 달라 안 걸린다 — 과하게 떼도 안전하다.
#
# 이걸 안 나눠서 '아이엘이(별관)어학원' 이 '아이엘이어' 로 남았고,
# 본관인 '아이엘이' 와 이어지지 않았다(신고로 발견).
# ★ **과목어는 업종어가 아니다 — 여기 넣으면 안 된다.**
#
#   한때 '수학학원'·'영어학원'·'국어학원'·'과학학원'·'논술학원' 이 이
#   목록에 있었다. 그러자 '대치정상**수학학원**' 이 '대치정상' 이 되고,
#   '대치1관정상**어학원**' 도 '대치정상' 이 되어 **영어 학원과 수학
#   학원이 한 학원으로 묶였다**(실측 3묶음: 정상 대치·목동, 함영원).
#
#   과목은 같은 브랜드의 두 학원을 **가르는 정보**다. 지우면 그 둘이
#   같아 보이는 것이 당연하다. 업종어(어학원·교습소·보습학원…)만 뗀다.
#
#   '어학원' 은 남긴다 — 그건 과목이 아니라 업종이다. 길이순 정렬이라
#   '학원' 보다 먼저 걸리므로 '아이엘이(별관)어학원' 이 '아이엘이어' 로
#   남던 문제도 그대로 해결된다.
_SUFFIX_STRONG = tuple(sorted(
    ("보습학원", "어학원", "교습소", "교육센터", "교육원", "캠퍼스", "센터",
     "본원", "분원", "본관", "분관", "호점", "학원", "관", "점"),
    key=len, reverse=True))


def _strip_suffix_strong(s: str) -> str:
    """업종어를 끝에서만, **긴 복합형부터** 뗀다.

    짧은 것부터 떼면 '학원' 이 먼저 걸려 '어학원' 이 끝에 안 남는다 →
    '아이엘이어'. 같은 함정을 neis.normalize_name 에서 이미 한 번 겪었다.
    """
    changed = True
    while changed:
        changed = False
        for w in _SUFFIX_STRONG:
            if s.endswith(w) and len(s) > len(w) + 1:
                s = s[: -len(w)]
                changed = True
                break
    return s


def hall_key(name: str) -> str:
    """관 표기만 지운 이름. **지역·과목·브랜드는 그대로 남긴다.**

    지역어까지 떼면(brand_token_light) 리드101 도곡·대치·개포가 한 학원이
    된다. 여기서 지우는 것은 관 표기와 업종어뿐이다.
    """
    s = re.sub(r"[（(].*?[)）]", "", name or "")
    s = _NUM.sub("", _NON.sub("", s).lower())
    s = _strip_suffix_strong(s)
    for w in _HALL:
        s = s.replace(w, "")
    return _strip_suffix_strong(s)


def has_hall_mark(name: str) -> bool:
    """'3관'·'신관'처럼 한 학원이 건물을 나눠 쓴다는 표시가 있는가."""
    return bool(_HALL_MARK.search(_NON.sub("", name or "")))


def _strip_hall_mark(name: str) -> str:
    """이름에서 관 번호만 뗀다. '길벗제2관보습학원' → '길벗보습학원'."""
    out = _HALL_MARK.sub("", name or "").strip()
    return out or name


def merge_same_name(groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """같은 학군에서 **대표명이 완전히 같은** 묶음끼리 다시 합친다.

    주소가 다르면 안 묶는 것이 기본이다. 한 건물에 수십 곳이 들어 있는
    동네라 주소만으로 묶으면 남남이 한 학원이 된다. 그런데 그 반대도 있다 —
    목동 씨앤씨는 대표명이 그냥 '씨앤씨' 인 묶음이 서로 다른 다섯 주소에
    흩어져 있었다. 한 학원의 여러 관이지 다섯 학원이 아니다.

    **이름이 글자 하나까지 같고 학군도 같다**면 같은 학원으로 본다.
    지점이 다르면 이름에 단서가 붙는다('반포시매쓰학원' vs '시매쓰학원').
    실측에서 이 조건에 걸린 것은 9묶음 21건이고 전부 유명 브랜드의 여러
    관이었다(씨앤씨·시대인재·대치파인만·플라즈마·시리우스…).

    ★ 원본 이름이 아니라 **대표명**으로 견준다. '씨앤씨' 라는 등록은
      NEIS 에 하나도 없다 — 그 이름은 '씨앤씨3관학원'·'씨앤씨5관학원' 의
      공통 접두사로 이 단계에서 만들어진다. 원본 이름으로 보면 아무것도
      안 걸린다(여기서 한 번 헛돌았다).
    """
    by_name: dict[tuple, list[str]] = defaultdict(list)
    by_hall: dict[tuple, list[str]] = defaultdict(list)
    marked: set[str] = set()
    for key, rows in groups.items():
        names = [r.get("name", "") for r in rows]
        rep = representative_name(names).strip()
        region = rows[0].get("region_id")
        if rep:
            by_name[(region, rep)].append(key)
        hall = hall_key(rep)
        if len(hall) >= 3:
            by_hall[(region, hall)].append(key)
        if any(has_hall_mark(n) for n in names):
            marked.add(key)

    # 관 표기가 붙은 묶음이 하나라도 있을 때만 관 기준으로 합친다.
    # '피아노교습소' 와 '피아노교습소(김옥선)' 은 이름이 비슷할 뿐
    # 한 학원이 아니다 — 그런 곳에는 관 표기가 없다.
    plans = [ks for ks in by_hall.values()
             if len(ks) > 1 and any(k in marked for k in ks)]

    out = dict(groups)
    for keys in plans:
        keys = [k for k in keys if k in out]
        if len(keys) < 2:
            continue
        merged: list[dict] = []
        for k in keys:
            merged.extend(out.pop(k))
        # 대표 레코드(주소·좌표)는 정원이 가장 큰 관으로 둔다. 아무거나
        # 고르면 지도에 본관이 아니라 별관이 찍힌다.
        merged.sort(key=lambda r: -(r.get("tofor_smtot") or 0))
        out[keys[0]] = merged
    return out


def representative_name(names: list[str]) -> str:
    """묶음의 대표 이름. **`names[0]` 이 가장 오래된 등록**이어야 한다.

    가장 짧은 이름을 쓰면 '씨엠에스(CMS)중등1관학원' 처럼 특정 관 이름이
    다섯 관을 대표하게 된다. 이름들의 공통 접두사가 있으면 그쪽이 브랜드다.

    ★ 공통 접두사가 없으면 **가장 오래된 등록의 이름**을 쓴다. 예전에는
      가장 짧은 이름이었는데, 그러면 과목이 다른 관이 묶였을 때 한 과목이
      전체를 대표한다. 신고로 드러났다(2026-08-29):

          대치1관정상어학원(영어·표본 337) + 대치정상수학학원(수학·61)
          → 최단 이름 '대치정상수학학원'

      영어가 압도적인 학원이 화면에 '수학학원' 으로 나갔다. id 는 이미
      가장 오래된 등록에서 딴다(신원). **이름만 다른 규칙으로 뽑으면
      신원과 표시가 어긋난다** — 같은 것을 두 기준으로 부르는 셈이다.

    ★ 접두사가 **너무 많이 깎이면 쓰지 않는다.**
      '책읽기독서논술교습소' 와 '책읽기와글쓰기리딩엠역삼…' 의 공통 접두사는
      '책읽기' 다. 3자라 조건은 통과하지만 이건 브랜드가 아니라 그냥
      일상어이고, 실제로 이 이름 때문에 온갖 독서 관련 글이 이 학원의
      근거로 잡혔다. 원래 이름의 절반도 안 남으면 접두사가 아니라
      우연히 겹친 낱말로 본다.
    """
    names = [n for n in names if n]
    if not names:
        return ""
    prefix = names[0]
    for n in names[1:]:
        while prefix and not n.startswith(prefix):
            prefix = prefix[:-1]
    prefix = re.sub(r"[\s(（]+$", "", prefix).strip()

    # 접두사가 쓸 만한지는 **가장 짧은 이름** 기준으로 본다. 여기까지는
    # 예전 그대로다 — 최고참 이름으로 견주면 그 이름이 긴 만큼 접두사가
    # 부족해 보여서, '메이플'·'뉴파인'·'브래니악' 같은 멀쩡한 브랜드 이름이
    # '메이플리틀쇼팽음악학원' 으로 퇴화한다(실측에서 이렇게 틀렸다).
    shortest = min(names, key=lambda n: (len(n), n))
    core = re.sub(r"(학원|교습소|어학원)$", "", shortest)
    if len(prefix) >= 3 and len(prefix) * 2 >= len(core):
        return prefix
    # 쓸 만한 공통 접두사가 없을 때만 신원(가장 오래된 등록)을 따른다.
    return names[0]


def merge(rows: list[dict]) -> dict:
    """한 묶음을 대표 레코드 하나로 합친다."""
    if len(rows) == 1:
        r = dict(rows[0])
        r["registration_count"] = 1
        r["registration_ids"] = [r.get("id")]
        return r

    # ★ 신원(id)은 **가장 오래된 등록**에서 딴다.
    #   이름 길이순으로 고르면 더 짧은 이름의 관이 새로 등록될 때마다
    #   학원의 id 가 뒤집힌다. id 는 후기·판정·정정이 전부 매달리는
    #   키라서, 한 번 뒤집히면 그 참조가 전부 고아가 된다.
    #   개설일이 같으면 id 문자열로 — 어떤 기준이든 결정적이면 된다.
    rows = sorted(rows, key=lambda r: (r.get("estbl_ymd") or "9999-99-99",
                                       str(r.get("id"))))
    base = dict(rows[0])
    # 주소·동은 정원이 가장 큰 관에서 — 지도에 별관이 찍히지 않게.
    loc = max(rows, key=lambda r: r.get("tofor_smtot") or 0)
    for f in ("road_address", "dong"):
        if loc.get(f):
            base[f] = loc[f]
    names = [r.get("name", "") for r in rows]
    rep = representative_name(names)
    # 통합체의 이름에 관 번호가 남으면 안 된다. '길벗제2관보습학원' 은
    # 5개 관을 합친 곳의 이름으로 읽히지 않는다 — 2관만 가리키는 말이다.
    if has_hall_mark(rep):
        # 번호만 뗀 이름이 실제 등록으로 있으면 그것을, 없으면 뗀 형태를.
        #
        # ★ 관 없는 이름을 **아무거나** 집어오면 안 된다. 과목이 다른 관이
        #   묶였을 때 그쪽 이름이 묶음 전체를 대표하게 된다 — 실측:
        #   '대치1관정상어학원'(대표) 이 관 표기 때문에 밀려나
        #   '대치정상수학학원' 이 영어 학원의 이름이 됐다.
        bare = _strip_hall_mark(rep)
        same = [n for n in names if not has_hall_mark(n) and n == bare]
        rep = same[0] if same else bare
    base["name"] = rep

    caps = [r.get("tofor_smtot") for r in rows if r.get("tofor_smtot")]
    base["tofor_smtot"] = sum(caps) if caps else None          # 정원은 합산
    seats = [r.get("dtm_rcptn_ablty_nmpr_smtot") for r in rows
             if r.get("dtm_rcptn_ablty_nmpr_smtot")]
    base["dtm_rcptn_ablty_nmpr_smtot"] = sum(seats) if seats else None


    dates = [r.get("estbl_ymd") for r in rows if r.get("estbl_ymd")]
    base["estbl_ymd"] = min(dates) if dates else None          # 가장 이른 개설일

    # 과목·단계는 합집합. 관마다 담당 과정이 다르므로 합쳐야 실제 모습이 된다.
    for field in ("subjects", "grade_bands", "stages", "flagship", "aliases"):
        merged, seen = [], set()
        for r in rows:
            for v in r.get(field) or []:
                if v not in seen:
                    seen.add(v)
                    merged.append(v)
        base[field] = merged

    # 단계별 근거도 합친다. 같은 단계에 두 관이 다른 근거로 붙었으면
    # 강한 쪽(curated > hinted > inferred)을 남긴다 — 통합 때문에 근거가
    # 약해 보이면 화면이 실제보다 덜 알려 준다.
    rank = {"curated": 2, "hinted": 1, "inferred": 0}
    basis: dict[str, str] = {}
    for r in rows:
        for sid, kind in (r.get("stage_basis") or {}).items():
            if rank.get(kind, 0) >= rank.get(basis.get(sid), -1):
                basis[sid] = kind
    base["stage_basis"] = {s: basis[s] for s in base["stages"] if s in basis}

    if any(r.get("reg_stttus_nm") == "정상" for r in rows):
        base["reg_stttus_nm"] = "정상"

    base["registration_count"] = len(rows)
    base["registration_ids"] = [r.get("id") for r in rows]
    base["merged_names"] = [r.get("name") for r in rows]
    return base


def apply(records: list[dict]) -> tuple[list[dict], int]:
    """전체에 적용. (합쳐진 목록, 줄어든 건수) 를 돌려준다."""
    groups = merge_same_name(group(records))
    out = [merge(rows) for rows in groups.values()]
    return out, len(records) - len(out)
