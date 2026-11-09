"""Install the authorised OpenEdu daily local research review on this Mac."""
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.edutree.parent_daily import STATE, LIMITS, SEOUL, bindings, put, settings

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'work.itdo.openedu-daily'
INTERNAL = Path.home()/'Library/Application Support/itdo/openedu-daily'
PYTHON = '/Volumes/ORICO/wixxim/runtime/.venv/bin/python'


def main():
    if ROOT != Path('/Volumes/ORICO/open_edu') or not Path('/Volumes/ORICO').is_mount():
        raise RuntimeError('Expected mounted ORICO project')
    INTERNAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    cfg = STATE/'config.json'
    if cfg.exists():
        current = json.loads(cfg.read_text())
        if current['source_bindings'] != bindings():
            raise RuntimeError('Existing binding changed; explicit migration required')
    else:
        model = settings()
        put(cfg, {'version': 1, 'owner': 'OpenEdu parent-service maintenance',
                  'scope': 'Public Mokdong elementary mathematics academy sources only',
                  'paused': False, 'schedule': '08:00 Asia/Seoul, once per date; catch up same day',
                  'start_date': (datetime.now(SEOUL).date()+timedelta(days=1)).isoformat(),
                  'model': {'id': model.model_id, 'digest': model.model_digest},
                  'limits': LIMITS, 'source_bindings': bindings(),
                  'cloud_fallback': False, 'automatic_fact_publication': False})
    launcher = INTERNAL/'launcher.py'
    source = '''import os, signal, subprocess
from pathlib import Path
root=Path('/Volumes/ORICO/open_edu')
if not Path('/Volumes/ORICO').is_mount() or not (root/'pipeline/edutree/parent_daily.py').is_file():
 raise SystemExit(0)
p=subprocess.Popen(['/Volumes/ORICO/wixxim/runtime/.venv/bin/python','-m','pipeline.edutree.parent_daily','tick'],cwd=root,start_new_session=True)
try:
 code=p.wait(timeout=300)
except subprocess.TimeoutExpired:
 os.killpg(p.pid,signal.SIGTERM)
 try:p.wait(timeout=3)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 raise SystemExit(1)
raise SystemExit(code)
'''
    if launcher.exists() and launcher.read_text() != source:
        raise RuntimeError('Existing launcher differs; explicit migration required')
    launcher.write_text(source); launcher.chmod(0o600)
    plist = Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    expected = plistlib.dumps({'Label': LABEL,
        'ProgramArguments': [str(Path('/Library/Developer/CommandLineTools/usr/bin/python3').resolve(strict=True)), str(launcher)],
        'WorkingDirectory': str(INTERNAL), 'StartInterval': 300, 'RunAtLoad': True,
        'ProcessType': 'Background', 'Umask': 63,
        'StandardOutPath': str(INTERNAL/'scheduler.log'), 'StandardErrorPath': str(INTERNAL/'scheduler.log')})
    domain = 'gui/'+str(os.getuid())
    loaded = subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True).returncode == 0
    if loaded and plist.read_bytes() != expected:
        raise RuntimeError('Loaded scheduler differs; explicit migration required')
    if not loaded:
        plist.write_bytes(expected); plist.chmod(0o600)
        subprocess.run(['plutil','-lint',str(plist)],check=True,capture_output=True)
        subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True)
    print(json.dumps({'label': LABEL, 'config': str(cfg), 'loaded': True,
                      'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()}))


if __name__ == '__main__': main()
