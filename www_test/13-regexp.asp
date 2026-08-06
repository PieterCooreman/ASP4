<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 13-regexp.asp - Regular expressions with the VBScript.RegExp object
' ----------------------------------------------------------------------------
' VBScript has no regex operator; instead you create a COM object:
'     Set re = New RegExp        (or Server.CreateObject("VBScript.RegExp"))
' and set three properties before using it:
'     .Pattern    - the regex itself (note: VBScript regex is its own dialect)
'     .IgnoreCase - True/False
'     .Global     - True = all matches; False = only the first
' then call .Test(), .Execute() or .Replace().
'
' EDGE CASES & dialect notes for agents:
'   * The VBScript regex engine is NOT PCRE: no lookbehind, no named groups,
'     no \d{2,} possessive quantifiers, \b works, but Unicode classes differ.
'   * .Execute returns a MatchCollection of Match objects; each Match has
'     .Value, .FirstIndex (0-based!), .Length and a SubMatches collection
'     (the capture groups, also 0-based).
'   * .Replace supports $1..$9 backreferences in the replacement string.
'   * Backslashes in patterns are fine in VBScript strings (no C-style escaping),
'     so "\d+" is written literally - a common point of confusion for agents
'     coming from languages where you'd write "\\d+".
'   * .Global = False is the default and silently returns just the first match -
'     a frequent source of "why did only one replace happen?" bugs.
' ============================================================================
Dim PageTitle : PageTitle = "Regular Expressions"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Factory: build a configured RegExp in one call ------------------------
' Keeps the demos terse and shows the property-setting pattern in one place.
Function NewRegex(ByVal pattern, ByVal ignoreCase, ByVal global)
    Dim re : Set re = New RegExp
    re.Pattern    = pattern
    re.IgnoreCase = ignoreCase
    re.Global     = global
    Set NewRegex  = re
End Function

' --- A reusable validator returning a friendly Yes/No ----------------------
Function MatchesYesNo(ByVal pattern, ByVal text)
    Dim re : Set re = NewRegex(pattern, True, False)
    If re.Test(text) Then MatchesYesNo = "matches" Else MatchesYesNo = "no match"
End Function
%>
<h1>Regular Expressions</h1>
<p class="lead">
  Regex in Classic ASP means the <code>VBScript.RegExp</code> COM object. Set
  <code>.Pattern</code>, <code>.IgnoreCase</code> and <code>.Global</code>, then
  call <code>.Test</code>, <code>.Execute</code> or <code>.Replace</code>.
</p>

<h2>.Test &mdash; does it match?</h2>
<p>
  <code>.Test</code> returns a Boolean. Note that backslash escapes like
  <code>\d</code>, <code>\w</code> and <code>\s</code> are written directly in the
  VBScript string - <strong>no double-backslashes</strong>, unlike C# or Java.
</p>
<%
DemoStart "Validating common formats"
WriteLine "<table class=""kv"">"
RenderTableRow "Email a@b.co  vs ^\w+@\w+\.\w+$", MatchesYesNo("^\w+@\w+\.\w+$", "a@b.co")
RenderTableRow "Email bad@    vs same pattern",   MatchesYesNo("^\w+@\w+\.\w+$", "bad@")
RenderTableRow "UK postcode SW1A 1AA",            MatchesYesNo("^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$", "SW1A 1AA")
RenderTableRow "Hex colour #1a2B3c",              MatchesYesNo("^#[0-9a-f]{6}$", "#1a2B3c")
RenderTableRow "Digits only ""12345""",           MatchesYesNo("^\d+$", "12345")
RenderTableRow "Digits only ""12a45""",           MatchesYesNo("^\d+$", "12a45")
WriteLine "</table>"
DemoEnd
%>

<h2>.Execute &mdash; capturing matches and groups</h2>
<p>
  <code>.Execute</code> returns a <strong>MatchCollection</strong>. Each
  <code>Match</code> exposes <code>.Value</code>, the <strong>0-based</strong>
  <code>.FirstIndex</code>, <code>.Length</code>, and a <code>.SubMatches</code>
  collection holding the parenthesised capture groups (also 0-based).
