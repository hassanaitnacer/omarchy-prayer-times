#!/usr/bin/env python3
"""One JSON-lines worker owned by the shell's singleton plugin service.

Prayer times stay offline; official Hijri dates sync separately over HTTPS.
Closing the QML process input also stops local audio.
Notification commits are atomic and locked across overlapping reloads.
"""
import ctypes
import fcntl
import json
import math
import os
from pathlib import Path
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import wave
import engine
from hijri_sync import AuthoritativeCalendar

HERE = Path(__file__).resolve().parent
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'omarchy/prayer-times'


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Ledger:
    def __init__(self, directory=STATE):
        self.directory = directory

    def deliver(self, key, now, action):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory/'delivery.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.directory/'delivered.json'
            values = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(values, dict):
                raise ValueError('ledger')
            values = {k:v for k,v in values.items() if isinstance(v,(int,float)) and now-v<3*86400}
            if key in values:
                return False
            if not action():
                return False
            values[key] = now
            atomic_json(path, values)
            return True


def event_key(cfg, event):
    return '|'.join((cfg['timezone'],str(round(cfg['latitude'],3)),str(round(cfg['longitude'],3)),event['date'],event['name'],event['kind']))


def dnd_off():
    try:
        r = subprocess.run(['omarchy-shell','notifications','isDnd'],capture_output=True,text=True,timeout=3)
        return r.returncode == 0 and r.stdout.strip() == 'off'
    except (OSError,subprocess.TimeoutExpired):
        return False  # Unknown state must never cause surprise audio.


def stop_with_parent():
    # The player belongs to this worker, even if the shell/worker is killed.
    ctypes.CDLL(None).prctl(1, signal.SIGTERM)
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


