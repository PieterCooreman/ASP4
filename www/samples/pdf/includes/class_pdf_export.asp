<%
Class cls_pdf_export
    Private Sub EnsureExportFolder()
        Dim fso, p
        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        p = Server.MapPath("exports")
        If Not fso.FolderExists(p) Then fso.CreateFolder p
        Set fso = Nothing
    End Sub

    Private Function HtmlToText(html)
        Dim t, rx
        t = "" & html

        Set rx = Server.CreateObject("VBScript.RegExp")
        rx.Global = True
        rx.IgnoreCase = True

        rx.Pattern = "<(br|br\s*/)>"
        t = rx.Replace(t, vbCrLf)
        rx.Pattern = "</(p|div|li|h1|h2|h3|h4|h5|h6)>"
        t = rx.Replace(t, vbCrLf)
        rx.Pattern = "<[^>]+>"
        t = rx.Replace(t, "")

        Set rx = Nothing

        t = Replace(t, "&nbsp;", " ")
        t = Replace(t, "&amp;", "&")
        t = Replace(t, "&lt;", "<")
        t = Replace(t, "&gt;", ">")
        t = Replace(t, "&quot;", Chr(34))
        t = Replace(t, "&#39;", "'")

        HtmlToText = t
    End Function

    Private Function EscapeHtml(s)
        Dim t
        t = "" & s
        t = Replace(t, "&", "&amp;")
        t = Replace(t, "<", "&lt;")
        t = Replace(t, ">", "&gt;")
        EscapeHtml = t
    End Function

    Public Function BuildPdf(title, quillHtml, quillText)
        Dim doc, bodyText, outPath, namePart, stamp, htmlOut, safeTitle

        EnsureExportFolder

        bodyText = Trim("" & quillText)
        If bodyText = "" Then bodyText = Trim(HtmlToText(quillHtml))
        If bodyText = "" Then bodyText = "(empty document)"

        namePart = SafeFilePart(title)
        stamp = Replace(CStr(Timer()), ".", "")
        outPath = Server.MapPath("exports/" & namePart & "_" & stamp & ".pdf")

        Set doc = ASPpy.pdf.New("P", "mm", "A4")
        doc.add_page
        doc.set_margins 15, 15, 15
        doc.set_auto_page_break True, 15

        safeTitle = EscapeHtml(Nz(title, "Untitled"))
        htmlOut = Trim("" & quillHtml)
        If htmlOut = "" Then
            htmlOut = "<p>" & EscapeHtml(bodyText) & "</p>"
        End If

        On Error Resume Next
        doc.write_html "<h1>" & safeTitle & "</h1>" & htmlOut
        If Err.Number <> 0 Then
            Err.Clear
            doc.set_font "Helvetica", "B", 16
            doc.multi_cell 0, 8, Nz(title, "Untitled"), 0, "L", False
            doc.ln 2
            doc.set_font "Helvetica", "", 11
            doc.multi_cell 0, 6, bodyText, 0, "L", False
        End If
        On Error GoTo 0

        doc.output outPath
        BuildPdf = outPath
    End Function
End Class
%>
