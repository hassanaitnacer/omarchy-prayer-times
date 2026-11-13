"""Offline prayer calculations and civil-time rules. Standard-library only.

Solar equations: https://praytimes.org/docs/calculation
Profiles: https://praytimes.org/docs/calculation#calculation-methods
The legacy Morocco profile preserves v1 settings; it is not an official timetable.
Epoch seconds are used internally. No dependence on the machine's timezone.
"""
from __future__ import annotations
import functools
import math
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = dt.timezone.utc
PRAYERS = ('fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha')
PROFILES = {
    'morocco': (19, 17, 0), 'mwl': (18, 17, 0), 'isna': (15, 15, 0),
    'egypt': (19.5, 17.5, 0), 'karachi': (18, 18, 0),
    'ummalqura': (18.5, 0, 90), 'custom': (19, 17, 0),
}
LEGACY_MARGINS = dict(zip(PRAYERS, (0, -3, 5, 0, 5, 0)))

def number(value, fallback, low, high):
    if value is None or isinstance(value, bool) or value == '':
        return fallback
    try:
        n = float(value)
        return n if math.isfinite(n) and low <= n <= high else fallback
    except (ValueError, TypeError):
        return fallback


def clean(value, limit=80):
    return ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in str(value))[:limit].strip()


def safe_shared(value):
    # Native button/notification text may be rich text. Do not feed it markup.
    return clean(value, 512).replace('&', '＆').replace('<', '‹').replace('>', '›')


def config(raw=None):
    s = raw if isinstance(raw, dict) else {}
    method = s.get('method', 'custom' if 'fajrAngle' in s or 'ishaAngle' in s else 'morocco')
    if not isinstance(method, str) or method not in PROFILES:
        method = 'morocco'
    f, i, interval = PROFILES[method]
    # Existing custom angles retain their meaning until a named profile is picked.
    if 'method' not in s or method == 'custom':
        f = number(s.get('fajrAngle'), f, 5, 25)
        i = number(s.get('ishaAngle'), i or 17, 5, 25)
    legacy_zone = 'Africa/Casablanca'
    if s.get('city', 'Casablanca') != 'Casablanca' or number(s.get('latitude'), 33.5731, -90, 90) != 33.5731 or number(s.get('longitude'), -7.5898, -180, 180) != -7.5898:
        localtime = str(Path('/etc/localtime').resolve())
        if '/zoneinfo/' in localtime:
            legacy_zone = localtime.split('/zoneinfo/', 1)[1]
    zone = s.get('timezone', legacy_zone)
    if not isinstance(zone, str) or len(zone) > 80:
        raise ValueError('timezone')
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('timezone') from None
    adjust = s.get('adjust') if isinstance(s.get('adjust'), dict) else {}
    base = LEGACY_MARGINS if method in ('morocco', 'custom') else ({'dhuhr': 1} if method != 'ummalqura' else {})
    muted = s.get('muted', [])
    return {
        'city': clean(s.get('city', 'Casablanca'), 40) or 'Casablanca',
        'latitude': number(s.get('latitude'), 33.5731, -90, 90),
        'longitude': number(s.get('longitude'), -7.5898, -180, 180),
        'timezone': zone, 'method': method, 'fajrAngle': f, 'ishaAngle': i,
        'ishaInterval': interval, 'asrFactor': 2 if str(s.get('asrFactor')) in ('2', '2.0') else 1,
        'highLatitude': s.get('highLatitude') if s.get('highLatitude') in ('none', 'middle', 'seventh', 'angle') else 'none',
        'margins': {p: base.get(p, 0) + round(number(adjust.get(p), 0, -60, 60)) for p in PRAYERS},
        'notify': s.get('notify', True) is not False,
        'muted': [p for p in PRAYERS if isinstance(muted, list) and p in muted],
        'advance': s.get('advance', False) is True,
        'advanceMinutes': round(number(s.get('advanceMinutes'), 10, 1, 60)),
        'fasting': s.get('fasting', False) is True,
        'hijri': s.get('hijri', True) is not False,
        'hijriSource': s.get('hijriSource') if s.get('hijriSource') in ('auto','habous','off') else 'auto',
        'hijriAdjust': round(number(s.get('hijriAdjust'), 0, -2, 2)),
        'hijriAdjustDate': iso_date(s.get('hijriAdjustDate')),
        'sound': s.get('sound') if s.get('sound') in ('chime', 'file') else 'off',
        'audioFile': clean(s.get('audioFile', ''), 1024),
        'volume': round(number(s.get('volume'), 50, 0, 100)),
    }


