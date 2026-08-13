"""Locale-aware formatting for VBScript built-ins.

Data source
-----------
``locale_data.json`` is generated from the Windows NLS tables - the same tables
the VBScript scripting engine reads - and was validated field-by-field against
live IIS output for all 60 supported locales.

Everything here is data-driven: there are no per-language branches in the code.
Adding or correcting a locale means editing one self-contained JSON record, not
editing Python.

Known gap (deliberate, documented): ar-SA/ar-DZ (Hijri) and th-TH (Buddhist
era) render dates on the Gregorian calendar, so their year/era differs from
IIS. All other supported locales match IIS exactly.
"""

from __future__ import annotations

import json as _json
import os as _os
import re as _re
import threading as _threading
import unicodedata as _unicodedata
from decimal import Decimal as _Decimal, ROUND_HALF_UP as _HALF_UP

#: LCID used when none is set. IIS would inherit the host's system locale;
#: ASPPY is deterministic across hosts instead, consistent with its
#: UTF-8-by-default stance (see README "Character encoding").
DEFAULT_LCID = 1033

_DATA = None
_LOCK = _threading.Lock()
_NAME_TO_LCID = None


# --------------------------------------------------------------------- data

def _load():
    global _DATA
    if _DATA is None:
        with _LOCK:
            if _DATA is None:
                path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     'locale_data.json')
                with open(path, 'r', encoding='utf-8') as f:
                    _DATA = _json.load(f)
    return _DATA


def get(lcid=None):
    """Return the locale record for an LCID.

    LCID 0 (and the neutral 1024/2048) resolves to :data:`DEFAULT_LCID`. An
    unknown LCID also falls back to the default rather than raising, so that
    formatting never breaks a page.
    """
    try:
        lcid = int(lcid) if lcid else 0
    except Exception:
        lcid = 0
    if lcid in (0, 1024, 2048):
        lcid = DEFAULT_LCID
    data = _load()
    rec = data.get(str(lcid))
    if rec is None:
        rec = data.get(str(DEFAULT_LCID))
        if rec is None:
            raise KeyError('locale_data.json is missing the default locale')
    return rec


def is_supported(lcid):
    try:
        return str(int(lcid)) in _load()
    except Exception:
        return False


def supported_lcids():
    return sorted(int(k) for k in _load())


def lcid_for_name(name):
    """Map a VBScript short locale string ("en-gb", "nl", "de-DE") to an LCID.

    VBScript's SetLocale accepts either a numeric LCID or a short name; the
    bare-language form resolves to that language's lowest-numbered LCID, which
    matches Windows' notion of the default sub-language.
    """
    global _NAME_TO_LCID
    if _NAME_TO_LCID is None:
        m = {}
        for lcid, rec in sorted(_load().items(), key=lambda kv: int(kv[0])):
            culture = (rec.get('culture') or '').lower()
            if culture:
                m[culture] = int(lcid)
                m.setdefault(culture.split('-')[0], int(lcid))
        _NAME_TO_LCID = m
    return _NAME_TO_LCID.get(str(name).strip().lower().replace('_', '-'))


# ------------------------------------------------------------------ numbers

def _to_decimal(x):
    if isinstance(x, _Decimal):
        return x
    if isinstance(x, int):
        return _Decimal(x)
    return _Decimal(repr(float(x)))


def round15(x):
    """Collapse a value to 15 significant decimal digits.

    VBScript pushes numbers through 15 significant digits before formatting,
    which is why IIS renders ``FormatNumber(1234567890123.456, 3)`` as
    ``1,234,567,890,123.460`` rather than ``...123.456``.
    """
    d = _to_decimal(x)
    if d == 0:
        return _Decimal(0)
    keep = 15 - (d.adjusted() + 1)
    if keep >= 0:
        return d.quantize(_Decimal(1).scaleb(-keep), rounding=_HALF_UP)
    return d.scaleb(keep).quantize(_Decimal(1), rounding=_HALF_UP).scaleb(-keep)


