<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 11-dates-time.asp - Dates, time and the many edge cases around them
' ----------------------------------------------------------------------------
' Demonstrates: how VBScript stores dates internally (as Doubles), building
' dates with DateSerial/TimeSerial, breaking them apart with DatePart, doing
' calendar math with DateAdd/DateDiff, and - crucially - the LOCALE traps that
' bite agents: CDate parses according to the server's regional settings, and
' the same date renders differently per locale.
'
' EDGE CASES highlighted on this page:
'   * A Date is really a Double: 1.0 == one day, the integer part is the day
'     count since 1899-12-30 and the fraction is the time of day.
'   * Date literals use #...# and are ALWAYS US-format (#m/d/yyyy#), regardless
'     of server locale - unlike CDate("...") which is locale-sensitive.
'   * DateDiff("d", ...) counts BOUNDARY crossings, not 24h chunks.
'   * Adding a month to Jan-31 clamps to the last valid day (Feb-28/29).
'   * Leap-year rule, weekend detection, and IsDate guarding.
' ============================================================================
Dim PageTitle : PageTitle = "Dates & Time"
%>
<!--#include file="includes/header.asp"-->
<%
' --- A leap-year test written from scratch (don't trust folklore) ----------
' Rule: divisible by 4, EXCEPT centuries, UNLESS divisible by 400.
Function IsLeapYear(ByVal y)
    IsLeapYear = (y Mod 4 = 0 And y Mod 100 <> 0) Or (y Mod 400 = 0)
End Function

' --- Count weekdays (Mon-Fri) between two dates, inclusive of the start -----
' Shows DateDiff for the loop bound and Weekday() for the test. vbMonday..vbFriday
' are the integer day-of-week constants (Sunday = 1 by default).
Function BusinessDaysBetween(ByVal d1, ByVal d2)
    Dim n, i, cur, dow
    n = 0
    For i = 0 To DateDiff("d", d1, d2)        ' DateDiff("d") = whole days apart
        cur = DateAdd("d", i, d1)             ' walk one day at a time
        dow = Weekday(cur, vbMonday)          ' force Monday=1 .. Sunday=7
        If dow >= 1 And dow <= 5 Then n = n + 1
    Next
    BusinessDaysBetween = n
End Function

' --- Human-friendly "x ago" relative time ----------------------------------
' Picks the largest sensible unit. Demonstrates Select Case on computed sizes.
Function RelativeTime(ByVal past, ByVal nowRef)
    Dim secs : secs = DateDiff("s", past, nowRef)
    Select Case True
        Case secs < 60      : RelativeTime = secs & " seconds ago"
        Case secs < 3600    : RelativeTime = (secs \ 60) & " minutes ago"
        Case secs < 86400   : RelativeTime = (secs \ 3600) & " hours ago"
        Case Else           : RelativeTime = (secs \ 86400) & " days ago"
    End Select
End Function
%>
<h1>Dates &amp; Time</h1>
<p class="lead">
  VBScript dates are deceptively simple and full of edge cases. This page shows
  the math, the locale traps, and a few small algorithms built on the date API.
</p>

<h2>A Date is secretly a Double</h2>
<p>
  Internally a <code>Date</code> is a floating-point number: the whole part is the
  number of days since <strong>30&nbsp;Dec&nbsp;1899</strong> and the fractional part
  is the fraction of the day. <code>CDbl()</code> reveals it; <code>CDate()</code>
  converts it back. That is why you can do arithmetic on dates directly.
</p>
<%
DemoStart "Same instant, two representations"
Dim anInstant : anInstant = CDate("2026-06-05 18:00:00")   ' locale-parsed text
WriteLine "<table class=""kv"">"
RenderTableRow "anInstant (as Date)",      anInstant
'RenderTableRow "CDbl(anInstant)",          CDbl(anInstant)
'RenderTableRow "Int part = whole days",    Int(CDbl(anInstant))
'RenderTableRow "Frac part = time of day",  CDbl(anInstant) - Int(CDbl(anInstant)) & "  (0.75 = 18:00)"
RenderTableRow "anInstant + 1 (tomorrow)", anInstant + 1
RenderTableRow "anInstant + 0.5 (+12h)",   anInstant + 0.5
WriteLine "</table>"
DemoEnd
%>

