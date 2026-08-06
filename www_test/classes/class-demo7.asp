<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 7 — Polymorphism without inheritance
'
'  CRITICAL FACT: VBScript classes do NOT support inheritance.
'  There is no  Class Dog Extends Animal.  There are no
'  interfaces, no virtual methods, no MustInherit.
'
'  Yet polymorphism is still achievable via DUCK TYPING:
'  "if it has a .Area() method, I can treat it as a shape."
'  As long as every object exposes the same method NAMES with
'  the same SIGNATURE, calling code can treat them uniformly.
'
'  This demo shows:
'    1. Several shape classes sharing an implicit "interface"
'       (Area, Perimeter, Name) — no base class required.
'    2. A function that consumes ANY of them polymorphically.
'    3. The STRATEGY pattern: interchangeable algorithm objects
'       (tax strategies) selected at runtime.
'    4. How to share common code WITHOUT inheritance, using
'       COMPOSITION (a helper object) instead.
' ============================================================


' ============================================================
' The implicit "IShape interface":
'    Public Property Get Name()
'    Public Function Area()
'    Public Function Perimeter()
' Every shape below honours this contract by CONVENTION.
' VBScript will not enforce it — discipline + tests do.
' ============================================================

Class Circle
    Private m_r
    Public Property Let Radius(v) : m_r = CDbl(v) : End Property
    Public Property Get Name()      : Name      = "Circle"            : End Property
    Public Function Area()          : Area      = 3.14159265 * m_r * m_r : End Function
    Public Function Perimeter()     : Perimeter = 2 * 3.14159265 * m_r : End Function
End Class

Class Rectangle
    Private m_w, m_h
    Public Sub Init(w, h) : m_w = CDbl(w) : m_h = CDbl(h) : End Sub
    Public Property Get Name()      : Name      = "Rectangle"         : End Property
    Public Function Area()          : Area      = m_w * m_h           : End Function
    Public Function Perimeter()     : Perimeter = 2 * (m_w + m_h)     : End Function
End Class

Class Triangle
    Private m_a, m_b, m_c
    Public Sub Init(a, b, c) : m_a = CDbl(a) : m_b = CDbl(b) : m_c = CDbl(c) : End Sub
    Public Property Get Name()  : Name = "Triangle" : End Property
    Public Function Perimeter() : Perimeter = m_a + m_b + m_c : End Function
    Public Function Area()       ' Heron's formula
        Dim s : s = (m_a + m_b + m_c) / 2
        Area = Sqr(s * (s - m_a) * (s - m_b) * (s - m_c))
    End Function
End Class


' ============================================================
' Polymorphic consumer.
' It does NOT care which concrete class it receives — only
' that the object responds to .Name, .Area and .Perimeter.
' This is the whole point: one function, many shape types.
' ============================================================
Function DescribeShape(shape)
    DescribeShape = shape.Name & " — area " & FormatNumber(shape.Area(), 2) & _
                    ", perimeter " & FormatNumber(shape.Perimeter(), 2)
End Function

' A defensive helper: confirm an object "quacks" like a shape
' before trusting it (TypeName / duck-test). Useful at boundaries.
Function LooksLikeShape(obj)
    On Error Resume Next
    Dim probe : probe = obj.Area()      ' will error if no Area method
    LooksLikeShape = (Err.Number = 0)
    On Error Goto 0
End Function


' ============================================================
' STRATEGY PATTERN
' Interchangeable algorithm objects. Each tax strategy exposes
' the same Calculate(amount) method. The Invoice picks one at
' runtime and never knows which concrete rule it holds.
' ============================================================
Class StandardVAT
    Public Property Get Name() : Name = "Standard VAT 21%" : End Property
    Public Function Calculate(amount) : Calculate = amount * 0.21 : End Function
End Class

Class ReducedVAT
    Public Property Get Name() : Name = "Reduced VAT 6%" : End Property
    Public Function Calculate(amount) : Calculate = amount * 0.06 : End Function
End Class

Class TaxExempt
    Public Property Get Name() : Name = "Tax exempt" : End Property
    Public Function Calculate(amount) : Calculate = 0 : End Function
End Class

Class Invoice
    Private m_net
    Private m_taxStrategy        ' ANY object with .Calculate / .Name

    Public Property Let Net(v) : m_net = CDbl(v) : End Property

    ' Inject a strategy object — swap behaviour without subclassing.
    Public Property Set TaxStrategy(obj) : Set m_taxStrategy = obj : End Property

    Public Function TaxName()  : TaxName  = m_taxStrategy.Name              : End Function
    Public Function TaxAmount(): TaxAmount = m_taxStrategy.Calculate(m_net) : End Function
    Public Function Total()    : Total    = m_net + TaxAmount()            : End Function
End Class


' ============================================================
'  USAGE
' ============================================================

' --- Polymorphism over a mixed array of shapes ---
Dim shapes(2)

Dim c : Set c = New Circle : c.Radius = 5
Set shapes(0) = c

