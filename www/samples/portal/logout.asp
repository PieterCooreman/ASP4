<!--#include file="includes/core.asp" -->
<%
Set db = PortalOpen()
Call PortalInit(db)
Call PortalSignOut()
Call PortalSetFlash("You are signed out.", "info")
db.Close
Set db = Nothing
Response.Redirect PortalUrl("login.asp")
Response.End
%>
