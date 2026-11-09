import gzip
import json
from pathlib import Path
import secrets

import pytest
from cryptography.exceptions import InvalidTag
from pipeline.edutree import evidence_backup as backup


def make_cache(path, key='old', first='2026-09-01'):
    path.mkdir(parents=True, exist_ok=True)
    (path/'mention_store.json.gz').write_bytes(gzip.compress(json.dumps({
        'version': 1, 'rows': {key: {'academy_key': '123', 'snippet': 'original',
                                  'first_seen': first, 'date_source': 'publication'}}}).encode()))
    (path/'first_seen.json').write_text(json.dumps({key: first}))
    (path/'.env').write_text('MUST_NOT_BE_BACKED_UP=synthetic')


def test_encrypted_roundtrip_preserves_dates_and_excludes_secrets(tmp_path):
    src, dst = tmp_path/'src', tmp_path/'dst'
    make_cache(src)
    key = secrets.token_bytes(32)
    encrypted, manifest = backup.pack(src, key)
    assert b'original' not in encrypted
    entries, decoded = backup.unpack(encrypted, key)
    assert set(entries) == {'mention_store.json.gz', 'first_seen.json'}
    assert manifest['rawRows'] == decoded['rawRows'] == 1
    backup.restore(encrypted, key, dst)
    assert backup.raw_rows((dst/'mention_store.json.gz').read_bytes())['old']['first_seen'] == '2026-09-01'
    assert not (dst/'.env').exists()


def test_wrong_key_or_tamper_never_writes_recovery_files(tmp_path):
    src, dst = tmp_path/'src', tmp_path/'dst'
    make_cache(src)
    key = secrets.token_bytes(32)
    encrypted, _ = backup.pack(src, key)
    for body, used_key in [(encrypted, secrets.token_bytes(32)),
                           (encrypted[:-1] + bytes([encrypted[-1] ^ 1]), key)]:
        with pytest.raises(InvalidTag):
            backup.restore(body, used_key, dst)
        assert not dst.exists()


def test_partial_cache_merge_keeps_both_histories_and_earliest_discovery(tmp_path):
    src, dst = tmp_path/'src', tmp_path/'dst'
    make_cache(src)
    make_cache(dst, key='new', first='2026-10-01')
    (dst/'first_seen.json').write_text(json.dumps({'old': '2026-11-09', 'new': '2026-10-01'}))
    key = secrets.token_bytes(32)
    encrypted, _ = backup.pack(src, key)
    backup.restore(encrypted, key, dst)
    rows = backup.raw_rows((dst/'mention_store.json.gz').read_bytes())
    assert set(rows) == {'old', 'new'}
    assert json.loads((dst/'first_seen.json').read_text())['old'] == '2026-09-01'


def test_empty_store_and_symlinks_fail_closed(tmp_path):
    src = tmp_path/'src'
    make_cache(src)
    (src/'profiles.json').symlink_to(src/'.env')
    with pytest.raises(ValueError, match='Symlink'):
        backup.pack(src, secrets.token_bytes(32))
    (src/'profiles.json').unlink()
    (src/'mention_store.json.gz').write_bytes(gzip.compress(b'{"version":1,"rows":{}}'))
    with pytest.raises(ValueError, match='nonempty'):
        backup.pack(src, secrets.token_bytes(32))


def test_missing_cache_restores_seed_and_too_small_checkpoint_cannot_pass(tmp_path, monkeypatch):
    src = tmp_path/'src'; make_cache(src)
    key = secrets.token_bytes(32); body, _ = backup.pack(src, key)
    seed = tmp_path/'seed.aes'; seed.write_bytes(body)
    monkeypatch.setattr(backup, 'release', lambda *args: None)
    with pytest.raises(ValueError, match='too small'):
        backup.recover(tmp_path/'bad', seed, key, 'owner/repo', 'synthetic', minimum=2)
    assert not (tmp_path/'bad').exists()
    result = backup.recover(tmp_path/'good', seed, key, 'owner/repo', 'synthetic')
    assert result['source'] == 'encrypted_ORICO_recovery_seed'


