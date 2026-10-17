"""Read GSC exports without extracting ZIP paths or inventing daily dimensions."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import zipfile

from .contracts import Metrics, aggregate

HEADERS = {
    "날짜": "Date", "클릭수": "Clicks", "클릭 수": "Clicks", "노출수": "Impressions",
    "노출 수": "Impressions", "게재 순위": "Position", "평균 게재순위": "Position",
    "인기 검색어": "Top queries", "상위 검색어": "Top queries", "인기 페이지": "Top pages",
    "상위 페이지": "Top pages", "국가": "Country", "기기": "Device",
    "필터": "Filter", "값": "Value", "마지막 크롤링": "Last crawled",
    "영향을 받은 페이지": "Affected pages",
}
FILES = {"Chart.csv": "daily", "Queries.csv": "query", "Pages.csv": "page",
         "Countries.csv": "country", "Devices.csv": "device",
         "Search appearance.csv": "appearance", "Filters.csv": "filters",
         "Table.csv": "index_urls", "Metadata.csv": "metadata"}
DIMENSIONS = {"query": "Top queries", "page": "Top pages", "country": "Country",
              "device": "Device", "appearance": "Search appearance"}


def integer(value: str) -> int:
    cleaned = value.strip().replace(",", "")
    if not re.fullmatch(r"\d+", cleaned):
        raise ValueError(f"INVALID_INTEGER: {value!r}")
    return int(cleaned)


def metric(row: dict) -> dict:
    clicks, impressions = integer(row["Clicks"]), integer(row["Impressions"])
    position = row.get("Position", "").strip()
    if impressions and not position:
        raise ValueError("MISSING_POSITION")
    p = float(position) if position else 0
    if impressions and p < 1:
        raise ValueError("INVALID_POSITION")
    return Metrics(clicks, impressions, p * impressions).to_dict()


def read_export(path: Path, property_id: str, *, exported_at: str | None = None) -> dict:
    raw = path.read_bytes()
    tables = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.infolist()) > 30:
            raise ValueError("TOO_MANY_ZIP_MEMBERS")
        total = 0
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.filename:
                raise ValueError("UNSAFE_ZIP_PATH")
            if entry.is_dir():
                continue
            if len(name.parts) != 1 or name.name not in FILES:
                raise ValueError(f"UNKNOWN_CSV: {entry.filename}")
            if name.name in tables:
                raise ValueError("DUPLICATE_ZIP_MEMBER")
            total += entry.file_size
            if entry.file_size > 32_000_000 or total > 128_000_000:
                raise ValueError("EXPORT_TOO_LARGE")
            text = archive.read(entry).decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            rows = [{HEADERS.get(k, k): v for k, v in row.items()} for row in reader]
            if any(None in row or any(v is None for v in row.values()) for row in rows):
                raise ValueError("MALFORMED_CSV")
            tables[name.name] = rows
    daily = tables.get("Chart.csv", [])
    if not daily:
        raise ValueError("MISSING_CHART")
    dates = [date.fromisoformat(row["Date"]).isoformat() for row in daily]
    if len(set(dates)) != len(dates):
        raise ValueError("DUPLICATE_DATE")
    dates.sort()
    filters = {r["Filter"]: r["Value"] for r in tables.get("Filters.csv", [])}
    is_index = "Affected pages" in daily[0]
    result = {
        "schemaVersion": 1, "property": property_id, "source": "gsc_csv",
        "checksum": hashlib.sha256(raw).hexdigest(), "timezone": "America/Los_Angeles",
        "exportedAt": exported_at or datetime.now(timezone.utc).isoformat(),
        "period": {"start": dates[0], "end": dates[-1]},
        "filters": filters, "searchType": filters.get("Search type", filters.get("검색 유형", "unknown")),
        "kind": "index" if is_index else "performance", "datasets": {}, "warnings": [],
    }
    if is_index:
        result["datasets"] = {
            "index_daily": [{"date": r["Date"], "count": integer(r["Affected pages"])} for r in daily],
            "index_urls": tables.get("Table.csv", []), "metadata": tables.get("Metadata.csv", []),
        }
        return result
    result["datasets"]["property_day"] = sorted(
        [dict(date=r["Date"], **metric(r)) for r in daily], key=lambda r: r["date"])
    for filename, dimension in FILES.items():
        if dimension not in DIMENSIONS or filename not in tables:
            continue
        rows = tables[filename]
        key = DIMENSIONS[dimension]
        items = [dict(key=r[key], **metric(r)) for r in rows]
        if len({r["key"] for r in items}) != len(items):
            raise ValueError(f"DUPLICATE_DIMENSION: {dimension}")
        result["datasets"][dimension] = {
            "grain": "period", "rows": items, "truncated": len(items) >= 1000,
        }
        if len(items) >= 1000:
            result["warnings"].append(f"{dimension.upper()}_ROW_LIMIT_REACHED")
    totals = aggregate(result["datasets"]["property_day"])
    queries = aggregate(result["datasets"].get("query", {}).get("rows", []))
    result["totals"] = totals.to_dict()
    result["queryClickCoverage"] = queries.clicks / totals.clicks if totals.clicks else None
    if queries.clicks != totals.clicks:
        result["warnings"].append("QUERY_ROWS_DO_NOT_EXPLAIN_ALL_CLICKS")
    expected = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
    if len(dates) != expected:
        result["warnings"].append("MISSING_DATES")
    return result
