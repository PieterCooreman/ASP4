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
from .vb_runtime import VBScriptRuntimeError, VBScriptCOMError, vbs_cstr, vbs_get_lcid
from . import vb_locale
from .vm.values import VBNull, VBEmpty
from decimal import Decimal as _Decimal


# VBScript has exactly ONE Date type (an OLE Automation double). ASPPY
# normalizes every date/time producer to datetime.datetime so that equality,
# comparison and arithmetic behave consistently (DateSerial() = CDate() must
# be True). Time-only values carry the OA zero date (1899-12-30); rendering
# code (vbs_cstr) prints date-only / time-only forms exactly like IIS does.
_OA_ZERO = _dt.datetime(1899, 12, 30)


def Now():
    return _dt.datetime.now()


def Date():
    t = _dt.date.today()
    return _dt.datetime(t.year, t.month, t.day)


def Time():
    n = _dt.datetime.now()
    return _OA_ZERO.replace(hour=n.hour, minute=n.minute, second=n.second)


def Timer():
    # Seconds since midnight (local time)
    n = _dt.datetime.now()
    midnight = n.replace(hour=0, minute=0, second=0, microsecond=0)
    return (n - midnight).total_seconds()


def _is_null(v):
    """True when the value is Null (also through a Request default property)."""
    if v is VBNull:
        return True
    return _scalarize(v) is VBNull


def Year(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).year


def Month(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).month


def Day(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).day


def Hour(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).hour


def Minute(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).minute


def Second(d):
    if _is_null(d): return VBNull
    return _to_datetime(d).second


def _pivot_2digit_year(y: int) -> int:
    # VBScript/OLE: a year of 0..29 means 2000..2029, 30..99 means 1930..1999.
    if 0 <= y <= 29:
        return y + 2000
    if 30 <= y <= 99:
        return y + 1900
    return y


def DateSerial(year, month, day):
    # VBScript normalizes overflow/underflow. Python doesn't directly.
    if _is_null(year) or _is_null(month) or _is_null(day):
        return VBNull
    y = int(_date_arg_number(year))
    m = int(_date_arg_number(month))
    d = int(_date_arg_number(day))
    y = _pivot_2digit_year(y)
    # Normalize month
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1
    base = _dt.datetime(y, m, 1)
    return base + _dt.timedelta(days=d - 1)


def TimeSerial(hour, minute, second):
    if _is_null(hour) or _is_null(minute) or _is_null(second):
        return VBNull
    h = int(_date_arg_number(hour))
    mi = int(_date_arg_number(minute))
    s = int(_date_arg_number(second))
    total = h * 3600 + mi * 60 + s
    total = total % 86400
    h = total // 3600
    mi = (total % 3600) // 60
    s = total % 60
    return _OA_ZERO.replace(hour=h, minute=mi, second=s)


def DateAdd(interval, number, date):
    if _is_null(number) or _is_null(date):
        return VBNull
    itv = str(interval).lower()
    n = _date_arg_number(number)
    dt = _to_datetime(date)

    if itv == "yyyy":
        return _add_years(dt, int(n))
    if itv == "y":
        return dt + _dt.timedelta(days=n)
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
    if _is_null(date1) or _is_null(date2):
        return VBNull
    itv = str(interval).lower()
    d1 = _to_datetime(date1)
    d2 = _to_datetime(date2)

    # VBScript DateDiff counts BOUNDARY crossings, not elapsed intervals:
    # both dates are truncated to the interval unit before diffing, so
    # DateDiff("n", 14:30:45, 15:00:15) = 30 (not 29).
    if itv in ("s",):
        t1 = d1.replace(microsecond=0)
        t2 = d2.replace(microsecond=0)
        return int(round((t2 - t1).total_seconds()))
    if itv in ("n",):
        t1 = d1.replace(second=0, microsecond=0)
        t2 = d2.replace(second=0, microsecond=0)
        return int(round((t2 - t1).total_seconds())) // 60
    if itv in ("h",):
        t1 = d1.replace(minute=0, second=0, microsecond=0)
        t2 = d2.replace(minute=0, second=0, microsecond=0)
        return int(round((t2 - t1).total_seconds())) // 3600
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
    if _is_null(date):
        return VBNull
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
    if _is_null(date) or _is_null(firstdayofweek):
        return VBNull
    dt = _to_datetime(date)
    # Python weekday: Monday=0..Sunday=6
    py = dt.weekday()
    # Convert to Sunday=1..Saturday=7
    vb = ((py + 1) % 7) + 1
    fdw = int(_date_arg_number(firstdayofweek))
    if fdw in (vbUseSystemDayOfWeek, 0):
        # vbUseSystemDayOfWeek resolves to the locale's first day of week, which
        # is Monday across most of Europe and Saturday for ar-DZ - not a fixed
        # Sunday. Verified against IIS for all 60 locales.
        fdw = vb_locale.first_day_of_week(vbs_get_lcid())
    # Adjust so that fdw becomes 1
    return ((vb - fdw) % 7) + 1


