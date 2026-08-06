<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 6 — Error handling done right
'
'  VBScript has NO Try/Catch. It only has:
'      On Error Resume Next   ' suppress + continue
'      On Error Goto 0        ' restore normal error halting
'      Err.Number / .Description / .Source / .Raise
'
'  The naive pattern (On Error Resume Next at the top of a
'  page and never turning it off) HIDES bugs. This demo shows
'  the disciplined patterns a coding agent should generate:
'
'    A. Result object  — methods return success/failure as
'       DATA instead of throwing. Caller never needs On Error.
'    B. Validator class — accumulates MULTIPLE errors instead
'       of stopping at the first one.
'    C. Scoped "Try" wrapper — On Error Resume Next is enabled
'       only around ONE risky call, then immediately disabled.
'    D. Err.Raise for true invariant violations (programmer
'       errors) that should NOT be swallowed.
' ============================================================


' ============================================================
' CLASS — Result
' A value-object that represents the OUTCOME of an operation.
' Instead of raising, methods hand back one of these. The
' caller inspects .Ok rather than wrapping calls in On Error.
' ============================================================
Class Result
    Private m_ok
    Private m_value
    Private m_error

    Private Sub Class_Initialize()
        m_ok = True : m_value = Empty : m_error = ""
    End Sub

    Public Property Get Ok()    : Ok    = m_ok    : End Property
    Public Property Get Value() : Value = m_value : End Property
    Public Property Get Error() : Error = m_error : End Property

    ' Factory-style configurators (return Me for fluency)
    Public Function Success(v)
        m_ok = True : m_value = v : m_error = "" : Set Success = Me
    End Function
    Public Function Failure(msg)
        m_ok = False : m_value = Empty : m_error = msg : Set Failure = Me
    End Function
End Class


' ============================================================
' CLASS — Validator
' Collects ALL validation errors for an input, not just the
' first. This is how real forms should report problems.
' ============================================================
Class Validator
    Private m_errors()
    Private m_count

    Private Sub Class_Initialize()
        m_count = 0 : ReDim m_errors(-1)
    End Sub

    ' Assert: if condition is False, record a message. Chainable.
    Public Function Check(condition, message)
        If Not condition Then
            ReDim Preserve m_errors(m_count)
            m_errors(m_count) = message
            m_count = m_count + 1
        End If
        Set Check = Me
    End Function

    Public Property Get IsValid() : IsValid = (m_count = 0) : End Property
    Public Property Get Count()   : Count   = m_count       : End Property
    Public Function ErrorAt(i)    : ErrorAt = m_errors(i)   : End Function

    Public Function Errors()
        If m_count = 0 Then Errors = Array() Else Errors = m_errors
    End Function
End Class


' ============================================================
' CLASS — BankAccount
' Business object that uses BOTH strategies:
'   • Withdraw returns a Result (expected failure: low balance)
'   • Deposit raises an error for an IMPOSSIBLE argument
'     (negative deposit = programmer bug, must surface loudly)
' ============================================================
Class BankAccount
    Private m_balance
    Private Sub Class_Initialize() : m_balance = 0 : End Sub

    Public Property Get Balance() : Balance = m_balance : End Property

    ' Expected, recoverable outcome → Result object, no raise.
    Public Function Withdraw(amount)
        Dim r : Set r = New Result
        If Not IsNumeric(amount) Then
            Set Withdraw = r.Failure("Amount must be numeric") : Exit Function
        End If
        amount = CDbl(amount)
        If amount <= 0 Then
            Set Withdraw = r.Failure("Amount must be positive") : Exit Function
        End If
        If amount > m_balance Then
            Set Withdraw = r.Failure("Insufficient funds: balance is €" & _
                FormatNumber(m_balance, 2)) : Exit Function
        End If
        m_balance = m_balance - amount
        Set Withdraw = r.Success(m_balance)
    End Function

    ' Programmer error / broken invariant → Err.Raise (do NOT hide).
    Public Sub Deposit(amount)
        If Not IsNumeric(amount) Or CDbl(amount) < 0 Then
            Err.Raise 6100, "BankAccount.Deposit", _
                "Deposit amount cannot be negative or non-numeric: " & amount
        End If
        m_balance = m_balance + CDbl(amount)
    End Sub
End Class


' ============================================================
' CLASS — Try
' A tiny scoped wrapper. SafeCall runs On Error Resume Next
' for the duration of ONE risky operation, captures the Err,
' then restores normal halting. The rest of the page is never
' left in a silent-failure state.
' ============================================================
Class TryRunner
    Public LastError
    Public LastNumber

    ' We can't pass arbitrary statements, so callers hand us an
    ' object + method name pattern. For the demo we wrap Deposit.
    Public Function Deposit(account, amount)
        LastError = "" : LastNumber = 0
        On Error Resume Next            ' ---- danger zone START
        account.Deposit amount
        If Err.Number <> 0 Then
            LastNumber = Err.Number
            LastError  = Err.Description
        End If
        On Error Goto 0                 ' ---- danger zone END (always!)
        Deposit = (LastNumber = 0)
    End Function
End Class


' ============================================================
'  USAGE
' ============================================================

' --- A. Result pattern: withdrawals ---
Dim acct : Set acct = New BankAccount
acct.Deposit 100

Dim w1 : Set w1 = acct.Withdraw(30)     ' ok
Dim w2 : Set w2 = acct.Withdraw(500)    ' fails: insufficient
Dim w3 : Set w3 = acct.Withdraw(-5)     ' fails: not positive