def _group(s, size, sep):
    """Group the integer part with a single uniform group size.

    The scripting engine never applies the Indic lakh/crore grouping that NLS
    reports for hi-IN, so a uniform size is correct here: IIS renders
    ``1,234,567.89``, not ``12,34,567.89``.
    """
    if not sep or not size or size < 1 or len(s) <= size:
        return s
    out = []
    i = len(s)
    while i > size:
        out.append(s[i - size:i])
        i -= size
    out.append(s[:i])
    return sep.join(reversed(out))


_NEG_NUMBER = ('(%s)', '-%s', '- %s', '%s-', '%s -')

_CURRENCY_POSITIVE = ('%(s)s%(n)s', '%(n)s%(s)s', '%(s)s %(n)s', '%(n)s %(s)s')

_CURRENCY_NEGATIVE = (
    '(%(s)s%(n)s)', '-%(s)s%(n)s', '%(s)s-%(n)s', '%(s)s%(n)s-',
    '(%(n)s%(s)s)', '-%(n)s%(s)s', '%(n)s-%(s)s', '%(n)s%(s)s-',
    '-%(n)s %(s)s', '-%(s)s %(n)s', '%(n)s %(s)s-', '%(s)s %(n)s-',
    '%(s)s -%(n)s', '%(n)s- %(s)s', '(%(s)s %(n)s)', '(%(n)s %(s)s)',
)


def _parenthesise(pattern, subst):
    """Build the ``useparens`` form from a locale's negative pattern.

    VBScript does not parenthesise the *positive* pattern; it takes the negative
    pattern, drops the sign and wraps the result. That preserves locale-specific
    spacing around the symbol - de-CH ``(CHF1'234.50)`` keeps no space while
    nl-BE ``(EUR 1.234,50)`` keeps one.
    """
    s = pattern.replace('-', '') % subst
    if s.startswith('(') and s.endswith(')'):
        return s
    return '(%s)' % s


def _tri(value, default):
    """Resolve a VBScript tristate argument: -1 True, 0 False, -2/None default."""
    if value is None or value == -2:
        return default
    return bool(value)


def _core(value, digits, lead, group, dec_sep, grp_sep, grp_size):
    d = round15(value)
    scale = _Decimal(1).scaleb(-digits) if digits > 0 else _Decimal(1)
    d = d.quantize(scale, rounding=_HALF_UP)
    negative = d < 0
    text = format(abs(d), 'f')
    int_part, _, frac_part = text.partition('.')
    frac_part = (frac_part + '0' * digits)[:digits] if digits > 0 else ''
    if group:
        int_part = _group(int_part, grp_size, grp_sep)
    if not lead and int_part == '0' and digits > 0:
        int_part = ''
    return negative, int_part + (dec_sep + frac_part if digits > 0 else '')


def format_number(value, digits=-1, lead=-2, parens=-2, group=-2, lcid=None):
    L = get(lcid)
    if digits is None or digits == -1:
        digits = L['numberDecimalDigits']
    negative, body = _core(
        value, int(digits), _tri(lead, True), _tri(group, True),
        L['numberDecimalSeparator'], L['numberGroupSeparator'],
        L['numberGroupSize'])
    if not negative:
        return body
    pattern = _NEG_NUMBER[L['numberNegativePattern']]
    if _tri(parens, False):
        return _parenthesise(pattern, body)
    return pattern % body


def format_currency(value, digits=-1, lead=-2, parens=-2, group=-2, lcid=None):
    L = get(lcid)
    if digits is None or digits == -1:
        digits = L['currencyDecimalDigits']
    negative, body = _core(
        value, int(digits), _tri(lead, True), _tri(group, True),
        L['currencyDecimalSeparator'], L['currencyGroupSeparator'],
        L['currencyGroupSize'])
    subst = {'s': L['currencySymbol'], 'n': body}
    if not negative:
        return _CURRENCY_POSITIVE[L['currencyPositivePattern']] % subst
    pattern = _CURRENCY_NEGATIVE[L['currencyNegativePattern']]
    if _tri(parens, False):
        return _parenthesise(pattern, subst)
    return pattern % subst


