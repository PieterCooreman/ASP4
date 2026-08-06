<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 1 — Order Management System
'
'  THE FLAGSHIP EXAMPLE: six small classes cooperating to do
'  one real job — turn a product catalogue + a customer into a
'  priced, VAT-inclusive invoice — while logging every step.
'
'  This is the example to imitate when an LLM is asked to build
'  a non-trivial Classic ASP feature. It demonstrates, together,
'  every core technique that makes class-based VBScript robust:
'
'    1. ENCAPSULATION   — each object owns its own state; no
'                         global variables, no parallel arrays.
'    2. VALIDATION at the boundary — Property Let rejects bad
'                         values with Err.Raise, so an object
'                         can never hold an invalid value.
'    3. DEPENDENCY INJECTION — Order receives a Logger and a
'                         Discount from outside (SetLogger /
'                         SetDiscount); it never creates them.
'    4. SINGLE RESPONSIBILITY — Order calculates, Discount
'                         decides the rule, InvoiceRenderer
'                         formats HTML, Logger logs. One job each.
'    5. LIFECYCLE — Class_Initialize sets defaults; Class_
'                         Terminate releases child objects.
'
'  KEY VBSCRIPT FACTS shown here (LLMs frequently miss these):
'    • Class_Initialize() takes NO arguments. To pass start-up
'      data, use an Init()/SetXxx method AFTER  New.
'    • Object assignment ALWAYS needs Set (Set m_log = logObj).
'    • A Property Get that RETURNS an object must use Set too
'      (Set GetLine = m_lines(i)).
'    • To test for "no object", use  If obj Is Nothing.
' ============================================================


' ============================================================
' CLASS 1 — Logger
' Centralises all output/logging so business classes never
' touch presentation. Supports log levels (INFO/WARN/ERROR).
' One shared Logger is injected into every Order, producing a
' single unified log — something global Subs cannot do cleanly.
' ============================================================
Class Logger
  Private m_entries     ' array of raw log lines (for the count)
  Private m_html        ' pre-rendered HTML for display

  ' Class_Initialize runs automatically on  New Logger.
  ' It CANNOT take parameters — initialise defaults only.
  Private Sub Class_Initialize()
    m_entries = Array()
    m_html = ""
  End Sub

  ' Add a log entry. level is "INFO" | "WARN" | "ERROR".
  Public Sub Log(level, msg)
    Dim entry
    entry = Now() & " [" & level & "] " & msg
    ' Grow the backing array by one and store the new line.
    ReDim Preserve m_entries(UBound(m_entries) + 1)
    m_entries(UBound(m_entries)) = entry

    Select Case UCase(level)
      Case "WARN"  : m_html = m_html & "<div class='warn'>&#9888; " & Server.HTMLEncode(msg) & "</div>"
      Case "ERROR" : m_html = m_html & "<div class='error'>&#10006; " & Server.HTMLEncode(msg) & "</div>"
      Case Else    : m_html = m_html & "<div class='value'>&#10004; " & Server.HTMLEncode(msg) & "</div>"
    End Select
  End Sub

  Public Function GetHTML()  : GetHTML  = m_html               : End Function
  Public Function GetCount() : GetCount = UBound(m_entries) + 1 : End Function

  Private Sub Class_Terminate()
    Erase m_entries
  End Sub
End Class


' ============================================================
' CLASS 2 — Product
' A single catalogue item. Every setter VALIDATES via Err.Raise,
' so the object can never hold an empty name or a negative price.
' Without a class you'd track id/name/price/stock in four
' separate parallel arrays — fragile and easy to desynchronise.
' ============================================================
Class Product
  Private m_id
  Private m_name
  Private m_price
  Private m_stock

  ' Read accessors (scalars → Property Get).
  Public Property Get ID()    : ID    = m_id    : End Property
  Public Property Get Name()  : Name  = m_name  : End Property
  Public Property Get Price() : Price = m_price : End Property
  Public Property Get Stock() : Stock = m_stock : End Property

  ' Write accessors validate FIRST, then store. Because the rule
  ' lives here, EVERY caller is protected automatically.
  Public Property Let ID(v)
    If Len(Trim(v)) = 0 Then Err.Raise 1001, "Product", "ID cannot be empty"
    m_id = Trim(v)
  End Property

  Public Property Let Name(v)
    If Len(Trim(v)) = 0 Then Err.Raise 1002, "Product", "Name cannot be empty"
    m_name = Trim(v)
  End Property

  Public Property Let Price(v)
    If Not IsNumeric(v) Or CDbl(v) < 0 Then Err.Raise 1003, "Product", "Invalid price: " & v
    m_price = CDbl(v)
  End Property

  Public Property Let Stock(v)
    If Not IsNumeric(v) Or CInt(v) < 0 Then Err.Raise 1004, "Product", "Invalid stock: " & v
    m_stock = CInt(v)
  End Property

  ' Behaviour lives WITH the data: reserving stock is the
  ' Product's own responsibility. Returns False if not enough.
  Public Function Reserve(qty)
    If qty > m_stock Then
      Reserve = False
    Else
      m_stock = m_stock - qty
      Reserve = True
    End If
  End Function

  Public Function Summary()
    Summary = m_name & " (€" & FormatNumber(m_price, 2) & ") — stock: " & m_stock
  End Function
