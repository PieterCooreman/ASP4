<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim exporter, action, docTitle, quillHtml, quillText, errMsg
Set exporter = New cls_pdf_export

action = LCase(Trim("" & Request.Form("action")))
docTitle = "" & Request.Form("doc_title")
quillHtml = "" & Request.Form("quill_html")
quillText = "" & Request.Form("quill_text")
errMsg = ""

If IsPost() And action = "download" Then
    On Error Resume Next
    Dim pdfPath
    pdfPath = exporter.BuildPdf(docTitle, quillHtml, quillText)
    If Err.Number <> 0 Then
        errMsg = "Could not generate PDF: " & Err.Description
        Err.Clear
    Else
        On Error GoTo 0
        Response.File pdfPath, False
        Response.End
    End If
    On Error GoTo 0
End If
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PDF Export Sample</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
  <link href="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.snow.css" rel="stylesheet">
  <style>
    .shell{max-width:1080px;margin:0 auto}
    #editor{height:360px}
  </style>
</head>
<body>
<main class="shell py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h4 mb-0">ASPpy PDF Export</h1>
    <span class="text-muted small">Quill -> server-side PDF</span>
  </div>

  <% If errMsg <> "" Then %>
    <div class="alert alert-danger"><%=H(errMsg)%></div>
  <% End If %>

  <div class="card border-0 shadow-sm">
    <div class="card-body">
      <form id="pdfForm" method="post" action="default.asp">
        <input type="hidden" name="action" value="download">
        <input type="hidden" name="quill_html" id="quillHtml">
        <input type="hidden" name="quill_text" id="quillText">

        <div class="mb-3">
          <label class="form-label" for="docTitle">Document title</label>
          <input class="form-control" id="docTitle" name="doc_title" value="<%=H(Nz(docTitle, "My Quill Document"))%>">
        </div>

        <div class="mb-3">
          <label class="form-label">Content (Quill editor)</label>
          <div id="editor"></div>
          <div class="form-text">The server receives Quill HTML and renders it with `ASPpy.pdf.write_html` (plain-text fallback if needed).</div>
        </div>

        <button class="btn btn-primary" type="submit">Download as PDF</button>
      </form>
    </div>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.min.js"></script>
<script>
  const quill = new Quill('#editor', {
    theme: 'snow',
    placeholder: 'Write here, then export as PDF...',
    modules: {
      toolbar: [
        [{ header: [1, 2, 3, false] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['blockquote', 'code-block'],
        ['link'],
        ['clean']
      ]
    }
  });

  const form = document.getElementById('pdfForm');
  const quillHtml = document.getElementById('quillHtml');
  const quillText = document.getElementById('quillText');

  quill.root.innerHTML = `<p><strong>ASPpy PDF sample</strong></p><p>This content is converted on the server.</p><ul><li>Quill HTML is posted</li><li>Plain text is posted</li><li>PDF is generated with ASPpy.pdf</li></ul>`;

  form.addEventListener('submit', () => {
    quillHtml.value = quill.root.innerHTML || '';
    quillText.value = quill.getText() || '';
  });
</script>
</body>
</html>