<h2>Building dates safely: DateSerial / TimeSerial</h2>
<p>
  Never string-concatenate a date and hope <code>CDate</code> parses it the way
  you meant. <code>DateSerial(y, m, d)</code> builds a date from numbers and even
  <em>normalises overflow</em>: month 13 rolls into the next year, day 0 is the
  last day of the previous month.
</p>
<%
DemoStart "DateSerial normalises out-of-range parts"
WriteLine "<table class=""kv"">"
RenderTableRow "DateSerial(2026, 6, 5)",   DateSerial(2026, 6, 5)
RenderTableRow "DateSerial(2026, 13, 1)",  DateSerial(2026, 13, 1) & "  (month 13 -> Jan 2027)"
RenderTableRow "DateSerial(2026, 3, 0)",   DateSerial(2026, 3, 0)  & "  (day 0 -> last day of Feb)"
RenderTableRow "DateSerial(2026, 1, -1)",  DateSerial(2026, 1, -1) & "  (negative day rolls back)"
RenderTableRow "TimeSerial(25, 0, 0)",     TimeSerial(25, 0, 0)    & "  (hour 25 -> 01:00 next day)"
WriteLine "</table>"
DemoEnd
%>

<h2>Pulling dates apart: DatePart</h2>
<%
DemoStart "Every component of a single instant"
Dim p : p = Now()
WriteLine "<table class=""kv"">"
RenderTableRow "Now()",                    p
RenderTableRow "Year / Month / Day",       Year(p) & " / " & Month(p) & " / " & Day(p)
RenderTableRow "Hour / Minute / Second",   Hour(p) & " / " & Minute(p) & " / " & Second(p)
RenderTableRow "MonthName(Month(p))",      MonthName(Month(p))
RenderTableRow "WeekdayName(Weekday(p))",  WeekdayName(Weekday(p))
RenderTableRow "DatePart(""q"", p) quarter", DatePart("q", p)
RenderTableRow "DatePart(""y"", p) day-of-year", DatePart("y", p)
RenderTableRow "DatePart(""ww"", p) week#", DatePart("ww", p)
WriteLine "</table>"
DemoEnd
%>

<h2>Calendar math: DateAdd and the month-clamp trap</h2>
<p>
  Adding one month to <strong>31 Jan</strong> cannot produce "31 Feb", so VBScript
  clamps to the last valid day. This surprises agents that assume add-a-month is
  reversible. It is <em>not</em>.
</p>
<%
DemoStart "DateAdd edge cases"
Dim jan31 : jan31 = DateSerial(2026, 1, 31)
WriteLine "<table class=""kv"">"
RenderTableRow "jan31",                          jan31
RenderTableRow "DateAdd(""m"", 1, jan31)",       DateAdd("m", 1, jan31) & "  (clamped to Feb 28)"
RenderTableRow "DateAdd(""m"", 1, that) again",  DateAdd("m", 1, DateAdd("m", 1, jan31)) & "  (NOT back to the 31st)"
RenderTableRow "DateAdd(""yyyy"", 2, jan31)",    DateAdd("yyyy", 2, jan31)
RenderTableRow "DateAdd(""d"", -1, jan31)",      DateAdd("d", -1, jan31)
RenderTableRow "DateAdd(""h"", 36, jan31)",      DateAdd("h", 36, jan31)
WriteLine "</table>"
DemoEnd
%>

<h2>DateDiff counts boundaries, not durations</h2>
<p>
  <code>DateDiff("d", a, b)</code> counts how many midnight boundaries you cross,
  NOT how many 24-hour periods elapsed. 23:59 to 00:01 the next minute is
  <strong>1 day</strong> apart even though only two minutes passed.
</p>
<%
DemoStart "The boundary-crossing gotcha"
Dim lateTonight, earlyTomorrow
lateTonight   = CDate("2026-06-05 23:59:00")
earlyTomorrow = CDate("2026-06-06 00:01:00")
WriteLine "<table class=""kv"">"
RenderTableRow "From",                         lateTonight
RenderTableRow "To",                           earlyTomorrow
RenderTableRow "DateDiff(""n"", ...) minutes", DateDiff("n", lateTonight, earlyTomorrow)
RenderTableRow "DateDiff(""d"", ...) days",    DateDiff("d", lateTonight, earlyTomorrow) & "  (1, despite 2 minutes!)"
RenderTableRow "DateDiff(""s"", ...) seconds", DateDiff("s", lateTonight, earlyTomorrow)
WriteLine "</table>"
DemoEnd
%>

