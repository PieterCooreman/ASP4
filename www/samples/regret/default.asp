<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Response.CodePage = 65001
Response.Charset = "UTF-8"

Dim db, regretSvc, sortBy, timeRemaining
Set db = New cls_db
db.Open
Set regretSvc = New cls_regret

regretSvc.PurgeExpiredRegrets db

sortBy = Request.QueryString("sort")
If sortBy = "" Then sortBy = "newest"

timeRemaining = GetTimeUntilMidnight()

db.Close
Set db = Nothing
%>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Regret Box</title>
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
            font-size: 28px;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 8px;
        }
        
        .countdown {
            font-size: 12px;
            color: #666;
            letter-spacing: 1px;
            transition: color 0.3s;
        }
        
        .countdown.urgent {
            color: #c44;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .submit-section {
            background: #111;
            border: 1px solid #222;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
        }
        
        .category-select {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .category-option {
            padding: 6px 12px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            color: #888;
        }
        
        .category-option:hover {
            border-color: #555;
        }
        
        .category-option.selected {
            background: #252525;
            border-color: #666;
            color: #fff;
        }
        
        textarea {
            width: 100%;
            background: #0a0a0a;
            border: 1px solid #222;
            border-radius: 8px;
            padding: 16px;
            color: #e8e8e8;
            font-family: 'Cormorant Garamond', serif;
            font-size: 18px;
            resize: none;
            outline: none;
            transition: border-color 0.2s;
        }
        
        textarea:focus {
            border-color: #444;
        }
        
        textarea::placeholder {
            color: #444;
            font-style: italic;
        }
        
        .char-count {
            text-align: right;
            font-size: 11px;
            color: #444;
            margin-top: 8px;
            margin-bottom: 16px;
        }
        
        .char-count.warning {
            color: #c44;
        }
        
        .submit-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #1a1a1a, #0a0a0a);
            border: 1px solid #333;
            border-radius: 8px;
            color: #888;
            font-size: 12px;
            letter-spacing: 2px;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .submit-btn:hover {
            background: #222;
            color: #aaa;
            border-color: #444;
        }
        
        .submit-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .crisis-message {
            display: none;
            background: #1a1510;
            border: 1px solid #3a3020;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
            text-align: center;
        }
        
        .crisis-message.visible {
            display: block;
        }
        
        .crisis-message p {
            color: #c84;
            font-size: 14px;
            margin-bottom: 8px;
        }
        
        .crisis-message a {
            color: #8ac;
            font-size: 12px;
        }
        
        .sort-bar {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #1a1a1a;
        }
        
        .sort-btn {
            background: none;
            border: none;
            color: #444;
            font-size: 11px;
            letter-spacing: 1px;
            text-transform: uppercase;
            cursor: pointer;
            transition: color 0.2s;
        }
        
        .sort-btn:hover {
            color: #666;
        }
        
        .sort-btn.active {
            color: #888;
        }
        
        .regrets-feed {
            display: flex;
            flex-direction: column;
            gap: 16px;
            padding-bottom: 40px;
        }
        
        .regret-card {
            background: #0f0f0f;
            border: 1px solid #1a1a1a;
            border-radius: 10px;
            padding: 20px;
            animation: fadeIn 0.4s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .regret-card.breathing {
            animation: fadeIn 0.4s ease-out, breathe 4s ease-in-out infinite 0.4s;
        }
        
        @keyframes breathe {
            0%, 100% { border-color: #1a1a1a; }
            50% { border-color: #2a2a2a; }
        }
        
        .regret-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .regret-category {
            font-size: 14px;
            color: #666;
        }
        
        .regret-today {
            font-size: 10px;
            color: #333;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .regret-text {
            font-family: 'Cormorant Garamond', serif;
            font-size: 20px;
            font-weight: 300;
            line-height: 1.5;
            color: #ccc;
            margin-bottom: 16px;
        }
        
        .regret-actions {
            display: flex;
            gap: 12px;
        }
        
        .vote-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 14px;
            background: #0a0a0a;
            border: 1px solid #1a1a1a;
            border-radius: 20px;
            color: #555;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .vote-btn:hover {
            background: #151515;
            border-color: #2a2a2a;
            color: #777;
        }
        
        .vote-btn.voted {
            color: #888;
        }
        
        .vote-btn .count {
            font-size: 11px;
            opacity: 0.7;
        }
        
        .report-btn {
            margin-left: auto;
            background: none;
            border: none;
            color: #333;
            font-size: 10px;
            cursor: pointer;
            transition: color 0.2s;
        }
        
        .report-btn:hover {
            color: #844;
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
        
        .archive-link {
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
        
        .archive-link:hover {
            color: #555;
        }
        
        .success-toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: #1a1a1a;
            border: 1px solid #333;
            padding: 14px 24px;
            border-radius: 8px;
            color: #888;
            font-size: 13px;
            opacity: 0;
            transition: all 0.3s;
            z-index: 1000;
        }
        
        .success-toast.visible {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
        
        .purge-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #0a0a0a;
            z-index: 9999;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        
        .purge-overlay.visible {
            display: flex;
            animation: fadeIn 0.5s;
        }
        
        .purge-overlay p {
            font-family: 'Cormorant Garamond', serif;
            font-size: 20px;
            color: #444;
            font-style: italic;
            animation: fadeOut 3s forwards 2s;
        }
        
        @keyframes fadeOut {
            to { opacity: 0; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>The Regret Box</h1>
            <div class="countdown" id="countdown">This box closes in <%=timeRemaining%> hours</div>
        </header>
        
        <div class="submit-section">
            <div class="category-select" id="categorySelect">
                <div class="category-option" data-category="love">💔 Love</div>
                <div class="category-option" data-category="career">💼 Career</div>
                <div class="category-option" data-category="family">👨‍👩‍👧 Family</div>
                <div class="category-option" data-category="education">🎓 Education</div>
                <div class="category-option" data-category="money">💰 Money</div>
                <div class="category-option" data-category="life">🌍 Life path</div>
                <div class="category-option" data-category="unsaid">😶 Things unsaid</div>
            </div>
            
            <textarea id="regretText" placeholder="Drop your regret here. One per day. Be honest..." maxlength="160" rows="3"></textarea>
            
            <div class="char-count" id="charCount">0 / 160</div>
            
            <button class="submit-btn" id="submitBtn" disabled>Drop it in</button>
            
            <div class="crisis-message" id="crisisMessage">
                <p>If you're carrying something heavy, you don't have to carry it alone.</p>
                <a href="https://988lifeline.org" target="_blank">Call 988 (Suicide & Crisis Lifeline)</a>
            </div>
        </div>
        
        <div class="sort-bar">
            <button class="sort-btn <%If sortBy="newest" Then Response.Write("active")%>" data-sort="newest">Newest</button>
            <button class="sort-btn <%If sortBy="me_too" Then Response.Write("active")%>" data-sort="me_too">Most "Me too"</button>
            <button class="sort-btn <%If sortBy="comfort" Then Response.Write("active")%>" data-sort="comfort">Most comforting</button>
        </div>
        
        <div class="regrets-feed" id="regretsFeed">
            <div class="empty-state">
                <div class="icon">🪦</div>
                <p>The box is empty. Be the first.</p>
            </div>
        </div>
        
        <a href="archive.asp" class="archive-link">View Archive</a>
    </div>
    
    <div class="success-toast" id="successToast"></div>
    
    <div class="purge-overlay" id="purgeOverlay">
        <p>It's gone. So is everyone else's.</p>
    </div>
    
    <script>
        const categories = document.querySelectorAll('.category-option');
        let selectedCategory = 'life';
        
        categories.forEach(cat => {
            cat.addEventListener('click', () => {
                categories.forEach(c => c.classList.remove('selected'));
                cat.classList.add('selected');
                selectedCategory = cat.dataset.category;
            });
        });
        
        document.querySelector('.category-option[data-category="life"]').classList.add('selected');
        
        const textArea = document.getElementById('regretText');
        const charCount = document.getElementById('charCount');
        const submitBtn = document.getElementById('submitBtn');
        
        textArea.addEventListener('input', () => {
            const len = textArea.value.length;
            charCount.textContent = len + ' / 160';
            charCount.classList.toggle('warning', len > 140);
            submitBtn.disabled = len === 0 || len > 160;
        });
        
        submitBtn.addEventListener('click', async () => {
            const text = textArea.value.trim();
            if (!text) return;
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('category', selectedCategory);
                
                const response = await fetch('api/regrets.asp', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.crisis) {
                    document.getElementById('crisisMessage').classList.add('visible');
                    return;
                }
                
                if (data.error) {
                    showToast(data.error);
                    return;
                }
                
                textArea.value = '';
                charCount.textContent = '0 / 160';
                submitBtn.disabled = true;
                showToast('Regret dropped. Make peace.');
                loadRegrets();
                
            } catch (err) {
                showToast('Something went wrong. Try again.');
            }
        });
        
        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const sort = btn.dataset.sort;
                window.location.href = '?sort=' + sort;
            });
        });
        
        function showToast(message) {
            const toast = document.getElementById('successToast');
            toast.textContent = message;
            toast.classList.add('visible');
            setTimeout(() => toast.classList.remove('visible'), 3000);
        }
        
        async function loadRegrets() {
            const params = new URLSearchParams(window.location.search);
            const sort = params.get('sort') || 'newest';
            
            try {
                const response = await fetch('api/regrets.asp?sort=' + sort);
                const regrets = await response.json();
                
                const feed = document.getElementById('regretsFeed');
                
                if (regrets.length === 0) {
                    feed.innerHTML = `
                        <div class="empty-state">
                            <div class="icon">🪦</div>
                            <p>The box is empty. Be the first.</p>
                        </div>
                    `;
                    return;
                }
                
                feed.innerHTML = regrets.map(regret => {
                    const totalVotes = regret.me_too + regret.not_alone;
                    const breathing = totalVotes > 10 ? 'breathing' : '';
                    
                    return `
                        <div class="regret-card ${breathing}" data-id="${regret.id}">
                            <div class="regret-header">
                                <span class="regret-category">${getCategoryEmoji(regret.category)} ${regret.category}</span>
                                <span class="regret-today">today</span>
                            </div>
                            <div class="regret-text">${escapeHtml(regret.text)}</div>
                            <div class="regret-actions">
                                <button class="vote-btn" data-id="${regret.id}" data-vote="me_too">
                                    🫂 Me too <span class="count">${regret.me_too}</span>
                                </button>
                                <button class="vote-btn" data-id="${regret.id}" data-vote="not_alone">
                                    🕯️ Not alone <span class="count">${regret.not_alone}</span>
                                </button>
                                <button class="report-btn" data-id="${regret.id}">report</button>
                            </div>
                        </div>
                    `;
                }).join('');
                
                document.querySelectorAll('.vote-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        const id = btn.dataset.id;
                        const vote = btn.dataset.vote;
                        
                        try {
                            const formData = new FormData();
                            formData.append('vote', vote);
                            
                            await fetch('api/regrets.asp?action=vote&id=' + id, {
                                method: 'POST',
                                body: formData
                            });
                            
                            btn.classList.add('voted');
                            const count = parseInt(btn.querySelector('.count').textContent) + 1;
                            btn.querySelector('.count').textContent = count;
                            
                        } catch (err) {
                            showToast('Vote failed. Try again.');
                        }
                    });
                });
                
                document.querySelectorAll('.report-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        if (confirm('Report this regret as inappropriate?')) {
                            try {
                                await fetch('api/regrets.asp?action=vote&id=' + btn.dataset.id, {
                                    method: 'POST'
                                });
                                showToast('Report submitted.');
                            } catch (err) {}
                        }
                    });
                });
                
            } catch (err) {
                console.error('Failed to load regrets:', err);
            }
        }
        
        function getCategoryEmoji(category) {
            const emojis = {
                'love': '💔',
                'career': '💼',
                'family': '👨‍👩‍👧',
                'education': '🎓',
                'money': '💰',
                'life': '🌍',
                'unsaid': '😶'
            };
            return emojis[category] || '💭';
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        loadRegrets();
        
        setInterval(loadRegrets, 15000);
        
        let minutesLeft = <%=timeRemaining%>;
        if (minutesLeft <= 30) {
            const countdown = document.getElementById('countdown');
            countdown.textContent = 'This box closes in ' + minutesLeft + ' minutes';
            countdown.classList.add('urgent');
        }
        
        if (minutesLeft <= 1) {
            document.getElementById('purgeOverlay').classList.add('visible');
        }
    </script>
</body>
</html>
