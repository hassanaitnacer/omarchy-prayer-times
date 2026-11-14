import concurrent.futures
import datetime as dt
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import backend

CONFIRMED = dict(city='Casablanca', latitude=33.5731, longitude=-7.5898,
                 timezone='Africa/Casablanca', method='morocco', setupComplete=True)

class Calculations(unittest.TestCase):
    def test_legacy_casablanca_is_unchanged(self):
        ts,_=engine.times(dt.date(2026,11,11),engine.config())
        self.assertEqual([dt.datetime.fromtimestamp(ts[p],engine.UTC).strftime('%H:%M') for p in engine.PRAYERS],
                         ['05:28','06:55','12:19','15:09','17:35','18:51'])

    def test_independent_adhan_fixtures(self):
        # External expected values, not generated from this implementation:
        # https://github.com/batoulapps/adhan-js/blob/develop/test/adhan.test.ts
        fixtures=[('isna',2,'2015-07-12',35.775,-78.6336,'America/New_York','04:42 06:08 13:21 18:22 20:32 21:57'),
                  ('mwl',1,'2015-12-01',35.775,-78.6336,'America/New_York','05:35 07:06 12:05 14:42 17:01 18:26'),
                  ('egypt',1,'2020-01-01',30.028703,31.249528,'Africa/Cairo','05:18 06:51 11:59 14:47 17:06 18:29')]
        for method,asr,date,lat,lon,zone,expected in fixtures:
            with self.subTest(method=method):
                cfg=engine.config(dict(method=method,asrFactor=asr,latitude=lat,longitude=lon,timezone=zone))
                ts,_=engine.times(dt.date.fromisoformat(date),cfg)
                self.assertEqual(' '.join(dt.datetime.fromtimestamp(ts[p],ZoneInfo(zone)).strftime('%H:%M') for p in engine.PRAYERS),expected)

    def test_order_across_full_year(self):
        cfg=engine.config()
        for day in range(365):
            ts,_=engine.times(dt.date(2026,1,1)+dt.timedelta(days=day),cfg)
            self.assertEqual(list(ts.values()),sorted(ts.values()))

    def test_independent_edinburgh_high_latitude_fixture(self):
        # Adhan's published Edinburgh fixture (same reference as above).
        # Different solar approximations can round a twilight boundary by 1m.
        cfg=engine.config(dict(latitude=55.983226,longitude=-3.216649,
                               timezone='Europe/London',method='mwl',highLatitude='middle'))
        ts,estimated=engine.times(dt.date(2020,6,15),cfg)
        expected=(74,266,794,1066,1321,74)
        for prayer,minute in zip(engine.PRAYERS,expected):
            local=dt.datetime.fromtimestamp(ts[prayer],ZoneInfo(cfg['timezone']))
            diff=abs(local.hour*60+local.minute-minute)
            self.assertLessEqual(min(diff,1440-diff),1,prayer)
        self.assertEqual(estimated,{'fajr','isha'})

    def test_seasonal_schedules_across_hemispheres(self):
        locations=[(-33.87,151.21,'Australia/Sydney'),(-33.92,18.42,'Africa/Johannesburg'),
                   (35.68,139.69,'Asia/Tokyo'),(24.86,67.01,'Asia/Karachi'),
                   (-23.55,-46.63,'America/Sao_Paulo'),(1.35,103.82,'Asia/Singapore')]
        for lat,lon,zone in locations:
            for month in (3,6,9,12):
                with self.subTest(zone=zone,month=month):
                    cfg=engine.config(dict(latitude=lat,longitude=lon,timezone=zone,method='mwl',highLatitude='middle'))
                    ts,_=engine.times(dt.date(2026,month,21),cfg)
                    self.assertNotIn(None,ts.values())
                    self.assertEqual(list(ts.values()),sorted(ts.values()))

    def test_profiles_do_not_inherit_morocco_margins(self):
        self.assertEqual(engine.config({'method':'mwl'})['margins'],dict(zip(engine.PRAYERS,(0,0,1,0,0,0))))
        self.assertEqual(engine.config({'method':'ummalqura'})['margins']['maghrib'],0)

    def test_custom_settings_migrate(self):
        cfg=engine.config({'fajrAngle':18,'ishaAngle':16,'adjust':{'fajr':2},'asrFactor':2})
        self.assertEqual((cfg['method'],cfg['fajrAngle'],cfg['ishaAngle'],cfg['asrFactor']),('custom',18,16,2))
        self.assertEqual(cfg['margins']['fajr'],2)
        self.assertEqual(cfg['margins']['maghrib'],5)

    def test_polar_events_are_not_invented(self):
        for rule in ('none','angle','middle','seventh'):
            cfg=engine.config(dict(latitude=69,longitude=18,highLatitude=rule))
            ts,_=engine.times(dt.date(2026,6,21),cfg)
            self.assertIsNone(ts['fajr']); self.assertIsNone(ts['sunrise']); self.assertIsNone(ts['maghrib']); self.assertIsNone(ts['isha'])

    def test_high_latitude_estimates_are_labelled(self):
        cfg=engine.config(dict(latitude=51.5,longitude=-.12,method='mwl',highLatitude='middle'))
        ts,estimated=engine.times(dt.date(2026,6,21),cfg)
        self.assertTrue({'fajr','isha'}<=estimated)
        self.assertLess(ts['fajr'],ts['sunrise']);self.assertGreater(ts['isha'],ts['maghrib'])

    def test_tabular_hijri_icu_fixtures(self):
        # ICU Islamic-civil calendar fixtures, independently checked with Intl.
        for date,expected in [('2026-02-17',(1447,8,29)),('2026-02-18',(1447,9,1)),('2026-03-19',(1447,9,30)),('2026-03-20',(1447,10,1)),('2026-11-11',(1448,5,30))]:
            self.assertEqual(tuple(engine.tabular_hijri(dt.date.fromisoformat(date)).values()),expected)

    def test_hijri_crescent_estimate_matches_moroccan_announcements(self):
        # First days announced by Morocco's Ministry of Habous.
        cfg=engine.config({})
        for date,month in [('2023-03-23',9),('2023-04-22',10),('2024-03-12',9),('2024-04-10',10),('2025-03-02',9),('2025-03-31',10),('2025-06-27',1),('2026-02-19',9)]:
            h=engine.hijri(dt.date.fromisoformat(date),cfg)
            self.assertEqual((h['month'],h['day']),(month,1),date)

    def test_hijri_months_are_contiguous(self):
        cfg=engine.config({})
        previous=engine.hijri(dt.date(2019,12,31),cfg)
        for n in range(3660):
            h=engine.hijri(dt.date(2020,1,1)+dt.timedelta(days=n),cfg)
            if h['day']==1:
                self.assertIn(previous['day'],(29,30))
                self.assertEqual((h['year']*12+h['month']),(previous['year']*12+previous['month'])+1)
            else:
                self.assertEqual((h['year'],h['month'],h['day']),(previous['year'],previous['month'],previous['day']+1))
            previous=h

    def test_hijri_correction_applies_to_its_month_only(self):
        # Morocco sighted the Jumada II 1448 crescent a day before the estimate.
        plain=engine.config({})
        cfg=engine.config(dict(hijriAdjust=1,hijriAdjustDate='2026-11-12'))
        day=lambda s,c:tuple(engine.hijri(dt.date.fromisoformat(s),c).values())
        self.assertEqual(day('2026-11-12',plain),(1448,6,1))
        self.assertEqual(day('2026-11-10',cfg),(1448,5,29))
        self.assertEqual(day('2026-11-11',cfg),(1448,6,1))
        self.assertEqual(day('2026-11-12',cfg),(1448,6,2))
        self.assertEqual(day('2026-12-10',cfg),(1448,6,30))
        for s in ('2026-12-11','2027-01-10','2027-02-08'):
            self.assertEqual(day(s,cfg),day(s,plain))
        legacy=engine.config(dict(hijriAdjust=1))
        self.assertEqual(day('2027-01-10',legacy),day('2027-01-11',plain))
        self.assertIsNone(engine.config(dict(hijriAdjustDate='nonsense'))['hijriAdjustDate'])

    def test_ramadan_isha_interval(self):
        cfg=engine.config(dict(method='ummalqura',latitude=21.4225,longitude=39.8262,timezone='Asia/Riyadh'))
        for date,minutes in [('2026-02-18',90),('2026-02-19',120),('2026-03-21',90)]:
            ts,_=engine.times(dt.date.fromisoformat(date),cfg)
            self.assertEqual(ts['isha']-ts['maghrib'],minutes*60)
        cfg['hijriAdjust']=1
        ts,_=engine.times(dt.date(2026,2,18),cfg)
        self.assertEqual(ts['isha']-ts['maghrib'],120*60)

    def test_timezone_is_independent_of_process_timezone(self):
        cfg=engine.config(dict(timezone='Asia/Tokyo',latitude=35.68,longitude=139.69,method='mwl'))
        now=dt.datetime(2026,11,11,16,tzinfo=engine.UTC).timestamp()
        data=engine.snapshot(cfg,now)
        self.assertEqual(data['today'],'2026-11-12')
        for row in data['rows']:
            self.assertEqual(row['hour'],dt.datetime.fromtimestamp(row['time'],ZoneInfo('Asia/Tokyo')).hour)

    def test_international_date_line(self):
        cfg=engine.config(dict(timezone='Pacific/Kiritimati',latitude=1.87,longitude=-157.4,method='mwl'))
        now=dt.datetime(2026,11,11,0,tzinfo=engine.UTC).timestamp()
        data=engine.snapshot(cfg,now)
        for row in data['rows']:
            local=dt.datetime.fromtimestamp(row['time'],ZoneInfo(cfg['timezone']))
            self.assertEqual(local.date().isoformat(),data['today'])
        self.assertIsNotNone(data['next'])

    def test_repeated_dst_hour_keeps_same_schedule(self):
        cfg=engine.config(dict(timezone='America/New_York',latitude=40.7,longitude=-74,method='isna'))
        first=dt.datetime(2026,11,1,5,30,tzinfo=engine.UTC).timestamp()
        second=first+3600
        self.assertEqual(engine.snapshot(cfg,first)['rows'],engine.snapshot(cfg,second)['rows'])

    def test_morocco_ramadan_timezone_transition(self):
        cfg=engine.config()
        offsets=set()
        for day in (14,15,16):
            date=dt.date(2026,2,day)
            ts,_=engine.times(date,cfg)
            local=dt.datetime.fromtimestamp(ts['dhuhr'],ZoneInfo(cfg['timezone']))
            offsets.add(local.utcoffset().total_seconds())
        self.assertEqual(offsets,{0,3600})

    def test_browsing_does_not_move_next_prayer(self):
        cfg=engine.config();now=dt.datetime(2026,11,11,10,tzinfo=engine.UTC).timestamp()
        today=engine.snapshot(cfg,now);future=engine.snapshot(cfg,now,3)
        self.assertEqual(today['next'],future['next'])
        self.assertEqual(future['date'],'2026-11-14')

    def test_fajr_end_and_fasting(self):
        cfg=engine.config(); ts,_=engine.times(dt.date(2026,11,11),cfg)
        before=engine.snapshot(cfg,ts['fajr']-60)
        during=engine.snapshot(cfg,ts['fajr']+60)
        self.assertEqual(before['fasting']['name'],'suhoor')
        self.assertEqual(during['fasting']['name'],'iftar')
        self.assertEqual(during['fajrEnd'],ts['sunrise'])
        self.assertEqual(during['next']['name'],'dhuhr')

    def test_unknown_zone_rejected_and_bad_values_bounded(self):
        with self.assertRaises(ValueError): engine.config({'timezone':'Mars/Unknown'})
        cfg=engine.config({'latitude':'nan','longitude':999,'volume':-100,'adjust':{'fajr':1e9}})
        self.assertEqual((cfg['latitude'],cfg['longitude'],cfg['volume']), (33.5731,-7.5898,50))
        self.assertEqual(cfg['margins']['fajr'],0)

    def test_offline_city_catalog_is_valid(self):
        cities=engine.cities();self.assertGreater(len(cities),300)
        for c in cities:
            ZoneInfo(c['timezone'])
            self.assertTrue(-90<=c['latitude']<=90 and -180<=c['longitude']<=180)
        self.assertEqual(next(c for c in cities if c['city']=='Casablanca')['latitude'],33.5731)