<h2>Literals vs CDate: the locale trap</h2>
<p>
  A <code>#...#</code> date literal is compiled and is <strong>always US m/d/y</strong>.
  <code>CDate("...")</code> on a string parses using the <em>server's</em> regional
  settings. On a UK/EU server <code>CDate("03/04/2026")</code> means 3&nbsp;April,
  while <code>#03/04/2026#</code> means 4&nbsp;March. Always prefer
  <code>DateSerial</code> for unambiguous, locale-proof dates.
</p>
<%
DemoStart "Same text, different meaning"
On Error Resume Next            ' CDate can raise on an unparseable string
WriteLine "<table class=""kv"">"
RenderTableRow "Literal #3/4/2026# (US, always)", #3/4/2026#
RenderTableRow "CDate(""3/4/2026"") (locale)",    CDate("3/4/2026")
RenderTableRow "DateSerial(2026,3,4) explicit",   DateSerial(2026, 3, 4)
If Err.Number <> 0 Then RenderTableRow "Note", "CDate raised: " & Err.Description
Err.Clear
On Error Goto 0
WriteLine "</table>"
DemoEnd
%>

<h2>Algorithms built on the date API</h2>
<%
DemoStart "Leap years, business days and relative time"
WriteLine "<table class=""kv"">"
RenderTableRow "IsLeapYear(2000)",  IsLeapYear(2000) & "  (divisible by 400 -> leap)"
RenderTableRow "IsLeapYear(1900)",  IsLeapYear(1900) & "  (century, not /400 -> NOT leap)"
RenderTableRow "IsLeapYear(2024)",  IsLeapYear(2024)
RenderTableRow "Business days 1 Jun..30 Jun 2026", _
               BusinessDaysBetween(DateSerial(2026,6,1), DateSerial(2026,6,30))
RenderTableRow "RelativeTime(2 hours ago)", _
               RelativeTime(DateAdd("h", -2, Now()), Now())
RenderTableRow "RelativeTime(3 days ago)", _
               RelativeTime(DateAdd("d", -3, Now()), Now())
WriteLine "</table>"
DemoEnd
%>

<h2>Guarding input with IsDate</h2>
<p>
  Always validate before converting. <code>IsDate</code> tells you whether
  <code>CDate</code> would succeed, so you can fail gracefully instead of crashing.
</p>
<%
DemoStart "IsDate gate"
Dim candidates, c
candidates = Array("2026-06-05", "31/31/2026", "tomorrow", "12:30", "")
WriteLine "<table class=""kv"">"
For Each c In candidates
    If IsDate(c) Then
        RenderTableRow "IsDate(""" & c & """)", "True -> CDate = " & CDate(c)
    Else
        RenderTableRow "IsDate(""" & c & """)", "False -> rejected"
    End If
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "' A Date IS a Double: 1.0 = one day" & vbCrLf & _
    "Response.Write CDbl(Now())          ' e.g. 46178.75" & vbCrLf & vbCrLf & _
    "' Build dates from numbers - locale-proof:" & vbCrLf & _
    "d = DateSerial(2026, 6, 5)          ' never ambiguous" & vbCrLf & vbCrLf & _
    "' Add a month to Jan 31 -> Feb 28 (clamped, not reversible!)" & vbCrLf & _
    "DateAdd(""m"", 1, DateSerial(2026,1,31))" & vbCrLf & vbCrLf & _
    "' DateDiff counts boundary crossings, not elapsed time:" & vbCrLf & _
    "DateDiff(""d"", #6/5/2026 23:59#, #6/6/2026 00:01#)   ' = 1" & vbCrLf & vbCrLf & _
    "' Always validate before converting:" & vbCrLf & _
    "If IsDate(s) Then d = CDate(s)"
%>
<!--#include file="includes/footer.asp"-->
