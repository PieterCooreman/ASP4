<%
Sub RenderNotFoundPage(pageTitle, errorTitle, errorMessage)
    Call RenderHeader(pageTitle)
%>
<!--#include file="../views/errors/not_found.asp" -->
<%
    Call RenderFooter()
End Sub
%>
