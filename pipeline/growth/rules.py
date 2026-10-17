"""Evidence-driven findings; uncertainty is part of the output."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from .contracts import aggregate, stable_hash, normalize_query


def finding(rule_id, subject, severity, title, evidence, **details):
    return dict(id=stable_hash([rule_id, subject, evidence]), ruleId=rule_id,
                subjectKey=subject, severity=severity, title=title, evidence=evidence,
                observedAt=datetime.now(timezone.utc).isoformat(), state="proposed", **details)


def detect_drop(rows: list[dict]) -> list[dict]:
    """Find an abrupt, sustained break using complete 7-day windows."""
    by_date = {r["date"]: r for r in rows}
    found = []
    for d in sorted(by_date):
        day = date.fromisoformat(d)
        before = [(day + timedelta(days=i)).isoformat() for i in range(-7, 0)]
        after = [(day + timedelta(days=i)).isoformat() for i in range(7)]
        if any(k not in by_date for k in before + after):
            continue
        prev = aggregate([by_date[k] for k in before])
        curr = aggregate([by_date[k] for k in after])
        yesterday = by_date[before[-1]]["impressions"]
        if prev.impressions < 100 or not yesterday:
            continue
        if curr.impressions / prev.impressions > .3 or by_date[d]["impressions"] / yesterday > .3:
            continue
        found.append(finding("traffic.sustained_drop.v1", d, "P0", "검색 노출 급감 원인 확인",
            {"before": before, "after": after, "previous": prev.to_dict(), "current": curr.to_dict()},
            confidence="observed", cause="insufficient_evidence",
            decrease=1-curr.impressions/prev.impressions,
            nextAction="필터·수집 누락, 배포, HTTP, canonical, 색인·크롤, 삭제 요청을 대조하세요."))
    return found


def classify_query(query: str) -> list[str]:
    q = normalize_query(query)
    tags = []
    for label, terms in {
        'service_brand': ('학원실록', 'open edu', 'openedu', '에듀트리'),
        'cost': ('학원비', '수강료', '교습비', '비용'),
        'level_test': ('레벨테스트', '레테', '입학시험'),
        'comparison': ('비교', '추천', '어디'),
        'school_zone': ('배정', '통학', '학구'),
        'reviews': ('후기', '리뷰'),
    }.items():
        if any(term in q for term in terms):
            tags.append(label)
    return tags or ['unknown']


def analyze(snapshot: dict, inventory: dict | None = None, entities=None) -> dict:
    if snapshot["kind"] != "performance":
        raise ValueError("PERFORMANCE_SNAPSHOT_REQUIRED")
    datasets = snapshot["datasets"]
    findings = detect_drop(datasets["property_day"])
    for dimension in ("page", "query"):
        if datasets.get(dimension, {}).get("truncated"):
            findings.append(finding("data.row_limit.v1", dimension, "P1", "내보내기 행 제한 확인",
                {"rows": len(datasets[dimension]["rows"])}, confidence="confirmed",
                nextAction="공식 API를 일별로 수집하세요. 이 표를 전수 목록으로 사용하지 않습니다."))
    if inventory:
        for issue in inventory.get("issues", []):
            findings.append(finding(issue["ruleId"], issue["url"], issue["severity"],
                issue["title"], issue.get("evidence", {}), confidence="code_verified"))
    page_rows = datasets.get("page", {}).get("rows", [])
    research = []
    for row in page_rows:
        if row['impressions'] < 10:
            continue
        path = urlsplit(row['key']).path
        aid = path.split('/')[-1].removesuffix('.html') if path.startswith('/a/') else None
        a = (entities or {}).get(aid)
        if not a:
            continue
        missing = []
        if not (a.get('gradeTarget') or {}).get('bandBasis'):
            missing.append('grade_target')
        if not a.get('tel') and not a.get('homepage'):
            missing.append('verified_contact')
        if (a.get('subjects') or []) == ['general']:
            missing.append('subject')
        if missing:
            findings.append(finding('content.fact_gap.v1', f'academy:{aid}', 'P1',
                f'{a.get("displayName") or a["name"]} 정보 확인',
                dict(url=row['key'], missing=missing, period=snapshot['period'],
                     impressions=row['impressions'], clicks=row['clicks']),
                confidence='current_data_verified',
                nextAction='주소·지점을 대조한 공식 모집 안내와 연락 경로를 확인하세요. 검색어로 학년·과목을 확정하지 않습니다.'))
            research.append(dict(academyId=aid, missing=missing, source='gsc_page',
                                 impressions=row['impressions'], status='candidate'))
    return {
        "schemaVersion": 1, "property": snapshot["property"], "period": snapshot["period"],
        "source": snapshot["source"], "asOf": snapshot["exportedAt"],
        "totals": snapshot["totals"], "daily": datasets["property_day"],
        "quality": {"warnings": snapshot["warnings"],
                    "queryClickCoverage": snapshot["queryClickCoverage"],
                    "pageRowsTruncated": datasets.get("page", {}).get("truncated", False)},
        "pages": sorted(page_rows, key=lambda r: -r["impressions"]),
        "queries": [dict(r, normalizedQuery=normalize_query(r['key']), intentTags=classify_query(r['key']))
                    for r in sorted(datasets.get("query", {}).get("rows", []), key=lambda r: -r["impressions"])],
        "researchQueue": research,
        "findings": sorted(findings, key=lambda f: (f["severity"],
            -f['evidence'].get('impressions', 0), f["subjectKey"])),
        "evaluation": "insufficient_evidence" if snapshot["totals"]["clicks"] < 20 else "not_evaluated",
    }
