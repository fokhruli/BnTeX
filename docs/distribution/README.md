# BnTeX installed-distribution candidate

Automatic Bengali in unmodified pdfLaTeX. Once the complete package is installed,
write `\usepackage{bntex}` and type ordinary Bengali/English text. Real bold uses
the audited Noto Serif Bengali Bold face. `[synthetic-italic]` explicitly enables
slanted emphasis; it is not a true italic face. Underline, color and sizes use
normal LaTeX commands. No profile loader, document word preparation, Python,
network or shell helper is required in document compilation.

This is an engineering candidate, not a CTAN release. Read the accompanying
installation scope and acceptance record. The resolver currently targets TeX
Live's standard TEXMF roots and default input-read policy. Strict
`openin_any=p` disallows its symbolic-root file checks; that restricted-policy
compatibility gate remains blocked. The package never changes security settings
or disables integrity checks to hide this condition.

Original code: MIT (LICENSE), with retained THIRD-PARTY-NOTICES.md.
Fonts and font-derived data: SIL OFL 1.1 (OFL-1.1.txt and FONT-NOTICES.md).
No third-party font binaries are present in the source archive. The maintainer
build assembles exact audited fonts into a complete local runtime for validation.
Publication and redistributable upload approval are separate decisions.

Use the complete distribution through a TeX installer. Do not copy only .sty
files or rebuild profiles as a document author. A CTAN upload is not immediate
availability in any particular Overleaf TeX Live image. Actual Overleaf browser,
independent-user and new-style visual acceptance are not claimed.