class Delivery(unittest.TestCase):
    def setUp(self):
        self.cfg=engine.config({'advance':True})
        self.event={'name':'asr','time':10000,'date':'2026-11-11','hour':15,'minute':0}

    def test_resume_catches_one_recent_event_silently(self):
        due=engine.due_event([self.event],10500,9000,self.cfg)
        self.assertEqual(due['name'],'asr');self.assertFalse(due['audible'])
        self.assertIsNone(engine.due_event([self.event],10900,9000,self.cfg))
        self.assertFalse(engine.due_event([self.event],10001,None,self.cfg)['audible'])

    def test_only_latest_event_and_no_muted_prayers(self):
        earlier=dict(self.event,name='dhuhr',time=9900)
        self.assertEqual(engine.due_event([earlier,self.event],10001,9990,self.cfg)['name'],'asr')
        self.cfg['muted']=['asr','dhuhr']
        self.assertIsNone(engine.due_event([earlier,self.event],10001,9990,self.cfg))

    def test_advance_never_replays_after_sleep(self):
        self.assertIsNone(engine.due_event([self.event],9401,9000,self.cfg))
        due=engine.due_event([self.event],9401,9390,self.cfg)
        self.assertEqual(due['kind'],'advance');self.assertFalse(due['audible'])
        self.assertIsNone(engine.due_event([self.event],9461,9450,self.cfg))

    def test_ledger_survives_restart_and_overlapping_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            count=[]
            def deliver(_):
                return backend.Ledger(Path(directory)).deliver('asr',10000,lambda:count.append(1) or True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(deliver,range(8)))
            self.assertEqual(sum(results),1);self.assertEqual(len(count),1)
            self.assertFalse(backend.Ledger(Path(directory)).deliver('asr',10001,lambda:True))

    def test_state_directory_and_files_are_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'omarchy'/'prayer-times'
            state.mkdir(parents=True);state.chmod(0o755)
            (state/'chime.wav').write_bytes(b'');(state/'chime.wav').chmod(0o644)
            (state/'delivery.lock').write_text('');(state/'delivery.lock').chmod(0o644)
            self.assertTrue(backend.Ledger(state).deliver('asr',10000,lambda:True))
            modes={p.name:p.stat().st_mode&0o777 for p in state.iterdir()}
            self.assertEqual(state.stat().st_mode&0o777,0o700)
            self.assertEqual(modes,{'chime.wav':0o600,'delivery.lock':0o600,'delivered.json':0o600})
            self.assertEqual(state.parent.stat().st_mode&0o777,0o755)  # only the plugin's own directory

    def test_new_state_is_created_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'prayer-times'
            old=os.umask(0)
            try:
                self.assertTrue(backend.Ledger(state).deliver('asr',10000,lambda:True))
            finally:
                os.umask(old)
            self.assertEqual(state.stat().st_mode&0o777,0o700)
            self.assertEqual({p.stat().st_mode&0o777 for p in state.iterdir()},{0o600})

    def test_history_key_keeps_coarse_location_only(self):
        cfg=engine.config(dict(latitude=55.983226,longitude=-3.216649,timezone='Europe/London'))
        key=backend.event_key(cfg,dict(self.event,kind='time'))
        self.assertEqual(key,'Europe/London|55.98|-3.22|2026-11-11|asr|time')

    def test_rounded_default_city_keeps_its_timezone(self):
        with patch.object(Path,'resolve',return_value=Path('/usr/share/zoneinfo/Asia/Tokyo')):
            self.assertEqual(engine.config(dict(latitude=33.57,longitude=-7.59))['timezone'],'Africa/Casablanca')
            self.assertEqual(engine.config(dict(latitude=33.5731,longitude=-7.5898))['timezone'],'Africa/Casablanca')
            self.assertEqual(engine.config(dict(latitude=33.6,longitude=-7.59))['timezone'],'Asia/Tokyo')

    def test_failed_delivery_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=backend.Ledger(Path(directory))
            self.assertFalse(ledger.deliver('asr',10000,lambda:False))
            self.assertTrue(ledger.deliver('asr',10001,lambda:True))

    def test_unsafe_text_neutralized_for_shared_sinks(self):
        raw='<img src="https://example.invalid/tracker"> & hello\n'
        text=engine.safe_shared(raw)
        self.assertNotIn('<',text);self.assertNotIn('>',text);self.assertNotIn('&',text)
        self.assertNotIn('\n',text)
        self.assertLessEqual(len(engine.clean('x'*1000)),80)

    def test_dnd_unknown_fails_quietly(self):
        with patch('backend.subprocess.run',side_effect=OSError()): self.assertFalse(backend.dnd_off())

    def test_worker_invalid_timezone_keeps_valid_state(self):
        worker=backend.Worker()
        worker.command({'command':'configure','settings':{'timezone':'Asia/Tokyo','notify':False}})
        worker.command({'command':'configure','settings':{'timezone':'wrong'}})
        self.assertEqual(worker.cfg['timezone'],'Asia/Tokyo')
        self.assertEqual(worker.error,'timezone')

    def test_short_suspend_suppresses_audio(self):
        worker=backend.Worker()
        worker.command({'command':'configure','settings':CONFIRMED})
        now=dt.datetime(2026,11,11,15,9,tzinfo=engine.UTC).timestamp()+1
        worker.last_tick=now-30
        worker.last_monotonic=100
        with patch('backend.time.monotonic',return_value=101), patch.object(worker,'notify') as notify:
            worker.tick(now)
            self.assertTrue(notify.called)
            self.assertFalse(notify.call_args.args[0]['audible'])

    def test_turning_sound_off_stops_player(self):
        worker=backend.Worker()
        worker.cfg['sound']='chime'
        worker.audio=subprocess.Popen(['sleep','30'])
        process=worker.audio
        worker.command({'command':'configure','settings':{'sound':'off'}})
        self.assertIsNotNone(process.poll())
        self.assertIsNone(worker.audio)

    def test_first_run_cannot_notify_or_play_until_confirmed(self):
        worker=backend.Worker()
        worker.command({'command':'configure','settings':dict(CONFIRMED, setupComplete=False, sound='chime')})
        now=dt.datetime(2026,11,11,15,9,tzinfo=engine.UTC).timestamp()+1
        with patch.object(worker,'notify') as notify, patch('backend.subprocess.Popen') as player:
            state=worker.tick(now)
            worker.play()
            notify.assert_not_called()
            player.assert_not_called()
        self.assertFalse(state['setupComplete'])
        worker.command({'command':'configure','settings':CONFIRMED})
        with patch.object(worker,'notify') as notify:
            worker.tick(now)
            notify.assert_called_once()

    def test_confirmation_rejects_missing_and_invalid_location_or_method(self):
        for field,value in [('latitude',None),('latitude','nan'),('longitude',181),
                            ('timezone','Invalid/Zone'),('method','invalid'),('city','')]:
            with self.subTest(field=field,value=value):
                worker=backend.Worker()
                worker.command({'command':'configure','settings':dict(CONFIRMED, **{field:value})})
                self.assertFalse(worker.setup_complete)
                self.assertFalse(worker.cfg['notify'])
        worker=backend.Worker()
        worker.command({'command':'configure','settings':{'setupComplete':True}})
        self.assertFalse(worker.setup_complete)

    def test_invalid_location_always_pauses_reminders_and_audio_then_recovers(self):
        worker=backend.Worker()
        worker.command({'command':'configure','settings':dict(CONFIRMED,sound='chime')})
        with patch.object(worker,'stop') as stop:
            worker.command({'command':'configure','settings':dict(CONFIRMED,timezone='Invalid/Zone',notify=False)})
            stop.assert_called_once()
        self.assertFalse(worker.cfg['notify'])
        self.assertEqual(worker.cfg['sound'],'off')
        self.assertFalse(worker.setup_complete)
        worker.command({'command':'configure','settings':dict(CONFIRMED,notify=False)})
        self.assertTrue(worker.setup_complete)
        self.assertFalse(worker.cfg['notify'])

    def test_daemon_emits_authoritative_hijri_date_after_midnight(self):
        # Reported regression: local month starts Nov 11, so Nov 12/13 must be
        # Jumada II 2/3. Exercise the actual daemon's minute emission loop.
        settings=dict(CONFIRMED,notify=False)
        calendar=backend.AuthoritativeCalendar(Path('/nonexistent-prayer-test-cache'))
        calendar.records=[dict(gregorian='2026-11-13',year=1448,month=6,day=3)]
        calendar.status='cached'
        clock=[dt.datetime(2026,11,12,23,59,59,tzinfo=ZoneInfo('Africa/Casablanca')).timestamp()]
        calls=[0]
        def select_once(reads,*args):
            calls[0]+=1
            if calls[0]==2:
                clock[0]+=2
                return ([],[],[])
            return (reads,[],[])
        payload=(json.dumps({'command':'configure','settings':settings})+'\n').encode()
        output=io.StringIO()
        with patch('backend.time.time',side_effect=lambda:clock[0]), \
             patch('backend.select.select',side_effect=select_once), \
             patch('backend.os.read',side_effect=[payload,b'']), \
             patch('backend.signal.signal'), patch('sys.stdout',output), \
             patch('backend.AuthoritativeCalendar',return_value=calendar), \
             patch.object(calendar,'refresh'):
            backend.main()
        states=[m['state'] for m in map(json.loads,output.getvalue().splitlines()) if m['type']=='state']
        self.assertEqual([s['today'] for s in states],['2026-11-12','2026-11-13'])
        self.assertEqual([s['hijri'] for s in states],[{'year':1448,'month':6,'day':2},{'year':1448,'month':6,'day':3}])

    def test_daemon_protocol_offline(self):
        payload='\n'.join(json.dumps(x) for x in [dict(command='configure',settings={'notify':False,'timezone':'Asia/Tokyo'}),dict(command='day',offset=2)])+'\n'
        r=subprocess.run([sys.executable,str(Path(backend.__file__))],input=payload,capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr)
        messages=[json.loads(line) for line in r.stdout.splitlines()]
        self.assertEqual(messages[0]['type'],'cities')
        self.assertTrue(messages[1]['state']['ready'])
        self.assertEqual(messages[1]['state']['offset'],2)

if __name__=='__main__': unittest.main()
