<!--#include file="asp/helpers.asp" -->
<!--#include file="asp/layout.asp" -->
<!--#include file="asp/controllers/shared.asp" -->
<!--#include file="asp/controllers/home.asp" -->
<%
Response.Buffer = True

Dim parts
parts = RouteParts()

If RouteIs("/") Or RouteIs("/index.asp") Then
    Call HomeIndex()
ElseIf UBound(parts) = 1 And parts(0) = "hello" Then
    Call HomeHello(parts(1))
Else
    Response.Status = "404 Not Found"
    Call RenderNotFoundPage("404 Not Found", "Route not found", "No page matches " & CurrentRoute() & ".")
End If
%>
