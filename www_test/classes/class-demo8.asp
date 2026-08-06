<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 8 — Real request handling
'
'  This is the pattern that matters most for Classic ASP web
'  apps: take untrusted Request data, turn it into a validated
'  object, persist it through a repository, and drive its
'  lifecycle with a state machine — all with classes.
'
'  Layers shown (each a class with one job):
'    • TicketRequest  — DTO built FROM Request, self-validating,
'                       HTML-encodes on the way OUT (XSS-safe).
'    • Ticket         — domain entity with a STATE MACHINE
'                       (Open → InProgress → Resolved → Closed)
'                       that rejects illegal transitions.
'    • TicketRepository — in-memory store (swap for a DB later)
'                       built on Scripting.Dictionary.
'    • TicketService  — orchestrates: validate → save → return.
'
'  WHY classes here: request handling is where loose VBScript
'  rots fastest (globals, repeated Request() calls, scattered
'  validation, SQL built inline). Classes contain the chaos.
'
'  NOTE: This page SIMULATES a POST by seeding Request-like
'  values into a Dictionary so it renders standalone in an
'  iframe. In a live form you would read Request.Form("...").
' ============================================================


' VBScript has no ternary operator; this helper stands in for it.
Function IIf(cond, a, b)
    If cond Then IIf = a Else IIf = b
End Function


' ============================================================
' DTO — TicketRequest
' Wraps raw input. Every getter returns an HTML-ENCODED value
' so the rest of the app cannot accidentally emit raw user
' text (defence-in-depth against XSS). Validation lives here.
' ============================================================
Class TicketRequest
    Private m_subject
    Private m_priority
    Private m_email
    Private m_errors()
    Private m_errCount

    Private Sub Class_Initialize()
        m_errCount = 0 : ReDim m_errors(-1)
    End Sub

    ' Bind from a source that behaves like Request.Form:
    ' anything exposing source(key). We pass a Dictionary here.
    Public Sub BindFrom(source)
        m_subject  = Trim(source("subject")  & "")
        m_priority = UCase(Trim(source("priority") & ""))
        m_email    = Trim(source("email")    & "")
    End Sub

    Private Sub AddError(msg)
        ReDim Preserve m_errors(m_errCount)
        m_errors(m_errCount) = msg
        m_errCount = m_errCount + 1
    End Sub

    Public Function Validate()
        m_errCount = 0 : ReDim m_errors(-1)
        If Len(m_subject) = 0 Then AddError "Subject is required."
        If Len(m_subject) > 80 Then AddError "Subject must be 80 characters or fewer."
        If InStr(m_email, "@") = 0 Then AddError "A valid email is required."
        Select Case m_priority
            Case "LOW", "NORMAL", "HIGH", "URGENT"   ' ok
            Case Else : AddError "Priority must be Low, Normal, High or Urgent."
        End Select
        Validate = (m_errCount = 0)
    End Function

    Public Property Get IsValid()    : IsValid    = (m_errCount = 0) : End Property
    Public Property Get ErrorCount() : ErrorCount = m_errCount       : End Property
    Public Function ErrorAt(i)       : ErrorAt    = m_errors(i)      : End Function

    ' Encoded getters — safe to write straight into HTML.
    Public Property Get Subject()  : Subject  = Server.HTMLEncode(m_subject)  : End Property
    Public Property Get Priority() : Priority = Server.HTMLEncode(m_priority) : End Property
    Public Property Get Email()    : Email    = Server.HTMLEncode(m_email)    : End Property
    ' Raw getters — for persistence only, never for HTML output.
    Public Property Get RawSubject() : RawSubject = m_subject : End Property
End Class