def validate_setup(raw):
    """A public installation must explicitly select its location and method."""
    for key, low, high in (('latitude', -90, 90), ('longitude', -180, 180)):
        if number(raw.get(key), None, low, high) is None:
            raise ValueError('location')
    if not isinstance(raw.get('city'), str) or not clean(raw['city']):
        raise ValueError('location')
    if not isinstance(raw.get('timezone'), str) or not raw['timezone']:
        raise ValueError('timezone')
    if not isinstance(raw.get('method'), str) or raw['method'] not in PROFILES:
        raise ValueError('method')


def iso_date(value):
    try:
        return dt.date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def julian(date):
    return date.toordinal() + 1721424.5


def sun_position(jd):
    d = jd - 2451545
    g, q = (357.529 + .98560028 * d) % 360, (280.459 + .98564736 * d) % 360
    l = (q + 1.915 * math.sin(math.radians(g)) + .020 * math.sin(math.radians(2*g))) % 360
    e = math.radians(23.439 - .00000036*d)
    l = math.radians(l)
    ra = math.degrees(math.atan2(math.cos(e)*math.sin(l), math.cos(l))) / 15 % 24
    eq = (q/15-ra+12) % 24-12
    return math.degrees(math.asin(math.sin(e)*math.sin(l))), eq


def raw_times(date, cfg):
    lat, lon = cfg['latitude'], cfg['longitude']
    # Civil dates east of the international date line can precede the UTC
    # date used by a longitude-only solar calculation (e.g. Kiritimati).
    mean_noon = dt.datetime.combine(date, dt.time(12), UTC).timestamp()-lon/15*3600
    local_noon_date = dt.datetime.fromtimestamp(mean_noon, ZoneInfo(cfg['timezone'])).date()
    date -= dt.timedelta(days=(local_noon_date-date).days)
    jd = julian(date)-lon/360
    def noon(h):
        return (12-sun_position(jd+h/24)[1]) % 24
    def at(alt, h, direction):
        dec = math.radians(sun_position(jd+h/24)[0])
        den = math.cos(dec)*math.cos(math.radians(lat))
        if abs(den) < 1e-12:
            return math.nan
        x = (math.sin(math.radians(alt))-math.sin(dec)*math.sin(math.radians(lat)))/den
        return noon(h)+direction*math.degrees(math.acos(x))/15 if -1 <= x <= 1 else math.nan
    hours = dict(zip(PRAYERS, (5, 6, 12, 13, 18, 18)))
    for _ in range(3):
        # Re-use a finite seed for unreachable events; never poison a later pass.
        seeds = {p: h if math.isfinite(h) else (5 if p == 'fajr' else 18) for p, h in hours.items()}
        dec = sun_position(jd+seeds['asr']/24)[0]
        asr_alt = math.degrees(math.atan(1/(cfg['asrFactor']+math.tan(math.radians(abs(lat-dec))))))
        hours = {
            'fajr': at(-cfg['fajrAngle'], seeds['fajr'], -1),
            'sunrise': at(-.833, seeds['sunrise'], -1),
            'dhuhr': noon(seeds['dhuhr']), 'asr': at(asr_alt, seeds['asr'], 1),
            'maghrib': at(-.833, seeds['maghrib'], 1),
            'isha': at(-cfg['ishaAngle'], seeds['isha'], 1),
        }
    midnight = dt.datetime.combine(date, dt.time(), UTC).timestamp()
    return {p: midnight+(h-lon/15)*3600 if math.isfinite(h) else None for p,h in hours.items()}


