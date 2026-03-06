<!--#include file="includes/core.asp" -->
<%
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)

Response.ContentType = "application/json"
If Not PortalIsLoggedIn() Then
    Response.Status = "401 Unauthorized"
    Response.Write "{""ok"":false}"
Else
    Session("portal_last_ping") = CStr(Now())
    Response.Write "{""ok"":true,""timeout_minutes"":" & PortalSessionTimeoutMinutes() & "}"
End If

db.Close
Set db = Nothing
%>
