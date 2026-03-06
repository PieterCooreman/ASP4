<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%Option Explicit%>

<%
' ===================================================================
' ASP/VBScript section for processing the form data
' ===================================================================

Dim submittedContent

' Check if the request method is POST, which means the form has been submitted.
If Request.ServerVariables("REQUEST_METHOD") = "POST" Then
  ' Retrieve the HTML content from the hidden input field named 'editor_content'.
  submittedContent = Request.Form("editor_content")
End If
%>

<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>Quill Editor in ASP Classic</title>

	<!-- Bootstrap 5.3.8 -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
	<!-- Bootstrap Icons -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.0/font/bootstrap-icons.min.css" rel="stylesheet">
	<!-- Quill Snow theme -->
	<link href="https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.snow.css" rel="stylesheet">

	<style>
	#editor-container { height: 350px; }
	/* Add styles for code blocks and blockquotes for better display */
	.ql-snow .ql-editor pre.ql-syntax { background-color: #23241f; color: #f8f8f2; overflow: visible; padding: 10px; border-radius: 5px; }
	.ql-snow .ql-editor blockquote { border-left: 4px solid #ccc; margin-bottom: 5px; margin-top: 5px; padding-left: 16px; }
	</style>
</head>
<body class="bg-light">

	<!-- Navigation -->
	<nav class="navbar navbar-dark bg-dark">
		<div class="container">
			<a class="navbar-brand" href="../../default.asp">
				<i class="bi bi-code-slash me-2"></i>ASP Boilerplate
			</a>
			<a href="../../default.asp" class="btn btn-outline-light btn-sm">
				<i class="bi bi-arrow-left me-1"></i>Back to samples
			</a>
		</div>
	</nav>

	<main class="py-5">
		<div class="container">

			<div class="row justify-content-center">
				<div class="col-lg-9">

					<h1 class="fw-bold mb-1"><i class="bi bi-pencil-square me-2 text-primary"></i>Quill WYSIWYG Editor</h1>
					<p class="text-muted mb-4">ASP Classic &mdash; Full-option toolbar</p>

					<% If Not IsNull(submittedContent) And submittedContent <> "" Then %>
					<div class="card border-0 shadow-sm mb-4">
						<div class="card-header bg-success text-white">
							<i class="bi bi-check-circle me-2"></i>Submitted Content
						</div>
						<div class="card-body">
							<% 
								' Display the raw HTML content that was submitted from the form.
								Response.Write(server.htmlencode(submittedContent))
							%>
						</div>
					</div>
					<% End If %>

					<div class="card border-0 shadow-sm">
						<div class="card-header bg-white border-bottom">
							<i class="bi bi-type me-2 text-secondary"></i>Editor
						</div>
						<div class="card-body p-0">
							<form name="quillForm" method="post" action="default.asp" onsubmit="return copyContent()">
								<div id="editor-container">
									<%=submittedContent%>
								</div>

								<input type="hidden" name="editor_content" id="editor_content">

								<div class="p-3 border-top bg-light text-end">
									<button type="submit" class="btn btn-primary">
										<i class="bi bi-send me-1"></i>Submit to Server
									</button>
								</div>
							</form>
						</div>
					</div>

				</div>
			</div>

		</div>
	</main>

	<!-- Footer -->
	<footer class="bg-dark text-white-50 py-4 mt-5">
		<div class="container text-center">
			<small><i class="bi bi-code-slash me-1"></i>ASP Classic Boilerplate &mdash; Built with Bootstrap 5.3.8</small>
		</div>
	</footer>

	<!-- Popper + Bootstrap JS bundle -->
	<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>
	<!-- Quill -->
	<script src="https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.js"></script>

	<script>
	// The toolbar array contains a very extensive set of options.
	const fullToolbarOptions = [
		[{ 'font': [] }],
		[{ 'header': [1, 2, 3, 4, 5, 6, false] }],
		[{ 'size': ['small', false, 'large', 'huge'] }],
		['bold', 'italic', 'underline', 'strike'],
		['blockquote', 'code-block'],
		[{ 'color': [] }, { 'background': [] }],
		[{ 'list': 'ordered'}, { 'list': 'bullet' }, { 'list': 'check' }],
		[{ 'script': 'sub'}, { 'script': 'super' }],
		[{ 'indent': '-1'}, { 'indent': '+1' }],
		[{ 'direction': 'rtl' }],
		[{ 'align': [] }],
		['link', 'image', 'video', 'formula'],
		['clean']
	];

	// Initialize the Quill editor on the div element '#editor-container'
	const quill = new Quill('#editor-container', {
		modules: {
			toolbar: fullToolbarOptions // Use the extended toolbar configuration
		},
		theme: 'snow'
	});

	/**
	 * This function is called just before the form is submitted (via onsubmit).
	 * It copies the full HTML content from the editor into the hidden <input> field.
	 */
	function copyContent() {
		// Retrieve the HTML content from the editor
		const htmlContent = quill.root.innerHTML;

		// Assign the HTML content to the 'value' of the hidden input field
		document.getElementById('editor_content').value = htmlContent;

		// Ensure the form is actually submitted
		return true;
	}
	</script>

</body>
</html>