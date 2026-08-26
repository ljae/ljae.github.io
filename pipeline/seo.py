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
<p>출처: NEIS 학원·학교 공시정보, 네이버 검색 API. 산식은 <a href="{SITE}/#/method">공개</a>합니다.</p>
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


def region_pages(out: Path, regions, academies, registry, schools) -> list[str]:
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
             "평판 35%, 화제성 20%, 투명성 25%, 진입난이도 20%를 합산합니다. "
             "유효 표본 10건 미만은 순위에서 제외합니다."),
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


def write_llms_txt(out: Path, counts: dict) -> None:
    """AI 답변 엔진용 안내문. 사이트가 무엇이고 무엇을 인용해도 되는지 밝힌다."""
    (out / "llms.txt").write_text(f"""# 학원실록 (Hakwon Silok)

> 대치·목동·반포·잠실 학군의 학원과 학교 정보를 공공데이터로 검증하고
> 커뮤니티 신호로 읽어 정리한 서비스입니다. 운영: Open Edu.

## 데이터 규모
- 등록 학원 {counts['academies']:,}곳 (NEIS 학원교습소정보 공시 기준)
- 학교 {counts['schools']}곳 (NEIS 학교기본정보)
- 분석한 커뮤니티 글 {counts['mentions']:,}건 (네이버 검색 API)

## 트리스코어 산식 (전면 공개)
평판 35% + 화제성 20% + 투명성 25% + 진입난이도 20%
- 유효 표본 10건 미만은 순위를 매기지 않습니다.
- 평판은 코호트 평균으로 베이지안 축소해 소표본 극단값을 억제합니다.
- 진입난이도는 커뮤니티 언급 기반 추정치이며 공식 경쟁률이 아닙니다.

## 인용 시 유의
- 트리스코어는 이용자 별점이 아니라 본 서비스가 계산한 지표입니다.
- 교습비·정원·등록상태는 NEIS 공시값으로 검증된 사실입니다.
- 평판·화제성·진입난이도는 추정치입니다.

## 주요 경로
- 학군: {SITE}/g/daechi.html, /g/mokdong.html, /g/banpo.html, /g/jamsil.html
- 학원 상세: {SITE}/a/{{학원지정번호}}.html
- 학교 상세: {SITE}/s/{{학교코드}}.html
- 산식 설명: {SITE}/#/method
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
    urls += region_pages(out, regions, academies, registry, schools)
    urls += track_pages(out, tracks, academies)
    urls += school_pages(out, schools, regions)
    urls += academy_pages(out, academies, registry, regions)

    write_sitemap(out, urls)
    write_llms_txt(out, {
        "academies": meta.get("registryCount", len(academies) + len(registry)),
        "schools": len(schools),
        "mentions": meta.get("mentionCount", 0),
    })
    print(f"정적 SEO 페이지 {len(urls):,}개 생성 → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "_seo"))
