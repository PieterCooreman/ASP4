<%
Class cls_settings
    Public Function GetOne(db)
        Set GetOne = db.Query("SELECT * FROM settings WHERE id=1 LIMIT 1")
    End Function

    Public Sub SaveBranding(db, title, slogan)
        db.Execute "UPDATE settings SET site_title='" & Q(title) & "',site_slogan='" & Q(slogan) & "',updated_at=datetime('now') WHERE id=1"
    End Sub

    Public Sub SaveFonts(db, bodyF, headF, btnF)
        db.Execute "UPDATE settings SET font_body='" & Q(bodyF) & "',font_heading='" & Q(headF) & "',font_button='" & Q(btnF) & "',updated_at=datetime('now') WHERE id=1"
    End Sub

    Public Sub SavePalette(db, p, s, okc, dn, w, i, l, dk, name)
        db.Execute "UPDATE settings SET palette_name='" & Q(name) & "',color_primary='" & Q(p) & "',color_secondary='" & Q(s) & "',color_success='" & Q(okc) & "',color_danger='" & Q(dn) & "',color_warning='" & Q(w) & "',color_info='" & Q(i) & "',color_light='" & Q(l) & "',color_dark='" & Q(dk) & "',updated_at=datetime('now') WHERE id=1"
    End Sub

    Public Sub ApplyPreset(db, presetName)
        Dim p
        Set p = PalettePreset(presetName)
        SavePalette db, p("primary"), p("secondary"), p("success"), p("danger"), p("warning"), p("info"), p("light"), p("dark"), p("name")
    End Sub
End Class
%>