Dim r : Set r = New Rectangle : r.Init 4, 6
Set shapes(1) = r

Dim t : Set t = New Triangle : t.Init 3, 4, 5
Set shapes(2) = t

Dim totalArea : totalArea = 0
Dim k
For k = 0 To UBound(shapes)
    totalArea = totalArea + shapes(k).Area()   ' same call, different class
Next

' --- Strategy: three invoices, same Net, different tax rule ---
Dim inv1 : Set inv1 = New Invoice : inv1.Net = 100
Dim s1 : Set s1 = New StandardVAT : Set inv1.TaxStrategy = s1

Dim inv2 : Set inv2 = New Invoice : inv2.Net = 100
Dim s2 : Set s2 = New ReducedVAT  : Set inv2.TaxStrategy = s2

Dim inv3 : Set inv3 = New Invoice : inv3.Net = 100
Dim s3 : Set s3 = New TaxExempt   : Set inv3.TaxStrategy = s3
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 7 — Polymorphism &amp; strategy</title>
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
    .v{color:#86efac}.k{color:#7dd3fc}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
  </style>
</head>
<body>
  <h1>Demo 7 — Polymorphism without inheritance</h1>
  <h2>VBScript has no base classes or interfaces — duck typing &amp; strategy fill the gap</h2>

  <h3>1. One function, many shape classes (duck typing)</h3>
  <div class="section">
    <pre>For k = 0 To UBound(shapes)
    total = total + shapes(k).Area()   ' Circle, Rectangle, Triangle — same call
Next</pre>
    <table>
      <tr><th>Shape</th><th>Description (via DescribeShape)</th></tr>
      <% For k = 0 To UBound(shapes) %>
        <tr><td class="k"><%= shapes(k).Name %></td>
            <td class="v"><%= Server.HTMLEncode(DescribeShape(shapes(k))) %></td></tr>
      <% Next %>
      <tr><td class="k"><strong>Total area</strong></td>
          <td class="v"><strong><%= FormatNumber(totalArea, 2) %></strong></td></tr>
    </table>
    <p class="note">No <code>Shape</code> base class exists. Each class independently exposes
    <code>Name</code>, <code>Area</code>, <code>Perimeter</code> — that shared shape <em>by convention</em>
    is the "interface". <code>DescribeShape</code> works on all of them.</p>
  </div>

  <h3>2. Strategy pattern — swap the algorithm, keep the object</h3>
  <div class="section">
    <pre>Set invoice.TaxStrategy = New StandardVAT   ' or ReducedVAT, or TaxExempt</pre>
    <table>
      <tr><th>Net</th><th>Tax strategy</th><th>Tax</th><th>Total</th></tr>
      <tr><td>€100.00</td><td class="k"><%= inv1.TaxName() %></td>
          <td class="v">€<%= FormatNumber(inv1.TaxAmount(), 2) %></td>
          <td class="v">€<%= FormatNumber(inv1.Total(), 2) %></td></tr>
      <tr><td>€100.00</td><td class="k"><%= inv2.TaxName() %></td>
          <td class="v">€<%= FormatNumber(inv2.TaxAmount(), 2) %></td>
          <td class="v">€<%= FormatNumber(inv2.Total(), 2) %></td></tr>
      <tr><td>€100.00</td><td class="k"><%= inv3.TaxName() %></td>
          <td class="v">€<%= FormatNumber(inv3.TaxAmount(), 2) %></td>
          <td class="v">€<%= FormatNumber(inv3.Total(), 2) %></td></tr>
    </table>
    <p class="note">The <code>Invoice</code> class never contains an <code>If taxType = ...</code> ladder.
    To add a new tax rule, write a new class with a <code>Calculate</code> method — <code>Invoice</code>
    stays untouched (Open/Closed principle).</p>
  </div>

  <h3>Rules for coding agents</h3>
  <div class="section">
    <table>
      <tr><th>Want</th><th>In VBScript, do this</th></tr>
      <tr><td>Shared behaviour across types</td><td class="v">Give each class the SAME method names (duck typing)</td></tr>
      <tr><td>Code reuse / a "base class"</td><td class="v">Use COMPOSITION: hold a helper object, delegate to it</td></tr>
      <tr><td>Interchangeable algorithms</td><td class="v">Strategy pattern: inject an object via <code>Property Set</code></td></tr>
      <tr><td>Verify an object honours a contract</td><td class="v">Duck-test with <code>On Error Resume Next</code> + a probe call</td></tr>
      <tr><td>Real inheritance (Extends/virtual)</td><td class="v">Not available — don't generate it; restructure instead</td></tr>
    </table>
  </div>

<%
Dim z
For z = 0 To UBound(shapes) : Set shapes(z) = Nothing : Next
Set inv1 = Nothing : Set inv2 = Nothing : Set inv3 = Nothing
Set s1 = Nothing : Set s2 = Nothing : Set s3 = Nothing
%>
</body>
</html>
