<% =("Hello World")%><br>

<%= ("Hello World")%><br>

<% = ("Hello World")%><br>

<% = ("Hello" & " " & "World")%><br>

<% = ("Hello"&" "&"World")%><br>

<% =("Hello World")%><br>

<%= ("Hello World")%><br>

<% = ("Hello World")%><br>

<% = ("Hello World")%><br>

<% = ("Hello" + " " + "World")%><br>

<% = ("Hello"+" "+"World")%><br>

<% response.write("Hello World")%><br>

<%response.write ("Hello World")%><br>

<% response.write ("Hello World")%><br>

<% response.write ("Hello World")%><br>

<% response.write ("Hello" & " " & "World")%><br>

<% response.write ("Hello"&" "&"World")%><br>

<% response.write("Hello World")%><br>

<%response.write ("Hello World")%><br>

<% response.write ("Hello World")%><br>

<% response.write ("Hello World")%><br>

<% response.write ("Hello" + " " + "World")%><br>

<% response.write ("Hello"+" "+"World")%><br>

<% ="Hello World"%><br>

<%= "Hello World"%><br>

<% = "Hello World"%><br>

<% = "Hello World"%><br>

<% = "Hello" & " " & "World"%><br>

<% = "Hello"&" "&"World"%><br>

<% ="Hello World"%><br>

<%= "Hello World"%><br>

<% = "Hello World"%><br>

<% = "Hello World"%><br>

<% = Filter(Array("Hello World", "Goodbye"), "Hello World")(0) %><br>

<% = "Hello" + " " + "World"%><br>

<% = "Hello"+" "+"World"%><br>

<% ReSpOnSe.wrIte "Hello World"%><br>

<%response.write "Hello World"%><br>

<% response.write "Hello World"%><br>

<% response.write "Hello World"%><br>

<% response.write "Hello" & " " & "World"%><br>

<% response.write "Hello"&" "&"World"%><br>

<%response.write "Hello World"%><br>

<% response.write "Hello World"%><br>

<% response.write "Hello World"%><br>

<% response.write "Hello" + " " + "World"%><br>

<% response.write "Hello"+" "+"World"%><br>

<% Response.Write "Hello " : Response.Write "World" %><br>

<% Function HW() : HW = "Hello World" : End Function : response.write HW() %><br>

<% RESPONSE.WRITE "Hello World" %><br>

<% rEsPoNsE.WrItE "Hello World" %><br>

<% = "Hello" & Chr(32) & "World" %><br>

<% = Chr(72)&Chr(101)&Chr(108)&Chr(108)&Chr(111)&Chr(32)&Chr(87)&Chr(111)&Chr(114)&Chr(108)&Chr(100) %><br>

<% Dim s : s = "Hello World" : Response.Write s %><br>

<% Dim a, b : a = "Hello" : b = "World" : Response.Write a & " " & b %><br>

<% s = "Hello World" : response.write  s %><br>

<% = Join(Array("Hello", "World"), " ") %><br>

<% = StrReverse("dlroW olleH") %><br>

<% = UCase("hello world") %><br>

<% = LCase("HELLO WORLD") %><br>

<% = Mid("Hello World Extra", 1, 11) %><br>

<% = Left("Hello World Extra", 11) %><br>

<% = Trim("  Hello World  ") %><br>

<% = Replace("Hello-World", "-", " ") %><br>

<% = Filter(Array("Hello World", "Goodbye"), "Hello World")(0) %><br>

<% For i = 1 To 1 : Response.Write "Hello World" : Next %><br>


<% Do : Response.Write "Hello World" : Loop While False %><br>

<% If True Then Response.Write "Hello World" %><br>

<% Select Case 1 : Case 1 : Response.Write "Hello World" : End Select %><br>

<% Class Greeter
     Public Function Say()
       Say = "Hello World"
     End Function
   End Class
   Dim g : Set g = New Greeter
   Response.Write g.Say()
%><br>

<% Dim dict : Set dict = CreateObject("Scripting.Dictionary")
   dict.Add "msg", "Hello World"
   Response.Write dict("msg")
%><br>

<% Execute "Response.Write ""Hello World""" %><br>

<% Eval("1=1") : Response.Write "Hello World" %><br>

<% Dim arr(1)
   arr(0) = "Hello"
   arr(1) = "World"
   Response.Write arr(0) & " " & arr(1)
%><br>

<% With Response
     .Write "Hello World"
   End With
%><br>

<% On Error Resume Next
   Err.Raise 9999
   If Err.Number = 9999 Then Response.Write "Hello World"
   On Error Goto 0
%><br>

<% Function Recurse(n)
     If n = 0 Then
       Recurse = "Hello World"
     Else
       Recurse = Recurse(n - 1)
     End If
   End Function
   Response.Write Recurse(3)
%><br>

<% Dim xmlDoc : Set xmlDoc = CreateObject("MSXML2.DOMDocument")
   xmlDoc.LoadXML "<msg>Hello World</msg>"
   Response.Write xmlDoc.SelectSingleNode("/msg").Text
%><br>

<% Response.Write CStr("Hello World") %><br>

<% Response.Write CreateObject("Scripting.FileSystemObject").GetTempName() & "" : Response.Write "Hello World" %>
<br>
<% Set re = New RegExp
   re.Pattern = "X"
   Response.Write re.Replace("HelloXWorld", " ")
%><br>

<% Response.Write Space(0) & "Hello World" %><br>

<% Response.Write String(0, " ") & "Hello World" %><br>

<% Response.Write FormatMessage() 
   Function FormatMessage()
     FormatMessage = "Hello World"
   End Function
%><br>

<% Response.Write vbNullString & "Hello World" %><br>

<% Response.Write Array("Hello World")(0) %><br>

<% ExecuteGlobal "Sub PrintIt() : Response.Write ""Hello World"" : End Sub"
   PrintIt
%><br>

<% GetRef("PrintHW")()
   Sub PrintHW() : Response.Write "Hello World" : End Sub
%><br>

<%
   ' Building it letter-by-letter via ASCII math instead of Chr() chains
   Dim s, i, codes
   codes = Array(72,101,108,108,111,32,87,111,114,108,100)
   s = ""
   For i = 0 To UBound(codes)
     s = s & Chr(codes(i))
   Next
   Response.Write s
%><br>

<% Response.Write Application("greeting") 
   Application("greeting") = "Hello World"
%><br>

<% Session("hw") = "Hello World" : Response.Write Session("hw") %>
<br>
<%
   Function IIf(expr, truePart, falsePart)
     If expr Then
       IIf = truePart
     Else
       IIf = falsePart
     End If
   End Function
   Response.Write IIf(Request.QueryString("hw") = "", "Hello World", Request.QueryString("hw"))
%><br>

<%
   Dim hw : hw = Request.QueryString("hw")
   If hw = "" Then hw = "Hello World"
   Response.Write hw
%>
