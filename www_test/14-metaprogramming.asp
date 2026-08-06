<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 14-metaprogramming.asp - Recursion, dynamic code and function pointers
' ----------------------------------------------------------------------------
' VBScript can treat code as data. This page shows three powerful (and rarely
' documented) features, plus classic recursion:
'
'   1. RECURSION - a Function that calls itself (factorial, Fibonacci with a
'      memo cache, and a recursive directory-style tree walk over nested arrays).
'
'   2. Eval / Execute / ExecuteGlobal - run a string as code at runtime:
'        * Eval(expr)        -> evaluates an EXPRESSION and returns its value.
'        * Execute(stmts)    -> runs STATEMENTS in the LOCAL scope (vanishes
'                               after the call).
'        * ExecuteGlobal(s)  -> runs statements in the GLOBAL scope, so anything
'                               defined (vars, even Subs) persists afterwards.
'
'   3. GetRef("ProcName") - obtains a *pointer* to a named Sub/Function so you
'      can pass behaviour around as a value (poor-man's lambda / callback). This
'      enables higher-order functions like Map/Reduce in a language that has no
'      first-class functions.
'
' SECURITY NOTE (important for agents): Eval/Execute on UNTRUSTED input is code
' injection. Everything Eval'd here is a hard-coded constant. NEVER Eval data
' that came from Request.* . This page demonstrates the mechanism, not a pattern
' to copy onto user input.
' ============================================================================
Dim PageTitle : PageTitle = "Metaprogramming: Recursion, Eval & GetRef"
%>
<!--#include file="includes/header.asp"-->
<%
' ---------------------------------------------------------------------------
' 1) RECURSION
' ---------------------------------------------------------------------------

' Classic factorial. n! = n * (n-1)! with base case 0! = 1.
Function Factorial(ByVal n)
    If n <= 1 Then
        Factorial = 1                  ' base case stops the recursion
    Else
        Factorial = n * Factorial(n - 1)
    End If
End Function

' Fibonacci WITH memoisation. Naive Fibonacci is exponential; caching results
' in a Dictionary makes it linear. The cache is module-level so it survives
' across the recursive calls. Demonstrates recursion + Dictionary together.
Dim g_fibCache : Set g_fibCache = Server.CreateObject("Scripting.Dictionary")
Function Fib(ByVal n)
    If n < 2 Then
        Fib = n
    ElseIf g_fibCache.Exists(n) Then
        Fib = g_fibCache(n)            ' cache hit - no further recursion
    Else
        Dim v : v = Fib(n - 1) + Fib(n - 2)
        g_fibCache.Add n, v            ' memoise before returning
        Fib = v
    End If
End Function

' Recursive walk over a JAGGED array (an array whose elements may themselves be
' arrays) - the array equivalent of walking a folder tree. Returns indented text.
Function WalkTree(ByVal node, ByVal depth)
    Dim sb : Set sb = New StringBuilder
    Dim i, child
    If IsArray(node) Then
        For i = 0 To UBound(node)
            child = node(i)
            ' Build the indent. NOTE: String(n, "&nbsp;") would only repeat the
            ' FIRST character ("&"), so we expand spaces into entities instead.
            Dim pad : pad = Replace(Space(depth * 2), " ", "&nbsp;")
            If IsArray(child) Then
                sb.Append pad & "+ (branch)<br>"
                sb.Append WalkTree(child, depth + 1)        ' recurse into branch
            Else
                sb.Append pad & "- " & HtmlEncode(child) & "<br>"
            End If
        Next
    End If
    WalkTree = sb.ToString()
End Function

' ---------------------------------------------------------------------------
' 3) GetRef + higher-order functions
' ---------------------------------------------------------------------------

' Two ordinary functions we will pass around BY REFERENCE via GetRef.
Function Square(ByVal x) : Square = x * x : End Function
Function Cube(ByVal x)   : Cube   = x * x * x : End Function

