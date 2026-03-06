<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>ASP Classic – Sample Apps</title>
	<meta name="description" content="">	

	<!-- Bootstrap 5.3.8 -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
	<!-- Bootstrap Icons -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.0/font/bootstrap-icons.min.css" rel="stylesheet">
</head>
<body class="bg-light">

	<!-- Navigation -->
	<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
		<div class="container">
			<a class="navbar-brand" href="default.asp">
				<i class="bi bi-code-slash me-2"></i>ASP Boilerplate
			</a>
			<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav" aria-controls="mainNav" aria-expanded="false" aria-label="Toggle navigation">
				<span class="navbar-toggler-icon"></span>
			</button>
			<div class="collapse navbar-collapse" id="mainNav">
				<ul class="navbar-nav ms-auto">
					<li class="nav-item">
						<a class="nav-link active" href="default.asp"><i class="bi bi-house me-1"></i>Home</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" href="#"><i class="bi bi-info-circle me-1"></i>About</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" href="#"><i class="bi bi-envelope me-1"></i>Contact</a>
					</li>
				</ul>
			</div>
		</div>
	</nav>

	<!-- Hero -->
	<div class="bg-dark text-white py-5">
		<div class="container text-center">
			<i class="bi bi-grid-3x3-gap-fill display-4 mb-3 d-block"></i>
			<h1 class="display-5 fw-bold">Sample Applications</h1>
			<p class="lead">Browse and launch all available ASP Classic sample apps.</p>
		</div>
	</div>

	<!-- Main -->
	<main class="py-5">
		<div class="container">

			<%
			' ProperCase: capitalises the first letter of each word,
			' treating hyphens and underscores as word separators too.
			Function ProperCase(str)
				Dim words, i, separators, word
				' Replace common folder-name separators with a space so we can split on one character
				str = Replace(str, "-", " ")
				str = Replace(str, "_", " ")
				words = Split(LCase(str), " ")
				For i = 0 To UBound(words)
					If Len(words(i)) > 0 Then
						words(i) = UCase(Left(words(i), 1)) & Mid(words(i), 2)
					End If
				Next
				ProperCase = Join(words, " ")
			End Function

			' A pool of Bootstrap Icons to rotate through for visual variety
			Dim icons(9)
			icons(0) = "bi-window"
			icons(1) = "bi-file-earmark-code"
			icons(2) = "bi-database"
			icons(3) = "bi-table"
			icons(4) = "bi-bar-chart-line"
			icons(5) = "bi-puzzle"
			icons(6) = "bi-gear"
			icons(7) = "bi-layout-text-window"
			icons(8) = "bi-braces"
			icons(9) = "bi-box-seam"

			' A pool of Bootstrap colours to rotate through
			Dim colours(4)
			colours(0) = "text-primary"
			colours(1) = "text-success"
			colours(2) = "text-warning"
			colours(3) = "text-danger"
			colours(4) = "text-info"

			Dim fso, samplesFolder, subFolders, subFolder
			Dim folderPath, folderCount, iconIndex, colourIndex

			folderCount  = 0
			iconIndex    = 0
			colourIndex  = 0

			folderPath = Server.MapPath("samples")

			Set fso = CreateObject("Scripting.FileSystemObject")

			If fso.FolderExists(folderPath) Then
				Set samplesFolder = fso.GetFolder(folderPath)
				Set subFolders    = samplesFolder.SubFolders

				If subFolders.Count = 0 Then
			%>
				<div class="alert alert-info">
					<i class="bi bi-info-circle me-2"></i>No sample folders found in <code>/samples</code>.
				</div>
			<%
				Else
			%>
				<div class="row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-xl-4 g-4">
			<%
					For Each subFolder In subFolders
						folderCount = folderCount + 1
						iconIndex   = (folderCount - 1) Mod 10
						colourIndex = (folderCount - 1) Mod 5
			%>
					<div class="col">
						<div class="card h-100 shadow-sm border-0">
							<div class="card-body text-center">
								<i class="bi <%=icons(iconIndex)%> <%=colours(colourIndex)%> fs-1 mb-3 d-block"></i>
								<h5 class="card-title fw-semibold"><%=subFolder.Name%></h5>
								<p class="card-text text-muted small">Sample application</p>
							</div>
							<div class="card-footer bg-transparent border-0 text-center pb-3">
								<a href="samples/<%=subFolder.Name%>/" class="btn btn-dark btn-sm" target="_blank" rel="noopener noreferrer">
									<i class="bi bi-play-fill me-1"></i>Launch
								</a>
							</div>
						</div>
					</div>
			<%
					Next
			%>
				</div>
				<p class="text-muted mt-4 small"><i class="bi bi-folder2-open me-1"></i><%=folderCount%> sample(s) found.</p>
			<%
				End If

				Set subFolders    = Nothing
				Set samplesFolder = Nothing
			Else
			%>
			<div class="alert alert-warning">
				<i class="bi bi-exclamation-triangle me-2"></i>The <code>/samples</code> folder does not exist on this server.
			</div>
			<%
			End If

			Set fso = Nothing
			%>

		</div>
	</main>

	<!-- Footer -->
	<footer class="bg-dark text-white-50 py-4 mt-auto">
		<div class="container text-center">
			<p class="mb-1">
				<i class="bi bi-code-slash me-1"></i>
				ASP Classic Boilerplate &mdash; Built with Bootstrap 5.3.8
			</p>
			<small><i class="bi bi-c-circle me-1"></i>Your Company &mdash; All rights reserved.</small>
		</div>
	</footer>

	<!-- Popper + Bootstrap JS bundle -->
	<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>

</body>
</html>