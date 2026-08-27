#!/usr/bin/env python3
"""검색엔진·AI가 읽을 수 있는 정적 HTML 을 만든다.

왜 필요한가
    앱은 CanvasKit 으로 캔버스에 그린다. 화면에 보이는 글자가 DOM 에 없어서
    구글·네이버 크롤러도, AI 답변 엔진도 내용을 하나도 읽지 못한다.
    지금 색인되는 것은 홈의 메타 태그뿐이다.

무엇을 하는가
    학원 3,910곳 · 학교 136곳 · 학군 4곳 · 트랙 12개를 각각 정적 페이지로
    낸다. 사람이 보기에도 멀쩡한 요약 페이지이고, 본문은 전부 DOM 에 있다.
    각 페이지는 앱의 해당 화면으로 연결된다.

    구조화 데이터(JSON-LD)를 함께 넣는다. 검색 결과 리치 스니펫과
    AI 답변 엔진이 사실을 정확히 인용하는 데 쓰인다.

주의
    aggregateRating 은 넣지 않는다. 그 스키마는 '이용자 별점'을 뜻하는데
    트리스코어는 우리가 계산한 지표다. 형식만 맞추자고 의미가 다른 값을
    넣으면 검색엔진과 이용자 모두를 오도한다.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "assets" / "data"
SITE = "https://openedu4u.com"

SUBJECTS = {"math": "수학", "english": "영어", "korean": "국어·논술",
            "science": "과학", "etc": "종합·보습"}
# 학원이 받는 학년대. 학교(초등학교·중학교·고등학교)와는 다른 축이다.
BANDS = {"elem_low": "예비초~초3", "elem_high": "초4~초6",
         "middle": "중등", "high": "고등"}


PILLAR_NAMES = {"reputation": "평판", "momentum": "화제성",
                "transparency": "투명성", "selectivity": "진입난이도"}

# 기둥별 계산 근거. 앱의 산식 화면(method_page.dart)과 같은 내용을 쓴다 —
# 두 곳이 다른 말을 하면 공개한 의미가 없다.
PILLAR_DETAIL = {
    "reputation": [
        "커뮤니티 게시물마다 감성 점수(-1 ~ +1)를 매깁니다.",
        "각 글의 가중치 = 신뢰도 × 최신성. 최신성은 반감기 180일 지수 감쇠입니다.",
        "신뢰도는 글 길이, 구체적 수치(학년·개월·등급), 1인칭 경험 서술, "
        "실제 수강 이력 언급으로 매깁니다.",
        "가중 평균을 같은 지역·과목 코호트 평균 쪽으로 축소합니다(베이지안 축소).",
        "축소한 값을 코호트 z점수로 옮깁니다 — 50 + 15z.",
    ],
    "selectivity": [
        "레벨테스트 난이도 언급 40% · 대기/마감 언급 30% · 정원 대비 언급량 30%.",
        "표본이 적으면 중앙(50)으로 끌어당깁니다(사전표본 10건) — "
        "12건으로 ‘난이도 100’ 은 측정이 아니라 잡음이기 때문입니다.",
        "공식 경쟁률이 아니라 커뮤니티 언급에서 추정한 값입니다.",
        "등급반(심화반·최상위반)별 난이도는 내놓지 않습니다.",
    ],
    "momentum": [
        "최근 90일 언급량을 로그 스케일로 잡고 코호트 안에서 z점수로 표준화합니다 (60%).",
        "최근 12개월 월별 언급량의 선형 추세 기울기를 봅니다 (40%).",
        "상승·보합·하락 화살표는 이 기울기에서 나옵니다.",
    ],
    "transparency": [
        "등록상태 정상 30점 — 휴원·폐원이면 감점.",
        "정원 공시 20점 · 교습과정 상세 25점.",
        "운영 지속기간 25점 — 개설일 기준 로그 스케일.",
        "네 기둥 중 유일하게 100% 검증 가능한 항목입니다.",
        "교습비 항목은 뺐습니다 — 아래 ‘교습비를 쓰지 않는 이유’ 를 보세요.",
    ],
}


def formula_parts(meta) -> list:
    """무거운 기둥부터 (이름, 퍼센트).

    가중치의 출처는 meta.json 하나뿐이다. 문서에 숫자를 박아 두면
    산식을 바꾼 뒤에도 옛 값이 남는다 — 실제로 llms.txt 와 학군 FAQ 가
    화제성 20% / 투명성 25% / 진입난이도 20% 라는 옛 값을 계속 내보내고 있었다.
    """
    w = (meta or {}).get("weights") or {}
    parts = [(PILLAR_NAMES[k], round(v * 100))
             for k, v in w.items() if k in PILLAR_NAMES]
    return sorted(parts, key=lambda nv: -nv[1])


def formula_line(meta, joiner: str = " + ") -> str:
    return joiner.join(f"{n} {pct}%" for n, pct in formula_parts(meta))


def min_sample(meta) -> int:
    return (meta or {}).get("minSampleForRank", 10)


def esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def load(name: str):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def won(v) -> str:
    if not v:
        return "미공개"
    return f"{v // 10000}만원" if v % 10000 == 0 else f"{v:,}원"


def page(title: str, desc: str, canonical: str, body: str,
         jsonld: dict | list | None = None, breadcrumb: list | None = None) -> str:
    blocks = []
    if jsonld:
        blocks.append(json.dumps(jsonld, ensure_ascii=False))
    if breadcrumb:
        blocks.append(json.dumps({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                for i, (n, u) in enumerate(breadcrumb)],
        }, ensure_ascii=False))
    scripts = "\n".join(
        f'<script type="application/ld+json">{b}</script>' for b in blocks)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<meta property="og:type" content="article">
<meta property="og:site_name" content="학원실록">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/og-image.png">
<link rel="icon" href="{SITE}/favicon.ico" sizes="any">
{scripts}
<style>
:root{{color-scheme:light dark}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
max-width:760px;margin:0 auto;padding:28px 20px 80px;line-height:1.75;color:#16203a;background:#fff}}
a{{color:#1d3f7a}}
header{{border-bottom:1px solid #e6e2d8;padding-bottom:14px;margin-bottom:22px}}
.brand{{font-weight:800;font-size:15px;color:#182448;text-decoration:none}}
.by{{font-size:12px;color:#9a8a6a;margin-left:6px}}
h1{{font-size:26px;margin:.4em 0 .2em;letter-spacing:-.5px}}
.sub{{color:#5d6b7a;font-size:14px;margin-top:0}}
table{{border-collapse:collapse;width:100%;margin:18px 0;font-size:14.5px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid #eee}}
th{{width:34%;color:#5d6b7a;font-weight:600}}
.cta{{display:inline-block;margin:18px 0;padding:11px 18px;background:#182448;color:#fff;
border-radius:8px;text-decoration:none;font-weight:700;font-size:14px}}
.chips span{{display:inline-block;background:#f1efe8;border-radius:999px;padding:3px 10px;
font-size:12.5px;margin:0 5px 5px 0}}
footer{{margin-top:40px;padding-top:16px;border-top:1px solid #e6e2d8;font-size:12.5px;color:#7a8794}}
ul{{padding-left:18px}}
</style>
</head>
<body>
<header><a class="brand" href="{SITE}/">학원실록</a><span class="by">by Open Edu</span></header>
{body}
<footer>
<p>출처: NEIS 학원·학교 공시정보, 네이버 검색 API. 산식은 <a href="{SITE}/method.html">공개</a>합니다.</p>
<p>운영: <a href="{SITE}/openedu/">Open Edu</a> · 정보에 오류가 있으면 정정을 요청해 주세요.</p>
</footer>
</body>
</html>
"""


