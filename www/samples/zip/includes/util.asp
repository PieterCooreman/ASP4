<%
Function H(v)
    H = Server.HTMLEncode("" & v)
End Function

Function IsPost()
    IsPost = (UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST")
End Function
%>
