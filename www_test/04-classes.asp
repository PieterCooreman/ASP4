<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 04-classes.asp - Object-Oriented VBScript
' Demonstrates: Class definition, private fields, Property Get/Let/Set,
' methods, the Me keyword, Class_Initialize / Class_Terminate, and
' object composition (a BankAccount holding a collection of Transactions).
' ============================================================================
Dim PageTitle : PageTitle = "Classes (OOP)"
%>
<!--#include file="includes/header.asp"-->
<%
' ----------------------------------------------------------------------------
' Class: Person
' Shows private fields, validated Property Let, read-only computed property.
' ----------------------------------------------------------------------------
Class Person
    Private m_first
    Private m_last
    Private m_age

    Private Sub Class_Initialize()
        m_first = "" : m_last = "" : m_age = 0
    End Sub

    Public Property Get FirstName() : FirstName = m_first : End Property
    Public Property Let FirstName(v) : m_first = Trim(v & "") : End Property

    Public Property Get LastName() : LastName = m_last : End Property
    Public Property Let LastName(v) : m_last = Trim(v & "") : End Property

    Public Property Get Age() : Age = m_age : End Property
    Public Property Let Age(v)
        ' Validate in the setter.
        If IsNumeric(v) And v >= 0 And v <= 150 Then
            m_age = CInt(v)
        Else
            m_age = 0
        End If
    End Property

    ' Read-only computed property using Me.
    Public Property Get FullName()
        FullName = Trim(Me.FirstName & " " & Me.LastName)
    End Property

    ' A method.
    Public Function Greeting()
        Greeting = "Hi, I'm " & Me.FullName & " and I'm " & m_age & " years old."
    End Function
End Class

' ----------------------------------------------------------------------------
' Class: BankAccount  (composition + Property Set of an object)
' ----------------------------------------------------------------------------
Class BankAccount
    Private m_owner          ' holds a Person object (set via Property Set)
    Private m_balance
    Private m_log            ' a StringBuilder of activity

    Private Sub Class_Initialize()
        m_balance = 0
        Set m_log = New StringBuilder
    End Sub

    Private Sub Class_Terminate()
        ' Demonstrates deterministic-ish cleanup.
        Set m_log = Nothing
    End Sub

    ' Property Set is used for OBJECT-valued properties.
    Public Property Set Owner(obj) : Set m_owner = obj : End Property
    Public Property Get Owner() : Set Owner = m_owner : End Property

    Public Property Get Balance() : Balance = m_balance : End Property

    Public Sub Deposit(ByVal amount)
        If amount > 0 Then
            m_balance = m_balance + amount
            m_log.AppendLine "Deposit " & FormatCurrency(amount) & " -> " & FormatCurrency(m_balance)
        End If
    End Sub

    Public Function Withdraw(ByVal amount)
        If amount > 0 And amount <= m_balance Then
            m_balance = m_balance - amount
            m_log.AppendLine "Withdraw " & FormatCurrency(amount) & " -> " & FormatCurrency(m_balance)
            Withdraw = True
        Else
            m_log.AppendLine "DECLINED withdrawal of " & FormatCurrency(amount)
            Withdraw = False
        End If
    End Function

    Public Function History()
        History = m_log.ToString()
    End Function
End Class
%>
<h1>Classes (OOP)</h1>
<p class="lead">VBScript supports real classes: private state, properties, methods and composition.</p>

<h2>The Person class</h2>
<%
DemoStart "Create a Person, set validated properties, call a method"
Dim p : Set p = New Person
p.FirstName = "Ada"
p.LastName  = "Lovelace"
p.Age       = 36
p.Age       = 999   ' rejected by the setter validation -> stays as last valid? No: set to 0

' Re-set a sensible age (the 999 above demonstrated rejection -> 0)
p.Age = 36

WriteLine "<table class=""kv"">"
RenderTableRow "FirstName",  p.FirstName
RenderTableRow "LastName",   p.LastName
RenderTableRow "FullName (computed)", p.FullName
RenderTableRow "Age",        p.Age
RenderTableRow "Greeting()", p.Greeting()
WriteLine "</table>"
DemoEnd
%>

<h2>Composition: BankAccount owns a Person</h2>
<%
DemoStart "Property Set links objects; methods mutate state"
Dim acct : Set acct = New BankAccount
Set acct.Owner = p          ' Property Set with an object

acct.Deposit 100
acct.Deposit 250.50
Dim ok1 : ok1 = acct.Withdraw(75)
Dim ok2 : ok2 = acct.Withdraw(99999)   ' will be declined

WriteLine "<p>Owner: <strong>" & HtmlEncode(acct.Owner.FullName) & "</strong></p>"
WriteLine "<p>Final balance: <strong>" & HtmlEncode(FormatCurrency(acct.Balance)) & "</strong></p>"
WriteLine "<p>Last withdrawal accepted? <strong>" & ok1 & "</strong> / Oversized accepted? <strong>" & ok2 & "</strong></p>"
WriteLine "<h3>Transaction log</h3>"
WriteLine "<pre class=""code""><code>" & HtmlEncode(acct.History()) & "</code></pre>"
DemoEnd

Set acct = Nothing   ' triggers Class_Terminate
Set p = Nothing
%>

<h2>Lifecycle hooks</h2>
<p>
  <code>Class_Initialize</code> runs on <code>New</code>;
  <code>Class_Terminate</code> runs when the object is set to <code>Nothing</code>
  or goes out of scope. The <code>BankAccount</code> above uses both.
</p>
<!--#include file="includes/footer.asp"-->