def academy_pages(out: Path, academies, registry, regions) -> list[str]:
    region_name = {r["id"]: r["name_ko"] for r in regions}
    urls = []
    (out / "a").mkdir(parents=True, exist_ok=True)

    for a in list(academies) + list(registry):
        aid = a["id"]
        name = a.get("displayName") or a["name"]
        reg = region_name.get(a.get("regionId"), "")
        subs = "·".join(SUBJECTS.get(s, s) for s in (a.get("subjects") or []))
        score = a.get("score")

        title = f"{name} — {reg} 학원 정보 | 학원실록"
        # 표본이 없으면 설명에도 점수를 적지 않는다 — 검색결과 스니펫이
        # 근거 없는 숫자를 그대로 인용해 간다.
        scored = bool(score and score.get("sampleSize"))
        desc = (f"{reg} {name}의 교습비, 정원, 등록상태를 NEIS 공시로 확인하세요."
                + (f" 트리스코어 {score['total']:.0f}점." if scored else ""))

        rows = [("학군", reg), ("분야", subs or "—"),
                ("주소", a.get("address")), ("등록상태", a.get("registrationStatus")),
                ("정원", f"{a['capacity']}명" if a.get("capacity") else "—")]
        if a.get("registrationCount", 1) > 1:
            rows.append(("등록 건수", f"{a['registrationCount']}건(관·과정별 등록 통합)"))

        body = [f"<h1>{esc(name)}</h1>",
                f'<p class="sub">{esc(reg)} · {esc(subs)}</p>']
        # 표본 0 은 '적다'가 아니라 '없다'다. 이때 평판은 코호트 평균(50)으로
        # 대체된 값이라 그대로 찍으면 50점이 평가 결과처럼 읽힌다. 실명 사업자에게
        # 근거 없는 숫자를 붙이는 것이라 점수 자체를 내지 않는다.
        # 앱도 같은 규칙이다 — academy_page.dart / academy_card.dart 의 sampleSize == 0 분기.
        #
        # '수집했는데 근거가 없다'와 '아직 안 봤다'는 다른 상태이므로 문구를 나눈다.
        if scored:
            body.append(
                f"<p><strong>트리스코어 {score['total']:.0f}점</strong> "
                # 예체능·기타는 투명성·진입난이도를 채점하지 않아 None 이다.
                # 0 으로 적으면 '점수가 나쁘다'로 읽히므로 항목 자체를 뺀다.
                + " (" + " · ".join(
                    f"{label} {score[key]:.0f}"
                    for key, label in (("reputation", "평판"),
                                       ("momentum", "화제성"),
                                       ("transparency", "투명성"),
                                       ("selectivity", "진입난이도"))
                    if score.get(key) is not None) + ") "
                + f"— 유효 표본 {score['sampleSize']}건"
                # 순위 기준은 파이프라인이 이미 정했다. 여기서 10 을 다시 쓰면
                # 기준이 두 곳에 생겨 언젠가 어긋난다.
                + ("" if score.get("isRanked") else " · 표본 부족으로 순위 제외")
                + "</p>")
        elif score:
            body.append("<p>수집한 커뮤니티 글에서 이 학원을 가리키는 근거를 "
                        "찾지 못했습니다. 점수를 내지 않습니다. 공시 정보만 표시합니다.</p>")
        else:
            body.append("<p>아직 커뮤니티 신호를 수집하지 않은 학원입니다. "
                        "공시 정보만 표시합니다.</p>")

        body.append("<table>" + "".join(
            f"<tr><th>{esc(k)}</th><td>{esc(v) or '—'}</td></tr>" for k, v in rows) + "</table>")
        body.append(f'<a class="cta" href="{SITE}/#/academy/{aid}">학원실록에서 자세히 보기</a>')

        ld = {
            "@context": "https://schema.org",
            "@type": "EducationalOrganization",
            "name": name,
            "url": f"{SITE}/a/{aid}.html",
            "areaServed": reg,
        }
        if a.get("address"):
            ld["address"] = {"@type": "PostalAddress",
                             "streetAddress": a["address"],
                             "addressCountry": "KR"}
        if a.get("lat") and a.get("lng"):
            ld["geo"] = {"@type": "GeoCoordinates",
                         "latitude": a["lat"], "longitude": a["lng"]}

        (out / "a" / f"{aid}.html").write_text(
            page(title, desc, f"{SITE}/a/{aid}.html", "\n".join(body), ld,
                 [("학원실록", f"{SITE}/"), (reg, f"{SITE}/g/{a.get('regionId')}.html"),
                  (name, f"{SITE}/a/{aid}.html")]), encoding="utf-8")
        urls.append(f"{SITE}/a/{aid}.html")
    return urls


