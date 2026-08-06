<%
' ============================================================================
' helpers.asp - Shared helper library for the Classic ASP/VBScript samples
' ----------------------------------------------------------------------------
' Include this file with:  <!--#include file="includes/helpers.asp"-->
' It defines reusable Subs, Functions and a Class used across all samples.
' ============================================================================

' --- HtmlEncode ------------------------------------------------------------
' Safely encodes a string for HTML output to prevent broken markup / XSS.
Function HtmlEncode(ByVal sText)
    Dim s
    s = sText & ""
    s = Replace(s, "&", "&amp;")
    s = Replace(s, "<", "&lt;")
    s = Replace(s, ">", "&gt;")
    s = Replace(s, """", "&quot;")
    s = Replace(s, "'", "&#39;")
    HtmlEncode = s
End Function

' --- WriteLine -------------------------------------------------------------
' Writes a string followed by a newline (keeps generated HTML readable).
Sub WriteLine(ByVal sText)
    Response.Write sText & vbCrLf
End Sub

' --- IsBlank ---------------------------------------------------------------
' Returns True when a value is Null, Empty or only whitespace.
Function IsBlank(ByVal v)
    If IsNull(v) Then
        IsBlank = True
    Else
        IsBlank = (Len(Trim(v & "")) = 0)
    End If
End Function

' --- Coalesce --------------------------------------------------------------
' Returns the first non-blank argument, or "" if both are blank.
Function Coalesce(ByVal a, ByVal b)
    If IsBlank(a) Then
        Coalesce = b
    Else
        Coalesce = a
    End If
End Function

' --- IIf -------------------------------------------------------------------
' Inline conditional helper (VBScript has no ternary operator). Returns
' truePart when cond is True, else falsePart. NOTE: unlike a real ternary,
' BOTH arguments are evaluated before IIf is called (no short-circuit), so
' never pass an expression that would error on the "not taken" branch.
Function IIf(ByVal cond, ByVal truePart, ByVal falsePart)
    If cond Then IIf = truePart Else IIf = falsePart
End Function

' --- RenderTableRow --------------------------------------------------------
' Emits a two-column <tr> with a label and an (encoded) value.
Sub RenderTableRow(ByVal sLabel, ByVal sValue)
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & _
              "</th><td>" & HtmlEncode(sValue) & "</td></tr>"
End Sub

' --- CodeBlock -------------------------------------------------------------
' Renders a snippet of source code inside a styled <pre> block.
Sub CodeBlock(ByVal sCode)
    WriteLine "<pre class=""code""><code>" & HtmlEncode(sCode) & "</code></pre>"
End Sub

' --- DemoBox start / end ---------------------------------------------------
' Wraps live demo output in a labelled panel.
Sub DemoStart(ByVal sTitle)
    WriteLine "<section class=""demo"">"
    WriteLine "  <h3>" & HtmlEncode(sTitle) & "</h3>"
    WriteLine "  <div class=""demo-output"">"
End Sub

Sub DemoEnd()
    WriteLine "  </div>"
    WriteLine "</section>"
End Sub

' ============================================================================
' Class: StringBuilder
' ----------------------------------------------------------------------------
' Efficiently concatenates many strings. Demonstrates a VBScript Class with
' a private field, a read-only property and methods.
' ============================================================================
Class StringBuilder
    Private m_parts
    Private m_count

    Private Sub Class_Initialize()
        ReDim m_parts(7)
        m_count = 0
    End Sub

    ' Append a value, growing the internal buffer as needed.
    Public Function Append(ByVal sText)
        If m_count > UBound(m_parts) Then
            ReDim Preserve m_parts(UBound(m_parts) * 2 + 1)
        End If
        m_parts(m_count) = sText & ""
        m_count = m_count + 1
        Set Append = Me      ' allow fluent chaining: sb.Append(..).Append(..)
    End Function

    ' Append text followed by a line break.
    Public Function AppendLine(ByVal sText)
        Append sText & vbCrLf
        Set AppendLine = Me
    End Function

    ' Read-only property: number of fragments appended.
    Public Property Get Count()
        Count = m_count
    End Property

    ' Materialise the final string.
    Public Function ToString()
        Dim used
        ReDim used(0)
        If m_count = 0 Then
            ToString = ""
        Else
            ReDim used(m_count - 1)
            Dim i
            For i = 0 To m_count - 1
                used(i) = m_parts(i)
            Next
            ToString = Join(used, "")
        End If
    End Function
End Class
%>
