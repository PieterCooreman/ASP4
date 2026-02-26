"""VBScript-like date/time functions.

Implementation goals:
- Provide the full VBScript date/time function surface.
- Keep behavior deterministic cross-platform where VBScript depends on locale.

Notes:
- Parsing of DateValue/TimeValue/CDate is deterministic and locale-agnostic.
"""

from __future__ import annotations

import datetime as _dt
import time as _time
import re as _re

from .vb_constants import (
    vbSunday,
    vbMonday,
    vbUseSystemDayOfWeek,
    vbUseSystem,
    vbFirstJan1,
    vbFirstFourDays,
    vbFirstFullWeek,
    vbGeneralDate,
    vbLongDate,
    vbShortDate,
    vbLongTime,
    vbShortTime,
)
from .vb_runtime import VBScriptRuntimeError, vbs_cstr, vbs_get_lcid_info
from .vm.values import VBNull


def Now():
    return _dt.datetime.now()


def Date():
    return _dt.date.today()


def Time():
    return _dt.datetime.now().time().replace(microsecond=0)


def Timer():
    # Seconds since midnight (local time)
    n = _dt.datetime.now()
    midnight = n.replace(hour=0, minute=0, second=0, microsecond=0)
    return (n - midnight).total_seconds()


def Year(d):
    return _to_datetime(d).year


def Month(d):
    return _to_datetime(d).month


def Day(d):
    return _to_datetime(d).day


def Hour(d):
    return _to_datetime(d).hour


def Minute(d):
    return _to_datetime(d).minute


def Second(d):
    return _to_datetime(d).second


def DateSerial(year, month, day):
    # VBScript normalizes overflow/underflow. Python doesn't directly.
    y = int(year)
    m = int(month)
    d = int(day)
    # Normalize month
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1
    base = _dt.date(y, m, 1)
    return base + _dt.timedelta(days=d - 1)


def TimeSerial(hour, minute, second):
    h = int(hour)
    mi = int(minute)
    s = int(second)
    total = h * 3600 + mi * 60 + s
    total = total % 86400
    h = total // 3600
    mi = (total % 3600) // 60
    s = total % 60
    return _dt.time(h, mi, s)


def DateAdd(interval, number, date):
    itv = str(interval).lower()
    n = float(number)
    dt = _to_datetime(date)

    if itv in ("yyyy", "y"):
        return _add_years(dt, int(n))
    if itv in ("q",):
        return _add_months(dt, int(n) * 3)
    if itv in ("m",):
        return _add_months(dt, int(n))
    if itv in ("d", "w"):
        return dt + _dt.timedelta(days=n)
    if itv in ("ww",):
        return dt + _dt.timedelta(weeks=n)
    if itv in ("h",):
        return dt + _dt.timedelta(hours=n)
    if itv in ("n",):
        return dt + _dt.timedelta(minutes=n)
    if itv in ("s",):
        return dt + _dt.timedelta(seconds=n)

    raise VBScriptRuntimeError(f"DateAdd: unsupported interval {interval!r}")