def school_pages(out: Path, schools, regions) -> list[str]:
    region_name = {r["id"]: r["name_ko"] for r in regions}
    urls = []
    (out / "s").mkdir(parents=True, exist_ok=True)
    for s in schools:
        sid = s["id"]
        reg = region_name.get(s.get("regionId"), "")
        title = f"{s['name']} — {reg} {s.get('levelLabel','')} | 학원실록"
        apt_n = len(s.get("apartments") or [])
        desc = (f"{reg} {s['name']} 위치와 배정 정보."
                + (f" 배정 아파트 {apt_n}단지." if apt_n else "")
                + f" {s.get('foundation','')} {s.get('coed','')}").strip()
        rows = [("학교급", s.get("levelLabel")), ("학군", reg),
                ("설립", s.get("foundation")), ("남녀공학", s.get("coed")),
                ("주소", s.get("address")), ("법정동", s.get("dong"))]
        apts = s.get("apartments") or []
        certain = s.get("level") == "elementary" and any(a.get("certain") for a in apts)
        if s.get("zoneName"):
            rows.append(("학구", s["zoneName"]))
        if apts:
            rows.append(("배정 아파트",
                         f"{len(apts)}단지"
                         + (f" · {s['apartmentHouseholds']:,}세대"
                            if s.get("apartmentHouseholds") else "")))

        body = [f"<h1>{esc(s['name'])}</h1>",
                f'<p class="sub">{esc(reg)} · {esc(s.get("levelLabel"))}</p>',
                "<table>" + "".join(
                    f"<tr><th>{esc(k)}</th><td>{esc(v) or '—'}</td></tr>"
                    for k, v in rows) + "</table>"]

        if apts:
            body.append("<h2>" + ("이 학교로 배정되는 아파트"
                                  if certain else "이 학교군에 속한 아파트") + "</h2>")
            body.append("<ul>" + "".join(
                f"<li>{esc(a['name'])}"
                + (f" — {a['households']:,}세대" if a.get("households") else "")
                + "</li>" for a in apts[:40]) + "</ul>")
            body.append("<p>" + ("초등학교는 통학구역이 1:1 이라 배정이 확정됩니다. "
                                 "구역은 해마다 조정될 수 있으니 관할 교육지원청 공고를 확인하세요."
                                 if certain else
                                 "중·고등학교는 학교군 추첨이라 반드시 이 학교로 배정되는 것은 아닙니다.")
                        + "</p>")

        body.append(f'<a class="cta" href="{SITE}/#/map">학군지도에서 위치 보기</a>')
        ld = {"@context": "https://schema.org", "@type": "School",
              "name": s["name"], "url": f"{SITE}/s/{sid}.html", "areaServed": reg}
        if s.get("address"):
            ld["address"] = {"@type": "PostalAddress",
                             "streetAddress": s["address"], "addressCountry": "KR"}
        if s.get("lat"):
            ld["geo"] = {"@type": "GeoCoordinates",
                         "latitude": s["lat"], "longitude": s["lng"]}
        (out / "s" / f"{sid}.html").write_text(
            page(title, desc, f"{SITE}/s/{sid}.html", "\n".join(body), ld,
                 [("학원실록", f"{SITE}/"), (reg, f"{SITE}/g/{s.get('regionId')}.html"),
                  (s["name"], f"{SITE}/s/{sid}.html")]), encoding="utf-8")
        urls.append(f"{SITE}/s/{sid}.html")
    return urls


