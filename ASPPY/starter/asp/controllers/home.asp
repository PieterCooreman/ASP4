<!--#include file="../models/app.asp" -->
<%
Sub HomeIndex()
    Dim pageTitle, highlights
    pageTitle = "ASPPY MVC Starter"
    highlights = StarterHighlights()

    Call RenderHeader(pageTitle)
%>
<!--#include file="../views/home/index.asp" -->
<%
    Call RenderFooter()
End Sub

Sub HomeHello(personName)
    Dim pageTitle, displayName
    pageTitle = "Dynamic Route Example"
    displayName = Replace(TextValue(personName), "-", " ")

    Call RenderHeader(pageTitle)
%>
<!--#include file="../views/home/hello.asp" -->
<%
    Call RenderFooter()
End Sub
%>
