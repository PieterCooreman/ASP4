<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 16-session-objects.asp - Storing OBJECTS in Session (and Application)
' ----------------------------------------------------------------------------
' Page 08 covered SCALAR Session/Application values. Real-world frameworks
' (MVC-style ViewBag / TempData carriers, shopping carts, wizard state) go one
' step further: they store an OBJECT REFERENCE - typically a
' Scripting.Dictionary - in Session state:
'
'     Set Session("viewBag") = someDictionary
'
' A correct ASP engine keeps the reference alive as an object. A broken engine
' silently serialises it to a string like "[NativeObject:20223]" - and then
' TypeName() returns "String", IsObject() returns False, and the first method
' call (.Count, .Add, ...) dies with a cryptic "Object required" error.
'
' This page verifies the CORRECT behaviour, in a way that REPORTS failure
' instead of crashing:
'
'   * Set Session("x") = obj  stores a live reference (Set, not Let!)
'   * TypeName(retrieved) must be "Dictionary" and IsObject(retrieved) True
'   * Mutations through the retrieved reference are visible on the next read
'   * BUT: IIS refuses apartment-threaded objects (Scripting.Dictionary is
'     one) in the APPLICATION collection - that store raises ASP 0197
'     "Cannot add object with apartment model behavior...". The trap is
'     demonstrated safely below inside a scoped error guard.
'   * Clean up with Session.Contents.Remove when done
'
' Every object read is guarded with IsObject() BEFORE any method call, so on a
' broken engine this page prints FAIL rows rather than raising "Object
' required". That guard is itself a pattern worth copying.
' ============================================================================
Dim PageTitle : PageTitle = "Objects in Session"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Pass/Fail check row -----------------------------------------------------
' Emits a three-column <tr>: label, actual value, and a coloured verdict.
' The caller computes `pass` so checks can be guarded (no method calls on a
' value that turned out not to be an object).
Sub CheckRow(ByVal sLabel, ByVal vActual, ByVal bPass)
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              HtmlEncode(vActual) & "</td><td class=""" & _
              IIf(bPass, "ok", "err") & """>" & _
              IIf(bPass, "PASS", "FAIL") & "</td></tr>"
End Sub

' --- Handle simple actions via the query string ------------------------------
Dim action : action = LCase(Trim(Request.QueryString("action") & ""))

If action = "reset" Then
    Session.Contents.Remove("viewBag")
ElseIf action = "add" Then
    ' Only touch the stored object when it really IS an object.
    If IsObject(Session("viewBag")) Then
        Dim bagForAdd : Set bagForAdd = Session("viewBag")
        Dim newKey : newKey = Trim(Request.QueryString("key") & "")
        If Len(newKey) > 0 Then
            bagForAdd(newKey) = Trim(Request.QueryString("value") & "")
        End If
    End If
End If

' --- Make sure a Dictionary lives in the Session ------------------------------
' First visit: create it and store the REFERENCE with Set. This is the exact
' pattern MVC-style frameworks use for a ViewBag / TempData carrier, sometimes
' passed across Server.Execute calls.
If Not IsObject(Session("viewBag")) Then
    Dim freshBag : Set freshBag = Server.CreateObject("Scripting.Dictionary")
    freshBag.Add "title", "Hello World"
    Set Session("viewBag") = freshBag          ' Set = store the object itself
End If
%>
<h1>Storing Objects in Session</h1>
<p class="lead">
  <code>Session</code> can hold more than strings and numbers: it can hold a
  <strong>live object reference</strong>, such as a
  <code>Scripting.Dictionary</code> used as a ViewBag. The checks below must
  all report <span class="ok">PASS</span> for a correct engine.
</p>

<h2>The core test: store and retrieve a Dictionary</h2>
<p>
  Stored with <code>Set Session("viewBag") = dict</code>, then read back.
  In classic IIS/ASP these are all true; an engine that serialises the object
  to a string fails every row.
</p>
<%
Dim isObj : isObj = IsObject(Session("viewBag"))

DemoStart "Object survival checks (guarded, so a broken engine prints FAIL instead of crashing)"
WriteLine "<table class=""kv"">"
CheckRow "IsObject(Session(""viewBag""))", isObj, isObj

If isObj Then
    Dim retrieved : Set retrieved = Session("viewBag")
    CheckRow "TypeName(retrieved)",  TypeName(retrieved),  (TypeName(retrieved) = "Dictionary")
    CheckRow "retrieved.Count >= 1", retrieved.Count,      (retrieved.Count >= 1)
    If retrieved.Exists("title") Then
        CheckRow "retrieved(""title"")", retrieved("title"), (retrieved("title") = "Hello World")
    Else
        CheckRow "retrieved(""title"")", "(key was removed/renamed via the form below)", True
    End If
Else
    ' Never call .Count / .Add here - on a broken engine the value is a mere
    ' string and any method call would raise "Object required".
    WriteLine "<tr><td colspan=""3"" class=""err"">The Session returned a " & _
              TypeName(Session("viewBag")) & " instead of an object - this engine " & _
              "serialised it (e.g. ""[NativeObject:...]""). Object storage is broken.</td></tr>"
End If
WriteLine "</table>"
DemoEnd
%>

<h2>Mutations persist through the reference</h2>
<p>
  Because the Session holds the <strong>same live object</strong>, writing
  through the retrieved reference is immediately visible on the next read -
  no need to store it back.
</p>
<%
If isObj Then
    DemoStart "Write via one reference, read via another"
    retrieved("lastVisit") = Now()             ' mutate through the reference
    Dim reread : Set reread = Session("viewBag")
    WriteLine "<table class=""kv"">"
    RenderTableRow "Keys now in the bag",   Join(reread.Keys, ", ")
    RenderTableRow "Value written via ref", reread("lastVisit")
    RenderTableRow "Count",                 reread.Count
    WriteLine "</table>"
    DemoEnd
End If
%>

<h2>The Application trap: IIS refuses apartment-threaded objects</h2>
<p>
  Session accepts an object reference, but on IIS the server-wide
  <code>Application</code> collection does <strong>not</strong>: storing a
  <code>Scripting.Dictionary</code> (an apartment-threaded COM object) there raises
  <em>ASP 0197 - "Cannot add object with apartment model behavior to the
  application intrinsic object"</em>. Application state may only hold
  <strong>free-threaded</strong> objects. The demo below attempts the store inside a
  scoped error guard, so the page reports the trap instead of dying from it.
</p>
<%
DemoStart "Attempted Application store, guarded"
On Error Resume Next
Application.Lock
Dim appDict : Set appDict = Server.CreateObject("Scripting.Dictionary")
appDict.Add "created", Now()
Set Application("appWideDict") = appDict            ' ASP 0197 on IIS
Dim appErr : appErr = Err.Number & ": " & Err.Description
Err.Clear
Application.Unlock
On Error Goto 0

If IsObject(Application("appWideDict")) Then
    WriteLine "<p class=""ok"">This engine accepted the object in Application state " & _
              "(a lenient or free-threaded engine). Created at " & _
              HtmlEncode(Application("appWideDict")("created")) & " - it resets when the app recycles.</p>"
Else
    WriteLine "<table class=""kv"">"
    RenderTableRow "Store result",  "REFUSED by the engine"
    RenderTableRow "Error raised",  appErr
    WriteLine "</table>"
    WriteLine "<p class=""warn"">Expected on IIS: use <strong>Session</strong> for per-user objects; " & _
              "Application state needs a free-threaded component.</p>"
End If
DemoEnd
%>

<h2>Try it</h2>
<%
DemoStart "Add your own key to the Session Dictionary"
%>
<form method="get" action="16-session-objects.asp" class="demo-form">
  <input type="hidden" name="action" value="add">
  <div>
    <label for="key">Key</label>
    <input type="text" id="key" name="key" value="note">
  </div>
  <div>
    <label for="value">Value</label>
    <input type="text" id="value" name="value" value="remember me">
  </div>
  <button type="submit">Add to Session Dictionary</button>
</form>
<p style="margin-top:12px">
  <a href="16-session-objects.asp">Reload</a> &nbsp;|&nbsp;
  <a href="16-session-objects.asp?action=reset">Remove the Dictionary from my Session</a>
</p>
<%
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "' STORE: use Set (object reference), not Let" & vbCrLf & _
    "Dim bag : Set bag = Server.CreateObject(""Scripting.Dictionary"")" & vbCrLf & _
    "bag.Add ""title"", ""Hello World""" & vbCrLf & _
    "Set Session(""bag"") = bag" & vbCrLf & vbCrLf & _
    "' RETRIEVE defensively: IsObject BEFORE any method call" & vbCrLf & _
    "If IsObject(Session(""bag"")) Then" & vbCrLf & _
    "    Dim r : Set r = Session(""bag"")" & vbCrLf & _
    "    Response.Write r.Count          ' safe: r is the live Dictionary" & vbCrLf & _
    "Else" & vbCrLf & _
    "    ' Engine serialised the object to a string - Session object" & vbCrLf & _
    "    ' storage is broken on this engine. Do NOT call r.Count here:" & vbCrLf & _
    "    ' it would raise ""Object required""." & vbCrLf & _
    "End If" & vbCrLf & vbCrLf & _
    "' WARNING - the Application trap:" & vbCrLf & _
    "' Set Application(""d"") = Server.CreateObject(""Scripting.Dictionary"")" & vbCrLf & _
    "' raises ASP 0197 on IIS (apartment-threaded objects are refused)." & vbCrLf & _
    "' Use Session for per-user objects; Application needs a" & vbCrLf & _
    "' free-threaded component. Guard the attempt if unsure:" & vbCrLf & _
    "On Error Resume Next : Set Application(""d"") = d : On Error Goto 0" & vbCrLf & vbCrLf & _
    "' CLEAN UP when done" & vbCrLf & _
    "Session.Contents.Remove ""bag"""
%>
<!--#include file="includes/footer.asp"-->
