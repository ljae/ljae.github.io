"""Publish private reports using a server key; no raw queries enter public assets."""
import os

import requests


def publish(snapshot_id, snapshot, report, *, session=None):
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise ValueError('SUPABASE_SERVER_CREDENTIALS_REQUIRED')
    response = (session or requests.Session()).post(url+'/rest/v1/rpc/growth_publish', timeout=60,
        headers={'apikey': key, 'Authorization': f'Bearer {key}'},
        json={'p_id': snapshot_id, 'p_snapshot': snapshot, 'p_report': report})
    if response.status_code not in (200, 204):
        raise RuntimeError(f'GROWTH_PUBLISH_HTTP_{response.status_code}')
    return response.json() if response.content else None