def region_pages(out: Path, regions, academies, registry, schools, meta) -> list[str]:
    urls = []
    (out / "g").mkdir(parents=True, exist_ok=True)
    for r in regions:
        rid, name = r["id"], r["name_ko"]
        acs = [a for a in academies if a.get("regionId") == rid]
        allac = acs + [a for a in registry if a.get("regionId") == rid]
        sch = [s for s in schools if s.get("regionId") == rid]
        ranked = sorted([a for a in acs if a.get("score", {}).get("isRanked")],
                        key=lambda a: -a["score"]["total"])[:20]

        title = f"{name} 학원·학교 — 학군 정보 | 학원실록"
        desc = (f"{name} 학군의 학원 {len(allac):,}곳과 학교 {len(sch)}곳. "
                f"NEIS 공시로 검증하고 커뮤니티 신호로 읽은 학군 정보.")

        body = [f"<h1>{esc(name)} 학군</h1>",
                f'<p class="sub">{esc(r.get("tagline",""))}</p>',
                f"<p>등록 학원 <strong>{len(allac):,}곳</strong> · "
                f"채점 완료 {len(acs)}곳 · 학교 {len(sch)}곳 "
                f"({', '.join(r['dong_list'])})</p>"]

        if ranked:
            body.append(f"<h2>{esc(name)} 학원 트리스코어 상위</h2><ul>")
            for a in ranked:
                nm = a.get("displayName") or a["name"]
                body.append(f'<li><a href="{SITE}/a/{a["id"]}.html">{esc(nm)}</a>'
                            f' — {a["score"]["total"]:.0f}점'
                            f' (표본 {a["score"]["sampleSize"]}건)</li>')
            body.append("</ul>")

        for lv, label in (("elementary", "초등학교"), ("middle", "중학교"), ("high", "고등학교")):
            rows = [s for s in sch if s.get("level") == lv]
            if rows:
                body.append(f"<h2>{esc(name)} {label} {len(rows)}곳</h2><ul>")
                body += [f'<li><a href="{SITE}/s/{s["id"]}.html">{esc(s["name"])}</a>'
                         f' — {esc(s.get("foundation",""))}</li>' for s in rows]
                body.append("</ul>")

        body.append(f'<a class="cta" href="{SITE}/#/rank">{esc(name)} 전체 랭킹 보기</a>')

        # AEO: 답변 엔진이 그대로 인용할 수 있는 문답 구조
        faq = [
            (f"{name} 학군에 학원이 몇 곳 있나요?",
             f"NEIS 공시 기준 {name} 학군(={', '.join(r['dong_list'])})에 "
             f"학원·교습소가 {len(allac):,}곳 등록돼 있습니다. "
             f"이 중 {len(acs)}곳을 트리스코어로 채점했습니다."),
            (f"{name} 학군에는 어떤 학교가 있나요?",
             f"초등학교 {sum(1 for s in sch if s['level']=='elementary')}곳, "
             f"중학교 {sum(1 for s in sch if s['level']=='middle')}곳, "
             f"고등학교 {sum(1 for s in sch if s['level']=='high')}곳이 있습니다."),
            ("트리스코어는 어떻게 계산되나요?",
             f"{formula_line(meta, ', ')}를 합산합니다. "
             f"유효 표본 {min_sample(meta)}건 미만은 순위에서 제외합니다. "
             f"자세한 산식은 {SITE}/method.html 에 전부 공개합니다."),
        ]
        body.append("<h2>자주 묻는 질문</h2>")
        for q, a_ in faq:
            body.append(f"<h3>{esc(q)}</h3><p>{esc(a_)}</p>")

        ld = [{"@context": "https://schema.org", "@type": "FAQPage",
               "mainEntity": [{"@type": "Question", "name": q,
                               "acceptedAnswer": {"@type": "Answer", "text": a_}}
                              for q, a_ in faq]}]
        (out / "g" / f"{rid}.html").write_text(
            page(title, desc, f"{SITE}/g/{rid}.html", "\n".join(body), ld,
                 [("학원실록", f"{SITE}/"), (name, f"{SITE}/g/{rid}.html")]),
            encoding="utf-8")
        urls.append(f"{SITE}/g/{rid}.html")
    return urls


