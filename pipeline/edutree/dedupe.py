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
_LIGHT = (
    "제",
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


def representative_name(names: list[str]) -> str:
    """묶음의 대표 이름.

    가장 짧은 이름을 쓰면 '씨엠에스(CMS)중등1관학원' 처럼 특정 관 이름이
    다섯 관을 대표하게 된다. 이름들의 공통 접두사가 있으면 그쪽이 브랜드다.

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

    shortest = min(names, key=lambda n: (len(n), n))
    # 업종어를 뗀 알맹이 기준으로 견준다. '교습소'·'학원' 은 어차피 공통이다.
    core = re.sub(r"(학원|교습소|어학원)$", "", shortest)
    if len(prefix) >= 3 and len(prefix) * 2 >= len(core):
        return prefix
    return shortest


def merge(rows: list[dict]) -> dict:
    """한 묶음을 대표 레코드 하나로 합친다."""
    if len(rows) == 1:
        r = dict(rows[0])
        r["registration_count"] = 1
        r["registration_ids"] = [r.get("id")]
        return r

    rows = sorted(rows, key=lambda r: (len(r.get("name", "")), r.get("name", "")))
    base = dict(rows[0])
    base["name"] = representative_name([r.get("name", "") for r in rows])

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

    if any(r.get("reg_stttus_nm") == "정상" for r in rows):
        base["reg_stttus_nm"] = "정상"

    base["registration_count"] = len(rows)
    base["registration_ids"] = [r.get("id") for r in rows]
    base["merged_names"] = [r.get("name") for r in rows]
    return base


def apply(records: list[dict]) -> tuple[list[dict], int]:
    """전체에 적용. (합쳐진 목록, 줄어든 건수) 를 돌려준다."""
    groups = group(records)
    out = [merge(rows) for rows in groups.values()]
    return out, len(records) - len(out)
