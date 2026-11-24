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
# ★ 다음은 보탬이지 기둥이 아니다 (2026-11-21 결정).
#   다음에 **이번 회차에 실제로 연결을 시도했고 닿지 않은 것**이면 네이버만으로
#   게시한다. 11-20 밤 러너에서 dapi.kakao.com 이 통째로 안 닿아 한 회차가
#   사라졌다 — 랭킹의 근거는 저장소에 쌓여 있고 네이버는 정상이었는데도.
#   범위는 연결 실패뿐이다. 키 거부·한도·한 번도 안 부름은 우리가 고칠 수
#   있는 고장이라 여전히 게시를 막는다. 네이버는 어떤 실패든 막는다.
OPTIONAL_WHEN_UNREACHABLE = ('daum_cafe', 'daum_blog', 'daum_web')
# ★ 일시 장애는 '회차 전체' 로 판정한다 (2026-11-24).
#   상태를 **마지막 요청 하나**로 적고 있었다. 11-24 따라잡기 회차에서 네이버가
#   13분(09:17~09:30 UTC) '서비스 예외'(errorCode 500)와 연결 시간 초과를 냈고,
#   그 전에 요청의 80%가 성공해 블로그 6.6만 건을 받았는데도, 마지막 요청이
#   실패였다는 이유로 게시가 막혔다.
#   → 이번 회차에 시도했고, 실패가 전부 일시 장애(서버 오류·연결 실패)이며,
#     요청의 절반 이상이 성공했으면 게시하고 경고로 남긴다. 키 거부·사용
#     중지·한도 초과는 우리가 고칠 고장이라 지금처럼 막는다.
TRANSIENT_FAILURES = ('network_error', 'server_error')
MIN_SUCCESS_SHARE = 0.5


def reset():
    with _lock:
        _rows.clear()


def record(source, status, count=0):
    with _lock:
        row = _rows.setdefault(source, {"requests": 0, "results": 0, "errors": 0})
        row["requests"] += 1
        row["results"] += count
        row["errors"] += int(status != "available")
        if status != "available":
            failures = row.setdefault("failures", {})
            failures[status] = failures.get(status, 0) + 1
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


def _degraded_but_collected(row):
    """일시 장애가 섞였지만 이번 회차가 실제로 수집한 출처인가."""
    requests, errors = row.get('requests'), row.get('errors')
    failures = row.get('failures')
    if type(requests) is not int or type(errors) is not int or requests < 1:
        return False
    if not isinstance(failures, dict) or not failures:
        return False          # 실패 종류를 모르면 막는다(옛 기록 포함)
    if set(failures) - set(TRANSIENT_FAILURES):
        return False
    ok = requests - errors
    return ok >= 1 and ok / requests >= MIN_SUCCESS_SHARE


def _review(rows, started_at, now):
    problems, warnings = [], []
    for name in REQUIRED_NIGHTLY_SOURCES:
        row = rows.get(name) or {}
        requests = row.get('requests', 0)
        tried = type(requests) is int and requests >= 1
        try:
            checked = datetime.fromisoformat(row['checkedAt'].replace('Z', '+00:00'))
            if checked.tzinfo is None or not started_at <= checked <= now:
                raise ValueError('not a current-run observation')
            current = True
        except (KeyError, AttributeError, TypeError, ValueError):
            current = False
        if (tried and current and row.get('status') != 'available'
                and _degraded_but_collected(row)):
            warnings.append('source_degraded:' + name)
            continue
        if (name in OPTIONAL_WHEN_UNREACHABLE and tried and current
                and row.get('status') == 'network_error'):
            warnings.append('source_unreachable:' + name)
            continue
        if row.get('status') != 'available' or not tried:
            problems.append('source_unavailable:' + name)
        if not current:
            problems.append('not_checked_this_run:' + name)
    return problems, warnings


def collection_problems(rows, started_at, *, now=None):
    """A cached success is not proof that this run contacted both providers."""
    return _review(rows, started_at, now or datetime.now(timezone.utc))[0]


def collection_warnings(rows, started_at, *, now=None):
    """이번 회차에 시도했으나 닿지 않은 다음 소스 — 게시는 하되 숨기지 않는다."""
    return _review(rows, started_at, now or datetime.now(timezone.utc))[1]


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
    warnings = []
    try:
        started = datetime.fromisoformat(json.loads(marker.read_text())['startedAt'])
        if started.tzinfo is None or started > now:
            raise ValueError('invalid start time')
        problems, warnings = _review(load(), started, now)
    except (OSError, KeyError, TypeError, ValueError):
        problems = ['collection_start_unknown']
    report = {'checkedAt': now.isoformat(), 'healthy': not problems,
              'problems': problems, 'warnings': warnings, 'sources': load()}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    unreachable = [w for w in warnings if w.startswith('source_unreachable:')]
    degraded = [w for w in warnings if w.startswith('source_degraded:')]
    # 로그에만 찍으면 아무도 안 본다 — 실행 요약의 경고로 올린다.
    if unreachable:
        print('::warning::다음 검색에 연결하지 못해 네이버만으로 게시합니다: '
              + ', '.join(unreachable))
    if degraded:
        print('::warning::일시 장애로 일부 요청이 실패했지만 절반 이상 수집해 게시합니다: '
              + ', '.join(degraded))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
