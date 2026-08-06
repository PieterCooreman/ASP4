<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 4 — Object composition
'
'  Composition = "HAS-A". An object holds OTHER objects as
'  fields and delegates to them. Because VBScript has NO
'  inheritance (no "Task Extends WorkItem"), composition is the
'  primary way to build rich models — you assemble behaviour
'  from collaborating objects instead of inheriting it.
'
'  The model here:
'    • TeamMember     — a person (name + role)
'    • Task           — a unit of work that HAS-A TeamMember
'                       assignee (an object field) + a state
'    • ProjectTracker — HAS-MANY Tasks (a Dictionary collection)
'
'  THE central VBScript rule this demo teaches — Let vs. Set:
'    • Property Let  → assign a SCALAR  (string/number/boolean)
'        task.Title = "Deploy"
'    • Property Set  → assign an OBJECT
'        Set task.Assignee = devLead
'    • A Property Get that RETURNS an object must itself use Set:
'        Public Property Get Assignee()
'            Set Assignee = p_Assignee
'        End Property
'      and the caller reads it with Set:  Set m = task.Assignee
'  Using Let where Set is required (or vice-versa) is one of the
'  most common VBScript runtime errors LLMs produce.
'
'  Also shown:
'    • NULL-OBJECT handling: an unassigned Task has Assignee =
'      Nothing; the view checks  If Not ... Is Nothing  before use.
'    • PROPERTY CHAINING: task.Assignee.Name reaches through the
'      composed object graph in one expression.
'    • A Dictionary as the HAS-MANY collection of child objects.
' ============================================================


' ============================================================
' TeamMember — a simple value object (the "part" being composed
' into a Task). Scalars only, so plain Property Let/Get pairs.
' ============================================================
Class TeamMember
    Private p_Name
    Private p_Role

    Public Property Let Name(val) : p_Name = val  : End Property
    Public Property Get Name()    : Name = p_Name : End Property

    Public Property Let Role(val) : p_Role = val  : End Property
    Public Property Get Role()    : Role = p_Role : End Property
End Class


' ============================================================
' Task — HAS-A TeamMember. p_Assignee holds an OBJECT, so it is
' exposed through Property SET (assign) and a Set-based Property
' GET (return). p_IsComplete is a scalar flag changed only via
' the MarkComplete() method (controlled state transition).
' ============================================================
Class Task
    Private p_Title
    Private p_IsComplete
    Private p_Assignee      ' a TeamMember object (or Nothing)

    Private Sub Class_Initialize()
        p_IsComplete = False
        Set p_Assignee = Nothing     ' start unassigned (null object)
    End Sub

    Public Property Let Title(val) : p_Title = val  : End Property
    Public Property Get Title()    : Title = p_Title : End Property

    ' Read-only flag — no Let; it changes only through MarkComplete.
    Public Property Get IsComplete() : IsComplete = p_IsComplete : End Property

    ' OBJECT assignment → Property SET (note the Set on the body too).
    Public Property Set Assignee(objMember)
        Set p_Assignee = objMember
    End Property
    ' Returning an OBJECT → the Get body uses Set as well.
    Public Property Get Assignee()
        Set Assignee = p_Assignee
    End Property

    Public Sub MarkComplete()
        p_IsComplete = True
    End Sub
End Class


' ============================================================
' ProjectTracker — HAS-MANY Tasks, keyed by task ID in a
' Dictionary. The Dictionary is the idiomatic VBScript
' collection; AddTask guards against duplicate IDs.
' ============================================================
Class ProjectTracker
    Private p_ProjectName
    Private p_Tasks         ' Scripting.Dictionary of Task objects

    Private Sub Class_Initialize()
        ' A Dictionary is far cleaner than parallel arrays here.
        Set p_Tasks = Server.CreateObject("Scripting.Dictionary")
    End Sub
    Private Sub Class_Terminate()
        Set p_Tasks = Nothing
    End Sub

    Public Property Let ProjectName(val) : p_ProjectName = val         : End Property
    Public Property Get ProjectName()    : ProjectName = p_ProjectName : End Property

    Public Sub AddTask(taskID, objTask)
        If Not p_Tasks.Exists(taskID) Then
            ' .Add stores the object reference; no Set needed for .Add,
            ' but reading it back later DOES need Set (see the view).
            p_Tasks.Add taskID, objTask
        End If
    End Sub

    Public Property Get Count() : Count = p_Tasks.Count : End Property

    ' Expose the collection so a view/renderer can iterate it.
    Public Function Tasks() : Set Tasks = p_Tasks : End Function
End Class


' ============================================================
'  BOOTSTRAP — build the object graph.
' ============================================================

' --- the project (HAS-MANY tasks) ---
Dim myProject : Set myProject = New ProjectTracker
myProject.ProjectName = "ASP Core Infrastructure"

' --- team members (the parts to compose in) ---
Dim devLead : Set devLead = New TeamMember
devLead.Name = "Sarah" : devLead.Role = "Lead Developer"

Dim qaTester : Set qaTester = New TeamMember
qaTester.Name = "James" : qaTester.Role = "QA Analyst"

' --- tasks (each may HAVE an assignee) ---
Dim task1, task2, task3

Set task1 = New Task
task1.Title = "Set up database connection pooling"
Set task1.Assignee = devLead   ' OBJECT assignment → Set
task1.MarkComplete             ' controlled state change

Set task2 = New Task
task2.Title = "Write unit tests for authentication"
Set task2.Assignee = qaTester

Set task3 = New Task
task3.Title = "Deploy to staging server"
' task3 deliberately left UNASSIGNED → Assignee stays Nothing

