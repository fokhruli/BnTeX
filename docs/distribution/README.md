# BnTeX installed-distribution candidate

Automatic Bengali in unmodified pdfLaTeX. Once the complete package is installed,
write `\usepackage{bntex}` and type ordinary Bengali/English text. Real bold uses
the audited Noto Serif Bengali Bold face. `[synthetic-italic]` explicitly enables
slanted emphasis; it is not a true italic face. Underline, color and sizes use
normal LaTeX commands. No profile loader, document word preparation, Python,
network or shell helper is required in document compilation.

This is an engineering candidate, not a CTAN release. Read the accompanying
installation scope and acceptance record. The resolver currently targets TeX
Live's standard TEXMF roots and default input-read policy. Behavior under
`openin_any=p` differs between the tested engines: the local pdfTeX 1.40.26
refuses symbolic-root checksums, whereas the TeX Live 2023 CI engine permits
them. The test first probes each checksum primitive, then requires successful
rendering with corruption rejection when readable, or a clear read-policy error
when not readable. This is not unrestricted platform or Overleaf certification.
The package never changes security settings or disables integrity checks.

If no TEXMF root resolves, the resolver checks each runtime asset by bare name,
which finds copies placed beside the document (for example a project upload),
against the same pinned MD5. MiKTeX does not expand `$TEXMF...` roots in file
names and its input search does not reach `fonts/`, so an installed MiKTeX TDS
tree is not yet supported; copying the runtime files beside the document works.

Original code: MIT (LICENSE), with retained THIRD-PARTY-NOTICES.md.
Fonts and font-derived data: SIL OFL 1.1 (OFL-1.1.txt and FONT-NOTICES.md).
No third-party font binaries are present in the source archive. The maintainer
build assembles exact audited fonts into a complete local runtime for validation.
Publication and redistributable upload approval are separate decisions.

Use the complete distribution through a TeX installer. Do not copy only .sty
files or rebuild profiles as a document author. A CTAN upload is not immediate
availability in any particular Overleaf TeX Live image. Actual Overleaf browser,
independent-user and new-style visual acceptance are not claimed.

## Complete inventory and source reproduction

The verifier requires the fixed release file set independently of the manifest's
hash list. Removing a required profile, font bank, notice, manual or build source
and deleting its manifest entry does not produce a verified distribution. It
also checks the original OFL text, corresponding runtime/source modules, matching
installed loaders, and absence of symlinks or unlisted files. These are consistency
checks on trusted distributions, not signatures or hostile-input authentication.

The complete TDS archive includes `source/latex/bntex/REPRODUCING.md`. A maintainer
can run the recorded `python -B -m bntex.distribution rebuild` command from that
source directory. It re-compiles the manual twice, runs the real font-profile
compilers, and requires the same manifest and archive bytes. The `-B` flag prevents
bytecode files from modifying the installed source tree. This reproduction tool
is not part of document authoring, and it neither downloads nor publishes files.

## Read-policy version note

Do not infer read-policy behavior from `openin_any=p` alone or change the host
policy to manufacture a pass. The upstream Kpathsea manual documents that the
input-name checks became no-ops in 2026; older libraries can still enforce them.
The package uses the configured engine unchanged and tests its actual primitive
capability. No tested local result establishes an Overleaf image's behavior.
Source: https://tug.org/texinfohtml/kpathsea.html#Safe-filenames
Change: https://ftp.tug.org/pipermail/tex-live-commits/2026-January/035883.html
