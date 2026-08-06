<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 3 — Layered services & a shopping cart
'
'  A small but realistic SERVICE-LAYER architecture. Several
'  single-purpose classes are wired together so that high-level
'  code (OrderService.CreateOrder) reads like plain English and
'  knows nothing about HOW logging, e-mail or totals happen.
'
'  Layers (each a class with one job):
'    • Logger        — write status lines
'    • Customer      — a data record (id/name/email)
'    • Product       — a data record (id/name/price)
'    • ShoppingCart  — a COLLECTION built on Scripting.Dictionary
'                      that tracks product + quantity per line
'    • EmailService  — sends a confirmation (stubbed)
'    • OrderService  — ORCHESTRATES the others via injection
'
'  KEY VBSCRIPT FACTS shown here (LLMs frequently miss these):
'    • Scripting.Dictionary is the idiomatic associative map in
'      Classic ASP. Create it with Server.CreateObject(...).
'    • To store an OBJECT as a Dictionary value you MUST use Set:
'        Set dict(key) = obj        ' object value  → Set
'        dict(key) = 123            ' scalar value  → no Set
'      Getting this wrong throws "Object doesn't support this
'      property or method" / type-mismatch at runtime.
'    • A Dictionary can hold OTHER Dictionaries — here each cart
'      line is itself a small Dictionary {"Product":obj,"Qty":n}.
'    • Inject collaborators via a Configure()/SetXxx method;
'      a class should not New its own dependencies.
'    • Release the Dictionary in Class_Terminate (Set = Nothing).
' ============================================================


' ============================================================
' Logger — the only class allowed to talk about presentation.
' (Method is named LogError, NOT Error: "Error" collides with
'  the built-in Err.Error and is a poor member name in VBScript.)
' ============================================================
Class Logger
    Private p_html

    Private Sub Class_Initialize() : p_html = "" : End Sub

    Public Sub Info(message)
        p_html = p_html & "<div class='value'>&#10004; " & Server.HTMLEncode(message) & "</div>"
    End Sub

    Public Sub LogError(message)
        p_html = p_html & "<div class='error'>&#10006; " & Server.HTMLEncode(message) & "</div>"
    End Sub

    Public Function GetHTML() : GetHTML = p_html : End Function
End Class


' ============================================================
' Customer — a plain data record (a "DTO"/entity). Property
' Get/Let pairs give controlled access; GetDisplayName is a tiny
' behaviour that belongs with the data.
' ============================================================
Class Customer
    Private mID, mName, mEmail

    Public Property Let ID(value)    : mID = value    : End Property
    Public Property Get ID()         : ID = mID       : End Property
    Public Property Let Name(value)  : mName = value  : End Property
    Public Property Get Name()       : Name = mName   : End Property
    Public Property Let Email(value) : mEmail = value : End Property
    Public Property Get Email()      : Email = mEmail : End Property

    Public Function GetDisplayName()
        GetDisplayName = mName & " (" & mEmail & ")"
    End Function
End Class


' ============================================================
' Product — a data record. Price is coerced to a number in its
' setter (CDbl) so totals never accidentally do string concat.
' ============================================================
Class Product
    Private mID, mName, mPrice

    Public Property Let ID(value)   : mID = value         : End Property
    Public Property Get ID()        : ID = mID            : End Property
    Public Property Let Name(value) : mName = value       : End Property
    Public Property Get Name()      : Name = mName        : End Property
    Public Property Let Price(value): mPrice = CDbl(value): End Property
    Public Property Get Price()     : Price = mPrice      : End Property
End Class


' ============================================================
' ShoppingCart — a COLLECTION class built on a Dictionary keyed
' by product ID. Each VALUE is itself a small Dictionary holding
' the Product object and the quantity. Adding the same product
' twice increments Qty instead of duplicating the line.
' ============================================================
Class ShoppingCart
    Private mItems     ' Scripting.Dictionary: key = product ID

    Private Sub Class_Initialize()
        Set mItems = Server.CreateObject("Scripting.Dictionary")
    End Sub
    Private Sub Class_Terminate()
        Set mItems = Nothing     ' release the COM object
    End Sub

    Public Sub AddProduct(product)
        Dim key : key = product.ID

        If mItems.Exists(key) Then
            ' Qty is a SCALAR value → assigned WITHOUT Set.
            mItems(key)("Qty") = mItems(key)("Qty") + 1
        Else
            Dim item
            Set item = Server.CreateObject("Scripting.Dictionary")
            Set item("Product") = product   ' OBJECT value  → Set
            item("Qty") = 1                  ' SCALAR value  → no Set
            Set mItems(key) = item           ' store the line Dictionary → Set
        End If
    End Sub

    Public Function GetTotal()
        Dim total, key : total = 0
        For Each key In mItems.Keys
            total = total + (mItems(key)("Product").Price * mItems(key)("Qty"))
        Next
        GetTotal = total
    End Function

    Public Function LineCount() : LineCount = mItems.Count : End Function

    ' Expose the underlying Dictionary so a view can iterate it.
    Public Function GetItems() : Set GetItems = mItems : End Function
