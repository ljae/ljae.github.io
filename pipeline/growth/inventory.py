"""Public HTML inventory with private, persistent semantic change tracking."""
from __future__ import annotations

from datetime import date
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

# Separate GitHub Pages project application, HTTP 200 verified 2026-10-17.
# It is served on the domain but is not part of this repository's artifact.
EXTERNALLY_MANAGED_PATHS = {'/world_math/'}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.links = []
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "meta" and a.get("name") == "robots":
            self.noindex = "noindex" in a.get("content", "")


def semantic_hash(document: str) -> str:
    # Export freshness is useful to a reader but is not a substantive fact change.
    document = re.sub(r'<p[^>]*data-generated-at="true"[^>]*>.*?</p>', '', document, flags=re.S)
    return hashlib.sha256(document.encode()).hexdigest()


def inventory(site_dir: Path, urls: list[str], *, previous=None, today=None,
              aliases=None, notices=None, allow_removals=False) -> dict:
    if not urls or len(urls) != len(set(urls)):
        raise ValueError("EMPTY_OR_DUPLICATE_SITEMAP")
    previous = previous or {"pages": {}}
    today = today or date.today().isoformat()
    pages, issues = {}, []
    for url in urls:
        path = urlsplit(url).path
        file = site_dir / (path.lstrip('/') or "index.html")
        if path.endswith('/'):
            file = site_dir / path.lstrip('/') / "index.html"
        if not file.is_file():
            raise ValueError(f"SITEMAP_FILE_MISSING: {url}")
        document = file.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(document)
        if parser.noindex or parser.canonical != url:
            raise ValueError(f"SITEMAP_NOT_CANONICAL_OR_INDEXABLE: {url}")
        digest = semantic_hash(document)
        old = previous.get("pages", {}).get(url)
        # First inventory has no trustworthy historic modification date.
        updated = old.get("semanticUpdatedAt") if old else None
        if old and old.get("semanticHash") != digest:
            updated = today
        pages[url] = {"semanticHash": digest, "semanticUpdatedAt": updated,
                      "canonical": parser.canonical, "outgoingUrls": parser.links,
                      "pageType": path.strip('/').split('/')[0] if path not in ('/', '/index.html') else 'home'}
        for link in parser.links:
            full = urlsplit(urljoin(url, link))
            if full.netloc != urlsplit(url).netloc:
                continue
            broken = None
            if full.fragment.startswith('/'):
                route = full.fragment.split('?', 1)[0]
                if route.startswith('/academy/'):
                    aid = route.split('/')[-1]
                    if not (site_dir / 'a' / f'{aid}.html').is_file():
                        broken = "학원 상세가 없는 앱 경로"
                elif route.split('/')[1] not in ('', 'rank', 'tree', 'map', 'method', 'admin', 'board', 'sources', 'compare'):
                    broken = "알 수 없는 앱 경로"
            elif full.path:
                if full.path in EXTERNALLY_MANAGED_PATHS:
                    continue
                target = site_dir / full.path.lstrip('/')
                if full.path.endswith('/'):
                    target /= 'index.html'
                if not target.is_file():
                    broken = "존재하지 않는 내부 링크"
            if broken:
                issues.append(dict(ruleId="route.broken_internal_link.v1", url=url, severity="P0",
                                   title=broken, evidence={"href": link}))
    removed = sorted(set(previous.get("pages", {})) - set(pages))
    known_aliases = aliases or {}
    compatibility = {}
    origin = urlsplit(urls[0])
    for old_id, canonical_id in known_aliases.items():
        old_url = f'{origin.scheme}://{origin.netloc}/a/{old_id}.html'
        target_url = f'{origin.scheme}://{origin.netloc}/a/{canonical_id}.html'
        file = site_dir / 'a' / f'{old_id}.html'
        parser = PageParser()
        if file.is_file():
            parser.feed(file.read_text(encoding='utf-8'))
        if target_url not in pages or parser.canonical != target_url or parser.noindex:
            raise ValueError(f'INVALID_COMPATIBILITY_PAGE: {old_url}')
        compatibility[old_url] = target_url
    removed_compatibility = sorted(set(previous.get('compatibilityUrls', {})) - set(compatibility) - set(pages))
    unavailable = {}
    for aid, checked_at in (notices or {}).items():
        if not re.fullmatch(r'\d+', str(aid)) or not checked_at:
            raise ValueError('INVALID_UNAVAILABLE_PAGE')
        url = f'{origin.scheme}://{origin.netloc}/a/{aid}.html'
        parser = PageParser()
        file = site_dir / 'a' / f'{aid}.html'
        if file.is_file():
            parser.feed(file.read_text(encoding='utf-8'))
        if url in pages or url in compatibility or parser.canonical != url or not parser.noindex:
            raise ValueError(f'INVALID_UNAVAILABLE_PAGE: {url}')
        unavailable[url] = checked_at
    missing_notices = set(previous.get('unavailableUrls', {})) - set(unavailable) - set(pages) - set(compatibility)
    unexpected = [url for url in removed if url not in compatibility and url not in unavailable]
    removed_compatibility = [url for url in removed_compatibility if url not in unavailable]
    if (unexpected or removed_compatibility or missing_notices) and not allow_removals:
        raise ValueError(f"UNEXPECTED_URL_REMOVAL: {len(unexpected)+len(removed_compatibility)+len(missing_notices)} URLs; review lifecycle/alias records first")
    if issues:
        raise ValueError(f"BROKEN_INTERNAL_LINKS: {json.dumps(issues[:8], ensure_ascii=False)}")
    return {"schemaVersion": 1, "generatedAt": today, "templateVersion": "search-detail-v2",
            "pages": pages, "compatibilityUrls": compatibility, "unavailableUrls": unavailable,
            "removed": removed + removed_compatibility, "issues": issues}


def save_manifest(path: Path, manifest: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
