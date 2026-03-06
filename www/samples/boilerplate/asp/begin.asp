<%
Option Explicit

Response.Buffer				= true
session.Timeout				= 120
server.ScriptTimeout		= 800 'seconds: needed for uploading bigger pictures/files!
Response.CharSet			= "utf-8"
Response.ContentType		= "text/html"
Response.CacheControl		= "no-cache"
Response.AddHeader "pragma", "no-cache"
Response.Expires			= -1
Response.ExpiresAbsolute	= Now()-1

%>