' ============================================================
' ENTITY — Ticket  (with a STATE MACHINE)
' A ticket may only move along legal transitions. Trying to
' Close an Open ticket directly is rejected. The allowed graph
' is encoded in CanTransitionTo, NOT scattered across the app.
' ============================================================
Class Ticket
    Private m_id
    Private m_subject
    Private m_priority
    Private m_state          ' OPEN | INPROGRESS | RESOLVED | CLOSED
    Private m_history()      ' audit trail of transitions
    Private m_histCount

    Private Sub Class_Initialize()
        m_state = "OPEN"
        m_histCount = 0 : ReDim m_history(-1)
        Log "Created (state OPEN)"
    End Sub

    Public Property Let ID(v)       : m_id = v       : End Property
    Public Property Get ID()        : ID = m_id      : End Property
    Public Property Let Subject(v)  : m_subject = v  : End Property
    Public Property Get Subject()   : Subject = m_subject : End Property
    Public Property Let Priority(v) : m_priority = v : End Property
    Public Property Get Priority()  : Priority = m_priority : End Property
    Public Property Get State()     : State = m_state : End Property

    Private Sub Log(msg)
        ReDim Preserve m_history(m_histCount)
        m_history(m_histCount) = msg
        m_histCount = m_histCount + 1
    End Sub

    ' The legal transition graph lives in ONE place.
    Private Function CanTransitionTo(target)
        Select Case m_state & ">" & target
            Case "OPEN>INPROGRESS", _
                 "INPROGRESS>RESOLVED", _
                 "RESOLVED>CLOSED", _
                 "RESOLVED>INPROGRESS"   ' reopen for rework
                CanTransitionTo = True
            Case Else
                CanTransitionTo = False
        End Select
    End Function

    ' Returns True on success, False if the move is illegal.
    Public Function MoveTo(target)
        target = UCase(target)
        If CanTransitionTo(target) Then
            Log m_state & " → " & target
            m_state = target
            MoveTo = True
        Else
            Log "REJECTED " & m_state & " → " & target & " (illegal)"
            MoveTo = False
        End If
    End Function

    Public Property Get HistoryCount() : HistoryCount = m_histCount : End Property
    Public Function HistoryAt(i)       : HistoryAt = m_history(i)   : End Function
End Class


' ============================================================
' REPOSITORY — TicketRepository
' Abstracts storage. Today: a Dictionary. Tomorrow: swap the
' body for ADO/SQL and NOTHING else in the app changes. That
' is the value of the repository pattern.
' ============================================================
Class TicketRepository
    Private m_store
    Private m_nextId

    Private Sub Class_Initialize()
        Set m_store = Server.CreateObject("Scripting.Dictionary")
        m_nextId = 1000
    End Sub
    Private Sub Class_Terminate()
        Set m_store = Nothing
    End Sub

    Public Function NextId()
        m_nextId = m_nextId + 1
        NextId = "TK-" & m_nextId
    End Function

    Public Sub Save(ticket)
        ' Storing an OBJECT in a Dictionary requires Set (scalars don't).
        Set m_store(ticket.ID) = ticket
    End Sub

    Public Function FindById(id)
        If m_store.Exists(id) Then Set FindById = m_store(id) Else Set FindById = Nothing
    End Function

    Public Property Get Count() : Count = m_store.Count : End Property
    Public Function Keys()      : Keys = m_store.Keys   : End Function
    Public Function Get_(id)    : Set Get_ = m_store(id): End Function
End Class


' ============================================================
' SERVICE — TicketService
' Orchestration layer. Takes a request, validates, creates the
' entity, persists it. The page (controller) only talks to this.
' ============================================================
Class TicketService
    Private m_repo
    Public Property Set Repository(r) : Set m_repo = r : End Property

    ' Returns the new Ticket on success, or Nothing on failure.
    Public Function CreateTicket(req)
        If Not req.IsValid Then Set CreateTicket = Nothing : Exit Function
        Dim t : Set t = New Ticket
        t.ID       = m_repo.NextId()
        t.Subject  = req.RawSubject          ' raw for storage
        t.Priority = req.Priority
        m_repo.Save t
        Set CreateTicket = t
    End Function
End Class


' ============================================================
'  USAGE — simulate two POSTs (one valid, one invalid)
' ============================================================

' Wire up the layers (in real code: do this once per request).
Dim repo : Set repo = New TicketRepository
Dim svc  : Set svc  = New TicketService
Set svc.Repository = repo

' ---- Simulated good POST ----
Dim form1 : Set form1 = Server.CreateObject("Scripting.Dictionary")
form1("subject")  = "Login page returns 500 after deploy"
form1("priority") = "high"
form1("email")    = "ops@example.com"

Dim req1 : Set req1 = New TicketRequest
req1.BindFrom form1
req1.Validate

Dim ticket1 : Set ticket1 = svc.CreateTicket(req1)

' Drive the state machine: legal then illegal transition.
Dim moveA, moveB, moveC
If Not ticket1 Is Nothing Then
    moveA = ticket1.MoveTo("INPROGRESS")   ' legal
    moveB = ticket1.MoveTo("CLOSED")       ' ILLEGAL (must resolve first)
    moveC = ticket1.MoveTo("RESOLVED")     ' legal
End If

' ---- Simulated bad POST ----
Dim form2 : Set form2 = Server.CreateObject("Scripting.Dictionary")
form2("subject")  = ""                ' missing
form2("priority") = "SOMETIMES"       ' invalid
form2("email")    = "broken-email"    ' no @

Dim req2 : Set req2 = New TicketRequest
req2.BindFrom form2
req2.Validate