class Worker:
    def __init__(self):
        self.raw = {}
        self.cfg = engine.config()
        self.ready = False
        self.setup_complete = False
        self.offset = 0
        self.last_tick = None
        self.last_monotonic = None
        self.audio = None
        self.audio_started = 0
        self.error = ''
        self.ledger = Ledger()
        self.language = 'en'
        self.catalogs = {lang:json.loads((HERE/'i18n'/f'{lang}.json').read_text()) for lang in ('en','ar','fr')}
        self.city_list = engine.cities()
        self.calendar = AuthoritativeCalendar(STATE)

    def text(self,key):
        return self.catalogs.get(self.language, self.catalogs['en']).get(key,self.catalogs['en'].get(key,key))

    def stop(self):
        if self.audio and self.audio.poll() is None:
            self.audio.terminate()
            try:
                self.audio.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.audio.kill()
                self.audio.wait(timeout=1)
        self.audio = None

    def play(self):
        self.stop()
        if not self.setup_complete or self.cfg['sound']=='off':
            return
        if not dnd_off():
            self.error = 'audioQuiet'
            return
        if not shutil.which('mpv'):
            self.error = 'audioPlayer'
            return
        path = Path(self.cfg['audioFile']).expanduser() if self.cfg['sound']=='file' else STATE/'chime.wav'
        if self.cfg['sound']=='chime' and not path.exists():
            STATE.mkdir(parents=True,exist_ok=True)
            # Original two-note chime, generated locally; no third-party media.
            with wave.open(str(path),'wb') as wav:
                rate=22050
                wav.setparams((1,2,rate,0,'NONE','not compressed'))
                samples=[]
                for i in range(int(rate*.8)):
                    t=i/rate
                    envelope=min(1,t/.02)*math.exp(-4*t)
                    value=.20*envelope*(math.sin(2*math.pi*660*t)+.5*math.sin(2*math.pi*880*t))
                    samples.append(struct.pack('<h',int(32767*value)))
                wav.writeframes(b''.join(samples))
        if not path.is_file() or not path.is_absolute():
            self.error='audioFile'
            return
        self.error=''
        self.audio=subprocess.Popen(['mpv','--no-config','--no-video','--no-terminal','--no-input-default-bindings',
                                     '--no-input-terminal','--load-scripts=no','--access-references=no',
                                     '--volume='+str(self.cfg['volume']),'--',str(path)],
                                     stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=stop_with_parent)
        self.audio_started=time.time()

    def notify(self,event,now):
        name=self.text('prayer.'+event['name'])
        body=self.text('notify.advance' if event['kind']=='advance' else 'notify.body').replace('%1',name).replace('%2',str(self.cfg['advanceMinutes']))
        hour,minute=event['hour'],event['minute']
        if self.raw.get('hour24',True):
            clock=f'{hour:02}:{minute:02}'
        else:
            clock=f'{hour%12 or 12}:{minute:02} '+('AM' if hour<12 else 'PM')
        headline=self.text('notify.headline').replace('%1',name).replace('%2',clock)
        argv=['omarchy','notification','send','--app-name','io.github.hassanaitnacer.prayer-times','--transient','-u','normal','-g','󱠧',
              engine.safe_shared(headline),engine.safe_shared(body)]
        if event['audible'] and self.cfg['sound']!='off':
            argv+=['--action',engine.safe_shared(self.text('audio.stop')),'omarchy-shell','io.github.hassanaitnacer.prayer-times.audio','stop']
        else:
            argv+=['--exec','omarchy-shell','shell','summon','io.github.hassanaitnacer.prayer-times','{}']
        def send():
            try:
                result=subprocess.run(argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
                if result.returncode:
                    self.error='delivery'
                    return False
                return True
            except (OSError,subprocess.TimeoutExpired):
                self.error='delivery'
                return False
        try:
            sent=self.ledger.deliver(event_key(self.cfg,event),now,send)
            if sent:
                if self.error=='delivery': self.error=''
                if event['audible'] and self.cfg['sound']!='off': self.play()
        except (OSError,ValueError):
            self.error='ledger'

    def command(self, message):
        command=message.get('command')
        if command=='configure':
            raw=message.get('settings',{})
            if not isinstance(raw,dict):
                return
            try:
                complete = raw.get('setupComplete') is True
                if complete:
                    engine.validate_setup(raw)
                cfg=engine.config(raw)
            except ValueError as error:
                # Fail quiet even if a bad location accompanies "reminders off".
                # A later valid update can restore the user's requested settings.
                self.stop()
                self.cfg['notify'] = False
                self.cfg['sound'] = 'off'
                self.setup_complete = False
                self.error=str(error)
                return
            if not complete:
                cfg['notify'] = False
                cfg['sound'] = 'off'
            if cfg['sound']=='off' or (self.cfg['notify'] and not cfg['notify']) or any(cfg[k]!=self.cfg[k] for k in ('latitude','longitude','timezone','volume','audioFile')):
                self.stop()
            self.raw=raw
            self.cfg=cfg
            self.setup_complete=complete
            self.ready=True
            self.error=''
            self.language=str(message.get('language','en')).replace('_','-').split('-')[0]
        elif command=='day':
            self.offset=int(engine.number(message.get('offset'),0,-366,366))
        elif command=='preview':
            self.play()
        elif command=='stop':
            self.stop()
        elif command=='clearError':
            self.error=''

    def tick(self, now=None, notifications=True):
        now=time.time() if now is None else now
        if self.audio:
            code=self.audio.poll()
            if code is not None:
                if code: self.error='audioPlayback'
                self.audio=None
            elif now-self.audio_started>1200:
                self.stop()
            elif notifications and not dnd_off():
                self.stop()
        data=engine.snapshot(self.cfg,now,self.offset,lambda date:self.calendar.date(date,self.cfg))
        data['hijriSync']=self.calendar.info(engine.iso_date(data['date']),self.cfg)
        if self.ready and self.setup_complete and notifications:
            mono=time.monotonic()
            last=self.last_tick
            # CLOCK_MONOTONIC excludes Linux suspend time. Even a short sleep
            # must not replay an advance reminder or start delayed audio.
            if last is not None and self.last_monotonic is not None and abs((now-last)-(mono-self.last_monotonic))>2:
                last=None
            event=engine.due_event(data['events'],now,last,self.cfg)
            if event:
                self.notify(event,now)
            self.last_tick=now
            self.last_monotonic=mono
        data.pop('events')
        data.update(error=self.error,playing=self.audio is not None,ready=self.ready,
                    setupComplete=self.setup_complete,offset=self.offset)
        return data


def main():
    worker=Worker()
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    def emit(payload):
        print(json.dumps(payload,ensure_ascii=False),flush=True)
    emit({'type':'cities','cities':worker.city_list})
    pending=b''
    next_tick=0
    last_snapshot=None
    try:
        while True:
            now=time.time()
            readable,_,_=select.select([sys.stdin.buffer],[],[],max(0,min(15,next_tick-now)))
            changed=False
            if readable:
                chunk=os.read(sys.stdin.fileno(),65536)
                if not chunk: break
                pending+=chunk
                if len(pending)>262144: raise ValueError('oversized input')
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    try:
                        message=json.loads(line)
                        if isinstance(message,dict):
                            worker.command(message)
                            changed=True
                    except (ValueError,TypeError):
                        worker.error='settings'
            now=time.time()
            if worker.ready and worker.setup_complete:
                worker.calendar.refresh(worker.cfg,atomic_json)
            if changed or now>=next_tick:
                payload=worker.tick(now,notifications=now>=next_tick)
                # Minute-level schedule/display work, plus immediate command/audio updates.
                key=(int(now//60),worker.offset,worker.error,payload['playing'],worker.calendar.checked,worker.calendar.status)
                if changed or key!=last_snapshot:
                    emit({'type':'state','state':payload})
                    last_snapshot=key
                next_tick=now+(1 if payload['playing'] else min(15,60-now%60))
    finally:
        worker.stop()
        worker.calendar.close()


if __name__=='__main__':
    try:
        main()
    except (BrokenPipeError,KeyboardInterrupt):
        pass
