"""Load/render real plugin content with native controls, without a compositor.
Only the Wayland popup wrapper is replaced; this does not test compositor IPC.
Usage: python tests/ui_smoke.py [output-directory]
"""
import json
import datetime as dt
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PLUGIN=Path(__file__).resolve().parents[1]
NATIVE=Path(os.environ.get('OMARCHY_PATH','/usr/share/omarchy'))/'shell'
OUTPUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else PLUGIN/'docs'
OUTPUT.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='prayer-ui-') as directory:
    root=Path(directory)
    for path in NATIVE.iterdir():
        if path.name not in ('shell.qml','Ui'):
            (root/path.name).symlink_to(path)
    shutil.copytree(NATIVE/'Ui',root/'Ui')
    shutil.copy(PLUGIN/'tests/ui/KeyboardPanel.qml',root/'Ui/KeyboardPanel.qml')
    (root/'shell.qml').write_text((PLUGIN/'tests/ui/shell.qml.in').read_text().replace('@PLUGIN@',PLUGIN.as_uri()))
    runtime=root/'runtime';runtime.mkdir(mode=0o700)
    state_dir=root/'state';state_dir.mkdir()
    cache=state_dir/'omarchy/prayer-times';cache.mkdir(parents=True)
    (cache/'calendar-habous.json').write_text(json.dumps(dict(source='https://www.habous.gov.ma/',checked=dt.datetime.now(dt.timezone.utc).isoformat(),records=[dict(gregorian='2026-11-13',year=1448,month=6,day=3)])))
    for mode,language in [('base','en'),('settings','en'),('city','fr'),('fasting','ar'),('setup','en'),('setup-confirm','fr'),('hijri-cached','en')]:
        (root/'language').write_text(language+'\n')
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_BACKEND='software',
                 XDG_RUNTIME_DIR=str(runtime),XDG_STATE_HOME=str(state_dir),DISPLAY='',PRAYER_QA_MODE=mode,PRAYER_QA_OUTPUT=str(OUTPUT),
                 OMARCHY_LANGUAGE_FILE=str(root/'language'))
        run=subprocess.run(['quickshell','-p',str(root/'shell.qml'),'--no-color'],env=env,capture_output=True,text=True,timeout=15)
        output=run.stdout+run.stderr
        (OUTPUT/f'{mode}.log').write_text(output)
        errors=[line for line in output.splitlines() if 'WARN scene:' in line or 'Failed to load configuration' in line]
        assert run.returncode==0 and not errors,(run.returncode,errors,output)
        assert 'PRAYER_QA_LOADED' in output
        state=json.loads(next(line[line.index('{'):] for line in output.splitlines() if 'PRAYER_QA_LOADED' in line))
        assert state['ready'] and not state['error'],state
        assert state['setupComplete'] == (mode != 'setup'),state
        if mode=='settings': assert state['method']=='mwl'
        if mode=='setup-confirm': assert state['timezone']=='Asia/Tokyo' and state['method']=='mwl'
        if mode=='hijri-cached' and state['date']=='2026-11-13':
            assert state['hijri']==dict(year=1448,month=6,day=3) and state['hijriSync']['status']=='cached'
        assert (OUTPUT/f'preview-{mode}.png').stat().st_size>1000
        print(f'{mode} ({language}): content, worker, settings and rendering passed')
print('Compositor placement, real notifications and audible playback require a desktop session.')
