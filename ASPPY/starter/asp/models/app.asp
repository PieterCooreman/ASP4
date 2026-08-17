<%
Function StarterHighlights()
    StarterHighlights = Array( _
        Array("Routing", "Use `www/default.asp` as the front controller and keep route parsing there."), _
        Array("Controllers", "Put request logic in `www/asp/controllers/` and keep layout ownership consistent."), _
        Array("Views", "Render page HTML from `www/asp/views/` instead of large `Response.Write` blocks."), _
        Array("Database", "Use `www/asp/db.asp` with `www/data/app.db`; do not initialize schema in `default.asp`." ) _
    )
End Function
%>
