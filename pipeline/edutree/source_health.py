"""출처별 실제 접근 상태. 성공 0건과 권한/네트워크 실패를 구분한다."""
import json
import threading
from datetime import datetime, timezone

from . import config

PATH = config.CACHE_DIR / "source_health.json"
_lock = threading.Lock()
_rows = {}


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
