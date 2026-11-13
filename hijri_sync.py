"""Validated Hijri dates from official Habous announcements, never estimates.

The ministry publishes explicit Gregorian/Hijri date pairs. A confirmed month
start establishes days 1–29. Day 30 requires explicit evidence; we never guess
when the next observed month begins. No coordinates are sent to the source.
"""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

URL = 'https://www.habous.gov.ma/'
MAX_BYTES = 1024 * 1024
HIJRI = {'محرم':1, 'صفر':2, 'ربيع الأول':3, 'ربيع الاول':3, 'ربيع الآخر':4, 'ربيع الثاني':4,
         'جمادى الأولى':5, 'جمادى الاولى':5, 'جمادى الآخرة':6, 'جمادى الثانية':6,
         'رجب':7, 'شعبان':8, 'رمضان':9, 'شوال':10, 'ذو القعدة':11, 'ذي القعدة':11,
         'ذو الحجة':12, 'ذي الحجة':12}
GREGORIAN = {'يناير':1,'فبراير':2,'مارس':3,'أبريل':4,'ابريل':4,'ماي':5,'يونيو':6,
             'يوليوز':7,'غشت':8,'شتنبر':9,'أكتوبر':10,'اكتوبر':10,'نونبر':11,'نوفمبر':11,'دجنبر':12,'ديسمبر':12}
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')
PAIR = re.compile(r'(\d{1,2})\s+('+'|'.join(HIJRI)+r')\s+(\d{4})\s*ه[ـ]?\s*'
                  r'(?:الموافق|موافق)\s*(?:لـ?|ل)?\s*(\d{1,2})\s+('+'|'.join(GREGORIAN)+r')\s+(\d{4})')

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.ignored=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.ignored+=1
        elif not self.ignored: self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.ignored=max(0,self.ignored-1)
        elif not self.ignored: self.parts.append(' ')
    def handle_data(self, data):
        if not self.ignored: self.parts.append(data)


def validate_records(records):
    if not isinstance(records,list) or not 1 <= len(records) <= 100:
        raise ValueError('invalid calendar records')
    result=[]; starts={}
    for record in records:
        date=dt.date.fromisoformat(record['gregorian'])
        year,month,day=(record[k] for k in ('year','month','day'))
        if any(type(v) is not int for v in (year,month,day)) or not (1200<=year<=1700 and 1<=month<=12 and 1<=day<=30):
            raise ValueError('invalid Hijri date')
        # A rough year guard catches a malformed or misassociated date pair.
        if abs(year-(date.year-622)*33/32)>3:
            raise ValueError('inconsistent years')
        start=date-dt.timedelta(days=day-1)
        key=(year,month)
        if key in starts and starts[key]!=start:
            raise ValueError('conflicting official month starts')
        starts[key]=start
        result.append(dict(gregorian=date.isoformat(),year=year,month=month,day=day))
    ordered=sorted(starts.items())
    for ((y1,m1),d1),((y2,m2),d2) in zip(ordered,ordered[1:]):
        if y2*12+m2 == y1*12+m1+1 and (d2-d1).days not in (29,30):
            raise ValueError('inconsistent consecutive months')
    return result


def parse_habous(html):
    parser=VisibleText(); parser.feed(html)
    text=re.sub(r'\s+',' ',''.join(parser.parts).translate(DIGITS))
    records=[]
    for day,month,year,gday,gmonth,gyear in PAIR.findall(text):
        records.append(dict(gregorian=dt.date(int(gyear),GREGORIAN[gmonth],int(gday)).isoformat(),
                            year=int(year),month=HIJRI[month],day=int(day)))
    return validate_records(records)


def resolve(records,date):
    candidates=[]
    starts={}
    for record in records:
        start=dt.date.fromisoformat(record['gregorian'])-dt.timedelta(days=record['day']-1)
        starts[(record['year'],record['month'])]=start
    for record in records:
        start=starts[(record['year'],record['month'])]
        day=(date-start).days+1
        next_month=(record['year']+1,1) if record['month']==12 else (record['year'],record['month']+1)
        next_start=starts.get(next_month)
        explicit_day30=any(r['year']==record['year'] and r['month']==record['month'] and r['day']==30 for r in records)
        limit=(next_start-start).days if next_start else (30 if explicit_day30 else 29)
        if 1<=day<=limit:
            candidates.append(dict(year=record['year'],month=record['month'],day=day))
    if candidates and all(c==candidates[0] for c in candidates):
        return candidates[0]
    return None


class SourceRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urlsplit(newurl)
        if parsed.scheme!='https' or parsed.hostname not in ('habous.gov.ma','www.habous.gov.ma'):
            raise ValueError('unexpected calendar redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_habous():
    request=Request(URL,headers={'User-Agent':'OmarchyPrayerTimes/2.0 (+https://github.com/hassanaitnacer/omarchy-prayer-times)', 'Accept':'text/html'})
    with build_opener(SourceRedirects()).open(request,timeout=10) as response:
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('oversized calendar response')
        return parse_habous(raw.decode('utf-8'))


class AuthoritativeCalendar:
    def __init__(self,directory):
        self.path=Path(directory)/'calendar-habous.json'
        self.records=[]; self.checked=None; self.status='unverified'
        self.future=None; self.executor=None; self.next_refresh=0
        try:
            if self.path.stat().st_size>65536: raise ValueError('oversized cache')
            cached=json.loads(self.path.read_text())
            if cached['source']!=URL: raise ValueError('unknown source')
            self.records=validate_records(cached['records'])
            checked=dt.datetime.fromisoformat(cached['checked'])
            if checked.tzinfo is None: raise ValueError('cache timestamp needs timezone')
            self.checked=checked.isoformat()
            elapsed=(dt.datetime.now(dt.timezone.utc)-checked).total_seconds()
            self.next_refresh=time.monotonic()+max(0,min(3600,3600-elapsed))
            self.status='cached'
        except (OSError,ValueError,TypeError,KeyError):
            self.records=[]
            self.checked=None
            self.status='unverified'

    @staticmethod
    def source(cfg):
        choice=cfg.get('hijriSource','auto')
        if not cfg.get('hijri',True) or choice=='off': return 'off'
        if choice=='habous' or (choice=='auto' and cfg['timezone'] in ('Africa/Casablanca','Africa/El_Aaiun')): return 'habous'
        return 'unsupported'

    def date(self,date,cfg):
        return resolve(self.records,date) if self.source(cfg)=='habous' else None

    def info(self,date,cfg):
        source=self.source(cfg)
        value=self.date(date,cfg)
        status=self.status if value else ('unverified' if source=='habous' else source)
        return dict(status=status,source='Habous' if source=='habous' else '',url=URL if source=='habous' else '',checked=self.checked,date=value)

    def refresh(self,cfg,save):
        """Called from the daemon loop. Network never blocks prayer reminders."""
        now=time.monotonic()
        if self.future and self.future.done():
            try:
                records=self.future.result()
                self.records=validate_records(records)
                self.checked=dt.datetime.now(dt.timezone.utc).isoformat()
                self.status='synced'
                save(self.path,dict(source=URL,checked=self.checked,records=self.records))
            except (OSError,ValueError,TypeError,KeyError):
                self.status='cached' if self.records else 'unverified'
            finally:
                self.future=None
        if self.source(cfg)!='habous' or self.future or now<self.next_refresh:
            return
        self.next_refresh=now+3600
        if self.executor is None: self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='hijri-sync')
        self.future=self.executor.submit(fetch_habous)

    def close(self):
        if self.executor: self.executor.shutdown(wait=False,cancel_futures=True)
