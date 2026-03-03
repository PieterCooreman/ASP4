<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Response.CodePage = 65001
Response.Charset = "UTF-8"

Dim db, regretSvc, totalStats, topCategory
Set db = New cls_db
db.Open
Set regretSvc = New cls_regret

totalStats = regretSvc.GetTotalStats(db)
topCategory = regretSvc.GetTopCategory(db)

db.Close
Set db = Nothing
%>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archive — The Regret Box</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Inter:wght@300;400&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        html, body {
            height: 100%;
            background: #0a0a0a;
            color: #e8e8e8;
            font-family: 'Inter', sans-serif;
        }
        
        .container {
            max-width: 680px;
            margin: 0 auto;
            padding: 20px;
            min-height: 100vh;
        }
        
        header {
            text-align: center;
            padding: 40px 0 30px;
        }
        
        h1 {
            font-family: 'Cormorant Garamond', serif;
            font-weight: 300;
            font-size: 24px;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: #555;
            margin-bottom: 8px;
        }
        
        .subtitle {
            font-size: 12px;
            color: #444;
            letter-spacing: 1px;
            margin-bottom: 30px;
        }
        
        .back-link {
            display: block;
            text-align: center;
            padding: 20px;
            color: #333;
            font-size: 11px;
            letter-spacing: 1px;
            text-transform: uppercase;
            text-decoration: none;
            border-top: 1px solid #1a1a1a;
            margin-top: 20px;
            transition: color 0.2s;
        }
        
        .back-link:hover {
            color: #555;
        }
        
        .archive-list {
            display: flex;
            flex-direction: column;
            gap: 2px;
            background: #111;
            border: 1px solid #1a1a1a;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .archive-row {
            display: grid;
            grid-template-columns: 100px 1fr 80px 80px;
            gap: 10px;
            padding: 16px 20px;
            background: #0f0f0f;
            align-items: center;
        }
        
        .archive-row:first-child {
            background: #141414;
        }
        
        .archive-row.header {
            font-size: 10px;
            color: #444;
            text-transform: uppercase;
            letter-spacing: 1px;
            background: #1a1a1a;
        }
        
        .archive-date {
            font-size: 13px;
            color: #666;
        }
        
        .archive-category {
            font-size: 14px;
            color: #888;
        }
        
        .archive-stat {
            text-align: right;
            font-size: 13px;
            color: #555;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #333;
        }
        
        .empty-state .icon {
            font-size: 48px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        .empty-state p {
            font-family: 'Cormorant Garamond', serif;
            font-size: 18px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Archive</h1>
            <p class="subtitle">Yesterday's regrets</p>
        </header>
        
        <div class="archive-list" id="archiveList">
            <div class="archive-row header">
                <span>Date</span>
                <span>Top Category</span>
                <span style="text-align:right">Regrets</span>
                <span style="text-align:right">Me too</span>
            </div>
        </div>
        
        <a href="default.asp" class="back-link">← Back to the box</a>
    </div>
    
    <script>
        async function loadArchive() {
            try {
                const response = await fetch('api/archive.asp');
                const archives = await response.json();
                
                const list = document.getElementById('archiveList');
                
                if (archives.length === 0) {
                    list.innerHTML = `
                        <div class="empty-state">
                            <div class="icon">📦</div>
                            <p>No archives yet. Check back tomorrow.</p>
                        </div>
                    `;
                    return;
                }
                
                let html = `<div class="archive-row header">
                    <span>Date</span>
                    <span>Top Category</span>
                    <span style="text-align:right">Regrets</span>
                    <span style="text-align:right">Me too</span>
                </div>`;
                
                archives.forEach(day => {
                    const date = new Date(day.date);
                    const formatted = date.toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric'
                    });
                    
                    html += `
                        <div class="archive-row">
                            <span class="archive-date">${formatted}</span>
                            <span class="archive-category">${day.top_category}</span>
                            <span class="archive-stat">${day.total_regrets}</span>
                            <span class="archive-stat">${day.total_me_too}</span>
                        </div>
                    `;
                });
                
                list.innerHTML = html;
                
            } catch (err) {
                console.error('Failed to load archive:', err);
            }
        }
        
        loadArchive();
    </script>
</body>
</html>