' --- register the tasks ---
myProject.AddTask "T-001", task1
myProject.AddTask "T-002", task2
myProject.AddTask "T-003", task3
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 4 — Object composition</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    .value{color:#86efac}.error{color:#f87171}.warn{color:#fcd34d}.k{color:#7dd3fc}.muted{color:#64748b}
    .tag{display:inline-block;background:#1e3a5f;color:#7dd3fc;border-radius:3px;padding:0 6px;font-size:.78rem;margin-right:4px}
    table{width:100%;border-collapse:collapse;font-size:.9rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    .pill{display:inline-block;padding:2px 9px;border-radius:9999px;font-size:.75rem;font-weight:bold}
    .pill-done{background:#14532d;color:#86efac}.pill-pending{background:#422006;color:#fcd34d}
  </style>
</head>
<body>
  <h1>Demo 4 — Object composition</h1>
  <h2>HAS-A &amp; HAS-MANY: building a model from collaborating objects (no inheritance needed)</h2>

  <h3>The object graph</h3>
  <div class="section">
    <span class="tag">ProjectTracker</span> has-many <span class="tag">Task</span>
    &nbsp; · &nbsp; <span class="tag">Task</span> has-a <span class="tag">TeamMember</span>
    <pre>Set task1.Assignee = devLead   ' OBJECT field → Property SET
Response.Write task1.Assignee.Name   ' property chaining through the graph</pre>
    <p class="note">A <code>Task</code> doesn't inherit from <code>TeamMember</code> — it <em>holds</em>
    one. Composition like this is how VBScript builds rich models, since the language has no
    inheritance.</p>
  </div>

  <h3>Project dashboard — <%= Server.HTMLEncode(myProject.ProjectName) %></h3>
  <div class="section">
    <table>
      <tr><th>Task</th><th>Assignee</th><th>Role</th><th>Status</th></tr>
      <%
      Dim tasks, key, t, m
      Set tasks = myProject.Tasks()
      For Each key In tasks.Keys
          ' Reading an OBJECT out of the Dictionary → Set.
          Set t = tasks(key)
      %>
        <tr>
          <td><%= Server.HTMLEncode(t.Title) %></td>
          <%
          ' NULL-OBJECT GUARD: only touch Assignee if it exists.
          If Not t.Assignee Is Nothing Then
              Set m = t.Assignee          ' object-returning Get → Set
          %>
            <td class="k"><%= Server.HTMLEncode(m.Name) %></td>
            <td><%= Server.HTMLEncode(m.Role) %></td>
          <%
          Else
          %>
            <td colspan="2"><em class="muted">Unassigned</em></td>
          <%
          End If
          %>
          <td>
          <% If t.IsComplete Then %>
            <span class="pill pill-done">Done</span>
          <% Else %>
            <span class="pill pill-pending">Pending</span>
          <% End If %>
          </td>
        </tr>
      <% Next %>
    </table>
    <p class="note">Row 3 ("Deploy to staging server") was never assigned, so <code>Assignee</code> is
    <code>Nothing</code>. The view checks <code>If Not t.Assignee Is Nothing</code> BEFORE reading
    <code>.Name</code> — skipping that guard would throw error 91 ("Object variable not set").</p>
  </div>

  <h3>The Let-vs-Set rule (the heart of this demo)</h3>
  <div class="section">
    <table>
      <tr><th>You are assigning…</th><th>Use</th><th>Example</th></tr>
      <tr><td>a string / number / boolean</td><td class="value">Property <strong>Let</strong></td><td><code>task.Title = "Deploy"</code></td></tr>
      <tr><td>an object</td><td class="value">Property <strong>Set</strong></td><td><code>Set task.Assignee = devLead</code></td></tr>
      <tr><td>reading an object back</td><td class="value">Get + caller <strong>Set</strong></td><td><code>Set m = task.Assignee</code></td></tr>
    </table>
    <pre>' Inside the class — note BOTH keywords:
Public Property Set Assignee(obj)   '   SET = object assignment
    Set p_Assignee = obj
End Property
Public Property Get Assignee()      '   returns an object…
    Set Assignee = p_Assignee       '   …so the body uses Set too
End Property</pre>
  </div>

  <h3>Rules for coding agents (takeaways from this demo)</h3>
  <div class="section">
    <table>
      <tr><th>Situation</th><th>Do this in VBScript</th></tr>
      <tr><td>"X owns a Y object"</td><td class="value">Composition: a private field holding the Y, exposed via <code>Property Set/Get</code></td></tr>
      <tr><td>Assigning an object to a property</td><td class="value"><code>Set obj.Prop = other</code> (and <code>Property Set</code> in the class)</td></tr>
      <tr><td>A property/method returns an object</td><td class="value">Read it with <code>Set x = obj.Prop</code></td></tr>
      <tr><td>A field might be unset</td><td class="value">Initialise to <code>Nothing</code>; guard with <code>If Not x Is Nothing</code></td></tr>
      <tr><td>"X has many Y"</td><td class="value">A <code>Scripting.Dictionary</code> of Y objects; iterate with <code>For Each</code></td></tr>
      <tr><td>State should change only via rules</td><td class="value">Expose a method (<code>MarkComplete</code>), keep the flag read-only</td></tr>
      <tr><td>Want inheritance ("Y extends X")</td><td class="value">Not available — compose or duck-type instead (see demo 7)</td></tr>
    </table>
  </div>

<%
' --- cleanup: release the graph. Set object fields to Nothing. ---
Set tasks = Nothing
Set task1 = Nothing : Set task2 = Nothing : Set task3 = Nothing
Set devLead = Nothing : Set qaTester = Nothing
Set myProject = Nothing
%>
</body>
</html>
