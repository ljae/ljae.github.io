"""출처별 실제 접근 상태. 성공 0건과 권한/네트워크 실패를 구분한다."""
import argparse
import json
import threading
from datetime import datetime, timezone

from . import config

PATH = config.CACHE_DIR / "source_health.json"
_lock = threading.Lock()
_rows = {}
REQUIRED_NIGHTLY_SOURCES = ('naver_cafe', 'naver_blog', 'daum_cafe',
                            'daum_blog', 'daum_web')


def reset():
    with _lock:
        _rows.clear()


def record(source, status, count=0):
    with _lock:
        row = _rows.setdefault(source, {"requests": 0, "results": 0, "errors": 0})
        row["requests"] += 1
        row["results"] += count
        row["errors"] += int(status != "available")
        row["status"] = status
        row["checkedAt"] = datetime.now(timezone.utc).isoformat()


def save():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(_rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load():
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def collection_problems(rows, started_at, *, now=None):
    """A cached success is not proof that this run contacted both providers."""
    now = now or datetime.now(timezone.utc)
    problems = []
    for name in REQUIRED_NIGHTLY_SOURCES:
        row = rows.get(name) or {}
        requests = row.get('requests', 0)
        if (row.get('status') != 'available' or type(requests) is not int
                or requests < 1):
            problems.append('source_unavailable:' + name)
        try:
            checked = datetime.fromisoformat(row['checkedAt'].replace('Z', '+00:00'))
            if checked.tzinfo is None or not started_at <= checked <= now:
                raise ValueError('not a current-run observation')
        except (KeyError, AttributeError, TypeError, ValueError):
            problems.append('not_checked_this_run:' + name)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify nightly Naver and Daum collection')
    parser.add_argument('action', choices=('start', 'check'))
    args = parser.parse_args(argv)
    marker = config.CACHE_DIR / 'nightly-source-start.json'
    report_path = config.CACHE_DIR / 'nightly-source-check.json'
    if args.action == 'start':
        # Run before any source calls; never silently skip Daum or use demo data.
        marker.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        missing = [name for name, ready in (
            ('NEIS_API_KEY', config.HAS_NEIS),
            ('NAVER_CLIENT_ID / NAVER_CLIENT_SECRET', config.HAS_NAVER),
            ('KAKAO_REST_API_KEY', config.HAS_DAUM)) if not ready]
        if missing:
            print('Missing nightly source credentials: ' + ', '.join(missing))
            return 1
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({'startedAt': datetime.now(timezone.utc).isoformat()}))
        return 0
    now = datetime.now(timezone.utc)
    try:
        started = datetime.fromisoformat(json.loads(marker.read_text())['startedAt'])
        if started.tzinfo is None or started > now:
            raise ValueError('invalid start time')
        problems = collection_problems(load(), started, now=now)
    except (OSError, KeyError, TypeError, ValueError):
        problems = ['collection_start_unknown']
    report = {'checkedAt': now.isoformat(), 'healthy': not problems,
              'problems': problems, 'sources': load()}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
