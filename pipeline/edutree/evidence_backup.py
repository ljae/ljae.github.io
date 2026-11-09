"""Encrypted, bounded evidence checkpoints. Never publish raw source caches."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from datetime import datetime, timezone
import zipfile

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HEADER = b'OpenEdu-cache-v1\0'
TAG = 'evidence-checkpoints'
FILES = ('mention_store.json.gz', 'first_seen.json', 'collect_history.json',
         'neis_academies.json', 'profiles.json', 'claim_llm.json',
         'post_summaries.json', 'blog_texts.json', 'source_health.json')
MAX_BYTES = 512 * 1024 * 1024


def key_bytes(value):
    if not value:
        raise ValueError('OPENEDU_EVIDENCE_BACKUP_KEY is required before collection')
    key = base64.urlsafe_b64decode(value)
    if len(key) != 32:
        raise ValueError('Invalid evidence backup key length')
    return key


def raw_rows(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        payload = f.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError('Evidence store exceeds recovery limit')
    result = json.loads(payload)
    if result.get('version') != 1 or not isinstance(result.get('rows'), dict) or not result['rows']:
        raise ValueError('Valid nonempty evidence store required')
    return result['rows']


def pack(cache, key):
    cache = Path(cache)
    entries = {}
    for name in FILES:
        path = cache / name
        if path.is_symlink():
            raise ValueError('Symlink not allowed in evidence checkpoint')
        if path.is_file():
            before = path.stat()
            entries[name] = path.read_bytes()
            if before.st_mtime_ns != path.stat().st_mtime_ns:
                raise ValueError('Evidence changed during checkpoint')
    if sum(map(len, entries.values())) > MAX_BYTES:
        raise ValueError('Checkpoint too large')
    count = len(raw_rows(entries.get('mention_store.json.gz', b'')))
    if 'first_seen.json' not in entries:
        raise ValueError('First-seen history required; never recreate it as today')
    manifest = {'version': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
                'rawRows': count, 'sha256': {n: hashlib.sha256(b).hexdigest() for n, b in entries.items()}}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        for name, data in entries.items():
            archive.writestr(name, data)
    nonce = secrets.token_bytes(12)
    encrypted = HEADER + nonce + AESGCM(key).encrypt(nonce, out.getvalue(), HEADER)
    return encrypted, manifest


def unpack(data, key):
    if not data.startswith(HEADER) or len(data) > MAX_BYTES:
        raise ValueError('Invalid encrypted checkpoint')
    pos = len(HEADER)
    plain = AESGCM(key).decrypt(data[pos:pos + 12], data[pos + 12:], HEADER)
    with zipfile.ZipFile(io.BytesIO(plain)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) - {*FILES, 'manifest.json'}:
            raise ValueError('Unexpected checkpoint entry')
        if sum(i.file_size for i in archive.infolist()) > MAX_BYTES:
            raise ValueError('Checkpoint expands beyond limit')
        manifest = json.loads(archive.read('manifest.json'))
        entries = {n: archive.read(n) for n in names if n != 'manifest.json'}
    if manifest.get('version') != 1 or set(entries) != set(manifest['sha256']):
        raise ValueError('Checkpoint manifest mismatch')
    for name, body in entries.items():
        if hashlib.sha256(body).hexdigest() != manifest['sha256'][name]:
            raise ValueError('Checkpoint content mismatch')
        if name.endswith('.json'):
            json.loads(body)
    if len(raw_rows(entries['mention_store.json.gz'])) != manifest['rawRows'] or 'first_seen.json' not in entries:
        raise ValueError('Checkpoint evidence/history mismatch')
    return entries, manifest


def restore(data, key, cache):
    entries, manifest = unpack(data, key)  # Authenticate everything before writing.
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for name in entries:
        if (cache / name).is_symlink():
            raise ValueError('Symlink not allowed in recovery destination')
    for name, incoming in entries.items():
        path = cache / name
        if path.exists():
            if name == 'mention_store.json.gz':
                # Preserve independently collected rows as well as the backup.
                rows = raw_rows(incoming)
                try:
                    current = raw_rows(path.read_bytes())
                except (OSError, ValueError, EOFError):
                    current = {}
                for k, v in current.items():
                    if k not in rows:
                        rows[k] = v
                incoming = gzip.compress(json.dumps({'version': 1, 'rows': rows}, ensure_ascii=False).encode(), mtime=0)
            elif name.endswith('.json'):
                old = json.loads(incoming)
                try:
                    current = json.loads(path.read_bytes())
                except ValueError:
                    current = {}
                if isinstance(old, dict) and isinstance(current, dict):
                    for k, v in current.items():
                        if name == 'first_seen.json' and k in old:
                            if isinstance(v, str) and isinstance(old[k], str):
                                old[k] = min(v, old[k])
                        else:
                            old[k] = v
                    incoming = json.dumps(old, ensure_ascii=False).encode()
                else:
                    continue  # Existing live directory data takes precedence.
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as f:
            f.write(incoming)
            temporary = Path(f.name)
        os.replace(temporary, path)
    return manifest


def api(repo, token, path, method='GET', **kwargs):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    response = requests.request(method, 'https://api.github.com/repos/' + repo + path,
                                headers={'Authorization': 'Bearer ' + token,
                                         'Accept': 'application/vnd.github+json'}, timeout=60, **kwargs)
    return response


def release(repo, token, create=False):
    r = api(repo, token, '/releases/tags/' + TAG)
    if r.status_code == 404 and create:
        r = api(repo, token, '/releases', 'POST', json={
            'tag_name': TAG, 'name': 'Encrypted evidence checkpoints', 'prerelease': True,
            'make_latest': 'false', 'body': 'Encrypted recovery state only. No decryption key or raw evidence is published.'})
        if r.status_code == 422:
            return release(repo, token)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def download(asset):
    url = asset['browser_download_url']
    if not url.startswith('https://github.com/'):
        raise ValueError('Unexpected artifact origin')
    # Signed storage redirects must not receive the GitHub bearer token.
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES:
        raise ValueError('Checkpoint download too large')
    return r.content


def recover(cache, seed, key, repo, token, minimum=1):
    cache = Path(cache)
    count = 0
    receipt = {}
    try:
        count = len(raw_rows((cache / 'mention_store.json.gz').read_bytes()))
        receipt = json.loads((cache / 'evidence-checkpoint.json').read_text())
    except (OSError, ValueError, EOFError):
        pass
    info = release(repo, token)
    assets = sorted((a for a in (info or {}).get('assets', [])
                     if a['name'].startswith('evidence-cache-') and a['name'].endswith('.aes')
                     and a.get('state') == 'uploaded'), key=lambda a: a['created_at'], reverse=True)
    if (assets and receipt.get('assetId') == assets[0]['id']
            and count >= max(minimum, receipt.get('rawRows', 0))
            and (cache / 'first_seen.json').is_file()):
        return {'source': 'verified_current_cache', 'rawRows': count}
    if assets:
        data = download(assets[0])
    elif Path(seed).is_file():
        data = Path(seed).read_bytes()
    else:
        parts = sorted(Path(seed).parent.glob(Path(seed).name + '.part[0-9][0-9]'))
        if not parts or sum(p.stat().st_size for p in parts) > MAX_BYTES:
            raise ValueError('Encrypted recovery seed missing or oversized')
        data = b''.join(p.read_bytes() for p in parts)
    _, manifest = unpack(data, key)
    if manifest['rawRows'] < minimum:
        raise ValueError('Checkpoint is too small for the published evidence baseline')
    restore(data, key, cache)
    if assets:
        (cache / 'evidence-checkpoint.json').write_text(json.dumps({
            'assetId': assets[0]['id'], 'rawRows': manifest['rawRows']}))
    return {'source': 'encrypted_checkpoint' if assets else 'encrypted_ORICO_recovery_seed',
            'rawRows': manifest['rawRows'], 'archiveCreatedAt': manifest['createdAt']}


def checkpoint(cache, key, repo, token):
    body, manifest = pack(cache, key)
    info = release(repo, token, create=True)
    digest = hashlib.sha256(body).hexdigest()
    name = 'evidence-cache-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + digest[:12] + '.aes'
    url = info['upload_url'].split('{', 1)[0]
    if not url.startswith('https://uploads.github.com/repos/' + repo + '/'):
        raise ValueError('Unexpected upload origin')
    r = requests.post(url, params={'name': name}, data=body, timeout=180,
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/octet-stream'})
    r.raise_for_status()
    saved = r.json()
    if saved.get('state') != 'uploaded' or saved.get('size') != len(body):
        raise ValueError('Checkpoint upload not confirmed')
    if hashlib.sha256(download(saved)).hexdigest() != digest:
        raise ValueError('Checkpoint download verification failed')
    # Prune only our previous checkpoints, after verifying the replacement.
    old = sorted((a for a in info.get('assets', []) if a['name'].startswith('evidence-cache-')
                  and a['name'].endswith('.aes') and a.get('state') == 'uploaded'),
                 key=lambda a: a['created_at'], reverse=True)
    for a in old[2:]:
        try:
            response = api(repo, token, '/releases/assets/' + str(a['id']), 'DELETE')
        except requests.RequestException:
            print('Checkpoint retained; older-asset cleanup deferred')
            break
        if response.status_code != 204:
            print('Checkpoint retained; older-asset cleanup deferred')
    result = {'asset': name, 'assetId': saved['id'], 'sha256': digest,
              'rawRows': manifest['rawRows'], 'bytes': len(body), 'verified': True}
    (Path(cache) / 'evidence-checkpoint.json').write_text(json.dumps(result))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['restore', 'checkpoint'])
    p.add_argument('--cache', type=Path, default=Path('pipeline/.cache'))
    p.add_argument('--seed', type=Path, default=Path('pipeline/data/evidence-recovery.aes'))
    args = p.parse_args()
    key = key_bytes(os.environ.get('OPENEDU_EVIDENCE_BACKUP_KEY'))
    repo, token = os.environ['GH_REPO'], os.environ['GH_TOKEN']
    if args.command == 'restore':
        meta = json.loads(Path('app/assets/data/meta.json').read_text())
        minimum = max(1, int(meta.get('rankingQuality', {}).get('validMentions', 0)))
        result = recover(args.cache, args.seed, key, repo, token, minimum)
    else:
        result = checkpoint(args.cache, key, repo, token)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
