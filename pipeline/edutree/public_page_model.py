"""Public facts shared by SEO generation; no scoring or inferred missing facts."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlencode

SUBJECTS = {"math": "수학", "english": "영어", "korean": "국어·논술",
            "science": "과학", "arts": "예체능", "etc": "종합·보습", "general": "과목 미확인"}
BANDS = {"elem_low": "예비초~초3", "elem_high": "초4~초6", "middle": "중등", "high": "고등"}
BASIS = {"official": "공식 안내", "directory": "소개 자료 대조", "registered": "공시",
         "curated": "큐레이션 단계", "reviews": "후기 반복 언급"}


def safe_url(value):
    if not isinstance(value, str) or re.search(r"[\s\\\x00-\x1f]", value.strip()):
        return None
    try:
        p = urlsplit(value.strip())
        _ = p.port  # Reject malformed ports as Dart Uri.tryParse does.
        return value.strip() if p.scheme in ("http", "https") and p.hostname and "@" not in p.netloc else None
    except ValueError:
        return None


def safe_phone(value):
    if not isinstance(value, str) or not re.fullmatch(r"\+?[0-9() .-]+", value.strip()):
        return None
    digits = re.sub(r"\D", "", value)
    if not 8 <= len(digits) <= 13 or re.fullmatch(r"(\d)\1+", digits):
        return None
    if value.strip().startswith("+"):
        return value.strip() if digits.startswith("82") else None
    return value.strip() if digits.startswith("0") or len(digits) == 8 else None


def app_link(route: str, **params) -> str:
    query = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f"/#/{route.lstrip('/')}" + (f"?{query}" if query else "")


def academy_model(a: dict, *, evaluated: bool, generated_at: str = "") -> dict:
    aid = str(a["id"])
    if not re.fullmatch(r"[0-9]+", aid):
        raise ValueError(f"Invalid academy ID: {aid!r}")
    target = a.get("gradeTarget") or {}
    grades = []
    for subject, bands in (target.get("bandBasis") or {}).items():
        if subject not in a.get("subjects", []):
            continue
        for band, basis in bands.items():
            # A raw gradeBands field without evidence is not a verified grade claim.
            if band in BANDS and basis in BASIS:
                grades.append(dict(subject=subject, band=band, basis=basis,
                                   label=f"{SUBJECTS.get(subject, '과목 미확인')} {BANDS[band]}",
                                   basisLabel=BASIS[basis]))
    score = a.get("score") or {}
    return {
        "schemaVersion": 1, "entityId": aid, "kind": "evaluated" if evaluated else "registry_only",
        "canonicalPath": f"/a/{aid}.html", "displayName": a.get("displayName") or a["name"],
        "regionId": a.get("regionId", ""), "address": a.get("address"),
        "subjects": [{"id": s, "label": SUBJECTS.get(s, "과목 미확인")} for s in a.get("subjects", [])],
        "grades": grades, "gradeNote": target.get("caveat"),
        "contact": {"phone": safe_phone(a.get("tel")), "officialUrl": safe_url(a.get("homepage"))},
        "tuition": {"status": "unknown", "amount": None},
        "evidenceStatus": ("available" if score.get("sampleSize") else "no_evidence") if evaluated else "not_collected",
        "dataGeneratedAt": generated_at, "sourceCheckedAt": None,
    }


def validate_aliases(entries: list[dict], entities: dict[str, dict]) -> dict[str, str]:
    """Only an explicit reviewed mapping can create a public compatibility page."""
    aliases = {}
    for row in entries:
        if row.get("status") != "verified":
            continue
        old, new = str(row["oldId"]), str(row["canonicalId"])
        if not re.fullmatch(r"\d+", old) or old == new or old in entities or new not in entities:
            raise ValueError(f"Invalid alias {old} -> {new}")
        if old in aliases or not row.get("evidence") or not row.get("reviewedAt"):
            raise ValueError(f"Unverified or conflicting alias: {old}")
        if old not in [str(i) for i in entities[new].get("registrationIds") or []]:
            raise ValueError(f"Alias is not a registered identity of {new}: {old}")
        aliases[old] = new
    return aliases