</p>
<%
DemoStart "Parsing dates out of free text"
Dim text : text = "Invoices: 2026-06-05, 2025-12-31 and 2024-02-29 are due."
Dim re   : Set re = NewRegex("(\d{4})-(\d{2})-(\d{2})", False, True)   ' Global = True
Dim matches : Set matches = re.Execute(text)
WriteLine "<p>Found <strong>" & matches.Count & "</strong> dates in the text.</p>"
WriteLine "<table class=""kv"">"
Dim m
For Each m In matches
    ' SubMatches(0)=year, (1)=month, (2)=day - the three capture groups.
    RenderTableRow "Match """ & m.Value & """ at index " & m.FirstIndex, _
        "year=" & m.SubMatches(0) & " month=" & m.SubMatches(1) & " day=" & m.SubMatches(2)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>.Replace &mdash; with $1 backreferences</h2>
<p>
  The replacement string can reference capture groups as <code>$1</code> &hellip;
  <code>$9</code>. Here we rewrite ISO dates (yyyy-mm-dd) into UK style
  (dd/mm/yyyy) by swapping the captured groups.
</p>
<%
DemoStart "Reformatting every date in one pass (Global = True)"
Dim src : src = "From 2026-06-05 to 2026-12-31."
Dim reFmt : Set reFmt = NewRegex("(\d{4})-(\d{2})-(\d{2})", False, True)
Dim out   : out = reFmt.Replace(src, "$3/$2/$1")     ' day/month/year
WriteLine "<table class=""kv"">"
RenderTableRow "Input",  src
RenderTableRow "Output", out
WriteLine "</table>"
DemoEnd
%>

<h2>The .Global trap</h2>
<p>
  <code>.Global</code> defaults to <strong>False</strong>, meaning
  <code>.Replace</code> only changes the <em>first</em> match. This is the single
  most common regex bug in Classic ASP. The two rows below use the identical
  pattern and input - only <code>.Global</code> differs.
</p>
<%
DemoStart "Same pattern, .Global False vs True"
Dim noisy : noisy = "a1b2c3d4"
Dim reOff : Set reOff = NewRegex("\d", False, False)   ' Global = False (default)
Dim reOn  : Set reOn  = NewRegex("\d", False, True)    ' Global = True
WriteLine "<table class=""kv"">"
RenderTableRow "Input",                    noisy
RenderTableRow ".Global=False, Replace #", reOff.Replace(noisy, "#") & "  (only first digit!)"
RenderTableRow ".Global=True,  Replace #", reOn.Replace(noisy, "#")  & "  (all digits)"
WriteLine "</table>"
DemoEnd
%>

<h2>A practical tokenizer</h2>
<p>
  Combining <code>.Execute</code> with a character-class pattern gives a quick
  word tokenizer that ignores punctuation - the kind of thing you'd otherwise
  build by hand with <code>Mid</code> and <code>InStr</code>.
</p>
<%
DemoStart "Extract words, ignoring punctuation"
Dim sentence : sentence = "Hello, ASP-world! It's 2026 already?"
Dim reWords  : Set reWords = NewRegex("[A-Za-z']+", True, True)
Dim wm, words, k
Set words = reWords.Execute(sentence)
WriteLine "<p>Tokens (" & words.Count & "): "
k = 0
For Each wm In words
    If k > 0 Then Response.Write ", "
    Response.Write "<strong>" & HtmlEncode(wm.Value) & "</strong>"
    k = k + 1
Next
WriteLine "</p>"
DemoEnd
%>

<h2>Dialect gotchas (read me)</h2>
<p>
  The VBScript engine is <strong>not PCRE</strong>. Patterns that work in
  Python/JS/PHP can silently fail or error here. Key differences:
</p>
<ul>
  <li><strong>No lookbehind</strong> <code>(?&lt;=...)</code> - unsupported.</li>
  <li><strong>No named groups</strong> <code>(?&lt;name&gt;...)</code> - use numbered SubMatches.</li>
  <li><strong>No inline flags</strong> like <code>(?i)</code> - set <code>.IgnoreCase</code> instead.</li>
  <li><strong>Lazy quantifiers</strong> <code>*?</code> <code>+?</code> <em>are</em> supported.</li>
  <li><strong>Single backslashes</strong> in the pattern string (VBScript strings don't escape <code>\</code>).</li>
</ul>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "Dim re : Set re = New RegExp" & vbCrLf & _
    "re.Pattern    = ""(\d{4})-(\d{2})-(\d{2})""   ' single backslashes!" & vbCrLf & _
    "re.IgnoreCase = True" & vbCrLf & _
    "re.Global     = True                          ' or only first match changes" & vbCrLf & vbCrLf & _
    "If re.Test(s) Then ...                         ' boolean" & vbCrLf & vbCrLf & _
    "For Each m In re.Execute(s)                    ' MatchCollection" & vbCrLf & _
    "    Response.Write m.Value                     ' the whole match" & vbCrLf & _
    "    Response.Write m.FirstIndex                ' 0-based position" & vbCrLf & _
    "    Response.Write m.SubMatches(0)             ' first capture group" & vbCrLf & _
    "Next" & vbCrLf & vbCrLf & _
    "out = re.Replace(s, ""$3/$2/$1"")              ' backreferences"
%>
<!--#include file="includes/footer.asp"-->