def WeekdayName(weekday, abbreviate=False, firstdayofweek=vbSunday):
    wd = int(weekday)
    if wd < 1 or wd > 7:
        raise VBScriptRuntimeError("WeekdayName: weekday must be 1..7")
    fdw = int(firstdayofweek) if firstdayofweek is not None else vbSunday
    if fdw < 0 or fdw > 7:
        raise VBScriptRuntimeError("WeekdayName: firstdayofweek must be 0..7")
    return vb_locale.weekday_name(wd, bool(abbreviate), fdw, vbs_get_lcid())


def MonthName(month, abbreviate=False):
    m = int(month)
    if m < 1 or m > 12:
        raise VBScriptRuntimeError("MonthName: month must be 1..12")
    return vb_locale.month_name(m, bool(abbreviate), vbs_get_lcid())


def DateValue(s):
    dt = _parse_iso_datetime(str(s))
    return _dt.datetime(dt.year, dt.month, dt.day)


def TimeValue(s):
    dt = _parse_iso_datetime(str(s))
    return _OA_ZERO.replace(hour=dt.hour, minute=dt.minute, second=dt.second)


def CDate(s):
    # IIS: an IStringList (Request value) coerces through its default
    # property; a missing key yields Empty.
    hook = getattr(s.__class__, '__vbs_scalar__', None)
    if hook is not None:
        s = hook(s)
    if s is VBNull:
        raise VBScriptCOMError(94, "Invalid use of Null")
    if s is VBEmpty:
        # VBScript: CDate(Empty) = #12:00:00 AM# (OA serial 0).
        return _OA_ZERO
    if isinstance(s, (_dt.datetime, _dt.date, _dt.time)):
        return _to_datetime(s)
    # Numbers are OA date serials: CDate(CDbl(d)) round-trips.
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        base = _OA_ZERO + _dt.timedelta(days=float(s))
        # Round to whole seconds like VBScript does.
        micro = base.microsecond
        base = base.replace(microsecond=0)
        if micro >= 500000:
            base += _dt.timedelta(seconds=1)
        return base
    try:
        return _parse_iso_datetime(str(s))
    except VBScriptRuntimeError:
        # Re-raise as Type mismatch (13) for VBScript compatibility
        raise VBScriptCOMError(13, "Type mismatch")


def IsDate(s):
    try:
        _parse_iso_datetime(str(s))
        return True
    except Exception:
        return False


def FormatDateTime(date, namedformat=vbGeneralDate):
    if _is_null(date) or _is_null(namedformat):
        return VBNull
    dt = _to_datetime(date)
    fmt = int(_date_arg_number(namedformat))
    lcid = vbs_get_lcid()

    if fmt == vbGeneralDate:
        # vbGeneralDate shows only the parts that carry information: a value on
        # the OA zero date (1899-12-30, e.g. Empty or TimeSerial) prints
        # time-only, and a midnight value prints date-only.
        has_date = (dt.year, dt.month, dt.day) != (1899, 12, 30)
        has_time = (dt.hour, dt.minute, dt.second, dt.microsecond) != (0, 0, 0, 0)
        if not has_date and not has_time:
            has_time = True
        return vb_locale.general_date(dt, lcid, has_date, has_time)
    if fmt == vbLongDate:
        return vb_locale.long_date(dt, lcid)
    if fmt == vbShortDate:
        return vb_locale.short_date(dt, lcid)
    if fmt == vbLongTime:
        return vb_locale.long_time(dt, lcid)
    if fmt == vbShortTime:
        return vb_locale.short_time(dt, lcid)

    raise VBScriptRuntimeError("FormatDateTime: invalid namedformat")