def track_pages(out: Path, tracks, academies) -> list[str]:
    urls = []
    (out / "t").mkdir(parents=True, exist_ok=True)
    for t in tracks:
        tid = t["id"]
        band = BANDS.get(t.get("grade_band"), "")
        title = f"{t['title']} 테크트리 — 학원 진학 경로 | 학원실록"
        # 학년대를 설명에 박아 둔다. '초4 수학학원' 같은 검색어가 실제로 많다.
        desc = t.get("summary") or f"{t['title']} 진학 경로와 단계별 학원."
        if band and band not in desc:
            desc = f"{band} 구간. {desc}"
        body = [f"<h1>{esc(t['title'])} 테크트리</h1>",
                f'<p class="sub">{esc(t.get("summary",""))}</p>']
        for st in t["stages"]:
            body.append(f"<h2>{esc(st['title'])}"
                        + (f" — {esc(st.get('subtitle'))}" if st.get("subtitle") else "")
                        + "</h2>")
            if st.get("goal"):
                body.append(f"<p><strong>목표</strong> {esc(st['goal'])}</p>")
            if st.get("exit_criteria"):
                body.append(f"<p><strong>다음 단계 기준</strong> {esc(st['exit_criteria'])}</p>")
            rows = [a for a in academies if st["id"] in (a.get("stages") or [])][:12]
            if rows:
                body.append("<ul>")
                body += [f'<li><a href="{SITE}/a/{a["id"]}.html">'
                         f'{esc(a.get("displayName") or a["name"])}</a></li>' for a in rows]
                body.append("</ul>")
        body.append(f'<a class="cta" href="{SITE}/#/tree">테크트리 그래프로 보기</a>')
        (out / "t" / f"{tid}.html").write_text(
            page(title, desc, f"{SITE}/t/{tid}.html", "\n".join(body), None,
                 [("학원실록", f"{SITE}/"), (t["title"], f"{SITE}/t/{tid}.html")]),
            encoding="utf-8")
        urls.append(f"{SITE}/t/{tid}.html")
    return urls


