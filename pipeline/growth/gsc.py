"""Read-only GSC transport and atomic day partitions. Credentials stay in CI."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import os
import random
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from .contracts import Metrics, aggregate, stable_hash

DATASETS = {"property_day": ["date"], "page": ["date", "page"],
            "query": ["date", "query"], "device": ["date", "device"],
            "country": ["date", "country"], "query_page": ["date", "query", "page"]}


class GscError(RuntimeError):
    def __init__(self, code, retryable=False):
        super().__init__(code)
        self.retryable = retryable


class GscClient:
    def __init__(self, *, session=None, token_provider=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.token_provider = token_provider or self.oauth_token
        self.sleep = sleep
        self._token = None

    def oauth_token(self):
        required = [os.environ.get(k) for k in ("GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN")]
        if not all(required):
            raise GscError("AUTH_REQUIRED")
        response = self.session.post("https://oauth2.googleapis.com/token", timeout=30,
            data=dict(grant_type="refresh_token", client_id=required[0], client_secret=required[1], refresh_token=required[2]))
        if response.status_code != 200:
            raise GscError("AUTH_REQUIRED")
        return response.json()["access_token"]

    def request(self, url, body):
        refreshed = False
        for attempt in range(5):
            if not self._token:
                self._token = self.token_provider()
            try:
                response = self.session.post(url, json=body, timeout=60,
                    headers={"Authorization": f"Bearer {self._token}"})
            except requests.RequestException:
                if attempt == 4:
                    raise GscError("SOURCE_UNAVAILABLE", True) from None
                self.sleep(min(2**attempt + random.random(), 30))
                continue
            if response.status_code == 401 and not refreshed:
                self._token = None
                refreshed = True
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt == 4:
                    raise GscError("QUOTA_OR_SOURCE_UNAVAILABLE", True)
                self.sleep(min(2**attempt + random.random(), 30))
                continue
            if response.status_code == 401:
                raise GscError("AUTH_REQUIRED")
            if response.status_code == 403:
                raise GscError("PROPERTY_ACCESS_REQUIRED")
            if response.status_code != 200:
                # Never print response bodies: they may contain account metadata.
                raise GscError(f"GSC_HTTP_{response.status_code}")
            return response.json()
        raise GscError("SOURCE_UNAVAILABLE", True)

    def query_day(self, property_id, day, dataset, *, search_type="web", row_limit=25000):
        url = f"https://www.googleapis.com/webmasters/v3/sites/{quote(property_id, safe='')}/searchAnalytics/query"
        rows = []
        start = 0
        aggregation = None
        while True:
            body = dict(startDate=day, endDate=day, type=search_type, dataState="final",
                        dimensions=DATASETS[dataset], rowLimit=row_limit, startRow=start,
                        aggregationType="byProperty" if dataset == "property_day" else "auto")
            result = self.request(url, body)
            current_aggregation = result.get("responseAggregationType")
            if aggregation is not None and aggregation != current_aggregation:
                raise ValueError("AGGREGATION_CHANGED_DURING_PAGINATION")
            aggregation = current_aggregation
            batch = result.get("rows", [])
            for r in batch:
                keys = r.get("keys", [])
                if len(keys) != len(DATASETS[dataset]) or keys[0] != day:
                    raise ValueError("INVALID_GSC_DIMENSIONS")
                if not float(r["clicks"]).is_integer() or not float(r["impressions"]).is_integer():
                    raise ValueError("INVALID_GSC_COUNTS")
                if r['impressions'] and r.get('position', 0) < 1:
                    raise ValueError('INVALID_GSC_POSITION')
                m = Metrics(int(r["clicks"]), int(r["impressions"]), r.get("position", 0)*r["impressions"])
                rows.append(dict(keys=keys, **m.to_dict()))
            if len(batch) < row_limit:
                break
            if start >= 100000:
                raise GscError("PARTITION_ROW_BUDGET_EXCEEDED")
            start += row_limit
        if len({tuple(r["keys"]) for r in rows}) != len(rows):
            raise ValueError("DUPLICATE_API_DIMENSIONS")
        return dict(rows=rows, aggregationType=aggregation, dataState="final",
                    topRowsOnly=dataset in ("query", "page", "query_page"))

    def inspect(self, property_id, url):
        return self.request("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                            dict(siteUrl=property_id, inspectionUrl=url, languageCode="ko-KR"))


def sync(client, store, property_id, start, end, search_type="web"):
    start_day, end_day = date.fromisoformat(start), date.fromisoformat(end)
    # Do not turn not-yet-available dates into zeros. The default is deliberately delayed.
    last_safe_day = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=3)
    if start_day > end_day or end_day > last_safe_day:
        raise ValueError("INVALID_OR_NOT_FINAL_DATE_RANGE")
    count = 0
    day = start_day
    while day <= end_day:
        key = day.isoformat()
        # Commit only when every dimension for this day succeeds; keep the previous day on failure.
        partition = {name: client.query_day(property_id, key, name, search_type=search_type) for name in DATASETS}
        store.put_partition(property_id, search_type, key, partition)
        count += 1
        day += timedelta(days=1)
    return count


def api_snapshot(store, property_id, start, end, search_type="web"):
    parts = store.partitions(property_id, search_type, start, end)
    dates = [(date.fromisoformat(start)+timedelta(days=i)).isoformat()
             for i in range((date.fromisoformat(end)-date.fromisoformat(start)).days+1)]
    if set(parts) != set(dates):
        raise ValueError("INCOMPLETE_PARTITION")
    daily = []
    grouped = {name: {} for name in DATASETS if name != "property_day"}
    for day in dates:
        totals = aggregate(parts[day]["property_day"]["rows"])
        daily.append(dict(date=day, **totals.to_dict()))
        for name in grouped:
            for row in parts[day][name]["rows"]:
                dimensions = row["keys"][1:]
                # Tuple JSON avoids collisions from user queries containing separators.
                key = tuple(dimensions)
                target = grouped[name].setdefault(key, dict(keys=dimensions, clicks=0, impressions=0, position_numerator=0))
                for field in ("clicks", "impressions", "position_numerator"):
                    target[field] += row[field]
    datasets = {"property_day": daily}
    for name, rows in grouped.items():
        datasets[name] = dict(grain="period", truncated=False, sourceLimited=True, rows=[
            dict(key=r["keys"][0] if len(r["keys"]) == 1 else list(r["keys"]),
                 **Metrics(r["clicks"], r["impressions"], r["position_numerator"]).to_dict()) for r in rows.values()])
    totals, queries = aggregate(daily), aggregate(datasets["query"]["rows"])
    snapshot = dict(schemaVersion=1, property=property_id, source="gsc_api_final", kind="performance",
                    timezone="America/Los_Angeles", searchType=search_type,
                    exportedAt=datetime.now(ZoneInfo("UTC")).isoformat(), period=dict(start=start, end=end),
                    filters={"Search type": search_type}, datasets=datasets, totals=totals.to_dict(),
                    queryClickCoverage=queries.clicks/totals.clicks if totals.clicks else None,
                    warnings=["API_TOP_ROWS_NOT_EXHAUSTIVE"])
    snapshot["checksum"] = stable_hash([property_id, search_type, start, end, datasets])
    return snapshot
