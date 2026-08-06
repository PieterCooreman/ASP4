<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 06-strings.asp - String manipulation
' Demonstrates: Len, UCase/LCase, Left/Right/Mid, InStr/InStrRev, Replace,
' Split/Join, StrReverse, Trim family, formatting, and two small algorithms
' (palindrome test + word counter) built from these primitives.
' ============================================================================
Dim PageTitle : PageTitle = "String Functions"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Palindrome test (ignores case and non-letters) -----------------------
Function IsPalindrome(ByVal s)
    Dim clean, ch, i
    clean = ""
    s = LCase(s)
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If ch >= "a" And ch <= "z" Then clean = clean & ch
    Next
    IsPalindrome = (clean = StrReverse(clean)) And (Len(clean) > 0)
End Function

' --- Word counter ----------------------------------------------------------
Function WordCount(ByVal s)
    Dim parts
    s = Trim(s)
    If Len(s) = 0 Then
        WordCount = 0
    Else
        ' Collapse runs of spaces, then split.
        Do While InStr(s, "  ") > 0
            s = Replace(s, "  ", " ")
        Loop
        parts = Split(s, " ")
        WordCount = UBound(parts) + 1
    End If
End Function

' --- Title-case each word --------------------------------------------------
Function TitleCase(ByVal s)
    Dim words, i
    words = Split(LCase(Trim(s)), " ")
    For i = 0 To UBound(words)
        If Len(words(i)) > 0 Then
            words(i) = UCase(Left(words(i), 1)) & Mid(words(i), 2)
        End If
    Next
    TitleCase = Join(words, " ")
End Function
%>
<h1>String Functions</h1>
<p class="lead">The built-in VBScript string toolbox, plus algorithms built from it.</p>

<h2>Core string functions</h2>
<%
DemoStart "Operating on the sample phrase"
Dim phrase : phrase = "Classic ASP on IIS"
WriteLine "<table class=""kv"">"
RenderTableRow "phrase",                phrase
RenderTableRow "Len",                   Len(phrase)
RenderTableRow "UCase",                 UCase(phrase)
RenderTableRow "LCase",                 LCase(phrase)
RenderTableRow "Left(phrase, 7)",       Left(phrase, 7)
RenderTableRow "Right(phrase, 3)",      Right(phrase, 3)
RenderTableRow "Mid(phrase, 9, 3)",     Mid(phrase, 9, 3)
RenderTableRow "InStr(phrase,""IIS"")", InStr(phrase, "IIS")
RenderTableRow "Replace ASP->ASP.NET",  Replace(phrase, "ASP", "ASP.NET")
RenderTableRow "StrReverse",            StrReverse(phrase)
WriteLine "</table>"
DemoEnd
%>

<h2>Split and Join</h2>
<%
DemoStart "CSV round-trip"
Dim csv : csv = "alpha,beta,gamma,delta"
Dim arr : arr = Split(csv, ",")
WriteLine "<p>Split into <strong>" & (UBound(arr) + 1) & "</strong> items.</p>"
WriteLine "<ul>"
Dim item
For Each item In arr
    WriteLine "<li>" & HtmlEncode(item) & "</li>"
Next
WriteLine "</ul>"
WriteLine "<p>Re-joined with "" | "": <strong>" & HtmlEncode(Join(arr, " | ")) & "</strong></p>"
DemoEnd
%>

<h2>Trimming and padding</h2>
<%
DemoStart "Trim family + Space + String"
Dim padded : padded = "   spaced out   "
WriteLine "<table class=""kv"">"
RenderTableRow "Original (bracketed)", "[" & padded & "]"
RenderTableRow "LTrim",  "[" & LTrim(padded) & "]"
RenderTableRow "RTrim",  "[" & RTrim(padded) & "]"
RenderTableRow "Trim",   "[" & Trim(padded) & "]"
RenderTableRow "Space(5)+'X'", "[" & Space(5) & "X]"
RenderTableRow "String(10, ""*"")", String(10, "*")
WriteLine "</table>"
DemoEnd
%>

<h2>Algorithms built from string primitives</h2>
<%
DemoStart "Palindrome, word count, and title-case"
WriteLine "<table class=""kv"">"
RenderTableRow "IsPalindrome(""A man, a plan, a canal: Panama"")", IsPalindrome("A man, a plan, a canal: Panama")
RenderTableRow "IsPalindrome(""hello"")",  IsPalindrome("hello")
RenderTableRow "WordCount(""the   quick brown   fox"")", WordCount("the   quick brown   fox")
RenderTableRow "TitleCase(""keep classic asp alive"")", TitleCase("keep classic asp alive")
WriteLine "</table>"
DemoEnd
%>

<h2>Formatting functions</h2>
<%
DemoStart "Number, currency, percent and date formatting"
WriteLine "<table class=""kv"">"
RenderTableRow "FormatNumber(1234567.891, 2)", FormatNumber(1234567.891, 2)
RenderTableRow "FormatCurrency(2599.5)",        FormatCurrency(2599.5)
RenderTableRow "FormatPercent(0.1875)",         FormatPercent(0.1875)
RenderTableRow "FormatDateTime(Now, 1)",        FormatDateTime(Now, 1)
RenderTableRow "FormatDateTime(Now, 2)",        FormatDateTime(Now, 2)
WriteLine "</table>"
DemoEnd
%>
<!--#include file="includes/footer.asp"-->