def format_percent(value, digits=-1, lead=-2, parens=-2, group=-2, lcid=None):
    L = get(lcid)
    if digits is None or digits == -1:
        digits = L['percentDecimalDigits']
    negative, body = _core(
        round15(value) * 100, int(digits), _tri(lead, True), _tri(group, True),
        L['percentDecimalSeparator'], L['percentGroupSeparator'],
        L['percentGroupSize'])
    symbol = L['percentSymbol']
    # The engine appends the percent sign directly and ignores the NLS
    # positive/negative percent patterns: IIS gives "12,34%", never "12,34 %".
    if not negative:
        return body + symbol
    if _tri(parens, False):
        return '(%s%s)' % (body, symbol)
    return '-' + body + symbol


_PLAIN_NUMBER = _re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')

#: Separators that NLS reports as non-breaking but that arrive as a plain space
#: from HTML forms and hand-typed input.
_SPACEY = ('\xa0', '\u202f', '\u2009', ' ')


def normalize_number_string(text, lcid=None):
    """Turn a locale-formatted numeric string into a plain Python literal.

    Returns ``None`` when the string is not a valid number in this locale, which
    callers surface as VBScript Type mismatch (13).

    The rule, derived from IIS across all 60 locales: strip the group separator
    wherever it occurs, accept the locale decimal separator, and reject any
    other separator. So en-US reads "1.234,56" as 1.23456 (the comma is a group
    separator and simply disappears) while fr-FR rejects "1.5" outright, because
    '.' is neither its decimal nor its group separator.

    Known deviation: fr-CH (4108) additionally accepts '.' as a decimal
    separator on IIS. That is a one-off in the Windows tables and is not
    modelled here.
    """
    L = get(lcid)
    t = str(text).strip()
    if not t:
        return None
    group = L['numberGroupSeparator']
    decimal = L['numberDecimalSeparator']
    if group:
        t = t.replace(group, '')
        if group in _SPACEY:
            for ch in _SPACEY:
                t = t.replace(ch, '')
    # A few locales accept a separator their own NLS table does not advertise
    # (de-AT formats groups with a non-breaking space but still parses '.').
    alt_group = L.get('alternateGroupSeparator')
    if alt_group:
        t = t.replace(alt_group, '')
    # fr-CH takes '.' as a decimal separator alongside ',', but only when the
    # primary separator is absent - "1.234,56" stays ambiguous and is rejected.
    alt_decimal = L.get('alternateDecimalSeparator')
    if alt_decimal and alt_decimal in t and decimal not in t:
        decimal = alt_decimal
    # Once group separators are gone, the only separator that may remain is the
    # locale's own decimal separator.
    for ch in ('.', ','):
        if ch != decimal and ch in t:
            return None
    if decimal != '.':
        t = t.replace(decimal, '.')
    if not _PLAIN_NUMBER.match(t):
        return None
    return t


def decimal_separator(lcid=None):
    return get(lcid)['numberDecimalSeparator']


def group_separator(lcid=None):
    return get(lcid)['numberGroupSeparator']


# -------------------------------------------------------------------- dates

#: Right-to-left mark, injected into date fields for RTL locales.
RLM = '\u200f'

_DAY_TOKEN = _re.compile(r"(?<!d)d{1,2}(?!d)")


def _uses_genitive(pattern):
    """Whether a pattern should use genitive month names.

    Windows switches to the genitive form when a long month name appears in a
    pattern that also carries a numeric day-of-month: Polish ``5 marca 2024``
    rather than nominative ``5 marzec 2024``. Affects Slavic, Baltic and
    Finnic locales.
    """
    stripped = _re.sub(r"'[^']*'", '', pattern)
    return ('MMM' in stripped) and bool(_DAY_TOKEN.search(stripped))