End Class


' ============================================================
' CLASS 3 — OrderLine
' One line within an order: a REFERENCE to a Product plus a
' quantity. It encapsulates the line-total calculation so the
' Order never repeats price × qty arithmetic.
'
' NOTE: m_product holds an OBJECT, so it is assigned with Set
' (inside Init) and released with Set ... = Nothing on terminate.
' ============================================================
Class OrderLine
  Private m_product   ' a Product object (held by reference)
  Private m_qty

  ' VBScript constructors take no args, so we expose Init().
  Public Sub Init(prod, qty)
    Set m_product = prod          ' Set: prod is an object
    m_qty = CInt(qty)
  End Sub

  Public Property Get ProductName() : ProductName = m_product.Name  : End Property
  Public Property Get UnitPrice()   : UnitPrice   = m_product.Price : End Property
  Public Property Get Qty()         : Qty         = m_qty           : End Property

  Public Property Get LineTotal()
    LineTotal = m_product.Price * m_qty
  End Property

  Private Sub Class_Terminate()
    Set m_product = Nothing       ' release the reference
  End Sub
End Class


' ============================================================
' CLASS 4 — Discount
' A swappable pricing RULE (a mini Strategy). The same Order
' works with a PERCENT rule, a FIXED rule, or none — without
' any change to Order itself. Add a new rule here, not there.
' ============================================================
Class Discount
  Private m_type      ' "PERCENT" | "FIXED" | "NONE"
  Private m_value

  Public Sub SetRule(discType, discValue)
    m_type  = UCase(discType)
    m_value = CDbl(discValue)
  End Sub

  Public Function Apply(subtotal)
    Select Case m_type
      Case "PERCENT"
        Apply = subtotal * (m_value / 100)
      Case "FIXED"
        If m_value > subtotal Then Apply = subtotal Else Apply = m_value
      Case Else
        Apply = 0
    End Select
  End Function

  Public Function Description()
    Select Case m_type
      Case "PERCENT" : Description = m_value & "% off"
      Case "FIXED"   : Description = "€" & FormatNumber(m_value, 2) & " off"
      Case Else      : Description = "no discount"
    End Select
  End Function
End Class


