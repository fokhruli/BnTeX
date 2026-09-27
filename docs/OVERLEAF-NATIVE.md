# Native project: Overleaf handoff and unperformed browser gate

Status: the local project, explicit new-word edits, Unicode PDF strings and document
contexts have been exercised. **No actual Overleaf browser import/compile or
independent second-user reproduction was performed.** The connected tool catalog
had no Overleaf integration in this task. Do not mark this checklist complete
merely because local pdfLaTeX or GitHub Actions passed.

## Current wrapper-free authoring

Use [AUTOMATIC-AUTHORING.md](AUTOMATIC-AUTHORING.md) to export the audited
regular/bold family and stage `examples/automatic-authoring/project.json`.
That example types ordinary Bengali through `bntex-auto`, including standard
formatting; no per-passage `\bn` or `\bnNative` command is required.
The legacy explicit `examples/native-project` procedure below remains available.
Test the selected interface in the browser rather than transferring acceptance
from the other. Synthetic italic requires the explicit documented option.

## Build the upload on your machine

Follow NATIVE-INTEGRATION.md to compile/export the exact installed font and stage
`examples/native-project/project.json`. The resulting root contains `main.tex`,
`preamble.tex`, `sections/`, `references.tex`, `latexmkrc`, and the complete native
installation. Then run `native_project pack` locally. That ZIP includes your own
installed font; check your rights before sharing it. No font binary is provided
in this repository or downloadable development source overlay.

Overleaf's official documentation supports uploading a ZIP with the source
subdirectories retained. Choose **New Project -> Upload Project**, select the
locally generated ZIP, and verify that `main.tex` is at the root and selected as
the main document. Choose **pdfLaTeX** in the project compiler settings and record
the exact selected TeX Live version.

The supplied `latexmkrc` sets `$pdf_mode=1` and puts `-no-shell-escape` after the
ordinary compiler options. This is a trusted project build configuration, not a
shaping helper. The sample also checks `\pdfshellescape=0` and fails explicitly
if the configuration was not honored. Local direct-pdfLaTeX tests do not establish
Overleaf's actual configuration. If its system rules conflict, record the failure
and resolve those rules; do not remove the guard to invent a passing no-shell test.

## Manual acceptance record

Record the following only after actually doing it; leave absent facts unfilled:

- Reviewer and date; project source revision; font/profile/installation hashes.
- Overleaf compiler and selected TeX Live version; actual log engine banner.
- Initial successful compilation; readable Bengali pages, TOC, bookmarks, metadata,
  captions, tables, footnotes and references. Preserve the downloaded log and PDF.
- Add a new bare Bengali word for the automatic project (or use an explicit span
  for the legacy project), then recompile without changing
  the installation or invoking a preparer. Verify its rendering and extraction.
- Verify ordinary English/math editing and changes to an included source file.
- Verify the source filename case and helper/configuration files survived upload.
- Record timeouts and failures exactly. Test short and longer documents separately;
  the synthetic local 100-page measurement is not an Overleaf time-budget promise.
- Compare original Unicode in a second actual PDF viewer. pypdf/Poppler checks do
  not establish every viewer's search, clipboard behavior or PDF accessibility.

Do not upload build logs, generated PDFs named `main.pdf`, or private local files
as project sources. Download source edits before replacing any installation; the
project assembler refuses to overwrite existing user work.

## Official sources consulted

- Uploading projects: https://docs.overleaf.com/managing-projects-and-files/uploading-a-project
- Compiler/TeX Live selection: https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler
- Project-local latexmkrc: https://docs.overleaf.com/managing-projects-and-files/the-latexmkrc-file

These pages describe platform mechanisms, not evidence that this particular
BnTeX project has already been tested there.