' Map: apply a function-pointer to every element of an array, returning a new
' array. 'fn' is a reference obtained with GetRef. This is impossible without
' GetRef because VBScript has no lambda syntax.
Function MapArray(ByVal fn, ByVal arr)
    Dim out, i
    ReDim out(UBound(arr))
    For i = 0 To UBound(arr)
        out(i) = fn(arr(i))            ' call THROUGH the pointer
    Next
    MapArray = out
End Function

' Reduce: fold an array down to one value using a 2-arg function-pointer.
Function ReduceArray(ByVal fn, ByVal arr, ByVal seed)
    Dim acc, i
    acc = seed
    For i = 0 To UBound(arr)
        acc = fn(acc, arr(i))
    Next
    ReduceArray = acc
End Function

Function Add(ByVal a, ByVal b) : Add = a + b : End Function
Function Max2(ByVal a, ByVal b)
    If a > b Then Max2 = a Else Max2 = b
End Function
%>
<h1>Metaprogramming</h1>
<p class="lead">
  VBScript can call itself recursively, run strings as code, and pass functions
  as values. These are the building blocks of interpreters, callbacks and
  higher-order programming.
</p>

<h2>1. Recursion: factorial</h2>
<%
DemoStart "n! computed by a function that calls itself"
Dim n
WriteLine "<table class=""kv"">"
For n = 0 To 8
    RenderTableRow n & "!", Factorial(n)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Recursion + caching: Fibonacci with a memo</h2>
<p>
  Without the Dictionary cache, <code>Fib(n)</code> recomputes the same
  sub-problems exponentially. The memo turns it into a fast linear walk.
</p>
<%
DemoStart "First 15 Fibonacci numbers (memoised)"
WriteLine "<p>"
For n = 0 To 14
    If n > 0 Then Response.Write ", "
    Response.Write "<strong>" & Fib(n) & "</strong>"
Next
WriteLine "</p>"
WriteLine "<p class=""ok"">Cache now holds " & g_fibCache.Count & " memoised results.</p>"
DemoEnd
%>

<h2>Recursion over a jagged array (tree walk)</h2>
<%
DemoStart "Walking a nested array as if it were a folder tree"
' Build a tree: arrays nested inside arrays.
Dim tree
tree = Array( _
    "readme.txt", _
    Array("src", "main.asp", Array("lib", "helpers.asp", "string.asp")), _
    Array("docs", "guide.md"), _
    "license" _
)
WriteLine "<div class=""demo-output"" style=""font-family:Consolas,monospace"">"
WriteLine WalkTree(tree, 0)
WriteLine "</div>"
DemoEnd
%>

<h2>2. Eval: evaluate an expression string</h2>
<p>
  <code>Eval</code> takes a string containing an <strong>expression</strong> and
  returns its value. Think of it as a one-line calculator. (Note: in VBScript
  <code>Eval("a = 5")</code> tests equality and returns a Boolean - it does
  <em>not</em> assign. Use <code>Execute</code> to assign.)
</p>
<%
DemoStart "A safe expression calculator (constants only!)"
Dim exprs, e
exprs = Array("2 + 3 * 4", "(10 - 4) / 2", "Len(""classic asp"")", "UCase(""abc"") & 123", "2 ^ 10", "7 Mod 3")
WriteLine "<table class=""kv"">"
For Each e In exprs
    On Error Resume Next
    Dim val : val = Eval(e)
    If Err.Number <> 0 Then
        RenderTableRow "Eval(""" & e & """)", "ERR: " & Err.Description
        Err.Clear
    Else
        RenderTableRow "Eval(""" & e & """)", val
    End If
    On Error Goto 0
Next
WriteLine "</table>"
WriteLine "<p class=""warn"">Never Eval anything from Request.* - that is remote code execution.</p>"
DemoEnd
%>

<h2>Execute vs ExecuteGlobal: scope matters</h2>
<p>
  <code>Execute</code> runs statements in the <em>local</em> scope - whatever it
  defines disappears when it returns. <code>ExecuteGlobal</code> runs them in the
  <em>global</em> scope, so newly defined variables (and even procedures) persist
  and can be used by ordinary code afterwards.
</p>
<%
DemoStart "Defining a variable at runtime, globally"
' ExecuteGlobal creates a real global variable named dynVar that the rest of the
' script can then read normally.
ExecuteGlobal "Dim dynVar : dynVar = ""I was created from a string at runtime"""
WriteLine "<table class=""kv"">"
RenderTableRow "Value of dynVar afterwards", dynVar

