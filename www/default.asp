<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to ASPPY</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .card {
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
            padding: 48px 56px;
            max-width: 480px;
            text-align: center;
        }

        .badge {
            display: inline-block;
            background: #f97316;
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            padding: 4px 12px;
            border-radius: 999px;
            margin-bottom: 16px;
        }

        h1 {
            margin: 0 0 12px;
            font-size: 28px;
            color: #0f172a;
        }

        p.greeting {
            font-size: 20px;
            color: #475569;
            margin-bottom: 24px;
        }

        p.description {
            font-size: 18px;
            color: #64748b;
            line-height: 1.6;
        }

        .footer {
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            font-size: 16px;
            color: #94a3b8;
        }

        strong.brand {
            color: #f97316;
        }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">ASPPY</span>
        <h1>Welcome to ASPPY!</h1>
        <p class="greeting">
            <%
            Dim hour
            hour = Hour(Now())
            If hour < 12 Then
                Response.Write "Good morning"
            ElseIf hour < 18 Then
                Response.Write "Good afternoon"
            Else
                Response.Write "Good evening"
            End If
            %>, and thanks for stopping by.
        </p>
        <p class="description">
            This page is running Classic ASP/VBScript on <strong class="brand">ASPPY</strong> — no IIS required.
        </p>
        <div class="footer">
            Server time: <%= Now() %>
        </div>
    </div>
</body>
</html>
