<%
Class cls_regret
    Public Function GetActiveRegrets(db, sortBy)
        Dim sql, rs
        Dim today
        today = DateValue(Now())
        
        Select Case sortBy
            Case "me_too"
                sql = "SELECT * FROM regrets WHERE expires_at > datetime('now') AND reports < 5 ORDER BY me_too DESC, created_at DESC"
            Case "comfort"
                sql = "SELECT * FROM regrets WHERE expires_at > datetime('now') AND reports < 5 ORDER BY not_alone DESC, created_at DESC"
            Case Else
                sql = "SELECT * FROM regrets WHERE expires_at > datetime('now') AND reports < 5 ORDER BY created_at DESC"
        End Select
        
        Set rs = db.Query(sql)
        Set GetActiveRegrets = rs
    End Function
    
    Public Function GetRegretCount(db)
        GetRegretCount = db.Scalar("SELECT COUNT(*) FROM regrets WHERE expires_at > datetime('now') AND reports < 5", 0)
    End Function
    
    Public Function CreateRegret(db, text, category)
        Dim id, createdAt, expiresAt, today, tomorrow, sql
        
        id = GenerateUUID()
        createdAt = Now()
        today = DateValue(createdAt)
        tomorrow = today + 1
        expiresAt = tomorrow
        
        sql = "INSERT INTO regrets (id, text, category, me_too, not_alone, created_at, expires_at, reports) VALUES ('" & _
            Q(id) & "', '" & Q(text) & "', '" & Q(category) & "', 0, 0, '" & Q(createdAt) & "', '" & Q(expiresAt) & "', 0)"
        
        db.Execute sql
        
        CreateRegret = id
    End Function
    
    Public Function Vote(db, id, voteType)
        If voteType = "me_too" Then
            db.Execute "UPDATE regrets SET me_too = me_too + 1 WHERE id = '" & Q(id) & "'"
        Else
            db.Execute "UPDATE regrets SET not_alone = not_alone + 1 WHERE id = '" & Q(id) & "'"
        End If
    End Function
    
    Public Function ReportRegret(db, id)
        Dim sql
        sql = "UPDATE regrets SET reports = reports + 1 WHERE id = '" & Q(id) & "'"
        db.Execute sql
    End Function
    
    Public Function GetRegretById(db, id)
        Dim sql, rs
        sql = "SELECT * FROM regrets WHERE id = '" & Q(id) & "'"
        Set rs = db.Query(sql)
        Set GetRegretById = rs
    End Function
    
    Public Function CheckRegretLimit(db, ip)
        Dim today, existingCount
        today = DateValue(Now())
        
        existingCount = db.Scalar("SELECT regret_count FROM rate_limits WHERE ip = '" & Q(ip) & "' AND window_date = '" & Q(today) & "'", 0)
        
        If existingCount >= 1 Then
            CheckRegretLimit = False
        Else
            CheckRegretLimit = True
        End If
    End Function
    
    Public Function IncrementRegretCount(db, ip)
        Dim today, existingCount
        today = DateValue(Now())
        
        existingCount = db.Scalar("SELECT regret_count FROM rate_limits WHERE ip = '" & Q(ip) & "' AND window_date = '" & Q(today) & "'", 0)
        
        db.Execute "INSERT OR REPLACE INTO rate_limits (ip, regret_count, vote_count, window_date) VALUES ('" & Q(ip) & "', " & (existingCount + 1) & ", " & GetVoteCount(db, ip) & ", '" & Q(today) & "')"
    End Function
    
    Public Function CheckVoteLimit(db, ip)
        Dim today, existingCount
        today = DateValue(Now())
        
        existingCount = db.Scalar("SELECT vote_count FROM rate_limits WHERE ip = '" & Q(ip) & "' AND window_date = '" & Q(today) & "'", 0)
        
        If existingCount >= 20 Then
            CheckVoteLimit = False
        Else
            CheckVoteLimit = True
        End If
    End Function
    
    Public Function GetVoteCount(db, ip)
        Dim today
        today = DateValue(Now())
        GetVoteCount = db.Scalar("SELECT vote_count FROM rate_limits WHERE ip = '" & Q(ip) & "' AND window_date = '" & Q(today) & "'", 0)
    End Function
    
    Public Function IncrementVoteCount(db, ip)
        Dim today, existingCount
        today = DateValue(Now())
        
        existingCount = GetVoteCount(db, ip)
        
        db.Execute "INSERT OR REPLACE INTO rate_limits (ip, regret_count, vote_count, window_date) VALUES ('" & Q(ip) & "', " & GetRegretCountForIP(db, ip) & ", " & (existingCount + 1) & ", '" & Q(today) & "')"
    End Function
    
    Public Function GetRegretCountForIP(db, ip)
        Dim today
        today = DateValue(Now())
        GetRegretCountForIP = db.Scalar("SELECT regret_count FROM rate_limits WHERE ip = '" & Q(ip) & "' AND window_date = '" & Q(today) & "'", 0)
    End Function
    
    Public Sub PurgeExpiredRegrets(db)
        Dim today, sql
        today = DateValue(Now())
        
        Dim rsStats
        Set rsStats = db.Query("SELECT category, SUM(me_too) as total_me_too, SUM(not_alone) as total_not_alone, COUNT(*) as total FROM regrets WHERE expires_at <= datetime('now') GROUP BY category")
        
        Dim totalRegrets, topCategory, totalMeToo, totalNotAlone
        totalRegrets = 0
        totalMeToo = 0
        totalNotAlone = 0
        topCategory = ""
        Dim maxCount
        maxCount = 0
        
        Do While Not rsStats.EOF
            totalRegrets = totalRegrets + CLng(Nz(rsStats("total"), 0))
            totalMeToo = totalMeToo + CLng(Nz(rsStats("total_me_too"), 0))
            totalNotAlone = totalNotAlone + CLng(Nz(rsStats("total_not_alone"), 0))
            If CLng(Nz(rsStats("total"), 0)) > maxCount Then
                maxCount = CLng(Nz(rsStats("total"), 0))
                topCategory = "" & rsStats("category")
            End If
            rsStats.MoveNext
        Loop
        rsStats.Close
        Set rsStats = Nothing
        
        If totalRegrets > 0 Then
            db.Execute "INSERT OR REPLACE INTO daily_archive (date, total_regrets, top_category, total_me_too, total_not_alone) VALUES ('" & Q(today) & "', " & totalRegrets & ", '" & Q(topCategory) & "', " & totalMeToo & ", " & totalNotAlone & ")"
        End If
        
        db.Execute "DELETE FROM regrets WHERE expires_at <= datetime('now')"
    End Sub
    
    Public Function GetDailyArchive(db)
        Dim sql, rs
        sql = "SELECT * FROM daily_archive ORDER BY date DESC LIMIT 30"
        Set rs = db.Query(sql)
        Set GetDailyArchive = rs
    End Function
    
    Public Function GetTotalStats(db)
        GetTotalStats = db.Scalar("SELECT SUM(total_regrets) FROM daily_archive", 0)
    End Function
    
    Public Function GetTopCategory(db)
        GetTopCategory = db.Scalar("SELECT top_category FROM daily_archive ORDER BY total_regrets DESC LIMIT 1", "")
    End Function
End Class
%>