' --- B. Validator: register a user, collect ALL problems ---
Dim username : username = "ab"          ' too short
Dim email    : email    = "not-an-email"
Dim age      : age      = "17"

Dim val : Set val = New Validator
' NOTE for coding agents: a chained call used as a *statement* (return value
' discarded) makes VBScript treat the first call as a Sub and reject the
' parentheses. Capturing the returned object with Set avoids that — and since
' Check returns Me, the whole chain still runs in order.
Dim valChain
Set valChain = val.Check(Len(username) >= 3, "Username must be at least 3 characters") _
                  .Check(InStr(email, "@") > 0, "Email must contain '@'") _
                  .Check(IsNumeric(age) And CInt(age) >= 18, "You must be 18 or older")

' --- C/D. TryRunner: deposit a negative amount (programmer bug) ---
Dim runner : Set runner = New TryRunner
Dim depOk  : depOk = runner.Deposit(acct, -50)   ' will be caught, not fatal
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 6 — Error handling</title>
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
    .ok{color:#86efac}.err{color:#f87171}.warn{color:#fcd34d}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    .badge{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.75rem;font-weight:bold}
    .b-ok{background:#14532d;color:#86efac}.b-err{background:#450a0a;color:#f87171}
  </style>
</head>
<body>
  <h1>Demo 6 — Error handling done right</h1>
  <h2>VBScript has no Try/Catch — these are the patterns that replace it</h2>

  <h3>A. Result object — expected failures returned as data</h3>
  <div class="section">
    <pre>Set r = account.Withdraw(amount)
If r.Ok Then ... Else Response.Write r.Error</pre>
    <table>
      <tr><th>Operation</th><th>Outcome</th><th>Detail</th></tr>
      <tr><td>Withdraw €30</td>
          <td><% If w1.Ok Then %><span class="badge b-ok">OK</span><% Else %><span class="badge b-err">FAIL</span><% End If %></td>
          <td class="ok">New balance: €<%= FormatNumber(w1.Value, 2) %></td></tr>
      <tr><td>Withdraw €500</td>
          <td><% If w2.Ok Then %><span class="badge b-ok">OK</span><% Else %><span class="badge b-err">FAIL</span><% End If %></td>
          <td class="err"><%= Server.HTMLEncode(w2.Error) %></td></tr>
      <tr><td>Withdraw €-5</td>
          <td><% If w3.Ok Then %><span class="badge b-ok">OK</span><% Else %><span class="badge b-err">FAIL</span><% End If %></td>
          <td class="err"><%= Server.HTMLEncode(w3.Error) %></td></tr>
    </table>
    <p class="note">The caller never touches <code>On Error</code>. Failure is just a value to inspect.</p>
  </div>

  <h3>B. Validator — collect every error, not just the first</h3>
  <div class="section">
    <pre>val.Check(Len(username) >= 3, "...")
   .Check(InStr(email,"@") > 0, "...")
   .Check(CInt(age) >= 18, "...")</pre>
    <% If val.IsValid Then %>
      <p class="ok">✔ All checks passed.</p>
    <% Else %>
      <p class="warn"><%= val.Count %> problem(s) found:</p>
      <ul>
      <%
      Dim j
      For j = 0 To val.Count - 1
      %>
        <li class="err"><%= Server.HTMLEncode(val.ErrorAt(j)) %></li>
      <% Next %>
      </ul>
    <% End If %>
    <p class="note">A form should show users <em>all</em> mistakes at once. Stopping at the first
    is poor UX; the <code>Validator</code> accumulates them.</p>
  </div>

  <h3>C &amp; D. Scoped <code>On Error</code> + <code>Err.Raise</code> for real bugs</h3>
  <div class="section">
    <pre>On Error Resume Next     ' enabled around ONE call only
account.Deposit amount
If Err.Number &lt;&gt; 0 Then captureError()
On Error Goto 0          ' ALWAYS restored immediately</pre>
    <% If depOk Then %>
      <p class="ok">Deposit succeeded.</p>
    <% Else %>
      <p class="err">✖ Caught error #<%= runner.LastNumber %>: <%= Server.HTMLEncode(runner.LastError) %></p>
    <% End If %>
    <p class="note">A negative deposit is a <em>programmer</em> error, so <code>Deposit</code> calls
    <code>Err.Raise</code>. The <code>TryRunner</code> wraps it tightly, captures it, and then
    restores normal error halting with <code>On Error Goto 0</code> — never leaving the rest of the
    page silently swallowing errors.</p>
  </div>

  <h3>Decision guide for coding agents</h3>
  <div class="section">
    <table>
      <tr><th>Situation</th><th>Use</th></tr>
      <tr><td>Expected, recoverable failure (low balance, not found)</td><td class="ok">Return a <code>Result</code> object</td></tr>
      <tr><td>Multiple input fields to validate</td><td class="ok"><code>Validator</code> that accumulates</td></tr>
      <tr><td>Calling code that might genuinely crash (COM, DB)</td><td class="ok">Scoped <code>On Error Resume Next</code> … <code>Goto 0</code></td></tr>
      <tr><td>Impossible state / broken invariant (programmer bug)</td><td class="ok"><code>Err.Raise</code> — fail loudly</td></tr>
      <tr><td>Whole-page <code>On Error Resume Next</code> with no <code>Goto 0</code></td><td class="err">NEVER — it hides every bug</td></tr>
    </table>
  </div>

<%
Set acct = Nothing : Set w1 = Nothing : Set w2 = Nothing : Set w3 = Nothing
Set val = Nothing : Set runner = Nothing
%>
</body>
</html>