def test_continuity_checks_and_checkpoint_precede_source_publication():
    import yaml
    root = Path(__file__).resolve().parents[2]
    steps = yaml.safe_load((root/'.github/workflows/collect.yml').read_text())['jobs']['collect']['steps']
    names = [s.get('name') for s in steps]
    assert names.index('Verify evidence continuity and restore encrypted checkpoint') < names.index('수집 · 채점')
    assert names.index('Verify durable encrypted evidence checkpoint before publication') < names.index('Supabase 업로드 (키가 있을 때만)') < names.index('변경분 커밋')


def test_verified_checkpoint_is_required_before_older_backups_are_pruned(tmp_path, monkeypatch):
    cache = tmp_path/'cache'; make_cache(cache)
    key = secrets.token_bytes(32)
    old = [{'id': i, 'name': f'evidence-cache-{i}.aes', 'created_at': str(i),
            'state': 'uploaded'} for i in range(1, 5)]
    old.append({'id': 99, 'name': 'unrelated-file.txt', 'created_at': '9', 'state': 'uploaded'})
    info = {'upload_url': 'https://uploads.github.com/repos/owner/repo/releases/1/assets{?name}',
            'assets': old}
    monkeypatch.setattr(backup, 'release', lambda *args, **kwargs: info)
    received, deleted = {}, []

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'id': 5, 'state': 'uploaded', 'size': len(received['body']),
                    'browser_download_url': 'https://github.com/owner/repo/releases/download/evidence-checkpoints/new.aes'}

    def post(url, **kwargs):
        assert url.startswith('https://uploads.github.com/repos/owner/repo/')
        assert kwargs['headers']['Authorization'] == 'Bearer synthetic'
        received['body'] = kwargs['data']
        return Response()

    def remove(repo, token, path, method):
        assert method == 'DELETE'
        deleted.append(path)
        return type('Deleted', (), {'status_code': 204})()

    monkeypatch.setattr(backup.requests, 'post', post)
    monkeypatch.setattr(backup, 'api', remove)
    monkeypatch.setattr(backup, 'download', lambda _: b'wrong body')
    with pytest.raises(ValueError, match='verification failed'):
        backup.checkpoint(cache, key, 'owner/repo', 'synthetic')
    assert deleted == []
    monkeypatch.setattr(backup, 'download', lambda _: received['body'])
    result = backup.checkpoint(cache, key, 'owner/repo', 'synthetic')
    assert result['verified']
    assert set(deleted) == {'/releases/assets/1', '/releases/assets/2'}
    assert json.loads((cache/'evidence-checkpoint.json').read_text())['assetId'] == 5


def test_signed_download_never_receives_github_authorization(monkeypatch):
    def get(url, **kwargs):
        assert 'headers' not in kwargs and 'auth' not in kwargs
        return type('Downloaded', (), {'content': b'encrypted', 'raise_for_status': lambda self: None})()
    monkeypatch.setattr(backup.requests, 'get', get)
    assert backup.download({'browser_download_url': 'https://github.com/owner/repo/releases/download/tag/file.aes'}) == b'encrypted'
    with pytest.raises(ValueError, match='origin'):
        backup.download({'browser_download_url': 'https://untrusted.example/file'})


def test_existing_cache_cannot_hide_a_newer_durable_checkpoint(tmp_path, monkeypatch):
    cache, newer = tmp_path/'cache', tmp_path/'newer'
    make_cache(cache, 'old')
    make_cache(newer, 'new')
    key = secrets.token_bytes(32); body, _ = backup.pack(newer, key)
    monkeypatch.setattr(backup, 'release', lambda *args: {'assets': [{
        'id': 7, 'name': 'evidence-cache-new.aes', 'state': 'uploaded', 'created_at': '2026-11-09'}]})
    monkeypatch.setattr(backup, 'download', lambda _: body)
    backup.recover(cache, tmp_path/'unused', key, 'owner/repo', 'synthetic')
    assert set(backup.raw_rows((cache/'mention_store.json.gz').read_bytes())) == {'old', 'new'}


def test_manual_review_can_skip_all_public_data_writes():
    import yaml
    root = Path(__file__).resolve().parents[2]
    steps = yaml.safe_load((root/'.github/workflows/collect.yml').read_text())['jobs']['collect']['steps']
    for name in ['Supabase 업로드 (키가 있을 때만)', '변경분 커밋']:
        condition = next(s['if'] for s in steps if s.get('name') == name)
        assert "github.event_name != 'workflow_dispatch' || inputs.publish_data" in condition
