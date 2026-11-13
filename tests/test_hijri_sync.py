import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import Future
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hijri_sync as sync
import engine

# Date pair published by the official ministry, retrieved 2026-11-13.
# https://www.habous.gov.ma/ (Friday sermon announcement)
OFFICIAL='<p>خطبة ليوم 3 جمادى الآخرة 1448هـ الموافق لـ 13 نونبر 2026م</p>'

class OfficialCalendar(unittest.TestCase):
    def test_official_pair_advances_without_any_manual_offset(self):
        records=sync.parse_habous(OFFICIAL)
        for day in (11,12,13,14):
            self.assertEqual(sync.resolve(records,dt.date(2026,11,day)),dict(year=1448,month=6,day=day-10))

    def test_arabic_digits_markup_and_scripts(self):
        html=OFFICIAL.replace('3','٣').replace('1448','١٤٤٨').replace('13','١٣').replace('2026','٢٠٢٦').replace('جمادى الآخرة','<b>جمادى الآخرة</b>')
        html+='<script>'+OFFICIAL.replace('13 نونبر','14 نونبر')+'</script>'
        self.assertEqual(sync.parse_habous(html),sync.parse_habous(OFFICIAL))

    def test_never_extrapolates_an_unannounced_month_boundary(self):
        records=sync.parse_habous(OFFICIAL)
        self.assertEqual(sync.resolve(records,dt.date(2026,12,9))['day'],29)
        self.assertIsNone(sync.resolve(records,dt.date(2026,12,10)))
        self.assertIsNone(sync.resolve(records,dt.date(2026,12,11)))
        explicit=records+[dict(gregorian='2026-12-10',year=1448,month=6,day=30)]
        self.assertEqual(sync.resolve(sync.validate_records(explicit),dt.date(2026,12,10))['day'],30)
        following=records+[dict(gregorian='2026-12-10',year=1448,month=7,day=1)]
        self.assertEqual(sync.resolve(sync.validate_records(following),dt.date(2026,12,10)),dict(year=1448,month=7,day=1))

    def test_missing_conflicting_and_invalid_dates_fail_closed(self):
        for html in ('maintenance',OFFICIAL+OFFICIAL.replace('13 نونبر','14 نونبر'),OFFICIAL.replace('13 نونبر','31 فبراير')):
            with self.subTest(html=html):
                with self.assertRaises(ValueError):sync.parse_habous(html)

    def test_unsupported_timezone_does_not_get_moroccan_date(self):
        with tempfile.TemporaryDirectory() as directory:
            calendar=sync.AuthoritativeCalendar(directory);calendar.records=sync.parse_habous(OFFICIAL)
            cfg=engine.config(dict(timezone='Asia/Tokyo'))
            self.assertIsNone(calendar.date(dt.date(2026,11,13),cfg))
            self.assertEqual(calendar.info(dt.date(2026,11,13),cfg)['status'],'unsupported')
            cfg['hijriSource']='habous'
            self.assertEqual(calendar.date(dt.date(2026,11,13),cfg)['day'],3)

    def test_verified_cache_survives_restart_and_network_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'calendar-habous.json'
            path.write_text(json.dumps(dict(source=sync.URL,checked='2026-11-13T10:00:00+00:00',records=sync.parse_habous(OFFICIAL))))
            calendar=sync.AuthoritativeCalendar(directory)
            calendar.future=Future();calendar.future.set_exception(OSError('offline'));calendar.next_refresh=float('inf')
            calendar.refresh(engine.config(),lambda *a:None)
            state=calendar.info(dt.date(2026,11,13),engine.config())
            self.assertEqual((state['date']['day'],state['status']),(3,'cached'))
            self.assertEqual(calendar.info(dt.date(2026,12,10),engine.config())['status'],'unverified')

    def test_sync_completion_validates_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            calendar=sync.AuthoritativeCalendar(directory)
            calendar.future=Future();calendar.future.set_result(sync.parse_habous(OFFICIAL));calendar.next_refresh=float('inf')
            writes=[];calendar.refresh(engine.config(),lambda path,data:writes.append(data))
            self.assertEqual(calendar.info(dt.date(2026,11,13),engine.config())['status'],'synced')
            self.assertEqual(writes[0]['source'],sync.URL)

    def test_redirects_cannot_downgrade_or_change_source(self):
        redirect=sync.SourceRedirects()
        for url in ('http://www.habous.gov.ma/','https://example.com/calendar'):
            with self.assertRaises(ValueError):redirect.redirect_request(None,None,302,'',{},url)

    def test_unverified_ramadan_interval_is_explicitly_estimated(self):
        cfg=engine.config(dict(method='ummalqura',timezone='Asia/Riyadh',latitude=21.42,longitude=39.83))
        times,estimated=engine.times(dt.date(2026,2,19),cfg,lambda d:None)
        self.assertIn('isha',estimated)
        times,estimated=engine.times(dt.date(2026,2,19),cfg,lambda d:dict(year=1447,month=9,day=1))
        self.assertNotIn('isha',estimated)
        self.assertEqual(times['isha']-times['maghrib'],120*60)

if __name__=='__main__':unittest.main()