def _time_pattern(pattern):
    """Normalise the narrow no-break space some locales carry before the AM/PM
    designator (ms-MY ``h:mm:ss\u202ftt``); the engine emits a plain space.

    Deliberately applied to *time* patterns only - kk-KZ's long *date* pattern
    keeps its narrow space on IIS.
    """
    return pattern.replace('\u202f', ' ')


def render(dt, pattern, lcid=None, rtl_marks=False):
    """Render a datetime through a Windows date/time pattern."""
    L = get(lcid)
    genitive = _uses_genitive(pattern)
    mark = RLM if (rtl_marks and L.get('rightToLeft')) else ''
    out = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c in ("'", '"'):
            j = pattern.find(c, i + 1)
            if j < 0:
                j = n
            out.append(pattern[i + 1:j])
            i = j + 1
            continue
        if c == '\\' and i + 1 < n:
            out.append(pattern[i + 1])
            i += 2
            continue
        j = i
        while j < n and pattern[j] == c:
            j += 1
        run = j - i
        weekday = (dt.weekday() + 1) % 7        # Python Mon=0 -> NLS Sun=0
        if c == 'd':
            if run == 1:
                out.append(mark + str(dt.day))
            elif run == 2:
                out.append(mark + '%02d' % dt.day)
            elif run == 3:
                out.append(mark + L['dayNamesAbbrev'][weekday])
            else:
                out.append(mark + L['dayNames'][weekday])
        elif c == 'M':
            if run == 1:
                out.append(mark + str(dt.month))
            elif run == 2:
                out.append(mark + '%02d' % dt.month)
            elif run == 3:
                names = L['monthNamesGenitiveAbbrev'] if genitive else L['monthNamesAbbrev']
                out.append(mark + names[dt.month - 1])
            else:
                names = L['monthNamesGenitive'] if genitive else L['monthNames']
                out.append(mark + names[dt.month - 1])
        elif c == 'y':
            if run <= 2:
                out.append(mark + '%02d' % (dt.year % 100))
            else:
                out.append(mark + '%0*d' % (run, dt.year))
        elif c == 'h':
            hour12 = dt.hour % 12 or 12
            out.append(str(hour12) if run == 1 else '%02d' % hour12)
        elif c == 'H':
            out.append(str(dt.hour) if run == 1 else '%02d' % dt.hour)
        elif c == 'm':
            out.append(str(dt.minute) if run == 1 else '%02d' % dt.minute)
        elif c == 's':
            out.append(str(dt.second) if run == 1 else '%02d' % dt.second)
        elif c == 't':
            designator = L['amDesignator'] if dt.hour < 12 else L['pmDesignator']
            out.append(designator[:1] if run == 1 else designator)
        elif c == 'g':
            pass                                 # era - not modelled
        else:
            out.append(c * run)
        i = j
    return ''.join(out)


def long_date(dt, lcid=None):
    # vbLongDate/vbShortDate go through the Win32 date-format API, which injects
    # RTL marks for right-to-left locales. vbGeneralDate and CStr() use the
    # variant-to-string path and do not - verified against IIS for he-IL.
    return render(dt, get(lcid)['longDatePattern'], lcid, rtl_marks=True)


def short_date(dt, lcid=None):
    return render(dt, get(lcid)['shortDatePattern'], lcid, rtl_marks=True)


def long_time(dt, lcid=None):
    return render(dt, _time_pattern(get(lcid)['longTimePattern']), lcid)


def short_time(dt, lcid=None):
    """vbShortTime is always 24-hour ``HH:mm``, but uses the locale time
    separator - fi-FI and id-ID give ``14.07``, every other locale ``14:07``.
    """
    L = get(lcid)
    return render(dt, 'HH' + (L['timeSeparator'] or ':') + 'mm', lcid)


def general_date(dt, lcid=None, has_date=True, has_time=True):
    parts = []
    if has_date:
        parts.append(render(dt, get(lcid)['shortDatePattern'], lcid))
    if has_time:
        parts.append(long_time(dt, lcid))
    return ' '.join(parts)