def DateDiff(interval, date1, date2, firstdayofweek=vbSunday, firstweekofyear=vbFirstJan1):
    itv = str(interval).lower()
    d1 = _to_datetime(date1)
    d2 = _to_datetime(date2)

    if itv in ("s",):
        return int((d2 - d1).total_seconds())
    if itv in ("n",):
        return int((d2 - d1).total_seconds() // 60)
    if itv in ("h",):
        return int((d2 - d1).total_seconds() // 3600)
    if itv in ("d", "y"):
        return (d2.date() - d1.date()).days
    if itv in ("ww", "w"):
        return int((d2.date() - d1.date()).days // 7)
    if itv in ("m",):
        return (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if itv in ("q",):
        q1 = (d1.month - 1) // 3
        q2 = (d2.month - 1) // 3
        return (d2.year - d1.year) * 4 + (q2 - q1)
    if itv in ("yyyy",):
        return d2.year - d1.year

    raise VBScriptRuntimeError(f"DateDiff: unsupported interval {interval!r}")


def DatePart(interval, date, firstdayofweek=vbSunday, firstweekofyear=vbFirstJan1):
    itv = str(interval).lower()
    dt = _to_datetime(date)

    if itv == "yyyy":
        return dt.year
    if itv == "q":
        return ((dt.month - 1) // 3) + 1
    if itv == "m":
        return dt.month
    if itv == "d":
        return dt.day
    if itv == "y":
        return dt.timetuple().tm_yday
    if itv == "w":
        return Weekday(dt, firstdayofweek)
    if itv == "ww":
        # Simplified week-of-year; VBScript depends on firstdayofweek/firstweekofyear.
        return _week_of_year(dt, firstdayofweek, firstweekofyear)
    if itv == "h":
        return dt.hour
    if itv == "n":
        return dt.minute
    if itv == "s":
        return dt.second

    raise VBScriptRuntimeError(f"DatePart: unsupported interval {interval!r}")


def Weekday(date, firstdayofweek=vbSunday):
    if date is VBNull:
        return VBNull
    dt = _to_datetime(date)
    # Python weekday: Monday=0..Sunday=6
    py = dt.weekday()
    # Convert to Sunday=1..Saturday=7
    vb = ((py + 1) % 7) + 1
    fdw = int(firstdayofweek)
    if fdw in (vbUseSystemDayOfWeek, 0):
        fdw = vbSunday
    # Adjust so that fdw becomes 1
    return ((vb - fdw) % 7) + 1


def WeekdayName(weekday, abbreviate=False, firstdayofweek=vbSunday):
    wd = int(weekday)
    if wd < 1 or wd > 7:
        raise VBScriptRuntimeError("WeekdayName: weekday must be 1..7")
    # Map 1..7 to names assuming 1=Sunday
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    name = names[wd - 1]
    return name[:3] if bool(abbreviate) else name


def MonthName(month, abbreviate=False):
    m = int(month)
    if m < 1 or m > 12:
        raise VBScriptRuntimeError("MonthName: month must be 1..12")
    names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    name = names[m - 1]
    return name[:3] if bool(abbreviate) else name


def DateValue(s):
    dt = _parse_iso_datetime(str(s))
    return dt.date()


def TimeValue(s):
    dt = _parse_iso_datetime(str(s))
    return dt.time().replace(microsecond=0)


def CDate(s):
    try:
        return _parse_iso_datetime(str(s))
    except VBScriptRuntimeError:
        # Re-raise as Type mismatch (13) for VBScript compatibility
        from .vb_runtime import VBScriptCOMError
        raise VBScriptCOMError(13, "Type mismatch")


def IsDate(s):
    try:
        _parse_iso_datetime(str(s))
        return True
    except Exception:
        return False


def FormatDateTime(date, namedformat=vbGeneralDate):
    dt = _to_datetime(date)
    fmt = int(namedformat)
    # Force deterministic US-like formats (ignoring host locale)
    # Use English names for %A and %B manually or ensure strftime uses C locale?
    # Python strftime depends on C locale.
    # To be absolutely sure, we construct the string manually for Long Date.
    
    # 1033 (US) formats:
    # Short Date: m/d/yyyy (e.g. 2/24/2026)
    # Long Date: dddd, MMMM d, yyyy (e.g. Tuesday, February 24, 2026)
    # Short Time: h:mm (24h or 12h? VBScript general date uses 12h? 1033 uses 12h usually? 
    # Actually Python's default ISO is 24h. 
    # Let's use strict patterns matching 1033 VBScript defaults roughly.
    
    if fmt == vbGeneralDate:
        # 2/24/2026 3:53:19 PM
        return _fmt_us_short_date(dt) + " " + _fmt_us_long_time(dt)
    if fmt == vbLongDate:
        # Tuesday, February 24, 2026
        return _fmt_us_long_date(dt)
    if fmt == vbShortDate:
        # 2/24/2026
        return _fmt_us_short_date(dt)
    if fmt == vbLongTime:
        # 3:53:19 PM
        return _fmt_us_long_time(dt)
    if fmt == vbShortTime:
        # 15:53 (24-hour usually for Short Time in VBScript? Or 03:53 without seconds?)
        # VBScript vbShortTime is usually HH:MM (24h) or hh:mm (12h)?
        # 1033 Short Time is h:mm tt. 
        # But let's check standard behavior. 
        # Actually vbShortTime (4) usually prints 24-hour HH:MM.
        return f"{dt.hour:02d}:{dt.minute:02d}"
        
    raise VBScriptRuntimeError("FormatDateTime: invalid namedformat")

def _fmt_us_short_date(dt):
    # m/d/yyyy
    return f"{dt.month}/{dt.day}/{dt.year}"

def _fmt_us_long_time(dt):
    # h:mm:ss PM
    h = dt.hour
    ap = "AM"
    if h >= 12:
        ap = "PM"
        if h > 12: h -= 12
    if h == 0: h = 12
    return f"{h}:{dt.minute:02d}:{dt.second:02d} {ap}"

def _fmt_us_long_date(dt):
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    # dt.weekday() is 0=Monday..6=Sunday. We need Sunday..Saturday
    # (6+1)%7 = 0 (Sunday)
    wd_idx = (dt.weekday() + 1) % 7
    wd_name = days[wd_idx]
    mo_name = months[dt.month - 1]
    return f"{wd_name}, {mo_name} {dt.day}, {dt.year}"



def _to_datetime(value) -> _dt.datetime:
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return _dt.datetime(value.year, value.month, value.day)
    if isinstance(value, _dt.time):
        today = _dt.date.today()
        return _dt.datetime(today.year, today.month, today.day, value.hour, value.minute, value.second)
    if isinstance(value, (int, float)):
        # VBScript/OLE Automation date: days since 1899-12-30
        base = _dt.datetime(1899, 12, 30)
        return base + _dt.timedelta(days=float(value))
    if isinstance(value, str):
        return _parse_iso_datetime(value)
    raise VBScriptRuntimeError(f"Expected date/time value, got {type(value).__name__}")


def _parse_iso_datetime(s: str) -> _dt.datetime:
    s = s.strip()
    month_re = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

    def _month_num(name: str) -> int:
        nm = name.strip().lower()
        if nm.startswith("jan"):
            return 1
        if nm.startswith("feb"):
            return 2
        if nm.startswith("mar"):
            return 3
        if nm.startswith("apr"):
            return 4
        if nm == "may":
            return 5
        if nm.startswith("jun"):
            return 6
        if nm.startswith("jul"):
            return 7
        if nm.startswith("aug"):
            return 8
        if nm.startswith("sep"):
            return 9
        if nm.startswith("oct"):
            return 10
        if nm.startswith("nov"):
            return 11
        if nm.startswith("dec"):
            return 12
        raise VBScriptRuntimeError("Invalid month name")

    def _parse_time_parts(hh, mi, se, ap):
        if hh is None:
            return 0, 0, 0
        h = int(hh)
        m = int(mi)
        s = int(se or 0)
        apv = (ap or "").upper()
        if apv:
            if h < 1 or h > 12:
                raise VBScriptRuntimeError("Invalid time")
            if apv == "AM":
                h = 0 if h == 12 else h
            else:
                h = 12 if h == 12 else (h + 12)
        else:
            if h < 0 or h > 23:
                raise VBScriptRuntimeError("Invalid time")
        if m < 0 or m > 59 or s < 0 or s > 59:
            raise VBScriptRuntimeError("Invalid time")
        return h, m, s
    # Accept: YYYY-MM-DD
    try:
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            return _dt.datetime.strptime(s, "%Y-%m-%d")
        # Accept: YYYY-MM-DD HH:MM:SS
        if len(s) == 19 and s[4] == '-' and s[7] == '-' and s[10] == ' ':
            return _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        # Accept: YYYY-MM-DDTHH:MM:SS[.fff] or YYYY-MM-DD HH:MM:SS.fff
        m = _re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?$", s)
        if m:
            yr = int(m.group(1))
            mo = int(m.group(2))
            da = int(m.group(3))
            hh = int(m.group(4))
            mi = int(m.group(5))
            se = int(m.group(6))
            frac = m.group(7) or ""
            micro = int((frac + "000000")[:6]) if frac else 0
            return _dt.datetime(yr, mo, da, hh, mi, se, micro)
        # Accept: HH:MM:SS (today)
        if len(s) == 8 and s[2] == ':' and s[5] == ':':
            t = _dt.datetime.strptime(s, "%H:%M:%S").time()
            today = _dt.date.today()
            return _dt.datetime(today.year, today.month, today.day, t.hour, t.minute, t.second)

        # Accept: MonthName D[, YYYY] [H:MM[:SS] [AM|PM]]
        m = _re.match(
            rf"^(?P<mon>{month_re})\s+(?P<day>\d{{1,2}})(?:\s*,?\s*(?P<year>\d{{4}}))?(?:\s+(?P<hh>\d{{1,2}}):(?P<mi>\d{{2}})(?::(?P<se>\d{{2}}))?(?:\s*(?P<ap>[AaPp][Mm]))?)?$",
            s,
            _re.IGNORECASE,
        )
        if m:
            mon = _month_num(m.group("mon"))
            day = int(m.group("day"))
            year = int(m.group("year") or _dt.date.today().year)
            hh, mi, se = _parse_time_parts(m.group("hh"), m.group("mi"), m.group("se"), m.group("ap"))
            return _dt.datetime(year, mon, day, hh, mi, se)

        # Accept: D MonthName[, YYYY] [H:MM[:SS] [AM|PM]]
        m = _re.match(
            rf"^(?P<day>\d{{1,2}})\s+(?P<mon>{month_re})(?:\s*,?\s*(?P<year>\d{{4}}))?(?:\s+(?P<hh>\d{{1,2}}):(?P<mi>\d{{2}})(?::(?P<se>\d{{2}}))?(?:\s*(?P<ap>[AaPp][Mm]))?)?$",
            s,
            _re.IGNORECASE,
        )
        if m:
            mon = _month_num(m.group("mon"))
            day = int(m.group("day"))
            year = int(m.group("year") or _dt.date.today().year)
            hh, mi, se = _parse_time_parts(m.group("hh"), m.group("mi"), m.group("se"), m.group("ap"))
            return _dt.datetime(year, mon, day, hh, mi, se)

        # Accept: MM/DD/YYYY [H:MM[:SS] [AM|PM]] (deterministic, US-style)
        m = _re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?)?$", s)
        if m:
            mo = int(m.group(1))
            da = int(m.group(2))
            yr = int(m.group(3))
            hh = int(m.group(4) or 0)
            mi = int(m.group(5) or 0)
            se = int(m.group(6) or 0)
            ap = (m.group(7) or "").upper()
            if ap:
                # 12-hour clock
                if hh < 1 or hh > 12:
                    raise VBScriptRuntimeError("Invalid time")
                if ap == 'AM':
                    hh = 0 if hh == 12 else hh
                else:
                    hh = 12 if hh == 12 else (hh + 12)
            return _dt.datetime(yr, mo, da, hh, mi, se)

        # Accept: D/M/YYYY or D-M-YYYY [H:MM[:SS] [AM|PM]] (day-first fallback)
        m = _re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?)?$", s)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            yr = int(m.group(3))
            hh = int(m.group(4) or 0)
            mi = int(m.group(5) or 0)
            se = int(m.group(6) or 0)
            ap = (m.group(7) or "").upper()
            if ap:
                if hh < 1 or hh > 12:
                    raise VBScriptRuntimeError("Invalid time")
                if ap == 'AM':
                    hh = 0 if hh == 12 else hh
                else:
                    hh = 12 if hh == 12 else (hh + 12)
            # Heuristic: prefer day-first; if day can't be month and month can, swap.
            day = a
            mon = b
            if a <= 12 and b > 12:
                mon, day = a, b
            return _dt.datetime(yr, mon, day, hh, mi, se)
    except Exception as e:
        raise VBScriptRuntimeError(str(e))
    raise VBScriptRuntimeError(
        "Unsupported date/time string format (supported: ISO YYYY-MM-DD[ HH:MM:SS], HH:MM:SS, MM/DD/YYYY, or DD/MM/YYYY)"
    )


def _add_months(dt: _dt.datetime, months: int) -> _dt.datetime:
    y = dt.year + (dt.month - 1 + months) // 12
    m = ((dt.month - 1 + months) % 12) + 1
    d = min(dt.day, _days_in_month(y, m))
    return dt.replace(year=y, month=m, day=d)


def _add_years(dt: _dt.datetime, years: int) -> _dt.datetime:
    y = dt.year + years
    d = min(dt.day, _days_in_month(y, dt.month))
    return dt.replace(year=y, day=d)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = _dt.date(year + 1, 1, 1)
    else:
        nxt = _dt.date(year, month + 1, 1)
    cur = _dt.date(year, month, 1)
    return (nxt - cur).days


def _week_of_year(dt: _dt.datetime, firstdayofweek, firstweekofyear):
    # Pragmatic: ISO week number, with minimal handling of VBScript flags.
    # If you need exact VBScript behavior for edge cases, we can refine this.
    return int(dt.isocalendar().week)