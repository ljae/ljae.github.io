"""python -m pipeline.growth.cli --help"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree

from .csv_import import read_export
from .rules import analyze
from .store import Store

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description="검색 유입 분석 · 학원 점수와 분리된 운영 도구")
    parser.add_argument("--db", type=Path, default=ROOT / "pipeline/.cache/growth/ledger.sqlite")
    subs = parser.add_subparsers(dest="command", required=True)
    imp = subs.add_parser("import-csv")
    imp.add_argument("--input", type=Path, required=True)
    imp.add_argument("--property", default="sc-domain:openedu4u.com")
    imp.add_argument("--exported-at")
    imp.add_argument("--dry-run", action="store_true")
    report = subs.add_parser("analyze")
    report.add_argument("--property", default="sc-domain:openedu4u.com")
    report.add_argument("--snapshot")
    report.add_argument("--inventory", type=Path)
    report.add_argument("--output", type=Path)
    view = subs.add_parser("report")
    view.add_argument("--property", default="sc-domain:openedu4u.com")
    view.add_argument("--output", type=Path, default=ROOT/'pipeline/.cache/growth/report.html')
    sync_parser = subs.add_parser("sync-gsc")
    sync_parser.add_argument("--property", default="sc-domain:openedu4u.com")
    sync_parser.add_argument("--start", required=True)
    sync_parser.add_argument("--end", required=True)
    sync_parser.add_argument("--search-type", default="web", choices=['web','image','video','news'])
    pub = subs.add_parser("publish")
    pub.add_argument("--property", default="sc-domain:openedu4u.com")
    pub.add_argument("--snapshot")
    pub.add_argument("--data-dir", type=Path, default=ROOT/'app/assets/data')
    report.add_argument("--data-dir", type=Path, default=ROOT/'app/assets/data')
    view.add_argument("--data-dir", type=Path, default=ROOT/'app/assets/data')
    aliases = subs.add_parser("alias-candidates")
    aliases.add_argument("--property", default="sc-domain:openedu4u.com")
    aliases.add_argument("--data-dir", type=Path, default=ROOT / 'app/assets/data')
    inv = subs.add_parser('inventory')
    inv.add_argument('--site-dir', type=Path, required=True)
    inv.add_argument('--previous-manifest', type=Path)
    inv.add_argument('--output', type=Path, default=ROOT/'pipeline/.cache/growth/page-manifest.json')
    args = parser.parse_args(argv)
    store = None
    try:
        if args.command == 'inventory':
            from .inventory import inventory, save_manifest
            root = ElementTree.parse(args.site_dir/'sitemap.xml').getroot()
            urls = [node.text for node in root.findall('.//{*}loc')]
            if root.tag.endswith('sitemapindex'):
                urls = [node.text for url in urls for node in ElementTree.parse(args.site_dir/url.split('/')[-1]).getroot().findall('.//{*}loc')]
            previous = json.loads(args.previous_manifest.read_text()) if args.previous_manifest else None
            public_aliases = json.loads((ROOT/'pipeline/data/url_aliases.json').read_text())
            aliases = {a['oldId']:a['canonicalId'] for a in public_aliases['entries'] if a.get('status')=='verified'}
            result = inventory(args.site_dir, urls, previous=previous, aliases=aliases)
            save_manifest(args.output, result)
            result = dict(output=str(args.output),pages=len(result['pages']),issues=len(result['issues']))
        elif args.command == "import-csv":
            snapshot = read_export(args.input, args.property, exported_at=args.exported_at)
            if args.dry_run:
                result = snapshot
            else:
                store = Store(args.db)
                key, inserted = store.import_snapshot(snapshot)
                result = dict(id=key, inserted=inserted, period=snapshot["period"],
                              kind=snapshot["kind"], totals=snapshot.get("totals"),
                              warnings=snapshot["warnings"])
        elif args.command == 'sync-gsc':
            from .gsc import GscClient, sync, api_snapshot
            store = Store(args.db)
            count = sync(GscClient(), store, args.property, args.start, args.end, args.search_type)
            snapshot = api_snapshot(store, args.property, args.start, args.end, args.search_type)
            key, inserted = store.import_snapshot(snapshot)
            result = dict(id=key, inserted=inserted, days=count, totals=snapshot['totals'])
        elif args.command == 'alias-candidates':
            store = Store(args.db)
            indexes = store.snapshots(args.property, kind='index')
            if not indexes:
                raise ValueError('SOURCE_UNAVAILABLE: 색인 CSV를 먼저 수입하세요')
            entities = []
            for name in ('academies.json','registry.json'):
                entities += json.loads((args.data_dir / name).read_text())
            mapping = {}
            for a in entities:
                for old in a.get('registrationIds') or []:
                    mapping.setdefault(str(old), []).append(str(a['id']))
            result = [dict(oldUrl=r['URL'], canonicalCandidates=mapping.get(r['URL'].split('/')[-1].removesuffix('.html'), []),
                           status='candidate_needs_identity_check') for r in indexes[0]['datasets']['index_urls']]
        else:
            store = Store(args.db)
            snapshots = store.snapshots(args.property)
            snapshot = next((s for s in snapshots if not getattr(args,'snapshot',None) or s["id"] == args.snapshot), None)
            if not snapshot:
                raise ValueError("SOURCE_UNAVAILABLE: CSV를 먼저 수입하세요")
            inventory = json.loads(args.inventory.read_text()) if getattr(args, 'inventory', None) else None
            entities = {}
            for name in ('academies.json','registry.json'):
                path = args.data_dir/name
                if path.exists():
                    entities.update({str(a['id']):a for a in json.loads(path.read_text())})
            result = analyze(snapshot, inventory, entities)
            if args.command == 'publish':
                from .publish import publish
                result = publish(snapshot['id'], snapshot, result)
            elif args.output:
                # Reports contain private queries. Never write under a deployable directory.
                target = args.output.resolve()
                for public in (ROOT / "_site", ROOT / "app/assets", ROOT / "app/build", ROOT / "openedu", ROOT / "app/web"):
                    if target.is_relative_to(public):
                        raise ValueError("PRIVATE_REPORT_PUBLIC_PATH")
                target.parent.mkdir(parents=True, exist_ok=True)
                if args.command == 'report':
                    from .report import render
                    reports = [analyze(s, entities=entities) for s in snapshots]
                    target.write_text(render(reports))
                    result = dict(output=str(target),snapshots=len(reports))
                else:
                    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, KeyError, zipfile.BadZipFile, UnicodeDecodeError) as e:
        print(f"INVALID_INPUT: {e}", file=sys.stderr)
        return 3
    except OSError as e:
        print(f"SOURCE_UNAVAILABLE: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 4 if getattr(e, 'retryable', False) else 2
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