' ============================================================
' CLASS 5 — Order
' The central business object. It AGGREGATES OrderLines, applies
' an injected Discount, holds customer info, and computes the
' money (subtotal → discount → net → VAT → grand total).
'
' Dependency injection: SetLogger / SetDiscount receive objects
' from outside. Order never calls New on them, so you can pass a
' different Logger or Discount (or none) without editing Order.
' ============================================================
Class Order
  Private m_id
  Private m_customer
  Private m_lines()       ' array of OrderLine objects
  Private m_lineCount
  Private m_discount      ' injected Discount object
  Private m_log           ' injected Logger object
  Private m_vat           ' VAT rate as a fraction (0.21 = 21%)

  Private Sub Class_Initialize()
    m_lineCount = 0
    ReDim m_lines(0)
    m_vat = 0.21
  End Sub

  ' --- dependency injection (objects → use Set) ---
  Public Sub SetLogger(logObj)    : Set m_log      = logObj  : End Sub
  Public Sub SetDiscount(discObj) : Set m_discount = discObj : End Sub

  Public Property Let OrderID(v)  : m_id       = v       : End Property
  Public Property Let Customer(v) : m_customer = v       : End Property
  Public Property Let VATRate(v)  : m_vat      = CDbl(v) : End Property
  Public Property Get OrderID()   : OrderID    = m_id       : End Property
  Public Property Get Customer()  : Customer   = m_customer : End Property

  ' Add a line. Reserving stock can FAIL — that is an expected
  ' outcome, so we log a WARN and return False (no exception).
  Public Function AddLine(prod, qty)
    If Not prod.Reserve(qty) Then
      m_log.Log "WARN", "Insufficient stock for """ & prod.Name & """ (requested: " & qty & ")"
      AddLine = False
      Exit Function
    End If

    Dim line : Set line = New OrderLine
    line.Init prod, qty

    If m_lineCount >= UBound(m_lines) + 1 Then
      ReDim Preserve m_lines(m_lineCount)
    End If
    Set m_lines(m_lineCount) = line     ' Set: storing an object
    m_lineCount = m_lineCount + 1

    m_log.Log "INFO", "Added " & qty & "× """ & prod.Name & """ to order"
    AddLine = True
  End Function

  ' Computed properties — derived on demand, never stored stale.
  Public Property Get Subtotal()
    Dim s : s = 0
    Dim i
    For i = 0 To m_lineCount - 1
      s = s + m_lines(i).LineTotal
    Next
    Subtotal = s
  End Property

  Public Property Get DiscountAmount()
    ' IsObject guards the optional dependency: no Discount → 0.
    If IsObject(m_discount) Then
      DiscountAmount = m_discount.Apply(Subtotal)
    Else
      DiscountAmount = 0
    End If
  End Property

  Public Property Get NetTotal()    : NetTotal    = Subtotal - DiscountAmount : End Property
  Public Property Get VATAmount()   : VATAmount   = NetTotal * m_vat          : End Property
  Public Property Get GrandTotal()  : GrandTotal  = NetTotal + VATAmount      : End Property
  Public Property Get LineCount()   : LineCount   = m_lineCount               : End Property

  ' Returns an OBJECT → caller must use  Set ln = order.GetLine(i)
  Public Function GetLine(i)
    Set GetLine = m_lines(i)
  End Function

  Private Sub Class_Terminate()
    Dim i
    For i = 0 To m_lineCount - 1 : Set m_lines(i) = Nothing : Next
    Set m_log      = Nothing
    Set m_discount = Nothing
  End Sub
End Class


' ============================================================
' CLASS 6 — InvoiceRenderer
' PURE PRESENTATION. It knows nothing about business rules — it
' only reads an Order and emits an HTML table. Keeping formatting
' out of Order means you can add a PDF/JSON renderer later
' without touching a single line of business logic.
' ============================================================
Class InvoiceRenderer
  Public Function Render(order, discObj)
    Dim html : html = ""
    html = html & "<table>"
    html = html & "<tr><th>Product</th><th>Unit price</th><th>Qty</th><th>Line total</th></tr>"

    Dim i
    For i = 0 To order.LineCount - 1
      Dim ln : Set ln = order.GetLine(i)      ' object → Set
      html = html & "<tr>"
      html = html & "<td>" & Server.HTMLEncode(ln.ProductName) & "</td>"
      html = html & "<td>€" & FormatNumber(ln.UnitPrice, 2) & "</td>"
      html = html & "<td>" & ln.Qty & "</td>"
      html = html & "<td class='highlight'>€" & FormatNumber(ln.LineTotal, 2) & "</td>"
      html = html & "</tr>"
    Next

    html = html & "<tr><td colspan='3' class='label'>Subtotal</td><td>€" & FormatNumber(order.Subtotal, 2) & "</td></tr>"

    ' Optional dependency check: only show a discount row if given one.
    If Not discObj Is Nothing Then
      html = html & "<tr><td colspan='3' class='label'>Discount (" & discObj.Description() & ")</td>"
      html = html & "<td class='warn'>&ndash;€" & FormatNumber(order.DiscountAmount, 2) & "</td></tr>"
    End If

    html = html & "<tr><td colspan='3' class='label'>VAT (21%)</td><td>€" & FormatNumber(order.VATAmount, 2) & "</td></tr>"
    html = html & "<tr class='total-row'><td colspan='3'><strong>Grand total</strong></td>"
    html = html & "<td><strong>€" & FormatNumber(order.GrandTotal, 2) & "</strong></td></tr>"
    html = html & "</table>"
    Render = html
  End Function
End Class


' ============================================================
'  BOOTSTRAP — wire the classes together (the "composition root")
'  Everything below just CONSTRUCTS and CONNECTS objects. Note
'  how readable this is: each class does its job, the wiring
'  reads like a sentence.
' ============================================================

' --- shared services ---
Dim log : Set log = New Logger
log.Log "INFO", "Application started"

' --- product catalogue (in real life: loaded from a database) ---
Dim pA : Set pA = New Product
pA.ID = "P001" : pA.Name = "Mechanical Keyboard" : pA.Price = 129.99 : pA.Stock = 5

Dim pB : Set pB = New Product
pB.ID = "P002" : pB.Name = "USB-C Hub (7-port)" : pB.Price = 49.95 : pB.Stock = 3

Dim pC : Set pC = New Product
pC.ID = "P003" : pC.Name = "27&#8243; IPS Monitor" : pC.Price = 379.00 : pC.Stock = 1

Dim pD : Set pD = New Product
pD.ID = "P004" : pD.Name = "Webcam HD 1080p" : pD.Price = 89.50 : pD.Stock = 2

log.Log "INFO", "Product catalogue loaded (4 products)"

' --- a discount rule (injected into order 1 only) ---
Dim disc : Set disc = New Discount
disc.SetRule "PERCENT", 10   ' 10% loyalty discount

' --- order #1 (with logger + discount injected) ---
Dim ord1 : Set ord1 = New Order
ord1.OrderID  = "ORD-2024-001"
ord1.Customer = "Lena Vandenberghe"
ord1.SetLogger log
ord1.SetDiscount disc

ord1.AddLine pA, 2   ' succeeds
ord1.AddLine pB, 3   ' succeeds (exact stock)
ord1.AddLine pC, 1   ' succeeds
ord1.AddLine pD, 5   ' FAILS — only 2 webcams in stock (logged as WARN)

' --- order #2 (same logger, NO discount, different customer) ---
Dim ord2 : Set ord2 = New Order
ord2.OrderID  = "ORD-2024-002"
ord2.Customer = "Mathis De Smedt"
ord2.SetLogger log
' SetDiscount NOT called → DiscountAmount returns 0 automatically

ord2.AddLine pD, 2   ' succeeds (remaining webcams)
ord2.AddLine pC, 1   ' FAILS — monitor already reserved by ord1

Dim renderer : Set renderer = New InvoiceRenderer
log.Log "INFO", "Rendering complete"
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 1 — Order Management System</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    .label{color:#94a3b8;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em}
    .value{color:#f0fdf4}.highlight{color:#86efac}.warn{color:#fcd34d}.error{color:#f87171}.k{color:#7dd3fc}
    .tag{display:inline-block;background:#1e3a5f;color:#7dd3fc;border-radius:3px;padding:0 6px;font-size:.78rem;margin-right:4px}
    table{width:100%;border-collapse:collapse;font-size:.9rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035}
    tr:last-child td{border-bottom:none}
    .total-row td{color:#86efac;border-top:1px solid #2d3748}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
  </style>
</head>
<body>
  <h1>Demo 1 — Order Management System</h1>
  <h2>Six cooperating classes: encapsulation · validation · dependency injection · single responsibility</h2>

  <h3>The six classes in this file</h3>
  <div class="section">
    <span class="tag">Logger</span>
    <span class="tag">Product</span>
    <span class="tag">OrderLine</span>
    <span class="tag">Discount</span>
    <span class="tag">Order</span>
    <span class="tag">InvoiceRenderer</span>
    <p class="note">Each has ONE job. <code>Order</code> receives a <code>Logger</code> and a
    <code>Discount</code> by injection — it never creates them. <code>InvoiceRenderer</code> only
    formats and contains zero business logic. That separation is what makes the code changeable.</p>
    <pre>Set ord1 = New Order
ord1.SetLogger log        ' inject the shared logger (Set, an object)
ord1.SetDiscount disc     ' inject a pricing rule
ord1.AddLine pA, 2        ' Product.Reserve() runs; OrderLine created</pre>
  </div>

  <h3>Order #1 — <%= Server.HTMLEncode(ord1.Customer) %>
      <small style="color:#64748b;font-size:.8rem">(<%= Server.HTMLEncode(ord1.OrderID) %>)</small></h3>
  <div class="section">
    <%= renderer.Render(ord1, disc) %>
    <p class="note">A 10% <code>Discount</code> object was injected, so the renderer shows a discount row.</p>
  </div>

  <h3>Order #2 — <%= Server.HTMLEncode(ord2.Customer) %>
      <small style="color:#64748b;font-size:.8rem">(<%= Server.HTMLEncode(ord2.OrderID) %>)</small></h3>
  <div class="section">
    <%= renderer.Render(ord2, Nothing) %>
    <p class="note">No <code>Discount</code> was injected; <code>DiscountAmount</code> returns 0 thanks to
    the <code>IsObject(m_discount)</code> guard — no special-casing in the caller.</p>
  </div>

  <h3>Product stock AFTER processing both orders</h3>
  <div class="section">
    <table>
      <tr><th>ID</th><th>Product</th><th>Remaining stock</th></tr>
      <tr><td class="k"><%= pA.ID %></td><td><%= pA.Name %></td><td><%= pA.Stock %></td></tr>
      <tr><td class="k"><%= pB.ID %></td><td><%= pB.Name %></td><td><%= pB.Stock %></td></tr>
      <tr><td class="k"><%= pC.ID %></td><td><%= pC.Name %></td><td><%= pC.Stock %></td></tr>
      <tr><td class="k"><%= pD.ID %></td><td><%= pD.Name %></td><td><%= pD.Stock %></td></tr>
    </table>
    <p class="note">Stock lives INSIDE each <code>Product</code> and only changes through
    <code>Reserve()</code>. The Order can't accidentally corrupt it — that is encapsulation.</p>
  </div>

  <h3>Unified application log (<%= log.GetCount() %> entries)</h3>
  <div class="section">
    <%= log.GetHTML() %>
    <p class="note">ONE <code>Logger</code> instance was injected into BOTH orders, so every event lands
    in a single log. Achieving this with global Subs would mean shared global state and naming clashes.</p>
  </div>

  <h3>Why classes instead of plain Subs &amp; Functions?</h3>
  <div class="section">
    <table>
      <tr><th style="width:24%">Concern</th><th>Without classes</th><th>With classes</th></tr>
      <tr><td class="k">State</td><td>Parallel arrays / globals, easy to desynchronise</td><td>Each object owns its state; no name collisions</td></tr>
      <tr><td class="k">Validation</td><td>Repeated <code>If</code> guards in every Sub that touches a value</td><td>Centralised in <code>Property Let</code> — one place</td></tr>
      <tr><td class="k">Reuse</td><td>Copy-paste; a second order means duplicating all variables</td><td><code>Set ord2 = New Order</code> — done</td></tr>
      <tr><td class="k">Dependency injection</td><td>Global logger/discount, hard to swap or test</td><td><code>SetLogger</code>/<code>SetDiscount</code> — pass any compatible object</td></tr>
      <tr><td class="k">Single responsibility</td><td>One giant Sub calculating AND formatting AND logging</td><td>Order calculates · Renderer formats · Logger logs</td></tr>
      <tr><td class="k">Cleanup</td><td>Manual <code>Nothing</code> assignments scattered everywhere</td><td><code>Class_Terminate</code> handles it</td></tr>
    </table>
  </div>

  <h3>Rules for coding agents (takeaways from this demo)</h3>
  <div class="section">
    <table>
      <tr><th>Situation</th><th>Do this in VBScript</th></tr>
      <tr><td>Need start-up data in a class</td><td class="value"><code>Class_Initialize</code> takes no args — add an <code>Init()</code>/<code>SetXxx</code> method</td></tr>
      <tr><td>Assign or return an object</td><td class="value">Always use <code>Set</code> (incl. object-returning <code>Property Get</code>)</td></tr>
      <tr><td>Protect a value from bad input</td><td class="value">Validate in <code>Property Let</code> and <code>Err.Raise</code> on failure</td></tr>
      <tr><td>A collaborator (logger, rule, repo)</td><td class="value">Inject it (<code>SetLogger</code>); don't <code>New</code> it inside</td></tr>
      <tr><td>Optional dependency might be absent</td><td class="value">Guard with <code>IsObject(...)</code> or <code>If x Is Nothing</code></td></tr>
      <tr><td>Mixing calculation with HTML</td><td class="value">Split it: a calculator class + a renderer class</td></tr>
      <tr><td>User text written into HTML</td><td class="value">Wrap in <code>Server.HTMLEncode()</code></td></tr>
    </table>
  </div>

<%
' --- cleanup: release every object (Class_Terminate then fires) ---
Set log = Nothing
Set pA = Nothing : Set pB = Nothing : Set pC = Nothing : Set pD = Nothing
Set disc = Nothing
Set ord1 = Nothing : Set ord2 = Nothing
Set renderer = Nothing
%>
</body>
</html>