End Class


' ============================================================
' EmailService — a stubbed side-effect. In production this would
' call a mail component (CDO/SMTP). Isolating it behind a class
' means OrderService doesn't care how mail is actually sent.
' ============================================================
Class EmailService
    Public LastMessage     ' captured so the view can show it

    Public Sub SendOrderConfirmation(customer, amount)
        LastMessage = "Sending email to " & customer.Email & _
                      " for order total €" & FormatNumber(amount, 2)
    End Sub
End Class


' ============================================================
' OrderService — the ORCHESTRATOR. It owns no data; it receives
' a Logger and an EmailService via Configure() (dependency
' injection) and coordinates them. CreateOrder reads like the
' business process it represents.
' ============================================================
Class OrderService
    Private mLogger
    Private mEmailService

    ' Inject collaborators (both objects → Set).
    Public Sub Configure(objLogger, emailService)
        Set mLogger = objLogger
        Set mEmailService = emailService
    End Sub

    Public Function CreateOrder(customer, cart)
        Dim total : total = cart.GetTotal()
        mLogger.Info "Creating order for " & customer.Name
        mEmailService.SendOrderConfirmation customer, total
        mLogger.Info "Order total = €" & FormatNumber(total, 2)
        CreateOrder = total
    End Function
End Class


' ============================================================
'  BOOTSTRAP — the composition root: build & wire everything.
' ============================================================

' --- shared services ---
Dim objLogger   : Set objLogger   = New Logger
Dim objEmailSvc : Set objEmailSvc = New EmailService
Dim objOrderSvc : Set objOrderSvc = New OrderService
objOrderSvc.Configure objLogger, objEmailSvc   ' inject dependencies

' --- a customer ---
Dim objCustomer : Set objCustomer = New Customer
objCustomer.ID = 1001
objCustomer.Name = "John Doe"
objCustomer.Email = "john@example.com"

' --- a tiny catalogue ---
Dim laptop : Set laptop = New Product
laptop.ID = 1 : laptop.Name = "Laptop" : laptop.Price = 999.95

Dim mouse : Set mouse = New Product
mouse.ID = 2 : mouse.Name = "Wireless Mouse" : mouse.Price = 39.95

' --- fill a cart (note: mouse added twice → Qty becomes 2) ---
Dim cart : Set cart = New ShoppingCart
cart.AddProduct laptop
cart.AddProduct mouse
cart.AddProduct mouse