Dim ticket2 : Set ticket2 = svc.CreateTicket(req2)   ' returns Nothing
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 8 — Request handling, repository &amp; state machine</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    table{width:100%;border-collapse:collapse;font-size:.9rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035}
    .ok{color:#86efac}.err{color:#f87171}.warn{color:#fcd34d}.k{color:#7dd3fc}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    .pill{display:inline-block;padding:2px 9px;border-radius:9999px;font-size:.75rem;font-weight:bold;background:#1e3a5f;color:#7dd3fc}
  </style>
</head>
<body>
  <h1>Demo 8 — Request handling, repository &amp; state machine</h1>
  <h2>DTO → validation → entity → repository → service: the layered Classic-ASP pattern</h2>

  <h3>Valid submission → ticket created &amp; persisted</h3>
  <div class="section">
    <% If Not ticket1 Is Nothing Then %>
      <table>
        <tr><th>Field</th><th>Value (HTML-encoded on output)</th></tr>
        <tr><td class="k">Ticket ID</td><td class="ok"><%= ticket1.ID %></td></tr>
        <tr><td class="k">Subject</td><td><%= req1.Subject %></td></tr>
        <tr><td class="k">Priority</td><td><span class="pill"><%= req1.Priority %></span></td></tr>
        <tr><td class="k">Email</td><td><%= req1.Email %></td></tr>
        <tr><td class="k">Current state</td><td class="ok"><%= ticket1.State %></td></tr>
      </table>
    <% End If %>
    <p class="note">The DTO validated the input, the service created the entity, and the repository
    stored it. The controller (this page) wrote only encoded values to HTML.</p>
  </div>

  <h3>State machine — legal vs. illegal transitions</h3>
  <div class="section">
    <pre>OPEN → INPROGRESS    (legal)
INPROGRESS → CLOSED  (ILLEGAL — must be RESOLVED first)
INPROGRESS → RESOLVED(legal)</pre>
    <table>
      <tr><th>Attempted move</th><th>Result</th></tr>
      <tr><td>Open → InProgress</td><td><%= IIf(moveA, "<span class='ok'>accepted</span>", "<span class='err'>rejected</span>") %></td></tr>
      <tr><td>InProgress → Closed</td><td><%= IIf(moveB, "<span class='ok'>accepted</span>", "<span class='err'>rejected (illegal)</span>") %></td></tr>
      <tr><td>InProgress → Resolved</td><td><%= IIf(moveC, "<span class='ok'>accepted</span>", "<span class='err'>rejected</span>") %></td></tr>
    </table>
    <p class="note"><strong>Audit trail</strong> (kept inside the Ticket object):</p>
    <pre><%
      Dim h
      For h = 0 To ticket1.HistoryCount - 1
        Response.Write Server.HTMLEncode(ticket1.HistoryAt(h)) & vbCrLf
      Next
    %></pre>
  </div>

  <h3>Invalid submission → service refuses to create</h3>
  <div class="section">
    <p class="warn"><%= req2.ErrorCount %> validation error(s); no ticket created:</p>
    <ul>
    <%
    Dim e
    For e = 0 To req2.ErrorCount - 1
    %>
      <li class="err"><%= Server.HTMLEncode(req2.ErrorAt(e)) %></li>
    <% Next %>
    </ul>
    <p class="note"><code>CreateTicket</code> returned <code>Nothing</code> because
    <code>req2.IsValid</code> was False — invalid data never reaches the repository.</p>
  </div>

  <h3>Repository state</h3>
  <div class="section">
    <p>Tickets stored: <span class="ok"><%= repo.Count %></span></p>
    <p class="note">Swap <code>TicketRepository</code>'s Dictionary for ADO/SQL and no other layer
    changes — that is the point of putting persistence behind a class.</p>
  </div>

  <h3>Why a coding agent should structure ASP this way</h3>
  <div class="section">
    <table>
      <tr><th>Layer</th><th>Responsibility</th><th>Replaces the bad habit of…</th></tr>
      <tr><td class="k">DTO (TicketRequest)</td><td>Read + validate + encode input</td><td>Calling <code>Request.Form()</code> all over the page</td></tr>
      <tr><td class="k">Entity (Ticket)</td><td>Business rules &amp; state machine</td><td><code>If status = "x" Then status = "y"</code> scattered everywhere</td></tr>
      <tr><td class="k">Repository</td><td>Storage behind an interface</td><td>Inline SQL strings mixed into page logic</td></tr>
      <tr><td class="k">Service</td><td>Orchestrate the use-case</td><td>One 400-line <code>&lt;% %&gt;</code> block</td></tr>
    </table>
  </div>

<%
Set req1 = Nothing : Set req2 = Nothing
Set ticket1 = Nothing : Set ticket2 = Nothing
Set form1 = Nothing : Set form2 = Nothing
Set svc = Nothing : Set repo = Nothing
%>
</body>
</html>
