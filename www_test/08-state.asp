<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 08-state.asp - Session and Application state
' Demonstrates: per-user Session variables (counter, last-visit timestamp,
' a stored name) and server-wide Application state (a global hit counter)
' guarded with Application.Lock / Unlock. Includes a small action handler.
' ============================================================================
Dim PageTitle : PageTitle = "Session & Application"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Handle simple actions via the query string ---------------------------
Dim action : action = LCase(Trim(Request.QueryString("action") & ""))

If action = "reset" Then
    Session.Contents.Remove("visits")
    Session.Contents.Remove("name")
ElseIf action = "setname" Then
    Session("name") = Trim(Request.QueryString("name") & "")
End If

' --- Per-user Session counter ---------------------------------------------
If IsEmpty(Session("visits")) Then
    Session("visits") = 1
Else
    Session("visits") = Session("visits") + 1
End If
Session("lastVisit") = Now()

' --- Server-wide Application hit counter (must be locked) ------------------
Application.Lock
If IsEmpty(Application("totalHits")) Then
    Application("totalHits") = 1
Else
    Application("totalHits") = Application("totalHits") + 1
End If
Dim totalHits : totalHits = Application("totalHits")
Application.Unlock
%>
<h1>Session &amp; Application State</h1>
<p class="lead">
  <strong>Session</strong> data is private to one browser; <strong>Application</strong>
  data is shared across all visitors. Reload the page to watch the counters move.
</p>

<h2>Your Session</h2>
<%
DemoStart "Per-user values (refresh to increment)"
WriteLine "<table class=""kv"">"
RenderTableRow "Session.SessionID",     Session.SessionID
RenderTableRow "Visits this session",   Session("visits")
RenderTableRow "Stored name",           Coalesce(Session("name"), "(not set)")
RenderTableRow "Last visit",            Session("lastVisit")
RenderTableRow "Session.Timeout (min)", Session.Timeout
RenderTableRow "Session.CodePage",      Session.CodePage
WriteLine "</table>"
DemoEnd
%>

<h2>Shared Application state</h2>
<%
DemoStart "Global counter, incremented under Application.Lock"
WriteLine "<table class=""kv"">"
RenderTableRow "Total hits (all users)", totalHits
WriteLine "</table>"
WriteLine "<p class=""warn"">Note: this counter resets when the IIS app pool recycles.</p>"
DemoEnd
%>

<h2>Try it</h2>
<%
DemoStart "Actions handled server-side via the query string"
%>
<form method="get" action="08-state.asp" class="demo-form">
  <input type="hidden" name="action" value="setname">
  <div>
    <label for="name">Store a name in your Session</label>
    <input type="text" id="name" name="name" value="<%= HtmlEncode(Coalesce(Session("name"), "")) %>">
  </div>
  <button type="submit">Save to Session</button>
</form>
<p style="margin-top:12px">
  <a href="08-state.asp">Reload (increments visits)</a> &nbsp;|&nbsp;
  <a href="08-state.asp?action=reset">Reset my Session</a>
</p>
<%
DemoEnd
%>

<h2>How it works</h2>
<%
CodeBlock _
    "' Per-user counter" & vbCrLf & _
    "If IsEmpty(Session(""visits"")) Then" & vbCrLf & _
    "    Session(""visits"") = 1" & vbCrLf & _
    "Else" & vbCrLf & _
    "    Session(""visits"") = Session(""visits"") + 1" & vbCrLf & _
    "End If" & vbCrLf & vbCrLf & _
    "' Shared counter - always Lock/Unlock around writes" & vbCrLf & _
    "Application.Lock" & vbCrLf & _
    "Application(""totalHits"") = Application(""totalHits"") + 1" & vbCrLf & _
    "Application.Unlock"
%>
<!--#include file="includes/footer.asp"-->
