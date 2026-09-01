"""이름이 오염원인 학원을 **전수로** 찾는다.

'새로운학원의 근거가 죄다 new 라는 뜻의 새로운' 이라는 신고를 받고
낱말을 손으로 넣었다. 그러면 신고가 온 곳만 고쳐지고 같은 성질의 다른
학원은 그대로 남는다. 실제로 그때 훑어 보니 한 번에 일곱 곳이었다
(테스트 201 · 피아노 196 · 새로운 166 · 포인트 160 · 갈무리 148 ·
로드맵 121 · 음악 51). **신고는 한 곳으로 오지만 원인은 낱말이다.**

두 종류가 있고 증상이 같다.

    일반 명사   '테스트'·'새로운'·'음악'  — 아무 글에나 나온다
    사람 이름   '윤도영'·'류다현'         — 동명이인 글이 섞인다
                (윤도영 146건 중 10건이 뮤지컬 배우였다)

## 사전을 두지 않는다 — 코퍼스가 답을 안다

'일상어 목록' 을 유지하는 방식은 목록을 채우는 사람만큼만 정확하다.
대신 **그 이름이 우리가 모은 글 전체에서 얼마나 흔한지**를 그 학원의
근거 수와 견준다. 이름이 제 근거보다 훨씬 넓게 퍼져 있으면, 그 이름은
그 학원만 가리키는 말이 아니다.

    넓이(wide)  코퍼스 전체에서 그 이름이 나오는 글 수
    근거(own)   그 학원의 표본
    퍼짐(spread) = wide / own

실측(캐시 5만 글): '테스트' wide 1,815 · own 201 → 퍼짐 9.0
                   '렉스김' wide 121 · own 120 → 퍼짐 1.0

제목 주인공 비율도 함께 본다. 제목에 제 이름이 거의 안 나오면 그 글들의
주인공은 남이다 — 사람 이름 학원이 여기서 잘 걸린다.

## 볼 수 없는 것

게이트가 실제로 어느 표기로 걸었는지는 여기서 모른다. 후보 중 가장 짧은
것(≥3자)을 대표로 쓴다. 그래서 두 글자 별칭('세정')으로 걸린 글은 넓이에
안 잡히고, 대신 **근거가 넓이보다 큰** 모양으로 드러난다(반포세정: 근거
126 · 코퍼스 48). 그것도 신호라 제목 비율이 함께 낮으면 걸러 낸다.

## 이 장치는 판정하지 않는다

여기서 하는 일은 **재고 알리는 것**까지다. 게이트를 조이는 결정은 위키
frontmatter 의 `generic: true` 로 사람이 한다 — 엔진은 frontmatter 를
덮어쓰지 않는다(SCHEMA.md). 자동으로 조이면 멀쩡한 학원의 근거가 조용히
사라지는 쪽으로 틀릴 수 있고, 그 실수는 화면에서 '학원이 없다' 로만
보인다.
"""
from __future__ import annotations

from . import analyze

#: 이만큼도 안 퍼진 이름은 애초에 문제가 안 된다. 코퍼스가 5만 글쯤이라
#: 30건은 '우연히 겹치는 정도' 의 아래쪽이다.
MIN_WIDE = 30

#: 제 근거보다 이 배수 이상 넓게 퍼져 있으면 이름이 헐겁다고 본다.
#: 3배는 '남의 글이 제 글의 두 배' 라는 뜻이다.
SPREAD_LIMIT = 3.0

#: 제목에 제 이름이 이 비율에도 못 미치면 그 글들의 주인공이 남이다.
#: 정상 학원은 대개 0.3~0.7 이다(후기 제목에 이름을 적는다).
TITLE_FLOOR = 0.15

#: 근거가 이보다 적으면 비율이 요동쳐 판단할 수 없다.
MIN_SAMPLE = 8


def _weakest(cands: set[str]) -> str | None:
    """가장 **헐거운** 후보 이름. 짧을수록 아무 데나 걸린다.

    '지엘피아카데미학원' 과 '지엘피' 가 함께 있으면 오염을 만드는 쪽은
    짧은 것이다. 두 글자는 우연이 너무 잦아 빼고 본다 — 그건 이 장치가
    아니라 `EVERYDAY_ALIASES` 가 다룬다.
    """
    usable = [c for c in cands if len(c) >= 3]
    return min(usable, key=len) if usable else None