' ExecuteGlobal can even define a brand-new Sub at runtime.
ExecuteGlobal "Function Triple(x) : Triple = x * 3 : End Function"
RenderTableRow "Calling the runtime-defined Triple(14)", Triple(14)
WriteLine "</table>"
DemoEnd
%>

<h2>3. GetRef: functions as values (callbacks)</h2>
<p>
  <code>GetRef("Name")</code> returns a reference to a named procedure. Store it
  in a variable, pass it to another function, and call through it. This is how you
  build <strong>Map</strong>, <strong>Reduce</strong> and event handlers in a
  language with no lambda syntax.
</p>
<%
DemoStart "Map and Reduce powered by GetRef"
Dim nums : nums = Array(1, 2, 3, 4, 5)

' Pass Square / Cube as values into MapArray.
Dim squares : squares = MapArray(GetRef("Square"), nums)
Dim cubes   : cubes   = MapArray(GetRef("Cube"),   nums)

' Pass Add / Max2 as values into ReduceArray.
Dim total   : total   = ReduceArray(GetRef("Add"),  nums, 0)
Dim biggest : biggest = ReduceArray(GetRef("Max2"), nums, nums(0))

WriteLine "<table class=""kv"">"
RenderTableRow "nums",                       Join(nums, ", ")
RenderTableRow "Map(Square)",                Join(squares, ", ")
RenderTableRow "Map(Cube)",                  Join(cubes, ", ")
RenderTableRow "Reduce(Add, seed 0)  = sum", total
RenderTableRow "Reduce(Max2)         = max", biggest
WriteLine "</table>"
DemoEnd
%>

<h2>GetRef for dynamic dispatch (a tiny dispatcher)</h2>
<p>
  Storing function pointers in a <code>Dictionary</code> keyed by name gives you
  a clean dispatch table - far better than a giant <code>Select Case</code>.
</p>
<%
DemoStart "Operation lookup table"
Dim ops : Set ops = Server.CreateObject("Scripting.Dictionary")
ops.Add "square", GetRef("Square")
ops.Add "cube",   GetRef("Cube")
Dim opName, fnPtr
WriteLine "<table class=""kv"">"
For Each opName In ops.Keys
    Set fnPtr = ops(opName)             ' fetch the pointer
    RenderTableRow "ops(""" & opName & """)(6)", fnPtr(6)   ' call it
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "' Recursion:" & vbCrLf & _
    "Function Factorial(n)" & vbCrLf & _
    "    If n <= 1 Then Factorial = 1 Else Factorial = n * Factorial(n - 1)" & vbCrLf & _
    "End Function" & vbCrLf & vbCrLf & _
    "' Eval evaluates an EXPRESSION and returns its value:" & vbCrLf & _
    "x = Eval(""2 + 3 * 4"")        ' 14" & vbCrLf & vbCrLf & _
    "' ExecuteGlobal runs STATEMENTS in global scope (they persist):" & vbCrLf & _
    "ExecuteGlobal ""Dim k : k = 99""" & vbCrLf & _
    "Response.Write k              ' 99" & vbCrLf & vbCrLf & _
    "' GetRef gives a callable pointer to a named proc:" & vbCrLf & _
    "Set fn = GetRef(""Square"")" & vbCrLf & _
    "Response.Write fn(7)          ' 49" & vbCrLf & vbCrLf & _
    "' SECURITY: never Eval/Execute data from Request.*"
%>
<!--#include file="includes/footer.asp"-->