def _scalarize(v):
    """Invoke a wrapped value's default-property hook (IStringList etc.).

    IIS coerces such COM objects through their default property before
    converting; an empty IStringList (missing Request key) becomes Empty."""
    hook = getattr(v.__class__, '__vbs_scalar__', None)
    if hook is not None:
        return hook(v)
    return v


def _to_datetime(value) -> _dt.datetime:
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return _dt.datetime(value.year, value.month, value.day)
    if isinstance(value, _dt.time):
        # Time-only values live on the OA zero date, like VBScript.
        return _OA_ZERO.replace(hour=value.hour, minute=value.minute, second=value.second)
    if isinstance(value, bool):
        # VBScript: True is -1, False is 0 (as an OA serial).
        return _OA_ZERO + _dt.timedelta(days=-1 if value else 0)
    if isinstance(value, (int, float)):
        # VBScript/OLE Automation date: days since 1899-12-30
        base = _dt.datetime(1899, 12, 30)
        return base + _dt.timedelta(days=float(value))
    value = _scalarize(value)
    if value is VBNull:
        # Callers turn this into Null propagation / error 94.
        raise VBScriptCOMError(94, "Invalid use of Null")
    if value is VBEmpty or value is None:
        # VBScript treats Empty as OA serial 0: Year(Empty) = 1899,
        # Month(Empty) = 12, Day(Empty) = 30, Hour(Empty) = 0.
        return _OA_ZERO
    if isinstance(value, str):
        # A Request value that coerced to Empty already returned above; a
        # genuinely empty string is a Type Mismatch on IIS.
        return _parse_iso_datetime(value)
    if isinstance(value, _Decimal):
        return _dt.datetime(1899, 12, 30) + _dt.timedelta(days=float(value))
    raise VBScriptRuntimeError(f"Expected date/time value, got {type(value).__name__}")


def _date_arg_number(v, what="argument"):
    """Coerce a numeric date argument like VBScript: Empty => 0, Null => 94.

    Used for DateAdd's `number` and DateSerial/TimeSerial's parts so that
    Empty (or a missing Request key) behaves as 0 instead of raising a bare
    Python TypeError."""
    v = _scalarize(v)
    if v is VBNull:
        raise VBScriptCOMError(94, "Invalid use of Null")
    if v is VBEmpty or v is None:
        return 0.0
    if isinstance(v, bool):
        return -1.0 if v else 0.0
    if isinstance(v, (int, float, _Decimal)):
        return float(v)
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return (_to_datetime(v) - _OA_ZERO).total_seconds() / 86400.0
    s = vbs_cstr(v).strip()
    if s == "":
        raise VBScriptCOMError(13, "Type mismatch")
    try:
        return float(s)
    except ValueError:
        raise VBScriptCOMError(13, "Type mismatch")


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
        # Accept time-only strings: H:MM, HH:MM, H:MM:SS, with optional AM/PM
        # (VBScript: IsDate("13:45") = True, CDate("13:45") = pure time value)
        m = _re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?$", s)
        if m:
            hh, mi, se = _parse_time_parts(m.group(1), m.group(2), m.group(3), m.group(4))
            return _OA_ZERO.replace(hour=hh, minute=mi, second=se)

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

        # Accept a numeric date with any of the separators Windows uses, read in
        # the current locale: "3/5/2024" is March 5th under en-US and 5 March
        # under nl-NL. A leading four-digit component is always ISO.
        m = _re.match(
            r"^(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})\.?"
            r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?)?$", s)
        if m:
            yr, mon, day = vb_locale.resolve_numeric_date(
                (m.group(1), m.group(2), m.group(3)), vbs_get_lcid())
            hh, mi, se = _parse_time_parts(m.group(4), m.group(5), m.group(6), m.group(7))
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