def tabular_hijri(date):
    # Tabular Islamic civil calendar, epoch 1 Muharram 1 AH = 622-07-19 Gregorian.
    def islamic_jd(year, month, day):
        return day+math.ceil(29.5*(month-1))+(year-1)*354+math.floor((3+11*year)/30)+1948439.5-1
    jd = julian(date)
    year = math.floor((30*(jd-1948439.5)+10646)/10631)
    month = min(12, math.ceil((jd-(29+islamic_jd(year, 1, 1)))/29.5)+1)
    day = int(jd-islamic_jd(year, month, 1)+1)
    return {'year': year, 'month': month, 'day': day}


def moon_position(jd):
    # Low-precision lunar ecliptic longitude, latitude and parallax in degrees
    # (Astronomical Almanac series; about 0.3 degrees, ample for a day estimate).
    t = (jd-2451545)/36525
    def s(a, b): return math.sin(math.radians(a+b*t))
    def c(a, b): return math.cos(math.radians(a+b*t))
    lon = (218.32+481267.881*t+6.29*s(135.0, 477198.87)-1.27*s(259.3, -413335.36)+.66*s(235.7, 890534.22)
           +.21*s(269.9, 954397.74)-.19*s(357.5, 35999.05)-.11*s(186.5, 966404.03)) % 360
    lat = 5.13*s(93.3, 483202.02)+.28*s(228.2, 960400.89)-.28*s(318.3, 6003.15)-.17*s(217.6, -407332.21)
    parallax = .9508+.0518*c(135.0, 477198.87)+.0095*c(259.3, -413335.36)+.0078*c(235.7, 890534.22)+.0028*c(269.9, 954397.74)
    return lon, lat, parallax


def crescent(date, cfg):
    """(moon-sun elongation in longitude, Yallop q) at local sunset, or None."""
    lat = max(-60, min(60, cfg['latitude']))
    sunset = raw_times(date, dict(cfg, latitude=lat))['maghrib']
    if sunset is None:
        return None
    jd = sunset/86400+2440587.5
    d = jd-2451545
    g = math.radians(357.529+.98560028*d)
    sun = (280.459+.98564736*d+1.915*math.sin(g)+.020*math.sin(2*g)) % 360
    lon, beta, parallax = moon_position(jd)
    e = math.radians(23.439-.00000036*d)
    def altitude(l, b):
        l, b = math.radians(l), math.radians(b)
        dec = math.asin(math.sin(b)*math.cos(e)+math.cos(b)*math.sin(e)*math.sin(l))
        ra = math.atan2(math.sin(l)*math.cos(e)-math.tan(b)*math.sin(e), math.cos(l))
        hour = math.radians(280.46061837+360.98564736629*d+cfg['longitude'])-ra
        return math.degrees(math.asin(math.sin(math.radians(lat))*math.sin(dec)+math.cos(math.radians(lat))*math.cos(dec)*math.cos(hour)))
    moon_alt = altitude(lon, beta)
    arcv = moon_alt-altitude(sun, 0)
    arcl = math.acos(math.cos(math.radians(beta))*math.cos(math.radians(lon-sun)))
    width = .27245*parallax*60*(1+math.sin(math.radians(moon_alt))*math.sin(math.radians(parallax)))*(1-math.cos(arcl))
    return (lon-sun) % 360, (arcv-(11.8371-6.3226*width+.7319*width**2-.1018*width**3))/10


