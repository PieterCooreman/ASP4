<%
Sub RenderHeader(title)
    Dim homeClass
    homeClass = "nav-link"

    If RouteIs("/") Or RouteIs("/index.asp") Then
        homeClass = "nav-link active"
    End If
%>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><%=Html(title)%></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="/assets/app.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg starter-nav">
        <div class="container">
            <a class="navbar-brand" href="/">ASPPY Starter</a>
            <div class="navbar-nav ms-auto">
                <a class="<%=homeClass%>" href="/">Home</a>
            </div>
        </div>
    </nav>
    <main class="py-4 py-lg-5">
        <div class="container">
<%
End Sub

Sub RenderFooter()
%>
        </div>
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
<%
End Sub
%>