' --- run the use-case ---
Dim total : total = objOrderSvc.CreateOrder(objCustomer, cart)
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 3 — Layered services &amp; cart</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    .label{color:#94a3b8;font-size:.8rem;text-transform:uppercase;letter-spacing:.08em}
    .value{color:#86efac}.error{color:#f87171}.warn{color:#fcd34d}.k{color:#7dd3fc}.muted{color:#64748b}
    .tag{display:inline-block;background:#1e3a5f;color:#7dd3fc;border-radius:3px;padding:0 6px;font-size:.78rem;margin-right:4px}
    table{width:100%;border-collapse:collapse;font-size:.9rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035}
    .total-row td{color:#86efac;border-top:1px solid #2d3748}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
  </style>
</head>
<body>
  <h1>Demo 3 — Layered services &amp; a shopping cart</h1>
  <h2>A service layer wired by dependency injection, over a Dictionary-backed collection</h2>

  <h3>The classes &amp; how they connect</h3>
  <div class="section">
    <span class="tag">Logger</span><span class="tag">Customer</span><span class="tag">Product</span>
    <span class="tag">ShoppingCart</span><span class="tag">EmailService</span><span class="tag">OrderService</span>
    <pre>Set svc = New OrderService
svc.Configure objLogger, objEmailSvc    ' inject collaborators (Set)
total = svc.CreateOrder(objCustomer, cart)   ' reads like the business process</pre>
    <p class="note"><code>OrderService</code> holds no data and creates none of its collaborators — it
    receives them. Swap <code>EmailService</code> for a real SMTP sender and nothing else changes.</p>
  </div>

  <h3>Cart contents (a Dictionary of Dictionaries)</h3>
  <div class="section">
    <table>
      <tr><th>Product ID</th><th>Product</th><th>Unit price</th><th>Qty</th><th>Line total</th></tr>
      <%
      Dim items, key, prod, qty, lineTotal
      Set items = cart.GetItems()
      For Each key In items.Keys
          Set prod = items(key)("Product")
          qty = items(key)("Qty")
          lineTotal = prod.Price * qty
      %>
        <tr>
          <td class="k"><%= prod.ID %></td>
          <td><%= Server.HTMLEncode(prod.Name) %></td>
          <td>€<%= FormatNumber(prod.Price, 2) %></td>
          <td><%= qty %></td>
          <td class="value">€<%= FormatNumber(lineTotal, 2) %></td>
        </tr>
      <% Next %>
      <tr class="total-row"><td colspan="4"><strong>Cart total</strong></td>
          <td><strong>€<%= FormatNumber(cart.GetTotal(), 2) %></strong></td></tr>
    </table>
    <p class="note">The mouse was added twice, so its line shows <code>Qty 2</code> — the
    <code>ShoppingCart</code> incremented an existing line instead of duplicating it. Each line is a
    small Dictionary <code>{"Product": obj, "Qty": n}</code>; the object value was stored with
    <code>Set</code>, the number without.</p>
  </div>

  <h3>What the OrderService logged</h3>
  <div class="section">
    <%= objLogger.GetHTML() %>
    <p class="note">Only the <code>Logger</code> produces presentation text. The other classes return
    data; they never call <code>Response.Write</code> themselves.</p>
  </div>

  <h3>Side effect captured from EmailService</h3>
  <div class="section">
    <div class="warn">&#9993; <%= Server.HTMLEncode(objEmailSvc.LastMessage) %></div>
    <p class="note">The e-mail is stubbed and merely recorded in <code>LastMessage</code>, so the demo
    has no real side effects — but <code>OrderService</code> calls it exactly as it would a real sender.</p>
  </div>

  <h3>Order summary</h3>
  <div class="section">
    <table>
      <tr><td class="label">Customer</td><td><%= Server.HTMLEncode(objCustomer.GetDisplayName()) %></td></tr>
      <tr><td class="label">Line items</td><td><%= cart.LineCount() %></td></tr>
      <tr class="total-row"><td class="label">Total</td><td><strong>€<%= FormatNumber(total, 2) %></strong></td></tr>
    </table>
  </div>

  <h3>Rules for coding agents (takeaways from this demo)</h3>
  <div class="section">
    <table>
      <tr><th>Situation</th><th>Do this in VBScript</th></tr>
      <tr><td>Need an associative map / lookup</td><td class="value">Use <code>Server.CreateObject("Scripting.Dictionary")</code></td></tr>
      <tr><td>Storing an OBJECT in a Dictionary</td><td class="value"><code>Set dict(key) = obj</code> (scalars need no <code>Set</code>)</td></tr>
      <tr><td>A line that needs several fields</td><td class="value">A nested Dictionary, or better, a small class</td></tr>
      <tr><td>Iterating a Dictionary</td><td class="value"><code>For Each key In dict.Keys</code></td></tr>
      <tr><td>A class needs a logger / mailer / repo</td><td class="value">Inject via <code>Configure()</code>; don't <code>New</code> it inside</td></tr>
      <tr><td>Releasing a Dictionary/COM object</td><td class="value"><code>Set = Nothing</code> in <code>Class_Terminate</code></td></tr>
      <tr><td>Naming a member</td><td class="value">Avoid reserved-ish names like <code>Error</code>; use <code>LogError</code></td></tr>
    </table>
  </div>

<%
' --- cleanup (Class_Terminate releases the cart's Dictionary) ---
Set items = Nothing
Set cart = Nothing
Set laptop = Nothing : Set mouse = Nothing
Set objCustomer = Nothing
Set objOrderSvc = Nothing
Set objEmailSvc = Nothing
Set objLogger = Nothing
%>
</body>
</html>