@functools.lru_cache(maxsize=8)
def _month_starts(year, lat, lon, zone):
    # First civil day of each lunar month around `year`: the day after the first
    # evening on which the new crescent is predicted to be visible to the naked
    # eye (Yallop q > -0.014) at the configured place. Months are 29 or 30 days.
    cfg = {'latitude': lat, 'longitude': lon, 'timezone': zone, 'fajrAngle': 18, 'ishaAngle': 18, 'asrFactor': 1}
    date, last = dt.date(year-1, 10, 1), dt.date(year+1, 2, 28)
    starts, waiting, previous = [], False, None
    while date <= last:
        seen = crescent(date, cfg)
        if seen is not None:
            if previous is not None and seen[0] < previous:
                waiting = True
            previous = seen[0]
            if waiting and seen[1] > -.014:
                start = date+dt.timedelta(days=1)
                if starts:
                    start = min(max(start, starts[-1]+dt.timedelta(days=29)), starts[-1]+dt.timedelta(days=30))
                starts.append(start)
                waiting = False
        date += dt.timedelta(days=1)
    return tuple(starts)


def hijri(date, cfg=None):
    """Estimated observational Hijri date for the configured place.

    hijriAdjust with hijriAdjustDate corrects the month that was current on that
    date (its start moves by the adjustment; later months are recalculated from
    it). Without a date it shifts every day, as older settings did.
    """
    if cfg is None:
        return tabular_hijri(date)
    adjust, anchor = cfg.get('hijriAdjust', 0), cfg.get('hijriAdjustDate')
    if adjust and not anchor:
        date, adjust = date+dt.timedelta(days=adjust), 0
    if not 1900 <= date.year <= 2200:
        return tabular_hijri(date)
    starts = list(_month_starts(date.year, round(cfg['latitude'], 2), round(cfg['longitude'], 2), cfg['timezone']))
    if adjust:
        shifted = anchor+dt.timedelta(days=adjust)
        i = max((n for n, s in enumerate(starts) if s <= shifted), default=None)
        if i is not None and (shifted-starts[i]).days < 30:
            starts[i] -= dt.timedelta(days=adjust)
            for n in range(i+1, len(starts)):
                starts[n] = min(max(starts[n], starts[n-1]+dt.timedelta(days=29)), starts[n-1]+dt.timedelta(days=30))
    i = max((n for n, s in enumerate(starts) if s <= date), default=None)
    if i is None or (i+1 == len(starts) and (date-starts[i]).days > 29):
        return tabular_hijri(date)
    name = tabular_hijri(starts[i]+dt.timedelta(days=14))
    return {'year': name['year'], 'month': name['month'], 'day': (date-starts[i]).days+1}


def times(date, cfg, calendar=None):
    t = raw_times(date, cfg)
    estimated = set()
    rule = cfg['highLatitude']
    if rule != 'none' and t['sunrise'] is not None and t['maghrib'] is not None:
        prev = raw_times(date-dt.timedelta(days=1), cfg)['maghrib']
        following = raw_times(date+dt.timedelta(days=1), cfg)['sunrise']
        def fraction(angle):
            return .5 if rule == 'middle' else 1/7 if rule == 'seventh' else angle/60
        for p, edge, other, sign in (('fajr', t['sunrise'], prev, -1), ('isha', t['maghrib'], following, 1)):
            if other is None or (p == 'isha' and cfg['ishaInterval']):
                continue
            portion = abs(edge-other)*fraction(cfg['fajrAngle' if p == 'fajr' else 'ishaAngle'])
            if t[p] is None or abs(t[p]-edge) > portion:
                t[p] = edge+sign*portion
                estimated.add(p)
    if cfg['ishaInterval'] and t['maghrib'] is not None:
        calendar_date = calendar(date) if calendar else hijri(date, cfg)
        if calendar_date is None:
            # Preserve offline prayer calculations, but expose uncertainty in
            # the Ramadan interval instead of labelling it authoritative.
            calendar_date = hijri(date, cfg)
            estimated.add('isha')
        ramadan = calendar_date['month'] == 9
        t['isha'] = t['maghrib']+(120 if ramadan else cfg['ishaInterval'])*60
    for p in PRAYERS:
        if t[p] is not None:
            t[p] = math.floor(t[p]/60+cfg['margins'][p]+.5)*60
    return t, estimated


