"""Install the authorised OpenEdu reviewer, initially paused for acceptance."""
import hashlib,json,os,plistlib,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.edutree.feedback_agent import STATE,identity,bindings
ROOT=Path(__file__).resolve().parents[1]
LABEL='work.itdo.openedu-feedback'
INTERNAL=Path.home()/'Library/Application Support/itdo/openedu-feedback'

def main():
 if ROOT!=Path('/Volumes/ORICO/open_edu') or not Path('/Volumes/ORICO').is_mount():raise RuntimeError('Mounted ORICO project required')
 STATE.mkdir(parents=True,exist_ok=True,mode=0o700);STATE.chmod(0o700)
 cfg=STATE/'config.json'
 if cfg.exists():
  if json.loads(cfg.read_text())['bindings']!=bindings():raise RuntimeError('Explicit source-binding migration required')
 else:
  slack=json.loads((Path.home()/'Library/Application Support/itdo/runtime-validation/slack.json').read_text())
  channels=[c for c,m in slack.get('channels',{}).items() if m=={'workspace':'jae-work','domain':'Work'}]
  if len(channels)!=1:raise RuntimeError('A unique authorised work-status channel is required')
  model=identity();cfg.write_text(json.dumps({'version':1,'owner':'OpenEdu feedback review','paused':True,'slackChannel':channels[0],'slackWorkspace':'jae-work','model':{'id':model.model_id,'digest':model.model_digest},'bindings':bindings(),'modelAttemptsPerDay':12,'modelContext':2048,'modelOutput':96,'cloudFallback':False,'automaticFields':['tel'],'reviewIntervalSeconds':300},indent=2));cfg.chmod(0o600)
 INTERNAL.mkdir(parents=True,exist_ok=True,mode=0o700)
 launcher=INTERNAL/'launcher.py'
 source="""import os,signal,subprocess
from pathlib import Path
root=Path('/Volumes/ORICO/open_edu')
if not Path('/Volumes/ORICO').is_mount() or not (root/'pipeline/edutree/feedback_agent.py').is_file():raise SystemExit(0)
p=subprocess.Popen(['/Volumes/ORICO/wixxim/runtime/.venv/bin/python','-m','pipeline.edutree.feedback_agent'],cwd=root,start_new_session=True)
try:code=p.wait(timeout=180)
except subprocess.TimeoutExpired:
 os.killpg(p.pid,signal.SIGTERM)
 try:p.wait(timeout=3)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 raise SystemExit(1)
raise SystemExit(code)
"""
 if launcher.exists() and launcher.read_text()!=source:raise RuntimeError('Launcher changed; explicit migration required')
 launcher.write_text(source);launcher.chmod(0o600)
 plist=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
 content=plistlib.dumps({'Label':LABEL,'ProgramArguments':[str(Path('/Library/Developer/CommandLineTools/usr/bin/python3').resolve(strict=True)),str(launcher)],'WorkingDirectory':str(INTERNAL),'StartInterval':300,'RunAtLoad':True,'ProcessType':'Background','Umask':63,'StandardOutPath':str(INTERNAL/'scheduler.log'),'StandardErrorPath':str(INTERNAL/'scheduler.log')})
 domain='gui/'+str(os.getuid());loaded=subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True).returncode==0
 if loaded and plist.read_bytes()!=content:raise RuntimeError('Loaded schedule differs')
 if not loaded:
  plist.write_bytes(content);plist.chmod(0o600);subprocess.run(['plutil','-lint',str(plist)],check=True,capture_output=True);subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True)
 print(json.dumps({'label':LABEL,'loaded':True,'paused':json.loads(cfg.read_text())['paused'],'launcherSHA256':hashlib.sha256(source.encode()).hexdigest()}))
if __name__=='__main__':main()