def method_page(out: Path, meta) -> list[str]:
    """산식 공개 페이지의 정적 판본.

    앱에도 같은 페이지가 있지만 그것은 해시 라우트(/#/method)라 서버로
    전달되지 않는다. 크롤러가 그 주소를 받으면 빈 SPA 껍데기를 받는다 —
    llms.txt 가 AI 답변 엔진에게 인용하라고 안내하던 주소가 바로 그것이었다.
    실명 사업자를 점수로 줄 세우면서 계산 방법을 못 읽게 두면 공개한 것이 아니다.
    """
    parts = formula_parts(meta)
    ms = min_sample(meta)
    prior = (meta or {}).get("reputationPriorCount", 12)
    half = (meta or {}).get("recencyHalflifeDays", 180)

    b = []
    b.append("<h1>트리스코어는 어떻게 계산되나요</h1>")
    b.append('<p class="sub">학원실록은 랭킹 산식을 공개합니다. 점수가 어떻게 나왔는지 '
             '설명할 수 없다면, 그 점수로 학원을 줄 세울 자격도 없다고 봅니다.</p>')

    b.append("<h2>산식</h2>")
    b.append("<p><strong>트리스코어 = " + esc(formula_line(meta)) + "</strong></p>")
    b.append(f"<p>유효 표본 {ms}건 미만은 순위를 매기지 않습니다. "
             f"표본이 0건이면 점수 자체를 내지 않습니다 — 근거가 없는 것과 "
             f"점수가 낮은 것은 다른 상태입니다.</p>")

    b.append("<h2>네 기둥</h2>")
    for name, pct in parts:
        key = next(k for k, v in PILLAR_NAMES.items() if v == name)
        b.append(f"<h3>{esc(name)} · {pct}%</h3><ul>")
        for line in PILLAR_DETAIL.get(key, []):
            b.append(f"<li>{esc(line)}</li>")
        b.append("</ul>")

    if len(parts) >= 4:
        b.append("<h2>무엇을 가장 무겁게 보나요</h2>")
        b.append(f"<p>가장 무겁게 두는 것은 {esc(parts[0][0])} {parts[0][1]}%, "
                 f"{esc(parts[1][0])} {parts[1][1]}% 입니다. 학부모가 실제로 묻는 것이 "
                 f"‘평이 좋은가’와 ‘가고 싶어도 갈 수 있는가’ 둘이기 때문입니다. "
                 f"들어가기 어렵다는 사실 자체가 수요의 가장 정직한 표현이고, 자리가 남는 "
                 f"학원과 대기를 거는 학원을 같은 저울에 놓으면 지금 학원가의 현황이 "
                 f"보이지 않습니다.</p>")
        b.append(f"<p>나머지는 {esc(parts[2][0])} {parts[2][1]}%, "
                 f"{esc(parts[3][0])} {parts[3][1]}% 입니다. 화제성은 좋고 나쁨이 아니라 "
                 f"‘지금 많이 이야기되는가’일 뿐이고, 투명성은 공시를 성실히 했는지를 볼 뿐 "
                 f"수업의 질과는 다른 이야기이기 때문입니다.</p>")

    b.append("<h2>표본이 적으면 순위를 매기지 않습니다</h2>")
    b.append("<p>후기 3건으로 만점을 받은 학원이 후기 200건으로 평균을 받은 학원보다 위에 "
             "오는 것은 통계가 아니라 사고입니다. 그래서 두 가지 장치를 둡니다.</p>")
    b.append(f"<p>첫째, 베이지안 축소. 모든 학원의 평판 점수를 같은 지역·과목 코호트의 평균 "
             f"쪽으로 {prior}건만큼 끌어당깁니다. 표본이 적을수록 평균에 가깝게 눌립니다.</p>")
    b.append(f"<p>둘째, 최소 표본. 유효 후기 {ms}건 미만인 학원은 순위에서 아예 빼고 별도 "
             f"목록으로 보여줍니다. 점수가 나빠서가 아니라, 적은 표본으로 등수를 매기는 것이 "
             f"그 학원에 부당하기 때문입니다.</p>")

    b.append("<h2>예체능·기타는 두 가지만 봅니다</h2>")
    b.append("<p>미술·음악·체육 학원과 그 외 학원은 평판 60%, 화제성 40% 두 축으로만 순위를 "
             "냅니다. 투명성을 빼는 이유는 예능 학원의 교습과정 공시가 ‘미술’ 한 줄인 경우가 "
             "많아, 상세도를 점수로 치면 학원의 실제 차이가 아니라 공시 습관을 재게 되기 "
             "때문입니다. 진입난이도를 빼는 이유는 레벨테스트나 대기 개념이 없는 곳이 "
             "대부분이라 신호가 잡히지 않기 때문입니다. 없는 것을 0점으로 치면 그것이 곧 "
             "왜곡입니다.</p>")
    b.append("<p>순위는 과목별로만 냅니다. 수학 학원과 미술 학원을 한 줄에 세우면 그 순위가 "
             "무엇을 뜻하는지 설명할 수 없습니다.</p>")

    b.append("<h2>긍정률은 무엇인가요</h2>")
    b.append(f"<p>분모는 의견을 낸 후기만 셉니다. 좋다고도 나쁘다고도 하지 않은 중립 서술은 "
             f"빼고, 긍정과 부정을 표현한 글만 놓고 그중 긍정의 비율을 냅니다. 중립까지 넣으면 "
             f"어디나 25~40%에 몰려 변별이 되지 않습니다 — 국내 커뮤니티 글에는 정보 전달 "
             f"위주의 중립 서술이 많기 때문입니다. 유효 후기가 {ms}건 미만이면 표시하지 "
             f"않습니다. 설문으로 받은 추천 의향이 아니므로 다른 서비스의 추천율과 같은 값이 "
             f"아닙니다.</p>")

    b.append("<h2>최근 글에 더 무게를 둡니다</h2>")
    b.append(f"<p>학원은 강사가 바뀌고 반 편성이 바뀝니다. 3년 전 후기와 지난달 후기가 같은 "
             f"무게일 수 없습니다. 그래서 모든 글에 반감기 {half}일의 감쇠를 겁니다 — 6개월 된 "
             f"글은 0.37, 1년 된 글은 0.13의 무게를 받습니다. 평판·화제성·진입난이도 모두에 "
             f"적용됩니다.</p>")
    b.append("<p>작성일을 알 수 없는 글(카페 검색 결과는 날짜를 주지 않습니다)은 6개월 된 글과 "
             "같은 무게로 둡니다. 모르는 것을 최신으로도, 오래된 것으로도 취급하지 않기 "
             "위해서입니다.</p>")

    b.append("<h2>과목마다 따로 셉니다</h2>")
    b.append("<p>한 학원이 여러 과목을 가르치는 것은 정상입니다. 하지만 랭킹은 과목마다 따로 "
             "매깁니다. 수학 후기가 수백 건인 종합학원이 그 점수를 그대로 들고 과학 랭킹 상위에 "
             "오르면, 그 순위는 ‘이 학원의 과학이 좋다’가 아니라 ‘이 학원이 유명하다’를 뜻하게 "
             "되기 때문입니다.</p>")
    b.append("<p>과목 판별은 학원 이름 근처(앞뒤 45자)에 나온 과목어만 봅니다. 글 전체에서 "
             "찾으면 지역 잡담이 전부 그 학원의 근거가 됩니다. 과목을 밝히지 않은 후기는 그 "
             "학원의 대표 과목에만 넣습니다.</p>")

    b.append("<h2>지점을 가려서 셉니다</h2>")
    b.append("<p>유명 학원은 여러 곳에 지점이 있는데 후기는 브랜드 이름으로 쓰입니다. 그대로 "
             "두면 분당 지점 후기가 대치 지점의 점수가 됩니다. 글이 지역을 밝히면 그 권역의 "
             "지점만 근거로 삼고, 네 학군 밖(분당·평촌·송도 등)을 가리키는 글은 어느 지점에도 "
             "넣지 않습니다.</p>")
    b.append("<p>글이 지역을 밝히지 않으면 이름이 걸리는 지점 전부에 똑같이 반영하고 ‘지점 불명 "
             "· 브랜드 공통’으로 표시합니다 — 같은 글이 여러 지점에 보이는 것은 오류가 "
             "아닙니다. 지역 판별은 제목을 우선합니다. 본문에 나오는 지역 이름은 다른 학원의 "
             "상호에 박혀 있는 경우가 많기 때문입니다.</p>")

    b.append("<h2>후기마다 무게가 다릅니다</h2>")
    b.append("<p>커뮤니티에서 수집한 글이 가장 낮습니다. 작성자를 확인할 수 없고 광고가 섞이기 "
             "때문입니다. 로그인해 남긴 후기는 그보다 높고, 재원 증빙이 확인된 후기가 가장 "
             "높습니다. 재원 인증에 만점을 주지는 않습니다 — 확인한 것은 ‘실제로 다녔다’이지 "
             "‘이 평가가 옳다’가 아니기 때문입니다.</p>")

    b.append("<h2>광고와 후기를 어떻게 구분하나요</h2>")
    b.append("<p>체험단·원고료·협찬 문구, 연락처와 외부 링크, 해시태그 도배, 같은 어절의 기계적 "
             "반복 — 이런 신호를 모아 게시물마다 스팸 점수를 매깁니다. 0.6을 넘으면 점수 "
             "계산에서 제외하고, 그 아래여도 신뢰도 가중치를 그만큼 깎습니다. 한 작성자가 같은 "
             "학원에 네 번 이상 등장하면 바이럴로 보고 가중치를 반비례로 줄입니다.</p>")

    b.append("<h2>교습비를 쓰지 않는 이유</h2>")
    b.append("<p>NEIS 공시는 금액을 주지만 교습시간을 주지 않습니다. 주 2회 26만원과 주 5회 "
             "26만원이 같은 값으로 나란히 서게 됩니다. 비교가 성립하지 않는 숫자를 화면에 "
             "올리면 그것은 정보가 아니라 오해의 원인입니다. 그래서 점수에서도 화면에서도 "
             "뺐습니다.</p>")

    b.append("<h2>등급반별 난이도를 내놓지 않는 이유</h2>")
    b.append("<p>반 이름 주변에서 난이도·대기 언급을 세어 만들어 봤지만 되지 않았습니다. 채점 "
             "대상 400곳 전체에서 반 이름과 난이도 표현이 함께 붙은 글이 186건뿐이었고, 계산 "
             "결과도 기초반이 최상위반보다 어렵게 나왔습니다. 숫자를 내면 정밀해 보이지만 "
             "근거가 없습니다. 대신 테크트리의 단계별 진입 기준을 보세요.</p>")

    b.append("<h2>데이터는 어디서 오나요</h2>")
    b.append("<table>"
             "<tr><th>NEIS 학원교습소정보</th>"
             "<td>학원명·주소·정원·교습과정·등록상태 (공공데이터)</td></tr>"
             "<tr><th>네이버 검색 오픈 API</th>"
             "<td>카페글·블로그·지식iN 스니펫 (공식 API)</td></tr>"
             "<tr><th>큐레이션 테크트리</th>"
             "<td>단계 구성과 진급 경로 (직접 작성)</td></tr></table>")

    b.append("<h2>무엇을 하지 않나요</h2><ul>")
    for line in [
        "게시물 본문을 저장하거나 재배포하지 않습니다. 원문은 링크로만 안내합니다.",
        "작성자의 아이디·닉네임을 저장하지 않습니다. 중복 판별용 해시만 남깁니다.",
        "광고비를 받고 순위를 바꾸지 않습니다.",
        "표본이 부족한 학원에 순위를 붙이지 않습니다.",
        "‘최악의 학원’ 같은 하위 랭킹을 만들지 않습니다.",
        "수집을 거부한 사이트의 글을 가져오지 않습니다. robots.txt 를 먼저 확인하고 "
        "도구를 바꿔 우회하지 않습니다.",
        "근거가 모자란 지표를 만들어 내지 않습니다. 교습비와 등급반별 난이도가 그래서 "
        "빠져 있습니다.",
    ]:
        b.append(f"<li>{esc(line)}</li>")
    b.append("</ul>")

    b.append("<h2>이해상충 고지</h2>")
    b.append("<p>학원실록의 운영사 Open Edu 는 1:1 원어민 영어 교육 사업을 함께 운영합니다. "
             "영어 과목의 평가에 이해상충 소지가 있으므로 이를 명시합니다. Open Edu 의 자체 "
             "서비스는 랭킹 대상에 포함하지 않습니다.</p>")

    b.append("<h2>틀린 것을 발견하셨다면</h2>")
    b.append("<p>정정을 요청해 주세요. 접수한 내용은 사람이 확인하고 처리합니다.</p>")
    b.append(f'<a class="cta" href="{SITE}/#/method">정정 요청하기</a>')

    gen = (meta or {}).get("generatedAt", "")
    cnt = (meta or {}).get("mentionCount", 0)
    b.append(f'<p class="sub">데이터 생성 시각: {esc(gen) or "—"} · 분석 글 {cnt:,}건</p>')

    title = "트리스코어 산식 — 학원 랭킹 계산 방법 전면 공개 | 학원실록"
    desc = ("학원실록이 학원 순위를 매기는 방법을 전부 공개합니다. "
            + formula_line(meta, ", ")
            + f". 유효 표본 {ms}건 미만은 순위를 매기지 않습니다.")
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "트리스코어는 어떻게 계산되나요",
        "description": desc,
        "inLanguage": "ko-KR",
        "url": f"{SITE}/method.html",
        "publisher": {"@type": "Organization", "name": "Open Edu",
                      "url": f"{SITE}/openedu/"},
    }
    if gen:
        ld["dateModified"] = gen[:10]
    (out / "method.html").write_text(
        page(title, desc, f"{SITE}/method.html", "\n".join(b), ld,
             [("학원실록", f"{SITE}/"), ("트리스코어 산식", f"{SITE}/method.html")]),
        encoding="utf-8")
    return [f"{SITE}/method.html"]


