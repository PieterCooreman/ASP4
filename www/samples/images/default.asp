<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim db, gallery, m, action, flashMsg
Set db = New cls_db
db.Open
Set gallery = New cls_gallery

m = LCase(Trim("" & Request.QueryString("m")))
If m = "" Then m = "gallery"
action = LCase(Trim("" & Request.Form("action")))

If m = "upload" Then
    On Error Resume Next
    Dim up, outMsg
    Set up = Request.Files.Item("photo")
    If up Is Nothing Then
        Response.ContentType = "application/json"
        Response.Write "{""ok"":false,""message"":""No file provided""}"
        db.Close: Set db = Nothing
        Response.End
    End If

    gallery.SaveUpload db, up
    If Err.Number <> 0 Then
        outMsg = Replace(Err.Description, Chr(34), "")
        Err.Clear
        Response.ContentType = "application/json"
        Response.Write "{""ok"":false,""message"":""" & H(outMsg) & """}"
    Else
        Response.ContentType = "application/json"
        Response.Write "{""ok"":true}"
    End If
    db.Close: Set db = Nothing
    Response.End
End If

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" And m = "gallery" Then
    If action = "delete" Then
        gallery.DeleteImage db, Request.Form("id")
        SetFlash "Image deleted."
        db.Close: Set db = Nothing
        Response.Redirect "default.asp"
        Response.End
    End If
End If

If m = "download" Then
    Dim rsD, fDownload
    Set rsD = gallery.GetById(db, Request.QueryString("id"))
    If rsD.EOF Then
        rsD.Close: Set rsD = Nothing
        db.Close: Set db = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Not found"
        Response.End
    End If
    fDownload = Server.MapPath("" & rsD("rel_path"))
    rsD.Close: Set rsD = Nothing
    db.Close: Set db = Nothing
    Response.File fDownload, False
    Response.End
End If

If m = "filter_download" Then
    On Error Resume Next
    Dim dlData, dlName
    dlData = gallery.BuildFilterBytes(db, Request.QueryString("id"), Request.QueryString("f"))
    If Err.Number <> 0 Then
        Err.Clear
        db.Close: Set db = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Filter unavailable"
        Response.End
    End If

    dlName = "filter_" & ToInt(Request.QueryString("id"), 0) & "_" & LCase(Trim("" & Request.QueryString("f"))) & ".jpg"
    db.Close: Set db = Nothing
    Response.FileBytes dlData, "image/jpeg", dlName, False
End If

If m = "thumb" Then
    On Error Resume Next
    Dim thumbData
    thumbData = gallery.BuildThumbBytes(db, Request.QueryString("id"))
    If Err.Number <> 0 Then
        Err.Clear
        db.Close: Set db = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Thumb unavailable"
        Response.End
    End If
    db.Close: Set db = Nothing
    Response.ContentType = "image/jpeg"
    Response.BinaryWrite thumbData
    Response.End
End If

If m = "filter" Then
    On Error Resume Next
    Dim filterData
    filterData = gallery.BuildFilterBytes(db, Request.QueryString("id"), Request.QueryString("f"))
    If Err.Number <> 0 Then
        Err.Clear
        db.Close: Set db = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Filter unavailable"
        Response.End
    End If
    db.Close: Set db = Nothing
    Response.ContentType = "image/jpeg"
    Response.BinaryWrite filterData
    Response.End
End If

flashMsg = GetFlash()
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Images Sample</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
  <style>
    body{background:linear-gradient(180deg,#edf2ff,#f8fafc)}
    .grid-thumb{width:100%;height:220px;object-fit:cover;background:#e2e8f0}
    .filter-thumb{width:100%;height:160px;object-fit:cover;background:#e2e8f0;border-radius:.5rem}
  </style>
</head>
<body>
<main class="container py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h4 mb-0">ASPpy Photos</h1>
    <span id="uploadState" class="text-muted small"></span>
  </div>

  <% If flashMsg <> "" Then %><div class="alert alert-info"><%=H(flashMsg)%></div><% End If %>

  <div class="card border-0 shadow-sm mb-4">
    <div class="card-body">
      <label class="form-label">Upload images (multi-select)</label>
      <input id="multiUpload" class="form-control" type="file" name="photos" accept="image/*" multiple>
      <div class="form-text">One field, multiple file selection. Images are resized to max 1920px and thumbs to max 300px.</div>
    </div>
  </div>

  <div class="row g-3">
    <%
    Dim rs
    Set rs = gallery.ListImages(db)
    Do Until rs.EOF
    %>
    <div class="col-12 col-sm-6 col-md-4 col-lg-3">
      <div class="card border-0 shadow-sm h-100">
        <img class="grid-thumb" src="default.asp?m=thumb&id=<%=rs("id")%>" alt="">
        <div class="card-body">
          <div class="small text-truncate"><%=H(rs("original_name"))%></div>
          <div class="text-muted small"><%=H(Nz(rs("width"),""))%> x <%=H(Nz(rs("height"),""))%></div>
        </div>
        <div class="card-footer bg-white border-0 d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#filters_<%=rs("id")%>">Filters</button>
          <a class="btn btn-sm btn-outline-secondary" href="default.asp?m=download&id=<%=rs("id")%>">Download</a>
          <form method="post" action="default.asp?m=gallery" class="ms-auto">
            <input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<%=rs("id")%>">
            <button class="btn btn-sm btn-outline-danger" type="submit" onclick="return confirm('Delete image?')">Delete</button>
          </form>
        </div>
      </div>
    </div>

    <div class="modal fade" id="filters_<%=rs("id")%>" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-xl modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header"><h5 class="modal-title">Filter variants - <%=H(rs("original_name"))%></h5><button class="btn-close" type="button" data-bs-dismiss="modal"></button></div>
          <div class="modal-body">
            <div class="row g-3 filter-grid" data-id="<%=rs("id")%>">
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">BLUR</div><img class="filter-thumb" data-filter="BLUR" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=BLUR">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">CONTOUR</div><img class="filter-thumb" data-filter="CONTOUR" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=CONTOUR">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">DETAIL</div><img class="filter-thumb" data-filter="DETAIL" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=DETAIL">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">EDGE_ENHANCE</div><img class="filter-thumb" data-filter="EDGE_ENHANCE" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=EDGE_ENHANCE">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">EDGE_ENHANCE_MORE</div><img class="filter-thumb" data-filter="EDGE_ENHANCE_MORE" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=EDGE_ENHANCE_MORE">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">EMBOSS</div><img class="filter-thumb" data-filter="EMBOSS" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=EMBOSS">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">FIND_EDGES</div><img class="filter-thumb" data-filter="FIND_EDGES" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=FIND_EDGES">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">SHARPEN</div><img class="filter-thumb" data-filter="SHARPEN" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=SHARPEN">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">SMOOTH</div><img class="filter-thumb" data-filter="SMOOTH" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=SMOOTH">Download</a></div>
              <div class="col-12 col-sm-6 col-md-4"><div class="small mb-1">SMOOTH_MORE</div><img class="filter-thumb" data-filter="SMOOTH_MORE" alt=""><a class="btn btn-sm btn-outline-secondary mt-2" href="default.asp?m=filter_download&id=<%=rs("id")%>&f=SMOOTH_MORE">Download</a></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <% rs.MoveNext: Loop
    rs.Close: Set rs = Nothing %>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
<script>
const uploader = document.getElementById('multiUpload');
const state = document.getElementById('uploadState');

uploader.addEventListener('change', async () => {
  const files = Array.from(uploader.files || []);
  if (!files.length) return;
  let ok = 0;
  for (let i = 0; i < files.length; i++) {
    state.textContent = `Uploading ${i + 1}/${files.length}...`;
    const fd = new FormData();
    fd.append('photo', files[i]);
    const res = await fetch('default.asp?m=upload', { method: 'POST', body: fd });
    try {
      const j = await res.json();
      if (j && j.ok) ok++;
    } catch (e) {}
  }
  state.textContent = `Uploaded ${ok}/${files.length}`;
  setTimeout(() => window.location.reload(), 500);
});

document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('show.bs.modal', () => {
    const grid = modal.querySelector('.filter-grid');
    if (!grid) return;
    const id = grid.getAttribute('data-id');
    grid.querySelectorAll('img[data-filter]').forEach(img => {
      if (img.getAttribute('src')) return;
      const f = encodeURIComponent(img.getAttribute('data-filter'));
      img.src = `default.asp?m=filter&id=${id}&f=${f}&_=${Date.now()}`;
    });
  });
});
</script>
</body>
</html>
<%
db.Close
Set db = Nothing
%>
