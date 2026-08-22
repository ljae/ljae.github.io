"""네이버 카페 심층 수집 — 로컬 전용 · 옵트인 모듈.

┌──────────────────────────────────────────────────────────────────┐
│ 읽고 시작하세요                                                    │
│                                                                  │
│ 네이버 카페 게시물은 검색 오픈 API가 스니펫까지만 돌려줍니다.        │
│ 본문 전체를 긁는 것은 네이버 이용약관에 어긋나고, 로그인 세션이       │
│ 필요하며, 계정 정지와 법적 분쟁의 소지가 있습니다.                   │
│                                                                  │
│ 그래서 이 모듈은 이렇게 만들었습니다.                               │
│   1. 기본값이 '꺼짐'입니다. 환경변수로 명시적으로 켜야 동작합니다.    │
│   2. 로그인을 대신 하지 않습니다. 아이디·비밀번호를 받지 않고,       │
│      저장하지도 않습니다.                                          │
│   3. 서비스는 이 모듈 없이도 전 기능이 동작합니다. 산출물은          │
│      집계 신호로만 반영되며, 원문은 저장·재배포하지 않습니다.        │
│   4. 배포 파이프라인(GitHub Actions)에서는 절대 실행되지 않습니다.   │
└──────────────────────────────────────────────────────────────────┘

동작 방식 두 가지
  A. 로컬 HTML 인제스트 (기본 · 권장)
     본인이 브라우저에서 직접 열어 저장한 카페 페이지(.html)를 폴더에
     넣어두면, 그 파일들만 파싱합니다. 자동 접속을 하지 않으므로
     약관·차단·계정 문제에서 자유롭습니다.

  B. 기존 로그인 브라우저 프로필 재사용 (수동 옵트인)
     Playwright 로 '본인이 이미 로그인해 둔' Chrome 프로필을 열어
     페이지를 읽습니다. 자동 로그인을 수행하지 않습니다.
     실행 전 스스로 판단하십시오. 책임은 실행하는 사람에게 있습니다.

사용
    export EDUTREE_ENABLE_CAFE_SCRAPER=1
    export EDUTREE_CAFE_HTML_DIR=~/edutree_cafe_pages
    python pipeline/run.py --with-cafe
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

ENABLE_FLAG = "EDUTREE_ENABLE_CAFE_SCRAPER"
HTML_DIR_ENV = "EDUTREE_CAFE_HTML_DIR"

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t ]+")
_DATE = re.compile(r"(20\d{2})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})")


class CafeModuleDisabled(RuntimeError):
    """모듈이 꺼져 있을 때. 정상 상황이므로 파이프라인은 계속 진행한다."""


def is_enabled() -> bool:
    return os.getenv(ENABLE_FLAG, "").strip() in ("1", "true", "yes")


def _guard() -> None:
    if not is_enabled():
        raise CafeModuleDisabled(
            f"카페 수집 모듈이 꺼져 있습니다. 켜려면 {ENABLE_FLAG}=1 을 설정하세요. "
            "(서비스는 이 모듈 없이도 정상 동작합니다.)"
        )
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        raise RuntimeError(
            "이 모듈은 CI 환경에서 실행할 수 없습니다. 로컬에서만 사용하세요."
        )


def html_to_text(raw: str) -> str:
    body = _TAG.sub(" ", raw)
    body = _ANY_TAG.sub(" ", body)
    body = (body.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    lines = [_WS.sub(" ", line).strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_title(raw: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    return _ANY_TAG.sub("", m.group(1)).strip() if m else ""


def _extract_date(text: str) -> str | None:
    m = _DATE.search(text)
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def ingest_local_html(academies: list[dict]) -> list[dict]:
    """방식 A — 직접 저장해 둔 카페 페이지를 파싱한다.

    학원명·별칭이 본문에 등장하는 파일만 해당 학원의 언급으로 잡는다.
    한 글에 여러 학원이 언급되면 각각에 귀속시킨다(실제로 비교 글이 많다).
    """
    _guard()
    directory = Path(os.path.expanduser(os.getenv(HTML_DIR_ENV, ""))).resolve()
    if not directory.is_dir():
        raise RuntimeError(
            f"{HTML_DIR_ENV} 가 가리키는 폴더가 없습니다: {directory}\n"
            "브라우저에서 저장한 카페 페이지(.html)를 넣어둘 폴더를 지정하세요."
        )

    # 학원명/별칭 → 학원 키
    lookup: list[tuple[str, dict]] = []
    for a in academies:
        names = {a.get("brand") or a["name"], a["name"], *(a.get("aliases") or [])}
        for n in names:
            if len(n) >= 2:
                lookup.append((n, a))

    mentions: list[dict] = []
    files = sorted(p for p in directory.rglob("*.htm*") if p.is_file())
    print(f"  카페 HTML {len(files)}개 파싱 중 ({directory})")

    for path in files:
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"    ! 읽기 실패 {path.name}: {exc}")
            continue

        text = html_to_text(raw)
        if len(text) < 60:
            continue
        title = _extract_title(raw)
        posted = _extract_date(text)
        flat = text.replace(" ", "")

        hit_keys: set[str] = set()
        for needle, academy in lookup:
            if needle.replace(" ", "") in flat and academy["id"] not in hit_keys:
                hit_keys.add(academy["id"])
                mentions.append({
                    "source": "cafe_local",
                    # 로컬 파일이므로 공개 URL이 없다. 파일명만 근거로 남긴다.
                    "source_url": f"local://{path.name}",
                    "url_hash": hashlib.sha256(
                        f"{path.name}|{academy['id']}".encode()).hexdigest()[:32],
                    "author_hash": None,      # 작성자 정보는 수집하지 않는다
                    "title": title[:200],
                    # 본문 전체를 저장하지 않는다. 분석에 필요한 만큼만 남긴다.
                    "snippet": _relevant_window(text, needle),
                    "posted_at": posted,
                    "academy_key": academy["id"],
                    "academy_name": academy["name"],
                    "region_id": academy.get("region_id"),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "is_local": True,
                })
    print(f"  카페 로컬 인제스트: {len(mentions)}건")
    return mentions


def _relevant_window(text: str, needle: str, width: int = 220) -> str:
    """학원명 주변 문맥만 잘라낸다. 본문 전재를 피하기 위한 장치."""
    idx = text.find(needle)
    if idx < 0:
        return text[:width]
    start = max(0, idx - width // 2)
    return text[start:start + width].replace("\n", " ").strip()


def collect_with_browser(urls: list[str], profile_dir: str) -> list[dict]:
    """방식 B — 이미 로그인된 브라우저 프로필을 재사용해 페이지를 읽는다.

    이 함수는 로그인을 수행하지 않는다. 아이디·비밀번호를 인자로 받지 않으며
    받더라도 쓰지 않는다. 이미 사람이 로그인해 둔 프로필을 열 뿐이다.

    Playwright 가 설치돼 있어야 한다:
        pip install playwright && playwright install chromium
    """
    _guard()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright 가 설치돼 있지 않습니다.\n"
            "  pip install playwright && playwright install chromium"
        ) from exc

    print("  ⚠ 브라우저 모드로 실행합니다. 네이버 이용약관과 robots.txt 를 "
          "확인하고 본인 책임 하에 사용하세요.")

    out: list[dict] = []
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=os.path.expanduser(profile_dir),
            headless=False,          # 사람이 보고 있어야 한다. 무인 자동화가 아니다.
        )
        page = context.new_page()
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                page.wait_for_timeout(1500)     # 사람이 읽는 속도로 천천히
                text = html_to_text(page.content())
                out.append({
                    "source": "cafe_local",
                    "source_url": url,
                    "url_hash": hashlib.sha256(url.encode()).hexdigest()[:32],
                    "author_hash": None,
                    "title": page.title()[:200],
                    "snippet": text[:400],
                    "posted_at": _extract_date(text),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "is_local": True,
                })
            except Exception as exc:      # noqa: BLE001 — 한 페이지 실패로 전체를 멈추지 않는다
                print(f"    ! {url}: {exc}")
        context.close()
    return out


def try_collect(academies: list[dict]) -> list[dict]:
    """파이프라인에서 부르는 진입점. 꺼져 있으면 조용히 빈 목록을 준다."""
    try:
        return ingest_local_html(academies)
    except CafeModuleDisabled as exc:
        print(f"  (건너뜀) {exc}")
        return []
    except RuntimeError as exc:
        print(f"  ! 카페 모듈 오류: {exc}")
        return []