def date_field_order(lcid=None):
    """Order of the year/month/day fields in the locale short date pattern.

    Returns a list such as ``['M', 'd', 'y']`` (en-US) or ``['d', 'M', 'y']``
    (nl-NL). Quoted literals are ignored so that patterns like kk-KZ's
    ``yyyy'zh'. d MMMM`` are read correctly.
    """
    pattern = _re.sub(r"'[^']*'", '', get(lcid)['shortDatePattern'])
    order = []
    for ch in pattern:
        if ch in ('y', 'M', 'd') and ch not in order:
            order.append(ch)
    for ch in ('y', 'M', 'd'):
        if ch not in order:
            order.append(ch)
    return order


def _normalise_year(year):
    """VBScript two-digit year window: 00-29 -> 2000s, 30-99 -> 1900s."""
    if year < 100:
        return year + (2000 if year < 30 else 1900)
    return year


def resolve_numeric_date(parts, lcid=None):
    """Map three numeric date components onto (year, month, day).

    Mirrors what Windows does for CDate/IsDate:

    * A leading four-digit component is an unambiguous ISO date and is read as
      year-month-day regardless of locale.
    * Otherwise a trailing four-digit component is the year and the two leading
      components follow the locale's own month/day order - so "3/5/2024" is
      5 March in nl-NL but March 5th in en-US.
    * If the resulting month is out of range while the day is not, the two are
      swapped. That is why IsDate("31/12/2024") is True on IIS in *every*
      locale, including month-first ones.
    """
    raw = [str(p) for p in parts]
    nums = [int(p) for p in raw]
    order = date_field_order(lcid)

    if len(raw[0]) == 4:
        year, month, day = nums[0], nums[1], nums[2]
    elif len(raw[2]) == 4:
        year = nums[2]
        month_first = [f for f in order if f in ('M', 'd')][0] == 'M'
        month, day = (nums[0], nums[1]) if month_first else (nums[1], nums[0])
    else:
        position = {field: i for i, field in enumerate(order)}
        year, month, day = nums[position['y']], nums[position['M']], nums[position['d']]

    if month > 12 and day <= 12:
        month, day = day, month
    return _normalise_year(year), month, day


# --------------------------------------------------------------- collation

def text_sort_key(text):
    """Sort key approximating Windows collation for vbTextCompare.

    Windows compares in levels: base letters first, then accents, then case.
    Case folding also expands the German sharp s, so "strasse" and "stra\u00dfe"
    compare equal, while "\u00e9" sorts after "e" because they share a base
    letter and differ only at the accent level. Both behaviours were confirmed
    identical across all 60 locales on IIS, so no per-locale tailoring is
    applied here.
    """
    folded = str(text).casefold()
    primary = ''.join(c for c in _unicodedata.normalize('NFD', folded)
                      if not _unicodedata.combining(c))
    return (primary, folded)


def compare_text(a, b):
    """vbTextCompare ordering: -1, 0 or 1."""
    ka, kb = text_sort_key(a), text_sort_key(b)
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0


def month_name(month, abbrev=False, lcid=None):
    L = get(lcid)
    return (L['monthNamesAbbrev'] if abbrev else L['monthNames'])[int(month) - 1]


def first_day_of_week(lcid=None):
    """Locale first day of week as a VBScript constant (1=Sunday .. 7=Saturday)."""
    return int(get(lcid)['firstDayOfWeek']) + 1


def weekday_name(weekday, abbrev=False, firstdayofweek=1, lcid=None):
    L = get(lcid)
    first = int(firstdayofweek or 0)
    if first == 0:                               # vbUseSystemDayOfWeek
        first = first_day_of_week(lcid)
    index = (first - 1 + (int(weekday) - 1)) % 7
    return (L['dayNamesAbbrev'] if abbrev else L['dayNames'])[index]