def write_sitemap(out: Path, urls: list[str]) -> None:
    from datetime import date
    today = date.today().isoformat()
    # 사이트맵 하나에 5만 URL 제한. 여유 있게 2만씩 쪼갠다.
    chunks = [urls[i:i + 20000] for i in range(0, len(urls), 20000)] or [[]]
    names = []
    for i, chunk in enumerate(chunks):
        nm = "sitemap.xml" if len(chunks) == 1 else f"sitemap-{i + 1}.xml"
        names.append(nm)
        entries = "\n".join(
            f"  <url><loc>{u}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>weekly</changefreq></url>" for u in chunk)
        (out / nm).write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'{entries}\n</urlset>\n', encoding="utf-8")
    if len(chunks) > 1:
        idx = "\n".join(f"  <sitemap><loc>{SITE}/{n}</loc>"
                        f"<lastmod>{today}</lastmod></sitemap>" for n in names)
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'{idx}\n</sitemapindex>\n', encoding="utf-8")


def write_llms_txt(out: Path, counts: dict, meta) -> None:
    """AI 답변 엔진용 안내문. 사이트가 무엇이고 무엇을 인용해도 되는지 밝힌다."""
    (out / "llms.txt").write_text(f"""# 학원실록 (Hakwon Silok)

> 대치·목동·반포·잠실 학군의 학원과 학교 정보를 공공데이터로 검증하고
> 커뮤니티 신호로 읽어 정리한 서비스입니다. 운영: Open Edu.

## 데이터 규모
- 등록 학원 {counts['academies']:,}곳 (NEIS 학원교습소정보 공시 기준)
- 학교 {counts['schools']}곳 (NEIS 학교기본정보)
- 분석한 커뮤니티 글 {counts['mentions']:,}건 (네이버 검색 API)

## 트리스코어 산식 (전면 공개)
{formula_line(meta)}
- 유효 표본 {min_sample(meta)}건 미만은 순위를 매기지 않습니다.
- 유효 표본이 0건이면 점수 자체를 내지 않습니다.
- 평판은 코호트 평균으로 베이지안 축소해 소표본 극단값을 억제합니다.
- 진입난이도는 커뮤니티 언급 기반 추정치이며 공식 경쟁률이 아닙니다.

## 인용 시 유의
- 예체능·기타 학원은 평판 60% + 화제성 40% 로만 채점합니다(다른 저울입니다).
- 트리스코어는 이용자 별점이 아니라 본 서비스가 계산한 지표입니다.
- 교습비·정원·등록상태는 NEIS 공시값으로 검증된 사실입니다.
- 평판·화제성·진입난이도는 추정치입니다.

## 주요 경로
- 학군: {SITE}/g/daechi.html, /g/mokdong.html, /g/banpo.html, /g/jamsil.html
- 학원 상세: {SITE}/a/{{학원지정번호}}.html
- 학교 상세: {SITE}/s/{{학교코드}}.html
- 산식 설명: {SITE}/method.html (전체 산식·기둥별 계산·제외 규칙)
""", encoding="utf-8")


def main(target: str) -> None:
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)

    regions = load("regions.json")
    academies = load("academies.json")
    registry = load("registry.json")
    schools = load("schools.json")
    tracks = (load("techtree.json") or {}).get("tracks", []) if (DATA / "techtree.json").exists() else []
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8")) if (DATA / "meta.json").exists() else {}

    urls = [f"{SITE}/", f"{SITE}/openedu/"]
    urls += method_page(out, meta)
    urls += region_pages(out, regions, academies, registry, schools, meta)
    urls += track_pages(out, tracks, academies)
    urls += school_pages(out, schools, regions)
    urls += academy_pages(out, academies, registry, regions)

    write_sitemap(out, urls)
    write_llms_txt(out, {
        "academies": meta.get("registryCount", len(academies) + len(registry)),
        "schools": len(schools),
        "mentions": meta.get("mentionCount", 0),
    }, meta)
    print(f"정적 SEO 페이지 {len(urls):,}개 생성 → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "_seo"))