def measure(academies: list[dict],
            mentions: list[dict],
            corpus: list[dict],
            candidates: dict[str, set[str]]) -> list[dict]:
    """학원마다 이름의 위험도를 잰다. 판정하지 않고 값만 낸다.

    [corpus] 는 게이트 **이전**의 글 전체다. 게이트를 통과한 것만 보면
    이미 걸러진 뒤라 '얼마나 넓게 퍼져 있는가' 를 볼 수 없다.
    """
    blobs = [analyze._norm((m.get("title") or "") + " " + (m.get("snippet") or ""))
             for m in corpus]
    titles = {}
    for m in mentions:
        titles.setdefault(m.get("academy_key"), []).append(
            analyze._norm(m.get("title") or ""))

    own_counts: dict[str, int] = {}
    for m in mentions:
        own_counts[m.get("academy_key")] = own_counts.get(m.get("academy_key"), 0) + 1

    # ★ 넓이는 **그 이름 전체**를 세고 근거는 한 지점 몫이라, 그대로 나누면
    #   지점이 많은 유명 브랜드가 무조건 퍼져 보인다. 실측에서 깊은생각
    #   (5.1배)·시대인재(4.8배)·한우리(4.5배)·시매쓰(4.4배)가 그렇게 걸렸다 —
    #   전부 멀쩡한 학원이고, 코퍼스의 그 글들은 **형제 지점 이야기**였다.
    #   → 같은 이름을 쓰는 학원의 근거를 모아서 견준다.
    tokens = {a["id"]: _weakest(candidates.get(a["id"]) or set()) for a in academies}
    brand_own: dict[str, int] = {}
    for aid, tok in tokens.items():
        if tok:
            brand_own[tok] = brand_own.get(tok, 0) + own_counts.get(aid, 0)

    rows = []
    for a in academies:
        aid = a["id"]
        own = own_counts.get(aid, 0)
        if own < MIN_SAMPLE:
            continue
        name = tokens.get(aid)
        if not name:
            continue
        wide = sum(1 for b in blobs if name in b)
        mine = titles.get(aid) or []
        title_ratio = (sum(1 for t in mine if name in t) / len(mine)) if mine else 0.0
        spread = wide / max(1, brand_own.get(name, own))

        # 두 사유는 함께 걸릴 수 있다. 하나만 적으면 다음 사람이 나머지를
        # 다시 재야 한다 — 둘 다 남긴다.
        why = []
        if spread >= SPREAD_LIMIT:
            why.append("퍼짐")
        if title_ratio < TITLE_FLOOR:
            why.append("제목에 이름 없음")
        if wide < MIN_WIDE or not why:
            continue
        rows.append({
            "id": aid,
            "name": a.get("display_name") or a.get("name"),
            "region_id": a.get("region_id"),
            "token": name,
            "own": own,
            "wide": wide,
            "spread": round(spread, 1),
            "title_ratio": round(title_ratio, 2),
            # 왜 걸렸는지를 남긴다. 숫자만 있으면 다음 사람이 다시 판단해야 한다.
            "why": " · ".join(why),
        })
    rows.sort(key=lambda r: (-r["spread"], -r["own"]))
    return rows


def report(rows: list[dict], total: int, already: set[str]) -> list[str]:
    """실행 로그에 찍을 줄. 조용히 지나가면 아무도 안 본다."""
    fresh = [r for r in rows if r["id"] not in already]
    if not rows:
        return [f"이름 위험 점검: 채점 {total:,}곳 중 걸리는 곳 없음 ✓"]
    out = [f"이름 위험 점검: {len(rows)}곳 "
           f"(이미 표시된 곳 {len(rows) - len(fresh)} · **새로 걸린 곳 {len(fresh)}**)"]
    for r in fresh[:8]:
        out.append(f"    · {r['name']}({r['region_id']}) '{r['token']}' "
                   f"근거 {r['own']} · 코퍼스 {r['wide']} · 퍼짐 {r['spread']}배 "
                   f"· 제목 {r['title_ratio']:.0%} — {r['why']}")
    if len(fresh) > 8:
        out.append(f"    … 외 {len(fresh) - 8}곳")
    if fresh:
        out.append("    → 확인 후 위키 frontmatter 에 generic: true "
                   "(엔진은 frontmatter 를 건드리지 않는다)")
    return out