def snapshot(cfg, now, offset=0, calendar=None):
    zone = ZoneInfo(cfg['timezone'])
    today = dt.datetime.fromtimestamp(now, zone).date()
    target = today+dt.timedelta(days=max(-366, min(366, offset)))
    cache = {}
    def day(date):
        if date not in cache:
            cache[date] = times(date,cfg,calendar)
        return cache[date]
    def row(p,t,estimated=False):
        local = dt.datetime.fromtimestamp(t,zone) if t is not None else None
        return {'name':p, 'time':t, 'hour':local.hour if local else None,
                'minute':local.minute if local else None, 'estimated':estimated}
    target_times, est = day(target)
    rows = [row(p,target_times[p],p in est) for p in PRAYERS]
    events=[]
    for date in (today-dt.timedelta(days=1),today,today+dt.timedelta(days=1)):
        ts, estimates = day(date)
        for p in PRAYERS:
            if p != 'sunrise' and ts[p] is not None:
                r = row(p,ts[p],p in estimates)
                r['date'] = date.isoformat()
                events.append(r)
    events.sort(key=lambda r:r['time'])
    next_event = next((r for r in events if r['time']>now),None)
    previous = next((r for r in reversed(events) if r['time']<=now),None)
    ts,_ = day(today)
    sunrise = ts['sunrise']
    fajr_end = sunrise if ts['fajr'] is not None and sunrise is not None and ts['fajr']<=now<sunrise else None
    fasting = None
    for date in (today,today+dt.timedelta(days=1)):
        ts, estimates = day(date)
        for name, p in (('suhoor','fajr'),('iftar','maghrib')):
            if ts[p] is not None and ts[p]>now:
                fasting = {'name':name,'time':ts[p], 'estimated':p in estimates}
                break
        if fasting:
            break
    return {'today':today.isoformat(),'date':target.isoformat(),'year':target.year,'month':target.month,'day':target.day,
            'rows':rows,'next':next_event,'previous':previous,'fajrEnd':fajr_end,'fasting':fasting,
            'hijri':calendar(target) if calendar else hijri(target, cfg), 'events':events,
            'timezone':cfg['timezone'], 'city':cfg['city'],'method':cfg['method'],'now':now,
            'estimated':bool(est),'unavailable':any(r['time'] is None for r in rows)}


def due_event(events, now, last_tick, cfg):
    if not cfg['notify']:
        return None
    eligible = [r for r in events if r['name'] not in cfg['muted']]
    recent = [r for r in eligible if 0 <= now-r['time'] < 15*60]
    if recent:
        r = max(recent,key=lambda r:r['time'])
        return dict(r, kind='prayer', audible=last_tick is not None and 0<=now-last_tick<=90 and now-r['time']<60)
    # Advance reminders are only generated by a continuously running service.
    if cfg['advance'] and last_tick is not None and 0<=now-last_tick<=90:
        for r in eligible:
            due = r['time']-cfg['advanceMinutes']*60
            if 0<=now-due<60 and r['time']>now:
                return dict(r,kind='advance',audible=False)
    return None


def cities():
    """Offline timezone reference cities from the system IANA database."""
    out = [{'city':'Casablanca','timezone':'Africa/Casablanca','latitude':33.5731,'longitude':-7.5898}]
    def coordinate(text):
        sign = -1 if text[0]=='-' else 1
        s=text[1:]; degrees=2 if len(s) in (4,6) else 3
        return sign*(int(s[:degrees])+int(s[degrees:degrees+2])/60+(int(s[degrees+2:])/3600 if len(s)>degrees+2 else 0))
    for line in Path('/usr/share/zoneinfo/zone.tab').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        _, coord, zone, *_ = line.split('\t')
        if zone=='Africa/Casablanca':
            continue
        split = next(i for i in range(1,len(coord)) if coord[i] in '+-')
        out.append({'city':zone.rsplit('/',1)[-1].replace('_',' '),'timezone':zone,
                    'latitude':coordinate(coord[:split]),'longitude':coordinate(coord[split:])})
    return sorted(out,key=lambda r:r['city'])
